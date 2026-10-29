"""The removal-test batch (tk-lmv, stage 5): every picked target switched off, plus noops, from two snapshots of
three S-arm base runs.

python -m bzombie.harness removal_batch [--dry] [--parallel N] [--n-msgs N] [--window-min M] [--s-root P]
                                        [--only a,b] [--bases r1,r2] [--snapshots s1,s2] [--noops K] [--max-fail F]

Plan: base run x snapshot x (removal_targets.TARGETS with value false, plus K noop replicates r1..rK). Default
3 x 2 x (11 + 2) = 78 branches of n_msgs 6 (his next six lines, then 30 minutes). Each branch is one
`python -m bzombie.harness branch ...` child (hidden, log in <var>/removal_batch/), so a crash or a budget pause
costs one branch. Resumable: a branch whose branch.json has `finished` is skipped; a crashed one is parked
(`_partial_*`) by branch() and run again. --parallel N children at once, starts 20 s apart (arm ports 18331-18339,
at most 9); the limits ticket each child takes is the real cap. --s-root defaults to this tree (the base configs'
arm_cmd names an older worktree without the removal targets). --dry prints the plan and the estimate, runs nothing.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from ..common import HIDE, VAR, hidden_env, parse_ts, read_json, read_jsonl, run_dir
from . import branch as branch_mod
from . import removal_targets as rt
from .driver import REPO

BASES = ["gr2_b_s3_momoka", "gr2_b_s4_momoka", "gr_b_s5_momoka"]
SNAPSHOTS = ["day1_end", "day2_end"]
N_MSGS = 6
WINDOW_MIN = 30
NOOPS = 2
START_GAP_S = 20
STARTUP_S = 90  # arm boot + restore + ticket, per branch (measured on the proof run: about 40 s boot)


def plan(bases=BASES, snapshots=SNAPSHOTS, targets=None, noops=NOOPS) -> list[dict]:
    """The branch list, in run order: snapshot, then base, then target (noops last)."""
    targets = rt.TARGETS if targets is None else targets
    out = []
    for snap in snapshots:
        for base in bases:
            items = [(t["name"], t["target"], False, "") for t in targets]
            items += [("noop", rt.NOOP, True, f"r{i + 1}") for i in range(noops)]
            for name, target, value, tag in items:
                out.append({"base": base, "snapshot": snap, "name": name, "target": target, "value": value,
                            "tag": tag, "bid": branch_mod.branch_id(snap, target, value, tag)})
    return out


def pending(items: list[dict]) -> list[dict]:
    return [i for i in items if not branch_mod.is_finished(i["base"], i["bid"])]


def window(base: str, snapshot: str, n_msgs: int, window_min: int):
    """(cursor, end) of a branch of base from snapshot: the snapshot's cursor to window_min after the n_msgs-th
    line of his at or after it (the base transcript is the script)."""
    h = read_json(run_dir(base) / "snapshots" / "harness" / f"{snapshot}.json")
    if h is None:
        return None
    cur = parse_ts(h["cursor"])
    him = [parse_ts(r["virtual_ts"]) for r in read_jsonl(run_dir(base) / "transcript.jsonl") if r.get("who") == "him"]
    after = [t for t in him if t >= cur]
    if not after:
        return None
    return cur, after[min(n_msgs, len(after)) - 1] + timedelta(minutes=window_min)


def base_window_cost(base: str, snapshot: str, n_msgs: int, window_min: int) -> dict | None:
    """What the base run itself spent between the snapshot cursor and the branch's end: the call count, the chat
    calls' latency and booked cost over that stretch. A noop branch repeats it; a removal branch spends less."""
    w = window(base, snapshot, n_msgs, window_min)
    if not w:
        return None
    cur, end = w
    chat = emb = lat = micro = 0
    for r in read_jsonl(run_dir(base) / "calls.jsonl"):
        t = r.get("virtual_ts")
        if not t or not (cur <= parse_ts(t) <= end):
            continue
        if r.get("endpoint") == "chat/completions":
            chat += 1
            lat += float(r.get("latency_s") or 0)
            micro += int(r.get("cost_micro") or 0)
        else:
            emb += 1
    return {"cursor": cur.isoformat(timespec="minutes"), "end": end.isoformat(timespec="minutes"),
            "virtual_h": round((end - cur).total_seconds() / 3600, 1), "chat_calls": chat, "embed_calls": emb,
            "latency_s": round(lat), "cost_usd": micro / 1e6}


