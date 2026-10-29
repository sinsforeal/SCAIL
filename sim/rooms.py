"""A room, as a thing people are in and can leave.

Until this file a room was a string on a turn. The exchange wrote `group`, or
`line:<somebody>`, into the shared world beside every line spoken, and who was
in the room was re-derived from the roster at each write. That is enough while
one process speaks for everybody in it.

It stops being enough the moment one of those people runs as her own process.
Then a turn has to be *delivered*, and only to the people who were actually in
the room when it was said: somebody who joined at nine did not see what was
said at eight, and somebody who left at ten does not hear what came after. So a
room gets a membership, with the moment each person joined and the moment she
left.

**Where it lives.** The truth is a row in the owning character's own save (kv
`rooms`), like every other fact she keeps. A copy goes into the shared world's
`members` table the instant a join or a leave happens, so a second process can
read who is in a room without opening anybody's save (docs/shared-world.md: the
world file is a copy, never the truth).

**How a turn travels.** Every turn spoken in a room is offered to each member
who runs her own process, except the speaker, and only if she was in the room
at the moment of that turn. When the room actually wants HER words -- her turn
in a conversation, or the thing the day's plan has her open with -- the same
message goes with `asking` set, carrying what she has not been sent, the moves
the conversation has already made, and how long the room will wait. What comes
back is one more turn in the room and one line of what it came to, appended
where it lands.

**The hub is the only wire.** This module never speaks to the network: it
writes what it wants sent to kv `room_out`, and the one object in the process
that holds a hub connection (`sim/peers.py`) empties that queue on its own
pass. Written to the save the moment it exists, so a stop mid-pass loses
nothing, and the character's process needs no second connection.

Nobody is named here. A room is a string, a member is a roster key, and who
runs herself is the `agent` field on her roster row (`sim/roster.py`).
"""
import logger
from sim import roster
from world.shared import stamp

# What a member sends back when the room asked her and she would say nothing.
# The hub refuses an empty body, so the silence travels as this token in the
# text and as `silent` on the envelope; the room reads the envelope and files
# no turn, and the token is never shown to anybody. Without it a chosen
# silence and a dead process looked the same and the room sat out the whole
# deadline for an answer that had already arrived.
SILENT = "(nothing)"

# how many rows the two queues hold before the oldest are dropped. A queue
# that grows without a reader is a leak; a queue that drops the newest is a
# lost turn, so it is the oldest that go.
QUEUE_KEEP = 200
# and how many turns of a room a participant keeps on her own side
ROOM_KEEP = 60


def name_for(kind, key=""):
    """What the record calls this room.

    The group chat is one room everybody in it shares. Anything else -- a LINE
    thread, a call, the kitchen -- is the two ends of it, and is named after
    the person who is not the character whose process this is. The same string
    the shared world's `rooms` table has always used, so the membership and the
    turns line up without a translation between them."""
    kind = str(kind or "line")
    return "group" if kind == "group" else f"{kind}:{key}"


def moves_block(moves, config=None, limit=8):
    """The moves this conversation has already made, one line each.

    A room kept every word anybody had said and no record of what those words
    were FOR, so each call re-derived a speaker's next turn from roughly the
    same state and got roughly the same turn. One girl played "fine, I will
    ask, but I am still the one who decides" at 07:19 and again at 07:23 in
    different words, which no test on the words could catch. The gist every
    writing call already returns is that record; this is how it is read back.

    Rendered by both writers -- the process that owns the room and the process
    of a member who writes her own turns -- from the same list, so the two
    sides cannot disagree about what has been tried."""
    rows = [m for m in (moves or []) if isinstance(m, dict) and str(m.get("gist") or "").strip()]
    if not rows:
        return ""
    from sim import lang
    t = lang.say(config)
    head = t("MOVES ALREADY MADE IN THIS CONVERSATION, each once. A move that landed is done: go "
             "on to something else. A move nobody answered is dropped, or made shorter and "
             "harder. Nobody plays the same beat twice:",
             "この会話ですでに打った手。それぞれ一度きり。通った手はもう終わり、次へ行く。返事がなかった手は、"
             "やめるか、短くきつくするか。同じ手を二度は打たない:")
    body = "\n".join("  - [%s] %s: %s" % (str(m.get("hm") or ""), str(m.get("who") or ""),
                                          str(m.get("gist"))[:120])
                     for m in rows[-int(limit or 8):])
    return head + "\n" + body


