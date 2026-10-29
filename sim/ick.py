import math
from sim import wiring
import logger
from sim import sight
from sim.textutil import words as tokens

# What learning something about him does to her.
#
# Nothing is charged in itself. A discovery costs her exactly what it takes
# away from her picture of him (sim/model_of_him.py) and gives her exactly what
# it bears out, so there is no list anywhere of things that are supposed to be
# shocking. The same download that takes 90 points off "he is not like the boys
# at school" in August takes nothing off her in October, because by then the
# belief has been rewritten to accommodate it. That is the whole of
# habituation: not a decay curve, a revised belief.
#
# Both directions matter. Before `fits` existed the model could only erode:
# given enough time every belief revised, `invested` ratcheted down and she
# became unshockable. A belief she has actually seen demonstrated is grounded,
# and grounded is harder to break.
#
# Judgements come from the model, because they are judgements: what does not
# fit and how badly, what it bears out, how private it is in itself, and what
# the girls in her class would make of it. Facts come from the code, because a
# model asked for a fact will confabulate one: how she came to know it, how
# many times she has met this sort of thing, and how wound up she was.
#
# How she came to know it decides two things at once. `hidden` is how much it
# lands as a betrayal, and speakability is whether she can ever raise it. She
# went through his things: unspeakable, because asking means admitting she
# looked. The app showed her: he gave her the app, so it is allowed, and being
# strange about it is a choice rather than a trap. He told her himself: it is
# just a thing she knows, and the telling is its own evidence about him.

# One tokeniser for both languages (`sim/textutil.words`). The regex that
# was here treated a maximal run of kana and kanji as one token, which in a
# language without spaces is a whole clause -- so a Japanese line could not
# be matched by anything, in any language, including a near-identical
# Japanese line. Character bigrams fix that; the English minimum is
# unchanged.
_MIN_LATIN = 3

_SOURCE_HIDDEN = {"snoop": 1.0, "digest": 0.7, "x": 0.55, "photo": 0.5, "lookup": 0.45, "told": 0.25}
# what she can bring up without giving herself away. Only the snoop is a secret:
# he gave her the app and her own X account is hers, so those she could mention
# if she were brave, and does not, which is a different thing from cannot.
_SPEAKABLE = {"digest", "x", "photo", "lookup", "told"}


def _words(text):
    return tokens(text, _MIN_LATIN)


