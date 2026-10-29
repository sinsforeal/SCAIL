"""Removal tests (tk-lmv): arm inject targets, the batch planner, the branch flags, the summary. Stub arm only, no
spend, no claude, no limits ticket. Arm port 18364 only (18331-18339 are live runs)."""
import json
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

if "bzombie.common" in sys.modules:
    os.environ["BZ_VAR"] = str(sys.modules["bzombie.common"].VAR)
else:
    os.environ["BZ_VAR"] = tempfile.mkdtemp(prefix="bzr_", dir=r"F:\temp" if os.path.isdir(r"F:\temp") else None)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "bzombie", "arms", "s"))
sys.path.insert(0, ROOT)

import control  # noqa: E402
from bzombie import llm  # noqa: E402
from bzombie.common import append_jsonl, read_json, read_jsonl, run_dir, write_json  # noqa: E402
from bzombie.harness import branch, cli, driver, removal_batch as rb, removal_summary as rs  # noqa: E402
from bzombie.harness import removal_targets as rt  # noqa: E402
from bzombie.harness.armclient import Arm  # noqa: E402
from bzombie.sim_him import him  # noqa: E402


def fake_app():
    return SimpleNamespace(config=SimpleNamespace(
        foresight=SimpleNamespace(enabled=True), primitives=SimpleNamespace(enabled=True),
        bz_s10=SimpleNamespace(budget=True, repeat_check=True), persona=SimpleNamespace(name="x")))


