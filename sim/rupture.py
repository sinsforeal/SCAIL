import logger
from sim import chattext
from sim import wiring

# Rupture and repair: the thing a relationship is actually made of.
#
# Before this, a fight healed by the passage of time. `guilt` decayed at 4 an
# hour toward a baseline of 10, `tension` drifted back down on its own, and
# `intent` could return `make_up` with nothing behind it -- so twenty-five hours
# of silence repaired a row exactly as well as an apology did, and better than a
# failed apology. Nothing in this relationship could be broken, which is why
# nothing in it could be earned.
#
# The psychology is not that closeness survives rupture. It is that **repair is
# what builds the bond**: a pair who have broken something and mended it are
# closer than a pair who never broke anything, and the mending is the whole of
# the difference. So:
#
#   - Time does not repair. While one is open, the gauges that carry it are
#     held off their decay (`State.decay`), so the day does not quietly file it
#     away. What time does is turn an open rupture into a scar.
#   - A repair has to be **performed**, by somebody, and it can **fail**. A
#     bid she makes that he does not take is worse than not having made it --
#     that is what makes making one cost something.
#   - Who broke it decides who owes the repair. Hers is guilt and she should
#     move; his is hurt and she waits, which is the harder one for her.
#   - Repaired, closeness ends up **above** where it started. Scarred, it ends
#     below and stays there, because cast meters have no gravity: nothing pulls
#     them back on its own.
#
# Code decides when (a jump in the gauges that carry a break, following
# something that was said), the model decides what it was and whether the thing
# that just happened has mended it.


