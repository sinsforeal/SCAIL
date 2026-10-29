"""Probed script for the grounding test (tk-6r3): a reference run's lines of his plus four probe questions, each once
per simulated day at a fixed time. The output is a JSONL the harness reads with --script-from <jsonl>, so arms A, B
and C get the same lines of his, probes included.

    python -m bzombie.harness.script_probes <ref_run_id|transcript.jsonl> <out.jsonl> [--clock-start 2026-10-26T07:00:00]
                                            [--days N]

Rows written: {"virtual_ts", "who": "him", "text", "sim_day", "probe": true|absent}. The reference's non-him rows are
dropped. A probe that lands within COLLIDE_MIN minutes of another line of his moves later by SHIFT_MIN until clear.
Sim days are counted from the clock start (day 1 starts at its date; the harness day length is 24 h).
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

from ..common import iso, parse_ts, read_json, read_jsonl, run_dir

# (HH:MM, text), the same every day. Evening, where his lines are densest in the reference runs.
PROBES = (
    ("12:55", "さっきどこ行ってたの？"),
    ("19:15", "部活どうだった？"),
    ("20:15", "千奈は元気？"),
    ("21:45", "今日なにしてた？"),
)
COLLIDE_MIN = 4
SHIFT_MIN = 7


def _source(src: str):
    p = Path(src)
    if p.is_file():
        return p, None
    rd = run_dir(src)
    if not (rd / "transcript.jsonl").is_file():
        raise SystemExit(f"{src}: not a file and no run with a transcript")
    return rd / "transcript.jsonl", src


def build(src: str, clock_start: str | None = None, days: int | None = None, probes=PROBES) -> list:
    path, ref = _source(src)
    cfg = (read_json(run_dir(ref) / "config.json") or {}) if ref else {}
    clock_start = clock_start or cfg.get("clock_start")
    if not clock_start:
        raise SystemExit("a plain jsonl needs --clock-start")
    days = days or int(cfg.get("sim_days") or 0)
    start = parse_ts(clock_start)
    rows = []
    for r in read_jsonl(path):
        if r.get("who", "him") != "him" or not r.get("text") or not r.get("virtual_ts"):
            continue
        rows.append({"virtual_ts": iso(parse_ts(r["virtual_ts"])), "who": "him", "text": r["text"]})
    if not rows:
        raise SystemExit(f"{src}: no lines of his")
    if not days:
        last = parse_ts(max(r["virtual_ts"] for r in rows))
        days = (last.date() - start.date()).days + 1
    taken = [parse_ts(r["virtual_ts"]) for r in rows]
    day0 = start.replace(hour=0, minute=0, second=0, microsecond=0)
    out = []
    for d in range(days):
        for hm, text in probes:
            h, m = (int(x) for x in hm.split(":"))
            t = day0 + dt.timedelta(days=d, hours=h, minutes=m)
            while any(abs((t - o).total_seconds()) < COLLIDE_MIN * 60 for o in taken):
                t += dt.timedelta(minutes=SHIFT_MIN)
            taken.append(t)
            out.append({"virtual_ts": iso(t), "who": "him", "text": text, "probe": True})
    allrows = rows + out
    allrows.sort(key=lambda r: r["virtual_ts"])
    for r in allrows:
        r["sim_day"] = (parse_ts(r["virtual_ts"]).date() - start.date()).days + 1
    return allrows


def write(rows: list, out: str) -> None:
    p = Path(out)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)

    def opt(name, default=None):
        return a[a.index(name) + 1] if name in a else default
    pos = [x for i, x in enumerate(a) if not x.startswith("--") and (i == 0 or not a[i - 1].startswith("--"))]
    if len(pos) != 2:
        sys.exit(__doc__)
    rows = build(pos[0], opt("--clock-start"), int(opt("--days")) if opt("--days") else None)
    write(rows, pos[1])
    n = sum(1 for r in rows if r.get("probe"))
    print(f"wrote {pos[1]}: {len(rows)} lines of his, {n} probes")


if __name__ == "__main__":
    main()
