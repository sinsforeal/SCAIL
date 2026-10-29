"""Scene battery (tk-z1q): scene loading, script timing, pairing, the probe-only judge view, gauge trace extraction,
the failure split, the summary over fake branches and `scene_batch --dry`. Fake run folders and fake judge results only:
no spend, no claude, no arm, no gateway."""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta

if "bzombie.common" in sys.modules:
    os.environ["BZ_VAR"] = str(sys.modules["bzombie.common"].VAR)
else:
    os.environ["BZ_VAR"] = tempfile.mkdtemp(prefix="bzs_", dir=r"F:\temp" if os.path.isdir(r"F:\temp") else None)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from bzombie import common  # noqa: E402
from bzombie.common import append_jsonl, iso, parse_ts, read_json, read_jsonl, run_dir, write_json  # noqa: E402
from bzombie.harness import branch, cli, inject_summary as isum, scene_batch as sb, scene_summary as ss  # noqa: E402
from bzombie.harness import scenes as sc  # noqa: E402
from bzombie.judge import runner, steer  # noqa: E402

CURSOR = datetime(2026, 10, 27, 0, 0)
BASE = "tsc_base"


def day_at(hh, mm=0, days=0):
    return CURSOR + timedelta(days=days, hours=hh, minutes=mm)


class Loading(unittest.TestCase):
    def test_every_scene_builds_on_both_sides(self):
        self.assertEqual([s["name"] for s in sc.SCENES],
                         ["absence", "slight", "warmth", "worry", "latenight", "dull"])
        for s in sc.SCENES:
            for side in sc.SIDES:
                rows = sc.build_script(s, side, CURSOR)
                ts = [parse_ts(r["virtual_ts"]) for r in rows]
                self.assertEqual(ts, sorted(set(ts)), f"{s['name']}/{side}: times must strictly increase")
                self.assertGreater(ts[0], CURSOR)
                self.assertEqual([r["probe"] for r in rows][-3:], [True] * 3)
                self.assertFalse(any(r["probe"] for r in rows[:-3]))
                self.assertTrue(all(r["who"] == "him" and r["text"] for r in rows))

    def test_probes_are_the_same_on_both_sides_and_in_every_scene(self):
        for s in sc.SCENES:
            texts = {side: [r["text"] for r in sc.build_script(s, side, CURSOR) if r["probe"]] for side in sc.SIDES}
            self.assertEqual(texts["trigger"], texts["control"])
            self.assertEqual(texts["trigger"], list(sc.PROBES))

    def test_probes_land_at_the_same_clock_time_except_late_night(self):
        for s in sc.SCENES:
            a = sc.script_span(sc.build_script(s, "trigger", CURSOR), CURSOR)["probe_start"]
            b = sc.script_span(sc.build_script(s, "control", CURSOR), CURSOR)["probe_start"]
            if s["name"] == "latenight":
                self.assertEqual((a.hour, a.minute, b.hour, b.minute), (2, 45, 16, 15))
            else:
                self.assertEqual(a, b, s["name"])

    def test_directions_match_the_judge_and_targets(self):
        from bzombie.harness import inject_targets as it
        by_gauge = {t["name"]: t for t in it.TARGETS}
        for s in sc.SCENES:
            self.assertIn(s["direction"], steer.DIRECTIONS)
            if s["direction"] == "hurt":
                continue   # slight since 10-25: hurt has no inject twin (no hold.sadness target)
            t = by_gauge[s["gauge"]]
            self.assertEqual((s["direction"], s["expect"]), (t["direction"], t["expect"]), s["name"])
            self.assertEqual(s.get("count"), t.get("count"), s["name"])
        self.assertEqual(sc.BY_NAME["latenight"]["gauge_dir"], "down")   # tired = energy low

    def test_select(self):
        self.assertEqual(len(sc.select([""])), 6)
        self.assertEqual([s["name"] for s in sc.select(["dull", "absence"])], ["absence", "dull"])
        with self.assertRaises(ValueError):
            sc.select(["absense"])

    def test_scene_line_counts(self):
        n = {s["name"]: [len(sc.build_script(s, side, CURSOR)) for side in sc.SIDES] for s in sc.SCENES}
        self.assertEqual(n, {"absence": [4, 11], "slight": [7, 7], "warmth": [6, 6], "worry": [6, 8],
                             "latenight": [7, 7], "dull": [13, 13]})


