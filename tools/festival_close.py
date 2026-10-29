"""Close a plan the world never held, in a save that already believes it.

The code that let this happen is fixed (`sim/ledger.py:outing_unbacked`, and
its three readers: the day planner's carry, the promise settle, and the cast's
own promises). This is the other half: a save written before the fix holds
rows about a public event that was never on the calendar, and those rows go on
speaking.

The case it was written for. She went to a festival on 2026-08-29 -- two were
on the ward calendar that day, and the scenes put her at the takoyaki stand
outside Otsuka station with her brother at 19:04, walking home in the yukata
at 20:25. The day plan's `settled` list is carried into the next day's
planning, where "tomorrow" means a different day, and nothing between the two
ever asked the calendar whether there WAS one. So the festival was tomorrow
again on 2, 3 and 4 September; sixteen promises were made about it and every
one of them came due and was recorded missed; and her own account announced it
as tomorrow on four separate days.

What this does, all of it against `sim/ledger.py:outing_unbacked` -- never
against the word "festival" on its own, so a real one on the calendar is left
alone:

  - open promises she made (kv `commitments`) settle `moot`, the status the
    code already has for an outing nobody could come to: no meters, no blame,
    remembered as the thing that did not happen;
  - their promises to her (kv `cast_bonds`) that are open or missed become
    `moot`, which every reader already skips, so the room stops saying "they
    said they would and did not" about a day that never came;
  - the `bond` events that recorded those as broken are removed, because a
    record line asserting a thing that did not happen is a fault and not
    history. Every removed row is written out first.
  - `cast_beats` / `cast_beats_prev` settled lines about it are dropped.

Meters are NOT rolled back: the resentment and tension those missed promises
added are hers now, and guessing them back out would be a second invention.
They decay on their own (`sim/sentiment.py`).

    python tools/festival_close.py --db data/world.db          # the bot must be stopped
    python tools/festival_close.py --db data/copy.db --apply
    python tools/festival_close.py --db data/world.db --apply

Without --apply it says what it would do and writes nothing.
"""

import argparse
import datetime
import io
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

from config import Config  # noqa: E402
from world.calendar import Calendar  # noqa: E402


def bot_is_running(db_path):
    """Is a live bot holding this save? A `.db` copied or written under a
    running process is the one thing that must not happen here."""
    try:
        import subprocess
        out = subprocess.run(["wmic", "process", "get", "commandline"], capture_output=True,
                             text=True, timeout=30).stdout
    except Exception:
        return None
    if not out.strip():
        return None
    name = os.path.basename(db_path).lower()
    for line in out.splitlines():
        low = line.lower()
        if "run.py" not in low or "python" not in low:
            continue
        if name in ("world.db",) and "tomoe" in low:
            return line.strip()
        if name in ("yukarin.db",) and "resident" in low:
            return line.strip()
    return None


class Gate:
    """`Ledger.outing_unbacked` without an App: the same words, the same
    calendar, the same answer."""

    DATE = __import__("re").compile(r"(20\d\d-\d\d-\d\d)")

    def __init__(self, config):
        self.words = list(getattr(config.world, "outing_words", None) or ())
        self.cal = Calendar(config) if self.words else None

    # A promise about a THING FROM the day is not a promise about the day. She
    # really did take photographs at Otsuka on 2026-08-29 and really did owe
    # them to a friend for four days; "send the festival photos" is true and
    # stays, and only what claims the day itself is closed. Stated here rather
    # than judged case by case, and deliberately over-cautious: a row named
    # here is left exactly as it is.
    OF_IT = ("photo", "video", "edit", "pic", "写真", "動画", "映像")

    def unbacked(self, text, date_str=None):
        if not self.words or not self.cal:
            return ""
        s = str(text or "")
        if any(w in s.lower() for w in self.OF_IT):
            return ""
        if not any(w.lower() in s.lower() for w in self.words):
            return ""
        days = self.DATE.findall(s) or ([date_str] if date_str else [])
        if not days:
            return ""
        for d in days:
            try:
                dd = datetime.date.fromisoformat(d)
            except (TypeError, ValueError):
                return ""
            for e in self.cal.events(dd):
                blob = (str(e.get("name", "")) + " " + str(e.get("note", ""))).lower()
                if any(w.lower() in blob for w in self.words):
                    return ""
        return "nothing on the calendar for %s is one" % ", ".join(sorted(set(days)))


def kv_get(db, key, default):
    r = db.execute("select value from kv where key=?", (key,)).fetchone()
    return json.loads(r[0]) if r else default


