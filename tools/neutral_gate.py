"""A mechanism prompt with the person taken out must still be her prompt.

`tomoe/prompts/showrunner.txt` opened by naming a fifteen-year-old in Nerima and
listing her friends as the arcs to choose from. That is a mechanism file with a
person pasted into it, and a second character invoking it is handed the first
one's life. The fix is to leave the rule in the file and mark the person's place
with a `{{TOKEN}}` that the character fills (`Config.fill`).

**The rule that makes it safe to do this to a live character's prompts: a
token's value for the character the prompt was written around is the exact span
that came out of it.** Render her fills back into the tokenised file and you get
the original file, byte for byte. If that holds, her behaviour cannot have
changed, and the check is mechanical rather than a judgement about whether two
wordings mean the same thing.

This is that check. It compares every tokenised prompt, rendered with the first
character's fills, against the copy taken before the change, and fails on one
differing byte. It is not a style opinion and it cannot pass by accident.

    python tools/neutral_gate.py            # against the newest retired snapshot
    python tools/neutral_gate.py --baseline data/retired/<ts>_neutral/prompts
"""

import argparse
import difflib
import glob
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

from config import Config  # noqa: E402

# The files that are the person rather than the machinery. These are ported by
# hand per character (`prompts_yukarin/voice_as_she_writes_in_text/bible.md`) and are the one place where a
# copy per character is the right answer, because there is nothing shared in
# them to share.
CHARACTER_FILES = {"bible.md", "style.md", "style_ja.md"}


def newest_baseline():
    """The snapshot taken before the first prompt was tokenised. Named rather
    than guessed: the retired directory carries the reason in its name."""
    dirs = sorted(glob.glob(os.path.join("data", "retired", "*_neutral", "prompts")))
    return dirs[-1] if dirs else ""


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--baseline", default="", help="the copy taken before tokenising")
    ap.add_argument("--config", default="config.json",
                    help="the config of the character the prompts were written around")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    base = args.baseline or newest_baseline()
    if not base or not os.path.isdir(base):
        print("no baseline snapshot found; nothing can be verified")
        return 1

    cfg = Config(path=args.config)
    tokenised, ok, bad = 0, 0, []
    for name in sorted(os.listdir("prompts")):
        if not name.endswith((".txt", ".md")):
            continue
        # A file that IS her is not a mechanism file and does not get holes cut
        # in it. The bible and the style files are the character; every other
        # prompt runs the machinery and only mentions her. Taking a token out
        # of the bible would be replacing her with a reference to her.
        if name in CHARACTER_FILES:
            if "[[" in io.open(os.path.join("prompts", name), encoding="utf-8").read():
                bad.append((name, "this file IS the character; it must not carry holes"))
            continue
        live = os.path.join("prompts", name)
        old = os.path.join(base, name)
        text = io.open(live, encoding="utf-8").read()
        if "[[" not in text:
            continue
        tokenised += 1
        if not os.path.exists(old):
            bad.append((name, "no copy in the baseline: nothing to compare against"))
            continue
        rendered = cfg.fill(text.strip(), name)
        original = io.open(old, encoding="utf-8").read().strip()
        if rendered == original:
            ok += 1
            if args.verbose:
                print("  ok    %-26s renders back exactly" % name)
            continue
        a, b = original.splitlines(), rendered.splitlines()
        diff = [l for l in difflib.unified_diff(a, b, "before", "rendered", n=0, lineterm="")][:8]
        bad.append((name, "\n        ".join(diff)))

    print("\n%d tokenised prompt(s); %d render back to the original exactly." % (tokenised, ok))
    if bad:
        print("\n%d DO NOT, and each one is a change to a live character's behaviour:" % len(bad))
        for name, why in bad:
            print("  FAIL  %s\n        %s" % (name, why))
        return 1
    if tokenised:
        print("Her prompts are unchanged; the holes are the only difference.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
