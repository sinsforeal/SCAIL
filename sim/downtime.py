"""The stretch during which nobody was running her, kept as exactly that.

A stop is `Stop-Process -Force`: no `finally`, no `atexit`, no shutdown hook,
so the process that is stopped cannot write anything on its way out and the
process that starts hours or days later has no idea a stop ever happened.
Left to itself the director reads the empty stretch as work outstanding and
asks a model to write hours nobody lived, at the wrong hour, as though she
had been there the whole time -- which is the same fault `App.temporal_gap`
already exists to prevent for a hole the provider left.

Two halves, one record. The operator's stop tool writes kv `stopped` on each
character's save once her process is confirmed down -- when it happened, why,
and whether it was a deliberate stop or the account running out of money --
and `on_boot` is the read at the other end: it clears the marker, works out
how long she was off, closes the open row in kv `stops`, and past
`downtime.gap_after_minutes` calls `App.temporal_gap` so the stretch lands on
her record as an honest blank with the reason written into the event.

`no_credit` is the other way in. When the provider answers that the account
has no money left, no retry fixes it and every character on the machine is
about to fail the same way within the minute. The character who saw it writes
her own marker at once -- the decision exists the moment it is made, and the
stop that follows runs no exit path -- and then asks for the machine-wide
stop, so the reason reaches every other save by the ordinary route.

    from sim import downtime
    downtime.on_boot(app)                                    # at the [boot] lines
    downtime.no_credit(config, store, name, role, err, e)    # llm.py, out of balance

Nothing here can stop his machine outside a live run: `no_credit` refuses
unless the feature is on, the clock is live, the machine is Windows and the
environment has no `SCAIL_NO_SHUTDOWN` in it. A sim, a replay, a dry run and
smoke all fail at least one of those.
"""
import os
import subprocess
import time

import logger

# One machine-wide stop per process. A run out of credit fails every role in
# turn, so the second, third and tenth call see the same answer; the flag is
# what stops each of them launching a stop of its own.
_asked = False

# What the provider says when the account is empty, as against every other
# way a call can fail. A bare "402" is deliberately not on this list: it is
# three digits that turn up inside a token count, a request id and a model
# slug, and the cost of reading one of those as an empty account is his
# machine turning itself off.
_PHRASES = ("insufficient credit", "insufficient_quota", "requires more credits",
            "add more credits", "negative balance", "payment required")


