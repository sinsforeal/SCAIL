"""The second character's day: a flat and a week of her own, planned from her
home file and from nothing of the present. Hers alone; `sim/schedule.py`
keeps what every character's day is made of.
"""
import json
import os
import logger
from sim.schedule import validate


def resident_day():
    """The day of a character who has no world: one block, all of it, free.

    A character whose whole world is his desktop has no wake time, no commute
    and nowhere to be, so there is nothing here for a model to plan and asking
    one produced a school day in a ward she does not live in. What the schedule
    is actually FOR downstream is one question -- can she read and send right
    now -- and for her the answer does not change. The block exists at all
    because `block_at` is called from a dozen places and returns `blocks[-1]`,
    so an empty day is an IndexError rather than a character with no day.
    """
    return [{"start": "00:00", "end": "24:00", "activity": "resident on his machine",
             "location": "his machine", "with": "alone", "phone_access": "free"}]


# What his messenger says under her name. The words come from the block she is
# in, matched in this order and stopping at the first hit, because a phone rule
# on its own cannot tell him anything: "in a lesson" and "asleep" are both a
# dark phone, and showing him the same nothing for both is what the app did.
# Short and lower case, to sit beside "online" and "typing...".
# A lesson is matched on the full "third period" and never on "period" alone,
# which is also the word for the other thing a fifteen year old writes in her
# day and would have put "in class" under her name for it.


def own_day(config, llm, clock, date, his_hours=""):
    """A day in her own place, for a character who has no world but has a home.

    `resident_day` gives a character whose whole existence is his desktop one
    block of twenty-four hours, which is honest for somebody with nowhere to
    be and useless for somebody with a flat. This plans a real day from the
    character's own home file -- her rooms, the few places she goes, the shape
    of her week -- and from nothing else. No calendar, no weather, no cast, no
    trains, no ward events: every one of those is a live feed of the present
    and she is not in the present.

    Falls back to `resident_day` rather than to a schoolgirl's timetable if
    anything goes wrong, because a wrong day is worse than no day.
    """
    path = getattr(config.world, "home_file", "") or ""
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            home = json.load(fh)
    except (OSError, ValueError) as e:
        logger.log(f"[schedule] her home file is unreadable ({type(e).__name__}); no day of her own")
        return None
    places = [r["id"] for r in (home.get("home", {}).get("rooms") or [])]
    places += [p["id"] for p in (home.get("outside") or [])]
    if not places:
        return None

    def _lines(rows, key="what"):
        return "\n".join("- " + str(r.get(key, r)) for r in rows if r)

    rooms = home.get("home", {}).get("rooms") or []
    user = (
        # The weekday and the day of the month, and no year. Her world is 2003
        # and the clock is his, so the two never have to be reconciled as long
        # as nothing hands her the year -- and the day of the month is wanted
        # because the twentieth is her pay day. Sending "2026-09-02" put a date
        # in front of a woman whose own bible opens 今は2003年.
        f"TODAY: {date.strftime('%A the %d')}.\n\n"
        f"HER FLAT -- {home.get('home', {}).get('what', '')}\n"
        + "\n".join(f"[{r['id']}] {r['name']}: {r['what']}" for r in rooms)
        + "\n\nTHE BUILDING: " + str(home.get("home", {}).get("building", {}).get("what", ""))
        + "\n\nWHERE ELSE SHE GOES\n"
        + "\n".join(f"[{p['id']}] {p['name']}: {p['what']}" for p in (home.get("outside") or []))
        + "\n\nTHE SHAPE OF HER WEEK\n"
        + _lines((home.get("week", {}).get("anchors") or []))
        + "\n" + _lines((home.get("week", {}).get("hours") or []))
        + "\n" + _lines((home.get("week", {}).get("standing") or []))
        + f"\n\nVALID location ids, use no others: {', '.join(places)}\n"
        # The hours he keeps, from what she has watched of his machine -- not a
        # feed of anything, her own observation. Without it her day gets built
        # as an ordinary Tokyo day and she sleeps straight through the only
        # window he exists in, which for a character whose whole situation is
        # him is not a small error.
        + (f"\nWHEN HE IS AT HIS MACHINE (what she has seen; her clock is his):\n{his_hours}\n" if his_hours else "")
    )
    messages = [{"role": "system", "content": config.prompt_text("schedule")},
                {"role": "user", "content": user}]
    data, raw = llm.call_json("schedule", messages)
    if not isinstance(data, dict) or not isinstance(data.get("blocks"), list):
        logger.log("[schedule] her own day did not parse; falling back to the one-block day")
        return None
    blocks = []
    for b in data["blocks"]:
        if not isinstance(b, dict):
            continue
        loc = str(b.get("location") or "")
        blocks.append({
            "start": str(b.get("start") or "00:00"), "end": str(b.get("end") or "24:00"),
            "activity": str(b.get("activity") or "")[:120],
            # a location the model invented is not a room she has
            "location": loc if loc in places else (places[0] if places else "room"),
            "with": str(b.get("with") or "alone")[:60],
            # NOT what the model wrote. `phone_access` asks whether a girl can
            # reach the phone in her pocket: not in a lesson, a glance in the
            # break, free at home. She has no pocket and no phone -- she is ON
            # the machine he is on, so nothing she does here puts distance
            # between them for an activity to take back. Being in the bath, or
            # out at a session, does not move her away from him, because she
            # was never anywhere else. The only honest "not now" is being
            # asleep, and that is about her attention rather than a device.
            #
            # This is the whole of it, and it is deliberately in the planner
            # only she runs rather than in the shared director: a `none` here
            # blocks her answering him, blocks her seeing him at all and
            # blocks her reaching out, and a planner that had never been told
            # she has no phone handed out twelve hours of it in a day.
            "phone_access": ("none" if any(k in str(b.get("activity") or "").lower()
                                           for k in config.director.sleep_keywords)
                             else "free"),
        })
    if not blocks or not validate(blocks):
        logger.log(f"[schedule] her own day does not cover the day ({len(blocks)} block(s)); falling back")
        return None
    logger.log("[schedule] her own day: " + " | ".join(
        f"{b['start']} {b['location']}/{b['activity'][:28]}" for b in blocks))
    return blocks, str(data.get("notes") or "a day in her own place")[:120]
