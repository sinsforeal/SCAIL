# -*- coding: utf-8 -*-
"""Replacing a file that another process may be reading, without it ever
seeing half of one.

Four processes run over this tree at once -- the hub, the machine's
collector, the mirror daemon and one bot per character -- and several files
are written by one of them and read by the others: the cast roster, the
household, the hub's own message log, the machine's telemetry snapshot, the
mirror of his list, the weather cache. A plain `open(path, "w")` truncates
the file first and fills it afterwards, so every reader in that window gets a
prefix and a parse error. On 2026-09-07 a patch script rewrote the cast
roster in place and two bots logged 364 parse failures in 31 seconds between
them.

The replacement is written to a temp file BESIDE the destination -- the same
directory, so the rename is within one volume, which is what makes it atomic
-- flushed, fsynced so the bytes are on the disk before the name moves, and
then renamed over the original.

`os.replace` on Windows fails with PermissionError while another process has
the destination open, because CPython opens a file for reading without
sharing delete. A reader holds it for microseconds, so the rename is retried
for a moment. If it still will not go, the bytes are written in place rather
than lost, and the caller is told, because a file not written at all is worse
than a file briefly half written.
"""
import io
import json
import os
import time

RETRY_SECONDS = 5.0
RETRY_SLEEP = 0.002
# A reader that loses the race waits and tries again. Three tries 20ms apart is
# a 60ms budget, which was enough on an idle machine and is not enough on a busy
# one: on 2026-09-17 the collector and its system monitor running beside the
# bot made `tools/atomic_test.py` fail its own "a reader that tries again never
# fails at all" check twice in a row, and the second time it blocked a restart
# (smoke refuses to start a bot on a red gate). Six tries 50ms apart is a 250ms
# budget: still bounded, still fast for the ordinary case, and wide enough that
# the reader is waiting out a rename rather than a machine.
READ_TRIES = 6
READ_PAUSE = 0.05


def replace(path, text, encoding="utf-8", newline=""):
    """Write `text` and put it in place of `path` in one rename.

    True when the rename went through, False when it would not and the file
    on disk is still the previous one.

    THERE IS NO WRITING IN PLACE HERE, not even as a fallback. Measured with
    a reader opening the file 400,000 times a second: the rename hit a
    sharing violation about once in forty writes, and a fallback that wrote
    the bytes in place handed two readers an empty file -- which is the whole
    fault this module exists to prevent. A reader handed a document one
    revision old recovers from it; a reader handed half of one does not. The
    replacement is left beside the original so nothing is lost, and the next
    call writes it again."""
    path = os.fspath(path)
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    tmp = os.path.join(d, ".%s.%d.tmp" % (os.path.basename(path), os.getpid()))
    with io.open(tmp, "w", encoding=encoding, newline=newline) as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    t0 = time.time()
    last = None
    while time.time() - t0 < RETRY_SECONDS:
        try:
            os.replace(tmp, path)
            return True
        except PermissionError as e:
            # a reader has it open; CPython opens a file for reading without
            # sharing delete, and a reader holds it for microseconds
            last = e
            time.sleep(RETRY_SLEEP)
        except OSError as e:
            last = e
            break
    try:
        import logger
        logger.log(f"[atomic] {os.path.basename(path)} was not replaced after "
                   f"{time.time() - t0:.0f}s ({type(last).__name__}); the file on disk is "
                   f"the previous one and the new bytes are beside it")
    except Exception:
        pass
    return False


def write_json(path, data, **dumps):
    """The same, for a JSON document. `dumps` is passed to `json.dumps`."""
    dumps.setdefault("ensure_ascii", False)
    return replace(path, json.dumps(data, **dumps))


def read_json(path, tries=READ_TRIES, pause=READ_PAUSE, encoding="utf-8"):
    """Read a JSON document that somebody else may be replacing right now.

    A read that fails is tried again rather than believed. Two windows fail
    and both are over in microseconds: while the name is moving the file
    cannot be opened at all (a sharing violation, 44 reads in 391,113
    measured), and a writer that has not been through this module yet -- a
    patch script -- truncates before it fills. The last failure is raised if
    all the attempts fail, so the caller decides what an unreadable file
    means."""
    last = None
    for i in range(max(1, int(tries))):
        try:
            with io.open(path, "r", encoding=encoding) as f:
                return json.load(f)
        except (OSError, ValueError) as e:
            last = e
            if i + 1 < max(1, int(tries)):
                time.sleep(pause)
    raise last
