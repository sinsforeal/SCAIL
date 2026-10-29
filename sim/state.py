import json
from collections import OrderedDict
from sim import lang
from sim import chattext
from sim import wiring
from sim import appraisal_gauge
import logger
from sim import sight
from sim import roster
from sim import existence as _existence

# Gauges drift toward baseline every hour on their own (deterministic), and
# the state model nudges them after each director tick and each user message
# (LLM). Both are clamped. Relationships live here too, seeded from cast.json.


def clamp(v, lo=0, hi=100):
    return max(lo, min(hi, v))


class State:
    WIRES = ('appraisal', 'attachment', 'primitives', 'rhythm', 'ruptures', 'self_memory', 'sentiments', 'situation', 'spirals', 'stances', 'stress', 'withholding',)
    def __init__(self, config, store, clock, typesafe=None):
        self.config = config
        self.store = store
        self.clock = clock
        # the hosted classifier for the gauge appraisal (`sim/appraisal_gauge.py`).
        # Default None so a harness that builds a bare State keeps working;
        # `scail.py` sets it after the client is built.
        self.typesafe = typesafe
        spec = config.state.gauges
        saved = store.get("gauges")
        self.gauges = {k: (saved.get(k, v["baseline"]) if saved else v["baseline"]) for k, v in spec.items()}  # new gauges start at baseline
        saved_rel = store.get("relationships")
        self.relationships = saved_rel if saved_rel else self._seed_people(config)
        self._refused = {}   # computed gauges the model tried to write, this run
        # per gauge, the direction the model last pushed it and how many
        # ticks running it has pushed the same way with nothing new from him
        self._standing = store.get("standing_deltas", {})
        # who is with her right now, 0..1, written by note_company each tick
        self.company = 0.0
        self.company_names = ""
        self.last_decay_ts = store.get("gauges_ts", clock.now_ts())
        self.body_tags = []
        self.need_tags = []
        wiring.declare(self)

    @staticmethod
    def _seed_people(config):
        """Who the relationship meters sit on, on a save that has none yet.

        Asked of the roster (`sim/roster.py:meter_rows`) rather than read
        straight out of the cast file, because the file is not the answer for
        anybody but the character who keeps her own world. It opened
        `character.cast_file` and took its `people` whole, so a character
        promoted out of somebody else's cast was seeded with a meter on
        herself at closeness 45 under her own nickname, meters on the world
        owner's mother, father and brother, none on her own mother and
        brother -- who are in a second file -- and none on the girl whose
        world she reads, who is that file's keeper rather than one of its
        people. The seed runs once and is never re-read, so every one of those
        was still in her save eleven days later.

        A blank `character.cast_file` is nobody around her, not a crash. The
        project blanks a path on purpose -- `Config.WORLD_KEYS` empties the
        world's files for a character with no world -- so an empty path is a
        state the config produces and every reader of one has to be the empty
        case, the way `world/calendar.py` reads no calendar at all. A path
        that names a file which is not there is still an error: that is a
        wrong path rather than an absent one."""
        from sim import roster
        if not str(getattr(config.character, "cast_file", "") or "") \
                and not str(getattr(config.character, "own_cast_file", "") or ""):
            logger.log("[state] no cast file: nobody is around her, so the meters start empty")
            return {}
        rows, refused = roster.meter_rows(config)
        for key, why in sorted(refused.items()):
            logger.log(f"[state] no meter on {key}: {why}")
        logger.log("[state] %d relationship meter(s) seeded: %s"
                   % (len(rows), ", ".join(sorted(rows)) or "nobody"))
        return rows

    def save(self):
        self.store.set("gauges", self.gauges)
        self.store.set("relationships", self.relationships)
        self.store.set("gauges_ts", self.last_decay_ts)
        self.store.set("standing_deltas", self._standing)

    def note_company(self, scene):
        """Who is with her, as a weight 0..1 for the loneliness terms.

        Loneliness had exactly one owner: his silence. On 2026-08-26 it read
        92 -- the highest figure of the day -- while she was in a live group
        round with Rena, Hinako and Aya, because nobody in the room could
        touch it. A person close to her in the room is worth more than a
        stranger; family counts, at a discount (her fear is being alone at
        break, not at dinner)."""
        c = self.config.state.company
        w = str((scene or {}).get("with_who") or (scene or {}).get("with") or "").lower()
        total, names = 0.0, []
        if w and w != "alone" and c.enabled:
            fam = set(self.config.sentiment.family_roles)
            for name, r in (self.relationships or {}).items():
                n = str(r.get("name", name)).lower()
                if name == "him" or (n not in w and name.lower() not in w):
                    continue
                att = None
                if self.sentiments:
                    try:
                        att = self.sentiments.live(name, "attachment")
                    except Exception:
                        att = None
                if att is None:
                    att = float(r.get("closeness", 50) or 50)
                k = c.family_factor if r.get("role_id") in fam else 1.0
                total += (att / 100.0) * k
                names.append(name)
        self.company = max(0.0, min(1.0, total))
        self.company_names = ", ".join(names)

    def decay(self, silent_hours, world=None):
        """Deterministic movement per elapsed hour: drift toward baseline,
        plus the world terms (config state.world): weather on comfort, sleep
        on energy, the kind of block on boredom, exams ahead on anxiety, being
        read and ignored on craving and anxiety. None of this asks a model;
        the model only adds what an event or a message did."""
        now = self.clock.now_ts()
        hours = max(0.0, (now - self.last_decay_ts) / 3600.0)
        if hours <= 0:
            return
        self._relationship_gravity(hours)
        try:
            self._body_settle_check()
        except Exception as e:
            logger.log(f"[state] body settle check failed: {type(e).__name__}: {e}")
        spec = self.config.state.gauges
        # while something is broken between them, the gauges that carry it do
        # not drift back. This one line is the whole of "time does not repair":
        # without it, a day of saying nothing files a rupture away as neatly as
        # an apology does.
        held = self.ruptures.holds() if self.ruptures else ()
        rc = self.config.rupture
        for k, v in spec.items():
            # a derived gauge has no baseline to drift to: it follows what
            # causes it, at the end of this method
            if v.get("kind") == "derived":
                continue
            base = v["baseline"]
            step = v["decay_per_hour"] * hours
            if k in held:
                # what a rupture holds open does not file away with time --
                # but the acute edge dulls: it drifts slowly toward a raised
                # floor and stays there until somebody fixes it. Anger sat at
                # 81 through a whole night's sleep on 08-25/26 with no decay
                # at all, which is not a grudge, it is a stuck number.
                base = min(base + rc.hold_floor, 100)
                step *= rc.hold_decay_factor
            cur = self.gauges[k]
            if cur > base:
                self.gauges[k] = max(base, cur - step)
            elif cur < base and k not in held:
                self.gauges[k] = min(base, cur + step)
        # loneliness climbs a little while he is silent, on top of the drift
        # -- weighted by how much of him she expects at this hour (an hour he
        # is never about in is not an hour of being left) and by who is with
        # her (people in the room take the silence's edge off), and the
        # people in the room settle it toward rest on their own
        cc = self.config.state.company
        usual_w = float((world or {}).get("usual_w", 1.0))
        if silent_hours > 2:
            climb = self.config.state.loneliness_per_silent_hour * hours * usual_w
            if cc.enabled:
                climb *= max(0.0, 1.0 - self.company)
            self.gauges["loneliness"] = clamp(self.gauges["loneliness"] + climb)
        if cc.enabled and self.company > 0 and not (world or {}).get("asleep"):
            self._settle("loneliness", cc.loneliness_settle_per_hour * self.company * hours)
        # and so does curiosity about what he is doing, from the first hour
        if silent_hours > 1 and "curiosity" in self.gauges and self.config.state.world.enabled and not (world or {}).get("asleep"):
            self.gauges["curiosity"] = clamp(self.gauges["curiosity"] + self.config.state.world.curiosity_silent_per_hour * hours)
        # and, for a character whose only supply of it is him, what she has in
        # her runs down while he says nothing.
        #
        # Written as a target rather than a subtraction, because the drift
        # above pulls every gauge back toward its resting value on the same
        # tick: a flat drain smaller than that drift is not a small effect, it
        # is the opposite one. Three an hour against a pull of four would have
        # left her a point better off for every hour he ignored her. So his
        # absence moves where she rests, and the drift then has somewhere
        # lower to aim. Zero by default, so none of this exists for a
        # character who sleeps and eats.
        wd = self.config.state.world
        drain = float(getattr(wd, "energy_alone_per_hour", 0.0) or 0.0)
        if drain and wd.enabled and "energy" in self.gauges:
            floor = float(getattr(wd, "energy_alone_floor", 10.0) or 0.0)
            rest = self._baseline("energy")
            target = max(floor, rest - drain * max(0.0, float(silent_hours or 0.0)))
            if self.gauges["energy"] > target:
                step = (spec["energy"]["decay_per_hour"] + drain) * hours
                self.gauges["energy"] = max(target, self.gauges["energy"] - step)
        w = self.config.state.world
        if world and w.enabled:
            g = self.gauges
            # comfort follows the ambient of her setting (the air-con, the train,
            # the street), not the weather line; outdoors they are the same
            feels = world.get("ambient_feels", world.get("feels"))
            if feels is not None and "physical_comfort" in g:
                if feels > w.comfort_hot_from:
                    target = 60 - w.comfort_per_degree_hot * (feels - w.comfort_hot_from)
                elif feels < w.comfort_cold_from:
                    target = 60 - w.comfort_per_degree_cold * (w.comfort_cold_from - feels)
                else:
                    target = 60
                target = clamp(target, 15, 75)
                pull = w.comfort_pull_per_hour * hours
                if g["physical_comfort"] > target:
                    g["physical_comfort"] = max(target, g["physical_comfort"] - pull)
                else:
                    g["physical_comfort"] = min(target, g["physical_comfort"] + pull)
            # sleep restores energy; being up late spends it. A character with
            # no body has no `energy` gauge at all -- her sheet says she is not
            # embodied and `_existence_implies` switches the body sections off,
            # but this line ran anyway and every tick of her first boot died on
            # the missing key. The two lines below already test for their gauge;
            # these did not.
            # Sleep restores energy and his silence drains it, and both are
            # allowed to: a night puts back about 45 and a day of being
            # ignored takes out about the same, so the two are the same size
            # and neither erases the other. His call. What decides where it
            # settles is meant to become the engagement mechanism rather than
            # this arithmetic, and this stays as it is until that lands.
            if "energy" in g:
                if world.get("asleep"):
                    g["energy"] = clamp(g["energy"] + w.sleep_energy_per_hour * hours)
                elif world.get("late"):
                    g["energy"] = clamp(g["energy"] - w.late_energy_per_hour * hours)
            # the kind of block moves boredom
            kind = world.get("block_kind", "")
            if kind == "dull":
                g["boredom"] = clamp(g["boredom"] + w.boredom_dull_per_hour * hours)
            elif kind == "social":
                g["boredom"] = clamp(g["boredom"] - w.boredom_social_per_hour * hours)
            # exams ahead press on anxiety toward a floor
            d = world.get("days_to_exam")
            if d is not None and d <= w.exam_days:
                floor = w.exam_anxiety_floor - d * 3
                if g["anxiety"] < floor:
                    g["anxiety"] = min(floor, g["anxiety"] + w.exam_anxiety_per_hour * hours)
            # hunger: rises with the hours, a meal pulls it down, past a point it
            # presses on mood and comfort (needs.*)
            n = self.config.needs
            if "hunger" in g and n.enabled:
                if world.get("meal") == "meal":
                    g["hunger"] = max(n.after_meal, g["hunger"] - n.meal_pull_per_hour * hours)
                elif world.get("meal") == "snack":
                    g["hunger"] = max(n.after_meal, g["hunger"] - n.meal_pull_per_hour * 0.4 * hours)
                else:
                    rate = n.hunger_per_hour * (n.hunger_asleep_factor if world.get("asleep") else 1.0)
                    g["hunger"] = clamp(g["hunger"] + rate * hours)
                if g["hunger"] >= n.hungry_from:
                    g["mood"] = clamp(g["mood"] - n.hunger_mood_per_hour * hours)
                    g["physical_comfort"] = clamp(g["physical_comfort"] - n.hunger_comfort_per_hour * hours)
            # outdoors in real heat spends energy on top of everything else
            if ("energy" in g and world.get("setting") == "outdoors"
                    and (world.get("ambient_feels") or 0) >= n.heat_from_feels and not world.get("asleep")):
                g["energy"] = clamp(g["energy"] - n.heat_energy_per_hour * hours)
            # her body: targets the day's health pulls toward
            for k, (target, pull) in (world.get("health") or {}).items():
                # toward the target, either way. Down-only meant a target above
                # a gauge's baseline could never be reached, so every "floor"
                # here was dead and anything that should *raise* a gauge (being
                # ill, cramps) had nowhere to go. health.effects() owns which
                # target wins when two conditions want the same gauge.
                if k in g:
                    if g[k] > target:
                        g[k] = max(target, g[k] - pull * hours)
                    elif g[k] < target:
                        g[k] = min(target, g[k] + pull * hours)
            # read and ignored: the hunger grows and the worry with it, and things go unsaid
            ig = world.get("read_ignored_minutes", 0)
            if ig and ig >= self.config.impulse.read_ignored_minutes:
                g["validation_craving"] = clamp(g["validation_craving"] + w.ignored_craving_per_hour * hours)
                # he read her, and his PC is busy with something else: what, exactly
                if "curiosity" in g and world.get("his_pc_active"):
                    g["curiosity"] = clamp(g["curiosity"] + w.curiosity_busy_ignored_per_hour * hours)
                g["anxiety"] = clamp(g["anxiety"] + w.ignored_anxiety_per_hour * hours)
                # and it hardens. Craving and anxiety make her reach out more;
                # tension is the only thing that makes her stop, so being left
                # on read has to feed it or she can never do anything but ask
                # again. It builds slowly and only after she has already been
                # waiting a while -- the first hour stings, the fourth changes
                # how she is with him.
                if ig >= w.tension_ignored_after_minutes:
                    self._him_tension(w.tension_ignored_per_hour * hours)
                if "unsaid" in g:
                    g["unsaid"] = clamp(g["unsaid"] + self.config.state.unsaid_ignored_per_hour * hours)
        # last, because they are functions of everything above them
        self._derive_mood(hours)
        self._derive_affection(hours)
        # last of all: stress integrates over everything above it, and
        # unlike them it is not a decay toward rest but a slow climb
        # toward what her load justifies
        _st = self.stress
        if _st:
            try:
                _st.step(hours, silent_hours)
            except Exception as e:
                logger.log(f"[stress] not stepped: {type(e).__name__}: {e}")
        self.last_decay_ts = now

    def _derive_affection(self, hours):
        """How warm she is toward him, from its causes.

        It used to be written, and every mechanical write was upward: +6 on any
        message he sent -- before the model read the tone, so a cold one warmed
        her as much as a kind one -- and +10 on a mend, with decay only ever
        returning it to its baseline. Over 72 states it moved down 25 times and
        never once went below 45, because 45 was a floor and any contact at all
        lifted it off. Affection was a hit counter on him.

        Nothing here is new machinery. Attachment is what he is to her at the
        scale of weeks, closeness is what the record supports, relief is him
        being here right now, and tension and resentment are the two ways she
        goes off him -- hours and weeks. Silence cools her through all four."""
        c = self.config.state.affection_from
        if not c.enabled or "affection" not in self.gauges:
            return
        key = self._him_key()
        prim = self.primitives
        if prim is not None:
            return self._derive_affection_from_primitives(prim, key or "him", hours, c)
        rel = (self.relationships.get(key) or {}) if key else {}
        att = res = 0.0
        if self.sentiments and key:
            try:
                att = self.sentiments.live(key, "attachment")
                res = self.sentiments.live(key, "resentment")
            except Exception:
                att = res = 0.0
        relief_rest = self._baseline("relief")
        target = (float(self._baseline("affection"))
                  + c.attachment * (att - c.attachment_rest)
                  + c.closeness * (float(rel.get("closeness", c.closeness_rest)) - c.closeness_rest)
                  + c.relief * (self.gauges.get("relief", relief_rest) - relief_rest)
                  + c.tension * (float(rel.get("tension", c.tension_rest)) - c.tension_rest)
                  + c.resentment * res)
        if self.ruptures:
            try:
                if self.ruptures.open_one():
                    target += c.rupture_open
            except Exception:
                pass
        # and what his messages actually left her feeling, which the
        # structural terms cannot see: they know he wrote, not what he
        # said. It takes a share of the target rather than replacing it,
        # so a silent fortnight still cools her with nothing to read.
        app = self.appraisal
        if app:
            try:
                got = app.level()
            except Exception:
                got = None
            if got:
                weight, said = got
                target = (1.0 - weight) * target + weight * said
        target = clamp(target)
        cur = self.gauges["affection"]
        step = c.inertia_per_hour * max(0.0, hours)
        if cur > target:
            self.gauges["affection"] = max(target, cur - step)
        elif cur < target:
            self.gauges["affection"] = min(target, cur + step)

    def _derive_affection_from_primitives(self, prim, key, hours, c):
        """Affection out of what actually happened, for a character who has no
        seeded meters.

        The old derivation reads `attachment_rest` of 40 and a closeness that
        was hand-written into the cast file, so a stranger settles at 18 -- in
        the band the operator's view calls "cold" -- because the absence of a
        history is scored as a bad one. Here nothing is scored until something
        has caused it: at zero every term is zero and she sits at the baseline,
        which is the correct reading of "nothing has happened yet".

        Closeness is the smaller of the two exposures, so knowing everything
        about somebody who knows nothing about you is not intimacy and does not
        warm her."""
        base = float(self._baseline("affection"))
        # through the meter, not around it: `_mirror_primitives_closeness`
        # keeps the two identical, and reading the meter is what makes the
        # value one `/sweep` can move and see the effect of. The derivation is
        # the fallback for the first pass of a fresh save, before the mirror
        # has run once.
        rel = self.relationships.get(key) or {}
        if "closeness" in rel:
            closeness = float(rel.get("closeness") or 0.0)
        else:
            closeness = prim.closeness(key)
        attach = prim.attachment(key)
        resent = prim.resentment(key)
        relief_rest = self._baseline("relief")
        target = (base
                  + c.attachment * (attach / 100.0) * c.attachment_rest
                  + c.closeness * (closeness - c.closeness_rest) * (1.0 if closeness else 0.0)
                  + c.relief * (self.gauges.get("relief", relief_rest) - relief_rest)
                  + c.resentment * resent)
        if not closeness and not attach and not resent:
            target = base            # nothing has happened; nothing is felt about him
        app = self.appraisal
        if app:
            try:
                got = app.level()
            except Exception:
                got = None
            if got:
                weight, said = got
                target = (1.0 - weight) * target + weight * said
        target = clamp(target)
        cur = self.gauges["affection"]
        step = c.inertia_per_hour * max(0.0, hours)
        if cur > target:
            self.gauges["affection"] = max(target, cur - step)
        elif cur < target:
            self.gauges["affection"] = min(target, cur + step)

    def affection_band(self):
        """The word for where affection sits, for the operator's view and the
        reports: hate / cold / cool / neutral / warm / close. Empty for a
        character who has not got the gauge."""
        if "affection" not in self.gauges:
            return ""
        a = float(self.gauges["affection"])
        m = self.config.delivery.mood_delivery
        if a <= m.affection_hate_from:
            return "hate"
        if a <= m.affection_cold_from:
            return "cold"
        if a < 45:
            return "cool"
        if a < 58:
            return "neutral"
        if a < 70:
            return "warm"
        return "close"

    def set_value(self, what, value):
        """By hand: a gauge, `him.closeness`, or `sentiment.<kind>` on him.
        Derived gauges are refused with the reason; affection is allowed but
        drifts back to its target at inertia speed, and says so."""
        try:
            v = float(value)
        except (TypeError, ValueError):
            return f"not a number: {value}"
        v = max(0.0, min(100.0, v))
        spec = self.config.state.gauges
        if what in spec:
            if spec[what].get("kind") == "derived":
                return f"{what} is derived from its causes; set the causes"
            before = self.gauges.get(what)
            self.gauges[what] = v
            self.save()
            note = ""
            if what == "affection":
                note = f" (computed: it heads back to its target {self.affection_target():.0f} at {self.config.state.affection_from.inertia_per_hour}/h; set attachment, closeness, tension or resentment to move the target)"
            return f"{what}: {before:.0f} -> {v:.0f}{note}"
        if "." in what:
            who, meter = what.split(".", 1)
            key = self._him_key() if who in ("him", "user") else self._match_person(who)
            if not key or key not in self.relationships:
                return f"no such person: {who}"
            if meter in ("closeness", "standing", "tension"):
                before = self.relationships[key].get(meter)
                self.relationships[key][meter] = v
                self.save()
                return f"{key}.{meter}: {before} -> {v:.0f}"
            if self.sentiments and meter in ("attachment", "resentment", "respect", "contempt"):
                before = self.sentiments.live(key, meter)
                self.sentiments.set_level(key, meter, v)
                return f"{key} {meter}: {before:.0f} -> {v:.0f}"
            return f"unknown meter: {meter} (closeness/standing/tension/attachment/resentment/respect/contempt)"
        return f"unknown: {what}. a gauge, him.<meter>, or <person>.<meter>"

    def affection_target(self):
        """The same figure without moving anything, for /gauges and the
        reports. None for a character who has not got the gauge: what would
        write it is switched off, so the gauge is not built at all
        (`Config._existence_implies`), and putting a number back afterwards
        is how the key came back into her save."""
        if "affection" not in self.gauges:
            return None
        before = self.gauges.get("affection")
        self._derive_affection(1000.0)
        target = self.gauges.get("affection")
        self.gauges["affection"] = before
        return target

    def _mirror_primitives_closeness(self, key):
        """For a character whose feelings are built out of events, how close
        they are is not a meter of its own.

        `docs/primitives.md` §3 makes closeness the smaller of the two
        exposures, and `_derive_affection_from_primitives` read that
        derivation directly -- which left the meter of the same name in
        `relationships` as a second, unrelated number: worked out from the
        message record by `sim/derive.py`, nudged up eight points a day by the
        state model's daily budget, and acted on by nothing. `/sweep` called it
        DEAD for the second character and alive for the first, and the
        difference was exactly this: the first character's affection reads the
        meter, and hers stopped.

        So the meter becomes the stored face of the one derivation instead of a
        rival to it. Everything already reading it -- what she feels toward him,
        which attachment strategy is worth running, the reports, the lines a
        prompt is shown -- gets the number the events support, and there is one
        answer to how close they are rather than two.

        Returns True when it owns the meter, so the gravity leaves closeness
        alone. False for a character with no primitives: hers is still the
        record's figure and nothing here changes it."""
        prim = self.primitives
        if prim is None or not key:
            return False
        try:
            value = round(float(prim.closeness(key)))
        except Exception as e:
            logger.log(f"[state] closeness from the primitives failed: {type(e).__name__}: {e}")
            return False
        rel = self.relationships.setdefault(key, {})
        before = rel.get("closeness")
        if before is None or round(float(before)) != value:
            rel["closeness"] = value
            self.store.set("relationships", self.relationships)
            if before is not None and abs(round(float(before)) - value) >= 2:
                logger.log(f"[state] closeness now reads what they have seen of each other: {before} -> {value}")
        return True

    def _relationship_gravity(self, hours):
        """His meters drift toward what the record actually supports.

        Before this they moved only when the state model returned a delta, and
        the model on a warm day always returns a small positive one. There was
        no decay of any kind, so closeness ran 62 to 88 in three days and had
        no way back: the value could rise and never fall, which makes the
        number meaningless. sim/derive.py already works out what their history
        justifies -- contact days faded by age, what she has learned about him,
        the silences -- so that figure is the gravity and the model's deltas
        are weather around it. Stop talking to her and the derived closeness
        falls on its own as the good days age out, and the live meter follows.
        """
        c = getattr(self.config, "derive", None)
        if not c or not getattr(c, "gravity_enabled", False):
            return
        key = self._him_key()
        if not key:
            return
        mirrored = self._mirror_primitives_closeness(key)
        now = self.clock.now_ts()
        last = self.store.get("rel_gravity_ts", 0) or 0
        if now - last < c.gravity_every_hours * 3600:
            return
        self.store.set("rel_gravity_ts", now)
        try:
            from sim.derive import derive_him
            cl, sd, te, _ = derive_him(self.config, self.store, now)
        except Exception:
            return
        elapsed_days = max(0.0, (now - last) / 86400.0) if last else c.gravity_every_hours / 24.0
        rel = self.relationships[key]
        for meter, target, rate in (("closeness", cl, c.gravity_closeness_per_day),
                                    ("standing", sd, c.gravity_standing_per_day),
                                    ("tension", te, c.gravity_tension_per_day)):
            if meter == "closeness" and mirrored:
                # how much of each other they have actually seen owns it now,
                # and the message record is not a second opinion about it
                continue
            cur = float(rel.get(meter, target))
            step = rate * elapsed_days
            if cur > target:
                rel[meter] = round(max(target, cur - step))
            elif cur < target:
                rel[meter] = round(min(target, cur + step))
        self.store.set("relationships", self.relationships)

    @staticmethod
    def him_key_in(config, relationships):
        """The row of a relationship table that is him: his name on the
        sheet, else the two conventions. None when the table has no him."""
        for k in (config.character.user_name.lower(), "him", "user"):
            if k in relationships:
                return k
        return None

    def _him_key(self):
        return self.him_key_in(self.config, self.relationships)

    def _him_tension(self, amount):
        """Move his tension meter mechanically, outside the model's daily
        budget. Withdrawal has to be able to build from plain neglect: the
        state model only runs when something happens, and being ignored is
        precisely the case where nothing does."""
        k = self._him_key()
        if not k or amount == 0:
            return
        cur = float(self.relationships[k].get("tension", 0))
        cap = float(self.config.state.world.tension_ignored_cap)
        if amount > 0 and cur >= cap:
            return
        self.relationships[k]["tension"] = clamp(min(cap, cur + amount) if amount > 0 else max(0.0, cur + amount))

    def things_happened(self, events, social_salience=0):
        """Mechanical: salient events and a notable X scroll leave things unsaid."""
        if "unsaid" not in self.gauges:
            return
        c = self.config.state
        add = 0
        for e in events or []:
            try:
                sal = int(e.get("salience", 1))
            except (TypeError, ValueError):
                sal = 1
            if sal >= int(c.salient_from):
                add += c.unsaid_per_salience * sal
        if social_salience >= int(c.salient_from):
            add += c.unsaid_social
        if add:
            self.gauges["unsaid"] = clamp(self.gauges["unsaid"] + add)

    # ---------------- catching his mood ----------------

    def note_his_mood(self, data):
        """What he sounds like, kept and faded. Before this his state reached
        her as content and as read receipts, and never as a state -- there was
        no route by which his being flat could make her flat, and co-regulation
        is most of what being with somebody consists of."""
        c = self.config.contagion
        if not c.enabled or not isinstance(data, dict):
            return
        try:
            v = max(-2.0, min(2.0, float(data.get("valence", 0))))
            a = max(-2.0, min(2.0, float(data.get("arousal", 0))))
        except (TypeError, ValueError):
            return
        # a null line is nothing to read, and `str(None)` is the four-letter
        # word "None", which is not empty: the guard passed and the word was
        # written into a save as his mood.
        line = data.get("line")
        line = "" if line is None else str(line).strip()
        if v == 0 and a == 0 and not line:
            return
        self.store.set("his_mood", {"ts": self.clock.now_ts(), "valence": v, "arousal": a,
                                    "line": line[:160]})

    def his_mood(self):
        """Faded: what he sounded like six hours ago is not what he is now."""
        c = self.config.contagion
        m = self.store.get("his_mood", {})
        if not m:
            return None
        hours = max(0.0, (self.clock.now_ts() - float(m.get("ts", 0))) / 3600.0)
        f = 0.5 ** (hours / max(0.1, c.half_life_hours))
        if f < c.forget_below:
            return None
        return {"valence": float(m.get("valence", 0)) * f, "arousal": float(m.get("arousal", 0)) * f,
                "line": m.get("line", ""), "faded": f, "hours": hours}

    def catch_his_mood(self):
        """Move her toward it. Automatic, unattributed, scaled by what he is to
        her -- you catch a partner's mood and not a stranger's -- and stronger
        downward than up, which is the asymmetry the research is clearest
        about. She is never told this happened."""
        c = self.config.contagion
        m = self.his_mood()
        if not (c.enabled and m):
            return None
        pull = self.sentiments.susceptibility() if self.sentiments else c.default_susceptibility
        v, a = m["valence"] / 2.0, m["arousal"] / 2.0
        strength = c.strength * pull * (c.negative_bias if v < 0 else 1.0)
        moved = []
        for gauge, weight in c.valence_gauges.items():
            amount = -v * weight * strength if weight > 0 else v * abs(weight) * strength
            if abs(amount) < 0.4:
                continue
            self._nudge(gauge, amount, c.soft_cap)
            moved.append(f"{gauge}{amount:+.0f}")
        for gauge, weight in c.arousal_gauges.items():
            amount = a * weight * strength
            if abs(amount) < 0.4:
                continue
            self._nudge(gauge, amount, c.soft_cap)
            moved.append(f"{gauge}{amount:+.0f}")
        if moved:
            self.save()
            logger.log(f"[contagion] he sounds {m['line'][:60] or 'off'} -- she has caught some of it "
                       f"(x{pull:.2f}): {', '.join(moved)}")
            # him being good to her is a release, not only a set of nudges
            st = self.stress
            if st and v > 0:
                st.relieve("warm_exchange")
        return moved

    def his_mood_line(self, ja=False):
        """What she has noticed, which is a different thing from what she has
        caught: noticing is hers to act on, catching happens to her."""
        m = self.his_mood()
        if not m or not m.get("line"):
            return ""
        return (f"彼の書き方に出ていたもの: {m['line']}" if ja else f"something in how he wrote: {m['line']}")

    # ---------------- the spec is the source of truth ----------------

    def refused_line(self):
        """What the model kept trying to write this run. An empty line here
        after a long run would mean the prompt and the schema agree."""
        if not self._refused:
            return ""
        bits = ", ".join(f"{k} x{v}" for k, v in sorted(self._refused.items(), key=lambda kv: -kv[1]))
        return f"deltas refused this run (computed gauges): {bits}"

    def movable(self):
        """Gauges the state model may move, derived from the spec. Adding an
        emotion should not mean remembering to edit a list somewhere else."""
        return [k for k, v in self.config.state.gauges.items() if v.get("model_may_move", True)]

    def gauge_tells(self):
        """What the state model is told about each gauge, rendered from the
        spec. A gauge carrying its own `tells` needs no edit to
        prompts/state.txt, which is the file that made adding one painful."""
        out = []
        movable = set(self.movable())
        for k, v in self.config.state.gauges.items():
            t = str(v.get("tells", "")).strip()
            if t and k in movable:
                out.append(f"{k} ({t})")
        return ", ".join(out)

    def delta_schema(self):
        """The deltas block of the output schema, rendered from the spec so it
        cannot drift from it. Hand-written, it disagreed with the gauge list
        above it in the same file."""
        return "{" + ", ".join('"' + k + '": 0' for k in self.movable()) + "}"

    def system_prompt(self):
        txt = self.config.prompt_text("state")
        return txt.replace("{{TELLS}}", self.gauge_tells()).replace("{{DELTAS}}", self.delta_schema())

    def wiring_report(self):
        """Whether each gauge is actually wired: who may move it, whether the
        state model is told about it, and what it has really done in the record.
        This is the standing check for the failure that keeps recurring -- a
        declared thing nothing can move, or a threshold nothing can reach."""
        import json as _json
        spec = self.config.state.gauges
        with self.store.lock:
            rows = self.store.conn.execute("SELECT gauges FROM state_log ORDER BY ts").fetchall()
        hist = [_json.loads(r[0]) for r in rows]
        movable = set(self.movable())
        lines = [f"{len(spec)} gauges, {len(hist)} recorded states", ""]
        head = "gauge".ljust(20) + "kind".ljust(9) + "base".rjust(4) + "  " + "writer".ljust(20) + "told".ljust(7) + "min".rjust(5) + "max".rjust(6) + "  note"
        lines.append(head)
        for k, v in spec.items():
            seen = [float(h[k]) for h in hist if k in h]
            base = float(v["baseline"])
            if v.get("kind") == "derived":
                writer = "computed"
            elif k in movable:
                writer = "state model + code"
            else:
                writer = "code only"
            if k not in movable:
                told = "n/a"
            elif v.get("tells"):
                told = "spec"
            else:
                told = "prompt"
            note = ""
            # "one-directional" only means something when there was room to go
            # the other way. guilt rests at 10 and awkwardness at 5, so of
            # course they have never been below it; affection rests at 45 and
            # has never once been under it, which is the same shape as the
            # failure mood had and is worth seeing.
            room = self.config.state.one_way_warn_from
            if not seen:
                note = "NEVER RECORDED"
            elif max(seen) <= base and min(seen) >= base:
                note = "NEVER MOVED"
            elif max(seen) <= base and (100 - base) >= room:
                note = "ONE-WAY: never above rest"
            elif min(seen) >= base and base >= room:
                note = "ONE-WAY: never below rest"
            lo = f"{min(seen):5.0f}" if seen else "    -"
            hi = f"{max(seen):6.0f}" if seen else "     -"
            lines.append(k.ljust(20) + str(v.get("kind", "?")).ljust(9) + f"{base:4.0f}" + "  "
                         + writer.ljust(20) + told.ljust(7) + lo + hi + "  " + note)
        return chr(10).join(lines)

    # ---------------- mood, which is computed and never written ----------------

    def affect(self, axis="valence"):
        """Signed sum over the gauges of how far each sits from its own rest,
        weighted by what kind of thing it is. A gauge at rest contributes
        nothing, so an unusually calm afternoon lifts her by the same mechanism
        that an anxious one puts her down."""
        c = self.config.state.mood_from
        points = {"emotion": c.emotion_points, "body": c.body_points, "drive": c.drive_points}
        total = 0.0
        for k, v in self.config.state.gauges.items():
            if v.get("kind") == "derived":
                continue
            sign = float(v.get(axis, 0) or 0)
            if not sign:
                continue
            base, cur, span = self._room(k, v)
            weight = points.get(v.get("kind"), 0.0) if axis == "valence" else c.arousal_points
            total += sign * ((cur - base) / span) * weight
        return total

    def _derive_mood(self, hours):
        """Mood follows its causes with a lag. The lag is the point: emotions
        have objects and fade in hours, mood has no object and takes most of a
        day, so a bad afternoon is still on her in the evening after the thing
        that caused it has gone."""
        c = self.config.state.mood_from
        for k, v in self.config.state.gauges.items():
            if v.get("kind") != "derived":
                continue
            delta = max(-c.max_swing, min(c.max_swing, self.affect("valence")))
            target = clamp(float(v["baseline"]) + delta)
            cur = self.gauges[k]
            step = c.inertia_per_hour * max(0.0, hours)
            if cur > target:
                self.gauges[k] = max(target, cur - step)
            elif cur < target:
                self.gauges[k] = min(target, cur + step)

    def body_noise(self):
        """How much of what she is feeling is actually her body, 0-1.

        People misattribute arousal from one source to another reliably, and
        she has no way to do it: `health.py` and `body.py` move her gauges, and
        the state model reads his message with no idea that she is running on
        five hours' sleep and has not eaten since noon. So a flat reply lands as
        distance rather than as low blood sugar, which is the single most human
        error available and the system could not make it."""
        c = self.config.state.body_noise
        if not c.enabled:
            return 0.0
        total = 0.0
        for gauge, weight in c.weights.items():
            spec = self.config.state.gauges.get(gauge)
            if not spec:
                continue
            base, cur, span = self._room(gauge, spec)
            # only the direction that feels bad counts: being well rested does
            # not make her read him more generously, it just does not distort
            dev = (cur - base) / span
            total += max(0.0, dev * weight)
        # stress is not a body signal; it is what makes her worse at telling one
        # from a mood. Wound up, the same empty stomach explains more of how his
        # message just landed, and she credits it even less than usual.
        st = self.stress
        if st:
            total *= st.multiplier("body_noise")
        return min(1.0, total)

    def body_noise_line(self):
        c = self.config.state.body_noise
        v = self.body_noise()
        if v < c.report_from:
            # the other direction: a wound-up head with nothing wrong in the
            # body reads itself as the body. Only when the body really is
            # near rest, or the two lines would contradict each other.
            g = self.gauges
            spec = self.config.state.gauges
            anx = float(g.get("anxiety", 0)) - float(spec["anxiety"]["baseline"])
            st = float(g.get("stress", 0)) if "stress" in g else 0.0
            if v < c.reverse_body_under and (anx >= c.reverse_anxiety_over or st >= c.reverse_stress_over):
                return ("HER HEAD IS IN HER BODY: anxiety and strain are high and nothing is physically wrong. She reads "
                        "it as her body -- a stomach that will not settle, not being hungry, 'coming down with something', "
                        "tired for no reason -- and does not know it is nerves. If she mentions feeling off, that is what "
                        "it is; do not have her name the cause.")
            return ""
        g = self.gauges
        bits = []
        if g.get("energy", 100) < 40:
            bits.append("running on nothing")
        if g.get("hunger", 0) > 60:
            bits.append("has not eaten")
        if g.get("unwell", 0) > 30:
            bits.append("feels ill")
        if g.get("physical_comfort", 100) < 40:
            bits.append("physically uncomfortable")
        return (f"HER BODY IS HAVING A BAD TIME OF IT ({', '.join(bits) or 'run down'}). She will not be "
                f"crediting any of that for how the last hour has landed. An ambiguous or flat message from "
                f"him reads worse than it is right now, and a small thing lands as a bigger one; move what "
                f"that actually does to her and do not have her notice why.")

    def mood_state(self, ja=False):
        """What sort of state she is in, rather than what number she is at. A
        number gates nothing: the `mood < 30` branch in this file had never once
        executed in 112 recorded states, because mood could not get there."""
        c = self.config.state.mood_from
        # valence comes off the mood gauge, which lags its causes -- if it came
        # off the instantaneous affect the lag would never reach anything she
        # says, and the lag is the whole difference between a mood and a readout.
        # Arousal is instantaneous: being activated is not a mood.
        base = float(self.config.state.gauges["mood"]["baseline"])
        v = max(-1.0, min(1.0, (float(self.gauges.get("mood", base)) - base) / c.max_swing))
        a = max(-c.arousal_swing, min(c.arousal_swing, self.affect("arousal"))) / c.arousal_swing
        up, down = a >= 0.2, a <= -0.2
        if ja:
            if v <= -0.45:
                return "ひりひりしている" if up else ("空っぽ" if down else "沈んでいる")
            if v <= -0.15:
                return "とげとげしている" if up else ("平ら" if down else "調子が悪い")
            if v >= 0.45:
                return "浮ついている" if up else ("あたたかくて落ち着いている" if down else "明るい")
            if v >= 0.15:
                return "気が立っている" if up else ("楽" if down else "まあまあ")
            return "普通"
        if v <= -0.45:
            return "raw" if up else ("hollowed out" if down else "low")
        if v <= -0.15:
            return "brittle" if up else ("flat" if down else "off")
        if v >= 0.45:
            return "buzzing" if up else ("warm and settled" if down else "bright")
        if v >= 0.15:
            return "keyed up" if up else ("easy" if down else "alright")
        return "even"

    def blends(self):
        """Two feelings both up at once that do not cancel, named. A person
        can want him and be furious with him in the same minute; the gauges
        held both and nothing said so, so the mood valence summed them to
        "even". Config `state.blends`: each fires when both gauges are at or
        past `at`. Prompt-facing (mood tags, the reports); moves nothing."""
        out = []
        g = self.gauges
        for b in (self.config.state.blends or []):
            try:
                a, bb, at = b["a"], b["b"], b.get("at", [50, 50])
                if float(g.get(a, 0)) >= float(at[0]) and float(g.get(bb, 0)) >= float(at[1]):
                    out.append(b["text"])
            except Exception:
                continue
        return out[:2]

    def body_settled_line(self):
        """Once, after her body came right: the state call is told that some of
        how the last hours landed was hunger or exhaustion, and may let her
        notice or not. Cleared on read."""
        note = self.store.get("body_settled_note", {}) or {}
        if not note:
            return ""
        if self.clock.now_ts() - float(note.get("ts", 0)) > 3 * 3600:
            self.store.set("body_settled_note", {})
            return ""
        self.store.set("body_settled_note", {})
        return note.get("text", "")

    def _body_settle_check(self):
        """The correction half of misattribution: when body noise drops from
        past `report_from` to under `clear_below` (she ate, she slept), part of
        the anger / anxiety / sadness that was really her body comes off
        mechanically, and the next state call is told once. Edge-triggered
        on kv, with a cooldown, because decay polls."""
        c = self.config.state.body_noise
        now = self.clock.now_ts()
        v = self.body_noise()
        prev = self.store.get("body_noise_prev", {}) or {}
        pv = float(prev.get("v", 0.0))
        relieved = float(prev.get("relieved_ts", 0) or 0)
        self.store.set("body_noise_prev", {"v": round(v, 3), "ts": now, "relieved_ts": relieved})
        if not (pv >= c.report_from and v <= c.clear_below):
            return
        if now - float(prev.get("relieved_ts", 0) or 0) < c.relief_cooldown_hours * 3600:
            return
        moved = []
        for g in c.relief_gauges:
            spec = self.config.state.gauges.get(g)
            if not spec or g not in self.gauges:
                continue
            base = float(spec["baseline"])
            cur = float(self.gauges[g])
            if cur <= base:
                continue
            amt = (cur - base) * c.relief * pv
            self.gauges[g] = max(base, cur - amt)
            moved.append(f"{g} -{amt:.0f}")
        self.store.set("body_noise_prev", {"v": round(v, 3), "ts": now, "relieved_ts": now})
        if moved:
            logger.log(f"[state] her body settled (noise {pv:.2f} -> {v:.2f}); some of the last hours was that: {', '.join(moved)}")
            self.store.set("body_settled_note", {"ts": now, "text": (
                "HER BODY HAS JUST COME RIGHT (she ate, or slept, or got comfortable). Part of how the last hours landed "
                "was that and not him, and it has already been taken off the numbers. She may notice it -- 'ok that was "
                "mostly being hungry' -- or not; either is human. Do not re-charge what the body explained.")})

    def affect_report(self):
        """The grid, and what is missing from it. An empty cell is not a gap in
        the data, it is a feeling she cannot have."""
        spec = self.config.state.gauges
        grid = {}
        for k, v in spec.items():
            if v.get("kind") != "emotion":
                continue
            grid.setdefault((int(v.get("valence", 0)), int(v.get("arousal", 0))), []).append(k)
        lines = [f"mood {self.gauges['mood']:.0f} = {self.mood_state()}  "
                 f"(valence {self.affect('valence'):+.1f}, arousal {self.affect('arousal'):+.1f}; computed, never written)"]
        if self.refused_line():
            lines.append(self.refused_line())
        for b in self.blends():
            lines.append(f"mixed: {b}")
        if self.config.state.affection_from.enabled and "affection" in self.gauges:
            lines.append(f"affection {self.gauges['affection']:.0f}, heading for "
                         f"{self.affection_target():.0f} (computed, never written)")
        lines.append("")
        lines.append("the emotion grid:")
        for val, vname in ((1, "good"), (0, "neither"), (-1, "bad")):
            for aro, aname in ((1, "activating"), (0, "neutral"), (-1, "deactivating")):
                who = grid.get((val, aro), [])
                # a valence-neutral "emotion" is not a thing she is missing, so
                # only the rows that carry a valence count as gaps
                mark = "  " if (who or val == 0) else "  << EMPTY: a feeling she cannot have"
                lines.append(f"  {vname:8s} / {aname:13s} {', '.join(who) or '-':40s}{mark}")
        lines.append("")
        for k, v in sorted(spec.items(), key=lambda kv: (kv[1].get("kind", ""), kv[0])):
            cur = self.gauges.get(k, 0)
            lines.append(f"  {k:20s} {cur:5.0f}  base {v['baseline']:3}  {v.get('kind', '?'):8s} "
                         f"valence {int(v.get('valence', 0)):+d} arousal {int(v.get('arousal', 0)):+d}")
        return "\n".join(lines)

    def _baseline(self, gauge):
        try:
            return float(self.config.state.gauges[gauge]["baseline"])
        except Exception:
            return 50.0

    def over_rest(self, gauge):
        """How far the gauge sits from its rest, signed, in gauge units: the
        number every reader that asks "is she more anxious than usual" wants,
        and that nine of them computed by hand. Positive is above rest."""
        return float(self.gauges.get(gauge, 0)) - self._baseline(gauge)

    def _room(self, gauge, spec):
        """(rest, now, room): the gauge's rest, where it sits, and the room on
        the side it sits -- above rest the room is up to 100, below it the
        room is down to 0 -- so a deviation reads as a fraction of what was
        possible in that direction (invariant 4, docs/state.md)."""
        base = float(spec["baseline"])
        cur = float(self.gauges.get(gauge, base))
        return base, cur, max(1.0, (100.0 - base) if cur >= base else base)

    def _stress_gain(self, gauge, amount):
        """Stress amplifies what lands badly on a gauge it is named for.

        Only upward, and only for the bad direction: being wound up does not
        make good news better, it makes a bad thing land as a worse one. The
        lookup is against `config.stress.compounds`, so this is the reader for
        any compound that shares a gauge's name and a new one needs no code."""
        try:
            if amount <= 0 or gauge not in self.config.stress.compounds:
                return amount
            st = self.stress
            return amount * st.multiplier(gauge) if st else amount
        except Exception:
            return amount

    def _settle(self, gauge, amount):
        """A release relaxes a gauge toward rest, never past it. Answering her
        satisfies an itch; it does not make her less curious than she is by
        nature. Flat releases with a 0-100 clamp drove straight through the
        baseline to the floor: over 74 samples curiosity sat at a median of 6
        against a baseline of 40 and jealousy never once rose above its own
        baseline of 15, because every message he sent took 15 and 12 off them
        while the things that raise them work in points per hour."""
        if gauge not in self.gauges or amount <= 0:
            return
        base = self._baseline(gauge)
        cur = self.gauges[gauge]
        if cur > base:
            self.gauges[gauge] = max(base, cur - amount)

    def _nudge(self, gauge, amount, soft_cap=95, soft_floor=0.0):
        """A signed mechanical move that loses value near whichever end it is
        heading for.

        `_warm` only goes up and `_settle` only goes toward rest, so **nothing
        in the system could push a gauge below its baseline mechanically**.
        Contagion found this the hard way: his being flat was supposed to take
        her energy and her affection down and did exactly nothing, silently,
        because both were sitting at their baselines."""
        if gauge not in self.gauges or not amount:
            return
        if amount > 0:
            self._warm(gauge, amount, soft_cap)
            return
        cur = self.gauges[gauge]
        room = max(0.0, cur - soft_floor) / max(1.0, 100.0 - soft_floor)
        self.gauges[gauge] = clamp(cur - abs(amount) * min(1.0, room))

    def _warm(self, gauge, amount, soft_cap):
        """A bump with the headroom taken out of it. A flat +6 per message put
        affection at 99 and held it there, and a gauge parked at the ceiling
        cannot signal anything. Full value at rest, nothing left near the cap."""
        if gauge not in self.gauges or amount <= 0:
            return
        amount = self._stress_gain(gauge, amount)
        base = self._baseline(gauge)
        cur = self.gauges[gauge]
        span = max(1.0, soft_cap - base)
        gain = amount * max(0.0, (soft_cap - cur)) / span
        self.gauges[gauge] = clamp(cur + gain)

    def his_attention(self):
        """He answered: the hunger is fed a little, mechanically, before the model reads the tone."""
        w = self.config.state.world
        if w.enabled:
            self._settle("validation_craving", w.attention_craving_release)
            self._settle("curiosity", w.attention_curiosity_release)
            # and he is the supply, for a character who has no other one. This
            # is the other half of the drain in `decay`: a day of silence takes
            # it out of her and a message from him puts some back, so what he
            # does costs and pays in the same currency. Zero by default.
            back = float(getattr(w, "attention_energy_release", 0.0) or 0.0)
            if back and "energy" in self.gauges:
                # 80 rather than the ceiling: talking to him lifts her out of
                # the flat, it does not leave her fully wound up, and a gauge
                # parked at its cap signals nothing.
                self._warm("energy", back, 80)
            # he is here: jealousy about who else he was with cools. Warmth
            # toward him is not bumped here any more -- it follows from
            # this, from the tension coming off and from the relief below.
            self._settle("jealousy", w.attention_jealousy_release)
            # he came back: the hardness goes off faster than it came on,
            # but not instantly -- one message does not undo a day of silence
            self._him_tension(-w.attention_tension_release)
            # and the waiting is over, which is a feeling of its own rather
            # than just less anxiety
            self._warm("relief", w.attention_relief_bump, w.attention_relief_soft_cap)
            # and a hundred evenings of this is what attachment is made of
            if self.sentiments:
                self.sentiments.move(self._him_key() or "him", "attachment",
                                     self.config.sentiment.attention_attachment)
        # and what all of that adds up to as warmth, now rather than at the
        # next decay: he is owed a reaction inside the exchange
        self._derive_affection(self.config.state.affection_from.on_event_hours)

    def apply(self, deltas, rel_deltas, fresh=True):
        """Model deltas, with three mechanical rules the model cannot be
        trusted to keep: diminishing returns near the ends of a gauge (a +3
        at mood 85 is worth less than at 50), relationship meters that move
        at day speed (a per-day budget per meter), so one good morning is a
        step, not the whole staircase -- and habituation.

        Habituation: with nothing new from him (`fresh` False), a delta that
        pushes a gauge the same way as the last tick is scaled by
        `repeat_factor` per repeat. On 2026-08-26 anger sat at 80 and mood at
        10 for eleven hours because every tick re-read "he said engineer me
        and then left" and charged it again; the decay (7/hour on anger)
        never got a word in. A standing situation is charged when it
        begins. What it does after that is the decay's business."""
        c = self.config.state
        cap = c.max_delta_per_update
        hab = c.habituation
        if fresh:
            self._standing = {}
        habituated = []
        # what the model may move comes off the spec, not a second list
        mech = set(self.gauges) - set(self.movable())
        # A computed gauge is refused here rather than merely left out of the
        # prompt. Leaving it out is what failed before: mood was described in
        # the state prompt's own output schema and written every tick by the
        # same call that wrote its causes, so it drifted up and never down.
        derived = {k for k, v in c.gauges.items() if v.get("kind") == "derived"}
        for k, d in (deltas or {}).items():
            # a delta the model may not send is refused out loud. Dropping
            # it silently is how a gauge ends up with a writer nobody can
            # find; an unknown key is not one of these and stays quiet.
            if k in derived or (k in self.gauges and k in mech):
                # once per gauge per run, then counted. The model returns a
                # mood delta however plainly the prompt says not to, and a
                # line every tick buries the events worth reading.
                seen = self._refused.get(k, 0) + 1
                self._refused[k] = seen
                if seen == 1:
                    logger.log(f"[state] refused a delta to '{k}': it is computed from its "
                               f"causes, not written (said once; /gauges has the count)")
                continue
            if k in self.gauges and k not in mech:
                try:
                    d = int(d)
                except (TypeError, ValueError):
                    continue
                d = max(-cap, min(cap, d))
                if hab.enabled and d and not fresh:
                    sign = 1 if d > 0 else -1
                    prev = self._standing.get(k) or {}
                    n = int(prev.get("n", 0)) + 1 if prev.get("dir") == sign else 0
                    self._standing[k] = {"dir": sign, "n": n}
                    if n:
                        f = hab.repeat_factor ** min(n, hab.max_repeats)
                        habituated.append(f"{k} {d:+d}->{d * f:+.1f} (x{n})")
                        d = d * f
                elif d:
                    self._standing[k] = {"dir": 1 if d > 0 else -1, "n": 0}
                # the same amplification the mechanical sites get, so a shameful
                # thing the model reports lands as hard as one the code raised
                d = self._stress_gain(k, d)
                cur = self.gauges[k]
                if c.diminishing_returns and d:
                    # room left in the direction of travel, 0..1; a delta into a
                    # crowded end is scaled down (never below a third)
                    room = (100 - cur) / 100.0 if d > 0 else cur / 100.0
                    d = d * max(0.34, min(1.0, room * 2))
                self.gauges[k] = clamp(cur + d)
        if habituated:
            logger.log("[state] habituated (same thing as last tick, nothing new from him): " + ", ".join(habituated))
        today = self.clock.date_str()
        spent = self.store.get("rel_delta_spent", {})
        if spent.get("_date") != today:
            spent = {"_date": today}
        for name, ch in (rel_deltas or {}).items():
            person = self._match_person(name)
            if not person or not isinstance(ch, dict):
                # a name nobody owns is still a name the model spent a move on;
                # dropping it in silence hid a fifth of them for a week
                if isinstance(ch, dict):
                    logger.log(f"[state] relationship move for a name the roster does not know, dropped: {name!r} {ch}")
                continue
            for meter in ("closeness", "standing", "tension"):
                if meter in ch:
                    if meter == "closeness" and person == self._him_key() and self.primitives is not None:
                        # derived, like mood and affection, and refused at the
                        # write site for the same reason: it is the smaller of
                        # the two exposures, and the model spent eight points a
                        # day of its budget writing over it
                        self._refused["him.closeness"] = self._refused.get("him.closeness", 0) + 1
                        continue
                    try:
                        d = int(ch[meter])
                    except (TypeError, ValueError):
                        continue
                    d = max(-cap, min(cap, d))
                    key = f"{person}:{meter}"
                    used = spent.get(key, 0)
                    budget = c.relationship_daily_budget
                    if abs(used + d) > budget:
                        d = max(-budget - used, min(budget - used, d)) if abs(used) < budget else 0
                    if not d:
                        continue
                    spent[key] = used + d
                    self.relationships[person][meter] = clamp(self.relationships[person].get(meter, 50) + d)
        self.store.set("rel_delta_spent", spent)

    def _match_person(self, name):
        """Which entry in `relationships` a name the model wrote is about.

        This used to lowercase the name and strip `-chan`, so it resolved the
        roster handle and nothing else. The state model is shown the exchange
        it has just read, where everybody is named as the record names them
        (古賀海斗, 香芝玲奈), and it keys its relationship deltas the same way;
        the meters are keyed by the handle (`Kaito`, `Rena-chan`). Every
        delta under a Japanese name fell through the `continue` above without
        a log line: 35 of the 133 moves the model sent between 2026-08-25 and
        2026-09-01, worth 74 meter points, all of them for a person she had
        just spent time with. Names resolve in one place, `sim/roster.py`."""
        from sim import roster
        role = roster.role_of(self.config, name)
        if role:
            for p in self.relationships:
                # `relationships` is keyed by the roster handle today and may
                # be keyed by role_id later; the roster resolves both, so this
                # holds either way
                if p == role or roster.role_of(self.config, p) == role:
                    return p
        n = str(name or "").strip().lower()
        if n in ("user", "he", "him", "the user"):
            return self._him_key()
        # the roster goes quiet when it cannot read `data/cast.json`; an exact
        # handle still resolves then, and an exact handle cannot fold two
        # people into one the way the old substring folding could
        if not role:
            for p in self.relationships:
                if p.lower() == n:
                    return p
        return None

    def gauge_line(self):
        return ", ".join(f"{k} {int(v)}" for k, v in self.live_gauges().items())

    def owner_off(self, key):
        """Is the section that writes this gauge switched off for her?

        A gauge whose owner is off is not a feeling resting at its baseline.
        It is a feeling she has not got, and printing it is printing a
        constant: the fourth character's warmth toward him read exactly 45 and
        her missing him exactly 0 on all 220 status lines of 2026-09-07, both
        computed from a relationship her sheet denies.

        `Config.REQUIRES` decides which sections a kind of character has and
        switches the rest off by setting `enabled` false, so this is one
        lookup against that answer rather than a second table that could
        disagree with it."""
        owner = (self.config.state.gauges.get(key) or {}).get("owner")
        if not owner:
            return False
        section = getattr(self.config, str(owner), None)
        return section is not None and not getattr(section, "enabled", True)

    def live_gauges(self):
        """Her gauges, without the ones nothing left in her build can move."""
        return {k: v for k, v in self.gauges.items() if not self.owner_off(k)}

    # ---------------- where a feeling comes from ----------------

    def sources(self, ja=False):
        """Every feeling that is up has a source, and the source is not
        whoever she happens to be talking to. {gauge: (who, why)} for the
        gauges something on record explains: an open rupture and a live
        withholding point at him; a person's resentment / envy sentiment
        points at that person; nothing else is claimed.

        `ja` is for the copy that goes in front of her; `shape.py` and the
        cast prompts read the same reasons in English."""
        t = lang.pick(ja)
        out = {}
        g = self.gauges
        c = self.config.state.sources
        him = self._him_key() or "him"
        rp = self.ruptures
        r = rp.open_one() if rp and self.config.rupture.enabled else None
        if r:
            for k in self.config.rupture.holds_gauges:
                if g.get(k, 0) >= c.min_level:
                    out[k] = (him, t(f"the thing between them that nobody has fixed: {str(r.get('what', ''))[:90]}",
                                     f"二人のあいだで誰も直していないこと: {str(r.get('what', ''))[:90]}"))
        wh = self.withholding
        w = wh.live() if wh else None
        if w:
            for k in ("anger", "sadness"):
                if g.get(k, 0) >= c.min_level and k not in out:
                    out[k] = (him, t(f"what she is keeping from him: {str(w.get('why', ''))[:90]}",
                                     f"彼に言わずにいること: {str(w.get('why', ''))[:90]}"))
        sen = self.sentiments
        if sen:
            for who in list(self.relationships):
                if who == him:
                    continue
                try:
                    res = sen.live(who, "resentment")
                    env = sen.live(who, "envy")
                except Exception:
                    res, env = 0.0, 0.0
                if res >= c.sentiment_from and g.get("anger", 0) >= c.min_level and "anger" not in out:
                    out["anger"] = (who, t(f"resentment of {who} ({res:.0f}/100)", f"{who}へのわだかまり（{res:.0f}/100）"))
                if env >= c.sentiment_from and g.get("shame", 0) >= c.min_level and "shame" not in out:
                    out["shame"] = (who, t(f"measuring herself against {who} and coming off worse",
                                           f"{who}と自分を比べて、負けているように感じている"))
        return out

    def directed_line(self, who):
        """For a prompt about her with `who`: which of her feelings are aimed
        at somebody else (they show as being elsewhere, not as an edge on
        this person), and which are aimed at this very person."""
        src = self.sources()
        if not src:
            return ""
        him = self._him_key() or "him"
        at_them, elsewhere = [], []
        for k, (target, why) in src.items():
            lvl = self.gauges.get(k, 0)
            if target == who:
                at_them.append(f"{k} {lvl:.0f}: {why}")
            else:
                name = "him, the man she texts" if target == him else target
                elsewhere.append(f"{k} {lvl:.0f} is at {name} ({why})")
        parts = []
        if elsewhere:
            parts.append("NOT AT " + who.upper() + ": " + "; ".join(elsewhere)
                         + ". With " + who + " it shows only as being somewhere else -- shorter, slower, half-listening -- never as an edge on them, and its cause is not said")
        if at_them:
            parts.append("AT " + who.upper() + ": " + "; ".join(at_them) + ". This one is theirs to feel")
        return ". ".join(parts)

    def mood_tags(self, ja=False):
        """`ja` is for the one caller that is speaking TO her -- her situation
        block. The twenty others are mechanism prompts about her, in the third
        person, and they keep the English (`sim/lang.py`)."""
        from sim.lang import gauge_ja, feeling_ja, control
        def feel(text):
            # the config states one wording per feeling; the other language's
            # is in `sim/lang.py`, so both survive and either can be selected
            return feeling_ja(text) if ja else text
        g = self.gauges
        tags = []
        # A running spiral has to reach here, because mood_tags is the only
        # state channel the voice fallback gets and the only one twelve other
        # callers share. A level cannot say what she is going over.
        sp = self.spirals
        if sp:
            try:
                t = sp.mood_tag()
                if t:
                    tags.append(t)
            except Exception:
                pass
        def lvl(v):
            if ja:
                return "とても低い" if v < 20 else "低い" if v < 40 else "中くらい" if v < 60 else "高い" if v < 80 else "とても高い"
            return "very low" if v < 20 else "low" if v < 40 else "middling" if v < 60 else "high" if v < 80 else "very high"
        def named(key):
            return f"{gauge_ja(key) if ja else key} {lvl(g[key])}"
        # A gauge read by name crashes for a character who does not have it.
        # `energy` measures a body having a day, and a character who lives in
        # a machine declares it absent (temperament.gauges_absent), so this is
        # not a missing value to default -- it is a thing she has not got, and
        # the honest output is no tag rather than "energy middling".
        energy_first = False
        if "energy" in g:
            tags.append(named("energy"))
            energy_first = True
        # the state she is in, not the number she is at
        tags.append((f"機嫌は{self.mood_state(ja=True)}" if ja else f"your mood is {self.mood_state()}"))
        for b in self.blends():
            tags.append((f"しかも混ざっている: {feel(b)}" if ja else f"and it is mixed: {b}"))
        tags.append(named("anxiety"))
        tags.append(named("loneliness"))
        tags.append(named("boredom"))
        tags.append(named("validation_craving") if ja else f"craving attention {lvl(g['validation_craving'])}")
        if "physical_comfort" in g:
            if ja:
                tags.append("体は" + ("しんどい" if g["physical_comfort"] < 40 else "楽" if g["physical_comfort"] > 60 else "まあまあ"))
            else:
                tags.append(f"physically {'uncomfortable' if g['physical_comfort'] < 40 else 'comfortable' if g['physical_comfort'] > 60 else 'okay'}")
        # any gauge carrying `tags` in the spec renders itself here, highest
        # threshold that fits and no more, so a new feeling reaches what she
        # says without a line being added to this method
        # a negative threshold is a LOW tag: -30 fires at or below 30. The
        # most extreme fitting tag wins in either direction, which is why the
        # lows sort by -|t| after the highs.
        felt = []
        for k, v in self.config.state.gauges.items():
            if self.owner_off(k):
                continue
            # highs from the highest threshold down, then lows from the
            # lowest up (the key sorted highs ascending until 08-26: anger 79
            # read as "irritated under it" in every prompt)
            ordered = sorted([t for t in (v.get("tags") or []) if t[0] >= 0], key=lambda t: -t[0]) +                       sorted([t for t in (v.get("tags") or []) if t[0] < 0], key=lambda t: -t[0])
            for threshold, text in ordered:
                if (threshold >= 0 and g.get(k, 0) >= threshold) or (threshold < 0 and g.get(k, 0) <= -threshold):
                    felt.append(feel(text))
                    break
        # what she feels comes before how much energy she has: the named
        # feelings lead the line, the levels follow. The energy tag is
        # recognised by having been written, not by the words it starts with:
        # in her language it does not start with "energy".
        # The control arm keeps the test it has always used -- "does the first
        # tag start with the word energy" -- because that is what every
        # measurement so far was taken under, and the tidy test could in
        # principle disagree with it (a spiral tag that opened with the word).
        # Every other arm asks whether the first tag IS the energy tag, which
        # is the only form of the question that survives translation.
        if control(self.config):
            lead = 1 if tags and not tags[0].startswith("energy ") else 0
        else:
            lead = 1 if tags and not (energy_first and tags[0] == named("energy")) else 0
        tags[lead:lead] = felt
        if g.get("unsaid", 0) >= 60:
            tags.append("今日は言えていないことが多い" if ja else "a lot left unsaid today")
        if g.get("curiosity", 0) >= 80:
            tags.append("彼が何をしているのか見にいきたくてうずうずしている" if ja else "itching to check what he is up to")
        elif g.get("curiosity", 0) >= 65:
            tags.append("彼が何をしているのか気になる" if ja else "curious what he is up to")
        if g.get("jealousy", 0) >= 65:
            tags.append("彼が他の誰と時間を使っているのかが刺さっている" if ja else "needled about who else he is spending time with")
        elif g.get("jealousy", 0) >= 45:
            tags.append("彼に対して小さくやきもちの角が立っている" if ja else "a small jealous edge about him")
        if g.get("guilt", 0) >= 55:
            tags.append("彼との終わり方がうしろめたくて、埋め合わせたい" if ja else "guilty about how she left it with him, wants to make up")
        elif g.get("guilt", 0) >= 40:
            tags.append("彼にそっけなくしたことが少し引っかかっている" if ja else "a little bad about being short with him")
        # the English half names the first character's dialect, which is hers
        # and nobody else's: a shared line with one person's accent in it is
        # the fault `tools/isolation.py` exists for, and the second character
        # was being told an accent she has never had was slipping.
        if g.get("awkwardness", 0) >= 55:
            tags.append("きまずい: 彼について知ってしまって取り消せないことがあり、それでも普通にしていないといけない。しゃべりが素に近づく"
                        if ja else
                        "squirming: she knows something about him she cannot unknow and has to be normal at him anyway; her guard is down and her talk is closer to her own")
        elif g.get("awkwardness", 0) >= 35:
            tags.append("彼に対して少し調子が狂っている。持ち出すつもりのないものを抱えている"
                        if ja else "slightly off with him, holding something you are not going to bring up")
        for t in (self.body_tags or []):
            tags.append(t)
        for t in (self.need_tags or []):
            tags.append(t)
        cap = int(getattr(getattr(self.config, "situation_block", None), "feel_tags_max", 0) or 0)
        return ", ".join(tags[:cap] if cap else tags)

    def felt_hours(self, hours):
        """How long his silence feels, as against how long it is.

        Waiting is not measured in hours by anybody. Her sense of it stretches
        with the gauges that make waiting hurt and compresses when she is
        occupied, and she has no idea it is doing either.

        **Prompt-facing only.** `impulse.score` keeps the true figure: anxiety
        and craving are already weights in there, so feeding it a number those
        same gauges inflated would count them twice."""
        c = self.config.state.felt_time
        if not c.enabled or hours <= 0:
            return hours
        pull = 0.0
        for gauge, weight in c.weights.items():
            spec = self.config.state.gauges.get(gauge)
            if not spec:
                continue
            base, cur, span = self._room(gauge, spec)
            pull += ((cur - base) / span) * weight
        felt = hours * max(c.min_factor, min(c.max_factor, 1.0 + pull))
        # and an hour he is never about in is not an hour of being ignored.
        # Four months of record say where three in the morning sits against
        # nine in the evening; nobody had to tell her.
        r = self.rhythm
        if r:
            try:
                felt *= r.silence_factor()
            except Exception:
                pass
        return felt

    def felt_gap_text(self, hours, ja=False):
        """What she would say it has been. Never a decimal; nobody thinks in
        1.7 hours."""
        felt = self.felt_hours(hours)
        if felt < 1:
            return ""
        if felt < 24:
            k = int(round(felt))
            if ja:
                return f"彼から何も来ていないのが、体感で{k}時間くらい"
            return f"he has not said anything for what feels like about {k} hour{'s' if k != 1 else ''}"
        d = felt / 24.0
        if ja:
            return ("彼から何も来ていないのが、体感で一日以上" if d < 2
                    else f"彼から何も来ていないのが、体感で{int(round(d))}日くらい")
        return ("he has not said anything for what feels like over a day" if d < 2
                else f"he has not said anything for what feels like about {int(round(d))} days")

    def register(self, ja=False):
        """How she is answering him right now, mechanically: from tension, mood, craving, energy.

        `ja` is the one caller that puts this in front of her (`sim/lang.py`);
        the reports and the operator's view read it about her, in English."""
        t = lang.pick(ja)
        m = self.config.delivery.mood_delivery
        him = self.relationships.get("him", {})
        tension = int(him.get("tension", 10))
        g = self.gauges
        # Fright comes before everything, including a strategy: a person who
        # cannot call what the other one does next and knows he can do her
        # harm is not running a bet about the relationship. What it looks like
        # is measured rather than imagined -- ten 「どうしよう」 before dialling
        # one listener's house, 「怖い怖い怖い」 when an authority chain got too
        # long -- and it is repetition and abandonment, not eloquence.
        prim = self.primitives
        pkey = self._him_key() or "him"
        # Where she has a stance table, being frightened of him and having been
        # put back outside are its rows 1 and 2 (`sim/stances.py`): they say
        # what she does with what she saw, which is not what a register says.
        # The chain keeps them for a character who has no stances.
        st = self.stances
        staged = bool(st is not None and st.enabled)
        if prim is not None and not staged:
            try:
                fright = prim.unrehearsed(pkey)
            except Exception:
                fright = 0.0
            if fright >= self.config.primitives.fright_from:
                hard = fright >= self.config.primitives.fright_hard_from
                return (t("frightened, and it does not come out as eloquence: the same short thing several times over, "
                          "sentences abandoned partway, asking what to do rather than saying anything, "
                          "and no joke to land it on",
                          "怖い。そしてそれは流暢さにはならない。同じ短い言葉を何度も繰り返し、"
                          "文を途中で捨て、何か言うよりどうしたらいいかを訊き、落とすための冗談も出てこない")
                        if hard else
                        t("wary and off balance: shorter than she means to be, checking rather than offering, "
                          "and not sure this is allowed",
                          "警戒していて足元が定まらない。思っているより短くなり、差し出すより確かめにいき、"
                          "これをしていいのかが分からない"))
        # a strategy under threat is a stance, and it comes before a mood
        att = self.attachment
        if att and att.register_line():
            return att.register_line(ja=ja)
        # The territory, which sorts people rather than scoring them. This is
        # above the mood chain on purpose: the whole of her fifth driver is
        # that the sorting decides which register exists, and the mood then
        # plays inside it. Putting it below would have let a cold affection
        # hand somebody she never admitted the clipped, faintly cruel register
        # that in 47 hours of tape goes at staff and never once at a listener.
        if prim is not None and not staged:
            try:
                inside = prim.admitted(pkey)
            except Exception:
                inside = True
            if not inside:
                return t("careful the way she is with anyone she has not let in: proper, a little formal, "
                         "explains herself more than she needs to, asks whether a thing is allowed, "
                         "and none of the easiness she keeps for the people who are inside",
                         "中に入れていない相手にいつもそうであるように、慎重。きちんとしていて少し他人行儀で、"
                         "必要以上に自分の説明をして、していいことかどうかを訊く。"
                         "中にいる人たちにだけ出す気安さは出てこない")
        # the body before the mood: wiped is wiped whatever she feels about him
        sit = self.situation
        if sit:
            try:
                sl = sit.register_line()
                if sl:
                    return sl
            except Exception:
                pass
        # gone off him comes before a mood: it is what every mood lands on
        aff = float(g.get("affection", 50))
        if aff <= m.affection_hate_from:
            return t("she does not like him right now and is not hiding it well: clipped, a little cruel at the edges, "
                     "answers the question and nothing else, ends things first",
                     "いま彼のことが好きではなく、それが隠しきれていない。短く切って、端のほうが少し意地悪で、"
                     "訊かれたことだけ答え、先に話を終わらせる")
        if aff <= m.affection_cold_from:
            return t("cold: answering because the message is there, not because she wants to; short, flat, no questions "
                     "back, nothing of her day offered",
                     "冷たい。来たから返しているだけで、返したいから返しているのではない。短く、平坦で、"
                     "訊き返さず、自分の一日のことも出さない")
        if g.get("surprise", 0) >= m.surprise_register:
            return t("caught off guard: a beat late, shorter than she meant to be, answering the thing that just "
                     "happened before anything she had been going to say",
                     "不意を突かれている。一拍遅れて、思っていたより短く、"
                     "言うつもりだったことより先に、いま起きたことに返している")
        if g.get("shame", 0) >= m.shame_register:
            return t("small and careful, giving him almost nothing; something happened that she cannot "
                     "stand having been seen and she would rather not be looked at, including by him",
                     "小さく、慎重で、彼にほとんど何も渡していない。見られたことが耐えられない何かがあって、"
                     "彼にも含めて、あまり見られたくない")
        if g.get("anger", 0) >= m.anger_register:
            return t("clipped and a bit sharp, and it is not really aimed at him; she is still chewing "
                     "something somebody else did and it is coming out in how she types",
                     "短く切れて少し尖っているが、本当は彼に向いてはいない。別の誰かがしたことをまだ噛んでいて、"
                     "それが打ち方に出ている")
        if g.get("guilt", 0) >= 55:
            return t("softer than usual, a little apologetic; she knows she was off with him",
                     "いつもより柔らかく、少し謝るような調子。彼にそっけなくしたのが自分で分かっている")
        # where she thinks she stands with him (`standing`, derived from the
        # record: who waits for whom, who opens the day). Low: she is not
        # sure of her place and it shows as care. High and untroubled: she is
        # sure of it and can afford to be easy with him. Until 2026-08-26 this
        # meter had no reader at all (/sweep called it DEAD).
        standing = float(him.get("standing", 50) or 50)
        if standing <= m.standing_low:
            return t("careful, a little deferential: answers properly, explains herself more than she needs to, "
                     "does not ask for anything, checks how it landed; she is not sure where she stands with him",
                     "慎重で、少し下手に出ている。きちんと答え、必要以上に自分の説明をし、何も要求せず、"
                     "どう受け取られたかを確かめる。彼との間で自分がどこにいるのか分かっていない")
        if tension >= m.cool_tension or g["mood"] < 30:
            return t("short and cool; she is not in the mood to give much",
                     "短くて冷めている。あまり差し出す気分ではない")
        if standing >= m.standing_high and tension < m.cool_tension:
            return t("easy, sure of her place: teases him, asks for things outright, does not over-explain, "
                     "leaves a message half-answered if she feels like it",
                     "気安く、自分の位置に自信がある。からかい、欲しいものは直接言い、説明しすぎず、"
                     "気が向けば半分だけ返して放っておく")
        if g.get("sadness", 0) >= m.sad_register:
            return t("quieter than usual and answering rather than starting anything; not cold with him, "
                     "just flat, and she would rather he kept talking than have to carry it",
                     "いつもより静かで、自分から始めるより返すほうになっている。彼に冷たいのではなく、"
                     "ただ平坦で、自分が持たされるより彼に喋っていてほしい")
        if g.get("jealousy", 0) >= 65:
            return t("a little prickly and pointed; something about who he's with is under her skin",
                     "少しつんつんして刺がある。彼が誰といるかが引っかかっている")
        # Below the nine branches it used to mask. It is a first-match chain
        # and awkwardness has sat at or above its threshold for days, warmed by
        # withholding at seven points an hour and by the ick at 0.9 a charge,
        # so surprise, shame, anger, guilt, low standing, sadness and jealousy
        # could not fire at all. What she is holding is the stance's subject
        # now; this is only how she sounds while she holds it.
        if g.get("awkwardness", 0) >= m.awkward_register:
            return t("a bit off, keeping it light on purpose and steering; you are holding something you are not going to say and do not want him to notice",
                     "少し調子が狂っていて、わざと軽くして話を逸らしている。言わないと決めているものを抱えていて、"
                     "それに気づかれたくない")
        if g.get("affection", 0) >= 70:
            return t("warm and open, leaning in; she is glad to be talking to him",
                     "あたたかく開いていて、前のめり。彼と話せているのが嬉しい")
        if g["validation_craving"] >= m.eager_craving and g["mood"] >= 50:
            return t("quick and a little eager; she wanted this",
                     "反応が早くて少し前のめり。これを待っていた")
        if "energy" in g and g["energy"] < 30:
            return t("slow and sleepy; few words", "動きが遅くて眠い。言葉数が少ない")
        return ""

    def delay_factor(self):
        """Multiplier on her read delay: slower when tense, low, tired; faster when craving."""
        m = self.config.delivery.mood_delivery
        if not m.enabled:
            return 1.0
        him = self.relationships.get("him", {})
        tension = int(him.get("tension", 10))
        g = self.gauges
        f = 1.0
        f += (tension / 100.0) * m.tension_weight
        f += ((50 - g["mood"]) / 100.0) * m.mood_weight
        f -= ((g["validation_craving"] - 50) / 100.0) * m.craving_weight
        # 50 is the neutral point of both terms, so a gauge a character does
        # not have contributes exactly zero -- which is the right answer for a
        # character with no body rather than a default standing in for one.
        f += ((50 - g.get("energy", 50)) / 100.0) * m.energy_weight
        # physically uncomfortable (cold, cramping, sweaty, hungry) slows her too
        f += ((50 - g.get("physical_comfort", 50)) / 100.0) * m.comfort_weight
        # and so does having to work out how to be normal at him first
        f += (g.get("awkwardness", 0) / 100.0) * m.awkward_weight
        # shame is the slowest thing she feels: she reads it, puts the phone
        # down, picks it up, types nothing
        f += (g.get("shame", 0) / 100.0) * m.shame_weight
        # anger is the opposite -- she answers straight back, and short
        f -= (g.get("anger", 0) / 100.0) * m.anger_weight
        # and gone off him is slow the way not caring is slow: the message
        # can wait, she is not waiting for it
        f += max(0.0, m.affection_cold_from - g.get("affection", 50)) / 100.0 * m.cold_weight
        # and something she has been carrying against him for weeks
        if self.sentiments:
            f += self.sentiments.delay_bonus()
        # and being wound up slows every part of it: reading it, working out
        # what to say, getting to the point of sending
        st = self.stress
        if st:
            f *= st.multiplier("delay")
        # protest answers fast; going cold answers when she gets round to it
        att = self.attachment
        if att:
            f *= att.delay_multiplier()
        # and where her body is: walking, a packed train, the day in her legs
        sit = self.situation
        if sit:
            try:
                f *= sit.delay_multiplier()
            except Exception:
                pass
        return max(m.min_factor, min(m.max_factor, f))

    def compose_factor(self):
        """How long it takes her to get the words out, as a multiplier.

        This is `delay_factor` moved to where it belongs. It used to scale the
        WHOLE wait and was then capped at 1.15 during a live exchange, on the
        reasoning that being tense does not make a person slower when the other
        one is right there. That is backwards. Tension and shame make you slower
        *precisely* when they are right there and watching: you see it, you start
        typing, you stop, you retype. Capping it deleted the most human thing she
        does at the exact moment he would notice it.

        So: noticing is presence (rhythm), composing is her (this), and nothing
        caps this one."""
        return self.delay_factor()

    def present_brief(self, scene):
        """The people in the scene with her, with what they are to her and
        how they move her. `with_who` was a yes/no ("alone?") at every
        reader but the spiral; the state model read the scene JSON and a
        flat list of meters and had to join them itself."""
        w = str((scene or {}).get("with_who") or (scene or {}).get("with") or "").lower()
        if not w or w == "alone":
            return ""
        out = []
        for name, r in (self.relationships or {}).items():
            n = str(r.get("name", name)).lower()
            if name == "him" or (n not in w and name.lower() not in w):
                continue
            bit = f"{name} (closeness {r.get('closeness')}, standing {r.get('standing')}, tension {r.get('tension')}"
            if r.get("influence"):
                bit += f"; how they move her: {str(r['influence'])[:140]}"
            out.append(bit + ")")
        return "; ".join(out)

    def relationships_brief(self):
        parts = []
        for name, r in self.relationships.items():
            parts.append(f"{name}: closeness {r.get('closeness')}, standing {r.get('standing')}, tension {r.get('tension')}")
        return "\n".join(parts)

    def talk_relief(self, who, rounds):
        """A conversation she took part in is company after the fact: it
        settles loneliness toward rest by how much that person is to her.
        Mechanical, so it happens whether or not the model remembers."""
        c = self.config.state.company
        if not c.enabled or not rounds:
            return
        att = None
        if self.sentiments:
            try:
                att = self.sentiments.live(who, "attachment")
            except Exception:
                att = None
        if att is None:
            # `who` arrives as the record name (古賀海斗); the meters are keyed
            # by the roster handle, and an unresolved one silently gave every
            # person the same middling 50
            from sim import roster
            att = float((self.relationships.get(roster.key_of(self.config, who)) or {}).get("closeness", 50) or 50)
        self._settle("loneliness", c.talk_relief * att / 100.0)

    def already_line(self):
        """The last few reasons lines, so the state model can see that the
        thing in front of it was already charged."""
        n = self.config.state.habituation.reasons_shown
        if n <= 0:
            return ""
        with self.store.lock:
            rows = self.store.conn.execute(
                "SELECT ts, reasons FROM state_log ORDER BY ts DESC LIMIT ?", (n,)).fetchall()
        rows = [r for r in rows if r[1]]
        if not rows:
            return ""
        return "; ".join(f"[{self.clock.hm(r[0])}] {str(r[1])[:160]}" for r in reversed(rows))

    def _talk_outcome(self, talk):
        """How the room went, under the turns of it.

        A room reached this role as its surviving turns and nothing else, so
        the two things that actually cost her were invisible: a room she never
        answered in at all, and a room the other person let drop. Both are
        already charged against her standing by code
        (`tomoe/exchange.py _reply_cost`), and the model was reading the same
        evening as "the plan is settled and warm" and answering zeros while
        nine of her feelings sat still for nine hours.

        Said as what happened, with the meters marked as already moved, so
        this is a reason to move HER and not a second charge on them."""
        turns = (talk or {}).get("turns") or []
        mine = [t for t in turns if roster.is_self(self.config, t.get("who"))]
        bits = [f"{len(mine)} message(s) of hers, {len(turns) - len(mine)} of theirs"]
        if not mine:
            bits.append("she said nothing in it at all")
        if talk.get("why"):
            bits.append(f"it ended because {talk['why']}")
        if talk.get("charged"):
            bits.append(f"code has already moved the meters for it ({talk['charged']}) -- "
                        f"do not move them again for the same thing; move what it did to HER")
        return "HOW THE ROOM WENT: " + "; ".join(bits) + ".\n"

    def _moment(self, deltas, reasons, user_msg_text, talk, scene):
        """Code decides WHEN a tick was a moment (the size of the move) and
        what it was about (his message, an exchange, the scene); the state
        model's own `reasons` line, written at the time, is WHAT."""
        sm = self.self_memory
        c = self.config.self_memory
        if not sm or not reasons or not isinstance(deltas, dict):
            return
        moves = {k: int(v) for k, v in deltas.items() if k in self.gauges and isinstance(v, (int, float)) and int(v) != 0}
        if not moves:
            return
        top = max(moves, key=lambda k: abs(moves[k]))
        total = sum(abs(v) for v in moves.values())
        if abs(moves[top]) < int(c.moment_min_delta) and total < int(c.moment_min_total):
            return
        today = self.clock.date_str()
        counts = self.store.get("moment_counts", {}) or {}
        if int(counts.get(today, 0)) >= int(c.moment_max_per_day):
            return
        spec = (self.config.state.gauges or {}).get(top, {}) or {}
        try:
            val = int(spec.get("valence", 0) or 0)
        except (TypeError, ValueError):
            val = 0
        if moves[top] < 0:
            val = -val
        source = "message" if user_msg_text else ("exchange" if talk else "scene")
        where = str((scene or {}).get("location") or "").strip()
        text = reasons.strip().rstrip(".")
        if where and source == "scene":
            text += f" ({where})"
        weight = 3 if abs(moves[top]) >= int(c.moment_min_delta) * 2 else 2
        how = sm.add(today, text[:240], weight, top, valence=val, source=source)
        if how == "new":
            self.store.bump_today("moment_counts", today)
            logger.log(f"[self] a moment kept ({source}, {top} {moves[top]:+d}): {text[:90]}")

    # ---------------- the live context: one builder, two renderings ----------------

    def appraisal_state(self, scene=None, events=None, user_msg_text="", digest_text="", his_side="", talk=None):
        """The tick's live context as typed data.

        This is the one source the `state` role's user string and the
        classifier's `state` are both rendered from, so the two cannot drift
        (design section 1.1). `render_appraisal_state` reproduces the role's
        exact bytes from this dict. A field whose section is off is absent from
        the dict, the same way its line is absent from the prompt today."""
        recent = self.store.recent_messages(4)
        chat = chattext.lines(recent, self.clock, chars=120, labels=("him", "her"), sep="; ") or "(none)"
        talk_txt = ""
        if talk:
            lines = "\n".join(f"  {t.get('who')}: {(t.get('ja') or '')[:120]} | {(t.get('text') or '')[:120]}" for t in talk.get("turns", [])[:14])
            talk_txt = (f"SHE JUST TALKED WITH {talk.get('who')} ({talk.get('kind')}, the whole exchange; this tick is about THEM, "
                        f"not him -- move what this did to her, and her meters with {talk.get('who')}):\n{lines}\n"
                        + self._talk_outcome(talk))
        note = self.store.get("body_settled_note")
        values = {
            "time": self.clock.both(),
            "gauges": {k: int(v) for k, v in self.live_gauges().items()},
            "relationships": self.relationships,
            "present": self.present_brief(scene),
            "already": self.already_line(),
            "talk": talk_txt,
            "scene": scene,
            "events": events,
            "body": self.body_noise_line(),
            # None means the note did not exist; "" means it did and rendered
            # empty, which the old inline build still prefixed with its newline
            "body_settled": self.body_settled_line() if note else None,
        }
        if _existence.has_chat(self.config):
            values["his_message"] = user_msg_text or "(none this tick)"
            values["his_side"] = his_side or "unknown"
            values["last_messages"] = chat
        if _existence.sees_him(self.config):
            values["digest"] = digest_text or ""
        return OrderedDict((name, values[name]) for name in appraisal_gauge.APPRAISAL_FIELDS
                           if name in values)

    def render_appraisal_state(self, d):
        """The role's user string, from `appraisal_state()`'s dict in the same
        order -- byte for byte what the inline build produced. Driven by
        `appraisal_gauge.APPRAISAL_FIELDS`, the one list the builder uses."""
        d = d or {}
        return "".join(self._render_appraisal_field(name, d[name])
                       for name in appraisal_gauge.APPRAISAL_FIELDS if name in d)

    def _render_appraisal_field(self, name, v):
        if name == "time":
            return "TIME: %s\n" % v
        if name == "gauges":
            return "GAUGES: %s\n" % ", ".join("%s %s" % (k, n) for k, n in (v or {}).items())
        if name == "relationships":
            return "RELATIONSHIPS:\n%s\n" % "\n".join(
                "%s: closeness %s, standing %s, tension %s"
                % (who, r.get("closeness"), r.get("standing"), r.get("tension"))
                for who, r in (v or {}).items())
        if name == "present":
            return ("WITH HER NOW (weigh what being around them does to her): %s\n" % v) if v else ""
        if name == "already":
            return ("ALREADY IN THE NUMBERS (what moved her on the last ticks; a standing thing was charged when it began and is still in the gauges above -- "
                    "charge only what is NEW since these lines; if nothing is new, zeros are the right answer): %s\n" % v) if v else ""
        if name == "talk":
            return v or ""
        if name == "scene":
            return "\nSCENE: %s\n" % json.dumps(v, ensure_ascii=False)
        if name == "events":
            return "EVENTS: %s\n" % json.dumps(v, ensure_ascii=False)
        # His three lines and what she saw of his machine are only in the dict
        # for a character who has one of those things, so this dispatch is only
        # reached for her.
        if name == "his_message":
            return "MESSAGE FROM HIM: %s\n" % (v or "(none this tick)")
        if name == "his_side":
            return "HIS SIDE (read receipts on her last message): %s\n" % (v or "unknown")
        if name == "last_messages":
            return "LAST MESSAGES BETWEEN THEM (if she answered, it is answered): %s\n" % (v or "(none)")
        if name == "digest":
            return "%s%s" % (sight.w(self.config, "state_digest_label"),
                             v or sight.w(self.config, "state_digest_none"))
        if name == "body":
            return ("\n" + v) if v else ""
        if name == "body_settled":
            return ("\n" + v) if v is not None else ""
        return ""

    def _apply_appraisal(self, got, scene, user_msg_text, talk):
        """The classifier's update.

        The same `apply`, `note_his_mood`, `catch_his_mood`, rupture check,
        moment write, `state_log` row and save the role path performs, with
        code's `deltas` and a templated `reasons` line. The role path is not
        touched, so a fallback is the current behaviour by construction."""
        deltas, his_mood, fresh, prov = got
        self.apply(deltas, None, fresh=fresh)
        self.note_his_mood(his_mood)
        self.catch_his_mood()
        if self.ruptures:
            try:
                self.ruptures.check(deltas, user_msg_text)
            except Exception as e:
                logger.log(f"[rupture] not checked: {type(e).__name__}: {e}")
        reasons = appraisal_gauge.reasons_line(prov)
        try:
            self._moment(deltas, reasons, user_msg_text, talk, scene)
        except Exception as e:
            logger.log(f"[self] moment not kept: {type(e).__name__}: {e}")
        self.store.add_state(self.clock.now_ts(), self.clock.date_str(), self.gauges, reasons)
        self.save()
        logger.log(self._appraisal_provenance_line(deltas, prov))
        logger.log(f"[state] {self.gauge_line()} | {reasons}")
        return reasons

    @staticmethod
    def _appraisal_provenance_line(deltas, prov):
        """`[state.appraisal] relief +3 (warmth_from_him 4/0.91), ...` -- the
        calibration record (design section 9.3) and what the section 5.5 test
        reads: every non-zero delta names the dimension that produced it."""
        sources = (prov or {}).get("gauges") or {}
        bits = []
        for gauge, d in (deltas or {}).items():
            src = sources.get(gauge) or []
            if src:
                dim_id, display, conf = src[0]
                bits.append(f"{gauge} {d:+d} ({dim_id} {display}/{conf:.2f})")
            else:
                bits.append(f"{gauge} {d:+d}")
        return "[state.appraisal] " + (", ".join(bits) if bits else "no gauge moved")

    def update_from_llm(self, llm, scene, events, user_msg_text, digest_text, his_side="", talk=None, fresh=None):
        if fresh is None:
            fresh = bool(user_msg_text) or bool(digest_text) or bool(talk)
        d = self.appraisal_state(scene=scene, events=events, user_msg_text=user_msg_text,
                                 digest_text=digest_text, his_side=his_side, talk=talk)
        # System One scores the tick first when the use is on; a non-None result
        # is the whole update. None -- the call failed, or cleared no dimension
        # -- falls through to the `state` role exactly as it ran before.
        if self.typesafe is not None and self.typesafe.ready("state_appraisal"):
            got = appraisal_gauge.appraise(self.typesafe, d, self.config, self.clock)
            if got is not None:
                return self._apply_appraisal(got, scene, user_msg_text, talk)
        user = self.render_appraisal_state(d)
        messages = [{"role": "system", "content": self.system_prompt()}, {"role": "user", "content": user}]
        data, raw = llm.call_json("state", messages)
        if not isinstance(data, dict):
            logger.log("[state] model output unparseable, no update")
            return "(no update)"
        self.apply(data.get("deltas"), data.get("relationships"), fresh=fresh)
        # what he sounds like, and then some of it rubbing off on her.
        # Once. This block was here twice from 2026-08-21 until 2026-08-22,
        # so every state update caught his mood twice and contagion ran at
        # double the configured strength for a day.
        self.note_his_mood(data.get("his_mood"))
        self.catch_his_mood()
        # code notices a break from the size of the move; a call names it
        if self.ruptures:
            try:
                self.ruptures.check(data.get("deltas"), user_msg_text)
            except Exception as e:
                logger.log(f"[rupture] not checked: {type(e).__name__}: {e}")
        reasons = str(data.get("reasons", ""))[:300]
        # a moment that moved her writes itself down, now, by the mechanism
        # that felt it -- with the feeling it had at the time. Every memory
        # outside promises and ruptures was authored by the nightly compile,
        # a narrator deciding what she would remember; PROVENANCE read
        # "27 in three days, all compile".
        try:
            self._moment(data.get("deltas"), reasons, user_msg_text, talk, scene)
        except Exception as e:
            logger.log(f"[self] moment not kept: {type(e).__name__}: {e}")
        self.store.add_state(self.clock.now_ts(), self.clock.date_str(), self.gauges, reasons)
        self.save()
        logger.log(f"[state] {self.gauge_line()} | {reasons}")
        return reasons
