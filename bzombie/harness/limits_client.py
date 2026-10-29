"""limits client: read the limits manager's state and pass its work gate. Stdlib only, one file, copy it as is.

    from limits_client import granted, host_verdict, token_order      # file name in the tree is yours
    with granted(who="bench/backtest", need={"cpu": 4, "mem_gb": 8}, prio="background") as t:
        run_the_job()                      # t.host is the host the manager chose ("here" or "laptop")

    python client.py status
    python client.py wait --who X --cpu 4 --mem-gb 8 --vram-mb 0 --host any --prio normal --timeout 3600
    python client.py release <ticket>

Where the manager lives: env LIMITS_ROOT, else F:\\REPS2\\Meta_Orchestrator; `--root` overrides both on the CLI and
every function takes `root=`. State is <root>/var/limits/state.json, tickets are <root>/var/limits/work_queue/.

Fail-open policy (decided 2026-10-14): when the manager is absent or state.json is older than max_age_s, `wait`
returns True after one stderr line "limits manager absent, running ungated", because a stopped manager must not
stop every job on both machines. The in-session hooks and each tree's local caps stay the hard stop. A missing
state is never an error to the caller; no function here raises on a bad or missing store.

Host verdicts (manager word -> client word): free -> free, busy -> busy, exclusive -> closed (a shift is open or
his GPU job runs: the PC takes nothing heavy), unknown or no fresh state -> unknown.

A ticket's `pid` is a PC process id: the manager frees the grant when that pid is dead. A job on the laptop is
ticketed either by the PC process that launches it (host="laptop", its PC pid), or by the laptop itself through
the manager's loopback bridge: `request(..., host="laptop", url="http://127.0.0.1:<port>")`, CLI `--url`. The
laptop never writes into this root; a bridge ticket has no pid and lives until released or its ttl.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

DEFAULT_ROOT = r"F:\REPS2\Meta_Orchestrator"
LEVELS = ("user", "shift", "high", "normal", "background")
HOSTS = ("any", "here", "laptop")
DEFAULT_TTL_S = 14400
# keep equal to manager.TOKEN_ORDER (a test compares them)
TOKEN_ORDER = {"green": "normal", "amber": "finish_current", "red": "no_new_agents", "closed": "stop_at_limit"}
VERDICT_WORD = {"free": "free", "busy": "busy", "exclusive": "closed"}
ABSENT_LINE = "limits manager absent, running ungated"


def root_path(root=None) -> Path:
    return Path(root or os.environ.get("LIMITS_ROOT") or DEFAULT_ROOT)


def state_path(root=None) -> Path:
    return root_path(root) / "var" / "limits" / "state.json"


def queue_dir(root=None) -> Path:
    return root_path(root) / "var" / "limits" / "work_queue"


def read_state(max_age_s: float = 180, root=None, now=time.time):
    """state.json as a dict, or None when it is missing, unreadable, not a dict or older than max_age_s."""
    try:
        p = state_path(root)
        st = None
        for attempt in range(4):  # Windows: a read can collide with the manager's os.replace; retry briefly
            try:
                st = json.loads(p.read_text(encoding="utf-8"))
                break
            except FileNotFoundError:
                return None
            except (OSError, ValueError):
                if attempt == 3:
                    return None
                time.sleep(0.05)
        if not isinstance(st, dict):
            return None
        at = st.get("written_at_epoch")
        if not isinstance(at, (int, float)):
            at = p.stat().st_mtime
        if now() - float(at) > max_age_s:
            return None
        return st
    except Exception:
        return None


def host_verdict(host: str, max_age_s: float = 180, root=None) -> str:
    """free, busy, closed or unknown for "here" or "laptop"."""
    st = read_state(max_age_s, root)
    try:
        h = (st or {}).get("hosts", {}).get(host) or {}
        if h.get("unknown"):
            return "unknown"
        return VERDICT_WORD.get(h.get("verdict"), "unknown")
    except Exception:
        return "unknown"


def token_order(max_age_s: float = 180, root=None) -> str:
    """normal, finish_current, no_new_agents, stop_at_limit, or unknown when the manager is absent or stale."""
    st = read_state(max_age_s, root)
    try:
        tokens = (st or {}).get("tokens") or {}
        return TOKEN_ORDER.get(tokens.get("autonomous_verdict", tokens.get("verdict")), "unknown")
    except Exception:
        return "unknown"


def lane_info(max_age_s: float = 180, root=None) -> dict | None:
    """The manager's lane record {"value", "since", "reason", "home_account"}, or None when the state is
    missing, stale or has no lane."""
    st = read_state(max_age_s, root)
    try:
        lane = (st or {}).get("lane")
        return lane if isinstance(lane, dict) and isinstance(lane.get("value"), str) else None
    except Exception:
        return None


def lane(max_age_s: float = 180, root=None) -> str:
    """api, subscription, wind_down, blocked, or unknown. Missing/stale/invalid state is
    unknown, never implicit permission to consume the autonomous subscription reserve."""
    info = lane_info(max_age_s, root)
    value = info.get("value") if info else None
    return value if value in ("api", "subscription", "wind_down", "blocked") else "unknown"


def _norm_need(need) -> dict:
    n = need or {}
    return {"cpu": float(n.get("cpu") or 0), "mem_gb": float(n.get("mem_gb") or 0),
            "vram_mb": float(n.get("vram_mb") or 0)}


DISK_CLASSES = ("bulk", "light")


def _norm_disk(disk):
    """{"vols": [...], "class": "bulk"|"light"} from a list/str of volume keys or that dict; None for none."""
    if not disk:
        return None
    if isinstance(disk, str):
        disk = [v for v in re.split(r"[,\s]+", disk) if v]
    if isinstance(disk, (list, tuple)):
        disk = {"vols": list(disk), "class": "bulk"}
    if not isinstance(disk, dict):
        raise ValueError("disk must be a list of volume keys or {vols, class}")
    vols = disk.get("vols")
    vols = [v for v in re.split(r"[,\s]+", vols) if v] if isinstance(vols, str) else list(vols or [])
    cls = str(disk.get("class") or "bulk")
    if cls not in DISK_CLASSES:
        raise ValueError(f"disk class must be one of {DISK_CLASSES}")
    vols = [str(v) for v in vols if v]
    return {"vols": vols, "class": cls} if vols else None


def _safe(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.]", "_", s or "job")[:40] or "job"


def _http(url: str, path: str, body=None, timeout: float = 10):
    """JSON round trip to the bridge; the dict reply, or None when it is unreachable or answers badly."""
    try:
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(url.rstrip("/") + path, data=data,
                                     headers={"Content-Type": "application/json"} if data else {})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read())
        return d if isinstance(d, dict) else None
    except Exception:
        return None


def refusal_line(ticket: str, rec: dict) -> str:
    fix = rec.get("fix")
    return "limits gate: REFUSED %s: %s (%s); the need is above what the host could ever grant, it can never be granted%s" % (
        ticket, rec.get("reason"), rec.get("detail") or "no detail", "; fix: " + fix if fix else "")


class Refused(TimeoutError):
    """granted() raises this (a TimeoutError subclass) when the manager refused the ticket."""


class Ticket:
    def __init__(self, ticket: str, rec: dict, root=None, url=None):
        self.ticket = ticket
        self.rec = rec
        self.root = root
        self.url = url  # bridge base URL: the laptop route, no shared filesystem
        self.host = None  # set by wait() when granted
        self.worker_cap = None  # set by wait() for a laptop grant: max parallel workers the job may run
        self.ungated = False  # True when wait() fell open
        self.refused = None  # set by wait() to {reason, detail, ...} when the manager refused the ticket

    def __repr__(self):
        return f"Ticket({self.ticket!r}, host={self.host!r})"

    @property
    def path(self) -> Path:
        return queue_dir(self.root) / f"{self.ticket}.json"

    def granted_host(self, max_age_s: float = 180):
        st = read_state(max_age_s, self.root)
        g = ((st or {}).get("grants") or {}).get(self.ticket) if st else None
        return (g or {}).get("host") if isinstance(g, dict) else None

    def wait(self, timeout_s: float = 3600, poll_s: float = 5, max_age_s: float = 180,
             sleep=time.sleep, now=time.time) -> bool:
        """True when granted, or when the manager is absent or stale (fail-open, one stderr line).
        False on timeout (the ticket file is removed then) or at once when the manager refused the ticket
        (need above the host's total capacity): self.refused holds the record, one stderr line names it."""
        t0 = now()
        while True:
            if self.url:
                g = _http(self.url, f"/grant/{self.ticket}")
                if g is None or g.get("absent") or (g.get("state_age_s") or 0) > max_age_s:
                    print(ABSENT_LINE, file=sys.stderr)
                    self.ungated = True
                    return True
                if isinstance(g.get("refused"), dict):
                    return self._refuse(g["refused"])
                if g.get("granted"):
                    self.host = g.get("host")
                    self.worker_cap = g.get("worker_cap")
                    return True
                if now() - t0 >= timeout_s:
                    self.release()
                    return False
                sleep(poll_s)
                continue
            st = read_state(max_age_s, self.root, now=now)
            if st is None:
                print(ABSENT_LINE, file=sys.stderr)
                self.ungated = True
                return True
            g = (st.get("grants") or {}).get(self.ticket)
            if isinstance(g, dict):
                self.host = g.get("host")
                self.worker_cap = g.get("worker_cap")
                return True
            rf = ((st.get("queue") or {}).get("refused") or {}).get(self.ticket)
            if isinstance(rf, dict):
                return self._refuse(rf)
            if now() - t0 >= timeout_s:
                self.release()
                return False
            sleep(poll_s)

    def _refuse(self, rec: dict) -> bool:
        self.refused = rec
        print(refusal_line(self.ticket, rec), file=sys.stderr)
        self.release()
        return False

    def release(self) -> None:
        """Remove the ticket file. Idempotent. The manager frees the grant on its next pass."""
        if self.url:
            _http(self.url, "/release", {"ticket": self.ticket})
            return
        try:
            os.unlink(self.path)
        except OSError:
            pass


def request(who: str, need=None, host: str = "any", prio: str = "normal", ttl_s: float = DEFAULT_TTL_S,
            heavy: bool = False, pid=None, root=None, now=time.time, url=None, disk=None) -> Ticket:
    """Write a ticket file (atomic: temp name the manager does not glob, then replace) and return its Ticket.

    host is the placement asked for: any (default), here or laptop; it is recorded on the ticket.
    pid defaults to this process; pass 0 for none (held by ttl only). Ticket id: <who>-<pid>-<epoch ms>.
    url: the manager's loopback bridge as seen from this machine (the laptop route). Nothing is written
    locally; the bridge writes the ticket with host=laptop and no pid. Bridge unreachable: an ungated
    Ticket (wait() then returns True with the ABSENT_LINE), the same fail-open as a missing state.
    disk: volume keys a bulk copy will saturate, e.g. disk=["F", "lan_laptop"] or {"vols": [...], "class": "bulk"}
    (class "light" is recorded, never held). The manager admits at most N bulk tickets per volume at once.
    Without disk the ticket is exactly as before."""
    disk = _norm_disk(disk)
    if host not in HOSTS:
        raise ValueError(f"host must be one of {HOSTS}")
    if prio not in LEVELS:
        raise ValueError(f"prio must be one of {LEVELS}")
    if url:
        if host == "here":
            raise ValueError("a bridge ticket is for the laptop: host must be laptop or any")
        body = {"who": who, "need": _norm_need(need), "prio": prio, "ttl_s": float(ttl_s), "heavy": bool(heavy)}
        if disk:
            body["disk"] = disk
        r = _http(url, "/ticket", body)
        tid = (r or {}).get("ticket") or f"{_safe(who)}-unreached-{int(now() * 1000)}"
        return Ticket(tid, r or {}, root, url)
    pid = os.getpid() if pid is None else pid
    q = queue_dir(root)
    q.mkdir(parents=True, exist_ok=True)
    ms = int(now() * 1000)
    while True:
        tid = f"{_safe(who)}-{pid}-{ms}"
        if not (q / f"{tid}.json").exists():
            break
        ms += 1
    rec = {"ticket": tid, "who": who, "need": _norm_need(need), "host": host, "prio": prio,
           "ttl_s": float(ttl_s), "created": now(), "pid": pid or None, "heavy": bool(heavy)}
    if disk:
        rec["disk"] = disk
    tmp = q / f"{tid}.json.tmp"
    tmp.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    os.replace(tmp, q / f"{tid}.json")
    return Ticket(tid, rec, root)


@contextlib.contextmanager
def granted(who: str, need=None, host: str = "any", prio: str = "normal", ttl_s: float = DEFAULT_TTL_S,
            heavy: bool = False, pid=None, timeout_s: float = 3600, poll_s: float = 5, root=None, url=None,
            disk=None):
    """request + wait + release. Raises TimeoutError when not granted within timeout_s (ticket already removed)."""
    t = request(who, need, host, prio, ttl_s, heavy, pid, root, url=url, disk=disk)
    try:
        if not t.wait(timeout_s, poll_s):
            if t.refused:
                raise Refused(refusal_line(t.ticket, t.refused))
            raise TimeoutError(f"limits gate: no grant for {t.ticket} within {timeout_s} s")
        yield t
    finally:
        t.release()


# ---------------------------------------------------------------- CLI

RECENT_S = 900  # status shows hold and refusal reasons of the last 15 min


def events_path(root=None) -> Path:
    return root_path(root) / "var" / "limits" / "events.jsonl"


def recent_holds(root=None, now=None, span_s: float = RECENT_S, tail_bytes: int = 400000) -> dict:
    """{ticket: event} the last `hold` or `refuse` event per ticket within span_s, read from the tail of
    events.jsonl. {} when the file is missing or unreadable."""
    from datetime import datetime
    out = {}
    try:
        p = events_path(root)
        with open(p, "rb") as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - tail_bytes))
            lines = f.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return out
    for ln in lines:
        try:
            e = json.loads(ln)
            if e.get("kind") not in ("hold", "refuse") or not e.get("ticket"):
                continue
            age = (now or time.time)() - datetime.fromisoformat(str(e["at"]).replace("Z", "+00:00")).timestamp()
        except (ValueError, TypeError, KeyError):
            continue
        if 0 <= age <= span_s:
            out[e["ticket"]] = dict(e, age_s=round(age))
    return out


