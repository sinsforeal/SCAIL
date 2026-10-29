"""Do the docs still describe the code that is there?

`tools/docs_assemble.py` regenerates PROJECT.md and CONFIG.md from the source,
so those two cannot drift far. Everything else can: the module specs in
`docs/`, the running state in HANDOVER.md, the operating rules in CLAUDE.md and
the hand-written chapters in `tools/docs_src/`. A doc that names a config key
that has been renamed, a function that has been deleted or a file that has
moved is worse than no doc, because it is believed.

So every backticked token in those files that LOOKS like an identifier is
resolved against the code:

  config keys     `exchange.away_p`, `cast.presence_gap_minutes`  -> config.py DEFAULTS
  functions       `Reactions.tick`, `engage_line`, `_named_by_her` -> a def in the source
  files           `tomoe/carried.py`, `prompts/style_ja.md`          -> the filesystem
  kv keys         kv `cast_asleep`                                 -> a store.set in the code

Prose in backticks is skipped: a token only counts when it has the shape of an
identifier, and `_ALLOW` carries the handful that are real but unresolvable
(external names, the shape of a thing rather than a thing).

    python tools/docs_check.py
    python tools/docs_check.py --verbose      # every token it resolved
"""
import argparse
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logger
logger.log = lambda m, to_console=True: None

from config import Config, DEFAULTS

DOCS = ["PROJECT.md", "CONFIG.md", "HANDOVER.md", "CLAUDE.md"]
DOC_DIRS = ["docs", "tools/docs_src"]

# real, and not resolvable here: other people's names, shapes rather than things
_ALLOW = {
    "ast.parse", "os.walk", "json.loads", "json.dumps", "time.time", "random.random",
    "config.json", "package.json", "requirements.txt", "world.db", "dryrun.db",
    "data/world.db", "data/dryrun.db", "run.cmd", "dryrun.cmd", "talkapp.cmd",
    "scail.py", "config.py", "store.py", "logger.py", "llm.py",
    # not python: the Android app, the one-file web app, and the Chrome
    # DevTools protocol
    "MainActivity.visible", "MainActivity.shouldOverrideUrlLoading",
    "faceLabel()", "tlabel()", "ttitle()", "dayOf()", "hm()", "buckets()", "canon()",
    # written on demand by a tool that has not been run yet
    "model.json",
    "Network.setUserAgentOverride", "Page.addScriptToEvaluateOnNewDocument",
}

IDENT = re.compile(r"`([^`\n]{2,60})`")
CONFIG_KEY = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")
FUNC = re.compile(r"^(?:[A-Z][A-Za-z0-9_]*\.)?_?[a-z][A-Za-z0-9_]*(\(\))?$")
CLASS_FUNC = re.compile(r"^([A-Z][A-Za-z0-9_]*)\.(_?[a-z][A-Za-z0-9_]*)(\(\))?$")
PATH = re.compile(r"^[a-zA-Z_][\w/]*\.(py|md|json|txt|cmd|html)$")
KV = re.compile(r"kv `([a-z][a-z0-9_]*)`")
DATE = re.compile(r"\b20\d\d-\d\d-\d\d\b")
# A document that carries this line says it is a record of evidence -- a report,
# a review, a hand read, a design plan -- rather than a statement of what runs
# now. It is exempt from "everything you name still exists" and from "no dates",
# because both of those are true of a spec and false of a record.
# The two markers a document uses to say it is not a spec: a record of
# evidence (`reference`) and a plan of work (`plan`). The comment at the one
# place this is asked already counted a design plan as exempt, and only the
# first word was in the pattern, so a plan naming the files its own steps
# create -- which is what a plan is -- failed the check and stopped a restart.
REFERENCE_DOC = re.compile(r"<!--\s*doc:\s*(?:reference|plan)\s*-->")


def flat_defaults(d=None, prefix=""):
    out = set()
    for k, v in (d if d is not None else DEFAULTS).items():
        key = f"{prefix}{k}"
        out.add(key)
        if isinstance(v, dict):
            out |= flat_defaults(v, key + ".")
    return out


def code_text():
    """Every line of python in the project, once."""
    parts = []
    for base, dirs, names in os.walk("."):
        dirs[:] = [x for x in dirs if x not in ("logs", "data", "secerts", "__pycache__", ".git")]
        for n in names:
            if n.endswith(".py"):
                try:
                    parts.append(io.open(os.path.join(base, n), encoding="utf-8", errors="replace").read())
                except OSError:
                    pass
    return "\n".join(parts)


