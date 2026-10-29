"""Match one of her generated lines to a recorded koikano clip.

The record holds 2509 of her lines, each with a clip id (MMK + six digits) and
an audio file. `tools/voice_index.py` folds those into
`data/vn/voice_index.json`: normalized text -> clip id. This module reads that
table and answers one question for the VN channel: is the line she is about to
speak one she has already spoken on tape, and if so which file.

Where her voice comes from is a mode, not a boolean (`tts.voice_mode`, and a
stage control the page holds):

  "tts"          never play from tape; the caller synthesises the line.
  "exact"        the line, normalized, is exactly a recorded line (NFKC width
                 fold, whitespace removed, edge punctuation and brackets
                 removed).
  "approximate"  exact, plus a pause-only near miss: the line is long enough,
                 one recorded line is within a high normalized edit-distance
                 ratio (>= 0.9), that line is the unique best by a margin
                 (`PARTIAL_MARGIN`), and the words themselves did not change --
                 only pauses may differ. A changed negation, name or number is
                 a different sentence and still misses.

A wrong clip is worse than silence. A line that normalizes to a tiny fragment
(`……っ` -> `っ`) is refused in every mode; real short utterances still play.
The legacy boolean `tts.clip_partial` seeds the mode where the config sets no
`voice_mode`: false -> exact, true -> approximate.

There is no substring match and no nearest neighbour, and a miss returns None
so the caller falls back to MiniMax synthesis.

A clip id she names herself (the persona writes `MMK000123`, or the line is
that id) is taken directly and wins over any text match -- in `exact` and
`approximate`; `tts` never plays from tape, a named id included.
"""

import io
import json
import os
import re
import unicodedata

# one clip: MMK + six digits. The record's one compound id
# (`MMK020136/MRA020088`) names two clips and does not match.
_CLIP_RE = re.compile(r"MMK\d{6}", re.IGNORECASE)

# The same edge set the build uses. Keep the two in step: a change here that is
# not made in `tools/voice_index.py` silently moves every key.
_EDGE = "。．.，,、！!？?…・:：;；「」『』（）()［］[]｛｝{}〈〉《》【】«»\"'“”‘’`~〜～"

# The three modes, and the legacy boolean that seeds one where a config sets no
# `voice_mode`: false -> exact, true -> approximate.
VOICE_MODES = ("tts", "exact", "approximate")

# Tier 3 (only in `approximate`). A near miss is played from tape only when the
# line is long enough that one pause is not the whole sentence, when the best
# normalized edit-distance ratio clears the bar, and when that best is unique
# by `PARTIAL_MARGIN`. The words must also be identical: `_spoken_text` drops
# pauses, so a difference in a particle or a digit is refused even at ratio 1.
PARTIAL_MIN_LEN = 8
PARTIAL_RATIO = 0.9
PARTIAL_MARGIN = 0.05

# Pauses, not words: two lines that differ only here are the same utterance.
_PAUSES = frozenset("、，,。．.…‥")

# A line that reduces to one of these is a recording artifact, not a sentence
# (`……っ` -> `っ`), and is refused in every mode. The guard is on the SPOKEN
# form, so "……" (empty after the edge strip) and "っー" are refused too, while
# "はい" and "そう" still play.
_FRAGMENT = "っッぁぃぅぇぉゃゅょァィゥェォャュョーー〜～"


def voice_mode(mode=None, partial=False):
    """The mode to use: an explicit one, else the legacy boolean, else exact."""
    if mode is None:
        return "approximate" if partial else "exact"
    if mode not in VOICE_MODES:
        raise ValueError("voice_mode must be tts, exact, or approximate")
    return mode


def _spoken_text(text):
    """The line with its pauses dropped: the words, for the words-only test."""
    return "".join(c for c in text if c not in _PAUSES)


def normalize(text):
    """The comparison form of a line (see `tools/voice_index.py:normalize`)."""
    t = unicodedata.normalize("NFKC", text or "")
    t = re.sub(r"[\s\u3000]+", "", t)
    return t.strip(_EDGE)


def _ratio(a, b):
    """1 - Levenshtein distance / the longer length: one edit in twenty is 0.95.

    A length gap alone bounds the ratio, so a pair whose lengths differ by more
    than `1 - PARTIAL_RATIO + PARTIAL_MARGIN` of the longer is refused before
    any rows are built. Two rows are kept, so the cost is O(len(a) * len(b)) in
    time and O(len(b)) in memory -- 2455 rows for a call, only on the
    approximate path."""
    if a == b:
        return 1.0
    la, lb = len(a), len(b)
    if not la or not lb:
        return 0.0
    top = max(la, lb)
    if abs(la - lb) / top > 1.0 - PARTIAL_RATIO + PARTIAL_MARGIN + 1e-12:
        return 0.0
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        cur = [i] + [0] * lb
        ca = a[i - 1]
        for j in range(1, lb + 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1,
                         prev[j - 1] + (0 if ca == b[j - 1] else 1))
        prev = cur
    return 1.0 - prev[lb] / top


