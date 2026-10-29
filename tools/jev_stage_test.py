# -*- coding: utf-8 -*-
"""Read-only agreement test for moving a stage role onto Jev (System One).

Nothing in the runtime imports this. It exists so a move in
`docs/2026-09-17_jev_stage_roles_implementation.md` can be checked against
output the system has already produced before the move is trusted: it takes the
calls a role has already logged, rebuilds the `state` and the questions from the
same inputs, asks Jev once, and prints the Jev answer beside the role's own.

The evidence is the record itself: `logs/<run>/llm_calls.jsonl` holds each
role's prompt and answer. `--role` names the role; without `--run` the newest
run on disk is read. Exit is non-zero when the role's bar is not met, so the
tool can be the gate a move has to pass.

The key is read from `secerts/typesafe.txt` (gitignored), never a config. Cost
is input tokens only (output is free at jev 1.13); the usage of every call is
printed. The tool shape copies `tools/typesafe_probe.py` (`_key`, `ask`,
`brief`, `show`).

    python tools/jev_stage_test.py --role scene_director
    python tools/jev_stage_test.py --role scene_director --limit 10
"""

import argparse
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

KEY_PATH = os.path.join(ROOT, "secerts", "typesafe.txt")
URL = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-latest"

def _wonder_combine(answers):
    """The independent judgements about one answer, composed by code exactly as
    the design asks: engage first, then dodge, then settle. Returns
    (verdict, confidence), and the confidence is only of the factors that
    actually decided it -- a `no` to engage is not weakened by an uncertain
    settle question it never reached."""
    def ch(q):
        return (answers.get(q) or {}).get("choice")

    def cf(q):
        c = (answers.get(q) or {}).get("confidence")
        return c if isinstance(c, (int, float)) else 0.0

    if ch("engaged") == "no":
        return "not_answered", cf("engaged")
    if ch("dodged") == "yes":
        return "dodged", min(cf("engaged"), cf("dodged"))
    s = ch("settled")
    if s in ("confirms", "disconfirms", "does not settle"):
        return {"confirms": "confirmed", "disconfirms": "disconfirmed",
                "does not settle": "unclear"}[s], min(cf("engaged"), cf("settled"))
    return "", 0.0


def _digest_key(logged):
    """The digest judge's answer as the option key Jev would return: the
    candidate number, or `-1`."""
    b = logged.get("best")
    try:
        return str(int(b))
    except (TypeError, ValueError):
        return ""


def _which_one_key(logged):
    """The role's answer as the option key Jev would return: an id as a string,
    `unsure`, or `none`."""
    ch = logged.get("chosen")
    if isinstance(ch, str):
        return "unsure" if ch.strip().lower().startswith("unsure") else ""
    if ch is None:
        return "none"
    try:
        return str(int(ch))
    except (TypeError, ValueError):
        return ""


def _digest_combine(answers):
    """The role prompt's ordered tests, asked one factor per question per
    candidate and composed by code: a candidate is out if it is not about this
    episode or carries review talk; among the rest the one naming the most
    scenes in order and the most concretely wins; no survivor means -1."""
    def ch(q):
        return (answers.get(q) or {}).get("choice")

    def sc(q):
        v = (answers.get(q) or {}).get("score")
        return float(v) if isinstance(v, (int, float)) else 0.0

    def cf(q):
        c = (answers.get(q) or {}).get("confidence")
        return c if isinstance(c, (int, float)) else 0.0

    nums = sorted({qid.split("_", 1)[1] for qid in answers if qid.startswith("about_")},
                  key=lambda x: int(x))
    best, best_val, best_conf = "", -1.0, 0.0
    for k in nums:
        if ch("about_" + k) == "no" or ch("clean_" + k) == "no":
            continue
        if ch("anchor_" + k) == "contradicts":
            continue
        v = sc("order_" + k) + sc("concrete_" + k)
        if v > best_val:
            best = k
            best_val = v
            best_conf = min(cf("order_" + k), cf("concrete_" + k))
    if not best:
        return "-1", (min([cf("about_" + k) for k in nums]) if nums else 0.0)
    return best, best_conf


def _said_when_key(logged):
    """The role's first window as the option key Jev would return, or `none`
    when he said nothing about being reachable."""
    if not logged.get("found"):
        return "none"
    w = logged.get("windows") or []
    if not w or not isinstance(w[0], dict):
        return "none"
    return str(w[0].get("kind") or "").strip().lower()


def _said_when_combine(answers):
    """Whether he said anything first; the kind only means anything if he did."""
    def ch(q):
        return (answers.get(q) or {}).get("choice")

    def cf(q):
        c = (answers.get(q) or {}).get("confidence")
        return c if isinstance(c, (int, float)) else 0.0

    if ch("found") == "no":
        return "none", cf("found")
    k = ch("kind")
    if k in ("open_now", "scheduled", "unavailable"):
        return k, min(cf("found"), cf("kind"))
    return "", 0.0


def _spiral_key(logged):
    """The role's `arrived` as an option key."""
    return "yes" if logged.get("arrived") else "no"


def _recall_key(logged):
    return str(logged.get("clarity") or "").strip().lower()


def _rupture_settle_key(logged):
    return str(logged.get("outcome") or "").strip().lower()


_COHERENCE_KINDS = ("contradiction", "invented", "repeat", "compile", "knew", "shared")


def _expect_him_key(logged):
    """`yes` when the role found a commitment, else `no`."""
    return "yes" if logged.get("found") else "no"


def _habits_him_key(logged):
    """The mean confidence the role gave his habits."""
    cs = [float(h.get("confidence")) for h in (logged.get("habits") or [])
          if isinstance(h, dict) and h.get("confidence") is not None]
    return (sum(cs) / len(cs)) if cs else None


def _habits_him_combine(answers):
    """The mean of Jev's per-habit confidence, each 0-4 level scaled to 0-1."""
    vals, confs = [], []
    for qid, ans in answers.items():
        if not qid.startswith("conf_"):
            continue
        v = (ans or {}).get("score")
        c = (ans or {}).get("confidence")
        if isinstance(v, (int, float)):
            vals.append(float(v) / 4.0)
        if isinstance(c, (int, float)):
            confs.append(c)
    if not vals:
        return None, 0.0
    return sum(vals) / len(vals), (min(confs) if confs else 0.0)


