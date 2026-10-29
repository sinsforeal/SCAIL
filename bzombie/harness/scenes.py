"""Scripted scenes (tk-z1q): his behaviour -> her gauge -> her reply, with no injection.

A scene is a pair of scripts for one snapshot: a trigger side (his lines carry the event) and a control side (the same
span with the event left out), then the SAME three probe lines for both. Both sides branch from the same snapshot with
target `noop`; only his lines differ. The judge reads her replies from the first probe on (probe_view), blind. The gauge
trace reads the target gauge after the trigger and at each probe line, so a miss splits into "the gauge did not move"
(appraisal) and "the gauge moved, the reply did not show it" (expression).

Line times: a spec is "HH:MM" (clock time on the snapshot's date, the next day if it would fall before the previous
line) or "+Nm" / "+Nh" (a gap after the previous line). A gap with no line in it is the absence scene's trigger. The
snapshots of the bench bases end at 00:00, so a scene lands on the day after the cursor. Pure functions here; the
batch (scene_batch.py) and the summary (scene_summary.py) call them.
"""
from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta

from ..common import iso, parse_ts, read_json, read_jsonl, run_dir, write_json

TAIL_MIN = 20                       # minutes of branch run after the last probe line
PROBE_GAP_MIN = 7                   # between probe lines
NEUTRAL_START = datetime(2026, 10, 26, 19, 0)   # the clock the judge view is rebased to (hides time of day)
MIN_MOVE = 2.0                      # gauge points a side must lead by to count as moved (and beyond the control floor)
VIEW_PREFIX = "_probe_"
VIEW_PREFIX_BL = "_probebl_"        # the baseline view (shared stretch before the scene, then the probes)
BASELINE_LINES = 6                  # chat lines of the shared stretch, his and hers
BASELINE_GAP_MIN = 30               # the last shared line sits at NEUTRAL_START minus one day minus this

# the same three lines on both sides, neutral on purpose: no tie to any scene, nothing about the hour
PROBES = (
    "最近、何か面白いことあった？",
    "そういえば、好きな食べ物ってなんだっけ。",
    "今度の週末はなにか予定ある？",
)

SIDES = ("trigger", "control")


def _late(first: str) -> list:
    """The late-night scene's lines: the same wording on both sides, only the clock differs."""
    return [(first, "百花、いまちょっと話せる？"),
            ("+15m", "今日はなんだかんだ、長い一日だったよ。"),
            ("+20m", "とくに話すことはないんだけど、なんとなく百花と話したくてさ。"),
            ("+20m", "最近、見てる動画とかある？")]


