# -*- coding: utf-8 -*-
"""TALKAPP: the messenger she lives in, served to his phone.

A standalone hub process (like the MAL daemon): aiohttp on localhost, fronted
by `tailscale serve` for HTTPS on the tailnet, never the public internet. The
bot connects with channels/talkapp_bot.py, which implements the same surface
as TelegramInterface -- the seam the LINE experiment proved ("nine methods on
self.tg, and a second channel needed no other change in the app").

What this buys that Telegram refuses:
- her 既読, shown to him at the exact moment `store.mark_read` fires -- her
  schedule becomes visible, which was the whole LINE prize;
- his reads as real events (app focused + bubble on screen) instead of
  receipts.py inferring them from a window title;
- a typing indicator driven by her compose delays, so the start-stop-retype
  behaviour compose_factor models is something he can watch;
- the group chat as she sees it (delivered beats only), with a clearly
  marked backstage toggle for the rest;
- room for more than one girl: everything is keyed by character.

The hub keeps its own message log (data/talkapp/state.json) -- that is the
CHANNEL's record, the way Telegram's servers hold the chat; the bot's save
file stays the simulation's truth. Voice notes are copied into
data/talkapp/media and served from there.
"""
import asyncio
import io
import json
import os
import shutil
import sys
import threading
import time

from aiohttp import web, WSMsgType

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import atomic  # noqa: E402

DATA = os.path.join(ROOT, "data", "talkapp")
MEDIA = os.path.join(DATA, "media")
AVATARS = os.path.join(DATA, "avatars")
FILES = os.path.join(DATA, "files")   # ops files too big for the log (her whole prompt), copied there by the bot
REACTIONS = os.path.join(DATA, "reactions")   # her face right now, copied there by the bot (sim/reactions.py)
STATE = os.path.join(DATA, "state.json")
VAPID_PEM = os.path.join(DATA, "vapid_private.pem")
APP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app")
# how long after her last bubble a voice note still counts as that bubble
# spoken; a render on a cold cache takes 10-30s, a queue behind it longer
VOICE_ATTACH_SECONDS = 300


def _now():
    return time.time()


