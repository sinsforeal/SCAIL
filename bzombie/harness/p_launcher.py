"""Harness-side launcher for the P arm (the arm_cmd of a P run config).

    C:\\Python314\\python.exe -m bzombie.harness.p_launcher --p-root F:\\REPS2\\SCAILV4\\tmp\\wt_bz_parm --port 18341 --run-id <id>

The driver spawns arm_cmd hidden with cwd SCAILV4 and has already claimed the port for this run. P must run from its
own tree and venv (private-machine fork, branch bz/parm-patch), so this launcher starts `harness.server` there in the
foreground with the same env as the fork's harness/launch.py, and exits with the server's code. The server takes its
own compute ticket (who scail/bz_p_<run_id>) and releases it and the port claim on /control/stop.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

NO_WINDOW = 0x08000000


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--p-root", required=True)
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--run-id", required=True)
    a = ap.parse_args(argv)
    py = os.path.join(a.p_root, ".venv", "Scripts", "python.exe")
    log_dir = os.path.join(r"H:\SCAIL\bzombie\var\runs", a.run_id, "logs")
    os.makedirs(log_dir, exist_ok=True)
    env = {**os.environ, "TEMP": r"H:\SCAIL\temp", "TMP": r"H:\SCAIL\temp", "PM_COMPLETION_CACHE": "0",
           "PYTHONPATH": a.p_root, "PYTHONUTF8": "1"}
    cmd = [py, "-m", "harness.server", "--port", str(a.port), "--ticket-who", f"scail/bz_p_{a.run_id}",
           "--run-id", a.run_id, "--log-file", os.path.join(log_dir, "p_control.log")]
    return subprocess.run(cmd, cwd=a.p_root, env=env, stdin=subprocess.DEVNULL, creationflags=NO_WINDOW).returncode


if __name__ == "__main__":
    sys.exit(main())
