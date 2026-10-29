"""A fork may only be deleted when one shared file reproduces what it said.

`tools/neutral_gate.py` proves the shared prompts still render to the first
character's originals. This is the other half: before a second character's
forked prompt is deleted, the shared file rendered with HER config has to carry
every rule the fork carried. Otherwise collapsing a fork is quietly deleting
whatever the fork had learned.

It is deliberately not a byte comparison. A fork was written by hand and its
wording drifts from the shared file in ways that do not matter -- "a simulated
girl's" against "a simulated woman's" -- while the thing that does matter is
whether a *rule* went missing. So it compares by line, ignoring lines that
differ only where a hole now stands, and names every line of the fork that has
no home in the rendered shared file. A line it names is either a rule to add
back or a rule you meant to drop; both need a person to say which.

    python tools/fork_gate.py --config config_yukarin.json --fork prompts_yukarin
    python tools/fork_gate.py --config config_yukarin.json --fork prompts_yukarin --only state.txt
"""

import argparse
import difflib
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

from config import Config  # noqa: E402
from neutral_gate import CHARACTER_FILES  # noqa: E402

_WS = re.compile(r"\s+")


def norm(line):
    return _WS.sub(" ", line.strip())


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", default="config_yukarin.json")
    ap.add_argument("--fork", default="prompts_yukarin")
    ap.add_argument("--only", default="", help="one file, to work on it alone")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    cfg = Config(path=args.config)
    names = sorted(f for f in os.listdir(args.fork) if f.endswith((".txt", ".md")))
    if args.only:
        names = [n for n in names if n == args.only]

    clean, dirty = [], []
    for name in names:
        if name in CHARACTER_FILES:
            continue
        shared = os.path.join("prompts", name)
        if not os.path.exists(shared):
            continue
        rendered = cfg.fill(io.open(shared, encoding="utf-8").read().strip(), name)
        fork = io.open(os.path.join(args.fork, name), encoding="utf-8").read().strip()
        have = {norm(l) for l in rendered.splitlines() if norm(l)}
        lost = [norm(l) for l in fork.splitlines() if norm(l) and norm(l) not in have]
        # a line the fork rewrote rather than dropped: close enough to a line
        # that IS there, so nothing was lost, only worded differently
        really = []
        for l in lost:
            near = difflib.get_close_matches(l, have, n=1, cutoff=0.75)
            if not near:
                really.append(l)
        if really:
            dirty.append((name, really))
        else:
            clean.append(name)

    if clean:
        print("\n%d fork(s) fully covered by the shared file; safe to delete:" % len(clean))
        for n in clean:
            print("  ok    %s" % n)
    if dirty:
        print("\n%d fork(s) still say something the shared file does not:" % len(dirty))
        for n, lost in dirty:
            print("  KEEP  %-16s %d line(s)" % (n, len(lost)))
            for l in lost[: (99 if args.verbose else 2)]:
                print("        %s" % l[:150])
    return 1 if dirty else 0


if __name__ == "__main__":
    sys.exit(main())
