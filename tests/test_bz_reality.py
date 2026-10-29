"""bz.reality: labels written by wonder / foresight / spiral and shown by
situation lines, recall, diary; off switch leaves rows and lines as before.
Plus open expectations passed to the bz order."""
import shutil
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

from sim import bz
from sim.bz import Bz

_ROOT = Path(__file__).resolve().parent.parent


class KV:
    """store stub: kv, events, messages."""
    def __init__(self):
        self.kv = {}
        self.events = []

    def get(self, k, d=None):
        return self.kv.get(k, d)

    def set(self, k, v):
        self.kv[k] = v

    def bump_today(self, k, d):
        m = self.kv.setdefault(k, {})
        m[d] = m.get(d, 0) + 1

    def digests_for_date(self, d):
        return []

    def user_facts(self):
        return []

    def recent_messages(self, n, scene_id=None):
        return []

    def events_for_date(self, d):
        return []

    def add_event(self, ts, date, kind, text, salience=1):
        self.events.append({"ts": ts, "date": date, "kind": kind, "text": text, "salience": salience})


class Clock:
    def now_ts(self): return 1000.0
    def date_str(self): return "2026-10-22"
    def hm(self, ts=None): return "10:00"
    def both(self): return "Thu 10:00"


def cfg(on):
    c = _config()
    c.bz.reality = on
    return c


_CFG = None


def _config():
    global _CFG
    if _CFG is None:
        from config import Config
        d = Path("F:/temp/bz_s6_test")
        d.mkdir(parents=True, exist_ok=True)
        p = d / "config.json"
        shutil.copyfile(_ROOT / "config_momoka.json", p)
        _CFG = Config(str(p))
    return _CFG


class LLM:
    def __init__(self, data):
        self.data = data

    def call_json(self, role, messages, **kw):
        return self.data, ""


class Reality(unittest.TestCase):
    def test_show_and_helpers(self):
        self.assertEqual(bz.show("plain"), "plain")
        self.assertIn("guess", bz.show("[inferred] he is cold"))
        self.assertIn("想像", bz.show("[imagined] x", ja=True))
        self.assertFalse(bz.reality_on(NS()))
        self.assertTrue(bz.reality_on(NS(bz=NS(reality=True))))

    def _wonder(self, on):
        from sim.wonder import Wonder
        w = Wonder(cfg(on), LLM({"questions": [{"text": "does he mind when I am late", "kind": "understand"}]}),
                   KV(), Clock(), NS(mood_tags=lambda: "calm", gauges={}))
        w._classify_typesafe = lambda user, added: None
        added = w.run(scene=None, why="t")
        return w, added

    def test_wonder(self):
        w, added = self._wonder(True)
        self.assertEqual(added[0]["reality"], "inferred")
        self.assertIn("guess", w.situation_line())
        w2, added2 = self._wonder(False)
        self.assertNotIn("reality", added2[0])
        self.assertNotIn("guess", w2.situation_line())
        # a labelled row read with the switch off reads as before
        w2.store.kv["questions"][0]["reality"] = "inferred"
        self.assertNotIn("guess", w2.situation_line())

    def _foresight(self, on):
        from sim.foresight import Foresight
        f = Foresight(cfg(on), LLM({"reply_p": 0.7, "reply_minutes": 30, "tone": "warm", "risk": "", "plan": ""}),
                      KV(), Clock(), NS(gauges={}))
        f._numbers_typesafe = lambda user: None
        return f, f.predict("hello")

    def test_foresight(self):
        f, rec = self._foresight(True)
        self.assertEqual(rec["reality"], "imagined")
        self.assertIn("imagined", f.situation_line())
        f2, rec2 = self._foresight(False)
        self.assertNotIn("reality", rec2)
        self.assertNotIn("imagined", f2.situation_line())

    def _spiral(self, on):
        from sim.spiral import Spirals
        sp = Spirals(cfg(on), LLM({"step": "maybe she meant it", "seed": "a short reply", "about": "mina", "terminus": "b1"}),
                     KV(), Clock(), NS(gauges={}, relationships={}))
        sp.self_model = NS(anchor_brief=lambda: "", get=lambda tid: {"text": "I am too much", "invested": 50})
        sp.records = None
        sp._pay = lambda arrived: None
        row = sp.run(None, "new", "t")
        return sp, row

    def test_spiral(self):
        sp, row = self._spiral(True)
        self.assertEqual(row["reality"], "inferred")
        self.assertIn("guess", sp.prompt_text())
        sp2, row2 = self._spiral(False)
        self.assertNotIn("reality", row2)
        self.assertNotIn("guess", sp2.prompt_text())

    def test_spiral_event_and_renderers(self):
        # the arrival event carries the prefix; recall and diary renderers turn it into words
        t = "[inferred] (she has not said any of this) she has talked herself all the way to it: x"
        self.assertEqual(bz.row_label(t), "inferred")
        out = bz.show(t, cfg(True))
        self.assertTrue(out.startswith(("(guess from what she saw)", "（見たことからの推測）")))
        self.assertEqual(bz.show("(she has not said any of this) x", cfg(False)), "(she has not said any of this) x")


class Expect(unittest.TestCase):
    def test_expecting_in_order(self):
        class LLM2:
            def __init__(self): self.calls = []
            def call(self, role, messages, **kw):
                self.calls.append(messages)
                return "do it"
        c = NS(bz=NS(order=True, keep_mood_tags=False, keep_register=False, cut_constant=False, constant_window=3,
                     constant_min_chars=12, protect=[], answer_first=False, echo=False, trend=False, reality=False),
               character=NS(writes_to_him="english"))
        llm = LLM2()
        b = Bz(c, llm, KV(), NS(gauges={"mood": 50.0}), None, log=lambda s: None)
        b.store.recent_messages = lambda n, scene_id=None: []
        exp = NS(situation_line=lambda ja=False: "what you are expecting of him: he said he would call")
        b.begin()
        b.finish([{"role": "user", "content": "x"}], "hi", "", b.expecting(exp, False))
        self.assertIn("EXPECTING: what you are expecting of him: he said he would call", llm.calls[0][1]["content"])
        self.assertEqual(b.expecting(None), "")
        self.assertEqual(b.expecting(NS(situation_line=lambda ja=False: 1 / 0)), "")


if __name__ == "__main__":
    unittest.main()
