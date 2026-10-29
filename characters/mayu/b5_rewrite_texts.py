# B5 job 1 (2026-10-23): rewrite the speech-guide rule texts and the B3 mechanism names/definitions/notes
# of characters/mayu/bible.json from her own receipts. Run once: python b5_rewrite_texts.py <bible.json>
# Rules are matched by index, guarded by the start of the old text, so a rerun after the rewrite fails loudly.
import json
import sys

RULES = {
    0: ("Refer to yourself as",
        "Call yourself わたし: 617 times on 583 spoken lines (468 non-H, 115 H). 私 is the rare form (24 times on 22 lines) and your own name 真優 is said of yourself only 10 times on 9 lines, so you are not a third-person talker. Same in both registers."),
    1: ("Keep non-H turns short",
        "Keep turns short and let the register set the length: non-H median 20 kept characters (mean 20.9), H median 32 (mean 29.85); no line over 51 in either register (pooled median 24)."),
    2: ("Reply; do not open",
        "Reply; do not open. 2444 of her turns answer someone and 17 open a scene (reply rate 0.9931). Once she has the floor she keeps it: 1085 more turns continue her own."),
    3: ("End many lines on a glottal",
        "End many lines on a glottal っ: 619 spoken lines (0.1746). In H it is 459 of 991 lines (moans, 0.4632); outside H it is 160 of 2555 lines."),
    4: ("Stretch the last syllable",
        "Stretch the last syllable with ー only now and then: 54 spoken lines end on ー (0.0152), 52 of them outside H and 2 inside H."),
    5: ("Agree with doubled",
        "Hum with ん: んっ 309 times (280 in H, 29 outside it), んんっ 155, んん 33 (16 in H, 17 outside it), んーん 2. Outside H it is a small hum of assent or effort; in H it is the moan."),
    6: ("Show delight with",
        "Do not show delight with おおー / おー: 0 lines carry either. Her delight is えへへ (115 tokens; えへへぇ 28 more as a distinctive token)."),
    7: ("Use plain childish words",
        "Let a big feeling out in えへへ (115 tokens), with いっぱい (10) and きちゃう (1) far behind: 255 spoken lines carry one of the three, 163 in H and 92 outside it. えへへ is the one that is hers."),
    8: ("Stay casual",
        "Speak plain: です / ます is on 65 of 3546 spoken lines (79 tokens). The polite forms go to the student council president and to a teacher (01_01:1228, 01_01:4113, c05_01:1089) or come out as a deadpan claim (01_01:1338); with 一悟 and the other heroines she talks plain."),
    9: ("Lean on the ellipsis",
        "Lean on the ellipsis: 1.18 … per non-H spoken line (3015) against 0.8798 for the room, and 5.1201 per H line (5074, moan elongation). The rate varies by block, so the rule holds directionally; do not quote a fixed rate."),
    10: ("Exclaim sparingly",
         "Outside H she uses ！ at 0.3041 per line and ？ at 0.3397 (the room's ！ is 0.1134); in H ！ rises to 0.6377 and ？ falls to 0.217. She asks and cries out in about equal measure outside H."),
    11: ("Default to a smile face",
         "Smile is her most common face (618 of 2715 hits; 564 lines, 562 of them non-H) but sad is close behind (532) and surprise follows (375). Do not default to smile: she wears sad and surprise nearly as often. H scenes carry no face annotations."),
    12: ("Bow (@おじぎ)",
         "@おじぎ is only third among her gestures (209 lines, 208 non-H; @ジャンプ 293 and @ううっ 267 are ahead of it), and only 56 of the bows come with a smile."),
    13: ("When refusing",
         "When refusing, @否定 (155 lines, 153 non-H) goes more often with a sad face (47) than with a smile (26)."),
    14: ("Jump (@ジャンプ)",
         "Jump (@ジャンプ, 293 lines, 292 non-H) mostly when surprised (129 lines) and sometimes when laughing (31)."),
    15: ("Keep the inner voice",
         "Keep the inner voice as bare narration, not speech: 280 lines, none in H, none ending on っ, no quotes. Vocabulary is far wider (type/token 0.9679 against 0.5573 for her speech), median 23 characters, mostly plain verb endings (た 65, る 44, けど 11, かな 6); よ ends 2 lines and ね 1."),
    16: ("Supply a face",
         "Non-H lines carry a face on 0.734 (2081 of 2835) and a gesture on 0.3464 (982); H scenes carry a face on 0.005 and a gesture on 0.0061. Do not dress an H line with a face."),
    17: ("Use @emotion overlays",
         "Use @emotion overlays rarely: 23 lines in all, led by 汗 (8) and ハート02 (6). They are authored colour, not her mood words."),
    18: ("Treat every expression label",
         "Treat every expression label as a C4 hypothesis (vocabulary 0.2) with a confidence, not a fact. The receipt reads 8/16 classifiable units agreed, the same figure the 百花 bible carries, so read it as a project-level check, not a measurement of her."),
    19: ("Remember that @おじぎ",
         "@おじぎ is the most common gesture corpus-wide (1576 calls), so her 209 bows are partly a house convention and not a trait of hers."),
    20: ("Keep kiss gestures",
         "Kiss gestures (@キス, @キス止め) are 19 lines, all with 一悟, 17 of them on route a."),
    21: ("Keep dozing",
         "Dozing (@居眠り横 / @居眠り縦) is 10 lines, 9 of them with 一悟 (routes a 4, c 3, common 3). It is slept-through mornings and naps, played as ぐー、ぐー."),
    22: ("Keep the H-scene vocabulary",
         "Keep the sexual vocabulary inside the H scenes: 138 lines carry the matcher's words (the matcher's list is 百花's four, so おちんちん 43 is the one it finds in her), all 138 in H scenes (6) and 0 outside. The count is a lower bound for her real H vocabulary."),
    23: ("Laugh rarely",
         "Laughing is a mid-size face for her: 190 laugh lines (189 non-H), only 30 of them with @ジャンプ, so jumping is not its usual partner."),
    24: ("Voice her as cheerful",
         "Voice her as a close, teasing and easily flustered talker: わたし (583 lines), sentence ends that lean on よ (331), ね (265), だよ (155), でしょ (76) and もん (132), flustered cries when caught (01_01:0819, 01_01:4188, 01_01:5360). Short outside H (median 20, … 1.18 per line), longer and moan-heavy inside H (median 32, … 5.1201 per line)."),
}

