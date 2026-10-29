"""Every quoted line in a persona file, counted against the tape.

Why this exists. A line quoted in a persona file becomes a catchphrase
regardless of how rare it is in the material -- six models proved it in one
afternoon (`docs/yukarin-voice-models.md` §3). The control speech guide
illustrated her self-cancel with 「あ、今のなし」, which appears **zero** times in
47 hours, and a model reproduced it verbatim on air. 「エロくない。エレガンス。」
occurs once and came back three times in four opportunities.

This is the same fault `docs/yukarin.md` §13 already overruled one level up,
where his character card turned a twice-in-forty-seven-hours age gag into
「永遠の17歳を自称する」. The card did it to the tape; the style file did it to
the card's correction; the bible does it too. So: count them.

A count is not a verdict. A line said once can be worth quoting -- it may be
the only time she ever had the occasion. What the file must not do is quote it
in a way that reads as a habit. The three honest outcomes are KEEP (frequent
enough to be a habit), MARK (real but singular, and labelled as such in the
file so it is read as an example of a KIND of move), and CUT (not hers at all).

    python tools/quote_audit.py                              # every persona file
    python tools/quote_audit.py --file prompts_yukarin/voice_as_she_writes_in_text/bible.md
    python tools/quote_audit.py --min 3                      # stricter habit line
"""

import argparse
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

FILES = ["prompts_yukarin/voice_as_she_writes_in_text/bible.md",
         "prompts_yukarin/voice_as_she_writes_in_text/style.md",
         "prompts_yukarin/voice_as_she_writes_in_text/style_candidate.md",
         "prompts_yukarin/voice_replica_in_text/bible.md",
         "prompts_yukarin/voice_replica_in_text/style.md"]

CORPUS = "yukarin/corpus"


def her_cues():
    """(ep, cue index, text) for every cue attributed to HER.

    The same split `yukarin/sheet/bounds.json` uses. Counting over the whole
    transcript instead would credit her with the room's lines, which is how
    「わよ」 got read as her idol register when it is 0.9 per 100k for her
    against 7.7 for everyone else.
    """
    out = []
    for f in sorted(os.listdir(CORPUS)):
        if not f.endswith(".jsonl"):
            continue
        ep = f[2:-6]
        cues = [json.loads(l) for l in io.open(os.path.join(CORPUS, f), encoding="utf-8")]
        attr = json.load(io.open(os.path.join(CORPUS, "attr", f"ep{ep}.json"), encoding="utf-8"))
        lab = {}
        for s in attr:
            for i in range(s["a"], s["b"] + 1):
                lab[i] = s["label"]
        for c in cues:
            if lab.get(c["i"]) == "her":
                out.append((ep, c["i"], c["text"]))
    return out


def every_cue():
    """Every cue in the transcript, whoever said it. Only needed for the half
    of a recorded exchange that is not hers: a demonstration of her on the
    phone has to quote the person on the other end to be readable."""
    out = []
    for f in sorted(os.listdir(CORPUS)):
        if not f.endswith(".jsonl"):
            continue
        ep = f[2:-6]
        for l in io.open(os.path.join(CORPUS, f), encoding="utf-8"):
            c = json.loads(l)
            out.append((ep, c["i"], c["text"]))
    return out


def norm(s):
    """Whitespace-insensitive, the same rule the extraction verifies quotes by:
    whisper leaves stray spaces inside Japanese words and they broke quote
    matching once already."""
    return re.sub(r"\s+", "", s)


def find(needle, cues, joined, index):
    """Where a quoted line occurs in her words, allowing a span across two
    adjacent cues -- the extraction's rule, because the transcript breaks a
    sentence wherever the speaker drew breath."""
    n = norm(needle)
    if not n:
        return []
    hits = []
    for ep, i, t in cues:
        if n in norm(t):
            hits.append(f"ep{ep}#{i}")
    if hits:
        return hits
    # A run of adjacent cues, up to SPAN of them. Two was not enough: the
    # transcript breaks wherever she drew breath, so 「なんか嬉しかった。ホロって
    # なったよ。ホロホロホロー。」 is one sentence of hers across three cues and a
    # two-cue window reported it as invented.
    SPAN = 5
    for k in range(len(cues)):
        run = cues[k][2]
        for j in range(k + 1, min(k + SPAN, len(cues))):
            if cues[j][0] != cues[k][0] or cues[j][1] != cues[j - 1][1] + 1:
                break
            run += cues[j][2]
            if n in norm(run):
                hits.append(f"ep{cues[k][0]}#{cues[k][1]}-{cues[j][1]}")
                break
        if hits:
            break
    return hits


def longest_fragment(needle, joined, minlen=6):
    """The longest run of a quoted line that IS in her words, when the whole of
    it is not.

    Without this the audit lies in the dangerous direction. 「何か無駄にならずに
    済んだ感とかあってね。」 matched nothing and would have been called invented,
    but 「無駄にならずに済んだ」 is real (ep011#459) and the file had simply tidied
    the tail. A near-miss like that is a paraphrase of something she said; a
    quote with no fragment at all is something she never said. Only the second
    is a fabrication, and the two must not be reported alike.
    """
    n = norm(needle)
    best = ""
    for start in range(len(n)):
        # nothing shorter than what we already have can win from here
        if len(n) - start <= len(best):
            break
        lo, hi = len(best) + 1, len(n) - start
        while lo <= hi:
            mid = (lo + hi) // 2
            if n[start:start + mid] in joined:
                best = n[start:start + mid]
                lo = mid + 1
            else:
                hi = mid - 1
    return best if len(best) >= minlen else ""


