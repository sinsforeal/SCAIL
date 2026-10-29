"""The 2026-08-26 midday layer, on a copy of the save, no LLM: blends,
the reverse body-noise line, the body-settled correction, wet exposure,
the surprise register, and facts about people with a curve.

    python tools/gaps_test.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import harness  # noqa: E402
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logger
logger.setup = lambda out_dir: None
logger.log = lambda m, to_console=True: print("   log:", m[:110])



def main():
    tmp = os.path.join(tempfile.gettempdir(), "scail_gaps.db")
    app = harness.build_on(tmp)
    st, mem, body = app.state, app.memory, app.body
    fails = []

    def check(label, ok):
        print(("  ok   " if ok else "  FAIL ") + label)
        if not ok:
            fails.append(label)

    base = {k: float(v["baseline"]) for k, v in app.config.state.gauges.items()}
    # --- blends
    for k in st.gauges:
        if k in base:
            st.gauges[k] = base[k]
    st.gauges["longing"], st.gauges["anger"] = 50, 60
    b = st.blends()
    check(f"longing 50 + anger 60 names a blend: {b[:1]}", any("furious" in x for x in b))
    check("a blend reaches the mood tags", "mixed" in st.mood_tags())
    st.gauges["longing"], st.gauges["anger"] = base["longing"], base["anger"]
    check("nothing mixed at rest", not st.blends())
    # --- reverse misattribution
    st.gauges["hunger"], st.gauges["energy"], st.gauges["unwell"], st.gauges["physical_comfort"] = 20, 70, 0, 65
    st.gauges["anxiety"] = base["anxiety"] + 40
    line = st.body_noise_line()
    check(f"wound-up head, body at rest -> reads as the body: {line[:40]!r}", line.startswith("HER HEAD IS IN HER BODY"))
    st.gauges["anxiety"] = base["anxiety"]
    check("no reverse line when calm", not st.body_noise_line())
    # --- the correction
    st.store.set("body_noise_prev", {})
    st.store.set("body_settled_note", {})
    st.gauges["hunger"], st.gauges["energy"] = 90, 20
    n1 = st.body_noise()
    st._body_settle_check()
    st.gauges["anger"] = 60
    st.gauges["hunger"], st.gauges["energy"] = 10, 75
    n2 = st.body_noise()
    st._body_settle_check()
    check(f"noise {n1:.2f} -> {n2:.2f} takes some anger off (now {st.gauges['anger']:.0f})", n1 >= 0.25 and n2 <= 0.12 and st.gauges["anger"] < 60)
    check("anger settles toward rest, never past it", st.gauges["anger"] >= base["anger"])
    note = st.body_settled_line()
    check("the state call is told once", note.startswith("HER BODY HAS JUST COME RIGHT"))
    check("...and only once", not st.body_settled_line())
    st.gauges["hunger"], st.gauges["energy"] = 90, 20
    st._body_settle_check()
    st.gauges["hunger"], st.gauges["energy"] = 10, 75
    a0 = st.gauges["anger"]
    st._body_settle_check()
    check("cooldown: a second settle inside 4h does nothing", st.gauges["anger"] == a0)
    # --- wet exposure
    d = app.clock.date_str()
    before = (st.store.get("exposure", {}) or {}).get(d, 0)
    body.note_wet(0.5, soaked=True)
    after = (st.store.get("exposure", {}) or {}).get(d, 0)
    check(f"half an hour soaked = {after - before:.2f} exposure hours", abs((after - before) - 1.0) < 1e-6)
    body.note_wet(0.5, soaked=False)
    check("with an umbrella it is just the half hour", abs((st.store.get("exposure", {})[d] - after) - 0.5) < 1e-6)
    # --- surprise
    st.gauges["surprise"] = 50
    st.gauges["affection"] = 60
    for k in ("awkwardness", "shame"):
        st.gauges[k] = base[k]
    reg = st.register()
    check(f"surprise 50 reaches the register: {reg[:30]!r}", reg.startswith("caught off guard"))
    check("...and the mood tags", "off guard" in st.mood_tags())
    st.gauges["surprise"] = base["surprise"]
    check("surprise has no valence but has arousal", app.config.state.gauges["surprise"]["valence"] == 0 and st.affect("arousal") is not None)
    # --- facts about people
    # one key per person, through the roster: the value is the roster key, and
    # what matters is that every form of her name lands on the same one
    check(f"who_key resolves every form of her to one key ({mem.who_key('rena')})",
          mem.who_key("Rena-chan") == mem.who_key("rena") == mem.who_key("香芝玲奈") == "rena-chan")
    check("...and her mother, whom it used to miss entirely",
          mem.who_key("mom") == mem.who_key("古賀由美") == "mom")
    check("...while a stranger keeps the plain normalisation",
          mem.who_key("レジの人") == "レジの人" and mem.who_key("Some Teacher-san") == "some")
    r1 = mem.add_cast_fact("Rena-chan", "Rena's older brother is repeating a year at his university", 3)
    r2 = mem.add_cast_fact("Rena", "Rena's older brother is repeating a year at university", 2)
    check(f"first is new, the near-duplicate reinforces ({r1}, {r2})", r1 == "new" and r2 == "reinforced")
    mem.add_cast_fact("Aya", "Aya cannot eat natto", 2)
    got = mem.cast_facts_for("rena")
    check(f"she has it in front of her under either name: {got}", any("brother" in x for x in got) and not any("natto" in x for x in got))
    lines = mem.cast_lines(st.relationships)
    check("the persona's people lines carry what she knows", any("what you know about them" in l for l in lines))
    rep = mem.cast_facts_report()
    check("/cast report lists it with a score", "brother" in rep and "w3" in rep)
    # a faded fact comes back on a cue
    with st.store.lock:
        st.store.conn.execute("UPDATE cast_facts SET ts=?, last_seen=? WHERE fact LIKE '%natto%'",
                              (app.clock.now_ts() - 400 * 86400,) * 2)
        st.store.conn.commit()
    check("400 days on, weight 2 is out of her prompt",
          not any("natto" in x for x in mem.cast_facts_for("Aya")))
    check("...until natto comes up", any("natto" in x for x in mem.cast_facts_for("Aya", cue_text="want natto for breakfast")))
    print(f"\n{len(fails)} failure(s)" if fails else "\nall ok")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