def cmd_status(a) -> int:
    st = read_state(a.max_age, a.root)
    if st is None:
        print(f"manager: absent or stale ({state_path(a.root)})")
        return 0
    print(f"manager: ok, state {round(time.time() - st.get('written_at_epoch', time.time()))} s old")
    print(f"token_order: {token_order(a.max_age, a.root)}")
    for h in ("here", "laptop"):
        print(f"{h}: {host_verdict(h, a.max_age, a.root)}")
    for tid, g in (st.get("grants") or {}).items():
        print(f"granted {tid} {g.get('host')} {g.get('prio')} {g.get('who')}")
    for w in (st.get("queue") or {}).get("waiting_tickets") or []:
        why = f" HOLD {w.get('hold_reason')} ({w.get('hold_detail') or 'no detail'})" if w.get("hold_reason") else ""
        print(f"waiting {w.get('ticket')} {w.get('host')} {w.get('prio')} {w.get('who')} {w.get('waited_s')} s{why}")
    shown = {w.get("ticket") for w in (st.get("queue") or {}).get("waiting_tickets") or []}
    shown |= set((st.get("grants") or {}).keys())
    for tid, e in recent_holds(a.root).items():
        if tid in shown:
            continue
        word = "REFUSED" if e.get("kind") == "refuse" else "HOLD"
        print(f"recent {tid} {e.get('host')} {e.get('who')} {word} {e.get('reason')} "
              f"({e.get('detail') or 'no detail'}) {e.get('age_s')} s ago")
    return 0


