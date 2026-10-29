"""Is a room a conversation, or a loop? Eight measures, off the record.

A group chat that reads wrong reads wrong for reasons that can be counted,
and until this tool nothing counted them. The audit of 2026-09-07 read two
rooms by eye and said one loops and the other plays the same beat twice on
each side; these are the same faults as numbers, so the next room can be
judged without reading it, and so a change to the writers can be shown to
move something.

What it measures, per room:

  own repeats          a message that says again what the SAME person said
                       earlier in the room (whole-message, the old test)
  cross-speaker echoes a message more than half of whose sentences somebody
                       ELSE has already said (`sim.textutil.echoed_by`)
  semantic repeats     two turns by one person whose one-line summaries mean
                       the same thing: the same conversational move twice
  messages per minute  over the room's own span
  bubble length        the mean per speaker, in characters
  stale rounds         rounds the room's own record marked as adding nothing
  arrangements         the share of turns that name a time, a place, or ask
                       one: a chat that is only ever a committee
  pocket used          how many of the day's concrete things to bring up
                       actually reached a turn

Where a room lives depends on who owns it. The character who keeps the world
has every room she runs in her own save (kv `cast_chat`, and the one in
flight in `exchange_live`) and copies every turn into the world file's
`rooms` table. A character who only takes part keeps what she was sent (kv
`peer_rooms`). All three are read here, all read-only.

    python tools/room_quality.py --world data/worlds/tokyo/world.db --date 2026-09-06
    python tools/room_quality.py --world data/worlds/tokyo/world.db \
        --date 2026-09-07 --room group --from 07:12 --to 07:30
    python tools/room_quality.py --save data/world.db --date 2026-09-06
    python tools/room_quality.py --save data/rena.db --peer-rooms

Never opens a live save for writing and never copies one: a copy of an open
database is a stale image, so every read here is `mode=ro` on the file
itself.
"""
import argparse
import io
import json
import os
import re
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

from sim.textutil import near_duplicate, echoed_by, sentences   # noqa: E402

# A turn that is doing the group's business rather than being in the room:
# a clock time, a place to be at, or the question that asks for one.
_TIME = re.compile(r"\d{1,2}\s*[:時]\s*\d{0,2}分?")
_PLACE = re.compile(r"駅|公園|校門|教室|学校|図書館|部室|会場|ホーム|集合|改札|うち|家の前")
_ARRANGE = re.compile(r"予定|待ち合わせ|何時|どこ")


def _ro(path):
    if not os.path.exists(path):
        raise SystemExit(f"no such file: {path}")
    return sqlite3.connect("file:%s?mode=ro" % path.replace("\\", "/"), uri=True)


def _kv(conn, key, default=None):
    row = conn.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
    if not row:
        return default
    try:
        return json.loads(row[0])
    except (TypeError, ValueError):
        return default


def _minutes(hm):
    try:
        h, m = str(hm).split(":")[:2]
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return None


# ---------------------------------------------------------------- gathering

def _rooms_from_world(path, date=None, room=None, lo=None, hi=None):
    """Every room in the world file, as the owner copied it: one row per turn,
    with who said it and when."""
    conn = _ro(path)
    q = "SELECT date, room, who, hm, ja FROM rooms"
    where, args = [], []
    if date:
        where.append("date=?")
        args.append(date)
    if room:
        where.append("room=?")
        args.append(room)
    if where:
        q += " WHERE " + " AND ".join(where)
    q += " ORDER BY date, room, hm"
    out = {}
    for d, rm, who, hm, ja in conn.execute(q, args):
        if lo is not None and (_minutes(hm) or 0) < lo:
            continue
        if hi is not None and (_minutes(hm) or 0) > hi:
            continue
        out.setdefault((d, rm), []).append({"who": who, "hm": hm, "ja": ja})
    conn.close()
    return [{"source": "the world file", "date": d, "room": rm, "turns": t,
             "moves": [], "stale": None, "long": None}
            for (d, rm), t in sorted(out.items())]


