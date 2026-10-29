
import logger

# Stress, which is not a feeling and does not behave like one.
#
# Every emotion here decays toward a baseline in hours, which is right for
# anger and wrong for this: a person who has had a bad fortnight is still
# wound up on the quiet Sunday at the end of it. So stress is an integrator
# with hysteresis. It has a target -- what her present LOAD justifies -- and
# it moves toward that target quickly upward and slowly downward, and the
# downward rate is itself gated on whether she is getting any recovery. That
# asymmetry is the whole mechanism; a symmetric version is just another
# emotion with a long name.
#
# Susceptibility is derived, never declared. Two people under the same load
# are not under the same stress, and what makes the difference is how much of
# their identity is load-bearing: `data/self_beliefs.json` says what she has
# riding on being a particular sort of person, and a girl with nine beliefs at
# ninety has further to fall from any given day than one with nine at forty.
# Concentration matters as much as height -- everything resting on one belief
# is brittle -- so the spread is in it too. Nothing in this file knows whether
# she is a worrier. Give it a different sheet and it answers differently.
#
# The load terms are all things the simulation already tracks. Stress invents
# no new bookkeeping: it reads what is unfinished, what cannot be said, what
# is owed, what her body is doing and how her people are.


class Stress:
    def __init__(self, config, store, clock, state, records=None, goals=None,
                 ruptures=None, ick=None, sentiments=None, health=None, money=None,
                 self_model=None, spirals=None):
        self.config = config
        self.store = store
        self.clock = clock
        self.state = state
        self.records = records
        self.goals = goals
        self.ruptures = ruptures
        self.ick = ick
        self.sentiments = sentiments
        self.health = health
        self.money = money
        self.self_model = self_model
        self.spirals = spirals
        self._susceptibility = None

    # ---------------- how much this person is a candidate for it ----------------

    def susceptibility(self):
        """0.5 to 1.5ish, derived from what her identity has riding on it.

        Not a trait anyone wrote down. A character sheet with modest, spread
        beliefs produces a resilient girl; one whose whole self rests on two
        propositions produces a brittle one, and the same code says so."""
        if self._susceptibility is not None:
            return self._susceptibility
        c = self.config.stress
        invested = []
        try:
            for b in (self.self_model.beliefs() if self.self_model else []):
                invested.append(float(b.get("invested", 50)))
        except Exception:
            invested = []
        if not invested:
            self._susceptibility = 1.0
            return 1.0
        mean = sum(invested) / len(invested)
        # concentration: how much of the total sits in the top third of beliefs
        top = sorted(invested, reverse=True)[: max(1, len(invested) // 3)]
        concentration = sum(top) / max(1.0, sum(invested))
        anx = float(self.state._baseline("anxiety")) if "anxiety" in self.state.gauges else 40.0
        s = (c.susceptibility_base
             + c.per_invested * (mean - 50.0) / 50.0
             + c.per_concentration * (concentration - 0.34)
             + c.per_anxiety_baseline * (anx - 40.0) / 40.0)
        self._susceptibility = max(c.susceptibility_min, min(c.susceptibility_max, s))
        return self._susceptibility

    # ---------------- what is on her ----------------

    def load(self, silent_hours=0.0):
        """The weighted sum of what she is carrying, 0..1ish. Every term is
        something the simulation already knows; none of it is new bookkeeping."""
        c = self.config.stress
        w = c.load_weights
        g = self.state.gauges
        parts = {}

        # unfinished: goals that have cost her something and are still open
        try:
            open_cost = sum(float(x.get("cost", 0) or 0) for x in (self.goals.all() if self.goals else [])
                            if x.get("state") == "wanting")
            parts["unfinished"] = min(1.0, open_cost / max(1.0, c.cost_full))
        except Exception:
            parts["unfinished"] = 0.0

        # unmended: a rupture standing between them
        try:
            parts["rupture"] = 1.0 if (self.ruptures and self.ruptures.open_one()) else 0.0
        except Exception:
            parts["rupture"] = 0.0

        # unspeakable: what she knows and cannot raise
        try:
            charge = sum(self.ick._live(i, self.clock.now_ts()) for i in self.ick.carrying()) if self.ick else 0.0
            parts["unspeakable"] = min(1.0, charge / max(1.0, c.charge_full))
        except Exception:
            parts["unspeakable"] = 0.0

        # unsaid: pressure with no outlet taken
        parts["unsaid"] = max(0.0, self.state.over_rest("unsaid")) / 100.0

        # body: the day her body is having, only the bad direction
        body = 0.0
        body += max(0.0, self.state.over_rest("unwell")) / 100.0
        body += max(0.0, -self.state.over_rest("energy")) / 100.0
        try:
            night = self.health.night() if self.health else {}
            if str(night.get("quality", "")) in ("poor", "rough"):
                body += c.bad_night
        except Exception:
            pass
        parts["body"] = min(1.0, body)

        # people: being out of place with them
        parts["belonging"] = max(0.0, -self.state.over_rest("belonging")) / 100.0

        # him: silence, and how much he is to her
        att = 0.0
        try:
            key = self.state._him_key()
            att = self.sentiments.live(key, "attachment") / 100.0 if (self.sentiments and key) else 0.4
        except Exception:
            att = 0.4
        parts["him"] = min(1.0, (silent_hours / max(1.0, c.silence_full)) * (0.5 + att))

        # what is coming: things she has agreed to and is dreading
        try:
            ev = self.store.get("event_stances", {}).get("events", [])
            parts["ahead"] = min(1.0, len([e for e in ev if e.get("stance") == "dragged"]) / 3.0)
        except Exception:
            parts["ahead"] = 0.0

        # money, when there is something she has said yes to
        try:
            bal = float((self.store.get("money", {}) or {}).get("balance", 9999))
            parts["money"] = 1.0 if bal < c.broke_below else 0.0
        except Exception:
            parts["money"] = 0.0

        total = sum(w.get(k, 0.0) * v for k, v in parts.items())
        self._parts = parts
        return max(0.0, min(1.5, total))

    # ---------------- the integrator ----------------

    def target(self, silent_hours=0.0):
        c = self.config.stress
        return max(0.0, min(100.0, c.floor + self.susceptibility() * self.load(silent_hours) * c.scale))

    def recovery(self):
        """Whether she is actually getting any. Absence of load is not rest:
        a person lying awake with her phone on her chest is not recovering."""
        c = self.config.stress
        g = self.state.gauges
        r = c.recovery_base
        scene = self.store.last_scene() or {}
        if str(scene.get("with_who", "")).lower() in ("alone", ""):
            r += c.recovery_alone
        if g.get("physical_comfort", 60) >= self.state._baseline("physical_comfort"):
            r += c.recovery_comfortable
        try:
            night = self.health.night() if self.health else {}
            if str(night.get("quality", "")) in ("good", "ok"):
                r += c.recovery_slept
        except Exception:
            pass
        # exhaustion forces rest: without this the loop has no way down
        s = g.get("stress", 0)
        r += c.recovery_per_stress * max(0.0, s - c.exhaustion_from) / 100.0
        return max(0.1, r)

    def step(self, hours, silent_hours=0.0):
        """Fast up, slow down, and only as far down as the load allows."""
        c = self.config.stress
        if not c.enabled or "stress" not in self.state.gauges:
            return
        tgt = self.target(silent_hours)
        cur = self.state.gauges["stress"]
        if cur < tgt:
            step = c.rise_per_hour * max(0.0, hours)
            self.state.gauges["stress"] = min(tgt, cur + step)
        elif cur > tgt:
            step = c.fall_per_hour * self.recovery() * max(0.0, hours)
            self.state.gauges["stress"] = max(tgt, cur - step)

    def relieve(self, kind):
        """A discrete release: a bath, the diary, a goal landing, a mend. It
        settles toward the load floor and never through it, because the thing
        causing it has not gone anywhere."""
        c = self.config.stress
        amount = c.relief.get(kind, 0.0)
        if not amount or "stress" not in self.state.gauges:
            return
        # Every site that calls this is polled, not edge-triggered: a bath is a
        # scene setting that lasts a block, a good night is a fact about the
        # whole morning, a warm exchange is a mood with a fade on it. Without a
        # cooldown here each of them would relieve her once per director tick,
        # which is not a release, it is a second decay curve.
        now = self.clock.now_ts()
        seen = self.store.get("stress_relief_ts", {}) or {}
        gap = float(c.relief_gap_minutes.get(kind, c.relief_gap_default)) * 60.0
        try:
            last = float(seen.get(kind, 0) or 0)
        except (TypeError, ValueError):
            last = 0.0
        if now - last < gap:
            return
        seen[kind] = now
        self.store.set("stress_relief_ts", seen)
        floor = self.target(0.0)
        before = self.state.gauges["stress"]
        self.state.gauges["stress"] = max(floor, before - amount)
        if before - self.state.gauges["stress"] >= 1.0:
            logger.log(f"[stress] {kind}: {before:.0f} -> {self.state.gauges['stress']:.0f} "
                       f"(the load holds it at {floor:.0f})")

    # ---------------- what it does to everything else ----------------

    def multiplier(self, what):
        """The compounding, capped. Without caps these terms feed each other
        and she never comes back up."""
        c = self.config.stress
        s = self.state.gauges.get("stress", 0)
        over = max(0.0, s - c.compounds_from) / max(1.0, 100.0 - c.compounds_from)
        m = 1.0 + over * c.compounds.get(what, 0.0)
        return min(m, c.compound_cap)

    def report(self):
        s = self.state.gauges.get("stress", 0)
        self.load(self.state.felt_hours(0) if hasattr(self.state, "felt_hours") else 0)
        out = [f"stress {s:.0f}, heading for {self.target():.0f}",
               f"  susceptibility {self.susceptibility():.2f} (derived from her beliefs, not set)",
               f"  recovery now   {self.recovery():.2f}x"]
        for k, v in sorted(getattr(self, "_parts", {}).items(), key=lambda kv: -kv[1]):
            if v > 0.001:
                out.append(f"    {k:12s} {v:.2f}")
        for what in self.config.stress.compounds:
            out.append(f"  x{self.multiplier(what):.2f} {what}")
        return "\n".join(out)
