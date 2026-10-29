"""Where her body is, continuously, and what it costs her.

His brief (2026-08-26): body state already reaches the gauges and some
behaviour; extend it into a continuous low-level simulation -- location
physics, fatigue accumulation, environmental affordances -- so that "I am
tired and the room is hot and I still have to answer" is a persistent
constraint on every action rather than a tag. Her commute and her trips
should be modelled and events should happen to her from reality. Then
(same day): walking speed from fatigue, weather, clothing and what she is
carrying; sweat in summer; running when she is late, which costs more and
bumps into people; rare positive and negative things on the way, or
nothing; texting while walking is possible and not free of risk; the
bike; her parents' car for a pickup or a family trip.

Four objects, no LLM:

**The place graph** (`data/places.json`): nodes she can be at and edges
with a mode and minutes (walk, bike, train on a named line, a car). The
free-text location the schedule or the director writes resolves to a node
by keyword; a location that matches nothing leaves her where she was.

**The journey.** When the block she is in wants her somewhere else, a
journey starts from where she actually is: legs from the graph (BFS on the
edges), each with its own minutes, mode and line. It runs on the clock,
not on the director: the director is TOLD where she is on the way and how
long is left, and may not put her at school before she has arrived.
Reality lands on the legs: the train status feed on a train leg of hers
(delayed adds minutes, suspended stops her with an event), the weather on
a walk leg (rain she is in, heat she is walking in), the rush windows
(the Seibu is packed), what she is wearing and carrying (the school bag,
a yukata and geta, shopping), and whether she is late (she runs: faster,
costlier, sweatier, likelier to bump into somebody). A finished journey
is written to kv `journeys` with what happened on it.

**Things that happen on the way.** Each leg rolls once, seeded by the
journey so a restart does not re-roll, against a small table scaled by
the conditions: a seat on a packed train, a dropped hairpin found, a cat
on a wall, missing the express, a bump on the stairs, someone standing
too close, a cracked screen. Most legs: nothing. Texting while walking is
allowed and multiplies the bump chance while she is doing it.

**Fatigue.** A code-owned body gauge (`fatigue`, rest 5, no decay of its
own) that accumulates by what she is doing -- walking in heat, standing on
a packed train, a day out, running -- and recovers only when she is
resting (lying down, the bath, sleep). Energy is what sleep gives; fatigue
is what the day takes. Readers: her read delay and composing (`State.
delay_factor` via `delay_multiplier`), the impulse (a weight), the shape
of her replies (`shape_bias`), her register, the tags, the director (HER
BODY NOW), and her situation block. `/where` prints all of it.
"""
import json
import os
from world.clock import hm_to_minutes
from sim import wiring
import random
import re
import datetime
import logger


FAMILY_WORDS = ("mom", "mother", "dad", "father", "family", "parents", "okaasan", "otousan")


def _family_words(config):
    """The words a block's `with` may use for her family: the generic ones
    and the names of everyone on her roster whose role is a relative."""
    words = list(FAMILY_WORDS)
    try:
        from sim import roster
        for k in roster.everyone(config):
            rec = roster.rec_of(config, k) or {}
            if str(rec.get("role_id", "")).lower() in ("mother", "father", "sibling", "grandmother", "grandfather"):
                for n in [k, rec.get("ja", ""), rec.get("reading", "")] + list(rec.get("aliases") or []):
                    n = str(n or "").strip().lower()
                    if n:
                        words.append(n)
    except Exception:
        pass
    return tuple(words)


_STOPS_CACHE = {}


def _stops_out(config):
    """The stations on her way in, after her own, from her own map.

    Empty for a character whose map has no commute in it, and then nothing in
    the table of what happens on a train names a place. Three sentences here
    used to name two stations on the FIRST character's line, so every embodied
    character in any city got them as her own lived experience -- a girl who
    lives on his machine included, and no guard could see it, because the name
    check did not look for places."""
    path = str(getattr(getattr(config, "world", None), "geography_file", "") or "")
    if not path or not os.path.exists(path):
        return ()
    try:
        key = (path, os.path.getmtime(path))
    except OSError:
        return ()
    hit = _STOPS_CACHE.get(key)
    if hit is None:
        try:
            with open(path, encoding="utf-8") as fh:
                geo = json.load(fh)
        except (OSError, ValueError):
            geo = {}
        hit = tuple(str(s).strip() for s in ((geo.get("commute") or {}).get("stops_inbound") or [])
                    if str(s).strip())[1:]
        _STOPS_CACHE[key] = hit
    return hit


