# -*- coding: utf-8 -*-
"""The gauge appraisal: System One scores independent dimensions over the live
tick context, and code maps the levels into the integer deltas `State.apply`
takes.

`docs/2026-09-17_gauge_appraisal_composite_scoring_design.md` is the design.
The classifier says *whether and which way*; this module owns *how much*. The
questions and the anchors are code, like `sim/inbound.py` and the GoEmotions
list, so a config cannot invent a gauge or a level; the numbers -- the weights,
the floors, the gain -- live in `state.appraisal` in config.

`appraise` returns `(deltas, his_mood, fresh, provenance)` or `None` when the
call fails or no dimension clears. `None` is the caller's signal to run the
`state` role exactly as before, so the fallback is the current behaviour by
construction.
"""

import re

import logger

# The 16 dimensions, in the order `reasons_line` joins their phrases. Each is a
# `score` (0-4 with anchors) or a `choice` with a fixed option set; the
# instructions name the `appraisal_state()` fields a question reads, so it is
# never answered over context it was not pointed at. `floor` is the default
# confidence floor; `state.appraisal.thresholds` overrides it.
DIMENSIONS = (
    {"id": "how_good_or_bad", "type": "score", "floor": 0.60,
     "instructions": "In `events`, `scene` and `his_message`, is what is happening plainly bad for her or plainly good?",
     "anchors": ["plainly bad for her", "bad", "neither, nothing happening", "good", "plainly good"]},
    {"id": "how_activating", "type": "score", "floor": 0.60,
     "instructions": "Do `events` and `his_message` leave her as she was, or jolt her?",
     "anchors": ["leaves her as she was", "barely moves her", "an ordinary beat", "stirring", "jolting"]},
    {"id": "is_this_new", "type": "choice", "floor": 0.50,
     "instructions": "Against `already`, `events`, `his_message` and `his_side`, is this new, standing, an answer to what she sent, or nothing?",
     "criteria": {"new": "Something new has happened or been said",
                  "standing": "The same situation as the last ticks, nothing new",
                  "answering_what_she_sent": "It answers a message or question she sent",
                  "nothing": "Nothing at all is happening"}},
    {"id": "whose_doing", "type": "choice", "floor": 0.50,
     "instructions": "Who do `present`, `relationships`, `events` and `his_message` show this coming from?",
     "criteria": {"him": "Him", "her_own_people": "People of her own", "herself": "She did it herself",
                  "nobody": "Nobody in particular", "the_world": "The world, chance or the day"}},
    {"id": "unfairness", "type": "score", "floor": 0.60,
     "instructions": "Do `events`, `present` and `his_message` show a rule or treatment applied to her and not to others?",
     "anchors": ["nothing of the kind", "a little one-sided", "mildly unfair", "clearly unfair", "a rule applied to her and not to others"]},
    {"id": "wanted_and_blocked", "type": "score", "floor": 0.60,
     "instructions": "Do `events` and `his_message` show something she wanted taken away or not happening?",
     "anchors": ["nothing she wanted was at stake", "a small want delayed", "a want blocked", "something she wanted lost",
                 "something she wanted was taken or did not happen"]},
    {"id": "exposure", "type": "score", "floor": 0.60,
     "instructions": "Do `scene`, `events` and `his_message` show her seen, caught out or read properly?",
     "anchors": ["she was not seen", "slightly exposed", "noticed", "caught out", "caught out, laughed at, read properly"]},
    {"id": "achievement", "type": "score", "floor": 0.60,
     "instructions": "Do `events` and `scene` show something of hers coming off?",
     "anchors": ["nothing of hers came off", "a small thing went right", "something worked", "something of hers did well",
                 "something of hers plainly did"]},
    {"id": "uncertainty", "type": "score", "floor": 0.60,
     "instructions": "Do `his_message`, `his_side` and `scene` leave a question or a plan hanging?",
     "anchors": ["nothing pending", "a small open question", "something still pending", "a lot left hanging",
                 "a question or a plan left hanging"]},
    {"id": "holding_back", "type": "choice", "floor": 0.50,
     "instructions": "Against `events`, `his_message` and `already`, is she holding something back?",
     "criteria": {"holding_something": "She has something she is not saying",
                  "nothing": "She is holding nothing back"}},
    {"id": "her_fault", "type": "score", "floor": 0.60,
     "instructions": "Do `events`, `last_messages` and `already` show her doing the thing she would regret?",
     "anchors": ["not hers", "barely hers", "partly hers", "mostly hers", "she did the thing she would regret"]},
    {"id": "warmth_from_him", "type": "score", "floor": 0.60,
     "instructions": "Do `his_message`, `his_side` and `last_messages` show him warm and close, flat, or absent?",
     "anchors": ["absent or flat", "cool", "ordinary", "warm", "plainly warm and close"]},
    {"id": "attention_from_him", "type": "choice", "floor": 0.50,
     "instructions": "From `his_side`, `last_messages` and `his_message`, how did he answer her?",
     "criteria": {"answered_properly": "He answered what she sent",
                  "answered_thinly": "He answered, but barely",
                  "read_and_ignored": "He read it and did not answer",
                  "said_nothing": "He has said nothing at all"}},
    {"id": "who_else_has_him", "type": "score", "floor": 0.60,
     "instructions": "Do `digest`, `scene` and `events` show him spending himself on somebody else?",
     "anchors": ["nothing of the kind", "a hint of it", "some of it", "a lot of it",
                 "plainly spending himself on somebody else"]},
    {"id": "his_valence", "type": "score", "floor": 0.60,
     "instructions": "From `his_message` alone, is he flat and grim or plainly good?",
     "anchors": ["flat and grim", "low", "ordinary", "good", "plainly good"]},
    {"id": "his_arousal", "type": "score", "floor": 0.60,
     "instructions": "From `his_message` alone, is he dead on his feet or wired?",
     "anchors": ["dead on his feet", "tired", "ordinary", "alert", "wired"]},
)

