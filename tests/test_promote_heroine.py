"""tools/koikano/promote_heroine.py on a tiny synthetic subject in a temp dir.

    cd H:\\SCAIL\\temp\\maria_full ; set PYTHONPATH=<worktree> ; python -m unittest tests.test_promote_heroine -v
"""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from tools.koikano import promote_heroine as ph  # noqa: E402


def put(path, tree):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8") as f:
        json.dump(tree, f, ensure_ascii=False)


class PromoteTest(unittest.TestCase):
    def setUp(self):
        tmp = os.environ.get("TEMP") or None
        self.d = tempfile.mkdtemp(prefix="promote_test_", dir=tmp)
        self.root = os.path.join(self.d, "chars")
        self.src = os.path.join(self.d, "src")
        self._src = ph.SRC
        ph.SRC = self.src
        ph.SLUG_DIRS["subj"] = "SUBJ_x"
        put(os.path.join(self.root, "momoka", "bundle.json"), {
            "_note": "m", "blank": {"x": 1},
            "config_overrides": {
                "models": {"main": {"prompt": "prompts_momoka/bible.md"}, "aux": {}},
                "character": {"name": "Momoka"},
                "vn": {"enabled": True, "port": 8770},
                "quality": {"caps": {"phrases": {"a": 1}}},
                "logging": {"db_path": "data/momoka.db"}}})
        put(os.path.join(self.root, "momoka", "fills.json"), {
            "_note": "n", "id": "momoka", "NAME": "x", "WHO": "x", "CITY": "x", "AGE_WORD": "x", "_age_note": "x"})
        put(os.path.join(self.root, "subj", "sheet.json"), {
            "name": {"full": "Test Hana", "japanese": "花子", "given": "花", "kana": "はな"},
            "existence": {"in_world": False, "_why": "x"}})
        sd = os.path.join(self.src, "subj")
        put(os.path.join(sd, "fills_src.json"), {"tokens": {
            "CITY": {"value": "a town", "receipt": "01_01:0001"},
            "AGE_WORD": {"value": "the record is silent"}}})
        put(os.path.join(sd, "cast_src.json"), {"people": {"him": {
            "role_id": "him", "name": "him", "role": "r", "note": "n", "aliases": ["h"]}}})
        put(os.path.join(sd, "world_src.json"), {"place_ids": ["her_room", "maid_room"]})
        put(os.path.join(sd, "bundle_src.json"), {"caps": {"phrases": {"z": 2}, "doubled_group": 2}})

    def tearDown(self):
        ph.SRC = self._src
        ph.SLUG_DIRS.pop("subj", None)
        shutil.rmtree(self.d, ignore_errors=True)

    def run_main(self, *extra):
        argv = sys.argv
        sys.argv = ["promote_heroine", "subj", "--root", self.root] + list(extra)
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                rc = ph.main()
        finally:
            sys.argv = argv
        return rc, out.getvalue()

    def test_want_has_every_token_and_no_notes(self):
        self.assertEqual(ph.momoka_tokens(self.root), ["NAME", "WHO", "CITY", "AGE_WORD"])

    def test_writes_four_files_with_counts(self):
        rc, out = self.run_main()
        self.assertEqual(rc, 0)
        self.assertIn("4 tokens, 1 from record, 1 record is silent, 0 missing", out)
        b = os.path.join(self.root, "subj")
        for f in ("bundle.json", "fills.json", "cast.json", os.path.join("world", "subj_house.json")):
            self.assertTrue(os.path.exists(os.path.join(b, f)), f)
        fills = json.load(io.open(os.path.join(b, "fills.json"), encoding="utf-8"))
        self.assertEqual(fills["NAME"], "花")
        self.assertEqual(fills["WHO"], "花子")
        self.assertEqual(fills["CITY"], "a town")
        self.assertEqual(fills["_receipts"]["AGE_WORD"], "record is silent")

    def test_bundle_shape(self):
        self.run_main()
        b = json.load(io.open(os.path.join(self.root, "subj", "bundle.json"), encoding="utf-8"))
        ov = b["config_overrides"]
        self.assertFalse(b["registered"])
        self.assertEqual(b["db"], "data/subj.db")
        self.assertEqual(ov["models"]["main"]["prompt"], "prompts_subj/bible.md")
        self.assertEqual(ov["quality"]["caps"]["phrases"], {"z": 2})
        self.assertFalse(ov["vn"]["enabled"])
        self.assertFalse(ov["tts"]["enabled"])
        self.assertNotIn("_note", ov["tts"])
        self.assertEqual(ov["logging"]["db_path"], "data/subj.db")

    def test_missing_token_refuses_and_writes_nothing(self):
        put(os.path.join(self.src, "subj", "fills_src.json"), {"tokens": {}})
        rc, out = self.run_main("--check")
        self.assertEqual(rc, 1)
        self.assertIn("missing: CITY, AGE_WORD", out)
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stdout(io.StringIO()):
                sys.argv, keep = ["p", "subj", "--root", self.root], sys.argv
                try:
                    ph.main()
                finally:
                    sys.argv = keep
        self.assertFalse(os.path.exists(os.path.join(self.root, "subj", "bundle.json")))

    def test_place_ids_must_be_the_shared_house(self):
        put(os.path.join(self.src, "subj", "world_src.json"), {"place_ids": ["kitchen"]})
        with self.assertRaises(SystemExit):
            self.run_main()

    def test_world_uses_shared_ids(self):
        self.run_main()
        w = json.load(io.open(os.path.join(self.root, "subj", "world", "subj_house.json"), encoding="utf-8"))
        self.assertEqual(sorted(w["places"]), ["her_room", "maid_room"])
        self.assertEqual(w["house_id"], "chiyoda")

    def test_own_places_keep_her_ids_and_default_house_id(self):
        put(os.path.join(self.src, "subj", "world_src.json"), {
            "own_places": {"her_home": "her house", "school": "the school"}, "visit_place_ids": ["house"]})
        self.run_main()
        w = json.load(io.open(os.path.join(self.root, "subj", "world", "subj_house.json"), encoding="utf-8"))
        self.assertEqual(sorted(w["places"]), ["her_home", "school"])
        self.assertEqual(w["shared_places"], {"house": ph.HOUSE_IDS["house"]})
        self.assertEqual(w["house_id"], "subj_home")

    def test_visit_ids_must_be_the_shared_house(self):
        put(os.path.join(self.src, "subj", "world_src.json"), {
            "own_places": {"her_home": "x"}, "visit_place_ids": ["her_home"]})
        with self.assertRaises(SystemExit):
            self.run_main()

    def test_own_places_for_a_visitor(self):
        """A heroine with a home of her own: shared id 'house' as a visitor, her rooms in own_places, her own house_id."""
        put(os.path.join(self.src, "subj", "world_src.json"), {
            "house_id": "subj_home", "place_ids": ["house"],
            "own_places": {"her_home": "her house", "school": "the school"}})
        self.run_main()
        w = json.load(io.open(os.path.join(self.root, "subj", "world", "subj_house.json"), encoding="utf-8"))
        self.assertEqual(w["house_id"], "subj_home")
        self.assertEqual(w["places"], {"house": "the main part of the house", "her_home": "her house",
                                       "school": "the school"})

    def test_own_places_may_not_reuse_a_shared_id(self):
        put(os.path.join(self.src, "subj", "world_src.json"), {"place_ids": [], "own_places": {"house": "mine"}})
        with self.assertRaises(SystemExit):
            self.run_main()

    def test_own_places_may_not_reuse_a_shared_id_in_the_visit_form(self):
        put(os.path.join(self.src, "subj", "world_src.json"), {
            "own_places": {"house": "mine"}, "visit_place_ids": ["house"]})
        with self.assertRaises(SystemExit):
            self.run_main()

    def test_both_visit_keys_at_once_is_refused(self):
        put(os.path.join(self.src, "subj", "world_src.json"), {
            "own_places": {"her_home": "x"}, "place_ids": ["house"], "visit_place_ids": ["house"]})
        with self.assertRaises(SystemExit):
            self.run_main()

    def _bundle_name(self):
        self.run_main()
        b = json.load(io.open(os.path.join(self.root, "subj", "bundle.json"), encoding="utf-8"))
        return b["config_overrides"]["character"]["name"]

    def test_name_is_last_word_of_full_by_default(self):
        self.assertEqual(self._bundle_name(), "Hana")

    def test_name_en_wins_over_three_part_full_name(self):
        sheet = os.path.join(self.root, "subj", "sheet.json")
        s = json.load(io.open(sheet, encoding="utf-8"))
        s["name"]["full"] = "Test Third Hana"
        put(sheet, s)
        self.assertEqual(self._bundle_name(), "Hana")
        s["name"]["full"] = "Alice Third Macy"
        put(sheet, s)
        put(os.path.join(self.src, "subj", "bundle_src.json"),
            {"caps": {"phrases": {"z": 2}, "doubled_group": 2}, "name_en": "Alice"})
        self.assertEqual(self._bundle_name(), "Alice")

    def test_visitor_places_need_labels_and_empty_week_places(self):
        wp = os.path.join(self.src, "subj", "world_src.json")
        put(wp, {"place_ids": ["her_home"], "places": {"her_home": "a room"},
                 "week": [{"slot": "morning", "place": ""}]})
        self.run_main()
        w = json.load(io.open(os.path.join(self.root, "subj", "world", "subj_house.json"), encoding="utf-8"))
        self.assertEqual(w["house_id"], "subj_home")
        put(wp, {"place_ids": ["her_home", "x"], "places": {"her_home": "a room"}})
        with self.assertRaises(SystemExit):
            self.run_main()
        put(wp, {"place_ids": ["her_home"], "places": {"her_home": "a room"},
                 "week": [{"slot": "morning", "place": "house"}]})
        with self.assertRaises(SystemExit):
            self.run_main()


