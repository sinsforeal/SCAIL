"""The shared code names nobody, and no shared file names one person's places.

Reads every character's sheet, cast file and map for the names a person goes by
(her own, her family's, her friends', with readings and aliases) and for the
places that are hers (her home area, her station and the stops on her line, her
ward, her school and its area, the places she keeps going back to). Then it
greps everything both characters share for any of them.

    python tools/character_names.py                 # exit 1 on a NEW hit; run by smoke
    python tools/character_names.py --all           # every finding, not just the new ones
    python tools/character_names.py --write-known   # rewrite tools/known_literals.json

What is scanned:

  the mind library and the runtime  `sim/`, `persona/`, `embodied/`, `world/`,
                                    `machine/`, and the eight files at the root;
  what the machine serves          `channels/`, `sensors/`, `talkapp/`,
                                    `tools/`, `car/` -- one hub and one set of
                                    tools for four characters;
  the programs                     `tomoe/`, `resident/` -- a program is one
                                    character's by design, so a name of HERS is
                                    not reported there and a name belonging to
                                    a character on the other program is;
  the prompts                      the shared directory and each character's
                                    own, minus the three files that ARE a
                                    character (her voice, her speech guide in
                                    each language) and her cast's sheets.

And in six kinds of file rather than one: `.py`, `.html`, `.js`, `.txt`, `.md`
and `.json`. The hub serves all four characters and labelled every one of them
with the first character's name in `.html` for months, with this check
reporting that the shared code names nobody.

Findings come in four lists, never mixed:

  code     a name or a place in an identifier or a string literal;
  prose    the same, in a file that is not Python (a template, a prompt);
  inside   the literal inside a longer word (`ChromeProfileTomoe`), reported
           separately because a word boundary is what hid that one;
  comment  a comment or a docstring, which this project uses for failure
           histories and worked examples: left alone, listed so that a reader
           knows the check saw them.

`tools/known_literals.json` is what was already there when the check was
widened. Every entry names the file, the literal, which of the four lists it is
in, and why it is expected; a finding that is not in it fails the run. It is
emptied as the literals are moved into the characters' own files.

A generic word that is also a role (mom, dad, mother, class) is not a name and
is not looked for; a literal shorter than three characters is skipped.
"""
import ast
import glob
import io
import json
import os
import re
import sys
import tokenize

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

SHARED_DIRS = ("sim", "persona", "embodied", "world", "machine")
SHARED_FILES = ("scail.py", "config.py", "llm.py", "store.py", "logger.py", "netwatch.py", "singleton.py")
# One machine, four characters: the hub that serves all of them, the sensors
# that watch his PC, the channels a message arrives on, the car, and the tools
# any character's process can call. A name in any of these is one character's
# life handed to whoever runs next -- the hub's story view labelled every
# character's own turns with the first character's name.
SERVED_DIRS = ("channels", "sensors", "talkapp", "tools", "car")
EXTENSIONS = (".py", ".html", ".js", ".txt", ".md", ".json")
# Never scanned: what is not source (a run's logs, a superseded copy, a build
# cache) and the check's own record of what is already there.
SKIP_PARTS = (os.sep + "__pycache__" + os.sep, os.sep + "retired" + os.sep,
              os.sep + "node_modules" + os.sep,
              # the source of the generated reference and the generated
              # inventory beside it: documentation about this project, which
              # describes the first character because she is the character it
              # was written about. Nothing any character's process reads.
              os.path.join(os.sep + "tools", "docs_src") + os.sep)
