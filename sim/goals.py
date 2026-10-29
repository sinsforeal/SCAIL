import re
from sim import wiring
import logger
from sim.textutil import words as tokens

# What she is trying to do.
#
# She formed an intention every single morning and nothing ever checked it.
# `outlook.morning` has always produced a `want` and a `dread` -- "to get
# through today without opening the English book, and maybe, if I'm brave,
# send him the melon bun photo I couldn't last night" -- written to kv and read
# by nothing. Meanwhile every person in the cast has a `want` that the beat
# writer reads and acts on. The supporting cast had agendas and she had moods.
#
# So the morning want becomes an object that outlives the morning. It reaches
# the director (she may act on it), the intent model (it is what she is after
# when she reaches for the phone), and her own situation. At the end of the day
# the compile is asked the question nothing was asking: did she do it. A want
# she keeps forming and keeps not doing is carried, and past a few days it
# stops being today's want and becomes a standing one -- which is the
# difference between a mood that recurs and a thing a person is actually
# trying to do.
#
# And then a day that does not go her way has to cost her something, or a
# goal she failed is indistinguishable from one she has not got round to --
# which is exactly what `missed` and `tried` used to be: a line appended to
# the goal's history, the goal left wanting, and nothing else anywhere.
#
# So a want is anchored to something she believes about herself
# (sim/model_of_her.py) in one of two ways. It can rest on one -- she wants
# it because she thinks she is someone who does that -- and then failing
# strains the belief. Or it can test one: she wants it against something she
# has decided about herself, and then failing is that belief being right
# about her, which is how repeated social failure hardens into an identity,
# and getting it is her being surprised by herself.
#
# Giving up falls out of the same numbers. A want survives while it is
# holding one of those up, so what she keeps carrying past all sense and
# what she quietly stops wanting is decided by how much is riding on the
# thing underneath it. Nothing here knows whether she is stubborn; point
# the same code at a different data/self_beliefs.json and it is a different
# girl who gives up at a different point.

# One tokeniser for both languages (`sim/textutil.words`). The regex that
# was here treated a maximal run of kana and kanji as one token, which in a
# language without spaces is a whole clause -- so a Japanese line could not
# be matched by anything, in any language, including a near-identical
# Japanese line. Character bigrams fix that; the English minimum is
# unchanged.
_MIN_LATIN = 4
_HIM = re.compile(r"\bhim\b|\bhe\b|\bhis\b", re.I)


def _words(text):
    return tokens(text, _MIN_LATIN)


def _same(a, b, threshold):
    wa, wb = _words(a), _words(b)
    if not wa or not wb:
        return False
    return len(wa & wb) / len(wa | wb) >= threshold


