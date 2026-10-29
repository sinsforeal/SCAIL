"""The forge: an instrument for porting the prompts to another character BY HAND.

The previous forge asked a model to rewrite the character-bearing spans and
then checked the result. It was retired on 2026-09-01 for two reasons. It had
gone stale -- its own docstring described 46 prompts when there are 84, it read
`prompts/` flat so the six per-person sheets in `prompts/cast/` were invisible,
its `{{PLACEHOLDER}}` rubric checked two tokens in the whole set, and its
proper-noun rubric matched capitalised Latin words, which for a character who
writes Japanese with a cast of 矢野さん and 鈴木さん sees nothing at all.

The deeper reason is that generation is the wrong operation. What is
character-bearing in these files is not the names, it is the psychology written
into the mechanism. `state.txt` says "Being with Aya calms her. Being watched
by Hinako does not", and defines anxiety as "how safe she feels in the group".
Substituting proper nouns into that produces a Tamura Yukari with a school
friend circle. Those sentences have to be *written*, by somebody who has read
the character, and the reading is the work.

So this does not write anything. It:

  survey    every prompt, what it carries, and how much of it is character
  show      one prompt with every character-bearing span marked
  check     a hand-written port against the rubric -- what must not break
  status    what is done and what is not

The rubric is anchored on what is really in the files rather than on what the
old one assumed, and it works in both scripts. It can only refuse; whether a
port reads as her is a judgement and is not mechanical.

    python tools/forge.py survey --sheet data/characters/yukarin.json
    python tools/forge.py show prompts/state.txt --sheet data/characters/yukarin.json
    python tools/forge.py check --dir prompts_yukarin --sheet data/characters/yukarin.json
    python tools/forge.py status --dir prompts_yukarin
"""
import argparse
import io
import json
import os
import re
import sys

if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

PROMPT_DIR = "prompts"
OLD_SHEET = "data/characters/tomoe.json"

# ---------------------------------------------------------------- what is mechanism
# Every one of these is a fact about the file rather than an opinion, and each
# was checked to exist in the current prompts before being made a rule.
SCHEMA_LINE = re.compile(r"Output ONLY (?:this|the following) JSON:?", re.I)
JSON_KEY = re.compile(r'"([a-z_][a-z0-9_]*)"\s*:')
TOKEN = re.compile(r"\{\{[A-Z_]+\}\}")
# a gauge or field name as the prompts write them: bare snake_case words that
# are the machine's vocabulary, not prose
MECH_WORD = re.compile(r"\b([a-z]+_[a-z_]+)\b")

# ------------------------------------------------- what is character-bearing
# A name in either script. Latin: a capitalised word that is not sentence
# initial. Japanese: a run of kanji/kana followed by an honorific, plus any
# name the sheet itself declares.
#
# "Sentence initial" has to mean it in both scripts and in Markdown. A file
# whose sentences end 「…」 and whose sections open `## Work` offered `Work`,
# `You` and `Your` as invented names, because the terminator class knew only
# ASCII full stops and the line-start guard was defeated by the heading
# marker sitting in front of the word.
LATIN_NAME = re.compile(r"(?<![.!?。！？」]\s)(?<!^)\b([A-Z][a-z]{2,}(?:-[a-z]+)?)\b", re.M)
MARKUP = re.compile(r"(?m)^(?:#{1,6}|[-*+]|\d+\.)\s+")
JA_NAME = re.compile(r"([一-鿿ぁ-んァ-ヿー]{2,8}(?:さん|ちゃん|くん|様|先生))")
JA_RUN = re.compile(r"[一-鿿ぁ-んァ-ヿー]{2,}")


def for_names(text):
    """The text as the name scanners should see it. Markdown structure comes
    off the front of a line so the word behind it is line-initial again, and
    bold markers come out everywhere, because `.** Work goes where...` hides
    the full stop from the terminator class and offers `Work` as a name."""
    return MARKUP.sub("", text).replace("**", "")

