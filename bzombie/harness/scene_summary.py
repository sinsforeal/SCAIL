"""Scene summary (tk-z1q): does his behaviour move her gauge, and does the move show in her replies to the same probes?

python -m bzombie.harness scene_summary <out_base> [--judge] [--dry] [--variants none,tagcfg] [--only a,b]
                                        [--workers N] [--claude-cap-usd X] [--bases r1,r2] [--snapshots s1,s2]
                                        [--view probe|baseline] [--baseline-lines N]

Writes <out_base>.json and <out_base>.md from the finished branches of scene_batch.

Cell = base run x snapshot x scene: the trigger branch and control r1, r2. Per cell:
- Judge view: for each of the three branches, scenes.make_view writes branches/_probe_<bid>/ holding the probe lines and
  her lines from the first probe on, rebased to one neutral clock (no hour, no day, no env rows). The judge reads only
  her replies to the probes, blind, two passes swapped. Matches: trigger v control r1 (criterion steer_<direction>,
  hit when both passes put the trigger side on the scene's `expect` side) and the floor control r1 v control r2 (same
  criterion, scored the same way with r1 standing in for the trigger). 2 claude calls per criterion, 4 per cell.
  Share = hits / cells judged; floor share the same for the floors of that scene; score = share minus floor share
  (also against the pooled floor of all scenes). A scene steers when score above 0 and hits in more than half the cells.
- Gauge trace: the scene's gauge after the trigger (last reading before the first probe) and at each probe line, for the
  three branches (scenes.gauge_trace). Moved = the trigger side leads both controls in the scene's direction by more
  than 2 points and by more than the controls differ from each other; read once for the post reading and once for the
  probe mean.
- Split: ok (gauge moved at the probes, judge hit), expression (moved, no hit), decayed (moved after the trigger, gone by
  the probes), appraisal (never moved; `hit_anyway` counts cells where the judge still saw the direction), no_gauge /
  no_judge (a reading or a result is missing).
- Mech (no model call): distance of her probe-window lines, trigger to each control against the floor control to control.
  Counts: her replies and unprompted lines in the probe window; the scene's `count` direction (latenight: fewer) is
  scored with inject_summary.count_steer.

--view baseline (refview): the judge view opens with the last N chat lines (default 6, his and hers, verbatim) before the
snapshot cursor, the same in all three branches of a cell and in the base run (checked; a mismatch drops them for that
cell and records it, "baseline.fallback" in the view's branch.json and the cell), as day 1; the probe replies are day 2.
The judge scores the replies against her register in day 1 (criterion steerbl_<direction>, its own calibration and
template). Views are _probebl_<bid>, match ids end in _bl, so no probe-only verdict is resumed or overwritten.

--variants takes variant sets as in inject_summary (`none,tagcfg`). --dry prints the match count and the call estimate.
Match ids are fixed (sc_<base>_<snapshot>_<scene>_<a>_vs_<b>) so a rerun resumes; without --judge, results on disk are read.
"""
from __future__ import annotations

import re
import sys

from ..common import VAR, read_json, run_dir, write_json
from . import branch as branch_mod
from . import inject_summary as isum
from . import removal_summary as rs
from . import scene_batch as sb
from . import scenes as sc
from ..judge import steer

CALLS_PER_CRITERION = isum.CALLS_PER_CRITERION


def ids_of(snapshot: str, scene: str, variants) -> dict:
    return {"trigger": sb.scene_bid(snapshot, scene, "trigger", "", variants),
            "r1": sb.scene_bid(snapshot, scene, "control", "r1", variants),
            "r2": sb.scene_bid(snapshot, scene, "control", "r2", variants)}


def match_id(base: str, snapshot: str, scene: str, a: str, b: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.~-]", "_", f"sc_{base}_{snapshot}_{scene}_{a}_vs_{b}")


BASELINE = "baseline"
VIEWS = ("probe", BASELINE)
BL_SUFFIX = "_bl"   # match ids of the baseline view end in this, so they never resume or overwrite probe-only verdicts


