"""Which work he means, when the machine's own facts cannot settle it.

Three layers decide what she is told about a thing he opened, and only the
third is a model's.

**One: the identity of the work is code's.** Every piece of evidence needed
to tell a 2006 one-episode OVA from the 2007 television run that shares its
Japanese title was already on the machine and unread: the folder the file sat
in, the season number in `S00E01`, and each candidate's episode count. That
is `sim/watching_him.py parse_file` / `parse_special` and
`AnimeKB.resolve_candidates`, and it costs nothing.

**Two: the relevance of a recalled row is also code's**, because it happens
on the reply path -- one shared content word, a cap on rows that arrived on a
cosine alone, each row's own mean subtracted (`sim/embed.py`).

**Three: this file.** The residue is genuinely a reading of text: two
editions with one title and no id from his list yet, a page whose identity
only its own words can settle, a title he typed that ties. One small role,
`which_one`, is handed a table of candidates code built and answers with an
id OUT OF THAT TABLE, or `null` for "none of these", or `"unsure"` for
"fetch nothing and wait". It never writes a word she reads: the caller looks
the id up in its own table and uses its own object, and the reason the model
gives goes to the log and to the store and nowhere else.

Where it runs: the worker that reads up on an episode he played, and the
lookup's own thread. **Never in a reply path**, the same rule
`works.her_part_verdict` is written to. A failure, a timeout, an answer that
does not parse, a confidence under the floor and an id code had already ruled
impossible all leave CODE's ranking standing, so nothing here can stop her
or delay her.

Where the answer is kept, and this is the line that matters: **the identity
of a work is a fact about the world, so it goes in the machine's shared store**
(`machine/retrievals.py`, pool `resolved`) under a key that names the question
and never the character, and both characters read the one answer. **A question
about HER RECORD -- whether a memory of hers is about this moment -- must
never go there**, because its candidates are her memories; it belongs in her
own save. `record_relevance` is the only way to write one and it refuses the
machine's store outright.

spec: docs/resolver.md
"""
import json
import re
import threading

import logger

SHARED_POOL = "resolved"


def norm(s):
    """The same normalisation `AnimeKB` uses, so a key written here and an id
    resolved there cannot disagree about what the question was."""
    return re.sub(r"[^a-z0-9぀-ヿ一-鿿]", "", str(s or "").lower())