KNOWN_PATH = os.path.join("tools", "known_literals.json")
# The world's, not one person's: every character in a world is in that city,
# and a shared prompt saying which city the world is in is the world speaking.
GENERIC_PLACES = {"tokyo", "japan", "asia/tokyo", "jp", "東京", "日本"}
GENERIC = {"mom", "mum", "dad", "mother", "father", "sibling", "grandmother", "grandfather", "teacher", "class",
           "user", "him", "her", "she", "he", "herself", "self", "family", "the group", "friend", "friends",
           # the Japanese "that person" / "that guy" a cast file lists as what somebody calls him
           "あの人", "あいつ", "the user",
           # A roster row is not always a person with a name: a radio persona's
           # cast is her listeners, her staff and the second person she is
           # addressing, and those words are the language rather than anybody.
           # Searched for, they made a fifth of every finding.
           "sister", "brother", "her mother", "her father", "his mother", "his father",
           "staff", "the staff", "listeners", "the listeners", "audience", "the audience",
           "everyone", "everybody", "あなた", "みんな", "みなさん", "皆さん", "スタッフ", "リスナー",
           # what a person is called at home. A roster lists these as names
           # because that is how she addresses them, and they are the words for
           # a mother and a brother in the language: an instruction telling a
           # model that the girls say 「お母さん」 is the language, not a person.
           "お母さん", "お父さん", "お兄ちゃん", "お姉ちゃん", "おかあさん", "おとうさん",
           "おにいちゃん", "おねえちゃん"}
# A program's directory is named after its character, and a path into it
# (`<program>/prompts/x.txt`) is a file of hers rather than her name in the
# mechanism; the bare lowercase package name is a package name. Read from the
# register (`characters.json`) rather than written here, so a third character's
# program is not a name this checker starts reporting against itself.
try:
    from tools import registry as _registry
except ImportError:
    import registry as _registry
PROGRAMS = {p.lower() for p in _registry.programs()} or {"tomoe", "resident"}


def _load(path):
    try:
        with io.open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _wards(text):
    """Every ward named in an address, in either script. A ward is the unit a
    news feed, a train board and a place classifier are configured by, and
    those three carried the first character's wards as defaults."""
    out = set()
    for m in re.finditer(r"([A-Z][A-Za-z]+)-ku\b", str(text or "")):
        out.add(m.group(1))
    for m in re.finditer(r"([一-鿿]{2,4})区", str(text or "")):
        out.add(m.group(1))
    return out


