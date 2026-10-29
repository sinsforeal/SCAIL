"""Fitting one timed line set onto another, and refusing when it does not fit.

The times in a subtitle file are true of the cut it was made for and of no
other. A broadcast rip of this episode starts its first line at 2:09 and the
disc's own caption starts the same line at 0:04: the broadcast carries a
sponsor card and a recap in front of the programme. The gap is not constant
either, because the commercial break takes out more picture on one side than
the other. So the model fitted here is a piecewise constant offset: within a
stretch of programme both cuts run at the same rate, and at a cut boundary the
offset steps.

Two ways to find the pairs the offset is fitted to.

**On text**, when both sides are the same language. Every line is matched to
the line most like it on the other side, the match is required to be mutual
and clearly better than the runner-up, and the sequence is then reduced to its
longest increasing subsequence so that nothing crosses. Split lines -- one rip
breaks a sentence in two where the other does not -- are kept out of the fit by
a high similarity floor, because half a sentence starts later than the whole
one and would drag the offset with it.

**On onsets alone**, when the two sides are different languages and share no
text. Only the times are left, so the fit is a vote: every plausible offset
gets a count of how many onsets it would line up, the strongest few survive,
and a dynamic program then walks the episode choosing one of them per line
with a penalty for changing. That penalty is what stops the fit from chasing
a coincidence in the middle of a scene.

Both paths end in the same place: segments, each with an offset and a
residual, and a decision to accept or refuse.
"""
import bisect
import collections

from . import normal

# a pair is only allowed to set the offset if the two lines are nearly the
# same sentence; a partial overlap is a split line and its start time is not
# the same event
ANCHOR_SIM = 0.70
# a pair counts as "this is the same episode" much lower down
MATCH_SIM = 0.50
# how far two anchors' offsets may differ and still belong to one stretch of
# programme. Frame-accurate rips of one cut agree inside a frame or two; this
# leaves room for a caption whose start was typed by hand.
SEGMENT_TOL = 0.30
# a new stretch is only opened when this many anchors in a row agree with each
# other and disagree with the current one. One anchor that disagrees is an
# outlier, and outliers exist in every rip.
CONFIRM = 3


def index_grams(lines):
    """gram -> [line number], for finding the few lines worth comparing."""
    idx = collections.defaultdict(list)
    grams = []
    for i, ln in enumerate(lines):
        g = normal.grams(normal.normalise(ln["text"]))
        grams.append(g)
        for x in g:
            idx[x].append(i)
    return idx, grams


def best_matches(a_lines, b_lines):
    """For every line of a, the two best-scoring lines of b.

    Only lines sharing at least one 3-gram are scored, which is what keeps this
    a second's work on a pair of files rather than half a million comparisons.
    """
    idx, b_grams = index_grams(b_lines)
    _, a_grams = index_grams(a_lines)
    out = []
    for i, ga in enumerate(a_grams):
        hits = collections.Counter()
        for x in ga:
            for j in idx.get(x, ()):
                hits[j] += 1
        best = (0.0, -1)
        second = 0.0
        for j in hits:
            s = normal.dice(ga, b_grams[j])
            if s > best[0]:
                second = best[0]
                best = (s, j)
            elif s > second:
                second = s
        out.append({"i": i, "j": best[1], "sim": round(best[0], 4),
                    "second": round(second, 4)})
    return out


def _lis(pairs):
    """The longest run of pairs that does not cross, by the b index.

    Two rips can both contain a line that happens to be identical to a line
    somewhere else in the episode -- a greeting, a name called out. Keeping
    only the longest non-crossing subsequence throws those away without
    needing to know which ones they are.
    """
    if not pairs:
        return []
    n = len(pairs)
    tails = []          # index into pairs of the last member of each length
    prev = [-1] * n
    for k, (_i, j, _s) in enumerate(pairs):
        lo, hi = 0, len(tails)
        while lo < hi:
            mid = (lo + hi) // 2
            if pairs[tails[mid]][1] < j:
                lo = mid + 1
            else:
                hi = mid
        if lo:
            prev[k] = tails[lo - 1]
        if lo == len(tails):
            tails.append(k)
        else:
            tails[lo] = k
    out = []
    k = tails[-1]
    while k >= 0:
        out.append(pairs[k])
        k = prev[k]
    out.reverse()
    return out


