# B5 (2026-10-23): bring bible_readable.md in line with the rewritten bible.json texts.
# usage: python b5_patch_readable.py <old_bible.json> <new_bible.json> <bible_readable.md>
import json
import re
import sys

old = json.load(open(sys.argv[1], encoding="utf-8"))
new = json.load(open(sys.argv[2], encoding="utf-8"))
path = sys.argv[3]
md = open(path, encoding="utf-8", newline="").read()
nl = "\r\n" if "\r\n" in md else "\n"
md = md.replace("\r\n", "\n")

n_rules = 0
for o, n in zip(old["speech_guide"]["rules"], new["speech_guide"]["rules"]):
    if o["rule"] != n["rule"]:
        assert md.count("| " + o["rule"] + " |") == 1, o["rule"][:40]
        md = md.replace("| " + o["rule"] + " |", "| " + n["rule"] + " |")
        n_rules += 1

n_mech = 0
for o, n in zip(old["mechanisms"]["mechanisms"], new["mechanisms"]["mechanisms"]):
    assert o["key"] == n["key"]
    m = re.search(r"^\| " + re.escape(o["name"]) + r" \| hers \| " + o["tier"] + r" \|", md, re.M)
    assert m, o["key"]
    md = md.replace(m.group(0), "| %s | hers | %s |" % (n["name"], n["tier"]))
    hdr = "- **%s** (hers, %s, %s, %d line(s)" % (o["name"], o["tier"], o["confidence"], o["lines"])
    i = md.index(hdr)
    j = md.index("\n", i)
    line = ("- **%s** (hers, %s, %s, %d line(s), share %s; non-H %d / H %d; control %s, distinctive %s): %s %s"
            % (n["name"], n["tier"], n["confidence"], n["lines"], n["share_of_spoken"], n["lines_non_H"], n["lines_H"],
               n["control_rate"], n["distinctive"], n["method"].rstrip(".") + ".", n["note"]))
    md = md[:i] + line + md[j:]
    n_mech += 1

ts = new["mechanisms"]["tier_split"]
md = re.sub(r"Mechanism split: class \{'hers': 14\}; tier \{[^}]*\} \([^)]*\) over 3546 spoken lines\.",
            "Mechanism split: class {'hers': 14}; tier {'firm': %d, 'thin': %d, 'weak': %d} (%d firm, %d thin, %d weak) over 3546 spoken lines."
            % (ts["firm"], ts["thin"], ts["weak"], ts["firm"], ts["thin"], ts["weak"]), md)
k = md.index("Every mechanism is classed `hers`")
e = md.index("\n", k)
md = md[:k] + new["mechanisms"]["class_note"] + md[e:]
if old["mechanisms"]["cross_reference"] in md:
    md = md.replace(old["mechanisms"]["cross_reference"], new["mechanisms"]["cross_reference"])
open(path, "w", encoding="utf-8", newline="").write(md.replace("\n", nl))
print("patched rules %d, mechanisms %d" % (n_rules, n_mech))
