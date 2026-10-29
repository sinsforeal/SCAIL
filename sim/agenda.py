"""What is coming, joined from every store that holds a dated thing.

Her sense of the week was second-hand. The clock line at the head of her
situation block says the weekday and the time and nothing else, and what
was COMING lived in five stores that never met: the calendar's holidays
and the wards' events with their lookahead, which reached the director and
the morning outlook and never her reply; the promises she has made, with a
date and often an hour on them; what he said he would do, with a deadline
his side; the people the day's plan has taken out of it; and the lines the
day has settled. She could be asked "what are you up to this week" with
every one of those on file and nothing in front of her.

One reader over all of them, and two views of it. `items()` is the join:
dated rows, sorted, exact repeats dropped. `prompt_text()` is the short
block she reads. `panel()` is the operator's, in the ops payload, and
`report()` is what `/agenda` prints.

**Nothing here is a plan and nothing here writes.** Every row is something
another module already decided and already owns; this only puts them in
one order. A collaborator that is `None` because the program did not build
it contributes nothing, which is the whole guard -- the calendar loads no
data at all for a character with no world, so it needs none.

**The block she reads must change only at her midnight, or when one of
these things lands.** It sits in the system half of her prompt, which the
provider caches as a byte prefix (`persona/sections.py`), so a wording
that counts down -- "in two days" -- would rewrite the block on every
midnight for every row and, worse, invite a per-call reading. Every date
is written absolutely: the weekday, the day and the month. And the block
starts at TOMORROW, because today is the day's one truth
(`sim/ledger.py`) and is in front of her on every call already, in the
half of the prompt that is re-sent anyway; the two views for the operator
show today as well.

Two stores that hold nothing dated, and why they are not read here. Her
account's posting is an impulse held for at most
`posting.hold_max_minutes` and dropped when her date turns over
(`tomoe/posting.py`), so it has no future date to carry. Foresight
predicts whether he answers the message she just sent, in minutes
(`sim/foresight.py`); it has a horizon of an hour, it is replaced by the
next send, and a row of it in the system half would rewrite the block
several times an evening.

Config `agenda`: `enabled`, `days` (how far ahead), `max_items` (how many
lines the block may carry, nearest first) and `in_prompt`.
"""

import datetime

import logger
from sim import lang
from sim import wiring


# Her own weekday letters, for the date at the head of a line she reads.
_WEEKDAY_JA = "月火水木金土日"


