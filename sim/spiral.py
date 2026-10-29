import logger
from sim import wiring
from sim import sight
from sim import bz

# Anxiety, as a process instead of a level.
#
# The `anxiety` gauge is a number that drifts toward a baseline. A number can
# say how wound up she is and cannot say the thing she cannot stop saying to
# herself, which is what anxiety actually consists of. Nothing in the system
# could hold "Rena said ok and nothing else and you have been going over it for
# three hours".
#
# So a spiral is an object: one small ambiguous detail, and a chain of
# inference that extends itself away from it. Five things make it what it is,
# and all five are human rather than hers:
#
#   1. Being wound up lowers what counts as a signal, so noise gets picked up.
#   2. An ambiguous thing is not allowed to stay ambiguous. It resolves
#      downward, because the bad reading is the one worth preparing for.
#   3. It chains. Each step is individually plausible, which is why she cannot
#      dismiss it.
#   4. Going over it again feels like solving it and is not.
#   5. It feeds itself: each step raises the pitch, and the pitch is what makes
#      the next step likely. This is the one gate in the project that
#      accelerates rather than damping, because that is the thing being
#      modelled. The brakes are opportunity -- being alone with an idle minute,
#      having the energy for it, a daily cap -- never the chain.
#
# What is hers rather than human is entirely in her own numbers, so this file
# names no trait and no person:
#
#   - her propensity is her `anxiety` baseline. Her rest is not neutral:
#     resting at 40 is what being an anxious girl consists of, so the level
#     itself is the propensity and being above rest on top of it accelerates.
#     Measuring only the part above baseline gives zero almost all the time,
#     because a gauge sits at its baseline -- the same shape as the bug that
#     stopped the snoop firing at all, and it stopped this firing at all too.
#   - who can start one comes from the cast meters: how unsettled her standing
#     with that person is, and how much friction is unresolved. Nobody is
#     listed as someone she worries about.
#   - what a chain is pulled toward is one of her self-beliefs, and how far it
#     can run comes from how much she has invested in the one it is heading
#     for. That is the ugly part of anxiety and the part that makes it hers: it
#     is motivated reasoning toward a conclusion she already holds. A girl
#     whose self-beliefs are all lightly held barely spirals, because there is
#     nothing pulling.
#
# It is not prediction error. The ick and the goals are both reality
# disagreeing with her; this is reality never getting a word in. That is why
# reassurance does not resolve one -- it suspends it, and the same seed can go
# again tomorrow, which is exactly what reassurance-seeking does to a person.
# Only the record disconfirming it settles anything, and that is the one route
# by which a belief she has never tested can ever be tested.


