"""Her face in the app (sim/reactions.py): one reaction each time her mood
crosses a band, the face chosen by what is up, never the same image inside
`repeat_days`. On a copy of the save, against the real reactions.db."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import harness  # noqa: E402
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    tmp = os.path.join(tempfile.gettempdir(), "scail_reaction.db")
    app = harness.build_on(tmp)
    rx, st, store = app.reactions, app.state, app.store
    fails = []

    def check(label, ok):
        print(("  ok   " if ok else "  FAIL ") + label)
        if not ok:
            fails.append(label)

    # her face only moves while he is about (`reactions.active_minutes`, added
    # 2026-08-28): without a message of his inside the window every tick
    # returns None and every assertion below fails on a premise the test never
    # built. He is here for the duration of this run.
    app.store.add_message(app.clock.now_ts(), app.clock.date_str(), "user", "test: he is at his machine")

    base = float(app.config.state.gauges["mood"]["baseline"])
    swing = app.config.state.mood_from.max_swing
    for k in ("anger", "sadness", "anxiety", "awkwardness", "shame", "surprise", "fatigue"):
        st.gauges[k] = 0
    st.gauges["energy"] = 60
    st.gauges["mood"] = base
    store.set("reaction_band", None)
    store.set("reaction_last", {})
    store.set("reactions_log", [])
    cnt = rx.counts()
    check(f"database read: {sum(cnt.values())} images in {len(cnt)} buckets", sum(cnt.values()) > 100 and "happy" in cnt)
    check("first tick after a boot only records the band", rx.tick() is None and store.get("reaction_band") == 0)
    check("a steady mood shows nothing", rx.tick() is None)
    st.gauges["mood"] = base + 0.5 * swing
    rec = rx.tick()
    check(f"mood up a band -> a face: {rec and rec['bucket']} #{rec and rec['id']} ({rec and rec['why']})", bool(rec) and rec["bucket"] == "happy")
    check("...copied for the hub", bool(rec) and os.path.exists(os.path.join(rx.out_dir, rec["file"])))
    check("...and current() hands it to the app", (rx.current() or {}).get("file") == (rec or {}).get("file"))
    check("same band again: nothing", rx.tick() is None)
    # the gap: a second crossing right away is swallowed
    st.gauges["mood"] = base - 0.5 * swing
    st.gauges["anger"] = 80
    check("a crossing inside min_gap_minutes shows nothing", rx.tick() is None)
    last = dict(store.get("reaction_last") or {})
    last["wall"] = last.get("wall", 0) - 3600
    store.set("reaction_last", last)
    store.set("reaction_band", 2)
    rec2 = rx.tick()
    check(f"mood down with anger 80 -> angry: {rec2 and rec2['bucket']}", bool(rec2) and rec2["bucket"] == "angry")
    st.gauges["anger"] = 0
    st.gauges["sadness"] = 70
    check("bucket_for: sadness at the floor -> sad", rx.bucket_for(-2) == "sad")
    st.gauges["sadness"] = 0
    st.gauges["energy"] = 20
    check("bucket_for: no energy at the floor -> tired", rx.bucket_for(-2) == "tired")
    st.gauges["energy"] = 60
    st.gauges["anxiety"] = 70
    check("bucket_for: anxiety in the off band -> nervous", rx.bucket_for(-1) == "nervous")
    st.gauges["anxiety"] = 0
    st.gauges["surprise"] = 50
    check("bucket_for: surprise over the line wins any band", rx.bucket_for(1) == "surprised")
    # surprise is its own crossing
    last = dict(store.get("reaction_last") or {})
    last["wall"] = last.get("wall", 0) - 3600
    last["surprised"] = False
    store.set("reaction_last", last)
    rec3 = rx.tick()
    check(f"surprise crossing -> a face without a band change: {rec3 and rec3['bucket']}", bool(rec3) and rec3["wanted"] == "surprised")
    st.gauges["surprise"] = 0
    # the repeat rule
    seen = {x["id"] for x in store.get("reactions_log")}
    picks = {rx.pick("happy")["id"] for _ in range(30)}
    check(f"pick never repeats a shown image inside repeat_days ({len(picks)} distinct)", not (picks & seen))
    forced = rx.tick(force_bucket="tired", why="test")
    check(f"forced bucket: {forced and forced['bucket']}", bool(forced) and forced["bucket"] == "tired")
    check("report reads", "reactions:" in rx.report() and "showing:" in rx.report())
    check("clear() empties current()", rx.clear() and rx.current() is None)
    print(f"\n{len(fails)} failure(s)" if fails else "\nall ok")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
