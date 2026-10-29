"""The mind library does not know how she sees him.

"The app on her phone" is true of the first character and false of the
second, and for a day the shared code said it to both: her editor binned a
true remark as a leak, her diary was asked what the app showed her. The words
live in each program now (`tomoe/words.py`, `resident/words.py`, through
`sim/sight.py`), and this is the check that keeps them there: every string
literal in the shared code, and every line of a shared mechanism prompt that
is not inside a `[[?digest]]` block, is read for the phone-app sense of "the
app" and "her phone". Comments and docstrings are not read; they are for the
person maintaining the code and may say what the code used to do.

    python tools/sight_words.py          # exit 1 and the offending lines if any

Run by tools/smoke.py. A module that is a person's rather than the mind's
(the cast, the exchange, the world, her body) is listed in PERSONS and will
be checked once it moves to her package.
"""
import ast
import glob
import io
import os
import re
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# a prompt line quoted back may hold anything; the console may be cp932
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SHARED = ["scail.py", "llm.py"] + sorted(glob.glob("sim/*.py")) + sorted(glob.glob("persona/*.py")) \
    + sorted(glob.glob("world/*.py")) + sorted(glob.glob("channels/*.py"))
# the first character's modules live under tomoe/ and are not scanned; what is
# left under sim/ and world/ is the mind and the clock
PERSONS = set()
PROMPTS = sorted(glob.glob("prompts/*.txt"))

# the phone-app sense only. "the app's labels" / "the app's clock" are TALKAPP,
# the messenger, and are true of both characters.
APP = re.compile(r"(app on (her|your) phone|phone app|APP SHOWED|the app show(s|ed)|look(ed|s|ing)? at the app"
                 r"|open(ed|s|ing)? the app|on the app\b|the app, which|the app is |the app about|the app at \{"
                 r"|or the app\b|and the app\b|from the app\b|through the app\b|the app decides"
                 r"|the app that (mirrors|shows)|the app's (live|digest|day)|her app\b"
                 r"|off her phone|checks? her phone|her phone (face down|in her hand|at midnight|under|every)"
                 r"|does with her hands and her phone|on her phone|long[- ]distance)", re.I)


def strings_of(path):
    """(line, text) for every string literal that is not a docstring."""
    src = io.open(path, encoding="utf-8").read()
    tree = ast.parse(src)
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
                    and isinstance(body[0].value.value, str):
                docs.add(id(body[0].value))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs:
            out.append((node.lineno, node.value))
    return out


# the schoolgirl's day, which was the shared schedule's presence table until
# it moved to her words table. Shared code only; the rendered-prompt pass
# below uses the wider list, because a prompt says it in prose.
SCHOOL = re.compile(r"\bhomeroom\b|\bin class\b|cleaning duty|between lessons|lunch break", re.I)

# What a fifteen-year-old's day is made of, in either language, as it would
# appear in a prompt sentence. Every entry has to be a word that cannot mean
# anything else in a mechanism prompt: "class" is a category, "term" is a
# search term, "a lesson" is what she has not learned, "15" is a count of
# minutes, and each of those is in a live prompt for a good reason. Plural
# "lessons" and the compounds below only ever mean school.
SCHOOLGIRL = re.compile(
    r"\bhomeroom\b|\bclassroom\b|\bclassmates?\b|cleaning duty|lunch break|between lessons"
    r"|\blessons\b|after school|school day|\bschools?\b|\bschoolgirl\b|\bhomework\b"
    r"|cram school|\buniforms?\b|\bteachers?\b|\bexams?\b|\brecess\b|\bsemester\b|term time"
    r"|\bteenager\b|\bteenage\b|fifteen[ -]year|\b15[ -]year"
    r"|学校|教室|授業|宿題|部活|制服|クラスの|女子高生|給食|掃除当番|放課後|同級生|担任|塾"
    r"|期末テスト|期末試験|中間テスト|中間試験", re.I)

# A file that IS a character is not a mechanism prompt: her own past is hers,
# and she talks about her own school days on the radio. Same rule as
# tools/neutral_gate.py, which will not cut holes in these either.
HERS = ("bible.md", "style.md", "style_ja.md", "style_candidate.md")


def programs():
    """The directories that are a character's program rather than the library.
    A program's prompts belong to its own character; a role that names one in
    another character's config is a role her existence switches off, and its
    file must not be read as something she is sent."""
    return {d for d in os.listdir(".")
            if os.path.isdir(d) and os.path.exists(os.path.join(d, "app.py"))}