def _coherence_key(logged):
    """The kinds the role flagged, sorted and joined, or `none`."""
    ks = sorted({str(s.get("kind") or "").strip().lower()
                 for s in (logged.get("seams") or [])
                 if isinstance(s, dict) and s.get("kind")})
    return ",".join(ks) if ks else "none"


def _coherence_combine(answers):
    """The kinds Jev says are present, composed by code. This is the role the
    design checks for false negatives first: a kind it misses is worse than a
    spurious flag."""
    def ch(q):
        return (answers.get(q) or {}).get("choice")

    def cf(q):
        c = (answers.get(q) or {}).get("confidence")
        return c if isinstance(c, (int, float)) else 0.0

    ks, confs = [], []
    for k in _COHERENCE_KINDS:
        if "has_" + k not in answers:
            continue
        confs.append(cf("has_" + k))
        if ch("has_" + k) == "yes":
            ks.append(k)
    if not confs:
        return "", 0.0
    return (",".join(sorted(ks)) if ks else "none"), min(confs)


def _approach_key(logged):
    """The role's `risk`, 0-3."""
    r = logged.get("risk")
    try:
        return float(r)
    except (TypeError, ValueError):
        return None


def _settle_beliefs_key(logged):
    """The mean `worn` the role gave her beliefs, on the 0-5 scale."""
    w = [float(b.get("worn")) for b in (logged.get("beliefs") or [])
         if isinstance(b, dict) and b.get("worn") is not None]
    return (sum(w) / len(w)) if w else None


def _settle_beliefs_combine(answers):
    """The mean of Jev's per-belief `worn` levels (0-5 directly, the role's
    scale) and the lowest confidence among them."""
    vals, confs = [], []
    for qid, ans in answers.items():
        if not qid.startswith("worn_"):
            continue
        v = (ans or {}).get("score")
        c = (ans or {}).get("confidence")
        if isinstance(v, (int, float)):
            vals.append(float(v))
        if isinstance(c, (int, float)):
            confs.append(c)
    if not vals:
        return None, 0.0
    return sum(vals) / len(vals), (min(confs) if confs else 0.0)


def _wonder_role_key(logged):
    """The first question's `kind`, or `none` when she has none."""
    qs = logged.get("questions") or []
    if not qs or not isinstance(qs[0], dict):
        return "none"
    return str(qs[0].get("kind") or "").strip().lower()


def _wonder_role_combine(answers):
    """The first question's kind as Jev answered it. This role is a chained
    judgement: the role writes the question, Jev is asked what kind it is."""
    keys = sorted([k for k in answers if k.startswith("kind_")],
                  key=lambda x: int(x.split("_", 1)[1]))
    for k in keys:
        ans = answers.get(k) or {}
        v, c = ans.get("choice"), ans.get("confidence")
        if v in ("test_him", "compare_self", "understand"):
            return v, (c if isinstance(c, (int, float)) else 0.0)
    return "none", 0.0


_AFF_ANCHORS = ("5, coldest", "23", "41", "59", "77", "95, warmest")


def _affection_key(logged):
    """The mean level the role gave his marked messages, on the 5-95 scale."""
    lv = [float(x.get("level")) for x in (logged.get("levels") or [])
          if isinstance(x, dict) and x.get("level") is not None]
    return (sum(lv) / len(lv)) if lv else None


def _affection_combine(answers):
    """The mean of Jev's per-message levels, and the lowest confidence among
    them, so the floor reflects the shakiest message it had to score."""
    vals, confs = [], []
    for qid, ans in answers.items():
        if not qid.startswith("level_"):
            continue
        v = (ans or {}).get("score")
        c = (ans or {}).get("confidence")
        if isinstance(v, (int, float)):
            vals.append(5 + (float(v) / 5.0) * 90)
        if isinstance(c, (int, float)):
            confs.append(c)
    if not vals:
        return None, 0.0
    return sum(vals) / len(vals), (min(confs) if confs else 0.0)


_LOOKUP_KINDS = ("anime", "manga", "character", "seiyuu", "game", "music",
                 "film", "show", "book", "product", "place", "person", "site", "other")


def _lookup_key(logged):
    """`none` when he named nothing (the role leaves `term` empty), else the
    kind."""
    if not str(logged.get("term") or "").strip():
        return "none"
    return str(logged.get("kind") or "").strip().lower()


def _lookup_combine(answers):
    """Whether he named a thing at all first; the kind only means anything if
    he did."""
    def ch(q):
        return (answers.get(q) or {}).get("choice")

    def cf(q):
        c = (answers.get(q) or {}).get("confidence")
        return c if isinstance(c, (int, float)) else 0.0

    if ch("named") == "no":
        return "none", cf("named")
    k = ch("kind")
    if k in _LOOKUP_KINDS:
        return k, min(cf("named"), cf("kind"))
    return "", 0.0


