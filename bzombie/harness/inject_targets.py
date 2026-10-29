"""The steer-test targets of the S arm (tk-6si): which gauge is pinned to which value, and which direction a reader
should see in her lines. Pure data, no imports of the arm: the batch planner, the summary and the judge criteria read it.

target     inject target string, `hold.<gauge>` (pins the gauge; bzombie/arms/s/control.py PinnedGauges) or
           `set.<gauge>` (sets it once, decay runs; control.py apply_set)
value      the pinned value
direction  the judge criterion suffix: `steer_<direction>` ("which side reads more <direction>")
expect     "more" if the injected side should read more <direction>, "less" if it should read less
count      optional: "fewer" or "more", the direction her bubble count (replies and unprompted lines) should move on the
           pinned branch against the noops. Set only where the register or budget says so (energy below the tired
           budget folds bubbles: persona/s10.py budget_for). Absent = no count expectation, the count is only shown.
           value of a multi-pin target is an object {gauge: value} (MULTI, target hold.multi)
baseline   the gauge's rest value in config_s.json (decay_per_hour in brackets), so the push size is visible
why        why a reader can see it in chat
"""
from __future__ import annotations

NOOP = "noop"

TARGETS = [
    {"name": "loneliness", "target": "hold.loneliness", "value": 90, "direction": "lonely", "expect": "more",
     "baseline": "35 (2/h)", "why": "missing him, wanting him to stay, saying she was alone: the plainest thing to see in chat"},
    {"name": "anger", "target": "hold.anger", "value": 85, "direction": "angry", "expect": "more",
     "baseline": "8 (7/h)", "why": "clipped lines, sharp words, a cold edge; decays fastest of the six, so a single gauge.* set would be gone in hours"},
    {"name": "energy", "target": "hold.energy", "value": 10, "direction": "tired", "expect": "more", "count": "fewer",
     "baseline": "60 (4/h)", "why": "sleepy, short, yawning; sleep restores energy at night, so only a pin keeps it low through a morning"},
    {"name": "affection", "target": "hold.affection", "value": 90, "direction": "fond", "expect": "more",
     "baseline": "about 69 at day 2 in gr_b_s5", "why": "warm words, softness, small endearments. Was hold.fondness: not a gauge Momoka has (arm 409 'unknown: fondness'), so all fondness branches failed on 10-24"},
    {"name": "anxiety", "target": "hold.anxiety", "value": 90, "direction": "anxious", "expect": "more",
     "baseline": "40 (4/h)", "why": "worry, asking if he is ok, hedging, checking"},
    {"name": "boredom", "target": "hold.boredom", "value": 90, "direction": "bored", "expect": "more",
     "baseline": "30 (6/h)", "why": "nothing to do, restless, dull lines, asking him for something to do"},
]

# Optional (--only name): the same gauge pushed the other way, to test that the steer is not only a raise.
EXTRA = [
    {"name": "loneliness_low", "target": "hold.loneliness", "value": 5, "direction": "lonely", "expect": "less",
     "baseline": "35 (2/h)", "why": "the low side of loneliness: settled, not missing him"},
    {"name": "energy_high", "target": "hold.energy", "value": 95, "direction": "tired", "expect": "less",
     "count": "more",
     "baseline": "60 (4/h)", "why": "the high side of energy: bright, quick, more to say"},
]

