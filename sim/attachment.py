import random

import logger
from sim import sight
from sim.episodes import EpisodeLog

# Attachment behaviour under threat: protest or deactivation, and the switch
# between them.
#
# Before this the only thing that made her reach out LESS was one hard
# threshold on tension (`impulse.withdraw_silent_from`), and everything else
# was a sum of loneliness and craving. A person whose attachment is under
# threat does not sit on a scale between "text more" and "text less". They
# run one of two strategies and swap:
#
#   protest      pursue harder. Test him, poke, ask, escalate, count the
#                minutes. The bet is that pushing brings him back.
#   deactivate   go cold. Get busy, answer in the fewest words, need
#                nothing, do not chase. The bet is that not wanting it
#                protects her from not getting it.
#
# and the swap is the recognisable part: a girl who has gone cold for six
# hours and then sends four messages at 1am is not two states of one score,
# she is a strategy that failed and the one under it breaking through.
#
# Code owns all of it. Threat is read off the record (his silence against
# what she expects of this hour, read-and-left, tension, a rupture, scars).
# Which strategy she picks is scored from what she believes about herself
# (`data/self_beliefs.json`, by id -- `not_come_looking` says nobody comes
# looking so do not wait to find out; `wont_stay_quiet` says push), from
# the meters and the sentiments, from the gauges, and from what the last
# episodes got her -- a protest he answered teaches protest, one he did
# not teaches going cold. The draw is weighted, never argmax, so the same
# day is not always the same girl. No model decides any of this; the roles
# that already write her (intent, persona, director) are told the stance
# and say what it looks like.
#
# Readers, because a strategy nothing reads is a tag: the impulse (score
# and the unanswered-streak stop), withholding pressure, delay_factor,
# register, the shape draw, the intent's carrying line, the persona's
# situation, the director. And it settles: the strategies are bets on
# beliefs, so the episode's end tests those beliefs -- that is the only
# route by which `not_come_looking` (evidence 30) ever gets evidence.

PROTEST, DEACTIVATE = "protest", "deactivate"


