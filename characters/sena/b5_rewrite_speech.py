#!/usr/bin/env python3
"""B5 job 1: rewrite sena's speech_guide rule texts and B3 mechanism prose from her own receipts.

The B3/B2 text in bible.json was authored from 百花's numbers (tag `text_basis`). This script
replaces rule text and mechanism name/note with prose that cites only values found in sena's
own bible.json (receipts, voice, bounds, b5_receipts) and drops the tag. Run once; it is
idempotent (it overwrites the same fields). Check with b5_check_numbers.py.
"""
import json
from pathlib import Path

P = Path(__file__).resolve().parent / "bible.json"

RULES = {
    0: "Refer to yourself as 私: 466 spoken lines carry it (309 outside H, 157 in H). 千奈 as a self-name is rare (4 lines); use it only when asked to be called by name.",
    1: "Speak in mid-length turns: median 23 kept characters outside H, 32 inside H (pooled median 27, mean 25.65); no line over 62. One-word reactions exist but are not the norm.",
    2: "Reply; do not open. 2307 replies against 12 openings (reply rate 0.9948); the 12 are scene-opening turns such as 失礼します (08_01:0036). 1174 further lines continue her own turn.",
    3: "Glottal っ ends 770 of 3493 spoken lines (0.2204): 529 of 1121 in H, 241 of 2372 outside it. Outside H it is a startle or a push-back (ケルちゃん、ストップです…っ), not a verbal tic.",
    4: "ー endings are rare: 11 lines (0.0031), 7 outside H and 4 in H, and they are stares and sulks (じー……, うー……), not stretched sentence endings. Do not stretch.",
    5: "Doubled ん is an H sound for her, not an agreement: んっ 177 occurrences (167 in H, 10 outside), んん 31 (21 in H, 10 outside), んんっ 98, んーん 0. Outside H do not answer with ん.",
    6: "She does not say おおー / おー: 0 occurrences in all 3493 spoken lines. That is 百花's delight word; do not borrow it.",
    7: "Baby words are not her register: 21 lines match, 18 in H and 3 outside. いっぱい (5 occurrences) is the idiom (お腹いっぱい, 胸がいっぱい), えへへ and きちゃう have 0.",
    8: "Stay polite: です / ます in 2340 of 3493 spoken lines (3133 occurrences), 先輩 appears 1126 times in 67 of 72 scenes. The polite base is what makes the slips (ち、違うんですよ) show.",
    9: "Lean on the ellipsis: 1.6556 … per line outside H and 5.3524 inside H (moans), against 0.7989 for the room. Outside H it is hesitation and embarrassment (あ……ありがとうございます……).",
    10: "Exclaim more than the room outside H (0.2635 ！ per line against 0.1239 for the room; H 0.8394) and ask often (0.3044 ？ per line outside H, 0.2346 in H). Her ！ is mostly protest.",
    11: "Her face is mostly talk and surprise, not smile: labels on her lines are talk 1095, surprise 290, neutral 245, sad 194, laugh 120, smile 327 occurrences (325 non-H lines). H scenes carry no face.",
    12: "Bow (@おじぎ) is her commonest gesture on non-H lines: 340 lines (335 outside H, 5 in H), 71 with a smile. It is partly the house convention (see the corpus count in rule 19).",
    13: "A refusal is a flustered denial: @否定 on 144 occurrences (143 outside H), 22 with a smile and 12 with sad. Typical shape: い、いえ…… / ち、違うんですよ。",
    14: "@ジャンプ is a startle, not laughter: 228 occurrences, all outside H, 85 with a surprise label and 0 with a laugh label.",
    15: "Keep the inner voice as bare narration, not speech: no quotes, fewer ！ and ？, polite endings (した, ます, です), far more varied vocabulary (type-token ratio 0.9339 against 0.4803 for her speech), median 26 characters. It appears in both registers: 449 inner lines, 49 of them in H.",
    16: "Supply a face on 0.7078 of her non-H lines and a gesture on 0.347; H scenes carry no face (0.0) and almost no gesture (0.0068).",
    17: "Use @emotion overlays sparingly: 22 lines carry one (びっくり 6, 汗 5 are the commonest); they are authored colour, not her mood words.",
    18: "Treat every expression label as a C4 hypothesis with a confidence, not a fact: 8/16 classifiable units agreed, vocabulary version 0.2.",
    19: "Remember that @おじぎ is the most common gesture corpus-wide (1576 calls, 340 hers), so its frequency is partly a house convention.",
    20: "Keep kiss gestures (@キス, @キス止め) only with 一悟, only on route b: 3 lines, all of them route b and all with 一悟.",
    21: "Dozing (@居眠り) is almost absent from her: 1 line (c04_01:2779), route c, with 一悟. Do not make sleepiness a trait of hers.",
    22: "Keep H-scene vocabulary inside the 7 H scenes. The word list this rule was built from is 百花's and matches 0 of her lines; her own H words are in voice.distinctive (精液 64 against 1 in the room, 勃起 14, 中出 10).",
    23: "Laugh label: 120 non-H lines, never together with a jump (0). The label is a C4 guess and several of its sample lines are not laughter (うぐっ); her audible laugh is ふふっ / あははっ when tickled or amused (01_01:1783).",
    24: "Voice her as a polite, flustered, quick-tongued 私-speaker: です / ます in 2340 of 3493 lines, 先輩 in 1126 tokens, 1.6556 … per line outside H, third-person naming of herself in 4 lines only (the receipt key third_person_lines holds her 私 lines: 466).",
}