class SenaSourcesTest(unittest.TestCase):
    """The real heroine_src/sena/ against the real tree: nothing is written (--check)."""

    def test_sena_has_every_token_and_a_receipt_or_silence(self):
        chars = os.path.join(HERE, "characters")
        want = ph.momoka_tokens(chars)
        src = ph.load(os.path.join(ph.SRC, "sena", "fills_src.json"))["tokens"]
        sheet = ph.load(os.path.join(chars, "sena", "sheet.json"))
        fills, miss, rec, sil = ph.build_fills("sena", sheet, {"tokens": src}, chars, want)
        self.assertEqual(miss, [])
        self.assertEqual(rec + sil + len(ph.MECH), len(want))
        self.assertEqual(fills["NAME"], "千奈")
        self.assertEqual(fills["FULLNAME"], "七瀬千奈")

    def test_sena_existence_is_tier_two_and_player_driven(self):
        ex = ph.load(os.path.join(HERE, "characters", "sena", "sheet.json"))["existence"]
        self.assertFalse(ex["in_world"])
        self.assertTrue(ex["player_driven"])

    def test_sena_emits_no_secret_or_grade(self):
        text = ""
        for f in ("fills_src", "cast_src", "world_src", "bundle_src"):
            with io.open(os.path.join(ph.SRC, "sena", f + ".json"), encoding="utf-8") as fh:
                text += fh.read()
        for banned in ("夏天すとら", "一年生", "一年の", "三年", "お父さん", "お母さん", "父", "母"):
            self.assertNotIn(banned, text, banned)

    def test_sena_world_uses_her_own_ids_and_house_ids_for_the_visit(self):
        w = ph.build_world("sena", {}, ph.load(os.path.join(ph.SRC, "sena", "world_src.json")), "")
        self.assertEqual(sorted(w["places"]), ["her_home", "school", "town"])
        self.assertEqual(list(w["shared_places"]), ["house"])
        for row in w["week"]:
            self.assertEqual(row["place"], "")
            self.assertIn(row["own_place"], w["places"])


