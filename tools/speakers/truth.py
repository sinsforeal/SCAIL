"""Reading a hand-written scene write-up as a scoring key, and scoring on it.

The write-up is prose with the timed lines mixed in. A timed line is a
timestamp in brackets, then a speaker in brackets, then what was said; the text
runs on to the following lines when the person kept talking, and those
continuation lines are recognised by carrying Japanese script, which the prose
around them does not.

Two things are scored here. Whether the aligned file has a cue at the moment
the key says a line starts, with the right words on it -- that is the
alignment, checked against a person's reading of the video rather than against
another subtitle file. And whether the name the rip put on that cue is the name
the key gives -- that is the free share of speaker attribution, the baseline
that voice work has to beat before it is worth doing.

The key's timestamps are minutes and seconds with nothing after the point, so a
cue that starts at 6:28.6 is written 6:28 and is six tenths away from its own
stated time. Scoring at half a second therefore measures the key's precision
rather than the alignment's, and it does: the very file the key was pinned to
scores 30 of 54 that way. Both numbers are reported, the half second because it
was asked for and the stated second because it is what the key can express, and
the file the key was pinned to is scored alongside as the ceiling.

The speaker is only asked for on the cue the text found, never on whichever cue
is nearest in time. Two lines a second apart that both contain the same phrase
are the ordinary shape of an argument, and taking the nearer one by clock alone
put an answer in the mouth of the person answered.
"""
import io
import re

from . import normal

_TIMED = re.compile(r"^\[(\d{1,2}):(\d\d)\]\s*\[([^\]]+)\]\s*(.*)$")
_JA = re.compile(r"[぀-ゟ゠-ヿ一-鿿]")


def read_key(path):
    """The timed lines of the write-up, in order."""
    rows = []
    for raw in io.open(path, encoding="utf-8").read().replace("\r", "").split("\n"):
        m = _TIMED.match(raw.strip())
        if m:
            rows.append({"t": int(m.group(1)) * 60 + int(m.group(2)),
                         "speaker": m.group(3).strip(), "text": m.group(4).strip()})
            continue
        s = raw.strip()
        # A line runs on when the person kept talking, and those lines are
        # Japanese while the write-up's own prose is English. Merely
        # CONTAINING Japanese is not enough to tell them apart: a paragraph
        # of stage direction quotes a phrase in Japanese, and that paragraph
        # was being read as the rest of somebody's line.
        if rows and s and not s.startswith("[") and _mostly_ja(s) \
                and not s.lower().startswith("scene"):
            rows[-1]["text"] += " " + s
    return rows


def _mostly_ja(s):
    body = [c for c in s if not c.isspace()]
    if not body:
        return False
    return sum(1 for c in body if _JA.match(c)) / float(len(body)) > 0.6


def _text_ok(cue_text, key_text):
    """The cue says part of what the key says.

    A key line is often a whole speech that the caption file splits over three
    cues, so the cue's words being inside the key's words is the match that
    matters; the overlap score is the fallback for a cue whose wording differs
    from the key's by a character or two.
    """
    a = normal.normalise(cue_text)
    b = normal.normalise(key_text)
    if not a or not b:
        return False, 0.0
    if a in b or b in a:
        return True, 1.0
    s = normal.dice(normal.grams(a), normal.grams(b))
    return s >= 0.5, round(s, 3)


def _pick(lines, k, lo, hi):
    """The cue for a key line: in the window, and saying what the key says.

    A cue whose words match is preferred over a cue that is merely nearer,
    because the window is wider than the gap between two lines of an argument.
    """
    best_any = None
    best_ok = None
    for ln in lines:
        d = ln["start"] - k["t"]
        if not (lo <= d <= hi):
            continue
        ok, sim = _text_ok(ln["text"], k["text"])
        if best_any is None or abs(d) < abs(best_any[0]["start"] - k["t"]):
            best_any = (ln, ok, sim)
        if ok and (best_ok is None or abs(d) < abs(best_ok[0]["start"] - k["t"])):
            best_ok = (ln, ok, sim)
    return best_ok or best_any


def score(lines, key, name_map, lo=-0.5, hi=0.5):
    """Every key line: the cue found for it, and the name on that cue."""
    rows = []
    for k in key:
        got = _pick(lines, k, lo, hi)
        cue, ok, sim = got if got else (None, False, 0.0)
        raw = "" if cue is None else (cue.get("speaker") or "")
        who = name_map.get(raw, "")
        how = "none"
        if cue is not None and raw:
            how = "carried" if cue.get("carried") else "named"
        rows.append({
            "t": k["t"], "want": k["speaker"], "key": k["text"],
            "cue_start": None if cue is None else cue["start"],
            "cue_text": "" if cue is None else cue["text"],
            "hit": bool(cue is not None and ok), "sim": sim,
            "reason": "" if cue is not None and ok else
                      ("no cue in the window" if cue is None
                       else "the nearest cue says something else"),
            "raw": raw, "got": who or raw, "how": how,
            "right": bool(who and who.lower() == k["speaker"].lower()),
        })
    return rows
