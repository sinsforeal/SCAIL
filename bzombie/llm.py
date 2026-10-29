"""Claude print-mode wrapper for the bench: simulated him, env writer, profile builder, judges.

Hidden fresh process per call, no tools, no session saved, prompt on stdin. Billed to API credits only (meta terms
10-22 17:14): a call needs `session` (set by the driver or the probe; holds the credits reservation). The reservation's
key goes only into the child env as ANTHROPIC_API_KEY. No session means no call; there is no subscription fallback.
Command line (checked against claude --help by the orchestrator):
  claude -p --model claude-sonnet-5-5 --output-format json --tools "" --no-session-persistence
         --setting-sources "" --strict-mcp-config --disable-slash-commands --system-prompt <text>
Each call appends one line to runs/<run_id>/claude_calls.jsonl (field billing: credits|queue).
Queue billing (User 10-22 17:23): once the one-time grant is used up, calls go to the bench worker session through
var/bzombie/claude_queue/ (see _queue and bzombie/worker/README.md). Run config `claude_billing`: "auto" (credits first,
queue after GrantExhausted at reserve or mid-run), "credits", "queue".
Tests swap `backend` for a stub (no process) or `_run` (fake subprocess.run); BZ_LLM_STUB=1 uses the canned backend.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
import uuid
from pathlib import Path

from . import common, credits
from .common import HIDE, TEMP_DIR, VAR, append_jsonl, hidden_env, read_json, write_json

MODEL = "claude-sonnet-5-5"  # pinned id, never an alias
CLAUDE_CMD = ["claude", "-p", "--model", MODEL, "--output-format", "json", "--tools", "",
              "--no-session-persistence", "--setting-sources", "", "--strict-mcp-config",
              "--disable-slash-commands"]
TASK_NAMES = {"him": "sim_him", "env": "env", "profile": "profile", "judge": "judge"}
last_wall_s = 0.0
backend = None  # callable(task, system, prompt) -> str ; None = real claude
session = None  # Session while a run or probe is live
_run = subprocess.run
STAMP = re.compile(r"^[ \t]*(?:\[[A-Za-z]{2,4}\.? \d{1,2}:\d{2}\][ \t]*)+", re.M)


class CapReached(RuntimeError):
    """The run's claude_cap_usd is spent; the driver pauses the run."""


class QueueUnavailable(Exception):
    """The queue path cannot answer: reason is worker_down or worker_timeout; the driver pauses the run with it."""

    def __init__(self, reason, msg=""):
        super().__init__(msg or reason)
        self.reason = reason


POLL_S = 1.0  # answer-file poll interval (tests shorten it)
WORKER_STALE_S = 600  # heartbeat older than this when a request is written: worker_down


def queue_dir() -> Path:
    return VAR / "claude_queue"


class Session:
    """What a real claude call needs: the credits reservation, the run folder for the call log, a clock reader.
    billing: credits | queue | auto. `mode` is where calls go right now (auto starts on credits, switches once)."""

    def __init__(self, reservation, rd, cap_usd: float, billing: str = "credits", queue_timeout_s: float = 900):
        self.reservation, self.rd, self.cap_usd = reservation, rd, float(cap_usd)
        self.billing, self.queue_timeout_s = billing, float(queue_timeout_s)
        self.mode = "queue" if billing == "queue" else "credits"
        self.calls = []  # in-memory copy of the log lines (probe reads it)

    def virtual_ts(self):
        c = read_json(self.rd / "clock.json") if self.rd else None
        return (c or {}).get("virtual_ts")


def strip_stamps(text: str) -> str:
    """Remove leading [Ddd hh:mm] stamps from the text and from each of its lines."""
    return STAMP.sub("", text or "").strip()


def parse_output(stdout: str) -> dict:
    """Parse claude's --output-format json: text from `result`, cost from `total_cost_usd`."""
    try:
        d = json.loads(stdout)
    except ValueError:
        raise RuntimeError("claude printed no JSON: " + (stdout or "")[:200])
    if not isinstance(d, dict):
        raise RuntimeError("claude JSON is not an object")
    return {"text": str(d.get("result") or ""), "cost_usd": float(d.get("total_cost_usd") or 0),
            "duration_ms": d.get("duration_ms"), "is_error": bool(d.get("is_error"))}


