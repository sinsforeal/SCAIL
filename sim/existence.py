"""What kind of thing a character is, as questions the library may ask.

Her sheet answers five of them (`character.existence`) and `Config.REQUIRES`
turns those answers into which sections run. This is the other reader of the
same answers, for the handful of places where an OBJECT or a WORDING depends
on what she is rather than on a section being on:

  * nothing builds an app that reads his machine for a character who has no
    sight of it, the way the calendar loads no data for a character with no
    world;
  * a heading that says "what you told him" belongs to a character who has a
    chat with him, and a character who has not needs the same list under a
    heading that is true of her.

One function per question, so a call site cannot invent a sixth answer out of
`getattr` and a default, and so the words a sheet may answer with live in one
file. Nobody is named here and nothing is imported: it reads the config and
returns a boolean.
"""


def _ex(config):
    return getattr(getattr(config, "character", None), "existence", None)


def _answer(config, key, default):
    return str(getattr(_ex(config), key, default) or default).lower()


def has_chat(config):
    """Has she a chat with him at all. False is a character who exists for
    somebody else's circle: no relationship layer, no writing to him first,
    no facts about him, and no heading that defines her against him."""
    return _answer(config, "with_him", "chat") != "none"


def sees_him(config):
    """Has she any window on his machine. False switches off everything that
    reads it, the app included: what a character has not got is absent rather
    than switched off."""
    return _answer(config, "sees_him", "digest") != "none"


def is_resident(config):
    """Is his machine in front of her, rather than something she looks at
    through an app on her phone."""
    return _answer(config, "sees_him", "digest") == "resident"
