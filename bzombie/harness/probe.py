"""python -m bzombie.harness probe --character momoka|tomoe [--cap-usd 2]

One real profile build if missing, one env-writer day, one sim-him turn against a canned two-line history, all through
the real credits path (reserve, dispatch, settle once). Result: var/bzombie/probe/<yyyymmdd_hhmm>.json (texts, costs,
durations, errors). An agent cannot run this (agent_boundary hook); the orchestrator launches it hidden.
"""
from __future__ import annotations

import os
import time
from datetime import datetime

from .. import credits, llm
from ..common import PROFILES, VAR, iso, write_json
from ..env import writer
from ..sim_him import him, profile

CANNED = {
    "tomoe": [("him", "morning. how was the lecture"), ("her", "so boring, I almost fell asleep. you?")],
    "momoka": [("him", "おはよう、今日は何するの"), ("her", "えっと、特になにもないよ。あなたは？")],
}
LANG = {"tomoe": "en", "momoka": "ja"}


def _step(out: dict, name: str, fn):
    s = llm.session.reservation
    before, t0 = s.spent_usd, time.time()
    rec = {"step": name, "error": None}
    try:
        rec["result"] = fn()
    except Exception as e:  # recorded, the probe goes on to the next step
        rec["error"] = s.scrub(f"{type(e).__name__}: {e}")[:600]
    rec["cost_usd"] = round(s.spent_usd - before, 6)
    rec["wall_s"] = round(time.time() - t0, 2)
    out["steps"].append(rec)


def run(character: str, cap_usd: float = 2.0) -> dict:
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    out = {"character": character, "stamp": stamp, "cap_usd": cap_usd, "model": llm.MODEL, "steps": [],
           "credits_error": None}
    rd = VAR / "probe" / f"{stamp}_calls"
    res = credits.Reservation(f"scail/bzombie_probe_{stamp}", cap_usd, os.getpid())
    try:
        res.open()
        llm.session = llm.Session(res, rd, cap_usd)
        if not (PROFILES / f"{character}.json").exists():
            _step(out, "profile", lambda: {k: str(v)[:200] for k, v in profile.build(character).items()
                                           if k != "measured"})
        else:
            out["steps"].append({"step": "profile", "skipped": "already built", "error": None})
        now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        _step(out, "env_day", lambda: _env(character, now))
        _step(out, "sim_him", lambda: _him(character))
        out["claude_calls"] = llm.session.calls
    except credits.CreditsRefused as e:
        out["credits_error"] = str(e)[:600]
    finally:
        llm.session = None
        try:
            res.settle()
        except credits.CreditsRefused as e:
            out["settle_error"] = str(e)[:600]
    out["total_cost_usd"] = round(res.spent_usd, 6)
    write_json(VAR / "probe" / f"{stamp}.json", out)
    return out


def _env(character: str, date: datetime) -> dict:
    d = writer.day_script(character, f"probe{datetime.now():%Y%m%d_%H%M}", 0, date)  # fresh seed: always a real call
    return {"events": len(d["events"]), "first_events": d["events"][:3], "him_plan": d["him_plan"],
            "world_state": d["world_state"]}


def _him(character: str) -> dict:
    now = datetime.now().replace(microsecond=0)
    conv = [{"who": w, "virtual_ts": iso(now), "text": t} for w, t in CANNED[character]]
    prof = him.load_profile(character)
    return him.decide(prof, conv, "a normal day, free in the evening", now, LANG[character], 1)
