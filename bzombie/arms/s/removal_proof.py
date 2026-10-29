"""No-spend proof that a removal target is really off (tk-lmv step 2), on the real S arm in process.

    python bzombie/arms/s/removal_proof.py <base_run> <snapshot> <out.json> [--hours N] [--only name,name]

For noop and every target of bzombie/harness/removal_targets.py: copy the base run's snapshot into a scratch runs
root, start the arm against fake_openai (no model, no spend), restore, inject, send his next line from the base
transcript, advance N virtual hours (default 9: past her waking, so morning and diary run) and count the llm roles
that called and the prompt sections (trace input names) of her outputs. A target passes when each of its `roles`
made calls in noop and none in the branch, and each of its `inputs` showed in noop and never in the branch.
A role or input that noop never showed is reported "not exercised": the target is then proven by its config flag only.
Scratch goes to H:\\SCAIL\\temp. Reads the base run, never writes it.
"""
import collections
import json
import os
import shutil
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
os.environ.setdefault("BZ_NO_TICKET", "1")
os.environ.setdefault("TEMP", r"H:\SCAIL\temp")
os.environ.setdefault("TMP", r"H:\SCAIL\temp")

import control  # noqa: E402
import fake_openai  # noqa: E402
from bzombie.common import read_json, read_jsonl, run_dir  # noqa: E402
from bzombie.harness import removal_targets as RT  # noqa: E402

PORT = 18396


def his_lines(base, snapshot, n=2):
    h = read_json(run_dir(base) / "snapshots" / "harness" / f"{snapshot}.json")
    tr = read_jsonl(run_dir(base) / "transcript.jsonl")
    rows = [r for r in tr if r["who"] == "him" and r["virtual_ts"] >= h["cursor"]][:n]
    return h, rows


def one(base, snapshot, tmp, name, target, hours, h, his, cfgb):
    rid = f"proof_{name}"
    runs = os.path.join(tmp, "runs")
    snap = os.path.join(runs, rid, "snapshots", "S", snapshot)
    os.makedirs(os.path.dirname(snap), exist_ok=True)
    shutil.copytree(os.path.join(str(run_dir(base)), "snapshots", "S", snapshot), snap, dirs_exist_ok=True)
    arm = control.Arm()
    arm.runs_root = runs
    t0 = time.time()
    arm.start({"run_id": rid, "character": cfgb["character"], "lang": cfgb["lang"],
               "clock_start": cfgb["clock_start"], "arm_variant": cfgb.get("arm_variant", ""),
               "seed": cfgb.get("seed", 0)})
    arm.restore(snapshot)
    removed = arm.inject(target, False)["removed"] if target != "noop" else []
    if target == "noop":
        arm.inject("noop", None)
    arm.app.config.api.cache_settle_seconds = 0
    ids0 = len(arm.app.llm.call_ids)
    for r in his:
        arm.send(r["text"], control.to_ts(r["virtual_ts"].replace("T", " ")))
    end = control.to_ts(h["cursor"].replace("T", " ")) + hours * 3600
    outs = []
    t = arm.vt
    while t < end:
        t = min(t + 600, end)
        outs += arm.advance(t)["outputs"]
    roles = collections.Counter(c["role"] or "(blank)" for c in arm.app.llm.call_ids[ids0:])
    secs = collections.Counter()
    tdir = os.path.join(runs, rid, "traces")   # send() advances to his time first: read every trace written
    for f in os.listdir(tdir) if os.path.isdir(tdir) else []:
        tr = read_json(os.path.join(tdir, f)) or {}
        for n in {i.get("name") for i in tr.get("inputs", [])}:
            secs[n] += 1
    res = {"target": target, "removed": removed, "roles": dict(roles), "sections": dict(secs),
           "outputs": len(os.listdir(tdir)) if os.path.isdir(tdir) else 0,
           "wall_s": round(time.time() - t0, 1)}
    arm.stop()
    return res


def verdict(res):
    base = res["noop"]
    out = {}
    for t in RT.TARGETS:
        r = res.get(t["name"])
        if not r:
            continue
        miss = []
        for role in t["roles"]:
            if not base["roles"].get(role):
                miss.append(f"role {role}: not exercised")
            elif r["roles"].get(role):
                miss.append(f"role {role}: STILL CALLS ({r['roles'][role]})")
        for sec in t["inputs"]:
            if not base["sections"].get(sec):
                miss.append(f"input {sec}: not exercised")
            elif r["sections"].get(sec):
                miss.append(f"input {sec}: STILL IN PROMPT")
        name, key = control.removal_key(t["target"])
        flag = f"{name}.{key}=False" in r["removed"]
        bad = [m for m in miss if "STILL" in m]
        out[t["name"]] = {"flag_recorded": flag, "pass": flag and not bad, "notes": miss}
    return out


def main(argv):
    base, snapshot, outp = argv[:3]
    hours = float(argv[argv.index("--hours") + 1]) if "--hours" in argv else 9.0
    only = argv[argv.index("--only") + 1].split(",") if "--only" in argv else None
    cfgb = read_json(run_dir(base) / "config.json")
    h, his = his_lines(base, snapshot)
    tmp = tempfile.mkdtemp(dir=r"H:\SCAIL\temp")
    os.environ["BZ_BASE_URL"] = f"http://127.0.0.1:{PORT}/arm/S/{{run_id}}/v1"
    fake = fake_openai.serve(PORT)
    threading.Thread(target=fake.serve_forever, daemon=True).start()
    todo = [("noop", "noop")] + [(t["name"], t["target"]) for t in RT.TARGETS if not only or t["name"] in only]
    res = {}
    for name, target in todo:
        res[name] = one(base, snapshot, tmp, name, target, hours, h, his, cfgb)
        print(name, res[name]["wall_s"], "s", "outputs", res[name]["outputs"], "roles", res[name]["roles"], flush=True)
        with open(outp, "w", encoding="utf-8") as fh:
            json.dump({"results": res, "verdict": verdict(res) if "noop" in res else {}}, fh, ensure_ascii=False, indent=1)
    print(json.dumps(verdict(res), ensure_ascii=False, indent=1))
    fake.shutdown()


if __name__ == "__main__":
    main(sys.argv[1:])
