import json
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from nadhir.web import dispatch  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        code, body = dispatch("/api/approve", raw)
        data = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(data)
