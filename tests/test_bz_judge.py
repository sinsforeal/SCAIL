"""Judge runner on stubs: calibrate, match on two stub-harness runs, splice, pass-2 swap, quote validation, billing."""
import os
import re
import subprocess
import sys
import tempfile
import unittest

_tmp = tempfile.mkdtemp(prefix="bzj_", dir=r"F:\temp") if os.path.isdir(r"F:\temp") else tempfile.mkdtemp()
os.environ.setdefault("BZ_VAR", _tmp)

import json  # noqa: E402

from bzombie import common, credits, llm  # noqa: E402
from bzombie.common import append_jsonl, read_json, read_jsonl, run_dir, write_json  # noqa: E402
from bzombie.harness import driver  # noqa: E402
from bzombie.judge import runner  # noqa: E402

from tests.bz_safety import refuse_live_var  # noqa: E402

refuse_live_var(common.VAR)  # before any write or rmtree of the queue
llm.backend = llm.canned
write_json(common.PROFILES / "tomoe.json", {"voice": "stub"})
CAL_IDS = ["answers_him.en.1", "answers_him.en.2", "frame_integrity.en.1"]
PLANTED_ONLY, PLANTED_TEXT = set(), set()
for _e in runner.load_defects():
    PLANTED_ONLY |= set(_e["planted"]) - set(_e["clean"])
    if _e["kind"] == "defect" and runner.planted_line(_e):
        PLANTED_TEXT.add(runner.planted_line(_e))


class FakeJudge:
    """Always picks the side without a marker (a planted-only line from defects.json, or MARK). Records where it sat."""

    def __init__(self, junk_quote=False, fail_first=False):
        self.calls, self.junk, self.fail_first, self.n = [], junk_quote, fail_first, 0

    def __call__(self, task, system, prompt):
        self.n += 1
        assert task == "judge"
        sec = {s: re.search(rf"=== TRANSCRIPT {s} ===\n(.*?)\n=== END OF {s} ===", prompt, re.S).group(1) for s in "AB"}
        marked = {s: ("MARK" in sec[s]) or any(x in sec[s].split("\n") for x in PLANTED_ONLY) \
            or any(t in sec[s] for t in PLANTED_TEXT) for s in "AB"}
        self.calls.append(marked)
        if self.fail_first and self.n == 1:
            return "this is not json"
        if marked["A"] == marked["B"]:
            v, sc = "tie", {"A": 3, "B": 3}
        else:
            v = "B" if marked["A"] else "A"
            sc = {"A": 2, "B": 4} if marked["A"] else {"A": 4, "B": 2}
        q = {}
        for s in "AB":
            m = re.search(r"\] her(?: \(unprompted\))?: (.*)", sec[s])
            q[s] = [m.group(1)] if m else []
        if self.junk:
            q["A"].append("THIS TEXT IS NOT IN ANY SLICE")
        return json.dumps({"verdict": v, "scores": sc, "reason": "stub", "quotes": q})


def stub_cfg(run_id, port, character="tomoe", lang="en"):
    cmd = [sys.executable, "-m", "bzombie.harness.stub_arm", "--port", "{port}", "--arm", "{arm}"]
    return {"run_id": run_id, "arm": "S", "character": character, "lang": lang, "model": "stub", "cap_usd": 1,
            "sim_days": 2, "clock_start": "2026-11-02T00:00:00", "seed": 7, "use_limits": False,
            "arm_port": port, "arm_cmd": cmd, "step_s": 3600}


def validate_results(tc, r, with_labels=True):
    for k in ("match_id", "character", "label_map", "criteria", "calibration", "summary"):
        tc.assertIn(k, r)
    if with_labels:
        tc.assertEqual(set(r["label_map"]), {"A", "B"})
    for c in r["criteria"]:
        tc.assertEqual(set(c), {"id", "name", "passes"})
        tc.assertEqual([p["pass"] for p in c["passes"]], [1, 2])
        for p in c["passes"]:
            tc.assertEqual(set(p), {"pass", "verdict", "scores", "reason", "quotes"})
            tc.assertIn(p["verdict"], ("A", "B", "tie"))
            tc.assertEqual(set(p["quotes"]), {"A", "B"})
            if p["scores"] is not None:
                tc.assertTrue(all(1 <= p["scores"][s] <= 5 for s in "AB"))
    for e in r["calibration"]:
        tc.assertEqual(set(e), {"defect", "caught"})
        tc.assertIsInstance(e["caught"], bool)


