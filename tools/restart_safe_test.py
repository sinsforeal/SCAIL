"""What a restart must not lose: build the App, set the state, build again.

Both bots are stopped and started several times in an evening, and a stop is
`Stop-Process -Force`: no `finally`, no `atexit`. Anything a module holds on
itself and writes nowhere is gone, and anything written only on the way out
was never written at all. This asserts, for the state that was found holding
its value only in memory, that a second App built on the same save reads back
what the first one set.

It is a rebuild, not a kill: the first App object is dropped and a second is
constructed on the same file. That is the strongest thing a test can do
without a subprocess, and it is enough -- everything under test here is a
`store.set` at the moment of change against a read in a constructor, and the
constructor is what runs again.

    python tools/restart_safe_test.py                  # both characters
    python tools/restart_safe_test.py --config config_yukarin.json --db data/yukarin.db

No model calls: every App built here is refused (`harness.refuse_model`).
"""
import argparse
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools import harness  # noqa: E402


FAILS = []
CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append(name)
    if ok:
        print(f"  ok   {name}" + (f" -- {detail}" if detail else ""))
    else:
        FAILS.append(name)
        print(f"  FAIL {name}" + (f" -- {detail}" if detail else ""))


_LAST_BUILT = [0]


def _build(*a, **k):
    """A run directory is named to the second, so two Apps cannot be built
    inside one."""
    while int(time.time()) <= _LAST_BUILT[0]:
        time.sleep(0.2)
    _LAST_BUILT[0] = int(time.time())
    return harness.refuse_model(harness.build_on(*a, **k))


def run(config, db, label):
    print(f"[restart-safe] {label}: {config} on a copy of {db}")
    fd, tmp = tempfile.mkstemp(suffix=".db", prefix="restart_safe_")
    os.close(fd)
    os.remove(tmp)
    try:
        app = _build(tmp, config, db)

        # --- what the first process sets --------------------------------
        # the standing request to cover a hole in one scene, and the forced
        # phone look that goes with it: `App.catch_up` sets both and empties
        # `missed_calls` in the same breath, so they are all that is left
        app.director.catch_up = True
        if app.phone:
            app.phone.force_next = True

        # the current scene, whole. The scenes table has a fixed column list,
        # so the keys the code attaches after the model answers are only ever
        # in the kv copy.
        scene = dict(app.director.current or {})
        ts = time.time()
        scene.update({"ts": ts, "hm": "12:34", "location": "a place", "activity": "doing a thing",
                      "with": "alone", "phone_access": "free", "sensory": "", "inner": "",
                      "events": [{"text": "something happened", "salience": 2}],
                      "setting": "indoors", "ate": "", "open_note": "a note she has open",
                      "around": "two people at the next table", "next_tick_minutes": 25})
        app.store.add_scene(ts, app.clock.date_str(), "12:34", scene, "")
        app.director.current = scene
        app.director._keep_scene(scene)

        # when she has decided to answer him. Only once the patch that makes
        # `App.reply_plan` a property over the save has been applied
        # (data/retired/2026-09-04_restart_safe/patch_forbidden.py); until
        # then the attribute is plain and there is nothing to check.
        plan_kept = isinstance(getattr(type(app), "reply_plan", None), property)
        if plan_kept:
            app.reply_plan = {"mode": "free", "presence": 0.8, "due_ts": ts + 264.0}

        # the sleep latch and the wake latch of a character who lives on his
        # machine, and where her reading of his notes had got to
        if getattr(app, "sight", None) is not None and hasattr(app.sight, "_set_woken"):
            app.sight._set_woken(True)
            app.sight._since = ts - 60
            app.store.set("resident_notes_since", app.sight._since)
            app.store.set("resident_asleep", {"since": ts - 3600, "hm": "02:11"})

        del app

        # --- the restart -------------------------------------------------
        again = _build(tmp, config, db, copy=False)

        check(f"{label}: the hole the catch-up asked for is still owed",
              again.director.catch_up is True)
        if again.phone:
            check(f"{label}: the forced phone look survives",
                  again.phone.force_next is True)

        cur = again.director.current or {}
        check(f"{label}: the scene comes back whole, not cut to the table's columns",
              cur.get("open_note") == "a note she has open" and cur.get("around")
              and cur.get("setting") == "indoors",
              f"open_note={cur.get('open_note')!r} around={cur.get('around')!r} setting={cur.get('setting')!r}")
        check(f"{label}: the scene's events come back as a list, not as JSON text",
              isinstance(cur.get("events"), list),
              f"{type(cur.get('events')).__name__}")

        if getattr(again, "sight", None) is not None and hasattr(again.sight, "_set_woken"):
            check(f"{label}: his message having woken her survives", again.sight._woken is True)
            check(f"{label}: she is still asleep after the restart, not re-derived",
                  again.sight._asleep is not None and again.sight._asleep.get("start") == "02:11",
                  repr(again.sight._asleep))
            check(f"{label}: where her reading of his notes had got to survives",
                  abs(float(again.sight._since) - (ts - 60)) < 1.0)

        if plan_kept:
            p = again.reply_plan or {}
            check(f"{label}: when she had decided to answer him survives, to the second",
                  p.get("mode") == "free" and abs(float(p.get("due_ts") or 0) - (ts + 264.0)) < 1.0,
                  f"due in {(float(p.get('due_ts') or 0) - ts) / 60:.1f} min, planned 4.4")
        else:
            print("  --   the reply plan is still a plain attribute; run "
                  "data/retired/2026-09-04_restart_safe/patch_forbidden.py --write to cover it")

        # the voice queue is a file, and it must be HER file: two characters
        # sharing one would hand the first to boot the other's line
        if getattr(again, "tts", None) is not None:
            base = os.path.basename(again.tts.pending_path)
            check(f"{label}: the queue of voice lines is hers, not the machine's",
                  base != "pending.json", base)

        del again
    finally:
        for suf in ("", "-wal", "-shm"):
            try:
                os.remove(tmp + suf)
            except OSError:
                pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="")
    ap.add_argument("--db", default="")
    args = ap.parse_args()
    if args.config or args.db:
        run(args.config or "config.json", args.db or "data/world.db", "one character")
    else:
        run("config.json", "data/world.db", "in a world")
        run("config_yukarin.json", "data/yukarin.db", "on his machine")
    print()
    if FAILS:
        print(f"[restart-safe] {len(FAILS)} of {len(CHECKS)} FAILED: {', '.join(FAILS)}")
        return 1
    print(f"[restart-safe] all clear: {len(CHECKS)} checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
