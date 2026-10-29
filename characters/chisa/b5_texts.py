# B5 job 1 for 知紗 (2026-10-24): one tier rule from counts for every entry, speech-guide texts
# rewritten from her receipts, B3 class_note / cross_reference rewritten, b5_counts section added.
# Same method as characters/maria/b5_texts.py. Her speech-guide texts came from 百花's prose; every
# one is replaced here by a count read off her 557 spoken lines (builder counts, receipts in the rule).
# usage: python b5_texts.py <dir with bible.json and bible_readable.md>   [--markers-only]
# Rules are matched by index and guarded by the start of the old text, so a rerun after the rewrite fails loudly.
import json
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools", "koikano"))
import koikano_bible as kb

TIER_RULE = ("one rule for every speech-guide entry, from the count n of her lines (or marks or hits where the receipt "
             "counts those) behind the entry's headline claim: firm = n of 50 or more; thin = n of 10 to 49; weak = n "
             "under 10, an absence (n is 0), or a caveat with no count")
MECH_TIER_RULE = ("per mechanism, from her lines n and her share of her spoken lines against the control share (the other "
                  "named speakers in her scenes): firm = n of 40 or more and her share at least 2x the control; thin = n of 10 "
                  "or more and her share above the control; weak = anything else (under 10 lines, or a share at or under the control)")


def tier_of(n):
    if n is None or n < 10:
        return "weak"
    return "firm" if n >= 50 else "thin"


def mech_tier(m):
    share, ctl = m["share_of_spoken"], m["control_rate"]
    if m["lines"] >= 40 and share >= 2 * ctl:
        return "firm"
    if m["lines"] >= 10 and share > ctl:
        return "thin"
    return "weak"


# index: (start of the old text, new text, n for the tier rule, register override or None)
RULES = {
    0: ("Refer to yourself as",
        "Call yourself 私: 68 of 557 spoken lines (H 26, non-H 42). You also call yourself 先生 (51 lines, 先生、相談に乗るわよ 01_01:4181) and twice by name (d05_01:0399, d05_01:0711).", 68, "all"),
    1: ("Keep non-H turns short",
        "Keep turns medium: median 28 kept characters pooled (non-H 27, H 29), no line over 59.", 557, None),
    2: ("Reply; do not open",
        "Reply; do not open. 430 of her turns answer someone and 0 open a scene (reply rate 1.0); 127 more continue her own turn.", 430, None),
    3: ("End many lines on a glottal",
        "A glottal っ ending is mostly an H habit: 87 lines end on っ, 65 of them in H (of 162) and 22 outside it (of 395).", 87, None),
    4: ("Stretch the last syllable",
        "Do not stretch the last syllable with ー: 0 of 395 non-H lines end on ー, and 1 of the 162 H lines does (08_02:4057 いつまでも寝ていられないわよー！).", 0, "all"),
    5: ("Agree with doubled",
        "Hum with ん mostly in H: んっ 23 (all in H), んん 8 (6 in H, 2 outside), んんっ 16 more; んーん 0.", 31, "H"),
    6: ("Show delight with",
        "Do not show delight with おおー / おー: 0 lines end on either; the one line with おー is a cheer (d17_01:1223 えいえいおー).", 0, "all"),
    7: ("Use plain childish words",
        "Childish words are not her habit: 8 spoken lines match any of いっぱい, きちゃう, えへへ (H 5, non-H 3).", 8, "all"),
    8: ("Stay casual",
        "Speak plain: です or ます is on 14 of 557 spoken lines (15 tokens), all of them outside H, mostly to other teachers or strangers (03_01:0644 野村先生). Her base register is plain with soft endings (わ, のよ, のね, かしら), not polite and not rough.", 543, "all"),
    9: ("Lean on the ellipsis",
        "Ellipsis runs 0.5772 … per line outside H (228 in 395) and 4.3827 inside H (710 in 162, moan elongation); the room runs at 0.9309 per line.", 228, None),
    10: ("Exclaim sparingly",
         "She exclaims and asks: outside H ！ 159 times (0.4025 per line) and ？ 146 (0.3696); in H ！ is 108 (0.6667 per line) and ？ 55 (0.3395). The room runs at 0.1341 ！ per line, so she is loud for the cast.", 159, None),
    11: ("Default to a smile face",
         "Smile is her commonest face outside H: 116 of 395 lines carry one; her 394 face hits are smile 116, surprise 81, talk 67, excited 55, neutral 44, sad 24, worried 7. H scenes carry no face (0 of 162).", 116, None),
    12: ("Bow (@おじぎ)",
         "Bow (@おじぎ) on 51 lines, 48 of them outside H and 18 with a smile.", 51, None),
    13: ("When refusing",
         "When refusing, @否定 (19 lines, all outside H); 6 of them go with a smile and 2 with a sad face.", 19, None),
    14: ("Jump (@ジャンプ)",
         "Jump (@ジャンプ) is common for her: 61 lines (56 outside H, 5 in H), 20 of them with surprise and 0 with a laugh.", 61, None),
    15: ("Keep the inner voice",
         "She has no inner voice in the record (0 inner lines). Do not write inner narration for her.", 0, "all"),
    16: ("Supply a face",
         "Non-H lines carry a face on 0.7949 (314 of 395) and a gesture on 0.4025 (159); H scenes carry a face on 0.0 (0 of 162) and a gesture on 0.0679 (11).", 314, None),
    17: ("Use @emotion overlays",
         "@emotion overlays are rare: 9 lines in all (キラン 2, 汗 2, はてな 1, びっくり 1, ぽわぽわ 1, キラキラ 1, ハート02 1). They are authored colour, not her mood words.", 9, None),
    18: ("Treat every expression label",
         "Treat every expression label as a C4 hypothesis (vocabulary 0.2) with a confidence, not a fact. The receipt 8/16 is a project-level figure shared by every subject, not a measure of her.", None, None),
    19: ("Remember that @おじぎ",
         "@おじぎ is the most common gesture corpus-wide (1576 calls), so her 51 bows are partly a house convention and not a trait of hers.", None, None),
    20: ("Keep kiss gestures",
         "Kiss gestures (@キス, @キス止め) are never hers: 0 lines. The kissing in 08_02 is written as sounds in her text (08_02:0414, 08_02:0445), not as a gesture.", 0, "all"),
    21: ("Keep dozing",
         "Dozing gestures (@居眠り横 / @居眠り縦) are never hers: 0 lines.", 0, "all"),
    22: ("Keep the H-scene vocabulary",
         "The H-scene vocabulary stays inside the H scene 08_02: 精液 or せーえき 6 lines, セックス 5, 中出し or 膣内 4, きちゃう 4, all in H and 0 outside. She does not say おちんちん or おまんこ (0 lines); she says ペニス on 8 lines (7 in H, 1 outside in d10_01:2212, where she repeats a student's question in a health class).", 15, None),
    23: ("Laugh rarely",
         "Laugh faces are never hers: 0 lines carry one. Her laugh is in the text instead: あは… on 17 lines (14 outside H, 3 in H), 20 with any laugh word.", 0, "all"),
    24: ("Voice her as cheerful",
         "Voice her as a warm, flustered adult teacher: plain forms with soft closings (のよ 47 lines, のね 38, かしら 27, わ-type closings 113), surname plus さん or 君 for every student, 先生 for herself, medium-length turns, and she replies far more than she opens. Not childlike, not polite-formal, not self-named by given name.", 543, "all"),
}