DIMENSION_BY_ID = {d["id"]: d for d in DIMENSIONS}

# The live context's fields, in the order the role reads them.
# `State.appraisal_state` builds its dict from this list and
# `State.render_appraisal_state` renders in it, so the classifier and the role
# are handed one context and cannot drift (design section 1.1).
APPRAISAL_FIELDS = (
    "time", "gauges", "relationships", "present", "already", "talk", "scene",
    "events", "his_message", "his_side", "last_messages", "digest", "body",
    "body_settled",
)

# Dimensions whose points `how_activating` scales. These carry bad news; an
# activating bad thing lands harder on anxiety and anger, a deactivating one
# more on sadness. `how_good_or_bad` scales only on its negative side, so good
# news is not made better by her being wound up.
_NEGATIVE_DIMENSIONS = ("how_good_or_bad", "unfairness", "wanted_and_blocked",
                        "exposure", "uncertainty", "her_fault", "who_else_has_him")

# The normalised value a choice fires with. A choice that means "nothing" is 0;
# `attention_from_him`'s positive options reduce craving and its negative ones
# flip the sign, which is what "sign flips on the negative options" means.
_CHOICE_X = {
    "is_this_new": {"new": 1.0, "standing": 1.0, "answering_what_she_sent": 1.0, "nothing": 1.0},
    "whose_doing": {"him": 1.0, "her_own_people": 1.0, "herself": 1.0, "nobody": 1.0, "the_world": 1.0},
    "holding_back": {"holding_something": 1.0, "nothing": 0.0},
    "attention_from_him": {"answered_properly": 1.0, "answered_thinly": 0.5,
                           "read_and_ignored": -1.0, "said_nothing": -1.0},
}

_NO_MESSAGE = ("", "(none this tick)")
_CLAUSE_SPLIT = re.compile(r"[。．.!?！？\n]+")


def questions():
    """The one fixed batch, in DIMENSIONS order."""
    out = {}
    for d in DIMENSIONS:
        q = {"type": d["type"], "instructions": d["instructions"]}
        if d["type"] == "score":
            q["criteria"] = list(d["anchors"])
        else:
            q["criteria"] = dict(d["criteria"])
        out[d["id"]] = q
    return out


