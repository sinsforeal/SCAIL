"""The scripted-scene batch (tk-z1q, feeding tk-6si and tk-lmv): his behaviour -> her gauge -> her reply, no injection.

python -m bzombie.harness scene_batch [--dry] [--parallel N] [--s-root P] [--variant tagcfg] [--only a,b]
                                      [--bases r1,r2] [--snapshots s1,s2] [--controls K] [--max-fail F]

Plan: base run x snapshot x scene x (one trigger branch + K control branches, default 2). Default 3 x 2 x 6 x 3 = 108
branches. Every branch is a plain `branch <base> <snapshot> noop true --script-from <scene script>` child: no inject,
only his lines differ. The scripts (scenes.py) are written to <var>/scenes/ just before each child starts; they hold
his scene lines and the three probe lines, with the scene's gaps as virtual time. n_msgs is the whole script and the
window is TAIL_MIN after the last probe, so the branch delivers every line. The two controls of a cell run the same
script (the floor: control v control). --variant works as in inject_batch (tagcfg, lonely2, aff_slow, decay_slow, ...)
and goes into every branch id, so scenes on today's config never meet branches of another config. Scene tags are
unique (`sc-<scene>-trigger`, `sc-<scene>-control-r1`), so none collides with a noop or a pin.

Why a module of its own and not inject_batch: the plan axes differ (scene x side, not target), the branch needs a
script file built from the snapshot's cursor, and the window is the script's. It reuses inject_batch's start spacing,
rb's constants and estimate figures, branch.branch and the same child launcher. --dry prints plan, scripts and the
estimate and writes nothing.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from ..common import HIDE, VAR, hidden_env, parse_ts, read_jsonl, run_dir
from . import branch as branch_mod
from . import removal_batch as rb
from . import scenes as sc
from .driver import REPO

BASES = rb.BASES
SNAPSHOTS = rb.SNAPSHOTS
CONTROLS = 2
VARIANTS = ()


def scene_tag(scene: str, side: str, rep: str = "") -> str:
    return f"sc-{scene}-{side}" + (f"-{rep}" if rep else "")


def scene_bid(snapshot: str, scene: str, side: str, rep: str = "", variants=()) -> str:
    """The id the child writes: <snapshot>_noop_True_<variants>_sc-<scene>-<side>[-rK]."""
    return branch_mod.branch_id(snapshot, "noop", True, branch_mod.full_tag(tuple(variants), scene_tag(scene, side, rep)))


def plan(bases=BASES, snapshots=SNAPSHOTS, scenes=None, controls=CONTROLS, variants=VARIANTS) -> list[dict]:
    """The branch list in run order: snapshot, base, scene, then trigger, then the controls. `script` names the file
    the child reads (var/scenes/...); the control reps share one script."""
    scenes = sc.SCENES if scenes is None else scenes
    variants = tuple(variants)
    out = []
    for snap in snapshots:
        for base in bases:
            for s in scenes:
                sides = [("trigger", "")] + [("control", f"r{k + 1}") for k in range(controls)]
                for side, rep in sides:
                    out.append({"base": base, "snapshot": snap, "scene": s["name"], "side": side, "rep": rep,
                                "target": "noop", "value": True, "tag": scene_tag(s["name"], side, rep),
                                "variants": list(variants), "script": str(sc.script_path(VAR, base, snap, s["name"], side)),
                                "bid": scene_bid(snap, s["name"], side, rep, variants)})
    return out


def pending(items: list[dict]) -> list[dict]:
    return [i for i in items if not branch_mod.is_finished(i["base"], i["bid"])]


def rows_of(i: dict):
    """(rows, span) of an item's script, or (None, None) when the base has no such snapshot."""
    cur = sc.snapshot_cursor(i["base"], i["snapshot"])
    if cur is None:
        return None, None
    rows = sc.build_script(sc.BY_NAME[i["scene"]], i["side"], cur)
    return rows, sc.script_span(rows, cur)


def cmd_args(i: dict, n_lines: int, s_root: str) -> list[str]:
    a = [sys.executable, "-m", "bzombie.harness", "branch", i["base"], i["snapshot"], i["target"], json.dumps(i["value"]),
         "--script-from", i["script"], "--n-msgs", str(n_lines), "--window-min", str(sc.TAIL_MIN),
         "--s-root", s_root, "--tag", i["tag"]]
    if i["variants"]:
        a += ["--variant", ",".join(i["variants"])]
    return a


def run_one(i: dict, s_root: str, log_dir) -> int:
    rows, span = rows_of(i)
    if rows is None:
        print(f"{i['base']} {i['bid']}: no snapshot {i['snapshot']}", flush=True)
        return 2
    sc.write_script(rows, i["script"])
    log_dir.mkdir(parents=True, exist_ok=True)
    with open(log_dir / f"{i['base']}__{i['bid']}.log", "ab") as out:
        p = subprocess.Popen(cmd_args(i, span["n_lines"], s_root), stdout=out, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL, creationflags=HIDE, cwd=str(REPO), env=hidden_env(),
                             close_fds=True)
        return p.wait()


def run(items: list[dict], parallel: int, s_root: str, max_fail: int) -> dict:
    log_dir = VAR / "scene_batch"
    state = {"done": 0, "failed": [], "skipped_after_abort": 0}
    lock, gap, last_start = threading.Lock(), threading.Lock(), [0.0]

    def work(i):
        with lock:
            if len(state["failed"]) >= max_fail:
                state["skipped_after_abort"] += 1
                return
        with gap:   # starts are spaced: free_port picks and arm boot must not race
            wait = rb.START_GAP_S - (time.time() - last_start[0])
            if wait > 0:
                time.sleep(wait)
            last_start[0] = time.time()
        rc = run_one(i, s_root, log_dir)
        with lock:
            if rc == 0:
                state["done"] += 1
            else:
                state["failed"].append({"base": i["base"], "bid": i["bid"], "rc": rc})
            print(f"{i['base']} {i['bid']}: rc {rc} ({state['done']} done, {len(state['failed'])} failed)", flush=True)

    with ThreadPoolExecutor(max_workers=max(1, parallel)) as ex:
        list(ex.map(work, items))
    return state


