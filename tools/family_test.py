"""Where the parents are, and the pickup answers, over a few weeks, on a
copy of the save. No LLM.

    python tools/family_test.py
"""
import os
import sys
import tempfile
import datetime
import zoneinfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.dbcopy import copy_db  # noqa: E402
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logger
logger.setup = lambda out_dir: None
logger.log = lambda m, to_console=True: None

from config import Config
from store import Store
from world.clock import WorldClock
from world.calendar import Calendar
from tomoe.family import Family


def main():
    tmp = os.path.join(tempfile.gettempdir(), "scail_family.db")
    copy_db("data/world.db", tmp)
    cfg = Config()
    st = Store(tmp)
    clk = WorldClock(cfg)
    tz = zoneinfo.ZoneInfo("Asia/Tokyo")
    t = [datetime.datetime(2026, 9, 1, 12, 0, tzinfo=tz).timestamp()]
    clk.now_ts = lambda: t[0]
    clk.now = lambda: datetime.datetime.fromtimestamp(t[0], tz)
    clk.to_char = lambda ts: datetime.datetime.fromtimestamp(ts, tz)
    clk.hm = lambda ts=None: datetime.datetime.fromtimestamp(ts or t[0], tz).strftime("%H:%M")
    clk.date_str = lambda ts=None: datetime.datetime.fromtimestamp(ts or t[0], tz).strftime("%Y-%m-%d")
    fam = Family(cfg, st, clk, Calendar(cfg), None)
    fails = []

    def check(label, ok):
        print(("  ok   " if ok else "  FAIL ") + label)
        if not ok:
            fails.append(label)

    def at(y, mo, d, h, mi=0):
        return datetime.datetime(y, mo, d, h, mi, tzinfo=tz).timestamp()

    # Tue 2026-09-01
    check("dad at work Tuesday noon", fam.where("dad", at(2026, 9, 1, 12))[0] == "work")
    check("mom at the Life Tuesday 11:00", fam.where("mom", at(2026, 9, 1, 11))[0] == "work")
    check("mom home Tuesday 16:00", fam.where("mom", at(2026, 9, 1, 16))[0] == "home")
    check("dad asleep at 03:00", fam.where("dad", at(2026, 9, 2, 3))[0] == "asleep")
    # every answer is (str, str) at every hour of a week -- the nested tuple
    # that took the director down on 08-26
    bad = [(dd, hh, who) for dd in range(1, 8) for hh in range(0, 24) for who in ("dad", "mom")
           if not all(isinstance(x, str) for x in fam.where(who, at(2026, 9, dd, hh, 30)))]
    check(f"where() always returns two strings ({len(bad)} bad)", not bad)
    ok, who, why = fam.can_pickup(at(2026, 9, 1, 19, 30), minutes_away=20)
    check(f"no pickup Tuesday 19:30: {why}", not ok)
    ok, who, why = fam.can_pickup(at(2026, 9, 1, 11, 0), minutes_away=10)
    check(f"mom in daylight, close: {who} -- {why}", (ok and who == "mom") or "work" in why or "Life" in why)
    # Sunday 2026-09-06
    check("dad home Sunday 15:00", fam.where("dad", at(2026, 9, 6, 15))[0] in ("home", "out"))
    yes = no = 0
    for d in (6, 13, 20, 27):
        ok, who, why = fam.can_pickup(at(2026, 9, d, 15, 0), minutes_away=15)
        yes += ok
        no += (not ok)
    check(f"Sunday afternoon pickups mostly yes ({yes} of 4)", yes >= 2)
    # weeknights: dad home late and sometimes unwilling
    answers = []
    for d in range(1, 26):
        ts = at(2026, 9, d, 22, 45)
        if datetime.datetime.fromtimestamp(ts, tz).weekday() >= 5:
            continue
        ok, who, why = fam.can_pickup(ts, minutes_away=20)
        answers.append((ok, why))
    yes = sum(1 for a in answers if a[0])
    unwilling = sum(1 for a in answers if not a[0] and ("last train" in a[1] or "sofa" in a[1] or "fifteen" in a[1]))
    away_or_out = sum(1 for a in answers if not a[0] and ("drinking" in a[1] or "dark" in a[1] or "nobody" in a[1] or "work" in a[1]))
    check(f"weeknights 22:45 over 3.5 weeks: {yes} yes, {unwilling} home-but-no, {away_or_out} not there / drunk / dark", yes >= 1 and unwilling >= 1 and away_or_out >= 1)
    # a family day exists in the next two months
    trips = []
    for i in range(0, 60):
        dd = datetime.date(2026, 9, 1) + datetime.timedelta(days=i)
        tr = fam.day(dd).get("trip")
        if tr:
            trips.append((dd.isoformat(), tr["name"]))
    check(f"family days in Sep-Oct: {trips}", 1 <= len(trips) <= 8)
    # a business trip shows up somewhere in the autumn
    away = [(datetime.date(2026, 9, 1) + datetime.timedelta(days=i)).isoformat() for i in range(0, 90)
            if fam.day(datetime.date(2026, 9, 1) + datetime.timedelta(days=i))["dad"]["away"]]
    check(f"dad away on a work trip some weekdays in the autumn: {away[:6]}", 1 <= len(away) <= 12)
    # the same date draws the same day
    a = fam.day(datetime.date(2026, 9, 4))
    st.set("family_days", {})
    b = fam.day(datetime.date(2026, 9, 4))
    check("the draw is seeded (same day twice)", a == b)
    print(fam.brief(datetime.date(2026, 9, 4)))
    print(fam.brief(datetime.date(2026, 9, 6)))
    print(f"\n{len(fails)} failure(s)" if fails else "\nall ok")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
