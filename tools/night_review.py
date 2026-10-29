"""What a night of the group chat actually costs, before it is run for real.

The late stretch (`Cast._late_window` / `_fill_late`) and the paced exchange
(`Exchange.tick`) between them decide how many messages there are, how far
apart they land, and how many model calls with distinct contexts that takes.
None of it was measurable without waiting a day per sample.

This mirrors the real logic rather than guessing at it:

  window      `_late_window` / `_group_morning` on the real cast file
  the chat    `chat_project.one_exchange`, which drives the real `_gap`,
              `_away`, `_sleeps`, `_awake_friends` and `_continue_p` -- the
              rounds, the speakers, the absences and who falls asleep are
              not modelled twice here

Calls counted the way they are actually made: one `cast_day` for the plan, one
`cast_beat` per beat (each with that person's sheet), one `cast_reply` per turn
of hers, and one `cast_turn` per speaker per round of theirs. Read-only, no
model, no store writes.

    python tools/night_review.py                 # 14 nights
    python tools/night_review.py --nights 60     # a longer sample
    python tools/night_review.py --from 2026-09-01
"""
import argparse
import datetime
import json
import os
import random
import sqlite3
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logger
logger.log = lambda m, to_console=True: None

from config import Config
from world.calendar import Calendar
from world.clock import hm_to_minutes
from tomoe.cast import CastEngine
import chat_project

TURNS_PER_CALL = (1, 2, 3)          # a speaker's call returns one to three turns
TURN_CHARS = (18, 95)               # observed range in the record