def members_for(config, kind, other_key, relationships=None, me_key=""):
    """Who is in this room, from the roster and the character's own meters.

    The group chat is her and every friend who is not dormant and not family;
    anything else is the two ends of it. One rule, in one place, because the
    membership and the question `roster.witnessed` answers about a stored
    conversation have to agree -- written twice they would drift, and a room
    whose members disagree with who was in it is a room whose transcript
    nobody can account for."""
    me = str(me_key or "")
    if str(kind or "") != "group":
        return sorted({k for k in (me, str(other_key or "")) if k})
    out = {me} if me else set()
    for k, r in (relationships or {}).items():
        # family is not in the group chat: the roster answers it (a row may say
        # so itself, and her own mother's role id is her own), and the row's
        # own role id stands in when the meter names somebody the roster has
        # lost
        # somebody's household is out of the friend group whoever's it is:
        # hers (`is_family`), anybody else's (`family_of`, a row that names
        # whose it is), and a row whose own role id says so
        if k == "him" or r.get("dormant") or roster.is_family(config, k) \
                or roster.family_of(config, k) \
                or str(r.get("role_id") or "") in roster.FAMILY_ROLES:
            continue
        key = roster.key_of(config, r.get("name", k))
        if key and not roster.same(config, key, "him"):
            out.add(key)
    return sorted(x for x in out if x)


