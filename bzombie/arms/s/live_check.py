"""Live check through the gateway: a Tomoe run with cap_usd 0.10, one message, advance to a reply,
numbers per reply (calls, cost, wall seconds). Usage: live_check.py <run_id> <port>"""

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

run_id, port = sys.argv[1], int(sys.argv[2])
rd = os.path.join(make_run.RUNS, run_id)
os.makedirs(rd, exist_ok=True)
now = time.time()
with open(os.path.join(rd, "config.json"), "w", encoding="utf-8") as fh:
    json.dump({"run_id": run_id, "arm": "S", "character": "tomoe", "lang": "en", "model": "deepseek-v4.1-flash-1017",
               "cap_usd": 0.10, "sim_days": 1, "clock_start": "2026-10-23T08:00:00", "seed": 1,
               "status": "running", "started_wall": now, "updated_wall": now}, fh)


def call(path, body=None, timeout=1800):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=None if body is None else json.dumps(body).encode(),
                                 method="GET" if body is None else "POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{path}: {e.code} {e.read().decode('utf-8', 'replace')[:600]}")


proc = launch(port)
for _ in range(60):
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/control/state", timeout=2)
    except urllib.error.HTTPError:
        break
    except Exception:
        time.sleep(1)
w0 = time.time()
print("start", call("/control/start", {"run_id": run_id, "character": "tomoe", "lang": "en",
                                        "clock_start": "2026-10-23T08:00:00"}), round(time.time() - w0, 1), "s")
t0 = control.parse_local("2026-10-23T08:00:00")
call("/control/env", {"events": [{"ts": t0 + 5, "kind": "world", "text": "She has a stats lecture at 9.",
                                  "source": "env_script/1"}]})
call("/control/send", {"text": "morning. did you sleep ok?", "ts": t0 + 60})
w1 = time.time()
t, outs = t0 + 60, []
while not outs and t < t0 + 60 + 1800:
    t += 60
    outs = call("/control/advance", {"to": t})["outputs"]
wall = time.time() - w1
print("reply after virtual s:", t - t0 - 60, "wall s:", round(wall, 1))
for o in outs:
    print("out", o["output_id"], repr(o["text"][:200]), "calls", len(o["call_ids"]))
calls = [json.loads(l) for l in open(os.path.join(rd, "calls.jsonl"), encoding="utf-8")]
cost = sum(int(c.get("cost_micro") or 0) for c in calls)
print("gateway calls:", len(calls), "cost_usd:", cost / 1e6, "errors:", sum(1 for c in calls if c.get("error")))
if outs:
    tr = call("/control/trace/" + outs[0]["output_id"])
    print("trace calls", len(tr["calls"]), "final", tr["final_call_id"][:8], "inputs", len(tr["inputs"]))
call("/control/stop", {})
