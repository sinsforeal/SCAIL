"""Time idle advance through a real gateway. Usage: time_check.py <run_id> <port> <character> <virtual_hours> [--live]
Makes the run's config.json (cap 0.20), boots the S arm, advances idle, prints wall seconds per virtual hour and
gateway calls. With --live it then sends one Japanese message and advances to her reply."""

import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_run  # noqa: E402
import control  # noqa: E402
from launch import launch  # noqa: E402

run_id, port, char, hours = sys.argv[1], int(sys.argv[2]), sys.argv[3], float(sys.argv[4])
live = "--live" in sys.argv
rd = os.path.join(make_run.RUNS, run_id)
os.makedirs(rd, exist_ok=True)
now = time.time()
lang = "ja" if char == "momoka" else "en"
START = "2026-10-23T08:00:00"
with open(os.path.join(rd, "config.json"), "w", encoding="utf-8") as fh:
    json.dump({"run_id": run_id, "arm": "S", "character": char, "lang": lang, "model": "deepseek-v4.1-flash-1017",
               "cap_usd": 0.20, "sim_days": 1, "clock_start": START, "seed": 1,
               "status": "running", "started_wall": now, "updated_wall": now}, fh)


def call(path, body=None, timeout=3600):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=None if body is None else json.dumps(body).encode(),
                                 method="GET" if body is None else "POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{path}: {e.code} {e.read().decode('utf-8', 'replace')[:600]}")


def gw():
    p = os.path.join(rd, "calls.jsonl")
    if not os.path.exists(p):
        return 0, 0
    cs = [json.loads(l) for l in open(p, encoding="utf-8")]
    return len(cs), sum(int(c.get("cost_micro") or 0) for c in cs)


launch(port)
for _ in range(60):
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/control/state", timeout=2)
    except urllib.error.HTTPError:
        break
    except Exception:
        time.sleep(1)
w0 = time.time()
print("start", call("/control/start", {"run_id": run_id, "character": char, "lang": lang, "clock_start": START}),
      round(time.time() - w0, 1), "s", flush=True)
t0 = control.parse_local(START)
c0, _ = gw()
w1 = time.time()
r = call("/control/advance", {"to": t0 + hours * 3600})
wall = time.time() - w1
c1, cost1 = gw()
print(f"idle advance {hours} h: {wall:.1f} s wall = {wall / hours:.1f} s/h, calls {c1 - c0}, cost_usd {cost1 / 1e6:.6f}, outputs {len(r['outputs'])}", flush=True)
for o in r["outputs"]:
    print("  idle out", o["virtual_ts"], repr(o["text"][:120]))
if live:
    t = t0 + hours * 3600
    msg = os.environ.get("BZ_MSG", "おはよう、今起きた？")
    call("/control/send", {"text": msg, "ts": t + 30})
    c2, _ = gw()
    w2 = time.time()
    outs = []
    tt = t + 30
    while not outs and tt < t + 30 + 3600:
        tt += 60
        outs = call("/control/advance", {"to": tt})["outputs"]
    wall2 = time.time() - w2
    c3, cost3 = gw()
    print(f"reply after virtual {tt - t - 30:.0f} s, wall {wall2:.1f} s, calls {c3 - c2}, total cost_usd {cost3 / 1e6:.6f}")
    for o in outs:
        print("  OUT", o["output_id"], repr(o["text"]))
    if outs:
        tr = call("/control/trace/" + outs[0]["output_id"])
        print("trace calls", len(tr["calls"]), "inputs", len(tr["inputs"]))
call("/control/stop", {})