def estimate(items: list[dict], n_msgs: int, window_min: int, parallel: int) -> dict:
    cache, rows = {}, []
    chat = emb = 0
    lat = 0.0
    usd = 0.0
    for i in items:
        k = (i["base"], i["snapshot"])
        if k not in cache:
            cache[k] = base_window_cost(*k, n_msgs, window_min)
        c = cache[k]
        if not c:
            continue
        chat += c["chat_calls"]
        emb += c["embed_calls"]
        lat += c["latency_s"] + STARTUP_S
        usd += c["cost_usd"]
    return {"branches": len(items), "windows": {f"{b}/{s}": c for (b, s), c in cache.items()},
            "chat_calls": chat, "embed_calls": emb, "cost_usd": round(usd, 2),
            "wall_h_serial": round(lat / 3600, 1), "wall_h": round(lat / 3600 / max(1, parallel), 1),
            "note": "upper bound: a removal branch makes fewer calls than the base did; wall = chat latency + "
                    f"{STARTUP_S} s start per branch, divided by parallel (ignores ticket waits)"}


def cmd_args(i: dict, n_msgs: int, window_min: int, s_root: str) -> list[str]:
    a = [sys.executable, "-m", "bzombie.harness", "branch", i["base"], i["snapshot"], i["target"],
         json.dumps(i["value"]), "--n-msgs", str(n_msgs), "--window-min", str(window_min), "--s-root", s_root]
    if i["tag"]:
        a += ["--tag", i["tag"]]
    return a


def run_one(i: dict, n_msgs: int, window_min: int, s_root: str, log_dir) -> int:
    log_dir.mkdir(parents=True, exist_ok=True)
    with open(log_dir / f"{i['base']}__{i['bid']}.log", "ab") as out:
        p = subprocess.Popen(cmd_args(i, n_msgs, window_min, s_root), stdout=out, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL, creationflags=HIDE, cwd=str(REPO), env=hidden_env(),
                             close_fds=True)
        return p.wait()


def run(items: list[dict], parallel: int, n_msgs: int, window_min: int, s_root: str, max_fail: int) -> dict:
    log_dir = VAR / "removal_batch"
    state = {"done": 0, "failed": [], "skipped_after_abort": 0}
    lock = threading.Lock()
    gap = threading.Lock()
    last_start = [0.0]

    def work(i):
        with lock:
            if len(state["failed"]) >= max_fail:
                state["skipped_after_abort"] += 1
                return
        with gap:  # starts are spaced: free_port picks and arm boot must not race
            wait = START_GAP_S - (time.time() - last_start[0])
            if wait > 0:
                time.sleep(wait)
            last_start[0] = time.time()
        rc = run_one(i, n_msgs, window_min, s_root, log_dir)
        with lock:
            if rc == 0:
                state["done"] += 1
            else:
                state["failed"].append({"base": i["base"], "bid": i["bid"], "rc": rc})
            print(f"{i['base']} {i['bid']}: rc {rc} ({state['done']} done, {len(state['failed'])} failed)", flush=True)

    with ThreadPoolExecutor(max_workers=max(1, parallel)) as ex:
        list(ex.map(work, items))
    return state


def main(argv):
    def opt(name, default=None):
        return argv[argv.index(name) + 1] if name in argv else default
    n_msgs, wmin = int(opt("--n-msgs", N_MSGS)), int(opt("--window-min", WINDOW_MIN))
    parallel = int(opt("--parallel", 1))
    s_root = opt("--s-root") or str(REPO).replace("\\", "/")
    only = set(opt("--only", "").split(",")) - {""}
    targets = [t for t in rt.TARGETS if not only or t["name"] in only]
    bases = opt("--bases", ",".join(BASES)).split(",")
    snaps = opt("--snapshots", ",".join(SNAPSHOTS)).split(",")
    noops = int(opt("--noops", NOOPS))
    items = plan(bases, snaps, targets, noops)
    todo = pending(items)
    print(f"plan: {len(items)} branches ({len(bases)} bases x {len(snaps)} snapshots x "
          f"{len(targets)} targets + {noops} noop), {len(items) - len(todo)} finished, {len(todo)} to run; "
          f"n_msgs {n_msgs}, window {wmin} min, parallel {parallel}, s-root {s_root}")
    print("targets: " + ", ".join(t["name"] for t in targets) + (f", noop x{noops}" if noops else ""))
    if "--dry" in argv:
        e = estimate(todo, n_msgs, wmin, parallel)
        for k, c in e["windows"].items():
            print(f"window {k}: " + (json.dumps(c) if c else "no snapshot or no line of his after it"))
        print(f"estimate for {e['branches']} branches: {e['chat_calls']} chat calls, {e['embed_calls']} embedding "
              f"calls, about ${e['cost_usd']} as the base runs booked it, wall {e['wall_h']} h at parallel "
              f"{parallel} ({e['wall_h_serial']} h serial)")
        print(e["note"])
        print("first three: " + "; ".join(f"{i['base']} {i['snapshot']} {i['target']} {i['value']} {i['tag']}".strip()
                                           for i in todo[:3]))
        return
    st = run(todo, parallel, n_msgs, wmin, s_root, int(opt("--max-fail", 3)))
    print(json.dumps(st))
    if st["failed"] or st["skipped_after_abort"]:
        sys.exit(1)
