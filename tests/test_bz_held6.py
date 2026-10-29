"""held6 (bz/held6 10-28): state.felt_carry_show on her real config and State through the bench overlays held5 (off) and
held6 (on), with a stub state model. The three "how it shows" lines come from characters/momoka/fills.json
(felt_carry_show). No arm, no gateway, no spend."""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from test_bz_appraisal import TMPDIR  # noqa: E402
from test_bz_gap import PREFIX, Base  # noqa: E402
from test_bz_held5 import DISMISS, REAL, GAPS, SLIGHT, SPREAD  # noqa: E402

with open(os.path.join(ROOT, "characters", "momoka", "fills.json"), encoding="utf-8") as fh:
    LINES = json.load(fh)["felt_carry_show"]

WORRY = "返事が来ない。変なことを言ったかもしれないと気になる。"


class Show(Base):
    def held6(self, tmp):
        return self.state(("held6",), tmp)

    def test_lines_exist_and_quote_no_record_line(self):
        self.assertEqual(sorted(LINES), ["anger", "anxiety", "sadness"])
        for k, v in LINES.items():
            self.assertTrue(v.strip(), k)
            self.assertNotIn("「", v, k)   # behaviour, never a quoted line

    def test_overlay_held6_is_held5_plus_show(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            a = self.state(("held5",), tmp).config.state
            b = self.held6(tmp).config.state
            self.assertFalse(a.felt_carry_show)
            self.assertTrue(b.felt_carry_show)
            self.assertEqual((a.felt_carry_rule, a.felt_carry_minutes, a.silence_call_minutes),
                             (b.felt_carry_rule, b.felt_carry_minutes, b.silence_call_minutes))

    def test_default_off_renders_as_today(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.state(("held5",), tmp)
            self.update(st, SPREAD, SLIGHT)
            self.assertTrue(st.store.get("felt_carry").get("hold"))
            self.assertNotIn("ups", st.store.get("felt_carry"))   # the stored record is held5's
            tags = st.mood_tags(ja=True)
            self.assertIn(PREFIX + SLIGHT, tags)
            for v in LINES.values():
                self.assertNotIn(v, tags)

    def test_held_hurt_shows_the_hurt_line(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.held6(tmp)
            self.update(st, {"sadness": 8, "anger": 3, "validation_craving": 4}, SLIGHT)
            tags = st.mood_tags(ja=True)
            self.assertIn(PREFIX + SLIGHT + ", " + LINES["sadness"], tags)   # right after the carry text
            self.assertNotIn(LINES["anxiety"], tags)
            self.assertNotIn(LINES["anger"], tags)
            # still shown long after felt_carry_minutes while held
            self.clock.n += 3 * 3600
            self.assertIn(LINES["sadness"], st.mood_tags(ja=True))

    def test_held_worry_shows_the_worry_line(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.held6(tmp)
            self.update(st, {"anxiety": 12, "sadness": 2}, WORRY)
            tags = st.mood_tags(ja=True)
            self.assertIn(PREFIX + WORRY + ", " + LINES["anxiety"], tags)
            self.assertNotIn(LINES["sadness"], tags)
            self.clock.n += 2 * 3600
            self.assertIn(LINES["anxiety"], st.mood_tags(ja=True))

    def test_held_sulk_shows_the_anger_line(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.held6(tmp)
            self.update(st, {"anger": 9, "sadness": 3, "validation_craving": 3}, "話を遮られてむっとした")
            tags = st.mood_tags(ja=True)
            self.assertIn(LINES["anger"], tags)
            self.assertNotIn(LINES["sadness"], tags)

    def test_unheld_carry_shows_none(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.held6(tmp)
            # pushes 7 (< hold min 10), magnitude 13: a carry, not held
            self.update(st, {"pride": 6, "anxiety": 4, "unsaid": 3, "relief": 3}, "うれしいけど少し緊張")
            self.assertTrue(self.carried(st))
            self.assertNotIn("hold", st.store.get("felt_carry"))
            tags = st.mood_tags(ja=True)
            for v in LINES.values():
                self.assertNotIn(v, tags)

    def test_held_without_a_feeling_gauge_shows_none(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.held6(tmp)
            self.update(st, {"loneliness": 6, "validation_craving": 6}, "ひとりで待っている")
            self.assertTrue(st.store.get("felt_carry").get("hold"))
            tags = st.mood_tags(ja=True)
            self.assertTrue(self.carried(st))
            for v in LINES.values():
                self.assertNotIn(v, tags)

    def test_resolution_removes_it(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.held6(tmp)
            self.update(st, {"sadness": 8, "anger": 3}, SLIGHT)
            self.assertIn(LINES["sadness"], st.mood_tags(ja=True))
            self.update(st, {"sadness": -6}, "ほっとした")   # a hold gauge lowered by the min
            tags = st.mood_tags(ja=True)
            self.assertNotIn(LINES["sadness"], tags)
            # his warm message resolves it too
            self.update(st, {"sadness": 8, "anger": 3}, SLIGHT)
            self.assertIn(LINES["sadness"], st.mood_tags(ja=True))
            self.update(st, {}, "返事", user_msg_text="さっきはごめん、好きだよ", addressed=True)
            self.assertNotIn(LINES["sadness"], st.mood_tags(ja=True))

    def test_expiry_removes_it(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.held6(tmp)
            self.update(st, {"sadness": 8, "anger": 3}, SLIGHT)
            self.assertIn(LINES["sadness"], st.mood_tags(ja=True))
            self.clock.n += 1441 * 60
            self.assertNotIn(LINES["sadness"], st.mood_tags(ja=True))

    def test_joined_thread_sums_the_raises(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.held6(tmp)
            self.update(st, SPREAD, SLIGHT)   # anxiety 3, sadness 3
            self.clock.n += 300
            self.update(st, {"anger": 4, "sadness": 3, "unsaid": 5}, DISMISS)
            self.assertEqual(st.store.get("felt_carry")["ups"], {"sadness": 6.0, "anxiety": 3.0, "anger": 4.0})
            self.assertIn(LINES["sadness"], st.mood_tags(ja=True))

    def test_replay_brush_off_shows_hurt_not_worry(self):
        """The real 20:04 to 20:23 answers: anxiety 7 against sadness 6 + anger 4, so the thread is hurt."""
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.held6(tmp)
            for (hm, deltas, reasons), gap in zip(REAL, GAPS):
                self.clock.n += gap
                self.update(st, deltas, reasons)
            rec = st.store.get("felt_carry")
            self.assertEqual(rec["ups"], {"sadness": 6.0, "anxiety": 7.0, "anger": 4.0})
            tags = st.mood_tags(ja=True)
            self.assertIn("どうでもいい", tags)
            self.assertIn(LINES["sadness"], tags)
            self.assertNotIn(LINES["anxiety"], tags)

    def test_no_lines_in_the_fills_means_no_show(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.held6(tmp)
            st.config._fills_cache = {}
            self.update(st, {"sadness": 8, "anger": 3}, SLIGHT)
            self.assertEqual(st.mood_tags(ja=True).count(LINES["sadness"]), 0)
            self.assertTrue(self.carried(st))


if __name__ == "__main__":
    unittest.main()
