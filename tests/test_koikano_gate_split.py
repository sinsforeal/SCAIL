"""Leak-free build and cross-subject control for the koikano tools.

Runs the real tools on the kirikiri corpus (read-only) into F:\\temp. Skipped when the corpus is absent.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KDIR = os.path.join(ROOT, "tools", "koikano")
sys.path.insert(0, KDIR)
import koikano_bible as kb  # noqa: E402
import cross_control as cc  # noqa: E402

CORPUS = kb.DEFAULT_CORPUS
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


class Margin(unittest.TestCase):
    def test_floor_and_growth(self):
        self.assertEqual(cc.margin(0.5, 100000, 0.5, 100000), 0.05)
        self.assertGreater(cc.margin(0.5, 50, 0.5, 50), 0.15)


@unittest.skipUnless(os.path.isdir(CORPUS), "kirikiri corpus not present")
class LeakFree(unittest.TestCase):
    def test_build_only_drops_holdout(self):
        base = tempfile.mkdtemp(prefix="gate_split_", dir="F:\\temp" if os.path.isdir("F:\\temp") else None)
        out = os.path.join(base, "h")
        r = subprocess.run([sys.executable, "-I", os.path.join(KDIR, "koikano_bible.py"), "--char", "百花",
                            "--out", out, "--build-only"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           creationflags=CREATE_NO_WINDOW)
        self.assertEqual(r.returncode, 0, r.stderr[-400:])
        bible = json.load(open(os.path.join(out, "bible.json"), encoding="utf-8"))
        self.assertEqual(bible["provenance"]["build_only_excluded_scenes"], kb.HYAKKA_HOLDOUT_SCENES)
        sl = json.load(open(os.path.join(out, "layers", "slice.json"), encoding="utf-8"))
        self.assertFalse(set(sl["scene_ids"]) & set(kb.HYAKKA_HOLDOUT_SCENES))
        self.assertFalse(any(i.split(":")[0] in kb.HYAKKA_HOLDOUT_SCENES for i in sl["her_line_ids"]))

    def test_build_only_needs_out(self):
        r = subprocess.run([sys.executable, "-I", os.path.join(KDIR, "koikano_bible.py"), "--build-only"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           creationflags=CREATE_NO_WINDOW)
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
