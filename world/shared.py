"""One world, on disk, that more than one process may read.

Everything a character knows about the world she lives in is in HER save: the
people's days, where each of them is, what the day settled, the group chat and
every exchange, who thinks what of whom, the pool of what is going round. A
second process running one of those people as a character of her own has no
way to reach any of it, and would plan a Saturday the first process never had.

So the world gets a file of its own. One sqlite file per world, under
`<world.shared_dir>/<world_shared.id>/world.db`, with **one writer** -- the
character whose config says `world_shared.owner` -- and any number of readers,
who open it through a `mode=ro` URI. A reader never copies it: a copy of an
open save is a stale image, and this file is written a row at a time while
other processes are reading it.

One writer for everything the owner owns, and a PARTITION for everybody else.
A character who only lives in this world writes the rows that are about
HERSELF -- the windows her own day planner puts her in, the rooms she is in,
the lines her own plan settled -- under her own id and a source naming her own
planner, and nothing else: a row about anybody else, or into any other table,
is refused and the refusal is logged. Two writers cannot land on one row
because the natural keys already carry the person and the source, and the
`world`, `owner` and `written` keys of `meta` stay the owner's -- a reader
records herself under `writers` instead, because opening the file to write a
row about oneself is not claiming the world.

It is a COPY, not the truth. Each fact still has exactly one owner in the
owner's own save, and every write here sits beside the write that already
records the thing: the plan writes the day's whereabouts, the ledger writes a
settled line, the exchange writes a turn as it is spoken, the compile writes
the edges, the orbit and the pool. Nothing reads this file to decide anything
in the owner's process. If the two ever disagree, the owner's save is right
and this one has a missing write.

Every row is written the moment the thing exists, never held to the end of a
tick, and every write is guarded: a world write that fails is logged by
exception type and the pass goes on.

Nobody is named here. What a person is called arrives as an argument.

    python world/shared.py --id <world id>       # the tables, and the last row of each
"""
import argparse
import json
import os
import sqlite3
import sys
import time

if __name__ == "__main__":
    # run straight out of the package as the operator's reader: python puts
    # `world/` on the path and not the root, so nothing else would import
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logger  # noqa: E402

# The shape of the file. A reader that finds a higher number than this stops
# rather than guessing what the columns mean; the owner refuses to write into
# a file a newer build made.
#
# Adding a WHOLE TABLE does not move this number, and the room membership
# table was added without moving it. The number exists so that nobody reads
# columns whose meaning has changed underneath them; a table an older build
# has never heard of is a table it never queries, and every read here is
# guarded, so an old file that does not have it yet answers "nothing" until
# the owner next opens the file and the `IF NOT EXISTS` creates it. Moving
# the number instead would have stopped every running process, which is a
# restart nobody asked for.
SCHEMA = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);

-- the cast rows a reader may know: what a person is called and when their
-- week has them somewhere. Never a sheet: nothing of what they think or feel.
CREATE TABLE IF NOT EXISTS roster (
  key TEXT PRIMARY KEY, name TEXT, ja TEXT, role_id TEXT,
  calls TEXT, week TEXT, ts TEXT, char_id TEXT);

-- where each person is, hour by hour, for the day
CREATE TABLE IF NOT EXISTS whereabouts (
  date TEXT, person TEXT, from_hm TEXT, to_hm TEXT, place TEXT,
  with_who TEXT, reach TEXT, source TEXT, ts TEXT, char_id TEXT,
  PRIMARY KEY (date, person, from_hm, to_hm, source));

-- what the day fixed, in the plan's own words
CREATE TABLE IF NOT EXISTS settled (
  date TEXT, line TEXT, source TEXT, ts TEXT, char_id TEXT,
  PRIMARY KEY (date, line));

-- the group chat and every two-person exchange, one row per turn
CREATE TABLE IF NOT EXISTS rooms (
  date TEXT, room TEXT, who TEXT, hm TEXT, ja TEXT, gloss TEXT,
  witnessed_by TEXT, ts TEXT, char_id TEXT,
  PRIMARY KEY (date, room, hm, who, ja));

