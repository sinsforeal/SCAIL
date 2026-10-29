"""Steer tests (tk-6si): the gauge pin, the batch planner, the variant flag, the summary and its scoring. Stub arm and
fake judge results only: no spend, no claude, no limits ticket. Arm port 18366 only (18331-18339 are live runs)."""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from types import SimpleNamespace
from unittest import mock

if "bzombie.common" in sys.modules:
    os.environ["BZ_VAR"] = str(sys.modules["bzombie.common"].VAR)
else:
    os.environ["BZ_VAR"] = tempfile.mkdtemp(prefix="bzi_", dir=r"F:\temp" if os.path.isdir(r"F:\temp") else None)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "bzombie", "arms", "s"))
sys.path.insert(0, ROOT)

import control  # noqa: E402
from bzombie import llm  # noqa: E402
from bzombie.common import VAR, append_jsonl, read_json, run_dir, write_json  # noqa: E402
from bzombie.harness import branch, cli, driver, inject_batch as ib, inject_summary as isum  # noqa: E402
from bzombie.harness import inject_targets as it, removal_batch as rb, removal_summary as rs  # noqa: E402
from bzombie.harness.armclient import Arm  # noqa: E402
from bzombie.judge import runner, steer  # noqa: E402
from bzombie.sim_him import him  # noqa: E402

PORT = 18366


class FakeState:
    def __init__(self):
        self.gauges = {"loneliness": 35.0, "energy": 60.0, "mood": 50.0}

    def set_value(self, name, v):
        if name == "mood":
            return "mood is derived"
        if name not in self.gauges:
            return f"unknown gauge {name}"
        self.gauges[name] = float(v)
        return None


class Pin(unittest.TestCase):
    def test_pin_holds_against_every_writer(self):
        app = SimpleNamespace(state=FakeState())
        control.apply_inject(app, "hold.loneliness", 90)
        g = app.state.gauges
        self.assertIsInstance(g, control.PinnedGauges)
        self.assertEqual(g["loneliness"], 90.0)
        g["loneliness"] = 10            # decay
        self.assertEqual(g["loneliness"], 90.0)
        g.update({"loneliness": 1, "energy": 5})   # a bulk write: pinned key kept, the other lands
        self.assertEqual((g["loneliness"], g["energy"]), (90.0, 5))
        g["energy"] = 7                 # an unpinned key moves freely
        self.assertEqual(g["energy"], 7)
        self.assertEqual(g.pins, {"loneliness": 90.0})
        self.assertIs(app.state.gauges, g, "a second hold must reuse the pinned dict")

    def test_release_and_repin(self):
        app = SimpleNamespace(state=FakeState())
        control.apply_inject(app, "hold.loneliness", 90)
        control.apply_inject(app, "hold.loneliness", None)
        self.assertEqual(app.state.gauges.pins, {})
        app.state.gauges["loneliness"] = 5
        self.assertEqual(app.state.gauges["loneliness"], 5)
        control.apply_inject(app, "hold.loneliness", 90)
        control.apply_inject(app, "hold.loneliness", 20)   # a new value on a pinned gauge lands
        self.assertEqual(app.state.gauges["loneliness"], 20.0)
        app.state.gauges["loneliness"] = 99
        self.assertEqual(app.state.gauges["loneliness"], 20.0)

    def test_release_without_pin_and_refusals(self):
        app = SimpleNamespace(state=FakeState())
        self.assertIsNone(control.apply_inject(app, "hold.loneliness", None))   # nothing pinned: no error
        with self.assertRaises(ValueError):
            control.apply_inject(app, "hold.mood", 80)       # derived
        with self.assertRaises(ValueError):
            control.apply_inject(app, "hold.nothing", 80)    # unknown
        self.assertNotIsInstance(app.state.gauges, control.PinnedGauges)

    def test_noop_and_plain_gauge_untouched(self):
        app = SimpleNamespace(state=FakeState())
        self.assertIsNone(control.apply_inject(app, "noop", True))
        self.assertEqual(app.state.gauges, {"loneliness": 35.0, "energy": 60.0, "mood": 50.0})
        self.assertNotIsInstance(app.state.gauges, control.PinnedGauges)


class Tag(unittest.TestCase):
    def test_full_tag(self):
        self.assertEqual(branch.full_tag(), "")
        self.assertEqual(branch.full_tag((), "r1"), "r1")
        self.assertEqual(branch.full_tag(("order",), ""), "order")
        self.assertEqual(branch.full_tag(("order", "trend"), "r2"), "order+trend_r2")
        self.assertNotEqual(branch.branch_id("s", "noop", True, branch.full_tag(("order",), "r1")),
                            branch.branch_id("s", "noop", True, "r1"))


