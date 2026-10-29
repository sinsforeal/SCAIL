# -*- coding: utf-8 -*-
"""The TALKAPP channel: same surface as TelegramInterface, backed by the hub.

The hub (talkapp/server.py) is a separate process on localhost; his phone
reaches it over Tailscale. This adapter is deliberately synchronous requests,
like the Telegram one, because the loop already polls.

Two things ride along on the poll, because the loop calls get_new_messages
every pass (and between bubbles, for interruption):
- his exact reads come back from the hub and are stamped onto her messages
  with store.mark_read -- receipts.py already prefers a stamped read_ts over
  its window inference, so no receipts change is needed;
- her reads of his messages, the group chat as she sees it, and one presence
  line are pushed up (throttled), which is what makes her 既読 real on his
  screen.
"""
import hashlib
from sim import wiring
import json
import os
import shutil
import time
import requests
import logger
import netwatch
from sim import schedule


from channels.base import Channel


class TalkappInterface(Channel):
    def __init__(self, config, vision=None, clock=None, store=None):
        t = config.talkapp
        self.config = config
        self.base = f"http://{t.host}:{t.port}"
        self.key = t.token
        self.char = "".join(config.character.name.lower().split())
        self.name = config.character.name
        self.store = store
        self.clock = clock
        self.vision = vision  # kept for surface parity; the hub is text-only for now
        self.console_only = config.telegram.console_only
        self.max_length = config.telegram.max_message_length
        self.active_chat_id = "talkapp"   # read by scail for "is a chat bound"
        self.ops_provider = None          # set by scail: () -> dict for the app's ops view
        self.reaction_provider = None     # set by scail: () -> {file, bucket, ts} or None, her face in the app
        self.last_update_id = int((store.get("talkapp_last_id", 0) if store else 0) or 0)
        self._last_state_push = 0.0
        self._group_digest = None
        wiring.declare(self)

    # ---------------- plumbing ----------------

    # Every URL this builds carries `key=<the hub token>`, and a requests
    # exception quotes the URL it failed on. So a failure is logged by TYPE
    # and never by text: the first hub bounce after the speak poll went in
    # wrote the token into session.log.
    def _get(self, path, **params):
        params["key"] = self.key
        r = requests.get(self.base + path, params=params, timeout=10)
        r.raise_for_status()
        return r.json()

    def _post(self, path, body):
        r = requests.post(self.base + path, params={"key": self.key}, json=body, timeout=15)
        r.raise_for_status()
        return r.json()

    # ---------------- the TelegramInterface surface ----------------

    def verify_connection(self):
        if self.console_only:
            logger.log("[talkapp] console-only mode, no connection")
            return True
        try:
            self._get("/health")
            history = []
            if self.store and self.clock:
                for m in self.store.recent_messages(200):
                    history.append({"role": "him" if m["role"] == "user" else "her",
                                    "text": m["text"], "ts": m["ts"],
                                    "read_ts": m.get("read_ts"), "tg_id": m.get("tg_id")})
            res = self._post("/bot/register", {"char": self.char, "name": self.name,
                                               # whether the app should draw a
                                               # speaker on her lines: her own
                                               # config decides, so the hub
                                               # never has to know who is who
                                               "speak": bool(self.config.tts.enabled
                                                             and getattr(self.config.tts, "on_demand", False)),
                                               # a character with no contact
                                               # with him registers so the
                                               # rooms can ask her, and his
                                               # phone does not list her
                                               "hidden": str(getattr(self.config.character.existence, "with_him", "chat")
                                                             or "chat").lower() == "none",
                                               "history": history})
            # imported rows came FROM this bot's own store: never re-deliver
            # them as new messages. A message he sends while the bot is down
            # gets a higher id and still arrives.
            if res.get("imported"):
                self.last_update_id = max(self.last_update_id, int(res.get("head", 0)))
                if self.store:
                    self.store.set("talkapp_last_id", self.last_update_id)
            logger.log(f"[talkapp] registered '{self.char}' at {self.base}")
            return True
        except Exception as e:
            logger.log(f"[talkapp] hub unreachable: {type(e).__name__}")
            return False

    def flush_queue(self):
        # Telegram discards its stale update queue on boot; here a message he
        # sent while the bot was down is real and must be delivered, so this
        # is deliberately nothing.
        return

    def get_new_messages(self):
        """Returns list of (text, message_id). Also syncs reads both ways."""
        if self.console_only:
            return []
        try:
            data = self._get("/bot/updates", char=self.char, after=self.last_update_id)
            netwatch.WATCH.ok("talkapp")
        except Exception as e:
            netwatch.WATCH.fail("talkapp", str(e))
            return []
        out = []
        for m in data.get("messages", []):
            self.last_update_id = max(self.last_update_id, int(m["id"]))
            if self.store:
                self.store.set("talkapp_last_id", self.last_update_id)
            out.append((m["text"], m["id"]))
        self._sync_reads()
        return out

    def send_typing(self):
        if self.console_only:
            return
        try:
            self._post("/bot/typing", {"char": self.char})
        except Exception:
            pass

    def send_message(self, text):
        if not text or not text.strip():
            return False
        if self.console_only:
            try:
                print(f"\n>>> {self.name.upper()}: {text}\n")
            except UnicodeEncodeError:
                print(f"\n>>> {self.name.upper()}: {text.encode('ascii', 'replace').decode()}\n")
            return True
        try:
            res = self._post("/bot/send", {"char": self.char, "text": text})
            netwatch.WATCH.ok("talkapp")
            return res.get("id") or True
        except Exception as e:
            netwatch.WATCH.fail("talkapp", str(e))
            return False

    def delete_message(self, message_id):
        if self.console_only or not message_id:
            return False
        try:
            return bool(self._post("/bot/delete", {"char": self.char, "id": int(message_id)}).get("ok"))
        except Exception as e:
            netwatch.WATCH.fail("talkapp", str(e))
            return False

    def edit_message(self, message_id, text):
        if self.console_only or not message_id:
            return False
        try:
            return bool(self._post("/bot/edit", {"char": self.char, "id": int(message_id), "text": text}).get("ok"))
        except Exception as e:
            netwatch.WATCH.fail("talkapp", str(e))
            return False

    def file_link(self, path):
        """Copy a file where the hub serves it (`/file/<name>`); the ops
        view links it. A document used to go out as a bubble in her chat."""
        d = os.path.join("data", "talkapp", "files")
        os.makedirs(d, exist_ok=True)
        name = os.path.basename(path)
        shutil.copyfile(path, os.path.join(d, name))
        return f"/file/{name}"

    def send_document(self, path, caption=""):
        if self.console_only:
            print(f"\n>>> FILE: {path} ({caption})\n")
            return True
        try:
            res = self._post("/bot/send", {"char": self.char,
                                           "text": f"[file] {os.path.basename(path)} {caption}".strip()})
            return bool(res.get("id"))
        except Exception as e:
            logger.log(f"[talkapp] document error: {type(e).__name__}")
            return False

    def send_photo(self, path):
        """A photo of hers, as a row of its own before the bubbles that caption it."""
        if self.console_only:
            print(f"\n>>> {self.name.upper()} (photo): {path}\n")
            return True
        try:
            res = self._post("/bot/photo", {"char": self.char, "path": os.path.abspath(path)})
            return bool(res.get("id"))
        except Exception as e:
            logger.log(f"[talkapp] photo error: {type(e).__name__}")
            return False

    def send_sticker(self, path, bucket="", ts=None, quiet=False, auto=False):
        """A reaction of hers in the chat: a frame of her from the episodes,
        the size of a LINE sticker. Not a message she wrote; never in her
        context. `ts` in the past places it there (the backfill)."""
        if self.console_only:
            print(f"\n>>> {self.name.upper()} (sticker {bucket}): {path}\n")
            return True
        try:
            res = self._post("/bot/sticker", {"char": self.char, "path": os.path.abspath(path),
                                              "bucket": bucket, "ts": ts, "quiet": quiet, "auto": bool(auto)})
            return bool(res.get("id"))
        except Exception as e:
            logger.log(f"[talkapp] sticker error: {type(e).__name__}")
            return False

    def send_voice(self, ogg_path, attach_to=0):
        """`attach_to` names the bubble this belongs to.

        Without it the hub attaches to her most recent bubble, which is right
        for a voice note she has just spoken and wrong for a line he tapped:
        a render takes a second or two and she may have said something else in
        the meantime, and the audio would land under the wrong words."""
        if self.console_only:
            print(f"\n>>> {self.name.upper()} (voice note): {ogg_path}\n")
            return True
        try:
            body = {"char": self.char, "path": os.path.abspath(ogg_path)}
            if attach_to:
                body["attach_to"] = int(attach_to)
            res = self._post("/bot/voice", body)
            return bool(res.get("id"))
        except Exception as e:
            logger.log(f"[talkapp] voice error: {type(e).__name__}")
            return False

    def post_swipes(self, hub_id, items, sat=0, rows=()):
        """The answers drawn for one of her messages, up to the hub, so the
        counter and the arrows in the chat show them."""
        if self.console_only:
            print(f"\n>>> {self.name.upper()} (swipes on {hub_id}): {len(items)}, sitting {sat}\n")
            return True
        try:
            return bool(self._post("/bot/swipes", {"char": self.char, "id": int(hub_id),
                                                   "swipes": list(items), "sat": int(sat),
                                                   "rows": [int(r) for r in rows]}).get("ok"))
        except Exception as e:
            logger.log(f"[talkapp] swipes not posted: {type(e).__name__}")
            return False

    def post_swipes_state(self, hub_id, pending="", reconstructed=None):
        """What is happening to one of her messages, without touching the
        answers already drawn for it.

        A rebuild of the moment a reply was written in takes a second process
        and the better part of a minute; with nothing sent, the chat shows an
        empty control and reads as a dead tap. `pending` is the line the chat
        puts on screen while it waits, and the empty string takes it away."""
        if self.console_only:
            print(f"\n>>> {self.name.upper()} (swipe state on {hub_id}): {pending or 'done'}\n")
            return True
        body = {"char": self.char, "id": int(hub_id), "pending": str(pending)}
        if reconstructed is not None:
            body["reconstructed"] = int(reconstructed)
        try:
            return bool(self._post("/bot/swipes", body).get("ok"))
        except Exception as e:
            logger.log(f"[talkapp] swipe state not posted: {type(e).__name__}")
            return False

    def hub_rows(self):
        """The hub's own copies of the recent rows.

        Read when a change to her words has to keep what is hanging off them:
        the audio on a bubble is a field of the CHANNEL's row, not of hers, so
        whether a line has been spoken is a question only the hub can answer."""
        if self.console_only:
            return []
        try:
            return (self._get("/history", char=self.char) or {}).get("messages", []) or []
        except Exception as e:
            logger.log(f"[talkapp] the hub's own rows were not read: {type(e).__name__}")
            return []

    def speak_requests(self):
        """Lines he has tapped since the last look: [{id, text}]."""
        if self.console_only:
            return []
        try:
            return (self._get("/bot/speak", char=self.char) or {}).get("lines", []) or []
        except Exception as e:
            # the type only. A requests exception carries the URL it failed on,
            # and the URL carries `key=<the hub token>`: logging it verbatim
            # wrote the token into session.log the first time the hub bounced.
            logger.log(f"[talkapp] speak poll error: {type(e).__name__}")
            return []

    def send_audio(self, audio_path):
        return self.send_voice(audio_path)

    # ---------------- the rides on the poll ----------------

    def _sync_reads(self):
        """Down: his view reads -> store.mark_read on her rows (receipts.py
        already trusts a stamped read_ts). Up (throttled): her reads of his
        messages, the group chat, presence."""
        now = self.clock.now_ts() if self.clock else 0
        try:
            reads = self._get("/bot/reads", char=self.char).get("reads", {})
            if reads and self.store:
                recent = self.store.recent_messages(120)
                for m in recent:
                    tg = str(m.get("tg_id") or "")
                    if m["role"] == "assistant" and not m.get("read_ts") and tg in reads:
                        self.store.mark_read(m["id"], float(reads[tg]))
        except Exception:
            pass
        self._push_state()

    def _push_state(self, force=False):
        """Up: her reads of his messages, the group chat, presence, the
        operator's payload and which model writes in her words.

        Throttled to `talkapp.state_push_seconds`, because most of it moves
        slowly; `force` is a control he has just tapped, whose answer must not
        wait out the throttle."""
        if not force and time.time() - self._last_state_push < self.config.talkapp.state_push_seconds:
            return
        self._last_state_push = time.time()
        try:
            her_reads = {}
            if self.store:
                for m in self.store.recent_messages(120):
                    if m["role"] == "user" and m.get("read_ts") and m.get("tg_id"):
                        her_reads[str(m["tg_id"])] = m["read_ts"]
            body = {"char": self.char, "her_reads": her_reads, "presence": self._presence()}
            # the group payload is the full record now, so it rides only
            # when it changed; the hub keeps its last copy
            group = self._group()
            digest = hashlib.sha1(json.dumps(group, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
            if digest != self._group_digest:
                body["group"] = group
                self._group_digest = digest
            if self.reaction_provider:
                try:
                    body["reaction"] = self.reaction_provider() or {}
                except Exception:
                    pass
            if self.ops_provider:
                try:
                    body["ops"] = self.ops_provider()
                except Exception as e:
                    body["ops"] = {"error": f"{type(e).__name__}: {e}"}
            # which model writes in her words and which names she will accept,
            # for the control in the chat header. Handed in rather than worked
            # out here: the precedence between the chat's toggle, the
            # all-roles pin and her config belongs to `LLM.call` and must be
            # read from one place only.
            if self.voice_model_provider:
                try:
                    got = self.voice_model_provider() or {}
                    body["voice_model"] = str(got.get("model", ""))
                    body["voice_models"] = list(got.get("models") or [])
                except Exception as e:
                    logger.log(f"[talkapp] her voice model was not read: {type(e).__name__}: {e}")
            self._post("/bot/state", body)
        except Exception:
            pass

    def state_push_due(self):
        """Send the state NOW rather than waiting out
        `talkapp.state_push_seconds`.

        The chat header is drawn from that push, and it is the only thing that
        tells the hub which model her voice is on. Clearing the throttle and
        leaving the send to the next pass was not enough: he picked a model,
        the bot took it, and the header went on naming the old one for the
        rest of the poll -- which reads as a tap that did nothing, and he
        tapped again three times."""
        self._last_state_push = 0.0
        try:
            self._push_state(force=True)
        except Exception as e:
            logger.log(f"[talkapp] the state was not pushed: {type(e).__name__}")

    def get_ops_commands(self):
        """Commands typed in the app's ops view, oldest first; the hub
        clears them on read."""
        try:
            return [str(t) for t in self._get("/bot/ops", char=self.char).get("commands", [])]
        except Exception:
            return []

    def post_ops_result(self, cmd, text):
        try:
            self._post("/bot/ops_result", {"char": self.char, "cmd": cmd, "text": str(text)})
        except Exception:
            pass

    # ---------------- another character on the same hub ----------------

    def peer_send(self, to_id, text, room=None):
        """One character to another (docs/peer-talk.md). The hub puts it in
        the RECIPIENT's mailbox with this character named on it; it is never a
        row in either chat, so nothing is pushed to his phone and nothing is
        read-receipted. A hub that has never seen that id answers `known`
        false: nobody is there, which is logged and not retried.

        `room` is the one optional field: when this message is a turn in a
        room both of them are in, rather than a message between the two of
        them, it says which room, what was said in it that she has not seen,
        who else is in it, and whether the room is waiting for her words
        (`sim/rooms.py`). The hub carries it and reads none of it."""
        if not to_id or not str(text or "").strip():
            return False
        if self.console_only:
            print(f"\n>>> {self.name.upper()} -> {to_id}: {text}\n")
            return True
        try:
            body = {"char": self.char, "to": str(to_id), "text": str(text)}
            if isinstance(room, dict) and room:
                body["room"] = room
            res = self._post("/bot/peer", body)
            netwatch.WATCH.ok("talkapp")
            if not res.get("known"):
                logger.log(f"[peer] nothing is registered with the hub as '{to_id}': she wrote to nobody")
            return res.get("id") or True
        except Exception as e:
            netwatch.WATCH.fail("talkapp", str(e))
            logger.log(f"[peer] not delivered to '{to_id}': {type(e).__name__}")
            return False

    def peer_updates(self, after=0):
        """What another character has said to her since `after`. The mailbox is
        not cleared on read, so a bot that was down misses nothing."""
        if self.console_only:
            return []
        try:
            got = self._get("/bot/peer", char=self.char, after=int(after or 0))
            netwatch.WATCH.ok("talkapp")
            return list(got.get("messages") or [])
        except Exception as e:
            netwatch.WATCH.fail("talkapp", str(e))
            return []

    def _ts(self, date, hm, opened=""):
        """The moment a row of the record actually was. The record keeps her
        wall time and her date, which is a time only if you already know whose
        clock it is; the app shows every one of these on HIS. `opened` is the
        time the exchange began: a turn earlier than its own opener has crossed
        midnight, which a chat running past the last light does."""
        if not (self.clock and date and hm):
            return 0
        return self.clock.ts_of(date, hm, 1 if (opened and hm < opened) else 0)

    def _self_names(self):
        """Every name that means her, for the app. Guarded, because a roster
        that will not load must not cost him the whole group payload."""
        try:
            from sim import roster
            return roster.self_names(self.config)
        except Exception:
            n = str(getattr(self.config.character, "name", "") or "")
            return [n.lower()] if n else []

    def _group(self):
        """The group chat as she sees it: delivered beats plus her own turns,
        with the undelivered rest carried but flagged, for the backstage
        toggle. Nobody in the APP sees a beat before its time unless the
        operator asks to.

        Three records feed it, and the third is the rooms she was in that
        somebody else keeps: a character who reads a world she does not own
        writes no beat and holds no exchange, so those two are empty for her
        and her copy of the room is the only thing there is to draw."""
        if not self.store:
            return {}
        beats = self.store.get("cast_beats", {}) or {}
        prev = self.store.get("cast_beats_prev", {}) or {}
        rows = []
        # `prev` is yesterday. It is only moved over when the date CHANGES, so
        # between the day boundary and `schedule.generate_at` -- when the plan
        # is still the skeleton and `plan_day` has not run -- both records hold
        # the same day, and every beat was rendered twice in the app for those
        # five hours every night.
        recs = (beats,) if prev.get("date") == beats.get("date") else (prev, beats)
        for rec in recs:
            for b in rec.get("beats", []):
                rows.append({"time": b.get("time", ""), "date": rec.get("date", ""),
                             "ts": self._ts(rec.get("date", ""), b.get("time", "")),
                             "who": b.get("who", ""),
                             "kind": b.get("kind", ""), "ja": b.get("ja", ""), "img": b.get("img", ""),
                             "text": b.get("text", ""), "done": bool(b.get("done"))})
        # cast_chat is a list of exchange records, each with her actual turns
        exchanges = []
        live = self.store.get("exchange_live") or None
        # the whole record the store keeps (`exchange.keep`), not a window:
        # the operator reads the same history the models can
        rows_x = list(self.store.get("cast_chat", []) or []) + ([dict(live, live=True)] if live and live.get("turns") else [])
        # and her conversations with another running character (sim/peers.py):
        # backstage, where her own people already are, and never a row in his
        # chat -- he is not in that room, and a row there would be pushed to
        # his phone and read-receipted as though he were
        peer_live = self.store.get("peer_live") or None
        rows_x += list(self.store.get("peer_chat", []) or [])
        if peer_live and peer_live.get("turns"):
            rows_x.append(dict(peer_live, live=True))
        for x in rows_x:
            date, opened = x.get("date", ""), x.get("hm", "")
            exchanges.append({
                "date": date, "hm": opened, "ts": self._ts(date, opened),
                "who": x.get("who", ""), "kind": x.get("kind", ""), "live": bool(x.get("live")),
                # the turns are Japanese only now; the gist is the operator's line
                "gist": x.get("gist", ""),
                "turns": [{"who": t.get("who", ""), "ja": t.get("ja", ""), "img": t.get("img", ""),
                           "text": t.get("text", ""), "hm": t.get("hm", ""),
                           "ts": self._ts(date, t.get("hm", "") or opened, opened)}
                          for t in x.get("turns", [])]})
        # ...and the rooms somebody else owns that she was in (kv `peer_rooms`,
        # sim/peers.py). A character who reads a world she does not keep owns
        # no conversation at all, so without this her panel drew whatever
        # stray beat was in her save and nothing of the group chat she had
        # actually been sitting in. One row per room: her copy of it is one
        # running record, and every turn in it carries the real instant it was
        # said, so the drawing is by `ts` as everywhere else here.
        for room, rec in sorted((self.store.get("peer_rooms", {}) or {}).items()):
            if not isinstance(rec, dict):
                continue
            turns = [t for t in (rec.get("turns") or []) if str(t.get("ja") or t.get("text") or "").strip()]
            if not turns:
                continue
            date, opened = str(rec.get("date") or ""), str(turns[0].get("hm") or "")
            exchanges.append({
                "date": date, "hm": opened, "ts": self._ts(str(turns[0].get("date") or date), opened),
                "who": str(rec.get("owner_name") or rec.get("owner") or ""),
                "kind": str(rec.get("kind") or "group"), "live": False, "gist": "",
                "room": str(room), "present": list(rec.get("present") or []),
                "turns": [{"who": str(t.get("who") or ""), "ja": str(t.get("ja") or ""), "img": "",
                           "text": str(t.get("text") or ""), "hm": str(t.get("hm") or ""),
                           "ts": float(t.get("ts") or 0)
                           or self._ts(str(t.get("date") or date), str(t.get("hm") or "") or opened, opened)}
                          for t in turns]})
        # the day the panel's header names. It has always been the day's beat
        # record, which a character who writes no beat has not got, so the
        # header read "her , times on your clock": the newest thing she was
        # actually shown answers for her.
        day = str(beats.get("date") or "")
        if not day and exchanges:
            day = str(max(exchanges, key=lambda x: float(x.get("ts") or 0)).get("date") or "")
        out = {"date": day, "beats": rows, "exchanges": exchanges,
               # every name that means HER, as her own roster resolves them,
               # so the app can put her turns on her own side of a room it did
               # not build. It was one character's names spelled into the
               # client as a pattern, which read for anybody else drew the
               # room OWNER's turns as the open character's own.
               "me": self._self_names()}
        # the social graph rides along for the app's backstage view only
        g = self.graph
        if g:
            try:
                out["graph"] = g.payload()
            except Exception:
                pass
        return out

    def _presence(self):
        """One line: where she is, as the phone could plausibly show (last
        seen). Scene detail stays in the simulation."""
        try:
            if self.config.resident:
                # her sleep is read off his machine (resident/sight.py), not her plan
                return "asleep" if (self.store and self.store.get("resident_asleep")) else "online"
            sched = self.store.get_schedule(self.clock.date_str()) if self.store and self.clock else None
            if not sched:
                return ""
            hm = self.clock.hm()
            for b in sched.get("blocks", []):
                if b["start"] <= hm < b["end"]:
                    # the block's own words, not just its phone rule: a lesson
                    # and a night are the same dark phone, and he was shown
                    # nothing for both -- except for a resident, whose words
                    # are the wrong answer: she was replying from the bath
                    # while this line said "away".
                    return schedule.presence_label(self.config, b)
        except Exception:
            pass
        return ""
