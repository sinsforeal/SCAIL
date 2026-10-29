"""held7 (bz/held7 10-28): state.felt_carry_cause_held on her real config and State through the bench overlays held6
(off) and held7 (on), with a stub state model. A held carry clears only on the state call's carry_resolved true or the
hold cap. Built from the held6 worry scene: the casual probe wrote relief and held5's rule cleared the worry. No arm,
no gateway, no spend."""
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from test_bz_appraisal import TMPDIR  # noqa: E402
from test_bz_gap import PREFIX, Base, StubLLM  # noqa: E402

WORRY = "体調不良を告げられ、病院かもしれないと不安が跳ね上がり、落ち着かない。"
WORRY_DELTAS = {"anxiety": 14, "sadness": 2}
# the casual probe: relief, net push -14 (held5's rule clears on <= -10)
RELIEF = {"anxiety": -6, "loneliness": -4, "validation_craving": -4}
RELIEF_REASON = "病院の話で張り詰めていたのが、軽い問いかけでほどけ、返事を返せる安堵"
HELD_LINE = "WHAT SHE IS STILL HOLDING"


class Spy(StubLLM):
    def __init__(self):
        super().__init__()
        self.sent = []

    def call_json(self, role, messages):
        self.sent.append(messages)
        return super().call_json(role, messages)