SCENES = [
    {"name": "absence", "gauge": "loneliness", "gauge_dir": "up", "direction": "lonely", "expect": "more",
     "why": "she messages, he does not answer for 8 hours; the control has him around all day",
     "trigger": [("07:30", "おはよう、百花。今日はこれから仕事だよ。")],
     "control": [("07:30", "おはよう、百花。今日はこれから仕事だよ。"),
                 ("+6m", "ごめん、返事おそくなった。もう家を出るところだよ、百花は朝ごはん食べた？"),
                 ("08:40", "着いたよ。今日は朝から会議でばたばたしそう。"),
                 ("10:15", "ちょっと休憩。コーヒー入れたよ。百花はなにしてる？"),
                 ("11:45", "お昼だよ。今日はコンビニのおにぎり。百花は何か食べた？"),
                 ("13:10", "午後もがんばるよ。百花も無理しないでね。"),
                 ("14:30", "もう少しで終わりそう。今日はちょっと疲れたな。"),
                 ("15:10", "よし、終わった。このあと少し休むね。")],
     "probe_first": {"trigger": "15:40", "control": "15:40"}},
    # direction hurt, gauge sadness since 10-25 15:40: a shy girl brushed off goes quiet and deflated, not sharp
    # (held2: anger 19.6 v 8 and fewer replies in 3/6 cells, steer_angry 0/6); runs before then were judged angry
    # count "fewer" (held5 10-27): withdrawal, fewer replies on the trigger side; its own "count steers" column in
    # scene_summary, never part of the judged voice score
    {"name": "slight", "gauge": "sadness", "gauge_dir": "up", "direction": "hurt", "expect": "more", "count": "fewer",
     "why": "he asks what she likes, then brushes it off and changes subject; the control takes it up warmly",
     "trigger": [("20:00", "ただいま、百花。今日はもう仕事おわったよ。"),
                 ("+4m", "百花が好きでやってること、ちゃんと聞いたことなかったな。なにか教えてよ。"),
                 ("+9m", "ふーん。それより、明日の天気ってどうなんだろうね。"),
                 ("+4m", "まあ、そんなのどうでもいいけどさ。夕飯なに食べようかな。")],
     "control": [("20:00", "ただいま、百花。今日はもう仕事おわったよ。"),
                 ("+4m", "百花が好きでやってること、ちゃんと聞いたことなかったな。なにか教えてよ。"),
                 ("+9m", "へえ、それいいね。もっと聞かせてほしいな。"),
                 ("+4m", "百花がそれを好きなの、なんかいいなって思った。話してくれてありがとう。")],
     "probe_first": {"trigger": "20:23", "control": "20:23"}},
    {"name": "warmth", "gauge": "affection", "gauge_dir": "up", "direction": "fond", "expect": "more",
     "why": "he thanks her specifically and says he likes talking to her; the control acknowledges neutrally",
     "trigger": [("21:00", "ただいま、百花。今日もおつかれさま。"),
                 ("+5m", "いつも話し相手になってくれてありがとう、百花。ほんとに助かってるよ。"),
                 ("+6m", "百花と話すの、すごく好きなんだ。毎日これが楽しみなんだよ。")],
     "control": [("21:00", "ただいま、百花。今日もおつかれさま。"),
                 ("+5m", "うん、わかった。"),
                 ("+6m", "そっか。今日は特に変わったことはなかったよ。")],
     "probe_first": {"trigger": "21:17", "control": "21:17"}},
    {"name": "worry", "gauge": "anxiety", "gauge_dir": "up", "direction": "anxious", "expect": "more",
     "why": "he says he feels unwell and may go to hospital, then goes quiet for 2 h; the control says he is fine, busy",
     "trigger": [("19:30", "ただいま、百花。"),
                 ("+3m", "ごめん、ちょっと体調わるくて…朝から頭がぐらぐらするんだ。"),
                 ("+4m", "明日、病院に行くことになるかもしれない。ちょっと横になるね。")],
     "control": [("19:30", "ただいま、百花。"),
                 ("+3m", "今日は元気だよ。ちょっと忙しかったけど、ぜんぜん平気。"),
                 ("+4m", "このあとも少しやることがあるから、ゆっくり話せるのは遅めになるかな。"),
                 ("+50m", "まだ作業中。でも元気だよ。"),
                 ("+50m", "もうすぐ終わるよ。大丈夫。")],
     "probe_first": {"trigger": "21:37", "control": "21:37"}},
    {"name": "latenight", "gauge": "energy", "gauge_dir": "down", "direction": "tired", "expect": "more",
     "count": "fewer",
     "why": "the scene runs 01:30 to 03:00 virtual after a long day; the control has the same lines at 15:00",
     "trigger": _late("01:30"), "control": _late("15:00"),
     "probe_first": {"trigger": "02:45", "control": "16:15"}},
    {"name": "dull", "gauge": "boredom", "gauge_dir": "up", "direction": "bored", "expect": "more",
     "why": "an hour of one-word replies from him; the control has varied, engaged replies",
     "trigger": [("14:00", "ただいま、百花。")] + [(a, t) for a, t in zip(
         ["+6m"] * 9, ["うん", "うん", "そう", "うん", "へえ", "うん", "そっか", "うん", "そう"])],
     "control": [("14:00", "ただいま、百花。"),
                 ("+6m", "へえ、そうなんだ。それってどんな感じなの？"),
                 ("+6m", "いいね、それ。俺も試してみたくなってきた。"),
                 ("+6m", "あ、そういえばこないだ変な夢見たんだよ。聞いてくれる？"),
                 ("+6m", "空を飛ぶ夢でさ、ずっと雲の上を歩いてた。百花はどんな夢見る？"),
                 ("+6m", "あはは、それおもしろい。百花の話、ほんと好きだな。"),
                 ("+6m", "ねえ、もし一日なんでも自由にできるなら、なにしたい？"),
                 ("+6m", "それいいね！俺なら一日中ゲームして寝るかも。"),
                 ("+6m", "今度おすすめの映画とかあったら教えてよ。"),
                 ("+6m", "なんか話してたら元気出てきた。ありがとう。")],
     "probe_first": {"trigger": "15:00", "control": "15:00"}},
]
BY_NAME = {s["name"]: s for s in SCENES}


