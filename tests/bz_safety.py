"""Guard for bench tests that write into the pinned VAR. bzombie.common pins VAR at its first import (default is the LIVE
H:\\SCAIL\\bzombie\\var). A test run that pinned the live VAR once wiped the live claude_queue (clean_queue rmtree) and
planted fake requests and a fake worker.json in it (2026-10-23 15:18-15:20, see
docs/reports/2026-10-24_worker_fix_notebook.md). Call refuse_live_var at import time and before any rmtree."""
import os
from pathlib import Path

LIVE_VAR = r"H:\SCAIL\bzombie\var"


def _norm(p) -> str:
    return os.path.normcase(os.path.abspath(str(p))).rstrip("\\/")


def refuse_live_var(var) -> None:
    if _norm(var) == _norm(LIVE_VAR):
        raise RuntimeError(f"refusing to run: bzombie.common.VAR is the live bench var {var}. Run this test module "
                           "first in its process, or with BZ_VAR set to a scratch folder before bzombie is imported.")
    if Path(var).name == "claude_queue":
        raise RuntimeError(f"refusing to run: VAR {var} looks like a queue folder")
