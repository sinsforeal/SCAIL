"""What the fiction said happened, against what the machine actually did.

Every model in this project writes prose, and some of the things prose can say
are things only code can do. The director wrote *"She finally sends him the
message she's been drafting since the bath"* and no message ever left the
process: no `messages` row, no `tg_id`, nothing delivered. The scene said she
acted; the machine had not. That is not a director bug, it is a missing
contract, and the same shape has now appeared four times -- the X post recorded
before `curation.decide` returned, `approach.note()` charged before the bubbles
existed, `hazards_seen` marked before delivery, and this.

The rule underneath all four: **a record of an action must never exist without
the action.** Two halves to enforcing it.

The ordering half is discipline and lives at each call site: nothing is written
down until the thing that decides whether it happens has returned. That is
already fixed everywhere it was found.

The other half is this module, and it is the one that generalises. Prose is
free text and can assert anything, so it needs a check rather than an ordering.
For every action she can take, this holds three things: the typed field that
legitimately carries it (`spent`, `open_note`, `ate` -- the channels code
already honours), a reader that answers whether it really happened in this
window, and what to do when the prose claims it and neither is true.

Code decides when (every tick that produced prose, cheap, gated); a model
decides what (does this sentence assert this action, and what should it say
instead). Nothing here rewrites state -- it only ever corrects the fiction down
to what the machine actually did, or hands the action to the channel that can
really perform it.

Every violation is logged to kv `reconcile_log`, because the point is not only
to correct a scene: it is to find out which call drifts, and how often, in a
system where nobody would otherwise notice.
"""
import re

import logger

# ---------------------------------------------------------------------------
# A photo of her own making, for him.
#
# She has no way to give him a picture she took. Scenery (tomoe/scenery.py) sends
# a real photograph from a real account as hers, and [share: ID] puts a post in
# his hands; both are the machine's, decided elsewhere. She owns no album for
# him and no drafts. On 2026-08-29 the anticipation role invented a yukata photo
# she wanted to send him, anticipation_line() carried it for hours, and in three
# days it reached ~60 interior lines, the cast engine and three of her messages
# to him. The rule now lives in prompts/bible.md, which every interior role gets.
#
# This is the tripwire for the next one, and it only ever flags: his standing
# rule is that a check never rewrites her dialogue. A line that refers to a
# scenery photo she really did send can trip it; that is the price of a cheap
# deterministic test, and the log line carries the text so it can be judged.
_PHOTO_EN = [
    r"\b(send|sending|sent|show|showing|showed)\s+(you|him)\b[^.]{0,40}\b(photo|photos|picture|pictures|pic|pics)\b",
    r"\b(photo|photos|picture|pictures|pic|pics)\b[^.]{0,40}\b(to|for)\s+(you|him)\b",
    r"\byou\s+(saw|seen|have seen)\b[^.]{0,30}\b(photo|picture|pic)\b",
    r"\bwaiting\b[^.]{0,30}\bfor a (photo|picture|pic)\b",
]
_PHOTO_EN = [re.compile(p, re.I) for p in _PHOTO_EN]
_HIM_JA = ("彼", "あの人", "あいつ")
_GAVE_JA = ("送ってき", "送ってく", "くれた", "見せてき")


def claims_own_photo(text):
    """Does this sentence say she has, took, owes or sent HIM a picture of her
    own -- or that he saw one? Deterministic, both languages, no model."""
    s = str(text or "")
    if not s:
        return False
    # scenery writes its own record line for a photo that really went out
    if s.lstrip().lower().startswith("she sent him a photo:"):
        return False
    if "写真" in s and any(h in s for h in _HIM_JA) and ("送" in s or "見せ" in s):
        if not any(g in s for g in _GAVE_JA):
            return True
    return any(p.search(s) for p in _PHOTO_EN)


