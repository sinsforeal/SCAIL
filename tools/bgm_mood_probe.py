# -*- coding: utf-8 -*-
"""Ground the music mood map in the game's own text.

The staging pass (`sim/scene.py`) chooses background music from `MOOD_BGM`,
a provisional mood-to-track table read off usage counts because the game
never labelled a track with a mood. This tool asks the game's own scripts
instead: at the points where a track was actually playing, it classifies the
mood of the scene around it and lets the votes decide the track's mood.

Scope. This is an analysis tool. Nothing in the runtime imports it, it writes
no save and it changes no live path. It reads the extracted corpus and one
inventory file, calls the real System One client (`typesafe.py`) and writes a
JSON and a small `.md` beside that inventory. `sim/scene.py:MOOD_BGM` is left
untouched; the coordinator reads the evidence and decides.

Sampling, bounded by design. Every span in the inventory is a stretch where
one track plays. This tool does not read every span. For each track it takes
up to `SPANS_PER_TRACK` spans, one per distinct scene, and for each sampled
span it reads two windows of `WINDOW` dialogue records: the head (the first
records after the `@playBgm`) and the transition (the last records before the
track changes or stops). Both windows belong to the span's own track, so a
label attaches to the outgoing track. The caps are printed in the run header
and carried in the output.

Questions. One botched classifier call is not worth replaying, so a failed
call, an `unclear` answer or an answer under the configured floor is recorded
as an abstention and never counted as a vote (`docs/system-one.md` section 4).

    python tools/bgm_mood_probe.py                 # full run, writes the outputs
    python tools/bgm_mood_probe.py --limit 12 --no-write   # calibration
    python tools/bgm_mood_probe.py --tracks BGM19,BGM21    # one or two tracks

Cost is input tokens only (output is free at jev 1.13); the tool totals the
`[typesafe] ... in= out=` lines the client logs and prints the spend.
"""

import argparse
import datetime
import json
import os
import re
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

USE = "bgm_mood"                 # the one use name, per docs/system-one.md section 4
FLOOR = 0.40                     # the use's threshold; 8-way choice spreads confidence
WINDOW = 5                       # dialogue records per window
SPANS_PER_TRACK = 6              # one per distinct scene, at most
CHARS_PER_WINDOW = 900           # excerpt cap, to keep the state bounded
PRICE_PER_MTOK = 0.042           # USD per million input tokens (jev 1.13)

USE_CONFIG = {"typesafe": {
    "enabled": True, "model": "jev-latest", "key_file": "secerts/typesafe.txt",
    "timeout_seconds": 60, "floor": FLOOR,
    "uses": {USE: {"enabled": True, "threshold": FLOOR}},
}}

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
ENERGY_CRITERIA = {
    "quiet": "calm, still, little happening; low energy",
    "steady": "ordinary conversational energy",
    "agitated": "raised energy: shouting, panic, fast action or strong feeling",
    "unclear": "the excerpt carries no readable energy",
}
# The second question exists because mood and energy are orthogonal for a music
# cue -- a quiet `tense` scene and an agitated one are different tracks -- and
# because it is an independent second read that can break a mood tie.


class _Section:
    def __init__(self, data):
        self.__dict__.update(data)


class _Conf:
    """The shape `TypeSafe` reads: attributes for the section, `raw` for uses."""

    def __init__(self, data):
        self.raw = data
        self.typesafe = _Section(data["typesafe"])


def _read_text(path):
    with open(path, "rb") as f:
        return f.read().decode("cp932", "replace")


def parse_scene(path):
    """The dialogue records of one `.ks` file, in file order.

    A record is one `@Talk` plus the un-tagged lines that follow it until the
    next command; the speaker is read from the tag. Returns (records, lines).
    """
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
    text = "\n".join(out)
    return text[:CHARS_PER_WINDOW]


def pick_spans(spans, keep_tracks, per_track):
    """Up to `per_track` spans per track, one per distinct scene, richest first
    so both windows have something to read."""
    by_track = defaultdict(list)
    for sp in spans:
        if not keep_tracks or sp["track"] in keep_tracks:
            by_track[sp["track"]].append(sp)
    chosen = []
    for track in sorted(by_track):
        best = {}
        for sp in by_track[track]:
            sc = sp["scene"]
            if sc not in best or sp["records"] > best[sc]["records"]:
                best[sc] = sp
        picked = sorted(best.values(), key=lambda s: (s["scene"], s["start_line"]))
        chosen.extend(picked[:per_track])
    return chosen


