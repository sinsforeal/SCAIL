#!/usr/bin/env python3
"""Tier fix pass for sena (2026-10-23): one rule for every entry, from the counts.

Run after the build, the gate, b5_receipts.py and b5_rewrite_speech.py:
    python tier_pass.py

The rule (written into bible.json as tier_rule on both sections):
  n = the number of lines (or occurrences, for gesture and face-label rules) the statement rests on.
  weak : the statement has no support of its own: its receipt is 0 for a positive claim, or its rate
         is at or below the comparison (mechanisms: not above the room control rate).
  thin : measured but n < 30, or the evidence is inferred.
  firm : measured, n >= 30, and where a comparison exists the rate is above it.
  An absence statement ("she does not do X") takes n = lines examined and the exceptions as the
  count: firm when the exceptions are 1 percent or less of the lines examined and the lines
  examined are 100 or more.
Mechanisms take n = lines (hits on her spoken lines) and the room control rate from the same bible.
Speech-guide rules take n from RULE_BASIS below (the receipt key named, so the choice is checkable).
Class, evidence and confidence are not touched here.
"""
import json
from pathlib import Path

P = Path(__file__).resolve().parent / "bible.json"

# index -> (kind, how n is read)  kind: pos = positive claim, abs = absence claim, inf = inferred
# Each entry names the receipt path read, as a tuple of keys.
RULE_BASIS = {
    0: ("pos", ("spoken_lines_with_私",)),
    1: ("pos", ("non_H", "lines")),
    2: ("pos", ("reply",)),
    3: ("pos", ("lines_ending_っ",)),
    4: ("abs", ("lines_ending_ー",), ("by_register", "non_H", "n")),
    5: ("pos", ("token_んっ",)),
    6: ("abs", ("token_おおー",), ("spoken_total",)),
    7: ("abs", ("lines_matched",), ("by_register", "non_H", "n")),
    8: ("pos", ("lines_with_です_ます",)),
    9: ("pos", ("…_by_register", "non_H", "count")),
    10: ("pos", ("！_by_register", "non_H", "count")),
    11: ("pos", ("all_occurrences",)),
    12: ("pos", ("lines",)),
    13: ("pos", ("@否定_occurrences",)),
    14: ("pos", ("@ジャンプ_occurrences",)),
    15: ("pos", ("inner_lines",)),
    16: ("pos", ("non_H", "with_expression")),
    17: ("pos", ("lines_with_emotion",)),
    18: ("inf", None),
    19: ("pos", ("her_@おじぎ",)),
    20: ("pos", ("kiss_lines",)),
    21: ("abs", ("lines",), ("spoken_total",)),
    22: ("pos", ("lines_with_H_tokens",)),
    23: ("pos", ("laugh_lines",)),
    24: ("inf", None),
}

RULE_TEXT = (
    "n is the count the statement rests on. weak: no support of its own (0 for a positive claim, or at or below the comparison). "
    "thin: measured with n under 30, or inferred. firm: measured, n 30 or more, above the comparison where one exists. "
    "An absence statement takes the lines examined as n and the exceptions as the count: firm when exceptions are 1 percent or "
    "less of 100 or more lines examined. Same rule for every row of speech_guide and mechanisms."
)


def dig(d, path):
    for k in path:
        d = d[k]
    return d


def tier_of(kind, n, exc_den, evidence):
    if kind == "inf" or evidence == "inferred":
        return "thin"
    if kind == "pos":
        if n == 0:
            return "weak"
        return "firm" if n >= 30 else "thin"
    # absence
    if exc_den is None or exc_den < 100:
        return "thin"
    return "firm" if n / exc_den <= 0.01 else "thin"


# Own-rule markers (read by load_rule_markers in koikano_bible_gate.py): index -> regex on the line text.
# Only rules a regex over one line can detect. The rest carry no marker (face and gesture tags, reply vs
# opening, turn length, inner voice, the composite voice rule, the inferred ones).
# 22 uses her own H words (精液 勃起 中出 れろ 乳首 挿入), picked from voice.distinctive, not 百花's list.
END = r"(?=[…・。！？\s」]*$)"
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', 'tools', 'koikano'))
import markers_io  # noqa: E402
MARKERS = markers_io.load('sena')  # tools/koikano/markers/sena.json is the source
H_RULE_22 = (
    "Keep H-scene vocabulary mostly inside the 7 H scenes. Her own H words (精液, 勃起, 中出, れろ, 乳首, 挿入, from voice.distinctive) "
    "match 120 of her 3493 spoken lines: 82 in H scenes, 38 outside. Outside H they are talk about it, not the act; do not open on them."
)


def apply_markers(b):
    rules = b["speech_guide"]["rules"]
    for i, r in enumerate(rules):
        r.pop("marker", None)
        if i in MARKERS:
            r["marker"] = {"pattern": MARKERS[i]}
    r22 = rules[22]
    if r22["rule"].startswith("Keep H-scene vocabulary"):
        r22["rule"] = H_RULE_22
        r22["receipt"] = {"h_scenes": 7, "in_H_scenes": 82, "in_non_H": 38, "lines_with_H_tokens": 120}
    return len(MARKERS), [i for i in range(len(rules)) if i not in MARKERS]


def main():
    b = json.loads(P.read_text(encoding="utf8"))
    nm, nomark = apply_markers(b)
    print("markers", nm, "no marker", nomark)
    spoken_total = b["mechanisms"]["spoken_lines"]
    log = []
    for i, r in enumerate(b["speech_guide"]["rules"]):
        basis = RULE_BASIS[i]
        kind = basis[0]
        n, den = None, None
        if kind != "inf":
            n = dig(r["receipt"], basis[1])
            if kind == "abs":
                den = spoken_total  # lines examined: her whole spoken record
        old = r["tier"]
        r["tier"] = tier_of(kind, n, den, r["evidence"])
        r["tier_basis"] = {"kind": kind, "n": n, "examined": den}
        log.append((i, old, r["tier"], kind, n, den))
    sg = b["speech_guide"]
    sg["tier_split"] = {k: sum(1 for r in sg["rules"] if r["tier"] == k) for k in ("firm", "thin", "weak") if any(r["tier"] == k for r in sg["rules"])}
    sg["tier_rule"] = RULE_TEXT
    m = b["mechanisms"]
    for row in m["mechanisms"]:
        old = row["tier"]
        if row["lines"] == 0 or row["share_of_spoken"] <= row["control_rate"]:
            row["tier"] = "weak"
        else:
            row["tier"] = "firm" if row["lines"] >= 30 else "thin"
        row["tier_basis"] = {"n": row["lines"], "rate": row["share_of_spoken"], "control_rate": row["control_rate"]}
        log.append((row["key"], old, row["tier"], "mech", row["lines"], row["control_rate"]))
    for k in ("firm", "thin", "weak"):
        m[k + "_count"] = sum(1 for r in m["mechanisms"] if r["tier"] == k)
    m["tier_split"] = {k: sum(1 for r in m["mechanisms"] if r["tier"] == k) for k in ("firm", "thin", "weak") if any(r["tier"] == k for r in m["mechanisms"])}
    m["tier_rule"] = RULE_TEXT
    P.write_text(json.dumps(b, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf8")
    for x in log:
        print(x)
    print("speech_guide", sg["tier_split"], "mechanisms", m["tier_split"])


if __name__ == "__main__":
    main()
