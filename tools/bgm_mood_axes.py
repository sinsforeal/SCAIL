# -*- coding: utf-8 -*-
"""Second pass over the koikano BGM spans: ask axes, not a mood label.

The first pass (`tools/bgm_mood_probe.py`) asked one seven-way mood `choice` over
headed and transitional windows and found the tracks do not sort one-to-one onto
the stage's seven moods: `tense` led twelve tracks, `warm` and `tender` five
each, no track read `cool`, and 26 of 27 tracks were split by one or two votes.
A seven-way choice spreads its probability, so a two-vote lead carries little
weight. This pass changes the question. It asks two ordinal `score` axes --
`valence` (very bad -> very good) and `arousal` (calm -> intense) -- as the
primary read, and keeps the categorical choice only as a cross-check. An ordinal
answer is a number, so a track becomes a point on a plane and the spread of that
point is the point: a tight cluster is a real cue, a wide one is a general bed.

Scope. Analysis only. Nothing in the runtime imports this tool, it writes no
save and it changes no live path. It reads the extracted corpus, one inventory
file and one expression-label file, calls the real System One client
(`typesafe.py`) and writes a JSON and a `.md` beside the first pass's outputs.
`sim/scene.py:MOOD_BGM` and the bundle are left untouched.

Sampling, every span. The first pass read 154 of 500 spans. This pass reads all
500, one window per span at its **middle** -- the stretch where the track plays
over content -- plus the **transition** window at its end. A span shorter than
the window yields the whole span as its middle and no separate transition. Each
span counts once in a track's centroid whatever its length, so a five-record
span is not drowned by a six-hundred-record one.

Questions. One batched call per span carries, per window, two `score` axes and
one `choice` over the seven moods plus `unclear`. `unclear`, an off-set answer,
an answer under the floor or a failed call is an abstention and never a value.
A failed call is logged by exception type only (`netwatch.redact`) and nothing
is written to `missed_calls` (`docs/system-one.md` section 4).

    python tools/bgm_mood_axes.py                       # full run, writes outputs
    python tools/bgm_mood_axes.py --dry-run             # parse/aggregate, no calls
    python tools/bgm_mood_axes.py --limit 8 --no-write  # calibration
    python tools/bgm_mood_axes.py --tracks BGM19,BGM21  # a couple of tracks

Cost is input tokens only (output is free at jev 1.13); the tool totals the
`[typesafe] ... in= out=` lines the client logs and prints the spend.
"""

import argparse
import datetime
import json
import math
import os
import re
import statistics
import sys
import tempfile
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import logger
from typesafe import TypeSafe

try:
    from sim.scene import MOODS, MOOD_BGM
except Exception:                                    # the tool must still run
    MOODS = ("neutral", "warm", "cool", "dim", "bright", "tense", "tender")
    MOOD_BGM = {}

CORPUS = "extracted_games/koikano"
INVENTORY = (r"F:\REPS2\clipboard capture (kirikiri)\extracted_games"
             r"\koikano\koikano_work\inventory\bgm_scene_table.json")

USE = "bgm_mood_axes"            # the one use name, per docs/system-one.md section 4
FLOOR = 0.40                     # per question; an 8-way choice spreads confidence
WINDOW = 12                      # dialogue records per window (see the notebook for why)
CHARS_PER_WINDOW = 2400          # excerpt cap, to keep the state bounded
PRICE_PER_MTOK = 0.042           # USD per million input tokens (jev 1.13)
FAR_BOUND = 1.20                 # a mood farther than this from every track has no cue
BED_SPREAD = 0.80                # SD at or above this on either axis is a general bed
STABILITY_SPANS = 60             # spans read twice (head vs middle) for the stability check

USE_CONFIG = {"typesafe": {
    "enabled": True, "model": "jev-latest", "key_file": "secerts/typesafe.txt",
    "timeout_seconds": 60, "floor": FLOOR,
    "uses": {USE: {"enabled": True, "threshold": FLOOR}},
}}

# --- the axes -----------------------------------------------------------------
# A `score` carries an ordinal level in the index space of its `criteria` list
# (the probe answered 1.04 for a three-anchor question), so a five-anchor list
# returns roughly 0..4 and the confidence travels with it. Valence is put on
# -2..+2 by subtracting 2 from the level so both axes span a range of four,
# which is what makes a plain Euclidean distance between them meaningful.
VALENCE_ANCHORS = ["very bad", "bad", "neutral", "good", "very good"]
AROUSAL_ANCHORS = ["calm", "mildly involved", "engaged", "animated", "intense"]
VALENCE_SHIFT = 2.0

# The categorical question, kept purely as a cross-check against the axes.
MOOD_CRITERIA = {
    "neutral": "ordinary, matter-of-fact; no strong feeling either way",
    "warm": "friendly, familiar, comfortable affection",
    "cool": "detached, aloof, calm but distant",
    "dim": "subdued, low, heavy or gloomy",
    "bright": "cheerful, lively, energetic and light",
    "tense": "strained, anxious, argumentative or on edge",
    "tender": "gentle, intimate, soft and caring",
    "unclear": "the excerpt carries no readable mood, or is not a scene moment",
}

