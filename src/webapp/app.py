"""Run with python -m src.webapp.app setup|serve. Bound to loopback only."""
import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
import uuid
from datetime import datetime
from getpass import getpass
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Flask, abort, g, jsonify, render_template, request, send_from_directory
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash

from .runtime import Runtime
from .store import Store
from .vision import ROOT, camera_address, normalise_image


def load_environment():
    """Read only the documented variables. Environment takes precedence."""
    path = ROOT / '.env'
    allowed = {'WEBAPP_DATA_DIR', 'WEBAPP_ORIGIN', 'WEBAPP_PORT', 'OPENAI_API_KEY'}
    if path.exists():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            key, sep, value = line.strip().partition('=')
            if sep and key in allowed:
                os.environ.setdefault(key, value.strip().strip('"').strip("'"))


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def event_dict(row):
    result = dict(row)
    for key in ('report', 'analysis'):
        result[key] = json.loads(result[key]) if result[key] else None
    return result


def create_app(data_dir=None, origin=None, start_workers=False):
    app = Flask(__name__)
    app.config.update(MAX_CONTENT_LENGTH=9 * 1024 * 1024)
    origin = (origin or os.environ.get('WEBAPP_ORIGIN', 'http://127.0.0.1:8080')).rstrip('/')
    parsed = urlsplit(origin)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.path or parsed.query or parsed.fragment or parsed.username:
        raise ValueError('WEBAPP_ORIGIN 必须是完整且不含路径的地址。')
    if parsed.scheme == 'http' and parsed.hostname not in ('127.0.0.1', 'localhost'):
        raise ValueError('远程入口必须使用 HTTPS。')
    app.config['TRUSTED_HOSTS'] = [parsed.hostname]
    app.config['PUBLIC_ORIGIN'] = origin
    store = Store(data_dir or os.environ.get('WEBAPP_DATA_DIR', str(ROOT / 'outputs' / 'webapp')))
    runtime = Runtime(store)
    app.extensions.update(store=store, runtime=runtime)

    def body():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ValueError('请发送 JSON 对象。')
        return data

    def text(data, key, maximum=120, required=True):
        value = data.get(key, '')
        if not isinstance(value, str) or len(value.strip()) > maximum or (required and not value.strip()):
            raise ValueError(f'{key} 内容无效或过长。')
        return value.strip()

    def request_key(data):
        key = text(data, 'request_key', 100)
        if not re.fullmatch(r'[A-Za-z0-9_-]{8,100}', key):
            raise ValueError('请求编号无效。')
        return key

    def session_row():
        value = request.cookies.get('litter_session', '')
        if len(value) > 200:
            return None
        return store.one('SELECT * FROM sessions WHERE token=? AND expires>?', (token_hash(value), time.time()))

    @app.before_request
    def protect():
        # No trusting X-Forwarded-Host/Proto. Tunnel preserves the configured Host.
        if request.host != parsed.netloc:
            abort(400, '入口地址不匹配，请使用配置的 WEBAPP_ORIGIN。')
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            if request.headers.get('Origin') != origin:
                abort(403, '请求来源无效。')
        if request.path.startswith('/static/') or request.path in ('/', '/api/login'):
            return
        g.auth = session_row()
        if not g.auth:
            abort(401, '请先登录。')
        if request.method != 'GET' and not hmac.compare_digest(request.headers.get('X-CSRF-Token', ''), g.auth['csrf']):
            abort(403, '安全令牌无效，请刷新页面。')

    @app.after_request
    def headers(response):
        response.headers.update({
            'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
            'Referrer-Policy': 'no-referrer', 'X-Frame-Options': 'DENY',
            'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
            'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
        })
        if parsed.scheme == 'https':
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        return response

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error=error.description), error.code

    @app.errorhandler(ValueError)
    def validation_error(error):
        return jsonify(error=str(error)), 400

    @app.errorhandler(sqlite3.IntegrityError)
    def conflict(error):
        return jsonify(error='记录冲突，请刷新后重试。'), 409

    @app.get('/')
    def index():
        return render_template('index.html', signed_in=bool(session_row()), configured=bool(store.one('SELECT id FROM owner')))

    @app.post('/api/login')
    def login():
        data = body()
        now = time.time()
        with store.connect() as db:
            db.execute('DELETE FROM login_attempts WHERE at<?', (now - 900,))
            db.execute('DELETE FROM sessions WHERE expires<?', (now,))
            if db.execute('SELECT COUNT(*) FROM login_attempts').fetchone()[0] >= 5:
                abort(429, '登录尝试过多，请 15 分钟后重试。')
            # Reserve attempt before expensive password hashing, including concurrent requests.
            db.execute('INSERT INTO login_attempts VALUES(?)', (now,))
        name = text(data, 'name', 80)
        password = data.get('password', '')
        if not isinstance(password, str) or len(password) > 256:
            abort(401, '账号或密码错误。')
        owner = store.one('SELECT * FROM owner WHERE id=1')
        if not owner or name != owner['name'] or not check_password_hash(owner['password'], password):
            abort(401, '账号或密码错误。')
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with store.connect() as db:
            db.execute('DELETE FROM login_attempts')
            db.execute('INSERT INTO sessions VALUES(?,?,?)', (token_hash(token), csrf, now + 43200))
        response = jsonify(ok=True)
        response.set_cookie('litter_session', token, max_age=43200, httponly=True, secure=parsed.scheme == 'https', samesite='Strict', path='/')
        return response

    @app.post('/api/logout')
    def logout():
        store.execute('DELETE FROM sessions WHERE token=?', (g.auth['token'],))
        response = jsonify(ok=True)
        response.delete_cookie('litter_session', path='/')
        return response

    @app.get('/api/state')
    def state():
        camera = runtime.camera_status()
        latest = store.one('SELECT * FROM events ORDER BY captured_at DESC LIMIT 1')
        settings = store.settings()
        owner = store.one('SELECT name FROM owner WHERE id=1')
        return jsonify(csrf=g.auth['csrf'], server_time=time.time(), owner=owner['name'], camera=camera,
                       motor=runtime.motor.status(), settings=settings,
                       ai_configured=bool(os.environ.get('OPENAI_API_KEY')),
                       cats=store.rows('SELECT * FROM cats ORDER BY name'),
                       latest=event_dict(latest) if latest else None,
                       commands=store.rows('SELECT * FROM commands ORDER BY created_at DESC LIMIT 30'),
                       jobs=store.rows('SELECT * FROM jobs ORDER BY created_at DESC LIMIT 10'),
                       notifications=store.rows('SELECT * FROM notifications ORDER BY created_at DESC LIMIT 50'),
                       counts=dict(visits=store.one("SELECT COUNT(*) AS n FROM events WHERE kind='visit'")['n'],
                                   real_cleanings=0,
                                   simulations=store.one("SELECT COUNT(*) AS n FROM commands WHERE mode='simulation' AND action='clean' AND status='completed'")['n']))

    @app.get('/api/events')
    def events():
        clauses, params = [], []
        cat = request.args.get('cat', '')
        date = request.args.get('date', '')
        if cat == 'unknown':
            clauses.append('cat_id IS NULL')
        elif cat:
            clauses.append('cat_id=?')
            params.append(cat)
        if date:
            try:
                # Fixed UTC+8, no platform timezone database dependency on Windows.
                from datetime import timezone, timedelta
                start = datetime.strptime(date, '%Y-%m-%d').replace(tzinfo=timezone(timedelta(hours=8))).timestamp()
            except ValueError:
                raise ValueError('日期格式应为 YYYY-MM-DD。') from None
            clauses.append('captured_at>=? AND captured_at<?')
            params.extend([start, start + 86400])
        where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
        offset = request.args.get('offset', '0')
        if not offset.isdigit() or len(offset) > 7:
            raise ValueError('分页参数无效。')
        rows = store.rows('SELECT * FROM events' + where + ' ORDER BY captured_at DESC LIMIT 30 OFFSET ?', (*params, int(offset)))
        return jsonify(events=[event_dict(r) for r in rows])

    @app.get('/api/events/<identifier>')
    def event(identifier):
        row = store.one('SELECT * FROM events WHERE id=?', (identifier,))
        if not row:
            abort(404, '记录不存在。')
        return jsonify(event_dict(row))

    @app.post('/api/events/<identifier>/cat')
    def assign_cat(identifier):
        data = body()
        cat = data.get('cat_id') or None
        if cat is not None and (not isinstance(cat, str) or not store.one('SELECT id FROM cats WHERE id=?', (cat,))):
            raise ValueError('猫咪资料不存在。')
        if not store.execute('UPDATE events SET cat_id=? WHERE id=?', (cat, identifier)):
            abort(404, '记录不存在。')
        # The analysis records its original context; reassigning never silently changes it.
        return jsonify(ok=True)

    @app.post('/api/events/<identifier>/retry')
    def retry(identifier):
        if not store.settings()['cloud_analysis'] or not os.environ.get('OPENAI_API_KEY'):
            raise ValueError('请先配置密钥并启用云端 AI 分析。')
        if not store.execute("UPDATE events SET analysis_status='pending',error=NULL WHERE id=? AND analysis_status NOT IN ('pending','running')", (identifier,)):
            abort(409, '记录不存在或分析已在等待／运行中。')
        return jsonify(ok=True)

    @app.post('/api/capture')
    def capture():
        key = request_key(body())
        if not store.settings()['camera_url']:
            raise ValueError('请先设置相机地址。')
        with store.connect() as db:
            previous = db.execute('SELECT * FROM jobs WHERE request_key=?', (key,)).fetchone()
            if previous:
                return jsonify(dict(previous))
            if db.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('pending','running')").fetchone()[0] >= 3:
                abort(429, '拍照任务处理中，请稍候。')
            identifier = str(uuid.uuid4())
            db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)', (identifier, 'capture', None, 'pending', None, time.time(), key))
        return jsonify(id=identifier, status='pending'), 202

    @app.post('/api/cats')
    def save_cat():
        data = body()
        name, age = text(data, 'name', 60), text(data, 'age', 60, False)
        identifier = text(data, 'id', 100, False) or str(uuid.uuid4())
        existing = store.one('SELECT * FROM cats WHERE id=?', (identifier,))
        store.execute('INSERT INTO cats VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,age=excluded.age',
                      (identifier, name, age, existing['photo'] if existing else None))
        return jsonify(id=identifier)

    @app.post('/api/cats/<identifier>/photo')
    def cat_photo(identifier):
        if not store.one('SELECT id FROM cats WHERE id=?', (identifier,)):
            abort(404, '猫咪资料不存在。')
        upload = request.files.get('photo')
        if not upload:
            raise ValueError('请选择猫咪照片。')
        try:
            data = normalise_image(upload.read())
        except Exception:
            raise ValueError('请选择有效的 JPG、PNG 或其他照片，大小不超过 8 MB。') from None
        filename = str(uuid.uuid4()) + '.jpg'
        (store.directory / 'media' / filename).write_bytes(data)
        store.execute('UPDATE cats SET photo=? WHERE id=?', (filename, identifier))
        return jsonify(ok=True)

    @app.post('/api/settings')
    def settings():
        data = body()
        values = {}
        for field in ('monitor', 'cloud_analysis', 'notifications'):
            if field in data:
                if type(data[field]) is not bool:
                    raise ValueError(field + ' 必须是开关。')
                values[field] = data[field]
        if 'camera_url' in data:
            try:
                values['camera_url'] = camera_address(text(data, 'camera_url', 200, False))
            except OSError:
                raise ValueError('无法解析相机地址。') from None
        if 'ai_model' in data:
            model = text(data, 'ai_model', 100)
            if not re.fullmatch(r'[A-Za-z0-9_.:-]+', model):
                raise ValueError('模型名称无效。')
            values['ai_model'] = model
        if 'serial_port' in data:
            port = text(data, 'serial_port', 30, False)
            if port and not re.fullmatch(r'COM[1-9][0-9]{0,2}', port):
                raise ValueError('Arduino 端口格式应为 COM3 等 Windows COM 端口。')
            values['serial_port'] = port
        store.configure(values)
        return jsonify(ok=True)

    @app.post('/api/account')
    def account():
        data = body()
        owner = store.one('SELECT * FROM owner WHERE id=1')
        current = data.get('current_password', '')
        password = data.get('new_password', '')
        if not isinstance(current, str) or len(current) > 256 or not check_password_hash(owner['password'], current):
            abort(403, '当前密码错误。')
        if not isinstance(password, str) or not 12 <= len(password) <= 256:
            raise ValueError('新密码需要 12–256 个字符。')
        name = text(data, 'name', 80)
        with store.connect() as db:
            db.execute('UPDATE owner SET name=?,password=? WHERE id=1', (name, generate_password_hash(password)))
            db.execute('DELETE FROM sessions')
        return jsonify(ok=True)

    @app.post('/api/motor/clean')
    def motor_clean():
        data = body()
        mode = data.get('mode', 'real')
        scenario = data.get('scenario', 'clear')
        if mode not in ('real', 'simulation') or scenario not in ('clear', 'cat', 'unknown', 'sensor', 'offline'):
            raise ValueError('控制参数无效。')
        return jsonify(runtime.motor.request(request_key(data), mode, scenario))

    @app.post('/api/motor/stop')
    def motor_stop():
        return jsonify(runtime.motor.stop(request_key(body())))

    @app.post('/api/notifications/read')
    def read_notifications():
        store.execute('UPDATE notifications SET read=1')
        return jsonify(ok=True)

    @app.get('/media/<filename>')
    def media(filename):
        # Only media referenced by a saved record is readable, even by the owner.
        if filename == 'latest.jpg':
            if not (store.directory / 'media' / filename).exists():
                abort(404)
        elif not (store.one('SELECT id FROM events WHERE original=? OR detection=?', (filename, filename))
                  or store.one('SELECT id FROM cats WHERE photo=?', (filename,))):
            abort(404)
        return send_from_directory(store.directory / 'media', filename)

    if start_workers:
        runtime.start()
    return app


