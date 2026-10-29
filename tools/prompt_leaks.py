"""Every role's prompt, rendered as this character, scanned for another one.

`tools/leaks.py` reads the assembled persona prompt and asks whether it claims
things her existence says she has not got. That is one role out of sixty. The
other fifty-nine are the mechanism prompts, and until they were neutralised
thirty-six of them named a fifteen-year-old in Nerima and listed her friends --
so a second character invoking any of them was handed the first one's life,
silently, with nothing checking.

This renders every prompt her config points at, through `Config.fill`, and
looks for the other character in the result. It is the wide check; `leaks.py`
is the deep one on the single role that speaks in her voice.

    python tools/prompt_leaks.py --config config_yukarin.json
    python tools/prompt_leaks.py --config config.json --against yukarin
"""

import argparse
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

from config import Config  # noqa: E402

# Whose life would be a leak. Latin names carry a word boundary because this
# project has now paid seven times for a substring match: `mom` inside
# `moment`, `Aya` inside `Ayako` (a real voice actress, in a prompt about
# voice actors), `Kaito` inside `Kaitou Tenshi`.
OTHERS = {
    "tomoe": r"朋絵|古賀|海斗|練馬|亜矢|玲奈|日南子|\bTomoe\b|\bKoga\b|\bKaito\b|\bRena\b"
             r"|\bHinako\b|\bAya\b|\bNerima\b|\bIkebukuro\b|\bSeibu\b|\bYumi\b|\bKenji\b",
    "yukarin": r"ゆかり|田村|\bYukari\b|\bTamura\b|文化放送|黒うさぎ",
}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", default="config_yukarin.json")
    ap.add_argument("--against", default="tomoe", choices=sorted(OTHERS),
                    help="whose life counts as a leak here")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    cfg = Config(path=args.config)
    rx = re.compile(OTHERS[args.against])
    who = getattr(cfg.character, "name", "?")
    roles = sorted((cfg.raw.get("models") or {}).items())

    checked = holes = leaked = 0
    findings, empty = [], []
    for role, spec in roles:
        if not isinstance(spec, dict) or not spec.get("prompt"):
            continue
        path = spec["prompt"]
        if not os.path.exists(path):
            continue
        checked += 1
        raw = io.open(path, encoding="utf-8").read()
        text = cfg.fill(raw, role)
        n = len(rx.findall(text))
        if n:
            leaked += 1
            line = next((l.strip() for l in text.splitlines() if rx.search(l)), "")
            findings.append((role, path, n, line))
        if "(not established for this character)" in text:
            holes += 1
            empty.append((role, path))

    print("\n%s -- %d role prompt(s) rendered" % (who, checked))
    if findings:
        print("\n%d carry %s's life:" % (len(findings), args.against))
        for role, path, n, line in findings:
            print("  %-18s %-32s %d" % (role, path, n))
            print("      %s" % line[:150])
    else:
        print("no role prompt carries %s's life." % args.against)

    if empty:
        print("\n%d role(s) render a hole this character has not filled:" % len(empty))
        for role, path in empty:
            print("  %-18s %s" % (role, path))
        print("  -- a hole is honest where the role never runs for her, and a")
        print("     gap to fill where it does. It is never the other character.")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
