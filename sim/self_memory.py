import math
import re
import logger
import sqlite3
from sim import wiring
from sim.embed import cued as embed_cued
from sim.textutil import words as tokens

# Her own memory of her own life.
#
# `user_facts` gave her a real forgetting curve for him -- weights, half-lives,
# reinforcement, things coming back on a cue -- and she had nothing of the kind
# for herself. Her past was one narrative and one summary per date, and only
# the summary of the most recent day reached her prompt. Ask her about a
# Tuesday three weeks ago and there was one line, because the compile flattened
# every scene into prose and threw the detail away. That is backwards: people
# remember their own lives in more detail than they remember their friends'.
#
# So the compile now also names the few things from a day that she herself
# would still be carrying, with a weight for how much it would stick and a word
# for how it sits. Her memories are slower to go than facts about him (a fact
# about someone else is information; this is her life), and the ones that
# refuse to fade are what her sense of herself is made of.
#
# What this is not: a diary (that is hers, written, gated on `unsaid`) or a
# self-claim (a thing she has told him and must stay consistent with). This is
# what happened to her, as she holds it.

# What she reads has to be in her own language.
#
# Every mechanism that keeps a memory writes English: `commitments` builds
# "She kept her word to X", the state model's own reasons line is English
# prose, the compile authors in English. For the character whose whole inner
# and outer life is Japanese that put English sentences in her head -- four of
# them in her save on her first day, and one from every mechanism after that.
#
# The fix is at the door rather than at the fifteen call sites, because the
# door is the one place every one of them goes through and the sixteenth
# will go through it too. `add()` already asks the model for the same line in the
# other language, to use as a second search key; when the line arrives in the
# language she does not write, the two simply change places -- what she reads
# is the rendering in her own language, and the original becomes the hidden
# key. Nothing is lost and no extra call is made. For a character who writes
# English and is written to in English the swap never fires.
#
# `feeling` gets the same treatment and is dropped rather than left in the
# wrong language, because it is a word of decoration in the prompt and a
# wrong-language word there is worse than none.

# One tokeniser for both languages (`sim/textutil.words`). The regex that
# was here treated a maximal run of kana and kanji as one token, which in a
# language without spaces is a whole clause -- so a Japanese line could not
# be matched by anything, in any language, including a near-identical
# Japanese line. Character bigrams fix that; the English minimum is
# unchanged.
_MIN_LATIN = 4

# Where a memory came from decides whether it can fade. Something that
# happened to her while she was running is on the curve, because that is what
# forgetting is. Something written in from her own record is not an event she
# lived through, it is what she is made of -- her job, her family, the flat she
# lives in -- and nobody gradually stops knowing that they present a radio
# programme. The row already carries the answer in `source`, so the rule reads
# off the row and no column is added. Two things write this source and both
# write it from a character's own extracted archive: `sim/seed_memories.py`,
# which the program that runs her calls once at boot, and the one-off script
# that seeded the earlier character before that module existed
# (`yukarin/week/patch_live.py`). A character with no such archive has no row
# of this source at all, so nothing below changes anything for her.
STANDING_SOURCES = ("seed",)


_ISO_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _is_day(text):
    """Does this row's `date` name a calendar day? Most do. A row written in
    from an extracted record may hold a month, or the span the archive bounds
    the thing by, because nothing narrower is known."""
    return bool(_ISO_DAY.match(str(text or "")))


def _words(text):
    return tokens(text, _MIN_LATIN)


def _keys(row):
    """A row's search tokens, in BOTH languages: what she wrote and its gloss.
    This is the dual key -- an English cue reaches a Japanese memory through
    the gloss, and a Japanese cue reaches an English one the same way."""
    try:
        return _words(row["text"]) | _words(row["alt"] if "alt" in row.keys() else "")
    except Exception:
        return _words(row["text"])


