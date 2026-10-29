import io
import json
import math
import logger

# Her picture of him: what she has decided he is, as opposed to what she knows
# he does.
#
# `user_facts` is the evidence log -- true things harvested from his PC, his
# list, his notes. This is the other thing entirely, and it comes first. Every
# belief here is derived from who she is rather than from anything he has done:
# a girl who has never been known by anybody needs him to see the real her, a
# girl who reads the air all day to stay out of trouble needs him to read her
# for once, a girl whose whole fear is being watched needs there to be no
# audience here. The seeds are in data/beliefs.json. Their `evidence` is low
# everywhere on purpose; that is what idealizing is.
#
# The point of holding it as an object is that it can be violated. Nothing is
# scripted as shocking: a discovery is charged exactly insofar as it costs her
# a belief she is invested in (sim/ick.py). And because a belief can be
# rewritten, the same discovery stops costing her anything once it has been.
# That is where "ah, that is just how he is" comes from -- not a decay curve,
# a revised belief.
#
# She does not revise on first contact. Her own sheet says she reads the air to
# avoid trouble and lies to save face, so her first move against a thing that
# does not fit is to explain it away. Strain accumulates and fades; only
# repeated pressure gets a belief rewritten, and what she is invested in she
# fights hardest for.


class ModelOfHim:
    """The machine, and the picture of him that first used it. What it works on
    is set by the four names below, so the same strain / confirm / shatter /
    revise behaviour can be pointed at what she has decided about herself
    without a second copy of it (sim/model_of_her.py)."""

    KEY = "beliefs"                 # where the set lives in kv
    SEED_ATTR = "beliefs_file"      # config.character.<this> is the seed json
    LOG = "beliefs"                 # the tag on its log lines
    REVISE_ROLE = "revise"          # the model role that rewrites one
    WHAT = "her picture of him"
    REVISE_HEADER = "WHAT SHE HAS BELIEVED ABOUT HIM"
    SETTLE_ON_SEED = True           # settle the day-zero set against her history
    # the wording of the brief (for the ick call) and of her prompt section;
    # the self-model (sim/model_of_her.py) points the same machine inward by
    # overriding these
    BRIEF_SETTLED = " [she is sure of this one; only something she cannot argue with touches it]"
    BRIEF_EMPTY = "- (she has decided nothing about him yet)"
    # The two notes that ride on a belief in HER prompt are pairs: the
    # heading above them was already in her language and these were not, so
    # each belief she reads ended in an English aside. The BRIEF_ ones above
    # stay English -- those go to the ick call, which is the machine asking
    # itself what there is to violate.
    PROMPT_STRAINED = (" (something has not fit this lately and you have been finding reasons for it; you have not let go of it)",
                       "（最近これに合わないことがあって、あなたはそのたびに理由を見つけている。手放してはいない）")
    PROMPT_REVISED = (" (you used to think better of him about this)",
                      "（これについては、前はもっと彼をよく思っていた）")
    PROMPT_HEAD = ("## What you have decided about him (you have never said any of this out loud, "
                   "you have never tested any of it, and you would be embarrassed to hear it read back)",
                   "## 彼について自分で決めたこと（どれも口に出したことはなく、確かめたこともない。"
                   "読み上げられたら恥ずかしい）")

    def __init__(self, config, llm, store, clock, memory=None):
        self.config = config
        self.llm = llm
        self.store = store
        self.clock = clock
        self.memory = memory
        if not self.store.get(self.KEY):
            self._seed()

    def _seed(self):
        # A blank seed path is a character who has decided nothing yet, not a
        # crash. The project empties a path on purpose (`Config.WORLD_KEYS`
        # does it for every world file a character with no world has no
        # business reading), so an empty path is a state the config produces
        # and this has to be the empty case the way `world/calendar.py` is --
        # in the constructor, so that everything downstream reads an empty set
        # rather than each reader guarding itself. A path naming a file that
        # is not there stays an error: that is a wrong path, not an absent one.
        path = str(getattr(self.config.character, self.SEED_ATTR, "") or "")
        if not path:
            self.store.set(self.KEY, [])
            logger.log(f"[{self.LOG}] no seed file: {self.WHAT} starts empty")
            return
        with io.open(path, "r", encoding="utf-8") as f:
            rows = json.load(f)["beliefs"]
        now = self.clock.now_ts()
        out = []
        for r in rows:
            b = dict(r)
            b.update({"strain": 0.0, "strained_count": 0, "last_strain_ts": 0,
                      "state": "held", "born_ts": now, "was": [], "why": []})
            out.append(b)
        self.store.set(self.KEY, out)
        logger.log(f"[{self.LOG}] seeded {self.WHAT} from {path}: {len(out)} things she has decided")
        c = self.config.beliefs
        facts = self.store.user_facts()
        if self.SETTLE_ON_SEED and c.settle_on_seed and len(facts) >= c.settle_min_facts:
            try:
                self.settle_against_history(facts)
            except Exception as e:
                logger.log(f"[{self.LOG}] not settled against her history: {type(e).__name__}: {e}")

    def settle_against_history(self, facts):
        """Put the day-zero picture where months of knowing him would have left
        it. The beliefs are derived from her, so they are right as a starting
        point and wrong as a description of someone four months in: she has been
        reading an app that shows her his computer since May. Seeded fresh onto a
        played-in save she would be shocked by the folder she has known about
        since spring. One call, once, the same idea as derive.apply_if_new for
        his relationship meters."""
        c = self.config.beliefs
        back = self.store.get("backstory", "")
        user = (
            f"HER PICTURE OF HIM, AS IT WAS ON THE FIRST DAY:\n{self.brief()}\n\n"
            + (f"HOW THEY GOT HERE:\n{back}\n\n" if back else "")
            + "WHAT SHE HAS ACTUALLY LEARNED ABOUT HIM SINCE:\n"
            + "\n".join(f"- {f}" for f in facts[-c.settle_facts_shown:])
        )
        messages = [{"role": "system", "content": self.config.prompt_text("settle_beliefs")},
                    {"role": "user", "content": user}]
        data, raw = self.llm.call_json("settle_beliefs", messages)
        rows = (data or {}).get("beliefs") if isinstance(data, dict) else None
        if not rows:
            logger.log(f"[{self.LOG}] history settled nothing")
            return 0
        n = 0
        # which beliefs are worn is the model's judgement; how many of them end
        # up visibly straining is not, so only the worst few take it at full
        # weight and the rest are marked without crossing the line
        graded = []
        for r in rows:
            if not isinstance(r, dict):
                continue
            bid = str(r.get("id", "")).strip()
            if not self.get(bid):
                continue
            try:
                borne, worn = float(r.get("borne_out", 0)), float(r.get("worn", 0))
            except (TypeError, ValueError):
                continue
            graded.append((bid, min(5.0, borne), min(5.0, worn), str(r.get("note", ""))[:160]))
        worst = {b for b, _, _, _ in sorted(graded, key=lambda g: -g[2])[: c.settle_max_straining]}
        for bid, borne, worn, note in graded:
            if borne > 0:
                self.confirm(bid, borne, note if borne >= worn else "")
            if worn > 0:
                scale = c.settle_strain_scale if bid in worst else c.settle_strain_scale * 0.35
                self.strain(bid, (worn / 5.0) * self.config.ick.strain_per_point * scale,
                            note if worn > borne else "")
            n += 1
        # and what she has already run into, so the novelty term knows she has
        # lived with these rather than treating each one as fresh
        kinds = [k for k in ((data or {}).get("kinds") or []) if isinstance(k, dict) and str(k.get("kind", "")).strip()]
        if kinds:
            now = self.clock.now_ts()
            self.store.set("ick_kinds", [{"kind": str(k["kind"])[:60], "seen": max(1, int(k.get("seen", 1) or 1)),
                                          "first_ts": now, "last_ts": now} for k in kinds[:20]])
            logger.log(f"[{self.LOG}] and {len(kinds)} sort(s) of thing she has already run into with him")
        logger.log(f"[{self.LOG}] settled {n} of them against {len(facts)} things she already knew")
        # and anything the record has plainly broken is rewritten here rather
        # than left standing, or she starts out holding a belief her own history
        # says she cannot be holding, and gets shocked by the folder she has
        # known about since May
        for _ in range(c.settle_max_revisions):
            due = self.due_revision()
            if not due:
                break
            if not self.revise(due):
                break
        return n

    # ---------------- access ----------------

    def beliefs(self):
        return self.store.get(self.KEY, [])

    def save(self, rows):
        self.store.set(self.KEY, rows)

    def get(self, bid):
        for b in self.beliefs():
            if b.get("id") == bid:
                return b
        return None

    def live_strain(self, b, now=None):
        """Strain fades. A thing that did not fit once and never again is a thing
        she talked herself out of; only repeated pressure gets anywhere."""
        now = now or self.clock.now_ts()
        age_days = max(0.0, (now - (b.get("last_strain_ts") or now)) / 86400.0)
        return float(b.get("strain", 0)) * math.exp(-math.log(2) * age_days / self.config.beliefs.strain_half_life_days)

    def revise_at(self, b):
        """How much it takes to make her let a piece of it go. What she has most
        riding on she defends longest; what she has actual grounds for she also
        defends longer, having reasons and not only needs."""
        c = self.config.beliefs
        return (c.revise_base
                + float(b.get("invested", 50)) / 100.0 * c.revise_per_invested
                + float(b.get("evidence", 0)) / 100.0 * c.revise_per_evidence)

    # ---------------- what a discovery does to it ----------------

    def settled(self, b):
        """She is not weighing this one any more: either she is certain of it or
        she has seen it demonstrated past arguing."""
        c = self.config.beliefs
        return (int(b.get("confidence", 50)) >= c.certain_from
                or int(b.get("evidence", 0)) >= c.graduate_from
                or b.get("state") == "known")

    def strain(self, bid, amount, why=""):
        """Something did not fit. Normally she absorbs it and finds a reason.

        But a belief she is certain of does not wear away by degrees. The
        higher the certainty the worse the contradiction, so past
        `certain_from` a real one takes the whole thing down at once and a
        small one does nothing at all -- which is what being sure of somebody
        actually feels like from the inside."""
        c = self.config.beliefs
        rows = self.beliefs()
        now = self.clock.now_ts()
        for b in rows:
            if b.get("id") != bid:
                continue
            if self.settled(b):
                if amount < c.shatter_min_strain:
                    logger.log(f"[{self.LOG}] {bid}: she is too sure of this to be niggled by that")
                    return b
                b["strain"] = round(self.revise_at(b) + 1, 1)
                b["last_strain_ts"] = now
                b["strained_count"] = int(b.get("strained_count", 0)) + 1
                b["shattered"] = True
                b["state"] = "straining"
                if why:
                    b["why"] = (b.get("why", []) + [{"date": self.clock.date_str(), "text": str(why)[:160]}])[-6:]
                self.save(rows)
                logger.log(f"[{self.LOG}] {bid} SHATTERED -- she was sure of this one "
                           f"(confidence {b.get('confidence')}, evidence {b.get('evidence')})")
                return b
            b["strain"] = round(self.live_strain(b, now) + float(amount), 1)
            b["last_strain_ts"] = now
            b["strained_count"] = int(b.get("strained_count", 0)) + 1
            if why:
                b["why"] = (b.get("why", []) + [{"date": self.clock.date_str(), "text": str(why)[:160]}])[-6:]
            b["state"] = "straining" if b["strain"] >= self.config.beliefs.straining_from else b.get("state", "held")
            self.save(rows)
            logger.log(f"[{self.LOG}] {bid} strained +{amount:.1f} -> {b['strain']:.1f} of {self.revise_at(b):.0f} "
                       f"({b.get('strained_count')} time(s) now)")
            return b
        return None

    def confirm(self, bid, amount, why=""):
        """Something bore a belief out. Before this the model could only ever
        erode: nothing raised evidence or confidence, so given enough time every
        belief revised, `invested` ratcheted down and she became unshockable. A
        belief she has actually seen demonstrated is grounded, which makes it
        harder to break later, and it takes some of the strain back off -- one
        good evening does not undo a pattern, but it is not nothing either.
        """
        c = self.config.beliefs
        rows = self.beliefs()
        now = self.clock.now_ts()
        for b in rows:
            if b.get("id") != bid or b.get("state") == "let_go":
                continue
            if self.settled(b):
                # it is not a belief any more, it is a thing she knows; further
                # confirmations of it are not worth anything
                return b
            share = float(amount) / 5.0
            b["evidence"] = min(100, int(b.get("evidence", 0)) + round(share * c.evidence_per_fit))
            b["confidence"] = min(100, int(b.get("confidence", 50)) + round(share * c.confidence_per_fit))
            before = self.live_strain(b, now)
            if before > 0:
                b["strain"] = round(max(0.0, before - share * c.strain_relieved_per_fit), 1)
                b["last_strain_ts"] = now
                if b["strain"] < c.straining_from and b.get("state") == "straining":
                    b["state"] = "held"
            if why:
                b["borne_out"] = (b.get("borne_out", []) + [{"date": self.clock.date_str(), "text": str(why)[:160]}])[-6:]
            self.save(rows)
            logger.log(f"[{self.LOG}] {bid} borne out +{amount:.0f} -> evidence {b['evidence']}, "
                       f"confidence {b['confidence']}" + (f", strain {before:.1f} -> {b['strain']:.1f}" if before > 0 else ""))
            if int(b.get("evidence", 0)) >= c.graduate_from and b.get("state") != "known":
                self._graduate(b, rows)
            return b
        return None

    def _graduate(self, b, rows):
        """She has seen it demonstrated past arguing. It stops being one of the
        things she has decided and becomes one of the things she knows, which is
        what user_facts is. It can still be shattered; it cannot be nibbled at,
        and it stops soaking up confirmations that were inflating the set."""
        b["state"] = "known"
        b["known_on"] = self.clock.date_str()
        self.save(rows)
        fact = f"About him, and she is sure of it: {b['text']}"
        try:
            if self.memory:
                self.memory.add_fact(fact, 4)
            else:
                self.store.add_user_fact(self.clock.now_ts(), fact)
        except Exception as e:
            logger.log(f"[{self.LOG}] {b['id']} graduated but the fact did not save: {type(e).__name__}")
        self.store.add_event(self.clock.now_ts(), self.clock.date_str(), "belief",
                             f"(she would not say it like this) she does not wonder about this any more: {b['text']}",
                             self.config.beliefs.event_salience)
        logger.log(f"[{self.LOG}] {b['id']} is not a belief any more, it is something she knows: {b['text'][:70]}")

    def due_revision(self):
        now = self.clock.now_ts()
        for b in self.beliefs():
            if b.get("state") == "let_go":
                continue
            if self.live_strain(b, now) >= self.revise_at(b):
                return b
        return None

    def revise(self, b):
        """She cannot hold it any more. One call rewrites what she believes now,
        in her own voice; the old wording is kept, because she should be able to
        feel that she used to think something else. After this the same evidence
        costs her nothing, which is the whole of habituation."""
        c = self.config.beliefs
        hist = "\n".join(f"- {w['date']}: {w['text']}" for w in b.get("why", [])) or "- (nothing written down)"
        user = (
            f"{self.REVISE_HEADER}: {b['text']}\n"
            f"WHY SHE EVER BELIEVED IT: {b.get('from', '')}\n"
            f"HOW MUCH RESTS ON IT: {b.get('invested', 50)} out of 100\n"
            f"HOW MUCH SHE ACTUALLY HAD TO GO ON: {b.get('evidence', 0)} out of 100\n"
            f"HOW MANY TIMES SOMETHING HAS NOT FIT: {b.get('strained_count', 0)}\n"
            + ("SHE WAS CERTAIN OF THIS ONE. It has not been wearing away; it has just been contradicted outright by something she cannot argue with, and it is going all at once.\n" if b.get("shattered") else "")
            + "\n"
            f"WHAT DID NOT FIT, IN ORDER:\n{hist}\n"
        )
        messages = [{"role": "system", "content": self.config.role_system(self.REVISE_ROLE)},
                    {"role": "user", "content": user}]
        data, raw = self.llm.call_json(self.REVISE_ROLE, messages)
        if not isinstance(data, dict) or not str(data.get("text", "")).strip():
            logger.log(f"[{self.LOG}] {b['id']} would not revise (nothing came back)")
            return None
        rows = self.beliefs()
        for row in rows:
            if row.get("id") != b["id"]:
                continue
            row["was"] = (row.get("was", []) + [{"date": self.clock.date_str(), "text": row["text"]}])[-4:]
            row["text"] = str(data["text"]).strip()[:200]
            row["state"] = "let_go" if data.get("let_go") else "revised"
            row["strain"] = 0.0
            row["confidence"] = max(0, int(row.get("confidence", 50)) - c.confidence_lost)
            row["invested"] = max(0, int(row.get("invested", 50)) - c.invested_lost)
            row["evidence"] = min(100, int(row.get("evidence", 0)) + c.evidence_gained)
            row["revised_on"] = self.clock.date_str()
            row["shattered"] = False
            self.save(rows)
            self.store.add_event(self.clock.now_ts(), self.clock.date_str(), "belief",
                                 self._revised_event(b, row), c.event_salience)
            logger.log(f"[{self.LOG}] {b['id']} REVISED: \"{b['text'][:60]}\" -> \"{row['text'][:80]}\"")
            return row
        return None

    def _revised_event(self, b, row):
        return (f"(she would not put it this way) she does not think of him as {b['text']} "
                f"any more. {row['text']}")

    # ---------------- her prompt ----------------

    def prompt_text(self):
        rows = [b for b in self.beliefs() if b.get("state") != "let_go"]
        if not rows:
            return ""
        now = self.clock.now_ts()
        rows.sort(key=lambda b: -int(b.get("invested", 0)))
        from sim.lang import say
        t = say(self.config)
        lines = []
        for b in rows[: self.config.beliefs.in_prompt]:
            line = f"- {b['text']}"
            if self.live_strain(b, now) >= self.config.beliefs.straining_from:
                # the protective move, made visible: she is not reconsidering,
                # she is holding it together and finding reasons
                line += t(*self.PROMPT_STRAINED)
            elif b.get("state") == "revised":
                line += t(*self.PROMPT_REVISED)
            lines.append(line)
        return "\n\n" + t(*self.PROMPT_HEAD) + "\n" + "\n".join(lines)

    def brief(self):
        """For the ick call: what there is to violate, with how much rests on each."""
        now = self.clock.now_ts()
        out = []
        for b in self.beliefs():
            if b.get("state") == "let_go":
                continue
            tag = ""
            if self.settled(b):
                tag = self.BRIEF_SETTLED
            elif self.live_strain(b, now) >= self.config.beliefs.straining_from:
                tag = " [already under strain]"
            out.append(f"- {b['id']}: {b['text']} (she has {b.get('invested', 50)} of 100 riding on this){tag}")
        return "\n".join(out) or self.BRIEF_EMPTY

    def report(self):
        now = self.clock.now_ts()
        rows = sorted(self.beliefs(), key=lambda b: -int(b.get("invested", 0)))
        lines = [f"{self.WHAT}: {len(rows)} thing(s) she has decided, "
                 f"{sum(1 for b in rows if b.get('state') == 'revised')} revised, "
                 f"{sum(1 for b in rows if b.get('state') == 'let_go')} let go"]
        for b in rows:
            st = self.live_strain(b, now)
            lines.append(f"\n  [{b['id']}] {b.get('state', 'held')}  invested {b.get('invested')}  "
                         f"confidence {b.get('confidence')}  evidence {b.get('evidence')}  "
                         f"strain {st:.1f}/{self.revise_at(b):.0f}  strained {b.get('strained_count', 0)}x")
            lines.append(f"     {b['text']}")
            for w in b.get("was", []):
                lines.append(f"     was ({w['date']}): {w['text']}")
            for w in b.get("why", [])[-3:]:
                lines.append(f"     did not fit ({w['date']}): {w['text']}")
            for w in b.get("borne_out", [])[-3:]:
                lines.append(f"     borne out ({w['date']}): {w['text']}")
        return "\n".join(lines)
