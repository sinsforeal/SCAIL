"""Felt carry (tk-z1q 10-25): state.felt_carry_minutes keeps a notable update's `reasons` in her mood line as text.
Her real config and State through the bench overlay feltcarry; no arm, no gateway, no spend."""
import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from test_bz_appraisal import TMPDIR, _Clock, real_state  # noqa: E402

HURT = "好きなことを話した直後に「どうでもいい」と切り捨てられ、沈んでいる。"
PREFIX = "さっきのことがまだ残っている: "


class FeltCarry(unittest.TestCase):
    def state(self, overlays, tmp):
        self.clock = _Clock(1_000_000.0)
        return real_state(overlays, tmp, self.clock)

    def test_off_by_default(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.state((), tmp)
            self.assertFalse(st._keep_felt({"anger": 8}, HURT))
            self.assertNotIn(PREFIX, st.mood_tags(ja=True))

    def test_notable_update_is_carried_then_expires(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.state(("feltcarry",), tmp)
            self.assertTrue(st._keep_felt({"anger": 6, "sadness": 4}, HURT))
            self.assertIn(PREFIX + HURT, st.mood_tags(ja=True))
            self.clock.n += 59 * 60
            self.assertIn(PREFIX + HURT, st.mood_tags(ja=True))
            self.clock.n += 2 * 60
            self.assertNotIn(PREFIX, st.mood_tags(ja=True))

    def test_small_update_does_not_overwrite(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.state(("feltcarry",), tmp)
            st._keep_felt({"anger": 6}, HURT)
            self.assertFalse(st._keep_felt({"anxiety": -3, "loneliness": -4}, "ふつうの返事"))
            self.assertIn(PREFIX + HURT, st.mood_tags(ja=True))

    def test_overlay_held3_carries_held2(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.state(("held3",), tmp)
            self.assertEqual(st.config.state.felt_carry_minutes, 60)
            self.assertEqual(st.config.state.max_delta_per_update, 30)
            self.assertEqual(st.config.rupture.min_score, 5.0)


if __name__ == "__main__":
    unittest.main()