def next_command(lines, end_line):
    """What ends the span: the first `@playBgm`/`@stopBgm` after its last line.

    The inventory's `play_bgm_events` holds only `@playBgm` (every event has a
    `file`), so a stop is not in that list. The raw script is read instead, so
    the transition window knows what actually follows it."""
    for i in range(end_line, len(lines)):
        s = lines[i].strip()
        if s.startswith("@playBgm"):
            m = re.search(r"file=([^\s]+)", s)
            return "changes to " + (m.group(1) if m else "another track")
        if s.startswith("@stopBgm"):
            return "stops"
    return "the scene ends"


def build_state(span, head, tail, end_word):
    state = {
        "scene": span["scene"],
        "track_playing": span["track"],
        "head": excerpt(head),
        "ends_with": end_word,
    }
    state["transition"] = excerpt(tail) if tail else ""
    return state


def build_questions(has_tail):
    q = {
        "head_mood": {
            "type": "choice",
            "instructions": "What mood does the `head` excerpt carry? Judge `head` only.",
            "criteria": MOOD_CRITERIA,
        },
        "head_energy": {
            "type": "choice",
            "instructions": "What is the energy of the `head` excerpt? Judge `head` only.",
            "criteria": ENERGY_CRITERIA,
        },
    }
    if has_tail:
        q["transition_mood"] = {
            "type": "choice",
            "instructions": "What mood does the `transition` excerpt carry? Judge "
                            "`transition` only; this is the moment the music "
                            "changes or stops.",
            "criteria": MOOD_CRITERIA,
        }
        q["transition_energy"] = {
            "type": "choice",
            "instructions": "What is the energy of the `transition` excerpt? Judge "
                            "`transition` only.",
            "criteria": ENERGY_CRITERIA,
        }
    return q


def read_sample(answers, win, kind, span, head, tail, end_word):
    """One window's raw answer and its verdict, including the abstention."""
    qid = f"{win}_{kind}"
    choice, conf = TypeSafe.choice(answers or {}, qid)
    rec = {"window": win, "kind": kind,
           "lines": [r["line"] for r in (head if win == "head" else tail)],
           "answer": choice if choice in (MOOD_CRITERIA if kind == "mood"
                                          else ENERGY_CRITERIA) else None,
           "confidence": round(conf, 3),
           "abstained": False, "reason": ""}
    if answers is None:
        rec["abstained"], rec["reason"] = True, "call_failed"
    elif rec["answer"] is None:
        rec["abstained"], rec["reason"] = True, "off_set"
    elif rec["answer"] == "unclear":
        rec["abstained"], rec["reason"] = True, "unclear"
    elif conf < FLOOR:
        rec["abstained"], rec["reason"] = True, "under_floor"
    return rec


def aggregate(track, spans_all, samples, events_by_scene):
    votes, energy = Counter(), Counter()
    for s in samples:
        if s["kind"] == "mood" and not s["abstained"]:
            votes[s["answer"]] += 1
        if s["kind"] == "energy" and not s["abstained"]:
            energy[s["answer"]] += 1
    chosen, tie = None, False
    if votes:
        conf_sum = defaultdict(float)
        for s in samples:
            if s["kind"] == "mood" and not s["abstained"]:
                conf_sum[s["answer"]] += s["confidence"]
        ranked = sorted(votes, key=lambda m: (-votes[m], -conf_sum[m], MOODS.index(m)))
        chosen = ranked[0]
        tie = len(ranked) > 1 and votes[ranked[0]] == votes[ranked[1]]
    return chosen, tie, dict(votes), dict(energy)