# Phrases that presuppose a relationship that already exists, or a life shaped
# like a schoolgirl's. These are not errors in the Tomoe prompts; they are the
# spans that cannot be carried to a character who starts at zero, and finding
# them is half the point of the survey (docs/pattern.md, the primitives work).
ASSUMES = [
    (r"\bthe group\b", "assumes a standing friend circle"),
    (r"\bgroup chat\b", "assumes a standing friend circle"),
    (r"\bclassmate|\bschool\b|\bhomeroom\b|\bclass\b", "assumes school"),
    (r"\bher friends\b|\bthe girls\b", "assumes a standing friend circle"),
    (r"\bjealous\w*\b", "assumes a bond worth defending"),
    (r"\bwhen he (?:answers|writes|replies|messages)\b", "assumes an established correspondence"),
    (r"\bhis silence\b|\bleft on read\b|\bunanswered\b", "assumes an established correspondence"),
    (r"\bmaking up\b|\brepair\b|\bmakes? it up\b", "assumes a bond that can rupture"),
    (r"\bcloseness\b|\bstanding\b|\btension per person\b", "assumes relationship meters with history"),
    (r"\bher mother\b|\bher father\b|\bokaa-san\b|\bher brother\b", "assumes family present"),
]


def prompts(root=PROMPT_DIR):
    """Every prompt file, including the per-person sheets in prompts/cast/,
    which the old forge could not see."""
    out = []
    for base, _dirs, files in os.walk(root):
        for f in sorted(files):
            if f.endswith((".txt", ".md")):
                out.append(os.path.join(base, f).replace("\\", "/"))
    return sorted(out)


def _no_notes(x):
    """A sheet's `_`-prefixed keys are notes to whoever reads the file, not
    data about the person. Scanning them for names found `Nothing` (from
    "Nothing here is a stress LEVEL") and `The` (from "The single sheet a
    character is generated from") and put both in the old character's name
    set, so a port containing the ordinary English word failed the rubric."""
    if isinstance(x, dict):
        return {k: _no_notes(v) for k, v in x.items() if not str(k).startswith("_")}
    if isinstance(x, list):
        return [_no_notes(v) for v in x]
    return x


# The fields that say WHO somebody is. The residue check reads only these,
# because it is looking for the old character surviving -- her name, her
# people, her places -- and not for every capitalised word in the file. The
# whole-sheet scan put `English` in the set (from `register.language`,
# "casual JK Japanese rendered into English") and failed a port for saying
# which language a machine-facing field is written in. A language is a
# descriptor, not an identity.
IDENTITY = ("name", "people", "origin", "place")


def sheet_names(sheet, identity_only=False):
    """Every name this character may use, in both scripts. A sheet is data, so
    it is serialised and scanned rather than walked -- a name in a list, a key
    or a sentence counts the same.

    `identity_only` narrows it to the fields that name a person or a place,
    which is what the residue check wants; the permissive whole-sheet set is
    right for deciding whether a name in a PORT was invented."""
    src = {k: v for k, v in _no_notes(sheet).items() if k in IDENTITY} if identity_only else _no_notes(sheet)
    blob = json.dumps(src, ensure_ascii=False)
    names = set(LATIN_NAME.findall(blob)) | set(JA_NAME.findall(blob))
    for key in ("name", "people", "origin", "place"):
        v = sheet.get(key)
        if isinstance(v, dict):
            for x in v.values():
                if isinstance(x, str):
                    names |= set(JA_RUN.findall(x)) if len(x) < 40 else set()
                elif isinstance(x, list):
                    for y in x:
                        if isinstance(y, str):
                            names.add(y.strip())
    return {n for n in names if len(n) >= 2}


def mechanism(text):
    """The vocabulary that must survive a port byte for byte."""
    return {
        "schema_lines": len(SCHEMA_LINE.findall(text)),
        "json_keys": sorted(set(JSON_KEY.findall(text))),
        "tokens": sorted(TOKEN.findall(text)),
        "mech_words": sorted(set(MECH_WORD.findall(text))),
    }


