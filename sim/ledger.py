"""One truth about the day, read by everyone who writes it.

The 08-29 compile put her in her mother's coral yukata all afternoon and had
her tell him "navy with white flowers" at night; walked her home from the
festival with a Rena the cast had grounded that morning; and settled "attend
the festival" KEPT, 120 minutes late, on that same phantom. Three writers of
"what is happening" -- the schedule, the cast's lives, her own claims -- and
none of them read the others. `settled` and `absent` closed two edges; this
is the table they were the first two columns of.

Nothing here asks a model. The ledger is composed from what code already
owns -- the schedule (as corrected by the plan's `absent`), the plan's
`settled`, what she is wearing (from the block, or a line his `/ledger`
command pins for the day), what she has bought, the promises still open --
and rendered as one block that the director, both sides of every exchange,
her own reply and the compile all receive. The point is not that any one of
them lacked the facts; it is that each had a different subset.

kv `ledger_wearing` {date, text}: a pinned line for the day, set by hand.
"""

import re
from sim import lang
from sim import wiring

import logger
from sim import roster
from sim import schedule as sched
# what the schedule writes in `with` that is not a person on her roster. It
# is defined where the schedule is written, so the gate that keeps a stranger
# out of a block and the audit that reports one use the same list.
from sim.schedule import NOT_PEOPLE


def _short(activity, chars=70):
    """A later block's activity, short enough to list a whole day of them.

    Cut at a space so a word is never halved. Only ever applied to a block she
    has not reached: what she DID is the plan's wording in full, and this is a
    glance down a page of her own schedule book."""
    s = " ".join(str(activity or "").split())
    if len(s) <= chars:
        return s
    cut = s[:chars]
    return (cut[:cut.rfind(" ")] if " " in cut else cut) + "..."


