import logger
from sim import lang

# When he is around: what she has learned, and what he has told her.
#
# This replaces a parsed window. The first version of it heard "I'm on break
# now for another 15" and built an object with a start, an end and a penalty
# that fired off a clock -- which is declared, not derived, and the rest of
# this project does not work that way. It also could not be right: it knew
# what he said and nothing about what he does.
#
# The record already holds when a user is usually about; nobody had to tell her.
#
# So: no timer, no schedule, no booking. Three things she can actually know.
#
#   the tempo      how live this conversation is RIGHT NOW, from the last few
#                  turns. He is answering in forty seconds, so she answers in
#                  forty seconds. This is what a short break looks like from
#                  the inside, and it works whether or not he mentioned it.
#
#   the shape      how usual it is for him to be about at this hour of HIS
#                  day, faded by age. His silence at three in the morning is
#                  not the same silence as at nine in the evening, and she has
#                  four months of evidence for which is which.
#
#   what he said   because being told is real, and a person who has been told
#                  expects. `hear` takes a stated "last break in about three
#                  hours" and turns it into an expectation with a sign and a
#                  six-hour half-life, which `usual_now` blends over the
#                  learned shape.
#
# The difference between an expectation and the window object this replaced is
# the whole point. Nothing fires off a clock. Nothing charges him for being
# wrong. What being told does is change what she is expecting -- and expecting
# him is exactly what makes his absence land, with no penalty needing to exist.
# It also decays, so a thing he said this morning about his afternoon is not
# something she is still holding him to on Thursday, and the record overtakes
# it: if he turns up, she has learned it for real and the statement is spent.


