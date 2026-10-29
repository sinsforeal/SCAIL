"""Checks on made-up input, for the parts a real file cannot exercise.

Made-up input is not second best here: it is the only way to state the
property. Snapping a recogniser's segments onto cue boundaries is checked
against boundaries this file chose, so a segment whose start has drifted is
known to have landed back on the right one, each boundary is used once, and a
segment with no boundary near it is left where it was rather than dragged to
the nearest thing. The piecewise fit is checked against an offset schedule this
file knows, with noise and a few deliberate outliers, so that a failure says
which of the two the fit could not survive. The song-span rule is checked
against a mark laid inside a line of dialogue, which is what a real ending
chapter mark did.

The one piece here that costs money to exercise for real -- the model that
judges a recognised line against the translated one -- is checked on the shapes
an answer comes back in, because what must hold is that anything which is not a
list of verdicts is refused rather than stored.

    python -m tools.speakers selftest
"""
import os
import random
import tempfile

from . import align, normal, songs, spotcheck, timedtext


def _cue(start, end, text="", speaker=""):
    return {"start": start, "end": end, "text": text, "speaker": speaker,
            "named": bool(speaker), "style": "", "index": 0}


def _check(name, ok, detail=""):
    print("  %-4s %s%s" % ("ok" if ok else "FAIL", name,
                           "" if ok else "   " + detail))
    return bool(ok)


def t_snap():
    """Drifted segments come back to the boundaries, one boundary each."""
    rnd = random.Random(7)
    skeleton = [_cue(t, t + 1.8) for t in [3.0, 6.0, 9.4, 12.1, 15.0, 21.0, 24.5]]
    segments = []
    for c in skeleton:
        segments.append(_cue(round(c["start"] + rnd.uniform(-0.6, 0.6), 3),
                             c["end"] + 0.2, "line at %.1f" % c["start"]))
    # one segment far from every boundary: nothing may pull it
    segments.append(_cue(40.0, 41.0, "orphan"))
    segments.sort(key=lambda r: r["start"])
    out = align.snap_to_skeleton(segments, skeleton, max_shift=1.0)
    starts = sorted(r["start"] for r in out if r["snapped"])
    ok = _check("every drifted segment landed on its own boundary",
                starts == [c["start"] for c in skeleton],
                "got %s" % starts)
    orphan = [r for r in out if not r["snapped"]]
    ok &= _check("a segment with no boundary near it kept its own time",
                 len(orphan) == 1 and orphan[0]["start"] == 40.0)
    ok &= _check("starts stay in order",
                 all(out[i]["start"] <= out[i + 1]["start"] for i in range(len(out) - 1)))
    # two segments crowding one boundary must not both take it
    crowd = [_cue(6.05, 7.0, "a"), _cue(6.15, 7.2, "b")]
    got = align.snap_to_skeleton(crowd, skeleton, max_shift=1.0)
    ok &= _check("one boundary is used at most once",
                 len({r["start"] for r in got}) == 2, "got %s" % [r["start"] for r in got])
    return ok


def t_fit():
    """A known two-step offset schedule is recovered from noisy anchors."""
    rnd = random.Random(11)
    anchors = []
    for i in range(120):
        c = 5.0 + i * 6.0
        off = 129.0 if c < 400 else 141.5
        anchors.append((c, c + off + rnd.uniform(-0.08, 0.08), 1.0))
    for i in (20, 55, 90):                       # anchors that are simply wrong
        c = anchors[i][0]
        anchors[i] = (c, c + 37.0, 1.0)
    segs = align.merge_small(align.fit_segments(anchors))
    ok = _check("two stretches found", len(segs) == 2, "got %d" % len(segs))
    if len(segs) == 2:
        ok &= _check("first offset within 100 ms of the truth",
                     abs(segs[0]["offset"] - 129.0) < 0.1, "got %.3f" % segs[0]["offset"])
        ok &= _check("second offset within 100 ms of the truth",
                     abs(segs[1]["offset"] - 141.5) < 0.1, "got %.3f" % segs[1]["offset"])
        ok &= _check("the step lands between 6:34 and 6:46",
                     394.0 <= 0.5 * (segs[0]["to"] + segs[1]["from"]) <= 406.0,
                     "got %.1f" % (0.5 * (segs[0]["to"] + segs[1]["from"])))
    ok &= _check("the wrong anchors did not open a stretch of their own",
                 all(s["residual_rms"] < 0.2 for s in segs))
    return ok