def character_hits(text, old_names):
    """Where the old character survives. Matching is whole-word for a name
    written in Latin letters and plain containment for one written in
    Japanese, which has no word boundaries to anchor on.

    It was containment for both, and `mom` therefore matched inside `moment`
    and failed a port that had nothing to do with her mother. That is the
    same fault `sim/roster.py` was written to end -- a name matched as a
    substring makes `Rena` and `Rena-chan` two girls -- and it does not stop
    being a fault because the matcher is a tool rather than the bot.

    A short run of bare hiragana cannot be matched this way at all, and is
    skipped. The old sheet's dialect endings reach the name set through the
    scan of `origin`, and `ばい` matched inside `あればいい` and
    `言えばいいの` -- ordinary grammar, in a file with no dialect in it.
    Whether a port leaks a dialect is a question about register and belongs
    to `yukarin/tools/fingerprint.py`, which counts endings against the
    corpus; it is not a question about names."""
    hits = []
    for n in sorted(old_names, key=len, reverse=True):
        if re.match(r"^[\x00-\x7f]+$", n):
            rx = re.compile(r"(?<![A-Za-z])" + re.escape(n) + r"(?![A-Za-z])")
        elif re.match(r"^[ぁ-ん]{1,2}$", n):
            continue
        else:
            rx = re.compile(re.escape(n))
        for m in rx.finditer(text):
            hits.append((m.start(), n))
    return hits


def assumes(text):
    out = []
    for rx, why in ASSUMES:
        n = len(re.findall(rx, text, re.I))
        if n:
            out.append((why, n))
    merged = {}
    for why, n in out:
        merged[why] = merged.get(why, 0) + n
    return sorted(merged.items(), key=lambda kv: -kv[1])