# rule index -> fit note when the receipt shows the rule is not hers
RULE_FIT = {
    6: "receipt 0: not hers",
    7: "receipt 21 lines, mostly H: not her register outside H",
    11: "smile is not her default face: 327 of 2303 expression occurrences",
    14: "co_laugh 0: jump is surprise only",
    21: "1 line: not a trait",
}

MECH = {
    "doubles_a_key_word": (
        "Doubles a word or phrase back to back",
        "95 lines (54 in H, 41 outside), 0.0272 of her spoken lines against 0.0342 for the room (251 lines): not above the room. The samples are set phrases (そもそも, それはそれは), lexical rather than emphasis. A house habit here, not a mark of hers.",
    ),
    "closes_a_turn_with_a_short_question": (
        "Rebounds with a short question",
        "229 lines (190 outside H, 39 in H), 0.0656 against 0.0811 for the room (596 lines) and 0.084 on the gate's held-out room. The matcher counts any line of 14 characters or fewer holding ？, so the samples are startle (ふぁっ！？) as much as questions. House style.",
    ),
    "plays_a_role_with_stock_catchphrases": (
        "Stock catchphrases (百花's move)",
        "1 line, in H, and the line (b05_02:1488) holds no catchphrase, so the hit is a false match. The room has 45. Not her move; do not give her a stage patter.",
    ),
    "performs_a_sound_effect": (
        "Sound effect in place of an action (百花's move)",
        "8 lines (5 in H, 3 outside), 0.0023 against 0.0071 for the room (52 lines). The samples are body words (むずむず, にやにや), not stage sounds. Not her move.",
    ),
    "labels_others_with_a_plain_noun": (
        "Pins a person to a plain noun (百花's move)",
        "0 lines; the room has 33 (0.0045). Not her move.",
    ),
    "attributes_her_limits_to_her_body": (
        "Blames a limit on a weak body",
        "1 line, outside H, and it is about 百花, not herself (d06_01:1205 百花は昔から身体が弱かったですから...). It shows she knows 百花's health history; it is not a way she refuses. Room: 29 lines.",
    ),
    "apologises_readily": (
        "Apologises",
        "44 lines (39 outside H, 5 in H), 0.0126 of her spoken lines against 0.0094 for the room (69 lines) and 0.0105 on the gate's held-out room: level with the room, not clearly above it. Samples: ごめんなさい (01_01:2109), ごめんなさい先生 (04_01:3090), お騒がせしてごめんなさい (05_01:4936).",
    ),
    "names_a_blow_with_a_loanword": (
        "Names a blow with a loanword (百花's move)",
        "1 line, and it is about someone else's shock (d13_01:0723 みゃー先輩の方がショックを受けて...). The room has 17. Not her move.",
    ),
    "coins_a_label_or_level": (
        "Coins a label or level (百花's move)",
        "2 lines (both outside H), 0.0006 against 0.003 for the room (22 lines). Both are her repeating another person's label in disbelief (なにが幼なじみレベルですか, 恋愛マスター！？), not coining one. Not her move.",
    ),
    "teases_in_a_mock_serious_register": (
        "Mock-serious tag or protest at being teased",
        "38 lines (25 in H, 13 outside), 0.0109 against 0.0046 for the room (34 lines) and 0.0064 on the gate's held-out room: above the room. In the samples she is the one being teased and answers with a tag (ずるい人ですね, からかわないでください). Read as protest, not as teasing.",
    ),
    "pivots_with_a_topic_marker": (
        "Pivots with a spoken marker",
        "14 lines (12 outside H, 2 in H), 0.004 against 0.0038 for the room (28 lines) and 0.0057 on the gate's held-out room. The samples are errand turns (そういえば先輩, 昨日の件で...) and one dodge (それより、あだ名の由来を掘り返さないでください). Level with the room.",
    ),
    "veils_it_as_a_secret": (
        "Declares something secret",
        "0 lines by this kana matcher (ひみつ / ないしょ / しーくれっと), room 5. The matcher misses kanji: 13 of her lines hold 秘密, 機密, ひみつ or ないしょ (b5_receipts.work). The real instance is her pen name and her genre, both kept secret (b01_01:3290, d10_01:0974). Hers, and not measurable by this matcher.",
    ),
    "hedges_with_kamo_kana": (
        "Hedges with かも / かな (room's move)",
        "0 lines against 160 for the room (0.0218). The matcher only reads line endings, so it is a lower bound. Not her move on this evidence.",
    ),
    "bargains_with_a_reward": (
        "Frames a request as a trade (matcher)",
        "9 lines (5 in H, 4 outside), 0.0026 against 0.0099 for the room (73 lines). The samples are conditionals (十川先輩がしゃんとしてくれたら！), not offers. Thin.",
    ),
}

