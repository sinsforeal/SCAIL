"""Where the songs are in an episode, and the audio with them silenced.

A speech recogniser listens to an opening or an ending song and writes the
lyrics down as if somebody had said them. Those words are not dialogue, they
land in the middle of the line set, and every later step -- alignment,
attribution, the card -- carries them. They are also the one part of an episode
whose position is written down somewhere: a release with chapter marks says
where the songs are, and a fansub's styled English track says it a second way,
because the person who typed it gave the song its own styles.

Two rules, in that order. **The chapter marks win when the file has them**: a
chapter titled for the opening or the ending is the authored boundary of the
song, and it covers the instrumental head and tail that no lyric line reaches.
Otherwise the song styles of the English track are used, clustered into runs,
because a lyric line is only the sung part and the gaps between the lines
belong to the same song.

Whichever rule decides a span, its edges are then pushed off any dialogue cue
of the English track they land inside. A chapter mark is authored for the
picture and can fall a second or two into the last line of the scene before it:
the ending mark of this experiment's first episode sits 0.85 s inside a cue.
Silencing over a spoken line is the one failure this whole step exists to
avoid, so an edge that overlaps a dialogue cue moves to the far side of it
with a margin.

The audio is SILENCED and not cut out, so every timestamp the recogniser
produces still means the same moment of the episode as before, and a transcript
made from cut audio can be compared with one made from the whole of it and with
a caption of the same video, line for line, with no offset anywhere.
"""
import os
import re
import subprocess

from . import timedtext

# a chapter title that names a song. A release titles them in English however
# it likes, and the two-letter forms are what a Japanese release usually uses.
_SONG_CHAPTER = re.compile(r"(opening|ending|\bop\b|\bed\b)", re.I)
# a style name that says the line is a song lyric rather than a sign or a
# title card. `sources._NOT_DIALOGUE` drops all three kinds together, which is
# right for a timing skeleton and wrong here: silencing the audio under an
# episode's title card would silence the dialogue playing over it.
_SONG_STYLE = re.compile(r"(\bop\b|\bed\b|opening|ending|insert|song|lyric|"
                         r"karaok|romaji|kanji|flower)", re.I)
# the largest silence inside one song, used to decide whether two lyric lines
# belong to the same run. An instrumental break in an anime opening is a few
# seconds; the distance between the opening and the ending is minutes.
_CLUSTER_GAP = 30.0
# a run of lyric lines shorter than this is not a song. An insert line or a
# stray credit in a song style would otherwise silence a piece of the episode.
_MIN_SONG = 30.0
# how far an edge is moved past a dialogue cue it overlaps. The recogniser
# needs the whole word, and its own voice detector opens its window slightly
# before the sound starts.
_EDGE_MARGIN = 0.5


def chapters(video):
    """[{"from", "to", "title"}] for the video's chapter marks."""
    cmd = ["ffprobe", "-v", "error", "-show_chapters",
           "-of", "compact=p=0:nk=0:e=none", video]
    txt = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                         errors="replace").stdout
    out = []
    for line in txt.split("\n"):
        row = {}
        for field in line.strip().split("|"):
            k, _, v = field.partition("=")
            row[k.strip()] = v.strip()
        if "start_time" not in row:
            continue
        try:
            out.append({"from": float(row["start_time"]),
                        "to": float(row["end_time"]),
                        "title": row.get("tag:title", "")})
        except ValueError:
            continue
    return out


def song_chapters(video):
    """The chapter spans whose title names a song."""
    return [dict(c, rule="chapter mark titled %r" % c["title"])
            for c in chapters(video) if _SONG_CHAPTER.search(c["title"] or "")]


def song_style_spans(ass_path):
    """Runs of lyric lines in the styled English track, as spans.

    Every event in a song style is taken, whatever its text, and the events are
    then joined into runs. A karaoke track writes the same line two or three
    times over -- once per layer, once romanised and once translated -- so the
    events overlap heavily and the union is what is wanted, not the count.
    """
    events, _styles = timedtext.parse_styled(timedtext.read_text(ass_path))
    spans = sorted((e["start"], e["end"]) for e in events
                   if _SONG_STYLE.search(e["style"] or ""))
    runs = []
    for a, z in spans:
        if runs and a - runs[-1]["to"] <= _CLUSTER_GAP:
            runs[-1]["to"] = max(runs[-1]["to"], z)
            runs[-1]["events"] += 1
            continue
        runs.append({"from": a, "to": z, "events": 1,
                     "rule": "run of lyric lines in the English track"})
    return [r for r in runs if r["to"] - r["from"] >= _MIN_SONG]


