
import logger
from sim import chattext
from sim import sight
from sim.episodes import EpisodeLog

# Getting at a thing she is not allowed to know.
#
# A sealed discovery -- something she found by going through his phone app --
# was unraisable for as long as it stayed hot, and that meant a month. The big
# one landed at charge 100 with a nine-day half-life against a carry floor of
# 12, so it sat in her prompt as "you cannot bring this up" for twenty-seven
# days and she never once went near it. Then it cooled and became teasable, and
# the only thing that had ever happened to the largest fact she held about him
# was that it stopped mattering.
#
# That is not what people do. Nobody who has read something they should not
# have holds it perfectly for a month and then makes a joke of it. They circle
# it. They ask a question that only makes sense if you already know, and hope
# he answers it himself; they bring up the neighbouring subject; they leave a
# gap for him to fill. The source stays hidden and the subject comes up anyway,
# which is a different thing from confessing and a different thing from silence.
#
# So: code decides when she reaches for it (pressure against opportunity, with
# a per-item memory so she does not circle the same thing nightly), a call
# decides what she actually says, and the hard rule the call cannot break is
# that she never reveals how she knows.
#
# What it does NOT do is let her say it outright. The seal is intact; this is
# the pressure finding the shape of an ordinary question. `risk` is how close
# she came, and a high one costs her -- that is the price of reaching.


