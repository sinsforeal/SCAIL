"""Bench arm D adapter (design 5): the owner as a harness-side process for one run.

Config: run config key "world" (dict, optional keys: spec path, seed). Present means arm D; the driver calls
WorldRunner.day() once per simulated day and merges the returned env events (kind: world) into the day's script.
Outputs under var/bzombie/runs/<run_id>/:
  world_log.jsonl      one beat per line (bzombie/grounding.py contract), appended day by day
  castworld/day_<n>.json   the whole day (beats, events, drops, call counts); reused on a resume, so a replay
                           after a restore never re-calls the model
  castworld/drops.jsonl    every beat or line dropped by code, with the reason
  castworld/calls.json     calls per name per day
  castworld.db         the owner's own save
Calls go through the run's gateway as arm X (the gateway forces the run's model, deepseek-v4.1-flash-1017).
The world does not react to her replies (harness-side, pre-rendered per day), so a scene's cast turns are lines to
the room; the arm answers each as it arrives on the virtual clock.
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from . import spec as specmod
from .engine import Owner
from .store import Store

GATEWAY = "http://127.0.0.1:18330"
SYSTEM = "あなたは物語の世界の進行役です。指示された形式のJSONだけを返します。"


def gateway_chat(run_id: str, gateway: str = GATEWAY, timeout: float = 1500):
    url = f"{gateway}/arm/X/{run_id}/v1/chat/completions"

    def chat(text: str) -> str:
        body = json.dumps({"model": "castworld", "temperature": 0.8, "max_tokens": 1500, "stream": False,
                           "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}]},
                          ensure_ascii=False).encode("utf-8")
        last = None
        for _ in range(2):
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json",
                                                                  "Authorization": "Bearer bz"})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    return json.load(r)["choices"][0]["message"]["content"] or ""
            except OSError as e:  # URLError, timeout; a 402 budget stop is an HTTPError (OSError) too: surface it
                last = e
                if getattr(e, "code", 0) == 402:
                    raise
        raise last
    return chat


def _append(p: Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


class WorldRunner:
    def __init__(self, run_dir, run_id: str, world_cfg: dict | None = None, seed: int = 1, chat=None, spec=None):
        self.rd = Path(run_dir)
        w = world_cfg if isinstance(world_cfg, dict) else {}
        self.spec = spec or specmod.load(w.get("spec"))
        self.store = Store(self.rd / "castworld.db")
        self.owner = Owner(self.spec, self.store, chat or gateway_chat(run_id, w.get("gateway", GATEWAY)),
                           seed=int(w.get("seed", seed) or 1))

    def day(self, day_index: int, date_str: str) -> list:
        """The day's env events (kind world), in virtual order. Reuses a saved day (resume safe)."""
        cache = self.rd / "castworld" / f"day_{day_index}.json"
        if cache.exists():
            return json.loads(cache.read_text(encoding="utf-8"))["events_out"]
        res = self.owner.run_day(date_str)
        src = f"castworld/day_{day_index}"
        out = [{"ts": e["ts"], "kind": "world", "text": e["text"], "source": src} for e in res["events"]]
        for row in res["world_log"]:
            _append(self.rd / "world_log.jsonl", {**row, "day": day_index})
        for d in res["drops"]:
            _append(self.rd / "castworld" / "drops.jsonl", {**d, "day": day_index})
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({**res, "events_out": out}, ensure_ascii=False, indent=1), encoding="utf-8")
        return out

    def close(self):
        self.store.close()