def kv_set(db, key, value):
    db.execute("insert or replace into kv (key, value) values (?, ?)",
               (key, json.dumps(value, ensure_ascii=False)))


def close_festival(db, cfg, apply=True, log=print, retired_root=os.path.join("data", "retired")):
    """The repair over an open sqlite connection: her open promises about an
    outing the calendar has no such event for on that date go `moot`, their
    promises about one the same, the `bond` events that recorded them as
    broken are removed (kept under data/retired), and the plan's carried
    settled lines that name one are dropped. Returns the number of rows
    changed; with `apply` False nothing is written. Called by the tool below
    with the bot stopped, and once at boot by the first character's program
    (kv `festival_closed`), which is the only way the repair reaches a live
    save that the bot itself holds."""
    gate = Gate(cfg)
    if not gate.words:
        log("this character has no world and no calendar; nothing to check a plan against")
        return 0
    changed = {"commitments": [], "bonds": [], "events": [], "settled": []}

    # 1. her own promises
    rows = kv_get(db, "commitments", [])
    for r in rows:
        if r.get("status") != "open":
            continue
        why = gate.unbacked(r.get("what", ""), r.get("date"))
        if not why:
            continue
        changed["commitments"].append(f"{r.get('date')} to {r.get('to_name')}: {r.get('what')} -- {why}")
        r["status"] = "moot"
        r["settled"] = datetime.date.today().isoformat()
        r["why"] = f"there was no such thing that day: {why}"

    # 2. their promises to her
    bonds = kv_get(db, "cast_bonds", {})
    for key, b in (bonds or {}).items():
        for p in b.get("promises", []):
            if p.get("state") not in ("open", "missed"):
                continue
            when = datetime.date.fromtimestamp(float(p.get("due_ts") or p.get("ts") or 0)).isoformat()
            why = gate.unbacked(p.get("what", ""), when)
            if not why:
                continue
            changed["bonds"].append(f"{key} ({p.get('state')}, due {when}): {p.get('what')} -- {why}")
            p["state"] = "moot"
            p["why"] = f"there was no such thing that day: {why}"

    # 3. the events that recorded those as broken
    doomed = []
    for row in db.execute("select rowid, date, text from events where kind='bond'").fetchall():
        rowid, date, text = row
        if " and did not" not in text:
            continue
        if not gate.unbacked(text, date):
            continue
        doomed.append({"rowid": rowid, "date": date, "text": text})
        changed["events"].append(f"{date}: {text[:110]}")

    # 4. the plan's own settled lines
    for key in ("cast_beats", "cast_beats_prev"):
        rec = kv_get(db, key, {})
        if not rec:
            continue
        keep = []
        for x in (rec.get("settled") or []):
            why = gate.unbacked(str(x), rec.get("date"))
            if why:
                changed["settled"].append(f"{key} ({rec.get('date')}): {str(x)[:110]} -- {why}")
                continue
            keep.append(x)
        if len(keep) != len(rec.get("settled") or []):
            rec["settled"] = keep
            if apply:
                kv_set(db, key, rec)

    for label, lines in changed.items():
        log("%s: %d" % (label, len(lines)))
        for l in lines:
            log("  " + l)

    total = sum(len(v) for v in changed.values())
    if not total:
        log("nothing to close.")
        return 0
    if not apply:
        log("%d row(s) would change. Nothing written." % total)
        return total

    kv_set(db, "commitments", rows)
    kv_set(db, "cast_bonds", bonds)
    if doomed:
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        out = os.path.join(retired_root, stamp + "_festival_events")
        os.makedirs(out, exist_ok=True)
        with io.open(os.path.join(out, "removed_bond_events.json"), "w", encoding="utf-8") as f:
            json.dump(doomed, f, ensure_ascii=False, indent=1)
        db.executemany("delete from events where rowid=?", [(d["rowid"],) for d in doomed])
        log("the removed rows are in %s" % out)
    db.commit()
    log("%d row(s) written." % total)
    return total