class Approach(EpisodeLog):
    LOG_KEY = "approaches"

    def __init__(self, config, llm, store, clock, state, ick, sentiments=None, records=None):
        self.config = config
        self.llm = llm
        self.store = store
        self.clock = clock
        self.state = state
        self.ick = ick
        self.sentiments = sentiments
        self.records = records

    # ---------------- bookkeeping ----------------

    def _for(self, item):
        key = self._key(item)
        return [a for a in self._log() if a.get("key") == key]

    @staticmethod
    def _key(item):
        return f"{item.get('ts')}"

    # ---------------- code decides when ----------------

    def pressure(self, item, now):
        """How hard this one is pushing. Live charge is most of it; the rest is
        that it has had time to work on her, and that she has nowhere else to
        put it."""
        c = self.config.approach
        live = float(item.get("live", item.get("charge", 0)) or 0)
        days = max(0.0, (now - float(item.get("ts", now))) / 86400.0)
        g = self.state.gauges
        unsaid_over = max(0.0, self.state.over_rest("unsaid"))
        p = (live / 100.0) * c.weight_charge
        p += min(1.0, days / max(0.1, c.days_full)) * c.weight_age
        p += min(1.0, unsaid_over / 60.0) * c.weight_unsaid
        # how much he is to her: you do not fish a stranger for what he meant
        try:
            key = self.state._him_key()
            att = self.sentiments.live(key, "attachment") / 100.0 if (self.sentiments and key) else 0.5
        except Exception:
            att = 0.5
        p += att * c.weight_attachment
        return p

    def due(self, scene=None):
        """(item, why) when she is going to reach for one, else (None, why).

        Pure code. Every gate here is opportunity or cost -- never whether the
        thing is important, which is the model's business and already priced
        into the charge."""
        c = self.config.approach
        if not c.enabled or not self.ick:
            return None, "off"
        g = self.state.gauges
        now = self.clock.now_ts()
        # she cannot face it. shame is the gauge that makes her hide, and this
        # is the most exposing thing she could do short of admitting it
        if g.get("shame", 0) >= c.shame_blocks_from:
            return None, f"too ashamed to go near it (shame {g.get('shame', 0):.0f})"
        if g.get("unsaid", 0) < self.state._baseline("unsaid") + c.unsaid_over_baseline:
            return None, "not enough is sitting on her"
        if self._today() >= c.max_per_day:
            return None, "daily cap"
        if now - self._last_ts() < c.min_gap_hours * 3600:
            return None, "too soon after the last one"
        # a scene with people in it is not where she does this
        who = str((scene or {}).get("with") or (scene or {}).get("with_who") or "alone").lower()
        if who not in ("alone", "", "nobody"):
            return None, f"not with {who} there"

        best, best_p = None, 0.0
        for it in self.ick.carrying():
            live = float(it.get("live", it.get("charge", 0)) or 0)
            if live < c.min_live:
                continue
            mine = self._for(it)
            if len(mine) >= c.max_per_item:
                continue
            if mine and (now - max(float(a["ts"]) for a in mine)) < c.per_item_gap_days * 86400:
                continue
            p = self.pressure(it, now)
            if p > best_p:
                best, best_p = it, p
        if not best:
            return None, "nothing sealed is pushing hard enough"
        if best_p < c.threshold:
            return None, f"the pressure is there but not enough of it (p {best_p:.2f} of {c.threshold})"
        return best, f"p {best_p:.2f}, held {(now - float(best['ts'])) / 86400.0:.1f}d, live {best.get('live', 0)}"

    # ---------------- the model decides what ----------------

    def write(self, item, scene=None):
        """What she gets at and how obliquely. Returns the dict or None.

        No words of hers: the subject and the angle go to her own call as a
        hint and she writes the message, so nothing here can arrive in his
        chat as a sentence a role wrote."""
        c = self.config.approach
        rels = self.records.cast_sheet(self.state.relationships) if self.records else ""
        prior = self._for(item)
        prior_txt = "\n".join(f"- she has already gone at: {(a.get('subject') or a.get('line', ''))[:150]}" for a in prior) or "(she has not gone near it yet)"
        recent = self.store.recent_messages(c.messages_shown)
        chat = chattext.lines(recent, chars=160, labels=("him", "her"), stamps=False) or "(nothing recent)"
        scene_txt = (f"{(scene or {}).get('location', '')} / {(scene or {}).get('activity', '')}") if scene else "(nowhere in particular)"
        user = (
            f"TIME: {self.clock.both()}\n"
            f"WHERE SHE IS: {scene_txt}\n"
            f"HOW SHE IS: {self.state.mood_tags()}\n\n"
            f"WHAT SHE KNOWS AND MAY NOT ADMIT KNOWING:\n{item.get('what', '')}\n"
            f"(she found this by {self._how(item)}; it has been {(self.clock.now_ts() - float(item['ts'])) / 86400.0:.1f} days)\n"
            f"WHAT IT COST HER: {', '.join(t.get('belief', '') for t in item.get('touched', []) or []) or 'nothing she can name'}\n\n"
            f"WHAT SHE HAS ALREADY TRIED ON THIS:\n{prior_txt}\n\n"
            f"THE PEOPLE AROUND HER:\n{rels}\n\n"
            f"THE LAST THINGS SAID BETWEEN THEM:\n{chat}"
        )
        messages = [{"role": "system", "content": self.config.prompt_text("approach")},
                    {"role": "user", "content": user}]
        data, raw = self.llm.call_json("approach", messages)
        if not isinstance(data, dict) or not str(data.get("subject", "")).strip():
            logger.log("[approach] the call named nothing for her to get at")
            return None
        return {"subject": str(data["subject"]).strip()[:200],
                "angle": str(data.get("angle", ""))[:200],
                "risk": max(0, min(3, int(data.get("risk", 1) or 1)))}

    def _how(self, item):
        return {"snoop": sight.w(self.config, "approach_source_snoop"),
                "digest": sight.w(self.config, "approach_source_digest"),
                "x": "his account"}.get(item.get("source", ""), sight.w(self.config, "approach_source_default"))

    # ---------------- what it costs and what it releases ----------------

    def note(self, item, out):
        """Record it, discharge some of the thing, and let the pressure down.

        This is the outlet that was missing. `unsaid` had two releases -- the
        diary at about 10 a day and an X post that the posting model kept
        refusing, on the grounds that everything underneath was the thing she
        must not say -- so it sat pinned at 100 for hours at a stretch, and a
        gauge at its ceiling signals nothing."""
        c = self.config.approach
        now = self.clock.now_ts()
        row = {"ts": now, "date": self.clock.date_str(), "key": self._key(item),
               "subject": out["subject"], "angle": out.get("angle", ""), "risk": out.get("risk", 1),
               "what": item.get("what", "")[:200]}
        log = self._log()
        log.append(row)
        self.store.set("approaches", log[-c.keep:])

        # the thing is part-said now: not resolved, but not sitting whole either
        items = self.store.get("charged", [])
        for it in items:
            if self._key(it) == self._key(item):
                before = float(it.get("charge", 0) or 0)
                it["charge"] = round(before * (1.0 - c.discharge), 1)
                it["approached"] = int(it.get("approached", 0)) + 1
                break
        self.store.set("charged", items)

        if "unsaid" in self.state.gauges:
            live = float(item.get("live", item.get("charge", 0)) or 0)
            relief = min(c.unsaid_relief_max, c.unsaid_relief_base + live * c.unsaid_relief_per_charge)
            self.state.gauges["unsaid"] = max(0.0, self.state.gauges["unsaid"] - relief)
        else:
            relief = 0.0
        # reaching for it costs her: she has just steered a conversation
        # somewhere she is not allowed to be, and she knows it
        self.state._warm("awkwardness", c.awkward_per_risk * out.get("risk", 1), c.awkward_soft_cap)
        if out.get("risk", 1) >= c.risk_shame_from:
            self.state._warm("shame", c.shame_on_close_call, c.shame_soft_cap)
        self.state.save()
        logger.log(f"[approach] she went at it sideways (risk {out.get('risk', 1)}, unsaid -{relief:.0f}): "
                   f"{out['subject'][:140]}")
        return row

    # ---------------- the report ----------------

    def report(self):
        log = self._log()
        # never short-circuit on an empty log: the question this answers is
        # "what is she sitting on and why has she not gone near it", and that
        # is most worth asking before she ever has
        out = [f"{len(log)} approach(es) on record" if log else "she has never gone near any of it"]
        for a in log[-8:]:
            out.append(f"  [{a.get('date')}] risk {a.get('risk')} — {(a.get('subject') or a.get('line', ''))[:110]}")
            if a.get("angle"):
                out.append(f"      angle: {a['angle'][:100]}")
        sealed = self.ick.carrying() if self.ick else []
        out.append("")
        out.append("sealed and still whole:")
        for it in sealed:
            n = len(self._for(it))
            out.append(f"  live {it.get('live', 0):5.1f}  gone at it {n} time(s)  {it.get('what', '')[:76]}")
        item, why = self.due()
        out.append("")
        out.append(f"right now: {why}")
        return "\n".join(out)
