import math
import datetime
import logger
from sim.textutil import words as tokens
from sim import roster, wiring
from sim.embed import cued as embed_cued

# How she forgets, and what she keeps. Facts about him carry a weight (how
# much the thing would stick: a passing detail 1, a habit 3, his birthday
# or his work 5) and fade on a half-life that grows with the weight; a fact
# that resurfaces (the compile learns it again, or a word of it appears in
# what he just wrote) is reinforced and comes back. What has faded is not
# deleted, it is just not in front of her until something cues it, which is
# what forgetting is like. The same idea ages the cast sheet (a friend's
# situation from three weeks ago is "as of" then; from six weeks ago she
# has lost track) and the notes she has read. The context meter at the
# bottom measures what her prompt is made of, so growth is visible and the
# budgets in config.context mean something.

# One tokeniser for both languages (`sim/textutil.words`). The regex that
# was here treated a maximal run of kana and kanji as one token, which in a
# language without spaces is a whole clause -- so a Japanese line could not
# be matched by anything, in any language, including a near-identical
# Japanese line. Character bigrams fix that; the English minimum is
# unchanged.
_MIN_LATIN = 5


class Memory:
    # the meaning search over what she knows about him (sim/embed.py): a
    # faded fact comes back on a cosine as well as on a shared word
    WIRES = ("embed",)

    def __init__(self, config, store, clock):
        self.config = config
        self.store = store
        self.clock = clock
        self._migrate()
        wiring.declare(self)

    def _migrate(self):
        with self.store.lock:
            cols = {r["name"] for r in self.store.conn.execute("PRAGMA table_info(user_facts)").fetchall()}
            if "weight" not in cols:
                # facts from before this existed (the May era, the first v3 days)
                # were distilled from whole days; they are not passing details
                self.store.conn.execute("ALTER TABLE user_facts ADD COLUMN weight INTEGER DEFAULT 2")
                self.store.conn.execute("UPDATE user_facts SET weight = 4")
            if "last_seen" not in cols:
                self.store.conn.execute("ALTER TABLE user_facts ADD COLUMN last_seen REAL")
            if "mentions" not in cols:
                self.store.conn.execute("ALTER TABLE user_facts ADD COLUMN mentions INTEGER DEFAULT 1")
            self.store.conn.execute("UPDATE user_facts SET last_seen = ts WHERE last_seen IS NULL")
            # what she knows about the people around her, on the same curve
            # as what she knows about him. Before this a friend was a
            # `situation` line that went dated at 14 days and vanished at 45,
            # and nothing she had learned about Rena was kept at all.
            self.store.conn.execute("CREATE TABLE IF NOT EXISTS cast_facts (ts REAL, who TEXT, fact TEXT, "
                                    "weight INTEGER DEFAULT 2, last_seen REAL, mentions INTEGER DEFAULT 1)")
            # Where a fact came from: the mechanism that learned it, the day it
            # is about (which is not the hour it was written -- the compile
            # tells a day at three in the morning of the next one), and the
            # conversation it came out of when the card writer could place it
            # (`sim/cards.py link_day`). Her own memories have carried a writer
            # since they existed and the facts carried nothing, so one evening's
            # memory, fact and card had nothing in common to say they were one
            # evening. Every column is nullable: a row nobody named is left
            # unnamed rather than given a writer it did not have.
            for table in ("user_facts", "cast_facts"):
                have = {r["name"] for r in self.store.conn.execute(f"PRAGMA table_info({table})").fetchall()}
                for col, kind in (("source", "TEXT"), ("date", "TEXT"), ("card_id", "INTEGER")):
                    if col not in have:
                        self.store.conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {kind}")
                        logger.log(f"[memory] added {col} to {table}; rows written from now on carry it")
            self.store.conn.commit()

    # ---------------- facts about him ----------------

    def half_life_days(self, weight):
        hl = self.config.memory.half_life_days
        w = max(1, min(5, int(weight or 2)))
        return float(hl[w - 1])

    def score(self, row, now=None):
        now = now or self.clock.now_ts()
        age_days = max(0.0, (now - float(row["last_seen"] or row["ts"])) / 86400.0)
        w = max(1, min(5, int(row["weight"] or 2)))
        return w * math.exp(-math.log(2) * age_days / self.half_life_days(w))

    def rows(self):
        with self.store.lock:
            return self.store.conn.execute("SELECT rowid AS rid, ts, fact, weight, last_seen, mentions FROM user_facts ORDER BY ts").fetchall()

    def facts_for_prompt(self, cue_text=""):
        """Facts she has in front of her now: the ones above the fade line by
        score, plus faded ones the moment just cued -- by a word of it, or by
        meaning, so a Japanese line can reach an English fact and a paraphrase
        can reach an exact one. What came back gets its last_seen bumped: it
        came back to her.

        The cue decides WHICH facts come back and nothing else. A recalled
        fact's worth is still its half-life score, so cueing a thing does not
        make it important, and nothing is retrieved on an empty cue."""
        c = self.config.memory
        now = self.clock.now_ts()
        rows = self.rows()
        cues = tokens(cue_text or "", _MIN_LATIN)
        live, faded, word = [], [], {}
        for r in rows:
            s = self.score(r, now)
            if s >= c.fact_min_score:
                live.append((s, r))
                continue
            faded.append(r)
            if cues and len(tokens(r["fact"], _MIN_LATIN) & cues) >= 1:
                word[r["rid"]] = 1.0
        live.sort(key=lambda x: (-x[0], x[1]["ts"]))
        out = [r["fact"] for _, r in live[: c.max_facts]]
        # the persona is on the loop thread: only stored vectors, and only if
        # the model is already up (`App._backfill_vectors` is what loads it).
        #
        # A row the WORDS never found has to share one content word with the
        # moment even so, and only `max_cosine_only` of them may arrive at
        # all: on 2026-09-04 every by-meaning row judged against its cue was
        # wrong, and each of them shared no word with the cue whatsoever.
        stats = {}
        reach = embed_cued(self.embed, "fact", [(r["rid"], r["fact"]) for r in faded],
                           cue_text if cues else "", word,
                           row_words={str(r["rid"]): tokens(r["fact"], _MIN_LATIN) for r in faded},
                           cue_words=cues,
                           cap=int(getattr(c, "max_cosine_only", c.max_recalled)),
                           stats=stats)
        recalled = sorted((r for r in faded if reach.get(str(r["rid"]), 0.0) > 0),
                          key=lambda r: -reach[str(r["rid"])])[: c.max_recalled]
        if recalled or stats.get("no_word") or stats.get("over_cap"):
            with self.store.lock:
                for r in recalled:
                    self.store.conn.execute("UPDATE user_facts SET last_seen=?, mentions=mentions+1 WHERE rowid=?", (now, r["rid"]))
                self.store.conn.commit()
            out += [r["fact"] for r in recalled]
            by_meaning = sum(1 for r in recalled if r["rid"] not in word)
            no_word = sum(1 for r in recalled
                          if r["rid"] not in word
                          and not (tokens(r["fact"], _MIN_LATIN) & cues))
            logger.log(f"[memory] {len(recalled)} faded fact(s) came back on a cue"
                       + (f" ({by_meaning} by meaning, {no_word} with no shared word)"
                          if by_meaning else "")
                       + (f"; {stats.get('no_word', 0)} dropped for sharing no word with the "
                          f"moment, {stats.get('over_cap', 0)} over the by-meaning cap"
                          if (stats.get("no_word") or stats.get("over_cap")) else ""))
        return out

    def search_items(self, min_latin=4):
        """Every fact as one row of the retrieval: what to embed it as, the
        label the searcher gives it, the body it quotes back, its word keys
        and the weight a fact carries against a day narrative. One place, so
        the word search and the meaning search cannot disagree about which
        row is which. `min_latin` is the SEARCHER's English threshold (4 in
        `sim/recall.py`), not this module's."""
        return [{"ref": r["rid"], "embed": r["fact"], "label": f"known #{r['rid']}",
                 "body": r["fact"][:300], "keys": tokens(r["fact"], min_latin), "mult": 1.2}
                for r in self.rows()]

    def _embed_row(self, rid, text):
        """The vector of a row just written, written with it. The persona
        reads stored vectors only, so a fact learned at tonight's compile has
        to be embedded by whoever wrote it to be reachable by meaning from
        the next reply on. One short encode; a failure only costs the meaning
        half, the words still find it."""
        if self.embed is None or not rid:
            return
        try:
            self.embed.vectors("fact", [(rid, text)])
        except Exception as e:
            logger.log(f"[memory] no vector for the new fact: {type(e).__name__}: {str(e)[:80]}")

    def add_fact(self, fact, weight=2, source="", date=None):
        """A new fact from the compile; a near-duplicate of an existing one reinforces it instead.

        `source` names the mechanism that learned it and `date` the day it is
        about, both kept on the row: three rows from one evening -- a memory of
        her own, a fact about the friend, a card -- had nothing in common to
        say so (`docs/memory.md` §7). A writer that names neither leaves them
        empty, which reads as unattributed and never as the compile."""
        fact = str(fact).strip()
        if not fact:
            return "empty"
        now = self.clock.now_ts()
        new_words = tokens(fact, _MIN_LATIN)
        best, best_j = None, 0.0
        for r in self.rows():
            words = tokens(r["fact"], _MIN_LATIN)
            if not words or not new_words:
                continue
            j = len(words & new_words) / len(words | new_words)
            if j > best_j:
                best, best_j = r, j
        try:
            weight = max(1, min(5, int(weight)))
        except (TypeError, ValueError):
            weight = 2
        with self.store.lock:
            if best is not None and best_j >= self.config.memory.duplicate_jaccard:
                self.store.conn.execute("UPDATE user_facts SET last_seen=?, mentions=mentions+1, weight=MAX(weight, ?) WHERE rowid=?",
                                        (now, min(5, max(int(best["weight"] or 2), weight)), best["rid"]))
                self.store.conn.commit()
                return "reinforced"
            cur = self.store.conn.execute(
                "INSERT INTO user_facts(ts,fact,weight,last_seen,mentions,source,date) VALUES(?,?,?,?,1,?,?)",
                (now, fact, weight, now, str(source or "")[:20], date))
            rid = cur.lastrowid
            self.store.conn.commit()
        self._embed_row(rid, fact)
        return "new"

    def facts_report(self):
        now = self.clock.now_ts()
        rows = self.rows()
        live = sum(1 for r in rows if self.score(r, now) >= self.config.memory.fact_min_score)
        lines = [f"{len(rows)} facts, {live} in front of her (min score {self.config.memory.fact_min_score})"]
        for r in sorted(rows, key=lambda r: -self.score(r, now))[:50]:
            age = (now - float(r["last_seen"] or r["ts"])) / 86400
            lines.append(f"{self.score(r, now):4.2f} w{r['weight']} x{r['mentions']} {age:5.1f}d  {r['fact'][:90]}")
        return "\n".join(lines)

    # ---------------- facts about the people around her ----------------

    def who_key(self, name):
        """One key per person, through the roster -- the table the rest of the
        machinery is already keyed by.

        This used to fold honorifics and lowercase, and its own docstring said
        `mom` and `Yumi` are not resolved here. That was survivable while the
        record was English. Since the relabelling every caller passes the
        record name, so `cast_facts_for(古賀由美)` looked for 古賀由美 while the
        row sat under `mom`: on every cast turn since, she has been unable to
        reach a single thing she knows about her own mother, father or
        brother. A name the roster does not know -- a stranger, a teacher --
        keeps the old normalisation, which is what it is for."""
        n = str(name or "").strip()
        if not n:
            return ""
        try:
            if roster.role_of(self.config, n):
                return str(roster.key_of(self.config, n)).strip().lower()
        except Exception:
            pass
        n = n.lower()
        for suf in ("-chan", "-kun", "-san", "-senpai", "ちゃん", "くん", "さん"):
            if n.endswith(suf):
                n = n[: -len(suf)]
        return n.split()[0] if n else ""

    def cast_fact_rows(self, who=None):
        with self.store.lock:
            rows = self.store.conn.execute("SELECT rowid AS rid, ts, who, fact, weight, last_seen, mentions FROM cast_facts ORDER BY ts").fetchall()
        if who is None:
            return rows
        k = self.who_key(who)
        return [r for r in rows if self.who_key(r["who"]) == k]

    def add_cast_fact(self, who, fact, weight=2, source="", date=None):
        """`source` and `date` are the row's lineage, as on the facts about
        him: which mechanism learned it and which day it is about."""
        fact = str(fact).strip()
        who = str(who).strip()
        if not fact or not who:
            return "empty"
        now = self.clock.now_ts()
        new_words = tokens(fact, _MIN_LATIN)
        best, best_j = None, 0.0
        for r in self.cast_fact_rows(who):
            words = tokens(r["fact"], _MIN_LATIN)
            if not words or not new_words:
                continue
            j = len(words & new_words) / len(words | new_words)
            if j > best_j:
                best, best_j = r, j
        try:
            weight = max(1, min(5, int(weight)))
        except (TypeError, ValueError):
            weight = 2
        with self.store.lock:
            if best is not None and best_j >= self.config.memory.duplicate_jaccard:
                self.store.conn.execute("UPDATE cast_facts SET last_seen=?, mentions=mentions+1, weight=MAX(weight, ?) WHERE rowid=?",
                                        (now, weight, best["rid"]))
                self.store.conn.commit()
                return "reinforced"
            self.store.conn.execute(
                "INSERT INTO cast_facts(ts,who,fact,weight,last_seen,mentions,source,date) VALUES(?,?,?,?,?,1,?,?)",
                (now, who, fact, weight, now, str(source or "")[:20], date))
            self.store.conn.commit()
        return "new"

    def cast_facts_for(self, who, cue_text="", limit=None):
        """What she has in front of her about one person: above the fade line
        by score, plus faded ones a word in `cue_text` brings back."""
        c = self.config.memory
        now = self.clock.now_ts()
        cues = tokens(cue_text or "", _MIN_LATIN)
        live, recalled = [], []
        for r in self.cast_fact_rows(who):
            s = self.score(r, now)
            if s >= c.fact_min_score:
                live.append((s, r))
            elif cues:
                words = tokens(r["fact"], _MIN_LATIN)
                if len(words & cues) >= 1:
                    recalled.append(r)
        live.sort(key=lambda x: (-x[0], x[1]["ts"]))
        n = limit or c.cast_facts_max
        out = [r["fact"] for _, r in live[:n]]
        if recalled:
            with self.store.lock:
                for r in recalled[:2]:
                    self.store.conn.execute("UPDATE cast_facts SET last_seen=?, mentions=mentions+1 WHERE rowid=?", (now, r["rid"]))
                self.store.conn.commit()
            out += [r["fact"] for r in recalled[:2]]
        return out

    def cast_facts_report(self):
        now = self.clock.now_ts()
        rows = self.cast_fact_rows()
        if not rows:
            return "(nothing kept about anyone yet)"
        by = {}
        for r in rows:
            by.setdefault(self.who_key(r["who"]), []).append(r)
        lines = ["what she knows about people (score w*2^(-age/half); under "
                 f"{self.config.memory.fact_min_score} it is out of her prompt until cued)"]
        for k, rs in sorted(by.items()):
            lines.append(f"  {rs[0]['who']}:")
            for r in sorted(rs, key=lambda r: -self.score(r, now)):
                age = (now - float(r["last_seen"] or r["ts"])) / 86400
                lines.append(f"    {self.score(r, now):4.2f} w{r['weight']} x{r['mentions']} {age:5.1f}d  {r['fact'][:90]}")
        return "\n".join(lines)

    # ---------------- the cast sheet, aged ----------------

    def cast_lines(self, relationships):
        """People around her for her own prompt: recent situations plain, older ones dated, stale ones gone."""
        c = self.config.memory
        today = self.clock.now().date()
        lines = []
        for name, r in relationships.items():
            if name == "him" or not (r.get("situation") or r.get("unresolved")):
                continue
            seen = r.get("last_seen") or ""
            age = None
            try:
                age = (today - datetime.date.fromisoformat(seen[:10])).days if seen else None
            except ValueError:
                age = None
            if age is not None and age > c.cast_forget_days:
                continue
            bit = r.get("situation", "")
            if age is not None and age > c.cast_age_days and bit:
                bit = f"(as of {seen[:10]}, you have not heard since) {bit}"
            if r.get("unresolved"):
                bit += f" (between you: {r['unresolved']})"
            try:
                facts = self.cast_facts_for(name)
            except Exception:
                facts = []
            if facts:
                bit += " | what you know about them: " + "; ".join(facts)
            lines.append(f"- {name}: {bit}")
        return lines

    # ---------------- the context meter ----------------

    def ratio(self):
        """chars per token, calibrated from the model's own count."""
        return float(self.store.get("context_ratio", 0) or self.config.context.chars_per_token)

    def tokens(self, text):
        return int(len(text or "") / self.ratio()) + 1

    def calibrate(self, chars, prompt_tokens):
        if not chars or not prompt_tokens or prompt_tokens < 500:
            return
        r = chars / float(prompt_tokens)
        old = self.store.get("context_ratio", 0) or r
        new = old * 0.7 + r * 0.3
        self.store.set("context_ratio", round(new, 3))

    def fit(self, sections, history, situation):
        """Measure her prompt against the one budget, `context.target_tokens`.
        Nothing is trimmed here.

        The thread's verbatim window fits itself to what is left of the
        target after the parts that ride whole (`sim/thread.py _window`),
        dropping whole days at a midnight; everything else rides whole. So
        there is nothing left for this to do, and what used to be here is
        gone: popping the oldest turn one at a time and then shortening the
        diary, the notes index and the facts to a fixed count rewrote the
        head of the thread on every call, which is the one edit the
        provider's cache charges for everything behind. The three
        sub-budgets that followed (history, carried, situation) went on
        2026-09-04: they did nothing the target does not.

        A total still over target is the parts that ride whole outgrowing
        it, or the window's floor (`thread.verbatim_hours`) alone being over
        it. It is said so in the log and in the notes, and it is not hidden
        by taking a message off the front."""
        c = self.config.context
        notes = []
        total = (sum(self.tokens(v) for v in sections.values())
                 + sum(self.tokens(m["content"]) for m in history) + self.tokens(situation))
        if total > c.target_tokens:
            notes.append(f"over target ({total} tok)")
            logger.log(f"[context] {total} tokens against a target of {c.target_tokens}: the parts that ride "
                       f"whole plus the window's floor do not fit inside it. Raise the target or lower "
                       f"thread.verbatim_hours; nothing is trimmed message by message to cover it")
        return sections, history, notes

    def measure(self, sections, history, situation, notes=None):
        """sections: {name: text}. Logs and stores the shape of her prompt in
        tokens: the four parts of it against the one target.

        The system half and what she carries are counted apart because they
        are charged apart -- the system half is a cache prefix that changes
        about once a day, the carried block is re-sent whole on every call.
        The thread's window reads this record (kv `context_last`) to know
        how much of the target is left for the history."""
        from persona import sections as _sec
        sizes = {k: self.tokens(v) for k, v in sections.items() if v}
        carried_names = set(_sec.CARRIED)
        carried = sum(v for k, v in sizes.items() if k in carried_names)
        system = sum(v for k, v in sizes.items() if k not in carried_names)
        hist = sum(self.tokens(m["content"]) for m in history)
        sit = self.tokens(situation)
        total = system + carried + hist + sit
        c = self.config.context
        rec = {"ts": self.clock.now_ts(), "system": system, "carried": carried, "sections": sizes,
               "history_msgs": len(history), "history_tokens": hist, "situation": sit, "total": total,
               "ratio": self.ratio(), "trimmed": notes or []}
        self.store.set("context_last", rec)
        parts = ", ".join(f"{k} {v / 1000:.1f}k" for k, v in sizes.items())
        logger.log(f"[context] ~{total / 1000:.1f}k tokens of {c.target_tokens / 1000:.0f}k: system {system / 1000:.1f}k"
                   f" | history {len(history)} turn(s) {hist / 1000:.1f}k"
                   f" | carrying {carried / 1000:.1f}k"
                   f" | situation {sit / 1000:.1f}k ({parts})"
                   + (f" | {', '.join(notes)}" if notes else ""))
        return rec

    def report(self):
        r = self.store.get("context_last")
        if not r:
            return "no persona call measured yet"
        c = self.config.context
        win = self.store.get("thread_window") or {}
        lines = [f"last persona prompt: ~{r['total'] / 1000:.1f}k tokens (target {c.target_tokens / 1000:.0f}k, window {c.max_tokens / 1000:.0f}k; {r.get('ratio', 0):.2f} chars/token calibrated)",
                 f"  system {r['system'] / 1000:.1f}k"
                 f" | history {r['history_msgs']} turn(s) {r.get('history_tokens', 0) / 1000:.1f}k"
                 + (f" of {win.get('budget_tokens', 0) / 1000:.1f}k left of the target" if win.get("budget_tokens") is not None else "")
                 + f" | carrying {r.get('carried', 0) / 1000:.1f}k"
                 f" | situation {r['situation'] / 1000:.1f}k"
                 + (f" | {', '.join(r['trimmed'])}" if r.get("trimmed") else "")]
        for k, v in sorted(r["sections"].items(), key=lambda kv: -kv[1]):
            lines.append(f"  {k:10s} {v / 1000:5.1f}k tok")
        return "\n".join(lines)
