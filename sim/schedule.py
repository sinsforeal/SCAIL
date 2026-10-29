import random
import logger
from sim import roster
from sim import sight
from world.clock import hm_to_minutes, minutes_to_hm

# What every character's day is made of: the wake, the contiguity rule, the
# block she is in now, the presence label. A day's SHAPE is a program's:
# `tomoe/schedule.py` plans a schoolgirl's timetable, `resident/schedule.py`
# a flat and a week of her own. Nothing here names a place or a person.

# what a block's `with` may say that is not a person on her roster. The
# ledger reads it too, and one definition is the point: a word that means
# "no one in particular" here has to mean it there.
NOT_PEOPLE = ("alone", "nobody", "the group", "classmates", "the class", "class",
              "strangers", "people", "crowd", "the crowd", "(home briefly)", "family")


def check_people(config, blocks, date_str=""):
    """Drop a name from a block's `with` that nobody on the roster owns.

    A name here is a claim that a person is in the room, and every mechanism
    downstream keys on the roster: `role_of` returns nothing for a stranger,
    so a bond, a sentiment, an `in_person` beat and an exchange all silently
    decline while the director goes on writing that person into the scene.
    A stale name is therefore not a cosmetic error, it is an empty chair the
    record cannot see. Flag it and take it out; the block keeps whoever is
    real, and falls back to `alone` when nobody is."""
    if not config:
        return blocks
    dropped = []
    for b in blocks or []:
        raw = str(b.get("with") or "").strip()
        if not raw:
            continue
        kept = []
        for n in [x.strip() for x in raw.replace("、", ",").replace(" and ", ",").split(",") if x.strip()]:
            low = n.lower()
            if roster.role_of(config, n) or any(k in low for k in NOT_PEOPLE):
                kept.append(n)
            else:
                dropped.append(f"{n!r} in {b.get('start', '??')}-{b.get('end', '??')}")
        if dropped and kept != [x.strip() for x in raw.replace("、", ",").replace(" and ", ",").split(",") if x.strip()]:
            b["with"] = ", ".join(kept) if kept else "alone"
    if dropped:
        logger.log(f"[schedule] FLAG{' ' + date_str if date_str else ''}: nobody on the roster is "
                   + "; ".join(dropped[:6]) + " -- dropped from the day")
    return blocks


def wake_time(config, store, date, is_school, health=None, state=None):
    """When she actually wakes. With the health sleep model on, the wake falls
    out of the night (bedtime + how long she slept + how rough it was); this
    only clamps it to the skeleton's structural window and rounds it. With
    health off it is a seeded jitter around the base hour, nudged later by low
    energy. Persisted (kv wake_days). Returns ("HH:MM", [reasons]) or (None, [])
    if disabled — then the skeleton's fixed hour stands."""
    wc = config.schedule.wake
    date_str = date.isoformat()
    if not wc.enabled:
        return None, []
    days = store.get("wake_days", {})
    if date_str in days:
        r = days[date_str]
        return r["hm"], r.get("why", [])
    lo, hi = (hm_to_minutes(wc.school_min), hm_to_minutes(wc.school_max)) if is_school \
        else (hm_to_minutes(wc.free_min), hm_to_minutes(wc.free_max))
    step = max(1, int(wc.round_to))
    why = []
    wake_m = None
    if health is not None and getattr(config.health, "enabled", False) and getattr(config.health.sleep, "enabled", False):
        try:
            n = health.night(date_str)
        except Exception:
            n = None
        if n and n.get("wake"):
            wake_m = hm_to_minutes(n["wake"])
            why = list(n.get("factors", []))
    if wake_m is None:
        # fallback: no sleep model — base hour plus seeded jitter and an energy nudge
        base_m = hm_to_minutes(wc.school_base if is_school else wc.free_base)
        rng = random.Random(f"{date_str}|wake|{wc.seed}")
        late = rng.gauss(0, wc.school_jitter_min if is_school else wc.free_jitter_min)
        if state is not None:
            e = float(state.gauges.get("energy", 60))
            if e < wc.energy_ref:
                late += (wc.energy_ref - e) * wc.energy_min_per_point * (0.4 if is_school else 1.0)
                if e < wc.energy_ref - 10:
                    why.append("run-down")
        wake_m = base_m + late
    # An alarm. The night decides when she would wake; a promise with a time on
    # it decides when she has to. She agreed to the library at 9 with Aya and
    # the wake had already been drawn at 10:10, so the plan the generator was
    # told to keep and the body it was planning for could not both be right,
    # and the outcome would have been a promise broken by arithmetic rather
    # than by her. The lead is getting up, out and there, and the hours she
    # actually slept are the sleep model's -- being short of them is the point.
    #
    # The sleep model sets the same alarm itself, and says so in three
    # different words depending on whether she beat it, snoozed it or neither;
    # matching only "alarm set" missed two of the three and stacked a second
    # lead on top of the first.
    lead = int(getattr(wc, "commitment_lead_minutes", 0) or 0)
    alarm_night = any("alarm" in str(f) for f in why)
    if lead and not alarm_night:
        due = [hm_to_minutes(r["from_hm"]) for r in (store.get("commitments", []) or [])
               if r.get("status") == "open" and r.get("date") == date_str and r.get("from_hm")]
        if due and (min(due) - lead) < wake_m:
            wake_m = min(due) - lead
            alarm_night = True
            why.append("she has to be somewhere")
    # `free_min` means "she does not get up before eight for nothing". A
    # promise with a time on it is not nothing. The floor was being applied to
    # a wake the sleep model had already drawn AROUND the alarm -- the short
    # night, the penalty and the energy target all follow from being up at
    # 07:20 -- and clamping it back to 08:00 threw that away and put her at the
    # library at 10:20 for a nine o'clock she had promised Aya. On an alarm
    # morning the only floor is the earliest this system ever has her up.
    floor = hm_to_minutes(wc.school_min) if alarm_night else lo
    wake_m = int(round(wake_m / step) * step)
    wake_m = max(floor, min(hi, wake_m))
    hm = f"{wake_m // 60:02d}:{wake_m % 60:02d}"
    days[date_str] = {"hm": hm, "why": why}
    keep = sorted(days.keys())[-45:]
    store.set("wake_days", {k: days[k] for k in keep})
    logger.log(f"[wake] {date_str}: {hm}" + (f" ({', '.join(why[:3])})" if why else ""))
    return hm, why


