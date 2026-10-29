"""Appraisal fixes (tk-z1q): state.loneliness_hold_when_silent and the mid-range felt tags, on her real config and State
through the bench overlays appraisal, midtags and lonehold. No arm, no gateway, no spend."""
import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

if "bzombie.common" in sys.modules:
    os.environ["BZ_VAR"] = str(sys.modules["bzombie.common"].VAR)
else:
    os.environ["BZ_VAR"] = tempfile.mkdtemp(prefix="bza_", dir=r"F:\temp" if os.path.isdir(r"F:\temp") else None)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "bzombie", "arms", "s"))
sys.path.insert(0, ROOT)

import control  # noqa: E402
from bzombie.common import read_json, write_json  # noqa: E402
from bzombie.harness import branch  # noqa: E402
from sim.lang import feeling_ja  # noqa: E402

LIVE = os.path.join(ROOT, "config_momoka.json")
TMPDIR = r"F:\temp" if os.path.isdir(r"F:\temp") else None
OVERLAYS = ("appraisal", "midtags", "lonehold")

ANX_MID = "ちょっと心配。悪いほうに考えかけて、胸のあたりがそわそわする"
ANX_HI = "心配で落ち着かない。悪いほうに考えてしまって、「やっぱり、百花には無理？」と彼に違うよと言ってほしい"
ANGER_MID = "ちょっとむっとした。ほんの少し、すねている"
ANGER_25 = feeling_ja("irritated under it")
ANGER_45 = feeling_ja("angry about something, and holding it in")
BORED_MID = "することがなくて、ちょっと退屈。ぼんやりしている"
EN_MID = "すこしねむい。低血圧で、頭がぼんやりしている"
EN_LOW = "ねむい。低血圧のぼんやりが抜けなくて、からだがおもい。無理はしたくない"


class _Clock:
    def __init__(self, n):
        self.n = n

    def now_ts(self):
        return self.n

    def date_str(self):
        return "d"


def real_state(overlays, tmp, clock):
    """Her real State on a copy of config_momoka.json with the named overlays merged in (a scratch db)."""
    from config import Config
    from store import Store
    from sim.state import State
    p = os.path.join(tmp, "c.json")
    write_json(p, read_json(LIVE))
    control.write_overrides(p, {}, list(overlays))
    with contextlib.redirect_stdout(io.StringIO()):
        cfg = Config(p)
        return State(cfg, Store(str(Path(tmp) / "w.db")), clock)


def silent_loneliness(overlays, hours=8, step=0.25):
    """Loneliness over `hours` virtual silent hours, one decay tick per `step` hours, starting at her baseline."""
    with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
        clock = _Clock(1_000_000.0)
        st = real_state(overlays, tmp, clock)
        base = st.config.state.gauges["loneliness"]["baseline"]
        st.gauges["loneliness"] = float(base)
        trace = []
        for i in range(1, int(round(hours / step)) + 1):
            clock.n += 3600 * step
            st.decay(i * step, {"usual_w": 1.0})
            trace.append(st.gauges["loneliness"])
        return base, trace, st


class HoldKey(unittest.TestCase):
    def test_default_is_off_and_live_config_does_not_carry_it(self):
        self.assertFalse(read_json(LIVE)["state"].get("loneliness_hold_when_silent", False))
        base, trace, st = silent_loneliness([])
        self.assertFalse(st.config.state.loneliness_hold_when_silent)

    def test_off_silence_never_leaves_baseline(self):
        """15-minute ticks: drift (2/h) beats the climb (1.5/h), so loneliness sits at baseline plus at most the
        climb of one tick (0.375) after each tick, never rising over 8 silent hours."""
        base, trace, _ = silent_loneliness([])
        self.assertEqual(base, 35)
        self.assertLessEqual(max(trace), base + 1.5 * 0.25 + 1e-9, trace)
        self.assertLessEqual(trace[-1], base + 1.5 * 0.25 + 1e-9)

    def test_off_hourly_ticks_plateau_one_climb_above_baseline(self):
        """With one tick per hour the order drift-then-climb leaves 36.5 after each tick (35 + 1.5), flat from the
        third silent hour: no accumulation."""
        base, trace, _ = silent_loneliness([], step=1.0)
        self.assertEqual(trace, [35.0, 35.0] + [36.5] * 6)

    def test_on_silence_rises_by_the_climb(self):
        base, trace, st = silent_loneliness(["lonehold"])
        self.assertTrue(st.config.state.loneliness_hold_when_silent)
        # silent_hours over 2 (ticks 9..32 of 32) climb 1.5/h * 0.25 each: 24 ticks, 9 points
        self.assertAlmostEqual(trace[-1], base + 9.0, places=6)
        self.assertEqual(trace[7], base)       # up to 2.0 silent hours: drift only, already at rest
        self.assertEqual(trace, sorted(trace))
        self.assertGreater(trace[-1], base + 8)

    def test_on_hourly_ticks_climb_every_hour(self):
        base, trace, _ = silent_loneliness(["lonehold"], step=1.0)
        self.assertEqual(trace, [35.0, 35.0] + [35.0 + 1.5 * i for i in range(1, 7)])

    def test_on_does_not_hold_when_he_is_talking(self):
        """silent_hours <= 2: the drift runs as before, so a raised loneliness still comes down."""
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            clock = _Clock(1_000_000.0)
            st = real_state(["lonehold"], tmp, clock)
            st.gauges["loneliness"] = 60.0
            clock.n += 3600
            st.decay(1, {"usual_w": 1.0})
            self.assertEqual(st.gauges["loneliness"], 58.0)     # 2/h drift

    def test_appraisal_overlay_holds_too(self):
        base, trace, _ = silent_loneliness(["appraisal"])
        self.assertAlmostEqual(trace[-1], base + 9.0, places=6)

    def test_midtags_alone_does_not_hold(self):
        base, trace, _ = silent_loneliness(["midtags"])
        self.assertLessEqual(max(trace), base + 1.5 * 0.25 + 1e-9)


