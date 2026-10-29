"""Stdlib HTTP server for the Momoka view.

Serves the view, her koikano sprites and faces, the generated audio, and
`state.json`; and takes his next line at POST /say. No framework, no build.
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

try:
    from runtime import app as app_mod
    from runtime import common
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from runtime import app as app_mod
    from runtime import common

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
    ".txt": "text/plain; charset=utf-8",
}


class Handler(BaseHTTPRequestHandler):
    cfg = None
    app = None
    view_dir = None
    char_dir = None
    audio_dir = None

    def log_message(self, fmt, *args):
        sys.stderr.write("  %s\n" % (fmt % args))

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path, ctype=None):
        if not path or not os.path.isfile(path):
            self._send(404, {"error": "not found", "path": path})
            return
        ctype = ctype or CONTENT_TYPES.get(os.path.splitext(path)[1].lower(),
                                           "application/octet-stream")
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        route = unquote(urlparse(self.path).path)
        if route in ("/", "/index.html"):
            return self._send_file(os.path.join(self.view_dir, "index.html"))
        if route == "/state.json":
            state = self.app.current_state() if self.app else None
            return self._send(200, state or {"turn": 0, "text": None})
        if route.startswith("/view/"):
            name = os.path.basename(route[len("/view/"):])
            return self._send_file(os.path.join(self.view_dir, name))
        if route.startswith("/asset/sprite/"):
            name = os.path.basename(route[len("/asset/sprite/"):])
            return self._send_file(os.path.join(self.char_dir, self.cfg["assets"]["sprite_dir"], name))
        if route.startswith("/asset/face/"):
            name = os.path.basename(route[len("/asset/face/"):])
            return self._send_file(os.path.join(self.char_dir, self.cfg["assets"]["face_dir"], name))
        if route.startswith("/asset/clip/"):
            name = os.path.basename(route[len("/asset/clip/"):])
            return self._send_file(os.path.join(self.char_dir, self.cfg["assets"]["voice_dir"], name))
        if route.startswith("/audio/"):
            name = os.path.basename(route[len("/audio/"):])
            return self._send_file(os.path.join(self.audio_dir, name))
        return self._send(404, {"error": "not found", "route": route})

    def do_POST(self):
        route = unquote(urlparse(self.path).path)
        if route != "/say":
            return self._send(404, {"error": "not found", "route": route})
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode("utf-8", "replace") if length else ""
        try:
            payload = json.loads(raw) if raw.strip() else {}
        except ValueError:
            return self._send(400, {"error": "body is not JSON"})
        text = (payload.get("text") or "").strip()
        if not text:
            return self._send(400, {"error": "no text"})
        try:
            state = self.app.turn(text, clip=payload.get("clip"))
        except Exception as e:
            return self._send(502, {"error": f"{type(e).__name__}: {e}"})
        return self._send(200, state)


def build():
    cfg = common.load_config()
    Handler.cfg = cfg
    Handler.app = app_mod.App(cfg)
    Handler.view_dir = common.root_path("view")
    Handler.char_dir = common.resolve(cfg["assets"]["character_dir"])
    # rendered lines live in the voice cache; /audio/ serves exactly that dir
    Handler.audio_dir = common.resolve(cfg["paths"]["cache_dir"])
    return cfg


def main():
    cfg = build()
    host, port = cfg["server"]["host"], int(cfg["server"]["port"])
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"Momoka view: http://{host}:{port}/  (state at /state.json, POST /say)")
    print("Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