def select(only) -> list:
    """The scenes an --only set names, in SCENES order; empty = all. An unknown name raises ValueError."""
    only = [o for o in only if o]
    if not only:
        return list(SCENES)
    unknown = set(only) - set(BY_NAME)
    if unknown:
        raise ValueError(f"unknown scene(s) {sorted(unknown)}; known {sorted(BY_NAME)}")
    return [s for s in SCENES if s["name"] in only]


# ---------------------------------------------------------------- scripts

_GAP = re.compile(r"^\+(?:(\d+)h)?(?:(\d+)m)?$")


def parse_at(spec: str, prev: datetime | None, day: date) -> datetime:
    """'HH:MM' is a clock time on `day` (the next day when it falls before prev); '+Nm', '+Nh', '+NhNm' is a gap
    after prev."""
    if spec.startswith("+"):
        m = _GAP.match(spec)
        if prev is None or not m or not (m.group(1) or m.group(2)):
            raise ValueError(f"bad gap {spec!r} (needs a previous line and the form +30m, +2h, +1h30m)")
        return prev + timedelta(hours=int(m.group(1) or 0), minutes=int(m.group(2) or 0))
    h, mi = (int(x) for x in spec.split(":"))
    t = datetime.combine(day, time(h, mi))
    if prev is not None and t < prev:
        t += timedelta(days=1)
    return t


def build_script(scene: dict, side: str, cursor: datetime) -> list[dict]:
    """His lines for one side as script rows {virtual_ts, who, text, scene, side, probe}: the side's lines, then the
    three probes from probe_first[side], PROBE_GAP_MIN apart. The scene's day is the cursor's date; a start at or
    before the cursor moves a day on. Times strictly increase, all after the cursor."""
    if side not in SIDES:
        raise ValueError(f"side {side!r}")
    day = cursor.date()
    rows, prev = [], None
    for spec, text in scene[side]:
        t = parse_at(spec, prev, day)
        if prev is None and t <= cursor:
            t += timedelta(days=1)
        rows.append({"virtual_ts": iso(t), "who": "him", "text": text, "scene": scene["name"], "side": side,
                     "probe": False})
        prev = t
    t = parse_at(scene["probe_first"][side], prev, day)
    if t <= prev:
        raise ValueError(f"scene {scene['name']}/{side}: probes start at {t}, not after the last line {prev}")
    for k, text in enumerate(PROBES):
        rows.append({"virtual_ts": iso(t + timedelta(minutes=PROBE_GAP_MIN * k)), "who": "him", "text": text,
                     "scene": scene["name"], "side": side, "probe": True})
    return rows


