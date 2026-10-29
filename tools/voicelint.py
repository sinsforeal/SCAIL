"""Run the voice rules over the exchanges already in the save and show what
they would flag.

The rules in `data/voice_rules.json` are regexes over Japanese, and a regex
written by eye is a guess. This runs the real checker over the real record --
every turn in kv `cast_chat` -- so a rule can be measured before it is
trusted: what it catches, what it catches wrongly, and how much of each
speaker it would light up.

Read-only. Touches no model and no live state; the save is opened read-only,
so it is safe against the running bot.

    python tools/voicelint.py                  # every speaker, every rule
    python tools/voicelint.py --rule kansai    # one rule
    python tools/voicelint.py --who Tomoe      # one speaker
    python tools/voicelint.py --lines          # every hit, not just a count

The family caveat: her Hakata is hers at home, so a rule with `skip_when`
naming "family" is suppressed for her turns inside a non-group exchange
opened by her mother, father or brother -- reconstructed here the way
`Exchange._speak` does it live. The "slip" context cannot be reconstructed,
because the gauges of the moment are not stored on the turn, so a handful of
her flagged lines were legitimately licensed when they were written. The
count is an upper bound.
"""
import argparse
import collections
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logger
logger.log = lambda m, to_console=True: None

from config import Config
from sim import roster, voicecheck

FAMILY_ROLES = {"mother", "father", "sibling"}


def turns_from(config, db_path):
    """Every stored turn, with the context its exchange gives it."""
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    row = con.execute("select value from kv where key='cast_chat'").fetchone()
    con.close()
    if not row:
        return []
    out = []
    for ex in json.loads(row[0]):
        opener, kind = ex.get("who", ""), ex.get("kind", "")
        # by role, not by label: the record names its speakers in Japanese
        family = roster.role_of(config, opener) in FAMILY_ROLES and kind != "group"
        for t in ex.get("turns", []):
            who = t.get("who") or "?"
            role = roster.role_of(config, who)
            ctx = {"family"} if (family and (role == "self" or role in FAMILY_ROLES)) else set()
            out.append({"who": who, "ja": t.get("ja") or "", "date": ex.get("date", ""),
                        "hm": t.get("hm", ""), "kind": kind, "opener": opener,
                        "context": ctx})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/world.db")
    ap.add_argument("--rule", default="", help="only this rule id")
    ap.add_argument("--who", default="", help="only this speaker")
    ap.add_argument("--lines", action="store_true", help="print every hit")
    ap.add_argument("--context", action="store_true",
                    help="ignore the family licence and flag everything")
    ap.add_argument("--register", action="store_true",
                    help="the register fingerprint per speaker and room, and the week's drift")
    a = ap.parse_args()

    config = Config()
    rows = turns_from(config, a.db)
    if not rows:
        print("no exchanges in the save; nothing to check")
        return
    if a.register:
        from tools import register
        fp = register.fingerprint(rows)
        print(f"{len(rows)} turns; markers per message, by speaker and room\n")
        keys = list(register.MARKERS)
        print(f"{'speaker':<10}{'room':<10}{'n':>4}{'chars':>7}  " + " ".join(f"{k:>6}" for k in keys))
        for (who, kind), v in sorted(fp.items()):
            print(f"{who:<10}{kind:<10}{v['n']:>4}{v['chars']:>7.0f}  " + " ".join(f"{v[k]:>6.2f}" for k in keys))
        print("\nroom contrast (mean |group - line| over the markers; 0 = the same person in both rooms):")
        for who, v in sorted(register.room_contrast(fp).items(), key=lambda kv: kv[1]["distance"]):
            print(f"  {who:<10} {v['distance']:.3f}  (group {v['group_n']} turns, {v['chars_group']:.0f} chars; line {v['line_n']}, {v['chars_line']:.0f})")
        print("\ndistance from the cast mean (higher is more their own voice):")
        for who, d in sorted(register.distinctness(fp).items(), key=lambda kv: -kv[1]):
            print(f"  {who:<10} {d:.3f}")
        print("\nthis week against last (markers that moved; FLATTENING is movement toward everyone else):")
        for who, v in sorted(register.drift(rows).items()):
            tag = "  FLATTENING" if v["flattening"] else ""
            print(f"  {who:<10} {v['n_before']}->{v['n_now']} turns  {v['distinct_before']:.3f}->{v['distinct_now']:.3f}{tag}")
            print(f"             " + ("; ".join(v["moved"]) or "steady"))
        return
    if a.who:
        rows = [r for r in rows if r["who"] == a.who]

    per = collections.defaultdict(lambda: collections.Counter())
    hits = collections.defaultdict(list)
    speakers = collections.Counter(r["who"] for r in rows)

    for r in rows:
        ctx = () if a.context else r["context"]
        for key, rid, why, hit in voicecheck.check(config, r["ja"], who=r["who"], context=ctx):
            if a.rule and rid != a.rule:
                continue
            per[r["who"]][rid] += 1
            hits[(r["who"], rid)].append((r["date"], r["hm"], hit, r["ja"], why))

    print(f"{len(rows)} turns from {a.db}"
          + (" (family licence ignored)" if a.context else ""))
    print()
    print(f"{'speaker':<12}{'turns':>6}  flagged")
    print("-" * 64)
    for who, n in speakers.most_common():
        if a.who and who != a.who:
            continue
        flags = per.get(who) or collections.Counter()
        total = sum(flags.values())
        detail = ", ".join(f"{rid} {c}" for rid, c in flags.most_common()) or "-"
        pct = f"{100 * total // n:>3d}%" if n else "   -"
        print(f"{who:<12}{n:>6}  {total:>3} {pct}  {detail}")

    if a.lines:
        print()
        for (who, rid), rowlist in sorted(hits.items()):
            print(f"=== {who} / {rid} -- {rowlist[0][4]} ({len(rowlist)})")
            # a turn is often several lines and the match is rarely in the
            # first of them, so the window follows the match; printing the
            # head of the turn made real hits look like phantoms
            for date, hm, hit, ja, _why in rowlist:
                flat = " ".join(ja.split())
                i = flat.find(hit)
                lo = max(0, i - 34)
                snip = ("..." if lo else "") + flat[lo:i + len(hit) + 40]
                print(f"  {date} {hm} [{hit}] {snip}")
            print()


if __name__ == "__main__":
    main()