class Attachment(EpisodeLog):
    LOG_KEY = "attachment_log"
    def __init__(self, config, store, clock, state, sentiments=None, ruptures=None,
                 receipts=None, rhythm=None, self_model=None, self_memory=None, impulse=None):
        self.config = config
        self.store = store
        self.clock = clock
        self.state = state
        self.sentiments = sentiments
        self.ruptures = ruptures
        self.receipts = receipts
        self.rhythm = rhythm
        self.self_model = self_model
        self.self_memory = self_memory
        self.impulse = impulse
        self._above_since = None      # when threat first crossed engage_from
        self.last_threat = 0.0

    # ---------------- the object ----------------

    def live(self):
        row = self.store.get("attachment")
        return row if row and not row.get("done") else None

    def strategy(self):
        r = self.live()
        return r["strategy"] if r else ""

    def _save(self, row):
        self.store.set("attachment", row)

    def _him(self):
        return self.state.relationships.get(self.state._him_key() or "him", {}) or {}

    # ---------------- threat ----------------

    def threat(self, silent_hours):
        """0..1: how much the bond reads as under threat right now.

        Every term is about him and her, and the whole thing is scaled by
        attachment -- a person you are not attached to cannot threaten you
        by going quiet, which is why a stranger's silence is just silence."""
        c = self.config.attachment
        t = 0.0
        # his silence against what she expects of THIS hour. Four months say
        # he is never about at some hour of his day; that is not being ignored.
        usual = 0.5
        try:
            if self.rhythm:
                usual = float(self.rhythm.usual_now())
        except Exception:
            pass
        hours = max(0.0, float(silent_hours))
        if hours >= c.silence_from_hours:
            over = min(1.0, (hours - c.silence_from_hours) / max(1.0, c.silence_full_hours - c.silence_from_hours))
            t += over * (c.silence_floor + (1.0 - c.silence_floor) * usual) * c.w_silence
        # read and left: the sharpest version of the same thing
        try:
            st = self.receipts.status() if self.receipts else None
            if st and st.get("state") == "read" and st.get("read_ts"):
                mins = (self.clock.now_ts() - float(st["read_ts"])) / 60.0
                if mins >= c.read_left_minutes:
                    t += c.w_read_left
        except Exception:
            pass
        him = self._him()
        tension = float(him.get("tension", 0) or 0)
        if tension > c.tension_from:
            t += (tension - c.tension_from) / max(1.0, 100.0 - c.tension_from) * c.w_tension
        try:
            r = self.ruptures.open_one() if self.ruptures else None
            if r:
                t += c.w_rupture * (1.0 if r.get("whose") in ("his", "both") else c.rupture_hers_factor)
            if self.ruptures:
                recent = [s for s in self.ruptures.scars()
                          if (self.clock.now_ts() - float(s.get("ts", 0))) / 86400.0 <= c.scar_days]
                t += min(c.w_scars_cap, len(recent) * c.w_scar)
        except Exception:
            pass
        # she reached out and got nothing, more than once
        try:
            if self.impulse:
                streak = self.impulse.unanswered_streak()
                if streak:
                    t += min(c.w_streak_cap, streak * c.w_streak)
        except Exception:
            pass
        scale = 1.0
        try:
            if self.sentiments:
                a = self.sentiments.live(self.state._him_key() or "him", "attachment")
                scale = c.attachment_floor + (1.0 - c.attachment_floor) * a / float(self.config.sentiment.ceiling)
        except Exception:
            pass
        self.last_threat = max(0.0, min(1.0, t * scale))
        return self.last_threat

    # ---------------- selection ----------------

    def _belief_pull(self):
        """Signed: + protest, - deactivate. Each belief pulls by what it says,
        weighted by how much she has seen it borne out, and discounted while
        it is under strain -- a belief she is currently finding reasons for is
        not one she acts from with her whole weight."""
        c = self.config.attachment
        if not self.self_model:
            return 0.0, []
        pulls = dict(self.config.raw.get("attachment", {}).get("belief_pulls", {}))
        out, parts = 0.0, []
        now = self.clock.now_ts()
        try:
            rows = self.self_model.beliefs()
        except Exception:
            return 0.0, []
        for b in rows:
            w = pulls.get(b.get("id"))
            if not w or b.get("state") == "let_go":
                continue
            ev = float(b.get("evidence", 0)) / 100.0
            strain = 0.0
            try:
                strain = min(1.0, self.self_model.live_strain(b, now) / max(1.0, self.self_model.revise_at(b)))
            except Exception:
                pass
            v = float(w) * (c.belief_floor + (1.0 - c.belief_floor) * ev) * (1.0 - c.strain_discount * strain)
            out += v
            parts.append(f"{b.get('id')} {v:+.2f}")
        return out, parts

    def _history_pull(self):
        """What the last episodes taught her. A strategy that worked is the
        one she reaches for; one that failed she reaches for less. This is
        the only memory the mechanism has and it is the point of it."""
        c = self.config.attachment
        out = 0.0
        now = self.clock.now_ts()
        for r in self._log()[-c.history_episodes:]:
            days = (now - float(r.get("ended_ts", r.get("ts", now)))) / 86400.0
            fade = 0.5 ** (days / max(1.0, c.history_half_life_days))
            last = r.get("strategy", "")
            worked = r.get("outcome") == "resolved"
            if last == PROTEST:
                out += (c.history_weight if worked else -c.history_weight) * fade
            elif last == DEACTIVATE:
                # he came to her while she was cold: going cold works
                out += (-c.history_weight if worked else c.history_weight * 0.5) * fade
        return out

    def scores(self):
        """(protest, deactivate, notes). Both are positive quantities; the
        signed pulls split between them."""
        c = self.config.attachment
        g = self.state.gauges
        him = self._him()
        notes = []
        signed = 0.0
        bp, parts = self._belief_pull()
        signed += bp
        notes.append("beliefs " + (", ".join(parts) or "-"))
        hp = self._history_pull()
        signed += hp
        notes.append(f"history {hp:+.2f}")
        # worth fighting for pushes toward pursuit; a wall of tension toward cold
        closeness = float(him.get("closeness", 50) or 50)
        tension = float(him.get("tension", 0) or 0)
        m = (closeness - 50.0) / 50.0 * c.w_closeness - tension / 100.0 * c.w_tension_select
        signed += m
        notes.append(f"meters {m:+.2f}")
        s = 0.0
        try:
            if self.sentiments:
                k = self.state._him_key() or "him"
                ceil = float(self.config.sentiment.ceiling)
                s = (self.sentiments.live(k, "attachment") / ceil * c.w_attachment
                     - self.sentiments.live(k, "resentment") / ceil * c.w_resentment)
        except Exception:
            pass
        signed += s
        notes.append(f"sentiment {s:+.2f}")
        # the gauges, over baseline only: anxious and angry pursue, ashamed and sad go cold
        gv = 0.0
        for gauge, w in (("anxiety", c.w_anxiety), ("anger", c.w_anger),
                         ("shame", -c.w_shame), ("sadness", -c.w_sadness)):
            over = max(0.0, self.state.over_rest(gauge)) / 100.0
            gv += over * w
        signed += gv
        notes.append(f"gauges {gv:+.2f}")
        p = c.base + max(0.0, signed)
        d = c.base + max(0.0, -signed)
        return p, d, notes

    def _pick(self, rng):
        p, d, notes = self.scores()
        total = max(1e-6, p + d)
        choice = PROTEST if rng.random() < p / total else DEACTIVATE
        return choice, p, d, notes

    # ---------------- the loop ----------------

    def tick(self, silent_hours):
        """Every pass. Opens an episode when threat holds, switches strategy
        when the running one has failed, and closes on burn-out."""
        c = self.config.attachment
        if not c.enabled:
            return
        t = self.threat(silent_hours)
        now = self.clock.now_ts()
        row = self.live()
        if not row:
            if t >= c.engage_from:
                if self._above_since is None:
                    self._above_since = now
                if (now - self._above_since) / 60.0 >= c.engage_minutes:
                    self._open(t)
            else:
                self._above_since = None
            return
        row["threat"] = round(t, 2)
        row["peak_threat"] = round(max(float(row.get("peak_threat", 0)), t), 2)
        hours = (now - float(row["ts"])) / 3600.0
        if hours >= c.max_hours:
            self._close(row, "burnt_out")
            return
        since = (now - float(row.get("since_ts", row["ts"]))) / 3600.0
        # How long the push has brought nothing: the quiet is measured from the
        # later of the strategy starting and his last message, because a push he
        # has answered inside the window has not gone unanswered. He wrote ninety
        # minutes into a five-hour push on 2026-09-06 and the switch still read the
        # whole five hours as silence.
        quiet = (now - max(float(row.get("since_ts", row["ts"])),
                           float(row.get("last_his_ts") or 0))) / 3600.0
        rng = random.Random(int(now // 600))
        if row["strategy"] == PROTEST:
            # pushing that has brought nothing turns cold: after the hours,
            # or when the streak stop shuts her down, or when she is too
            # ashamed of having pushed
            streak = 0
            try:
                streak = self.impulse.unanswered_streak() if self.impulse else 0
            except Exception:
                pass
            why = ""
            if quiet >= c.protest_exhaust_hours:
                why = (f"pushed for {since:.1f}h and nothing came back"
                       if quiet >= since - 0.05 else
                       f"pushed for {since:.1f}h and nothing back for {quiet:.1f}h "
                       f"since he last wrote")
            elif streak >= c.protest_streak_stop:
                why = f"{streak} unanswered in a row"
            elif self.state.gauges.get("shame", 0) >= c.shame_switch:
                why = "ashamed of how much she has been pushing"
            if why and len(row.get("switches", [])) < c.max_switches:
                self._switch(row, DEACTIVATE, why)
        else:
            # cold that cannot be kept up: longing or craving climbing while
            # she is not asking for anything, and the longer it has held the
            # likelier it breaks
            g = self.state.gauges
            need = max(float(g.get("longing", 0)), float(g.get("validation_craving", 0)))
            if since >= c.rebound_min_hours and need >= c.rebound_from and len(row.get("switches", [])) < c.max_switches:
                p = min(c.rebound_p_cap, c.rebound_p_base + (since - c.rebound_min_hours) * c.rebound_p_per_hour
                        + (need - c.rebound_from) / 100.0 * c.rebound_p_per_need)
                if rng.random() < p:
                    self._switch(row, PROTEST, f"held cold {since:.1f}h and it broke (need {need:.0f})")
                else:
                    row["rebound_p"] = round(p, 2)
        self._save(row)

    def _open(self, t):
        c = self.config.attachment
        now = self.clock.now_ts()
        rng = random.Random(int(now // 600))
        strategy, p, d, notes = self._pick(rng)
        row = {"ts": now, "date": self.clock.date_str(), "since_ts": now, "strategy": strategy,
               "first": strategy, "threat": round(t, 2), "peak_threat": round(t, 2),
               "scores": {"protest": round(p, 2), "deactivate": round(d, 2)},
               "notes": notes, "switches": [], "done": False}
        self._save(row)
        self._above_since = None
        self.store.add_event(now, self.clock.date_str(), "attachment",
                             ("she has started pushing at him: checking, asking, counting the minutes" if strategy == PROTEST
                              else "she has gone cold on him on purpose: busy, brief, needing nothing"), c.event_salience)
        logger.log(f"[attach] {strategy} (threat {t:.2f}; protest {p:.2f} vs deactivate {d:.2f}; {'; '.join(notes)})")

    def _switch(self, row, to, why):
        c = self.config.attachment
        now = self.clock.now_ts()
        row["switches"].append({"ts": now, "from": row["strategy"], "to": to, "why": why[:120]})
        row["strategy"] = to
        row["since_ts"] = now
        # a swap costs: giving up pushing is a small defeat; breaking one's
        # own cold front is a humiliation, and she knows it
        if to == DEACTIVATE:
            self.state._warm("sadness", c.sadness_on_give_up, c.soft_cap)
        else:
            self.state._warm("shame", c.shame_on_break, c.soft_cap)
        self.state.save()
        self.store.add_event(now, self.clock.date_str(), "attachment",
                             ("she has stopped pushing and gone cold instead" if to == DEACTIVATE
                              else "the cold front broke: she is reaching for him again and hates that she is"),
                             c.event_salience)
        logger.log(f"[attach] switch {row['switches'][-1]['from']} -> {to}: {why}")

    def note_test(self, kind, test):
        """What she is checking him for, from the intent call, on the record
        of the episode: the tests are what a protest is made of."""
        row = self.live()
        if not row or row.get("strategy") != PROTEST:
            return
        row.setdefault("tests", []).append({"ts": self.clock.now_ts(), "kind": kind, "test": test[:160]})
        row["tests"] = row["tests"][-8:]
        self._save(row)
        logger.log(f"[attach] test ({kind}): {test[:100]}")

    def observable_line(self, in_person):
        """What a person near her could SEE of the stance -- never the
        stance itself, which is hers. Face to face it is the phone; over
        LINE it is the timing of her replies."""
        s = self.strategy()
        if not s:
            return ""
        name = self.config.character.name
        if in_person:
            return sight.w(self.config, "attach_protest_in_person" if s == PROTEST else "attach_deactivate_in_person", name=name)
        return (f"{name}'s replies today have been quick and there have been a lot of them"
                if s == PROTEST else
                f"{name}'s replies today have been short and slow, like she is busy with something")

    # ---------------- what ends it ----------------

    def his_message(self, text=""):
        """He said something. A message is not a resolution by itself -- one
        curt line into a protest does not end it -- but it is the only thing
        that can, the count is what the settle reads, and the stamp is where
        the exhaustion measures its quiet from: five hours of pushing with an
        answer in the middle of them is not five hours of nothing back."""
        c = self.config.attachment
        row = self.live()
        if not row:
            return
        row["his_messages"] = int(row.get("his_messages", 0)) + 1
        row["last_his_ts"] = self.clock.now_ts()
        self._save(row)

    def maybe_resolve(self, silent_hours):
        """After his message has been read into the state: the threat has to
        have actually gone, not just been interrupted."""
        c = self.config.attachment
        row = self.live()
        if not row or not row.get("his_messages"):
            return
        t = self.threat(silent_hours)
        # under the floor, or well down from where it peaked: a standing
        # tension with him keeps the figure off zero and must not keep an
        # answered episode open for ever
        if t <= c.release_below or t <= float(row.get("peak_threat", 1.0)) * c.release_fraction:
            self._close(row, "resolved")

    def _close(self, row, outcome):
        c = self.config.attachment
        now = self.clock.now_ts()
        row["done"] = True
        row["outcome"] = outcome
        row["ended_ts"] = now
        row["hours"] = round((now - float(row["ts"])) / 3600.0, 1)
        self._save(row)
        log = self._log()
        log.append(dict(row))
        self.store.set("attachment_log", log[-c.keep:])
        self._settle_beliefs(row)
        strat, first = row["strategy"], row.get("first", row["strategy"])
        swaps = len(row.get("switches", []))
        if outcome == "resolved":
            text = ("he came back while she was pushing" if strat == PROTEST else "he came to her while she was being cold")
            feel, val = ("relieved, and a bit embarrassed about the pushing" if strat == PROTEST
                         else "vindicated, and not sure she likes what that says"), 1
        else:
            text = ("she pushed and nothing came" if strat == PROTEST else "she went cold and he let her")
            feel, val = "flat", -2
            if self.sentiments:
                self.sentiments.move(self.state._him_key() or "him", "resentment", c.resentment_on_burnout,
                                     f"{strat} got nothing")
        if swaps:
            text += f", after swapping tack {swaps} time{'s' if swaps != 1 else ''}"
        self.store.add_event(now, self.clock.date_str(), "attachment", text, c.event_salience)
        if self.self_memory and self.config.self_memory.enabled:
            self.self_memory.add(self.clock.date_str(), text[0].upper() + text[1:] + ".", c.memory_weight, feel, valence=val, source="attachment")
        logger.log(f"[attach] {outcome} after {row['hours']}h as {strat} (first {first}, {swaps} switch(es), "
                   f"his messages {row.get('his_messages', 0)}, peak threat {row.get('peak_threat')})")

    def _settle_beliefs(self, row):
        """The strategies are bets on beliefs, so the end of an episode is
        evidence about them. Each strategy names, in config, which belief a
        resolved episode strains and which a failed one confirms; a
        rebound (cold that broke) strains the belief that the mask holds."""
        if not self.self_model:
            return
        c = self.config.attachment
        raw = self.config.raw.get("attachment", {})
        table = raw.get("belief_tests", {}).get(row["strategy"], {})
        key = "resolved" if row.get("outcome") == "resolved" else "failed"
        for bid, amount in (table.get(key) or {}).items():
            try:
                if float(amount) < 0:
                    self.self_model.strain(bid, abs(float(amount)), f"attachment: {row['strategy']} {key}")
                else:
                    self.self_model.confirm(bid, float(amount), f"attachment: {row['strategy']} {key}")
            except Exception as e:
                logger.log(f"[attach] belief {bid} not settled: {type(e).__name__}: {e}")
        broke = [s for s in row.get("switches", []) if s.get("to") == PROTEST]
        if broke:
            for bid, amount in (raw.get("belief_tests", {}).get("rebound") or {}).items():
                try:
                    self.self_model.strain(bid, abs(float(amount)) * len(broke), "attachment: the cold front broke")
                except Exception as e:
                    logger.log(f"[attach] belief {bid} not settled: {type(e).__name__}: {e}")

    # ---------------- readers ----------------

    def impulse_bonus(self):
        c = self.config.attachment
        s = self.strategy()
        if s == PROTEST:
            return c.impulse_protest
        if s == DEACTIVATE:
            return -c.impulse_deactivate
        return 0.0

    def extra_streak(self):
        """Protest keeps pushing past the point a calm girl stops."""
        return self.config.attachment.protest_extra_streak if self.strategy() == PROTEST else 0

    def withhold_pressure(self):
        return self.config.attachment.withhold_deactivate if self.strategy() == DEACTIVATE else 0.0

    def delay_multiplier(self):
        c = self.config.attachment
        s = self.strategy()
        if s == PROTEST:
            return c.delay_protest
        if s == DEACTIVATE:
            return c.delay_deactivate
        return 1.0

    def shape_bias(self):
        """'curt' to collapse the draw (minimising), 'open' to keep it, ''."""
        s = self.strategy()
        return "curt" if s == DEACTIVATE else ("open" if s == PROTEST else "")

    def register_line(self, ja=False):
        s = self.strategy()
        if s == PROTEST:
            if ja:
                return ("反応が早くて少し多すぎで、彼を試している。彼がそこにいることを確かめたくて、"
                        "返ってくるものはどれも、そこに彼がどれだけ入っているかで測られている")
            return ("quick and a little too much, and testing him: she wants to know he is there and every "
                    "answer is being measured for how much of him is in it")
        if s == DEACTIVATE:
            if ja:
                return ("わざと短く、忙しそうに、何も必要としていない顔をしている。"
                        "他にすることがある人のように返していて、確かめたことを彼に見られるくらいなら死ぬ")
            return ("brief, busy and needing nothing, on purpose; she answers like someone with better things "
                    "to do and would rather die than let him see she checked")
        return ""

    def intent_line(self):
        r = self.live()
        if not r:
            return ""
        if r["strategy"] == PROTEST:
            return ("she is pushing at him to find out whether he is still there -- `check_on`, `ask`, a `tease` "
                    "that is really a test, `complain` about the quiet, `confront` if it has an edge. Each one "
                    "escalates a little on the last; she is counting")
        return ("she has gone cold on purpose and is not going to chase: `nothing` is the likely answer, or a "
                "minimal `continue` about something of her own, as if she had not noticed the gap. Reaching for "
                "him now would cost her")

    def situation_line(self, ja=False):
        r = self.live()
        if not r:
            return ""
        swaps = len(r.get("switches", []))
        if r["strategy"] == PROTEST:
            line = ("あなたは彼に手を伸ばしては、返ってくるものを測っている。彼がまだそこにいることを"
                    "確かめたくて、それを隠せてもいない"
                    if ja else
                    "you have been reaching for him and measuring what comes back; you want to know he is still "
                    "there and you are not being subtle about it")
            if swaps:
                line += ("。気にしないふりをしてみて、続かなかったあと" if ja else
                         ", after you tried not caring and could not keep it up")
        else:
            line = ("あなたはわざと彼に冷たくしている。忙しそうに、短く、何も必要としていない顔で、"
                    "知られるより不思議がられているほうがいい"
                    if ja else
                    "you have gone cold on him on purpose: busy, brief, needing nothing, and you would rather he "
                    "wondered than knew")
            if swaps:
                line += ("。押してみて何も返ってこなかったあと" if ja else ", after pushing got you nothing")
        return line

    def director_line(self):
        r = self.live()
        if not r:
            return ""
        if r["strategy"] == DEACTIVATE:
            return ("ATTACHMENT: she has gone cold on him on purpose -- she is filling her time (people, a task, "
                    "the TV, anything) and the phone stays face down; her scenes should show her being busy, "
                    "not waiting")
        return ("ATTACHMENT: she is pushing at him -- checking the phone, rereading, half-starting messages; her "
                "scenes should show her not quite present wherever she is")

    def report(self):
        c = self.config.attachment
        r = self.live()
        out = [f"attachment strategy (threat now {self.last_threat:.2f}, engage {c.engage_from})"]
        if r:
            hours = (self.clock.now_ts() - float(r["ts"])) / 3600.0
            out.append(f"  OPEN: {r['strategy']} for {hours:.1f}h (started as {r.get('first')}, threat {r.get('threat')}, "
                       f"peak {r.get('peak_threat')}, his messages {r.get('his_messages', 0)})")
            out.append(f"    scores at open: {r.get('scores')}")
            for n in r.get("notes", []):
                out.append(f"    {n}")
            for s in r.get("switches", []):
                out.append(f"    {self.clock.hm(s['ts'])} {s['from']} -> {s['to']}: {s['why']}")
            for t in r.get("tests", []):
                out.append(f"    test {self.clock.hm(t['ts'])} ({t['kind']}): {t['test']}")
            if r.get("rebound_p"):
                out.append(f"    rebound p {r['rebound_p']}")
        else:
            out.append("  nothing open")
        p, d, notes = self.scores()
        out.append(f"  if one opened now: protest {p:.2f} vs deactivate {d:.2f} ({'; '.join(notes)})")
        log = self._log()
        if log:
            out.append(f"  last {min(6, len(log))} episode(s):")
            for e in log[-6:]:
                out.append(f"    {e.get('date')} {e.get('first')}->{e.get('strategy')} {e.get('outcome')} "
                           f"{e.get('hours')}h, {len(e.get('switches', []))} switch(es)")
        return "\n".join(out)
