import threading
import queue
import time
import random
import logger
import netwatch
from sim import wiring

# Outbound bubbles go through here so the main loop never sleeps on a send.
# Each bubble gets a typing delay proportional to its length; the wall-clock
# delay is scaled by the world clock so sim runs stay fast.


class Delivery:
    # her account (a program's, None for a character without one): asked
    # whether a bubble that has just left was one of its posts; her voice,
    # asked for the prompt the reply that is leaving was drawn from
    WIRES = ('social', 'persona')

    def __init__(self, config, clock, store, tg, tts=None):
        self.config = config
        self.clock = clock
        self.store = store
        self.tg = tg
        self.tts = tts
        self.offline_wait_seconds = config.delivery.offline_wait_seconds
        self.send_attempts = config.delivery.send_attempts
        self.send_retry_seconds = config.delivery.send_retry_seconds
        self.q = queue.Queue()
        self.pending = 0
        self.withhold = ""      # set (to a reason) and nothing leaves: a replay is not a conversation
        self._lock = threading.Lock()
        self._strand()
        wiring.declare(self)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _outbox(self, bubbles):
        """The bubbles composed and not yet gone, in the save.

        A bubble reaches the `messages` table only after it has actually left,
        and the queue in front of that is a `queue.Queue`, so a stop between
        composing and sending used to lose the whole burst with nothing
        anywhere to show for it -- no row, no event, a persona line in the log
        with no send under it."""
        try:
            self.store.set("outbox", list(bubbles))
        except Exception as e:
            logger.log(f"[delivery] the outbox was not kept: {type(e).__name__}: {e}")

    def _strand(self):
        """Bubbles the last process composed and never sent.

        They are NOT sent now. She wrote them for a minute -- what she was
        doing, what he had just said, how present he was -- and putting them
        into a conversation that has moved on answers a moment that has gone.
        What this owes is the trace: the record says she nearly said it and
        did not, so nothing downstream believes she said a thing he never
        saw, and the hole is visible instead of silent."""
        try:
            left = list(self.store.get("outbox", []) or [])
        except Exception:
            return
        if not left:
            return
        self.store.set("outbox", [])
        ts = self.clock.now_ts()
        try:
            self.store.add_event(ts, self.clock.date_str(ts), "unsent",
                                 "she had written this and it never left: "
                                 + " // ".join(str(b)[:80] for b in left), 1)
        except Exception as e:
            logger.log(f"[delivery] the stranded bubbles were not recorded: {type(e).__name__}: {e}")
        logger.log(f"[delivery] {len(left)} bubble(s) from the last run never left and are not being sent now: "
                   + " // ".join(str(b)[:60] for b in left))

    def typing_seconds(self, text):
        d = self.config.delivery
        s = len(text) * d.typing_seconds_per_char
        s *= random.uniform(0.7, 1.3)
        return max(d.typing_min_seconds, min(d.typing_max_seconds, s))

    def send_bubbles(self, bubbles, self_started, lead_seconds=0, voice="", media="",
                     voice_lines=None):
        """Queue bubbles. lead_seconds is character-time delay before the first one.
        voice is a short spoken line sent as a voice note after the last bubble.

        `voice_lines` is the stage's own voicing: when it is not None, every
        bubble in it is synthesised as it is sent and the clip is attached to
        that bubble, so the reader can advance line by line and hear each. It is
        the same on-demand path the ♪ uses, and the caller passes it only when
        the stage's voice toggle is on."""
        if not bubbles:
            return
        if self.withhold:
            logger.log(f"[delivery] withheld ({self.withhold}) {len(bubbles)} bubble(s): " + " // ".join(b[:60] for b in bubbles))
            return
        with self._lock:
            self.pending += len(bubbles)
        self._outbox(bubbles)
        # when she started saying it, so a message of his that was already
        # sitting there does not count as cutting in
        # media is a photo path that goes out before the first bubble (tomoe/scenery.py)
        # the prompt these words were drawn from rides with them: taken here,
        # on the loop thread, one statement after the draft, so it cannot be
        # the prompt of a reply that was composed while this burst waited
        self.q.put(("batch", bubbles, self_started, lead_seconds, voice, self.clock.now_ts(), media,
                    self._prompt_for(bubbles), voice_lines))

    def _voice_bubble(self, line, mid, path=None):
        """Speak one bubble of a reply, attached to the line it belongs to.

        The stage voices every line of hers, one clip per bubble, so the reader
        can advance line by line and hear each as it comes. The reply path has
        already made the clip (`render_wait`), so `path` is the prepared file and
        it is attached at once; the ♪ path still renders on demand. The clip
        carries the bubble's hub id so a clip that lands after the next bubble
        was published still belongs to its own line
        (`channels/vn_bot.py:_attach_audio`)."""
        try:
            if path:
                self.tg.send_voice(path, attach_to=mid)
                return
            self.tts.speak_on_demand(
                line, lambda path, _id=mid: self.tg.send_voice(path, attach_to=_id))
        except Exception as e:
            logger.log(f"[voice] bubble not voiced: {type(e).__name__}: {e}")

    def _prompt_for(self, bubbles):
        """The persona's record of the call these bubbles came out of -- and
        only when they ARE those bubbles.

        `/send <text>`, a replaced reply and a photo caption go through
        `send_bubbles` too, and filing one of those under the last reply's
        prompt would offer a swipe that redraws something else entirely."""
        p = getattr(self.persona, "last_reply_prompt", None) if self.persona else None
        if not p or list(p.get("bubbles") or []) != list(bubbles):
            return None
        return p

    def _char_id(self):
        return "".join(str(self.config.character.name).lower().split())

    def _freeze(self, prompt, mid, anchor):
        """The reply's own prompt, against the row the first bubble made.

        Written as each bubble lands rather than when the burst ends: a stop
        is `Stop-Process -Force`, and a paid answer held in a local until the
        end of a loop is a paid answer lost. The first row is the anchor and
        every row of the burst is named on it, so a swipe asked for on the
        third bubble finds the same prompt as one asked for on the first.
        Returns the anchor."""
        try:
            ts = self.clock.now_ts()
            if anchor is None:
                text = "\n\n".join(prompt.get("bubbles") or [])
                model = str(prompt.get("model") or "")
                u = prompt.get("usage") or {}
                self.store.add_reply_prompt(mid, self._char_id(), ts, model,
                                            prompt.get("messages") or [],
                                            prompt.get("params") or {}, [mid], text)
                # what she actually sent is candidate 0, so the arrows in the
                # chat start from the real reply rather than from a draw
                self.store.add_swipe(mid, 0, model, text, voice_path="", ts=ts,
                                     prompt_tokens=int(u.get("prompt_tokens") or 0),
                                     completion_tokens=int(u.get("completion_tokens") or 0),
                                     cached_tokens=cached_of(u),
                                     cost=cost_of(slug_of(self.config, str(prompt.get("provider") or ""), model), u))
                return mid
            self.store.extend_reply_prompt(anchor, mid)
        except Exception as e:
            logger.log(f"[swipe] the reply's own prompt was not kept: {type(e).__name__}: {e}")
        return anchor

    def _cut_in(self, queued_ts):
        """Anything unread from him that arrived after she started talking."""
        if not self.config.delivery.interruptible:
            return False
        try:
            return any(m["ts"] > queued_ts for m in self.store.unread_user_messages())
        except Exception:
            return False

    def busy(self):
        with self._lock:
            return self.pending > 0

    def _note_share(self, text, ts):
        """A bubble that has left, offered to her account: if it was a post
        of hers it is recorded as sent now, with the event."""
        if not self.social:
            return
        try:
            k = self.social.note_sent(text)
            if k:
                # what she saw rides with it: the record of a send used to be
                # the handle and the caption, so a picture she had opened was
                # gone by the time he asked what it was
                pics = "; ".join(str(m.get("subject") or "") for m in (k.get("media") or [])
                                 if m.get("subject"))[:160]
                what = f"@{k['author']}: {k['text'][:80]}" + (f" -- the picture: {pics}" if pics else "")
                self.store.add_event(ts, self.clock.date_str(ts), "share",
                                     f"she sent him a post from X: {what}", 2)
                logger.log(f"[share] {k['url']} -- {what}")
        except Exception as e:
            logger.log(f"[share] not recorded: {type(e).__name__}: {e}")

    def _run(self):
        while True:
            item = self.q.get()
            kind, bubbles, self_started, lead, voice, queued_ts = item[:6]
            media = item[6] if len(item) > 6 else ""
            prompt = item[7] if len(item) > 7 else None
            voice_lines = item[8] if len(item) > 8 else None
            anchor = None
            try:
                # Her voice for the whole reply is made before the first line is
                # shown: every clip is prepared up front, so advancing through
                # the lines never waits on synthesis and the ready mark can mean
                # the whole reply is ready. There is no typing delay: a visual
                # novel shows the line when it is ready, not while it is typed
                # (2026-09-17).
                voice_paths = {}
                if voice_lines is not None and self.tts:
                    take_cue = getattr(self.tg, "take_vocal_cue", None)
                    vocal_cue = take_cue() if callable(take_cue) else ""
                    cue_used = False
                    for b in bubbles:
                        label = None
                        provider = getattr(self.tg, "emotion_provider", None)
                        if callable(provider):
                            try:
                                label = provider(b)
                                prepare = getattr(self.tg, "prepare_emotion", None)
                                if callable(prepare) and label:
                                    prepare(b, label)
                            except Exception as e:
                                logger.log(f"[delivery] voice emotion unavailable: {type(e).__name__}")
                        clip = self.tts._clip_for(b) if vocal_cue and not cue_used else None
                        tag = vocal_cue if vocal_cue and not cue_used and not clip else ""
                        p = self.tts.render_wait(b, emotion=label, interjection=tag)
                        if tag and p:
                            cue_used = True
                        if p:
                            voice_paths[b] = p
                if lead > 0:
                    time.sleep(self.clock.wall_seconds(lead))
                if media:
                    if not self.tg.send_photo(media):
                        logger.log(f"[delivery] photo not sent: {media}")
                for i, b in enumerate(bubbles):
                    # he said something while she was still talking. She stops;
                    # what she had not sent yet is simply never said, and she
                    # never refers to it, because she did not say it.
                    if i and self._cut_in(queued_ts):
                        left = len(bubbles) - i
                        with self._lock:
                            self.pending -= left
                        logger.log(f"[delivery] he cut in after {i} bubble(s); {left} never sent: "
                                   + " // ".join(x[:60] for x in bubbles[i:]))
                        voice = ""
                        break
                    # Telegram times out often enough that one attempt is not
                    # a send. Retry before giving up, and only call it
                    # delivered if it actually left: on 2026-08-20 a bubble
                    # timed out, was stored with delivered_ts set anyway, and
                    # she went on believing he had it.
                    # A dead link is not a failed message. Wait for it rather
                    # than spending the retries and calling it undelivered.
                    waited = 0
                    while netwatch.WATCH.offline() and waited < self.offline_wait_seconds:
                        time.sleep(5)
                        waited += 5
                    ok = False
                    for attempt in range(self.send_attempts):
                        ok = self.tg.send_message(b)
                        if ok:
                            break
                        if attempt + 1 < self.send_attempts:
                            time.sleep(self.send_retry_seconds * (attempt + 1))
                            logger.log(f"[send retry {attempt + 2}/{self.send_attempts}] {b[:80]}")
                    ts = self.clock.now_ts()
                    # keep Telegram's id for her bubble so it can be edited
                    # or deleted later; True means console mode, not an id
                    tg_id = ok if isinstance(ok, int) and not isinstance(ok, bool) else None
                    mid = self.store.add_message(ts, self.clock.date_str(ts), "assistant", b,
                                                 self_started=1 if self_started else 0,
                                                 delivered_ts=ts if ok else None, tg_id=tg_id,
                                                 dedupe=bool(getattr(self.tg, "MSG_ID_UNIQUE", False)))
                    if prompt and mid:
                        anchor = self._freeze(prompt, mid, anchor)
                    # every line of hers is voiced when the stage's voice toggle
                    # is on: one clip per bubble, attached to that bubble. The
                    # key is the hub id the channel knows as `turn_id`, not the
                    # store row id: keyed by the row id the clip never matched
                    # the turn on screen and nothing played (2026-09-17).
                    if ok and mid and voice_lines is not None and self.tts:
                        self._voice_bubble(b, tg_id if tg_id else mid, voice_paths.get(b))
                    self._outbox(bubbles[i + 1:])
                    # A later Jump may branch here. The VN channel takes a
                    # compressed copy after this bubble and the remaining
                    # outbox are both recorded, never before the send.
                    checkpoint = getattr(self.tg, "checkpoint_line", None)
                    if ok and mid and callable(checkpoint):
                        checkpoint(tg_id, mid)
                    if ok:
                        logger.log(f"[sent {'(self)' if self_started else ''}] {b[:120]}")
                        # a post of hers is recorded as sent here, as it
                        # goes, never while the reply was drafted
                        self._note_share(b, ts)
                    else:
                        logger.log(f"[send failed after {self.send_attempts}] {b[:120]}")
                    with self._lock:
                        self.pending -= 1
                self._outbox([])
                if voice and self.tts:
                    self.tts.enqueue(voice)
            except Exception as e:
                logger.log(f"[delivery] error: {e}")
                with self._lock:
                    self.pending = max(0, self.pending - len(bubbles))