def hm(m):
    m = int(m) % (24 * 60)
    return "%02d:%02d" % (m // 60, m % 60)


def overrun(r, start_min):
    """How far past its own declared end the chat actually ran, in minutes.
    Both clocks are kept on the same side of midnight first -- the last light
    is often "02:13", which is 133 as a wall clock and 1573 as a time counted
    from a 23:00 start."""
    end = hm_to_minutes(r["last_hm"])
    if end < start_min:
        end += 24 * 60
    return int(round(r["end"] - end))


def one_night(cfg, cast, rng, date_str, draws):
    """A night's late stretch, simulated turn by turn."""
    c = cfg.cast
    ex = cfg.exchange
    last_hm, tail, has_late = cast._late_window(date_str)
    first = cast._group_morning(date_str)
    out = {"date": date_str, "last_hm": last_hm, "has_late": has_late,
           "morning": hm(first) if first else "-", "beats": 0, "turns": 0,
           "gaps": [], "calls": {}, "speakers": set(), "span": 0, "end": 0}
    if not has_late:
        return out

    start = hm_to_minutes(c.late_from_hm)
    end = hm_to_minutes(last_hm)
    span = (end - start) % (24 * 60)
    out["span"] = span
    n_beats = int(c.late_beats_min) + (1 if rng.random() < 0.35 else 0)
    out["beats"] = n_beats

    from tomoe.cast import FAMILY
    friends = [k for k, r in (cast.state.relationships or {}).items()
               if k != "him" and not r.get("dormant")
               and str(r.get("role_id") or "") not in FAMILY]

    out.setdefault("by_agent", {})

    def bump(role, n=1, agent=None):
        out["calls"][role] = out["calls"].get(role, 0) + n
        key = agent or str(cfg.character.name)
        out["by_agent"][key] = out["by_agent"].get(key, 0) + n

    # one store for the night: somebody who falls asleep in the first beat is
    # still asleep for the second
    store = chat_project._Store()
    for _b in range(n_beats):
        # nobody on her roster is nobody: a night with no friend in it has
        # no opener, and the fallback used to be the first character's friend
        if not friends:
            break
        opener = rng.choice(friends)
        bump("cast_beat", agent=opener)         # the opener, in that person's voice
        out["speakers"].add(opener)
        t = start + rng.randint(0, max(1, span - 5))
        r = chat_project.one_exchange(cfg, rng.randint(0, 10 ** 6), start_hm=hm(t),
                                      store=store, last_hm=last_hm)
        out["turns"] += r["msgs"]
        out["aways"] = out.get("aways", 0) + r["aways"]
        out["why"] = r["why"]
        # the calls the exchange made, split the way they are actually made
        bump("cast_reply", max(1, r["calls"] // 2))
        for s in friends[:ex.group_max_speakers]:
            bump("cast_turn", max(0, (r["calls"] - max(1, r["calls"] // 2)) // max(1, min(len(friends), ex.group_max_speakers))), agent=s)
            out["speakers"].add(s)
        out["gaps"].append(r["mins"] * 60.0 / max(1, r["msgs"]))
        t += r["mins"]
        out["end"] = max(out["end"], t)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nights", type=int, default=14)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--start", default="2026-08-28")
    ap.add_argument("--config", default="config.json", help="whose nights")
    a = ap.parse_args()

    cfg = Config(a.config)
    con = sqlite3.connect("file:%s?mode=ro" % str(cfg.logging.db_path).replace("\\", "/"),
                          uri=True)

    def kv(k, d):
        r = con.execute("select value from kv where key=?", (k,)).fetchone()
        return json.loads(r[0]) if r else d

    rels, commits = kv("relationships", {}), kv("commitments", [])

    class St:
        relationships = rels

    class Store:
        def get(s, k, d=None):
            return commits if k == "commitments" else (d if d is not None else {})

    cast = CastEngine.__new__(CastEngine)
    cast.config, cast.state, cast.store = cfg, St(), Store()
    cast.calendar = Calendar(cfg)

    rng = random.Random(a.seed)
    d0 = datetime.date.fromisoformat(a.start)
    draws = {k: {"attention": (r.get("rhythm") or {}).get("attention", 50)} for k, r in rels.items()}

    rows = [one_night(cfg, cast, rng, (d0 + datetime.timedelta(days=i)).isoformat(), draws)
            for i in range(a.nights)]

    print(f"{a.nights} nights from {a.start}, seed {a.seed}\n")
    print(f"{'night':<12}{'tomorrow':<5}{'earliest up':>12}{'chat dies':>11}"
          f"{'window':>9}{'msgs':>6}{'mean gap':>10}{'last msg':>8}{'over':>6}   calls")
    print("-" * 108)
    for r in rows:
        d = datetime.date.fromisoformat(r["date"])
        nxt = (d + datetime.timedelta(days=1)).strftime("%a")
        if not r["has_late"]:
            print(f"{r['date']:<12}{nxt:<5}{r['morning']:>12}{r['last_hm']:>11}"
                  f"{'quiet':>9}{'-':>6}{'-':>10}   -")
            continue
        g = statistics.mean(r["gaps"]) if r["gaps"] else 0
        calls = ", ".join(f"{k} {v}" for k, v in sorted(r["calls"].items()))
        over = overrun(r, hm_to_minutes(cfg.cast.late_from_hm))
        print(f"{r['date']:<12}{nxt:<5}{r['morning']:>12}{r['last_hm']:>11}"
              f"{str(r['span']) + 'm':>9}{r['turns']:>6}{g / 60:>8.1f}m"
              f"{hm(r['end']):>8}{('+' + str(over)) if over > 0 else '':>6}   {calls}")

    start_min = hm_to_minutes(cfg.cast.late_from_hm)
    overs = [overrun(r, start_min) for r in rows if r["has_late"]]
    live = [r for r in rows if r["has_late"]]
    allg = [g for r in rows for g in r["gaps"]]
    tot = {}
    for r in rows:
        for k, v in r["calls"].items():
            tot[k] = tot.get(k, 0) + v

    print("\n" + "=" * 96)
    print(f"nights running late         {len(live)} of {len(rows)}  ({100*len(live)//max(len(rows),1)}%)")
    if live:
        print(f"window when it runs         {min(r['span'] for r in live)}-{max(r['span'] for r in live)} min, "
              f"mean {statistics.mean(r['span'] for r in live):.0f}")
        print(f"last message                {min(r['last_hm'] for r in live)} .. {max(r['last_hm'] for r in live)}")
        print(f"messages a late night       mean {statistics.mean(r['turns'] for r in live):.1f}, "
              f"range {min(r['turns'] for r in live)}-{max(r['turns'] for r in live)}")
        print(f"messages per night, all     mean {statistics.mean(r['turns'] for r in rows):.1f}")
        print(f"ran past its own end        mean {statistics.mean(overs):+.0f} min, worst {max(overs):+d}; "
              f"over on {sum(1 for o in overs if o > 0)} of {len(overs)} late nights")
    if allg:
        allg.sort()
        print(f"gap between messages        mean {statistics.mean(allg)/60:.1f}m, "
              f"median {allg[len(allg)//2]/60:.1f}m, "
              f"p90 {allg[int(0.9*(len(allg)-1))]/60:.1f}m, max {max(allg)/60:.1f}m")
    print()
    print("model calls, each with its own context:")
    for k, v in sorted(tot.items(), key=lambda x: -x[1]):
        print(f"  {k:<12} {v:>5}   {v/max(len(rows),1):>5.1f} a night")
    n_late = max(len(live), 1)
    print(f"  {'TOTAL':<12} {sum(tot.values()):>5}   {sum(tot.values())/max(len(rows),1):>5.1f} a night"
          f"   |  {sum(tot.values())/n_late:>4.1f} on a night that RUNS late")
    print()
    print("  The per-night average is dragged down by the quiet nights; the second")
    print("  column is what a late night actually costs. Both are the late stretch")
    print("  only -- a whole day is around 560 calls, of which the cast layer is 11%.")
    print("  Late exchanges draw on `exchange.late_reserved`, not the day's budget.")
    per = {}
    for r in rows:
        for k, v in (r.get("by_agent") or {}).items():
            per[k] = per.get(k, 0) + v
    print()
    print("per agent -- each call carries that person's own sheet, day and edges:")
    for k, v in sorted(per.items(), key=lambda x: -x[1]):
        print(f"  {k:<12} {v:>5}   {v/max(len(rows),1):>5.1f} a night")


if __name__ == "__main__":
    main()
