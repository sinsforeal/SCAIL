import os
import sys
import json

import atomic
import hashlib
import datetime
import threading
import queue
import subprocess
import time
import binascii
import re
import requests
import logger

VOICE_EMOTIONS = {
    "joy": "happy", "amusement": "happy", "excitement": "happy",
    "sadness": "sad", "grief": "sad", "remorse": "sad",
    "anger": "angry", "fear": "fearful", "disgust": "disgusted",
    "surprise": "surprised", "relief": "calm",
}


def voice_tag(text):
    """Add an audio-only performance cue when the written line acts it out."""
    line = str(text or "")
    if re.search(r"(?:ふふ|はは|あはは|えへへ|（笑）|\(笑\))", line):
        return "(laughs) " + line
    if re.search(r"(?:はぁ[…。．]|ふぅ[…。．]|ため息)", line):
        return "(sighs) " + line
    return line


INTERJECTIONS = {"(laughs)", "(chuckle)", "(coughs)", "(clear-throat)",
                 "(groans)", "(breath)", "(pant)", "(inhale)", "(exhale)",
                 "(gasps)", "(sniffs)", "(sighs)", "(snorts)", "(burps)",
                 "(lip-smacking)", "(humming)", "(hissing)", "(emm)", "(sneezes)"}

# Renders her voice lines: a short spoken Japanese phrase, not the message.
# The MiniMax script (async API, polls, sanitizes to FLAC) is driven as a
# subprocess; the FLAC is converted to OGG/Opus so Telegram shows it as a
# voice note rather than an attached file. Failures are logged and dropped;
# a missing voice never blocks a text. Every rendered line is kept under
# data/voice keyed by its text, so a line she says again costs nothing and
# sounds the same as last time. Lines waiting to be rendered are kept in
# pending.json so a restart mid-render re-sends them instead of dropping
# them (the 07:43 line on 2026-08-19 finished rendering eleven minutes
# after the process that asked for it was gone).


