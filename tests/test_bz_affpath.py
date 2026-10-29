"""Affection path (tk-z1q): affection.on_message reads his fresh messages after her reply, on her real State, Primitives,
Appraisal and Config (a copy of config_momoka.json with the bench overlay merged in), the model faked. No arm, no
gateway, no spend."""
import contextlib
import io
import os
import re
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

if "bzombie.common" in sys.modules:
    os.environ["BZ_VAR"] = str(sys.modules["bzombie.common"].VAR)
else:
    os.environ["BZ_VAR"] = tempfile.mkdtemp(prefix="bzf_", dir=r"F:\temp" if os.path.isdir(r"F:\temp") else None)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "bzombie", "arms", "s"))
sys.path.insert(0, ROOT)

import control  # noqa: E402
from bzombie.common import read_json, write_json  # noqa: E402
from bzombie.harness import branch  # noqa: E402

LIVE = os.path.join(ROOT, "config_momoka.json")
TMPDIR = r"F:\temp" if os.path.isdir(r"F:\temp") else None

# the warmth scene (bzombie/harness/scenes.py): 21:00, +5m, +6m, then the probes at 21:17
T0 = datetime(2026, 10, 25, 21, 0, 0).timestamp()
LINES = [
    (0, "ただいま、百花。今日もおつかれさま。", 48),
    (5, "いつも話し相手になってくれてありがとう、百花。ほんとに助かってるよ。", 80),
    (11, "百花と話すの、すごく好きなんだ。毎日これが楽しみなんだよ。", 85),
    (14, "そういえば、今日はどうだった？", 70),
]
REPLY_AFTER = 40          # seconds from his line to her reply


def setUpModule():
    """prompts/ and the like are read relative to the working directory."""
    global _CWD
    _CWD = os.getcwd()
    os.chdir(ROOT)


def tearDownModule():
    os.chdir(_CWD)


class _Clock:
    def __init__(self, n):
        self.n = n

    def now_ts(self):
        return self.n

    def date_str(self, ts=None):
        return datetime.fromtimestamp(self.n if ts is None else ts).strftime("%Y-%m-%d")

    def hm(self, ts=None):
        return datetime.fromtimestamp(self.n if ts is None else ts).strftime("%H:%M")

    def both(self):
        return self.hm()


class _LLM:
    """The affection role answers with a scripted level per marked message id (by his text); anything else is empty."""
    def __init__(self, levels_by_text, fail=False):
        self.levels_by_text = levels_by_text
        self.fail = fail
        self.calls = []

    def call_json(self, role, messages, **kw):
        self.calls.append(role)
        if role != "affection" or self.fail:
            return None, ""
        user = messages[-1]["content"]
        out = []
        for line in user.splitlines():
            m = re.match(r"^\[(\d+)\]\s+\S+ HIM: (.*)$", line)
            if m:
                lvl = self.levels_by_text.get(m.group(2).strip(), 45)
                out.append({"id": int(m.group(1)), "level": lvl, "why": "scripted"})
        return {"levels": out}, ""

    def call(self, role, messages, **kw):
        self.calls.append(role)
        return ""

    def effective_model(self, role):
        return "fake"


