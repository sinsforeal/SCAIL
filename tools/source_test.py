"""Emotions have a source (State.sources / directed_line) and a held gauge
dulls instead of freezing (rupture.hold_decay_factor / hold_floor). On a
copy of the save."""
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import harness  # noqa: E402
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    tmp = os.path.join(tempfile.gettempdir(), "scail_source.db")
    app = harness.build_on(tmp)
    st, store = app.state, app.store
    fails = []

    def check(label, ok):
        print(("  ok   " if ok else "  FAIL ") + label)
        if not ok:
            fails.append(label)

    him = st._him_key() or "him"
    rc = app.config.rupture
    base = float(app.config.state.gauges["anger"]["baseline"])
    # ---- the hold: an open rupture on file, anger at 81, a night passes
    # the hold needs an open rupture; whether the live save happens to have one
    # today is not what this is testing, so make one when there is none
    r = app.ruptures.open_one()
    if not r:
        rows = app.ruptures.all()
        rows.append({"id": "test-0", "date": app.clock.date_str(), "ts": app.clock.now_ts(), "what": "test rupture", "state": "open", "severity": 1.0})
        app.ruptures.save(rows)
        r = app.ruptures.open_one()
    check(f"an open rupture is on file ({r and r['id']}) holding {list(rc.holds_gauges)}",
          bool(r) and "anger" in rc.holds_gauges)
    st.gauges["anger"] = 81.0
    st.last_decay_ts = app.clock.now_ts() - 8 * 3600
    st.decay(0, {"asleep": True})
    a = st.gauges["anger"]
    floor = base + rc.hold_floor
    expect = max(floor, 81 - 8 * app.config.state.gauges["anger"]["decay_per_hour"] * rc.hold_decay_factor)
    check(f"held anger dulls over 8 h: 81 -> {a:.1f} (expected {expect:.1f}, floor {floor:.0f})", abs(a - expect) < 0.5 and a < 81)
    st.gauges["anger"] = floor - 5
    st.last_decay_ts = app.clock.now_ts() - 8 * 3600
    st.decay(0, {"asleep": True})
    check(f"...and below the floor it is not pushed back up ({st.gauges['anger']:.1f})", st.gauges["anger"] <= floor - 5 + 0.01)
    st.gauges["anger"] = 81.0
    st.last_decay_ts = app.clock.now_ts() - 48 * 3600
    st.decay(0, {})
    check(f"two days held: it stops at the floor, {st.gauges['anger']:.1f} == {floor:.0f}", abs(st.gauges["anger"] - floor) < 0.01)
    # ---- the source: the rupture aims anger at him
    st.gauges["anger"] = 70.0
    st.gauges["sadness"] = 60.0
    src = st.sources()
    check(f"sources(): anger -> {src.get('anger', ('?',))[0]}", src.get("anger", ("",))[0] == him)
    line = st.directed_line("Rena-chan")
    check("directed_line(Rena-chan) says NOT AT RENA-CHAN and names him", "NOT AT RENA-CHAN" in line and "him" in line)
    check("...and says it shows as being elsewhere, never as an edge on them", "never as an edge" in line)
    check("directed_line(him) says AT HIM and nothing is elsewhere", "AT HIM" in st.directed_line(him).upper() and "NOT AT" not in st.directed_line(him))
    # ---- a sentiment aims it at a friend
    sen = app.sentiments
    sen.set_level("Hinako", "resentment", 60)
    rows = app.ruptures.all()
    for row in rows:
        if row.get("state") == "open":
            row["state"] = "scarred"
    app.ruptures.save(rows)
    store.set("withholding", {"done": True})
    src = st.sources()
    check(f"no rupture, resentment of Hinako 60: anger -> {src.get('anger', ('?',))[0]}", src.get("anger", ("",))[0] == "Hinako")
    check("directed_line(Hinako) says AT HINAKO", "AT HINAKO" in st.directed_line("Hinako"))
    check("directed_line(Rena-chan) says it is at Hinako, not her", "NOT AT RENA-CHAN" in st.directed_line("Rena-chan") and "Hinako" in st.directed_line("Rena-chan"))
    pl = app.persona._directed()
    check(f"the persona (to him) is told the anger is at Hinako: {pl[:70]}", "Hinako" in pl and "not at him" in pl)
    st.gauges["anger"] = 10.0
    check("anger under min_level has no source", "anger" not in st.sources())
    print(f"\n{len(fails)} failure(s)" if fails else "\nall ok")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