class Rhythm:
    def __init__(self, config, store, clock, state=None, llm=None, receipts=None, typesafe=None):
        self.config = config
        self.llm = llm
        self.receipts = receipts
        self.store = store
        self.clock = clock
        self.state = state
        # The hosted classifier (`typesafe.py`, `docs/system-one.md`): when her
        # config turns the `said_when` use on, two questions -- did he say
        # anything about when he is reachable, and which kind -- settle the
        # `kind` the role also writes. The timings and the quote stay the
        # role's, so the role is still called; only the kind is overridden.
        self.typesafe = typesafe
        self._cache = None
        self._cache_ts = 0.0

    def _said_when_typesafe(self, user):
        """(found, kind) from Jev: found is `no`/`yes`/None, and kind is one of
        the three or "" when the use is off or under its floor."""
        ts = self.typesafe
        if ts is None or not ts.ready("said_when"):
            return None, ""
        use = ts.use("said_when") or {}
        floor = float(use.get("threshold", 0.5))
        questions = {
            "found": {"type": "choice",
                      "instructions": "Does his message say, in words, anything about when he is or "
                                      "is not reachable -- a break, being out? Do not "
                                      "infer it from him being chatty, the time of day, or him going "
                                      "quiet.",
                      "criteria": {"yes": "he said in words when he is or is not reachable",
                                   "no": "he said nothing about it"}},
            "kind": {"type": "choice",
                     "instructions": "If he did, which kind is it?",
                     "criteria": {"open_now": "he is free now and it is bounded",
                                  "scheduled": "he will be free later and says roughly when",
                                  "unavailable": "a stretch he cannot be reached in"}},
        }
        answers = ts.ask("said_when", {"his message and the clock": user}, questions)
        if not answers:
            return None, ""
        f, fconf = ts.choice(answers, "found")
        if fconf is None or fconf < floor:
            return None, ""
        if f == "no":
            logger.log(f"[rhythm] typesafe: he said nothing about being around (conf {fconf:.2f})")
            return "no", ""
        k, kconf = ts.choice(answers, "kind")
        if k in ("open_now", "scheduled", "unavailable") and kconf is not None and kconf >= floor:
            logger.log(f"[rhythm] typesafe: {k} (conf {kconf:.2f})")
            return "yes", k
        return "yes", ""

    # ---------------- what the record says about his hours ----------------

    def profile(self):
        """Per hour of HIS day: how much of him is usually in it, 0..1, and the
        median minutes he has taken to answer her. Faded by age, so a habit he
        has dropped stops counting."""
        c = self.config.rhythm
        now = self.clock.now_ts()
        if self._cache and now - self._cache_ts < c.cache_seconds:
            return self._cache
        msgs = self.store.recent_messages(c.messages_scanned)
        hours = {h: {"weight": 0.0, "lat": []} for h in range(24)}
        last_her = None
        half = max(1.0, c.half_life_days) * 86400.0
        for m in msgs:
            ts = float(m["ts"])
            h = self.clock.to_user(ts).hour
            age = max(0.0, now - ts)
            fade = 0.5 ** (age / half)
            if m["role"] == "user":
                hours[h]["weight"] += fade
                if last_her is not None:
                    d = (ts - last_her) / 60.0
                    if 0 < d < c.latency_cap_minutes:
                        hours[h]["lat"].append(d)
                last_her = None
            elif last_her is None:
                last_her = ts
        top = max([v["weight"] for v in hours.values()] or [0.0]) or 1.0
        out = {}
        for h, v in hours.items():
            lat = sorted(v["lat"])
            out[h] = {"weight": v["weight"] / top,
                      "median_minutes": (lat[len(lat) // 2] if lat else None),
                      "samples": len(lat)}
        self._cache, self._cache_ts = out, now
        return out

    def learned_now(self, ts=None):
        """0..1: how usual it is for him to be about at this hour of his day,
        from the record alone.

        Smoothed across the neighbouring hours, because nobody's day has edges
        on the hour and one quiet 14:00 in the record should not make 14:00 a
        hole."""
        p = self.profile()
        h = self.clock.to_user(ts or self.clock.now_ts()).hour
        w = self.config.rhythm.neighbour_weight
        near = p[(h - 1) % 24]["weight"] * w + p[h]["weight"] + p[(h + 1) % 24]["weight"] * w
        return max(0.0, min(1.0, near / (1.0 + 2 * w)))

    # ---------------- and what he has actually told her ----------------

    def hear(self, text):
        """He said something about when he is around. It becomes an expectation.

        Not a booking. Nothing fires off a clock because of it, nothing
        punishes him for being wrong, and it does not survive being wrong for
        long. What it does is what being told does to anybody: it changes what
        she is expecting, and expecting him is what makes his absence land."""
        c = self.config.rhythm
        if not c.enabled or not c.hear_enabled or not text or len(text) < c.said_min_chars:
            return []
        low = text.lower()
        if not any(w in low for w in c.said_trigger_words):
            return []
        user = (f"HIS LOCAL TIME NOW: {self.clock.user_now().strftime('%A %Y-%m-%d %H:%M')}\n"
                f"HER LOCAL TIME NOW: {self.clock.now().strftime('%A %Y-%m-%d %H:%M')}\n"
                f"(she is {self.clock.offset_hours():+.0f} hours from him)\n\n"
                f"HIS MESSAGE:\n{text[:1500]}")
        messages = [{"role": "system", "content": self.config.prompt_text("said_when")},
                    {"role": "user", "content": user}]
        data, raw = self.llm.call_json("said_when", messages) if self.llm else (None, "")
        # The classifier's reading of whether he said anything, and which kind,
        # stands over the role's when it answers above its floor; the role still
        # supplies the timings and the quote.
        jfound, jkind = self._said_when_typesafe(user)
        if jfound == "no":
            return []
        if not isinstance(data, dict) or not data.get("found"):
            return []
        now = self.clock.now_ts()
        rows = self.store.get("rhythm_said", [])
        added = []
        for f in (data.get("windows") or [data])[: c.said_max_per_message]:
            try:
                kind = jkind or str(f.get("kind", "")).strip()
                starts = float(f.get("starts_in_minutes", 0) or 0)
                lasts = float(f.get("lasts_minutes", 0) or 0)
                conf = float(f.get("confidence", 0.5) or 0.5)
            except (TypeError, ValueError):
                continue
            if kind not in ("open_now", "scheduled", "unavailable") or lasts <= 0:
                continue
            if conf < c.said_min_confidence:
                continue
            lasts = min(lasts, c.said_max_hours * 60)
            start = now + starts * 60
            row = {"said_ts": now, "start_ts": start, "end_ts": start + lasts * 60,
                   "direction": -1 if kind == "unavailable" else 1,
                   "quote": str(f.get("quote", ""))[:200], "confidence": round(conf, 2)}
            if any(abs(float(o["start_ts"]) - start) < c.said_dedupe_minutes * 60
                   and o.get("direction") == row["direction"] for o in rows):
                continue
            rows.append(row)
            added.append(row)
            when = self.clock.to_char(start).strftime("%a %H:%M")
            logger.log(f"[rhythm] he told her: {'around' if row['direction'] > 0 else 'not around'} "
                       f"for {lasts:.0f} min from {when} her time — \"{row['quote'][:70]}\"")
        if added:
            self.store.set("rhythm_said", rows[-c.said_keep:])
        return added

    def expectation(self, ts=None):
        """-1..+1: what he has told her about this moment, faded since he said it.

        Positive: he said he would be about. Negative: he said he would not.
        Faded, because a thing he said three days ago about his afternoon is
        not a thing she is still holding him to."""
        c = self.config.rhythm
        if not c.enabled or not c.hear_enabled:
            return 0.0
        ts = ts or self.clock.now_ts()
        best = 0.0
        for r in self.store.get("rhythm_said", []):
            try:
                if not (float(r["start_ts"]) <= ts <= float(r["end_ts"])):
                    continue
                age_h = max(0.0, (ts - float(r["said_ts"])) / 3600.0)
                fade = 0.5 ** (age_h / max(0.5, c.said_half_life_hours))
                v = float(r.get("direction", 1)) * float(r.get("confidence", 0.5)) * fade
            except (TypeError, ValueError, KeyError):
                continue
            if abs(v) > abs(best):
                best = v
        return max(-1.0, min(1.0, best))

    def said_now(self, ts=None):
        """The row he said, if one covers this moment. For her prompt."""
        ts = ts or self.clock.now_ts()
        live = [r for r in self.store.get("rhythm_said", [])
                if float(r.get("start_ts", 0)) <= ts <= float(r.get("end_ts", 0))]
        return max(live, key=lambda r: float(r.get("said_ts", 0))) if live else None

    def usual_now(self, ts=None):
        """What she actually expects of him at this moment: what she has
        learned, moved by what he has told her.

        Both, because both are real. Four months of record say he is never
        about at three in the morning; him saying "I'm up, talk to me" is worth
        more than the record for the next hour, and worth nothing by tomorrow."""
        c = self.config.rhythm
        base = self.learned_now(ts)
        e = self.expectation(ts)
        if e > 0:
            return max(0.0, min(1.0, base + (1.0 - base) * e * c.said_weight))
        return max(0.0, min(1.0, base * (1.0 + e * c.said_weight)))

    def usual_latency(self, ts=None):
        """What he usually takes to answer at this hour, in minutes, or None."""
        p = self.profile()
        h = self.clock.to_user(ts or self.clock.now_ts()).hour
        for hh in (h, (h - 1) % 24, (h + 1) % 24):
            if p[hh]["samples"] >= self.config.rhythm.min_samples:
                return p[hh]["median_minutes"]
        return None

    # ---------------- how live it is right now ----------------

    def presence(self):
        """0..1: is he actually at the phone, right now.

        This replaces `tempo`, which had three terms and one signal -- his last
        latency, the message density and the freshness are all "how recently was
        he active", heavily correlated, so weighting them 0.5/0.3/0.2 counted one
        piece of evidence three times and called it confidence.

        Worse, it inferred presence from message gaps while `receipts.py` was
        sitting there knowing whether HIS TELEGRAM CHAT IS THE FOREGROUND WINDOW
        ON HIS PC -- direct evidence, and accurate since the ward/idle fixes.
        That is the strongest term here and the reason for the rebuild.

        One number, decaying continuously, so it means the same thing wherever
        it is read."""
        c = self.config.rhythm
        now = self.clock.now_ts()
        best = 0.0
        # 1. his chat is open. Nothing else comes close to this.
        try:
            st = self.receipts.status() if self.receipts else None
        except Exception:
            st = None
        if st:
            if st.get("state") == "read" and st.get("read_ts"):
                mins = (now - float(st["read_ts"])) / 60.0
                best = max(best, c.presence_read * self._decay(mins, c.presence_read_half_min))
            elif st.get("active"):
                best = max(best, c.presence_active)
        # 2. he said something, and how long he took to say it
        msgs = self.store.recent_messages(c.turns_scanned)
        last_him = max([float(m["ts"]) for m in msgs if m["role"] == "user"] or [0])
        if last_him:
            best = max(best, c.presence_spoke * self._decay((now - last_him) / 60.0, c.presence_spoke_half_min))
        lat = self._last_latency(msgs)
        if lat is not None and lat <= c.quick_reply_minutes:
            best = max(best, c.presence_quick * self._decay((now - last_him) / 60.0, c.presence_spoke_half_min))
        # 3. and the weak prior: is this an hour he is ever about in
        return max(0.0, min(1.0, max(best, self.learned_now() * c.presence_prior)))

    @staticmethod
    def _decay(minutes, half):
        return 0.5 ** (max(0.0, minutes) / max(0.1, half))

    @staticmethod
    def _last_latency(msgs):
        """Minutes he took to answer her, most recently."""
        lat, pending = None, None
        for m in msgs:
            if m["role"] != "user":
                if pending is None:
                    pending = float(m["ts"])
            else:
                if pending is not None:
                    lat = (float(m["ts"]) - pending) / 60.0
                pending = None
        return lat

    def in_exchange(self):
        """Are they in a conversation, with hysteresis.

        Turn-taking is bimodal -- you are in one or you are not -- and the old
        single threshold at 0.45 with linear interpolation above it meant the
        fast regime only really bit near 1.0, and flapped in and out on a
        ninety-second lull. Entering costs more than staying."""
        c = self.config.rhythm
        p = self.presence()
        was = bool(self.store.get("in_exchange", False))
        now = p >= (c.stay_above if was else c.enter_above)
        if now != was:
            self.store.set("in_exchange", now)
            logger.log(f"[rhythm] {'in an exchange with him' if now else 'the exchange has gone quiet'} (presence {p:.2f})")
        return now

    def tempo(self):
        """Kept as the old name for anything still asking. Presence is the thing."""
        return self.presence()

    # ---------------- what it changes ----------------

    def noticing_seconds(self, access="free"):
        """How long before she even looks at it.

        The old model multiplied ONE range by her mood factor, which conflates
        two different things: noticing a message and composing an answer. A live
        exchange collapses the noticing to nothing -- the phone is in her hand --
        while composing still takes as long as what she is saying is long. Under
        one multiplier her careful paragraph arrived implausibly fast."""
        c = self.config.rhythm
        p = self.presence()
        lo, hi = (c.notice_live_seconds if self.in_exchange() else
                  (c.notice_glance_seconds if access == "glance" else c.notice_idle_seconds))
        # inside the band, presence still moves her: at 0.9 she is at the fast
        # end of it, at 0.5 the slow end
        k = max(0.0, min(1.0, p))
        return lo, lo + (hi - lo) * (1.0 - k)

    def notices(self, ja=False):
        """The subtle half: what she has picked up about how he is being.

        Not a number she is told -- a comparison she would actually make,
        against four months of him. This is the only place the learned shape
        reaches her as words."""
        t = lang.pick(ja)
        c = self.config.rhythm
        med = self.usual_latency()
        lat = self._last_latency(self.store.recent_messages(c.turns_scanned))
        if med and lat is not None:
            if lat <= med * c.notice_faster_ratio and lat < c.quick_reply_minutes:
                return t("he is answering much faster than he usually does at this hour "
                         f"(about {int(med)} minutes, normally).",
                         f"この時間の彼にしては返事がずいぶん早い（普段は{int(med)}分くらい）。")
            if lat >= med * c.notice_slower_ratio and lat > c.quick_reply_minutes:
                return t(f"he is slower than he usually is at this hour -- about {int(lat)} minutes "
                         f"where he is normally {int(med)}.",
                         f"この時間の彼にしては遅い。普段{int(med)}分のところが{int(lat)}分くらいかかっている。")
        u = self.learned_now()
        if u <= c.quiet_line_below and self.presence() >= c.enter_above:
            return t("he is up and talking at an hour he is almost never about in.",
                     "彼がほとんど起きていない時間に、起きていて喋っている。")
        return ""

    def reply_seconds(self):
        """Her read delay range, from the tempo. Not a floor imposed by a
        declared window: the faster this is going, the faster she is in it."""
        c = self.config.rhythm
        lo, hi = self.config.delivery.read_delay_free_seconds
        flo, fhi = c.fast_seconds
        t = self.tempo()
        if t < c.tempo_from:
            return (lo, hi)
        # linear between the normal range and the fast one
        k = (t - c.tempo_from) / max(0.01, 1.0 - c.tempo_from)
        return (lo + (flo - lo) * k, hi + (fhi - hi) * k)

    def delay_cap(self):
        """How much the mood factor may still slow her while it is live. Being
        tense does not make a person slower when the other one is right there."""
        c = self.config.rhythm
        t = self.tempo()
        if t < c.tempo_from:
            return None
        return c.delay_factor_cap + (1.0 - c.delay_factor_cap) * (1.0 - t)

    def silence_factor(self, ts=None):
        """How much an hour of silence counts, at this hour of his day.

        Read by `State.felt_hours`. Four months of record say he is not there
        at three in the morning, so three in the morning does not hurt."""
        c = self.config.rhythm
        if not c.enabled:
            return 1.0
        u = self.usual_now(ts)
        return c.quiet_hour_factor + (1.0 - c.quiet_hour_factor) * u

    # ---------------- what she is told ----------------

    def brief(self, ja=False):
        """One line, in the shape of something she would actually think.

        `ja` is her copy; the foresee role reads the same line about her in
        English."""
        def s_(en, jp):
            return jp if ja else en
        c = self.config.rhythm
        if not c.enabled:
            return ""
        t = self.tempo()
        if t >= c.tempo_live_line:
            med = self.usual_latency()
            return s_("he is right here and answering quickly, which he is not always. "
                      + (f"he usually takes about {int(med)} minutes at this hour." if med else ""),
                      "彼はいまそこにいて、返事が早い。いつもそうとは限らない。"
                      + (f"この時間だと普段は{int(med)}分くらいかかる。" if med else ""))
        # what he said comes first when he said it, because it is the thing she
        # would actually be thinking: he told her, and either he is here or he
        # is not, and both of those are about him rather than about the hour
        said = self.said_now()
        if said and abs(self.expectation()) >= c.said_line_from:
            if float(said.get("direction", 1)) > 0:
                return s_(f"he said he would be around about now — \"{said.get('quote', '')}\" — "
                          f"and he has not said anything yet.",
                          f"彼はこのくらいの時間にいると言っていた——「{said.get('quote', '')}」——"
                          f"のに、まだ何も来ていない。")
            return s_(f"he told you he would be out of reach about now — \"{said.get('quote', '')}\". "
                      f"he is not ignoring you.",
                      f"彼はこのくらいの時間は手が離せないと言っていた——「{said.get('quote', '')}」。"
                      f"無視されているのではない。")
        u = self.usual_now()
        if u <= c.quiet_line_below:
            return s_("this is not an hour he is usually about in.", "彼が普段いる時間帯ではない。")
        if u >= c.busy_line_above:
            med = self.usual_latency()
            return s_("this is usually one of his hours"
                      + (f" — he is normally about {int(med)} minutes at this time." if med else "."),
                      "ここは普段の彼の時間帯"
                      + (f"——この時間だと返事は普段{int(med)}分くらい。" if med else "。"))
        return ""

    def report(self):
        p = self.profile()
        out = [f"tempo now {self.tempo():.2f} (fast from {self.config.rhythm.tempo_from}), "
               f"this hour is {self.usual_now():.2f} usual for him, "
               f"silence counts x{self.silence_factor():.2f}"]
        r = self.reply_seconds()
        out.append(f"her read delay right now: {r[0]:.0f}-{r[1]:.0f}s "
                   f"(normally {self.config.delivery.read_delay_free_seconds[0]}-"
                   f"{self.config.delivery.read_delay_free_seconds[1]}s)")
        cap = self.delay_cap()
        out.append(f"mood may slow her by at most x{cap:.2f}" if cap else "mood factor unrestricted")
        out.append("")
        out.append("his day, as the record has it (his local hours):")
        for h in range(24):
            v = p[h]
            if v["weight"] < 0.02 and not v["samples"]:
                continue
            med = f"{v['median_minutes']:.0f}m" if v["median_minutes"] else "-"
            out.append(f"  {h:02d}:00  {'#' * int(round(v['weight'] * 24)):<24} {v['weight']:.2f}  "
                       f"answers in {med} ({v['samples']} sample(s))")
        line = self.brief()
        if line:
            out.append("")
            out.append(f"she would put it: {line}")
        return "\n".join(out)
