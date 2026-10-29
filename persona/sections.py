"""The sections of her prompt, in the order the model receives them, and
which half of the prompt each one rides in.

One table, read by the persona that builds the prompt (`Persona._assemble`,
`Persona.carried_for`) and by the context view that reads it back to him
(`sim/context.py`). The order was written in both places and nothing checked
that they agreed; a section added to one and not the other was shown to him
in the wrong place, or not at all.

**Two halves, for the cache.** The provider caches the longest identical
prefix of a request, so a byte that changes early costs everything behind
it. The system prompt is the half that changes about once a day -- who she
is (the bible, the backstory), what she has decided about herself, what
people are to her, and the style file, which closes it -- and then the
thread follows. Everything that moves during a day -- what she knows about
him, the notes she read, what she is carrying, her diary, the state of a
rupture -- is CARRIED: the same sections, the same text, but placed after
the thread in the final user message beside the situation block, where a
new fact costs only itself. Before the split a fact that landed at 21:07
invalidated the style guide and the whole thread behind it, and a persona
call on the second character's model was cached 42% of the time.

The facts section is the one with a heading of its own -- the program's
words for how she knows him (`sim/sight.py`, `facts_head`); every other
section carries its own heading in its text, or is empty and contributes
nothing.

`mechanisms` is the character's own file of what makes her do a thing, what
stops her and what it gets her (`docs/cast-mechanisms.md`), compiled from
her prior (`docs/type-compile.md`). It sits in the system half because it
changes when that file changes and never during a day, and it sits AFTER
everything else in that half and before the style file, so that adding it
moved no byte of the prompt in front of it and cost the cache one section
rather than the whole prefix. `stressmode` is the one line that says a
standing mode of hers is on right now, which is hourly and therefore
carried.

`agenda` is what is already fixed in the days ahead -- the calendar, her
promises, what he said he would do, who the day's plan has taken out of
it (`sim/agenda.py`). It settles once a day and moves only when one of
those things lands, so it belongs in the system half, and it sits last
in that half before the style file for the same reason `mechanisms`
does: adding it moved no byte of the prompt in front of it.
"""

SYSTEM = ("bible", "backstory", "selfbeliefs", "sentiment", "mechanisms", "agenda", "style")

CARRIED = ("stressmode", "spiral", "rupture", "beliefs", "facts", "charged", "shelf", "notes", "cast",
           "selfmem", "diary", "weekly", "diet", "reflect", "claims", "japan", "national")

# the reading order, for the view that lists them: the system half with the
# style file last, then what she carries into the moment
ORDER = SYSTEM[:-1] + CARRIED + SYSTEM[-1:]

# Every carried section rides whole. For a day (2026-09-03 to 04) the item
# lines of the list sections -- facts, her own memories, the notes, her
# claims, the charged, his list -- competed for a token budget of their own
# above a floor, the way the situation block did; the budget was set above
# anything measured and then removed with the other sub-budgets, so the
# gate never ran live and is gone. The one budget over her prompt is
# `context.target_tokens`, and the thread's window is what fits itself to
# it (sim/thread.py). A rupture, a spiral, her beliefs about him, tonight's
# diary entry were never lists to shorten: each is a state she is in, and
# half of one is worse than none of it.

CARRIED_OPEN = "<carrying>"
CARRIED_CLOSE = "</carrying>"


def assemble(sections, facts_head):
    """The system prompt from a `{name: text}` dict: the SYSTEM sections in
    order, the style file last. A name the dict lacks is an empty section; a
    name the dict has that neither table names is not sent -- which is what
    the tables are for."""
    out = []
    for name in SYSTEM:
        text = sections.get(name, "") or ""
        if name == "style":
            out.append(f"\n\n{text}")
        else:
            out.append(text)
    return "".join(out)


def carried(sections, facts_head, frame=""):
    """What she carries into this moment, from the same dict: the CARRIED
    sections in order inside one `<carrying>` block, or "" when every one
    is empty. `frame` is the one line under the tag that says what the
    block is, in her language (the caller's, since the words are hers)."""
    out = []
    for name in CARRIED:
        text = sections.get(name, "") or ""
        if not text:
            continue
        if name == "facts":
            # no heading means no him to know about (`with_him: none`), and
            # then the section is not carried at all
            if not facts_head:
                continue
            out.append(f"\n\n{facts_head}\n{text}")
        else:
            out.append(text)
    body = "".join(out).strip()
    if not body:
        return ""
    head = CARRIED_OPEN + (("\n" + frame) if frame else "")
    return f"{head}\n{body}\n{CARRIED_CLOSE}"