def text_anchors(cand, ref, anchor_sim=ANCHOR_SIM):
    """Monotone (candidate time, reference time) pairs, on the text."""
    fwd = best_matches(cand, ref)
    back = best_matches(ref, cand)
    back_best = {m["i"]: m["j"] for m in back}
    picked = []
    for m in fwd:
        if m["j"] < 0 or m["sim"] < anchor_sim:
            continue
        if back_best.get(m["j"]) != m["i"]:
            continue                      # not each other's best: a split line
        if m["sim"] - m["second"] < 0.05:
            continue                      # a line repeated in the episode
        picked.append((m["i"], m["j"], m["sim"]))
    picked = _lis(picked)
    return [(cand[i]["start"], ref[j]["start"], s) for i, j, s in picked], fwd


def match_rate(fwd, sim=MATCH_SIM):
    """Share of candidate lines with any counterpart at all. This is the check
    that the file is this episode of this work, and it is independent of every
    time in either file."""
    if not fwd:
        return 0.0
    return sum(1 for m in fwd if m["sim"] >= sim) / float(len(fwd))


# ------------------------------------------------------- the piecewise fit

def _median(xs):
    xs = sorted(xs)
    n = len(xs)
    if not n:
        return 0.0
    return xs[n // 2] if n % 2 else 0.5 * (xs[n // 2 - 1] + xs[n // 2])


def scatter(anchors, window=15):
    """How closely two files agree inside one stretch of programme.

    Two rips made from one authoring agree to the millisecond; two authorings
    of the same episode, typed by different people watching different masters,
    agree to a few tenths of a second and no better. A tolerance fixed in
    advance therefore either misses a real cut on one pair or invents a dozen
    of them on the other, and the broadcast rip of this episode got twenty
    invented stretches whose offsets flapped over half a second.

    So it is measured instead: the spread of the offset inside a short sliding
    window, where no cut can be hiding, taken as the median of the absolute
    deviations, and then the median of that over the whole episode.
    """
    ds = [b - a for a, b, _s in sorted(anchors, key=lambda x: x[0])]
    if len(ds) < window:
        return 0.0
    spreads = []
    for i in range(len(ds) - window + 1):
        chunk = ds[i:i + window]
        mid = _median(chunk)
        spreads.append(_median([abs(x - mid) for x in chunk]))
    return _median(spreads)


def tolerance(anchors, base=SEGMENT_TOL, k=4.0, cap=1.5):
    """The step a real cut has to be bigger than, for this pair of files."""
    return min(cap, max(base, k * scatter(anchors)))


def fit_segments(anchors, tol=SEGMENT_TOL, confirm=CONFIRM):
    """Anchors -> stretches of programme, each with one offset.

    Walks the anchors in time. A point that agrees with the stretch being built
    joins it. A point that does not is held back, and only when `confirm`
    held-back points agree with each other is a new stretch opened at the first
    of them; otherwise they are dropped as outliers.
    """
    anchors = sorted(anchors, key=lambda a: a[0])
    segs = []
    cur = []
    hold = []
    for a in anchors:
        d = a[1] - a[0]
        if not cur:
            cur = [a]
            continue
        if abs(d - _median([x[1] - x[0] for x in cur])) <= tol:
            # the stretch carried on across the held-back points, so those
            # points were wrong rather than the start of something; they are
            # dropped, never folded back in, because a bad anchor inside a
            # stretch is exactly what the residual is there to report
            hold = []
            cur.append(a)
            continue
        hold.append(a)
        if len(hold) >= confirm:
            ds = [x[1] - x[0] for x in hold]
            if max(ds) - min(ds) <= tol * 2:
                segs.append(cur)
                cur = hold
                hold = []
            else:
                hold.pop(0)               # not a step, just noise
    if cur:
        segs.append(cur)
    out = []
    for s in segs:
        ds = [a[1] - a[0] for a in s]
        off = _median(ds)
        res = [abs(d - off) for d in ds]
        out.append({
            "from": round(s[0][0], 3), "to": round(s[-1][0], 3),
            "anchors": len(s), "offset": round(off, 3),
            "residual_rms": round((sum(r * r for r in res) / len(res)) ** 0.5, 3),
            "residual_max": round(max(res), 3),
            "points": [(round(a[0], 3), round(a[1] - a[0], 3)) for a in s],
        })
    return out


def merge_small(segs, min_anchors=3, tol=SEGMENT_TOL):
    """A stretch with almost no support is not a cut, it is a handful of bad
    anchors. It is folded into whichever neighbour has the closer offset."""
    if len(segs) <= 1:
        return segs
    out = []
    for s in segs:
        if s["anchors"] >= min_anchors or not out:
            out.append(dict(s))
            continue
        out[-1] = _join(out[-1], s)
    # a leading small stretch survives the loop above; fold it forward
    while len(out) > 1 and out[0]["anchors"] < min_anchors:
        out[1] = _join(out[0], out[1])
        out.pop(0)
    return _drop_excursions(out, tol)


def _drop_excursions(segs, tol):
    """A stretch whose neighbours agree with each other is not a cut.

    A cut cannot be undone: once the broadcast has inserted a sponsor card the
    programme stays that much later for the rest of the reel. So an offset that
    leaves the line its neighbours sit on and then comes back to it is
    something else -- with a speech recogniser as the reference it is a quiet
    passage where the voice detector opened a second and a half early, four
    segments in a row. Those stretches are folded back into their neighbours,
    which is where their lines belonged.
    """
    changed = True
    while changed and len(segs) >= 3:
        changed = False
        for i in range(1, len(segs) - 1):
            a, b, c = segs[i - 1], segs[i], segs[i + 1]
            if abs(a["offset"] - c["offset"]) <= tol \
                    and abs(b["offset"] - a["offset"]) > tol:
                segs = segs[:i - 1] + [_join(_join(a, b), c)] + segs[i + 2:]
                changed = True
                break
    return segs


def _join(a, b):
    pts = a["points"] + b["points"]
    off = _median([d for _t, d in pts])
    res = [abs(d - off) for _t, d in pts]
    return {"from": a["from"], "to": b["to"], "anchors": len(pts),
            "offset": round(off, 3),
            "residual_rms": round((sum(r * r for r in res) / len(res)) ** 0.5, 3),
            "residual_max": round(max(res), 3), "points": pts}


def offset_at(segs, t):
    """The offset the fit applies at a candidate time.

    Outside the fitted stretches the nearest one's offset is used rather than
    an extrapolation: nothing in the data says the drift continues, and the
    lines out there are the opening theme and the credits.
    """
    if not segs:
        return 0.0
    for k, s in enumerate(segs):
        if t <= s["to"] or k == len(segs) - 1:
            if k and t < s["from"]:
                prev = segs[k - 1]
                # the boundary sits halfway between the two stretches
                if t < 0.5 * (prev["to"] + s["from"]):
                    return prev["offset"]
            return s["offset"]
    return segs[-1]["offset"]


def apply_segments(lines, segs):
    """The candidate's lines moved onto the reference's clock."""
    out = []
    for ln in lines:
        off = offset_at(segs, ln["start"])
        n = dict(ln)
        n["start"] = round(ln["start"] + off, 3)
        n["end"] = round(ln["end"] + off, 3)
        n["offset"] = round(off, 3)
        out.append(n)
    out.sort(key=lambda r: r["start"])
    return out


def fit_quality(anchors, segs):
    """How well the fitted offsets explain the anchors, in seconds."""
    if not anchors or not segs:
        return {"anchors": 0, "median_error": None, "within_250ms": 0.0,
                "within_500ms": 0.0, "within_1000ms": 0.0}
    errs = [abs((b - a) - offset_at(segs, a)) for a, b, _s in anchors]
    out = {"anchors": len(errs), "median_error": round(_median(errs), 3)}
    for ms in (250, 500, 1000):
        n = sum(1 for e in errs if e <= ms / 1000.0)
        out["within_%dms" % ms] = round(n / float(len(errs)), 4)
    return out


def verdict(n_cand, n_ref, rate, quality, segs,
            min_match=0.50, min_coverage=0.30, min_within=0.80,
            within=1.0, max_median=0.50, max_rms=1.00):
    """Accept or refuse, with the reason in words.

    Refusing is the point of this function. A file that does not fit is not a
    file to be shifted into place: it is a different cut, a different episode
    or a different work, and putting its times on this video would put a wrong
    line under every frame that follows.

    Refusing and ranking are two different questions and are kept apart here.
    A file is refused when the piecewise model does not describe it -- wrong
    episode, too little to anchor on, anchors still seconds out after the fit.
    How precisely it lands once accepted is reported and is what decides which
    accepted file wins; it is not grounds for throwing one away. A broadcast
    caption typed against a broadcast master lands within about a third of a
    second of a disc caption typed against the disc, and that is the truth
    about those two files rather than a failure of the fit. A third of a second
    is well inside a spoken line, which is what the times are for.
    """
    cov = quality["anchors"] / float(max(1, min(n_cand, n_ref)))
    why = []
    if rate < min_match:
        why.append("only %.0f%% of its lines have a counterpart in the reference; "
                   "this is not the same episode" % (100 * rate))
    if cov < min_coverage:
        why.append("only %.0f%% of the shorter file could be anchored" % (100 * cov))
    if (quality["median_error"] or 0) > max_median:
        why.append("after fitting, the middling anchor is still %.2f s out"
                   % quality["median_error"])
    if quality["within_%dms" % int(within * 1000)] < min_within:
        why.append("after fitting, %.0f%% of anchors are still more than %.1f s out"
                   % (100 * (1 - quality["within_%dms" % int(within * 1000)]), within))
    worst = max([s["residual_rms"] for s in segs] or [0.0])
    if worst > max_rms:
        why.append("a fitted stretch still scatters by %.2f s" % worst)
    return {"accepted": not why, "coverage": round(cov, 4),
            "match_rate": round(rate, 4), "worst_rms": worst,
            "reasons": why}


# --------------------------------------------- fitting on onsets alone

def _refine(cand_starts, ref_sorted, off, bin_w):
    """A voted offset moved to the middle of the pairs that voted for it.

    A bin is half a second wide and the offset it stands for is its edge, so a
    true offset can sit a quarter of a second from the number the vote returns.
    That quarter second then costs every one of its lines a chunk of its score,
    while a coincidental offset that happens to land on a bin edge keeps all of
    its. The broadcast rip's whole second half was fitted a hundred seconds
    wrong that way: the wrong offset scored better per line than the right one.
    """
    ds = []
    for c in cand_starts:
        k = bisect.bisect_left(ref_sorted, c + off)
        for r in ref_sorted[max(0, k - 1):k + 2]:
            if abs(r - c - off) <= bin_w:
                ds.append(r - c)
    return _median(ds) if ds else off


def onset_anchors(cand_starts, ref_starts, max_offset=420.0, tol=0.5,
                  peaks=16, switch_penalty=6.0):
    """Monotone (candidate time, reference time) pairs from times only.

    `max_offset` is kept for the caller that wants to say how far a broadcast
    cut may have moved the programme; the search itself is bounded by what it
    has already placed, so the number only trims the first window.
    """
    ref_sorted = sorted(ref_starts)
    cand = sorted(cand_starts)
    if not ref_sorted or not cand:
        return [], []
    anchors = _monotone(place_stretches(cand, ref_sorted, tol, tol))
    # A run is allowed a few misses inside it, so it also lets in a few pairs
    # that are not the same event: one line of the candidate against a
    # neighbouring line of the reference. They are worth nothing and they cost
    # a stretch its residual, so a pair further from its own stretch's offset
    # than any real timing difference could be is dropped.
    anchors = _prune(anchors, tol)
    offsets = [s["offset"] for s in
               fit_segments(anchors, tol=max(tol, tolerance(anchors)))]
    return anchors, offsets


def _prune(anchors, tol, slack=2.0, min_anchors=6, min_span=30.0):
    """Anchors kept only where enough of them agree over enough of the clock.

    Fitting on times alone finds a stretch wherever a few lines happen to sit
    at the same distance from a few reference lines, and this episode has one
    of those: six lines in a row, sixteen seconds of programme, five and a half
    seconds away from the stretch on either side of them. Six in a row is not
    obviously noise, but the sixteen seconds is decisive -- a cut boundary
    comes after a sponsor card, an opening or a commercial break, never sixteen
    seconds after the last one and never reversed. Folding such a stretch into
    its neighbour, which is what the ordinary tidy-up does, moves nothing but
    ruins the neighbour's residual and so the verdict on the whole file, so
    they are dropped instead.
    """
    out = []
    for s in fit_segments(anchors, tol=max(tol, tolerance(anchors))):
        if s["anchors"] < min_anchors or (s["to"] - s["from"]) < min_span:
            continue
        off = s["offset"]
        out.extend([a for a in anchors if s["from"] <= a[0] <= s["to"]
                    and abs((a[1] - a[0]) - off) <= slack * tol])
    out.sort(key=lambda a: a[0])
    return out or anchors


def _monotone(anchors):
    """The longest run of pairs that does not cross, by reference time."""
    picked = _lis([(i, a[1], a[2]) for i, a in enumerate(anchors)])
    keep = {i for i, _j, _s in picked}
    return [a for i, a in enumerate(anchors) if i in keep]


def _run_of(cs, matched, allow_missing=3):
    """The longest stretch of consecutive lines an offset explains.

    An offset that is right explains line after line; an offset that is a
    coincidence explains one here and one three lines further on. Keeping only
    the longest run, and allowing a few misses inside it for the lines one file
    splits and the other does not, is what separates the two -- and it is also
    what says where the stretch ends, which is what the search either side of
    it needs to know.
    """
    best = (0, 0, 0)
    i = 0
    while i < len(cs):
        if cs[i] not in matched:
            i += 1
            continue
        j = i
        gap = 0
        last = i
        while j + 1 < len(cs) and gap <= allow_missing:
            j += 1
            if cs[j] in matched:
                gap = 0
                last = j
            else:
                gap += 1
        hits = sum(1 for k in range(i, last + 1) if cs[k] in matched)
        if hits > best[0]:
            best = (hits, i, last)
        i = last + 1
    return best


def place_stretches(cand_starts, ref_sorted, tol, bin_w, c_lo=None, c_hi=None,
                    r_lo=None, r_hi=None, depth=0, min_lines=8, min_hits=6):
    """Every stretch of programme, found strongest first inside its own window.

    One vote over a whole episode cannot find a short stretch: this episode's
    prologue is thirty-odd lines, and thirty votes are lost among a thousand
    bins of noise, so it came out a hundred and twenty-five seconds wrong. But
    the prologue is boxed in once the long stretches are placed -- it lies
    before them on both clocks -- and a vote over a two-minute window is not
    close at all.

    So the search is recursive. The strongest offset in the window wins, its
    longest unbroken run of lines becomes a stretch, and the search then runs
    again on what is left in front of it and behind it, with both sides bounded
    by what has already been placed. Nothing has to be told how many cuts the
    broadcast made.
    """
    cs = [c for c in cand_starts
          if (c_lo is None or c > c_lo) and (c_hi is None or c < c_hi)]
    rs = [r for r in ref_sorted
          if (r_lo is None or r > r_lo) and (r_hi is None or r < r_hi)]
    if depth > 8 or len(cs) < min_lines or len(rs) < min_lines:
        return []
    votes = collections.Counter()
    for c in cs:
        for r in rs:
            votes[int(round((r - c) / bin_w))] += 1
    if not votes:
        return []
    off = _refine(cs, rs, votes.most_common(1)[0][0] * bin_w, bin_w)
    matched = {}
    for c in cs:
        k = bisect.bisect_left(rs, c + off)
        for r in rs[max(0, k - 1):k + 2]:
            if abs(r - c - off) <= tol:
                matched[c] = r
                break
    hits, i, j = _run_of(cs, matched)
    if hits < min_hits:
        return []
    found = [(c, matched[c], 1.0) for c in cs[i:j + 1] if c in matched]
    return (place_stretches(cand_starts, ref_sorted, tol, bin_w, c_lo,
                            found[0][0], r_lo, found[0][1], depth + 1)
            + found
            + place_stretches(cand_starts, ref_sorted, tol, bin_w, found[-1][0],
                              c_hi, found[-1][1], r_hi, depth + 1))


# --------------------------------------------- snapping a transcript on

def snap_to_skeleton(segments, skeleton, max_shift=1.0, keep_end=True):
    """Move a transcript's segments onto a skeleton's cue boundaries.

    This is the last step of the case where no Japanese subtitle exists: the
    speech recogniser supplies the words with times of its own, and the English
    track supplies cue boundaries that a person typed while watching. The
    recogniser's boundaries drift -- it starts a segment where the audio rises,
    which is not where the line starts -- so each segment is pulled onto the
    nearest skeleton onset it can reach.

    Each skeleton cue is used at most once and in order, so a burst of short
    segments cannot all collapse onto one cue. A segment with no cue within
    `max_shift` keeps its own times and is marked, because inventing a
    boundary for it would be worse than leaving it where the recogniser put it.
    """
    sk = sorted(skeleton, key=lambda r: r["start"])
    out = []
    used = 0
    for seg in sorted(segments, key=lambda r: r["start"]):
        best = None
        for k in range(used, len(sk)):
            cue = sk[k]
            if cue["start"] > seg["start"] + max_shift:
                break
            d = abs(cue["start"] - seg["start"])
            if d <= max_shift and (best is None or d < best[0]):
                best = (d, k)
        n = dict(seg)
        if best is None:
            n["snapped"] = False
            n["shift"] = 0.0
        else:
            _d, k = best
            cue = sk[k]
            n["shift"] = round(cue["start"] - seg["start"], 3)
            n["start"] = round(cue["start"], 3)
            if keep_end and abs(cue["end"] - seg["end"]) <= max_shift:
                n["end"] = round(cue["end"], 3)
            n["snapped"] = True
            used = k + 1
        if n["end"] < n["start"]:
            n["end"] = n["start"]
        out.append(n)
    return out
