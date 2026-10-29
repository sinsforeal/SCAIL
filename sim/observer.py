"""What a judge is allowed to know about her.

A role that decides, scores, predicts, sorts or checks is a neutral party and
never gets her character sheet (`Config.ROLE_STANCE`, his call 2026-09-05).
The sheet is written TO her, in the second person, opens "You are <her name>
... you are not an assistant ... you never mention prompts, models, systems",
and it used to sit LAST in a judge's system prompt -- so the judge read it as
its own identity. Measured over 2026-09-04 and 09-05: the role that picks
which urge she has returned a finished message in her voice instead of the
second-person intention it was asked for on 13 of 13 answers, and one of them
went into the last line of her situation block and was sent as her next bubble
twelve seconds later.

But three judges genuinely have to know what she is like -- what stings her,
what she would keep on a timeline, which headlines would reach her at all --
and the answer to that is not "give them the sheet back" and not "hand-write a
second sheet in the third person", which would drift from the first the day he
edits a line of her voice.

So: ONE observer's note, generated FROM the sheet by a model, cached in her
save under the sheet's own hash, and rewritten only when the sheet changes.
Third person throughout, English, machine-facing -- nobody is addressed in it,
so the language rule that puts everything said TO a character in her language
does not apply (CLAUDE.md; `docs/language.md`). One flash call per bible edit.

Read it with `observer.digest(config, llm, store)`. Every judge already holds
those three, so this needs no wiring and no new collaborator.
"""
import hashlib
import time

import logger

KV = "observer_digest"
# the same note for a caller with no save, for the life of that process
_MEM = {}
# The sheet's own opening, in either character's language. A digest that
# contains one of these is the sheet leaking through the rewrite, which is the
# one failure this whole module exists to prevent.
_SHEET_TELLS = ("You are not an assistant and not a text generator",
                "You never break frame, never mention prompts",
                "アシスタントでもテキスト生成器でもない",
                "プログラムとしてではなく、あなたとして反応する")


def _sheet_text(config):
    try:
        return config.prompt_text("persona") or ""
    except Exception as e:
        logger.log(f"[observer] her character sheet could not be read: {type(e).__name__}")
        return ""


def _hash(text):
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:16]


def leaks_the_sheet(text):
    """The sentence of the sheet this note copied, or "" if it copied none."""
    for tell in _SHEET_TELLS:
        if tell in (text or ""):
            return tell
    return ""


def digest(config, llm, store, rebuild=False):
    """The observer's note about her, generated once per version of her sheet.

    Returns "" rather than raising: a judge without the note is a judge with
    less to go on, which is the state every judge was in before this existed;
    a judge that crashes is a turn nobody takes.
    """
    sheet = _sheet_text(config)
    if not sheet.strip():
        return ""
    want = _hash(sheet)
    # A caller with no save is the headline reader, which runs as its own
    # one-shot process on its own clock (`tools/zeitgeist.py`). It gets the
    # same note, cached for the life of that process instead of across boots:
    # one flash call per run of a worker that runs a few times a day, rather
    # than a store parameter threaded through a tool that has never needed one.
    if store is None:
        hit = _MEM.get(want)
        if hit and not rebuild:
            return hit
        row = None
    else:
        try:
            row = store.get(KV, None) or None
        except Exception:
            row = None
    if isinstance(row, dict) and not rebuild and row.get("hash") == want and str(row.get("text", "")).strip():
        return str(row["text"]).strip()

    had = isinstance(row, dict) and str(row.get("text", "")).strip()
    why = "her character sheet changed" if had else "there was none yet"
    text = ""
    try:
        text = (llm.call("observer", [
            {"role": "system", "content": config.prompt_text("observer")},
            {"role": "user", "content": sheet}]) or "").strip()
    except Exception as e:
        logger.log(f"[observer] the note was not written ({type(e).__name__}); "
                   f"the judges run without it")
        text = ""
    if not text:
        # Keep the old note rather than dropping to nothing: a stale note about
        # a sheet whose last paragraph moved is worth more to a judge than no
        # note at all, and the hash is left alone so the next boot tries again.
        return str((row or {}).get("text", "") or "").strip()

    leak = leaks_the_sheet(text)
    if leak:
        logger.log(f"[observer] the note came back with the sheet's own words in it "
                   f"({leak[:40]!r}); it is not kept and the judges run without it")
        return str((row or {}).get("text", "") or "").strip()

    lines = [l for l in text.splitlines() if l.strip()]
    if store is None:
        _MEM[want] = text
    else:
        try:
            store.set(KV, {"hash": want, "text": text, "ts": time.time(),
                           "model": llm.effective_model("observer")})
        except Exception as e:
            logger.log(f"[observer] the note was written but not saved: {type(e).__name__}")
    logger.log(f"[observer] a fresh observer's note about her, {len(lines)} line(s), "
               f"because {why}")
    return text


def block(config, llm, store, heading="WHAT SHE IS LIKE (an observer's note about her, "
                                     "written from her own record; she is not reading this "
                                     "and it is not addressed to her):"):
    """The note with its heading, or "" -- what a judge's user message appends."""
    text = digest(config, llm, store)
    return (heading + "\n" + text) if text else ""
