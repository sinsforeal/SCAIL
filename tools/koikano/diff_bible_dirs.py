"""Compare two bible output dirs file by file, as parsed JSON (key order ignored).

usage: python diff_bible_dirs.py <orig_dir> <new_dir>
Prints one line per file: same / DIFFERENT (with the first differing paths).
"""
import json
import os
import sys


def walk(a, b, path, out, limit=12):
    if len(out) >= limit:
        return
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a:
                out.append("%s/%s only in new" % (path, k))
            elif k not in b:
                out.append("%s/%s only in orig" % (path, k))
            else:
                walk(a[k], b[k], path + "/" + str(k), out, limit)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append("%s list len %d vs %d" % (path, len(a), len(b)))
        for i, (x, y) in enumerate(zip(a, b)):
            walk(x, y, "%s[%d]" % (path, i), out, limit)
    elif a != b:
        out.append("%s: %r vs %r" % (path, str(a)[:80], str(b)[:80]))


def main():
    o, n = sys.argv[1], sys.argv[2]
    for root, _, files in os.walk(o):
        for f in sorted(files):
            if not f.endswith(".json"):
                continue
            po = os.path.join(root, f)
            rel = os.path.relpath(po, o)
            pn = os.path.join(n, rel)
            if not os.path.exists(pn):
                print("MISSING in new:", rel)
                continue
            a = json.load(open(po, encoding="utf-8"))
            b = json.load(open(pn, encoding="utf-8"))
            out = []
            walk(a, b, "", out)
            print(rel, "same" if not out else "DIFFERENT")
            for line in out:
                print("   ", line)
    for root, _, files in os.walk(n):
        for f in files:
            if f.endswith(".json") and not os.path.exists(os.path.join(o, os.path.relpath(os.path.join(root, f), n))):
                print("only in new:", os.path.relpath(os.path.join(root, f), n))


main()
