"""The App on a copy of a save, the way the loop builds it.

Twelve harnesses carried the same eight lines: copy the save, swap
`sys.argv` for the console flags, parse with scail's own parser so the flags
never drift from the real ones, build. This is those lines once. The copy
is SQLite's backup (`tools/dbcopy.py`), never a file copy of an open save.

    from tools import harness
    app = harness.build_on(tmp)                       # config_momoka.json, data/momoka.db
    app = harness.build_on(tmp, "config_momoka.json", "data/momoka.db")
    app = harness.build_on(tmp, copy=False)           # again on the same copy: a restart

`refuse_model(app)` makes every model call raise, for a harness that must
not spend: nothing here does it by default, because a harness that catches
exceptions around a call would pass for the wrong reason.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from tools.dbcopy import copy_db  # noqa: E402


def quiet_logger():
    """No run directory, no ACTIVE pid file, nothing written under `logs/`.

    `App.__init__` calls `logger.setup()`, which makes a timestamped run
    directory with an ACTIVE file the restarter reads. Smoke stubs the
    logger for that reason; the hand-run tools that build through this
    harness did not, and eight of them left run directories in one morning.
    Stubbed here, once, so a tool has to ask to log."""
    import logger
    logger.setup = lambda out_dir: None
    logger.finish = lambda: None
    logger.log = lambda m, to_console=True: None
    logger.log_llm = lambda *a, **k: None
    logger.write_artifact = lambda *a, **k: None


def build_on(tmp, config="config_momoka.json", db="data/momoka.db", extra=(), copy=True, quiet=True):
    """Copy `db` to `tmp` and build the App on it, console mode, no sensors.

    `copy=False` skips the copy and builds on whatever is at `tmp` already:
    what a restart does, for a harness that wants to see whether the state
    the first App wrote is still there for the second one
    (`tools/restart_safe_test.py`). `quiet=False` keeps the real logger,
    for a tool that wants a run directory of its own."""
    import scail
    if quiet:
        quiet_logger()
        config = scratch_config(config, tmp)
    if copy:
        copy_db(os.path.join(ROOT, db) if not os.path.isabs(db) else db, tmp)
    argv = sys.argv
    sys.argv = ["scail.py", "--config", config, "--console", "--no-sensors", "--db", tmp, *extra]
    try:
        args = scail.parse_args()
    finally:
        sys.argv = argv
    return scail.App(args)


class Refused(RuntimeError):
    pass


def refuse_model(app):
    """Every model call on this App raises `Refused`: a harness that must not spend."""
    def _refuse(*a, **k):
        raise Refused("this harness does not spend model calls")
    app.llm.call = _refuse
    app.llm.call_json = _refuse
    return app

class NoNetwork(RuntimeError):
    pass


def refuse_network():
    """Every outbound connection from this process raises `NoNetwork`.

    A scratch build on a fresh save fetches what the live save has cached
    (weather, the train table, the hazards backfill, the anime index), each
    with its own timeout, and twenty-four such builds took six minutes where
    one on a live copy takes a second. Every fetch in the tree is logged by
    exception type and goes on, so refusing at the socket makes a scratch
    build honest and fast rather than broken. Process-wide, on purpose: a
    harness that must not reach the network wants no exception."""
    import socket

    def _refuse(*a, **k):
        raise NoNetwork("this harness does not reach the network")
    socket.socket.connect = _refuse
    socket.create_connection = _refuse

def refuse_model_before_build():
    """Every model call in this process raises `Refused`, including one made
    while the App is being built. `refuse_model` patches an App that exists;
    a build that spends before returning (the cast-arcs planner ran at boot
    on a fresh save, 42 seconds of retries with the network refused) is only
    caught by patching the class first."""
    import llm as _llm

    def _refuse(*a, **k):
        raise Refused("this harness does not spend model calls")
    _llm.LLM.call = _refuse
    _llm.LLM.call_json = _refuse

def scratch_config(config, tmp):
    """A copy of the config beside the scratch save, with every path a build
    WRITES pointed away from the live tree.

    `Config` rewrites the file it is given (the backfill), and the shared
    world (`world/shared.py`) is written the moment a plan or a settled line
    exists, at boot. A harness building the first character on a copy of
    her save therefore wrote four settled lines into the live world file
    before this existed. The copy carries the world directory under the
    scratch save's own directory, so a tool's build has a world of its own
    and the live one is only ever written by the running character."""
    import json
    src = os.path.join(ROOT, config) if not os.path.isabs(config) else config
    with open(src, encoding="utf-8") as fh:
        cfg = json.load(fh)
    w = cfg.setdefault("world", {})
    if w.get("shared_dir"):
        w["shared_dir"] = os.path.join(os.path.dirname(os.path.abspath(tmp)), "scail_scratch_worlds")
    dst = os.path.abspath(tmp) + ".config.json"
    with open(dst, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, ensure_ascii=False, indent=1)
    return dst
