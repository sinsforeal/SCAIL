import json
import time
import base64
import datetime
import threading

import requests

import logger

# Eyes. Everywhere else in the system she reads text about the world; this is
# the one component that looks at a picture. Two callers: a photo he sends over
# Telegram, and the images on the X posts she stops at while scrolling.
#
# Gemini on Vertex AI, authenticated with the service-account key in secerts/.
# Vertex needs an OAuth2 bearer token, so google-auth signs the key's JWT and
# exchanges it; the token lasts an hour and is cached until a minute before it
# expires. Nothing here raises into the loop: every failure logs and returns
# None, and the caller falls back to "she can see that he sent a picture".

_TOKEN_LOCK = threading.Lock()


class Vision:
    def __init__(self, config, store=None):
        self.config = config
        self.c = config.vision
        self._creds = None
        self._project = None
        # the day's call count lives in the save (kv `vision_calls`, {date: n})
        # so that it survives a restart: kept in memory it was reset by every
        # restart and, with the week's restarts, held on two days out of nine
        # (2026-09-04). The in-memory pair is the fallback with no store.
        self.store = store
        self._day = None
        self._count = 0
        # Backing off. Every failure here used to return None and the caller
        # came straight back: 33 "daily call budget spent" lines in two days,
        # 20 auth failures and 7 quota refusals, each one a call that could not
        # have worked. Worse, the scenery harvest turned every empty answer
        # into a usable row of nowhere, so an outage did not just cost nothing,
        # it filled her pool with junk. Nothing waits on this -- a look that
        # cannot happen is skipped and comes back on the next pass.
        self._down_until = 0.0
        self._fails = 0
        self._budget_said = None
        self.enabled = bool(self.c.enabled)
        if self.enabled:
            try:
                info = json.load(open(self.c.key_path, "r", encoding="utf-8"))
                self._project = self.c.project_id or info["project_id"]
            except Exception as e:
                logger.log(f"[vision] key unreadable ({type(e).__name__}); vision off")
                self.enabled = False

    # ---------- auth ----------

    def _token(self):
        """A live access token, refreshed when it is within a minute of expiry."""
        from google.oauth2 import service_account
        import google.auth.transport.requests
        with _TOKEN_LOCK:
            if self._creds is None:
                self._creds = service_account.Credentials.from_service_account_file(
                    self.c.key_path, scopes=["https://www.googleapis.com/auth/cloud-platform"])
            # `google.auth` gives `expiry` as a NAIVE datetime in UTC, and
            # `.timestamp()` on a naive datetime reads it as LOCAL time. On a
            # machine four hours behind UTC that made a token look like it had
            # 300 minutes left when it had 60, so the refresh never fired
            # inside the hour the token was alive and every call for the four
            # hours after it died came back 401 "Request had invalid
            # authentication credentials" until something restarted the
            # process. That is the 20 auth failures in two days; the key was
            # never the problem.
            exp = getattr(self._creds, "expiry", None)
            if exp is not None and exp.tzinfo is None:
                exp = exp.replace(tzinfo=datetime.timezone.utc)
            stale = (not self._creds.token) or (exp is not None and
                                                (exp.timestamp() - time.time()) < 60)
            if stale:
                self._creds.refresh(google.auth.transport.requests.Request())
            return self._creds.token

    # ---------- budget and backing off ----------

    def _budget_ok(self, date_str):
        """A hard daily ceiling on calls, so a runaway loop cannot bill the day away."""
        return self._spent(date_str) < self.c.max_calls_per_day

    def _spent(self, date_str):
        """Calls made on `date_str` so far: from the save when there is one."""
        if self.store is not None:
            try:
                return int(self.store.today_count("vision_calls", date_str))
            except Exception:
                pass
        if self._day != date_str:
            self._day, self._count = date_str, 0
        return self._count

    def _charge(self, date_str):
        """One call made: written to the save the moment it happens."""
        if self.store is not None:
            try:
                self.store.bump_today("vision_calls", date_str)
                return
            except Exception:
                pass
        if self._day != date_str:
            self._day, self._count = date_str, 0
        self._count += 1

    def _back_off(self, why):
        """Wait longer each time, up to `backoff_max_seconds`, and say so once
        rather than on every attempt."""
        self._fails += 1
        base = float(getattr(self.c, "backoff_seconds", 60) or 60)
        cap = float(getattr(self.c, "backoff_max_seconds", 1800) or 1800)
        wait = min(cap, base * (2 ** (self._fails - 1)))
        self._down_until = time.time() + wait
        logger.log(f"[vision] {why}; backing off {int(wait)}s (failure {self._fails})")

    def _recovered(self):
        if self._fails:
            logger.log(f"[vision] answering again after {self._fails} failure(s)")
        self._fails = 0
        self._down_until = 0.0

    def available(self, date_str="", reason=""):
        """Is a call worth making at all? The harvest asks before it opens a
        browser and downloads images it has no way to describe.

        `reason="share"` is the one exemption: a picture that is about to be
        handed to another person is looked at whatever the day's counter says
        (`look`), so the caller must not skip it on the budget either."""
        if not self.enabled:
            return False
        if time.time() < self._down_until:
            return False
        if reason == "share":
            return True
        return self._budget_ok(date_str) if date_str else True

    # ---------- images ----------

    def fetch_image(self, url):
        """Download one image. Returns (mime, bytes) or None. Used for X media,
        which is public on pbs.twimg.com and needs no session."""
        try:
            r = requests.get(url, timeout=self.c.fetch_timeout_seconds,
                             headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 200 or not r.content:
                logger.log(f"[vision] image {r.status_code} for {url[:70]}")
                return None
            if len(r.content) > self.c.max_image_bytes:
                logger.log(f"[vision] image too big ({len(r.content)} bytes)")
                return None
            mime = r.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
            if not mime.startswith("image/"):
                return None
            return mime, r.content
        except Exception as e:
            logger.log(f"[vision] image fetch failed: {type(e).__name__}")
            return None

    # ---------- the call ----------

    def look(self, images, instruction, date_str="", label="", max_tokens=None,
             reason="", about="", _retry=False):
        """images: list of (mime, bytes). Returns the model's text, or None.

        Gemini 3.x always spends some tokens thinking, so max_output_tokens has
        to cover thinking AND the answer or the answer comes back empty -- the
        same trap DeepSeek's reasoning modes set (PROJECT 10)."""
        if not self.enabled or not images:
            return None
        if time.time() < self._down_until:
            return None
        # every call is counted against a day, hers when the caller gives it
        # and the machine's otherwise; a call with no date used to bypass the
        # ceiling altogether
        date_str = date_str or datetime.date.today().isoformat()
        if not self._budget_ok(date_str):
            # She cannot send another person a picture she has not looked at,
            # so a look asked for by the share pipeline is made whatever the
            # counter says (his rule, 2026-09-06: she sent him a lewd bot's cat
            # panel unseen because the day's calls had gone to the harvester
            # half an hour earlier). It is still charged below, and its own
            # ceiling is `social.share_looks_per_day`.
            if reason == "share":
                logger.log(f"[vision] share look outside the day's budget: {about or label}")
            else:
                # once a day, not once a call: this said itself 33 times
                if self._budget_said != date_str:
                    self._budget_said = date_str
                    logger.log(f"[vision] the day's {self.c.max_calls_per_day} calls are spent; "
                               f"nothing more until tomorrow")
                return None
        parts = [{"text": instruction}]
        for mime, data in images[: self.c.max_images_per_call]:
            parts.append({"inlineData": {"mimeType": mime,
                                         "data": base64.b64encode(data).decode("ascii")}})
        body = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "maxOutputTokens": int(max_tokens or self.c.max_output_tokens),
                "temperature": self.c.temperature,
                "thinkingConfig": {"thinkingBudget": int(self.c.thinking_budget)},
            },
            # she is looking at his pictures and at an adult-leaning timeline;
            # a refusal here is a hole in the fiction, not a safety win
            "safetySettings": [{"category": cat, "threshold": "BLOCK_ONLY_HIGH"} for cat in (
                "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_DANGEROUS_CONTENT",
                "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_HARASSMENT")],
        }
        host = ("aiplatform.googleapis.com" if self.c.region == "global"
                else f"{self.c.region}-aiplatform.googleapis.com")
        url = (f"https://{host}/v1/projects/{self._project}/locations/{self.c.region}"
               f"/publishers/google/models/{self.c.model}:generateContent")
        t0 = time.time()
        try:
            r = requests.post(url, headers={"Authorization": f"Bearer {self._token()}",
                                            "Content-Type": "application/json"},
                              json=body, timeout=self.c.timeout_seconds)
        except Exception as e:
            self._back_off(f"call failed ({label}): {type(e).__name__}")
            return None
        self._charge(date_str)
        if r.status_code != 200:
            msg = ""
            try:
                msg = r.json().get("error", {}).get("message", "")[:120]
            except Exception:
                msg = r.text[:120]
            if r.status_code in (401, 403, 429, 500, 503):
                self._back_off(f"{r.status_code} ({label}): {msg}")
            else:
                logger.log(f"[vision] {r.status_code} ({label}): {msg}")
            return None
        d = r.json()
        out = "".join(p.get("text", "")
                      for cand in d.get("candidates", [])
                      for p in cand.get("content", {}).get("parts", [])
                      if not p.get("thought")).strip()
        self._recovered()
        um = d.get("usageMetadata", {})
        logger.log(f"[vision] {label or 'look'}: {len(images)} image(s), {time.time() - t0:.1f}s, "
                   f"{um.get('totalTokenCount', 0)} tokens")
        if not out:
            fin = (d.get("candidates") or [{}])[0].get("finishReason", "")
            # once more before the row is marked undescribed: three blanks in
            # a row on 2026-08-31 skipped the rest of a harvest for a hiccup
            if fin != "MAX_TOKENS" and not _retry:
                logger.log(f"[vision] empty answer ({label}, finish {fin}); asking once more")
                return self.look(images=images, instruction=instruction, date_str=date_str, label=label,
                                 max_tokens=max_tokens, reason=reason, about=about, _retry=True)
            logger.log(f"[vision] empty answer ({label}, finish {fin})")
            return None
        return out

    # ---------- the two callers ----------

    def describe_photo(self, image, caption="", date_str=""):
        """A picture he sent her over Telegram. One or two sentences of what is
        in it, written as what she sees, not as an image-captioning exercise."""
        if not self.c.telegram_enabled:
            return None
        instr = self.config.read_text(self.c.prompt_photo, "Describe this picture plainly in two sentences.")
        if caption:
            instr += f"\n\nHe sent it with this caption: {caption}"
        return self.look([image], instr, date_str, label="his photo")

    def tag_post_images(self, images, text="", author="", date_str="", reason="", about=""):
        """What the picture IS, as tags rather than a sentence.

        Prose was fine for one read and useless afterwards: it could not be
        counted, compared, or matched against his own image activity, which is
        already classified in booru tags. Tags can be, and they cache -- the
        same picture never needs a second call."""
        if not self.c.x_enabled:
            return None
        instr = (
            "Tag this image the way a booru does, for a catalogue.\n\n"
            "Return lower_snake_case tags: subject count (1girl, 2girls, no_humans), who and what "
            "(hair colour and length, eye colour, clothing, uniform, yukata, glasses), the setting "
            "(classroom, beach, night, rain, festival, konbini), what is happening (sitting, eating, "
            "waving, crying), the register (chibi, official_art, screenshot, fan_art, photo, meme, "
            "text_only), and the mood (cute, cosy, dramatic, funny, lewd). Twenty at most, fewer is "
            "fine, and only what is actually visible.\n\n"
            "`characters` and `series` only when you genuinely recognise them; an empty list is the "
            "right answer when you do not. `subject` is one short line saying what the image is. "
            "`rating` is safe, suggestive or explicit.\n\n"
            'Output ONLY this JSON: {"subject": "...", "tags": ["..."], "characters": ["..."], '
            '"series": ["..."], "rating": "safe"}'
        )
        ctx = []
        if author:
            ctx.append(f"posted by @{author}")
        if text:
            ctx.append(f"the post says: {text[:200]}")
        if ctx:
            instr += "\n\nContext: " + "; ".join(ctx)
        raw = self.look(images, instr, date_str, label=f"tag @{author}"[:40],
                        max_tokens=self.c.x_max_output_tokens, reason=reason, about=about)
        if not raw:
            return None
        try:
            import json as _json
            import re as _re
            m = _re.search(r"\{.*\}", raw, _re.DOTALL)
            return _json.loads(m.group(0)) if m else None
        except (ValueError, AttributeError):
            return None

    def describe_post_images(self, images, text="", author="", date_str=""):
        """The pictures on one X post she stopped at."""
        if not self.c.x_enabled:
            return None
        instr = self.config.read_text(self.c.prompt_x, "Describe what is in these images in one sentence.")
        ctx = []
        if author:
            ctx.append(f"posted by @{author}")
        if text:
            ctx.append(f"the post says: {text[:200]}")
        if ctx:
            instr += "\n\nContext: " + "; ".join(ctx)
        return self.look(images, instr, date_str, label=f"x post @{author}"[:40],
                         max_tokens=self.c.x_max_output_tokens)
