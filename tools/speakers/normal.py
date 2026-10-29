"""One normalised form of a Japanese caption line, and similarity over it.

Two rips of the same episode disagree on everything that is not a word. One
writes the reading of a name in brackets after it, one does not; one ends a
continued line with an arrow, one with a dash; one uses full-width digits and
one half-width; one puts an ideographic space where the other puts none. None
of that is what was said, and every one of it would show up as an error if the
text were compared raw.

So text is compared only after: markup removed, escapes turned into spaces,
compatibility characters folded (which is what turns full-width latin and
digits into ordinary ones, and half-width kana into full-width), the reading
in brackets dropped, the caption's own marks dropped, and then every
punctuation mark, symbol and space removed. What is left is kana, kanji,
latin letters and digits. The long-vowel mark and the repeat mark survive
that filter because Unicode files them as letters, which is right: they are
part of the word.

Similarity is the Dice coefficient over character 3-grams, which is the right
shape for this job -- one rip splits a sentence where the other does not, so
the two strings are often a whole and one of its halves, and an overlap
measure reads that as a partial match rather than as a miss.
"""
import re
import unicodedata

# ASS override blocks, and the markup an SRT or a VTT carries
_TAGS = re.compile(r"\{[^{}]*\}|<[^<>]*>")
_ESCAPES = re.compile(r"\\[Nnh]")
# a reading printed in brackets after the word it reads: 澤村(さわむら).
# Only a run that is entirely kana counts, so an ordinary aside in brackets
# is left alone.
_RUBY = re.compile(r"[(（]\s*[ぁ-ゟァ-ヿー]{1,16}\s*[)）]")
# the marks a caption uses for its own purposes rather than for the words:
# the arrow that says the sentence continues in the next cue, the dashes it
# uses for a trailing-off, the ellipses, and the note that says somebody is
# singing
_MARKS = "→⇒―─‐–—〜~…‥♪♬〝〟"


def strip_markup(s):
    """Display text: the words with the markup gone, the line breaks kept."""
    s = _TAGS.sub("", s or "")
    s = s.replace("\\N", "\n").replace("\\n", "\n").replace("\\h", " ")
    s = _RUBY.sub("", s)
    s = re.sub(r"[ \t]+", " ", s)
    return "\n".join(x.strip() for x in s.split("\n") if x.strip())


def normalise(s):
    """The comparison form: kana, kanji, letters and digits, nothing else."""
    s = _TAGS.sub("", s or "")
    s = _ESCAPES.sub(" ", s)
    s = unicodedata.normalize("NFKC", s)
    # NFKC has already turned （かな） into (かな), so the reading is dropped
    # after the fold rather than before it
    s = _RUBY.sub("", s)
    out = []
    for ch in s:
        if ch in _MARKS:
            continue
        cat = unicodedata.category(ch)
        if cat[0] in ("P", "S", "Z", "C"):
            continue
        out.append(ch)
    return "".join(out).lower()


def grams(s, n=3):
    """The character n-grams of a normalised string, as a set.

    A string shorter than n is its own single gram, so a one-word answer still
    has something to match on.
    """
    if not s:
        return set()
    if len(s) <= n:
        return {s}
    return {s[i:i + n] for i in range(len(s) - n + 1)}


def dice(a, b):
    """Overlap of two gram sets, 0 to 1."""
    if not a or not b:
        return 0.0
    return 2.0 * len(a & b) / float(len(a) + len(b))


def edits_banded(a, b, band=400):
    """Levenshtein between two long strings, computed near the diagonal only.

    Whole-episode text is thousands of characters, and the full table is tens
    of millions of cells. It is also almost entirely wasted: the two strings
    are the same episode in the same order, so the path never wanders far from
    the diagonal. The band is checked afterwards -- if the answer touches its
    edge, the band was too narrow and the distance is a bound rather than the
    distance, which the caller is told.
    """
    n, m = len(a), len(b)
    if abs(n - m) > band:
        band = abs(n - m) + 200
    big = n + m + 1
    prev = [big] * (m + 1)
    for j in range(0, min(m, band) + 1):
        prev[j] = j
    touched = False
    for i in range(1, n + 1):
        lo = max(1, i - band)
        hi = min(m, i + band)
        cur = [big] * (m + 1)
        cur[lo - 1] = i if lo == 1 else big
        for j in range(lo, hi + 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] != b[j - 1]))
        if hi == m and cur[m] >= big:
            touched = True
        prev = cur
    return prev[m], (touched or prev[m] >= big)


def edits(a, b):
    """Levenshtein distance between two strings, two rows of the table.

    Called once per pair of lines rather than once per episode, so the whole
    table is never built: the longest caption line in a rip is a few dozen
    characters.
    """
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]
