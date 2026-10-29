# B5 job 1 for 真里亜 (2026-10-23): one tier rule from counts for every entry, speech-guide texts
# rewritten from her receipts, B3 class_note / cross_reference rewritten, b5_counts section added.
# usage: python b5_texts.py <dir with bible.json and bible_readable.md>
# Reads the record through tools/koikano/koikano_bible.py (read-only). Rules are matched by index and
# guarded by the start of the old text, so a rerun after the rewrite fails loudly.
import json
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools", "koikano"))
import koikano_bible as kb

TIER_RULE = ("one rule for every entry, from the count n of her lines (or occurrences where the receipt "
             "counts occurrences) behind the entry's headline claim: firm = n of 50 or more and not marked "
             "non-distinctive; thin = n of 10 to 49; weak = n under 10, an absence ('she does not do X', "
             "n is 0), a caveat with no count, or distinctive false")


def tier_of(n, distinctive=True):
    if n is None or n < 10 or distinctive is False:
        return "weak"
    return "firm" if n >= 50 else "thin"


# index: (start of the old text, new text, n for the tier rule, register override or None)
RULES = {
    0: ("Refer to yourself as",
        "Call yourself 私: 159 times on 156 of 1228 spoken lines (H 48 lines, non-H 108). Your own name 真里亜 is said of yourself twice, so you are not a third-person talker.", 156, "all"),
    1: ("Keep non-H turns short",
        "Keep turns medium: median 29 kept characters pooled (non-H 28, H 32), no line over 60.", 1228, None),
    2: ("Reply; do not open",
        "Reply; do not open. 1033 of her turns answer someone and 1 opens a scene (reply rate 0.999); 194 more continue her own turn.", 1033, None),
    3: ("End many lines on a glottal",
        "A glottal っ ending is an H habit: 84 lines end on っ, 74 of them in H (of 295 H lines) and 10 outside it (of 933).", 84, None),
    4: ("Stretch the last syllable",
        "Do not stretch the last syllable with ー: 0 spoken lines end on ー.", 0, "all"),
    5: ("Agree with doubled",
        "Hum with ん only in H: んっ 24 and んん 5, all of them in H scenes and none outside; んんっ 11 more.", 24, "H"),
    6: ("Show delight with",
        "Do not show delight with おおー / おー: 0 lines carry either.", 0, "all"),
    7: ("Use plain childish words",
        "Childish words are not her habit: 6 spoken lines match any of いっぱい, きちゃう, えへへ (いっぱい 2, きちゃう 0, えへへ 0).", 6, "all"),
    8: ("Stay casual",
        "Speak polite: です or ます is on 894 of 1228 spoken lines (1146 tokens), with everyone and in H scenes too. Polite is her base register, not an exception.", 894, "all"),
    9: ("Lean on the ellipsis",
        "Ellipsis runs 0.5445 … per line outside H (508) and 4.1627 inside H (1228, moan elongation); the room runs at 1.0602 per line.", 508, None),
    10: ("Exclaim sparingly",
         "Outside H she asks (？ 119 times, 0.1275 per line) and rarely exclaims (！ 17, 0.0182 per line); in H ！ rises to 83 (0.2814 per line) and ？ is 53.", 119, None),
    11: ("Default to a smile face",
         "Smile is her common face outside H: 505 of 933 lines carry one, and 535 of her 792 face hits are smile. H scenes carry no face (0 of 295).", 505, None),
    12: ("Bow (@おじぎ)",
         "Bow (@おじぎ) on 185 lines, 182 of them outside H and 117 with a smile.", 185, None),
    13: ("When refusing",
         "When refusing, @否定 (50 lines, 49 outside H); 31 of them go with a smile and 2 with a sad face.", 50, None),
    14: ("Jump (@ジャンプ)",
         "Jump (@ジャンプ) is rare for her: 7 lines, all outside H, 5 of them with surprise.", 7, None),
    15: ("Keep the inner voice",
         "She has no inner voice in the record (0 inner lines). Do not write inner narration for her.", 0, "all"),
    16: ("Supply a face",
         "Non-H lines carry a face on 0.7663 (715 of 933) and a gesture on 0.3462 (323); H scenes carry a face on 0.0 and a gesture on 0.0237 (7 of 295).", 715, None),
    17: ("Use @emotion overlays",
         "@emotion overlays are rare: 5 lines in all (キラキラ 3, キラン 1, 汗 1). They are authored colour, not her mood words.", 5, None),
    18: ("Treat every expression label",
         "Treat every expression label as a C4 hypothesis (vocabulary 0.2) with a confidence, not a fact. The receipt 8/16 is a project-level figure shared by every subject, not a measure of her.", None, None),
    19: ("Remember that @おじぎ",
         "@おじぎ is the most common gesture corpus-wide (1576 calls), so her 185 bows are partly a house convention and not a trait of hers.", None, None),
    20: ("Keep kiss gestures",
         "Kiss gestures (@キス, @キス止め) are never hers: 0 lines.", 0, "all"),
    21: ("Keep dozing",
         "Dozing gestures (@居眠り横 / @居眠り縦) are never hers: 0 lines.", 0, "all"),
    22: ("Keep the H-scene vocabulary",
         "The H-scene vocabulary (せーえき, おちんちん, おまんこ, きちゃう) stays inside H scenes: 45 lines there, 0 outside.", 45, None),
    23: ("Laugh rarely",
         "Laugh faces are never hers: 0 lines carry one. Her laugh is written into the text instead (うふふ, ふふ).", 0, "all"),
    24: ("Voice her as cheerful",
         "Voice her as a composed, polite maid: ladylike endings (ですわ, ますわ), a title for everyone (お嬢様 for 百花, 宮国様 for 一悟), soft laughter, medium-length turns, and she replies far more than she opens. Not cheerful or childlike, and not self-named.", 894, "all"),
}

