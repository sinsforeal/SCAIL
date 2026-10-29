"""The second character's program: everything the runtime runs for her and for
nobody else.

She is resident on his machine. She has a flat and a week of her own, planned
from her home file; she has no world for them to be in, no cast, no account
and no phone, so none of that is built here -- it does not exist in her
process. What is hers is her sight: a note he opens she has read, and she
sleeps when he does.

The same hooks as `tomoe/app.py`, and the runtime asks `hasattr` before it
calls one; what is not here is not hers.
"""
import logger
from sim import seed_memories
from sim.wiring import wire
from resident import schedule as rsched
from resident import words  # noqa: F401 -- how she sees him: his machine in front of her


NAME = "resident"


def build(app):
    c = app.config
    # A character read out of a real archive arrives with a timeline of her own
    # past, and until it is in her memory store nothing can reach it: not a
    # word of his, not the cosine, not the deliberate search. Once, at boot,
    # insert-only, no model call, and immediately silent for a character whose
    # config names no such file (`sim/seed_memories.py`). It is here rather
    # than in the runtime because a boot-time migration belongs to the program
    # that runs her; the library holds the work, so a world-program character
    # who is given a timeline needs this one line in her program too.
    try:
        seed_memories.seed_if_needed(app)
    except Exception as e:
        logger.log(f"[memory] her own past was not seeded: {type(e).__name__}: {e}")
    app.sight = None
    if getattr(c.resident_sight, "enabled", False):
        from resident.sight import ResidentSight
        app.sight = ResidentSight(c, app.store, app.clock, app.notes, app.sys_monitor, learned=app.assess_learned)
        # the director asks her sight before it asks the plan
        wire(app.director, sleep_source=app.sight)
        # one concrete thing off his screen, for the persona to offer her
        wire(app.persona, sight=app.sight)
        # a page of hers open in front of him: her record and a search answer
        # whether it is hers, and it is a reason to reach out first
        wire(app.sight, lore=app.lore, lookup=app.lookup, anime_kb=app.anime_kb)
        # and what he is doing, classified off the raw window trail
        # (`typesafe.py`, `docs/system-one.md` item 4)
        wire(app.sight, typesafe=app.typesafe)
        wire(app.impulse, sight=app.sight)
        # and the same observation reaches the moment she decides at: at the
        # phone she is told he is at the machine and not on her, so reaching out
        # when he is not looking is hers to choose (`sim/pick.py:_him_lines`)
        wire(app.pick, sight=app.sight)
    app.eroge = None
    if getattr(c.eroge, "enabled", False):
        from sim.eroge import Eroge
        app.eroge = Eroge(c, app.store, app.clock)
        wire(app.eroge, llm=app.llm, retrievals=app.retrievals)
        # her situation reads it where it reads everything else off his
        # screen: it is one more thing in front of him this minute
        if app.sight is not None:
            wire(app.sight, eroge=app.eroge)
    # Her own record also answers when he TYPES the name of a work instead of
    # opening its page: one resolution, whatever named it (`sim/works.py`), so
    # a part she played is never bought from the web. Not her sight's -- this
    # holds whether or not she can see his screen.
    if app.lookup is not None and app.lore is not None:
        wire(app.lookup, lore=app.lore)


def plan_day(app, d):
    """A character with no world may still have a home. Her own place, her
    own week, and nothing of the present: planned from her home file alone,
    with the one-block day as the fallback if she has no such file or the
    plan does not hold together."""
    own = None
    try:
        his = app.phone.day_shape_line() if app.phone else ""
        for h in (app.store.get("habits_him", []) or [])[:6]:
            hrs = h.get("hours") or []
            if len(hrs) == 2:
                his += f"\n- {h.get('what', '')}, roughly {hrs[0]:02d}:00-{hrs[1]:02d}:00"
        own = rsched.own_day(app.config, app.llm, app.clock, app.clock.now().date(), his_hours=his)
    except Exception as e:
        logger.log(f"[schedule] her own day failed: {type(e).__name__}: {e}")
    if own:
        blocks, note = own
    else:
        blocks = rsched.resident_day()
        note = "no world of her own: she is resident on his machine"
    app.store.save_schedule(d, app.clock.now_ts(), blocks, note)
    return {"date": d, "blocks": blocks, "notes": note}


def day_line(app):
    return "no world of her own"


def every_pass(app):
    """Her sight, every pass: a note in front of him, whether he is up, and
    how long he has been gone."""
    if app.sight:
        try:
            app.sight.poll(app.director.current)
        except Exception as e:
            logger.log(f"[resident] sight: {type(e).__name__}: {e}")
        # His coming back is hers to notice, because she is in the machine he
        # comes back to. The library holds the rule and rolls for it; her sight
        # is the only thing that can say he has been away six hours and is here
        # now (sim/initiative.py). A character who cannot see him this way is
        # never told, and then there is no return rule for her at all.
        try:
            app.impulse.initiative.observe_away(app.sight.away_seconds(), app.state)
        except Exception as e:
            logger.log(f"[resident] his return not weighed: {type(e).__name__}: {e}")
    # An episode he played she watched him play: the module reads it up in the
    # background and it is hers as it lands, dated to his play rather than to
    # this pass, so nothing about her freshness or settle window moves. A
    # character who has to go and fetch what he has been doing has a moment
    # instead, and it is her own (`tomoe/app.py:after_phone_look`).
    if app.watching:
        app.watching.note_seen(at_play=True)


def after_self_start(app, bubbles):
    """She reached out; a page of hers in front of him was said once."""
    if app.sight:
        app.sight.note_spoken()


def before_reply(app, reason=""):
    """A reply of hers is about to be written -- because he wrote to her, or
    because she decided to. If he is in a visual novel, this is the moment the
    account of what he is reading is worth paying for, and the only one: not a
    timer, and never while nobody is about to say anything."""
    if app.eroge is None:
        return
    try:
        app.eroge.look(reason)
    except Exception as e:
        logger.log(f"[eroge] the look failed: {type(e).__name__}: {e}")


def on_his_message(app, text):
    # he wrote to her: he is awake, whatever his machine says
    if app.sight and app.sight.wake("he wrote to her"):
        app.coasting_block = None
        app.woke = True
