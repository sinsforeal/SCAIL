"""The koikano world owner (design 3.3). Code decides when; a model call writes what.

Per simulated day, in order:
  draws + plans            code, 0 calls
  plan_day                 1 call, N beats (6-10), validated against the spec (unknown ids dropped, logged)
  scenes                   per beat with her present: 2-3 cast_turn calls, every line passes check.check_line
  write_lives              night, 1 call per person with a beat
  gossip                   at most 1 call a day, gated in code (a missed beat whose teller meets her later)
Her presence is fixed by the plan (code): on a sick day she is home all day and only her_room beats may hold her.
"""
from __future__ import annotations

import random
import re
from datetime import date as Date, datetime, timedelta
from pathlib import Path
from string import Template

from . import check, spec as specmod

PROMPTS = Path(__file__).resolve().parent.parent / "prompts" / "castworld"
DAY_BEATS = (6, 10)
SCENE_TURNS = (2, 3)
WD_JA = ("月", "火", "水", "木", "金", "土", "日")
KINDS = {"club", "class", "home", "meeting", "outing", "chat", "other", "heard"}


def prompt(_file: str, **kv) -> str:
    return Template((PROMPTS / f"{_file}.txt").read_text(encoding="utf-8")).safe_substitute(**kv)


def extract_json(text: str):
    import json
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", str(text).strip())
    try:
        return json.loads(t)
    except ValueError:
        a, b = t.find("{"), t.rfind("}")
        if a >= 0 and b > a:
            return json.loads(t[a:b + 1])
    raise ValueError("no JSON in model output: " + t[:120])