class ControlTargets(unittest.TestCase):
    def test_section_flag(self):
        app = fake_app()
        self.assertEqual(control.apply_inject(app, "section.foresight", False), ("foresight", "enabled"))
        self.assertFalse(app.config.foresight.enabled)
        control.apply_inject(app, "section.foresight", True)
        self.assertTrue(app.config.foresight.enabled)

    def test_bz_s10_key(self):
        app = fake_app()
        self.assertEqual(control.apply_inject(app, "bz_s10.budget", False), ("bz_s10", "budget"))
        self.assertFalse(app.config.bz_s10.budget)
        self.assertTrue(app.config.bz_s10.repeat_check)

    def test_noop_changes_nothing(self):
        app = fake_app()
        before = json.dumps(app.config, default=lambda o: vars(o), sort_keys=True)
        self.assertIsNone(control.apply_inject(app, "noop", True))
        self.assertEqual(before, json.dumps(app.config, default=lambda o: vars(o), sort_keys=True))

    def test_unknown_and_wrong_value(self):
        app = fake_app()
        with self.assertRaises(KeyError):
            control.apply_inject(app, "section.nothing_here", False)
        with self.assertRaises(KeyError):
            control.apply_inject(app, "section.persona", False)  # no `enabled` on it
        with self.assertRaises(KeyError):
            control.apply_inject(app, "bz_s10.nope", False)
        with self.assertRaises(ValueError):
            control.apply_inject(app, "section.foresight", "no")
        with self.assertRaises(ValueError):
            control.apply_inject(app, "bz_s10.budget", 0)

    def test_write_overrides(self):
        p = os.path.join(os.environ["BZ_VAR"], "cfg_override.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"foresight": {"enabled": True, "n": 3}, "keep": 1}, f)
        control.write_overrides(p, {("foresight", "enabled"): False, ("bz_s10", "budget"): False})
        d = json.load(open(p, encoding="utf-8"))
        self.assertEqual(d["foresight"], {"enabled": False, "n": 3})
        self.assertEqual(d["bz_s10"], {"budget": False})
        self.assertEqual(d["keep"], 1)
        control.write_overrides(p, {})  # nothing recorded: file untouched
        self.assertEqual(json.load(open(p, encoding="utf-8")), d)

    def test_targets_table_matches_arm(self):
        for t in rt.TARGETS:
            self.assertIsNotNone(control.removal_key(t["target"]), t["name"])
        self.assertEqual(len({t["name"] for t in rt.TARGETS}), len(rt.TARGETS))
        self.assertFalse(set(t["name"] for t in rt.TARGETS) & set(rt.DROPPED))
        boot = {control.removal_key(t["target"]) for t in rt.TARGETS if t["boot"]}
        self.assertEqual(boot, control.BOOT_ONLY)


class Planner(unittest.TestCase):
    def test_default_plan(self):
        items = rb.plan()
        n_t = len(rt.TARGETS)
        self.assertEqual(len(items), 3 * 2 * (n_t + 2))
        self.assertEqual(len({(i["base"], i["bid"]) for i in items}), len(items), "branch ids collide")
        for b in rb.BASES:
            for s in rb.SNAPSHOTS:
                cell = [i for i in items if i["base"] == b and i["snapshot"] == s]
                noops = [i for i in cell if i["target"] == "noop"]
                self.assertEqual(sorted(i["tag"] for i in noops), ["r1", "r2"])
                self.assertEqual(len({i["bid"] for i in noops}), 2)
                self.assertEqual(len(cell) - 2, n_t)
        self.assertTrue(all(i["value"] is False for i in items if i["target"] != "noop"))

    def test_resume_skips_finished_only(self):
        items = rb.plan(["rb_base"], ["day1_end"], noops=1)
        self.assertEqual(len(rb.pending(items)), len(items))
        a, b = items[0], items[1]
        write_json(run_dir("rb_base") / "branches" / a["bid"] / "branch.json", {"finished": True})
        write_json(run_dir("rb_base") / "branches" / b["bid"] / "branch.json", {"target": b["target"]})  # crashed
        left = rb.pending(items)
        self.assertEqual(len(left), len(items) - 1)
        self.assertNotIn(a["bid"], [i["bid"] for i in left])
        self.assertIn(b["bid"], [i["bid"] for i in left])

    def test_cmd_args(self):
        i = rb.plan(["gr_b_s5_momoka"], ["day1_end"], noops=1)[-1]
        c = rb.cmd_args(i, 6, 30, "F:/x")
        self.assertEqual(c[c.index("branch") + 1:c.index("branch") + 5], ["gr_b_s5_momoka", "day1_end", "noop", "true"])
        self.assertEqual(c[c.index("--tag") + 1], "r1")
        self.assertEqual(c[c.index("--s-root") + 1], "F:/x")
        self.assertEqual(c[c.index("--n-msgs") + 1], "6")

    def test_only_and_dry(self):
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf), mock.patch.object(rb, "estimate", lambda *a, **k: {
                "branches": 0, "windows": {}, "chat_calls": 0, "embed_calls": 0, "cost_usd": 0, "wall_h": 0,
                "wall_h_serial": 0, "note": "n"}), mock.patch.object(rb, "run", side_effect=AssertionError("ran")):
            rb.main(["--dry", "--only", "foresight,recall", "--bases", "a,b", "--snapshots", "day1_end"])
        out = buf.getvalue()
        self.assertIn("plan: 8 branches", out)  # 2 bases x 1 snapshot x (2 targets + 2 noop)
        self.assertIn("targets: foresight, recall, noop x2", out)

    def test_s_root_swap(self):
        cfg = {"arm_cmd": ["py", "-m", "x", "--s-root", "F:/old", "--port", "{port}"]}
        out = branch.swap_s_root(cfg, "F:/new")
        self.assertEqual(out["arm_cmd"][4], "F:/new")
        self.assertEqual(cfg["arm_cmd"][4], "F:/old", "base config must stay as it was")
        self.assertIs(branch.swap_s_root(cfg, None), cfg)
        with self.assertRaises(ValueError):
            branch.swap_s_root({"arm_cmd": ["py"]}, "F:/new")


REF = [("2026-11-02T09:15:00", "morning, you up?"), ("2026-11-03T08:00:00", "day two first"),
       ("2026-11-03T08:10:00", "day two, ten minutes on"), ("2026-11-03T22:00:00", "late one")]


def cfg(run_id, port, **kw):
    cmd = [sys.executable, "-m", "bzombie.harness.stub_arm", "--port", "{port}", "--arm", "{arm}"]
    c = {"run_id": run_id, "arm": "S", "character": "tomoe", "lang": "en", "model": "stub", "cap_usd": 1,
         "sim_days": 2, "clock_start": "2026-11-02T00:00:00", "seed": 7, "use_limits": False,
         "arm_port": port, "arm_cmd": cmd, "step_s": 3600}
    c.update(kw)
    return c