def _rooms_from_save(path, date=None, room=None, lo=None, hi=None):
    """The rooms this character RAN: her own record of each conversation, and
    the one still in flight."""
    conn = _ro(path)
    rows = list(_kv(conn, "cast_chat", []) or [])
    live = _kv(conn, "exchange_live", None)
    if isinstance(live, dict) and live.get("turns"):
        rows = rows + [dict(live, live=True)]
    out = []
    for x in rows:
        if not isinstance(x, dict):
            continue
        if date and x.get("date") != date:
            continue
        name = "group" if x.get("kind") == "group" else "%s:%s" % (x.get("kind"), x.get("who"))
        if room and name != room:
            continue
        turns = [{"who": t.get("who", ""), "hm": t.get("hm", ""),
                  "ja": t.get("ja") or t.get("text", "")} for t in (x.get("turns") or [])]
        turns = [t for t in turns
                 if (lo is None or (_minutes(t["hm"]) or 0) >= lo)
                 and (hi is None or (_minutes(t["hm"]) or 0) <= hi)]
        if not turns:
            continue
        out.append({"source": "her own record" + (", in flight" if x.get("live") else ""),
                    "date": x.get("date", ""), "room": name, "turns": turns,
                    "moves": list(x.get("moves") or []), "stale": x.get("stale"),
                    "long": x.get("long_bubbles"), "gist": x.get("gist", "")})
    conn.close()
    return out


def _rooms_from_peer(path, date=None, room=None, lo=None, hi=None):
    """The rooms this character is only a MEMBER of: what she was sent."""
    conn = _ro(path)
    seen = _kv(conn, "peer_rooms", {}) or {}
    out = []
    for name, rec in sorted(seen.items()):
        if room and name != room:
            continue
        by_day = {}
        for t in (rec.get("turns") or []):
            d = t.get("date") or rec.get("date") or ""
            if date and d != date:
                continue
            if lo is not None and (_minutes(t.get("hm")) or 0) < lo:
                continue
            if hi is not None and (_minutes(t.get("hm")) or 0) > hi:
                continue
            by_day.setdefault(d, []).append({"who": t.get("who", ""), "hm": t.get("hm", ""),
                                             "ja": t.get("ja", "")})
        for d, turns in sorted(by_day.items()):
            out.append({"source": "the record of a room she is in", "date": d, "room": name,
                        "turns": turns, "moves": list(rec.get("moves") or []),
                        "stale": None, "long": None})
    conn.close()
    return out


def _pockets(path, date):
    """(offered, used) over every person, for one day."""
    conn = _ro(path)
    rec = _kv(conn, "cast_pockets", {}) or {}
    conn.close()
    day = rec.get(date) or {}
    offered = used = 0
    for _who, row in day.items():
        if not isinstance(row, dict):
            continue
        offered += len(row.get("items") or [])
        used += len([i for i in (row.get("items") or [])
                     if i.get("id") in (row.get("used") or [])])
    return offered, used


# ---------------------------------------------------------------- measuring

