"""Consistent, immutable VN save slots and an offline restore.

The database is the simulation context. The stage file records the line the
player is seeing and the remaining bubbles, which live only in the browser.
Restore is deliberately offline: a running App has cached simulation objects
and an open SQLite connection that cannot safely be replaced underneath it.
"""

import argparse
from contextlib import closing
import datetime as dt
import gzip
import json
import os
import shutil
import socket
import sqlite3
import uuid
from pathlib import Path

from tools.dbcopy import copy_db


def _atomic_json(path, value):
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _valid_stage(stage):
    if not isinstance(stage, dict) or not isinstance(stage.get("current"), dict):
        raise ValueError("current stage frame is required")
    current = stage["current"]
    pending = stage.get("pending", [])
    if not isinstance(pending, list) or len(pending) > 100 or any(not isinstance(x, dict) for x in pending):
        raise ValueError("invalid pending stage frames")
    turns = [current.get("turn")] + [x.get("turn") for x in pending]
    if any(type(t) is not int or t < 0 for t in turns):
        raise ValueError("invalid stage turn")
    if turns != sorted(set(turns)):
        raise ValueError("stage turns must increase without duplicates")
    return {"current": current, "pending": pending}


def create_slot(db_path, saves_dir, stage, *, latest_turn=None):
    """Take a SQLite online backup and publish it only after both files exist."""
    stage = _valid_stage(stage)
    if latest_turn is not None and max(x["turn"] for x in [stage["current"], *stage["pending"]]) != latest_turn:
        raise ValueError("stage has advanced; refresh before saving")
    saves = Path(saves_dir)
    saves.mkdir(parents=True, exist_ok=True)
    slot = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    temp = saves / ("." + slot + ".tmp")
    final = saves / slot
    temp.mkdir()
    try:
        copy_db(str(db_path), str(temp / "world.db"))
        with closing(sqlite3.connect(temp / "world.db")) as con:
            ok = con.execute("PRAGMA quick_check").fetchone()[0]
            if ok != "ok":
                raise RuntimeError("snapshot failed SQLite quick_check: " + str(ok))
            scene = con.execute("SELECT value FROM kv WHERE key='active_scene'").fetchone()
        meta = {
            "version": 1,
            "id": slot,
            "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "scene_id": json.loads(scene[0]) if scene else "main",
            "turn": stage["current"]["turn"],
            "text": str(stage["current"].get("text") or "")[:160],
            "pending_count": len(stage["pending"]),
            "place": str((stage["current"].get("scene") or {}).get("place") or "")[:80],
            "background_url": str((stage["current"].get("scene") or {}).get("url") or ""),
            "face_url": str(stage["current"].get("face") or ""),
        }
        _atomic_json(temp / "stage.json", stage)
        _atomic_json(temp / "meta.json", meta)
        os.replace(temp, final)
        return meta
    except BaseException:
        shutil.rmtree(temp, ignore_errors=True)
        raise


def create_line_checkpoint(db_path, checkpoints_dir, frame, msg_id):
    """Keep the context immediately after one delivered line, compressed."""
    stage = _valid_stage({"current": frame, "pending": []})
    root = Path(checkpoints_dir)
    root.mkdir(parents=True, exist_ok=True)
    slot = "line-" + uuid.uuid4().hex
    temp, final = root / ("." + slot + ".tmp"), root / slot
    temp.mkdir()
    try:
        raw = temp / "world.db"
        copy_db(str(db_path), str(raw))
        with open(raw, "rb") as source, gzip.open(temp / "world.db.gz", "wb", compresslevel=1) as out:
            shutil.copyfileobj(source, out)
        raw.unlink()
        meta = {"version": 1, "kind": "line", "id": slot,
                "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                "turn": frame["turn"], "turn_id": frame.get("turn_id"),
                "msg_id": int(msg_id),
                "text": str(frame.get("text") or "")[:160]}
        _atomic_json(temp / "stage.json", stage)
        _atomic_json(temp / "meta.json", meta)
        os.replace(temp, final)
        return meta
    except BaseException:
        shutil.rmtree(temp, ignore_errors=True)
        raise


def list_slots(saves_dir):
    rows = []
    for path in Path(saves_dir).glob("*/meta.json"):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
            if row.get("id") == path.parent.name and (path.parent / "world.db").is_file() and (path.parent / "stage.json").is_file():
                if "background_url" not in row:
                    stage = json.loads((path.parent / "stage.json").read_text(encoding="utf-8"))
                    frame = stage.get("current") or {}
                    row["background_url"] = (frame.get("scene") or {}).get("url") or ""
                    row["face_url"] = frame.get("face") or ""
                    row["place"] = (frame.get("scene") or {}).get("place") or ""
                rows.append(row)
        except (OSError, ValueError):
            pass
    return sorted(rows, key=lambda x: x["id"], reverse=True)