SRC_REAL = os.path.join(HERE, "tools", "koikano", "heroine_src")
# what must never be in an emitted value (ruling 10-23 13:29): a school year, an age
FORBIDDEN = ("一年生", "二年生", "三年生", "歳", "grade 1", "grade 2", "grade 3", "years old", "-year-old")


class RealSourcesTest(unittest.TestCase):
    """The hand-read sources of every heroine that has them: no token missing, receipts well-formed,
    nothing a ruling keeps out."""

    def keys(self):
        return sorted(k for k in os.listdir(SRC_REAL) if os.path.isdir(os.path.join(SRC_REAL, k)))

    def read(self, key, name):
        with io.open(os.path.join(SRC_REAL, key, name), encoding="utf-8") as f:
            return json.load(f)

    def test_every_heroine_covers_momoka_tokens(self):
        want = ph.momoka_tokens(os.path.join(HERE, "characters"))
        for key in self.keys():
            have = self.read(key, "fills_src.json")["tokens"]
            sheet = ph.load(os.path.join(HERE, "characters", key, "sheet.json"))
            _, miss, _, _ = ph.build_fills(key, sheet, {"tokens": have}, None, want)
            self.assertEqual(miss, [], key)

    def test_receipts_are_scene_line_or_named(self):
        import re
        rx = re.compile(r"^[0-9a-z]{2,3}_\d{2}:\d{4}$")
        for key in self.keys():
            for t, v in self.read(key, "fills_src.json")["tokens"].items():
                for r in (v.get("receipt") or "").split():
                    if rx.match(r):
                        continue
                    # a named section or a count is allowed only when it is more than one bare word
                    self.assertTrue(len(v["receipt"].split()) > 1 or r.endswith(".md"), (key, t, r))

    def test_nothing_a_ruling_keeps_out(self):
        for key in self.keys():
            for name in ("fills_src.json", "cast_src.json", "world_src.json"):
                blob = json.dumps(self.read(key, name), ensure_ascii=False)
                for bad in FORBIDDEN:
                    self.assertNotIn(bad, blob, (key, name, bad))

    def test_world_places_are_shared_ids_or_own(self):
        for key in self.keys():
            w = self.read(key, "world_src.json")
            own = set(w.get("own_places") or {})
            self.assertFalse(own & set(ph.HOUSE_IDS), key)
            ok = set(ph.HOUSE_IDS) | {""}
            # her own place is `at` (mayu) or `own_place` (sena); a shared-house heroine (maria) has neither
            for row in w.get("week", []):
                self.assertIn(row["place"], ok, (key, row["slot"]))
                at = row.get("at") or row.get("own_place")
                if at:
                    self.assertIn(at, own, (key, row["slot"]))
            for name, block in w.get("house", {}).items():
                self.assertIn(block.get("place", ""), ok, (key, name))
                at = block.get("at") or block.get("own_place")
                if at:
                    self.assertIn(at, own, (key, name))

    def test_cast_rows_are_her_lines_with_no_numbers(self):
        for key in self.keys():
            c = self.read(key, "cast_src.json")
            for pk, p in c["people"].items():
                for opt in ("numbers", "closeness", "standing", "tension"):
                    self.assertNotIn(opt, p, (key, pk))
                self.assertTrue(p["aliases"], (key, pk))


