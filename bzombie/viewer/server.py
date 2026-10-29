"""HTTP server for the viewer. 127.0.0.1 only. Read-only except POST /api/vote."""
import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .data import Store

HOST = "127.0.0.1"
PORT = 18350
STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


def make_handler(store, port):
    ok_hosts = {"127.0.0.1:%d" % port, "localhost:%d" % port}

    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "bzviewer"

        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json; charset=utf-8"):
            if not isinstance(body, bytes):
                body = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _host_ok(self):
            return (self.headers.get("Host") or "") in ok_hosts

        def do_GET(self):
            if not self._host_ok():
                return self._send(403, {"error": "bad host"})
            u = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            try:
                if u.path.startswith("/api/"):
                    return self._api(u.path[5:], q)
                return self._static(u.path)
            except Exception as e:  # a bad file must never kill a page
                return self._send(500, {"error": "%s: %s" % (type(e).__name__, e)})

        def do_POST(self):
            if not self._host_ok():
                return self._send(403, {"error": "bad host"})
            u = urlparse(self.path)
            if u.path != "/api/vote":
                return self._send(404, {"error": "not found"})
            try:
                n = int(self.headers.get("Content-Length") or 0)
                if n > 65536:
                    return self._send(413, {"error": "too large"})
                body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
                rec, err = store.record_vote(body.get("pair_id"), body.get("choice"), body.get("note"))
                if err:
                    return self._send(400, {"error": err})
                return self._send(200, {"ok": True, "vote": rec})
            except (ValueError, UnicodeDecodeError):
                return self._send(400, {"error": "bad json"})
            except Exception as e:
                return self._send(500, {"error": "%s: %s" % (type(e).__name__, e)})

        def _static(self, path):
            name = "index.html" if path in ("/", "") or not os.path.splitext(path)[1] else path.lstrip("/")
            p = os.path.normpath(os.path.join(STATIC, name))
            if not p.startswith(STATIC) or not os.path.isfile(p):
                return self._send(404, {"error": "not found"})
            with open(p, "rb") as f:
                data = f.read()
            ct = mimetypes.guess_type(p)[0] or "application/octet-stream"
            if ct.startswith("text/") or ct.endswith("javascript"):
                ct += "; charset=utf-8"
            return self._send(200, data, ct)

        def _api(self, ep, q):
            s = store
            ref = q.get("run", "")
            if ep == "runs":
                return self._send(200, {"runs": s.runs(), "root": s.root})
            if ep == "options":
                return self._send(200, s.options(q.get("dev") == "1"))
            if ep == "run":
                r = s.run_row(ref)
                return self._send(200 if r else 404, r or {"error": "no such run"})
            if ep == "transcript":
                cfg = s.config(ref)
                if cfg is None:
                    return self._send(404, {"error": "no such run"})
                tr = s.transcript(ref)
                return self._send(200, {"run": s.run_row(ref), "lines": tr})
            if ep == "trace":
                t = s.trace(ref, q.get("output", ""))
                if t is None:
                    return self._send(404, {"error": "no trace for that output"})
                calls = {c.get("call_id"): c for c in s.calls(ref)}
                t["call_meta"] = {cid: calls[cid] for cid in
                                  [x if isinstance(x, str) else (x or {}).get("call_id") for x in (t.get("calls") or [])]
                                  if cid in calls}
                return self._send(200, t)
            if ep == "call":
                c = s.call_detail(ref, q.get("call", ""))
                return self._send(200 if c else 404, c or {"error": "no such call"})
            if ep == "stats":
                st = s.stats(ref)
                return self._send(200 if st else 404, st or {"error": "no such run"})
            if ep == "compare":
                r = s.compare(q.get("a", ""), q.get("b", ""), q.get("env", "1") != "0")
                return self._send(200 if r else 404, r or {"error": "no such run"})
            if ep == "judge":
                if q.get("match"):
                    m = s.match(q["match"])
                    return self._send(200 if m else 404, m or {"error": "no such match"})
                return self._send(200, {"matches": s.matches(), "modelcheck": s.modelcheck(), "calibrations": s.calibrations()})
            if ep == "pairs":
                return self._send(200, {"pairs": s.pairs()})
            if ep == "pair":
                p = s.pair(q.get("id", ""))
                return self._send(200 if p else 404, p or {"error": "no such pair"})
            return self._send(404, {"error": "unknown endpoint"})

    return H


def serve(data, port=PORT):
    store = Store(data)
    srv = ThreadingHTTPServer((HOST, port), make_handler(store, port))
    srv.daemon_threads = True
    return srv
