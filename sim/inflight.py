"""Work that was in flight when the process died.

`tools/restart.ps1` stops with `TerminateProcess`, so no `finally` and no
`atexit` runs: a job on a background thread -- a lookup, a recall, the day's
compile, a harvest of photographs, her look at her timeline -- simply stops
mid-call, and the next process has no way to know it ever started. That was
the last row of the restart inventory
(`data/retired/2026-09-04_restart_safe/REPORT.md`).

One kv record, `in_flight`, holds a row per running job: what kind it is,
what it is about, when it started, the pid that started it, and `redo` --
the request the next process would need to do it again. A job writes its row
when it starts and deletes it when it finishes, whether it finished well or
raised; a killed process leaves the row behind, and that leftover row IS the
flag.

At boot the leftovers are logged in one line and handed to `POLICY`, which
is the whole of the per-kind behaviour -- redo it, drop it and record it as a
missed call the way `LLM.call` does, or put a picked photograph back in the
pool. A job kind with no row in that table is logged and dropped; nothing
gets a guard of its own.

    from sim import inflight
    with inflight.job(store, "lookup", about=text[:80]):
        ...                                   # the work

`resolve(app)` is the boot read. It runs off the loop thread (the compile it
may redo is a model call of a minute or more) and before any job of this
process has started, so a row it finds is by definition a dead process's.
"""
import threading
import time

import logger

_lock = threading.RLock()
_seq = 0


# ---------------- the record ----------------

def rows(store):
    """[{token, kind, about, started_ts, pid, redo}] -- the jobs believed to be running."""
    if store is None:
        return []
    out = store.get("in_flight", []) or []
    return list(out) if isinstance(out, list) else []


def _write(store, out):
    store.set("in_flight", out[-40:])


def start(store, kind, about="", redo=None):
    """Record that a job has begun; returns the token that clears it."""
    global _seq
    if store is None:
        return ""
    import os
    with _lock:
        _seq += 1
        token = f"{kind}:{int(time.time())}:{_seq}"
        out = [r for r in rows(store) if r.get("token") != token]
        out.append({"token": token, "kind": str(kind), "about": str(about or "")[:200],
                    "started_ts": time.time(), "pid": os.getpid(),
                    "redo": redo if isinstance(redo, dict) else ({} if redo is None else {"what": str(redo)[:200]})})
        _write(store, out)
    return token


def done(store, token):
    """The job finished -- well or badly. Either way it is no longer in flight."""
    if store is None or not token:
        return
    with _lock:
        out = [r for r in rows(store) if r.get("token") != token]
        _write(store, out)


class job:
    """`with inflight.job(store, kind, about, redo):` round the body of a job.

    The row is written on the way in and removed on the way out, including
    on an exception: a job that failed is not a job still running. A killed
    process never reaches the way out, which is the point."""

    def __init__(self, store, kind, about="", redo=None):
        self.store, self.kind, self.about, self.redo = store, kind, about, redo
        self.token = ""

    def __enter__(self):
        self.token = start(self.store, self.kind, self.about, self.redo)
        return self

    def __exit__(self, *exc):
        done(self.store, self.token)
        return False


# ---------------- what to do with one the process died on ----------------

def _redo_compile(app, row):
    """A day the compile started and never told is told now."""
    d = str((row.get("redo") or {}).get("date") or row.get("about") or "").strip()
    if not d:
        return "no date on the row; dropped"
    if app.store.get_day(d):
        return f"{d} already has a day row; nothing to redo"
    try:
        app.compiled_dates.discard(d)
    except AttributeError:
        pass
    app.compile(d)
    return f"{d} compiled again"


def _drop_as_missed(app, row):
    """Dropped, and written where an unanswered call is written: the work was
    paid for and lost, and `App.catch_up` is the one reader of that."""
    try:
        old = list(app.store.get("missed_calls", []) or [])
        old.append({"ts": float(row.get("started_ts") or time.time()), "role": str(row.get("kind"))})
        app.store.set("missed_calls", old[-200:])
    except Exception as e:
        return f"not recorded as missed: {type(e).__name__}: {e}"
    return "dropped and recorded as a missed call"


def _release_photo(app, row):
    """A photograph picked to send that never went stays usable."""
    rid = (row.get("redo") or {}).get("rid")
    sc = getattr(app, "scenery", None)
    if sc is None or rid is None:
        return "no photograph to put back"
    try:
        with app.store.lock:
            cur = app.store.conn.execute("SELECT used_ts FROM scenery WHERE rowid=?", (int(rid),)).fetchone()
            if cur is None:
                return f"row {rid} is gone"
            if not cur[0]:
                return f"row {rid} was never marked sent; still in the pool"
            app.store.conn.execute("UPDATE scenery SET used_ts=NULL WHERE rowid=?", (int(rid),))
            app.store.conn.commit()
    except Exception as e:
        return f"not put back: {type(e).__name__}: {e}"
    return f"row {rid} put back in the pool"


def _drop(app, row):
    """Nothing to redo and nothing to give back: the next run does it again on its own clock."""
    return "dropped; the next one is due on its own schedule"


# One row per kind of job, and the whole of the behaviour. A kind that is not
# here is logged and dropped -- adding a job means adding a line here.
POLICY = {
    "compile": _redo_compile,
    "lookup": _drop_as_missed,
    "recall": _drop_as_missed,
    "x_look": _drop_as_missed,
    "scenery_harvest": _drop,
    "scenery_pick": _release_photo,
}


def resolve(app):
    """The boot read: log what was in flight, then act on each by its kind.

    Off the loop thread and before this process starts any job of its own.
    Returns the number of rows it found."""
    import os
    store = app.store
    with _lock:
        found = [r for r in rows(store) if int(r.get("pid") or 0) != os.getpid()]
        keep = [r for r in rows(store) if int(r.get("pid") or 0) == os.getpid()]
        _write(store, keep)
    if not found:
        return 0
    logger.log(f"[boot] {len(found)} job(s) were in flight when the process died: "
               + "; ".join(f"{r.get('kind')} ({r.get('about') or 'no subject'}, "
                           f"{_ago(app, r)})" for r in found))
    for r in found:
        fn = POLICY.get(str(r.get("kind")))
        if fn is None:
            logger.log(f"[boot] {r.get('kind')}: no rule for this kind of job; dropped")
            continue
        try:
            logger.log(f"[boot] {r.get('kind')}: {fn(app, r)}")
        except Exception as e:
            logger.log(f"[boot] {r.get('kind')} could not be settled: {type(e).__name__}: {e}")
    return len(found)


def _ago(app, row):
    try:
        mins = (time.time() - float(row.get("started_ts") or 0)) / 60.0
    except (TypeError, ValueError):
        return "at an unknown time"
    return f"started {mins:.0f} min ago"


def report(store):
    """`/inflight`: what this process believes is running now."""
    out = rows(store)
    if not out:
        return "nothing in flight"
    return "in flight:\n" + "\n".join(
        f"  {r.get('kind')} pid {r.get('pid')} for {(time.time() - float(r.get('started_ts') or 0)) / 60.0:.1f} min"
        f" -- {r.get('about') or ''}" for r in out)
