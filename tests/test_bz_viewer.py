"""Viewer tests: python -m unittest tests.test_bz_viewer -v"""
import json
import os
import shutil
import sys
import tempfile
import unittest
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from bzombie.viewer import data as D  # noqa: E402
from bzombie.viewer.__main__ import main as cli  # noqa: E402

FIX = os.path.join(ROOT, "bzombie", "viewer", "fixtures", "var")
TMPROOT = os.environ.get("TEMP") if (os.environ.get("TEMP") or "").upper().startswith("F:") else r"F:\temp"
os.makedirs(TMPROOT, exist_ok=True)


class Stats(unittest.TestCase):
    def test_purity(self):
        self.assertEqual(D.language_purity(["こんにちは"], "ja"), 1.0)
        self.assertEqual(D.language_purity(["hello"], "ja"), 0.0)
        self.assertAlmostEqual(D.language_purity(["abc あい"], "en"), 0.6)
        self.assertIsNone(D.language_purity(["123 !!"], "en"))

    def test_repetition(self):
        self.assertEqual(D.repetition_rate(["hello there", "Hello, there!", "something else"]), 1 / 3)
        self.assertIsNone(D.repetition_rate([]))
        self.assertEqual(D.repetition_rate(["a long distinct line", "totally other words"]), 0.0)

    def test_percentile_and_hist(self):
        self.assertEqual(D.percentile([1, 2, 3, 4], 0.5), 2.5)
        self.assertIsNone(D.percentile([], 0.5))
        h = D.length_hist([5, 15, 500])
        self.assertEqual(sum(x["n"] for x in h), 3)
        self.assertEqual(h[-1]["n"], 1)

    def test_compute_stats(self):
        tr = [{"who": "him", "text": "x"}, {"who": "her", "text": "ab", "kind": "reply"}, {"who": "her", "text": "cdef", "kind": "unprompted"}, {"who": "env", "text": "e"}]
        calls = [{"cost_micro": 1000000, "latency_s": 2.0, "prompt_tokens": 10, "completion_tokens": 5, "virtual_ts": "2026-11-02T09:00:00+09:00", "model": "m"},
                 {"cost_micro": 500000, "latency_s": 1.0, "error": "x", "virtual_ts": "2026-11-03T09:00:00+09:00"}]
        s = D.compute_stats({"lang": "en"}, tr, calls, [], lambda ts: int(ts[9]) - 1)
        self.assertEqual((s["calls"], s["errors"], s["replies"], s["unprompted"]), (2, 1, 1, 1))
        self.assertAlmostEqual(s["cost_usd"], 1.5)
        self.assertEqual([d["day"] for d in s["cost_per_day"]], [1, 2])
        self.assertEqual(s["calls_per_reply"], 2)
        self.assertEqual(s["reply_len"]["mean"], 3)

    def test_empty(self):
        s = D.compute_stats({}, [], [])
        self.assertEqual(s["calls"], 0)
        self.assertIsNone(s["latency"]["mean"])
        self.assertIsNone(s["repetition_rate"])

    def test_causal(self):
        c = D.causal_stats([{"causal": {"admitted": [{"weight": 3, "constant": True}, {"weight": 1}]}}, {"causal": {}}, {}])
        self.assertEqual(c["traces_with_causal"], 1)
        self.assertAlmostEqual(c["causal_share"], 0.75)
        self.assertAlmostEqual(c["constant_line_share"], 0.5)

    def test_scrub(self):
        o = D.scrub({"headers": {"Authorization": "Bearer x", "ok": 1}, "l": [{"api_key": "k", "a": 2}]})
        self.assertEqual(o, {"headers": {"ok": 1}, "l": [{"a": 2}]})