# ---------------------------------------------------------------------------
# Swiping a reply: the same call again, and choosing which answer stands.
#
# A swipe re-runs the prompt the reply was DRAWN from, byte for byte, on
# whichever model the chat is toggled to. It is not a new reply. By the time
# he asks, her gauges have decayed, the director has written another scene and
# the thread has grown; a prompt rebuilt at that moment would answer a
# different question and would quietly rewrite what she was answering. So the
# messages array is frozen at reply time (`store.reply_prompts`) and a swipe
# sends exactly that.
#
# Viewing a candidate changes nothing at all -- it is a read of
# `store.swipes`. Sitting one is the only write: the rows of that burst in her
# save take the candidate's text through the same path a hand correction uses
# (`/context msg set`), the hub's copies are edited so his phone agrees, the
# voice note is re-rendered for the new words, and because `sim/thread.py`
# rebuilds the thread from the store on every call, the next reply carries the
# version he sat and no other. A candidate nobody sat is in no prompt
# anywhere.
#
# These are functions over the App rather than a class of their own, the way
# `sim/inflight.py` settles the jobs a dead process left: they need her voice,
# her model client, her store and her channel at once, and none of them owns
# the others.


def slug_of(config, provider, name):
    """The slug a model NAME goes out as at this provider. A name the
    provider has no entry for goes out as a literal, which is what the map
    is for."""
    provider = provider or (config.raw["api"].get("provider") or "")
    p = ((config.raw["api"].get("providers") or {}).get(provider) or {})
    return ((p.get("models") or {}).get(name) or name)