def rendered_school_hits():
    """Every prompt a character with no world can be sent, rendered with her
    own fills and read for a schoolgirl's day.

    A prompt is not shared code and the static pass cannot see it: the line
    that told a twenty-seven-year-old woman she was fifteen was in a mechanism
    file, behind no fork, and only appeared once the file was filled in for
    her. So this renders it the way her process will."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import Config

    progs = programs()
    bad, quiet = [], io.StringIO()
    for cfgpath in sorted(glob.glob("config_*.json")):
        real, sys.stdout = sys.stdout, quiet          # her build talks; nobody needs it here
        try:
            cfg = Config(path=cfgpath)
            cond = cfg.conditions()
            if cond.get("in_world", True):
                continue
            mine = str(getattr(cfg.character, "program", "") or "")
            seen = set()
            for role, spec in sorted((cfg.raw.get("models") or {}).items()):
                path = (spec or {}).get("prompt") if isinstance(spec, dict) else None
                if not path:
                    continue
                path = path.replace("\\", "/")
                head = path.split("/")[0]
                if path in seen or head in progs and head != mine:
                    continue
                if os.path.basename(path) in HERS:
                    continue
                # A role whose prompt belongs to the SCAILV3 library and whose
                # file is not in this fork (Momoka's bundle leaves its section
                # off) has no wording to read; skip it the way smoke skips it.
                if not os.path.exists(path):
                    continue
                seen.add(path)
                for i, line in enumerate(cfg.prompt_text(role).splitlines(), 1):
                    m = SCHOOLGIRL.search(line)
                    if m:
                        bad.append((path, i, m.group(0), role, line.strip()[:110]))
        finally:
            sys.stdout = real
    return bad


def main():
    # SCAILV4 runs one character who IS a schoolgirl the game put in a school
    # and whose bundle deliberately gives her no world. The rendered-school
    # pass below is the v3 rule for a worldless ADULT (it caught a mechanism
    # prompt telling a twenty-seven-year-old she was fifteen); for this fork
    # every shared prompt that names the school is correct, so `--no-school`
    # runs the shared-code pass alone. smoke calls it that way.
    no_school = "--no-school" in sys.argv[1:]
    bad = []
    for path in SHARED:
        p = path.replace("\\", "/")
        if p in PERSONS:
            continue
        try:
            for line, text in strings_of(p):
                m = APP.search(text) or SCHOOL.search(text)
                if m:
                    bad.append((p, line, m.group(0), text.strip().replace("\n", " ")[:90]))
        except SyntaxError as e:
            bad.append((p, e.lineno or 0, "syntax", str(e)[:90]))
    # a [[^resident]] block is the first character's wording as much as a [[?digest]] one
    block = re.compile(r"\[\[\?digest\]\].*?\[\[/digest\]\]|\[\[\^resident\]\].*?\[\[/resident\]\]", re.S)
    for path in PROMPTS:
        text = io.open(path, encoding="utf-8").read()
        stripped = block.sub("", text)
        for i, line in enumerate(stripped.splitlines(), 1):
            m = APP.search(line)
            if m:
                bad.append((path.replace("\\", "/"), i, m.group(0), line.strip()[:90]))
    rc = 0
    if bad:
        for p, line, hit, text in bad:
            print(f"  {p}:{line}  [{hit}]  {text}")
        print(f"{len(bad)} place(s) in the shared code or a shared prompt still say how she sees him; "
              "the words belong in tomoe/words.py and resident/words.py (sim/sight.py)")
        rc = 1
    else:
        print(f"shared code and {len(PROMPTS)} mechanism prompts: nothing says how she sees him; the words are the programs'")

    if no_school:
        print("rendered-school pass skipped (--no-school): this fork's one character is a "
              "schoolgirl with no world, so the v3 worldless-adult rule does not apply")
        return rc
    school = rendered_school_hits()
    if school:
        for p, line, hit, role, text in school:
            print(f"  {p}:{line}  [{hit}]  (role {role})  {text}")
        print(f"{len(school)} line(s) tell a character with no world about a schoolgirl's day. "
              "Put the first character's world inside [[?in_world]]...[[/in_world]], or move the "
              "wording to a [[TOKEN]] in data/characters/neutral/<id>.json with her exact span as "
              "the first character's value (tools/neutral_gate.py proves she is unchanged).")
        rc = 1
    else:
        print("rendered prompts for a character with no world: no school day in any of them")
    return rc


if __name__ == "__main__":
    sys.exit(main())
