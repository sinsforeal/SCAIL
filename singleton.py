"""One bot, one save file. Enforced, not asked for.

On 2026-08-19 two copies of `scail.py` ran at once for about twenty minutes.
Telegram's `getUpdates` hands an update to whoever asks with an offset that has
not passed it yet, so both processes were told about the same message and both
called `store.add_message`:

    2026-08-19_16-39-58   [21:46:16] [him] do you eat anything other than melon pan?
    2026-08-19_21-40-43   [21:46:12] [him] do you eat anything other than melon pan?

rows 254 and 255, identical text, identical `tg_id` 619. Same again at 21:58.
Her unread queue held it twice, the persona saw it twice, both copies were
marked read, and both processes answered.

The rule "never run two copies" was written in CLAUDE.md and a rule is not a
mechanism. This is the mechanism.

Liveness is psutil plus a cmdline match, and both halves matter. `OpenProcess`
returns a usable handle for a process that has already exited, which is exactly
how the MAL daemon spent three days refusing to restart against its own corpse;
and pids are recycled, so a lock naming a pid that now belongs to something
else must not wedge the bot shut forever.

The cmdline the lock compares against is the one the HOLDER wrote when it took
the lock, on the second line of the file. It used to be a fixed string,
`scail.py`, which stopped matching the day the runtime moved behind
`tomoe/run.py` and `resident/run.py`: every live bot then read as dead, so
`holder()` returned 0 for a save a bot was sitting on and `acquire()` would
have taken the lock over and started a second copy -- the fault this module
exists to prevent, inert for as long as the two programs have existed. A
holder that records its own command line needs no guess about what a bot is
called. A lock file from before this (a bare pid) still falls back to `marker`.
"""
import os

import logger


class AlreadyRunning(Exception):
    pass


class Singleton:
    def __init__(self, path, marker="run.py"):
        self.path = path
        self.marker = marker
        self.taken = False

    def _read(self):
        """(pid, the command line the holder wrote, or "")."""
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                parts = (f.read() or "").split("\n", 1)
            return int((parts[0] or "0").strip() or 0), (parts[1].strip() if len(parts) > 1 else "")
        except (OSError, ValueError):
            return 0, ""

    def _alive(self, pid, cmdline=""):
        if not pid:
            return False
        try:
            import psutil
            p = psutil.Process(pid)
            if not p.is_running() or p.status() == psutil.STATUS_ZOMBIE:
                return False
            live = " ".join(p.cmdline() or [])
            # the holder's own command line is the exact test; `marker` is the
            # fallback for a lock file written before holders recorded it
            return live == cmdline if cmdline else (self.marker in live)
        except Exception:
            return False

    def _own_cmdline(self):
        try:
            import psutil
            return " ".join(psutil.Process(os.getpid()).cmdline() or [])
        except Exception:
            return ""

    def holder(self):
        """The pid of the live process holding this save, or 0. For anything
        that wants to know whether a bot is up before touching its save --
        `yukarin/week/patch_live.py` refuses to write behind a running one.
        The liveness test belongs here rather than at the caller: a handle
        opens for a process that has already exited, and pids are recycled."""
        pid, cmdline = self._read()
        return pid if self._alive(pid, cmdline) else 0

    def acquire(self):
        """Raises AlreadyRunning when another live bot holds it."""
        pid, cmdline = self._read()
        if pid and pid != os.getpid() and self._alive(pid, cmdline):
            raise AlreadyRunning(f"another bot is already running (pid {pid})")
        if pid:
            logger.log(f"[lock] the lock named pid {pid}, which is gone; taking it over")
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(f"{os.getpid()}\n{self._own_cmdline()}")
        self.taken = True
        return self

    def release(self):
        if not self.taken:
            return
        try:
            if self._read()[0] != os.getpid():
                return              # somebody else owns it now; leave theirs alone
            os.remove(self.path)
        except (OSError, ValueError):
            pass
        self.taken = False
