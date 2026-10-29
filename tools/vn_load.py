"""Run one user-requested VN load outside the character process.

The request comes from the local stage. This tool alone reads the operator's
character register; a character never reads another character's files.
"""

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from tools.registry import characters
from tools.vn_saves import restore_slot, validate_slot


ROOT = Path(__file__).resolve().parent.parent


def _status(path, request_id, phase, **fields):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"request_id": request_id, "phase": phase,
            "updated_utc": dt.datetime.now(dt.timezone.utc).isoformat(), **fields}
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _restart(target, mode, log):
    proc = subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(ROOT / "tools" / "restart.ps1"),
         "-Target", target, mode, "-NoSmoke"],
        cwd=ROOT, capture_output=True, text=True, errors="replace", timeout=120)
    with open(log, "a", encoding="utf-8") as f:
        f.write(f"{mode}: exit {proc.returncode}\n{proc.stdout}\n{proc.stderr}\n")
    if proc.returncode:
        raise RuntimeError(f"restart {mode} failed; see {log}")


def run(slot_id, db_path, state_path, saves_dir, status_path, request_id):
    if Path(slot_id).name != slot_id or slot_id.startswith("."):
        raise ValueError("invalid slot id")
    db = Path(db_path).resolve()
    state = Path(state_path).resolve()
    saves = Path(saves_dir).resolve()
    if state.parent != saves.parent:
        raise ValueError("the stage and save directories do not match")
    matching = [r for r in characters()
                if (ROOT / r["db"]).resolve() == db]
    if len(matching) != 1:
        raise ValueError("database does not name one registered character")
    target = matching[0]["key"]
    slot = saves / slot_id
    validate_slot(slot)
    log = saves / "load.log"
    _status(status_path, request_id, "stopping", slot=slot_id)
    # Give the HTTP reply time to reach the page before the restart stops it.
    time.sleep(1)
    _restart(target, "-StopOnly", log)
    error = None
    recovery = None
    try:
        _status(status_path, request_id, "restoring", slot=slot_id)
        recovery = restore_slot(slot, db, state)
    except Exception as exc:
        error = str(exc)
    _status(status_path, request_id, "starting", slot=slot_id)
    try:
        _restart(target, "-StartOnly", log)
    except Exception as exc:
        error = (error + "; " if error else "") + str(exc)
    _status(status_path, request_id, "error" if error else "ready",
            slot=slot_id, recovery=recovery, error=error)
    if error:
        raise RuntimeError(error)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--slot", required=True)
    p.add_argument("--db", required=True)
    p.add_argument("--state", required=True)
    p.add_argument("--saves", required=True)
    p.add_argument("--status", required=True)
    p.add_argument("--request-id", required=True)
    args = p.parse_args()
    try:
        run(args.slot, args.db, args.state, args.saves, args.status, args.request_id)
    except Exception as exc:
        _status(args.status, args.request_id, "error", slot=args.slot, error=str(exc))
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
