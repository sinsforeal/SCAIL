"""The gate on what he has actually watched (`sim/watching_him.py`).

Nothing is fetched, digested, marked seen or told to a character until he has
sat through `watching.min_watched_minutes` of the file -- unpaused seconds as
the player counts them, never the position, because seeking to the last minute
and closing the file leaves the same position as watching the whole thing.

Four things are proved, on a scratch save, with a hand-written player history,
state file and plays log and no network or model call anywhere:

  * an open below the gate is HELD -- no fetch, not seen, and the hold is a
    row in the save;
  * the hold survives a restart and is not doubled;
  * past the gate the episode is taken up and the hold is gone;
  * a play that ENDED under the gate is a skim: no fetch, not seen, a row in
    his own timeline saying so.
"""
import json
import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import harness  # noqa: E402
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# a file his library really is shaped like, and a work to resolve it to
SHOW = "Example Show"
AID = 25145


class FakeKB:
    """His anime mirror, with one work in it. The gate is what is under test,
    and a real mirror would make the test depend on his list."""

    def resolve_candidates(self, title, ep=None, kind=""):
        return [{"aid": AID, "title": SHOW, "type": "tv", "rule": "the only one"}]

    def resolve_special(self, title):
        return None

    def resolve_strict(self, title, ep=None, kind=""):
        return (AID, SHOW, "tv")

    def entry(self, aid):
        return {"type": "tv", "eps": 12, "season": "fall 2014"}

    def japanese_title(self, aid):
        return "電波教師"


def path_for(ep):
    return f"D:\\Videos\\Example Show [1080p] (2014)\\Example Show - {ep:02d}.mkv"


def rig(app, box):
    """Point the module at the scratch player files and stop it fetching."""
    c = app.config.watching
    c.enabled = True
    c.player_history_path = os.path.join(box, "mpv_history.log")
    c.now_playing_path = os.path.join(box, "mpv_now.json")
    c.player_plays_path = os.path.join(box, "mpv_plays.log")
    c.plays_timeline_path = os.path.join(box, "plays.md")
    c.min_minutes_in = 3.0
    c.min_watched_minutes = 10.0
    # the wait for his list to name the id is a different mechanism with its
    # own test; off here so a pass through the gate is not held by it
    c.confirm_minutes = 0.0
    w = app.watching
    w.anime_kb = FakeKB()
    w._from_list = lambda since: []
    started = []
    w.start = lambda item: (started.append(item), True)[1]
    return w, started


def write_history(box, rows):
    with open(os.path.join(box, "mpv_history.log"), "w", encoding="utf-8") as fh:
        for ts, p in rows:
            fh.write(f"{int(ts)}|{p}\n")


def write_now(box, opened=None, path="", watched=0.0, pos=0.0, dur=1420.0, playing=True):
    d = {"t": int(time.time()), "playing": False}
    if playing:
        d = {"t": int(time.time()), "playing": True, "path": path, "pos": pos,
             "dur": dur, "paused": False, "watched": watched, "opened": int(opened)}
    with open(os.path.join(box, "mpv_now.json"), "w", encoding="utf-8") as fh:
        json.dump(d, fh)


def write_plays(box, rows):
    with open(os.path.join(box, "mpv_plays.log"), "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write("{opened}|{ended}|{path}|length={length:.1f}|time={time:.1f}"
                     "|watched={watched:.1f}|reason={reason}\n".format(**r))


