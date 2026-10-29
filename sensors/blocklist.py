"""The names of things he had open that no character may be shown.

`sensors.window_title_blocklist` is one list and it is not only about window
titles. The same name reaches her by three routes: the title bar of the window
itself, the FOLDER a file manager is showing (its whole title is a path), and
the title of a page in his browsing history. His project's name arrived in her
prose the third way on 2026-09-04, through a Google search whose query was a
path -- the URL was google.com, which no junk filter names, and the page title
carried the path whole.

So the patterns are compiled once here and every sensor that emits a name of
something he had open asks this module. One rule, one place, and a pattern
added to the config reaches all of them.

What is done with a match differs by source, and that is the caller's to say.
A window is BLANKED and never dropped: dropping it would leave
`SystemMonitor.right_now` on the window before it, and the window still counts
with its process and its minutes. A visit in a browsing log has no such
continuity behind it and is dropped whole.
"""
import re

import logger

# A browser puts its own name after the page's title ("Leg - Claude -- Mozilla
# Firefox"), so a pattern anchored to the end of a title never matched a
# browser window and the assistant's tab reached her as "firefox: Leg -
# Claude" (2026-09-04). Every candidate is tried both raw and with this off.
BROWSER_SUFFIX = re.compile(r"\s+[—–-]+\s+(Mozilla Firefox|Google Chrome|Microsoft Edge|Brave|Chromium|Opera|Vivaldi)"
                            r"(\s+\((Private|InPrivate) Browsing\))?\s*$", re.I)

_COMPILED = {}
_HIDDEN = {}


def hidden(config, proc):
    """Is this a program whose own NAME no character may be shown?

    `blocks` answers about a name a WINDOW carries; this answers about the
    program itself. Blanking the terminal titles left the process name behind,
    and for a terminal the program name IS what he is doing: "WindowsTerminal"
    stood in the second character's rolling account of his machine, her window
    trail, her live status line, her picture of his habits, her facts about
    him and her own written reflections on 2026-09-05, with every title
    already blank.

    A window whose program is hidden is never dropped. Dropping it would leave
    the account saying the machine was quiet through the hours he typed four
    thousand keys into it. It keeps its clock and its minutes and loses its
    name.
    """
    p = str(proc or "").lower()
    if not p:
        return False
    raw = tuple(str(x).lower() for x in (getattr(config, "hidden_processes", None) or []))
    if raw not in _HIDDEN:
        _HIDDEN[raw] = set(raw)
    return p in _HIDDEN[raw]


def patterns(config):
    """The compiled blocklist for this config, compiled once per list."""
    raw = tuple(str(p) for p in (getattr(config, "window_title_blocklist", None) or []))
    if raw not in _COMPILED:
        out = []
        for p in raw:
            try:
                out.append(re.compile(p, re.IGNORECASE))
            except re.error as e:
                logger.log(f"[SYSMON] bad window_title_blocklist pattern {p!r}: {e}")
        _COMPILED[raw] = out
    return _COMPILED[raw]


def blocks(config, text):
    """Is this name of something he had open -- a window title, a folder, a
    path, the title of a page he visited -- one she must not be shown?"""
    t = str(text or "")
    if not t.strip():
        return False
    core = BROWSER_SUFFIX.sub("", t)
    for p in patterns(config):
        if p.search(t) or (core != t and p.search(core)):
            return True
    return False