class SelfMemory:
    # the meaning search over her own life (sim/embed.py): an English
    # question reaches a Japanese memory through the cosine, not only
    # through the gloss's words
    WIRES = ("embed",)

    def __init__(self, config, store, clock, state=None, llm=None):
        self.config = config
        self.store = store
        self.clock = clock
        self.state = state
        # optional: without it a memory is stored in the one language it was
        # written in, which is what happened before there was a gloss at all
        self.llm = llm
        # the language she writes, from the one setting that already says so
        self.writes_ja = str(getattr(config.character, "writes_to_him", "english")).lower().startswith("ja")
        # one short rendering per feeling word, for this process. The state
        # model hands the same gauge name over and over; a cache keyed inside
        # the instance belongs to one character, which is what a shared cache
        # has to be (tools/isolation.py).
        self._feeling_cache = {}
        self._ensure()
        wiring.declare(self)

    def hers(self, text):
        """Is this in the language she writes? Empty counts as hers -- there is
        nothing to read."""
        text = str(text or "").strip()
        if not text:
            return True
        from sim.textutil import is_japanese
        ja = is_japanese(text)
        if self.writes_ja:
            return ja
        # for a character who writes English, `is_japanese` is also true of a
        # line with no letters in it at all -- "20:15", "3km", an ellipsis --
        # and none of those is the other language
        return not ja or not any("぀" <= ch <= "ヿ" or "一" <= ch <= "鿿" or "ぁ" <= ch <= "ゟ"
                                 for ch in text)

    def _ensure(self):
        with self.store.lock:
            self.store.conn.execute("""
                CREATE TABLE IF NOT EXISTS self_memories (
                    id INTEGER PRIMARY KEY, ts REAL, date TEXT, text TEXT,
                    weight INTEGER DEFAULT 2, feeling TEXT,
                    last_seen REAL, mentions INTEGER DEFAULT 1)""")
            # where a memory came from: the mechanism that lived it (commit,
            # scenery, npc, rupture, spiral, goals, attachment, backstory) or
            # the compile, which writes from the record and has invented (memory
            # 78: a classmate and a rumour that were in no event). Read by
            # /absurd PROVENANCE, and by STANDING_SOURCES above, which is what
            # tells a life she lived from a life she was written with.
            try:
                self.store.conn.execute("ALTER TABLE self_memories ADD COLUMN source TEXT DEFAULT 'compile'")
                self.store.conn.commit()
            except sqlite3.OperationalError:
                pass
            # valence, -2 to +2, written by the compile. `feeling` is a word and
            # a word cannot be compared to a mood -- matching on it would be the
            # `_match_kind` mistake again. Rows written before this default to 0,
            # which makes them neutral rather than wrong.
            cols = {r[1] for r in self.store.conn.execute("PRAGMA table_info(self_memories)")}
            # The other-language rendering of the same memory, so a cue in
            # either language finds it. Two of the six memories the compile
            # kept on 2026-08-28 came back in Japanese where the other 63 were
            # English, and nothing written in one language could ever be
            # matched from the other.
            if "alt" not in cols:
                self.store.conn.execute("ALTER TABLE self_memories ADD COLUMN alt TEXT")
                logger.log("[self] added alt to self_memories; rows fill in as they are written")
            if "valence" not in cols:
                self.store.conn.execute("ALTER TABLE self_memories ADD COLUMN valence INTEGER DEFAULT 0")
                logger.log("[self] added valence to self_memories; existing rows are neutral")
            # Which conversation of her past this memory came out of, when the
            # card writer could place it (`sim/cards.py link_day`). One evening
            # can leave her a memory of her own, a fact about the friend who was
            # there and a card, three rows that can all land in one prompt with
            # nothing to say they are one thing. NULL is honest and common: a
            # memory the nightly compile wrote is about a whole day and sits
            # inside no single conversation.
            if "card_id" not in cols:
                self.store.conn.execute("ALTER TABLE self_memories ADD COLUMN card_id INTEGER")
                logger.log("[self] added card_id to self_memories; a row is linked when the cards of its day are written")
            # Where a row written in from an extracted record came from on the
            # tape: the event's stable id in the source file, the basis its
            # date rests on, and every episode and cue index the claim was
            # found at (`sim/seed_memories.py`). No prompt reads it. It is what
            # makes such a row auditable back to the archive she was read out
            # of, and its first field is what lets the seed be run twice
            # without writing anything twice. NULL for every row a mechanism
            # of hers wrote: a memory of a day she lived has no receipt.
            if "receipt" not in cols:
                self.store.conn.execute("ALTER TABLE self_memories ADD COLUMN receipt TEXT")
                logger.log("[self] added receipt to self_memories; a row written in from her own record carries one")
            self.store.conn.commit()

    # ---------------- keeping ----------------

    def half_life_days(self, weight):
        hl = self.config.self_memory.half_life_days
        return float(hl[max(1, min(5, int(weight or 2))) - 1])

    def standing(self, row):
        """Part of who she is rather than something that happened to her."""
        try:
            src = row["source"] if "source" in row.keys() else ""
        except Exception:
            src = ""
        return str(src or "") in STANDING_SOURCES

    def score(self, row, now=None):
        w = max(1, min(5, int(row["weight"] or 2)))
        # A memory that is part of her does not decay: its score is its weight,
        # for good. The exemption is here rather than at the readers because
        # `for_prompt`, `report` and anything added later all come through this
        # one function, and a guard at each of them is a guard the next reader
        # will not have.
        if self.standing(row):
            return float(w)
        now = now or self.clock.now_ts()
        age_days = max(0.0, (now - float(row["last_seen"] or row["ts"])) / 86400.0)
        return w * math.exp(-math.log(2) * age_days / self.half_life_days(w))

    def rows(self):
        with self.store.lock:
            return self.store.conn.execute(
                "SELECT rowid AS rid, ts, date, text, weight, feeling, last_seen, mentions, valence, alt, source "
                "FROM self_memories ORDER BY ts").fetchall()

    def embed_text(self, row):
        """What a memory is embedded as: what she wrote and its other-language
        rendering together, so the one vector carries both of the keys the
        word search already uses."""
        try:
            alt = row["alt"] if "alt" in row.keys() else ""
        except Exception:
            alt = ""
        return (str(row["text"] or "") + " " + str(alt or "")).strip()

    def _embed_row(self, rid, text):
        """The vector of a row just written, written with it: the persona
        reads stored vectors only, so a memory the compile kept tonight has
        to be embedded by its writer to be reachable by meaning tomorrow."""
        if self.embed is None or not rid or not str(text or "").strip():
            return
        try:
            self.embed.vectors("selfmem", [(rid, text)])
        except Exception as e:
            logger.log(f"[self] no vector for the new memory: {type(e).__name__}: {str(e)[:80]}")

    def gloss(self, text):
        """The same line in the other language, for the search key. Failure is
        not fatal: the row goes in without an `alt` and is still findable in the
        language it was written in."""
        if not getattr(self, "llm", None) or not str(text).strip():
            return ""

        # counted, not sniffed: `tomoe.cast.is_japanese` already does this and
        # already knows that a line of English quoting 「おやすみ」 is English.
        # A presence test called that memory Japanese and would have thrown
        # away a perfectly good key.
        from sim.textutil import is_japanese
        want_ja = not is_japanese(str(text))
        for attempt in (1, 2):
            try:
                out = self.llm.call("gloss", [
                    {"role": "system", "content": self.config.prompt_text("gloss")},
                    {"role": "user", "content": str(text)[:400]}], max_tokens=200)
            except Exception as e:
                logger.log(f"[self] no gloss ({type(e).__name__}); the memory is one-language only")
                return ""
            out = " ".join(str(out or "").split())[:400]
            if not out:
                continue
            # it has to be the OTHER language, or it is not a second key
            if is_japanese(out) != want_ja:
                logger.log(f"[self] the gloss came back in the same language, asked again")
                continue
            # and it has to be Japanese rather than Chinese. One of the first 69
            # came back 「彩的备用自动铅笔」 -- simplified, and Aya renamed 彩 --
            # which the voice checker has had a rule for since the day a
            # simplified 绫 turned up in her own mouth.
            try:
                from sim import voicecheck
                flags = voicecheck.check(self.config, out)
                if any(f[1] == "simplified-chinese" for f in flags):
                    logger.log(f"[self] the gloss came back in Chinese, asked again: {out[:40]}")
                    continue
            except Exception:
                pass
            return out
        return ""

    def add(self, date, text, weight=2, feeling="", valence=0, source="compile", card_id=None):
        """A near-duplicate of something she already carries reinforces it rather
        than sitting next to it: the same afternoon remembered twice is one
        afternoon she thinks about often."""
        text = str(text).strip()
        if not text:
            return "empty"
        try:
            weight = max(1, min(5, int(weight)))
        except (TypeError, ValueError):
            weight = 2
        now = self.clock.now_ts()
        # the other-language key, made before the lock: it is a model call
        alt = self.gloss(text)
        if not self.hers(text) and alt and self.hers(alt):
            # it came in written in the language she does not read. The
            # rendering is hers; the sentence the mechanism built becomes the
            # hidden key, so retrieval still works from either language.
            text, alt = alt, text
        elif not self.hers(text):
            logger.log(f"[self] a memory came in in the wrong language and no rendering came back; "
                       f"she will not read it until repair() gets to it: {text[:60]}")
        feeling = self._feeling_in_her_language(feeling)
        new_words = _words(text) | _words(alt)
        best, best_j = None, 0.0
        for r in self.rows():
            w = _keys(r)
            if not w or not new_words:
                continue
            j = len(w & new_words) / len(w | new_words)
            if j > best_j:
                best, best_j = r, j
        with self.store.lock:
            if best is not None and best_j >= self.config.self_memory.duplicate_jaccard:
                self.store.conn.execute(
                    "UPDATE self_memories SET last_seen=?, mentions=mentions+1, weight=MAX(weight,?) WHERE rowid=?",
                    (now, weight, best["rid"]))
                self.store.conn.commit()
                return "reinforced"
            try:
                valence = max(-2, min(2, int(valence)))
            except (TypeError, ValueError):
                valence = 0
            cur = self.store.conn.execute(
                "INSERT INTO self_memories(ts,date,text,weight,feeling,last_seen,mentions,valence,alt,source,card_id) "
                "VALUES(?,?,?,?,?,?,1,?,?,?,?)",
                (now, date, text, weight, str(feeling or "")[:40], now, valence, alt, str(source or "compile")[:20],
                 int(card_id) if card_id else None))
            rid = cur.lastrowid
            self.store.conn.commit()
        self._embed_row(rid, (text + " " + (alt or "")).strip())
        return "new"

    def _feeling_in_her_language(self, feeling):
        f = " ".join(str(feeling or "").split())[:40]
        if not f or self.hers(f):
            return f
        if f in self._feeling_cache:
            return self._feeling_cache[f]
        out = self.gloss(f)
        out = out if (out and self.hers(out)) else ""
        if not out:
            logger.log(f"[self] no word for how this one sits in her own language, so none: {f}")
        self._feeling_cache[f] = out
        return out

    def forget_day(self, date, source):
        """Drop one writer's memories of one date, vectors and all.

        For a writer that can be asked to do the same day twice -- the compile
        is the only one (`/compile <date>`) -- because the duplicate test is on
        wording, and the model writing the same evening a second time in other
        words gets past it. `/compile 2026-09-03` run twice left her carrying
        the same Mario Kart game and the same message from Rena as four
        memories instead of two. Returns how many were dropped."""
        with self.store.lock:
            rids = [r[0] for r in self.store.conn.execute(
                "SELECT rowid FROM self_memories WHERE date=? AND source=?", (date, source)).fetchall()]
            if rids:
                self.store.conn.execute("DELETE FROM self_memories WHERE date=? AND source=?", (date, source))
                self.store.conn.commit()
        if rids and self.embed is not None:
            try:
                self.embed.forget("selfmem", rids)
            except Exception as e:
                logger.log(f"[self] the old vectors were kept: {type(e).__name__}")
        return len(rids)

    def repair(self, limit=20):
        """Rows she cannot read: written before the rule above, or written
        while the rendering was failing. Most of them cost nothing to fix,
        because the rendering is already sitting in `alt` and the two only have
        to change places; the rest are one model call each and are capped, so a
        long-dead save does not turn a compile into a hundred calls."""
        wrong = [r for r in self.rows() if not self.hers(r["text"])]
        if not wrong:
            return 0
        swapped = glossed = 0
        for r in wrong[:limit]:
            alt = r["alt"] if "alt" in r.keys() else ""
            if alt and self.hers(alt):
                text, alt = alt, r["text"]
                swapped += 1
            else:
                text = self.gloss(r["text"])
                if not text or not self.hers(text):
                    continue
                alt = r["text"]
                glossed += 1
            feeling = self._feeling_in_her_language(r["feeling"])
            with self.store.lock:
                self.store.conn.execute(
                    "UPDATE self_memories SET text=?, alt=?, feeling=? WHERE rowid=?",
                    (text, alt, feeling, r["rid"]))
                self.store.conn.commit()
            # the two languages changed places, so the vector of the old
            # text is of a row that no longer reads that way
            if self.embed is not None:
                try:
                    self.embed.forget("selfmem", [r["rid"]])
                except Exception as e:
                    logger.log(f"[self] old vector kept: {type(e).__name__}")
            self._embed_row(r["rid"], (text + " " + (alt or "")).strip())
        if swapped or glossed:
            logger.log(f"[self] {swapped + glossed} memory(ies) she could not read put into her own language "
                       f"({swapped} by using the rendering already stored, {glossed} asked for)")
        return swapped + glossed

    def congruence(self, row):
        """How well a memory matches the mood she is in. People do not retrieve
        evenly: feeling low surfaces the low ones, which deepens the low. It is
        the second self-feeding loop in the system after the spiral, and it was
        missing entirely -- `recall.py` had no reference to state, mood or any
        gauge at all.

        Keyed on `mood`, which lags its causes, rather than on instantaneous
        affect: a mood is what colours retrieval, not the feeling of the
        minute."""
        c = self.config.self_memory
        if not (c.mood_congruent and self.state):
            return 1.0
        try:
            v = int(row["valence"] or 0)
        except (KeyError, IndexError, TypeError, ValueError):
            return 1.0
        if not v:
            return 1.0
        spec = self.config.state.gauges.get("mood") or {}
        base = float(spec.get("baseline", 55))
        swing = float(self.config.state.mood_from.max_swing)
        her = max(-1.0, min(1.0, (float(self.state.gauges.get("mood", base)) - base) / swing))
        return max(c.congruence_floor, 1.0 + c.congruence_weight * her * (v / 2.0))

    # ---------------- carrying ----------------

    def _turn(self, ring, slots, step=True):
        """Where in the record today starts.

        Kept in the store and stepped once a character day, not once a call:
        every call that writes her words builds the system prompt twice
        (`persona.system_for` does it for his room and for hers) and the two
        have to come out identical, which they cannot if the choosing moves
        between them. A day is also about the rate at which what is near the
        surface of a life actually changes."""
        if ring <= 0 or slots <= 0:
            return 0
        cur = self.store.get("selfmem_turn", {}) or {}
        today = self.clock.date_str()
        at = int(cur.get("at", 0) or 0)
        if step and cur.get("date") != today:
            # the first day starts at the top of the record rather than one
            # turn into it, or the heaviest slots-worth would be skipped and
            # not come round until the whole ring had
            at = (at + slots) % ring if cur else 0
            self.store.set("selfmem_turn", {"date": today, "at": at})
        return at % ring

    def _standing_for_prompt(self, rows, step=True):
        """Her biography, bounded.

        None of it fades, so all of it is equally in front of her and something
        other than the fade line has to choose. Two candidates were measured
        against her own record and both fail. Recency is meaningless here: the
        dates on these are when each thing was told on air, which is not the
        order in which they matter. And overlap with what he just wrote is
        noise -- a question naming her brother put four unrelated anecdotes
        above the one memory that names him, because conversational Japanese is
        mostly grammar and grammar collides with any sentence. That is the same
        finding `sim/lore.py` is built on, and the reason THAT retrieval matches
        hand-written names instead; a cue still reaches every one of these
        through `search`, where a model reads the excerpts and can throw the
        collisions away.

        So: weight, and a turn. Anything at the top of the scale is in every
        prompt, because weight 5 already means "for good" in this module. The
        rest of the slots walk the remainder in weight order, one step a
        character day, so the whole record comes round instead of the same few
        lines standing there for ever."""
        c = self.config.self_memory
        cap = max(0, int(c.standing_in_prompt))
        if not rows or not cap:
            return []
        always = [r for r in rows if int(r["weight"] or 2) >= 5][:cap]
        keep = {r["rid"] for r in always}
        ring = sorted((r for r in rows if r["rid"] not in keep),
                      key=lambda r: (-int(r["weight"] or 2), float(r["ts"] or 0)))
        slots = min(cap - len(always), len(ring))
        if slots <= 0:
            return always
        at = self._turn(len(ring), slots, step)
        return always + [ring[(at + i) % len(ring)] for i in range(slots)]

    def for_prompt(self, cue_text=""):
        """What she is still carrying: what she is made of, which does not fade,
        plus the lived ones above the fade line, plus any a word of his just
        brought back (and those get their last_seen bumped -- it came back to
        her)."""
        c = self.config.self_memory
        now = self.clock.now_ts()
        cues = _words(cue_text)
        live, faded, standing, word = [], [], [], {}
        for r in self.rows():
            # a row still in the wrong language does not go in front of her.
            # `repair` runs at the compile and clears them; until it has, she
            # is missing a memory rather than reading one in a language she
            # does not write.
            if not self.hers(r["text"]):
                continue
            # the two kinds are chosen separately and get their own slots, so a
            # save with hundreds of biography lines cannot crowd out the days
            # she has actually lived, and the days cannot bury the biography
            if self.standing(r):
                standing.append(r)
                continue
            s = self.score(r, now) * self.congruence(r)
            if s >= c.min_score:
                live.append((s, r))
                continue
            faded.append(r)
            if cues and len(_keys(r) & cues) >= 2:
                word[r["rid"]] = 1.0
        live.sort(key=lambda x: (-x[0], -x[1]["ts"]))
        out = [dict(r) for r in self._standing_for_prompt(standing)]
        out += [dict(r) for _, r in live[: c.max_in_prompt]]
        # and by meaning as well as by words: the persona is on the loop
        # thread, so only what is already stored and only if the model is up.
        #
        # The word test above wants TWO keys in common; a row that arrives on
        # its cosine alone has to share at least one, and only
        # `max_cosine_only` such rows arrive at all. On the second
        # character's save every one of her memories cleared the old fixed
        # floor for every Japanese cue, so this pool is the one where the
        # cosine was choosing at random.
        stats = {}
        reach = embed_cued(self.embed, "selfmem", [(r["rid"], self.embed_text(r)) for r in faded],
                           cue_text if cues else "", word,
                           row_words={str(r["rid"]): _keys(r) for r in faded},
                           cue_words=cues,
                           cap=int(getattr(c, "max_cosine_only", c.max_recalled)),
                           stats=stats)
        recalled = sorted((r for r in faded if reach.get(str(r["rid"]), 0.0) > 0),
                          key=lambda r: -reach[str(r["rid"])])[: c.max_recalled]
        if recalled or stats.get("no_word") or stats.get("over_cap"):
            with self.store.lock:
                for r in recalled:
                    self.store.conn.execute(
                        "UPDATE self_memories SET last_seen=?, mentions=mentions+1 WHERE rowid=?", (now, r["rid"]))
                self.store.conn.commit()
            out += [dict(r) for r in recalled]
            by_meaning = sum(1 for r in recalled if r["rid"] not in word)
            no_word = sum(1 for r in recalled
                          if r["rid"] not in word and not (_keys(r) & cues))
            logger.log(f"[self] {len(recalled)} thing(s) of her own came back on a cue"
                       + (f" ({by_meaning} by meaning, {no_word} with no shared word)"
                          if by_meaning else "")
                       + (f"; {stats.get('no_word', 0)} dropped for sharing no word with the "
                          f"moment, {stats.get('over_cap', 0)} over the by-meaning cap"
                          if (stats.get("no_word") or stats.get("over_cap")) else ""))
        return out

    def prompt_text(self, cue_text=""):
        rows = self.for_prompt(cue_text)
        if not rows:
            return ""
        lines = []
        for r in rows:
            # The month and the day, when the row has a calendar day to give.
            # A row written in from an extracted record may hold the span the
            # archive bounds the thing by instead ("1994-04-01..1996-03-31")
            # or a month with no day in it, because nothing narrower is known;
            # slicing five characters off those produced "- 04-01..1996-03-31:"
            # and "- 03:". When there is no day, the sentence carries its own
            # time ("in her fifth or sixth year of primary school") and the
            # honest prefix is none.
            when = str(r["date"] or "")
            lines.append(f"- {when[5:]}: {r['text']}" if _is_day(when) else f"- {r['text']}")
        from sim.lang import say
        from sim import existence
        t = say(self.config)
        # A character with no chat with him has nothing to define this list
        # against and nobody to have kept it from.
        head = (t("## Things of your own you are still carrying (your life, not his; you have not "
                  "necessarily told him any of it)",
                  "## いまも抱えている自分のこと（彼のことではなく、あなたの生活。彼に話したとは限らない）")
                if existence.has_chat(self.config) else
                t("## Things of your own you are still carrying (your life; you have not "
                  "necessarily told anybody any of it)",
                  "## いまも抱えている自分のこと（あなたの生活。誰かに話したとは限らない）"))
        return "\n\n" + head + "\n" + "\n".join(lines)

    def search_items(self):
        """Her own past as rows of the retrieval: what to embed each one as,
        the label the searcher gives it, the body it quotes back, its word
        keys in both languages and the weight her own life carries against a
        day narrative (she remembers what happened to her better than she
        remembers the shape of the day it happened in). One place, so the
        word search and the meaning search cannot disagree about which row is
        which.

        A standing row (her seeded record) is left out when
        `standing_in_prompt` is 0: those are lore records then, found by name
        (sim/lore.py), and serving them twice is the same line twice."""
        out = []
        lore_serves = int(self.config.self_memory.standing_in_prompt) <= 0
        for r in self.rows():
            if not self.hers(r["text"]):
                continue
            if lore_serves and self.standing(r):
                continue
            out.append({"ref": r["rid"], "embed": self.embed_text(r),
                        "label": f"{r['date']} #{r['rid']}", "body": r["text"][:300],
                        "keys": _keys(r), "mult": 1.3 * self.congruence(r)})
        return out

    def search(self, words):
        """For the recall: her own past by words, scored the same way the days
        are. The meaning half of the same pool is added by `Recall._semantic`
        over `search_items`, which is where the labels come from."""
        if not words:
            return []
        out = []
        for it in self.search_items():
            ov = words & it["keys"]
            if ov:
                out.append((len(ov) / (len(words) ** 0.5) * it["mult"],
                            "her own", it["label"], it["body"], ov))
        return out

    def recent_report(self, limit=14, exclude_date=None):
        """The last few things she is carrying, for the nightly compile.

        The compile is handed what she knows about him and about the people
        around her so that it reinforces rather than writing a second wording
        of the same thing; without this it wrote her own memories blind. Only
        the lived ones -- her biography is not something a day can repeat --
        only the ones in the language she reads, newest last, with the weight
        each carries and how often it has come back.

        `exclude_date` leaves out one date: the compile deletes its own
        memories of the day it is redoing, so showing them would tell the day
        not to write what it is about to lose."""
        rows = [r for r in self.rows()
                if not self.standing(r) and self.hers(r["text"])
                and (exclude_date is None or r["date"] != exclude_date)]
        rows = rows[-max(1, int(limit)):]
        if not rows:
            return "(nothing she is carrying yet)"
        out = []
        for r in rows:
            out.append(f"  {r['date']} w{r['weight']} x{r['mentions']} {str(r['text'])[:160]}"
                       + (f" [{r['feeling']}]" if r["feeling"] else ""))
        return "\n".join(out)

    def report(self):
        c = self.config.self_memory
        now = self.clock.now_ts()
        rows = self.rows()
        made_of = [r for r in rows if self.standing(r)]
        lived = [r for r in rows if not self.standing(r)]
        live = sum(1 for r in lived if self.score(r, now) >= c.min_score)
        chosen = {r["rid"] for r in self._standing_for_prompt(made_of, step=False)}
        lines = [f"{len(rows)} things she remembers of her own"]
        if made_of:
            lines.append(f"  {len(made_of)} of them are what she is made of and never fade; "
                         f"{len(chosen)} of those are in her prompt today (standing_in_prompt "
                         f"{c.standing_in_prompt}), and the turn moves on tomorrow")
        lines.append(f"  {len(lived)} she lived through, {live} of them still in front of her "
                     f"(min score {c.min_score})")
        for r in sorted(lived, key=lambda r: -self.score(r, now))[:40]:
            age = (now - float(r["last_seen"] or r["ts"])) / 86400
            lines.append(f"{self.score(r, now):4.2f} x{self.congruence(r):4.2f} w{r['weight']} v{r['valence'] or 0:+d} {age:5.1f}d  "
                         f"{r['date']} {r['text'][:78]}" + (f"  [{r['feeling']}]" if r["feeling"] else ""))
        for r in sorted(made_of, key=lambda r: (-int(r["weight"] or 2), float(r["ts"] or 0)))[:40]:
            lines.append(f"made of  w{r['weight']} {'IN PROMPT' if r['rid'] in chosen else '         '}  "
                         f"{r['date']} {r['text'][:78]}")
        return "\n".join(lines)
