# -*- coding: utf-8 -*-
"""Describe the corpus assets the stage does not draw yet, from the game's own
record rather than from a guess.

The koikano stage state (`koikano_work/stage_state.jsonl`) carries every line of
the script with the background, the CG and the sprites it was shown with. This
reads that record and, for each background and each CG, writes down the scenes
it appears in and a sample of the dialogue around it. The output is the raw
material for the `CG_NOTES` and place tables the console will read; nothing here
goes live, and nothing in the corpus is written.

    python tools/corpus_describe.py                       # write the report
    python tools/corpus_describe.py --kind cg --top 30    # print the most used CGs
    python tools/corpus_describe.py --out scratch.json --corpus <path>

Standard library only. The corpus is read-only.
"""

import argparse
import collections
import datetime
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

DEFAULT_CORPUS = (r"F:\REPS2\clipboard capture (kirikiri)\extracted_games\koikano"
                  r"\koikano_work\stage_state.jsonl")
DEFAULT_OUT = os.path.join(ROOT, "data", "vn", "corpus_describe.json")

# How many dialogue lines are kept as the sample for one asset. Enough to read
# what it is; not the whole scene.
SAMPLE = 8


def _id(value):
    """The id out of a stage field, which the record writes as a dict or a
    string depending on the field."""
    if isinstance(value, dict):
        return str(value.get("id") or value.get("file") or "").strip()
    return str(value or "").strip()


def collect(corpus_path):
    """{kind: {asset_id: {"scenes": [...], "count": n, "sample": [...]}}} for
    `cg` and `bg`, in the order the script uses them."""
    out = {"cg": {}, "bg": {}}
    lines = 0
    with io.open(corpus_path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            lines += 1
            stage = row.get("stage") or {}
            scene = str(row.get("scene") or "")
            text = str(row.get("text") or "").strip()
            for kind, value in (("cg", stage.get("cg")), ("bg", (stage.get("bg") or {}))):
                aid = _id(value)
                if not aid:
                    continue
                row_out = out[kind].setdefault(aid, {"scenes": [], "count": 0, "sample": []})
                row_out["count"] += 1
                if scene and scene not in row_out["scenes"]:
                    row_out["scenes"].append(scene)
                if text and len(row_out["sample"]) < SAMPLE:
                    row_out["sample"].append(text[:120])
    return out, lines


def main():
    ap = argparse.ArgumentParser(description="Describe corpus assets from the stage state.")
    ap.add_argument("--corpus", default=DEFAULT_CORPUS)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--kind", choices=("cg", "bg", "all"), default="all")
    ap.add_argument("--top", type=int, default=0, help="print the N most used, do not write")
    args = ap.parse_args()

    if not os.path.isfile(args.corpus):
        print(f"[corpus] no stage state at {args.corpus}")
        return 1
    data, lines = collect(args.corpus)
    print(f"[corpus] {lines} line(s) read; {len(data['cg'])} CG id(s), "
          f"{len(data['bg'])} background id(s)")

    if args.top:
        kind = "bg" if args.kind == "bg" else "cg"
        rows = sorted(data[kind].items(), key=lambda kv: -kv[1]["count"])[:args.top]
        for aid, row in rows:
            print(f"  {aid:12s} {row['count']:5d}  scenes {','.join(row['scenes'][:3])}  "
                  f"| {(row['sample'][0] if row['sample'] else '')[:70]}")
        return 0

    doc = {
        "generated": datetime.date.today().isoformat(),
        "corpus": args.corpus,
        "counts": {"lines": lines,
                   "cg": len(data["cg"]), "bg": len(data["bg"])},
        "cg": {k: v for k, v in sorted(data["cg"].items())},
        "bg": {k: v for k, v in sorted(data["bg"].items())},
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with io.open(args.out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print(f"[corpus] wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