class Rooms:
    """The rooms this character's process owns, and who is in each.

    Built wherever it is needed rather than passed around: every piece of its
    state is in the save, so two instances in one process are one thing seen
    twice. The instance that has the shared world writes the copy; the one that
    has the hub connection empties the outbound queue."""

    def __init__(self, config, store, clock, channel=None, world_shared=None):
        self.config = config
        self.store = store
        self.clock = clock
        self.channel = channel
        self.world_shared = world_shared

    # ---------------- who is in what ----------------

    def _all(self):
        rec = self.store.get("rooms", {}) or {}
        return rec if isinstance(rec, dict) else {}

    def members(self, room):
        """{roster key: the membership row} for one room, joined and left."""
        return dict(self._all().get(str(room), {}) or {})

    def present(self, room, at_ts=None):
        """The roster keys of everybody in the room -- now, or at a moment."""
        ts = float(at_ts) if at_ts is not None else self.clock.now_ts()
        out = []
        for key, row in self.members(room).items():
            if float(row.get("joined_ts") or 0) > ts:
                continue
            left = float(row.get("left_ts") or 0)
            if left and left <= ts:
                continue
            out.append(key)
        return sorted(out)

    def in_room(self, room, key, at_ts=None):
        return key in self.present(room, at_ts)

    def agents_present(self, room, at_ts=None):
        """[(roster key, hub id)] for the members who run their own process
        and were in the room at that moment."""
        out = []
        for key in self.present(room, at_ts):
            hub = roster.agent_of(self.config, key)
            if hub:
                out.append((key, hub))
        return out

    # ---------------- joining and leaving ----------------

    def join(self, room, key, at_ts=None):
        """One person is in this room from now on. Said out loud, because a
        room quietly gaining a member is a room whose transcript nobody can
        account for."""
        room, key = str(room), str(key)
        if not room or not key:
            return False
        all_rooms = self._all()
        rows = dict(all_rooms.get(room, {}) or {})
        ts = float(at_ts) if at_ts is not None else self.clock.now_ts()
        was = rows.get(key) or {}
        if was and not float(was.get("left_ts") or 0):
            return False                      # already in it; nothing happened
        hub = roster.agent_of(self.config, key)
        rows[key] = {"joined": stamp(), "joined_ts": ts, "left": "", "left_ts": 0.0, "agent": hub}
        all_rooms[room] = rows
        self.store.set("rooms", all_rooms)
        self._to_world(room, key, rows[key])
        logger.log(f"[room] {room}: {key} joined at {self.clock.hm(ts)}"
                   + (f", and writes her own turns (as '{hub}')" if hub else ""))
        return True

    def leave(self, room, key, at_ts=None):
        """One person is out of this room. Her rows stay -- who was in the
        room when a thing was said is what the membership is FOR -- and
        nothing said after this moment is sent to her."""
        room, key = str(room), str(key)
        all_rooms = self._all()
        rows = dict(all_rooms.get(room, {}) or {})
        row = rows.get(key)
        if not row or float(row.get("left_ts") or 0):
            return False
        ts = float(at_ts) if at_ts is not None else self.clock.now_ts()
        row = dict(row, left=stamp(), left_ts=ts)
        rows[key] = row
        all_rooms[room] = rows
        self.store.set("rooms", all_rooms)
        self._to_world(room, key, row)
        logger.log(f"[room] {room}: {key} left at {self.clock.hm(ts)}")
        return True

    def settle(self, room, keys, at_ts=None):
        """The room's membership as the roster now has it: everybody in `keys`
        who is not in the room joins, everybody in the room who is not in
        `keys` leaves. A diff, so an unchanged room writes nothing at all."""
        keys = [str(k) for k in (keys or []) if str(k or "")]
        moved = 0
        for k in keys:
            if self.join(room, k, at_ts):
                moved += 1
        for k in list(self.members(room)):
            if k not in keys and self.leave(room, k, at_ts):
                moved += 1
        return moved

    def _to_world(self, room, key, row):
        """The copy another process reads. Guarded where the write is, not at
        the call site (world/shared.py), so a world that is off or broken
        costs the join nothing."""
        w = self.world_shared
        if not (w and getattr(w, "enabled", False) and getattr(w, "owner", False)):
            return
        w.put_member(room, key, joined=row.get("joined", ""), joined_ts=row.get("joined_ts", 0),
                     left=row.get("left", ""), left_ts=row.get("left_ts", 0),
                     agent=row.get("agent", ""))

    # ---------------- what is sent ----------------

    def _sent(self):
        rec = self.store.get("room_sent", {}) or {}
        return rec if isinstance(rec, dict) else {}

    def _mark_sent(self, room, key, ts):
        rec = self._sent()
        rows = dict(rec.get(room, {}) or {})
        rows[key] = max(float(rows.get(key) or 0), float(ts or 0))
        rec[room] = rows
        self.store.set("room_sent", rec)

    def _unsent(self, room, key, turns, limit=12):
        """The turns of this room she has not been sent: nothing from before
        she joined, nothing she has already had, and nothing she said."""
        row = self.members(room).get(key) or {}
        since = max(float(row.get("joined_ts") or 0), float((self._sent().get(room, {}) or {}).get(key) or 0))
        out = []
        for t in (turns or []):
            ts = float(t.get("ts") or 0)
            if ts and ts <= since:
                continue
            out.append({"who": t.get("who", ""), "ja": t.get("ja") or t.get("text", ""),
                        "hm": t.get("hm", ""), "ts": ts})
        return out[-int(limit or 12):]

    def _queue(self, to, text, envelope):
        """One message to another process, written to the save now and put on
        the hub by whoever holds the connection, on its own pass."""
        rows = list(self.store.get("room_out", []) or [])
        rows.append({"to": str(to), "text": str(text or "")[:2000], "room": envelope})
        self.store.set("room_out", rows[-QUEUE_KEEP:])

    def _envelope(self, room, kind, date, hm, asking, turns=(), present=(),
                  cue="", about="turn", beat_id="", wait_s=0, silent=False, moves=(), gist="",
                  said_today=()):
        return {"id": str(room), "kind": str(kind or "line"), "date": str(date or ""),
                "hm": str(hm or ""), "asking": bool(asking), "turns": list(turns),
                "present": list(present), "cue": str(cue or ""), "about": str(about or "turn"),
                "beat_id": str(beat_id or ""), "wait_s": int(wait_s or 0),
                # the moves already made in this conversation, one line each
                # (`docs/room-quality.md`): the room's own memory of what has
                # been tried, so a member writing her turn in her own process
                # can see that she has already played a beat and the room
                # does not get it twice in four minutes
                "moves": list(moves),
                # ...and what the character whose room this is has already
                # said to her today in other conversations
                # (`sim/said_today.py`), so the member answering is not told
                # the same thing twice by two rooms and can treat it as the
                # old news it is
                "said_today": list(said_today),
                # ...and, on the way back, one line of what her turn came to,
                # which is the next entry in that list
                "gist": str(gist or "")[:200],
                # she was asked and would say nothing; there is no turn in this
                # message and the room settles on it (`SILENT` above)
                "silent": bool(silent)}

    def post_turn(self, room, kind, date, turn, speaker_key):
        """One turn, out to every member of the room who writes her own words
        -- except whoever just spoke, and except anybody who was not in the
        room at the moment it was said."""
        ts = float(turn.get("ts") or 0) or self.clock.now_ts()
        sent = 0
        for key, hub in self.agents_present(room, ts):
            if key == speaker_key:
                continue
            env = self._envelope(room, kind, date, turn.get("hm", ""), False,
                                 turns=[{"who": turn.get("who", ""), "ja": turn.get("ja") or turn.get("text", ""),
                                         "hm": turn.get("hm", ""), "ts": ts}],
                                 present=self.present(room, ts))
            self._queue(hub, turn.get("ja") or turn.get("text", ""), env)
            self._mark_sent(room, key, ts)
            sent += 1
        return sent

    def ask(self, room, kind, date, key, turns=(), cue="", about="turn", beat_id="",
            wait_s=180, hm="", limit=12, moves=(), said_today=()):
        """The room is waiting for this person's own words.

        Carries what she has not been sent, who is in the room with her, the
        moves the conversation has already made, the moment, and how long the
        room will wait before going on without her. Returns the hub id it was
        addressed to, or "" when nobody there runs herself."""
        hub = roster.agent_of(self.config, key)
        if not hub:
            return ""
        now = self.clock.now_ts()
        unsent = self._unsent(room, key, turns, limit)
        present = self.present(room, now)
        hm = hm or self.clock.hm(now)
        line = (f"{hm} — {room}. " + (cue or "the room is waiting for you.")).strip()
        env = self._envelope(room, kind, date, hm, True, turns=unsent, present=present,
                             cue=cue, about=about, beat_id=beat_id, wait_s=wait_s, moves=moves,
                             said_today=said_today)
        self._queue(hub, line, env)
        for t in unsent:
            self._mark_sent(room, key, t.get("ts") or now)
        logger.log(f"[room] {room}: {key} writes her own turn; asked '{hub}' with "
                   f"{len(unsent)} turn(s) she had not seen, waiting up to {int(wait_s)}s")
        return hub

    # ---------------- what comes back ----------------

    def put(self, key, envelope, text, who=""):
        """A turn written by another process, filed for the room's owner to
        append on its next pass. Written to the save the moment it arrives:
        the process that appends it is not the one that received it."""
        rows = list(self.store.get("room_in", []) or [])
        rows.append({"room": str(envelope.get("id") or ""), "kind": str(envelope.get("kind") or ""),
                     "about": str(envelope.get("about") or "turn"),
                     "beat_id": str(envelope.get("beat_id") or ""),
                     "key": str(key), "who": str(who or key), "ja": str(text or ""),
                     # what her own writer said this turn came to, so the
                     # room's moves ledger has her entry too and the next
                     # round can see she has already played it
                     "gist": str(envelope.get("gist") or "")[:200],
                     "ts": self.clock.now_ts()})
        self.store.set("room_in", rows[-QUEUE_KEEP:])
        return True

    def take(self, about="turn", room="", beat_id=""):
        """The arrived turns of one kind, removed from the queue. A reader
        takes what is its own and leaves the rest: the beat path and the
        exchange path drain the same queue.

        `beat_id` narrows it to the answer to one particular beat. The beat
        path is handed one beat at a time, and draining the whole queue for
        it threw away the answer to any other beat that had come back in the
        same second."""
        rows = list(self.store.get("room_in", []) or [])
        mine, rest = [], []
        for r in rows:
            if (r.get("about") == about and (not room or r.get("room") == room)
                    and (not beat_id or str(r.get("beat_id") or "") == str(beat_id))):
                mine.append(r)
            else:
                rest.append(r)
        if mine:
            self.store.set("room_in", rest)
        return mine

    # ---------------- the outbound queue ----------------

    def flush(self, channel=None):
        """Everything waiting for the hub, sent once. A message that does not
        go is logged and dropped rather than retried: the hub answers `known`
        false when nobody is there, and a queue that retries is a queue that
        floods a mailbox after an outage."""
        ch = channel or self.channel
        rows = list(self.store.get("room_out", []) or [])
        if not rows or ch is None or not hasattr(ch, "peer_send"):
            return 0
        self.store.set("room_out", [])
        sent = 0
        for r in rows:
            try:
                if ch.peer_send(r.get("to", ""), r.get("text", ""), room=r.get("room")):
                    sent += 1
                else:
                    logger.log(f"[room] not delivered to '{r.get('to')}': the hub took nothing")
            except Exception as e:
                logger.log(f"[room] not delivered to '{r.get('to')}': {type(e).__name__}: {e}")
        return sent

    # ---------------- the operator's view ----------------

    def report(self):
        all_rooms = self._all()
        if not all_rooms:
            return "rooms: none yet (nobody on the roster runs her own process)"
        out = []
        for room in sorted(all_rooms):
            here, gone = [], []
            for key, row in sorted(all_rooms[room].items()):
                mark = key + (f" [{row['agent']}]" if row.get("agent") else "")
                (gone if float(row.get("left_ts") or 0) else here).append(mark)
            out.append(f"  {room}: " + ", ".join(here) + (("  (left: " + ", ".join(gone) + ")") if gone else ""))
        waiting = len(self.store.get("room_out", []) or [])
        arrived = len(self.store.get("room_in", []) or [])
        return ("rooms and who is in them:\n" + "\n".join(out)
                + f"\n  {waiting} message(s) waiting for the hub, {arrived} turn(s) arrived and not yet placed")