DIST_NOTE = "B4 held out late route-b scenes and read the room's rate at or above hers on this move (see the gate rate on this row); kept and marked, not deleted."

MECH_TOP = {
    "class_note": "The `class: hers` and `tier` fields on these 14 rows are the tool's defaults, carried over from the 百花 build; they were not re-derived for 千奈. Read the counts and the notes: only a few of the 14 are her moves (apologises 44 lines, teases or protests 38, pivots 14, short question 229), the 百花-flavoured ones (catchphrases, sound effects, plain-noun labels, loanword blows) have 0 to 8 lines. Her own habits (polite register, 先輩, the stammered restart, 私) are in speech_guide, voice.surface and b5_receipts.own_moves.",
    "cross_reference": "These are the moves that carry no @emotion / @face / @action. Her surface marks are measured separately in speech_guide (私, です / ます, … and ！ rates, っ endings) and in voice.surface; this section adds the move, not the mark.",
}


OWN_B3_CLASS_NOTE = ("These mechanisms are her own reading (tools/koikano/b3/sena.py), set against the other six named heroines over the whole record, "
                     "not the default list carried over from 百花. Every row is classed hers because the matcher words were picked from what she says and the others do not. "
                     "Tier is set by characters/sena/tier_pass.py from the counts, the same rule as speech_guide (see its tier_rule field).")


def main():
    b = json.loads(P.read_text(encoding="utf8"))
    rules = b["speech_guide"]["rules"]
    assert len(rules) == len(RULES)
    for i, text in RULES.items():
        r = rules[i]
        r["rule"] = text
        r.pop("text_basis", None)
        if i in RULE_FIT:
            r["b5_fit"] = RULE_FIT[i]
        else:
            r.pop("b5_fit", None)
    m = b["mechanisms"]
    own_b3 = False
    for row in m["mechanisms"]:
        if row["key"] not in MECH:
            own_b3 = True  # her own B3 reading (tools/koikano/b3/sena.py): text is authored there, keep it
            continue
        name, note = MECH[row["key"]]
        row["name"] = name
        row["note"] = note
        row.pop("text_basis", None)
        if "distinctive_note" in row:
            row["distinctive_note"] = DIST_NOTE
    if own_b3:
        m["class_note"] = OWN_B3_CLASS_NOTE
    else:
        m["class_note"] = MECH_TOP["class_note"]
    m["cross_reference"] = MECH_TOP["cross_reference"]
    prov = b.setdefault("provenance", {})
    prov["b5_speech_rewrite"] = "2026-10-23: speech_guide rule texts and B3 mechanism names/notes rewritten from this file's own receipts (b5_rewrite_speech.py); text_basis tags removed. Mechanism class/tier fields are unchanged tool defaults."
    P.write_text(json.dumps(b, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf8")
    left = [r["rule"][:30] for r in rules if "text_basis" in r] + [x["key"] for x in m["mechanisms"] if "text_basis" in x]
    print("text_basis left:", left)


if __name__ == "__main__":
    main()
