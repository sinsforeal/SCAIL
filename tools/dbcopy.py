"""A copy of a live save that is a save.

Both live saves are in rollback-journal mode, so a file copy taken while a
bot is mid-transaction is a torn image, and the write-ahead sidecars a copy
would carry do not exist. SQLite's own backup reads a consistent snapshot
through a read-only connection and never touches the source. Every harness
that builds the App on a copy goes through this; `tools/smoke.py` too.
"""
import os
import sqlite3


def copy_db(src, dst):
    for suffix in ("", "-wal", "-shm"):
        if os.path.exists(dst + suffix):
            os.remove(dst + suffix)
    con = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    out = sqlite3.connect(dst)
    try:
        with out:
            con.backup(out)
    finally:
        out.close()
        con.close()
    return dst
