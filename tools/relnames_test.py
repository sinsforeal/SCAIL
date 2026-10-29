"""The state model's relationship moves land on the right person, whatever
name it wrote them under.

The state role is shown the exchange it has just read, and in that transcript
everybody is named as the record names them (香芝玲奈, 古賀海斗). It keys its
relationship deltas the same way. Her meters are keyed by the roster handle
(`Rena-chan`, `Kaito`), and `State._match_person` used to resolve a name by
lowercasing it and stripping `-chan`, which matched the handle and nothing
else. Every move under a Japanese name was dropped with no log line.

This runs against a copy of the live save and the real `data/cast.json`, so
the names it tries are the names the model actually sees.

    python tools/relnames_test.py
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import harness  # noqa: E402
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logger
logger.setup = lambda out_dir: None
logger.log = lambda m, to_console=True: None

from sim import roster


def old_match(relationships, name):
    """What `_match_person` did before 2026-09-01, kept here so the test says
    what it is guarding against rather than only that it passes."""
    n = name.lower().replace("-chan", "").replace("-san", "").strip()
    for p in relationships:
        if p.lower().replace("-chan", "") == n:
            return p
    if n in ("user", "he", "him", "the user"):
        return "him"
    return None


def every_name(cast):
    """Every string the record could call each person by, from the data:
    the roster key, the Japanese name, the reading, the display name, the
    explicit aliases, and what everyone else's `calls` entries use."""
    people = cast.get("people", {})
    nick = {}
    for person in people.values():
        for whose, called in (person.get("calls") or {}).items():
            nick.setdefault(whose, set()).add(called)
    out = {}
    for key, p in people.items():
        forms = {key, p.get("ja"), p.get("reading"), p.get("name")}
        forms |= set(p.get("aliases") or ())
        forms |= nick.get(key, set())
        out[key] = sorted(f for f in forms if f)
    return out


def main():
    tmp = os.path.join(tempfile.gettempdir(), "scail_relnames.db")
    app = harness.build_on(tmp)
    st = app.state
    fails = []

    def check(label, ok):
        print(("  ok   " if ok else "  FAIL ") + label)
        if not ok:
            fails.append(label)

    with open(app.config.character.cast_file, "r", encoding="utf-8") as f:
        cast = json.load(f)
    forms = every_name(cast)

    # --- 1. every name for a person resolves to that person's meters
    print("\n-- every name in data/cast.json resolves to the right meters")
    missed_old = []
    for key, names in forms.items():
        if key not in st.relationships:
            continue
        wrong = []
        for n in names:
            got = st._match_person(n)
            if got != key:
                wrong.append(f"{n} -> {got}")
            if old_match(st.relationships, n) != key:
                missed_old.append(f"{key}:{n}")
        check(f"{key}: {len(names)} names, all resolve" + (f" -- WRONG: {wrong}" if wrong else ""), not wrong)
    print(f"   the old lowercase-and-strip matcher missed {len(missed_old)} of these: {missed_old}")
    check("the old matcher missed names the roster resolves (this is the bug)", bool(missed_old))

    # --- 2. a delta keyed by the record's Japanese name moves the meter
    print("\n-- a move keyed by the Japanese record name lands")
    for key in ("Rena-chan", "Kaito", "mom", "dad"):
        rec_name = roster.record_name(app.config, key)
        if not rec_name or rec_name == key or key not in st.relationships:
            continue
        st.store.set("rel_delta_spent", {"_date": app.clock.date_str()})
        before = float(st.relationships[key].get("closeness", 50))
        st.apply({}, {rec_name: {"closeness": 2}})
        after = float(st.relationships[key].get("closeness", 50))
        check(f"{rec_name} +2 closeness moved {key}: {before} -> {after}", after == before + 2)
        st.relationships[key]["closeness"] = before

    # --- 3. him still resolves under every word the model uses for him
    print("\n-- him")
    him = st._him_key()
    for n in ("him", "user", "the user", "he"):
        check(f"{n!r} -> {him}", st._match_person(n) == him)

    # --- 4. a name nobody owns stays nobody
    print("\n-- a stranger is not folded into somebody real")
    # Miki and Yuzu are the two girls a stale string literal in the day's
    # skeleton invented; the model has since keyed moves to both. They must
    # resolve to nothing, not to the nearest real classmate.
    for n in ("Miki", "Yuzu", "レジの人", "the teacher", "Tomoe", "her"):
        got = st._match_person(n)
        check(f"{n!r} owns no meters (got {got})", got is None)

    # --- 5. the per-day budget still holds on the Japanese name
    print("\n-- the daily budget is not bypassed by the new spelling")
    key = "Rena-chan"
    rec_name = roster.record_name(app.config, key)
    budget = int(app.config.state.relationship_daily_budget)
    st.store.set("rel_delta_spent", {"_date": app.clock.date_str()})
    before = float(st.relationships[key].get("closeness", 50))
    for _ in range(20):
        st.apply({}, {rec_name: {"closeness": 3}})
    moved = float(st.relationships[key].get("closeness", 50)) - before
    check(f"twenty +3 moves under {rec_name} spent {moved:.0f}, budget {budget}", abs(moved) <= budget)
    st.relationships[key]["closeness"] = before

    print()
    if fails:
        print(f"FAILED {len(fails)}:")
        for f_ in fails:
            print("  - " + f_)
        return 1
    print("all good")
    return 0


if __name__ == "__main__":
    sys.exit(main())
