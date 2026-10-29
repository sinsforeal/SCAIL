#!/usr/bin/env python3
"""B5 supplement for sena: counts the B2 layer cannot give (nicknames, work, the plain-form turns after 百花).

Reads the corpus read-only (character_conversations_focused/千奈.jsonl), writes the section
`b5_receipts` into bible.json beside it. Every number the prompts cite that is not already a
B2/B3 receipt comes from here. Run: python b5_receipts.py [--corpus DIR]
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT = r"F:\REPS2\clipboard capture (kirikiri)\extracted_games\koikano\koikano_work\character_conversations_focused"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=DEFAULT)
    a = ap.parse_args()
    rows = [json.loads(l) for l in open(Path(a.corpus) / "千奈.jsonl", encoding="utf8")]
    foc = [r for r in rows if r["is_focus"] and r["line_kind"] == "spoken"]

    def n_lines(pat):
        rx = re.compile(pat)
        return sum(1 for r in foc if rx.search(r["text"]))

    def first_ids(pat, k=3):
        rx = re.compile(pat)
        return [{"record_id": r["scene"] + ":" + format(r["source_line"], "04d"), "text": r["text"]} for r in foc if rx.search(r["text"])][:k]

    by_other = Counter()
    for r in rows:
        if not r["is_focus"] and r["line_kind"] == "spoken":
            for m in re.findall(r"ナタリー", r["text"]):
                by_other[r["speaker"]] += 1
    after_momoka = [r for r in foc if r["prev_speaker"] == "百花"]
    plain_after_momoka = [r for r in after_momoka if "です" not in r["text"] and "ます" not in r["text"]]
    momoka_scenes = sorted({r["scene"] for r in rows if r["speaker"] == "百花"})
    out = {
        "method": "b5_receipts.py over character_conversations_focused/千奈.jsonl; counts are spoken lines of 千奈 that contain the string, unless the key says occurrences",
        "address": {
            "lines_with_みゃー先輩": n_lines("みゃー先輩"),
            "lines_with_十川先輩": n_lines("十川先輩"),
            "lines_with_一悟先輩": n_lines("一悟先輩"),
            "lines_with_一悟先輩_by_route_b": sum(1 for r in foc if "一悟先輩" in r["text"] and r["scene"][0] == "b"),
            "occurrences_of_ナタリー_in_others_lines": dict(by_other),
            "lines_of_hers_naming_ナタリー": n_lines("ナタリー"),
            "lines_with_会長": n_lines("会長"),
            "lines_with_百花": n_lines("百花"),
            "lines_with_真里亜さん": n_lines("真里亜さん"),
            "nickname_origin": first_ids("宮国、一悟|みゃー先輩です|ナタリー」|『みゃー』", 4),
        },
        "work": {
            "lines_with_小説": n_lines("小説"),
            "lines_with_作家": n_lines("作家"),
            "lines_with_担当編集": n_lines("担当編集"),
            "lines_with_締め切り": n_lines("締め切り"),
            "lines_with_ペンネーム": n_lines("ペンネーム"),
            "lines_with_秘密_or_機密": n_lines("秘密|機密|ひみつ|ないしょ"),
            "secret_lines": first_ids("ペンネーム|機密事項", 4),
        },
        "with_百花": {
            "scenes_where_百花_speaks": len(momoka_scenes),
            "her_lines_right_after_a_百花_turn": len(after_momoka),
            "of_those_without_です_ます": len(plain_after_momoka),
            "plain_examples": [{"record_id": r["scene"] + ":" + format(r["source_line"], "04d"), "text": r["text"]} for r in plain_after_momoka if len(r["text"]) > 14][:4],
            "childhood_friend_line": first_ids("幼なじみが困っている", 1),
            "talks_of_百花_body": first_ids("百花は昔から身体が弱かった", 1),
        },
        "own_moves": {
            "lines_opening_with_a_single_kana_then_、": n_lines(r"^「[ぁ-んァ-ヶ]っ?、"),
            "lines_with_ハレンチ": n_lines("ハレンチ"),
            "lines_with_いやらしい": n_lines("いやらしい"),
            "lines_with_違います_or_違う": n_lines("違います|違うんです|違うん"),
            "lines_ending_か_or_か？": n_lines(r"か[？！]?」$"),
            "starter_examples": first_ids(r"^「[ぁ-んァ-ヶ]っ?、", 3),
        },
        "shares_of_spoken_3493": {
            k: round(v / len(foc), 4)
            for k, v in {
                "single_kana_then_、_opener": n_lines(r"^「[ぁ-んァ-ヶ]っ?、"),
                "ハレンチ": n_lines("ハレンチ"),
                "いやらしい": n_lines("いやらしい"),
                "違います_or_違う": n_lines("違います|違うんです|違うん"),
                "ends_か": n_lines(r"か[？！]?」$"),
                "みゃー先輩": n_lines("みゃー先輩"),
                "十川先輩": n_lines("十川先輩"),
                "小説": n_lines("小説"),
                "秘密_or_機密": n_lines("秘密|機密|ひみつ|ないしょ"),
            }.items()
        },
    }
    p = HERE / "bible.json"
    text = p.read_text(encoding="utf8")
    b = json.loads(text)
    rt = json.dumps(b, ensure_ascii=False, indent=2, sort_keys=True)
    if rt.strip() != text.strip():
        # a previous run may have added b5_receipts; compare without it
        b2 = {k: v for k, v in b.items() if k != "b5_receipts"}
        rt2 = json.dumps(b2, ensure_ascii=False, indent=2, sort_keys=True)
        print("format round-trip: exact" if rt2.strip() == text.strip() else "format round-trip differs (ok if b5 sections exist)")
    b["b5_receipts"] = out
    p.write_text(json.dumps(b, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf8")
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if not isinstance(vv, list)} for k, v in out.items() if isinstance(v, dict)}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    sys.exit(main())