def main():
    load_environment()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['setup', 'serve'])
    args = parser.parse_args()
    if args.command == 'setup':
        store = Store(os.environ.get('WEBAPP_DATA_DIR', str(ROOT / 'outputs' / 'webapp')))
        if store.one('SELECT id FROM owner'):
            raise SystemExit('主人账号已存在。请登录页面设置修改账号。')
        name = input('主人账号（默认 owner）: ').strip() or 'owner'
        password = getpass('设置密码（至少 12 字符）: ')
        if len(name) > 80 or not 12 <= len(password) <= 256 or password != getpass('再次输入密码: '):
            raise SystemExit('账号／密码格式不正确，或两次密码不同。')
        store.execute('INSERT INTO owner VALUES(1,?,?)', (name, generate_password_hash(password)))
        print('账号已创建。运行 start-webapp.cmd 启动。')
        return
    # One process owns camera, SQLite jobs and serial. No auto-reloader/multi-worker deployment.
    import atexit
    from waitress import serve
    port = int(os.environ.get('WEBAPP_PORT', '8080'))
    app = create_app(start_workers=True)
    atexit.register(app.extensions['runtime'].shutdown)
    if not app.extensions['store'].one('SELECT id FROM owner'):
        raise SystemExit('请先运行 setup-webapp.cmd 创建主人账号。')
    print('WebApp: ' + app.config['PUBLIC_ORIGIN'], flush=True)
    print('真实 motor 启动已禁用。Ctrl+C 结束。', flush=True)
    serve(app, host='127.0.0.1', port=port, threads=6, max_request_body_size=9 * 1024 * 1024)


if __name__ == '__main__':
    main()
