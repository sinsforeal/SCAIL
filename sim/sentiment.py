import math
import logger
from sim import existence

# What a person is to her, as opposed to how she feels this afternoon.
#
# Every emotion in this system is episodic and has no object. `anger` fades in
# seven hours. `affection` is "warm toward him, wanting to be close now" -- a
# state of the evening. The relationship meters (closeness, standing, tension)
# are the other half of the problem: they are bookkeeping over the record and
# nothing about them is felt. So she could be warm at 8pm and neutral at 8am
# with nothing carried across, and `closeness 48` did no felt work at all.
#
# A sentiment is the missing layer: a durable felt orientation toward a named
# person, built out of the emotions she has actually had about them, fading only
# over weeks, and colouring everything that happens with that person. It is what
# you would be answering if somebody asked what he is to you.
#
# Four kinds, and they are the universal ones rather than hers:
#
#   attachment  wanting them near, and distress at their absence
#   resentment  grievance that never got put down
#   respect     they are worth something in her eyes
#   contempt    they are not, and she has stopped hiding it from herself
#
# What makes them hers is entirely what has happened: they are seeded once from
# the meters (four months of talking to him did not happen for nothing) and
# after that they only move on events that carry a person -- a rupture mended
# or scarred, a bid nobody took, his attention, and what the compile makes of
# the day.
#
# They do felt work through three routes rather than sitting in a report:
# `longing` is what attachment feels like at a distance, contagion is scaled by
# attachment (you catch the mood of someone who matters to you, not a
# stranger's), and resentment is subtracted from the impulse and added to the
# delay.

# envy (2026-08-26): what measuring yourself against a person leaves behind;
# written only by tomoe/compare.py, read by the spiral seed and cast_reply
_KINDS = ("attachment", "resentment", "respect", "contempt", "envy")


def seed_row(c, rel, now, owned=False):
    """What one person is to her at the moment the meters are all there is.

    Module level rather than inside the seeding loop because a save whose
    meters were seeded wrong is repaired later, and the row that repair adds
    for a person the seed never had has to be the row the seed would have
    written (`tools/promoted_save_retire.py`). Written twice, the repaired save
    and the fresh one would disagree about the same person."""
    closeness = float((rel or {}).get("closeness", 50))
    standing = float((rel or {}).get("standing", 50))
    tension = float((rel or {}).get("tension", 0))
    return {
        "attachment": 0.0 if owned else round(closeness * c.seed_attachment_from_closeness, 1),
        "resentment": round(tension * c.seed_resentment_from_tension, 1),
        "respect": round(standing * c.seed_respect_from_standing, 1),
        "contempt": 0.0,
        "envy": 0.0,
        "last_ts": now,
    }


def note_phone_use(store, ts, kind="app", keep=400):
    """She physically picked it up and looked at something. Kept as a plain
    ring of timestamps because the only question ever asked of it is "was she
    on her phone while these people were standing there"."""
    rows = store.get("phone_use", [])
    rows.append({"ts": float(ts), "kind": kind})
    store.set("phone_use", rows[-keep:])