def flag_own_photo(text, where, store=None, clock=None):
    """Log it and keep a row; never touch the text. Returns True when flagged."""
    if not claims_own_photo(text):
        return False
    logger.log(f"[reconcile] FLAG: a photo of her own making, for him ({where}): {str(text)[:160]}")
    if store is not None and clock is not None:
        try:
            rows = list(store.get("flags", []) or [])
            rows.append({"ts": clock.now_ts(), "date": clock.date_str(),
                         "what": "a photo of her own making, for him", "where": where,
                         "text": str(text)[:300]})
            store.set("flags", rows[-100:])
        except Exception:
            pass
    return True


# ---------------------------------------------------------------- restaged contact
# The director invents a message arriving. It was found by the neutralisation
# test: at her 22:38 on 2026-09-01 the neutral director returned the event
# "He replied to her message about the festival photos" -- he really had
# written, at 22:37, and the input said so twice (`UNREAD MESSAGES FROM HIM: 0`
# and `already sent, do not restage them`). The original prompt did not state
# the rule anywhere; it happened not to fire because every example in its list
# was one of her own people. A fence nobody wrote down.
#
# So it is checked here instead, against the record, where it holds for any
# prompt file and for a character with no people at all. Flag only: an event
# is the machine's own record rather than her words, but a wrong drop is worse
# than a wrong flag until the rate is known.
# The word boundary on `he` is load-bearing. Without it, `he\s+replied`
# matches inside "she replied" and her own answer is flagged as his contact --
# the same substring fault as `mom` inside `moment`, which this project has
# now paid for three times today.
_CONTACT_EN = [
    r"\bhe\s+(replied|answered|wrote|messaged|texted|responded)\b",
    r"\bhe\s+got\s+(in\s+touch|back\s+to\s+her)\b",
    r"\ba\s+(message|reply|text)\s+(from him|arrived|came)\b",
    r"\bmessage\s+from\s+him\b",
    r"\bhis\s+(reply|answer|message)\b",
]
_CONTACT_EN = [re.compile(p, re.I) for p in _CONTACT_EN]
_CONTACT_JA = ("返事が来", "返信が来", "連絡が来", "メッセージが来", "返事をくれ", "返ってき")


def claims_inbound_contact(text):
    """Does this event say the other person got in touch? Deterministic, both
    languages, no model."""
    s = str(text or "")
    if not s:
        return False
    if any(j in s for j in _CONTACT_JA):
        return True
    return any(p.search(s) for p in _CONTACT_EN)


def inbound_since(store, since):
    """Did a message from him actually arrive inside the window."""
    try:
        rows = store.recent_messages(30)
    except Exception:
        return True          # cannot tell, so do not accuse
    return any(r.get("role") == "user" and float(r.get("ts") or 0) >= since - 1 for r in rows)


def flag_restaged_contact(text, where, store=None, clock=None, window_minutes=120):
    """Log it and keep a row; never remove the event. True when flagged."""
    if not claims_inbound_contact(text):
        return False
    if store is None or clock is None:
        return False
    now = clock.now_ts()
    if inbound_since(store, now - window_minutes * 60):
        return False         # he really did write; the event is honest
    logger.log(f"[reconcile] FLAG: an event says he made contact and the record has none "
               f"in {window_minutes} minutes ({where}): {str(text)[:160]}")
    try:
        rows = list(store.get("flags", []) or [])
        rows.append({"ts": now, "date": clock.date_str(),
                     "what": "contact he did not make", "where": where,
                     "text": str(text)[:300]})
        store.set("flags", rows[-100:])
    except Exception:
        pass
    return True


class Action:
    """One thing she can do that leaves a real trace.

    `channel` is the scene field that legitimately carries it, or None when the
    scene has no way to perform it at all -- a director tick cannot send a
    message or publish a post, so prose claiming either is always wrong.
    """

    def __init__(self, name, cue, channel, truth, policy, instead):
        self.name = name
        self.cue = cue
        self.channel = channel
        self.truth = truth
        self.policy = policy
        self.instead = instead