class Goals:
    WIRES = ('graph',)
    def __init__(self, config, store, clock, state=None):
        self.config = config
        self.store = store
        self.clock = clock
        self.state = state
        wiring.declare(self)

    def all(self):
        return self.store.get("goals", [])

    def save(self, rows):
        self.store.set("goals", rows[-self.config.goals.max_kept:])

    def get(self, gid):
        for g in self.all():
            if g.get("id") == gid:
                return g
        return None

    def open(self):
        """Standing wants, plus today's. Yesterday's unsettled today-goal is not
        open any more; it either got carried this morning or it lapsed."""
        today = self.clock.date_str()
        return [g for g in self.all() if g.get("state") == "wanting"
                and (g.get("horizon") == "standing" or g.get("last_seen_date") == today)]

    # ---------------- the morning ----------------

    def note_morning(self, want, dread, date, anchors=None, self_model=None):
        """What she woke up wanting. The same want two mornings running is one
        want she is carrying, not two.

        `anchors` is what the morning call said each one is riding on: an id
        out of her self-beliefs and whether the want rests on it or tests it.
        The model copies an id back rather than the code matching words,
        which is the lesson from the ick's kinds."""
        c = self.config.goals
        anchors = anchors or {}
        rows = self.all()
        made = []
        for text, kind in ((want, "want"), (dread, "avoid")):
            text = str(text or "").strip()
            if len(text) < c.min_chars:
                continue
            hit = None
            for g in rows:
                if g.get("state") == "wanting" and g.get("kind") == kind and _same(g["text"], text, c.same_jaccard):
                    hit = g
                    break
            anc = self._anchor_for(anchors.get(kind), self_model)
            if hit:
                if not hit.get("anchor") and anc:
                    # it was not anchored when it was formed; anchor it now
                    hit["anchor"], hit["anchor_sign"] = anc
                if hit.get("last_seen_date") == date:
                    # already noted this morning; noting it again is not another day
                    made.append(hit)
                    continue
                hit["carried"] = int(hit.get("carried", 0)) + 1
                hit["last_seen_date"] = date
                if hit["carried"] >= c.carry_to_standing and hit.get("horizon") != "standing":
                    hit["horizon"] = "standing"
                    logger.log(f"[goals] she keeps wanting this, so it is not a today thing any more: {hit['text'][:70]}")
                made.append(hit)
            else:
                g = {"id": f"{date}-{kind}-{len(rows)}", "text": text[:160], "kind": kind,
                     "horizon": "today", "born_date": date, "last_seen_date": date, "carried": 0,
                     "state": "wanting", "about_him": bool(_HIM.search(text)), "history": [],
                     "anchor": anc[0] if anc else "", "anchor_sign": anc[1] if anc else "rests_on",
                     "cost": 0.0}
                rows.append(g)
                made.append(g)
                logger.log(f"[goals] new {kind}: {text[:80]}"                           + (f" (riding on {anc[0]}, {anc[1]})" if anc else ""))
        self.save(rows)
        return made

    def _anchor_for(self, spec, self_model):
        """(belief id, sign) if the morning named one she actually holds."""
        if not (isinstance(spec, dict) and self_model):
            return None
        bid = str(spec.get("belief", "")).strip()
        if not bid or not self_model.get(bid):
            return None
        sign = str(spec.get("sign", "")).strip().lower()
        return (bid, sign if sign in ("rests_on", "tests") else "rests_on")

    # ---------------- what she is after, where it is read ----------------

    def _fmt(self, g, ja=False):
        s = g["text"]
        if g.get("horizon") == "standing":
            n = int(g.get("carried", 0))
            s += (f"（これを望んで目が覚めるのが{n + 1}日続いていて、まだやっていない）" if ja else
                  f" (you have woken up wanting this {n + 1} days running and still not done it)")
        limit = float(g.get("give_up_at", 0) or 0)
        if limit and float(g.get("cost", 0) or 0) >= limit * self.config.goals.tiring_at:
            # not a decision yet; the feeling that comes before one
            s += ("（そして、これは自分には無理かもしれないという感じが出てきている）" if ja else
                  " (and it has started to feel like something you are not going to manage)")
        return s

    def situation_line(self, ja=False):
        rows = self.open()
        if not rows:
            return ""
        wants = [self._fmt(g, ja) for g in rows if g.get("kind") == "want"]
        avoid = [g["text"] for g in rows if g.get("kind") == "avoid"]
        bits = []
        if wants:
            bits.append(("今日やろうとしていること: " if ja else "what you are trying to do: ") + "; ".join(wants))
        if avoid:
            bits.append(("今日それなしで乗り切ろうとしていること: " if ja else
                         "what you are trying to get through the day without: ") + "; ".join(avoid))
        return ". ".join(bits)

    def director_line(self):
        rows = [g for g in self.open() if g.get("kind") == "want"]
        if not rows:
            return ""
        return ("WHAT SHE IS TRYING TO DO (her own, from this morning; let the day give her a chance at it "
                "or take one away, never narrate her deciding to do it): " + "; ".join(self._fmt(g) for g in rows))

    def intent_hint(self):
        """The standing want about him is the one that should be driving her to
        pick up the phone, and it is the one she keeps not acting on."""
        rows = [g for g in self.open() if g.get("kind") == "want" and g.get("about_him")]
        if not rows:
            return ""
        rows.sort(key=lambda g: -int(g.get("carried", 0)))
        return self._fmt(rows[0])

    def brief(self):
        rows = self.open()
        return "; ".join(f"[{g['id']}] {g['text']}" for g in rows) or "(nothing open)"

    # ---------------- the end of the day ----------------

    def settle(self, results, date, self_model=None, self_memory=None):
        """The question nothing was asking, and then the answer costing her
        something. `results` is what the compile made of each open goal,
        strictly from the record."""
        if not results:
            return 0
        c = self.config.goals
        rows = self.all()
        n = 0
        for r in results:
            if not isinstance(r, dict):
                continue
            gid = str(r.get("id", ""))
            outcome = str(r.get("outcome", "")).strip().lower()
            if outcome not in ("got", "tried", "missed", "let_go"):
                continue
            witnessed = bool(r.get("witnessed"))
            note = str(r.get("note", ""))[:140]
            for g in rows:
                if g.get("id") != gid or g.get("state") != "wanting":
                    continue
                g["history"] = (g.get("history", []) + [{"date": date, "outcome": outcome,
                                                         "note": note, "witnessed": witnessed}])[-8:]
                b = self._anchor(g, self_model)
                limit = self.give_up_at(g, self_model)
                g["give_up_at"] = round(limit, 1)
                if outcome == "let_go":
                    # she dropped it rather than failed at it; that is a decision
                    # and it does not go against anything she thinks she is
                    g["state"] = "let_go"
                    logger.log(f"[goals] let go: {g['text'][:70]}" + (f" -- {note[:80]}" if note else ""))
                elif outcome == "got":
                    g["state"] = "got"
                    g["cost"] = 0.0
                    self._charge(g, b, "got", self.cost_of(g, "got", witnessed, b), note, self_model)
                    self._feel("got", witnessed, g)
                    logger.log(f"[goals] got: {g['text'][:70]}" + (f" -- {note[:80]}" if note else ""))
                    self._remember(g, "got", note, date, witnessed, self_memory)
                else:
                    cost = self.cost_of(g, outcome, witnessed, b)
                    g["cost"] = round(float(g.get("cost", 0.0)) + cost, 1)
                    logger.log(f"[goals] {outcome} ({'in front of people, ' if witnessed else ''}"
                               f"cost {cost:.0f}, {g['cost']:.0f} of {limit:.0f} now): {g['text'][:70]}")
                    self._charge(g, b, outcome, cost, note, self_model)
                    self._feel(outcome, witnessed, g)
                    if g["cost"] >= limit:
                        self._give_up(g, b, limit, cost, date, note, self_model, self_memory)
                    else:
                        self._remember(g, outcome, note, date, witnessed, self_memory)
                n += 1
                break
        # a today-goal not re-formed this morning has lapsed: `open()` already
        # reads it that way; the record said `wanting` for ever (21 rows from
        # 08-21 on) and every reader of the raw rows was misled
        for g in rows:
            if (g.get("state") == "wanting" and g.get("horizon") != "standing"
                    and str(g.get("last_seen_date") or "") < str(date)):
                g["state"] = "lapsed"
        self.save(rows)
        return n

    # ---------------- what an outcome costs her ----------------

    def _anchor(self, g, self_model):
        if not (self_model and g.get("anchor")):
            return None
        return self_model.get(g["anchor"])

    def cost_of(self, g, outcome, witnessed, belief=None):
        """What one outcome takes off her. Three terms, none of them a trait:
        how much she had riding on it (what the goal was holding up, and how
        many mornings she has woken up wanting it), whether she actually acted,
        and whether anybody saw.

        A day she let go past is about her. A move that did not land has an
        explanation available and she will take it -- her own sheet says the
        first thing she does with a thing that does not fit is find a reason."""
        c = self.config.goals
        invested = float(belief.get("invested", 50)) if belief else 0.0
        base = (c.fail_base
                + c.fail_per_carried * int(g.get("carried", 0))
                + c.fail_per_invested * invested / 100.0)
        if outcome == "missed":
            base *= c.fail_missed_scale
        elif outcome == "tried":
            base *= c.fail_tried_scale
        if witnessed:
            scale = c.fail_witnessed_scale
            # the audience has a temperature: the same stumble costs more in
            # front of a group that already runs irritated at her than a warm
            # one. heat 0.5 is neutral and leaves the old scale exactly.
            g = self.graph
            if g and c.witnessed_heat_spread:
                scale *= 1.0 + (g.witnessed_heat() - 0.5) * 2 * c.witnessed_heat_spread
            base *= scale
        return round(base, 1)

    def give_up_at(self, g, self_model=None):
        """When she stops wanting it: when what it costs to keep wanting the
        thing passes what the thing is holding up. A want anchored to nothing
        much has a low ceiling and dies quietly; one holding up something she
        has ninety riding on she carries well past sense."""
        c = self.config.goals
        b = self._anchor(g, self_model)
        invested = float(b.get("invested", 50)) if b else 0.0
        return c.give_up_base + c.give_up_per_invested * invested / 100.0

    def _charge(self, g, b, outcome, cost, note, self_model):
        """Put the outcome against the thing the goal was holding up. Which
        direction it goes is the anchor's sign, not the outcome on its own: a
        want that tests a belief about herself is confirmed by failing."""
        if not (b and self_model):
            return
        c = self.config.goals
        tests = g.get("anchor_sign") == "tests"
        why = f"{g['text']}" + (f" -- {note}" if note else "")
        if outcome == "got":
            if tests:
                # she did the thing this said she was not the sort to do
                self_model.strain(b["id"], cost, why)
            else:
                self_model.confirm(b["id"], c.got_fit, why)
        elif tests:
            # it not going her way is this being right about her
            self_model.confirm(b["id"], c.got_fit if outcome == "missed" else c.tried_fit, why)
        else:
            self_model.strain(b["id"], cost, why)

    def _feel(self, outcome, witnessed, g):
        """What it feels like, as opposed to what it costs. A failed goal used
        to charge a belief, write a memory and produce no feeling at all, and a
        goal she got produced nothing either -- so the whole system had a
        downside and no upside. Through _warm, so none of it pins."""
        if not self.state:
            return
        c = self.config.goals
        carried = 1.0 + min(2.0, int(g.get("carried", 0)) * 0.5)
        if outcome == "got":
            self.state._warm("pride", c.pride_on_got * carried, c.pride_soft_cap)
            _st = getattr(self.state, "stress", None)
            if _st:
                _st.relieve("goal_got")
        elif outcome in ("missed", "tried", "given_up"):
            amount = c.sadness_on_give_up if outcome == "given_up" else c.sadness_per_fail
            self.state._warm("sadness", amount * carried, c.sadness_soft_cap)
            if witnessed:
                # in front of people is not the same failure at all
                self.state._warm("shame", c.shame_on_witnessed, c.shame_soft_cap)
        self.state.save()

    def _give_up(self, g, b, limit, cost, date, note, self_model, self_memory):
        """She is not trying for it any more. This is the expensive one: the
        goal was holding something up and it stops.

        What it charges is the last failure again, weighted -- not the whole
        accumulated cost, which the belief has already been strained for one
        failure at a time. Replaying it doubled the bill and revised the
        belief on the spot."""
        c = self.config.goals
        g["state"] = "given_up"
        g["given_up_on"] = date
        logger.log(f"[goals] she is not trying for this any more "
                   f"(cost {g['cost']:.0f} of {limit:.0f}): {g['text'][:70]}")
        if b and self_model:
            why = f"she stopped trying for this: {g['text']}"
            if g.get("anchor_sign") == "tests":
                self_model.confirm(b["id"], c.give_up_fit, why)
            else:
                self_model.strain(b["id"], float(cost) * c.give_up_strain_mult, why)
        self._feel("given_up", False, g)
        # not an event of the day being compiled but of tonight: the day is
        # what happened, this is what she made of it
        self.store.add_event(self.clock.now_ts(), date, "goal",
                             f"(she would not announce it) she has stopped trying for this: {g['text']}",
                             c.event_salience)
        if self_memory and self.config.self_memory.enabled:
            self_memory.add(date, f"She gave up on this one: {g['text']}" + (f" {note}" if note else ""),
                            c.memory_weight_given_up, "flat", source="goals")

    def _remember(self, g, outcome, note, date, witnessed, self_memory):
        """A day that went against her stays with her longer than one that went
        her way, but not every one of them is a memory. Only what she would
        actually still be carrying: something people saw, or something she had
        been waking up wanting for days."""
        c = self.config.goals
        if not (self_memory and self.config.self_memory.enabled and note):
            return
        carried = int(g.get("carried", 0))
        if outcome == "got":
            if carried < c.carry_to_standing:
                return
            weight, feeling = c.memory_weight_got, "relief"
        else:
            if not witnessed and carried < c.carry_to_standing:
                return
            weight, feeling = c.memory_weight_fail, ("small shame" if witnessed else "a bad taste")
        self_memory.add(date, note, weight, feeling, source="goals")

    def report(self):
        rows = self.all()
        op = [g for g in rows if g.get("state") == "wanting"]
        lines = [f"{len(rows)} on record, {len(op)} still wanting "
                 f"({sum(1 for g in op if g.get('horizon') == 'standing')} standing)"]
        for g in sorted(rows, key=lambda g: (g.get("state") != "wanting", -int(g.get("carried", 0)))):
            lines.append(f"\n  [{g['id']}] {g['kind']}/{g['horizon']}  {g['state']}  "
                         f"carried {g.get('carried', 0)}  born {g['born_date']}"
                         + ("  (about him)" if g.get("about_him") else ""))
            if g.get("anchor"):
                lines.append(f"     {'testing' if g.get('anchor_sign') == 'tests' else 'riding on'} "
                             f"{g['anchor']}; cost {float(g.get('cost', 0) or 0):.0f}"
                             + (f" of {float(g['give_up_at']):.0f}" if g.get("give_up_at") else ""))
            lines.append(f"     {g['text']}")
            for h in g.get("history", [])[-4:]:
                lines.append(f"     {h['date']}: {h['outcome']}" + (f" -- {h['note']}" if h.get("note") else ""))
        return "\n".join(lines)
