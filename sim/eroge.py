"""What he is reading in a visual novel, as one thing she knows about.

The reader (`sensors/eroge_monitor.py`) hands over the Japanese lines his text
hooker caught while he read them. This decides when to look, pays for one
account of them, keeps the account and nothing else, and hands the words to
each program's own table so that how she comes to know it is never said here.

**The account is made on demand, at two moments, and never on a timer** (his
call, 2026-09-04): when a message of his has arrived and her reply is about to
be built, and when she has decided to write first and the reply is about to be
built. Those are the only moments the answer is worth anything, and a game
left open in the background between them costs nothing.

**Three rules decide what it is written from**, all three his:

  * the lines from where his current stretch of READING began -- a cursor, not
    a timer. A pause of an hour does not move it. A skip run moves it past the
    skipped lines, which are never summarised, because text he held the button
    through is not text he read. The window overflowing past
    `eroge.max_raw_chars` moves it too, which is also what catches a hooked
    menu or a line storm;
  * a floor of `eroge.min_new_lines` new lines before a call is worth making.
    Under it the last account stands;
  * one account of the stretch, and never the lines. **The raw text goes into
    one call and is dropped.** Nothing in the record can be quoted back
    afterwards, because nothing of it is kept: not in the save, not in a log.

The account's own instruction is the content gate and there is no other. An
explicit stretch comes out as one clause naming it as an intimate scene and
nothing further -- which is the same compression the module applies to
everything, applied where the compression happens to be total. That is a
prompt (`prompts/eroge_digest.txt`), not a filter, and it is the only place
the decision lives.

store: kv `eroge_cursor` (where his reading began and how far it has got), kv
`eroge_last` (the account, with what it was written from), kv `eroge_day` (the
day's accounts, which the compile turns into one fact about him and then
forgets). The game's CARD is not in her save at all: it is the same card
whoever looks it up, so it is the machine's (`machine/retrievals.py`, kind
`vn_card`) and one fetch serves both characters.

spec: PROJECT.md §12.14
"""

import logger
from sensors import eroge_monitor as reader
from sim import sight
from sim import wiring


