# -*- coding: utf-8 -*-
"""Look at, and rehearse, the seed of a character's own past.

The work itself is `sim/seed_memories.py`, which the program that runs her
calls once at boot, so this is not the route the rows normally arrive by.
What it is for is seeing what the seed is made of before it runs, and running
it against a COPY of a save to prove what it writes.

It refuses to write a save named in `characters.json`: a seed run against a
live one would be a second writer on it, and a character whose own process
does this at boot needs nothing done to her by hand.

    python tools/seed_memories.py --config config_asumin.json --report
    python tools/seed_memories.py --config config_asumin.json --sample 12
    python tools/seed_memories.py --config config_asumin.json --db /tmp/copy.db
"""
import argparse
import datetime
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sim import seed_memories  # noqa: E402
from store import Store  # noqa: E402

if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)


def live_saves():
    try:
        reg = json.load(io.open(os.path.join(ROOT, "characters.json"), encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    return {os.path.basename(str(r.get("db") or "")).lower() for r in reg.get("characters", [])}


def paths_from(config_path):
    d = json.load(io.open(os.path.join(ROOT, config_path), encoding="utf-8"))
    ch = d.get("character") or {}
    return str(ch.get("timeline_file") or ""), str(ch.get("memories_file") or "")


def report(rows, moments_seen):
    dated = [r for r in rows if seed_memories.is_day(r["date"])]
    spans = [r for r in rows if not seed_memories.is_day(r["date"])]
    covered = [r for r in rows if r["covers"]]
    print("\n  %d rows: %d on a calendar day, %d on a span or a month the archive bounds"
          % (len(rows), len(dated), len(spans)))
    basis = {}
    for r in rows:
        basis[r["basis"]] = basis.get(r["basis"], 0) + 1
    for k in sorted(basis, key=lambda k: -basis[k]):
        print("    %-10s %4d" % (k, basis[k]))
    print("  %d of them are the same moment of tape as %d row(s) of her moments file"
          % (len(covered), len({m for r in covered for m in r['covers']})))
    print("  %d row(s) of the moments file are matched by nothing here" % moments_seen)
    if rows and rows[0].get("felt"):
        print("  felt as %s to %s (the true span is %s to %s)"
              % (min(r["felt"] for r in rows), max(r["felt"] for r in rows),
                 min(r["pivot"] for r in rows), max(r["pivot"] for r in rows)))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", help="the character config to read her two paths from")
    ap.add_argument("--timeline", default="", help="her timeline file, instead of a config")
    ap.add_argument("--moments", default="", help="her moments file, instead of a config")
    ap.add_argument("--db", default="", help="a COPY of a save to write, never a live one")
    ap.add_argument("--anchor", default="", help="the day the last event is felt to have happened")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--sample", type=int, default=0, help="print N rows spread across the span")
    args = ap.parse_args()

    timeline, moments = args.timeline, args.moments
    if args.config:
        timeline, moments = paths_from(args.config)
    if not timeline:
        raise SystemExit("no timeline: give --config or --timeline")
    if not os.path.exists(os.path.join(ROOT, timeline)):
        raise SystemExit("no such timeline: %s" % timeline)

    store = None
    if args.db:
        if os.path.basename(os.path.abspath(args.db)).lower() in live_saves():
            raise SystemExit("refusing %s: that is a live save, and her own process seeds it at boot"
                             % os.path.basename(args.db))
        store = Store(args.db)

    if args.anchor:
        anchor = datetime.date.fromisoformat(args.anchor)
    elif store is not None:
        anchor = seed_memories.first_day(store, _Today()) - datetime.timedelta(days=1)
    else:
        anchor = datetime.date.today() - datetime.timedelta(days=1)

    rows = seed_memories.build_rows(os.path.join(ROOT, timeline),
                                    os.path.join(ROOT, moments) if moments else "", anchor)
    print("%d timeline event(s) -> %d row(s), last one felt as %s" % (
        len(seed_memories.load_events(os.path.join(ROOT, timeline))), len(rows), anchor))

    if store is not None:
        # the table and its columns belong to `SelfMemory._ensure`, which a
        # scratch database here has never had run against it
        _ensure_table(store)
        before = _count(store)
        written = seed_memories.write(store, rows)
        print("  wrote %d row(s); the table held %d and now holds %d"
              % (len(written), before, _count(store)))

    if args.report:
        seen = len(seed_memories.load_moments(os.path.join(ROOT, moments))) if moments else 0
        covered = {m for r in rows for m in r["covers"]}
        report(rows, seen - len(covered))
    if args.sample:
        rows = sorted(rows, key=lambda r: r["pivot"])
        step = max(1, len(rows) // args.sample)
        print()
        for r in rows[::step][: args.sample]:
            print("  %-34s date %-24s felt %s w%d" % (r["key"], r["date"], r["felt"], r["weight"]))
            print("     ja: %s" % r["text"])
            print("     en: %s" % r["alt"])
            print("     receipt: %s" % r["receipt"])


class _Today:
    """The one thing `first_day` asks a clock for."""

    def now(self):
        return datetime.datetime.now()


def _ensure_table(store):
    store.conn.execute("""CREATE TABLE IF NOT EXISTS self_memories (
        id INTEGER PRIMARY KEY, ts REAL, date TEXT, text TEXT,
        weight INTEGER DEFAULT 2, feeling TEXT, last_seen REAL,
        mentions INTEGER DEFAULT 1, source TEXT DEFAULT 'compile',
        alt TEXT, valence INTEGER DEFAULT 0, card_id INTEGER, receipt TEXT)""")
    cols = {r[1] for r in store.conn.execute("PRAGMA table_info(self_memories)")}
    for name, kind in (("source", "TEXT DEFAULT 'compile'"), ("alt", "TEXT"),
                       ("valence", "INTEGER DEFAULT 0"), ("card_id", "INTEGER"),
                       ("receipt", "TEXT")):
        if name not in cols:
            store.conn.execute(f"ALTER TABLE self_memories ADD COLUMN {name} {kind}")
    store.conn.commit()


def _count(store):
    return store.conn.execute("SELECT COUNT(*) FROM self_memories").fetchone()[0]


if __name__ == "__main__":
    main()