def material():
    """{literal: {"what": name|place, "who": {character keys}, "where": file}}.

    `who` is what makes a program package exempt for its own character: a name
    of hers in `tomoe/` is her program naming her, and a name of somebody
    else's in the same file is a leak.
    """
    try:
        from tools import registry
    except ImportError:
        import registry
    out = {}

    def add(n, what, who, where):
        n = str(n or "").strip()
        # three characters for a name, because two ASCII letters are noise.
        # A PLACE written in Japanese is two characters and no more -- 練馬,
        # 豊島, 中野 are whole ward names -- and dropping them meant the ward
        # list a news fetch and a place classifier are configured by was never
        # searched for. Matching is on a word boundary, and a Japanese
        # character is a word character, so 中野 inside a longer word does not
        # match; only the substring pass could, and that one is reported apart.
        if len(n) < (2 if (what == "place" and not n.isascii()) else 3):
            return
        if n.lower() in GENERIC:
            return
        if what == "place" and n.lower() in GENERIC_PLACES:
            return
        row = out.setdefault(n, {"what": what, "who": set(), "where": where})
        row["who"].add(who)

    for row in registry.characters():
        key, cfg = row["key"], _load(row["config"])
        ch, world = cfg.get("character") or {}, cfg.get("world") or {}
        sheet = _load(str(world.get("character_file") or ""))
        ex = dict((ch.get("existence") or {}))
        ex.update(sheet.get("existence") or {})
        for f in ("name", "name_ja", "reading_ja"):
            add(ch.get(f), "name", key, row["config"])
        nm = sheet.get("name") or {}
        if isinstance(nm, dict):
            for k in ("full", "given", "family", "japanese"):
                add(nm.get(k), "name", key, str(world.get("character_file") or ""))
            for k in ("aliases", "aliases_ja"):
                for v in nm.get(k) or []:
                    add(v, "name", key, str(world.get("character_file") or ""))
        for path in (str(ch.get("cast_file") or ""), str(ch.get("own_cast_file") or "")):
            if not path:
                continue
            for k, rec in (_load(path).get("people") or {}).items():
                add(k, "name", key, path)
                if isinstance(rec, dict):
                    for f in ("ja", "reading", "name", "full"):
                        add(rec.get(f), "name", key, path)
                    for v in rec.get("aliases") or []:
                        add(v, "name", key, path)
        # HER PLACES. The list held no place at all, so no ward, station, line,
        # school or neighbourhood was ever searched for -- while the shared body
        # layer handed every embodied character three stations on the first
        # character's commute as her own lived experience.
        place = sheet.get("place") or {}
        for f in ("lives", "school_area", "line"):
            add(place.get(f), "place", key, str(world.get("character_file") or ""))
        # where she is FROM, from her sheet's own words about it. Three of the
        # four are from the same prefecture, so without this its name was one
        # character's place and reported inside the other two's own prompt
        # directories, where it is theirs.
        origin = sheet.get("origin") or {}
        blob = " ".join(str(origin.get(f) or "") for f in ("from", "dialect"))
        for w in ORIGIN_WORDS:
            if w in blob:
                add(w, "place", key, str(world.get("character_file") or ""))
        if not ex.get("in_world", True):
            continue
        geo_path = str(world.get("geography_file") or "")
        geo = _load(geo_path)
        home, station, school = (geo.get("home") or {}), (geo.get("station") or {}), (geo.get("school") or {})
        add(home.get("station"), "place", key, geo_path)
        add(station.get("name_ja"), "place", key, geo_path)
        add(str(station.get("name_ja") or "").replace("駅", ""), "place", key, geo_path)
        add(str(school.get("name") or "").split(" -- ")[0].split(" (")[0], "place", key, geo_path)
        for m in re.finditer(r"[（(]([^）)]+)[）)]", str(school.get("name") or "")):
            add(m.group(1), "place", key, geo_path)
        for s in (geo.get("commute") or {}).get("stops_inbound") or []:
            add(s, "place", key, geo_path)
        for line in station.get("lines") or []:
            add(str(line).split(" (")[0].replace(" line", ""), "place", key, geo_path)
        for area in geo.get("areas") or []:
            for name in ((geo.get(str(area.get("key") or "")) or {}).get("places") or {}):
                bare = str(name).replace("the ", "")
                # a proper noun and not a kind of shop: `Sunshine City` and
                # `Shakujii Park` are places, `purikura` and `shotengai` are
                # nouns, and searching for a noun reports every use of the word
                if bare[:1].isupper() or not bare.isascii():
                    add(bare, "place", key, geo_path)
                    # and its own first word, which is how the place is
                    # written where it is configured rather than described:
                    # the scene classifier's list says `shakujii`, not
                    # `Shakujii Park`
                    head = bare.split(" ")[0]
                    if len(head) >= 5 and head[:1].isupper() and head.isascii():
                        add(head, "place", key, geo_path)
        for where_else in geo.get("elsewhere") or {}:
            add(where_else, "place", key, geo_path)
        for blob in (home.get("address_en"), home.get("address_ja"), station.get("address_en"),
                     station.get("address_ja"), school.get("address_en"), school.get("address_ja")):
            for w in _wards(blob):
                add(w, "place", key, geo_path)
    return out


def names():
    """Every name a person on any character's roster goes by. Kept as its own
    call because two other checks ask for exactly this and nothing else."""
    return {n: row["where"] for n, row in material().items() if row["what"] == "name"}




# Every token type a name can hide in. An f-string has not been one STRING
# token since the tokeniser changed in 3.12 -- it arrives as FSTRING_START /
# FSTRING_MIDDLE / FSTRING_END -- and behind that blindness six places in the
# shared mind wrote the FIRST character's given name into every character's
# event ledger while this check reported that the shared code names nobody.
_WANTED = {tokenize.NAME, tokenize.STRING}
for _n in ("FSTRING_START", "FSTRING_MIDDLE", "FSTRING_END"):
    if hasattr(tokenize, _n):
        _WANTED.add(getattr(tokenize, _n))


