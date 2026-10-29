"""Removal-test summary (tk-lmv, stage 6): did a target change her beyond what a noop changes anyway?

python -m bzombie.harness removal_summary <out_base> [--judge] [--dry] [--vs both|noop|base] [--workers N]
                                          [--claude-cap-usd X] [--bases r1,r2] [--snapshots s1,s2]

Writes <out_base>.json and <out_base>.md (one table per target) from the finished branches of removal_batch.

Mechanical diff (no model call, always computed). Per cell (base run x snapshot) and branch: her lines in the
window, her characters, unprompted lines, chat calls, prompt tokens, booked cost, calls per llm role. Distance of two
branches = 1 - difflib ratio of her lines joined (0 same, 1 nothing shared). The drift floor of a cell is
distance(noop r1, noop r2): what two identical runs differ by. A target is changed in a cell when its distance to
both noops is above that floor. A target is changed overall when it is changed in more than half of the cells.
The base is read through `basewin_<snapshot>`: a folder beside the branches holding the base transcript cut to the
branch window (so the judge compares equal spans); written here, never touches the base run itself.

Judge (--judge only; the orchestrator's call, `claude -p` through bzombie.judge): per cell, for each target a match
target v noop r1 and target v basewin, plus noop r1 v noop r2 (the floor) and noop r1 v basewin. Match ids are fixed
(rm_<base>_<snapshot>_<a>_vs_<b>) so a rerun resumes. Without --judge, results already on disk are read. Each match
is 7 criteria x 2 passes = 14 claude calls (memory_continuity and emotional_arc are left out: the span is one sim day).
"""
from __future__ import annotations

import collections
import difflib
import json
import re
import subprocess
import sys

from ..common import HIDE, VAR, hidden_env, parse_ts, read_json, read_jsonl, run_dir, write_json
from . import branch as branch_mod
from . import removal_batch as rb
from . import removal_targets as rt
from .driver import REPO

CALLS_PER_MATCH = 14
CHARACTER = "momoka"


def basewin_id(snapshot: str) -> str:
    return f"basewin_{snapshot}"


