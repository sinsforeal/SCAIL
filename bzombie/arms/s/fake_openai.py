"""A tiny local OpenAI-compatible server for the S arm tests. Path: /arm/S/<run>/v1/chat/completions
(stream and non-stream) and /embeddings. Every response carries an x-bz-call-id header.
JSON-looking asks get "{}", everything else a short line. Usage: fake_openai.py <port>."""

import json
import sys
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CALLS = []


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        b = json.dumps({"data": [{"id": "bz-model"}]}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        req = json.loads(self.rfile.read(n) or b"{}")
        cid = str(uuid.uuid4())
        CALLS.append(req)
        if self.path.endswith("/embeddings"):
            inp = req.get("input") or []
            inp = [inp] if isinstance(inp, str) else inp
            body = {"object": "list", "data": [{"object": "embedding", "index": i, "embedding": [0.1] * 384}
                                               for i, _ in enumerate(inp)], "model": "bz-model",
                    "usage": {"prompt_tokens": 1, "total_tokens": 1}}
            return self._json(body, cid)
        msgs = req.get("messages") or []
        blob = " ".join(str(m.get("content", "")) for m in msgs)
        jsonish = bool(req.get("response_format")) or "JSON" in blob or "json" in blob
        text = "{}" if jsonish else "うん、いるよ。"
        if req.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("x-bz-call-id", cid)
            self.end_headers()
            chunk = {"id": cid, "object": "chat.completion.chunk", "model": "bz-model",
                     "choices": [{"index": 0, "delta": {"role": "assistant", "content": text}, "finish_reason": None}]}
            fin = {"id": cid, "object": "chat.completion.chunk", "model": "bz-model",
                   "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                   "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}
            for c in (chunk, fin):
                self.wfile.write(("data: " + json.dumps(c) + "\n\n").encode())
            self.wfile.write(b"data: [DONE]\n\n")
            return
        body = {"id": cid, "object": "chat.completion", "model": "bz-model",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}
        self._json(body, cid)

    def _json(self, body, cid):
        b = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("x-bz-call-id", cid)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)


def serve(port):
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    return srv


if __name__ == "__main__":
    serve(int(sys.argv[1])).serve_forever()