# ---------------------------------------------------------------- the tail
#
# The rows above were found by a rule: the line says "festival" on a date the
# calendar has no festival on. These are the same plan with the word taken
# out, which is why no rule finds them -- "wear yukata and meet at station",
# "Wait at the station in front even if it rains", "帯を結んでくれる". They are
# named one by one, with the text they must still have for the repair to touch
# them, and every one of them is the 2026-08-29 festival being got ready for
# six days after it happened. This list is a repair of one save at one moment;
# it is not a rule, and nothing new should be added to it -- the rule is now
# that a plan for a public event names the calendar entry it means
# (`world/calendar.py:entry`, `sim/ledger.py`, `tomoe/cast.py:event_of`).
TAIL_COMMITMENTS = [
    ("c178838732022", "wake up on time"),
    ("c178843764926", "wear yukata and meet at station"),
    ("c178847449421", "get her yukata ready for her mother to tie the obi"),
]
TAIL_BONDS = [
    ("dad", "Wait at the station in front even if it rains"),
    ("mom", "帯を結んでくれる"),
    ("mom", "今夜帯を結んでくれる"),
]
# and the line the whole tail hangs off, which the word rule cannot see and
# which the day plan for 2026-09-05 would otherwise carry one day further
TAIL_SETTLED = ["Meet dad at the station tomorrow (2026-09-05)"]
TAIL_WHY = ("the 2026-08-29 festival, got ready for after it had happened; "
            "the calendar has no such thing on 2026-09-05")


def close_festival_tail(db, cfg, apply=True, log=print, retired_root=os.path.join("data", "retired")):
    """The rows the rule cannot see, named one by one. Her three open
    promises about the phantom and the three of theirs become `moot`; the
    rows are written out before they change. Idempotent: a row whose status
    or text has moved on is left alone."""
    changed, dumped = [], []
    rows = kv_get(db, "commitments", [])
    for cid, what in TAIL_COMMITMENTS:
        for r in rows:
            if r.get("id") != cid or r.get("status") != "open":
                continue
            if str(r.get("what", "")).strip() != what:
                log("left alone, its text has moved on: %s %r" % (cid, str(r.get("what"))[:60]))
                continue
            dumped.append(dict(r))
            r["status"] = "moot"
            r["settled"] = datetime.date.today().isoformat()
            r["why"] = TAIL_WHY
            changed.append("%s to %s: %s" % (r.get("date"), r.get("to_name"), what))

    bonds = kv_get(db, "cast_bonds", {})
    for key, what in TAIL_BONDS:
        for p in ((bonds or {}).get(key) or {}).get("promises", []):
            if p.get("state") not in ("open", "missed") or str(p.get("what", "")).strip() != what:
                continue
            dumped.append({"who": key, **p})
            was = p.get("state")
            p["state"] = "moot"
            p["why"] = TAIL_WHY
            changed.append("%s (was %s): %s" % (key, was, what))

    plans = {}
    for key in ("cast_beats", "cast_beats_prev"):
        rec = kv_get(db, key, {})
        keep = [x for x in (rec.get("settled") or [])
                if not any(str(x).strip().startswith(p) for p in TAIL_SETTLED)]
        if len(keep) != len(rec.get("settled") or []):
            for x in (rec.get("settled") or []):
                if x not in keep:
                    dumped.append({"kv": key, "date": rec.get("date"), "settled": x})
                    changed.append("%s (%s): %s" % (key, rec.get("date"), str(x)[:90]))
            rec["settled"] = keep
            plans[key] = rec

    for line in changed:
        log("  " + line)
    if not changed:
        log("the tail is already closed.")
        return 0
    if not apply:
        log("%d row(s) would change. Nothing written." % len(changed))
        return len(changed)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = os.path.join(retired_root, stamp + "_festival_tail")
    os.makedirs(out, exist_ok=True)
    with io.open(os.path.join(out, "closed_rows.json"), "w", encoding="utf-8") as f:
        json.dump(dumped, f, ensure_ascii=False, indent=1)
    kv_set(db, "commitments", rows)
    kv_set(db, "cast_bonds", bonds)
    for key, rec in plans.items():
        kv_set(db, key, rec)
    db.commit()
    log("the rows as they were are in %s" % out)
    log("%d row(s) written." % len(changed))
    return len(changed)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--db", default="data/world.db")
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--apply", action="store_true", help="write; without it nothing is changed")
    ap.add_argument("--force", action="store_true", help="run even if a bot looks to be holding the save")
    args = ap.parse_args()

    held = bot_is_running(args.db)
    if held and not args.force:
        print("REFUSED: a bot looks to be holding %s:\n  %s\n"
              "Stop it (restart.cmd tomoe) and run this between the stop and the start." % (args.db, held))
        return 2

    cfg = Config(path=args.config)
    db = sqlite3.connect(args.db)
    close_festival(db, cfg, apply=args.apply)
    print("-- the rows the rule cannot see --")
    close_festival_tail(db, cfg, apply=args.apply)
    return 0


if __name__ == "__main__":
    sys.exit(main())
