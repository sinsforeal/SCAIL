"""Fixed-script mode for simulated him (tk-mz5), on the stub arm. No spend, no claude, no limits ticket.
Arm ports 18361-18364 only (18331-18339 are live runs)."""
import os
import sys
import tempfile
import unittest

from unittest import mock

# Import-time state: only BZ_VAR, because bzombie.common pins VAR at its first import. First module in the process:
# a fresh temp VAR. Later: keep the env (the stub arms inherit it) in line with the pinned VAR.
# BZ_LLM_STUB and every monkeypatch are scoped to this class in setUpClass and undone by addClassCleanup.
if "bzombie.common" in sys.modules:
    os.environ["BZ_VAR"] = str(sys.modules["bzombie.common"].VAR)
else:
    os.environ["BZ_VAR"] = tempfile.mkdtemp(prefix="bzs_", dir=r"F:\temp" if os.path.isdir(r"F:\temp") else None)
_tmp = os.environ["BZ_VAR"]

from bzombie import llm  # noqa: E402
from bzombie.common import append_jsonl, read_json, read_jsonl, run_dir, write_json  # noqa: E402
from bzombie.harness import branch, cli, driver, script  # noqa: E402
from bzombie.harness.armclient import Arm  # noqa: E402
from bzombie.sim_him import him  # noqa: E402
from tests.bz_safety import refuse_live_var  # noqa: E402

refuse_live_var(sys.modules["bzombie.common"].VAR)  # this module writes runs, his.jsonl and scripts into VAR


def cfg(run_id, port, **kw):
    cmd = [sys.executable, "-m", "bzombie.harness.stub_arm", "--port", "{port}", "--arm", "{arm}"]
    c = {"run_id": run_id, "arm": "S", "character": "tomoe", "lang": "en", "model": "stub", "cap_usd": 1,
         "sim_days": 2, "clock_start": "2026-11-02T00:00:00", "seed": 7, "use_limits": False,
         "arm_port": port, "arm_cmd": cmd, "step_s": 3600}
    c.update(kw)
    return c


def make_ref(run_id, lines, character="tomoe", sim_days=2):
    """A finished reference run, written by hand: config.json plus a transcript with his lines (and a her line)."""
    rd = run_dir(run_id)
    rd.mkdir(parents=True, exist_ok=True)
    write_json(rd / "config.json", cfg(run_id, 1, character=character, sim_days=sim_days))
    for ts, text in lines:
        append_jsonl(rd / "transcript.jsonl", {"virtual_ts": ts, "who": "him", "text": text})
        append_jsonl(rd / "transcript.jsonl", {"virtual_ts": ts, "who": "her", "text": "ignored"})


def his(tr):
    return [(e["virtual_ts"], e["text"]) for e in tr if e["who"] == "him"]


REF = [("2026-11-02T09:15:00", "morning, you up?"), ("2026-11-02T09:15:05", "second line, 5 s later"),
       ("2026-11-03T08:00:00", "day two first"), ("2026-11-03T08:10:00", "day two, ten minutes on"),
       ("2026-11-03T22:00:00", "late one"), ("2026-11-04T10:00:00", "day three, past sim_days")]