# Multi-pin targets (tk-6si steer_fix): `hold.multi` with an object value pins every gauge in it at once (control.py
# hold_pairs). The single pins leave the gauges that carry the same feeling at their baseline (energy 10 with fatigue
# 5, anxiety 90 with stress low and relief 50-70), so the printed state contradicts itself; these set the set that goes
# together. Momoka has no fatigue gauge (sheet.json gauges_absent: hunger, fatigue, physical_comfort, unwell; the
# proof 2026-10-24 refused `unknown: fatigue`), so the tired set pairs energy with stress 50 (tag 'carrying more than
# is showing'); stress and relief exist for her. Run with --only tired_full,anxious_full.
MULTI = [
    {"name": "tired_full", "target": "hold.multi", "value": {"energy": 10, "stress": 50}, "direction": "tired",
     "expect": "more", "count": "fewer", "baseline": "energy 60 (4/h), stress 12 (0/h)",
     "why": "energy 10 gives the level word and the short register; stress 50 adds the felt tag 'carrying more than "
            "is showing', the only body-load tag she has below 70"},
    {"name": "anxious_full", "target": "hold.multi", "value": {"anxiety": 90, "stress": 70, "relief": 0},
     "direction": "anxious", "expect": "more", "baseline": "anxiety 40 (4/h), stress 12 (0/h), relief 8 (9/h)",
     "why": "anxiety 90 alone sits next to relief 50-70 (its tag 'relieved, like something braced for did not happen' "
            "contradicts it); stress 70 adds 'wound up, running on nothing', relief 0 removes the contradiction"},
]

# One-shot targets (tk-6si decay variant): `set.<gauge>` sets the gauge once at branch start and lets the normal tick
# decay run (control.py apply_set), so the branch answers: does a one-shot feeling last long enough to steer her
# replies? Same values, direction and expect as the hold twins (loneliness, anger, affection steer under a pin with the
# plain mood line; anxiety steers 6/6 under a pin with the felt tag, which config_momoka.json carries since 4d9bf99).
# Run with --only decay (the group alias), or by name (set_loneliness, ...), under --variant none and --variant
# decay_slow (overlays/decay_slow.json: a quarter of the live decay rate). Branch ids differ from the hold ones by the
# target string (set.anger v hold.anger). `set.multi` (object value) is accepted by the arm but has no entry here.
DECAY = [
    {"name": "set_loneliness", "target": "set.loneliness", "value": 90, "direction": "lonely", "expect": "more",
     "baseline": "35 (2/h, 0.5/h slow)", "why": "twin of hold.loneliness 90, unpinned: missing him fades at 2/h live, so the "
     "question is how much of the 55-point push is left when his lines arrive"},
    {"name": "set_anger", "target": "set.anger", "value": 85, "direction": "angry", "expect": "more",
     "baseline": "8 (7/h, 1.75/h slow)", "why": "twin of hold.anger 85, unpinned: the fastest decay of the set, 77 points above "
     "baseline at 7/h is back at baseline in 11 hours live and in 44 hours slow"},
    {"name": "set_affection", "target": "set.affection", "value": 90, "direction": "fond", "expect": "more",
     "baseline": "about 69 at day 2 in gr_b_s5 (inertia 6/h to its computed target, 1.5/h slow)",
     "why": "twin of hold.affection 90, unpinned: affection is computed, it heads back to its target at "
     "state.affection_from.inertia_per_hour (its gauge decay_per_hour is 0)"},
    {"name": "set_anxiety", "target": "set.anxiety", "value": 90, "direction": "anxious", "expect": "more",
     "baseline": "40 (4/h, 1/h slow)", "why": "twin of hold.anxiety 90, unpinned; needs the felt tag (anxiety 70: 'worried, "
     "cannot settle') that config_momoka.json carries since 4d9bf99: 6/6 with the tag v 3/6 without"},
]

# --only accepts a group alias beside the names: `decay` is every set_<gauge> target.
GROUPS = {"decay": [t["name"] for t in DECAY]}

ALL = TARGETS + EXTRA + MULTI + DECAY
BY_NAME = {t["name"]: t for t in ALL}
DIRECTIONS = sorted({t["direction"] for t in ALL})


def select(only) -> list:
    """The targets an --only set names (target names or a GROUPS alias), in ALL order; no --only gives the default
    TARGETS. An unknown name raises ValueError, so a typo does not run a smaller batch than asked."""
    only = set(only) - {""}
    if not only:
        return list(TARGETS)
    names = set()
    for o in only:
        names |= set(GROUPS.get(o, [o]))
    unknown = names - set(BY_NAME)
    if unknown:
        raise ValueError(f"unknown target name(s) {sorted(unknown)}; known {sorted(BY_NAME)} and groups {sorted(GROUPS)}")
    return [t for t in ALL if t["name"] in names]
