"""Retire the second world a world READER built in her own save.

A character who is in a world somebody else keeps runs none of the machinery
that writes it (`docs/shared-world.md` §8). The rule landed after such a
character had already been running for forty-five minutes, and what she wrote
in that time is still in her save: her own draw of the roster's week, her own
day's script for people whose day the owner had already fixed, her own pool of
rumours, her own orbit and her own edges. The planner is gated now, so nothing
new is written -- but a plan already in the record keeps coming due on her
clock, and every subsystem that READS one of those keys reads the second
world's answer rather than the owner's.

So the rows are moved out of the save and into a file under
`data/retired/`, and deleted. Never edited in place, never merged with the
world file: they are one process's answer to a question that is not its own,
and the honest thing to do with them is keep them where a person can read them
and take them out of the running record.

Two jobs, one marker:

1. the world-writing keys and the `events` rows of kind `cast` (the only
   writer of that kind is the day's beat delivery, which a reader now
   refuses);
2. one repair of her record of the rooms she is in that somebody else owns
   (kv `peer_rooms`): a turn filed twice, once under the name of the process
   that relayed it and once under whoever actually said it, is one turn, and
   every turn is stamped with the day it was said on.

`tomoe/app.py retire_second_world_once` runs this at the reader's next boot.
On a stopped save it is also a command:

    python tools/second_world_retire.py --db <save> --out <file.json> [--apply]

Nobody is named here. Which character this is comes from the save it is
pointed at.
"""
import argparse
import datetime
import json
import os
import sqlite3

# What a world's machinery writes into the character's own save. One row per
# switched-off section, plus the two the program gates rather than the
# existence table (the day's beats, kept as today and yesterday).
KEYS = ("cast_beats", "cast_beats_prev", "cast_arcs", "cast_days", "cast_plans",
        "gossip", "orbit", "social_graph")
# The kv that says this ran. Read before anything is touched, written after.
MARKER = "second_world_retired"


def _decode(text):
    """The stored value as data where it parses, and as its own text where it
    does not: the file is for a person to read, and a value that will not
    decode is still worth keeping verbatim."""
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return {"_raw": text}


def collect(conn):
    """What is in this save that belongs to a world she does not keep."""
    kv = {}
    for k in KEYS:
        row = conn.execute("SELECT value FROM kv WHERE key=?", (k,)).fetchone()
        if row is None:
            continue
        kv[k] = _decode(row[0])
    cols = ("id", "ts", "date", "kind", "text", "salience")
    events = [dict(zip(cols, r)) for r in
              conn.execute("SELECT id, ts, date, kind, text, salience FROM events "
                           "WHERE kind='cast' ORDER BY id")]
    return kv, events


