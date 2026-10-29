import logger
from sim import chattext
from sim import lang
from sim import wiring
from sim.episodes import EpisodeLog

# How far back the hand-back looks for the message a silence was about.
# Her last words to him and the hold that followed them are inside a
# handful of messages; a window rather than the whole record keeps the
# question local to the exchange it belongs to.
HAND_BACK_SCAN = 40

# Not answering, on purpose.
#
# Everything that made her slow was mechanical and none of it was a decision.
# `delay_factor` stretches the wait when she is tense or tired or low, the
# glance roll sometimes leaves a message for a free moment, and the schedule
# takes her phone away -- but in every one of those she is *trying* to answer
# and something is in the way. She could not once look at a message, understand
# it perfectly, and choose to leave it there.
#
# That is most of what a fifteen-year-old does with a phone. Being left on read
# is already modelled on his side: `receipts.py` watches his Telegram window and
# `read_ignored_minutes` feeds her craving, her anxiety and eventually his
# tension. She had no way to do it back.
#
# Two shapes, because they are different weapons and she knows it:
#
#   wait      the message stays pending and she answers it when the hold ends,
#             so her reply is still about what he said. Deniable: she could
#             have been busy, and she decides later whether she meant it.
#
#   silence   the message is consumed while the hold runs. She has read it,
#             her reply queue does not have it any more, and the next thing
#             she says is about something else -- which is the loudest thing
#             she can do without saying a word. The hour of having read him
#             and said nothing is what cannot be taken back; the message
#             itself goes back to her, once, if the hold runs out and he has
#             still written nothing (`_hand_back`).
#
# The first draft of this claimed he would see a read receipt. He does not:
# `store.mark_read` is her side only and the Telegram Bot API has no such
# thing. What makes `silence` land is the unanswered question, not a tick.
#
# Code decides whether the pressure is there; a call decides which of the two,
# for how long, and what would break it. It costs her the whole time -- holding
# out is work, `unsaid` climbs, and if he is warm at her while she holds, guilt
# does the rest. And it ends: the clock runs out, or he says the thing that
# breaks it, or she caves, which is a message of its own kind.