class Ruptures:
    WIRES = ('primitives',)
    def __init__(self, config, llm, store, clock, state, records=None, self_model=None, self_memory=None,
                 sentiments=None, typesafe=None):
        self.config = config
        self.llm = llm
        self.store = store
        self.clock = clock
        self.state = state
        self.records = records
        self.self_model = self_model
        self.self_memory = self_memory
        self.sentiments = sentiments
        # The hosted classifier (`typesafe.py`, `docs/system-one.md`): when her
        # config turns the `rupture_settle` use on, one `choice` says whether
        # what just happened mended the rupture, made it worse, or left it
        # alone. The `note` and `by` stay the role's, so the role is still
        # called and only the outcome is overridden.
        self.typesafe = typesafe
        wiring.declare(self)

    def _outcome_typesafe(self, user):
        """Jev's outcome for this settling, or None when it cannot answer above
        the use's floor."""
        ts = self.typesafe
        if ts is None or not ts.ready("rupture_settle"):
            return None
        use = ts.use("rupture_settle") or {}
        floor = float(use.get("threshold", 0.5))
        questions = {"outcome": {
            "type": "choice",
            "instructions": "Has what just happened mended the rupture, or made it worse, or borne "
                            "on it at all? Time passing on its own is never `mended`: an unmended "
                            "rupture settles in rather than healing. Warmth is not repair when the "
                            "thing was hers -- if she broke it, being let off is not the same as "
                            "being forgiven.",
            "criteria": {
                "mended": "it is actually fixed: somebody addressed the thing or made it not matter, "
                          "and the other took it. Merely talking again is not mended.",
                "tried": "somebody made a real move at it and it did not land. Not neutral: a bid "
                         "nobody takes leaves the bidder worse off.",
                "worse": "what just happened made it bigger.",
                "nothing": "nothing that just happened bears on it either way. The commonest "
                           "answer."}}}
        answers = ts.ask("rupture_settle", {"the rupture and everything said since": user}, questions)
        if not answers:
            return None
        v, conf = ts.choice(answers, "outcome")
        if v in ("mended", "tried", "worse", "nothing") and conf is not None and conf >= floor:
            logger.log(f"[rupture] typesafe: {v} (conf {conf:.2f})")
            return v
        return None

    # ---------------- access ----------------

    def all(self):
        return self.store.get("ruptures", [])

    def save(self, rows):
        self.store.set("ruptures", rows[-self.config.rupture.max_kept:])

    def open_one(self):
        for r in self.all():
            if r.get("state") == "open":
                return r
        return None

    def scars(self):
        return [r for r in self.all() if r.get("state") == "scarred"]

    # ---------------- noticing one ----------------

    def check(self, deltas, his_message, her_message=""):
        """Did something just break. Mechanical: a jump in the gauges that carry
        a break, in a tick that had something said in it. A rupture is not a bad
        mood -- it needs an exchange behind it."""
        c = self.config.rupture
        if not c.enabled or self.open_one():
            return None
        if not (his_message or her_message):
            return None
        # What breaks is being let in. Nothing a person she has not admitted
        # does can rupture anything, because there is nothing there to break --
        # she can be frightened by him, or angry at him, and neither is a
        # rupture. `sim/primitives.py`, docs §3.
        prim = self.primitives
        if prim is not None and not prim.can_rupture(self.state._him_key() or "him"):
            return None
        d = {k: float(v) for k, v in (deltas or {}).items() if isinstance(v, (int, float))}
        score = (max(0.0, d.get("anger", 0)) * c.anger_weight
                 + max(0.0, d.get("guilt", 0)) * c.guilt_weight
                 + max(0.0, d.get("shame", 0)) * c.shame_weight
                 + max(0.0, d.get("sadness", 0)) * c.sadness_weight)
        if score < c.min_score:
            return None
        return self.name(score, his_message, her_message)

    def name(self, score, his_message, her_message=""):
        """One call: what broke, and whose it was."""
        c = self.config.rupture
        msgs = self.store.recent_messages(c.messages_shown)
        chat = chattext.lines(msgs, self.clock, chars=220) or "(nothing)"
        scars = "\n".join(f"- {r['date']}: {r.get('what', '')}" for r in self.scars()[-c.scars_shown:]) or "(none)"
        user = (
            f"NOW: {self.clock.both()}\nHOW SHE IS: {self.state.mood_tags()}\n"
            f"BETWEEN THEM: {self.state.relationships.get(self.state._him_key() or 'him', {})}\n\n"
            f"WHAT WAS JUST SAID:\n{chat}\n\n"
            f"THINGS BETWEEN THEM THAT WERE NEVER MENDED:\n{scars}\n"
        )
        messages = [{"role": "system", "content": self.config.prompt_text("rupture")},
                    {"role": "user", "content": user}]
        data, raw = self.llm.call_json("rupture", messages)
        if not isinstance(data, dict) or not str(data.get("what", "")).strip():
            logger.log("[rupture] the gauges moved but nothing came back")
            return None
        if not data.get("broke"):
            logger.log(f"[rupture] not a break, just a bad moment: {str(data.get('what', ''))[:80]}")
            return None
        whose = str(data.get("whose", "unclear")).strip().lower()
        if whose not in ("hers", "his", "both", "unclear"):
            whose = "unclear"
        rows = self.all()
        now = self.clock.now_ts()
        r = {"id": f"{self.clock.date_str()}-{len(rows)}",
             "date": self.clock.date_str(), "ts": now,
             "what": str(data["what"])[:220], "whose": whose,
             "severity": max(1, min(5, int(data.get("severity", 2) or 2))),
             "state": "open", "attempts": [], "last_ts": now}
        rows.append(r)
        self.save(rows)
        self._on_open(r)
        logger.log(f"[rupture] something broke ({whose}, severity {r['severity']}): {r['what'][:90]}")
        self.store.add_event(now, self.clock.date_str(), "rupture",
                             f"(she would not call it this) it is not right between them: {r['what']}",
                             c.event_salience)
        return r

    def _on_open(self, r):
        c = self.config.rupture
        # a scar makes the next one land harder and quicker: that is what an
        # unmended thing does to a pair
        prior = len(self.scars())
        scale = 1.0 + min(c.scar_scale_cap, prior * c.scar_scale_per)
        self.state._him_tension(c.tension_per_severity * r["severity"] * scale)
        if r["whose"] in ("hers", "both"):
            self.state._warm("guilt", c.guilt_per_severity * r["severity"], c.guilt_soft_cap)
        self.state.save()

    # ---------------- mending one ----------------

    def settle(self, trigger):
        """Something happened that could have mended it. `trigger` says what:
        `his_message`, `her_message`, or `day`."""
        c = self.config.rupture
        r = self.open_one()
        if not (c.enabled and r):
            return None
        now = self.clock.now_ts()
        # Gate on there being something new to judge, not on a clock. A time
        # gap measured from the break would skip a fast repair, and a fast
        # repair is the best kind there is.
        if trigger != "day":
            # either side: his bid can mend it and so can her taking one. Only
            # watching his messages meant a rupture he had already apologised
            # for stayed open until it scarred, because her accepting it was
            # not a thing that could be noticed.
            newest = max([m["ts"] for m in self.store.recent_messages(20)] or [0])
            if newest <= float(r.get("settle_ts", 0)) or newest <= float(r["ts"]):
                return None
        msgs = [m for m in self.store.recent_messages(c.messages_shown) if m["ts"] >= float(r["ts"]) - 600]
        chat = chattext.lines(msgs, self.clock, chars=220) or "(nothing since)"
        tries = "\n".join(f"- {self.clock.hm(a['ts'])} by {a['by']}: {a.get('note', '')}" for a in r.get("attempts", [])) or "(none)"
        hours = (now - float(r["ts"])) / 3600.0
        user = (
            f"WHAT BROKE, {hours:.1f} HOURS AGO: {r['what']}\n"
            f"WHOSE IT WAS: {r['whose']}\nHOW BAD: {r['severity']} of 5\n"
            f"REPAIRS TRIED SO FAR:\n{tries}\n\n"
            f"EVERYTHING SAID SINCE IT BROKE:\n{chat}\n\n"
            f"WHAT JUST HAPPENED: {trigger}\n"
        )
        messages = [{"role": "system", "content": self.config.prompt_text("rupture_settle")},
                    {"role": "user", "content": user}]
        data, raw = self.llm.call_json("rupture_settle", messages)
        if not isinstance(data, dict):
            return None
        outcome = str(data.get("outcome", "")).strip().lower()
        # The classifier's outcome stands over the role's when it answers above
        # its floor; `note` and `by` stay the role's.
        jout = self._outcome_typesafe(user)
        if jout:
            outcome = jout
        note = str(data.get("note", ""))[:180]
        by = str(data.get("by", "")).strip().lower()
        if outcome not in ("mended", "tried", "worse", "nothing"):
            return None
        rows = self.all()
        for row in rows:
            if row.get("id") != r["id"]:
                continue
            row["last_ts"] = now
            row["settle_ts"] = now
            if outcome == "nothing":
                self.save(rows)
                return None
            row["attempts"] = (row.get("attempts", []) + [{"ts": now, "by": by or "unclear",
                                                           "outcome": outcome, "note": note}])[-8:]
            if outcome == "mended":
                row["state"] = "mended"
                row["mended_on"] = self.clock.date_str()
                row["mended_by"] = by or "unclear"
                self._on_mended(row, note)
            elif outcome == "tried":
                self._on_failed(row, by, note)
            elif outcome == "worse":
                row["severity"] = min(5, int(row.get("severity", 2)) + 1)
                self._on_worse(row, note)
            self.save(rows)
            return row
        return None

    def _on_mended(self, r, note):
        """The payoff, and the reason the whole thing exists. Closeness ends up
        **above** where it was: a pair who have broken something and mended it
        are closer than a pair who never broke anything."""
        c = self.config.rupture
        k = self.state._him_key()
        if k:
            rel = self.state.relationships[k]
            rel["closeness"] = min(100.0, float(rel.get("closeness", 50)) + c.closeness_on_mend * r["severity"])
            rel["tension"] = max(0.0, float(rel.get("tension", 0)) - c.tension_off_on_mend * r["severity"])
        self.state._settle("guilt", c.guilt_off_on_mend * r["severity"])
        self.state._warm("relief", c.relief_on_mend, c.relief_soft_cap)
        # the largest release there is: an unmended thing is the heaviest single
        # term in the load, and mending it takes that term off
        _st = getattr(self.state, "stress", None)
        if _st:
            _st.relieve("rupture_mended")
        self.state.save()
        # and it changes what he is to her, which is the part that lasts
        if self.sentiments:
            sc = self.config.sentiment
            who = self.state._him_key() or "him"
            self.sentiments.move(who, "attachment", sc.mend_attachment * r["severity"], "they got past something")
            self.sentiments.move(who, "respect", sc.mend_respect * r["severity"], "he came through")
        logger.log(f"[rupture] mended by {r.get('mended_by')} after "
                   f"{(self.clock.now_ts() - float(r['ts'])) / 3600:.1f}h: {note[:90]}")
        self.store.add_event(self.clock.now_ts(), self.clock.date_str(), "rupture",
                             f"they got past it, and it is better than it was before: {note or r['what']}",
                             c.event_salience)
        if self.self_memory and self.config.self_memory.enabled:
            self.self_memory.add(self.clock.date_str(), note or f"They got past it: {r['what']}",
                                 c.memory_weight_mend, "warm about it, and a bit wrung out", source="rupture")

    def _on_failed(self, r, by, note):
        """A bid nobody took. This is the one that has to hurt, or making one
        costs nothing and she would make them all day."""
        c = self.config.rupture
        if by == "hers":
            self.state._warm("shame", c.shame_on_failed_bid, c.shame_soft_cap)
            self.state._warm("sadness", c.sadness_on_failed_bid, c.sadness_soft_cap)
            self.state._him_tension(c.tension_on_failed_bid)
            self.state.save()
            if self.sentiments:
                self.sentiments.move(self.state._him_key() or "him", "resentment",
                                     self.config.sentiment.failed_bid_resentment, "he did not take it")
            logger.log(f"[rupture] she tried and it did not land: {note[:90]}")
        else:
            logger.log(f"[rupture] he made a move at it and it is not mended yet: {note[:90]}")

    def _on_worse(self, r, note):
        c = self.config.rupture
        self.state._him_tension(c.tension_per_severity)
        self.state._warm("anger", c.anger_on_worse, c.anger_soft_cap)
        self.state.save()
        logger.log(f"[rupture] it got worse (severity {r['severity']}): {note[:90]}")

    def age(self):
        """What time actually does: it does not mend anything, it turns an open
        thing into a scar. Cast meters have no gravity, so what this takes off
        closeness stays off."""
        c = self.config.rupture
        r = self.open_one()
        if not (c.enabled and r):
            return None
        hours = (self.clock.now_ts() - float(r["ts"])) / 3600.0
        if hours < c.scar_after_hours:
            return None
        rows = self.all()
        for row in rows:
            if row.get("id") != r["id"]:
                continue
            row["state"] = "scarred"
            row["scarred_on"] = self.clock.date_str()
            self.save(rows)
            k = self.state._him_key()
            if k:
                rel = self.state.relationships[k]
                rel["closeness"] = max(0.0, float(rel.get("closeness", 50)) - c.closeness_on_scar * row["severity"])
            self.state.save()
            if self.sentiments:
                self.sentiments.move(self.state._him_key() or "him", "resentment",
                                     self.config.sentiment.scar_resentment * row["severity"],
                                     "they never sorted it out")
            logger.log(f"[rupture] nobody ever fixed it, so it is just a thing between them now: {row['what'][:80]}")
            self.store.add_event(self.clock.now_ts(), self.clock.date_str(), "rupture",
                                 f"(never said out loud) they never did sort this out: {row['what']}",
                                 c.event_salience)
            if self.self_memory and self.config.self_memory.enabled:
                self.self_memory.add(self.clock.date_str(), f"They never sorted this out: {row['what']}",
                                     c.memory_weight_scar, "still sore", source="rupture")
            return row
        return None

    # ---------------- what it holds open ----------------

    def holds(self):
        """Gauges that must not decay while something is open. This is the whole
        of "time does not repair": without it a day of saying nothing files a
        row away as neatly as an apology does."""
        c = self.config.rupture
        if not (c.enabled and self.open_one()):
            return ()
        return tuple(c.holds_gauges)

    # ---------------- where it shows up ----------------

    def prompt_text(self):
        from sim.lang import say
        t = say(self.config)
        c = self.config.rupture
        r = self.open_one()
        scars = self.scars()[-c.scars_in_prompt:]
        parts = []
        if r:
            hours = (self.clock.now_ts() - float(r["ts"])) / 3600.0
            whose = ({"hers": "自分がやったことで、それは分かっている",
                      "his": "やったのは彼のほう",
                      "both": "二人ともやった",
                      "unclear": "どちらが始めたのかも分からない"}
                     if t(False, True) else
                     {"hers": "you were the one who did it, and you know it",
                      "his": "he was the one who did it",
                      "both": "you both did it",
                      "unclear": "you are not even sure which of you started it"}).get(r["whose"], "")
            tried = len([a for a in r.get("attempts", []) if a.get("by") == "hers"])
            tail = ""
            if tried:
                tail = t(f" You have had a go at fixing it {tried} time{'s' if tried != 1 else ''} and it has not "
                         f"taken, which is worse than not having tried.",
                         f" 直そうとして{tried}回やってみて、うまくいっていない。やらなかったよりも悪い。")
            parts.append("\n\n" + t("## Something is not right between you and him",
                                    "## 彼とのあいだで、うまくいっていないことがある") + "\n"
                         + t(f"- {r['what']} ({whose}; about {int(hours)} hour(s) ago). It is not fixed and it is not "
                             f"going to fix itself.{tail}",
                             f"- {r['what']}（{whose}、およそ{int(hours)}時間前）。直っていないし、放っておいて直るものでもない。{tail}"))
        if scars:
            parts.append("\n\n" + t("## Things between you and him that never got sorted out",
                                    "## 彼とのあいだで、最後まで片づかなかったこと") + "\n"
                         + "\n".join(f"- {s['date'][5:]}: {s['what']}" for s in scars))
        return "".join(parts)

    def intent_line(self):
        r = self.open_one()
        if not r:
            return ""
        if r["whose"] in ("hers", "both"):
            return ("something is broken between them and she is the one who did it -- `make_up` is what this is "
                    "for, and she is bad at it: she goes around the houses rather than saying the thing")
        return ("something is broken between them and he is the one who did it. She wants it fixed and she is not "
                "going to be the one to say so, which is what `nothing`, `check_on` and a pointed `tease` are for")

    def report(self):
        rows = self.all()
        r = self.open_one()
        lines = [f"{len(rows)} on record: {sum(1 for x in rows if x.get('state') == 'mended')} mended, "
                 f"{len(self.scars())} never sorted, {'1 open' if r else 'nothing open'}"]
        for x in rows[-12:]:
            hours = (self.clock.now_ts() - float(x["ts"])) / 3600.0
            lines.append(f"\n  [{x['id']}] {x.get('state')}  {x['whose']}  severity {x.get('severity')}  "
                         f"{hours:.1f}h ago")
            lines.append(f"     {x.get('what', '')}")
            for a in x.get("attempts", []):
                lines.append(f"     {self.clock.hm(a['ts'])} {a['by']} -> {a['outcome']}: {a.get('note', '')[:90]}")
        return "\n".join(lines)
