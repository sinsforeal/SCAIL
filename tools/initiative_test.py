"""The gate on reaching out first, on a copy of a save, spending nothing.

    python tools/initiative_test.py                       # the second character
    python tools/initiative_test.py config.json data/world.db

Four things, in order: his coming back is rolled and often not taken; a run of
unanswered messages raises the bar and then stops her for the day; a discharge
and a stance that entered without waiting go through anyway and say so; and
what the gate is holding survives a rebuild of the App on the same file.

Every model call raises (`harness.refuse_model`), and the clock is driven by
hand so a whole day can be walked in a second.
"""
import datetime
import os
import random
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools import harness  # noqa: E402


NOW = [0.0]


def drive(clock):
    """The clock reads NOW[0]. Everything else on it -- her date, his hour,
    the stamps -- is derived from `now_ts`, so this is the only override."""
    clock.now_ts = lambda: NOW[0]
    return clock


def at(clock, hh, mm=0, day=0):
    d = datetime.datetime.now(tz=clock.user_tz).replace(hour=hh, minute=mm, second=0, microsecond=0)
    return (d + datetime.timedelta(days=day)).timestamp()


def clear(app):
    for k in ("initiative_away_since", "initiative_hold_until", "initiative_return",
              "initiative_unanswered_counts", "stance"):
        app.store.set(k, None)


def send(app, ts, text, self_started=1, read=True):
    """A message of hers on the record, exactly as delivery writes one."""
    app.store.add_message(ts, app.clock.date_str(ts), "assistant", text,
                          self_started=self_started, delivered_ts=ts,
                          read_ts=(ts + 120) if read else None)


def heard(app, ts, text="ok"):
    app.store.add_message(ts, app.clock.date_str(ts), "user", text)


# ---------------------------------------------------------------- 1. his return

def his_return(app, trials=10):
    ini = app.impulse.initiative
    print("\n=== his return after six hours away, ten trials at each hour ===")
    print("    (his clock; the roll is once, and a delay of minutes if she takes it)")
    for hh in (10, 15, 22):
        taken, delays, p_seen = 0, [], 0.0
        for _ in range(trials):
            clear(app)
            back = at(app.clock, hh)
            NOW[0] = back - 6 * 3600
            ini.observe_away(0, app.state)                 # he is here
            NOW[0] = back - 6 * 3600 + 46 * 60
            ini.observe_away(46 * 60, app.state)           # and now he is not
            NOW[0] = back
            ini.observe_away(3, app.state)                 # he touched something
            row = app.store.get("initiative_return", None) or {}
            hold = float(app.store.get("initiative_hold_until", 0) or 0)
            p_seen = float(row.get("p", 0.0))
            if row.get("due"):
                taken += 1
                delays.append((float(row["due"]) - back) / 60.0)
            else:
                assert hold > back, "a return she did not take must still hold her"
        d = f"delay {min(delays):.0f}-{max(delays):.0f} min" if delays else "she said nothing at all"
        print(f"  {hh:02d}:00  p={p_seen:.2f}  taken {taken}/{trials}, said nothing {trials - taken}/{trials}  {d}")

    print("\n  and what the gate says while a taken return is waiting on its delay:")
    while True:
        clear(app)
        back = at(app.clock, 15)
        NOW[0] = back - 6 * 3600
        ini.observe_away(0, app.state)
        NOW[0] = back - 6 * 3600 + 46 * 60
        ini.observe_away(46 * 60, app.state)
        NOW[0] = back
        ini.observe_away(3, app.state)
        if (app.store.get("initiative_return", None) or {}).get("due"):
            break
    print(f"    at his touch          : {ini.hold_reason(0, '') or '(open)'}")
    NOW[0] = back + 3 * 60
    print(f"    three minutes later   : {ini.hold_reason(0, '') or '(open)'}")
    NOW[0] = float(app.store.get("initiative_return")["due"]) + 1
    print(f"    when the delay is up  : {ini.hold_reason(0, '') or '(open)'}")

    print("\n  a return he came back from by writing to her is not rolled at all:")
    clear(app)
    back = at(app.clock, 11, day=1)
    NOW[0] = back - 6 * 3600
    ini.observe_away(0, app.state)
    NOW[0] = back - 6 * 3600 + 46 * 60
    ini.observe_away(46 * 60, app.state)
    heard(app, back - 60, "morning")
    NOW[0] = back
    ini.observe_away(3, app.state)
    print(f"    held: {ini.hold_reason(0, '') or '(open)'}")


# ---------------------------------------------------------------- 2. being ignored

