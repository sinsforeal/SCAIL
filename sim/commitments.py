# -*- coding: utf-8 -*-
import datetime
from sim import wiring
import re

import logger
from sim import roster
from world.clock import hm_to_minutes

# A promise to a named person that stakes something outside her head.
#
# Everything that could fail before this cost a gauge or a belief: a missed
# goal strained an anchor, a bad day moved mood. Money existed but no want
# ever drew on it, and the cast meters only moved after the fact. So nothing
# was ever *put down first* -- she could not lose anything she had not
# already lost. This is the object that changes that: made in an exchange
# ("約束したじゃん"), it reserves yen from her allowance, claims a window the
# schedule must honour, and puts her standing with that person on the table.
#
# Three rules keep it a stake rather than a tag:
# - The model NAMES, code BINDS. The commit call reads an exchange and says
#   what she agreed to; it becomes a commitment only with a cast counterparty
#   and a real date inside the horizon, capped per day. "Let's hang out
#   sometime" binds nothing.
# - It is settled from the record only, once, and never reversed. An
#   `attend` is kept if a scene on the day had her with that person in the
#   window; a `buy` is kept if the money log shows the spend. Nothing the
#   narrator claims counts (rule 14).
# - Both outcomes cost. Kept: the yen is actually gone, regard rises.
#   Broken: that person's edge moves (regard down, irritation up), the meter
#   comes off with no gravity, guilt and shame warm, a memory with negative
#   valence is written, and the counterparty's next turn carries it -- they
#   bring it up, not the narrator.
#
# What she does not have covers the scarcity: a promise she cannot fund is
# recorded `funded: false`, and the morning outlook is shown the whole table
# so a want can be about which one to fund.

KINDS = ("attend", "buy", "bring", "send")
# promises to HIM (2026-08-26): the one person who can actually watch her
# keep or break one. Settled off the message record, which is the only
# record his side has: she said she would text by / send / tell, and the
# rows either exist in the window or they do not.
HIM_KINDS = ("text_by", "send", "tell")
# `send` is in both, and the two are settled from different records, so the
# branch is on WHO it was made to and never on the verb. Before this a
# promise to a friend to send something had no verb at all: "send the
# festival photos" bound as an `attend`, was judged on whether a scene had
# her standing next to Rena between 19:00 and 21:00, and was broken on the
# day she actually sent them -- after which the room asked for them for four
# more days (docs/group-chat-audit.md).
_NEEDS_PRESENCE = ("attend", "bring")
_WORD = re.compile(r"[A-Za-z0-9]+")


# "tomorrow" written into the record on Thursday still says tomorrow on
# Friday. `_parse_when` already resolves the WHEN to a real date -- that part
# was right -- but the prose kept the relative word, and everything that reads
# the prose afterwards believes it: the events model turned a promise dated
# 08-28 into a stance for 08-29, so the same promise sat on two days and the
# day it was dated had no block for it. The date field is the record of the
# day; the sentence does not need to say it twice.
_RELATIVE = re.compile(
    r"\s*(?:,\s*)?\b(?:the day after tomorrow|tomorrow(?:\s+(?:morning|afternoon|evening|night))?"
    r"|today|tonight|this (?:morning|afternoon|evening)|later today)\b"
    r"|\s*(?:明後日|明日|今日|今夜|今晩|今朝)", re.I)
# the same words owning a noun: "tomorrow's festival", "tonight's match"
_POSSESSIVE_DAY = re.compile(
    r"\b(?:the day after tomorrow|tomorrow|today|tonight|this (?:morning|afternoon|evening))['’]s\s+", re.I)


_HOME_WORDS = ("her room", "her bedroom", "her futon", "kitchen", "bathroom", "genkan", "family flat", "living room")


def _at_home(scene):
    """Where she lives, by the scene's own words. Somebody else's house
    ("Rena's house") and the way home ("walking home") are not it."""
    loc = str(scene.get("location", "")).lower()
    if "'s " in loc or "walk" in loc or "between" in loc or "street" in loc:
        return False
    return loc == "home" or loc.startswith("home,") or loc.endswith(", home") or any(w in loc for w in _HOME_WORDS)


def _drop_relative_day(text):
    """The sentence without the relative day word. The date is beside it.

    A possessive one owns the noun after it, and taking the word out on its
    own left the apostrophe behind: "go to tomorrow's festival" was stored as
    "go to 's festival", a promise to nobody about a thing with no owner,
    which then stood on the record for six days. The possessive becomes "the"
    -- "go to the festival" -- and the day is in the row's `date` field."""
    out = _POSSESSIVE_DAY.sub("the ", str(text or ""))
    out = _RELATIVE.sub(" ", out)
    out = re.sub(r"\s{2,}", " ", out).strip(" ,、。")
    return out or str(text or "").strip()


# what is left when a word has been taken out of the middle of a phrase and
# the grammar it was carrying was not: a promise like this is not recorded
_MANGLED = re.compile(r"(?:^|\s)(?:'s|’s|of|to|at|with|the|a)\s*(?:$|[,.])|(?:^|\s)['’]s\b")


def _mangled(text):
    """Is this sentence missing a word it was built around."""
    return bool(_MANGLED.search(str(text or "")))


def _words(text):
    return set(w.lower() for w in _WORD.findall(text or "") if len(w) > 2)


def _same(a, b, threshold):
    wa, wb = _words(a), _words(b)
    if not wa or not wb:
        return False
    return len(wa & wb) / len(wa | wb) >= threshold


