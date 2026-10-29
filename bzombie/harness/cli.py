"""python -m bzombie.harness run <config> | status | pause <run> | resume <run>
| branch <run> <snapshot> <target> <value> [--script-from <run|jsonl>] [--n-msgs N] [--window-min M] [--s-root P] [--tag T]
|   (his lines: the parent's own, by default; N lines then M minutes; --s-root runs the arm from that tree; --tag = replicate)
|   (--variant order,trend turns bz switches on after the inject; target hold.<gauge> pins a gauge at <value>)
|   (every S-arm branch save gets his live primitives, admitted (tk-xhv); --stranger or --variant stranger turns it off)
| inject_batch [--dry] [--variant order,trend] [--only a,b] ...   (the steer test: hold one gauge, replay his lines)
| inject_summary <out.json> [--judge]   (per gauge: the share of cells where the injected side reads more X)
| scene_batch [--dry] [--parallel N] [--variant tagcfg] [--only a,b]   (tk-z1q: scripted scenes, trigger v control, no injection)
| scene_summary <out.json> [--judge]   (probe-only judge, gauge trace, appraisal v expression split)
| removal_batch [--dry] [--parallel N] [--n-msgs N] [--s-root P] [--only a,b]   (the removal-test batch, resumable)
| removal_summary <out.json> [--judge]   (per target: changed beyond noop drift or not)
| new --like <run> --run-id <id> [--s-root P] [--seed N] [--script-from <run|jsonl>] [--run|--fg]
| script_probes <ref_run|jsonl> <out.jsonl> [--clock-start T] [--days N]   (his lines plus four probes a day, for --script-from)
| probe --character momoka|tomoe [--cap-usd N]   (real claude calls via credits; orchestrator launches it hidden)

run and resume start a hidden detached driver process (use --fg to run in this process). The viewer is another
agent's part (contract: Viewer); this CLI does not start it.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

from ..common import GATEWAY, VAR, read_json, run_dir, spawn_hidden
from . import branch as branch_mod
from . import driver


def _spawn_driver(run_id: str):
    rd = run_dir(run_id)
    (rd / "logs").mkdir(parents=True, exist_ok=True)
    p = spawn_hidden([sys.executable, "-m", "bzombie.harness", "_drive", run_id], rd / "logs" / "driver.log",
                     cwd=str(driver.REPO))
    print(f"driver started for {run_id}, pid {p.pid}, log {rd / 'logs' / 'driver.log'}")


def cmd_run(args):
    fg = "--fg" in args
    args = [a for a in args if a != "--fg"]
    cfg = driver.load_config(args[0])
    driver.init_run(cfg)
    if fg:
        driver.drive(cfg["run_id"])
        print(read_json(run_dir(cfg["run_id"]) / "state.json"))
    else:
        _spawn_driver(cfg["run_id"])


TEMPLATES = Path(__file__).resolve().parent / "templates"


RUNTIME_KEYS = ("status", "started_wall", "updated_wall", "arm_port", "peer_ports", "stub", "branch_of", "him_script")


def like_config(like: str, run_id: str, s_root=None, seed=None, sim_days=None, script_from=None) -> dict:
    """Config of an existing run as the base of a new one (tk-mz5). Runtime keys are dropped. --s-root swaps the
    value after "--s-root" in arm_cmd (a real list, never a bash-quoted string), --seed and --sim-days are ints,
    --script-from sets him_via script and him_script (character checked now; a different seed than the
    reference's is allowed but prints a warning: the env script is keyed by character and seed)."""
    src = read_json(run_dir(like) / "config.json")
    if not src:
        sys.exit(f"no run {like}")
    cfg = {k: v for k, v in src.items() if k not in RUNTIME_KEYS}
    cfg["run_id"] = run_id
    if s_root:
        cmd = list(cfg.get("arm_cmd") or [])
        if "--s-root" not in cmd:
            sys.exit(f"run {like} has no --s-root in arm_cmd; use --set arm_cmd=<json list>")
        cmd[cmd.index("--s-root") + 1] = s_root
        cfg["arm_cmd"] = cmd
    if seed is not None:
        cfg["seed"] = int(seed)
    if sim_days is not None:
        cfg["sim_days"] = int(sim_days)
    if script_from:
        cfg["him_via"], cfg["him_script"] = "script", script_from
        ref = read_json(run_dir(script_from) / "config.json") if not Path(script_from).is_file() else None
        if ref and ref.get("seed") != cfg.get("seed"):
            print(f"warning: seed {cfg.get('seed')} differs from the reference's {ref.get('seed')}: "
                  "the env script differs too (env is keyed by character and seed)")
    return cfg


def cmd_new(args):
    """new --template s_momoka | --like <run> --run-id <id> [--s-root P] [--seed N] [--script-from R] [--set key=json ...]
    [--run | --fg]: create the run folder from a template or from an existing run's config."""
    def opt(name, default=None):
        return args[args.index(name) + 1] if name in args else default
    tpl, run_id, like = opt("--template"), opt("--run-id"), opt("--like")
    if (not tpl and not like) or not run_id:
        sys.exit("usage: new --template <name> | --like <run_id> --run-id <id> [--s-root <path>] [--seed N] "
                 "[--sim-days N] [--script-from <run_id|jsonl>] [--set key=json] [--run|--fg]; templates: "
                 + ", ".join(sorted(p.stem for p in TEMPLATES.glob("*.json"))))
    if like:
        cfg = like_config(like, run_id, s_root=opt("--s-root"), seed=opt("--seed"), sim_days=opt("--sim-days"),
                          script_from=opt("--script-from"))
    else:
        cfg = json.loads((TEMPLATES / f"{tpl}.json").read_text(encoding="utf-8"))
    cfg["run_id"] = run_id
    for i, a in enumerate(args):
        if a == "--set":
            k, v = args[i + 1].split("=", 1)
            try:
                v = json.loads(v)
            except ValueError:
                pass
            cfg[k] = v
    cfg = driver.load_config(cfg)
    rd = driver.init_run(cfg)
    print("run created:", rd)
    if "--fg" in args:
        driver.drive(run_id)
        print(read_json(rd / "state.json"))
    elif "--run" in args:
        _spawn_driver(run_id)


def cmd_resume(args):
    fg = "--fg" in args
    run_id = [a for a in args if a != "--fg"][0]
    st = read_json(run_dir(run_id) / "state.json")
    if not st:
        sys.exit(f"no run {run_id}")
    if st.get("status") == "running" and _alive(st.get("pid")):
        sys.exit("run is live; pause it first")
    if fg:
        driver.drive(run_id)
        print(read_json(run_dir(run_id) / "state.json"))
    else:
        _spawn_driver(run_id)


def _alive(pid) -> bool:
    if not pid:
        return False
    try:
        import ctypes
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))
        if not h:
            return False
        ctypes.windll.kernel32.CloseHandle(h)
        return True
    except Exception:
        return False