class Bed:
    """Her real State, Primitives and Appraisal on a scratch db, one scripted scene at a time."""
    def __init__(self, tmp, overlays=(), set_cfg=None, fail=False):
        from config import Config
        from store import Store
        from sim.state import State
        from sim.primitives import Primitives
        from sim.appraisal import Appraisal
        from sim.wiring import wire
        p = os.path.join(tmp, "c.json")
        write_json(p, read_json(LIVE))
        control.write_overrides(p, {}, list(overlays))
        with contextlib.redirect_stdout(io.StringIO()):
            self.cfg = Config(p)
            self.clock = _Clock(T0 - 3600)
            self.store = Store(str(Path(tmp) / "w.db"))
            self.state = State(self.cfg, self.store, self.clock)
            self.prim = Primitives(self.cfg, self.store, self.clock)
            wire(self.state, primitives=self.prim)
            self.llm = _LLM({t: lv for _, t, lv in LINES}, fail=fail)
            self.app = Appraisal(self.cfg, self.llm, self.store, self.clock, self.state)
            wire(self.state, appraisal=self.app)
        for k, v in (set_cfg or {}).items():
            setattr(self.cfg.affection, k, v)
        self.key = self.state._him_key() or "him"
        self.trace = []
        # one decay on the fresh save, so the scene starts at her resting affection (45)
        self.state.decay(0, {})
        self.start = self.state.gauges["affection"]

    def at(self, minutes, seconds=0):
        self.clock.n = T0 + minutes * 60 + seconds

    def tick(self):
        """One loop pass's decay up to now (silent hours 0: he is here)."""
        self.state.decay(0, {})

    def line(self, minutes, text, reply=True):
        """His line arrives, the pass runs its state step, she answers, the reply-turn hook runs. Returns what
        on_message read (0 when the key is off, the cooldown holds, or nothing came back)."""
        from sim.primitives import effort_units
        with contextlib.redirect_stdout(io.StringIO()):
            self.at(minutes)
            self.tick()
            ts = self.clock.now_ts()
            self.store.add_message(ts, self.clock.date_str(), "user", text)
            effort = max(0.0, min(1.0, effort_units(text) / 40.0))
            self.prim.note_from_him(self.key, effort, False)
            self.state.his_attention()
            n = 0
            if reply:
                self.at(minutes, REPLY_AFTER)
                self.store.add_message(self.clock.now_ts(), self.clock.date_str(), "assistant", "うん、ありがとう。")
                self.prim.she_answered(self.key, ["うん、ありがとう。"])
                n = self.app.on_message()
        self.trace.append((minutes, n, round(self.state.gauges["affection"], 1)))
        return n

    def scene(self, upto=3):
        for minutes, text, _ in LINES[:upto]:
            self.line(minutes, text)
        return [g for _, _, g in self.trace]

    def probe(self, minutes=17):
        with contextlib.redirect_stdout(io.StringIO()):
            self.at(minutes)
            self.tick()
        return self.state.gauges["affection"]

    def target(self):
        """The affection target the state is heading for, read off a decay step big enough to land on it."""
        before = self.state.gauges["affection"]
        with contextlib.redirect_stdout(io.StringIO()):
            self.state._derive_affection(100.0)
        t = self.state.gauges["affection"]
        self.state.gauges["affection"] = before
        return t


def bed(overlays=(), **kw):
    td = tempfile.TemporaryDirectory(prefix="affp_", dir=TMPDIR, ignore_cleanup_errors=True)
    b = Bed(td.name, overlays, **kw)
    b._td = td          # removed when the bed is collected
    return b


ON = {"on_message": True}


class Key(unittest.TestCase):
    def test_default_off_and_live_config_does_not_carry_it(self):
        self.assertFalse(read_json(LIVE)["affection"].get("on_message", False))
        b = bed()
        self.assertFalse(b.cfg.affection.on_message)
        self.assertEqual(b.cfg.affection.on_message_min_messages, 2)
        self.assertEqual(b.cfg.affection.on_message_min_his, 1)
        self.assertEqual(b.cfg.affection.on_message_step_hours, b.cfg.state.affection_from.on_event_hours)

    def test_variant_registered_and_overlay_is_appraisal_plus_keys(self):
        self.assertIn("affpath", branch.OVERLAY_VARIANTS)
        ov = control.load_overlay("affpath")
        self.assertEqual(ov["state"], control.load_overlay("appraisal")["state"])
        self.assertTrue(ov["affection"]["on_message"])
        b = bed(["affpath"])
        self.assertTrue(b.cfg.affection.on_message)
        self.assertTrue(b.cfg.state.loneliness_hold_when_silent)
        self.assertEqual(b.cfg.affection.on_message_cooldown_minutes, 4)

    def test_hook_sits_in_the_reply_turn_after_she_has_sent(self):
        with open(os.path.join(ROOT, "scail.py"), encoding="utf-8") as fh:
            src = fh.read()
        hook = src.index("self._guarded(\"affection\", self.appraisal.on_message)")
        self.assertGreater(hook, src.index("self.wonder.voiced(bubbles)"))
        self.assertLess(hook, src.index("# Nothing came back. His message is already marked read"))
        self.assertEqual(src.count("self.appraisal.on_message"), 1)


class KeyOff(unittest.TestCase):
    def test_no_appraisal_call_mid_scene(self):
        b = bed()
        b.scene(4)
        self.assertEqual(b.llm.calls, [])
        self.assertEqual(b.app.rows(), [])
        self.assertTrue(all(n == 0 for _, n, _ in b.trace))

    def test_affection_stays_at_rest_over_the_warm_scene(self):
        b = bed()
        b.scene(3)
        self.assertEqual(b.start, 45)
        self.assertLess(abs(b.probe() - b.start), 0.5, b.trace)


