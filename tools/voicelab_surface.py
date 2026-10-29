"""Surface distance from her tape, per row: the second axis of the voice bench.

The first axis (how Yukarin) is a reading against `docs/yukarin-voice-standard.md`
and inherits whatever is wrong with the standard. This one does not: it compares
a row's marker rates with her attributed speech directly, so it is the part of
a ranking that survives if the standard turns out to be wrong about her.

Two numbers per row, over the CHAT answers only (the broadcast set is the
fairness control and is not the target):

  distance   mean over every marker of |log((row + 1) / (tape + 1))|, rates per
             100k characters. Lower is closer. The +1 keeps a marker the row
             never used from making the distance infinite.
  fillers    えっと / あのー / えーと / うーん / んーと per 100k, against the tape's
             own rate. These are her most dispersed habits (えっと in 91 of 99
             episodes). Under a guide that bans typed hesitation a high number
             is a model overriding the guide; under one that instructs her
             speech, the tape's rate is the target.

Neither is a score. The reading decides; these are what the reading is checked
against.

    python tools/voicelab_surface.py --run data/voicelab/<stamp> [--run ...] [--agents DIR]

This used to be a one-off script pasted into a shell, which is how the numbers
in the first ranking were produced and why nobody could re-run them. Same
arithmetic, same marker list (`voicelab_report.MARKERS`), same corpus reader.
"""

import argparse
import io
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import voicelab_report as R
from quote_audit import her_cues

FILLERS = ("えーと", "えっと", "うーん", "んーと", "あのー")


def measure(rows, markers=None):
    """[(model, distance, fillers_per_100k, n_answers)], plus the tape's filler rate."""
    markers = markers or R.MARKERS
    tape = "".join(t for _, _, t in her_cues())
    corpus = {m: tape.count(m) / len(tape) * 1e5 for m in markers}
    tape_fill = sum(tape.count(k) for k in FILLERS) / len(tape) * 1e5
    out = []
    for m in dict.fromkeys(r["model"] for r in rows):
        g = [r for r in rows if r["model"] == m and r.get("set", "chat") == "chat"
             and (r.get("text") or "").strip()]
        if not g:
            continue
        t = "".join(r["text"] for r in g)
        rate = {k: t.count(k) / len(t) * 1e5 for k in markers}
        d = sum(abs(math.log((rate[k] + 1) / (corpus[k] + 1))) for k in markers) / len(markers)
        fill = sum(t.count(k) for k in FILLERS) / len(t) * 1e5
        out.append((m, d, fill, len(g)))
    return sorted(out, key=lambda x: x[1]), tape_fill


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="append", required=True, help="run directory; repeatable")
    ap.add_argument("--agents", default="", help="directory holding subagent_*.jsonl (default: the first run dir)")
    ap.add_argument("--out", default="", help="write the table here as markdown as well")
    args = ap.parse_args()
    rows = R.load(args.run, args.agents or None)
    table, tape_fill = measure(rows)
    lines = ["| model | distance | fillers /100k | chat answers |", "|---|---|---|---|"]
    for m, d, f, n in table:
        lines.append(f"| {m} | {d:.2f} | {f:.0f} | {n} |")
    lines.append(f"| **her tape** | 0 | **{tape_fill:.0f}** | -- |")
    print(f"surface distance over {len(R.MARKERS)} markers, chat set, runs {args.run}\n")
    print("\n".join(lines))
    if args.out:
        io.open(args.out, "w", encoding="utf-8").write(
            "# Surface distance from her tape, chat answers\n\n"
            "distance = mean |log((row+1)/(tape+1))| over the marker list, rates per 100k; "
            "fillers = えっと/あのー/えーと/うーん/んーと per 100k.\n\n" + "\n".join(lines) + "\n")
        print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()