def t_normalise():
    """The caption's own marks and a bracketed reading come off; the words do not."""
    pairs = [("１話から", "1話から"),
             ("澤村(さわむら)さん", "澤村さん"),
             ("そうだね→", "そうだね"),
             ("うん…　わかった。", "うんわかった"),
             ("ハーレム アニメ", "ハーレムアニメ"),
             ("ｱﾆﾒ", "アニメ")]
    ok = True
    for raw, want in pairs:
        got = normal.normalise(raw)
        ok &= _check("normalise %r" % raw, got == want, "got %r want %r" % (got, want))
    ok &= _check("the long-vowel mark survives", "ー" in normal.normalise("ハーレム"))
    ok &= _check("a split line still scores as a partial match",
                 normal.dice(normal.grams("あしたてんきになあれ"),
                             normal.grams("あしたてんきに")) > 0.5)
    return ok


def t_labels():
    """A bracketed name in front of words is a speaker; a bracketed sound is not."""
    text = ("1\n00:00:01,000 --> 00:00:03,000\n（詩織）おはよう\n\n"
            "2\n00:00:04,000 --> 00:00:06,000\n今日は早いね\n\n"
            "3\n00:00:20,000 --> 00:00:22,000\n（ドアの音）\n\n"
            "4\n00:00:23,000 --> 00:00:25,000\nもう行くの\n")
    d = tempfile.mkdtemp(prefix="speakers_selftest_")
    p = os.path.join(d, "sample.srt")
    timedtext._write(p, text)
    lines = timedtext.parse(p)
    ok = _check("four cues read", len(lines) == 4, "got %d" % len(lines))
    ok &= _check("the name in front of words was lifted out",
                 lines[0]["speaker"] == "詩織" and lines[0]["named"]
                 and "（" not in lines[0]["text"])
    ok &= _check("the bracketed sound is not a speaker", not lines[2]["named"])
    runs = timedtext.apply_runs(lines, gap_s=5.0)
    ok &= _check("the next line inherits the name",
                 lines[1]["speaker"] == "詩織" and lines[1]["carried"])
    ok &= _check("a long silence ends the run", lines[3]["speaker"] == "")
    ok &= _check("the counts add up",
                 runs["direct"] + runs["carried"] + runs["unnamed"] == len(lines))
    # a round trip through both writers keeps the times and the words
    timedtext.write_srt(lines, os.path.join(d, "out.srt"))
    timedtext.write_ass(lines, os.path.join(d, "out.ass"))
    again = timedtext.parse(os.path.join(d, "out.srt"))
    ok &= _check("srt round trip keeps every time and word",
                 [(r["start"], r["text"]) for r in again]
                 == [(r["start"], r["text"]) for r in lines])
    back = timedtext.parse(os.path.join(d, "out.ass"))
    ok &= _check("ass round trip keeps the speaker in the actor field",
                 [r["speaker"] for r in back] == [r["speaker"] for r in lines])
    return ok


