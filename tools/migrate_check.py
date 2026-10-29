"""What the first character's primitives would be if computed from her record.

The nine numbers are live for the second character and off for the first, whose
relationship is still the hand-written meters in `data/cast.json` -- closeness
62, standing 55, tension 15, none of which any event earned. `docs/primitives.md`
§6 says the honest way to switch her over is to compute them from the record she
already has and look at where the computed value disagrees with the seeded one,
because the record contains the events and the seed contains somebody's guess.

This is that computation. It replays her whole history through the same
functions production uses -- his message moves attention and the ledger, a look
at his machine moves what she has seen of him, a kept promise moves the ledger
back, time decays and accrues -- and prints the nine numbers and every
derivation beside the meters they would replace.

**It reads a COPY of the save and never the save**, asks no model, changes
nothing, and is safe to run while the bot is up.

    python tools/migrate_check.py
    python tools/migrate_check.py --db data/world.db --verbose
"""

import argparse
import io
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.dbcopy import copy_db  # noqa: E402
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

from config import Config          # noqa: E402
from sim.primitives import Primitives, KEYS  # noqa: E402

# What a look at his machine is called in her record. She sees him through a
# digest she chooses to open, so these are the moments she actually looked --
# not every tick.
SEEING = ("snoop", "share", "post")


class _Clock:
    """A clock that walks the record instead of the wall, so decay and accrual
    are measured over her real elapsed hours."""

    def __init__(self, ts):
        self.ts = ts

    def now_ts(self):
        return self.ts


class _Store:
    """The primitives store, in memory. Nothing here touches the save."""

    def __init__(self):
        self.d = {}

    def get(self, k, default=None):
        return self.d.get(k, default if default is not None else {})

    def set(self, k, v):
        self.d[k] = v


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--db", default="data/world.db")
    ap.add_argument("--config", default="config.json")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    tmp = os.path.join(tempfile.gettempdir(), "migrate_check.db")
    copy_db(args.db, tmp)
    con = sqlite3.connect(tmp)

    cfg = Config(path=args.config)
    # the numbers move at production's rates whether or not she is switched on
    cfg.primitives.enabled = True
    clock = _Clock(0)
    prim = Primitives(cfg, _Store(), clock)
    key = "him"

    rows = []
    for ts, role, text in con.execute(
            "select ts, role, text from messages where ts is not null order by ts"):
        rows.append((float(ts), "msg", role, text or ""))
    for ts, kind, text in con.execute(
            "select ts, kind, text from events where ts is not null order by ts"):
        rows.append((float(ts), "event", kind, text or ""))
    rows.sort(key=lambda r: r[0])
    if not rows:
        print("no dated rows in the record; nothing to compute")
        return 1

    last = rows[0][0]
    counts = {"his message": 0, "she looked": 0, "she gave": 0}
    trail = []
    for ts, kind, a, text in rows:
        clock.ts = ts
        hours = max(0.0, (ts - last) / 3600.0)
        if hours:
            prim.decay(key, hours)
            prim.accrue(key, hours)
        last = ts
        if kind == "msg" and a == "user":
            words = len(str(text).split())
            # the same reading production uses: what the message cost him, and
            # whether it answered something she had asked
            effort = max(0.0, min(1.0, words / 40.0))
            answered = "?" in str(text) or words > 12
            prim.note_from_him(key, effort, answered)
            counts["his message"] += 1
        elif kind == "event" and a in SEEING:
            prim.observe(key, str(text)[:100])
            counts["she looked"] += 1
        elif kind == "event" and a == "commitment" and "kept" in str(text).lower():
            prim.gave(key, str(text)[:100])
            counts["she gave"] += 1
        if args.verbose and len(trail) < 400:
            trail.append((ts, prim.closeness(key), prim.attachment(key)))

    print("\nreplayed %d dated rows: %s" % (len(rows), ", ".join(
        "%d %s" % (v, k) for k, v in counts.items())))
    span = (rows[-1][0] - rows[0][0]) / 86400.0
    print("her record spans %.0f days\n" % span)

    r = prim.row(key)
    print("the nine, computed from what happened:")
    for k in KEYS:
        print("  %-22s %6.1f" % (k, r[k]))
    print()
    print("what that derives, beside the meter it would replace:")
    cast = cfg.read_text(getattr(cfg.character, "cast_file", "data/cast.json"))
    import json
    people = (json.loads(cast).get("people") or {}) if cast else {}
    him = people.get("him") or {}
    print("  %-22s %6.1f   against a hand-written %s" % (
        "closeness", prim.closeness(key), him.get("closeness")))
    print("  %-22s %6.1f" % ("attachment", prim.attachment(key)))
    print("  %-22s %6.1f" % ("resentment", prim.resentment(key)))
    cr = prim.craving(key)
    print("  %-22s %s" % ("craving", "undefined" if cr is None else "%6.1f" % cr))
    print("  %-22s %s" % ("admitted", prim.admitted(key)))
    print("  %-22s %s" % ("can ick", prim.can_ick(key)))
    print("  %-22s %s" % ("can withhold", prim.can_withhold(key)))
    print("  %-22s %s" % ("can rupture", prim.can_rupture(key)))

    print("\nRead this as a shape, not a score. The rates were set for a")
    print("character who watches his machine continuously; this one sees him")
    print("through a digest she has to decide to open, so the absolute numbers")
    print("are not transferable. What is informative is whether four months of")
    print("a real relationship lands anywhere near the meter somebody typed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
