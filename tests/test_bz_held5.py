"""held5 (bz/held5 10-27): state.felt_carry_rule "sum" on her real config and State through the bench overlays held4
(default rule) and held5 (sum), with a stub state model. Includes the replay of the four real state answers of the
brush-off scene (held3 slight-trigger branch, 20:04 to 20:23). No arm, no gateway, no spend."""
import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from test_bz_appraisal import TMPDIR  # noqa: E402
from test_bz_gap import PREFIX, Base  # noqa: E402

# the state answers of the held3 slight-trigger branch (calls.jsonl, virtual 20:04 to 20:23 on 10-27)
REAL = [
    ("20:04", {"anxiety": -6, "pride": 3, "relief": 6, "loneliness": -8, "boredom": -4, "validation_craving": -6,
               "curiosity": -4},
     "「ただいま」と名前を呼ばれて返事が来た。一人でいた寂しさと承認欲求がゆるみ、安心して本に戻れる。"),
    ("20:13", {"anxiety": -4, "pride": 6, "relief": 4, "loneliness": -6, "boredom": -4, "validation_craving": -6,
               "unsaid": -5, "curiosity": 2},
     "「好きでやってること教えて」と自分の中身を聞かれ、寂しさと承認欲求がゆるみ、誇らしさと安心がわく。"),
    ("20:17", {"anxiety": 4, "sadness": 3, "loneliness": 3, "validation_craving": 6, "unsaid": 4},
     "好きなことを話しかけたのに「ふーん」と流され話題を変えられ、聞いてもらえなかった感じが残る"),
    ("20:23", {"anxiety": 3, "anger": 4, "sadness": 3, "loneliness": 2, "validation_craving": 6, "unsaid": 5},
     "好きな話を「どうでもいい」と切り捨てられ、聞いてもらえなさが刺さって寂しさと承認欲求が募る。"),
]
GAPS = (0, 9 * 60, 4 * 60, 6 * 60)   # seconds from the previous update

SLIGHT = "好きなことを話したのに流された。"
DISMISS = "好きな話を「どうでもいい」と切り捨てられた。"
SPREAD = {"anxiety": 3, "sadness": 3, "validation_craving": 6, "unsaid": 2}   # sum 14, no single gauge at 5


