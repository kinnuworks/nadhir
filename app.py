"""Hosted entrypoint (WSGI): serves the page from web/ and the JSON API. No framework needed."""
import json
import mimetypes
from pathlib import Path

from nadhir.web import dispatch

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"


def app(environ, start_response):
    path = environ.get("PATH_INFO", "/")
    method = environ.get("REQUEST_METHOD", "GET")
    if method == "POST" and path.startswith("/api/"):
        size = int(environ.get("CONTENT_LENGTH") or 0)
        code, body = dispatch(path, environ["wsgi.input"].read(size) if size else b"")
        data = json.dumps(body, ensure_ascii=False).encode()
        start_response(f"{code} {'OK' if code == 200 else 'Error'}",
                       [("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(data)))])
        return [data]
    if path in ("/", "/index.html"):
        path = "/web/index.html"
    target = (ROOT / path.lstrip("/")).resolve()
    if method == "GET" and path.startswith("/web/") and WEB in target.parents and target.is_file():
        data = target.read_bytes()
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        start_response("200 OK", [("Content-Type", ctype), ("Content-Length", str(len(data)))])
        return [data]
    start_response("404 Not Found", [("Content-Type", "text/plain")])
    return [b"not found"]