class VoiceIndex:
    """The text -> clip table, loaded once, plus the clip files themselves."""

    def __init__(self, index_path, clip_dir):
        self.index_path = index_path
        self.clip_dir = clip_dir
        self.by_text = {}
        self.loaded = False
        self.notes = []
        self._load()

    def _load(self):
        if not os.path.exists(self.index_path):
            self.notes.append("no clip index at %s" % self.index_path)
            return
        try:
            with io.open(self.index_path, encoding="utf-8") as f:
                tree = json.load(f)
        except (OSError, ValueError) as e:
            self.notes.append("clip index unreadable: %s: %s" % (type(e).__name__, e))
            return
        for text, clip in (tree.get("by_text") or {}).items():
            key = normalize(text)
            if key and clip:
                self.by_text[key] = str(clip)
        self.loaded = True

    def size(self):
        return len(self.by_text)

    def clip_path(self, clip_id):
        """The file for one clip id, or None when it is not on disk."""
        m = _CLIP_RE.search(str(clip_id or ""))
        if not m:
            return None
        path = os.path.join(self.clip_dir, m.group(0).upper() + ".ogg")
        return path if os.path.isfile(path) else None

    def lookup(self, text, partial=False, mode=None):
        hit = self.lookup_detail(text, partial=partial, mode=mode)
        return hit[0] if hit else None

    def lookup_detail(self, text, partial=False, mode=None):
        """The best match as `(clip_id, matched_text, ratio, tier)`, or None.

        `matched_text` is the RECORDED line the clip speaks, so the stage can
        say what the closest real match was. The tier is 1 for the whole line,
        3 for the pause-only near miss (0 would be a clip id named outright,
        which `resolve_detail` handles)."""
        mode = voice_mode(mode, partial)
        if mode == "tts":
            return None
        n = normalize(text)
        spoken = _spoken_text(n)
        if len(spoken) < 2 or all(c in _FRAGMENT for c in spoken):
            return None
        clip = self.by_text.get(n)
        if clip:
            return (clip, n, 1.0, 1)
        if mode != "approximate" or len(spoken) < PARTIAL_MIN_LEN:
            return None
        best, best_ratio, second, best_text = None, 0.0, 0.0, ""
        for cand, c in self.by_text.items():
            r = _ratio(n, cand)
            if r > best_ratio:
                second, best_ratio, best, best_text = best_ratio, r, c, cand
            elif r > second:
                second = r
        if (best and best_ratio >= PARTIAL_RATIO
                and best_ratio - second + 1e-12 >= PARTIAL_MARGIN
                and spoken == _spoken_text(best_text)):
            return (best, best_text, round(best_ratio, 3), 3)
        return None

    def resolve_detail(self, text, clip_id=None, partial=False, mode=None):
        """The clip file AND what it matched, for the stage's own badge.

        `resolve` answers the only question the caller used to have -- which
        file to play. The stage also says which recorded line it is playing,
        which is this. `tts` never plays from tape, so it answers None before
        any id is considered."""
        mode = voice_mode(mode, partial)
        if mode == "tts":
            return None
        path = self.clip_path(clip_id) if clip_id else None
        if path:
            m = _CLIP_RE.search(str(clip_id or ""))
            return {"path": path, "clip": (m.group(0).upper() if m else ""),
                    "matched": "", "ratio": 1.0, "tier": 0}
        # an id the line IS, never one merely inside it: a compound or a longer
        # sentence that happens to contain a clip id is not a request for it
        named = _CLIP_RE.fullmatch(str(text or "").strip())
        if named:
            path = self.clip_path(named.group(0))
            if path:
                return {"path": path, "clip": named.group(0).upper(),
                        "matched": "", "ratio": 1.0, "tier": 0}
        hit = self.lookup_detail(text, mode=mode)
        if not hit:
            return None
        clip, matched, ratio, tier = hit
        path = self.clip_path(clip)
        if not path:
            return None
        return {"path": path, "clip": clip, "matched": matched,
                "ratio": ratio, "tier": tier}

    def resolve(self, text, clip_id=None, partial=False, mode=None):
        hit = self.resolve_detail(text, clip_id=clip_id, partial=partial, mode=mode)
        return hit["path"] if hit else None


def selftest():
    """`python channels/vn_voice.py <index> <clip_dir> "line"` -- one lookup."""
    import sys
    if len(sys.argv) < 4:
        print("usage: python channels/vn_voice.py <index.json> <clip_dir> <line>")
        return 2
    idx = VoiceIndex(sys.argv[1], sys.argv[2])
    line = sys.argv[3]
    hit = idx.resolve(line)
    print("[vn_voice] index=%d loaded=%s" % (idx.size(), idx.loaded))
    print("[vn_voice] %r -> %s" % (line, hit or "(no clip; TTS)"))
    return 0 if hit else 1


if __name__ == "__main__":
    raise SystemExit(selftest())