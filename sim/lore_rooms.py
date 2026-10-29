"""Her own record reaching her in the rooms with her own people.

The retrieval itself is `sim/lore.py` and none of it is repeated here. What
this module is, is the ONE way a room asks it: how the room's turns are split
into the two sides the retrieval reads, and the one line that goes over the
answer. Until 2026-09-06 only her reply to him asked at all
(`persona/persona.py`), so a character whose life is in her record -- 81
records and 320 cue phrases for the promoted one -- remembered none of it
with her friends, in the rooms where most of her words are written.

The split is the whole of it and it is `sim/lore.py`'s rule, not a new one.
What the OTHERS have said since her last turn is the conversation reaching
for something, and a record it names is reachable however often they name
it. Her own recent turns name a record just as well -- she is often the one
who raised the thing -- but they are also where she has just TOLD it, and a
telling stays in the window for the next few turns, so her own side is the
only one an already-offered record is held against (`lore.own_words_days`).
Handing both sides in as one cue is what made the second character tell the
same anecdote three turns running.

A character with no record of her own has `Persona.lore` None and every
function here returns nothing, so a room's assembly is byte-identical for
her.
"""

import logger
from sim import lang


def window(config):
    """How many of the room's turns the retrieval is asked over.

    `lore.cue_exchanges` counts exchanges and a turn is half of one, the way
    her reply to him counts it. 0 means no window at all rather than no
    turns: a room with a short history is still a room she can be reminded
    in."""
    try:
        return max(0, int(getattr(config.lore, "cue_exchanges", 3) or 0)) * 2
    except (TypeError, ValueError):
        return 6


def _said(turn):
    """What was actually typed. Her rooms are Japanese and the gloss is the
    machine's, so the Japanese is the cue and the English beside it is not."""
    return str(turn.get("ja") or turn.get("text") or "").strip()


def cue_echo(turns, is_self, back):
    """(what the others are asking with, what she has said herself).

    `is_self` is asked about a turn's `who` and is the caller's, because a
    room she owns names her one way and a room she was invited into names
    her another."""
    rows = [t for t in (turns or []) if _said(t)]
    if back > 0:
        rows = rows[-back:]
    last_mine = -1
    for i, t in enumerate(rows):
        if is_self(t.get("who")):
            last_mine = i
    cue = [_said(t) for i, t in enumerate(rows) if i > last_mine and not is_self(t.get("who"))]
    echo = [_said(t) for t in rows if is_self(t.get("who"))]
    return "\n".join(cue), "\n".join(echo)


def lines(persona, config, turns, is_self, context_text=""):
    """The lines of her record this room reached for, tagged `lore` -- the
    same source her reply to him uses, so one weight and one entry in the
    attention table cover both rooms. Usually empty, which is the point.

    Guarded: a retrieval that fails is logged by type and the turn is
    written without it. Her record is not worth a turn of hers."""
    lr = persona.lore if persona is not None else None
    if lr is None:
        return []
    cue, echo = cue_echo(turns, is_self, window(config))
    if not (cue.strip() or echo.strip() or str(context_text or "").strip()):
        return []
    try:
        return list(lr.lines(cue, context_text=str(context_text or ""), echo_text=echo) or [])
    except Exception as e:
        logger.log(f"[lore] not retrieved for a room of her own: {type(e).__name__}: {e}")
        return []


def preamble(config):
    """The one line over the retrieved lines, in her language.

    Every other line in a room's block is something happening now. Without a
    header a thing she has known for years reads as an event and she answers
    it; with the wrong header it reads as a brief and she recites it. The
    wording is her reply to him's, so the same lines are framed the same way
    wherever she meets them (`persona/persona.py:_admit`)."""
    t = lang.say(config)
    if str(getattr(config.situation_block, "lore_preamble", "full") or "full") == "short":
        return t("things you have known for years, which this came near (not a list, not a subject to raise):",
                 "前から知っていること。話が近くを通っただけ（リストでも話題でもない）:")
    return t(
        "things you happen to know, because this came near them. NOT a list to get "
        "through and NOT a subject to raise: you have known all of it for years, so "
        "none of it is news to you and none of it is worth announcing. If it does not "
        "come out of you naturally in this reply, leave it alone and say nothing about it.",
        "話がたまたま近くを通ったので出てきた、あなたが前から知っていること。消化するリストでもなければ、"
        "持ち出す話題でもない。どれも何年も前から知っていることで、あなたにとっては新しくないし、"
        "わざわざ言うほどのことでもない。この返事で自然に出てこないなら、そのままにして何も言わない。")


def place(kept, lore, config):
    """`kept` with the preamble in front of the first retrieved line that
    survived the gate, or `kept` untouched when none did."""
    if not lore:
        return kept
    ids = {id(l) for l in lore}
    at = next((i for i, l in enumerate(kept) if id(l) in ids), None)
    if at is None:
        return kept
    return list(kept[:at]) + [preamble(config)] + list(kept[at:])