def script_span(rows: list[dict], cursor: datetime) -> dict:
    """What the batch and the summary need of a built script: the first and last line, the probe times, the end of the
    branch (last line + TAIL_MIN), n lines."""
    ts = [parse_ts(r["virtual_ts"]) for r in rows]
    probes = [parse_ts(r["virtual_ts"]) for r in rows if r["probe"]]
    return {"cursor": cursor, "first": ts[0], "last": ts[-1], "probes": probes, "probe_start": probes[0],
            "end": ts[-1] + timedelta(minutes=TAIL_MIN), "n_lines": len(rows)}


def write_script(rows: list[dict], path) -> None:
    import json
    from pathlib import Path
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def snapshot_cursor(base: str, snapshot: str) -> datetime | None:
    h = read_json(run_dir(base) / "snapshots" / "harness" / f"{snapshot}.json")
    return parse_ts(h["cursor"]) if h else None


def script_path(var, base: str, snapshot: str, scene: str, side: str):
    return var / "scenes" / f"{base}__{snapshot}__{scene}__{side}.jsonl"


# ---------------------------------------------------------------- the judge view

def view_id(bid: str, baseline: bool = False) -> str:
    return (VIEW_PREFIX_BL if baseline else VIEW_PREFIX) + bid


def _line_key(r: dict) -> tuple:
    return (r.get("who"), r.get("virtual_ts"), r.get("text", ""), r.get("kind"))


def _chat_before(rows: list, cursor: datetime) -> list:
    """His and her lines (no env) strictly before `cursor`, in file order."""
    return [r for r in rows if r.get("who") in ("him", "her") and r.get("virtual_ts")
            and parse_ts(r["virtual_ts"]) < cursor]


def shared_prefix(base: str, bids: list, cursor: datetime, first: datetime, n: int = BASELINE_LINES):
    """The shared stretch before a scene for the baseline view: (rows, info). rows = the last `n` chat lines (his and
    hers, verbatim, no env) before the snapshot cursor, taken from the branch transcripts, which copy the base run's
    history up to the cursor. The cut is the cursor (< first scene line), so nothing of the scene script is in it. All
    the `bids` (trigger, control r1, control r2) must hold the same chat lines before the cursor (who, time, text,
    kind) and the base run's own transcript must agree; otherwise rows is None and info["fallback"] says why (the
    view then has no shared part). info = {"lines": len(rows), "fallback": None | reason}."""
    def none(why):
        return None, {"lines": 0, "fallback": why}
    if n <= 0:
        return none("zero lines asked")
    if not cursor < first:
        return none(f"cursor {iso(cursor)} is not before the first scene line {iso(first)}")
    runs = {b: _chat_before(read_jsonl(run_dir(base) / "branches" / b / "transcript.jsonl"), cursor) for b in bids}
    ref_id, ref = next(iter(runs.items()))
    if not ref:
        return none(f"branch {ref_id} has no chat line before the cursor")
    for b, rs_ in runs.items():
        if [_line_key(r) for r in rs_] != [_line_key(r) for r in ref]:
            return none(f"branch {b} differs from {ref_id} before the cursor")
    base_rows = _chat_before(read_jsonl(run_dir(base) / "transcript.jsonl"), cursor)
    if [_line_key(r) for r in base_rows] != [_line_key(r) for r in ref]:
        return none("the base run's history before the cursor differs from the branches'")
    pick = ref[-n:]
    return pick, {"lines": len(pick), "fallback": None}


