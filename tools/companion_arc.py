"""Three months of an ordinary companionable relationship, and what she becomes.

`tools/mechanisms_test.py` asks whether each mechanism opens and shuts at the
right moment. This asks the longer question: run a character forward through a
relationship that is going *well* -- he writes several times a day, she watches
him, she keeps the odd promise, she writes most nights -- and see whether the
numbers describe a companion at the end of it.

The first run of this found the thing that mattered. Closeness reached 72 in a
week and **fell to 10 by day ninety**, because a diary entry lowers what he
holds of her and nothing raised it: the one mechanism that gave her a private
interior was quietly dismantling the relationship. That is not visible in a
single tick, in the arc test, or in any generation -- only in a long run.

No model is called and no save is touched: it drives the primitives directly at
rates measured from the first character's real record (a median of six things a
day she tells him about herself, over fourteen days).

    python tools/companion_arc.py --config config_yukarin.json
    python tools/companion_arc.py --days 180 --quiet-diary
"""

import argparse
import io
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", default="config_yukarin.json")
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--messages", type=int, default=4, help="his messages a day")
    ap.add_argument("--looks", type=int, default=6, help="times a day she sees something of his")
    ap.add_argument("--tells", type=int, default=6,
                    help="things a day she tells him about herself (the measured median)")
    ap.add_argument("--quiet-diary", action="store_true", help="she keeps nothing back")
    ap.add_argument("--unanswered", action="store_true",
                    help="he writes and she does not answer: the ledger should run against her")
    args = ap.parse_args()

    tmp = os.path.join(tempfile.gettempdir(), "companion_arc.db")
    for s in ("", "-wal", "-shm", ".lock"):
        try:
            os.remove(tmp + s)
        except OSError:
            pass
    import scail
    import logger
    argv = sys.argv
    sys.argv = ["scail.py", "--console", "--no-sensors", "--config", args.config, "--db", tmp]
    try:
        a = scail.parse_args()
    finally:
        sys.argv = argv
    app = scail.App(a)
    if app.primitives is None:
        print("this character does not use the primitives; there is no arc to run")
        return 0
    p, k = app.primitives, app.state._him_key() or "him"
    logger.log = lambda *x, **kw: None       # the shape, not the trace

    def show(label):
        r = p.row(k)
        print("  %-22s %3.0f/%3.0f  %3.0f/%3.0f  %3.0f  %+5.0f  %3.0f | %4.0f %5.0f %4.0f %5.0f"
              % (label, r["exposure_hers"], r["exposure_his"], r["attention_hers"],
                 r["attention_his"], r["predictability_hers"], r["reciprocity"],
                 r["cost_of_loss"], p.closeness(k), p.attachment(k), p.resentment(k),
                 p.resentment(k)))

    print("\n  %-22s %-9s %-9s %-4s %-6s %-4s | %s"
          % ("", "exposure", "attention", "he", "ledger", "cost", "close attach guilt resent"))
    print("  %-22s %-9s %-9s %-4s %-6s %-4s |"
          % ("", "hers/his", "hers/his", "pred", "", ""))
    show("day 0")
    marks = {1, 7, 30, 60, args.days}
    for day in range(1, args.days + 1):
        for _ in range(args.messages):
            p.note_from_him(k, 0.7, answered=True)
            # and she answers most of them, which is what makes an exchange an
            # exchange rather than a debt
            if not args.unanswered:
                p.she_answered(k, ["a reply of about twenty-eight words " * 1] * 4)
        for _ in range(args.looks):
            p.observe(k, "something on his machine")
        for _ in range(args.tells):
            p.disclosed(k, "something she told him about herself")
        if day % 7 == 0:
            p.gave(k, "she did the thing she said she would")
        if not args.quiet_diary and day % 2 == 0:
            p.kept_private(k, "an evening she wrote down and did not tell him")
        p.decay(k, 24.0)
        p.accrue(k, 24.0)
        if day in marks:
            show("after %d day%s" % (day, "" if day == 1 else "s"))

    print("\n  gates: admitted %s, ick %s, withhold %s, rupture %s, perform %s"
          % (p.admitted(k), p.can_ick(k), p.can_withhold(k), p.can_rupture(k), p.can_perform(k)))
    # affection is derived, not stored, so it has to be driven to its target or
    # the number printed is whatever she booted with -- which is how I first
    # misread a companion as "neutral"
    cw = app.config.state.affection_from
    for _ in range(600):
        app.state._derive_affection_from_primitives(p, k, 1.0, cw)
    print("  affection %d (%s)" % (round(app.state.gauges["affection"]), app.state.affection_band()))
    print("\n  What to look for: closeness that rises and STAYS, a ledger that holds a")
    print("  value rather than decaying to nothing between events, and attachment and")
    print("  cost of loss that still have somewhere to go at ninety days.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
