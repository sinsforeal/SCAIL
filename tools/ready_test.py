"""What a character still needs before she can be run.

`tools/character_test.py` asks whether a sheet is coherent. This asks a
different question: if the loop were pointed at her tomorrow, what would it
demand that does not exist? Every answer is a file that is missing, a prompt
that is not ported, or a module that assumes something her sheet says is not
true.

    python tools/ready_test.py --sheet data/characters/yukarin.json
"""

import argparse
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

from config import Config                      # noqa: E402
from tools.forge import prompts, PROMPT_DIR    # noqa: E402

# Which modules stop making sense when a property of her existence is false.
# Read off the code rather than guessed: each name is a module whose whole job
# is the thing named.
GATED = {
    "embodied": ["embodied/health.py", "embodied/body.py", "sim/needs.py"],
    "in_world": ["sim/schedule.py", "sim/ledger.py", "embodied/situation.py", "tomoe/family.py",
                 "tomoe/cast.py", "tomoe/exchange.py", "tomoe/social.py", "tomoe/scenery.py"],
}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sheet", required=True)
    ap.add_argument("--config", default="config.json",
                    help="her own config, if she has one -- otherwise this reports the other "
                         "character's file paths and every one of them looks wrong")
    ap.add_argument("--port", default="prompts_yukarin", help="where her ported prompts are")
    args = ap.parse_args()

    cfg = Config(path=args.config, character_file=args.sheet)
    # whose file is it? A path is HERS when it differs from what the default
    # config names for the same key. Guessing from the filename cannot tell a
    # deliberate share from an unported leftover.
    base = Config(path="config.json") if os.path.abspath(args.config) != os.path.abspath("config.json") else None
    sheet = json.load(open(args.sheet, encoding="utf-8"))
    ex = cfg.character.existence
    who = (sheet.get("name") or {}).get("full") or sheet.get("id")

    print("\n%s -- embodied=%s in_world=%s sees_him=%s\n" % (who, ex.embodied, ex.in_world, ex.sees_him))

    # ---- 1. the data files the character section names
    print("-- data files her config points at")
    missing = []
    for key in ("cast_file", "cast_sheets_dir", "voice_rules_file", "beliefs_file",
                "self_beliefs_file", "style_prompt", "style_ja_prompt"):
        path = getattr(cfg.character, key, "")
        if not path:
            continue
        ok = os.path.exists(path)
        # a path under prompts/ is the OTHER character's; hers would be in the port
        ported = os.path.join(args.port, os.path.relpath(path, PROMPT_DIR)) if path.startswith(PROMPT_DIR) else None
        if ported and os.path.exists(ported):
            print("  ok    %-18s %s  (ported)" % (key, ported))
        elif ok:
            theirs = getattr(base.character, key, None) if base else None
            if base is not None and theirs != path:
                print("  ok    %-18s %s" % (key, path))
            else:
                print("  SHARED %-17s %s  -- the other character's file, not hers" % (key, path))
                missing.append(key)
        else:
            print("  MISS  %-18s %s" % (key, path))
            missing.append(key)

    # ---- 2. prompts
    print("\n-- prompts")
    allp = prompts()
    done = [p for p in allp if os.path.exists(os.path.join(args.port, os.path.relpath(p, PROMPT_DIR)))]
    print("  %d of %d ported" % (len(done), len(allp)))

    # which roles a resident, disembodied character still needs
    needed = ["state.txt", "director.txt", "editor.txt",
              "intent.txt", "nudge.txt", "diary.txt", "timeline.txt", "reflect.txt",
              "him_profile.txt", "habits_him.txt", "expect_him.txt", "ick.txt",
              "wonder.txt", "recall.txt", "memory" ".txt", "coherence.txt"]
    gap = [n for n in needed if not os.path.exists(os.path.join(args.port, n))
           and os.path.exists(os.path.join(PROMPT_DIR, n))]
    print("  still needed for a resident character: %d" % len(gap))
    for n in gap:
        print("      %s" % n)

    # Who she is and how she writes are not found by name in the port
    # directory: a character can carry more than one written voice, one
    # directory per approach, and which one runs is whatever the config points
    # at. Looking for `bible.md` beside the mechanism prompts finds the
    # unselected one or nothing.
    for label, path in (("bible", cfg.models.persona.prompt),
                        ("speech guide", cfg.character.style_prompt)):
        print("  %-5s %-13s %s" % ("ok" if os.path.exists(path) else "MISS", label, path))

    # ---- 3. modules that assume what her sheet denies
    print("\n-- modules that assume something her sheet says is not true")
    off = []
    for prop, mods in GATED.items():
        if not getattr(ex, prop, True):
            for m in mods:
                if os.path.exists(m):
                    off.append((prop, m))
    if not off:
        print("  none")
    for prop, m in off:
        print("  %-9s is false, so %s has nothing to do" % (prop, m))
    print("  -- none of these consult existence yet; that is the wiring job")

    # ---- 4. the primitives: is there anything to move them?
    print("\n-- the primitives")
    import subprocess
    src = open("sim/primitives.py", encoding="utf-8").read()
    callers = []
    for root, _d, files in os.walk("."):
        if any(x in root for x in (".git", "__pycache__", "retired", "logs")):
            continue
        for f in files:
            if not f.endswith(".py") or f == "primitives.py":
                continue
            p = os.path.join(root, f)
            try:
                t = open(p, encoding="utf-8").read()
            except OSError:
                continue
            if "primitives" in t and "import" in t:
                callers.append(p.replace("\\", "/").lstrip("./"))
    print("  the store and the derivations exist (%d lines)" % len(src.splitlines()))
    print("  modules that read or write them: %s" % (", ".join(callers) if callers else "NONE"))
    # This used to say nothing fed them. It does now: every one of the nine has
    # an event that writes it and every derivation gates something the running
    # code does (HISTORY 2026-09-01 15:05). `tools/mechanisms_test.py` is the
    # check; repeating a claim about them here would be a second place to go
    # stale.
    print("  -- fed and gated: `python tools/mechanisms_test.py --config <hers>`")
    print("     walks the arc with no model call and names which event writes")
    print("     each of the nine.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
