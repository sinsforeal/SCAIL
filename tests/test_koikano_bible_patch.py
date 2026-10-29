"""tk-oas: the patched bible tool gives route, route character and self-reference per subject.

Runs the real builder on the kirikiri corpus (read-only), into a temp dir on F:.
Skipped when the corpus is not on this machine.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "tools", "koikano", "koikano_bible.py")
CORPUS = r"F:\REPS2\clipboard capture (kirikiri)\extracted_games\koikano"
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def build(char, out):
    r = subprocess.run(
        [sys.executable, "-I", TOOL, "--char", char, "--out", out, "--doc", os.path.join(out, "doc.md")],
        capture_output=True, text=True, encoding="utf-8", creationflags=CREATE_NO_WINDOW)
    if r.returncode != 0:
        raise AssertionError(r.stderr[-500:])
    return json.load(open(os.path.join(out, "bible.json"), encoding="utf-8"))


def self_rule(bible):
    return [r for r in bible["speech_guide"]["rules"] if r["rule"].startswith(("Name yourself", "Refer to yourself"))][0]


@unittest.skipUnless(os.path.isdir(CORPUS), "kirikiri corpus not present")
class BiblePatch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base = tempfile.mkdtemp(prefix="bible_patch_", dir="F:\\temp" if os.path.isdir("F:\\temp") else None)
        cls.hyakka = build("百花", os.path.join(base, "h"))
        cls.sena = build("千奈", os.path.join(base, "s"))
        cls.maria = build("真里亜", os.path.join(base, "m"))

    def test_route_per_subject(self):
        self.assertEqual((self.hyakka["identity"]["route"], self.hyakka["identity"]["route_character"]), ("d", "百花"))
        self.assertEqual((self.sena["identity"]["route"], self.sena["identity"]["route_character"]), ("b", "千奈"))
        self.assertEqual(self.sena["meta"]["route"], "b")
        self.assertEqual((self.maria["identity"]["route"], self.maria["identity"]["route_character"]), ("", ""))

    def test_self_reference_is_the_subjects_own(self):
        h = self_rule(self.hyakka)["rule"]
        self.assertTrue(h.startswith("Name yourself 百花 in the third person; do not use 私."), h)
        s = self_rule(self.sena)["rule"]
        self.assertNotIn("百花", s)
        self.assertIn("千奈" if "Name yourself" in s else "yourself as", s)

    def test_offers_self_matcher_skipped_for_others(self):
        keys = lambda b: {m["key"] for m in b["mechanisms"]["mechanisms"]}
        self.assertIn("offers_herself_as_the_actor", keys(self.hyakka))
        self.assertNotIn("offers_herself_as_the_actor", keys(self.sena))

    def test_no_hyakka_literal_in_other_subjects_computed_fields(self):
        kiss = [r for r in self.sena["speech_guide"]["rules"] if r["rule"].startswith("Keep kiss")][0]
        self.assertTrue(kiss["rule"].endswith("route b."), kiss["rule"])
        self.assertNotIn("route_d", kiss["receipt"])


if __name__ == "__main__":
    unittest.main()