class Planner(unittest.TestCase):
    def test_default_plan(self):
        items = ib.plan()
        self.assertEqual(len(items), 3 * 2 * (len(it.TARGETS) + 2))
        self.assertEqual(len(items), 48)
        self.assertEqual(len({(i["base"], i["bid"]) for i in items}), 48, "branch ids collide")
        for b in ib.BASES:
            for s in ib.SNAPSHOTS:
                cell = [i for i in items if i["base"] == b and i["snapshot"] == s]
                self.assertEqual([i["name"] for i in cell if i["name"] != "noop"], [t["name"] for t in it.TARGETS])
                self.assertEqual(sorted(i["tag"] for i in cell if i["name"] == "noop"), ["r1", "r2"])
        i0 = items[0]
        self.assertEqual(i0["bid"], branch.branch_id("day1_end", "hold.loneliness", 90))
        self.assertEqual(i0["bid"], "day1-end_hold-loneliness_90")
        self.assertEqual((i0["direction"], i0["expect"], i0["variants"]), ("lonely", "more", []))
        self.assertTrue(all(isinstance(i["value"], int) for i in items if i["name"] != "noop"))

    def test_variant_passthrough(self):
        items = ib.plan(["b"], ["day1_end"], [it.TARGETS[0]], 1, ("order",))
        t, n = items
        self.assertEqual(t["variants"], ["order"])
        self.assertEqual(t["bid"], branch.branch_id("day1_end", "hold.loneliness", 90, "order"))
        self.assertEqual(n["bid"], branch.branch_id("day1_end", "noop", True, branch.full_tag(("order",), "r1")))
        ct = ib.cmd_args(t, 6, 30, "F:/x")
        self.assertEqual(ct[ct.index("branch") + 1:ct.index("branch") + 5], ["b", "day1_end", "hold.loneliness", "90"])
        self.assertEqual(ct[ct.index("--variant") + 1], "order")
        self.assertNotIn("--tag", ct)
        self.assertEqual(ct[ct.index("--s-root") + 1], "F:/x")
        cn = ib.cmd_args(n, 6, 30, "F:/x")
        self.assertEqual((cn[cn.index("--tag") + 1], cn[cn.index("--variant") + 1]), ("r1", "order"))
        plain = ib.cmd_args(ib.plan(["b"], ["day1_end"], [it.TARGETS[0]], 0)[0], 6, 30, "F:/x")
        self.assertNotIn("--variant", plain)
        self.assertEqual(plain[plain.index("--n-msgs") + 1], "6")

    def test_only_extras_and_resume(self):
        items = ib.plan(["b"], ["day1_end"], [it.BY_NAME["loneliness"], it.BY_NAME["loneliness_low"]], 0)
        self.assertEqual(len({i["bid"] for i in items}), 2, "the reverse pin of one gauge has its own id")
        self.assertEqual(items[1]["expect"], "less")
        items = ib.plan(["inj_resume"], ["day1_end"], noops=1)
        self.assertEqual(len(ib.pending(items)), len(items))
        write_json(run_dir("inj_resume") / "branches" / items[0]["bid"] / "branch.json", {"finished": True})
        write_json(run_dir("inj_resume") / "branches" / items[1]["bid"] / "branch.json", {"target": "x"})
        self.assertEqual([i["bid"] for i in ib.pending(items)], [i["bid"] for i in items[1:]])

    def test_dry_main(self):
        buf = io.StringIO()
        est = {"branches": 0, "windows": {}, "chat_calls": 0, "embed_calls": 0, "cost_usd": 0, "wall_h": 0,
               "wall_h_serial": 0, "note": "n"}
        with redirect_stdout(buf), mock.patch.object(rb, "estimate", lambda *a, **k: est), \
                mock.patch.object(ib, "run", side_effect=AssertionError("ran")):
            ib.main(["--dry", "--only", "loneliness,loneliness_low", "--bases", "a,b", "--snapshots", "day1_end",
                     "--variant", "order"])
        out = buf.getvalue()
        self.assertIn("plan: 8 branches", out)   # 2 bases x 1 snapshot x (2 targets + 2 noop)
        self.assertIn("variants order", out)
        self.assertIn("loneliness=90, loneliness_low=5, noop x2", out)


class Judge(unittest.TestCase):
    def test_steer_criteria_and_template(self):
        self.assertEqual(sorted(steer.DIRECTIONS), it.DIRECTIONS)
        for d in it.DIRECTIONS:
            c = steer.criterion_id(d)
            self.assertTrue(steer.is_steer(c))
            self.assertIn(c, runner.CRITERIA)
            self.assertNotIn(c, runner.DEFAULT_CRITERIA)
            tpl = runner.template(c)
            self.assertNotIn("{steer", tpl)
            self.assertIn(d, tpl)
        self.assertFalse(steer.is_steer("steer_nothing"))
        self.assertFalse(steer.is_steer("register"))

    def test_steer_control_rule(self):
        e = {"kind": "control", "criterion": "steer_lonely"}

        def p(a, b):
            return {"scores": {"A": a, "B": b}, "verdict": "A" if a > b else "B" if b > a else "tie"}
        self.assertTrue(runner.score_entry(e, [p(3, 3), p(3, 3)]))
        self.assertTrue(runner.score_entry(e, [p(4, 3), p(3, 4)]))     # one point apart, either way
        self.assertFalse(runner.score_entry(e, [p(4, 2), p(5, 2)]))    # both passes 2+ apart, same way
        self.assertFalse(runner.score_entry(e, [p(2, 4), p(1, 4)]))
        self.assertTrue(runner.score_entry(e, [p(4, 2), p(2, 4)]))     # position bias, not a difference

    def test_calibration_entries(self):
        ent = {x["id"]: x for x in runner.load_defects()}
        for d in it.DIRECTIONS:
            self.assertEqual(ent[f"steer_{d}.ja.1"]["kind"], "steer")
            self.assertEqual(ent[f"control.steer_{d}.ja.1"]["kind"], "control")


def result(pair, crit, injected_letter, outcome, scores=None):
    """Write a fake results.json for one criterion of a pair. injected_letter: the match label the pair's `a` got;
    outcome: A, B, tie, split or invalid in match labels."""
    other = "B" if injected_letter == "A" else "A"
    path = VAR / "judge" / pair["match_id"] / "results.json"
    r = read_json(path) or {"label_map": {injected_letter: f"{pair['base']}~{pair['a']}",
                                          other: f"{pair['base']}~{pair['b']}"}, "summary": {"per_criterion": {}}}
    r["summary"]["per_criterion"][crit] = {
        "outcome": outcome, "agree": outcome in ("A", "B", "tie"), "calibrated": True,
        "mean_scores": scores or {"A": 3, "B": 3}}
    write_json(path, r)