def dialogue_cues(ass_path):
    """The spans of the English track that carry dialogue timing.

    Not the timing skeleton: an event in a dialogue style whose text is empty
    is dropped from the skeleton, because it says nothing to read, and it is
    kept here, because the person who typed it was marking a span of speech.
    The last one of this experiment's first episode is exactly that, and it is
    what the ending chapter mark cuts into.
    """
    from . import sources
    events, _styles = timedtext.parse_styled(timedtext.read_text(ass_path))
    keep, _drop = sources.dialogue_styles(ass_path)
    return [{"from": e["start"], "to": e["end"],
             "text": timedtext.normal.strip_markup(e["raw"])}
            for e in sorted(events, key=lambda r: r["start"])
            if e["style"] in keep and not sources._PLACED.search(e["raw"] or "")]


def push_off_cues(span, cues, margin=_EDGE_MARGIN):
    """Move a span's edges out of any dialogue cue they land inside.

    The start moves forward past the cue it is inside, the end moves back
    before its cue, so the span can only ever shrink. A span that shrinks to
    nothing would mean a song mark laid over a scene, which is a fault worth
    seeing rather than a case to handle, so it is left inverted for the caller
    to refuse.
    """
    out = dict(span)
    moved = []
    for c in cues:
        if c["from"] < out["from"] < c["to"]:
            out["from"] = round(c["to"] + margin, 3)
            moved.append({"edge": "start", "cue_from": c["from"], "cue_to": c["to"],
                          "cue_text": c["text"][:60]})
        if c["from"] < out["to"] < c["to"]:
            out["to"] = round(c["from"] - margin, 3)
            moved.append({"edge": "end", "cue_from": c["from"], "cue_to": c["to"],
                          "cue_text": c["text"][:60]})
    out["pushed"] = moved
    return out


def find_spans(video, ass_path):
    """The song spans of one episode, by whichever rule the file supports."""
    spans = song_chapters(video)
    how = "the video's own chapter marks"
    if not spans and ass_path and os.path.exists(ass_path):
        spans = song_style_spans(ass_path)
        how = "the song styles of the English track"
    cues = dialogue_cues(ass_path) if ass_path and os.path.exists(ass_path) else []
    spans = [push_off_cues(s, cues) for s in spans]
    return {"spans": spans, "decided_by": how, "dialogue_cues": len(cues)}


# ------------------------------------------------------------------- audio

def _filter(spans):
    """One ffmpeg volume filter that mutes every span and touches nothing else."""
    parts = "+".join("between(t,%.3f,%.3f)" % (s["from"], s["to"]) for s in spans)
    return "volume=enable='%s':volume=0" % parts


def write_audio(video, out_path, spans=(), redo=False):
    """The episode's first audio track as 16 kHz mono, songs muted if given.

    16 kHz mono signed 16-bit is what the recogniser resamples to anyway, so
    handing it that costs nothing and makes the cut file and the whole file
    identical in every respect except the muting.
    """
    if os.path.exists(out_path) and not redo:
        return out_path, None
    d = os.path.dirname(os.path.abspath(out_path))
    if d and not os.path.isdir(d):
        os.makedirs(d)
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", video, "-map", "0:a:0"]
    af = _filter(spans) if spans else ""
    if af:
        cmd += ["-af", af]
    cmd += ["-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", out_path]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if r.returncode != 0 or not os.path.exists(out_path):
        raise RuntimeError("ffmpeg could not write %s: %s"
                           % (out_path, (r.stderr or "").strip()[:300]))
    return out_path, af


def loudness(path, spans):
    """Signal level inside each song span and either side of it.

    The proof that the muting landed where it was meant to, and it is measured
    from the samples rather than asked of a filter: a span reading exactly zero
    and the seconds on both sides of it reading the ordinary level of the
    episode is the whole of what the muted file claims to be.
    """
    import wave
    import numpy
    with wave.open(path, "rb") as f:
        rate = f.getframerate()
        raw = f.readframes(f.getnframes())
    a = numpy.frombuffer(raw, dtype=numpy.int16).astype(numpy.float32) / 32768.0

    def _rms(t0, t1):
        chunk = a[max(0, int(t0 * rate)):max(0, int(t1 * rate))]
        return float(numpy.sqrt((chunk * chunk).mean())) if chunk.size else 0.0

    rows = []
    for s in spans:
        # measured a quarter second in from each edge: the volume filter turns
        # on and off at an audio frame boundary, so up to one frame of about
        # 60 ms survives at each end of the span, and measuring the raw edges
        # reports that frame rather than the muting
        rows.append({"where": "inside %.3f..%.3f" % (s["from"], s["to"]),
                     "rms": _rms(s["from"] + 0.25, s["to"] - 0.25)})
        rows.append({"where": "the 5 s before it",
                     "rms": _rms(s["from"] - 5.0, s["from"])})
        rows.append({"where": "the 5 s after it",
                     "rms": _rms(s["to"], s["to"] + 5.0)})
    rows.append({"where": "the whole file", "rms": _rms(0, len(a) / float(rate))})
    return rows
