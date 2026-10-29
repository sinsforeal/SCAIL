"""Her own past, out of her extracted record and into the store that fades.

A character built by reading a real archive arrives with two files of her own
life. One is a set of standing facts and quoted moments, retrieved when a
message NAMES the thing (`sim/lore.py`). The other is a timeline: the things
that happened to her once, each with the day or the span the tape supports and
the episode and cue index it was said in. Nothing read the second one. So a
trip, an illness, a purchase or a move -- the parts of a past a person reaches
for sideways rather than by name -- could not be reached at all, in any room,
by anything: not by a word of his, not by meaning, not by the deliberate
search.

This writes that timeline into `self_memories`, the store her own memories
live in (`sim/self_memory.py`, `docs/memory.md`). Once a row is there the
cosine over her own past can find it (`sim/embed.py`, pool `selfmem`), the
deliberate search can quote it back (`sim/recall.py`), and a few lines of it
ride every prompt on the rotation her config's `self_memory.standing_in_prompt`
sets.

## What is written, and what is not

**The timeline only.** The quoted moments beside it are a decided question and
the decision is the other way: a line off the corpus is her record, found when
a message names it and silent otherwise, and it stays in the retrieval file
(`sim/lore.py._memories`). This module reads the moments file for one purpose
-- to see which of its rows are the same event as a timeline row, so the
overlap is named on the row rather than discovered later.

**No model is asked anything**, here or at boot. The Japanese is the
timeline's and the English reading beside it is the timeline's gloss, which is
exactly the two search keys the store wants (`text` and `alt`), so there is
nothing to translate.

**The rows go straight into the table rather than through `SelfMemory.add`,**
for the two reasons that method is wrong for a seed: it stamps `ts` and
`last_seen` with the moment it runs, which would make a whole life equally
fresh, and it pays for a gloss that is already written.

## The date, and the felt age

Two different things, in two columns, and the difference is the point.

`date` is the day the timeline gives, unchanged: a calendar day she stated, or
the broadcast day the tape bounds the thing by, or -- for the majority, which
the tape bounds and does not date -- the span itself, written
`1994-04-01..1996-03-31`. Nothing between those bounds is asserted, which is
the rule the timeline states, so no day inside them is invented. A reader shows
a month and a day only when the value is a plain calendar day
(`SelfMemory.prompt_text`).

`ts` and `last_seen` are the felt age, and they are an ordering device rather
than a claim. Against a 2026 clock a thing she said in 2010 is 6,000 days old,
so the last event of the tape is fixed at the day before her save's first day
-- her remembered life ends where her lived record begins -- and the rest runs
back from there at its true distance. Her whole life keeps its real shape and
its real intervals; a childhood memory sits as far back as a childhood memory
should. For a bounded event the arithmetic uses the middle of the span, which
is an ordering choice and is why it is in this column and not in `date`.

## Weight, feeling and valence

Every seeded row carries the same weight, and the reason is the reason the
seed for the earlier character left its feeling and its valence empty: nothing
in the row grounds one, and a wrong value here is worse than none. A timeline
event has no judgement of how much losing it would cost her -- there is no
hand read behind this file -- so the seeder does not invent a scale. The
middle of the scale it is, which keeps two things true: nothing is pinned in
her prompt for ever (`_standing_for_prompt` fixes anything at the top of the
scale there), and the rotation then walks her life in the one order the rows
do carry, which is chronological.

`source` is the seed's own word, which is what tells the store that these are
what she is made of rather than something she lived through while running, so
they never fade (`SelfMemory.STANDING_SOURCES`).

## The receipt

`receipt` carries, in one line: the event's stable id in the source file, the
basis the date rests on, every episode and cue index the claim was found at,
and the id of the moments-file row it duplicates where there is one. It is read
by no prompt. It is what makes a seeded row auditable back to the tape, and its
first field is what makes running this twice add nothing.
"""

import datetime
import io
import json
import os
import re

import logger
from sim.self_memory import STANDING_SOURCES, _is_day as is_day

# Bumped when the rows this module would write change. A save whose marker is
# behind is offered the seed again; the write is insert-only by stable id, so
# what is already there is untouched and only what is new lands.
SEED_VERSION = 1

# The word in `source` that means "written in from her own record". It is what
# the store reads to decide a row does not fade, so it is that constant and
# never a string of its own.
SEED_SOURCE = STANDING_SOURCES[0]

# The middle of the store's 1-to-5 scale. See the module docstring: nothing in
# a timeline event judges what losing it would cost her.
SEED_WEIGHT = 3

# How far apart two cue indexes may be and still be the same moment of tape.
# The extraction records its own drift class: 25 of 1,038 raw facts and 8 of
# 326 moments name a cue one to three higher than the cue their quote is in,
# always in that direction. So three, which is that class's width and not a
# number chosen to make a count come out.
CUE_DRIFT = 3