def cached_of(usage):
    """The part of the prompt the host answered from its cache. On the same
    model a swipe's prompt is byte-identical to the original's, so this
    should be nearly all of it; on a different model it is zero, and the
    number is here so that is visible rather than assumed."""
    d = (usage or {}).get("prompt_tokens_details") or {}
    return int(d.get("cached_tokens") or 0)


def cost_of(slug, usage):
    """What one call cost, from the same price table `/stats` uses. The
    host's own figure wins when it reports one."""
    u = usage or {}
    if u.get("cost"):
        return float(u["cost"])
    try:
        from tools.llmstats import OPENROUTER
        price = OPENROUTER.get(slug)
    except Exception:
        price = None
    if not price:
        return 0.0
    ins, out = int(u.get("prompt_tokens") or 0), int(u.get("completion_tokens") or 0)
    cached = cached_of(u)
    return (max(0, ins - cached) * price[0] + cached * price[2] + out * price[1]) / 1e6


def to_bubbles(app, text):
    """One answer split the way a reply is split.

    The spoken line is lifted out and the draft cleaned with the persona's own
    two pure passes, so a candidate is shaped exactly like the reply it stands
    beside. The persona's `_split` is deliberately NOT used: it also lifts a
    sticker out, banks a search she asked for and resolves a shared post,
    which are things a reply does on its way out and a candidate he is only
    looking at must not do."""
    out, voice = app.persona._extract_voice(text or "")
    out = app.persona._clean(out)
    if not app.config.delivery.split_on_blank_lines:
        return ([out] if out else []), voice
    from persona.persona import split_bubbles
    return split_bubbles(out), voice


