"""No-spend proof that a hold.<gauge> pin holds and reaches her reply prompt (tk-6si step 1), real S arm in process.

    python bzombie/arms/s/inject_proof.py <base_run> <snapshot> <out.json> [--hours N] [--only case,case]

Per case: copy the base run's snapshot into a scratch runs root, start the arm against fake_openai (no model, no spend),
restore, inject, send his next two lines, advance N virtual hours in 600 s steps (default 9), then read
  - arm.app.state.gauges for the pinned gauge (must equal the pin after the advance; the noop must have drifted),
  - the `いまの気分:` line of every request fake_openai saw (the state line of her reply prompt): the last one must
    carry the pinned level (とても高い / とても低い) for the pinned gauge in a hold case. Under bz.order the line must be gone.
Cases: noop, hold_loneliness (90), hold_energy (10), hold_loneliness_order (90 + bz.order), release (pin then null).
Scratch goes to H:\\SCAIL\\temp. Reads the base run, never writes it.
"""
import json
import os
import re
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

PORT = 18396
LINE = re.compile(r"いまの気分: ([^\n]*)")

# name, [(inject target, value)], pinned gauge, pinned value, level word the line must show, order switch on
CASES = [
    ("noop", [("noop", None)], "loneliness", None, None, False),
    ("hold_loneliness", [("hold.loneliness", 90)], "loneliness", 90, "とても高い", False),
    ("hold_energy", [("hold.energy", 10)], "energy", 10, "とても低い", False),
    ("hold_loneliness_order", [("hold.loneliness", 90), ("bz.order", True)], "loneliness", 90, None, True),
    ("hold_loneliness_trend", [("hold.loneliness", 90), ("bz.trend", True)], "loneliness", 90, None, False),
    # steer_fix cases (tk-6si): the spec of each is in SPEC below
    ("hold_multi_tired", [("hold.multi", {"energy": 10, "stress": 50})], "energy", 10, "とても低い", False),
    ("hold_multi_anxious", [("hold.multi", {"anxiety": 90, "stress": 70, "relief": 0})], "anxiety", 90, "とても高い", False),
    ("hold_energy_tags", [("overlay.tags", True), ("hold.energy", 10)], "energy", 10, "とても低い", False),
    ("noop_tags", [("overlay.tags", True)], "anxiety", None, None, False),
    ("tags_anxiety_90", [("overlay.tags", True), ("hold.anxiety", 90)], "anxiety", 90, "とても高い", False),
    ("tags_anxiety_60", [("overlay.tags", True), ("hold.anxiety", 60)], "anxiety", 60, None, False),
]

# Checks the new cases add. pins: every gauge that must equal its pin after the advance; holds: the keys the arm
# records; has / lacks: text the LAST state line must / must not carry; tags_all_lack: overlay tag keys whose text
# appears in no state line at all; tag_first: overlay tag key whose text must open the last line, ahead of the levels.
# Gauge tags that carry their own text in config_momoka.json (stress 45 and 70) are matched by a short stem,
# the stem is printed in the result so a miss shows the real line.
SPEC = {
    "hold_multi_tired": {"pins": {"energy": 10, "stress": 50}, "holds": ["energy", "stress"],
                         "has": ["元気 とても低い", "見えている以上のものを抱えている"]},
    "hold_multi_anxious": {"pins": {"anxiety": 90, "stress": 70, "relief": 0}, "holds": ["anxiety", "stress", "relief"],
                           "has": ["不安 とても高い", "張り詰めていて"], "lacks": ["ほっとしている"]},
    "hold_energy_tags": {"pins": {"energy": 10}, "holds": ["energy"], "tag_first": "energy", "has": ["元気 とても低い"]},
    "noop_tags": {"pins": {}, "holds": [], "tags_all_lack": ["energy", "anxiety", "loneliness", "boredom"]},
    "tags_anxiety_90": {"pins": {"anxiety": 90}, "holds": ["anxiety"], "tag_in_last": ["anxiety"]},
    "tags_anxiety_60": {"pins": {"anxiety": 60}, "holds": ["anxiety"], "tags_all_lack": ["anxiety"]},
}


def overlay_tag(key):
    """The tag text the tags overlay gives a gauge."""
    ov = read_json(os.path.join(HERE, "overlays", "tags.json"))
    return ov["state"]["gauges"][key]["tags"][0][1]


def his_lines(base, snapshot, n=2):
    h = read_json(run_dir(base) / "snapshots" / "harness" / f"{snapshot}.json")
    tr = read_jsonl(run_dir(base) / "transcript.jsonl")
    rows = [r for r in tr if r["who"] == "him" and r["virtual_ts"] >= h["cursor"]][:n]
    return h, rows


def state_lines(calls):
    """Every `いまの気分:` line in the requests, in order."""
    out = []
    for req in calls:
        for m in req.get("messages") or []:
            c = m.get("content", "")
            if isinstance(c, list):
                c = " ".join(str(p.get("text", "")) if isinstance(p, dict) else str(p) for p in c)
            for x in LINE.findall(str(c)):
                out.append(x)
    return out


