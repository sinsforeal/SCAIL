"""Read her assembled prompt the way she would, and flag what she does not have.

The whole prompt is what the persona role is actually given -- her bible, her
style, her beliefs, her people, and the `<situation>` block the machinery
composes fresh every call. The bible and the style are hand-written and were
checked by the forge. **The situation block is not**: it is assembled by code
that was written around one character, so anything in it that assumes a body, a
day, a school, a household or an app arrives without anybody having chosen it.

This dumps both and greps them for concepts the character's `existence` says she
has not got. Every hit is a line she would read as true about herself.

    python tools/leaks.py --config config_yukarin.json
"""

import argparse
import io
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

# What each property of an existence rules out, as words that would actually
# appear. Each was taken from a real assembled prompt rather than imagined.
LACKS = {
    "embodied": [
        (r"\ballowance\b|\byen (left|on the)\b|\bMONEY\b", "money a body spends"),
        (r"\bbike\b|\bcar when he is\b|\bon foot\b|\btrains on your lines\b|\bbuses?\b", "getting somewhere"),
        (r"\bhungry\b|\bhunger\b|\bate\b|\bmeal\b|\bbath\b|\bsleep\b|\btired\b", "a body's day"),
        (r"\bwearing\b|\bwhat you are holding\b|\byour hair\b|\bthe heat\b", "a body in a place"),
        (r"\bweather\b|\bit is \d+C\b|\bhumid", "weather on skin"),
    ],
    "in_world": [
        (r"\bschool\b|\bclass\b|\bhomeroom\b|\bclassmates?\b", "school"),
        # LINE is the messenger. Matched case-sensitively: with re.I it also
        # matches the ordinary word "line", and flagged "blank line between
        # separate bubbles" as evidence of a friend circle -- the same
        # substring fault this project has now paid for six times.
        (r"\bgroup chat\b|\bthe group\b|(?-i:\bLINE\b)|\byour friends\b", "a circle"),
        (r"\bmum\b|\bmom\b|\bdad\b|\byour brother\b|\bfamily dinner\b", "family in the house"),
        (r"\bTHE DAY'S LEDGER\b|\bwhere she was, with whom\b", "a day with places in it"),
        (r"\byour room\b|\bthe kitchen\b|\bthe station\b", "somewhere to be"),
    ],
    "resident": [
        (r"\bopened the app\b|\bthe app on your phone\b|\byou have not opened\b", "an app she would open -- she is resident and simply sees"),
        (r"\bhis account\b|\bthe account lately\b|\bliked @", "an account of his she posts from"),
    ],
}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", default="config_yukarin.json")
    ap.add_argument("--dump", default="", help="write the whole assembled prompt here")
    args = ap.parse_args()

    tmp = os.path.join(tempfile.gettempdir(), "leaks.db")
    for suffix in ("", "-wal", "-shm", ".lock"):
        try:
            os.remove(tmp + suffix)
        except OSError:
            pass

    import scail
    argv = sys.argv
    sys.argv = ["scail.py", "--console", "--no-sensors", "--config", args.config, "--db", tmp]
    try:
        a = scail.parse_args()
    finally:
        sys.argv = argv
    app = scail.App(a)
    ex = app.config.character.existence

    scene = {"location": "his machine", "activity": "he is typing", "with": "alone",
             "phone_access": "free", "setting": "indoors", "sensory": "a window open",
             "inner": "", "events": [], "share_worthy": False, "share_hint": "",
             "next_tick_minutes": 20}
    whole = app.persona.system_for("him") + "\n\n" + app.persona.carried_for() + "\n\n<situation>\n" + \
        app.persona._situation(scene, "", [], "") + "\n</situation>"
    if args.dump:
        open(args.dump, "w", encoding="utf-8").write(whole)
        print("wrote %s (%d chars)" % (args.dump, len(whole)))

    props = {"embodied": ex.embodied, "in_world": ex.in_world,
             "resident": str(ex.sees_him).lower() == "resident"}
    print("\n%s -- embodied=%s in_world=%s sees_him=%s"
          % (app.config.character.name, ex.embodied, ex.in_world, ex.sees_him))
    print("prompt is %d chars\n" % len(whole))

    lines = whole.split("\n")
    total = 0
    for prop, rules in LACKS.items():
        want = props.get(prop)
        # "resident" is a lack when she IS resident; the others are lacks when false
        lacking = want if prop == "resident" else (want is False)
        if not lacking:
            continue
        for rx, what in rules:
            hits = [ln.strip() for ln in lines if re.search(rx, ln, re.I)]
            if not hits:
                continue
            total += len(hits)
            print("  %-34s %d line(s)" % (what, len(hits)))
            for h in hits[:2]:
                print("      %s" % h[:132])
    print("\n%d line(s) she would read as true about herself and are not." % total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
