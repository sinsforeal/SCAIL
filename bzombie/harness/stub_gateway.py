"""Stub gateway status: GET /status with fake spend, for testing `status` without the real gateway.

python -m bzombie.harness.stub_gateway [--port 18330]
"""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ..common import VAR, read_json


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        runs = {}
        d = VAR / "runs"
        for p in (d.iterdir() if d.exists() else []):
            c = read_json(p / "config.json") or {}
            runs[p.name] = {"arm": c.get("arm"), "spend_usd": 0.0, "cap_usd": c.get("cap_usd"), "calls": 0, "errors": 0}
        b = json.dumps({"stub": True, "runs": runs, "balance_usd": 9.37}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=18330)
    a = ap.parse_args()
    ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()
