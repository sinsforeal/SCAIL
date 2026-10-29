"""tools/check_world_spec.py: the real spec passes, and each class of defect is caught.

Defect cases run against a tiny fake record, so they do not need the corpus.
"""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools", "koikano"))

import check_world_spec as cws  # noqa: E402
from sim.scene import PLACE_BACKGROUNDS  # noqa: E402


def stage_row(scene, line, speaker, text, bg):
    return {"scene": scene, "source_line": line, "speaker": speaker, "text": text,
            "stage": {"bg": {"id": bg}}}


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        rows = [stage_row("01_01", 10, "百花", "「演劇部は百花が作った」", "BG02a01"),
                stage_row("01_01", 20, "真優", "「週末は家にいる」", "BG18a01")]
        with open(os.path.join(self.dir, "stage_state.jsonl"), "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    def tearDown(self):
        self.tmp.cleanup()

    def run_spec(self, spec):
        path = os.path.join(self.dir, "spec.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(spec, f, ensure_ascii=False)
        return cws.run(record_dir=self.dir, spec=path, cards=[])

    def good(self):
        return {"places": [], "anchors": [], "rows": {},
                "club": {"facts": [{"text": "She founded the club.",
                                    "receipts": [{"id": "01_01:0010", "anchor": "演劇部は百花が作った", "bg": "BG02"}]}]}}

    def test_good_passes(self):
        errors, s = self.run_spec(self.good())
        self.assertEqual(errors, [])
        self.assertEqual(s["facts"], 1)
        self.assertEqual(s["receipts"], 1)

    def test_fact_without_receipt(self):
        spec = self.good()
        spec["club"]["facts"].append({"text": "No receipt here.", "receipts": []})
        errors, _ = self.run_spec(spec)
        self.assertTrue(any("without a receipt" in e for e in errors), errors)

    def test_parameter_needs_basis(self):
        spec = self.good()
        spec["club"]["facts"].append({"text": "A number.", "kind": "parameter", "receipts": []})
        errors, _ = self.run_spec(spec)
        self.assertTrue(any("without a basis" in e for e in errors), errors)
        spec["club"]["facts"][-1]["basis"] = "tuning"
        errors, _ = self.run_spec(spec)
        self.assertEqual(errors, [])

    def test_receipt_not_in_record(self):
        spec = self.good()
        spec["club"]["facts"][0]["receipts"][0]["id"] = "01_01:0099"
        errors, _ = self.run_spec(spec)
        self.assertTrue(any("not in the record" in e for e in errors), errors)

    def test_anchor_not_in_line(self):
        spec = self.good()
        spec["club"]["facts"][0]["receipts"][0]["anchor"] = "文芸部"
        errors, _ = self.run_spec(spec)
        self.assertTrue(any("anchor" in e for e in errors), errors)

    def test_wrong_bg(self):
        spec = self.good()
        spec["club"]["facts"][0]["receipts"][0]["bg"] = "BG18"
        errors, _ = self.run_spec(spec)
        self.assertTrue(any("has bg" in e for e in errors), errors)

    def test_bad_id_format(self):
        spec = self.good()
        spec["club"]["facts"][0]["receipts"][0]["id"] = "01_01-10"
        errors, _ = self.run_spec(spec)
        self.assertTrue(any("bad receipt id" in e for e in errors), errors)

    def test_grade_and_age_words(self):
        for word in ("一年生の部長", "17歳の部長", "三年生"):
            spec = self.good()
            spec["club"]["facts"][0]["text"] = word
            errors, _ = self.run_spec(spec)
            self.assertTrue(any("age or grade" in e for e in errors), (word, errors))

    def test_age_word_in_anchor(self):
        spec = self.good()
        spec["club"]["facts"][0]["receipts"][0]["anchor"] = "一年生"
        errors, _ = self.run_spec(spec)
        self.assertTrue(any("anchor carries" in e for e in errors), errors)

    def test_note_may_name_the_ban(self):
        spec = self.good()
        spec["_note"] = "No age, grade or birthplace; 年生 is never emitted."
        spec["rules"] = {"age_grade": "No age and no grade."}
        errors, _ = self.run_spec(spec)
        self.assertEqual(errors, [])

    def test_birthplace(self):
        spec = self.good()
        spec["club"]["facts"][0]["text"] = "She is from a small town (出身は地方)."
        errors, _ = self.run_spec(spec)
        self.assertTrue(any("birthplace" in e for e in errors), errors)

    def test_named_parent(self):
        spec = self.good()
        spec["club"]["facts"][0]["text"] = "千代田さんの父 is kind."
        errors, _ = self.run_spec(spec)
        self.assertTrue(any("named parent" in e for e in errors), errors)

    def test_parent_word_outside_parent_fact(self):
        spec = self.good()
        spec["club"]["facts"][0]["text"] = "Her father decides."
        spec["club"]["facts"][0]["text"] = "母が決める"
        errors, _ = self.run_spec(spec)
        self.assertTrue(any("parent word outside" in e for e in errors), errors)

    def test_parent_fact_must_say_unnamed(self):
        spec = self.good()
        spec["club"]["facts"][0].update({"kind": "parent", "text": "パパとママは背景"})
        errors, _ = self.run_spec(spec)
        self.assertTrue(any("named false" in e for e in errors), errors)
        spec["club"]["facts"][0]["named"] = False
        errors, _ = self.run_spec(spec)
        self.assertEqual(errors, [])

    def test_unknown_place_id(self):
        spec = self.good()
        spec["rows"] = {"x": {"week": [{"text": "t", "place": "moon_base",
                                        "receipts": [{"id": "01_01:0010", "anchor": "演劇部"}]}]}}
        errors, _ = self.run_spec(spec)
        self.assertTrue(any("unknown place id" in e for e in errors), errors)

    def test_place_bg_mismatch(self):
        spec = self.good()
        spec["places"] = [{"id": "club_room", "place": "club_room", "bg": "BG99a01"}]
        errors, _ = self.run_spec(spec)
        self.assertTrue(any("scene.py says" in e for e in errors), errors)

    def test_absent_pattern(self):
        spec = self.good()
        spec["club"]["facts"][0]["receipts"] = [{"id": "01_01:0010", "absent": "演劇"}]
        errors, _ = self.run_spec(spec)
        self.assertTrue(any("absent pattern" in e for e in errors), errors)

    def test_receipt_with_no_test(self):
        spec = self.good()
        spec["club"]["facts"][0]["receipts"] = [{"id": "01_01:0010"}]
        errors, _ = self.run_spec(spec)
        self.assertTrue(any("no anchor" in e for e in errors), errors)


class RealSpec(unittest.TestCase):
    def test_real_spec_and_cards(self):
        errors, s = cws.run()
        self.assertEqual(errors, [])
        self.assertEqual(s["places"], len(PLACE_BACKGROUNDS))
        self.assertGreaterEqual(s["cards"], 2)
        self.assertGreaterEqual(s["anchors"], 6)
        self.assertGreaterEqual(s["rows"], 6)
        self.assertGreater(s["facts"], 0)

    def test_places_cover_every_scene_py_id(self):
        spec = json.load(open(cws.SPEC, encoding="utf-8"))
        self.assertEqual({p["id"] for p in spec["places"]}, set(PLACE_BACKGROUNDS))
        for p in spec["places"]:
            self.assertEqual(p["bg"], PLACE_BACKGROUNDS[p["id"]])

    def test_rows_are_the_six_cast(self):
        spec = json.load(open(cws.SPEC, encoding="utf-8"))
        self.assertEqual(set(spec["rows"]), {"mayu", "sena", "alice", "maria", "chisa", "hikaru"})
        self.assertIn("sick_days", spec["momoka"])
        self.assertEqual(spec["momoka"]["sick_days"]["draw"]["kind"], "parameter")

    def test_cards_have_speech_receipts_and_no_age(self):
        for slug in ("chisa", "hikaru"):
            card = json.load(open(os.path.join(ROOT, "characters", slug, "card.json"), encoding="utf-8"))
            self.assertTrue(3 <= len(card["speech"]) <= 5, slug)
            self.assertTrue(card["address"]["others_call_her_or_him"], slug)
            self.assertTrue(card["holes"], slug)


if __name__ == "__main__":
    unittest.main()