CLASS_NOTE = ("Every mechanism is classed `hers`: the matchers in tools/koikano/b3/chisa.py were written from her own lines "
              "(found by contrasting her non-H lines with the other named speakers in her scenes), and each recurs across "
              "her scenes. Nothing was classed `author` or `moment`. The `distinctive` flag compares her rate with those "
              "speakers; the B4 gate re-tested it on the holdout. Tiers follow the mechanism tier rule (see tier_rule).")
CROSS_REF = ("These are the moves that carry no `@emotion` / `@face` / `@action`. The surface rules they lean on "
             "(the plain register, the ellipsis, the ？ / ！ marks) are measured separately in `speech_guide` "
             "and in `voice.surface`; this section adds the move, not the mark.")

H_VOCAB = re.compile(r"精液|せーえき|セックス|中出し|なかだし|膣内|きちゃう")


def b5_counts():
    paths = kb.default_paths(kb.DEFAULT_CORPUS)
    recs = [r for r in kb.read_jsonl(paths["game_logic"]) if r["kind"] == "@Talk" and r["file"] != "macro.ks"]
    mine = [r for r in recs if r["speaker"] == "知紗"]
    addr = {}
    for f in ["十川さん", "千代田さん", "七瀬さん", "宮国君", "アリス会長", "真里亜さん", "真優さん", "小野坂君", "野村先生", "ケルベロス"]:
        addr[f] = sum(1 for r in mine if f in r["text"])
    end = {}
    for f in ["のよ", "のね", "かしら", "わね", "わよ", "だわ", "ちゃう", "ね", "よ"]:
        end[f] = sum(1 for r in mine if re.sub(r"[「」『』\s。！？…っ]", "", r["text"]).endswith(f))
    prev = Counter()
    for i, r in enumerate(recs):
        if r["speaker"] == "知紗" and i and recs[i - 1]["scene"] == r["scene"]:
            prev[recs[i - 1]["speaker"]] += 1
    mine_scenes = {r["scene"] for r in mine}
    scenes_with = {s: len({x["scene"] for x in recs if x["speaker"] == s} & mine_scenes)
                   for s in ["百花", "一悟", "真優", "千奈", "アリス", "真里亜", "ひかる"]}
    named = Counter()
    for r in recs:
        if r["speaker"] == "知紗":
            continue
        for f in ["榎本先生", "知紗先生", "知紗さん", "知紗せんせー", "知紗"]:
            if f in r["text"]:
                named[f] += 1
                break
    return {
        "source": "characters/chisa/b5_texts.py over game_logic.jsonl, her spoken lines (counts of lines)",
        "lines_containing_address_form": addr,
        "lines_ending_with": end,
        "replying_to_previous_speaker": dict(prev.most_common()),
        "scenes_shared_with": scenes_with,
        "room_lines_naming_her_first_matching_form": dict(named.most_common()),
        "h_vocabulary_lines_in_h_scene": sum(1 for r in mine if r["scene"] == "08_02" and H_VOCAB.search(r["text"])),
        "h_vocabulary_lines_outside": sum(1 for r in mine if r["scene"] != "08_02" and H_VOCAB.search(r["text"])),
    }


