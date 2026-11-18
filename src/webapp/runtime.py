"""Single-process workers. Motor STOP never waits behind inference or cloud requests."""
import json
import logging
import threading
import time
import uuid

from .analysis import analyse
from .vision import Detector, fetch_photo

LOG = logging.getLogger(__name__)


class Motor:
    """Simulate cycles; the real serial adapter can ONLY transmit stop."""
    def __init__(self, store):
        self.store = store
        self.lock = threading.RLock()
        self.active = None
        self.serial = None
        self.serial_port = ''
        self.serial_error = ''
        self.sensor = None
        self.last_telemetry = 0
        self.connected = False
        self.buffer = b''
        self.port_changed_at = 0
        store.execute("UPDATE commands SET status='failed',reason='服务器重启；旧启动指令不会重放。',updated_at=? WHERE status IN ('pending','running')", (time.time(),))

    def request(self, key, mode, scenario='clear'):
        with self.lock:
            old = self.store.one('SELECT * FROM commands WHERE request_key=?', (key,))
            if old:
                if old['mode'] != mode or old['action'] != 'clean':
                    raise ValueError('请求编号已用于其他操作。')
                return old
            now = time.time()
            reason = ''
            if mode != 'simulation':
                reason = '真实清理未开放：机构位置反馈、卡住处理与整机测试尚未验收。'
            elif self.active:
                reason = '已有模拟清理正在运行。'
            elif scenario != 'clear':
                reason = {'cat': '模拟猫咪进入，禁止启动。', 'unknown': '模拟视觉未知或过期，禁止启动。',
                          'sensor': '模拟传感器异常，禁止启动。', 'offline': '模拟通信中断，禁止启动。'}[scenario]
            identifier = str(uuid.uuid4())
            status = 'rejected' if reason else 'pending'
            self.store.execute('INSERT INTO commands VALUES(?,?,?,?,?,?,?,?,?,?)',
                               (identifier, key, 'clean', mode, status, reason, now, now + 5, now))
            if status == 'pending':
                self.active = identifier
            return self.store.one('SELECT * FROM commands WHERE id=?', (identifier,))

    def stop(self, key, reason='主人请求停止。'):
        with self.lock:
            old = self.store.one('SELECT * FROM commands WHERE request_key=?', (key,))
            if old:
                if old['action'] != 'stop':
                    raise ValueError('请求编号已用于其他操作。')
                return old
            now = time.time()
            if self.active:
                self.store.execute("UPDATE commands SET status='stopped',reason=?,updated_at=? WHERE id=?", (reason, now, self.active))
                self.active = None
            # Existing SensorMotorTest understands x. Serial write is bounded.
            sent = False
            if self.serial:
                try:
                    self.serial.write(b'x\n')
                    sent = True
                except Exception:
                    self.disconnect()
            identifier = str(uuid.uuid4())
            self.store.execute('INSERT INTO commands VALUES(?,?,?,?,?,?,?,?,?,?)',
                               (identifier, key, 'stop', 'serial' if sent else 'simulation',
                                'pending' if sent else 'stopped',
                                '停止已发送，等待硬件确认。' if sent else '模拟已停止；未连接硬件，无法确认真实 motor。',
                                now, now + 3, now))
            return self.store.one('SELECT * FROM commands WHERE id=?', (identifier,))

    def disconnect(self):
        if self.serial:
            try:
                self.serial.close()
            except Exception:
                pass
        self.serial = None
        self.connected = False
        self.sensor = None
        self.last_telemetry = 0
        self.buffer = b''

    def tick(self):
        with self.lock:
            now = time.time()
            if self.active:
                row = self.store.one('SELECT * FROM commands WHERE id=?', (self.active,))
                if row['status'] == 'pending' and now > row['expires_at']:
                    self.store.execute("UPDATE commands SET status='failed',reason='模拟启动已过期。',updated_at=? WHERE id=?", (now, self.active))
                    self.active = None
                elif row['status'] == 'pending' and now - row['created_at'] >= .5:
                    self.store.execute("UPDATE commands SET status='running',reason='仅模拟：未向硬件发送启动。',updated_at=? WHERE id=?", (now, self.active))
                elif row['status'] == 'running' and now - row['updated_at'] >= 3:
                    self.store.execute("UPDATE commands SET status='completed',reason='模拟循环完成；不计入真实清理次数。',updated_at=? WHERE id=?", (now, self.active))
                    self.store.notify('motor:' + self.active, '模拟清理完成，未运行真实 motor。')
                    self.active = None
            self.store.execute("UPDATE commands SET status='failed',reason='停止确认超时，真实 motor 状态未知；请使用实体停止。',updated_at=? WHERE action='stop' AND status='pending' AND expires_at<?", (now, now))
            port = self.store.settings()['serial_port']
            if port != self.serial_port:
                self.disconnect()
                self.serial_port = port
                self.port_changed_at = 0
            if port and not self.serial and now - self.port_changed_at > 5:
                self.port_changed_at = now
                try:
                    import serial
                    self.serial = serial.Serial(port, 9600, timeout=0, write_timeout=.2)
                    self.connected = True
                    self.serial_error = ''
                    # Opening Uno resets it. Clear any previous permission immediately.
                    self.serial.write(b'x\n')
                except Exception:
                    self.disconnect()
                    self.serial_error = 'Arduino 连接失败，请检查 COM 端口与 USB。'
                    self.store.notify('serial-offline', self.serial_error)
            if self.serial:
                try:
                    self.buffer += self.serial.read(min(self.serial.in_waiting, 4096))
                    if len(self.buffer) > 8192:
                        self.buffer = b''
                    while b'\n' in self.buffer:
                        line, self.buffer = self.buffer.split(b'\n', 1)
                        try:
                            status = json.loads(line)
                        except (ValueError, UnicodeError):
                            continue
                        if not isinstance(status, dict) or status.get('protocol') != 'litter-status-v1':
                            continue
                        self.last_telemetry = now
                        self.sensor = status.get('sensor_clear') if type(status.get('sensor_clear')) is bool else None
                        if status.get('motor') == 'stopped':
                            self.store.execute("UPDATE commands SET status='stopped',reason='硬件报告 motor 已停止。',updated_at=? WHERE action='stop' AND status='pending'", (now,))
                except Exception:
                    self.disconnect()
                    self.serial_error = 'Arduino 通信中断；硬件状态未知。'
                    self.store.notify('serial-offline', self.serial_error)

    def status(self):
        with self.lock:
            fresh = time.time() - self.last_telemetry < 3
            return dict(real_enabled=False, serial_connected=self.connected, serial_error=self.serial_error,
                        sensor_clear=self.sensor if fresh else None, telemetry_fresh=fresh,
                        waste_bin='unknown', active=self.active,
                        reason='真实清理未开放；需要完成机构与整机安全验收。')


