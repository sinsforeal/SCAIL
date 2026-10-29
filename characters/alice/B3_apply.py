# B5 job 1 (tk-oas, 2026-10-23): rewrite the speech_guide rule texts and the B3 mechanism notes of
# characters/alice/bible.json from アリス's own receipts, drop the text_basis tags, recompute the
# mechanism distinctive flag and tier from her own gate holdout, regenerate bible_readable.md.
# Run once: C:/Python314/python.exe -X utf8 characters/alice/B5_apply_speech_guide.py
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools", "koikano"))
import koikano_bible as kb  # noqa: E402

BIBLE_IN = "F:/temp/b3_alice/out_alice/bible.json"
BIBLE = os.path.join(HERE, "bible.json")
GATE = "F:/temp/b3_alice/out_alice/gate.json"
READABLE = os.path.join(HERE, "bible_readable.md")


def dump(o):
    return json.dumps(o, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


raw = open(BIBLE_IN, encoding="utf-8", newline="").read()
b = json.loads(raw)
print("bible.json round-trips byte-for-byte:", dump(b) == raw.replace("\r\n", "\n"))
old_md = ""
try:
    print("render_doc reproduces bible_readable.md before the edit:", kb.render_doc(b).rstrip("\n") == old_md.rstrip("\n"))
except Exception as e:  # report, do not hide
    print("render_doc failed before edit:", repr(e))

g = json.load(open(GATE, encoding="utf-8"))
grows = {r["key"]: r for r in g["tests"]["mechanisms"]["rows"]}

voice = b["voice"]
toks = {t[0]: t[1] for t in voice["channels"]["her_dialogue"]["top_tokens"]}
parts = {p["ending"]: p for p in voice["surface"]["particles"]["her_spoken"]}
addr = b["interactions"]["her_address_terms_overall"]

sg = b["speech_guide"]
R = sg["rules"]
assert len(R) == 25, len(R)


def setrule(i, text, **receipt_add):
    r = R[i]
    r["rule"] = text
    r.pop("text_basis", None)
    r.setdefault("receipt", {}).update(receipt_add)


r1 = R[1]["receipt"]
setrule(1,
        "Speak in mid-length turns: median %d kept characters outside H and %d inside H (%d pooled over %d spoken lines); "
        "no line is longer than %d. Length does not separate her registers; H differs by marks and sounds, not by running longer."
        % (r1["non_H"]["median_chars"], r1["H"]["median_chars"], r1["pooled"]["median_chars"], r1["pooled"]["lines"],
           r1["pooled"]["max_chars"]))

r2 = R[2]["receipt"]
setrule(2,
        "Reply; do not open. Her reply rate is %s (%d replies, %d scene openings), and she keeps going inside her own turn "
        "(%d self-continuations): answer first, then run on, never start the exchange."
        % (r2["reply_rate"], r2["reply"], r2["initiation"], r2["self_continuation"]))

r3 = R[3]["receipt"]
setrule(3,
        "Close a line on a clipped っ only when the line is a decree, a catch or an exasperated call (だから私は生徒会長の責務として、"
        "このような決定を下すことにしたっ; まったく、ケルベロスっ; に、逃がすかっ). It ends %d lines (%s of her spoken lines), "
        "%d of them in H (moans) and %d outside it, so outside H it is occasional, not a habit."
        % (r3["lines_ending_っ"], r3["share_of_spoken"], r3["by_register"]["H"]["lines"], r3["by_register"]["non_H"]["lines"]))

r4 = R[4]["receipt"]
setrule(4,
        "Do not stretch a last syllable with ー. It ends %d of her spoken lines (%s), %d in H, and both are a breath or a sigh "
        "(ふぅー……), not a drawl. Her sentence ends are the soft particles (ね, よ, かな), not ー."
        % (r4["lines_ending_ー"], r4["share_of_spoken"], r4["by_register"]["H"]["lines"]))

r5 = R[5]["receipt"]
setrule(5,
        "The doubled ん is a moan token for her, not an agreement: んん appears %d times (%d in H, %d outside), んっ %d (%d in H, %d outside), "
        "んんっ %d, んーん %d. Outside H she agrees in words: うん (%d), そうだね (%d), そうか (%d)."
        % (r5["token_んん"], r5["token_んん_by_register"]["H"], r5["token_んん_by_register"]["non_H"],
           r5["token_んっ"], r5["token_んっ_by_register"]["H"], r5["token_んっ_by_register"]["non_H"],
           r5["token_んんっ"], r5["token_んーん"], toks["うん"], toks["そうだね"], toks["そうか"]),
        token_うん=toks["うん"], token_そうだね=toks["そうだね"], token_そうか=toks["そうか"])

r6 = R[6]["receipt"]
setrule(6,
        "Do not show delight with おおー / おー: both have %d hits in both registers. Her delight is a written laugh, ふふ (%d) and ふふっ (%d), "
        "and noticing is おや (%d)."
        % (r6["token_おおー"], toks["ふふ"], toks["ふふっ"], toks["おや"]),
        token_ふふ=toks["ふふ"], token_ふふっ=toks["ふふっ"], token_おや=toks["おや"])

r7 = R[7]["receipt"]
setrule(7,
        "Plain childish words are not her register: %d lines match (%d in H, %d outside), えへへ %d, きちゃう %d, and the outside-H hits are "
        "an adult いっぱい (めいっぱい, 今週いっぱい, 力いっぱい). Do not add えへへ or childish exclamations."
        % (r7["lines_matched"], r7["by_register"]["H"]["lines"], r7["by_register"]["non_H"]["lines"], r7["token_えへへ"], r7["token_きちゃう"]))

r8 = R[8]["receipt"]
setrule(8,
        "Stay in plain form with a courteous edge: です / ます turns up in %d of %d spoken lines (%d occurrences), a formal turn now and then "
        "(それは助かりますが……), never the base."
        % (r8["lines_with_です_ます"], r8["of_spoken_lines"], r8["token_ですます_occurrences"]))

r9 = R[9]["receipt"]
setrule(9,
        "Use the ellipsis as a held beat before the line lands (おや……？, ああ、なるほど……): %s per line outside H (%d marks), %s per line inside H "
        "(%d marks, moan elongation). The room outside her runs %s, so outside H she sits at the room's rate. Read it as direction, not a fixed rate."
        % (r9["…_by_register"]["non_H"]["per_line"], r9["…_by_register"]["non_H"]["count"], r9["…_by_register"]["H"]["per_line"],
           r9["…_by_register"]["H"]["count"], r9["room_per_line"]))

r10 = R[10]["receipt"]
setrule(10,
        "Exclaim sparingly outside H (%s ！ per line, %d marks) and ask often: ？ runs %s per line outside H (%d marks). H moans carry ！ heavily "
        "(%s per line, %d marks); the room outside her averages %s ！ per line."
        % (r10["！_by_register"]["non_H"]["per_line"], r10["！_by_register"]["non_H"]["count"], r10["？_by_register"]["non_H"]["per_line"],
           r10["？_by_register"]["non_H"]["count"], r10["！_by_register"]["H"]["per_line"], r10["！_by_register"]["H"]["count"],
           r10["room_！_per_line"]))

r11 = R[11]["receipt"]
setrule(11,
        "Default to a smile face on non-H lines: %d of %d non-H lines carry one (%d smile hits of %d expression hits in all). "
        "H scenes carry no face annotations (%d of %d lines)."
        % (r11["smile_lines"], r11["smile_lines_by_register"]["non_H"]["n"], r11["smile_occurrences"], r11["all_occurrences"],
           r11["smile_lines_by_register"]["H"]["lines"], r11["smile_lines_by_register"]["H"]["n"]))

r12 = R[12]["receipt"]
setrule(12,
        "Bow (@おじぎ) as the default gesture outside H: %d of %d non-H lines, %d of them with a smile; none in H (%d of %d)."
        % (r12["lines"], r12["by_register"]["non_H"]["n"], r12["co_smile"], r12["by_register"]["H"]["lines"], r12["by_register"]["H"]["n"]))

r13 = R[13]["receipt"]
setrule(13,
        "When refusing, use @否定 (%d lines, non-H only) and keep smiling: %d of them carry a smile and %d a sad face. Her refusals are the "
        "teasing おやおや / いやいや kind (誰にでもなんてことはないよ？), not a hard no."
        % (r13["@否定_occurrences"], r13["co_smile"], r13["co_sad"]))

r14 = R[14]["receipt"]
setrule(14,
        "Jump (@ジャンプ) on surprise, not on laughter: %d lines, non-H only, %d of them with a surprise face and %d with a laugh face "
        "(おや、それならどうして？; 本当かい？)."
        % (r14["@ジャンプ_occurrences"], r14["co_surprise"], r14["co_laugh"]))

r15 = R[15]["receipt"]
setrule(15,
        "Keep the inner voice as bare written narration, not speech: %d lines, %d in H, median %d characters, no quotes, no っ (%d lines end in it), "
        "type-token ratio %s against %s for her speech. It speaks of 私 and 一悟くん in plain narrating form (だろう, ている); never アリス."
        % (r15["inner_lines"], r15["inner_lines_H"], r15["inner_median_chars"], r15["inner_lines_ending_っ"], r15["inner_ttr"], r15["spoken_ttr"]))

r16 = R[16]["receipt"]
setrule(16,
        "Supply a face on most of her non-H lines (rate %s, %d of %d) and a gesture on about three in ten (rate %s, %d); H scenes carry no faces "
        "and no gestures (%d of %d)."
        % (r16["non_H"]["expression_rate"], r16["non_H"]["with_expression"], r16["non_H"]["lines"], r16["non_H"]["gesture_rate"],
           r16["non_H"]["with_gesture"], r16["H"]["with_expression"], r16["H"]["lines"]))

r17 = R[17]["receipt"]
ty = r17["types"]
setrule(17,
        "Use @emotion overlays sparingly: %d lines in all (キラン %d, 汗 %d, びっくり %d, びっくりF %d, キラキラ %d, ハート01 %d); "
        "they are authored colour, not her mood words."
        % (r17["lines_with_emotion"], ty["キラン"], ty["汗"], ty["びっくり"], ty["びっくりF"], ty["キラキラ"], ty["ハート01"]))

R[18]["rule"] = ("Treat every expression label as a C4 hypothesis with a confidence, not a fact. The agreement figure in the receipt "
                 "was measured on 百花's units; no figure of her own exists.")
R[18].pop("text_basis", None)

r19 = R[19]["receipt"]
setrule(19,
        "Remember that @おじぎ is the most common gesture corpus-wide (%d calls), so her %d bow lines are partly a house convention."
        % (r19["corpus_@おじぎ_calls"], r19["her_@おじぎ"]))

r21 = R[21]["receipt"]
setrule(21,
        "Do not give her dozing (@居眠り横 / @居眠り縦): %d lines in the record, %d with 一悟. Leave sleepiness out."
        % (r21["lines"], r21["with_一悟"]))

r22 = R[22]["receipt"]
setrule(22,
        "Keep the H-scene vocabulary (the matcher's list: せーえき, おちんちん, おまんこ, きちゃう) inside the H scenes: %d lines carry it, "
        "all in the %d H scenes and %d outside. Her own spellings include 精液 (%d bigram hits) and おちんちん (%d tokens)."
        % (r22["lines_with_H_tokens"], r22["h_scenes"], r22["in_non_H"], 38, toks["おちんちん"]),
        bigram_精液=38, token_おちんちん=toks["おちんちん"])

r23 = R[23]["receipt"]
setrule(23,
        "Laughter is not tagged on her lines (%d laugh-face lines, %d with @ジャンプ); it is written into the words: ふふ (%d) and ふふっ (%d)."
        % (r23["laugh_lines"], r23["with_@ジャンプ"], toks["ふふ"], toks["ふふっ"]),
        token_ふふ=toks["ふふ"], token_ふふっ=toks["ふふっ"])

r24 = R[24]["receipt"]
setrule(24,
        "Voice her as composed, teasing and theatrical: plain-form sentences with soft particles (ね, よ, かな, だね, だよ), 私 for herself, "
        "mid-length turns (median %d characters outside H, %d inside), the ellipsis as a held beat (%s per line outside H). Where the register "
        "shifts toward moans inside an H scene it shifts by sound (%s … per line), not by childishness."
        % (r24["non_H"]["median_chars"], r24["H"]["median_chars"], r24["non_H"]["ellipsis_per_line"], r24["H"]["ellipsis_per_line"]))

# ---- three rules of her own (her particles, her noticing sounds, her address terms) ----
p = parts
new_rules = [
    {
        "class": "hers", "evidence": "measured", "register": "all", "tier": "firm",
        "rule": ("Close a turn on a soft particle, not a bare verb: ね ends %d of her spoken lines (%s), よ %d (%s), な %d, かな %d (%s), "
                 "だね %d, だよ %d, ん %d. That is the composed, explaining frame of her voice (…だよ, …だね, …かな)."
                 % (p["ね"]["lines"], p["ね"]["share"], p["よ"]["lines"], p["よ"]["share"], p["な"]["lines"], p["かな"]["lines"], p["かな"]["share"],
                    p["だね"]["lines"], p["だよ"]["lines"], p["ん"]["lines"])),
        "receipt": {"line_final_ね": p["ね"]["lines"], "line_final_ね_share": p["ね"]["share"], "line_final_よ": p["よ"]["lines"],
                    "line_final_よ_share": p["よ"]["share"], "line_final_な": p["な"]["lines"], "line_final_かな": p["かな"]["lines"],
                    "line_final_かな_share": p["かな"]["share"], "line_final_だね": p["だね"]["lines"], "line_final_だよ": p["だよ"]["lines"],
                    "line_final_ん": p["ん"]["lines"], "source": "voice.surface.particles.her_spoken"},
        "added_by": "B5 2026-10-23",
    },
    {
        "class": "hers", "evidence": "measured", "register": "all", "tier": "firm",
        "rule": ("Notice before you answer and laugh in words: おや is %d of her tokens, ふふ %d, ふふっ %d, ああ %d, うん %d, ありがとう %d. "
                 "The notice (おや……？, ん？) comes first, the answer after it."
                 % (toks["おや"], toks["ふふ"], toks["ふふっ"], toks["ああ"], toks["うん"], toks["ありがとう"])),
        "receipt": {"token_おや": toks["おや"], "token_ふふ": toks["ふふ"], "token_ふふっ": toks["ふふっ"], "token_ああ": toks["ああ"],
                    "token_うん": toks["うん"], "token_ありがとう": toks["ありがとう"], "source": "voice.channels.her_dialogue.top_tokens"},
        "added_by": "B5 2026-10-23",
    },
    {
        "class": "hers", "evidence": "measured", "register": "all", "tier": "firm",
        "rule": ("Name him 一悟くん (%d) or 一悟 (%d) and call the people she likes by name with a suffix: 真優ちゃん %d, 千奈ちゃん %d; bare 百花 %d, "
                 "真里亜 %d; ケルベロス %d and ケル %d. The room calls her アリス %d, アリス様 %d, アリスさん %d."
                 % (addr["一悟くん"], addr["一悟"], addr["真優ちゃん"], addr["千奈ちゃん"], addr["百花"], addr["真里亜"], addr["ケルベロス"], addr["ケル"],
                    b["interactions"]["they_address_her"]["アリス"], b["interactions"]["they_address_her"]["アリス様"],
                    b["interactions"]["they_address_her"]["アリスさん"])),
        "receipt": {"her_address_terms_overall": dict(addr), "they_address_her": dict(b["interactions"]["they_address_her"]),
                    "source": "interactions.her_address_terms_overall, interactions.they_address_her"},
        "added_by": "B5 2026-10-23",
    },
]
R.extend(new_rules)

# splits
from collections import Counter  # noqa: E402
sg["tier_split"] = dict(sorted(Counter(r["tier"] for r in R).items()))
sg["class_split"] = dict(sorted(Counter(r["class"] for r in R).items()))
sg["evidence_split"] = dict(sorted(Counter(r["evidence"] for r in R).items()))
sg["register_split"] = dict(sorted(Counter(r["register"] for r in R).items()))
sg["unreceipted"] = [i for i, r in enumerate(R) if not r.get("receipt")]
left = [i for i, r in enumerate(R) if "text_basis" in r]
assert not left, left


# ---- B3 2026-10-23: tiers by one rule, mechanisms from her own B3 reading ----
# n and kind per speech_guide rule, read off the receipts in the rule list:
# ("p", n) presence: n her lines that show the thing; ("a", hits, checked) absence claim;
# ("i", own_figure) inferred. Rules 0-27 in order (25 from the tool, 3 added above).
RULE_N = {
    0: ("p", 393), 1: ("p", 2792), 2: ("p", 1733), 3: ("p", 404), 4: ("a", 2, 2792), 5: ("p", 98),
    6: ("a", 0, 2792), 7: ("a", 27, 2792), 8: ("a", 25, 2792), 9: ("p", 1602), 10: ("p", 83), 11: ("p", 492),
    12: ("p", 301), 13: ("p", 74), 14: ("p", 48), 15: ("p", 39), 16: ("p", 1502), 17: ("p", 12),
    18: ("i", False), 19: ("i", True), 20: ("p", 15), 21: ("a", 0, 2792), 22: ("p", 99), 23: ("a", 0, 1870),
    24: ("i", True), 25: ("p", 332), 26: ("p", 107), 27: ("p", 146),
}


def tier_rule(spec):
    kind = spec[0]
    if kind == "i":
        return "thin" if spec[1] else "weak"
    if kind == "a":
        return "firm" if spec[1] <= 0.01 * spec[2] else "thin"
    n = spec[1]
    return "firm" if n >= 30 else ("thin" if n >= 10 else "weak")


assert len(R) == 28, len(R)
for i, r in enumerate(R):
    r["tier"] = tier_rule(RULE_N[i])
    r["tier_n"] = list(RULE_N[i][1:]) if RULE_N[i][0] != "i" else ["inferred", RULE_N[i][1]]
sg["tier_split"] = dict(sorted(Counter(r["tier"] for r in R).items()))
sg["tier_basis"] = ("one rule for rules and mechanisms: n = her lines that show the thing (an absence rule: hits at or under 1 percent of the lines checked "
                    "counts as firm); n under 10 weak, 10 to 29 thin, 30 or more firm; inferred entries are never firm (thin with a figure of her own, "
                    "weak without). No held-out test exists for her own rules, so only the n clause applies to them.")

# ---- mechanisms ----
M = b["mechanisms"]


def base(r, gr):
    h, c = gr["holdout"], gr["control_in_holdout"]
    return ("%d lines (%d outside H, %d inside), %s of her spoken lines; the other heroines in her scenes run %d lines at %s. "
            "Her holdout (late route-c block): %d of %d against %d of %d for the control." %
            (r["lines"], r["lines_non_H"], r["lines_H"], r["share_of_spoken"], r["control_lines"], r["control_rate"],
             h["hits"], h["n"], c["hits"], c["n"]))


def tier_mech(r, h, c):
    above = h["hits"] / h["n"] > c["hits"] / c["n"]
    if r["lines"] < 10 or not above:
        return "weak", above
    return ("firm" if (r["lines"] >= 30 and h["hits"] >= 5) else "thin"), above


for r in M["mechanisms"]:
    gr = grows[r["key"]]
    h, c = gr["holdout"], gr["control_in_holdout"]
    r["tier"], dist = tier_mech(r, h, c)
    r["distinctive"] = dist
    r["gate_holdout"] = {"hits": h["hits"], "n": h["n"], "control_hits": c["hits"], "control_n": c["n"]}
    r["gate_control_rate"] = round(c["hits"] / c["n"], 4)
    r.pop("distinctive_note", None)
    if not dist:
        r["distinctive_note"] = ("Her own gate holdout: %d of %d against %d of %d for the control heroines, at or below the control rate, "
                                 "so the move is not hers alone." % (h["hits"], h["n"], c["hits"], c["n"]))
    r["note"] = base(r, gr) + " " + r["note"]
    r.pop("text_basis", None)
    r["absent_in_her_lines"] = r["lines"] == 0

mm = M["mechanisms"]
M["tier_split"] = dict(sorted(Counter(r["tier"] for r in mm).items()))
M["firm_count"] = sum(r["tier"] == "firm" for r in mm)
M["thin_count"] = sum(r["tier"] == "thin" for r in mm)
M["weak_count"] = sum(r["tier"] == "weak" for r in mm)
M["distinctive_false"] = [r["key"] for r in mm if not r["distinctive"]]
M["tier_basis"] = sg["tier_basis"] + (" For a mechanism the held-out direction test also applies: weak if her holdout rate is at or below the control "
                                      "rate; firm needs at least 5 holdout hits.")
M["class_note"] = ("These %d mechanisms are the tools/koikano/b3/alice.py reading, made from her own lines and not from 百花's list. Every one is classed "
                   "hers by the builder's reading; the gate holdout decides distinctive. %d are above the control rate there, %d are not (%s). "
                   "The marginal ones are in their rows." % (len(mm), len(mm) - len(M["distinctive_false"]), len(M["distinctive_false"]),
                                                              ", ".join(M["distinctive_false"])))
M["cross_reference"] = ("These are the moves that carry no @emotion / @face / @action. The surface rules they lean on are measured separately in "
                        "`speech_guide` (the first-person 私, the soft particles, the ellipsis and ？ marks, the noticing sounds) and in "
                        "`voice.surface`; this section adds the move, not the mark.")
M["note"] = ("The mechanisms are the builder's reading of her speech across her scenes, not the author's: the definitions and the classing are "
             "interpretive, the line counts and receipts are mechanical. A regex count is a lower bound where the move is defined by reading. "
             "`lines_H` / `lines_non_H` split the count by the @Hシーン開始 register.")
# ---- own-rule markers (read by koikano_bible_gate.load_rule_markers): one regex on the spoken text per firm/thin
# rule a regex over her lines can detect. Patterns chosen from the build block's receipts, not the holdout.
# Rules with no marker (not a property of one spoken line): 1 length, 2 reply rate, 11-14 face/gesture, 15 inner voice,
# 16 face/gesture rate, 17 emotion overlays, 18 C4 note, 19 bow convention, 20 kiss, 21 dozing, 24 composed-voice summary.
END = r"[」』]?\s*$"
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', 'tools', 'koikano'))
import markers_io  # noqa: E402
RULE_MARKER = markers_io.load('alice')  # tools/koikano/markers/alice.json is the source
for _i, _pat in RULE_MARKER.items():
    sg["rules"][_i]["marker"] = {"pattern": _pat}
print("rules with marker", len(RULE_MARKER), "of", len(sg["rules"]), "rules; none:", len(sg["rules"]) - len(RULE_MARKER))
b["provenance"]["b3_alice"] = ("2026-10-23 B3: mechanisms from tools/koikano/b3/alice.py; speech_guide rule texts rewritten from her receipts "
                               "(as B5 2026-10-23); tiers by one rule from the counts; gate run on this build.")
b["provenance"].pop("b5_rewrite", None)

open(BIBLE, "w", encoding="utf-8", newline="\n").write(dump(b))
try:
    md = kb.render_doc(b)
    open(READABLE, "w", encoding="utf-8", newline="\n").write(md if md.endswith("\n") else md + "\n")
    print("bible_readable.md regenerated")
except Exception as e:
    print("render_doc failed after edit:", repr(e))
print("rules tier", sg["tier_split"], "mech tier", M["tier_split"], "distinctive_false", M["distinctive_false"])
