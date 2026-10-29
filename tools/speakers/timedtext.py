"""Reading and writing a timed line set, in the four formats that turn up.

A line is a plain dict so that it survives a round trip through JSON without a
schema:

    {"start": 4.74, "end": 7.87, "text": "...", "speaker": "...",
     "named": True, "style": "Default", "index": 0}

`named` is the difference between a name the file itself put on the line and a
name this tool carried forward from an earlier line. Attribution scored later
has to be able to tell the two apart, and a single `speaker` field cannot.

Two things here are not in the subtitle module the character processes use,
which is why they are written again rather than imported. The first is that
the styled formats are read by their own declared field order (`Format:` in
each section) rather than by counting commas, because a file that declares its
events in a different order is legal and does exist. The second is that the
speaker label a Japanese closed caption puts in brackets is read as a label
only when words follow it in the same cue: a bracketed run that IS the whole
cue is a sound, not somebody speaking.
"""
import io
import json
import os
import re

from . import normal

# a caption rip prefixes a speaker's first line in a run with the name in
# full-width brackets, sometimes with the reading inside: （霞ヶ丘詩羽(かす…)）
_LABEL = re.compile(r"^[（(]((?:[^（()）]|\([^()]*\)){1,24})[）)]")
_KANA_KANJI = re.compile(r"[぀-ゟ゠-ヿ一-鿿]")
# the head of a bracketed run that makes it an event rather than a person.
# A caption annotates the track as well as the talk, and both are bracketed.
_SOUND_TAIL = ("音", "声", "ざわめき", "歓声", "拍手", "笑い", "悲鳴", "鳴き",
               "ノイズ", "アナウンス", "ナレーション", "テレビ", "ラジオ",
               "メール", "着信", "効果")


def _t_srt(s):
    m = re.match(r"(\d+):(\d\d):(\d\d)[,.](\d{1,3})", s.strip())
    if not m:
        return None
    h, mi, se, ms = (int(x) for x in m.groups())
    return h * 3600 + mi * 60 + se + ms / 1000.0


def _t_ass(s):
    m = re.match(r"(\d+):(\d\d):(\d\d)[.:](\d{1,2})", s.strip())
    if not m:
        return None
    h, mi, se, cs = (int(x) for x in m.groups())
    return h * 3600 + mi * 60 + se + cs / 100.0