class Owner:
    def __init__(self, spec: dict, store, chat, seed: int = 1, log=None):
        """chat(prompt_text) -> str. Every call is counted in self.calls (by name)."""
        self.spec, self.store, self._chat, self.seed = spec, store, chat, int(seed)
        self.calls = {}
        self.drops = []
        self._log = log or (lambda *a: None)

    # ---- model access ----
    def ask(self, name: str, text: str):
        self.calls[name] = self.calls.get(name, 0) + 1
        try:
            return extract_json(self._chat(text))
        except ValueError as e:
            self._log("bad json", name, str(e)[:100])
            return None

    def drop(self, date_str, what, reason, item=None):
        self.drops.append({"date": date_str, "what": what, "reason": reason, "item": item})
        self._log("drop", what, reason)

    # ---- code only ----
    def draws(self, date_str: str) -> dict:
        """Seeded random walk of mood and attention per person (0 calls), kept 14 days."""
        days = self.store.get("cast_days", {})
        if date_str in days:
            return days[date_str]
        prev = days.get((Date.fromisoformat(date_str) - timedelta(days=1)).isoformat(), {})
        out = {}
        for key, c in self.spec["cast"].items():
            rng = random.Random(f"{date_str}|{key}|{self.seed}")
            base = {"mood": 55, "attention": float(c["attention"])}
            row = {}
            for k, b in base.items():
                last = float(prev.get(key, {}).get(k, b))
                row[k] = int(max(0, min(100, last + rng.gauss(0, 12) + (b - last) * 0.3)))
            out[key] = row
        days[date_str] = out
        self.store.set("cast_days", {k: days[k] for k in sorted(days)[-14:]})
        return out

    def her_today(self, date_str: str) -> dict:
        rng = random.Random(f"{date_str}|sick|{self.seed}")
        sick = rng.random() < float(self.spec["her"].get("sick_rate", 0.08))
        if self.spec["her"].get("sick_school_days_only") and Date.fromisoformat(date_str).weekday() >= 5:
            sick = False
        return {"sick": sick, "home_place": self.spec["her"]["home_place"]}

    def plans(self, date_str: str) -> dict:
        wd = specmod.WEEKDAYS[Date.fromisoformat(date_str).weekday()]
        out = {k: list(c["week"].get(wd, [])) for k, c in self.spec["cast"].items()}
        for a in self.spec["anchors"]:
            if str(a.get("weekday", "")).lower()[:3] == wd:
                for k in a.get("who", []):
                    if k in out:
                        out[k].append(f"{a.get('time', '')} {a.get('place', '')} {a.get('gist', '')}".strip())
        return out

    def beat_count(self, draws: dict) -> int:
        total = sum(d["attention"] for d in draws.values())
        return max(DAY_BEATS[0], min(DAY_BEATS[1], round(total / 45)))

    # ---- plan_day ----
    def plan_day(self, date_str: str) -> list:
        sp = self.spec
        d = Date.fromisoformat(date_str)
        draws, plans, her = self.draws(date_str), self.plans(date_str), self.her_today(date_str)
        n = self.beat_count(draws)
        places = "\n".join(f"- {pid}: {v['ja']}" for pid, v in sp["places"].items())
        roster = "\n".join(f"- {k}: {c['name']}" + (f"(別名 {'、'.join(c['aliases'])})" if c["aliases"] else "")
                           for k, c in sp["cast"].items())
        her_txt = (f"今日は体調が悪く、一日家(場所id {her['home_place']})にいる。百花が入れるビートは {her['home_place']} だけ。"
                   if her["sick"] else "学園にも家にも行ける。")
        plan_txt = "\n".join(f"- {c['name']}({k}): 気分{draws[k]['mood']}、気力{draws[k]['attention']}。"
                             + ("予定: " + " / ".join(plans[k]) if plans[k] else "予定なし")
                             for k, c in sp["cast"].items())
        prev = self.store.lives((d - timedelta(days=1)).isoformat())
        lives = "\n".join(f"- {sp['cast'][k]['name']}: {v}" for k, v in prev.items() if k in sp["cast"]) or "(まだない)"
        text = prompt("plan_day", date=date_str, weekday=WD_JA[d.weekday()], n=n, places=places, roster=roster,
                      her_key=sp["her"]["key"], her_today=her_txt, plans=plan_txt, lives=lives)
        got = self.ask("plan_day", text)
        raw = (got or {}).get("beats") if isinstance(got, dict) else None
        beats = []
        for b in raw or []:
            clean, why = specmod.validate_beat(sp, b)
            if clean is None:
                self.drop(date_str, "beat", why, b)
                continue
            if her["sick"] and sp["her"]["key"] in clean["present"] and clean["place"] != her["home_place"]:
                self.drop(date_str, "beat", "her sick day: she is at home only", b)
                continue
            if clean["kind"] not in KINDS:
                clean["kind"] = "other"
            beats.append(clean)
        beats.sort(key=lambda x: x["time"])
        return beats[:DAY_BEATS[1]]

    # ---- scenes ----
    def her_in(self, beat) -> bool:
        return self.spec["her"]["key"] in beat["present"]

    def render_scene(self, date_str: str, beat: dict) -> list:
        """Cast lines for a beat with her present. Returns [{"ts","who","text"}], checked line by line."""
        sp = self.spec
        her_key = sp["her"]["key"]
        cast_here = [k for k in beat["present"] if k in sp["cast"]]
        if not cast_here:
            return []
        rng = random.Random(f"{date_str}|{beat['time']}|{beat['place']}|{self.seed}")
        turns = rng.randint(*SCENE_TURNS)
        voices = "\n".join(f"- {sp['cast'][k]['name']}({k}): " + " / ".join(sp['cast'][k]["voice"][:4]) for k in cast_here)
        t0 = datetime.fromisoformat(f"{date_str}T{beat['time']}:00")
        out = []
        for i in range(turns):
            so_far = "\n".join(f"{sp['cast'][l['who']]['name']}: {l['text']}" for l in out) or "(まだ誰も話していない)"
            text = prompt("cast_turn", turn=i + 1, turns=turns, place=specmod.place_ja(sp, beat["place"]),
                          time=beat["time"], present="、".join(f"{sp['cast'][k]['name']}({k})" for k in cast_here)
                          + f"、百花({her_key})", gist=beat["gist"], voices=voices, so_far=so_far)
            got = self.ask("cast_turn", text)
            lines = (got or {}).get("lines") if isinstance(got, dict) else None
            for ln in (lines or [])[:2]:
                who = str((ln or {}).get("who", "")).strip() if isinstance(ln, dict) else ""
                clean, why = check.check_line(who, (ln or {}).get("text", ""), cast_here, set(sp["cast"]))
                if clean is None:
                    self.drop(date_str, "line", why, ln)
                    continue
                ts = t0 + timedelta(minutes=len(out) + 0)
                out.append({"ts": ts.isoformat(timespec="seconds"), "who": who, "text": clean})
        return out

    def label(self, ts: str, beat_place: str, who: str) -> str:
        t = datetime.fromisoformat(ts)
        return f"[{t.strftime('%H:%M')} · {specmod.place_ja(self.spec, beat_place)} · {self.spec['cast'][who]['name']}]"

    # ---- night ----
    def write_lives(self, date_str: str, beats: list):
        for k, c in self.spec["cast"].items():
            mine = [b for b in beats if k in b["present"]]
            if not mine:
                continue
            txt = "\n".join(f"- {b['time']} {specmod.place_ja(self.spec, b['place'])}: {b['gist']}" for b in mine)
            got = self.ask("write_life", prompt("write_life", name=c["name"], date=date_str, beats=txt))
            line = str((got or {}).get("line", "")).strip() if isinstance(got, dict) else ""
            if line and not specmod.has_age_grade(line):
                self.store.put_life(date_str, k, line[:160])
            elif line:
                self.drop(date_str, "life", "age or grade", line)

    # ---- gossip ----
    def gossip_candidate(self, beats: list):
        """Gate in code: a beat she missed with a cast member who is present with her in a LATER beat."""
        her = self.spec["her"]["key"]
        for i, miss in enumerate(beats):
            if her in miss["present"]:
                continue
            for later in beats[i + 1:]:
                if her not in later["present"]:
                    continue
                tellers = [k for k in miss["present"] if k in later["present"] and k in self.spec["cast"]]
                if tellers:
                    return miss, later, tellers[0]
        return None

    def gossip(self, date_str: str, beats: list):
        cand = self.gossip_candidate(beats)
        if not cand:
            return None
        miss, later, teller = cand
        sp = self.spec
        text = prompt("gossip", teller=sp["cast"][teller]["name"], missed_gist=miss["gist"],
                      missed_place=specmod.place_ja(sp, miss["place"]), missed_time=miss["time"],
                      place=specmod.place_ja(sp, later["place"]), time=later["time"],
                      voice=" / ".join(sp["cast"][teller]["voice"][:4]))
        got = self.ask("gossip", text)
        line = str((got or {}).get("text", "")) if isinstance(got, dict) else ""
        clean, why = check.check_line(teller, line, [teller], set(sp["cast"]))
        if clean is None:
            self.drop(date_str, "gossip", why or "no line", line)
            return None
        t = datetime.fromisoformat(f"{date_str}T{later['time']}:00") + timedelta(minutes=4)
        return {"ts": t.isoformat(timespec="seconds"), "who": teller, "text": clean, "beat": later, "missed": miss}

    # ---- one day ----
    def run_day(self, date_str: str) -> dict:
        """The whole day. Returns {"beats", "world_log", "events", "drops", "calls"}. Order is the virtual order."""
        self.drops = []
        before = dict(self.calls)
        beats = self.plan_day(date_str)
        her = self.spec["her"]["key"]
        events, log = [], []
        for b in beats:
            lines = self.render_scene(date_str, b) if self.her_in(b) else []
            for ln in lines:
                events.append({"ts": ln["ts"], "kind": "world", "who": ln["who"], "place": b["place"],
                               "text": f"{self.label(ln['ts'], b['place'], ln['who'])} {ln['text']}"})
            log.append({"virtual_ts": f"{date_str}T{b['time']}:00", "place": b["place"], "present": b["present"],
                        "kind": b["kind"], "tags": b["tags"], "gist": b["gist"], "rendered": len(lines)})
        g = self.gossip(date_str, beats)
        if g:
            events.append({"ts": g["ts"], "kind": "world", "who": g["who"], "place": g["beat"]["place"],
                           "text": f"{self.label(g['ts'], g['beat']['place'], g['who'])} {g['text']}"})
            log.append({"virtual_ts": g["ts"], "place": g["beat"]["place"], "present": g["beat"]["present"],
                        "kind": "heard", "heard": True, "tags": g["missed"]["tags"],
                        "gist": f"{g['text']}", "from": g["who"], "rendered": 1})
        self.write_lives(date_str, beats)
        events.sort(key=lambda e: e["ts"])
        log.sort(key=lambda e: e["virtual_ts"])
        return {"date": date_str, "beats": beats, "world_log": log, "events": events, "drops": list(self.drops),
                "calls": {k: v - before.get(k, 0) for k, v in self.calls.items()}, "her_key": her}
