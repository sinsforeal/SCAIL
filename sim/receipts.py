from sim import sight
from sim import lang

# Read receipts, inferred. Telegram gives bots nothing, but the app on her
# phone shows his screen: if the Telegram window came to the front after her
# message, he read it; if his PC was busy but the chat never came up, he saw
# the notification and left it; if the PC has been quiet, he has not seen
# it. From her side these are just the ticks in the chat. Also stamps
# read_ts on her messages so /day can show what he read and when.


class Receipts:
    def __init__(self, config, store, clock, sys_monitor=None):
        self.config = config
        self.store = store
        self.clock = clock
        self.mon = sys_monitor
        r = config.receipts
        self.procs = [p.lower() for p in r.telegram_process_names]
        # the window title that is her chat: her own name, which is what
        # Telegram Desktop puts in the title bar. There was a config list to
        # add more titles to it, and in both characters' files it held exactly
        # one entry, that same name -- so nothing was ever added and it is
        # gone (2026-09-04, his call). Under TALKAPP none of this runs at all:
        # a read there is an event from the hub, not an inference off a window.
        own = str(getattr(config.character, "name", "") or "").strip()
        self.chats = [own.lower()] if own else []

    @staticmethod
    def _chat_of(title):
        """The conversation a Telegram Desktop window has open.

        The title is the chat name, with a left-to-right mark in front of it and
        the unread count after: `\u200eTomoe - (679745)`. Strip both and what is
        left is who he is talking to."""
        t = (title or "").replace("\u200e", "").replace("\u200f", "").strip()
        for sep in (" \u2013 (", " - (", " \u2014 ("):
            if sep in t:
                t = t.split(sep)[0]
                break
        return t.strip().lower()

    def _is_her_chat(self, process, title):
        """He has HER conversation open, rather than Telegram being somewhere
        on screen.

        This used to match the process OR the word "telegram" in the title, and
        against the live feed that was 4 real hits out of 1407: a terminal
        called `Administrator: hc-telegram`, his `telegram_auto_copy_bot`
        source, a Notepad++ config, a Google search, and another chat entirely
        all counted as him reading her. The window title says which chat it is,
        so there is no reason to guess."""
        p = (process or "").lower()
        if not any(x in p for x in self.procs):
            return False
        chat = self._chat_of(title)
        if not chat:
            return False
        return any(chat == c or chat.startswith(c) for c in self.chats)

    def status(self):
        """Returns dict or None when nothing of hers is pending.
        keys: state (unseen|seen|read|replied), her_ts, minutes, read_ts, active"""
        her = self.store.last_message("assistant")
        his = self.store.last_message("user")
        if not her:
            return None
        if his and his["ts"] > her["ts"]:
            return {"state": "replied", "her_ts": her["ts"], "minutes": 0}
        now = self.clock.now_ts()
        out = {"state": "unknown", "her_ts": her["ts"], "minutes": (now - her["ts"]) / 60.0, "read_ts": None, "active": False}
        if not self.mon or not self.config.receipts.enabled:
            return out
        # her_ts is character time; sessions are wall time. Same instant in real
        # mode; in sim mode receipts are meaningless and the monitor is off anyway.
        sessions, last_input = self.mon.attention_since(her["ts"])
        read_at = None
        focus = 0.0
        # On TALKAPP a read is an exact event (the bubble on his screen in the
        # app, reported by the hub and stamped by the adapter), so the window
        # inference must not run: the dead Telegram chat still opens on his
        # desktop, and him rereading old history there would stamp reads on
        # messages he never saw. His PC being active stays a signal (`seen`);
        # it can never claim a read.
        if not self.config.talkapp.enabled:
            for start, end, proc, title in sessions:
                if self._is_her_chat(proc, title):
                    seg = end - max(start, her["ts"])
                    if seg > 0:
                        focus += seg
                        if read_at is None and seg >= self.config.receipts.read_min_seconds:
                            read_at = max(start, her["ts"])
        # Idle means idle. This was `last_input > her["ts"] or bool(sessions)`,
        # and the second half made any foreground change at all count as him
        # being at the machine -- so "seen" was nearly always true and "unseen"
        # nearly never happened. He can sit there with the screen on and not
        # touch anything for an hour, and that is not him seeing anything.
        active = last_input > 0 and (now - last_input) <= self.config.receipts.idle_after_minutes * 60
        out["active"] = active
        if read_at is not None and focus >= self.config.receipts.read_min_seconds:
            out["state"] = "read"
            out["read_ts"] = read_at
            self._stamp_read(her["ts"], read_at)
        elif her.get("read_ts"):
            # stamped on an earlier pass: a restart empties the monitor's
            # attention window, but a read stays read
            out["state"] = "read"
            out["read_ts"] = her["read_ts"]
        elif active:
            # "around", not "seen": his PC having input only proves he is at
            # the machine. Under Telegram a desktop toast made "he saw the
            # notification" a fair claim; under TALKAPP the notification went
            # to his phone and his PC shows nothing, so claiming he SAW
            # anything asserted a falsehood she then reacted to as deliberate.
            out["state"] = "around"
        else:
            out["state"] = "unseen"
        return out

    def was_around_between(self, t0, t1):
        """Was he at the machine at any point in (t0, t1)? A window session
        touching the span, or his last input falling inside it."""
        if not self.mon or not self.config.receipts.enabled:
            return False
        try:
            sessions, last_input = self.mon.attention_since(float(t0))
        except Exception:
            return False
        if last_input and float(t0) <= float(last_input) <= float(t1):
            return True
        for start, end, _proc, _title in sessions:
            if float(start) <= float(t1) and float(end) >= float(t0):
                return True
        return False

    def _stamp_read(self, her_ts, read_at):
        # every message of hers since his last one shares the read time
        his = self.store.last_message("user")
        since = his["ts"] if his else 0
        for m in self.store.recent_messages(30):
            if m["role"] == "assistant" and m["ts"] > since and not m["read_ts"]:
                self.store.mark_read(m["id"], read_at)

    def line(self, st, ja=False):
        """One sentence for her situation block, or '' when there is nothing to
        say. `ja` is her copy of it; `/receipts` reads the same status in
        English, because that one is for a developer."""
        if not st or st["state"] in ("replied", "unknown"):
            return ""
        t = lang.pick(ja)
        mins = int(st["minutes"])
        if st["state"] == "read":
            ago = int((self.clock.now_ts() - st["read_ts"]) / 60)
            if ago < 3:
                return t("he just read your last message(s).", "彼がいまあなたのメッセージを読んだ。")
            return t(f"he read your last message(s) {ago} minutes ago and has not replied.",
                     f"彼が{ago}分前にあなたのメッセージを読んで、返事はまだない。")
        if st["state"] == "around":
            if self.config.talkapp.enabled:
                # only what the evidence supports: the app shows him at his
                # desk; whether he has looked at his phone she cannot know
                return t(*sight.w2(self.config, "receipts_busy", mins=mins))
            return t(f"your last message(s) have sat there {mins} minutes; his PC has been busy the whole time but the chat never came up, so he saw the notification and left it.",
                     f"あなたのメッセージが{mins}分そのままになっている。彼のパソコンはずっと動いていたのにチャットは一度も開かれていない。"
                     f"通知を見て、そのままにしたということ。")
        return t(f"your last message(s) have sat there {mins} minutes; his PC has been quiet, so he probably has not seen them yet.",
                 f"あなたのメッセージが{mins}分そのままになっている。彼のパソコンは静かなので、まだ見ていないと思われる。")

    def brief(self, st):
        """Short form for the director and state prompts."""
        if not st:
            return "no message of hers pending"
        if st["state"] == "replied":
            return "he replied to her last message"
        return f"{st['state']} ({int(st['minutes'])} min since her last message)"
