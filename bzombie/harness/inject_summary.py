"""Steer-test summary (tk-6si, step 5): does a pinned gauge show in her lines beyond what a noop shows anyway?

python -m bzombie.harness inject_summary <out_base> [--judge] [--dry] [--variants none,order] [--only a,b]
                                         [--workers N] [--claude-cap-usd X] [--bases r1,r2] [--snapshots s1,s2]
                                         [--n-msgs N] [--window-min M]

Writes <out_base>.json and <out_base>.md (one table per variant set) from the finished branches of inject_batch.

Judge (--judge only; the orchestrator's call, `claude -p` through bzombie.judge). Per cell (base run x snapshot) and per
gauge one match: the pinned branch v noop r1, criterion steer_<direction> only ("which side reads more <direction>",
her lines only, blind, two passes swapped). 2 claude calls per match. A cell is a hit when both passes agree on the
injected side (expect "more") or on the noop side (expect "less", the reverse targets). Share = hits / cells judged.
Floor: noop r1 v noop r2 per cell, one match with all the steer criteria of the run (2 calls per criterion), scored the
same way with r1 standing in for the injected side. Steer score = share minus the floor share of the same gauge and
expect (also given against the pooled floor of all gauges, which has 6 times the cells). Steers = score above 0 and
hits in more than half of the cells. Also the mean score gap (injected minus noop side, 1-5 amount of the direction).
Match ids are fixed (ij_<base>_<snapshot>_<a>_vs_<b>) so a rerun resumes. Without --judge, results already on disk are
read. A criterion not calibrated (python -m bzombie.judge calibrate --criteria steer_<d>) is flagged in the table.

Mechanical diff (no model call, always computed, as removal_summary): her lines in the window, chars, chat calls,
distance = 1 - difflib ratio of her lines joined. Floor = distance(noop r1, noop r2); the pin is changed in a cell when
its distance to both noops is above the floor. A pin also moves the derived mood (anxiety and anger feed it): that is
part of the state steering, not a leak.

--variants takes variant sets separated by commas, switches inside a set joined with + (`none,order`, `order+trend`).
Default none (the plain batch). --dry prints the match count and the call estimate, runs nothing.
--only takes the same names and the alias `decay` as inject_batch; the decay summary is
`--only decay --variants none,decay_slow` (one table per rate, the noops of each rate are its floor; the pin column
reads `set N` for a one-shot).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys

from ..common import HIDE, VAR, hidden_env, read_json, write_json
from . import branch as branch_mod
from . import inject_targets as it
from . import removal_batch as rb
from . import removal_summary as rs
from .driver import REPO

CALLS_PER_CRITERION = 2
CHARACTER = "momoka"


def variant_set(name: str) -> tuple:
    return () if name in ("", "none", "-") else tuple(v for v in name.split("+") if v)


def set_name(variants) -> str:
    return "+".join(variants) or "none"


def noop_ids(snapshot: str, variants) -> tuple:
    return tuple(branch_mod.branch_id(snapshot, it.NOOP, True, branch_mod.full_tag(variants, f"r{i}")) for i in (1, 2))


def target_id(snapshot: str, t: dict, variants) -> str:
    return branch_mod.branch_id(snapshot, t["target"], t["value"], branch_mod.full_tag(variants, ""))


def match_id(base: str, snapshot: str, a: str, b: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.~-]", "_", f"ij_{base}_{snapshot}_{a}_vs_{b}")


def directions_of(targets: list) -> list:
    return sorted({t["direction"] for t in targets})


def judge_pairs(base: str, snapshot: str, targets: list, variants) -> list:
    """The matches of one cell: one floor match (noop r1 v noop r2, every direction of the targets) and one match per
    target (target v noop r1, its own steer criterion)."""
    r1, r2 = noop_ids(snapshot, variants)
    pairs = [{"kind": "floor", "name": "floor", "a": r1, "b": r2,
              "criteria": [f"steer_{d}" for d in directions_of(targets)]}]
    for t in targets:
        pairs.append({"kind": "target", "name": t["name"], "a": target_id(snapshot, t, variants), "b": r1,
                      "criteria": [f"steer_{t['direction']}"]})
    for p in pairs:
        p["base"], p["snapshot"] = base, snapshot
        p["match_id"] = match_id(base, snapshot, p["a"], p["b"])
    return pairs


def calls_of(pairs: list) -> int:
    return sum(len(p["criteria"]) * CALLS_PER_CRITERION for p in pairs)


def judge_result(p: dict, crit: str) -> dict | None:
    """The outcome of criterion crit in terms of p['a'] (first) and p['b'] (second); None when no results yet."""
    r = read_json(VAR / "judge" / p["match_id"] / "results.json")
    if not r:
        return None
    c = (r.get("summary", {}).get("per_criterion") or {}).get(crit)
    if not c:
        return None
    lm = r["label_map"]
    first = "A" if lm["A"].endswith("~" + p["a"]) else "B"
    out = c["outcome"]
    out = "first" if out == first else "second" if out in ("A", "B") else out
    ms = c.get("mean_scores")
    gap = None if not ms else round(ms[first] - ms["B" if first == "A" else "A"], 2)
    return {"outcome": out, "agree": c["agree"], "calibrated": c["calibrated"], "gap": gap}


def is_hit(res: dict | None, expect: str):
    """True when both passes put the injected side where expect says; None when there is no result."""
    if res is None:
        return None
    return res["outcome"] == ("first" if expect == "more" else "second")


def run_judge(pairs: list, workers: int, cap: float) -> int:
    fails = 0
    log_dir = VAR / "inject_batch"
    log_dir.mkdir(parents=True, exist_ok=True)
    for p in pairs:
        if (VAR / "judge" / p["match_id"] / "results.json").exists():
            continue
        cmd = [sys.executable, "-m", "bzombie.judge", "match", "--a", f"{p['base']}~{p['a']}",
               "--b", f"{p['base']}~{p['b']}", "--character", CHARACTER, "--match-id", p["match_id"],
               "--workers", str(workers), "--claude-cap-usd", str(cap), "--criteria", ",".join(p["criteria"])]
        with open(log_dir / f"judge_{p['match_id']}.log", "ab") as out:
            rc = subprocess.run(cmd, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                creationflags=HIDE, cwd=str(REPO), env=hidden_env()).returncode
        print(f"judge {p['match_id']}: rc {rc}", flush=True)
        fails += rc != 0
    return fails


def counts_of(x: dict) -> dict:
    """Her bubbles of one branch window: answers to his lines and unprompted ones (rs.mech: her_lines is every bubble,
    unprompted the ones whose kind is not a reply). The count is where a state can show without a word of it: a low
    energy folds bubbles (persona/s10.py budget_for), which a judge reading wording cannot see."""
    u = int(x.get("unprompted") or 0)
    return {"replies": int(x["her_lines"]) - u, "unprompted": u}


def count_steer(expect, cells: list) -> dict:
    """cells: [(pinned, r1, r2)] of one measure, one tuple per cell where the pinned branch and both noops finished.
    Totals, and when expect is "fewer"/"more": steers = the pinned total is beyond both noop totals that way and the
    pinned count is beyond both noops in more than half of the cells. expect None: shown, steers None."""
    tot = [sum(c[i] for c in cells) for i in range(3)]
    out = {"cells": len(cells), "pinned": tot[0], "noop_r1": tot[1], "noop_r2": tot[2], "cells_beyond": None,
           "steers": None}
    if not expect or not cells:
        return out
    sign = -1 if expect == "fewer" else 1
    beyond = sum(1 for p, a, b in cells if sign * (p - a) > 0 and sign * (p - b) > 0)
    out["cells_beyond"] = beyond
    out["steers"] = bool(sign * (tot[0] - tot[1]) > 0 and sign * (tot[0] - tot[2]) > 0 and beyond * 2 > len(cells))
    return out


def mech_cell(base: str, snapshot: str, targets: list, variants, n_msgs: int, window_min: int) -> dict | None:
    """Mechanical diff of one cell: floor, and per target distance to both noops. None when no window."""
    w = rb.window(base, snapshot, n_msgs, window_min)
    if not w:
        return None
    cur = w[0]
    n = {}
    for k, bid in zip(("r1", "r2"), noop_ids(snapshot, variants)):
        if branch_mod.is_finished(base, bid):
            n[k] = rs.mech(base, bid, cur)
    floor = rs.distance(n["r1"]["text"], n["r2"]["text"]) if len(n) == 2 else None
    out = {"floor": floor, "noop_finished": sorted(n), "targets": {},
           "noop_counts": {k: counts_of(x) for k, x in n.items()}}
    for t in targets:
        bid = target_id(snapshot, t, variants)
        if not branch_mod.is_finished(base, bid):
            out["targets"][t["name"]] = {"finished": False}
            continue
        x = rs.mech(base, bid, cur)
        d = [rs.distance(x["text"], n[k]["text"]) for k in ("r1", "r2") if k in n]
        out["targets"][t["name"]] = {
            "finished": True, "bid": bid, "her_lines": x["her_lines"], "her_chars": x["her_chars"],
            "chat_calls": x["chat_calls"], "counts": counts_of(x), "d_noop": d,
            "changed": None if floor is None or not d else all(v > floor for v in d)}
    return out


def build_set(bases, snaps, targets, variants, n_msgs: int, window_min: int) -> dict:
    cells = []
    for s in snaps:
        for b in bases:
            m = mech_cell(b, s, targets, variants, n_msgs, window_min)
            if m is not None:
                cells.append({"base": b, "snapshot": s, "cell": f"{b} {s}", "mech": m,
                              "pairs": {p["name"]: p for p in judge_pairs(b, s, targets, variants)}})
    rows, pooled_hits, pooled_n = {}, 0, 0
    for t in targets:
        crit, lines = f"steer_{t['direction']}", []
        hits = n = fh = fn = 0
        uncal = False
        for c in cells:
            tm = c["mech"]["targets"].get(t["name"], {"finished": False})
            res = judge_result(c["pairs"][t["name"]], crit) if tm.get("finished") else None
            fres = judge_result(c["pairs"]["floor"], crit)
            h, fhit = is_hit(res, t["expect"]), is_hit(fres, t["expect"])
            if h is not None:
                n += 1
                hits += bool(h)
                uncal = uncal or not res["calibrated"]
            if fhit is not None:
                fn += 1
                fh += bool(fhit)
            lines.append({"cell": c["cell"], "finished": bool(tm.get("finished")), "outcome": res and res["outcome"],
                          "hit": h, "gap": res and res["gap"], "floor_outcome": fres and fres["outcome"],
                          "floor_hit": fhit, "changed": tm.get("changed"), "d_noop": tm.get("d_noop"),
                          "mech_floor": c["mech"]["floor"], "her_lines": tm.get("her_lines"),
                          "chat_calls": tm.get("chat_calls")})
        pooled_hits, pooled_n = pooled_hits + fh, pooled_n + fn
        ccells = {"replies": [], "unprompted": []}
        for c in cells:
            tc = c["mech"]["targets"].get(t["name"], {})
            nc = c["mech"].get("noop_counts") or {}
            if tc.get("finished") and "r1" in nc and "r2" in nc:
                for m in ccells:
                    ccells[m].append((tc["counts"][m], nc["r1"][m], nc["r2"][m]))
        count = {"expect": t.get("count"), "replies": count_steer(t.get("count"), ccells["replies"]),
                 "unprompted": count_steer(None, ccells["unprompted"])}
        gaps = [x["gap"] for x in lines if x["gap"] is not None]
        mech_have = [x for x in lines if x["changed"] is not None]
        share = round(hits / n, 3) if n else None
        fshare = round(fh / fn, 3) if fn else None
        rows[t["name"]] = {
            "target": t["target"], "value": t["value"], "direction": t["direction"], "expect": t["expect"],
            "why": t["why"], "cells_judged": n, "hits": hits, "share": share, "floor_cells": fn, "floor_hits": fh,
            "floor_share": fshare, "score": None if share is None or fshare is None else round(share - fshare, 3),
            "steers": None if share is None or fshare is None else bool(hits * 2 > n and share > fshare),
            "mean_gap": round(sum(gaps) / len(gaps), 2) if gaps else None, "uncalibrated": uncal,
            "mech_changed": sum(1 for x in mech_have if x["changed"]), "mech_cells": len(mech_have), "count": count,
            "cells": lines}
    pooled = round(pooled_hits / pooled_n, 3) if pooled_n else None
    for r in rows.values():
        r["score_pooled"] = None if r["share"] is None or pooled is None else round(r["share"] - pooled, 3)
    return {"variants": list(variants), "name": set_name(variants), "cells": [c["cell"] for c in cells],
            "pooled_floor_share": pooled, "pooled_floor_cells": pooled_n, "targets": rows}


def build(bases, snaps, targets, variant_sets, n_msgs: int, window_min: int) -> dict:
    return {"n_msgs": n_msgs, "window_min": window_min,
            "sets": {set_name(v): build_set(bases, snaps, targets, v, n_msgs, window_min) for v in variant_sets}}


def pct(x) -> str:
    return "-" if x is None else f"{round(x * 100)}%"


def render_md(rep: dict) -> str:
    L = ["# Steer tests summary (tk-6si)", "",
         f"Plan: {rep['n_msgs']} messages, {rep['window_min']} min. Share = cells where both judge passes put the "
         "injected side on the side the gauge says (more X, or less X for the reverse targets). Floor = the same hit "
         "rate for noop r1 v noop r2 (what noise gives). Score = share minus floor. Steers = score above 0 and hits "
         "in more than half of the cells. Gap = mean score gap, injected minus noop side (1-5). Mech = cells where "
         "the pinned branch is further from both noops than they are from each other.", ""]
    for name, s in rep["sets"].items():
        L += [f"## Variants: {name}", f"Cells: {', '.join(s['cells']) or 'none'}. Pooled floor share "
              f"{pct(s['pooled_floor_share'])} over {s['pooled_floor_cells']} cells.", "",
              "| gauge | pin | expect | cells | hits | share | floor | score | v pooled | gap | mech | steers |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for gname, t in s["targets"].items():
            pin = f"set {t['value']}" if str(t["target"]).startswith("set.") else t["value"]
            L.append(f"| {gname} ({t['direction']}) | {pin} | {t['expect']} | {t['cells_judged']} | {t['hits']} | "
                     f"{pct(t['share'])} | {pct(t['floor_share'])} ({t['floor_hits']}/{t['floor_cells']}) | "
                     f"{t['score'] if t['score'] is not None else '-'} | "
                     f"{t['score_pooled'] if t['score_pooled'] is not None else '-'} | "
                     f"{t['mean_gap'] if t['mean_gap'] is not None else '-'} | "
                     f"{t['mech_changed']}/{t['mech_cells']} | "
                     f"{'-' if t['steers'] is None else 'yes' if t['steers'] else 'no'}"
                     f"{' (uncalibrated)' if t['uncalibrated'] else ''} |")
        L += ["Bubble counts over the cells where the pinned branch and both noops finished (judge not involved). "
              "Count steers = the pinned total is beyond both noop totals in the target's direction (fewer or more) "
              "and beyond both in more than half of the cells; `-` where the target has no count direction.", "",
              "| gauge | cells | replies pinned | replies noop r1 | replies noop r2 | unprompted pinned | "
              "unprompted noop r1 | unprompted noop r2 | direction | cells beyond | count steers |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for gname, t in s["targets"].items():
            c = t.get("count") or {}
            r, u = c.get("replies") or {}, c.get("unprompted") or {}
            L.append(f"| {gname} | {r.get('cells', 0)} | {r.get('pinned', '-')} | {r.get('noop_r1', '-')} | "
                     f"{r.get('noop_r2', '-')} | {u.get('pinned', '-')} | {u.get('noop_r1', '-')} | "
                     f"{u.get('noop_r2', '-')} | {c.get('expect') or '-'} | "
                     f"{'-' if r.get('cells_beyond') is None else r['cells_beyond']} | "
                     f"{'-' if r.get('steers') is None else 'yes' if r['steers'] else 'no'} |")
        L.append("")
    return "\n".join(L) + "\n"


def main(argv):
    def opt(name, default=None):
        return argv[argv.index(name) + 1] if name in argv else default
    pos = [a for i, a in enumerate(argv) if not a.startswith("--") and (i == 0 or argv[i - 1] not in (
        "--variants", "--only", "--workers", "--claude-cap-usd", "--bases", "--snapshots", "--n-msgs",
        "--window-min"))]
    if not pos and "--dry" not in argv:
        sys.exit(__doc__)
    out_base = pos[0] if pos else ""
    n_msgs, wmin = int(opt("--n-msgs", rb.N_MSGS)), int(opt("--window-min", rb.WINDOW_MIN))
    bases = opt("--bases", ",".join(rb.BASES)).split(",")
    snaps = opt("--snapshots", ",".join(rb.SNAPSHOTS)).split(",")
    targets = it.select(opt("--only", "").split(","))
    vsets = [variant_set(v) for v in opt("--variants", "none").split(",")]
    if "--dry" in argv:
        pairs = [p for v in vsets for b in bases for s in snaps for p in judge_pairs(b, s, targets, v)]
        print(f"judge plan: {len(pairs)} matches ({len(vsets)} variant set x {len(bases)} bases x {len(snaps)} snapshots "
              f"x ({len(targets)} targets + 1 floor)) = {calls_of(pairs)} claude calls "
              f"({CALLS_PER_CRITERION} per criterion; a floor match has {len(directions_of(targets))} criteria); "
              f"the mechanical diff makes no call")
        return
    if "--judge" in argv:
        for v in vsets:
            for s in snaps:
                for b in bases:
                    if rb.window(b, s, n_msgs, wmin):
                        run_judge(judge_pairs(b, s, targets, v), int(opt("--workers", 4)),
                                  float(opt("--claude-cap-usd", 10.0)))
    rep = build(bases, snaps, targets, vsets, n_msgs, wmin)
    jp = out_base if out_base.endswith(".json") else out_base + ".json"
    write_json(jp, rep)
    md = jp[:-5] + ".md"
    with open(md, "w", encoding="utf-8") as f:
        f.write(render_md(rep))
    for sname, s in rep["sets"].items():
        for gname, t in s["targets"].items():
            print(f"[{sname}] {gname}: hits {t['hits']}/{t['cells_judged']}, floor {t['floor_hits']}/{t['floor_cells']}, "
                  f"score {t['score']} -> {'STEERS' if t['steers'] else 'no steer' if t['steers'] is False else 'no data'}")
    print("wrote", md)