class Situation:
    WIRES = ('family', 'trains',)
    def __init__(self, config, store, clock, weather=None, trains=None, body=None, state=None, calendar=None):
        self.config = config
        self.store = store
        self.clock = clock
        self.weather = weather
        self.trains = trains
        self.body = body
        self.state = state
        self.calendar = calendar
        # A character with no world has no place graph and no path to one:
        # `Config.WORLD_KEYS` blanks it, and this constructor runs whatever
        # `situation.enabled` says, so without this it opens "" and the bot
        # dies at boot. An empty graph is the honest map of nowhere.
        if config.world.places_file:
            with open(config.world.places_file, "r", encoding="utf-8") as fh:
                self.map = json.load(fh)
        else:
            self.map = {"nodes": {}, "edges": []}
        self.nodes = self.map.get("nodes", {})
        self.edges = self.map.get("edges", [])
        self.rec = store.get("situation", {}) or {}
        self.rec.setdefault("node", "home")
        self.rec.setdefault("journey", None)
        self.rec.setdefault("last_ts", clock.now_ts())
        self.rec.setdefault("arrived_ts", clock.now_ts())
        self.rec.setdefault("activity", "")
        wiring.declare(self)

    def _save(self):
        self.store.set("situation", self.rec)

    # ---------------- the map ----------------

    def resolve(self, location, activity=""):
        """A node id for a free-text place, or None (unknown / in transit)."""
        text = f"{location or ''} {activity or ''}".lower()
        if not text.strip():
            return None
        e = self.config.environment
        if any(k in (location or "").lower() for k in e.transit_keywords):
            return None
        best, blen = None, 0
        for nid, n in self.nodes.items():
            for k in n.get("keywords", []):
                if k.lower() in text and len(k) > blen:
                    best, blen = nid, len(k)
        return best

    def _neighbours(self, nid):
        for e in self.edges:
            if e["a"] == nid:
                yield e["b"], e
            elif e["b"] == nid:
                yield e["a"], e

    def route(self, a, b):
        """Legs from a to b: BFS by hops. A place the map cannot reach gets
        the unknown-trip leg."""
        if a == b:
            return []
        prev = {a: None}
        frontier = [a]
        while frontier and b not in prev:
            nxt = []
            for n in frontier:
                for m, e in self._neighbours(n):
                    if m not in prev:
                        prev[m] = (n, e)
                        nxt.append(m)
            frontier = nxt
        if b not in prev:
            u = self.map.get("unknown_trip", {"mode": "train", "min": 30})
            return [{"from": a, "to": b, "mode": u.get("mode", "train"), "min": u.get("min", 30), "line": u.get("line", "")}]
        legs = []
        cur = b
        while prev[cur]:
            n, e = prev[cur]
            legs.append({"from": n, "to": cur, "mode": e["mode"], "min": e["min"], "line": e.get("line", ""),
                         "rush": e.get("rush"), "change": bool(e.get("change"))})
            cur = n
        return list(reversed(legs))

    def name(self, nid):
        return (self.nodes.get(nid) or {}).get("name", nid or "?")

    # ---------------- how she would get there (facts, so nothing is invented) ----------------

    def travel_line(self):
        """The ways she can move, read off the map's own modes. She told him
        she would do her homework "on the bus"; there is no bus in the graph
        and never was. A model with no fact fills the gap itself, so the fact
        goes in the prompt."""
        modes = {e.get("mode") for e in self.edges if e.get("mode")}
        words = {"walk": "on foot", "train": "the trains on your lines",
                 "bike": "your bike", "car": "dad's car when he is the one driving"}
        have = [words[m] for m in ("walk", "train", "bike", "car") if m in modes]
        if not have:
            return ""
        line = "how you get anywhere: " + ", ".join(have[:-1]) + (" or " + have[-1] if len(have) > 1 else "")
        if "bus" not in modes:
            line += ". you do not take buses -- there is no bus in your life"
        return line

    def trip_lines(self, texts, limit=2, min_minutes=0):
        """Route lines for the places her day names. Each text is split into
        clauses first: a promises line lists three of them, and resolving the
        whole blob at once picks the longest keyword in it, which is how "the
        Pixar event tomorrow" lost to a FamilyMart mentioned in the next
        clause. One line per place, in the order they are named."""
        here = self.rec.get("node")
        out, seen = [], set()
        for text in texts:
            for clause in re.split(r"[;.\n]|(?<=\w), (?=you |she |and )", str(text or "")):
                if len(out) >= limit:
                    return out
                node = self.resolve(clause, clause)
                if not node or node == here or node in seen:
                    continue
                seen.add(node)
                line = self.trip_line(node, min_minutes=min_minutes)
                if line:
                    out.append(line)
        return out

    def minutes_to(self, node):
        """How long getting there actually takes from where she is, in
        minutes, or None when it cannot be worked out. The honest figure --
        what she BELIEVES about it is somebody else's business
        (`Commitments.running_late`)."""
        here = self.rec.get("node")
        if not node or not here:
            return None
        if node == here:
            return 0.0
        legs = self.route(here, node)
        if not legs:
            return None
        return sum(float(l.get("min") or 0) for l in legs)

    def trip_line(self, node, label="", min_minutes=0):
        """The real legs from where she is to a node. What a plan costs her in
        minutes and which line she is actually on is a fact she has; she should
        not have to guess it in front of him."""
        here = self.rec.get("node")
        if not node or not here or node == here:
            return ""
        legs = self.route(here, node)
        if not legs:
            return ""
        bits, total, change = [], 0, False
        for l in legs:
            total += float(l.get("min") or 0)
            change = change or bool(l.get("change"))
            m = l.get("mode")
            if m == "walk":
                bits.append(f"{round(l['min'])} min walk to {self.name(l['to'])}")
            elif m == "train":
                bits.append(f"{l.get('line') or 'the train'} {round(l['min'])} min to {self.name(l['to'])}")
            elif m == "bike":
                bits.append(f"{round(l['min'])} min on the bike to {self.name(l['to'])}")
            elif m == "car":
                bits.append(f"{round(l['min'])} min in the car to {self.name(l['to'])}")
            else:
                bits.append(f"{round(l['min'])} min to {self.name(l['to'])}")
        if total < min_minutes:
            return ""      # a four-minute walk to the konbini is not news
        head = f"getting to {label or self.name(node)}"
        return (f"{head}: " + " then ".join(bits)
                + f" -- about {round(total)} min" + (", one change" if change else "") + ", door to door")

    # ---------------- reality on a leg ----------------

    def _rush(self, leg, ts):
        r = leg.get("rush")
        if not r:
            return ""
        hm = self.clock.to_char(ts).strftime("%H:%M") if hasattr(self.clock, "to_char") else datetime.datetime.fromtimestamp(ts).strftime("%H:%M")
        m = hm_to_minutes(hm)
        inbound = leg.get("from") == "nerima_station"
        win = r.get("inbound" if inbound else "outbound")
        if win and hm_to_minutes(win[0]) <= m <= hm_to_minutes(win[1]):
            return "packed"
        return ""

    def _line_status(self, line):
        """(word, minutes_extra, stopped) for a train line from the feed."""
        if not line or not self.trains:
            return "", 0, False
        try:
            st = (self.trains._now or self.store.get("train_status", {}) or {})
        except Exception:
            st = {}
        for name, status in st.items():
            if line in name or name in line:
                if not status or status == "平常運転" or "平常" in status:
                    return "", 0, False
                c = self.config.situation
                if any(w in status for w in ("見合わせ", "運休")):
                    return status, c.stopped_minutes, True
                return status, c.delayed_minutes, False
        return "", 0, False

    def _weather(self):
        try:
            return self.weather.current(self.clock.now()) if self.weather else {}
        except Exception:
            return {}

    def _outfit(self, blk, scene):
        """What she is wearing and carrying, from the day and the block: a
        walk factor (>1 slower), a load factor on fatigue, and a sweat factor.
        Nothing here asks a model; the words in the schedule are enough."""
        c = self.config.situation
        text = " ".join(str((blk or {}).get(k, "")) + " " + str((scene or {}).get(k, "")) for k in ("activity", "location")).lower()
        wear, carry = "casual", "nothing much"
        walk, load, sweat = 1.0, 1.0, 1.0
        school = False
        try:
            school = bool(self.calendar and self.calendar.is_school_day(self.clock.now().date()))
        except Exception:
            school = False
        # A uniform is a fact about somebody who is in a school. The calendar
        # already answers no for a character with no world; the words in her
        # activity line must not answer yes on their own.
        in_world = bool(self.config.conditions().get("in_world", True))
        if any(k in text for k in c.yukata_keywords):
            wear, walk, sweat = "yukata and geta", c.yukata_walk, c.yukata_sweat
        elif school or (in_world and any(k in text for k in ("uniform", "school", "class"))):
            wear, sweat = "the uniform (blouse, skirt, the blazer over her arm in summer)", c.uniform_sweat
        if school or (in_world and "school" in text):
            carry, load = "the school bag", c.school_bag_load
        if any(k in text for k in c.shopping_keywords):
            carry, load = "shopping bags", c.shopping_load
        if any(k in text for k in ("bento", "lunch box")):
            carry, load = carry + " and a bento", load * 1.03
        return {"wear": wear, "carry": carry, "walk": walk, "load": load, "sweat": sweat}

    def _hurry(self, blk, nxt, eta_ts):
        """Is she late? The next block's start against the plain eta."""
        if not nxt:
            return False, 0
        try:
            hm = self.clock.hm(eta_ts)
            late = hm_to_minutes(hm) - hm_to_minutes(nxt["start"])
        except Exception:
            return False, 0
        return late > self.config.situation.hurry_tolerance_minutes, late

    def _speed(self, leg, w, outfit, hurry):
        """Minutes for a walk or bike leg as she actually moves them."""
        c = self.config.situation
        f = 1.0
        fat = float(self.state.gauges.get("fatigue", 0)) if self.state else 0.0
        if fat >= c.wiped_from:
            f *= c.walk_wiped
        elif fat >= c.tired_from:
            f *= c.walk_tired
        feels = w.get("feels")
        if feels is not None and feels > c.heat_free_feels:
            f *= 1.0 + (feels - c.heat_free_feels) * c.walk_heat_per_degree
        if (w.get("precip_mm") or 0) >= self.config.needs.rain_mm_from:
            f *= c.walk_rain
        f *= outfit["walk"]
        f *= 1.0 + (outfit["load"] - 1.0) * 0.5
        if leg["mode"] == "bike":
            f = (f - 1.0) * 0.5 + 1.0
        if hurry and leg["mode"] == "walk":
            f *= c.run_time_factor
        return float(leg["min"]) * f

    # ---------------- the journey ----------------

    def start(self, to, why="", blk=None, nxt=None, scene=None, vehicle=""):
        """A journey from where she is to `to`, now. `vehicle` may force
        "car" (a pickup, a family trip) or "bike"."""
        frm = self.rec.get("node") or "home"
        if frm == to:
            return None
        c = self.config.situation
        now = self.clock.now_ts()
        w = self._weather()
        outfit = self._outfit(blk, scene)
        with_who = str((scene or {}).get("with_who") or (scene or {}).get("with") or (blk or {}).get("with") or "").lower()
        act = ((blk or {}).get("activity", "") + " " + (scene or {}).get("activity", "")).lower()
        family = any(k in with_who for k in _family_words(self.config))
        if not vehicle:
            if family and any(k in act for k in c.car_keywords):
                vehicle = "car"
            elif any(k in act for k in ("bike", "bicycle", "cycling", "mamachari")):
                vehicle = "bike"
        legs = self.route(frm, to)
        if vehicle == "car":
            # dad's car: door to door, at a car's pace over the same distance
            mins = max(c.car_min_minutes, sum(l["min"] for l in legs) * c.car_factor)
            legs = [{"from": frm, "to": to, "mode": "car", "min": round(mins), "line": ""}]
        elif vehicle == "bike":
            legs = [dict(l, mode="bike", min=max(2, round(l["min"] * c.bike_factor))) if l["mode"] == "walk" else l for l in legs]
        # first pass: the plain eta, to know whether she is late
        plain = now + 60 * sum(float(l["min"]) + (c.change_minutes if l.get("change") else 0) for l in legs)
        hurry, late = self._hurry(blk, nxt, plain)
        t = now
        effects = []
        for i, leg in enumerate(legs):
            leg["start_ts"] = t
            mins = float(leg["min"])
            if leg["mode"] == "train":
                word, extra, stopped = self._line_status(leg.get("line", ""))
                if word:
                    leg["status"] = word
                    mins += extra
                    effects.append(f"{leg.get('line')}: {word} (+{extra} min)")
                if leg.get("change"):
                    mins += c.change_minutes
                leg["crowd"] = self._rush(leg, t)
                if leg["crowd"]:
                    mins += c.packed_minutes
            elif leg["mode"] in ("walk", "bike"):
                feels = w.get("feels")
                rain = (w.get("precip_mm") or 0) >= self.config.needs.rain_mm_from
                if rain:
                    leg["rain"] = True
                    # an umbrella most of the time; forgotten now and then
                    leg["umbrella"] = random.Random(f"{now}|umb").random() > c.forget_umbrella_p
                    effects.append("rain on the walk" + ("" if leg["umbrella"] else ", no umbrella"))
                if feels is not None and feels >= self.config.needs.heat_from_feels:
                    leg["hot"] = feels
                    effects.append(f"walking in {feels:.0f}C feels-like")
                mins = self._speed(leg, w, outfit, hurry)
                if hurry:
                    leg["running"] = True
            leg["end_ts"] = t + mins * 60
            t = leg["end_ts"]
            self._roll(leg, i, now, outfit, hurry)
        if hurry:
            effects.append(f"running late by {late} min, so she ran")
        effects = list(dict.fromkeys(effects))
        j = {"from": frm, "to": to, "legs": legs, "started_ts": now, "eta_ts": t,
             "planned_min": round(sum(l["min"] for l in legs)), "effects": effects, "why": why,
             "date": self.clock.date_str(), "hm": self.clock.hm(), "outfit": outfit, "hurry": hurry,
             "vehicle": vehicle, "sweat": 0.0}
        self.rec["journey"] = j
        self.rec["node"] = None
        self._save()
        logger.log(f"[where] leaving {self.name(frm)} for {self.name(to)}: " + " > ".join(self._leg_txt(l) for l in legs)
                   + f" (eta {self.clock.hm(t)}; wearing {outfit['wear']}, carrying {outfit['carry']}"
                   + (f"; {'; '.join(effects)}" if effects else "") + ")")
        return j

    def pickup(self, why):
        """Dad's car from wherever she is to home, when it is on offer."""
        return self.start("home", why=why, vehicle="car")

    def _leg_txt(self, l):
        s = f"{l['mode']} {round(l['min'])}m to {self.name(l['to'])}"
        if l.get("line"):
            s += f" on the {l['line']}"
        if l.get("crowd"):
            s += ", packed"
        if l.get("running"):
            s += ", running"
        if l.get("status"):
            s += f" ({l['status']})"
        return s

    def current_leg(self, ts=None):
        j = self.rec.get("journey")
        if not j:
            return None
        ts = ts or self.clock.now_ts()
        for l in j["legs"]:
            if ts < l["end_ts"]:
                return l
        return j["legs"][-1] if j["legs"] else None

    # ---------------- things that happen on the way ----------------

    def _roll(self, leg, i, seed, outfit, hurry):
        """One roll per leg at departure, seeded, against the table for that
        mode. Most legs: nothing. The result sits on the leg until its
        minute comes."""
        c = self.config.situation
        rng = random.Random(f"{seed}|{i}|{leg['mode']}")
        table = []
        if leg["mode"] == "walk":
            k = (c.run_bump_factor if hurry else 1.0)
            table = [
                (c.p_bump * k, "bump", 2, {"awkwardness": 6, "anxiety": 2}, 0, "she bumped into somebody at the crossing, bag first, and apologised twice"),
                (c.p_found, "found", 2, {"pride": 4, "boredom": -6}, 1, "she found a hairclip on the pavement, still good, and kept it"),
                (c.p_cat, "cat", 1, {"boredom": -8, "sadness": -3}, 2, "a cat on a wall let her get close for once"),
                (c.p_neighbour, "neighbour", 1, {"awkwardness": 3}, 2, "the woman from the third floor stopped her to ask about school, smiling too much"),
                (c.p_trip * k, "trip", 3, {"awkwardness": 10, "shame": 6, "physical_comfort": -8}, 1, "she caught her foot on the kerb and went over, grazed knee, a man asked if she was okay"),
            ]
            if leg.get("rain") and not leg.get("umbrella"):
                table.append((1.0, "soaked", 3, {"physical_comfort": -18, "anger": 4}, 0, "no umbrella: she got properly soaked, hair and blouse, and it is not drying"))
        elif leg["mode"] == "bike":
            table = [
                (c.p_bike_chain, "chain", 3, {"anger": 8, "awkwardness": 4}, 8, "the chain came off and she had to put it back with her hands, black to the wrist"),
                (c.p_cat, "cat", 1, {"boredom": -6}, 0, "a shiba on a lead barked at her the whole way past"),
            ]
        elif leg["mode"] == "train":
            if leg.get("crowd"):
                # her own line's stations, one and two stops out
                stops = _stops_out(self.config)
                near = (" from %s" % stops[0]) if stops else ""
                out = (" at %s" % stops[1]) if len(stops) > 1 else ""
                table = [
                    (c.p_seat, "seat", 1, {"fatigue": -6, "physical_comfort": 4}, 0, "she got a seat%s, which never happens" % out),
                    (c.p_close, "close", 4, {"anxiety": 12, "shame": 8, "anger": 6, "physical_comfort": -6}, 0, "a man stood too close on the packed car, close enough that she moved cars%s and stood by the door with her arms crossed" % out),
                    (c.p_missed, "missed", 2, {"anger": 4, "anxiety": 3}, 8, "she missed the express by a door and stood on the platform for the next one"),
                    (c.p_bag, "bag", 1, {"physical_comfort": -4, "anger": 2}, 0, "someone's backpack in her back the whole way%s" % near),
                ]
            else:
                table = [
                    (c.p_missed, "missed", 2, {"anger": 3}, 8, "she missed the train by a door and waited for the next"),
                    (c.p_seat * 3, "seat", 1, {"fatigue": -4}, 0, "an empty seat by the door, for once"),
                    (c.p_dog, "dog", 1, {"boredom": -6}, 0, "a dachshund in a bag on the seat opposite, looking at her"),
                ]
        elif leg["mode"] == "car":
            table = [(c.p_car_talk, "cartalk", 2, {"awkwardness": 4}, 0, "dad asked about school in the car, the same question, and she said fine")]
        r = rng.random()
        acc = 0.0
        for p, kind, sal, deltas, mins, text in table:
            acc += p
            if r < acc:
                at = leg["start_ts"] + rng.random() * max(60.0, (leg["end_ts"] - leg["start_ts"]) * 0.9)
                leg["event"] = {"kind": kind, "salience": sal, "deltas": deltas, "minutes": mins, "text": text, "at": at, "fired": False}
                return

    def _fire(self, leg, j):
        ev = leg.get("event")
        if not ev or ev.get("fired"):
            return None
        ev["fired"] = True
        if ev.get("minutes"):
            shift = ev["minutes"] * 60
            for l in j["legs"]:
                if l["end_ts"] >= leg["end_ts"]:
                    l["end_ts"] += shift
            j["eta_ts"] += shift
        if self.state:
            for g, d in (ev.get("deltas") or {}).items():
                try:
                    if g == "fatigue":
                        self.state.gauges["fatigue"] = max(0.0, min(100.0, self.state.gauges["fatigue"] + d))
                    else:
                        self.state._nudge(g, d)
                except Exception:
                    pass
        j["effects"].append(ev["text"][:60])
        return {"kind": "journey", "salience": ev["salience"], "text": ev["text"]}

    def _texting_risk(self, leg, hours):
        """Texting while walking: allowed, and it multiplies the bump chance
        for the minutes she is doing it. Read off her own messages."""
        c = self.config.situation
        if leg["mode"] != "walk" or leg.get("event") or hours <= 0 or not self.state:
            return None
        now = self.clock.now_ts()
        try:
            recent = self.store.recent_messages(6)
        except Exception:
            return None
        texting = any(m["role"] == "assistant" and now - float(m["ts"]) <= c.texting_window_minutes * 60 for m in recent)
        if not texting:
            return None
        p = c.p_bump * c.texting_bump_factor * hours * 60 / max(1.0, float(leg["min"]))
        if random.random() < p:
            leg["event"] = {"kind": "bump_texting", "salience": 3, "deltas": {"awkwardness": 8, "shame": 5, "anxiety": 3}, "minutes": 1,
                            "text": "she walked into a man at the crossing with her eyes on the phone; he said something, she bowed and did not look up", "at": now, "fired": False}
            return leg["event"]
        return None

    def _sweat(self, leg, hours, w):
        """Summer in a uniform, on foot: comfort goes with the minutes in it."""
        c = self.config.situation
        if leg["mode"] not in ("walk", "bike") or not self.state or hours <= 0:
            return
        feels = w.get("feels")
        if feels is None or feels < c.sweat_from_feels:
            return
        j = self.rec.get("journey") or {}
        f = j.get("outfit", {}).get("sweat", 1.0) * (c.run_sweat_factor if leg.get("running") else 1.0)
        amt = c.sweat_comfort_per_hour * (1.0 + (feels - c.sweat_from_feels) / 5.0) * f * hours
        self.state._nudge("physical_comfort", -amt)
        j["sweat"] = round(float(j.get("sweat", 0.0)) + amt, 1)

    def _arrive(self):
        j = self.rec["journey"]
        now = self.clock.now_ts()
        actual = round((now - j["started_ts"]) / 60)
        late = actual - j["planned_min"]
        row = {"date": j["date"], "hm": j["hm"], "from": j["from"], "to": j["to"], "planned_min": j["planned_min"],
               "actual_min": actual, "effects": j.get("effects", []), "legs": [self._leg_txt(l) for l in j["legs"]],
               "arrived_hm": self.clock.hm(), "wear": j.get("outfit", {}).get("wear", ""), "carry": j.get("outfit", {}).get("carry", ""),
               "sweat": j.get("sweat", 0.0), "vehicle": j.get("vehicle", "")}
        self.store.set("journeys", (self.store.get("journeys", []) + [row])[-self.config.situation.keep_journeys:])
        # rain she walked in reaches tomorrow's cold draw
        if self.body:
            for l in j["legs"]:
                if l.get("mode") == "walk" and l.get("rain"):
                    try:
                        self.body.note_wet(float(l.get("min", 0) or 0) / 60.0, soaked=not l.get("umbrella"))
                    except Exception:
                        pass
        self.rec["node"] = j["to"]
        self.rec["journey"] = None
        self.rec["arrived_ts"] = now
        self.rec["last_sweat"] = j.get("sweat", 0.0)
        self._save()
        logger.log(f"[where] arrived at {self.name(j['to'])} after {actual} min" + (f" ({late:+d} vs plan)" if late else "")
                   + (f"; sweat {row['sweat']}" if row["sweat"] else "")
                   + (f"; {'; '.join(row['effects'])}" if row["effects"] else ""))
        events = []
        if late >= self.config.situation.late_event_from and not j.get("hurry"):
            events.append({"kind": "journey", "salience": 3 if late < 25 else 4,
                           "text": f"she got to {self.name(j['to'])} {late} minutes late ({'; '.join(row['effects']) or 'the trains'})"})
        if row["sweat"] >= self.config.situation.sweat_event_from:
            events.append({"kind": "journey", "salience": 2,
                           "text": f"she arrived at {self.name(j['to'])} sweated through, blouse stuck to her back, hair gone"})
        return events

    # ---------------- the clock ----------------

    def tick(self, scene, blocks):
        """Every loop pass. Moves her by the schedule and the director, runs
        the journey on the clock, accumulates fatigue. Returns events."""
        c = self.config.situation
        if not c.enabled:
            return []
        now = self.clock.now_ts()
        hours = max(0.0, (now - float(self.rec.get("last_ts", now))) / 3600.0)
        self.rec["last_ts"] = now
        events = []
        blk, nxt = self._blocks(blocks)
        loc = (scene or {}).get("location") or (blk or {}).get("location") or ""
        act = (scene or {}).get("activity") or (blk or {}).get("activity") or ""
        self.rec["activity"] = act[:80]
        j = self.rec.get("journey")
        if j:
            leg = self.current_leg(now)
            if leg:
                # a line stopping under her mid-leg
                if leg["mode"] == "train" and not leg.get("status"):
                    word, extra, stopped = self._line_status(leg.get("line", ""))
                    if word:
                        leg["status"] = word
                        shift = extra * 60
                        for l in j["legs"]:
                            if l["end_ts"] >= leg["end_ts"]:
                                l["end_ts"] += shift
                        j["eta_ts"] += shift
                        j["effects"].append(f"{leg.get('line')}: {word} mid-ride (+{extra} min)")
                        events.append({"kind": "journey", "salience": 4 if stopped else 3,
                                       "text": (f"her train stopped between stations: the {leg.get('line')} is {word}; she is standing in the car with everyone else, {extra} minutes at least"
                                                if stopped else f"the {leg.get('line')} is {word}; her train is crawling, about {extra} minutes late")})
                        # stranded: someone may come for her -- or not, and the
                        # reason is the family's, not a coin
                        if stopped:
                            ok, who, why = self._pickup_offer(now, leg)
                            if ok:
                                j["effects"].append(f"{who} came to get her")
                                events.append({"kind": "journey", "salience": 3, "text": f"mom rang: {why}; wait by the exit"})
                                self.rec["journey"] = None
                                self.rec["node"] = leg["from"]
                                self.pickup(why=f"the line stopped; {who} drove")
                                j = self.rec["journey"]
                                leg = None
                            elif who:
                                j["effects"].append(f"no pickup: {why}")
                                events.append({"kind": "journey", "salience": 2, "text": f"she rang home about the train; {why}"})
                if leg:
                    self._texting_risk(leg, hours)
                    ev = leg.get("event")
                    if ev and not ev.get("fired") and now >= ev["at"]:
                        fired = self._fire(leg, j)
                        if fired:
                            events.append(fired)
                    self._sweat(leg, hours, self._weather())
            if now >= j["eta_ts"]:
                events += self._arrive()
        else:
            here = self.rec.get("node")
            started = False
            if blk and nxt and self.resolve(blk.get("location", "")) is None \
                    and any(k in (blk.get("location", "") + " " + blk.get("activity", "")).lower() for k in self.config.environment.transit_keywords):
                t2 = self.resolve(nxt.get("location", ""), nxt.get("activity", ""))
                if t2 and t2 != here:
                    self.start(t2, why=f"block: {blk.get('activity', '')[:40]}", blk=blk, nxt=nxt, scene=scene)
                    started = True
            if not started:
                target = self.resolve(loc, act)
                if target and target != here:
                    self.start(target, why=f"{'scene' if (scene or {}).get('location') else 'block'}: {loc[:40]}", blk=blk, nxt=nxt, scene=scene)
        self._fatigue(hours, scene, blk)
        self._save()
        return events

    def _pickup_offer(self, ts, leg):
        """(ok, who, why): the family's answer when she is stranded. With no
        family object nobody can come: a character without one has nobody to ring."""
        fam = self.family
        if fam:
            try:
                mins = sum(float(l["min"]) for l in (self.rec.get("journey") or {}).get("legs", []) if l["end_ts"] > ts)
                return fam.can_pickup(ts, from_node=leg.get("from", ""), minutes_away=mins)
            except Exception as e:
                logger.log(f"[where] pickup not asked: {type(e).__name__}: {e}")
        return False, "", "nobody can come"

    def _blocks(self, blocks):
        if not blocks:
            return None, None
        hm = self.clock.hm()
        for i, b in enumerate(blocks):
            if b["start"] <= hm < b["end"]:
                return b, (blocks[i + 1] if i + 1 < len(blocks) else None)
        return None, None

    # ---------------- fatigue ----------------

    def mode(self):
        """What her body is doing right now: walk / running / bike / packed_train /
        train / car / out / sitting / still / resting / bath / asleep."""
        j = self.rec.get("journey")
        if j:
            leg = self.current_leg()
            if leg:
                if leg["mode"] == "train":
                    return "packed_train" if leg.get("crowd") else "train"
                if leg["mode"] == "walk" and leg.get("running"):
                    return "running"
                return leg["mode"]
        act = (self.rec.get("activity") or "").lower()
        node = self.rec.get("node") or ""
        if any(k in act for k in ("asleep", "sleeping")):
            return "asleep"
        if any(k in act for k in ("bath", "shower", "ofuro")):
            return "bath"
        if any(k in act for k in ("lying", "in bed", "lying down", "on the floor", "napping", "dozing")):
            return "resting"
        if node == "home":
            return "still"
        if node in ("school",):
            return "sitting"
        return "out"

    def _fatigue(self, hours, scene, blk):
        c = self.config.situation
        g = self.state.gauges if self.state else None
        if g is None or "fatigue" not in g or hours <= 0:
            return
        m = self.mode()
        rate = {"walk": c.walk_per_hour, "running": c.walk_per_hour * c.run_fatigue_factor, "bike": c.walk_per_hour * 0.8,
                "packed_train": c.packed_per_hour, "train": c.train_per_hour, "car": -c.rest_per_hour * 0.3, "out": c.out_per_hour,
                "sitting": c.sitting_per_hour, "still": -c.rest_per_hour * 0.5, "resting": -c.rest_per_hour,
                "bath": -c.bath_per_hour, "asleep": -c.sleep_per_hour}.get(m, 0.0)
        if rate > 0:
            j = self.rec.get("journey") or {}
            rate *= float(j.get("outfit", {}).get("load", 1.0)) if j else 1.0
            feels = None
            try:
                feels = (self.body.last or {}).get("ambient_feels") if self.body else None
            except Exception:
                feels = None
            if feels is not None and feels > c.heat_free_feels:
                rate *= 1.0 + (feels - c.heat_free_feels) / c.heat_per_degree
        base = float(self.config.state.gauges["fatigue"]["baseline"])
        cur = float(g["fatigue"])
        new = cur + rate * hours
        if rate < 0:
            new = max(base, new)
        g["fatigue"] = max(0.0, min(100.0, new))

    # ---------------- readers ----------------

    def constraints(self):
        m = self.mode()
        j = self.rec.get("journey")
        left = int((j["eta_ts"] - self.clock.now_ts()) / 60) if j else 0
        leg = self.current_leg() if j else None
        f = float(self.state.gauges.get("fatigue", 0)) if self.state else 0.0
        can_type = "fine"
        if m == "running":
            can_type = "no (running)"
        elif m in ("walk", "bike"):
            can_type = "possible, one eye on the road" if m == "walk" else "no (on the bike)"
        elif m == "packed_train":
            can_type = "one thumb, held up to her face"
        elif m == "car":
            can_type = "fine, but dad is right there"
        private = bool((self.nodes.get(self.rec.get("node") or "") or {}).get("private")) and not j
        return {"mode": m, "node": self.rec.get("node"), "journey": j, "minutes_left": left, "leg": leg,
                "fatigue": f, "can_type": can_type, "private": private}

    def delay_multiplier(self):
        c = self.config.situation
        k = self.constraints()
        f = 1.0 + (k["fatigue"] / 100.0) * c.fatigue_delay_weight
        m = k["mode"]
        if m == "running" or m == "bike":
            f *= c.running_delay
        elif m == "walk":
            f *= c.walking_delay
        elif m == "packed_train":
            f *= c.packed_delay
        return f

    def shape_bias(self):
        m = self.mode()
        if m in ("walk", "running", "bike"):
            return "curt"
        if m == "packed_train":
            return "short"
        if self.state and float(self.state.gauges.get("fatigue", 0)) >= self.config.situation.wiped_from:
            return "short"
        return ""

    def register_line(self):
        if self.state and float(self.state.gauges.get("fatigue", 0)) >= self.config.situation.wiped_from:
            return "wiped: the day is in her legs and her thumbs; short answers, typos she does not fix, nothing that needs thinking"
        return ""

    def persona_line(self):
        k = self.constraints()
        j = k["journey"]
        bits = []
        if j and k["leg"]:
            leg = k["leg"]
            where = {"walk": ("running to " if leg.get("running") else "walking to ") + self.name(leg["to"]),
                     "bike": f"on her bike to {self.name(leg['to'])}",
                     "train": f"on the {leg.get('line', 'train')} to {self.name(leg['to'])}" + (", standing, packed, one hand on the strap" if leg.get("crowd") else ", sitting"),
                     "car": f"in dad's car to {self.name(leg['to'])}"}.get(leg["mode"], f"on the way to {self.name(leg['to'])}")
            bits.append(f"you are {where}, about {max(1, k['minutes_left'])} min to go; typing is {k['can_type']}")
            o = j.get("outfit") or {}
            if o.get("wear") and o["wear"] != "casual":
                bits.append(f"in {o['wear']}" + (f", carrying {o['carry']}" if o.get("carry") and o["carry"] != "nothing much" else ""))
            if j.get("hurry"):
                bits.append("you are late and you know it")
            if leg.get("status"):
                bits.append(f"the line is {leg['status']}")
            if leg.get("rain"):
                bits.append("it is raining on you" + ("" if leg.get("umbrella", True) else " and you have no umbrella"))
            if leg.get("hot"):
                bits.append(f"it is {leg['hot']:.0f}C out here")
            if float(j.get("sweat", 0)) >= self.config.situation.sweat_line_from:
                bits.append("you are sweating through the blouse")
        elif float(self.rec.get("last_sweat", 0) or 0) >= self.config.situation.sweat_line_from and self.clock.now_ts() - float(self.rec.get("arrived_ts", 0)) < 40 * 60:
            bits.append("you just got in sweated through, hair stuck to your neck")
        f = k["fatigue"]
        if f >= self.config.situation.wiped_from:
            bits.append("you are wiped -- legs heavy, eyes going")
        elif f >= self.config.situation.tired_from:
            bits.append("your legs are tired from the day")
        return "; ".join(bits)

    def director_line(self):
        k = self.constraints()
        j = k["journey"]
        if j and k["leg"]:
            leg = k["leg"]
            rest = [self._leg_txt(l) for l in j["legs"] if l["end_ts"] > self.clock.now_ts()]
            o = j.get("outfit") or {}
            return (f"SHE IS ON THE WAY from {self.name(j['from'])} to {self.name(j['to'])}: now {self._leg_txt(leg)}, "
                    f"about {max(1, k['minutes_left'])} min until she is there (eta {self.clock.hm(j['eta_ts'])}); remaining: {' > '.join(rest)}; "
                    f"wearing {o.get('wear', '?')}, carrying {o.get('carry', '?')}"
                    + (", LATE and running" if j.get("hurry") else "") + ". "
                    f"Put the scene WHERE SHE ACTUALLY IS -- she cannot be at {self.name(j['to'])} yet."
                    + (f" Her line: {leg['status']}." if leg.get("status") else "")
                    + (f" What just happened on the way (already in the events; show it, do not invent another): {j['effects'][-1]}." if j.get("effects") else ""))
        # Silent when she has no place graph. With the section off this still
        # spoke, and what it said was false: it reported `SHE IS AT home` --
        # the default string, not a node of any graph -- and told the
        # director that a scene anywhere else needs a journey on the clock,
        # while her plan had her in the bath. `sim/ledger.py` is the day's
        # one truth and nothing may contradict it; this did, from inside the
        # director's own prompt.
        if not getattr(self.config.situation, "enabled", False):
            return ""
        node = self.rec.get("node")
        return f"SHE IS AT {self.name(node)} (since {self.clock.hm(self.rec.get('arrived_ts', 0))}); a scene somewhere else means she travels there first, on the clock" if node else ""

    def report(self):
        k = self.constraints()
        lines = [f"where: {self.name(k['node']) if k['node'] else 'on the way'}; mode {k['mode']}; fatigue {k['fatigue']:.0f}; typing {k['can_type']}; private {k['private']}"]
        j = k["journey"]
        if j:
            o = j.get("outfit") or {}
            lines.append(f"journey {self.name(j['from'])} -> {self.name(j['to'])}, left {self.clock.hm(j['started_ts'])}, eta {self.clock.hm(j['eta_ts'])} ({k['minutes_left']} min left); "
                         + " > ".join(self._leg_txt(l) for l in j["legs"]) + f"; wearing {o.get('wear')}, carrying {o.get('carry')}"
                         + ("; LATE, running" if j.get("hurry") else "") + (f"; sweat {j.get('sweat')}" if j.get("sweat") else "")
                         + (f"; {'; '.join(j['effects'])}" if j.get("effects") else ""))
        lines.append(f"delay x{self.delay_multiplier():.2f}; shape bias {self.shape_bias() or '-'}; {self.register_line() or 'register: nothing from the body'}")
        rows = self.store.get("journeys", [])[-8:]
        if rows:
            lines.append("journeys:")
            for r in rows:
                lines.append(f"  {r['date'][5:]} {r['hm']}-{r['arrived_hm']} {self.name(r['from'])} -> {self.name(r['to'])}: {r['actual_min']} min (plan {r['planned_min']}"
                             + (f", {r['vehicle']}" if r.get("vehicle") else "") + ")"
                             + (f"; {'; '.join(r['effects'])}" if r.get("effects") else ""))
        return "\n".join(lines)
