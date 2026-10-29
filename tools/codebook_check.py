"""The mechanism codebook loads, every field is there, and nobody is named in it.

The codebook (`data/codebook/v<version>.json`, `docs/codebook.md`) is the closed
vocabulary a character's behaviour is coded against, and every `code` field
written anywhere else points into it. This checks that it can still be pointed
into: the schema of every entry, no duplicate id, no `excludes` naming a
neighbour that is not in the book, an anchored entry that actually has anchors,
a family inside the twenty, one version across the whole file, and no
character's name anywhere in it -- the codebook is shared between every
character and a person's name in an entry would make it one character's.

    python tools/codebook_check.py         # exit 1 on a fault; run by smoke

It reads the file and nothing else. No save, no model call.
"""
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

try:
    from tools import character_names as _names
except ImportError:
    import character_names as _names

VERSION = "0.1"
PATH = os.path.join("data", "codebook", "v%s.json" % VERSION)
# The second tier: entries the compile table needed and the frozen file does
# not hold (data/retired/20260906_compile/build_compile_table.py writes it).
# It is held to the same schema, its ids may not collide with the frozen
# file's, and an `excludes` neighbour may resolve into either tier.
THEORY = os.path.join("data", "codebook", "v%s_theory.json" % VERSION)
LEDGER = os.path.join("data", "codebook", "loss_ledger.json")

FAMILIES = {
    "F1": "self-presentation and face",
    "F2": "disclosure and concealment",
    "F3": "affect regulation",
    "F4": "approach and initiative",
    "F5": "avoidance and withdrawal",
    "F6": "attachment and reassurance",
    "F7": "conflict, rupture and repair",
    "F8": "status, comparison and rank",
    "F9": "belonging and conformity",
    "F10": "care and obligation",
    "F11": "self-concept and self-belief",
    "F12": "decision and commitment",
    "F13": "attention and noticing",
    "F14": "humour and play",
    "F15": "the frame and the format",
    "F16": "memory and narrative",
    "F17": "wanting and taste",
    "F18": "body and state",
    "F19": "the picture of another person",
    "F20": "requests and refusals",
}

TEXT_FIELDS = ("definition", "trigger", "suppressor", "function", "includes")
LIST_FIELDS = {"occasions": 4, "variation": 3, "excludes": 2, "near_misses": 2, "sources": 3}
STATUSES = ("anchored", "theory-derived")
FITS = ("threshold", "baseline", "no home")
KINDS = ("extracted:", "authored:", "library:", "scope:")

# A code that needs a face, a voice or a body to define is out of scope
# (`docs/codebook-scope.md` section 7): a channel may add evidence to a code,
# but a code that cannot be seen in a subtitle file cannot be in a vocabulary
# shared between a tape, a chat log and a written sheet. Only the definition is
# checked, because a variation may legitimately describe what a form sounded
# like on one occasion.
PHYSICAL = ("face", "facial", "smile", "smiles", "blush", "blushes", "frown", "gaze",
            "eye contact", "tone of voice", "body language", "posture")

# `<program>/module.py` is a path to a file of that character's, not her name in
# the entry; `tools/character_names.py` makes the same exemption for shared code.
PROGRAM_PATH = re.compile(r"\b[a-z_]+/[a-z_0-9]+\.py\b")


def fail(problems, msg):
    problems.append(msg)


def check_entry(e, ids, problems):
    where = e.get("id") or "(an entry with no id)"
    if not re.match(r"^F\d+\.[a-z0-9-]+$", str(e.get("id") or "")):
        fail(problems, "%s: the id is not F<n>.<function-phrase>" % where)
        return
    fam = e.get("family")
    if fam not in FAMILIES:
        fail(problems, "%s: family %r is outside the twenty" % (where, fam))
    if e["id"].split(".", 1)[0] != fam:
        fail(problems, "%s: the id's family and the family field disagree" % where)
    if e.get("layer") not in ("occurrence", "function"):
        fail(problems, "%s: layer must be occurrence or function, not %r" % (where, e.get("layer")))
    for f in TEXT_FIELDS:
        v = e.get(f)
        if not isinstance(v, str) or len(v.strip()) < 20:
            fail(problems, "%s: %s is missing or too thin to code against" % (where, f))
    prov = e.get("provenance")
    if not isinstance(prov, str) or (prov != "bespoke" and len(prov.strip()) < 20):
        fail(problems, "%s: provenance must name the instrument it borrows from, or be bespoke" % where)
    if isinstance(e.get("definition"), str):
        d = e["definition"]
        if not d.rstrip().endswith("."):
            fail(problems, "%s: the definition is not one finished sentence" % where)
        for w in PHYSICAL:
            if re.search(r"(?<!\w)%s(?!\w)" % re.escape(w), d, re.I):
                fail(problems, "%s: the definition needs a %s, which the text-only rule refuses" % (where, w))
    for f, least in LIST_FIELDS.items():
        v = e.get(f)
        if not isinstance(v, list) or len(v) < least:
            fail(problems, "%s: %s needs at least %d and has %s" %
                 (where, f, least, len(v) if isinstance(v, list) else "nothing"))
    if isinstance(e.get("variation"), list) and len(set(map(str, e["variation"]))) != len(e["variation"]):
        fail(problems, "%s: two of the surface forms are the same, so the entry is a tic" % where)
    for x in e.get("excludes") or []:
        if not isinstance(x, dict) or not x.get("neighbour") or not x.get("rule"):
            fail(problems, "%s: an excludes row has no neighbour or no rule" % where)
            continue
        if x["neighbour"] == e["id"]:
            fail(problems, "%s: excludes itself" % where)
        elif x["neighbour"] not in ids:
            fail(problems, "%s: excludes names %s, which is not in the codebook" % (where, x["neighbour"]))
    for nm in e.get("near_misses") or []:
        if not isinstance(nm, dict) or not nm.get("ref") or not nm.get("why"):
            fail(problems, "%s: a near miss has no reference or no reason" % where)
    t = e.get("tunes")
    if not isinstance(t, dict) or t.get("fits") not in FITS:
        fail(problems, "%s: tunes must say whether a rate fits a threshold, a baseline, or has no home" % where)
    for line in e.get("sources") or []:
        if not str(line).startswith(KINDS):
            fail(problems, "%s: the source line %r names no inventory" % (where, str(line)[:40]))
    if e.get("status") not in STATUSES:
        fail(problems, "%s: status must be anchored or theory-derived" % where)
    anchors = e.get("anchors")
    if not isinstance(anchors, list):
        fail(problems, "%s: anchors is not a list" % where)
    elif e.get("status") == "anchored" and not anchors:
        fail(problems, "%s: called anchored and has no anchor" % where)
    elif e.get("status") == "theory-derived" and anchors:
        fail(problems, "%s: called theory-derived and carries anchors" % where)
    if not isinstance(e.get("single_source"), bool):
        fail(problems, "%s: single_source is not recorded" % where)
    if e.get("version") != VERSION:
        fail(problems, "%s: written under version %r, not %s" % (where, e.get("version"), VERSION))
    if "class" in e:
        fail(problems, "%s: carries a class field, which is decided per subject at coding time" % where)