def main():
    tmp = os.path.join(tempfile.gettempdir(), "scail_watching_gate.db")
    box = os.path.join(tempfile.gettempdir(), "scail_watching_gate")
    shutil.rmtree(box, ignore_errors=True)
    os.makedirs(box, exist_ok=True)
    fails = []

    def check(label, ok):
        print(("  ok   " if ok else "  FAIL ") + label)
        if not ok:
            fails.append(label)

    app = harness.build_on(tmp)
    w, started = rig(app, box)
    store = app.store
    now = time.time()

    # ---- 1. he opens episode 6 and is two minutes in
    open6 = int(now - 130)
    write_history(box, [(open6, path_for(6))])
    write_now(box, opened=open6, path=path_for(6), watched=120.0, pos=125.0)
    store.set("watching_cursor", {"list": "2026-01-01T00:00", "player": open6 - 1})
    store.set("watching_seen", {})
    store.set("watching_short", [])
    store.set("watching_held", {})
    got = w.poll()
    held = store.get("watching_held", {}) or {}
    check("2 min into a 10 min gate: nothing is taken up", got is None)
    check("...no fetch was started", not started)
    check(f"...the episode is not seen ({list((store.get('watching_seen', {}) or {}))})",
          f"{AID}:6" not in (store.get("watching_seen", {}) or {}))
    check(f"...and the hold is a row in the save ({list(held)})",
          list(held) == [f"{AID}:6"] and abs(float(held[f"{AID}:6"]["watched"]) - 120.0) < 1)
    check("...the cursor was put back so the next poll finds the open again",
          float((store.get("watching_cursor", {}) or {}).get("player", 0)) <= open6 - 1)

    # ---- 2. the process is stopped and started again, still inside the file
    write_now(box, opened=open6, path=path_for(6), watched=300.0, pos=310.0)
    app2 = harness.build_on(tmp, copy=False)
    w2, started2 = rig(app2, box)
    got2 = w2.poll()
    held2 = app2.store.get("watching_held", {}) or {}
    check("after a restart, five minutes in: still nothing taken up", got2 is None)
    check("...still no fetch", not started2)
    check(f"...one hold, not two ({list(held2)})", list(held2) == [f"{AID}:6"])
    check("...and it is the same hold, held since the first poll",
          abs(float(held2[f"{AID}:6"]["since"])
              - float((store.get("watching_held", {}) or {})[f"{AID}:6"]["since"])) < 1)

    # ---- 3. he is now eleven minutes into it
    write_now(box, opened=open6, path=path_for(6), watched=660.0, pos=670.0)
    got3 = w2.poll()
    held3 = app2.store.get("watching_held", {}) or {}
    check(f"11 min in: episode 6 is taken up ({got3 and got3.get('title')} "
          f"ep{got3 and got3.get('ep')})",
          bool(got3) and got3.get("anime_id") == AID and int(got3.get("ep")) == 6)
    check(f"...with the watched seconds on it ({got3 and got3.get('watched')})",
          bool(got3) and abs(float(got3.get("watched") or 0) - 660.0) < 1)
    check(f"...and the hold is cleared ({list(held3)})", not held3)

    # ---- 4. he opens episode 7, watches four minutes and closes it
    open7 = int(now - 400)
    write_history(box, [(open6, path_for(6)), (open7, path_for(7))])
    write_plays(box, [{"opened": open7, "ended": open7 + 250, "path": path_for(7),
                       "length": 1420.0, "time": 245.0, "watched": 240.0,
                       "reason": "stop"}])
    write_now(box, playing=False)
    app2.store.set("watching_cursor", {"list": "2026-01-01T00:00", "player": open7 - 1})
    started2.clear()
    got4 = w2.poll()
    seen = app2.store.get("watching_seen", {}) or {}
    short = app2.store.get("watching_short", []) or []
    check("ended at 4 min of a 10 min gate: nothing is taken up", got4 is None)
    check("...no fetch was started", not started2)
    check(f"...episode 7 is not marked seen ({sorted(seen)})", f"{AID}:7" not in seen)
    check(f"...the open is remembered by its own clock, not as the episode ({short[-1:]})",
          f"{AID}:7:{open7}" in short)
    check("...and no hold is left standing",
          f"{AID}:7" not in (app2.store.get("watching_held", {}) or {}))

    # ---- his own timeline
    tl = os.path.join(box, "plays.md")
    body = open(tl, encoding="utf-8").read() if os.path.exists(tl) else ""
    rows = [ln for ln in body.splitlines() if ln.startswith("|") and str(open7) in ln]
    check(f"his timeline has a row for the play ({rows[:1]})", len(rows) == 1)
    check("...and it reads as a skim that did not count for her",
          bool(rows) and "skim" in rows[0] and "no (skim)" in rows[0])
    # every process may write it, and the row must not double
    w.config.watching.plays_timeline_path = tl
    w._record_plays()
    w2._record_plays()
    again = [ln for ln in open(tl, encoding="utf-8").read().splitlines()
             if ln.startswith("|") and str(open7) in ln]
    check(f"...three writers, one row ({len(again)})", len(again) == 1)

    # ---- 5. a player that reports nothing: no plays log, no state file. The
    # clock is all there is, and "he is still in it" and "he closed it and
    # nothing saw" look the same, so a recent open is held rather than filed
    # as a skim and lost.
    open8 = int(now - 240)
    write_history(box, [(open8, path_for(8))])
    os.remove(os.path.join(box, "mpv_plays.log"))
    os.remove(os.path.join(box, "mpv_now.json"))
    app2.store.set("watching_cursor", {"list": "2026-01-01T00:00", "player": open8 - 1})
    started2.clear()
    got5 = w2.poll()
    check("no plays log and no state file, 4 min since the open: held, not taken up",
          got5 is None and not started2)
    check(f"...and it is not filed as a skim ({(app2.store.get('watching_short', []) or [])[-1:]})",
          not any(s.startswith(f"{AID}:8") for s in (app2.store.get("watching_short", []) or []))
          and f"{AID}:8" in (app2.store.get("watching_held", {}) or {}))

    print()
    print("FAILED: " + "; ".join(fails) if fails else "all ok")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
