"""Her generated lines against the way the tape says she writes.

The method, stated plainly so it can be argued with:

  1. `yukarin/audit/countable.json` holds 69 markers counted by hand over the
     whole corpus -- 99 episodes, 567,846 characters. Each has a total, the
     number of episodes it appears in, and therefore a rate per 100,000
     characters. That file is the measurement; this tool invents no numbers.
  2. Take the lines she has actually generated -- her side of the chat, out of
     her own save -- and count the same markers in them.
  3. For each marker, the corpus rate gives an EXPECTED count in a body of text
     that size. Compare the observed count against a Poisson interval around
     that expectation.
  4. Report only the markers where the volume is enough for the comparison to
     mean anything, and say so explicitly for the rest.

Step 4 is the whole design. A marker at 46.5 per 100k needs about 6,500
characters of her writing before one occurrence is even expected, and her first
evening produced 300. Reporting "えっとね: expected 0.14, observed 0 -- DRIFT"
would be a lie dressed as arithmetic, and it is the mistake this tool exists to
refuse to make.

    python tools/voice_verify.py                       # her save, all of it
    python tools/voice_verify.py --min-expected 5      # stricter
    python tools/voice_verify.py --file lines.txt      # any text instead
"""

import argparse
import io
import json
import math
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

COUNTABLE = os.path.join("yukarin", "audit", "countable.json")


def poisson_hi(lam, p=0.99):
    """Largest k with P(X <= k) < p, for a Poisson with this mean.

    The upper end of what "no change" could plausibly produce. Used rather
    than a normal approximation because the counts here are small, which is
    exactly the regime where the normal approximation invents findings.
    """
    if lam <= 0:
        return 0
    cum, term, k = math.exp(-lam), math.exp(-lam), 0
    while cum < p and k < 10000:
        k += 1
        term *= lam / k
        cum += term
    return k


def poisson_lo(lam, p=0.01):
    if lam <= 0:
        return 0
    cum, term, k = math.exp(-lam), math.exp(-lam), 0
    while cum < p and k < 10000:
        k += 1
        term *= lam / k
        cum += term
    return k


def her_lines(db):
    if not os.path.exists(db):
        raise SystemExit("no save at %s" % db)
    cx = sqlite3.connect(db)
    rows = cx.execute("SELECT text FROM messages WHERE role='assistant' ORDER BY ts").fetchall()
    return [r[0] for r in rows if r[0]]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--db", default="data/yukarin.db")
    ap.add_argument("--file", default="", help="read her lines from a text file instead")
    ap.add_argument("--min-expected", type=float, default=3.0,
                    help="a marker is only judged when this many occurrences are expected")
    args = ap.parse_args()

    meas = json.load(io.open(COUNTABLE, encoding="utf-8"))
    corpus_chars = float(meas["chars"])

    if args.file:
        lines = [l for l in io.open(args.file, encoding="utf-8").read().split("\n") if l.strip()]
    else:
        lines = her_lines(args.db)
    text = "\n".join(lines)
    n = len(text)

    print("\n  HER LINES: %d message(s), %d characters" % (len(lines), n))
    print("  THE TAPE  : %d episodes, %d characters (yukarin/audit/countable.json)"
          % (meas["episodes"], meas["chars"]))
    if not n:
        print("\n  nothing of hers to measure yet.\n")
        return 0

    judged, quiet, flags = [], [], []
    for c in meas["claims"]:
        total = int(c["total"])
        if not total:
            # a marker the tape never shows: the test is one-sided, and any
            # occurrence at all is worth a look
            hits = sum(text.count(m) for m in c["markers"])
            if hits:
                flags.append((c["id"], "absent from the tape, %d here" % hits, list(c["markers"])[:2]))
            continue
        rate = total / corpus_chars
        lam = rate * n
        hits = sum(text.count(m) for m in c["markers"])
        if lam < args.min_expected:
            quiet.append((c["id"], lam, hits))
            continue
        lo, hi = poisson_lo(lam), poisson_hi(lam)
        verdict = "ok" if lo <= hits <= hi else ("HIGH" if hits > hi else "LOW")
        judged.append((c["id"], lam, hits, lo, hi, verdict, list(c["markers"])[:2]))

    if judged:
        print("\n  JUDGED -- enough of her writing for the comparison to mean something")
        print("  %-26s %8s %6s %-12s %s" % ("marker", "expected", "seen", "plausible", ""))
        for cid, lam, hits, lo, hi, verdict, mk in judged:
            print("  %-26s %8.1f %6d  %2d-%-8d %-5s %s"
                  % (cid[:26], lam, hits, lo, hi, verdict, "/".join(mk)))
    else:
        print("\n  JUDGED: none. There is not enough of her writing yet for any single")
        print("  marker to be testable -- see the next block for how much would be needed.")

    if quiet:
        quiet.sort(key=lambda x: -x[1])
        print("\n  NOT TESTABLE AT THIS VOLUME (%d markers). The corpus rate predicts fewer" % len(quiet))
        print("  than %.0f occurrences in %d characters, so neither presence nor absence" % (args.min_expected, n))
        print("  says anything. Shown with the volume of her writing that would be needed.")
        for cid, lam, hits in quiet[:12]:
            need = args.min_expected / (lam / n) if lam else 0
            print("    %-26s expected %5.2f, seen %d -- needs ~%s characters"
                  % (cid[:26], lam, hits, f"{int(need):,}" if need else "?"))
        if len(quiet) > 12:
            print("    ... and %d more" % (len(quiet) - 12))

    if flags:
        print("\n  NEVER ON THE TAPE, PRESENT HERE (%d)" % len(flags))
        for cid, why, mk in flags:
            print("    %-26s %s  (%s)" % (cid[:26], why, "/".join(mk)))

    print("\n  Read this as a screen, not a verdict. `docs/verification.md` is the method")
    print("  and the seven ways it can mislead you.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