# The seven moods the stage uses, each placed on the two axes. Valence is -2..2,
# arousal is 0..4. The reasoning for each point is in the notebook and in the
# `.md`; it is read off the same one-line criteria the categorical question uses,
# so the two answers cannot ask for different things.
MOOD_TARGETS = {
    "bright":  (1.8, 3.0, "cheerful, lively, energetic and light: high on both"),
    "warm":    (1.3, 1.8, "friendly, familiar affection: clearly positive, mid energy"),
    "tender":  (1.4, 1.0, "gentle, intimate, soft and caring: positive, low energy"),
    "neutral": (0.0, 2.0, "ordinary, no strong feeling: the middle of both"),
    "cool":    (-0.2, 1.0, "detached, aloof, calm but distant: near zero, low energy"),
    "dim":     (-1.3, 1.2, "subdued, low, heavy or gloomy: negative, low-mid energy"),
    "tense":   (-1.4, 3.2, "strained, anxious, on edge: negative, high energy"),
}

# A coarse valence for each expression the corpus is labelled with, so the
# label mix can be compared with the classifier's axis. Only the nine labels the
# per-line file uses are mapped; an unmapped label is dropped from the check.
EXPRESSION_VALENCE = {
    "laugh": 2.0, "excited": 2.0, "smile": 1.5, "shy": 0.5, "surprise": 0.3,
    "neutral": 0.0, "serious": -0.3, "worried": -1.0, "sad": -1.5, "angry": -1.8,
}


# --- reading the corpus -------------------------------------------------------

def _read_text(path):
    with open(path, "rb") as f:
        return f.read().decode("cp932", "replace")


def parse_scene(path):
    """The dialogue records of one `.ks` file, in file order.

    A record is one `@Talk` plus the un-tagged lines that follow it until the
    next command; the speaker is read from the tag. The `line` is the `@Talk`
    tag's own 1-based line, the same key the expression-label file uses."""
    lines = _read_text(path).splitlines()
    recs = []
    i = 0
    while i < len(lines):
        tag = lines[i].strip()
        if tag.startswith("@Talk"):
            j = i + 1
            body = []
            while j < len(lines) and not lines[j].lstrip().startswith("@"):
                body.append(lines[j].strip().lstrip("\u3000"))
                j += 1
            m = re.search(r"name=([^\s]+)", tag)
            text = "\n".join(x for x in body if x)
            if text:
                recs.append({"line": i + 1, "speaker": m.group(1) if m else "",
                             "text": text})
            i = j
        else:
            i += 1
    return recs


def excerpt(recs):
    out = []
    for r in recs:
        who = f"{r['speaker']}: " if r["speaker"] else ""
        out.append(who + r["text"])
    return "\n".join(out)[:CHARS_PER_WINDOW]


def next_command(lines, end_line):
    """What ends the span: the first `@playBgm`/`@stopBgm` after its last line."""
    for i in range(end_line, len(lines)):
        s = lines[i].strip()
        if s.startswith("@playBgm"):
            m = re.search(r"file=([^\s]+)", s)
            return "changes to " + (m.group(1) if m else "another track")
        if s.startswith("@stopBgm"):
            return "stops"
    return "the scene ends"