CLASS_NOTE = ("Every mechanism is classed `hers`: the matchers in tools/koikano/b3/maria.py were written from her own lines, "
              "and each recurs across her scenes. Nothing was classed `author` or `moment`. The `distinctive` flag compares "
              "her rate with the other heroines in her scenes; the B4 gate re-tested it on the holdout. Tiers follow one count "
              "rule (see tier_rule): firm 50 lines or more, thin 10 to 49, weak under 10 or not distinctive.")
CROSS_REF = ("These are the moves that carry no `@emotion` / `@face` / `@action`. The surface rules they lean on "
             "(the polite です / ます register, the ellipsis, the ？ / ！ marks) are measured separately in `speech_guide` "
             "and in `voice.surface`; this section adds the move, not the mark.")


def b5_counts():
    paths = kb.default_paths(kb.DEFAULT_CORPUS)
    recs = [r for r in kb.read_jsonl(paths["game_logic"]) if r["kind"] == "@Talk" and r["file"] != "macro.ks"]
    mine = [r for r in recs if r["speaker"] == "真里亜"]
    addr = {}
    for f in ["お嬢様", "宮国様", "真優様", "千奈様", "アリス様", "榎本先生", "小野坂様", "ケルベロスさん", "ご主人様", "一悟様"]:
        addr[f] = sum(1 for r in mine if f in r["text"])
    end = {}
    for f in ["ですわ", "ますわ", "ですね", "ますね", "ですか？", "ございます", "いたします", "くださいませ"]:
        end[f] = sum(1 for r in mine if re.sub(r"[「」『』\s]", "", r["text"]).endswith(f))
    prev = Counter()
    prev_scene_lines = 0
    for i, r in enumerate(recs):
        if r["speaker"] == "真里亜" and i and recs[i - 1]["scene"] == r["scene"]:
            prev[recs[i - 1]["speaker"]] += 1
    scenes_with = {s: len({x["scene"] for x in recs if x["speaker"] == s} & {x["scene"] for x in mine})
                   for s in ["百花", "一悟", "真優", "千奈", "アリス", "知紗", "ひかる"]}
    return {
        "source": "characters/maria/b5_texts.py over game_logic.jsonl, her spoken lines (counts of lines)",
        "lines_containing_address_form": addr,
        "lines_ending_with": end,
        "replying_to_previous_speaker": dict(prev.most_common()),
        "scenes_shared_with": scenes_with,
        "room_lines_naming_her_真里亜": 167,
        "room_lines_naming_her_真里亜さん": 76,
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
        if i == 24:
            r["receipt"] = {"polite_lines": 894, "spoken_lines": 1228, "reply_rate": 0.999}
        row_old = "| " + old_rule + " | " + r["class"] + " | " + old_tier + " | " + old_reg + " |"
        assert md.count(row_old) == 1, (i, old_rule[:30])
        md = md.replace(row_old, "| " + text + " | " + r["class"] + " | " + r["tier"] + " | " + r["register"] + " |")
    sg["tier_split"] = dict(sorted(Counter(r["tier"] for r in sg["rules"]).items()))
    sg["tier_rule"] = TIER_RULE
    sg["tier_note"] = ("The tool's tiers (firm 19, thin 6) were set by hand from 百花's numbers; tier_was keeps them. "
                       "Several firm rules had a receipt of 0 (ー, おおー, kiss, doze, laugh, inner voice).")

    mech = bible["mechanisms"]
    for m in mech["mechanisms"]:
        t = tier_of(m["lines"], m["distinctive"])
        assert t == m["tier"], (m["key"], t, m["tier"])
        m["tier_n"] = m["lines"]
        m.pop("text_basis", None)
    mech["tier_rule"] = TIER_RULE
    mech["class_note"] = CLASS_NOTE
    old_cross = mech["cross_reference"]
    mech["cross_reference"] = CROSS_REF
    ts = dict(sorted(Counter(m["tier"] for m in mech["mechanisms"]).items()))
    assert ts == mech["tier_split"], (ts, mech["tier_split"])
    mech["firm_count"], mech["thin_count"], mech["weak_count"] = ts.get("firm", 0), ts.get("thin", 0), ts.get("weak", 0)
    bible["b5_counts"] = b5_counts()
    bible["meta"]["b5"] = "2026-10-23: speech-guide texts rewritten from her receipts, tiers from one count rule (characters/maria/b5_texts.py)"

    # readable md: rule split line, class note, cross reference
    md = re.sub(r"tier \{'firm': 19, 'thin': 6\}", "tier %s" % sg["tier_split"], md, count=1)
    md = md.replace("a tier (firm / thin)", "a tier (firm / thin / weak, see tier_rule in bible.json)", 1)
    k = md.index("Every mechanism is classed `hers`")
    e = md.index("\n", k)
    md = md[:k] + CLASS_NOTE + md[e:]
    if old_cross in md:
        md = md.replace(old_cross, CROSS_REF)
    kb.write_json(bp, bible)
    open(mp, "w", encoding="utf-8", newline="").write(md.replace("\n", nl))
    print("speech tiers", sg["tier_split"], "mechanism tiers", ts)


# Own-rule markers (read by load_rule_markers in tools/koikano/koikano_bible_gate.py).
# Firm and thin speech-guide rules only. Patterns come from the build block's text, not the holdout.
# Rules with no marker (nothing in the spoken text to match; they are about length, turn order,
# faces or gestures): 1 (turn length), 2 (reply, not open), 11 (smile face), 12 (bow), 13 (refusal
# gesture), 16 (face supply). Weak rules (absences, caveats) carry none by design.
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', 'tools', 'koikano'))
import markers_io  # noqa: E402
MARKERS = markers_io.load('maria')  # tools/koikano/markers/maria.json is the source


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
