import math
from sim.state import State

import logger

# Where the relationship meters come from.
#
# They used to be three numbers typed into cast.json -- closeness 62, standing
# 55, tension 15 -- which is a claim about how well they know each other rather
# than a consequence of anything. It also could not be right twice: the same
# file seeds a fresh install with no history and an install carrying the whole
# May 2026 chat.
#
# These derive them from the record instead. The May import is 144 messages
# over four days followed by a 99 day silence; that history should produce a
# particular closeness, and a database with nothing in it should produce a
# stranger. Everything here is read-only arithmetic over the store -- no model,
# no guessing -- and once derived the meters move normally from there.
#
# Three principles the numbers follow:
#   Days matter more than messages. Seventy texts in one evening is one day of
#   knowing someone; the same seventy over three weeks is a relationship.
#   Everything saturates. Twice the history is not twice the closeness.
#   Time is corrosive. Closeness earned in May has faded by August, and the
#   silence that did it leaves its own mark.


def _half_life_weight(age_days, half_life):
    return 0.5 ** (max(0.0, age_days) / max(1.0, half_life))


def quiet_days_for_standing(msgs, now_ts):
    last = max((m["ts"] for m in msgs if m.get("role") == "user"), default=now_ts)
    return max(0.0, (now_ts - last) / 86400.0)