class TTSQueue:
    def __init__(self, config, tg):
        self.config = config
        self.tg = tg
        self.q = queue.Queue()
        # scratch for the render; the kept audio lives in the cache dir
        # absolute: the MiniMax script runs with its own directory as cwd
        base = os.path.abspath(os.path.join(os.path.dirname(config.tts.cache_dir) or "data", "tts_jobs"))
        self.inp_dir = os.path.join(base, "inputs")
        self.out_dir = os.path.join(base, "outputs")
        os.makedirs(self.inp_dir, exist_ok=True)
        os.makedirs(self.out_dir, exist_ok=True)
        self.cache_dir = os.path.abspath(config.tts.cache_dir)
        os.makedirs(self.cache_dir, exist_ok=True)
        self.index_path = os.path.join(self.cache_dir, "index.json")
        self.index = self._load_index()
        self.processed = 0
        self.failed = 0
        self.last_error = ""
        self.last_render_seconds = 0.0
        # The queue of lines waiting to be rendered survives a restart in a
        # file, and that file belongs to ONE character. The scratch dir is the
        # machine's and both characters use it, so a single pending.json meant
        # the first process to boot picked up whatever the other one had left
        # and said it -- her line, in the wrong voice, in the wrong chat. The
        # program name keys it; a character with no program keeps the old path.
        who = str(getattr(config.character, "program", "") or "").strip()
        self.pending_path = os.path.join(base, f"pending_{who}.json" if who else "pending.json")
        self.pending = self._load_pending()
        self._minimax_cfg = None
        threading.Thread(target=self._run, daemon=True).start()
        logger.log(f"[TTS] voice worker started ({config.tts.mode})")
        self._recover()

    def enqueue(self, text):
        if not self.config.tts.enabled or not text or not text.strip():
            return
        text = text.strip()
        self.pending.append({"text": text, "ts": time.time()})
        self._save_pending()
        self.q.put(text)

    def _load_pending(self):
        if os.path.exists(self.pending_path):
            try:
                with open(self.pending_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _save_pending(self):
        try:
            atomic.write_json(self.pending_path, self.pending)
        except Exception as e:
            logger.log(f"[TTS] could not save pending: {e}")

    def _done(self, text):
        self.pending = [p for p in self.pending if p.get("text") != text]
        self._save_pending()

    def _recover(self):
        """Lines left unsent by the previous process: render the recent ones, drop the stale."""
        if not self.pending:
            return
        max_age = self.config.tts.recover_max_age_minutes * 60
        now = time.time()
        keep = []
        for p in self.pending:
            age = now - float(p.get("ts", 0))
            if age <= max_age:
                keep.append(p)
                self.q.put(p["text"])
                logger.log(f"[TTS] re-queued from last run ({age / 60:.0f} min old): {p['text']}")
            else:
                logger.log(f"[TTS] dropped stale line from last run ({age / 60:.0f} min old): {p['text']}")
        self.pending = keep
        self._save_pending()

    def status(self):
        return (f"voice: {'on' if self.config.tts.enabled else 'off'} ({self.config.tts.mode}) | queue {self.q.qsize()} | done {self.processed} | failed {self.failed}"
                f" | last render {self.last_render_seconds:.1f}s"
                + (f" | last error: {self.last_error}" if self.last_error else ""))

    def _clip_for(self, text):
        """A recorded clip for this line, if the channel has one.

        The VN channel holds her generated line against the koikano record and
        hands back the file when she has already spoken it; a recorded line
        costs nothing and is in her own voice, so it is preferred over
        synthesis. The phone and Telegram channels have no such table and
        return None, so their path is unchanged. A lookup that raises is a
        miss: synthesis is the fallback, never a crash."""
        resolver = getattr(self.tg, "clip_for", None)
        if not callable(resolver):
            return None
        try:
            return resolver(text)
        except Exception as e:
            logger.log(f"[TTS] clip lookup failed: {type(e).__name__}: {e}")
            return None

    def _minimax(self):
        """The MiniMax script's own config: key, model, voice, so the two paths sound the same."""
        if self._minimax_cfg is None:
            with open(self.config.tts.minimax_config_path, "r", encoding="utf-8") as f:
                self._minimax_cfg = json.load(f)
        return self._minimax_cfg

    def _voice_setting(self, mc, emotion=None):
        """Whose voice this is. The MiniMax config file is shared by everything
        on this machine and names a single voice, so a second character would
        otherwise speak in the first one's. `tts.voice_id` in a character's own
        config wins; empty keeps the shared setting, which is what the first
        character has always had."""
        vs = dict(mc.get("voice_setting") or {})
        own = str(getattr(self.config.tts, "voice_id", "") or "").strip()
        if own:
            vs["voice_id"] = own
        mapped = VOICE_EMOTIONS.get(str(emotion or "").lower()) if getattr(self.config.tts, "emotion_enabled", False) else None
        if mapped:
            vs["emotion"] = mapped
        return vs

    def _speech_options(self, text, emotion=None, interjection=""):
        t = self.config.tts
        tag = interjection if interjection in INTERJECTIONS else ""
        spoken = (tag + " " + text) if tag else (voice_tag(text) if getattr(t, "interjection_tags", False) else text)
        language = str(getattr(t, "language_boost", "") or "")
        pronunciation = getattr(t, "pronunciation_dict", None) or {}
        # Config.Section wraps nested dictionaries. The cache key and the
        # HTTP JSON body both need ordinary JSON data, not that wrapper.
        if not isinstance(pronunciation, dict):
            pronunciation = dict(vars(pronunciation))
        return spoken, language, pronunciation, emotion

    def _render_sync(self, text, flac, emotion=None, interjection=""):
        """The synchronous endpoint: audio comes back inline, about a second for a short line."""
        t = self.config.tts
        mc = self._minimax()
        spoken, language, pronunciation, _ = self._speech_options(text, emotion, interjection)
        payload = {
            "model": mc.get("model_id", "speech-2.8-hd"),
            "text": spoken,
            "stream": False,
            # the shared MiniMax config names one voice for the whole
            # machine; a character with her own id overrides it, so two
            # personas do not speak in the same voice
            "voice_setting": self._voice_setting(mc, emotion),
            "audio_setting": {"sample_rate": 32000, "bitrate": 128000, "format": "flac", "channel": 1},
        }
        if language:
            payload["language_boost"] = language
        if pronunciation:
            payload["pronunciation_dict"] = pronunciation
        r = requests.post(t.sync_endpoint, json=payload, timeout=(10, t.sync_timeout_seconds),
                          headers={"Authorization": f"Bearer {mc['api_key']}", "Content-Type": "application/json"})
        if r.status_code != 200:
            raise RuntimeError(f"sync http {r.status_code}: {r.text[:200]}")
        j = r.json()
        base = j.get("base_resp") or {}
        if base.get("status_code", 0) != 0:
            raise RuntimeError(f"sync api {base.get('status_code')}: {base.get('status_msg')}")
        hexdata = (j.get("data") or {}).get("audio") or ""
        if not hexdata:
            raise RuntimeError("sync api returned no audio")
        with open(flac, "wb") as f:
            f.write(binascii.unhexlify(hexdata))
        return True

    def _render_script(self, text, flac, inp, emotion=None, interjection=""):
        t = self.config.tts
        spoken, language, pronunciation, _ = self._speech_options(text, emotion, interjection)
        mapped = VOICE_EMOTIONS.get(str(emotion or "").lower()) if getattr(t, "emotion_enabled", False) else None
        if language or pronunciation or mapped or spoken != text:
            raise RuntimeError("async script cannot preserve the selected voice emotion, language, pronunciation or interjection tag")
        script = t.minimax_script_path
        if not script or not os.path.exists(script):
            raise RuntimeError(f"script missing: {script}")
        with open(inp, "w", encoding="utf-8") as f:
            f.write(spoken)
        cmd = [sys.executable, os.path.abspath(script), "--config", os.path.abspath(t.minimax_config_path), "--input", inp, "--output", flac]
        # the script writes its own log next to itself; run it from there
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                             encoding="utf-8", errors="replace",
                             cwd=os.path.dirname(script), timeout=900)
        if res.returncode != 0 or not os.path.exists(flac):
            raise RuntimeError(f"minimax exit {res.returncode}: {(res.stderr or res.stdout)[-300:]}")
        return True

    def _render_async(self, text, flac, emotion=None, interjection=""):
        """Compatible MiniMax fallback with the same speech options as sync."""
        mc = self._minimax()
        spoken, language, pronunciation, _ = self._speech_options(text, emotion, interjection)
        payload = {
            "model": mc.get("model_id", "speech-2.8-hd"), "text": spoken,
            "voice_setting": self._voice_setting(mc, emotion),
            "audio_setting": {"sample_rate": 32000, "bitrate": 128000,
                              "format": "flac", "channel": 1},
        }
        if language:
            payload["language_boost"] = language
        if pronunciation:
            payload["pronunciation_dict"] = pronunciation
        headers = {"Authorization": f"Bearer {mc['api_key']}", "Content-Type": "application/json"}
        base = "https://api.minimax.io/v1"
        def checked(response, step):
            response.raise_for_status()
            data = response.json()
            status = data.get("base_resp") or {}
            if status.get("status_code", 0) != 0:
                raise RuntimeError(f"async {step}: {status.get('status_code')} {status.get('status_msg')}")
            return data
        created = checked(requests.post(base + "/t2a_async_v2", json=payload,
                                        headers=headers, timeout=(10, 20)), "create")
        task_id = created.get("task_id")
        file_id = created.get("file_id")
        if not task_id:
            raise RuntimeError("async create returned no task id")
        deadline = time.monotonic() + float(getattr(self.config.tts, "async_fallback_timeout_seconds", 35))
        while time.monotonic() < deadline:
            status = checked(requests.get(base + "/query/t2a_async_query_v2",
                                          params={"task_id": task_id}, headers=headers,
                                          timeout=(10, 15)), "query")
            state = str(status.get("status") or "").lower()
            if state == "success":
                file_id = status.get("file_id") or file_id
                break
            if state in ("failed", "expired"):
                raise RuntimeError(f"async task {state}")
            time.sleep(min(2.0, max(0.0, deadline - time.monotonic())))
        else:
            raise RuntimeError("async fallback timed out")
        if not file_id:
            raise RuntimeError("async task returned no file id")
        file_info = checked(requests.get(base + "/files/retrieve", params={"file_id": file_id},
                                         headers=headers, timeout=(10, 15)), "retrieve")
        url = (file_info.get("file") or {}).get("download_url")
        if not url or not str(url).startswith("https://"):
            raise RuntimeError("async retrieve returned no secure download URL")
        audio = requests.get(url, timeout=(10, 25))
        audio.raise_for_status()
        if not audio.content:
            raise RuntimeError("async download returned no audio")
        with open(flac, "wb") as f:
            f.write(audio.content)
        return True

    def _load_index(self):
        if os.path.exists(self.index_path):
            try:
                with open(self.index_path, "r", encoding="utf-8") as f:
                    idx = json.load(f)
            except Exception:
                return {}
            # The cache is addressed by file name. It used to hold the full
            # path of each ogg, so moving the project made every cached line
            # miss and be rendered and paid for again (the rename to SCAILV3
            # on 2026-08-20 cost all 45 of them). Old entries are healed here.
            fixed = 0
            for e in idx.values():
                o = str(e.get("ogg", ""))
                if o and (os.path.sep in o or "/" in o):
                    e["ogg"] = os.path.basename(o)
                    fixed += 1
            if fixed:
                self.index = idx
                self._save_index()
                logger.log(f"[TTS] cache index: {fixed} entr(ies) reduced to file names")
            return idx
        return {}

    def _ogg_path(self, stored):
        """Where that cached line lives now, wherever the project sits."""
        return os.path.join(self.cache_dir, os.path.basename(str(stored or "")))

    def _save_index(self):
        atomic.write_json(self.index_path, self.index, indent=1)

    def _key(self, text, emotion=None, interjection=""):
        """The cache key is the line AND the voice saying it.

        It was the line alone, and the cache directory is shared by every
        character on this machine, so the second character saying anything the
        first had already said would have been handed the first one's audio.
        Two Japanese girls reach 「うん」 and 「ごめん」 within the first day. A
        character's own `tts.voice_id` is part of the key now, which also means
        changing a voice re-synthesises rather than serving the old one."""
        voice = str(getattr(self.config.tts, "voice_id", "") or "shared")
        norm = "".join(text.split()).strip("。！？!?…・")
        spoken, language, pronunciation, _ = self._speech_options(text, emotion, interjection)
        mapped = VOICE_EMOTIONS.get(str(emotion or "").lower()) if getattr(self.config.tts, "emotion_enabled", False) else None
        if not (language or pronunciation or mapped or spoken != text):
            material = voice + "\x00" + norm  # retain existing characters' cache
        else:
            material = json.dumps({"voice": voice,
                                   "voice_setting": self._voice_setting(self._minimax(), emotion),
                                   "model": self._minimax().get("model_id", "speech-2.8-hd"),
                                   "text": spoken, "emotion": mapped,
                                   "language": language, "pronunciation": pronunciation},
                                  ensure_ascii=False, sort_keys=True)
        return hashlib.sha1(material.encode("utf-8")).hexdigest()[:16]

    def cached_path(self, text, emotion=None, interjection=""):
        k = self._key(text, emotion, interjection)
        entry = self.index.get(k)
        if not entry or not entry.get("ogg"):
            return None
        path = self._ogg_path(entry["ogg"])
        return path if os.path.exists(path) else None

    def _remember(self, text, ogg, emotion=None, interjection=""):
        k = self._key(text, emotion, interjection)
        now = datetime.datetime.now().isoformat(timespec="seconds")
        name = os.path.basename(str(ogg))
        entry = self.index.get(k, {"text": text, "ogg": name, "first": now, "uses": 0})
        entry["ogg"] = name
        entry["last"] = now
        entry["uses"] = entry.get("uses", 0) + 1
        self.index[k] = entry
        self._save_index()

    def speak_on_demand(self, text, deliver):
        """He tapped a line and wants to hear it: render, hand the file back.

        On the same worker as the voice notes, so two renders never run at
        once, and never in `pending.json` -- a tap is not owed to him across a
        restart the way a line she meant to speak is. `deliver` is called with
        the path; if she has said this before it is a cache hit and returns in
        milliseconds, which is what makes tapping it again free.
        """
        if not self.config.tts.enabled or not text or not text.strip():
            return
        self.q.put({"speak": text.strip(), "deliver": deliver})

    def render_wait(self, text, timeout=90.0, emotion=None, interjection=""):
        """Make a line's clip now and hand back its path, waiting for the
        worker.

        The reply path prepares every line's voice before the first line is
        shown, so he can click through the whole reply without ever waiting on
        synthesis and the ready mark can mean the whole reply is ready
        (2026-09-17). A cache hit returns at once; a failure returns None and
        the reply still goes, just unvoiced."""
        if not self.config.tts.enabled or not text or not text.strip():
            return None
        done = threading.Event()
        box = {}

        def _deliver(path):
            box["path"] = path
            done.set()

        self.q.put({"speak": text.strip(), "deliver": _deliver,
                    "emotion": emotion, "interjection": interjection})
        done.wait(timeout)
        return box.get("path")

    def _run(self):
        while True:
            job = self.q.get()
            on_demand = isinstance(job, dict)
            text = job["speak"] if on_demand else job
            try:
                if on_demand:
                    path = self.render(text, emotion=job.get("emotion"),
                                       interjection=job.get("interjection", ""))
                    if path:
                        job["deliver"](path)
                    else:
                        # Signal the waiter with nothing. It used to be left
                        # unsignalled, so `render_wait` blocked its whole
                        # timeout on a line that had already failed and the
                        # reply waited 90 s on a render that was never coming
                        # (2026-09-17). A `speak_on_demand` delivery gets None
                        # and does nothing, which is the same miss.
                        logger.log(f"[TTS] nothing to play back for: {text[:40]}")
                        job["deliver"](None)
                else:
                    self._render_and_send(text)
            except Exception as e:
                self.failed += 1
                self.last_error = str(e)
                logger.log(f"[TTS] error: {e}")
            finally:
                if not on_demand:
                    self._done(text)
                self.q.task_done()

    def render(self, text, emotion=None, interjection=""):
        """The audio for a line, cached: a path, or None if it could not be made.

        Split out of `_render_and_send` so that making the sound and pushing it
        at him are two decisions. A character who does not send voice notes can
        still be asked to speak a line he taps -- same synthesis, same cache,
        same voice -- and the second time he taps it costs nothing.
        """
        clip = self._clip_for(text)
        if clip:
            return clip
        cached = self.cached_path(text, emotion, interjection)
        if cached:
            return cached
        t = self.config.tts
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        inp = os.path.join(self.inp_dir, f"in_{stamp}.txt")
        flac = os.path.join(self.out_dir, f"out_{stamp}.flac")
        ogg = os.path.join(self.cache_dir, f"{self._key(text, emotion, interjection)}.ogg")
        t0 = time.time()
        rendered = False
        if t.mode == "sync":
            try:
                rendered = self._render_sync(text, flac, emotion, interjection)
            except Exception as e:
                logger.log(f"[TTS] sync render failed ({e}); falling back to the script")
        if not rendered:
            try:
                options = self._speech_options(text, emotion, interjection)
                mapped = VOICE_EMOTIONS.get(str(emotion or "").lower()) if getattr(t, "emotion_enabled", False) else None
                if options[1] or options[2] or mapped or options[0] != text:
                    rendered = self._render_async(text, flac, emotion, interjection)
                else:
                    rendered = self._render_script(text, flac, inp, emotion, interjection)
            except Exception as e:
                self.failed += 1
                self.last_error = str(e)
                logger.log(f"[TTS] {self.last_error}")
                return None
        self.last_render_seconds = time.time() - t0
        conv = subprocess.run([t.ffmpeg, "-y", "-loglevel", "error", "-i", flac, "-c:a", "libopus",
                               "-b:a", "48k", "-vbr", "on", "-application", "voip", ogg],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace")
        if conv.returncode == 0 and os.path.exists(ogg):
            self._remember(text, ogg, emotion, interjection)
            return ogg
        return flac if os.path.exists(flac) else None

    def _render_and_send(self, text):
        """A voice note of hers: the same render and cache as a line he taps
        (`render`), then the send -- the note as opus, the raw audio when
        the conversion failed."""
        clip = self._clip_for(text)
        cached = None if clip else self.cached_path(text)
        if clip:
            logger.log(f"[TTS] voice from a recorded clip: {text} -> {os.path.basename(clip)}")
        elif not cached:
            logger.log(f"[TTS] rendering: {text}")
        path = clip or self.render(text)
        if not path:
            return
        sent = path.endswith(".ogg") and self.tg.send_voice(path)
        if not sent:
            sent = self.tg.send_audio(path)
        if sent:
            self.processed += 1
            if clip:
                logger.log(f"[TTS] recorded clip sent: {os.path.basename(path)}")
            elif cached:
                logger.log(f"[TTS] voice sent from cache: {text}")
            else:
                logger.log(f"[TTS] voice sent ({os.path.basename(path)}, render {self.last_render_seconds:.1f}s)")
        else:
            self.failed += 1
            self.last_error = "telegram upload failed"
            logger.log("[TTS] telegram upload failed")
