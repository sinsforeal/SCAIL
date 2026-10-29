"""One check, then exit: is the MAL mirror daemon up, and is it stuck.

Run every 5 minutes by the scheduled task SCAIL_mal_watchdog
(tools/mal_watchdog_setup.ps1 registers it; mal_watchdog.cmd is the pythonw
wrapper it runs). This is NOT a second daemon -- it never opens
data/mal_history.db for writing and never touches Chrome. It only looks at
the process table and reads one row of the db read-only, then either does
nothing, or asks Task Scheduler to run SCAIL_mal again.

Two things it is built never to do, both because tools/mal_history.py daemon
is already the single writer of the mirror and this must stay true:
  - it never starts a second `daemon` process itself. It only ever runs
    `schtasks /run /tn SCAIL_mal`, which goes through mal_daemon.cmd, which
    goes through the SAME lock-file check the daemon already has
    (tools/mal_history.py:805-828, `_daemon_alive`) -- if one is somehow
    already up when this fires, the new one prints "already running" and
    exits at once.
  - it never touches Momoka, any other character, or tools/smoke.py. It
    matches exactly one process by exact command line -- the same regex
    tools/restart.ps1:110 uses for the same daemon -- and nothing else.

    python tools/mal_watchdog.py             # one check, prints + logs, exits
"""
import datetime
import os
import re
import sqlite3
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "data", "mal_history.db")
LOG_PATH = os.path.join(ROOT, "logs", "mal_watchdog.log")
TASK_NAME = "SCAIL_mal"

# Same pattern as tools/restart.ps1:110 ('mal' row, $KNOWN["mal"].Match) --
# one daemon, matched the same way everywhere it is matched.
MATCH = re.compile(r'mal_history\.py"?\s+daemon')

STALE_SECONDS = 30 * 60      # daemon_last_ts older than this while the pid is
                              # up means it is hung, not just mid-poll
RELAUNCH_WAIT_SECONDS = 10   # how long to give schtasks /run before checking
                              # whether the process actually came up
# Every child is launched hidden: this runs under pythonw, so an unhidden
# console child (schtasks) gets its own window, and with Windows Terminal as
# the default host that flashed on his desktop every 5 min (2026-10-21).
NO_WINDOW = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW


def log(msg):
    line = f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  {msg}"
    print(line, flush=True)
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8", errors="replace") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def find_daemon():
    """Every process whose command line matches the daemon's, exact pid list.
    Never image-name matching -- see tools/restart.ps1's Find-One for why."""
    import psutil
    out = []
    for p in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            info = p.info
            name = (info.get("name") or "").lower()
            cmdline = " ".join(info.get("cmdline") or [])
            if "python" in name and MATCH.search(cmdline):
                out.append(info["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return out


def read_daemon_last_ts():
    """meta.daemon_last_ts, read-only -- same access pattern as
    sensors/mal_monitor.py (mode=ro). Returns None if the db is missing or
    cannot be read right now (locked, mid-write); that is not itself a
    failure worth acting on."""
    if not os.path.exists(DB_PATH):
        return None
    try:
        con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=5)
        try:
            row = con.execute("SELECT value FROM meta WHERE key='daemon_last_ts'").fetchone()
        finally:
            con.close()
        return int(row[0]) if row and row[0] is not None else None
    except Exception as e:
        log(f"  could not read daemon_last_ts: {type(e).__name__}: {e}")
        return None


def relaunch():
    """schtasks /run /tn SCAIL_mal -- the exact mechanism restart.ps1's
    Start-One uses. /end first, same reason Start-One does it: a task left
    at RUNNING (it should not be, the daemon detaches and mal_daemon.cmd
    exits at once, but be sure) would otherwise swallow the /run silently."""
    subprocess.run(["schtasks", "/end", "/tn", TASK_NAME], capture_output=True, text=True,
                   creationflags=NO_WINDOW)
    time.sleep(1)
    r = subprocess.run(["schtasks", "/run", "/tn", TASK_NAME], capture_output=True, text=True,
                       creationflags=NO_WINDOW)
    if r.returncode != 0:
        log(f"  schtasks /run /tn {TASK_NAME} failed (exit {r.returncode}): "
            f"{(r.stdout or r.stderr or '').strip()}")
        return False
    time.sleep(RELAUNCH_WAIT_SECONDS)
    after = find_daemon()
    if len(after) == 1:
        log(f"  relaunch ok -- pid {after[0]} is up")
        return True
    log(f"  relaunch did not come up cleanly (now matches {len(after)} process(es): {after})")
    return False


def main():
    procs = find_daemon()

    if len(procs) > 1:
        # never guess which one is the real daemon -- same refusal
        # tools/restart.ps1's Stop-One/Start-IfDown make on a double match.
        log(f"REFUSING: {len(procs)} processes match the daemon's command line "
            f"({procs}); not touching any of them. Look at them by hand.")
        return 0

    if len(procs) == 0:
        log("daemon not running; relaunching via schtasks /run /tn SCAIL_mal")
        relaunch()
        return 0

    pid = procs[0]
    ts = read_daemon_last_ts()
    if ts is None:
        log(f"daemon pid {pid} is up; meta.daemon_last_ts unreadable right now (db missing "
            f"or busy) -- skipping the staleness check this pass")
        return 0

    age = int(time.time()) - ts
    # A freshly relaunched daemon has not written daemon_last_ts yet; judging it
    # by the old value killed it every 5 min in a loop (2026-10-21 09:47-10:56).
    try:
        import psutil
        up_s = int(time.time() - psutil.Process(pid).create_time())
    except Exception:
        up_s = None
    if age > STALE_SECONDS and up_s is not None and up_s < STALE_SECONDS:
        log(f"daemon pid {pid} up {up_s}s, daemon_last_ts {age}s old -- still in its grace "
            f"window ({STALE_SECONDS}s from start), not judged yet")
        return 0
    if age > STALE_SECONDS:
        log(f"daemon pid {pid} is up but daemon_last_ts is {age}s old (> {STALE_SECONDS}s) "
            f"-- looks hung; killing pid {pid} and relaunching")
        try:
            import psutil
            psutil.Process(pid).kill()
            time.sleep(2)
        except Exception as e:
            log(f"  could not kill pid {pid}: {type(e).__name__}: {e}")
        relaunch()
    else:
        log(f"daemon pid {pid} up, last tick {age}s ago -- ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
