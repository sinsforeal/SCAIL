"""Does every end of stress actually reach something.

Six compounds and eight relief kinds. A compound nothing reads and a relief
nothing calls are the same fault as a gauge nothing reads, and the only way to
know is to move the gauge and watch something else change. This moves stress
between 10 and 90 and asserts that each of the six named readers answers
differently, then fires each of the eight releases twice in a row and asserts
the second one does nothing.

It needs no LLM and no prompts, and it runs against a copy of the save.

    python tools/stress_test.py

Written after the wiring was found half-done: the integrator had been running
in State.decay since the day stress shipped, and not one of the fourteen ends
had a caller. Two things it caught immediately are the reason it exists --
`relief_gap_minutes` was a Section rather than a dict, so relieve() raised on
its first call, and the sleep_cost multiplier was being applied underneath
mind_pen_max, where a night stressful enough to matter had already saturated
the cap and the reader could not change the score.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.dbcopy import copy_db  # noqa: E402

import logger

logger.log = lambda m: None
logger.log_llm = lambda *a, **k: None

from config import Config
from store import Store
from world.clock import WorldClock
from embodied.health import Health
from sim.impulse import Impulse
from sim.memory import Memory
from sim.model_of_her import ModelOfHer
from sim.spiral import Spirals
from sim.state import State
from sim.stress import Stress

LOW, HIGH = 10.0, 90.0
_fails = []


def main():
    db = os.path.join(tempfile.gettempdir(), "stress_test.db")
    copy_db(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "world.db"), db)

    c = Config("config.json")
    store = Store(db)
    clock = WorldClock(c)
    st = State(c, store, clock)
    her = ModelOfHer(c, None, store, clock, Memory(c, store, clock))
    s = Stress(c, store, clock, st, None, None, None, None, None, None, None, her, None)
    st.stress = s

    def at(level, fn):
        st.gauges["stress"] = level
        return fn()

    def show(label, lo, hi, up=True):
        ok = (hi > lo + 1e-9) if up else (hi < lo - 1e-9)
        if not ok:
            _fails.append(label)
        print(f"  {label:14s} stress {LOW:.0f} -> {lo:<9.3f}  stress {HIGH:.0f} -> {hi:<9.3f}  "
              + ("ok" if ok else "NOTHING READS IT"))

    print("=" * 84)
    print("THE SIX COMPOUNDS, AND WHAT EACH ONE REACHES")
    print("=" * 84)
    for k in c.stress.compounds:
        print(f"    {k:11s} x{at(LOW, lambda: s.multiplier(k)):.2f} at 10, "
              f"x{at(HIGH, lambda: s.multiplier(k)):.2f} at 90")
    print()

    # her body has to be worth misreading or the term is zero whatever stress is
    st.gauges["energy"], st.gauges["hunger"], st.gauges["physical_comfort"] = 25, 85, 30
    show("body_noise", at(LOW, st.body_noise), at(HIGH, st.body_noise))
    show("delay", at(LOW, st.delay_factor), at(HIGH, st.delay_factor))

    def warmed():
        st.gauges["shame"] = 5.0
        st._warm("shame", 10.0, 80.0)
        return st.gauges["shame"]

    def applied():
        st.gauges["shame"] = 5.0
        st.apply({"shame": 6}, {})
        return st.gauges["shame"]

    # both routes a gauge can be written by, because shame arrives either way
    show("shame(_warm)", at(LOW, warmed), at(HIGH, warmed))
    show("shame(apply)", at(LOW, applied), at(HIGH, applied))

    sp = Spirals(c, None, store, clock, st, None, her)
    show("spiral", at(LOW, sp._stress), at(HIGH, sp._stress))

    imp = Impulse(c, store, clock)
    scene = {"phone_access": "free", "with_who": "alone"}
    show("withdraw", at(LOW, lambda: imp.score(st, scene, 3.0)),
         at(HIGH, lambda: imp.score(st, scene, 3.0)), up=False)

    h = Health(c, store, clock, st, None, None)
    st.gauges["anxiety"], st.gauges["unsaid"] = 80, 90
    date = clock.date_str()

    def night():
        store.set("health_days", {})
        return h.night(date)["score"]

    show("sleep_cost", at(LOW, night), at(HIGH, night), up=False)

    print()
    print("=" * 84)
    print("THE EIGHT RELEASES, AND THE COOLDOWN THAT MAKES THEM DISCRETE")
    print("=" * 84)
    st.gauges["unsaid"], st.gauges["belonging"], st.gauges["energy"] = 95, 20, 25
    floor = s.target(0.0)
    print(f"  her load holds the floor at {floor:.0f}")
    for kind in c.stress.relief:
        store.set("stress_relief_ts", {})
        st.gauges["stress"] = 80.0
        s.relieve(kind)
        first = st.gauges["stress"]
        s.relieve(kind)
        again = st.gauges["stress"]
        moved = 80.0 - first
        if moved <= 0:
            _fails.append("relief:" + kind)
        if again != first:
            _fails.append("cooldown:" + kind)
        print(f"    {kind:18s} 80 -> {first:5.1f} (-{moved:4.1f})   straight away again -> {again:5.1f}  "
              + ("ok" if (moved > 0 and again == first) else "BROKEN"))

    store.set("stress_relief_ts", {})
    st.gauges["stress"] = floor + 2.0
    s.relieve("rupture_mended")
    print(f"\n  and never through the floor: {floor + 2.0:.0f} with a 16-point release -> "
          f"{st.gauges['stress']:.1f} (floor {floor:.0f})")
    if st.gauges["stress"] < floor - 1e-6:
        _fails.append("floor")

    print()
    if _fails:
        print(f"{len(_fails)} failed: {', '.join(_fails)}")
        sys.exit(1)
    print("every compound reaches something and every release fires once")


if __name__ == "__main__":
    main()
