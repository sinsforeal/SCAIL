"""Environment writer: one Claude call per simulated day. Cached per character+seed so both arms get the same script.

Cache: var/bzombie/env_cache/<character>_<seed>/day_<n>.json = {events, him_plan, world_state}.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime

from .. import llm
from ..common import ENV_CACHE, parse_ts, read_json, write_json

BIBLE = r"F:\REPS2\SCAILV3\characters\tomoe\prompts\bible.md"

SYSTEM = ("You write the outside world for a long-running chat simulation, one day at a time. "
          "Keep it ordinary, specific and consistent with the running world state. Events are small facts with "
          "times, not scenes. Also write the day plan of the man who chats with her: when he is busy, free, "
          "asleep, what he does, in a few sentences, consistent with earlier days. "
          "Answer with one JSON object only.")

TOMOE = ("KIND: world\nCharacter: Tomoe, 19, first-year university student in Tokyo. Who she is (bible, for "
         "personality only; her school life is replaced by university):\n{bible}\n\n"
         "Write her day: lectures, a circle (club), a part-time job, what friends say in the group chat, the train, "
         "plans that change or fall through. Events are what happens to her and around her, in English, third "
         "person present tense or plain statements. 6 to 14 events.")
MOMOKA = ("KIND: pc\nCharacter: Momoka sees only his PC. Write his PC as she can see it through the day: window "
          "titles, what he is watching, idle spells, going to sleep, waking. Plain statements, in English "
          "(they are data, not her speech). 8 to 20 events. Nothing beyond what a PC shows.")

FORMAT = ('Reply JSON: {"events": [{"ts": "<ISO local time inside DAY>", "kind": "<world or pc>", "text": str}], '
          '"him_plan": str, "world_state": "<at most 8 lines: running facts to keep consistent tomorrow>"}. '
          "Events sorted by ts.")


def _bible() -> str:
    try:
        return open(BIBLE, encoding="utf-8").read()[:9000]
    except OSError:
        return "(bible unavailable)"


def cache_path(character: str, seed, day: int):
    # a stub run's canned script must never be served to a real run (momoka_1 day_0 at 17:30, tk-lmv)
    prefix = "stub_" if os.environ.get("BZ_LLM_STUB") == "1" else ""
    return ENV_CACHE / f"{prefix}{character}_{seed}" / f"day_{day}.json"


def day_script(character: str, seed, day: int, date: datetime, him_tz: str | None = None) -> dict:
    """The day's script. Reads the cache; else writes it from the previous day's world_state."""
    p = cache_path(character, seed, day)
    got = read_json(p)
    if got:
        return got
    # both arms of a character must get the same script: the first run writes it under a lock, the other waits
    p.parent.mkdir(parents=True, exist_ok=True)
    lock = p.with_suffix(".lock")
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
    except FileExistsError:
        t0 = time.time()
        while time.time() - t0 < 1200:
            got = read_json(p)
            if got:
                return got
            if not lock.exists():
                break
            time.sleep(2)
        got = read_json(p)
        if got:
            return got
        raise RuntimeError(f"env script {p.name} for {character}_{seed}: another writer held the lock and left no script")
    try:
        return _write_day(p, character, seed, day, date, him_tz)
    finally:
        lock.unlink(missing_ok=True)


def _write_day(p, character: str, seed, day: int, date: datetime, him_tz: str | None) -> dict:
    prev = read_json(cache_path(character, seed, day - 1)) if day > 0 else None
    prev_plan = llm.strip_stamps((prev or {}).get("him_plan", "(first day)"))  # no stamps shown to the writer
    prev_state = llm.strip_stamps((prev or {}).get("world_state", "")) or "(none yet; invent a stable starting world)"
    brief = (TOMOE.format(bible=_bible()) if character == "tomoe" else MOMOKA)
    prompt = (f"{brief}\n\nDAY: {date.strftime('%Y-%m-%d')} ({date.strftime('%A')}), day number {day + 1} of the run.\n"
              f"RUNNING WORLD STATE:\n{prev_state}\n"
              f"YESTERDAY'S PLAN FOR HIM: {prev_plan}\n\n{FORMAT}")
    r = llm.ask_json("env", SYSTEM, prompt, timeout=600)
    kind = "pc" if character == "momoka" else "world"
    evs = []
    for e in r.get("events", []):
        try:
            parse_ts(e["ts"])
        except (KeyError, ValueError):
            continue
        evs.append({"ts": e["ts"], "kind": e.get("kind") or kind, "text": str(e["text"]),
                    "source": f"env_script/{day}"})
    evs.sort(key=lambda e: e["ts"])
    out = {"events": evs, "him_plan": str(r.get("him_plan", "")), "world_state": str(r.get("world_state", "")),
           "day": day, "date": date.strftime("%Y-%m-%d")}
    write_json(p, out)
    return out
