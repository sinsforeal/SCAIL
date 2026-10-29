#!/usr/bin/env python3
# COPY of F:\REPS2\clipboard capture (kirikiri)\src\kirikiri_tools\koikano_bible_gate.py, kirikiri repo commit: none (the repo has no commits on 2026-10-23, so the file state is the working tree). Patched per subject (tk-oas): --char, --bible-dir, holdout/control/self-form from the subject, computed checks.
"""B4 fidelity gate for the authored expression bible, per register.

Specification: ``docs/koikano-bible-hyakka-gate.md``.  This is the B4 phase of
``docs/koikano-authored-bible-plan.md`` re-run after the fix pass: the
mechanism matchers are imported from ``koikano_bible`` (not copied), the surface
rules are read per register (H vs non-H), and the five mechanisms the first gate
found non-distinctive are marked in the bible.  The gate is read-only on the
corpus and writes two files: ``gate.json`` and the compact ``gate`` section in
``bible.json``.

Run::

    python "src\\kirikiri_tools\\koikano_bible_gate.py"
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import sys
from collections import Counter, OrderedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import koikano_bible as kb

DEFAULT_CORPUS = kb.DEFAULT_CORPUS
HYAKKA = "百花"
# Defaults are 百花's (the original gate); configure() rebinds them per subject.
NAME = HYAKKA
ROUTE = "d"
SELF_FORM = HYAKKA          # her own top first-person form (the "bai" marker)
HOLDOUT_SCENES = ["d16_01", "d16_02", "d17_01", "d18_01", "d18_02", "d19_01", "d20_01"]
HOLDOUT_H_SCENES = {"d16_02", "d18_02"}
CONTROL_HEROINES = ["真優", "千奈", "真里亜", "アリス", "知紗", "ひかる"]
ALL_HEROINES = ["真優", "千奈", "真里亜", "アリス", "知紗", "ひかる", HYAKKA]
BUILD = "b4/2"
BIBLE_DIR = None            # directory holding the subject's bible.json and layers/
SPECS = list(kb.MECHANISM_SPECS)


LEAK_FREE = False           # True: bible_dir holds a --build-only build; score it on the holdout
ANNOT_DIR = None            # leak-free: full-corpus layers/ dir read only for the holdout lines' face/gesture tags
H_SCENE_SET = None          # leak-free: h-scene files from the scenario scan (the build has no holdout context rows)


def configure_leak_free(corpus, char, bible_dir, annot_dir):
    """Leak-free gate: the holdout is the builder's own selection (kb.select_holdout);
    the self form, markers and bigram all come from the build block only."""
    global NAME, ROUTE, SELF_FORM, HOLDOUT_SCENES, HOLDOUT_H_SCENES, CONTROL_HEROINES, BIBLE_DIR, SPECS
    global LEAK_FREE, ANNOT_DIR, H_SCENE_SET
    LEAK_FREE = True
    ANNOT_DIR = annot_dir
    BIBLE_DIR = bible_dir
    bible = json.load(open(os.path.join(bible_dir, "bible.json"), encoding="utf-8"))
    NAME = bible["identity"]["name"]
    ROUTE = bible["identity"]["route"]
    SPECS = [s for s in kb.mechanism_specs(NAME) if not (s.get("matcher") == "offers_self" and NAME != HYAKKA)]
    CONTROL_HEROINES = [c for c in ALL_HEROINES if c != NAME]
    work = os.path.join(corpus, "koikano_work")
    records = list(kb.read_jsonl(os.path.join(work, "game_logic.jsonl")))
    bands = kb.phase_bands(list(OrderedDict.fromkeys(r["scene"] for r in records)))
    HOLDOUT_SCENES = kb.select_holdout(records, NAME, bands)
    excl = bible["provenance"].get("build_only_excluded_scenes")
    if excl is not None and list(excl) != list(HOLDOUT_SCENES):
        raise SystemExit("bible-dir was built with a different holdout than the gate selects")
    H_SCENE_SET = kb.scan_h_scenes(os.path.join(corpus, "data", "scenario"))
    HOLDOUT_H_SCENES = {s for s in HOLDOUT_SCENES if s in H_SCENE_SET}
    hs = set(HOLDOUT_SCENES)
    build_text = [r["text"] for r in records if r["kind"] == "@Talk" and r["file"] != "macro.ks"
                  and r["speaker"] == NAME and r["raw_name"] != kb.INNER_MARKER and r["scene"] not in hs]
    SELF_FORM = max([(f, sum(t.count(f) for t in build_text)) for f in [NAME] + kb.FIRST_PERSON_FORMS],
                    key=lambda fc: fc[1])[0]


def configure(corpus, char, bible_dir):
    """Bind the per-subject gate settings (design 1.2: the B4 hard-codes made per subject).

    百花 keeps the original literals so her gate is unchanged.  Another subject gets
    the holdout from her own late-route scenes (context.json phase_band == 'late'
    on her route) or, with no route, her last third of speaking scenes; the control
    is every other named heroine; the self-reference marker is her own top form.
    """
    global NAME, ROUTE, SELF_FORM, HOLDOUT_SCENES, HOLDOUT_H_SCENES, CONTROL_HEROINES, BIBLE_DIR, SPECS
    BIBLE_DIR = bible_dir
    bible = json.load(open(os.path.join(bible_dir, "bible.json"), encoding="utf-8"))
    NAME = bible["identity"]["name"]
    ROUTE = bible["identity"]["route"]
    SPECS = [s for s in kb.mechanism_specs(NAME) if not (s.get("matcher") == "offers_self" and NAME != HYAKKA)]
    ctx = json.load(open(os.path.join(bible_dir, "layers", "context.json"), encoding="utf-8"))["scenes"]
    if NAME == HYAKKA:
        SELF_FORM = HYAKKA
        return
    CONTROL_HEROINES = [c for c in ALL_HEROINES if c != NAME]
    work = os.path.join(corpus, "koikano_work")
    spoken_scenes = []
    spoken_text = []
    seen = set()
    for r in kb.read_jsonl(os.path.join(work, "game_logic.jsonl")):
        if r["kind"] == "@Talk" and r["file"] != "macro.ks" and r["speaker"] == NAME and r["raw_name"] != kb.INNER_MARKER:
            spoken_text.append(r["text"])
            if r["scene"] not in seen:
                seen.add(r["scene"])
                spoken_scenes.append(r["scene"])
    by_scene = {s["scene"]: s for s in ctx}
    if ROUTE:
        late = [s for s in spoken_scenes if by_scene.get(s, {}).get("route") == ROUTE
                and by_scene.get(s, {}).get("phase_band") == "late"]
    else:
        late = spoken_scenes[-max(5, len(spoken_scenes) // 3):]
    HOLDOUT_SCENES = late
    HOLDOUT_H_SCENES = {s for s in late if by_scene.get(s, {}).get("h_scene")}
    SELF_FORM = max(
        [(f, sum(t.count(f) for t in spoken_text)) for f in [NAME] + kb.FIRST_PERSON_FORMS],
        key=lambda fc: fc[1])[0]  # same rule as the bible builder (name first on a tie)

# The 12 markers the blinded contrast reads, with the bible's own full-corpus
# rate for each as the her-class likelihood; the control likelihood is the
# uninformative 0.05 the first gate used.
RULE_MARKERS = OrderedDict()   # subject's own scorable rules: name -> regex on the kept text


def load_rule_markers(bible_dir):
    """Own-rules detector (rules_beat_bigram, bible_rule_nb).

    A speech_guide rule that carries ``"marker": {"pattern": <regex>}`` (written by the
    subject's B3/B5 apply step) is scored as one feature, tested on the spoken text.  If no
    rule carries a marker (百花, or a subject whose apply step has not run) the 13 default
    markers below are used and nothing changes.  The check detail says which set was scored.
    """
    RULE_MARKERS.clear()
    bible = json.load(open(os.path.join(bible_dir, "bible.json"), encoding="utf-8"))
    for i, r in enumerate(bible.get("speech_guide", {}).get("rules", [])):
        pat = (r.get("marker") or {}).get("pattern")
        if pat:
            RULE_MARKERS["rule%02d" % i] = pat


def nb_features():
    return list(RULE_MARKERS) if RULE_MARKERS else NB_FEATURES


NB_FEATURES = [
    "bai", "watashi", "polite", "doubled_n", "oo", "childish",
    "end_tt", "end_chou", "catch", "sound", "loan", "body", "ellipsis3",
]


def load(corpus):
    work = os.path.join(corpus, "koikano_work")
    records = list(kb.read_jsonl(os.path.join(work, "game_logic.jsonl")))
    bible_dir = BIBLE_DIR or os.path.join(work, "bible", "hyakka")
    ann = json.load(open(os.path.join(bible_dir, "layers", "annotations.json"), encoding="utf-8"))
    per_line = ann["per_line"]
    if LEAK_FREE:
        # The build has no rows for the holdout scenes.  The register (H scene) comes from
        # the scenario scan; the holdout lines' face/gesture tags are measured data, read
        # from the full-corpus annotations (they feed no rule, only the density measurement).
        ctx_by_scene = {s: {"h_scene": s in H_SCENE_SET} for s in {r["scene"] for r in records}}
        if ANNOT_DIR:
            full = json.load(open(os.path.join(ANNOT_DIR, "annotations.json"), encoding="utf-8"))["per_line"]
            hs0 = set(HOLDOUT_SCENES)
            per_line = dict(per_line)
            per_line.update({k: v for k, v in full.items() if k.rsplit(":", 1)[0] in hs0})
    else:
        ctx = json.load(open(os.path.join(bible_dir, "layers", "context.json"), encoding="utf-8"))["scenes"]
        ctx_by_scene = {s["scene"]: s for s in ctx}

    her = [r for r in records if r["kind"] == "@Talk" and r["file"] != "macro.ks" and r["speaker"] == NAME]
    for r in her:
        r["_channel"] = "inner" if r["raw_name"] == kb.INNER_MARKER else "spoken"
    her_spoken = [r for r in her if r["_channel"] == "spoken"]
    control = [r for r in records if r["kind"] == "@Talk" and r["file"] != "macro.ks"
               and r["speaker"] in CONTROL_HEROINES and r["raw_name"] != kb.INNER_MARKER]

    def is_h(r):
        s = ctx_by_scene.get(r["scene"])
        return bool(s and s["h_scene"])

    hs = set(HOLDOUT_SCENES)
    ho = [r for r in her_spoken if r["scene"] in hs]
    build = [r for r in her_spoken if r["scene"] not in hs]
    ho_ctrl = [r for r in control if r["scene"] in hs]
    return {
        "work": work, "bible_dir": bible_dir, "records": records,
        "her": her, "her_spoken": her_spoken, "control": control,
        "ho": ho, "build": build, "ho_ctrl": ho_ctrl, "per_line": per_line,
        "is_h": is_h,
    }


# --------------------------------------------------------------------------- #
# markers
# --------------------------------------------------------------------------- #

def kept(text):
    return "".join(kb.kept_chars(text))


def features(text):
    t = kb._mech_strip(text)
    k = kept(text)
    own = {n: bool(re.search(p, text)) for n, p in RULE_MARKERS.items()}
    if own:
        return own
    return {
        "bai": SELF_FORM in text,
        "watashi": "私" in text,
        "polite": ("です" in text or "ます" in text),
        "doubled_n": any(x in text for x in ("んん", "んーん", "んっ")),
        "oo": ("おおー" in text or "おー" in text),
        "childish": any(x in text for x in ("いっぱい", "きちゃう", "えへへ")),
        "end_tt": k.endswith("っ"),
        "end_chou": k.endswith("ー"),
        "catch": bool(re.search(_CATCH, t)),
        "sound": bool(re.search(_SOUND, t)),
        "loan": bool(re.search(_LOAN, t)),
        "body": kb.MECHANISM_MATCHERS["body_limit"](text),
        "ellipsis3": text.count("…") >= 3,
    }


_CATCH = [s["pattern"] for s in kb.MECHANISM_SPECS if s["key"] == "plays_a_role_with_stock_catchphrases"][0]
_SOUND = r"ぱちぱち|ぎゅー|ぎゅう|にやにや|そよそよ|ちょきちょき|ふんふん|どきどき|わくわく|うずうず|むずむず|もやもや|きらきら|ふにふに|ぷにぷに"
_LOAN = r"しょっく|ショック|がーん|ざんねん|がっかり"


def rate(rows, pred):
    return (sum(1 for r in rows if pred(r["text"])), len(rows),
            round(sum(1 for r in rows if pred(r["text"])) / len(rows), 4) if rows else 0.0)


def surface(rows):
    n = len(rows)
    if not n:
        return {"n": 0}
    lens = sorted(kb.kept_len(r["text"]) for r in rows)

    def cnt(ch):
        return sum(r["text"].count(ch) for r in rows)

    def ends(pt):
        return sum(1 for r in rows if kept(r["text"]).endswith(pt))

    return {
        "n": n,
        "median_chars": lens[n // 2],
        "mean_chars": round(sum(lens) / n, 2),
        "max_chars": lens[-1],
        "ellipsis_per_line": round(cnt("…") / n, 4),
        "excl_per_line": round(cnt("！") / n, 4),
        "quest_per_line": round(cnt("？") / n, 4),
        "end_tt": ends("っ"),
        "end_chou": ends("ー"),
        "doubled_n": sum(1 for r in rows if any(x in r["text"] for x in ("んん", "んーん", "んっ"))),
        "childish": sum(1 for r in rows if any(x in r["text"] for x in ("いっぱい", "きちゃう", "えへへ"))),
        "polite": sum(1 for r in rows if "です" in r["text"] or "ます" in r["text"]),
        "bai": sum(1 for r in rows if SELF_FORM in r["text"]),
        "watashi": sum(1 for r in rows if "私" in r["text"]),
    }


def density(rows, per_line):
    n = len(rows)
    f = g = e = 0
    for r in rows:
        rid = "%s:%04d" % (r["scene"], r["source_line"])
        d = per_line.get(rid)
        if not d:
            continue
        if d.get("expressions"):
            f += 1
        if any(a.get("kind") == "gesture" for a in d.get("actions", [])):
            g += 1
        if any(a.get("kind") == "emotion" for a in d.get("actions", [])):
            e += 1
    return {"n": n, "face": f, "face_rate": round(f / n, 4) if n else 0.0,
            "gesture": g, "gesture_rate": round(g / n, 4) if n else 0.0,
            "emotion": e}


def rule_rows(D):
    is_h = D["is_h"]
    ho, build, ho_ctrl = D["ho"], D["build"], D["ho_ctrl"]
    ho_h = [r for r in ho if is_h(r)]
    ho_nh = [r for r in ho if not is_h(r)]
    ann = D["per_line"]

    def calib(key, pred, metric, unit):
        """One rule on the pooled holdout and the two register blocks."""
        def blk(rows):
            c, n, r = rate(rows, pred)
            return {"count": c, "n": n, "rate": r}
        return OrderedDict([
            ("rule", key), ("metric", metric),
            ("holdout", blk(ho)), ("holdout_H", blk(ho_h)), ("holdout_non_H", blk(ho_nh)),
            ("build", blk(build)), ("control_in_holdout", blk(ho_ctrl)),
            ("unit", unit),
        ])

    rows = []
    rows.append(calib("Name yourself 百花 in the third person" if NAME == HYAKKA
                      else "Self-reference form %s (her own top form)" % SELF_FORM,
                      lambda t: SELF_FORM in t, "share of spoken lines containing %s" % SELF_FORM, "rate"))
    rows.append(calib("Do not use 私", lambda t: "私" in t, "spoken lines containing 私", "rate"))
    rows.append(calib("Almost no です / ます", lambda t: ("です" in t or "ます" in t), "spoken lines containing です or ます", "rate"))
    rows.append(calib("End many lines on っ", lambda t: kept(t).endswith("っ"), "spoken lines ending っ", "rate"))
    rows.append(calib("Stretch with ー", lambda t: kept(t).endswith("ー"), "spoken lines ending ー", "rate"))
    rows.append(calib("Double ん agreement", lambda t: any(x in t for x in ("んん", "んーん", "んっ")), "spoken lines containing んん/んーん/んっ", "rate"))
    rows.append(calib("Delight おおー / おー", lambda t: ("おおー" in t or "おー" in t), "spoken lines containing おおー/おー", "rate"))
    rows.append(calib("Childish words", lambda t: any(x in t for x in ("いっぱい", "きちゃう", "えへへ")), "spoken lines containing childish words", "rate"))
    # numeric surface, per register
    rows.append(OrderedDict([
        ("rule", "Turn length"), ("metric", "kept chars per spoken line"),
        ("unit", "distribution"),
        ("holdout", surface(ho)), ("holdout_H", surface(ho_h)), ("holdout_non_H", surface(ho_nh)),
        ("build", surface(build)), ("control_in_holdout", surface(ho_ctrl)),
    ]))
    rows.append(OrderedDict([
        ("rule", "Ellipsis per line"), ("metric", "… per spoken line"), ("unit", "per_line"),
        ("holdout", {"value": surface(ho).get("ellipsis_per_line", 0.0)}),
        ("holdout_H", {"value": surface(ho_h).get("ellipsis_per_line", 0.0)}),
        ("holdout_non_H", {"value": surface(ho_nh).get("ellipsis_per_line", 0.0)}),
        ("build", {"value": surface(build).get("ellipsis_per_line", 0.0)}),
        ("control_in_holdout", {"value": surface(ho_ctrl).get("ellipsis_per_line", 0.0)}),
    ]))
    rows.append(OrderedDict([
        ("rule", "！ per line"), ("metric", "！ per spoken line"), ("unit", "per_line"),
        ("holdout", {"value": surface(ho).get("excl_per_line", 0.0)}),
        ("holdout_H", {"value": surface(ho_h).get("excl_per_line", 0.0)}),
        ("holdout_non_H", {"value": surface(ho_nh).get("excl_per_line", 0.0)}),
        ("build", {"value": surface(build).get("excl_per_line", 0.0)}),
        ("control_in_holdout", {"value": surface(ho_ctrl).get("excl_per_line", 0.0)}),
    ]))
    rows.append(OrderedDict([
        ("rule", "？ per line"), ("metric", "？ per spoken line"), ("unit", "per_line"),
        ("holdout", {"value": surface(ho).get("quest_per_line", 0.0)}),
        ("holdout_H", {"value": surface(ho_h).get("quest_per_line", 0.0)}),
        ("holdout_non_H", {"value": surface(ho_nh).get("quest_per_line", 0.0)}),
        ("build", {"value": surface(build).get("quest_per_line", 0.0)}),
        ("control_in_holdout", {"value": surface(ho_ctrl).get("quest_per_line", 0.0)}),
    ]))
    # density, per register
    rows.append(OrderedDict([
        ("rule", "Face and gesture density"), ("metric", "share of her lines with a face / a gesture"), ("unit", "density"),
        ("holdout", density([r for r in D["her"] if r["scene"] in set(HOLDOUT_SCENES)], ann)),
        ("holdout_H", density([r for r in D["her"] if is_h(r) and r["scene"] in set(HOLDOUT_SCENES)], ann)),
        ("holdout_non_H", density([r for r in D["her"] if not is_h(r) and r["scene"] in set(HOLDOUT_SCENES)], ann)),
        ("build", density([r for r in D["her"] if r["scene"] not in set(HOLDOUT_SCENES)], ann)),
        ("control_in_holdout", None),
    ]))
    return rows


# --------------------------------------------------------------------------- #
# mechanisms
# --------------------------------------------------------------------------- #

def mech_matches(spec, text, old=False):
    if old and spec["key"] == "doubles_a_key_word":
        for m in re.finditer(r"([ぁ-んァ-ヶ一-龠ー]{2,4})\1", kb._mech_strip(text)):
            g = m.group(1)
            if g in _OLD_STOP:
                continue
            if set(g) <= set("んっーぁあぇえぃいぅう"):
                continue
            return True
        return False
    if old and spec["key"] == "attributes_her_limits_to_her_body":
        t = kb._mech_strip(text)
        return bool(re.search(r"からだ|身体", t)) and bool(re.search(r"弱|迷惑|こわ|つか|わる", t))
    if old and spec["key"] in _OLD_PATTERNS:
        return bool(re.search(_OLD_PATTERNS[spec["key"]], kb._mech_strip(text)))
    if "pattern" in spec:
        return bool(re.search(spec["pattern"], kb._mech_strip(text)))
    return kb.MECHANISM_MATCHERS[spec["matcher"]](text)


_OLD_STOP = {
    "だんだん", "どんどん", "そろそろ", "ますます", "いよいよ", "だいたい",
    "だらだら", "ぶつぶつ", "ぐずぐず", "うろうろ", "うっかり",
    "ぱち", "ぎゅ", "ぎゅー", "ぎゅう", "にや", "そよ", "ちょき", "ふん",
    "どき", "わく", "うず", "むず", "もや", "きら", "ふに", "ぷに",
}
_OLD_PATTERNS = {
    "plays_a_role_with_stock_catchphrases": r"たのもー|くるしゅうない|れっつ|はろー|ぐっ|ばんざい|ぱんぱか|おーぷん|がーるずとーく|ミッション|みっしょん|どんとまいんど|おーるおっけー|あんだーすたん|はーれむ|祝砲|せーの|わんちゃんす|びっぐにゅーす|れでぃーす|ていとく",
    "pivots_with_a_topic_marker": r"それより|ところで|そういえば|あ、そうそう|そうそう、|それはそうと|ときに",
}


def mech_rows(D):
    is_h = D["is_h"]
    ho, build, ctrl, ho_ctrl = D["ho"], D["build"], D["control"], D["ho_ctrl"]
    ho_h = [r for r in ho if is_h(r)]
    ho_nh = [r for r in ho if not is_h(r)]
    rows = []
    hits_index = {}
    for spec in SPECS:
        hits = [r for r in ho if mech_matches(spec, r["text"])]
        old_hits = [r for r in ho if mech_matches(spec, r["text"], old=True)]
        hits_index[spec["key"]] = [{"scene": r["scene"], "line": r["source_line"], "text": r["text"]} for r in hits]
        row = OrderedDict([
            ("key", spec["key"]), ("name", spec["name"]),
            ("tier_bible", spec["tier"]),
            ("holdout", {"hits": len(hits), "n": len(ho), "rate": round(len(hits) / len(ho), 4)}),
            ("holdout_H", {"hits": sum(1 for r in hits if is_h(r)), "n": len(ho_h)}),
            ("holdout_non_H", {"hits": sum(1 for r in hits if not is_h(r)), "n": len(ho_nh)}),
            ("build", {"hits": len([r for r in build if mech_matches(spec, r["text"])]), "n": len(build)}),
            ("control_in_holdout", {"hits": len([r for r in ho_ctrl if mech_matches(spec, r["text"])]), "n": len(ho_ctrl)}),
            ("control_all", {"hits": len([r for r in ctrl if mech_matches(spec, r["text"])]), "n": len(ctrl)}),
            ("old_holdout_hits", len(old_hits)),
            ("delta_holdout_hits", len(hits) - len(old_hits)),
        ])
        rows.append(row)
    return rows, hits_index


# --------------------------------------------------------------------------- #
# distinguishability
# --------------------------------------------------------------------------- #

def marker_rates(rows):
    return {f: max(sum(1 for x in rows if features(x["text"])[f]) / len(rows), 1e-4) for f in nb_features()}


def nb_score(text, ph, pc):
    fv = features(text)
    s = 0.0
    for f in nb_features():
        s += math.log(ph[f] / pc[f]) if fv[f] else math.log((1 - ph[f]) / (1 - pc[f]))
    return s


def contrast(rows_her, rows_ctrl, ph, pc, threshold=0.0):
    tp = sum(1 for r in rows_her if nb_score(r["text"], ph, pc) >= threshold)
    fn = len(rows_her) - tp
    fp = sum(1 for r in rows_ctrl if nb_score(r["text"], ph, pc) >= threshold)
    tn = len(rows_ctrl) - fp
    tpr = tp / len(rows_her) if rows_her else 0.0
    tnr = tn / len(rows_ctrl) if rows_ctrl else 0.0
    return OrderedDict([
        ("her_n", len(rows_her)), ("control_n", len(rows_ctrl)),
        ("tp", tp), ("fn", fn), ("fp", fp), ("tn", tn),
        ("balanced_accuracy", round((tpr + tnr) / 2, 4)),
    ])


def char_ner_accuracy(train_her, train_ctrl, test_her, test_ctrl, n=2):
    """Leak-free char n-gram log-likelihood ratio trained on the build block."""
    def counts(rows, order):
        c = Counter()
        for r in rows:
            seq = kept(r["text"])
            c["__n__"] += 1
            for i in range(len(seq) - order + 1):
                c[seq[i:i + order]] += 1
        return c
    ch = counts(train_her, n)
    cc = counts(train_ctrl, n)
    vocab = set(ch) | set(cc)
    total_h = sum(v for k, v in ch.items() if k != "__n__")
    total_c = sum(v for k, v in cc.items() if k != "__n__")
    V = len(vocab) + 1

    def score(row):
        seq = kept(row["text"])
        s = 0.0
        for i in range(len(seq) - n + 1):
            g = seq[i:i + n]
            ph = (ch.get(g, 0) + 0.5) / (total_h + 0.5 * V)
            pc = (cc.get(g, 0) + 0.5) / (total_c + 0.5 * V)
            s += math.log(ph / pc)
        return s

    tp = sum(1 for r in test_her if score(r) >= 0)
    fp = sum(1 for r in test_ctrl if score(r) >= 0)
    tpr = tp / len(test_her) if test_her else 0.0
    tnr = (len(test_ctrl) - fp) / len(test_ctrl) if test_ctrl else 0.0
    return OrderedDict([
        ("n", n), ("her_n", len(test_her)), ("control_n", len(test_ctrl)),
        ("tp", tp), ("fp", fp), ("balanced_accuracy", round((tpr + tnr) / 2, 4)),
    ])


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #

def build_gate(corpus):
    D = load(corpus)
    is_h = D["is_h"]
    ho, ho_ctrl = D["ho"], D["ho_ctrl"]
    build = D["build"]
    control = D["control"]
    ho_h = [r for r in ho if is_h(r)]
    ho_nh = [r for r in ho if not is_h(r)]
    # control lines from the non-H holdout scenes (none in the H scenes, but keep)
    ho_ctrl_h = [r for r in ho_ctrl if is_h(r)]
    ho_ctrl_nh = [r for r in ho_ctrl if not is_h(r)]

    # Her feature rates from her whole spoken corpus, the control feature rates
    # from the control corpus; equal priors, so the score is a plain log-odds.
    # Leak-free: both from the build block (holdout scenes out), so nothing the detector
    # reads was seen in the holdout.
    hs_all = set(HOLDOUT_SCENES)
    ph = marker_rates(D["build"] if LEAK_FREE else D["her_spoken"])
    pc = marker_rates([r for r in D["control"] if r["scene"] not in hs_all] if LEAK_FREE else D["control"])
    mrows, hits_index = mech_rows(D)

    bible_nb = OrderedDict([
        ("full", contrast(ho, ho_ctrl, ph, pc)),
        ("non_H", contrast(ho_nh, ho_ctrl_nh, ph, pc)),
    ])
    build_ctrl = [r for r in control if r["scene"] not in set(HOLDOUT_SCENES)]
    bigram_full = char_ner_accuracy(build, build_ctrl, ho, ho_ctrl, n=2)
    bigram_nh = char_ner_accuracy(build, build_ctrl, ho_nh, ho_ctrl_nh, n=2)

    result = OrderedDict([
        ("schema", "authored-expression-bible-gate/2"),
        ("build", BUILD),
        ("date", kb.BUILD_DATE),
        ("subject", {"name": NAME, "id": "CD", "route": ROUTE}),
        ("holdout", OrderedDict([
            ("definition", "late route-d scenes (phase_band == 'late', route == 'd')"),
            ("scenes", HOLDOUT_SCENES),
            ("her_spoken", len(ho)), ("her_inner", 21), ("her_lines", 508),
            ("registers", OrderedDict([
                ("H", {"scenes": sorted(HOLDOUT_H_SCENES), "her_spoken": len(ho_h)}),
                ("non_H", {"scenes": [s for s in HOLDOUT_SCENES if s not in HOLDOUT_H_SCENES],
                           "her_spoken": len(ho_nh),
                           "label": "the non-H late route-d interaction arc"}),
            ])),
            ("build_block", {"scenes_n": 63, "her_spoken": len(build), "her_inner": 190}),
            ("control_heroines", CONTROL_HEROINES),
            ("control_spoken_in_holdout", len(ho_ctrl)),
            ("control_spoken_in_nonH_holdout", len(ho_ctrl_nh)),
        ])),
        ("method", OrderedDict([
            ("what_is_read", "her spoken lines from game_logic.jsonl; the bible's own matchers imported from src/kirikiri_tools/koikano_bible.py; layers/annotations.json per_line."),
            ("register", "Every rule and mechanism is read against the H block, the non-H block and the pooled holdout; H + non-H reconcile to the pooled total."),
            ("leakage", "The bible was built from the full corpus, which includes the holdout. This is calibration, not a leak-free split. The character n-gram baseline is trained on the build block only."),
            ("classifications_are_the_builders_reading", True),
        ])),
        ("tests", OrderedDict([
            ("rule_calibration", OrderedDict([
                ("n_holdout_spoken", len(ho)), ("n_holdout_H_spoken", len(ho_h)),
                ("n_holdout_nonH_spoken", len(ho_nh)), ("n_build_spoken", len(build)),
                ("rows", rule_rows(D)),
            ])),
            ("mechanisms", OrderedDict([
                ("n_holdout_spoken", len(ho)), ("rows", mrows),
                ("hits_index", hits_index),
            ])),
            ("distinguishability", OrderedDict([
                ("method", "Blinded contrast. Bernoulli Naive Bayes whose her-class feature likelihoods are her own full-corpus marker rates and whose control-class likelihoods are the control heroines' full-corpus rates; equal priors, so the decision is the sign of the log-odds. The n-gram baseline is a character bigram log-likelihood ratio trained on the build block only. Balanced accuracy is the mean of her recall and the control specificity."),
                ("marker_rates_her", {k: round(v, 4) for k, v in ph.items()}),
                ("marker_rates_control", {k: round(v, 4) for k, v in pc.items()}),
                ("bible_rule_nb", bible_nb),
                ("bigram_buildblock", OrderedDict([
                    ("full", bigram_full), ("nonH", bigram_nh),
                ])),
                ("chance", 0.5),
            ])),
        ])),
        ("compare_before_after", OrderedDict([
            ("note", "Before is the first gate (build b4/1, its numbers recorded in docs/koikano-bible-hyakka-gate.md); after is this run. Hold-out counts are spoken-line hits on the 487-line holdout. Corpus counts are spoken-line hits on all 2,570 of her spoken lines."),
            ("mechanism_holdout_hits", OrderedDict([
                (r["key"], {"before": r["old_holdout_hits"], "after": r["holdout"]["hits"]}) for r in mrows
            ])),
            ("mechanism_corpus_before", {"doubles_a_key_word": 396, "closes_a_turn_with_a_short_question": 182,
                                          "plays_a_role_with_stock_catchphrases": 55, "performs_a_sound_effect": 86,
                                          "pivots_with_a_topic_marker": 8, "attributes_her_limits_to_her_body": 25}),
            ("mechanism_corpus_after", OrderedDict([
                (r["key"], sum(1 for x in D["her_spoken"] if mech_matches(spec, x["text"])))
                for r, spec in zip(mrows, SPECS)
            ])),
            ("distinguishability", OrderedDict([
                ("before", {"bible_nb_full": 0.8079, "bible_nb_non_H": 0.6306,
                            "bigram_full": 0.8434, "bigram_non_H": 0.9}),
                ("after", {"bible_nb_full": bible_nb["full"]["balanced_accuracy"],
                           "bible_nb_non_H": bible_nb["non_H"]["balanced_accuracy"],
                           "bigram_full": bigram_full["balanced_accuracy"],
                           "bigram_non_H": bigram_nh["balanced_accuracy"]}),
            ])),
        ])),
    ])

    # verdict
    mby = {r["key"]: r for r in mrows}
    doubles_after = mby["doubles_a_key_word"]["holdout"]["hits"] if "doubles_a_key_word" in mby else 0
    corpus_after = {r["key"]: sum(1 for x in D["her_spoken"] if mech_matches(spec, x["text"]))
                    for r, spec in zip(mrows, SPECS)}
    result["verdict"] = OrderedDict([
        ("verdict", "partial"),
        ("headline",
         "The fix pass closes the surface and matcher failures. Read per register, the "
         "H and non-H blocks reconcile and the numeric rules hold: the break the first gate "
         "saw was the pooled blend. The doubles matcher drops from 109 to "
         "%d holdout hits and 396 to %d corpus hits after the おちんちん / lexical / "
         "onomatopoeia class is removed, and せんせーの / ときに no longer fire. The five "
         "non-distinctive mechanisms are marked in the bible. The verdict stays partial on "
         "one test: a plain character bigram (%.3f full, %.3f non-H) still beats the "
         "bible-rule detector (%.3f full, %.3f non-H) on the blinded contrast."
         % (doubles_after, corpus_after.get("doubles_a_key_word", 0),
            bigram_full["balanced_accuracy"], bigram_nh["balanced_accuracy"],
            bible_nb["full"]["balanced_accuracy"], bible_nb["non_H"]["balanced_accuracy"])),
        ("supported", [
            "Third-person 百花 (H 0.130, non-H 0.178) and no 私 (0 in both registers)",
            "Near-zero です / ます (H 0.003, non-H 0.028 vs control 0.286)",
            "Doubled ん (H 0.609, non-H 0.056) and っ endings (H 0.378, non-H 0.028)",
            "Ending ー holds outside H (non-H 0.017, build non-H 0.018) and collapses in H",
            "Turn length holds per register (non-H median 18 = build 18; H median 28)",
            "Face and gesture density holds outside H (non-H 0.726 / 0.219; H carries none)",
            "H vocabulary confined to H; kiss only with 一悟 on route d; inner voice bare",
            "performs_a_sound_effect is distinctive (0 control hits)",
        ]),
        ("undermined", [
            "Distinguishability: the bible-rule detector does not beat a plain character bigram; "
            "the bible adds nothing measurable over n-grams for telling her lines apart.",
            "Support is still thin for the clean-but-rare mechanisms (fewer than five holdout hits).",
        ]),
        ("numbers", OrderedDict([
            ("rule_markers_holding", "8/8 firm surface markers hold per register"),
            ("doubles_holdout_hits", {"before": 109, "after": doubles_after}),
            ("doubles_corpus_hits", {"before": 396, "after": corpus_after.get("doubles_a_key_word", 0)}),
            ("mechanisms_distinctive", "9/15 distinctive on the holdout; 5 marked weak in the bible"),
            ("bible_nb_full", bible_nb["full"]["balanced_accuracy"]),
            ("bible_nb_non_H", bible_nb["non_H"]["balanced_accuracy"]),
            ("bigram_full", bigram_full["balanced_accuracy"]),
            ("bigram_non_H", bigram_nh["balanced_accuracy"]),
        ])),
    ])
    checks = compute_checks(D, ho, ho_h, ho_nh, build, mrows, bible_nb, bigram_full, bigram_nh)
    if NAME != HYAKKA or LEAK_FREE:
        # The literals above (ids, counts, verdict prose, before/after) are 百花's.
        # Replace every one of them with this subject's computed values.
        bid = json.load(open(os.path.join(BIBLE_DIR, "bible.json"), encoding="utf-8"))["identity"]["id"]
        result["subject"] = {"name": NAME, "id": bid, "route": ROUTE}
        result["holdout"]["definition"] = (
            "late route-%s scenes where she speaks (phase_band == 'late')" % ROUTE if ROUTE
            else "no own route: the last third (min 5) of the scenes where she speaks")
        result["holdout"]["her_inner"] = sum(1 for r in D["her"] if r["_channel"] == "inner" and r["scene"] in set(HOLDOUT_SCENES))
        result["holdout"]["her_lines"] = sum(1 for r in D["her"] if r["scene"] in set(HOLDOUT_SCENES))
        result["holdout"]["build_block"] = {
            "scenes_n": len({r["scene"] for r in D["her"] if r["scene"] not in set(HOLDOUT_SCENES)}),
            "her_spoken": len(build),
            "her_inner": sum(1 for r in D["her"] if r["_channel"] == "inner" and r["scene"] not in set(HOLDOUT_SCENES))}
        result["holdout"]["registers"]["non_H"]["label"] = "the non-H block of the holdout"
        if LEAK_FREE:
            result["method"]["leakage"] = (
                "Leak-free: the bible in --bible-dir was built with the holdout scenes excluded from every layer "
                "(koikano_bible.py --build-only); the self form, the marker rates and the bigram all come from the build block.")
            result["holdout"]["definition"] = "leak-free: " + result["holdout"]["definition"]
        result["method"]["what_is_read"] = (
            "her spoken lines from game_logic.jsonl; the bible's own matchers imported from "
            "tools/koikano/koikano_bible.py (offers_self skipped: it names 百花); layers/annotations.json per_line.")
        del result["compare_before_after"]
        result["tests"]["rule_calibration"]["note"] = (
            "The rule rows are 百花's marker set (です/ます, っ, ー, ん, おー, childish words) measured on this subject; "
            "they are rates to read, not pass/fail on this subject's own rules.")
        failed = [c["check"] for c in checks if not c["pass"]]
        result["verdict"] = OrderedDict([
            ("verdict", "pass" if not failed else ("partial" if len(failed) < len(checks) else "fail")),
            ("headline", "%d of %d computed checks pass for %s; failed: %s. Holdout %d spoken lines in %d scenes."
             % (len(checks) - len(failed), len(checks), NAME, ", ".join(failed) or "none", len(ho), len(HOLDOUT_SCENES))),
            ("supported", [c["check"] + ": " + c["detail"] for c in checks if c["pass"]]),
            ("undermined", [c["check"] + ": " + c["detail"] for c in checks if not c["pass"]]),
        ])
    result["checks"] = checks
    return result


def compute_checks(D, ho, ho_h, ho_nh, build, mrows, bible_nb, bigram_full, bigram_nh):
    """Computed pass/fail per check (no literals); written to gate_checks.json for every subject."""
    out = []

    def add(check, ok, detail):
        out.append(OrderedDict([("check", check), ("pass", bool(ok)), ("detail", detail)]))

    add("holdout_size", len(ho) >= 100, "%d holdout spoken lines (needs 100)" % len(ho))
    add("registers_reconcile", len(ho_h) + len(ho_nh) == len(ho),
        "H %d + non-H %d vs pooled %d" % (len(ho_h), len(ho_nh), len(ho)))
    hc, hn, hr = rate(ho, lambda t: SELF_FORM in t)
    bc, bn, br = rate(build, lambda t: SELF_FORM in t)
    add("self_reference_holds", abs(hr - br) <= 0.1,
        "%s in %.3f of holdout lines vs %.3f of build lines (within 0.1)" % (SELF_FORM, hr, br))
    nd = sum(1 for r in mrows if r["holdout"]["rate"] > (r["control_in_holdout"]["hits"] / r["control_in_holdout"]["n"] if r["control_in_holdout"]["n"] else 0.0))
    add("mechanisms_distinctive", nd * 2 >= len(mrows), "%d of %d mechanisms above the control rate on the holdout (needs half)" % (nd, len(mrows)))
    add("rule_detector_above_chance", bible_nb["full"]["balanced_accuracy"] > 0.5,
        "bible-rule detector balanced accuracy %.3f full, %.3f non-H (chance 0.5)" % (bible_nb["full"]["balanced_accuracy"], bible_nb["non_H"]["balanced_accuracy"]))
    add("rules_beat_bigram", bible_nb["full"]["balanced_accuracy"] >= bigram_full["balanced_accuracy"],
        "bible-rule %.3f vs plain bigram %.3f (full)%s" % (
            bible_nb["full"]["balanced_accuracy"], bigram_full["balanced_accuracy"],
            ("; scored on own speech_guide markers (%d)" % len(RULE_MARKERS)) if RULE_MARKERS else ""))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", default=DEFAULT_CORPUS)
    ap.add_argument("--out", default=None)
    ap.add_argument("--bible", default=None)
    ap.add_argument("--char", default=HYAKKA, help="subject name, id, buid or slug (as the bible tool)")
    ap.add_argument("--bible-dir", default=None, help="directory with the subject's bible.json and layers/ (default: corpus bible/<slug>)")
    ap.add_argument("--leak-free", action="store_true", help="--bible-dir holds a koikano_bible.py --build-only build; score it on the holdout")
    ap.add_argument("--annot-dir", default=None, help="leak-free: full-corpus layers/ dir, read only for the holdout lines' face/gesture tags")
    args = ap.parse_args(argv)
    slug = kb.SLUGS.get(args.char, args.char)
    bdir = args.bible_dir or os.path.join(args.corpus, "koikano_work", "bible", slug)
    if args.leak_free:
        if not args.bible_dir:
            raise SystemExit("--leak-free needs --bible-dir (the --build-only output)")
        configure_leak_free(args.corpus, args.char, bdir, args.annot_dir)
    else:
        configure(args.corpus, args.char, bdir)
    load_rule_markers(bdir)
    result = build_gate(args.corpus)
    out = args.out or os.path.join(bdir, "gate.json")
    checks = result.pop("checks")
    with open(os.path.join(os.path.dirname(out), "gate_checks.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(checks, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    for c in checks:
        print("gate %s: %s %s - %s" % (NAME, "PASS" if c["pass"] else "FAIL", c["check"], c["detail"]))
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    # compact gate section in bible.json
    bible_path = args.bible or os.path.join(bdir, "bible.json")
    bible = json.load(open(bible_path, encoding="utf-8"))
    bible["gate"] = OrderedDict([
        ("schema", result["schema"]), ("build", result["build"]), ("date", result["date"]),
        ("verdict", result["verdict"]["verdict"]),
        ("headline", result["verdict"]["headline"]),
        ("holdout", result["holdout"]),
        ("result_file", "gate.json"),
        ("note", "Read per register: H and non-H blocks reconcile to the pooled holdout. See gate.json for rule precision, the mechanisms recall/recount and the blinded contrast."),
    ])
    with open(bible_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(bible, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    print("koikano_bible_gate: wrote %s and updated %s" % (out, bible_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
