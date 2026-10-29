# -*- coding: utf-8 -*-
"""The visual-novel channel: her turns on a stage instead of in bubbles.

Same nine-method seam as `channels/base.py` defines and `talkapp_bot.py` also
implements -- the runtime still calls `send_message`, `send_voice`,
`get_new_messages` and the rest --
but instead of a chat bubble the turn is drawn as a koikano VN frame: her
sprite (base PNG plus diff PNG), the face badge, the message window with her
words, and the voice audio. The player's typed line is the inbound message,
so `poll_inbound` / `maybe_reply` / `delivery` flow exactly as they do for a
phone; only the mouth and the ears are different.

A stdlib `ThreadingHTTPServer` runs in a daemon thread and carries turns
between this object and the browser. The runtime owns the loop; this object
only holds the latest turn, serves it at `/state.json`, and queues what the
browser posts to `/say` for the next `get_new_messages`. No third-party
dependency, no outbound call: with the model refused the stage still draws and
the view still serves.

Her feeling rides in on two wires the runtime already sets: `reaction_provider`
(the mood-band face, `sim/reactions.py`) and the words themselves. Both are
handed to `VnExpression`, which will only name an asset that is on disk.
"""

import datetime
import json
import os
import queue
import re
import shutil
import subprocess
import struct
import sys
import threading
import time
import random
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

import logger
from channels.base import Channel
from channels.vn_expression import VnExpression
from channels.vn_voice import VoiceIndex, VOICE_MODES, voice_mode
from sim import wiring


CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".ogg": "audio/ogg",
    ".opus": "audio/ogg",
    ".flac": "audio/flac",
    ".wav": "audio/wav",
    ".txt": "text/plain; charset=utf-8",
}

DEFAULTS = {
    "enabled": False,
    "host": "127.0.0.1",
    "port": 8770,
    "view_dir": "view",
    "out_dir": "data/vn",
    "default_expression": "neutral",
    "sprite_zoom": 1.55,
    "idle_motion": True,
    "idle_sway": False,
    "bgm_dir": "",
    "default_bgm": "BGM03",
}

# The mood a track stands for, read backwards from the corpus's own titles
# (`sim/scene.py:MOOD_BGM`). A track he picks by hand takes the scene mood of
# its title; a track not here leaves the staging's own mood alone.
TRACK_MOOD = {
    "BGM03": "neutral",
    "BGM16": "warm",
    "BGM12": "cool",
    "BGM05": "dim",
    "BGM02": "bright",
    "BGM11": "tense",
    "BGM15": "tender",
    "BGM13": "sad",
    "BGM18": "nostalgic",
    "BGM26": "romantic",
}

# The face that scene mood is drawn with. The scene's light vocabulary is not
# the face vocabulary, so each is named; only the moods with a face move her,
# and a mood with none leaves her face to her own words.
TRACK_MOOD_EXPRESSION = {
    "neutral": "neutral",
    "warm": "smile",
    "cool": "neutral",
    "dim": "neutral",
    "bright": "smile",
    "tense": "worried",
    "tender": "smile",
    "sad": "sad",
    "nostalgic": "neutral",
    "romantic": "smile",
}