def load(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def cmd_survey(args):
    old = sheet_names(load(args.old))
    rows = []
    for p in prompts():
        text = open(p, encoding="utf-8").read()
        m = mechanism(text)
        hits = character_hits(text, old)
        asm = assumes(text)
        rows.append({
            "prompt": p, "bytes": len(text),
            "schema": m["schema_lines"], "keys": len(m["json_keys"]),
            "names": len(hits), "distinct": len({n for _, n in hits}),
            "assumes": sum(n for _, n in asm), "why": [w for w, _ in asm],
        })
    rows.sort(key=lambda r: (-r["assumes"], -r["names"]))
    print("%-34s %7s %6s %5s %6s %7s  %s"
          % ("prompt", "bytes", "schema", "keys", "names", "assumes", "what it presupposes"))
    for r in rows:
        print("%-34s %7d %6d %5d %6d %7d  %s"
              % (r["prompt"][:34], r["bytes"], r["schema"], r["keys"],
                 r["names"], r["assumes"], "; ".join(r["why"])[:60]))
    n_names = sum(1 for r in rows if r["names"])
    n_asm = sum(1 for r in rows if r["assumes"])
    n_sch = sum(1 for r in rows if r["schema"])
    print("\n%d prompts. %d name the old character, %d presuppose a relationship or a "
          "schoolgirl's life, %d carry an output schema."
          % (len(rows), n_names, n_asm, n_sch))
    print("A file with names and no presuppositions is a substitution. A file with "
          "presuppositions is a rewrite, and it is a rewrite for ANY second character, "
          "not only this one.")
    if args.out:
        json.dump(rows, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("->", args.out)
    return 0


def cmd_show(args):
    old = sheet_names(load(args.old))
    text = open(args.prompt, encoding="utf-8").read()
    print("=" * 78)
    print(args.prompt, "--", len(text), "bytes")
    m = mechanism(text)
    print("MECHANISM that must survive: %d schema line(s), %d json keys, %d tokens, "
          "%d machine words" % (m["schema_lines"], len(m["json_keys"]), len(m["tokens"]),
                                len(m["mech_words"])))
    if m["json_keys"]:
        print("  keys: " + ", ".join(m["json_keys"][:24]))
    print("=" * 78)
    for i, line in enumerate(text.split("\n"), 1):
        marks = []
        got = sorted({n for _, n in character_hits(line, old)})
        if got:
            marks.append("NAME:" + ",".join(got[:5]))
        for why, n in assumes(line):
            marks.append("ASSUMES:" + why)
        if SCHEMA_LINE.search(line):
            marks.append("SCHEMA-FOLLOWS")
        print("%4d | %s" % (i, line))
        if marks:
            print("     >>> " + " | ".join(marks))
    return 0


def cmd_check(args):
    """The rubric. Every check is a fact about the file. It can refuse; it
    cannot approve -- whether the port reads as her is not mechanical."""
    old = sheet_names(load(args.old), identity_only=True)   # who must not survive
    new = sheet_names(load(args.sheet))                      # what this one may say
    fails, warns, ok = [], [], 0
    done = 0
    for p in prompts():
        rel = os.path.relpath(p, PROMPT_DIR).replace("\\", "/")
        q = os.path.join(args.dir, rel).replace("\\", "/")
        if not os.path.exists(q):
            continue
        done += 1
        a = open(p, encoding="utf-8").read()
        b = open(q, encoding="utf-8").read()
        ma, mb = mechanism(a), mechanism(b)

        if ma["schema_lines"] != mb["schema_lines"]:
            fails.append((rel, "schema lines %d -> %d" % (ma["schema_lines"], mb["schema_lines"])))
        missing_keys = set(ma["json_keys"]) - set(mb["json_keys"])
        if missing_keys:
            fails.append((rel, "json keys lost: " + ", ".join(sorted(missing_keys))))
        if sorted(ma["tokens"]) != sorted(mb["tokens"]):
            fails.append((rel, "placeholder tokens changed"))
        missing_mech = set(ma["mech_words"]) - set(mb["mech_words"])
        if missing_mech:
            warns.append((rel, "machine words gone: " + ", ".join(sorted(missing_mech)[:8])))

        # residue: the old character must not survive, in either script
        residue = sorted({n for _, n in character_hits(b, old)} - new)
        if residue:
            fails.append((rel, "old character remains: " + ", ".join(residue[:8])))
        # invention: a name the port introduced and the new sheet does not
        # declare. Anything the original already said in the same place is
        # not an invention of the port -- the schema's own `"Name"` stub is
        # the case that showed it, and it is in every file with a per-person
        # block.
        found = set(LATIN_NAME.findall(for_names(b))) | set(JA_NAME.findall(b))
        carried = set(LATIN_NAME.findall(for_names(a))) | set(JA_NAME.findall(a))
        invented = sorted(n for n in found - new - carried if len(n) >= 2)
        if invented:
            warns.append((rel, "names not in the sheet: " + ", ".join(invented[:8])))

        # Size is compared in UTF-8 bytes rather than characters, because a
        # character is not a comparable unit across scripts and a byte
        # roughly is: Japanese carries about three times as much per
        # character and costs three bytes to write. The 15,310-byte
        # Japanese bible is 90% of the 17,086-byte original by that measure
        # and 31% of it by character count, which is not a fact about the
        # port.
        r = len(b.encode("utf-8")) / max(len(a.encode("utf-8")), 1)
        if not 0.5 <= r <= 1.8:
            warns.append((rel, "size %.0f%% of the original, by bytes" % (r * 100)))
        if not any(f[0] == rel for f in fails):
            ok += 1

    print("%d of %d prompts ported. %d pass the rubric." % (done, len(prompts()), ok))
    for rel, why in fails:
        print("  FAIL  %-32s %s" % (rel, why))
    for rel, why in warns:
        print("  warn  %-32s %s" % (rel, why))
    if not done:
        print("nothing to check yet: write ports into %s/ mirroring prompts/" % args.dir)
    return 1 if fails else 0


def cmd_status(args):
    all_p = prompts()
    done = [p for p in all_p
            if os.path.exists(os.path.join(args.dir, os.path.relpath(p, PROMPT_DIR)))]
    print("%d of %d ported (%.0f%%)" % (len(done), len(all_p), 100 * len(done) / len(all_p)))
    todo = [p for p in all_p if p not in done]
    for p in todo[:40]:
        print("   todo", p)
    if len(todo) > 40:
        print("   ... and %d more" % (len(todo) - 40))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("survey", "show", "check", "status"):
        s = sub.add_parser(name)
        s.add_argument("--sheet", default="data/characters/yukarin.json")
        s.add_argument("--old", default=OLD_SHEET)
        s.add_argument("--dir", default="prompts_yukarin")
        s.add_argument("--out", default=None)
        if name == "show":
            s.add_argument("prompt")
    args = ap.parse_args()
    return {"survey": cmd_survey, "show": cmd_show,
            "check": cmd_check, "status": cmd_status}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
