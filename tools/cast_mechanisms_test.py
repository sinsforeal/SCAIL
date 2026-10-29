"""The mechanisms loader, the renderer and the two checks, on fixtures.

No save, no network and no model call: everything here is a JSON file under
`tools/fixtures/cast_mechanisms/` and the config's list of roles. Three
fixture directories, one claim each -- a sound file, a file with a mechanism
no call renders, and a file carrying one of every fault the validator
exists to catch.

What it proves:

- a sound file validates, and the block it renders is the Japanese and
  nothing else: no id, no `name`, no `class`, no `tier` reaches a prompt;
- a secret reaches the two calls where that person is speaking for herself
  and never the day planner, which writes for everybody at once;
- the byte cap drops the rarest mechanism first and keeps the one that
  fires every day;
- a mechanism whose `readers` name a role no call asks a block for is
  reported DEAD, the way a gauge nothing acts on is;
- a real roster person with no file renders no block at all, so the calls
  go out exactly as they did before anyone wrote a file.

    python tools/cast_mechanisms_test.py
"""
import fnmatch
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

import logger  # noqa: E402
logger.log = lambda m, to_console=True: None

from config import Config  # noqa: E402
from tomoe import cast_mechanisms as cm  # noqa: E402

FIX = os.path.join("tools", "fixtures", "cast_mechanisms")
SOUND, DEAD, BROKEN = (os.path.join(FIX, d) for d in ("sound", "dead", "broken"))

# The vocabulary a personality type is written in. It belongs to the author's
# prior and to the compile table, and it may appear in NOTHING a call reads:
# a model shown behaviour and producing the type is the experiment, and a
# model shown the type is a different and worse one. The four-letter codes
# are matched with their own case, the rest without, and the two files that
# ARE the prior are exempted by path.
TYPE_CODES = ("ESFJ", "ISFJ", "ESTJ", "ISTJ", "ENFJ", "INFJ", "ENTJ", "INTJ",
              "ESFP", "ISFP", "ESTP", "ISTP", "ENFP", "INFP", "ENTP", "INTP")
TYPE_SHORT = ("Fe", "Fi", "Te", "Ti", "Se", "Si", "Ne", "Ni")
TYPE_LONG = ("extraverted feeling", "introverted feeling", "extraverted thinking",
             "introverted thinking", "extraverted sensing", "introverted sensing",
             "extraverted intuition", "introverted intuition")
TYPE_POSITIONS = ("dominant", "auxiliary", "tertiary", "inferior", "extravert", "introvert")

# Where a compiled block, a sheet or a prompt could carry it. `characters` is
# the bundles: a character's own sheet keeps her derived type, and her bundle
# carries a copy of her prompts.
VOCAB_ROOTS = ("data/cast_mechanisms", "data/cast_mechanisms_yukarin", "data/characters",
               "characters",
               "prompts", "prompts_yukarin", "tomoe/prompts", "yukarin/prompts")
# the author's prior itself, which is the one place the vocabulary belongs
VOCAB_EXEMPT = (os.path.join("data", "characters", "types"),)
# and a character's own sheet, for the same reason: her type is derived from her
# behaviour and kept there, and no call reads the file (docs/character-method.md
# 3.6). Exempted per file, because everything else in her bundle is scanned.
VOCAB_EXEMPT_FILES = ("characters/*/sheet.json",)

fails = []


def check(label, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + label + (("  -- " + detail) if detail else ""))
    if not ok:
        fails.append(label)