def _log(s: Session, task: str, prompt: str, r: dict, billing: str = "credits"):
    rec = {"wall_ts": time.time(), "virtual_ts": s.virtual_ts(), "task": TASK_NAMES.get(task, task),
           "cost_usd": r["cost_usd"], "duration_ms": r["duration_ms"], "is_error": r["is_error"],
           "billing": billing, "prompt_head": prompt[:200], "text_head": r["text"][:200]}
    if r.get("agent_model"):
        rec["agent_model"] = r["agent_model"]
    s.calls.append(rec)
    if s.rd:
        append_jsonl(s.rd / "claude_calls.jsonl", rec)


def _real(task: str, system: str, prompt: str, timeout: float = 300) -> str:
    s = session
    if s is None:
        raise RuntimeError("no claude session: calls are billed to API credits or the bench queue only")
    if s.mode == "queue":
        return _queue(s, task, system, prompt)
    try:
        return _credits(s, task, system, prompt, timeout)
    except credits.GrantExhausted:
        if s.billing != "auto":
            raise
        # grant used up mid-run: settle what was spent, move the live session to the queue, redo this call there
        try:
            if s.reservation is not None:
                s.reservation.settle()
        except credits.CreditsRefused:
            pass  # the driver's close_credits retries and records settle_error
        s.mode = "queue"
        return _queue(s, task, system, prompt)


def _heartbeat_age() -> float:
    """Seconds since the worker last wrote worker.json; inf when missing or unreadable."""
    w = read_json(queue_dir() / "worker.json")
    t = (w or {}).get("last_seen_wall")
    if isinstance(t, str):
        try:
            from datetime import datetime
            t = datetime.fromisoformat(t).timestamp()
        except ValueError:
            t = None
    return time.time() - float(t) if isinstance(t, (int, float)) else float("inf")


def _queue(s: Session, task: str, system: str, prompt: str) -> str:
    """Write <req_id>.req.json (tmp then rename), poll for <req_id>.ans.json, move both to done/. One fresh agent per
    request is the worker's job. worker_down if the heartbeat is stale at write time, worker_timeout if no answer."""
    global last_wall_s
    q = queue_dir()
    (q / "done").mkdir(parents=True, exist_ok=True)
    age = _heartbeat_age()
    if age > WORKER_STALE_S:
        seen = "missing" if age == float("inf") else f"{int(age)} s old"
        raise QueueUnavailable("worker_down", f"bench worker heartbeat {seen} (limit {WORKER_STALE_S} s)")
    rid = uuid.uuid4().hex[:16]
    req_p, ans_p = q / f"{rid}.req.json", q / f"{rid}.ans.json"
    t0 = time.time()
    tmp = q / f"{rid}.req.tmp"
    write_json(tmp, {"req_id": rid, "task": TASK_NAMES.get(task, task), "model": "sonnet", "system": system,
                     "prompt": prompt, "run_id": s.rd.name if s.rd else None, "virtual_ts": s.virtual_ts(),
                     "created_wall": t0, "fresh": True})
    os.replace(tmp, req_p)
    ans = None
    while True:
        if ans_p.exists():
            try:
                ans = json.loads(ans_p.read_text(encoding="utf-8"))
                break
            except (ValueError, OSError):
                pass  # half-written, or the worker's rename holds it (Windows PermissionError); read again next poll
        if time.time() - t0 > s.queue_timeout_s:
            try:
                os.replace(req_p, q / "done" / f"{rid}.req.json.timeout")
            except OSError:
                pass
            raise QueueUnavailable("worker_timeout", f"no answer to {rid} in {int(s.queue_timeout_s)} s")
        time.sleep(POLL_S)
    last_wall_s = time.time() - t0
    for p in (req_p, ans_p):
        try:
            common.replace_retry(p, q / "done" / p.name)
        except OSError:
            pass
    text = str(ans.get("text") or "")
    err = bool(ans.get("is_error"))
    _log(s, task, prompt, {"text": text, "cost_usd": 0.0, "duration_ms": int(last_wall_s * 1000), "is_error": err,
                           "agent_model": ans.get("agent_model")}, billing="queue")
    if err:
        raise RuntimeError("bench worker reported an error: " + str(ans.get("error") or text)[:300])
    return text


