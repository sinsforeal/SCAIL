"""Branch-and-replay for removal tests.

From a named snapshot of a base run: restore, apply one inject target, replay his next message(s) from the base
transcript, store the branch beside the base in runs/<run_id>/branches/<branch_id>/ (branch.json, transcript.jsonl,
calls.jsonl, traces/). The gateway and arm work in a scratch run folder runs/_br_<branch_id> (config.json for the
model, snapshots); the viewer ignores folders starting with an underscore.
"""
from __future__ import annotations

import re
import shutil
from datetime import timedelta

from ..common import ARM_BASE_PORT, VAR, iso, parse_ts, read_json, read_jsonl, run_dir, write_json
from .armclient import ArmError
from . import script as hscript
from .driver import Pause, Session, free_port, load_config, ticket, touch_config


def _safe(s) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", str(s)).strip("-")[:24] or "x"


def branch(run_id: str, snapshot: str, target: str, value, n_msgs: int = 1, window_min: int = 30,
           script_from: str | None = None) -> str:
    """His lines come from a script: by default the parent run's own transcript (tk-mz5), so base and branch see
    identical him lines. script_from overrides it (a run id of the same character, or a JSONL path). The branch
    delivers the first n_msgs scripted lines at or after the snapshot's cursor, then every scripted line up to
    window_min after the last of those (a second line of his inside the window is delivered too)."""
    base = run_dir(run_id)
    cfg = load_config(base / "config.json")
    h = read_json(base / "snapshots" / "harness" / f"{snapshot}.json")
    if h is None:
        raise ValueError(f"no harness snapshot {snapshot} in {run_id}")
    base_tr = read_jsonl(base / "transcript.jsonl")
    cursor = parse_ts(h["cursor"])
    source = script_from or run_id
    sc = hscript.load(source, cfg["character"])
    after = [l for l in sc["lines"] if parse_ts(l["virtual_ts"]) >= cursor]
    if not after:
        raise ValueError(f"no message of his after snapshot {snapshot} in script {source}")
    end = parse_ts(after[min(n_msgs, len(after)) - 1]["virtual_ts"]) + timedelta(minutes=window_min)
    msgs = [l for l in after if parse_ts(l["virtual_ts"]) <= end]
    bid = f"{_safe(snapshot)}_{_safe(target)}_{_safe(value)}"
    bdir = base / "branches" / bid
    if (bdir / "branch.json").exists():
        raise ValueError(f"branch {bid} exists")
    scratch_id = f"_br_{run_id}_{bid}"
    bcfg = {**cfg, "run_id": scratch_id, "branch_of": run_id, "status": "running",
            "him_via": "script", "him_script": source}
    srd = run_dir(scratch_id)
    srd.mkdir(parents=True, exist_ok=True)
    write_json(srd / "config.json", bcfg)
    src = base / "snapshots" / cfg["arm"] / snapshot
    if src.exists():
        shutil.copytree(src, srd / "snapshots" / cfg["arm"] / snapshot, dirs_exist_ok=True)
    # prefix of the base transcript and its traces
    bdir.mkdir(parents=True, exist_ok=True)
    prefix = base_tr[:h["transcript_len"]]
    (bdir / "transcript.jsonl").write_text("".join(__import__("json").dumps(r, ensure_ascii=False) + "\n"
                                                  for r in prefix), encoding="utf-8")
    for r in prefix:
        t = base / "traces" / f"{r.get('output_id')}.json"
        if r.get("output_id") and t.exists():
            (bdir / "traces").mkdir(exist_ok=True)
            shutil.copy2(t, bdir / "traces" / t.name)
    meta = {"branch_id": bid, "from_snapshot": snapshot, "target": target, "value": value,
            "replayed_from_virtual_ts": h["cursor"], "him_via": "script", "him_script": source,
            "base_him_via": cfg.get("him_via")}
    write_json(bdir / "branch.json", meta)

    port = free_port(ARM_BASE_PORT[cfg["arm"]])
    sess = Session(bcfg, port=port, out=bdir)
    sess.env_seen = set()
    try:
        with ticket(bcfg):
            sess.ensure_arm()
            sess.start_arm()
            sess.arm.restore(snapshot)
            sess.arm.inject(target, value)
            sess.set_clock(cursor)
            # env events of the base script from the snapshot on
            events = []
            for d in range(sess.sim_day(cursor) - 1, sess.sim_day(end)):
                s = read_json(base / "env" / f"day_{d}.json") or {"events": []}
                events += [e for e in s["events"] if parse_ts(e["ts"]) >= cursor]
            for e in events:
                if parse_ts(e["ts"]) < cursor:
                    sess.env_seen.add(e["ts"] + e["text"])
            if events:
                sess.arm.env(events)
            step = timedelta(seconds=cfg["step_s"])

            def run_to(t):
                nonlocal cursor
                while cursor < t:
                    nxt = min(cursor + step, t)
                    sess.set_clock(nxt)
                    outs = sess.arm.advance(iso(nxt))
                    sess.add_env(events, nxt)
                    sess.collect(outs, branch=True)
                    cursor = nxt

            for m in msgs:
                mt = parse_ts(m["virtual_ts"])
                run_to(mt)
                sess.set_clock(mt)
                sess.arm.send(m["text"], m["virtual_ts"])
                sess.add_line("him", m["virtual_ts"], m["text"], branch=True)
            run_to(end)
            sess.arm.stop()
    except ArmError as e:
        sess.arm.stop()
        raise Pause("budget" if e.budget else "arm_error", str(e))
    # calls of the scratch run belong to the branch
    calls = srd / "calls.jsonl"
    if calls.exists():
        shutil.move(str(calls), str(bdir / "calls.jsonl"))
    return bid