def doc_files():
    out = [p for p in DOCS if os.path.isfile(p)]
    for d in DOC_DIRS:
        if os.path.isdir(d):
            for n in sorted(os.listdir(d)):
                if n.endswith(".md"):
                    out.append(os.path.join(d, n))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()

    Config()                      # so a broken config fails here, loudly
    keys = flat_defaults()
    code = code_text()
    defs = set(re.findall(r"^\s*(?:async )?def (\w+)", code, re.M))
    classes = set(re.findall(r"^class (\w+)", code, re.M))
    # an attribute is as real as a method: `Intent.last_question` and
    # `reaction_provider` are set on the object and read elsewhere
    attrs = set(re.findall(r"self\.(\w+)\s*=", code)) | set(re.findall(r"\.(\w+)\s*=\s*self\.", code))
    modules = {os.path.splitext(n)[0] for base, _d, ns in os.walk(".") for n in ns
               if n.endswith(".py") and "logs" not in base and "retired" not in base}
    data_files = {n for base, _d, ns in os.walk("data") if "retired" not in base for n in ns} if os.path.isdir("data") else set()
    # a bare basename resolves against every live file in the tree -- the
    # docs write `cast.py` for `tomoe/cast.py` -- but never against the
    # retired archive, which is where a moved file's old copy hides
    live_files = set()
    for base, dirs, ns in os.walk("."):
        dirs[:] = [x for x in dirs if x not in ("logs", "retired", "__pycache__", ".git", "node_modules")]
        for n in ns:
            live_files.add(n)
    kv_set = set(re.findall(r"""(?:store|self\.store)\.set\(\s*["'](\w+)["']""", code))
    kv_set |= set(re.findall(r"""(?:store|self\.store)\.get\(\s*["'](\w+)["']""", code))
    # the per-day counters (Store.today_count / bump_today) read and write kv too
    kv_set |= set(re.findall(r"""(?:store|self\.store)\.(?:today_count|bump_today)\(\s*["'](\w+)["']""", code))

    bad, checked = [], 0
    for path in doc_files():
        text = io.open(path, encoding="utf-8", errors="replace").read()
        # A document declares what kind of thing it is. A record of evidence --
        # a report, a review, a hand read, a design plan -- correctly names the
        # files and code that existed when it was written, and correctly cites
        # the day it was taken. Holding it to "everything you name still
        # exists" would make it lie or make the check cry wolf, and a check
        # nobody trusts is a check nobody runs. A spec gets no such exemption:
        # it says what is true now.
        if REFERENCE_DOC.search(text[:2000]):
            continue
        for kvname in set(KV.findall(text)):
            checked += 1
            if kvname not in kv_set:
                bad.append((path, f"kv `{kvname}`", "nothing in the code reads or writes it"))
        for tok in set(IDENT.findall(text)):
            t = tok.strip()
            if t in _ALLOW or " " in t:
                continue
            # a filename first: `cast.py` and `places.json` have the shape of a
            # config key and are not one
            if PATH.match(t):
                checked += 1
                base = os.path.basename(t)
                if not (os.path.exists(t) or base in data_files or (base == t and t in live_files) or any(
                        os.path.exists(os.path.join(d, t)) for d in
                        ("sim", "persona", "embodied", "world", "tomoe", "tomoe/world", "tomoe/prompts", "resident",
                         "machine", "channels", "sensors", "tools", "prompts", "prompts_yukarin",
                         "data"))):
                    bad.append((path, t, "no such file"))
                continue
            if CONFIG_KEY.match(t):
                checked += 1
                head, tail = t.split(".")[0], t.split(".")[-1]
                # `situation.delay_multiplier` is a module and a method, not a
                # config section and a key; both spellings are legitimate prose
                if head in modules and (tail in defs or tail in attrs):
                    continue
                if t not in keys and head in {k.split(".")[0] for k in keys}:
                    bad.append((path, t, "not a key in config.py DEFAULTS"))
                continue
            m = CLASS_FUNC.match(t)
            if m and not t.rsplit(".", 1)[-1] in ("jpg", "png", "webp", "db", "json", "md", "txt"):
                checked += 1
                cls, fn = m.group(1), m.group(2)
                if cls not in classes:
                    bad.append((path, t, f"no class {cls}"))
                elif fn not in defs and fn not in attrs:
                    bad.append((path, t, f"no def or attribute {fn}"))
                continue
            if t.endswith("()") and FUNC.match(t):
                checked += 1
                if t[:-2] not in defs and t[:-2] not in attrs:
                    bad.append((path, t, "no such function"))

    # a dated note belongs in HISTORY.md: PROJECT.md (its sources) and the
    # specs describe what is true now. "since <date>", a HISTORY pointer
    # ("Part C 2026-..."), a token expiry and the --sim example are the
    # dates that are not notes.
    for path in doc_files():
        if not (path.startswith("tools/docs_src") or path.startswith("docs") or path == "PROJECT.md"):
            continue
        text = io.open(path, encoding="utf-8", errors="replace").read()
        if REFERENCE_DOC.search(text[:2000]):
            continue
        for n, line in enumerate(text.split("\n"), 1):
            if not DATE.search(line):
                continue
            if any(w in line for w in ("since ", "Part C", "--sim", "expires", "HISTORY", "history:")):
                continue
            # a date inside a filename is the name of a dated document, not a
            # note written into a spec: `docs/review-2026-08-26-prompts.md` has
            # to be nameable by the index that points at it.
            if re.search(r"[\w./-]*20\d\d-\d\d-\d\d[\w./-]*\.md", line):
                continue
            # a date from before this project began is data, not a note about
            # its work: the second character's corpus is broadcasts of
            # 2003-2005 and the documents that read them cite air dates.
            if all(int(d[:4]) < 2026 for d in DATE.findall(line)):
                continue
            checked += 1
            bad.append((path, f"line {n}: {DATE.search(line).group(0)}", "a dated note; it belongs in HISTORY.md"))

    by_file = {}
    for path, tok, why in bad:
        by_file.setdefault(path, []).append((tok, why))
    print(f"docs checked: {len(doc_files())} files, {checked} references resolved\n")
    for path in sorted(by_file):
        print(f"  {path}")
        for tok, why in sorted(by_file[path]):
            print(f"    {tok:<44} {why}")
    print(f"\n{len(bad)} stale reference(s)" if bad else "\nno stale references")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
