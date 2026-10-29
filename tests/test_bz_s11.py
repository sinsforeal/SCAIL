import json
import os
import sys
import unittest
from types import SimpleNamespace as NS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sim import pick_change, shape  # noqa: E402
from sim.pick import PhonePick  # noqa: E402


class Store:
    def __init__(self, msgs=(), events=(), kv=None):
        self.msgs, self.events, self.kv = list(msgs), list(events), dict(kv or {})

    def get(self, k, d=None):
        return self.kv.get(k, d)

    def set(self, k, v):
        self.kv[k] = v

    def last_message(self, role=None):
        r = [m for m in self.msgs if role is None or m["role"] == role]
        return r[-1] if r else None

    def recent_events(self, n):
        return self.events[-n:]


C = NS(ceiling_minutes=180, gauge_move=12, event_salience=2, silence_steps_hours=[2, 6, 12])
T0 = 1_000_000.0
BASE = {"ts": T0, "gauges": {"mood": 50.0, "anger": 8.0}, "idle": 0}


def why(store, now, gauges=None, base=BASE):
    st = NS(gauges=gauges or {"mood": 50.0, "anger": 8.0})
    return pick_change.reasons(C, store, st, now, base, (now - base.get("ts", now)) / 60.0)


class DueTests(unittest.TestCase):
    def test_no_change_no_reason(self):
        self.assertEqual(why(Store(), T0 + 3000), [])

    def test_first_look(self):
        self.assertEqual(why(Store(), T0, base={}), ["first look"])

    def test_his_message(self):
        s = Store(msgs=[{"role": "user", "ts": T0 + 100, "text": "hi"}])
        self.assertIn("he wrote", why(s, T0 + 3000))

    def test_old_message_is_not_a_change(self):
        s = Store(msgs=[{"role": "user", "ts": T0 - 100, "text": "hi"}])
        self.assertEqual(why(s, T0 + 3000), [])

    def test_pc_event_and_return(self):
        s = Store(kv={"phone_account": {"ts": T0 + 50}, "phone_last_live": {"ts": T0 + 50, "idle_min": 0}})
        r = why(s, T0 + 3000, base=dict(BASE, idle=60))
        self.assertIn("pc event", r)
        self.assertIn("he is back at his machine", r)

    def test_world_event_salience(self):
        lo = Store(events=[{"ts": T0 + 10, "salience": 1, "text": "x"}])
        hi = Store(events=[{"ts": T0 + 10, "salience": 2, "text": "bell"}])
        self.assertEqual(why(lo, T0 + 3000), [])
        self.assertTrue(why(hi, T0 + 3000)[0].startswith("world event"))

    def test_gauge_move(self):
        r = why(Store(), T0 + 3000, gauges={"mood": 50.0, "anger": 25.0})
        self.assertEqual(len(r), 1)
        self.assertIn("gauge anger", r[0])
        self.assertEqual(why(Store(), T0 + 3000, gauges={"mood": 55.0, "anger": 8.0}), [])

    def test_expectation_due(self):
        s = Store(kv={"expectations": [{"state": "open", "due_ts": T0 + 500}]})
        self.assertIn("expectation came due", why(s, T0 + 3000))
        s = Store(kv={"expectations": [{"state": "open", "due_ts": T0 + 99999}]})
        self.assertEqual(why(s, T0 + 3000), [])

    def test_silence_step(self):
        s = Store(msgs=[{"role": "user", "ts": T0 - 3600, "text": "bye"}])
        self.assertEqual(why(s, T0 + 600), [])
        self.assertIn("his silence reached 2h", why(s, T0 + 3700))

    def test_ceiling(self):
        r = why(Store(), T0 + 181 * 60)
        self.assertTrue(r and r[0].startswith("ceiling"))
        self.assertEqual(why(Store(), T0 + 179 * 60), [])


class Clock:
    def __init__(self, now):
        self.n = now

    def now_ts(self):
        return self.n

    def date_str(self):
        return "d"


def picker(store, now, on=True):
    pk = object.__new__(PhonePick)
    pk.config = NS(pick=NS(enabled=True, max_per_day=30, min_gap_minutes=25, due_on_change=on,
                           moments=NS(block=True, scene=True, beat=True, inbound=True), **vars(C)))
    pk.store, pk.clock, pk.live, pk.state, pk.director = store, Clock(now), True, NS(gauges={"mood": 50.0, "anger": 8.0}), None
    pk.last_refusal = pk.last_due_why = ""
    pk.offered = lambda t: True
    pk.block_key = lambda sch=None: ("d|08:00", None)
    pk.scene_key = lambda sc: "s"
    store.today_count = lambda *a: 0
    return pk


class PickDueTests(unittest.TestCase):
    def test_floor_blocks_even_with_change(self):
        s = Store(kv={"pick_last_ts": T0, "pick_base": BASE, "pick_block": "d|08:00"},
                  msgs=[{"role": "user", "ts": T0 + 10, "text": "hi"}])
        ok, w, _ = picker(s, T0 + 600).due("block", "free")
        self.assertFalse(ok)
        self.assertIn("since her last look", w)

    def test_no_change_refused_past_floor(self):
        s = Store(kv={"pick_last_ts": T0, "pick_base": BASE, "pick_block": "x"})
        ok, w, _ = picker(s, T0 + 3000).due("block", "free")
        self.assertFalse(ok)
        self.assertTrue(w.startswith("nothing changed"))

    def test_change_makes_due_and_records_why(self):
        s = Store(kv={"pick_last_ts": T0, "pick_base": BASE, "pick_block": "d|08:00"},
                  events=[{"ts": T0 + 100, "salience": 2, "text": "bell"}])
        pk = picker(s, T0 + 3000)
        ok, w, trig = pk.due("block", "free")
        self.assertTrue(ok)
        self.assertIn("world event", pk.last_due_why)

    def test_ceiling_unfreezes(self):
        s = Store(kv={"pick_last_ts": T0, "pick_base": BASE, "pick_block": "d|08:00"})
        ok, _, _ = picker(s, T0 + 200 * 60).due("block", "free")
        self.assertTrue(ok)

    def test_off_keeps_old_behaviour(self):
        s = Store(kv={"pick_last_ts": T0, "pick_block": "d|08:00", "pick_scene": "s"})
        ok, w, _ = picker(s, T0 + 3000, on=False).due("block", "free")
        self.assertFalse(ok)
        self.assertTrue(w.startswith("already looked"))


