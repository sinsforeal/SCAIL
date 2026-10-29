"""One shared embedding service for every SCAIL mind (127.0.0.1 only).

POST /v1/embeddings {"model", "input": str|[str], "input_type": "query"|"passage"}
  -> {"data": [{"index", "embedding"}]}  (same shape and same vectors as the
  bzombie gateway: e5 prefix from input_type, normalised, batch 32).
GET /status -> device, model, calls. The model loads once, on the first call.

Start hidden (one line, from the repo root):
  C:\\Python314\\pythonw.exe tools\\embed_server.py 18320   (pythonw has no window)
or from Python: subprocess.Popen([pythonw, "tools/embed_server.py", "18320"], creationflags=0x08000000)

Then set embed.url to http://127.0.0.1:18320/v1/embeddings in the mind's config.
"""
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODEL = "intfloat/multilingual-e5-small"
_lock = threading.Lock()
_state = {"model": None, "device": None, "calls": 0}


def _encode(texts, prefix):
    with _lock:
        if _state["model"] is None:
            import torch
            from sentence_transformers import SentenceTransformer
            dev = "cuda" if torch.cuda.is_available() else "cpu"
            _state["model"] = SentenceTransformer(MODEL, device=dev)
            _state["device"] = dev
        vecs = _state["model"].encode([prefix + t for t in texts], normalize_embeddings=True,
                                      batch_size=32, show_progress_bar=False)
        _state["calls"] += 1
    return [[float(x) for x in v] for v in vecs]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        raw = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path.rstrip("/") == "/status":
            return self._send(200, {"model": MODEL, "device": _state["device"],
                                    "loaded": _state["model"] is not None, "calls": _state["calls"]})
        self._send(404, {"error": "not_found"})

    def do_POST(self):
        if not self.path.rstrip("/").endswith("/embeddings"):
            return self._send(404, {"error": "not_found"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n).decode("utf-8"))
            inp = body.get("input")
            texts = [inp] if isinstance(inp, str) else inp
            if not isinstance(texts, list) or not texts or not all(isinstance(t, str) for t in texts):
                return self._send(400, {"error": "input must be a string or list of strings"})
            prefix = "query: " if body.get("input_type") == "query" else "passage: "
            vecs = _encode(texts, prefix)
        except Exception as e:
            return self._send(500, {"error": "embedding failed: " + type(e).__name__})
        self._send(200, {"object": "list", "model": body.get("model") or "multilingual-e5-small",
                         "data": [{"object": "embedding", "index": i, "embedding": v}
                                  for i, v in enumerate(vecs)],
                         "usage": {"prompt_tokens": 0, "total_tokens": 0}})


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 18320
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
