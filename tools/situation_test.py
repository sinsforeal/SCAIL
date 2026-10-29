"""Walk one school-morning commute through embodied/situation.py with the clock
moved by hand, on a copy of the save. No LLM. Asserts the things that are
easy to break: the journey starts from the block, the legs come from the
map, a delayed line adds minutes, arrival lands on the right node, a late
arrival is an event, fatigue climbs on the walk in heat and falls in bed.

    python tools/situation_test.py
"""
import os
import sys
import tempfile
import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.dbcopy import copy_db  # noqa: E402
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logger
logger.setup = lambda out_dir: None
logger.log = lambda m, to_console=True: print("   " + m)

from config import Config
from store import Store
from world.clock import WorldClock
from sim.state import State
from embodied.situation import Situation


class FakeWeather:
    def __init__(self, feels=34.0, rain=0.0):
        self.feels, self.rain = feels, rain

    def current(self, dt=None):
        return {"temp": self.feels - 4, "feels": self.feels, "humidity": 70, "precip_mm": self.rain, "sky": "sunny"}


class FakeTrains:
    def __init__(self):
        self._now = {}


class FakeBody:
    def __init__(self, feels):
        self.last = {"ambient_feels": feels, "setting": "outdoors"}


def main():
    tmp = os.path.join(tempfile.gettempdir(), "scail_situation.db")
    copy_db("data/world.db", tmp)
    cfg = Config()
    st = Store(tmp)
    clk = WorldClock(cfg)
    # a hand clock: her time, moved by us
    base = datetime.datetime(2026, 9, 1, 7, 30, tzinfo=clk.char_tz) if hasattr(clk, "char_tz") else None
    if base is None:
        import zoneinfo
        base = datetime.datetime(2026, 9, 1, 7, 30, tzinfo=zoneinfo.ZoneInfo("Asia/Tokyo"))
    t = [base.timestamp()]
    clk.now_ts = lambda: t[0]
    clk.now = lambda: datetime.datetime.fromtimestamp(t[0], base.tzinfo)
    clk.hm = lambda ts=None: datetime.datetime.fromtimestamp(ts or t[0], base.tzinfo).strftime("%H:%M")
    clk.date_str = lambda ts=None: datetime.datetime.fromtimestamp(ts or t[0], base.tzinfo).strftime("%Y-%m-%d")
    clk.to_char = lambda ts: datetime.datetime.fromtimestamp(ts, base.tzinfo)
    state = State(cfg, st, clk)
    state.gauges["fatigue"] = 5.0
    trains = FakeTrains()
    sit = Situation(cfg, st, clk, FakeWeather(34.0), trains, FakeBody(34.0), state)
    sit.rec.update({"node": "home", "journey": None, "last_ts": t[0], "arrived_ts": t[0]})
    state.situation = sit
    blocks = [
        {"start": "06:45", "end": "07:35", "activity": "wake, wash, uniform", "location": "home", "with": "mom", "phone_access": "free"},
        {"start": "07:35", "end": "08:20", "activity": "walk to Nerima station, packed Seibu Ikebukuro line inbound, walk to school", "location": "commute", "with": "strangers", "phone_access": "glance"},
        {"start": "08:20", "end": "12:30", "activity": "morning classes", "location": "school, classroom 1-C", "with": "class", "phone_access": "glance"},
    ]
    fails = []

    def check(label, ok):
        print(("  ok   " if ok else "  FAIL ") + label)
        if not ok:
            fails.append(label)

    def step(minutes, scene=None):
        t[0] += minutes * 60
        return sit.tick(scene or {}, blocks)

    # 07:30 at home, the home block: nothing happens
    ev = step(0, {"location": "her room", "activity": "uniform, hair"})
    check("at home before the commute block: no journey", sit.rec["journey"] is None and sit.rec["node"] == "home")
    # 07:36: the commute block wants her at school
    ev = step(6, {"location": "her room", "activity": "grabbing her bag"})
    j = sit.rec["journey"]
    check("commute block starts a journey to school", bool(j) and j["to"] == "school")
    legs = [l["mode"] for l in j["legs"]] if j else []
    check(f"legs from the map: {legs}", legs == ["walk", "train", "walk"])
    check("the Seibu leg is packed at 07:46", any(l.get("crowd") == "packed" for l in j["legs"] if l["mode"] == "train"))
    check("the walk is hot", any(l.get("hot") for l in j["legs"] if l["mode"] == "walk"))
    plan = j["planned_min"]
    check(f"planned {plan} min (10+12+10 = 32)", plan == 32)
    f0 = state.gauges["fatigue"]
    check("walking mode while on the first leg", sit.mode() in ("walk", "walking"))
    check("delay multiplier while walking > 1.5", sit.delay_multiplier() > 1.5)
    check("shape bias curt while walking", sit.shape_bias() == "curt")
    line = sit.director_line()
    check("director told she is on the way", "ON THE WAY" in line and "cannot be at" in line)
    # 07:48: she is on the train; the line goes delayed under her
    ev = step(12, {"location": "commute", "activity": "on the train"})
    check("mode packed_train on the Seibu", sit.mode() == "packed_train")
    trains._now = {"西武池袋線": "遅延"}
    ev = step(1, {"location": "commute", "activity": "on the train"})
    check("a delayed line mid-ride is an event", any("遅延" in e["text"] for e in ev))
    j = sit.rec["journey"]
    check("eta pushed by delayed_minutes", (j["eta_ts"] - j["started_ts"]) / 60 >= plan + cfg.situation.delayed_minutes - 0.01)
    check("fatigue climbed on the hot walk", state.gauges["fatigue"] > f0 + 1)
    # ride it out
    ev = step(40, {"location": "school, classroom 1-C", "activity": "homeroom"})
    check("arrived at school", sit.rec["node"] == "school" and sit.rec["journey"] is None)
    check("late arrival is an event", any("late" in e["text"] for e in ev))
    rows = st.get("journeys", [])
    check("journey written with its effects", bool(rows) and rows[-1]["to"] == "school" and any("遅延" in x for x in rows[-1]["effects"]))
    # school is sitting; then home in bed: fatigue comes down
    f1 = state.gauges["fatigue"]
    blocks2 = [{"start": "00:00", "end": "23:59", "activity": "lying on the bed", "location": "her room", "with": "alone", "phone_access": "free"}]
    sit.rec.update({"node": "home", "journey": None})
    t[0] += 3600
    sit.rec["last_ts"] = t[0]
    t[0] += 3600
    sit.tick({"location": "her room", "activity": "lying on the bed, phone"}, blocks2)
    check(f"fatigue falls at rest ({f1:.0f} -> {state.gauges['fatigue']:.0f})", state.gauges["fatigue"] < f1)
    # a trip the map does not know
    sit.rec.update({"node": "home", "journey": None})
    sit.start("koto", why="test")
    j = sit.rec["journey"]
    check("a trip to the Pixar exhibition routes via the station and Ikebukuro", j and [l["to"] for l in j["legs"]] == ["nerima_station", "ikebukuro", "koto"])
    # late: she leaves at 08:05 for an 08:20 homeroom and runs
    sit.rec.update({"node": "home", "journey": None})
    t[0] = datetime.datetime(2026, 9, 1, 8, 5, tzinfo=base.tzinfo).timestamp()
    sit.rec["last_ts"] = t[0]
    state.gauges["fatigue"] = 5.0
    sit.tick({"location": "her room", "activity": "grabbing her bag"}, blocks)
    j = sit.rec["journey"]
    check("leaving at 08:05 for 08:20 is late: she runs", bool(j) and j["hurry"] and all(l.get("running") for l in j["legs"] if l["mode"] == "walk"))
    walk = [l for l in j["legs"] if l["mode"] == "walk"][0]
    check(f"a run leg is faster than its map minutes ({(walk['end_ts'] - walk['start_ts']) / 60:.1f} < 10)", (walk["end_ts"] - walk["start_ts"]) / 60 < 10)
    check("in the uniform with the school bag", "uniform" in j["outfit"]["wear"] and "school bag" in j["outfit"]["carry"])
    check("mode running; typing not possible", sit.mode() == "running" and sit.constraints()["can_type"].startswith("no"))
    f0 = state.gauges["fatigue"]
    sit.tick({"location": "commute", "activity": "running"}, blocks)
    t[0] += 5 * 60
    sit.tick({"location": "commute", "activity": "running"}, blocks)
    check(f"running in 34C costs more fatigue in 5 min ({state.gauges['fatigue'] - f0:.1f} > 1.5)", state.gauges["fatigue"] - f0 > 1.5)
    pc0 = state.gauges["physical_comfort"]
    check("sweat took comfort off", j.get("sweat", 0) > 0)
    # dad drives to Kaito's match
    sit.rec.update({"node": "home", "journey": None})
    sit.start("hikarigaoka", why="test", blk={"activity": "dad drives them to Kaito's match", "with": "dad, Kaito", "location": "Hikarigaoka Park"})
    j = sit.rec["journey"]
    check("with dad and 'drives': one car leg", bool(j) and j["vehicle"] == "car" and len(j["legs"]) == 1 and j["legs"][0]["mode"] == "car")
    # the bike to Shakujii
    sit.rec.update({"node": "home", "journey": None})
    sit.start("shakujii", why="test", blk={"activity": "cycling to Shakujii park", "with": "alone", "location": "Shakujii Park"})
    j = sit.rec["journey"]
    check("bike edge used to Shakujii", bool(j) and j["legs"][0]["mode"] == "bike")
    # a pickup when the line stops late in the evening
    sit.rec.update({"node": "ikebukuro", "journey": None})
    t[0] = datetime.datetime(2026, 9, 1, 21, 40, tzinfo=base.tzinfo).timestamp()
    sit.rec["last_ts"] = t[0]
    import random as _r
    _r.seed(1)
    sit.start("home", why="test", blk={"activity": "train home", "with": "strangers", "location": "commute"})
    trains._now = {"西武池袋線": "運転見合わせ"}
    t[0] += 60
    got = None
    for _ in range(6):
        ev = sit.tick({"location": "commute", "activity": "on the train"}, [{"start": "21:30", "end": "22:30", "activity": "train home", "location": "commute", "with": "strangers", "phone_access": "free"},
                                                                          {"start": "22:30", "end": "23:59", "activity": "home", "location": "her room", "with": "alone", "phone_access": "free"}])
        if any("dad" in e["text"] for e in ev):
            got = ev
            break
        sit.rec.update({"node": "ikebukuro", "journey": None})
        trains._now = {}
        sit.start("home", why="test")
        trains._now = {"西武池袋線": "運転見合わせ"}
        t[0] += 60
    # no family object on this Situation: nobody can come (the coin-toss
    # father of the old rule went with the runtime split; a character who
    # has a family answers through it, tools/family_test.py)
    check("a suspended line at 21:41 with no family object brings nobody, tried 6 times", got is None)
    # the event table: seeded, mostly nothing, sometimes a thing
    hits = {}
    for n in range(400):
        leg = {"from": "nerima_station", "to": "ikebukuro", "mode": "train", "min": 12, "crowd": "packed", "start_ts": 1000 + n, "end_ts": 1000 + n + 720}
        sit._roll(leg, 0, 5000 + n, {"load": 1.0}, False)
        if leg.get("event"):
            hits[leg["event"]["kind"]] = hits.get(leg["event"]["kind"], 0) + 1
    total = sum(hits.values())
    check(f"packed-train legs: {total}/400 had an event ({hits}) -- rare, not never", 20 <= total <= 120)
    print(sit.report())
    print(f"\n{len(fails)} failure(s)" if fails else "\nall ok")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