def names_in(doc, problems):
    """No character's name anywhere in the file."""
    text = json.dumps(doc, ensure_ascii=False)
    text = PROGRAM_PATH.sub(" ", text)
    for n in _names.names():
        if re.search(r"(?<!\w)%s(?!\w)" % re.escape(n), text, re.I):
            fail(problems, "a character's name appears in the codebook: %s" % n)


def main():
    problems = []
    if not os.path.isfile(PATH):
        print("FAIL %s does not exist" % PATH)
        return 1
    doc = json.load(io.open(PATH, encoding="utf-8"))
    if doc.get("version") != VERSION:
        fail(problems, "the file says version %r and this check is written for %s; a version "
                       "change invalidates every code field and re-runs the ledger" %
             (doc.get("version"), VERSION))
    entries = doc.get("entries") or []
    theory_doc = {}
    theory = []
    if os.path.isfile(THEORY):
        theory_doc = json.load(io.open(THEORY, encoding="utf-8"))
        if theory_doc.get("version") != VERSION:
            fail(problems, "the companion file says version %r and this check is "
                           "written for %s" % (theory_doc.get("version"), VERSION))
        theory = theory_doc.get("entries") or []

    ids = [e.get("id") for e in entries]
    seen = set()
    for i in ids:
        if i in seen:
            fail(problems, "duplicate id: %s" % i)
        seen.add(i)
    # An id in both tiers is worse than an id in neither: a `code` field would
    # then resolve to two different entries depending on which file was read.
    for e in theory:
        i = e.get("id")
        if i in seen:
            fail(problems, "%s is in both the codebook and its companion" % i)
        seen.add(i)
    for e in entries + theory:
        check_entry(e, seen, problems)
    for e in theory:
        if e.get("status") != "theory-derived":
            fail(problems, "%s is in the companion file and is not theory-derived" % e.get("id"))
    for f in doc.get("families") or []:
        if f.get("id") not in FAMILIES:
            fail(problems, "family %r is outside the twenty" % f.get("id"))
    names_in(doc, problems)
    if theory_doc:
        names_in(theory_doc, problems)

    if os.path.isfile(LEDGER):
        led = json.load(io.open(LEDGER, encoding="utf-8"))
        if led.get("version") != VERSION:
            fail(problems, "the loss ledger was written under version %r" % led.get("version"))
        for key, rows in led.items():
            if not isinstance(rows, list):
                continue
            for r in rows:
                for cid in r.get("covered_by") or []:
                    if cid not in seen:
                        fail(problems, "the loss ledger sends %s to %s, which is not in the codebook" %
                             (key, cid))
    else:
        fail(problems, "the loss ledger is missing")

    per = {}
    for e in entries + theory:
        f = e.get("family")
        row = per.setdefault(f, [0, 0, 0])
        row[0] += 1
        row[1 if e.get("status") == "anchored" else 2] += 1
    both = entries + theory
    print("codebook version %s: %d entries, %d anchored, %d theory-derived, %d on one subject" %
          (VERSION, len(both),
           len([e for e in both if e.get("status") == "anchored"]),
           len([e for e in both if e.get("status") == "theory-derived"]),
           len([e for e in both if e.get("single_source")])))
    # How many entries no record has reached yet: the pilot codes the anchored
    # ones only, so this is the size of what the reliability run cannot touch.
    print("  %d of the %d wait for a record to anchor them (%d of those in the "
          "companion file the compile table needed)"
          % (len([e for e in both if e.get("status") == "theory-derived"]),
             len(both), len(theory)))
    for f in sorted(FAMILIES, key=lambda x: int(x[1:])):
        n, a, t = per.get(f, [0, 0, 0])
        print("  %-4s %-34s %3d entries  %3d anchored  %3d theory-derived%s" %
              (f, FAMILIES[f], n, a, t, "   EMPTY" if not n else ""))
    if problems:
        print("FAIL %d problems" % len(problems))
        for p in problems[:40]:
            print("   " + p)
        return 1
    print("ok   every entry has its fields, its neighbours resolve, and nobody is named")
    return 0


if __name__ == "__main__":
    sys.exit(main())