def code_tokens(path):
    """(line, text) for every identifier and string literal in the file,
    comments and docstrings left out."""
    src = io.open(path, encoding="utf-8", errors="replace").read()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    doc_lines = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None) or []
            if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
                    and isinstance(body[0].value.value, str):
                for ln in range(body[0].lineno, body[0].end_lineno + 1):
                    doc_lines.add(ln)
    out = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type in _WANTED and tok.start[0] not in doc_lines:
                out.append((tok.start[0], tok.string))
    except (tokenize.TokenError, IndentationError):
        pass
    return out


# Where a person is allowed to live inside the shared prompt directory. The
# bible and the two speech guides ARE the first character, and her cast sheets
# are hers -- her config points at `prompts/cast` and the second character's
# points somewhere else, so they are per-character files that happen to sit
# under a shared path. Everything else in `prompts/` is machinery both
# characters load.
CHARACTER_PROMPTS = ("bible.md", "style.md", "style_ja.md")
CHARACTER_PROMPT_DIRS = (os.path.join("prompts", "cast"),)

# Words that are one person's origin and nobody else's. A dialect, a home
# region, a marker counted off one corpus: none of these is a mechanism, and a
# mechanism prompt that carries one hands it to whoever runs that prompt next.
# The five head-voice roles told the second character that her Hakata comes out
# when she is tired (2026-09-05); she has never had one.
#
# Unlike the name check this reads the RAW text, comments and docstrings
# included, because a comment that says a shared rule is about one region's
# dialect is a comment that will be believed by the next person to edit it.
ORIGIN_WORDS = ("Hakata", "博多", "Kansai", "関西弁", "Fukuoka", "福岡", "ほいで")


def origin_hits():
    """Every place a shared prompt or a shared module names one character's
    dialect or home region."""
    files = [p for p in SHARED_FILES if os.path.exists(p)]
    for d in SHARED_DIRS:
        files += sorted(glob.glob(os.path.join(d, "**", "*.py"), recursive=True))
    for p in sorted(glob.glob(os.path.join("prompts", "**", "*.*"), recursive=True)):
        if os.path.basename(p) in CHARACTER_PROMPTS:
            continue
        if any(p.startswith(d + os.sep) for d in CHARACTER_PROMPT_DIRS):
            continue
        if p.endswith((".txt", ".md")):
            files.append(p)
    out = []
    for path in files:
        try:
            text = io.open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            for w in ORIGIN_WORDS:
                if w in line:
                    out.append((path, n, w, line.strip()[:70]))
    return out


def prompt_dirs():
    """The shared prompt directory and every character's own, with the files
    that ARE a character left out."""
    out = ["prompts"]
    try:
        from tools import registry
    except ImportError:
        import registry
    for row in registry.characters():
        cfg = _load(row["config"])
        for path in (str((cfg.get("character") or {}).get("style_prompt") or ""),
                     str(((cfg.get("models") or {}).get("persona") or {}).get("prompt") or "")):
            d = os.path.dirname(path)
            while d and d not in out and os.path.isdir(d) and os.sep in d:
                d = os.path.dirname(d)
            d = os.path.dirname(path)
            if d and d not in out and os.path.isdir(d):
                out.append(d)
    return out


def owned_prompt_dirs():
    """{directory: character key} for each character's own prompt directory:
    a name of hers there is her own file, and a name of somebody else's is a
    leak."""
    out = {}
    try:
        from tools import registry
    except ImportError:
        import registry
    for row in registry.characters():
        cfg = _load(row["config"])
        for path in (str((cfg.get("character") or {}).get("style_prompt") or ""),
                     str(((cfg.get("models") or {}).get("persona") or {}).get("prompt") or "")):
            d = os.path.dirname(path)
            if d and d != "prompts":
                out[d] = row["key"]
    return out


def programs_of():
    """{character key: her program package}."""
    try:
        from tools import registry
    except ImportError:
        import registry
    return {r["key"]: r["program"] for r in registry.characters()}