class Ledger:
    WIRES = ('cast', 'situation', 'world_shared',)
    def __init__(self, config, store, clock, cast=None, commitments=None, money=None, situation=None, calendar=None):
        self.config = config
        self.store = store
        self.clock = clock
        self.cast = cast
        self.commitments = commitments
        self.money = money
        self.situation = situation
        self.calendar = calendar
        wiring.declare(self)

    # ---------------- the columns ----------------
    def plan(self, date_str=None):
        """The plan's own facts for the day: `settled` and `absent`."""
        date_str = date_str or self.clock.date_str()
        for key in ("cast_beats", "cast_beats_prev"):
            rec = self.store.get(key, {}) or {}
            if rec.get("date") == date_str:
                return rec
        return {}

    # ---------------- a world somebody else keeps ----------------
    def _reads_world(self):
        """She is in a world she does not own, and the file has rows.

        The day's absences and the day's settled lines are both written by
        the planner, and a character who does not keep the world runs no
        planner: her own `cast_beats` is empty forever and every line below
        would be blank. So they come from the world file instead, which the
        owner wrote as she fixed the day (`world/shared.py`,
        docs/shared-world.md). Never both: the owner reads her own save and
        nothing here changes for her."""
        w = self.world_shared
        return bool(w and w.enabled and not w.owner and getattr(self.config, "world_reader", False))

    # what the day's plan writes into the world file for a person it removed
    # from the day, which is how an absence is told apart from a fixture
    ABSENT_SOURCE = "the day's absences"

    def absent(self, date_str=None):
        """[(record name, from_hm, to_hm, why)] for the day."""
        out = []
        if self._reads_world():
            # the world's people, out of the world file; her own people's
            # absences follow, out of her own plan
            date_str = date_str or self.clock.date_str()
            for r in (self.world_shared.whereabouts(date_str) or []):
                if str(r.get("source") or "") != self.ABSENT_SOURCE:
                    continue
                # not her own absence, read back off somebody else's plan. The
                # owner's process plans a day for her row too, because the
                # people who have not been promoted still reach for her through
                # it, so the world file says where SHE is -- and her own day's
                # one truth repeated it about herself in the third person
                # ("she is at her grandmother's 16:00-22:00").
                if roster.is_self(self.config, str(r.get("person") or "")):
                    continue
                out.append((roster.record_name(self.config, str(r.get("person") or "")),
                            str(r.get("from_hm") or "00:00")[:5], str(r.get("to_hm") or "24:00")[:5],
                            str(r.get("place") or "")[:80]))
        hers = self._own_windows(date_str)
        for a in (self.plan(date_str).get("absent") or []):
            if not isinstance(a, dict) or not a.get("who"):
                continue
            nm = roster.record_name(self.config, str(a["who"]))
            lo = str(a.get("from") or "00:00")[:5]
            hi = str(a.get("to") or "24:00")[:5]
            # a character who runs her own process says where she is. An
            # absence this plan wrote over a window she has written for
            # herself is a draw of her week, and hers outranks it
            # (docs/shared-world.md §2) -- the same preference the world
            # file's own rows are read under.
            if any(lo < b and a0 < hi for a0, b in hers.get(nm, ())):
                continue
            out.append((nm, lo, hi, str(a.get("why") or "")[:80]))
        return out

    def _own_windows(self, date_str=None):
        """{record name: [(from, to)]} of what a character in this world has
        written about herself today. Empty in a world nobody but the owner
        writes into, so a roster of people who do not run themselves reads
        exactly as it did."""
        w = self.world_shared
        if not (w and w.enabled):
            return {}
        out = {}
        try:
            rows = w.their_own_whereabouts(date_str or self.clock.date_str()) or []
        except Exception as e:
            logger.log(f"[ledger] what a character wrote about herself was not read: {type(e).__name__}: {e}")
            return {}
        for r in rows:
            nm = roster.record_name(self.config, str(r.get("person") or ""))
            out.setdefault(nm, []).append((str(r.get("from_hm") or "00:00")[:5],
                                           str(r.get("to_hm") or "24:00")[:5]))
        return out

    def is_absent(self, who, hm=None, date_str=None):
        """Is this person, at this hour of the day, somebody the plan removed?"""
        hm = hm or self.clock.hm()
        for nm, lo, hi, _why in self.absent(date_str):
            if roster.same(self.config, nm, who) and lo <= hm < hi:
                return True
        return False

    def settled(self, date_str=None, to_world=True):
        """The lines the day has settled.

        For the character who KEEPS the world, reading them is also what
        copies them into the world file, so another process in the same
        world plans against the same day -- which is right on the path that
        builds a prompt for the day being lived, and wrong for a view that
        is only looking. `to_world=False` is that view (`sim/agenda.py`):
        the agenda's line at boot used to put the plan's settled lines into
        the file before the day's own writers had run, and the reader's
        window on to them then held a different eight rows."""
        date_str = date_str or self.clock.date_str()
        out = []
        if self._reads_world():
            # the owner already refused a line her calendar could not back
            # before she wrote it, so a reader takes the rows as they stand;
            # what her own plan settled about her own people follows
            out = [self.spoken(s) for s in self.world_shared.settled_lines(date_str, limit=8)]
            # the world's own rows are the owner's and are never written back;
            # what HER OWN plan settled is hers to write, under her own
            # planner's name (the partition, docs/shared-world.md §2)
            to_world = to_world and bool(self.world_shared.writes_own())
        for x in (self.plan(date_str).get("settled") or []):
            s = str(x)[:160]
            if not s.strip():
                continue
            why = self.outing_unbacked(s, date_str)
            if why:
                self._refused(date_str, s, why)
                continue
            out.append(self.spoken(s))
            if to_world:
                self._settled_to_world(date_str, s)
        return out[:8]

    # ---------------- a plan the world does not hold ----------------
    _DATE = re.compile(r"(20\d\d-\d\d-\d\d)")
    # What a plan for a public event names: the calendar entry it means, its
    # date and its title, written into the line itself so every reader of the
    # line -- the speakers, her reply, the compile, the next day's planner --
    # carries the binding with it and no second field can be forgotten.
    EVENT = re.compile(r"\[calendar: (20\d\d-\d\d-\d\d) ([^\]]{1,90})\]")

    @classmethod
    def spoken(cls, text):
        """The line with the binding written out, for a prompt that is asked
        for words. The marker is the record's own shorthand and a model given
        a bracket copies brackets; what a speaker needs is the fact that the
        thing is really on, and its name."""
        return cls.EVENT.sub(lambda m: "(really on: %s, %s)" % (m.group(2).strip(), m.group(1)),
                             str(text or ""))

    @staticmethod
    def event_mark(date_str, title):
        """The binding as it is written into a line."""
        t = " ".join(str(title or "").split()).replace("]", "）")[:90]
        return "[calendar: %s %s]" % (date_str, t) if (date_str and t) else ""

    def event_ok(self, mark):
        """Is this binding still a thing the calendar has: `"<date> <title>"`
        or the whole `[calendar: ...]` marker. No calendar of her own means
        nothing to check against and nothing refused."""
        s = str(mark or "").strip()
        if not s or not self.calendar:
            return True
        m = self.EVENT.search(s) or re.match(r"^(20\d\d-\d\d-\d\d)[ :]+(.+)$", s)
        if not m:
            return False
        import datetime as _dt
        try:
            d = _dt.date.fromisoformat(m.group(1))
        except (TypeError, ValueError):
            return False
        return self.calendar.entry(d, m.group(2)) is not None

    def event_for(self, text, date_str):
        """The calendar entry a line about a public event means, as
        `"<date> <title>"`, or "". The word list says the line is about one;
        the calendar says which. Used where a promise binds."""
        words = list(getattr(self.config.world, "outing_words", None) or ())
        if not words or not self.calendar or not date_str:
            return ""
        low = str(text or "").lower()
        if not any(w.lower() in low for w in words):
            return ""
        import datetime as _dt
        try:
            d = _dt.date.fromisoformat(date_str)
        except (TypeError, ValueError):
            return ""
        e = self.calendar.outing_on(d, words)
        return ("%s %s" % (date_str, e["name"])) if e else ""

    def outing_unbacked(self, text, date_str=None):
        """Why a line that promises a public event is not backed by the
        calendar, or "".

        She went to a festival on 2026-08-29: the calendar had two that day
        and the scenes put her at the takoyaki stand outside Otsuka station
        with her brother at 19:04. The plan's `settled` list is carried into
        the next day's planning, where "tomorrow" means a different day, and
        nothing between the two ever asked the calendar whether there WAS one.
        So the festival was tomorrow on 20 and 23 August and again on 2, 3 and
        4 September, six days of everyone arranging a yukata for a day that
        never came, and five days of the record then writing "said they would
        go to the festival tomorrow and did not".

        A dated claim about a public event is now checked against the one
        place that knows what is on. A line with no such word in it, or with
        no date to check, is not this rule's business and passes in silence --
        this refuses a promise the world cannot keep, not a plan.

        The primary truth is the binding, not the word. A plan for an outing
        names the calendar entry it means (`[calendar: <date> <title>]`,
        written by the planner and checked when it is stored), and a line
        that carries one is judged on that alone: "meet dad at the station
        tomorrow (2026-09-05)" was the phantom festival with the word taken
        out, and no list of words can see it. The word list stays as the
        second net, for free text nobody bound to anything -- her own
        message, a friend's line, the judge's sentence about a promise.
        """
        marks = self.EVENT.findall(str(text or ""))
        if marks:
            for d, title in marks:
                if not self.event_ok("%s %s" % (d, title)):
                    return "the calendar has no %s on %s" % (str(title).strip()[:60], d)
            return ""
        words = list(getattr(self.config.world, "outing_words", None) or ())
        if not words or not self.calendar:
            return ""
        s = str(text or "")
        low = s.lower()
        if not any(w.lower() in low for w in words):
            return ""
        days = self._DATE.findall(s) or ([date_str] if date_str else [])
        if not days:
            return ""
        import datetime as _dt
        for d in days:
            try:
                dd = _dt.date.fromisoformat(d)
            except (TypeError, ValueError):
                return ""
            for e in self.calendar.events(dd):
                blob = (str(e.get("name", "")) + " " + str(e.get("note", ""))).lower()
                if any(w.lower() in blob for w in words):
                    return ""
        return ("nothing on the calendar for %s is one" % ", ".join(sorted(set(days))))

    def promise_unbacked(self, r):
        """Why a promise row is about something that is not happening, or "".
        A row bound to a calendar entry is judged on the entry -- an event
        pulled from the calendar after she agreed to go leaves the promise
        with nothing to keep -- and an unbound one on the word list."""
        ev = str((r or {}).get("event") or "").strip()
        if ev and not self.event_ok(ev):
            return "the calendar no longer has %s" % ev[:70]
        return self.outing_unbacked((r or {}).get("what", ""), (r or {}).get("date"))

    _refused_seen = None
    _world_said = None

    def _settled_to_world(self, date_str, line):
        """A line the day has settled, into the world file (`world/shared.py`)
        the moment it is accepted, so another process in the same world plans
        against the same day. Once per line per day: `settled` is read on
        every prompt build, and the copy would otherwise be rewritten a
        hundred times an hour."""
        w = self.world_shared
        # the owner writes the day's lines; a character who only lives in this
        # world writes the ones her own plan settled, under her own source
        if not (w and w.enabled) or not (w.owner or w.writes_own()):
            return
        if self._world_said is None:
            self._world_said = set()
        k = (date_str, line[:60])
        if k in self._world_said:
            return
        self._world_said.add(k)
        w.put_settled(date_str, line, source=("the plan" if w.owner else w.OWN_PLAN))

    def _refused(self, date_str, line, why):
        """Said once a day per line: `settled` is read on every prompt build."""
        if self._refused_seen is None:
            self._refused_seen = set()
        k = (date_str, line[:60])
        if k in self._refused_seen:
            return
        self._refused_seen.add(k)
        logger.log(f"[ledger] a settled line the calendar does not have, dropped: {line[:90]} -- {why}")

    def where(self, when=None, schedule=None):
        """The block she is in: (block, with-list) -- names resolved to the record."""
        when = when or self.clock.now()
        s = schedule or self.store.get_schedule(when.date().isoformat())
        if not s or not s.get("blocks"):
            return None, []
        blk = sched.block_at(s["blocks"], when)
        return blk, self.people_in(blk)

    def people_in(self, blk):
        w = str((blk or {}).get("with") or "")
        names = [x.strip() for x in w.replace("、", ",").replace(" and ", ",").split(",") if x.strip()]
        return [roster.record_name(self.config, n) if roster.role_of(self.config, n) else n for n in names]

    def wearing(self, blk=None, scene=None, date_str=None):
        """A line pinned for the day wins; otherwise what the block implies."""
        date_str = date_str or self.clock.date_str()
        pin = self.store.get("ledger_wearing", {}) or {}
        if pin.get("date") == date_str and pin.get("text"):
            return str(pin["text"])[:120]
        # Only ask a module that is switched on. With the place graph off,
        # `_outfit` matched no keyword against a calendar holding no data and
        # returned its defaults, so the day's one truth carried
        # "wearing: casual; carrying nothing much" every day forever -- a
        # sentence nobody wrote about a character nobody dressed.
        if self.situation and blk is not None and getattr(self.config.situation, "enabled", False):
            try:
                o = self.situation._outfit(blk, scene or {})
                return f"{o['wear']}; carrying {o['carry']}"
            except Exception:
                pass
        return ""

    def pin_wearing(self, text):
        self.store.set("ledger_wearing", {"date": self.clock.date_str(), "text": str(text or "")[:120]})

    # ---------------- what she ate ----------------
    _MEAL_WORDS = ("breakfast", "lunch", "dinner", "snack", "eat", "meal", "bento", "朝食", "昼食", "夕食", "おやつ", "ご飯", "ごはん", "弁当", "食")

    def meals(self, date_str=None):
        """The day's meals, pinned as they happen: [{hm, meal, text}]. A
        photo she sent of her lunch, a scene that has her eating a named
        thing -- one truth for what she ate, so the director, her turns and
        the compile do not each invent a different one."""
        date_str = date_str or self.clock.date_str()
        rows = self.store.get("ledger_meals", {}) or {}
        return list(rows.get(date_str, []) or [])

    def pin_meal(self, meal, text, hm=None):
        date_str = self.clock.date_str()
        rows = self.store.get("ledger_meals", {}) or {}
        day = list(rows.get(date_str, []) or [])
        text = " ".join(str(text or "").split())[:140]
        if not text:
            return
        # one line per meal a day: a second photo of the same lunch is the same lunch
        day = [m for m in day if m.get("meal") != meal] + [{"hm": hm or self.clock.hm(), "meal": str(meal or "")[:12], "text": text}]
        rows[date_str] = day[-6:]
        self.store.set("ledger_meals", {k: v for k, v in rows.items() if k >= date_str})
        logger.log(f"[ledger] {meal or 'meal'} pinned: {text[:80]}")

    def meal_line(self, date_str=None):
        ms = self.meals(date_str)
        if not ms:
            return ""
        return "; ".join(f"{m['meal']} ({m['hm']}): {m['text']}" for m in ms)

    # ---------------- the block ----------------
    def text(self, scene=None, when=None, schedule=None, for_whom="her", ja=False):
        """The ledger as prose lines. `for_whom` 'her' includes her money and
        promises; 'them' (a friend's turn) leaves those out -- they are not
        things a friend can see. `ja` is the wording she is addressed in; the
        block's activity and the settled facts are the plan's own words and
        are left exactly as the record holds them."""
        t = lang.pick(ja)
        when = when or self.clock.now()
        date_str = when.date().isoformat()
        lines = []
        blk, people = self.where(when, schedule)
        if blk:
            who = ", ".join(people) if people else t("alone", "ひとり")
            lines.append(f"- {blk['start']}-{blk['end']}: {blk.get('activity', '')} @ {blk.get('location', '')}, "
                         + t(f"with {who}", f"一緒にいるのは: {who}"))
        # What is still to come today, with the times on it. The ledger has
        # always shown the block she is in and nothing after it, so a question
        # about her evening had no fact behind it and was answered from
        # whatever she last said about it -- which is how a recording her own
        # plan puts at 20:30 was told to him as 午前, the morning, and then
        # repeated for twelve hours because her own claim was the newest thing
        # in the record. `situation_block.ledger_rest_of_day` is how many later
        # blocks are named; 0 is the ledger as every reader has always had it.
        rest = int(getattr(self.config.situation_block, "ledger_rest_of_day", 0) or 0)
        if rest > 0 and blk:
            s = schedule or self.store.get_schedule(date_str) or {}
            later = [b for b in (s.get("blocks") or []) if str(b.get("start", "")) >= str(blk.get("end", "24:00"))]
            if later:
                said = "; ".join(f"{b['start']} {_short(b.get('activity', ''))}" for b in later[:rest])
                lines.append(t(f"- still to come today: {said}", f"- 今日このあと: {said}"))
        for nm, lo, hi, why in self.absent(date_str):
            lines.append(t(f"- {nm} is NOT around {lo}-{hi}" + (f": {why}" if why else "") + " -- nobody is with them, nobody saw them",
                           f"- {nm}は{lo}-{hi}のあいだ、いない" + (f": {why}" if why else "") + " -- 誰も一緒にいないし、誰も見ていない"))
        for x in self.settled(date_str):
            lines.append(t(f"- settled: {x}", f"- 確定: {x}"))
        ml = self.meal_line(date_str)
        if ml:
            lines.append(t(f"- what she has eaten today: {ml}", f"- 今日食べたもの: {ml}"))
        if self.money:
            try:
                bl = self.money.bought_line(date_str)
                if bl:
                    lines.append(f"- {bl}")
            except Exception:
                pass
        if for_whom == "her":
            wear = self.wearing(blk, scene, date_str)
            if wear:
                lines.append(t(f"- wearing: {wear}", f"- 着ているもの: {wear}"))
            if self.money:
                try:
                    ml = self.money.line()
                    if ml:
                        lines.append(f"- {ml}")
                except Exception:
                    pass
            if self.commitments:
                try:
                    for r in self.commitments.open():
                        if r.get("date") == date_str:
                            # a promise about a public event the calendar has
                            # nothing of is settled `moot` at the compile; it
                            # does not stand in the day's one truth until then
                            if self.promise_unbacked(r):
                                continue
                            lines.append(t(f"- promised {r.get('to_name')}: {r.get('what')}",
                                           f"- {r.get('to_name')}との約束: {r.get('what')}")
                                         + (t(f" at {r['from_hm']}", f"（{r['from_hm']}）") if r.get("from_hm") else ""))
                except Exception:
                    pass
        if not lines:
            return ""
        if getattr(self.config.situation_block, "ledger_preamble", True):
            head = t("THE DAY'S LEDGER (the machine's record of today; every line here is true and outranks memory, "
                     "prose and habit -- a person marked NOT around is not in any scene; a block's activity is the plan's "
                     "wording, and what she has bought or eaten is the record's own line):",
                     "今日の台帳（機械が持っている今日の記録。ここにある行はすべて本当で、記憶にも文章にも習慣にも優先する。"
                     "「いない」と書かれた人はどの場面にもいない。時間帯の行動は予定に書かれたままの言葉で、"
                     "買ったもの食べたものは記録そのものの行）:")
        else:
            head = t("today, as recorded:", "今日の記録:")
        return head + "\n" + "\n".join(lines)

    def day_text(self, date_str):
        """The whole day for the compile: every block with who was actually
        there, the absences, the settled facts."""
        s = self.store.get_schedule(date_str)
        lines = []
        for b in (s or {}).get("blocks", []):
            who = ", ".join(self.people_in(b)) or "alone"
            lines.append(f"- {b['start']}-{b['end']}: {b.get('activity', '')} @ {b.get('location', '')}, with {who}")
        for nm, lo, hi, why in self.absent(date_str):
            lines.append(f"- {nm} was NOT around {lo}-{hi}" + (f": {why}" if why else "")
                         + " -- she was not with them, did not see them, and they were not on any train")
        for x in self.settled(date_str):
            lines.append(f"- settled: {x}")
        wear = self.wearing(date_str=date_str)
        if wear:
            lines.append(f"- she wore: {wear}")
        if self.money:
            try:
                bl = self.money.bought_line(date_str)
                if bl:
                    lines.append(f"- {bl}")
            except Exception:
                pass
        return "\n".join(lines)

    # ---------------- the audit ----------------
    def audit(self, date_str=None):
        """What contradicts the ledger, for `/absurd`: an absent person still
        in a block's `with`; a promise KEPT to somebody absent; a `with` name
        the roster does not know."""
        date_str = date_str or self.clock.date_str()
        faults = []
        s = self.store.get_schedule(date_str)
        absent = self.absent(date_str)
        for b in (s or {}).get("blocks", []):
            for n in self.people_in(b):
                low = n.lower()
                # a hedge the schedule wrote ("maybe dad") is dad, maybe: any
                # roster name inside the phrase resolves it
                known = roster.role_of(self.config, n) or any(roster.role_of(self.config, w) for w in re.split(r"[\s,/&()]+", n) if w)
                if not known and not any(k in low for k in NOT_PEOPLE):
                    faults.append(f"{b['start']} with '{n}': not on her roster")
                for nm, lo, hi, _w in absent:
                    if roster.same(self.config, nm, n) and b["start"] < hi and b["end"] > lo:
                        faults.append(f"{b['start']} with {n}, who is absent {lo}-{hi}")
        if self.commitments:
            try:
                for r in self.commitments.rows():
                    if r.get("date") == date_str and r.get("status") == "kept" and any(
                            roster.same(self.config, nm, r.get("to_name", "")) and
                            (not r.get("from_hm") or lo <= r["from_hm"] < hi) for nm, lo, hi, _w in absent):
                        faults.append(f"promise to {r['to_name']} KEPT on a day they were absent: {r.get('what', '')[:50]}")
            except Exception:
                pass
        return faults
