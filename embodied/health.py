import random
from sim import wiring
import datetime
import logger
from sim import roster
from world.clock import hm_to_minutes, minutes_to_hm
from embodied.body import indoor_ambient

# Her body, beyond energy. Mechanical and seeded: a cold every so often, a
# cycle with a few rough days a month, and how well she sleeps. None of it
# asks a model; each day's state is drawn once, persisted, and pushed into the
# gauges as world terms (comfort, energy, mood), into the director's prompt
# (so scenes show tissues, cramps, yawning), into the schedule generation
# (a sick day stays home, a rough night a slow morning) and into her own mood
# tags (she knows how she feels). Whether she tells him is hers.
#
# Sleep is not a coin flip. Each night is scored 0-100 from concrete terms --
# how long she was down (bedtime plus a wound-up delay, against how much sleep
# she needs), the overnight heat, an unsettled mind, a late or missed meal,
# cramps or a cold -- and banded good / ok / poor / rough. The score decides
# how tired she wakes and, with her bedtime, when: late to bed on a hot,
# anxious night means a short rough sleep and a later, groggier morning.


class Health:
    WIRES = ('sentiments',)
    def __init__(self, config, store, clock, state=None, weather=None, calendar=None):
        self.config = config
        self.store = store
        self.clock = clock
        self.state = state
        self.weather = weather
        self.calendar = calendar
        self.sentiments = None    # set by scail, for `belonging` in _rising
        wiring.declare(self)

    def _days(self):
        return self.store.get("health_days", {})

    # A day with nothing in it, for a character who has no body to have one.
    _NO_BODY = {"cold": 0, "cycle_day": 0, "period_day": 0, "bad_sleep": False,
                "sleep": {}, "notes": []}

    def today(self, date_str=None):
        """The day's state: {cold, cycle_day, period_day, bad_sleep, sleep, notes}."""
        c = self.config.health
        # Refused here rather than at the call sites. Every caller was supposed
        # to be gated on `health.enabled` and most are, but the schedule is
        # handed this object unconditionally, and that one path was enough to
        # give a character with no body a menstrual cycle and a night's sleep
        # on her first boot. One gate inside beats N outside.
        if not c.enabled:
            return dict(self._NO_BODY)
        date_str = date_str or self.clock.date_str()
        days = self._days()
        if date_str in days and "sleep" in days[date_str]:
            return days[date_str]
        d = datetime.date.fromisoformat(date_str)
        prev = days.get((d - datetime.timedelta(days=1)).isoformat(), {})
        rng = random.Random(f"{date_str}|health|{c.seed}")
        # cold: continues if yesterday had days left; else may start
        cold = max(0, int(prev.get("cold", 0)) - 1)
        cold_started = False
        # yesterday outdoors in heat or rain raises the odds a cold starts today
        ex = (self.store.get("exposure", {}) or {}).get((d - datetime.timedelta(days=1)).isoformat(), 0)
        p_cold = c.cold_p_per_day + ex * c.exposure_cold_p_per_hour
        if cold == 0 and prev.get("cold", 0) == 0 and rng.random() < p_cold:
            cold = rng.randint(c.cold_days_min, c.cold_days_max)
            cold_started = True
        # cycle
        start = datetime.date.fromisoformat(c.cycle_start)
        cycle_day = ((d - start).days % c.cycle_days) + 1
        period_day = cycle_day if cycle_day <= c.period_days else 0
        row = {"cold": cold, "cycle_day": cycle_day, "period_day": period_day}
        # sleep, scored from concrete terms using this day's body state
        sleep = self._sleep(d, row)
        row["sleep"] = sleep
        row["bad_sleep"] = sleep["bad"]
        notes = []
        if cold:
            notes.append(("starting a cold" + (" (yesterday in the heat and rain did it)" if ex else "")) if cold_started else ("a cold, the worst of it" if cold >= 3 else "the tail of a cold"))
        if period_day:
            notes.append("first day of her period, cramps" if period_day == 1 else "period, day 2, heavy and tired" if period_day == 2 else f"period, day {period_day}")
        # sleep stays out of `notes` (its own line/brief carry it); notes is
        # cold + cycle, so brief() and sleep_brief() don't say it twice
        row["notes"] = notes
        days[date_str] = row
        keep = sorted(days.keys())[-45:]
        self.store.set("health_days", {k: days[k] for k in keep})
        if notes:
            logger.log(f"[health] {date_str}: " + ", ".join(notes))
        return row

    # ---------------- the night ----------------

    def _alarm_for(self, date_str):
        """Minutes-into-the-day she has to be up by, from the earliest promise
        that names a time on that date, or None. The lead is
        `schedule.wake.commitment_lead_minutes` -- one owner for "how long
        before a thing she has to be awake", read from here so the night and
        the schedule cannot disagree about it."""
        try:
            lead = int(self.config.schedule.wake.commitment_lead_minutes or 0)
        except Exception:
            return None
        if not lead:
            return None
        due = [hm_to_minutes(r["from_hm"]) for r in (self.store.get("commitments", []) or [])
               if r.get("status") == "open" and r.get("date") == date_str and r.get("from_hm")]
        return (min(due) - lead) if due else None

    def _about(self, text, words, name=""):
        """Is this line about that morning? The counterparty's name is the
        strongest signal and often the only shared word -- "get the English
        page done with Aya tomorrow" and "do homework together at the library
        at 9" are the same morning and overlap on nothing else. Her goals are
        written in Japanese and the promise is the machine's record in
        English, so the name has to be matched in both scripts: Aya is あや
        over there."""
        t = (text or "").lower()
        if name:
            forms = {name}
            for f in forms:
                if len(f) >= 2 and f.lower() in t:
                    return True
        hits = sum(1 for w in words if len(w) > 3 and w in t)
        return hits >= 2 or any(len(w) > 6 and w in t for w in words)

    def _pull_for(self, date_str):
        """How much that morning is worth to her, before any body term:
        (pull, why), or (None, []) when nothing that day names an hour.

        Duty is not the term. What moves her is wanting the morning, or being
        afraid of not being there. All of it is already on the record -- an
        open `want` goal against an `avoid` one, the event stance and WHO
        decided it, and how thin her place in the circle is. The same figure
        answers two questions a night apart: does she turn in early for it,
        and does she get up when it goes off."""
        try:
            rc = self.config.schedule.wake.rising
        except Exception:
            return None, []
        rows = [r for r in (self.store.get("commitments", []) or [])
                if r.get("status") == "open" and r.get("date") == date_str and r.get("from_hm")]
        if not rows:
            return None, []
        r = min(rows, key=lambda x: hm_to_minutes(x["from_hm"]))
        words = [w.strip(",.'\"") for w in
                 f"{r.get('what', '')} {r.get('to_name', '')}".lower().split() if w.strip(",.'\"")]
        pull, why = 0.0, []
        for gl in (self.store.get("goals", []) or []):
            if gl.get("state") != "wanting" or not self._about(gl.get("text"), words, r.get("to_name", "")):
                continue
            if gl.get("kind") == "want":
                pull += rc.want_pull
                why.append("she wants this one")
            elif gl.get("kind") == "avoid":
                pull -= rc.avoid_push
                why.append("she is dreading it")
        st = self.store.get("event_stances", {}) or {}
        for e in (st.get("events", []) or []):
            if not self._about(e.get("name"), words, r.get("to_name", "")):
                continue
            if e.get("stance") == "going":
                pull += rc.stance_going_pull
            elif e.get("stance") == "not hers":
                pull -= rc.stance_not_hers_push
            if e.get("pusher") and str(e["pusher"]).lower() not in ("", "none"):
                pull -= rc.pusher_push
                why.append(f"{e['pusher']} decided it")
        if r.get("source", "").startswith("exchange") and any(
                str(e.get("pusher", "")).lower() == str(r.get("to_name", "")).lower()
                for e in (st.get("events", []) or [])):
            pull -= rc.pusher_push
        # the engine: when her place is thin, not being there is the danger,
        # and it pulls her out of bed even for a morning she is dreading
        if self.sentiments:
            try:
                bel = float(self.sentiments.belonging())
                if bel < rc.belonging_ref:
                    pull += (rc.belonging_ref - bel) / 100.0 * rc.belonging_pull
                    why.append("she cannot be the one who was not there")
            except Exception:
                pass
        return pull, why

    def _rising(self, date_str, is_school, hours, need_h):
        """Does she actually get up when it goes off? Signed, in minutes:
        negative is up before the alarm, positive is snoozing past it.

        Duty is not the term. School is compliance and has its own branch (up
        at the last minute, never earlier); what moves her out of bed is
        wanting the morning, or being afraid of not being there. All of it is
        already on the record -- an open `want` goal against an `avoid` one,
        the event stance and WHO decided it, and how thin her place in the
        circle is -- so this is arithmetic, not a call."""
        try:
            rc = self.config.schedule.wake.rising
        except Exception:
            return 0.0, []
        pull, why = self._pull_for(date_str)
        if pull is None:
            return 0.0, []

        short = max(0.0, (need_h or 0) - (hours or 0))
        pull -= short * rc.short_sleep_push
        g = (self.state.gauges if self.state else {}) or {}
        pull -= float(g.get("unwell", 0)) * rc.unwell_push

        pull = max(-1.0, min(1.0, pull))
        # Beating the alarm is something a rested body does. Wanting the
        # morning cannot buy sleep back: on 5.8 hours of a needed 8.6 she was
        # getting up 25 minutes EARLY because she was keen, which is not what
        # a fifteen-year-old does. The most that wanting it buys on a short
        # night is being up when it goes off instead of lying there. The
        # snooze side is deliberately not gated -- being short of sleep is
        # exactly the reason people snooze.
        rest = float(getattr(rc, "early_needs_rest_hours", 1.5) or 1.5)
        rested = 1.0 if short <= 0 else max(0.0, 1.0 - short / rest) if rest > 0 else 0.0
        if pull > 0:
            mins = -pull * rc.early_max_min * rested
            if mins > -1 and why:
                why.append("but she is too short of sleep to be up before it")
        else:
            mins = -pull * rc.snooze_max_min
        return mins, why

    def _chat_alive(self, date_str):
        """How much of the group chat was still going in the small hours
        before `date_str`, in turns, and who was still up.

        Her own words are the whole of the mechanism: 「みんな起きてるのに私だけ
        寝るなんて無理!」 -- she is not kept up by "her phone", she is kept up by
        the chat still being ALIVE, because being the one who drops out first
        is unthinkable to her. So the term counts other people's turns, not
        hers: what holds her there is that they are still talking."""
        s = self.config.health.sleep
        after = hm_to_minutes(getattr(s, "chat_alive_after_hm", "23:00"))
        prev = (datetime.date.fromisoformat(date_str) - datetime.timedelta(days=1)).isoformat()
        n, who = 0, set()
        for x in self.store.get("cast_chat", []) or []:
            if x.get("kind") != "group" or x.get("date") not in (prev, date_str):
                continue
            for t in x.get("turns", []):
                hm = str(t.get("hm") or "")
                if len(hm) != 5:
                    continue
                m = hm_to_minutes(hm)
                # An exchange keeps the date it STARTED on, so one that opens
                # at 23:20 and runs to 00:40 carries 00:40 under yesterday's
                # date. Both sides of midnight count, from either date, or the
                # small hours -- the part of the night that actually keeps her
                # up -- are the part that gets missed.
                until = getattr(s, "chat_alive_until_min", 300)
                if x.get("date") == prev:
                    # last evening, or an exchange of last evening's that ran
                    # past midnight and kept yesterday's date on its later turns
                    ok = m >= after or m <= until
                else:
                    # dated today: only the small hours count. A 23:30 exchange
                    # dated today belongs to the NEXT night, and would be
                    # counted against this morning on any recompute.
                    ok = m <= until
                if not ok:
                    continue
                if roster.is_self(self.config, t.get("who")):
                    continue
                n += 1
                who.add(roster.record_name(self.config, t.get("who")))
        return n, who

    def _sleep(self, d, row):
        """Score the night that produces d's morning, 0-100, from concrete terms.
        Returns {score, quality, bad, bedtime, wake, hours, need_hours, factors,
        short_note, energy_target}."""
        s = self.config.health.sleep
        date_str = d.isoformat()
        is_school = bool(self.calendar.is_school_day(d)) if self.calendar else False
        g = (self.state.gauges if self.state else {}) or {}
        rng = random.Random(f"{date_str}|sleep|{self.config.health.seed}")
        if not s.enabled:
            wake = s.school_alarm if is_school else "09:30"
            return {"score": 70, "quality": "ok", "bad": False, "bedtime": s.planned_bed_school if is_school else s.planned_bed_free,
                    "wake": wake, "hours": None, "need_hours": None, "factors": [], "short_note": "slept badly",
                    "energy_target": s.energy_target_ok}

        factors = []
        anx = float(g.get("anxiety", 30))
        uns = float(g.get("unsaid", 20))
        screen = max(float(g.get("curiosity", 0)), float(g.get("boredom", 0)))

        # --- bedtime: lights-out plus how long she lies there wound up / scrolling
        planned = hm_to_minutes(s.planned_bed_school if is_school else s.planned_bed_free)
        delay = s.delay_base_min + rng.gauss(0, s.delay_jitter_min)
        delay += max(0.0, anx - s.delay_ref) * s.delay_per_anxiety
        delay += max(0.0, uns - s.delay_ref) * s.delay_per_unsaid
        if screen >= s.screen_ref:
            delay += s.delay_screen_min
        # the chat being alive is its own reason, and a stronger one than the
        # phone in the abstract: she cannot be the one who drops out.
        chat_n, chat_who = self._chat_alive(date_str)
        if chat_n:
            add = min(float(s.chat_alive_max_min), chat_n * float(s.chat_alive_per_turn_min))
            if add >= 1:
                delay += add
                names = "、".join(sorted(chat_who)[:2]) or "the others"
                factors.append(f"the group chat was still going ({names}, {chat_n} messages) and she stayed in it")
        delay = max(0.0, min(s.delay_max_min, delay))
        bedtime_m = planned + delay
        need_h = (s.need_hours_school if is_school else s.need_hours_free) + rng.gauss(0, s.need_jitter_hours)

        # She has to be up at a quarter to eight, and until now the night
        # before knew nothing about it: `planned_bed_free` is the same hour
        # whatever tomorrow holds, and the delay only ever pushes it later.
        # So the system took her sleep and then charged her for being late
        # with it -- she was never given the evening to decide about. Now the
        # alarm reaches backwards. Whether she acts on it is the same figure
        # that decides whether she gets up for it, against the same phone and
        # the same wound-up head that make her late to bed on any other night.
        # Either way the record says she knew.
        alarm = self._alarm_for(date_str)
        if alarm is not None:
            pull, _pw = self._pull_for(date_str)
            pull = max(0.0, min(1.0, pull if pull is not None else 0.0))
            full_bed = alarm - need_h * 60.0          # down by here for a whole night
            gap = bedtime_m - full_bed
            if gap > 0:
                # what keeps her up on any other night keeps her up on this
                # one, and it has to be able to win: the shortfall before a
                # nine o'clock is two hours, so without scaling the ceiling
                # too she brought it forward the full hour however wound up
                # and however deep in her phone she was.
                resist = min(1.0, delay / max(1.0, float(s.delay_max_min)))
                shift = min(float(s.early_bed_max_min) * (1.0 - resist),
                            gap * float(s.early_bed_pull) * pull * (1.0 - resist))
                if shift >= s.early_bed_note_min:
                    bedtime_m -= shift
                    factors.append(f"turned in {shift:.0f} min early for the morning")
                elif pull >= s.early_bed_knew_pull:
                    factors.append("she knew she had to be up and stayed on her phone anyway")
                else:
                    # she knew either way. Not going to bed for a morning she
                    # does not want is the most deliberate version of this.
                    factors.append("she had to be up and did not go to bed for it")

        # --- environmental penalties (independent of duration)
        pen = 0.0
        try:
            dt = datetime.datetime.combine(d, datetime.time(3, 0), tzinfo=self.clock.char_tz)
            w = self.weather.current(dt) if self.weather else None
        except Exception:
            w = None
        if w:
            env = self.config.environment
            out_feels = w.get("feels", w.get("temp"))
            hum = w.get("humidity", 60) or 60
            # the BEDROOM overnight, not the street: the same room model body.py
            # uses, with the AC on (she sleeps with it). Only a heatwave the AC
            # can't fully beat leaks in.
            room = indoor_ambient(env, out_feels)
            ac_on = out_feels is not None and out_feels >= env.ac_from_feels
            if room is not None:
                if ac_on and out_feels > s.ac_struggle_from:
                    room += (out_feels - s.ac_struggle_from) * s.ac_struggle_leak
                if room > s.heat_feels_ok:
                    hp = min(s.heat_pen_max, (room - s.heat_feels_ok) * s.heat_pen_per_deg)
                    if hp >= 3:
                        pen += hp
                        factors.append("a hot night" if room >= 30 else "a warm room")
                    if not ac_on and hum > s.humid_ref:
                        pen += min(s.humid_pen_max, (hum - s.humid_ref) * s.humid_pen_per_pct)
        mind = min(s.mind_pen_max, max(0.0, anx - s.mind_ref) * s.anxiety_pen_per_pt + max(0.0, uns - s.mind_ref) * s.unsaid_pen_per_pt)
        # What she is carrying does not switch off at bedtime. This is the loop
        # the recovery term exists to govern: stress costs her the night, a bad
        # night is a load term, and the load is what stress integrates.
        #
        # After the cap and not before it, which is the whole of whether this
        # reader does anything. anxiety and unsaid are load terms themselves, so
        # any night stressful enough to matter has both of them over mind_ref
        # and the raw figure already past mind_pen_max -- scaling underneath the
        # cap fired only on the nights where it could not change the score. The
        # ceiling is what a busy head costs her in an ordinary week; stress is
        # what raises the ceiling.
        _st = getattr(self.state, "stress", None) if self.state else None
        if _st:
            mind *= _st.multiplier("sleep_cost")
        if mind >= 4:
            pen += mind
            factors.append("couldn't switch her head off")
        last_meal = self.store.get("last_meal_ts")
        if last_meal:
            try:
                bed_ts = datetime.datetime.combine(d, datetime.time(0, 0), tzinfo=self.clock.char_tz).timestamp() + bedtime_m * 60
                hrs_since = (bed_ts - last_meal) / 3600.0
                if 0 <= hrs_since < s.late_meal_hours:
                    pen += s.late_meal_pen
                    factors.append("ate too late")
            except Exception:
                pass
        hunger = float(g.get("hunger", 0))
        if hunger > s.hungry_to_bed_ref:
            pen += min(s.hungry_pen_max, (hunger - s.hungry_to_bed_ref) * s.hungry_pen_per_pt)
            factors.append("went to bed hungry")
        if row.get("period_day") in (1, 2):
            pen += s.cramp_pen
            factors.append("cramps")
        if int(row.get("cold", 0)) >= 2:
            pen += s.cold_pen
            factors.append("stuffed up with a cold")

        # --- wake: a worse night (more env penalty) pushes it later
        env_score = max(0.0, 100.0 - pen)
        deficit10 = max(0.0, s.ok_from - env_score) / 10.0
        jit = rng.gauss(0, s.wake_jitter_min)
        if is_school:
            wake_m = hm_to_minutes(s.school_alarm) + min(s.oversleep_max_min, deficit10 * s.school_snooze_per_10) + jit
            wake_m = max(hm_to_minutes(s.school_alarm) - 5, min(hm_to_minutes(s.school_wake_ceil), wake_m))
        else:
            wake_m = bedtime_m + need_h * 60 + min(s.oversleep_max_min, deficit10 * s.free_oversleep_per_10) + jit
            wake_m = max(hm_to_minutes(s.free_wake_floor), min(hm_to_minutes(s.free_wake_ceil), wake_m))

        # An alarm. A school morning already has one (school_alarm); a promise
        # with a time on it is the other reason she sets one, and it belongs
        # HERE rather than on top of the drawn wake, because the night has to
        # be planned around it: `hours` is measured after this, so the short
        # night, the penalty, the factors and the energy target all follow from
        # having to be up. Otherwise she would be woken early for free by a
        # clamp somewhere later and the morning would cost her nothing.
        if alarm is not None and alarm < wake_m:
            # the alarm is the earliest she COULD be up; whether she does is
            # what the morning is worth to her against the night she had
            rise, why_rise = self._rising(date_str, is_school,
                                          (alarm - bedtime_m) / 60.0, need_h)
            # `free_wake_floor` is the floor on a DRAWN wake -- "she does not
            # get up before 8 for nothing". This is not nothing, and `rise` is
            # already bounded either side, so the alarm is its own floor.
            wake_m = alarm + rise
            if rise <= -1:
                factors.append(f"up {abs(rise):.0f} min before the alarm" + (f": {why_rise[0]}" if why_rise else ""))
            elif rise >= 1:
                factors.append(f"snoozed {rise:.0f} min past the alarm" + (f": {why_rise[0]}" if why_rise else ""))
            else:
                factors.append("alarm set, she has to be somewhere"
                               + (f": {why_rise[0]}" if why_rise else ""))

        # --- duration and its penalty; total score
        hours = max(0.0, (wake_m - bedtime_m) / 60.0)
        short = max(0.0, need_h - hours)
        if short > 0.25:
            pen += min(s.short_pen_max, short * s.short_pen_per_hour)
            factors.append(f"only about {hours:.0f} hours")
        elif hours >= s.long_grog_from_hours:
            pen += s.long_grog_pen
            factors.append("slept too long, groggy")
        score = int(max(0, min(100, round(100 - pen))))
        if score >= s.good_from:
            quality = "good"
        elif score >= s.ok_from:
            quality = "ok"
        elif score >= s.poor_from:
            quality = "poor"
        else:
            quality = "rough"
        bad = quality in ("poor", "rough")
        energy_target = {"good": s.energy_target_good, "ok": s.energy_target_ok,
                         "poor": s.energy_target_poor, "rough": s.energy_target_rough}[quality]
        short_note = {"good": "slept well", "ok": "slept ok", "poor": "slept badly", "rough": "barely slept"}[quality]
        out = {"score": score, "quality": quality, "bad": bad, "bedtime": minutes_to_hm(int(round(bedtime_m)), wrap=True),
               "wake": minutes_to_hm(int(round(wake_m)), wrap=True), "hours": round(hours, 1), "need_hours": round(need_h, 1),
               "factors": factors, "short_note": short_note, "energy_target": energy_target}
        if bad or quality == "good":
            logger.log(f"[sleep] {date_str}: {quality} (score {score}) — {hours:.1f}h, bed {out['bedtime']} up {out['wake']}"
                       + (f"; {', '.join(factors)}" if factors else ""))
        return out

    def night(self, date_str=None):
        """The sleep dict for a date (draws the day if needed)."""
        return self.today(date_str).get("sleep", {})

    def brief(self, date_str=None):
        t = self.today(date_str)
        return ", ".join(t["notes"]) if t["notes"] else ""

    def sleep_brief(self, date_str=None):
        """One line for the director / her situation: how she slept."""
        n = self.night(date_str)
        if not n or n.get("hours") is None:
            return ""
        q = n["quality"]
        base = {"good": "slept well", "ok": "slept ok", "poor": "slept badly", "rough": "barely slept"}[q]
        line = f"{base}, about {n['hours']:.0f}h (up {n['wake']})"
        if q in ("poor", "rough") and n.get("factors"):
            line += f": {', '.join(n['factors'][:3])}"
        return line

    def tags(self):
        """What she feels in her body, for her mood tags."""
        t = self.today()
        out = []
        if t["cold"]:
            out.append("has a cold" if t["cold"] >= 2 else "getting over a cold")
        if t["period_day"] in (1, 2):
            out.append("cramps")
        elif t["period_day"]:
            out.append("on her period")
        n = t.get("sleep", {})
        q = n.get("quality")
        if q == "rough":
            out.append(f"running on ~{n['hours']:.0f}h, wrecked" if n.get("hours") is not None else "barely slept, wrecked")
        elif q == "poor":
            out.append(f"tired, slept badly (~{n['hours']:.0f}h)" if n.get("hours") is not None else "slept badly")
        elif q == "good" and n.get("hours") is not None:
            out.append("well-rested")
        return out

    def effects(self):
        """Targets the world terms pull toward, per hour: {gauge: (target, pull)}.

        This method owns composition -- where two conditions want the same
        gauge it takes the worse of the two -- and the state loop moves toward
        whatever comes back, in either direction. The loop used to move down
        only, which made `period_anxiety_floor` a floor that could only lower
        her anxiety: being on her period had never once raised it."""
        c = self.config.health
        t = self.today()
        eff = {}
        if t["cold"]:
            sev = 1.0 if t["cold"] >= 3 else 0.6
            eff["energy"] = (c.cold_energy_target, c.pull_per_hour * sev)
            eff["physical_comfort"] = (c.cold_comfort_target, c.pull_per_hour * sev)
            # not mood: mood is computed from its causes now, and a cold is a
            # cause. Being ill is felt as flatness, and the flatness is what
            # puts the mood down.
            eff["unwell"] = (c.cold_unwell_target, c.pull_per_hour * sev)
        if t["period_day"] in (1, 2):
            eff["physical_comfort"] = (min(eff.get("physical_comfort", (100, 0))[0], c.period_comfort_target), c.pull_per_hour)
            eff["unwell"] = (max(eff.get("unwell", (0, 0))[0], c.period_unwell_target), c.pull_per_hour)
            eff["anxiety"] = (c.period_anxiety_target, c.pull_per_hour * 0.4)
        elif t["period_day"]:
            eff["physical_comfort"] = (min(eff.get("physical_comfort", (100, 0))[0], c.period_comfort_target + 10), c.pull_per_hour * 0.5)
        n = t.get("sleep", {})
        if n.get("bad"):
            target = n.get("energy_target", 40)
            eff["energy"] = (min(eff.get("energy", (100, 0))[0], target), c.pull_per_hour)
            if n.get("quality") == "rough":
                eff["unwell"] = (max(eff.get("unwell", (0, 0))[0], c.rough_night_unwell_target), c.pull_per_hour * 0.5)
        return eff

    def schedule_note(self, date_str):
        """For the schedule model at 05:00: a sick day or a rough night changes the plan."""
        t = self.today(date_str)
        parts = []
        if t["cold"] >= 3:
            return "She has a cold, the bad days of it: she stays home or goes and regrets it; mom notices; tissues, a mask, early bed."
        if t["cold"]:
            parts.append("She is at the tail of a cold: sniffly, a little slower.")
        if t["period_day"] in (1, 2):
            parts.append("First days of her period: cramps, tired, a heat pad, less patience for the group, still goes where she must.")
        n = t.get("sleep", {})
        if n.get("quality") == "rough":
            parts.append(f"She barely slept ({n['hours']:.0f}h" + (f", {n['factors'][0]}" if n.get("factors") else "") + "): a slow, short-fused morning, a nap likely in the afternoon.")
        elif n.get("quality") == "poor":
            parts.append(f"She slept badly ({n['hours']:.0f}h): slower morning, flagging by afternoon.")
        return " ".join(parts)