class Spirals:
    WIRES = ('graph', 'sentiments',)
    def __init__(self, config, llm, store, clock, state, records=None, self_model=None, self_memory=None):
        self.config = config
        self.llm = llm
        self.store = store
        self.clock = clock
        self.state = state
        self.records = records
        self.self_model = self_model
        self.self_memory = self_memory
        wiring.declare(self)

    # ---------------- access ----------------

    def all(self):
        return self.store.get("spirals", [])

    def save(self, rows):
        self.store.set("spirals", rows[-self.config.spiral.max_kept:])

    def live(self):
        for s in self.all():
            if s.get("state") == "running":
                return s
        return None

    def _count(self):
        return self.store.get("spiral_counts", {}).get(self.clock.date_str(), 0)

    def _note_count(self):
        counts = self.store.get("spiral_counts", {})
        d = self.clock.date_str()
        counts[d] = counts.get(d, 0) + 1
        self.store.set("spiral_counts", {k: v for k, v in counts.items() if k >= d[:8] + "01"})

    # ---------------- how likely she is to be doing this at all ----------------

    def pressure(self):
        """How wound up she is, and how far past her own rest.

        Measured purely as anxiety above baseline this is **zero almost all the
        time**, because a gauge sits at its baseline, and she could never start
        one at all -- the same shape as the bug that stopped the snoop firing
        for two days. Her rest is not neutral: resting at 40 is what being an
        anxious girl consists of, and a girl who rests at 15 has to be provoked
        into it. So the level is the propensity and being above rest on top of
        that accelerates it."""
        c = self.config.spiral
        try:
            base = float(self.config.state.gauges["anxiety"]["baseline"])
        except (KeyError, TypeError, ValueError):
            base = 40.0
        anx = float(self.state.gauges.get("anxiety", base))
        above = max(0.0, (anx - base)) / max(1.0, 100.0 - base)
        return min(c.pressure_cap, (anx / 100.0) * (1.0 + above))

    def seedability(self):
        """Who could start one, and how badly. Not a list of people she worries
        about: how unsettled her standing with each of them is, out of the
        meters the cast already carries. Somebody she is placed well with and
        has nothing outstanding with cannot seed anything."""
        c = self.config.spiral
        best, best_w = None, 0.0
        for name, r in (self.state.relationships or {}).items():
            if name == "him":
                continue
            tension = float(r.get("tension", 0)) / 100.0
            unplaced = max(0.0, (float(c.standing_settled_at) - float(r.get("standing", 50)))) / 100.0
            w = tension * c.tension_weight + unplaced * c.standing_weight
            # somebody she measures herself against can start one too
            try:
                sen = self.sentiments
                if sen:
                    w += sen.live(name, "envy") / 100.0 * c.envy_weight
            except Exception:
                pass
            if w > best_w:
                best, best_w = name, w
        return best, best_w

    def max_steps(self, terminus_invested):
        """How far a chain can run. Not a constant: a chain runs while the
        belief it is heading for is still pulling, so what she has most riding
        on carries her furthest."""
        c = self.config.spiral
        n = int(round(float(terminus_invested) / c.steps_per_invested))
        return max(2, min(c.max_steps_hard, n))

    def due(self, scene):
        """Whether she is going over something right now. Code decides when;
        the call only writes what."""
        c = self.config.spiral
        if not (c.enabled and self.self_model):
            return False, "off", None
        g = self.state.gauges
        if float(g.get("energy", 100)) < c.min_energy:
            return False, "too tired to keep it going", None
        cur = self.live()
        now = self.clock.now_ts()
        if cur and (now - float(cur.get("last_ts", 0))) < c.min_gap_minutes * 60:
            return False, "too soon", None
        if not cur:
            if self._count() >= c.max_per_day:
                return False, "daily cap", None
            if (now - float(self.store.get("spiral_last_ts", 0))) < c.min_gap_minutes * 60:
                return False, "too soon", None
        p = self.pressure()
        if p <= 0:
            return False, "she is at rest", None
        # rumination needs somewhere to happen: a busy scene genuinely stops it,
        # which is why she is fine while she is with them and starts on the train
        occupied = 1.0
        w = ((scene or {}).get("with") or (scene or {}).get("with_who") or "alone").lower()
        if w and w != "alone":
            occupied = c.busy_factor
        if cur:
            steps = len(cur.get("steps", []))
            inv = float(cur.get("terminus_invested", 50))
            if steps >= self.max_steps(inv):
                return False, "it has gone as far as it goes", None
            # the self-feeding term: each step makes the next likelier, scaled
            # by how much she has riding on where it is heading
            prob = (c.extend_base * (1.0 + steps * c.extend_per_step)
                    * (inv / 100.0) * p * occupied * self._stress())
            return (self._roll(prob), f"going over it again (p {prob:.2f}, step {steps + 1})", "extend")
        who, seed_w = self.seedability()
        if seed_w < c.seed_min:
            return False, "nothing unsettled enough to start on", None
        prob = c.start_base * p * seed_w * occupied * self._stress()
        # `who` is what made a spiral likely, not what it will be about: the
        # subject comes back from the model as `about`, and it picks whatever
        # the day actually handed her. Naming `who` here read as a promise
        # the chain does not keep.
        return (self._roll(prob), f"something is unsettled enough to start on "
                f"(p {prob:.2f}, most of it {who})", "start")

    def _stress(self):
        """Stress is the propensity's other half. Anxiety says how readily she
        starts on something; this says how little else she has left to hold it
        off with, and it multiplies both the starting and the extending."""
        st = getattr(self.state, "stress", None)
        return st.multiplier("spiral") if st else 1.0

    def _roll(self, prob):
        import random
        return random.random() < max(0.0, min(1.0, prob))

    # ---------------- the chain ----------------

    def run(self, scene, mode, why):
        cur = self.live()
        c = self.config.spiral
        rels = self.records.cast_sheet(self.state.relationships) if self.records else "(nobody)"
        beliefs = self.self_model.anchor_brief()
        date = self.clock.date_str()
        events = [e for e in self.store.events_for_date(date)][-c.events_shown:]
        ev_txt = "\n".join(f"[{self.clock.hm(e['ts'])}] {e['text']}" for e in events) or "(nothing much)"
        chat = self.store.get("cast_chat", [])[-c.chat_shown:]
        chat_txt = "\n".join(f"{x.get('date', '')} {x.get('who', '')}: {x.get('text', '')[:160]}" for x in chat) or "(nothing said)"
        scene_txt = (f"{(scene or {}).get('location', '')} / {(scene or {}).get('activity', '')} "
                     f"with {(scene or {}).get('with') or (scene or {}).get('with_who') or 'nobody'}") if scene else "(nowhere)"
        user = (
            f"NOW: {self.clock.both()}. She is {scene_txt}.\n"
            f"HOW WOUND UP SHE IS: anxiety {int(self.state.gauges.get('anxiety', 0))} of 100, "
            f"mood {int(self.state.gauges.get('mood', 0))}, energy {int(self.state.gauges.get('energy', 0))}\n\n"
            f"THE PEOPLE, AND HOW SHE IS PLACED WITH THEM:\n{rels}\n\n"
            f"WHAT SHE HAS DECIDED ABOUT HERSELF (a chain ends at one of these; copy the id back exactly):\n{beliefs}\n\n"
            f"TODAY, AS IT HAPPENED:\n{ev_txt}\n\n"
            f"WHAT WAS ACTUALLY SAID TO HER LATELY:\n{chat_txt}\n"
        )
        if mode == "extend" and cur:
            steps = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(cur.get("steps", [])))
            user += (f"\nSHE IS ALREADY GOING OVER THIS.\nIT STARTED WITH: {cur['seed']}\n"
                     f"WHERE IT HAS GOT TO:\n{steps}\n"
                     f"WHERE IT IS HEADED: {cur.get('terminus_text', '')}\n"
                     f"IT CAN RUN {self.max_steps(cur.get('terminus_invested', 50)) - len(cur.get('steps', []))} MORE STEP(S) AT MOST.\n")
        else:
            user += "\nSHE IS NOT GOING OVER ANYTHING YET. FIND THE SMALL AMBIGUOUS THING AND TAKE THE FIRST STEP.\n"
        messages = [{"role": "system", "content": self.config.role_system("spiral")},
                    {"role": "user", "content": user}]
        data, raw = self.llm.call_json("spiral", messages)
        if not isinstance(data, dict):
            logger.log("[spiral] nothing came back")
            return None
        step = str(data.get("step", "")).strip()
        if not step:
            logger.log("[spiral] she did not take it any further")
            return None
        rows = self.all()
        now = self.clock.now_ts()
        if mode == "extend" and cur:
            for s in rows:
                if s.get("id") != cur["id"]:
                    continue
                s["steps"] = s.get("steps", []) + [step[:220]]
                s["last_ts"] = now
                s["pitch"] = min(100, int(s.get("pitch", 0)) + c.pitch_per_step)
                arrived = bool(data.get("arrived")) or len(s["steps"]) >= self.max_steps(s.get("terminus_invested", 50))
                if arrived:
                    s["state"] = "arrived"
                    s["arrived_on"] = self.clock.date_str()
                self._pay(arrived)
                self.save(rows)
                logger.log(f"[spiral] step {len(s['steps'])}: {step[:110]}")
                if arrived:
                    logger.log(f"[spiral] and there it is -- it has arrived at \"{s.get('terminus_text', '')[:70]}\"")
                    self.store.add_event(now, self.clock.date_str(), "spiral",
                                         ("[inferred] " if bz.reality_on(self.config) else "") + f"(she has not said any of this) she has talked herself all the way to it: {step[:160]}",
                                         c.event_salience)
                return s
            return None
        tid = str(data.get("terminus", "")).strip()
        tb = self.self_model.get(tid)
        if not tb:
            logger.log(f"[spiral] it was not heading anywhere she believes ({tid!r})")
            return None
        s = {"id": f"{self.clock.date_str()}-{len(rows)}",
             "seed": str(data.get("seed", ""))[:200],
             "about": str(data.get("about", ""))[:60],
             "steps": [step[:220]],
             "terminus": tid, "terminus_text": tb["text"], "terminus_invested": int(tb.get("invested", 50)),
             "state": "running", "pitch": c.pitch_per_step,
             "born_ts": now, "last_ts": now, "date": self.clock.date_str(), **({"reality": "inferred"} if bz.reality_on(self.config) else {})}
        rows.append(s)
        self.save(rows)
        self.store.set("spiral_last_ts", now)
        self._note_count()
        self._pay(False)
        logger.log(f"[spiral] it has started on {s['about'] or 'something'}: {s['seed'][:90]}")
        logger.log(f"[spiral]   1. {step[:110]}  (heading for {tid}, up to {self.max_steps(s['terminus_invested'])} steps)")
        return s

    def _pay(self, arrived):
        """What going over it costs her. Through _warm, so the gauge saturates
        gracefully while the thought carries on getting worse -- those are two
        different curves and it is right that they come apart. Mood is left to
        the state model off the event, rather than pushed down through the
        baseline by hand."""
        c = self.config.spiral
        self.state._warm("anxiety", c.arrived_anxiety if arrived else c.anxiety_per_step, c.anxiety_soft_cap)
        self.state.save()

    # ---------------- what ends one ----------------

    def suspend_for_him(self):
        """He answered. She feels better and nothing has been settled: the chain
        is suspended, not resolved, and the same seed can go again tomorrow.
        That is not a shortcut -- reassurance is what keeps anxiety alive in
        people, precisely because it heads off the test."""
        c = self.config.spiral
        rows = self.all()
        n, touched = 0, 0
        for s in rows:
            if s.get("state") not in ("running", "arrived"):
                continue
            touched += 1
            if s.get("state") == "running":
                s["state"] = "suspended"
                s["suspended_on"] = self.clock.date_str()
                n += 1
            # a chain that already arrived is not suspended by him saying
            # something -- she has the conclusion now -- but it does stop
            # hurting for a while, which is the whole trap
        if touched:
            self.save(rows)
            self.state._settle("anxiety", c.reassurance_relief)
            self.state._warm("relief", c.reassurance_relief, 70)
            self.state.save()
            logger.log(f"[spiral] he said something and it stopped hurting for a bit "
                       f"(nothing settled; {n} suspended, {touched - n} already arrived)")
        return touched

    def fade_old(self):
        """It dies of neglect. Most of them do."""
        c = self.config.spiral
        rows = self.all()
        now = self.clock.now_ts()
        n = 0
        for s in rows:
            if s.get("state") not in ("running", "suspended"):
                continue
            if (now - float(s.get("last_ts", now))) >= c.fade_hours * 3600:
                s["state"] = "faded"
                n += 1
        if n:
            self.save(rows)
            logger.log(f"[spiral] {n} thing(s) she was going over stopped mattering")
        return n

    def resume(self):
        """A suspended chain can pick up again. It is the same seed; nothing
        about it was answered."""
        rows = self.all()
        for s in rows:
            if s.get("state") == "suspended":
                s["state"] = "running"
                s["last_ts"] = self.clock.now_ts()
                self.save(rows)
                logger.log(f"[spiral] it came back: {s['seed'][:80]}")
                return s
        return None

    # ---------------- the record having the last word ----------------

    def settle(self, date):
        """The only thing that resolves one. At the compile, the chains that
        got somewhere are put against what actually happened. This is the route
        by which a belief she has never once tested can be tested: a chain
        arrives at it, and then the day either bears it out or does not."""
        c = self.config.spiral
        if not (c.enabled and self.self_model):
            return 0
        rows = self.all()
        due = [s for s in rows if s.get("state") in ("arrived", "running", "suspended")
               and s.get("date") == date and len(s.get("steps", [])) >= c.settle_min_steps]
        if not due:
            return 0
        day = self.store.recent_days(1)
        narrative = day[0]["narrative"] if day and day[0]["date"] == date else ""
        events = self.store.events_for_date(date)
        ev_txt = "\n".join(f"[{self.clock.hm(e['ts'])}] {e['text']}" for e in events) or "(nothing)"
        chat = [x for x in self.store.get("cast_chat", []) if x.get("date") == date]
        chat_txt = "\n".join(f"{x.get('who', '')}: {x.get('text', '')[:160]}" for x in chat) or "(nothing said)"
        n = 0
        for s in due:
            steps = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(s.get("steps", [])))
            user = (
                f"WHAT SET HER OFF: {s['seed']}\n"
                f"WHO IT WAS ABOUT: {s.get('about') or 'nobody in particular'}\n"
                f"WHERE SHE TOOK IT:\n{steps}\n"
                f"WHAT SHE TALKED HERSELF INTO: {s.get('terminus_text', '')}\n\n"
                f"WHAT ACTUALLY HAPPENED THAT DAY:\n{narrative[:2500] or '(not compiled)'}\n\n"
                f"THE DAY'S EVENTS:\n{ev_txt}\n\nWHAT WAS SAID TO HER:\n{chat_txt}\n\n"
                f"WHAT SHE HAS DECIDED ABOUT HERSELF:\n{self.self_model.anchor_brief()}\n"
                # the graph is the ground truth her chain guessed at: "Rena is
                # done with me" can now be put against what Rena actually
                # holds, which is what turns social anxiety into a testable
                # prediction rather than a self-sealing loop
                + (f"\nWHAT THE PEOPLE AROUND HER ACTUALLY THINK OF HER (the world's record, never hers to see):\n{self.graph.tomoe_lines()}\n"
                   if self.graph else "")
            )
            messages = [{"role": "system", "content": self.config.prompt_text("spiral_settle")},
                        {"role": "user", "content": user}]
            data, raw = self.llm.call_json("spiral_settle", messages)
            if not isinstance(data, dict):
                continue
            outcome = str(data.get("outcome", "")).strip().lower()
            note = str(data.get("note", ""))[:160]
            if outcome not in ("happened", "did_not"):
                logger.log(f"[spiral] still open, nothing settled it: {s['seed'][:70]}")
                continue
            for row in rows:
                if row.get("id") != s["id"]:
                    continue
                row["state"] = "borne_out" if outcome == "happened" else "disconfirmed"
                row["settled_on"] = date
                row["settle_note"] = note
            if outcome == "happened":
                self.self_model.confirm(s["terminus"], c.borne_out_fit,
                                        f"she saw it coming: {note or s.get('terminus_text', '')}")
                logger.log(f"[spiral] she was right, and that is worse: {s['seed'][:70]}")
            else:
                self.self_model.strain(s["terminus"], c.disconfirm_strain,
                                       f"she talked herself into this and none of it happened: {note or s['seed']}")
                self.state._warm("relief", c.disconfirm_relief, 75)
                logger.log(f"[spiral] none of it happened: {s['seed'][:70]}")
                # and being wrong about a room bears on whatever she believes
                # about being able to read one -- named by the call, never here,
                # because that belief is this girl's and not every girl's
                for t in (data.get("also_touches") or [])[: c.max_also_touches]:
                    if not isinstance(t, dict):
                        continue
                    bid = str(t.get("id", "")).strip()
                    if not bid or bid == s["terminus"] or not self.self_model.get(bid):
                        continue
                    try:
                        w = max(0.0, min(5.0, float(t.get("weight", 0))))
                    except (TypeError, ValueError):
                        continue
                    if w > 0:
                        self.self_model.strain(bid, (w / 5.0) * c.disconfirm_strain,
                                               str(t.get("note", ""))[:160])
            if self.self_memory and self.config.self_memory.enabled and note:
                self.self_memory.add(date, note, c.memory_weight,
                                     "sick with it" if outcome == "happened" else "worn out over nothing", source="spiral")
            n += 1
        self.save(rows)
        return n

    # ---------------- where it shows up ----------------

    def prompt_text(self):
        c = self.config.spiral
        rows = [s for s in self.all() if s.get("state") in ("running", "arrived", "suspended")]
        if not rows:
            return ""
        rows.sort(key=lambda s: -float(s.get("last_ts", 0)))
        lines = []
        for s in rows[: c.in_prompt]:
            chain = " ".join(t.rstrip(".") + "." for t in s.get("steps", []) if t)
            hours = max(0.0, (self.clock.now_ts() - float(s.get("born_ts", 0))) / 3600.0)
            how_long = f" You have been at this about {int(hours)} hour(s)." if hours >= 1 else ""
            tail = ""
            if s.get("state") == "arrived":
                tail = " You have got all the way to the end of it and you cannot get back."
            elif s.get("state") == "suspended":
                tail = " It went quiet for a bit. It has not been answered."
            seed = s["seed"].rstrip(".") + "."
            _lab = (bz.label_phrase(s["reality"], False) + " ") if s.get("reality") and bz.reality_on(self.config) else ""
            lines.append(f"- {_lab}It started with: {seed} {chain}{how_long}{tail}")
        from sim.lang import say
        return ("\n\n" + say(self.config)(
            "## What you have been going over (nobody has said any of this to you; "
            "you worked it out yourself, and you are certain you are right)",
            "## ずっと頭の中で回していること（誰かに言われたことではない。自分で組み立てたもので、"
            "自分では間違いないと思っている）") + "\n" + "\n".join(lines))

    def director_line(self):
        s = self.live() or next((x for x in self.all() if x.get("state") == "arrived"), None)
        if not s:
            return ""
        return ("WHAT SHE IS CHEWING ON (she will not raise it and it is taking up room; let it show in what she "
                f"{sight.w(self.config, 'spiral_hands')}, never as her explaining it): {s['seed']} {' '.join(s.get('steps', [])[-2:])}")

    def mood_tag(self):
        s = self.live() or next((x for x in self.all() if x.get("state") == "arrived"), None)
        if not s:
            return ""
        if s.get("state") == "arrived":
            return "has talked herself into something and cannot get back out of it"
        return "stuck on something somebody said, going round on it"

    def impulse_bonus(self):
        """The social term the impulse never had. An afternoon that went badly
        with them is exactly when a girl like her picks up her phone to him."""
        c = self.config.spiral
        s = self.live() or next((x for x in self.all() if x.get("state") == "arrived"), None)
        if not s:
            return 0.0
        return c.impulse_weight * (float(s.get("pitch", 0)) / 100.0) * 100.0

    def report(self):
        rows = self.all()
        who, w = self.seedability()
        lines = [f"anxiety {int(self.state.gauges.get('anxiety', 0))}, pressure {self.pressure():.2f}; "
                 f"most unsettled with {who or '(nobody)'} ({w:.2f} of {self.config.spiral.seed_min} needed); "
                 f"{self._count()} today of {self.config.spiral.max_per_day}"]
        for s in rows[-12:]:
            lines.append(f"\n  [{s['id']}] {s.get('state')}  about {s.get('about') or '-'}  "
                         f"pitch {s.get('pitch', 0)}  -> {s.get('terminus')} (invested {s.get('terminus_invested')}, "
                         f"up to {self.max_steps(s.get('terminus_invested', 50))} steps)")
            lines.append(f"     seed: {s.get('seed', '')}")
            for i, t in enumerate(s.get("steps", [])):
                lines.append(f"     {i + 1}. {t}")
            if s.get("settle_note"):
                lines.append(f"     settled: {s['settle_note']}")
        return "\n".join(lines)