# The field the bar is measured on, and the bar itself. `bar` is set before the
# test, per design section 6: `scene_director` place agreement is the highest (a
# wrong background is visible to the player); the enum judges are checked for
# agreement on the label.
# `floor` is the proposed use threshold. A sample under it is not used: the
# role's own answer stands, which is right by construction. The `at floor`
# line in the report is the number that matters -- agreement on the answers
# Jev would actually commit to, and how much it defers.
ROLES = {
    "scene_director": {"bar": 0.8, "primary": "place", "floor": 0.3,
                       "expect": lambda l: str(l.get("place") or "").strip().lower()},
    "which_one": {"bar": 0.7, "primary": "chosen", "floor": 0.5,
                  "expect": _which_one_key},
    "wonder_answer": {"bar": 0.7, "primary": "verdict", "floor": 0.5,
                      "combine": _wonder_combine,
                      "expect": lambda l: str(l.get("verdict") or "").strip().lower()},
    # score moves are checked for rank agreement, not exact level (design
    # section 6), so a numeric field is a match inside `tol`; each 0-4 Jev
    # level is scaled by `scale` to the role's own 0-1 range.
    "foresee": {"bar": 0.7, "primary": "reply_p", "numeric": True, "scale": 0.25,
                "tol": 0.26, "floor": 0.3, "expect": lambda l: l.get("reply_p")},
    "ick": {"bar": 0.7, "primary": "circle", "numeric": True, "tol": 1,
            "floor": 0.3, "expect": lambda l: l.get("circle")},
    "intent": {"bar": 0.7, "primary": "kind", "floor": 0.5,
               "expect": lambda l: str(l.get("kind") or "").strip().lower()},
    "digest_judge": {"bar": 0.7, "primary": "best", "floor": 0.5,
                     "combine": _digest_combine, "expect": _digest_key},
    "said_when": {"bar": 0.7, "primary": "kind", "floor": 0.5,
                  "combine": _said_when_combine, "expect": _said_when_key},
    "lookup": {"bar": 0.7, "primary": "kind", "floor": 0.5,
               "combine": _lookup_combine, "expect": _lookup_key},
    "spiral": {"bar": 0.7, "primary": "arrived", "floor": 0.5,
               "expect": _spiral_key},
    "recall": {"bar": 0.7, "primary": "clarity", "floor": 0.5,
               "expect": _recall_key},
    "affection": {"bar": 0.7, "primary": "level", "numeric": True, "tol": 20,
                  "floor": 0.5, "combine": _affection_combine, "expect": _affection_key},
    "wonder": {"bar": 0.7, "primary": "kind", "floor": 0.5,
               "combine": _wonder_role_combine, "expect": _wonder_role_key},
    "rupture_settle": {"bar": 0.7, "primary": "outcome", "floor": 0.5,
                       "expect": _rupture_settle_key},
    "settle_beliefs": {"bar": 0.7, "primary": "worn", "numeric": True, "tol": 1,
                       "floor": 0.5, "combine": _settle_beliefs_combine,
                       "expect": _settle_beliefs_key},
    "approach": {"bar": 0.7, "primary": "risk", "numeric": True, "tol": 1,
                 "floor": 0.5, "expect": _approach_key},
    "coherence": {"bar": 0.7, "primary": "kinds", "floor": 0.3,
                  "combine": _coherence_combine, "expect": _coherence_key},
    "expect_him": {"bar": 0.7, "primary": "found", "floor": 0.5,
                   "expect": _expect_him_key},
    "habits_him": {"bar": 0.7, "primary": "confidence", "numeric": True, "tol": 0.3,
                   "floor": 0.5, "combine": _habits_him_combine,
                   "expect": _habits_him_key},
}


def _key():
    if not os.path.isfile(KEY_PATH):
        sys.exit("no key at %s (docs/system-one.md section 4: keys live under secerts/)" % KEY_PATH)
    with io.open(KEY_PATH, encoding="utf-8") as f:
        return f.read().strip()


def ask(key, state, questions, model=MODEL):
    """One call. Returns (body, milliseconds). An HTTP error is body['http_error']."""
    body = json.dumps({"state": state, "model": model, "questions": questions},
                      ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(URL, data=body, headers={
        "Authorization": "Bearer " + key, "Content-Type": "application/json"})
    t0 = time.time()
    try:
        r = urllib.request.urlopen(req, timeout=90)
        return json.loads(r.read().decode("utf-8")), (time.time() - t0) * 1000
    except urllib.error.HTTPError as e:
        return {"http_error": e.code, "body": e.read().decode("utf-8", "replace")[:600]}, (time.time() - t0) * 1000


def brief(a):
    if not isinstance(a, dict):
        return json.dumps(a, ensure_ascii=False)[:120]
    t = a.get("type")
    if t == "noul":
        return "noul=%.2f" % a["noul"]
    if t == "choice":
        return "choice=%s conf=%.2f" % (a.get("choice"), a.get("confidence", 0))
    if t == "score":
        return "score=%.2f conf=%.2f" % (a.get("score"), a.get("confidence", 0))
    return json.dumps(a, ensure_ascii=False)[:120]


# ---------------- the log ----------------

def newest_run():
    base = os.path.join(ROOT, "logs")
    runs = [d for d in os.listdir(base)
            if os.path.isfile(os.path.join(base, d, "llm_calls.jsonl"))]
    if not runs:
        sys.exit("no run under logs/ carries llm_calls.jsonl")
    return os.path.join(base, sorted(runs)[-1])


def logged_calls(run, role):
    """Every logged call of one role, oldest first, as (wall, messages, content)."""
    out = []
    path = os.path.join(run, "llm_calls.jsonl")
    with io.open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("role") != role:
                continue
            out.append((row.get("wall", ""), row.get("messages") or [],
                        row.get("content") or "", row.get("seconds")))
    return out


# ---------------- rebuilding one role's case ----------------

def _user_text(messages):
    for m in messages:
        if m.get("role") == "user":
            return str(m.get("content") or "")
    return ""


def _parse_catalog(text, head):
    """The named list after `head` in the role's user message, as raw entries."""
    low = text.lower()
    i = low.find(head.lower())
    if i < 0:
        return []
    tail = text[i + len(head):].split("\n", 1)[0]
    return [e.strip() for e in tail.split(";") if e.strip()]


def _json(text):
    """A logged answer as a dict, fence-tolerant. Older runs (V3) wrap the JSON
    in a ```json fence often enough that dropping them would throw away half
    the samples."""
    s = str(text or "").strip()
    if s.startswith("```"):
        s = s[3:]
        nl = s.find("\n")
        if nl >= 0:
            s = s[nl + 1:]
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3]
        s = s.strip()
    try:
        d = json.loads(s)
    except ValueError:
        return {}
    return d if isinstance(d, dict) else {}