def main():
    ap = argparse.ArgumentParser(description="map BGM tracks to moods from the game text")
    ap.add_argument("--inventory", default=INVENTORY)
    ap.add_argument("--limit", type=int, default=0, help="max spans this run (calibration)")
    ap.add_argument("--tracks", default="", help="comma-separated track ids")
    ap.add_argument("--per-track", type=int, default=SPANS_PER_TRACK)
    ap.add_argument("--window", type=int, default=WINDOW)
    ap.add_argument("--retries", type=int, default=2,
                    help="extra attempts when a call fails (a lost sample is worth one retry)")
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args()

    window = args.window
    with open(args.inventory, encoding="utf-8") as f:
        inv = json.load(f)
    corpus = str(inv.get("corpus") or CORPUS)
    scenario_dir = os.path.join(corpus, "data", "scenario")
    out_dir = os.path.dirname(os.path.abspath(args.inventory))
    out_json = os.path.join(out_dir, "bgm_mood_map.json")
    out_md = os.path.join(out_dir, "bgm_mood_map.md")

    events_by_scene = defaultdict(list)
    for ev in inv.get("play_bgm_events", []):
        events_by_scene[ev["scene"]].append(ev)
    for v in events_by_scene.values():
        v.sort(key=lambda e: e["source_line"])

    keep = {t.strip() for t in args.tracks.split(",") if t.strip()}
    spans = pick_spans(inv.get("bgm_spans", []), keep, args.per_track)
    if args.limit:
        spans = spans[:args.limit]

    files = {}
    for sp in spans:
        files.setdefault(sp["scene"], os.path.join(scenario_dir, sp["scene"] + ".ks"))

    print(f"[bgm_mood] corpus {corpus}")
    print(f"[bgm_mood] window {window} records, up to {args.per_track} span(s)/track, "
          f"{len(spans)} span(s) sampled, floor {FLOOR}, use '{USE}'")

    cfg = _Conf(USE_CONFIG)
    ts = TypeSafe(cfg)
    if not ts.ready(USE):
        sys.exit("[bgm_mood] the typesafe use is not ready (key or switch); nothing called")

    call_log = os.path.join(tempfile.gettempdir(), "opencode", "bgm_mood_calls.log")
    os.makedirs(os.path.dirname(call_log), exist_ok=True)
    try:
        os.remove(call_log)
    except OSError:
        pass
    logger.setup_file(call_log)

    parsed = {}
    rawlines = {}
    tracks = {}
    calls = 0
    retried = 0
    failed_spans = 0
    t0 = datetime.datetime.now()
    for n, sp in enumerate(spans, 1):
        scene = sp["scene"]
        if scene not in parsed:
            path = files[scene]
            if os.path.isfile(path):
                parsed[scene] = parse_scene(path)
                rawlines[scene] = _read_text(path).splitlines()
            else:
                parsed[scene] = []
                rawlines[scene] = []
        recs = [r for r in parsed[scene]
                if sp["start_line"] <= r["line"] <= sp["end_line"]]
        if not recs:
            continue
        head = recs[:window]
        tail = recs[-window:] if len(recs) > window else None
        end_word = next_command(rawlines[scene], sp["end_line"])
        state = build_state(sp, head, tail, end_word)
        questions = build_questions(tail is not None)
        answers = None
        for attempt in range(args.retries + 1):
            answers = ts.ask(USE, state, questions)
            calls += 1
            if answers is not None:
                break
            retried += 1
        if answers is None:
            failed_spans += 1
        samples = [read_sample(answers, "head", "mood", sp, head, tail, end_word),
                   read_sample(answers, "head", "energy", sp, head, tail, end_word)]
        if tail:
            samples.append(read_sample(answers, "transition", "mood", sp, head, tail, end_word))
            samples.append(read_sample(answers, "transition", "energy", sp, head, tail, end_word))
        tracks.setdefault(sp["track"], {"spans": []})
        tracks[sp["track"]]["spans"].append({
            "scene": scene, "start_line": sp["start_line"], "end_line": sp["end_line"],
            "records": len(recs), "ends_with": end_word,
            "head_excerpt": excerpt(head),
            "transition_excerpt": excerpt(tail) if tail else None,
            "answers": samples,
        })
        if n % 20 == 0:
            print(f"[bgm_mood] {n}/{len(spans)} spans, {calls} call(s)")

    seconds = (datetime.datetime.now() - t0).total_seconds()
    in_tok = out_tok = 0
    failed = 0
    if os.path.isfile(call_log):
        with open(call_log, encoding="utf-8") as f:
            for line in f:
                m = re.search(r"in=(\d+) out=(\d+)", line)
                if m:
                    in_tok += int(m.group(1))
                    out_tok += int(m.group(2))
                elif "call failed" in line or "not called" in line:
                    failed += 1

    report = {"generated": datetime.datetime.now().isoformat(timespec="seconds"),
              "corpus": corpus,
              "inventory": args.inventory,
              "use": USE, "model": ts.model, "floor": FLOOR,
              "sampling": {"window_records": window, "max_spans_per_track": args.per_track,
                           "spans_sampled": len(spans),
                           "rule": "one span per distinct scene per track, richest first; "
                                   "head and transition windows per span"},
              "calls": {"made": calls, "retried": retried, "failed": failed,
                        "spans_failed": failed_spans, "seconds": round(seconds, 1),
                        "input_tokens": in_tok, "output_tokens": out_tok,
                        "cost_usd": round(in_tok * PRICE_PER_MTOK / 1e6, 6)},
              "provisional_mood_bgm": dict(MOOD_BGM),
              "tracks": {}}
    for track in sorted(tracks):
        spans_list = tracks[track]["spans"]
        all_samples = []
        for s in spans_list:
            for a in s["answers"]:
                a["scene"] = s["scene"]
                a["start_line"] = s["start_line"]
                a["end_line"] = s["end_line"]
                all_samples.append(a)
        chosen, tie, votes, energy = aggregate(track, inv.get("bgm_spans", []),
                                               all_samples, events_by_scene)
        report["tracks"][track] = {
            "chosen_mood": chosen, "tie": tie,
            "vote_counts": votes, "energy_counts": energy,
            "spans_in_corpus": sum(1 for s in inv.get("bgm_spans", []) if s["track"] == track),
            "spans_sampled": len(spans_list),
            "head_samples": sum(1 for a in all_samples
                                if a["kind"] == "mood" and a["window"] == "head"),
            "transition_samples": sum(1 for a in all_samples
                                      if a["kind"] == "mood" and a["window"] == "transition"),
            "abstentions": sum(1 for a in all_samples
                               if a["kind"] == "mood" and a["abstained"]),
            "scenes_seen": sorted({s["scene"] for s in spans_list}),
            "spans": spans_list,
        }

    transitions = defaultdict(Counter)
    for sp in spans:
        tr = report["tracks"].get(sp["track"])
        if not tr:
            continue
        for s in sp_samples(report, sp):
            if s["kind"] == "mood" and s["window"] == "transition" and not s["abstained"]:
                transitions[(sp["track"],
                             next_command(rawlines[sp["scene"]], sp["end_line"]))][s["answer"]] += 1
    report["transitions"] = {"%s -> %s" % k: dict(v) for k, v in sorted(transitions.items())}

    diff = compare(report["tracks"])
    report["differences"] = diff

    if args.no_write:
        print("[bgm_mood] --no-write: outputs not written")
    else:
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        with open(out_md, "w", encoding="utf-8") as f:
            f.write(render_md(report, diff))
        print(f"[bgm_mood] wrote {out_json}")
        print(f"[bgm_mood] wrote {out_md}")

    print(f"[bgm_mood] {calls} call(s), {failed} failed, {in_tok} in / {out_tok} out tokens, "
          f"${in_tok * PRICE_PER_MTOK / 1e6:.4f}, {seconds:.1f}s")
    print_tracks(report["tracks"])
    print_differences(diff)


