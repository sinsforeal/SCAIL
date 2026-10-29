# Mechanical check: every number in prompts/bible.md and prompts/style.md must be one of the character's receipts.
# usage: python check_prompt_numbers.py [character_dir]     (default: the folder this file is in)
# Allowed numbers: every numeric leaf (int or float) of bible.json outside `context`, `spot_check` and `gate`
# (counts, rates, lengths), compared by value. Record ids (e.g. 01_01:0616) must appear verbatim in bible.json.
# Numbers written inside rule/definition/note strings are NOT allowed sources (they are prose, not receipts).
# Kanji counters (二回, 一つ ...) are listed as warnings; ALLOW_KANJI lists the ones that are a move's name.
# Exit code 1 if any number or id is a miss.
import json
import os
import re
import sys
import unicodedata

ALLOW_KANJI = {"二回"}   # 大事な語を二回続ける = the doubling move's name, not a count
SKIP_SECTIONS = {"context", "spot_check", "gate"}


def numeric_leaves(o, out):
    if isinstance(o, bool):
        return
    if isinstance(o, (int, float)):
        out.add(float(o))
    elif isinstance(o, dict):
        for v in o.values():
            numeric_leaves(v, out)
    elif isinstance(o, list):
        for v in o:
            numeric_leaves(v, out)


def main(d):
    raw = open(os.path.join(d, "bible.json"), encoding="utf-8").read()
    bible = json.loads(raw)
    allowed = set()
    for k, v in bible.items():
        if k not in SKIP_SECTIONS:
            numeric_leaves(v, allowed)
    misses = 0
    for name in ("bible.md", "style.md"):
        text = unicodedata.normalize("NFKC", open(os.path.join(d, "prompts", name), encoding="utf-8").read())
        ids = re.findall(r"[0-9a-z]+_\d\d:\d{4}", text)
        rest = re.sub(r"[0-9a-z]+_\d\d:\d{4}", " ", text)
        nums = re.findall(r"\d+(?:\.\d+)?", rest)
        bad_ids = sorted({i for i in ids if i not in raw})
        bad_nums = sorted({n for n in nums if float(n) not in allowed})
        kanji = sorted({m for m in re.findall(r"(?:一|二|三|四|五|六|七|八|九|十)+(?:つ|回|行|人|場面|件|個)", rest) if m not in ALLOW_KANJI})
        print("%s: %d ids (%d unique), %d numbers (%d unique)" % (name, len(ids), len(set(ids)), len(nums), len(set(nums))))
        print("  id misses: %s" % (bad_ids or "none"))
        print("  number misses: %s" % (bad_nums or "none"))
        print("  kanji counters (warning): %s" % (kanji or "none"))
        misses += len(bad_ids) + len(bad_nums)
    print("RESULT: %s" % ("OK, 0 misses" if not misses else "%d misses" % misses))
    return 1 if misses else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))))
