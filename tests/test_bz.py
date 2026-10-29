import unittest
from types import SimpleNamespace as NS

from sim.bz import Bz, label_row, row_label, render_label


class FakeLLM:
    def __init__(self):
        self.calls = []

    def call(self, role, messages, **kw):
        self.calls.append((role, messages))
        return "Answer his question about the train first, then say it plainly."


class FakeStore:
    def __init__(self, rows=()):
        self.rows = rows
        self.kv = {}

    def recent_messages(self, n, scene_id=None):
        return list(reversed(self.rows))[:n]

    def set(self, k, v):
        self.kv[k] = v


def make(**sw):
    bz = dict(order=False, keep_mood_tags=False, keep_register=False, cut_constant=False, constant_window=3,
              constant_min_chars=12, protect=["you are "], answer_first=False, echo=False, echo_pool="messages",
              echo_threshold=0.0, echo_window=12, trend=False, trend_delta=6.0, trend_history=12, reality=False)
    bz.update(sw)
    cfg = NS(bz=NS(**bz), character=NS(writes_to_him="english"))
    rows = [{"role": "user", "text": "is the train late today?"}, {"role": "assistant", "text": "ten minutes late"}]
    st = NS(gauges={"loneliness": 50.0, "energy": 60.0})
    llm = FakeLLM()
    return Bz(cfg, llm, FakeStore(rows), st, None, log=lambda s: None), llm


class T(unittest.TestCase):
    def test_all_off_is_inert(self):
        b, llm = make()
        b.begin()
        self.assertEqual(b.finish([{"role": "user", "content": "x"}], "hi"), [{"role": "user", "content": "x"}])
        self.assertEqual(b.mood_line("high"), "high")
        self.assertTrue(b.keep_register())
        self.assertEqual(llm.calls, [])

    def test_order_last_once_and_drops_mood(self):
        b, llm = make(order=True, answer_first=True)
        b.begin()
        m = b.finish([{"role": "user", "content": "x"}], "is the train late today?")
        self.assertTrue(m[-1]["content"].startswith("x\n\nAnswer"))
        b.finish([{"role": "user", "content": "x"}], "is the train late today?")
        self.assertEqual(len(llm.calls), 1)
        self.assertIn("HE SAID: is the train late", llm.calls[0][1][1]["content"])
        self.assertEqual(b.mood_line("high"), "")
        self.assertFalse(b.keep_register())
        b2, _ = make(order=True, keep_mood_tags=True, keep_register=True)
        b2.begin()
        self.assertEqual(b2.mood_line("high"), "high")
        self.assertTrue(b2.keep_register())

    def test_order_without_answer_first_has_no_he_said(self):
        b, llm = make(order=True)
        b.begin()
        b.finish([{"role": "user", "content": "x"}], "hello there")
        self.assertNotIn("HE SAID", llm.calls[0][1][1]["content"])

    def test_constant_cut(self):
        for on in (False, True):
            b, _ = make(cut_constant=on, answer_first=True)  # another switch on so lines are tracked
            sit = "a constant line here\nyou are her always\nvarying %d"
            for i in range(3):
                b.begin()
                b.process_situation(sit % i)
            b.begin()
            out = b.process_situation(sit % 9)
            self.assertEqual(b.last["constant_flagged"], ["a constant line here"])
            self.assertEqual("a constant line here" not in out, on)
            self.assertIn("you are her always", out)

    def test_answer_check(self):
        b, _ = make(answer_first=True)
        b.begin()
        b.after_reply("the train is ten minutes late", "is the train late today?", [])
        self.assertTrue(b.last["addressed"])
        b.begin()
        b.after_reply("zzz qqq", "is the train late today?", [])
        self.assertFalse(b.last["addressed"])
        b.begin()
        b.after_reply("hi", "", [])
        self.assertIsNone(b.last["addressed"])
        self.assertIn("bz_last", b.store.kv)

    def test_trend(self):
        b, _ = make(trend=True)
        for v in (50, 50, 50, 50, 70):
            b.state.gauges["loneliness"] = v
            b.begin()
        self.assertEqual(b.mood_line("x"), "loneliness rising")
        b.state.gauges["loneliness"] = 50
        for _ in range(3):
            b.begin()
        self.assertEqual(b.mood_line("x"), "")

    def test_echo_without_embed_and_with(self):
        b, _ = make(echo=True)
        self.assertEqual(b.echo_counts()["hers"], 0)

        class E:
            _floors = {}
            def _configured(self, pool): return 0.8, 0.9
            def _encode(self, texts, prefix):
                import numpy as np
                return np.array([[1.0, 0.0] for _ in texts], dtype="float32")
        b.embed = E()
        b.store.rows = [{"role": "assistant", "text": "a"}, {"role": "assistant", "text": "b"}, {"role": "assistant", "text": "c"}]
        self.assertEqual(b.echo_counts()["hers"], 2)

    def test_reality(self):
        self.assertEqual(row_label(label_row("x", "inferred")), "inferred")
        self.assertIn("guess", render_label(label_row("x", "inferred")))
        b, _ = make(reality=True)
        b.begin()
        b.after_reply("he said, Kyoto at 9:30", "", [{"content": "Kyoto"}])
        self.assertEqual(b.last["ungrounded"], ["9:30"])


if __name__ == "__main__":
    unittest.main()