def _credits(s: Session, task: str, system: str, prompt: str, timeout: float = 300) -> str:
    global last_wall_s
    if s.reservation is None or not s.reservation.id:
        raise RuntimeError("no credits session: claude calls are billed to API credits only")
    if s.reservation.spent_usd >= s.cap_usd:
        raise CapReached(f"claude cap ${s.cap_usd} spent (${s.reservation.spent_usd:.4f})")
    cmd = list(CLAUDE_CMD) + ["--system-prompt", system]
    cwd = os.path.join(TEMP_DIR, "bz_claude")
    os.makedirs(cwd, exist_ok=True)
    env = s.reservation.child_env(hidden_env())  # key + anthropic-workspace-id header, child env only
    t0 = time.time()
    p = _run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8", timeout=timeout,
             creationflags=HIDE, cwd=cwd, env=env)
    last_wall_s = time.time() - t0
    if p.returncode != 0:
        _log(s, task, prompt, {"text": "", "cost_usd": 0.0, "duration_ms": int(last_wall_s * 1000), "is_error": True})
        # stderr can hold only a warning (e.g. connectors disabled under an API key); the error is in stdout's JSON
        try:
            why = parse_output(p.stdout)["text"]
        except RuntimeError:
            why = (p.stdout or "")[:400]
        msg = s.reservation.scrub(f"claude -p exit {p.returncode}: {why[:400]} | stderr: {(p.stderr or '')[:200]}")
        if credits.exhausted(why):
            raise credits.GrantExhausted(msg)
        raise RuntimeError(msg)
    try:
        r = parse_output(p.stdout)
    except RuntimeError as e:
        raise RuntimeError(s.reservation.scrub(str(e)))
    s.reservation.add(r["cost_usd"])
    _log(s, task, prompt, r)
    if r["is_error"]:
        raise RuntimeError(s.reservation.scrub("claude reported an error: " + r["text"][:300]))
    return r["text"]


def ask(task: str, system: str, prompt: str, timeout: float = 300) -> str:
    if backend is not None:
        return backend(task, system, prompt)
    if os.environ.get("BZ_LLM_STUB") == "1":
        return canned(task, system, prompt)
    return _real(task, system, prompt, timeout)


def extract_json(text: str):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except ValueError:
        pass
    a, b = text.find("{"), text.rfind("}")
    if a >= 0 and b > a:
        return json.loads(text[a:b + 1])
    raise ValueError("no JSON object in model output: " + text[:200])


def ask_json(task: str, system: str, prompt: str, retries: int = 1, timeout: float = 300):
    last = None
    for _ in range(retries + 1):
        try:
            return extract_json(ask(task, system, prompt, timeout))
        except ValueError as e:
            last = e
    raise last


def canned(task: str, system: str, prompt: str) -> str:
    """Deterministic stand-in used by tests."""
    if task == "him":
        m = re.search(r"NOW: (\S+)", prompt)
        now = m.group(1) if m else "2026-01-01T00:00:00"
        n = int(re.search(r"TODAY_ME: (\d+)", prompt).group(1))
        conv = prompt.split("CONVERSATION:")[-1].strip().splitlines()
        last_is_me = bool(conv) and conv[-1].startswith("me:")
        if n < 3 and not last_is_me:
            return json.dumps({"write": True, "text": f"stub message {n}", "next_look": None})
        return json.dumps({"write": False, "text": "", "next_look": _plus(now, 90)})
    if task == "env":
        d = re.search(r"DAY: (\d{4}-\d{2}-\d{2})", prompt).group(1)
        kind = "pc" if "KIND: pc" in prompt else "world"
        return json.dumps({"events": [
            {"ts": f"{d}T09:00:00", "kind": kind, "text": "stub event morning"},
            {"ts": f"{d}T18:00:00", "kind": kind, "text": "stub event evening"}],
            "him_plan": "stub plan: busy during the day, free after 19:00",
            "world_state": "stub world state"})
    if task == "profile":
        return json.dumps({"voice": "stub", "length": "short", "topics": [], "habits": [], "timing": "evenings"})
    return "{}"


def _plus(iso_s: str, minutes: int) -> str:
    from datetime import datetime, timedelta
    return (datetime.fromisoformat(iso_s) + timedelta(minutes=minutes)).isoformat(timespec="seconds")
