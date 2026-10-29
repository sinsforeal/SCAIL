import time
import datetime
from zoneinfo import ZoneInfo

# Two clocks matter: hers (character_timezone) and his (user_timezone). Every
# scheduling decision runs on hers. In sim mode the world starts at sim_start
# and advances sim_speed times faster than wall time, so a full day can be
# dry-run in minutes. Sensors and Telegram still use the wall clock; only the
# simulated character time is fictional.


class WorldClock:
    def __init__(self, config):
        w = config.world
        self.char_tz = ZoneInfo(w.character_timezone)
        if w.user_timezone == "local":
            self.user_tz = datetime.datetime.now().astimezone().tzinfo
        else:
            self.user_tz = ZoneInfo(w.user_timezone)
        # A character who has no world of her own has no timezone of her own:
        # she is resident on his machine and there is no elsewhere for her to
        # be. The second character booted many hours ahead of him, so her
        # morning was his evening, her day rolled over in the middle of his
        # afternoon, and the impulse gate read "he is never about at this hour"
        # about the hour he was sitting at the keyboard.
        if not config.character.existence.in_world:
            self.char_tz = self.user_tz
        self.mode = config.clock.mode
        self.speed = float(config.clock.sim_speed)
        self._wall_anchor = time.time()
        if self.mode == "sim":
            start = config.clock.sim_start
            if start:
                naive = datetime.datetime.strptime(start, "%Y-%m-%d %H:%M")
                self._sim_anchor = naive.replace(tzinfo=self.char_tz).timestamp()
            else:
                self._sim_anchor = time.time()
        else:
            self._sim_anchor = None
        # Has this character a clock of her own that is not his? The record's
        # labels carry both readings where there are two and one where there
        # is one, so the question is answered once, at build, and every label
        # in a run is the same shape. A character with no world is on his
        # clock by the rule above; a character whose own zone happens to sit
        # at his offset would otherwise have every stamp print the same time
        # twice.
        self.two_clocks = (self.char_tz is not self.user_tz
                           and self.now().utcoffset() != self.user_now().utcoffset())

    def now_ts(self):
        if self.mode == "sim":
            return self._sim_anchor + (time.time() - self._wall_anchor) * self.speed
        return time.time()

    def now(self):
        return datetime.datetime.fromtimestamp(self.now_ts(), tz=self.char_tz)

    def user_now(self):
        return datetime.datetime.fromtimestamp(self.now_ts(), tz=self.user_tz)

    def to_char(self, ts):
        return datetime.datetime.fromtimestamp(ts, tz=self.char_tz)

    def to_user(self, ts):
        return datetime.datetime.fromtimestamp(ts, tz=self.user_tz)

    def char_zone_word(self):
        """The place her clock is kept on, in one word: "Asia/Tokyo" ->
        "Tokyo". A label that carries two readings has to say which is which,
        and the clock is what decides her timezone, so the word for it belongs
        here -- no shared module names a city, and a character configured into
        another zone gets that zone's word with no edit."""
        name = str(getattr(self.char_tz, "key", "") or "")
        return name.rsplit("/", 1)[-1].replace("_", " ") or "her time"

    def sleep(self, seconds):
        # sleeps `seconds` of character time
        if self.mode == "sim":
            time.sleep(max(0.01, seconds / self.speed))
        else:
            time.sleep(seconds)

    def wall_seconds(self, char_seconds):
        return char_seconds / self.speed if self.mode == "sim" else char_seconds

    def date_str(self, ts=None):
        d = self.now() if ts is None else self.to_char(ts)
        return d.strftime("%Y-%m-%d")

    def hm(self, ts=None):
        d = self.now() if ts is None else self.to_char(ts)
        return d.strftime("%H:%M")

    def offset_hours(self):
        # positive means she is ahead of him
        a = self.now().utcoffset().total_seconds()
        b = self.user_now().utcoffset().total_seconds()
        return (a - b) / 3600.0

    def stamp(self, ts=None):
        d = self.now() if ts is None else self.to_char(ts)
        return d.strftime("%Y-%m-%d %H:%M")

    def ts_of(self, date_str, hm, plus_days=0):
        """The real instant of a date and a wall time on HER clock. What the
        record keeps is "2026-08-28" and "21:07", which is only a time if you
        already know whose clock it is; this turns it back into a moment, so
        it can be shown on anybody's."""
        try:
            d = datetime.datetime.strptime(f"{date_str} {hm}", "%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            return 0.0
        return (d + datetime.timedelta(days=plus_days)).replace(tzinfo=self.char_tz).timestamp()

    def season(self, ts=None, ja=False):
        """Which of the four seasons it is on her clock."""
        d = self.now() if ts is None else self.to_char(ts)
        return season_of(d.month, ja)

    def time_of_year(self, ts=None, ja=False):
        """Where in the season her clock is, for a line a model reads."""
        d = self.now() if ts is None else self.to_char(ts)
        return time_of_year(d.month, ja)

    def both(self, ts=None):
        c = self.now() if ts is None else self.to_char(ts)
        u = self.user_now() if ts is None else self.to_user(ts)
        return f"{c.strftime('%a %H:%M')} her time, {u.strftime('%a %H:%M')} his time"

    def both_daypart(self, ts=None):
        """Both clocks, each with the part of the day it is in, and how far
        apart they are -- for any role that decides something about HIM.

        `both` gives two clock readings and leaves the reader to work out
        whose morning 10:30 is. The role that names the urge behind a message
        she starts did not: given "Sat 23:30 her time, Sat 10:30 his time" it
        wrote her the line "are you still awake? or did you fall asleep on me
        again", which she sent at his Saturday mid-morning, and did the same
        thing at his 08:10 and his 09:20 (2026-09-02, -04, -05). A character
        with no world of her own is on his clock, so there is one reading and
        nothing to be apart from."""
        c = self.now() if ts is None else self.to_char(ts)
        u = self.user_now() if ts is None else self.to_user(ts)
        if c.utcoffset() == u.utcoffset():
            return f"{c.strftime('%a %H:%M')} ({daypart(c.hour)}), his clock and hers"
        off = self.offset_hours()
        return (f"{c.strftime('%a %H:%M')} her time ({daypart(c.hour)}), "
                f"{u.strftime('%a %H:%M')} his time ({daypart(u.hour)}) -- "
                f"she is {abs(off):.0f} hours {'ahead of' if off > 0 else 'behind'} him")


def daypart(hour, ja=False):
    """Plain words for a clock hour, so nobody has to infer whether his 09:10 is his late night or his morning (she is many hours ahead; his morning is
    her late evening, and both she and the role that decides what she wants
    read it as him being up late)."""
    if hour < 5:
        return "真夜中" if ja else "the middle of the night"
    if hour < 9:
        return "早朝" if ja else "early morning"
    if hour < 12:
        return "午前" if ja else "morning"
    if hour < 14:
        return "昼" if ja else "midday"
    if hour < 17:
        return "午後" if ja else "afternoon"
    if hour < 20:
        return "夕方" if ja else "evening"
    if hour < 23:
        return "夜" if ja else "night"
    return "深夜" if ja else "late at night"


# The season a month falls in, in either language a character is addressed
# in. It belongs to the clock because a prompt that names a season names the
# one it was written in: the night prompt still opened with "Late August" in
# September, and would have said it in November. Three months each, the same
# division `tomoe/scenery.py` tags a photograph with, so a night written in
# September and a photograph picked in September agree about the time of year.
_SEASON_EN = ("winter", "spring", "summer", "autumn")
_SEASON_JA = ("冬", "春", "夏", "秋")


# Where in the season, which is the same size of function of the month: its
# place among the three. The line the night prompt used to hardcode was "Late
# August", and a bare "summer" would have thrown that away -- early September
# in Tokyo is still hot and full of cicadas, and late November is not.
_PART_EN = ("early ", "", "late ")
_PART_JA = (("初冬", "冬", "晩冬"), ("早春", "春", "晩春"),
            ("初夏", "真夏", "晩夏"), ("初秋", "秋", "晩秋"))


def season_of(month, ja=False):
    """Which of the four, for a tag: what a photograph is stored against."""
    return (_SEASON_JA if ja else _SEASON_EN)[(int(month) % 12) // 3]


def time_of_year(month, ja=False):
    """What time of year it is, for a line somebody reads: "late summer",
    "early autumn", 晩夏, 初秋."""
    i, part = (int(month) % 12) // 3, (int(month) % 12) % 3
    return _PART_JA[i][part] if ja else _PART_EN[part] + _SEASON_EN[i]


def parse_hm(hm):
    h, m = hm.split(":")
    return int(h), int(m)


def minutes_of_day(dt):
    return dt.hour * 60 + dt.minute


_RAISE = object()


def hm_to_minutes(hm, default=_RAISE):
    """"HH:MM" as minutes of the day. Strict by default; with `default` a
    string that is not a clock reads as that instead (a promise with no
    time on it, a block the model wrote badly)."""
    try:
        h, m = str(hm).split(":")
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        if default is _RAISE:
            raise
        return default


def minutes_to_hm(m, wrap=False):
    """Minutes of the day as "HH:MM". A schedule's day may end at "24:00" or
    later, so the hour is not wrapped unless asked; a clock reading is."""
    m = int(m)
    h = m // 60
    if wrap:
        h %= 24
    return f"{h:02d}:{m % 60:02d}"


def in_window(dt, start_hm, end_hm):
    # handles windows that cross midnight
    cur = minutes_of_day(dt)
    s = hm_to_minutes(start_hm)
    e = hm_to_minutes(end_hm)
    if s <= e:
        return s <= cur < e
    return cur >= s or cur < e