def derive_him(config, store, now_ts):
    """(closeness, standing, tension, why) from the message record alone."""
    c = config.derive
    rows = store.all_messages() if hasattr(store, "all_messages") else None
    if rows is None:
        rows = []
    msgs = [r for r in rows if r.get("ts")]
    if not msgs:
        return c.cold_closeness, c.cold_standing, c.cold_tension, ["no history: they are strangers"]

    day_of = {}
    hers = his = 0
    for m in msgs:
        d = m.get("date") or ""
        day_of.setdefault(d, {"hers": 0, "his": 0, "ts": m["ts"], "first": m.get("role")})
        day_of[d]["ts"] = max(day_of[d]["ts"], m["ts"])
        if m.get("role") == "assistant":
            day_of[d]["hers"] += 1
            hers += 1
        else:
            day_of[d]["his"] += 1
            his += 1

    # --- closeness: contact days, each faded by how long ago it was, and each
    # worth more when both of them actually spoke
    weighted = 0.0
    for d, v in day_of.items():
        age = (now_ts - v["ts"]) / 86400.0
        both = min(v["hers"], v["his"])
        depth = min(1.0, math.log1p(both) / math.log1p(c.day_depth_ref))
        weighted += _half_life_weight(age, c.closeness_half_life_days) * (c.day_floor + (1 - c.day_floor) * depth)
    closeness = c.closeness_ceiling * (1.0 - math.exp(-weighted / max(0.1, c.closeness_days_ref)))

    # what she has learned about him is closeness that does not fade with a gap
    facts = 0
    try:
        facts = len(store.user_facts() or [])
    except Exception:
        pass
    known = min(c.facts_max, c.facts_ceiling * (1.0 - math.exp(-facts / max(1.0, c.facts_ref))))
    # knowing him is closeness a gap cannot take back, but not entirely: after
    # long enough it is knowing who he used to be. Without this, thirty days of
    # total silence still left closeness at 35.
    quiet = (now_ts - max((m["ts"] for m in msgs if m.get("role") == "user"), default=now_ts)) / 86400.0
    closeness += known * (c.known_floor + (1 - c.known_floor) * _half_life_weight(quiet, c.known_half_life_days))

    # --- standing: how sure she is of her place. The message ratio alone
    # barely moves -- it sat at 50 in every simulated scenario -- so it is only
    # one of three terms. The other two are the ones a person actually feels:
    # whether he ever starts it, and how long he leaves her waiting.
    # Every term is weighted by how recent the day was. Averaged flat over the
    # whole record it converged to the same number in every simulated future --
    # he could talk daily or stop entirely and standing landed on 63 either
    # way, which is the definition of a value that is never used. How sure she
    # is of her place is about how he has been lately, not about the mean of
    # everything that ever happened.
    w_his = w_hers = 0.0
    w_starts_his = w_starts_hers = 0.0
    for v in day_of.values():
        wt = _half_life_weight((now_ts - v["ts"]) / 86400.0, c.standing_half_life_days)
        w_his += v["his"] * wt
        w_hers += v["hers"] * wt
        if v.get("first") == "user":
            w_starts_his += wt
        elif v.get("first") == "assistant":
            w_starts_hers += wt
    share = w_his / max(1e-6, w_his + w_hers)
    standing = c.cold_standing + (share - 0.5) * c.standing_span
    if w_starts_his + w_starts_hers > 0:
        standing += (w_starts_his / (w_starts_his + w_starts_hers) - 0.5) * c.standing_starts_span

    # and if he has simply gone, her footing goes with him
    if quiet_days_for_standing(msgs, now_ts) >= c.standing_absent_from_days:
        gone = quiet_days_for_standing(msgs, now_ts) - c.standing_absent_from_days
        standing -= min(c.standing_absent_max, gone * c.standing_absent_per_day)

    # how long he leaves her hanging, averaged over her messages that he
    # eventually answered
    waits = []
    ordered = sorted(msgs, key=lambda m: m["ts"])
    pending = None
    for m in ordered:
        if m.get("role") == "assistant":
            if pending is None:
                pending = m["ts"]
        elif pending is not None:
            waits.append((m["ts"] - pending) / 3600.0)
            pending = None
    if waits:
        typical = sorted(waits)[len(waits) // 2]
        standing -= min(c.standing_wait_max, typical * c.standing_per_wait_hour)

    # --- tension: the gap since he last spoke, and the worst silence they have
    # had. A long one leaves a mark even after he comes back.
    last_his = max((m["ts"] for m in msgs if m.get("role") == "user"), default=msgs[0]["ts"])
    quiet_days = (now_ts - last_his) / 86400.0
    tension = c.cold_tension + min(c.tension_gap_max, quiet_days * c.tension_per_quiet_day)
    days_sorted = sorted(day_of.values(), key=lambda v: v["ts"])
    worst = 0.0
    for a, b in zip(days_sorted, days_sorted[1:]):
        worst = max(worst, (b["ts"] - a["ts"]) / 86400.0)
    if worst >= c.scar_from_days:
        # A long silence leaves a mark that heals while he is AROUND. Keying it
        # on time-since-he-last-spoke made it fade during the silence itself,
        # so thirty days of being ignored showed tension falling.
        end_of_gap = 0.0
        for a, b in zip(days_sorted, days_sorted[1:]):
            if (b["ts"] - a["ts"]) / 86400.0 >= c.scar_from_days:
                end_of_gap = max(end_of_gap, b["ts"])
        contact_since = sum(1 for v in day_of.values() if v["ts"] > end_of_gap)
        tension += c.scar_tension * _half_life_weight(contact_since, c.scar_half_life_days)

    why = [f"{len(day_of)} day(s) of contact, {hers} from her and {his} from him",
           f"{facts} thing(s) she has learned about him"]
    if worst >= c.scar_from_days:
        why.append(f"a {worst:.0f} day silence between them")
    if quiet_days >= 1:
        why.append(f"he last spoke {quiet_days:.1f} days ago")

    clamp = lambda v: max(0.0, min(100.0, v))
    return round(clamp(closeness)), round(clamp(standing)), round(clamp(tension)), why


def apply_if_new(config, store, clock, relationships):
    """Set his meters from the record, once, unless they were derived already
    or someone has set them by hand. Returns True if it wrote."""
    if not config.derive.enabled:
        return False
    if store.get("relationship_derived"):
        return False
    key = State.him_key_in(config, relationships)
    if not key:
        return False
    cl, st, te, why = derive_him(config, store, clock.now_ts())
    relationships[key].update({"closeness": cl, "standing": st, "tension": te})
    store.set("relationships", relationships)
    store.set("relationship_derived", {"at": clock.now_ts(), "closeness": cl, "standing": st, "tension": te, "why": why})
    logger.log(f"[derive] his meters from the record: closeness {cl}, standing {st}, tension {te}"
               f" ({'; '.join(why)})")
    return True
