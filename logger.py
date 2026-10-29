import os
import json
import time
import shutil
import datetime
from pathlib import Path

# One directory per run under out_dir, named by wall-clock start time. Older
# run directories are zipped in place, never deleted.

_run_dir = None
_session_log = None
_llm_log = None


def _pid_alive(pid):
    try:
        import psutil
        return psutil.pid_exists(pid)
    except ImportError:
        return True  # cannot tell; leave the directory alone


def setup(out_dir):
    """One directory per run. A run leaves an ACTIVE file holding its pid;
    setup never archives a directory whose pid is still alive, so a dry run
    started next to the live bot cannot pull the live log out from under it."""
    global _run_dir, _session_log, _llm_log
    base = Path(out_dir).expanduser().resolve()
    base.mkdir(parents=True, exist_ok=True)
    for old in base.iterdir():
        if not old.is_dir():
            continue
        marker = old / "ACTIVE"
        if marker.exists():
            try:
                pid = int(marker.read_text().strip() or 0)
            except ValueError:
                pid = 0
            if pid and _pid_alive(pid):
                continue
        # not a run directory (the dry-run tree lives under here): leave it
        if not (old / "session.log").exists() and not marker.exists():
            continue
        zip_path = old.with_suffix(".zip")
        try:
            # a good archive from an earlier attempt (rmtree failed because a
            # tail held session.log) must never be overwritten by an empty one
            if zip_path.exists() and zip_path.stat().st_size > 200:
                pass
            elif any(old.iterdir()):
                shutil.make_archive(str(old), "zip", root_dir=str(old))
            shutil.rmtree(old)
        except Exception as e:
            print(f"[LOG] could not archive {old}: {e}")
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    # Two processes can start inside one second -- the restart brings up three
    # in a row, and a harness builds two -- and the second used to die on
    # FileExistsError before it had written a line. A letter after the stamp
    # keeps them apart and keeps the name sortable.
    _run_dir = base / stamp
    for suffix in ("", "b", "c", "d", "e", "f", "g", "h"):
        _run_dir = base / (stamp + suffix)
        try:
            _run_dir.mkdir()
            break
        except FileExistsError:
            continue
    else:
        _run_dir.mkdir(exist_ok=True)
    (_run_dir / "ACTIVE").write_text(str(os.getpid()))
    _session_log = _run_dir / "session.log"
    _llm_log = _run_dir / "llm_calls.jsonl"
    log(f"run directory {_run_dir}")
    return _run_dir


def setup_file(path):
    """Log to one fixed file rather than a run directory: for a process that
    belongs to the machine (machine/collector.py), whose runs are nobody's."""
    global _session_log
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    _session_log = p


def finish():
    """Drop the ACTIVE marker so the next boot may archive this run."""
    if _run_dir:
        try:
            (_run_dir / "ACTIVE").unlink()
        except OSError:
            pass


def run_dir():
    return _run_dir


def log(message, to_console=True):
    stamp = datetime.datetime.now().strftime("%H:%M:%S")
    line = f"[{stamp}] {message}"
    if to_console:
        try:
            print(line)
        except UnicodeEncodeError:
            print(line.encode("ascii", "replace").decode())
    if _session_log:
        with open(_session_log, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def log_llm(role, messages, content, reasoning, usage, seconds, extra=None):
    if not _llm_log:
        return
    rec = {
        "wall": datetime.datetime.now().isoformat(timespec="seconds"),
        "role": role,
        "seconds": round(seconds, 2),
        "usage": usage,
        "messages": messages,
        "content": content,
        "reasoning": reasoning
    }
    if extra:
        rec.update(extra)      # provider, served_by, model slug -- who actually answered
    with open(_llm_log, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def write_artifact(name, text):
    if not _run_dir:
        return
    with open(_run_dir / name, "a", encoding="utf-8") as f:
        f.write(text + "\n")
