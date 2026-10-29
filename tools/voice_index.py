"""Build the text -> koikano clip index for her recorded lines.

Every line she spoke in the koikano record carries a `voice` id (MMK + six
digits) and a clip file of that name in `by_character/MOMOKA_百花/voice`. This
tool reads the record, keeps her lines, normalizes the text, and writes one
lookup table `data/vn/voice_index.json`. The VN channel reads that table and
plays the recorded clip when her generated line is one she has on tape, and
falls back to MiniMax synthesis otherwise (`channels/vn_voice.py`).

The corpus is read-only. This tool writes only the index it names:

    python tools/voice_index.py                 # build data/vn/voice_index.json
    python tools/voice_index.py --check         # fail if the file is stale
    python tools/voice_index.py --out scratch.json --corpus <path> --voice-dir <dir>

Standard library only. A clip id that is not `MMK` + six digits (the record
holds one compound id, `MMK020136/MRA020088`) is skipped: it names two clips
and would be a guess.
"""

import argparse
import datetime
import io
import json
import os
import re
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

DEFAULT_CORPUS = (r"F:\REPS2\clipboard capture (kirikiri)\extracted_games\koikano"
                  r"\koikano_work\game_logic.jsonl")
DEFAULT_VOICE_DIR = (r"F:\REPS2\clipboard capture (kirikiri)\extracted_games\koikano"
                     r"\by_character\MOMOKA_百花\voice")
DEFAULT_OUT = os.path.join(ROOT, "data", "vn", "voice_index.json")

# `voice` ids that are hers: MMK + six digits. Longer, compound or empty ids
# are not a single clip and are refused rather than resolved to a guess.
_CLIP_RE = re.compile(r"^MMK\d{6}$")

# What is stripped from both ends of a line before it is compared. The record
# wraps her lines in 「」 and ends them with 。 or ！; a generated line carries its
# own punctuation, so the edge marks are noise. Internal marks are kept: two
# lines that differ inside are two lines.
_EDGE = "。．.，,、！!？?…‥・:：;；「」『』（）()［］[]｛｝{}〈〉《》【】«»\"'“”‘’`~〜～"


def normalize(text):
    """The comparison form of a line: width-folded, no whitespace, no edge marks.

    NFKC folds a full-width Latin/digit/kana to its ordinary form and the
    half-width kana to full width, so two spellings of one line compare equal.
    Whitespace is removed everywhere, edge punctuation only at the ends.
    """
    t = unicodedata.normalize("NFKC", text or "")
    t = re.sub(r"[\s\u3000]+", "", t)
    return t.strip(_EDGE)


def _is_hers(row):
    """A 百花 line, or any line whose voice id is an MMK clip."""
    if str(row.get("speaker") or "") == "百花":
        return True
    return _CLIP_RE.match(str(row.get("voice") or "").strip().upper()) is not None


def read_lines(corpus):
    """Every (clip_id, text) of hers in the record, in file order."""
    out = []
    with io.open(corpus, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            cid = str(row.get("voice") or "").strip().upper()
            if not _CLIP_RE.match(cid):
                continue
            if not _is_hers(row):
                continue
            out.append((cid, str(row.get("text") or "")))
    return out


def build(corpus, voice_dir):
    """The index tree. Deterministic: ties are broken by file order."""
    rows = read_lines(corpus)
    on_disk = set()
    if os.path.isdir(voice_dir):
        on_disk = {n[:-4].upper() for n in os.listdir(voice_dir)
                   if n.lower().endswith(".ogg")}

    by_text = {}          # normalized text -> the clip that stands for it
    by_clip = {}          # clip id -> normalized text
    multi = {}            # normalized text -> every clip carrying it
    missing = []
    for cid, text in rows:
        n = normalize(text)
        if not n:
            continue
        by_clip.setdefault(cid, n)
        multi.setdefault(n, [])
        if cid not in multi[n]:
            multi[n].append(cid)
        if n not in by_text:
            # the first line of the record that says this stands for it, so a
            # rebuild over the same corpus gives the same file
            by_text[n] = cid
        if on_disk and cid not in on_disk:
            missing.append(cid)

    duplicates = {n: ids for n, ids in multi.items() if len(ids) > 1}
    # only clips whose file is on disk may be handed to the player; anything
    # else is dropped here rather than discovered at play time
    if on_disk:
        for n, cid in list(by_text.items()):
            if cid not in on_disk:
                alt = next((c for c in multi.get(n, []) if c in on_disk), "")
                if alt:
                    by_text[n] = alt
                else:
                    del by_text[n]
    return {
        "built": datetime.datetime.now().isoformat(timespec="seconds"),
        "source": corpus,
        "voice_dir": voice_dir,
        "lines": sum(1 for _, t in rows if normalize(t)),
        "texts": len(by_text),
        "duplicates": len(duplicates),
        "missing_clips": len(set(missing)),
        "by_text": by_text,
        "by_clip": by_clip,
        "multi": duplicates,
    }


def _write(path, tree):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(tree, ensure_ascii=False, indent=1) + "\n")
    os.replace(tmp, path)


def _summary(tree):
    return ("%d line(s) with a clip id, %d distinct text(s), %d text(s) said "
            "more than once, %d clip id(s) not on disk"
            % (tree["lines"], tree["texts"], tree["duplicates"],
               tree["missing_clips"]))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--corpus", default=DEFAULT_CORPUS)
    ap.add_argument("--voice-dir", default=DEFAULT_VOICE_DIR)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--check", action="store_true",
                    help="build in memory and fail if the file on disk differs")
    args = ap.parse_args()

    if not os.path.exists(args.corpus):
        print("  FAIL corpus not found: %s" % args.corpus)
        return 1
    tree = build(args.corpus, args.voice_dir)

    if args.check:
        if not os.path.exists(args.out):
            print("  FAIL no index at %s" % args.out)
            return 1
        with io.open(args.out, encoding="utf-8") as f:
            have = json.load(f)
        # `built` is a timestamp and is allowed to differ; everything else is
        # the build's own output and must match
        have.pop("built", None)
        fresh = dict(tree)
        fresh.pop("built", None)
        if have != fresh:
            print("  FAIL index is stale: %s" % args.out)
            return 1
        print("  ok   index is current: %s" % _summary(tree))
        return 0

    _write(args.out, tree)
    print("  wrote %s" % args.out)
    print("  %s" % _summary(tree))
    return 0


if __name__ == "__main__":
    sys.exit(main())
