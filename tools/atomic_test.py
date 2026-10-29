# -*- coding: utf-8 -*-
"""A file replaced under a reader is never seen half written.

    python tools/atomic_test.py        # in smoke; temp files only

On 2026-09-07 a patch script rewrote `data/cast.json` in place while three
bot processes were reading it, and two of them logged 364 parse failures
between them in 31 seconds. `atomic.replace` writes beside the destination,
fsyncs, and renames over it, which is one operation as far as a reader is
concerned.

What the rename does NOT promise on Windows is that the file can be opened at
every instant: CPython opens a file for reading without sharing delete, so a
read that lands exactly while the name is moving gets a sharing violation.
That is a different failure and a much better one -- nothing is torn, the
read simply has to be tried again -- and `atomic.read_json` is what tries it.
Both are checked here, and so is the reader that used to log one line per
failed read.
"""
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

import atomic  # noqa: E402

fails = []
ROUNDS = 30


def check(ok, what, detail=""):
    print(("  ok   " if ok else "  FAIL ") + what + (("  -- " + detail) if detail else ""))
    if not ok:
        fails.append(what)
    return ok


def _document(n):
    """About the size of the cast roster: some tens of kilobytes of nested
    JSON with Japanese in it."""
    return {"people": {f"person{i}": {"ja": "名前" * 6, "note": "x" * 200, "round": n}
                       for i in range(60)}}


def _reader(path, out, stop, careful):
    """Reads as fast as it can, either plainly or through `atomic.read_json`."""
    while not stop.is_set():
        try:
            if careful:
                doc = atomic.read_json(path)
            else:
                with io.open(path, encoding="utf-8") as fh:
                    doc = json.load(fh)
            out["read"] += 1
            if len(doc.get("people") or {}) != 60:
                out["torn"] += 1
        except ValueError:
            out["half"] += 1
        except OSError:
            out["locked"] += 1
        time.sleep(0.0005)      # so the writer is not starved of the GIL


def one(path, writer, label, careful=False):
    out = {"read": 0, "half": 0, "locked": 0, "torn": 0}
    writer(path, _document(0))
    stop = threading.Event()
    t = threading.Thread(target=_reader, args=(path, out, stop, careful), daemon=True)
    t.start()
    for n in range(1, ROUNDS + 1):
        writer(path, _document(n))
        time.sleep(0.003)
    stop.set()
    t.join(timeout=5)
    print(f"  {label}: {out['read']} whole read(s), {out['half']} half a file, "
          f"{out['locked']} could not be opened, {out['torn']} short")
    return out


def _in_place(path, doc):
    with io.open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False)


def write_checks(tmp):
    print("\nA LARGE DOCUMENT REPLACED UNDER A READER")
    good = one(os.path.join(tmp, "atomic.json"), atomic.write_json, "through atomic.write_json")
    check(good["half"] == 0, "the reader is never handed half a file",
          f"{good['half']} parse failure(s)")
    check(good["torn"] == 0, "and never a short one", f"{good['torn']} short")
    check(good["read"] > 100, "and did read it, so the test measured something",
          f"{good['read']} reads")

    print("\nTHE SAME, READ THROUGH atomic.read_json")
    careful = one(os.path.join(tmp, "careful.json"), atomic.write_json,
                  "through atomic.read_json", careful=True)
    check(careful["half"] == 0 and careful["locked"] == 0,
          "a reader that tries again never fails at all",
          f"{careful['half']} half, {careful['locked']} locked")

    print("\nWRITTEN IN PLACE, FOR COMPARISON")
    bad = one(os.path.join(tmp, "inplace.json"), _in_place, "written in place")
    print(f"  (this is what produced the 364 parse failures on 2026-09-07; it broke "
          f"{bad['half']} read(s) here, which is a race and may be 0 on a fast disk)")


def suppression_checks():
    print("\nTHE READER THAT USED TO SHOUT")
    from sim import roster
    said = []
    import logger
    was = logger.log
    logger.log = lambda m: said.append(m)
    try:
        roster._UNREADABLE.update({"path": "", "since": 0.0, "n": 0, "said": 0.0})
        e = ValueError("Expecting ',' delimiter: line 859 column 339")
        for _ in range(233):
            roster._say_unreadable("data/cast.json", e)
        first = list(said)
        roster._say_readable("data/cast.json")
    finally:
        logger.log = was
    check(len(first) == 1, "233 failed reads inside a minute say it once", f"{len(first)} line(s)")
    check(len(said) == 2 and "readable again" in said[-1],
          "and the recovery says how long it lasted and how many reads it cost",
          said[-1] if said else "")
    check("233 failed read" in said[-1], "with the count", said[-1])


def main():
    tmp = tempfile.mkdtemp(prefix="atomic_test_")
    try:
        write_checks(tmp)
        suppression_checks()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print()
    if fails:
        print(f"FAIL: {len(fails)} check(s): " + "; ".join(fails[:6]))
        return 1
    print("all checks passed: a replaced file is never half a file")
    return 0


if __name__ == "__main__":
    sys.exit(main())
