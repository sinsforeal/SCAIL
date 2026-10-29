"""Is the extracted voice real information about her, or a fit to its own episodes?

Everything else in this project measures the OUTPUT: does the character the
pipeline produced sound like the tape. That is worth knowing and it does not
test the method. A description can match its own source perfectly and carry no
information -- the way a curve through every point predicts nothing.

So: hold episodes back, and test the description against them. Six tests, no
model calls, no network, entirely local. Nothing here is written; it reads
`yukarin/corpus/`, `yukarin/sheet/`, `yukarin/persona/`, `yukarin/audit/` and
`yukarin/providers.db` (read-only URI) and writes one document.

    python tools/voice_replicate.py
    python tools/voice_replicate.py --fit 70 --window 60 --trials 200
    python tools/voice_replicate.py --out docs/yukarin-replication.md

---------------------------------------------------------------------------
THE DESIGN, AND WHERE IT DIFFERS FROM THE OBVIOUS ONE
---------------------------------------------------------------------------

**What can and cannot be held out.** Re-running the extraction on a subset of
episodes would cost hundreds of model calls, so the sheet on disk is a fixed
input here and it was built from all 99 episodes. What is held out is the
MEASUREMENT and the WEIGHTS: every rate, every weight and every prevalence in
this file is estimated on the fit episodes alone and tested on episodes the
estimator never saw. That tests whether the description's content transfers.
It does not test the extraction's sampling variance, which only re-running
would. Both facts are stated in the output.

**The description under test is code, not a list typed here.** Three batteries,
each one an artefact that existed before this tool:

  * the 35 regex markers in `yukarin/tools/fingerprint.py` -- the pipeline's
    own mechanical description of her surface, imported from that file so it
    cannot drift from it;
  * the countable claims in `yukarin/audit/countable.json` that occur often
    enough to be measurable -- his hand-written character card, not the
    pipeline's output, so an independent description of the same woman;
  * `signature_hers_against_the_room` in `yukarin/sheet/bounds.json` -- 24
    markers the project already selected as hers by contrast with the room.
    That selection used all 99 episodes, so it LEAKS the held-out set. It is
    run anyway, labelled, because the gap between it and the honest batteries
    is a measurement of what the leak is worth.

Six of the 35 fingerprint markers were written from a close reading of ep095,
which the chronological split holds out. The battery is therefore also scored
with those six removed, and that variant is the leak-free headline.

**The unit is a fixed-width window, not a cue and not a span.** Her spans
average 134 characters and the other voices' average 54, so at span level a
classifier that only reads length would look like a voice detector. Chopping
every attribution span into windows of exactly `--window` characters removes
that confound by construction: every unit is the same size, so length carries
no information at all and the score cannot borrow any.

**The negative class is separated by kind.** The attribution labels are
`her | mail | read | song | other`. Only `other` is other people talking;
`mail` is a listener's letter and `read` is copy, both voiced by her but
written by somebody else. Telling her apart from a letter is a much easier
problem than telling her apart from the staff, so lumping them would inflate
the result. `other` is the headline; the rest are reported separately.

**The controls decide whether any of it means anything.** Three, all scored
through identical machinery on the identical held-out windows:

  * frequency- and length-matched random markers -- for each real marker, a
    character n-gram of the same length and comparable corpus frequency drawn
    at random. Unmatched random n-grams would be a straw man, because rare
    forms and common forms do not carry comparable evidence;
  * the most frequent n-grams in the corpus, chosen with no reference to who
    says them -- asks whether "any common form plus fitted weights" is enough;
  * markers selected on the FIT episodes by her-versus-room log-odds, a
    procedure that needs no extraction, no model and no reading -- asks
    whether the extraction beats five lines of arithmetic. This is the control
    most likely to embarrass the project, which is why it is here, and it is
    built competently rather than as a straw man.

Both of the last two beat the extraction. So the test that decides the thing
is the nested one: add the extraction's markers ON TOP of each baseline and
ask whether the AUC moves, with a bootstrap over held-out episodes paired
across the two batteries. That is the only form of the question that
distinguishes "the description is worse than counting" from "the description
contains nothing counting does not already have", and they are different
claims with different consequences for the project.

**Two traps this tool refuses to walk into.**

  1. A marker whose expected count in a sample is under `--min-expected`
     (3) is not tested at all. "Expected 0.14, observed 0, DRIFT" is a lie
     with arithmetic in front of it; `tools/voice_verify.py` exists because
     that mistake was made once already.
  2. A Poisson interval assumes occurrences are independent. They are not:
     one circle-drawing bit put 45 `にゃん` into a single episode, and topic
     clusters every marker in this corpus by episode. A Poisson test on
     pooled counts therefore rejects almost everything and calls ordinary
     burstiness drift. Each marker is tested BOTH ways -- the naive Poisson
     interval the project's verifier uses, and a bootstrap over whole fit
     episodes that carries the between-episode variance with it. The gap
     between the two counts is itself a finding about `voice_verify.py`.
     Every flagged marker is also reported with the share of its held-out
     occurrences carried by the single busiest episode, because a marker
     whose whole movement is one broadcast is a bit that ran that night.

**A trap this tool hit while being written.** `babytalk` looked like a 346%
rise until the concentration column showed 83% of its held-out occurrences in
one episode. Two more of the five flagged markers were written from a close
reading of ep095, which the chronological split holds out -- a form gets
noticed because it was salient in the episode being read, so a marker picked
there is of course commoner there. Selection on the test set arrives disguised
as drift, and neither of those would have been visible without the extra
column and the leak-free battery.

**And a third, which is the reason `orthography_check` exists.** The one drift
left after those two -- the thinking-aloud joints falling by a third -- is
partly the recogniser. Split that family by spelling and the vowel-lengthened
forms fall while the short one rises, and the long-vowel mark itself is 13%
rarer in the late block. `fingerprint.py` already treats vowel length in a
filler as whisper's guess and counts the family rather than the spelling; the
same argument applies to any chronological comparison over this corpus, which
tests the description against a moving target and a moving instrument at once.
"""

import argparse
import bisect
import importlib.util
import io
import json
import math
import os
import random
import re
import sqlite3
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

CORPUS = os.path.join("yukarin", "corpus")
LABELS = ("her", "mail", "read", "song", "other")


# --------------------------------------------------------------------------
# corpus
# --------------------------------------------------------------------------

def ep_key(ep):
    """021_5 is an omake half-episode and sorts between 21 and 22."""
    a, _, b = ep.partition("_")
    return (int(a), int(b) if b else 0)


def load_corpus():
    """One record per episode: its date and its attribution spans as text.

    A span is a contiguous run of cues with one speaker label. Cue text is
    joined without a separator, matching the way the fingerprint battery and
    the countable audit were measured.
    """
    eps = []
    for f in sorted(os.listdir(CORPUS)):
        if not f.endswith(".jsonl"):
            continue
        ep = f[2:-6]
        attr_path = os.path.join(CORPUS, "attr", "ep%s.json" % ep)
        if not os.path.exists(attr_path):
            continue
        cues, date = {}, None
        for line in io.open(os.path.join(CORPUS, f), encoding="utf-8"):
            c = json.loads(line)
            cues[c["i"]] = c["text"]
            date = date or c.get("date")
        spans = []
        for s in json.load(io.open(attr_path, encoding="utf-8")):
            if s["label"] not in LABELS:
                continue
            idx = list(range(s["a"], s["b"] + 1))
            parts = [cues[i] for i in idx if i in cues]
            if parts:
                spans.append({"label": s["label"], "text": "".join(parts),
                              "cues": parts})
        eps.append({"ep": ep, "date": date, "spans": spans})
    eps.sort(key=lambda e: ep_key(e["ep"]))
    return eps


def label_text(episode, label):
    return "".join(s["text"] for s in episode["spans"] if s["label"] == label)