class Sentiments:
    def __init__(self, config, store, clock, state, records=None):
        self.config = config
        self.store = store
        self.clock = clock
        self.state = state
        self.records = records
        if not self.store.get("sentiments"):
            self._seed()

    # ---------------- access ----------------

    def all(self):
        return self.store.get("sentiments", {})

    def save(self, rows):
        self.store.set("sentiments", rows)

    def _seed(self):
        """Once, from the meters. Four months of talking to him did not happen
        for nothing, and starting every sentiment at zero would have her meeting
        him again on a save with a hundred days of history in it -- the same
        reasoning as `derive.apply_if_new` and `settle_against_history`."""
        c = self.config.sentiment
        out = {}
        now = self.clock.now_ts()
        prim = getattr(self.state, "primitives", None)
        him = self.state._him_key() or "him"
        for name, rel in (self.state.relationships or {}).items():
            # Four months of talking to him did not happen for nothing -- but
            # for a character the primitives own, four months did not happen at
            # all, and seeding her attachment to him off a meter is how she came
            # to be 67 attached to a man she had exchanged nine messages with.
            owned = prim is not None and name == him
            if self._no_him(self._name(name)):
                continue
            out[name] = seed_row(c, rel, now, owned=owned)
        self.save(out)
        logger.log(f"[sentiment] seeded what {len(out)} people are to her from the meters")

    def _him_names(self):
        """Every key a caller may ask for him under.

        `state._him_key()` returns None when her relationship table has no row
        for him, and every call site then falls back to the literal "him", so
        refusing only the resolved key would refuse nothing. His name on her
        sheet and the two conventions are the whole set, the same three
        `State.him_key_in` looks for."""
        names = {"him", "user"}
        who = str(getattr(getattr(self.config, "character", None), "user_name", "") or "").strip().lower()
        if who:
            names.add(who)
        try:
            k = self.state._him_key() if self.state is not None else None
        except Exception:
            k = None
        if k:
            names.add(str(k).lower())
        return names

    def _no_him(self, name):
        """True when this is a row about him and she has no chat with him.

        A character who exists for somebody else's circle has never spoken to
        him, so there is nothing for this layer to hold about him: the row is
        not opened by a read, not seeded, and not written."""
        if existence.has_chat(self.config):
            return False
        return str(name or "").strip().lower() in self._him_names()

    def _blank(self):
        """An all-zero row that is handed to a reader and never saved."""
        row = {k: 0.0 for k in _KINDS}
        row["last_ts"] = self.clock.now_ts()
        return row

    def _name(self, name):
        """The roster handle these rows are keyed by. A caller holding the
        Japanese record name must not open a SECOND row for somebody who
        already has one: an exchange with 前田亜矢 did exactly that, and the
        empty row sat beside Aya's while every read came back zero."""
        from sim import roster
        return roster.key_of(self.config, name) or str(name or "")

    def get(self, name):
        name = self._name(name)
        if self._no_him(name):
            return self._blank()
        rows = self.all()
        if name not in rows:
            rows[name] = {k: 0.0 for k in _KINDS}
            rows[name]["last_ts"] = self.clock.now_ts()
            self.save(rows)
        return rows[name]

    def him(self):
        return self.get(self.state._him_key() or "him")

    # ---------------- the slow part ----------------

    def live(self, name, kind):
        """Faded to now. Sentiments erode with absence, toward nothing rather
        than toward a baseline: what somebody is to you goes if nothing keeps
        happening, which is the difference between a sentiment and a trait."""
        c = self.config.sentiment
        row = self.get(name)
        half = float(c.half_life_days.get(kind, 60))
        days = max(0.0, (self.clock.now_ts() - float(row.get("last_ts", 0))) / 86400.0)
        return float(row.get(kind, 0.0)) * math.exp(-math.log(2) * days / half)

    def set_level(self, name, kind, value):
        """By hand (the /set command): the level now, as if it had just been
        written; fades from here like any other."""
        name = self._name(name)
        if self._no_him(name):
            return
        rows = self.all()
        row = rows.setdefault(name, {k: 0.0 for k in _KINDS})
        for k in _KINDS:
            row[k] = round(self.live(name, k), 2)
        row["last_ts"] = self.clock.now_ts()
        row[kind] = round(max(0.0, min(self.config.sentiment.ceiling, float(value))), 2)
        rows[name] = row
        self.save(rows)
        logger.log(f"[sentiment] {name} {kind} set by hand -> {row[kind]:.0f}")

    def move(self, name, kind, amount, why=""):
        """A thing that happened with a person, put where it accumulates. Small
        amounts on purpose: a sentiment is a hundred evenings, not one."""
        if kind not in _KINDS or not amount:
            return
        name = self._name(name)
        if self._no_him(name):
            return
        c = self.config.sentiment
        rows = self.all()
        row = rows.setdefault(name, {k: 0.0 for k in _KINDS})
        now = self.clock.now_ts()
        # fade everything to now first, or an old value would take the new
        # amount at full strength on top of a number that should have decayed
        for k in _KINDS:
            row[k] = round(self.live(name, k), 2)
        row["last_ts"] = now
        room = c.ceiling - row.get(kind, 0.0)
        gain = float(amount) * max(0.0, min(1.0, room / max(1.0, c.ceiling)))
        row[kind] = round(max(0.0, min(c.ceiling, row.get(kind, 0.0) + gain)), 2)
        rows[name] = row
        self.save(rows)
        if abs(gain) >= c.log_from:
            logger.log(f"[sentiment] {name} {kind} {'+' if gain > 0 else ''}{gain:.1f} -> {row[kind]:.0f}"
                       + (f" ({why})" if why else ""))

    # ---------------- what it does ----------------

    def _attachment(self, name=None):
        """How attached she is to somebody.

        For the person the primitives own, their figure -- which is attention
        times what losing him would cost, built out of events. This layer's own
        row for him was seeded from a closeness meter no event earned and read
        67 while the events said 1.8, and three readers were acting on it. A
        second history of one person is what the primitives exist to end;
        everybody else is still this layer's, because nothing else holds a
        number for them."""
        him = self.state._him_key() or "him"
        k = self._name(name) if name else him
        prim = getattr(self.state, "primitives", None)
        if prim is not None and k == him:
            return float(prim.attachment(k))
        return self.live(k, "attachment")

    def longing(self, silent_hours):
        """What attachment feels like at a distance, and the reason this girl
        needed the layer at all. `loneliness` is a deficit -- it wants contact,
        any contact, and it drives her at her phone. Longing is about one person
        and it is not entirely unpleasant, and she is in a relationship
        conducted across a great distance with no gauge for missing somebody."""
        c = self.config.sentiment
        a = self._attachment()
        if a < c.longing_needs_attachment:
            return 0.0
        hours = max(0.0, float(silent_hours))
        ramp = min(1.0, hours / max(1.0, c.longing_full_hours))
        return min(100.0, (a / c.ceiling) * ramp * c.longing_scale)

    def susceptibility(self, name=None):
        """How much of somebody's mood she catches. You catch the mood of a
        person who matters to you and not a stranger's, which is what makes this
        a reader of the sentiment layer rather than a constant."""
        c = self.config.sentiment
        a = self._attachment(name)
        return c.contagion_floor + (a / c.ceiling) * (1.0 - c.contagion_floor)

    def impulse_bonus(self):
        """Attachment makes her reach; resentment makes her not. Resentment is
        the second thing in the whole system that can make her reach out less --
        tension was the first and shame the second, and this is the one that
        lasts for weeks."""
        c = self.config.sentiment
        k = self.state._him_key() or "him"
        return (self._attachment() / c.ceiling * c.impulse_attachment
                - self.live(k, "resentment") / c.ceiling * c.impulse_resentment)

    def delay_bonus(self):
        c = self.config.sentiment
        k = self.state._him_key() or "him"
        return self.live(k, "resentment") / c.ceiling * c.delay_resentment

    # ---------------- the other side of the pull ----------------

    def peers(self):
        """The circle, which is not the family. Belonging is about the people
        who could leave you out -- her own named fear is being excluded at
        break, not at dinner -- and you belong to a family whether it is going
        well or not. `role_id` on the cast already carries the distinction."""
        fam = set(self.config.sentiment.family_roles)
        out = []
        for name, rel in (self.state.relationships or {}).items():
            if name == (self.state._him_key() or "him"):
                continue
            if str(rel.get("role_id", "")) in fam:
                continue
            out.append(name)
        return out

    def last_circle_contact(self):
        """When she was last actually among them. A scene carries a timestamp
        and who she was with; a message from one of them counts too."""
        peers = set(self.peers())
        best = 0.0
        with self.store.lock:
            rows = self.store.conn.execute(
                "SELECT ts, with_who FROM scenes ORDER BY ts DESC LIMIT 400").fetchall()
        for r in rows:
            who = (r["with_who"] or "").lower()
            if who and who != "alone" and any(p.split("-")[0].lower() in who for p in peers):
                best = max(best, float(r["ts"]))
                break
        # and a message from one of them, at day resolution -- cast_chat keeps
        # date and hm and no timestamp, and the clock has no parse
        today = self.clock.date_str()
        for x in self.store.get("cast_chat", [])[-30:]:
            if x.get("who") not in peers:
                continue
            try:
                import datetime
                days = (datetime.date.fromisoformat(today) - datetime.date.fromisoformat(x["date"])).days
            except Exception:
                continue
            if days < 0:
                continue
            hh, mm = 12, 0
            try:
                hh, mm = [int(p) for p in (x.get("hm") or "12:00").split(":")[:2]]
            except Exception:
                pass
            now = self.clock.now()
            ts = self.clock.now_ts() - days * 86400 - max(0, (now.hour - hh) * 3600 + (now.minute - mm) * 60)
            best = max(best, ts)
        return best

    def belonging(self):
        """How held she is by the circle right now, which is the counterweight
        to him. `longing` is attachment to one person times his absence; this is
        her standing with the group times how recently they had her, and the two
        of them compete for the same need. Nothing did this before: the impulse
        had ten weights and not one about the people she spends her day with, so
        an evening where the group was good to her left her wanting him exactly
        as much as an evening where they were not."""
        c = self.config.sentiment
        peers = self.peers()
        if not peers:
            # Nobody who could leave her out, so there is nothing to read. The
            # floor was being returned instead, which cleared the tag threshold
            # of 22 and put "on the outside of them lately" permanently into a
            # line that holds five feelings -- and handed the impulse and the
            # stress load a constant to act on. None is the honest answer and
            # the writer skips it.
            return None
        num = den = 0.0
        for p in peers:
            w = max(1.0, self.live(p, "attachment"))
            num += float((self.state.relationships.get(p) or {}).get("standing", 50)) * w
            den += w
        base = num / max(1.0, den)
        last = self.last_circle_contact()
        hours = max(0.0, (self.clock.now_ts() - last) / 3600.0) if last else 999.0
        keep = 0.5 ** (hours / max(1.0, c.belonging_half_life_hours))
        return max(0.0, min(100.0, base * (c.belonging_floor + (1.0 - c.belonging_floor) * keep)))

    def phone_debt(self, date):
        """What being on her phone with him costs her with them.

        Rena's own sheet says being caught on her phone stings and Hinako's says
        she catches the phone habits, and neither of them could ever notice --
        `influence` reaches the beat writer and nothing else. Mechanical and
        from the record: her messages to him that landed while a scene had
        people in it. Cast meters have no gravity, so what this takes off
        standing stays off."""
        c = self.config.sentiment
        if not c.phone_debt_enabled:
            return {}
        # Once per date. This is the only thing the compile does to the record
        # that ADDS UP rather than replaces, so a day compiled twice docked her
        # friends twice for the same afternoon on her phone.
        done = list(self.store.get("phone_debt_done", []) or [])
        if date in done:
            return {}
        self.store.set("phone_debt_done", (done + [date])[-90:])
        with self.store.lock:
            scenes = self.store.conn.execute(
                "SELECT ts, with_who FROM scenes WHERE date=? ORDER BY ts", (date,)).fetchall()
        # Everything that counts as being on it in front of them: what she
        # sent, and every time she picked it up. Counting only sends charged
        # her nothing for the afternoon Hinako twice said it out loud, because
        # she was checking rather than typing -- which is the thing people
        # actually notice.
        day0 = min((float(s["ts"]) for s in scenes), default=0.0)
        day1 = max((float(s["ts"]) for s in scenes), default=0.0) + 3600.0
        moments = [float(m["ts"]) for m in self.store.messages_for_date(date) if m["role"] != "user"]
        moments += [float(u.get("ts", 0)) for u in self.store.get("phone_use", [])
                    if day0 <= float(u.get("ts", 0)) <= day1]
        if not (scenes and moments):
            return {}
        peers = self.peers()
        caught = {}
        for ts in sorted(moments):
            who = ""
            for s in scenes:
                if float(s["ts"]) <= ts:
                    who = (s["with_who"] or "").lower()
                else:
                    break
            if not who or who == "alone":
                continue
            for p in peers:
                if p.split("-")[0].lower() in who:
                    caught[p] = caught.get(p, 0) + 1
        out = {}
        for p, count in caught.items():
            over = count - c.phone_debt_free
            if over <= 0:
                continue
            cost = min(c.phone_debt_max, over * c.phone_debt_per_message)
            rel = self.state.relationships.get(p)
            if not rel:
                continue
            rel["standing"] = max(0.0, float(rel.get("standing", 50)) - cost)
            out[p] = (count, round(cost, 1))
            logger.log(f"[circle] {p} noticed her attention was on him {count} time(s) (sent or picked it up) "
                       f"while they were there; "
                       f"standing -{cost:.1f}")
        if out:
            self.state.save()
        return out

    # ---------------- where it shows up ----------------

    def prompt_text(self):
        c = self.config.sentiment
        lines = []
        from sim.lang import say
        t = say(self.config)
        ranked = sorted(self.all(), key=lambda p: -max(self.live(p, k) for k in _KINDS))
        for name in ranked[: c.max_in_prompt]:
            bits = []
            for kind in _KINDS:
                v = self.live(name, kind)
                if v < c.prompt_from:
                    continue
                # the item lines, not only the heading: under the heading in
                # her own language these were still English, so what a person
                # is to her was the one thing in the section she had to
                # translate before she could feel it
                how = t("a bit ", "少し") if v < 45 else t("", "") if v < 72 else t("a great deal ", "かなり")
                bits.append({
                    "attachment": t(f"{how}attached to {name}", f"{name}に{how}なついている"),
                    "resentment": t(f"{how}carrying something against {name}",
                                    f"{name}に対して{how}引っかかっているものを抱えている"),
                    "respect": t(f"{how}looking up to {name}", f"{name}を{how}すごいと思っている"),
                    "contempt": t(f"{how}contemptuous of {name}", f"{name}を{how}見下している"),
                    "envy": t(f"{how}measuring yourself against {name} and coming off worse",
                              f"{name}と{how}自分を比べて、負けていると感じている"),
                }[kind])
            if bits:
                lines.append(t("- you are " + ", and ".join(bits),
                               "- " + "、そして".join(bits)))
        if not lines:
            return ""
        return ("\n\n" + t(
            "## What these people are to you (not how you feel today; what they are. "
            "You have never put any of it in words)",
            "## この人たちがあなたにとって何なのか（今日どう感じているかではなく、何であるか。"
            "言葉にしたことは一度もない）") + "\n" + "\n".join(lines))

    def report(self):
        c = self.config.sentiment
        rows = self.all()
        lines = [f"{len(rows)} people, faded to now (half-lives in days: {dict(c.half_life_days)})",
                 "person".ljust(14) + "".join(k[:11].rjust(12) for k in _KINDS)]
        for name in rows:
            lines.append(name[:14].ljust(14) + "".join(f"{self.live(name, k):12.1f}" for k in _KINDS))
        lines.append("")
        if existence.has_chat(self.config):
            lines.append(f"him: susceptibility to his mood {self.susceptibility():.2f}, "
                         f"impulse {self.impulse_bonus():+.1f}, delay {self.delay_bonus():+.2f}")
            for h in (0, 6, 12, 24, 48):
                lines.append(f"  longing after {h:2d}h of silence: {self.longing(h):5.1f}")
        else:
            lines.append("him: no chat with him, so this layer holds nothing about him")
        last = self.last_circle_contact()
        ago = (self.clock.now_ts() - last) / 3600.0 if last else None
        lines.append(f"circle: {', '.join(self.peers())}")
        lines.append(f"  last among them {(f'{ago:.1f}h ago' if ago is not None else 'no record')}; belonging {self.belonging():.1f}")
        return "\n".join(lines)