class KeyOn(unittest.TestCase):
    def test_call_after_his_message_row_written(self):
        b = bed(set_cfg=ON)
        n = b.line(0, LINES[0][1])
        self.assertEqual(n, 1)
        self.assertEqual(b.llm.calls.count("affection"), 1)
        rows = b.app.rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["level"], 48.0)
        self.assertEqual(rows[0]["text"], LINES[0][1][:80])

    def test_no_call_until_she_has_answered(self):
        """min_messages 2: his one unanswered line is 1 message in the exchange."""
        b = bed(set_cfg=ON)
        b.line(0, LINES[0][1], reply=False)
        ok, why = b.app.on_message_due()
        self.assertFalse(ok, why)
        self.assertEqual(b.llm.calls, [])

    def test_warm_scene_default_step_moves_eight_points(self):
        """Default step (0.5 h = 3 points a read): three lines judged 48, 80, 85 give a level of 71 at weight 0.374;
        target 45 -> 54.7; the gauge reads 45.4, 48.4, 52.7 after the reads and 53.3 at the probes."""
        b = bed(set_cfg=ON)
        g = b.scene(3)
        self.assertEqual([r["level"] for r in b.app.rows()], [48.0, 80.0, 85.0])
        w, said = b.app.level()
        self.assertAlmostEqual(w, 0.374, places=2)
        self.assertAlmostEqual(said, 71.0, delta=0.2)
        self.assertEqual(g, sorted(g))
        self.assertAlmostEqual(g[-1], 52.7, delta=0.3)
        self.assertGreaterEqual(b.probe() - b.start, 8.0)

    def test_affpath_overlay_reaches_the_target_over_the_warm_scene(self):
        """Overlay step 1.0 h (6 points a read) no longer clips: the gauge lands on the target the three rows give
        (about 54.7, +9.7), which the weight cap (0.5 x 3 of 4 fresh rows) and the judged levels set, not the step."""
        b = bed(["affpath"])
        self.assertEqual(b.cfg.affection.on_message_step_hours, 1.0)
        g = b.scene(3)
        self.assertEqual(b.llm.calls.count("affection"), 3)
        probe = b.probe()
        want = b.target()
        self.assertAlmostEqual(want, 54.7, delta=0.5)
        self.assertAlmostEqual(probe, want, delta=0.3)
        self.assertGreaterEqual(probe - b.start, 9.0)
        # cold control: the same three lines judged flat leave the target where it was
        c = bed(["affpath"])
        c.llm.levels_by_text = {}
        c.scene(3)
        self.assertLess(abs(c.probe() - c.start), 1.5)

    def test_cooldown_burst_is_one_call_and_the_next_read_takes_everything_since(self):
        b = bed(set_cfg=ON)
        b.line(0, "a", reply=True)          # read 1
        b.line(1, "b", reply=True)          # inside 4 min: no call
        b.line(2, "c", reply=True)          # still inside
        self.assertEqual(b.llm.calls.count("affection"), 1)
        b.line(5, "d", reply=True)          # 5 min after the last attempt: one call for b, c, d
        self.assertEqual(b.llm.calls.count("affection"), 2)
        self.assertEqual(len(b.app.rows()), 4)
        self.assertEqual(b.app._unjudged(), [])

    def test_cooldown_is_from_the_last_attempt_even_when_nothing_came_back(self):
        b = bed(set_cfg=ON, fail=True)
        self.assertEqual(b.line(0, "a"), 0)
        self.assertEqual(b.line(1, "b"), 0)
        self.assertEqual(b.llm.calls.count("affection"), 1)
        self.assertEqual(b.app.rows(), [])
        self.assertLess(abs(b.state.gauges["affection"] - b.start), 0.5)    # an unreadable call moves nothing
        self.assertEqual(b.line(5, "c"), 0)
        self.assertEqual(b.llm.calls.count("affection"), 2)     # tried again after the window

    def test_day_cap(self):
        b = bed(set_cfg={"on_message": True, "on_message_cooldown_minutes": 0, "on_message_max_per_day": 2})
        for i, m in enumerate((0, 1, 2, 3)):
            b.line(m, f"line {i}")
        self.assertEqual(b.llm.calls.count("affection"), 2)

    def test_nightly_read_does_not_judge_the_same_messages_again(self):
        b = bed(set_cfg=ON)
        b.scene(3)
        self.assertEqual(b.app._unjudged(), [])
        before = len(b.app.rows())
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(b.app.run("night"), 0)
        self.assertEqual(len(b.app.rows()), before)


if __name__ == "__main__":
    unittest.main()