class Agenda:
    """The coming days, joined. Built for every character."""

    WIRES = ('calendar', 'commitments', 'expectations', 'ledger',)

    def __init__(self, config, store, clock):
        self.config = config
        self.store = store
        self.clock = clock
        wiring.declare(self)

    # ---------------- the join ----------------

    def items(self, days=None):
        """[{date, hm, kind, text, source}] for today and the next `days`,
        sorted by date then time, exact repeats dropped.

        `kind` is the machine's own word for what the row is -- `event`,
        `holiday`, `promise`, `he_said`, `away`, `settled` -- and the
        wording she reads is picked from it at render time (`_head`), so the
        row itself stays neutral and the operator's views print the word.

        `text` is the record's own words -- an event's name, a promise's
        wording, the reason a person is out of the day -- left exactly as
        the store holds them, the way the ledger leaves a block's activity.
        The wording around them is the reader's."""
        days = int(self.config.agenda.days if days is None else days)
        today = self.clock.now().date()
        rows = []
        for name, fn in (("the calendar", self._calendar), ("her promises", self._promises),
                         ("what he said", self._he_said), ("the day's plan", self._away),
                         ("the day's plan", self._settled)):
            try:
                rows.extend(fn(today, days))
            except Exception as e:
                logger.log(f"[agenda] {name} not read: {type(e).__name__}: {e}")
        seen = set()
        out = []
        for r in sorted(rows, key=lambda x: (x["date"], x["hm"])):
            key = (r["date"], r["hm"], r["kind"], r["text"])
            if key in seen:
                continue
            seen.add(key)
            out.append(r)
        return out

    @staticmethod
    def _row(date, kind, text, source, hm=""):
        text = " ".join(str(text or "").split())
        if len(text) > 160:
            text = text[:160]
            # the ward's event lines end in the place in brackets; a cut that
            # lands inside one leaves an opening bracket and half a place name
            cut = text.rfind("[")
            if cut > 40 and "]" not in text[cut:]:
                text = text[:cut].rstrip()
            text += "..."
        return {"date": str(date), "hm": str(hm or "")[:5], "kind": kind, "text": text, "source": source}

    def _calendar(self, today, days):
        """The national holidays and what is on, hers and her wards'.

        No guard: a character with no world has an empty holiday table and
        an empty event file, so this returns nothing for her by the data
        rather than by a branch (`world/calendar.py`)."""
        out = []
        for i in range(days + 1):
            d = today + datetime.timedelta(days=i)
            h = self.calendar.holiday(d)
            if h:
                out.append(self._row(d.isoformat(), "holiday", h, "the calendar"))
        for e in self.calendar.events(today, lookahead_days=days):
            try:
                start = datetime.date.fromisoformat(str(e.get("start")))
            except (TypeError, ValueError):
                continue
            when = max(start, today)
            text = str(e.get("name") or "")
            if e.get("note"):
                text += ": " + str(e["note"])
            out.append(self._row(when.isoformat(), "event", text, "the calendar"))
        return out

    def _promises(self, today, days):
        """The promises still open, with the date they come due.

        A promise about a public event the calendar has nothing of is left
        out, the same rule and the same reader as the day's one truth
        (`Ledger.promise_unbacked`): six days of a festival that was always
        tomorrow is what that check exists to stop, and a week view is
        exactly where it would come back."""
        if not (self.commitments and self.config.commitments.enabled):
            return []
        last = (today + datetime.timedelta(days=days)).isoformat()
        out = []
        for r in self.commitments.open():
            d = str(r.get("date") or "")
            if not (today.isoformat() <= d <= last):
                continue
            if self.ledger and self.ledger.promise_unbacked(r):
                continue
            who = str(r.get("to_name") or "")
            what = str(r.get("what") or "")
            out.append(self._row(d, "promise", (f"{what} ({who})" if who else what),
                                 "her promises", hm=str(r.get("from_hm") or "")))
        return out

    def _he_said(self, today, days):
        """What he said he would do, and when he said he would be about,
        each with the deadline it is judged against (`sim/expectations.py`).
        His deadline is his local time; the date it lands on is hers,
        because the week she reads is hers."""
        if not (self.expectations and self.config.expect.enabled):
            return []
        first, last = today, today + datetime.timedelta(days=days)
        out = []
        for r in self.expectations.rows():
            if str(r.get("state")) != "open" or not r.get("due_ts"):
                continue
            try:
                due = self.clock.to_char(float(r["due_ts"]))
            except (TypeError, ValueError):
                continue
            if not (first <= due.date() <= last):
                continue
            out.append(self._row(due.date().isoformat(), "he_said", r.get("what", ""),
                                 "what he said", hm=due.strftime("%H:%M")))
        return out

    def _away(self, today, days):
        """Who the day's plan has taken out of the day, and why. The ledger
        is the one reader of this: for the character who keeps the world it
        is her own plan, and for a character who reads a world somebody else
        keeps it is the rows the owner wrote into the world file."""
        if not self.ledger:
            return []
        out = []
        for i in range(days + 1):
            d = (today + datetime.timedelta(days=i)).isoformat()
            for name, lo, hi, why in self.ledger.absent(d):
                text = f"{name} {lo}-{hi}"
                if why:
                    text += ", " + why
                out.append(self._row(d, "away", text, "the day's plan", hm=lo))
        return out

    def _settled(self, today, days):
        """The lines today has settled. Today alone: the plan settles the day
        being lived, and there is nothing settled about a day the planner has
        not reached.

        `to_world=False` because this is a view. For the character who keeps
        the world, reading the settled lines is also what copies them into
        the world file, and that copy belongs to the path that builds her
        prompt for today -- the line this printed at boot put them there
        before the day's own writers had run, and the reader's window on to
        them then held a different eight rows."""
        if not self.ledger:
            return []
        return [self._row(today.isoformat(), "settled", line, "the day's plan")
                for line in self.ledger.settled(today.isoformat(), to_world=False)]

    # ---------------- the block she reads ----------------

    def _when(self, date_str, hm, ja):
        """The date as she reads it, absolute. Never a countdown: this block
        rides in the cached half of her prompt, and a relative wording would
        rewrite every line of it."""
        try:
            d = datetime.date.fromisoformat(date_str)
        except (TypeError, ValueError):
            return date_str
        when = f"{d.month}月{d.day}日({_WEEKDAY_JA[d.weekday()]})" if ja else d.strftime("%a %d %b")
        return when + (f" {hm}" if hm else "")

    @staticmethod
    def _head(kind, t):
        return {"event": t("", ""),
                "holiday": t("national holiday: ", "祝日: "),
                "promise": t("you promised: ", "約束していること: "),
                "he_said": t("he said he would: ", "彼が言っていたこと: "),
                "away": t("not around: ", "いない人: "),
                "settled": t("settled: ", "決まったこと: ")}.get(kind, "")

    def prompt_text(self):
        """The short block in the system half of her prompt, or "".

        **From tomorrow on.** Today is already in front of her on every call,
        in full and in the half of the prompt that is re-sent anyway: where
        she is and who with, who is out of the day, what the day settled and
        what she promised for it are the day's one truth (`sim/ledger.py`),
        inside the situation block. Repeating today here would say it twice
        and, worse, put it in the CACHED half, where a settled line landing
        at four in the afternoon rewrites the style file and the whole
        prefix behind it. What was missing was never today; it was the rest
        of the week. So this block is the complement of the ledger, and its
        bytes move at her midnight and when something lands on a day ahead.

        Empty renders nothing at all -- no heading over an empty list --
        because a character with no world, no promises and nothing he said
        would otherwise carry a section saying she has nothing on."""
        rows = self.in_prompt_rows()
        if not rows:
            return ""
        ja = lang.reads_ja(self.config)
        t = lang.pick(ja)
        lines = [f"- {self._when(r['date'], r['hm'], ja)}: {self._head(r['kind'], t)}{r['text']}"
                 for r in rows]
        ex = self.config.character.existence
        if str(getattr(ex, "with_him", "chat") or "chat").lower() == "none":
            # no him: the dates and her own promises, and nothing he said
            head = t("## The coming days (what is already fixed: the dates and what you promised. "
                     "You know these already; none of it is a topic to raise)",
                     "## これからの数日（もう決まっていること。日付と、あなたがした約束。"
                     "すでに知っていることで、話題として持ち出すためのものではない）")
        else:
            head = t("## The coming days (what is already fixed: the dates, what you promised, what he said he would do. "
                     "You know these already; none of it is a topic to raise)",
                     "## これからの数日（もう決まっていること。日付、あなたがした約束、彼がすると言っていたこと。"
                     "すでに知っていることで、話題として持ち出すためのものではない）")
        return "\n\n" + head + "\n" + "\n".join(lines)

    # ---------------- the operator's views ----------------

    def panel(self, days=None):
        """The ops payload's rows: today and the days ahead, uncut."""
        c = self.config.agenda
        rows = self.items(days if days is not None else c.days)
        return {"enabled": bool(c.enabled), "in_prompt": bool(c.in_prompt),
                "days": int(c.days if days is None else days), "count": len(rows),
                "rows": rows, "in_prompt_max": int(c.max_items),
                "in_prompt_count": len(self.in_prompt_rows())}

    def in_prompt_rows(self):
        """The rows the block carries: tomorrow on, capped. One reader, so
        `/agenda` marks the same lines her prompt has."""
        c = self.config.agenda
        if not (c.enabled and c.in_prompt):
            return []
        first = (self.clock.now().date() + datetime.timedelta(days=1)).isoformat()
        return [r for r in self.items(c.days) if r["date"] >= first][:int(c.max_items)]

    def report(self, days=None):
        """`/agenda [days]`: every dated thing in the window, today included,
        with a mark against the ones her prompt carries."""
        c = self.config.agenda
        n = int(c.days if days is None else days)
        rows = self.items(n)
        if not rows:
            return f"nothing dated in the next {n} day(s)"
        carried = {(r["date"], r["hm"], r["kind"], r["text"]) for r in self.in_prompt_rows()}
        out = [f"{len(rows)} dated thing(s) over the next {n} day(s), today included. "
               f"* is a line her prompt carries (tomorrow on, at most {c.max_items}; today is the "
               f"ledger's and is in front of her already)"
               + ("" if (c.enabled and c.in_prompt) else " -- the block is OFF")]
        for r in rows:
            mark = "*" if (r["date"], r["hm"], r["kind"], r["text"]) in carried else " "
            out.append(f" {mark} {r['date']} {r['hm'] or '  :  '} {r['kind']:8s} {r['text']} [{r['source']}]")
        return "\n".join(out)

    def boot_line(self):
        """One line at boot naming what is on, so a week that is empty when
        it should not be is visible without asking for it."""
        c = self.config.agenda
        if not c.enabled:
            return "[agenda] off"
        rows = self.items(c.days)
        by = {}
        for r in rows:
            by[r["kind"]] = by.get(r["kind"], 0) + 1
        kinds = ", ".join(f"{k} {v}" for k, v in sorted(by.items())) or "nothing"
        carried = self.in_prompt_rows()
        tail = (f"; {len(carried)} in her prompt" + (f", first {carried[0]['date']} {carried[0]['text'][:60]}"
                                                     if carried else "")
                ) if c.in_prompt else "; not in her prompt"
        return f"[agenda] {len(rows)} dated thing(s) over {c.days} day(s): {kinds}{tail}"