class Summary(unittest.TestCase):
    TARGETS = [it.BY_NAME["loneliness"], it.BY_NAME["loneliness_low"], it.BY_NAME["energy"]]

    def test_judge_pairs(self):
        ps = isum.judge_pairs("b", "day1_end", it.TARGETS, ())
        self.assertEqual(len(ps), 1 + 6)
        self.assertEqual(ps[0]["kind"], "floor")
        self.assertEqual(ps[0]["criteria"], [f"steer_{d}" for d in it.DIRECTIONS])
        self.assertEqual((ps[0]["a"], ps[0]["b"]), isum.noop_ids("day1_end", ()))
        self.assertEqual(ps[1]["criteria"], ["steer_lonely"])
        self.assertEqual(ps[1]["b"], ps[0]["a"])   # pinned v noop r1; the floor is r1 v r2
        self.assertEqual(len({p["match_id"] for p in ps}), 7)
        self.assertEqual(isum.calls_of(ps), 6 * 2 + 6 * 2)
        po = isum.judge_pairs("b", "day1_end", it.TARGETS, ("order",))
        self.assertTrue(set(p["match_id"] for p in po).isdisjoint(p["match_id"] for p in ps))
        self.assertTrue(all("order" in p["a"] for p in po))

    def test_dry_counts(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            isum.main(["--dry"])
        self.assertIn("42 matches", buf.getvalue())            # 3 bases x 2 snapshots x (6 targets + 1 floor)
        self.assertIn("144 claude calls", buf.getvalue())      # 6 cells x (6 x 2 + 6 x 2)
        buf = io.StringIO()
        with redirect_stdout(buf):
            isum.main(["--dry", "--variants", "none,order", "--only", "loneliness"])
        self.assertIn("24 matches", buf.getvalue())            # 2 sets x 6 cells x (1 target + 1 floor)
        self.assertIn("48 claude calls", buf.getvalue())

    def test_variant_set_names(self):
        self.assertEqual(isum.variant_set("none"), ())
        self.assertEqual(isum.variant_set("order+trend"), ("order", "trend"))
        self.assertEqual(isum.set_name(()), "none")
        self.assertEqual(isum.set_name(("order", "trend")), "order+trend")

    def test_hit_rule(self):
        more, none = {"outcome": "first"}, None
        self.assertTrue(isum.is_hit(more, "more"))
        self.assertFalse(isum.is_hit(more, "less"))
        self.assertTrue(isum.is_hit({"outcome": "second"}, "less"))
        for o in ("tie", "split", "invalid"):
            self.assertFalse(isum.is_hit({"outcome": o}, "more"))
            self.assertFalse(isum.is_hit({"outcome": o}, "less"))
        self.assertIsNone(isum.is_hit(none, "more"))

    def test_scoring_floor_and_reverse(self):
        bases, snaps = ["ij_b1", "ij_b2"], ["day1_end"]
        pairs = {b: {p["name"]: p for p in isum.judge_pairs(b, "day1_end", self.TARGETS, ())} for b in bases}
        b1, b2 = pairs["ij_b1"], pairs["ij_b2"]
        # loneliness (more): both cells pick the pinned side (once as label A, once as label B)
        result(b1["loneliness"], "steer_lonely", "A", "A", {"A": 4, "B": 2})
        result(b2["loneliness"], "steer_lonely", "B", "B", {"A": 2, "B": 3})
        # loneliness_low (less, same direction): hit only when the NOOP side reads more lonely
        result(b1["loneliness_low"], "steer_lonely", "A", "B", {"A": 2, "B": 4})   # noop reads more: hit
        result(b2["loneliness_low"], "steer_lonely", "A", "A", {"A": 4, "B": 2})   # pinned reads more: miss
        # energy: no target result at all, floor results only
        # floor: r1 v r2. lonely: cell 1 r1 reads more (false pick for expect more), cell 2 tie
        result(b1["floor"], "steer_lonely", "A", "A")
        result(b2["floor"], "steer_lonely", "A", "tie")
        result(b1["floor"], "steer_tired", "A", "B")    # the match label map is fixed by the first write: r1 is A
        result(b2["floor"], "steer_tired", "A", "B")    # so the winner B is r2 in both cells
        finished = {(b, isum.target_id("day1_end", t, ())) for b in bases for t in self.TARGETS if t["name"] != "energy"}
        finished |= {(b, n) for b in bases for n in isum.noop_ids("day1_end", ())}

        def fake_mech(base, bid, cursor):
            same = "noop" in bid
            return {"her_lines": 2, "her_chars": 5, "unprompted": 0, "chat_calls": 4, "prompt_tokens": 1,
                    "cost_micro": 1, "roles": {}, "text": "aaaa" if same else "zzzz"}
        win = (datetime(2026, 11, 3), datetime(2026, 11, 3, 9))
        with mock.patch.object(rb, "window", lambda *a: win), mock.patch.object(rs, "mech", fake_mech), \
                mock.patch.object(branch, "is_finished", lambda r, b: (r, b) in finished):
            s = isum.build_set(bases, snaps, self.TARGETS, (), 6, 30)
        t = s["targets"]
        lo, low, en = t["loneliness"], t["loneliness_low"], t["energy"]
        self.assertEqual((lo["cells_judged"], lo["hits"], lo["share"]), (2, 2, 1.0))
        self.assertEqual((lo["floor_cells"], lo["floor_hits"], lo["floor_share"]), (2, 1, 0.5))
        self.assertEqual(lo["score"], 0.5)
        self.assertTrue(lo["steers"])
        self.assertEqual(lo["mean_gap"], 1.5)             # (4-2 and 3-2) / 2, injected minus noop side
        self.assertEqual((lo["mech_changed"], lo["mech_cells"]), (2, 2))
        self.assertEqual((low["cells_judged"], low["hits"], low["share"]), (2, 1, 0.5))
        self.assertEqual((low["floor_hits"], low["floor_share"]), (0, 0.0))   # r1 reading more is no hit for "less"
        self.assertEqual(low["score"], 0.5)
        self.assertFalse(low["steers"])                   # 1 of 2 is not more than half
        self.assertEqual(low["mean_gap"], 0.0)            # (2-4 and 4-2) / 2
        self.assertEqual(en["cells_judged"], 0)           # branch not finished
        self.assertIsNone(en["share"])
        self.assertIsNone(en["steers"])
        self.assertEqual(en["floor_cells"], 2)
        self.assertEqual(en["floor_hits"], 0)             # tired, expect more: r2 won both floors
        self.assertEqual((s["pooled_floor_cells"], s["pooled_floor_share"]), (6, round(1 / 6, 3)))
        self.assertEqual(lo["score_pooled"], round(1.0 - round(1 / 6, 3), 3))
        self.assertIsNone(en["score_pooled"])
        md = isum.render_md({"n_msgs": 6, "window_min": 30, "sets": {"none": s}})
        self.assertIn("## Variants: none", md)
        self.assertIn("| loneliness (lonely) | 90 | more | 2 | 2 | 100% |", md)
        self.assertIn("| loneliness_low (lonely) | 5 | less | 2 | 1 | 50% |", md)

    def test_uncalibrated_and_split_are_flagged_not_hit(self):
        b = {p["name"]: p for p in isum.judge_pairs("ij_b3", "day1_end", self.TARGETS[:1], ())}
        result(b["loneliness"], "steer_lonely", "A", "split")
        path = VAR / "judge" / b["loneliness"]["match_id"] / "results.json"
        r = read_json(path)
        r["summary"]["per_criterion"]["steer_lonely"]["calibrated"] = False
        write_json(path, r)
        win = (datetime(2026, 11, 3), datetime(2026, 11, 3, 9))
        fm = lambda base, bid, cursor: {"her_lines": 1, "her_chars": 1, "unprompted": 0, "chat_calls": 1,  # noqa: E731
                                        "prompt_tokens": 1, "cost_micro": 1, "roles": {}, "text": "x"}
        with mock.patch.object(rb, "window", lambda *a: win), mock.patch.object(rs, "mech", fm), \
                mock.patch.object(branch, "is_finished", lambda r, b: True):
            s = isum.build_set(["ij_b3"], ["day1_end"], self.TARGETS[:1], (), 6, 30)
        lo = s["targets"]["loneliness"]
        self.assertEqual((lo["cells_judged"], lo["hits"]), (1, 0))
        self.assertTrue(lo["uncalibrated"])
        self.assertEqual(lo["floor_cells"], 0)
        self.assertIsNone(lo["score"])
        self.assertIs(lo["cells"][0]["changed"], False)   # all texts equal: distance 0 is not above the floor 0


class MultiState(FakeState):
    def __init__(self):
        super().__init__()
        self.gauges.update({"fatigue": 5.0, "anxiety": 40.0, "stress": 12.0, "relief": 8.0})


class SteerFix(unittest.TestCase):
    """hold.multi, the tags overlay and the bubble counts (tk-6si steer_fix); no arm."""

    def test_hold_pairs(self):
        self.assertEqual(control.hold_pairs("hold.energy", 10), [("energy", 10)])
        self.assertEqual(control.hold_pairs("hold.energy", None), [("energy", None)])
        self.assertEqual(control.hold_pairs("hold.multi", {"energy": 10, "fatigue": 75}),
                         [("energy", 10), ("fatigue", 75)])
        for bad in (10, None, [], {}, "energy"):
            with self.assertRaises(ValueError):
                control.hold_pairs("hold.multi", bad)

    def test_hold_multi_pins_all(self):
        app = SimpleNamespace(state=MultiState())
        control.apply_inject(app, "hold.multi", {"anxiety": 90, "stress": 70, "relief": 0})
        g = app.state.gauges
        self.assertIsInstance(g, control.PinnedGauges)
        self.assertEqual(g.pins, {"anxiety": 90.0, "stress": 70.0, "relief": 0.0})
        g.update({"anxiety": 1, "stress": 1, "relief": 99, "energy": 3})
        self.assertEqual((g["anxiety"], g["stress"], g["relief"], g["energy"]), (90.0, 70.0, 0.0, 3))
        control.apply_inject(app, "hold.multi", {"relief": None})   # null in an object releases that gauge only
        self.assertEqual(set(g.pins), {"anxiety", "stress"})
        with self.assertRaises(ValueError):
            control.apply_inject(app, "hold.multi", 10)
        with self.assertRaises(ValueError):
            control.apply_inject(SimpleNamespace(state=MultiState()), "hold.multi", {"mood": 50})   # derived
        with self.assertRaises(ValueError):   # a gauge she does not have (fatigue is absent for Momoka) is refused
            control.apply_inject(SimpleNamespace(state=MultiState()), "hold.multi", {"nope": 5})

    def test_multi_branch_ids(self):
        a, b = it.BY_NAME["tired_full"], it.BY_NAME["anxious_full"]
        ia = branch.branch_id("day1_end", a["target"], a["value"])
        ib_ = branch.branch_id("day1_end", b["target"], b["value"])
        self.assertNotEqual(ia, ib_)
        self.assertIn("energy-10-stress-50", ia)
        self.assertIn("anxiety-90-stress-70-relief-0", ib_)
        planned = {i["bid"] for i in ib.plan([BASE], ["day1_end"], [a, b], 2)}
        self.assertTrue({ia, ib_} <= planned)
        self.assertNotIn(a, it.TARGETS)
        self.assertNotIn(b, it.TARGETS)
        self.assertEqual(len(it.TARGETS), 6)

    def test_deep_merge_and_overlay(self):
        d = {"a": {"x": 1, "l": [1, 2]}, "s": 1}
        control.deep_merge(d, {"a": {"y": 2, "l": [3]}, "s": {"k": 1}, "n": 5})
        self.assertEqual(d, {"a": {"x": 1, "y": 2, "l": [3]}, "s": {"k": 1}, "n": 5})
        ov = control.load_overlay("tags")
        gs = ov["state"]["gauges"]
        self.assertEqual(set(gs), {"energy", "anxiety", "loneliness", "boredom"})
        for g, body in gs.items():
            self.assertEqual(set(body), {"tags"}, g)
            for th in body["tags"]:
                self.assertEqual(len(th), 2, g)
                self.assertIsInstance(th[0], (int, float))
                self.assertTrue(isinstance(th[1], str) and th[1], g)
        self.assertLess(gs["energy"]["tags"][0][0], 0)   # negative threshold = low tag
        with self.assertRaises(KeyError):
            control.load_overlay("no_such_overlay")

    def test_overlay_merges_into_config_file(self):
        with tempfile.TemporaryDirectory(dir=r"F:\temp" if os.path.isdir(r"F:\temp") else None) as td:
            p = os.path.join(td, "c.json")
            write_json(p, {"state": {"gauges": {"anxiety": {"baseline": 40, "tags": [[50, "old"]]}, "other": {"k": 1}}}})
            control.write_overrides(p, {}, ["tags"])
            g = read_json(p)["state"]["gauges"]
            self.assertEqual(g["anxiety"]["baseline"], 40)                       # untouched key kept
            self.assertEqual(g["anxiety"]["tags"], control.load_overlay("tags")["state"]["gauges"]["anxiety"]["tags"])
            self.assertEqual(g["other"], {"k": 1})
            self.assertIn("energy", g)

    def test_count_steer(self):
        f = isum.count_steer("fewer", [(103, 136, 139)])
        self.assertEqual((f["pinned"], f["noop_r1"], f["noop_r2"], f["cells"]), (103, 136, 139, 1))
        self.assertIs(f["steers"], True)
        self.assertEqual(f["cells_beyond"], 1)
        self.assertIs(isum.count_steer("more", [(103, 136, 139)])["steers"], False)
        mixed = isum.count_steer("fewer", [(5, 10, 10), (12, 10, 10)])   # total fewer (17 v 20) but 1 of 2 cells
        self.assertEqual(mixed["cells_beyond"], 1)
        self.assertIs(mixed["steers"], False)
        n = isum.count_steer(None, [(103, 136, 139)])
        self.assertIsNone(n["steers"])
        self.assertIsNone(n["cells_beyond"])
        self.assertEqual(n["pinned"], 103)
        e = isum.count_steer("fewer", [])
        self.assertIsNone(e["steers"])
        self.assertEqual(e["cells"], 0)
        self.assertIs(isum.count_steer("fewer", [(10, 10, 12)])["steers"], False)   # tie with one noop is not beyond

    def test_count_table_in_md(self):
        cnt = {"expect": "fewer", "replies": isum.count_steer("fewer", [(103, 136, 139)]),
               "unprompted": isum.count_steer(None, [(4, 5, 6)])}
        row = {"target": "hold.energy", "value": 10, "direction": "tired", "expect": "more", "why": "w",
               "cells_judged": 0, "hits": 0, "share": None, "floor_cells": 0, "floor_hits": 0, "floor_share": None,
               "score": None, "steers": None, "mean_gap": None, "uncalibrated": False, "mech_changed": 0,
               "mech_cells": 0, "count": cnt, "score_pooled": None, "cells": []}
        rep = {"n_msgs": 8, "window_min": 30, "sets": {"tags": {"variants": ["tags"], "name": "tags", "cells": ["b s"],
               "pooled_floor_share": None, "pooled_floor_cells": 0, "targets": {"energy": row}}}}
        md = isum.render_md(rep)
        self.assertIn("Variants: tags", md)
        self.assertIn("| gauge | cells | replies pinned | replies noop r1 | replies noop r2 |", md)
        self.assertIn("| energy | 1 | 103 | 136 | 139 | 4 | 5 | 6 | fewer | 1 | yes |", md)


class DecayVariant(unittest.TestCase):
    """set.<gauge> (a one-shot, decay runs) and the decay_slow overlay (tk-6si decay variant); no arm."""

    def test_set_pairs(self):
        self.assertEqual(control.set_pairs("set.anger", 85), [("anger", 85)])
        self.assertEqual(control.set_pairs("set.multi", {"anxiety": 90, "stress": 70}),
                         [("anxiety", 90), ("stress", 70)])
        for bad in (10, None, [], {}, "anxiety"):
            with self.assertRaises(ValueError):
                control.set_pairs("set.multi", bad)

    def test_set_is_not_pinned(self):
        app = SimpleNamespace(state=MultiState())
        control.apply_inject(app, "set.loneliness", 90)
        g = app.state.gauges
        self.assertNotIsInstance(g, control.PinnedGauges)
        self.assertEqual(g["loneliness"], 90.0)
        g["loneliness"] = 80            # decay writes: it lands, nothing eats it
        self.assertEqual(g["loneliness"], 80)
        control.apply_inject(app, "set.multi", {"anxiety": 90, "stress": 70})
        self.assertEqual((g["anxiety"], g["stress"]), (90.0, 70.0))
        self.assertNotIsInstance(app.state.gauges, control.PinnedGauges)

    def test_set_refusals_and_hold_pin_dropped(self):
        app = SimpleNamespace(state=MultiState())
        with self.assertRaises(ValueError):
            control.apply_inject(app, "set.loneliness", None)    # nothing to release
        with self.assertRaises(ValueError):
            control.apply_inject(app, "set.mood", 80)            # derived
        with self.assertRaises(ValueError):
            control.apply_inject(app, "set.nothing", 80)         # unknown
        with self.assertRaises(ValueError):
            control.apply_inject(app, "set.multi", 10)
        control.apply_inject(app, "hold.loneliness", 90)         # a set on a held gauge drops the pin, then lands
        control.apply_inject(app, "set.loneliness", 40)
        g = app.state.gauges
        self.assertEqual(g["loneliness"], 40.0)
        g["loneliness"] = 35
        self.assertEqual(g["loneliness"], 35)

    @staticmethod
    def _real_state(cfg_path, tmp, clock):
        import contextlib
        from pathlib import Path
        from config import Config
        from store import Store
        from sim.state import State
        with contextlib.redirect_stdout(io.StringIO()):
            cfg = Config(cfg_path)
            return State(cfg, Store(str(Path(tmp) / "w.db")), clock)

    class _Clock:
        def __init__(self, n):
            self.n = n

        def now_ts(self):
            return self.n

        def date_str(self):
            return "d"

    def test_set_then_decay_on_the_real_state(self):
        """Her real config and State: set.anger lands at 85, one virtual hour later it is 7 lower (decay_per_hour 7);
        the hold twin stays at 85. set.affection 90 heads back at the computed-affection inertia (6/h)."""
        live = os.path.join(ROOT, "config_momoka.json")
        with tempfile.TemporaryDirectory(dir=r"F:\temp" if os.path.isdir(r"F:\temp") else None,
                                         ignore_cleanup_errors=True) as tmp:
            clock = self._Clock(1_000_000.0)
            st = self._real_state(live, tmp, clock)
            app = SimpleNamespace(state=st)
            rate = st.config.state.gauges["anger"]["decay_per_hour"]
            self.assertEqual(rate, 7)
            control.apply_inject(app, "set.anger", 85)
            control.apply_inject(app, "set.affection", 90)
            self.assertEqual((st.gauges["anger"], st.gauges["affection"]), (85.0, 90.0))   # right after the inject
            clock.n += 3600
            st.decay(0.0)
            self.assertEqual(st.gauges["anger"], 85.0 - rate)
            self.assertLess(st.gauges["affection"], 90.0)
            self.assertGreater(st.gauges["affection"], 90.0 - 6.0 - 0.01)   # at most one hour of inertia
            with tempfile.TemporaryDirectory(dir=tmp, ignore_cleanup_errors=True) as t2:
                clock2 = self._Clock(1_000_000.0)
                st2 = self._real_state(live, t2, clock2)
                control.apply_inject(SimpleNamespace(state=st2), "hold.anger", 85)
                clock2.n += 3600
                st2.decay(0.0)
                self.assertEqual(st2.gauges["anger"], 85.0)    # the pin twin does not decay

    def test_decay_slow_overlay_is_a_quarter_of_live(self):
        live = read_json(os.path.join(ROOT, "config_momoka.json"))
        ov = control.load_overlay("decay_slow")
        gs = ov["state"]["gauges"]
        self.assertEqual(set(gs), {"anger", "boredom", "energy", "anxiety", "loneliness"})
        for g, body in gs.items():
            self.assertEqual(set(body), {"decay_per_hour"}, g)
            self.assertEqual(body["decay_per_hour"], live["state"]["gauges"][g]["decay_per_hour"] / 4, g)
        # affection's gauge decay is 0 live; it heads to its target at affection_from.inertia_per_hour
        self.assertEqual(live["state"]["gauges"]["affection"]["decay_per_hour"], 0)
        self.assertEqual(ov["state"]["affection_from"],
                         {"inertia_per_hour": live["state"]["affection_from"]["inertia_per_hour"] / 4})
        self.assertEqual(set(ov), {"state"})
        self.assertEqual(set(ov["state"]), {"gauges", "affection_from"})
        self.assertIn("decay_slow", branch.OVERLAY_VARIANTS)
        self.assertIn("tags", branch.OVERLAY_VARIANTS)

    def test_decay_slow_merges_and_slows_the_real_state(self):
        live = os.path.join(ROOT, "config_momoka.json")
        with tempfile.TemporaryDirectory(dir=r"F:\temp" if os.path.isdir(r"F:\temp") else None,
                                         ignore_cleanup_errors=True) as tmp:
            p = os.path.join(tmp, "c.json")
            write_json(p, read_json(live))
            control.write_overrides(p, {}, ["decay_slow"])
            merged = read_json(p)["state"]["gauges"]
            self.assertEqual(merged["anger"]["decay_per_hour"], 1.75)
            self.assertEqual(merged["anger"]["baseline"], 8)             # untouched key kept
            self.assertEqual(merged["anger"]["tags"], read_json(live)["state"]["gauges"]["anger"]["tags"])
            clock = self._Clock(1_000_000.0)
            st = self._real_state(p, tmp, clock)
            control.apply_inject(SimpleNamespace(state=st), "set.anger", 85)
            clock.n += 3600
            st.decay(0.0)
            self.assertEqual(st.gauges["anger"], 85.0 - 1.75)

    def test_live_config_carries_the_energy_and_anxiety_tags(self):
        """The S arm composes its config from <s-root>/config_momoka.json (make_run.py), not from bundle.json, so the
        felt tags for set_anxiety / energy have to be in that file (master 4d9bf99)."""
        gs = read_json(os.path.join(ROOT, "config_momoka.json"))["state"]["gauges"]
        self.assertEqual(gs["anxiety"]["tags"][0][0], 70)
        self.assertEqual(gs["energy"]["tags"][0][0], -30)

    def test_targets_ids_select_and_dry_plan(self):
        names = [t["name"] for t in it.DECAY]
        self.assertEqual(names, ["set_loneliness", "set_anger", "set_affection", "set_anxiety"])
        self.assertEqual(len(set(t["name"] for t in it.ALL)), len(it.ALL))   # names stay unique
        for t in it.DECAY:
            twin = it.BY_NAME[t["name"][4:]]
            self.assertEqual(t["target"], "set." + twin["target"][5:])
            self.assertEqual((t["value"], t["direction"], t["expect"]),
                             (twin["value"], twin["direction"], twin["expect"]))
            self.assertNotEqual(branch.branch_id("day1_end", t["target"], t["value"]),
                                branch.branch_id("day1_end", twin["target"], twin["value"]))
            self.assertNotIn(t, it.TARGETS)
        self.assertEqual(len(it.TARGETS), 6)                                  # the default batch is unchanged
        self.assertEqual([t["name"] for t in it.select([])], [t["name"] for t in it.TARGETS])
        self.assertEqual([t["name"] for t in it.select(["decay"])], names)
        self.assertEqual([t["name"] for t in it.select(["set_anger", "loneliness"])], ["loneliness", "set_anger"])
        with self.assertRaises(ValueError):
            it.select(["set_angr"])
        out = io.StringIO()
        with redirect_stdout(out):
            ib.main(["--dry", "--only", "decay", "--variant", "decay_slow", "--bases", "nobase_a,nobase_b",
                     "--snapshots", "day1_end,day2_end"])
        text = out.getvalue()
        self.assertIn("plan: 24 branches (2 bases x 2 snapshots x 4 targets + 2 noop)", text)   # 2*2*(4+2)
        out = io.StringIO()
        with redirect_stdout(out):
            ib.main(["--dry", "--only", "decay", "--variant", "decay_slow"])
        text = out.getvalue()
        self.assertIn("variants decay_slow", text)
        self.assertIn("set_loneliness=90, set_anger=85, set_affection=90, set_anxiety=90, noop x2", text)
        p = ib.plan(rb.BASES, rb.SNAPSHOTS, it.select(["decay"]), 2, ("decay_slow",))
        self.assertEqual(len(p), 36)                                          # 3 bases x 2 snapshots x (4 + 2)
        self.assertEqual(len({i["bid"] for i in p}), 12)                      # a bid is per snapshot; a base has its own folder
        self.assertTrue(all(i["bid"].endswith("_decay-slow") or i["bid"].endswith("_decay-slow-r1")
                            or i["bid"].endswith("_decay-slow-r2") for i in p))
        plain = ib.plan(rb.BASES, rb.SNAPSHOTS, it.select(["decay"]), 2, ())
        self.assertFalse({i["bid"] for i in p} & {i["bid"] for i in plain})  # a rate does not collide with the other
        hold = ib.plan(rb.BASES, rb.SNAPSHOTS, it.TARGETS, 2, ())
        self.assertFalse({i["bid"] for i in plain if i["name"] != "noop"} & {i["bid"] for i in hold})
        self.assertEqual(ib.cmd_args(p[0], 6, 30, "S")[4:8], [p[0]["base"], p[0]["snapshot"], "set.loneliness", "90"])
        self.assertEqual(ib.cmd_args(p[0], 6, 30, "S")[-2:], ["--variant", "decay_slow"])

    def test_summary_plan_and_md_for_two_rates(self):
        targets = it.select(["decay"])
        pairs = [pp for v in (isum.variant_set("none"), isum.variant_set("decay_slow"))
                 for b in rb.BASES for s in rb.SNAPSHOTS for pp in isum.judge_pairs(b, s, targets, v)]
        self.assertEqual(len(pairs), 2 * 3 * 2 * (4 + 1))                     # 60 matches
        self.assertEqual(len({pp["match_id"] for pp in pairs}), 60)
        a = isum.target_id("day1_end", it.BY_NAME["set_anger"], ())
        b = isum.target_id("day1_end", it.BY_NAME["set_anger"], ("decay_slow",))
        self.assertNotEqual(a, b)
        self.assertEqual(isum.noop_ids("day1_end", ("decay_slow",))[0],
                         branch.branch_id("day1_end", "noop", True, "decay_slow_r1"))
        row = {"target": "set.anger", "value": 85, "direction": "angry", "expect": "more", "why": "w",
               "cells_judged": 0, "hits": 0, "share": None, "floor_cells": 0, "floor_hits": 0, "floor_share": None,
               "score": None, "steers": None, "mean_gap": None, "uncalibrated": False, "mech_changed": 0,
               "mech_cells": 0, "count": {}, "score_pooled": None, "cells": []}
        rep = {"n_msgs": 6, "window_min": 30, "sets": {"decay_slow": {
            "variants": ["decay_slow"], "name": "decay_slow", "cells": ["b s"], "pooled_floor_share": None,
            "pooled_floor_cells": 0, "targets": {"set_anger": row}}}}
        md = isum.render_md(rep)
        self.assertIn("Variants: decay_slow", md)
        self.assertIn("| set_anger (angry) | set 85 | more |", md)


REF = [("2026-11-02T09:15:00", "morning, you up?"), ("2026-11-03T08:00:00", "day two first"),
       ("2026-11-03T08:10:00", "day two, ten minutes on"), ("2026-11-03T22:00:00", "late one")]


def cfg(run_id, port, **kw):
    cmd = [sys.executable, "-m", "bzombie.harness.stub_arm", "--port", "{port}", "--arm", "{arm}"]
    c = {"run_id": run_id, "arm": "S", "character": "tomoe", "lang": "en", "model": "stub", "cap_usd": 1,
         "sim_days": 2, "clock_start": "2026-11-02T00:00:00", "seed": 7, "use_limits": False,
         "arm_port": port, "arm_cmd": cmd, "step_s": 3600}
    c.update(kw)
    return c


BASE = "inj_base"
LONELY = it.BY_NAME["loneliness"]
BID_HOLD = branch.branch_id("day1_end", "hold.loneliness", 90)
BID_HOLD_ORDER = branch.branch_id("day1_end", "hold.loneliness", 90, "order")


class OnStub(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def no_model(*a, **k):
            raise AssertionError("sim-him model called in script mode")
        cls.addClassCleanup(cls._stop_arms)
        for p in (mock.patch.dict(os.environ, {"BZ_LLM_STUB": "1"}),
                  mock.patch.object(him, "decide", no_model),
                  mock.patch.object(branch, "free_port", lambda base, span=9: PORT),
                  mock.patch.object(llm, "backend", None)):
            p.start()
            cls.addClassCleanup(p.stop)
        rd = run_dir("inj_ref")
        rd.mkdir(parents=True, exist_ok=True)
        write_json(rd / "config.json", cfg("inj_ref", 1))
        for ts, text in REF:
            append_jsonl(rd / "transcript.jsonl", {"virtual_ts": ts, "who": "him", "text": text})
        driver.init_run(driver.load_config(cfg(BASE, PORT, him_via="script", him_script="inj_ref")))
        driver.drive(BASE)
        assert read_json(run_dir(BASE) / "state.json")["status"] == "done"

    @staticmethod
    def _stop_arms():
        try:
            Arm(PORT).stop()
        except Exception:
            pass

    @staticmethod
    def _injects(bid):
        out = []
        for p in sorted((run_dir(BASE) / "branches" / bid / "traces").glob("*.json")):
            inj = (read_json(p) or {}).get("state_at_output", {}).get("injects")
            if inj:
                out = inj
        return out

    @staticmethod
    def _branch(*args):
        if not branch.is_finished(BASE, args[-1]):
            cli.cmd_branch([BASE, "day1_end"] + list(args[:-1]))

    def test_hold_branch_and_variant_passthrough(self):
        self._branch("hold.loneliness", "90", "--n-msgs", "1", BID_HOLD)
        self._branch("hold.loneliness", "90", "--n-msgs", "1", "--variant", "order", BID_HOLD_ORDER)
        bd = run_dir(BASE) / "branches"
        m, mo = read_json(bd / BID_HOLD / "branch.json"), read_json(bd / BID_HOLD_ORDER / "branch.json")
        self.assertTrue(m["finished"] and mo["finished"])
        self.assertEqual((m["target"], m["value"], m["variants"]), ("hold.loneliness", 90, []))
        self.assertEqual((mo["variants"], mo["tag"]), (["order"], "order"))
        self.assertNotEqual(BID_HOLD, BID_HOLD_ORDER)
        self.assertEqual(self._injects(BID_HOLD), [["hold.loneliness", 90]])
        self.assertEqual(self._injects(BID_HOLD_ORDER), [["hold.loneliness", 90], ["bz.order", True]])

    def test_overlay_variant_injects_first_and_multi_value(self):
        bid_t = branch.branch_id("day1_end", "hold.loneliness", 90, "tags")
        self._branch("hold.loneliness", "90", "--n-msgs", "1", "--variant", "tags", bid_t)
        bd = run_dir(BASE) / "branches"
        self.assertEqual(read_json(bd / bid_t / "branch.json")["variants"], ["tags"])
        self.assertEqual(self._injects(bid_t), [["overlay.tags", True], ["hold.loneliness", 90]])   # overlay first
        bid_ot = branch.branch_id("day1_end", "hold.loneliness", 90, "order-tags")
        self._branch("hold.loneliness", "90", "--n-msgs", "1", "--variant", "order,tags", bid_ot)
        inj = self._injects(bid_ot)
        self.assertEqual(inj[0], ["overlay.tags", True])
        self.assertEqual(inj[1], ["hold.loneliness", 90])
        self.assertEqual(inj[2], ["bz.order", True])
        multi = it.BY_NAME["tired_full"]
        bid_m = branch.branch_id("day1_end", multi["target"], multi["value"])
        self._branch("hold.multi", json.dumps(multi["value"]), "--n-msgs", "1", bid_m)
        self.assertEqual(self._injects(bid_m), [["hold.multi", {"energy": 10, "stress": 50}]])

    @staticmethod
    def _seeded(bid):
        out = None
        for p in sorted((run_dir(BASE) / "branches" / bid / "traces").glob("*.json")):
            s = (read_json(p) or {}).get("state_at_output", {})
            if "seed_him" in s:
                out = s["seed_him"]
        return out

    def test_branch_seeds_his_primitives_unless_stranger(self):
        """tk-xhv: every S-arm branch is seeded by default (seed.him goes to the arm after the overlays, before the
        target, and is not an experiment inject); --variant stranger and --stranger leave the save as it was."""
        bid_d = branch.branch_id("day1_end", "hold.loneliness", 90, "tags")
        self._branch("hold.loneliness", "90", "--n-msgs", "1", "--variant", "tags", bid_d)
        bid_s = branch.branch_id("day1_end", "hold.loneliness", 90, "stranger")
        self._branch("hold.loneliness", "90", "--n-msgs", "1", "--stranger", bid_s)
        bd = run_dir(BASE) / "branches"
        md, ms = read_json(bd / bid_d / "branch.json"), read_json(bd / bid_s / "branch.json")
        self.assertTrue(self._seeded(bid_d))
        self.assertTrue(md["seed"].startswith("primitives_him@"))
        self.assertEqual(self._injects(bid_d), [["overlay.tags", True], ["hold.loneliness", 90]])
        self.assertFalse(self._seeded(bid_s))
        self.assertNotIn("seed", ms)
        self.assertEqual(ms["variants"], ["stranger"])
        self.assertEqual(self._injects(bid_s), [["hold.loneliness", 90]])   # stranger is no bz switch

    def test_set_branch_and_decay_slow_variant(self):
        t = it.BY_NAME["set_anger"]
        bid_s = branch.branch_id("day1_end", t["target"], t["value"])
        bid_slow = branch.branch_id("day1_end", t["target"], t["value"], "decay_slow")
        self.assertNotIn(bid_s, (BID_HOLD, branch.branch_id("day1_end", "hold.anger", 85)))
        self._branch("set.anger", "85", "--n-msgs", "1", bid_s)
        self._branch("set.anger", "85", "--n-msgs", "1", "--variant", "decay_slow", bid_slow)
        bd = run_dir(BASE) / "branches"
        self.assertEqual(read_json(bd / bid_slow / "branch.json")["variants"], ["decay_slow"])
        self.assertEqual(self._injects(bid_s), [["set.anger", 85]])
        self.assertEqual(self._injects(bid_slow), [["overlay.decay_slow", True], ["set.anger", 85]])   # overlay first
        item = ib.plan([BASE], ["day1_end"], [t], 0, ("decay_slow",))
        self.assertEqual([i["bid"] for i in item], [bid_slow])
        self.assertEqual(ib.pending(item), [])

    def test_batch_ids_match_branch_dirs_and_mechanical_cell(self):
        item = ib.plan([BASE], ["day1_end"], [LONELY], 2)
        self.assertEqual([i["bid"] for i in item][0], BID_HOLD)
        self._branch("hold.loneliness", "90", "--n-msgs", "1", BID_HOLD)
        for r in ("r1", "r2"):
            bid = branch.branch_id("day1_end", "noop", True, r)
            self._branch("noop", "true", "--n-msgs", "1", "--tag", r, bid)
        self._branch("hold.loneliness", "90", "--n-msgs", "1", "--variant", "order", BID_HOLD_ORDER)
        self.assertEqual(sorted(i["bid"] for i in ib.pending(item)), [])   # all three finished under the planned ids
        m = isum.mech_cell(BASE, "day1_end", [LONELY], (), 1, 30)
        self.assertEqual(m["floor"], 0.0)
        self.assertEqual(m["noop_finished"], ["r1", "r2"])
        row = m["targets"]["loneliness"]
        self.assertTrue(row["finished"])
        self.assertEqual(row["d_noop"], [0.0, 0.0])
        self.assertIs(row["changed"], False)        # the stub's replies do not depend on the pin
        mo = isum.mech_cell(BASE, "day1_end", [LONELY], ("order",), 1, 30)
        self.assertIsNone(mo["floor"])              # the order variant has its pin branch but no noops yet
        self.assertTrue(mo["targets"]["loneliness"]["finished"])
        self.assertIsNone(mo["targets"]["loneliness"]["changed"])


if __name__ == "__main__":
    unittest.main()