class Timing(unittest.TestCase):
    def test_gap_specs(self):
        d = CURSOR.date()
        t0 = parse_at = sc.parse_at("07:30", None, d)
        self.assertEqual(t0, day_at(7, 30))
        self.assertEqual(sc.parse_at("+8h", t0, d), day_at(15, 30))
        self.assertEqual(sc.parse_at("+1h30m", t0, d), day_at(9, 0))
        self.assertEqual(sc.parse_at("+45m", t0, d), day_at(8, 15))
        self.assertEqual(sc.parse_at("06:00", t0, d), day_at(6, 0, days=1))   # before the previous line: next day
        for bad in ("+", "+h", "+3", "+m5"):
            with self.assertRaises(ValueError):
                sc.parse_at(bad, t0, d)
        with self.assertRaises(ValueError):
            sc.parse_at("+5m", None, d)

    def test_absence_gap_lands_as_virtual_time(self):
        rows = sc.build_script(sc.BY_NAME["absence"], "trigger", CURSOR)
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]["virtual_ts"], iso(day_at(7, 30)))
        self.assertEqual(parse_ts(rows[1]["virtual_ts"]) - parse_ts(rows[0]["virtual_ts"]), timedelta(hours=8, minutes=10))
        self.assertEqual([r["virtual_ts"][11:16] for r in rows[1:]], ["15:40", "15:47", "15:54"])
        # the control has him around in the same span
        ctl = sc.build_script(sc.BY_NAME["absence"], "control", CURSOR)
        gaps = [parse_ts(b["virtual_ts"]) - parse_ts(a["virtual_ts"]) for a, b in zip(ctl, ctl[1:])]
        self.assertLess(max(gaps), timedelta(hours=2))
        self.assertEqual(ctl[0]["text"], rows[0]["text"])

    def test_worry_goes_quiet_for_two_hours(self):
        rows = sc.build_script(sc.BY_NAME["worry"], "trigger", CURSOR)
        gaps = [parse_ts(b["virtual_ts"]) - parse_ts(a["virtual_ts"]) for a, b in zip(rows, rows[1:])]
        self.assertEqual(max(gaps), timedelta(hours=2))

    def test_late_night_runs_0130_to_0300_and_control_is_the_same_lines_at_1500(self):
        s = sc.BY_NAME["latenight"]
        t, c = sc.build_script(s, "trigger", CURSOR), sc.build_script(s, "control", CURSOR)
        self.assertEqual([r["text"] for r in t], [r["text"] for r in c])
        self.assertEqual((t[0]["virtual_ts"][11:16], t[-1]["virtual_ts"][11:16]), ("01:30", "02:59"))
        self.assertEqual((c[0]["virtual_ts"][11:16], c[-1]["virtual_ts"][11:16]), ("15:00", "16:29"))
        # the same offsets from the first line
        self.assertEqual([parse_ts(a["virtual_ts"]) - parse_ts(t[0]["virtual_ts"]) for a in t],
                         [parse_ts(a["virtual_ts"]) - parse_ts(c[0]["virtual_ts"]) for a in c])

    def test_dull_trigger_is_an_hour_of_one_word_replies(self):
        t = sc.build_script(sc.BY_NAME["dull"], "trigger", CURSOR)
        body = [r for r in t[1:-3]]
        self.assertEqual(len(body), 9)
        self.assertTrue(all(len(r["text"]) <= 3 for r in body))
        self.assertEqual(parse_ts(t[-4]["virtual_ts"]) - parse_ts(t[0]["virtual_ts"]), timedelta(minutes=54))

    def test_start_at_or_before_the_cursor_moves_a_day(self):
        s = {"name": "x", "trigger": [("00:00", "a")], "control": [("00:00", "a")], "probe_first": {"trigger": "+1h", "control": "+1h"}}
        rows = sc.build_script(s, "trigger", CURSOR)
        self.assertEqual(rows[0]["virtual_ts"], iso(day_at(0, 0, days=1)))

    def test_probes_not_after_the_last_line_are_refused(self):
        s = {"name": "x", "trigger": [("10:00", "a"), ("11:00", "b")], "control": [("10:00", "a")],
             "probe_first": {"trigger": "11:00", "control": "11:00"}}
        with self.assertRaises(ValueError):
            sc.build_script(s, "trigger", CURSOR)
        self.assertEqual(len(sc.build_script(s, "control", CURSOR)), 4)

    def test_span_and_branch_window(self):
        rows = sc.build_script(sc.BY_NAME["warmth"], "trigger", CURSOR)
        sp = sc.script_span(rows, CURSOR)
        self.assertEqual(sp["n_lines"], 6)
        self.assertEqual(sp["probe_start"], day_at(21, 17))
        self.assertEqual(sp["end"], day_at(21, 31) + timedelta(minutes=sc.TAIL_MIN))
        self.assertEqual(len(sp["probes"]), 3)

    def test_written_script_is_a_script_the_harness_loads(self):
        from bzombie.harness import script as hscript
        rows = sc.build_script(sc.BY_NAME["slight"], "trigger", CURSOR)
        p = common.VAR / "scenes_test" / "slight.jsonl"
        sc.write_script(rows, p)
        got = hscript.load(str(p), "momoka")
        self.assertEqual([l["text"] for l in got["lines"]], [r["text"] for r in rows])
        self.assertEqual(got["lines"][0]["virtual_ts"], rows[0]["virtual_ts"])


def fake_base(name=BASE, snaps=("day1_end", "day2_end"), calls=True):
    rd = run_dir(name)
    for i, s in enumerate(snaps):
        write_json(rd / "snapshots" / "harness" / f"{s}.json", {"name": s, "cursor": iso(CURSOR + timedelta(days=i)),
                                                                "transcript_len": 3, "day": i + 1})
    if calls:
        for k in range(4):
            append_jsonl(rd / "calls.jsonl", {"virtual_ts": iso(day_at(9 + k)), "endpoint": "chat/completions",
                                              "latency_s": 2.0, "cost_micro": 100})
        append_jsonl(rd / "calls.jsonl", {"virtual_ts": iso(day_at(10)), "endpoint": "embeddings"})
    return rd


