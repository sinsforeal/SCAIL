import logger
from sim import chattext
from sim import wiring
from sim import sight
from sim import reconcile
from sim import roster
from sim.director import scene_brief

# What she thinks about him, to herself. After the app has shown her
# something (a digest, his likes, a note), or when curiosity or being
# ignored has built up, and she is alone with a quiet minute, one call
# reads the day's evidence about him the way she would turn it over: what
# it means, whether it bothers her, what she would ask and will not. The
# thought is private (kv reflections; the last few sit in her system
# prompt as things she has thought, never as things she said), it moves
# her gauges (this is where the jealous pang and the settling live), and
# it leaves the director an inner line. He never sees it unless her state
# makes her speak.
#
# And about anyone else (2026-08-26). Thirty reflections in the save and
# thirty about him, by construction: the only private mind she had was
# pointed at him. Now a subject is chosen by pressure -- him on the old
# triggers, or a person she talked with today whose exchange she has not
# turned over, weighted by the tension and standing she carries with them
# -- and a cast thought reads the record of what was said, not the app.
# The thought reaches her prompt, the director, and `cast_reply` for the
# person it is about, so the next thing she says to Rena has an interior
# behind it.


class Reflection:
    WIRES = ('commitments', 'records', 'sentiments', 'social',)
    def __init__(self, config, llm, store, clock, state, phone=None, social=None, notes=None, receipts=None):
        self.config = config
        self.llm = llm
        self.store = store
        self.clock = clock
        self.state = state
        self.phone = phone
        self.social = social
        self.notes = notes
        self.receipts = receipts
        self.records = None        # wired by App: the cast sheet and threads
        self.sentiments = None
        self.commitments = None
        self.last_ts = store.get("reflect_last_ts", 0)
        self.last_digest_ts = store.get("reflect_last_digest_ts", 0)
        wiring.declare(self)

    def _count(self):
        return self.store.get("reflect_counts", {}).get(self.clock.date_str(), 0)

    def _cast_count(self):
        return self.store.get("reflect_cast_counts", {}).get(self.clock.date_str(), 0)

    def _him_key(self):
        return self.state._him_key() or "him"

    def cast_subject(self, scene):
        """(who, why) for the person most worth turning over, or ("", why).

        Pressure, not a rota: an exchange today she has not thought about
        yet, weighted by the tension and the standing she carries with that
        person; a person she is in a room with is not turned over (that is
        the conversation, not a thought about it)."""
        c = self.config.reflect
        if not c.cast_enabled:
            return "", "cast off"
        if self._cast_count() >= c.cast_max_per_day:
            return "", "cast daily cap"
        now = self.clock.now_ts()
        last = self.store.get("reflect_cast_last", {})
        if now - float(last.get("_ts", 0)) < c.cast_min_gap_minutes * 60:
            return "", "too soon (cast)"
        today = self.clock.date_str()
        # who is standing next to her, as roles: the scene names them in free
        # text and the record names them in Japanese, so neither is a
        # substring of the other and the test has to go through the roster
        here_txt = str(scene.get("with") or scene.get("with_who") or "alone")
        here = {roster.role_of(self.config, tok) for tok in
                here_txt.replace(",", " ").replace("/", " ").replace("と", " ").split()}
        here.discard("")
        best, why, score = "", "", 0.0
        rels = self.state.relationships or {}
        for x in self.store.get("cast_chat", []):
            if x.get("date") != today:
                continue
            who = x.get("who", "")
            if not who or who == self._him_key() or roster.role_of(self.config, who) in here:
                continue
            stamp = f"{x.get('date')} {x.get('hm')}"
            if last.get(who) == stamp:
                continue    # already turned over
            r = rels.get(who, {}) or {}
            s = 1.0 + float(r.get("tension", 0) or 0) / 50.0 + max(0.0, 50.0 - float(r.get("standing", 50) or 50)) / 50.0
            s += 0.5 * len(x.get("turns", [])) / 6.0
            if s > score:
                best, score, why = who, s, f"{who} after {x.get('hm')} ({x.get('kind')}; tension {r.get('tension')}, standing {r.get('standing')})"
        if best and score >= c.cast_score_from:
            return best, why
        return "", "nobody to turn over"

    def due(self, scene):
        """(ok, why, subject): a quiet moment, something to turn over (or
        enough pressure), caps and gaps. Subject is him or a cast name."""
        c = self.config.reflect
        if not c.enabled or not scene:
            return False, "off", ""
        w = (scene.get("with") or scene.get("with_who") or "alone").lower()
        if w != "alone" and c.alone_only:
            return False, "not alone", ""
        now = self.clock.now_ts()
        if now - self.last_ts < c.min_gap_minutes * 60:
            return False, "too soon", ""
        # a person she talked with today comes before him when the pressure
        # with them is there; the phone is not needed to think about Rena
        who, cwhy = self.cast_subject(scene)
        if who:
            return True, cwhy, who
        if scene.get("phone_access") == "none":
            return False, "no phone", ""
        if self._count() >= c.max_per_day:
            return False, "daily cap", ""
        g = self.state.gauges
        digests = self.store.digests_for_date(self.clock.date_str())
        new_digest = bool(digests) and digests[-1]["ts"] > self.last_digest_ts
        st = self.receipts.status() if self.receipts else None
        ignored = bool(st and st.get("state") == "read" and st.get("minutes", 0) >= c.ignored_minutes)
        him = self._him_key()
        if new_digest:
            return True, sight.w(self.config, "reflect_why_new"), him
        if g.get("curiosity", 0) >= c.curiosity_from:
            return True, f"curiosity {int(g['curiosity'])}", him
        if g.get("jealousy", 0) >= c.jealousy_from:
            return True, f"jealousy {int(g['jealousy'])}", him
        if g.get("guilt", 0) >= c.guilt_from:
            return True, f"guilt {int(g['guilt'])}", him
        if ignored:
            return True, "read and left", him
        return False, "nothing to turn over", ""

    def after_reading(self, scene, why, record):
        """Her reaction to something of his she has just read.

        The record is handed to the call rather than left to be found
        among the day's events: it is the thing this thought is about,
        and the events list holds a dozen other rows by evening."""
        c = self.config.reflect
        if not c.enabled or not scene or not str(record or "").strip():
            return None
        w = (scene.get("with") or scene.get("with_who") or "alone").lower()
        if w != "alone" and c.alone_only:
            logger.log(f"[reflect] not after the read: she is with {w[:30]}")
            return None
        if self._count() >= c.max_per_day:
            logger.log("[reflect] not after the read: the day's cap is spent")
            return None
        return self.run(scene, why=why, record=record)

    def run(self, scene, why="", subject="", record=""):
        c = self.config.reflect
        today = self.clock.date_str()
        him = self._him_key()
        if subject and subject != him:
            return self.run_cast(scene, subject, why)
        digests = self.store.digests_for_date(today)[-4:]
        dig_txt = "\n".join(f"[{self.clock.hm(d['ts'])}] {d['text']}" for d in digests) or sight.w(self.config, "digest_none_today")
        live = self.phone.live_line() if self.phone else ""
        likes = self.social.his_likes_line() if self.social else ""
        follows = self.social.his_follows_line() if self.social else ""
        about = self.social.about_him_line() if self.social else ""
        notes = self.notes.index_text(limit=3) if self.notes else ""
        msgs = self.store.recent_messages(12)
        chat = chattext.lines(msgs, self.clock, chars=200) or "(nothing recent)"
        st = self.receipts.status() if self.receipts else None
        his_side = self.receipts.brief(st) if self.receipts else ""
        prev = self.store.get("reflections", [])[-2:]
        prev_txt = "\n".join(f"- {p['date']} {p['hm']}: {p['thought'][:200]}" for p in prev) or "(none)"
        facts = self.store.user_facts()[-15:]
        user = (
            f"TIME: {self.clock.both()}\nWHERE SHE IS: {scene_brief(scene)}\nHOW SHE FEELS: {self.state.mood_tags()}\nWHY NOW: {why}\n\n"
            + (f"WHAT SHE JUST READ (the record as it was stored -- the machine's account of what was "
               f"there, not her words; what it did to her is what you write):\n{record}\n\n" if record else "")
            + f"{sight.w(self.config, 'digest_today_label')}\n{dig_txt}\n" + (f"RIGHT NOW: {live}\n" if live else "") +
            (f"\n{likes}\n" if likes else "") + (f"{follows}\n" if follows else "") +
            (f"\n{about}\n" if about else "") +
            (f"\nNOTES OF HIS SHE HAS READ:\n{notes}\n" if notes else "") +
            f"\nTHE CHAT LATELY:\n{chat}\nHIS SIDE: {his_side or 'unknown'}\n\n"
            f"WHAT SHE KNOWS ABOUT HIM (recent):\n" + "\n".join(f"- {f}" for f in facts) + "\n\n"
            f"WHAT SHE THOUGHT LAST TIME (do not repeat):\n{prev_txt}\n"
        )
        system = self.config.role_system("reflect")
        data, raw = self.llm.call_json("reflect", [{"role": "system", "content": system}, {"role": "user", "content": user}])
        self.last_ts = self.clock.now_ts()
        self.store.set("reflect_last_ts", self.last_ts)
        if digests:
            self.last_digest_ts = digests[-1]["ts"]
            self.store.set("reflect_last_digest_ts", self.last_digest_ts)
        self.store.bump_today("reflect_counts", today)
        if not isinstance(data, dict) or not str(data.get("thought", "")).strip():
            logger.log("[reflect] nothing came")
            return None
        thought = str(data["thought"]).strip()[:700]
        stance = str(data.get("stance", "") or "").strip()[:200]
        ask = str(data.get("would_ask", "") or "").strip()[:160]
        rec = {"date": today, "hm": self.clock.hm(), "about": him, "thought": thought, "stance": stance, "would_ask": ask, "why": why}
        self.store.set("reflections", (self.store.get("reflections", []) + [rec])[-c.keep:])
        deltas = data.get("deltas") if isinstance(data.get("deltas"), dict) else {}
        allowed = {k: v for k, v in deltas.items() if k in c.gauges_it_may_move}
        if allowed:
            self.state.apply(allowed, {})
            self.state.save()
        reconcile.flag_own_photo(thought, "reflect", self.store, self.clock)
        self.store.add_event(self.clock.now_ts(), today, "reflect", f"(private) {thought[:160]}", 1)
        logger.log(f"[reflect] ({why}) {thought[:160]}" + (f" | stance: {stance[:80]}" if stance else "") + (f" | deltas {allowed}" if allowed else ""))
        return rec

    def run_cast(self, scene, who, why=""):
        """One private thought about a person in her own life, from the
        record of what was said. No app, no digest: the evidence is the
        exchange."""
        c = self.config.reflect
        today = self.clock.date_str()
        yday = self._yesterday()
        rows = [x for x in self.store.get("cast_chat", [])
                if roster.same(self.config, who, x.get("who")) and x.get("date", "") >= yday]
        talks = []
        for x in rows[-4:]:
            day = "today" if x["date"] == today else "yesterday"
            talks.append(f"[{day} {x['hm']}, {x['kind']}] " + " / ".join(f"{t['who']}: {t.get('text') or t.get('ja', '')}" for t in x["turns"]))
        talks_txt = "\n".join(talks) or "(nothing recorded)"
        r = (self.state.relationships or {}).get(roster.key_of(self.config, who), {}) or {}
        meters = f"closeness {r.get('closeness', '?')}, standing {r.get('standing', '?')} (how she thinks she ranks in their eyes), tension {r.get('tension', '?')}"
        sheet = ""
        try:
            if self.records:
                sheet = self.records.cast_sheet({who: r}, meters=False, influence=True)
        except Exception:
            pass
        sent = ""
        try:
            if self.sentiments:
                sent = ", ".join(f"{k} {self.sentiments.live(who, k):.0f}" for k in ("attachment", "resentment", "respect", "contempt"))
        except Exception:
            pass
        threads = ""
        try:
            if self.records:
                threads = self.records.threads_brief()
        except Exception:
            pass
        promise = ""
        try:
            if self.commitments:
                promise = self.commitments.brief_for(who)
        except Exception:
            pass
        prev = [p for p in self.store.get("reflections", []) if p.get("about") == who][-2:]
        prev_txt = "\n".join(f"- {p['date']} {p['hm']}: {p['thought'][:200]}" for p in prev) or "(none)"
        user = (
            f"TIME: {self.clock.both()}\nWHERE SHE IS: {scene_brief(scene)}\nHOW SHE FEELS: {self.state.mood_tags()}\nWHY NOW: {why}\n\n"
            f"WHO: {who}\n{sheet}\nHER METERS WITH {who.upper()}: {meters}\n"
            + (f"WHAT {who.upper()} IS TO HER (slow, weeks): {sent}\n" if sent else "")
            + f"\nWHAT WAS ACTUALLY SAID (today and yesterday):\n{talks_txt}\n"
            + (f"\nRUNNING THREADS:\n{threads}\n" if threads else "")
            + (f"\nPROMISE ON THE TABLE: {promise}\n" if promise else "")
            + f"\nWHAT SHE THOUGHT ABOUT {who.upper()} LAST TIME (do not repeat):\n{prev_txt}\n"
        )
        base = self.config.prompt_text("reflect")
        style = base[base.find("### How she talks"):] if "### How she talks" in base else ""
        system = self.config.role_system("reflect_cast", style)
        data, raw = self.llm.call_json("reflect_cast", [{"role": "system", "content": system}, {"role": "user", "content": user}])
        now = self.clock.now_ts()
        self.last_ts = now
        self.store.set("reflect_last_ts", now)
        last = self.store.get("reflect_cast_last", {})
        last["_ts"] = now
        if rows:
            last[who] = f"{rows[-1].get('date')} {rows[-1].get('hm')}"
        self.store.set("reflect_cast_last", last)
        self.store.bump_today("reflect_cast_counts", today)
        if not isinstance(data, dict) or not str(data.get("thought", "")).strip():
            logger.log(f"[reflect] nothing came (about {who})")
            return None
        thought = str(data["thought"]).strip()[:700]
        stance = str(data.get("stance", "") or "").strip()[:200]
        ask = str(data.get("would_ask", "") or "").strip()[:160]
        rec = {"date": today, "hm": self.clock.hm(), "about": who, "thought": thought, "stance": stance, "would_ask": ask, "why": why}
        self.store.set("reflections", (self.store.get("reflections", []) + [rec])[-c.keep:])
        deltas = data.get("deltas") if isinstance(data.get("deltas"), dict) else {}
        allowed = {k: v for k, v in deltas.items() if k in c.cast_gauges_it_may_move}
        if allowed:
            self.state.apply(allowed, {})
            self.state.save()
        self.store.add_event(now, today, "reflect", f"(private, about {who}) {thought[:160]}", 1)
        logger.log(f"[reflect] about {who} ({why}) {thought[:160]}" + (f" | stance: {stance[:80]}" if stance else "") + (f" | deltas {allowed}" if allowed else ""))
        return rec

    def _yesterday(self):
        import datetime
        return (self.clock.now().date() - datetime.timedelta(days=1)).isoformat()

    def prompt_text(self):
        """The last few private thoughts, for her system prompt."""
        c = self.config.reflect
        rows = self.store.get("reflections", [])[-c.in_prompt:]
        him = self._him_key()
        return "\n".join(f"- {r['date'][5:]} {r['hm']} (about {'him' if r.get('about', him) == him else r['about']}): {r['thought']}"
                         + (f" (what you would never say: {r['stance']})" if r.get("stance") else "") for r in rows)

    def inner_hint(self, about=None):
        """Today's latest thought, for the director (any subject) or the
        intent (about him only -- a thought about Rena is not what she is
        carrying toward HIM)."""
        rows = [r for r in self.store.get("reflections", []) if r["date"] == self.clock.date_str()]
        if about:
            rows = [r for r in rows if r.get("about", self._him_key()) == about]
        if not rows:
            return ""
        r = rows[-1]
        who = r.get("about", self._him_key())
        tag = "" if who == self._him_key() else f"(about {who}) "
        return tag + r["thought"][:200]

    def about(self, who, days=2):
        """What she has privately thought about this person lately, for the
        call that writes her next words to them."""
        import datetime
        since = (self.clock.now().date() - datetime.timedelta(days=days - 1)).isoformat()
        rows = [r for r in self.store.get("reflections", []) if r.get("about") == who and r["date"] >= since]
        return "\n".join(f"- {r['date'][5:]} {r['hm']}: {r['thought']}" + (f" (never said: {r['stance']})" if r.get("stance") else "") for r in rows[-2:])
