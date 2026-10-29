"""Stub arm: the full control API with canned outputs, for harness tests without spending.

python -m bzombie.harness.stub_arm --port 18331 --arm S [--fail-402-at-send N]
Reply to each message 20 virtual s later ("stub reply to: ..."). An env event whose text has "evening" makes her send
an unprompted line. inject target "mute" (value true) silences replies, so a branch differs from its base.
Writes calls.jsonl lines into the run folder like a gateway would (one fake call per output).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import uuid
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ..common import append_jsonl, read_json, run_dir, write_json


class State:
    def __init__(self, arm):
        self.arm = arm
        self.run_id = None
        self.clock = None
        self.pending = []  # (ts, kind, text, inputs)
        self.mute = False
        self.n = 0
        self.sends = 0
        self.traces = {}
        self.fail_at = None
        self.peer = {}        # start body: role, peer_key, peer_contacts
        self.peer_msgs = []   # delivered mail, (id, from, text, ts)
        self.peer_seen = 0
        self.peer_sent = 0
        self.peer_due = []    # (ts, to, text)
        self.opened = False
        self.injects = []     # every (target, value) injected, in order; goes into each trace's state_at_output
        self.seed_him = False  # seed.him (tk-xhv) is save prep, not an experiment inject: kept apart from injects

    def dump(self):
        return {"clock": self.clock.isoformat(), "pending": self.pending, "mute": self.mute, "n": self.n}


S = None
ARGS = None


def rd() -> Path:
    # a run's other minds get their own runs root (BZ_RUNS), as the real S arm does
    return Path(os.environ["BZ_RUNS"]) / S.run_id if os.environ.get("BZ_RUNS") else run_dir(S.run_id)


def epoch(dt: datetime) -> float:
    from zoneinfo import ZoneInfo
    return dt.replace(tzinfo=ZoneInfo("Asia/Tokyo")).timestamp()


def emit(ts, kind, text, inputs):
    S.n += 1
    oid = f"o{S.n:05d}"
    cid = str(uuid.uuid4())
    append_jsonl(rd() / "calls.jsonl", {"call_id": cid, "arm": S.arm, "run_id": S.run_id, "virtual_ts": ts,
                                        "request": {"messages": [{"role": "user", "content": json.dumps(inputs)}]},
                                        "response": {"choices": [{"message": {"content": text}}]},
                                        "cost_micro": 100, "latency_s": 0.01, "error": None})
    S.traces[oid] = {"output_id": oid, "arm": S.arm, "run_id": S.run_id, "virtual_ts": ts, "text": text,
                     "final_call_id": cid, "calls": [{"call_id": cid, "role": "final"}],
                     "inputs": [{"kind": k, "source": s, "text": t} for k, s, t in inputs],
                     "state_at_output": {"mute": S.mute, "injects": list(S.injects), "seed_him": S.seed_him}, "causal": {"stub": True, "n": S.n}}
    return {"output_id": oid, "virtual_ts": ts, "text": text, "kind": kind, "call_ids": [cid]}


def advance(to: datetime):
    outs = []
    due = sorted([p for p in S.pending if datetime.fromisoformat(p[0]) <= to], key=lambda p: p[0])
    S.pending = [p for p in S.pending if p not in due]
    for ts, kind, text, inputs in due:
        if kind == "env":
            if "evening" in text and not S.mute:
                outs.append(emit(ts, "unprompted", f"stub unprompted about: {text}", [("env_event", "env", text)]))
        elif not S.mute:
            outs.append(emit(ts, "reply", f"stub reply to: {text}", [("his_words", "msg", text)]))
    peer_out = []
    if S.peer.get("peer_contacts"):
        c0 = S.peer["peer_contacts"][0]["id"]
        if S.peer.get("role") != "peer" and not S.opened and to.hour >= 9:
            S.opened = True
            S.peer_due.append((to, c0, "stub hello from the first mind"))
        for m in S.peer_msgs:
            if m["id"] > S.peer_seen and S.peer_sent < 3:
                S.peer_seen = m["id"]
                S.peer_sent += 1
                S.peer_due.append((to + timedelta(seconds=30), m["from"], f"stub peer reply to: {m['text'][:40]}"))
        keep = []
        for ts, dest, text in S.peer_due:
            if ts <= to:
                peer_out.append({"to": dest, "text": text, "ts": epoch(ts), "from": S.peer.get("peer_key") or "first",
                                 "name": S.peer.get("peer_key") or "first", "call_ids": []})
            else:
                keep.append((ts, dest, text))
        S.peer_due = keep
    S.clock = to
    S.last_peer_out = peer_out
    return outs


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path == "/control/state":
            return self._send(200, {"stub": True, "clock": S.clock.isoformat() if S.clock else None, "mute": S.mute})
        if self.path.startswith("/control/trace/"):
            t = S.traces.get(self.path.rsplit("/", 1)[1])
            return self._send(200 if t else 404, t or {"error": "no such output"})
        self._send(404, {})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        p = self.path
        if p == "/control/start":
            S.run_id = body["run_id"]
            S.clock = datetime.fromisoformat(body["clock_start"])
            S.pending, S.mute, S.n, S.traces, S.injects = [], False, 0, {}, []
            S.seed_him = False
            S.peer = {k: body[k] for k in ("role", "peer_key", "peer_contacts") if k in body}
            S.peer_msgs, S.peer_seen, S.peer_sent, S.peer_due, S.opened, S.last_peer_out = [], 0, 0, [], False, []
            return self._send(200, {"ok": True})
        if p == "/control/advance":
            outs = advance(datetime.fromisoformat(body["to"]))
            loc = "maid_room" if S.peer.get("role") == "peer" else "house"
            return self._send(200, {"outputs": outs, "peer_out": S.last_peer_out, "place": {"location": loc, "activity": "stub"}})
        if p == "/control/peer_in":
            S.peer_msgs += body["messages"]
            return self._send(200, {"ok": True})
        if p == "/control/send":
            S.sends += 1
            marker = rd() / "stub_fail_done"
            # the planned 402 is for the base run; a branch scratch run (_br_*) has its own folder, no marker
            if ARGS.fail_402_at_send and not str(S.run_id).startswith("_br_") and S.sends == ARGS.fail_402_at_send and not marker.exists():
                marker.write_text("1")
                return self._send(402, {"error": {"type": "budget_exhausted"}})
            ts = datetime.fromisoformat(body["ts"])
            S.pending.append(((ts + timedelta(seconds=20)).isoformat(), "reply", body["text"], []))
            return self._send(200, {"ok": True})
        if p == "/control/env":
            for e in body["events"]:
                S.pending.append((e["ts"], "env", e["text"], []))
            return self._send(200, {"ok": True})
        if p == "/control/snapshot":
            d = rd() / "snapshots" / S.arm / body["name"]
            write_json(d / "state.json", {**S.dump(), "traces": S.traces})
            return self._send(200, {"ok": True})
        if p == "/control/restore":
            d = read_json(rd() / "snapshots" / S.arm / body["name"] / "state.json")
            if not d:
                return self._send(404, {"error": "no snapshot"})
            S.clock = datetime.fromisoformat(d["clock"])
            S.pending = [tuple(x) for x in d["pending"]]
            S.mute, S.n, S.traces = d["mute"], d["n"], d["traces"]
            return self._send(200, {"ok": True})
        if p == "/control/inject":
            t = body["target"]
            if t == "seed.him":
                S.seed_him = bool(body["value"])
                return self._send(200, {"ok": True, "removed": []})
            S.injects.append([t, body["value"]])
            if t == "mute":
                S.mute = bool(body["value"])
            removed = []
            if t.startswith(("section.", "bz_s10.")) and body["value"] is False:
                removed = [t]  # recorded only (like the real arm's answer), no effect on the canned replies
            return self._send(200, {"ok": True, "removed": removed})
        if p == "/control/stop":
            self._send(200, {"ok": True})
            import threading
            threading.Thread(target=SRV.shutdown, daemon=True).start()
            return
        self._send(404, {})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--arm", default="S")
    ap.add_argument("--fail-402-at-send", type=int, default=0)
    ARGS = ap.parse_args()
    S = State(ARGS.arm)
    SRV = ThreadingHTTPServer(("127.0.0.1", ARGS.port), H)
    SRV.serve_forever()
