"""A gauge at its end is an event, not a level.

His ask (2026-08-26): "gauge limits as events rather than saturating
levels -- reaching a ceiling or floor discharges into a discrete
behavioural or cognitive event, then resets lower." Before this a gauge
at 95 sat at 95: anger stayed 81 for thirteen hours and the only thing it
did was colour her register. A person at the end of their anger does
something -- snaps, throws the phone on the bed, cries -- and comes down
from it, and what they did is on the record.

`state.discharge.rules`: one per gauge, with the level it fires at, what
it resets to, a cooldown, and the behaviour. Four kinds of behaviour, all
dispatched by `App.maybe_discharge`:

- `say`: a forced self-started message -- the impulse gate and her resolve
  do not get a vote, and the intent is given the discharge as the whole
  hint (anger: it comes out at him sharp and unedited; unsaid: the thing
  comes out badly worded; loneliness: she reaches with no pretext;
  craving: she fishes). Needs the phone; otherwise the fallback fires.
- `look`: a forced look at the app (boredom, jealousy).
- `spiral`: a chain starts (anxiety). Falls back if one is live.
- `act`: something in the room -- she cried, she gave up on the day, she
  went small -- an event of salience 3 that the next director scene must
  reflect (it rides in as THINGS THAT JUST HAPPENED), with side effects
  on other gauges and, where it is a release, a stress relief.

Code decides all of it; no model call is made here. The reset is to a
level, not to rest: what caused it has not gone. `/discharge` lists the
rules and what fired.
"""
import logger


class Discharge:
    def __init__(self, config, store, clock, state, stress=None):
        self.config = config
        self.store = store
        self.clock = clock
        self.state = state
        self.stress = stress
        self.pending = []   # events for the next director tick

    def rules(self):
        return list(self.config.state.discharge.rules or [])

    def _count(self):
        return int((self.store.get("discharge_counts", {}) or {}).get(self.clock.date_str(), 0))

    def check(self, scene=None, asleep=False):
        """Fire every rule whose gauge is at its end and off cooldown; reset
        the gauge; record it. Returns the rules that fired, for the App to
        act on."""
        c = self.config.state.discharge
        if not c.enabled or asleep:
            return []
        now = self.clock.now_ts()
        last = self.store.get("discharge_last", {}) or {}
        fired = []
        for r in self.rules():
            g = r.get("gauge")
            if g not in self.state.gauges:
                continue
            cur = float(self.state.gauges[g])
            floor = r.get("floor")
            hit = (cur <= float(floor)) if floor is not None else (cur >= float(r.get("at", 95)))
            if not hit:
                continue
            if now - float(last.get(g, 0) or 0) < float(r.get("cooldown_hours", c.cooldown_hours)) * 3600:
                continue
            if self._count() + len(fired) >= c.max_per_day:
                logger.log(f"[discharge] {g} at {cur:.0f} but the day's cap is reached")
                break
            self.state.gauges[g] = float(r.get("reset_to", 50))
            last[g] = now
            fired.append(dict(r, was=round(cur), ts=now))
        if fired:
            self.store.set("discharge_last", last)
            today = self.clock.date_str()
            self.store.bump_today("discharge_counts", today, len(fired))
            self.state.save()
        return fired

    def act(self, r, how=""):
        """The `act` behaviour (or any rule's fallback): the event, the side
        effects, the relief. Returns the event text."""
        text = str(r.get("text", "") or f"her {r['gauge']} hit its end")
        now = self.clock.now_ts()
        for g, d in (r.get("side") or {}).items():
            if g in self.state.gauges:
                try:
                    self.state._nudge(g, float(d))
                except Exception:
                    pass
        if r.get("relieve") and self.stress:
            try:
                self.stress.relieve(r["relieve"])
            except Exception:
                pass
        self.state.save()
        self.store.add_event(now, self.clock.date_str(), "discharge", text, 3)
        self.pending.append({"text": text, "salience": 3})
        self.record(r, "act" + (f":{how}" if how else ""), text)
        return text

    def record(self, r, did, text=""):
        rows = self.store.get("discharges", [])
        rows.append({"date": self.clock.date_str(), "hm": self.clock.hm(), "ts": r.get("ts", self.clock.now_ts()), "gauge": r["gauge"],
                     "was": r.get("was"), "reset_to": r.get("reset_to"), "did": did, "text": str(text)[:160]})
        self.store.set("discharges", rows[-self.config.state.discharge.keep:])
        logger.log(f"[discharge] {r['gauge']} {r.get('was')} -> {r.get('reset_to')}: {did} -- {str(text)[:100]}")

    def take(self):
        out, self.pending = self.pending, []
        return out

    def report(self):
        c = self.config.state.discharge
        g = self.state.gauges
        last = self.store.get("discharge_last", {}) or {}
        now = self.clock.now_ts()
        lines = [f"discharge: {'on' if c.enabled else 'off'}; {self._count()}/{c.max_per_day} today; a gauge at its end does something and resets",
                 "  gauge               now   fires at  resets to  action   cooldown"]
        for r in self.rules():
            gg = r["gauge"]
            cd = float(r.get("cooldown_hours", c.cooldown_hours))
            rem = max(0.0, cd - (now - float(last.get(gg, 0) or 0)) / 3600.0) if last.get(gg) else 0.0
            lvl = f"<= {r['floor']}" if r.get("floor") is not None else f">= {r.get('at')}"
            lines.append(f"  {gg:18s} {float(g.get(gg, 0)):5.0f}   {lvl:8s}   {float(r.get('reset_to', 0)):5.0f}    {r.get('action', 'act'):7s}  {('%.1fh left' % rem) if rem else 'ready'}")
        rows = self.store.get("discharges", [])[-8:]
        if rows:
            lines.append("  fired:")
            for x in rows:
                lines.append(f"    {x['date'][5:]} {x['hm']} {x['gauge']} {x['was']} -> {x['reset_to']} ({x['did']}): {x['text'][:90]}")
        else:
            lines.append("  fired: nothing yet")
        return "\n".join(lines)