def _jaccard(a, b):
    wa, wb = _words(a), _words(b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


class Ick:
    WIRES = ('graph', 'primitives',)
    def __init__(self, config, llm, store, clock, state, model=None, records=None, typesafe=None):
        self.config = config
        self.llm = llm
        self.store = store
        self.clock = clock
        self.state = state
        self.model = model
        self.records = records
        # The hosted classifier (`typesafe.py`, `docs/system-one.md`): when her
        # config turns the `ick` use on, two scores -- how much her circle would
        # make of it, and how private the thing is in itself -- stand over the
        # role's when they answer above the use's floor. The per-belief
        # `strain`/`weight` and the prose stay the role's.
        self.typesafe = typesafe
        wiring.declare(self)

    def _scores_typesafe(self, user):
        """(circle, intimate) from Jev, or None when it cannot answer above the
        floor. Both are 0-5, the role's own scale."""
        ts = self.typesafe
        if ts is None or not ts.ready("ick"):
            return None
        use = ts.use("ick") or {}
        floor = float(use.get("threshold", 0.3))
        questions = {
            "circle": {"type": "score",
                       "instructions": "How much would the girls in her class make of this if they "
                                       "knew? Score 0 when she has no such circle at all (the state "
                                       "says so), or when this is nothing they would remark on. Most "
                                       "ordinary things are 0 or 1.",
                       "criteria": ["none", "a little", "some", "a lot", "a great deal", "everything"]},
            "intimate": {"type": "score",
                         "instructions": "How private is the thing in itself -- bodily, sexual, "
                                         "ashamed, medical, money lost, the kind of thing anybody "
                                         "keeps to themselves? Most ordinary things are 0 or 1.",
                         "criteria": ["none", "slight", "some", "quite", "very", "entirely"]},
        }
        answers = ts.ask("ick", {"the picture, what she learned and how": user}, questions)
        if not answers:
            return None
        c, cconf = ts.score(answers, "circle")
        i, iconf = ts.score(answers, "intimate")
        if cconf is None or cconf < floor:
            return None
        try:
            circle = max(0.0, min(5.0, float(c)))
        except (TypeError, ValueError):
            return None
        try:
            intimate = max(0.0, min(5.0, float(i))) if (iconf or 0) >= floor else None
        except (TypeError, ValueError):
            intimate = None
        logger.log(f"[ick] typesafe: circle {circle:.1f} (conf {cconf:.2f})"
                   + (f", intimate {intimate:.1f}" if intimate is not None else ""))
        return circle, intimate

    # ---------------- how new this sort of thing is ----------------

    def kinds(self):
        return self.store.get("ick_kinds", [])

    def kinds_text(self):
        """What she has already run into, most familiar first. Shown to the
        scoring call so it can say which of these a thing is. Without this it
        was being asked to reuse a wording it had never been shown, and coined
        a fresh label every time -- "his evening browsing" nine times over for the same pages she has watched him read for months."""
        rows = sorted(self.kinds(), key=lambda k: -int(k.get("seen", 1)))
        return "\n".join(f"- {k['kind']} (she has run into this {k.get('seen', 1)} time(s))"
                         for k in rows[: self.config.ick.kinds_in_prompt])

    def _match_kind(self, kind):
        """The model is shown her kinds and asked to copy one back exactly, so an
        exact hit is the normal path. The word-overlap pass underneath is only a
        loose net for near-misses; it cannot see that "his evening browsing" and "a sports page" are one thing, which is why it cannot be the matcher."""
        want = (kind or "").strip().lower()
        for k in self.kinds():
            if str(k.get("kind", "")).strip().lower() == want:
                return k
        best, best_j = None, 0.0
        for k in self.kinds():
            j = _jaccard(k.get("kind", ""), kind)
            if j > best_j:
                best, best_j = k, j
        return best if best_j >= self.config.ick.kind_jaccard else None

    def _record_kind(self, kind, ts):
        rows = self.kinds()
        k = self._match_kind(kind)
        if k:
            k["seen"] = int(k.get("seen", 1)) + 1
            k["last_ts"] = ts
        else:
            rows.append({"kind": kind, "seen": 1, "first_ts": ts, "last_ts": ts})
        self.store.set("ick_kinds", rows[-self.config.ick.max_kinds:])

    # ---------------- how she was when she found it ----------------

    def _state_multiplier(self):
        """Only unease adds. A calm gauge counts as nothing rather than as a
        discount, the rule the snoop gate had to learn twice."""
        c = self.config.ick
        g = self.state.gauges
        m = 1.0
        for name, weight in (("anxiety", c.anxiety_weight), ("jealousy", c.jealousy_weight),
                             ("loneliness", c.loneliness_weight)):
            over = self.state.over_rest(name)
            m += max(0.0, over) / 100.0 * weight
        if g.get("energy", 50) < c.tired_below:
            m += c.tired_bonus
        return max(0.6, min(c.max_state_multiplier, m))

    def _circle_multiplier(self, circle):
        """The girls never find out and she never tells them, but she runs
        everything past them in her head. What they would have something to say
        about costs more than the same thing in private -- and only to the
        extent she is currently in the grip of what people think."""
        c = self.config.ick
        if circle <= 0:
            return 1.0
        grip = max(0.3, float(self.state.gauges.get("anxiety", c.circle_anxiety_ref)) / c.circle_anxiety_ref)
        return 1.0 + (circle / 5.0) * c.circle_weight * min(2.0, grip)

    def _cast_text(self):
        if not self.records:
            return ""
        try:
            sheet = self.records.cast_sheet(self.state.relationships, meters=False, influence=True)
        except Exception:
            return ""
        lines = [ln for ln in (sheet or "").split("\n") if ln.strip() and "him" not in ln.lower()[:6]]
        out = "\n".join(lines[: self.config.ick.cast_in_prompt])
        # what they ACTUALLY hold about her right now amplifies the charge
        # more honestly than the static sheet: "what would Rena make of it"
        # asked of the live edge, not of a stance written weeks ago
        g = self.graph
        if g:
            gl = g.tomoe_lines()
            if gl:
                out += "\nWHAT THEY CURRENTLY HOLD ABOUT HER:\n" + gl
        return out

    # ---------------- the discovery ----------------

    def assess(self, what, source="snoop", context=""):
        c = self.config.ick
        if not c.enabled or not (what or "").strip() or not self.model:
            return None
        # A prediction error needs a model to violate. For a character who has
        # just met him there is no picture to take anything away from, so
        # nothing he does can be out of character and the call is not worth
        # making -- and the score it would have returned would have been
        # invented against an empty brief. `sim/primitives.py`, docs §3.
        prim = self.primitives
        if prim is not None:
            key = self.state._him_key() or "him"
            if not prim.can_ick(key):
                logger.log("[ick] not scored: she has no picture of him yet for this to violate")
                return None
        cast = self._cast_text()
        kinds = self.kinds_text()
        known = self.store.user_facts()[-c.known_shown:]
        user = (
            f"TIME: {self.clock.both()}\n"
            f"HOW SHE CAME TO KNOW IT: {c.source_words.get(source, source)}\n\n"
            f"HER PICTURE OF HIM (what there is to take away, and to bear out):\n{self.model.brief()}\n\n"
            + (f"THE GIRLS WHOSE OPINION RUNS HER LIFE (they will never know about any of this):\n{cast}\n\n" if cast else "")
            + (f"WHAT SHE ALREADY KNOWS ABOUT HIM (anything here is old news, not a discovery):\n"
               + "\n".join(f"- {f}" for f in known) + "\n\n" if known else "")
            + (f"SORTS OF THING SHE HAS RUN INTO WITH HIM BEFORE (say which of these this is, copying the wording exactly; only name a new one if it is genuinely a different sort of thing):\n{kinds}\n\n" if kinds else "")
            + f"WHAT SHE LEARNED:\n{what.strip()[:c.max_chars]}\n"
            + (f"\nAROUND IT: {context.strip()[:400]}\n" if context else "")
        )
        messages = [{"role": "system", "content": self.config.prompt_text("ick")},
                    {"role": "user", "content": user}]
        data, raw = self.llm.call_json("ick", messages)
        if not isinstance(data, dict):
            logger.log("[ick] unscored (nothing parseable came back)")
            return None

        def num(v, hi=5.0):
            try:
                return max(0.0, min(hi, float(v)))
            except (TypeError, ValueError):
                return 0.0

        kind = str(data.get("kind", "") or "").strip()[:60] or "something about him"
        intimate = num(data.get("intimate"))
        circle = num(data.get("circle"))
        # The classifier's two scores stand over the role's when it answers
        # above its floor; the per-belief strain/weight and the prose stay the
        # role's.
        got = self._scores_typesafe(user)
        if got:
            circle, jint = got
            if jint is not None:
                intimate = jint
        why = str(data.get("why", "") or "")[:200]

        def pairs(field, amount_key):
            # each carries its own note. One shared line filed against every
            # belief it touched put a sentence about the folder into the history
            # of a belief that had nothing to do with it.
            out = []
            for t in (data.get(field) or [])[:2]:
                if not isinstance(t, dict):
                    continue
                b = self.model.get(str(t.get("belief", "")).strip())
                a = num(t.get(amount_key))
                if b and a > 0:
                    out.append((b, a, str(t.get("note", "") or "")[:160]))
            return out

        touches = pairs("touches", "strain")
        fits = pairs("fits", "weight")

        # what it costs her: each belief weighted by what she has riding on it
        # and by whether it is about her own place with him at all
        cost = 0.0
        for b, s, _ in touches:
            about = 1.0 + (float(b.get("about_her", 0)) / 5.0) * c.about_her_weight
            cost += (s / 5.0) * (float(b.get("invested", 50)) / 100.0) * about
        cost += (intimate / 5.0) * c.intimate_weight

        prior = self._match_kind(kind)
        seen = int(prior.get("seen", 0)) if prior else 0
        # How much of this is about HER rather than about him. The ick already
        # carries it per belief; here it decides whether the discount applies
        # at all.
        about_her = max([float(b.get("about_her", 0)) for b, _s, _n in touches] or [0.0])
        # Three rules, not three numbers. A thing about her costs the tenth
        # time what it cost the first -- her save holds one at charge 50.8,
        # that she is a line in his ledger and does not know whether the line
        # is a person, and getting used to that is not something a person
        # does. And a thing HE told her that does not fit is prediction error
        # against his own account of himself, which is a different event from
        # prediction error against something she inferred by watching.
        never = (about_her >= c.about_her_top) or (source == "told")
        if never:
            novelty = 1.0
        elif seen >= c.settled_after:
            # not a discovery any more: a fact about him
            novelty = 0.0
        else:
            novelty = max(c.novelty_floor, 1.0 / math.pow(1.0 + seen, c.novelty_power))
        hidden = _SOURCE_HIDDEN.get(source, 0.7)
        smult = self._state_multiplier()
        cmult = self._circle_multiplier(circle)
        charge = max(0.0, min(100.0, (cost / c.charge_ceiling) * 100.0 * hidden * novelty * smult * cmult))

        ts = self.clock.now_ts()
        self._record_kind(kind, ts)
        known_kind = "already one of hers" if prior else "a new sort of thing"
        touched_txt = ", ".join(f"{b['id']}+{s:.0f}" for b, s, _ in touches) or "nothing of hers"
        fits_txt = ", ".join(f"{b['id']}+{a:.0f}" for b, a, _ in fits)

        # the belief takes the hit whether or not the charge clears the floor: a
        # small thing that keeps not fitting is how a picture comes apart
        for b, s, note in touches:
            self.model.strain(b["id"], (s / 5.0) * c.strain_per_point, note or why)
        for b, a, note in fits:
            self.model.confirm(b["id"], a, note or why)

        if charge < c.min_charge:
            if fits:
                logger.log(f"[ick] {kind}: nothing taken, and it bore out {fits_txt}")
            else:
                logger.log(f"[ick] {kind}: costs her little ({touched_txt}, intimate {intimate:.0f}, "
                           f"circle {circle:.0f}, x{novelty:.2f} after {seen} = {charge:.0f}"
                           + ("; this sort of thing is just how he is now" if novelty == 0 else "") + ")")
            return None

        speakable = source in _SPEAKABLE
        item = {"ts": ts, "date": self.clock.date_str(), "kind": kind, "charge": round(charge, 1),
                "what": why, "source": source, "speakable": speakable, "intimate": intimate,
                "circle": circle, "seen_before": seen, "about_her": round(about_her, 1),
                "touched": [{"belief": b["id"], "strain": s} for b, s, _ in touches]}
        items = self.store.get("charged", [])
        items.append(item)
        self.store.set("charged", items[-c.max_items:])

        bump = charge * c.awkwardness_per_charge
        self.state._warm("awkwardness", bump, c.awkwardness_soft_cap)
        if "surprise" in self.state.gauges:
            # prediction error is surprise before it is anything else
            self.state._warm("surprise", charge * c.surprise_per_charge, c.surprise_soft_cap)
        if "unsaid" in self.state.gauges and not speakable:
            # only a thing she cannot raise goes into what is left unsaid; a
            # thing she is merely not raising is a choice she is making
            self.state._warm("unsaid", charge * c.unsaid_per_charge, c.unsaid_soft_cap)
        self.state.save()
        self.store.add_event(ts, self.clock.date_str(), "ick",
                             ("(you could say this and have not) " if speakable else "(you are not going to say this) ") + why,
                             c.event_salience)
        logger.log(f"[ick] {kind}: charge {charge:.0f} via {source} (costs {touched_txt}"
                   + (f"; bears out {fits_txt}" if fits else "")
                   + f"; intimate {intimate:.0f}; circle {circle:.0f} x{cmult:.2f}; novelty {novelty:.2f} after {seen} [{known_kind}"
                   + ("; about her, so it does not habituate" if never and about_her >= c.about_her_top
                      else ("; he said it himself, so it does not habituate" if never else "")) + "]; "
                   f"hidden {hidden:.2f}; state {smult:.2f}) -> awkwardness +{bump:.0f}"
                   + ("" if speakable else " [cannot raise it]"))
        return item

    # ---------------- what she is carrying ----------------

    def _live(self, item, now=None):
        now = now or self.clock.now_ts()
        age_days = max(0.0, (now - item.get("ts", now)) / 86400.0)
        return float(item.get("charge", 0)) * math.exp(-math.log(2) * age_days / self.config.ick.half_life_days)

    def _hot(self):
        c = self.config.ick
        now = self.clock.now_ts()
        out = [(self._live(it, now), it) for it in self.store.get("charged", [])]
        out = [(l, it) for l, it in out if l >= c.carry_floor]
        out.sort(key=lambda x: -x[0])
        return [dict(it, live=round(l, 1)) for l, it in out[: c.in_prompt * 2]]

    def carrying(self):
        """Hot, and she cannot raise it without admitting how she knows."""
        return [it for it in self._hot() if not it.get("speakable")][: self.config.ick.in_prompt]

    def unraised(self):
        """Hot, and she could raise it. She has not, which is a different thing."""
        return [it for it in self._hot() if it.get("speakable")][: self.config.ick.in_prompt]

    def teasable(self):
        """Cooled off, and she has met the sort of thing enough times that it is
        just how he is. This is where a discovery ends up if nothing else
        happens to it: not forgotten, not unspeakable, something to needle him
        about."""
        c = self.config.ick
        now = self.clock.now_ts()
        out = []
        for it in self.store.get("charged", []):
            if self._live(it, now) >= c.carry_floor:
                continue
            k = self._match_kind(it.get("kind", ""))
            if k and int(k.get("seen", 1)) >= c.teasable_after_seen:
                out.append(it)
        return out[-c.teasable_in_prompt:]

    def settled(self):
        """How settled she is with him, 0 to 1: the share of what she has met
        lately whose sort she had already run into.

        Habituation as a state rather than only as a discount. At 1.0 nothing
        he does is news and she can needle him about any of it; at 0.0 every
        look is new. Free to compute, and the threshold the calm stance reads
        (`sim/stances.py`). Over the recent window, and over the whole record
        when the window is too thin to read."""
        c = self.config.ick
        now = self.clock.now_ts()
        all_rows = list(self.store.get("charged", []))
        rows = [it for it in all_rows if (now - float(it.get("ts", 0))) <= float(c.settled_days) * 86400.0]
        if len(rows) < int(c.settled_min):
            rows = all_rows[-int(c.settled_window):]
        if not rows:
            return 0.0
        met = sum(1 for it in rows if int(it.get("seen_before", 0)) >= 1)
        return met / float(len(rows))

    def prompt_text(self):
        from sim.lang import say
        t = say(self.config)
        parts = []
        hot = self.carrying()
        if hot:
            parts.append("\n\n" + t("## Things about him you know and cannot bring up (you went looking and found them; "
                                    "asking would mean admitting that, so they just sit there while you talk to him)",
                                    "## 彼について知っているけれど持ち出せないこと（自分で見にいって見つけたもの。訊けば見たと認めることになるので、"
                                    "話しているあいだもそこに置いたままになっている）")
                         + "\n" + "\n".join(f"- {it['what']}" for it in hot))
        un = self.unraised()
        if un:
            parts.append("\n\n" + t(*sight.w2(self.config, "ick_unsaid_head"))
                         + "\n" + "\n".join(f"- {it['what']}" for it in un))
        tease = self.teasable()
        if tease:
            parts.append("\n\n" + t("## Things about him that stopped being a shock (this is just how he is; you can needle "
                                    "him about it if it comes up, it is not a secret you are keeping any more)",
                                    "## もう驚かなくなった彼のこと（そういう人だというだけ。話に出ればつついてもいい。"
                                    "もう抱えている秘密ではない）")
                         + "\n" + "\n".join(f"- {it['what']}" for it in tease))
        return "".join(parts)

    def bars(self, text):
        """True when this is one of the things she cannot raise. The thread
        pressure has no idea what it is pushing out; left alone it would
        eventually make her say the one thing she never would."""
        for it in self.carrying():
            for field in (it.get("what", ""), it.get("kind", "")):
                if field and _jaccard(field, text) >= self.config.ick.bar_jaccard:
                    return True
        return False

    def report(self):
        now = self.clock.now_ts()
        g = int(self.state.gauges.get("awkwardness", 0))
        items = self.store.get("charged", [])
        lines = [f"awkwardness {g} (baseline {int(self.state._baseline('awkwardness'))})",
                 f"how settled she is with him: {self.settled():.2f} "
                 f"(1.0 = nothing he does is news; 0.0 = every look is new)",
                 f"charged: {len(items)} on record, {len(self.carrying())} she cannot raise, "
                 f"{len(self.unraised())} she could and has not, {len(self.teasable())} teasable"]
        for it in sorted(items, key=lambda x: -self._live(x, now))[:14]:
            t = ", ".join(f"{d['belief']}+{d['strain']:.0f}" for d in it.get("touched", [])) or "-"
            lines.append(f"  {self._live(it, now):5.1f} (was {it.get('charge', 0):5.1f}) {it['date']} "
                         f"[{it.get('source', '?')}{'' if it.get('speakable') else ', sealed'}] "
                         f"[{it.get('kind', '')}] cost: {t} :: {it.get('what', '')[:60]}")
        kinds = sorted(self.kinds(), key=lambda k: -int(k.get("seen", 1)))
        lines.append(f"\nsorts of thing she has run into: {len(kinds)}")
        for k in kinds[:15]:
            lines.append(f"  x{k.get('seen', 1):<3d} {k.get('kind', '')}")
        return "\n".join(lines)