class Eroge:
    # the model, and the machine's one store of what has been fetched about
    # the world -- a game's card is the same card whoever looks it up
    WIRES = ('llm', 'retrievals',)

    def __init__(self, config, store, clock):
        self.config = config
        self.store = store
        self.clock = clock
        self.llm = None
        self.retrievals = None
        wiring.declare(self)

    # ---------------- is he in one ----------------

    def playing(self):
        """The game in front of him this minute, or None."""
        if not self.config.eroge.enabled:
            return None
        try:
            return reader.now_playing(self.config)
        except Exception as e:
            logger.log(f"[eroge] his files not read: {type(e).__name__}")
            return None

    # ---------------- the look ----------------

    def look(self, reason=""):
        """One account of what he has been reading, if there is one to make.

        Called at the two moments a reply is about to be written. Returns the
        account it left standing, or None."""
        c = self.config.eroge
        if not c.enabled or self.llm is None:
            return None
        np = self.playing()
        if not np or not np.get("key"):
            return None
        self._know_the_game(np)
        cur = self.store.get("eroge_cursor", {}) or {}
        same = (cur.get("key") == np["key"]
                and abs(float(cur.get("session_start") or 0) - np["since_ts"]) < 1.0)
        rl = reader.read_lines(self.config, np, cursor=int(cur.get("index") or 0) if same else 0)
        self.store.set("eroge_cursor", {
            "key": np["key"], "session_start": np["since_ts"], "index": rl["cursor"],
            "first_id": rl["first_id"], "last_id": rl["last_id"], "note": rl["note"]})
        last = self.store.get("eroge_last", {}) or {}
        fresh = (last.get("key") == np["key"]
                 and abs(float(last.get("session_start") or 0) - np["since_ts"]) < 1.0
                 and int(last.get("cursor") or -1) == rl["cursor"])
        if fresh and int(last.get("last_id") or 0) >= rl["last_id"]:
            # not a line has moved since the account was written
            return last
        if not rl["lines"]:
            # the newest thing he did was hold the skip button down: she may be
            # told he is skipping and nothing about what he skipped
            return last if fresh else None
        new = (rl["last_id"] - int(last.get("last_id") or 0)) if fresh else len(rl["lines"])
        if new < int(c.min_new_lines):
            return last if fresh else None
        text = self._ask(np, rl, reason)
        if not text:
            return last if fresh else None
        row = {"key": np["key"], "title": np["title"], "vndb_id": np.get("vndb_id"),
               "session_start": np["since_ts"], "cursor": rl["cursor"],
               "first_id": rl["first_id"], "last_id": rl["last_id"],
               "note": rl["note"], "lines": len(rl["lines"]), "chars": rl["chars"],
               "digest": text, "at": self.clock.now_ts(), "why": str(reason or "")}
        self.store.set("eroge_last", row)
        self._keep_for_the_day(row, np)
        logger.log(f"[eroge] {np['title'][:24]}: {len(rl['lines'])} line(s), "
                   f"{rl['chars']} chars in, {len(text)} chars out"
                   + (f" ({rl['note']})" if rl["note"] else "") + f" -- {reason}")
        return row

    def _ask(self, np, rl, reason):
        """One call on the cheap model. The lines go in and are dropped: they
        are not written to the save, and the only place they are ever seen
        again is the model call log, which is the record of what was paid
        for."""
        c = self.config.eroge
        ja = str(getattr(self.config.character, "writes_to_him", "english")).lower() == "japanese"
        head = [f"Title: {np['title']}"]
        head.append("Write the account in Japanese." if ja else "Write the account in English.")
        head.append(f"At most {int(c.max_chars)} characters.")
        if rl["note"] == "skipped":
            head.append("He skipped ahead through the stretch before these lines: say that he "
                        "skipped through a part he had seen before, and write nothing about it.")
        elif rl["note"] == "ran long":
            head.append("The stretch before these lines ran longer than fits: say the account "
                        "begins part-way through, and write nothing about the earlier part.")
        body = "\n".join(l["text"] for l in rl["lines"])
        try:
            out = self.llm.call("eroge_digest", [
                {"role": "system", "content": self.config.prompt_text("eroge_digest")},
                {"role": "user", "content": "\n".join(head) + "\n\n" + body}])
        except Exception as e:
            logger.log(f"[eroge] the account was not written: {type(e).__name__}")
            return ""
        return " ".join(str(out or "").split())[: int(c.max_chars)]

    # ---------------- what she has ----------------

    def current(self):
        """The account she is holding, while he is still in the game it is
        about. It is about what is in front of him; once he has stopped it is
        the day's record's business, not the situation's."""
        if not self.config.eroge.enabled:
            return None
        row = self.store.get("eroge_last", {}) or {}
        if not row.get("digest"):
            return None
        np = self.playing()
        if not np or np.get("key") != row.get("key"):
            return None
        return row

    def glance_lines(self, t):
        """(text, kind, pin) for her situation, in her program's words.

        Pinned, like the episode he is watching: what he is doing this minute
        and what is happening in it is not a line that competes for room."""
        if not self.config.eroge.enabled:
            return []
        np = self.playing()
        if not np:
            return []
        cur = self.store.get("eroge_cursor", {}) or {}
        row = self.current()
        if not row and str(cur.get("note") or "") == "skipped":
            # he is holding the button down through something he has read
            # before: she may be told that and nothing about what is in it
            return [(t(*sight.w2(self.config, "eroge_skipping", n=np["title"])), "fact", False)]
        out = [(t(*sight.w2(self.config, "eroge_playing", n=np["title"],
                            m=int(np["minutes"]))), "fact", True)]
        if row:
            out.append((t(*sight.w2(self.config, "eroge_digest_line", n=np["title"]))
                        + row["digest"], "fact", True))
        return out

    # ---------------- the game as a thing she knows ----------------

    def _know_the_game(self, np):
        """The card, once per game, under every name he might type: the title,
        the developer, and each of the cast with the reading he set."""
        if not np.get("vndb_id"):
            return
        key = f"eroge:{np['vndb_id']}"
        from sim.known import KnownThings
        known = KnownThings(self.config, self.store, self.clock)
        if known.get(key):
            return
        from sensors import vndb
        text = vndb.card(self.retrievals, np["vndb_id"],
                         int(self.config.eroge.card_max_chars))
        if not text:
            return
        names = [np["title"]]
        for g in reader.games(self.config):
            if g.get("key") != np["key"]:
                continue
            names.append(g.get("developer") or "")
            for person in g.get("cast") or []:
                names += [person.get("name") or "", person.get("reading") or ""]
        seen, uniq = set(), []
        for n in names:
            n = str(n or "").strip()
            if len(n) >= 2 and n not in seen:
                seen.add(n)
                uniq.append(n)
        known.add(key, uniq[:60], "game", text, source="eroge", show=np["title"])

    # ---------------- the day ----------------

    def _keep_for_the_day(self, row, np):
        """The day's accounts, for the compile. The sitting's own bounds go
        with each one so the fact can say how long he was at it; the raw lines
        do not, because they are nowhere."""
        day = self.store.get("eroge_day", {}) or {}
        date = self.clock.date_str()
        rows = [r for r in (day.get(date) or []) if r.get("session_start") != np["since_ts"]]
        rows.append({"title": np["title"], "digest": row["digest"],
                     "session_start": np["since_ts"], "last_line_ts": np["last_line_ts"],
                     "at": row["at"]})
        day[date] = rows[-12:]
        for d in sorted(day)[:-4]:
            day.pop(d, None)
        self.store.set("eroge_day", day)


def day_fact(store, date_str, max_chars=300):
    """The day's reading as one fact about him, or "".

    How long he was at it is the sittings' own bounds summed, not a count of
    accounts: an evening is several accounts of one sitting."""
    rows = (store.get("eroge_day", {}) or {}).get(date_str) or []
    if not rows:
        return ""
    by = {}
    for r in rows:
        t = str(r.get("title") or "")
        seen = by.setdefault(t, {"sittings": {}, "digest": "", "at": 0.0})
        start = float(r.get("session_start") or 0)
        seen["sittings"][start] = max(seen["sittings"].get(start, 0.0),
                                      float(r.get("last_line_ts") or 0) - start)
        if float(r.get("at") or 0) >= seen["at"]:
            seen["at"], seen["digest"] = float(r.get("at") or 0), str(r.get("digest") or "")
    parts = []
    for title, seen in sorted(by.items(), key=lambda kv: -sum(kv[1]["sittings"].values())):
        mins = sum(seen["sittings"].values()) / 60.0
        how = f"{mins / 60:.1f} hours" if mins >= 90 else f"{int(round(mins))} minutes"
        parts.append(f"he spent {how} reading {title}" + (f"; {seen['digest']}" if seen["digest"] else ""))
    return " / ".join(parts)[:int(max_chars)]