class Withholding(EpisodeLog):
    WIRES = ('attachment', 'foresight', 'primitives',)
    LOG_KEY = "withholding_log"
    def __init__(self, config, llm, store, clock, state, sentiments=None, ruptures=None, receipts=None):
        self.config = config
        self.llm = llm
        self.store = store
        self.clock = clock
        self.state = state
        self.sentiments = sentiments
        self.ruptures = ruptures
        self.receipts = receipts
        wiring.declare(self)

    # ---------------- the record ----------------

    def live(self):
        """The decision she is currently keeping to, or None."""
        row = self.store.get("withholding")
        if not row or row.get("done"):
            return None
        if self.clock.now_ts() >= float(row.get("until_ts", 0)):
            return None
        return row


    # ---------------- code decides whether there is anything to decide ----------------

    def pressure(self):
        """How much of her wants to leave it there. 0..1ish."""
        c = self.config.withholding
        g = self.state.gauges
        him = self.state.relationships.get(self.state._him_key() or "him", {}) or {}
        # Something worth withholding is something not yet shown. A character
        # he has already read to the bottom has nothing to hold, so this is
        # zero for a reason that can be stated rather than a sum of gauges
        # that happens to be small -- and it wakes on its own the moment she
        # gets one private thing back. `sim/primitives.py`, docs §5.
        prim = self.primitives
        if prim is not None and not prim.can_withhold(self.state._him_key() or "him"):
            return 0.0
        p = 0.0
        tension = float(him.get("tension", 0) or 0)
        p += max(0.0, tension - c.tension_from) / 100.0 * c.weight_tension
        for gauge, key in (("anger", "weight_anger"), ("shame", "weight_shame"),
                           ("sadness", "weight_sadness")):
            over = max(0.0, self.state.over_rest(gauge))
            p += over / 100.0 * getattr(c, key)
        # gone off him: leaving it there is easy when she does not care
        p += max(0.0, c.cold_from - g.get("affection", 50)) / 100.0 * c.weight_cold
        # where she stands with him: unsure of her place she cannot afford a
        # sulk (it comes off), sure of it she can leave him waiting
        standing = float(him.get("standing", 50) or 50)
        p -= max(0.0, c.standing_secure_from - standing) / 100.0 * c.weight_standing_low
        p += max(0.0, standing - c.standing_secure_from) / 100.0 * c.weight_standing_high
        # the one that lasts for weeks rather than hours
        try:
            k = self.state._him_key()
            if self.sentiments and k:
                p += self.sentiments.live(k, "resentment") / 100.0 * c.weight_resentment
        except Exception:
            pass
        try:
            if self.ruptures and self.ruptures.open_one():
                p += c.weight_rupture
        except Exception:
            pass
        # gone cold on purpose: not answering is the strategy itself
        att = self.attachment
        if att:
            p += att.withhold_pressure()
        # and the oldest reason of all: he did it to her first, recently
        try:
            st = self.receipts.status() if self.receipts else None
            if st and st.get("state") == "read" and st.get("read_ts"):
                mins = (self.clock.now_ts() - float(st["read_ts"])) / 60.0
                if mins >= c.tit_for_tat_minutes:
                    p += c.weight_tit_for_tat
        except Exception:
            pass
        return p

    def due(self, unread):
        """(True, why) when she is going to make a decision about answering.

        Everything here is opportunity and cost. Whether the thing he said
        deserves it is the call's business, not this one's."""
        c = self.config.withholding
        if not c.enabled or not unread:
            return False, "off"
        if self.live():
            return False, "already holding"
        now = self.clock.now_ts()
        if now - self._last_ts() < c.min_gap_hours * 3600:
            return False, "too soon after the last time"
        if self._today() >= c.max_per_day:
            return False, "daily cap"
        p = self.pressure()
        if p < c.threshold:
            return False, f"nothing in her wants to (p {p:.2f} of {c.threshold})"
        return True, f"p {p:.2f}"

    # ---------------- the model decides what kind and how long ----------------

    def decide(self, unread, scene=None):
        """Returns the decision row, or None when she just answers."""
        c = self.config.withholding
        text = "\n".join(m["text"] for m in unread)[:1200]
        him = self.state.relationships.get(self.state._him_key() or "him", {}) or {}
        recent = self.store.recent_messages(c.messages_shown)
        chat = chattext.lines(recent, chars=140, labels=("him", "her"), stamps=False)
        stance = ""
        try:
            att = self.attachment
            if att and att.live():
                stance = att.situation_line()
                if att.strategy() == "deactivate":
                    stance += " -- not answering IS what she is doing at the moment; `wait` and `silence` are the shape of it, not a departure from it"
                else:
                    stance += " -- she is pushing at him, so leaving him unanswered would cost her more than it costs him; `answer` unless the message itself earns it"
        except Exception:
            stance = ""
        rup = ""
        try:
            r = self.ruptures.open_one() if self.ruptures else None
            if r:
                rup = f"something is broken between them right now: {r.get('what', '')} (whose: {r.get('whose', '?')})"
        except Exception:
            pass
        user = (
            f"TIME: {self.clock.both()}\n"
            f"WHERE SHE IS: {(scene or {}).get('location', '?')} / {(scene or {}).get('activity', '?')}\n"
            f"HOW SHE IS: {self.state.mood_tags()}\n"
            f"BETWEEN THEM: closeness {him.get('closeness')}, tension {him.get('tension')}\n"
            + (rup + "\n" if rup else "")
            + (f"WHERE SHE STANDS WITH HIM RIGHT NOW: {stance}\n" if stance else "")
            + (f"WHAT SHE EXPECTS OF HIM (her own reading): {self.foresight.intent_line()}\n"
               if self.foresight and self.foresight.intent_line() else "")
            + f"\nWHAT HE JUST SENT:\n{text}\n\nTHE LAST THINGS SAID:\n{chat}"
        )
        messages = [{"role": "system", "content": self.config.prompt_text("withhold")},
                    {"role": "user", "content": user}]
        data, raw = self.llm.call_json("withhold", messages)
        if not isinstance(data, dict):
            return None
        choice = str(data.get("choice", "answer")).strip()
        if choice not in ("wait", "silence"):
            logger.log(f"[withhold] she thought about not answering and answered: {str(data.get('why', ''))[:110]}")
            return None
        try:
            mins = float(data.get("minutes", 0) or 0)
        except (TypeError, ValueError):
            mins = 0.0
        mins = max(c.min_minutes, min(c.max_minutes, mins))
        now = self.clock.now_ts()
        row = {"ts": now, "date": self.clock.date_str(), "kind": choice,
               "until_ts": now + mins * 60, "minutes": round(mins),
               "why": str(data.get("why", ""))[:300],
               "breaks_if": str(data.get("breaks_if", ""))[:200],
               "done": False, "caved": False}
        # a hold still standing when a new one is decided is superseded, not
        # lost -- four rows from 08-25..27 sat `done: False` for a week because
        # the live row was overwritten and only `log[-1]` ever closed
        prev = self.store.get("withholding")
        if prev and not prev.get("done"):
            self._release(prev, "superseded by a new hold")
        self.store.set("withholding", row)
        log = self._log()
        log.append(dict(row))
        self.store.set("withholding_log", log[-c.keep:])
        self.store.add_event(now, self.clock.date_str(), "withhold",
                             ("she read his message and did not answer it" if choice == "silence"
                              else "she left his message sitting there without opening it"), 2)
        logger.log(f"[withhold] {choice} for {mins:.0f} min: {row['why'][:120]}"
                   + (f" | breaks if: {row['breaks_if'][:60]}" if row['breaks_if'] else ""))
        return row

    # ---------------- what it costs while it runs ----------------

    def tick(self):
        """Called every pass. Holding out is work, and it does not last."""
        c = self.config.withholding
        row = self.store.get("withholding")
        if not row or row.get("done"):
            return
        now = self.clock.now_ts()
        if now >= float(row.get("until_ts", 0)):
            self._release(row, f"she has stopped holding out ({row.get('kind')}, {row.get('minutes')} min)",
                          expired=True)
            return
        # the cost, per pass, while she keeps it up
        hours = max(0.0, (now - float(row.get("last_charged", row["ts"]))) / 3600.0)
        if hours < c.charge_every_minutes / 60.0:
            return
        row["last_charged"] = now
        if "unsaid" in self.state.gauges:
            self.state.gauges["unsaid"] = min(100.0, self.state.gauges["unsaid"] + c.unsaid_per_hour * hours)
        self.state._warm("awkwardness", c.awkward_per_hour * hours, c.awkward_soft_cap)
        # and if he has been decent at her while she does it, that is guilt
        try:
            m = self.state.his_mood()
            if m and float(m.get("valence", 0)) > 0:
                self.state._warm("guilt", c.guilt_per_hour * hours, c.guilt_soft_cap)
        except Exception:
            pass
        # the sulk nobody noticed. She meant to be conspicuously not answering
        # and he has gone quiet too, so now she is just sitting in it -- which
        # irks her at him, on top of whatever she was already cross about.
        irk = self.irked()
        if irk > 0:
            self.state._warm("validation_craving", c.irk_craving_per_hour * irk * hours, c.irk_soft_cap)
            self.state._him_tension(c.irk_tension_per_hour * irk * hours)
        self.state.save()
        self.store.set("withholding", row)

    def hold_from_silence(self, why):
        """The persona answered him with nothing and its reasoning said why
        ("let him sit in the read receipt for once"). That is a decision,
        not an error; it becomes a `silence` she keeps for a while instead
        of his message going back in the queue to be answered anyway."""
        c = self.config.withholding
        if self.live():
            return None
        now = self.clock.now_ts()
        mins = float(c.silence_from_empty_minutes)
        row = {"ts": now, "date": self.clock.date_str(), "kind": "silence",
               "until_ts": now + mins * 60, "minutes": round(mins),
               "why": str(why or "")[:300], "breaks_if": "", "done": False, "caved": False}
        # a hold still standing when a new one is decided is superseded, not
        # lost -- four rows from 08-25..27 sat `done: False` for a week because
        # the live row was overwritten and only `log[-1]` ever closed
        prev = self.store.get("withholding")
        if prev and not prev.get("done"):
            self._release(prev, "superseded by a new hold")
        self.store.set("withholding", row)
        log = self._log()
        log.append(dict(row))
        self.store.set("withholding_log", log[-c.keep:])
        self.store.add_event(now, self.clock.date_str(), "withhold", "she read his message and did not answer it", 2)
        logger.log(f"[withhold] she read it and chose not to answer ({int(mins)} min): {row['why'][:120]}")
        return row

    def broken_by(self, text):
        """He said something while she was holding. Does it end it?

        Cheap and deliberate: the model wrote `breaks_if` when it decided, and
        this is a word check against it plus the two things that always work.
        No call -- she is not deliberating, she is reading a message and
        finding she has stopped meaning it."""
        c = self.config.withholding
        row = self.live()
        if not row:
            return False
        low = (text or "").lower()
        if any(w in low for w in c.always_breaks):
            self._release(row, "he said the thing that undid it")
            return True
        cue = (row.get("breaks_if") or "").lower()
        words = [w for w in cue.replace(",", " ").split() if len(w) > 4]
        if words and sum(1 for w in words if w in low) >= c.breaks_if_words:
            self._release(row, "he did the thing she was waiting for")
            return True
        return False

    def unnoticed_hours(self):
        """How long he has been quiet since she started holding out.

        The thing that actually kills a sulk. She is not answering *at* him,
        and it only works if he is there to not be answered. When he goes quiet
        too, the silence stops being hers -- it is just silence, she is sitting
        in it with him, and the whole gesture is wasted on somebody who has not
        noticed."""
        row = self.live()
        if not row:
            return 0.0
        last_him = 0.0
        for m in self.store.recent_messages(60):
            if m["role"] == "user":
                last_him = max(last_him, float(m["ts"]))
        since = max(float(row["ts"]), last_him)
        return max(0.0, (self.clock.now_ts() - since) / 3600.0)

    def resolve(self):
        """How much more the impulse has to clear for her to break her own
        silence, right now.

        This is why withholding is never a lock on her own mouth. She decided
        not to answer; she did not decide to stop wanting things. If she has
        something to say badly enough it comes out anyway, and the longer he
        leaves her holding it the less the silence is worth keeping -- being
        ignored while sulking is worse than not sulking, and she knows it."""
        c = self.config.withholding
        row = self.live()
        if not row:
            return 0.0
        r = c.resolve_base
        # it erodes on its own, and much faster while he is not even there
        held_h = max(0.0, (self.clock.now_ts() - float(row["ts"])) / 3600.0)
        r -= held_h * c.resolve_decay_per_hour
        r -= self.unnoticed_hours() * c.resolve_decay_per_unnoticed_hour
        return max(0.0, r)

    def irked(self):
        """He has not noticed. That is its own injury, and it is not the one
        she was going for."""
        c = self.config.withholding
        h = self.unnoticed_hours()
        if h < c.irk_after_hours:
            return 0.0
        return min(1.0, (h - c.irk_after_hours) / max(0.5, c.irk_full_hours))

    def cave(self):
        """She gave in before she meant to. Its own kind of message."""
        row = self.live()
        if not row:
            return False
        row["caved"] = True
        self._release(row, "she could not keep it up")
        self.state._warm("shame", self.config.withholding.shame_on_cave,
                         self.config.withholding.shame_soft_cap)
        self.state.save()
        return True

    def _hand_back(self, row):
        """His message, back in front of her, when the hold ran out and he
        never wrote. The ids handed back, empty when none was.

        A `silence` marks his message read and consumes it, and while she is
        holding that is the whole shape. When the clock runs out with him
        still quiet, what is left is a message she has read and not answered,
        which is the one thing this project may not do by accident, so it goes
        back into the queue `maybe_reply` reads and she is asked about it again
        -- and may leave it again. Here rather than in
        `App.recover_lost_reply`, which refuses to put one back at boot
        because three restarts on 2026-08-26 each requeued a message she had
        chosen not to answer.

        Nothing goes back if he has written since (the newer message is
        already in front of her), if she caved, or if she has spoken to him
        after it: he is not sitting on an unanswered message then. Once per
        message over every hold there has ever been, kv
        `withholding_handed_back`."""
        c = self.config.withholding
        if row.get("kind") != "silence" or row.get("caved") or not c.silence_hands_back:
            return []
        started = float(row.get("ts") or 0)
        recent = self.store.recent_messages(HAND_BACK_SCAN)
        if any(m["role"] == "user" and float(m["ts"]) > started for m in recent):
            return []
        spoke = max([float(m["ts"]) for m in recent if m["role"] == "assistant"] or [0.0])
        done = list(self.store.get("withholding_handed_back", []) or [])
        ids = [m["id"] for m in recent
               if m["role"] == "user" and m.get("read_ts") and spoke < float(m["ts"]) <= started
               and m["id"] not in done]
        if not ids:
            return []
        for mid in ids:
            self.store.unmark_read(mid)
        self.store.set("withholding_handed_back", (done + ids)[-c.keep:])
        return ids

    def handed_back(self):
        """The hold whose message went back to her, while it is still sitting
        there: gone once she has dealt with it, and gone the moment he writes
        again, because then the newer message is what she is looking at."""
        row = self.store.get("withholding") or {}
        ids = list(row.get("handed_back") or [])
        if not ids or not row.get("done"):
            return None
        unread = {m["id"] for m in self.store.unread_user_messages()}
        if not any(i in unread for i in ids):
            return None
        if any(m["role"] == "user" and m["id"] not in ids
               and float(m["ts"]) > float(row.get("ts") or 0)
               for m in self.store.recent_messages(HAND_BACK_SCAN)):
            return None
        return row

    def _release(self, row, why, expired=False):
        """It is over: he said the thing, she caved, a new decision superseded
        it, or the clock ran out. Only the clock running out can hand his
        message back, so only `tick` passes `expired`."""
        back = self._hand_back(row) if expired else []
        if back:
            row["handed_back"] = back
            why = "ran out with him still quiet; his message goes back to her"
        row["done"] = True
        row["released"] = why
        self.store.set("withholding", row)
        log = self._log()
        hit = next((r for r in reversed(log) if r.get("ts") == row.get("ts")), log[-1] if log else None)
        if hit is not None:
            hit.update({"done": True, "released": why, "caved": row.get("caved", False),
                        "handed_back": bool(back)})
            self.store.set("withholding_log", log)
        logger.log(f"[withhold] over: {why}")

    # ---------------- what she is told ----------------

    def situation_line(self, ja=False):
        row = self.live()
        if not row:
            # the hold is over and his message came back: she is told it is
            # still there and that he has not written since. While the hold
            # RUNS the line below stands, because during it she really is not
            # going to answer.
            back = self.handed_back()
            if not back:
                return ""
            t = lang.pick(ja)
            mins = int(back.get("minutes") or 0)
            return t(f"his message is still sitting there unanswered. you left it {mins} minutes "
                     f"and said nothing, and he has not written since. it is in front of you "
                     f"again: answer it or leave it where it is.",
                     f"彼のメッセージはまだそのまま、返事をしていない。{mins}分放っておいて何も言わなかったし、"
                     f"そのあいだ彼からは何も来ていない。また目の前にある。返すか、このままにしておくか。")
        mins = int((float(row["until_ts"]) - self.clock.now_ts()) / 60.0)
        if row.get("kind") == "silence":
            if ja:
                return (f"彼が言ったことは読んだうえで、それに返事をしないと決めている。{row.get('why', '')} "
                        f"あとで返すつもりもない。何か言うとしたら別のことについてで、"
                        f"それをどう取るかは彼の勝手。")
            return (f"you have read what he said and you are not going to answer it. {row.get('why', '')} "
                    f"you are not going to answer it later either -- if you say something it will be about "
                    f"something else, and he can make of that what he likes.")
        if ja:
            return (f"彼のメッセージがそのままになっていて、まだ返していない。{row.get('why', '')} "
                    f"少ししたら返す。あと{mins}分ほど待たせておく。")
        return (f"his message is sitting there and you have not answered it yet. {row.get('why', '')} "
                f"you will get to it, in a bit -- about {mins} more minute(s) of letting him wait.")

    def report(self):
        log = self._log()
        out = [f"{len(log)} time(s) she has done this on purpose" if log
               else "she has never deliberately left him waiting"]
        for a in log[-8:]:
            out.append(f"  [{a.get('date')}] {a.get('kind')} {a.get('minutes')}min"
                       + ("  CAVED" if a.get("caved") else "")
                       + ("  HANDED BACK" if a.get("handed_back") else "")
                       + f" — {a.get('why', '')[:90]}")
        row = self.live()
        out.append("")
        if row:
            mins = int((float(row["until_ts"]) - self.clock.now_ts()) / 60.0)
            out.append(f"right now: {row.get('kind')}, {mins} min left. breaks if: {row.get('breaks_if', '-')}")
        else:
            ok, why = self.due(self.store.unread_user_messages())
            out.append(f"right now: not holding. {why} (pressure {self.pressure():.2f})")
        return "\n".join(out)