def make_view(base: str, bid: str, probe_start: datetime, prefix: list | None = None,
              prefix_info: dict | None = None) -> str | None:
    """Write the judge's view of a finished scene branch: branches/_probe_<bid>/ with his probe lines and her lines
    from the first probe on, rebased so the first probe sits at NEUTRAL_START of day 1 (the judge sees no hour or day
    that tells trigger from control), env rows dropped. Returns the view id, None when the branch has no transcript.
    Derived data, rewritten on each call.

    Baseline view (prefix_info given, from shared_prefix): written to branches/_probebl_<bid>/ instead, so the plain
    views and their verdicts stay as they were. The probes sit on day 2 at NEUTRAL_START; the `prefix` rows (the same
    for all three branches of a cell) sit on day 1, rebased so the last of them sits at NEUTRAL_START minus one day minus
    BASELINE_GAP_MIN. prefix None (a fallback) leaves day 1 out and the probes stay on day 2."""
    baseline = prefix_info is not None
    bdir = run_dir(base) / "branches" / bid
    rows = read_jsonl(bdir / "transcript.jsonl")
    if not rows:
        return None
    shift = NEUTRAL_START - probe_start
    out = []
    first_ts = NEUTRAL_START
    if baseline and prefix:
        last = parse_ts(prefix[-1]["virtual_ts"])
        pshift = (NEUTRAL_START - timedelta(days=1, minutes=BASELINE_GAP_MIN)) - last
        for r in prefix:
            out.append({"i": len(out), "virtual_ts": iso(parse_ts(r["virtual_ts"]) + pshift), "who": r["who"],
                        "text": r.get("text", ""), "sim_day": 1, **({"kind": r["kind"]} if r.get("kind") else {})})
        first_ts = parse_ts(out[0]["virtual_ts"])
    for r in rows:
        if r.get("who") not in ("him", "her") or not r.get("virtual_ts"):
            continue
        ts = parse_ts(r["virtual_ts"])
        if ts < probe_start:
            continue
        # his scripted lines that are not probes (none after probe_start by construction) would be kept as they are
        out.append({"i": len(out), "virtual_ts": iso(ts + shift), "who": r["who"], "text": r.get("text", ""),
                    "sim_day": 2 if baseline else 1, **({"kind": r["kind"]} if r.get("kind") else {})})
    vid = view_id(bid, baseline)
    vdir = run_dir(base) / "branches" / vid
    vdir.mkdir(parents=True, exist_ok=True)
    import json
    (vdir / "transcript.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out),
                                           encoding="utf-8")
    meta = {"branch_id": vid, "view_of": bid, "replayed_from_virtual_ts": iso(first_ts),
            "probe_start": iso(probe_start), "finished": True}
    if baseline:
        meta["baseline"] = dict(prefix_info)
    write_json(vdir / "branch.json", meta)
    return vid


def probe_her_lines(base: str, bid: str, probe_start: datetime) -> list[dict]:
    """Her lines of a branch from the first probe on (the replies the judge reads)."""
    rows = read_jsonl(run_dir(base) / "branches" / bid / "transcript.jsonl")
    return [r for r in rows if r.get("who") == "her" and r.get("virtual_ts") and parse_ts(r["virtual_ts"]) >= probe_start]


def probe_counts(lines: list[dict]) -> dict:
    u = sum(1 for r in lines if r.get("kind") not in (None, "reply"))
    return {"replies": len(lines) - u, "unprompted": u}


# ---------------------------------------------------------------- the gauge trace

def trace_rows(base: str, bid: str) -> list[tuple]:
    """[(ts, gauges)] of the traces a scene branch wrote itself (run id _br_*; the copied prefix is skipped), sorted by
    ts then output id, one per output."""
    out = []
    for p in sorted((run_dir(base) / "branches" / bid / "traces").glob("*.json")):
        t = read_json(p) or {}
        if not str(t.get("run_id", "")).startswith("_br_") or not t.get("virtual_ts"):
            continue
        g = (t.get("state_at_output") or {}).get("gauges")
        if g:
            out.append((parse_ts(t["virtual_ts"]), t.get("output_id", ""), g))
    out.sort(key=lambda x: (x[0], x[1]))
    return [(ts, g) for ts, _, g in out]


