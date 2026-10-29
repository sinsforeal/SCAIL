"""Two running characters, talking to each other.

Each character is her own process with her own save and her own model, and
the hub they both register with is the relay: `Channel.peer_send` puts a
message in the other one's mailbox, `Channel.peer_updates` reads what has
been put in hers. Nothing here knows anything about the other process --
not her config, not her save, not her schedule, not whether she is awake.
What arrives is words and a hub id, and that is deliberately all: a
character learns a peer the way she learns him, by being told.

**This is not the path his messages take.** `App.poll_inbound` runs the
relationship with him -- attachment, the primitives, foresight, the
expectations of him, the questions she asked him, whether she was holding
out, the state of a rupture -- and none of that is true of somebody else's
message. A peer message reaches her mind through exactly two doors: her
history (`sim/thread.py`, as a room of its own) and, once, the company a
conversation is (`State.talk_relief` at the close).

**Code decides when, the model decides what.** Four bounds, all hers, all
deterministic, so two bots cannot run away with each other and neither has
to trust the other to stop: her turns in one conversation (`max_turns`),
what she sends in a day (`max_per_day`), a floor under two sends of hers
(`min_gap_seconds`) on top of a reading-and-typing delay taken from the
length of what she is answering, and a window with her phone access
(`open_from_hm`..`open_to_hm`, and the scene's `phone_access`).

Nobody is named here. The contacts are `peer_talk.contacts` in her own
config: the peer's hub id, what THIS character calls her, and the language
of the room. Config, never code, for the same reason
`character.writes_to_him` is (docs/peer-talk.md).

The store:

  kv `peer_live`     the conversation in flight, or None
  kv `peer_chat`     the closed ones, newest last, capped at `keep`
  kv `peer_last_id`  the hub cursor, so nothing is delivered twice
  kv `peer_counts`   {date: what she sent that day}
  kv `peer_rooms`    the rooms she is a member of but does not own, and the
                     turns of each she has been sent

**Her record of a room has three readers.** The call that writes her next turn
in it (below), her own history (`sim/thread.py _records`, so a room she took
part in is still there between rounds rather than only inside the one call),
and the group view on his phone (`channels/talkapp_bot.py _group`, so what he
sees of her friends' chat is what she has actually been shown). Until
2026-09-06 it had one, and her six turns in the group chat that evening left no
trace in her history and drew nothing on his screen.

**A message may be a room rather than a conversation.** The same mailbox
carries turns in a room two or more of them are in -- the group chat, or a
two-person exchange -- which is how somebody who used to be written by
another process comes to say her own words (`sim/rooms.py`,
docs/peer-talk.md). One rule tells the two apart and it is on the message:
a message carrying a `room` is a turn in that room, and everything else is
one character writing to another. A room needs no contact row, because the
people in it are people in her world rather than somebody she was told
about.
"""
import random

import logger
from sim import lang
from sim import lore_rooms
from sim import roster
from sim import pocket as pocket_mod
from sim import rooms as rooms_mod
from sim.rooms import Rooms, moves_block
from sim.said_today import SaidToday
from sim.textutil import drop_echoes
from sim.thread import place_tail

# What her answer must come back as. A JSON key has no audience and stays
# English wherever the prose around it goes.
JSON_SHAPE = ('{"messages": ["...", "..."], "gist": "..."}  '
              '-- `messages` is what she sends now, one string per message, at most two, '
              'and an EMPTY list is the right answer when she would leave it sitting; '
              '`gist` is one short line of what the conversation came to, for her own record.')