def measure(room):
    turns = room["turns"]
    n = len(turns)
    res = {"turns": n}
    own = cross = 0
    own_pairs, cross_pairs = [], []
    prior = []
    for t in turns:
        ja = str(t.get("ja") or "")
        who = str(t.get("who") or "")
        # the old test, kept as its own number: a WHOLE message that repeats a
        # whole message of the same person's. It is what the writers caught
        # before this work, so the two columns say what the new filter adds.
        if any(p[0] == who and near_duplicate(p[1], ja) for p in prior):
            own += 1
            own_pairs.append((t.get("hm"), who, ja[:60]))
        # and the new one: more than half of this message's sentences already
        # said in the room, by anybody, this speaker included
        ewho, line = echoed_by(ja, prior)
        if ewho or line:
            cross += 1
            cross_pairs.append((t.get("hm"), who, ewho, line[:60]))
        prior.append((who, ja))
    res["own_repeats"] = own
    res["cross_echoes"] = cross
    res["own_pairs"] = own_pairs
    res["cross_pairs"] = cross_pairs

    # the same move twice: two of one person's one-line summaries meaning the
    # same thing. Only a record that keeps a moves ledger can answer this.
    sem, seen = 0, []
    for m in room.get("moves") or []:
        who, gist = str(m.get("who") or ""), str(m.get("gist") or "")
        if any(w == who and near_duplicate(g, gist) for w, g in seen):
            sem += 1
        seen.append((who, gist))
    res["semantic_repeats"] = sem if (room.get("moves")) else None

    lo = min([_minutes(t.get("hm")) for t in turns if _minutes(t.get("hm")) is not None] or [0])
    hi = max([_minutes(t.get("hm")) for t in turns if _minutes(t.get("hm")) is not None] or [0])
    span = max(1, hi - lo)
    res["span"] = "%s-%s (%d min)" % (turns[0].get("hm"), turns[-1].get("hm"), hi - lo)
    res["per_minute"] = n / float(span)

    lens = {}
    for t in turns:
        lens.setdefault(str(t.get("who") or ""), []).append(len(str(t.get("ja") or "")))
    res["lengths"] = {w: sum(v) / float(len(v)) for w, v in lens.items()}

    arr = 0
    for t in turns:
        ja = str(t.get("ja") or "")
        if _TIME.search(ja) or _PLACE.search(ja) or _ARRANGE.search(ja):
            arr += 1
    res["arrangements"] = arr / float(n) if n else 0.0
    res["stale"] = room.get("stale")
    res["long"] = room.get("long")
    return res


def show(room, res, verbose=False):
    print("\n%s %s  (%s)" % (room["date"], room["room"], room["source"]))
    print("  %d turn(s), %s, %.2f message(s) a minute"
          % (res["turns"], res["span"], res["per_minute"]))
    print("  own repeats (whole message) %d, sentence echoes in the room %d, same move twice %s"
          % (res["own_repeats"], res["cross_echoes"],
             "-" if res["semantic_repeats"] is None else res["semantic_repeats"]))
    print("  stale rounds %s, bubbles over the group length %s"
          % ("-" if res["stale"] is None else res["stale"],
             "-" if res["long"] is None else res["long"]))
    print("  arrangements %.0f%% of turns" % (100 * res["arrangements"]))
    for who in sorted(res["lengths"], key=lambda w: -res["lengths"][w]):
        print("    %-14s mean bubble %5.0f chars" % (who, res["lengths"][who]))
    if verbose:
        for hm, who, ja in res["own_pairs"]:
            print("    own repeat    [%s] %s: %s" % (hm, who, ja))
        for hm, who, ewho, line in res["cross_pairs"]:
            print("    echo of %-10s [%s] %s: %s" % (ewho, hm, who, line))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--world", help="a world file (data/worlds/<id>/world.db)")
    ap.add_argument("--save", help="a character's own save")
    ap.add_argument("--peer-rooms", action="store_true",
                    help="read the rooms the save's character only takes part in")
    ap.add_argument("--date")
    ap.add_argument("--room")
    ap.add_argument("--from", dest="lo", help="hh:mm")
    ap.add_argument("--to", dest="hi", help="hh:mm")
    ap.add_argument("-v", "--verbose", action="store_true", help="name every repeat")
    args = ap.parse_args(argv)
    lo, hi = _minutes(args.lo) if args.lo else None, _minutes(args.hi) if args.hi else None
    rooms = []
    if args.world:
        rooms += _rooms_from_world(args.world, args.date, args.room, lo, hi)
    if args.save and args.peer_rooms:
        rooms += _rooms_from_peer(args.save, args.date, args.room, lo, hi)
    elif args.save:
        rooms += _rooms_from_save(args.save, args.date, args.room, lo, hi)
    if not rooms:
        print("no room matched")
        return 0
    for room in rooms:
        show(room, measure(room), verbose=args.verbose)
    if args.save and args.date and not args.peer_rooms:
        try:
            offered, used = _pockets(args.save, args.date)
            print("\n%s: %d pocket item(s) offered, %d used" % (args.date, offered, used))
        except sqlite3.Error as e:
            print("\npocket not read: %s" % e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