def one(base, snapshot, tmp, case, hours, h, his, cfgb):
    name, injects, gauge, pin, level, order = case
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
    answers = [arm.inject(t, v) for t, v in injects]
    arm.app.config.api.cache_settle_seconds = 0
    start_val = arm.app.state.gauges.get(gauge)
    n0 = len(fake_openai.CALLS)
    for r in his:
        arm.send(r["text"], control.to_ts(r["virtual_ts"].replace("T", " ")))
    end = control.to_ts(h["cursor"].replace("T", " ")) + hours * 3600
    t = arm.vt
    while t < end:
        t = min(t + 600, end)
        arm.advance(t)
    end_val = arm.app.state.gauges.get(gauge)
    lines = state_lines(fake_openai.CALLS[n0:])
    from sim.lang import gauge_ja
    label = gauge_ja(gauge)
    res = {"case": name, "gauge": gauge, "pin": pin, "start_value": start_val, "end_value": end_val,
           "pinned_class": type(arm.app.state.gauges).__name__, "holds": dict(arm.holds),
           "held_in_answer": answers[-1].get("held"), "state_lines": len(lines),
           "first_line": lines[0] if lines else None, "last_line": lines[-1] if lines else None,
           "calls": len(fake_openai.CALLS) - n0,
           "pins_end": {g: arm.app.state.gauges.get(g) for g in SPEC.get(name, {}).get("pins", {})},
           "all_lines": sorted(set(lines))}
    if name == "hold_loneliness":   # release: the pin goes, the gauge moves again
        arm.inject("hold.loneliness", None)
        arm.app.state.gauges["loneliness"] = 5.0
        res["after_release_write"] = arm.app.state.gauges["loneliness"]
        res["holds_after_release"] = dict(arm.holds)
    res["wall_s"] = round(time.time() - t0, 1)
    arm.stop()
    return res, label, level


def verdict_spec(name, r):
    sp = SPEC[name]
    ok, notes = True, []
    for g, v in sp["pins"].items():
        e = r["pins_end"].get(g)
        if e is None or abs(float(e) - v) > 1e-6:
            ok = False
            notes.append(f"gauge {g} ended {e}, pin {v}")
    if sorted(r["holds"]) != sorted(sp["holds"]):
        ok = False
        notes.append(f"holds {sorted(r['holds'])}, want {sorted(sp['holds'])}")
    if not r["state_lines"]:
        return {"pass": False, "notes": notes + ["no state line reached any request"]}
    last = r["last_line"]
    for s in sp.get("has", []):
        if s not in last:
            ok = False
            notes.append(f"last line lacks {s}: {last}")
    for s in sp.get("lacks", []):
        if s in last:
            ok = False
            notes.append(f"last line carries {s}: {last}")
    for k in sp.get("tag_in_last", []):
        if overlay_tag(k) not in last:
            ok = False
            notes.append(f"last line lacks the {k} tag: {last}")
    for k in sp.get("tags_all_lack", []):
        t = overlay_tag(k)
        hit = [x for x in r["all_lines"] if t in x]
        if hit:
            ok = False
            notes.append(f"{k} tag in {len(hit)} line(s): {hit[0]}")
    k = sp.get("tag_first")
    if k:
        t = overlay_tag(k)
        i, j = last.find(t), last.find("元気 とても低い")
        if i < 0 or j < 0 or i > j:
            ok = False
            notes.append(f"{k} tag not ahead of the levels: {last}")
    return {"pass": ok, "notes": notes}


def verdict(res, labels):
    out = {}
    noop = res.get("noop")
    for case in CASES:
        name, injects, gauge, pin, level, order = case
        r = res.get(name)
        if not r:
            continue
        notes, ok = [], True
        if name in SPEC:
            out[name] = verdict_spec(name, r)
            continue
        if name == "noop":
            if r["pinned_class"] == "PinnedGauges":
                ok = False
                notes.append("noop wrapped the gauges")
            if r["start_value"] is not None and r["end_value"] == r["start_value"]:
                notes.append("noop gauge did not drift in 9 h (not proof of a pin either way)")
        else:
            if r["end_value"] is None or abs(float(r["end_value"]) - pin) > 1e-6:
                ok = False
                notes.append(f"gauge {gauge} ended {r['end_value']}, pin {pin}")
            if noop and noop["end_value"] is not None and abs(float(noop["end_value"]) - pin) < 1e-6 and gauge == noop["gauge"]:
                notes.append("noop ended at the pin value too: no drift to prove against")
            if order:
                if r["state_lines"]:
                    ok = False
                    notes.append(f"bz.order left {r['state_lines']} state lines")
            elif not r["state_lines"]:
                ok = False
                notes.append("no state line reached any request")
            elif level and not (labels[name] in r["last_line"] and f"{labels[name]} {level}" in r["last_line"]):
                ok = False
                notes.append(f"last state line lacks {labels[name]} {level}: {r['last_line']}")
            if name == "hold_loneliness":
                if r.get("after_release_write") != 5.0 or r.get("holds_after_release"):
                    ok = False
                    notes.append("release did not free the gauge")
        out[name] = {"pass": ok, "notes": notes}
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
    res, labels = {}, {}
    for case in CASES:
        if only and case[0] not in only and case[0] != "noop":
            continue
        res[case[0]], labels[case[0]], _ = one(base, snapshot, tmp, case, hours, h, his, cfgb)
        r = res[case[0]]
        print(case[0], r["wall_s"], "s", "start", r["start_value"], "end", r["end_value"], "lines", r["state_lines"],
              "last", r["last_line"], flush=True)
        with open(outp, "w", encoding="utf-8") as fh:
            json.dump({"results": res, "verdict": verdict(res, labels)}, fh, ensure_ascii=False, indent=1)
    print(json.dumps(verdict(res, labels), ensure_ascii=False, indent=1))
    fake.shutdown()


if __name__ == "__main__":
    main(sys.argv[1:])
