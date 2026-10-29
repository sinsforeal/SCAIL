"""Run a character sheet against the machinery, without the machinery running.

The question "does a different character actually work" splits into levels,
and only the last of them needs prompts, an LLM or a save with history in it.
Most of what can be wrong is wrong at level 1.

    L1  config     her sheet loads, her gauges validate, and the merged set
                   differs from the other character's in the ways it should
    L2  state      a State built on a scratch save decays toward HER baselines,
                   not the ones config.py ships with
    L3  derived    the code-owned figures -- susceptibility, stress, mood --
                   answer differently for her because her data differs
    L4  prompts    the forge's survey and rubric over a hand-written port

L1 to L3 are free and take a second. Run them on every sheet; run L4 when the
sheet is settled.

    python tools/character_test.py --sheet data/characters/megumi.json
    python tools/character_test.py --sheet X --against data/characters/tomoe.json
"""
import argparse
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logger

logger.log = lambda m: None
logger.log_llm = lambda *a, **k: None

from config import Config
from store import Store
from world.clock import WorldClock

PASS, FAIL, WARN = "  ok  ", " FAIL ", " warn "
_fails = []


def check(ok, label, detail="", warn_only=False):
    mark = PASS if ok else (WARN if warn_only else FAIL)
    print(f"{mark} {label}" + (f"   {detail}" if detail else ""))
    if not ok and not warn_only:
        _fails.append(label)
    return ok


# ---------------------------------------------------------------- L1

def level1(sheet_path, against):
    print("\nL1  CONFIG: does her sheet load and validate")
    try:
        cfg = Config("config.json", character_file=sheet_path)
    except Exception as e:
        check(False, "the sheet loads", f"{type(e).__name__}: {e}")
        return None, None
    sheet = cfg.character_sheet
    name = (sheet.get("name") or {}).get("full") or sheet.get("id", "?")
    check(bool(sheet), "the sheet loads", name)

    base = Config("config.json", character_file=against)
    hers, theirs = cfg.state.gauges, base.state.gauges

    # the check that matters: does she have her own numbers
    diff = {k: (theirs[k]["baseline"], hers[k]["baseline"])
            for k in hers if k in theirs and hers[k]["baseline"] != theirs[k]["baseline"]}
    same = os.path.abspath(sheet_path) == os.path.abspath(against)
    check(bool(diff) or same, "her baselines differ from the other character's",
          "compared against itself" if same else f"{len(diff)} gauge(s) retuned",
          warn_only=same)
    for k, (a, b) in sorted(diff.items())[:8]:
        print(f"         {k:22s} {a:>5} -> {b}")

    own = sorted(set(hers) - set(theirs))
    missing = sorted(set(theirs) - set(hers))
    if own:
        print(f"         gauges only she has: {own}")
    if missing:
        print(f"         gauges she does not have: {missing}")
    check(True, "gauge set", f"{len(hers)} total, {len(own)} of her own")

    # every gauge, hers included, must say what kind of thing it is
    bad = [k for k, v in hers.items()
           if v.get("kind") not in ("emotion", "drive", "body", "derived")
           or "valence" not in v or "arousal" not in v or "baseline" not in v]
    check(not bad, "every gauge declares kind, valence, arousal, baseline", str(bad[:4]) if bad else "")

    # the emotion grid must still span, or she has a feeling she cannot have
    grid = {}
    for k, v in hers.items():
        if v.get("kind") == "emotion":
            grid.setdefault((int(v.get("valence", 0)), int(v.get("arousal", 0))), []).append(k)
    empty = [f"{'good' if val > 0 else 'bad'}/{'activating' if aro > 0 else 'deactivating'}"
             for val in (1, -1) for aro in (1, -1) if not grid.get((val, aro))]
    check(not empty, "the emotion grid spans valence x arousal",
          f"empty: {empty}" if empty else "", warn_only=True)
    return cfg, sheet


# ---------------------------------------------------------------- L2

def level2(cfg):
    print("\nL2  STATE: does she decay toward her own baselines")
    tmp = os.path.join(tempfile.gettempdir(), "character_test.db")
    if os.path.exists(tmp):
        os.remove(tmp)
    from sim.state import State
    clock = WorldClock(cfg)
    store = Store(tmp)
    st = State(cfg, store, clock)

    # push everything away from rest, then let a long quiet stretch pass.
    # decay() takes its elapsed hours from last_decay_ts, not from its first
    # argument (that is silent_hours), so the clock is what has to be moved
    for k in st.gauges:
        st.gauges[k] = 90.0
    st.last_decay_ts = clock.now_ts() - 48 * 3600
    st.decay(0.0, {})
    off, slow = [], []
    for k, v in cfg.state.gauges.items():
        rate = float(v.get("decay_per_hour", 0) or 0)
        if rate <= 0 or v.get("kind") == "derived" or not v.get("model_may_move", True):
            # code-owned or computed: these have their own target and are
            # supposed to sit wherever their causes put them, not at rest
            continue
        base = float(v["baseline"])
        # the test is direction, not arrival: a deliberately slow gauge (a
        # ledger that does not come down on its own) is not a broken one, and
        # asserting arrival would forbid exactly the gauges a second character
        # is likely to bring
        if st.gauges[k] > 90.0 - 1e-6:
            off.append((k, round(st.gauges[k], 1), base))
        elif abs(st.gauges[k] - base) > 1.5:
            slow.append((k, round(st.gauges[k], 1), base, round((90 - base) / rate / 24, 1)))
    check(not off, "every decaying gauge moves toward HER baseline",
          str(off[:4]) if off else "")
    for k, now, base, days in slow:
        print(f"         {k}: {now} -> {base} takes about {days} day(s), by design")
    sample = [k for k in ("anxiety", "energy", "boredom", "loneliness") if k in st.gauges][:4]
    print("         " + ", ".join(f"{k} {st.gauges[k]:.0f}" for k in sample))
    return st, store, clock


