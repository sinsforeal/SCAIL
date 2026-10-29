"""The B-zombie bench channel: a queue in, a record out, for one character.

No VN stage, no TTS, no Telegram, no sensors. The control server (bzombie/arms/s/control.py)
pushes his messages with `push` and collects what she sent with `take_outputs`. Her time is
the stepped clock, so every record carries the virtual timestamp.
"""

import threading

from channels.base import Channel
from sim import wiring


class BzChannel(Channel):
    MSG_ID_UNIQUE = True

    def __init__(self, config, vision=None, clock=None, store=None):
        self.config = config
        self.clock = clock
        self.store = store
        self.vision = vision
        self.who = str(getattr(getattr(config, "character", None), "name", "") or "her")
        self.console_only = True
        self._lock = threading.Lock()
        self._inbox = []          # (text, message_id)
        self._outputs = []        # every bubble she sent, in order
        # one id space for both directions: the store dedupes on tg_id across roles
        # (MSG_ID_UNIQUE), so his message 2 and her bubble 2 must never share a number
        self._next_id = 1
        self._peer_out = []       # what she wrote to another mind, until the driver takes it
        self._peer_in = []        # what the hub delivered to her (the save keeps the cursor: kv peer_last_id)
        wiring.declare(self)

    def seed_ids(self, last_used):
        """Continue the id space after `last_used` (the largest tg_id already in the save). A channel built
        over a restored save starts at 1 otherwise, every message of his collides with a stored id and the
        store dedupe drops it unread (tk-pjz: S arms silent after a resume)."""
        with self._lock:
            self._next_id = max(self._next_id, int(last_used or 0) + 1)

    def verify_connection(self):
        return True

    def flush_queue(self):
        with self._lock:
            self._inbox.clear()

    def push(self, text, ts=None):
        """His message. Returns the message id."""
        with self._lock:
            mid = self._next_id
            self._next_id += 1
            self._inbox.append((str(text), mid))
        return mid

    def get_new_messages(self):
        with self._lock:
            out, self._inbox = self._inbox, []
        return out

    def send_typing(self):
        return None

    def _now(self):
        return float(self.clock.now_ts()) if self.clock else 0.0

    def send_message(self, text):
        if not text or not str(text).strip():
            return False
        with self._lock:
            n = self._next_id
            self._next_id += 1
            self._outputs.append({"n": n, "virtual_ts": self._now(), "text": str(text)})
        return n

    def delete_message(self, message_id):
        with self._lock:
            for o in self._outputs:
                if o["n"] == message_id:
                    o["deleted"] = True
                    return True
        return False

    def edit_message(self, message_id, text):
        with self._lock:
            for o in self._outputs:
                if o["n"] == message_id:
                    o["text"] = str(text)
                    return True
        return False

    def send_document(self, path, caption=""):
        return False

    def take_outputs(self):
        """What she sent since the last call, oldest first."""
        with self._lock:
            out, self._outputs = self._outputs, []
        return [o for o in out if not o.get("deleted")]

    def pending_inbound(self):
        with self._lock:
            return len(self._inbox)

    # ---------------- another running mind (sim/peers.py) ----------------
    # The talkapp hub's two verbs, with the bench driver as the hub: peer_send files the message in an outbox
    # the control server hands to the driver, peer_updates reads a mailbox the driver fills (bzombie/harness/peers.py
    # PeerHub). Same shapes as talkapp_bot: {id, from, name, text, ts[, room]} in, hub id = display name lowercased.

    @property
    def hub_id(self):
        return self.who.lower().replace(" ", "")

    def peer_send(self, to_id, text, room=None):
        if not to_id or not str(text or "").strip():
            return False
        with self._lock:
            self._peer_out.append({"to": str(to_id), "text": str(text), "ts": self._now(),
                                   "from": self.hub_id, "name": self.who,
                                   **({"room": room} if isinstance(room, dict) and room else {})})
            return len(self._peer_out)

    def peer_updates(self, after=0):
        with self._lock:
            return [dict(m) for m in self._peer_in if int(m.get("id") or 0) > int(after or 0)]

    def peer_in(self, msgs):
        """The hub's delivery: rows with an id each; one id is delivered once."""
        with self._lock:
            have = {int(m.get("id") or 0) for m in self._peer_in}
            for m in msgs:
                if int(m.get("id") or 0) not in have:
                    self._peer_in.append(dict(m))
            self._peer_in = self._peer_in[-400:]

    def take_peer_out(self):
        with self._lock:
            out, self._peer_out = self._peer_out, []
        return out