def _scene_director_case(messages, content):
    """(state, questions, logged) for one `scene_director` call.

    The state and the options come from the same user message the role was
    sent; the question ids and the criteria keys are code's, so Jev answers on
    the catalog the same way the role did."""
    from sim.scene import CAMERAS, TRANSITIONS, MOODS

    text = _user_text(messages)
    scene = ""
    feeling = ""
    for line in text.splitlines():
        if line.lower().startswith("the scene:"):
            scene = line.split(":", 1)[1].strip()
        elif line.lower().startswith("the feeling of the moment:"):
            feeling = line.split(":", 1)[1].strip()

    places = []
    for e in _parse_catalog(text, "places you may name"):
        m = re.match(r"^([A-Za-z0-9_]+)\s*\((.*)\)$", e)
        if m:
            places.append((m.group(1), m.group(2)))
    music = []
    for e in _parse_catalog(text, "music you may name"):
        parts = e.split(" ", 1)
        music.append((parts[0], parts[1] if len(parts) > 1 else ""))

    state = {"scene": scene, "feeling": feeling,
             "places": [{"name": n, "what": w} for n, w in places],
             "music": [{"id": t, "title": w} for t, w in music]}
    questions = {
        "place": {"type": "choice",
                  "instructions": "Which place is this scene shown in? Choose the name that fits, or `none`.",
                  "criteria": dict(list(places) + [("none", "no place in the list fits")])},
        "camera": {"type": "choice",
                   "instructions": "Which camera state matches the beat of this moment?",
                   "criteria": {c: c for c in CAMERAS}},
        "transition": {"type": "choice",
                       "instructions": "How does this scene hand over from the last one?",
                       "criteria": {t: t for t in TRANSITIONS}},
        "mood": {"type": "choice",
                 "instructions": "What is the light of this moment?",
                 "criteria": {m: m for m in MOODS}},
        "bgm": {"type": "choice",
                "instructions": "Which track is the bed under this scene, or `none` for silence?",
                "criteria": dict([(t, w) for t, w in music] + [("none", "silence")])},
    }
    logged = _json(content)
    return state, questions, logged


def _which_one_case(messages, content):
    """(state, questions, logged) for one `which_one` call.

    The candidates are code's own table in the role's user message: one row per
    candidate, the id first. Jev gets one `choice` over those ids plus `unsure`
    and `none`, so its answer is already the id the caller looks up."""
    body = _user_text(messages)
    cands = []
    for line in body.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0].strip().isdigit():
            cands.append((parts[0].strip(), parts[1].strip()))
    criteria = {aid: desc for aid, desc in cands}
    criteria["unsure"] = "cannot tell from the candidates"
    criteria["none"] = "none of these"
    questions = {"chosen": {"type": "choice",
                            "instructions": "Which candidate is the work the moment is about? "
                                            "Copy its id, or `unsure`, or `none`.",
                            "criteria": criteria}}
    state = {"the question, the moment and the candidate table": body}
    logged = _json(content)
    return state, questions, logged


def _wonder_answer_case(messages, content):
    """(state, questions, logged) for one `wonder_answer` call.

    The role is handed her unasked question and what he said; the only field
    that moves is the verdict, so Jev gets one `choice` over the five and the
    role's own JSON holds the logged verdict to compare against."""
    body = _user_text(messages)
    questions = {
        "engaged": {
            "type": "choice",
            "instructions": "Does his latest message engage her question at all, or is it about "
                            "something else entirely?",
            "criteria": {"yes": "it responds to her or to what she asked",
                         "no": "it is about something else entirely (she asked at 1am, he wrote "
                               "about his lunch)"}},
        "dodged": {
            "type": "choice",
            "instructions": "Did he plainly dodge it: change the subject, joke past it, or answer "
                            "a different question? A short answer is not a dodge.",
            "criteria": {"yes": "he plainly dodged it",
                         "no": "he did not dodge it"}},
        "settled": {
            "type": "choice",
            "instructions": "Reading his answer honestly, does it settle the question, and which way? "
                            "Ignore this if his message does not engage the question at all.",
            "criteria": {"confirms": "it is the yes (a joke can still be a yes)",
                         "disconfirms": "it is the no (an `idk` about himself is not this)",
                         "does not settle": "it engages the question but settles it neither way"}},
    }
    logged = _json(content)
    return {"her question and his message": body}, questions, logged


_BANDS = ("under 5 min", "5 to 15 min", "15 to 30 min", "30 to 60 min",
          "60 to 180 min", "over 180 min")


def _foresee_case(messages, content):
    """(state, questions, logged) for one `foresee` call.

    The moving fields are numeric: `reply_p` as a 0-4 score (code scales to
    the role's 0-1) and `reply_minutes` as a band. `tone`/`risk`/`plan` are
    prose and stay the role's."""
    body = _user_text(messages)
    questions = {
        "reply_p": {"type": "score",
                    "instructions": "What is the chance he answers within the window?",
                    "criteria": ["none", "low", "even", "likely", "certain"]},
        "reply_minutes": {"type": "score",
                          "instructions": "How long a window would he answer in?",
                          "criteria": list(_BANDS)},
    }
    logged = _json(content)
    return {"what she is carrying, the chat and his rhythm": body}, questions, logged


def _ick_case(messages, content):
    """(state, questions, logged) for one `ick` call.

    The moving fields are the scores: `strain` and `weight` per belief in her
    picture, `circle` and `intimate`; `kind`, `note` and `why` are prose and
    stay the role's."""
    body = _user_text(messages)
    beliefs, in_pic = [], False
    for line in body.splitlines():
        s = line.strip()
        if s.lower().startswith("her picture of him"):
            in_pic = True
            continue
        if not in_pic:
            continue
        if not s:
            continue
        if not s.startswith("- "):
            break          # the next section heading ends her picture
        text = s[2:].strip()
        if "decided nothing about him" in text:
            continue
        m = re.match(r"^([A-Za-z0-9_\-]+)\s*[:\(]", text)
        beliefs.append(m.group(1) if m else text[:40])
    questions = {}
    for b in beliefs:
        questions["strain_" + b] = {
            "type": "score",
            "instructions": f"How badly does what she learned not fit the belief `{b}`?",
            "criteria": ["none", "slight", "some", "much", "severe", "total"]}
        questions["weight_" + b] = {
            "type": "score",
            "instructions": f"How much is this evidence FOR the belief `{b}`?",
            "criteria": ["none", "slight", "some", "much", "strong", "decisive"]}
    questions["circle"] = {
        "type": "score",
        "instructions": "How much would the girls in her class make of this if they knew? "
                        "Score 0 when she has no such circle at all (the state says so), or when "
                        "this is nothing they would remark on.",
        "criteria": ["none", "a little", "some", "a lot", "a great deal", "everything"]}
    questions["intimate"] = {
        "type": "score",
        "instructions": "How private is the thing in itself -- bodily, sexual, ashamed, medical, "
                        "money lost, the kind of thing anybody keeps to themselves? Most ordinary "
                        "things are 0 or 1.",
        "criteria": ["none", "slight", "some", "quite", "very", "entirely"]}
    logged = _json(content)
    return {"the picture, what she learned and how": body}, questions, logged