class Resolver:
    # `llm` is the model client and `retrievals` the machine's store of what
    # has been fetched and decided about the world. Both are handed over after
    # construction (`sim/wiring.py`), and with either of them absent this
    # answers with code's own ranking and asks nothing.
    WIRES = ("llm", "retrievals")

    def __init__(self, config, store, clock, anime_kb=None, typesafe=None):
        self.config = config
        self.store = store
        self.clock = clock
        self.anime_kb = anime_kb
        # The hosted classifier (`typesafe.py`, `docs/system-one.md`): when her
        # config turns the `which_one` use on, one `choice` over code's own
        # candidate ids answers the question the `which_one` role answers in
        # JSON today. Code still does the lookup in its own table; a failure or
        # an answer under the floor leaves the ranking standing.
        self.typesafe = typesafe
        self.llm = None
        self.retrievals = None
        from sim import wiring
        wiring.declare(self)

    # ---------------- what the log says about every decision ----------------

    @staticmethod
    def say(question, cands, chosen, dropped=(), by="code", why=""):
        """One `[resolver]` line per decision: the question, the candidates
        with their ids and editions, what was chosen, what was dropped and
        why, and whether code or the model chose.

        Until 2026-09-04 the only trace of a wrong choice was a line about
        episode titles in the middle of a fetch, and nothing at all in the
        line she read."""
        def one(c):
            if not isinstance(c, dict):
                return str(c)
            return (f"mal:{c.get('aid')} {c.get('title') or ''}"
                    + (f" [{c.get('type')}" + (f", {c.get('eps')} ep" if c.get("eps") else "") + "]"
                       if c.get("type") or c.get("eps") else ""))
        bits = [f"[resolver] {question}: {len(cands)} candidate(s)"]
        if cands:
            bits.append("; ".join(one(c) for c in cands[:6]))
        bits.append("chose " + (one(chosen) if chosen else "nothing"))
        if dropped:
            bits.append("dropped " + "; ".join(str(d) for d in dropped))
        bits.append(f"by {by}")
        if why:
            bits.append(str(why)[:200])
        logger.log(" -- ".join(bits))

    # ---------------- the paid call ----------------

    def on(self):
        c = getattr(self.config, "which_one", None)
        return bool(c is not None and getattr(c, "enabled", False) and self.llm is not None)

    def _table(self, cands):
        """The candidate table the role is handed: one row per candidate, ids
        and quoted text only. Nothing about her interior goes in, and a
        candidate's own words are quoted rather than translated."""
        n = int(getattr(self.config.which_one, "max_candidates", 6) or 6)
        rows = []
        for c in cands[:n]:
            head = str(c.get("blurb") or "").strip().replace("\n", " ")[:300]
            rows.append(f"{c.get('aid')}\t{c.get('type') or '?'}, "
                        f"{c.get('eps') or '?'} episode(s)"
                        + (f", {c.get('season')}" if c.get("season") else "")
                        + (f"\t{head}" if head else ""))
        return "id\twhat it is\tthe first 300 characters\n" + "\n".join(rows)

    def _ask_typesafe(self, question, cands, cue, key):
        """The hosted classifier's reading of code's own table, or None.

        One `choice` over the candidate ids plus `unsure` and `none`, so the
        answer is already an id the caller can look up. Everything that decides
        the outcome stays in `choose_work`: a `none` chooses nothing, an
        `unsure` keeps the ranking and says so, and an answer under the use's
        floor leaves code's ranking standing."""
        ts = self.typesafe
        if ts is None or not ts.ready("which_one"):
            return None
        use = ts.use("which_one") or {}
        floor = float(use.get("threshold", 0.5))
        criteria = {}
        for c in cands:
            aid = c.get("aid")
            if not aid:
                continue
            head = str(c.get("blurb") or "").strip().replace("\n", " ")[:300]
            criteria[str(int(aid))] = (
                f"{c.get('type') or '?'}, {c.get('eps') or '?'} episode(s)"
                + (f", {c.get('season')}" if c.get("season") else "")
                + (f" - {head}" if head else ""))
        criteria["unsure"] = "cannot tell from the candidates"
        criteria["none"] = "none of these"
        body = (f"THE QUESTION: {question}\n\nWHAT IS KNOWN ABOUT THE MOMENT:\n{cue}\n\n"
                f"THE CANDIDATES:\n{self._table(cands)}")
        questions = {"chosen": {
            "type": "choice",
            "instructions": "Which candidate is the work this moment is about? "
                            "Copy its id, or `unsure`, or `none`.",
            "criteria": criteria}}
        answers = ts.ask("which_one", {"the question, the moment and the candidates": body}, questions)
        if not answers:
            return None
        chosen, conf = ts.choice(answers, "chosen")
        if chosen is None or conf < floor or chosen not in criteria:
            return None
        out = {"chosen": None, "unsure": False, "confidence": conf,
               "why": "the classifier's reading", "reused": False}
        if chosen == "unsure":
            out["unsure"] = True
        elif chosen != "none":
            try:
                out["chosen"] = int(chosen)
            except (TypeError, ValueError):
                return None
        logger.log(f"[resolver] typesafe: {chosen} (conf {conf:.2f})")
        return out

    def _ask(self, question, cands, cue, key):
        """The one call. Returns `{chosen, confidence, why, unsure}` or None.

        The answer is written to the machine's store the moment it exists
        (`get_or_fetch`), keyed on the question, so the other character never
        pays for it again and two processes that notice the same play in the
        same minute ask once between them."""
        got = self._ask_typesafe(question, cands, cue, key)
        if got is not None:
            return got
        c = self.config.which_one
        ids = {int(x.get("aid")) for x in cands if x.get("aid")}
        body = (f"THE QUESTION: {question}\n\nWHAT IS KNOWN ABOUT THE MOMENT:\n{cue}\n\n"
                f"THE CANDIDATES:\n{self._table(cands)}")

        def call():
            data, _raw = self.llm.call_json("which_one", [
                {"role": "system", "content": self.config.prompt_text("which_one")},
                {"role": "user", "content": body}])
            if not isinstance(data, dict):
                return None
            chosen = data.get("chosen")
            out = {"chosen": None, "unsure": False,
                   "confidence": 0.0, "why": str(data.get("why") or "")[:400]}
            if isinstance(chosen, str) and chosen.strip().lower().startswith("unsure"):
                out["unsure"] = True
            elif chosen is not None:
                try:
                    out["chosen"] = int(str(chosen).strip())
                except (TypeError, ValueError):
                    out["chosen"] = None
                    out["unsure"] = True
            try:
                out["confidence"] = float(data.get("confidence") or 0.0)
            except (TypeError, ValueError):
                out["confidence"] = 0.0
            # An answer with no reason and no choice is nothing to store.
            text = json.dumps(out, ensure_ascii=False)
            return {"text": text, "meta": {"answer": out, "candidates": sorted(ids),
                                           "question": question}}

        try:
            if self.retrievals is None:
                got = call()
                row = {"text": (got or {}).get("text", ""), "meta": (got or {}).get("meta") or {},
                       "reused": False} if got else None
            else:
                row = self.retrievals.get_or_fetch(
                    SHARED_POOL, key, call, model=self._model_slug())
        except Exception as e:
            logger.log(f"[resolver] the call failed: {type(e).__name__}; code's answer stands")
            return None
        if not row:
            return None
        ans = (row.get("meta") or {}).get("answer")
        if not isinstance(ans, dict):
            try:
                ans = json.loads(row.get("text") or "{}")
            except ValueError:
                return None
        ans["reused"] = bool(row.get("reused"))
        return ans

    def _model_slug(self):
        try:
            return str((self.config.model("which_one") or {}).get("model") or "")
        except Exception:
            return ""

    def _timed(self, fn):
        """The call with `which_one.timeout_seconds` over it. Past the timeout
        code's answer stands and the thread finishes on its own -- the paid
        answer still reaches the store, because the store is written inside
        the call and never held here."""
        out = {}

        def run():
            try:
                out["ans"] = fn()
            except Exception as e:
                logger.log(f"[resolver] the call raised: {type(e).__name__}")
        t = threading.Thread(target=run, daemon=True)
        t.start()
        t.join(float(getattr(self.config.which_one, "timeout_seconds", 30) or 30))
        if t.is_alive():
            logger.log("[resolver] the call has not come back inside "
                       f"{getattr(self.config.which_one, 'timeout_seconds', 30)}s; "
                       f"code's answer stands")
            return None
        return out.get("ans")

    # ---------------- question one: which work, which edition ----------------

    def choose_work(self, question, cands, cue, key, code_pick=None):
        """The identity question. `cands` is the ranked list code built, best
        first, each `{aid, title, type, eps, ...}`; `code_pick` is what code
        would answer on its own, which is `cands[0]` unless the caller says
        otherwise.

        Returns `(chosen, decided_by, unsure)`. `chosen` is one of `cands` or
        None for "nothing -- fetch nothing"; `decided_by` is for the log.
        Code's own answer stands on every failure."""
        pick = code_pick if code_pick is not None else (cands[0] if cands else None)
        if not cands:
            self.say(question, cands, None, by="code", why="his list has nothing of that name")
            return None, "code", False
        if len(cands) == 1:
            self.say(question, cands, pick, by="code",
                     why=cands[0].get("rule") or "one candidate on his list")
            return pick, "code", False
        if not self.on():
            self.say(question, cands, pick, by="code",
                     dropped=[f"mal:{c['aid']} not asked about" for c in cands[1:]],
                     why="the resolver's role is off; the ranking stands")
            return pick, "code", False
        ans = self._timed(lambda: self._ask(question, cands, cue, key))
        if not ans:
            self.say(question, cands, pick, by="code", why="no usable answer; the ranking stands")
            return pick, "code", False
        floor = float(getattr(self.config.which_one, "min_confidence", 0.5) or 0.0)
        conf = float(ans.get("confidence") or 0.0)
        why = str(ans.get("why") or "")
        tag = "the model" + (" (a stored answer)" if ans.get("reused") else "")
        if ans.get("unsure"):
            self.say(question, cands, pick, by=tag,
                     dropped=["it says it cannot tell"], why=why)
            return pick, tag, True
        if conf < floor:
            self.say(question, cands, pick, by="code",
                     dropped=[f"its answer at confidence {conf:.2f}, under {floor:.2f}"], why=why)
            return pick, "code", False
        if ans.get("chosen") is None:
            self.say(question, cands, None, by=tag, why=why or "none of these")
            return None, tag, False
        hit = next((c for c in cands if int(c.get("aid") or 0) == int(ans["chosen"])), None)
        if hit is None:
            # an id that is not in the table it was handed, or one the episode
            # count had already ruled impossible: dropped, and code's ranking
            # stands
            self.say(question, cands, pick, by="code",
                     dropped=[f"mal:{ans['chosen']}, which is not in the table it was handed"],
                     why=why)
            return pick, "code", False
        self.say(question, cands, hit, by=tag,
                 dropped=[f"mal:{c['aid']}" for c in cands if c is not hit], why=why)
        return hit, tag, False

    # ---------------- question two: is this row about this moment ----------------

    def record_relevance(self, cue_key, verdicts):
        """A decision about HER RECORD, written to HER OWN SAVE.

        The candidates of a relevance question are her memories and her facts.
        A key naming them in the machine's shared store would put one
        character's record in a file the other reads, which is the fault
        `tools/isolation.py` and `tools/character_leaks.py` exist to catch --
        so this is the only writer for that answer and the machine's store is
        not reachable from it."""
        if not cue_key or not verdicts:
            return False
        try:
            rows = self.store.get("resolved_relevance", []) or []
            rows.append({"cue": str(cue_key)[:200], "ts": self.clock.now_ts(),
                         "verdicts": list(verdicts)[:20]})
            self.store.set("resolved_relevance", rows[-40:])
            return True
        except Exception as e:
            logger.log(f"[resolver] her own record of the relevance answer not written: "
                       f"{type(e).__name__}")
            return False