def t_onsets():
    """Onsets alone recover an offset schedule with no text to help."""
    rnd = random.Random(3)
    ref = [round(4.0 + 3.7 * i + rnd.uniform(0, 1.5), 3) for i in range(200)]
    cand = []
    for t in ref:
        off = -125.0 if t < 500 else -137.0
        cand.append(round(t - off + rnd.uniform(-0.12, 0.12), 3))
    anchors, offsets = align.onset_anchors(sorted(cand), ref, max_offset=300.0, tol=0.5)
    segs = align.merge_small(align.fit_segments(anchors), min_anchors=8)
    ok = _check("the vote put both true offsets forward",
                any(abs(o + 125.0) < 1.5 for o in offsets)
                and any(abs(o + 137.0) < 1.5 for o in offsets),
                "got %s" % [round(o, 1) for o in offsets[:6]])
    ok &= _check("two stretches found on times alone", len(segs) == 2,
                 "got %d: %s" % (len(segs), [s["offset"] for s in segs]))
    if len(segs) == 2:
        ok &= _check("both offsets within 100 ms",
                     abs(segs[0]["offset"] + 125.0) < 0.1
                     and abs(segs[1]["offset"] + 137.0) < 0.1,
                     "got %.3f, %.3f" % (segs[0]["offset"], segs[1]["offset"]))
    return ok


def t_song_edges():
    """A song span moves off the dialogue it overlaps and never onto more."""
    cues = [{"from": 100.0, "to": 104.0, "text": "the line before"},
            {"from": 279.9, "to": 281.9, "text": ""}]
    # a mark laid 0.85 s inside the last line of the scene, which is what a
    # real ending chapter mark did
    got = songs.push_off_cues({"from": 281.0, "to": 373.0}, cues, margin=0.5)
    ok = _check("the start moved past the line it was inside",
                abs(got["from"] - 282.4) < 0.001, "got %.3f" % got["from"])
    ok &= _check("the end was left alone", abs(got["to"] - 373.0) < 0.001)
    ok &= _check("the cue that moved it is named", len(got["pushed"]) == 1)
    clear = songs.push_off_cues({"from": 142.0, "to": 232.0}, cues, margin=0.5)
    ok &= _check("a span inside nobody's line is untouched",
                 clear["from"] == 142.0 and clear["to"] == 232.0
                 and not clear["pushed"])
    return ok


def t_verdicts():
    """An answer that is not a verdict list is refused rather than stored."""
    good = spotcheck._parse('{"verdicts":[{"i":1,"verdict":"match","why":"same"}]}')
    ok = _check("a plain answer parses", good == [{"i": 1, "verdict": "match",
                                                   "why": "same"}])
    fenced = spotcheck._parse('```json\n[{"i":2,"verdict":"partial","why":"half"}]\n```')
    ok &= _check("a fenced answer parses", fenced
                 and fenced[0]["verdict"] == "partial")
    ok &= _check("prose is refused", spotcheck._parse("cue 1 looks fine") is None)
    ok &= _check("a verdict that is not one of the three is refused",
                 spotcheck._parse('[{"i":1,"verdict":"good","why":"x"}]') is None)
    rows = [{"verdict": "mismatch", "cer": 0.9}, {"verdict": "partial", "cer": 0.1},
            {"verdict": "match", "cer": 0.8}, {"verdict": "match", "cer": 0.05}]
    m = spotcheck.coincidence(rows, 0.25)
    ok &= _check("the flags against the caption count four ways",
                 (m["flagged_bad"], m["flagged_ok"], m["unflagged_bad"],
                  m["unflagged_ok"]) == (1, 1, 1, 1))
    ok &= _check("precision and recall follow from those four",
                 abs(m["precision"] - 0.5) < 1e-9 and abs(m["recall"] - 0.5) < 1e-9)
    return ok


def run():
    ok = True
    for fn in (t_normalise, t_labels, t_fit, t_snap, t_onsets, t_song_edges,
               t_verdicts):
        print("[%s] %s" % (fn.__name__, (fn.__doc__ or "").split("\n")[0]))
        ok &= bool(fn())
    print("\n%s" % ("all checks passed" if ok else "SOMETHING FAILED"))
    return 0 if ok else 1
