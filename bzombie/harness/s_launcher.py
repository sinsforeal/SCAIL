"""Harness-side launcher for the S arm (the arm_cmd of an S run config).

    C:\\Python314\\python.exe -m bzombie.harness.s_launcher --s-root F:\\REPS2\\SCAILV4\\tmp\\wt_bz_s --port 18331

Seam with the S worktree (bz/s), which this file never edits:
- S's control.py /control/start calls make_run.build itself, which writes only under runs/<run_id>/s/ (config_s.json,
  prompts, save.db, logs). The harness never writes there.
- S's control.py also writes runs/<run_id>/traces/<output_id>.json (same content the harness fetches and rewrites).
- S's control.py writes runs/<run_id>/clock.json too, as epoch seconds, every 5 virtual s. The contract and the
  harness own that file (ISO virtual_ts, sim_day, wall_ts), so this launcher turns S's _clock_file into a no-op.
Everything else (config.json, state.json, transcript.jsonl, env/, calls.jsonl) is the harness's or the gateway's.
"""
from __future__ import annotations

import argparse
import os
import sys


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--s-root", required=True)
    ap.add_argument("--port", type=int, required=True)
    a = ap.parse_args(argv)
    here = os.path.join(a.s_root, "bzombie", "arms", "s")
    for p in (here, a.s_root):
        if p not in sys.path:
            sys.path.insert(0, p)
    os.environ.setdefault("TEMP", r"H:\SCAIL\temp")
    os.environ.setdefault("TMP", r"H:\SCAIL\temp")
    import control  # S's control server module, from the S worktree
    control.Arm._clock_file = lambda self: None  # the harness owns clock.json
    sys.argv = ["control.py", "--port", str(a.port)]
    control.main()


if __name__ == "__main__":
    main()
