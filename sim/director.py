import json
import re
from sim import chattext
from sim import lang
from sim import wiring
import logger
from sim import sight
from sim import schedule as sched
from sim import reconcile
from sim import roster
from world.clock import hm_to_minutes


class Director:
    WIRES = ('attachment', 'briefs', 'cast', 'commitments', 'diet', 'events', 'exchange', 'family', 'goals', 'household', 'ledger', 'outlook', 'people', 'reflection', 'situation', 'sleep_source', 'spirals', 'zeitgeist',)
    def _family_txt(self, now):
        """Never lets the tick down: a fault here is a missing line, not a
        missing scene (it took the director out for three runs on 08-26)."""
        try:
            f = self.family
            return f"THE FAMILY RIGHT NOW: {f.now_line()}\n{f.brief(now.date())}\n" if f else ""
        except Exception as e:
            logger.log(f"[director] family line failed: {type(e).__name__}: {e}")
            return ""

    def _friends_line(self):
        try:
            c = self.cast
            return c.plans_brief(self.clock.date_str()) if c else ""
        except Exception:
            return ""

    def _japan_line(self):
        try:
            z = self.zeitgeist
            return z.short(limit=5) if z else ""
        except Exception:
            return ""

    def __init__(self, config, llm, store, clock, weather, calendar, state, records=None, phone=None, health=None, body=None, diet=None, money=None):
        self.config = config
        self.llm = llm
        self.store = store
        self.clock = clock
        self.weather = weather
        self.calendar = calendar
        self.state = state
        self.records = records
        self.phone = phone
        self.health = health
        self.body = body
        self.diet = diet
        self.money = money
        self.last_tick_ts = store.get("director_last_tick_ts", 0)
        self.next_tick_minutes = store.get("director_next_tick_minutes", config.director.tick_minutes)
        self.current = self._resume_scene()
        # the last scene the MODEL wrote, as opposed to a placeholder cut from
        # the schedule block when it did not answer. When these drift apart
        # the record has a hole, and the next real scene covers the whole of
        # it (catch_up), the way the night scene covers the night.
        self.last_model_ts = store.get("director_last_model_ts", 0)
        self.hole_written = False      # one-shot: the scene just returned covers a hole
        # A scene the console started (`docs/2026-09-17_vn_stage_manager_scope.md`)
        # holds until he clears it: the plan tick does not reclaim it, or the
        # directed scene would be overwritten within twenty minutes. Kept in kv
        # so a restart resumes the directed scene.
        self.directive = store.get("director_directive", None)
        wiring.declare(self)

    # The standing request to cover a hole in one scene. `App.catch_up` sets it
    # and then stamps the missed calls done and empties them in the same
    # breath, so the flag is the only thing left that knows the hole is owed --
    # and a restart between the request and the next tick used to drop it, with
    # nothing anywhere afterwards to say a stretch of her day was never written.
    @property
    def catch_up(self):
        return bool(self.store.get("director_catch_up", False))

    @catch_up.setter
    def catch_up(self, v):
        if bool(v) != bool(self.store.get("director_catch_up", False)):
            self.store.set("director_catch_up", bool(v))

    def _resume_scene(self):
        """The scene she is in, as the code left it.

        The `scenes` table has a fixed column list, so a scene rebuilt from it
        loses every key the code attached after the model answered -- what she
        ate, what she spent, the note she has open, who is about, how long this
        scene lasts -- and hands `events` back as a JSON string rather than the
        list its readers index. The whole dict goes to kv as well, and this
        prefers it whenever it is the same scene as the newest row."""
        row = self.store.last_scene()
        kept = self.store.get("director_current", None)
        if isinstance(kept, dict) and row and kept.get("ts") == row.get("ts"):
            return kept
        return row

    def _keep_scene(self, data):
        """The current scene, whole, for the next process to pick up."""
        try:
            self.store.set("director_current", data)
        except Exception as e:
            logger.log(f"[director] the scene was not kept whole: {type(e).__name__}: {e}")

    def _brief(self, name, *a):
        """Her household, her map: the program's text, if she has a world.
        `briefs` is a module the program wires (tomoe/briefs.py); a
        character with no world has none and gets nothing."""
        mod = self.briefs
        fn = getattr(mod, name, None) if mod else None
        if fn is None:
            return ""
        try:
            return fn(self.config, *a) or ""
        except Exception as e:
            logger.log(f"[director] {name} not read: {type(e).__name__}: {e}")
            return ""

    def from_plan(self):
        """Is this character's scene cut from her plan in code, with no model
        call? `director.scene_source` decides: "model" (the default, and the
        first character's) asks the director role every tick; "plan" reads the
        schedule block and nothing else.

        A second writer over the plan is what a character with a world round
        her needs -- her day is full of people, places and weather the plan
        cannot know the state of. A character whose whole day is written once
        from her own home file has none of that, and the tick was buying a
        paraphrase of the block she is already in."""
        return str(getattr(self.config.director, "scene_source", "model")).lower() == "plan"

    def _until_block_end(self, blk):
        """How long a scene cut from the plan holds: to the end of the block,
        and never longer than the ordinary beat.

        The boundary is the only moment a planned day changes, so a scene must
        never outlast it. The beat is the cap because everything that reads a
        scene runs on the same tick -- whether she writes first, her diary, a
        spiral, what she is looking forward to -- and letting a two-hour block
        set the timestep would slow all of that with it."""
        c = self.config.director
        now = self.clock.now()
        left = hm_to_minutes(str(blk.get("end") or "24:00")) - (now.hour * 60 + now.minute)
        if left <= 0:
            left = c.tick_minutes
        return max(1, min(int(left), int(c.tick_minutes)))

    def _plan_scene(self, blk, extra_events=None):
        """The scene as the plan already holds it: no call, nothing invented.

        Every field a reader of a scene asks for is answered from the block or
        from the machine's own record. `sensory` and `inner` are empty because
        the block's own wording is the description (it is written once a day
        from her home file and is specific: "in the bath with salts, the
        changing space cold outside"), and because a second sentence about
        what is on his screen is the third copy of it in her prompt. What the
        model used to add here and nothing replaces -- a household move, a
        thread opening or closing, a note of his she decides to open, the pull
        to say something -- is listed in docs/yukarin.md."""
        text = f"{blk.get('location', '')} {blk.get('activity', '')}".lower()
        bath = tuple(getattr(self.config.environment, "bath_keywords", None) or ())
        return {
            "location": blk.get("location", ""),
            "activity": blk.get("activity", ""),
            "with": blk.get("with", "alone"),
            "phone_access": blk.get("phone_access", "free"),
            "setting": "bath" if any(k in text for k in bath) else "indoors",
            "sensory": "",
            # she has no wallet and nothing tracks what she eats; the block
            # says she is eating and the ledger's own line says what
            "ate": "", "spent": None,
            # what really happened since the last scene, as the machine wrote
            # it down. The model path was handed these to reflect; here they
            # are the events, and nothing else can be one.
            "events": [dict(e) for e in (extra_events or []) if isinstance(e, dict) and e.get("text")],
            # a pull to speak is decided by the impulse gate and by what her
            # sight puts in front of her, never by a paraphrase of the block
            "share_worthy": False, "share_hint": "",
            # `open_threads` is deliberately absent rather than empty: the
            # settler leaves the threads alone unless it is handed a list, and
            # an empty list would close every one of them.
            "resolved_threads": [],
            "schedule_change": None, "open_note": "",
            "next_tick_minutes": self._until_block_end(blk),
        }

    # The director sets its own timestep (next_tick_minutes in the scene):
    # twenty minutes alone with her phone, an hour in class or on a train
    # where nothing changes. A schedule block boundary always interrupts.
    def due(self, schedule=None):
        now_ts = self.clock.now_ts()
        if now_ts - self.last_tick_ts >= self.next_tick_minutes * 60:
            return True
        if schedule and self.last_tick_ts:
            then = self.clock.to_char(self.last_tick_ts)
            if sched.block_at(schedule["blocks"], then) is not sched.block_at(schedule["blocks"], self.clock.now()):
                return True
        return False

    def _hole(self, schedule):
        """The stretch since the model last wrote a scene, when placeholders
        stand in for it: the schedule blocks that passed, as one block of
        text for the prompt. Empty when the record is whole."""
        if not self.last_model_ts:
            return ""
        now_ts = self.clock.now_ts()
        mins = (now_ts - self.last_model_ts) / 60
        if mins < self.next_tick_minutes * 1.5:
            self.catch_up = False        # the record is whole; nothing to cover
            return ""
        if not self.catch_up and mins < self.next_tick_minutes * 2.5:
            return ""
        then = self.clock.to_char(self.last_model_ts)
        now = self.clock.now()
        blocks = []
        if schedule:
            t0 = hm_to_minutes(then.strftime("%H:%M")) if then.date() == now.date() else 0
            t1 = hm_to_minutes(now.strftime("%H:%M"))
            for b in schedule.get("blocks", []):
                s, e = hm_to_minutes(b["start"]), hm_to_minutes(b["end"])
                if e > t0 and s < t1:
                    blocks.append(f"{b['start']}-{b['end']} {b['activity']} @ {b['location']} with {b.get('with', '?')}")
        return (f"THE RECORD HAS A HOLE: from {then.strftime('%H:%M')} to {now.strftime('%H:%M')} nobody wrote her "
                f"({mins:.0f} minutes; the scenes on record for that stretch are placeholders cut from the schedule). "
                f"The schedule says she went through: {'; '.join(blocks) or '(no blocks on the schedule)'}. "
                f"Write THIS scene as the whole stretch: what happened through those blocks, in order, as `events` "
                f"(each starting with its time), ending where she is now. Nothing in it can contradict the ledger or "
                f"the messages above.\n")

    def sleeping(self):
        """True when the current scene is the one written for tonight. The
        flag cannot live in the scene dict: it is rebuilt from the scenes
        table's columns on boot and anything the code added is lost."""
        return bool(self.current) and self.current.get("ts") == self.store.get("sleep_scene_ts")

    def scene_fresh(self):
        return bool(self.current) and (self.clock.now_ts() - self.current["ts"]) < self.next_tick_minutes * 60 * 1.5

    def phone_access(self, schedule):
        # A fresh scene is the authority (the director may have put her in
        # the bath or let her skip a class); once it goes stale the schedule
        # block takes over until the next tick.
        blk = sched.block_at(schedule["blocks"], self.clock.now())
        access = blk.get("phone_access", "glance")
        if self.scene_fresh():
            cur = self.current.get("phone_access")
            if cur in ("free", "glance", "none"):
                access = cur
        return access

    def asleep_block(self, schedule):
        """True when the schedule has her asleep now (phone none + a sleep word).
        A resident's sleep is not in her plan: `sleep_source` (resident/sight.py)
        reads it off his machine and is asked first."""
        src = self.sleep_source
        if src is not None:
            return src.asleep_block()
        blk = sched.block_at(schedule["blocks"], self.clock.now())
        return blk if sched.is_sleep_block(blk, self.config.director.sleep_keywords) else None

    def sleep_scene(self, schedule, block, reason=""):
        """One scene for the whole night, written when she goes under.

        The director does not tick while she sleeps, so whatever the last
        waking scene said stayed on the record until morning: "eyes closed but
        not asleep", true at 01:53, was still the current scene at 04:56. The
        night is a real part of her day and it should be described as one.
        Costs one call per night -- none at all where the scene is cut from
        the plan, which then supplies the night the same way it supplies every
        other block: the words the sleep block itself was planned with."""
        now = self.clock.now()
        if self.from_plan():
            data, raw = {"location": block.get("location") or "her room",
                         "activity": block.get("activity") or "asleep",
                         "sensory": ""}, ""
            return self._settle_sleep(data, raw, block, now)
        night = self.health.night() if self.health else {}
        last = self.current or {}
        msgs = self.store.recent_messages(4)
        msgs_txt = chattext.lines(msgs, self.clock, chars=200) or "(nothing recent)"
        gap = ""
        if msgs:
            mins = (self.clock.now_ts() - msgs[-1]["ts"]) / 60
            gap = f" The last of it was {mins:.0f} minutes ago."
        room = ""
        if self.body:
            env = self.body.setting(last, block, self.scene_fresh())
            room = env.get("line") or ""
        factors = ", ".join(night.get("factors", [])[:3])
        # What time of year it is comes from the clock, never from the prompt:
        # the prompt used to open the sensory rule with the season it was
        # written in and kept saying it into the next one. English because the
        # night prompt is the director talking to itself about her; `say`
        # follows the character if she is ever instructed in her own language.
        t = lang.say(self.config)
        season = t(self.clock.time_of_year(), self.clock.time_of_year(ja=True))
        user = (
            f"NOW: {now.strftime('%A %Y-%m-%d %H:%M')} her time; she has just stopped being awake"
            + (f" ({reason})" if reason else "") + ".\n"
            f"THE TIME OF YEAR: {season}.\n"
            f"SHE IS DUE UP AT: {night.get('wake') or block['end']} (the sleep block runs {block['start']}-{block['end']}).\n"
            f"THIS NIGHT: {self.health.sleep_brief() if self.health else '(not scored)'}"
            + (f"; what is against her: {factors}" if factors else "") + ".\n"
            f"HER BODY TODAY: {self.health.brief() if self.health else ''}\n"
            f"HER STATE AS SHE WENT UNDER: {self.state.gauge_line()}\n"
            f"WEATHER OUTSIDE TONIGHT: {self.weather.describe(now)}\n"
            f"THE ROOM: {room or 'her own room'}\n"
            f"THE LAST SCENE BEFORE THIS: {last.get('location', '')} / {last.get('activity', '')}. "
            f"{last.get('sensory', '')}\n"
            f"THE LAST THINGS SAID BETWEEN THEM:\n{msgs_txt}{gap}\n"
        )
        messages = [{"role": "system", "content": self.config.prompt_text("sleep")}, {"role": "user", "content": user}]
        data, raw = self.llm.call_json("sleep", messages)
        if not isinstance(data, dict) or not data.get("activity"):
            logger.log("[director] sleep scene unparseable, using a plain one")
            data = {"location": "her room, in bed", "activity": "asleep", "sensory": ""}
        return self._settle_sleep(data, raw, block, now)

    def _settle_sleep(self, data, raw, block, now):
        """The night written down, whoever described it: one copy, so the
        scene cut from the plan and the scene a model wrote are the same
        record with the same fields."""
        # everything else is the code's to say: she is asleep, so there is no
        # phone, nothing to share, and no events or threads come out of a night
        wake_m = hm_to_minutes(block["end"])
        now_m = now.hour * 60 + now.minute
        if wake_m <= now_m:
            wake_m += 24 * 60
        data.update({"with": "alone", "phone_access": "none", "setting": "indoors_ac" if "ac" in (data.get("sensory") or "").lower() else "indoors",
                     "ate": "", "spent": None, "events": [], "share_worthy": False, "share_hint": "",
                     "open_note": "", "schedule_change": None, "asleep": True,
                     "next_tick_minutes": max(1, wake_m - now_m)})
        ts = self.clock.now_ts()
        self.store.add_scene(ts, self.clock.date_str(), self.clock.hm(), data, raw)
        self.last_tick_ts = ts
        # this one holds until the wake, so it never reads as stale mid-night
        self.next_tick_minutes = data["next_tick_minutes"]
        self.store.set("director_last_tick_ts", ts)
        self.store.set("director_next_tick_minutes", self.next_tick_minutes)
        self.store.set("sleep_scene_ts", ts)
        data["ts"] = ts
        data["hm"] = self.clock.hm()
        self.current = data
        self._keep_scene(data)
        logger.log(f"[director] asleep: {data['location']} / {data['activity']}")
        return data

    def _waiting(self):
        """Whose message she has not answered, from `cast_chat` itself.

        The scene model was writing "Hinako's message still sits unread on her
        phone" at 11:00 having answered Hinako at 10:38 -- three lines below it
        in the same prompt -- because it was reading its own earlier event and
        repeating it. Code says who is actually waiting; the model does not
        have to infer it from a list of things it wrote."""
        try:
            from sim import roster
            today = self.clock.date_str()
            out = []
            for x in (self.store.get("cast_chat", []) or []):
                if x.get("date") != today or not x.get("turns"):
                    continue
                last = x["turns"][-1]
                if roster.is_self(self.config, last.get("who")):
                    continue
                out.append(f"{x.get('who')} ({x.get('hm')})")
            return ", ".join(out[-4:]) or "nobody: she has answered everyone who reached her today"
        except Exception:
            return "unknown"

    def _ledger_txt(self, schedule):
        led = self.ledger
        if not led:
            return ""
        try:
            return led.text(scene=self.current, schedule=schedule, for_whom="her")
        except Exception as e:
            logger.log(f"[director] ledger unavailable: {type(e).__name__}: {e}")
            return ""

    def tick(self, schedule, digest_text, unread_count, extra_events=None, his_side=""):
        now = self.clock.now()
        c = self.config.director
        blk = sched.block_at(schedule["blocks"], now)
        if self.directive:
            # A scene the console started holds until he clears it
            # (`docs/2026-09-17_vn_stage_manager_scope.md`): the plan must not
            # reclaim it, and every reader of `current` keeps seeing the scene
            # he set. Nothing is written and no call is made.
            logger.log("[director] the plan tick stands down: a directed scene is live")
            return self.current
        if self.from_plan():
            # The plan wrote this scene when it wrote the day. Nothing is
            # asked, nothing is built, and the record is whole by
            # construction, so the hole the catch-up covers cannot open.
            self.last_model_ts = self.clock.now_ts()
            self.store.set("director_last_model_ts", self.last_model_ts)
            return self._settle_scene(self._plan_scene(blk, extra_events), blk, unread_count)
        recent = self.store.recent_scenes(c.recent_scenes_in_prompt)
        # `inner` is trimmed here on purpose: the scenes are context for what
        # has just happened, and pasting whole previous inner lines back made
        # the director copy its own phrasing from tick to tick.
        recent_txt = "\n".join(
            f"[{s['hm']}] {s['location']} / {s['activity']} (with {s['with_who']}, phone {s['phone_access']}). "
            f"{s['sensory']} | events: {s['events']}"
            for s in recent) or "(first scene of the run)"
        days = self.store.recent_days(c.recent_days_in_prompt)
        days_txt = "\n".join(f"{d['date']}: {d['summary']}" for d in days) or "(none)"
        backstory = self.store.get("backstory", "")
        today_events = self.store.events_for_date(self.clock.date_str())
        events_txt = "\n".join(f"[{self.clock.hm(e['ts'])}] ({e['kind']}, s{e['salience']}) {e['text']}" for e in today_events[-12:]) or "(none yet today)"
        msgs = self.store.recent_messages(8)
        msgs_txt = chattext.lines(msgs, self.clock, chars=200) or "(no messages recently)"
        if self.records:
            threads_txt = self.records.threads_brief()
            cast_txt = self.records.cast_sheet(self.state.relationships)
            places_txt = self.records.places_brief()
            arcs_txt = self.records.arcs_brief()
        else:
            threads_txt = json.dumps(self.store.get("open_threads", []), ensure_ascii=False)
            cast_txt = self.state.relationships_brief()
            places_txt = "(none)"
            arcs_txt = "(none)"
        gap = (self.clock.now_ts() - self.last_tick_ts) / 60 if self.last_tick_ts else 0
        hole_txt = ""
        hole = self._hole(schedule)
        if hole:
            gap = (self.clock.now_ts() - self.last_model_ts) / 60
            hole_txt = hole
        body = self.health.brief() if self.health else ""
        sleep = self.health.sleep_brief() if self.health else ""
        body_all = "; ".join(x for x in (sleep, body) if x)
        body_txt = f"HER BODY TODAY: {body_all} (show it in the scene when it would show; do not narrate it every tick)\n" if body_all else ""
        now_txt = ""
        if self.body:
            env = self.body.setting(self.current, blk, self.scene_fresh())
            red = self.body.red(self.state.gauges) if self.config.needs.enabled else []
            red_txt = ""
            if red and self.config.needs.director_may_deviate:
                red_txt = (f" She is {' and '.join(red)}: if the block allows it she may deviate a little for it now (the fridge, a konbini, a nap, dozing off over the worksheet); "
                           f"keep that inside this scene's activity and set `ate` if she eats; leave schedule_change null unless a later block actually moves.")
            where = ""
            try:
                sit = self.situation
                where = sit.director_line() if sit else ""
            except Exception:
                where = ""
            now_txt = ((where + "\n") if where else "") + (f"HER BODY NOW: {self.body.needs_line(self.state.gauges)}; the last scene had her {env.get('line') or 'somewhere'}. "
                       f"Say where this scene puts her in `setting`; she is hot only when the setting makes her hot (walking in it, a room without air-con), comfortable inside with the air-con; if she eats in this scene set `ate`.{red_txt}\n")
        money_txt = (self.money.line() + " (if she buys something in this scene, say what and how much in `spent`)\n") if self.money and self.money.line() else ""
        diet_short = self.diet.short() if self.diet else ""
        diet_txt = f"HER OWN THINGS: {diet_short}\n" if diet_short else ""
        refl = self.reflection.inner_hint() if self.reflection else ""
        ex_line = self.exchange.director_line() if self.exchange else ""
        morning = self.outlook.store.get("morning_intent", {}) if self.outlook else {}
        morning_txt = (f"WHAT TODAY IS TO HER (her own sense, this morning): {morning.get('text', '')}" + chr(10)) if morning.get("date") == self.clock.date_str() else ""
        ex_txt = (f"WHAT SHE SAID TO PEOPLE TODAY (the exchanges, already happened): {ex_line}" + chr(10)) if ex_line else ""
        refl_txt = (f"WHAT SHE HAS BEEN THINKING TODAY (private, hers; about him unless marked; it may color inner, never the events): {refl}" + chr(10)) if refl else ""
        goal_txt = ""
        if self.goals and self.config.goals.enabled:
            gl = self.goals.director_line()
            if gl:
                goal_txt = gl + chr(10)
        if self.commitments:
            cl = self.commitments.director_line()
            if cl:
                goal_txt += cl + chr(10)
        if self.attachment:
            al = self.attachment.director_line()
            if al:
                goal_txt += al + chr(10)
        # what she is going round on. The reference to this went into the
        # prompt when the spiral was built and the assignment did not, so
        # every tick raised NameError -- invisible until she next woke up,
        # because a sleeping girl gets no director ticks.
        spiral_txt = ""
        if self.spirals and self.config.spiral.enabled:
            sl = self.spirals.director_line()
            if sl:
                spiral_txt = sl + chr(10)
        cat = self.phone.catalogue_text() if self.phone else ""
        catalogue_txt = f"{sight.w(self.config, 'director_notes_label')}{cat}\n" if cat else ""

        # what she has agreed to and who decided it for her: the plan
        # honours it, and the director may still have her wriggle out
        _ev = self.events
        stance_txt = (_ev.brief() + "\n") if _ev and _ev.brief() else ""
        # a world with only the seven people who matter in it is a stage set
        around = ""
        try:
            if self.people:
                around = self.people.around({"location": blk["location"], "activity": blk["activity"]})
        except Exception:
            around = ""
        user = (
            f"NOW: {now.strftime('%A %Y-%m-%d %H:%M')} her time. His time: {self.clock.user_now().strftime('%A %H:%M')}. "
            f"Minutes since the last scene: {gap:.0f}.\n"
            + hole_txt
            + f"CALENDAR: {self.calendar.describe(now.date())}\n"
            + (f"GOING ON IN JAPAN THIS WEEK (it can be on the TV, in the group chat, on a poster; never a lecture): {self._japan_line()}\n" if self._japan_line() else "")
            + f"WEATHER: {self.weather.describe(now)}\n\n"
            f"SCHEDULED BLOCK NOW: {blk['start']}-{blk['end']} {blk['activity']} @ {blk['location']} with {blk.get('with', '?')} (phone {blk['phone_access']})\n"
            + (f"PEOPLE SIMPLY THERE (background, not an event, nobody she will remember): {around}\n" if around else "")
            + f"FULL SCHEDULE TODAY:\n{sched.describe(schedule)}\n\n"
            + (self._ledger_txt(schedule) + "\n\n" if self._ledger_txt(schedule) else "")
            + f"HER STATE: {self.state.gauge_line()}\n"
            f"{body_txt}"
            f"{now_txt}"
            f"{money_txt}{diet_txt}{refl_txt}{morning_txt}{goal_txt}{spiral_txt}{ex_txt}"
            f"CAST (who these people are right now):\n{cast_txt}\n\n"
            f"PLACES SHE KEEPS GOING BACK TO: {places_txt}\n"
            f"{self._brief('geography_brief')}\n"
            f"{self._brief('home_brief', (blk or {}).get('location', ''))}"
            f"{self._brief('household_brief')}\n"
            + self._family_txt(now)
            + (f"WHERE HER FRIENDS ARE TODAY (their timetables; a scene with one of them needs them free; a twist is theirs and she finds out only the way people do):\n{self._friends_line()}\n" if self._friends_line() else "")
            + f"{self._brief('household_secret')}\n"
            f"{stance_txt}"
            f"ARCS (slow pressures from the showrunner; nudge, never force, she never names them):\n{arcs_txt}\n\n"
            f"THREADS:\n{threads_txt}\n"
            f"BACKSTORY WITH HIM: {backstory or '(none recorded)'}\n"
            f"RECENT DAYS:\n{days_txt}\n\n"
            f"EVENTS SO FAR TODAY:\n{events_txt}\n\n"
            f"RECENT SCENES:\n{recent_txt}\n\n"
            f"{sight.w(self.config, 'director_digest_label')}{digest_text or sight.w(self.config, 'director_digest_none')}\n"
            f"{catalogue_txt}"
            f"UNREAD MESSAGES FROM HIM: {unread_count}\n"
            f"WHO IS WAITING ON HER RIGHT NOW (from the record, not from the last scene -- do not write that a message sits unread when it does not): {self._waiting()}\n"
            f"HIS SIDE OF THE CHAT (read receipts): {his_side or 'unknown'}\n"
            f"RECENT MESSAGES BETWEEN THEM (already sent, do not restage them):\n{msgs_txt}\n"
        )
        hh = self.household
        if hh:
            try:
                user += hh.director_text()
            except Exception as e:
                logger.log(f"[household] not shown to the director: {type(e).__name__}")
        if extra_events:
            user += f"THINGS THAT JUST HAPPENED (must be reflected): {json.dumps(extra_events, ensure_ascii=False)}\n"

        messages = [{"role": "system", "content": self.config.prompt_text("director")}, {"role": "user", "content": user}]
        data, raw = self.llm.call_json("director", messages)
        if isinstance(data, dict) and "activity" in data:
            self.last_model_ts = self.clock.now_ts()
            self.store.set("director_last_model_ts", self.last_model_ts)
            if hole:
                logger.log(f"[director] catch-up scene written for the hole ({len(data.get('events') or [])} events)")
                self.catch_up = False
                self.hole_written = True
        else:
            logger.log("[director] output unparseable, falling back to schedule block"
                       + ("; the hole stays open" if hole else ""))
            logger.write_artifact("director_rejects.txt", f"{now}\n{raw}\n")
            data = {"location": blk["location"], "activity": blk["activity"], "with": blk.get("with", "alone"),
                    "phone_access": blk["phone_access"], "sensory": "", "events": [],
                    "share_worthy": False, "share_hint": "", "open_threads": self.records.open_thread_texts() if self.records else [],
                    "resolved_threads": [], "schedule_change": None, "next_tick_minutes": c.tick_minutes}
        return self._settle_scene(data, blk, unread_count, raw)

    # A scene the console started. It goes through `_settle_scene`, the one
    # writer, so it is a real scene of her day: a `scenes` row, its events, and
    # `director_current`. That is what makes it part of her memory later, and
    # what keeps the stage and her words from disagreeing.
    def apply_directive(self, proposal, blk, scene_id, unread_count=0):
        """Write the scene the console proposed and hold it until cleared."""
        proposal = proposal or {}
        place = str(proposal.get("place") or "").strip()
        data = {
            "location": place or "here",
            "activity": str(proposal.get("text") or "a scene he set"),
            "with": str(proposal.get("with") or "him"),
            "phone_access": "free",
            "sensory": "",
            # what she is wearing is part of the scene, so she knows it in the
            # moment (`scene_brief`) and it is on the record afterwards
            "outfit": str(proposal.get("outfit_note") or ""),
            "events": [],
            "share_worthy": True,
            "share_hint": "",
            "resolved_threads": [],
            "schedule_change": None,
            "next_tick_minutes": int(self.config.director.tick_max_minutes),
        }
        got = self._settle_scene(data, blk, unread_count, raw="directed by the console")
        self.directive = {"scene_id": str(scene_id or ""),
                          "title": str(proposal.get("text") or ""),
                          "place": place, "bg": str(proposal.get("bg") or "")}
        self.store.set("director_directive", self.directive)
        logger.log(f"[director] a directed scene is live: {self.directive['title'][:80]}")
        return got

    def clear_directive(self):
        """Hand the scene back to the plan. The directed scene stays on the
        record as the scene that happened; the next tick writes the plan's."""
        self.directive = None
        self.store.set("director_directive", None)
        logger.log("[director] the directed scene is cleared; the plan resumes")

    def set_outfit(self, note):
        """He dressed her by hand: the outfit is a fact of the scene she is in,
        so it goes into `director_current` and into her situation
        (`scene_brief`), and she knows what she is wearing. It is not a new scene
        and it does not move the plan."""
        note = str(note or "").strip()
        if not self.current:
            return ""
        self.current["outfit"] = note
        self._keep_scene(self.current)
        logger.log(f"[director] outfit set by hand: {note[:80] or 'her default'}")
        return note

    def set_place(self, note):
        """He picked the place by hand. Keep it in her current situation."""
        note = str(note or "").strip()
        if not self.current or not note:
            return ""
        self.current["location"] = note
        self._keep_scene(self.current)
        logger.log(f"[director] place set by hand: {note[:80]}")
        return note

    # digits, clock times and the words that only ever carry a figure. Two
    # sentences that match once these are gone are the same observation with
    # the counter moved on.
    _FIGURES = re.compile(r"\d[\d.,:]*\s*(?:%|h|m|s|min(?:ute)?s?|sec(?:ond)?s?|hours?|keys?|windows?|tabs?)?", re.I)

    def _same_but_the_figures(self, text):
        """Is this the previous event over again with the numbers moved on?

        The director is asked for a scene every `tick_minutes`, and a machine
        he has walked away from produces the same true sentence every time:
        "He's been away from the machine for 116 / 177 / 237 / 371 / 485
        minutes, nothing touched since 04:19" was 28 of the 31 events written
        about him in one day. Nothing downstream can tell those apart from 28
        things happening, so her day so far, her diary and the compile all read
        them as a day of events.

        Only the immediately previous one is compared, not a window of them: a
        thing that genuinely happens twice with a gap between is two events,
        and the fault this answers is strictly consecutive."""
        prev = str(self.store.get("last_life_event", "") or "")
        if not prev:
            return False
        a = " ".join(self._FIGURES.sub(" ", str(text or "")).split()).lower()
        b = " ".join(self._FIGURES.sub(" ", prev).split()).lower()
        return bool(a) and a == b

    def _settle_scene(self, data, blk, unread_count, raw=""):
        """Everything that happens to a scene after somebody has written it:
        the fields checked, the money spent, the meal noted, the events and
        the household's moves written to the record, the threads synced, the
        timestep clamped, the row saved and the scene kept whole.

        One copy, whether the scene came from the model or was cut from the
        plan, because two copies would drift and the second one would be the
        one nobody reads."""
        c = self.config.director
        if data.get("phone_access") not in ("free", "glance", "none"):
            data["phone_access"] = blk["phone_access"]
        data["open_note"] = (data.get("open_note") or "").strip() if isinstance(data.get("open_note"), str) else ""
        if data.get("setting") not in ("outdoors", "indoors_ac", "indoors", "transit", "bath"):
            data["setting"] = ""
        data["ate"] = data["ate"].strip().lower() if isinstance(data.get("ate"), str) and data["ate"].strip().lower() in ("meal", "snack") else ""
        if data["ate"] and self.body:
            self.body.note_meal(data["ate"], self.state.gauges)
        if self.money and isinstance(data.get("spent"), dict):
            data["spent_yen"] = self.money.spend(data["spent"])
        events = [e for e in (data.get("events") or []) if isinstance(e, dict) and e.get("text")]
        for e in events:
            try:
                sal = int(e.get("salience", 1))
            except (TypeError, ValueError):
                sal = 1
            e["salience"] = max(1, min(5, sal))
            # an event claiming he got in touch, with no inbound message on
            # the record to match it (sim/reconcile.py). Flag only.
            reconcile.flag_restaged_contact(e["text"], "director event", self.store, self.clock)
            if self._same_but_the_figures(e["text"]):
                logger.log(f"[director] event dropped, the last one said this with different numbers: {e['text'][:90]}")
                continue
            # An event is an invention, and a character who only READS a world
            # invents for her own circle and nobody else. Hers put two of the
            # owner's cast members in the flea-market conversation and gave one
            # of them a yukata to look for; none of it reached the world file,
            # so the partition held, but it is a second answer to a question
            # that is not hers (`sim/roster.mentions_outside`).
            if roster.mentions_outside(self.config, e["text"]):
                logger.log("[director] event dropped, it gives somebody outside her own circle "
                           f"something to do: {e['text'][:90]}")
                continue
            self.store.add_event(self.clock.now_ts(), self.clock.date_str(), "life", e["text"], e["salience"])
            self.store.set("last_life_event", e["text"])
        # the household's moves: checked against the seed and the budget by
        # code, and written into the record as events she will meet
        hh = self.household
        if hh and data.get("household_changes"):
            try:
                for text, sal in hh.apply(data.get("household_changes")):
                    self.store.add_event(self.clock.now_ts(), self.clock.date_str(), "household", text, sal)
                    events.append({"text": text, "salience": sal})
            except Exception as e:
                logger.log(f"[household] moves not applied: {type(e).__name__}: {e}")
        data["events"] = events
        opens = data.get("open_threads") if isinstance(data.get("open_threads"), list) else None
        resolved = data.get("resolved_threads") if isinstance(data.get("resolved_threads"), list) else []
        if opens is not None:
            if self.records:
                self.records.sync_threads([str(t) for t in opens], [str(t) for t in resolved], people_hint=str(data.get("with", "")))
            else:
                self.store.set("open_threads", [str(t) for t in opens][: c.max_open_threads])
        if data.get("schedule_change"):
            self.store.add_event(self.clock.now_ts(), self.clock.date_str(), "schedule_change", json.dumps(data["schedule_change"], ensure_ascii=False), 1)
        try:
            nt = int(data.get("next_tick_minutes", c.tick_minutes))
        except (TypeError, ValueError):
            nt = c.tick_minutes
        nt = max(c.tick_min_minutes, min(c.tick_max_minutes, nt))
        # a scene that wants his attention, or a phone in hand, should not coast for an hour
        if data.get("share_worthy") or unread_count:
            nt = min(nt, c.tick_minutes)
        # a red need (starving, exhausted) keeps the world close until it is met
        if self.body and self.config.needs.enabled and self.body.red(self.state.gauges) and not data["ate"]:
            nt = min(nt, self.config.needs.red_tick_minutes)
        data["next_tick_minutes"] = nt

        ts = self.clock.now_ts()
        self.store.add_scene(ts, self.clock.date_str(), self.clock.hm(), data, raw)
        self.last_tick_ts = ts
        self.next_tick_minutes = nt
        self.store.set("director_last_tick_ts", ts)
        self.store.set("director_next_tick_minutes", nt)
        data["ts"] = ts
        data["hm"] = self.clock.hm()
        data["with_who"] = data.get("with", "")
        # the people who are simply there (tomoe/npc.py around): code, not the
        # model, and never an event -- background for her prompt only
        try:
            data["around"] = self.people.around(data) if self.people else ""
        except Exception:
            data["around"] = ""
        self.current = data
        self._keep_scene(data)
        logger.log(f"[director {data['hm']}] {data['location']} / {data['activity']} (phone {data['phone_access']}, {data.get('setting') or 'setting ?'}{', ate ' + data['ate'] if data.get('ate') else ''}, next in {nt}m) :: {data.get('sensory', '')[:140]}")
        for e in events:
            logger.log(f"    event s{e['salience']}: {e['text']}")
        return data


def scene_brief(scene):
    if not scene:
        return "(no scene yet)"
    s = f"{scene.get('location', '')}: {scene.get('activity', '')}"
    w = scene.get("with") or scene.get("with_who")
    if w and w != "alone":
        s += f", with {w}"
    # What she is wearing is a fact about her body, not a stage direction: she
    # knows it and may speak of it, which is why a hand-picked outfit can be
    # noticed at all (2026-09-18).
    if scene.get("outfit"):
        s += f". you are wearing {scene['outfit']}"
    if scene.get("sensory"):
        s += f". {scene['sensory']}"
    if scene.get("around"):
        s += f". people about, nobody in particular: {scene['around']}"
    return s