class Hub:
    def __init__(self, config):
        self.config = config
        os.makedirs(MEDIA, exist_ok=True)
        os.makedirs(AVATARS, exist_ok=True)
        self.state = self._load()
        self.clients = set()          # phone websockets
        self.focused = {}             # ws -> bool (page visible)
        self.loop = None              # set at startup; threads marshal back through it
        self._last_push = {}          # char -> ts of the last push that went out
        self.push = None              # (webpush fn, public key) when available
        if config.talkapp.push_enabled:
            self.push = self._init_push()

    # ---------------- persistence ----------------

    def _load(self):
        try:
            with open(STATE, "r", encoding="utf-8") as f:
                st = json.load(f)
        except (OSError, ValueError):
            return {"seq": 1000, "chars": {}, "subs": []}
        # an ops call without a `char` once created a nameless character
        # that the app listed beside her
        st["chars"] = {k: v for k, v in st.get("chars", {}).items() if k}
        return st

    def _save(self):
        atomic.write_json(STATE, self.state)

    def _char(self, cid):
        if not cid:
            raise web.HTTPBadRequest(text="char required")
        c = self.state["chars"].setdefault(cid, {
            "name": cid, "log": [], "typing_until": 0, "group": {}, "presence": ""})
        # the operator's view and its command channel: kept off the chat log
        c.setdefault("ops", {})
        c.setdefault("ops_queue", [])
        c.setdefault("ops_log", [])
        # lines he has tapped to hear, waiting for her bot to speak them.
        # `speak` is whether her bot offers it at all, so the button appears on
        # the character who has a voice on demand and on no other.
        # The other answers to a message of hers, keyed by the hub's own
        # message id, and which of them the conversation goes on from. Kept
        # BESIDE the log, never in it: a candidate nobody sat is not something
        # she said, so it is never a row, never a notification and never a
        # preview. Her save is the truth; this is the channel's copy of it,
        # the way `ops` is the channel's copy of the operator's payload.
        c.setdefault("swipes", {})
        # which model writes in her words, and the names her bot will accept
        # -- what the control in the chat header shows and offers
        c.setdefault("voice_model", "")
        c.setdefault("voice_models", [])
        c.setdefault("speak", False)
        c.setdefault("speak_queue", [])
        # messages from ANOTHER CHARACTER, waiting for this one's bot to
        # look (docs/peer-talk.md). Kept off the chat log on purpose: a row in
        # the log is his chat, and `h_bot_updates` hands the bot every row
        # that is not hers, so a peer message there would arrive as him. Each
        # row carries who sent it, which the log's two-valued `role` cannot
        # say. Not cleared on read -- the recipient holds the cursor -- so a
        # character who is down misses nothing.
        c.setdefault("peer_in", [])
        return c

    def _next_id(self):
        self.state["seq"] += 1
        return self.state["seq"]

    # ---------------- push ----------------

    def _init_push(self):
        try:
            from pywebpush import webpush
            from py_vapid import Vapid, b64urlencode
            from cryptography.hazmat.primitives import serialization
            if not os.path.exists(VAPID_PEM):
                v = Vapid()
                v.generate_keys()
                v.save_key(VAPID_PEM)
                print("[talkapp] generated VAPID keys")
            v = Vapid.from_file(VAPID_PEM)
            pub = b64urlencode(v.public_key.public_bytes(
                serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint))
            return webpush, pub
        except Exception as e:
            print(f"[talkapp] push unavailable: {type(e).__name__}: {e}")
            return None

    def _push_out(self, title, body, char=""):
        """Notify the phone when no client has the page visible.

        A skipped push is gone forever (there is no retry), so every attempt
        and every skip lands one line in data/talkapp/push.log -- "not
        reliable" was undiagnosable from a console window."""
        focused = any(self.focused.get(ws) for ws in self.clients)
        if not self.push or focused:
            self._push_log("skip", title,
                           "page visible" if focused else "push unavailable")
            return
        if char:
            self._last_push[char] = _now()
        subs = list(self.state["subs"])
        # webpush is a blocking HTTP call; on the event loop one slow push
        # service stalled the whole hub, heartbeats included
        threading.Thread(target=self._push_send,
                         args=(subs, title, body, char), daemon=True).start()

    def _push_send(self, subs, title, body, char):
        webpush, _ = self.push
        dead = []
        for sub in subs:
            try:
                # ttl: pywebpush's default is 0 -- deliver this instant or
                # discard -- so anything sent while the phone dozed was
                # silently dropped by Mozilla's server. A day of TTL means
                # the notification waits for the phone instead.
                webpush(subscription_info=sub,
                        data=json.dumps({"title": title, "body": body[:120],
                                         "char": char}),
                        vapid_private_key=VAPID_PEM,
                        vapid_claims={"sub": "mailto:talkapp@localhost"},
                        ttl=86400, timeout=10,
                        headers={"Urgency": "high"})
                self._push_log("sent", title, "..." + sub["endpoint"][-10:])
            except Exception as e:
                # 404/410 means the subscription is gone; drop it
                if "410" in str(e) or "404" in str(e):
                    dead.append(sub)
                    self._push_log("dead-sub", title, "..." + sub["endpoint"][-10:])
                else:
                    self._push_log("fail", title,
                                   f"{type(e).__name__}: {str(e)[:80]}")
        if dead and self.loop:
            # state.json belongs to the event loop; never touch it from here
            def drop():
                for sub in dead:
                    if sub in self.state["subs"]:
                        self.state["subs"].remove(sub)
                self._save()
            self.loop.call_soon_threadsafe(drop)

    def _push_log(self, verdict, title, detail):
        try:
            with open(os.path.join(DATA, "push.log"), "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} "
                        f"{verdict:<8} {title}: {detail}\n")
        except OSError:
            pass

    # ---------------- broadcast ----------------

    async def broadcast(self, event):
        gone = []
        for ws in self.clients:
            try:
                await ws.send_json(event)
            except Exception:
                gone.append(ws)
        for ws in gone:
            self.clients.discard(ws)
            self.focused.pop(ws, None)

    # ---------------- auth ----------------

    def _authed(self, request):
        key = request.query.get("key") or request.headers.get("X-Key", "")
        return key and key == self.config.talkapp.token

    # ================= phone side =================

    async def h_index(self, request):
        # no-cache: revalidate every load, or an installed PWA keeps showing
        # last week's client
        return web.FileResponse(os.path.join(APP_DIR, "index.html"),
                                headers={"Cache-Control": "no-cache"})

    async def h_static(self, request):
        name = request.match_info["name"]
        path = os.path.normpath(os.path.join(APP_DIR, name))
        if not path.startswith(APP_DIR) or not os.path.isfile(path):
            raise web.HTTPNotFound()
        return web.FileResponse(path, headers={"Cache-Control": "no-cache"})

    async def h_sw(self, request):
        """The service worker, served at the root. A worker may not control
        a scope above its own path, so /app/sw.js with scope '/' throws --
        Chrome names the scope rule, Firefox just says 'The operation is
        insecure', and push was broken everywhere until this."""
        return web.FileResponse(os.path.join(APP_DIR, "sw.js"),
                                headers={"Cache-Control": "no-cache",
                                         "Content-Type": "application/javascript"})

    # ================= link previews =================

    _PREVIEW = {}       # url -> (ts, card)

    async def h_preview(self, request):
        """A card for a link in the chat: title, a line, an image, the site.
        An X status goes through fxtwitter's JSON (x.com serves nothing to a
        plain fetch); anything else is the page's OpenGraph tags. Cached an
        hour; a failed lookup is a card with just the host, so the client
        never waits twice."""
        if not self._authed(request):
            raise web.HTTPForbidden()
        url = (request.query.get("url") or "").strip()
        if not url.startswith(("http://", "https://")) or len(url) > 2000:
            raise web.HTTPBadRequest()
        now = time.time()
        hit = self._PREVIEW.get(url)
        if hit and now - hit[0] < 3600:
            return web.json_response(hit[1])
        card = await self._preview_card(url)
        self._PREVIEW[url] = (now, card)
        if len(self._PREVIEW) > 400:
            for k in sorted(self._PREVIEW, key=lambda k: self._PREVIEW[k][0])[:100]:
                self._PREVIEW.pop(k, None)
        return web.json_response(card)

    async def _preview_card(self, url):
        import re
        import html as _html
        import aiohttp
        from urllib.parse import urlparse
        host = (urlparse(url).hostname or "").lower()
        card = {"url": url, "site": host.replace("www.", ""), "title": "", "desc": "", "image": ""}
        headers = {"User-Agent": "Mozilla/5.0 (Linux; Android 14) TALKAPP/1.0", "Accept-Language": "ja,en"}
        try:
            timeout = aiohttp.ClientTimeout(total=8)
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as s:
                m = re.search(r"(?:x|twitter)\.com/([A-Za-z0-9_]+)/status/(\d+)", url)
                if m:
                    async with s.get(f"https://api.fxtwitter.com/status/{m.group(2)}") as r:
                        if r.status == 200:
                            j = await r.json(content_type=None)
                            t = (j or {}).get("tweet") or {}
                            a = t.get("author") or {}
                            card["site"] = "x.com"
                            card["title"] = (a.get("name") or "") + (f" (@{a.get('screen_name')})" if a.get("screen_name") else "")
                            card["desc"] = (t.get("text") or "")[:280]
                            med = ((t.get("media") or {}).get("photos") or [])
                            if med:
                                card["image"] = med[0].get("url") or ""
                            elif (t.get("media") or {}).get("videos"):
                                card["image"] = (t["media"]["videos"][0].get("thumbnail_url") or "")
                            elif a.get("avatar_url"):
                                card["image"] = a["avatar_url"]
                            return card
                async with s.get(url, allow_redirects=True) as r:
                    ctype = r.headers.get("Content-Type", "")
                    if r.status != 200 or "html" not in ctype:
                        return card
                    raw = await r.content.read(512 * 1024)
                    text = raw.decode(r.charset or "utf-8", errors="replace")

                def meta(*names):
                    for n in names:
                        mm = (re.search(r'<meta[^>]+(?:property|name)=["%s]%s["%s][^>]+content=["%s]([^"%s]*)' % ("'", re.escape(n), "'", "'", "'"), text, re.I)
                              or re.search(r'<meta[^>]+content=["%s]([^"%s]*)["%s][^>]+(?:property|name)=["%s]%s["%s]' % ("'", "'", "'", "'", re.escape(n), "'"), text, re.I))
                        if mm and mm.group(1).strip():
                            return _html.unescape(mm.group(1).strip())
                    return ""
                card["title"] = meta("og:title", "twitter:title") or _html.unescape((re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S) or [None, ""])[1].strip())[:160]
                card["desc"] = meta("og:description", "twitter:description", "description")[:280]
                card["image"] = meta("og:image", "twitter:image")
                card["site"] = meta("og:site_name") or card["site"]
                if card["image"].startswith("/"):
                    p = urlparse(url)
                    card["image"] = f"{p.scheme}://{p.netloc}{card['image']}"
        except Exception as e:
            card["error"] = f"{type(e).__name__}"
        return card

    async def h_ver(self, request):
        """The client compares this on every foreground and reloads itself
        when the page on disk is newer than the one it is running."""
        if not self._authed(request):
            raise web.HTTPForbidden()
        try:
            v = int(os.path.getmtime(os.path.join(APP_DIR, "index.html")))
        except OSError:
            v = 0
        # the APK's own version, written by its build; the native app shows
        # "update app" when this is above what it is running
        apk_ver, apk_name = 0, ""
        try:
            with open(os.path.join(APP_DIR, "talkapp.ver"), encoding="utf-8") as f:
                parts = f.read().strip().split(" ", 1)
                apk_ver = int(parts[0])
                apk_name = parts[1] if len(parts) > 1 else ""
        except (OSError, ValueError):
            pass
        # what the phone is ACTUALLY running, reported by the page inside the
        # native app. Without it the only way to know whether a built APK had
        # been installed was to ask him, which is not a thing to keep doing.
        try:
            got = int(request.query.get("app", "") or 0)
        except ValueError:
            got = 0
        if got:
            self.state["app"] = {"ver": got, "name": request.query.get("app_name", "")[:40],
                                 "at": time.time()}
            self._save()
        return web.json_response({"ver": v, "apk_ver": apk_ver, "apk_name": apk_name})

    async def h_app(self, request):
        """Installed against served, so nobody has to ask."""
        if not self._authed(request):
            raise web.HTTPForbidden()
        apk_ver, apk_name = 0, ""
        try:
            with open(os.path.join(APP_DIR, "talkapp.ver"), encoding="utf-8") as f:
                parts = f.read().strip().split(" ", 1)
                apk_ver = int(parts[0])
                apk_name = parts[1] if len(parts) > 1 else ""
        except (OSError, ValueError):
            pass
        got = self.state.get("app") or {}
        seen = got.get("ver", 0)
        return web.json_response({
            "served": apk_ver, "served_name": apk_name,
            "installed": seen, "installed_name": got.get("name", ""),
            "seen_at": got.get("at", 0),
            "state": ("never reported" if not seen else
                      "current" if seen >= apk_ver else "behind")})

    @staticmethod
    def _dl_name(asked, fallback):
        """The name a saved file lands under: what the phone asked for, cut
        down to what every filesystem and every download manager accepts."""
        safe = "".join(ch if (ch.isalnum() and ch.isascii()) or ch in "._-" else "_"
                       for ch in os.path.basename(str(asked)))
        return safe[:80] or os.path.basename(fallback)

    async def h_media(self, request):
        if not self._authed(request):
            raise web.HTTPForbidden()
        name = request.match_info["name"]
        path = os.path.normpath(os.path.join(MEDIA, name))
        if not path.startswith(MEDIA) or not os.path.isfile(path):
            raise web.HTTPNotFound()
        # A voice note or a photo is named for the millisecond it was copied
        # in, so that name can never stand for different audio: the phone is
        # told to keep the file for a year and plays it again from its own
        # disk instead of asking for it a second time. A reaction frame is
        # named after the frame, which could in principle be redrawn, so it
        # revalidates once a day (the file's ETag makes that a 304).
        unique = len(name) > 13 and name[:13].isdigit() and name[13] == "_"
        headers = {"Cache-Control": ("private, max-age=31536000, immutable"
                                     if unique else "private, max-age=86400")}
        # ?dl=<name>: he is saving the file, not playing it. The attachment
        # disposition is what makes a WebView hand the file to Android's
        # download manager rather than play it in place.
        asked = request.query.get("dl")
        if asked:
            headers["Content-Disposition"] = \
                'attachment; filename="%s"' % self._dl_name(asked, name)
        return web.FileResponse(path, headers=headers)

    async def h_avatar(self, request):
        """Profile icon by name: a file dropped in data/talkapp/avatars/
        (tomoe.png, him.jpg, Rena-chan.png, group.png). 404 falls back to the
        letter circle in the client.

        The record names people in Japanese now (香芝玲奈), and the files are
        named by the roster handle, so every friend's picture 404ed and the app
        drew a letter circle instead. The name is resolved the way everything
        else resolves a name (`sim/roster.py`): the file as asked for first, so
        dropping in `香芝玲奈.jpg` also works, then the handle it belongs to."""
        if not self._authed(request):
            raise web.HTTPForbidden()
        asked = os.path.basename(request.match_info["name"])
        names = [asked]
        try:
            from sim import roster
            rec = roster.rec_of(self.config, asked) or {}
            for form in (rec.get("key"), rec.get("name"), rec.get("ja"), rec.get("role_id"),
                         roster.record_name(self.config, asked)):
                form = os.path.basename(str(form or "")).strip()
                if form and form not in names:
                    names.append(form)
        except Exception:
            pass
        for name in names:
            for ext in ("", ".png", ".jpg", ".jpeg", ".webp"):
                path = os.path.normpath(os.path.join(AVATARS, name + ext))
                if path.startswith(AVATARS) and os.path.isfile(path):
                    return web.FileResponse(path)
        raise web.HTTPNotFound()

    async def h_reaction_img(self, request):
        if not self._authed(request):
            raise web.HTTPForbidden()
        name = os.path.basename(request.match_info["name"])
        path = os.path.normpath(os.path.join(REACTIONS, name))
        if path.startswith(REACTIONS) and os.path.isfile(path):
            return web.FileResponse(path)
        raise web.HTTPNotFound()

    async def h_file(self, request):
        """A text file the bot left for the ops view (`/context full`)."""
        if not self._authed(request):
            raise web.HTTPForbidden()
        name = os.path.basename(request.match_info["name"])
        path = os.path.normpath(os.path.join(FILES, name))
        if path.startswith(FILES) and os.path.isfile(path):
            return web.Response(text=io.open(path, encoding="utf-8", errors="replace").read(),
                                content_type="text/plain", charset="utf-8")
        raise web.HTTPNotFound()

    async def h_vapid(self, request):
        if not self._authed(request):
            raise web.HTTPForbidden()
        return web.json_response({"key": self.push[1] if self.push else ""})

    async def h_subscribe(self, request):
        if not self._authed(request):
            raise web.HTTPForbidden()
        sub = await request.json()
        if sub not in self.state["subs"]:
            self.state["subs"].append(sub)
            self._save()
            print("[talkapp] push subscription added")
        return web.json_response({"ok": True, "subs": len(self.state["subs"])})

    async def h_push_test(self, request):
        """Fire a test push at every subscription, so 'did it work' is a tap
        rather than waiting for her next message."""
        if not self._authed(request):
            raise web.HTTPForbidden()
        n = len(self.state["subs"])
        was_focused = dict(self.focused)
        try:
            # the suppression is for real messages; a test must always fire
            for ws in self.focused:
                self.focused[ws] = False
            self._push_out("TALKAPP", "test notification - this is what her messages will feel like")
        finally:
            self.focused.update(was_focused)
        # the native app's socket path gets its own test event (the web
        # client ignores unknown types); this is how the APK is verified
        # without waiting for her next message
        await self.broadcast({"type": "notify_test"})
        return web.json_response({"ok": True, "subs": n})

    async def h_chars(self, request):
        if not self._authed(request):
            raise web.HTTPForbidden()
        # A character registered hidden has no chat with him, so she is left
        # out of the list his phone draws as conversations. She still runs,
        # still posts an ops payload and still takes commands, and the ops
        # view needs a chip for her to reach it -- hence the flag: hidden
        # keeps her off the chat list, not off the hub. The caller that asks
        # for everyone gets `hidden` on each row so it can tell them apart.
        show_all = request.query.get("all", "") not in ("", "0")
        out = []
        for cid, c in self.state["chars"].items():
            if c.get("hidden") and not show_all:
                continue
            last = c["log"][-1] if c["log"] else None
            preview = (last or {}).get("text", "")[:60]
            if not preview and (last or {}).get("kind") == "voice":
                preview = "🎤 voice note"
            if not preview and (last or {}).get("kind") == "sticker":
                preview = "a sticker"
            if not preview and (last or {}).get("kind") == "photo":
                preview = "📷 photo"
            out.append({"id": cid, "name": c["name"],
                        "last": preview,
                        # whether her bot will speak a line he taps. The button
                        # is drawn per character, so one of them having a voice
                        # on demand does not put a speaker on the other's chat.
                        "speak": bool(c.get("speak")),
                        "hidden": bool(c.get("hidden")),
                        "last_ts": (last or {}).get("ts", 0)})
        # the app coalesces a burst of bubbles into one alert; the window
        # lives in config so it changes without a new APK
        return web.json_response({"chars": out,
                                  "notify_burst_seconds": self.config.talkapp.notify_burst_seconds})

    async def h_history(self, request):
        if not self._authed(request):
            raise web.HTTPForbidden()
        cid = request.query.get("char", "")
        before = float(request.query.get("before", "0") or 0)
        if cid not in self.state["chars"]:
            return web.json_response({"messages": [], "typing_until": 0,
                                      "group": {}, "presence": ""})
        c = self._char(cid)
        log = c["log"]
        if before:
            log = [m for m in log if m["ts"] < before]
        return web.json_response({"messages": log[-80:],
                                  "typing_until": c["typing_until"],
                                  "reaction": c.get("reaction", {}),
                                  # The other answers drawn for her messages,
                                  # and the model her voice is on: the chat
                                  # can be opened straight from a
                                  # notification, so both have to arrive with
                                  # the history and not only over the socket.
                                  # Bounded to the rows this route sends -- a
                                  # candidate for a message the phone is not
                                  # being given is bytes with nothing to draw
                                  # them on.
                                  "swipes": {k: v for k, v in (c.get("swipes") or {}).items()
                                             if k in {str(m["id"]) for m in log[-80:]}},
                                  "voice_model": c.get("voice_model", ""),
                                  "voice_models": c.get("voice_models", []),
                                  # whether to draw a speaker on her lines. Sent
                                  # here as well as in /chars because the chat
                                  # can be opened straight from a notification,
                                  # with the character list never loaded.
                                  "speak": bool(c.get("speak")),
                                  "group": c.get("group", {}),
                                  "presence": c.get("presence", "")})

    async def h_ws(self, request):
        if not self._authed(request):
            raise web.HTTPForbidden()
        ws = web.WebSocketResponse(heartbeat=25)
        await ws.prepare(request)
        self.clients.add(ws)
        # not visible until the page says so: the client sends a focus frame
        # in onopen. Assuming True here meant every reconnect-in-background
        # (and every zombie socket) silently swallowed pushes until the
        # heartbeat killed it. A rare duplicate notification beats a lost one.
        self.focused[ws] = False
        try:
            async for msg in ws:
                if msg.type != WSMsgType.TEXT:
                    continue
                try:
                    ev = json.loads(msg.data)
                except ValueError:
                    continue
                await self._phone_event(ev, ws)
        finally:
            self.clients.discard(ws)
            self.focused.pop(ws, None)
        return ws

    async def _phone_event(self, ev, ws):
        t = ev.get("type")
        if t == "focus":
            # only the socket that spoke: one phone's "visible" must not
            # mark a dying twin visible too
            self.focused[ws] = bool(ev.get("focused"))
            return
        cid = ev.get("char", "")
        if cid not in self.state["chars"]:
            return
        c = self._char(cid)
        if t == "send":
            # him -> her. Queued for the bot's next poll.
            text = str(ev.get("text", ""))[:4000].strip()
            if not text:
                return
            m = {"id": self._next_id(), "role": "him", "kind": "text",
                 "text": text, "ts": _now(), "read_ts": None}
            c["log"].append(m)
            self._trim(c)
            self._save()
            await self.broadcast({"type": "message", "char": cid, "msg": m})
        elif t == "read":
            # he actually saw these bubbles of hers: app focused, on screen
            now = _now()
            changed = []
            ids = set(int(i) for i in ev.get("ids", []))
            for m in c["log"]:
                if m["id"] in ids and m["role"] == "her" and not m["read_ts"]:
                    m["read_ts"] = now
                    changed.append(m["id"])
            if changed:
                self._save()
                await self.broadcast({"type": "read", "char": cid,
                                      "ids": changed, "ts": now})

    def _trim(self, c):
        keep = self.config.talkapp.log_keep
        if len(c["log"]) > keep:
            c["log"] = c["log"][-keep:]

    # ================= bot side =================

    async def h_bot_register(self, request):
        if not self._authed(request):
            raise web.HTTPForbidden()
        d = await request.json()
        cid = d["char"]
        c = self._char(cid)
        c["name"] = d.get("name", cid)
        # whether this bot will speak a line on request. Declared by the bot
        # rather than configured here, so the hub never has to know which
        # character is which.
        c["speak"] = bool(d.get("speak"))
        # whether his phone lists her at all: a character registered only so
        # that another character's rooms can ask her through the hub
        c["hidden"] = bool(d.get("hidden"))
        # first registration may carry the Telegram-era history so the phone
        # shows the whole relationship, not a chat that starts today. `ext`
        # keeps the bot's original tg_id so receipts can still map either way.
        imported = False
        if not c["log"] and d.get("history"):
            for h in d["history"]:
                c["log"].append({"id": self._next_id(), "role": h["role"],
                                 "kind": "text", "text": h["text"], "ts": h["ts"],
                                 "read_ts": h.get("read_ts"), "ext": h.get("tg_id")})
            imported = True
            print(f"[talkapp] {cid}: imported {len(c['log'])} history rows")
        self._save()
        return web.json_response({"ok": True, "head": self.state["seq"], "imported": imported})

    async def h_bot_updates(self, request):
        if not self._authed(request):
            raise web.HTTPForbidden()
        cid = request.query.get("char", "")
        after = int(request.query.get("after", "0") or 0)
        c = self._char(cid)
        out = [{"id": m["id"], "text": m["text"], "ts": m["ts"]}
               for m in c["log"] if m["role"] == "him" and m["id"] > after]
        return web.json_response({"messages": out})

    # ---------------- one character to another ----------------

    async def h_bot_peer_send(self, request):
        """`{char: <sender>, to: <recipient>, text}` -- one character writing
        to another. The row goes into the RECIPIENT's mailbox with the sender
        on it. `known` false means nothing has ever registered under that id:
        nobody is there, and the sender logs it rather than retrying."""
        if not self._authed(request):
            raise web.HTTPForbidden()
        d = await request.json()
        frm = str(d.get("char", "") or "")
        to = str(d.get("to", "") or "")
        text = str(d.get("text", "") or "")[:4000].strip()
        if not frm or not to:
            raise web.HTTPBadRequest(text="char and to required")
        if not text:
            return web.json_response({"ok": False, "reason": "empty"})
        known = to in self.state["chars"]
        src = self._char(frm)
        c = self._char(to)
        m = {"id": self._next_id(), "from": frm, "name": src.get("name", frm),
             "text": text, "ts": _now()}
        # A turn in a room both of them are in, rather than a message between
        # the two of them: which room, what was said in it, who is in it, and
        # whether the room is waiting for her words (sim/rooms.py). Carried
        # verbatim and never read here -- the hub is the relay and knows
        # nothing about anybody's world.
        room = d.get("room")
        if isinstance(room, dict) and room:
            m["room"] = room
        c["peer_in"].append(m)
        keep = int(getattr(self.config.talkapp, "peer_keep", 400) or 400)
        if len(c["peer_in"]) > keep:
            c["peer_in"] = c["peer_in"][-keep:]
        self._save()
        print(f"[talkapp] peer {frm} -> {to}: {text[:60]}" + ("" if known else "  (nobody registered under that id)"))
        return web.json_response({"ok": True, "id": m["id"], "to": to, "known": known})

    async def h_bot_peer(self, request):
        """What another character has said to this one since `after`. The
        cursor is the polling bot's, like /bot/updates, so this never clears
        the mailbox."""
        if not self._authed(request):
            raise web.HTTPForbidden()
        cid = request.query.get("char", "")
        since = int(request.query.get("after", "0") or 0)
        c = self._char(cid)
        out = [dict(m) for m in c["peer_in"] if int(m["id"]) > since]
        return web.json_response({"messages": out})

    async def h_bot_send(self, request):
        if not self._authed(request):
            raise web.HTTPForbidden()
        d = await request.json()
        cid = d["char"]
        c = self._char(cid)
        m = {"id": self._next_id(), "role": "her", "kind": d.get("kind", "text"),
             "text": str(d.get("text", "")), "ts": _now(), "read_ts": None}
        if d.get("media"):
            m["media"] = d["media"]
        c["log"].append(m)
        c["typing_until"] = 0
        self._trim(c)
        self._save()
        await self.broadcast({"type": "message", "char": cid, "msg": m})
        self._push_out(c["name"], m["text"] or ("🎤 voice note" if m["kind"] == "voice" else "file"), char=cid)
        return web.json_response({"id": m["id"]})

    async def h_scenery_img(self, request):
        """A harvested image, for the ops view only (keyed like everything else)."""
        if not self._authed(request):
            raise web.HTTPForbidden()
        name = os.path.basename(request.match_info["name"])
        path = os.path.join(DATA, "..", "scenery", "img", name)
        if not os.path.isfile(path):
            raise web.HTTPNotFound()
        return web.FileResponse(path)

    async def h_bot_photo(self, request):
        """A photo of hers: copied into media, a row of kind `photo`."""
        if not self._authed(request):
            raise web.HTTPForbidden()
        d = await request.json()
        src = d.get("path", "")
        if not os.path.isfile(src):
            return web.json_response({"id": 0})
        name = f"{int(_now() * 1000)}_{os.path.basename(src)}"
        shutil.copy(src, os.path.join(MEDIA, name))
        cid = d["char"]
        c = self._char(cid)
        m = {"id": self._next_id(), "role": "her", "kind": "photo", "text": "",
             "media": name, "ts": _now(), "read_ts": None}
        c["log"].append(m)
        c["typing_until"] = 0
        self._trim(c)
        self._save()
        await self.broadcast({"type": "message", "char": cid, "msg": m})
        self._push_out(c["name"], "📷 photo", char=cid)
        return web.json_response({"id": m["id"]})

    async def h_bot_sticker(self, request):
        """A reaction of hers as a sticker in the chat (sim/reactions.py):
        a frame of her from the episodes, kind `sticker`, not a message she
        wrote. `ts` may be in the past (the backfill); the row is inserted
        where its time falls."""
        if not self._authed(request):
            raise web.HTTPForbidden()
        d = await request.json()
        src = d.get("path", "")
        if not os.path.isfile(src):
            return web.json_response({"id": 0})
        name = f"reaction_{os.path.basename(src)}"
        dst = os.path.join(MEDIA, name)
        if not os.path.exists(dst):
            shutil.copy(src, dst)
        cid = d["char"]
        c = self._char(cid)
        ts = float(d.get("ts") or _now())
        # `auto` marks the ones her mood put there rather than the ones she
        # placed in a reply: the app labels them, so a picture arriving on its
        # own is never mistaken for her saying something.
        m = {"id": self._next_id(), "role": "her", "kind": "sticker", "text": "", "bucket": str(d.get("bucket", ""))[:20],
             "auto": bool(d.get("auto")), "media": name, "ts": ts, "read_ts": None}
        pos = len(c["log"])
        while pos > 0 and c["log"][pos - 1]["ts"] > ts:
            pos -= 1
        c["log"].insert(pos, m)
        self._trim(c)
        self._save()
        await self.broadcast({"type": "message", "char": cid, "msg": m})
        if not d.get("quiet"):
            self._push_out(c["name"], "a sticker", char=cid)
        return web.json_response({"id": m["id"]})

    async def h_bot_voice(self, request):
        if not self._authed(request):
            raise web.HTTPForbidden()
        d = await request.json()
        src = d.get("path", "")
        if not os.path.isfile(src):
            return web.json_response({"id": 0})
        name = f"{int(_now() * 1000)}_{os.path.basename(src)}"
        shutil.copy(src, os.path.join(MEDIA, name))
        cid = d["char"]
        c = self._char(cid)
        # a line he tapped names the bubble it belongs to, so it attaches there
        # however long the render took and whatever she has said since
        want = int(d.get("attach_to", 0) or 0)
        if want:
            m = next((x for x in c["log"] if x["id"] == want), None)
            if m is None:
                return web.json_response({"id": 0})
            m["voice"] = name
            self._save()
            await self.broadcast({"type": "edit", "char": cid, "msg": m})
            return web.json_response({"id": m["id"], "attached": True})
        # The note is her last bubble spoken, so it attaches to that bubble
        # rather than landing as a row of its own. A row of its own was
        # broadcast as a message, and the phone's one notification slot per
        # character then showed "voice note" in place of what she said --
        # every reply, since every reply speaks. It stands alone only when
        # there is no fresh bubble to attach to (`/say`, or a slow render).
        last = c["log"][-1] if c["log"] else None
        if (last and last["role"] == "her" and last.get("kind", "text") == "text"
                and not last.get("voice") and _now() - last["ts"] <= VOICE_ATTACH_SECONDS):
            last["voice"] = name
            self._save()
            await self.broadcast({"type": "edit", "char": cid, "msg": last})
            return web.json_response({"id": last["id"], "attached": True})
        m = {"id": self._next_id(), "role": "her", "kind": "voice", "text": "",
             "media": name, "ts": _now(), "read_ts": None}
        c["log"].append(m)
        self._trim(c)
        self._save()
        await self.broadcast({"type": "message", "char": cid, "msg": m})
        if _now() - self._last_push.get(cid, 0) > 90:
            self._push_out(c["name"], "🎤 voice note", char=cid)
        return web.json_response({"id": m["id"]})

    async def h_bot_typing(self, request):
        if not self._authed(request):
            raise web.HTTPForbidden()
        d = await request.json()
        c = self._char(d["char"])
        c["typing_until"] = _now() + self.config.talkapp.typing_seconds
        await self.broadcast({"type": "typing", "char": d["char"],
                              "until": c["typing_until"]})
        return web.json_response({"ok": True})

    async def h_bot_edit(self, request):
        if not self._authed(request):
            raise web.HTTPForbidden()
        d = await request.json()
        c = self._char(d["char"])
        for m in c["log"]:
            if m["id"] == int(d["id"]):
                m["text"] = str(d.get("text", m["text"]))
                self._save()
                await self.broadcast({"type": "edit", "char": d["char"], "msg": m})
                return web.json_response({"ok": True})
        return web.json_response({"ok": False})

    async def h_bot_delete(self, request):
        if not self._authed(request):
            raise web.HTTPForbidden()
        d = await request.json()
        c = self._char(d["char"])
        n = len(c["log"])
        c["log"] = [m for m in c["log"] if m["id"] != int(d["id"])]
        if len(c["log"]) != n:
            self._save()
            await self.broadcast({"type": "delete", "char": d["char"], "id": int(d["id"])})
        return web.json_response({"ok": len(c["log"]) != n})

    async def h_bot_reads(self, request):
        """His view-based reads of her messages, for the adapter to stamp."""
        if not self._authed(request):
            raise web.HTTPForbidden()
        cid = request.query.get("char", "")
        c = self._char(cid)
        out = {str(m.get("ext") or m["id"]): m["read_ts"] for m in c["log"][-100:]
               if m["role"] == "her" and m["read_ts"]}
        return web.json_response({"reads": out})

    async def h_bot_state(self, request):
        """The bot's periodic sync: her reads of his messages (既読), the
        group chat as she sees it, one presence line."""
        if not self._authed(request):
            raise web.HTTPForbidden()
        d = await request.json()
        cid = d["char"]
        c = self._char(cid)
        changed = []
        for sid, ts in (d.get("her_reads") or {}).items():
            for m in c["log"]:
                if (m["id"] == int(sid) or m.get("ext") == int(sid)) \
                        and m["role"] == "him" and not m["read_ts"]:
                    m["read_ts"] = ts
                    changed.append(m["id"])
        if d.get("group") is not None:
            c["group"] = d["group"]
        if d.get("presence") is not None:
            c["presence"] = d["presence"]
        if d.get("ops") is not None:
            c["ops"] = d["ops"]
        model_changed = False
        if d.get("voice_model") is not None and d["voice_model"] != c.get("voice_model"):
            c["voice_model"] = str(d["voice_model"])
            model_changed = True
        if d.get("voice_models") is not None and d["voice_models"] != c.get("voice_models"):
            c["voice_models"] = list(d["voice_models"])
            model_changed = True
        reaction_changed = False
        if d.get("reaction") is not None and d["reaction"] != c.get("reaction", {}):
            c["reaction"] = d["reaction"]
            reaction_changed = True
        self._save()
        if reaction_changed:
            await self.broadcast({"type": "reaction", "char": cid, "reaction": c["reaction"]})
        if changed:
            await self.broadcast({"type": "kidoku", "char": cid, "ids": changed})
        if d.get("group") is not None:
            await self.broadcast({"type": "group", "char": cid, "group": c["group"],
                                  "presence": c.get("presence", "")})
        if d.get("ops") is not None:
            await self.broadcast({"type": "ops", "char": cid})
        if model_changed:
            # the header redraws itself the moment the toggle takes, so what
            # it says is what the next reply will actually be written on
            await self.broadcast({"type": "model", "char": cid,
                                  "model": c["voice_model"], "models": c["voice_models"]})
        return web.json_response({"ok": True})

    # ---------------- the operator's view ----------------

    async def h_ops(self, request):
        """The bot's latest ops payload and the command log, for the app."""
        if not self._authed(request):
            raise web.HTTPForbidden()
        cid = request.query.get("char", "")
        c = self._char(cid)
        return web.json_response({"ops": c.get("ops", {}), "log": c.get("ops_log", [])[-30:]})

    async def h_ops_cmd(self, request):
        """A slash command from the app's ops view, queued for the bot. It
        never touches the chat log."""
        if not self._authed(request):
            raise web.HTTPForbidden()
        d = await request.json()
        c = self._char(d.get("char", ""))
        text = str(d.get("text", "")).strip()
        if text:
            c["ops_queue"].append(text)
            c["ops_queue"] = c["ops_queue"][-20:]
            self._save()
        return web.json_response({"ok": True, "queued": len(c["ops_queue"])})

    # ---------------- swipes and the model toggle ----------------

    def _queue(self, c, text):
        """A command for her bot, on the same queue the ops bar uses. The hub
        answers none of this itself: it has no model, no key and no copy of
        the prompt a redraw has to be made from."""
        c["ops_queue"].append(text)
        c["ops_queue"] = c["ops_queue"][-20:]
        self._save()

    async def h_bot_swipes(self, request):
        """Her bot's answers for one of her messages, and which one is sitting.

        Trimmed to the messages still in the log, or the candidates of
        something that scrolled out of it would sit here for ever."""
        if not self._authed(request):
            raise web.HTTPForbidden()
        d = await request.json()
        cid = d["char"]
        c = self._char(cid)
        mid = int(d.get("id", 0) or 0)
        if not mid:
            return web.json_response({"ok": False, "why": "which message?"})
        # Merged, not replaced. Three kinds of post arrive here: the answers
        # drawn so far, the waiting line while a rebuild of the moment runs in
        # a second process, and the mark that says the prompt behind them was
        # rebuilt rather than kept. Each carries only its own keys, and a post
        # that replaced the record would take the other two away with it.
        have = dict((c.get("swipes") or {}).get(str(mid)) or {})
        rec = {"items": list(d["swipes"]) if d.get("swipes") is not None else list(have.get("items") or []),
               "sat": int((d.get("sat") if d.get("sat") is not None else have.get("sat", 0)) or 0),
               "rows": [int(x) for x in ((d.get("rows") if d.get("rows") is not None
                                          else have.get("rows")) or [])],
               "pending": str(d["pending"]) if d.get("pending") is not None
                          else str(have.get("pending") or ""),
               "reconstructed": int((d["reconstructed"] if d.get("reconstructed") is not None
                                     else have.get("reconstructed", 0)) or 0),
               "ts": _now()}
        c["swipes"][str(mid)] = rec
        live = {str(m["id"]) for m in c["log"]}
        c["swipes"] = {k: v for k, v in c["swipes"].items() if k in live}
        self._save()
        await self.broadcast({"type": "swipes", "char": cid, "id": mid,
                              "swipes": rec["items"], "sat": rec["sat"],
                              "pending": rec["pending"],
                              "reconstructed": rec["reconstructed"]})
        return web.json_response({"ok": True, "n": len(rec["items"])})

    async def h_swipe(self, request):
        """He tapped swipe on one of her messages: draw that reply again.

        Queued for her bot, like a line he taps to hear. The answer is drawn
        from the prompt frozen when she sent it, which only her save has."""
        if not self._authed(request):
            raise web.HTTPForbidden()
        d = await request.json()
        cid = d.get("char", "")
        c = self._char(cid)
        mid = int(d.get("id", 0) or 0)
        m = next((x for x in c["log"] if x["id"] == mid), None)
        if not m or m["role"] != "her":
            return web.json_response({"ok": False, "why": "not one of her messages"})
        self._queue(c, f"/swipe {mid}")
        return web.json_response({"ok": True, "queued": True})

    async def h_sit(self, request):
        """He picked one of the answers: from here on the conversation goes on
        from that one. The write is her bot's -- her own record first, the
        hub's copy after it."""
        if not self._authed(request):
            raise web.HTTPForbidden()
        d = await request.json()
        cid = d.get("char", "")
        c = self._char(cid)
        mid = int(d.get("id", 0) or 0)
        n = int(d.get("n", 0) or 0)
        rec = (c.get("swipes") or {}).get(str(mid))
        if not rec or not any(int(i.get("n", -1)) == n for i in rec["items"]):
            return web.json_response({"ok": False, "why": "no such answer"})
        self._queue(c, f"/sit {mid} {n}")
        return web.json_response({"ok": True, "queued": True})

    async def h_model(self, request):
        """The model her voice is written on, picked in the chat header.

        Checked against what her bot said it will accept, so a stale page
        cannot queue a name that provider has no slug for."""
        if not self._authed(request):
            raise web.HTTPForbidden()
        d = await request.json()
        cid = d.get("char", "")
        c = self._char(cid)
        name = str(d.get("model", "")).strip()
        if name != "auto" and name not in (c.get("voice_models") or []):
            return web.json_response({"ok": False, "why": "her bot does not offer that one"})
        self._queue(c, f"/voicemodel {name}")
        return web.json_response({"ok": True, "queued": True})

    async def h_speak(self, request):
        """He tapped a line and wants to hear it.

        Queued for her bot rather than answered here: the hub has no voice and
        no key, and the character's own config is what says which voice she has.
        A line she has spoken before comes back from the cache in milliseconds;
        the first time costs one render, which is why nothing is spoken until
        he asks for it.
        """
        if not self._authed(request):
            raise web.HTTPForbidden()
        d = await request.json()
        cid = d.get("char", "")
        c = self._char(cid)
        mid = int(d.get("id", 0) or 0)
        m = next((x for x in c["log"] if x["id"] == mid), None)
        if not m or m["role"] != "her" or not (m.get("text") or "").strip():
            return web.json_response({"ok": False, "why": "nothing to say"})
        # the capability first, before anything is handed back. With the cache
        # check ahead of it this answered for the character who does NOT offer
        # a voice on request, serving a voice note she had already sent: no
        # button draws it, so nothing surfaced, and a check that only holds
        # because the caller is polite is not a check.
        if not c.get("speak"):
            return web.json_response({"ok": False, "why": "this one does not speak on request"})
        if m.get("voice"):
            return web.json_response({"ok": True, "voice": m["voice"], "cached": True})
        if not any(q["id"] == mid for q in c["speak_queue"]):
            c["speak_queue"].append({"id": mid, "text": m["text"], "ts": _now()})
            c["speak_queue"] = c["speak_queue"][-20:]
            self._save()
        return web.json_response({"ok": True, "queued": True})

    async def h_bot_speak(self, request):
        if not self._authed(request):
            raise web.HTTPForbidden()
        c = self._char(request.query.get("char", ""))
        q, c["speak_queue"] = list(c.get("speak_queue", [])), []
        if q:
            self._save()
        return web.json_response({"lines": q})

    async def h_bot_ops(self, request):
        if not self._authed(request):
            raise web.HTTPForbidden()
        c = self._char(request.query.get("char", ""))
        q, c["ops_queue"] = list(c.get("ops_queue", [])), []
        if q:
            self._save()
        return web.json_response({"commands": q})

    async def h_bot_ops_result(self, request):
        if not self._authed(request):
            raise web.HTTPForbidden()
        d = await request.json()
        cid = d.get("char", "")
        c = self._char(cid)
        row = {"ts": _now(), "cmd": str(d.get("cmd", ""))[:200], "text": str(d.get("text", ""))[:30000]}
        c["ops_log"].append(row)
        c["ops_log"] = c["ops_log"][-60:]
        self._save()
        await self.broadcast({"type": "ops_result", "char": cid, "row": row})
        return web.json_response({"ok": True})

    async def h_health(self, request):
        return web.json_response({"ok": True, "chars": list(self.state["chars"])})