# Where the save records that it has been seeded, and with what. Written as a
# literal at each call rather than through this name, because that is where
# every kv key in the project is read from and both the docs check and the
# generated table of kv keys by module look for it there.
MARKER = "selfmem_seed"

_CUE = re.compile(r"(ep\d+)#(\d+)")


def _as_date(text):
    """A day for the arithmetic, out of a day, a month or a year. The first of
    the month or of the year: this feeds the felt-age ordering only, never the
    `date` column, so it asserts nothing."""
    s = str(text or "").strip()
    for fmt, pad in (("%Y-%m-%d", ""), ("%Y-%m", "-01"), ("%Y", "-01-01")):
        try:
            return datetime.datetime.strptime(s + pad, "%Y-%m-%d").date()
        except ValueError:
            continue
    return None


def _cues(refs):
    out = set()
    for ref in refs:
        m = _CUE.match(str(ref or "").strip())
        if m:
            out.add((m.group(1), int(m.group(2))))
    return out


def _read_json(path):
    with io.open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_events(path):
    """The timeline's events, in the order the file holds them."""
    raw = _read_json(path)
    events = raw.get("events", raw) if isinstance(raw, dict) else raw
    return list(events or [])


def load_moments(path):
    """The moments file's rows, or nothing when the character has no such
    file. Read for the overlap and for nothing else."""
    if not path or not os.path.exists(path):
        return []
    raw = _read_json(path)
    rows = raw.get("records", raw) if isinstance(raw, dict) else raw
    return list(rows or [])


def overlap(events, moments):
    """Which moments-file row is the same moment of tape as which event.

    Matched on the receipt -- the episode and the cue index -- because that is
    the one thing the two files share. The texts cannot be compared: a timeline
    event is a written sentence about what happened and a moments row is her
    verbatim line, so they overlap on grammar and nothing else, which is the
    finding `sim/lore.py` is built on.

    Returns event id -> the moments ids it covers."""
    ev = [(e.get("id"), _cues(r.get("at") for r in (e.get("receipts") or []))) for e in events]
    out = {}
    for row in moments:
        refs = _cues(p.get("ref") for c in (row.get("claims") or [])
                     for p in (c.get("provenance") or []))
        if not refs:
            continue
        for eid, ecues in ev:
            if any(e1 == e2 and abs(c1 - c2) <= CUE_DRIFT
                   for (e1, c1) in refs for (e2, c2) in ecues):
                out.setdefault(eid, []).append(row.get("id"))
                break
    return out


def _date_and_pivot(event):
    """The `date` column's value, and the day the felt age is measured from.

    A stated or broadcast day is both. A bounded event's date is the span, and
    the pivot is the middle of it -- an ordering choice, kept out of `date` so
    that nothing inside the bounds is asserted."""
    if event.get("date"):
        return str(event["date"]), _as_date(event["date"])
    lo, hi = event.get("not_before"), event.get("not_after")
    a, b = _as_date(lo), _as_date(hi)
    if a and b:
        return f"{lo}..{hi}", a + (b - a) // 2
    return str(lo or hi or ""), (a or b)


def build_rows(timeline_path, moments_path="", anchor=None, weight=SEED_WEIGHT):
    """Every timeline event as a row for `self_memories`, with its felt day.

    `anchor` is the day the last event of the tape is felt to have happened.
    Without one the rows come back with their true distances and no felt day,
    which is what a report wants and what a write does not."""
    events = load_events(timeline_path)
    covers = overlap(events, load_moments(moments_path))
    built = []
    for e in events:
        text = " ".join(str(e.get("text") or "").split())
        if not text:
            continue
        date_col, pivot = _date_and_pivot(e)
        if pivot is None:
            continue
        eid = str(e.get("id") or "").strip()
        if not eid:
            continue
        key = "timeline:" + eid
        parts = [key, str(e.get("date_basis") or "?"),
                 " ".join(str(r.get("at") or "") for r in (e.get("receipts") or []))]
        if covers.get(eid):
            parts.append(" ".join(covers[eid]))
        built.append({
            "key": key,
            "date": date_col,
            "pivot": pivot,
            "text": text,
            "alt": " ".join(str(e.get("gloss") or "").split()),
            "weight": int(weight),
            "receipt": " | ".join(p for p in parts if p),
            "basis": str(e.get("date_basis") or "?"),
            "covers": covers.get(eid) or [],
        })
    if not built:
        return built
    last = max(r["pivot"] for r in built)
    for r in built:
        r["felt"] = (anchor - (last - r["pivot"])) if anchor else None
    return built


# ---------------- writing ----------------


def seeded_keys(store):
    """The stable ids already in the table, off the receipt's first field."""
    with store.lock:
        rows = store.conn.execute(
            "SELECT receipt FROM self_memories WHERE source=?", (SEED_SOURCE,)).fetchall()
    keys = set()
    for r in rows:
        got = str((r[0] if not hasattr(r, "keys") else r["receipt"]) or "")
        if got:
            keys.add(got.split(" | ")[0].strip())
    return keys


