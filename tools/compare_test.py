"""Social comparison without the model: who counts as a peer, who is
present, the pressure, the gates, the effects of a fired comparison, and
the envy readers. On a copy of the save.

    python tools/compare_test.py
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
    tmp = os.path.join(tempfile.gettempdir(), "scail_compare.db")
    app = harness.build_on(tmp)
    cm, st, sen = app.compare, app.state, app.sentiments
    fails = []

    def check(label, ok):
        print(("  ok   " if ok else "  FAIL ") + label)
        if not ok:
            fails.append(label)

    peers = cm.peers()
    check(f"peers are the circle, not family or him: {peers}", "Rena-chan" in peers and "mom" not in peers and "dad" not in peers and "Kaito" not in peers and "him" not in peers)
    scene = {"with_who": "Rena and Hinako, on the platform", "sensory": "", "inner": ""}
    check(f"present() from a scene: {cm.present(scene)}", set(cm.present(scene)) == {"Rena-chan", "Hinako"})
    talk = {"who": "group", "turns": [{"who": "Aya", "text": "hi"}, {"who": "Tomoe", "text": "hey"}]}
    check(f"present() from a talk: {cm.present(None, talk)}", cm.present(None, talk) == ["Aya"])
    check("nobody present -> not eligible", cm.eligible({"with_who": "alone"})[0] is False)
    st.store.set("compare_counts", {})
    st.store.set("compare_last_ts", 0)
    ok, why, who = cm.eligible(scene)
    check(f"peers present, no cap, no cooldown -> eligible ({why})", ok)
    p0 = cm.pressure()
    base = {k: float(v["baseline"]) for k, v in app.config.state.gauges.items()}
    st.gauges["validation_craving"], st.gauges["shame"] = 90, 70
    p1 = cm.pressure()
    check(f"craving and shame raise the pressure {p0:.2f} -> {p1:.2f}", p1 > p0)
    st.gauges["validation_craving"], st.gauges["shame"] = base["validation_craving"], base["shame"]
    st.store.set("compare_counts", {app.clock.date_str(): 2})
    check("daily cap holds", cm.eligible(scene)[1] == "daily cap")
    st.store.set("compare_counts", {})
    st.store.set("compare_last_ts", app.clock.now_ts() - 600)
    check("cooldown holds", cm.eligible(scene)[1] == "cooldown")
    # effects
    e0 = sen.live("Rena-chan", "envy")
    sh0, pr0 = st.gauges["shame"], st.gauges["pride"]
    b0 = app.model_of_her.get("plain_underneath")
    s0 = app.model_of_her.live_strain(b0) if b0 else None
    moved = cm.apply("Rena-chan", "looks", "up", 0.6, "plain_underneath", "her legs. mine.")
    e1 = sen.live("Rena-chan", "envy")
    b1 = app.model_of_her.get("plain_underneath")
    s1 = app.model_of_her.live_strain(b1) if b1 else None
    check(f"upward: envy {e0:.0f} -> {e1:.0f}, shame {sh0:.0f} -> {st.gauges['shame']:.0f} ({moved})", e1 > e0 and st.gauges["shame"] > sh0)
    check(f"...and the self-belief it landed on is strained {s0} -> {s1}", s1 is not None and s0 is not None and s1 > s0)
    moved = cm.apply("Hinako", "grades", "down", 0.5, "", "at least i passed")
    check(f"downward: pride {pr0:.0f} -> {st.gauges['pride']:.0f} ({moved})", st.gauges["pride"] > pr0)
    check("envy is in the sentiment prompt text", "measuring yourself against" in sen.prompt_text() or e1 < app.config.sentiment.prompt_from)
    # the spiral seed reads envy
    # Seedability is envy PLUS how unsettled her standing is with each person,
    # and on the live save Rena and Hinako sit 20-30 below the settled line, so
    # they outweigh a maxed-out envy on Aya by standing alone. That is the
    # world being true, not the mechanism being wrong: settle the others so the
    # check measures what it says it measures.
    sen.set_level("Aya", "envy", 90)
    app.spirals.sentiments = sen
    settled = float(app.config.spiral.standing_settled_at)
    for nm, rel in (st.relationships or {}).items():
        if nm not in ("him", "Aya") and isinstance(rel, dict):
            rel["standing"], rel["tension"] = max(float(rel.get("standing", 50)), settled), 0
    best, w = app.spirals.seedability()
    check(f"envy makes Aya seedable: {best} {w:.2f}", best == "Aya" and w >= 0.3)
    print(cm.report(scene))
    print(f"\n{len(fails)} failure(s)" if fails else "\nall ok")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