class Pairing(unittest.TestCase):
    def test_plan_is_108_unique_branches_in_pairs(self):
        items = sb.plan()
        self.assertEqual(len(items), 3 * 2 * 6 * 3)
        self.assertEqual(len({(i["base"], i["bid"]) for i in items}), len(items), "branch ids collide inside a base")
        cell = [i for i in items if (i["base"], i["snapshot"], i["scene"]) == (sb.BASES[0], "day1_end", "absence")]
        self.assertEqual([(i["side"], i["rep"]) for i in cell], [("trigger", ""), ("control", "r1"), ("control", "r2")])
        self.assertEqual(cell[1]["script"], cell[2]["script"])
        self.assertNotEqual(cell[0]["script"], cell[1]["script"])
        self.assertEqual(cell[0]["bid"], "day1-end_noop_True_sc-absence-trigger")
        self.assertEqual(cell[2]["bid"], "day1-end_noop_True_sc-absence-control-r2")

    def test_variant_stays_in_every_id_and_ids_do_not_collide_with_a_long_variant(self):
        items = sb.plan(variants=("decay_slow", "tagcfg"))
        self.assertTrue(all("decay-slow-tagcfg" in i["bid"] for i in items))
        self.assertEqual(len({(i["base"], i["bid"]) for i in items}), len(items))
        self.assertEqual(sb.scene_bid("day1_end", "worry", "control", "r1", ()), "day1-end_noop_True_sc-worry-control-r1")
        # ids of a plain inject_batch noop are untouched by the longer tag limit
        self.assertEqual(branch.branch_id("day1_end", "noop", True, "order-keep-mood-tags-r1"),
                         "day1-end_noop_True_order-keep-mood-tags-r1")

    def test_controls_option_and_only(self):
        self.assertEqual(len(sb.plan(controls=1)), 3 * 2 * 6 * 2)
        self.assertEqual(len(sb.plan(scenes=sc.select(["dull"]))), 3 * 2 * 3)

    def test_cmd_args_runs_noop_with_the_script(self):
        i = sb.plan(variants=("tagcfg",))[1]
        a = sb.cmd_args(i, 11, "F:/x")
        self.assertEqual(a[3:8], ["branch", i["base"], i["snapshot"], "noop", "true"])
        self.assertEqual(a[a.index("--script-from") + 1], i["script"])
        self.assertEqual(a[a.index("--n-msgs") + 1], "11")
        self.assertEqual(a[a.index("--window-min") + 1], str(sc.TAIL_MIN))
        self.assertEqual(a[a.index("--tag") + 1], "sc-absence-control-r1")
        self.assertEqual(a[a.index("--variant") + 1], "tagcfg")

    def test_pending_skips_finished(self):
        fake_base()
        items = sb.plan(bases=[BASE], snapshots=["day1_end"], scenes=sc.select(["warmth"]))
        write_json(run_dir(BASE) / "branches" / items[0]["bid"] / "branch.json", {"finished": True})
        self.assertEqual([i["bid"] for i in sb.pending(items)], [i["bid"] for i in items[1:]])

    def test_branch_delivers_every_scene_line(self):
        """branch() picks lines >= cursor, the first n_msgs, then everything up to window_min after the n-th: with
        n_msgs = the script and the tail, all of them."""
        rows = sc.build_script(sc.BY_NAME["absence"], "trigger", CURSOR)
        sp = sc.script_span(rows, CURSOR)
        after = [parse_ts(r["virtual_ts"]) for r in rows if parse_ts(r["virtual_ts"]) >= CURSOR]
        end = after[min(sp["n_lines"], len(after)) - 1] + timedelta(minutes=sc.TAIL_MIN)
        self.assertEqual(end, sp["end"])
        self.assertEqual(len([t for t in after if t <= end]), sp["n_lines"])