def main():
    from config import Config
    config = Config(path=os.path.join(ROOT, "config.json"))
    if not config.talkapp.token:
        # a token is the second wall behind the tailnet; refuse to run open
        print("[talkapp] no talkapp.token in config.json; set one first")
        sys.exit(1)
    hub = Hub(config)
    app = web.Application(client_max_size=32 * 1024 * 1024)
    app.add_routes([
        web.get("/", hub.h_index),
        web.get("/app/{name}", hub.h_static),
        web.get("/media/{name}", hub.h_media),
        web.get("/avatar/{name}", hub.h_avatar),
        web.get("/reaction/{name}", hub.h_reaction_img),
        web.get("/file/{name}", hub.h_file),
        web.get("/vapid", hub.h_vapid),
        web.get("/ver", hub.h_ver),
        web.get("/preview", hub.h_preview),
        web.get("/app", hub.h_app),
        web.get("/sw.js", hub.h_sw),
        web.post("/push/subscribe", hub.h_subscribe),
        web.post("/push/test", hub.h_push_test),
        web.get("/chars", hub.h_chars),
        web.get("/history", hub.h_history),
        web.get("/ws", hub.h_ws),
        web.get("/health", hub.h_health),
        web.post("/bot/register", hub.h_bot_register),
        web.get("/bot/updates", hub.h_bot_updates),
        web.post("/bot/send", hub.h_bot_send),
        web.post("/bot/voice", hub.h_bot_voice),
        web.post("/bot/photo", hub.h_bot_photo),
        web.post("/bot/sticker", hub.h_bot_sticker),
        web.get("/scenery/{name}", hub.h_scenery_img),
        web.post("/bot/typing", hub.h_bot_typing),
        web.post("/bot/edit", hub.h_bot_edit),
        web.post("/bot/delete", hub.h_bot_delete),
        web.get("/bot/reads", hub.h_bot_reads),
        web.post("/bot/state", hub.h_bot_state),
        web.get("/ops", hub.h_ops),
        web.post("/ops/cmd", hub.h_ops_cmd),
        web.post("/swipe", hub.h_swipe),
        web.post("/sit", hub.h_sit),
        web.post("/model", hub.h_model),
        web.post("/bot/swipes", hub.h_bot_swipes),
        web.post("/speak", hub.h_speak),
        web.get("/bot/speak", hub.h_bot_speak),
        web.get("/bot/ops", hub.h_bot_ops),
        web.post("/bot/ops_result", hub.h_bot_ops_result),
        web.post("/bot/peer", hub.h_bot_peer_send),
        web.get("/bot/peer", hub.h_bot_peer),
    ])
    async def _startup(app):
        hub.loop = asyncio.get_running_loop()
    app.on_startup.append(_startup)
    host, port = config.talkapp.host, config.talkapp.port
    print(f"[talkapp] serving on http://{host}:{port} (front with: tailscale serve --bg https / http://127.0.0.1:{port})")
    web.run_app(app, host=host, port=port, print=None)


if __name__ == "__main__":
    main()
