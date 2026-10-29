# B3 pass for mayu (2026-10-23): after tools/koikano/koikano_bible.py has rebuilt bible.json with the own
# B3 reading (tools/koikano/b3/mayu.py), reapply the B5 speech-guide rule texts and set every tier by one rule.
# usage: python b3_apply.py <bible.json>     (in place; fails loudly on a second run)
#
# Tier rule, same for every entry (mechanism or speech-guide rule), from the count n the entry rests on:
#   n >= 40 -> firm; 10 <= n < 40 -> thin; n < 10 -> weak.
#   Two clauses on top: (a) evidence "inferred" caps the tier at thin; (b) a mechanism whose share of her
#   spoken lines is at or under the control share is weak whatever n is; a firm mechanism needs share >= 2x control.
#   n for a rule is the line count of its main receipt (see N_OF below); an absence rule (zero hits) rests on
#   the spoken lines checked.
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import b5_rewrite_texts as b5  # RULES (rule texts by index, guarded), reused unchanged

FIRM, THIN = 40, 10


def tier_of(n, inferred=False, share=None, control=None):
    if share is not None and control is not None:
        if share <= control:
            return "weak"
        if n >= FIRM and not (control == 0 or share >= 2 * control):
            return "thin"
    t = "firm" if n >= FIRM else "thin" if n >= THIN else "weak"
    if inferred and t == "firm":
        t = "thin"
    return t


def n_of(i, r, spoken):
    c = r["receipt"]
    f = {
        0: lambda: c["spoken_lines_with_わたし"],
        1: lambda: c["pooled"]["lines"],
        2: lambda: c["reply"] + c["initiation"],
        3: lambda: c["lines_ending_っ"],
        4: lambda: c["lines_ending_ー"],
        5: lambda: c["token_んっ"],
        6: lambda: spoken,  # absence rule: the lines checked
        7: lambda: c["lines_matched"],
        8: lambda: c["lines_with_です_ます"],
        9: lambda: c["spoken_lines"],
        10: lambda: c["！_by_register"]["H"]["count"] + c["！_by_register"]["non_H"]["count"],
        11: lambda: c["smile_lines"],
        12: lambda: c["lines"],
        13: lambda: c["by_register"]["H"]["lines"] + c["by_register"]["non_H"]["lines"],
        14: lambda: c["by_register"]["H"]["lines"] + c["by_register"]["non_H"]["lines"],
        15: lambda: c["inner_lines"],
        16: lambda: c["H"]["lines"] + c["non_H"]["lines"],
        17: lambda: c["lines_with_emotion"],
        18: lambda: int(c["her_units_agreed"].split()[0].split("/")[1]),
        19: lambda: c["her_@おじぎ"],
        20: lambda: c["kiss_lines"],
        21: lambda: c["lines"],
        22: lambda: c["lines_with_H_tokens"],
        23: lambda: c["laugh_lines"],
        24: lambda: c["third_person_lines"],
    }
    return f[i]()


# Own-rule markers (read by load_rule_markers in tools/koikano/koikano_bible_gate.py): a regex over the kept
# spoken text, one per speech_guide rule that a text pattern can detect. Built from the rule wording, not tuned
# on the holdout. Rules with no entry here (2 reply/open, 11-14 face and gesture mixes, 15 inner voice,
# 16-20 and 23 annotation labels) rest on tags or context, not on the line text, so they carry no marker.
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', 'tools', 'koikano'))
import markers_io  # noqa: E402
MARKERS = markers_io.load('mayu')  # tools/koikano/markers/mayu.json is the source


def add_markers(b):
    rules = b["speech_guide"]["rules"]
    for i, pat in MARKERS.items():
        rules[i]["marker"] = {"pattern": pat}
    return len(MARKERS), len(rules)


def main(path):
    if path == "--markers-only":
        path = sys.argv[2]
        b = json.load(open(path, encoding="utf-8"))
        print("markers %d of %d rules" % add_markers(b))
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(b, fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.write("\n")
        return
    b = json.load(open(path, encoding="utf-8"))
    sg = b["speech_guide"]
    rules = sg["rules"]
    assert len(rules) == 25 and len(b5.RULES) == 25
    if "tier_basis" in rules[0]:
        sys.exit("already applied")
    spoken = b["mechanisms"]["spoken_lines"]
    for i, (guard, new) in b5.RULES.items():
        old = rules[i]["rule"]
        if not old.startswith(guard):
            sys.exit("rule %d: old text does not start with %r: %r" % (i, guard, old[:50]))
        rules[i]["rule"] = new
        rules[i].pop("text_basis", None)
        n = n_of(i, rules[i], spoken)
        t = tier_of(n, inferred=rules[i]["evidence"] == "inferred")
        rules[i]["tier_basis"] = "n=%d" % n
        if t != rules[i]["tier"]:
            rules[i]["tier_was"] = rules[i]["tier"]
            rules[i]["tier"] = t
    from collections import Counter
    sg["tier_split"] = dict(sorted(Counter(r["tier"] for r in rules).items()))
    sg["note"] = sg["note"].replace("a tier (firm / thin)", "a tier (firm / thin / weak, set by one count rule: firm n>=40, thin 10-39, weak under 10, inferred evidence capped at thin; tier_basis states n, tier_was the builder's old value)")

    m = b["mechanisms"]
    for x in m["mechanisms"]:
        t = tier_of(x["lines"], share=x["share_of_spoken"], control=x["control_rate"])
        x["tier_basis"] = "n=%d, share %s vs control %s" % (x["lines"], x["share_of_spoken"], x["control_rate"])
        if t != x["tier"]:
            sys.exit("mechanism %s: file tier %s, rule says %s" % (x["key"], x["tier"], t))
    tiers = [x["tier"] for x in m["mechanisms"]]
    m["firm_count"], m["thin_count"], m["weak_count"] = (tiers.count(k) for k in ("firm", "thin", "weak"))
    m["tier_split"] = {k: tiers.count(k) for k in ("firm", "thin", "weak")}
    m["class_note"] = ("Every mechanism is classed `hers` by this reading: each was found by contrasting her spoken lines with the other "
                       "named speakers' in her scenes (tools/koikano/b3/mayu.py), and the distinctive flag is that contrast on the whole build, not the "
                       "held-out gate. The class was not checked against the corpus ownership markers. The one move at or under the control "
                       "share (stammers_first_sound) is kept as `weak`: the script's other speakers stammer as much, so it is house style.")
    m["cross_reference"] = b5.TOP["cross_reference"]
    b["provenance"]["b3_own_reading"] = ("2026-10-23: mechanisms from tools/koikano/b3/mayu.py (her own 13, not 百花's 15); speech_guide rule texts "
                                      "reapplied from b5_rewrite_texts.py; every tier set by the count rule in characters/mayu/b3_apply.py.")
    print("markers %d of %d rules" % add_markers(b))
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(b, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    print("rules", sg["tier_split"], "mechanisms", m["tier_split"])
    for i, r in enumerate(rules):
        if "tier_was" in r:
            print(i, r["tier_was"], "->", r["tier"], r["tier_basis"])


if __name__ == "__main__":
    main(sys.argv[1])