def appraise(typesafe, state, config, clock):
    """Score the tick and combine, or None to fall back to the `state` role."""
    if typesafe is None:
        return None
    try:
        if not typesafe.ready("state_appraisal"):
            return None
        return _appraise(typesafe, state, config, clock)
    except Exception as e:
        logger.log(f"[state.appraisal] not run: {type(e).__name__}")
        return None


def _appraise(typesafe, state, config, clock):
    use = typesafe.use("state_appraisal") or {}
    cfg = _cfg(config)
    base_floor = _float(use.get("threshold"), 0.6)
    thresholds = cfg.get("thresholds") or {}
    weights = cfg.get("weights") or {}
    max_points = _int(cfg.get("max_points_per_dimension"), 4)
    gain = cfg.get("gain_from_arousal") or {}
    gmin, gmax = _float(gain.get("min"), 0.6), _float(gain.get("max"), 1.2)

    answers = typesafe.ask("state_appraisal", state, questions())
    if not answers:
        return None

    cleared, abstained = [], []
    for d in DIMENSIONS:
        qid = d["id"]
        floor = _float(thresholds.get(qid), d.get("floor", base_floor))
        if d["type"] == "score":
            level, conf = typesafe.score(answers, qid)
            if level is None or conf < floor:
                abstained.append((qid, conf))
                continue
            x = _score_x(qid, level)
        else:
            level, conf = typesafe.choice(answers, qid)
            if not level or conf < floor or level not in d["criteria"]:
                abstained.append((qid, conf))
                continue
            x = _CHOICE_X.get(qid, {}).get(level, 0.0)
        cleared.append((d, level, x, conf))

    if not cleared:
        logger.log("[state.appraisal] no dimension cleared; the state role decides")
        return None

    arousal_x = 0.0
    for d, level, x, conf in cleared:
        if d["id"] == "how_activating":
            arousal_x = max(0.0, min(1.0, float(x)))
    act_gain = gmin + (gmax - gmin) * arousal_x

    totals, sources = {}, {}
    for d, level, x, conf in cleared:
        qid = d["id"]
        w = weights.get(qid) or {}
        if not w:
            continue
        g = act_gain if (qid in _NEGATIVE_DIMENSIONS and (qid != "how_good_or_bad" or x < 0)) else 1.0
        display = _display(d, level)
        for gauge, points in w.items():
            contribution = _float(points, 0.0) * float(x) * g
            contribution = max(-max_points, min(max_points, contribution))
            if abs(contribution) < 1e-9:
                continue
            totals[gauge] = totals.get(gauge, 0.0) + contribution
            sources.setdefault(gauge, []).append((qid, display, conf))

    deltas = {}
    for gauge, v in totals.items():
        n = int(round(v))
        if n:
            deltas[gauge] = n

    fresh = True
    for d, level, x, conf in cleared:
        if d["id"] == "is_this_new":
            fresh = str(level) != "standing"

    prov = {"gauges": sources,
            "dims": [(d["id"], _display(d, level), conf) for d, level, x, conf in cleared],
            "abstained": abstained}
    if abstained:
        logger.log("[state.appraisal] abstained (under floor): "
                   + ", ".join("%s %.2f" % (qid, c) for qid, c in abstained))
    return deltas, _his_mood(cleared, state), fresh, prov


def reasons_line(provenance):
    """A phrase per cleared dimension, in DIMENSIONS order, capped at 300."""
    dims = (provenance or {}).get("dims") or []
    parts = []
    for dim_id, display, _conf in dims:
        fn = _REASONS.get(dim_id)
        phrase = fn(display, _x_hint(dim_id, display)) if fn else str(dim_id)
        if phrase and phrase not in parts:
            parts.append(phrase)
    text = "; ".join(parts).strip()
    return (text or "nothing much moved her")[:300]


# ---------------- the combination helpers ----------------

def _cfg(config):
    """`state.appraisal` as plain data.

    `Config.Section` wraps a nested map as a `Section` unless its key is
    whitelisted, and `thresholds` is not, so the merged raw tree is the read
    that returns dicts for every number this module needs."""
    raw = getattr(config, "raw", None)
    state = raw.get("state") if isinstance(raw, dict) else None
    app = state.get("appraisal") if isinstance(state, dict) else None
    return app if isinstance(app, dict) else {}