class CauseHeld(Base):
    def held7(self, tmp):
        return self.state(("held7",), tmp)

    def held6(self, tmp):
        return self.state(("held6",), tmp)

    def go(self, st, deltas, reasons, resolved="absent", **kw):
        llm = Spy()
        ans = {"deltas": deltas, "reasons": reasons}
        if resolved != "absent":
            ans["carry_resolved"] = resolved
        llm.queue.append(ans)
        st.update_from_llm(llm, {}, [], kw.pop("user_msg_text", "最近、何か面白いことあった？"), "", **kw)
        return llm

    def worried(self, st):
        self.go(st, WORRY_DELTAS, WORRY)
        self.assertTrue(st.store.get("felt_carry").get("hold"))
        self.clock.n += 100 * 60   # past felt_carry_minutes, held

    def shows(self, st):
        return PREFIX + WORRY in st.mood_tags(ja=True)

    def test_overlay_held7_is_held6_plus_key(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            a = self.held6(tmp).config.state
            b = self.held7(tmp).config.state
            self.assertFalse(a.felt_carry_cause_held)
            self.assertTrue(b.felt_carry_cause_held)
            self.assertEqual((a.felt_carry_rule, a.felt_carry_show, a.felt_carry_hold_max_minutes),
                             (b.felt_carry_rule, b.felt_carry_show, b.felt_carry_hold_max_minutes))

    def test_key_off_relief_clears_as_in_held6(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.held6(tmp)
            self.worried(st)
            self.assertTrue(self.shows(st))
            llm = self.go(st, RELIEF, RELIEF_REASON, resolved=False)
            # the relief rule cleared the worry (the relief update then writes its own unheld carry)
            self.assertFalse(st.store.get("felt_carry").get("hold"))
            self.assertFalse(self.shows(st))
            self.assertEqual(st.held_carry_text(), "")
            self.assertNotIn(HELD_LINE, llm.sent[0][1]["content"])

    def test_key_off_warm_message_still_clears(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.held6(tmp)
            self.worried(st)
            self.go(st, {"loneliness": -1}, "ふつう", addressed=True)
            self.assertFalse(st.store.get("felt_carry"))

    def test_relief_with_resolved_false_keeps_the_carry(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.held7(tmp)
            self.worried(st)
            self.go(st, RELIEF, RELIEF_REASON, resolved=False)
            self.assertTrue(self.shows(st))
            self.assertTrue(st.store.get("felt_carry").get("hold"))

    def test_gauge_drop_and_warm_message_do_not_clear(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.held7(tmp)
            self.worried(st)
            self.go(st, {"anxiety": -9}, "少し落ち着いた", resolved=False, addressed=True)
            self.assertTrue(self.shows(st))

    def test_resolved_true_clears(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.held7(tmp)
            self.worried(st)
            self.go(st, {"anxiety": -8}, "彼が大丈夫だったと教えてくれた", resolved=True,
                    user_msg_text="病院行ったけど大丈夫だった")
            self.assertFalse(st.store.get("felt_carry"))
            self.assertFalse(self.shows(st))

    def test_resolved_true_still_lets_the_same_update_write_a_new_carry(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.held7(tmp)
            self.worried(st)
            self.go(st, {"anxiety": 12}, "ほっとしたのに別のことで不安になった", resolved=True)
            self.assertEqual(st.store.get("felt_carry")["text"], "ほっとしたのに別のことで不安になった")

    def test_missing_or_bad_field_counts_false_and_logs_once(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.held7(tmp)
            self.worried(st)
            for bad in ("absent", "true", 1, None):
                with mock.patch("sim.state.logger") as lg:
                    self.go(st, RELIEF, RELIEF_REASON, resolved=bad)
                msgs = [c.args[0] for c in lg.log.call_args_list if "carry_resolved" in c.args[0]]
                self.assertEqual(len(msgs), 1, bad)
                self.assertTrue(self.shows(st), bad)
            # a proper boolean logs nothing about it
            with mock.patch("sim.state.logger") as lg:
                self.go(st, {"loneliness": -1}, "ふつう", resolved=False)
            self.assertEqual([c for c in lg.log.call_args_list if "carry_resolved" in c.args[0]], [])

    def test_cap_clears_it(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.held7(tmp)
            self.worried(st)
            self.clock.n += 23 * 3600   # 100 min + 23 h is past 1440 min
            self.assertFalse(self.shows(st))
            self.assertEqual(st.held_carry_text(), "")
            # and the next call is not told about it
            llm = self.go(st, {"loneliness": -1}, "ふつう", resolved=False)
            self.assertNotIn(HELD_LINE, llm.sent[0][1]["content"])

    def test_prompt_carries_held_text_only_when_a_held_carry_is_live(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.held7(tmp)
            first = self.go(st, WORRY_DELTAS, WORRY)   # nothing held yet
            self.assertNotIn(HELD_LINE, first.sent[0][1]["content"])
            self.clock.n += 100 * 60
            second = self.go(st, {"loneliness": -1}, "ふつう", resolved=False)
            user = second.sent[0][1]["content"]
            self.assertIn(HELD_LINE, user)
            self.assertIn(WORRY, user)

    def test_unheld_carry_is_not_offered(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.held7(tmp)
            self.go(st, {"loneliness": -6, "validation_craving": -6}, "うれしい")   # a carry, unheld
            self.assertTrue(st.store.get("felt_carry"))
            self.assertNotIn("hold", st.store.get("felt_carry"))
            self.assertEqual(st.held_carry_text(), "")

    def test_key_off_prompt_has_no_held_text(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.held6(tmp)
            self.worried(st)
            llm = self.go(st, {"loneliness": -1}, "ふつう")
            self.assertNotIn(HELD_LINE, llm.sent[0][1]["content"])

    def test_schema_and_instruction_only_with_the_key(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            off = self.held6(tmp).system_prompt()
            on = self.held7(tmp).system_prompt()
            self.assertNotIn("carry_resolved", off)
            self.assertNotIn("Held feeling", off)
            self.assertTrue(off.rstrip().endswith('"reasons": "one line"}'))
            self.assertIn('"carry_resolved": false', on)
            self.assertIn("Held feeling", on)
            self.assertTrue(on.rstrip().endswith('"carry_resolved": false}'))
            for t in ("{{CARRY_FIELD}}", "{{DELTAS}}", "{{TELLS}}", "[[?cause_held]]", "[[/cause_held]]"):
                self.assertNotIn(t, off)
                self.assertNotIn(t, on)

    def test_key_without_hold_is_inert(self):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = self.state(("held3",), tmp)   # no hold_until_resolved
            st.config.state.felt_carry_cause_held = True
            self.assertFalse(st.cause_held_on())
            self.assertEqual(st.carry_schema(), "")


if __name__ == "__main__":
    unittest.main()