def resolve(app, msg_id):
    """(the anchor row's id, the frozen prompt) for an id that may be either
    the hub's or the record's.

    The app knows hub ids and the record knows its own, and 141 in the store
    was 1813 on the hub. The hub's id is tried FIRST, because the app is what
    asks; a plain record id still works from the ops bar."""
    mid = int(msg_id)
    row = app.store.message_by_tg_id(mid)
    if row is None:
        row = app.store.message_by_id(mid)
    if row is None:
        return None, None
    got = app.store.reply_prompt_for(row["id"])
    return row, got


def swipe(app, msg_id, model=""):
    """Draw the reply again, on the model the chat is toggled to.

    Returns a line for the ops log. The answer is written to her save the
    moment it exists, before it is shown anywhere."""
    row, got = resolve(app, msg_id)
    if row is None:
        return f"no message {msg_id} in her record"
    if got is None:
        return (f"message {row['id']} has no kept prompt, so there is nothing to draw again. "
                "Only replies sent since the swipe machinery went in have one.")
    anchor = int(got["msg_id"])
    name = model or app.llm.effective_model("persona")
    provider = app.llm.active_provider()
    # the ORIGINAL sampling settings, and this model. `_model` is passed, so
    # the toggle is not applied twice and the frozen temperature and effort
    # are what they were, not what the config says today
    m = dict(app.config.model("persona"))
    m.update({k: v for k, v in (got.get("params") or {}).items()
              if k in ("temperature", "thinking", "effort", "max_tokens")})
    m["model"] = name
    n = app.store.next_swipe_n(anchor)
    logger.log(f"[swipe] message {anchor}: drawing answer {n} again on {name} "
               f"({len(got.get('messages') or [])} messages, frozen at reply time)")
    text = (app.llm.call("persona", got["messages"], _model=m, _provider=provider) or "").strip()
    if not text:
        return f"{name} gave no answer; nothing kept (the call is in missed_calls)"
    u = dict(getattr(app.llm, "last_usage", None) or {})
    bubbles, voice = to_bubbles(app, text)
    joined = "\n\n".join(bubbles)
    cost = cost_of(slug_of(app.config, provider, name), u)
    app.store.add_swipe(anchor, n, name, joined, voice_path="", ts=app.clock.now_ts(),
                        prompt_tokens=int(u.get("prompt_tokens") or 0),
                        completion_tokens=int(u.get("completion_tokens") or 0),
                        cached_tokens=cached_of(u), cost=cost)
    push(app, anchor)
    return (f"answer {n} on {name}: " + " // ".join(b[:80] for b in bubbles)
            + (f" | aloud: {voice}" if voice else "")
            + f"\n  in {u.get('prompt_tokens', 0)} ({cached_of(u)} of it out of the host's cache), "
            f"out {u.get('completion_tokens', 0)}, ${cost:.5f}"
            + f"\n  /sit {anchor} {n} to make this the one the conversation goes on from")


