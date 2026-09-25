"""Vercel function for the calculator API."""

import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from calculator import CalculatorError, calculate


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length < 1 or length > 100_000:
                raise CalculatorError('ข้อมูลยาวเกินไป')
            payload = json.loads(self.rfile.read(length))
            result = calculate(
                payload.get('formula'),
                payload.get('variables'),
                payload.get('angleUnit', 'DEG'),
                payload.get('symbolValues'),
            )
            status = 200
        except (CalculatorError, ValueError, TypeError, KeyError) as error:
            result = {'error': str(error)}
            status = 400
        except Exception:
            result = {'error': 'คำนวณสูตรนี้ไม่ได้'}
            status = 400

        body = json.dumps(result, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
