"""Dependency-light local server. Run with `npm run dev`."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from calculator import CalculatorError, calculate


ROOT = Path(__file__).resolve().parent
CONTENT_TYPES = {'.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript', '.mjs': 'text/javascript', '.woff2': 'font/woff2', '.woff': 'font/woff'}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split('?', 1)[0]
        if path == '/':
            path = '/index.html'
        file = (ROOT / path.lstrip('/')).resolve()
        if not file.is_relative_to(ROOT) or not file.is_file() or (not path.startswith('/vendor/katex/') and path not in {'/index.html', '/app.js', '/styles.css'}):
            self.send_error(404)
            return
        body = file.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', CONTENT_TYPES.get(file.suffix, 'application/octet-stream'))
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != '/api/calculate':
            self.send_error(404)
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length < 1 or length > 100_000:
                raise CalculatorError('ข้อมูลยาวเกินไป')
            payload = json.loads(self.rfile.read(length))
            result = calculate(payload.get('formula'), payload.get('variables'), payload.get('angleUnit', 'DEG'), payload.get('symbolValues'))
            status = 200
        except (CalculatorError, ValueError, TypeError, KeyError) as error:
            result = {'error': str(error)}
            status = 400
        except Exception:
            result = {'error': 'คำนวณสูตรนี้ไม่ได้'}
            status = 400
        body = json.dumps(result, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == '__main__':
    print('Open http://localhost:3000', flush=True)
    ThreadingHTTPServer(('localhost', 3000), Handler).serve_forever()