def sp_samples(report, sp):
    """The answer records of one sampled span, for the transition join."""
    tr = report["tracks"].get(sp["track"])
    if not tr:
        return []
    for s in tr["spans"]:
        if s["scene"] == sp["scene"] and s["start_line"] == sp["start_line"]:
            return s["answers"]
    return []


def compare(tracks):
    """The track's chosen mood against the provisional mood-to-track table."""
    out = {"track_chosen": {}, "provisional_ok": [], "provisional_wrong": [],
           "tracks_not_in_provisional": [], "moods_without_a_track": []}
    for track, t in tracks.items():
        out["track_chosen"][track] = t["chosen_mood"]
    image = set(MOOD_BGM.values())
    for mood, prov in sorted(MOOD_BGM.items()):
        got = tracks.get(prov)
        if got is None:
            out["provisional_wrong"].append({"mood": mood, "provisional": prov,
                                             "reason": "not sampled"})
        elif got["chosen_mood"] == mood:
            out["provisional_ok"].append({"mood": mood, "track": prov,
                                          "votes": got["vote_counts"]})
        else:
            out["provisional_wrong"].append(
                {"mood": mood, "provisional": prov,
                 "reads_as": got["chosen_mood"], "votes": got["vote_counts"]})
    for track, t in sorted(tracks.items()):
        if track not in image:
            out["tracks_not_in_provisional"].append(
                {"track": track, "reads_as": t["chosen_mood"], "votes": t["vote_counts"]})
    for mood in MOODS:
        if mood not in (MOOD_BGM if MOOD_BGM else {}):
            out["moods_without_a_track"].append(mood)
    return out


