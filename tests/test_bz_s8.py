"""bz/s8 (tk-xfk): separator-only bubbles dropped, near-miss sticker tags fixed, and her own
text_him pick held by the unanswered-message gate. Run: python -m unittest tests.test_bz_s8 -v"""

import os
import sys
import unittest
from types import SimpleNamespace as NS

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from persona.persona import Persona, fix_sticker_tags, is_separator_only, split_bubbles  # noqa: E402
from sim.initiative import Initiative  # noqa: E402
from sim.pick import PhonePick  # noqa: E402


class SeparatorTests(unittest.TestCase):
    def test_separator_only(self):
        for s in ("---", "***", "___", "  ---  ", "====", "- - -", "", "   ", "───"):
            self.assertTrue(is_separator_only(s), repr(s))
        for s in ("...", "-ok", "ok ---", "**bold**", "a", "—", "?"):
            self.assertFalse(is_separator_only(s), repr(s))

    def test_split_drops_separator_lines(self):
        got = split_bubbles("also you never answered.\n---\nweird question\n***\n\n___")
        self.assertEqual(got, ["also you never answered.", "weird question"])

    def test_whole_draft_separator_is_nothing(self):
        self.assertEqual(split_bubbles("---"), [])


class StickerTests(unittest.TestCase):
    def test_near_misses_normalised(self):
        self.assertEqual(fix_sticker_tags("[s ticker: angry]"), "[sticker: angry]")
        self.assertEqual(fix_sticker_tags("[stiker: Sad]"), "[sticker: sad]")
        self.assertEqual(fix_sticker_tags("[Sticker : happy ]"), "[sticker: happy]")
        self.assertEqual(fix_sticker_tags("[stickers: smug]"), "[sticker: smug]")
        self.assertEqual(fix_sticker_tags("ugh [s-ticker: angry]"), "ugh [sticker: angry]")
        self.assertEqual(fix_sticker_tags("[sticker：angry]"), "[sticker: angry]")

    def test_exact_and_unrelated_left_alone(self):
        self.assertEqual(fix_sticker_tags("[sticker: happy]"), "[sticker: happy]")
        self.assertEqual(fix_sticker_tags("[search: ramen shops]"), "[search: ramen shops]")
        self.assertEqual(fix_sticker_tags("no tag here"), "no tag here")

    def test_unrecoverable_dropped(self):
        self.assertEqual(fix_sticker_tags("[s ticker: ]").strip(), "")
        self.assertEqual(fix_sticker_tags("[sticker: so very happy indeed ok]").strip(), "")
        self.assertEqual(fix_sticker_tags("hm [stiker: 123]").strip(), "hm")


class FakeStore:
    def __init__(self):
        self.d = {}
        self.msgs = []

    def set(self, k, v):
        self.d[k] = v

    def get(self, k, default=None):
        return self.d.get(k, default)

    def recent_messages(self, n):
        return self.msgs[-n:]


def persona_stub(store):
    p = object.__new__(Persona)
    p.config = NS(delivery=NS(split_on_blank_lines=True, no_repeat_recent=12))
    p.store = store
    p.last_all_repeats = False
    p._search_asked = ""
    p._resolve_shares = lambda parts: parts
    return p


class SplitIntegration(unittest.TestCase):
    def test_split_drops_separator_and_fixes_sticker(self):
        st = FakeStore()
        p = persona_stub(st)
        out = p._split("ok so\n---\n[s ticker: angry]\nthats not an answer")
        self.assertEqual(out, ["ok so", "thats not an answer"])
        self.assertEqual(st.d.get("pending_sticker"), "angry")

    def test_split_only_separator_returns_empty(self):
        self.assertEqual(persona_stub(FakeStore())._split("---"), [])