def ignored(app):
    ini = app.impulse.initiative
    imp = app.impulse
    print("\n=== self-started messages he does not answer ===")
    clear(app)
    DAY = 2
    heard(app, at(app.clock, 8, 0, day=DAY), "last thing he said")

    n = 0
    for hh, mm in ((9, 0), (9, 30), (10, 30), (12, 0), (14, 0), (17, 0), (21, 0)):
        NOW[0] = at(app.clock, hh, mm, day=DAY)
        streak = imp.unanswered_streak()
        held = ini.hold_reason(streak, "read")
        print(f"\n  {hh:02d}:{mm:02d}  streak {streak}, he has read every one of them")
        if held:
            other = ini.hold_reason(streak, "delivered")
            print(f"    the gate holds -> {held}")
            print(f"    had he not opened them: {other or '(open, and she reaches out)'}")
            continue
        n += 1
        ini.note_sent(streak)
        send(app, NOW[0], f"message {n}")
        print(f"    she reaches out ({n}); self-starts into a silence of her own today: "
              f"{ini._unanswered_today()} of {app.config.impulse.max_unanswered_per_day}")

    print("\n  the day's cap is the backstop under the backoff:")
    app.store.set("initiative_unanswered_counts", {app.clock.date_str(): 3})
    NOW[0] = at(app.clock, 23, 59, day=DAY)
    print(f"    with three of hers unanswered today: {ini.hold_reason(imp.unanswered_streak(), 'read')}")

    print("\n  and his small hours, with nothing else holding her:")
    clear(app)
    NOW[0] = at(app.clock, 4, 30, day=DAY + 1)
    print(f"    04:30 where he is: {ini.hold_reason(0, '') or '(open)'}")
    NOW[0] = at(app.clock, 9, 0, day=DAY + 1)
    print(f"    09:00 where he is: {ini.hold_reason(0, '') or '(open)'}")


# ---------------------------------------------------------------- 3. through it anyway

def overrides(app):
    ini = app.impulse.initiative
    imp = app.impulse
    print("\n=== what goes through a closed gate ===")
    clear(app)
    NOW[0] = at(app.clock, 12, day=4)
    heard(app, NOW[0] - 6 * 3600, "earlier")
    send(app, NOW[0] - 30 * 60, "one of hers he has not answered")
    streak = imp.unanswered_streak()
    print(f"  streak {streak}; the gate says: {ini.hold_reason(streak, 'read')}")

    print("\n  a gauge at its end (App.maybe_impulse's forced path):")
    print(f"    with urgent: {ini.hold_reason(streak, 'read', urgent=True) or '(through, and the override is logged above)'}")

    print("\n  a stance that entered without waiting:")
    send(app, NOW[0] - 5 * 60, "another of hers")
    streak = imp.unanswered_streak()
    ini.note_sent(streak)
    print(f"    streak {streak}; the gate says: {ini.hold_reason(streak, 'read')}")
    for key in ("sitting_on_it", "frightened", "outside_again"):
        app.store.set("stance", {"key": key, "since": NOW[0]})
        why = ini.hold_reason(streak, "read")
        print(f"    stance {key:16s} -> {'held: ' + why if why else 'through'}")
    app.store.set("stance", None)


# ---------------------------------------------------------------- 4. a restart

def restart(app, tmp, config, db):
    ini = app.impulse.initiative
    print("\n=== what a restart keeps ===")
    clear(app)
    NOW[0] = at(app.clock, 10, day=5)
    ini.observe_away(0, app.state)
    NOW[0] = at(app.clock, 10, 46, day=5)
    ini.observe_away(46 * 60, app.state)
    NOW[0] = at(app.clock, 16, day=5)
    ini.observe_away(3, app.state)
    before = {"initiative_hold_until": app.store.get("initiative_hold_until", 0),
              "initiative_return": app.store.get("initiative_return", None),
              "initiative_away_since": app.store.get("initiative_away_since", 0)}
    app.store.set("initiative_unanswered_counts", {app.clock.date_str(): 2})
    before["initiative_unanswered_counts"] = app.store.get("initiative_unanswered_counts", {})

    app2 = harness.refuse_model(harness.build_on(tmp, config, db, copy=False))
    drive(app2.clock)
    NOW[0] = at(app2.clock, 16, day=5)
    ok = True
    for k, v in before.items():
        got = app2.store.get(k, None)
        same = (str(got) == str(v))
        ok = ok and same
        print(f"  {'ok  ' if same else 'FAIL'} {k}: {got}")
    print(f"  the new App's gate says: {app2.impulse.initiative.hold_reason(0, '') or '(open)'}")
    return ok


def main():
    config = sys.argv[1] if len(sys.argv) > 1 else "config_yukarin.json"
    db = sys.argv[2] if len(sys.argv) > 2 else "data/yukarin.db"
    random.seed()
    tmp = os.path.join(tempfile.gettempdir(), "initiative_test.db")
    app = harness.refuse_model(harness.build_on(tmp, config, db))
    drive(app.clock)
    NOW[0] = app.clock.user_now().timestamp() if False else datetime.datetime.now().timestamp()
    print(f"\n{app.config.character.name}, on a copy of {db}")
    print(app.impulse.initiative.report())
    his_return(app)
    ignored(app)
    overrides(app)
    ok = restart(app, tmp, config, db)
    print("\n" + ("every counter survived the rebuild" if ok else "SOMETHING DID NOT SURVIVE THE REBUILD"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