def ensure_basewin(base: str, snapshot: str, n_msgs: int, window_min: int) -> str | None:
    """Folder runs/<base>/branches/basewin_<snapshot>: base transcript rows from the snapshot cursor to the window
    end, branch.json with replayed_from_virtual_ts, so `<base>~basewin_<snapshot>` is a judge spec."""
    w = rb.window(base, snapshot, n_msgs, window_min)
    if not w:
        return None
    cur, end = w
    d = run_dir(base) / "branches" / basewin_id(snapshot)
    if (d / "branch.json").exists():
        return basewin_id(snapshot)
    rows = [r for r in read_jsonl(run_dir(base) / "transcript.jsonl")
            if r.get("virtual_ts") and cur <= parse_ts(r["virtual_ts"]) <= end]
    d.mkdir(parents=True, exist_ok=True)
    (d / "transcript.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                                        encoding="utf-8")
    write_json(d / "branch.json", {"branch_id": basewin_id(snapshot), "from_snapshot": snapshot, "target": "base",
                                   "replayed_from_virtual_ts": cur.isoformat(), "window_end": end.isoformat(),
                                   "finished": True})
    return basewin_id(snapshot)


def her_lines(base: str, bid: str, cursor) -> list[dict]:
    rows = read_jsonl(run_dir(base) / "branches" / bid / "transcript.jsonl")
    return [r for r in rows if r.get("who") == "her" and r.get("virtual_ts") and parse_ts(r["virtual_ts"]) >= cursor]


def role_of_calls(base: str, bid: str) -> dict:
    """call_id -> role, from the traces beside the branch (calls.jsonl rows carry no role)."""
    m = {}
    for p in (run_dir(base) / "branches" / bid / "traces").glob("*.json"):
        for c in (read_json(p) or {}).get("calls", []):
            m[c["call_id"]] = c.get("role") or "(blank)"
    return m


def mech(base: str, bid: str, cursor) -> dict:
    lines = her_lines(base, bid, cursor)
    out = {"her_lines": len(lines), "her_chars": sum(len(str(r.get("text") or "")) for r in lines),
           "unprompted": sum(1 for r in lines if r.get("kind") not in (None, "reply")),
           "text": "\n".join(str(r.get("text") or "") for r in lines),
           "chat_calls": 0, "prompt_tokens": 0, "cost_micro": 0, "roles": {}}
    calls = run_dir(base) / "branches" / bid / "calls.jsonl"
    if calls.exists():
        roles = role_of_calls(base, bid)
        cnt = collections.Counter()
        for r in read_jsonl(calls):
            if r.get("endpoint") != "chat/completions":
                continue
            out["chat_calls"] += 1
            out["prompt_tokens"] += int((r.get("usage") or {}).get("prompt_tokens") or 0)
            out["cost_micro"] += int(r.get("cost_micro") or 0)
            cnt[roles.get(r["call_id"], "(not in a trace)")] += 1
        out["roles"] = dict(cnt)
    return out


def distance(a: str, b: str) -> float:
    if not a and not b:
        return 0.0
    return round(1 - difflib.SequenceMatcher(None, a, b, autojunk=False).ratio(), 4)


def cell_report(base: str, snapshot: str, targets: list[dict], n_msgs: int, window_min: int) -> dict | None:
    w = rb.window(base, snapshot, n_msgs, window_min)
    if not w:
        return None
    cur = w[0]
    bw = ensure_basewin(base, snapshot, n_msgs, window_min)
    ids = {"noop_r1": branch_mod.branch_id(snapshot, rt.NOOP, True, "r1"),
           "noop_r2": branch_mod.branch_id(snapshot, rt.NOOP, True, "r2")}
    m = {"base": mech(base, bw, cur)}
    for k, bid in ids.items():
        if branch_mod.is_finished(base, bid):
            m[k] = mech(base, bid, cur)
    out = {"base": base, "snapshot": snapshot, "mech": {}, "targets": {}}
    floor = distance(m["noop_r1"]["text"], m["noop_r2"]["text"]) if "noop_r1" in m and "noop_r2" in m else None
    out["floor"] = floor
    out["noop_v_base"] = [distance(m[k]["text"], m["base"]["text"]) for k in ("noop_r1", "noop_r2") if k in m]
    for t in targets:
        bid = branch_mod.branch_id(snapshot, t["target"], False)
        if not branch_mod.is_finished(base, bid):
            out["targets"][t["name"]] = {"finished": False}
            continue
        x = mech(base, bid, cur)
        d_noop = [distance(x["text"], m[k]["text"]) for k in ("noop_r1", "noop_r2") if k in m]
        row = {"finished": True, "bid": bid, "her_lines": x["her_lines"], "her_chars": x["her_chars"],
               "unprompted": x["unprompted"], "chat_calls": x["chat_calls"], "prompt_tokens": x["prompt_tokens"],
               "d_base": distance(x["text"], m["base"]["text"]), "d_noop": d_noop,
               "roles_removed": {r: [x["roles"].get(r, 0), [m[k]["roles"].get(r, 0) for k in ("noop_r1", "noop_r2")
                                                              if k in m]] for r in t["roles"]}}
        row["changed"] = (None if floor is None or not d_noop else all(d > floor for d in d_noop))
        out["targets"][t["name"]] = row
    out["mech"] = {k: {a: v for a, v in x.items() if a not in ("text",)} for k, x in m.items()}
    return out


def match_id(base: str, snapshot: str, a: str, b: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.~-]", "_", f"rm_{base}_{snapshot}_{a}_vs_{b}")


def judge_pairs(base: str, snapshot: str, targets: list[dict], vs: str) -> list[dict]:
    bw = basewin_id(snapshot)
    r1, r2 = (branch_mod.branch_id(snapshot, rt.NOOP, True, f"r{i}") for i in (1, 2))
    pairs = [{"kind": "floor", "a": r1, "b": r2}]
    if vs in ("both", "base"):
        pairs.append({"kind": "noop_v_base", "a": r1, "b": bw})
    for t in targets:
        bid = branch_mod.branch_id(snapshot, t["target"], False)
        if vs in ("both", "noop"):
            pairs.append({"kind": f"{t['name']}_v_noop", "a": bid, "b": r1})
        if vs in ("both", "base"):
            pairs.append({"kind": f"{t['name']}_v_base", "a": bid, "b": bw})
    for p in pairs:
        p["base"], p["snapshot"] = base, snapshot
        p["match_id"] = match_id(base, snapshot, p["a"], p["b"])
    return pairs


def judge_result(p: dict) -> dict | None:
    """The match's outcome in terms of p['a'] (first) and p['b'] (second); None when no results.json yet."""
    r = read_json(VAR / "judge" / p["match_id"] / "results.json")
    if not r:
        return None
    lm = r["label_map"]  # match label -> spec
    first = "A" if lm["A"].endswith("~" + p["a"]) else "B"
    sec = "B" if first == "A" else "A"
    wins = r["summary"]["wins"]
    w = r["summary"]["winner"]
    return {"first": wins[first], "second": wins[sec], "tie": wins["tie"], "split": wins["split"],
            "winner": None if w is None else "first" if w == first else "second" if w == sec else "tie",
            "uncalibrated": [u["id"] for u in r["summary"].get("uncalibrated", [])]}


def run_judge(pairs: list[dict], workers: int, cap: float) -> int:
    fails = 0
    for p in pairs:
        if (VAR / "judge" / p["match_id"] / "results.json").exists():
            continue
        cmd = [sys.executable, "-m", "bzombie.judge", "match", "--a", f"{p['base']}~{p['a']}",
               "--b", f"{p['base']}~{p['b']}", "--character", CHARACTER, "--match-id", p["match_id"],
               "--workers", str(workers), "--claude-cap-usd", str(cap)]
        (VAR / "removal_batch").mkdir(parents=True, exist_ok=True)
        with open(VAR / "removal_batch" / f"judge_{p['match_id']}.log", "ab") as out:
            rc = subprocess.run(cmd, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                creationflags=HIDE, cwd=str(REPO), env=hidden_env()).returncode
        print(f"judge {p['match_id']}: rc {rc}", flush=True)
        fails += rc != 0
    return fails


def render_md(rep: dict) -> str:
    L = ["# Removal tests summary (tk-lmv)", "",
         f"Plan: {rep['n_msgs']} messages, {rep['window_min']} min. Drift floor = distance(noop r1, noop r2) "
         "(0 same, 1 nothing shared). Changed = distance to both noops above the floor. Overall changed = more than "
         "half of the cells.", ""]
    for name, t in rep["targets"].items():
        L += [f"## {name} ({t['target']}): " + ("changed beyond noop" if t["changed"] else
                                               "no change beyond noop" if t["changed"] is False else "no data"),
              f"Changed in {t['cells_changed']} of {t['cells_with_data']} cells. {t['why']}", "",
              "| cell | floor | d to noop r1 | d to noop r2 | d to base | noop d to base | her lines | chat calls | "
              "removed roles (branch v noops) | changed | judge v noop | judge v base |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for c in t["cells"]:
            if not c.get("finished"):
                L.append(f"| {c['cell']} | | | | | | | | | not run | | |")
                continue
            dn = c["d_noop"] + [None] * (2 - len(c["d_noop"]))
            L.append(f"| {c['cell']} | {c['floor']} | {dn[0]} | {dn[1]} | {c['d_base']} | {c['noop_v_base']} | "
                     f"{c['her_lines']} | {c['chat_calls']} | {c['roles_removed'] or '-'} | {c['changed']} | "
                     f"{c.get('judge_v_noop', '-')} | {c.get('judge_v_base', '-')} |")
        L.append("")
    fl = [c for c in rep["floors"]]
    L += ["## Drift floor per cell", "", "| cell | floor | noop v base |", "|---|---|---|"]
    L += [f"| {c['cell']} | {c['floor']} | {c['noop_v_base']} |" for c in fl]
    if rep.get("judge_floor"):
        L += ["", "Judge floor (noop r1 v noop r2), first/second wins and ties: " + json.dumps(rep["judge_floor"])]
    return "\n".join(L) + "\n"


def fmt_judge(r) -> str:
    if r is None:
        return "-"
    return f"{r['winner']} ({r['first']}-{r['second']}-{r['tie']})"


def build(bases, snaps, targets, n_msgs, window_min, vs) -> dict:
    cells = []
    for s in snaps:
        for b in bases:
            c = cell_report(b, s, targets, n_msgs, window_min)
            if c:
                cells.append(c)
    rep = {"n_msgs": n_msgs, "window_min": window_min, "targets": {}, "floors": [], "judge_floor": []}
    for c in cells:
        cell = f"{c['base']} {c['snapshot']}"
        rep["floors"].append({"cell": cell, "floor": c["floor"], "noop_v_base": c["noop_v_base"]})
        for p in judge_pairs(c["base"], c["snapshot"], targets, vs):
            if p["kind"] == "floor" and (r := judge_result(p)):
                rep["judge_floor"].append({"cell": cell, **r})
    for t in targets:
        rows = []
        for c in cells:
            tr = dict(c["targets"].get(t["name"], {"finished": False}))
            tr.update(cell=f"{c['base']} {c['snapshot']}", floor=c["floor"], noop_v_base=c["noop_v_base"])
            if tr.get("finished"):
                pairs = {p["kind"]: p for p in judge_pairs(c["base"], c["snapshot"], [t], vs)}
                tr["judge_v_noop"] = fmt_judge(judge_result(pairs[f"{t['name']}_v_noop"])) \
                    if f"{t['name']}_v_noop" in pairs else "-"
                tr["judge_v_base"] = fmt_judge(judge_result(pairs[f"{t['name']}_v_base"])) \
                    if f"{t['name']}_v_base" in pairs else "-"
            rows.append(tr)
        have = [r for r in rows if r.get("changed") is not None]
        k = sum(1 for r in have if r["changed"])
        rep["targets"][t["name"]] = {"target": t["target"], "why": t["why"], "cells": rows,
                                     "cells_with_data": len(have), "cells_changed": k,
                                     "changed": None if not have else k * 2 > len(have)}
    return rep


def main(argv):
    def opt(name, default=None):
        return argv[argv.index(name) + 1] if name in argv else default
    pos = [a for i, a in enumerate(argv) if not a.startswith("--") and (i == 0 or argv[i - 1] not in (
        "--vs", "--workers", "--claude-cap-usd", "--bases", "--snapshots", "--n-msgs", "--window-min"))]
    if not pos and "--dry" not in argv:
        sys.exit(__doc__)
    out_base = pos[0] if pos else ""
    n_msgs, wmin = int(opt("--n-msgs", rb.N_MSGS)), int(opt("--window-min", rb.WINDOW_MIN))
    bases = opt("--bases", ",".join(rb.BASES)).split(",")
    snaps = opt("--snapshots", ",".join(rb.SNAPSHOTS)).split(",")
    vs = opt("--vs", "both")
    if vs not in ("both", "noop", "base"):
        sys.exit("--vs both|noop|base")
    if "--dry" in argv:
        n = sum(len(judge_pairs(b, s, rt.TARGETS, vs)) for b in bases for s in snaps)
        print(f"judge plan: {n} matches x {CALLS_PER_MATCH} claude calls = {n * CALLS_PER_MATCH} calls "
              f"(--vs {vs}); the mechanical diff makes no call")
        return
    if "--judge" in argv:
        for s in snaps:
            for b in bases:
                if ensure_basewin(b, s, n_msgs, wmin):
                    run_judge(judge_pairs(b, s, rt.TARGETS, vs), int(opt("--workers", 4)),
                              float(opt("--claude-cap-usd", 10.0)))
    rep = build(bases, snaps, rt.TARGETS, n_msgs, wmin, vs)
    write_json(out_base + ".json" if not out_base.endswith(".json") else out_base, rep)
    md = (out_base[:-5] if out_base.endswith(".json") else out_base) + ".md"
    with open(md, "w", encoding="utf-8") as f:
        f.write(render_md(rep))
    for name, t in rep["targets"].items():
        print(f"{name}: changed {t['cells_changed']}/{t['cells_with_data']} -> "
              f"{'CHANGED' if t['changed'] else 'no change beyond noop' if t['changed'] is False else 'no data'}")
    print("wrote", md)
