"""Local PawLog dashboard with optional camera and USB monitoring.

Run: python -m src.webapp.preview
"""
import argparse
import json
import re
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Event, Thread
from urllib.parse import urlsplit

WEB = Path(__file__).resolve().parent
VISITS = WEB.parents[1] / 'outputs' / 'vision'
VISIT_ID = re.compile(r'auto-\d{8}-\d{6}-\d{6}')
IMAGES = ('cat.jpg', 'waste-original.png', 'detection.jpg')


def visit_records():
    records = []
    for folder in sorted(VISITS.glob('auto-*'), reverse=True):
        if not VISIT_ID.fullmatch(folder.name) or folder.is_symlink():
            continue
        try:
            report = json.loads((folder / 'result.json').read_text(encoding='utf-8'))
            captured_at = report['waste_photo_at']
            detected = report['waste_detected']
            if not isinstance(captured_at, str) or not isinstance(detected, bool):
                continue
            if not all((folder / name).is_file() for name in IMAGES):
                continue
        except (OSError, ValueError, KeyError, TypeError):
            continue
        records.append({'id': folder.name, 'capturedAt': captured_at, 'wasteDetected': detected})
        try:
            observation = json.loads((folder / '.pawlog-health-observation.json').read_text(encoding='utf-8'))
            if isinstance(observation, dict):
                records[-1]['observation'] = observation
        except (OSError, ValueError):
            pass
    return records


class PreviewHandler(SimpleHTTPRequestHandler):
    def send_json(self, payload, status=200):
        data = json.dumps(payload).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        host = f'127.0.0.1:{self.server.server_port}'
        if self.headers.get('Host') != host or self.headers.get('Origin') != f'http://{host}':
            self.send_json({'error': 'Open PawLog at its local 127.0.0.1 address.'}, 403)
            return
        cleaning = self.server.cleaning
        if not cleaning or self.path not in ('/api/local/run', '/api/local/stop'):
            self.send_json({'error': 'USB controls are unavailable.'}, 404)
        elif self.path == '/api/local/stop':
            cleaning.stop()
            self.send_json({'message': 'Stop requested'})
        elif cleaning.run_once():
            self.send_json({'message': 'Start requested'})
        else:
            self.send_json({'error': 'Start blocked. Check the camera, occupancy sensor and tray position.'}, 409)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/api/local/device':
            cleaning = self.server.cleaning
            self.send_json(cleaning.snapshot() if cleaning else {})
            return
        if path == '/api/vision-visits':
            self.send_json(visit_records())
            return
        if path.startswith('/visit-image/'):
            parts = path.split('/')
            if len(parts) == 4 and VISIT_ID.fullmatch(parts[2]) and parts[3] in IMAGES:
                image = VISITS / parts[2] / parts[3]
                if image.is_file() and image.resolve() == image:
                    data = image.read_bytes()
                    self.send_response(200)
                    self.send_header('Content-Type', self.guess_type(str(image)))
                    self.send_header('Content-Length', str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
            self.send_error(404)
            return
        if path in ('/', '/index.html'):
            self.path = '/templates/index.html'
        elif not path.startswith('/static/'):
            self.send_error(404)
            return
        resolved = Path(self.translate_path(self.path)).resolve()
        allowed = (WEB / 'templates' / 'index.html',)
        if resolved not in allowed and not resolved.is_relative_to(WEB / 'static'):
            self.send_error(404)
            return
        super().do_GET()

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' blob: data: http: https:; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        super().end_headers()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--camera', help='ESP32-CAM LAN address')
    ports = parser.add_mutually_exclusive_group()
    ports.add_argument('--arduino', help='USB port for PawLogController, e.g. COM3')
    ports.add_argument('--motor-test', metavar='COM_PORT', help='Start one timed MotorTest cycle after each camera-confirmed visit')
    parser.add_argument('--empty-range', nargs=2, type=int, metavar=('MIN_CM', 'MAX_CM'))
    parser.add_argument('--auto-clean', action='store_true')
    parser.add_argument('--sync', action=argparse.BooleanOptionalAction, default=None,
                        help='Sync completed visits to hosted PawLog when monitoring (enabled by default)')
    args = parser.parse_args()
    if args.arduino and (not args.camera or not args.empty_range):
        parser.error('--arduino requires --camera and a measured --empty-range')
    if args.motor_test and (not args.camera or args.auto_clean):
        parser.error('--motor-test requires --camera and enables its own automatic mode')
    if args.empty_range and (not args.arduino or not 2 <= args.empty_range[0] < args.empty_range[1] <= 400):
        parser.error('--empty-range requires --arduino and increasing bounds from 2 to 400 cm')
    if args.auto_clean and not args.arduino:
        parser.error('--auto-clean requires --arduino')
    if args.sync and not args.camera:
        parser.error('--sync requires --camera')

    server = ThreadingHTTPServer(('127.0.0.1', args.port), partial(PreviewHandler, directory=str(WEB)))
    server.cleaning = None
    workers = []
    done = Event()
    link = None
    motor = None
    if args.camera:
        from .vision import camera_address, fetch_photo
        import sys

        sys.path.insert(0, str(WEB.parent / 'vision'))
        from monitor_camera import cv2, monitor
        import numpy as np

        source = camera_address(args.camera)

        def fetch(source):
            return cv2.imdecode(np.frombuffer(fetch_photo(source), dtype=np.uint8), cv2.IMREAD_COLOR)

        if args.arduino:
            from cleaning import Cleaning

            server.cleaning = Cleaning(args.arduino, args.empty_range)
            workers.append(Thread(target=server.cleaning.loop, daemon=True))
        def monitor_camera():
            options = dict(cleaning=server.cleaning, automatic=args.auto_clean,
                           stop=done, sync=args.sync is not False, fetch=fetch)
            try:
                monitor(source, timed_motor=motor, **options)
            finally:
                if motor:
                    motor.stop()

        workers.append(Thread(target=monitor_camera, daemon=True))
    started_workers = []
    try:
        if args.motor_test:
            import serial
            from timed_motor import TimedMotor

            try:
                link = serial.Serial(args.motor_test, 9600, timeout=.25, write_timeout=.2)
                motor = TimedMotor(link)
                motor.verify()
            except (OSError, RuntimeError) as error:
                parser.exit(1, f'MotorTest ({args.motor_test}): {error}\n')
            print(f'MotorTest verified on {args.motor_test}.', flush=True)
        print(f'PawLog UI preview: http://127.0.0.1:{args.port}', flush=True)
        print('Local vision records are loaded from outputs/vision. Ctrl+C to stop.', flush=True)
        for worker in workers:
            worker.start()
            started_workers.append(worker)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        done.set()
        if server.cleaning:
            server.cleaning.closed.set()
        for worker in started_workers:
            worker.join(timeout=2)
        if link is not None:
            link.close()
        server.server_close()


if __name__ == '__main__':
    main()
