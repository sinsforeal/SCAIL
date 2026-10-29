import re
from sim import chattext
from sim import wiring
import logger
from sim import sight
from sim import reconcile
from sim.director import scene_brief

# Three small pieces of her own mind that are not about him:
#  - experience: when a scene has her actually watching, reading, listening
#    or playing something, one call writes what she made of it (a real
#    title for the season, what she thought) into her media diet, so "what
#    are you into" has an opinion behind it and not a one-liner.
#  - morning: at the wake tick, what today is to her (what she wants, what
#    she dreads), first person; her situation carries it through the day
#    and the director sees it as intent.
#  - anticipation: before a thing she can see coming (a calendar event
#    today or tomorrow; his usual first activity, read off the app's day
#    shape), what she is looking forward to or bracing for; a line in her
#    situation for a couple of hours and a small nudge to the gauges.


class Outlook:
    WIRES = ('commitments', 'diet',)
    def __init__(self, config, llm, store, clock, state, calendar=None, phone=None, diet=None, records=None, health=None, money=None, self_model=None, watchlist=None, recap=None):
        self.config = config
        self.llm = llm
        self.store = store
        self.clock = clock
        self.state = state
        self.calendar = calendar
        self.phone = phone
        self.diet = diet
        self.records = records
        self.health = health
        self.money = money
        self.self_model = self_model
        self.watchlist = watchlist
        self.recap = recap
        wiring.declare(self)

    # ---------------- experience ----------------

    def experience_due(self, scene):
        c = self.config.experience
        if not c.enabled or not scene:
            return False
        act = (scene.get("activity", "") or "").lower()
        if not re.search(c.trigger_regex, act, re.I):
            return False
        if not self._has_object(act):
            return False
        counts = self.store.get("experience_counts", {})
        if counts.get(self.clock.date_str(), 0) >= c.max_per_day:
            return False
        last = self.store.get("experience_last_ts", 0)
        return (self.clock.now_ts() - last) >= c.min_gap_minutes * 60

    def _has_object(self, act):
        """Is there a thing here to have an experience OF? The trigger is only
        a verb, and her verbs attach to him as readily as to a show -- reading
        his reply, watching the typing indicator, listening to her dad. This
        asks for the object: a category noun, or the name of something on her
        own watchlist (a scene can say "K-On" and never say "episode")."""
        obj = getattr(self.config.experience, "object_regex", "")
        if obj and re.search(obj, act, re.I):
            return True
        if not self.watchlist:
            return False
        for show in self.watchlist.all():
            for name in (show.get("title", ""), show.get("ja", "")):
                if name and len(name) >= 3 and name.lower() in act:
                    return True
        return False

    def _watching(self, scene):
        act = (scene.get("activity", "") or "").lower()
        return bool(re.search(self.config.experience.watch_regex, act))

    def experience(self, scene):
        c = self.config.experience
        today = self.clock.date_str()
        recent = self.diet.things_recent(21) if self.diet else []
        recent_txt = "\n".join(f"- {d['date']}: {d['text']}" for d in recent[-8:]) or "(nothing on record)"
        # grounded watching: if the scene is her watching and she has a show
        # on her list, pin THIS title+episode and hand the model the real
        # あらすじ so she reacts to what happened, not an invention
        watching, recap_txt = None, ""
        if self.watchlist and self._watching(scene):
            watching = self.watchlist.current()
            if watching and self.recap:
                # with the model client the fetch is the judged path: several
                # candidates, one judge, the transcript or the official blurb
                # as the anchor. Her own watching used to take the first page
                # that passed the section test and trust it forever.
                #
                # The English title goes with it, because the fetcher reads
                # the English episode list only when it is given one, and a
                # show on her own list carries no id to reach the other
                # English source. Without it her own watching ran on the
                # Japanese blog search alone while his ran on three sources:
                # not one page from either English source is in the archive
                # for any of the three episodes of her own list fetched so far.
                recap_txt = self.recap.recap_for(watching, watching.get("ep"),
                                                 llm=self.llm,
                                                 english=watching.get("title", "")) or ""
        pin = ""
        if watching:
            ep = watching.get("ep", 1)
            pin = (f"\nSHE IS WATCHING: {watching['title']} episode {ep}"
                   f" ({watching.get('kind', 'anime')}). Use exactly this title and episode number.\n")
            if recap_txt:
                pin += ("この話で実際に起きること（あらすじ。作り話をせず、これに反応して。"
                        "ネタバレでも彼女はもう観たのでOK）:\n" + recap_txt[:1800] + "\n")
            else:
                pin += "(no synopsis found; react as if she just watched it, keep it vague about plot)\n"
        user = (
            f"TIME: {self.clock.both()} (season: {self.calendar.describe(self.clock.now().date())[:120] if self.calendar else ''})\n"
            f"WHERE SHE IS / WHAT SHE IS DOING: {scene_brief(scene)}\nHOW SHE FEELS: {self.state.mood_tags()}\n"
            f"{pin}\n"
            f"WHAT SHE HAS BEEN INTO (her record; continue these when it fits, do not restart them):\n{recent_txt}\n"
        )
        system = self.config.role_system("experience")
        data, raw = self.llm.call_json("experience", [{"role": "system", "content": system}, {"role": "user", "content": user}])
        self.store.set("experience_last_ts", self.clock.now_ts())
        self.store.bump_today("experience_counts", today)
        if not isinstance(data, dict) or not str(data.get("what", "")).strip() or data.get("skip"):
            logger.log("[experience] nothing she would remember from this")
            return None
        what = str(data["what"]).strip()[:120]
        thought = str(data.get("thought", "") or "").strip()[:300]
        line = f"{what}: {thought}" if thought else what
        if self.diet:
            self.diet.add_things([line], today)
        self.store.add_event(self.clock.now_ts(), today, "her_thing", line, 2)
        if watching and self.watchlist:
            self.watchlist.advance(watching["title"])
        logger.log(f"[experience] {line[:180]}")
        return line

    # ---------------- morning ----------------

    def morning(self, schedule):
        c = self.config.morning
        if not c.enabled:
            return ""
        today = self.clock.date_str()
        prev = self.store.get("morning_intent", {})
        if prev.get("date") == today:
            return prev.get("text", "")
        sched_txt = "\n".join(f"{b['start']}-{b['end']} {b['activity']} @ {b['location']} with {b.get('with', '')}" for b in (schedule or {}).get("blocks", [])) or "(no plan yet)"
        notes = (schedule or {}).get("notes", "")
        threads = self.records.threads_brief() if self.records else ""
        arcs = self.records.arcs_brief() if self.records else ""
        body = "; ".join(x for x in ((self.health.sleep_brief() if self.health else ""), (self.health.brief() if self.health else "")) if x)
        money = self.money.persona_line() if self.money else ""
        # what she has promised people and what it costs: a want may be
        # about funding one, dodging one, or which one when she cannot all
        commit = self.commitments.morning_line() if self.commitments else ""
        days = self.store.recent_days(1)
        yday = days[0]["summary"] if days else ""
        user = (
            f"TODAY: {self.clock.both()}. {self.calendar.describe(self.clock.now().date()) if self.calendar else ''}\n"
            f"HOW SHE WAKES: {self.state.mood_tags()}" + (f"; body: {body}" if body else "") + (f"; {money}" if money else "") + "\n\n"
            f"THE PLAN:\n{sched_txt}\n{notes}\n"
            + (f"\nPROMISES ON THE TABLE (real money, real people; not all of it fits her allowance): {commit}\n" if commit else "")
            + f"\nTHREADS: {threads}\nARCS: {arcs}\n\nYESTERDAY: {yday or '(nothing recorded)'}\n"
            # what a want could be riding on. She is shown the ids and copies
            # one back; matching words to beliefs is what could not tell that
            # "get through it without anyone looking at me" is holding up
            # "being on your own is embarrassing".
            + (f"\nWHAT SHE HAS DECIDED ABOUT HERSELF:\n{self.self_model.anchor_brief()}\n"
               if (self.self_model and self.config.beliefs.enabled) else "")
        )
        system = self.config.role_system("morning")
        data, raw = self.llm.call_json("morning", [{"role": "system", "content": system}, {"role": "user", "content": user}])
        text = str((data or {}).get("text", "") if isinstance(data, dict) else "").strip()[:500]
        if not text:
            logger.log("[morning] nothing came")
            return ""
        self.store.set("morning_intent", {"date": today, "hm": self.clock.hm(), "text": text,
                                          "want": str(data.get("want", ""))[:120], "dread": str(data.get("dread", ""))[:120],
                                          "anchors": {"want": data.get("want_anchor"), "avoid": data.get("dread_anchor")}})
        reconcile.flag_own_photo(text, "morning", self.store, self.clock)
        self.store.add_event(self.clock.now_ts(), today, "morning", f"(to herself, waking) {text[:160]}", 1)
        logger.log(f"[morning] {text[:200]}")
        return text

    def morning_line(self, ja=False):
        m = self.store.get("morning_intent", {})
        if m.get("date") != self.clock.date_str():
            return ""
        return (f"今朝、目が覚めたときに思ったこと: {m['text']}" if ja else
                f"this morning, waking up, you thought: {m['text']}")

    # ---------------- anticipation ----------------

    def _his_wake_hm(self):
        """His usual first activity, her time, from the app's day shapes (kv his_first_active: list of hm strings)."""
        rows = self.store.get("his_first_active", [])
        if len(rows) < 2:
            return None
        mins = sorted(int(r[:2]) * 60 + int(r[3:5]) for r in rows[-7:] if len(r) >= 5)
        return mins[len(mins) // 2]

    def anticipation_due(self, scene):
        c = self.config.anticipation
        if not c.enabled or not scene:
            return False, ""
        today = self.clock.date_str()
        done = self.store.get("anticipation_done", {})
        now = self.clock.now()
        hm = now.hour * 60 + now.minute
        his = self._his_wake_hm()
        if his is not None and 0 <= his - hm <= c.before_minutes and not done.get(f"{today}:his_wake"):
            return True, "his_wake"
        if self.calendar:
            # a thing she can see coming is a day, not a run: the calendar says
            # "today" for a one-day event and "today, day N of M" for an
            # exhibition that runs a month (worth saying on none of its days --
            # calendar.events), and "tomorrow" for the eve, never "in 1 days".
            # Read as prefixes, the first replay of 2026-09-01 dreaded four
            # museum shows in a row and the eve never fired at all.
            for e in self.calendar.events(now.date(), lookahead_days=1):
                key = f"{today}:{e['name']}"
                if e["when"] in ("today", "today, day 1") and hm >= c.event_morning_from_minutes and not done.get(key):
                    return True, f"event:{e['name']}"
                if e["when"] == "tomorrow" and hm >= c.event_eve_from_minutes and not done.get(key + ":eve"):
                    return True, f"eve:{e['name']}"
        return False, ""

    def settle_past_events(self):
        """A catch-up scene has written the day through today's calendar
        events: they are behind her, and nothing anticipates them now."""
        if not self.calendar:
            return
        today = self.clock.date_str()
        done = self.store.get("anticipation_done", {})
        for e in self.calendar.events(self.clock.now().date(), lookahead_days=0):
            key = f"{today}:{e['name']}"
            if e["when"].startswith("today") and not done.get(key):
                done[key] = "covered by the catch-up scene"
                logger.log(f"[anticipation] {e['name']}: the catch-up scene wrote the day past it; not anticipated")
        self.store.set("anticipation_done", {k: v for k, v in done.items() if k.startswith(today)})

    def anticipate(self, scene, why):
        c = self.config.anticipation
        today = self.clock.date_str()
        done = self.store.get("anticipation_done", {})
        # "event:" starts with "eve" -- for a week every today-event was framed
        # as the eve of itself ("tomorrow is ...") and its done-key got ":eve",
        # so it fired again every tick (nine 明日は始業式 lines on 2026-09-01)
        key = f"{today}:his_wake" if why == "his_wake" else f"{today}:{why.split(':', 1)[1]}" + (":eve" if why.startswith("eve:") else "")
        done[key] = True
        self.store.set("anticipation_done", {k: v for k, v in done.items() if k.startswith(today)})
        if why == "his_wake":
            his = self._his_wake_hm()
            about = sight.w(self.config, "outlook_shows_up", hm=f"{his // 60:02d}:{his % 60:02d}") + "; that is less than an hour away. What is she hoping for, bracing for, planning to say or not say?"
        elif why.startswith("eve:"):
            about = f"tomorrow is {why.split(':', 1)[1]}. Tonight, what is she looking forward to or dreading about it?"
        else:
            about = f"today is {why.split(':', 1)[1]}. What is she looking forward to or dreading?"
        msgs = self.store.recent_messages(4)
        chat = chattext.lines(msgs, chars=80, labels=("him", "her"), stamps=False, sep="; ") or "(nothing lately)"
        threads = self.records.threads_brief() if self.records else ""
        user = (f"TIME: {self.clock.both()}\nWHERE SHE IS: {scene_brief(scene)}\nHOW SHE FEELS: {self.state.mood_tags()}\n"
                f"WHAT IS COMING: {about}\nTHE CHAT LATELY: {chat}\nTHREADS: {threads}\n")
        system = self.config.role_system("anticipation")
        data, raw = self.llm.call_json("anticipation", [{"role": "system", "content": system}, {"role": "user", "content": user}])
        if not isinstance(data, dict) or not str(data.get("text", "")).strip():
            logger.log(f"[anticipation] nothing came ({why})")
            return ""
        text = str(data["text"]).strip()[:400]
        self.store.set("anticipation", {"date": today, "ts": self.clock.now_ts(), "why": why, "text": text})
        deltas = data.get("deltas") if isinstance(data.get("deltas"), dict) else {}
        allowed = {k: v for k, v in deltas.items() if k in c.gauges_it_may_move}
        if allowed:
            self.state.apply(allowed, {})
            self.state.save()
        reconcile.flag_own_photo(text, "anticipation", self.store, self.clock)
        self.store.add_event(self.clock.now_ts(), today, "anticipation", f"(to herself) {text[:160]}", 1)
        logger.log(f"[anticipation] ({why}) {text[:180]}" + (f" | deltas {allowed}" if allowed else ""))
        return text

    def anticipation_line(self, ja=False):
        a = self.store.get("anticipation", {})
        if not a or self.clock.now_ts() - a.get("ts", 0) > self.config.anticipation.hours_in_prompt * 3600:
            return ""
        return (f"ここのところ頭にあること: {a['text']}" if ja else f"on your mind lately: {a['text']}")
