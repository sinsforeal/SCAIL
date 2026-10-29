"""Sweep the gauges against their readers, offline, on a copy of the save.

    python tools/sweep.py [gauge|him|all]
    python tools/sweep.py all --config config_yukarin.json --db data/yukarin.db

Builds the App the way tools/smoke.py does (console, no sensors, logger
stubbed, a copy of the save) and prints sim/sweep.sweep(). Same thing as
`/sweep` in the app, without touching the live process.

The character was hardcoded here, so the second character could only be swept
from inside the running bot -- which is the one place a sweep is awkward to
run. Her config is COPIED before it is used, because `Config.__init__` rewrites
the file it is given and hers is open in a running process.
"""
import argparse
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import harness  # noqa: E402
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("what", nargs="?", default="all")
    p.add_argument("--config", default="config.json")
    p.add_argument("--db", default="data/world.db")
    a = p.parse_args()
    stem = os.path.splitext(os.path.basename(a.config))[0]
    tmp = os.path.join(tempfile.gettempdir(), f"scail_sweep_{stem}.db")
    cfg = os.path.join(tempfile.gettempdir(), f"scail_sweep_{stem}.json")
    shutil.copy(a.config, cfg)
    import logger
    logger.setup = lambda out_dir: None
    logger.finish = lambda: None
    logger.log = lambda m, to_console=True: None
    logger.log_llm = lambda *a, **k: None
    logger.write_artifact = lambda *a, **k: None
    import scail  # noqa: F401
    app = harness.build_on(tmp, cfg, a.db)
    from sim.sweep import sweep
    print(sweep(app, a.what))


if __name__ == "__main__":
    main()