def report(app, msg_id=0):
    """What has been drawn for one reply, or which replies can be drawn again."""
    if not msg_id:
        ids = app.store.reply_prompt_ids(12)
        if not ids:
            return "no reply has a kept prompt yet"
        out = ["replies that can be drawn again (newest first): id, answers, which one is sitting"]
        for i in ids:
            got = app.store.reply_prompt(i) or {}
            cands = app.store.swipes_for(i)
            out.append(f"  {i}: {len(cands)} answer(s), sitting {int(got.get('sat') or 0)}, "
                       f"drawn on {got.get('model', '?')} -- {str(got.get('text', ''))[:70]}")
        out.append("/swipe <id> draws another; /sit <id> <n> chooses one")
        return "\n".join(out)
    row, got = resolve(app, msg_id)
    if got is None:
        return f"no kept prompt for message {msg_id}"
    anchor = int(got["msg_id"])
    sat = int(got.get("sat") or 0)
    out = [f"message {anchor} (rows {got.get('msg_ids')}), drawn on {got.get('model', '?')}, "
           f"sitting: {sat}"]
    for c in app.store.swipes_for(anchor):
        out.append(f"  [{c['n']}]{' <- sitting' if c['n'] == sat else ''} {c['model']} "
                   f"in={c['prompt_tokens']} cached={c['cached_tokens']} out={c['completion_tokens']} "
                   f"${float(c['cost'] or 0):.5f}\n      " + str(c["text"]).replace("\n", " / ")[:400])
    return "\n".join(out)