-- what each of them privately holds about another
CREATE TABLE IF NOT EXISTS graph (
  holder TEXT, about TEXT, regard INTEGER, irritation INTEGER, view TEXT,
  ts TEXT, char_id TEXT, PRIMARY KEY (holder, about));

-- the people around the people: whose brother, whose coach
CREATE TABLE IF NOT EXISTS orbit (
  owner TEXT, relation TEXT, name TEXT, note TEXT, ts TEXT, char_id TEXT,
  PRIMARY KEY (owner, relation, name));

-- what is going round that is nobody's own business
CREATE TABLE IF NOT EXISTS gossip (
  item_id TEXT PRIMARY KEY, text TEXT, heat REAL, knows TEXT,
  ts TEXT, char_id TEXT);

-- who is in a room, and since when. A room is the group chat or the two ends
-- of an exchange, named the way the `rooms` table names it. Membership is what
-- decides who a turn reaches: a girl who joined the chat at 21:04 was not in
-- the room at 20:50 and is never sent what was said then. `joined_ts` and
-- `left_ts` are on the OWNER's character clock, the one the turns are stamped
-- with, so the two can be compared; `joined` and `left` are machine local, for
-- a person reading the file. `agent` is the hub id when that member runs as
-- her own process, and "" when the owner still writes her words.
CREATE TABLE IF NOT EXISTS members (
  room TEXT, member TEXT, joined TEXT, joined_ts REAL, left TEXT, left_ts REAL,
  agent TEXT, ts TEXT, char_id TEXT,
  PRIMARY KEY (room, member));

-- what happened, at the salience the owner filed it under
CREATE TABLE IF NOT EXISTS events (
  date TEXT, kind TEXT, text TEXT, salience INTEGER, ts TEXT, char_id TEXT,
  PRIMARY KEY (date, kind, text));
"""

TABLES = ("roster", "whereabouts", "settled", "rooms", "members", "graph", "orbit", "gossip", "events")

# The column each table is read back in order of, for the reader and for the
# command line's "the last row of each".
ORDER = {"roster": "key", "whereabouts": "date, from_hm", "settled": "date", "rooms": "date, hm",
         "members": "room, member",
         "graph": "holder", "orbit": "owner", "gossip": "ts", "events": "date, ts"}

# What a character who does not own the world may write, and how her rows say
# who wrote them. She writes only about herself: these three tables, each row
# under her own char_id and -- where the table has a source column -- under the
# name of one of her own planners rather than of the owner's.
READER_TABLES = ("whereabouts", "settled", "members")
# a window her own day planner fixed, and a line her own plan settled
OWN_DAY = "her own day"
OWN_PLAN = "her own plan"
READER_SOURCES = (OWN_DAY, OWN_PLAN)


def _span(row):
    """One whereabouts row's window, with the ends a missing value implies."""
    return (str(row.get("from_hm") or "") or "00:00", str(row.get("to_hm") or "") or "24:00")


def _prefer_own(rows):
    """The whereabouts rows with each person's own rows preferred.

    The owner's planner draws a day for everybody on her roster, including a
    character who runs her own process, and that character's own day planner
    is the one that knows where she actually is. Where the two cover the same
    window hers is the answer; the owner's row stands for every window she has
    written nothing for. The list it was given, unchanged, in a world nobody
    but the owner writes into."""
    hers = {}
    for r in rows:
        if str(r.get("source") or "") == OWN_DAY:
            hers.setdefault(str(r.get("person") or ""), []).append(r)
    if not hers:
        return rows
    out = []
    for r in rows:
        mine = hers.get(str(r.get("person") or ""))
        if not mine or str(r.get("source") or "") == OWN_DAY:
            out.append(r)
            continue
        lo, hi = _span(r)
        if not any(lo < b and a < hi for a, b in (_span(x) for x in mine)):
            out.append(r)
    return out