class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["BZ_LLM_STUB"] = "1"
        llm.backend = llm.canned
        for rid, port in (("jb_a", 18395), ("jb_b", 18396)):
            driver.init_run(driver.load_config(stub_cfg(rid, port)))
            driver.drive(rid)
            assert read_json(run_dir(rid) / "state.json")["status"] == "done"
        # marker: run jb_b carries a her line with MARK on day 2 (an X slice sees it)
        tr = read_jsonl(run_dir("jb_b") / "transcript.jsonl")
        last = [e for e in tr if e["who"] == "her"][-1]
        append_jsonl(run_dir("jb_b") / "transcript.jsonl",
                     {**last, "text": "MARK odd line", "virtual_ts": "2026-11-03T23:00:00", "i": 999})

    def setUp(self):
        self.old = (llm.backend, runner.claude_billing)
        os.environ["BZ_LLM_STUB"] = "1"

    def tearDown(self):
        llm.backend, runner.claude_billing = self.old

    def test_calibrate_three_entries(self):
        fj = FakeJudge()
        llm.backend = fj
        code, r = runner.calibrate(ids=CAL_IDS, stamp="t1", workers=1)
        self.assertEqual(code, 0)
        validate_results(self, r, with_labels=False)
        self.assertEqual([e["caught"] for e in r["calibration"]], [True, True, True])
        self.assertEqual(len(fj.calls), 6)
        # pass 1 puts planted in B, pass 2 in A, and the stored passes are back in clean=A labels
        for i in range(3):
            self.assertEqual((fj.calls[2 * i]["A"], fj.calls[2 * i]["B"]), (False, True))
            self.assertEqual((fj.calls[2 * i + 1]["A"], fj.calls[2 * i + 1]["B"]), (True, False))
        for c in r["criteria"]:
            self.assertEqual([p["verdict"] for p in c["passes"]], ["A", "A"])
        s = r["summary"]
        self.assertTrue(s["calibrated"]["answers_him"])
        self.assertTrue(s["by_lang"]["answers_him"]["en"]["complete"])
        self.assertFalse(s["by_lang"]["frame_integrity"]["en"]["complete"])
        self.assertTrue((common.VAR / "judge" / "calibration" / "t1" / "results.json").exists())

    def test_score_rules(self):
        d = {"id": "x", "kind": "defect", "expected_verdict": {"pass1": "A", "pass2": "B"}}
        good = [{"verdict": "A", "scores": {"A": 4, "B": 2}}, {"verdict": "A", "scores": {"A": 5, "B": 3}}]
        self.assertTrue(runner.score_entry(d, good))
        self.assertFalse(runner.score_entry(d, [good[0], {"verdict": "tie", "scores": {"A": 3, "B": 3}}]))
        self.assertFalse(runner.score_entry(d, [good[0], {"verdict": "A", "scores": None}]))
        c = {"id": "c", "kind": "control", "expected_verdict": {"pass1": "any", "pass2": "any"}}
        self.assertTrue(runner.score_entry(c, [good[0], {"verdict": "A", "scores": {"A": 3, "B": 3}}]))
        self.assertFalse(runner.score_entry(c, [good[0], {"verdict": "A", "scores": {"A": 5, "B": 3}}]))

    def test_match_two_stub_runs(self):
        llm.backend = FakeJudge()
        runner.calibrate(ids=CAL_IDS[:2], stamp="t2", workers=1)  # answers_him en complete
        fj = FakeJudge()
        llm.backend = fj
        code, r = runner.match("jb_a", "jb_b", "tomoe", match_id="m1", seed=11, workers=1)
        self.assertEqual(code, 0)
        validate_results(self, r)
        self.assertEqual(len(r["criteria"]), 9)
        self.assertEqual(len(fj.calls), 18)
        lm = r["label_map"]
        self.assertEqual(sorted(lm.values()), ["jb_a", "jb_b"])
        bad_label = "A" if lm["A"] == "jb_b" else "B"  # the MARK run
        good = "B" if bad_label == "A" else "A"
        by = {c["id"]: c for c in r["criteria"]}
        for cid in ("memory_continuity", "emotional_arc", "grounded_claims", "non_repetition", "frame_integrity"):
            self.assertEqual([p["verdict"] for p in by[cid]["passes"]], [good, good], cid)  # X slices carry the MARK
        # pass 2 swap: the marked side sat in the other prompt slot, the stored verdicts agree anyway
        i = [c["id"] for c in r["criteria"]].index("memory_continuity")
        self.assertEqual(fj.calls[2 * i][bad_label], True)
        self.assertEqual(fj.calls[2 * i + 1][good], True)  # pass 2: the marked content sits in the other slot
        self.assertEqual(fj.calls[2 * i + 1][bad_label], False)
        s = r["summary"]
        self.assertEqual({u["id"] for u in s["uncalibrated"]}, set(runner.CRITERIA) - {"answers_him"})
        self.assertTrue(s["per_criterion"]["answers_him"]["calibrated"])
        self.assertNotIn(bad_label, [s["winner"]])  # only answers_him counts and it is a tie: no MARK in W slices
        self.assertEqual(s["seed"], 11)
        res = read_json(common.VAR / "judge" / "m1" / "results.json")
        self.assertEqual(res["match_id"], "m1")
        # blind: nothing that names an arm, run id or model in the slices written to disk
        for p in (common.VAR / "judge" / "m1" / "slices").glob("*.txt"):
            txt = p.read_text(encoding="utf-8")
            self.assertNotIn("jb_a", txt)
            self.assertNotIn("claude", txt)
        self.assertTrue((common.VAR / "judge" / "m1" / "slices" / "answers_him.A.txt").read_text(
            encoding="utf-8").startswith("=== W1 ("))

    def test_label_assignment_is_seeded_and_recorded(self):
        llm.backend = FakeJudge()
        seen = set()
        for seed in range(1, 9):
            _, r = runner.match("jb_a", "jb_b", "tomoe", match_id=f"seed{seed}", seed=seed, criteria=["frame_integrity"],
                                workers=1)
            seen.add(r["label_map"]["A"])
            plan = read_json(common.VAR / "judge" / f"seed{seed}" / "plan.json")
            self.assertEqual((plan["seed"], plan["label_map"]), (seed, r["label_map"]))
        self.assertEqual(seen, {"jb_a", "jb_b"})

    def test_resume_uses_cache(self):
        fj = FakeJudge()
        llm.backend = fj
        runner.match("jb_a", "jb_b", "tomoe", match_id="m_res", seed=3, criteria=["answers_him"], workers=1)
        self.assertEqual(fj.n, 2)
        runner.match("jb_a", "jb_b", "tomoe", match_id="m_res", criteria=["answers_him"], workers=1)
        self.assertEqual(fj.n, 2)

    def test_quote_validation_and_retry(self):
        shown = {"A": "[d1 Mon 10:00] her: hello there", "B": "[d1 Mon 10:00] her: bye"}
        ok = {"verdict": "A", "scores": {"A": 4, "B": 2}, "reason": "r", "quotes": {"A": ["hello there", "nope"], "B": ["bye"]}}
        clean, bad, err = runner.validate(ok, shown)
        self.assertEqual((err, bad, clean["quotes"]), (None, 1, {"A": ["hello there"], "B": ["bye"]}))
        self.assertIsNotNone(runner.validate({**ok, "verdict": "B"}, shown)[2])  # names the lower-scored side
        self.assertIsNotNone(runner.validate({**ok, "scores": {"A": 6, "B": 2}}, shown)[2])
        self.assertIsNotNone(runner.validate({**ok, "extra": 1}, shown)[2])
        fj = FakeJudge(junk_quote=True, fail_first=True)
        llm.backend = fj
        p, meta = runner.run_pass("answers_him", "tomoe", "[d1 Mon 10:00] her: a\nMARK", "[d1 Mon 10:00] her: b", 1)
        self.assertEqual((fj.n, meta["retries"], meta["bad_quotes"], meta["invalid"]), (2, 1, 1, 0))
        self.assertNotIn("THIS TEXT IS NOT IN ANY SLICE", p["quotes"]["A"])
        llm.backend = lambda t, s, pr: "garbage"
        p, meta = runner.run_pass("answers_him", "tomoe", "x", "y", 2)
        self.assertEqual((p["verdict"], p["scores"], meta["invalid"]), ("tie", None, 1))
        self.assertTrue(p["reason"].startswith("invalid judge output"))

    def test_fill_leaves_json_braces_and_slices(self):
        out = runner.fill(runner.template("answers_him"), "CARD {slice_B}", "AAA", "BBB")
        self.assertIn('{"verdict": "A"', out)
        self.assertIn("AAA", out)
        self.assertNotIn("{character_card}", out)

    def test_splice_on_stub_run(self):
        fj = FakeJudge()
        llm.backend = fj
        code, r = runner.splice("jb_a", per_criterion=1, criteria=["frame_integrity", "answers_him"], stamp="sp1",
                                workers=1, seed=5)
        self.assertEqual(code, 0)
        validate_results(self, r)
        self.assertEqual(r["summary"]["per_criterion"]["frame_integrity"], {"n": 1, "caught": 1})
        self.assertEqual(r["summary"]["per_criterion"]["answers_him"]["n"], 1)
        # the planted line really sits in side B only: the fake saw it on B in pass 1
        self.assertTrue(fj.calls[0]["B"] and not fj.calls[0]["A"])

    def test_grant_exhausted_pauses_and_settles_once(self):
        calls = []

        def fake_credits(args):
            calls.append(str(args[0]))
            if args[0] == "reserve":
                return 0, json.dumps({"id": "r1", "key_label": "lab"}), ""
            return 0, json.dumps({"id": "r1"}), ""

        def fake_run(cmd, **kw):
            return subprocess.CompletedProcess(cmd, 1, json.dumps({"result": "Your credit balance is too low"}), "")

        old = (credits.runner, credits.read_key, credits.read_workspace, llm._run)
        credits.runner, credits.read_key, credits.read_workspace = fake_credits, lambda l: "sk-FAKE", lambda l: "ws"
        llm._run = fake_run
        llm.backend = None
        os.environ.pop("BZ_LLM_STUB", None)
        runner.claude_billing = "credits"  # credits mode: a used-up grant pauses (auto goes on to the queue, next test)
        try:
            code, r = runner.calibrate(ids=CAL_IDS[:1], stamp="t_pause", workers=1)
        finally:
            credits.runner, credits.read_key, credits.read_workspace, llm._run = old
        self.assertEqual((code, r), (75, None))
        self.assertEqual(calls, ["reserve", "dispatch", "settle"])
        self.assertIsNone(llm.session)
        p = read_json(common.VAR / "judge" / "calibration" / "t_pause" / "pause.json")
        self.assertEqual(p["reason"], "grant_exhausted")
        self.assertNotIn("sk-FAKE", json.dumps(p))
        rows = read_jsonl(common.VAR / "judge" / "calibration" / "t_pause" / "claude_calls.jsonl")
        self.assertEqual(rows[0]["task"], "judge")

    def _worker(self, fj):
        """Thread standing in for the bench worker: beats worker.json and answers judge requests through FakeJudge."""
        import threading
        import time
        q = llm.queue_dir()
        q.mkdir(parents=True, exist_ok=True)
        stop = threading.Event()

        def loop():
            while not stop.is_set():
                write_json(q / "worker.json", {"session_label": "fake", "last_seen_wall": time.time()})
                for rp in sorted(q.glob("*.req.json")):
                    req = read_json(rp)
                    ap = q / f"{req['req_id']}.ans.json" if req else None
                    if not req or ap.exists():
                        continue
                    write_json(q / "tmp.ans", {"req_id": req["req_id"], "text": fj("judge", req["system"], req["prompt"]),
                                               "is_error": False, "error": None, "agent_model": "sonnet"})
                    common.replace_retry(q / "tmp.ans", ap)
                time.sleep(0.02)

        t = threading.Thread(target=loop, daemon=True)
        t.start()
        return stop, t

    def tesa_auto_falls_through_to_queue_after_grant(self):
        calls = []

        def fake_credits(args):
            calls.append(str(args[0]))
            return 0, json.dumps({"id": "r2", "key_label": "lab"}), ""

        def fake_run(cmd, **kw):
            return subprocess.CompletedProcess(cmd, 1, json.dumps({"result": "Your credit balance is too low"}), "")

        old = (credits.runner, credits.read_key, credits.read_workspace, llm._run, llm.POLL_S)
        credits.runner, credits.read_key, credits.read_workspace = fake_credits, lambda l: "sk-FAKE", lambda l: "ws"
        llm._run, llm.POLL_S = fake_run, 0.05
        llm.backend = None
        os.environ.pop("BZ_LLM_STUB", None)
        runner.claude_billing = "auto"
        fj = FakeJudge()
        stop, t = self._worker(fj)
        try:
            code, r = runner.calibrate(ids=CAL_IDS[:1], stamp="a_auto", workers=1)
        finally:
            stop.set()
            t.join(2)
            credits.runner, credits.read_key, credits.read_workspace, llm._run, llm.POLL_S = old
        self.assertEqual(code, 0)
        self.assertEqual(calls, ["reserve", "dispatch", "settle"])  # settled once, at the switch
        self.assertIsNone(llm.session)
        self.assertEqual(fj.n, 2)  # both passes answered by the worker
        rows = read_jsonl(common.VAR / "judge" / "calibration" / "a_auto" / "claude_calls.jsonl")
        self.assertEqual([x["billing"] for x in rows if not x["is_error"]], ["queue", "queue"])

    def test_queue_worker_down_pauses(self):
        import shutil
        shutil.rmtree(llm.queue_dir(), ignore_errors=True)
        old = llm.backend
        llm.backend = None
        os.environ.pop("BZ_LLM_STUB", None)
        runner.claude_billing = "queue"
        try:
            code, r = runner.calibrate(ids=CAL_IDS[:1], stamp="t_down", workers=1)
        finally:
            llm.backend = old
        self.assertEqual((code, r), (75, None))
        p = read_json(common.VAR / "judge" / "calibration" / "t_down" / "pause.json")
        self.assertEqual(p["reason"], "worker_down")

    def test_slice_cut_pairs_and_caps(self):
        evA, _ = runner.load_events("jb_a")
        evB, _ = runner.load_events("jb_b")
        ctx = runner.Ctx(evA, evB, 1)
        self.assertTrue(ctx.pairs)
        for ia, ib in ctx.pairs:
            self.assertEqual(evA[ia]["day"], evB[ib]["day"])
            self.assertLessEqual(abs((evA[ia]["ts"] - evB[ib]["ts"]).total_seconds()), 45 * 60)
        sa, sb, level = ctx.build("memory_continuity")
        self.assertEqual(level, 0)
        self.assertRegex(sa, r"=== day 1 \(\w{3}\) ===\n\[d1 \w{3} \d\d:\d\d\] ")
        self.assertIn("env (world):", sa)
        self.assertNotIn("env (", ctx.build("frame_integrity")[0])
        self.assertTrue(runner.is_question("what time?") and runner.is_question("行くの") and not runner.is_question("ok"))


if __name__ == "__main__":
    unittest.main()