class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def no_model(*a, **k):
            raise AssertionError("sim-him model called in script mode")
        cls.addClassCleanup(cls._stop_arms)
        for p in (mock.patch.dict(os.environ, {"BZ_LLM_STUB": "1"}),  # canned env script, no credits
                  mock.patch.object(him, "decide", no_model),
                  mock.patch.object(branch, "free_port", lambda base, span=9: 18363),
                  mock.patch.object(llm, "backend", None)):  # a harness module may have set the canned backend
            p.start()
            cls.addClassCleanup(p.stop)

    @staticmethod
    def _stop_arms():
        for p in (18361, 18362, 18363, 18364):
            try:
                Arm(p).stop()
            except Exception:
                pass

    def test_lines_verbatim_at_ts_no_model_then_branch_uses_parent_lines(self):
        make_ref("ref1", REF)
        driver.init_run(driver.load_config(cfg("sc1", 18361, him_via="script", him_script="ref1")))
        driver.drive("sc1")
        st = read_json(run_dir("sc1") / "state.json")
        self.assertEqual(st["status"], "done", st)
        tr = read_jsonl(run_dir("sc1") / "transcript.jsonl")
        # sim_days 2: the day-three line is not sent; the rest arrive verbatim at their own ts
        self.assertEqual(his(tr), [(t, x) for t, x in REF if t < "2026-11-04"])
        # the arm got them at their ts: its replies come 20 s after, even for the 5 s apart pair
        replies = [(e["virtual_ts"], e["text"]) for e in tr if e["who"] == "her" and e["kind"] == "reply"]
        self.assertIn(("2026-11-02T09:15:20", "stub reply to: morning, you up?"), replies)
        self.assertIn(("2026-11-02T09:15:25", "stub reply to: second line, 5 s later"), replies)
        self.assertFalse(st.get("script_ended"))
        calls = read_jsonl(run_dir("sc1") / "calls.jsonl")
        self.assertFalse([c for c in calls if c.get("arm") == "X"], "no sim-him gateway call")
        # branch at day1_end: default script = the parent run's own lines after the snapshot
        bid = branch.branch("sc1", "day1_end", "mute", True)
        bd = run_dir("sc1") / "branches" / bid
        meta = read_json(bd / "branch.json")
        self.assertEqual((meta["him_via"], meta["him_script"]), ("script", "sc1"))
        base_len = read_json(run_dir("sc1") / "snapshots" / "harness" / "day1_end.json")["transcript_len"]
        new = read_jsonl(bd / "transcript.jsonl")[base_len:]
        # first line at 08:00 plus the 08:10 line inside the 30 min window; the 22:00 one is out
        self.assertEqual(his(new), [(t, x) for t, x in REF[2:4]])
        self.assertFalse([e for e in new if e["who"] == "her"], "muted branch must not reply")
        # identical to what the base saw in the same span
        self.assertEqual(his(new), [h for h in his(tr) if "2026-11-03T08:00" <= h[0] <= "2026-11-03T08:40"])

    def test_reference_with_fewer_days_logs_once(self):
        make_ref("ref2", REF[:2], sim_days=1)
        driver.init_run(driver.load_config(cfg("sc2", 18362, him_via="script", him_script="ref2")))
        driver.drive("sc2")
        st = read_json(run_dir("sc2") / "state.json")
        self.assertEqual(st["status"], "done", st)
        self.assertIn("2026-11-02T09:15:05", st["script_ended"])
        self.assertTrue(st["script_ended"].startswith("day 2"))
        self.assertEqual(his(read_jsonl(run_dir("sc2") / "transcript.jsonl")), REF[:2])

    def test_character_mismatch_refused_at_load(self):
        make_ref("ref_momoka", REF[:2], character="momoka")
        with self.assertRaises(script.ScriptError):
            driver.load_config(cfg("sc3", 18364, him_via="script", him_script="ref_momoka"))
        with self.assertRaises(script.ScriptError):
            driver.load_config(cfg("sc3", 18364, him_via="script"))  # no him_script
        with self.assertRaises(script.ScriptError):
            driver.load_config(cfg("sc3", 18364, him_via="script", him_script="no_such_run"))

    def test_jsonl_path_source(self):
        p = os.path.join(_tmp, "his.jsonl")
        for ts, text in REF[:2]:
            append_jsonl(p, {"virtual_ts": ts, "text": text})  # no "who": taken as his
        got = script.load(p, "tomoe")
        self.assertEqual([(l["virtual_ts"], l["text"]) for l in got["lines"]], REF[:2])
        self.assertIsNone(got["ref_run"])

    def test_like_config(self):
        make_ref("ref4", REF[:2])
        write_json(run_dir("ref4") / "config.json", {**cfg("ref4", 18361), "status": "done", "arm_port": 18361,
                                                      "arm_cmd": ["py", "-m", "x", "--s-root", "OLD", "--port", "{port}"]})
        c = cli.like_config("ref4", "new4", s_root="F:\\wt_x", seed="9", script_from="ref4")
        self.assertEqual(c["arm_cmd"], ["py", "-m", "x", "--s-root", "F:\\wt_x", "--port", "{port}"])
        self.assertEqual((c["seed"], c["him_via"], c["him_script"], c["run_id"]), (9, "script", "ref4", "new4"))
        self.assertNotIn("status", c)
        self.assertNotIn("arm_port", c)
        driver.load_config(c)  # accepted


if __name__ == "__main__":
    unittest.main()
