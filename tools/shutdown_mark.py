"""Write "she was stopped on purpose, and this is why" into every character's save.

A character who is stopped and started again has a stretch of hours during
which nobody wrote her: no schedule, no scenes, no messages, no compile. When
she comes back, the day machinery has to account for that stretch somehow, and
what it does without a record is invent it from placeholders -- a day that
reads as lived because nothing said otherwise. The honest answer is a blank
she knows about, and this is where the fact that produces it is written.

The stop itself is `stopall.cmd` (tools/restart.ps1 -Shutdown), which stops
every process and then runs this. The read at the other end is the boot's, in
`sim/downtime.py`: it finds the marker, turns the stretch between the stop and
the resume into one temporal-gap event, and clears it.

TWO REFUSALS, both of which are the point of the tool rather than caution.

  * **It will not write behind a running process.** The save's own writer is
    the bot, and a second writer on an open save is the fault that this
    project has a lock file for. The test is the lock file's holder
    (`singleton.Singleton.holder()`), which answers with a live pid or 0, and
    the liveness test belongs there: `OpenProcess` hands back a usable handle
    for a process that has already exited, so "the handle opened" is not an
    answer. A character whose process is still up is reported and counts as a
    failure; nothing of hers is touched.

  * **It will not overwrite a marker that is already there.** A marker on a
    save is a stop that nobody has resumed from yet, and ITS timestamp is the
    honest beginning of the stretch nobody wrote her. Replacing it with a
    later one would shorten the blank by however long the save sat untouched
    between the two stops.

What it writes, per save, in the `kv` table (`key TEXT PRIMARY KEY, value
TEXT`, the value JSON, exactly as `store.py` reads it):

    stopped   {"ts": <time.time() at the stop>, "why": "<one sentence>",
               "kind": "operator" | "no_credit", "by": "stopall.cmd"}
    stops     the last 50 rows of {"stopped_ts":, "why":, "kind":}; the boot
              completes the newest row with the resume.

`kind` says whose decision the stop was: `operator` is his, `no_credit` is the
machine's own -- the bot asking to be shut down because there is no money left
to answer with. She is told a different thing in each case.

    python tools/shutdown_mark.py --why "moving the machine"
    python tools/shutdown_mark.py --kind no_credit --why "the account is empty"
    python tools/shutdown_mark.py --dry-run --why "..."       # says what it would write
    python tools/shutdown_mark.py yukari asumin --why "..."   # only these two
    python tools/shutdown_mark.py tomoe --db data/copy.db --why "..."   # a rehearsal
"""
import argparse
import io
import json
import os
import sqlite3
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from singleton import Singleton                     # noqa: E402
from tools import registry                          # noqa: E402

KEEP = 50           # how many past stops a save carries
BY = "stopall.cmd"

if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)


def when(ts):
    """Machine local time, which is what every timestamp written here is."""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))


def existing(db):
    """The marker already on this save, or None. Read-only: a save that is
    only being looked at is not opened for writing, so a dry run cannot
    create a journal file beside somebody's live database."""
    uri = "file:%s?mode=ro" % db.replace("?", "%3f").replace("#", "%23")
    conn = sqlite3.connect(uri, uri=True)
    try:
        have = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='kv'").fetchone()
        if not have:
            return "no kv table"
        row = conn.execute("SELECT value FROM kv WHERE key='stopped'").fetchone()
        if not row or row[0] is None:
            return None
        try:
            return json.loads(row[0])
        except ValueError:
            return {}
    finally:
        conn.close()