def _messages_since(app, since):
    rows = app.store.recent_messages(30)
    return any(r["role"] == "assistant" and float(r["ts"]) >= since - 1 for r in rows)


def _spend_since(app, since):
    """Did money actually move inside this tick's window.

    The money log carries date and hm, not a timestamp, so the window has to be
    rebuilt from the clock. Comparing the date alone -- which this did -- means
    one konbini run in the morning answers True until midnight, and every false
    'she bought' after it passes unchallenged."""
    try:
        log = (app.money.m or {}).get("log", [])
    except Exception:
        return False
    today = app.clock.date_str()
    for row in reversed(log[-12:]):
        if str(row.get("date", "")) != today:
            continue
        hm = str(row.get("hm", ""))
        if ":" not in hm:
            continue
        try:
            h, m = (int(x) for x in hm.split(":")[:2])
        except ValueError:
            continue
        now = app.clock.now()
        when = now.replace(hour=h, minute=m, second=0, microsecond=0).timestamp()
        if when >= since - 60:
            return True
    return False


def _note_since(app, since):
    try:
        rows = app.store.recent_events(12)
    except Exception:
        return False
    return any(r["kind"] == "note_read" and float(r["ts"]) >= since - 1 for r in rows)


def _post_since(app, since):
    try:
        rows = app.store.recent_events(12)
    except Exception:
        return False
    return any(r["kind"] == "post" and float(r["ts"]) >= since - 1 for r in rows)


def _about_somebody_else(config, text):
    """Is this sentence about a cast member rather than about her? The
    reconcile actions are all about what SHE did -- sent, spent, posted, read
    -- and a beat's event line starts with the person who did it."""
    head = " ".join(str(text or "").split()[:2])
    if not head:
        return False
    from sim import roster
    for token in (head.split()[0], head):
        role = roster.role_of(config, token.strip(".,:;"))
        if role:
            return role != "self"
    return False


def actions(her="she"):
    return [
        Action(
            "sent_him_a_message",
            f"the scene says SHE ({her} herself, never one of her friends or family) sent, texted, "
            "replied to or messaged HIM, or quotes words of hers that went to him",
            None,
            _messages_since,
            "impossible",
            "she can draft, retype, hover over send and put the phone down -- but the scene cannot "
            "send it. Say what she did with the draft instead, and leave it unsent."),
        Action(
            "posted_on_x",
            "the scene says she posted, tweeted or put something on X",
            None,
            _post_since,
            "impossible",
            "posting is decided elsewhere and may be refused. Say she thought of posting, or opened "
            "X, and stop there."),
        Action(
            "spent_money",
            "the scene says she bought, paid for, or came away with something that costs money",
            "spent",
            _spend_since,
            "channel",
            "if she really buys it, put it in `spent` as {yen, on}. If she cannot afford it or it is "
            "not worth a line, say she looked at it and did not."),
        Action(
            "opened_his_note",
            "the scene says she opened, read or looked at one of his notes",
            "open_note",
            _note_since,
            "channel",
            "reading a note goes in `open_note` by name, and the code decides whether she gets it. "
            "Prose may say she thought about opening it."),
        Action(
            "ate",
            "the scene says she ate a meal or a snack",
            "ate",
            None,
            "channel",
            "eating goes in `ate` as \"meal\" or \"snack\" so her hunger actually moves."),
    ]


# The prompt lives in prompts/reconcile.txt like every other role, so the
# wording can be tightened without a code change.



