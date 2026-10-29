"""Style profile builder. One Claude call per character from his real messages.

Raw messages and the profile stay in var/bzombie/profiles/ (gitignored). Nothing from them goes into a tracked file.
"""
from __future__ import annotations

import json
import sqlite3
import statistics
from collections import Counter
from datetime import datetime

from .. import llm
from ..common import PROFILES, write_json

SOURCES = {
    "tomoe": (r"F:/temp/scail_cost/world_copy.db", "en"),
    "momoka": (r"F:/REPS2/SCAILV4/data/momoka.db", "ja"),
}

SYSTEM = ("You write a style profile of one real person from his messages to a companion character. The profile is "
          "used to make another writer imitate his texting style. Describe voice, sentence shape, length, "
          "punctuation, emoji and slang habits, how he opens and ends a chat, how he reacts to her, topics he "
          "tends to raise (as categories, in your own words), how he flirts or does not, how long he stays away "
          "and at what hours he writes. Never include his old content: no names, no events, no quoted lines, "
          "no sentence copied from the messages. Answer with one JSON object only.")


def read_messages(character: str) -> list:
    path, _ = SOURCES[character]
    c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return [(r[0], r[1]) for r in c.execute("select ts, text from messages where role='user' order by ts")]
    finally:
        c.close()


def stats(msgs: list) -> dict:
    lens = [len(t) for _, t in msgs]
    hours = Counter(datetime.fromtimestamp(ts).hour for ts, _ in msgs)
    gaps = sorted((b[0] - a[0]) / 60 for a, b in zip(msgs, msgs[1:]))
    q = lambda p: round(gaps[int(p * (len(gaps) - 1))], 1) if gaps else None
    return {"count": len(msgs), "len_median": statistics.median(lens), "len_p10": sorted(lens)[len(lens) // 10],
            "len_p90": sorted(lens)[int(len(lens) * 0.9)], "hour_counts": {str(h): hours[h] for h in sorted(hours)},
            "gap_minutes_p25_p50_p75_p90": [q(.25), q(.5), q(.75), q(.9)],
            "days_active": len({datetime.fromtimestamp(ts).date() for ts, _ in msgs})}


def build(character: str) -> dict:
    msgs = read_messages(character)
    st = stats(msgs)
    body = "\n".join(f"- {t.replace(chr(10), ' / ')}" for _, t in msgs)
    prompt = (f"Measured facts (use them for length and timing):\n{json.dumps(st)}\n\n"
              f"His messages ({len(msgs)}):\n{body}\n\n"
              'Reply JSON: {"voice": str, "length": str, "punctuation_emoji": str, "openings_endings": str, '
              '"reaction_to_her": str, "topic_categories": [str], "flirting": str, "habits": [str], '
              '"timing": str, "dos": [str], "donts": [str]}')
    prof = llm.ask_json("profile", SYSTEM, prompt, timeout=600)
    prof["measured"] = st
    prof["character"] = character
    write_json(PROFILES / f"{character}.json", prof)
    return prof
