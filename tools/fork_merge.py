"""Fold one character's forked prompt back into the shared mechanism file.

A fork exists because two characters needed different words from one role. Most
of that difference is not the person and not a judgement -- it is her
condition. She has no shared history with him, no body, no day, and she watches
his machine rather than choosing to open an app. So the shared file can carry
both, with the parts that only apply to one wrapped in a condition
(`Config.fill`, `[[?no_history]]...[[/no_history]]`).

This does the mechanical part of that fold and refuses to guess at the rest.
It aligns the two files line by line and, for every place they differ:

  the fork ADDS a line       -> wrapped in the condition you name and inserted
  the fork REPLACES a line   -> both kept, each under its own side of the
                                condition
  the fork DROPS a line      -> left alone and reported, because deleting a
                                rule from a live character's prompt is not
                                something a script should decide

Then both gates have to pass: `tools/neutral_gate.py` proves the first
character's rendering is unchanged byte for byte, and `tools/fork_gate.py`
proves the shared file still says everything the fork said.

    python tools/fork_merge.py recall.txt --cond no_history
    python tools/fork_merge.py state.txt --cond embodied --sense not
"""

import argparse
import difflib
import io
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)


def wrap(cond, sense, body):
    """`sense` is which way round: "is" keeps the body when the condition
    holds, "not" keeps it when it does not."""
    return "[[%s%s]]%s[[/%s]]" % ("?" if sense == "is" else "^", cond, body, cond)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("name", help="the file, e.g. recall.txt")
    ap.add_argument("--cond", required=True, help="the condition the fork's lines depend on")
    ap.add_argument("--sense", default="is", choices=("is", "not"),
                    help="'is' when the fork's lines apply while the condition holds")
    ap.add_argument("--fork", default="prompts_yukarin")
    ap.add_argument("--dry", action="store_true", help="show the plan, write nothing")
    args = ap.parse_args()

    shared_p = os.path.join("prompts", args.name)
    fork_p = os.path.join(args.fork, args.name)
    for p in (shared_p, fork_p):
        if not os.path.exists(p):
            print("no such file: %s" % p)
            return 2

    a = io.open(shared_p, encoding="utf-8").read().split("\n")
    b = io.open(fork_p, encoding="utf-8").read().split("\n")
    sm = difflib.SequenceMatcher(None, [l.strip() for l in a], [l.strip() for l in b])

    out, added, replaced, dropped = [], 0, 0, 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            out.extend(a[i1:i2])
        elif tag == "insert":
            body = "\n".join(b[j1:j2])
            if body.strip():
                out.append(wrap(args.cond, args.sense, body))
                added += 1
            else:
                out.extend(b[j1:j2])
        elif tag == "replace":
            old, new = "\n".join(a[i1:i2]), "\n".join(b[j1:j2])
            if not new.strip():
                out.extend(a[i1:i2])
                dropped += 1
                continue
            other = "not" if args.sense == "is" else "is"
            out.append(wrap(args.cond, other, old) + wrap(args.cond, args.sense, new))
            replaced += 1
        elif tag == "delete":
            out.extend(a[i1:i2])
            dropped += 1

    text = "\n".join(out)
    print("%s: %d addition(s), %d replacement(s), %d line(s) the fork dropped and I did not"
          % (args.name, added, replaced, dropped))
    if dropped:
        print("  -- a dropped line stays in. If the fork was right to lose it, take it out by hand.")
    if args.dry:
        print("\n(dry run, nothing written)")
        return 0
    stamp = time.strftime("%Y%m%d_%H%M%S") + "_fork_merge"
    keep = os.path.join("data", "retired", stamp)
    os.makedirs(keep, exist_ok=True)
    shutil.copy(shared_p, os.path.join(keep, args.name))
    io.open(shared_p, "w", encoding="utf-8").write(text)
    print("  written; the file before this is in %s" % keep)
    print("  now run: python tools/neutral_gate.py && python tools/fork_gate.py "
          "--config config_yukarin.json --only %s" % args.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
