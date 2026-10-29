"""Gender field of the light cast cards (tools/koikano/build_cast_cards.py)."""
import json
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools", "koikano"))
import build_cast_cards as bcc  # noqa: E402

PRONOUN_WORDS = re.compile(r"\b(her|hers|she|him|his|he)\b")


def strings(node, path=""):
    if isinstance(node, dict):
        for k, v in node.items():
            if k in ("receipts", "receipt", "pattern"):
                continue
            yield from strings(v, path + "/" + k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from strings(v, path + "/%d" % i)
    elif isinstance(node, str):
        yield path, node


class GenderField(unittest.TestCase):
    def test_every_subject_has_a_known_gender_and_basis(self):
        for slug, spec in bcc.SUBJECTS.items():
            self.assertIn(spec["gender"], bcc.PRON, slug)
            self.assertTrue(spec["gender_basis"], slug)

    def test_hikaru_is_he_him(self):
        self.assertEqual(bcc.SUBJECTS["hikaru"]["gender"], "he")
        self.assertEqual(bcc.PRON["he"]["obj"], "him")
        self.assertEqual(bcc.PRON["he"]["poss"], "his")

    def test_built_cards_use_their_own_pronouns(self):
        for slug, spec in bcc.SUBJECTS.items():
            card = json.load(open(os.path.join(ROOT, "characters", slug, "card.json"), encoding="utf-8"))
            g = card["identity"]["gender"]
            self.assertEqual(g["pronouns"], bcc.PRON[spec["gender"]]["label"])
            self.assertTrue(g["receipts"])
            wrong = ("she", "her") if spec["gender"] == "he" else ("he", "him", "his")
            for path, s in strings(card):
                if path.startswith("/identity/gender") or path.startswith("/_note"):
                    continue
                words = set(PRONOUN_WORDS.findall(s))
                if "Momoka's lines name" in s:
                    words.discard("her")
                self.assertFalse(words & set(wrong), "%s %s: %s" % (slug, path, s))

    def test_hikaru_manner_has_computed_and_hand_items_with_receipts(self):
        card = json.load(open(os.path.join(ROOT, "characters", "hikaru", "card.json"), encoding="utf-8"))
        manner = card["manner"]
        self.assertTrue(any(m.get("kind") == "computed" for m in manner))
        self.assertTrue(any("fact" in m for m in manner))
        for m in manner:
            self.assertTrue(m.get("receipts") or m.get("receipt"), m)


if __name__ == "__main__":
    unittest.main()
