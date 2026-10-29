"""How long he has been away, for a character who lives on a visual novel stage.

The phone-era model asked whether he had read her message and whether his
machine was busy (`sim/receipts.py`, `sim/rhythm.py:presence`). A visual novel
has no away channel: he is either at the stage or the story is not happening.

"Being away" is defined as a message gap -- `reunion.min_away_minutes`, six
hours by default: that long or longer with nothing from him. The stage touch is
only the trigger (he opened the page after that long), and the gap itself is
measured from his last message.

Nothing is sent while he is away. The one output is the arrival: the director
sets the scene and she says a single short line, as if he walked in on her in
the middle of something. That is not her initiating -- she does not write to
him first (`character.existence.player_driven`) -- it is the scene opening.
"""

# A page that polls every second must not write the save every second; a
# gesture inside this window is still the same visit.
MIN_STAMP_GAP_SECONDS = 5.0


def _away_text(hours, ja=False):
    """What she would say it has been. Rounded; nobody thinks in 5.7 hours."""
    if hours < 1.0:
        m = max(1, int(round(hours * 60.0)))
        return f"{m}分" if ja else f"{m} minute{'s' if m != 1 else ''}"
    if hours < 24.0:
        h = max(1, int(round(hours)))
        return f"{h}時間" if ja else f"{h} hour{'s' if h != 1 else ''}"
    d = max(1, int(round(hours / 24.0)))
    return f"{d}日" if ja else f"{d} day{'s' if d != 1 else ''}"


class Reunion:
    """How long he has been gone, and the one arrival that ends it."""

    def __init__(self, config, store, clock):
        self.config = config
        self.store = store
        self.clock = clock

    @property
    def c(self):
        return getattr(self.config, "reunion", None)

    def _on(self):
        c = self.c
        return bool(c is not None and getattr(c, "enabled", False))

    def enabled(self):
        """Whether this character keeps the reunion clock at all."""
        return self._on()

    def _min_away_seconds(self):
        c = self.c
        return float(getattr(c, "min_away_minutes", 360) or 360) * 60.0

    def away_seconds(self):
        """How long he has been gone: since his last message, or None when he
        never has messaged. This is the classification, not the visit."""
        try:
            last = self.store.last_message("user")
        except Exception:
            last = None
        if not last:
            return None
        return max(0.0, self.clock.now_ts() - float(last.get("ts") or 0))

    def away_hours(self):
        s = self.away_seconds()
        return None if s is None else s / 3600.0

    def away(self):
        """Whether he counts as away right now: the message gap is long enough."""
        s = self.away_seconds()
        return bool(s is not None and s >= self._min_away_seconds())

    def present(self):
        """Whether the stage was touched recently enough to count as still here."""
        try:
            last = float(self.store.get("present_ts", 0) or 0)
        except Exception:
            last = 0.0
        if not last:
            return False
        c = self.c
        window = float(getattr(c, "present_window_seconds", 120) or 120)
        return (self.clock.now_ts() - last) <= window

    def stamp(self):
        """He touched the stage. Called from the channel on every interaction;
        the save write is throttled, so a poll a second costs nothing.

        A touch after a long message gap is an arrival, and books exactly one:
        he opened the page after being away, and the scene opens on her in the
        middle of something."""
        if not self._on():
            return
        now = self.clock.now_ts()
        try:
            last_touch = float(self.store.get("present_ts", 0) or 0)
        except Exception:
            last_touch = 0.0
        if now - last_touch < MIN_STAMP_GAP_SECONDS:
            return
        # never on a first-ever visit: there is no away to have come back from
        if last_touch:
            away = self.away_seconds()
            if away is not None and away >= self._min_away_seconds():
                try:
                    self.store.set("reunion_arrival", {"away_s": away, "ts": now})
                except Exception:
                    pass
        try:
            self.store.set("present_ts", now)
        except Exception:
            pass

    def take_arrival(self):
        """The pending arrival, once: `{"away_s": .., "ts": ..}` or None."""
        try:
            got = self.store.get("reunion_arrival", None)
        except Exception:
            got = None
        if got:
            try:
                self.store.set("reunion_arrival", None)
            except Exception:
                pass
        return got or None

    def line(self, ja=False):
        """One line for her situation on his return, or '' when he was not gone.

        The stage knowing he is away is not a reason to speak: she never writes
        first (`character.existence.player_driven`). This is context for the
        turn he causes, and nothing more."""
        if not self._on():
            return ""
        h = self.away_hours()
        if h is None or h < self._min_away_seconds() / 3600.0:
            return ""
        ago = _away_text(h, ja)
        if ja:
            return (f"彼は{ago}ぶりに戻ってきた。あなたは自分の時間を過ごしていた。"
                    f"彼はまだ何も言っていない。")
        return (f"he is back after {ago} away; you were living your own time in "
                f"between, and he has not said anything yet.")
