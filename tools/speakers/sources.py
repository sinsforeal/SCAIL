"""Where an episode's subtitles come from, and the timing skeleton in the video.

Two sources, both on this machine and neither needing the network: the files
beside the video, and the archive mirror's folder for the work. Both are walked
the way the character processes' own subtitle module walks them -- same stem
beside the video with or without a language suffix, a `Subs` folder beside it,
then the mirror's folder filtered to the episode number.

The third source is inside the video. A fansub release carries its English
track as a styled subtitle, and even though its words are no use for a Japanese
line set, the times are: somebody typed a cue boundary at the start of every
spoken line while watching this exact cut. Stripped of the styles that are
signs and song, that is a timing skeleton of the episode.
"""
import os
import re
import subprocess

from . import timedtext

SUB_EXT = (".srt", ".ass", ".ssa", ".vtt")
# a style whose name says it is not somebody speaking. A fansub names its
# dialogue styles after the show or after nothing at all, and everything else
# it names after the job: the sign it is covering, the song it is subtitling,
# the episode title card.
_NOT_DIALOGUE = re.compile(
    r"(sign|typeset|karaok|song|lyric|romaji|kanji|title|credit|staff|cast|"
    r"note|tl ?note|\bop\b|\bed\b|opening|ending|insert|logo|caption|scroll)",
    re.I)
# an override that places text somewhere on the picture. The dialogue style
# already puts a spoken line at the bottom, so a line that asks to be put
# somewhere else is a sign in a dialogue style, which is how a fansub typesets
# a small one rather than declaring a style for it.
_PLACED = re.compile(r"\\(pos|move|an[0-9]|org|clip|iclip|p[1-9]|fad)")


def beside(video):
    """Subtitle files next to the video, best guess first."""
    d = os.path.dirname(os.path.abspath(video))
    stem = os.path.splitext(os.path.basename(video))[0].lower()
    out = []
    for folder in (d, os.path.join(d, "Subs"), os.path.join(d, "subs")):
        if not os.path.isdir(folder):
            continue
        for name in sorted(os.listdir(folder)):
            p = os.path.join(folder, name)
            if not os.path.isfile(p) or not name.lower().endswith(SUB_EXT):
                continue
            base = os.path.splitext(name)[0].lower()
            base = re.sub(r"\.(ja|jp|jpn|japanese|en|eng|english)$", "", base)
            if base == stem or base.startswith(stem):
                out.append(p)
    return out


def in_mirror(folder, episode):
    """The mirror's files for one episode of one work.

    The episode number is read off the filename the way the archive's own names
    carry it, and a file whose number cannot be read is offered anyway: the
    folder is one work, so a stray naming scheme is more likely to be this
    episode than to be nothing.
    """
    if not folder or not os.path.isdir(folder):
        return []
    out = []
    for name in sorted(os.listdir(folder)):
        p = os.path.join(folder, name)
        if not os.path.isfile(p) or not name.lower().endswith(SUB_EXT):
            continue
        if episode_of(name) == episode:
            out.append(p)
    return out


def episode_of(name):
    """The episode number a subtitle filename claims, or None."""
    s = str(name or "")
    m = re.search(r"S(\d{1,2})E(\d{1,3})", s, re.I)
    if m:
        return int(m.group(2))
    stem = re.sub(r"\[[^\]]*\]", " ", s)
    stem = re.sub(r"\([^)]*\)", " ", stem)
    stem = re.sub(r"\.(srt|ass|ssa|vtt)$", "", stem, flags=re.I)
    stem = re.sub(r"\.(ja|jp|jpn|en|eng)$", "", stem, flags=re.I)
    m = re.search(r"[-–—]\s*E?(\d{1,3})(?:v\d)?\s*$", stem.strip())
    if m:
        return int(m.group(1))
    m = re.search(r"第(\d{1,3})話", s)
    if m:
        return int(m.group(1))
    return None