class VnInterface(Channel):
    # A tap on the sprite, by region. `clips` are her recorded voice lines,
    # one picked at random per touch. `label` -> EMOTION_OVERLAY overlay.
    # head: pat (laughs, heart, SE074, cute giggles). face: poke (smile,
    # flustered). shoulder: touch (talk, neutral sounds). body: too forward
    # (worried, annoyed/surprised clips).
    TOUCH_REACTIONS = {
        "head":     {"signal": {"expression": "laugh", "label": "love"},          "sound": "SE074",
                     "clips": ["MMK041003", "MMK040455", "MMK000085"]},
        "face":     {"signal": {"expression": "smile", "label": "embarrassment"}, "sound": "",
                     "clips": ["MMK001188", "MMK041159", "MMK040329"]},
        "shoulder": {"signal": {"expression": "talk"},                           "sound": "",
                     "clips": ["MMK000140", "MMK001149"]},
        "body":     {"signal": {"expression": "worried", "label": "nervousness"}, "sound": "",
                     "clips": ["MMK040186", "MMK040724"]},
    }
    TOUCH_COOLDOWN = 4.0  # seconds; a click storm should not spam _set_face/_notify
    # What she'd tell herself happened, logged as an event so next turn's
    # context carries it (see handle_touch -> self.store.add_event).
    TOUCH_EVENT_TEXT = {
        "head":     "he patted my head",
        "face":     "he poked my cheek",
        "shoulder": "he touched my shoulder",
        "body":     "he touched me somewhere too forward",
    }
    # Small, fixed-size gauge bumps a touch causes, applied straight to
    # self.state.gauges via the gauge_nudge callback (see __init__ and
    # handle_touch) rather than through state.apply()'s habituation /
    # diminishing-returns path. affection and mood have model_may_move:
    # false, but code is still allowed to move them a little.
    TOUCH_GAUGE_DELTAS = {
        "head":     {"affection": 2, "pride": 1},
        "face":     {"shame": 2, "affection": 1},
        "shoulder": {"relief": 1},
        "body":     {"anxiety": 3, "shame": 2, "affection": -1},
    }

    def __init__(self, config, vision=None, clock=None, store=None):
        self.config = config
        self.vision = vision
        self.clock = clock
        self.store = store
        c = self._vn_cfg()
        self.root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.host = str(c.get("host") or DEFAULTS["host"])
        self.port = int(c.get("port") or DEFAULTS["port"])
        self.active_chat_id = "vn"            # read by scail for "is a chat bound"
        self.console_only = False
        self.max_length = 4096
        self.name = self._character_name()
        self.full = self._character_full()
        self.ops_provider = None              # set by scail
        self.reaction_provider = None         # set by scail: () -> {bucket, ...}
        self.scene_provider = None            # set by scail: () -> {bg, camera, ...}
        self.emotion_provider = None          # set by scail: (text) -> label
        self.voice_model_provider = None      # set by scail
        self.voice_model_setter = None        # set by scail: (name) -> what changed
        self.stage_model_provider = None      # set by scail: the stage roles' model
        self.stage_model_setter = None        # set by scail: (name) -> what changed
        # set by scail: the out-of-character console behind the director button.
        # `stage_chat` is (text) -> {reply, proposal} or None; `stage_history`
        # is () -> the console chat so far; `stage_snapshot` is () -> what it is
        # told (the current scene and the catalogs).
        self.stage_chat = None
        self.stage_history = None
        self.stage_snapshot = None
        self.graph = None                     # set by scail
        # set by scail: () -> he touched the stage; the reunion clock reads it
        self.present_notice = None
        self.save_busy_provider = None       # set by scail: reply or delivery in flight
        self.reply_draw_provider = None
        self.reply_sit_provider = None
        self.gauge_nudge = None       # set by scail: (deltas_dict, reason) -> None
        # set by scail: (text, id) -> render the tapped line now and attach it
        self.speak_now = None
        # paths the view server reads and writes
        self.view_dir = self._resolve(c.get("view_dir") or DEFAULTS["view_dir"])
        self.out_dir = self._resolve(c.get("out_dir") or DEFAULTS["out_dir"])
        self.voice_dir = os.path.join(self.out_dir, "voice")
        self.state_path = os.path.join(self.out_dir, "state.json")
        self.saves_dir = os.path.join(self.out_dir, "saves")
        self.checkpoints_dir = os.path.join(self.out_dir, "checkpoints")
        self.load_status_path = os.path.join(self.out_dir, "load_status.json")
        self._load_requested = False
        os.makedirs(self.voice_dir, exist_ok=True)
        self.expr = VnExpression(c, root=self.root)
        # Her recorded koikano lines: a table built from the game record
        # (`tools/voice_index.py`) and the clips it names, read in place from
        # the corpus. A generated line that is one of them is played from tape
        # rather than synthesised; a miss falls through to MiniMax.
        self.clip_dir = os.path.join(self._resolve(c.get("character_dir") or ""),
                                     c.get("voice_dir") or "voice")
        self.voice_index = VoiceIndex(os.path.join(self.out_dir, "voice_index.json"),
                                      self.clip_dir)
        # the two art directories the stage draws besides the sprite: the
        # backgrounds `sim/scene.py` names and the emotion overlays a label
        # carries. Both are the game's, read in place.
        self.bg_dir = self._resolve(c.get("bg_dir"))
        self.emotion_dir = self._resolve(c.get("emotion_dir"))
        # the music `sim/scene.py` names, read in place from the game's own
        # `audio/bgm`; a config with no corpus simply has none and the stage
        # plays nothing
        self.bgm_dir = self._resolve(c.get("bgm_dir"))
        self.se_dir = self._resolve(c.get("se_dir") or os.path.join(os.path.dirname(self.bgm_dir), "se"))
        self.frame_dir = self._resolve(c.get("frame_dir") or os.path.join(os.path.dirname(self.bg_dir), "frame"))
        self.default_bgm = str(c.get("default_bgm") or DEFAULTS["default_bgm"])
        # the browser talks to the next poll's loop
        self._inbox = queue.Queue()
        self._inbound_next = 1
        # the latest turn, and the few before it for edit / delete
        self._rev = 0
        self._hub_next = 1
        self._history = []
        self._prepared_emotions = {}
        try:
            self._used_vocal_cue = str(self.store.get("vn_used_vocal_cue", "") or "")
        except Exception:
            self._used_vocal_cue = ""
        try:
            self._used_face_cue = str(self.store.get("vn_used_face_cue", "") or "")
        except Exception:
            self._used_face_cue = ""
        self._shown_id = 0
        self._audio_url = None
        self._user_text = ""
        self._last_touch_ts = 0   # cooldown clock for /touch (handle_touch)
        # The stage's own controls, toggled from the page. The toggles, voice
        # source and hand-picked stage choices belong to the save so a restart
        # resumes the frame he selected.
        self._auto_voice = self._stored_control("vn_auto_voice", bool(c.get("auto_voice", False)))
        self._quality_on = self._stored_control("vn_quality", self._quality_default())
        # Where her voice comes from: `tts` synthesises every line, `exact`
        # plays a recorded clip only when she said the line verbatim on tape,
        # `approximate` also plays a near miss. The config seeds it; a stage
        # control overrides it and the choice is kept.
        self._voice_mode = self._stored_voice_mode()
        self._scene_request = None
        self._scene_notice_request = None
        # The console's approved proposal and its clear, held for the runtime to
        # apply on the loop thread (never on the HTTP thread: writing a scene is
        # the one writer's and the loop's).
        self._director_request = None
        self._director_clear = False
        # An outfit he picked by hand, held for the loop to let her notice it
        # (the sprite changes at once; the reaction is a turn).
        self._outfit_request = None
        self._bg_override = self._stored_background_override()
        # The outfit the stage manager set, as the corpus's costume id
        # (`channels/vn_expression.py`, `CD01`..`CD07`). None draws the default.
        self._costume_override = self._stored_costume_override()
        # A track picked by hand on the stage. It stands until he picks
        # "director" again, unlike the background, because music flipping back
        # every turn would be jarring. `_mood_override` is the scene mood that
        # track stands for, which also colours her face (see TRACK_MOOD).
        self._bgm_override = self._stored_track_override()
        self._mood_override = TRACK_MOOD.get(self._bgm_override.upper(), "") if self._bgm_override else ""
        # A background selection is a one-shot request. Recreate its request
        # after a restart so the scene pass still receives it, rather than only
        # redrawing an old frame in the browser.
        if self._bg_override:
            self._scene_request = self._scene_pick(self._bg_override)
            self._scene_notice_request = {"bg": self._bg_override}
        self._voice_source = None
        self._voice_clip = None
        # Per-turn audio, keyed by the hub id of the bubble it belongs to. A
        # reply is several bubbles and each is voiced separately, so a clip can
        # arrive after the next bubble is already published; the frame carries
        # this map and the stage plays the clip when it reaches that line.
        self._turn_audio = {}
        self._turn_clip = {}
        self._turn_match = {}
        self._last_clip_match = {}
        # lines he asked to hear again (the ♪ beside a line in the backlog).
        # The runtime polls `speak_requests`; the audio comes back the same way
        # a finished turn's does, so nothing new plays it.
        self._speak_queue = []
        # her reply as it is being written: the text so far, and whether the
        # stream is still open. Kept off the turn counter so the live update
        # does not replay the voice on every token.
        self._partial = None
        self._streaming = False
        # the SSE readers: a queue each, fed the whole state on every change
        self._subs = set()
        self._lock = threading.Lock()
        self._httpd = None
        self._server_thread = None
        self._state = self._restore_state() or self._standby_state()
        self._write_state()
        wiring.declare(self)

    # ---------------- setup helpers ----------------

    def _restore_state(self):
        """The last frame the stage drew, so a restart or a page reload shows
        her last line and the last scene instead of the standby.

        The state file already held it; boot overwrote it with `……` before the
        page could read it, so a reload lost her last message and the scene
        (2026-09-17). The counters continue from the restored frame, and the
        clips it had served are restored with it so a re-shown line still
        has its voice."""
        try:
            with open(self.state_path, "r", encoding="utf-8", errors="replace") as f:
                got = json.load(f)
        except (OSError, ValueError):
            return None
        if not isinstance(got, dict) or not str(got.get("text") or "").strip():
            return None
        # A stream cannot survive process restart. Keeping the old flag would
        # leave the page waiting for a model call that no longer exists and
        # would refuse every save until another reply arrived.
        got["streaming"] = False
        got["partial"] = None
        try:
            self._rev = int(got.get("turn") or 0)
            self._shown_id = int(got.get("turn_id") or 0)
            self._hub_next = max(self._hub_next, self._shown_id + 1)
        except (TypeError, ValueError):
            self._rev = 0
            self._shown_id = 0
        audio = got.get("audio_by_turn")
        resume = got.get("resume_view")
        if isinstance(resume, dict):
            try:
                self._rev = max(self._rev, *(int(x.get("turn") or 0) for x in resume.get("pending", [])))
                self._hub_next = max([self._shown_id, *(int(x.get("turn_id") or 0) for x in resume.get("pending", []))]) + 1
            except (TypeError, ValueError):
                pass
        if isinstance(audio, dict):
            # JSON keys come back as strings while a live attach uses ints; the
            # map must not hold both or `sorted()` in `_attach_audio` raises and
            # the line never gets its clip (2026-09-17 16:22)
            restored = {}
            for k, v in audio.items():
                if not v:
                    continue
                try:
                    restored[int(k)] = str(v)
                except (TypeError, ValueError):
                    continue
            self._turn_audio = restored
        if isinstance(resume, dict):
            for frame in resume.get("pending", []):
                for k, v in (frame.get("audio_by_turn") or {}).items():
                    try:
                        self._turn_audio[int(k)] = str(v)
                    except (TypeError, ValueError):
                        continue
        return got

    def _vn_cfg(self):
        raw = getattr(self.config, "raw", None)
        block = dict(DEFAULTS)
        if isinstance(raw, dict) and isinstance(raw.get("vn"), dict):
            block.update(raw["vn"])
        return block

    def _resolve(self, path):
        return path if os.path.isabs(path) else os.path.join(self.root, path)

    def _character_name(self):
        try:
            return str(self.config.character.name)
        except Exception:
            return "Momoka"

    def _character_full(self):
        try:
            return str(self.config.character.name_ja or self.config.character.name)
        except Exception:
            return self.name

    # ---------------- the state the view draws ----------------

    def _standby_state(self):
        res = self.expr.resolve(self.expr.default, costume=self._costume_override)
        return self._frame(res, "……", None)

    def _frame(self, res, text, audio_url):
        overlay = res.get("overlay")
        return {
            "character": self.name,
            "full": self.full,
            "updated": datetime.datetime.now().isoformat(timespec="seconds"),
            "turn": self._rev,
            "turn_id": self._shown_id,
            "speaker": self.full,
            "text": text,
            "partial": self._partial,
            "streaming": self._streaming,
            "mood": res["expression"],
            "c4": res["c4"],
            "costume": res.get("costume"),
            "sprite": {
                "tag": res["tag"],
                "base": self._sprite_url(res["base_tag"]),
                "diff": self._sprite_url(res["diff_tag"]) if res["diff_tag"] else None,
                "geometry": res.get("geometry"),
                "zoom": self._sprite_zoom(),
            },
            "face": self._face_url(res["face"]),
            "overlay": self._emotion_url(overlay) if overlay else None,
            "idle": self._idle_state(),
            "scene": self._scene_state(),
            "voice": {
                "auto": self._auto_voice,
                "source": self._voice_source,
                "clip": self._voice_clip,
                "mode": self._voice_mode,
            },
            "audio": audio_url,
            "audio_by_turn": dict(self._turn_audio),
            "audio_error": None,
            "user_text": self._user_text,
        }

    def _scene_state(self):
        """The staging `sim/scene.py` last decided, as the view draws it.

        Before a turn has run the `scene_provider` has nothing to give, and
        the stage would be the bare CSS gradient. The director's own default
        background is drawn then, so the stage has a place from boot; it is
        served only if the file is on disk, the same rule the staging pass
        keeps."""
        got = None
        try:
            if self.scene_provider:
                got = self.scene_provider()
        except Exception as e:
            logger.log(f"[vn] scene signal not read: {type(e).__name__}")
        if self._bg_override:
            got = {"place": "", "bg": self._bg_override, "camera": "static",
                   "transition": "cut", "mood": "neutral",
                   # a hand-picked background must not stop the music: the
                   # track rides along from the staging already showing
                   "bgm": str((got or {}).get("bgm") or "")}
        if not got:
            got = self._standby_scene()
        if not got:
            return None
        # A track picked by hand stands until he picks "director" again: it
        # overrides whatever the staging chose and takes the mood of its own
        # title, so the light and her face move with the music he set.
        if self._bgm_override:
            got = dict(got)
            got["bgm"] = self._bgm_override
            if self._mood_override:
                got["mood"] = self._mood_override
        bg = str(got.get("bg") or "")
        bgm = str(got.get("bgm") or "")
        sound = str(got.get("se") or "")
        sound_file = os.path.join(self.se_dir, sound + ".ogg") if sound else ""
        if not (sound_file and os.path.isfile(sound_file)):
            sound = ""
        snow = bool(got.get("snow"))
        snow_files = [f"ENV_SNOW{i}.png" for i in range(1, 5)]
        snow_urls = ([f"/asset/frame/{name}" for name in snow_files]
                     if snow and all(os.path.isfile(os.path.join(self.frame_dir, name)) for name in snow_files)
                     else [])
        return {
            "place": got.get("place", ""),
            "bg": bg,
            "url": f"/asset/bg/{bg.lower()}.png" if bg else None,
            "camera": got.get("camera", "static"),
            "transition": got.get("transition", "cut"),
            "mood": got.get("mood", "neutral"),
            "bgm": bgm or None,
            "bgm_url": f"/asset/bgm/{bgm.lower()}.ogg" if bgm else None,
            "bgm_loop": self._bgm_loop_points(bgm) if bgm else None,
            "snow": bool(snow_urls),
            "snow_urls": snow_urls,
            "se": sound or None,
            "se_url": f"/asset/se/{sound}.ogg" if sound else None,
            "cue_id": str(got.get("cue_id") or "") if sound else "",
        }

    def _bgm_on_disk(self, name):
        """The track's spelling, or '' when there is no music to play. Same rule
        as the backgrounds: nothing is emitted that the stage cannot load."""
        want = str(name or "").strip().lower()
        if not (want and self.bgm_dir):
            return ""
        try:
            for entry in os.listdir(self.bgm_dir):
                if entry.lower() == want + ".ogg":
                    return entry[:-4]
        except OSError:
            return ""
        return ""

    def _ogg_sample_rate(self, path):
        """The ogg's own sample rate from the Vorbis identification header.

        The `.sli` points are sample counts at the decoded PCM's rate, and the
        game's files are 48 kHz, not 44.1. Dividing by 44.1 put BGM03's loop end
        at 99.7 s in a 92.2 s file, so `currentTime >= from` never fired and the
        element looped the whole file -- the rough seam he could hear. Read the
        rate rather than assume it; 0 means unreadable."""
        try:
            with open(path, "rb") as f:
                head = f.read(8192)
        except OSError:
            return 0
        i = head.find(b"vorbis")
        if i < 0 or i + 15 > len(head):
            return 0
        rate = struct.unpack_from("<I", head, i + 11)[0]
        return rate if 8000 <= rate <= 192000 else 0

    def _bgm_loop_points(self, name):
        """The game's own loop points for a track, in seconds, or None.

        The `.sli` beside each ogg is a WaveLoopManager record --
        `Link { From=4397181; To=717183; Smooth=False; ... }` -- in samples at
        the ogg's own rate. Without them the stage loops the whole file, which
        snaps audibly on a track that has a lead-in; with them it jumps From ->
        To, and the seam is the one the game itself mastered. Here `From` is the
        loop end and `To` the loop start (From after To). Only a real pair is
        returned (both positive, From after To, From inside the file); anything
        else means no points and the element loops the file as before."""
        track = str(name or "").strip()
        if not (track and self.bgm_dir):
            return None
        ogg = os.path.join(self.bgm_dir, track + ".ogg")
        path = ogg + ".sli"
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError:
            return None
        m_from = re.search(r"From\s*=\s*(\d+)", text)
        m_to = re.search(r"To\s*=\s*(\d+)", text)
        if not (m_from and m_to):
            return None
        rate = self._ogg_sample_rate(ogg) or 44100.0
        try:
            frm = int(m_from.group(1)) / float(rate)
            to = int(m_to.group(1)) / float(rate)
        except ValueError:
            return None
        if not (frm > to >= 0):
            return None
        return {"from": round(frm, 3), "to": round(to, 3)}

    def _standby_scene(self):
        """The staging before the pass has decided one: the director's default
        background, if it is on disk. Nothing is invented and no character is
        named; the id is the corpus's own default."""
        bg = self._default_bg_id()
        if not (bg and self.bg_dir):
            return None
        path = os.path.join(self.bg_dir, bg.lower() + ".png")
        if not os.path.isfile(path):
            return None
        return {"place": "", "bg": bg, "camera": "static",
                "transition": "cut", "mood": "neutral",
                "bgm": self._bgm_on_disk(self.default_bgm)}

    def _default_bg_id(self):
        """`scene_director.default_bg`, the background the staging pass falls
        back to.

        Read from the merged config tree the same way `_stored_voice_mode` reads
        `tts`: the VN channel has its own section, but this default belongs to
        the staging pass and is not copied into `vn`, so it cannot drift."""
        raw = getattr(self.config, "raw", None)
        sd = raw.get("scene_director") if isinstance(raw, dict) else None
        return str((sd or {}).get("default_bg") or "")

    def _sprite_zoom(self):
        """How much the sprite is enlarged past the viewport height.

        The art is cut at her socks with no feet, so at 1.0 the cut sits on
        the viewport bottom behind the message window and she reads as
        footless. Enlarging and anchoring the top puts the cut below the
        visible area and frames her from the head to about the knee. Read
        from `vn.sprite_zoom`; a value at or below zero shows the whole
        figure."""
        c = self._vn_cfg()
        try:
            z = float(c.get("sprite_zoom", 1.55))
        except (TypeError, ValueError):
            return 1.55
        return z if z > 0 else 1.0

    def _sprite_url(self, tag):
        return f"/asset/sprite/{tag.lower()}.png"

    def _face_url(self, face_id):
        return f"/asset/face/{face_id.lower()}f.png"

    def _emotion_url(self, name):
        return f"/asset/emotion/{str(name).lower()}.png"

    def _idle_state(self):
        """The stage's idle motion defaults, for the page to read.

        `motion` is the breathing bob on her and the float on the emotion
        mark; `sway` is the optional lateral drift, off unless a character
        turns it on. The page can override either from its own toggle. This
        default is deliberate for the stage, so it beats
        `prefers-reduced-motion`; that machine setting only decides when the
        player has made no choice and no default is sent."""
        c = self._vn_cfg()
        return {
            "motion": bool(c.get("idle_motion", True)),
            "sway": bool(c.get("idle_sway", False)),
        }

    # ---------------- the stage's controls ----------------

    def _quality_default(self):
        """`quality.enabled`, the guard's own default, read from the merged
        config tree the way `_stored_voice_mode` reads `tts` and
        `_default_bg_id` reads `scene_director`."""
        raw = getattr(self.config, "raw", None)
        q = raw.get("quality") if isinstance(raw, dict) else None
        return bool(q.get("enabled", False)) if isinstance(q, dict) else False

    def _stored_control(self, key, default):
        """A stage toggle as the page last left it, else the config default.

        The page posts these on load, but a page already open across a restart
        does not, so the channel came back with the toggles at their defaults
        and her replies unvoiced until he noticed (2026-09-17 15:12). Written
        through the save, so a restart keeps them; nothing else about her is
        touched."""
        try:
            got = self.store.get(key, None) if self.store else None
        except Exception:
            got = None
        return default if got is None else bool(got)

    def _persist_control(self, key, value):
        """Keep a stage control on the save, as it is.

        It used to coerce every value to `bool`, which is right for the two
        toggles it was written for and wrong for the voice mode: `exact` was
        saved as `true`, and on the next boot `true` was not one of the three
        modes, so the mode fell back to the legacy `vn_clip_partial` and every
        choice he made in the menu was silently ignored (2026-09-17)."""
        try:
            if self.store:
                self.store.set(key, value)
        except Exception:
            pass

    def _stored_background_override(self):
        """The pending hand-picked background, when its asset still exists."""
        try:
            saved = str(self.store.get("vn_background_override", "") or "").strip().upper()
        except Exception:
            saved = ""
        if saved and (not self.bg_dir or not os.path.isfile(os.path.join(self.bg_dir, saved.lower() + ".png"))):
            logger.log(f"[vn] saved background is no longer on disk: {saved}")
            saved = ""
        if not saved:
            self._persist_control("vn_background_override", None)
        return saved or None

    def _stored_costume_override(self):
        """The saved costume, unless the current corpus no longer has it."""
        try:
            saved = str(self.store.get("vn_costume_override", "") or "").strip().upper()
        except Exception:
            saved = ""
        if saved and saved not in {cid.upper() for cid in self.expr.costume_ids()}:
            logger.log(f"[vn] saved outfit is no longer on disk: {saved}")
            saved = ""
        if not saved:
            self._persist_control("vn_costume_override", None)
        return saved or None

    def _stored_track_override(self):
        """The saved hand-picked track, unless its audio file disappeared."""
        try:
            saved = str(self.store.get("vn_track_override", "") or "").strip()
        except Exception:
            saved = ""
        saved = self._bgm_on_disk(saved) if saved else ""
        if not saved:
            self._persist_control("vn_track_override", None)
        return saved or None

    @staticmethod
    def _scene_pick(bg):
        return {"bg": bg, "place": "", "camera": "static",
                "transition": "cut", "mood": "neutral"}

    def voice_auto(self):
        """Whether the page asked for her replies to be spoken automatically."""
        return bool(self._auto_voice)

    def quality_on(self):
        """Whether the page asked for the draft guard to run."""
        return bool(self._quality_on)

    def take_scene_request(self):
        """The background the page picked, handed to the staging pass once."""
        with self._lock:
            req = self._scene_request
            self._scene_request = None
        return req

    def take_scene_notice_request(self):
        """The hand-picked place, handed to the runtime once for her reply."""
        with self._lock:
            req = self._scene_notice_request
            self._scene_notice_request = None
        return req

    def queue_director(self, proposal):
        """He approved the console's proposal. Held for the loop to apply."""
        with self._lock:
            # The approved scene is authoritative. A former manual background
            # or track must not survive a restart and cover the director's
            # background or music before its request reaches the loop.
            self._bg_override = None
            self._bgm_override = None
            self._mood_override = ""
            self._scene_request = None
            self._scene_notice_request = None
            self._director_request = dict(proposal or {})
        self._persist_control("vn_background_override", None)
        self._persist_control("vn_track_override", None)
        return True

    def take_director_request(self):
        """The approved proposal, handed to the runtime once."""
        with self._lock:
            req = self._director_request
            self._director_request = None
        return req

    def queue_director_clear(self):
        """He cleared the directed scene. Held for the loop to apply."""
        with self._lock:
            self._director_clear = True
        return True

    def take_director_clear(self):
        with self._lock:
            got = self._director_clear
            self._director_clear = False
        return got

    def _bg_ids(self):
        """The backgrounds on disk, as ids the page can offer."""
        if not self.bg_dir or not os.path.isdir(self.bg_dir):
            return []
        out = []
        for name in sorted(os.listdir(self.bg_dir)):
            stem, ext = os.path.splitext(name)
            if ext.lower() == ".png" and stem:
                out.append(stem.upper())
        return out

    def _bgm_ids(self):
        """The tracks on disk, with the corpus's own title when it has one, so
        the page can offer them by meaning rather than by id."""
        if not self.bgm_dir or not os.path.isdir(self.bgm_dir):
            return []
        try:
            from sim.scene import BGM_TITLES
        except Exception:
            BGM_TITLES = {}
        out = []
        for name in sorted(os.listdir(self.bgm_dir)):
            stem, ext = os.path.splitext(name)
            if ext.lower() != ".ogg" or not stem:
                continue
            key = stem.upper()
            out.append({"id": key, "title": str(BGM_TITLES.get(key) or "")})
        return out

    def control_state(self):
        return {"auto_voice": bool(self._auto_voice),
                "quality": bool(self._quality_on),
                "voice_mode": self._voice_mode}

    def voice_models(self):
        """The models the stage may offer for her words: the provider's own
        table, cut to what it can serve. Empty when the runtime has not wired
        the provider, so the picker simply has nothing to offer."""
        if not self.voice_model_provider:
            return {"model": "", "models": [], "pinned": False}
        try:
            got = self.voice_model_provider() or {}
        except Exception as e:
            logger.log(f"[vn] the model list not read: {type(e).__name__}: {e}")
            return {"model": "", "models": [], "pinned": False}
        return {"model": str(got.get("model") or ""),
                "models": [str(m) for m in (got.get("models") or [])],
                "pinned": bool(got.get("pinned"))}

    def set_voice_model(self, name):
        """The stage picked the model her words are written on. An empty pick
        is `auto`: hand it back to her config. The pin is written to her own
        save by the runtime, so it outlives the run. None means nothing is
        wired to take the choice."""
        if not self.voice_model_setter:
            return None
        want = str(name or "").strip()
        try:
            msg = self.voice_model_setter(want or "auto")
        except Exception as e:
            logger.log(f"[vn] the model pick failed: {type(e).__name__}: {e}")
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}
        report = self.voice_models()
        return {"ok": True, "message": str(msg or ""),
                "model": report.get("model"), "pinned": report.get("pinned")}

    def stage_model(self):
        """The model the STAGE roles are on, for the second picker: every role
        that is not one of her voice roles. Empty when the runtime has not
        wired the provider."""
        if not self.stage_model_provider:
            return {"model": "", "models": []}
        try:
            got = self.stage_model_provider() or {}
        except Exception as e:
            logger.log(f"[vn] the stage model list not read: {type(e).__name__}: {e}")
            return {"model": "", "models": []}
        return {"model": str(got.get("model") or ""),
                "models": [str(m) for m in (got.get("models") or [])]}

    def set_stage_model(self, name):
        """The stage pinned its roles to one model, or gave them back their
        config entries on an empty pick. Her voice roles are untouched. None
        means nothing is wired."""
        if not self.stage_model_setter:
            return None
        try:
            got = self.stage_model_setter(str(name or "").strip())
        except Exception as e:
            logger.log(f"[vn] the stage model not set: {type(e).__name__}: {e}")
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}
        if isinstance(got, dict):
            return got
        return {"ok": True, "message": str(got or "")}

    def recent_log(self, n=80):
        """The conversation so far, oldest first, for the stage's backlog.

        Both sides: his messages and hers, with the clock reading the record
        already carries. The page shows it behind the input so what he wrote is
        still readable after he has sent it -- the frame carries only the
        newest turn."""
        if self.store is None:
            return []
        try:
            rows = self.store.recent_messages(int(n))
        except Exception as e:
            logger.log(f"[vn] the backlog not read: {type(e).__name__}: {e}")
            return []
        out = []
        frames = self.store.vn_message_frames([r.get("id") for r in rows
                                               if r.get("role") == "assistant"])
        checkpoints = self.store.vn_line_checkpoints([r.get("id") for r in rows
                                                       if r.get("role") == "assistant"])
        with self._lock:
            live_frame = dict(self._state or {})
        for r in rows:
            text = str(r.get("text", "") or "").strip()
            if not text:
                continue
            recorded = frames.get(int(r.get("id") or 0)) if str(r.get("role")) == "assistant" else None
            inferred = None
            if str(r.get("role")) == "assistant" and recorded is None:
                inferred = self._legacy_replay_frame(r, live_frame)
            row = {
                "role": "him" if str(r.get("role")) == "user" else "her",
                "text": text[:1000],
                "ts": r.get("ts"),
                # the row's own id, so the  beside a line can name it back
                "id": r.get("id"),
                "stage": recorded or inferred,
                "stage_source": "recorded" if recorded else ("inferred" if inferred else None),
                "checkpoint": (checkpoints.get(int(r.get("id") or 0))
                               if str(r.get("role")) == "assistant" else None),
            }
            # A recorded line the ♪ would play from tape rather than synthesise:
            # the backlog says which real line it is and how close the match
            # was, so what he will hear is not left to the ear (2026-09-17).
            if row["role"] == "her" and self.voice_index is not None:
                try:
                    hit = self.voice_index.lookup_detail(
                        text, mode=self._voice_mode)
                except Exception as e:
                    logger.log(f"[vn] backlog match not read: {type(e).__name__}")
                    hit = None
                if hit:
                    row["match"] = {"clip": hit[0], "matched": hit[1],
                                    "ratio": hit[2], "tier": hit[3]}
            out.append(row)
        return out

    def gauge_history(self, limit=500):
        """State log entries for the chart, newest first in storage, oldest
        first in the returned list -- so the chart can draw it left to right
        without having to reverse it itself."""
        if not self.store:
            return []
        try:
            with self.store.lock:
                rows = self.store.conn.execute(
                    "SELECT ts, date, gauges FROM state_log ORDER BY ts DESC LIMIT ?",
                    (int(limit),)).fetchall()
            out = []
            for r in reversed(rows):
                g = r["gauges"]
                if isinstance(g, str):
                    g = json.loads(g)
                out.append({"ts": r["ts"], "date": r["date"], "gauges": g})
            return out
        except Exception as e:
            logger.log(f"[vn] gauge history not read: {type(e).__name__}: {e}")
            return []

    def _legacy_replay_frame(self, row, live_frame):
        """Give a pre-archive line a visible face without claiming its old cue.

        Older messages did not save their director pose. The resolver can infer
        a face from the words in the current outfit, but the original choice
        cannot be recovered from text alone.
        """
        if not live_frame.get("sprite"):
            return None
        text = str(row.get("text") or "")
        try:
            res = self.expr.resolve({"text": text}, costume=live_frame.get("costume"))
        except Exception:
            return None
        frame = dict(live_frame)
        frame.update({
            "turn": -int(row.get("id") or 0), "turn_id": 0,
            "speaker": self.full, "text": text,
            "mood": res["expression"], "c4": res["c4"],
            "costume": res.get("costume"),
            "sprite": {"tag": res["tag"], "base": self._sprite_url(res["base_tag"]),
                       "diff": self._sprite_url(res["diff_tag"]) if res["diff_tag"] else None,
                       "geometry": res.get("geometry"), "zoom": self._sprite_zoom()},
            "face": self._face_url(res["face"]),
            "overlay": None, "audio": None, "audio_by_turn": {},
            "voice": {"auto": False},
        })
        return frame

    def checkpoint_line(self, hub_id, store_id):
        """Capture context after this bubble entered the record and outbox moved."""
        from tools.vn_saves import create_line_checkpoint
        if not (self.store and hub_id and store_id):
            return None
        frame = self.store.vn_frames([hub_id]).get(int(hub_id))
        if not frame:
            return None
        try:
            self.store.set_vn_message_frame(store_id, frame)
            db = self._resolve(self.config.logging.db_path)
            meta = create_line_checkpoint(db, self.checkpoints_dir, frame, store_id)
            self.store.set_vn_line_checkpoint(store_id, meta["id"])
            return meta["id"]
        except Exception as e:
            logger.log(f"[vn] line checkpoint failed: {type(e).__name__}: {e}")
            return None

    def reply_candidates(self, hub_id):
        if self.store is None:
            return None
        row = self.store.message_by_tg_id(int(hub_id))
        if not row or row.get("role") != "assistant":
            return None
        prompt = self.store.reply_prompt_for(row["id"])
        if not prompt:
            return None
        anchor = int(prompt["msg_id"])
        return {"turn_id": int(hub_id), "anchor": anchor,
                "sat": int(prompt.get("sat") or 0),
                "candidates": [{"n": int(c["n"]), "text": c["text"],
                                "model": c["model"]}
                               for c in self.store.swipes_for(anchor)]}

    def set_control(self, payload):
        """A control the page toggled. Returns the controls as they now are."""
        with self._lock:
            if "auto_voice" in payload:
                self._auto_voice = bool(payload["auto_voice"])
                self._persist_control("vn_auto_voice", self._auto_voice)
            if "quality" in payload:
                self._quality_on = bool(payload["quality"])
                self._persist_control("vn_quality", self._quality_on)
            if "voice_mode" in payload:
                want = str(payload["voice_mode"])
                if want in VOICE_MODES:
                    self._voice_mode = want
                    self._persist_control("vn_voice_mode", want)
                else:
                    logger.log(f"[vn] voice mode refused: {want[:20]}")
            state = {"auto_voice": self._auto_voice, "quality": self._quality_on,
                     "voice_mode": self._voice_mode}
            # the frame carries these switches, so it is rewritten here; the
            # turn counter is left alone so a toggle never replays her voice
            if self._state is not None:
                self._state["voice"] = {
                    "auto": self._auto_voice,
                    "source": self._voice_source,
                    "clip": self._voice_clip,
                    "mode": self._voice_mode,
                }
                self._state["updated"] = datetime.datetime.now().isoformat(timespec="seconds")
                snapshot = dict(self._state)
            else:
                snapshot = None
        if snapshot is not None:
            self._write_state()
            self._notify(snapshot)
        logger.log(f"[vn] controls: voice auto={state['auto_voice']} quality={state['quality']}")
        return state

    def set_scene(self, bg, directed=False):
        """Draw a background now; queue a place notice only for a hand pick."""
        bg = str(bg or "").strip().upper()
        if not bg:
            return None
        if self.bg_dir and not os.path.isfile(os.path.join(self.bg_dir, bg.lower() + ".png")):
            logger.log(f"[vn] scene pick not on disk: {bg}")
            return None
        with self._lock:
            self._bg_override = bg
            if not directed:
                self._scene_request = self._scene_pick(bg)
                self._scene_notice_request = {"bg": bg}
            # the turn counter is left alone: the background belongs to the
            # stage, and the view draws it from every frame. Bumping the turn
            # queued the same line again as a pending bubble (2026-09-17).
            self._state["scene"] = self._scene_state()
            self._state["updated"] = datetime.datetime.now().isoformat(timespec="seconds")
            state = dict(self._state)
        if not directed:
            self._persist_control("vn_background_override", bg)
        self._write_state()
        if self.store is not None and state.get("turn_id"):
            self.store.set_vn_frame(state["turn_id"], state)
        self._notify(state)
        logger.log(f"[vn] scene set {'by director' if directed else 'by hand'}: {bg}")
        return bg

    def set_track(self, bgm):
        """The page picked a track: play it now and keep it until 'director'.

        Unlike a background this is held, not one turn only -- music flipping
        back mid-scene would be jarring. An empty pick hands the choice back to
        the staging pass. The track's own mood rides along, so a track chosen by
        hand colours the light and her face (`TRACK_MOOD`)."""
        want = str(bgm or "").strip()
        if want:
            on_disk = self._bgm_on_disk(want)
            if not on_disk:
                logger.log(f"[vn] track pick not on disk: {want}")
                return None
            want = on_disk
        with self._lock:
            self._bgm_override = want or None
            self._mood_override = TRACK_MOOD.get(want.upper(), "") if want else ""
            if self._state is not None:
                self._state["scene"] = self._scene_state()
        self._persist_control("vn_track_override", want or None)
        # redraw the face for the new mood -- or back to her own words -- and
        # publish, so the pick is visible at once rather than on the next turn
        self._set_face({})
        logger.log(f"[vn] track set by hand: {want or 'director'}")
        return want or ""

    def set_costume(self, costume, redraw=True):
        """The outfit the stage manager set, or '' to return to her default.

        The corpus's costume id (`CD01`..`CD07`, `channels/vn_expression.py`).
        Applied to the frame already showing, like a track picked by hand: the
        sprite base and face are re-resolved in the new costume, so the outfit
        changes at once rather than on the next turn. An id not on disk is
        refused, so a bad name cannot leave her undressed."""
        want = str(costume or "").strip().upper()
        if want and want not in {c.upper() for c in self.expr.costume_ids()}:
            logger.log(f"[vn] costume pick not on disk: {costume!r}")
            return None
        with self._lock:
            self._costume_override = want or None
        self._persist_control("vn_costume_override", want or None)
        # keep the expression she is wearing and redraw it in the new costume
        mood = (self._state or {}).get("mood") or self.expr.default
        if redraw:
            self._set_face({"expression": mood})
        logger.log(f"[vn] outfit set by hand: {want or 'default'}")
        return want

    def _costume_ids(self):
        """The outfits on disk, as ids the page can offer, with what each is."""
        try:
            from sim.scene import COSTUME_NOTES
            notes = dict(COSTUME_NOTES)
        except Exception:
            notes = {}
        try:
            own = getattr(self.config.scene_director, "costumes", None)
            if isinstance(own, dict):
                notes.update({str(k): str(v) for k, v in own.items()})
        except Exception:
            pass
        return [{"id": cid, "what": notes.get(cid) or ""} for cid in self.expr.costume_ids()]

    def set_outfit(self, costume):
        """The page picked an outfit by hand: her sprite changes at once and the
        runtime is asked to let her notice it. Returns the id, or None when the
        id is not on disk."""
        got = self.set_costume(costume)
        if got is None:
            return None
        with self._lock:
            self._outfit_request = {"costume": got}
        return got

    def take_outfit_request(self):
        """The outfit he picked by hand, handed to the runtime once."""
        with self._lock:
            got = self._outfit_request
            self._outfit_request = None
        return got

    def _signal_for(self, text):
        """The feeling as a signal the resolver understands.

        The 28-label read from `sim/emotion.py` first, because it is finer and
        it is what carries the overlay; the mood-band reaction next, which is
        what the app's own header picture is cut from; and the words last, so a
        refused model still moves the face."""
        with self._lock:
            prepared = self._prepared_emotions.pop(text, "")
        if prepared:
            return {"label": prepared, "text": text}
        try:
            if self.emotion_provider:
                label = self.emotion_provider(text)
                if label:
                    return {"label": label, "text": text}
        except Exception as e:
            logger.log(f"[vn] emotion signal not read: {type(e).__name__}")
        try:
            if self.reaction_provider:
                got = self.reaction_provider() or {}
                if got.get("bucket"):
                    return {"bucket": got["bucket"], "text": text}
        except Exception as e:
            logger.log(f"[vn] reaction signal not read: {type(e).__name__}")
        return {"text": text}

    def prepare_emotion(self, text, label):
        """Keep the voice worker's label for the face of the same bubble."""
        if text and label:
            with self._lock:
                self._prepared_emotions[str(text)] = str(label)

    def take_vocal_cue(self):
        """Hand a scene director's sound tag to one reply once."""
        try:
            scene = self.scene_provider() if self.scene_provider else None
        except Exception:
            return ""
        if not isinstance(scene, dict):
            return ""
        tag = str(scene.get("interjection") or "")
        cue_id = str(scene.get("vocal_cue_id") or "")
        if not (tag and cue_id):
            return ""
        with self._lock:
            if cue_id == self._used_vocal_cue:
                return ""
            self._used_vocal_cue = cue_id
        self._persist_control("vn_used_vocal_cue", cue_id)
        return tag

    # ---------------- the SSE readers ----------------

    def subscribe(self):
        """A queue the /events handler reads: the whole state on every change."""
        q = queue.Queue(maxsize=32)
        with self._lock:
            self._subs.add(q)
        return q

    def unsubscribe(self, q):
        with self._lock:
            self._subs.discard(q)

    def _notify(self, state):
        with self._lock:
            subs = list(self._subs)
        for q in subs:
            try:
                q.put_nowait(state)
            except queue.Full:
                pass

    def _face_signal(self, signal):
        """The signal the face is drawn from. A track picked by hand names a
        mood and that mood's face wins while it stands; otherwise her own words
        decide."""
        if self._mood_override:
            face = TRACK_MOOD_EXPRESSION.get(self._mood_override)
            if face:
                return {"expression": face}
        return signal

    def _opening_face_signal(self, signal):
        """Use the director's exact native pair once on a new scene or beat.

        Each later bubble still follows its own emotion reader. The cue id is
        persisted, so a restart or an edited old bubble cannot replay it.
        """
        own = self._face_signal(signal)
        try:
            scene = self.scene_provider() if self.scene_provider else None
        except Exception:
            scene = None
        if not isinstance(scene, dict):
            return own
        cue = str(scene.get("face_cue_id") or "")
        index = str(scene.get("face_index") or "")
        if not (cue and index and cue != self._used_face_cue):
            return own
        self._used_face_cue = cue
        self._persist_control("vn_used_face_cue", cue)
        # A hand-picked track owns the face while it stands. Consume the
        # opening cue anyway so it cannot appear late when the track is reset.
        if self._mood_override:
            return own
        return {**(own if isinstance(own, dict) else {"expression": own}), "face_index": index}

    def _publish(self, text, signal, hub_id):
        with self._lock:
            self._rev += 1
            res = self.expr.resolve(self._opening_face_signal(signal), costume=self._costume_override)
            self._audio_url = None
            # a new turn stages its own scene, so a background picked by hand
            # stops overriding it; the voice badge belongs to the audio that
            # just played and goes with it
            self._bg_override = None
            self._persist_control("vn_background_override", None)
            self._voice_source = None
            self._voice_clip = None
            self._shown_id = hub_id
            self._partial = None
            self._streaming = False
            self._state = self._frame(res, text, None)
            state = dict(self._state)
        self._write_state()
        if self.store is not None and state.get("turn_id"):
            self.store.set_vn_frame(state["turn_id"], state)
        self._notify(state)

    def _set_face(self, signal):
        """Move the face, mood, sprite and overlay on the line already showing.

        This is a reaction or a track picked by hand, not a new bubble, so the
        turn counter is left alone: bumping it made the view queue the same line
        again and the new track (or face) waited for a click that also showed a
        line he had already read (2026-09-17). The stage redraws what moved from
        the frame itself."""
        with self._lock:
            if not self._state:
                return
            res = self.expr.resolve(self._face_signal(signal), costume=self._costume_override)
            self._state["mood"] = res["expression"]
            self._state["c4"] = res["c4"]
            self._state["costume"] = res.get("costume")
            self._state["sprite"] = {
                "tag": res["tag"],
                "base": self._sprite_url(res["base_tag"]),
                "diff": self._sprite_url(res["diff_tag"]) if res["diff_tag"] else None,
                "geometry": res.get("geometry"),
                "zoom": self._sprite_zoom(),
            }
            self._state["face"] = self._face_url(res["face"])
            self._state["overlay"] = self._emotion_url(res["overlay"]) if res.get("overlay") else None
            self._state["updated"] = datetime.datetime.now().isoformat(timespec="seconds")
            state = dict(self._state)
        self._write_state()
        if self.store is not None and state.get("turn_id"):
            self.store.set_vn_frame(state["turn_id"], state)
        self._notify(state)

    def handle_touch(self, region):
        """A click on her sprite, from `/touch`. Region is one of
        `TOUCH_REACTIONS`; anything else (or a click inside the cooldown) is a
        no-op the browser just skips the sound for. Routed through `_set_face`
        rather than poking `self._state` directly, so the overlay lookup and
        the file-exists checks it already does are not duplicated here."""
        region = str(region or "").strip().lower()
        reaction = self.TOUCH_REACTIONS.get(region)
        if not reaction:
            return {"ok": False}
        now = time.time()
        if now - (self._last_touch_ts or 0) < self.TOUCH_COOLDOWN:
            return {"ok": False, "cooldown": True}
        self._last_touch_ts = now
        self._set_face(dict(reaction["signal"]))
        if self.store is not None:
            try:
                text = self.TOUCH_EVENT_TEXT.get(region, "he touched me somewhere forward")
                self.store.add_event(time.time(), self.clock.date_str(), "touch", text, 1)
            except Exception:
                pass
        deltas = self.TOUCH_GAUGE_DELTAS.get(region, {})
        if deltas and self.gauge_nudge:
            try:
                self.gauge_nudge(deltas, f"touch:{region}")
            except Exception:
                pass
        sound_name = reaction.get("sound") or ""
        sound_url = ""
        if sound_name:
            sound_file = os.path.join(self.se_dir or "", sound_name + ".ogg")
            if os.path.isfile(sound_file):
                sound_url = "/asset/se/" + sound_name + ".ogg"
        voice_url = ""
        clips = reaction.get("clips") or []
        if clips:
            pick = random.choice(clips)
            clip_file = os.path.join(self.clip_dir or "", pick + ".ogg")
            if os.path.isfile(clip_file):
                voice_url = "/asset/clip/" + pick + ".ogg"
        return {"ok": True, "region": region, "sound": sound_url, "voice": voice_url}

    def stream_delta(self, text):
        """Her reply as it is written, from the model's stream (`llm.py`).

        Kept off the turn counter and off disk: the live reader gets it over
        SSE, and the finished turn is published as usual when the call
        returns. A reader on the polling fallback sees the finished turn only,
        which is the honest limit of that path."""
        with self._lock:
            if not self._state:
                return
            self._partial = str(text or "")
            self._streaming = True
            self._state["partial"] = self._partial
            self._state["streaming"] = True
            state = dict(self._state)
        self._notify(state)

    def _attach_audio(self, url, attach_to=0):
        with self._lock:
            self._audio_url = url
            target = int(attach_to or 0)
            shown = int(self._shown_id or 0)
            if target:
                self._turn_audio[target] = url
                self._turn_clip[target] = self._voice_clip
                self._turn_match[target] = dict(self._last_clip_match or {})
                # keep the map small: only the turns the stage can still be
                # advancing through. Drop by insertion order, not by a string
                # sort of the keys: a three-digit turn (100) sorts before a
                # two-digit one (26) as text, so the sort dropped the newest
                # clip the moment it was attached (2026-09-17).
                if len(self._turn_audio) > 24:
                    for old in list(self._turn_audio)[:-24]:
                        self._turn_audio.pop(old, None)
                        self._turn_clip.pop(old, None)
                        self._turn_match.pop(old, None)
            if not self._state:
                return
            # A clip is attached to the line it belongs to and does NOT make a
            # new turn: a turn per clip made the stage show the same bubble
            # twice, because the audio arrives after the next bubble was
            # published. The frame carries the map instead, and the stage plays
            # the clip when it reaches that line.
            if not target or target == shown:
                self._state["audio"] = url
            # the audio arrives after the turn was published, so the source
            # badge is written here as well -- otherwise the frame still says
            # nothing about where this line came from
            self._state["voice"] = {
                "auto": self._auto_voice,
                "source": self._voice_source,
                "clip": self._voice_clip,
                "mode": self._voice_mode,
                # what the clip actually says, when it is a recorded line: the
                # stage says which real match it is playing
                "match": (self._turn_match.get(target) if target
                          else dict(self._last_clip_match or {})) or None,
            }
            self._state["turn_id"] = shown
            self._state["audio_by_turn"] = dict(self._turn_audio)
            self._state["updated"] = datetime.datetime.now().isoformat(timespec="seconds")
            state = dict(self._state)
        self._write_state()
        if self.store is not None and target:
            old = self.store.vn_frames([target]).get(target)
            if old:
                old["audio"] = url
                old["audio_by_turn"] = {str(target): url}
                old["voice"] = dict(state.get("voice") or {})
                self.store.set_vn_frame(target, old)
        self._notify(state)

    def _write_state(self):
        try:
            os.makedirs(self.out_dir, exist_ok=True)
            tmp = self.state_path + ".tmp"
            with self._lock:
                blob = json.dumps(self._state, ensure_ascii=False, indent=1)
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(blob)
            os.replace(tmp, self.state_path)
        except Exception as e:
            logger.log(f"[vn] state not written: {type(e).__name__}")

    def current_state(self):
        with self._lock:
            state = dict(self._state) if self._state else None
        if state is not None:
            try:
                state["reply_busy"] = bool(self.save_busy_provider()) if callable(self.save_busy_provider) else False
            except Exception:
                state["reply_busy"] = True
        return state

    def branch_pending(self):
        with self._lock:
            return bool(self._state and self._state.get("branch_from"))

    def continue_branch(self, hub_id):
        """Keep the original reply and release the restored simulation."""
        with self._lock:
            if not self._state or int(self._state.get("branch_from") or 0) != int(hub_id):
                raise ValueError("no restored reply is waiting")
            self._state.pop("branch_from", None)
            self._state.pop("resume_view", None)
            state = dict(self._state)
        self._write_state()
        self._notify(state)
        return {"continued": True}

    def load_status(self):
        try:
            with open(self.load_status_path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {"phase": "idle"}

    def request_load(self, slot_id, *, line=False):
        """Start the operator's offline restarter after returning this request."""
        from tools.vn_saves import validate_slot

        if (self.current_state() or {}).get("streaming") or self._inbox.qsize() or (callable(self.save_busy_provider) and self.save_busy_provider()):
            raise ValueError("wait for the current reply to finish")
        slot_id = str(slot_id or "")
        if not slot_id or os.path.basename(slot_id) != slot_id or slot_id.startswith("."):
            raise ValueError("invalid slot id")
        slots_dir = self.checkpoints_dir if line else self.saves_dir
        validate_slot(os.path.join(slots_dir, slot_id))
        with self._lock:
            if self._load_requested and self.load_status().get("phase") == "error":
                self._load_requested = False
            if self._load_requested:
                raise ValueError("a load is already in progress")
            self._load_requested = True
        request_id = uuid.uuid4().hex
        db = self._resolve(self.config.logging.db_path)
        args = [sys.executable, "-m", "tools.vn_load", "--slot", slot_id,
                "--db", db, "--state", self.state_path,
                "--saves", slots_dir, "--status", self.load_status_path,
                "--request-id", request_id]
        try:
            os.makedirs(self.saves_dir, exist_ok=True)
            status_tmp = self.load_status_path + ".tmp"
            with open(status_tmp, "w", encoding="utf-8") as f:
                json.dump({"request_id": request_id, "slot": slot_id,
                           "phase": "checking"}, f)
            os.replace(status_tmp, self.load_status_path)
            with open(os.path.join(self.saves_dir, "load-launch.log"), "a", encoding="utf-8") as log:
                subprocess.Popen(args, cwd=self.root, stdin=subprocess.DEVNULL,
                                 stdout=log, stderr=subprocess.STDOUT,
                                 creationflags=(getattr(subprocess, "DETACHED_PROCESS", 0)
                                                | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)),
                                 close_fds=True)
        except Exception:
            with self._lock:
                self._load_requested = False
            try:
                with open(self.load_status_path, "w", encoding="utf-8") as f:
                    json.dump({"request_id": request_id, "phase": "error",
                               "error": "could not start load helper"}, f)
            except OSError:
                pass
            raise
        return {"request_id": request_id, "slot": slot_id, "phase": "checking"}

    # ---------------- the channel surface ----------------

    def verify_connection(self):
        """Start the view server. Nothing is contacted outbound, so a refused
        model never stops the stage: the server is the only thing boot needs."""
        if self._httpd is not None:
            return True
        try:
            self._start_server()
            clips = self.voice_index.size()
            said = f"{clips} recorded line(s)" if clips else "no clip index"
            logger.log(f"[vn] view at http://{self.host}:{self.port}/ "
                       f"({len(self.expr.faces)} expressions verified, {said})")
            return True
        except Exception as e:
            logger.log(f"[vn] view server did not start: {type(e).__name__}: {e}")
            # the runtime loop must still come up; the stage is what is missing
            return True

    def _start_server(self):
        channel = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, fmt, *args):
                sys.stderr.write("  [vn] %s\n" % (fmt % args))

            def _send(self, code, body, ctype="application/json; charset=utf-8"):
                if isinstance(body, (dict, list)):
                    body = json.dumps(body, ensure_ascii=False).encode("utf-8")
                elif isinstance(body, str):
                    body = body.encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def _send_file(self, path):
                if not path or not os.path.isfile(path):
                    return self._send(404, {"error": "not found", "path": path})
                ctype = CONTENT_TYPES.get(os.path.splitext(path)[1].lower(),
                                          "application/octet-stream")
                with open(path, "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def _chunk(self, text):
                """One SSE event, chunked so an HTTP/1.1 reader can stream it."""
                body = ("data: " + text + "\n\n").encode("utf-8")
                self.wfile.write(("%x\r\n" % len(body)).encode("ascii"))
                self.wfile.write(body + b"\r\n")
                self.wfile.flush()

            def _events(self):
                """Server-sent events: the whole state on every change.

                The token stream is the live edge; a reader that cannot hold
                this open falls back to the poll the view always runs."""
                q = channel.subscribe()
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                try:
                    self._chunk(json.dumps(channel.current_state() or {"turn": 0}, ensure_ascii=False))
                    while True:
                        try:
                            state = q.get(timeout=15)
                            self._chunk(json.dumps(state, ensure_ascii=False))
                        except queue.Empty:
                            self._chunk(json.dumps({"ping": True}))   # a kept-alive comment
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass
                finally:
                    channel.unsubscribe(q)

            def do_GET(self):
                route = unquote(urlparse(self.path).path)
                if route in ("/", "/index.html"):
                    channel._touch()
                    return self._send_file(os.path.join(channel.view_dir, "index.html"))
                if route == "/state.json":
                    return self._send(200, channel.current_state() or {"turn": 0})
                if route == "/saves":
                    from tools.vn_saves import list_slots, quick_slot
                    return self._send(200, {"saves": list_slots(channel.saves_dir),
                                            "quick": quick_slot(channel.saves_dir)})
                if route == "/saves/load-status":
                    return self._send(200, channel.load_status())
                if route.startswith("/replies/"):
                    try:
                        turn_id = int(route[len("/replies/"):])
                        got = channel.reply_candidates(turn_id)
                    except (ValueError, TypeError):
                        got = None
                    return self._send(200 if got else 404, got or {"error": "reply not found"})
                if route == "/scenes":
                    return self._send(200, {"backgrounds": channel._bg_ids()})
                if route == "/tracks":
                    return self._send(200, {"tracks": channel._bgm_ids()})
                if route == "/outfits":
                    return self._send(200, {"outfits": channel._costume_ids()})
                if route == "/models":
                    return self._send(200, channel.voice_models())
                if route == "/model-stage":
                    return self._send(200, channel.stage_model())
                if route == "/control":
                    return self._send(200, channel.control_state())
                if route == "/log":
                    return self._send(200, {"messages": channel.recent_log()})
                if route == "/gauge_history":
                    return self._send(200, channel.gauge_history())
                if route == "/director":
                    # the director-button console: the chat so far and what the
                    # console is told (the current scene and the catalogs)
                    channel._touch()
                    hist = channel.stage_history() if callable(channel.stage_history) else []
                    stat = channel.stage_snapshot() if callable(channel.stage_snapshot) else {}
                    return self._send(200, {"status": stat or {}, "history": hist or []})
                if route == "/events":
                    channel._touch()
                    return self._events()
                if route.startswith("/view/"):
                    name = os.path.basename(route[len("/view/"):])
                    return self._send_file(os.path.join(channel.view_dir, name))
                if route.startswith("/asset/sprite/"):
                    name = os.path.basename(route[len("/asset/sprite/"):])
                    return self._send_file(os.path.join(channel.expr.sprite_dir, name))
                if route.startswith("/asset/face/"):
                    name = os.path.basename(route[len("/asset/face/"):])
                    return self._send_file(os.path.join(channel.expr.face_dir, name))
                if route.startswith("/asset/bg/"):
                    name = os.path.basename(route[len("/asset/bg/"):])
                    return self._send_file(os.path.join(channel.bg_dir or "", name))
                if route.startswith("/asset/emotion/"):
                    name = os.path.basename(route[len("/asset/emotion/"):])
                    return self._send_file(os.path.join(channel.emotion_dir or "", name))
                if route.startswith("/asset/bgm/"):
                    name = os.path.basename(route[len("/asset/bgm/"):])
                    return self._send_file(os.path.join(channel.bgm_dir or "", name))
                if route.startswith("/asset/se/"):
                    name = os.path.basename(route[len("/asset/se/"):])
                    return self._send_file(os.path.join(channel.se_dir or "", name))
                if route.startswith("/asset/frame/"):
                    name = os.path.basename(route[len("/asset/frame/"):])
                    return self._send_file(os.path.join(channel.frame_dir or "", name))
                if route.startswith("/asset/clip/"):
                    # a recorded koikano line, served in place from the corpus;
                    # the same file the prototype's route named
                    name = os.path.basename(route[len("/asset/clip/"):])
                    return self._send_file(os.path.join(channel.clip_dir or "", name))
                if route.startswith("/audio/"):
                    name = os.path.basename(route[len("/audio/"):])
                    return self._send_file(os.path.join(channel.voice_dir, name))
                return self._send(404, {"error": "not found", "route": route})

            def do_POST(self):
                route = unquote(urlparse(self.path).path)
                if route not in ("/say", "/control", "/scene", "/track", "/outfit", "/model", "/model-stage", "/speak", "/director", "/director/approve", "/director/clear", "/saves", "/saves/load", "/replay/branch", "/replies/draw", "/replies/sit", "/replies/continue", "/touch"):
                    return self._send(404, {"error": "not found", "route": route})
                channel._touch()
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length).decode("utf-8", "replace") if length else ""
                try:
                    payload = json.loads(raw) if raw.strip() else {}
                except ValueError:
                    return self._send(400, {"error": "body is not JSON"})
                if not isinstance(payload, dict):
                    return self._send(400, {"error": "body is not an object"})
                if route == "/saves/load":
                    try:
                        return self._send(202, channel.request_load(payload.get("slot")))
                    except (ValueError, OSError, RuntimeError) as e:
                        return self._send(400, {"error": str(e)})
                if route == "/replay/branch":
                    try:
                        return self._send(202, channel.request_load(payload.get("checkpoint"), line=True))
                    except (ValueError, OSError, RuntimeError) as e:
                        return self._send(400, {"error": str(e)})
                if route == "/replies/continue":
                    try:
                        return self._send(200, channel.continue_branch(payload.get("turn_id")))
                    except (ValueError, TypeError) as e:
                        return self._send(400, {"error": str(e)})
                if route in ("/replies/draw", "/replies/sit"):
                    try:
                        turn_id = int(payload.get("turn_id") or 0)
                        if not channel.reply_candidates(turn_id):
                            raise ValueError("reply has no frozen prompt")
                        if callable(channel.save_busy_provider) and channel.save_busy_provider():
                            raise ValueError("wait for the current reply to finish")
                        if route == "/replies/draw":
                            if not callable(channel.reply_draw_provider):
                                raise ValueError("reply drawing is unavailable")
                            result = channel.reply_draw_provider(turn_id)
                        else:
                            if not callable(channel.reply_sit_provider):
                                raise ValueError("reply selection is unavailable")
                            result = channel.reply_sit_provider(turn_id, int(payload.get("n")))
                        return self._send(200, {"message": result,
                                                "reply": channel.reply_candidates(turn_id)})
                    except (ValueError, TypeError, RuntimeError) as e:
                        return self._send(400, {"error": str(e)})
                if route == "/saves":
                    from tools.vn_saves import create_slot, set_quick_slot
                    current = channel.current_state() or {}
                    if current.get("streaming") or channel._inbox.qsize() or (callable(channel.save_busy_provider) and channel.save_busy_provider()):
                        return self._send(409, {"error": "wait for the current reply to finish"})
                    try:
                        db = channel._resolve(channel.config.logging.db_path)
                        stage = payload.get("stage")
                        if len(raw) > 2_000_000:
                            raise ValueError("stage snapshot is too large")
                        saved = create_slot(db, channel.saves_dir, stage,
                                            latest_turn=int(current.get("turn") or 0))
                        if payload.get("quick") is True:
                            set_quick_slot(channel.saves_dir, saved["id"])
                    except (ValueError, OSError, RuntimeError) as e:
                        return self._send(400, {"error": str(e)})
                    return self._send(200, {"save": saved})
                if route == "/control":
                    return self._send(200, channel.set_control(payload))
                if route == "/scene":
                    bg = channel.set_scene(payload.get("bg"))
                    if not bg:
                        return self._send(400, {"error": "no such background",
                                                "bg": payload.get("bg")})
                    return self._send(200, {"scene": bg})
                if route == "/track":
                    # empty means "director"; None means the id is not on disk
                    bgm = channel.set_track(payload.get("bgm"))
                    if bgm is None:
                        return self._send(400, {"error": "no such track",
                                                "bgm": payload.get("bgm")})
                    return self._send(200, {"track": bgm})
                if route == "/outfit":
                    # empty means her default; None means the id is not on disk
                    got = channel.set_outfit(payload.get("outfit"))
                    if got is None:
                        return self._send(400, {"error": "no such outfit",
                                                "outfit": payload.get("outfit")})
                    return self._send(200, {"outfit": got})
                if route == "/model":
                    # empty means "her config": hand the choice back
                    got = channel.set_voice_model(payload.get("model"))
                    if got is None:
                        return self._send(400, {"error": "no model picker"})
                    if not got.get("ok"):
                        return self._send(400, got)
                    return self._send(200, got)
                if route == "/model-stage":
                    # empty means "each stage role's own config entry"
                    got = channel.set_stage_model(payload.get("model"))
                    if got is None:
                        return self._send(400, {"error": "no model picker"})
                    if not got.get("ok"):
                        return self._send(400, got)
                    return self._send(200, got)
                if route == "/speak":
                    # the ♪ beside a line in the backlog: locate the clip already
                    # on disk for it and play it; do not make it again
                    url = channel.queue_speak(payload.get("text"), payload.get("id"))
                    if not url:
                        return self._send(400, {"error": "no audio for that line"})
                    return self._send(200, {"url": url})
                if route == "/director":
                    # one turn of the out-of-character console. It answers or
                    # proposes; it never writes a scene by itself.
                    text = (payload.get("text") or "").strip()
                    if not text:
                        return self._send(400, {"error": "no text"})
                    if not callable(channel.stage_chat):
                        return self._send(400, {"error": "no console"})
                    got = channel.stage_chat(text)
                    if not got:
                        return self._send(400, {"error": "no answer"})
                    return self._send(200, got)
                if route == "/director/approve":
                    # he approved the console's proposal: held for the loop,
                    # which writes the scene and opens it
                    prop = payload.get("proposal")
                    if not isinstance(prop, dict):
                        return self._send(400, {"error": "no proposal"})
                    channel.queue_director(prop)
                    return self._send(200, {"queued": True})
                if route == "/director/clear":
                    channel.queue_director_clear()
                    return self._send(200, {"queued": True})
                if route == "/touch":
                    return self._send(200, channel.handle_touch(payload.get("region")))
                text = (payload.get("text") or "").strip()
                if not text:
                    return self._send(400, {"error": "no text"})
                got = channel.queue_line(text)
                return self._send(200, {"queued": True, "id": got})

        self._httpd = ThreadingHTTPServer((self.host, self.port), Handler)
        self._httpd.daemon_threads = True
        self._server_thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._server_thread.start()

    def _touch(self):
        """He is at the stage. Told to the reunion clock (`sim/reunion.py`) on a
        page load, a control, or a line he typed -- never on the state poll,
        which the browser does on its own and which would say he is present
        while he is asleep in the chair."""
        fn = self.present_notice
        if callable(fn):
            try:
                fn()
            except Exception:
                pass

    def queue_line(self, text):
        """A line the player typed, for the runtime's next `get_new_messages`."""
        with self._lock:
            mid = self._inbound_next
            self._inbound_next += 1
            self._user_text = text
            if self._state:
                self._state["user_text"] = text
            state = dict(self._state) if self._state else None
        self._inbox.put({"id": mid, "text": text})
        if state is not None:
            self._notify(state)
        logger.log(f"[him] {text[:200]}")
        return mid

    def flush_queue(self):
        # nothing stale to drop: a line he typed while she was thinking is real
        return

    def get_new_messages(self):
        out = []
        while True:
            try:
                item = self._inbox.get_nowait()
            except queue.Empty:
                break
            out.append((item["text"], item["id"]))
        return out

    def send_typing(self):
        # the VN stage has no typing indicator; her line appears when it is said
        return

    def send_message(self, text):
        if not text or not text.strip():
            return False
        text = text.strip()
        signal = self._signal_for(text)
        with self._lock:
            hub_id = self._hub_next
            self._hub_next += 1
            self._history.append({"id": hub_id, "text": text, "signal": signal})
            self._history = self._history[-50:]
        self._publish(text, signal, hub_id)
        return hub_id

    def delete_message(self, message_id):
        if not message_id:
            return False
        with self._lock:
            row = next((r for r in self._history if r["id"] == int(message_id)), None)
            if row is not None:
                row["removed"] = True
            shown = self._shown_id == int(message_id)
        if shown:
            self._replace_shown_text(int(message_id), "……")
        return row is not None or shown

    def edit_message(self, message_id, text):
        if not message_id or text is None:
            return False
        signal = self._signal_for(text)
        with self._lock:
            row = next((r for r in self._history if r["id"] == int(message_id)), None)
            if row is not None:
                row["text"] = text
                row["signal"] = signal
            shown = self._shown_id == int(message_id)
        if shown:
            self._replace_shown_text(int(message_id), text, signal)
        elif self.store is not None:
            frame = self.store.vn_frames([int(message_id)]).get(int(message_id))
            if frame:
                frame["text"] = text
                frame["audio"] = None
                frame["audio_by_turn"] = {}
                self._apply_reply_expression(frame, signal)
                self.store.set_vn_frame(int(message_id), frame)
        return row is not None or shown

    def _apply_reply_expression(self, frame, signal):
        try:
            res = self.expr.resolve(self._face_signal(signal), costume=self._costume_override)
            frame["mood"] = res["expression"]
            frame["c4"] = res["c4"]
            frame["costume"] = res.get("costume")
            frame["sprite"] = {"tag": res["tag"],
                               "base": self._sprite_url(res["base_tag"]),
                               "diff": self._sprite_url(res["diff_tag"]) if res["diff_tag"] else None,
                               "geometry": res.get("geometry"), "zoom": self._sprite_zoom()}
            frame["face"] = self._face_url(res["face"])
            frame["overlay"] = self._emotion_url(res["overlay"]) if res.get("overlay") else None
        except Exception as exc:
            logger.log(f"[vn] edited expression failed: {type(exc).__name__}: {exc}")

    def _replace_shown_text(self, hub_id, text, signal=None):
        """Apply a chosen reply after restart without resetting its stage."""
        with self._lock:
            if not self._state or self._shown_id != hub_id:
                return
            self._rev += 1
            self._state["turn"] = self._rev
            self._state["text"] = text
            self._state["audio"] = None
            self._state["audio_by_turn"] = {}
            if signal is not None:
                self._apply_reply_expression(self._state, signal)
            self._state["updated"] = datetime.datetime.now().isoformat(timespec="seconds")
            state = dict(self._state)
        self._write_state()
        if self.store is not None:
            self.store.set_vn_frame(hub_id, state)
        self._notify(state)

    def show_selected_reply(self, hub_id, text):
        """Move the box to the surviving line if a shorter answer dropped it."""
        hub_id = int(hub_id)
        if self._shown_id == hub_id:
            with self._lock:
                if not self._state or not self._state.get("branch_from"):
                    return
                self._state.pop("branch_from", None)
                self._state.pop("resume_view", None)
                state = dict(self._state)
            self._write_state()
            self._notify(state)
            return
        frame = self.store.vn_frames([hub_id]).get(hub_id) if self.store else None
        if not frame:
            return
        with self._lock:
            self._rev += 1
            frame.update({"turn": self._rev, "turn_id": hub_id, "text": text,
                          "audio": None, "audio_by_turn": {},
                          "updated": datetime.datetime.now().isoformat(timespec="seconds")})
            frame.pop("resume_view", None)
            frame.pop("branch_from", None)
            self._shown_id = hub_id
            self._state = frame
            state = dict(frame)
        self._write_state()
        self.store.set_vn_frame(hub_id, state)
        self._notify(state)

    def clip_match(self, text, clip_id=None):
        """The recorded clip for this line AND what it matched, or None.

        `clip_for` answers only which file to play; the stage also says which
        recorded line it is playing, so this keeps the matched line, the ratio
        and the tier (1 whole line, 3 pause-only near miss; 0 is a clip id she
        named herself). Which modes are consulted is the stage's `voice_mode`:
        `tts` never plays from tape, so it answers None here."""
        if not self.voice_index:
            return None
        try:
            return self.voice_index.resolve_detail(
                text, clip_id=clip_id, mode=self._voice_mode)
        except Exception as e:
            logger.log(f"[vn] clip match failed: {type(e).__name__}")
            return None

    def clip_for(self, text, clip_id=None):
        """The recorded koikano clip for this line, or None.

        The runtime asks this before it synthesises: a clip id named outright
        wins, then a line whose text is one she has already spoken, and a miss
        returns None so MiniMax speaks it. `voice_mode` selects between
        synthesis only, an exact recorded line, and a pause-only near miss;
        see `channels/vn_voice.py` and `docs/voice.md`. Never guesses. What it
        matched is kept in `_last_clip_match` for the frame's own badge."""
        detail = self.clip_match(text, clip_id=clip_id)
        self._last_clip_match = detail or {}
        return detail.get("path") if detail else None

    def _stored_voice_mode(self):
        """The voice mode as the page or the config left it.

        A stage control, so the page's last choice wins; the config seeds it
        on a first boot. The legacy boolean `vn_clip_partial` (and
        `tts.clip_partial`) is read once and folded into the mode, so a save
        written before the mode existed comes back as exact or approximate."""
        raw = getattr(self.config, "raw", None)
        tts = (raw.get("tts") or {}) if isinstance(raw, dict) else {}
        configured = tts.get("voice_mode")
        has_config_mode = configured in VOICE_MODES
        if not has_config_mode:
            configured = None
        default = voice_mode(configured, bool(tts.get("clip_partial", False)))
        try:
            saved = self.store.get("vn_voice_mode", None) if self.store else None
            if saved in VOICE_MODES:
                return saved
            if saved is not None:
                # A value written while the control helper coerced to bool: it
                # is not a mode, so it must not stand in the way of the legacy
                # read. Drop it, once.
                try:
                    self.store.set("vn_voice_mode", None)
                except Exception:
                    pass
            legacy = self.store.get("vn_clip_partial", None) if self.store else None
        except Exception:
            legacy = None
        # An explicit config mode is a decision and stands over the save's
        # legacy boolean; the legacy read is only for a config that names none.
        mode = default if (has_config_mode or legacy is None) else voice_mode(partial=bool(legacy))
        self._persist_control("vn_voice_mode", mode)
        return mode

    def _stage_voice(self, ogg_path):
        """Put a rendered clip where the stage can fetch it and return its URL.

        A recorded clip is served in place from the corpus; synthesis output is
        copied into the run's voice directory, which holds only synthesis. No
        turn is touched here: the URL is the whole answer for a line he asked to
        hear from the backlog."""
        if not ogg_path or not os.path.isfile(ogg_path):
            return ""
        name = os.path.basename(ogg_path)
        # a recorded clip is served in place from the corpus, so the run's own
        # voice directory holds only synthesis output
        if self.clip_dir and os.path.dirname(os.path.abspath(ogg_path)) == os.path.abspath(self.clip_dir):
            return f"/asset/clip/{name}"
        dst = os.path.join(self.voice_dir, name)
        try:
            if os.path.abspath(ogg_path) != os.path.abspath(dst):
                shutil.copyfile(ogg_path, dst)
        except Exception as e:
            logger.log(f"[vn] voice not staged: {type(e).__name__}")
            return ""
        return f"/audio/{name}"

    def voice_url(self, ogg_path):
        """The URL for a clip that is already on disk, with nothing attached to
        a turn. The backlog's ♪ asks for a line he already heard, so the file is
        located and served rather than filed against a turn of its own."""
        return self._stage_voice(ogg_path)

    def send_voice(self, ogg_path, attach_to=0):
        url = self._stage_voice(ogg_path)
        if not url:
            return False
        name = os.path.basename(ogg_path)
        if url.startswith("/asset/clip/"):
            self._voice_source = "clip"
            self._voice_clip = os.path.splitext(name)[0].upper()
        else:
            self._voice_source = "tts"
            self._voice_clip = None
        self._attach_audio(url, attach_to)
        return True

    def send_audio(self, audio_path):
        return self.send_voice(audio_path)

    def send_photo(self, path):
        # the stage has no photo row; the caption bubble that follows is the turn
        return False

    def send_sticker(self, path, bucket="", ts=None, quiet=False, auto=False):
        """A reaction of hers: the mood-band face, drawn on the current turn."""
        if bucket:
            try:
                self._set_face({"bucket": bucket})
            except Exception as e:
                logger.log(f"[vn] sticker face not set: {type(e).__name__}")
                return False
        return True

    def send_document(self, path, caption=""):
        return False

    def file_link(self, path):
        # no ops view to link into; fall through to send_document
        return ""

    def queue_speak(self, text, mid=0):
        """He asked to hear one line again -- the ♪ beside it in the backlog.

        The line was voiced when it was said, so its clip is already on disk
        (the TTS cache or the recorded corpus). Locate it and hand back the URL
        the page can play. It is NOT attached to a turn: a backlog tap is not a
        bubble of a reply, and `audio_by_turn` prunes its oldest keys, which
        dropped the clip the tap had just filed there (2026-09-17). Returns the
        URL, or '' when there is nothing to play."""
        line = str(text or "").strip()
        if not line:
            return ""
        mid = int(mid or 0)
        fn = self.speak_now
        if callable(fn):
            logger.log(f"[vn] he asked to hear: {line[:60]}")
            try:
                url = fn(line, mid)
            except Exception as e:
                logger.log(f"[vn] speak-now failed: {type(e).__name__}")
                return ""
            return url or ""
        # No renderer wired (a channel that cannot voice): fall back to the
        # runtime's worker, which posts the audio back to the line.
        with self._lock:
            self._speak_queue.append({"id": mid, "text": line[:600]})
        logger.log(f"[vn] he asked to hear (queued): {line[:60]}")
        return ""

    def speak_requests(self):
        with self._lock:
            rows = list(self._speak_queue)
            self._speak_queue = []
        return rows

    def get_ops_commands(self):
        return []

    def post_ops_result(self, cmd, text):
        return None

    def peer_send(self, to_id, text):
        return False

    def peer_updates(self, after=0):
        return []

    def post_swipes(self, hub_id, items, sat=0, rows=()):
        return False

    def post_swipes_state(self, hub_id, pending="", reconstructed=None):
        return False

    def state_push_due(self):
        return None

    def hub_rows(self):
        return []


if __name__ == "__main__":
    # a stub boot: the channel alone, no SCAIL App, so the stage can be checked
    # without a key. Run from the repo root: python channels/vn_bot.py
    import time
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, root)

    class _Char:
        name = "Momoka"
        name_ja = "百花"

    class _Stub:
        raw = {"vn": {"enabled": True}}
        character = _Char()

    vn = VnInterface(_Stub())
    vn.verify_connection()
    vn.send_message("こんにちは、今日はいい天気だね。")
    print(f"stub turn written to {vn.state_path}")
    print(f"view: http://{vn.host}:{vn.port}/  (Ctrl+C to stop)")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
