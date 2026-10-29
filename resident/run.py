"""Run 千代田百花 (Chiyoda Momoka), the one character in this fork, resident on
his machine.

    python resident\run.py              # live, config_momoka.json, data/momoka.db
    python resident\run.py --sim ...    # any scail.py option

Registers her words (how she sees him: his machine in front of her), fills in
her config and save unless they are given, and hands the rest to the shared
runtime. momoka.cmd launches this.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)

import resident.words  # noqa: E402,F401 -- registers before anything reads
import scail  # noqa: E402

if __name__ == "__main__":
    argv = list(sys.argv[1:])
    if "--config" not in argv:
        argv += ["--config", "config_momoka.json"]
    if "--db" not in argv:
        argv += ["--db", "data/momoka.db"]
    scail.main(argv, program="resident")