class AliceFilesTest(unittest.TestCase):
    """The promoted files of アリス in characters/alice (skipped when absent)."""
    D = os.path.join(HERE, "characters", "alice")

    def load(self, *p):
        path = os.path.join(self.D, *p)
        if not os.path.exists(path):
            self.skipTest("no " + path)
        return json.load(io.open(path, encoding="utf-8"))

    def test_fills_complete_and_free_of_grade_and_type(self):
        fills = self.load("fills.json")
        vals = {k: v for k, v in fills.items() if not k.startswith("_") and k != "id"}
        self.assertEqual(len(vals), 48)
        text = json.dumps(vals, ensure_ascii=False)
        for bad in ("ENFJ", "年生", "歳"):
            self.assertNotIn(bad, text)

    def test_bundle_name_and_off_switches(self):
        ov = self.load("bundle.json")["config_overrides"]
        self.assertEqual(ov["character"]["name"], "Alice")
        self.assertFalse(ov["vn"]["enabled"])
        self.assertFalse(ov["tts"]["enabled"])

    def test_cast_has_no_number_keys(self):
        cast = self.load("cast.json")
        for pid, row in cast["people"].items():
            for k in ("closeness", "standing", "tension"):
                self.assertNotIn(k, row, pid)

    def test_house_uses_shared_ids_and_week_is_housemate(self):
        w = self.load("world", "alice_house.json")
        self.assertEqual(w["house_id"], "chiyoda")
        self.assertEqual(w["place_ids"], ["house"])
        self.assertNotIn("her_home", json.dumps(w, ensure_ascii=False))
        for row in w["week"]:
            self.assertIn(row["place"], ("", "house", "her_room", "maid_room"), row["slot"])


