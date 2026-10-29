# -*- coding: utf-8 -*-
"""What she has already said to whom today, across conversations.

The room already remembers what it has tried: a per-conversation list of the
moves made in it (`sim/rooms.py moves_block`). That list dies with the room,
which is exactly the wrong shape for the fault it was aimed at. On 2026-09-08
one character told the same friend that Thursday at ten at the ticket gate was
settled seven times, in six DIFFERENT rooms, and the per-room list saw at most
one of them at a time. Another sent the same photograph six times over an
evening across four rooms. Both of them then read the filter's deletion of the
words as the conversation having gone nowhere, and opened another one.

This is the memory that crosses rooms: one line per conversation she finished,
under the name of the person she finished it with, thrown away at midnight. It
costs no model call -- the summary each writing call already returns is the
line -- and it has three readers:

  * the call that writes her turn, so she can see she has already been to this
    person with this today;
  * the moment she is asked what she does with the phone (`sim/pick.py`), so
    "message her again" is a choice made against what she has already said;
  * the process of a member who writes her own turns, handed the same list in
    the envelope beside the moves ledger, so both writers see one record.

It also holds the one gate code keeps here: a person she went to and had
nothing to say to leaves the list of people she may write to for a while
(`exchange.reopen_after_nothing_minutes`). Code decides when she is asked and
what she is allowed to do; she decides what she does.

Every piece of its state is in the save, so two instances in one process are
one thing seen twice -- the same property `sim/rooms.py` has, and the reason
Peers builds its own rather than being handed one.

Nobody is named here.
"""
import logger
from sim import lang, roster

# how many lines are kept for one person in one day. A person she has been to
# twelve times today is a person the gate below has already taken off the
# list, and a prompt about repetition is not the answer to repetition.
PER_PERSON = 12
# ...and how many of them the prompt is shown
SHOWN = 6


