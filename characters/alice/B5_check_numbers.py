# B5 mechanical check (tk-oas): every number in prompts/bible.md and prompts/style.md must appear in bible.json.
# Record ids (01_01:1193, c03_01:1610) are stripped first: they name a line, they are not figures.
# A number matches exactly (as a value or as text inside a string/key of bible.json), or as a rounding of a float receipt
# to the number of decimals written (reported as "rounded", for a human to read). Anything else is a MISS.
# Usage: C:/Python314/python.exe -X utf8 characters/alice/B5_check_numbers.py
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
bible = json.load(open(os.path.join(HERE, "bible.json"), encoding="utf-8"))

NUM = re.compile(r"\d+(?:\.\d+)?")
exact = {}   # canonical string -> first path
floats = []  # (value, path)


def canon(s):
    return s


def walk(o, path):
    if isinstance(o, dict):
        for k, v in o.items():
            for m in NUM.findall(str(k)):
                exact.setdefault(m, path + "/" + str(k))
            walk(v, path + "/" + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk(v, path + "[%d]" % i)
    elif isinstance(o, bool):
        pass
    elif isinstance(o, (int, float)):
        exact.setdefault(repr(o) if isinstance(o, float) else str(o), path)
        if isinstance(o, float):
            floats.append((o, path))
    elif isinstance(o, str):
        for m in NUM.findall(o):
            exact.setdefault(m, path)


walk(bible, "")

ID = re.compile(r"[A-Za-z]?\d{2}_\d{2}:\d{4}|[A-Za-z]?\d{2}_\d{2}")
rc = 0
for name in ("bible.md", "style.md"):
    text = open(os.path.join(HERE, "prompts", name), encoding="utf-8").read()
    stripped = ID.sub(" ", text)
    seen = {}
    for m in NUM.findall(stripped):
        seen[m] = seen.get(m, 0) + 1
    miss, rounded, ok = [], [], 0
    for n, c in sorted(seen.items(), key=lambda kv: float(kv[0])):
        if n in exact:
            ok += 1
            continue
        dec = len(n.split(".")[1]) if "." in n else 0
        hit = None
        if "." in n:
            for v, p in floats:
                if round(v, dec) == float(n):
                    hit = (v, p)
                    break
        if hit:
            rounded.append((n, hit[0], hit[1]))
        else:
            miss.append((n, c))
    small = sorted(n for n in seen if "." not in n and int(n) < 10 and n in exact)
    print("== %s: %d distinct numbers, %d exact, %d rounded, %d MISS" % (name, len(seen), ok, len(rounded), len(miss)))
    print("   (single-digit integers match by coincidence easily; read these by eye: %s)" % ", ".join(small))
    for w in ("年生", "歳", "才", "先輩", "後輩", "年長", "高校", "中学", "ダディ", "パパ", "ママ", "お父", "お母"):
        if w in text:
            print("   AGE/GRADE/PARENT WORD in text: %s" % w)
            rc += 1
    for n, v, p in rounded:
        print("   rounded %s ~ %r at %s" % (n, v, p))
    for n, c in miss:
        i = stripped.find(n)
        print("   MISS %s (x%d): ...%s..." % (n, c, stripped[max(0, i - 30): i + 30].replace("\n", " ")))
    rc += len(miss)
print("RESULT:", "OK, no misses" if rc == 0 else "%d misses" % rc)
sys.exit(1 if rc else 0)
