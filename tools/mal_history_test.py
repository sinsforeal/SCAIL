# -*- coding: utf-8 -*-
"""One row per watch, on this machine's clock.

    python tools/mal_history_test.py        # in smoke; no network, no live store

Two things are checked, both against numbers the player's own log settles.

The public history page is rendered on MyAnimeList's clock and the logged-in
panel on his account's, three hours apart, so the same watch used to be
written twice: "Yesterday, 6:05 PM" from the page and "Ep 13, watched on
09/03/2026 at 21:05" from the panel, and his player opened that file at 20:30:16. The same three hours put a relative label a day out when
the page was read between midnight here and midnight there, which is why 34
watches had two page rows a day apart carrying the identical label.

Everything runs on a scratch database in a temp directory. The live mirror is
never opened.
"""
import datetime
import io
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

import mal_history as M  # noqa: E402

fails = []


def check(ok, what, detail=""):
    print(("  ok   " if ok else "  FAIL ") + what + (("  -- " + detail) if detail else ""))
    if not ok:
        fails.append(what)
    return ok


def clock_checks():
    print("\nA LABEL ON THE SITE'S CLOCK, READ ON THIS MACHINE'S")
    # every pair below is one watch: the page's label, the moment on this
    # machine the page was read, and what the panel says the watch was
    cases = [
        ("Yesterday, 6:05 PM", datetime.datetime(2026, 9, 4, 15, 0), "2026-09-03T21:05",
         "Mitsudomoe ep 13, read in the afternoon"),
        ("Yesterday, 6:05 PM", datetime.datetime(2026, 9, 5, 1, 0), "2026-09-03T21:05",
         "the same label read after midnight here and before midnight there"),
        ("Yesterday, 4:47 PM", datetime.datetime(2026, 9, 5, 12, 0), "2026-09-04T19:47",
         "Example Show OVA ep 1"),
        ("Aug 8, 2:32 PM", datetime.datetime(2026, 8, 20, 12, 0), "2026-08-08T17:32",
         "Example Show ep 1, an absolute label"),
        ("09-03-26, 6:05 PM", datetime.datetime(2026, 9, 7, 12, 0), "2026-09-03T21:05",
         "the same watch once the page stops calling it yesterday"),
    ]
    for label, read_at, panel, why in cases:
        got = M._resolve_history_time(label, read_at)
        check(got == panel, f"{label!r} -> {panel}  ({why})", str(got))


def scratch(tmp):
    """A mirror holding the two rows one Mitsudomoe watch produced, and one
    the panel never saw."""
    path = os.path.join(tmp, "mal_history.db")
    con = M.db(path)
    con.execute("INSERT INTO anime(anime_id,title) VALUES(7627,'Mitsudomoe')")
    con.execute("INSERT INTO anime(anime_id,title) VALUES(1480,'Example Show')")
    rows = [
        (7627, 13, "2026-09-03T21:05", "Ep 13, watched on 09/03/2026 at 21:05", "ajaxtb"),
        (7627, 13, "2026-09-03T18:05", "Yesterday, 6:05 PM", "history"),
        (7627, 13, "2026-09-04T18:05", "Yesterday, 6:05 PM", "history"),
        (1480, 1, "2026-09-04T16:47", "Yesterday, 4:47 PM", "history"),
        (1480, 1, "2026-09-05T16:47", "Yesterday, 4:47 PM", "history"),
    ]
    for r in rows:
        con.execute("INSERT INTO episodes(anime_id,ep,watched_at,raw,source) VALUES(?,?,?,?,?)", r)
    con.commit()
    return con


def migration_checks(tmp):
    print("\nTHE MIGRATION, ON A SCRATCH COPY")
    con = scratch(tmp)
    check(con.execute("SELECT COUNT(*) FROM episodes WHERE anime_id=7627 AND ep=13").fetchone()[0] == 3,
          "the scratch store starts with three rows for one watch")
    dropped, moved = M.migrate_episode_stamps(con, dry=False, out=lambda s: print("   " + s.strip()))
    got = con.execute("SELECT watched_at, source FROM episodes WHERE anime_id=7627 AND ep=13").fetchall()
    check(len(got) == 1, "the two page rows collapse into the panel's one", str(got))
    check(bool(got) and got[0][0] == "2026-09-03T21:05" and got[0][1] == "ajaxtb",
          "and what is left is the panel's stamp", str(got and got[0]))
    left = con.execute("SELECT watched_at, source FROM episodes WHERE anime_id=1480 AND ep=1").fetchall()
    check(len(left) == 1, "a watch the panel never saw keeps one row", str(left))
    check(bool(left) and left[0][0] == "2026-09-04T19:47",
          "moved onto this machine's clock, where his player opened the file at 19:14",
          str(left and left[0][0]))
    check(dropped == 3 and moved == 1, "three dropped, one moved", f"{dropped}, {moved}")
    print("\n  running it a second time changes nothing:")
    again = M.migrate_episode_stamps(con, dry=False, out=lambda s: print("   " + s.strip()))
    check(again == (0, 0), "the migration is idempotent", str(again))


def upsert_checks(tmp):
    print("\nWHAT THE DAEMON WRITES FROM NOW ON")
    path = os.path.join(tmp, "upsert.db")
    con = M.db(path)
    con.execute("INSERT INTO anime(anime_id,title) VALUES(7627,'Mitsudomoe')")
    con.commit()
    M._upsert_episodes(con, 7627, [(13, "2026-09-03T18:05", "Yesterday, 6:05 PM")], "history")
    check(con.execute("SELECT COUNT(*) FROM episodes").fetchone()[0] == 1,
          "the page's row stands while the panel has nothing")
    M._upsert_episodes(con, 7627, [(13, "2026-09-03T21:05", "Ep 13, watched on 09/03/2026 at 21:05")], "ajaxtb")
    got = con.execute("SELECT watched_at, source FROM episodes").fetchall()
    check(len(got) == 1 and got[0][1] == "ajaxtb",
          "the panel's row takes the page's row out with it", str(got))
    M._upsert_episodes(con, 7627, [(13, "2026-09-03T18:05", "Yesterday, 6:05 PM")], "history")
    check(con.execute("SELECT COUNT(*) FROM episodes").fetchone()[0] == 1,
          "and a later page row for that episode is not written at all")
    stamped = con.execute("SELECT scraped_at FROM episodes").fetchone()[0]
    check(bool(stamped), "the moment the page was read is on the row", str(stamped))


def main():
    tmp = tempfile.mkdtemp(prefix="mal_history_test_")
    try:
        clock_checks()
        migration_checks(tmp)
        upsert_checks(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print()
    if fails:
        print(f"FAIL: {len(fails)} check(s): " + "; ".join(fails[:6]))
        return 1
    print("all checks passed: one row per watch, on this machine's clock")
    return 0


if __name__ == "__main__":
    sys.exit(main())
