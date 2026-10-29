"""Whether she may reach out first at all, before anything asks whether she
wants to.

The impulse score answers "does she feel like texting him". It was the only
thing between her and a self-started message, and it answers a different
question from the one a person actually asks, which is "is now a moment when
somebody would send this". Three faults followed from that and this module is
all three of them in one place.

**She fired on his first touch.** For a character who is resident on his
machine, him coming back after six hours away is an event of the loop: the
sleep coasting ends, a director tick runs at once, and the impulse is asked
with eight hours of silence behind it and every gauge at the top of its range.
Once she was writing to him seconds after he touched the keyboard, with a score far over the threshold. That is not a girl
noticing he is up; it is a doorbell. His return is now a *reason she might*
write, with odds that rise with how long he was gone and how much she is
holding, and a delay of minutes drawn from a range, so that a return often starts with him writing first.

**She reached again into her own silence.** Nothing counted what her last
self-started message had got back. `Impulse.unanswered_streak` capped the run
at two, and between the first and the second there was nothing but the ordinary
cooldown -- ninety minutes, the same as after a conversation. So the bar for
reaching out a second time into no answer was the same as the bar for the
first. It now rises with each unanswered message, minutes then hours, with a
cap on how many of those a day may hold; and a message he has OPENED and left
weighs heavier than one he has not looked at, because the first is an answer
and the second may only be a man away from his desk.

**Nothing was quiet at his night.** Her own sleep is his (`resident/sight.py`),
but a night he spends at the machine is a night she may talk into, and the
small hours of his day were worth no more than the middle of it.

Two ways through: a gauge at its end (`sim/discharge.py`), and the two stances
that enter without waiting -- having just been frightened of him, and having
just been put outside (`sim/stances.py`). Both are logged as overrides.

Everything is in the save (`initiative_*`), so a restart does not hand her a
clean sheet: the backoff is read off the record of what she actually sent, and
the pending return and the day's count are keys.
"""
import random

import logger
from world.clock import in_window
from sim.stances import URGENT