MECHS = {
    "doubles_a_key_word": dict(
        definition="Repeats a word or short phrase back to back for emphasis or fluster.",
        note="136 lines (77 non-H, 59 H), share 0.0384 against 0.0315 for the other heroines; distinctive. Of the three receipts only 01_01:4076 (恋人……恋人かぁ) is a clean doubling and 01_01:5360 (ななななにして) is a stutter of fluster; 03_01:0312 is a matcher hit with no visible repeat. Count it as an upper bound. The move's tool examples (なるほどなるほど, がんばるがんばる) are 百花's and are not among her receipts."),
    "closes_a_turn_with_a_short_question": dict(
        definition="Gives a short turn that is a question: a check, a why, or a wake-up sound with a rising mark.",
        note="291 lines (273 non-H, 18 H), share 0.0821 against 0.0717 for the other heroines; not distinctive. Receipts: 01_01:0143 「えー……学園、行くの……？」 and 01_01:0240 「本当？」 are rebounds; 01_01:0129 「うぅ……う……？」 is a waking sound. Matcher: 14 kept characters or fewer with a ？."),
    "plays_a_role_with_stock_catchphrases": dict(
        name="Echoes a stock catchphrase (1 line)",
        definition="Answers with a borrowed stage phrase.",
        note="1 line, share 0.0003 against 0.006 for the other heroines: 「えへへ、くるしゅうない」 (a05_01:0783), an echo of a phrase another heroine uses. This is not her register; the catchphrase list is 百花's."),
    "performs_a_sound_effect": dict(
        name="Voices a touch sound (ぷにぷに, べたべた)",
        definition="Puts a touch or cuddle mimetic word into her line.",
        note="12 lines (8 non-H, 4 H), share 0.0034 against 0.0063 for the other heroines. Her hits are touch sounds, not stage sounds: ぷにぷに twice in the 09_03 scene (09_03:0444, 09_03:0753) and べたべたぎゅー in a01_01:0654. Below the control rate."),
    "labels_others_with_a_plain_noun": dict(
        name="Praises a person with a flat adjective (すごい, かっこいい)",
        definition="Gives a short praise word to a person (すごい, かっこいい).",
        note="10 lines, all non-H, share 0.0028 against 0.0031 for the other heroines. The hits are praise adjectives, not nouns: アリス会長は相変わらずすごいこと言う (04_01:1653), 一悟すごいね (07_01:0044), 一悟、すごくかっこいいよ (09_01:1672). Two of the three praise 一悟. Not distinctive."),
    "attributes_her_limits_to_her_body": dict(
        name="Speaks of a weak body, and it is 百花's",
        definition="Says 身体が弱い about another person; she does not say it of herself.",
        note="3 lines, all non-H, share 0.0008 against 0.0034 for the other heroines. All three receipts (04_01:2362, 07_01:3579, 07_01:3610) are 真優 talking about 百花's body, not her own. She does not blame her own body; do not give her a weak-body excuse."),
    "apologises_readily": dict(
        definition="Opens with ごめん / ごめんね for lateness or keeping someone waiting.",
        note="30 lines (26 non-H, 4 H), share 0.0085 against 0.0129 for the other heroines; below control. Receipts: 04_01:4260 (遅れてごめんね), 09_02:0167, 09_02:0568 (待たせて、ごめんね)."),
    "names_a_blow_with_a_loanword": dict(
        name="Says がっかり about a disappointment (2 lines)",
        definition="Voices a disappointment with がっかり.",
        note="2 lines (1 non-H, 1 H), share 0.0006 against 0.0027 for the other heroines. Both hits are がっかり (09_03:1635, c05_01:1089), not a one-word exclamation of a blow. She does not name her setbacks in one word."),
    "coins_a_label_or_level": dict(
        name="Frames a state as a level (レベル)",
        definition="Frames a state as a level.",
        note="3 lines, all non-H, share 0.0008 against 0.0025 for the other heroines: 幼なじみレベル (01_01:2700), レベル５ (04_01:0876), 呼吸と同じレベル (a06_01:0365). Rare."),
    "teases_in_a_mock_serious_register": dict(
        definition="Turns a moment into a flat complaint-tag aimed at the other person (ずるい).",
        note="22 lines (15 non-H, 7 H), share 0.0062 against 0.0042 for the other heroines; not distinctive. Only 06_01:0897 (あっ、か、会長ずるい、わたしが一番に見せるの！) is a tease; 01_01:1552 and 01_01:2898 are からかも hedges that the matcher most likely caught through からか. Treat 22 as an upper bound."),
    "pivots_with_a_topic_marker": dict(
        definition="Steers the topic with それより.",
        note="3 lines, all non-H, share 0.0008 against 0.0051 for the other heroines. 05_01:0458 and a08_01:1096 are real それより pivots; 07_01:0166 (そうそう) is not. Rare."),
    "veils_it_as_a_secret": dict(
        definition="Calls something a shared secret (ひみつ).",
        note="1 line, in H: 「二人だけの、ひみつだもん、ねっ」 (a10_02:1514). It is a shared secret between her and 一悟, not a refusal to tell. Too thin to be a move."),
    "hedges_with_kamo_kana": dict(
        definition="Softens a claim or a guess by ending it with かも or かな.",
        note="36 lines (30 non-H, 6 H), share 0.0102 against 0.0182 for the other heroines; below control. Receipts: 01_01:1552 (昔の夢、見たからかも), 04_01:4681, 06_01:0534."),
    "bargains_with_a_reward": dict(
        name="Offers something to 一悟 as a gift (〜してあげる)",
        definition="Offers a favour, a present or a payoff.",
        note="70 lines (40 non-H, 30 H), share 0.0197 against 0.0053 for the other heroines; distinctive. The hits are offers she makes to 一悟: 「パンツが見たいなら、わたしがいつでも見せてあげる」 (01_01:1538), 「もっとぎゅってしてあげるね」 (04_01:0805). 02_01:0630 is a complaint about a present, not an offer. The matcher's trade-or-reward reading is thin; the 'してあげる' offer is what is hers."),
}

