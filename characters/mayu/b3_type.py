# Writes the type (CM 3.6) into sheet.json. Derived 2026-10-23 from the surviving entries; read by no model call.
# usage: python b3_type.py sheet.json
import json
import sys

T = {
    "type": "ISFJ",
    "why": ("Derived last from the surviving entries (13 mechanisms, 25 speech-guide rules, her non-H spoken lines 2908 against 7930 for the other "
            "named speakers). Two axes (E/I, S/N) lean on measured contrasts that are small; T/F and J/P are close to even and the confidence says so. "
            "Near miss ISFP, with J/P the deciding axis, and INFJ on S/N."),
    "axes": {
        "EI": {"letter": "I", "confidence": 0.6,
               "line": "Keeps to one person and refuses the public side of her own work; replies far more than she opens.",
               "receipts": ["reply_rate 0.9931 (2444 reply, 17 open)", "sets_herself_beside_ichigo 63 lines vs 0 control",
                            "02_01:5422 refuses to appear", "02_01:5468 and 03_01:0034 no longer wants to perform", "03_01:0156 does not want to go to the club",
                            "01_01:0192 does not want to go out", "01_01:2546 wanted the club for two",
                            "withdraw words 0.0162 vs 0.0115 control"]},
        "SN": {"letter": "S", "confidence": 0.5,
               "line": "Talks about the day, food, the script in hand; the concrete outweighs the hypothetical, by a little.",
               "receipts": ["concrete-word share 0.0664 vs 0.0533 control (193 lines)", "possibility-word share 0.0402 vs 0.0364 (117 lines)",
                            "01_01:0579 weight of the shopping", "01_01:0192 reports this morning's dream"]},
        "TF": {"letter": "F", "confidence": 0.4,
               "line": "Argues from how it feels to her (もん 131 lines, 好き 100 lines), but presses points as obvious (でしょ 76 lines); close to even.",
               "receipts": ["justifies_with_mon 131 lines vs 1", "says_suki_outright 100 vs 82 control lines", "feeling-word share 0.0798 vs 0.0755 (no gap)",
                            "reason-word share 0.0915 vs 0.0566 (against)", "presses_with_desho 76 vs 15 (against)"]},
        "JP": {"letter": "J", "confidence": 0.35,
               "line": "Almost no evidence either way: plan words are at the control rate and open-ended words are rare in her and in the room.",
               "receipts": ["plan-word share 0.0241 vs 0.0243 control", "open-ended-word share 0.0017 vs 0.0026", "03_01:0530 絶対。約束ね"]},
    },
    "contradictions": [
        "Reason words (0.0915 vs 0.0566) and でしょ presses (76 vs 15) fight the F letter and are not bent to it.",
        "えへへ 169 lines and 'みんな' words at the control rate fight the I letter: she is not quiet, she is selective.",
        "Her stage refusals (02_01:5422) sit beside stage work she still does (a08_01:1302): the I letter holds for the public, not for the craft.",
    ],
    "note": "Nothing reads this field: not in bible.md, style.md or any prompt. Derived last, never a source of a rule.",
}

path = sys.argv[1]
s = json.load(open(path, encoding="utf-8"))
s.update(T)
with open(path, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(s, fh, ensure_ascii=False, indent=2)
    fh.write("\n")
print("ok", T["type"])
