"""What the group chat will produce, from the dials as they stand.

Not a reading of the record -- the record is from before the mechanics
changed. This DRIVES THE REAL CODE (`Exchange._gap`, `_away`, `_sleeps`,
`_awake_friends`, `_continue_p`) with a stub store and clock and counts what
comes out, so the answer moves when the dials move and cannot drift away from
what the bot actually does. Only the model calls are stubbed: a call returns
one to four messages, which is what `cast_turn` and `cast_reply` ask for.

The chain, in the order it binds:

    beats        beats_base + beats_per_attention * sum(attention)/100, capped
                 beats_max; plus idle_share and late_beats_min, then re-capped
    exchanges    a beat becomes one only if `wants()` lets it: exchange
                 .max_per_day, plus exchange.late_reserved for the late group
                 ones, and nobody who has fallen asleep opens anything
    rounds       it ends on group_max_rounds, on a failed group_continue_p
                 draw -- dragged down by away_drag for every absence so far --
                 or when everybody who was in it has gone to sleep
    speakers     the opener, plus each other AWAKE friend on
                 min(0.9, group_jump_in_p * attention/50), capped
                 group_max_speakers

    python tools/chat_project.py
    python tools/chat_project.py --group-exchanges 6 --nights 500
"""
import argparse
import datetime
import os
import random
import statistics
import sys
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logger
logger.log = lambda m, to_console=True: None

from config import Config
from tomoe.exchange import Exchange

TZ = ZoneInfo("Asia/Tokyo")
TURNS_PER_CALL = (1, 2, 2, 3, 4)      # what the prompts ask for
ATT = {"香芝玲奈": 65, "米山日南子": 35, "前田亜矢": 55}
REL = {"him": {"role_id": "partner", "name": "him"},
       "Rena-chan": {"role_id": "ringleader", "name": "香芝玲奈"},
       "Hinako": {"role_id": "rival", "name": "米山日南子"},
       "Aya": {"role_id": "confidante", "name": "前田亜矢"},
       "mom": {"role_id": "mother", "name": "古賀由美"},
       "Kaito": {"role_id": "sibling", "name": "古賀海斗"}}

STARTS = ["16:20", "18:05", "20:10", "22:15", "23:40", "00:30", "01:10", "01:50"]


class _Store:
    def __init__(self):
        self.kv = {}

    def get(self, k, d=None):
        return self.kv.get(k, {} if d is None else d)

    def set(self, k, v):
        self.kv[k] = v


class _Clock:
    def __init__(self, ts):
        self.ts = ts

    def now_ts(self):
        return self.ts

    def now(self):
        return datetime.datetime.fromtimestamp(self.ts, tz=TZ)

    def to_char(self, ts):
        return datetime.datetime.fromtimestamp(ts, tz=TZ)

    def hm(self, ts=None):
        return self.to_char(self.ts if ts is None else ts).strftime("%H:%M")

    def date_str(self, ts=None):
        return self.to_char(self.ts if ts is None else ts).strftime("%Y-%m-%d")


def _past(hm, last_hm):
    """The night's last light, the way `Exchange._past_last_light` reads it:
    the small hours belong to the evening they came out of, and only the six
    hours after it count as an overrun."""
    if not last_hm:
        return False

    def since_noon(s):
        m = int(s[:2]) * 60 + int(s[3:5])
        return m + 24 * 60 if m < 12 * 60 else m

    return 0 <= since_noon(hm) - since_noon(last_hm) <= 6 * 60