def main(d):
    bp = os.path.join(d, "bible.json")
    mp = os.path.join(d, "bible_readable.md")
    bible = json.load(open(bp, encoding="utf-8"))
    md = open(mp, encoding="utf-8", newline="").read()
    nl = "\r\n" if "\r\n" in md else "\n"
    md = md.replace("\r\n", "\n")

    sg = bible["speech_guide"]
    for i, (start, text, n, reg) in RULES.items():
        r = sg["rules"][i]
        assert r["rule"].startswith(start), (i, r["rule"][:30])
        old_rule, old_tier, old_reg = r["rule"], r["tier"], r["register"]
        r["rule"] = text
        r["tier_was"] = old_tier
        r["tier_n"] = n
        r["tier"] = tier_of(n)
        if reg:
            r["register"] = reg
        r.pop("text_basis", None)
        row_old = "| " + old_rule + " | " + r["class"] + " | " + old_tier + " | " + old_reg + " |"
        assert md.count(row_old) == 1, (i, old_rule[:30])
        md = md.replace(row_old, "| " + text + " | " + r["class"] + " | " + r["tier"] + " | " + r["register"] + " |")
    sg["tier_split"] = dict(sorted(Counter(r["tier"] for r in sg["rules"]).items()))
    sg["tier_rule"] = TIER_RULE
    sg["tier_note"] = ("The tool's tiers (firm 19, thin 6) were set by hand from 百花's numbers; tier_was keeps them. "
                       "Many firm rules had a receipt of 0 (ー, おおー, kiss, doze, laugh, inner voice).")

    mech = bible["mechanisms"]
    for m in mech["mechanisms"]:
        t = mech_tier(m)
        assert t == m["tier"], (m["key"], t, m["tier"])
        m["tier_n"] = m["lines"]
        m.pop("text_basis", None)
    mech["tier_rule"] = MECH_TIER_RULE
    old_note = mech["class_note"]
    mech["class_note"] = CLASS_NOTE
    old_cross = mech["cross_reference"]
    mech["cross_reference"] = CROSS_REF
    ts = dict(sorted(Counter(m["tier"] for m in mech["mechanisms"]).items()))
    assert ts == mech["tier_split"], (ts, mech["tier_split"])
    mech["firm_count"], mech["thin_count"], mech["weak_count"] = ts.get("firm", 0), ts.get("thin", 0), ts.get("weak", 0)
    bible["b5_counts"] = b5_counts()
    bible["meta"]["b5"] = "2026-10-24: speech-guide texts rewritten from her receipts, tiers from count rules (characters/chisa/b5_texts.py)"

    md = re.sub(r"tier \{'firm': 19, 'thin': 6\}", "tier %s" % sg["tier_split"], md, count=1)
    md = md.replace("a tier (firm / thin)", "a tier (firm / thin / weak, see tier_rule in bible.json)", 1)
    for old, new in ((old_note, CLASS_NOTE), (old_cross, CROSS_REF)):
        if old in md:
            md = md.replace(old, new)
        else:
            print("note: not in readable md (left):", old[:40])
    kb.write_json(bp, bible)
    open(mp, "w", encoding="utf-8", newline="").write(md.replace("\n", nl))
    print("speech tiers", sg["tier_split"], "mechanism tiers", ts)


# Own-rule markers (read by load_rule_markers in tools/koikano/koikano_bible_gate.py).
# Firm and thin speech-guide rules only. Patterns come from the build block's text, not the holdout.
# Rules with no marker (about length, turn order, faces or gestures, not in the spoken text): 1, 2, 11, 12,
# 13, 14, 16. Rule 8 (plain register) has none: its claim is an absence of です / ます and the gate matches presence.
# Weak rules (absences, caveats) carry none by design.
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', 'tools', 'koikano'))
import markers_io  # noqa: E402
MARKERS = markers_io.load('chisa')  # tools/koikano/markers/chisa.json is the source


def add_markers(d):
    """Idempotent. Run again after any rebuild: python b5_texts.py <dir> --markers-only"""
    bp = os.path.join(d, "bible.json")
    bible = json.load(open(bp, encoding="utf-8"))
    rules = bible["speech_guide"]["rules"]
    for i, pat in MARKERS.items():
        assert rules[i]["tier"] in ("firm", "thin"), (i, rules[i]["tier"])
        rules[i]["marker"] = {"pattern": pat}
    kb.write_json(bp, bible)
    print("markers on rules", sorted(MARKERS))


if __name__ == "__main__":
    if "--markers-only" in sys.argv:
        add_markers(sys.argv[1])
    else:
        main(sys.argv[1])
        add_markers(sys.argv[1])
