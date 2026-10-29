"""Episode cards: her past, one card per episode, written once and kept.

The thread holds the last day or two verbatim and used to hold a day past
that as one recap line and an exchange as one gist line, then nothing after
a week; the compile's narrative sat in the save where no reply could reach
it. A person keeps a conversation as its shape and two or three exact
lines. That is a card.

**Code decides the episodes.** His chat splits into episodes at silences of
`delivery.gap_marker_hours`; each exchange with her own people is one
(already a unit in `cast_chat`). **A model writes the card** (role
`episode_cards`, one call per day at the compile): `shape`, three to six
lines of what happened, in her language; `anchors`, one to three lines
quoted from the record with who said them; `felt`, one line. **Code checks
the anchors**: a quote that is not a substring of the episode's own text
(whitespace aside) is dropped and logged, so the only exact words her past
keeps are words that were said. Cards are never faded and never rewritten;
recompiling a day replaces its cards.

Two readers: the thread (`sim/thread.py`) renders the cards of the days
past its verbatim window at their own time, in place of the recap lines;
recall (`sim/recall.py`) searches them by words and, with `sim/embed.py`,
by meaning, so an evening from a month ago can come back on a cue.
"""
import json
import re

import logger
from sim import wiring
from sim.textutil import words as tokens

_MIN_LATIN = 4


def _norm(s):
    return re.sub(r"[\s　「」『』\"'“”‘’、。,.!?！？…・\-–—]+", "", str(s or "")).lower()


