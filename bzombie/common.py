"""Shared paths and small helpers for the bench harness. Stdlib only."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

VAR = Path(os.environ.get("BZ_VAR", r"H:\SCAIL\bzombie\var"))
PROFILES = VAR / "profiles"
ENV_CACHE = VAR / "env_cache"
HIDE = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
ARM_BASE_PORT = {"S": 18331, "P": 18341}
PEER_BASE_PORT = 18361  # second and later minds of one run (tk-1pl); 18361-18369, outside the S and P ranges
GATEWAY = "http://127.0.0.1:18330"
VIEWER_PORT = 18350
TEMP_DIR = r"H:\SCAIL\temp"


def run_dir(run_id: str) -> Path:
    return VAR / "runs" / run_id


def replace_retry(src, dst, tries: int = 40) -> None:
    """os.replace that waits out Windows sharing violations (PermissionError while another handle reads dst)."""
    for n in range(tries):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if n == tries - 1:
                raise
            time.sleep(0.01 * (n + 1) if n < 10 else 0.1)


def read_json(p, default=None):
    for n in range(20):
        try:
            return json.loads(Path(p).read_text(encoding="utf-8"))
        except PermissionError:  # a writer is mid-replace on Windows; the file is there, try again
            time.sleep(0.01 * (n + 1))
        except (OSError, ValueError):
            return default
    return default


def write_json(p, obj) -> None:
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    replace_retry(tmp, p)


def append_jsonl(p, obj) -> None:
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def read_jsonl(p) -> list:
    out = []
    try:
        with open(p, encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if ln:
                    try:
                        out.append(json.loads(ln))
                    except ValueError:
                        pass
    except OSError:
        pass
    return out


def parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s)


def iso(d: datetime) -> str:
    return d.isoformat(timespec="seconds")


def norm_ts(v, tz: str = "Asia/Tokyo") -> str:
    """An arm may report virtual_ts as epoch seconds (S does); the run files carry naive local ISO (clock_start's form)."""
    if isinstance(v, (int, float)):
        from zoneinfo import ZoneInfo
        return iso(datetime.fromtimestamp(v, ZoneInfo(tz)).replace(tzinfo=None))
    return v


TOKYO = "Asia/Tokyo"


def to_him(dt: datetime, him_tz: str | None) -> datetime:
    """Virtual time (naive Tokyo, the one timeline) as the wall clock in his zone (naive)."""
    if not him_tz or him_tz == TOKYO:
        return dt
    from zoneinfo import ZoneInfo
    return dt.replace(tzinfo=ZoneInfo(TOKYO)).astimezone(ZoneInfo(him_tz)).replace(tzinfo=None)


def from_him(dt: datetime, him_tz: str | None) -> datetime:
    """His wall clock (naive, his zone) back onto the Tokyo timeline."""
    if not him_tz or him_tz == TOKYO:
        return dt
    from zoneinfo import ZoneInfo
    return dt.replace(tzinfo=ZoneInfo(him_tz)).astimezone(ZoneInfo(TOKYO)).replace(tzinfo=None)


def hidden_env() -> dict:
    e = dict(os.environ)
    e["TEMP"] = e["TMP"] = TEMP_DIR
    return e


def pythonw() -> str:
    exe = Path(sys.executable)
    w = exe.with_name("pythonw.exe")
    return str(w if w.exists() else exe)


def spawn_hidden(args: list, log_path=None, cwd=None, env_extra=None) -> subprocess.Popen:
    """Hidden process (CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP), output to log_path.
    Never DETACHED_PROCESS: with CREATE_NO_WINDOW it flashed a console (meta 10-22 17:14)."""
    out = open(log_path, "ab") if log_path else subprocess.DEVNULL
    return subprocess.Popen(args, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                            creationflags=HIDE | (0x00000200 if os.name == "nt" else 0),
                            cwd=cwd, env={**hidden_env(), **(env_extra or {})}, close_fds=True)


def day_start(clock_start: str, day: int) -> datetime:
    d = parse_ts(clock_start)
    return d.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=day)