CHISA_LINES = (r"F:\REPS2\clipboard capture (kirikiri)\extracted_games\koikano\koikano_work"
               r"\character_lines\知紗.jsonl")


class ChisaSourcesTest(unittest.TestCase):
    """The real heroine_src/chisa/ against the real tree: nothing is written."""

    def _text(self):
        text = ""
        for f in ("fills_src", "cast_src", "world_src", "bundle_src"):
            with io.open(os.path.join(ph.SRC, "chisa", f + ".json"), encoding="utf-8") as fh:
                text += fh.read()
        return text

    def test_chisa_has_every_token_and_a_receipt_or_silence(self):
        chars = os.path.join(HERE, "characters")
        want = ph.momoka_tokens(chars)
        src = ph.load(os.path.join(ph.SRC, "chisa", "fills_src.json"))["tokens"]
        sheet = ph.load(os.path.join(chars, "chisa", "sheet.json"))
        fills, miss, rec, sil = ph.build_fills("chisa", sheet, {"tokens": src}, chars, want)
        self.assertEqual(miss, [])
        self.assertEqual(rec + sil + len(ph.MECH), len(want))
        self.assertEqual(fills["NAME"], "知紗")

    def test_chisa_existence_is_tier_two_and_player_driven(self):
        ex = ph.load(os.path.join(HERE, "characters", "chisa", "sheet.json"))["existence"]
        self.assertFalse(ex["in_world"])
        self.assertTrue(ex["player_driven"])

    def test_chisa_voice_prefix_is_chs_and_letter_cf(self):
        self.assertEqual(ph.VOICE_PREFIX["chisa"], "CHS")
        self.assertEqual(ph.LETTER["chisa"], "CF")
        self.assertEqual(ph.load(os.path.join(ph.SRC, "chisa", "bundle_src.json"))["voice_prefix"], "CHS")

    def test_chisa_sources_carry_no_grade_parent_or_h_words(self):
        text = self._text()
        for banned in ("一年生", "二年", "三年", "お父さん", "お母さん", "セックス", "精液", "射精", "ペニス", "中出し", "膣"):
            self.assertNotIn(banned, text, banned)

    def test_chisa_every_receipt_is_one_of_her_lines(self):
        if not os.path.exists(CHISA_LINES):
            self.skipTest("corpus not on this machine")
        import re
        ids = set()
        with io.open(CHISA_LINES, encoding="utf-8") as fh:
            for line in fh:
                r = json.loads(line)
                ids.add("%s:%04d" % (r["scene"], r["source_line"]))
        cited = set(re.findall(r"[0-9a-z]+_\d\d:\d{4}", self._text()))
        self.assertTrue(cited)
        self.assertEqual(sorted(cited - ids), [])

    def test_chisa_world_uses_her_own_ids_and_house_ids_for_the_visits(self):
        w = ph.build_world("chisa", {}, ph.load(os.path.join(ph.SRC, "chisa", "world_src.json")), "")
        self.assertEqual(sorted(w["places"]), ["her_home", "road", "school"])
        self.assertEqual(list(w["shared_places"]), ["house"])
        for row in w["week"]:
            self.assertEqual(row["place"], "")
            self.assertIn(row["own_place"], w["places"])
        self.assertEqual([r["place"] for r in w["visit"]], ["house", "house"])

    def test_chisa_prompts_mark_every_liberty(self):
        with io.open(os.path.join(HERE, "characters", "chisa", "prompts", "bible.md"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertGreaterEqual(text.count("liberty:"), 5)
        self.assertIn("08_02:3606", text)


if __name__ == "__main__":
    unittest.main()