def quick_slot(saves_dir):
    try:
        slot = json.loads((Path(saves_dir) / "quick.json").read_text(encoding="utf-8"))["slot"]
        return slot if any(row["id"] == slot for row in list_slots(saves_dir)) else ""
    except (OSError, ValueError, KeyError, TypeError):
        return ""


def set_quick_slot(saves_dir, slot):
    _atomic_json(Path(saves_dir) / "quick.json", {"slot": slot})


def validate_slot(slot_dir):
    slot = Path(slot_dir)
    meta = json.loads((slot / "meta.json").read_text(encoding="utf-8"))
    if meta.get("id") != slot.name or meta.get("version") != 1:
        raise ValueError("invalid slot metadata")
    stage = _valid_stage(json.loads((slot / "stage.json").read_text(encoding="utf-8")))
    source = slot / "world.db"
    expanded = None
    if not source.is_file() and (slot / "world.db.gz").is_file():
        expanded = slot / (".validate-" + uuid.uuid4().hex + ".db")
        with gzip.open(slot / "world.db.gz", "rb") as compressed, open(expanded, "wb") as out:
            shutil.copyfileobj(compressed, out)
        source = expanded
    try:
        with closing(sqlite3.connect(f"file:{source}?mode=ro", uri=True)) as con:
            if con.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise RuntimeError("saved database failed SQLite quick_check")
    finally:
        if expanded is not None:
            expanded.unlink(missing_ok=True)
    return meta, stage


def restore_slot(slot_dir, db_path, state_path):
    """Restore while the VN server is stopped; preserve the old timeline."""
    slot = Path(slot_dir)
    meta, stage = validate_slot(slot)
    db_path, state_path = Path(db_path), Path(state_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    recovery_dir = slot.parent / ("recovery-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8])
    recovery_dir.mkdir()
    if db_path.exists():
        copy_db(str(db_path), str(recovery_dir / "world.db"))
    if state_path.exists():
        shutil.copy2(state_path, recovery_dir / "state.json")
    saved = stage["current"].copy()
    saved["resume_view"] = stage
    if meta.get("kind") == "line":
        saved["branch_from"] = int(meta["turn_id"])
    tmp_db = db_path.with_name(db_path.name + ".restore.tmp")
    if (slot / "world.db").is_file():
        copy_db(str(slot / "world.db"), str(tmp_db))
    else:
        with gzip.open(slot / "world.db.gz", "rb") as compressed, open(tmp_db, "wb") as out:
            shutil.copyfileobj(compressed, out)
    with closing(sqlite3.connect(tmp_db)) as con:
        if con.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise RuntimeError("saved database failed SQLite quick_check")
        if meta.get("kind") == "line":
            con.execute("INSERT OR REPLACE INTO kv(key,value) VALUES('outbox','[]')")
            con.execute("INSERT OR REPLACE INTO vn_line_checkpoints(msg_id,checkpoint_id) VALUES(?,?)",
                        (int(meta["msg_id"]), slot.name))
            con.commit()
    tmp_state = state_path.with_name(state_path.name + ".restore.tmp")
    _atomic_json(tmp_state, saved)
    try:
        os.replace(tmp_db, db_path)
        os.replace(tmp_state, state_path)
    except BaseException:
        if (recovery_dir / "world.db").is_file():
            copy_db(str(recovery_dir / "world.db"), str(db_path))
        if (recovery_dir / "state.json").is_file():
            shutil.copy2(recovery_dir / "state.json", state_path)
        else:
            state_path.unlink(missing_ok=True)
        tmp_db.unlink(missing_ok=True)
        tmp_state.unlink(missing_ok=True)
        raise
    return str(recovery_dir)


def main():
    p = argparse.ArgumentParser(description="Restore a VN save while its character is stopped")
    p.add_argument("slot", help="slot id from /saves")
    p.add_argument("--saves", default="data/vn/saves")
    p.add_argument("--db", required=True)
    p.add_argument("--state", required=True)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8770)
    args = p.parse_args()
    if Path(args.slot).name != args.slot or args.slot.startswith("."):
        p.error("slot must be an id, not a path")
    try:
        with socket.create_connection((args.host, args.port), timeout=1):
            p.error("VN server is running; stop this character before restoring")
    except OSError:
        pass
    recovery = restore_slot(Path(args.saves) / args.slot, args.db, args.state)
    print("restored", args.slot)
    print("previous timeline preserved at", recovery)


if __name__ == "__main__":
    main()
