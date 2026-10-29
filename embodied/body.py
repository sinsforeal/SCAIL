from sim import lang

# Where her body is and what it needs, mechanically. The weather line says
# what Tokyo feels like outside; what she feels depends on whether she is
# walking in it, on an air-conditioned train, or in her room with the
# air-con on. This module turns the scene (or, between ticks, the schedule
# block) into a setting and an ambient feels-like that the comfort gauge
# follows, and tracks hunger the same way: it rises with the hours, meals
# reset it, and both the director and the persona are told, so "it's hot"
# is only said when she is hot and "starving" when she has not eaten.
# Rest is the energy gauge, which already follows sleep and late nights.

SETTINGS = ("outdoors", "indoors_ac", "indoors", "transit", "bath")


def indoor_ambient(e, out_feels):
    """Room feels-like for an indoor space given the outdoor feels-like, AC on
    automatically once it is hot enough to run it. One source of truth for
    what a room holds: used by the live comfort model here and by the sleep
    model (the bedroom overnight). Returns None if there is no weather."""
    if out_feels is None:
        return None
    if out_feels >= e.ac_from_feels:      # hot out: AC on, room sits at the set-point
        return e.ac_feels
    if out_feels <= e.heat_from_feels:    # cold out: heating on
        return e.heated_feels
    # mild: a room holds some of the outside, a touch cooler when warm
    return out_feels - e.indoor_offset if out_feels > e.ac_feels else out_feels + e.indoor_offset