def sit(app, msg_id, n):
    """Make one candidate the version the conversation goes on from.

    Her rows take its text through the same path a hand correction uses, the
    hub's copies are edited so his phone shows what her record holds, and the
    voice note on a row that had one is re-rendered for the new words the way
    `tools/replace_reply.py` does it."""
    row, got = resolve(app, msg_id)
    if got is None:
        return f"no kept prompt for message {msg_id}"
    anchor = int(got["msg_id"])
    n = int(n)
    cands = {int(c["n"]): c for c in app.store.swipes_for(anchor)}
    if n not in cands:
        return f"message {anchor} has no answer {n} (it has {sorted(cands)})"
    bubbles, voice = to_bubbles(app, cands[n]["text"])
    if not bubbles:
        return f"answer {n} has no words in it; nothing sat"
    rows = [app.store.message_by_id(i) for i in (got.get("msg_ids") or [anchor])]
    rows = [r for r in rows if r]
    if not rows:
        return f"the rows of message {anchor} are gone from her record"
    # One candidate onto the rows the burst already has, in order: the shape
    # is kept where the counts agree, which is nearly always (one bubble).
    # A longer answer folds its surplus into the last row rather than adding
    # one, because a new row would be stamped now and would sort after
    # everything he has said since. A shorter one drops the rows it does not
    # need, from her record and from the hub both.
    keep = min(len(bubbles), len(rows))
    texts = list(bubbles[:keep])
    if len(bubbles) > len(rows):
        texts[-1] = "\n\n".join(bubbles[keep - 1:])
    out = [f"answer {n} ({cands[n]['model']}) is now what the conversation goes on from"]
    voiced = _hub_voices(app, [r.get("tg_id") for r in rows])
    for r, t in zip(rows, texts):
        app.ctx.message_set(r["id"], t)
        if r.get("tg_id"):
            app.tg.edit_message(r["tg_id"], t)
        out.append(f"  store {r['id']} / hub {r.get('tg_id')}: {t[:80]}")
    for r in rows[keep:]:
        app.ctx.message_del(r["id"])
        if r.get("tg_id"):
            app.tg.delete_message(r["tg_id"])
        out.append(f"  store {r['id']} / hub {r.get('tg_id')}: dropped, this answer is shorter")
    show_selected = getattr(app.tg, "show_selected_reply", None)
    if callable(show_selected) and rows[keep - 1].get("tg_id"):
        show_selected(rows[keep - 1]["tg_id"], texts[-1])
    app.store.sit_swipe(anchor, n)
    # the note attached to a row is the OLD words spoken; a hub edit changes
    # the text and leaves the audio, so it is rendered again for what the row
    # now says (`tools/replace_reply.py`, the same three steps)
    if app.tts and app.config.tts.enabled:
        for r, t in zip(rows, texts):
            if not (r.get("tg_id") and voiced.get(int(r["tg_id"]))):
                continue
            try:
                path = app.tts.render(voice or t)
                if path:
                    app.tg.send_voice(path, attach_to=int(r["tg_id"]))
                    out.append(f"  the voice note on hub {r['tg_id']} was rendered again")
                else:
                    out.append(f"  the voice note on hub {r['tg_id']} could not be rendered; the old one stays")
            except Exception as e:
                out.append(f"  the voice note on hub {r['tg_id']} was not touched: {type(e).__name__}")
    push(app, anchor)
    logger.log(f"[swipe] answer {n} sat on message {anchor}: " + " // ".join(t[:60] for t in texts))
    return "\n".join(out)


def _hub_voices(app, hub_ids):
    """Which of these rows the hub has audio on, so only those are rendered
    again."""
    rows = getattr(app.tg, "hub_rows", None)
    if not rows:
        return {}
    try:
        return {int(m["id"]): str(m.get("voice") or "") for m in (rows() or [])
                if m.get("voice") and int(m["id"]) in {int(i) for i in hub_ids if i}}
    except Exception:
        return {}


def push(app, anchor):
    """The candidates for one reply, up to the hub, so the arrows and the
    counter in the chat show them. The hub keeps them beside its own copy of
    the message the way it keeps the ops payload."""
    send = getattr(app.tg, "post_swipes", None)
    if not send:
        return
    got = app.store.reply_prompt(anchor) or {}
    row = app.store.message_by_id(anchor) or {}
    if not row.get("tg_id"):
        return
    items = [{"n": int(c["n"]), "model": c["model"], "text": c["text"],
              "ts": c["ts"], "in": int(c["prompt_tokens"] or 0),
              "cached": int(c["cached_tokens"] or 0),
              "out": int(c["completion_tokens"] or 0),
              "cost": round(float(c["cost"] or 0), 6)}
             for c in app.store.swipes_for(anchor)]
    try:
        send(int(row["tg_id"]), items, int(got.get("sat") or 0),
             rows=[int(i) for i in (got.get("msg_ids") or [])])
    except Exception as e:
        logger.log(f"[swipe] the hub was not told: {type(e).__name__}: {e}")