class SaidToday:
    def __init__(self, config, store, clock):
        self.config = config
        self.store = store
        self.clock = clock

    # ---------------- the row ----------------

    def _row(self):
        """Today's row, empty on the first read of a new date. Reset on the
        first WRITE rather than here, so a reader on a new day sees nothing
        and never blanks a row the writer has not replaced yet."""
        rec = self.store.get("said_today", {}) or {}
        if not isinstance(rec, dict) or rec.get("date") != self.clock.date_str():
            return {"date": self.clock.date_str(), "people": {}, "cooled": {}}
        rec.setdefault("people", {})
        rec.setdefault("cooled", {})
        return rec

    def _save(self, rec):
        rec["date"] = self.clock.date_str()
        self.store.set("said_today", rec)

    def _name(self, who):
        return roster.record_name(self.config, who)

    def _find(self, rec, who):
        """The key this person's lines are under, whatever form the caller
        used. The pick is handed a name the model wrote and a room is handed
        the record's own; both have to land on one entry."""
        name = self._name(who)
        if name in rec["people"]:
            return name
        for k in rec["people"]:
            if roster.same(self.config, k, name):
                return k
        return name

    # ---------------- writing ----------------

    def note(self, who, gist, room="line"):
        """One line of what a conversation with this person came to.

        Written where the conversation is FINISHED, from the record's own
        summary -- which is a summary of turns that survived the filter and
        of nothing else."""
        gist = " ".join(str(gist or "").split())[:200]
        if not gist or not str(who or "").strip():
            return False
        rec = self._row()
        key = self._find(rec, who)
        rows = list(rec["people"].get(key) or [])
        rows.append({"hm": self.clock.hm(), "gist": gist, "room": str(room or "line")})
        rec["people"][key] = rows[-PER_PERSON:]
        self._save(rec)
        return True

    def note_room(self, out, me_key="self"):
        """A finished room: one line under everybody she spoke to in it.

        The counterparty of a private room, every other speaker of a group
        one -- because a thing said into the group has been said to each of
        them, which is the whole reason the same arrangement could go round
        six rooms without either writer seeing it twice."""
        if not isinstance(out, dict):
            return 0
        gist = out.get("gist") or ""
        if not gist:
            return 0
        turns = out.get("turns") or []
        # nothing of hers in the room is nothing she said in it
        if not any(roster.is_self(self.config, t.get("who")) for t in turns):
            return 0
        kind = str(out.get("kind") or "line")
        if kind == "group":
            names, seen = [], set()
            for t in turns:
                w = str(t.get("who") or "")
                if not w or roster.is_self(self.config, w):
                    continue
                n = self._name(w)
                if n not in seen:
                    seen.add(n)
                    names.append(n)
        else:
            names = [self._name(out.get("who") or "")]
        n = 0
        for name in names:
            if name and self.note(name, gist, room=kind):
                n += 1
        return n

    # ---------------- reading ----------------

    def for_person(self, who, limit=SHOWN):
        rec = self._row()
        return list(rec["people"].get(self._find(rec, who)) or [])[-int(limit or SHOWN):]

    def people(self):
        """[(name, rows)] for everybody she has been to today."""
        rec = self._row()
        return [(k, list(v or [])) for k, v in rec["people"].items() if v]

    def block(self, who, limit=SHOWN):
        """What she has already said to this person today, for the call that
        writes her turn. The same shape as the promise line beside it."""
        rows = self.for_person(who, limit)
        if not rows:
            return ""
        t = lang.say(self.config)
        head = t(f"WHAT SHE HAS ALREADY SAID TO {self._name(who)} TODAY, in other conversations "
                 f"(she does not say it again unless something has changed): ",
                 f"今日すでに{self._name(who)}に言ってあること（別の会話で。何か変わっていない限り、"
                 f"同じことは言わない）: ")
        return head + "; ".join(f"{r.get('hm', '')} {r.get('gist', '')}" for r in rows)

    def lines_for_pick(self, limit=3):
        """One line per person she has been to today, for the moment she is
        asked what she does with the phone."""
        t = lang.say(self.config)
        out = []
        for name, rows in self.people():
            if not rows:
                continue
            gists = "; ".join(str(r.get("gist") or "") for r in rows[-int(limit or 3):])
            out.append(t(f"what you already went to {name} with today: {gists}",
                         f"今日すでに{name}に言ったこと: {gists}"))
        return out

    def envelope_rows(self, who, limit=SHOWN):
        """The same list, as data, for a member who writes her own turns in
        her own process (`sim/rooms.py`: it rides in the envelope beside the
        moves ledger)."""
        return [dict(r) for r in self.for_person(who, limit)]

    @staticmethod
    def block_from(rows, config, who=""):
        """The block rendered from rows that came in an envelope, so the two
        writers read one wording."""
        rows = [r for r in (rows or []) if isinstance(r, dict) and str(r.get("gist") or "").strip()]
        if not rows:
            return ""
        t = lang.say(config)
        head = t(f"WHAT YOU HAVE ALREADY SAID TO {who} TODAY, in other conversations (you do not say "
                 f"it again unless something has changed): ",
                 f"今日すでに{who}に言ってあること（別の会話で。何か変わっていない限り、同じことは"
                 f"言わない）: ")
        return head + "; ".join(f"{r.get('hm', '')} {r.get('gist', '')}" for r in rows)

    # ---------------- the gate ----------------

    def cool(self, who, minutes=0, why=""):
        """She went to this person and had nothing to say. Take her off the
        list of people the chooser may write to for a while.

        Said once, when it is set. The model chooses inside the gates code
        keeps, and a person she has just opened a chat with and closed again
        is not a choice her world can honour twice in ten minutes."""
        minutes = float(minutes or getattr(self.config.exchange, "reopen_after_nothing_minutes", 0) or 0)
        if minutes <= 0:
            return 0.0
        rec = self._row()
        key = self._find(rec, who)
        until = self.clock.now_ts() + minutes * 60.0
        if float((rec["cooled"] or {}).get(key) or 0) >= until:
            return float(rec["cooled"][key])
        rec["cooled"][key] = until
        self._save(rec)
        logger.log(f"[pick] {key} is off the list until {self.clock.hm(until)}: she had nothing new "
                   f"for her at {self.clock.hm()}" + (f" ({why})" if why else ""))
        return until

    def cooled_until(self, who):
        """When this person comes back onto the list, or 0."""
        rec = self._row()
        until = float((rec["cooled"] or {}).get(self._find(rec, who)) or 0)
        return until if until > self.clock.now_ts() else 0.0

    def cool_line(self, who):
        """The one sentence the chooser is shown about it, or ""."""
        until = self.cooled_until(who)
        if not until:
            return ""
        rows = self.for_person(who, 1)
        hm = rows[-1].get("hm", "") if rows else ""
        t = lang.say(self.config)
        name = self._name(who)
        return t(f"you went to {name} at {hm} and had nothing new for her; not again before "
                 f"{self.clock.hm(until)}",
                 f"{hm}に{name}のところへ行って、新しく言うことがなかった。{self.clock.hm(until)}までは"
                 f"また行かない")

    def cool_lines(self):
        rec = self._row()
        out = []
        for name in list(rec["cooled"] or {}):
            line = self.cool_line(name)
            if line:
                out.append(line)
        return out

    def report(self):
        rec = self._row()
        out = [f"said today ({rec.get('date')}): {len(rec.get('people') or {})} person(s)"]
        for name, rows in (rec.get("people") or {}).items():
            out.append(f"  {name}: " + " | ".join(f"[{r.get('hm')}] {str(r.get('gist'))[:70]}" for r in rows))
        for name, until in (rec.get("cooled") or {}).items():
            left = (float(until) - self.clock.now_ts()) / 60.0
            out.append(f"  off the list: {name} for another {left:.0f} min" if left > 0
                       else f"  off the list: {name} (expired)")
        return "\n".join(out)