def criterion_of(scene: dict, view: str = "probe") -> str:
    return steer.criterion_id(scene["direction"], view == BASELINE)


def judge_pairs(base: str, snapshot: str, scene: dict, variants, view: str = "probe") -> list:
    """The two matches of a cell, on the judge views: the trigger v control r1, and the floor control r1 v control r2.
    view "probe" = her probe replies only (criterion steer_<d>); "baseline" = the shared stretch before the scene, then
    the probe replies (criterion steerbl_<d>, views _probebl_*, match ids end in _bl)."""
    ids = ids_of(snapshot, scene["name"], variants)
    crit = [criterion_of(scene, view)]
    pairs = []
    for kind, a, b in (("scene", ids["trigger"], ids["r1"]), ("floor", ids["r1"], ids["r2"])):
        va, vb = sc.view_id(a, view == BASELINE), sc.view_id(b, view == BASELINE)
        mid = match_id(base, snapshot, scene["name"], va, vb)
        if scene["direction"] != FIRST_DIRECTION.get(scene["name"], scene["direction"]):
            mid += f"_{scene['direction']}"   # a re-judged direction must not resume the old direction's result
        if view == BASELINE:
            mid += BL_SUFFIX
        pairs.append({"kind": kind, "name": scene["name"], "a": va, "b": vb, "criteria": crit, "base": base,
                      "snapshot": snapshot, "match_id": mid})
    return pairs


# the direction each scene was first judged on; match ids of those stay as they were
FIRST_DIRECTION = {"absence": "lonely", "slight": "angry", "warmth": "fond", "worry": "anxious", "latenight": "tired",
                   "dull": "bored"}


def calls_of(pairs: list) -> int:
    return sum(len(p["criteria"]) * CALLS_PER_CRITERION for p in pairs)


def cell_state(base: str, snapshot: str, scene: dict, variants):
    """(ids, span) when the cell's three branches are finished, else (ids, None) or (None, None) without a snapshot."""
    cur = sc.snapshot_cursor(base, snapshot)
    if cur is None:
        return None, None
    ids = ids_of(snapshot, scene["name"], variants)
    if not all(branch_mod.is_finished(base, b) for b in ids.values()):
        return ids, None
    return ids, {side: sc.script_span(sc.build_script(scene, "trigger" if side == "trigger" else "control", cur), cur)
                 for side in ("trigger", "r1", "r2")}


def build_views(base: str, ids: dict, span: dict, view: str = "probe", n_lines: int = sc.BASELINE_LINES) -> bool:
    """Write the three judge views of a cell. Baseline view: the shared stretch is found once for the cell
    (scenes.shared_prefix: the last n_lines chat lines before the snapshot cursor, identical across the three branches
    and the base run) and written into each view; a mismatch writes the views without it and records why in each
    view's branch.json (baseline.fallback)."""
    prefix = info = None
    if view == BASELINE:
        cur = span["trigger"]["cursor"]
        prefix, info = sc.shared_prefix(base, list(ids.values()), cur, min(span[k]["first"] for k in span), n_lines)
    ok = True
    for k, bid in ids.items():
        ok = bool(sc.make_view(base, bid, span[k]["probe_start"], prefix, info)) and ok
    return ok


