"""Simulated him: one model call per turn. Inputs: style profile, conversation as he saw it, day plan.

Model (User 10-22 20:10: "my model is not running on Claude"): with a run_id, each turn goes through the gateway as
arm X on that run (`/arm/X/<run_id>/v1`), so the gateway forces the run's model (deepseek-v4.1-flash-1017 on Surplus)
and logs the call in the run's calls.jsonl with arm "X". Without a run_id (probe) or under BZ_LLM_STUB it uses llm.ask.
"""
from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timedelta

from .. import llm
from ..common import GATEWAY, PROFILES, from_him, iso, parse_ts, read_json, to_him

SYSTEM = {
    "en": ("You play one real person texting a companion character on his phone. You are not an assistant. "
           "Write exactly like the style profile says: its length, voice, habits and timing. "
           "Never copy old content; improvise on what the conversation and your day plan give you. "
           "Romance and flirting are fine when the profile shows he does that. "
           "You see only her messages, nothing behind them. "
           "Answer with one JSON object and nothing else."),
    "ja": ("You play one real person texting a companion character on his phone. You are not an assistant. "
           "He writes to her in Japanese. Write exactly like the style profile says: its length, voice, habits and "
           "timing. Never copy old content; improvise on what the conversation and your day plan give you. "
           "Romance and flirting are fine when the profile shows he does that. "
           "You see only her messages, nothing behind them. "
           "Answer with one JSON object and nothing else."),
}

FORMAT = ('Reply with JSON only: {"write": true|false, "text": "<message, empty if write is false>", '
          '"next_look": "<ISO local time you next look at your phone, after NOW; required if write is false, '
          'optional if write is true>"}. If you write, the text is exactly what you send, in his language and '
          'style, no quotes around it, no stage directions.')


def load_profile(character: str) -> dict:
    p = read_json(PROFILES / f"{character}.json")
    if p is None:
        raise FileNotFoundError(f"no style profile for {character}: build it with python -m bzombie.sim_him profile {character}")
    return p


def format_conversation(conv: list, max_lines: int = 60) -> str:
    """conv: transcript entries {virtual_ts, who: him|her, text}. Her outputs and his own lines only."""
    out = []
    for e in conv[-max_lines:]:
        if e.get("who") not in ("him", "her"):
            continue
        txt = llm.strip_stamps(e["text"]).replace("\n", " / ")  # no stamps in what he sees (model check 17:15)
        out.append(f"{'me' if e['who'] == 'him' else 'her'}: {txt}")
    return "\n".join(out)


def build_prompt(profile: dict, conv: list, day_plan: str, now: datetime, lang: str, today_me: int) -> str:
    import json
    return (f"STYLE PROFILE:\n{json.dumps(profile, ensure_ascii=False, indent=1)}\n\n"
            f"YOUR PLAN FOR TODAY:\n{day_plan}\n\n"
            f"NOW: {iso(now)} ({now.strftime('%A')})\n"
            f"TODAY_ME: {today_me}\n"
            f"CONVERSATION:\n{format_conversation(conv)}\n\n{FORMAT}")


def ask_gateway(run_id: str, system: str, prompt: str, timeout: float = 1500) -> str:
    # longer than the gateway's own retry chain (240 s per hung attempt, up to 5 retries), so a Surplus hang
    # costs time, never the run (cl1 10-22: three 605 s calls paused all four runs at a 300 s client timeout)
    """One chat call through the gateway as arm X of the run; the gateway forces the run's model."""
    body = json.dumps({"model": "sim-him", "temperature": 0.8, "max_tokens": 1024, "stream": False,
                       "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]},
                      ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(f"{GATEWAY}/arm/X/{run_id}/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer bz"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        d = json.load(resp)
    return d["choices"][0]["message"]["content"] or ""


def ask_json(run_id: str | None, system: str, prompt: str, retries: int = 1):
    if not run_id or os.environ.get("BZ_LLM_STUB") == "1" or llm.backend is not None:
        return llm.ask_json("him", system, prompt)
    last = None
    for _ in range(retries + 1):
        try:
            return llm.extract_json(ask_gateway(run_id, system, prompt))
        except ValueError as e:
            last = e
    raise last


def decide(profile: dict, conv: list, day_plan: str, now: datetime, lang: str, today_me: int = 0,
           min_gap_min: int = 5, him_tz: str | None = None, run_id: str | None = None) -> dict:
    """Returns {"write": bool, "text": str, "next_look": ISO str (always set when write is False)}.

    now and next_look are on the virtual (Tokyo) timeline; he sees NOW and gives next_look in his own zone him_tz."""
    prompt = build_prompt(profile, conv, day_plan, to_him(now, him_tz), lang, today_me)
    r = ask_json(run_id, SYSTEM.get(lang, SYSTEM["en"]), prompt)
    text = llm.strip_stamps(str(r.get("text") or ""))
    write = bool(r.get("write")) and bool(text)
    nl = r.get("next_look")
    try:
        nlt = parse_ts(nl) if nl else None
    except ValueError:
        nlt = None
    if nlt is not None:
        nlt = from_him(nlt.replace(tzinfo=None), him_tz)
    if nlt is None or nlt <= now:
        nlt = None if write else now + timedelta(minutes=min_gap_min * 6)
    return {"write": write, "text": text if write else "",
            "next_look": iso(nlt) if nlt else None}