class Peers:
    """Her side of it. One instance per character, built by the runtime for
    every character, and idle for a character with no contacts."""

    def __init__(self, config, llm, store, clock, channel, state, persona, thread, ledger=None):
        self.config = config
        self.llm = llm
        self.store = store
        self.clock = clock
        self.channel = channel
        self.state = state
        self.persona = persona
        self.thread = thread
        self.ledger = ledger
        self._capped = ""
        # the pocket items the last call was shown, marked once it came back
        self._pocket_ids = []
        # the rooms she is in, and the queue between this process and the hub.
        # Every piece of its state is in the save, so the copy the exchange
        # holds and this one are one thing seen twice (`sim/rooms.py`).
        self.rooms = Rooms(config, store, clock, channel=channel)
        # ...and her own memory of what she has said to whom today, built
        # here for the same reason: all of its state is in the save, so the
        # instance the runtime holds and this one are one thing seen twice
        self.said_today = SaidToday(config, store, clock)

    # ---------------- who she can write to ----------------

    @property
    def c(self):
        return self.config.peer_talk

    def on(self):
        return bool(getattr(self.c, "enabled", False)) and bool(self.contacts())

    def reads_mailbox(self):
        """Whether the mailbox is looked at this pass at all.

        Peer talk being on is one reason. The other is that somebody in her
        own world runs as her own process: her turns come back through this
        same mailbox and she is not a contact -- she is one of the people
        already on the roster, and what makes her different is one field on
        her row (`sim/roster.py`)."""
        if bool(getattr(self.c, "enabled", False)):
            return True
        try:
            return bool(roster.agents(self.config))
        except Exception:
            return False

    def contacts(self):
        """[{id, name, language}] from her own config, malformed rows dropped."""
        out = []
        for row in (getattr(self.c, "contacts", None) or []):
            if not isinstance(row, dict):
                continue
            cid = str(row.get("id") or "").strip()
            if not cid:
                continue
            out.append({"id": cid,
                        "name": str(row.get("name") or cid).strip() or cid,
                        "language": str(row.get("language") or "").strip().lower()})
        return out

    def contact(self, cid):
        for row in self.contacts():
            if row["id"] == str(cid or ""):
                return row
        return None

    # ---------------- the record ----------------

    def live(self):
        rec = self.store.get("peer_live") or None
        return rec if isinstance(rec, dict) and rec.get("turns") else None

    def _me(self):
        return str(getattr(self.config.character, "name", "") or "her")

    def _mine(self, rec):
        return [t for t in (rec.get("turns") or []) if t.get("who") == self._me()]

    def _sent_today(self):
        return int((self.store.get("peer_counts", {}) or {}).get(self.clock.date_str(), 0) or 0)

    def _read_delay(self, text):
        """She read it and then typed. The same shape the cast exchange uses:
        the length of what she is answering, plus a pause."""
        return len(str(text or "")) / 6.0 + random.uniform(15, 90)

    def _open_record(self, who, ts):
        return {"date": self.clock.date_str(ts), "hm": self.clock.hm(ts), "kind": "peer",
                "who": who["name"], "peer": who["id"], "turns": [], "gist": "",
                "started_ts": ts, "next_ts": ts}

    # ---------------- what arrives ----------------

    def poll(self):
        """What another character has said to her since the last look. Each
        message is written to the save before the cursor moves past it: a
        message counted and then lost is a message nobody can see was lost."""
        if not self.reads_mailbox():
            return 0
        cur = int(self.store.get("peer_last_id", 0) or 0)
        try:
            rows = self.channel.peer_updates(after=cur) or []
        except Exception as e:
            logger.log(f"[peer] the mailbox was not read: {type(e).__name__}: {e}")
            return 0
        got = 0
        for m in sorted(rows, key=lambda r: int(r.get("id") or 0)):
            mid = int(m.get("id") or 0)
            if mid <= cur:
                continue
            env = m.get("room")
            if isinstance(env, dict) and env.get("id"):
                # a turn in a room, not a message to her: a different door
                # entirely, and none of the conversation machinery below
                self._room_message(m, env)
                cur = mid
                self.store.set("peer_last_id", cur)
                got += 1
                continue
            who = self.contact(m.get("from"))
            if who is None:
                # somebody registered with the hub who is not on her list. Not
                # an error and not answered: she has no idea who that is.
                logger.log(f"[peer] a message from '{m.get('from')}' with no contact row of hers: not delivered")
            else:
                self._receive(who, str(m.get("text") or ""), float(m.get("ts") or self.clock.now_ts()))
                got += 1
            cur = mid
            self.store.set("peer_last_id", cur)
        return got

    def _receive(self, who, text, ts):
        if not str(text or "").strip():
            return
        rec = self.live()
        if rec and rec.get("peer") != who["id"]:
            self._finish(rec, "somebody else wrote to her")
            rec = None
        if not rec:
            rec = self._open_record(who, ts)
        rec["turns"].append({"who": who["name"], "ja": str(text), "hm": self.clock.hm(ts), "ts": ts})
        rec["next_ts"] = max(float(rec.get("next_ts") or 0), ts + self._read_delay(text))
        self.store.set("peer_live", rec)
        logger.log(f"[peer] {who['name']} -> her: {str(text)[:140]}")

    # ---------------- the gates ----------------

    def _in_window(self):
        hm = self.clock.hm()
        lo = str(getattr(self.c, "open_from_hm", "00:00") or "00:00")
        hi = str(getattr(self.c, "open_to_hm", "24:00") or "24:00")
        return lo <= hm < hi

    def _phone_away(self, scene):
        return str((scene or {}).get("phone_access", "") or "") == "none"

    def _cannot_send(self, scene, rec=None):
        """Why she cannot send anything this pass, or "" when she can."""
        if self._phone_away(scene):
            return "her phone is away"
        if not self._in_window():
            return "outside the hours she writes in"
        if self._sent_today() >= int(getattr(self.c, "max_per_day", 12) or 12):
            return "she has said her piece for today"
        if rec is not None:
            mine = self._mine(rec)
            if len(mine) >= int(getattr(self.c, "max_turns", 6) or 6):
                return "she has had her turns in this one"
            if mine:
                gap = self.clock.now_ts() - float(mine[-1].get("ts") or 0)
                if gap < float(getattr(self.c, "min_gap_seconds", 90) or 90):
                    return "she only just wrote"
        return ""

    def _quiet_for(self):
        """Minutes since the last peer message in EITHER direction."""
        last = 0.0
        rec = self.live()
        rows = list(self.store.get("peer_chat", []) or []) + ([rec] if rec else [])
        for x in rows:
            for t in (x.get("turns") or []):
                last = max(last, float(t.get("ts") or 0))
        if not last:
            return 10 ** 6
        return (self.clock.now_ts() - last) / 60.0

    # ---------------- the loop's one entry ----------------

    def tick(self, scene=None):
        """Once per pass: put on the hub whatever a room has waiting, read the
        mailbox, answer if it is her turn and she can, otherwise consider
        opening one.

        The room queue is emptied whether or not she has a peer to write to:
        this object is the only one in the process holding a hub connection,
        and the rooms it carries messages for belong to her own world."""
        # the scene is the phone gate for anything the mailbox brings back
        # during this pass, and `poll` is two calls deep from here
        self._scene = scene
        if self.reads_mailbox():
            self.rooms.flush()
        self.poll()
        if not self.on():
            return
        rec = self.live()
        if rec:
            over = float(getattr(self.c, "live_minutes", 120) or 120) * 60
            if self.clock.now_ts() - float(rec.get("started_ts") or 0) > over:
                self._finish(rec, "it trailed off")
                return
            turns = rec.get("turns") or []
            if turns and turns[-1].get("who") == self._me():
                return                      # she has the last word; nothing to answer
            if self.clock.now_ts() < float(rec.get("next_ts") or 0):
                return                      # she has not read it yet
            why = self._cannot_send(scene, rec)
            if why:
                if self._capped != why:
                    self._capped = why
                    logger.log(f"[peer] {rec.get('who')} is waiting: {why}")
                return
            self._capped = ""
            self._write(rec, scene)
            return
        self._maybe_open(scene)

    def _maybe_open(self, scene):
        rows = self.contacts()
        if not rows:
            return
        if self._cannot_send(scene):
            return
        if self._quiet_for() < float(getattr(self.c, "min_gap_minutes", 45) or 45):
            return
        if random.random() > float(getattr(self.c, "open_p", 0.02) or 0.02):
            return
        who = random.choice(rows)
        rec = self._open_record(who, self.clock.now_ts())
        # nothing is recorded before the action it claims happened: the record
        # is opened with no turns and only becomes a conversation if she
        # actually writes one
        self._write(rec, scene, opening=True)

    # ---------------- the call that writes her words ----------------

    def _system(self, who, cue):
        """ONE assembly for every call that writes her words
        (`persona.system_for`): the friend arm -- the same person she is with
        him, byte for byte, without `style.md`, which is how she writes to HIM
        -- and then this call's own tail: the peer contract and the other half
        of her voice."""
        core = ""
        if self.persona is not None:
            try:
                core = self.persona.system_for("friend", cue_text=cue)
            except Exception as e:
                logger.log(f"[peer] her assembly unavailable, falling back to the sheet: {type(e).__name__}: {e}")
        if not core:
            core = self.config.prompt_text("persona")
        tail = self.config.prompt_text("peer_reply")
        style = self.config.read_text(getattr(self.config.character, "style_ja_prompt", ""))
        return core + "\n\n---\nHOW THIS CALL WORKS:\n" + tail + ("\n\n---\n" + style if style else "")

    def _user(self, who, rec, opening, scene):
        t = lang.say(self.config)
        room = self.thread._room("peer", who["name"])
        head = t(f"You are writing to {who['name']}. She is not him: she is somebody who writes to you on "
                 f"the same messenger, and the two of you are in {room}. She cannot see your chat with him, "
                 f"and he is not in this room.",
                 f"あなたは{who['name']}に書いている。彼ではない。同じメッセンジャーであなたに書いてくる相手で、"
                 f"二人がいるのは{room}。彼とのチャットは相手には見えないし、彼はこの部屋にいない。")
        lines = [head]
        lang_row = who.get("language")
        if lang_row:
            lines.append(t(f"Write to her in {lang_row}.", f"相手には{lang_row}で書く。"))
        if self.ledger is not None:
            try:
                led = self.ledger.text(scene=scene, ja=lang.reads_ja(self.config))
                if led:
                    lines.append(led)
            except Exception as e:
                logger.log(f"[peer] the day's one truth was not read: {type(e).__name__}: {e}")
        # ...and what she has of her own to bring up. Her own conversations
        # get the same pocket her turn in somebody else's room does, so a
        # character whose whole social life is her own circle is not the one
        # left with nothing concrete to say
        pblock, self._pocket_ids = self._pocket_block()
        if pblock:
            lines.append(pblock)
        if opening:
            lines.append(t("Nothing has been said yet. Write what you would actually open with, or an empty "
                           "list if you would not write at all right now.",
                           "まだ何も言われていない。実際に自分から書き出す言葉を書く。いま書かないなら空のリストで。"))
        else:
            lines.append(t("Write your next message(s), or an empty list if you would leave it sitting.",
                           "次に送るメッセージを書く。放っておくなら空のリストで。"))
        lines.append("ANSWER ONLY AS JSON: " + JSON_SHAPE)
        user = "\n\n".join(x for x in lines if x)
        # what she carries rides after the thread, at the head of this call's
        # own user text: one person, the same block in every room, and the
        # system prompt stays a cached prefix (persona/sections.py)
        if self.persona is not None:
            try:
                carried = self.persona.carried_for()
                if carried:
                    user = carried + "\n\n" + user
            except Exception as e:
                logger.log(f"[peer] her carried block unavailable: {type(e).__name__}: {e}")
        return user

    def _write(self, rec, scene, opening=False):
        who = self.contact(rec.get("peer")) or {"id": rec.get("peer"), "name": rec.get("who"), "language": ""}
        turns = rec.get("turns") or []
        cue = " ".join(str(x.get("ja") or "") for x in turns[-3:])
        system = self._system(who, cue)
        user = self._user(who, rec, opening, scene)
        t = lang.say(self.config)
        frame = t("--- the newest message, the one you are answering. Everything above this line is the "
                  "situation, not her words ---",
                  "--- いま届いた最新のメッセージ。返すのはこれ。この線より上は状況の説明で、相手の言葉ではない ---")
        messages = [{"role": "system", "content": system}]
        try:
            hist = self.thread.build(live_turns=turns, live_who=who["name"], live_kind="peer", cue_text=cue)
            messages += place_tail(hist, user, frame)
        except Exception as e:
            logger.log(f"[peer] the thread fell back to the block: {type(e).__name__}: {e}")
            messages.append({"role": "user", "content": user})
        data, _raw = self.llm.call_json("peer_reply", messages)
        if not isinstance(data, dict):
            # a paid answer that did not parse is not stored as data, and she
            # is not asked again this pass
            rec["next_ts"] = self.clock.now_ts() + float(getattr(self.c, "min_gap_seconds", 90) or 90)
            self.store.set("peer_live", rec)
            logger.log("[peer] no answer that parsed; she is left to it")
            return
        out = [str(x).strip() for x in (data.get("messages") or []) if str(x or "").strip()][:2]
        gist = str(data.get("gist") or "").strip()
        if gist:
            rec["gist"] = gist[:220]
        if not out:
            if turns:
                rec["next_ts"] = self.clock.now_ts() + float(getattr(self.c, "min_gap_seconds", 90) or 90)
                self.store.set("peer_live", rec)
            logger.log(f"[peer] she left {who['name']} sitting")
            return
        # nothing is recorded before the action it claims happened: each
        # message is sent and then filed, one at a time
        for i, text in enumerate(out):
            ok = False
            try:
                ok = bool(self.channel.peer_send(who["id"], text))
            except Exception as e:
                logger.log(f"[peer] not sent to {who['name']}: {type(e).__name__}: {e}")
            if not ok:
                break
            ts = self.clock.now_ts() + i * (len(text) / 6.0)
            rec["turns"].append({"who": self._me(), "ja": text, "hm": self.clock.hm(ts), "ts": ts})
            rec["next_ts"] = ts + float(getattr(self.c, "min_gap_seconds", 90) or 90)
            self.store.set("peer_live", rec)
            self.store.bump_today("peer_counts", self.clock.date_str())
            logger.log(f"[peer] her -> {who['name']}: {text[:140]}")
        self._pocket_used(getattr(self, "_pocket_ids", []))

    # ---------------- a room she is in but does not own ----------------
    #
    # The other end of `sim/rooms.py`. One process owns a room -- it plans the
    # day the room happens in, it keeps the record of it, it stamps every turn
    # -- and everybody else in that room is a participant who receives turns
    # and sends turns. A participant runs none of the room's machinery: no
    # beats, no pacing of the room, no deciding who speaks next. She is told
    # what was said and, when it is her turn, asked for words.
    #
    # Which of the two this character is, for a given room, is not a setting:
    # it is which side of the message she is on. A message that says the room
    # is waiting for her is a room somebody else owns; a turn arriving from
    # somebody her own roster says runs herself is a room she owns.

    def _room_message(self, m, env):
        frm = str(m.get("from") or "")
        room = str(env.get("id") or "")
        if env.get("asking"):
            self._room_reply(m, env)
            return
        # Which side of the room this process is on is decided by whether it
        # OWNS the room, and it owns a room when it has a membership for it:
        # kv `rooms`, written by `Rooms.join` and by nothing else, and a
        # participant never joins a room somebody else keeps.
        #
        # The test used to be a roster lookup on the sender. The row of the
        # character who KEEPS a world carries her own hub id in the cast file
        # everybody in that world reads, so in a reader's process the lookup
        # matched every relay from the only process that ever writes to her:
        # each one was filed as "the owner speaking for herself in a room I
        # own", into the owner-side queue that nothing on her side drains,
        # with the envelope's real speaker thrown away. Her record had the
        # world's owner saying two other girls' lines and stopped at 09:22.
        if self.rooms.members(room) or env.get("silent"):
            rec = roster.by_agent(self.config, frm) or {}
            key = rec.get("key") or frm
            who = rec.get("ja") or rec.get("name") or frm
            if env.get("silent"):
                # she was asked and would say nothing. Filed as an empty turn
                # so the room settles at once instead of sitting out its
                # deadline; nothing goes into the record.
                self.rooms.put(key, env, "", who=who)
                logger.log(f"[room] {room}: {key} had nothing to say")
            else:
                self.rooms.put(key, env, str(m.get("text") or ""), who=who)
                logger.log(f"[room] {room}: {key} wrote her own turn; it goes into the record")
            return
        rows = [t for t in (env.get("turns") or []) if str(t.get("ja") or "").strip()]
        if not rows:
            # no turns in the envelope: the sender is the only speaker there is
            rows = [{"who": str(m.get("name") or frm), "ja": str(m.get("text") or ""),
                     "hm": str(env.get("hm") or "")}]
        # A relayed turn is filed under whoever SAID it. The envelope carries
        # the speaker on every turn in it (`sim/rooms.py post_turn`), and the
        # message's `name` is the display name of the process that sent it --
        # always the room's owner for a turn she is only passing on.
        self._room_file(env, m, rows)

    def _rooms_seen(self):
        rec = self.store.get("peer_rooms", {}) or {}
        return rec if isinstance(rec, dict) else {}

    def _rooms_today(self):
        """What she has said today in rooms somebody else owns. Its own
        counter: the peer conversation's day budget is for conversations she
        has of her own, and a room is not one of those."""
        return int((self.store.get("room_counts", {}) or {}).get(self.clock.date_str(), 0) or 0)

    def _pocket_block(self):
        """(the lines, the ids): things of her OWN she could bring up today.

        Built once a day from her own material and never from anybody else's
        roster (`sim/pocket.py`): in a world she does not keep, the people
        are not hers and inventing for them is the fault the partition
        exists to stop. The ids come back so the caller can mark them once
        the call has actually written something.

        Nothing here is switched on per character: a resident with a circle
        of her own gets a pocket the same way a member of somebody else's
        group chat does."""
        try:
            p = pocket_mod.Pocket(self.config, self.store, self.clock)
            date = self.clock.date_str()
            me = self._me()
            n = int(getattr(getattr(self.config, "cast", None), "pocket_items", 4) or 4)
            if not p.row(date, me):
                items = pocket_mod.own_items(self.store, lang.say(self.config), limit=n)
                if items and p.put(date, me, items):
                    logger.log(f"[pocket] {len(items)} thing(s) of her own to bring up today")
            return p.block(date, me, limit=n, ja=lang.reads_ja(self.config))
        except Exception as e:
            logger.log(f"[pocket] hers was not built: {type(e).__name__}: {e}")
            return "", []

    def _pocket_used(self, ids):
        """Marked after the call came back with words, never before it."""
        if not ids:
            return
        try:
            pocket_mod.Pocket(self.config, self.store, self.clock).mark(
                self.clock.date_str(), self._me(), ids)
        except Exception as e:
            logger.log(f"[pocket] hers was not marked: {type(e).__name__}: {e}")

    def _room_silent(self, frm, env, why):
        """The room asked and she is saying nothing. Handed back at once,
        with the reason in her own log, so the room settles rather than
        waiting out its deadline for an answer that has already been given
        (`sim/rooms.SILENT`). A gate of hers and a decision of hers are the
        same answer to the room: it goes on without her either way, and the
        one thing it must not do is sit."""
        room = str(env.get("id") or "")
        back = dict(env, asking=False, turns=[], present=list(env.get("present") or []), silent=True)
        sent = False
        try:
            sent = bool(self.channel.peer_send(frm, rooms_mod.SILENT, room=back))
        except Exception as e:
            logger.log(f"[room] her silence did not reach {room}: {type(e).__name__}: {e}")
        logger.log(f"[room] {why} in {room}"
                   + ("; the room was told" if sent else "; the room was not told and will wait"))

    def _room_file(self, env, m, turns):
        """What she has been told of a room she is in. Only this: the words,
        who said them, when, and on which day. No plan, no record of
        anybody's, no graph -- she learns a room the way she learns him, by
        what arrives.

        Every row carries its own day and, where the envelope had one, the
        real instant. The record itself spans as many days as its last
        `room_keep` turns do, so a row that took the record's day would have
        its clock re-read every time the record rolled over -- and three
        readers now render a stamp from it (her next turn, her phone, her
        thread), where a stamp is written once and never rewritten
        (docs/context.md)."""
        room = str(env.get("id") or "")
        if not room:
            return {}
        all_rooms = self._rooms_seen()
        rec = dict(all_rooms.get(room) or {"kind": env.get("kind") or "line", "turns": [],
                                           "owner": str(m.get("from") or ""),
                                           "owner_name": str(m.get("name") or "")})
        rows = list(rec.get("turns") or [])
        day = str(env.get("date") or rec.get("date") or "")
        # One turn is one row, whichever door it came through. The same turn
        # arrives twice -- inside the ask that wants her words, where it
        # carries no clock yet, and as the relay of that turn a moment later,
        # where it does -- so what makes two rows the same is who said it, the
        # words and the day, never the clock, which is the one thing that
        # differs between the two arrivals.
        at = {}
        for i, t in enumerate(rows):
            at[(str(t.get("date") or rec.get("date") or ""), str(t.get("who") or ""),
                str(t.get("ja") or ""))] = i
        for t in turns:
            ja = str(t.get("ja") or "")
            if not ja.strip():
                continue
            key = (str(t.get("date") or day), str(t.get("who") or ""), ja)
            ix = at.get(key)
            if ix is not None:
                # already filed: the only thing a second arrival may add is
                # the clock the first one did not carry
                row = rows[ix]
                if not str(row.get("hm") or "") and str(t.get("hm") or ""):
                    row["hm"] = str(t.get("hm"))
                if not float(row.get("ts") or 0) and float(t.get("ts") or 0):
                    row["ts"] = float(t.get("ts"))
                continue
            rows.append({"who": key[1], "ja": ja, "hm": str(t.get("hm") or ""),
                         "ts": float(t.get("ts") or 0), "date": key[0]})
            at[key] = len(rows) - 1
        rec["turns"] = rows[-int(getattr(self.c, "room_keep", 60) or 60):]
        rec["date"] = day
        rec["present"] = list(env.get("present") or rec.get("present") or [])
        all_rooms[room] = rec
        self.store.set("peer_rooms", all_rooms)
        return rec

    def _room_reply(self, m, env):
        """The room is waiting for her words. Her own persona writes them --
        the same assembly as every other call that writes her words, the
        friend arm -- and they go back to whoever asked, as one more turn in
        that room."""
        room = str(env.get("id") or "")
        frm = str(m.get("from") or "")
        rec = self._room_file(env, m, list(env.get("turns") or []))
        scene = getattr(self, "_scene", None)
        if self._phone_away(scene) and str(env.get("kind") or "") != "in_person":
            self._room_silent(frm, env, "her phone is away")
            return
        if self._rooms_today() >= int(getattr(self.c, "room_max_per_day", 60) or 60):
            self._room_silent(frm, env, "she has said her piece in the rooms for today")
            return
        turns = list(rec.get("turns") or [])
        cue = " ".join(str(t.get("ja") or "") for t in turns[-3:])
        who = {"id": frm, "name": str(m.get("name") or frm), "language": ""}
        system = self._system(who, cue)
        user = self._room_user(env, rec, m)
        t = lang.say(self.config)
        frame = t("--- the newest thing said in the room. Everything above this line is the situation, "
                  "not anybody's words ---",
                  "--- 部屋でいま言われた最新の言葉。この線より上は状況の説明で、誰かの発言ではない ---")
        messages = [{"role": "system", "content": system}]
        try:
            # the room's own record is in her thread now (`Thread._records`),
            # so the copy she is handed here is named: one room, once
            hist = self.thread.build(live_turns=turns, live_who=who["name"],
                                     live_kind=str(env.get("kind") or "peer"), cue_text=cue,
                                     live_room=room)
            messages += place_tail(hist, user, frame)
        except Exception as e:
            logger.log(f"[room] the thread fell back to the block: {type(e).__name__}: {e}")
            messages.append({"role": "user", "content": user})
        data, _raw = self.llm.call_json("peer_reply", messages)
        if not isinstance(data, dict):
            logger.log(f"[room] no answer that parsed for {room}; the room goes on without her")
            return
        out = [str(x).strip() for x in (data.get("messages") or []) if str(x or "").strip()][:2]
        wrote = len(out)
        # A message that says again what has already been said in this room --
        # by anybody, her included -- does not go. Her side had no repeat test
        # of any kind: the owner's writer at least refused a speaker her own
        # near-duplicate, and this path refused nothing, which is how the same
        # three sentences went into the group chat at 21:33, 21:44 and 21:50.
        # Flagged and dropped, never rewritten and never asked again.
        c_ex = getattr(self.config, "exchange", None)
        window = int(getattr(c_ex, "repeat_window_turns", 20) or 20)
        prior = [(str(x.get("who") or ""), str(x.get("ja") or "")) for x in turns[-window:]]
        out = drop_echoes(out, prior, who_of=lambda _t: self._me(),
                          min_chars=int(getattr(c_ex, "repeat_min_chars", 12) or 12),
                          why="of hers in a room")
        if not out:
            self._room_silent(frm, env, "everything she wrote had already been said in the room"
                              if wrote else "she had nothing to say")
            return
        # nothing is recorded before the action it claims happened: each turn
        # is put on the hub and then filed
        back = dict(env, asking=False, turns=[], present=list(env.get("present") or []),
                    silent=False,
                    # one line of what her turn came to, which becomes the
                    # room's next entry in the moves ledger (`sim/rooms.py`)
                    gist=str(data.get("gist") or "")[:200])
        for text in out:
            ok = False
            try:
                ok = bool(self.channel.peer_send(frm, text, room=back))
            except Exception as e:
                logger.log(f"[room] her turn did not reach {room}: {type(e).__name__}: {e}")
            if not ok:
                break
            now = self.clock.now_ts()
            self._room_file(env, m, [{"who": self._me(), "ja": text, "hm": self.clock.hm(now),
                                      "ts": now, "date": self.clock.date_str(now)}])
            # a room turn spends the ROOM's day budget and not the peer
            # conversation's: a room she is in belongs to somebody else's
            # process, `peer_talk` is switched off for a character who has no
            # peers of her own, and twelve turns in the group chat used to put
            # her out of a section she does not run
            self.store.bump_today("room_counts", self.clock.date_str())
            logger.log(f"[room] her -> {room}: {text[:140]}")
        # her side of the room is written: one line of what it came to,
        # under everybody who was in it, so her next room today sees it
        try:
            for p in (env.get("present") or []):
                if str(p) != self._me():
                    self.said_today.note(p, data.get("gist") or "",
                                         room=str(env.get("kind") or "line"))
        except Exception as e:
            logger.log(f"[said] her own turn was not noted: {type(e).__name__}: {e}")
        # what she was offered to bring up was put in front of a call that
        # came back with words, so it is spent whether or not she used it:
        # offering it again tomorrow is how a pocket becomes a script
        self._pocket_used(getattr(self, "_pocket_ids", []))

    def _room_user(self, env, rec, m):
        """What she is told about the room: where she is, who is in it with
        her, what has been said, and what is being waited for. Her own carried
        block rides after the thread, as it does in every other room."""
        t = lang.say(self.config)
        kind = str(env.get("kind") or "line")
        label = self.thread._room(kind, str(m.get("name") or "")) if self.thread is not None else kind
        present = ", ".join(str(p) for p in (env.get("present") or []))
        lines = [t(f"You are in {label}. What follows is what has been said in it, and it is your turn.",
                   f"あなたは{label}にいる。以下はそこで言われたこと。いまはあなたの番。")]
        if present:
            lines.append(t(f"In the room: {present}.", f"部屋にいるのは: {present}。"))
        if env.get("cue"):
            lines.append(t(f"What you are reaching them about now: {env['cue']}",
                           f"いま相手に切り出そうとしていること: {env['cue']}"))
        if self.ledger is not None:
            try:
                led = self.ledger.text(scene=getattr(self, "_scene", None), ja=lang.reads_ja(self.config))
                if led:
                    lines.append(led)
            except Exception as e:
                logger.log(f"[room] the day's one truth was not read: {type(e).__name__}: {e}")
        # What she happens to know, when the room's words came near it. This
        # room is somebody else's and she is only sent its turns, so there is
        # no gate here and no competition for room: the lines go in as they
        # come back, under the same header her other rooms use
        # (sim/lore_rooms.py). What she is reaching them about is the context.
        me = self._me()
        lore = lore_rooms.lines(self.persona, self.config, rec.get("turns"), lambda w: w == me,
                                context_text=str(env.get("cue") or ""))
        if lore:
            lines.append("\n".join([lore_rooms.preamble(self.config)] + [str(l) for l in lore]))
        # what she has of her own to bring up, and what the room has already
        # been through. The ids are marked once the call comes back with words
        pblock, self._pocket_ids = self._pocket_block()
        if pblock:
            lines.append(pblock)
        mv = moves_block(env.get("moves"), self.config,
                         limit=int(getattr(getattr(self.config, "exchange", None),
                                           "moves_shown", 8) or 8))
        if mv:
            lines.append(mv)
        # what SHE has already said to the people in this room today, out of
        # her own save, and what the character whose room this is has
        # already said to her, out of the envelope. The moves ledger is
        # this room's memory; these two are the day's, across rooms
        # (`sim/said_today.py`).
        try:
            for p in (env.get("present") or []):
                if str(p) == self._me():
                    continue
                own = self.said_today.block(p)
                if own:
                    lines.append(own)
        except Exception as e:
            logger.log(f"[said] her own list was not read: {type(e).__name__}: {e}")
        theirs = SaidToday.block_from(env.get("said_today"), self.config,
                                      who=str(m.get("name") or m.get("from") or ""))
        if theirs:
            lines.append(t("...and what she has already been over with you today, in her other "
                           "conversations -- it is not news: ",
                           "...そして今日、別の会話で相手がすでにあなたに言ってあること。新しい話ではない: ")
                         + theirs)
        lines.append(t("Write your next message(s), or an empty list if you would say nothing.",
                       "次に送るメッセージを書く。何も言わないなら空のリストで。"))
        lines.append("ANSWER ONLY AS JSON: " + JSON_SHAPE)
        user = "\n\n".join(x for x in lines if x)
        if self.persona is not None:
            try:
                carried = self.persona.carried_for()
                if carried:
                    user = carried + "\n\n" + user
            except Exception as e:
                logger.log(f"[room] her carried block unavailable: {type(e).__name__}: {e}")
        return user

    # ---------------- the close ----------------

    def _finish(self, rec, why):
        rows = list(self.store.get("peer_chat", []) or [])
        out = dict(rec)
        out.pop("next_ts", None)
        turns = out.get("turns") or []
        out["ended_hm"] = (turns[-1].get("hm") if turns else out.get("hm")) or ""
        out["why"] = why
        keep = int(getattr(self.c, "keep", 60) or 60)
        self.store.set("peer_chat", (rows + [out])[-keep:])
        self.store.set("peer_live", None)
        mine = len(self._mine(out))
        now = self.clock.now_ts()
        self.store.add_event(now, self.clock.date_str(now), "peer_chat",
                             f"with {out.get('who')}: {out.get('gist') or why}", 2)
        # the company a conversation is, mechanically, whether or not the model
        # remembers it: the same call the cast close makes, and `sim/state.py`
        # stays the one owner of the gauge
        if mine and self.state is not None:
            try:
                self.state.talk_relief(out.get("who") or "", mine)
            except Exception as e:
                logger.log(f"[peer] the company was not counted: {type(e).__name__}: {e}")
        logger.log(f"[peer] closed with {out.get('who')} after {len(turns)} message(s), {mine} of hers: {why}")

    def flush(self):
        """The day is being told: a conversation still open is part of it."""
        rec = self.live()
        if rec:
            self._finish(rec, "the day ended on it")

    # ---------------- the operator's view ----------------

    def _rooms_report(self):
        """The rooms she is in that somebody else owns, and the ones this
        process owns with somebody in them who writes her own turns."""
        out = []
        seen = self._rooms_seen()
        for room in sorted(seen):
            rec = seen[room] or {}
            out.append("  in %s (%s owns it): %d turn(s) she has been sent"
                       % (room, rec.get("owner_name") or rec.get("owner") or "?",
                          len(rec.get("turns") or [])))
        own = self.rooms.report()
        if not own.startswith("rooms: none"):
            out.append(own)
        return "\n".join(out)

    def _pocket_report(self):
        try:
            return pocket_mod.Pocket(self.config, self.store, self.clock).report()
        except Exception as e:
            return "pockets: not read (%s)" % type(e).__name__

    def report(self):
        rooms = self._rooms_report()
        # what she had to bring up and never did, the way /sweep names a
        # feeling nothing reads
        pk = self._pocket_report()
        if pk and not pk.startswith("pockets: nothing"):
            rooms = (rooms + "\n" if rooms else "") + pk
        if not getattr(self.c, "enabled", False):
            return ("peer talk: off" + ("\n" + rooms if rooms else ""))
        rows = self.contacts()
        if not rows:
            return ("peer talk: on, and she has nobody on her list"
                    + ("\n" + rooms if rooms else ""))
        out = ["peer talk: " + ", ".join(f"{r['name']} ({r['id']}{', ' + r['language'] if r['language'] else ''})"
                                         for r in rows),
               "  sent today %d of %d, quiet for %.0f min, cursor %s"
               % (self._sent_today(), int(getattr(self.c, "max_per_day", 12) or 12),
                  min(self._quiet_for(), 99999), self.store.get("peer_last_id", 0) or 0)]
        rec = self.live()
        if rec:
            out.append("  live with %s: %d message(s), %d of hers, opened %s"
                       % (rec.get("who"), len(rec.get("turns") or []), len(self._mine(rec)), rec.get("hm")))
            for t in (rec.get("turns") or [])[-4:]:
                out.append(f"    [{t.get('hm')}] {t.get('who')}: {str(t.get('ja') or '')[:90]}")
        else:
            out.append("  nothing live")
        for x in list(self.store.get("peer_chat", []) or [])[-3:]:
            out.append("  %s %s with %s: %d message(s) -- %s"
                       % (x.get("date"), x.get("hm"), x.get("who"), len(x.get("turns") or []),
                          x.get("gist") or x.get("why") or ""))
        if rooms:
            out.append(rooms)
        return "\n".join(out)