def _files():
    """Everything both characters share, by kind of file."""
    out = []
    for p in SHARED_FILES:
        if os.path.exists(p):
            out.append(p)
    for d in tuple(SHARED_DIRS) + SERVED_DIRS + tuple(sorted(PROGRAMS)) + tuple(prompt_dirs()):
        if not os.path.isdir(d):
            continue
        for p in sorted(glob.glob(os.path.join(d, "**", "*.*"), recursive=True)):
            if not p.endswith(EXTENSIONS) or any(s in os.sep + p for s in SKIP_PARTS):
                continue
            if os.path.normpath(p) == os.path.normpath(KNOWN_PATH):
                continue
            if os.path.basename(p) in CHARACTER_PROMPTS:
                continue
            if any(os.path.normpath(p).startswith(os.path.normpath(d2) + os.sep)
                   for d2 in CHARACTER_PROMPT_DIRS):
                continue
            out.append(p)
    seen, uniq = set(), []
    for p in out:
        k = os.path.normpath(p)
        if k not in seen:
            seen.add(k)
            uniq.append(p)
    return uniq


def _exempt(path, row, owned, progs):
    """Is this literal allowed to be in this file?

    A program package is one character's by design: her own name in `tomoe/`
    is her program naming her. A name belonging to a character on the OTHER
    program is not exempt, and neither is a name belonging to nobody who runs
    that program. The same rule for a character's own prompt directory."""
    head = os.path.normpath(path).split(os.sep)[0]
    if head in PROGRAMS:
        return bool(row["who"]) and all(progs.get(k) == head for k in row["who"])
    for d, key in owned.items():
        if os.path.normpath(path).startswith(os.path.normpath(d) + os.sep):
            return key in row["who"]
    return False


def scan():
    """[(file, line, literal, kind, text)] for every finding, in four kinds:
    `code`, `prose`, `inside` and `comment`."""
    wanted = material()
    owned, progs = owned_prompt_dirs(), programs_of()
    pats, loose = {}, {}
    for n in wanted:
        pats[n] = re.compile(r"(?<![\w])" + re.escape(n) + r"(?![\w])", re.I if n.isascii() else 0)
        # inside a longer word, and case-SENSITIVE, because that is what the
        # kind of hit this list exists for looks like: a name kept in its own
        # capitals inside an identifier (`ChromeProfileTomoe`). Folding the case
        # here makes `Rena` a hit on `rename` and `Kana` a hit on every
        # variable holding Japanese kana, which is four hundred findings that
        # are not a leak and would bury the two that are.
        loose[n] = re.compile(re.escape(n))
    out = []
    for path in _files():
        is_py = path.endswith(".py")
        try:
            raw = io.open(path, encoding="utf-8", errors="replace").read().splitlines()
        except OSError:
            continue
        code = {}
        if is_py:
            for line, text in code_tokens(path):
                code.setdefault(line, []).append(text)
        for n, row in wanted.items():
            if _exempt(path, row, owned, progs):
                continue
            rx, rxl = pats[n], loose[n]
            if is_py:
                for line, texts in code.items():
                    for text in texts:
                        bare = text.strip().strip("\"'")
                        if bare.lower() in PROGRAMS:
                            continue
                        if rx.search(text):
                            out.append((path, line, n, "code", text.strip()[:70]))
                        elif rxl.search(text):
                            out.append((path, line, n, "inside", text.strip()[:70]))
                for line, text in enumerate(raw, 1):
                    # a line with no code token on it is a comment or a
                    # docstring, whether the name on it stands alone or sits
                    # inside a longer one: it is not text anybody is handed
                    if line in code or not (rx.search(text) or rxl.search(text)):
                        continue
                    out.append((path, line, n, "comment", text.strip()[:70]))
            else:
                for line, text in enumerate(raw, 1):
                    if rx.search(text):
                        out.append((path, line, n, "prose", text.strip()[:70]))
                    elif rxl.search(text):
                        out.append((path, line, n, "inside", text.strip()[:70]))
    return out, wanted