def _score_x(qid, level):
    v = max(0.0, min(4.0, float(level)))
    return (v - 2.0) / 2.0 if qid == "how_good_or_bad" else v / 4.0


def _display(dim, level):
    if dim.get("type") == "score":
        return str(int(round(float(level))))
    return str(level)


def _x_hint(dim_id, display):
    d = DIMENSION_BY_ID.get(dim_id) or {}
    if d.get("type") == "score":
        try:
            return _score_x(dim_id, float(display))
        except (TypeError, ValueError):
            return 0.0
    return _CHOICE_X.get(dim_id, {}).get(display, 0.0)


def _his_mood(cleared, state):
    """`{valence, arousal, line}` scaled to -2..+2 for `note_his_mood`, or {}
    when he did not write. The line is a code template that quotes his
    shortest clause; the classifier cannot write prose (design section 6)."""
    msg = str((state or {}).get("his_message") or "").strip()
    if msg in _NO_MESSAGE:
        return {}
    out = {}
    for d, level, x, conf in cleared:
        if d["id"] == "his_valence":
            out["valence"] = max(-2.0, min(2.0, float(level) - 2.0))
        elif d["id"] == "his_arousal":
            out["arousal"] = max(-2.0, min(2.0, float(level) - 2.0))
    if not out:
        return {}
    out.setdefault("valence", 0.0)
    out.setdefault("arousal", 0.0)
    out["line"] = _shortest_clause(msg)
    return out


def _shortest_clause(text):
    bits = [b.strip() for b in _CLAUSE_SPLIT.split(str(text or "")) if b.strip()]
    if not bits:
        return ""
    return min(bits, key=len)[:60]


_REASONS = {
    "how_good_or_bad": lambda lvl, x: ("something good happened" if x > 0 else
                                       ("something bad happened" if x < 0 else "an ordinary beat")),
    "how_activating": lambda lvl, x: ("it jolted her" if x >= 0.75 else
                                      ("it stirred her" if x >= 0.4 else "it left her as she was")),
    "is_this_new": lambda lvl, x: {"new": "something new", "standing": "the same thing standing",
                                   "answering_what_she_sent": "he was answering her",
                                   "nothing": "nothing happening"}.get(lvl, str(lvl)),
    "whose_doing": lambda lvl, x: "that was " + {"him": "him", "her_own_people": "her own people",
                                                  "herself": "her own doing", "nobody": "nobody's",
                                                  "the_world": "the world"}.get(lvl, str(lvl)),
    "unfairness": lambda lvl, x: "it was unfair to her" if x >= 0.5 else "a bit one-sided",
    "wanted_and_blocked": lambda lvl, x: "something she wanted was blocked" if x >= 0.5 else "a want was delayed",
    "exposure": lambda lvl, x: "she was seen" if x >= 0.5 else "a little exposed",
    "achievement": lambda lvl, x: "something of hers came off" if x >= 0.5 else "a small thing went right",
    "uncertainty": lambda lvl, x: "something left hanging" if x >= 0.5 else "a small open question",
    "holding_back": lambda lvl, x: "she is holding something back" if lvl == "holding_something" else "nothing held back",
    "her_fault": lambda lvl, x: "she did the thing she would regret" if x >= 0.5 else "partly her own doing",
    "warmth_from_him": lambda lvl, x: ("plainly warm from him" if x >= 0.75 else
                                       ("warm from him" if x >= 0.5 else
                                        ("cool from him" if x <= 0.25 else "him ordinary"))),
    "attention_from_him": lambda lvl, x: {"answered_properly": "he answered her properly",
                                          "answered_thinly": "he answered thinly",
                                          "read_and_ignored": "he read and ignored her",
                                          "said_nothing": "he said nothing"}.get(lvl, str(lvl)),
    "who_else_has_him": lambda lvl, x: "he is spending himself elsewhere" if x >= 0.5 else "a hint of somebody else",
    "his_valence": lambda lvl, x: "he sounds good" if x > 0 else ("he sounds bad" if x < 0 else "he sounds ordinary"),
    "his_arousal": lambda lvl, x: "he sounds wired" if x >= 0.5 else ("he sounds flat" if x <= -0.5 else "he sounds ordinary"),
}


def _float(v, default):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _int(v, default):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default