BID_R1 = branch.branch_id("day1_end", "noop", True, "r1")
BID_R2 = branch.branch_id("day1_end", "noop", True, "r2")
BID_F = branch.branch_id("day1_end", "section.foresight", False)


class OnStub(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def no_model(*a, **k):
            raise AssertionError("sim-him model called in script mode")
        cls.addClassCleanup(cls._stop_arms)
        for p in (mock.patch.dict(os.environ, {"BZ_LLM_STUB": "1"}),
                  mock.patch.object(him, "decide", no_model),
                  mock.patch.object(branch, "free_port", lambda base, span=9: 18364),
                  mock.patch.object(llm, "backend", None)):
            p.start()
            cls.addClassCleanup(p.stop)
        rd = run_dir("rm_ref")
        rd.mkdir(parents=True, exist_ok=True)
        write_json(rd / "config.json", cfg("rm_ref", 1))
        for ts, text in REF:
            append_jsonl(rd / "transcript.jsonl", {"virtual_ts": ts, "who": "him", "text": text})
        driver.init_run(driver.load_config(cfg("rm_base", 18364, him_via="script", him_script="rm_ref")))
        driver.drive("rm_base")
        assert read_json(run_dir("rm_base") / "state.json")["status"] == "done"

    @staticmethod
    def _stop_arms():
        try:
            Arm(18364).stop()
        except Exception:
            pass

    def test_flags_replicates_finished_and_partial(self):
        # CLI flags: --n-msgs 1 (his first line after the snapshot, then 30 min: two lines), --tag, --window-min
        cli.cmd_branch(["rm_base", "day1_end", "noop", "true", "--n-msgs", "1", "--tag", "r1"])
        cli.cmd_branch(["rm_base", "day1_end", "noop", "true", "--n-msgs", "1", "--tag", "r2"])
        bd = run_dir("rm_base") / "branches"
        m1, m2 = read_json(bd / BID_R1 / "branch.json"), read_json(bd / BID_R2 / "branch.json")
        for m in (m1, m2):
            self.assertTrue(m["finished"])
            self.assertEqual((m["n_msgs"], m["window_min"], m["target"]), (1, 30, "noop"))
        self.assertEqual((m1["tag"], m2["tag"]), ("r1", "r2"))
        self.assertTrue(branch.is_finished("rm_base", BID_R1))
        base_len = read_json(run_dir("rm_base") / "snapshots" / "harness" / "day1_end.json")["transcript_len"]
        new = read_jsonl(bd / BID_R1 / "transcript.jsonl")[base_len:]
        self.assertEqual([e["text"] for e in new if e["who"] == "him"], ["day two first", "day two, ten minutes on"])
        # --n-msgs 2 reaches the second line, so the window runs to 08:40 and the 22:00 line stays out
        cli.cmd_branch(["rm_base", "day1_end", "section.foresight", "false", "--n-msgs", "2", "--window-min", "5"])
        n2 = read_jsonl(bd / BID_F / "transcript.jsonl")[base_len:]
        self.assertEqual([e["text"] for e in n2 if e["who"] == "him"], ["day two first", "day two, ten minutes on"])
        # finished branch: a second run refuses; a crashed one (no mark) is parked and rerun
        with self.assertRaises(ValueError):
            branch.branch("rm_base", "day1_end", "noop", True, tag="r1")
        write_json(bd / BID_R2 / "branch.json", {"branch_id": "x", "target": "noop"})
        branch.branch("rm_base", "day1_end", "noop", True, tag="r2")
        self.assertTrue(branch.is_finished("rm_base", BID_R2))
        self.assertEqual(len([p for p in bd.iterdir() if p.name.startswith("_partial_" + BID_R2)]), 1)

    def test_stub_inject_answers_removed(self):
        a = Arm(18364)
        import subprocess
        p = subprocess.Popen([sys.executable, "-m", "bzombie.harness.stub_arm", "--port", "18364", "--arm", "S"],
                             creationflags=0x08000000 if os.name == "nt" else 0)
        try:
            import time
            for _ in range(50):
                try:
                    a.state()
                    break
                except Exception:
                    time.sleep(0.1)
            self.assertEqual(a.inject("noop", True).get("removed"), [])
            self.assertEqual(a.inject("section.foresight", False).get("removed"), ["section.foresight"])
        finally:
            try:
                a.stop()
            except Exception:
                pass
            p.wait(timeout=10)

    def test_window_and_estimate_from_base(self):
        w = rb.window("rm_base", "day1_end", 1, 30)
        self.assertEqual((w[0].isoformat(), w[1].isoformat()), ("2026-11-03T00:00:00", "2026-11-03T08:30:00"))
        self.assertIsNone(rb.window("rm_base", "day1_end", 1, 30) is None or None)
        e = rb.estimate(rb.plan(["rm_base"], ["day1_end"], noops=2), 1, 30, 2)
        self.assertEqual(e["branches"], len(rt.TARGETS) + 2)
        self.assertAlmostEqual(e["wall_h"] * 2, e["wall_h_serial"], delta=0.11)

    def test_summary_mechanical(self):
        for t in ("noop",):
            pass
        cli.cmd_branch(["rm_base", "day1_end", "noop", "true", "--n-msgs", "1", "--tag", "r1"]) if not branch.is_finished(
            "rm_base", BID_R1) else None
        targets = [{"name": "foresight", "target": "section.foresight", "roles": ["foresee"], "why": "t"}]
        if not branch.is_finished("rm_base", BID_F):
            cli.cmd_branch(["rm_base", "day1_end", "section.foresight", "false", "--n-msgs", "1"])
        if not branch.is_finished("rm_base", BID_R2):
            cli.cmd_branch(["rm_base", "day1_end", "noop", "true", "--n-msgs", "1", "--tag", "r2"])
        c = rs.cell_report("rm_base", "day1_end", targets, 1, 30)
        self.assertEqual(c["floor"], 0.0)
        row = c["targets"]["foresight"]
        self.assertEqual(row["d_noop"], [0.0, 0.0])
        self.assertIs(row["changed"], False)  # identical to the noops: not above the floor
        self.assertEqual(row["roles_removed"], {"foresee": [0, [0, 0]]})
        bw = run_dir("rm_base") / "branches" / "basewin_day1_end"
        self.assertTrue(read_json(bw / "branch.json")["finished"])
        self.assertEqual(read_json(bw / "branch.json")["replayed_from_virtual_ts"], "2026-11-03T00:00:00")
        self.assertTrue(all("2026-11-03" in r["virtual_ts"] for r in read_jsonl(bw / "transcript.jsonl")))

    def test_summary_changed_logic_and_render(self):
        texts = {"base": "a\nb", "noop_r1": "a\nb", "noop_r2": "a\nb", "t": "zzzz\nyyyy"}

        def fake_mech(base, bid, cursor):
            k = "t" if "foresight" in bid else "noop_r1" if bid.endswith("r1") else "noop_r2" if bid.endswith("r2") else "base"
            return {"her_lines": 2, "her_chars": 3, "unprompted": 0, "text": texts[k], "chat_calls": 5,
                    "prompt_tokens": 10, "cost_micro": 1, "roles": {"foresee": 0 if k == "t" else 2}}
        targets = [{"name": "foresight", "target": "section.foresight", "roles": ["foresee"], "why": "t"}]
        with mock.patch.object(rs, "mech", fake_mech), mock.patch.object(branch, "is_finished", lambda r, b: True):
            rep = rs.build(["rm_base"], ["day1_end"], targets, 1, 30, "both")
            t = rep["targets"]["foresight"]
            self.assertTrue(t["changed"])
            self.assertEqual((t["cells_changed"], t["cells_with_data"]), (1, 1))
            self.assertEqual(rep["floors"][0]["floor"], 0.0)
            md = rs.render_md(rep)
        self.assertIn("## foresight (section.foresight): changed beyond noop", md)
        self.assertIn("Drift floor per cell", md)

    def test_judge_pairs(self):
        targets = rt.TARGETS[:2]
        both = rs.judge_pairs("b", "day1_end", targets, "both")
        self.assertEqual(len(both), 2 + 2 * 2)  # floor + noop v base + (v noop, v base) per target
        self.assertEqual(len(rs.judge_pairs("b", "day1_end", targets, "noop")), 1 + 2)
        self.assertEqual(len({p["match_id"] for p in both}), len(both))
        self.assertTrue(all("~" not in p["a"] for p in both))


if __name__ == "__main__":
    unittest.main()