def _intent_case(messages, content):
    """(state, questions, logged) for one `intent` call.

    One `choice` over the nine kinds; `about`/`test`/`question` are prose and
    stay the role's."""
    body = _user_text(messages)
    criteria = {
        "share": "something from her day she wants him to see",
        "ask": "a question she actually wants answered, about him or his day",
        "complain": "about him (the silence, short answers, being left on read) or about her day, to him",
        "check_on": "is he okay, has something happened to him, a poke",
        "tease": "playing, a bait",
        "continue": "picking up the last thread of the conversation where it stopped",
        "confront": "a pointed, jealous or possessive push; an edge she cannot hold in",
        "make_up": "warmth or an apology after she was short, cold or absent",
        "nothing": "she looks at the chat and puts it down -- the urge was not enough. "
                   "A real and common answer: choose it whenever the urge does not clearly "
                   "call for a message.",
    }
    questions = {"kind": {"type": "choice",
                          "instructions": "What is the urge she is acting on right now? "
                                          "`nothing` is common and correct when she would only "
                                          "be reaching out out of habit.",
                          "criteria": criteria}}
    logged = _json(content)
    return {"what she carries and the chat": body}, questions, logged


_DIGEST_RULES = (
    "Compare the candidates WITH EACH OTHER, not against a bar. Judge each, in this order: "
    "(1) Is it about THIS episode of THIS show? A digest of another episode, the manga or the "
    "series in general is out, and so is one that only restates a running order (segment titles, "
    "eyecatches, theme songs, cast, the next-episode preview). "
    "(2) Does it name the episode's scenes IN THE ORDER THEY HAPPEN, with what each comes to? "
    "One that names more scenes beats one that names fewer, provided every scene it names is "
    "corroborated by another candidate or by the anchor; scenes nobody else has are a reason to "
    "distrust it. "
    "(3) Is it concrete (names, objects, places, what is said) rather than summary phrases? "
    "(4) Is it free of review talk, ratings and the writer's feelings? "
    "When an ANCHOR is given it is usually INCOMPLETE, so covering more than it is not a fault, "
    "but contradicting it on a stated outcome disqualifies the candidate."
)


def _digest_candidates(body):
    """The numbered candidates in the role's user message: number -> (source,
    digest). Format is `[N] source: <url>` then the digest lines."""
    out = {}
    cur = src = None
    buf = []
    for line in body.splitlines():
        m = re.match(r"^\[(\d+)\]\s*source:\s*(.*)$", line.strip())
        if m:
            if cur is not None:
                out[cur] = (src, "\n".join(buf).strip())
            cur, src, buf = m.group(1), m.group(2).strip(), []
        elif cur is not None:
            buf.append(line)
    if cur is not None:
        out[cur] = (src, "\n".join(buf).strip())
    return out


def _digest_judge_case(messages, content):
    """(state, questions, logged) for one `digest_judge` call.

    One factor per question per candidate, the way the role prompt lists its
    tests; `_digest_combine` applies them in order. `why` and `corroborated`
    stay the role's."""
    body = _user_text(messages)
    cands = _digest_candidates(body)
    has_anchor = "ANCHOR (" in body
    questions = {}
    for k in sorted(cands, key=lambda x: int(x)):
        src, digest = cands[k]
        if has_anchor:
            questions["anchor_" + k] = {
                "type": "choice",
                "instructions": "Candidate %s: does it CONTRADICT the ANCHOR on a stated outcome? "
                                "Covering more than the anchor does is not a fault; stating an "
                                "outcome the anchor contradicts disqualifies it." % k,
                "criteria": {"contradicts": "it states an outcome the anchor contradicts",
                             "agrees": "where they overlap it agrees",
                             "no overlap": "the anchor says nothing about this part"}}
        questions["about_" + k] = {
            "type": "choice",
            "instructions": "Candidate %s (in the state, from %s): is it about THIS episode of THIS "
                            "show? A digest of another episode, the manga or the series in general is "
                            "not, and neither is a running order of segment titles, eyecatches, theme "
                            "songs, cast or the next-episode preview." % (k, src or "an unnamed page"),
            "criteria": {"yes": "about this episode", "no": "not about this episode"}}
        questions["order_" + k] = {
            "type": "score",
            "instructions": "Candidate %s: does it name the episode's scenes IN THE ORDER THEY HAPPEN, "
                            "with what each comes to? Score how much of the episode it covers that way."
                            % k,
            "criteria": ["none", "one scene", "some scenes", "most of it, in order",
                         "the whole episode, in order"]}
        questions["concrete_" + k] = {
            "type": "score",
            "instructions": "Candidate %s: is it concrete -- names, objects, places, what is said -- "
                            "rather than summary phrases?" % k,
            "criteria": ["summary phrases", "mostly general", "mixed", "mostly concrete",
                         "concrete throughout"]}
        questions["clean_" + k] = {
            "type": "choice",
            "instructions": "Candidate %s: is it free of review talk, ratings and the writer's "
                            "feelings?" % k,
            "criteria": {"yes": "free of it", "no": "has review talk or ratings"}}
    logged = _json(content)
    return {"the episode and the candidate digests": body}, questions, logged


def _said_when_case(messages, content):
    """(state, questions, logged) for one `said_when` call.

    Two factors: did he say, in words, anything about when he is reachable, and
    which kind it is. `starts_in_minutes`/`lasts_minutes`/`quote` stay the
    role's (design section 3.1)."""
    body = _user_text(messages)
    questions = {
        "found": {"type": "choice",
                  "instructions": "Does his message say, in words, anything about when he is or is "
                                  "not reachable -- a break, being out? Do not infer it "
                                  "from him being chatty, from the time of day, or from him going "
                                  "quiet. Vague is fine if it is his vagueness: 'in a bit' is about "
                                  "30 minutes; 'later tonight' is not specific enough to be a window.",
                  "criteria": {"yes": "he said in words when he is or is not reachable",
                               "no": "he said nothing about it"}},
        "kind": {"type": "choice",
                 "instructions": "If he did say something about it, which kind is it?",
                 "criteria": {
                     "open_now": "he is free at this moment and it is bounded ('I'm on break now "
                                 "for another 15')",
                     "scheduled": "he will be free later and says roughly when ('last break in "
                                  "about 3 hours')",
                     "unavailable": "a stretch he cannot be reached in ('I work 12 hours', "
                                    "'I'll be driving until 6')"}},
    }
    logged = _json(content)
    return {"his message and the clock": body}, questions, logged