def known():
    """{(file, literal, kind)} that were already there when the check was
    widened, from `tools/known_literals.json`."""
    doc = _load(KNOWN_PATH)
    return {(os.path.normpath(e.get("file", "")), e.get("literal", ""), e.get("kind", ""))
            for e in doc.get("entries") or []}


def _write_known(hits, wanted):
    import datetime
    rows = {}
    for path, _line, n, kind, _text in hits:
        if kind == "comment":
            continue
        rows[(os.path.normpath(path), n, kind)] = (wanted.get(n) or {}).get("what", "name")
    entries = [{"file": p.replace(os.sep, "/"), "literal": n, "kind": kind,
                "reason": REASONS.get(kind, "").replace("<what>", what)}
               for (p, n, kind), what in sorted(rows.items())]
    doc = {"_what": __doc__.split("\n")[0],
           "_rule": ("Every entry was in the tree on the day the name check was widened to "
                     "places, to five more directories, to five more kinds of file and to a "
                     "match inside an identifier. A finding that is not here fails the run; "
                     "an entry is deleted as its literal moves into the character's own "
                     "files (docs/character-layers-plan.md, step 9)."),
           "_dated": datetime.date.today().isoformat(),
           "_counts": {k: sum(1 for e in entries if e["kind"] == k)
                       for k in ("code", "prose", "inside", "comment")},
           "entries": entries}
    with io.open(KNOWN_PATH, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    return len(entries)


REASONS = {
    "code": "a <what> in shared code, there before the check was widened; step 9 of "
            "docs/character-layers-plan.md moves it into the character's own files",
    "prose": "a <what> in a shared prompt or template, there before the check was widened; "
             "step 9 of docs/character-layers-plan.md moves it into the character's own files",
    "inside": "a <what> inside a longer word, which a word boundary used to hide",
    "comment": "a <what> in a comment or a docstring: a failure history or a worked example, "
               "which is what the comments in this project are for. Left alone on purpose.",
}


def main():
    argv = sys.argv[1:]
    hits, wanted = scan()
    origins = origin_hits()
    if "--write-known" in argv:
        n = _write_known(hits, wanted)
        print(f"{KNOWN_PATH}: {n} entry(s) written from {len(hits)} finding(s)")
        return 0
    was = known()
    # A comment or a docstring is never a failure. This project's comments are
    # failure histories and worked examples, and the name in one is what the
    # history is about; they are counted and listed so a reader knows the check
    # saw them, and they are not what the known list is for.
    new = [h for h in hits
           if h[3] != "comment" and (os.path.normpath(h[0]), h[2], h[3]) not in was]
    show = hits if "--all" in argv else new
    by_kind = {}
    for path, line, n, kind, text in show:
        by_kind.setdefault(kind, []).append((path, line, n, text))
    for kind in ("code", "prose", "inside", "comment"):
        rows = by_kind.get(kind) or []
        if not rows:
            continue
        print(f"{kind.upper()}: {len(rows)} finding(s)")
        for path, line, n, text in rows[:60] if not ("--all" in argv) else rows:
            print(f"  {path}:{line}  {n!r} in {text}")
    if origins:
        print(f"ORIGIN: {len(origins)} place(s) in shared code or a shared prompt name one "
              f"character's dialect")
        for path, line, w, text in origins[:40]:
            print(f"  {path}:{line}  {w!r} in {text}")
    # One summary line at the END whichever way it goes, because `tools/
    # smoke.py` prints the first line of a failing run and the LAST line of a
    # passing one, and a second pass added above that convention would have
    # hidden whichever of the two it was not printing.
    if new or origins:
        print(f"{len(new)} finding(s) not in {KNOWN_PATH} and {len(origins)} dialect word(s) "
              f"in what the characters share")
        return 1
    counts = {}
    for _p, _l, _n, kind, _t in hits:
        counts[kind] = counts.get(kind, 0) + 1
    print(f"nothing new names a character or her places: {len(_files())} file(s), "
          f"{len(wanted)} name(s) and place(s) looked for, "
          + (", ".join(f"{v} {k}" for k, v in sorted(counts.items())) or "no findings")
          + f", all in {KNOWN_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