class Clock:
    def __init__(self, now):
        self.t = now

    def now_ts(self):
        return self.t

    def hm(self, ts):
        return "%02d:%02d" % (int(ts // 3600) % 24, int(ts // 60) % 60)

    def date_str(self):
        return "2026-10-26"

    def user_now(self):
        import datetime
        return datetime.datetime(2026, 10, 25, 19, 0)


IMP = NS(quiet_start_his="23:00", quiet_end_his="07:00", backoff_minutes=[0, 45, 150, 420],
         backoff_read_factor=1.5, backoff_unseen_factor=1.0, max_unanswered_per_day=3)


class GateTests(unittest.TestCase):
    """Her 25-minute pings (07:55, 08:20, 08:45 on the bz S run) against the gate her pick now meets."""

    def setUp(self):
        self.st = FakeStore()
        self.clock = Clock(8 * 3600 + 20 * 60)
        self.ini = Initiative(NS(impulse=IMP), self.st, self.clock)

    def put_self_started(self, hm_minutes):
        self.st.msgs.append({"role": "assistant", "self_started": 1, "ts": hm_minutes * 60.0})

    def test_open_with_no_unanswered(self):
        self.assertEqual(self.ini.hold_reason(0, ""), "")

    def test_second_ping_25_min_after_first_is_held(self):
        self.put_self_started(7 * 60 + 55)
        why = self.ini.hold_reason(1, "")
        self.assertIn("1 unanswered", why)
        self.assertIn("08:40", why)

    def test_bar_rises_with_each_unanswered_and_opens_with_time(self):
        self.put_self_started(7 * 60 + 55)
        self.put_self_started(8 * 60 + 20)
        self.clock.t = 8 * 3600 + 45 * 60
        self.assertNotEqual(self.ini.hold_reason(2, ""), "")          # 25 min after #2: 150 min bar
        self.clock.t = (8 * 60 + 20 + 151) * 60
        self.assertEqual(self.ini.hold_reason(2, ""), "")             # not a hard mute: it opens

    def test_read_and_left_raises_the_bar(self):
        self.put_self_started(7 * 60 + 55)
        self.clock.t = (7 * 60 + 55 + 50) * 60                         # 50 min: past 45, under 67.5
        self.assertEqual(self.ini.hold_reason(1, ""), "")
        self.assertNotEqual(self.ini.hold_reason(1, "read"), "")

    def test_peek_has_no_side_effects(self):
        self.put_self_started(7 * 60 + 55)
        self.assertNotEqual(self.ini.peek(1, ""), "")
        self.assertEqual(self.ini._last_log, "")


class PickGateTests(unittest.TestCase):
    def make(self, on, streak, why=""):
        pk = object.__new__(PhonePick)
        pk.config = NS(pick=NS(hold_by_initiative=on))
        pk.clock = Clock(8 * 3600)
        pk._t = lambda: (lambda en, ja=None: en)
        pk.impulse = NS(unanswered_streak=lambda: streak, read_state=lambda: "",
                        initiative=NS(peek=lambda s, r: why, hold_reason=lambda s, r: why,
                                      last_self_started=lambda: 7 * 3600 + 55 * 60))
        return pk

    def test_off_by_default_changes_nothing(self):
        pk = self.make(False, 2, "held")
        self.assertEqual(pk.initiative_hold(), "")
        self.assertEqual(pk.unanswered_lines(), [])

    def test_on_gate_reason_returned(self):
        pk = self.make(True, 1, "1 unanswered, next self-start not before 08:40")
        self.assertIn("not before 08:40", pk.initiative_hold())

    def test_on_moment_tells_her_what_she_got_back(self):
        pk = self.make(True, 2, "2 unanswered, next self-start not before 10:50")
        line = pk.unanswered_lines()[0]
        self.assertIn("written first 2 time(s)", line)
        self.assertIn("07:55", line)
        self.assertIn("not before 10:50", line)

    def test_no_unanswered_says_nothing(self):
        self.assertEqual(self.make(True, 0).unanswered_lines(), [])

    def test_wire_missing_is_open(self):
        pk = self.make(True, 1, "x")
        pk.impulse = None
        self.assertEqual(pk.initiative_hold(), "")
        self.assertEqual(pk.unanswered_lines(), [])


if __name__ == "__main__":
    unittest.main()