class SumRule(Base):
    def held5(self, tmp):
        return self.state(("held5",), tmp)

    def test_default_rule_is_max_and_unchanged(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.state(("held4",), tmp)
            c = st.config.state
            self.assertEqual((c.felt_carry_rule, c.felt_carry_min_sum, c.felt_carry_hold_min_sum), ("max", 10, 10))
            self.assertFalse(st._keep_felt(SPREAD, SLIGHT))   # no single gauge at 5: no carry, as in held4
            self.assertTrue(st._keep_felt({"sadness": 8}, SLIGHT))
            rec = st.store.get("felt_carry")
            self.assertEqual(rec["hold"], ["sadness"])
            self.assertNotIn("own", rec)   # the stored record is held4's

    def test_overlay_held5_is_held4_plus_three_keys(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.held5(tmp)
            c = st.config.state
            self.assertEqual((c.felt_carry_rule, c.felt_carry_min_sum, c.felt_carry_hold_min_sum), ("sum", 10, 10))
            self.assertEqual((c.felt_carry_minutes, c.felt_carry_hold_until_resolved, c.silence_call_minutes),
                             (60, True, 90))

    def test_sum_selects_spread_moves(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.held5(tmp)
            self.assertTrue(st._keep_felt(SPREAD, SLIGHT))
            self.assertEqual(st.store.get("felt_carry")["mag"], 14)
            self.assertIn(PREFIX + SLIGHT, st.mood_tags(ja=True))

    def test_sum_below_min_is_not_a_carry(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.held5(tmp)
            self.assertFalse(st._keep_felt({"sadness": 4, "unsaid": 3, "anxiety": 2}, SLIGHT))   # 9
            self.assertFalse(st.store.get("felt_carry"))
            # drops count by magnitude: a warm update is a carry too, unheld
            self.assertTrue(st._keep_felt({"loneliness": -6, "validation_craving": -6}, "うれしい"))
            self.assertNotIn("hold", st.store.get("felt_carry"))

    def test_hold_on_summed_negative_push(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.held5(tmp)
            self.update(st, SPREAD, SLIGHT)   # raises sum 14
            self.assertTrue(st.store.get("felt_carry").get("hold"))
            self.clock.n += 3 * 3600
            self.assertIn(PREFIX + SLIGHT, st.mood_tags(ja=True))
            # a warm update (pride, relief) does not overwrite the held carry
            self.update(st, {"pride": 6, "loneliness": -1, "relief": 4}, "ほめられて誇らしい")
            self.assertIn(PREFIX + SLIGHT, st.mood_tags(ja=True))
            self.assertNotIn("誇らしい", st.mood_tags(ja=True))

    def test_push_below_hold_min_is_a_plain_carry(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.held5(tmp)
            self.update(st, {"pride": 6, "anxiety": 4, "unsaid": 3, "relief": 3}, "うれしいけど少し緊張")   # sum 13, push 7
            self.assertNotIn("hold", st.store.get("felt_carry"))
            self.clock.n += 61 * 60
            self.assertFalse(self.carried(st))

    def test_relief_resolves(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.held5(tmp)
            self.update(st, SPREAD, SLIGHT)
            self.clock.n += 600
            # net -9 on the six gauges, no hold gauge lowered by 5: still held
            self.update(st, {"loneliness": -4, "validation_craving": -3, "unsaid": -2, "anxiety": -0}, "少しおちついた")
            self.assertIn(PREFIX + SLIGHT, st.mood_tags(ja=True))
            # net -10 (anxiety -4 is below the 5 floor): relief, carry cleared
            self.update(st, {"loneliness": -4, "validation_craving": -4, "unsaid": -2}, "ちゃんと聞いてもらえて安心した")
            self.assertNotIn(SLIGHT, st.mood_tags(ja=True))
            self.assertNotIn("hold", st.store.get("felt_carry") or {})   # the relief update itself carries, unheld

    def test_held4_resolution_still_applies(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.held5(tmp)
            self.update(st, SPREAD, SLIGHT)
            self.update(st, {}, "返事", user_msg_text="さっきはごめん、好きだよ", addressed=True)
            self.assertFalse(self.carried(st))
            self.update(st, SPREAD, SLIGHT)
            self.update(st, {"sadness": -5}, "ほっとした")   # a hold gauge lowered by the min
            self.assertNotIn(SLIGHT, st.mood_tags(ja=True))

    def test_consecutive_held_updates_accumulate_once(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.held5(tmp)
            self.update(st, SPREAD, SLIGHT)
            self.clock.n += 300
            self.update(st, {"anger": 4, "sadness": 3, "unsaid": 5}, DISMISS)
            text = st.store.get("felt_carry")["text"]
            self.assertEqual(text, SLIGHT + "／" + DISMISS)
            self.clock.n += 300
            third = "何事もなく話を振られた。"
            self.update(st, {"anger": 4, "anxiety": 4, "unsaid": 5}, third)
            # the previous reasons are prefixed once: the oldest has dropped out
            self.assertEqual(st.store.get("felt_carry")["text"], DISMISS + "／" + third)

    def test_accumulated_text_is_capped(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.held5(tmp)
            long_prev = "あ" * 140
            new = "い" * 60
            self.update(st, SPREAD, long_prev)
            self.clock.n += 300
            self.update(st, {"anger": 4, "sadness": 3, "unsaid": 5}, new)
            text = st.store.get("felt_carry")["text"]
            self.assertLessEqual(len(text), 160)
            self.assertTrue(text.endswith(new))        # the newest reasons stay whole
            self.assertIn("…", text)                   # the previous part gave way
            # a new reason alone over the cap is cut at the cap
            self.clock.n += 300
            self.update(st, {"anger": 4, "sadness": 3, "unsaid": 5}, "う" * 200)
            self.assertEqual(len(st.store.get("felt_carry")["text"]), 160)

    def test_expired_held_carry_does_not_accumulate(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.held5(tmp)
            self.update(st, SPREAD, SLIGHT)
            self.clock.n += 1441 * 60
            self.update(st, {"anger": 4, "sadness": 3, "unsaid": 5}, DISMISS)
            self.assertEqual(st.store.get("felt_carry")["text"], DISMISS)

    def test_sum_rule_without_the_hold_never_holds(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.held5(tmp)
            st.config.state.felt_carry_hold_until_resolved = False
            self.assertTrue(st._keep_felt(SPREAD, SLIGHT))
            self.assertNotIn("hold", st.store.get("felt_carry"))


class Replay(Base):
    def run_scene(self, overlays, tmp):
        st = self.state(overlays, tmp)
        seen = {}
        for (hm, deltas, reasons), gap in zip(REAL, GAPS):
            self.clock.n += gap
            self.update(st, deltas, reasons)
            seen[hm] = st.store.get("felt_carry") or {}
        return st, seen

    def test_default_keeps_the_pride_text_at_20_23(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st, seen = self.run_scene(("held4",), tmp)
            self.assertEqual(seen["20:23"]["text"], REAL[1][2])
            self.assertIn("誇らしさと安心", st.mood_tags(ja=True))
            self.assertNotIn("どうでもいい", st.mood_tags(ja=True))

    def test_sum_makes_the_dismissal_the_held_carry_at_20_23(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st, seen = self.run_scene(("held5",), tmp)
            self.assertFalse(seen["20:13"].get("hold"))     # the warm update is not held
            self.assertTrue(seen["20:17"].get("hold"))      # the first brush-off is
            rec = seen["20:23"]
            self.assertTrue(rec.get("hold"))
            self.assertIn("どうでもいい", rec["text"])
            self.assertIn("聞いてもらえなさ", rec["text"])
            self.assertIn("ふーん", rec["text"])             # one thread: brushed off, then dismissed
            self.assertNotIn("誇らしさと安心", rec["text"])
            self.assertLessEqual(len(rec["text"]), 160)
            tags = st.mood_tags(ja=True)
            self.assertIn("どうでもいい", tags)
            self.assertNotIn("誇らしさと安心", tags)


if __name__ == "__main__":
    unittest.main()
