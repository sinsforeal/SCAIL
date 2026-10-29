import os
import re
import json
import datetime


class Calendar:
    def __init__(self, config):
        self.lookahead = config.world.event_lookahead_days
        self.describe_limit = config.world.calendar_describe_limit
        # A character with no world of her own has no calendar: no school
        # terms, no national holidays, and none of what her wards announced,
        # because there are no wards. `Config.WORLD_FILES` has already blanked
        # the paths for her, so there is nothing here to read and nothing to
        # refuse method by method -- `describe` and `is_school_day` were
        # guarded first and `events` was not, so the morning outlook still went
        # looking for what was on today and gave her somebody else's disaster
        # drill to think about. Anything added to this class later inherits the
        # silence, because the silence is in the data and not in a branch.
        self.holidays = self._read(config.world.holidays_file, {})
        self.school = self._read(config.world.school_calendar_file,
                                 {"terms": [], "breaks": [], "events": [], "school_day": {}})
        self.config = config
        self._local_mtime = 0
        self._local = []
        self._reload_local()

    @staticmethod
    def _read(path, empty):
        if not path:
            return json.loads(json.dumps(empty))
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _reload_local(self):
        """Events discovered from the wards' own feeds (tools/local_events.py).

        Read off disk whenever the file changes, so a fetch that runs while she
        is awake reaches her without a restart, and kept separate from the
        hand-written calendar, which this never touches."""
        path = getattr(self.config.world, "local_events_file", "")
        # `events()` calls this on every look, so the constructor emptying the
        # list is not enough on its own: without this the file would be read
        # back in a moment later
        if not path or not self.config.character.existence.in_world:
            self._local = []
            return
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            self._local = []
            return
        if mtime == self._local_mtime:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                self._local = (json.load(f) or {}).get("events", [])
            self._local_mtime = mtime
        except (OSError, ValueError):
            self._local = []

    @staticmethod
    def _d(s):
        return datetime.date.fromisoformat(s)

    def _in(self, date, item):
        return self._d(item["start"]) <= date <= self._d(item["end"])

    def holiday(self, date):
        return self.holidays.get(date.isoformat())

    def term(self, date):
        for t in self.school["terms"]:
            if self._in(date, t):
                return t["name"]
        return None

    def school_break(self, date):
        for b in self.school["breaks"]:
            if self._in(date, b):
                return b["name"]
        return None

    def events(self, date, lookahead_days=0, limit=None):
        """What is on, soonest and shortest first.

        Ranking is not decoration. The discovered half of the calendar carries
        month-long exhibitions beside one-night festivals, and a thing that
        runs for 31 days is true on every one of them and worth saying on none.
        The key is one number in both directions: days from now to when this
        was or will be news. A festival starting today is 0, one tomorrow is 1,
        an exhibition in its fourth week is 25. So today beats tomorrow beats
        next week beats scenery, ties break on the shorter run, and `limit`
        cuts the tail rather than an arbitrary slice of the middle.
        """
        self._reload_local()
        out = []
        # the hand-written year first, then whatever the wards have announced
        for e in list(self.school["events"]) + list(self._local):
            s = self._d(e["start"])
            en = self._d(e["end"])
            run = (en - s).days + 1
            if s <= date <= en:
                elapsed = (date - s).days
                when = "today" if s == en else ("today, day 1" if s == date else f"today, day {elapsed + 1} of {run}")
                out.append({"name": e["name"], "when": when, "note": e.get("note", ""),
                            "start": e["start"], "end": e["end"],
                            "_rank": (elapsed, run)})  # started today = 0
            elif date < s <= date + datetime.timedelta(days=lookahead_days):
                n = (s - date).days
                out.append({"name": e["name"], "when": "tomorrow" if n == 1 else f"in {n} days",
                            "note": e.get("note", ""), "start": e["start"], "end": e["end"],
                            "_rank": (n, run)})  # in n days
        out.sort(key=lambda e: e["_rank"])
        return out[:limit] if limit else out

    # ---------------- naming one entry ----------------
    # A plan for a public event names the entry it means: the date it is on
    # and the title as the calendar holds it. That pair is what a settled
    # line, a beat and a promise carry, and it is checked here rather than by
    # looking for the word "festival" in a sentence -- "meet dad at the
    # station tomorrow" was the same phantom festival with the word taken out.
    _NOISE = re.compile(r"[\s　・'\"!?~〜–—\-_/,.:;()\[\]{}「」【】（）～！？]+")

    @classmethod
    def _norm(cls, s):
        return cls._NOISE.sub("", str(s or "")).casefold()

    def entry(self, date, title):
        """The event running on this date whose title is this one, or None.

        The title is compared with spacing and brackets taken out, and a
        shorter one that is the head of a longer one matches: the list a
        planner is shown holds names of sixty characters and a plan quotes as
        much of one as it needs."""
        want = self._norm(title)
        if not want or len(want) < 3:
            return None
        for e in self.events(date):
            have = self._norm(e.get("name"))
            if not have:
                continue
            if have == want or (len(want) >= 4 and (want in have or have in want)):
                return e
        return None

    def outing_on(self, date, words):
        """The entry on this date that one of these words makes a public
        event (`world.outing_words`), or None. One place asks the calendar
        what is on; the gate and the promise binding both read it."""
        ws = [str(w).lower() for w in (words or ()) if str(w).strip()]
        if not ws:
            return None
        for e in self.events(date):
            blob = (str(e.get("name", "")) + " " + str(e.get("note", ""))).lower()
            if any(w in blob for w in ws):
                return e
        return None

    def is_school_day(self, date):
        # she has no school if she has no world
        if not self.config.character.existence.in_world:
            return False
        if date.weekday() == 6:
            return False
        if date.weekday() == 5 and not self.school["school_day"].get("saturday_classes"):
            return False
        if self.holiday(date):
            return False
        if self.school_break(date):
            return False
        for e in self.school["events"]:
            if e.get("no_school") and self._in(date, e):
                return False
        return self.term(date) is not None

    def describe(self, date):
        # A school term and what her wards have announced are facts about
        # somebody who goes to that school and lives in those wards. Refused
        # here rather than at the fifteen call sites: the description reaches
        # the director, the morning outlook, the schedule and the cast, and it
        # took one of them for a character whose whole world is his desktop to
        # open her first morning with "Wednesday. A school day."
        if not self.config.character.existence.in_world:
            return date.strftime("%A %Y-%m-%d")
        parts = [date.strftime("%A %Y-%m-%d")]
        h = self.holiday(date)
        if h:
            parts.append(f"national holiday: {h}")
        b = self.school_break(date)
        if b:
            parts.append(f"school: {b}")
        elif self.is_school_day(date):
            parts.append(f"school day ({self.term(date)})")
        else:
            parts.append("no school today")
        ev = self.events(date, lookahead_days=self.lookahead, limit=self.describe_limit)
        for e in ev:
            s = f"{e['name']} ({e['when']})"
            if e["note"]:
                s += f": {e['note']}"
            parts.append(s)
        return ". ".join(parts)

    def school_day_template(self):
        return self.school["school_day"]