def write(store, rows):
    """Insert every row whose stable id is not in the table yet, and return
    the rowids written. Insert-only: a row already seeded is left exactly as
    it is, mentions and last-seen stamp included, because those are the record
    of a memory having come back to her and a re-run must not undo it."""
    have = seeded_keys(store)
    todo = [r for r in rows if r["key"] not in have]
    written = []
    if not todo:
        return written
    with store.lock:
        for r in todo:
            ts = datetime.datetime.combine(r["felt"], datetime.time(12, 0)).timestamp()
            cur = store.conn.execute(
                "INSERT INTO self_memories(ts,date,text,weight,feeling,last_seen,mentions,"
                "valence,alt,source,card_id,receipt) VALUES(?,?,?,?,'',?,1,0,?,?,NULL,?)",
                (ts, r["date"], r["text"], r["weight"], ts, r["alt"], SEED_SOURCE, r["receipt"]))
            written.append(cur.lastrowid)
        store.conn.commit()
    return written


def first_day(store, clock):
    """The first day this save holds anything at all, which is the day she came
    online. `state_log` because a gauge snapshot is written on the first pass of
    the first boot, before she has said anything or lived a day."""
    try:
        with store.lock:
            row = store.conn.execute("SELECT MIN(ts) FROM state_log").fetchone()
        if row and row[0]:
            return datetime.datetime.fromtimestamp(float(row[0])).date()
    except Exception:
        pass
    return clock.now().date()


# ---------------- the boot migration ----------------


def seed_if_needed(app):
    """Seed this character's own past, once, at boot.

    Silent and immediate for a character whose config names no timeline: that
    is most of them, and absence is not a failure. Loud for a config that names
    a file which is not on disk, which is a wrong path rather than an absent
    one, and then nothing is written and nothing is marked, so the next boot
    tries again.

    Returns the number of rows written."""
    c = app.config
    path = str(getattr(c.character, "timeline_file", "") or "").strip()
    if not path:
        return 0
    if not os.path.exists(path):
        logger.log(f"[memory] the timeline her config names is not on disk, so nothing was seeded: {path}")
        return 0
    mark = app.store.get("selfmem_seed", {}) or {}
    with app.store.lock:
        held = app.store.conn.execute("SELECT COUNT(*) FROM self_memories").fetchone()[0]
    if held and int(mark.get("version", 0) or 0) >= SEED_VERSION:
        return 0
    anchor = first_day(app.store, app.clock) - datetime.timedelta(days=1)
    moments = str(getattr(c.character, "memories_file", "") or "").strip()
    try:
        rows = build_rows(path, moments, anchor)
    except (OSError, ValueError, KeyError) as e:
        logger.log(f"[memory] her timeline was not read, so nothing was seeded: {type(e).__name__}: {e}")
        return 0
    # what she reads has to be in the language she writes, the same test the
    # store's own door applies to every memory that arrives
    bad = [r for r in rows if not app.self_memory.hers(r["text"])]
    for r in bad[:3]:
        logger.log(f"[memory] a timeline row is not in the language she writes and was left out: {r['key']}")
    rows = [r for r in rows if app.self_memory.hers(r["text"])]
    written = write(app.store, rows)
    dated = sum(1 for r in rows if is_day(r["date"]))
    bounded = len(rows) - dated
    index = _index(app, written)
    app.store.set("selfmem_seed", {"version": SEED_VERSION, "rows": len(rows), "written": len(written),
                           "anchor": anchor.isoformat(), "file": path,
                           "at": app.clock.now_ts()})
    if written:
        logger.log(f"[memory] seeded {len(written)} memories from her timeline "
                   f"({dated} dated, {bounded} bounded), {index}")
    return len(written)


def _index(app, rowids):
    """The vectors of the rows just written, so her own past can be reached by
    meaning on the first reply rather than after the pass that follows boot.
    The same call `SelfMemory` makes for a memory the compile keeps."""
    if not rowids or app.embed is None or not app.config.embed.enabled:
        return "the index is left to the pass after boot"
    try:
        with app.store.lock:
            rows = app.store.conn.execute(
                "SELECT rowid AS rid, text, alt FROM self_memories WHERE rowid IN (%s)"
                % ",".join("?" * len(rowids)), list(rowids)).fetchall()
        want = [(r["rid"], (str(r["text"] or "") + " " + str(r["alt"] or "")).strip()) for r in rows]
        return f"{len(app.embed.vectors('selfmem', want))} of them indexed by meaning"
    except Exception as e:
        logger.log(f"[memory] the seeded rows have no vectors yet: {type(e).__name__}: {str(e)[:80]}")
        return "the index is left to the pass after boot"