# A quoted line is not the only way a file can hand a model a catchphrase, but
# it is the one that gets copied verbatim, so it is what this counts.
QUOTE = re.compile(r"[「『]([^」』]{3,})[」』]")


def audit(path, cues, joined, index, min_habit):
    text = io.open(path, encoding="utf-8").read()
    rows = []
    for m in QUOTE.finditer(text):
        q = m.group(1).strip()
        if not q or q.startswith("#"):
            continue
        hits = find(q, cues, joined, index)
        frag = "" if hits else longest_fragment(q, joined)
        # a long quote is a whole line of hers; a short one is a form, and a
        # form is better counted as a substring than looked up as a sentence
        eps = len({h.split("#")[0] for h in hits})
        rows.append({"quote": q, "n": len(hits), "eps": eps, "where": hits[:3], "frag": frag})
    return rows


# The long demonstrations are not in 「」 -- they are markdown blockquotes, and
# for a while nothing checked them at all. Reading the four in the control
# speech guide against the tape found every one of them smoothed: connectives
# inserted, long vowels shortened, and the hesitation sounds deleted (53 filler
# tokens in the tape's own wording, 5 in the file's). None was invented, but a
# demonstration edited towards clean prose teaches clean prose.
BLOCK_SPEAKER = re.compile(r"^\s*(?:ゆかり|相手)\s*[:：]")
BLOCK_CITE = re.compile(r"（ep[^）]*）")
BLOCK_PUNCT = re.compile(r"[\s。、,.!！?？…「」『』\-]+")


def _longest_in(needle, hay):
    """The longest run of a demonstration that really is in the tape. Uses the
    blockquote normaliser rather than `norm`, so it searches the same haystack
    the verdict was decided against."""
    q = BLOCK_PUNCT.sub("", needle)
    best = ""
    for a in range(len(q)):
        if len(q) - a <= len(best):
            break
        lo, hi = len(best) + 1, len(q) - a
        while lo <= hi:
            m = (lo + hi) // 2
            if q[a:a + m] in hay:
                best = q[a:a + m]
                lo = m + 1
            else:
                hi = m - 1
    return best


def blockquotes(path, hers, room):
    """Every blockquoted demonstration, checked verbatim against the tape.

    A line prefixed 相手: is the other half of a recorded exchange and is
    checked against every voice; anything else has to be in her own words.
    """
    rows = []
    for ln in io.open(path, encoding="utf-8").read().split("\n"):
        if not ln.startswith(">"):
            continue
        body = BLOCK_CITE.sub("", ln[1:]).replace("／", "\n")
        for part in body.split("\n"):
            other = bool(BLOCK_SPEAKER.match(part))
            part = BLOCK_SPEAKER.sub("", part).strip()
            q = BLOCK_PUNCT.sub("", part)
            if len(q) < 4:
                continue
            hay = room if other else hers
            if q in hay:
                rows.append(("OK  ", part, ""))
            else:
                rows.append(("EDIT", part, _longest_in(part, hay)))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="")
    ap.add_argument("--min", type=int, default=3,
                    help="occurrences at or above which a line reads as a habit")
    args = ap.parse_args()

    cues = her_cues()
    joined = "".join(norm(t) for _, _, t in cues)
    hers_bq = "".join(BLOCK_PUNCT.sub("", t) for _, _, t in cues)
    room_bq = "".join(BLOCK_PUNCT.sub("", t) for _, _, t in every_cue())
    print(f"her attributed words: {len(cues)} cues, {sum(len(t) for _,_,t in cues)} chars\n")

    files = [args.file] if args.file else FILES
    grand = {"KEEP": 0, "MARK": 0, "NEAR": 0, "CUT": 0}
    edited = 0
    for path in files:
        if not os.path.exists(path):
            continue
        rows = audit(path, cues, joined, None, args.min)
        print("=" * 78)
        print(f"{path}  --  {len(rows)} quoted line(s)")
        print("=" * 78)
        for r in sorted(rows, key=lambda x: x["n"]):
            if r["n"] == 0:
                verdict = "NEAR" if r["frag"] else "CUT "
            else:
                verdict = "MARK" if r["n"] < args.min else "KEEP"
            grand[verdict.strip()] = grand.get(verdict.strip(), 0) + 1
            if r["where"]:
                where = " ".join(r["where"])
            elif r["frag"]:
                where = f"longest real fragment: {r['frag']}"
            else:
                where = "-- no fragment of this is in her words --"
            print(f"  [{verdict}] {r['n']:>3}x / {r['eps']:>2}ep  {r['quote'][:52]:<54} {where}")
        bq = blockquotes(path, hers_bq, room_bq)
        if bq:
            print(f"  -- {len(bq)} blockquoted demonstration line(s)")
            for verdict, part, frag in bq:
                if verdict == "OK  ":
                    print(f"  [{verdict}] {part[:70]}")
                else:
                    edited += 1
                    print(f"  [{verdict}] {part[:70]}\n           longest real run: {frag}")
        print()
    print(f"KEEP {grand['KEEP']}   MARK {grand['MARK']}   CUT {grand['CUT']}   "
          f"edited demonstrations {edited}")
    print("\nCUT is a line she never says. MARK is real but singular: keep it only if the")
    print("file says it is one occasion rather than a habit. A count is not a verdict.")
    print("EDIT is a demonstration that has been smoothed on its way into the file:")
    print("the words are hers, the wording is not, and a tidied example teaches tidy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