def length_words(seconds):
    """A span in the unit that fits it: minutes under two hours, hours under
    two days, days beyond that. `(4320 min)` in an event about a three-day
    stop is a number a reader has to do arithmetic on to understand."""
    s = max(0.0, float(seconds or 0))
    if s < 120 * 60:
        return f"{s / 60:.0f} min"
    if s < 48 * 3600:
        h, m = divmod(int(s // 60), 60)
        return f"{h} h" if m == 0 else f"{h} h {m} min"
    d, h = divmod(int(s // 3600), 24)
    return f"{d} days" if h == 0 else f"{d} days {h} h"


def _local(ts):
    """Machine local time, which is what every stop and start is stamped in."""
    return time.strftime("%m-%d %H:%M", time.localtime(float(ts)))


def _save_start(store):
    """The oldest moment this save holds, or 0 when it holds nothing yet.

    A marker older than that is not a stop of this character's: it is a
    marker copied in from somewhere or a clock that was wrong when it was
    written, and the stretch it claims never existed to be missed."""
    try:
        with store.lock:
            r = store.conn.execute(
                "SELECT MIN(t) FROM (SELECT MIN(ts) AS t FROM messages UNION ALL "
                "SELECT MIN(ts) FROM events UNION ALL SELECT MIN(ts) FROM scenes)").fetchone()
        return float(r[0] or 0)
    except Exception:
        return 0.0


# ---------------- the boot read ----------------

def on_boot(app):
    """The stop before this run, settled. Returns the line it logged, or "".

    No marker is the ordinary case -- a process killed by hand, a crash, a
    machine that lost power -- and it says nothing, because a boot line about
    the absence of a record on every start of every character is noise.
    """
    store = app.store
    mark = store.get("stopped")
    if not isinstance(mark, dict) or not mark:
        return ""
    # cleared before anything else is done with it: a marker that survived
    # its own read would put the same stretch on the record at every boot
    store.set("stopped", None)

    t1 = float(app.clock.now_ts())
    t0 = float(mark.get("ts") or 0)
    why = str(mark.get("why") or "").strip() or "no reason was recorded"
    kind = str(mark.get("kind") or "operator")
    doubt = ""
    started = _save_start(store)
    if t0 <= 0:
        t0, doubt = t1, "the marker carried no time, so the stop is read as having no length"
    elif t0 > t1 + 60:
        doubt = f"the marker was stamped ahead of now ({_local(t0)}) and is read as this moment instead"
        t0 = t1
    elif started and t0 < started:
        doubt = (f"the marker was stamped {_local(t0)}, before anything in this save, "
                 f"and is read from the save's own beginning instead")
        t0 = started
    seconds = max(0.0, t1 - t0)
    minutes = seconds / 60.0

    c = getattr(app.config, "downtime", None)
    on = bool(getattr(c, "enabled", True))
    after = float(getattr(c, "gap_after_minutes", 20) or 0)
    write_gap = on and seconds > 0 and minutes >= after

    _close_row(store, t0, t1, minutes, why, kind, write_gap)

    line = (f"[boot] stopped {_local(t0)} and back {_local(t1)} his time "
            f"({length_words(seconds)}): {why}")
    if doubt:
        line += f"; {doubt}"
    if not write_gap:
        if not on:
            line += "; nothing written as a gap (the whole of downtime is switched off in her config)"
        else:
            line += (f"; nothing written as a gap: shorter than the {after:g} min "
                     f"a stop has to last before it is worth saying (downtime.gap_after_minutes)")
    logger.log(line)

    if write_gap:
        tag = "no credit" if kind == "no_credit" else "stopall.cmd"
        try:
            app.temporal_gap(t0, t1, why=tag, note=why)
        except Exception as e:
            logger.log(f"[boot] the stop was not written as a gap: {type(e).__name__}: {e}")
    return line


def _close_row(store, t0, t1, minutes, why, kind, gap):
    """The open row in kv `stops` gets its other end. A stop the tool never
    managed to record a row for gets one written now from the marker, so the
    list is the whole history of stops rather than the ones that went well."""
    rows = [r for r in (store.get("stops", []) or []) if isinstance(r, dict)]
    row = None
    for r in reversed(rows):
        if not r.get("resumed_ts"):
            row = r
            break
    if row is None:
        row = {"stopped_ts": t0, "why": why, "kind": kind}
        rows.append(row)
    # the clamped time, not the one the marker claimed: a row whose own two
    # ends do not agree with its length is a row nobody can read
    row["stopped_ts"] = t0
    row["resumed_ts"] = t1
    row["minutes"] = round(minutes, 1)
    row["gap"] = bool(gap)
    store.set("stops", rows[-50:])


def report(store):
    """The stops this save remembers, as a paragraph an operator can read.

    The one reader of kv `stops`: when she was stopped, for how long, why,
    and whether the stretch went on her record as a gap."""
    rows = [r for r in (store.get("stops", []) or []) if isinstance(r, dict)]
    if not rows:
        return "no stop is on this save"
    out = []
    for r in rows[-15:]:
        end = (f"back {_local(r['resumed_ts'])} after {length_words(float(r.get('minutes') or 0) * 60)}"
               + (", written as a gap" if r.get("gap") else ", too short for a gap")) if r.get("resumed_ts") \
            else "not started again yet"
        out.append(f"  {_local(r.get('stopped_ts') or 0)} {r.get('kind') or 'operator'}: {end}"
                   f" -- {r.get('why') or 'no reason was recorded'}")
    return f"stops ({len(rows)}, last {len(out)}):\n" + "\n".join(out)


# ---------------- the account running out of money ----------------

def looks_like_no_credit(err, exc=None):
    """Is this failure the account being empty, as against any other failure?

    The status code is the answer where there is one. Otherwise it is a
    phrase the provider wrote in words, and the test is deliberately narrow:
    everything on this list says out loud that money is what is missing."""
    if getattr(exc, "status_code", None) == 402:
        return True
    text = str(err or "").lower()
    return any(p in text for p in _PHRASES)


def no_credit(config, store, provider, role, err, exc=None):
    """The provider says the account is empty: record it and ask for the stop.

    Returns True only when the machine's stop was actually asked for. False
    covers both "this was some other failure" and "this is it, but this run
    is not allowed to stop anything" -- a sim, a replay, smoke, a machine
    that is not his, or the escape hatch in the environment.

    The caller's own logging and its `return None` are untouched: the stop is
    something that happens as well, never instead."""
    global _asked
    if not looks_like_no_credit(err, exc):
        return False
    c = getattr(config, "downtime", None)
    if not bool(getattr(c, "enabled", False)) or not bool(getattr(c, "shutdown_on_no_credit", False)):
        return False
    if str(getattr(getattr(config, "clock", None), "mode", "")) != "live":
        return False
    if os.name != "nt":
        return False
    if os.environ.get("SCAIL_NO_SHUTDOWN"):
        logger.log(f"  [llm:{role}] the account is out of credit; SCAIL_NO_SHUTDOWN is set, "
                   f"so nothing is stopped")
        return False
    if _asked:
        return False
    _asked = True

    why = (f"the model provider answered that the account has no credit left "
           f"({provider}, asked for {role})")
    try:
        _mark(store, why)
    except Exception as e:
        logger.log(f"  [llm:{role}] the stop was not recorded on her save: {type(e).__name__}: {e}")
    cmd = str(getattr(c, "shutdown_command", "stopall.cmd") or "").strip()
    logger.log(f"  [llm:{role}] the account is out of credit; asking {cmd} to stop the machine, "
               f"and the stop is on her save so the next boot knows why she was away")
    try:
        _launch(cmd, why)
    except Exception as e:
        logger.log(f"  [llm:{role}] {cmd} could not be started: {type(e).__name__}: {e}")
        return False
    return True


def _mark(store, why):
    """This character's own marker, written the moment the decision exists.

    An existing marker is left alone: it is a stop this save has not been
    started again from yet, and the reason it carries is the older one."""
    if store is None:
        return
    if isinstance(store.get("stopped"), dict):
        return
    store.set("stopped", {"ts": time.time(), "why": why, "kind": "no_credit",
                          "by": "sim/downtime.py"})
    rows = [r for r in (store.get("stops", []) or []) if isinstance(r, dict)]
    rows.append({"stopped_ts": time.time(), "why": why, "kind": "no_credit"})
    store.set("stops", rows[-50:])


def _launch(cmd, why):
    """The stop tool, started and let go of.

    Detached and in its own process group, because the thing it is about to
    stop is this process: a child would be killed with its parent, and a
    child sharing the console would be killed with the console."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = cmd if os.path.isabs(cmd) else os.path.join(root, cmd)
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    argv = [os.environ.get("COMSPEC", "cmd.exe"), "/c", path, "--no-credit", why]
    subprocess.Popen(argv, cwd=root, creationflags=flags, close_fds=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
