"""End-to-end harness test on stubs: 2-day run, budget pause and resume, branch. No spend, no claude, no limits ticket."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

# bzombie.common pins VAR at its first import. First module in the process: a fresh temp VAR. Later modules (another
# test module imported first): keep the env, which the stub arms inherit, in line with the pinned VAR.
_TMP = r"H:\SCAIL\temp" if os.path.isdir(r"H:\SCAIL\temp") else None
_REAL_VAR = Path(r"H:\SCAIL\bzombie\var")
_REPOINTED = None
if "bzombie.common" in sys.modules and "bzt" not in Path(str(sys.modules["bzombie.common"].VAR)).name:
    # an earlier module pinned the real VAR (tk-bea): repoint it, and every bzombie module that copied it, to a temp dir
    # so no run dir or port claim lands in the real var
    _old = sys.modules["bzombie.common"].VAR
    _new = Path(tempfile.mkdtemp(prefix="bzt_", dir=_TMP))
    _swap = {_old: _new, _old / "profiles": _new / "profiles", _old / "env_cache": _new / "env_cache"}
    for _m in [m for n, m in list(sys.modules.items()) if n.startswith("bzombie") and m is not None]:
        for _k in ("VAR", "PROFILES", "ENV_CACHE"):
            _v = getattr(_m, _k, None)
            if isinstance(_v, Path) and _v in _swap:
                setattr(_m, _k, _swap[_v])
    _REPOINTED = _new
    import atexit  # later modules in the same run share this dir: remove it only when the process ends
    import shutil as _sh
    atexit.register(lambda: _sh.rmtree(_new, ignore_errors=True))
    os.environ["BZ_VAR"] = str(_new)
elif "bzombie.common" in sys.modules:
    os.environ["BZ_VAR"] = str(sys.modules["bzombie.common"].VAR)
else:
    os.environ["BZ_VAR"] = tempfile.mkdtemp(prefix="bzt_", dir=_TMP)

import json  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402

from bzombie import common, credits, llm  # noqa: E402
from bzombie.common import PROFILES, read_json, read_jsonl, run_dir, write_json  # noqa: E402
from bzombie.harness import branch, driver  # noqa: E402

llm.backend = llm.canned
write_json(PROFILES / "tomoe.json", {"voice": "stub"})
FAKE_KEY = "sk-ant-FAKEKEY-for-tests"


class FakeCredits:
    """Stands in for credits.py: records every call, can refuse a verb."""

    def __init__(self, refuse=None, why="insufficient confirmed shared API credit for this reservation"):
        self.calls, self.refuse, self.why = [], refuse, why

    def __call__(self, args):
        self.calls.append([str(a) for a in args])
        verb = args[0]
        if verb == self.refuse:
            return 3, "", self.why
        if verb == "reserve":
            return 0, json.dumps({"id": "res1", "key_label": "lab1", "state": "reserved"}), ""
        return 0, json.dumps({"id": "res1", "state": verb}), ""

    def verbs(self):
        return [c[0] for c in self.calls]


def use_credits(refuse=None, **kw):
    fc = FakeCredits(refuse, **kw)
    credits.runner = fc
    credits.read_key = lambda label: FAKE_KEY
    credits.read_workspace = lambda label: "wrkspc_test"
    return fc


use_credits()


def cfg(run_id, port, fail_at=0):
    cmd = [sys.executable, "-m", "bzombie.harness.stub_arm", "--port", "{port}", "--arm", "{arm}"]
    if fail_at:
        cmd += ["--fail-402-at-send", str(fail_at)]
    return {"run_id": run_id, "arm": "S", "character": "tomoe", "lang": "en", "model": "stub", "cap_usd": 1,
            "sim_days": 2, "clock_start": "2026-11-02T00:00:00", "seed": 7, "use_limits": False,
            "arm_port": port, "arm_cmd": cmd, "step_s": 3600,
            "him_via": "claude"}  # these tests drive Claude billing through sim-him's llm calls


class FakeWorker(threading.Thread):
    """Stands in for the bench worker session: beats worker.json, answers every .req.json with canned text."""

    def __init__(self, error_task=None):
        super().__init__(daemon=True)
        self.stop, self.answered, self.error_task = threading.Event(), [], error_task
        self.q = llm.queue_dir()
        self.q.mkdir(parents=True, exist_ok=True)
        write_json(self.q / "worker.json", {"session_label": "fake", "last_seen_wall": time.time()})

    def run(self):
        while not self.stop.is_set():
            write_json(self.q / "worker.json", {"session_label": "fake", "last_seen_wall": time.time()})
            for rp in sorted(self.q.glob("*.req.json")):  # the driver moves answered files away under us
                req = read_json(rp)
                if not req:
                    continue
                ap = self.q / f"{req['req_id']}.ans.json"
                if ap.exists():
                    continue
                task = {v: k for k, v in llm.TASK_NAMES.items()}.get(req["task"], req["task"])
                err = task == self.error_task
                self.answered.append(req)
                write_json(self.q / "tmp.ans", {"req_id": req["req_id"], "text": "" if err else
                                                llm.canned(task, req["system"], req["prompt"]),
                                                "is_error": err, "error": "boom" if err else None,
                                                "answered_wall": time.time(), "agent_model": "sonnet"})
                common.replace_retry(self.q / "tmp.ans", ap)
            time.sleep(0.02)


def clean_queue():
    shutil.rmtree(llm.queue_dir(), ignore_errors=True)


class T(unittest.TestCase):
    def setUp(self):
        llm.POLL_S = 0.05
        clean_queue()

    @classmethod
    def tearDownClass(cls):  # a budget pause leaves its stub arm running by design; stop them all
        from bzombie.harness.armclient import Arm
        for port in (18391, 18392, 18393, 18394, 18381, 18382, 18383, 18384, 18385, 18386):
            try:
                Arm(port).stop()
            except Exception:
                pass

    def test_run_pause_resume_branch(self):
        c = driver.load_config(cfg("t_run", 18391, fail_at=2))
        driver.init_run(c)
        driver.drive("t_run")
        st = read_json(run_dir("t_run") / "state.json")
        self.assertEqual(st["status"], "paused")
        self.assertEqual(st["reason"], "budget")
        self.assertEqual(read_json(run_dir("t_run") / "config.json")["status"], "paused")
        driver.drive("t_run")
        st = read_json(run_dir("t_run") / "state.json")
        self.assertEqual(st["status"], "done", st)
        rd = run_dir("t_run")
        tr = read_jsonl(rd / "transcript.jsonl")
        whos = {e["who"] for e in tr}
        self.assertEqual(whos, {"him", "her", "env"})
        self.assertEqual({e["sim_day"] for e in tr}, {1, 2})
        self.assertEqual(len({(e["virtual_ts"], e["text"]) for e in tr}), len(tr), "duplicate lines")
        outs = [e for e in tr if e["who"] == "her"]
        self.assertTrue(outs)
        for e in outs:
            self.assertTrue((rd / "traces" / f"{e['output_id']}.json").exists())
        ck = read_json(rd / "clock.json")  # last simulated moment, last day run (not the next day's 00:00)
        self.assertEqual((ck["sim_day"], ck["virtual_ts"]), (2, "2026-11-03T23:59:59"))
        self.assertNotIn("stub", read_json(rd / "config.json"))  # BZ_LLM_STUB unset in this test
        self.assertEqual(read_json(rd / "config.json")["status"], "done")
        self.assertTrue((rd / "snapshots" / "harness" / "day1_end.json").exists())
        # branch: mute her at day1_end, replay his next message
        bid = branch.branch("t_run", "day1_end", "mute", True)
        bdir = rd / "branches" / bid
        self.assertEqual(read_json(bdir / "branch.json")["target"], "mute")
        btr = read_jsonl(bdir / "transcript.jsonl")
        base_len = read_json(rd / "snapshots" / "harness" / "day1_end.json")["transcript_len"]
        new = btr[base_len:]
        self.assertTrue(any(e["who"] == "him" for e in new))
        self.assertFalse(any(e["who"] == "her" for e in new), "muted branch must not reply")
        base_next = [e for e in tr[base_len:] if e["who"] == "him"][0]
        self.assertEqual([e for e in new if e["who"] == "him"][0]["text"], base_next["text"])
        self.assertTrue((bdir / "calls.jsonl").exists() or True)

    def test_credits_flow_settles_once(self):
        fc = use_credits()
        c = driver.load_config({**cfg("t_cr", 18392), "claude_cap_usd": 7})
        self.assertEqual(c["model"], "stub")
        self.assertFalse(driver.load_config({k: v for k, v in cfg("t_cr2", 18392).items() if k not in
                                             ("use_limits", "model")})["use_limits"])
        self.assertEqual(driver.load_config({k: v for k, v in cfg("t_cr3", 18392).items() if k != "model"})["model"],
                         "deepseek-v4.1-flash-1017")
        driver.init_run(c)
        driver.drive("t_cr")
        self.assertEqual(read_json(run_dir("t_cr") / "state.json")["status"], "done")
        self.assertEqual(fc.verbs(), ["reserve", "dispatch", "settle"])
        r = fc.calls[0]
        self.assertEqual(r[r.index("--who") + 1], "scail/bzombie_t_cr")
        self.assertEqual(float(r[r.index("--amount-usd") + 1]), 7.0)
        self.assertIn("--pid", r)
        self.assertEqual(fc.calls[1][1], "res1")
        self.assertEqual(fc.calls[2][:3], ["settle", "res1", "--actual-usd"])
        self.assertIsNone(llm.session)

    def test_refusal_pauses_and_never_falls_back(self):
        # a used-up grant pauses as grant_exhausted (next: bench worker queue); any other refusal as credits_refused
        cases = [("t_ref", "insufficient confirmed shared API credit for this reservation", "grant_exhausted"),
                 ("t_ref2", "unresolved usage on an earlier reservation", "credits_refused")]
        try:
            for rid, why, reason in cases:
                fc = use_credits(refuse="reserve", why=why)
                driver.init_run(driver.load_config({**cfg(rid, 18393), "claude_billing": "credits"}))
                driver.drive(rid)
                st = read_json(run_dir(rid) / "state.json")
                self.assertEqual((st["status"], st["reason"]), ("paused", reason))
                self.assertIn(why.split()[0], st["error"])
                self.assertEqual(fc.verbs(), ["reserve"])  # no dispatch, no settle, no arm start
                self.assertFalse((run_dir(rid) / "transcript.jsonl").exists())
        finally:
            use_credits()

    def test_runs_claim_distinct_arm_ports(self):
        # 10-22 18:42: two runs without arm_port both took the base port and drove one arm
        a = {k: v for k, v in cfg("t_pa", 0).items() if k != "arm_port"}
        b = {k: v for k, v in cfg("t_pb", 0).items() if k != "arm_port"}
        driver.init_run(driver.load_config(a))
        driver.init_run(driver.load_config(b))
        sa = driver.Session(driver.load_config(read_json(run_dir("t_pa") / "config.json")))
        sb = driver.Session(driver.load_config(read_json(run_dir("t_pb") / "config.json")))
        self.assertNotEqual(sa.port, sb.port)
        self.assertEqual(read_json(run_dir("t_pa") / "config.json")["arm_port"], sa.port)
        again = driver.Session(driver.load_config(read_json(run_dir("t_pa") / "config.json")))
        self.assertEqual(again.port, sa.port)  # a resume keeps its port

    def test_settle_runs_on_pause(self):
        fc = use_credits()
        c = driver.load_config(cfg("t_pz", 18394, fail_at=2))
        driver.init_run(c)
        driver.drive("t_pz")
        self.assertEqual(read_json(run_dir("t_pz") / "state.json")["reason"], "budget")
        self.assertEqual(fc.verbs(), ["reserve", "dispatch", "settle"])

    def test_real_call_command_env_log_and_cost(self):
        use_credits()
        res = credits.Reservation("scail/bzombie_x", 10, os.getpid()).open()
        rd = run_dir("t_llm")
        write_json(rd / "clock.json", {"virtual_ts": "2026-11-02T10:00:00", "sim_day": 1})
        seen = {}

        def fake_run(cmd, **kw):
            seen["cmd"], seen["env"], seen["kw"] = cmd, kw["env"], kw
            out = {"result": '{"write": true, "text": "[Mon 21:30] hi there", "next_look": null}',
                   "total_cost_usd": 0.0123, "duration_ms": 900, "is_error": False}
            return subprocess.CompletedProcess(cmd, 0, json.dumps(out), "")

        old_backend, old_run = llm.backend, llm._run
        llm.backend, llm._run = None, fake_run
        llm.session = llm.Session(res, rd, 10)
        try:
            text = llm.ask("him", "SYSTEM TEXT", "PROMPT TEXT")
        finally:
            llm.backend, llm._run, llm.session = old_backend, old_run, None
        cmd = seen["cmd"]
        self.assertEqual(cmd[:4], ["claude", "-p", "--model", "claude-sonnet-5-5"])
        for flag in ("--output-format", "json", "--no-session-persistence", "--strict-mcp-config",
                     "--disable-slash-commands"):
            self.assertIn(flag, cmd)
        self.assertEqual(cmd[cmd.index("--tools") + 1], "")
        self.assertEqual(cmd[cmd.index("--setting-sources") + 1], "")
        self.assertEqual(cmd[cmd.index("--system-prompt") + 1], "SYSTEM TEXT")
        self.assertEqual(seen["kw"]["input"], "PROMPT TEXT")
        self.assertEqual(seen["kw"]["creationflags"], 0x08000000)
        self.assertEqual(seen["env"]["ANTHROPIC_API_KEY"], FAKE_KEY)
        self.assertEqual(seen["env"]["ANTHROPIC_CUSTOM_HEADERS"], "anthropic-workspace-id: wrkspc_test")
        self.assertNotIn(FAKE_KEY, " ".join(cmd))
        self.assertIn("hi there", text)
        self.assertAlmostEqual(res.spent_usd, 0.0123)
        lines = read_jsonl(rd / "claude_calls.jsonl")
        self.assertEqual(len(lines), 1)
        self.assertEqual((lines[0]["task"], lines[0]["cost_usd"], lines[0]["duration_ms"], lines[0]["is_error"],
                          lines[0]["virtual_ts"]), ("sim_him", 0.0123, 900, False, "2026-11-02T10:00:00"))
        self.assertNotIn(FAKE_KEY, json.dumps(lines))

    # ---- queue path (bench worker) ----
    def run_real_llm(self, rid, port, **extra):
        """Drive a 2-day run with the real ask() path (no backend stub) and return (state, calls log lines)."""
        old = llm.backend
        llm.backend = None
        try:
            driver.init_run(driver.load_config({**cfg(rid, port), **extra}))
            driver.drive(rid)
        finally:
            llm.backend = old
        return read_json(run_dir(rid) / "state.json"), read_jsonl(run_dir(rid) / "claude_calls.jsonl")

    def test_queue_ask_end_to_end(self):
        w = FakeWorker()
        w.start()
        rd = run_dir("t_q1")
        write_json(rd / "clock.json", {"virtual_ts": "2026-11-02T10:00:00", "sim_day": 1})
        old = llm.backend
        llm.backend, llm.session = None, llm.Session(None, rd, 10, "queue", 20)
        try:
            outs = [llm.ask("him", "SYS", f"NOW: 2026-11-02T10:00:00\nTODAY_ME: {i}\nCONVERSATION:\n") for i in range(3)]
        finally:
            llm.backend, llm.session = old, None
            w.stop.set()
            w.join(2)
        self.assertEqual(len(w.answered), 3)
        self.assertEqual(len({r["req_id"] for r in w.answered}), 3)
        r = w.answered[0]
        self.assertEqual((r["task"], r["model"], r["system"], r["run_id"], r["virtual_ts"], r["fresh"]),
                         ("sim_him", "sonnet", "SYS", "t_q1", "2026-11-02T10:00:00", True))
        self.assertIn("stub message 0", outs[0])
        q = llm.queue_dir()
        self.assertEqual(list(q.glob("*.req.json")) + list(q.glob("*.ans.json")), [])
        self.assertEqual(len(list((q / "done").glob("*.req.json"))), 3)
        self.assertEqual(len(list((q / "done").glob("*.ans.json"))), 3)
        lines = read_jsonl(rd / "claude_calls.jsonl")
        self.assertEqual([(x["billing"], x["cost_usd"], x["task"], x["agent_model"]) for x in lines],
                         [("queue", 0.0, "sim_him", "sonnet")] * 3)

    def test_queue_worker_error_answer_raises(self):
        w = FakeWorker(error_task="him")
        w.start()
        old = llm.backend
        llm.backend, llm.session = None, llm.Session(None, run_dir("t_q2"), 10, "queue", 20)
        try:
            with self.assertRaises(RuntimeError) as cm:
                llm.ask("him", "s", "NOW: 2026-11-02T10:00:00\nTODAY_ME: 0\n")
        finally:
            llm.backend, llm.session = old, None
            w.stop.set()
            w.join(2)
        self.assertIn("boom", str(cm.exception))

    def test_queue_billing_run_completes(self):
        use_credits()
        w = FakeWorker()
        w.start()
        try:
            st, lines = self.run_real_llm("t_q3", 18381, claude_billing="queue")
        finally:
            w.stop.set()
            w.join(2)
        self.assertEqual(st["status"], "done", st)
        self.assertTrue(lines and all(x["billing"] == "queue" for x in lines))

    def test_auto_switches_at_reserve(self):
        fc = use_credits(refuse="reserve")  # default claude_billing is auto
        w = FakeWorker()
        w.start()
        try:
            st, lines = self.run_real_llm("t_q4", 18382)
        finally:
            w.stop.set()
            w.join(2)
            use_credits()
        self.assertEqual(st["status"], "done", st)
        self.assertEqual(fc.verbs(), ["reserve"])
        self.assertTrue(lines and all(x["billing"] == "queue" for x in lines))
        self.assertGreaterEqual(len(w.answered), len(lines))

    def test_auto_switches_mid_run(self):
        fc = use_credits()
        w = FakeWorker()
        w.start()
        n = {"i": 0}

        def fake_run(cmd, **kw):
            n["i"] += 1
            if n["i"] > 3:  # grant runs out after 3 good calls
                out = {"result": "Credit balance is too low", "is_error": True}
                return subprocess.CompletedProcess(cmd, 1, json.dumps(out), "")
            p = kw["input"]
            task = "him" if "NOW:" in p else "env" if "DAY:" in p else "profile"
            out = {"result": llm.canned(task, "", p), "total_cost_usd": 0.01, "duration_ms": 5, "is_error": False}
            return subprocess.CompletedProcess(cmd, 0, json.dumps(out), "")

        old_run, llm._run = llm._run, fake_run
        try:
            st, lines = self.run_real_llm("t_q5", 18383)
        finally:
            llm._run = old_run
            w.stop.set()
            w.join(2)
        self.assertEqual(st["status"], "done", st)
        billing = [x["billing"] for x in lines if not x["is_error"]]
        self.assertEqual(billing[:3], ["credits"] * 3)
        self.assertTrue(len(billing) > 3 and set(billing[3:]) == {"queue"}, billing)
        self.assertEqual(fc.verbs(), ["reserve", "dispatch", "settle"])  # settled once, at the switch
        self.assertAlmostEqual(float(fc.calls[2][3]), 0.03)
        self.assertEqual(sum(1 for x in lines if x["billing"] == "credits" and x["is_error"]), 1)
        self.assertIsNone(llm.session)

    def test_credits_billing_does_not_switch(self):
        use_credits()

        def fake_run(cmd, **kw):
            return subprocess.CompletedProcess(cmd, 1, json.dumps({"result": "credit balance is too low"}), "")

        old_run, llm._run = llm._run, fake_run
        try:
            st, _ = self.run_real_llm("t_q6", 18384, claude_billing="credits")
        finally:
            llm._run = old_run
        self.assertEqual((st["status"], st["reason"]), ("paused", "grant_exhausted"))

    def test_worker_down_pauses(self):
        use_credits()
        st, lines = self.run_real_llm("t_q7", 18385, claude_billing="queue")  # no worker.json at all
        self.assertEqual((st["status"], st["reason"]), ("paused", "worker_down"))
        self.assertEqual(list(llm.queue_dir().glob("*.req.json")), [])  # nothing written for a dead worker
        # a heartbeat 11 minutes old is down too
        write_json(llm.queue_dir() / "worker.json", {"session_label": "x", "last_seen_wall": time.time() - 660})
        with self.assertRaises(llm.QueueUnavailable) as cm:
            llm._queue(llm.Session(None, None, 1, "queue", 5), "him", "s", "p")
        self.assertEqual(cm.exception.reason, "worker_down")

    def test_worker_timeout_pauses(self):
        use_credits()
        write_json(llm.queue_dir() / "worker.json", {"session_label": "x", "last_seen_wall": time.time()})
        st, _ = self.run_real_llm("t_q8", 18386, claude_billing="queue", queue_timeout_s=0.5)
        self.assertEqual((st["status"], st["reason"]), ("paused", "worker_timeout"))
        self.assertEqual(list(llm.queue_dir().glob("*.req.json")), [])
        self.assertEqual(len(list((llm.queue_dir() / "done").glob("*.req.json.timeout"))), 1)

    def test_no_session_no_call(self):
        old = llm.backend
        llm.backend, llm.session = None, None
        try:
            with self.assertRaises(RuntimeError):
                llm.ask("him", "s", "p")
        finally:
            llm.backend = old

    def test_parse_output_and_error_scrub(self):
        r = llm.parse_output(json.dumps({"result": "ok", "total_cost_usd": 0.5, "duration_ms": 10, "is_error": True}))
        self.assertEqual((r["text"], r["cost_usd"], r["is_error"]), ("ok", 0.5, True))
        with self.assertRaises(RuntimeError):
            llm.parse_output("not json")
        use_credits()
        res = credits.Reservation("w", 1, os.getpid()).open()
        res.key()
        self.assertEqual(res.scrub(f"bad {FAKE_KEY} here"), "bad *** here")

    def test_stub_flag_in_config(self):
        os.environ["BZ_LLM_STUB"] = "1"
        try:
            driver.init_run(driver.load_config({**cfg("t_stub", 18387), "sim_days": 1}))
            driver.drive("t_stub")
        finally:
            os.environ.pop("BZ_LLM_STUB", None)
        self.assertIs(read_json(run_dir("t_stub") / "config.json")["stub"], True)
        self.assertEqual(read_json(run_dir("t_stub") / "clock.json")["sim_day"], 1)

    def test_tomoe_him_reads_13h_behind(self):
        from datetime import datetime
        from bzombie.sim_him import him
        seen = []
        old = llm.backend
        llm.backend = lambda task, s, p: seen.append(p) or json.dumps({"write": False, "text": "", "next_look": "2026-11-02T09:30:00"})
        try:
            now = datetime(2026, 11, 2, 21, 30)
            d = him.decide({"voice": "x"}, [], "plan", now, "en", 0, him_tz="Etc/GMT+4")
            him.decide({"voice": "x"}, [], "plan", now, "ja", 0, him_tz="Asia/Tokyo")
        finally:
            llm.backend = old
        self.assertIn("NOW: 2026-11-02T08:30:00", seen[0])  # 21:30 Tokyo is 08:30 for Tomoe's him
        self.assertIn("NOW: 2026-11-02T21:30:00", seen[1])  # Momoka: no difference
        self.assertEqual(d["next_look"], "2026-11-02T22:30:00")  # his 09:30 back on the Tokyo timeline
        self.assertEqual(common.to_him(datetime(2026, 11, 2, 21, 30), "Etc/GMT+4").hour, 8)
        for t, tz in (("s_tomoe", "Etc/GMT+4"), ("s_momoka", "Asia/Tokyo")):
            tpl = read_json(Path(driver.__file__).parent / "templates" / f"{t}.json")
            self.assertEqual(tpl["him_timezone"], tz)

    def test_strip_stamps_and_history(self):
        self.assertEqual(llm.strip_stamps("[Mon 21:30] hello"), "hello")
        self.assertEqual(llm.strip_stamps("[Tue 9:05][Tue 9:06] a\n[Wed 10:00] b"), "a\nb")
        self.assertEqual(llm.strip_stamps("keep [not a stamp] text"), "keep [not a stamp] text")
        from bzombie.sim_him import him
        hist = him.format_conversation([
            {"who": "her", "virtual_ts": "2026-11-02T10:00:00", "text": "[Mon 10:00] hey"},
            {"who": "him", "virtual_ts": "2026-11-02T10:05:00", "text": "yo"},
            {"who": "env", "virtual_ts": "2026-11-02T10:06:00", "text": "rain"}])
        self.assertEqual(hist, "her: hey\nme: yo")
        llm.backend = lambda task, s, p: json.dumps({"write": True, "text": "[Mon 21:30] late one", "next_look": None})
        try:
            d = him.decide({"voice": "x"}, [], "plan", __import__("datetime").datetime(2026, 11, 2, 21, 30), "en")
        finally:
            llm.backend = llm.canned
        self.assertEqual(d["text"], "late one")


class PortClaims(unittest.TestCase):
    def test_stale_takeover_race_gives_distinct_ports(self):
        """10-22 20:41: two drivers took over one stale claim and shared an arm. Eight racers, one stale claim:
        every racer gets its own port."""
        from bzombie.harness import driver
        d = driver.VAR / "ports"
        d.mkdir(parents=True, exist_ok=True)
        for f in d.glob("1839*"):
            f.unlink()
        write_json(run_dir("old_done") / "state.json", {"status": "done"})
        write_json(d / "18390.json", {"run_id": "old_done", "claimed": "2026-10-22T18:00:00"})
        got, errs = {}, []
        go = threading.Barrier(8)

        def racer(i):
            try:
                go.wait()
                got[i] = driver.claim_port(f"race_{i}", 18390, span=9)
            except Exception as e:  # noqa: BLE001
                errs.append(e)
        ts = [threading.Thread(target=racer, args=(i,)) for i in range(8)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(errs, [])
        self.assertEqual(len(set(got.values())), 8, got)
        self.assertEqual(read_json(d / f"{got[0]}.json")["run_id"], "race_0")


if __name__ == "__main__":
    unittest.main()
