"""embed.url: the url path posts to a service and never imports torch."""
import json
import os
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

CHILD = r"""
import sys, json, sqlite3, threading
sys.path.insert(0, %r)
from types import SimpleNamespace
from sim import embed
store = SimpleNamespace(lock=threading.RLock(), conn=sqlite3.connect(':memory:'))
cfg = SimpleNamespace(embed=SimpleNamespace(enabled=True, model='intfloat/multilingual-e5-small',
    batch_size=2, url=sys.argv[1], url_timeout=5))
e = embed.Embeddings(cfg, store)
v = e.query('hello')
print(json.dumps({'ok': v is not None, 'torch': 'torch' in sys.modules,
                  'st': 'sentence_transformers' in sys.modules}))
"""


def make_server(fail=False):
    log = []

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            log.append(body)
            if fail:
                self.send_response(500)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            data = [{"index": i, "embedding": [3.0, 4.0, float(len(t))]} for i, t in enumerate(body["input"])]
            raw = json.dumps({"data": list(reversed(data))}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, log, "http://127.0.0.1:%d/v1/embeddings" % srv.server_address[1]


def make_embed(url, batch=2):
    import sqlite3
    from sim import embed
    store = SimpleNamespace(lock=threading.RLock(), conn=sqlite3.connect(":memory:", check_same_thread=False))
    cfg = SimpleNamespace(embed=SimpleNamespace(enabled=True, model="intfloat/multilingual-e5-small",
                                                batch_size=batch, url=url, url_timeout=2))
    return embed.Embeddings(cfg, store)


class RemoteEmbed(unittest.TestCase):
    def setUp(self):
        self.srv, self.log, self.url = make_server()
        self.addCleanup(self.srv.shutdown)

    def test_no_torch_in_fresh_process(self):
        r = subprocess.run([sys.executable, "-c", CHILD % ROOT, self.url], capture_output=True,
                           text=True, timeout=60, creationflags=0x08000000 if os.name == "nt" else 0)
        d = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertTrue(d["ok"])
        self.assertFalse(d["torch"])
        self.assertFalse(d["st"])

    def test_query_kind_normalised_and_truncated(self):
        e = make_embed(self.url)
        v = e.query("x" * 5000)
        self.assertAlmostEqual(float((v ** 2).sum()), 1.0, places=5)
        self.assertAlmostEqual(float(v[0]), 3.0 / (9 + 16 + 2000 ** 2) ** 0.5, places=6)
        self.assertEqual(self.log[-1]["input_type"], "query")
        self.assertEqual(len(self.log[-1]["input"][0]), 2000)

    def test_passage_kind_and_order_and_batches(self):
        e = make_embed(self.url, batch=2)
        e.available()
        self.log.clear()
        out = e._encode(["a", "bb", "ccc", "dddd", "eeeee"], "passage: ")
        self.assertEqual(out.shape, (5, 3))
        self.assertEqual([len(b["input"]) for b in self.log], [2, 2, 1])
        self.assertTrue(all(b["input_type"] == "passage" for b in self.log))
        # index order restored although the stub reverses it
        self.assertLess(out[0][2], out[4][2])

    def test_unreachable_marks_unavailable(self):
        self.srv.shutdown()
        self.srv.server_close()
        e = make_embed(self.url)
        self.assertFalse(e.available())
        self.assertTrue(e._failed)
        self.assertIsNone(e.query("hi"))

    def test_server_error_midway_never_raises(self):
        srv, log, url = make_server(fail=True)
        self.addCleanup(srv.shutdown)
        e = make_embed(url)
        self.assertIsNone(e.query("hi"))
        self.assertTrue(e._failed)
        self.assertEqual(len(log), 2)  # ping: one try plus one retry

    def test_failure_after_load(self):
        e = make_embed(self.url)
        self.assertIsNotNone(e.query("hi"))
        self.srv.shutdown()
        self.srv.server_close()
        self.assertIsNone(e._encode(["x"], "passage: "))
        self.assertTrue(e._failed)
        self.assertFalse(e.available())


if __name__ == "__main__":
    unittest.main()