def cmd_wait(a) -> int:
    pid = os.getppid() if a.pid is None else a.pid  # this CLI exits after the grant: tie it to the caller
    t = request(a.who, {"cpu": a.cpu, "mem_gb": a.mem_gb, "vram_mb": a.vram_mb}, a.host, a.prio,
                a.ttl, a.heavy, pid, a.root, url=a.url, disk={"vols": a.disk, "class": a.disk_class} if a.disk else None)
    if t.wait(a.timeout, a.poll, a.max_age):
        print(f"{t.host or 'ungated'} {t.ticket}")
        return 0
    if t.refused:
        return 4  # refusal line already on stderr
    print(f"timeout without a grant: {t.ticket}", file=sys.stderr)
    return 3


def cmd_release(a) -> int:
    Ticket(a.ticket, {}, a.root, a.url).release()
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="limits client")
    ap.add_argument("--root", default=None)
    ap.add_argument("--max-age", type=float, default=180)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    w = sub.add_parser("wait")
    w.add_argument("--who", required=True)
    w.add_argument("--cpu", type=float, default=0)
    w.add_argument("--mem-gb", type=float, default=0)
    w.add_argument("--vram-mb", type=float, default=0)
    w.add_argument("--host", default="any", choices=HOSTS)
    w.add_argument("--prio", default="normal", choices=LEVELS)
    w.add_argument("--ttl", type=float, default=DEFAULT_TTL_S)
    w.add_argument("--timeout", type=float, default=3600)
    w.add_argument("--poll", type=float, default=5)
    w.add_argument("--heavy", action="store_true")
    w.add_argument("--disk", default=None, help="volume keys the job saturates, comma separated, e.g. F,lan_laptop")
    w.add_argument("--disk-class", default="bulk", choices=DISK_CLASSES, help="bulk (default) is serialized per volume")
    w.add_argument("--url", default=None, help="bridge URL (laptop route), e.g. http://127.0.0.1:47615")
    w.add_argument("--pid", type=int, default=None, help="PC pid the grant lives with (default: the parent; 0 = ttl only)")
    r = sub.add_parser("release")
    r.add_argument("ticket")
    r.add_argument("--url", default=None, help="bridge URL when the ticket was requested through it")
    a = ap.parse_args(argv)
    return {"status": cmd_status, "wait": cmd_wait, "release": cmd_release}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