def render_md(report, diff):
    L = []
    L.append("# BGM mood map, read from the game's own text\n")
    L.append(f"Generated {report['generated']} with `{report['model']}` over "
             f"`{os.path.basename(report['inventory'])}`.\n")
    L.append("This is evidence, not a live table. `sim/scene.py:MOOD_BGM` is "
             "provisional and was not edited; the coordinator decides.\n")
    s = report["sampling"]
    c = report["calls"]
    L.append("## Method\n")
    L.append(f"- Sampling: {s['rule']}. Window {s['window_records']} dialogue records, "
             f"at most {s['max_spans_per_track']} span(s) per track, "
             f"{s['spans_sampled']} span(s) sampled.")
    L.append(f"- Questions: `mood` (choice over {', '.join(MOODS)} plus `unclear`) and "
             f"`energy` (quiet/steady/agitated/unclear), per window, from the excerpt alone.")
    L.append(f"- Floor: {report['floor']}; an `unclear` answer or an answer under the "
             f"floor is an abstention and never a vote.")
    L.append(f"- Calls: {c['made']} made, {c['failed']} failed, {c['input_tokens']} input "
             f"tokens, ${c['cost_usd']:.4f}, {c['seconds']}s.\n")
    L.append("## Per track\n")
    L.append("| track | spans in corpus | sampled | head/trans | abstained | votes | chosen | split |")
    L.append("|---|---|---|---|---|---|---|---|")
    for track in sorted(report["tracks"]):
        t = report["tracks"][track]
        votes = ", ".join(f"{k}:{v}" for k, v in sorted(t["vote_counts"].items(),
                                                        key=lambda kv: -kv[1])) or "-"
        split = "split" if (t["tie"] or len(t["vote_counts"]) > 1) else "unanimous"
        L.append(f"| {track} | {t['spans_in_corpus']} | {t['spans_sampled']} | "
                 f"{t['head_samples']}/{t['transition_samples']} | {t['abstentions']} | "
                 f"{votes} | **{t['chosen_mood'] or '-'}** | {split} |")
    L.append("\n## Against the provisional table\n")
    L.append("| mood | provisional track | evidence track(s) with that mood |")
    L.append("|---|---|---|")
    by_mood = defaultdict(list)
    for track, t in report["tracks"].items():
        if t["chosen_mood"]:
            by_mood[t["chosen_mood"]].append(track)
    for mood in MOODS:
        ev = ", ".join(f"{t} ({report['tracks'][t]['vote_counts']})"
                       for t in sorted(by_mood.get(mood, []))) or "-"
        L.append(f"| {mood} | {MOOD_BGM.get(mood, '-')} | {ev} |")
    if diff["provisional_wrong"]:
        L.append("\nProvisional pairings that the votes do not support:\n")
        for d in diff["provisional_wrong"]:
            if d.get("reason"):
                L.append(f"- `{d['mood']}` -> `{d['provisional']}`: {d['reason']}")
            else:
                L.append(f"- `{d['mood']}` -> `{d['provisional']}`: {d['provisional']} "
                         f"reads as **{d['reads_as']}** ({d['votes']})")
    if diff["tracks_not_in_provisional"]:
        L.append("\nTracks the provisional table never names:\n")
        for d in diff["tracks_not_in_provisional"]:
            L.append(f"- `{d['track']}` reads as **{d['reads_as']}** ({d['votes']})")
    L.append("")
    return "\n".join(L)


def print_tracks(tracks):
    print(f"{'track':8s} {'spans':>5s} {'samp':>4s} {'votes':<34s} {'chosen':<9s} split")
    for track in sorted(tracks):
        t = tracks[track]
        votes = ", ".join(f"{k}:{v}" for k, v in sorted(t["vote_counts"].items(),
                                                        key=lambda kv: -kv[1])) or "-"
        split = "split" if (t["tie"] or len(t["vote_counts"]) > 1) else "unan"
        print(f"{track:8s} {t['spans_in_corpus']:5d} {t['spans_sampled']:4d} "
              f"{votes:<34s} {str(t['chosen_mood'] or '-'):<9s} {split}")


def print_differences(diff):
    print("[bgm_mood] against sim/scene.py:MOOD_BGM")
    for d in diff["provisional_wrong"]:
        if d.get("reason"):
            print(f"  {d['mood']:8s} -> {d['provisional']:6s} {d['reason']}")
        else:
            print(f"  {d['mood']:8s} -> {d['provisional']:6s} reads as {d['reads_as']} {d['votes']}")
    for d in diff["tracks_not_in_provisional"]:
        print(f"  (new) {d['track']:6s} reads as {d['reads_as']} {d['votes']}")


if __name__ == "__main__":
    main()