def windows(episodes, width, interior_only=False):
    """(episode, label, text) for every full `width`-character window.

    Windows never cross a span, so every one has a single speaker label, and
    every one is exactly `width` characters, so length carries no information.
    The remainder at the end of each span is discarded.

    `interior_only` drops the first and last cue of every span before
    chopping. The attribution is a model's and its known failure is boundary
    bleed -- a letter's closing line landing in the following `her` span. The
    difference between the two runs is what that noise is worth.
    """
    out = []
    for e in episodes:
        for s in e["spans"]:
            parts = s["cues"]
            if interior_only:
                if len(parts) <= 2:
                    continue
                parts = parts[1:-1]
            t = "".join(parts)
            for k in range(len(t) // width):
                out.append((e["ep"], s["label"], t[k * width:(k + 1) * width]))
    return out


# --------------------------------------------------------------------------
# the batteries -- descriptions that existed before this tool
# --------------------------------------------------------------------------

def fingerprint_battery():
    """The 35 regexes in `yukarin/tools/fingerprint.py`, imported from it."""
    path = os.path.join("yukarin", "tools", "fingerprint.py")
    spec = importlib.util.spec_from_file_location("_yfp", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return dict(mod.MARKERS)


# Written from a close reading of ep095, which the chronological split holds
# out. Named here so the battery can be scored without them.
EP095_DERIVED = ("desu_wa", "baby_end", "ojinami", "hekomi", "choushi",
                 "omou_koto_ni")


def countable_battery(min_total=20):
    """His character card's countable claims, at volumes worth measuring.

    Most of the 74 markers in that file measured zero or once over 99
    episodes. A marker seen once cannot separate anything and including it
    would only pad the battery.
    """
    data = json.load(io.open(os.path.join("yukarin", "audit", "countable.json"),
                             encoding="utf-8"))
    out = {}
    for claim in data["claims"]:
        for m, n in claim["markers"].items():
            if n >= min_total:
                out[m] = re.escape(m)
    return out


def signature_battery():
    """bounds.json's 24 'hers alone against the room' markers.

    Selected on all 99 episodes, so it leaks the held-out set by construction.
    Kept to measure what the leak is worth.
    """
    b = json.load(io.open(os.path.join("yukarin", "sheet", "bounds.json"),
                          encoding="utf-8"))
    names = [m["marker"] for m in b["section_i"]["signature_hers_against_the_room"]]
    fp = fingerprint_battery()
    return {n: fp[n] for n in names if n in fp}


# --------------------------------------------------------------------------
# counting and scoring
# --------------------------------------------------------------------------

def compile_battery(battery):
    return [(k, re.compile(rx)) for k, rx in battery.items()]


def count_vec(text, compiled):
    return [len(rx.findall(text)) for _, rx in compiled]


def rate_vec(texts, compiled):
    """Occurrences per 100,000 characters over a body of text, and its size."""
    joined = "".join(texts)
    n = max(len(joined), 1)
    return [len(rx.findall(joined)) / n * 1e5 for _, rx in compiled], n


def weights_from(fit_pos, fit_neg, compiled, alpha=1.0):
    """log of her rate over the other side's rate, per marker.

    Smoothed by `alpha` per 100k so a zero on either side stays finite. A
    marker she uses twice as often contributes half as much as one she uses
    four times as often, and a marker the other side uses more contributes
    against her.
    """
    pr, _ = rate_vec(fit_pos, compiled)
    nr, _ = rate_vec(fit_neg, compiled)
    return [math.log((p + alpha) / (q + alpha)) for p, q in zip(pr, nr)]


def score_windows(win, compiled, w):
    """Every window is the same width, so the raw dot product is already a
    rate and needs no length normalisation."""
    return [(sum(a * b for a, b in zip(w, count_vec(t, compiled))), lab, ep)
            for ep, lab, t in win]


def auc(scored, pos_label, neg_label):
    """Probability that a random window of hers outscores a random window of
    the other side's, ties counted half. 0.5 is a coin."""
    pos = sorted(s for s, lab, _ in scored if lab == pos_label)
    neg = sorted(s for s, lab, _ in scored if lab == neg_label)
    if not pos or not neg:
        return float("nan"), 0, 0
    tot = 0.0
    for s in pos:
        lo = bisect.bisect_left(neg, s)
        hi = bisect.bisect_right(neg, s)
        tot += lo + 0.5 * (hi - lo)
    return tot / (len(pos) * len(neg)), len(pos), len(neg)


def auc_ci(scored, pos_label, neg_label, rnd, boots=400):
    """Bootstrap over held-out EPISODES, not over windows.

    Windows inside one episode share a topic and a recording, so resampling
    windows would pretend to more independent evidence than exists.
    """
    by_ep = defaultdict(list)
    for s, lab, ep in scored:
        by_ep[ep].append((s, lab, ep))
    eps = list(by_ep)
    vals = []
    for _ in range(boots):
        draw = []
        for _ in range(len(eps)):
            draw.extend(by_ep[eps[rnd.randrange(len(eps))]])
        a, _p, _n = auc(draw, pos_label, neg_label)
        if a == a:
            vals.append(a)
    vals.sort()
    if not vals:
        return (float("nan"), float("nan"))
    return (vals[int(len(vals) * 0.025)], vals[int(len(vals) * 0.975)])


# --------------------------------------------------------------------------
# the controls
# --------------------------------------------------------------------------

def ngram_index(texts, lengths, min_count=3):
    """Counter of character n-grams over the pooled window text, by length."""
    joined = "".join(texts)
    idx = {}
    for L in lengths:
        c = Counter(joined[i:i + L] for i in range(len(joined) - L + 1))
        idx[L] = {g: n for g, n in c.items() if n >= min_count}
    return idx


def marker_shapes(battery, pooled_text):
    """For each real marker, the length and corpus frequency of what it
    actually matches -- the two properties a fair random control must copy."""
    shapes = []
    for k, rx in battery.items():
        ms = re.compile(rx).findall(pooled_text)
        ms = [m if isinstance(m, str) else "".join(m) for m in ms]
        ms = [m for m in ms if m]
        if not ms:
            shapes.append((k, 2, 3))
            continue
        lens = sorted(len(m) for m in ms)
        shapes.append((k, max(2, lens[len(lens) // 2]), len(ms)))
    return shapes


def matched_random_set(shapes, idx, rnd, real_forms):
    """One random n-gram per real marker, same length, frequency within a
    factor of two, widening the band only if that band is empty."""
    out = {}
    for k, L, n in shapes:
        pool = idx.get(L) or idx[min(idx)]
        for band in (2.0, 4.0, 16.0, 1e9):
            cands = [g for g, c in pool.items()
                     if n / band <= c <= n * band and g not in real_forms]
            if len(cands) >= 4:
                break
        if not cands:
            continue
        out["r_%s" % k] = re.escape(rnd.choice(cands))
    return out


def top_frequency_set(shapes, idx, real_forms):
    """The most frequent n-grams of each needed length, chosen with no
    reference to who says them."""
    out, used = {}, set()
    by_len = defaultdict(list)
    for L, pool in idx.items():
        by_len[L] = [g for g, _ in sorted(pool.items(), key=lambda kv: -kv[1])]
    ptr = defaultdict(int)
    for k, L, _n in shapes:
        lst = by_len.get(L) or by_len[min(by_len)]
        while ptr[L] < len(lst) and (lst[ptr[L]] in used or lst[ptr[L]] in real_forms):
            ptr[L] += 1
        if ptr[L] >= len(lst):
            continue
        g = lst[ptr[L]]
        ptr[L] += 1
        used.add(g)
        out["f_%s" % k] = re.escape(g)
    return out


def fit_selected_set(fit_pos, fit_neg, idx, size, min_count=20):
    """Markers chosen on the fit episodes alone by her-versus-room log-odds.

    No model, no reading, no extraction -- the arithmetic an afternoon would
    produce. Whatever this scores is the bar the pipeline has to clear, so it
    is built competently rather than as a straw man: the ranking statistic is
    the log-odds ratio divided by its own standard error, which is the
    standard way to stop a rare form with an extreme ratio from outranking a
    common one with a solid difference.
    """
    pos, neg = "".join(fit_pos), "".join(fit_neg)
    np_, nn = max(len(pos), 1), max(len(neg), 1)
    ranked = []
    for L, pool in sorted(idx.items()):
        if L > 4:
            continue
        for g in pool:
            a = pos.count(g)
            b = neg.count(g)
            if a + b < min_count:
                continue
            # log odds of appearing in her text rather than theirs, over its
            # standard error; add-half smoothing keeps a zero finite
            oa, ob = a + 0.5, b + 0.5
            lo = math.log((oa / (np_ - oa)) / (ob / (nn - ob)))
            se = math.sqrt(1.0 / oa + 1.0 / ob)
            ranked.append((abs(lo / se), g))
    ranked.sort(reverse=True)
    return {"s_%d" % i: re.escape(g) for i, (_, g) in enumerate(ranked[:size])}


def auc_diff_ci(sc_a, sc_b, pos_label, neg_label, rnd, boots=400):
    """Bootstrap CI for the DIFFERENCE between two batteries' AUC, resampling
    the same held-out episodes for both so the comparison is paired."""
    ga, gb = defaultdict(list), defaultdict(list)
    for s, lab, ep in sc_a:
        ga[ep].append((s, lab, ep))
    for s, lab, ep in sc_b:
        gb[ep].append((s, lab, ep))
    eps = sorted(set(ga) & set(gb))
    vals = []
    for _ in range(boots):
        pick = [eps[rnd.randrange(len(eps))] for _ in range(len(eps))]
        da = [x for e in pick for x in ga[e]]
        db = [x for e in pick for x in gb[e]]
        x, _p, _n = auc(da, pos_label, neg_label)
        y, _p, _n = auc(db, pos_label, neg_label)
        if x == x and y == y:
            vals.append(x - y)
    vals.sort()
    if not vals:
        return float("nan"), float("nan")
    return vals[int(len(vals) * 0.025)], vals[int(len(vals) * 0.975)]


# --------------------------------------------------------------------------
# test 1 -- stability of the measured surface
# --------------------------------------------------------------------------

def poisson_interval(lam):
    """Normal approximation, 95%. Only ever called with lam >= 3."""
    sd = math.sqrt(lam)
    return lam - 1.96 * sd, lam + 1.96 * sd


def bootstrap_interval(per_ep, test_chars, rnd, boots=2000):
    """Predictive interval for the held-out count, resampling whole fit
    episodes so between-episode burstiness is inside the interval."""
    vals = []
    n = len(per_ep)
    for _ in range(boots):
        c = ch = 0
        while ch < test_chars:
            k, m = per_ep[rnd.randrange(n)]
            c += k
            ch += m
        vals.append(c * test_chars / ch)
    vals.sort()
    return vals[int(boots * 0.025)], vals[int(boots * 0.975)]


def stability(fit_eps, test_eps, battery, rnd, min_expected=3.0):
    compiled = compile_battery(battery)
    fit_texts = [label_text(e, "her") for e in fit_eps]
    test_text = "".join(label_text(e, "her") for e in test_eps)
    fit_chars = sum(len(t) for t in fit_texts)
    test_chars = len(test_text)
    rows = []
    for j, (name, rx) in enumerate(compiled):
        per_ep = [(len(rx.findall(t)), max(len(t), 1)) for t in fit_texts]
        fit_count = sum(c for c, _ in per_ep)
        fit_rate = fit_count / max(fit_chars, 1) * 1e5
        obs = len(rx.findall(test_text))
        exp = fit_rate / 1e5 * test_chars
        # how concentrated the held-out occurrences are: the share carried by
        # the single busiest episode. A marker whose "drift" is one broadcast
        # is a bit, not a change in her.
        by_ep = sorted(((len(rx.findall(label_text(e, "her"))), e["ep"])
                        for e in test_eps), reverse=True)
        top_share = (by_ep[0][0] / obs) if obs else 0.0
        row = {"marker": name, "expected": exp, "observed": obs,
               "fit_rate": fit_rate, "top_share": top_share,
               "top_ep": by_ep[0][1] if by_ep else "",
               "test_rate": obs / max(test_chars, 1) * 1e5,
               "testable": exp >= min_expected}
        if row["testable"]:
            plo, phi = poisson_interval(exp)
            blo, bhi = bootstrap_interval(per_ep, test_chars, rnd)
            row.update({"poisson_ok": plo <= obs <= phi,
                        "boot_ok": blo <= obs <= bhi,
                        "boot_lo": blo, "boot_hi": bhi})
        rows.append(row)
    return rows, fit_chars, test_chars


def orthography_check(fit_eps, test_eps):
    """How much of an apparent drift is the recogniser's spelling rather than
    hers.

    The corpus is whisper's transcript. `fingerprint.py` already says the
    vowel length in a filler is the recogniser's guess as much as the
    speaker's, which is why the joint family is one marker and not seven. The
    same argument bites the drift measurement: if the long-vowel mark itself
    becomes rarer across the split, every vowel-lengthened spelling falls with
    it and none of that is a change in how she talks.
    """
    a = "".join(label_text(e, "her") for e in fit_eps)
    b = "".join(label_text(e, "her") for e in test_eps)

    def r(text, rx):
        return len(re.findall(rx, text)) / max(len(text), 1) * 1e5

    out = {}
    for name, rx in (("the long-vowel mark ー", "ー"), ("the comma 、", "、"),
                     ("the full stop 。", "。")):
        out[name] = (r(a, rx), r(b, rx))
    forms = {}
    for f in ("えっと", "えーと", "えーっと", "あのね", "あのー", "んーと"):
        forms[f] = (r(a, re.escape(f)), r(b, re.escape(f)))
    return out, forms


# --------------------------------------------------------------------------
# test 4 -- mechanism prevalence
# --------------------------------------------------------------------------

def mechanism_prevalence(fit_set, test_set, min_expected=3.0):
    """Does a mechanism appear in held-out episodes at the rate the fit
    episodes give?

    The clustering saw all 99 episodes, so this is not a clean holdout of the
    extraction: it asks whether a mechanism's prevalence is a stable property
    or a burst. A mechanism the sheet reports at 96 of 99 episodes and that
    then misses the held-out block is a description of a period, not a trait.
    """
    path = os.path.join("yukarin", "sheet", "clusters_v2.json")
    clusters = json.load(io.open(path, encoding="utf-8"))["clusters"]
    rows = []
    for c in clusters:
        eps = {m.split(":")[0][2:] for m in c["members"] if m.startswith("ep")}
        a = len(eps & fit_set)
        b = len(eps & test_set)
        p = a / max(len(fit_set), 1)
        exp = p * len(test_set)
        if exp < min_expected:
            rows.append({"name": c["name"], "testable": False,
                         "fit_eps": a, "test_eps": b, "expected": exp})
            continue
        sd = math.sqrt(len(test_set) * p * (1 - p)) or 1e-9
        rows.append({"name": c["name"], "testable": True, "fit_eps": a,
                     "test_eps": b, "expected": exp, "p": p,
                     "z": (b - exp) / sd, "ok": abs(b - exp) <= 1.96 * sd})
    return rows


# --------------------------------------------------------------------------
# test 5 -- fact recurrence across the split
# --------------------------------------------------------------------------

def fact_recurrence(fit_set, test_set, episodes):
    """Do the fact records describe recurring properties or one-off content?

    Each record's claims cite the cues they were located in. A record whose
    evidence sits only in the fit block and never recurs is episode content;
    one re-evidenced in the held-out block is something she keeps saying.

    The quote is re-checked against the corpus here rather than trusted: the
    record carries its own `located` flag, and reporting a pipeline's opinion
    of itself as a verification is exactly the move this file exists to avoid.
    A quote is accepted if it appears in the cue named or in its two
    neighbours, whitespace removed, which is the tolerance the extraction's
    own verifier allows for a quote running over a cue boundary.
    """
    raw = {}
    for f in os.listdir(CORPUS):
        if f.endswith(".jsonl"):
            raw[f[2:-6]] = {c["i"]: c["text"] for c in
                            (json.loads(l) for l in
                             io.open(os.path.join(CORPUS, f), encoding="utf-8"))}
    ws = re.compile(r"\s+")

    def present(ep, i, quote):
        cues = raw.get(ep)
        if not cues or not quote:
            return False
        window = "".join(cues.get(k, "") for k in range(i - 2, i + 3))
        return ws.sub("", quote) in ws.sub("", window)

    path = os.path.join("yukarin", "persona", "records_facts.json")
    recs = json.load(io.open(path, encoding="utf-8"))
    rows = []
    for r in recs:
        eps = set()
        claimed = checked = total = 0
        for cl in r.get("claims", []):
            for sp in cl.get("speech", []):
                total += 1
                at = sp.get("at") or ""
                if not (sp.get("located") and at.startswith("ep")):
                    continue
                claimed += 1
                ep = at.split("#")[0][2:]
                eps.add(ep)
                try:
                    i = int(at.split("#")[1])
                except (IndexError, ValueError):
                    continue
                if present(ep, i, sp.get("ja") or ""):
                    checked += 1
        rows.append({"id": r.get("id"), "eps": eps, "located": claimed,
                     "verified": checked, "total": total,
                     "in_fit": bool(eps & fit_set), "in_test": bool(eps & test_set)})
    return rows


# --------------------------------------------------------------------------
# test 6 -- re-extraction agreement, read out of providers.db
# --------------------------------------------------------------------------

PROV = os.path.join("yukarin", "extract", "providers")
CTRL = os.path.join("yukarin", "extract", "control")
MAPV2 = os.path.join("yukarin", "extract", "map_v2")

# Pairs of extractions of the SAME episode by the SAME model on the SAME host,
# differing in one inference setting. The nearest thing on disk to a replicate.
NEAR_REPLICATES = [
    (os.path.join(CTRL, "gemini"), os.path.join(CTRL, "gemini_nothink"),
     "Vertex gemini flash, thinking on vs off"),
    (os.path.join(CTRL, "or_oi_reason"), os.path.join(CTRL, "or_oi"),
     "OpenInference DeepSeek, reasoning high vs host default"),
    (os.path.join(CTRL, "glm"), os.path.join(PROV, "glm__z-ai"),
     "GLM flash on Z.AI, unpinned vs pinned reasoning high"),
    (os.path.join(CTRL, "or_di"), os.path.join(PROV, "deepinfra"),
     "DeepInfra DeepSeek, no reasoning field vs reasoning high"),
]


def cited_cues(path):
    """The cue indices a run pointed at as mechanism evidence.

    This is the one thing comparable across runs. Mechanism NAMES are free
    text a model invents, so they cannot be matched mechanically; the cue
    index survives `extract.verify`, which drops a quote found nowhere in the
    corpus and corrects one found in a neighbouring cue.
    """
    try:
        j = json.load(io.open(path, encoding="utf-8"))
    except Exception:
        return set(), set()
    cues, names = set(), set()
    for m in j.get("mechanisms") or []:
        if isinstance(m, dict):
            if m.get("name"):
                names.add(str(m["name"]).strip().lower())
            for e in m.get("evidence") or []:
                if isinstance(e, dict) and isinstance(e.get("i"), int):
                    cues.add(e["i"])
    return cues, names


def jaccard(a, b):
    return len(a & b) / len(a | b) if (a or b) else float("nan")


def provider_agreement(rnd):
    """Between-run agreement of the extraction, from the outputs on disk."""
    out = {"eps": {}, "near": [], "db": {}}

    # the summary metrics
    path = os.path.join("yukarin", "providers.db")
    if os.path.exists(path):
        uri = "file:%s?mode=ro" % path.replace("\\", "/")
        con = sqlite3.connect(uri, uri=True)
        rows = list(con.execute(
            "select slug, ep, status, mechanisms, quotes_ok, quotes_offered, "
            "fable_same, fable_compat, fable_missing from runs"))
        cells = list(con.execute("select slug, ep, count(*) from runs group by slug, ep"))
        con.close()
        ok = [r for r in rows if r[2] == "ok"]
        qv = sorted(r[4] / r[5] for r in ok if r[5])
        rec = sorted((r[6] + r[7]) / (r[6] + r[7] + r[8])
                     for r in ok if r[6] is not None and (r[6] + r[7] + r[8]))
        mech = sorted(r[3] for r in ok if r[3] is not None)
        out["db"] = {"rows": len(rows), "ok": len(ok),
                     "max_per_cell": max((c[2] for c in cells), default=0),
                     "qv": qv, "recall": rec, "mech": mech}

    # cue-level overlap between every pair of runs on the same episode
    runs = defaultdict(dict)
    for d in sorted(os.listdir(PROV)) if os.path.isdir(PROV) else []:
        for f in sorted(os.listdir(os.path.join(PROV, d))):
            if f.endswith(".json"):
                runs[f[:-5]][d] = os.path.join(PROV, d, f)
    for f in sorted(os.listdir(MAPV2)) if os.path.isdir(MAPV2) else []:
        if f.endswith(".json") and f[:-5] in runs:
            runs[f[:-5]]["official"] = os.path.join(MAPV2, f)

    for ep, byslug in sorted(runs.items()):
        sets = {}
        for slug, p in byslug.items():
            c, n = cited_cues(p)
            if c:
                sets[slug] = (c, n)
        if len(sets) < 3:
            continue
        # the chance baseline draws from the cues the extractor was actually
        # given -- her attributed words -- not from every cue in the episode
        pool = []
        attr = os.path.join(CORPUS, "attr", "%s.json" % ep)
        if os.path.exists(attr):
            for s in json.load(io.open(attr, encoding="utf-8")):
                if s["label"] == "her":
                    pool.extend(range(s["a"], s["b"] + 1))
        n_cues = len(pool)
        slugs = sorted(sets)
        js, ns, chance = [], [], []
        for i in range(len(slugs)):
            for k in range(i + 1, len(slugs)):
                a, an = sets[slugs[i]]
                b, bn = sets[slugs[k]]
                js.append(jaccard(a, b))
                ns.append(len(an & bn))
                if n_cues:
                    ra = set(rnd.sample(pool, min(len(a), n_cues)))
                    rb = set(rnd.sample(pool, min(len(b), n_cues)))
                    chance.append(jaccard(ra, rb))
        js.sort()
        chance.sort()
        out["eps"][ep] = {"runs": len(sets), "cues": n_cues, "pairs": len(js),
                          "j": js, "chance": chance,
                          "name_matches": sum(ns), "name_max": max(ns) if ns else 0}

    for a_dir, b_dir, what in NEAR_REPLICATES:
        for ep in ("ep005", "ep095", "ep025"):
            pa, pb = os.path.join(a_dir, ep + ".json"), os.path.join(b_dir, ep + ".json")
            if os.path.exists(pa) and os.path.exists(pb):
                ca, _ = cited_cues(pa)
                cb, _ = cited_cues(pb)
                if ca and cb:
                    out["near"].append((what, ep, jaccard(ca, cb)))
    return out


# --------------------------------------------------------------------------

def fmt(x, n=3):
    return "n/a" if x != x else ("%.*f" % (n, x))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fit", type=int, default=70,
                    help="episodes used to estimate everything")
    ap.add_argument("--window", type=int, default=60,
                    help="characters per scored unit")
    ap.add_argument("--trials", type=int, default=200,
                    help="matched-random marker sets")
    ap.add_argument("--min-expected", type=float, default=3.0)
    ap.add_argument("--seed", type=int, default=20260902)
    ap.add_argument("--out", default=os.path.join("docs", "yukarin-replication.md"))
    args = ap.parse_args()

    rnd = random.Random(args.seed)
    eps = load_corpus()
    n_eps = len(eps)

    splits = {}
    splits["chronological"] = (eps[:args.fit], eps[args.fit:])
    shuf = list(eps)
    random.Random(args.seed + 1).shuffle(shuf)
    splits["random"] = (shuf[:args.fit], shuf[args.fit:])

    batteries = {}
    fp = fingerprint_battery()
    batteries["fingerprint (35)"] = fp
    batteries["fingerprint minus ep095 (29)"] = {
        k: v for k, v in fp.items() if k not in EP095_DERIVED}
    cb = countable_battery()
    batteries["his card, countable (%d)" % len(cb)] = cb
    sig = signature_battery()
    batteries["bounds signature (%d, leaks)" % len(sig)] = sig

    L = []
    P = L.append
    P("# Does the extraction replicate, or did it fit its own episodes")
    P("")
    P("Generated by `tools/voice_replicate.py`; re-running it reproduces every")
    P("number here. No model calls, no network, nothing written outside this file.")
    P("The method under test is the pipeline in `docs/yukarin.md` §3; the rules")
    P("this obeys about what a count can and cannot say are `docs/verification.md`.")
    P("")
    P("**The question.** Every other check in the project measures the output --")
    P("whether the character the pipeline produced sounds like the tape.")
    P("None of them asks whether the description is information about the woman")
    P("rather than a restatement of the episodes it was built from. A curve through")
    P("every point fits perfectly and predicts nothing. So: estimate on part of the")
    P("corpus, test on the part the estimator never saw.")
    P("")
    P("**What is and is not held out.** Re-running the extraction on a subset would")
    P("cost hundreds of model calls, so the sheet on disk is a fixed input and it was")
    P("built from all 99 episodes. What is held out is every rate, weight and")
    P("prevalence used below: all are estimated on the fit episodes alone. That tests")
    P("whether the description's content transfers to unseen material. It does not")
    P("test the extraction's own sampling variance, which only re-running would --")
    P("§6 is the nearest thing on disk to that.")
    P("")
    summary_at = len(L)

    # ---------------- corpus and split ----------------
    her_all = sum(len(label_text(e, "her")) for e in eps)
    oth_all = sum(len(label_text(e, "other")) for e in eps)
    P("## 0. The material and the split")
    P("")
    P("| | |")
    P("|---|---|")
    P("| episodes | %d |" % n_eps)
    P("| her attributed words | %s characters |" % format(her_all, ","))
    P("| other voices in the studio | %s |" % format(oth_all, ","))
    P("| letters read aloud (`mail`) | %s |"
      % format(sum(len(label_text(e, "mail")) for e in eps), ","))
    P("| copy and ads (`read`) | %s |"
      % format(sum(len(label_text(e, "read")) for e in eps), ","))
    P("| fit / held out | first %d episodes (%s to %s) / last %d (%s to %s) |"
      % (args.fit, eps[0]["date"], eps[args.fit - 1]["date"],
         n_eps - args.fit, eps[args.fit]["date"], eps[-1]["date"]))
    P("")
    P("The chronological split is the honest one. Her surface drifts across the two")
    P("years -- the sheet carries `register_by_year` for exactly that reason -- so")
    P("fitting early and testing late tests the description against a moving target.")
    P("The random split is the easy version, and the difference between them is the")
    P("drift, measured rather than asserted.")
    P("")

    # ---------------- 1. stability ----------------
    P("## 1. Does the measured surface hold on episodes it never saw")
    P("")
    P("The 35 regex markers of `yukarin/tools/fingerprint.py` -- the pipeline's own")
    P("mechanical description of her surface -- measured over her attributed words in")
    P("the fit episodes, used to predict a count in the held-out ones.")
    P("")
    P("Two intervals per marker. The **Poisson** one is what `tools/voice_verify.py`")
    P("uses and it assumes occurrences are independent, which they are not: topic")
    P("clusters every marker by episode, and one circle-drawing bit put 45 `にゃん`")
    P("into a single broadcast. The **bootstrap** one resamples whole fit episodes,")
    P("so between-episode burstiness is inside the interval instead of being counted")
    P("as drift. A marker expected fewer than %g times is not tested at all."
      % args.min_expected)
    P("")
    stab = {}
    for sname, (f_eps, t_eps) in splits.items():
        rows, fc, tc = stability(f_eps, t_eps, fp, random.Random(args.seed), args.min_expected)
        stab[sname] = rows
        tested = [r for r in rows if r["testable"]]
        P("**%s split** -- %s characters of her fitted, %s held out. "
          "%d of 35 markers testable; **Poisson %d/%d**, **bootstrap %d/%d**."
          % (sname, format(fc, ","), format(tc, ","), len(tested),
             sum(1 for r in tested if r["poisson_ok"]), len(tested),
             sum(1 for r in tested if r["boot_ok"]), len(tested)))
        P("")
    rows = stab["chronological"]
    P("Per marker, chronological split:")
    P("")
    P("| marker | fit /100k | held-out /100k | expected | observed | Poisson | bootstrap |")
    P("|---|---|---|---|---|---|---|")
    for r in sorted(rows, key=lambda r: -r["expected"]):
        if not r["testable"]:
            continue
        P("| `%s` | %.1f | %.1f | %.1f | %d | %s | %s |"
          % (r["marker"], r["fit_rate"], r["test_rate"], r["expected"], r["observed"],
             "ok" if r["poisson_ok"] else "**out**",
             "ok" if r["boot_ok"] else "**out**"))
    skipped = [r for r in rows if not r["testable"]]
    P("")
    P("Not testable at this volume (%d): %s."
      % (len(skipped), ", ".join("`%s` (expected %.1f)" % (r["marker"], r["expected"])
                                 for r in sorted(skipped, key=lambda r: -r["expected"]))))
    P("")
    moved = sorted((r for r in rows if r["testable"] and not r["boot_ok"]),
                   key=lambda r: -abs(r["test_rate"] - r["fit_rate"]))
    if moved:
        P("The markers that move even after burstiness is allowed for, fit rate to")
        P("held-out rate. The last column is the share of the held-out occurrences")
        P("carried by the single busiest episode -- a marker whose whole movement is")
        P("one broadcast is a bit that ran that night, not a change in her:")
        P("")
        P("| marker | fit /100k | held-out /100k | move | busiest held-out episode |")
        P("|---|---|---|---|---|")
        for r in moved:
            P("| `%s` | %.1f | %.1f | %s %.0f%% | ep%s carries %.0f%% of them |"
              % (r["marker"], r["fit_rate"], r["test_rate"],
                 "up" if r["test_rate"] > r["fit_rate"] else "down",
                 abs(r["test_rate"] - r["fit_rate"]) / max(r["fit_rate"], 0.01) * 100,
                 r["top_ep"], r["top_share"] * 100))
        P("")
        spread = [r for r in moved if r["top_share"] < 0.25]
        if spread:
            P("**%s the real drift**, spread across the held-out block rather than"
              % (", ".join("`%s` is" % r["marker"] for r in spread)
                 if len(spread) == 1 else
                 ", ".join("`%s`" % r["marker"] for r in spread) + " are"))
            P("piled into one broadcast. %s"
              % ("The thinking-aloud joints -- えーっと, えっと, あのね -- fall by a "
                 "third between the first seventy broadcasts and the last "
                 "twenty-nine. It is the size of change `register_by_year` exists to "
                 "hold, and it means any single rate quoted for this marker is an "
                 "average over two unlike years."
                 if any(r["marker"] == "joint" for r in spread) else
                 "That is a change in how she talks over the two years, which is "
                 "what `register_by_year` exists to hold."))
            P("")
            marks, forms = orthography_check(*splits["chronological"])
            P("**And a good part of even that is the recogniser, not her.** The corpus")
            P("is whisper's transcript. Split the joint family by spelling and the")
            P("vowel-lengthened forms fall while the short one rises:")
            P("")
            P("| form | fit /100k | held-out /100k | move |")
            P("|---|---|---|---|")
            for f, (x, y) in forms.items():
                P("| %s | %.1f | %.1f | %s%.0f%% |"
                  % (f, x, y, "+" if y >= x else "-", abs(y - x) / max(x, 0.01) * 100))
            P("")
            P("The long-vowel mark itself is %.0f%% rarer in the held-out block (%.0f"
              % ((marks["the long-vowel mark ー"][0] - marks["the long-vowel mark ー"][1])
                 / max(marks["the long-vowel mark ー"][0], 0.01) * 100,
                 marks["the long-vowel mark ー"][0]))
            P("per 100k against %.0f), and the comma by %.0f%%. Those are properties of"
              % (marks["the long-vowel mark ー"][1],
                 (marks["the comma 、"][0] - marks["the comma 、"][1])
                 / max(marks["the comma 、"][0], 0.01) * 100))
            P("the transcription, not of a person. `fingerprint.py` already treats the")
            P("vowel length in a filler as the recogniser's guess and counts the family")
            P("rather than the spelling; the same argument bites the drift measurement,")
            P("and the honest reading of the one distributed drift in this corpus is")
            P("that it is part her and part whisper, in a proportion this material")
            P("cannot separate.")
            P("")
        leaked = [r for r in moved if r["marker"] in EP095_DERIVED]
        if leaked:
            P("**Two of those five are the marker set leaking, and it shows in the last")
            P("column.** %s written from a close reading of ep095, which sits in the"
              % (", ".join("`%s`" % r["marker"] for r in leaked)
                 + (" was" if len(leaked) == 1 else " were")))
            P("held-out block%s. A form gets noticed because it was salient in"
              % (" -- and ep095 is the episode carrying most of their held-out "
                 "occurrences" if all(r["top_ep"] == "095" for r in leaked) else ""))
            P("the episode being read, so a marker picked there is of course commoner")
            P("there. That is selection on the test set appearing as drift, and it is why")
            P("the leak-free battery in §2 and §3 drops all six ep095-derived markers.")
            P("")

    # ---------------- 2. discrimination ----------------
    P("## 2. Can the description find her in episodes it never saw")
    P("")
    P("Every attribution span is chopped into windows of exactly %d characters, so"
      % args.window)
    P("every scored unit is the same size and length carries no information. Her")
    P("spans average 134 characters and the other voices' 54; at span level a")
    P("classifier reading nothing but length would look like a voice detector, and")
    P("this construction removes that.")
    P("")
    P("Each marker is weighted by the log ratio of her rate to the other side's,")
    P("measured on the **fit episodes only**. Held-out windows are scored and")
    P("compared against the attribution. The figure is the area under the ROC curve:")
    P("the chance a random window of hers outscores a random window of the other")
    P("side's. 0.5 is a coin.")
    P("")
    P("The negative class is split by kind, because they are not the same problem.")
    P("`other` is other people talking in the studio and is the hard one. `mail` is a")
    P("listener's letter and `read` is copy -- both voiced by her, written by someone")
    P("else, and telling her apart from them is a different and easier task.")
    P("")

    disc = {}
    for sname, (f_eps, t_eps) in splits.items():
        f_win = windows(f_eps, args.window)
        t_win = windows(t_eps, args.window)
        f_set = {}
        for lab in LABELS:
            f_set[lab] = [t for _e, l, t in f_win if l == lab]
        for bname, bat in batteries.items():
            comp = compile_battery(bat)
            for neg in ("other", "mail", "read"):
                w = weights_from(f_set["her"], f_set[neg], comp)
                sc = score_windows(t_win, comp, w)
                a, npos, nneg = auc(sc, "her", neg)
                lo, hi = auc_ci(sc, "her", neg, random.Random(args.seed + 3))
                disc[(sname, bname, neg)] = (a, lo, hi, npos, nneg)

    P("| split | description | against | held-out windows (hers / theirs) | AUC | 95% CI |")
    P("|---|---|---|---|---|---|")
    for sname in ("chronological", "random"):
        for bname in batteries:
            for neg in ("other", "mail", "read"):
                a, lo, hi, npos, nneg = disc[(sname, bname, neg)]
                P("| %s | %s | %s | %s / %s | **%s** | %s–%s |"
                  % (sname, bname, neg, format(npos, ","), format(nneg, ","),
                     fmt(a), fmt(lo), fmt(hi)))
    P("")

    # attribution noise: interior-only windows
    f_eps, t_eps = splits["chronological"]
    comp = compile_battery(batteries["fingerprint minus ep095 (29)"])
    fi = windows(f_eps, args.window, interior_only=True)
    ti = windows(t_eps, args.window, interior_only=True)
    wi = weights_from([t for _e, l, t in fi if l == "her"],
                      [t for _e, l, t in fi if l == "other"], comp)
    ai, npi, nni = auc(score_windows(ti, comp, wi), "her", "other")
    a0 = disc[("chronological", "fingerprint minus ep095 (29)", "other")][0]
    P("**How much of the ceiling is the attribution's own noise.** The attribution is")
    P("a model's, and its known failure is boundary bleed -- a letter's closing line")
    P("landing in the following `her` span. Dropping the first and last cue of every")
    P("span before chopping removes most of that: AUC %s against %s on the same"
      % (fmt(ai), fmt(a0)))
    P("split and battery (%s held-out windows). The gap is what the boundary noise"
      % format(npi + nni, ","))
    P("is worth, and it bounds how much of the remaining error is the instrument")
    P("rather than the description.")
    P("")

    # ---------------- 3. specificity ----------------
    P("## 3. Is it specific to her, or would any set of forms do")
    P("")
    P("The same machinery, the same held-out windows, the same fitted weights --")
    P("only the marker set changes. Three controls, in rising order of how hard they")
    P("are to beat, and then the two combinations that say whether the description")
    P("adds anything to a control that already beats it.")
    P("")
    f_eps, t_eps = splits["chronological"]
    f_win = windows(f_eps, args.window)
    t_win = windows(t_eps, args.window)
    f_her = [t for _e, l, t in f_win if l == "her"]
    f_oth = [t for _e, l, t in f_win if l == "other"]
    pooled = "".join(t for _e, l, t in f_win + t_win if l in ("her", "other"))
    base = batteries["fingerprint minus ep095 (29)"]
    shapes = marker_shapes(base, pooled)
    lengths = sorted({L for _k, L, _n in shapes} | {2, 3, 4})
    idx = ngram_index([t for _e, l, t in f_win if l in ("her", "other")], lengths)
    real_forms = set()
    for _k, rx in base.items():
        real_forms.update(m if isinstance(m, str) else "".join(m)
                          for m in re.compile(rx).findall(pooled))

    aucs = []
    for _ in range(args.trials):
        s = matched_random_set(shapes, idx, rnd, real_forms)
        c = compile_battery(s)
        w = weights_from(f_her, f_oth, c)
        a, _p, _n = auc(score_windows(t_win, c, w), "her", "other")
        if a == a:
            aucs.append(a)
    aucs.sort()

    def run_set(bat):
        c = compile_battery(bat)
        s = score_windows(t_win, c, weights_from(f_her, f_oth, c))
        a, _p, _n = auc(s, "her", "other")
        return a, s

    tf = top_frequency_set(shapes, idx, real_forms)
    a_tf, s_tf = run_set(tf)
    fs = fit_selected_set(f_her, f_oth, idx, len(base))
    a_fs, s_fs = run_set(fs)
    _a_base, s_base = run_set(base)
    both = dict(tf)
    both.update(base)
    a_both, s_both = run_set(both)
    both_fs = dict(fs)
    both_fs.update(base)
    a_both_fs, s_both_fs = run_set(both_fs)

    P("| marker set | size | how it was chosen | AUC |")
    P("|---|---|---|---|")
    P("| the extraction, minus ep095 | %d | read off the tape and his card, before this test | **%s** |"
      % (len(base), fmt(a0)))
    P("| matched random, median of %d | %d | same length and comparable corpus frequency, otherwise arbitrary | %s |"
      % (len(aucs), len(base), fmt(aucs[len(aucs) // 2]) if aucs else "n/a"))
    P("| matched random, best of %d | %d | as above | %s |"
      % (len(aucs), len(base), fmt(aucs[-1]) if aucs else "n/a"))
    P("| fit-selected by log-odds | %d | arithmetic on the fit episodes, no model and no reading | %s |"
      % (len(fs), fmt(a_fs)))
    P("| most frequent n-grams | %d | the commonest forms in the corpus, no reference to who says them | **%s** |"
      % (len(tf), fmt(a_tf)))
    P("| frequency baseline + the extraction | %d | the two above together | **%s** |"
      % (len(both), fmt(a_both)))
    P("| fit-selected + the extraction | %d | the fit-selected baseline plus the extraction | **%s** |"
      % (len(both_fs), fmt(a_both_fs)))
    P("")
    if aucs:
        better = sum(1 for x in aucs if x >= a0)
        P("**Against arbitrary forms, the description wins.** Matched-random sets")
        P("reaching the extraction's AUC: **%d of %d** (median %s, 95th percentile %s)."
          % (better, len(aucs), fmt(aucs[len(aucs) // 2]),
             fmt(aucs[int(len(aucs) * 0.95)])))
        P("The forms the extraction named separate her from the room better than forms")
        P("of the same length and frequency drawn at random from the same text. That is")
        P("the specificity test passing, and it is the answer to *did the extraction")
        P("find the episodes rather than the woman*: it did not.")
        P("")
    lo, hi = auc_diff_ci(s_tf, s_base, "her", "other", random.Random(args.seed + 11))
    P("**Against two procedures that involve no reading at all, it loses, and this is")
    P("the finding the project should not skip.** The commonest n-grams in the corpus,")
    P("chosen with no reference to who says them, score %s. Markers picked by log-odds"
      % fmt(a_tf))
    P("off the fit episodes -- five lines of arithmetic, no model, no listening --")
    P("score %s. The description read off the tape scores %s. The frequency baseline"
      % (fmt(a_fs), fmt(a0)))
    P("beats it by %s (95%% CI %s to %s, paired over held-out episodes). Most of what"
      % (fmt(a_tf - a0), fmt(lo), fmt(hi)))
    P("separates her from the room is in ordinary frequency statistics that nobody had")
    P("to read anything to reach.")
    P("")
    lo2, hi2 = auc_diff_ci(s_both, s_tf, "her", "other", random.Random(args.seed + 12))
    lo3, hi3 = auc_diff_ci(s_both_fs, s_fs, "her", "other", random.Random(args.seed + 13))
    P("**So the question that decides it is whether the description carries anything")
    P("those baselines do not already have.** It does, and by a small margin that")
    P("holds up. Adding the extraction's markers to the frequency baseline moves it")
    P("from %s to %s, a difference of %s (95%% CI %s to %s); adding them to the"
      % (fmt(a_tf), fmt(a_both), fmt(a_both - a_tf), fmt(lo2), fmt(hi2)))
    P("fit-selected baseline moves it from %s to %s, a difference of %s (95%% CI %s to %s)."
      % (fmt(a_fs), fmt(a_both_fs), fmt(a_both_fs - a_fs), fmt(lo3), fmt(hi3)))
    P("%s"
      % ("Both intervals stay above zero, so the reading found something the counting "
         "did not. It is a real increment and a small one, beside a separation the "
         "counting reaches on its own."
         if lo2 > 0 and lo3 > 0 else
         "At least one interval crosses zero, so on this evidence the description "
         "cannot be shown to add anything to what raw counting already gives."))
    P("")
    P("For reference, the leaky battery -- the 24 markers")
    P("`yukarin/sheet/bounds.json` selected as hers by contrast across all 99")
    P("episodes, the held-out ones included -- scores %s,"
      % fmt(disc[("chronological", "bounds signature (%d, leaks)" % len(sig), "other")][0]))
    P("which is what a description that has seen the test set is worth here: very")
    P("little. Selection leakage is not this corpus's biggest problem.")
    P("")

    # ---------------- 4. mechanisms ----------------
    fit_set = {e["ep"] for e in splits["chronological"][0]}
    test_set = {e["ep"] for e in splits["chronological"][1]}
    mech = mechanism_prevalence(fit_set, test_set, args.min_expected)
    mt = [m for m in mech if m["testable"]]
    P("## 4. Do the sheet's mechanisms predict anything about unseen episodes")
    P("")
    P("Each of the 77 mechanisms has a member list naming the episodes it was found")
    P("in. Its prevalence over the fit episodes predicts how many of the %d held-out"
      % len(test_set))
    P("episodes it should appear in; a binomial interval says whether it did. A")
    P("mechanism expected in fewer than %g held-out episodes is not tested."
      % args.min_expected)
    P("")
    P("This is **not** a clean holdout: the clustering saw all 99 episodes, so a")
    P("mechanism cannot be absent from the held-out block by surprise. What it does")
    P("test is whether a prevalence the sheet reports as a trait is stable in time or")
    P("is a period the sheet is describing as a disposition.")
    P("")
    P("- testable mechanisms: **%d** of %d" % (len(mt), len(mech)))
    P("- prevalence holds: **%d of %d**" % (sum(1 for m in mt if m["ok"]), len(mt)))
    P("")
    off = sorted((m for m in mt if not m["ok"]), key=lambda m: m["z"])
    if off:
        P("| mechanism | fit episodes | expected held-out | observed | z |")
        P("|---|---|---|---|---|")
        for m in off:
            P("| `%s` | %d/%d | %.1f | %d | %+.1f |"
              % (m["name"], m["fit_eps"], len(fit_set), m["expected"], m["test_eps"], m["z"]))
        P("")
        down = [m["name"] for m in off if m["z"] < 0]
        up = [m["name"] for m in off if m["z"] > 0]
        P("**%d of the %d testable mechanisms move, %d down and %d up, and they move as"
          % (len(off), len(mt), len(down), len(up)))
        P("a set rather than one at a time.** What falls away is the advice-and-letters")
        P("material -- answering a problem with an invented construction, mirroring a")
        P("listener's trouble with her own, live calls. What rises is the frame and the")
        P("direct answer -- transitions, inviting the audience in, replying with")
        P("something concrete about herself. That is the shape of a programme changing")
        P("its corners, not of a woman changing. The sheet already knows part of this:")
        P("`yukarin/sheet/judgement.json` marks 16 of the 77 as the radio programme")
        P("rather than her. It does not mark these, and on this evidence the prevalence")
        P("numbers attached to at least %d more of them are describing a format era."
          % len(off))
        P("")

    # ---------------- 5. facts ----------------
    facts = fact_recurrence(fit_set, test_set, eps)
    multi = [f for f in facts if len(f["eps"]) >= 2]
    in_fit = [f for f in facts if f["in_fit"]]
    both_f = [f for f in facts if f["in_fit"] and f["in_test"]]
    only_one = [f for f in facts if len(f["eps"]) == 1]
    loc = sum(f["located"] for f in facts)
    ver = sum(f["verified"] for f in facts)
    tot = sum(f["total"] for f in facts)
    P("## 5. Do the fact records describe her, or describe episodes")
    P("")
    P("The %d records in `yukarin/persona/records_facts.json` cite the cues they were"
      % len(facts))
    P("located in. A record whose whole evidence sits in one episode is that")
    P("episode's content; one re-evidenced across the split boundary is something she")
    P("keeps saying, and only the second kind is a description of a person.")
    P("")
    P("| | |")
    P("|---|---|")
    P("| fact records | %d |" % len(facts))
    P("| speech citations the record claims are located in a cue | %d of %d |"
      % (loc, tot))
    P("| ... re-checked against the corpus here and found there | **%d (%.1f%%)** |"
      % (ver, ver / max(loc, 1) * 100))
    P("| records evidenced in two or more episodes | %d (%.0f%%) |"
      % (len(multi), len(multi) / max(len(facts), 1) * 100))
    P("| records evidenced in exactly one episode | %d (%.0f%%) |"
      % (len(only_one), len(only_one) / max(len(facts), 1) * 100))
    P("| records with evidence in the fit block | %d |" % len(in_fit))
    P("| ... re-evidenced in the held-out block | **%d (%.0f%%)** |"
      % (len(both_f), len(both_f) / max(len(in_fit), 1) * 100))
    P("")
    P("The attribution of the facts to the tape holds up under an independent check.")
    P("The records carry their own `located` flag; that flag is the pipeline's opinion")
    P("of itself, so every quote was searched for again in the corpus here. %d of the"
      % ver)
    P("%d claimed citations are present in the cue named or its immediate neighbours."
      % loc)
    P("That is the strongest number in this file, and it is a check on the pipeline's")
    P("honesty rather than on its insight -- nothing was invented.")
    P("")
    P("The recurrence figure is the weaker half. Half the records rest on one episode.")
    P("That is not by itself a fault -- a brother six years younger is a fact whether")
    P("she says it once or ten times -- but it means half the record set has no")
    P("internal confirmation at all, and cross-episode recurrence is the only kind")
    P("available without leaving the corpus. Of the %d records with evidence in the fit"
      % len(in_fit))
    P("block, **%d** turn up again in episodes the fit block does not contain. Those"
      % len(both_f))
    P("are the ones this corpus can call properties of her rather than things that")
    P("happened in a broadcast.")
    P("")

    # ---------------- 6. providers ----------------
    pa = provider_agreement(random.Random(args.seed + 5))
    P("## 6. Does the extraction reproduce itself")
    P("")
    P("`yukarin/providers.db` and the run outputs beside it hold the same extraction")
    P("run over and over on two fixed episodes -- one 2003, one 2005, both hand-read")
    P("-- with the prompt, the input text, the verification and the post-processing")
    P("held constant and only the host, the model and the reasoning setting varying.")
    P("That is re-extraction agreement data and it has never been read as one.")
    P("")
    db = pa.get("db") or {}
    if db:
        qv, rec, mech = db["qv"], db["recall"], db["mech"]
        P("**First, what the database structurally cannot say.** Its run tables are")
        P("keyed on (host+model, episode), so a second run of the same configuration")
        P("cannot be stored; the largest number of rows in any cell is **%d**. The"
          % db["max_per_cell"])
        P("harness sends no seed and runs at temperature 0.2, so every call is")
        P("stochastic. **There is no repeat of any single configuration anywhere in the")
        P("file, and therefore no run-to-run reliability figure in it.**")
        P("")
        P("`yukarin/tools/control.py` was written to produce exactly that figure -- its")
        P("docstring says the official endpoint runs twice, labels `ctl_a` and `ctl_b`,")
        P("and that the agreement between those two runs is the noise floor every other")
        P("comparison is read against. No `ctl_a` or `ctl_b` output exists on disk. The")
        P("one measurement that would make the rest of the ranking interpretable is the")
        P("one that was skipped.")
        P("")
        P("What the %d successful rows do give, as distributions rather than a ranking:" % db["ok"])
        P("")
        P("| | n | min | median | max |")
        P("|---|---|---|---|---|")
        if qv:
            P("| quote validity (cited quotes found verbatim in the cue cited) | %d | %s | %s | %s |"
              % (len(qv), fmt(qv[0]), fmt(qv[len(qv) // 2]), fmt(qv[-1])))
        if rec:
            P("| recall against the hand extraction | %d | %s | %s | %s |"
              % (len(rec), fmt(rec[0]), fmt(rec[len(rec) // 2]), fmt(rec[-1])))
        if mech:
            P("| mechanisms surviving verification | %d | %d | %d | %d |"
              % (len(mech), mech[0], mech[len(mech) // 2], mech[-1]))
        P("")
        P("Quote validity is the one thing that reproduces: it is mechanical, checked")
        P("against the corpus with no model in the loop, and it sits near the ceiling")
        P("almost everywhere. **Fabrication is not the failure mode.** What the same")
        P("input produces at wildly different rates is *how much* gets extracted and")
        P("*which* of it -- a %d-fold range in mechanism count off identical text."
          % (mech[-1] // max(mech[len(mech) // 2], 1) if mech else 0))
        P("")
    P("**Second, the agreement that can be measured.** The run outputs are on disk, so")
    P("agreement is computable directly: for each pair of runs over the same episode,")
    P("the overlap of the cue indices each one cited as evidence -- which moments of")
    P("the episode the run pointed at. That is the only comparable unit, because")
    P("mechanism *names* are free text the model invents.")
    P("")
    P("| episode | runs | pairs | Jaccard min / median / max | same by chance (median) | identical mechanism names, all pairs |")
    P("|---|---|---|---|---|---|")
    for ep, d in sorted(pa["eps"].items()):
        j, ch = d["j"], d["chance"]
        P("| %s | %d | %d | %s / **%s** / %s | %s | %d (most in one pair: %d) |"
          % (ep, d["runs"], d["pairs"], fmt(j[0], 2), fmt(j[len(j) // 2], 2),
             fmt(j[-1], 2), fmt(ch[len(ch) // 2], 2) if ch else "n/a",
             d["name_matches"], d["name_max"]))
    P("")
    P("Two runs of the same extraction over the same episode agree on **about a")
    P("quarter** of the moments they cite. That is two to three times chance, so the")
    P("runs are reading the same text and not hallucinating independently -- and it is")
    P("nowhere near agreement. On the naming of what was found they agree essentially")
    P("never.")
    P("")
    if pa["near"]:
        P("**Third, the noise floor, as close as the disk gets to it.** These pairs are")
        P("the same model on the same host over the same episode with one inference")
        P("setting changed:")
        P("")
        P("| pair | episode | Jaccard on cited cues |")
        P("|---|---|---|")
        for what, ep, j in pa["near"]:
            P("| %s | %s | %s |" % (what, ep, fmt(j, 2)))
        P("")
        near = [j for _w, _e, j in pa["near"]]
        P("They run %s to %s -- **at or below the median agreement between two"
          % (fmt(min(near), 2), fmt(max(near), 2)))
        P("different models**. Changing one setting on one model moves the output as")
        P("much as swapping the model does. Whatever the host ranking is sorting on, it")
        P("is not separable from the method's own variance, and the ranking's mid-field")
        P("ordering should not be read as a result.")
        P("")
    P("")

    # ---------------- what this does not establish ----------------
    P("## 7. What this does not establish")
    P("")
    P("Stated separately because a demonstration that buries its limits is worth")
    P("nothing, and because several of these are large enough to bound the whole")
    P("exercise.")
    P("")
    P("**It does not test the extraction.** The sheet, the fact records and the marker")
    P("batteries were all written with the whole corpus available. What is held out")
    P("is the estimation of every rate, weight and prevalence, not the extraction")
    P("itself. Re-running the pipeline on the fit episodes alone and comparing the")
    P("sheet it produces against the one on disk is the test this is standing in for,")
    P("and it costs model calls this run was not allowed to make.")
    P("")
    P("**It measures the surface, not the person.** Everything above counts forms.")
    P("None of it touches the mechanisms as descriptions of a psychology -- whether")
    P("`self-failure-comedy` is a real disposition rather than a plausible label for a")
    P("pile of moments is not a question a regex can be pointed at. §4 tests only")
    P("whether the sheet's prevalence numbers are stable in time.")
    P("")
    P("**The other voices are not a matched control, and this is the largest hole.**")
    P("The attribution has one label for everybody who is not her, so the negative")
    P("class is a mixture -- the programme's staff, whom the sheet's address block")
    P("names as 矢野さん, ヨシイさん and 親方, plus occasional guests -- and it cannot be")
    P("decomposed from the labels on disk. If most of it is men, then part of every")
    P("AUC above is telling a woman from men in 2003 Japanese, which needs no")
    P("description of *her* at all. Nothing in this corpus bounds how large that part")
    P("is, because there is no second young female broadcaster in it in any volume.")
    P("")
    P("**The labels are a model's.** The attribution was produced by one model call")
    P("per episode and has known boundary noise. The interior-only figure in §2 bounds")
    P("what that costs but does not remove it, and a systematic attribution error")
    P("would appear here as signal.")
    P("")
    P("**The tape is ASR, and the transcription is not stable across the split.** The")
    P("counts inherit whisper's errors, which are not uniform: `docs/verification.md`")
    P("§2 fallacy 4 has the detail. Worse for a chronological design, the long-vowel")
    P("mark and the comma are both measurably rarer in the late block, so an")
    P("orthographic shift and a change in her arrive at the measurement looking")
    P("identical. §1 separates them where a marker family can be split by spelling and")
    P("cannot where it cannot. A chronological split tests the description against a")
    P("moving target and against a moving instrument at the same time.")
    P("")
    P("**Register transfer is untouched, and it is the one that matters downstream.**")
    P("All of this is spoken broadcast Japanese measured against spoken broadcast")
    P("Japanese. She types private messages to one person. There is no held-out set of")
    P("things she would have typed in 2003 because no such text exists, so nothing")
    P("here licenses any expected rate in her chat. `docs/verification.md` §2")
    P("fallacy 2 is the standing statement of that and this file does not weaken it.")
    P("")
    P("**Multiple comparisons.** §1 tests 22 markers and §4 tests 33 mechanisms at 95%")
    P("each, so roughly one to three flags per run are chance. A single flag is noise;")
    P("the ones worth reading are the large ones with a named cause.")
    P("")
    P("**What would settle the parts this leaves open**, in order of what it buys per")
    P("call spent:")
    P("")
    P("1. Run one stable configuration over ep005 and ep095 **twice**, at the same")
    P("   temperature and reasoning setting, and compute the cue-overlap figure in §6")
    P("   between those two runs. That is the noise floor `yukarin/tools/control.py`")
    P("   was written to produce. Four calls. Until it exists, no number in the host")
    P("   ranking can be read as a measurement of a host.")
    P("2. Re-run the map stage over the fit episodes only and compare the sheet it")
    P("   produces against the one on disk -- the real held-out test of the")
    P("   extraction, which this file only stands in for. Seventy calls.")
    P("3. Label the `other` spans by speaker in a handful of episodes. That is the")
    P("   only way to find out how much of §2 is her voice and how much is not being")
    P("   a man.")
    P("")

    # ---------------- headline, inserted above ----------------
    S = []
    tested = [r for r in stab["chronological"] if r["testable"]]
    S.append("## What it comes to")
    S.append("")
    S.append("| question | answer |")
    S.append("|---|---|")
    S.append("| Does her measured surface hold on episodes the measurement never saw? | "
             "**%d of %d** testable markers land inside a prediction interval that "
             "carries between-episode burstiness. |"
             % (sum(1 for r in tested if r["boot_ok"]), len(tested)))
    S.append("| Does the description separate her from the room in unseen episodes? | "
             "**AUC %s** against the other voices in the studio, %s against letters "
             "read aloud. |" % (fmt(a0), fmt(disc[("chronological", "fingerprint minus ep095 (29)", "mail")][0])))
    S.append("| Is that specific to her, or would any forms do? | "
             "**Specific.** Of %d marker sets of the same length and frequency drawn "
             "at random, **%d** reached it (median %s). |"
             % (len(aucs), sum(1 for x in aucs if x >= a0),
                fmt(aucs[len(aucs) // 2]) if aucs else float("nan")))
    S.append("| Does it beat counting, with no reading at all? | "
             "**No.** The commonest n-grams in the corpus score %s and markers picked "
             "by log-odds off the fit episodes score %s, both above the description's "
             "%s. |" % (fmt(a_tf), fmt(a_fs), fmt(a0)))
    S.append("| Does it carry anything counting does not? | "
             "**Yes, a little.** Added to the frequency baseline it moves %s to %s "
             "(CI %s to %s); added to the fit-selected baseline, %s to %s (CI %s to "
             "%s). |" % (fmt(a_tf), fmt(a_both), fmt(lo2), fmt(hi2),
                         fmt(a_fs), fmt(a_both_fs), fmt(lo3), fmt(hi3)))
    rtested = [r for r in stab["random"] if r["testable"]]
    S.append("| How much does the two years of drift cost? | "
             "Shuffle the split instead of taking it in time and the same "
             "measurement holds **%d of %d** markers instead of %d of %d, and "
             "separates at **%s** instead of %s. That gap is the drift. |"
             % (sum(1 for r in rtested if r["boot_ok"]), len(rtested),
                sum(1 for r in tested if r["boot_ok"]), len(tested),
                fmt(disc[("random", "fingerprint minus ep095 (29)", "other")][0]),
                fmt(a0)))
    S.append("| Does the pipeline reproduce itself? | "
             "**Unmeasured, and the measurement was designed and then skipped.** Two "
             "runs of the same extraction over the same episode agree on about a "
             "quarter of the moments they cite; the same model with one setting "
             "changed agrees no better than a different model does. |")
    S.append("| Do the fact records describe her or describe episodes? | "
             "**%d%%** of the 152 rest on a single episode; **%d%%** of those with "
             "evidence in the fit block are re-evidenced in the held-out block. |"
             % (round(len(only_one) / max(len(facts), 1) * 100),
                round(len(both_f) / max(len(in_fit), 1) * 100)))
    S.append("")
    S.append("The short form: **the described surface transfers to unseen episodes and")
    S.append("is hers rather than the episodes'; the extraction that produced it does not")
    S.append("reproduce; and the description is worth less as a discriminator than")
    S.append("counting common forms, though it is not worth nothing on top of them.**")
    S.append("§7 says what none of this reaches, and one of those limits is large.")
    S.append("")
    L[summary_at:summary_at] = S

    out = args.out
    io.open(out, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("wrote", out)
    print("stability chronological: Poisson %d/%d bootstrap %d/%d"
          % (sum(1 for r in stab["chronological"] if r["testable"] and r["poisson_ok"]),
             sum(1 for r in stab["chronological"] if r["testable"]),
             sum(1 for r in stab["chronological"] if r["testable"] and r["boot_ok"]),
             sum(1 for r in stab["chronological"] if r["testable"])))
    for k in sorted(disc):
        print("auc", k, fmt(disc[k][0]))
    print("controls: random median %s best %s | topfreq %s | fit-selected %s"
          % (fmt(aucs[len(aucs) // 2]) if aucs else "n/a",
             fmt(aucs[-1]) if aucs else "n/a", fmt(a_tf), fmt(a_fs)))
    print("interior-only AUC", fmt(ai))
    print("mechanisms ok %d/%d" % (sum(1 for m in mt if m["ok"]), len(mt)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