class Commitments:
    WIRES = ('graph', 'ledger', 'primitives', 'situation',)
    def __init__(self, config, llm, store, clock, state, money=None, graph=None, self_memory=None):
        self.config = config
        self.llm = llm
        self.store = store
        self.clock = clock
        self.state = state
        self.money = money
        self.graph = graph
        self.self_memory = self_memory
        # her name in capitals, for the prompt headings only. This was `self._her`,
        # which shadowed the method `_her()` below: three headings read the string
        # and six event writers called it, and every promise either character made
        # died in a TypeError with its paid call (audit of 2026-09-04 21:35).
        self._her_caps = str(getattr(config.character, "name", "her") or "her").upper()
        wiring.declare(self)

    # ---------------- storage ----------------

    def rows(self):
        return self.store.get("commitments", [])

    def save(self, rows):
        self.store.set("commitments", rows[-self.config.commitments.keep:])

    def open(self):
        return [r for r in self.rows() if r.get("status") == "open"]

    def _her(self):
        """Her name, for the one-line record of a promise. It used to be the
        first character's given name written into the string, which put her in
        every other character's event ledger -- and the checker that exists to
        catch exactly that could not see an f-string."""
        return str(getattr(self.config.character, "name", "") or "she")

    def _key_of(self, who):
        """The roster key, or None when nobody owns the name -- callers here
        branch on None, so an unknown name must not come back as itself."""
        return roster.key_of(self.config, who) if roster.role_of(self.config, who) else None

    def _name_of(self, key):
        return (self.state.relationships or {}).get(key, {}).get("name", key)

    # ---------------- making ----------------

    def _present(self, rec):
        """The roster keys of everybody who was in this exchange: the
        counterparty of a private room, every speaker in a group one. One
        walk, because `_bind` and `settle_sends_now` have to agree about who
        was there."""
        present = {self._key_of((rec or {}).get("who"))}
        for t in (rec or {}).get("turns") or []:
            present.add(self._key_of(t.get("who")))
        present.discard(None)
        present.discard("")
        return present

    def settle_sends_now(self, rec=None):
        """A promise to send somebody something is closed the moment the chat
        carries it, not at the day's compile.

        Sending the photograph used to create a fresh promise to send the
        photograph: the judge read the exchange, saw her saying she was
        sending it, and opened a promise that the settle would not look at
        until 10:55 the next morning. Between those two moments the chooser
        was offered "send her the photos you promised" at every opportunity
        and took it three more times, and the filter deleted the words each
        time -- so the room went quiet and the wanting did not. The record
        that keeps it is the same one the compile reads (`_check_send`: a
        message of HERS, in a room that person was in, carrying a picture),
        so nothing here believes anything she says about it.

        With a record, only the promises to people who were in that exchange;
        with none, every open one. Returns how many closed."""
        c = self.config.commitments
        if not c.enabled:
            return 0
        rows = self.rows()
        today = self.clock.date_str()
        present = self._present(rec) if rec else None
        n = 0
        for r in rows:
            if r.get("status") != "open" or r.get("kind") != "send" or r.get("to") == "him":
                continue
            if present is not None and r.get("to") not in present:
                continue
            kept, why = self._check_send(r)
            if not kept:
                continue
            self._close(r, "kept", why, today)
            logger.log(f"[commit] kept as it happened: {r['what'][:60]} -- {why[:80]}")
            prim = self.primitives
            if prim is not None and str(r.get("to_name") or "").strip():
                try:
                    prim.gave(r["to_name"], "she said she would %s, and she did" % str(r.get("what") or "")[:70])
                except Exception as e:
                    logger.log(f"[primitives] a kept promise not counted: {type(e).__name__}: {e}")
            n += 1
        if n:
            self.save(rows)
        return n

    def from_exchange(self, rec):
        """After an exchange: did she commit to anything? One flash call
        names it; code decides whether it binds."""
        c = self.config.commitments
        if not c.enabled or not rec or not rec.get("turns"):
            return []
        # before the judge is asked, so its list of what she still owes
        # this person does not show a promise this very exchange kept,
        # and before `_bind` can restate one
        self.settle_sends_now(rec)
        today = self.clock.date_str()
        rows = self.rows()
        # A cap that returns before the call throws the evidence away with it:
        # Aya proposed the library at 9 and Tomoe said yes, and the day's three
        # slots had already gone in one 23:40 batch, so nothing was bound and
        # the 05:00 schedule was never told to keep the window. She then talked
        # to him about a plan the machine had no record of. `max_open` is what
        # bounds how much she is carrying; this is a rate limit, and when it
        # bites it says so instead of dropping a real agreement in silence.
        if len([r for r in rows if r.get("made") == today]) >= c.max_new_per_day:
            logger.log(f"[commit] not asked about the exchange with {rec.get('who', '?')}: "
                       f"{c.max_new_per_day} made today already (raise commitments.max_new_per_day)")
            return []
        who = rec.get("who", "")
        chat = "\n".join(
            f"{t.get('who')}: {t.get('ja') or t.get('text', '')}" for t in rec["turns"])
        mine = [r for r in self.open() if roster.same(self.config, who, r["to_name"])]
        open_txt = "\n".join(f"- id {r['id']}: {r['what']} ({self._when(r)}"
                             + (f", {r['yen']} yen" if r.get("yen") else "") + ")" for r in mine) or "(none)"
        avail = self.money.available() if self.money else 0
        user = (
            f"TODAY: {self.clock.both()}\n"
            f"HER CALENDAR (resolve 明日 / 土曜 / the 29th against this): {self._week_line()}\n"
            f"WITH: {who} ({rec.get('kind', 'line')})\n"
            f"{self._her_caps}'S OPEN COMMITMENTS TO THIS PERSON: \n{open_txt}\n"
            f"MONEY SHE ACTUALLY HAS FREE: {avail} yen\n\n"
            f"THE EXCHANGE:\n{chat}\n"
        )
        data, _ = self.llm.call_json("commit", [
            {"role": "system", "content": self.config.prompt_text("commit")},
            {"role": "user", "content": user}])
        if not isinstance(data, dict):
            return []
        made = []
        amended = 0
        # a time or a date named in a later exchange for a promise already
        # open -- Kaito's "明日9時半、フィールドな" the evening before -- is the
        # promise's from then on; nothing carried it before, so the plan
        # invented 14:00, his own thread had 9:30, and by 10:28 he said she
        # had not come to a match still four hours off
        for item in data.get("amended", []) if isinstance(data.get("amended"), list) else []:
            if not isinstance(item, dict):
                continue
            cid = str(item.get("id", "") or "")
            date, f_hm, t_hm = self._parse_when(str(item.get("when", "") or ""))
            for r in rows:
                if r.get("id") == cid and r.get("status") == "open" and date:
                    before = self._when(r)
                    r.update({"date": date, "from_hm": f_hm or r.get("from_hm", ""), "to_hm": t_hm or r.get("to_hm", "")})
                    if self._when(r) != before:
                        r.setdefault("history", []).append(f"{today}: {before} -> {self._when(r)}, said with {who}")
                        self._wake_needs_redrawing(r)
                        logger.log(f"[commit] amended with {who}: {r['what'][:50]} {before} -> {self._when(r)}")
                        amended += 1
        for cid in data.get("cancelled", []) if isinstance(data.get("cancelled"), list) else []:
            self._cancel(str(cid), rows)
        for item in data.get("commitments", []) if isinstance(data.get("commitments"), list) else []:
            r = self._bind(item, rec, rows)
            if r:
                made.append(r)
                if len([x for x in rows if x.get("made") == today]) >= c.max_new_per_day:
                    break
        if made or data.get("cancelled") or amended:
            self.save(rows)
        return made

    def planner_lines(self, date_str):
        """For the cast planner: what she has promised on this date and the
        next, by id, with the date written out. The planner writes a day
        that may not be today, so a relative word is the wrong word here."""
        c = self.config.commitments
        if not c.enabled:
            return ""
        import datetime as _dt
        try:
            d0 = _dt.date.fromisoformat(date_str)
        except ValueError:
            return ""
        d1 = (d0 + _dt.timedelta(days=1)).isoformat()
        out = []
        for r in sorted(self.open(), key=lambda x: x["date"]):
            if r.get("date") not in (date_str, d1):
                continue
            rel = "the day being planned" if r["date"] == date_str else "the day after"
            when = (f"at {r['from_hm']}" + (f"-{r['to_hm']}" if r.get("to_hm") else "")) if r.get("from_hm") else "time not fixed"
            out.append(f"- [{r['id']}] with {r['to_name']}: {r['what']} -- {r['date']} ({rel}), {when}")
        return "\n".join(out)

    def pin_time(self, cid, hm, why=""):
        """The plan gave a time to a promise that had none: from then on it
        is the promise's time, for the schedule, the director, the speakers
        and the settle alike."""
        rows = self.rows()
        for r in rows:
            if r.get("id") == cid and r.get("status") == "open" and not r.get("from_hm"):
                mins = hm_to_minutes(hm, None)
                if mins is None:
                    return False
                r["from_hm"] = hm
                r["to_hm"] = f"{min(23, mins // 60 + 2):02d}:{mins % 60:02d}"
                r.setdefault("history", []).append(f"{self.clock.date_str()}: time set to {hm}" + (f" ({why})" if why else ""))
                self.save(rows)
                self._wake_needs_redrawing(r)
                logger.log(f"[commit] the plan set the time of '{r['what'][:50]}' ({r['to_name']}): {hm}" + (f" -- {why}" if why else ""))
                return True
        return False

    def from_chat(self):
        """After she has said something to him: did she promise him anything?
        Runs on the loop pass once her bubbles are in the store (delivery
        writes them as they go, so this waits for the batch to end). One
        call per burst of hers; the newest assistant rows since the last
        look are what is judged, the last few turns are the context."""
        c = self.config.commitments
        if not (c.enabled and c.him_enabled):
            return []
        last = self.store.get("commit_him_last_ts")
        msgs = self.store.recent_messages(c.him_messages_shown)
        hers = [m for m in msgs if m["role"] == "assistant"]
        if not hers:
            return []
        newest = max(m["ts"] for m in hers)
        if last is None:
            # first run on a save with history: start from now, or the
            # whole record would be read as tonight's promises
            self.store.set("commit_him_last_ts", newest)
            return []
        fresh = [m for m in hers if m["ts"] > float(last)]
        if not fresh:
            return []
        if self.clock.now_ts() - newest < c.him_settle_seconds:
            return []        # the batch may still be going out
        self.store.set("commit_him_last_ts", newest)
        today = self.clock.date_str()
        rows = self.rows()
        if len([r for r in rows if r.get("made") == today and r.get("to") == "him"]) >= c.him_max_new_per_day:
            logger.log(f"[commit] not asked what she just promised him: {c.him_max_new_per_day} made today "
                       "already (raise commitments.him_max_new_per_day)")
            return []
        chat = "\n".join(f"[{self.clock.hm(m['ts'])}] {'HIM' if m['role'] == 'user' else self._her_caps}: {m['text'][:300]}"
                         + ("   <- new" if m["role"] == "assistant" and m["ts"] > float(last) else "") for m in msgs)
        mine = [r for r in self.open() if r["to"] == "him"]
        open_txt = "\n".join(f"- id {r['id']}: {r['what']} ({self._when(r)})" for r in mine) or "(none)"
        user = (
            f"TODAY: {self.clock.both()}\n"
            f"HER CALENDAR: {self._week_line()}\n"
            f"{self._her_caps}'S OPEN PROMISES TO HIM:\n{open_txt}\n\n"
            f"THE CHAT (her time; the lines marked <- new are what she just sent):\n{chat}\n"
        )
        data, _ = self.llm.call_json("commit_him", [
            {"role": "system", "content": self.config.prompt_text("commit_him")},
            {"role": "user", "content": user}])
        if not isinstance(data, dict):
            return []
        made = []
        for cid in data.get("cancelled", []) if isinstance(data.get("cancelled"), list) else []:
            self._cancel(str(cid), rows)
        for item in data.get("commitments", []) if isinstance(data.get("commitments"), list) else []:
            r = self._bind_him(item, rows)
            if r:
                made.append(r)
        if made or data.get("cancelled"):
            self.save(rows)
        return made

    def _wake_needs_redrawing(self, r):
        """A promise with a start time on a day whose night has already been
        drawn: drop that draw so it is drawn again with the alarm in it. The
        wake and the night are decided once per date and persisted, and a plan
        agreed after that would otherwise be kept by a body that had already
        decided to sleep through it -- she agreed to the library at 9 at 20:05
        and her 10:10 wake was already on record."""
        if not r.get("from_hm") or r.get("date", "") <= self.clock.date_str():
            return
        for key in ("wake_days", "health_days"):
            days = self.store.get(key, {}) or {}
            if r["date"] in days:
                days.pop(r["date"])
                self.store.set(key, days)
                logger.log(f"[commit] {r['date']} {key[:-5]} re-draws: she has to be up for "
                           f"{r['what'][:50]} at {r['from_hm']}")

    def _outing(self, what, date):
        """(the calendar entry this promise is about, why it is not one).

        A promise to be somewhere public is a promise about a thing on the
        calendar, and it binds to that entry or it does not bind at all.
        Sixteen promises came due against a festival that had happened five
        days earlier and every one of them was written down as missed; the
        record then said for a week that everybody had let her down. The
        entry travels with the row, so an event dropped from the calendar
        after she agreed to go leaves the promise moot rather than broken."""
        led = self.ledger
        if not led:
            return "", ""
        try:
            why = led.outing_unbacked(what, date)
            if why:
                return "", why
            return led.event_for(what, date), ""
        except Exception:
            return "", ""

    def _bind_him(self, item, rows):
        """A promise to him binds with one of HIM_KINDS and a real date."""
        c = self.config.commitments
        if not isinstance(item, dict):
            return None
        kind = str(item.get("kind", "")).strip().lower()
        if kind not in HIM_KINDS:
            return None
        what = _drop_relative_day(str(item.get("what", "") or ""))[:120]
        if not what:
            return None
        date, f_hm, t_hm = self._parse_when(str(item.get("when", "") or ""))
        if not date:
            return None
        if _mangled(what):
            logger.log(f"[commit] not bound to him, the sentence lost the word it was built around: {what[:70]!r}")
            return None
        event, no_such = self._outing(what, date)
        if no_such:
            logger.log(f"[commit] not bound to him, no such thing that day ({no_such}): {what[:70]}")
            return None
        today = self.clock.date_str()
        for r in rows:
            if r.get("status") == "open" and r["to"] == "him" and _same(r["what"], what, c.similar_threshold):
                r.update({"date": date, "from_hm": f_hm, "to_hm": t_hm, "what": what})
                r.setdefault("history", []).append(f"{today}: restated to him")
                logger.log(f"[commit] restated to him: {what[:60]} ({self._when(r)})")
                return None
        if len([r for r in rows if r.get("status") == "open"]) >= c.max_open:
            return None
        gid = f"h{int(self.clock.now_ts())}{len(rows) % 100:02d}"
        r = {"id": gid, "made": today, "hm": self.clock.hm(), "to": "him", "to_name": "him",
             "what": what, "kind": kind, "date": date, "from_hm": f_hm, "to_hm": t_hm,
             "yen": 0, "reserved": 0, "funded": True, "source": "her own message to him",
             "event": event, "status": "open", "history": []}
        rows.append(r)
        self._wake_needs_redrawing(r)
        self.store.add_event(self.clock.now_ts(), today, "commitment", f"{self._her()} told him she would {what}", 3)
        logger.log(f"[commit] to him: {what[:70]} | {self._when(r)} ({kind})")
        return r

    def _bind(self, item, rec, rows):
        """A commitment binds only with a cast counterparty and a real date."""
        c = self.config.commitments
        if not isinstance(item, dict):
            return None
        key = self._key_of(item.get("to") or rec.get("who"))
        if not key or key == "him":
            return None
        # The judge is shown her open promises to this person, and the cheaper
        # model lifts one off that list into an exchange with somebody else:
        # three of thirty-five pairs in docs/ab-judge-roles.md (the notebook to
        # Aya from a talk with Hinako, two to Rena from breakfast with her
        # mother). A promise binds only to somebody who was in the exchange --
        # the counterparty of a private one, a speaker in a group one.
        present = self._present(rec)
        if key not in present:
            logger.log(f"[commit] not bound: {str(item.get('to') or '')[:20]!r} was not in the exchange with "
                       f"{rec.get('who', '?')} ({str(item.get('what', ''))[:50]})")
            return None
        kind = str(item.get("kind", "")).strip().lower()
        if kind not in KINDS:
            return None
        what = _drop_relative_day(str(item.get("what", "") or ""))[:120]
        if not what:
            return None
        date, f_hm, t_hm = self._parse_when(str(item.get("when", "") or ""))
        if not date:
            return None
        # A judge's sentence with a word taken out of the middle of it is not
        # a promise anybody made: "go to tomorrow's festival" was stored as
        # "go to 's festival" and stood open for six days.
        if _mangled(what):
            logger.log(f"[commit] not bound, the sentence lost the word it was built around: {what[:70]!r}")
            return None
        event, no_such = self._outing(what, date)
        if no_such:
            logger.log(f"[commit] not bound, no such thing that day ({no_such}): {what[:70]}")
            return None
        try:
            yen = max(0, min(50000, int(item.get("yen") or 0)))
        except (TypeError, ValueError):
            yen = 0
        today = self.clock.date_str()
        # the same promise again is the same promise: the window and the sum
        # move, nothing is charged (telling someone the time changed is not
        # letting them down)
        for r in rows:
            if r.get("status") == "open" and r["to"] == key and _same(r["what"], what, c.similar_threshold):
                r.update({"date": date, "from_hm": f_hm, "to_hm": t_hm, "what": what})
                r.setdefault("history", []).append(f"{today}: restated in an exchange with {rec.get('who')}")
                if yen and self.money and yen != r.get("yen", 0):
                    r["yen"] = yen
                    r["reserved"] = self.money.reserve(r["id"], yen)
                    r["funded"] = r["reserved"] >= yen
                logger.log(f"[commit] restated to {r['to_name']}: {what[:60]} ({self._when(r)})")
                return None
        if len([r for r in rows if r.get("status") == "open"]) >= c.max_open:
            return None
        gid = f"c{int(self.clock.now_ts())}{len(rows) % 100:02d}"
        reserved = self.money.reserve(gid, yen) if (yen and self.money) else 0
        r = {"id": gid, "made": today, "hm": self.clock.hm(), "to": key, "to_name": self._name_of(key),
             "what": what, "kind": kind, "date": date, "from_hm": f_hm, "to_hm": t_hm,
             "yen": yen, "reserved": reserved, "funded": (reserved >= yen) if yen else True,
             "source": f"exchange with {rec.get('who')} ({rec.get('kind')})",
             "event": event, "status": "open", "history": []}
        rows.append(r)
        self._wake_needs_redrawing(r)
        self.store.add_event(self.clock.now_ts(), today, "commitment",
                             f"{self._her()} promised {r['to_name']}: {what}" + (f" ({yen} yen)" if yen else "")
                             + (" -- money she does not have" if not r["funded"] else ""), 3)
        logger.log(f"[commit] to {r['to_name']}: {what[:70]} | {self._when(r)}"
                   + (f" | {yen} yen, {reserved} put aside" if yen else "")
                   + ("" if r["funded"] else " | NOT FUNDED"))
        return r

    def _week_line(self):
        """The next seven days with their dates, because `clock.both()`
        carries a weekday and a time but no date, and a model asked to
        resolve 明日 without one invents a year."""
        today = self.clock.now().date()
        out = [f"today {today.isoformat()} ({today.strftime('%A')})"]
        for i in range(1, 8):
            d = today + datetime.timedelta(days=i)
            out.append(f"{'tomorrow' if i == 1 else d.strftime('%A')} {d.isoformat()}")
        return "; ".join(out)

    _DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")

    def _parse_when(self, s):
        s = s.strip()
        today = self.clock.now().date()
        # relative words, resolved by code rather than trusted from a year the
        # model made up: today / tomorrow / a weekday name (next occurrence)
        rel = re.match(r"^(today|tomorrow|[A-Za-z]+day)(?:\s+(\d{1,2}:\d{2})(?:\s*[-~]\s*(\d{1,2}:\d{2}))?)?$", s, re.I)
        if rel:
            w = rel.group(1).lower()
            if w == "today":
                d = today
            elif w == "tomorrow":
                d = today + datetime.timedelta(days=1)
            elif w in self._DAYS:
                ahead = (self._DAYS.index(w) - today.weekday()) % 7 or 7
                d = today + datetime.timedelta(days=ahead)
            else:
                return None, "", ""
            s = d.isoformat() + (f" {rel.group(2)}" if rel.group(2) else "") + (f"-{rel.group(3)}" if rel.group(3) else "")
        m = re.match(r"^(\d{4}-\d{2}-\d{2})(?:[ T](\d{1,2}:\d{2})(?:\s*[-~]\s*(\d{1,2}:\d{2}))?)?$", s)
        if not m:
            return None, "", ""
        try:
            d = datetime.date.fromisoformat(m.group(1))
        except ValueError:
            return None, "", ""
        if d < today or (d - today).days > self.config.commitments.max_days_ahead:
            return None, "", ""
        f_hm = m.group(2) or ""
        t_hm = m.group(3) or ""
        if f_hm and not t_hm:
            mins = hm_to_minutes(f_hm, None)
            t_hm = f"{min(23, mins // 60 + 2):02d}:{mins % 60:02d}" if mins is not None else ""
        return d.isoformat(), f_hm, t_hm

    def _cancel(self, cid, rows):
        """She called one off herself, in words, before the day. Honest, and
        cheaper than not turning up -- but not free."""
        c = self.config.commitments
        for r in rows:
            if r.get("id") == cid and r.get("status") == "open":
                r["status"] = "let_go"
                r["settled"] = self.clock.date_str()
                r["why"] = "she called it off herself"
                if self.money:
                    self.money.release(r["id"])
                self.state._warm("guilt", c.cancel_guilt, 90)
                self._move_edge(r["to_name"], 0, c.cancel_irritation)
                self.store.add_event(self.clock.now_ts(), self.clock.date_str(), "commitment",
                                     f"{self._her()} told {r['to_name']} she could not after all: {r['what']}", 3)
                logger.log(f"[commit] called off with {r['to_name']}: {r['what'][:60]}")
                return True
        return False

    # ---------------- settling ----------------

    def settle(self, date):
        """At the compile, from the record only. Once; never reversed."""
        c = self.config.commitments
        if not c.enabled:
            return 0
        # anything a room kept and nothing was there to notice
        self.settle_sends_now()
        rows = self.rows()
        n = 0
        for r in rows:
            if r.get("status") != "open" or r.get("date", "") > date:
                continue
            # the other party could not come: nothing to keep and nothing
            # broken. "attend the festival" was KEPT 120 minutes late against
            # a Rena the cast had grounded that morning. Only for the two
            # that need her standing there -- somebody shut in at home is
            # exactly who a picture gets sent to, and their being out of the
            # day is no excuse for not sending it.
            led = self.ledger
            # a promise about a public event the calendar does not have that
            # day was never a day she could turn up on. Settled the way an
            # outing nobody could come to is settled -- nobody's fault and
            # nobody's meters -- rather than counted against her as broken,
            # which is what happened five days running to promises about a
            # festival that had already been and gone (sim/ledger.py).
            if led:
                why_none = led.promise_unbacked(r)
                if why_none:
                    self._close(r, "moot", f"there was no such thing that day: {why_none}", date)
                    n += 1
                    continue
            if led and r["kind"] in _NEEDS_PRESENCE and led.is_absent(r["to_name"], r.get("from_hm") or "12:00", r["date"]):
                self._close(r, "moot", f"{r['to_name']} could not come", date)
                n += 1
                continue
            kept, why, late = self._check(r)
            self._close(r, "kept" if kept else "broken", why, date, late=late)
            # A promise she made HIM and kept is a give, and it is the only
            # entry on the ledger she controls. A character with no world has
            # almost no other way to put anything into it, so without this
            # reciprocity can only ever run against her -- and a ledger that
            # moves in one direction is not a ledger (docs/primitives.md §4).
            prim = self.primitives
            if prim is not None and kept and str(r.get("to_name") or "").strip():
                try:
                    prim.gave(r["to_name"], "she said she would %s, and she did" % str(r.get("what") or "")[:70])
                except Exception as e:
                    logger.log(f"[primitives] a kept promise not counted: {type(e).__name__}: {e}")
            n += 1
        if n:
            self.save(rows)
        return n

    def _in_window(self, hm, r):
        if not r.get("from_hm"):
            return True
        t = hm_to_minutes(hm, None)
        f, e = hm_to_minutes(r["from_hm"], None), hm_to_minutes(r.get("to_hm") or r["from_hm"], None)
        if t is None or f is None or e is None:
            return True
        slack = self.config.commitments.attend_slack_minutes
        return f - slack <= t <= e + slack

    def _late(self, hm, r):
        """Minutes past the hour she said. `attend_slack_minutes` is 90, so
        turning up at half past twelve for a nine o'clock settled KEPT and
        looked in the record exactly like arriving on time -- same regard,
        same pride, same "she kept her word". She did keep it. She was also
        late, and that is a different thing to have been."""
        if not r.get("from_hm"):
            return 0
        t, f = hm_to_minutes(hm or "", None), hm_to_minutes(r["from_hm"], None)
        if t is None or f is None:
            return 0
        return max(0, t - f)

    def _place_ok(self, r, scenes):
        """Does the promise name a place the day actually has, and does THIS
        scene stand in it? "bring a water bottle to the festival" was KEPT
        by standing next to Kaito in the kitchen at 08:45. The promise's own
        words are matched against every scene's location and activity; if
        any scene matches, only a matching scene can keep it. A promise that
        names no place the day has ("go out") keeps on presence alone."""
        from sim.textutil import words
        from sim import schedule as sched
        want = words(r.get("what", ""), min_latin=4)
        if not want:
            return lambda s: True
        # the scene's own `activity` is what she is doing ("grabbing the water
        # bottle"), and matching on it kept "bring a water bottle to the
        # festival" in the kitchen. Where she IS is the location and the
        # schedule block the scene falls in.
        blocks = (self.store.get_schedule(r["date"]) or {}).get("blocks") or []

        def toks(s):
            t = str(s.get("location", ""))
            try:
                h, m = str(s.get("hm", "")).split(":")
                blk = sched.block_at(blocks, datetime.datetime(2000, 1, 1, int(h), int(m))) if blocks else None
                if blk:
                    t += " " + str(blk.get("activity", "")) + " " + str(blk.get("location", ""))
            except (ValueError, IndexError):
                pass
            return words(t, min_latin=4)
        if not any(want & toks(s) for s in scenes):
            # the promise names a thing -- Kaito's soccer match -- and the
            # day never had it. "go to the match" was KEPT by Kaito standing
            # in her doorway at 10:40. Being with them somewhere that is not
            # home still keeps it (the scene may just not name the place);
            # being with them at home does not.
            if r.get("kind") == "attend":
                return lambda s: not _at_home(s)
            return lambda s: True
        return lambda s: bool(want & toks(s))

    def _check(self, r):
        c = self.config.commitments
        name = r["to_name"].lower()
        # who it was made to decides which record settles it, never the verb:
        # `send` means one thing to him (a message with something in it) and
        # another to a friend (a picture in their chat), and reading the verb
        # sent the second one looking through her messages to him.
        if r.get("to") == "him":
            kept, why = self._check_him(r)
            return kept, why, 0
        if r["kind"] == "send":
            kept, why = self._check_send(r)
            return kept, why, 0
        if r["kind"] in ("attend", "bring"):
            scenes = self.store.scenes_for_date(r["date"])
            here = self._place_ok(r, scenes)
            for s in scenes:
                if name in (s.get("with_who") or "").lower() and self._in_window(s.get("hm", ""), r) and here(s):
                    return True, f"she was with {r['to_name']} at {s.get('hm')} ({s.get('location', '')[:40]})", self._late(s.get("hm", ""), r)
            # an in-person exchange has no place; it keeps a promise only
            # when the promise names none (then presence alone keeps it)
            from sim.textutil import words as _w
            if r["kind"] != "attend" or not _w(r.get("what", ""), min_latin=4):
                for x in self.store.get("cast_chat", []):
                    if (x.get("date") == r["date"] and x.get("kind") == "in_person"
                            and roster.same(self.config, name, x.get("who")) and self._in_window(x.get("hm", ""), r)):
                        return True, f"she was with {r['to_name']} in person at {x.get('hm')}", self._late(x.get("hm", ""), r)
            if r["kind"] == "attend":
                at_home = [s for s in scenes if name in (s.get("with_who") or "").lower() and _at_home(s)]
                if at_home:
                    return False, f"she was with {r['to_name']} only at home ({at_home[0].get('hm')}); the day never took her to it", 0
                return False, f"no scene on {r['date']} had her with {r['to_name']}" + (f" between {r['from_hm']} and {r['to_hm']}" if r.get("from_hm") else ""), 0
        if r["kind"] in ("buy", "bring") and self.money:
            for e in self.money.m.get("log", []):
                if (e.get("yen", 0) < 0 and r["made"] <= e.get("date", "") <= r["date"]
                        and _same(e.get("on", ""), r["what"], c.buy_match)):
                    return True, f"bought: {e['on']} ({-e['yen']} yen on {e['date']})", 0
            return False, "nothing in the money record matches it", 0
        return False, "no record of it", 0

    def _check_send(self, r):
        """A promise to a person in her world to send them something.

        The record is the chat itself: a message of HERS, in a room that
        person was in, carrying a picture or a video. Her saying she sent it
        does not count and must not -- she told her mother the photos had
        gone at 18:22 on a day the chat has no picture of hers in it at all
        (rule 14, nothing the narrator claims).

        Anything up to the day it was due counts. A picture sent the evening
        before is the thing arriving early, not a different promise."""
        marker = re.compile(r"^\s*\[(?:写真|動画|photo|video)\b")
        for x in self.store.get("cast_chat", []):
            date = str(x.get("date") or "")
            if not (r["made"] <= date <= r["date"]):
                continue
            if not roster.witnessed(self.config, r["to_name"], x):
                continue
            for t in x.get("turns") or []:
                if not roster.is_self(self.config, t.get("who", "")):
                    continue
                if t.get("img") or marker.match(str(t.get("ja") or "")):
                    where = "the group" if x.get("kind") == "group" else r["to_name"]
                    return True, f"she sent it to {where} at {t.get('hm') or x.get('hm')} on {date}"
        return False, f"nothing of hers in {r['to_name']}'s chat carried it"

    def _check_him(self, r):
        """From her messages to him on the day, in the window, nothing else."""
        c = self.config.commitments
        hers = [m for m in self.store.messages_for_date(r["date"]) if m["role"] == "assistant"
                and self._in_window(self.clock.hm(m["ts"]), r)]
        if not hers:
            return False, f"she sent him nothing on {r['date']}" + (f" between {r['from_hm']} and {r['to_hm']}" if r.get("from_hm") else "")
        if r["kind"] == "text_by":
            return True, f"she messaged him at {self.clock.hm(hers[0]['ts'])}"
        if r["kind"] == "send":
            for m in hers:
                if "http" in (m["text"] or "") or "[share" in (m["text"] or "") or "[photo" in (m["text"] or ""):
                    return True, f"she sent it at {self.clock.hm(m['ts'])}"
            return False, "she wrote to him but sent no link or picture"
        for m in hers:
            if _same(m["text"] or "", r["what"], c.buy_match):
                return True, f"she told him at {self.clock.hm(m['ts'])}: {(m['text'] or '')[:60]}"
        return False, "she wrote to him but never got to it"

    def _knew_late(self, r, date):
        """The record of her having known, for this promise, or None."""
        seen = self.store.get("knew_late", {}) or {}
        for key, v in seen.items():
            if key.startswith(f"{r.get('date', date)}|") and key.endswith(f"|{r.get('id', '')}"):
                return v
        return seen.get(f"{r.get('date', date)}|{r.get('id', '')}") or None

    def _close(self, r, status, why, date, late=0):
        c = self.config.commitments
        late = int(late or 0)
        after = int(getattr(c, "late_after_minutes", 15) or 15)
        was_late = status == "kept" and late >= after
        # did she WALK INTO it? `running_late` records the moment the honest
        # arithmetic stopped being deniable, so a late arrival she saw coming
        # is not the same thing as one that happened to her. Without this the
        # settle cannot tell the difference and neither can she.
        knew = self._knew_late(r, date)
        if was_late:
            why = f"{why} -- {late} minutes late" + (f", and she knew it by {knew['hm']}" if knew else "")
        r["status"] = status
        r["settled"] = date
        r["why"] = why
        r["late_min"] = late
        if self.money:
            self.money.release(r["id"])
        rel = (self.state.relationships or {}).get(r["to"])
        if status == "moot":
            # nobody's fault, nobody's meters; she remembers it as the thing
            # that did not happen, which is what it was
            if self.self_memory and self.config.self_memory.enabled:
                self.self_memory.add(date, f"{r['to_name']} could not come after all: {r['what']}.",
                                     weight=1, feeling="a bit flat about it", valence=0, source="commit")
            text = f"The promise to {r['to_name']} came to nothing: {r['what']} ({why})"
            self.store.add_event(self.clock.now_ts(), date, "commitment", text, 2)
            logger.log(f"[commit] MOOT with {r['to_name']}: {r['what'][:60]} -- {why[:80]}")
            return
        if status == "kept":
            if rel:
                rel["standing"] = min(100.0, float(rel.get("standing", 50)) + (c.kept_standing if not was_late else 0))
            # she came, so it is kept; she was late, so it is not the same as
            # having been on time. The person waiting is the one who felt it.
            self._move_edge(r["to_name"], c.late_regard if was_late else c.kept_regard,
                            c.late_irritation if was_late else 0)
            self.state._warm("pride", c.late_pride if was_late else c.kept_pride, 90)
            if was_late:
                self.state._warm("guilt", c.late_guilt * (c.knew_guilt_factor if knew else 1.0), 90)
            if self.self_memory and self.config.self_memory.enabled:
                if was_late:
                    knew_txt = (f" She had known since {knew['hm']} that she was not going to make it, "
                                f"and said nothing." if knew else "")
                    self.self_memory.add(date, f"She got to {r['to_name']} {late} minutes late: {r['what']}. "
                                               f"She had said {r['from_hm']}.{knew_txt}",
                                         weight=c.memory_weight_kept,
                                         feeling="ashamed" if knew else "sheepish", valence=0, source="commit")
                else:
                    self.self_memory.add(date, f"She kept her word to {r['to_name']}: {r['what']}.",
                                         weight=c.memory_weight_kept, feeling="steady", valence=1, source="commit")
            text = (f"{self._her()} was {late} minutes late to {r['to_name']}: {r['what']} ({why})" if was_late
                    else f"{self._her()} kept her promise to {r['to_name']}: {r['what']} ({why})")
            sal = 3
        else:
            if rel:
                # no gravity on the meters: this stays off
                rel["standing"] = max(0.0, float(rel.get("standing", 50)) - c.broken_standing)
                rel["closeness"] = max(0.0, float(rel.get("closeness", 50)) - c.broken_closeness)
            self._move_edge(r["to_name"], -c.broken_regard, c.broken_irritation)
            self.state._warm("guilt", c.broken_guilt, 90)
            self.state._warm("shame", c.broken_shame, 90)
            if self.self_memory and self.config.self_memory.enabled:
                self.self_memory.add(date, f"She let {r['to_name']} down: she had said she would ({r['what']}) and did not.",
                                     weight=c.memory_weight_broken, feeling="ashamed", valence=-2, source="commit")
            text = f"{self._her()} did not keep her promise to {r['to_name']}: {r['what']} ({why})"
            sal = 4
        try:
            self.state.save()
        except Exception:
            pass
        self.store.add_event(self.clock.now_ts(), date, "commitment", text, sal)
        logger.log(f"[commit] {status.upper()}{' (LATE ' + str(late) + 'm)' if was_late else ''} with "
                   f"{r['to_name']}: {r['what'][:60]} -- {why[:80]}")

    def _move_edge(self, holder_name, d_regard, d_irritation):
        """The counterparty's own edge to her, moved by code now; their next
        graph update rewrites the view from the witnessed event."""
        if not self.graph:
            return
        if getattr(self.graph, "read_only", False):
            # one process settles who holds what about whom
            # (docs/shared-world.md); a copy moved here would be a number
            # nobody else in the world agrees with
            logger.log(f"[commit] the edge {holder_name} holds is the world owner's to move; not moved here")
            return
        try:
            g = self.graph._load()
            # keyed by the handle the record calls her, which is not her
            # config name for a character promoted out of somebody else's cast
            e = g["edges"].get(f"{holder_name}|{roster.handle(self.config)}")
            if not e:
                return
            e["regard"] = max(0, min(100, int(e.get("regard", 50)) + d_regard))
            e["irritation"] = max(0, min(100, int(e.get("irritation", 10)) + d_irritation))
            e["updated"] = self.clock.now_ts()
            e["evidence"] = int(e.get("evidence", 0)) + 1
            self.graph._save(g)
        except Exception as ex:
            logger.log(f"[commit] edge not moved: {type(ex).__name__}: {ex}")

    # ---------------- readers ----------------

    def _when(self, r):
        s = r.get("date", "")
        if r.get("from_hm"):
            s += f" {r['from_hm']}" + (f"-{r['to_hm']}" if r.get("to_hm") else "")
        return s

    def _days(self, r):
        try:
            return (datetime.date.fromisoformat(r["date"]) - self.clock.now().date()).days
        except ValueError:
            return 0

    def _rel_day(self, r):
        d = self._days(r)
        if d <= 0:
            return "today"
        if d == 1:
            return "tomorrow"
        return f"in {d} days ({r['date'][5:]})"

    def running_late(self):
        """Is she going to make it, and does she know?

        The map has always known what a place costs to reach and nothing ever
        compared it to the clock, so she could stand at the genkan with a nine
        o'clock promise and no idea. Now the honest figure exists: where she
        is, what the journey costs, how long is left.

        She is not honest with herself about it. `optimism_minutes` is what she
        shaves off when she is already behind -- if she runs, if the train is
        there, if the lights go her way. Past `knows_late_minutes` of real
        shortfall the optimism stops working and **she knows**, and the record
        says she knew. That is the whole point of the split: a lateness she
        walked into is hers, and one she never saw coming is the system being
        unfair to her.

        Returns a dict or None."""
        c = self.config.commitments
        sit = self.situation
        if not c.enabled or not sit:
            return None
        today = self.clock.date_str()
        rows = [r for r in self.open() if r.get("date") == today and r.get("from_hm")]
        if not rows:
            return None
        r = min(rows, key=lambda x: hm_to_minutes(x["from_hm"]))
        due = hm_to_minutes(r["from_hm"])
        now = hm_to_minutes(self.clock.hm())
        left = due - now
        if left > c.warn_within_minutes:
            return None            # not yet on her mind
        node = None
        try:
            node = sit.resolve(r.get("what", ""), r.get("what", ""))
        except Exception:
            node = None
        eta = sit.minutes_to(node) if node else None
        if eta is None:
            return None
        margin = left - eta                       # < 0 is late, honestly
        believed = margin + float(c.optimism_minutes)
        knows = margin <= -float(c.knows_late_minutes)
        rec = {"what": r.get("what", ""), "who": r.get("to_name", ""), "from_hm": r["from_hm"],
               "eta": round(eta), "left": round(left), "margin": round(margin),
               "believed": round(believed), "knows": bool(knows),
               "where": sit.name(node) if node else ""}
        if knows:
            # she knew, and the record says so -- read at the settle, so a
            # kept-but-late promise can tell the difference between bad luck
            # and a girl who left anyway
            seen = self.store.get("knew_late", {}) or {}
            key = f"{today}|{r.get('id', r['from_hm'])}"
            if key not in seen:
                seen[key] = {"ts": self.clock.now_ts(), "hm": self.clock.hm(),
                             "by": rec["margin"], "what": rec["what"], "who": rec["who"]}
                self.store.set("knew_late", seen)
                logger.log(f"[commit] she knows she is {-rec['margin']} min late for "
                           f"{rec['who']} ({rec['what'][:40]}): {rec['eta']} min to go, "
                           f"{rec['left']} min left")
        return rec

    def late_line(self):
        """The lateness as she carries it -- what she believes, not the honest
        number, except once it is too big to believe around."""
        rec = self.running_late()
        if not rec:
            return ""
        who, when = rec["who"], rec["from_hm"]
        if rec["knows"]:
            return (f"you are not going to make {when} with {who}. it is {rec['eta']} minutes "
                    f"from here and you have {rec['left']}. you know it, and you have not said anything.")
        if rec["margin"] < 0:
            # she IS late and does not believe it yet -- the interesting state,
            # and the one the ordering hid: this used to be tested against her
            # optimistic figure, which is worse than the threshold that makes
            # her know, so it could never fire.
            return (f"{when} with {who} is tight -- {rec['eta']} minutes to get there and {rec['left']} left. "
                    f"you think you can still make it if you go right now.")
        if rec["margin"] < 10:
            return f"{when} with {who}: {rec['eta']} minutes to get there, {rec['left']} left. cutting it fine."
        return ""

    def situation_line(self, ja=False):
        """Persona: what she has promised, as she would carry it."""
        c = self.config.commitments
        if not c.enabled:
            return ""
        out = []
        for r in sorted(self.open(), key=lambda x: x["date"])[:5]:
            if ja:
                s = f"{r['to_name']}に{r['what']}と言った（{self._rel_day(r)}"
                if r.get("from_hm"):
                    s += f" {r['from_hm']}"
                s += "）"
                if r.get("yen"):
                    s += f"、{r['yen']}円くらい" + ("" if r.get("funded") else "、その分は手元にない")
            else:
                s = f"you told {r['to_name']} you would {r['what']} ({self._rel_day(r)}"
                if r.get("from_hm"):
                    s += f" {r['from_hm']}"
                s += ")"
                if r.get("yen"):
                    s += f", about {r['yen']} yen" + ("" if r.get("funded") else " which you do not have")
            out.append(s)
        recent = [r for r in self.rows() if r.get("status") in ("broken",) and self._age(r) <= 3]
        for r in recent[-2:]:
            out.append(f"{self._ago(r)}、{r['to_name']}との約束を守れなかった: {r['what']}" if ja else
                       f"you let {r['to_name']} down {self._ago(r)}: {r['what']}")
        line = ((("約束したこと: " if ja else "promises: ") + "; ".join(out))) if out else ""
        late = self.late_line()
        return (line + ("\n" if line else "") + late) if late else line

    def _age(self, r):
        try:
            return (self.clock.now().date() - datetime.date.fromisoformat(r.get("settled", r["date"]))).days
        except ValueError:
            return 99

    def _ago(self, r):
        a = self._age(r)
        return "today" if a <= 0 else ("yesterday" if a == 1 else f"{a} days ago")

    def director_line(self):
        c = self.config.commitments
        if not c.enabled:
            return ""
        rows = sorted(self.open(), key=lambda x: x["date"])[:6]
        if not rows:
            return ""
        lines = ["WHAT SHE HAS PROMISED PEOPLE (real, on the record; if she buys the thing, `spent.on` must name it; "
                 "if she is with the person for it, say so in `with`):"]
        for r in rows:
            lines.append(f"- {r['to_name']}: {r['what']} -- {self._rel_day(r)}"
                         + (f" {r['from_hm']}-{r['to_hm']}" if r.get("from_hm") else "")
                         + (f"; {r['reserved']} of {r['yen']} yen put aside" if r.get("yen") else ""))
        return "\n".join(lines)

    def schedule_lines(self):
        """For the schedule (via Events.brief): windows the plan must keep."""
        c = self.config.commitments
        if not c.enabled:
            return []
        out = []
        for r in sorted(self.open(), key=lambda x: x["date"]):
            if 0 <= self._days(r) <= 1:
                out.append(f"- {self._rel_day(r)}" + (f" {r['from_hm']}-{r['to_hm']}" if r.get("from_hm") else "")
                           + f": {r['what']} (promised to {r['to_name']})")
        return out

    def morning_line(self):
        c = self.config.commitments
        if not c.enabled:
            return ""
        rows = sorted(self.open(), key=lambda x: x["date"])[:6]
        if not rows:
            return ""
        parts = []
        for r in rows:
            p = f"{r['what']} for {r['to_name']} ({self._rel_day(r)})"
            if r.get("yen"):
                p += f", {r['yen']} yen" + ("" if r.get("funded") else " SHE DOES NOT HAVE")
            parts.append(p)
        avail = f"; {self.money.available()} yen actually free" if self.money else ""
        return "; ".join(parts) + avail

    def brief_for(self, who):
        """For this speaker's cast_turn: what Tomoe owes them, kept, or
        broke. Theirs to bring up."""
        c = self.config.commitments
        if not c.enabled:
            return ""
        key = self._key_of(who)
        if not key:
            return ""
        out = []
        # her name as the record writes it: this goes into a prompt where the
        # transcript beside it says 古賀朋絵 and the sheet says they call her とも
        from sim import roster
        her = roster.record_name(self.config, str(getattr(self.config.character, "name", "") or "her"))
        for r in self.rows():
            if r["to"] != key:
                continue
            if r["status"] == "open":
                out.append(f"- {her} said she would {r['what']} ({self._rel_day(r)})")
            elif r["status"] == "broken" and self._age(r) <= 10:
                out.append(f"- {her} said she would {r['what']} and did not ({self._ago(r)})")
            elif r["status"] == "let_go" and self._age(r) <= 5:
                out.append(f"- {her} called off {r['what']} herself ({self._ago(r)})")
            elif r["status"] == "kept" and self._age(r) <= 5:
                out.append(f"- {her} kept her word about {r['what']} ({self._ago(r)})")
        return "\n".join(out[-5:])

    def owed_sends(self, who):
        """What she has still to send this person: the `what` of each open
        one, for her own side of the chat. Only theirs, and only while it is
        still open -- a thing already sent is not in front of her again."""
        c = self.config.commitments
        key = self._key_of(who)
        if not c.enabled or not key:
            return []
        return [str(r.get("what") or "") for r in self.rows()
                if r.get("status") == "open" and r.get("kind") == "send" and r.get("to") == key
                and str(r.get("what") or "").strip()][:2]

    def closed_brief(self, days=3):
        """Promises that have stopped being owed, for the day's planner.

        It is told to carry what yesterday settled "unless a beat today
        changes it", and nothing else ever tells it a thing is finished. So
        a line saying a promise is still due outlived the promise itself:
        the row had been closed and the record said she had sent the photos,
        and the day's settled list still said they were owed -- which is the
        line the prompt calls true above memory and habit, so every friend's
        turn was written against a debt that no longer existed."""
        c = self.config.commitments
        if not c.enabled:
            return ""
        today = self.clock.date_str()
        out = []
        for r in self.rows():
            if r.get("status") == "open" or not r.get("settled"):
                continue
            if self._days_between(str(r["settled"]), today) > int(days):
                continue
            done = {"kept": "she did it", "broken": "she did not, and it is over",
                    "let_go": "she called it off", "moot": "it fell through on their side"}
            out.append(f"- {r['what']} (to {r['to_name']}): {done.get(r['status'], r['status'])}, "
                       f"settled {r['settled']}")
        return "\n".join(out[-8:])

    def _days_between(self, a, b):
        try:
            return abs((datetime.date.fromisoformat(b) - datetime.date.fromisoformat(a)).days)
        except (TypeError, ValueError):
            return 999

    def report(self):
        rows = self.rows()
        out = [f"{len(self.open())} open, {len(rows)} on record"
               + (f"; {self.money.reserved()} yen put aside of {self.money.balance()}" if self.money else "")]
        for r in rows[-12:]:
            out.append(f"  {r['status']:7s} {r['to_name'][:10]:10s} {r['kind']:6s} {self._when(r):17s} "
                       f"{r['what'][:44]:44s}" + (f" {r['yen']}y" if r.get("yen") else "")
                       + ("" if r.get("funded", True) else " UNFUNDED")
                       + (f"  <- {r.get('why', '')[:50]}" if r.get("why") else ""))
        return "\n".join(out)