class PushbackTests(unittest.TestCase):
    def make(self, gauges, on=True, base=0.45):
        sh = object.__new__(shape.Shape)
        st = Store()
        sh.state = NS(gauges=gauges, store=st)
        sh.clock = Clock(T0)
        sh.config = NS(shape=NS(pushback=NS(enabled=on, base=base, threshold=0.5, min_gap_minutes=20,
                                            how="loud, rude as affection.")))
        shape.Shape.ja = property(lambda self: False)
        return sh

    CALM = {"mood": 90, "anger": 0, "awkwardness": 0, "shame": 0, "stress": 5, "anxiety": 5, "energy": 70}
    EDGY = {"mood": 55, "anger": 8, "awkwardness": 5, "shame": 5, "stress": 6, "anxiety": 36, "energy": 64}

    def real_windows(self):
        p = r"F:/REPS2/SCAILV4/var/bzombie/runs/cl2_s_tomoe/transcript.jsonl"
        if not os.path.exists(p):
            self.skipTest("no cl2_s_tomoe transcript")
        with open(p, encoding="utf-8") as f:
            rows = [json.loads(l) for l in f]
        return {r["i"]: r["text"] for r in rows if r["who"] == "him"}

    def test_wants_kind_on_real_windows(self):
        w = self.real_windows()
        self.assertEqual(shape.wants_kind(w[39]), "do")     # just reply to the newest dog video
        self.assertEqual(shape.wants_kind(w[46]), "do")     # just say 'ok this one wins'
        self.assertEqual(shape.wants_kind(w[71]), "do")     # "just dont pick something so weird": a don't beats "definitely"
        self.assertEqual(shape.wants_kind("just me and the computer tonight"), "")
        self.assertEqual(shape.wants_kind("it is definitely weird"), "agree")
        self.assertEqual(shape.wants_kind(w[67]), "")       # a plain report

    def test_a_read_that_lands_is_reads_her(self):
        w = self.real_windows()
        self.assertEqual(shape.engage_kind(w[26]), "reads_her")  # you're not the one who has to live with it

    def test_fires_edgy_tomoe_not_calm(self):
        w = self.real_windows()
        line = self.make(self.EDGY).pushback(w[39])
        self.assertIn("push back", line)
        self.assertIn("loud, rude as affection", line)
        self.assertEqual(self.make(self.CALM).pushback(w[39]), "")

    def test_min_gap_and_off_and_no_ask(self):
        w = self.real_windows()
        sh = self.make(self.EDGY)
        self.assertTrue(sh.pushback(w[39]))
        self.assertEqual(sh.pushback(w[46]), "")
        self.assertEqual(sh.last_pushback.get("held"), "min gap")
        self.assertEqual(self.make(self.EDGY, on=False).pushback(w[39]), "")
        self.assertEqual(self.make(self.EDGY).pushback(w[67]), "")


class RealPathTests(unittest.TestCase):
    """Real Config, Store, State and Shape: no stub between pushback and its store."""

    def test_pushback_through_real_state_store(self):
        import tempfile
        from pathlib import Path
        from config import Config
        from store import Store
        from sim.state import State
        with tempfile.TemporaryDirectory(dir=os.environ.get("TEMP"), ignore_cleanup_errors=True) as tmp:
            cfg = Config(os.path.join(ROOT, "config_momoka.json"))
            cfg.shape.pushback.enabled = True
            cfg.shape.pushback.base = 0.9
            store = Store(str(Path(tmp) / "w.db"))
            clock = Clock(T0)
            st = State(cfg, store, clock)
            self.assertIs(st.store, store)
            sh = shape.Shape(cfg, st, clock)
            line = sh.pushback("just reply to the newest dog video")
            self.assertTrue(line, sh.last_pushback)
            self.assertTrue(sh.last_pushback["fired"])
            self.assertEqual(float(store.get("pushback_last")), T0)
            self.assertEqual(sh.pushback("just say ok this one wins"), "")
            self.assertEqual(sh.last_pushback.get("held"), "min gap")
            clock.n = T0 + 21 * 60
            self.assertTrue(sh.pushback("just say ok this one wins"))


class LongHoldTests(unittest.TestCase):
    def test_start_after_long_nothing_changed_hold(self):
        s = Store(kv={"pick_last_ts": T0, "pick_base": BASE, "pick_block": "d|08:00", "pick_scene": "s"})
        ok, w, _ = picker(s, T0 + 150 * 60).due("block", "free")
        self.assertFalse(ok)
        self.assertTrue(w.startswith("nothing changed"))
        pk = picker(s, T0 + 181 * 60)
        ok, w, _ = pk.due("block", "free")
        self.assertTrue(ok, w)
        self.assertIn("ceiling", pk.last_due_why)


if __name__ == "__main__":
    unittest.main()