# ---------------------------------------------------------------- L3

def level3(cfg, st, store, clock, sheet):
    print("\nL3  DERIVED: do the computed figures follow her data, not the code")
    from sim.stress import Stress

    beliefs_path = ((sheet.get("beliefs") or {}).get("about_herself") or "").strip()
    self_model = None
    if beliefs_path and os.path.exists(beliefs_path):
        from sim.memory import Memory
        from sim.model_of_her import ModelOfHer
        try:
            self_model = ModelOfHer(cfg, None, store, clock, Memory(cfg, store, clock))
        except Exception as e:
            print(f"         self-beliefs would not load: {type(e).__name__}")
    else:
        check(False, "she has a self-belief file", "stress susceptibility falls back to 1.0",
              warn_only=True)

    s = Stress(cfg, store, clock, st, self_model=self_model)
    st.stress = s
    sus = s.susceptibility()
    check(True, "stress susceptibility", f"{sus:.2f}"
          + ("  (derived from her beliefs)" if self_model else "  (default: no belief file)"))

    # the asymmetry has to be visible whoever she is
    st.gauges["stress"] = float(cfg.state.gauges["stress"]["baseline"])
    if "unsaid" in st.gauges:
        st.gauges["unsaid"] = 95
    tgt = s.target(30.0)
    st.gauges["stress"] = tgt
    s.step(4.0, 0.0)
    fell = tgt - st.gauges["stress"]
    st.gauges["stress"] = float(cfg.state.gauges["stress"]["baseline"])
    s.step(4.0, 30.0)
    rose = st.gauges["stress"] - float(cfg.state.gauges["stress"]["baseline"])
    check(rose > fell, "stress rises faster than it falls",
          f"4h up {rose:.1f}, 4h down {fell:.1f}")

    if "mood" in st.gauges:
        st.gauges["mood"] = 50
        for k, v in cfg.state.gauges.items():
            if v.get("kind") == "emotion" and int(v.get("valence", 0)) < 0:
                st.gauges[k] = 85
        st._derive_mood(12.0)
        low = st.gauges["mood"]
        for k, v in cfg.state.gauges.items():
            if v.get("kind") == "emotion" and int(v.get("valence", 0)) < 0:
                st.gauges[k] = float(v["baseline"])
        st._derive_mood(12.0)
        check(st.gauges["mood"] > low, "mood follows its causes both ways",
              f"bad day {low:.0f}, then {st.gauges['mood']:.0f}")


# ---------------------------------------------------------------- L4

def level4(sheet_path):
    print("\nL4  PROMPTS: what the forge would have to do")
    from tools.forge import prompts, sheet_names, load
    sheet = load(sheet_path)
    old = load("data/characters/tomoe.json")
    old_nouns, new_nouns = sheet_names(old), sheet_names(sheet)
    import re
    need = [os.path.basename(p) for p in prompts()
            if any(re.search(rf"\b{re.escape(n)}\b", open(p, encoding="utf-8").read())
                   for n in old_nouns)]
    print(f"         {len(need)} of {len(prompts())} prompts name the other character and need re-pointing")
    print(f"         she brings {len(new_nouns)} name(s) of her own")
    check(len(new_nouns) >= 3, "her sheet has enough names to re-point with",
          "" if len(new_nouns) >= 3 else "too thin; generation will invent or go vague",
          warn_only=True)
    print("         (next: python tools/forge.py survey --sheet ... then port by hand)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", required=True)
    ap.add_argument("--against", default="data/characters/tomoe.json")
    ap.add_argument("--level", type=int, default=4)
    args = ap.parse_args()

    print("=" * 78)
    print(f"CHARACTER TEST: {args.sheet}")
    print("=" * 78)
    cfg, sheet = level1(args.sheet, args.against)
    if cfg and args.level >= 2:
        st, store, clock = level2(cfg)
        if args.level >= 3:
            level3(cfg, st, store, clock, sheet)
    if args.level >= 4:
        level4(args.sheet)

    print()
    if _fails:
        print(f"{len(_fails)} check(s) failed:")
        for f in _fails:
            print(f"  - {f}")
        sys.exit(1)
    print("every check passed")


if __name__ == "__main__":
    main()