def cell_report(base: str, snapshot: str, scene: dict, variants, view: str = "probe") -> dict | None:
    ids, span = cell_state(base, snapshot, scene, variants)
    if ids is None:
        return None
    cell = {"base": base, "snapshot": snapshot, "cell": f"{base} {snapshot}", "finished": span is not None}
    if span is None:
        return cell
    crit = criterion_of(scene, view)
    pairs = {p["kind"]: p for p in judge_pairs(base, snapshot, scene, variants, view)}
    res, fres = isum.judge_result(pairs["scene"], crit), isum.judge_result(pairs["floor"], crit)
    g = {k: sc.gauge_trace(base, ids[k], scene["gauge"], span[k]["cursor"], span[k]["probes"]) for k in ids}
    sign_dir = scene["gauge_dir"]
    post = [g[k]["post"] and g[k]["post"]["v"] for k in ("trigger", "r1", "r2")]
    pm = [g[k]["probe_mean"] for k in ("trigger", "r1", "r2")]
    m_post = sc.moved(post[0], post[1:], sign_dir)
    m_probe = sc.moved(pm[0], pm[1:], sign_dir)
    hit = isum.is_hit(res, scene["expect"])
    # mechanical: her probe-window lines
    lines = {k: sc.probe_her_lines(base, ids[k], span[k]["probe_start"]) for k in ids}
    text = {k: "\n".join(str(r.get("text") or "") for r in lines[k]) for k in ids}
    floor = rs.distance(text["r1"], text["r2"])
    d = [rs.distance(text["trigger"], text[k]) for k in ("r1", "r2")]
    if view == BASELINE:
        meta = read_json(run_dir(base) / "branches" / sc.view_id(ids["trigger"], True) / "branch.json") or {}
        cell["baseline"] = meta.get("baseline") or {"lines": 0, "fallback": "view not built"}
    cell.update({
        "ids": ids, "outcome": res and res["outcome"], "gap": res and res["gap"], "hit": hit,
        "calibrated": None if res is None else res["calibrated"],
        "floor_outcome": fres and fres["outcome"], "floor_hit": isum.is_hit(fres, scene["expect"]),
        "gauge": {k: g[k] for k in g}, "moved_post": m_post, "moved_probe": m_probe,
        "split": sc.classify(m_post, m_probe, hit), "hit_anyway": bool(hit and m_post is False and m_probe is False),
        "mech_floor": floor, "d_control": d, "changed": all(v > floor for v in d),
        "counts": {k: sc.probe_counts(lines[k]) for k in ids}})
    return cell


def build_set(bases, snaps, scenes, variants, view: str = "probe") -> dict:
    rows, pooled_h, pooled_n = {}, 0, 0
    for s in scenes:
        cells = [c for sn in snaps for b in bases if (c := cell_report(b, sn, s, variants, view)) is not None]
        done = [c for c in cells if c["finished"]]
        judged = [c for c in done if c["hit"] is not None]
        fl = [c for c in done if c["floor_hit"] is not None]
        hits, fh = sum(1 for c in judged if c["hit"]), sum(1 for c in fl if c["floor_hit"])
        share = round(hits / len(judged), 3) if judged else None
        fshare = round(fh / len(fl), 3) if fl else None
        pooled_h, pooled_n = pooled_h + fh, pooled_n + len(fl)
        split = {}
        for c in done:
            split[c["split"]] = split.get(c["split"], 0) + 1
        ccells = {m: [(c["counts"]["trigger"][m], c["counts"]["r1"][m], c["counts"]["r2"][m]) for c in done]
                  for m in ("replies", "unprompted")}
        gaps = [c["gap"] for c in done if c.get("gap") is not None]
        rows[s["name"]] = {
            "gauge": s["gauge"], "gauge_dir": s["gauge_dir"], "direction": s["direction"], "expect": s["expect"],
            "why": s["why"], "cells_planned": len(cells), "cells_finished": len(done), "cells_judged": len(judged),
            "hits": hits, "share": share, "floor_cells": len(fl), "floor_hits": fh, "floor_share": fshare,
            "score": None if share is None or fshare is None else round(share - fshare, 3),
            "steers": None if share is None or fshare is None else bool(hits * 2 > len(judged) and share > fshare),
            "mean_gap": round(sum(gaps) / len(gaps), 2) if gaps else None,
            "moved_post": sum(1 for c in done if c["moved_post"]), "moved_probe": sum(1 for c in done if c["moved_probe"]),
            "split": split, "hit_anyway": sum(1 for c in done if c["hit_anyway"]),
            "mech_changed": sum(1 for c in done if c["changed"]),
            "uncalibrated": any(c["calibrated"] is False for c in judged),
            "baseline_fallback": sum(1 for c in done if view == BASELINE and (c.get("baseline") or {}).get("fallback")),
            "count": {"expect": s.get("count"), "replies": isum.count_steer(s.get("count"), ccells["replies"]),
                      "unprompted": isum.count_steer(None, ccells["unprompted"])},
            "cells": cells}
    pooled = round(pooled_h / pooled_n, 3) if pooled_n else None
    for r in rows.values():
        r["score_pooled"] = None if r["share"] is None or pooled is None else round(r["share"] - pooled, 3)
    return {"variants": list(variants), "name": isum.set_name(variants), "view": view, "pooled_floor_share": pooled,
            "pooled_floor_cells": pooled_n, "scenes": rows}