MIN_BLOCK_MINUTES = 20




def _apply_wake(blocks, wake_hm):
    """Move the end of the night's asleep block to wake_hm and let the morning
    absorb the difference. A later wake pushes the blocks after it forward
    until one is long enough to swallow the shift; a block the morning ran
    over entirely is dropped. Bounding the wake by the *next block's* end
    (the old rule) silently capped every free morning at 10:15, because that
    is where the skeleton's slow-wake block ends -- the drawn wake never got
    out. The day stays contiguous and every block keeps a real length, which
    is what validate() checks."""
    if not wake_hm:
        return blocks
    w = hm_to_minutes(wake_hm)
    for i, b in enumerate(blocks):
        if b.get("phone_access") != "none" or "asleep" not in (b.get("activity") or "").lower():
            continue
        if i + 1 >= len(blocks):
            return blocks
        day_end = hm_to_minutes(blocks[-1]["end"])
        w = max(hm_to_minutes(b["start"]) + 30, min(w, day_end - MIN_BLOCK_MINUTES))
        b["end"] = minutes_to_hm(w)
        out = blocks[: i + 1]
        cursor = w
        for nb in blocks[i + 1:]:
            # every block starts where the last one ended -- validate() demands
            # it. Waking earlier stretches the morning block back; waking later
            # pushes it along until a block is long enough to absorb the shift.
            # A block shorter than the minimum by design keeps its own length
            # instead: the ten minutes between two lessons are ten minutes, and
            # rounding them up to twenty walked the bells of the whole school
            # day forward by an hour.
            s = cursor
            own = hm_to_minutes(nb["end"]) - hm_to_minutes(nb["start"])
            if own <= 0:
                continue
            floor = min(MIN_BLOCK_MINUTES, own)
            e = min(max(hm_to_minutes(nb["end"]), s + floor), day_end)
            if e - s < floor:
                continue  # the morning ran over it entirely
            nb["start"], nb["end"] = minutes_to_hm(s), minutes_to_hm(e)
            out.append(nb)
            cursor = e
        out[-1]["end"] = minutes_to_hm(day_end)
        return out
    return blocks


def validate(blocks):
    if not isinstance(blocks, list) or not blocks:
        return False
    prev_end = 0
    # a model writes midnight as "00:00" as often as "24:00", and a day whose
    # last block ends at 00:00 is a whole replan thrown away (2026-09-03 02:27)
    if blocks and isinstance(blocks[-1], dict) and blocks[-1].get("end") == "00:00":
        blocks[-1]["end"] = "24:00"
    for b in blocks:
        try:
            s = hm_to_minutes(b["start"])
            e = hm_to_minutes(b["end"])
        except Exception:
            return False
        if s != prev_end or e <= s:
            return False
        if b.get("phone_access") not in ("free", "glance", "none"):
            b["phone_access"] = "glance"
        prev_end = e
    return prev_end == 24 * 60


def presence_label(config, block):
    """One phrase for the messenger: where she is, or how reachable she is.

    Her whereabouts come first and the phone rule is the fallback, so a lesson
    reads as a lesson rather than as silence. Both are the program's words
    (`sim/sight.py`): the whereabouts table is a schoolgirl's -- in class, on
    the train, at lunch, cleaning duty -- and the second character's is
    empty, because for her the whereabouts are not the answer to how
    reachable she is ("bath" matched "away" here while she was replying
    from it); her plan carries the only phone rule she has (`own_day`), so
    she gets that alone. The phone-rule fallback differs too: a dark phone is
    "away" for one and "asleep" for the other, and a word that says nothing
    is "away" rather than nothing, because a dark phone he cannot account
    for reads as the app being broken."""
    if not block:
        return ""
    text = f"{block.get('activity', '')} {block.get('location', '')}".lower()
    for key, label in sight.w(config, "presence_words"):
        if key in text:
            return label
    by_phone = sight.w(config, "presence_by_phone")
    return by_phone.get(block.get("phone_access", ""), by_phone.get("", ""))


def is_sleep_block(block, sleep_keywords):
    """Is this block her asleep? The phone is off and the words say so.

    `director.asleep_block` is the one caller, and it is the one answer to
    whether she is up: her phone being off through the night is what the
    posting gate reads as "asleep" too, without asking a second question."""
    if not block or block.get("phone_access") != "none":
        return False
    act = (block.get("activity") or "").lower()
    return any(k in act for k in sleep_keywords)


def block_at(blocks, dt):
    cur = dt.hour * 60 + dt.minute
    for b in blocks:
        if hm_to_minutes(b["start"]) <= cur < hm_to_minutes(b["end"]):
            return b
    return blocks[-1]


def describe(schedule):
    lines = [f"{b['start']}-{b['end']} {b['activity']} @ {b['location']} (with {b.get('with', '?')}, phone {b['phone_access']})" for b in schedule["blocks"]]
    return "\n".join(lines) + f"\nNOTES: {schedule.get('notes', '')}"