def cmd_pause(args):
    rd = run_dir(args[0])
    (rd / "pause.flag").write_text("1")
    print("pause flag set; the driver stops at its next step, stops the arm and frees its ticket")


def cmd_status(args):
    spend = {}
    try:
        with urllib.request.urlopen(GATEWAY + "/status", timeout=2) as r:
            g = json.loads(r.read())
        spend = g.get("runs", {}) if isinstance(g.get("runs"), dict) else {}
        print("gateway: up" + (f", balance {g['balance_usd']}" if "balance_usd" in g else ""))
    except Exception:
        print("gateway: not reachable")
    d = VAR / "runs"
    for p in sorted(d.iterdir()) if d.exists() else []:
        st = read_json(p / "state.json")
        if not st or p.name.startswith("_"):
            continue
        c = read_json(p / "config.json") or {}
        sp = (spend.get(p.name) or {}).get("spend_usd")
        print(f"{p.name}: {st.get('status')} {c.get('arm')} {c.get('character')} day {st.get('day')}/{c.get('sim_days')} "
              f"at {st.get('cursor')} spend {sp if sp is not None else '?'}/{c.get('cap_usd')}"
              + (f" reason {st.get('reason')}" if st.get("reason") else ""))


def cmd_branch(args):
    """branch <run> <snapshot> <target> <value> [--script-from R] [--n-msgs N] [--window-min M] [--s-root P] [--tag T] [--stranger]"""
    opts = ("--script-from", "--n-msgs", "--window-min", "--s-root", "--tag", "--variant")
    stranger = "--stranger" in args   # same as --variant stranger: no his-primitives seed (tk-xhv)
    args = [x for x in args if x != "--stranger"]

    def opt(name, default=None):
        return args[args.index(name) + 1] if name in args else default
    pos = [a for i, a in enumerate(args) if a not in opts and (i == 0 or args[i - 1] not in opts)]
    if len(pos) < 4:
        sys.exit("usage: branch <run> <snapshot> <target> <value> [--script-from <run|jsonl>] [--n-msgs N] "
                 "[--window-min M] [--s-root P] [--tag T]")
    run_id, snap, target, value = pos[:4]
    try:
        value = json.loads(value)
    except ValueError:
        pass
    bid = branch_mod.branch(run_id, snap, target, value, n_msgs=int(opt("--n-msgs", 1)),
                            window_min=int(opt("--window-min", 30)), script_from=opt("--script-from"),
                            s_root=opt("--s-root"), tag=opt("--tag", ""),
                            variants=[v for v in opt("--variant", "").split(",") if v] + (["stranger"] if stranger else []))
    print("branch", bid, "stored in", run_dir(run_id) / "branches" / bid)


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    if not a:
        print(__doc__)
        return
    cmd, rest = a[0], a[1:]
    if cmd == "_drive":
        driver.drive(rest[0])
        return
    if cmd == "script_probes":
        from . import script_probes
        script_probes.main(rest)
        return
    if cmd in ("removal_batch", "removal_summary", "inject_batch", "inject_summary", "scene_batch", "scene_summary"):
        mod = __import__(f"bzombie.harness.{cmd}", fromlist=["main"])
        mod.main(rest)
        return
    if cmd == "probe":
        from . import probe
        ch = rest[rest.index("--character") + 1] if "--character" in rest else ""
        if ch not in ("momoka", "tomoe"):
            sys.exit("usage: probe --character momoka|tomoe [--cap-usd N]")
        cap = float(rest[rest.index("--cap-usd") + 1]) if "--cap-usd" in rest else 2.0
        r = probe.run(ch, cap)
        print("probe written:", r["stamp"], "cost", r["total_cost_usd"], "credits_error", r["credits_error"],
              "errors", [s["step"] for s in r["steps"] if s.get("error")])
        return
    fn = {"run": cmd_run, "new": cmd_new, "status": cmd_status, "pause": cmd_pause, "resume": cmd_resume, "branch": cmd_branch}.get(cmd)
    if not fn:
        print(__doc__)
        sys.exit(2)
    fn(rest)
