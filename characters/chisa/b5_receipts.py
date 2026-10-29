# B5 job 2 for 知紗 (2026-10-24): puts the record lines the prompts cite into bible.json as `b5_receipts`,
# so tools check_prompt_numbers.py can verify every scene:line id in prompts/bible.md and style.md, and
# corrects one rule text that said she says ペニス once (the record has 8 lines).
# usage: python b5_receipts.py [character_dir]     (default: the folder this file is in); rerun is safe.
# Source: koikano_work/character_lines/知紗.jsonl (her own lines only; every cited id must be one of them).
import json
import os
import re
import sys

CORPUS = r"F:\REPS2\clipboard capture (kirikiri)\extracted_games\koikano\koikano_work\character_lines\知紗.jsonl"
OLD_RULE = "she says ペニス once (08_02:2284)."
NEW_RULE = ("she says ペニス on 8 lines (7 in H, 1 outside in d10_01:2212, where she repeats a student's question "
            "in a health class).")
H_SCENE = "08_02"
H_WORDS = ["ペニス", "精液", "射精", "セックス", "中出し", "なかだし", "膣内", "おちんちん", "おまんこ"]


def main(d):
    rows = {}
    for line in open(CORPUS, encoding="utf-8"):
        r = json.loads(line)
        rows["%s:%04d" % (r["scene"], r["source_line"])] = r
    bible_path = os.path.join(d, "bible.json")
    bible = json.load(open(bible_path, encoding="utf-8"))
    ids = set()
    for name in ("bible.md", "style.md"):
        text = open(os.path.join(d, "prompts", name), encoding="utf-8").read()
        ids.update(re.findall(r"[0-9a-z]+_\d\d:\d{4}", text))
    lines = {}
    bad = []
    for i in sorted(ids):
        if i in rows:
            lines[i] = rows[i]["text"]
        else:
            bad.append(i)
    if bad:
        print("ids that are not her lines (other speaker or no such line):", bad)
    counts = {}
    for w in H_WORDS:
        hit = [k for k, r in rows.items() if w in r["text"]]
        counts[w] = {"lines": len(hit), "in_H": sum(1 for k in hit if k.startswith(H_SCENE + ":")),
                     "outside_H": sum(1 for k in hit if not k.startswith(H_SCENE + ":")),
                     "outside_ids": [k for k in hit if not k.startswith(H_SCENE + ":")]}
    bible["b5_receipts"] = {
        "_note": ("record lines cited by prompts/bible.md and prompts/style.md, copied from her own line file so the "
                  "number check can find every id; turn_length_bins are the bible's own bin edges; h_words counts "
                  "her spoken lines containing each word"),
        "turn_length_bins": [1, 5, 6, 10, 11, 20, 21, 40, 41, 80, 81],
        "h_words": counts,
        "lines": lines,
    }

    def swap(o):
        if isinstance(o, str):
            return o.replace(OLD_RULE, NEW_RULE)
        if isinstance(o, list):
            return [swap(x) for x in o]
        if isinstance(o, dict):
            return {k: swap(v) for k, v in o.items()}
        return o

    bible = swap(bible)
    with open(bible_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(bible, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    print("b5_receipts: %d lines, h_words %s" % (len(lines), {k: v["lines"] for k, v in counts.items()}))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__)))