def write_marker(db, marker):
    """The marker and one row on the list, in one transaction. Plain sqlite3
    rather than `store.Store`: the save's own writer is dead by the time this
    runs, and opening the whole store would build a character to write four
    keys."""
    conn = sqlite3.connect(db)
    try:
        row = conn.execute("SELECT value FROM kv WHERE key='stops'").fetchone()
        try:
            stops = json.loads(row[0]) if row and row[0] else []
        except ValueError:
            stops = []
        if not isinstance(stops, list):
            stops = []
        stops.append({"stopped_ts": marker["ts"], "why": marker["why"], "kind": marker["kind"]})
        stops = stops[-KEEP:]
        conn.execute("INSERT OR REPLACE INTO kv(key,value) VALUES('stopped',?)",
                     (json.dumps(marker),))
        conn.execute("INSERT OR REPLACE INTO kv(key,value) VALUES('stops',?)",
                     (json.dumps(stops),))
        conn.commit()
        return len(stops)
    finally:
        conn.close()


def mark(row, db, marker, dry):
    """One character. Returns (ok, one line about her)."""
    label = "%s (%s)" % (row["name"], row["key"])
    if not os.path.exists(db):
        return False, "%s: no save at %s" % (label, db)

    # The lock file names the process that holds this save, and holder() is 0
    # unless that process is genuinely alive.
    pid = Singleton(db + ".lock").holder()
    if pid:
        return False, ("%s: her process is still up (pid %d) -- nothing written. "
                       "Stop her first." % (label, pid))

    try:
        was = existing(db)
    except sqlite3.Error as e:
        return False, "%s: %s could not be read (%s)" % (label, db, type(e).__name__)
    if was == "no kv table":
        return False, "%s: %s has no kv table, so it is not a save" % (label, db)
    if was is not None:
        return True, ("%s: already marked stopped at %s (%s, %s) -- left as it is, "
                      "because that is when the blank starts"
                      % (label, when(was.get("ts") or 0), was.get("kind") or "?",
                         was.get("why") or "no reason given"))

    if dry:
        return True, "%s: would write %s to %s" % (label, json.dumps(marker), db)
    try:
        n = write_marker(db, marker)
    except sqlite3.Error as e:
        return False, "%s: could not write to %s (%s)" % (label, db, type(e).__name__)
    return True, ("%s: marked stopped at %s, %s -- \"%s\" (%d stop(s) on her record)"
                  % (label, when(marker["ts"]), marker["kind"], marker["why"], n))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("keys", nargs="*", help="character keys from characters.json; all of them by default")
    ap.add_argument("--why", default="", help="one plain sentence, written onto every record")
    ap.add_argument("--kind", default="operator", choices=("operator", "no_credit"),
                    help="whose decision the stop was")
    ap.add_argument("--dry-run", action="store_true", help="say what would be written and touch nothing")
    ap.add_argument("--db", default="", help="mark this save instead of the register's; needs exactly one key")
    a = ap.parse_args(argv)

    rows = registry.characters()
    if not rows:
        print("no characters registered: characters.json is missing or empty")
        return 1
    if a.keys:
        known = {r["key"] for r in rows}
        unknown = [k for k in a.keys if k not in known]
        if unknown:
            print("unknown character key(s): %s. The register has: %s"
                  % (", ".join(unknown), ", ".join(sorted(known))))
            return 2
        rows = [r for r in rows if r["key"] in a.keys]
    if a.db and len(rows) != 1:
        print("--db replaces one character's save, so name exactly one key with it")
        return 2

    # One timestamp for the whole run: the four saves record the same stop, and
    # a per-character clock would make one character's blank start a second
    # before another's for no reason anybody could read.
    marker = {"ts": time.time(), "why": a.why.strip() or "no reason given",
              "kind": a.kind, "by": BY}

    print("[shutdown_mark] %s%s -- %s"
          % (when(marker["ts"]), " (dry run, nothing will be written)" if a.dry_run else "",
             marker["why"]))
    bad = 0
    for row in rows:
        db = a.db if a.db else row["db"]
        if not os.path.isabs(db):
            db = os.path.join(ROOT, db)
        ok, line = mark(row, db, marker, a.dry_run)
        if not ok:
            bad += 1
        print("  " + line)
    if bad:
        print("  %d character(s) could not be marked. Their blank will not be on their record."
              % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