def window_cost(calls: list, cur, end) -> dict:
    """What a base run's own calls cost between cur and end (the same stretch of virtual time the scene branch covers):
    chat and embedding calls, chat latency, booked cost. The scene's lines differ from the base's, so this is a
    proxy for the order of magnitude, not a prediction."""
    chat = emb = lat = micro = 0
    for r in calls:
        t = r.get("virtual_ts")
        if not t or not (cur <= parse_ts(t) <= end):
            continue
        if r.get("endpoint") == "chat/completions":
            chat += 1
            lat += float(r.get("latency_s") or 0)
            micro += int(r.get("cost_micro") or 0)
        else:
            emb += 1
    return {"chat_calls": chat, "embed_calls": emb, "latency_s": round(lat), "cost_usd": micro / 1e6}


def estimate(items: list[dict], parallel: int) -> dict:
    """Calls, cost and wall time of the items: per item the base run's calls between the snapshot cursor and the end of
    the scene (cursor to last probe + tail), wall = chat latency + rb.STARTUP_S per branch over `parallel`. An
    upper bound where the scene is quieter than the base was (an absence trigger sends no lines)."""
    calls_by_base, rows = {}, []
    chat = emb = 0
    lat = usd = 0.0
    spans = {}
    for i in items:
        r, span = rows_of(i)
        if r is None:
            continue
        spans[(i["scene"], i["side"], i["snapshot"], i["base"])] = span
        if i["base"] not in calls_by_base:
            calls_by_base[i["base"]] = read_jsonl(run_dir(i["base"]) / "calls.jsonl")
        c = window_cost(calls_by_base[i["base"]], span["cursor"], span["end"])
        chat += c["chat_calls"]
        emb += c["embed_calls"]
        lat += c["latency_s"] + rb.STARTUP_S
        usd += c["cost_usd"]
        rows.append(c)
    return {"branches": len(items), "estimated": len(rows), "chat_calls": chat, "embed_calls": emb,
            "cost_usd": round(usd, 2), "wall_h_serial": round(lat / 3600, 1),
            "wall_h": round(lat / 3600 / max(1, parallel), 1), "spans": spans,
            "note": "upper bound where a scene sends fewer lines than the base did; the base calls between the "
                    "snapshot cursor and the scene end stand in for the scene's; wall = chat latency + "
                    f"{rb.STARTUP_S} s start per branch over parallel (ignores ticket waits)"}


def scene_lines_report(scenes: list, cursor) -> list[str]:
    """One line per scene and side: lines, probes, span and the gap that carries the trigger."""
    out = []
    for s in scenes:
        for side in sc.SIDES:
            rows = sc.build_script(s, side, cursor)
            sp = sc.script_span(rows, cursor)
            gaps = [parse_ts(b["virtual_ts"]) - parse_ts(a["virtual_ts"]) for a, b in zip(rows, rows[1:])]
            out.append(f"{s['name']} {side}: {len(rows)} lines ({sum(r['probe'] for r in rows)} probes), "
                       f"{sp['first']:%H:%M} to {sp['last']:%H:%M}, probes from {sp['probe_start']:%H:%M}, "
                       f"longest gap {max(gaps)}")
    return out


def main(argv):
    def opt(name, default=None):
        return argv[argv.index(name) + 1] if name in argv else default
    parallel = int(opt("--parallel", 1))
    s_root = opt("--s-root") or str(REPO).replace("\\", "/")
    scenes = sc.select(opt("--only", "").split(","))
    bases = opt("--bases", ",".join(BASES)).split(",")
    snaps = opt("--snapshots", ",".join(SNAPSHOTS)).split(",")
    controls = int(opt("--controls", CONTROLS))
    variants = tuple(v for v in opt("--variant", ",".join(VARIANTS)).split(",") if v)
    items = plan(bases, snaps, scenes, controls, variants)
    todo = pending(items)
    print(f"plan: {len(items)} branches ({len(bases)} bases x {len(snaps)} snapshots x {len(scenes)} scenes x "
          f"(1 trigger + {controls} control)), {len(items) - len(todo)} finished, {len(todo)} to run; "
          f"parallel {parallel}, variants {','.join(variants) or '-'}, s-root {s_root}")
    print("scenes: " + ", ".join(f"{s['name']} ({s['gauge']} {s['gauge_dir']}, {s['direction']})" for s in scenes))
    if "--dry" in argv:
        cur = next((c for c in (sc.snapshot_cursor(b, s) for s in snaps for b in bases) if c), None)
        if cur:
            print("\n".join(scene_lines_report(scenes, cur)))
        e = estimate(todo, parallel)
        print(f"estimate for {e['branches']} branches ({e['estimated']} with a snapshot): {e['chat_calls']} chat calls, "
              f"{e['embed_calls']} embedding calls, about ${e['cost_usd']} as the base runs booked it, wall "
              f"{e['wall_h']} h at parallel {parallel} ({e['wall_h_serial']} h serial)")
        print(e["note"])
        print("first three: " + "; ".join(f"{i['base']} {i['snapshot']} {i['bid']}" for i in todo[:3]))
        return
    st = run(todo, parallel, s_root, int(opt("--max-fail", 3)))
    print(json.dumps(st))
    if st["failed"] or st["skipped_after_abort"]:
        sys.exit(1)