def fmt_srt(t):
    t = max(0.0, float(t))
    ms = int(round(t * 1000))
    return "%02d:%02d:%02d,%03d" % (ms // 3600000, ms // 60000 % 60, ms // 1000 % 60, ms % 1000)


def fmt_ass(t):
    t = max(0.0, float(t))
    cs = int(round(t * 100))
    return "%d:%02d:%02d.%02d" % (cs // 360000, cs // 6000 % 60, cs // 100 % 60, cs % 100)


def read_text(path):
    """The file as text. A rip off a Japanese service is usually UTF-8 with a
    byte-order mark, and an older one is sometimes the Windows Japanese
    codepage; neither announces itself, so both are tried."""
    raw = io.open(path, "rb").read()
    for enc in ("utf-8-sig", "cp932", "utf-16"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


# ------------------------------------------------------------------ parsing

def parse_cues(text):
    """SRT and VTT: blocks separated by a blank line, each with one timing
    line. The identifier line before the timing is optional in both formats
    and absent from neither in practice, so it is simply skipped."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    out = []
    for block in text.split("\n\n"):
        lines = [x for x in block.split("\n") if x.strip()]
        if not lines:
            continue
        span = None
        body = []
        for line in lines:
            if span is None and "-->" in line:
                a, _, z = line.partition("-->")
                start = _t_srt(a.strip().split(" ")[0])
                end = _t_srt(z.strip().split(" ")[0])
                if start is not None:
                    span = (start, end if end is not None else start)
                continue
            if span is not None:
                body.append(line)
        if span and body:
            out.append({"start": span[0], "end": span[1], "style": "",
                        "actor": "", "raw": "\n".join(body)})
    return out


def parse_styled(text):
    """ASS and SSA: the sections walked, the styles collected, the events read
    by the field order the file declares. Returns (events, styles)."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    section = ""
    style_fields = []
    event_fields = []
    styles = {}
    events = []
    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            section = s[1:-1].strip().lower()
            continue
        key, _, rest = s.partition(":")
        key = key.strip().lower()
        if key == "format":
            names = [x.strip().lower() for x in rest.split(",")]
            if "style" in section:
                style_fields = names
            elif "event" in section:
                event_fields = names
            continue
        if key == "style" and "style" in section:
            parts = rest.split(",")
            row = dict(zip(style_fields, [p.strip() for p in parts]))
            if row.get("name"):
                styles[row["name"]] = row
            continue
        if key == "dialogue" and "event" in section:
            fields = event_fields or ["layer", "start", "end", "style", "name",
                                      "marginl", "marginr", "marginv", "effect", "text"]
            parts = rest.split(",", len(fields) - 1)
            if len(parts) < len(fields):
                continue
            row = dict(zip(fields, parts))
            start = _t_ass(row.get("start", ""))
            end = _t_ass(row.get("end", ""))
            if start is None:
                continue
            events.append({"start": start, "end": end if end is not None else start,
                           "style": (row.get("style") or "").strip(),
                           "actor": (row.get("name") or "").strip(),
                           "effect": (row.get("effect") or "").strip(),
                           "raw": row.get("text", "")})
    return events, styles


def _label_of(raw):
    """(speaker, text) for one cue. The label is only the first bracketed run
    of the cue and only when words follow it, so a cue that is nothing but a
    bracketed sound keeps its brackets and gets no speaker."""
    first, _, rest = raw.partition("\n")
    m = _LABEL.match(first.strip())
    if not m:
        return "", raw
    who = normal.strip_markup(m.group(1)).strip()
    tail = first.strip()[m.end():].strip()
    if not who or not _KANA_KANJI.search(who):
        return "", raw
    if len(who) > 12:
        return "", raw
    if any(who.endswith(x) for x in _SOUND_TAIL):
        return "", raw
    if not tail and not rest.strip():
        return "", raw
    body = tail + ("\n" + rest if rest.strip() else "")
    return who, body


def _split_shared(raw):
    """One cue as [(speaker, text)], split wherever a new label starts.

    Two people answering each other inside two seconds share a cue, and the
    caption marks the second one with a label of its own part-way down. Keeping
    the whole cue under the first name would put an answer in the mouth of the
    person who was answered, which is the one mistake attribution must not
    make, so the cue is cut at every label.
    """
    parts = []
    who, body = _label_of(raw)
    lines = body.split("\n")
    cur_who, cur = who, []
    for k, part in enumerate(lines):
        m = _LABEL.match(part.strip()) if k else None
        if m:
            inner, tail = _label_of(part.strip() + ("\n" + "\n".join(lines[k + 1:])
                                                    if k + 1 < len(lines) else ""))
            if inner:
                if any(x.strip() for x in cur):
                    parts.append((cur_who, "\n".join(cur)))
                cur_who, cur = inner, [tail.split("\n")[0]]
                continue
        cur.append(part)
    parts.append((cur_who, "\n".join(cur)))
    return [(w, t) for w, t in parts if t.strip()]


def parse(path, keep_styles=None, split_shared=True):
    """A subtitle file as lines, in time order, with the labels lifted out.

    `keep_styles` restricts a styled file to a set of style names; without it
    every event is kept. A cue holding two labelled speakers becomes two lines
    whose share of the cue's span is their share of its characters, which is
    all the timing a single cue can offer.
    """
    text = read_text(path)
    low = path.lower()
    if low.endswith((".ass", ".ssa")) or "\nDialogue:" in text:
        events, _styles = parse_styled(text)
    else:
        events = parse_cues(text)
    events.sort(key=lambda r: (r["start"], r["end"]))
    lines = []
    for ev in events:
        if keep_styles is not None and ev["style"] not in keep_styles:
            continue
        parts = _split_shared(ev["raw"]) if split_shared else [_label_of(ev["raw"])]
        parts = [(w, normal.strip_markup(t)) for w, t in parts]
        parts = [(w, t) for w, t in parts if t]
        if not parts:
            continue
        widths = [max(1, len(t)) for _w, t in parts]
        total = float(sum(widths))
        span = max(0.0, ev["end"] - ev["start"])
        at = ev["start"]
        for (who, body), width in zip(parts, widths):
            dur = span * width / total
            speaker = who or ev.get("actor") or ""
            # a file this tool wrote says in the effect field which of the two
            # kinds of name a line carries, so a round trip does not turn a
            # name the run rule guessed into a name the caption printed
            effect = ev.get("effect") or ""
            lines.append({"start": round(at, 3), "end": round(at + dur, 3),
                          "text": body, "speaker": speaker,
                          "named": bool(speaker) and effect != "carried",
                          "carried": effect == "carried", "style": ev["style"],
                          "shared_cue": len(parts) > 1, "index": len(lines)})
            at += dur
    return lines


# ------------------------------------------------------------- the run rule

def apply_runs(lines, gap_s=5.0):
    """Carry a name forward over the lines that follow it.

    A Japanese closed caption names a speaker once, on the first line of a run,
    and leaves the rest of the run unnamed. Carrying the name forward is
    therefore right until something ends the run, and two things do: the next
    name, and a silence long enough that the caption would have named the
    speaker again on the other side of it. `gap_s` is that silence, measured
    from the end of one line to the start of the next.

    Returns the count of lines named directly, by the rule, and not at all.
    """
    direct = carried = unnamed = 0
    current = ""
    prev_end = None
    for ln in lines:
        if ln.get("carried"):
            # a name this tool already carried is not evidence for the next
            # line; the run is re-derived from the printed names alone
            ln["speaker"] = ""
            ln["carried"] = False
        if ln["named"]:
            current = ln["speaker"]
            direct += 1
        else:
            if prev_end is not None and (ln["start"] - prev_end) > gap_s:
                current = ""
            if current:
                ln["speaker"] = current
                ln["carried"] = True
                carried += 1
            else:
                ln["speaker"] = ""
                unnamed += 1
        ln.setdefault("carried", False)
        prev_end = ln["end"]
    return {"direct": direct, "carried": carried, "unnamed": unnamed,
            "gap_s": gap_s, "lines": len(lines)}


# ------------------------------------------------------------------ writing

_ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,60,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,3,1,2,60,60,45,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def write_srt(lines, path):
    parts = []
    for i, ln in enumerate(lines, 1):
        parts.append("%d\n%s --> %s\n%s\n" % (
            i, fmt_srt(ln["start"]), fmt_srt(ln["end"]), ln["text"]))
    _write(path, "\n".join(parts))
    return len(lines)


def write_ass(lines, path, header_notes=()):
    """The same lines as a styled file, the speaker in the Actor field.

    The Actor field is where a subtitle editor shows a name and where the rest
    of this pipeline will look for one, so a name carried by the run rule and a
    name the rip printed both land there; which of the two it was is in the
    effect field, so that nothing downstream has to guess.
    """
    out = ["".join("; %s\n" % n for n in header_notes) + _ASS_HEADER]
    for ln in lines:
        text = ln["text"].replace("\n", "\\N")
        effect = "carried" if ln.get("carried") else ("named" if ln.get("named") else "")
        out.append("Dialogue: 0,%s,%s,Default,%s,0,0,0,%s,%s\n" % (
            fmt_ass(ln["start"]), fmt_ass(ln["end"]),
            ln.get("speaker", ""), effect, text))
        # the other language's line for the same moment, if the caller kept
        # one. A comment row never renders, so a person can read it in an
        # editor and nothing downstream can mistake it for what was said.
        if ln.get("gloss"):
            out.append("Comment: 0,%s,%s,Default,,0,0,0,gloss,%s\n" % (
                fmt_ass(ln["start"]), fmt_ass(ln["end"]),
                ln["gloss"].replace("\n", " ")))
    _write(path, "".join(out))
    return len(lines)


def _write(path, text):
    d = os.path.dirname(os.path.abspath(path))
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def write_json(obj, path):
    _write(path, json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True))