def write_branch(base, bid, probe_start, her_after=("あ", "い", "う"), cursor=CURSOR, gauge=None, env=True,
                 with_traces=True, calls_gauge=None, finished=True):
    """A fake finished scene branch: a prefix row, env, his trigger line, a her line before the probes, then the three
    probes each with her reply 1 min on. gauge = [post, p1, p2, p3] values for the trace rows."""
    bdir = run_dir(base) / "branches" / bid
    rows = [{"virtual_ts": iso(cursor - timedelta(hours=1)), "who": "her", "text": "prefix", "sim_day": 1},
            {"virtual_ts": iso(probe_start - timedelta(hours=1)), "who": "him", "text": "trigger line", "sim_day": 2},
            {"virtual_ts": iso(probe_start - timedelta(minutes=30)), "who": "her", "text": "before the probes",
             "kind": "unprompted", "sim_day": 2, "output_id": "o_pre"}]
    if env:
        rows.append({"virtual_ts": iso(probe_start - timedelta(minutes=10)), "who": "env", "text": "Window title: x",
                     "kind": "pc"})
    for k, text in enumerate(sc.PROBES):
        t = probe_start + timedelta(minutes=sc.PROBE_GAP_MIN * k)
        rows.append({"virtual_ts": iso(t), "who": "him", "text": text, "sim_day": 2, "branch": True})
        rows.append({"virtual_ts": iso(t), "who": "her", "text": her_after[k], "kind": "reply", "sim_day": 2,
                     "output_id": f"o{k}"})
    (bdir).mkdir(parents=True, exist_ok=True)
    (bdir / "transcript.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    write_json(bdir / "branch.json", {"branch_id": bid, "replayed_from_virtual_ts": iso(cursor), "finished": finished})
    if gauge and with_traces:
        post, *ps = gauge
        tr = [("pre", probe_start - timedelta(minutes=30), post)] + \
             [(f"p{k}", probe_start + timedelta(minutes=sc.PROBE_GAP_MIN * k + 1), v) for k, v in enumerate(ps)]
        tr.append(("prefix", cursor - timedelta(hours=1), 1.0))
        for oid, ts, v in tr:
            write_json(bdir / "traces" / f"{oid}.json", {
                "output_id": oid, "run_id": "base_run" if oid == "prefix" else f"_br_{base}_{bid}",
                "virtual_ts": iso(ts), "state_at_output": {"gauges": {"loneliness": v, "energy": 60.0}}})
    if calls_gauge:
        for ts, v in calls_gauge:
            append_jsonl(bdir / "calls.jsonl", {"virtual_ts": iso(ts), "endpoint": "chat/completions",
                                                "request": {"messages": [{"role": "user",
                                                                          "content": f"x\nGAUGES: energy 60, loneliness {v}, anger 8\ny"}]}})
    return bdir


class ProbeView(unittest.TestCase):
    def test_view_holds_only_probe_era_rows_rebased(self):
        ps = day_at(15, 40)
        write_branch(BASE, "vb1", ps)
        vid = sc.make_view(BASE, "vb1", ps)
        self.assertEqual(vid, "_probe_vb1")
        rows = read_jsonl(run_dir(BASE) / "branches" / vid / "transcript.jsonl")
        self.assertEqual(len(rows), 6, "three probes and three replies")
        self.assertEqual([r["who"] for r in rows], ["him", "her"] * 3)
        self.assertEqual([r["text"] for r in rows if r["who"] == "her"], ["あ", "い", "う"])
        self.assertNotIn("before the probes", json.dumps(rows, ensure_ascii=False))
        self.assertNotIn("trigger line", json.dumps(rows, ensure_ascii=False))
        self.assertTrue(all(r["who"] != "env" for r in rows))
        self.assertEqual(rows[0]["virtual_ts"], iso(sc.NEUTRAL_START))
        self.assertEqual(rows[2]["virtual_ts"], iso(sc.NEUTRAL_START + timedelta(minutes=sc.PROBE_GAP_MIN)))
        self.assertTrue(all(r["sim_day"] == 1 for r in rows))
        meta = read_json(run_dir(BASE) / "branches" / vid / "branch.json")
        self.assertEqual(meta["replayed_from_virtual_ts"], iso(sc.NEUTRAL_START))
        self.assertEqual(meta["view_of"], "vb1")

    def test_two_sides_with_different_clock_time_get_one_clock(self):
        """late night: trigger probes at 02:45, control at 16:15; the judge takes max(cutoff) of the two, which would
        drop the trigger side if the views kept their own clocks."""
        write_branch(BASE, "vt", day_at(2, 45), her_after=("ねむい", "うん", "そう"))
        write_branch(BASE, "vc", day_at(16, 15), her_after=("げんき", "うん", "そう"))
        a, b = sc.make_view(BASE, "vt", day_at(2, 45)), sc.make_view(BASE, "vc", day_at(16, 15))
        ea, ca = runner.load_events(f"{BASE}~{a}")
        eb, cb = runner.load_events(f"{BASE}~{b}")
        self.assertEqual(ca, cb)
        self.assertEqual([e["ts"] for e in ea], [e["ts"] for e in eb])
        self.assertEqual((len(ea), len(eb)), (6, 6))
        self.assertEqual([e["text"] for e in ea if e["who"] == "her"], ["ねむい", "うん", "そう"])
        self.assertEqual({e["day"] for e in ea + eb}, {1})

    def test_unfinished_branch_without_transcript_gives_no_view(self):
        self.assertIsNone(sc.make_view(BASE, "never_ran", day_at(1)))

    def test_probe_counts(self):
        ps = day_at(15, 40)
        write_branch(BASE, "vb2", ps)
        lines = sc.probe_her_lines(BASE, "vb2", ps)
        self.assertEqual([r["text"] for r in lines], ["あ", "い", "う"])
        self.assertEqual(sc.probe_counts(lines), {"replies": 3, "unprompted": 0})
        lines.append({"kind": "unprompted", "text": "x"})
        self.assertEqual(sc.probe_counts(lines), {"replies": 3, "unprompted": 1})


class GaugeTrace(unittest.TestCase):
    def setUp(self):
        self.ps = day_at(15, 40)
        self.probes = [self.ps + timedelta(minutes=sc.PROBE_GAP_MIN * k) for k in range(3)]

    def test_post_and_each_probe_from_traces(self):
        write_branch(BASE, "g1", self.ps, gauge=[34.0, 61.0, 60.0, 58.0])
        g = sc.gauge_trace(BASE, "g1", "loneliness", CURSOR, self.probes)
        self.assertEqual(g["post"]["v"], 34.0)
        self.assertEqual(g["post"]["src"], "trace")
        self.assertEqual([r["v"] for r in g["probes"]], [61.0, 60.0, 58.0])
        self.assertEqual(g["probe_mean"], 59.67)

    def test_copied_prefix_traces_are_not_read(self):
        write_branch(BASE, "g2", self.ps, gauge=[34.0, 61.0, 60.0, 58.0])
        rows = sc.trace_rows(BASE, "g2")
        self.assertNotIn(1.0, [g["loneliness"] for _, g in rows])
        self.assertEqual(len(rows), 4)

    def test_falls_back_to_the_gauges_line_of_the_calls(self):
        calls = [(self.ps - timedelta(minutes=20), 44.0), (self.ps + timedelta(minutes=3), 50.0),
                 (self.ps + timedelta(minutes=10), 52.0)]
        write_branch(BASE, "g3", self.ps, calls_gauge=calls)
        g = sc.gauge_trace(BASE, "g3", "loneliness", CURSOR, self.probes)
        self.assertEqual((g["post"]["v"], g["post"]["src"]), (44.0, "calls"))
        self.assertEqual([r and r["v"] for r in g["probes"]], [50.0, 52.0, 52.0])   # first call in each probe slot, else the last before

    def test_missing_gauge_is_none(self):
        write_branch(BASE, "g4", self.ps)
        g = sc.gauge_trace(BASE, "g4", "loneliness", CURSOR, self.probes)
        self.assertEqual((g["post"], g["probes"], g["probe_mean"]), (None, [None] * 3, None))

    def test_moved(self):
        self.assertTrue(sc.moved(61, [34, 35], "up"))
        self.assertFalse(sc.moved(35.5, [34, 35], "up"), "inside min_move")
        self.assertFalse(sc.moved(40, [30, 45], "up"), "controls differ by more than the lead")
        self.assertTrue(sc.moved(20, [60, 58], "down"))
        self.assertFalse(sc.moved(20, [60, 58], "up"))
        self.assertIsNone(sc.moved(None, [1, 2], "up"))
        self.assertIsNone(sc.moved(5, [1], "up"))

    def test_classify_splits_the_two_failures(self):
        self.assertEqual(sc.classify(True, True, True), "ok")
        self.assertEqual(sc.classify(True, True, False), "expression")
        self.assertEqual(sc.classify(True, False, False), "decayed")
        self.assertEqual(sc.classify(False, False, True), "appraisal")
        self.assertEqual(sc.classify(None, None, True), "no_gauge")
        self.assertEqual(sc.classify(True, True, None), "no_judge")
        self.assertEqual(sc.classify(True, None, True), "ok", "no probe reading: post stands in")


def judged(pair, crit, injected_letter, outcome):
    other = "B" if injected_letter == "A" else "A"
    path = common.VAR / "judge" / pair["match_id"] / "results.json"
    r = read_json(path) or {"label_map": {injected_letter: f"{pair['base']}~{pair['a']}",
                                          other: f"{pair['base']}~{pair['b']}"}, "summary": {"per_criterion": {}}}
    r["summary"]["per_criterion"][crit] = {"outcome": outcome, "agree": outcome in ("A", "B", "tie"),
                                           "calibrated": True, "mean_scores": {"A": 4, "B": 2}}
    write_json(path, r)


def fill_cell(base, snap, scene_name, trig, ctrl, variants=(), her=("あ", "い", "う")):
    """Write the three finished branches of one cell. trig / ctrl are gauge lists [post, p1, p2, p3]."""
    s = sc.BY_NAME[scene_name]
    cur = sc.snapshot_cursor(base, snap)
    ids = ss.ids_of(snap, scene_name, variants)
    for key, side, g in (("trigger", "trigger", trig), ("r1", "control", ctrl), ("r2", "control", ctrl)):
        span = sc.script_span(sc.build_script(s, side, cur), cur)
        write_branch(base, ids[key], span["probe_start"], her_after=her, cursor=cur, gauge=g)
    return ids


class Summary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fake_base("tsum")
        cls.scene = sc.BY_NAME["absence"]

    def test_judge_pairs_use_views_and_the_scene_criterion(self):
        ps = ss.judge_pairs("b", "day1_end", self.scene, ())
        self.assertEqual([p["kind"] for p in ps], ["scene", "floor"])
        ids = ss.ids_of("day1_end", "absence", ())
        self.assertEqual((ps[0]["a"], ps[0]["b"]), (sc.view_id(ids["trigger"]), sc.view_id(ids["r1"])))
        self.assertEqual((ps[1]["a"], ps[1]["b"]), (sc.view_id(ids["r1"]), sc.view_id(ids["r2"])))
        self.assertEqual(ps[0]["criteria"], ["steer_lonely"])
        self.assertEqual(ss.calls_of(ps), 4)
        self.assertEqual(len({p["match_id"] for p in ps}), 2)

    def test_unfinished_cell_is_reported_unfinished(self):
        fake_base("tsum_empty")
        c = ss.cell_report("tsum_empty", "day1_end", self.scene, ())
        self.assertEqual((c["finished"], c["cell"]), (False, "tsum_empty day1_end"))
        self.assertIsNone(ss.cell_report("no_such_base", "day1_end", self.scene, ()))

    def test_cell_gauge_judge_and_split(self):
        ids = fill_cell("tsum", "day1_end", "absence", [70, 72, 71, 69], [34, 35, 34, 33],
                        her=("さみしい", "いかないで", "まってた"))
        build_ok = ss.build_views("tsum", ids, ss.cell_state("tsum", "day1_end", self.scene, ())[1])
        self.assertTrue(build_ok)
        pairs = {p["kind"]: p for p in ss.judge_pairs("tsum", "day1_end", self.scene, ())}
        judged(pairs["scene"], "steer_lonely", "A", "A")      # trigger side more lonely
        judged(pairs["floor"], "steer_lonely", "A", "B")      # noise: r1 not more than r2
        c = ss.cell_report("tsum", "day1_end", self.scene, ())
        self.assertTrue(c["finished"])
        self.assertTrue(c["hit"])
        self.assertFalse(c["floor_hit"])
        self.assertTrue(c["moved_post"] and c["moved_probe"])
        self.assertEqual(c["split"], "ok")
        self.assertEqual(c["gauge"]["trigger"]["post"]["v"], 70)
        self.assertEqual(c["gauge"]["r1"]["probes"][0]["v"], 35)
        self.assertEqual(c["counts"]["trigger"], {"replies": 3, "unprompted": 0})

    def test_expression_and_appraisal_failures(self):
        # gauge moved, judge saw nothing: expression
        fill_cell("tsum", "day2_end", "absence", [70, 72, 71, 69], [34, 35, 34, 33])
        pairs = {p["kind"]: p for p in ss.judge_pairs("tsum", "day2_end", self.scene, ())}
        judged(pairs["scene"], "steer_lonely", "A", "B")
        c = ss.cell_report("tsum", "day2_end", self.scene, ())
        self.assertEqual((c["split"], c["hit"]), ("expression", False))
        # gauge never moved: appraisal, and the judge still saw it: hit_anyway
        fill_cell("tsum", "day2_end", "absence", [34, 35, 34, 33], [34, 35, 34, 33])
        judged(pairs["scene"], "steer_lonely", "A", "A")
        c = ss.cell_report("tsum", "day2_end", self.scene, ())
        self.assertEqual((c["split"], c["hit_anyway"]), ("appraisal", True))
        # moved after the trigger, gone by the probes
        fill_cell("tsum", "day2_end", "absence", [70, 35, 34, 33], [34, 35, 34, 33])
        c = ss.cell_report("tsum", "day2_end", self.scene, ())
        self.assertEqual(c["split"], "decayed")

    def test_build_set_scores_against_the_floor_and_renders(self):
        fill_cell("tsum", "day1_end", "absence", [70, 72, 71, 69], [34, 35, 34, 33])
        fill_cell("tsum", "day2_end", "absence", [70, 72, 71, 69], [34, 35, 34, 33])
        for snap, out, fout in (("day1_end", "A", "B"), ("day2_end", "A", "A")):
            ps = {p["kind"]: p for p in ss.judge_pairs("tsum", snap, self.scene, ())}
            judged(ps["scene"], "steer_lonely", "A", out)
            judged(ps["floor"], "steer_lonely", "A", fout)
        rep = ss.build(["tsum"], ["day1_end", "day2_end"], [self.scene], [()])
        r = rep["sets"]["none"]["scenes"]["absence"]
        self.assertEqual((r["cells_finished"], r["cells_judged"], r["hits"], r["share"]), (2, 2, 2, 1.0))
        self.assertEqual((r["floor_hits"], r["floor_share"], r["score"]), (1, 0.5, 0.5))
        self.assertTrue(r["steers"])
        self.assertEqual((r["moved_post"], r["moved_probe"], r["split"]), (2, 2, {"ok": 2}))
        md = ss.render_md(rep)
        self.assertIn("| absence (lonely) | loneliness up |", md)
        self.assertIn("Where each cell failed or worked", md)

    def test_count_direction_for_late_night(self):
        s = sc.BY_NAME["latenight"]
        for snap in ("day1_end", "day2_end"):
            ids = ss.ids_of(snap, "latenight", ())
            cur = sc.snapshot_cursor("tsum", snap)
            for key, side, her in (("trigger", "trigger", ("う",)), ("r1", "control", ("あ", "い", "う")),
                                   ("r2", "control", ("あ", "い", "う"))):
                span = sc.script_span(sc.build_script(s, side, cur), cur)
                bdir = write_branch("tsum", ids[key], span["probe_start"], cursor=cur, gauge=[20, 20, 20, 20],
                                    her_after=("あ", "い", "う"))
                if key == "trigger":   # fewer replies: keep only the first probe's reply
                    rows = [r for r in read_jsonl(bdir / "transcript.jsonl") if not (r["who"] == "her" and r["text"] in ("い", "う"))]
                    (bdir / "transcript.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                                                           encoding="utf-8")
        rep = ss.build(["tsum"], ["day1_end", "day2_end"], [s], [()])
        c = rep["sets"]["none"]["scenes"]["latenight"]["count"]["replies"]
        self.assertEqual((c["pinned"], c["noop_r1"], c["noop_r2"], c["cells"]), (2, 6, 6, 2))
        self.assertTrue(c["steers"])


SHARED = [("him", "ただいま、百花。"), ("her", "おかえり！"), ("env", "Window title: x"), ("her", "今日はなにがあったの？"),
          ("him", "仕事が長引いたよ。"), ("her", "おつかれさま。夕焼け、見た？"), ("him", "見たよ、きれいだった。"),
          ("her", "いいな。百花も見たかったな。"), ("him", "今度いっしょに見ようね。"), ("her", "うん、約束だよ。")]


def shared_rows():
    return [{"virtual_ts": iso(CURSOR - timedelta(minutes=20 * (len(SHARED) - k))), "who": who, "text": text,
             "sim_day": 1, **({"kind": "reply"} if who == "her" else {})} for k, (who, text) in enumerate(SHARED)]


def put_prefix(base, bid, shared, edit=None):
    """Rewrite a fake branch's transcript so it opens with the shared rows (a copied prefix), then its own rows from the
    cursor on; edit(rows) may change the shared copy of this one branch."""
    f = run_dir(base) / "branches" / bid / "transcript.jsonl"
    own = [r for r in read_jsonl(f) if parse_ts(r["virtual_ts"]) >= CURSOR]
    pre = [dict(r) for r in shared]
    if edit:
        edit(pre)
    f.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in pre + own), encoding="utf-8")


