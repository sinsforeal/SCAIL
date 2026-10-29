import re

import logger
from sim import wiring
from sim import observer

# What his messages actually leave her feeling, judged rather than counted.
#
# The mechanical version could only add: any message he sent warmed her by a
# fixed amount before anything had read it. Arithmetic cannot tell "busy, talk
# later" from "busy, sorry, i'll message you tonight", and the difference
# between those two is most of how a person comes to feel about somebody.
#
# It runs once a day, when she goes under. Not per message -- she is
# answering a message then, not scoring it -- and not on a timer either:
# the day is the unit a person settles up in, and reading the whole of it
# at once is the only way an evening can be judged against the morning it
# followed. One call gives each of his messages the level of warmth it
# leaves her at, inside a band the code sets, with no cap on how many --
# context is the only bound.
#
# Affection is then those levels faded by age, blended with what her
# structural causes say (attachment, closeness, tension, resentment), so a
# quiet week still cools her with nothing to judge. A day too thin to be
# worth reading (under `min_messages`) is not read: it rolls into the next
# night, because the clock never moves past what was left unscored.


class Appraisal:
    WIRES = ('persona',)

    def __init__(self, config, llm, store, clock, state, sentiments=None, typesafe=None):
        self.config = config
        self.llm = llm
        self.store = store
        self.clock = clock
        self.state = state
        self.sentiments = sentiments
        # The hosted classifier (`typesafe.py`, `docs/system-one.md`): when her
        # config turns the `affection` use on, one `score` per marked message
        # gives the level of warmth it leaves her at. The `why` stays the
        # role's; the role is still called, and only the levels are overridden.
        self.typesafe = typesafe
        self.last_ts = store.get("appraisal_last_ts", 0)
        wiring.declare(self)

    def _levels_typesafe(self, user):
        """{message id: level 5-95} from Jev, or None. The anchors are code's;
        each `score` level is mapped onto the 5-95 scale the role uses."""
        ts = self.typesafe
        if ts is None or not ts.ready("affection"):
            return None
        use = ts.use("affection") or {}
        floor = float(use.get("threshold", 0.5))
        ids = []
        for line in user.splitlines():
            m = re.match(r"^\[(\d+)\]", line.strip())
            if m:
                ids.append(m.group(1))
        if not ids:
            return None
        anchors = ("5, coldest", "23", "41", "59", "77", "95, warmest")
        questions = {}
        for i in ids:
            questions["level_" + i] = {
                "type": "score",
                "instructions": "Message [%s]: where does she end up in warmth toward him after "
                                "reading it? 45 is her ordinary resting warmth; most messages land "
                                "between 40 and 55; use the ends only when something really "
                                "happened." % i,
                "criteria": list(anchors)}
        answers = ts.ask("affection", {"the exchange and how she is": user}, questions)
        if not answers:
            return None
        out = {}
        lowest = None
        for i in ids:
            v, conf = ts.score(answers, "level_" + i)
            if conf is None or conf < floor or not isinstance(v, (int, float)):
                return None
            out[int(i)] = round(5 + (float(v) / 5.0) * 90, 1)
            lowest = conf if lowest is None else min(lowest, conf)
        logger.log(f"[affection] typesafe: {len(out)} level(s), lowest conf {lowest:.2f}")
        return out

    # ---------------- what has been judged ----------------

    def rows(self):
        c = self.config.affection
        now = self.clock.now_ts()
        keep = [r for r in self.store.get("appraisal_levels", [])
                if now - float(r.get("ts", 0)) < c.keep_hours * 3600]
        return keep[-c.max_kept:]

    def _save(self, rows):
        self.store.set("appraisal_levels", rows[-self.config.affection.max_kept:])

    def level(self):
        """(how much of the target these levels own, what they say), or None.

        Faded by age, because how a message left her stops mattering: the
        weight is what makes a fortnight-old kindness count for less than
        last night's, without any of it being forgotten."""
        c = self.config.affection
        rows = self.rows()
        if not rows:
            return None
        now = self.clock.now_ts()
        num = den = 0.0
        for r in rows:
            age = max(0.0, (now - float(r.get("ts", 0))) / 3600.0)
            w = 0.5 ** (age / max(0.5, c.half_life_hours))
            num += w * float(r.get("level", 45))
            den += w
        if den <= 0:
            return None
        weight = min(c.max_weight, c.max_weight * den / max(0.1, c.full_weight_at))
        return weight, num / den

    # ---------------- the cycle ----------------

    def due(self, night_key=None):
        """Once, as she goes under, and only if the day had a conversation in
        it. `min_messages` counts the exchange rather than his half: his half
        of a day is a modest number of messages, so counting only his would make the
        floor the whole day. `min_his` is there so a night of her talking to
        herself is not read as him."""
        c = self.config.affection
        if not (c.enabled and c.review_enabled):
            return False, "off"
        if night_key and self.store.get("appraisal_night") == night_key:
            # keyed to the night, so a restart does not read the day twice
            return False, "already read tonight"
        fresh = self._unjudged()
        exchange = [m for m in self.store.recent_messages(c.window_messages)
                    if float(m.get("ts", 0)) > self.last_ts]
        if len(exchange) < c.min_messages:
            return False, f"only {len(exchange)} since the last read"
        if len(fresh) < c.min_his:
            return False, f"only {len(fresh)} of them his"
        return True, f"{len(exchange)} message(s) since the last read, {len(fresh)} of them his"

    def on_message_due(self):
        """The bench read (`affection.on_message`): shortly after a reply, not
        at night. Same read, own minimums, and a cooldown so a burst of lines
        is one call. The nightly `due()` is untouched."""
        c = self.config.affection
        if not (c.enabled and c.review_enabled and c.on_message):
            return False, "off"
        now = self.clock.now_ts()
        last = float(self.store.get("appraisal_msg_ts", 0) or 0)
        if last and now - last < c.on_message_cooldown_minutes * 60:
            return False, "cooldown"
        counts = self.store.get("appraisal_msg_counts", {}) or {}
        if int(counts.get(self.clock.date_str(), 0)) >= c.on_message_max_per_day:
            return False, "day cap"
        fresh = self._unjudged()
        exchange = [m for m in self.store.recent_messages(c.window_messages)
                    if float(m.get("ts", 0)) > self.last_ts]
        if len(exchange) < c.on_message_min_messages:
            return False, f"only {len(exchange)} since the last read"
        if len(fresh) < c.on_message_min_his:
            return False, f"only {len(fresh)} of them his"
        return True, f"{len(exchange)} message(s) since the last read, {len(fresh)} of them his"

    def on_message(self):
        """Read his fresh messages now if `on_message_due`, then let affection
        step once toward the target the new rows give it (the per-event step
        is capped, so without this the gauge waits for the next decay tick).
        Returns the number of messages read."""
        ok, why = self.on_message_due()
        if not ok:
            if why not in ("off", "cooldown"):
                logger.log(f"[affection] no read after the message: {why}")
            return 0
        c = self.config.affection
        day = self.clock.date_str()
        counts = {day: int((self.store.get("appraisal_msg_counts", {}) or {}).get(day, 0)) + 1}
        self.store.set("appraisal_msg_counts", counts)
        self.store.set("appraisal_msg_ts", self.clock.now_ts())
        logger.log(f"[affection] reading him after his message: {why}")
        n = self.run()
        if n:
            before = float(self.state.gauges.get("affection", 0))
            self.state._derive_affection(c.on_message_step_hours)
            self.state.save()
            logger.log(f"[affection] after the read: {before:.1f} -> "
                       f"{float(self.state.gauges.get('affection', 0)):.1f}")
        return n

    def _unjudged(self):
        """His messages since the last cycle. Hers go in for context but are
        never scored -- this is what he left her feeling, not what she did."""
        c = self.config.affection
        out = []
        for m in self.store.recent_messages(c.window_messages):
            if float(m.get("ts", 0)) <= self.last_ts:
                continue
            if m.get("role") == "user":
                out.append(m)
        return out

    def run(self, night_key=None):
        """The night's read: everything of his since the last one, with the
        exchange around it for context."""
        c = self.config.affection
        fresh = self._unjudged()
        if not fresh:
            return 0
        first = min(float(m["ts"]) for m in fresh)
        window = [m for m in self.store.recent_messages(c.window_messages)
                  if float(m.get("ts", 0)) >= first - c.context_seconds]
        n = self.score(fresh, window)
        if not n:
            # nothing came back readable: leave the clock where it is so
            # tomorrow night picks the same day up again
            return 0
        self.last_ts = self.clock.now_ts()
        self.store.set("appraisal_last_ts", self.last_ts)
        if night_key:
            self.store.set("appraisal_night", night_key)
        return n

    def score(self, fresh, window):
        """The call itself. Kept separate from the nightly read so the
        backfill tool can hand it a stretch of history without touching the
        clock that decides which day gets read next."""
        c = self.config.affection
        if not fresh:
            return 0
        ids = {int(m["id"]) for m in fresh}
        lines = []
        for m in window:
            who = "HIM" if m.get("role") == "user" else "her"
            mark = f"[{m['id']}] " if int(m["id"]) in ids else "      "
            lines.append(f"{mark}{self.clock.hm(m['ts'])} {who}: {str(m.get('text', ''))[:400]}")
        sen = ""
        if self.sentiments:
            try:
                key = self.state._him_key() or "him"
                sen = (f"what he is to her at the moment: attachment {self.sentiments.live(key, 'attachment'):.0f}, "
                       f"resentment {self.sentiments.live(key, 'resentment'):.0f}")
            except Exception:
                sen = ""
        # What she is like, as an observer wrote it. Never her character
        # sheet: this role scores him on her behalf and must not think it is
        # her (`sim/observer.py`, his call 2026-09-05).
        note = observer.block(self.config, self.llm, self.store)
        # What she has in front of her this minute: the same situation block and
        # the same carrying block the persona itself would be sent, built now
        # (`Persona.judge_view`). The sections this prompt names by name -- how
        # she is at the moment, the warmth she is sitting at -- stay below it.
        her = self.persona.judge_view() if self.persona else ""
        user = (
            (her + "\n\n" if her else "")
            + (note + "\n\n" if note else "")
            + f"TIME: {self.clock.both()}\n"
            f"HOW SHE IS: {self.state.mood_tags()}\n"
            f"WARMTH SHE IS SITTING AT: {self.state.gauges.get('affection', 45):.0f} "
            f"({c.neutral} is neither warmer nor colder than usual for her)\n"
            + (sen + "\n" if sen else "")
            + f"\nTHE EXCHANGE (only the marked [id] lines are his and need a level):\n"
            + "\n".join(lines)
        )
        system = self.config.role_system("affection")
        data, _ = self.llm.call_json("affection", [{"role": "system", "content": system},
                                                   {"role": "user", "content": user}])
        if not isinstance(data, dict):
            logger.log("[affection] the review came back unreadable")
            return 0
        # The classifier's per-message levels stand over the role's when they
        # answer above the use's floor; the `why` stays the role's, so the role
        # is still called and still supplies the ids it judged.
        jlevels = self._levels_typesafe(user)
        by_id = {int(m["id"]): m for m in fresh}
        rows = self.rows()
        n = 0
        for item in (data.get("levels") or [])[: c.max_per_cycle]:
            if not isinstance(item, dict):
                continue
            try:
                mid = int(item.get("id"))
                lvl = float(item.get("level"))
            except (TypeError, ValueError):
                continue
            if jlevels is not None and mid in jlevels:
                lvl = jlevels[mid]
            m = by_id.get(mid)
            if not m:
                continue
            # the band is the code's, not the model's: one message is a message,
            # not a verdict on the relationship
            lvl = max(c.level_min, min(c.level_max, lvl))
            rows.append({"ts": float(m["ts"]), "id": mid, "level": round(lvl, 1),
                         "why": str(item.get("why", ""))[:120],
                         "text": str(m.get("text", ""))[:80]})
            n += 1
        self._save(rows)
        if n:
            got = self.level()
            logger.log(f"[affection] read {n} of his message(s): "
                       + "; ".join(f"{r['level']:.0f} {r['why'][:44]}" for r in rows[-n:])
                       + (f" -> they say {got[1]:.0f} at weight {got[0]:.2f}" if got else ""))
        return n

    # ---------------- what it looks like ----------------

    def report(self):
        got = self.level()
        lines = ["how his messages have been landing (sim/appraisal.py):"]
        if not got:
            lines.append("  nothing judged yet; affection is running on its structural causes alone")
        else:
            w, lvl = got
            lines.append(f"  {len(self.rows())} message(s) in the window say {lvl:.0f}, "
                         f"owning {w * 100:.0f}% of the target")
        for r in self.rows()[-8:]:
            lines.append(f"  {self.clock.hm(r['ts'])} {r['level']:5.1f}  {r['why'][:60]}")
            lines.append(f"           \"{r['text'][:64]}\"")
        return "\n".join(lines)
