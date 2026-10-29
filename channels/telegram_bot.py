import requests
from sim import wiring
import logger
import netwatch


from channels.base import Channel


class TelegramInterface(Channel):
    # Telegram's message ids are globally unique, so a redelivered update can
    # be recognised by its id and dropped (`store.add_message`). No other
    # channel here may claim this.
    MSG_ID_UNIQUE = True

    def _redact(self, e):
        """Errors from requests carry the full URL, token included; never log it."""
        text = str(e)
        if getattr(self, "token", None):
            text = text.replace(self.token, "<token>")
        return text

    def __init__(self, config, vision=None, clock=None, store=None):
        t = config.telegram
        self.token = t.bot_token
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        # Kept in the save file, not just in memory: Telegram holds an update
        # until a poll confirms it with a higher offset, so a restart used to
        # start from zero and re-read anything the last run had not confirmed.
        self.store = store
        self.last_update_id = int((store.get("tg_last_update_id", 0) if store else 0) or 0)
        self.active_chat_id = str(t.chat_id) if t.chat_id else ""
        self.max_length = t.max_message_length
        self.console_only = t.console_only
        # the console label comes from her config, never a name in shared code
        self.who = str(getattr(getattr(config, "character", None), "name", "") or "her")
        self.vision = vision          # she can look at a picture he sends
        self.clock = clock
        wiring.declare(self)

    def _download(self, file_id):
        """Telegram file bytes for a file_id. Returns (mime, bytes) or None."""
        try:
            info = requests.get(f"{self.base_url}/getFile",
                                params={"file_id": file_id}, timeout=15).json()
            if not info.get("ok"):
                return None
            path = info["result"]["file_path"]
            r = requests.get(f"https://api.telegram.org/file/bot{self.token}/{path}", timeout=30)
            if r.status_code != 200 or not r.content:
                return None
            ext = path.rsplit(".", 1)[-1].lower()
            mime = {"png": "image/png", "webp": "image/webp", "gif": "image/gif"}.get(ext, "image/jpeg")
            return mime, r.content
        except Exception as e:
            logger.log(f"[telegram] file download failed: {self._redact(e)}")
            return None

    def _look_at_photo(self, msg, caption):
        """He sent a picture. She opens it and looks. Returns the line for her
        history, or None to fall back to the plain marker."""
        if not (self.vision and self.vision.enabled):
            return None
        photos = msg.get("photo") or []
        if not photos:
            return None
        best = max(photos, key=lambda p: p.get("file_size") or p.get("width") or 0)
        img = self._download(best.get("file_id"))
        if not img:
            return None
        date_str = self.clock.date_str() if self.clock else ""
        desc = self.vision.describe_photo(img, caption, date_str)
        if not desc:
            return None
        head = f'he sent a photo, caption "{caption}"' if caption else "he sent a photo"
        return f"[{head}: {desc}]"

    def verify_connection(self):
        if self.console_only:
            logger.log("[telegram] console-only mode, no connection")
            return True
        try:
            data = requests.get(f"{self.base_url}/getMe", timeout=10).json()
            if data.get("ok"):
                logger.log(f"[telegram] bot @{data['result']['username']}")
                return True
            logger.log(f"[telegram] error {data}")
            return False
        except Exception as e:
            logger.log(f"[telegram] network error: {e}")
            return False

    def flush_queue(self):
        if self.console_only:
            return
        try:
            data = requests.get(f"{self.base_url}/getUpdates", timeout=10).json()
            if data.get("ok") and data["result"]:
                self.last_update_id = data["result"][-1]["update_id"]
                logger.log(f"[telegram] ignored {len(data['result'])} old updates")
        except Exception as e:
            logger.log(f"[telegram] flush error: {e}")

    def get_new_messages(self):
        """Returns list of (text, message_id)."""
        if self.console_only:
            return []
        params = {"offset": self.last_update_id + 1, "timeout": 5}
        try:
            data = requests.get(f"{self.base_url}/getUpdates", params=params, timeout=15).json()
            netwatch.WATCH.ok("telegram")
            out = []
            if data.get("ok"):
                for update in data["result"]:
                    self.last_update_id = update["update_id"]
                    if self.store:
                        self.store.set("tg_last_update_id", self.last_update_id)
                    msg = update.get("message")
                    if not msg:
                        continue
                    text = msg.get("text")
                    if text is None:
                        # she cannot see the picture, but she can see that he sent one
                        cap = (msg.get("caption") or "").strip()
                        if "photo" in msg:
                            text = self._look_at_photo(msg, cap) or \
                                "[he sent a photo" + (f": {cap}" if cap else "") + "]"
                        elif "sticker" in msg:
                            emo = (msg.get("sticker") or {}).get("emoji", "")
                            text = f"[he sent a sticker {emo}]".replace("  ", " ")
                        elif "voice" in msg or "audio" in msg:
                            text = "[he sent a voice message]"
                        elif "video" in msg or "animation" in msg or "video_note" in msg:
                            text = "[he sent a video" + (f": {cap}" if cap else "") + "]"
                        elif "document" in msg:
                            text = "[he sent a file: " + str((msg.get("document") or {}).get("file_name", "")) + "]"
                    if text is not None:
                        chat_id = str(msg["chat"]["id"])
                        if not self.active_chat_id:
                            self.active_chat_id = chat_id
                            logger.log(f"[telegram] locked onto chat {chat_id}")
                        if chat_id == self.active_chat_id:
                            out.append((text, msg.get("message_id")))
            return out
        except Exception as e:
            netwatch.WATCH.fail("telegram", self._redact(e))
            return []

    def send_typing(self):
        if self.console_only or not self.active_chat_id:
            return
        try:
            requests.post(f"{self.base_url}/sendChatAction", json={"chat_id": self.active_chat_id, "action": "typing"}, timeout=10)
        except Exception:
            pass

    def send_message(self, text):
        if not text or not text.strip():
            return False
        if self.console_only:
            try:
                print(f"\n>>> {self.who}: {text}\n")
            except UnicodeEncodeError:
                print(f"\n>>> {self.who}: {text.encode('ascii', 'replace').decode()}\n")
            return True
        if not self.active_chat_id:
            logger.log("[telegram] no chat id")
            return False
        first_id = None
        for chunk in self._split(text):
            try:
                res = requests.post(f"{self.base_url}/sendMessage", json={"chat_id": self.active_chat_id, "text": chunk}, timeout=10).json()
                if not res.get("ok"):
                    logger.log(f"[telegram] send error {res}")
                    return False
                if first_id is None:
                    first_id = (res.get("result") or {}).get("message_id")
            except Exception as e:
                netwatch.WATCH.fail("telegram", self._redact(e))
                return False
        netwatch.WATCH.ok("telegram")
        # the id, so a bubble of hers can be edited or deleted afterwards. It
        # was thrown away before, and when her history had to be corrected on
        # 2026-08-20 there was no way to touch what Telegram already held.
        return first_id or True

    def delete_message(self, message_id):
        """Remove one of her messages from his chat. Telegram allows this for
        about 48 hours. Returns True when it is gone."""
        if self.console_only or not self.active_chat_id or not message_id:
            return False
        try:
            res = requests.post(f"{self.base_url}/deleteMessage",
                                json={"chat_id": self.active_chat_id, "message_id": int(message_id)},
                                timeout=10).json()
            if not res.get("ok"):
                logger.log(f"[telegram] delete refused: {str(res.get('description', ''))[:80]}")
            return bool(res.get("ok"))
        except Exception as e:
            netwatch.WATCH.fail("telegram", self._redact(e))
            return False

    def edit_message(self, message_id, text):
        """Rewrite one of her messages in place. Same 48 hour window."""
        if self.console_only or not self.active_chat_id or not message_id:
            return False
        try:
            res = requests.post(f"{self.base_url}/editMessageText",
                                json={"chat_id": self.active_chat_id,
                                      "message_id": int(message_id), "text": text},
                                timeout=10).json()
            if not res.get("ok"):
                logger.log(f"[telegram] edit refused: {str(res.get('description', ''))[:80]}")
            return bool(res.get("ok"))
        except Exception as e:
            netwatch.WATCH.fail("telegram", self._redact(e))
            return False

    def send_document(self, path, caption=""):
        """For the things too big to read in chunks of 4096: her whole prompt."""
        if self.console_only:
            print(f"\n>>> FILE: {path} ({caption})\n")
            return True
        if not self.active_chat_id:
            return False
        try:
            with open(path, "rb") as f:
                res = requests.post(f"{self.base_url}/sendDocument",
                                    data={"chat_id": self.active_chat_id, "caption": caption[:1000]},
                                    files={"document": f}, timeout=120).json()
            if not res.get("ok"):
                logger.log(f"[telegram] document error {res}")
            return bool(res.get("ok"))
        except Exception as e:
            netwatch.WATCH.fail("telegram", self._redact(e))
            return False

    def send_voice(self, ogg_path, attach_to=0):
        if self.console_only:
            print(f"\n>>> {self.who} (voice note): {ogg_path}\n")
            return True
        if not self.active_chat_id:
            return False
        try:
            with open(ogg_path, "rb") as f:
                res = requests.post(f"{self.base_url}/sendVoice", data={"chat_id": self.active_chat_id}, files={"voice": f}, timeout=120).json()
            if not res.get("ok"):
                logger.log(f"[telegram] voice error {res}")
            return bool(res.get("ok"))
        except Exception as e:
            logger.log(f"[telegram] voice network error: {e}")
            return False

    def send_audio(self, audio_path):
        if self.console_only or not self.active_chat_id:
            return False
        try:
            with open(audio_path, "rb") as f:
                res = requests.post(f"{self.base_url}/sendAudio", data={"chat_id": self.active_chat_id}, files={"audio": f}, timeout=120).json()
            return bool(res.get("ok"))
        except Exception as e:
            logger.log(f"[telegram] audio error: {e}")
            return False

    def _split(self, text):
        if len(text) <= self.max_length:
            return [text]
        chunks = []
        while len(text) > self.max_length:
            at = text.rfind("\n", 0, self.max_length)
            if at == -1:
                at = self.max_length
            chunks.append(text[:at])
            text = text[at:].lstrip("\n")
        if text:
            chunks.append(text)
        return chunks
