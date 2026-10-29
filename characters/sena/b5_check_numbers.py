#!/usr/bin/env python3
"""Mechanical check for sena's runtime prompts.

1. Every number in prompts/bible.md and prompts/style.md (and sheet.json when --sheet) must appear
   in bible.json: as a numeric value, as a number inside any string value, or inside a key.
   Record ids (06_01:5137, b06_01) are not counted as numbers; they are checked in step 2.
2. Every record id quoted in the prompts must exist in 千奈's focused conversation file, and a
   「quote」 written right after an id must be a substring of a line at that id (ellipsis-split
   fragments are checked one by one).
Also checks that the rewritten speech_guide / mechanism prose cites only bible.json numbers.
Exit 1 on any miss. Run: python b5_check_numbers.py [--corpus DIR]
"""
import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORPUS = r"F:\REPS2\clipboard capture (kirikiri)\extracted_games\koikano\koikano_work\character_conversations_focused\千奈.jsonl"
ID = re.compile(r"\b[a-z]?\d\d_\d\d(?::\d{4})?\b")
NUM = re.compile(r"(?<![A-Za-z0-9_.:])\d+(?:\.\d+)?(?![A-Za-z0-9_])")


def nums_in(text):
    text = unicodedata.normalize("NFKC", text)
    text = ID.sub(" ", text)
    return NUM.findall(text)


def norm(s):
    return repr(float(s))


def collect(o, out):
    if isinstance(o, dict):
        for k, v in o.items():
            out.update(norm(n) for n in nums_in(str(k)))
            collect(v, out)
    elif isinstance(o, list):
        for v in o:
            collect(v, out)
    elif isinstance(o, bool) or o is None:
        pass
    elif isinstance(o, (int, float)):
        out.add(norm(str(o)))
    elif isinstance(o, str):
        out.update(norm(n) for n in nums_in(o))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=CORPUS)
    ap.add_argument("--sheet", action="store_true")
    a = ap.parse_args()
    bible = json.loads((HERE / "bible.json").read_text(encoding="utf8"))
    known = set()
    collect(bible, known)
    gc = HERE / "gate_checks.json"
    if gc.exists():
        collect(json.loads(gc.read_text(encoding="utf8")), known)
    misses = 0
    files = [HERE / "prompts" / "bible.md", HERE / "prompts" / "style.md"]
    if a.sheet:
        files.append(HERE / "sheet.json")
    texts = {f.name: f.read_text(encoding="utf8") for f in files}
    # the rewritten speech prose
    prose = [r["rule"] for r in bible["speech_guide"]["rules"]]
    prose += [m["name"] + " " + m["note"] for m in bible["mechanisms"]["mechanisms"]]
    prose += [bible["mechanisms"]["class_note"], bible["mechanisms"]["cross_reference"]]
    texts["bible.json:speech_guide+mechanisms prose"] = "\n".join(prose)
    for name, t in texts.items():
        found = nums_in(t)
        bad = sorted({n for n in found if norm(n) not in known}, key=float)
        print(f"{name}: {len(found)} numbers, {len(set(found))} distinct, misses: {bad if bad else 'none'}")
        misses += len(bad)
    # step 2: record ids
    rows = {}
    p = Path(a.corpus)
    if p.exists():
        for l in p.open(encoding="utf8"):
            r = json.loads(l)
            rows.setdefault(r["scene"] + ":" + format(r["source_line"], "04d"), []).append(r["text"])
        pat = re.compile(r"\b([a-z]?\d\d_\d\d:\d{4})(?:「([^」]*)」)?")
        n_ids = bad_ids = 0
        for name, t in texts.items():
            if name.startswith("bible.json"):
                continue
            for m in pat.finditer(t):
                n_ids += 1
                rid, quote = m.group(1), m.group(2)
                if rid not in rows:
                    print(f"  {name}: id not in record: {rid}")
                    bad_ids += 1
                elif quote:
                    frags = [f for f in re.split(r"…+|\.\.\.", quote) if f.strip()]
                    blob = "\n".join(rows[rid])
                    if not all(f in blob for f in frags):
                        print(f"  {name}: quote does not match {rid}: {quote[:40]}")
                        bad_ids += 1
        print(f"record ids checked: {n_ids}, bad: {bad_ids}")
        misses += bad_ids
    else:
        print("corpus file not found, id check skipped")
    print("RESULT:", "OK" if misses == 0 else f"{misses} miss(es)")
    return 1 if misses else 0


if __name__ == "__main__":
    sys.exit(main())