class MidTags(unittest.TestCase):
    def tags_at(self, overlays, **gauges):
        with tempfile.TemporaryDirectory(dir=TMPDIR, ignore_cleanup_errors=True) as tmp:
            st = real_state(overlays, tmp, _Clock(1_000_000.0))
            for k, v in gauges.items():
                st.gauges[k] = float(v)
            out = st.mood_tags(ja=True)
            return out if isinstance(out, str) else ", ".join(out)

    def test_mid_tag_fires_in_its_band_only_with_the_overlay(self):
        for ov in ("appraisal", "midtags"):
            self.assertIn(ANX_MID, self.tags_at([ov], anxiety=50), ov)
            self.assertIn(ANGER_MID, self.tags_at([ov], anger=15), ov)
            self.assertIn(BORED_MID, self.tags_at([ov], boredom=40), ov)
            self.assertIn(EN_MID, self.tags_at([ov], energy=48), ov)
        for kw in ({"anxiety": 50}, {"anger": 15}, {"boredom": 40}, {"energy": 48}):
            t = self.tags_at([], **kw)
            for s in (ANX_MID, ANGER_MID, BORED_MID, EN_MID):
                self.assertNotIn(s, t, kw)
        # lonehold carries no tags
        t = self.tags_at(["lonehold"], anxiety=50, anger=15, boredom=40, energy=48)
        for s in (ANX_MID, ANGER_MID, BORED_MID, EN_MID):
            self.assertNotIn(s, t)

    def test_mid_tag_silent_at_rest_and_just_below_its_line(self):
        t = self.tags_at(["appraisal"], anxiety=40, anger=8, boredom=30, energy=60)
        for s in (ANX_MID, ANGER_MID, BORED_MID, EN_MID):
            self.assertNotIn(s, t)
        t = self.tags_at(["appraisal"], anxiety=44, anger=11, boredom=35, energy=53)
        for s in (ANX_MID, ANGER_MID, BORED_MID, EN_MID):
            self.assertNotIn(s, t)

    def test_mid_does_not_shadow_a_higher_tag(self):
        t = self.tags_at(["appraisal"], anxiety=75)
        self.assertIn(ANX_HI, t)
        self.assertNotIn(ANX_MID, t)
        t = self.tags_at(["appraisal"], anger=30)
        self.assertIn(ANGER_25, t)
        self.assertNotIn(ANGER_MID, t)
        t = self.tags_at(["appraisal"], anger=50)
        self.assertIn(ANGER_45, t)
        self.assertNotIn(ANGER_25, t)
        self.assertNotIn(ANGER_MID, t)
        t = self.tags_at(["appraisal"], energy=25)
        self.assertIn(EN_LOW, t)
        self.assertNotIn(EN_MID, t)

    def test_each_gauge_renders_one_tag(self):
        """The most extreme fitting tag wins, no more: at anxiety 90 exactly one of the two anxiety texts shows."""
        t = self.tags_at(["appraisal"], anxiety=90, energy=10, anger=60)
        self.assertEqual((t.count(ANX_HI), t.count(ANX_MID)), (1, 0))
        self.assertEqual((t.count(EN_LOW), t.count(EN_MID)), (1, 0))

    def test_overlay_lists_carry_the_live_tags(self):
        live = read_json(LIVE)["state"]["gauges"]
        for ov in ("appraisal", "midtags"):
            gs = control.load_overlay(ov)["state"]["gauges"]
            self.assertEqual(set(gs), {"anxiety", "anger", "boredom", "energy"}, ov)
            for g, body in gs.items():
                self.assertEqual(set(body), {"tags"}, (ov, g))
                kept = [t for t in body["tags"] if t in (live[g].get("tags") or [])]
                self.assertEqual(kept, live[g].get("tags") or [], (ov, g))        # every live tag, same order
                self.assertEqual(len(body["tags"]), len(kept) + 1, (ov, g))       # plus exactly one new mid tag
        self.assertEqual(control.load_overlay("appraisal")["state"]["gauges"],
                         control.load_overlay("midtags")["state"]["gauges"])


class Overlays(unittest.TestCase):
    def test_registered_as_variants_and_keys(self):
        for ov in OVERLAYS:
            self.assertIn(ov, branch.OVERLAY_VARIANTS)
        self.assertEqual(control.load_overlay("lonehold"), {"state": {"loneliness_hold_when_silent": True}})
        self.assertIs(control.load_overlay("appraisal")["state"]["loneliness_hold_when_silent"], True)
        self.assertNotIn("loneliness_hold_when_silent", control.load_overlay("midtags")["state"])


if __name__ == "__main__":
    unittest.main()