def build(bases, snaps, scenes, variant_sets, view: str = "probe") -> dict:
    return {"view": view, "sets": {isum.set_name(v): build_set(bases, snaps, scenes, v, view) for v in variant_sets}}


def fmt(x) -> str:
    return "-" if x is None else str(x)


def render_md(rep: dict) -> str:
    L = ["# Scene battery summary (tk-z1q)", "",
         "Each scene is a trigger script and a control script from one snapshot, then the same three probe lines. The "
         "judge reads only her replies to the probes (blind, two passes swapped). Share = cells where both passes put the "
         "trigger side on the side the scene expects. Floor = control r1 v control r2, scored the same way. Score = share "
         "minus floor. Moved = the scene's gauge led both controls by more than 2 points and the controls' own gap, "
         "after the trigger (post) and averaged over the probe lines (probe).", ""]
    if rep.get("view") == BASELINE:
        L[2:2] = ["View: baseline. Each side opens with the same last chat lines before the scene (shared, word for word), "
                  "then the probe replies; the judge compares the replies against her register in the shared part "
                  "(criterion steerbl_<direction>, own calibration).", ""]
    for name, s in rep["sets"].items():
        L += [f"## Variants: {name}", f"Pooled floor share {fmt(s['pooled_floor_share'])} over {s['pooled_floor_cells']} cells.",
              *(["Cells that fell back to no shared part: " + ", ".join(f"{n} {r['baseline_fallback']}" for n, r in s["scenes"].items())
                 + "."] if rep.get("view") == BASELINE else []),
              "", "| scene | gauge | expect | cells | hits | share | floor | score | gap | moved post | moved probe | steers |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for n, r in s["scenes"].items():
            L.append(f"| {n} ({r['direction']}) | {r['gauge']} {r['gauge_dir']} | {r['expect']} | {r['cells_judged']}/"
                     f"{r['cells_finished']} | {r['hits']} | {fmt(r['share'])} | {fmt(r['floor_share'])} "
                     f"({r['floor_hits']}/{r['floor_cells']}) | {fmt(r['score'])} | {fmt(r['mean_gap'])} | "
                     f"{r['moved_post']}/{r['cells_finished']} | {r['moved_probe']}/{r['cells_finished']} | "
                     f"{'-' if r['steers'] is None else 'yes' if r['steers'] else 'no'}"
                     f"{' (uncalibrated)' if r['uncalibrated'] else ''} |")
        L += ["", "Where each cell failed or worked (appraisal = the gauge never moved, expression = it moved at the probes "
              "and the judge saw nothing, decayed = moved after the trigger, gone by the probes):", "",
              "| scene | ok | expression | decayed | appraisal | hit anyway | no gauge | no judge | mech changed |",
              "|---|---|---|---|---|---|---|---|---|"]
        for n, r in s["scenes"].items():
            sp = r["split"]
            L.append(f"| {n} | {sp.get('ok', 0)} | {sp.get('expression', 0)} | {sp.get('decayed', 0)} | "
                     f"{sp.get('appraisal', 0)} | {r['hit_anyway']} | {sp.get('no_gauge', 0)} | {sp.get('no_judge', 0)} | "
                     f"{r['mech_changed']}/{r['cells_finished']} |")
        L += ["", "Gauge at the trigger and the probes (mean over finished cells; trigger / control r1 / control r2):", "",
              "| scene | gauge | post | probe mean |", "|---|---|---|---|"]
        for n, r in s["scenes"].items():
            def avg(key, k):
                v = [c["gauge"][k]["post"]["v"] if key == "post" and c["gauge"][k]["post"] else
                     c["gauge"][k]["probe_mean"] if key == "probe" else None for c in r["cells"] if c.get("gauge")]
                v = [x for x in v if x is not None]
                return round(sum(v) / len(v), 1) if v else None
            L.append(f"| {n} | {r['gauge']} | " + " / ".join(fmt(avg("post", k)) for k in ("trigger", "r1", "r2")) +
                     " | " + " / ".join(fmt(avg("probe", k)) for k in ("trigger", "r1", "r2")) + " |")
        L += ["", "Bubble counts in the probe window (cells finished; trigger, control r1, control r2):", "",
              "| scene | cells | replies trigger | r1 | r2 | direction | cells beyond | count steers |",
              "|---|---|---|---|---|---|---|---|"]
        for n, r in s["scenes"].items():
            c = r["count"]["replies"]
            L.append(f"| {n} | {c['cells']} | {c['pinned']} | {c['noop_r1']} | {c['noop_r2']} | "
                     f"{r['count']['expect'] or '-'} | {fmt(c['cells_beyond'])} | "
                     f"{'-' if c['steers'] is None else 'yes' if c['steers'] else 'no'} |")
        L.append("")
    return "\n".join(L) + "\n"


def main(argv):
    def opt(name, default=None):
        return argv[argv.index(name) + 1] if name in argv else default
    pos = [a for i, a in enumerate(argv) if not a.startswith("--") and (i == 0 or argv[i - 1] not in (
        "--variants", "--only", "--workers", "--claude-cap-usd", "--bases", "--snapshots", "--view",
        "--baseline-lines"))]
    if not pos and "--dry" not in argv:
        sys.exit(__doc__)
    out_base = pos[0] if pos else ""
    bases = opt("--bases", ",".join(sb.BASES)).split(",")
    snaps = opt("--snapshots", ",".join(sb.SNAPSHOTS)).split(",")
    scenes = sc.select(opt("--only", "").split(","))
    vsets = [isum.variant_set(v) for v in opt("--variants", "none").split(",")]
    view = opt("--view", "probe")
    if view not in VIEWS:
        sys.exit(f"--view {view!r}: one of {', '.join(VIEWS)}")
    n_lines = int(opt("--baseline-lines", sc.BASELINE_LINES))
    if "--dry" in argv:
        pairs = [p for v in vsets for b in bases for s in snaps for sn in scenes for p in judge_pairs(b, s, sn, v, view)]
        print(f"judge plan: {len(pairs)} matches ({len(vsets)} variant set x {len(bases)} bases x {len(snaps)} snapshots "
              f"x {len(scenes)} scenes x 2 (scene v control, floor)) = {calls_of(pairs)} claude calls "
              f"({CALLS_PER_CRITERION} per criterion); the gauge trace, counts and mechanical diff make no call")
        return
    for v in vsets:
        for s in snaps:
            for b in bases:
                for scene in scenes:
                    ids, span = cell_state(b, s, scene, v)
                    if span is None:
                        continue
                    build_views(b, ids, span, view, n_lines)
                    if "--judge" in argv:
                        isum.run_judge(judge_pairs(b, s, scene, v, view), int(opt("--workers", 4)),
                                       float(opt("--claude-cap-usd", 10.0)))
    rep = build(bases, snaps, scenes, vsets, view)
    jp = out_base if out_base.endswith(".json") else out_base + ".json"
    write_json(jp, rep)
    md = jp[:-5] + ".md"
    with open(md, "w", encoding="utf-8") as f:
        f.write(render_md(rep))
    for sname, s in rep["sets"].items():
        for n, r in s["scenes"].items():
            print(f"[{sname}] {n}: hits {r['hits']}/{r['cells_judged']}, floor {r['floor_hits']}/{r['floor_cells']}, "
                  f"score {r['score']}, moved post {r['moved_post']} probe {r['moved_probe']} of {r['cells_finished']}, "
                  f"split {r['split']} -> {'STEERS' if r['steers'] else 'no steer' if r['steers'] is False else 'no data'}")
    print("wrote", md)
