"""A gauge at its end does something and resets, without the model: the
rules fire at their levels, reset to a level not to rest, hold a
cooldown and a daily cap, an `act` writes an event with side effects and
a stress release, and the next tick is handed the event. On a copy of
the save.

    python tools/discharge_test.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import harness  # noqa: E402
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logger
logger.setup = lambda out_dir: None
logger.log = lambda m, to_console=True: print("   log:", m[:120])



def main():
    tmp = os.path.join(tempfile.gettempdir(), "scail_discharge.db")
    app = harness.build_on(tmp)
    dc, st, store = app.discharge, app.state, app.store
    fails = []

    def check(label, ok):
        print(("  ok   " if ok else "  FAIL ") + label)
        if not ok:
            fails.append(label)

    base = {k: float(v["baseline"]) for k, v in app.config.state.gauges.items()}
    for k in st.gauges:
        if k in base:
            st.gauges[k] = base[k]
    store.set("discharge_last", {})
    store.set("discharge_counts", {})
    store.set("discharges", [])
    check("nothing at rest fires", dc.check({}) == [])
    check(f"{len(dc.rules())} rules, every gauge real", all(r["gauge"] in st.gauges for r in dc.rules()))
    # sadness at its end: an act
    st.gauges["sadness"] = 95
    r0 = st.gauges["relief"]
    fired = dc.check({})
    check(f"sadness 95 fires: {[f['gauge'] for f in fired]}", [f["gauge"] for f in fired] == ["sadness"])
    check(f"...and resets to a level, not rest: {st.gauges['sadness']:.0f}", st.gauges["sadness"] == 55)
    text = dc.act(fired[0])
    check(f"the act: {text[:50]}", "cried" in text and st.gauges["relief"] > r0)
    evs = [e for e in store.events_for_date(app.clock.date_str()) if e["kind"] == "discharge"]
    check("an event of salience 3 on the record", any(e["salience"] == 3 and "cried" in e["text"] for e in evs))
    take = dc.take()
    check("the next tick is handed it once", len(take) == 1 and dc.take() == [])
    check("recorded", any(x["gauge"] == "sadness" and x["did"] == "act" for x in store.get("discharges", [])))
    # cooldown
    st.gauges["sadness"] = 96
    check("cooldown: not again inside 4h", dc.check({}) == [] and st.gauges["sadness"] == 96)
    st.gauges["sadness"] = base["sadness"]
    # asleep: nothing fires
    st.gauges["anger"] = 99
    check("asleep: nothing fires", dc.check({}, asleep=True) == [] and st.gauges["anger"] == 99)
    # say rule: check() fires it; the App decides how it is carried out
    fired = dc.check({})
    check(f"anger 99 fires a `say`: {fired[0]['action'] if fired else None}, reset {st.gauges['anger']:.0f}", fired and fired[0]["action"] == "say" and st.gauges["anger"] == 62)
    # without a phone the App falls back to the act
    app.phone_access = lambda: "none"
    st.gauges["unsaid"] = 97
    before = len(store.get("discharges", []))
    app.maybe_discharge({"location": "class"})
    rows = store.get("discharges", [])
    check(f"no phone -> unsaid `say` falls back to the act: {rows[-1]['did'] if rows else None}", len(rows) == before + 1 and rows[-1]["did"].startswith("act") and st.gauges["unsaid"] == 45)
    # daily cap
    store.set("discharge_last", {})
    for g in ("stress", "shame", "jealousy", "boredom"):
        st.gauges[g] = 99
    fired = dc.check({})
    check(f"daily cap {app.config.state.discharge.max_per_day}: fired {len(fired)} of 4 with {before + 1} already today", len(fired) + before + 1 <= app.config.state.discharge.max_per_day + 0 or len(fired) < 4)
    print(dc.report())
    print(f"\n{len(fails)} failure(s)" if fails else "\nall ok")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