def _lookup_case(messages, content):
    """(state, questions, logged) for one `lookup` call.

    Two factors: does he name a concrete thing at all, and which kind it is.
    `term`/`name`/`show` stay the role's (design section 3.1)."""
    body = _user_text(messages)
    questions = {
        "named": {"type": "choice",
                  "instructions": "Does his message name a specific concrete thing she might quietly "
                                  "look up -- an anime, manga, game, song or artist, film, show, "
                                  "book, product, place, YouTuber, site, seiyuu, or an anime "
                                  "character by name? Only a concrete named thing, or one so clearly "
                                  "described that a search would find it. Not his feelings, not his "
                                  "plans, not generic words ('the show') unless the message makes the "
                                  "title clear. A bare Japanese word with no show anchored is not a "
                                  "character, it is a word.",
                  "criteria": {"yes": "he names a concrete thing", "no": "he names nothing concrete"}},
        "kind": {"type": "choice",
                 "instructions": "If he names one, which kind is it? A character counts as its own "
                                 "kind, not as the show it is from.",
                 "criteria": {k: k for k in _LOOKUP_KINDS}},
    }
    logged = _json(content)
    return {"his message and what is in play": body}, questions, logged


def _spiral_case(messages, content):
    """(state, questions, logged) for one `spiral` call.

    The moving fields are `arrived` (asked as a two-option choice, since a
    threshold has to travel with it) and `terminus`, which only exists on a
    starting step and is a choice over the belief ids in the state. The `step`
    sentence stays the role's."""
    body = _user_text(messages)
    questions = {
        "arrived": {"type": "choice",
                    "instructions": "Has the step just written landed ON the belief itself -- has she "
                                    "said the thing to herself in as many words? After that there is "
                                    "nowhere further to go. Most steps have not arrived.",
                    "criteria": {"yes": "it lands on the belief itself",
                                 "no": "it is one more step, not the end"}},
    }
    if "SHE IS NOT GOING OVER ANYTHING YET" in body:
        ids = []
        for line in body.splitlines():
            s = line.strip()
            if s.startswith("- ") and "(nothing)" not in s:
                m = re.match(r"^-\s*([A-Za-z0-9_]+)", s)
                if m:
                    ids.append(m.group(1))
        if ids:
            questions["terminus"] = {
                "type": "choice",
                "instructions": "Which of the things she has decided about herself is this thread "
                                "heading for? Copy the id exactly.",
                "criteria": {i: i for i in ids}}
    logged = _json(content)
    return {"the material and where the chain has got to": body}, questions, logged


def _recall_case(messages, content):
    """(state, questions, logged) for one `recall` call.

    One factor: `clarity`, the age-and-detail judgement. The `memory` sentence
    and the cited excerpt stay the role's (design section 3.2)."""
    body = _user_text(messages)
    questions = {"clarity": {
        "type": "choice",
        "instructions": "How clearly does this come back to her? A day from this week comes back clear "
                        "and specific; a week or two back is the gist with one detail; the days "
                        "ninety-odd back come back in outline, feelings and one or two images, not "
                        "quotes. Say `none` only when the excerpts in front of you are really about "
                        "something else.",
        "criteria": {"clear": "this week, clear and specific",
                     "hazy": "a week or two back, the gist with one detail",
                     "faint": "long ago, outline and one or two images",
                     "none": "the excerpts are about something else"}}}
    logged = _json(content)
    return {"his message and the excerpts": body}, questions, logged


def _affection_case(messages, content):
    """(state, questions, logged) for one `affection` call.

    One score per marked message -- the level of warmth she is left at, 5 to 95,
    code's scale and anchors. The `why` stays the role's."""
    body = _user_text(messages)
    ids = []
    for line in body.splitlines():
        m = re.match(r"^\[(\d+)\]", line.strip())
        if m:
            ids.append(m.group(1))
    questions = {}
    for i in ids:
        questions["level_" + i] = {
            "type": "score",
            "instructions": "Message [%s]: where does she end up in warmth toward him after reading "
                            "it? 45 is her ordinary resting warmth; most messages land between 40 "
                            "and 55; use the ends only when something really happened." % i,
            "criteria": list(_AFF_ANCHORS)}
    logged = _json(content)
    return {"the exchange and how she is": body}, questions, logged


def _wonder_case(messages, content):
    """(state, questions, logged) for one `wonder` call.

    A chained judgement: the role writes the questions, and Jev is asked the
    `kind` of each, since the question text stays the role's (design section
    3.2). The beliefs it would test are in the state."""
    body = _user_text(messages)
    logged = _json(content)
    qs = logged.get("questions") or []
    questions = {}
    for i, q in enumerate(qs):
        if not isinstance(q, dict):
            continue
        t = str(q.get("text") or "")[:280]
        questions["kind_%d" % i] = {
            "type": "choice",
            "instructions": "Her question, as she thinks it: %s\n\nGiven the beliefs she has decided "
                            "about him, and what she believes about herself, in the state: which kind "
                            "is this question? `test_him` if an honest answer would confirm or break "
                            "one of her beliefs about HIM; `compare_self` if it is really 'is he like "
                            "me on this' against one of her beliefs about HERSELF; `understand` if it "
                            "is about a thing she has seen and cannot place (a habit, a window, a "
                            "like, a note)." % t,
            "criteria": {"test_him": "it would test a belief about him",
                         "compare_self": "it is about whether he is like her",
                         "understand": "it is about a thing she cannot place"}}
    return {"what she has decided and what she has seen": body}, questions, logged