def windows_for(recs, width):
    """(middle, transition, stratum). The middle is centred; a span no longer
    than the window is its own middle and has no separate transition."""
    n = len(recs)
    if n == 0:
        return None, None, "empty"
    if n <= width:
        return recs, None, "short"          # the whole span is the middle
    start = max(0, (n - width) // 2)
    mid = recs[start:start + width]
    tail = recs[-width:]
    stratum = "medium" if n <= 2 * width else "long"
    return mid, tail, stratum


# --- questions and answers ----------------------------------------------------

def build_questions(has_transition):
    q = {
        "mid_valence": {
            "type": "score",
            "instructions": "Judge the mood of the `middle` excerpt only. How "
                            "positive or negative is the scene it carries?",
            "criteria": VALENCE_ANCHORS,
        },
        "mid_arousal": {
            "type": "score",
            "instructions": "Judge the mood of the `middle` excerpt only. How "
                            "calm or intense is the scene it carries?",
            "criteria": AROUSAL_ANCHORS,
        },
        "mid_mood": {
            "type": "choice",
            "instructions": "Which single mood does the `middle` excerpt carry? "
                            "Judge `middle` only.",
            "criteria": MOOD_CRITERIA,
        },
    }
    if has_transition:
        q["trans_valence"] = {
            "type": "score",
            "instructions": "Judge the `transition` excerpt only: the moment the "
                            "music changes or stops. How positive or negative is it?",
            "criteria": VALENCE_ANCHORS,
        }
        q["trans_arousal"] = {
            "type": "score",
            "instructions": "Judge the `transition` excerpt only: the moment the "
                            "music changes or stops. How calm or intense is it?",
            "criteria": AROUSAL_ANCHORS,
        }
        q["trans_mood"] = {
            "type": "choice",
            "instructions": "Which single mood does the `transition` excerpt carry? "
                            "This is the moment the music changes or stops.",
            "criteria": MOOD_CRITERIA,
        }
    return q


def read_axis(answers, qid, axis, window, scene, start, end):
    level, conf = TypeSafe.score(answers or {}, qid)
    rec = {"window": window, "kind": "axis", "axis": axis, "value": None,
           "confidence": round(conf, 3), "abstained": False, "reason": "",
           "scene": scene, "start_line": start, "end_line": end}
    if answers is None:
        rec["abstained"], rec["reason"] = True, "call_failed"
    elif level is None:
        rec["abstained"], rec["reason"] = True, "off_set"
    elif conf < FLOOR:
        rec["abstained"], rec["reason"] = True, "under_floor"
    else:
        rec["value"] = round(level - (VALENCE_SHIFT if axis == "valence" else 0.0), 3)
    return rec


def read_choice(answers, qid, window, scene, start, end):
    choice, conf = TypeSafe.choice(answers or {}, qid)
    rec = {"window": window, "kind": "mood", "answer": None,
           "confidence": round(conf, 3), "abstained": False, "reason": "",
           "scene": scene, "start_line": start, "end_line": end}
    if answers is None:
        rec["abstained"], rec["reason"] = True, "call_failed"
    elif choice not in MOOD_CRITERIA:
        rec["abstained"], rec["reason"] = True, "off_set"
    elif choice == "unclear":
        rec["abstained"], rec["reason"] = True, "unclear"
    elif conf < FLOOR:
        rec["abstained"], rec["reason"] = True, "under_floor"
    else:
        rec["answer"] = choice
    return rec


def questions_answered(answers, span, mid, tail):
    scene, s, e = span["scene"], span["start_line"], span["end_line"]
    out = [read_axis(answers, "mid_valence", "valence", "middle", scene, s, e),
           read_axis(answers, "mid_arousal", "arousal", "middle", scene, s, e),
           read_choice(answers, "mid_mood", "middle", scene, s, e)]
    if tail:
        out += [read_axis(answers, "trans_valence", "valence", "transition", scene, s, e),
                read_axis(answers, "trans_arousal", "arousal", "transition", scene, s, e),
                read_choice(answers, "trans_mood", "transition", scene, s, e)]
    return out


# --- statistics ---------------------------------------------------------------

def _pct(vals, p):
    s = sorted(vals)
    if not s:
        return None
    k = (len(s) - 1) * p
    f, c = math.floor(k), math.ceil(k)
    if f == c:
        return s[int(k)]
    return s[f] * (c - k) + s[c] * (k - f)


def iqr(vals):
    return None if len(vals) < 2 else round(_pct(vals, 0.75) - _pct(vals, 0.25), 3)


def mean_sd(vals):
    if not vals:
        return None, None
    m = round(statistics.fmean(vals), 3)
    sd = round(statistics.stdev(vals), 3) if len(vals) > 1 else 0.0
    return m, sd


def pearson(xs, ys):
    n = len(xs)
    if n < 2:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return None if dx == 0 or dy == 0 else round(num / (dx * dy), 3)


# --- per-track aggregation ----------------------------------------------------

def _span_values(span, window, axis):
    return [a["value"] for a in span["answers"]
            if a["kind"] == "axis" and a["axis"] == axis and a["window"] == window
            and not a["abstained"]]


def aggregate_track(spans):
    """A track as a point with a spread. Each span contributes one value per
    axis -- the mean of the windows it has -- so a short span and a long span
    count the same. The primary read is the middle window; the transition is
    reported beside it."""
    val_span, aro_span = [], []
    val_windows, aro_windows = [], []
    val_trans, aro_trans = [], []
    votes = Counter()
    votes_mid = Counter()
    abst = Counter()
    counted = 0
    counted_windows = set()
    for sp in spans:
        mv = _span_values(sp, "middle", "valence")
        ma = _span_values(sp, "middle", "arousal")
        mv = mv if mv else (_span_values(sp, "transition", "valence"))
        ma = ma if ma else (_span_values(sp, "transition", "arousal"))
        if mv:
            val_span.append(statistics.fmean(mv))
        if ma:
            aro_span.append(statistics.fmean(ma))
        val_windows += [a["value"] for a in sp["answers"]
                        if a["kind"] == "axis" and a["axis"] == "valence" and not a["abstained"]]
        aro_windows += [a["value"] for a in sp["answers"]
                        if a["kind"] == "axis" and a["axis"] == "arousal" and not a["abstained"]]
        val_trans += _span_values(sp, "transition", "valence")
        aro_trans += _span_values(sp, "transition", "arousal")
        if any(not a["abstained"] for a in sp["answers"]):
            counted += 1
        for a in sp["answers"]:
            if a["kind"] == "axis" and not a["abstained"]:
                counted_windows.add((sp["scene"], sp["start_line"], a["window"]))
        for a in sp["answers"]:
            if a["kind"] == "mood":
                if a["abstained"]:
                    abst[a["reason"]] += 1
                else:
                    votes[a["answer"]] += 1
                    if a["window"] == "middle":
                        votes_mid[a["answer"]] += 1
    mv, sv = mean_sd(val_span)
    ma, sa = mean_sd(aro_span)
    ranked = sorted(votes, key=lambda m: (-votes[m], MOODS.index(m)))
    winner = ranked[0] if ranked else None
    tie = len(ranked) > 1 and votes[ranked[0]] == votes[ranked[1]]
    return {
        "mean_valence": mv, "sd_valence": sv, "iqr_valence": iqr(val_windows),
        "mean_arousal": ma, "sd_arousal": sa, "iqr_arousal": iqr(aro_windows),
        "mean_valence_transition": mean_sd(val_trans)[0],
        "mean_arousal_transition": mean_sd(aro_trans)[0],
        "valence_values": [round(v, 3) for v in val_span],
        "arousal_values": [round(v, 3) for v in aro_span],
        "spans_counted": counted,
        "windows_counted": len(counted_windows),
        "abstentions": dict(abst),
        "vote_counts": dict(votes),
        "vote_counts_middle": dict(votes_mid),
        "categorical_winner": winner,
        "categorical_tie": tie,
    }


# --- assignment ---------------------------------------------------------------

def assign_moods(centroids, beds):
    """Greedy global nearest: sort every (mood, track) pair by distance and take
    a pair when neither side is taken. Beds are not eligible. A mood whose
    nearest track is farther than FAR_BOUND is reported as having no cue."""
    eligible = {t: c for t, c in centroids.items() if t not in beds}
    pairs = []
    for mood, (tv, ta, _why) in MOOD_TARGETS.items():
        for track, (v, a) in eligible.items():
            d = math.hypot(tv - v, ta - a)
            pairs.append((d, mood, track))
    pairs.sort()
    taken_moods, taken_tracks, out = set(), set(), {}
    for d, mood, track in pairs:
        if mood in taken_moods or track in taken_tracks:
            continue
        out[mood] = {"track": track, "distance": round(d, 3)}
        taken_moods.add(mood)
        taken_tracks.add(track)
    # nearest and runner-up per mood, for the report
    detail = {}
    for mood in MOOD_TARGETS:
        near = sorted(((math.hypot(MOOD_TARGETS[mood][0] - v, MOOD_TARGETS[mood][1] - a), t)
                       for t, (v, a) in eligible.items()))
        chosen = out.get(mood)
        runner = next(((t, round(d, 3)) for d, t in near
                       if not chosen or t != chosen["track"]), None)
        detail[mood] = {
            "target": {"valence": MOOD_TARGETS[mood][0], "arousal": MOOD_TARGETS[mood][1]},
            "reason": MOOD_TARGETS[mood][2],
            "assigned": chosen["track"] if chosen else None,
            "distance": chosen["distance"] if chosen else (round(near[0][0], 3) if near else None),
            "far": bool(chosen and chosen["distance"] > FAR_BOUND),
            "runner_up": {"track": runner[0], "distance": runner[1]} if runner else None,
        }
    return out, detail


# --- expression-label cross-check ---------------------------------------------

def load_expression_labels(path, inventory_dir):
    """Per-line labels. `expression_labels.json` is keyed by sprite asset (915
    entries, 126 distinct `provenance.context.receipt` line keys); the true
    per-line file is `expression_labels_pilot_lines.jsonl`, one record per
    dialogue line with `scene` and `source_line`. The join key is
    (scene, source_line), the same line number `parse_scene` reports."""
    out = {}
    used = os.path.join(inventory_dir, "expression_labels_pilot_lines.jsonl")
    if os.path.isfile(used):
        with open(used, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    o = json.loads(line)
                except ValueError:
                    continue
                e = o.get("expression")
                if e:
                    out[(o.get("scene"), o.get("source_line"))] = (e, o.get("confidence"))
    return out, used


def crosscheck(tracks, labels, parsed):
    """The emotion mix under each track and its agreement with the axes."""
    cov = {"spans_with_labels": 0, "spans_total": 0, "lines_joined": 0,
           "lines_in_spans": 0}
    xs, ys, names = [], [], []
    for track, t in tracks.items():
        mix = Counter()
        conf_mix = Counter()
        for sp in t["spans"]:
            lines = [r["line"] for r in parsed.get(sp["scene"], [])]
            inside = [ln for ln in lines if sp["start_line"] <= ln <= sp["end_line"]]
            cov["lines_in_spans"] += len(inside)
            hit = 0
            for ln in inside:
                got = labels.get((sp["scene"], ln))
                if got:
                    mix[got[0]] += 1
                    conf_mix[got[1] or "-"] += 1
                    cov["lines_joined"] += 1
                    hit += 1
            cov["spans_total"] += 1
            if hit:
                cov["spans_with_labels"] += 1
        vals = [EXPRESSION_VALENCE[e] for e in mix if e in EXPRESSION_VALENCE
                for _ in range(mix[e])]
        t["label_crosscheck"] = {
            "mix": dict(mix.most_common()),
            "confidence_mix": dict(conf_mix),
            "lines_joined": sum(mix.values()),
            "mean_label_valence": round(statistics.fmean(vals), 3) if vals else None,
            "label_valence_n": len(vals),
        }
        if vals and t["mean_valence"] is not None:
            xs.append(statistics.fmean(vals))
            ys.append(t["mean_valence"])
            names.append(track)
    return cov, pearson(xs, ys), names


# --- stability ----------------------------------------------------------------

def pick_stability(spans, limit):
    """Events spread across tracks: one from each track in turn, newest scene
    order within the track, until the cap is reached."""
    by_track = defaultdict(list)
    for sp in spans:
        by_track[sp["track"]].append(sp)
    for v in by_track.values():
        v.sort(key=lambda s: (s["scene"], s["start_line"]))
    picked, i = [], 0
    while len(picked) < limit:
        added = False
        for track in sorted(by_track):
            if i < len(by_track[track]):
                picked.append(by_track[track][i])
                added = True
                if len(picked) >= limit:
                    break
        if not added:
            break
        i += 1
    return picked


def stability_questions():
    q = {}
    for place, criteria in (("head", None), ("middle", None)):
        q[f"{place}_valence"] = {"type": "score", "criteria": VALENCE_ANCHORS,
                                 "instructions": f"How positive or negative is the `{place}` excerpt? Judge `{place}` only."}
        q[f"{place}_arousal"] = {"type": "score", "criteria": AROUSAL_ANCHORS,
                                 "instructions": f"How calm or intense is the `{place}` excerpt? Judge `{place}` only."}
        q[f"{place}_mood"] = {"type": "choice", "criteria": MOOD_CRITERIA,
                              "instructions": f"Which single mood does the `{place}` excerpt carry? Judge `{place}` only."}
    return q


# --- main ---------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="read BGM tracks as points on valence/arousal axes")
    ap.add_argument("--inventory", default=INVENTORY)
    ap.add_argument("--limit", type=int, default=0, help="max spans this run (calibration)")
    ap.add_argument("--tracks", default="", help="comma-separated track ids")
    ap.add_argument("--window", type=int, default=WINDOW)
    ap.add_argument("--stability", type=int, default=STABILITY_SPANS)
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--dry-run", action="store_true", help="parse and aggregate, make no call")
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args()

    width = args.window
    with open(args.inventory, encoding="utf-8") as f:
        inv = json.load(f)
    corpus = str(inv.get("corpus") or CORPUS)
    scenario_dir = os.path.join(corpus, "data", "scenario")
    out_dir = os.path.dirname(os.path.abspath(args.inventory))
    out_json = os.path.join(out_dir, "bgm_mood_axes.json")
    out_md = os.path.join(out_dir, "bgm_mood_axes.md")

    keep = {t.strip() for t in args.tracks.split(",") if t.strip()}
    spans = [sp for sp in inv.get("bgm_spans", []) if not keep or sp["track"] in keep]
    spans.sort(key=lambda s: (s["track"], s["scene"], s["start_line"]))
    if args.limit:
        spans = spans[:args.limit]

    parsed, rawlines, files = {}, {}, {}
    for sp in spans:
        scene = sp["scene"]
        if scene in parsed:
            continue
        path = os.path.join(scenario_dir, scene + ".ks")
        files[scene] = path
        if os.path.isfile(path):
            parsed[scene] = parse_scene(path)
            rawlines[scene] = _read_text(path).splitlines()
        else:
            parsed[scene] = []
            rawlines[scene] = []

    labels, label_file = load_expression_labels(
        os.path.join(out_dir, "expression_labels.json"), out_dir)

    print(f"[bgm_mood_axes] corpus {corpus}")
    print(f"[bgm_mood_axes] window {width} records, {len(spans)} span(s), "
          f"all spans included, floor {FLOOR}, use '{USE}'")
    print(f"[bgm_mood_axes] expression labels: {len(labels)} line labels from "
          f"{os.path.basename(label_file)}")

    cfg = _Conf(USE_CONFIG)
    ts = TypeSafe(cfg)
    calls = retried = failed_spans = 0
    t0 = datetime.datetime.now()
    call_log = os.path.join(tempfile.gettempdir(), "opencode", "bgm_mood_axes_calls.log")
    os.makedirs(os.path.dirname(call_log), exist_ok=True)
    try:
        os.remove(call_log)
    except OSError:
        pass
    if not args.dry_run:
        logger.setup_file(call_log)
        if not ts.ready(USE):
            sys.exit("[bgm_mood_axes] the typesafe use is not ready (key or switch); nothing called")

    tracks = {}
    for n, sp in enumerate(spans, 1):
        scene = sp["scene"]
        recs = [r for r in parsed.get(scene, [])
                if sp["start_line"] <= r["line"] <= sp["end_line"]]
        if not recs:
            continue
        mid, tail, stratum = windows_for(recs, width)
        end_word = next_command(rawlines.get(scene, []), sp["end_line"])
        state = {"scene": scene, "track_playing": sp["track"], "stratum": stratum,
                 "window_records": len(mid), "middle": excerpt(mid),
                 "ends_with": end_word}
        if tail:
            state["transition"] = excerpt(tail)
        questions = build_questions(tail is not None)

        answers = None
        if args.dry_run:
            answers = None
        else:
            for _ in range(args.retries + 1):
                answers = ts.ask(USE, state, questions)
                calls += 1
                if answers is not None:
                    break
                retried += 1
            if answers is None:
                failed_spans += 1
            if n % 25 == 0:
                print(f"[bgm_mood_axes] {n}/{len(spans)} spans, {calls} call(s)")

        span_rec = {
            "scene": scene, "track": sp["track"], "start_line": sp["start_line"],
            "end_line": sp["end_line"], "records": len(recs), "stratum": stratum,
            "ends_with": end_word,
            "windows": {
                "middle": {"from_line": mid[0]["line"], "to_line": mid[-1]["line"],
                           "excerpt": excerpt(mid)},
                "transition": ({"from_line": tail[0]["line"], "to_line": tail[-1]["line"],
                                "excerpt": excerpt(tail)} if tail else None),
            },
            "answers": questions_answered(answers, sp, mid, tail) if not args.dry_run else [],
        }
        tracks.setdefault(sp["track"], {"spans": []})["spans"].append(span_rec)

    # aggregate
    report_tracks = {}
    centroids = {}
    for track, t in sorted(tracks.items()):
        agg = aggregate_track(t["spans"])
        agg["spans_in_corpus"] = sum(1 for s in inv.get("bgm_spans", []) if s["track"] == track)
        agg["spans_sampled"] = len(t["spans"])
        agg["scenes_seen"] = sorted({s["scene"] for s in t["spans"]})
        agg["spans"] = t["spans"]
        bed = (agg["sd_valence"] is not None and agg["sd_valence"] >= BED_SPREAD) or \
              (agg["sd_arousal"] is not None and agg["sd_arousal"] >= BED_SPREAD)
        agg["general_bed"] = bool(bed)
        report_tracks[track] = agg
        if agg["mean_valence"] is not None and agg["mean_arousal"] is not None:
            centroids[track] = (agg["mean_valence"], agg["mean_arousal"])

    beds = {t for t, a in report_tracks.items() if a["general_bed"]}
    assigned, detail = assign_moods(centroids, beds)
    for mood, got in assigned.items():
        report_tracks[got["track"]]["assigned_mood"] = mood

    cov, corr, corr_tracks = crosscheck(report_tracks, labels, parsed)

    # stability
    stability = None
    if args.stability and not args.dry_run:
        picks = pick_stability(spans, args.stability)
        per_track_head, per_track_mid = defaultdict(list), defaultdict(list)
        axis_deltas, agree_mood, total = [], 0, 0
        rows = []
        for sp in picks:
            scene = sp["scene"]
            recs = [r for r in parsed.get(scene, [])
                    if sp["start_line"] <= r["line"] <= sp["end_line"]]
            if not recs:
                continue
            head = recs[:width]
            mid, tail, _ = windows_for(recs, width)
            st = {"scene": scene, "track_playing": sp["track"],
                  "head": excerpt(head), "middle": excerpt(mid)}
            ans = None
            for _ in range(args.retries + 1):
                ans = ts.ask(USE, st, stability_questions())
                calls += 1
                if ans is not None:
                    break
                retried += 1
            hv, _ = TypeSafe.score(ans or {}, "head_valence")
            ha, _ = TypeSafe.score(ans or {}, "head_arousal")
            mv, _ = TypeSafe.score(ans or {}, "middle_valence")
            ma, _ = TypeSafe.score(ans or {}, "middle_arousal")
            hc, _ = TypeSafe.choice(ans or {}, "head_mood")
            mc, _ = TypeSafe.choice(ans or {}, "middle_mood")
            row = {"scene": scene, "track": sp["track"],
                   "head": {"valence": hv, "arousal": ha, "mood": hc},
                   "middle": {"valence": mv, "arousal": ma, "mood": mc}}
            rows.append(row)
            for a, b in ((hv, mv), (ha, ma)):
                if a is not None and b is not None:
                    axis_deltas.append(abs(a - b))
            total += 1
            if hc in MOOD_CRITERIA and mc in MOOD_CRITERIA and hc != "unclear" and mc != "unclear":
                if hc == mc:
                    agree_mood += 1
            if mv is not None:
                per_track_mid[sp["track"]].append(mv - VALENCE_SHIFT)
            if hv is not None:
                per_track_head[sp["track"]].append(hv - VALENCE_SHIFT)
            if ma is not None:
                per_track_mid[sp["track"] + "|a"].append(ma)
            if ha is not None:
                per_track_head[sp["track"] + "|a"].append(ha)
        moved = {}
        for track in sorted(set(k.split("|")[0] for k in per_track_mid)):
            mm = statistics.fmean(per_track_mid[track]) if per_track_mid.get(track) else None
            hh = statistics.fmean(per_track_head[track]) if per_track_head.get(track) else None
            ma = statistics.fmean(per_track_mid[track + "|a"]) if per_track_mid.get(track + "|a") else None
            ha = statistics.fmean(per_track_head[track + "|a"]) if per_track_head.get(track + "|a") else None
            delta = None
            if None not in (mm, hh, ma, ha):
                delta = round(math.hypot(mm - hh, ma - ha), 3)
            moved[track] = {"n": len(per_track_mid.get(track, [])),
                            "head_valence": round(hh, 3) if hh is not None else None,
                            "middle_valence": round(mm, 3) if mm is not None else None,
                            "head_arousal": round(ha, 3) if ha is not None else None,
                            "middle_arousal": round(ma, 3) if ma is not None else None,
                            "centroid_move": delta,
                            "untrusted": bool(delta is not None and delta > 0.75)}
        stability = {
            "spans": total,
            "mean_axis_abs_delta": round(statistics.fmean(axis_deltas), 3) if axis_deltas else None,
            "mood_agreement": round(agree_mood / total, 3) if total else None,
            "mood_agree_n": agree_mood,
            "moved_tracks": {t: v for t, v in moved.items() if v["untrusted"]},
            "per_track": moved,
            "rows": rows,
        }

    seconds = (datetime.datetime.now() - t0).total_seconds()
    in_tok = out_tok = 0
    if os.path.isfile(call_log):
        with open(call_log, encoding="utf-8") as f:
            for line in f:
                m = re.search(r"in=(\d+) out=(\d+)", line)
                if m:
                    in_tok += int(m.group(1))
                    out_tok += int(m.group(2))

    report = {
        "generated": datetime.datetime.now().isoformat(timespec="seconds"),
        "corpus": corpus, "inventory": args.inventory,
        "use": USE, "model": ts.model, "floor": FLOOR,
        "dry_run": bool(args.dry_run),
        "sampling": {
            "window_records": width,
            "rule": "all 500 spans; one centred window at the span's middle plus the "
                    "span's transition (last window records) when the span is longer "
                    "than the window; a shorter span is its own middle only",
            "spans_sampled": len(spans),
            "strata": dict(Counter(s["stratum"] for t in tracks.values() for s in t["spans"])),
            "span_weighting": "one value per span per axis (mean of its counted windows), "
                              "so every span counts the same whatever its length",
        },
        "axes": {"valence": {"anchors": VALENCE_ANCHORS, "range": [-2, 2]},
                 "arousal": {"anchors": AROUSAL_ANCHORS, "range": [0, 4]}},
        "mood_targets": {m: {"valence": v, "arousal": a, "reason": why}
                         for m, (v, a, why) in MOOD_TARGETS.items()},
        "bounds": {"far_bound": FAR_BOUND, "bed_spread": BED_SPREAD},
        "calls": {"made": calls, "retried": retried, "spans_failed": failed_spans,
                  "seconds": round(seconds, 1), "input_tokens": in_tok,
                  "output_tokens": out_tok,
                  "cost_usd": round(in_tok * PRICE_PER_MTOK / 1e6, 6)},
        "provisional_mood_bgm": dict(MOOD_BGM),
        "assignment": detail,
        "general_beds": sorted(beds),
        "crosscheck": {"coverage": cov, "pearson_valence": corr,
                       "tracks_in_correlation": corr_tracks,
                       "label_file": label_file},
        "stability": stability,
        "tracks": report_tracks,
    }

    if args.dry_run or args.no_write:
        print("[bgm_mood_axes] not written")
    else:
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        with open(out_md, "w", encoding="utf-8") as f:
            f.write(render_md(report))
        print(f"[bgm_mood_axes] wrote {out_json}")
        print(f"[bgm_mood_axes] wrote {out_md}")

    print(f"[bgm_mood_axes] {calls} call(s), {failed_spans} span(s) failed, "
          f"{in_tok} in / {out_tok} out tokens, ${in_tok * PRICE_PER_MTOK / 1e6:.4f}, "
          f"{seconds:.1f}s")
    print_table(report_tracks, beds)


def print_table(tracks, beds):
    print(f"{'track':8s} {'spans':>5s} {'val':>6s} {'sdv':>5s} {'aro':>6s} {'sda':>5s} "
          f"{'winner':<8s} {'bed':<4s} assigned")
    for track in sorted(tracks):
        t = tracks[track]
        print(f"{track:8s} {t['spans_sampled']:5d} {str(t['mean_valence']):>6s} "
              f"{str(t['sd_valence']):>5s} {str(t['mean_arousal']):>6s} "
              f"{str(t['sd_arousal']):>5s} {str(t['categorical_winner'] or '-'):<8s} "
              f"{'BED' if track in beds else '':<4s} {t.get('assigned_mood', '')}")


def render_md(report):
    L = []
    L.append("# BGM tracks as points on valence and arousal\n")
    L.append(f"Generated {report['generated']} with `{report['model']}` over "
             f"`{os.path.basename(report['inventory'])}`. Analysis only; "
             f"`sim/scene.py:MOOD_BGM` and the bundle were not edited.\n")
    s, c = report["sampling"], report["calls"]
    L.append("## Method\n")
    L.append(f"- Sampling: {s['rule']}. Window {s['window_records']} dialogue records, "
             f"{s['spans_sampled']} span(s) sampled; strata {s['strata']}.")
    L.append(f"- Weighting: {s['span_weighting']}. Spread is the sample standard "
             f"deviation (n-1) across span values; the IQR is also in the JSON.")
    L.append(f"- Questions per window: two `score` axes -- valence "
             f"({'/'.join(report['axes']['valence']['anchors'])}) and arousal "
             f"({'/'.join(report['axes']['arousal']['anchors'])}) -- plus the "
             f"categorical `choice` over the seven moods and `unclear` as a cross-check.")
    L.append(f"- Floor {report['floor']}; `unclear`, off-set, under-floor and a failed "
             f"call are abstentions and never values.")
    L.append(f"- Calls: {c['made']} made, {c['spans_failed']} span(s) failed, "
             f"{c['input_tokens']} input tokens, ${c['cost_usd']:.4f}, {c['seconds']}s.\n")
    L.append("## Mood targets and the nearest track\n")
    L.append("| mood | target (valence, arousal) | reason | assigned track | distance | runner-up |")
    L.append("|---|---|---|---|---|---|")
    for mood in MOODS:
        d = report["assignment"].get(mood, {})
        tgt = d.get("target", {})
        ru = d.get("runner_up") or {}
        far = " **far**" if d.get("far") else ""
        L.append(f"| {mood} | ({tgt.get('valence')}, {tgt.get('arousal')}) | "
                 f"{d.get('reason', '')} | {d.get('assigned') or '-'}{far} | "
                 f"{d.get('distance')} | {ru.get('track', '-')} ({ru.get('distance', '-')}) |")
    L.append("\n## Per track\n")
    L.append("| track | spans | mean val | sd val | mean aro | sd aro | cat winner | votes | "
             "assigned |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for track in sorted(report["tracks"]):
        t = report["tracks"][track]
        votes = ", ".join(f"{k}:{v}" for k, v in sorted(t["vote_counts"].items(),
                                                        key=lambda kv: -kv[1])) or "-"
        L.append(f"| {track} | {t['spans_sampled']} | {t['mean_valence']} | "
                 f"{t['sd_valence']} | {t['mean_arousal']} | {t['sd_arousal']} | "
                 f"{t['categorical_winner'] or '-'} | {votes} | "
                 f"{t.get('assigned_mood', '-')} |")
    L.append("\n## General beds (spread >= %.2f, not a mood cue)\n" % report["bounds"]["bed_spread"])
    L.append(", ".join(report["general_beds"]) or "none")
    cov = report["crosscheck"]["coverage"]
    L.append("\n## Expression-label cross-check\n")
    L.append(f"- Join key (scene, source_line) from `{os.path.basename(report['crosscheck']['label_file'])}`; "
             f"{cov['lines_joined']} of {cov['lines_in_spans']} lines inside the spans "
             f"joined ({cov['spans_with_labels']}/{cov['spans_total']} spans with any label).")
    L.append(f"- Pearson correlation between a track's mean classifier valence and its "
             f"mean label valence: {report['crosscheck']['pearson_valence']} "
             f"over {len(report['crosscheck']['tracks_in_correlation'])} tracks.")
    st = report["stability"]
    L.append("\n## Stability (head vs middle placement)\n")
    if st:
        L.append(f"- {st['spans']} spans read twice; mean absolute axis delta "
                 f"{st['mean_axis_abs_delta']}; categorical agreement "
                 f"{st['mood_agreement']} ({st['mood_agree_n']}/{st['spans']}).")
        L.append(f"- Tracks whose centroid moved more than 0.75 between placements: "
                 f"{', '.join(st['moved_tracks']) or 'none'}.")
    else:
        L.append("- not run")
    L.append("")
    return "\n".join(L)


class _Section:
    def __init__(self, data):
        self.__dict__.update(data)


class _Conf:
    """The shape `TypeSafe` reads: attributes for the section, `raw` for uses."""

    def __init__(self, data):
        self.raw = data
        self.typesafe = _Section(data["typesafe"])


if __name__ == "__main__":
    main()