class Cards:
    WIRES = ("embed",)

    def __init__(self, config, llm, store, clock):
        self.config = config
        self.llm = llm
        self.store = store
        self.clock = clock
        self._ensure()
        wiring.declare(self)

    def _ensure(self):
        with self.store.lock:
            self.store.conn.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    id INTEGER PRIMARY KEY, date TEXT, start_ts REAL, end_ts REAL,
                    room TEXT, who TEXT, shape TEXT, anchors TEXT, felt TEXT,
                    n_lines INTEGER, created_ts REAL)""")
            self.store.conn.execute("CREATE INDEX IF NOT EXISTS episodes_date ON episodes(date)")
            self.store.conn.commit()

    # ---------------- the episodes of a day, by code ----------------

    def _turn_ts(self, ex, turn, start_ts):
        import datetime
        hm = str(turn.get("hm") or ex.get("hm") or "00:00")
        try:
            h, m = hm.split(":")
            d = datetime.datetime.strptime(str(ex.get("date")), "%Y-%m-%d").replace(
                hour=int(h), minute=int(m), tzinfo=self.clock.char_tz)
        except (ValueError, TypeError):
            return start_ts
        ts = d.timestamp()
        if start_ts and ts < start_ts - 6 * 3600:
            ts += 86400
        return ts

    def segment(self, date_str):
        """[{room, who, kind, start_ts, end_ts, lines: [(ts, speaker, text)]}] for
        the day: his chat cut at silences, each exchange with her people whole."""
        gap = float(self.config.delivery.gap_marker_hours) * 3600
        segs = []
        cur = None
        for m in self.store.messages_for_date(date_str):
            text = str(m.get("text") or "").strip()
            if not text:
                continue
            ts = float(m["ts"])
            speaker = "him" if m.get("role") == "user" else "you"
            if cur is None or ts - cur["end_ts"] >= gap:
                cur = {"room": "chat with him", "who": "him", "kind": "him", "start_ts": ts, "end_ts": ts, "lines": []}
                segs.append(cur)
            cur["lines"].append((ts, speaker, text))
            cur["end_ts"] = ts
        for ex in self.store.get("cast_chat", []) or []:
            if ex.get("date") != date_str or not ex.get("turns"):
                continue
            start = float(ex.get("started_ts") or 0) or self._turn_ts(ex, ex["turns"][0], 0)
            lines = []
            for t in ex["turns"]:
                text = str(t.get("ja") or t.get("text") or "").strip()
                if text:
                    lines.append((self._turn_ts(ex, t, start), str(t.get("who") or ""), text))
            if not lines:
                continue
            segs.append({"room": self._room(ex.get("kind", ""), ex.get("who", "")), "who": str(ex.get("who") or ""),
                         "kind": str(ex.get("kind") or ""), "start_ts": start, "end_ts": lines[-1][0], "lines": lines})
        segs.sort(key=lambda s: s["start_ts"])
        return self._coarsen(segs)

    def _coarsen(self, segs):
        """Fewer, fuller episodes. Two exchanges in the same room within
        `episodes.merge_gap_minutes` are one conversation with a pause in it;
        what is left under `episodes.min_lines` (a sticker, a photo, one
        line nobody answered) is gathered into one odds-and-ends episode for
        the day, each line labelled with its room. The first run wrote 20
        to 27 cards a day, most of them a single message, and the thread
        grew past what the verbatim days had cost."""
        c = self.config.episodes
        gap = float(c.merge_gap_minutes) * 60
        merged = []
        for s in segs:
            last = merged[-1] if merged else None
            if last and last["room"] == s["room"] and s["start_ts"] - last["end_ts"] <= gap:
                last["lines"].extend(s["lines"])
                last["end_ts"] = max(last["end_ts"], s["end_ts"])
            else:
                merged.append(dict(s, lines=list(s["lines"])))
        full = [s for s in merged if len(s["lines"]) >= int(c.min_lines)]
        small = [s for s in merged if len(s["lines"]) < int(c.min_lines)]
        if small:
            lines = []
            for s in small:
                for ts, who, text in s["lines"]:
                    lines.append((ts, f"{who} ({s['room']})", text))
            lines.sort(key=lambda x: x[0])
            full.append({"room": "odds and ends", "who": "", "kind": "odds", "start_ts": lines[0][0],
                         "end_ts": lines[-1][0], "lines": lines})
        full.sort(key=lambda s: s["start_ts"])
        return full

    def _room(self, kind, who):
        from sim import roster
        name = roster.record_name(self.config, who) or who
        return {"line": f"LINE with {name}", "group": "group chat", "in_person": f"in person, {name}",
                "call": f"call with {name}", "video": f"video call with {name}"}.get(kind, f"{kind} with {name}")

    # ---------------- writing the cards, one call a day ----------------

    def write(self, date_str):
        """The day's cards, written once; a day written again is replaced.
        Returns the number of cards kept."""
        c = self.config.episodes
        if not c.enabled:
            return 0
        segs = self.segment(date_str)
        if not segs:
            return 0
        # The language she writes in, which is `character.writes_to_him` --
        # the same question `SelfMemory` asks. It was `sim.lang.reads_ja`,
        # which answers a different one: which INSTRUCTION ARM is selected,
        # and both characters run the control arm. So every card of the
        # character who writes Japanese came back with its shape and its
        # feeling in English -- her own remembered past, handed back to her in
        # a language she does not write (`docs/yukarin.md` §20).
        writes_ja = str(getattr(self.config.character, "writes_to_him", "english")).lower().startswith("ja")
        lang = "Japanese" if writes_ja else "English"
        parts = []
        for i, s in enumerate(segs, 1):
            head = f"EPISODE {i}: {s['room']}, {self.clock.hm(s['start_ts'])}-{self.clock.hm(s['end_ts'])}, {len(s['lines'])} lines"
            body = "\n".join(f"[{self.clock.hm(ts)}] {who}: {text}" for ts, who, text in s["lines"][: int(c.max_lines_per_episode)])
            parts.append(head + "\n" + body)
        user = (f"DATE: {date_str}\nWRITE `shape` IN {lang.upper()}. Anchors are copied exactly as said, in the language they were said in.\n\n"
                + "\n\n".join(parts))
        messages = [{"role": "system", "content": self.config.prompt_text("episode_cards")}, {"role": "user", "content": user}]
        data, raw = self.llm.call_json("episode_cards", messages)
        cards = (data or {}).get("cards") if isinstance(data, dict) else None
        if not isinstance(cards, list):
            logger.log(f"[episodes] {date_str}: no usable answer ({len(raw or '')} chars raw); cards not written")
            return 0
        kept, dropped_anchors, rows = 0, 0, []
        by_n = {}
        for card in cards:
            if isinstance(card, dict):
                try:
                    by_n[int(card.get("n"))] = card
                except (TypeError, ValueError):
                    pass
        now = self.clock.now_ts()
        for i, s in enumerate(segs, 1):
            card = by_n.get(i)
            if not card:
                continue
            shape = str(card.get("shape") or "").strip()
            if not shape:
                continue
            text_norm = _norm(" ".join(t for _, _, t in s["lines"]))
            anchors = []
            for a in (card.get("anchors") or [])[: int(c.anchors_max) * 2]:
                if isinstance(a, dict):
                    who, q = str(a.get("who") or ""), str(a.get("text") or "").strip()
                else:
                    who, q = "", str(a).strip()
                if q and len(_norm(q)) >= 4 and _norm(q) in text_norm:
                    anchors.append({"who": who[:40], "text": q[:200]})
                elif q:
                    dropped_anchors += 1
            anchors = anchors[: int(c.anchors_max)]
            rows.append((date_str, s["start_ts"], s["end_ts"], s["room"], s["who"], shape[:1200],
                         json.dumps(anchors, ensure_ascii=False), "",
                         len(s["lines"]), now))
            kept += 1
        with self.store.lock:
            old = [r[0] for r in self.store.conn.execute("SELECT id FROM episodes WHERE date=?", (date_str,)).fetchall()]
            self.store.conn.execute("DELETE FROM episodes WHERE date=?", (date_str,))
            self.store.conn.executemany(
                "INSERT INTO episodes(date,start_ts,end_ts,room,who,shape,anchors,felt,n_lines,created_ts) VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
            self.store.conn.commit()
        if self.embed is not None and old:
            self.embed.forget("episode", old)
        # the rows of that day that came out of one of these conversations now
        # say which one (`link_day`); the links to the cards just replaced go
        # with them
        self._unlink_cards(old)
        try:
            self.link_day(date_str)
        except Exception as e:
            logger.log(f"[episodes] {date_str}: the rows of that day were not linked to their cards: {type(e).__name__}: {e}")
        logger.log(f"[episodes] {date_str}: {kept} card(s) from {len(segs)} episode(s), "
                   f"{sum(len(json.loads(r[6])) for r in rows)} anchor(s) kept, {dropped_anchors} dropped as not said")
        if self.embed is not None and rows:
            try:
                self.embed.vectors("episode", [(r["id"], self.text_of(r)) for r in self.for_date(date_str)])
            except Exception as e:
                logger.log(f"[episodes] not embedded: {type(e).__name__}: {e}")
        return kept

    # ---------------- what a card fed ----------------

    # A row that can be placed inside one conversation is a row that was
    # written at the moment it happened, so its own timestamp is the time the
    # thing happened. A row the nightly compile wrote is about a whole day and
    # its timestamp is the hour the day was told, hours after everything in
    # it; it belongs to no single conversation and keeps its writer and its
    # date instead of being pinned to whichever card happened to be running.
    # A row whose writer left no name is in the same position: unknown, not
    # the compile.
    TOLD_LATER = ("compile", "day", "seed", "")
    # Which room a writer's name says she was in. A row is placed only when
    # its writer is one of these: the rest -- a promise settled, a goal given
    # up, a spiral ending -- are conclusions drawn later about a stretch of
    # the day and belong to no one conversation either.
    HIS_ROOM = ("message", "scenery")
    THEIR_ROOM = ("exchange", "bond")
    LINEAGE = (("self_memories", "text", "she still carries"),
               ("user_facts", "fact", "she knows about him"),
               ("cast_facts", "fact", "she knows about someone"))

    def _has_lineage(self, table):
        with self.store.lock:
            cols = {r[1] for r in self.store.conn.execute(f"PRAGMA table_info({table})").fetchall()}
        return {"card_id", "source", "date"} <= cols

    def _card_around(self, cards, ts, source):
        """The one conversation a row's own moment sits inside, or None.

        A wrong link is worse than none: what this is for is the ground under
        a later cross-store read, and a memory attached to a conversation it
        did not come out of would be read as evidence. So it is strict on
        three counts, and says None much more often than it answers.

        Several cards cover one instant -- she is in the group chat and in the
        kitchen at once -- so the WRITER has to say which side of her life the
        row came from: writing to him, or talking to one of her own people.
        A writer that says neither places nothing, which is why a state tick
        about the scene is left alone: its wording is often about his last
        message while the only card around the moment is a friend's.
        The odds-and-ends card never answers, because its span runs from the
        first stray line of the day to the last and containment proves nothing
        about it -- the same limit the thread puts on it (`sim/thread.py`
        carded). Of the cards left, the shortest span wins: it is the most
        specific claim."""
        inside = [c for c in cards
                  if float(c["start_ts"]) <= ts <= float(c["end_ts"]) and c["room"] != "odds and ends"]
        if source in self.HIS_ROOM:
            inside = [c for c in inside if c["room"] == "chat with him"]
        elif source in self.THEIR_ROOM:
            inside = [c for c in inside if c["room"] != "chat with him"]
        else:
            return None
        if not inside:
            return None
        inside.sort(key=lambda c: (float(c["end_ts"]) - float(c["start_ts"]), -float(c["start_ts"])))
        return inside[0]

    def link_day(self, date_str, quiet=False):
        """Attach the conversation each of that day's memories and facts came
        out of, where one can be found. Returns how many rows were linked.

        Run at the end of every write of a day's cards, and by hand over the
        days already carded (`relink`, `/episodes relink`). It is the only
        thing that reads all three stores at once: nothing else knows the span
        of a conversation, and the card writer is given no collaborator, so
        the statements are here and each is guarded on the column existing.
        Lineage only -- no row is dropped, merged or scored differently for
        having a card."""
        cards = self.for_date(date_str)
        if not cards:
            return 0
        linked = 0
        for table, _text, _label in self.LINEAGE:
            if not self._has_lineage(table):
                continue
            with self.store.lock:
                rows = self.store.conn.execute(
                    f"SELECT rowid, ts, COALESCE(source,'') FROM {table} WHERE date=? AND card_id IS NULL",
                    (date_str,)).fetchall()
            for rid, ts, source in rows:
                if str(source) in self.TOLD_LATER:
                    continue
                card = self._card_around(cards, float(ts or 0), str(source))
                if card is None:
                    continue
                with self.store.lock:
                    self.store.conn.execute(f"UPDATE {table} SET card_id=? WHERE rowid=?", (int(card["id"]), rid))
                    self.store.conn.commit()
                linked += 1
        if linked and not quiet:
            logger.log(f"[episodes] {date_str}: {linked} row(s) of what she keeps now name the conversation they came from")
        return linked

    def _unlink_cards(self, ids):
        """A day written again gets new card rows, so the links to the old
        ones are cleared before `link_day` makes them afresh."""
        if not ids:
            return
        marks = ",".join("?" * len(ids))
        for table, _text, _label in self.LINEAGE:
            if not self._has_lineage(table):
                continue
            with self.store.lock:
                self.store.conn.execute(f"UPDATE {table} SET card_id=NULL WHERE card_id IN ({marks})", list(ids))
                self.store.conn.commit()

    def relink(self, days=14, end_ts=None):
        """The back-link over the days already carded, newest first: (rows,
        days looked at). For a save whose cards were written before anything
        recorded what they fed."""
        end = float(end_ts or self.clock.now_ts())
        have, rows, seen = self.dates(), 0, 0
        for i in range(int(days)):
            d = self.clock.date_str(end - i * 86400)
            if d not in have:
                continue
            seen += 1
            rows += self.link_day(d, quiet=True)
        if rows:
            logger.log(f"[episodes] {rows} row(s) over {seen} carded day(s) now name the conversation they came from")
        return rows, seen

    def linked_count(self):
        """How many rows of her record name a card at all."""
        n = 0
        for table, _text, _label in self.LINEAGE:
            if not self._has_lineage(table):
                continue
            with self.store.lock:
                n += int(self.store.conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE card_id IS NOT NULL").fetchone()[0])
        return n

    def fed(self, card_id):
        """What one card fed: the rows of her record that name it, as
        (what kind of row it is, who wrote it, the text)."""
        out = []
        for table, text_col, label in self.LINEAGE:
            if not self._has_lineage(table):
                continue
            with self.store.lock:
                for r in self.store.conn.execute(
                        f"SELECT COALESCE(source,''), {text_col} FROM {table} WHERE card_id=? ORDER BY ts",
                        (int(card_id),)).fetchall():
                    out.append((label, str(r[0]), str(r[1])))
        return out

    def fed_report(self, date_str=None, n=6):
        """Her past as cards, each with what it fed: `/episodes fed [date]`."""
        cards = self.for_date(date_str) if date_str else self.rows()[-n:]
        if not cards:
            return f"no cards for {date_str}" if date_str else "no cards yet"
        out = [f"what each card fed ({date_str or 'the last ' + str(len(cards))}):"]
        for c in cards:
            out.append(f"  [{self.clock.to_char(c['start_ts']):%a %d %b %H:%M}] {c['room']}, "
                       f"{c['n_lines']} lines: {str(c['shape'])[:70]}")
            rows = self.fed(c["id"])
            if not rows:
                out.append("      (nothing of her record names this conversation)")
            for label, source, text in rows:
                out.append(f"      {label} ({source or 'unattributed'}): {text[:90]}")
        return "\n".join(out)

    # ---------------- reading ----------------

    def for_date(self, date_str):
        with self.store.lock:
            rows = self.store.conn.execute("SELECT * FROM episodes WHERE date=? ORDER BY start_ts", (date_str,)).fetchall()
        return [dict(r) for r in rows]

    def between(self, start_ts, end_ts):
        with self.store.lock:
            rows = self.store.conn.execute("SELECT * FROM episodes WHERE start_ts>=? AND start_ts<? ORDER BY start_ts",
                                           (float(start_ts), float(end_ts))).fetchall()
        return [dict(r) for r in rows]

    def dates(self):
        with self.store.lock:
            return {r[0] for r in self.store.conn.execute("SELECT DISTINCT date FROM episodes").fetchall()}

    def rows(self):
        with self.store.lock:
            rows = self.store.conn.execute("SELECT * FROM episodes ORDER BY start_ts").fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def anchors_of(card):
        try:
            return json.loads(card.get("anchors") or "[]")
        except (TypeError, ValueError):
            return []

    def text_of(self, card):
        """Shape and anchors as one text, for search and embedding."""
        return (card.get("shape") or "") + " " + " ".join(a.get("text", "") for a in self.anchors_of(card))

    def render(self, card, stamp, full=True):
        """The card as the thread shows it, at its own time: a labelled
        header, the shape, and -- for the recent days (`full`) -- the exact
        lines that were said. Older, the shape alone: the exact words stay
        in the card for recall."""
        head = f"[{stamp} · {card['room']} · {card['n_lines']} messages, until {self.clock.hm(card['end_ts'])}] (as you remember it)"
        lines = [head, str(card["shape"]).strip()]
        if full:
            for a in self.anchors_of(card):
                who = a.get("who") or ""
                lines.append(f"  「{a.get('text', '')}」" + (f" — {who}" if who else ""))
        return "\n".join(lines)

    def backfill(self, start_ts, end_ts, max_days=8):
        """Cards for the days in [start, end) that have none and have a
        record: at most `max_days` calls. Run once after boot in a thread
        and after every compile, so a save from before the cards has them
        for the days its thread shows past verbatim."""
        if not self.config.episodes.enabled:
            return 0
        have = self.dates()
        wrote = 0
        t = start_ts
        while t < end_ts and wrote < max_days:
            d = self.clock.date_str(t)
            if d not in have and (self.store.messages_for_date(d) or any(x.get("date") == d for x in self.store.get("cast_chat", []) or [])):
                if self.write(d):
                    wrote += 1
            t += 86400
        if wrote:
            logger.log(f"[episodes] backfilled {wrote} day(s)")
        # and the back-link over the same days. A day's own cards are written
        # in the middle of its compile, before the settlers -- a promise kept,
        # a goal given up -- have written their memories of it, so those rows
        # are placed on the next pass rather than never (`link_day`). This runs
        # after boot and after every compile.
        try:
            self.relink(days=int((end_ts - start_ts) / 86400) + 1)
        except Exception as e:
            logger.log(f"[episodes] the back-link over the carded days did not run: {type(e).__name__}: {e}")
        return wrote

    def search(self, words):
        """(score, 'episode', when, body, overlap) rows for recall, by words."""
        out = []
        if not words:
            return out
        for r in self.rows():
            tw = tokens(self.text_of(r), _MIN_LATIN)
            ov = words & tw
            if ov:
                when = self.clock.to_char(r["start_ts"]).strftime("%Y-%m-%d %H:%M")
                out.append((len(ov) / (len(words) ** 0.5) * 1.1, "episode", f"{when} {r['room']}", self.text_of(r)[:500], ov))
        return out

    def report(self, n=5):
        rows = self.rows()
        by_date = {}
        for r in rows:
            by_date[r["date"]] = by_date.get(r["date"], 0) + 1
        out = [f"episode cards: {len(rows)} over {len(by_date)} day(s)" + (f"; {self.embed.report()}" if self.embed is not None else "")]
        try:
            out[0] += f"; {self.linked_count()} row(s) of what she keeps name the conversation they came from"
        except Exception as e:
            out[0] += f"; lineage unreadable ({type(e).__name__})"
        for r in rows[-n:]:
            out.append("  " + self.render(r, self.clock.to_char(r["start_ts"]).strftime("%a %d %b %H:%M")).replace("\n", "\n    ")[:600])
            for label, source, text in self.fed(r["id"]):
                out.append(f"      it fed: {label} ({source or 'unattributed'}): {text[:80]}")
        return "\n".join(out)
