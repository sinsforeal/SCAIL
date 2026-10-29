"""No default in the library is one person's file.

    python tools/defaults_person_test.py     # exit 1 on any finding; run by smoke

`config.json` is generated from `config.py:DEFAULTS` and backfilled: a key a
character's config does not carry is filled in from the defaults on her first
load and written into her own file, where it then looks authored. So a default
that names one character's household, roster, map or save is inherited by the
next character in silence -- which is what the fourth character's first day
was, in full: the first character's household, map, roster and cast sheets.

This builds nothing. It walks the defaults with the same path finder the
isolation check uses (`tools/isolation.paths`) and fails on any path-shaped
value that is neither the machine's, nor a mechanism prompt's, nor the
shared world's own. Those three categories are the same ones
`tools/isolation.py` classifies a shared file into, imported from there so the
two cannot drift.

It also names the seventeen person-shaped keys explicitly and fails if one of
them is not empty, so that re-pointing one at a file -- rather than adding a
new key -- is caught with the key named rather than by a prefix rule.
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

from config import DEFAULTS
from tools import isolation

# The world's own files, which belong to everybody in that world rather than
# to one person in it: the nation's public holidays, what the ward puts on,
# and the directory the worlds live in. `Config.WORLD_KEYS` blanks all three
# for a character with no world, and `tools/isolation.py` classifies them as
# the world's when two characters share one.
WORLD_OWN = {
    "world.holidays_file": "the nation's public holidays: not a person's and not a world's either",
    "world.local_events_file": "what the ward puts on, which is the world's and is read by everybody in it",
    "world.shared_dir": "the directory the worlds live in, one per world",
}

# Every person-shaped key, named. The value must be empty here and come from
# the character's own config.
PERSON_KEYS = (
    ("character.style_prompt", "her speech guide"),
    ("character.style_ja_prompt", "her speech guide in the other language"),
    ("character.cast_file", "the roster of who is around her"),
    ("character.cast_sheets_dir", "their sheets"),
    ("character.own_cast_file", "her own circle, in a world she does not keep"),
    ("character.own_cast_sheets_dir", "her own circle's sheets"),
    ("character.voice_rules_file", "how each person around her may sound"),
    ("character.beliefs_file", "what she has decided about him"),
    ("character.self_beliefs_file", "what she has decided about herself"),
    ("character.neutral_file", "the values for the character-shaped holes in the shared prompts"),
    ("models.persona.prompt", "who she is, as a prompt"),
    ("world.household_file", "her family as an economy"),
    ("world.geography_file", "her map"),
    ("world.places_file", "the places she keeps going back to"),
    ("world.school_calendar_file", "her school's year"),
    ("world.zeitgeist_file", "what is going round where she is"),
    ("world.taste_file", "her taste sheet"),
    ("world.home_file", "her flat, for a character with no world"),
    ("cast.mechanisms_dir", "what the people around her do"),
    ("cast.types_file", "the type each of them was written from"),
    ("logging.db_path", "her save"),
)


def _dig(d, dotted):
    cur = d
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def main():
    findings = []

    print("[defaults] every person-shaped key is empty")
    for key, what in PERSON_KEYS:
        v = _dig(DEFAULTS, key)
        if v is None:
            findings.append("%s is not in DEFAULTS at all (%s)" % (key, what))
            print("  FAIL %-34s missing" % key)
        elif str(v).strip():
            findings.append("%s defaults to %r, which is one character's %s" % (key, v, what))
            print("  FAIL %-34s %r" % (key, v))
    if not findings:
        print("  ok   %d key(s), all empty" % len(PERSON_KEYS))

    print("[defaults] every path left in the defaults is the machine's, a mechanism prompt's, "
          "or the world's")
    allowed = tuple(isolation.MACHINE) + tuple(isolation.NEUTRAL)
    left = []
    for key, value in sorted(isolation.paths(DEFAULTS).items()):
        if key.startswith(allowed) or key in WORLD_OWN:
            continue
        left.append("%s = %s" % (key, value))
    if left:
        findings.extend(left)
        print("  FAIL %d path(s) belong to nobody the rules know about:" % len(left))
        for line in left[:12]:
            print("       " + line)
    else:
        print("  ok   %d path(s), every one of them accounted for"
              % len(isolation.paths(DEFAULTS)))

    # A value that IS a person without being a path: `PATHY` never sees these,
    # because they have no directory and no extension, and one of them
    # configured a second character to publish the first one's face.
    print("[defaults] and no default is a person written as a bare name")
    named = [(k, _dig(DEFAULTS, k)) for k in isolation.PERSON_KEYS
             if str(_dig(DEFAULTS, k) or "").strip()]
    if named:
        findings.extend("%s = %r" % (k, v) for k, v in named)
        print("  FAIL " + "; ".join("%s = %r" % (k, v) for k, v in named))
    else:
        print("  ok   %d key(s) checked" % len(isolation.PERSON_KEYS))

    print()
    if findings:
        print("[defaults] %d finding(s): a config generated from the defaults alone would name "
              "a person" % len(findings))
        return 1
    print("[defaults] a config generated from the defaults alone names no file belonging to "
          "a person")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
