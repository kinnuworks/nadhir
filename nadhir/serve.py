"""Local server: python -m nadhir.serve  (then open http://localhost:8000)"""
from __future__ import annotations

import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .web import dispatch

ROOT = Path(__file__).resolve().parent.parent


class Handler(SimpleHTTPRequestHandler):
    """Serves only the web/ folder (paths /web/...), the same layout as the hosted site."""
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT), **kw)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.path = "/web/index.html"
        if not self.path.startswith("/web/") or ".." in self.path:
            self.send_error(404)
            return
        super().do_GET()

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        code, body = dispatch(self.path, raw)
        data = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"http://localhost:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