def stamp():
    """Machine local time, which is the clock every record in this tree is
    stamped with. A world holds two processes on two character clocks and one
    machine; the machine's is the only one both of them agree about."""
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _guard(fn):
    """A world write never takes a tick down with it. The guard is here rather
    than at each of the ten call sites: a caller that has to remember to wrap
    it is a caller that will one day forget, and the failure of a copy is
    never worth the pass it was made during."""
    def go(self, *a, **k):
        try:
            return fn(self, *a, **k)
        except Exception as e:
            self._fault(f"{fn.__name__}: {type(e).__name__}: {e}")
            return False
    go.__name__ = fn.__name__
    go.__doc__ = fn.__doc__
    return go


def _js(v):
    """A dict or a list into the one text column that holds it."""
    if v in (None, "", {}, []):
        return ""
    if isinstance(v, str):
        return v
    try:
        return json.dumps(v, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(v)[:400]


class SharedWorld:
    """One character's handle on the world file: a writer if her config says
    she owns the world, and otherwise a reader who writes the rows about
    herself and nothing else.

    Built for every character whose sheet says she is in a world, and idle --
    `enabled` false, every write a no-op -- for everybody else. A writer who is
    not the owner writes the rows about herself and nothing else (`_may_write`).

    `me` is what the world's record calls this character, for the rows she may
    write about herself; left empty it is asked of her own roster the first
    time it is needed (`sim/roster.handle`)."""

    def __init__(self, config, char_id="", me=""):
        self.config = config
        sec = getattr(config, "world_shared", None)
        self.world_id = str(getattr(sec, "id", "") or "").strip()
        self.owner = bool(getattr(sec, "owner", False))
        # whether a character who does not own this world writes the rows
        # about herself at all. Off, she writes nothing, which is what the
        # world was before the partition existed.
        self.writes_own_rows = bool(getattr(sec, "reader_writes_own_rows", True))
        self.dir = str(getattr(config.world, "shared_dir", "") or "").strip()
        self.char_id = str(char_id or "").strip() or "".join(str(config.character.name).lower().split())
        self.enabled = bool(getattr(sec, "enabled", False)) and bool(self.world_id) and bool(self.dir)
        self.path = os.path.join(self.dir, self.world_id, "world.db") if self.enabled else ""
        self._con = None
        self._faults = 0
        self._said = set()
        self._me_given = str(me or "").strip()
        self._me_key = None
        self._writer_noted = 0.0
        self._own_cache = None

    # ---------------- the file ----------------

    def _fault(self, line):
        """Said once per shape of failure: a world write runs on every turn,
        and a broken file would otherwise fill the log with one line a minute."""
        self._faults += 1
        head = line.split(":")[0]
        if head in self._said:
            return
        self._said.add(head)
        logger.log(f"[shared world] {line}")

    def _open_writer(self):
        """Opened on the first write, not at construction: a harness that
        builds the App and never plans a day must leave no file behind, and
        `tools/smoke.py` builds every character on every restart."""
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        fresh = not os.path.exists(self.path)
        con = sqlite3.connect(self.path, timeout=10)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA busy_timeout=8000")
        con.executescript(SCHEMA_SQL)
        have = con.execute("SELECT value FROM meta WHERE key='version'").fetchone()
        if have and int(have["value"]) > SCHEMA:
            con.close()
            self.enabled = False
            logger.log(f"[shared world] {self.path} is version {have['value']} and this build writes {SCHEMA}; not opened")
            return
        with con:
            if self.owner:
                # which world this is, who keeps it and when it was last
                # written. A character who opens the same file to write the
                # rows about herself must not stamp these three: they say
                # whose world it is, and she only lives in it.
                con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('version',?)", (str(SCHEMA),))
                con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('world',?)", (self.world_id,))
                con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('owner',?)", (self.char_id,))
                con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('written',?)", (stamp(),))
            elif not have:
                # she has reached a world the owner has not written yet, and
                # the shape of the file she just created is this build's
                con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('version',?)", (str(SCHEMA),))
        self._con = con
        logger.log(f"[shared world] {self.world_id}: {self.path} open for writing as {self.char_id}"
                   + ("" if self.owner else " (the rows about herself only)")
                   + (" (created)" if fresh else ""))
        if not self.owner:
            self._note_writer(force=True)

    def _read_con(self):
        """A read-only connection, for a process that does not own the world.
        Never a copy: a file copy of a database being written is a torn image,
        and `mode=ro` is the same answer `tools/dbcopy.py` gives."""
        if not self.enabled or not os.path.exists(self.path):
            return None
        con = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True, timeout=10)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA busy_timeout=8000")
        return con

    def _writer(self, table="", about=None, source=""):
        """The connection this write goes through, or None when the write is
        not this character's to make."""
        if not self.enabled:
            return None
        if not self.owner and not self._may_write(table, about, source):
            return None
        if self._con is None:
            self._open_writer()
        return self._con

    def _write(self, sql, args, table="", about=None, source=""):
        con = self._writer(table, about, source)
        if con is None:
            return False
        with con:
            con.execute(sql, args)
        if not self.owner:
            self._note_writer()
        return True

    def close(self):
        if self._con is not None:
            self._con.close()
            self._con = None

    # ---------------- who may write what ----------------

    def _me(self):
        """What the world's record calls this character.

        A character promoted out of somebody else's cast still has a row in
        that cast, and the handle it is keyed by is what every shared record
        about her uses -- not the name in her own config (`sim/roster.handle`).
        Asked once, and never of an owner: she writes about everybody."""
        if self._me_key is None:
            key = self._me_given
            if not key:
                try:
                    from sim import roster
                    key = str(roster.handle(self.config) or "")
                except Exception as e:
                    self._fault(f"what this world calls this character is not resolvable: {type(e).__name__}: {e}")
                    key = ""
            self._me_key = key or self.char_id
        return self._me_key

    def _is_me(self, who):
        """Is this row about the character writing it? Her key, her Japanese
        name, her reading and every nickname the others call her by all resolve
        to herself on her own roster, so the question is asked there; the name
        she was built with answers it before the roster is reached."""
        s = str(who or "").strip()
        if not s:
            return False
        if self._me_given and s.casefold() == self._me_given.casefold():
            return True
        try:
            from sim import roster
            return bool(roster.is_self(self.config, s))
        except Exception:
            return s.casefold() == self._me().casefold()

    def writes_own(self, who=""):
        """May this character write a row about this person?

        True only for a character who does not own the world, whose own rows
        are switched on, about herself. A caller asks it to say what it means
        -- the copy of a room, of a day -- and the store enforces it anyway."""
        if not self.enabled or self.owner or not self.writes_own_rows:
            return False
        return self._is_me(who) if who else True

    def _may_write(self, table, about=None, source=""):
        """The partition, for a character who does not own the world: the rows
        about HERSELF in three tables, each saying which of her own planners
        wrote it. Everything else is refused with the fault logged, because a
        second answer to a question the world already has one answer for is
        worse than a missing row."""
        if not self.writes_own_rows:
            self._fault("the rows about herself are switched off (world_shared.reader_writes_own_rows) and one was offered")
            return False
        if table not in READER_TABLES:
            self._fault(f"the {table or 'unnamed'} table is the owner's; a character who does not keep this world may not write it")
            return False
        if about is not None and not self._is_me(about):
            self._fault(f"a row about somebody else, refused: only the rows about herself are hers to write ({str(about)[:40]})")
            return False
        if table in ("whereabouts", "settled") and source not in READER_SOURCES:
            self._fault(f"a row that does not name one of her own planners, refused: source {(source or 'none')!r}")
            return False
        return True

    _WRITER_STAMP_SECONDS = 60

    def _note_writer(self, force=False):
        """Who besides the owner has written into this world, and when each of
        them last did: `meta`'s `writers`, a JSON list. Once a minute at most
        -- a day of her own is a handful of rows, and the stamp is for a person
        reading the file rather than for a reader of the rows."""
        if self._con is None:
            return
        now = time.time()
        if not force and (now - self._writer_noted) < self._WRITER_STAMP_SECONDS:
            return
        self._writer_noted = now
        rows = []
        try:
            row = self._con.execute("SELECT value FROM meta WHERE key='writers'").fetchone()
            got = json.loads(row["value"]) if (row and row["value"]) else []
            rows = [r for r in got if isinstance(r, dict) and r.get("char_id") != self.char_id]
        except (sqlite3.Error, TypeError, ValueError):
            rows = []
        rows.append({"char_id": self.char_id, "written": stamp()})
        rows.sort(key=lambda r: str(r.get("char_id")))
        with self._con:
            self._con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('writers',?)",
                              (json.dumps(rows, ensure_ascii=False),))

    # ---------------- what the owner writes ----------------

    @_guard
    def put_person(self, key, name="", ja="", role_id="", calls=None, week=None):
        """One cast row a reader may know. What they are called and when their
        week has them somewhere -- never what they think of anybody."""
        return self._write(
            "INSERT OR REPLACE INTO roster(key,name,ja,role_id,calls,week,ts,char_id) VALUES(?,?,?,?,?,?,?,?)",
            (str(key)[:60], str(name or "")[:80], str(ja or "")[:80], str(role_id or "")[:40],
             _js(calls), _js(week), stamp(), self.char_id), table="roster")

    @_guard
    def put_whereabouts(self, date, person, from_hm, to_hm, place="", with_who="", reach="", source=""):
        """Where one person is between two times, and how reachable they are."""
        return self._write(
            "INSERT OR REPLACE INTO whereabouts(date,person,from_hm,to_hm,place,with_who,reach,source,ts,char_id)"
            " VALUES(?,?,?,?,?,?,?,?,?,?)",
            (str(date)[:10], str(person)[:60], str(from_hm)[:5], str(to_hm)[:5], str(place or "")[:120],
             str(with_who or "")[:120], str(reach or "")[:20], str(source or "")[:40], stamp(), self.char_id),
            table="whereabouts", about=person, source=source)

    @_guard
    def put_settled(self, date, line, source=""):
        """One thing the day fixed, in the plan's own words."""
        line = " ".join(str(line or "").split())[:200]
        if not line:
            return False
        # this table's natural key is the date and the line and carries no
        # person, so a character who does not keep the world never overwrites
        # a line that is already in it: the owner's wording of a line both of
        # them settled stands, and hers lands only where there is nothing.
        verb = "INSERT OR REPLACE" if self.owner else "INSERT OR IGNORE"
        return self._write(
            verb + " INTO settled(date,line,source,ts,char_id) VALUES(?,?,?,?,?)",
            (str(date)[:10], line, str(source or "")[:40], stamp(), self.char_id),
            table="settled", source=source)

    @_guard
    def put_turn(self, date, room, who, hm, ja, gloss="", witnessed_by=""):
        """One turn, the moment it is spoken. The room is the group chat or
        the two ends of an exchange, written the way the owner's record names
        it; `witnessed_by` is who else was in it, comma separated."""
        ja = str(ja or "").strip()
        if not ja:
            return False
        return self._write(
            "INSERT OR REPLACE INTO rooms(date,room,who,hm,ja,gloss,witnessed_by,ts,char_id)"
            " VALUES(?,?,?,?,?,?,?,?,?)",
            (str(date)[:10], str(room)[:40], str(who or "")[:60], str(hm or "")[:5], ja[:800],
             str(gloss or "")[:400], str(witnessed_by or "")[:200], stamp(), self.char_id), table="rooms")

    @_guard
    def put_member(self, room, member, joined="", joined_ts=0.0, left="", left_ts=0.0, agent=""):
        """That one person is in one room, and since when -- or that she has
        left it, and when.

        Written the moment the join or the leave happens, by the process that
        owns the room, so a second process can see who is in a room without
        opening anybody's save. The truth is the owner's own record; this is
        the copy every other reader gets (docs/shared-world.md)."""
        return self._write(
            "INSERT OR REPLACE INTO members(room,member,joined,joined_ts,left,left_ts,agent,ts,char_id)"
            " VALUES(?,?,?,?,?,?,?,?,?)",
            (str(room)[:40], str(member)[:60], str(joined or "")[:20], float(joined_ts or 0),
             str(left or "")[:20], float(left_ts or 0), str(agent or "")[:40], stamp(), self.char_id),
            table="members", about=member)

    @_guard
    def put_edge(self, holder, about, regard=50, irritation=0, view=""):
        """What one person holds about another, as the owner's compile settled it."""
        return self._write(
            "INSERT OR REPLACE INTO graph(holder,about,regard,irritation,view,ts,char_id) VALUES(?,?,?,?,?,?,?)",
            (str(holder)[:60], str(about)[:60], int(regard), int(irritation),
             str(view or "")[:300], stamp(), self.char_id), table="graph")

    @_guard
    def put_orbit(self, owner, relation, name="", note=""):
        """Somebody in one of the cast's own lives who is not on the roster."""
        return self._write(
            "INSERT OR REPLACE INTO orbit(owner,relation,name,note,ts,char_id) VALUES(?,?,?,?,?,?)",
            (str(owner)[:60], str(relation or "")[:60], str(name or "")[:60],
             str(note or "")[:300], stamp(), self.char_id), table="orbit")

    @_guard
    def put_gossip(self, item_id, text, heat=0.0, knows=None):
        """One thing going round, with how warm it still is and who has heard it."""
        return self._write(
            "INSERT OR REPLACE INTO gossip(item_id,text,heat,knows,ts,char_id) VALUES(?,?,?,?,?,?)",
            (str(item_id)[:60], str(text or "")[:400], float(heat or 0), _js(knows), stamp(), self.char_id),
            table="gossip")

    @_guard
    def put_event(self, date, kind, text, salience=1):
        """One thing that happened, at the salience the owner filed it under."""
        return self._write(
            "INSERT OR REPLACE INTO events(date,kind,text,salience,ts,char_id) VALUES(?,?,?,?,?,?)",
            (str(date)[:10], str(kind or "")[:40], str(text or "")[:600], int(salience or 1),
             stamp(), self.char_id), table="events")

    # ---------------- what a character writes about herself ----------------

    @_guard
    def put_own_day(self, date, person, rows):
        """Where this character is today, as her own day planner settled it.

        The whole day in one transaction, replacing what she wrote for that
        date before: the natural key is the person and the window, so a block
        that MOVED in a re-plan would otherwise leave the old answer in the
        file beside the new one. `rows` is [(from_hm, to_hm, place, reach)].

        Who she is with is not written. The people beside her are her own
        circle's, and they are not in this world (docs/shared-world.md §9);
        where she is and whether her phone is on is what the world needs."""
        con = self._writer("whereabouts", about=person, source=OWN_DAY)
        if con is None:
            return 0
        date, person = str(date)[:10], str(person)[:60]
        n = 0
        with con:
            con.execute("DELETE FROM whereabouts WHERE date=? AND person=? AND source=?",
                        (date, person, OWN_DAY))
            for lo, hi, place, reach in rows:
                if not (lo and hi):
                    continue
                con.execute(
                    "INSERT OR REPLACE INTO whereabouts(date,person,from_hm,to_hm,place,with_who,reach,source,ts,char_id)"
                    " VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (date, person, str(lo)[:5], str(hi)[:5], str(place or "")[:120], "",
                     str(reach or "")[:20], OWN_DAY, stamp(), self.char_id))
                n += 1
        self._note_writer(force=True)
        return n

    # ---------------- what anybody reads ----------------

    @_guard
    def rows(self, table, where="", args=(), limit=500):
        """A table, oldest first. The owner reads through her own connection,
        anybody else through a read-only one opened for the call: a reader is
        a different process and holds nothing open between looks."""
        if table not in TABLES:
            raise ValueError(f"no table {table!r} in the world file")
        sql = f"SELECT * FROM {table}" + (f" WHERE {where}" if where else "") \
            + f" ORDER BY {ORDER[table]} LIMIT {int(limit)}"
        con = self._con if (self.owner and self._con is not None) else self._read_con()
        if con is None:
            return []
        try:
            return [dict(r) for r in con.execute(sql, tuple(args)).fetchall()]
        finally:
            if con is not self._con:
                con.close()

    def roster(self):
        return self.rows("roster") or []

    def whereabouts(self, date):
        """Where the day has each person, with each person's own rows preferred
        over the owner's draw of her week (`_prefer_own`)."""
        return _prefer_own(self.rows("whereabouts", "date=?", (str(date)[:10],)) or [])

    def their_own_whereabouts(self, date):
        """Only the rows a character wrote about HERSELF, for the owner's
        planner: her own draw of a week stands for everybody else, and these
        are the windows that outrank it.

        Kept for as long as the file is untouched. The planner asks this for
        every person on every line it writes and at every look at whether
        somebody's phone is on, and the answer only changes when somebody
        writes the file."""
        date = str(date)[:10]
        try:
            st = os.stat(self.path) if self.path else None
            mark = (st.st_mtime_ns, st.st_size) if st else (0, 0)
        except OSError:
            mark = (0, 0)
        got = self._own_cache
        if got and got[0] == date and got[1] == mark:
            return got[2]
        rows = self.rows("whereabouts", "date=? AND source=?", (date, OWN_DAY)) or []
        self._own_cache = (date, mark, rows)
        return rows

    def settled(self, date):
        return self.rows("settled", "date=?", (str(date)[:10],)) or []

    def turns(self, date, room=""):
        if room:
            return self.rows("rooms", "date=? AND room=?", (str(date)[:10], str(room))) or []
        return self.rows("rooms", "date=?", (str(date)[:10],)) or []

    def events(self, date):
        return self.rows("events", "date=?", (str(date)[:10],)) or []

    def gossip(self, limit=200):
        """What is going round, warmest first. A reader whose own pool is
        switched off (she is in a world she does not keep) has this and
        nothing else."""
        rows = self.rows("gossip", limit=limit) or []
        return sorted(rows, key=lambda r: -float(r.get("heat") or 0))

    def orbit(self, owner="", limit=200):
        """The people around the people: whose brother, whose coach."""
        if owner:
            return self.rows("orbit", "owner=?", (str(owner),), limit=limit) or []
        return self.rows("orbit", limit=limit) or []

    def graph(self, about="", limit=200):
        """What each of them privately holds about another, as the owner's
        compile settled it. `about` narrows it to what they hold about one
        person -- which for a reader is usually herself."""
        if about:
            return self.rows("graph", "about=?", (str(about),), limit=limit) or []
        return self.rows("graph", limit=limit) or []

    # ---------------- the same rows as lines, for a prompt ----------------
    #
    # A reader puts these in front of a model where a subsystem of her own
    # would have. The wording is the file's own and names nobody: what a
    # person is called arrives in the rows.

    def whereabouts_lines(self, date, limit=40):
        """Where the day has each person, one line per person."""
        by = {}
        for r in self.whereabouts(date)[:limit]:
            who = str(r.get("person") or "")
            if not who:
                continue
            bit = "%s %s-%s" % (str(r.get("place") or "somewhere"),
                                str(r.get("from_hm") or ""), str(r.get("to_hm") or ""))
            reach = str(r.get("reach") or "")
            if reach and reach != "away":
                bit += " (phone %s)" % reach
            by.setdefault(who, []).append(bit)
        return ["- %s: %s" % (who, "; ".join(bits)) for who, bits in by.items()]

    def gossip_lines(self, limit=8):
        return ["- " + str(r.get("text") or "") for r in self.gossip()[:int(limit)]
                if str(r.get("text") or "").strip()]

    def orbit_lines(self, limit=8):
        out = []
        for r in self.orbit()[:int(limit)]:
            head = "%s's %s" % (str(r.get("owner") or ""), str(r.get("relation") or "someone"))
            nm = str(r.get("name") or "")
            note = str(r.get("note") or "")
            out.append("- " + head + (", %s" % nm if nm else "") + (": %s" % note if note else ""))
        return out

    def settled_lines(self, date, limit=8):
        return [str(r.get("line") or "") for r in self.settled(date)[:int(limit)]
                if str(r.get("line") or "").strip()]

    def members(self, room=""):
        """Who is in a room, or everybody in every room. A row with `left`
        set is somebody who WAS in it: the row is kept, because who was in
        the room when a thing was said is the question this table answers."""
        if room:
            return self.rows("members", "room=?", (str(room),)) or []
        return self.rows("members") or []

    @_guard
    def counts(self):
        """Row count per table, for the operator and for a reader deciding
        whether the world has been written yet.

        A table this build knows and the file does not is counted as nothing
        rather than taking the whole count down: a world file written before
        a table existed is a file the owner has not reopened yet, not a
        broken one."""
        con = self._con if (self.owner and self._con is not None) else self._read_con()
        if con is None:
            return {}
        out = {}
        try:
            for t in TABLES:
                try:
                    out[t] = int(con.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"])
                except sqlite3.Error:
                    out[t] = 0
            return out
        finally:
            if con is not self._con:
                con.close()

    def report(self):
        """`/sweep` and the operator: what the world holds, and who wrote it."""
        if not self.enabled:
            return "shared world: OFF (no world id, no directory, or the section is off)"
        head = (f"shared world {self.world_id}: {self.path} | this character is "
                + ("the OWNER and writes it" if self.owner else
                   ("a READER, and writes the rows about herself" if self.writes_own_rows else "a READER")))
        c = self.counts() or {}
        if not c:
            return head + "\n  (the file does not exist yet)"
        return head + "\n" + "\n".join(f"  {t:<12} {c.get(t, 0):>6}" for t in TABLES)


# The two sources named on the class as well, so a caller holding a store does
# not spell the string. Here rather than in the class body, where the name on
# the left would shadow the module's own on the right.
SharedWorld.OWN_DAY = OWN_DAY
SharedWorld.OWN_PLAN = OWN_PLAN


# ---------------- the reader on the command line ----------------

def _last(w, table):
    rows = w.rows(table, limit=100000) or []
    return rows[-1] if rows else None


def main():
    from config import DEFAULTS
    ap = argparse.ArgumentParser(description="what one world file holds")
    ap.add_argument("--id", required=True, help="the world id, the directory under --dir")
    ap.add_argument("--dir", default=DEFAULTS["world"]["shared_dir"],
                    help="where the worlds live (config key world.shared_dir)")
    a = ap.parse_args()

    from types import SimpleNamespace as NS
    cfg = NS(world_shared=NS(enabled=True, id=a.id, owner=False),
             world=NS(shared_dir=a.dir), character=NS(name="reader"))
    w = SharedWorld(cfg, char_id="reader")
    print(w.report())
    if not os.path.exists(w.path or ""):
        return 1
    for t in TABLES:
        r = _last(w, t)
        if r:
            bits = ", ".join(f"{k}={str(v)[:40]}" for k, v in r.items() if v not in ("", None))
            print(f"  {t:<12} last: {bits[:160]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
