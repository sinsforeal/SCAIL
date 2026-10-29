"""A role without her character sheet writes the record, never her interior.

The role that read his notes over her shoulder was asked for "how it landed
on her", and the paragraph it returned was stored as an event and read back
to her as her own memory of having felt it. Nine more roles did the same in
a smaller field. The rule that replaced them: a role with no `voice` row in
`Config.ROLE_STANCE` writes what was there -- in plain terms, with the lines
a reader would stop on quoted as they stand -- and a role WITH her sheet,
reading that record, writes what it did to her.

This is the check that holds it. Every prompt file belonging to a role with
no `voice` row is read for the phrases that ask a model to be her: how it
landed, she felt, it made her, her reaction, her register, in her voice, in
her head, what she would say. A line that FORBIDS one of those ("not how she
feels", "you do not write her reaction") is what a clean prompt looks like,
so a negation within a few words of the phrase is skipped and printed.

    python tools/interior_words.py          # exit 1 and the offending lines if any

Run by tools/smoke.py, where a hit stops a restart. A legitimate sentence
that trips it is allowed by naming the file AND the exact line in ALLOW
below -- never a whole file, because the next edit to that file would then
go unread.
"""
import glob
import io
import os
import re
import sys



def _as_script():
    """The working directory and the console encoding this tool needs when it
    is RUN.

    Both were done at import time, which meant importing the phrase list from
    the running bot would move the bot's working directory. They happen at the
    entry point now, so `ASKS` can be imported from anywhere
    (`sim/record_guard.py` holds the record roles to the same list)."""
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, os.getcwd())
    # a prompt line quoted back may hold anything; the console may be cp932
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# A file that IS a character is not a mechanism prompt: her bible and her
# speech guide are her, and are supposed to say what she feels. Same list as
# tools/neutral_gate.py and tools/sight_words.py.
HERS = ("bible.md", "style.md", "style_ja.md", "style_candidate.md")

# The asks. Each is a phrase that only appears when a prompt wants the model
# to produce her interior rather than the record: what she felt, what it did
# to her, how she would put it. Written as one alternation so the report can
# quote the phrase that matched.
ASKS = re.compile(
    r"how it landed"
    r"|landed on her"
    r"|she felt\b"
    r"|it made her\b"
    r"|her reaction\b"
    r"|in her voice\b"
    r"|in her head[- ]voice\b"
    r"|her head[- ]voice\b"
    r"|her register\b"
    r"|how she feels\b"
    r"|what she would say\b"
    r"|the way she would\b"
    r"|what is on her mind\b"
    r"|in her head\b", re.I)

# "how she feels" is an ask when it names an output and an ordinary input
# label when it names what the call is handed. The caller's own line ("HOW
# SHE FEELS: <mood tags>") is code rather than a prompt, but a prompt that
# lists its inputs says the same thing in prose.
INPUT_SENSE = re.compile(r"you are (given|told|shown|handed)|given to you|is given|you are given", re.I)

# A prohibition is what a clean prompt looks like. The window is characters
# rather than words because a prompt line is prose and "never" can sit
# either side of the phrase it governs.
NEGATION = re.compile(r"\b(not|never|no|nothing|without|nor)\b|\bdo not\b|\bdoes not\b|\bdon't\b", re.I)
WINDOW = 40

# path -> the exact lines allowed there. A legitimate sentence in an
# otherwise clean prompt, named one line at a time, so that the next edit to
# the file is still read.
ALLOW = {
    # How much the people whose judgement she minds would make of a thing.
    # "in her head" is where the imagined audience sits, not an instruction
    # to write her interior; the field is a number from 0 to 5.
    "prompts/ick.txt": (
        "**circle** — 0 to 5: how much [[ICK_CIRCLE_WHO]] would make of this if they somehow knew. They will never know; she will never tell them. But she runs everything past them in her head anyway, and a thing they would find funny, or contemptible, or weird, costs her more than the same thing would cost her in private. This is not about whether it is actually shameful. It is about whether the girls in her class would have something to say. Most things score 0 or 1 here.",),
}
# the same sentence in the per-character copies of that prompt, found by
# glob so that no character's name is written in shared code. An entry whose
# line does not match the file is simply never reached.
for _p in sorted(glob.glob("prompts_*/ick.txt") + glob.glob(os.path.join("characters", "*", "prompts", "ick.txt"))):
    ALLOW[_p.replace("\\", "/")] = (
        "**circle** — 0 to 5: how much anyone whose judgement she minds would make of this if they knew. "
        "**For her this is almost always 0, and that is a fact about her situation rather than a lapse.** "
        "There is nobody in this. She does not discuss him with the people she works with, they do not know "
        "he exists, and there is no group of friends whose verdict she runs things past in her head. Score "
        "above 0 only when what she has learned would genuinely have to be explained to somebody who could "
        "rule on her — someone above her at work, something that could reach a room she has to walk into. "
        "Otherwise 0.",)