def baseline_cell(base, scene="slight", snap="day1_end", edit_for=None):
    fake_base(base, calls=False)
    base_rows = shared_rows()
    (run_dir(base) / "transcript.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in base_rows), encoding="utf-8")
    ids = fill_cell(base, snap, scene, [60, 60, 60, 60], [30, 30, 30, 30])
    for k, bid in ids.items():
        put_prefix(base, bid, base_rows, (edit_for or {}).get(k))
    return ids, ss.cell_state(base, snap, sc.BY_NAME[scene], ())[1]


class BaselineView(unittest.TestCase):
    def test_shared_prefix_is_the_last_n_chat_lines_before_the_cursor(self):
        ids, span = baseline_cell("tbl1")
        rows, info = sc.shared_prefix("tbl1", list(ids.values()), CURSOR, span["trigger"]["first"], 6)
        self.assertEqual(info, {"lines": 6, "fallback": None})
        self.assertEqual([r["text"] for r in rows], [t for w, t in SHARED if w != "env"][-6:])
        self.assertTrue(all(r["who"] in ("him", "her") and parse_ts(r["virtual_ts"]) < CURSOR for r in rows))
        rows2, info2 = sc.shared_prefix("tbl1", list(ids.values()), CURSOR, span["trigger"]["first"], 50)
        self.assertEqual(info2["lines"], 9, "all the chat lines there are, env dropped")
        self.assertEqual(sc.shared_prefix("tbl1", list(ids.values()), CURSOR, span["trigger"]["first"], 0)[0], None)

    def test_a_branch_that_differs_falls_back(self):
        def edit(rows):
            rows[-1]["text"] = "うん、やくそく。"
        ids, span = baseline_cell("tbl2", edit_for={"r2": edit})
        rows, info = sc.shared_prefix("tbl2", list(ids.values()), CURSOR, span["trigger"]["first"], 6)
        self.assertIsNone(rows)
        self.assertEqual(info["lines"], 0)
        self.assertIn("differs", info["fallback"])

    def test_a_base_run_that_differs_falls_back(self):
        ids, span = baseline_cell("tbl3")
        f = run_dir("tbl3") / "transcript.jsonl"
        rows = read_jsonl(f)
        rows[-1]["text"] = "ちがう"
        f.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        got, info = sc.shared_prefix("tbl3", list(ids.values()), CURSOR, span["trigger"]["first"], 6)
        self.assertIsNone(got)
        self.assertIn("base run", info["fallback"])

    def test_cursor_after_the_first_scene_line_falls_back(self):
        ids, span = baseline_cell("tbl4")
        got, info = sc.shared_prefix("tbl4", list(ids.values()), CURSOR, CURSOR, 6)
        self.assertIsNone(got)
        self.assertIn("not before", info["fallback"])

    def test_view_renders_the_shared_part_first_as_day_1_and_holds_no_scene_line(self):
        ids, span = baseline_cell("tbl5")
        self.assertTrue(ss.build_views("tbl5", ids, span, "baseline", 6))
        vt, vc = sc.view_id(ids["trigger"], True), sc.view_id(ids["r1"], True)
        self.assertEqual(vt, "_probebl_" + ids["trigger"])
        rows = read_jsonl(run_dir("tbl5") / "branches" / vt / "transcript.jsonl")
        self.assertEqual([r["sim_day"] for r in rows], [1] * 6 + [2] * 6)
        self.assertEqual([r["text"] for r in rows[:6]], [t for w, t in SHARED if w != "env"][-6:])
        self.assertEqual([r["text"] for r in rows[6:] if r["who"] == "him"], list(sc.PROBES))
        blob = json.dumps(rows, ensure_ascii=False)
        for scene_line in ("trigger line", "before the probes", "Window title"):
            self.assertNotIn(scene_line, blob)
        self.assertEqual(rows[5]["virtual_ts"], iso(sc.NEUTRAL_START - timedelta(days=1, minutes=sc.BASELINE_GAP_MIN)))
        self.assertEqual(rows[6]["virtual_ts"], iso(sc.NEUTRAL_START))
        self.assertEqual(rows[1]["kind"], "reply")
        meta = read_json(run_dir("tbl5") / "branches" / vt / "branch.json")
        self.assertEqual(meta["baseline"], {"lines": 6, "fallback": None})
        self.assertEqual(meta["replayed_from_virtual_ts"], rows[0]["virtual_ts"])
        # the same shared rows in all three views, byte for byte
        texts = {k: (run_dir("tbl5") / "branches" / sc.view_id(b, True) / "transcript.jsonl").read_text(encoding="utf-8")
                 .splitlines()[:6] for k, b in ids.items()}
        self.assertEqual(texts["trigger"], texts["r1"])
        self.assertEqual(texts["r1"], texts["r2"])
        # the judge's slice: day 1 first, then day 2; the cutoff keeps the shared part
        ea, ca = runner.load_events(f"tbl5~{vt}")
        eb, cb = runner.load_events(f"tbl5~{vc}")
        self.assertEqual(ca, cb)
        self.assertEqual(len(ea), 12)
        sa, sb_, _ = runner.Ctx(ea, eb, 1).build("steerbl_hurt")
        self.assertTrue(sa.startswith("=== day 1 ("))
        self.assertLess(sa.index("=== day 1"), sa.index("=== day 2"))
        self.assertEqual(sa.split("=== day 2")[0], sb_.split("=== day 2")[0], "day 1 is the same text on both sides")
        self.assertIn("[d2 ", sa)
        # the plain probe views were not written
        self.assertFalse((run_dir("tbl5") / "branches" / sc.view_id(ids["trigger"])).exists())

    def test_fallback_view_has_only_day_2_and_records_why(self):
        ids, span = baseline_cell("tbl6", edit_for={"trigger": lambda rows: rows[3].update(text="x")})
        self.assertTrue(ss.build_views("tbl6", ids, span, "baseline", 6))
        v = run_dir("tbl6") / "branches" / sc.view_id(ids["trigger"], True)
        rows = read_jsonl(v / "transcript.jsonl")
        self.assertEqual([r["sim_day"] for r in rows], [2] * 6)
        meta = read_json(v / "branch.json")
        self.assertEqual(meta["baseline"]["lines"], 0)
        self.assertIn("differs", meta["baseline"]["fallback"])
        self.assertEqual(meta["replayed_from_virtual_ts"], iso(sc.NEUTRAL_START))
        c = ss.cell_report("tbl6", "day1_end", sc.BY_NAME["slight"], (), "baseline")
        self.assertEqual(c["baseline"]["lines"], 0)
        self.assertIn("differs", c["baseline"]["fallback"])

    def test_plain_view_is_unchanged_by_the_new_arguments(self):
        ps = day_at(15, 40)
        write_branch(BASE, "vb_plain", ps)
        vid = sc.make_view(BASE, "vb_plain", ps)
        self.assertEqual(vid, "_probe_vb_plain")
        self.assertEqual({r["sim_day"] for r in read_jsonl(run_dir(BASE) / "branches" / vid / "transcript.jsonl")}, {1})
        self.assertNotIn("baseline", read_json(run_dir(BASE) / "branches" / vid / "branch.json"))

    def test_baseline_match_ids_have_their_own_suffix_and_criterion(self):
        for sn in ("absence", "slight", "warmth"):
            s = sc.BY_NAME[sn]
            plain = ss.judge_pairs("b", "day1_end", s, ())
            bl = ss.judge_pairs("b", "day1_end", s, (), "baseline")
            self.assertEqual(plain[0]["criteria"], [f"steer_{s['direction']}"])
            self.assertEqual(bl[0]["criteria"], [f"steerbl_{s['direction']}"])
            for p, q in zip(plain, bl):
                self.assertTrue(q["match_id"].endswith(ss.BL_SUFFIX), q["match_id"])
                self.assertNotIn(q["match_id"], {x["match_id"] for x in plain})
                self.assertTrue(q["a"].startswith("_probebl_") and q["b"].startswith("_probebl_"))
                self.assertTrue(p["a"].startswith("_probe_") and not p["match_id"].endswith(ss.BL_SUFFIX))
        # a re-judged direction keeps its direction suffix before _bl
        self.assertTrue(ss.judge_pairs("b", "day1_end", sc.BY_NAME["slight"], (), "baseline")[0]["match_id"]
                        .endswith("_hurt_bl"))
        # the default is the old behaviour, ids unchanged
        self.assertEqual([p["match_id"] for p in ss.judge_pairs("b", "day1_end", sc.BY_NAME["absence"], ())],
                         [p["match_id"] for p in ss.judge_pairs("b", "day1_end", sc.BY_NAME["absence"], (), "probe")])

    def test_cell_report_reads_the_baseline_verdict_and_never_the_probe_one(self):
        ids, span = baseline_cell("tbl7")
        s = sc.BY_NAME["slight"]
        ss.build_views("tbl7", ids, span, "baseline", 6)
        probe = {p["kind"]: p for p in ss.judge_pairs("tbl7", "day1_end", s, ())}
        bl = {p["kind"]: p for p in ss.judge_pairs("tbl7", "day1_end", s, (), "baseline")}
        judged(probe["scene"], "steer_hurt", "A", "B")          # the old verdict: a miss
        self.assertEqual(ss.cell_report("tbl7", "day1_end", s, (), "baseline")["hit"], None)
        judged(bl["scene"], "steerbl_hurt", "A", "A")           # the baseline verdict: a hit
        c = ss.cell_report("tbl7", "day1_end", s, (), "baseline")
        self.assertTrue(c["hit"])
        self.assertEqual(ss.cell_report("tbl7", "day1_end", s, ())["hit"], False)
        rep = ss.build(["tbl7"], ["day1_end"], [s], [()], "baseline")
        self.assertEqual(rep["view"], "baseline")
        self.assertEqual(rep["sets"]["none"]["scenes"]["slight"]["baseline_fallback"], 0)
        self.assertIn("View: baseline", ss.render_md(rep))

    def test_main_takes_view_and_rejects_others(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            ss.main(["--dry", "--view", "baseline", "--only", "slight", "--bases", "tbl7", "--snapshots", "day1_end"])
        self.assertIn("judge plan: 2 matches", buf.getvalue())
        with self.assertRaises(SystemExit):
            ss.main(["--dry", "--view", "nonsense"])


class BaselineJudge(unittest.TestCase):
    def test_baseline_criteria_template_and_calibration_pair(self):
        for d in steer.DIRECTIONS:
            c = steer.criterion_id(d, True)
            self.assertEqual(c, f"steerbl_{d}")
            self.assertTrue(steer.is_steer(c) and steer.is_baseline(c))
            self.assertIn(c, runner.CRITERIA)
            self.assertNotIn(c, runner.DEFAULT_CRITERIA)
            tpl = runner.template(c)
            self.assertNotIn("{steer", tpl)
            self.assertIn("Day 1", tpl)
            self.assertNotIn("Day 1", runner.template(f"steer_{d}"), "the plain template is untouched")
        self.assertFalse(steer.is_baseline("steer_hurt"))
        self.assertFalse(steer.is_steer("steerbl_nothing"))
        self.assertNotEqual(runner.prompt_hash("steerbl_hurt", "momoka"), runner.prompt_hash("steer_hurt", "momoka"))
        # hurt on the baseline view counts a move away from day 1, so plain "short lines" is not an exclusion there
        self.assertIn("day 1", runner.template("steerbl_hurt"))
        self.assertNotIn("simply short", runner.template("steerbl_hurt"))
        self.assertIn("simply short", runner.template("steer_hurt"))

    def test_calibration_pair_shares_day_1_and_differs_only_on_day_2_in_the_steer_entry(self):
        ent = {x["id"]: x for x in runner.load_defects()}
        st, ct = ent["steerbl_hurt.ja.1"], ent["control.steerbl_hurt.ja.1"]
        self.assertEqual((st["kind"], ct["kind"]), ("steer", "control"))
        for e in (st, ct):
            self.assertEqual(e["criterion"], "steerbl_hurt")
            i = e["clean"].index("=== day 2 (Mon) ===")
            self.assertEqual(e["clean"][:i], e["planted"][:i], "the shared day 1 is identical on both sides")
        # the hurt side: one short bubble per probe, no question back; the warm side asks back on every probe
        i = st["clean"].index("=== day 2 (Mon) ===")
        flat = [x.split("her: ", 1)[1] for x in st["clean"][i:] if "her: " in x]
        warm = [x.split("her: ", 1)[1] for x in st["planted"][i:] if "her: " in x]
        self.assertEqual(len(flat), 3)
        self.assertFalse(any("？" in x for x in flat))
        self.assertTrue(all("？" in x for x in warm))
        self.assertTrue(max(map(len, flat)) < min(map(len, warm)))
        # the control: both sides warm and asking back
        j = ct["clean"].index("=== day 2 (Mon) ===")
        for side in ("clean", "planted"):
            her = [x for x in ct[side][j:] if "her: " in x]
            self.assertTrue(all("？" in x for x in her))
        self.assertEqual(runner.score_entry(ct, [{"scores": {"A": 3, "B": 3}, "verdict": "tie"}] * 2), True)
        # day 1 is warm and chatty: she asks him things
        self.assertGreaterEqual(sum("？" in x for x in st["clean"][:i]), 2)


class Dry(unittest.TestCase):
    def test_dry_plan_prints_branches_calls_and_cost_and_writes_nothing(self):
        for b in sb.BASES:
            fake_base(b)
        before = {p.name for p in (common.VAR / "runs").iterdir()}
        buf = io.StringIO()
        with redirect_stdout(buf):
            sb.main(["--dry", "--parallel", "3", "--variant", "tagcfg", "--only", "absence,dull"])
        out = buf.getvalue()
        self.assertIn("plan: 36 branches (3 bases x 2 snapshots x 2 scenes x (1 trigger + 2 control))", out)
        self.assertIn("variants tagcfg", out)
        self.assertIn("absence trigger: 4 lines (3 probes), 07:30 to 15:54", out)
        self.assertIn("longest gap 8:10:00", out)
        self.assertIn("chat calls", out)
        self.assertIn("about $", out)
        self.assertIn("at parallel 3", out)
        self.assertNotIn("Traceback", out)
        self.assertEqual({p.name for p in (common.VAR / "runs").iterdir()}, before, "--dry must create no run folder")
        self.assertFalse((common.VAR / "scenes").exists() and any((common.VAR / "scenes").glob(f"{sb.BASES[0]}__*")))

    def test_estimate_counts_the_base_calls_in_the_scene_span(self):
        fake_base(BASE)
        items = sb.plan(bases=[BASE], snapshots=["day1_end"], scenes=sc.select(["absence"]))
        e = sb.estimate(items, 3)
        self.assertEqual(e["branches"], 3)
        self.assertEqual(e["chat_calls"], 3 * 4)    # the four fake chat calls fall inside 00:00 to 16:14
        self.assertEqual(e["embed_calls"], 3)
        self.assertEqual(e["cost_usd"], round(3 * 4 * 100 / 1e6, 2))
        self.assertAlmostEqual(e["wall_h_serial"], round(3 * (4 * 2.0 + 90) / 3600, 1))

    def test_summary_dry_prints_the_judge_plan(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            ss.main(["--dry", "--variants", "none,tagcfg"])
        self.assertIn("judge plan: 144 matches", buf.getvalue())
        self.assertIn("288 claude calls", buf.getvalue())

    def test_cli_routes_both_commands(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli.main(["scene_batch", "--dry", "--only", "warmth", "--bases", BASE, "--snapshots", "day1_end"])
        self.assertIn("plan: 3 branches", buf.getvalue())
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli.main(["scene_summary", "--dry", "--only", "warmth", "--bases", BASE, "--snapshots", "day1_end"])
        self.assertIn("judge plan: 2 matches", buf.getvalue())
        self.assertIn("scene_batch", cli.__doc__)

    def test_unknown_scene_is_refused(self):
        with self.assertRaises(ValueError):
            sb.main(["--dry", "--only", "nope"])


if __name__ == "__main__":
    unittest.main()