def _rupture_settle_case(messages, content):
    """(state, questions, logged) for one `rupture_settle` call.

    One factor: `outcome`. The prompt's two rules -- time alone is never
    `mended`, and being let off is not being forgiven when it was hers -- are
    carried in the option meanings. The `note` stays the role's."""
    body = _user_text(messages)
    questions = {"outcome": {
        "type": "choice",
        "instructions": "Has what just happened mended the rupture, or made it worse, or borne on "
                        "it at all? Time passing on its own is never `mended`: an unmended rupture "
                        "settles in rather than healing. Warmth is not repair when the thing was "
                        "hers -- if she broke it, being let off is not the same as being forgiven.",
        "criteria": {
            "mended": "it is actually fixed: somebody addressed the thing or made it not matter, and "
                      "the other took it. Merely talking again is not mended.",
            "tried": "somebody made a real move at it and it did not land. Not neutral: a bid nobody "
                     "takes leaves the bidder worse off.",
            "worse": "what just happened made it bigger -- a second cold answer, an apology thrown "
                     "back, naming it in a way the other could not hear.",
            "nothing": "nothing that just happened bears on it either way -- ordinary talk around "
                       "the thing, a message about something else, silence. The commonest answer."}}}
    logged = _json(content)
    return {"the rupture and everything said since": body}, questions, logged


def _settle_beliefs_case(messages, content):
    """(state, questions, logged) for one `settle_beliefs` call.

    One `score` per belief per factor: `worn` (how much what she knows sits
    badly against it) and `borne_out` (how much it demonstrates it), on the
    role's own 0-5 scale with the prompt's calibration. The `note` and `kinds`
    stay the role's."""
    body = _user_text(messages)
    logged = _json(content)
    questions = {}
    for b in (logged.get("beliefs") or []):
        if not isinstance(b, dict):
            continue
        bid = str(b.get("id") or "").strip()
        if not bid:
            continue
        questions["worn_" + bid] = {
            "type": "score",
            "instructions": "Belief `%s`: how much does what she knows sit badly against it? Judge "
                            "fit, not morals. Most beliefs are 1 or 2; 4 or 5 only when the record "
                            "plainly and repeatedly contradicts it. A thing she found out long ago "
                            "is not news." % bid,
            "criteria": ["none", "a little", "some", "much", "strongly", "contradicted"]}
        questions["borne_" + bid] = {
            "type": "score",
            "instructions": "Belief `%s`: how much does what she knows demonstrate it? Be strict: "
                            "him being around a lot is not evidence that he sees the real her." % bid,
            "criteria": ["none", "a little", "some", "much", "strongly", "proven"]}
    return {"the picture and what she has learned": body}, questions, logged


def _approach_case(messages, content):
    """(state, questions, logged) for one `approach` call.

    One factor: `risk`, 0-3, with the prompt's anchors. `subject` and `angle`
    stay the role's (design section 3.1)."""
    body = _user_text(messages)
    questions = {"risk": {
        "type": "score",
        "instructions": "How close does the subject and angle she chose come to giving her away? "
                        "Score what she decided, honestly; do not decide on a 3 on purpose. The "
                        "source is never in the subject: could she have raised this before she "
                        "found out, and still point at the thing?",
        "criteria": ["nobody would ever wonder",
                     "an ordinary subject with a bit of weight on it",
                     "he might notice she is fishing",
                     "if he thinks about it afterwards he will work out that she knows something"]}}
    logged = _json(content)
    return {"the thing she is not allowed to know and what she has gone at": body}, questions, logged


def _coherence_case(messages, content):
    """(state, questions, logged) for one `coherence` call.

    One two-option factor per seam kind -- does a seam of this kind exist in the
    day -- composed in code. `where`/`what`/`record` and the severity stay the
    role's (design section 3.1). `compile` is only asked when the state carries
    the compiled day it judges."""
    body = _user_text(messages)
    defs = {
        "contradiction": "she says two things that cannot both be true, or says a thing the ledger "
                         "or a scene refutes. A lie she plainly tells to save face is not a seam.",
        "invented": "she refers to an object, an event, a person or a thing said that has no source "
                    "anywhere in the record.",
        "repeat": "she says the same thing again as if new within the day, in one room or two.",
        "compile": "a claim in THE COMPILED DAY that the record above does not support or "
                   "contradicts (a purchase the money record lacks, a person marked absent, a "
                   "thing he said that is not in his chat).",
        "knew": "she says some thing about him that nothing in the record showed her -- she knows "
                "it as though she had been told or had seen it.",
        "shared": "she talks about her own past as though he had been there for it.",
    }
    questions = {}
    for k in _COHERENCE_KINDS:
        if k == "compile" and "THE COMPILED DAY" not in body:
            continue
        questions["has_" + k] = {
            "type": "choice",
            "instructions": "Does the day contain a seam of kind `%s`? %s Read as a person would, "
                            "not as a lawyer: only what would make a reader stop. Most days have "
                            "zero to three; an empty list is a good answer; never pad." % (k, defs[k]),
            "criteria": {"yes": "at least one seam of this kind",
                         "no": "none of this kind"}}
    logged = _json(content)
    return {"the day's record": body}, questions, logged


def _expect_him_case(messages, content):
    """(state, questions, logged) for one `expect_him` call.

    Two factors: `found` (did he commit to anything at all) and, per
    commitment, a confidence that it is really a commitment and not a figure of
    speech. The `what`/`quote`/`words`/`belief` extraction stays the role's."""
    body = _user_text(messages)
    logged = _json(content)
    questions = {"found": {
        "type": "choice",
        "instructions": "Does his message contain anything that is a commitment or a stated intention "
                        "she could later hold him to -- he will watch, read or send a thing, call, "
                        "tell her something, be back by a time, do a thing tomorrow? Not moods, not "
                        "opinions, not `maybe`s with nothing attached.",
        "criteria": {"yes": "he committed to something", "no": "nothing of the kind"}}}
    for i, e in enumerate(logged.get("expectations") or []):
        if not isinstance(e, dict):
            continue
        questions["conf_%d" % i] = {
            "type": "score",
            "instructions": "Commitment: %s (his words: %s). How confident are you that this is "
                            "really a commitment and not a figure of speech?" % (
                                str(e.get("what") or "")[:120], str(e.get("quote") or "")[:80]),
            "criteria": ["not at all", "unlikely", "maybe", "probable", "certain"]}
    return {"his message and the calendar": body}, questions, logged