def one_exchange(cfg, seed, start_hm="22:40", store=None, last_hm=""):
    """One group exchange, played out on the real gap and continue code."""
    rng = random.Random(seed)
    random.seed(seed)
    h, m = int(start_hm[:2]), int(start_hm[3:])
    start = datetime.datetime(2026, 8, 29, h, m, tzinfo=TZ).timestamp()
    clock = _Clock(start)
    ex = Exchange.__new__(Exchange)
    ex.config, ex.clock = cfg, clock
    ex.store = store if store is not None else _Store()
    ex.state = type("S", (), {"relationships": REL, "gauges": {}})()
    awake = ex._awake_friends()
    who = "香芝玲奈" if "香芝玲奈" in awake else (awake[0] if awake else "")
    if not who:
        return {"msgs": 0, "mins": 0.0, "why": "everybody was asleep", "aways": 0, "calls": 0}
    rec = {"who": who, "kind": "group", "turns": [{"who": who, "ja": "x" * 40}],
           "rounds": 0, "aways": 0, "side": "hers"}
    msgs, calls, t, why = 1, 1, start, ""
    while True:
        calls += 1                                   # cast_reply: her side
        for _ in range(rng.choice(TURNS_PER_CALL)):
            t += ex._gap(40, 40, "group", clock.hm(t), rec=rec, next_side="hers")
            rec["turns"].append({"who": "古賀朋絵", "ja": "x" * 40})
            msgs += 1
        rec["rounds"] += 1
        clock.ts = t
        if _past(clock.hm(t), last_hm):
            why = "the chat was done for the night"
            break
        if rec["rounds"] >= cfg.exchange.group_max_rounds:
            why = "ran its rounds"
            break
        if random.random() > ex._continue_p("group", rec):
            why = "petered out"
            break
        t += ex._gap(40, 40, "group", clock.hm(t), rec=rec, next_side="theirs")
        clock.ts = t
        awake = ex._awake_friends()
        if not awake:
            why = "they had all gone to sleep"
            break
        speakers = [who] if who in awake else []
        for f in awake:
            if f in speakers or len(speakers) >= cfg.exchange.group_max_speakers:
                continue
            if random.random() < min(0.9, cfg.exchange.group_jump_in_p * ATT.get(f, 50) / 50.0):
                speakers.append(f)
        if not speakers:
            why = "nobody picked it up"
            break
        for s in speakers:
            calls += 1                               # cast_turn: one call each
            for _ in range(rng.choice(TURNS_PER_CALL)):
                rec["turns"].append({"who": s, "ja": "x" * 40})
                msgs += 1
                t += 12
        clock.ts = t
        if (t - start) / 60.0 > cfg.exchange.group_max_live_minutes:
            why = "it trailed off (the live cap)"
            break
    return {"msgs": msgs, "mins": (t - start) / 60.0, "why": why,
            "aways": rec["aways"], "calls": calls}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nights", type=int, default=400)
    ap.add_argument("--group-exchanges", type=int, default=5,
                    help="group exchanges a day (the beats that `wants()` lets through)")
    a = ap.parse_args()

    cfg = Config()
    ex, ca = cfg.exchange, cfg.cast
    atts = {"Rena-chan": 65, "Hinako": 35, "Aya": 55, "mom": 60, "dad": 25, "Kaito": 50}
    beats = min(ca.beats_max, round(ca.beats_base + ca.beats_per_attention * sum(atts.values()) / 100.0))

    print("THE DIALS AS THEY STAND\n")
    print(f"  beats a day            {beats}  (cap {ca.beats_max}; idle floor "
          f"{ca.idle_share:.0%}, late floor {ca.late_beats_min})")
    print(f"  exchanges a day        {ex.max_per_day} + {ex.late_reserved} reserved late")
    print(f"  a group exchange ends  rounds >= {ex.group_max_rounds}, group_continue_p "
          f"{ex.group_continue_p} (x{ex.away_drag} per absence), {ex.group_max_live_minutes} min, "
          f"or everybody asleep")
    print(f"  who jumps in           group_jump_in_p {ex.group_jump_in_p}, cap {ex.group_max_speakers}")
    print(f"  absences               away_p {ex.away_p}; one reason ends the night, "
          f"back about {ex.sleep_wake_hm}")
    print()

    days = []
    for d in range(a.nights):
        store = _Store()                     # one night: sleep carries across its exchanges
        rows = [one_exchange(cfg, 4000 + d * 17 + i, start_hm=hm, store=store)
                for i, hm in enumerate(STARTS[:a.group_exchanges])]
        days.append(rows)
    msgs = [sum(r["msgs"] for r in day) for day in days]
    calls = [sum(r["calls"] for r in day) for day in days]
    ones = [r for day in days for r in day]

    print("WHAT THAT COMES TO\n")
    print(f"  a group exchange       {statistics.mean(r['msgs'] for r in ones):.0f} messages, "
          f"{statistics.mean(r['calls'] for r in ones):.1f} calls, "
          f"{statistics.mean(r['mins'] for r in ones):.0f} min, "
          f"{statistics.mean(r['aways'] for r in ones):.1f} absences")
    print(f"  a day ({a.group_exchanges} of them)     "
          f"{statistics.mean(msgs):.0f} messages (median {statistics.median(msgs):.0f}, "
          f"{min(msgs)}-{max(msgs)}), {statistics.mean(calls):.0f} calls")
    print(f"  cost                   "
          f"{statistics.mean(calls) / max(statistics.mean(msgs), 1):.2f} calls a message")
    print()
    why = {}
    for r in ones:
        why[r["why"]] = why.get(r["why"], 0) + 1
    print("  how a group exchange ends:")
    for k, v in sorted(why.items(), key=lambda x: -x[1]):
        print(f"    {k:<28} {100 * v / len(ones):>4.0f}%")
    print()
    print(f"  Her prompt carries the newest {getattr(ex, 'group_full_recent', 2)} group "
          f"conversations whole and the older")
    print("  ones as their gist: at this volume the whole thing is ~14k characters against")
    print("  a `chat` section budgeted at 1,000 tokens.")


if __name__ == "__main__":
    main()