class Reconcile:
    def __init__(self, config, store, llm, clock, typesafe=None):
        self.config = config
        self.store = store
        self.llm = llm
        self.clock = clock
        # the hosted classifier (`typesafe.py`): when her config turns the
        # `reconcile` use on, it answers which events claim an action, and the
        # model role is only asked to write the correction when one does
        self.typesafe = typesafe
        self.actions = actions(str(getattr(config.character, "name", "she") or "she"))

    def _log(self, entries):
        log = self.store.get("reconcile_log", []) or []
        log.extend(entries)
        keep = int(self.config.reconcile.log_keep)
        self.store.set("reconcile_log", log[-keep:])

    def check(self, app, scene, since_ts):
        """Correct any event in `scene` that claims an action the machine did
        not perform. Mutates scene["events"] in place and returns the number of
        corrections. Never raises: a check that fails must not cost a tick."""
        if not self.config.reconcile.enabled:
            return 0
        events = [e for e in (scene.get("events") or []) if str(e.get("text", "")).strip()]
        for e in events:
            flag_own_photo(e["text"], "scene event", self.store, self.clock)
        if not events:
            return 0
        try:
            return self._check(app, scene, events, since_ts)
        except Exception as e:
            logger.log(f"[reconcile] not checked: {type(e).__name__}: {e}")
            return 0

    def _typesafe_flags(self, events, satisfied):
        """Which events claim an action, as System One reads them: one `choice`
        per (event, action), over the actions that did not really happen and were
        not already declared through a channel. Returns the flagged
        (index, action) pairs, or None when the classifier could not answer and
        the model must decide as it did before."""
        use = self.typesafe.use("reconcile")
        questions, pairs = {}, []
        for i, e in enumerate(events):
            for a in self.actions:
                if a.name in satisfied:
                    continue
                qid = "%s__%d" % (a.name, i)
                questions[qid] = {
                    "type": "choice",
                    "instructions": "Does `events[%d]` say %s?" % (i, a.cue),
                    "criteria": {"claims": "The event asserts this action",
                                 "does_not": "The event does not assert this action"},
                }
                pairs.append((qid, i, a.name))
        if not questions:
            return []
        answers = self.typesafe.ask(
            "reconcile", {"events": [e.get("text", "") for e in events]}, questions)
        if answers is None:
            return None
        floor = float((use or {}).get("threshold", 0.5))
        flags = []
        for qid, i, name in pairs:
            choice, conf = self.typesafe.choice(answers, qid)
            if choice == "claims" and conf >= floor:
                flags.append((i, name))
        return flags

    def _detect(self, app, scene, events, since_ts):
        """The raw detector: returns the model's violation rows for these
        events. Shared by the first pass and by the check on its own output.

        System One answers first when her config turns the use on: one choice
        per (event, action), over the actions that did not really happen and were
        not declared. Nothing flagged means the model role is not asked at all,
        which is the common tick. A classifier that could not answer returns
        None and the model decides, exactly as it did before (`typesafe.py`)."""
        # what really happened, and what the scene declared through a channel
        truth, declared, satisfied = [], [], []
        for a in self.actions:
            did = False
            if a.truth is not None:
                try:
                    did = bool(a.truth(app, since_ts))
                except Exception:
                    did = False
            chan = scene.get(a.channel) if a.channel else None
            has_chan = bool(chan)
            if did or has_chan:
                satisfied.append(a.name)
            if has_chan:
                declared.append(f"  {a.name}: the scene set `{a.channel}` -- this one is legitimate")
            truth.append(f"  {a.name}: really happened this window = {did or has_chan}")

        if self.typesafe is not None and self.typesafe.ready("reconcile"):
            flags = self._typesafe_flags(events, set(satisfied))
            if flags is not None:
                if not flags:
                    logger.log(f"[reconcile] typesafe: {len(events)} event(s), nothing claimed; "
                               "the model is not asked")
                    return []
                logger.log(f"[reconcile] typesafe: {len(flags)} claim(s) flagged; the model writes the correction")

        catalogue = "\n".join(
            f"  {a.name}: {a.cue}\n      if wrongly claimed -> {a.instead}" for a in self.actions)
        ev_txt = "\n".join(f"  [{i}] {e['text']}" for i, e in enumerate(events))
        user = (f"ACTIONS TO CHECK FOR:\n{catalogue}\n\n"
                f"WHAT REALLY HAPPENED:\n" + "\n".join(truth) + "\n"
                + ("\n".join(declared) + "\n" if declared else "")
                + f"\nTHE SCENE'S EVENTS:\n{ev_txt}\n")
        data, _ = self.llm.call_json("reconcile",
                                     [{"role": "system", "content": self.config.prompt_text("reconcile")},
                                      {"role": "user", "content": user}])
        rows = (data or {}).get("violations") if isinstance(data, dict) else None
        return rows if isinstance(rows, list) else []

    def _check(self, app, scene, events, since_ts):
        rows = self._detect(app, scene, events, since_ts)
        if not rows:
            return 0

        by_name = {a.name: a for a in self.actions}
        fixed, entries, drop = 0, [], set()
        for r in rows:
            if not isinstance(r, dict):
                continue
            i = r.get("index")
            a = by_name.get(str(r.get("action", "")))
            new = str(r.get("fixed", "")).strip()
            if not isinstance(i, int) or not (0 <= i < len(events)) or a is None or not new:
                continue
            old = events[i]["text"]
            if new == old:
                continue
            if _about_somebody_else(self.config, old):
                # "Rena sent another sticker about her fringe" was rewritten to
                # "Rena thought about sending ... but she didn't", which is a
                # true thing about her friend turned into a false one. Every
                # action here is about what SHE did; a sentence whose subject
                # is another person on the roster is not hers to be corrected.
                logger.log(f"[reconcile] {a.name}: that sentence is about "
                           f"{old.split()[0]}, not her; left alone")
                continue
            # the correction is another model assertion, so it does not get
            # trusted either: back through the same detector once, and if it
            # still claims something that did not happen the event is dropped.
            if self._still_claims(app, scene, new, since_ts):
                logger.log(f"[reconcile] {a.name}: the rewrite still claimed it; dropping the event")
                drop.add(i)
                entries.append({"ts": self.clock.now_ts(), "date": self.clock.date_str(),
                                "hm": self.clock.hm(), "action": a.name, "policy": a.policy,
                                "was": old[:300], "now": "(dropped: the rewrite still claimed it)"})
                fixed += 1
                continue
            events[i]["text"] = new
            fixed += 1
            entries.append({"ts": self.clock.now_ts(), "date": self.clock.date_str(),
                            "hm": self.clock.hm(), "action": a.name, "policy": a.policy,
                            "was": old[:300], "now": new[:300]})
            if a.policy == "channel":
                logger.log(f"[reconcile]   it had a channel for this (`{a.channel}`) and did not use it")
            logger.log(f"[reconcile] {a.name}: the scene claimed it and the machine did not do it")
            logger.log(f"[reconcile]   was: {old[:110]}")
            logger.log(f"[reconcile]   now: {new[:110]}")
        if drop:
            scene["events"] = [e for j, e in enumerate(scene.get("events") or [])
                               if j not in drop]
        if entries:
            self._log(entries)
        return fixed

    def _still_claims(self, app, scene, text, since_ts):
        """Run one corrected sentence back through the detector. True means the
        rewrite is no better than what it replaced."""
        try:
            n = self._detect(app, scene, [{"text": text}], since_ts)
        except Exception:
            return False
        return bool(n)

    def report(self, n=20):
        log = self.store.get("reconcile_log", []) or []
        if not log:
            return "nothing has been corrected yet."
        counts = {}
        for e in log:
            counts[e.get("action", "?")] = counts.get(e.get("action", "?"), 0) + 1
        out = [f"{len(log)} correction(s) on record, by action:"]
        for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
            out.append(f"  {v:>3}  {k}")
        out.append("")
        out.append(f"the last {min(n, len(log))}:")
        for e in log[-n:]:
            out.append(f"  {e.get('date', '')} {e.get('hm', '')}  {e.get('action', '')}")
            out.append(f"      was: {str(e.get('was', ''))[:100]}")
            out.append(f"      now: {str(e.get('now', ''))[:100]}")
        return "\n".join(out)
