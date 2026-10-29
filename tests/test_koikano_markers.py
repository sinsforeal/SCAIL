"""Own-rule marker hook: one json per subject, read by the apply scripts, run_leak_free and the gate.

No corpus needed.
"""
import json
import os
import re
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KDIR = os.path.join(ROOT, "tools", "koikano")
sys.path.insert(0, KDIR)
import markers_io  # noqa: E402
import koikano_bible as kb  # noqa: E402
import koikano_bible_gate as g  # noqa: E402

OWN = ["mayu", "sena", "alice", "maria"]


class MarkerFiles(unittest.TestCase):
    def test_four_subjects_have_compilable_markers_and_hyakka_none(self):
        self.assertEqual(markers_io.load("hyakka"), {})
        for slug in OWN:
            m = markers_io.load(slug)
            self.assertGreaterEqual(len(m), 8, slug)
            for i, pat in m.items():
                re.compile(pat)
                self.assertIsInstance(i, int)

    def test_apply_sets_marker_and_pads_stub_rules(self):
        bible = {"speech_guide": {"rules": [{"rule": "a"}, {"rule": "b"}]}}
        n = markers_io.apply_to_bible(bible, "alice")
        rules = bible["speech_guide"]["rules"]
        self.assertEqual(n, len(markers_io.load("alice")))
        self.assertEqual(len(rules), max(markers_io.load("alice")) + 1)
        self.assertEqual(rules[0]["marker"]["pattern"], markers_io.load("alice")[0])
        self.assertTrue(rules[-1].get("stub") or "marker" in rules[-1])

    def test_hyakka_bible_unchanged(self):
        bible = {"speech_guide": {"rules": [{"rule": "a"}]}}
        self.assertEqual(markers_io.apply_to_bible(bible, "hyakka"), 0)
        self.assertEqual(bible, {"speech_guide": {"rules": [{"rule": "a"}]}})

    def test_gate_scores_on_own_markers(self):
        d = tempfile.mkdtemp(prefix="markers_", dir="F:\\temp" if os.path.isdir("F:\\temp") else None)
        bible = {"speech_guide": {"rules": [{"rule": "a"}, {"rule": "b"}, {"rule": "c"}]}}
        markers_io.apply_to_bible(bible, "maria")
        with open(os.path.join(d, "bible.json"), "w", encoding="utf-8") as fh:
            json.dump(bible, fh, ensure_ascii=False)
        try:
            g.load_rule_markers(d)
            self.assertEqual(len(g.RULE_MARKERS), len(markers_io.load("maria")))
            self.assertEqual(g.nb_features(), list(g.RULE_MARKERS))
            self.assertEqual(set(g.features("ですわ")), set(g.RULE_MARKERS))
        finally:
            g.RULE_MARKERS.clear()
        self.assertEqual(g.nb_features(), g.NB_FEATURES)


class RenderGuard(unittest.TestCase):
    def test_render_doc_rejects_a_bible_json_with_a_clear_error(self):
        with self.assertRaises(TypeError):
            kb.render_doc({"identity": {"name": "x"}})

    def test_shipped_alice_renders_from_files(self):
        layers = "F:\\temp\\gate_rerun\\full\\alice\\layers"
        if not os.path.isdir(layers):
            self.skipTest("no full-corpus layers dir")
        md = kb.render_doc_from_files(os.path.join(ROOT, "characters", "alice", "bible.json"), layers)
        self.assertIn("アリス", md)


if __name__ == "__main__":
    unittest.main()