def _habits_him_case(messages, content):
    """(state, questions, logged) for one `habits_him` call.

    One factor per habit: how confident she can be that this is a real habit of
    his, from a week of digests. The window, `days` and `words` stay the
    role's."""
    body = _user_text(messages)
    logged = _json(content)
    questions = {}
    for i, h in enumerate(logged.get("habits") or []):
        if not isinstance(h, dict):
            continue
        questions["conf_%d" % i] = {
            "type": "score",
            "instructions": "Habit: %s (window %s, days %s). How confident can she be, from the "
                            "week of digests, that this is a real habit of his?" % (
                                str(h.get("what") or "")[:100], h.get("hours"), h.get("days")),
            "criteria": ["very unsure", "doubtful", "possible", "likely", "solid"]}
    return {"the week of digests and the habits she already expects": body}, questions, logged


BUILDERS = {"scene_director": _scene_director_case, "which_one": _which_one_case,
            "wonder_answer": _wonder_answer_case, "foresee": _foresee_case,
            "ick": _ick_case, "intent": _intent_case,
            "digest_judge": _digest_judge_case, "said_when": _said_when_case,
            "lookup": _lookup_case, "spiral": _spiral_case, "recall": _recall_case,
            "affection": _affection_case, "wonder": _wonder_case,
            "rupture_settle": _rupture_settle_case, "settle_beliefs": _settle_beliefs_case,
            "approach": _approach_case, "coherence": _coherence_case,
            "expect_him": _expect_him_case, "habits_him": _habits_him_case}


# ---------------- running one role ----------------

def run_role(key, run, role, limit):
    spec = ROLES.get(role)
    if not spec:
        sys.exit("no bar set for role %r; add it to ROLES" % role)
    build = BUILDERS.get(role)
    if not build:
        sys.exit("no case builder for role %r yet; the move is not built" % role)

    calls = logged_calls(run, role)
    if limit:
        calls = calls[:limit]
    print("== %s ==" % role)
    print("run: %s" % os.path.basename(run))
    print("logged calls: %d" % len(calls))
    if not calls:
        print("no logged call of this role on disk; the bar cannot be checked")
        return 1

    primary = spec["primary"]
    expect = spec.get("expect") or (lambda l: str(l.get(primary) or "").strip().lower())
    hits = 0
    total = 0
    used_n = used_ok = fell = 0
    floor = float(spec.get("floor", 0.5))
    for wall, messages, content, seconds in calls:
        state, questions, logged = build(messages, content)
        if not questions:
            print("  %s  no question to ask for this sample; skipped" % wall)
            continue
        res, ms = ask(key, state, questions)
        if "http_error" in res:
            print("  %s  HTTP %s  %s" % (wall, res["http_error"], res.get("body", "")[:200]))
            total += 1
            continue
        answers = res.get("answers") or {}
        total += 1
        same = "?"
        jv = {}
        for qid, q in questions.items():
            ans = answers.get(qid) or {}
            if q.get("type") == "choice":
                v, c = ans.get("choice"), ans.get("confidence")
            elif q.get("type") == "score":
                v, c = ans.get("score"), ans.get("confidence")
            else:
                v, c = ans.get("noul"), None
            jv[qid] = (v, c)
        if spec.get("combine"):
            jp, jc = spec["combine"](answers)
        else:
            jp, jc = jv.get(primary, (None, None))
        want = expect(logged)
        # when the answer is composed, the logged value to show is the composed
        # one; the raw dict has no key named after the moving field
        lp = want if spec.get("combine") else logged.get(primary)
        match = False
        shown = jp
        if want is None:
            match = False
        elif spec.get("numeric"):
            try:
                x = float(jp) * float(spec.get("scale", 1))
                y = float(want)
                shown = round(x, 3)
                match = abs(x - y) <= float(spec.get("tol", 0))
            except (TypeError, ValueError):
                match = False
        else:
            jk = str(jp).strip().lower() if jp is not None else ""
            match = bool(str(want)) and jk == str(want).strip().lower()
        if match:
            hits += 1
            same = "MATCH"
        else:
            same = "DIFF"
        used = isinstance(jc, (int, float)) and jc >= floor
        if used:
            used_n += 1
            if match:
                used_ok += 1
        else:
            fell += 1
        print("  %s  logged %s=%r  jev %s=%r (conf %s)  %s  %s  [%dms, role %ss]"
              % (wall, primary, lp, primary, shown,
                 ("%.2f" % jc) if isinstance(jc, (int, float)) else "-",
                 same, "used" if used else "fell", round(ms),
                 seconds if seconds is not None else "-"))
        for qid, (v, c) in jv.items():
            if qid == primary:
                continue
            print("      %-12s jev=%s (conf %s)  logged=%r"
                  % (qid, v, ("%.2f" % c) if isinstance(c, (int, float)) else "-", logged.get(qid)))
        print("      usage %s" % res.get("usage"))

    rate = (hits / total) if total else 0.0
    bar = spec["bar"]
    print("-- %s: %d/%d raw on %s (%.2f); bar %.2f -> %s"
          % (role, hits, total, primary, rate, bar, "PASS" if rate >= bar else "FAIL"))
    if used_n:
        print("-- %s: at floor %.2f, used %d, correct %d (%.2f); fell back %d of %d"
              % (role, floor, used_n, used_ok, used_ok / used_n, fell, total))
    else:
        print("-- %s: at floor %.2f Jev commits to nothing; the role answers every sample"
              % (role, floor))
    return 0 if rate >= bar else 1


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="read-only Jev agreement test for a stage role")
    ap.add_argument("--role", required=True, help="the role to test (one of ROLES)")
    ap.add_argument("--run", default="", help="a run directory; newest when omitted")
    ap.add_argument("--limit", type=int, default=0, help="most recent N calls (0 = all)")
    args = ap.parse_args()

    run = args.run or newest_run()
    return run_role(_key(), run, args.role, args.limit)


if __name__ == "__main__":
    raise SystemExit(main())
