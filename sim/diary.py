import datetime
from world.clock import hm_to_minutes
from sim import chattext
from sim import wiring
import logger
from sim import sight
from sim import existence

# Her diary. Not a report to anyone: first person, for herself, the things
# she did not send and the day as it felt. It is not forced. A gauge,
# `unsaid`, fills with what the day left in her (events, things she typed
# and deleted, being read and ignored, what she saw on X) and empties when
# she writes. When it is high enough in a free evening block, with a
# probability that rises with it, she writes; the last entries sit in her
# prompt as what she wrote, so her own memory of herself exists alongside
# the compiled record about her.


class Diary:
    WIRES = ('social', 'zeitgeist',)
    def __init__(self, config, llm, store, clock, state, records=None, social=None):
        self.config = config
        self.llm = llm
        self.store = store
        self.clock = clock
        self.state = state
        self.records = records
        self.social = social
        # (date, reason) pairs already said once, so the log carries why she
        # did not write on an evening the window was open without repeating it
        # every tick. Nothing said it before, and two evenings of a character
        # never writing at all left no line to read.
        self._said = set()
        wiring.declare(self)

    def day_weight(self):
        """How much of a day she has behind her, as the count of things that
        happened worth writing about.

        The pressure gauge (`unsaid`) is the measure for a character who has
        somebody to say things to and does not: three of its four fillers are
        the relationship -- holding something back from him, a thing about him
        she cannot raise, being left on read -- and for a character with no
        chat with him the only one left is the handful of salient events that
        happen to be hanging on the current scene. Hers ran between 15 and 24
        against a gate of 50 for the whole of her record, so the window opened
        every evening and the gate could not.

        Her own day is the honest measure for her: what her record says
        happened, at the salience the state layer already treats as
        significant. Read from her own store, so it counts her own people and
        her own places and nothing of him."""
        try:
            date = self.date_for_now()
            today = self.clock.date_str()
            rows = list(self.store.events_for_date(date))
            if today != date:
                rows += list(self.store.events_for_date(today))
        except Exception:
            return 0
        floor = int(getattr(self.config.state, "salient_from", 3) or 3)
        return sum(1 for e in rows if int(e.get("salience", 1) or 1) >= floor)

    def entries(self, n=None):
        e = self.store.get("diary", [])
        return e[-n:] if n else e

    def date_for_now(self):
        """The day an entry written at this moment is ABOUT.

        Her diary is an evening, and the evening does not end where the date
        does: the window runs 20:30 to 01:30 and she is still on her phone in
        bed for the last hour of it. Keying the entry on the calendar date
        filed the small hours against a day that had not happened -- and it
        latched, because an entry written at 00:27 on the 24th marked the 24th
        done, which closed the 24th's own 20:30 window and left 00:00 on the
        25th as the only chance, from then on. Twelve of the first fifteen
        entries were written between 00:01 and 00:59, each handed the new
        day's empty event list; the one filed as 09-03 opens with the time
        twenty-five past midnight and is about the 2nd.

        The window's own start is the answer: everything inside it belongs to
        the date it opened on. Only when the window wraps midnight, so a diary
        configured to sit inside one day is untouched."""
        c = self.config.diary
        lo, hi = hm_to_minutes(c.hours_start), hm_to_minutes(c.hours_end)
        now = self.clock.now()
        if lo > hi and (now.hour * 60 + now.minute) <= hi:
            return (now.date() - datetime.timedelta(days=1)).isoformat()
        return self.clock.date_str()

    def wrote_tonight(self):
        """Has the evening she is in already been written? Not "is there an
        entry dated today", which is the question that latched."""
        d = self.date_for_now()
        return any(e["date"] == d for e in self.entries(5))

    def _refused(self, why):
        """Say once, for this evening, why she is not writing. The gate had no
        voice at all: two evenings of a character who has never written one
        left nothing in the log to read, and the answer was in a gauge nobody
        had thought to plot."""
        key = (self.date_for_now(), why.split(",")[0])
        if key not in self._said:
            self._said.add(key)
            logger.log(f"[diary] not tonight, {why}")
        return False, why

    def may_write(self, scene):
        c = self.config.diary
        if not c.enabled:
            return False, "off"
        if self.wrote_tonight():
            return False, f"already written for {self.date_for_now()}"
        if not scene or scene.get("phone_access") != "free":
            return False, "not alone"
        hm = self.clock.now().hour * 60 + self.clock.now().minute
        lo = hm_to_minutes(c.hours_start)
        hi = hm_to_minutes(c.hours_end)
        inside = lo <= hm <= hi if lo <= hi else (hm >= lo or hm <= hi)
        if not inside:
            return False, "hours"
        g = self.state.gauges
        u = g.get("unsaid", 0)
        # shame and the flat kind of sadness are the two she cannot say to
        # anybody, so they belong here even when the day left little unsaid --
        # the diary is the only place either of them has to go
        carried = max(g.get("shame", 0), g.get("sadness", 0))
        # ...and for a character with no chat with him, the day itself. Three
        # of the four things that fill `unsaid` are the relationship, so a
        # character who has not got one cannot reach a gate built on it: hers
        # never passed 24 against a threshold of 50, over two evenings with
        # the window open and eight to sixteen things happening in each of
        # them. What she has instead is her own day, and a diary is what a day
        # with nobody to tell is for.
        day = self.day_weight() if not existence.has_chat(self.config) else 0
        if u < c.min_unsaid and carried < c.min_carried and day < c.min_day_events:
            return self._refused(f"unsaid {int(u)}, nothing she is sitting on"
                                 + (f", {day} thing(s) happened today" if not existence.has_chat(self.config) else ""))
        import random
        p = (c.base_probability + max(0.0, u - c.min_unsaid) / 100.0 * c.unsaid_weight
             + max(0.0, carried - c.min_carried) / 100.0 * c.carried_weight
             + max(0, day - c.min_day_events) * c.day_weight)
        if random.random() > min(0.95, p):
            return False, "not tonight"
        return True, "ok"

    def write(self, scene, reason="she felt like it"):
        c = self.config.diary
        date = self.date_for_now()
        # The evening she is writing about, plus anything since midnight when
        # she is writing in the small hours: both are the same evening to her,
        # and the rows come back ordered by ts, so the two lists join in order.
        # `today` is the real calendar date and is used only where a record has
        # to say when a thing actually happened.
        today = self.clock.date_str()
        tail = today if today != date else None

        def _both(reader):
            return reader(date) + (reader(tail) if tail else [])

        events = _both(self.store.events_for_date)
        ev_txt = "\n".join(f"[{self.clock.hm(e['ts'])}] ({e['kind']}, s{e['salience']}) {e['text']}" for e in events[-25:]) or "(nothing much)"
        # What she and he said, and what she last saw of his machine: two
        # sections that belong to a character who has a chat with him and a
        # window on him. For one who has neither, the headings were still
        # going in with "(we did not talk today)" and "(she did not look at
        # the app today)" under them -- a man in her diary who is not in her
        # life, every night, in the one place that is supposed to be hers.
        him = ""
        if existence.has_chat(self.config):
            msgs = _both(self.store.messages_for_date)
            msg_txt = chattext.lines(msgs[-30:], self.clock, chars=200, labels=("him", "me")) or "(we did not talk today)"
            him += f"\n\nMESSAGES WITH HIM TODAY:\n{msg_txt}"
        if existence.sees_him(self.config):
            digests = _both(self.store.digests_for_date)
            dig = digests[-1]["text"] if digests else sight.w(self.config, "diary_none")
            him += f"\n\n{sight.w(self.config, 'diary_label')}{dig}"
        # A gist, not the prose. Pasting whole entries back made this a copy
        # loop: whatever voice it drifted into was the voice it then studied,
        # so the register could not recover however the prompt was worded. She
        # needs to know what she already covered, not how she phrased it.
        last = self.entries(3)
        last_txt = "\n".join(f"{e['date']}: {' '.join((e.get('text') or '').split())[:110]}..."
                             for e in last) or "(no earlier entries)"
        x_line = self.social.recent_line() if self.social else ""
        threads = self.records.threads_brief() if self.records else ""
        week = ""
        try:
            week = self.zeitgeist.brief(limit=5) if self.zeitgeist else ""
        except Exception:
            week = ""
        user = (
            f"DATE: {date} ({datetime.date.fromisoformat(date).strftime('%A')}), {self.clock.hm()} her time"
            + (" -- past midnight, so this is still that evening and not the new day's\n" if tail else ".\n")
            + f"WHERE SHE IS: {scene.get('location', '')}: {scene.get('activity', '')}\n"
            f"HOW SHE FEELS: {self.state.mood_tags()} (unsaid {int(self.state.gauges.get('unsaid', 0))}/100)\n"
            f"WHY NOW: {reason}\n\n"
            f"TODAY'S EVENTS:\n{ev_txt}" + him + "\n"
            + (f"{x_line}\n" if x_line else "") +
            f"\nTHREADS:\n{threads}\n\n"
            + (f"GOING ON AROUND HER THIS WEEK (what she has seen or heard):\n{week}\n\n" if week else "")
            + f"WHAT SHE ALREADY WROTE ABOUT ON RECENT NIGHTS (so tonight is not the same entry "
            f"again -- this is a record of what was covered, not an example of how to write; the "
            f"register rules above are the authority on that):\n{last_txt}"
        )
        system = self.config.role_system("diary")
        # her own hand is Japanese (his call, 2026-08-26); the gloss is for
        # the record and the weekly, never the thing itself
        data, raw = self.llm.call_json("diary", [{"role": "system", "content": system}, {"role": "user", "content": user}])
        ja = str((data or {}).get("ja", "") if isinstance(data, dict) else "").strip()
        text = str((data or {}).get("text", "") if isinstance(data, dict) else "").strip()
        if not ja and not text:
            return None
        ja, text = ja[: c.max_chars], text[: c.max_chars]
        entries = self.entries()
        from sim import voicecheck
        voicecheck.note(self.config, self.store, ja, who=self.config.character.name, role="diary", where="diary")
        entries.append({"date": date, "ts": self.clock.now_ts(), "ja": ja, "text": text or ja})
        self.store.set("diary", entries[-c.keep:])
        relief = c.relief
        # Writing it down is not saying it. If the thing pressing on her is
        # something she has not asked him, the diary should take the edge off
        # and no more -- at full relief it was a valve that let the pressure
        # out every night and made sure he never heard about it.
        try:
            if self.records and self.records.pressing_thread(self.state.gauges.get("unsaid", 0)):
                relief = c.relief_when_unasked
        except Exception:
            pass
        self.state.gauges["unsaid"] = max(0, self.state.gauges.get("unsaid", 0) - relief)
        # An evening she had and did not hand over. For a character he read to
        # the bottom before she spoke, this is the only thing that gives her
        # anything back to hold: it unsees nothing, it makes his share of her
        # smaller (sim/primitives.py:kept_private).
        prim = getattr(self.state, "primitives", None)
        if prim is not None:
            try:
                prim.kept_private(self.state._him_key() or "him", "an evening she wrote down and did not tell him")
            except Exception as e:
                logger.log(f"[primitives] the diary not counted: {type(e).__name__}: {e}")
        _st = getattr(self.state, "stress", None)
        if _st:
            _st.relieve("diary")
        self.state.save()
        # the ENTRY is filed against the evening it is about; the EVENT that
        # she sat and wrote it is filed against the day it actually happened
        # on, so a 00:27 entry does not land in a day compiled at 23:55
        self.store.add_event(self.clock.now_ts(), today, "diary", "she wrote in her diary for a while", 1)
        when = " (written after midnight, about the evening before)" if tail else ""
        logger.log(f"[diary] for {date}{when}: {(ja or text)[:120].replace(chr(10), ' / ')} | {text[:100].replace(chr(10), ' / ')} (unsaid -{relief})")
        return ja or text

    def prompt_text(self):
        c = self.config.diary
        last = self.entries(c.in_prompt)
        if not last:
            return ""
        # what she wrote, as she wrote it: the Japanese where there is one
        return "\n\n".join(f"{e['date']}:\n{e.get('ja') or e['text']}" for e in last)


