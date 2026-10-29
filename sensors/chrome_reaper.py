"""Kill the Chrome left behind by a scraper that died without cleaning up.

`driver.quit()` in a `finally` covers a clean exit and a Ctrl-C. It does not
cover the two ways these processes actually end: the console window being
closed, and a force-kill. Neither runs Python's exit path at all, so chromedriver
and its Chrome survive with the profile still locked, and the next start either
fails on the lock or leaves a second tree behind. The MAL daemon's Chrome had
been up since 2026-08-20 across several restarts of everything around it.

So the rule is: **reap on the way in, not only on the way out.** Whatever
happened to the last run, a start owns its profile.

**Matched on the exact `--user-data-dir` value, never a substring.** This
matters more than it looks. Until 2026-09-09 these profiles were named as
extensions of another program's own -- his `C:\\ChromeProfile` was a prefix
of `C:\\ChromeProfileMAL` and `C:\\ChromeProfileTomoe` -- and a substring match
would have killed another program's Chrome. They live under `F:\\Chrome_Profiles` now,
one directory per owner, and his is beside them: the names no longer nest,
and the rule is unchanged, because a rule that holds only while the naming
happens to be careful is not one. Compare normalised full paths for equality
or do not kill.

Chrome's renderers do not carry the flag, and chromedriver carries a port
instead, so a match is an anchor: the whole tree above and below it goes.
"""
import os
import re

try:
    import psutil
except ImportError:      # the sensors are Windows-only; the tools are not
    psutil = None

_NAMES = ("chrome.exe", "chromedriver.exe")
_FLAG = re.compile(r'--?user-data-dir=("([^"]*)"|(\S+))')


def _profile_of(cmdline):
    """The exact profile a process was launched against, or ''."""
    m = _FLAG.search(cmdline or "")
    if not m:
        return ""
    return os.path.normpath(m.group(2) or m.group(3) or "").lower().rstrip("\\/")


def _norm(path):
    return os.path.normpath(path or "").lower().rstrip("\\/")


def find(profile):
    """Every process tree bound to this profile. Returns a list of psutil.Process
    roots, highest ancestor first."""
    if not psutil or not profile:
        return []
    want = _norm(profile)
    anchors = []
    procs = {}
    for p in psutil.process_iter(["pid", "name", "ppid", "cmdline"]):
        try:
            name = (p.info["name"] or "").lower()
            if name not in _NAMES:
                continue
            procs[p.info["pid"]] = p
            if _profile_of(" ".join(p.info["cmdline"] or [])) == want:
                anchors.append(p)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    # walk up while the parent is still one of ours: a matched Chrome tab was
    # started by a Chrome that was started by a chromedriver, and killing the
    # tab alone leaves the browser and the driver holding the lock
    roots = {}
    for p in anchors:
        top = p
        while True:
            try:
                parent = top.parent()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break
            if not parent:
                break
            try:
                if (parent.name() or "").lower() not in _NAMES:
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break
            top = parent
        roots[top.pid] = top
    return list(roots.values())


def kill(profile, log=print, keep=()):
    """Kill every tree on `profile`. `keep` is pids the caller still owns.

    Returns how many processes were killed."""
    if not psutil:
        return 0
    keep = set(keep or ())
    killed = 0
    for root in find(profile):
        if root.pid in keep:
            continue
        try:
            tree = root.children(recursive=True)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            tree = []
        for p in tree + [root]:
            if p.pid in keep:
                continue
            try:
                p.kill()
                killed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    if killed:
        log(f"[chrome] reaped {killed} leftover process(es) on {profile}")
    _unlock(profile, log)
    return killed


def _unlock(profile, log=print):
    """A killed Chrome leaves its singleton files behind and the next start
    refuses the profile. They are safe to remove once nothing is holding it."""
    for name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
        p = os.path.join(profile, name)
        try:
            if os.path.exists(p) or os.path.islink(p):
                os.remove(p)
        except OSError:
            pass


def reap_orphans(profile, log=print):
    """Only the trees nobody owns any more.

    `kill()` takes the profile off everybody, which is the right rule where one
    scraper owns its profile alone. The account profile is not that: the bot's
    scenery harvest, her X look and the MAL daemon all run against it, and a
    start that reaped the lot would cut off a session somebody else is in the
    middle of. What actually strands the profile is a force-kill -- the `finally`
    never runs, chromedriver outlives the python that made it, and the tree sits
    there holding the lock until something takes it off. A root whose parent is
    gone is exactly that and nothing else, so those, and only those.

    The singleton files come off only when nothing live is left; removing them
    under a running Chrome is how you get two browsers on one profile, which is
    the fault this is here to prevent."""
    if not psutil or not profile:
        return 0
    killed, live = 0, 0
    for root in find(profile):
        try:
            parent = root.parent()
            owned = parent is not None and parent.is_running()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            owned = False
        if owned:
            live += 1
            continue
        try:
            tree = root.children(recursive=True)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            tree = []
        for q in tree + [root]:
            try:
                q.kill()
                killed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    # A chromedriver whose Chrome has already exited is invisible to `find`:
    # matching anchors on `--user-data-dir`, and only Chrome carries it. Three
    # of them had piled up on this machine by the second day. One with no
    # browser under it and no python over it is serving nobody, whatever
    # profile it was once for, so it is safe to take without knowing.
    for q in (psutil.process_iter(["pid", "name", "ppid"]) if psutil else []):
        try:
            if (q.info["name"] or "").lower() != "chromedriver.exe":
                continue
            parent = q.parent()
            if parent is not None and parent.is_running():
                continue
            if q.children(recursive=True):
                continue
            q.kill()
            killed += 1
            log(f"[chrome] reaped an orphaned chromedriver ({q.info['pid']}) with no browser under it")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    if killed:
        log(f"[chrome] reaped {killed} orphaned process(es) on {profile}"
            + (f"; {live} live session(s) left alone" if live else ""))
        if not live:
            _unlock(profile, log)
    return killed


def install_exit_handler(profile, log=print, keep=lambda: ()):
    """Reap on the way out as well, for the exits Python does see.

    `atexit` covers a normal return and an unhandled exception. SIGTERM and
    SIGBREAK cover a `taskkill` without /F and the console close button on
    Windows. Nothing covers /F or a power cut, which is why `kill()` on start
    is the one that actually matters."""
    import atexit
    import signal

    done = {"ran": False}

    def _reap(*_a):
        if done["ran"]:
            return
        done["ran"] = True
        try:
            kill(profile, log=log, keep=keep())
        except Exception:
            pass

    atexit.register(_reap)
    for sig in ("SIGTERM", "SIGBREAK", "SIGINT"):
        s = getattr(signal, sig, None)
        if s is None:
            continue
        try:
            prev = signal.getsignal(s)

            def _handler(signum, frame, _prev=prev):
                _reap()
                if callable(_prev):
                    return _prev(signum, frame)
                raise KeyboardInterrupt

            signal.signal(s, _handler)
        except (ValueError, OSError):
            pass
    return _reap
