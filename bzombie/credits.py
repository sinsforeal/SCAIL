"""API-credit billing for the bench's claude -p children (meta terms 10-22 17:14).

Per run, from the driver: reserve -> dispatch (before the first claude call) -> settle once with the summed
total_cost_usd. The API key of the reservation's label is read from ~/.scail/secrets.json inside this process
and goes only into a child's env as ANTHROPIC_API_KEY. It is never logged, printed, written or put in a message.
A credits.py refusal (nonzero exit) raises CreditsRefused with its stderr text. The User 10-22 17:23-17:24: the API
grant is one-time and not replenished; burn it first. claude -p cannot use the subscription, so after the grant the
work goes to normal agents through the bench session's queue. `exhausted()` tells a used-up grant apart
(GrantExhausted) from any other refusal. The key's workspace id goes along as a header (child_env).
Tests swap `runner` (the credits.py caller) and `read_key` (the secrets reader).
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from .common import HIDE, hidden_env

META_PY = r"F:\REPS2\Meta_Orchestrator\.venv\Scripts\python.exe"
CREDITS_PY = r"F:\REPS2\Meta_Orchestrator\tools\limits\credits.py"
SECRETS = Path(os.path.expanduser("~")) / ".scail" / "secrets.json"
TTL_S = 86400  # a run lasts hours; credits.py default 900 s would expire it


class CreditsRefused(Exception):
    """credits.py said no (or answered garbage). Message is its stderr text, never a key."""


class GrantExhausted(CreditsRefused):
    """The one-time API grant is used up. claude -p cannot run on the subscription (User 10-22 17:24), so the
    harness's Claude work moves to the bench session's queue (normal agents); until that exists the run pauses."""


def _runner(args: list) -> tuple:
    p = subprocess.run([META_PY, CREDITS_PY] + [str(a) for a in args], capture_output=True, text=True,
                       encoding="utf-8", timeout=120, creationflags=HIDE, env=hidden_env())
    return p.returncode, p.stdout, p.stderr


def _entry(label: str) -> dict:
    data = json.loads(SECRETS.read_text(encoding="utf-8"))
    for k in (data.get("anthropic_api") or {}).get("keys") or []:
        if isinstance(k, dict) and k.get("label") == label and k.get("key"):
            return k
    raise CreditsRefused(f"no API key with label {label!r} in secrets")  # label is not a secret


def _read_key(label: str) -> str:
    return str(_entry(label)["key"])


def _read_workspace(label: str) -> str:
    """The grant keys are not workspace-scoped: every request needs anthropic-workspace-id (API 400 otherwise)."""
    return str(_entry(label).get("workspace_id") or "")


def exhausted(text: str) -> bool:
    """The one-time grant is used up (credits.py refusal or the API's own answer): time for the subscription."""
    t = (text or "").lower()
    return "insufficient confirmed" in t or "credit balance is too low" in t or "credit balance too low" in t


runner = _runner
read_key = _read_key
read_workspace = _read_workspace


def _call(args: list) -> dict:
    rc, out, err = runner(args)
    if rc != 0:
        why = (err or out or f"credits.py exit {rc}").strip()[:600]
        raise (GrantExhausted if exhausted(why) else CreditsRefused)(why)
    try:
        d = json.loads(out)
    except ValueError:
        raise CreditsRefused("credits.py printed no JSON: " + (out or "")[:200])
    return d if isinstance(d, dict) else {}


class Reservation:
    """One run's credit reservation. open() reserves and dispatches; settle() runs once."""

    def __init__(self, who: str, cap_usd: float, pid: int | None = None):
        self.who, self.cap_usd, self.pid = who, float(cap_usd), pid or os.getpid()
        self.id = None
        self.label = None
        self.settled = False
        self.spent_usd = 0.0
        self._key = None

    def open(self) -> "Reservation":
        r = _call(["reserve", "--who", self.who, "--amount-usd", self.cap_usd, "--pid", self.pid,
                   "--ttl-s", TTL_S])
        self.id, self.label = r.get("id"), r.get("key_label")
        if not self.id or not self.label:
            raise CreditsRefused("reserve answer has no id or key_label")
        _call(["dispatch", self.id, "--pid", self.pid, "--ttl-s", TTL_S])
        return self

    def key(self) -> str:
        if self._key is None:
            self._key = read_key(self.label)
        return self._key

    def child_env(self, env: dict) -> dict:
        """Put the key and its workspace header into a child's env (and nowhere else)."""
        env["ANTHROPIC_API_KEY"] = self.key()
        ws = read_workspace(self.label)
        if ws:
            env["ANTHROPIC_CUSTOM_HEADERS"] = f"anthropic-workspace-id: {ws}"
        return env

    def add(self, usd: float):
        self.spent_usd += float(usd or 0)

    def settle(self):
        """Once. Safe to call from every exit path."""
        if self.settled or not self.id:
            return None
        self.settled = True
        return _call(["settle", self.id, "--actual-usd", round(self.spent_usd, 6)])

    def scrub(self, text: str) -> str:
        return text.replace(self._key, "***") if self._key and text else text