def main():
    cfg = Config("config.json")
    print("[cast_mechanisms] the fixtures")

    # --- the loader and the validator
    data = cm.load(cfg, "fixture-girl", SOUND)
    check("a sound file loads", bool(data.get("mechanisms")),
          "%d mechanisms, %d drivers, %d secret(s)"
          % (len(data.get("mechanisms") or []), len(data.get("drivers") or []),
             len(data.get("secrets") or [])))
    problems = cm.validate(cfg, SOUND)
    check("a sound file has no problems", not problems, "; ".join(problems[:3]))

    check("a person with no file renders nothing",
          cm.block_ja(cfg, "nobody-has-written-this-one", "cast_turn", SOUND) == "")

    # --- what reaches a prompt, and what never does
    turn = cm.block_ja(cfg, "fixture-girl", "cast_turn", SOUND)
    check("the block renders for the speaker's own call", bool(turn), "%d chars" % len(turn))
    check("the mechanism that fires every day is in it", "速さ" in turn)
    leaked = [w for w in ("fixture.answers-first", "answers before anyone else",
                          "authored", "hers", "high", "readers", "cast_turn") if w in turn]
    check("no id, no name, no class, no tier, no role name in the block",
          not leaked, ", ".join(leaked))

    day = cm.block_ja(cfg, "fixture-girl", "cast_day", SOUND)
    check("a mechanism kept from the planner is not in the planner's block",
          "話を逸らす" in turn and "話を逸らす" not in day)

    # --- the secret
    beat = cm.block_ja(cfg, "fixture-girl", "cast_beat", SOUND)
    secret = "試験に落ちた"
    check("the secret is in her own turn and her own beat",
          secret in turn and secret in beat)
    check("the secret is not in the day planner, which writes for everybody",
          secret not in day)
    planner = cm.block_for_planner(cfg, ["fixture-girl"], SOUND)
    check("the secret is not in the planner's whole-cast block",
          bool(planner) and secret not in planner, "%d chars" % len(planner))

    # --- the cap
    full = cm.block_ja(cfg, "fixture-girl", "cast_turn", SOUND, cap=10000)
    rare, high = "既読だけ", "速さ"
    small = cm.block_ja(cfg, "fixture-girl", "cast_turn", SOUND, cap=len(full) - 20)
    check("under the cap the rarest goes and the daily one stays",
          rare in full and rare not in small and high in small,
          "%d chars -> %d" % (len(full), len(small)))
    tiny = cm.block_ja(cfg, "fixture-girl", "cast_turn", SOUND, cap=1)
    check("a cap nothing fits under still leaves what is not a mechanism",
          "→" not in tiny and secret in tiny, "%d chars" % len(tiny))

    # --- a mechanism nothing reads
    d = cm.dead(cfg, DEAD)
    ids = [i for _k, i, _r in d]
    check("a mechanism read by a role no call asks for is DEAD",
          ids == ["fixture.dead.never-read"], ", ".join(ids) or "nothing reported")
    check("nothing is DEAD in the sound fixture", not cm.dead(cfg, SOUND))

    # --- every fault the validator exists to catch
    bad = cm.validate(cfg, BROKEN)
    wanted = {
        "an id used twice": "is already used in",
        "a frequency outside the set": "frequency 'often'",
        "a class outside the set": "class 'her own'",
        "a reader that is not a role": "reader 'cast_whatever'",
        "a driver naming a mechanism that is not there": "which is not in this file",
        "a secret held from somebody not on the roster": "is not on the roster",
        "Japanese that renders to nothing": "renders to nothing",
    }
    for label, needle in wanted.items():
        check("the validator reports " + label, any(needle in p for p in bad))

    # --- the live directory, whatever is in it today
    print("[cast_mechanisms] the real directory (%s)" % cm.mechanisms_dir(cfg))
    live = cm.keys_on_disk(cfg)
    if not live:
        print("  note no files written yet; every call renders no block and goes out unchanged")
    else:
        lp = cm.validate(cfg)
        check("every real file validates", not lp, "; ".join(lp[:4]))
        ld = cm.dead(cfg)
        check("no real mechanism is DEAD", not ld,
              ", ".join("%s/%s" % (k, i) for k, i, _r in ld[:4]))
        for key in live:
            print("     %-16s turn %4d chars   beat %4d   day %4d (cap %d)"
                  % (key, len(cm.block_ja(cfg, key, "cast_turn")),
                     len(cm.block_ja(cfg, key, "cast_beat")),
                     len(cm.block_ja(cfg, key, "cast_day")), cm.max_chars(cfg)))

    # --- the two stress modes, on a fabricated reading
    #
    # Nobody on the roster has gauges of her own today, so the mode is never
    # on for any of them and the code path would go untested for ever. These
    # readings are made up on the spot for that reason and are nobody's.
    print("[cast_mechanisms] a mode starts on a gauge reading and not otherwise")
    modes = {}
    for key in cm.keys_on_disk(cfg):
        for m in (cm.load(cfg, key).get("mechanisms") or []):
            if m.get("gauge_trigger"):
                modes.setdefault(key, []).append(m)
    check("every compiled person has a mode that starts after a span of hours "
          "and one that starts at a gauge's end",
          bool(modes) and all(sorted(x["gauge_trigger"]["mode"] for x in v) == ["grip", "loop"]
                              for v in modes.values()),
          ", ".join("%s %d" % (k, len(v)) for k, v in sorted(modes.items())))
    if modes:
        key = sorted(modes)[0]
        loop = [m for m in modes[key] if m["gauge_trigger"]["mode"] == "loop"][0]
        grp = [m for m in modes[key] if m["gauge_trigger"]["mode"] == "grip"][0]
        lg, lt = loop["gauge_trigger"]["gauge"], loop["gauge_trigger"]["at"]
        gg, gt = grp["gauge_trigger"]["gauge"], grp["gauge_trigger"]["at"]
        check("nothing is on for somebody with no gauges at all",
              cm.mode_for(cfg, key, {}) is None and cm.mode_line(cfg, key, None) == "")
        check("the level alone does not start the mode that needs a span of hours",
              cm.mode_for(cfg, key, {lg: lt + 5}) is None,
              "%s at %d, no history" % (lg, lt + 5))
        on = cm.mode_for(cfg, key, {lg: lt + 5}, lambda g, lvl: 99)
        check("the level held for long enough does start it",
              on is not None and on["gauge_trigger"]["mode"] == "loop")
        line = cm.mode_line(cfg, key, {lg: lt + 5}, lambda g, lvl: 99)
        check("the line says what has been going on and never what she does about it",
              bool(line) and "→" not in line and "->" not in line, line[:70])
        check("a gauge at its end starts the other one, and wins over the first",
              (cm.mode_for(cfg, key, {gg: gt + 5, lg: lt + 5}, lambda g, lvl: 99) or {})
              .get("gauge_trigger", {}).get("mode") == "grip")
        check("a mode is a conditional in the block, not a standing habit",
              any(cm._WHEN[("grip", "ja")] in l or cm._WHEN[("loop", "ja")] in l
                  for l in cm.block_ja(cfg, key, "cast_turn", cap=99999).split("\n")))

    # --- the character's own file, in her own language
    print("[cast_mechanisms] the character's own block, in the language she is addressed in")
    own = str(getattr(cfg.character, "name", "") or "")
    if own in cm.keys_on_disk(cfg):
        block = cm.block_ja(cfg, own, "persona", cap=cm.own_max_chars(cfg),
                            lang="ja" if cm.lang_of(cfg) else "en")
        check("her own block renders for her own call", bool(block), "%d chars" % len(block))
        rows = cm.load(cfg, own).get("mechanisms") or []
        leaked = [w for w in ([str(r.get("id")) for r in rows[:3]]
                              + ["authored", "derived", "\"code\"", "receipts"]) if w in block]
        check("no id, no tier, no code and no receipt in her block", not leaked, ", ".join(leaked))
        check("her block is under its own ceiling", len(block) <= cm.own_max_chars(cfg),
              "%d of %d" % (len(block), cm.own_max_chars(cfg)))
    else:
        print("  note no file for %r yet; her prompt carries no block" % own)

    # --- the type is nowhere in what a model reads
    print("[cast_mechanisms] the personality vocabulary is in the author's prior and nowhere else")
    hits = []
    for root in VOCAB_ROOTS:
        if not os.path.isdir(root):
            continue
        for d, _subs, fs in os.walk(root):
            if any(os.path.normpath(d).startswith(x) for x in VOCAB_EXEMPT):
                continue
            for f in fs:
                if not f.endswith((".json", ".md", ".txt")):
                    continue
                p = os.path.join(d, f)
                rel = os.path.normpath(p).replace(os.sep, "/")
                if any(fnmatch.fnmatch(rel, pat) for pat in VOCAB_EXEMPT_FILES):
                    continue
                try:
                    text = io.open(p, encoding="utf-8", errors="replace").read()
                except OSError:
                    continue
                for w in TYPE_CODES:
                    if re.search(r"(?<![A-Za-z])%s(?![A-Za-z])" % w, text):
                        hits.append("%s: %s" % (p, w))
                for w in TYPE_SHORT:
                    if re.search(r"(?<![A-Za-z])%s(?![A-Za-z])" % w, text):
                        hits.append("%s: %s" % (p, w))
                for w in TYPE_LONG + TYPE_POSITIONS:
                    if re.search(r"(?<!\w)%s(?!\w)" % w, text, re.I):
                        hits.append("%s: %s" % (p, w))
    check("no four letters, no function name and no position word in a "
          "mechanisms file, a sheet or a prompt", not hits, "; ".join(hits[:5]))

    print()
    if fails:
        print("%d FAILURE(S): %s" % (len(fails), ", ".join(fails)))
        return 1
    print("all clear")
    return 0


if __name__ == "__main__":
    sys.exit(main())