class Body:
    def __init__(self, config, store, clock, weather):
        self.config = config
        self.store = store
        self.clock = clock
        self.weather = weather
        self.last = {}

    # ---------------- setting and ambient

    def _classify(self, location, activity):
        """The location decides when it can; the activity only when the location says nothing."""
        e = self.config.environment
        for t in ((location or "").lower(), (activity or "").lower()):
            if any(k in t for k in e.bath_keywords):
                return "bath"
            if any(k in t for k in e.transit_keywords):
                return "transit"
            if any(k in t for k in e.outdoor_keywords):
                return "outdoors"
            if any(k in t for k in e.indoor_keywords):
                return "indoors"
        return "indoors"

    def setting(self, scene, block, scene_fresh):
        """Returns {setting, ambient_feels, outside_feels, outside_temp, humidity, place, line}."""
        e = self.config.environment
        try:
            cur = self.weather.current(self.clock.now())
            out_feels = cur.get("feels")
            out_temp = cur.get("temp")
            humidity = cur.get("humidity")
            sky = cur.get("sky", "")
        except Exception:
            out_feels = out_temp = humidity = None
            sky = ""
        src = scene if (scene and scene_fresh) else (block or {})
        place = f"{src.get('location', '')}".strip()
        said = (scene or {}).get("setting") if (scene and scene_fresh) else None
        if said in SETTINGS:
            s = said
        else:
            s = self._classify(src.get('location', ''), src.get('activity', ''))
            # indoors without a word from the director: the air-con is on when
            # it is hot enough outside, the heating when it is cold enough
            if s == "indoors" and out_feels is not None and out_feels >= e.ac_from_feels:
                s = "indoors_ac"
        if out_feels is None:
            ambient = None
        elif s == "outdoors":
            ambient = out_feels
        elif s == "transit":
            ambient = e.transit_feels if out_feels >= e.ac_from_feels or out_feels <= e.heat_from_feels else out_feels
        elif s == "indoors_ac":
            ambient = e.ac_feels
        elif s == "bath":
            ambient = e.bath_feels
        else:  # indoors, no air-con: a room holds some of the outside, heating in winter
            ambient = indoor_ambient(e, out_feels)
        line = self._line(s, ambient, out_temp, out_feels, humidity, sky)
        self.last = {"setting": s, "ambient_feels": ambient, "outside_feels": out_feels, "outside_temp": out_temp,
                     "humidity": humidity, "place": place, "line": line}
        return self.last

    @staticmethod
    def _line(s, ambient, out_temp, out_feels, humidity, sky):
        if out_feels is None:
            return ""
        outside = f"outside {out_temp}C, feels {out_feels}C, humidity {humidity}%, {sky}"
        if s == "outdoors":
            return f"outdoors in it ({outside})"
        if s == "transit":
            return f"on transit, air-conditioned, about {ambient}C ({outside})"
        if s == "indoors_ac":
            return f"indoors with the air-con on, about {ambient}C ({outside})"
        if s == "bath":
            return f"in the bath ({outside})"
        return f"indoors without air-con, about {ambient}C ({outside})"

    def persona_line(self, ja=False):
        """What she would notice about the air, for her situation block.

        Nothing at all for a character with no body to feel it in. This tested
        whether a `Body` object existed rather than whether she has one, and
        the object is built for everybody -- so an invented Tokyo reached her
        prompt as "around you: you are inside, 24.9C". The section's own flag
        is the answer, checked here rather than at the two call sites, because
        a third one would have missed it again."""
        if not getattr(self.config.environment, "enabled", False):
            return ""
        l = self.last
        if not l or l.get("ambient_feels") is None:
            return ""
        s = l["setting"]
        of = l["outside_feels"]
        hot = of is not None and of >= self.config.environment.ac_from_feels
        cold = of is not None and of <= self.config.environment.heat_from_feels
        t = lang.pick(ja)
        if s == "outdoors":
            if hot:
                return t(f"you are outside and it is hot ({of}C feels-like, humid)",
                         f"外にいて、暑い（体感{of}度、じめじめしている）")
            if cold:
                return t(f"you are outside and it is cold ({of}C feels-like)", f"外にいて、寒い（体感{of}度）")
            return t(f"you are outside, {of}C feels-like", f"外にいる。体感{of}度")
        if s == "indoors_ac":
            return t(f"you are inside with the air-con on, comfortable; outside it is {of}C feels-like",
                     f"室内で冷房が入っていて、快適。外は体感{of}度") if hot else \
                t(f"you are inside, comfortable; outside it is {of}C feels-like",
                  f"室内で快適。外は体感{of}度")
        if s == "transit":
            return t(f"you are on the train, air-conditioned; outside it is {of}C feels-like",
                     f"電車の中で、冷房が効いている。外は体感{of}度")
        if s == "bath":
            return t("you are in the bath", "お風呂に入っている")
        if hot:
            return t(f"you are inside without the air-con; the room is warm ({l['ambient_feels']}C), outside {of}C feels-like",
                     f"室内で冷房はなし。部屋が暖かい（{l['ambient_feels']}度）、外は体感{of}度")
        if cold:
            return t(f"you are inside with the heating on; outside it is {of}C feels-like",
                     f"室内で暖房が入っている。外は体感{of}度")
        return t(f"you are inside, {l['ambient_feels']}C", f"室内。{l['ambient_feels']}度")

    def note_wet(self, hours, soaked=False):
        """A walk in the rain counts as exposure whatever the scene's setting
        says, and getting soaked counts `health.wet_exposure_factor` times
        over. Before this only a scene stamped `outdoors` during the tick
        counted, so a rain leg of a journey (scene `transit`) and an umbrella
        walk weighed the same: nothing."""
        if hours <= 0:
            return
        h = hours * (self.config.health.wet_exposure_factor if soaked else 1.0)
        ex = self.store.get("exposure", {})
        d = self.clock.date_str()
        ex[d] = round(ex.get(d, 0) + h, 3)
        self.store.set("exposure", dict(sorted(ex.items())[-7:]))

    def note_exposure(self, hours):
        """Hours outdoors in heat or rain, per date (kv exposure); health reads yesterday's."""
        n = self.config.needs
        l = self.last
        if not l or l.get("setting") != "outdoors" or hours <= 0:
            return
        hot = (l.get("ambient_feels") or 0) >= n.heat_from_feels
        try:
            rain = (self.weather.current(self.clock.now()).get("precip_mm") or 0) >= n.rain_mm_from
        except Exception:
            rain = False
        if not (hot or rain):
            return
        ex = self.store.get("exposure", {})
        d = self.clock.date_str()
        ex[d] = round(ex.get(d, 0) + hours, 3)
        self.store.set("exposure", dict(sorted(ex.items())[-7:]))

    def red(self, gauges):
        """Which needs are red right now: ['hungry', 'exhausted']."""
        n = self.config.needs
        out = []
        if gauges.get("hunger", 0) >= n.red_hunger:
            out.append("hungry")
        if gauges.get("energy", 100) <= n.red_energy:
            out.append("exhausted")
        return out

    # ---------------- needs

    def meal_kind(self, scene, block, scene_fresh):
        """'meal' / 'snack' / '' from the director's `ate` or the words of the scene / block."""
        n = self.config.needs
        if scene and scene_fresh:
            ate = (scene.get("ate") or "").strip().lower() if isinstance(scene.get("ate"), str) else ""
            if ate in ("meal", "snack"):
                return ate
        src = scene if (scene and scene_fresh) else (block or {})
        t = f"{src.get('activity', '')} {src.get('location', '')}".lower()
        if any(k in t for k in n.meal_keywords):
            return "meal"
        if any(k in t for k in n.snack_keywords):
            return "snack"
        return ""

    def note_meal(self, kind, gauges):
        """Apply a meal to hunger at once (the director said she ate).

        Nothing at all for a character with no hunger to satisfy. The caller
        guards on this object existing, which it does for everybody, and the
        line below indexes `gauges["hunger"]` -- a key a sheet is allowed to
        remove. Her plan has her eating in the kitchen at 13:00, so one model
        answer of "meal" would have ended her loop on a KeyError. The prompt
        already tells her director not to set `ate`, and a prompt rule nothing
        checks is a suggestion."""
        n = self.config.needs
        if not getattr(n, "enabled", False) or "hunger" not in gauges:
            return
        if kind == "meal":
            gauges["hunger"] = min(gauges["hunger"], n.after_meal)
            self.store.set("last_meal_ts", self.clock.now_ts())
        elif kind == "snack":
            gauges["hunger"] = max(n.after_meal, gauges["hunger"] - n.snack_drop)

    def hunger_tags(self, gauges):
        n = self.config.needs
        h = gauges.get("hunger", 0)
        if h >= n.starving_from:
            return ["really hungry"]
        if h >= n.hungry_from:
            return ["hungry"]
        return []

    def needs_line(self, gauges):
        """For the director: hunger with when she last ate; rest as energy.

        Empty for a character who has no physical needs modelled, for the same
        reason as `persona_line` above: the object exists for everybody and the
        flag is what says whether she does."""
        if not getattr(self.config.needs, "enabled", False):
            return ""
        n = self.config.needs
        h = gauges.get("hunger", 0)
        last = self.store.get("last_meal_ts")
        since = f", last ate {((self.clock.now_ts() - last) / 3600):.1f}h ago" if last else ""
        hs = "really hungry" if h >= n.starving_from else "hungry" if h >= n.hungry_from else "not hungry" if h < n.hungry_from * 0.5 else "could eat"
        e = gauges.get("energy", 50)
        es = "exhausted" if e < 20 else "tired" if e < 40 else "rested" if e > 65 else "okay"
        return f"{hs} (hunger {int(h)}{since}); {es} (energy {int(e)})"