def repair_rooms(conn, apply=True, log=print):
    """Her record of a room somebody else owns, cleaned once.

    Two things. A turn that arrived twice -- inside the ask that wanted her
    words, where it carried the real speaker and no clock, and as the relay of
    that same turn, where it carried a clock and the RELAYING process's
    display name -- is one turn: the speaker's row stands and takes the clock
    the other one carried. And every turn is stamped with the day it was said
    on, because one record runs across days and three readers now render a
    stamp from it.

    Returns (rooms touched, rows dropped, rows dated)."""
    row = conn.execute("SELECT value FROM kv WHERE key='peer_rooms'").fetchone()
    if row is None:
        return 0, 0, 0
    try:
        rooms = json.loads(row[0])
    except (TypeError, ValueError):
        return 0, 0, 0
    if not isinstance(rooms, dict):
        return 0, 0, 0
    touched = dropped = dated = 0
    for name, rec in rooms.items():
        if not isinstance(rec, dict):
            continue
        turns = list(rec.get("turns") or [])
        owner = str(rec.get("owner_name") or "")
        day = str(rec.get("date") or "")
        # which texts were filed by more than one name
        names = {}
        for t in turns:
            names.setdefault(str(t.get("ja") or ""), set()).add(str(t.get("who") or ""))
        out, moved = [], False
        for t in turns:
            ja = str(t.get("ja") or "")
            who = str(t.get("who") or "")
            others = names.get(ja, set()) - {owner}
            if who == owner and others:
                # the same words are also filed under whoever said them: this
                # row is the relay wearing the sender's name. Its clock is the
                # real one, so it goes to the row that keeps the speaker.
                for u in out:
                    if str(u.get("ja") or "") == ja and str(u.get("who") or "") != owner:
                        if not str(u.get("hm") or "") and str(t.get("hm") or ""):
                            u["hm"] = str(t.get("hm"))
                        if not float(u.get("ts") or 0) and float(t.get("ts") or 0):
                            u["ts"] = float(t.get("ts"))
                dropped += 1
                moved = True
                log(f"{name}: {who} was not the speaker of {ja[:40]!r}; the row is dropped "
                    f"and its clock {str(t.get('hm') or '')!r} goes to the one that names "
                    + ", ".join(sorted(others)))
                continue
            if not str(t.get("date") or ""):
                t["date"] = day
                dated += 1
                moved = True
            out.append(t)
        # a relay row that arrived BEFORE the speaker's row keeps the clock it
        # carried, so the pass above is run once more in the other direction
        for t in out:
            if str(t.get("hm") or ""):
                continue
            for u in turns:
                if (str(u.get("ja") or "") == str(t.get("ja") or "")
                        and str(u.get("who") or "") == owner and str(u.get("hm") or "")):
                    t["hm"] = str(u.get("hm"))
                    if not float(t.get("ts") or 0) and float(u.get("ts") or 0):
                        t["ts"] = float(u.get("ts"))
                    moved = True
                    break
        if moved:
            rec["turns"] = out
            touched += 1
    if touched and apply:
        conn.execute("INSERT OR REPLACE INTO kv(key,value) VALUES('peer_rooms',?)",
                     (json.dumps(rooms),))
        conn.commit()
    return touched, dropped, dated


def retire(conn, out_path, apply=True, log=print):
    """Move the second world out of this save. Returns the summary dict."""
    kv, events = collect(conn)
    rooms = repair_rooms(conn, apply=apply, log=log)
    summary = {"keys": sorted(kv), "events": len(events), "file": out_path,
               "rooms_touched": rooms[0], "rows_dropped": rooms[1], "rows_dated": rooms[2]}
    if not kv and not events:
        return summary
    doc = {"written": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
           "why": "the world's own machinery run by a character who reads that world and does "
                  "not keep it (docs/shared-world.md 8); moved out of her save, not edited",
           "kv": kv, "events": events}
    if apply:
        d = os.path.dirname(out_path)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
        for k in kv:
            conn.execute("DELETE FROM kv WHERE key=?", (k,))
        if events:
            conn.execute("DELETE FROM events WHERE kind='cast'")
        conn.commit()
    return summary


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", required=True, help="the save (a COPY unless the bot is stopped)")
    ap.add_argument("--out", default="", help="where the retired rows go")
    ap.add_argument("--apply", action="store_true", help="write and delete; otherwise report only")
    a = ap.parse_args()
    out = a.out or os.path.join("data", "retired",
                                datetime.datetime.now().strftime("%Y%m%d_%H%M") + "_second_world",
                                os.path.splitext(os.path.basename(a.db))[0] + ".json")
    conn = sqlite3.connect(a.db)
    s = retire(conn, out, apply=a.apply, log=lambda m: print("  " + str(m)))
    print(("applied" if a.apply else "would move")
          + ": %d key(s) %s, %d events row(s) of kind cast, %d room(s) repaired "
            "(%d row(s) dropped, %d dated)"
          % (len(s["keys"]), ", ".join(s["keys"]) or "-", s["events"],
             s["rooms_touched"], s["rows_dropped"], s["rows_dated"]))
    print("  -> " + s["file"])


if __name__ == "__main__":
    main()
