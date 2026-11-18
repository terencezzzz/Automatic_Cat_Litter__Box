"""Frontend-only PawLog preview. Does not import backend, models, AI or serial.

Run: python -m src.webapp.preview
"""
import argparse
import json
import re
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
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
    return records


class PreviewHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/api/vision-visits':
            data = json.dumps(visit_records()).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
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
        self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' blob: http: https:; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        super().end_headers()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8080)
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), partial(PreviewHandler, directory=str(WEB)))
    print(f'PawLog UI preview: http://127.0.0.1:{args.port}', flush=True)
    print('Local vision records are loaded from outputs/vision. Ctrl+C to stop.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