class Runtime:
    def __init__(self, store):
        self.store = store
        self.motor = Motor(store)
        self.stop_event = threading.Event()
        self.detector = None
        self.camera = dict(status='unknown', cat_present=None, captured_at=None, error='尚未收到照片。')
        self.camera_lock = threading.Lock()
        self.capture_lock = threading.Lock()
        self.visit = None
        self.confirm_next = False
        self.camera_source = None
        self.threads = []
        store.execute("UPDATE jobs SET status='failed',error='服务器重启，请手动重试。' WHERE status IN ('pending','running')")
        store.execute("UPDATE events SET analysis_status='failed',error='服务器重启，请重试分析。' WHERE analysis_status='running'")

    def start(self):
        for target in (self.capture_loop, self.analysis_loop, self.motor_loop):
            thread = threading.Thread(target=target, daemon=True)
            self.threads.append(thread)
            thread.start()

    def shutdown(self):
        self.stop_event.set()
        self.motor.stop(str(uuid.uuid4()), '服务器关闭。')
        for thread in self.threads:
            thread.join(timeout=2)
        with self.motor.lock:
            self.motor.disconnect()

    def get_detector(self):
        if self.detector is None:
            self.detector = Detector()
        return self.detector

    def camera_status(self):
        with self.camera_lock:
            status = self.camera.copy()
        if status['captured_at'] is None or time.time() - status['captured_at'] > 4:
            status.update(status='stale', cat_present=None)
        return status

    def set_camera(self, **values):
        with self.camera_lock:
            self.camera.update(values)

    def save_event(self, data, kind, source_key, captured_at):
        existing = self.store.one('SELECT id FROM events WHERE source_key=?', (source_key,))
        if existing:
            return existing['id']
        identifier = str(uuid.uuid4())
        photo_name = identifier + '.jpg'
        (self.store.directory / 'media' / photo_name).write_bytes(data)
        # Store original BEFORE running any detector.
        self.store.execute('INSERT INTO events(id,source_key,kind,captured_at,original,report,analysis_status) VALUES(?,?,?,?,?,?,?)',
                           (identifier, source_key, kind, captured_at, photo_name,
                            json.dumps({'status': 'unknown'}), 'pending'))
        try:
            report, detected = self.get_detector().waste(data)
            detection_name = identifier + '-detection.jpg'
            (self.store.directory / 'media' / detection_name).write_bytes(detected)
            self.store.execute('UPDATE events SET report=?,detection=? WHERE id=?',
                               (json.dumps(report), detection_name, identifier))
        except Exception:
            self.store.execute('UPDATE events SET error=? WHERE id=?', ('本地检测失败，请检查模型与 Python 环境。原图已保留。', identifier))
        return identifier

    def capture(self, key, kind='manual'):
        with self.capture_lock:
            started = time.monotonic()
            captured_at = time.time()
            data = fetch_photo(self.store.settings()['camera_url'])
            # Snapshot is private and always has its own timestamp in status.
            (self.store.directory / 'media' / 'latest.jpg').write_bytes(data)
            self.set_camera(captured_at=captured_at, status='unknown', cat_present=None, error='')
            cat = None
            try:
                cat = self.get_detector().cat(data)
                if time.monotonic() - started > 4:
                    raise ValueError('照片判断超时。')
                self.set_camera(status='ok', cat_present=cat)
            except Exception:
                self.set_camera(status='unknown', cat_present=None, error='猫咪检测失败或耗时过长；状态未知。')
            if kind == 'manual':
                return self.save_event(data, kind, key, captured_at)
            from monitor_camera import Visit
            if self.visit is None:
                self.visit = Visit()
            ready = self.visit.observe(cat if self.camera_status()['status'] == 'ok' else None, started)
            if ready and self.confirm_next:
                event_id = self.save_event(data, 'visit', key, captured_at)
                self.visit = Visit()
                self.confirm_next = False
                return event_id
            self.confirm_next = ready
            return None

    def capture_loop(self):
        next_capture = 0
        while not self.stop_event.is_set():
            settings = self.store.settings()
            source = (settings['camera_url'], settings['monitor'])
            if source != self.camera_source:
                self.visit = None
                self.confirm_next = False
                self.camera_source = source
                self.set_camera(status='unknown', cat_present=None, captured_at=None, error='等待新照片。')
            job = self.store.one("SELECT * FROM jobs WHERE kind='capture' AND status='pending' ORDER BY created_at LIMIT 1")
            automatic = settings['monitor'] and settings['camera_url'] and time.monotonic() >= next_capture
            if job or automatic:
                if job:
                    self.store.execute("UPDATE jobs SET status='running' WHERE id=?", (job['id'],))
                try:
                    event_id = self.capture(job['id'] if job else 'visit:' + str(uuid.uuid4()), 'manual' if job else 'visit')
                    if job:
                        self.store.execute("UPDATE jobs SET status='completed',event_id=? WHERE id=?", (event_id, job['id']))
                except Exception:
                    self.set_camera(status='offline', cat_present=None, error='相机拍照失败，请检查地址、供电与网络。')
                    self.visit = None
                    self.confirm_next = False
                    self.store.notify('camera-offline', '相机连接失败；当前状态未知。')
                    if job:
                        self.store.execute("UPDATE jobs SET status='failed',error='拍照失败，请检查相机连接。' WHERE id=?", (job['id'],))
                next_capture = time.monotonic() + 2
            self.stop_event.wait(.2)

    def analyse_event(self, event):
        identifier = event['id']
        self.store.execute("UPDATE events SET analysis_status='running',error=NULL WHERE id=?", (identifier,))
        try:
            settings = self.store.settings()
            history = []
            if event['cat_id']:
                history = self.store.rows("SELECT captured_at,analysis FROM events WHERE cat_id=? AND captured_at<? AND analysis_status='completed' ORDER BY captured_at DESC LIMIT 5", (event['cat_id'], event['captured_at']))
            result = analyse((self.store.directory / 'media' / event['original']).read_bytes(),
                             json.loads(event['report']), history, settings['ai_model'])
            self.store.execute("UPDATE events SET analysis=?,analysis_status='completed',error=NULL WHERE id=?", (json.dumps(result, ensure_ascii=False), identifier))
            self.store.notify('analysis:' + identifier + ':' + str(time.time()), '照片分析完成：' + result['level'], identifier)
        except Exception as error:
            message = str(error) if isinstance(error, ValueError) else 'AI 分析失败，照片已保留，请重试。'
            self.store.execute("UPDATE events SET analysis_status='failed',error=? WHERE id=?", (message, identifier))
            self.store.notify('analysis-failed:' + identifier, '照片分析失败，可以重试。', identifier)

    def analysis_loop(self):
        while not self.stop_event.is_set():
            if self.store.settings()['cloud_analysis']:
                event = self.store.one("SELECT * FROM events WHERE analysis_status='pending' ORDER BY captured_at LIMIT 1")
                if event:
                    self.analyse_event(event)
            self.stop_event.wait(.5)

    def motor_loop(self):
        while not self.stop_event.is_set():
            try:
                self.motor.tick()
            except Exception:
                LOG.exception('Motor status worker failed')
                with self.motor.lock:
                    self.motor.disconnect()
                    self.motor.serial_error = '状态读取异常；真实 motor 状态未知。'
            self.stop_event.wait(.1)
