"""The steer-test batch (tk-6si): one gauge pinned per branch (hold.<gauge>), plus noops, from two snapshots of three
S-arm base runs, his own next lines replayed.

python -m bzombie.harness inject_batch [--dry] [--parallel N] [--n-msgs N] [--window-min M] [--s-root P]
                                       [--variant order] [--only a,b] [--bases r1,r2] [--snapshots s1,s2]
                                       [--noops K] [--max-fail F]

Plan: base run x snapshot x (inject_targets.TARGETS, value from the entry, plus K noop replicates r1..rK). Default
3 x 2 x (6 + 2) = 48 branches of n_msgs 6 (his next six lines, then 30 minutes). Every branch, noops included, runs with
the same --variant switches. Default none: the base runs are plain, and the pin reaches her through the mood line
(`さみしさ とても高い`). `--variant order` drops that line (bz.order), so the pin can only act through other routes
(register, scene, other minds): a second batch that asks whether state steers her without the printed level.
`--variant trend` alone is no use for a pin (trend words name change, a pin has none); with order and trend both on
the mood line is dropped (sim/bz.py mood_line: order wins). Each branch is one
`python -m bzombie.harness branch ...` child (hidden, log in <var>/inject_batch/). Resumable on branch.json `finished`.
The window, the estimate and the start spacing are removal_batch's. --only takes names from inject_targets.ALL
(also loneliness_low, energy_high) or the group alias `decay` (set_loneliness, set_anger, set_affection, set_anxiety:
set.<gauge> sets the gauge once and decay runs, the decay variant of tk-6si). The decay batch runs twice, once per
rate: `--only decay` (live rates) and `--only decay --variant decay_slow` (overlays/decay_slow.json, a quarter of the
live rates); the variant is in the branch id, so the two do not collide. --dry prints the plan and the estimate,
runs nothing.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from ..common import HIDE, VAR, hidden_env
from . import branch as branch_mod
from . import inject_targets as it
from . import removal_batch as rb
from .driver import REPO

BASES = rb.BASES
SNAPSHOTS = rb.SNAPSHOTS
N_MSGS = rb.N_MSGS
WINDOW_MIN = rb.WINDOW_MIN
NOOPS = rb.NOOPS
VARIANTS = ()   # plain: her reply prompt keeps the `いまの気分:` line, which carries the pin (proof: inject_proof.py)


def plan(bases=BASES, snapshots=SNAPSHOTS, targets=None, noops=NOOPS, variants=VARIANTS) -> list[dict]:
    """The branch list, in run order: snapshot, then base, then target (noops last). `tag` is the replicate tag
    handed to the child (the child adds the variants itself); `bid` is the full id the child will write."""
    targets = it.TARGETS if targets is None else targets
    variants = tuple(variants)
    out = []
    for snap in snapshots:
        for base in bases:
            items = [(t["name"], t["target"], t["value"], "", t) for t in targets]
            items += [("noop", it.NOOP, True, f"r{i + 1}", None) for i in range(noops)]
            for name, target, value, tag, t in items:
                out.append({"base": base, "snapshot": snap, "name": name, "target": target, "value": value,
                            "tag": tag, "variants": list(variants), "direction": t["direction"] if t else "",
                            "expect": t["expect"] if t else "",
                            "bid": branch_mod.branch_id(snap, target, value, branch_mod.full_tag(variants, tag))})
    return out


def pending(items: list[dict]) -> list[dict]:
    return [i for i in items if not branch_mod.is_finished(i["base"], i["bid"])]


def cmd_args(i: dict, n_msgs: int, window_min: int, s_root: str) -> list[str]:
    a = [sys.executable, "-m", "bzombie.harness", "branch", i["base"], i["snapshot"], i["target"],
         json.dumps(i["value"]), "--n-msgs", str(n_msgs), "--window-min", str(window_min), "--s-root", s_root]
    if i["tag"]:
        a += ["--tag", i["tag"]]
    if i["variants"]:
        a += ["--variant", ",".join(i["variants"])]
    return a


def run_one(i: dict, n_msgs: int, window_min: int, s_root: str, log_dir) -> int:
    log_dir.mkdir(parents=True, exist_ok=True)
    with open(log_dir / f"{i['base']}__{i['bid']}.log", "ab") as out:
        p = subprocess.Popen(cmd_args(i, n_msgs, window_min, s_root), stdout=out, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL, creationflags=HIDE, cwd=str(REPO), env=hidden_env(),
                             close_fds=True)
        return p.wait()


def run(items: list[dict], parallel: int, n_msgs: int, window_min: int, s_root: str, max_fail: int) -> dict:
    log_dir = VAR / "inject_batch"
    state = {"done": 0, "failed": [], "skipped_after_abort": 0}
    lock = threading.Lock()
    gap = threading.Lock()
    last_start = [0.0]

    def work(i):
        with lock:
            if len(state["failed"]) >= max_fail:
                state["skipped_after_abort"] += 1
                return
        with gap:
            wait = rb.START_GAP_S - (time.time() - last_start[0])
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
    targets = it.select(opt("--only", "").split(","))
    bases = opt("--bases", ",".join(BASES)).split(",")
    snaps = opt("--snapshots", ",".join(SNAPSHOTS)).split(",")
    noops = int(opt("--noops", NOOPS))
    variants = tuple(v for v in opt("--variant", ",".join(VARIANTS)).split(",") if v)
    items = plan(bases, snaps, targets, noops, variants)
    todo = pending(items)
    print(f"plan: {len(items)} branches ({len(bases)} bases x {len(snaps)} snapshots x "
          f"{len(targets)} targets + {noops} noop), {len(items) - len(todo)} finished, {len(todo)} to run; "
          f"n_msgs {n_msgs}, window {wmin} min, parallel {parallel}, variants {','.join(variants) or '-'}, "
          f"s-root {s_root}")
    print("targets: " + ", ".join(f"{t['name']}={t['value']}" for t in targets) + (f", noop x{noops}" if noops else ""))
    if "--dry" in argv:
        e = rb.estimate(todo, n_msgs, wmin, parallel)
        for k, c in e["windows"].items():
            print(f"window {k}: " + (json.dumps(c) if c else "no snapshot or no line of his after it"))
        print(f"estimate for {e['branches']} branches: {e['chat_calls']} chat calls, {e['embed_calls']} embedding "
              f"calls, about ${e['cost_usd']} as the base runs booked it, wall {e['wall_h']} h at parallel "
              f"{parallel} ({e['wall_h_serial']} h serial)")
        print(e["note"])
        print("first three: " + "; ".join(f"{i['base']} {i['snapshot']} {i['target']} {i['value']} {i['bid']}"
                                           for i in todo[:3]))
        return
    st = run(todo, parallel, n_msgs, wmin, s_root, int(opt("--max-fail", 3)))
    print(json.dumps(st))
    if st["failed"] or st["skipped_after_abort"]:
        sys.exit(1)