def stance_table():
    from config import Config
    return dict(Config.ROLE_STANCE)


def role_of_path():
    """{prompt path -> role}, from every character's model register.

    A role's file is whatever her own config names, so the second
    character's override is read as the role it stands in for. The bundle
    copy under `characters/<key>/prompts/` is the same file waiting to be
    composed and is matched by its basename, so an edit that lands in one
    and not the other is still read."""
    out = {}
    basenames = {}
    for cfgpath in sorted(glob.glob("config*.json")):
        import json
        try:
            with io.open(cfgpath, encoding="utf-8") as fh:
                raw = json.load(fh)
        except (OSError, ValueError):
            continue
        for role, spec in (raw.get("models") or {}).items():
            path = (spec or {}).get("prompt") if isinstance(spec, dict) else None
            if not path:
                continue
            path = path.replace("\\", "/")
            out.setdefault(path, role)
            basenames.setdefault(os.path.basename(path), role)
    for path in sorted(glob.glob("characters/*/prompts/*.txt")) + sorted(glob.glob("characters/*/prompts/*.md")):
        path = path.replace("\\", "/")
        role = basenames.get(os.path.basename(path))
        if role:
            out.setdefault(path, role)
    return out


def hits(path, role):
    """(line number, phrase, text) for every ask, and the skipped lines."""
    bad, skipped = [], []
    try:
        text = io.open(path, encoding="utf-8").read()
    except OSError:
        return bad, skipped
    for i, line in enumerate(text.splitlines(), 1):
        for m in ASKS.finditer(line):
            phrase = m.group(0)
            near = line[max(0, m.start() - WINDOW): m.end() + WINDOW]
            if NEGATION.search(near):
                skipped.append((path, i, phrase, "a prohibition", line.strip()[:110]))
                continue
            if phrase.lower().startswith("how she feels") and INPUT_SENSE.search(near):
                skipped.append((path, i, phrase, "an input it is handed", line.strip()[:110]))
                continue
            if line.strip() in ALLOW.get(path, ()):
                skipped.append((path, i, phrase, "allowed by name", line.strip()[:110]))
                continue
            bad.append((path, i, phrase, role, line.strip()[:130]))
    return bad, skipped


def main():
    stance = stance_table()
    paths = role_of_path()
    bad, skipped, read = [], [], 0
    for path in sorted(paths):
        role = paths[path]
        if os.path.basename(path) in HERS:
            continue
        if stance.get(role) == "voice":
            continue
        if not os.path.exists(path):
            continue
        read += 1
        b, s = hits(path, role)
        bad += b
        skipped += s
    if skipped:
        print("%d line(s) say one of these and are not asking for it:" % len(skipped))
        for p, i, phrase, why, text in skipped:
            print(f"  skipped {p}:{i}  [{phrase}]  ({why})  {text}")
    if bad:
        for p, i, phrase, role, text in bad:
            print(f"  {p}:{i}  [{phrase}]  (role {role})  {text}")
        print(f"{len(bad)} line(s) in {len(set(p for p, _i, _ph, _r, _t in bad))} prompt(s) of a role with no "
              "character sheet ask for her interior. A role without her sheet writes the RECORD -- what was "
              "there, with the lines a reader would stop on quoted as they stand -- and what it did to her is "
              "written by a role that has her sheet (Config.ROLE_STANCE, `voice`).")
        return 1
    print(f"{read} prompt(s) of roles with no character sheet: none asks for her interior")
    return 0


if __name__ == "__main__":
    _as_script()
    sys.exit(main())