class Readers(unittest.TestCase):
    def test_partial_and_bad_lines(self):
        d = tempfile.mkdtemp(dir=TMPROOT)
        p = os.path.join(d, "t.jsonl")
        with open(p, "wb") as f:
            f.write(b'{"a": 1}\nnot json\n[1,2]\n{"a": 2}\n{"a": 3, "te')
        t = D.JsonlTail(p)
        self.assertEqual([x["a"] for x in t.refresh()], [1, 2])
        self.assertEqual(t.bad, 2)
        with open(p, "ab") as f:
            f.write('xt": "日本語"}\n{"a": 4}\n'.encode("utf-8"))
        items = t.refresh()
        self.assertEqual([x["a"] for x in items], [1, 2, 3, 4])
        self.assertEqual(t.read_span(2)["text"], "日本語")
        with open(p, "wb") as f:  # truncated and rewritten
            f.write(b'{"a": 9}\n')
        self.assertEqual([x["a"] for x in t.refresh()], [9])

    def test_missing(self):
        self.assertEqual(D.JsonlTail(os.path.join(TMPROOT, "nope.jsonl")).refresh(), [])
        s = D.Store(os.path.join(TMPROOT, "no_such_tree"))
        self.assertEqual(s.runs(), [])
        self.assertEqual(s.matches(), [])
        self.assertIsNone(s.modelcheck())
        self.assertEqual(s.pairs(), [])
        self.assertEqual(s.options()["arm"], [])

    def test_half_written_run(self):
        d = tempfile.mkdtemp(dir=TMPROOT)
        r = os.path.join(d, "runs", "r1")
        os.makedirs(os.path.join(r, "traces"))
        with open(os.path.join(r, "config.json"), "w") as f:
            f.write('{"arm": "S", "lang"')  # broken config
        with open(os.path.join(r, "calls.jsonl"), "w") as f:
            f.write('{"call_id": "c1", "usage": {"prompt_tokens": "7"}, "cost_micro": "12"}\n{"call_id"')
        with open(os.path.join(r, "traces", "o1.json"), "w") as f:
            f.write("{broken")
        s = D.Store(d)
        row = s.run_row("r1")
        self.assertEqual(row["calls"], 1)
        self.assertEqual(row["status"], "unknown")
        self.assertEqual(s.stats("r1")["prompt_tokens"], 7)
        self.assertEqual(s.traces("r1"), [])

    def test_underscore_runs_skipped(self):
        d = tempfile.mkdtemp(dir=TMPROOT)
        for n in ("r1", "_br_scratch"):
            os.makedirs(os.path.join(d, "runs", n))
            with open(os.path.join(d, "runs", n, "calls.jsonl"), "w") as f:
                f.write('{"call_id": "c1"}\n')
        self.assertEqual([r["ref"] for r in D.Store(d).runs()], ["r1"])

    def test_modelcheck_view(self):
        v = D.Store(FIX).modelcheck()["view"]
        self.assertEqual(v["pass_count"], 2)
        self.assertEqual(set(v["summary"]), {"fxmodel-a", "fxmodel-b"})
        self.assertEqual(len(v["moments"]), 2)
        m = v["moments"][0]
        self.assertEqual(len(m["samples"]), 6)
        self.assertEqual(m["chat"][0][0], "him")
        s = m["samples"][1]
        self.assertEqual(s["model"], "fxmodel-b")
        self.assertAlmostEqual(s["cost_usd"], 150 / 1e6)
        self.assertEqual([p["rank"] for p in s["passes"]], [2, 5])
        self.assertEqual(s["passes"][0]["flags"], ["timestamp_stamps"])
        self.assertEqual(D.modelcheck_view(None, [], "x")["moments"], [])

    def _mkrun(self, d, rid, cfg, files=("clock.json",), age=0, lines=0, calls=0):
        r = os.path.join(d, "runs", rid)
        os.makedirs(r)
        with open(os.path.join(r, "config.json"), "w") as f:
            json.dump(dict({"run_id": rid}, **cfg), f)
        for n in files:
            p = os.path.join(r, n)
            with open(p, "w") as f:
                if n == "transcript.jsonl":
                    for i in range(lines):
                        f.write(json.dumps({"who": "her", "text": "x%d" % i, "sim_day": 1}) + "\n")
                elif n == "calls.jsonl":
                    for i in range(calls):
                        f.write(json.dumps({"call_id": "c%d" % i, "model": "m", "cost_micro": 1000000}) + "\n")
                else:
                    f.write("{}")
            os.utime(p, (1000.0 - age, 1000.0 - age))
        return r

    def test_stale(self):
        d = tempfile.mkdtemp(dir=TMPROOT)
        base = {"arm": "S", "character": "momoka", "sim_days": 1, "status": "running"}
        self._mkrun(d, "old", base, ("clock.json", "calls.jsonl"), age=601, calls=1)
        self._mkrun(d, "fresh", base, ("clock.json", "calls.jsonl"), age=599, calls=1)
        self._mkrun(d, "mixed", base, ("clock.json", "transcript.jsonl"), age=0, lines=1)  # newest file wins
        self._mkrun(d, "doneold", dict(base, status="done"), ("clock.json", "calls.jsonl"), age=5000, calls=1)
        s = D.Store(d)
        s.now = lambda: 1000.0
        st = {r["run_id"]: r["status"] for r in s.runs()}
        self.assertEqual(st, {"old": "stale", "fresh": "running", "mixed": "running", "doneold": "done"})
        with open(os.path.join(d, "runs", "old", "config.json")) as f:
            self.assertEqual(json.load(f)["status"], "running")  # never written back

    def test_dev_runs(self):
        d = tempfile.mkdtemp(dir=TMPROOT)
        base = {"arm": "S", "character": "momoka", "sim_days": 3, "status": "done"}
        for rid in ("cl2_s_momoka", "bz_p_e2e_x", "bz_s_live2", "bz_s_time9", "bz_smoke_ds", "modelcheck"):
            self._mkrun(d, rid, base)
        self._mkrun(d, "bz_nosim", {"arm": "S", "status": "done"})
        s = D.Store(d)
        dev = {r["run_id"]: r["dev"] for r in s.runs()}
        self.assertEqual({k for k, v in dev.items() if not v}, {"cl2_s_momoka"})  # every bz_* is setup-era; cl1_* died on the port race
        self.assertEqual(len(dev), 7)
        self.assertEqual(s.options()["status"], ["done"])
        self.assertEqual(s.options()["arm"], ["S"])
        self.assertEqual(s.options(dev=True)["arm"], ["S"])
        self.assertIsNone(D.Store(d).options().get("nope"))

    def test_canned(self):
        d = tempfile.mkdtemp(dir=TMPROOT)
        base = {"arm": "P", "character": "tomoe", "sim_days": 1, "status": "running"}
        self._mkrun(d, "bz_p_e2e_dummy_1", base, ("transcript.jsonl",), lines=2)
        self._mkrun(d, "nocalls", base, ("transcript.jsonl",), lines=2)
        self._mkrun(d, "stubcmd", dict(base, arm_cmd=["python", "-m", "bzombie.harness.stub_arm"]), ("calls.jsonl",), calls=1)
        self._mkrun(d, "real", base, ("transcript.jsonl", "calls.jsonl"), lines=2, calls=2)
        s = D.Store(d)
        s.now = lambda: 1000.0
        c = {r["run_id"]: r["canned"] for r in s.runs()}
        self.assertEqual(c, {"bz_p_e2e_dummy_1": "DUMMY", "nocalls": "STUB", "stubcmd": "STUB", "real": None})
        real = [r for r in s.runs() if r["run_id"] == "real"][0]
        self.assertEqual(real["days_done"], 1)
        self.assertEqual(real["calls_per_day"], 2)
        self.assertAlmostEqual(real["cost_per_day_usd"], 2.0)
        self.assertEqual(real["kind"], "full")

    def test_calibrations(self):
        cals = D.Store(FIX).calibrations()
        self.assertEqual([c["stamp"] for c in cals], ["20260102_000002", "20260101_000001"])  # newest first
        n, o = cals
        self.assertEqual((n["calibrated"], n["of"]), (4, 4))
        self.assertEqual((o["calibrated"], o["of"]), (3, 4))
        self.assertEqual(o["uncalibrated"], ["own_life"])
        self.assertEqual(n["calls"], 8)
        self.assertAlmostEqual(n["cost_usd"], 0.08)
        row = [x for x in o["rows"] if x["criterion"] == "own_life" and x["lang"] == "en"][0]
        self.assertEqual((row["planted"], row["caught"], row["calibrated"]), (2, 1, False))
        self.assertEqual([e["caught"] for e in row["entries"]], [True, False])
        self.assertEqual(len(D.Store(FIX).matches()), 2)  # calibration is not a match
        self.assertEqual(D.Store(tempfile.mkdtemp(dir=TMPROOT)).calibrations(), [])

    def test_bad_names(self):
        s = D.Store(FIX)
        self.assertIsNone(s.run_dir("../x"))
        self.assertIsNone(s.trace("fx_S_momoka_ds", "..\\..\\config"))
        self.assertIsNone(s.pair("../pairs/p1"))

    def test_fixture(self):
        s = D.Store(FIX)
        refs = [r["ref"] for r in s.runs()]
        self.assertEqual(len(refs), 5)
        self.assertIn("fx_S_momoka_ds~no_gauge", refs)
        st = s.stats("fx_S_tomoe_glm")
        self.assertEqual(st["language_purity"], 1.0)
        m = s.match("m_momoka")
        self.assertEqual(m["agreement"]["agreed"], 2)
        self.assertEqual(m["calibration_caught"], {"caught": 1, "of": 2})
        p = s.pair("p1")
        self.assertNotIn("mapping", json.dumps(p))
        c = s.compare("fx_S_momoka_ds", "fx_P_momoka_ds")
        self.assertTrue(c["rows"])


