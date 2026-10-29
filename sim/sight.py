"""How she comes to know what he does on his machine -- the words for it.

The mind library never says "the app on her phone" or "what she saw on his
machine": which of those is true is a property of the program running her,
not of the mind. Each program registers its table (`tomoe/words.py`,
`resident/words.py`) and the library asks `w(config, key)` for a phrase or
`w2(config, key)` for the English and Japanese pair the persona's `t()` takes.
A key nobody registered raises at first use, in smoke, rather than rendering
a hole. `tools/sight_words.py` (in smoke) fails on a shared file that names
the app itself, which is how the wording is kept out of the library for good.

The first character's table is the wording the library carried before this,
byte for byte, so nothing she reads changed when it moved.
"""
_TABLES = {}


# Which package registered which table, so a character whose program is the
# resident one and whose sight of him is `none` still gets her own program's
# words rather than a KeyError.
_BY_PROGRAM = {}


def register(program, table):
    _TABLES[program] = dict(table)
    import inspect
    frame = inspect.stack()[1]
    pkg = str(frame.frame.f_globals.get("__name__", "")).split(".")[0]
    if pkg:
        _BY_PROGRAM[pkg] = program


def _table(config):
    prog = "resident" if config.resident else "app"
    if prog not in _TABLES:
        # the entry points register their own; this is the safety net for a
        # tool that builds the persona without one. The program is the one
        # her config names, so the library never writes a program's name.
        import importlib
        importlib.import_module(str(getattr(config.character, "program", "") or "") + ".words")
    if prog not in _TABLES:
        # Her program registered under another name. That happens for one kind
        # of character: her sheet says she has no sight of him AT ALL, so the
        # sight test does not call her resident, while the program she runs on
        # is the resident one and has registered only its own table. The
        # library must not pick between two programs' words, so it takes the
        # one HER program registered and nothing else.
        mine = _BY_PROGRAM.get(str(getattr(config.character, "program", "") or ""))
        if mine and mine in _TABLES:
            return _TABLES[mine]
    return _TABLES[prog]


def w(config, key, **kw):
    s = _table(config)[key]
    return s.format(**kw) if kw else s


def w2(config, key, **kw):
    en, ja = _table(config)[key]
    return (en.format(**kw), ja.format(**kw)) if kw else (en, ja)