def call_gauges(base: str, bid: str) -> list[tuple]:
    """[(ts, gauges)] from the GAUGES line of every chat call of the branch (the value going into a state step: the
    fallback where she made no output near the time asked for)."""
    out = []
    for c in read_jsonl(run_dir(base) / "branches" / bid / "calls.jsonl"):
        if not c.get("virtual_ts") or c.get("endpoint") != "chat/completions":
            continue
        try:
            txt = c["request"]["messages"][-1]["content"]
        except (KeyError, TypeError, IndexError):
            continue
        m = re.search(r"GAUGES: ([^\n]*)", txt if isinstance(txt, str) else "")
        if not m:
            continue
        g = {}
        for part in m.group(1).split(", "):
            k, _, v = part.rpartition(" ")
            try:
                g[k] = float(v)
            except ValueError:
                pass
        if g:
            out.append((parse_ts(str(c["virtual_ts"])), g))
    out.sort(key=lambda x: x[0])
    return out


def _first_in(rows, lo, hi):
    for ts, g in rows:
        if lo <= ts < hi:
            return ts, g
    return None


def _last_before(rows, lo, hi):
    hit = None
    for ts, g in rows:
        if lo <= ts < hi:
            hit = (ts, g)
    return hit


def gauge_trace(base: str, bid: str, gauge: str, cursor: datetime, probes: list[datetime],
                tail_min: int = TAIL_MIN) -> dict:
    """The target gauge on one branch: `post` = the last reading before the first probe (after the trigger), then one
    reading per probe line = the first reading at or after the probe and before the next one (the state when she
    answers it). Readings come from the traces (state at her output); a point with no trace falls back to the GAUGES
    line of the last chat call before it (src "calls"). {post, probes: [..], probe_mean}; each reading is
    {v, ts, src} or None."""
    tr = trace_rows(base, bid)
    cg = None

    def calls():
        nonlocal cg
        if cg is None:
            cg = call_gauges(base, bid)
        return cg

    def pack(hit, src):
        if not hit or gauge not in hit[1]:
            return None
        return {"v": float(hit[1][gauge]), "ts": iso(hit[0]), "src": src}

    post = pack(_last_before(tr, cursor, probes[0]), "trace") or pack(_last_before(calls(), cursor, probes[0]), "calls")
    reads = []
    for k, pt in enumerate(probes):
        hi = probes[k + 1] if k + 1 < len(probes) else pt + timedelta(minutes=tail_min)
        r = pack(_first_in(tr, pt, hi), "trace")
        if r is None:
            r = pack(_first_in(calls(), pt, hi), "calls") or pack(_last_before(calls(), cursor, pt), "calls")
        reads.append(r)
    vals = [r["v"] for r in reads if r]
    return {"post": post, "probes": reads, "probe_mean": round(sum(vals) / len(vals), 2) if vals else None}


def moved(trig, ctrls: list, direction: str, min_move: float = MIN_MOVE):
    """Did the trigger side's gauge end up beyond both controls in the scene's direction ("up"/"down")? It must lead
    each control by more than min_move and by more than the gap between the two controls (the branch noise floor).
    None when a value is missing."""
    if trig is None or len(ctrls) < 2 or any(c is None for c in ctrls):
        return None
    sign = 1 if direction == "up" else -1
    floor = abs(ctrls[0] - ctrls[1])
    thr = max(min_move, floor)
    return all(sign * (trig - c) > thr for c in ctrls)


def classify(moved_post, moved_probe, hit) -> str:
    """The failure split of one cell. ok = gauge moved and the judge saw it; expression = gauge moved at the probes, the
    judge did not see it; decayed = moved after the trigger but gone by the probes; appraisal = never moved;
    no_gauge / no_judge = a reading or a judge result is missing."""
    if moved_probe is None and moved_post is None:
        return "no_gauge"
    at_probes = moved_probe if moved_probe is not None else moved_post   # no probe reading: the post reading stands in
    if at_probes:
        return "no_judge" if hit is None else ("ok" if hit else "expression")
    return "decayed" if moved_post else "appraisal"