def japanese_share(lines):
    """Share of lines carrying Japanese script. A folder marked Japanese is
    not proof: one work's files in the archive are somebody's Chinese
    listening script, and a dual-language file reads about a half."""
    if not lines:
        return 0.0
    n = sum(1 for ln in lines if re.search(r"[぀-ゟ゠-ヿ一-鿿]", ln["text"]))
    return n / float(len(lines))


# ------------------------------------------------------- the video's own track

def probe_streams(video):
    """[(index, codec, language, title)] for every subtitle stream."""
    cmd = ["ffprobe", "-v", "error", "-select_streams", "s",
           "-show_entries", "stream=index,codec_name:stream_tags=language,title",
           "-of", "default=noprint_wrappers=1:nokey=0", video]
    txt = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                         errors="replace").stdout
    rows = []
    cur = {}
    for line in txt.split("\n"):
        k, _, v = line.strip().partition("=")
        if k == "index" and cur:
            rows.append(cur)
            cur = {}
        if k:
            cur[k.replace("TAG:", "")] = v
    if cur:
        rows.append(cur)
    return [{"index": int(r["index"]), "codec": r.get("codec_name", ""),
             "language": r.get("language", ""), "title": r.get("title", "")}
            for r in rows if r.get("index", "").isdigit()]


def extract_stream(video, index, out_path, redo=False):
    """One subtitle stream copied out of the container, cached on disk."""
    if os.path.exists(out_path) and not redo:
        return out_path
    d = os.path.dirname(os.path.abspath(out_path))
    if d and not os.path.isdir(d):
        os.makedirs(d)
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", video,
           "-map", "0:%d" % index, "-c:s", "copy", out_path]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if r.returncode != 0 or not os.path.exists(out_path):
        raise RuntimeError("ffmpeg could not extract stream %d: %s"
                           % (index, (r.stderr or "").strip()[:300]))
    return out_path


def dialogue_styles(path):
    """(kept, dropped) style names of a styled subtitle file."""
    events, styles = timedtext.parse_styled(timedtext.read_text(path))
    names = sorted(set(list(styles) + [e["style"] for e in events]))
    keep = [n for n in names if not _NOT_DIALOGUE.search(n)]
    drop = [n for n in names if _NOT_DIALOGUE.search(n)]
    return keep, drop


def skeleton(path):
    """The spoken-cue onsets of a styled subtitle file, and what was dropped.

    What this is for is the timings: somebody typed a cue boundary at the start
    of every spoken line while watching this exact cut, and that is a record of
    when people speak that no other file on disk has. The words come back with
    them under the name `gloss` and under that name only. They are the wrong
    language for the line set and they are somebody's translation rather than a
    transcript, so nothing downstream may take them for what was said; they are
    there to be read beside the Japanese by a person checking the result.
    """
    keep, drop = dialogue_styles(path)
    events, _styles = timedtext.parse_styled(timedtext.read_text(path))
    cues = []
    placed = 0
    styled_out = 0
    for ev in sorted(events, key=lambda r: r["start"]):
        if ev["style"] not in keep:
            styled_out += 1
            continue
        if _PLACED.search(ev["raw"] or ""):
            placed += 1
            continue
        if not timedtext.normal.strip_markup(ev["raw"]):
            continue
        cues.append({"start": round(ev["start"], 3), "end": round(ev["end"], 3),
                     "actor": ev["actor"],
                     "gloss": timedtext.normal.strip_markup(ev["raw"]).replace("\n", " ")})
    # cues that start together are one line split over two rows on screen
    merged = []
    for c in cues:
        if merged and abs(c["start"] - merged[-1]["start"]) < 0.04:
            merged[-1]["end"] = max(merged[-1]["end"], c["end"])
            merged[-1]["gloss"] = (merged[-1]["gloss"] + " " + c["gloss"]).strip()
            continue
        merged.append(c)
    return {"cues": merged, "kept_styles": keep, "dropped_styles": drop,
            "events": len(events), "dropped_by_style": styled_out,
            "dropped_as_placed": placed,
            "actors": sorted({c["actor"] for c in merged if c["actor"]})}
