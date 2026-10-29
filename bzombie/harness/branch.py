"""Branch-and-replay for removal tests.

From a named snapshot of a base run: restore, apply one inject target, replay his next message(s) from the base
transcript, store the branch beside the base in runs/<run_id>/branches/<branch_id>/ (branch.json, transcript.jsonl,
calls.jsonl, traces/). The gateway and arm work in a scratch run folder runs/_br_<branch_id> (config.json for the
model, snapshots); the viewer ignores folders starting with an underscore.
"""
from __future__ import annotations

import re
import shutil
from datetime import datetime, timedelta

from ..common import ARM_BASE_PORT, VAR, iso, parse_ts, read_json, read_jsonl, run_dir, write_json
from .armclient import ArmError
from . import script as hscript
from .driver import Pause, Session, free_port, load_config, ticket, touch_config


def _load_bench_seed():
    """bzombie/arms/s is not a package (the arm runs as a script): load bench_seed.py by its path."""
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / "arms" / "s" / "bench_seed.py"
    spec = importlib.util.spec_from_file_location("bz_bench_seed", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bench_seed = _load_bench_seed()


def _safe(s, n: int = 24) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", str(s)).strip("-")[:n] or "x"


# variants that are config overlays (bzombie/arms/s/overlays/<name>.json, inject target overlay.<name>), not bz switches
# tagcfg is empty: the config as it is (energy and anxiety tags since master 4d9bf99), with its own fresh noops so a
# run on today's config is never compared with noops replayed on an older one
# lonely2: a loneliness felt tag at 60 without the ずるい/ひとりじめ half that hurt in tags, plus decay_slow's 0.5/h;
# aff_slow: affection_from.inertia_per_hour 0.25 (live 6, decay_slow 1.5) so a set affection is not pulled back to target
# appraisal fixes (tk-z1q): lonehold = state.loneliness_hold_when_silent on; midtags = felt tags at anxiety 45, anger 12,
# boredom 36, energy 52 or below (each carries the full tag list of its gauge, lists replace); appraisal = both
# affpath (tk-z1q) = appraisal + affection.on_message: his fresh messages are read after her reply (4 min cooldown, step
# 1.0 h = 6 points per read), so a warm scene reaches the affection target
OVERLAY_VARIANTS = ("tags", "decay_slow", "tagcfg", "lonely2", "aff_slow", "appraisal", "midtags", "lonehold",
                    "affpath", "gain", "held", "held2", "feltcarry", "held3", "held4", "held5", "held6", "held7", "admbase")
# held7: held6 + felt_carry_cause_held (a held carry clears only when the state call, given the held text, answers
# carry_resolved true, or at the 1440 min cap; relief, a gauge drop and a warm message no longer clear it)
# admbase (10-27): no overlay keys; the admitted baseline under the seed default, with its own branch ids so it never
# resumes an old stranger-mode baseline branch as finished
# stranger (tk-xhv): the off switch of the bench default. Every S-arm branch save is seeded with his live relationship
# primitives (bzombie/arms/s/seeds/primitives_him.json, applied by the arm's seed.him inject) so he is admitted;
# --variant stranger leaves the save as the base run left it (predictability_hers 0.0), for results of before the
# default. It is a branch-id part like any variant, and branch.json carries "seed" (absent = stranger mode).
NO_SEED_VARIANT = "stranger"
# feltcarry: state.felt_carry_minutes 60 only; held3: held2 + felt carry (the state call's reasons for a notable
# update stay in her mood line as text for 60 min)
# held4: held3 + felt_carry_hold_until_resolved (a sadness or anxiety carry stays past 60 min until a later call lowers
# that gauge by 5 or his message reads warm / about her; cap 1440 min) + silence_call_minutes 90 (one state update on
# a silence event 90 min after her last line, once per span, re-armed by his next message)
# held5: held4 + felt_carry_rule "sum" (an update is the carry when its summed |delta| over the feeling gauges +
# validation_craving + unsaid is 10 or more; held when the summed raises of sadness, anxiety, anger, loneliness,
# validation_craving, unsaid are 10 or more; a net drop of 10 on those resolves it; held updates join into one thread)
# held6: held5 + felt_carry_show (while a hurt, worry or sulk carry is held, her mood line also says how that feeling
# shows in her: the line comes from her bundle, characters/momoka/fills.json felt_carry_show; behaviour, not a line)
# held2: held + primitives.admit_needs_predictability 0 (bench saves never admit him, so no rupture could open)
# held: gain + rupture.min_score 5 (a hurt from him can open a held, named grievance) + loneliness_per_silent_hour 4
# gain (tk-z1q 10-25): affpath + state.max_delta_per_update 30 + the state role on prompts/state_gain.txt (events aimed
# at her move a gauge 10 to 25; silence after she reached out raises loneliness and anxiety clearly)


def branch_id(snapshot: str, target: str, value, tag: str = "") -> str:
    """<snapshot>_<target>_<value>, plus _<tag> for a replicate (two noops from one snapshot). A multi-pin value (an
    object) is written out in full up to 48 characters so two multi targets do not share an id."""
    v = _safe(" ".join(f"{k}-{x}" for k, x in value.items()), 48) if isinstance(value, dict) else _safe(value)
    # tag up to 64 characters (was 24): a scene tag with a variant in front ("tagcfg-sc-absence-control-r1") must not be
    # cut so that r1 and r2 share an id. No existing branch id has a tag over 22 characters, so none changes.
    return f"{_safe(snapshot)}_{_safe(target)}_{v}" + (f"_{_safe(tag, 64)}" if tag else "")


def full_tag(variants=(), tag: str = "") -> str:
    """The id suffix of a branch: the bz variant switches on it (`order+trend`), then the replicate tag. Two branches
    that differ only by variant must not share an id."""
    return "_".join(x for x in ("+".join(variants), tag) if x)


def is_finished(run_id: str, bid: str) -> bool:
    """A branch is done when branch.json carries the finished mark (written at the end of branch())."""
    meta = read_json(run_dir(run_id) / "branches" / bid / "branch.json")
    return bool(meta and meta.get("finished"))


def seeds_save(cfg: dict, variants) -> bool:
    """True when this branch's save gets his live primitives: the S arm (the P arm has no such save) and not the
    stranger variant."""
    return cfg.get("arm") == "S" and NO_SEED_VARIANT not in tuple(variants)


def swap_s_root(cfg: dict, s_root: str | None) -> dict:
    """Copy of cfg whose arm_cmd runs the arm from s_root (the value after --s-root). The base run's config is
    untouched: a branch of an older run can run the arm from a tree that has the new inject targets."""
    if not s_root:
        return cfg
    cmd = list(cfg.get("arm_cmd") or [])
    if "--s-root" not in cmd:
        raise ValueError("arm_cmd has no --s-root to swap")
    cmd[cmd.index("--s-root") + 1] = s_root
    return {**cfg, "arm_cmd": cmd}


def branch(run_id: str, snapshot: str, target: str, value, n_msgs: int = 1, window_min: int = 30,
           script_from: str | None = None, s_root: str | None = None, tag: str = "", variants=()) -> str:
    """His lines come from a script: by default the parent run's own transcript (tk-mz5), so base and branch see
    identical him lines. script_from overrides it (a run id of the same character, or a JSONL path). The branch
    delivers the first n_msgs scripted lines at or after the snapshot's cursor, then every scripted line up to
    window_min after the last of those (a second line of his inside the window is delivered too). s_root runs the
    arm from that tree (the base config's arm_cmd names an older worktree). tag is a replicate suffix of the
    branch id. branch.json gets finished: true when the branch ran to its end (the batch resumes on it).
    variants: bz switches (order, trend, ...) turned on after the main inject, so a variant combines with any target
    (a gauge hold, a removal, noop); they are part of the branch id. value of a hold.<gauge> target pins the gauge
    (bzombie/arms/s/control.py PinnedGauges)."""
    variants = tuple(variants)
    tag = full_tag(variants, tag)
    base = run_dir(run_id)
    cfg = swap_s_root(load_config(base / "config.json"), s_root)
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
    bid = branch_id(snapshot, target, value, tag)
    bdir = base / "branches" / bid
    scratch_id = f"_br_{run_id}_{bid}"
    if (bdir / "branch.json").exists():
        if is_finished(run_id, bid):
            raise ValueError(f"branch {bid} exists")
        # a crashed earlier try: park it (never deleted) and start clean
        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        bdir.rename(base / "branches" / f"_partial_{bid}_{stamp}")
        if run_dir(scratch_id).exists():
            run_dir(scratch_id).rename(run_dir(f"{scratch_id}_partial_{stamp}"))
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
            "base_him_via": cfg.get("him_via"), "n_msgs": n_msgs, "window_min": window_min,
            "tag": tag, "s_root": s_root, "variants": list(variants)}
    seeded = seeds_save(cfg, variants)
    if seeded:
        meta["seed"] = bench_seed.seed_tag()
    write_json(bdir / "branch.json", meta)

    port = free_port(ARM_BASE_PORT[cfg["arm"]])
    sess = Session(bcfg, port=port, out=bdir)
    sess.env_seen = set()
    try:
        with ticket(bcfg):
            sess.ensure_arm()
            sess.start_arm()
            sess.arm.restore(snapshot)
            # config overlays first: they rebuild the App over the restored save, which would drop a bz switch
            for v in variants:
                if v in OVERLAY_VARIANTS:
                    sess.arm.inject(f"overlay.{v}", True)
            if seeded:   # after the overlays (a restore would lose it), before the target
                sess.arm.inject("seed.him", True)
            sess.arm.inject(target, value)
            for v in variants:
                if v not in OVERLAY_VARIANTS and v != NO_SEED_VARIANT:
                    sess.arm.inject(f"bz.{v}", True)
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
    write_json(bdir / "branch.json", {**meta, "finished": True, "finished_wall": iso(datetime.now())})
    return bid
