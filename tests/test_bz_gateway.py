"""Gateway tests against a local fake upstream. Run: python -m unittest tests.test_bz_gateway -v"""
import http.client
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bzombie", "gateway"))
import policy  # noqa: E402
import server  # noqa: E402


class FakeUp:
    """Fake Surplus. Records requests; `fail429` = number of 429s to answer first."""

    def __init__(self):
        self.reqs = []
        self.fail429 = 0
        self.stall = 0  # number of requests to stall (no response bytes) before answering normally
        self.release = threading.Event()
        self.cost = 40
        self.content = "hello"
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                raw = json.dumps({"credit_balance_usdc": "9000000"}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_POST(self):
                n = int(self.headers["Content-Length"])
                body = json.loads(self.rfile.read(n))
                outer.reqs.append(body)
                if outer.stall > 0:
                    # stalled request: no byte until released (or 8 s), then drop the connection
                    outer.stall -= 1
                    outer.release.wait(8)
                    return
                if outer.fail429 > 0:
                    outer.fail429 -= 1
                    self.send_response(429)
                    self.send_header("Retry-After", "0")
                    self.send_header("Content-Length", "2")
                    self.end_headers()
                    self.wfile.write(b"{}")
                    return
                usage = {"prompt_tokens": 5, "completion_tokens": 3, "buyer_cost_micro": outer.cost}
                if body.get("stream"):
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.end_headers()
                    chunks = [
                        {"id": "c1", "choices": [{"index": 0, "delta": {"content": outer.content[:2]}}]},
                        {"id": "c1", "choices": [{"index": 0, "delta": {"content": outer.content[2:]}, "finish_reason": "stop"}]},
                        {"id": "c1", "choices": [], "usage": usage},
                    ]
                    for c in chunks:
                        self.wfile.write(("data: " + json.dumps(c) + "\n\n").encode())
                    self.wfile.write(b"data: [DONE]\n\n")
                    return
                raw = json.dumps({"id": "c1", "choices": [{"index": 0, "message": {
                    "role": "assistant", "content": outer.content, "reasoning_content": "hmm"}}],
                    "usage": usage}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()


class FakeEmbedder:
    name = "fake-e5"
    device = "cpu"

    def encode(self, texts, prefix="passage: "):
        return [[0.0] * 383 + [float(len(t))] for t in texts]


class GatewayCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(dir=os.environ.get("TEMP"))
        cls.up = FakeUp()
        key = os.path.join(cls.tmp, "key.txt")
        with open(key, "w") as f:
            f.write("test-key-not-real")
        cls.gw = server.Gateway(cls.tmp, key, "http://127.0.0.1:%d/v1" % cls.up.port, FakeEmbedder(), backoff=0.01)
        cls.srv = server.make_server(cls.gw, "127.0.0.1", 0)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.up.srv.shutdown()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        self.up.reqs.clear()
        self.up.fail429 = 0
        self.up.cost = 40
        self.up.content = "hello"

    def mkrun(self, run_id, model, lang="en", cap=1.0):
        d = os.path.join(self.tmp, "runs", run_id)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "config.json"), "w") as f:
            json.dump({"model": model, "lang": lang, "cap_usd": cap}, f)
        with open(os.path.join(d, "clock.json"), "w") as f:
            json.dump({"virtual_ts": "2026-10-23T08:00:00+09:00"}, f)

    def post(self, path, body, headers=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        h = {"Content-Type": "application/json"}
        h.update(headers or {})
        c.request("POST", path, json.dumps(body), h)
        r = c.getresponse()
        raw = r.read()
        return r.status, dict(r.getheaders()), raw

    def calls(self, run_id):
        with open(os.path.join(self.tmp, "runs", run_id, "calls.jsonl"), encoding="utf-8") as f:
            return [json.loads(x) for x in f]

    BASE = {"model": "gpt-4", "messages": [{"role": "system", "content": "SYS"}, {"role": "user", "content": "hi"}]}

    def test_deepseek_policy(self):
        self.mkrun("r_ds", policy.DEEPSEEK)
        body = dict(self.BASE, thinking={"type": "enabled"}, frequency_penalty=0.5, presence_penalty=0.5,
                    temperature=0.7)
        st, hd, raw = self.post("/arm/S/r_ds/v1/chat/completions", body)
        self.assertEqual(st, 200)
        sent = self.up.reqs[-1]
        self.assertEqual(sent["model"], policy.DEEPSEEK)
        self.assertEqual(sent["reasoning_effort"], "none")
        for k in ("thinking", "frequency_penalty", "presence_penalty", "chat_template_kwargs"):
            self.assertNotIn(k, sent)
        self.assertEqual(sent["temperature"], 0.7)

    def test_glm_policy_no_tools(self):
        self.mkrun("r_glm", policy.GLM)
        self.post("/arm/P/r_glm/v1/chat/completions", dict(self.BASE, reasoning_effort="none"))
        sent = self.up.reqs[-1]
        self.assertEqual(sent["model"], policy.GLM)
        self.assertEqual(sent["reasoning_effort"], "low")
        self.assertEqual(sent["chat_template_kwargs"], {"clear_thinking": True})

    def test_glm_policy_tools_keeps_thinking(self):
        self.mkrun("r_glm2", policy.GLM)
        body = dict(self.BASE, tools=[{"type": "function", "function": {"name": "f", "parameters": {}}}],
                    chat_template_kwargs={"clear_thinking": True})
        self.post("/arm/S/r_glm2/v1/chat/completions", body)
        sent = self.up.reqs[-1]
        self.assertEqual(sent["reasoning_effort"], "low")
        self.assertNotIn("chat_template_kwargs", sent)

    def test_max_tokens_floor(self):
        self.mkrun("r_mt", policy.DEEPSEEK)
        self.post("/arm/S/r_mt/v1/chat/completions", dict(self.BASE, max_tokens=200))
        self.assertEqual(self.up.reqs[-1]["max_tokens"], 1024)
        self.post("/arm/S/r_mt/v1/chat/completions", dict(self.BASE, max_tokens=2000))
        self.assertEqual(self.up.reqs[-1]["max_tokens"], 2000)
        self.post("/arm/S/r_mt/v1/chat/completions", self.BASE)
        self.assertNotIn("max_tokens", self.up.reqs[-1])

    def test_language_pin(self):
        for lang in ("ja", "en"):
            rid = "r_pin_" + lang
            self.mkrun(rid, policy.DEEPSEEK, lang)
            body = {"model": "x", "messages": [{"role": "system", "content": "SYS"},
                                               {"role": "user", "content": "one"},
                                               {"role": "assistant", "content": "two"},
                                               {"role": "user", "content": "three"}]}
            self.post("/arm/S/%s/v1/chat/completions" % rid, body)
            m = self.up.reqs[-1]["messages"]
            pin = policy.PINS[lang]
            self.assertTrue(m[0]["content"].startswith(pin) and m[0]["content"].endswith("SYS"))
            self.assertTrue(m[3]["content"].endswith(pin) and m[3]["content"].startswith("three"))
            self.assertEqual(m[1]["content"], "one")
            self.assertEqual(m[2]["content"], "two")
        self.assertEqual(policy.PINS["ja"], "キャラクターとしての文章はすべて自然な日本語で書く。")

    def test_pin_without_system_message(self):
        out = policy.apply_pin([{"role": "user", "content": "hi"}], "en")
        self.assertEqual(out[0]["role"], "system")
        self.assertEqual(len(out), 2)

    def test_nonstream_metering_log_header(self):
        self.mkrun("r_log", policy.DEEPSEEK, "ja")
        st, hd, raw = self.post("/arm/S/r_log/v1/chat/completions", self.BASE)
        self.assertEqual(st, 200)
        lines = self.calls("r_log")
        self.assertEqual(len(lines), 1)
        rec = lines[0]
        for k in ("call_id", "arm", "run_id", "wall_ts", "virtual_ts", "model", "request", "response", "usage",
                  "cost_micro", "latency_s", "error"):
            self.assertIn(k, rec)
        self.assertEqual(rec["cost_micro"], 40)
        self.assertEqual(rec["arm"], "S")
        self.assertEqual(rec["virtual_ts"], "2026-10-23T08:00:00+09:00")
        self.assertEqual(rec["response"]["choices"][0]["message"]["reasoning_content"], "hmm")
        hdr = {k.lower(): v for k, v in hd.items()}
        self.assertEqual(hdr["x-bz-call-id"], rec["call_id"])
        self.assertEqual(self.gw.run("r_log").spent_micro, 40)

    def test_stream_metering(self):
        self.mkrun("r_st", policy.GLM)
        st, hd, raw = self.post("/arm/P/r_st/v1/chat/completions", dict(self.BASE, stream=True))
        self.assertEqual(st, 200)
        text = raw.decode()
        self.assertIn("[DONE]", text)
        self.assertNotIn("buyer_cost_micro", text)  # caller did not ask for usage
        self.assertTrue(self.up.reqs[-1]["stream_options"]["include_usage"])
        rec = self.calls("r_st")[0]
        self.assertEqual(rec["cost_micro"], 40)
        self.assertEqual(rec["response"]["choices"][0]["message"]["content"], "hello")
        hdr = {k.lower(): v for k, v in hd.items()}
        self.assertEqual(hdr["x-bz-call-id"], rec["call_id"])

    PRE = {"model": "gpt-4", "messages": [{"role": "system", "content": "SYS"},
                                          {"role": "user", "content": "story so far"},
                                          {"role": "assistant", "content": 'User says: "hi"\nMomoka says: "'}]}

    def test_fold_prefill_unit(self):
        out, var = policy.fold_prefill(self.PRE["messages"])
        self.assertEqual(var, policy.FOLD_VARIANT)
        self.assertEqual([m["role"] for m in out], ["system", "user"])
        self.assertTrue(out[-1]["content"].startswith("story so far"))
        self.assertIn(policy.FOLD_LINE, out[-1]["content"])
        self.assertTrue(out[-1]["content"].endswith('Momoka says: "'))
        self.assertEqual(len(self.PRE["messages"]), 3)  # input untouched
        # long prefill keeps only the tail
        long_pre = "x" * 1000 + "TAIL"
        out2, _ = policy.fold_prefill([{"role": "user", "content": "u"}, {"role": "assistant", "content": long_pre}])
        self.assertTrue(out2[-1]["content"].endswith("TAIL"))
        self.assertLess(len(out2[-1]["content"]), 600)

    def test_fold_prefill_not_applied(self):
        for msgs in ([{"role": "user", "content": "u"}],
                     [{"role": "user", "content": "u"}, {"role": "assistant", "content": ""}],
                     [{"role": "user", "content": "u"},
                      {"role": "assistant", "content": "x", "tool_calls": [{"id": "1"}]}],
                     [{"role": "assistant", "content": "only"}],
                     [{"role": "system", "content": "s"}, {"role": "assistant", "content": "no user"}]):
            out, var = policy.fold_prefill(msgs)
            self.assertIsNone(var)
            self.assertEqual(out, msgs)

    def test_fold_prefill_via_gateway(self):
        self.mkrun("r_fold", policy.DEEPSEEK, "ja")
        st, hd, raw = self.post("/arm/P/r_fold/v1/chat/completions", self.PRE)
        self.assertEqual(st, 200)
        sent = self.up.reqs[-1]["messages"]
        self.assertEqual([m["role"] for m in sent], ["system", "user"])
        self.assertIn(policy.FOLD_LINE, sent[-1]["content"])
        rec = self.calls("r_fold")[0]
        self.assertEqual(rec["prefill_fold"], policy.FOLD_VARIANT)
        self.assertEqual(len(rec["request"]["messages"]), 3)  # original kept
        self.assertEqual(rec["request"]["messages"][-1]["role"], "assistant")
        self.assertEqual(rec["request_sent"]["messages"][-1]["role"], "user")
        self.assertEqual(json.loads(raw)["choices"][0]["message"]["content"], "hello")  # no echo

    def test_fold_prefill_stream(self):
        self.mkrun("r_fold_st", policy.DEEPSEEK, "en")
        st, hd, raw = self.post("/arm/P/r_fold_st/v1/chat/completions", dict(self.PRE, stream=True))
        self.assertEqual(st, 200)
        self.assertEqual(self.up.reqs[-1]["messages"][-1]["role"], "user")
        rec = self.calls("r_fold_st")[0]
        self.assertEqual(rec["prefill_fold"], policy.FOLD_VARIANT)
        self.assertEqual(rec["request"]["messages"][-1]["role"], "assistant")

    def test_no_fold_when_last_is_user(self):
        self.mkrun("r_nofold", policy.DEEPSEEK, "ja")
        self.post("/arm/S/r_nofold/v1/chat/completions", self.BASE)
        self.assertNotIn("prefill_fold", self.calls("r_nofold")[0])
        self.assertNotIn("template_junk", self.calls("r_nofold")[0])

    def test_junk_detector_unit(self):
        for t in ("a <｜begin▁of▁sentence｜> b", "x<ds_safety>y", "# Valid channels: analysis"):
            self.assertTrue(policy.detect_junk(t), t)
        for t in ("hello", "", None, "Valid channel"):
            self.assertFalse(policy.detect_junk(t), t)

    def test_junk_flag_nonstream_and_stream(self):
        self.up.content = "ok <ds_safety>[x]</ds_safety>Safe"
        self.mkrun("r_junk", policy.DEEPSEEK, "ja")
        st, hd, raw = self.post("/arm/P/r_junk/v1/chat/completions", self.BASE)
        self.assertIn("ds_safety", json.loads(raw)["choices"][0]["message"]["content"])  # not edited
        self.post("/arm/P/r_junk/v1/chat/completions", dict(self.BASE, stream=True))
        recs = self.calls("r_junk")
        self.assertTrue(recs[0]["template_junk"])
        self.assertTrue(recs[1]["template_junk"])
        self.assertIn("ds_safety", recs[1]["response"]["choices"][0]["message"]["content"])

    def test_stream_usage_passed_when_asked(self):
        self.mkrun("r_st2", policy.GLM)
        st, hd, raw = self.post("/arm/P/r_st2/v1/chat/completions",
                                dict(self.BASE, stream=True, stream_options={"include_usage": True}))
        self.assertIn("buyer_cost_micro", raw.decode())

    def test_cap_402(self):
        self.mkrun("r_cap", policy.DEEPSEEK, "en", cap=0.00005)  # 50 micro
        self.up.cost = 60
        st, _, _ = self.post("/arm/S/r_cap/v1/chat/completions", self.BASE)
        self.assertEqual(st, 200)
        n = len(self.up.reqs)
        st, hd, raw = self.post("/arm/S/r_cap/v1/chat/completions", self.BASE)
        self.assertEqual(st, 402)
        self.assertEqual(json.loads(raw)["error"]["type"], "budget_exhausted")
        self.assertEqual(len(self.up.reqs), n)  # nothing went upstream
        self.assertEqual(self.calls("r_cap")[-1]["error"], "budget_exhausted")

    def test_retry_429(self):
        self.mkrun("r_429", policy.DEEPSEEK)
        self.up.fail429 = 2
        st, _, _ = self.post("/arm/S/r_429/v1/chat/completions", self.BASE)
        self.assertEqual(st, 200)
        self.assertEqual(len(self.up.reqs), 3)
        self.assertEqual(self.calls("r_429")[0]["retries"], 2)
        self.assertEqual(self.calls("r_429")[0]["cost_micro"], 40)

    def test_retry_gives_up_after_5(self):
        self.mkrun("r_429b", policy.DEEPSEEK)
        self.up.fail429 = 99
        st, _, _ = self.post("/arm/S/r_429b/v1/chat/completions", self.BASE)
        self.assertEqual(st, 429)
        self.assertEqual(len(self.up.reqs), 6)
        self.assertEqual(self.calls("r_429b")[0]["cost_micro"], 0)

    def test_arm_x_overrides(self):
        self.mkrun("r_x", policy.DEEPSEEK, "en")
        self.post("/arm/X/r_x/v1/chat/completions", self.BASE, {"x-bz-model": policy.GLM, "x-bz-lang": "ja"})
        sent = self.up.reqs[-1]
        self.assertEqual(sent["model"], policy.GLM)
        self.assertTrue(sent["messages"][0]["content"].startswith(policy.PINS["ja"]))
        # S cannot override
        self.post("/arm/S/r_x/v1/chat/completions", self.BASE, {"x-bz-model": policy.GLM})
        self.assertEqual(self.up.reqs[-1]["model"], policy.DEEPSEEK)

    def test_embeddings_local(self):
        self.mkrun("r_em", policy.DEEPSEEK)
        n = len(self.up.reqs)
        st, hd, raw = self.post("/arm/S/r_em/v1/embeddings", {"model": "x", "input": ["abc", "de"]})
        self.assertEqual(st, 200)
        d = json.loads(raw)
        self.assertEqual(len(d["data"]), 2)
        self.assertEqual(len(d["data"][0]["embedding"]), 384)
        self.assertEqual(len(self.up.reqs), n)
        self.assertEqual(self.calls("r_em")[-1]["endpoint"], "embeddings")

    def test_models_and_status(self):
        self.mkrun("r_ms", policy.GLM)
        c = http.client.HTTPConnection("127.0.0.1", self.port)
        c.request("GET", "/arm/S/r_ms/v1/models")
        self.assertEqual(json.loads(c.getresponse().read())["data"][0]["id"], policy.GLM)
        self.post("/arm/S/r_ms/v1/chat/completions", self.BASE)
        c = http.client.HTTPConnection("127.0.0.1", self.port)
        c.request("GET", "/status")
        s = json.loads(c.getresponse().read())
        self.assertEqual(s["runs"]["r_ms"]["spent_micro"], 40)
        self.assertEqual(s["runs"]["r_ms"]["cap_usd"], 1.0)
        self.assertEqual(s["balance"]["credit_balance_usdc"], "9000000")

    def test_unknown_run_404(self):
        st, _, _ = self.post("/arm/S/nope/v1/chat/completions", self.BASE)
        self.assertEqual(st, 404)

    # ---- hedge: first upstream try stalls (no byte), the second answers at once
    def hedge_run(self, run_id, hedge_after, stall, stream):
        import time
        self.mkrun(run_id, policy.DEEPSEEK)
        old = self.gw.hedge_after_s
        self.gw.hedge_after_s = hedge_after
        self.up.release.clear()
        self.up.stall = stall
        try:
            t0 = time.time()
            st, hd, raw = self.post("/arm/P/%s/v1/chat/completions" % run_id, dict(self.BASE, stream=stream))
            return st, raw, time.time() - t0
        finally:
            self.gw.hedge_after_s = old
            self.up.release.set()

    def test_hedge_nonstream(self):
        st, raw, dt = self.hedge_run("r_h_ns", 0.3, 1, False)
        self.assertEqual(st, 200)
        self.assertEqual(json.loads(raw)["choices"][0]["message"]["content"], "hello")
        self.assertLess(dt, 4)
        self.assertEqual(len(self.up.reqs), 2)
        rec = self.calls("r_h_ns")[0]
        self.assertTrue(rec["hedged"])
        self.assertEqual(rec["hedge_won"], "second")
        self.assertEqual(rec["cost_micro"], 40)
        self.assertEqual(rec["retries"], 0)
        self.assertEqual(len(self.calls("r_h_ns")), 1)

    def test_hedge_stream(self):
        st, raw, dt = self.hedge_run("r_h_st", 0.3, 1, True)
        self.assertEqual(st, 200)
        text = raw.decode()
        self.assertEqual(text.count("[DONE]"), 1)
        self.assertEqual(text.count('"c1"'), 2)  # one winner's chunks only
        self.assertLess(dt, 4)
        self.assertEqual(len(self.up.reqs), 2)
        rec = self.calls("r_h_st")[0]
        self.assertTrue(rec["hedged"])
        self.assertEqual(rec["hedge_won"], "second")
        self.assertEqual(rec["cost_micro"], 40)
        self.assertEqual(rec["response"]["choices"][0]["message"]["content"], "hello")

    def test_no_hedge_when_fast(self):
        for stream in (False, True):
            rid = "r_h_fast%d" % stream
            st, raw, dt = self.hedge_run(rid, 5, 0, stream)
            self.assertEqual(st, 200)
            self.assertEqual(len(self.up.reqs), 1)
            self.up.reqs.clear()
            rec = self.calls(rid)[0]
            self.assertFalse(rec["hedged"])
            self.assertNotIn("hedge_won", rec)

    def test_hedge_disabled(self):
        # first try stalls; with hedge off the gateway just waits for the stalled try (released after 1 s)
        import time
        self.mkrun("r_h_off", policy.DEEPSEEK)
        old = self.gw.hedge_after_s
        self.gw.hedge_after_s = 0
        self.up.release.clear()
        self.up.stall = 1
        threading.Timer(1.0, self.up.release.set).start()
        try:
            t0 = time.time()
            st, _, _ = self.post("/arm/P/r_h_off/v1/chat/completions", self.BASE)
            dt = time.time() - t0
        finally:
            self.gw.hedge_after_s = old
            self.up.release.set()
        self.assertEqual(st, 200)  # stalled try was dropped, the retry loop answered
        self.assertGreaterEqual(dt, 0.9)
        rec = self.calls("r_h_off")[0]
        self.assertFalse(rec["hedged"])
        self.assertEqual(rec["retries"], 1)

    def test_hedge_env_default(self):
        self.assertEqual(server.HEDGE_AFTER_S, 60.0)
        os.environ["BZ_HEDGE_AFTER_S"] = "0"
        try:
            g = server.Gateway(self.tmp, "k", "http://127.0.0.1:1/v1", FakeEmbedder())
            self.assertEqual(g.hedge_after_s, 0)
        finally:
            del os.environ["BZ_HEDGE_AFTER_S"]

    def test_bind_refuses_non_loopback(self):
        with self.assertRaises(ValueError):
            server.make_server(self.gw, "0.0.0.0", 0)


if __name__ == "__main__":
    unittest.main()