class Initiative:
    def __init__(self, config, store, clock):
        self.config = config
        self.store = store
        self.clock = clock
        self._last_log = ""

    @property
    def c(self):
        return self.config.impulse

    # ---------------- his coming back ----------------

    def observe_away(self, away_seconds, state=None):
        """How long he has been away from the machine, told by whoever can see
        it: a program whose character is inside the machine calls this every
        pass. Nobody calls it for a character who cannot see him that way, and
        then there is no return rule for her at all.

        The transition from away to here is the only thing this reads. It rolls
        once, and either books a delay or holds her for a while, so that his
        touch itself is never the thing that sends a message."""
        c = self.c
        now = self.clock.now_ts()
        limit = float(c.return_away_minutes) * 60.0
        away = max(0.0, float(away_seconds or 0.0))
        since = float(self.store.get("initiative_away_since", 0) or 0)
        if away >= limit:
            if not since:
                # his absence began when the machine went quiet, not now
                self.store.set("initiative_away_since", now - away)
            return
        if not since:
            return
        self.store.set("initiative_away_since", 0)
        gone_h = max(0.0, (now - since) / 3600.0)
        # he came back by writing to her: he opened it, there is nothing for
        # her to decide about opening it
        last_his = self.store.last_message("user")
        if last_his and float(last_his.get("ts", 0) or 0) >= since:
            logger.log(f"[impulse] his return after {gone_h:.1f}h: he wrote first, nothing to roll")
            return
        unsaid = 0.0
        share = 0.0
        if state is not None:
            try:
                unsaid = float(state.gauges.get("unsaid", 0) or 0)
                share = max(0.0, min(1.0, state.over_rest("unsaid") / 60.0))
            except Exception:
                share = 0.0
        p = (float(c.return_p_base)
             + min(gone_h, float(c.return_p_hours_cap)) * float(c.return_p_per_hour)
             + share * float(c.return_p_unsaid))
        p = max(0.0, min(float(c.return_p_max), p))
        head = f"[impulse] his return: p={p:.2f} (gone {gone_h:.0f}h, unsaid {unsaid:.0f})"
        if random.random() < p:
            lo, hi = [float(x) for x in c.return_delay_minutes]
            delay = random.uniform(min(lo, hi), max(lo, hi))
            self.store.set("initiative_return", {"due": now + delay * 60.0, "p": round(p, 3),
                                                 "gone_h": round(gone_h, 2)})
            self.store.set("initiative_hold_until", now + delay * 60.0)
            logger.log(f"{head} -> in {delay:.0f} min")
        else:
            # kept with no due time: the odds she was given stay readable in
            # `/impulse` and in the line that holds her, which is the whole
            # point of rolling in code rather than in a model
            self.store.set("initiative_return", {"due": 0, "p": round(p, 3), "gone_h": round(gone_h, 2)})
            self.store.set("initiative_hold_until", now + float(c.return_hold_minutes) * 60.0)
            logger.log(f"{head} -> not this time")

    # ---------------- the gate ----------------

    def urgent(self):
        """A stance that entered without waiting is a state in which a person
        does speak out of turn. Read off the row the last generation settled;
        deciding one here would enter a stance nothing is about to use."""
        try:
            return str((self.store.get("stance", {}) or {}).get("key") or "") in URGENT
        except Exception:
            return False

    def _last_self_started(self):
        for m in reversed(self.store.recent_messages(40)):
            if m["role"] == "assistant" and m["self_started"]:
                return float(m["ts"])
        return 0.0

    def _unanswered_today(self):
        return int((self.store.get("initiative_unanswered_counts", {}) or {}).get(self.clock.date_str(), 0))

    def hold_reason(self, streak=0, read_state="", urgent=False):
        """"" when she may reach out first, else why not. Never asks whether
        she wants to: that is the impulse's question and it is asked after
        this one.

        A gauge at its end and a stance that entered without waiting go
        through a closed gate, and the reason they went through is worth as
        much on the record as the reason she was held."""
        why = self._closed(streak, read_state)
        if not why:
            return ""
        if urgent or self.urgent():
            self.override(f"{'a discharge' if urgent else 'an urgent stance'} over '{why}'")
            return ""
        return self._say(why)

    def peek(self, streak=0, read_state=""):
        """What `hold_reason` would say, with nothing logged and nothing
        overridden: for a prompt that tells her where the gate stands."""
        return self._closed(streak, read_state)

    def last_self_started(self):
        return self._last_self_started()

    def _closed(self, streak, read_state):
        c = self.c
        now = self.clock.now_ts()
        hold = float(self.store.get("initiative_hold_until", 0) or 0)
        if now < hold:
            ret = self.store.get("initiative_return", None) or {}
            mins = int((hold - now) / 60.0) + 1
            if ret.get("due"):
                return f"his return: she is giving it {mins} more min"
            return (f"his return, gone {float(ret.get('gone_h', 0)):.0f}h, rolled p="
                    f"{float(ret.get('p', 0)):.2f} and not taken; quiet for {mins} min")
        if in_window(self.clock.user_now(), c.quiet_start_his, c.quiet_end_his):
            return f"his small hours ({c.quiet_start_his}-{c.quiet_end_his} where he is)"
        if streak >= 1:
            if self._unanswered_today() >= int(c.max_unanswered_per_day):
                return f"{self._unanswered_today()} self-starts today already went unanswered"
            steps = [float(x) for x in c.backoff_minutes]
            step = steps[min(streak, len(steps) - 1)]
            # he opened it and said nothing, which is an answer; an unopened
            # one may only be a man away from his desk
            step *= float(c.backoff_read_factor if str(read_state) == "read" else c.backoff_unseen_factor)
            due = self._last_self_started() + step * 60.0
            if now < due:
                return f"{streak} unanswered, next self-start not before {self.clock.hm(due)}"
        return ""

    def _say(self, why):
        line = f"[impulse] held: {why}"
        if line != self._last_log:
            logger.log(line)
            self._last_log = line
        return why

    def override(self, why):
        """What went through a gate that was shut, and what the gate had said.
        It writes nothing: a message that actually goes clears the hold in
        `note_sent`, and one that does not should leave the hold where it is."""
        logger.log(f"[impulse] override: {why}")

    # ---------------- the record ----------------

    def note_sent(self, streak=0):
        """A self-started message has actually gone. The backoff itself is read
        off the record, so the only thing to write is the day's count of times
        she reached into a silence of her own making."""
        self.store.set("initiative_hold_until", 0)
        self.store.set("initiative_return", None)
        if streak >= 1:
            self.store.bump_today("initiative_unanswered_counts", self.clock.date_str())

    def report(self):
        c = self.c
        now = self.clock.now_ts()
        hold = float(self.store.get("initiative_hold_until", 0) or 0)
        ret = self.store.get("initiative_return", None) or {}
        since = float(self.store.get("initiative_away_since", 0) or 0)
        out = ["reaching out first: the gate before the score",
               f"  his return: p = {c.return_p_base} + {c.return_p_per_hour}/h (to {c.return_p_hours_cap}h)"
               f" + {c.return_p_unsaid} x how far unsaid is over rest, capped {c.return_p_max};"
               f" away counts from {c.return_away_minutes} min",
               f"  taken -> she writes in {c.return_delay_minutes[0]}-{c.return_delay_minutes[1]} min;"
               f" not taken -> quiet {c.return_hold_minutes} min",
               f"  unanswered backoff (min): {list(c.backoff_minutes)}, x{c.backoff_read_factor} if he read it,"
               f" x{c.backoff_unseen_factor} if he has not opened it; cap {c.max_unanswered_per_day}/day",
               f"  quiet where he is: {c.quiet_start_his}-{c.quiet_end_his}",
               f"  through it anyway: a discharge, and the stances {', '.join(URGENT)}",
               f"  he has been away since: {self.clock.stamp(since) if since else '(he is about)'}",
               f"  unanswered self-starts today: {self._unanswered_today()} of {c.max_unanswered_per_day}",
               f"  last self-started: {self.clock.stamp(self._last_self_started()) if self._last_self_started() else '(none on record)'}"]
        if now < hold:
            out.append(f"  held for another {int((hold - now) / 60.0) + 1} min"
                       + (f" (his return, taken at p={ret.get('p')})" if ret.get("due") else " (his return, not taken)"))
        else:
            out.append("  nothing is holding her right now")
        if self.urgent():
            out.append("  an urgent stance is live: the gate is open")
        return "\n".join(out)
