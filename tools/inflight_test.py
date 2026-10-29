"""The in-flight flag, proven by killing a process in the middle of a job.

    python tools/inflight_test.py
    python tools/inflight_test.py --config config_yukarin.json --db data/yukarin.db

A child process builds the App on a copy of the save and starts a real
lookup on its background thread. The parent waits until the kv record
`in_flight` shows the job, then kills the child with `taskkill /F`, which is
`TerminateProcess`: no `finally`, no `atexit`, exactly what `restart.ps1`
does. The parent then builds a second App on the same copy -- a restart --
and runs the boot read, which must find the row, log it and settle it.

Three more rows are written by hand before the boot read, because the
outcomes they exercise cannot be reached by killing a lookup: a compile for
a day that already has its `days` row (must NOT be paid for again), a compile
for a day that has none (must be rerun, for real), and a photograph marked
sent that never went (must go back in the pool).

It spends: the lookup call the child is killed in the middle of, and one
compile of an empty day.
"""
import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

TMP = os.path.join(ROOT, "data", "retired", "inflight_test", "inflight.db")
EMPTY_DAY = "2026-01-01"          # nothing on record: a compile of it is a few hundred tokens


def _kv(db, key):
    c = sqlite3.connect("file:" + db + "?mode=ro", uri=True)
    try:
        r = c.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return json.loads(r[0]) if r and r[0] else []
    except sqlite3.OperationalError:
        return []
    finally:
        c.close()


def child(config, db):
    """Build on the copy and start a lookup; then sit there to be killed."""
    from tools import harness
    app = harness.build_on(db, config, db, copy=False)
    app.lookup.start("have you seen Bocchi the Rock, the episode with the bucket", app.clock.now_ts())
    print("[child] lookup started", flush=True)
    while True:
        time.sleep(1)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="config.json")
    p.add_argument("--db", default="data/world.db")
    p.add_argument("--child", action="store_true")
    a = p.parse_args()
    if a.child:
        return child(a.config, a.db)

    os.makedirs(os.path.dirname(TMP), exist_ok=True)
    from tools.dbcopy import copy_db
    from tools import harness
    copy_db(os.path.join(ROOT, a.db), TMP)
    print(f"== a copy of {a.db} at {TMP}")

    # ---- the child, and the kill ----
    proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "tools", "inflight_test.py"),
                             "--child", "--config", a.config, "--db", TMP],
                            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace")
    t0 = time.time()
    rows = []
    while time.time() - t0 < 180:
        rows = _kv(TMP, "in_flight")
        if rows:
            break
        if proc.poll() is not None:
            print("== the child died on its own:\n" + (proc.stdout.read() or ""))
            return 1
        time.sleep(0.5)
    if not rows:
        proc.kill()
        print("== the child never wrote a row; the flag is not being written")
        return 1
    print(f"== the child is in flight after {time.time() - t0:.1f}s: "
          + "; ".join(f"{r['kind']} pid {r['pid']} ({r['about'][:50]})" for r in rows))
    subprocess.run(["taskkill", "/F", "/PID", str(proc.pid)], capture_output=True)
    proc.wait(timeout=30)
    print(f"== killed with TerminateProcess (exit {proc.returncode}); "
          f"kv in_flight still holds {len(_kv(TMP, 'in_flight'))} row(s)")

    # ---- three more outcomes, written the way a dead process would have left them ----
    import sqlite3 as s3
    c = s3.connect(TMP)
    told = c.execute("SELECT date FROM days ORDER BY date DESC LIMIT 1").fetchone()[0]
    c.execute("DELETE FROM days WHERE date=?", (EMPTY_DAY,))
    pick = c.execute("SELECT rowid FROM scenery WHERE used_ts IS NULL LIMIT 1").fetchone()
    if pick:
        c.execute("UPDATE scenery SET used_ts=? WHERE rowid=?", (time.time(), pick[0]))
    extra = [
        {"token": "t1", "kind": "compile", "about": told, "started_ts": time.time() - 300, "pid": 1,
         "redo": {"date": told}},
        {"token": "t2", "kind": "compile", "about": EMPTY_DAY, "started_ts": time.time() - 300, "pid": 1,
         "redo": {"date": EMPTY_DAY}},
    ]
    if pick:
        extra.append({"token": "t3", "kind": "scenery_pick", "about": "a photograph she picked and never sent",
                      "started_ts": time.time() - 300, "pid": 1, "redo": {"rid": pick[0]}})
    cur = _kv(TMP, "in_flight") + extra
    c.execute("INSERT OR REPLACE INTO kv(key,value) VALUES(?,?)", ("in_flight", json.dumps(cur, ensure_ascii=False)))
    c.commit()
    c.close()
    print(f"== {len(extra)} more row(s) written by hand: a compile of {told} (already told), "
          f"a compile of {EMPTY_DAY} (never told)"
          + (f", scenery row {pick[0]} marked sent" if pick else ""))

    # ---- the restart ----
    print("== building the App again on the same copy: the restart")
    app = harness.build_on(TMP, a.config, TMP, copy=False)
    # never let a test prune or write into his real backups
    app.config.logging.backup_dir = os.path.join(os.path.dirname(TMP), "backups")
    from sim import inflight
    n = inflight.resolve(app)
    print(f"== the boot read found {n} row(s); kv in_flight now holds {len(_kv(TMP, 'in_flight'))}")

    ok = True
    day = app.store.get_day(EMPTY_DAY)
    print(f"   {EMPTY_DAY} days row after the boot read: "
          + (f"{len(day['narrative'])} chars -- REDONE" if day else "STILL MISSING"))
    ok &= bool(day)
    if pick:
        c = s3.connect("file:" + TMP + "?mode=ro", uri=True)
        used = c.execute("SELECT used_ts FROM scenery WHERE rowid=?", (pick[0],)).fetchone()[0]
        c.close()
        print(f"   scenery row {pick[0]}: " + ("back in the pool" if used is None else f"still marked sent ({used})"))
        ok &= used is None
    missed = app.store.get("missed_calls", []) or []
    print(f"   missed_calls now holds {len(missed)} row(s); the last: {missed[-1] if missed else '(none)'}")
    ok &= any(m.get("role") == "lookup" for m in missed)
    print("== " + ("EVERY OUTCOME AS DESIGNED" if ok else "SOMETHING DID NOT SETTLE"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
