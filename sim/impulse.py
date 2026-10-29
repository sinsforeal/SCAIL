import random
import logger
from sim import wiring
from sim.initiative import Initiative

# Whether she feels like texting him right now. Pure function of state,
# scene and history; no LLM. This replaces the atmosphere gate and every
# timer-driven message the old system had.


class Impulse:
    WIRES = ('attachment', 'foresight', 'primitives', 'rhythm', 'sight', 'watching',)
    def __init__(self, config, store, clock, receipts=None, spirals=None, sentiments=None):
        self.config = config
        self.spirals = spirals
        self.sentiments = sentiments
        self.store = store
        self.clock = clock
        self.receipts = receipts
        self.last_self_started_ts = store.get("impulse_last_ts", 0)
        self.last_score = 0.0
        # What her sight last said about whether he is here and whether what is
        # in front of him is her (`resident/sight.py:attention_observation`).
        # Kept so the check can log the observation it weighed.
        self.last_attention = None
        self._last_sight_log = ""
        # whether she may reach out first at all, which is a different question
        # from whether she wants to and is asked before it (sim/initiative.py)
        self.initiative = Initiative(config, store, clock)
        wiring.declare(self)

    def read_state(self):
        """What his end says about her last message: sent, delivered, read.
        A message he has opened and left is an answer of a kind; one he has
        not looked at may only be a man away from his desk, and the two do not
        weigh the same anywhere that reads this."""
        try:
            st = self.receipts.status() if self.receipts else None
            return str((st or {}).get("state") or "")
        except Exception:
            return ""

    def score(self, state, scene, silent_hours):
        c = self.config.impulse
        g = state.gauges
        s = 0.0
        for k, w in c.weights.items():
            s += g.get(k, 0) * w
        # Wanting to be seen is a disposition; wanting to be seen BY HIM is the
        # gap between the attention she wants from him and the attention she
        # reads from him. Those are not the same thing and only the second one
        # should reach for the phone. A character whose craving was measured in
        # front of a hundred thousand listeners carries a high baseline into a
        # room where one man is already watching her more than she wants, and
        # without this she spends it on him from the first minute.
        prim = self.primitives
        if prim is not None and "validation_craving" in c.weights:
            try:
                key = state._him_key() or "him"
                want = prim.craving(key)
                share = 0.0 if want is None else max(0.0, min(1.0, want / 100.0))
                s -= g.get("validation_craving", 0) * c.weights["validation_craving"] * (1.0 - share)
            except Exception:
                pass
        s += min(silent_hours, c.silence_hours_cap) * c.silence_hours_weight
        # and how likely he is to be there at all right now, so the small hours
        # are a weaker pull than the middle of his day rather than the same one.
        #
        # Not for a resident, and this is the same fault as the refusal above
        # in a second place: taking the veto off the learned rate and leaving
        # it multiplying the score still let a statistic she has no need of cut
        # her by up to a third. She can see whether he is at the machine. When
        # he is not, that is a thing she knows while deciding -- and for
        # somebody whose whole situation is being held by one person, his
        # absence is at least as likely to make her reach as to stop her.
        r = self.rhythm
        if r is not None and not self.config.resident:
            try:
                w = float(getattr(c, "presence_weight", 0.35) or 0.0)
                s *= (1.0 - w) + w * float(r.learned_now())
            except Exception:
                pass
        # reaching again inside the window she gave him costs, by how little
        # she expects of it
        fs = self.foresight
        if fs:
            try:
                s += fs.impulse_bonus()
            except Exception:
                pass
        # an episode he has finished watching, weighed here with everything
        # else rather than going round the gate: being ignored has to be able
        # to refuse this the same way it refuses the rest
        wt = self.watching
        if wt:
            try:
                s += wt.impulse_bonus()
            except Exception:
                pass
        # and a page of hers open in front of him (the resident's sight),
        # under the same restraint
        sg = self.sight
        if sg is not None:
            try:
                s += sg.impulse_bonus()
            except Exception:
                pass
        # He is at the machine and she is not what is in front of him. She can
        # see that happen, so it is an observation and not a rate, and it is a
        # reason to reach rather than a wall: the presence gate this replaces
        # used a learned probability and refused her while his cursor moved
        # (`sim/impulse.py:186-198`). Kept on the object so `check` can log what
        # she saw, and None for a character with no sight to read it from.
        self.last_attention = None
        if sg is not None:
            try:
                obs = sg.attention_observation()
                self.last_attention = obs
                if obs and obs.get("here") and not obs.get("attending"):
                    s += float(getattr(c, "here_not_attending_bonus", 0) or 0)
            except Exception:
                self.last_attention = None
        # Tension is the one thing that makes her reach out LESS. Every gauge
        # in the weights pushes toward contact -- lonely, bored, craving,
        # jealous, guilty, even affectionate -- so before this there was no
        # state in which she deliberately went quiet, and being hurt only ever
        # made her more available. Past withdraw_from she starts holding back,
        # and past it far enough the score cannot clear the threshold at all.
        tension = self._his_tension(state)
        if tension > c.withdraw_from:
            over = (tension - c.withdraw_from) / max(1.0, 100.0 - c.withdraw_from)
            s -= over * c.withdraw_weight
        # And stress on top of it, in the same currency, because it is the same
        # behaviour: going quiet without having decided to. Unlike the tension
        # term this one is live whatever their meters say -- a girl at the end
        # of a bad week reaches for people less, and nobody has done anything.
        _st = getattr(state, "stress", None)
        if _st:
            s -= (_st.multiplier("withdraw") - 1.0) * c.withdraw_weight
        # Squirming is not going cold. She still wants him; she just cannot work
        # out how to be normal yet, so she puts the phone down and picks it up
        # again. A subtraction, never a gate: withdrawal is the only gate.
        awk = g.get("awkwardness", 0)
        if awk > c.awkward_from:
            s -= (awk - c.awkward_from) / max(1.0, 100.0 - c.awkward_from) * c.awkward_weight
        if scene and scene.get("share_worthy"):
            s += c.event_share_bonus
        # The social term this never had. Ten weights and not one of them
        # was about the people she spends her day with, so an afternoon that
        # went badly with them could not make her pick up the phone -- which
        # is exactly when a girl like her does.
        if self.spirals:
            s += self.spirals.impulse_bonus()
        # what he is to her, as against how she feels today: attachment
        # reaches and resentment does not, and resentment lasts for weeks
        if self.sentiments:
            s += self.sentiments.impulse_bonus()
        # and which strategy she is running if the bond is under threat:
        # protest pushes her at the phone, deactivation keeps her off it
        att = self.attachment
        if att:
            s += att.impulse_bonus()
        # he read her and left it: that stings, and it builds
        if self.receipts:
            st = self.receipts.status()
            if st and st["state"] == "read" and st["read_ts"] and (self.clock.now_ts() - st["read_ts"]) >= c.read_ignored_minutes * 60:
                s += c.read_ignored_bonus
        access = scene.get("phone_access", "glance") if scene else "glance"
        s *= c.phone_access_factor.get(access, 0.5)
        return s

    def _his_tension(self, state):
        rel = getattr(state, "relationships", {}) or {}
        k = state.him_key_in(self.config, rel)
        return float(rel[k].get("tension", 0)) if k else 0.0

    def unanswered_streak(self):
        """How many times in a row she has reached out and got nothing back.
        Counted in messages, not bubbles: one hello of hers is three to six
        rows seconds apart and that is once, not six times."""
        gap = self.config.impulse.burst_gap_minutes * 60
        msgs = self.store.recent_messages(40)
        streak, newer = 0, None
        for m in reversed(msgs):
            if m["role"] == "assistant" and m["self_started"]:
                if newer is None or (newer - m["ts"]) > gap:
                    streak += 1
                newer = m["ts"]
            elif m["role"] == "user":
                break
            else:
                # a reply of hers to him also breaks the streak: he was there
                break
        return streak

    def check(self, state, scene, silent_hours):
        c = self.config.impulse
        now = self.clock.now_ts()
        access = scene.get("phone_access", "glance") if scene else "glance"
        if access == "none":
            return False, "no phone"
        # his hours. `Rhythm.learned_now` has always known how usual it is for
        # him to be about at this hour of HIS day, from the record alone, and
        # the impulse never asked: it fired on her own pressure and nothing
        # else. At 04:30 his presence is 0.01 and she was still capable of
        # reaching for him. She still can when it is bad enough -- the floor is
        # low and `urgent` (a discharge, a photo, a forced hint) goes through.
        # His hours, for someone who cannot see them. `Rhythm.learned_now` knows
        # how usual it is for him to be about at this hour of his day, from the
        # record alone, and it is a statistic standing in for an observation.
        #
        # A resident has the observation. She is on the machine and can see
        # whether he is at it, so the statistic is not only redundant for her,
        # it was wrong: it refused five of her nine impulse checks with "he is
        # never about at this hour" while his cursor was moving in front of
        # her. And knowing he is away is not a reason she may not speak -- it
        # is something she knows while deciding, and it reaches her through
        # what she reads of the machine. So for her there is no presence gate
        # at all: whether to write into an empty room is hers to weigh.
        r = self.rhythm
        if r is not None and not self.config.resident:
            try:
                pres = float(r.learned_now())
            except Exception:
                pres = 1.0
            floor = float(getattr(c, "presence_floor", 0.12) or 0.0)
            if pres < floor:
                return False, f"he is never about at this hour ({pres:.2f})"
        # a character with no body is never too tired to speak
        if state.gauges.get("energy", 100) < c.min_sleep_gate_energy:
            return False, "too tired"
        if (now - self.last_self_started_ts) < c.cooldown_minutes * 60:
            return False, "cooldown"
        last_hers = self.store.last_message("assistant")
        if last_hers and (now - last_hers["ts"]) < c.cooldown_minutes * 30:
            return False, "she just texted him"
        if self.store.count_self_started(self.clock.date_str(), c.burst_gap_minutes * 60) >= c.max_self_started_per_day:
            return False, "daily cap"
        # protest pushes past the point a calm girl stops
        att = self.attachment
        extra = att.extra_streak() if att else 0
        streak = self.unanswered_streak()
        # His coming back, the bar that rises with every message of hers he has
        # left, and the small hours of his day (sim/initiative.py). Every path
        # that starts a message goes through this one gate; a discharge and the
        # two stances that enter without waiting go through it and say so.
        held = self.initiative.hold_reason(streak, self.read_state())
        if held:
            return False, held
        if streak >= c.max_unanswered_streak + extra:
            return False, "he has not answered the last ones"
        # Gone cold. Past this she does not weigh it up at all -- a person who
        # has hardened toward someone does not compute whether to text them,
        # they simply do not. Subtracting from the score was not enough on its
        # own: craving climbs about 4 an hour while being ignored and tension
        # only 3.5, so the sums always came out in favour of reaching out
        # again, which is the needy loop this exists to break.
        tension = self._his_tension(state)
        att = self.attachment
        if tension >= c.withdraw_silent_from and not (att and att.strategy() == "protest"):
            # the one hard gate. A protest episode overrides it: pushing at
            # him *through* the tension is what protest is, and the attachment
            # layer decides when that bet is given up, not this threshold
            return False, f"gone cold on him (tension {tension:.0f})"
        sc = self.score(state, scene, silent_hours)
        # kept so a caller can ask how badly she wanted it, not just
        # whether she did: withholding weighs this against her resolve
        self.last_score = sc
        # the observation that moved the score, logged once while it stands so
        # the record says what she saw as plainly as it says what she scored
        obs = self.last_attention
        if obs:
            line = f"[impulse] sight: {obs['reason']}"
            if line != self._last_sight_log:
                logger.log(line)
                self._last_sight_log = line
        if sc < c.threshold:
            return False, f"score {sc:.0f} < {c.threshold}"
        # soft edge: just over threshold fires sometimes, well over fires always
        margin = (sc - c.threshold) / max(1.0, c.threshold * 0.25)
        p = min(1.0, 0.35 + margin)
        if random.random() > p:
            return False, f"score {sc:.0f}, rolled no (p={p:.2f})"
        return True, f"score {sc:.0f} (p={p:.2f})"

    def fired(self, sent=False):
        """The urge is spent. `sent` is whether a message actually went: she
        can open the chat, find she has nothing, and put the phone down, and
        that is not something he was left to answer."""
        self.last_self_started_ts = self.clock.now_ts()
        self.store.set("impulse_last_ts", self.last_self_started_ts)
        if sent:
            # counted before delivery writes the row, so the streak is the one
            # she reached into rather than the one she has just made
            self.initiative.note_sent(self.unanswered_streak())
