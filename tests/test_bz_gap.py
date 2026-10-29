"""Gap pass (bz/gap 10-27): state.felt_carry_hold_until_resolved and state.silence_call_minutes, on her real config and
State through the bench overlay held4, with a stub state model. No arm, no gateway, no spend."""
import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from test_bz_appraisal import TMPDIR, _Clock, real_state  # noqa: E402

HURT = "好きなことを話した直後に「どうでもいい」と切り捨てられ、沈んでいる。"
WORRY = "彼が具合が悪いと言ったきり返事がなく、心配で落ち着かない。"
PREFIX = "さっきのことがまだ残っている: "
T0 = 1_000_000.0


class Clock(_Clock):
    """_Clock plus the two readers the state call's prompt builder uses."""

    def both(self):
        return "t%d" % int(self.n)

    def hm(self, ts):
        return "%02d:%02d" % (int(ts // 3600) % 24, int(ts // 60) % 60)


class StubLLM:
    """The state role: returns the queued answer, never a network call."""

    def __init__(self):
        self.queue = []

    def call_json(self, role, messages):
        return self.queue.pop(0), "stub"


class Base(unittest.TestCase):
    def state(self, overlays, tmp):
        self.clock = Clock(T0)
        return real_state(overlays, tmp, self.clock)

    def update(self, st, deltas, reasons, **kw):
        llm = StubLLM()
        llm.queue.append({"deltas": deltas, "reasons": reasons})
        return st.update_from_llm(llm, {}, [], kw.pop("user_msg_text", ""), "", **kw)

    def carried(self, st):
        return PREFIX in st.mood_tags(ja=True)


class HeldCarry(Base):
    def test_off_by_default_changes_nothing(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.state(("held3",), tmp)
            self.assertFalse(st.config.state.felt_carry_hold_until_resolved)
            self.assertEqual(st.config.state.silence_call_minutes, 0)
            self.assertTrue(st._keep_felt({"sadness": 8}, HURT))
            self.assertNotIn("hold", st.store.get("felt_carry"))
            self.clock.n += 61 * 60
            self.assertFalse(self.carried(st))
            self.assertIsNone(st.silence_event())
            self.assertFalse(st.resolve_felt({"sadness": -9}, True))

    def test_overlay_held4_is_held3_plus_keys(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.state(("held4",), tmp)
            c = st.config.state
            self.assertEqual((c.felt_carry_minutes, c.max_delta_per_update), (60, 30))
            self.assertTrue(c.felt_carry_hold_until_resolved)
            self.assertEqual((c.felt_carry_hold_max_minutes, c.silence_call_minutes), (1440, 90))
            self.assertEqual(st.config.rupture.min_score, 5.0)

    def test_hurt_survives_past_60_min_while_unresolved(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.state(("held4",), tmp)
            self.update(st, {"sadness": 8, "anger": 3}, HURT)
            self.assertEqual(st.store.get("felt_carry")["hold"], ["sadness"])
            self.clock.n += 3 * 3600
            self.assertIn(PREFIX + HURT, st.mood_tags(ja=True))
            # a neutral update (small moves) neither clears nor replaces it
            self.update(st, {"loneliness": -2}, "ふつうの返事")
            self.assertIn(PREFIX + HURT, st.mood_tags(ja=True))

    def test_worry_held_on_anxiety(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.state(("held4",), tmp)
            self.update(st, {"anxiety": 12}, WORRY)
            self.assertEqual(st.store.get("felt_carry")["hold"], ["anxiety"])
            self.clock.n += 2 * 3600
            self.assertIn(PREFIX + WORRY, st.mood_tags(ja=True))

    def test_anger_carry_is_not_held(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.state(("held4",), tmp)
            self.update(st, {"anger": 9}, "むっとした")
            self.assertNotIn("hold", st.store.get("felt_carry"))
            self.clock.n += 61 * 60
            self.assertFalse(self.carried(st))

    def test_clears_when_a_later_call_lowers_the_gauge(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.state(("held4",), tmp)
            self.update(st, {"anxiety": 12}, WORRY)
            self.clock.n += 3600 * 2
            self.update(st, {"anxiety": -3}, "返事が来た")  # lowered by less than 5: still held
            self.assertIn(PREFIX + WORRY, st.mood_tags(ja=True))
            self.update(st, {"anxiety": -6}, "無事だとわかってほっとした")
            # the worry text is gone; the relief itself (anxiety -6) is a notable update and carries as before, unheld
            self.assertNotIn(WORRY, st.mood_tags(ja=True))
            self.assertNotIn("hold", st.store.get("felt_carry") or {})
            self.clock.n += 61 * 60
            self.assertFalse(self.carried(st))

    def test_clears_when_his_message_addresses_it(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.state(("held4",), tmp)
            self.update(st, {"sadness": 8}, HURT)
            self.clock.n += 600
            self.update(st, {}, "返事", user_msg_text="さっきはごめん", addressed=False)
            self.assertIn(PREFIX + HURT, st.mood_tags(ja=True))
            self.update(st, {}, "返事", user_msg_text="さっきはごめん、好きだよ", addressed=True)
            self.assertFalse(self.carried(st))

    def test_hard_cap(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.state(("held4",), tmp)
            self.update(st, {"sadness": 8}, HURT)
            self.clock.n += 1439 * 60
            self.assertIn(PREFIX + HURT, st.mood_tags(ja=True))
            self.clock.n += 2 * 60
            self.assertFalse(self.carried(st))

    def test_update_that_raises_a_hold_gauge_replaces_a_held_carry(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.state(("held4",), tmp)
            self.update(st, {"sadness": 8}, HURT)
            self.clock.n += 600
            self.update(st, {"anxiety": 7}, WORRY)
            self.assertIn(PREFIX + WORRY, st.mood_tags(ja=True))
            self.assertNotIn(HURT, st.mood_tags(ja=True))

    def test_update_does_not_resolve_its_own_carry(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.state(("held4",), tmp)
            self.update(st, {"sadness": 8}, HURT, addressed=True)
            self.assertIn(PREFIX + HURT, st.mood_tags(ja=True))


class SilenceCall(Base):
    def say(self, st, role, minutes_from_t0):
        st.store.add_message(T0 + minutes_from_t0 * 60, "d", role, "x")

    def test_fires_once_past_threshold_and_rearms_on_his_message(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.state(("held4",), tmp)
            self.say(st, "user", 0)
            self.say(st, "assistant", 1)
            self.clock.n = T0 + 60 * 60
            self.assertIsNone(st.silence_event())  # 59 min after her line
            self.clock.n = T0 + 91 * 60
            ev = st.silence_event()
            self.assertIsNotNone(ev)
            self.assertIn("90 minutes", ev["text"])
            self.clock.n = T0 + 300 * 60
            self.assertIsNone(st.silence_event())  # once per span
            # his message, her reply, a new silence: re-armed
            self.say(st, "user", 301)
            self.say(st, "assistant", 302)
            self.clock.n = T0 + 350 * 60
            self.assertIsNone(st.silence_event())
            self.clock.n = T0 + 400 * 60
            self.assertIsNotNone(st.silence_event())

    def test_does_not_fire_when_he_is_waiting_on_her(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.state(("held4",), tmp)
            self.say(st, "assistant", 0)
            self.say(st, "user", 5)
            self.clock.n = T0 + 600 * 60
            self.assertIsNone(st.silence_event())

    def test_no_line_of_hers_no_call(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.state(("held4",), tmp)
            self.clock.n = T0 + 600 * 60
            self.assertIsNone(st.silence_event())

    def test_off_by_default(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.state((), tmp)
            self.say(st, "assistant", 0)
            self.clock.n = T0 + 600 * 60
            self.assertIsNone(st.silence_event())
            self.assertIsNone(st.store.get("silence_call_span"))

    def test_silence_update_moves_gauge_and_feeds_the_carry(self):
        """The silence event goes into the state call as an event; a raise of anxiety from it is carried and held."""
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.state(("held4",), tmp)
            self.say(st, "user", 0)
            self.say(st, "assistant", 1)
            self.clock.n = T0 + 100 * 60
            ev = st.silence_event()
            seen = {}

            class Spy(StubLLM):
                def call_json(self, role, messages):
                    seen["user"] = messages[-1]["content"]
                    return {"deltas": {"anxiety": 9, "loneliness": 6}, "reasons": WORRY}, "stub"

            before = st.gauges["anxiety"]
            st.update_from_llm(Spy(), {}, [ev], "", "", fresh=True)
            self.assertIn("he has not answered her last message for 99 minutes", seen["user"])
            self.assertGreater(st.gauges["anxiety"], before)
            self.clock.n += 5 * 3600
            self.assertIn(PREFIX + WORRY, st.mood_tags(ja=True))


if __name__ == "__main__":
    unittest.main()