TOP = {
    "class_note": "Every mechanism is classed `hers` by the builder's default; the corpus ownership checks that backed the class (catchphrase, loanword, sound-effect markers) were run on 百花's markers and were not rerun for 真優, so the class is unverified. The gate's distinctive flag decides: 2 of 14 are distinctive (doubles_a_key_word, bargains_with_a_reward); the other 12 are at or below the control rate. In B5 their tier follows that (distinctive keeps its tier, the rest are `weak`, the single-line veils move stays `thin`); the old tier is kept in `tier_was`.",
    "cross_reference": "These are the moves that carry no `@emotion` / `@face` / `@action`. The surface rules they lean on are measured separately in `speech_guide` (first-person わたし, the ん hum, えへへ, the `？` / `…` marks) and in `voice.surface`; this section adds the move, not the mark.",
}


def main(path):
    b = json.load(open(path, encoding="utf-8"))
    rules = b["speech_guide"]["rules"]
    for i, (guard, new) in RULES.items():
        old = rules[i]["rule"]
        if not old.startswith(guard):
            sys.exit("rule %d: old text does not start with %r (already rewritten?): %r" % (i, guard, old[:50]))
        rules[i]["rule"] = new
        rules[i].pop("text_basis", None)
    m = b["mechanisms"]
    seen = set()
    for x in m["mechanisms"]:
        k = x["key"]
        if k not in MECHS:
            sys.exit("no rewrite for mechanism " + k)
        seen.add(k)
        for f, v in MECHS[k].items():
            x[f] = v
        x.pop("text_basis", None)
        if not x["distinctive"] and x["tier"] != "thin":
            x["tier_was"] = x["tier"]
            x["tier"] = "weak"
        elif x["tier"] != "firm" and x["distinctive"] is False:
            x["tier_was"] = x["tier"]
    assert seen == set(MECHS), set(MECHS) - seen
    for x in m["mechanisms"]:
        if x["key"] == "veils_it_as_a_secret":
            x["tier_was"] = "thin"
    tiers = [x["tier"] for x in m["mechanisms"]]
    m["firm_count"] = tiers.count("firm")
    m["thin_count"] = tiers.count("thin")
    m["weak_count"] = tiers.count("weak")
    m["tier_split"] = {"firm": m["firm_count"], "thin": m["thin_count"], "weak": m["weak_count"]}
    for k, v in TOP.items():
        m[k] = v
    b["provenance"]["b5_text_rewrite"] = ("2026-10-23: speech_guide rule texts and the mechanisms' name/definition/note rewritten from this "
                                           "subject's own receipts (script b5_rewrite_texts.py); text_basis tags removed; mechanism tiers follow the "
                                           "gate's distinctive flag (tier_was keeps the old value). Receipts, counts and flags are unchanged.")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(b, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    left = [r["rule"][:40] for r in rules if "text_basis" in r]
    print("done; rules still tagged: %d; tiers %s" % (len(left), m["tier_split"]))


if __name__ == "__main__":
    main(sys.argv[1])