class EndToEnd(unittest.TestCase):
    PORT = 18359

    def get(self, path):
        with urllib.request.urlopen("http://127.0.0.1:%d%s" % (self.PORT, path), timeout=10) as r:
            body = r.read()
            return r.status, body

    def j(self, path):
        st, b = self.get(path)
        self.assertEqual(st, 200, path)
        return json.loads(b.decode("utf-8"))

    def test_e2e(self):
        data = os.path.join(tempfile.mkdtemp(dir=TMPROOT), "var")
        shutil.copytree(FIX, data)
        a = ["--data", data, "--port", str(self.PORT)]
        self.assertEqual(cli(["start"] + a), 0)
        try:
            for p in ("/", "/app.js", "/style.css", "/?view=judge&run=x"):
                st, b = self.get(p)
                self.assertEqual(st, 200, p)
            self.assertIn("B-zombie", self.get("/")[1].decode("utf-8"))
            runs = self.j("/api/runs")["runs"]
            self.assertEqual(len(runs), 5)
            self.assertTrue(self.j("/api/options")["model"])
            ref = "fx_S_momoka_ds"
            tr = self.j("/api/transcript?run=" + ref)
            her = [x for x in tr["lines"] if x["who"] == "her"][0]
            self.assertIn("テスト", her["text"])  # Japanese survives the trip
            t = self.j("/api/trace?run=%s&output=%s" % (ref, her["output_id"]))
            self.assertTrue(t["call_meta"])
            cid = t["final_call_id"]
            c = self.j("/api/call?run=%s&call=%s" % (ref, cid))
            self.assertIn("messages", c["request"])
            self.assertTrue(self.j("/api/stats?run=" + ref)["calls"])
            self.assertTrue(self.j("/api/stats?run=%s~no_gauge" % ref)["calls"])
            self.assertTrue(self.j("/api/run?run=" + ref)["arm"])
            cmp_ = self.j("/api/compare?a=%s&b=fx_P_momoka_ds&env=0" % ref)
            self.assertTrue(cmp_["rows"])
            self.assertEqual(len(self.j("/api/judge")["matches"]), 2)
            self.assertEqual(len(self.j("/api/judge")["calibrations"]), 2)
            self.assertNotIn("dev", self.j("/api/options")["status"])
            self.assertFalse(any(r["dev"] for r in runs))
            self.assertEqual(self.j("/api/judge?match=m_momoka")["match_id"], "m_momoka")
            self.assertTrue(self.j("/api/judge")["modelcheck"]["view"]["moments"])
            self.assertEqual(len(self.j("/api/pairs")["pairs"]), 2)
            pair = self.j("/api/pair?id=p1")
            self.assertEqual(set(pair), {"pair_id", "A", "B", "vote"})
            with self.assertRaises(urllib.error.HTTPError) as cm:
                self.get("/api/run?run=nope")
            self.assertEqual(cm.exception.code, 404)
            # bad Host is refused
            rq = urllib.request.Request("http://127.0.0.1:%d/api/runs" % self.PORT, headers={"Host": "evil.example"})
            with self.assertRaises(urllib.error.HTTPError) as cm:
                urllib.request.urlopen(rq, timeout=5)
            self.assertEqual(cm.exception.code, 403)
            # vote
            body = json.dumps({"pair_id": "p1", "choice": "B", "note": "メモ note"}).encode("utf-8")
            rq = urllib.request.Request("http://127.0.0.1:%d/api/vote" % self.PORT, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(rq, timeout=5) as r:
                self.assertEqual(r.status, 200)
            bad = urllib.request.Request("http://127.0.0.1:%d/api/vote" % self.PORT, data=json.dumps({"pair_id": "p1", "choice": "Z"}).encode(), headers={"Content-Type": "application/json"})
            with self.assertRaises(urllib.error.HTTPError) as cm:
                urllib.request.urlopen(bad, timeout=5)
            self.assertEqual(cm.exception.code, 400)
            lines = open(os.path.join(data, "votes.jsonl"), encoding="utf-8").read().splitlines()
            self.assertEqual(len(lines), 1)
            v = json.loads(lines[0])
            self.assertEqual((v["pair_id"], v["choice"], v["note"]), ("p1", "B", "メモ note"))
            self.assertTrue(self.j("/api/pairs")["pairs"][0]["voted"])
            self.assertNotIn("fx_S", json.dumps(self.j("/api/pair?id=p1")))
        finally:
            self.assertEqual(cli(["stop"] + a), 0)
        with self.assertRaises(Exception):
            self.get("/api/runs")

    def test_empty_tree(self):
        port = self.PORT + 1
        data = tempfile.mkdtemp(dir=TMPROOT)
        a = ["--data", data, "--port", str(port)]
        self.assertEqual(cli(["start"] + a), 0)
        try:
            for ep in ("runs", "options", "judge", "pairs"):
                with urllib.request.urlopen("http://127.0.0.1:%d/api/%s" % (port, ep), timeout=5) as r:
                    self.assertEqual(r.status, 200)
        finally:
            cli(["stop"] + a)


if __name__ == "__main__":
    unittest.main()
