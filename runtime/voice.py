"""Momoka's voice: a line of text in, a playable audio file out.

Uses the shared MiniMax account (same key, model and voice as SCAILV3) through
the synchronous endpoint, then converts FLAC to Ogg/Opus with ffmpeg. Render
output is cached by a hash of the text, so a repeated line is free.

If a game clip id is given (e.g. `MMK000123`), that recorded clip is used
instead of synthesis.
"""

import binascii
import hashlib
import json
import os
import subprocess
import sys

import requests

try:
    from . import common
except ImportError:
    import common


class VoiceError(RuntimeError):
    pass


class Voice:
    def __init__(self, cfg=None):
        self.cfg = cfg or common.load_config()
        t = self.cfg["tts"]
        self.enabled = bool(t["enabled"])
        self.endpoint = t["endpoint"]
        self.mode = t.get("mode", "sync")
        self.ffmpeg = t.get("ffmpeg", "ffmpeg")
        self.output_format = t.get("output_format", "ogg")
        self.timeout = float(t.get("timeout_seconds", 120))
        self.voice_override = str(t.get("voice_id") or "").strip()
        self.audio_dir = common.resolve(self.cfg["paths"]["audio_dir"])
        self.cache_dir = common.resolve(self.cfg["paths"]["cache_dir"])
        self.clip_dir = os.path.join(common.resolve(self.cfg["assets"]["character_dir"]),
                                     self.cfg["assets"]["voice_dir"])
        os.makedirs(self.audio_dir, exist_ok=True)
        os.makedirs(self.cache_dir, exist_ok=True)
        self._minimax = None

    def minimax(self):
        if self._minimax is None:
            with open(common.resolve(self.cfg["tts"]["minimax_config_path"]), encoding="utf-8") as f:
                self._minimax = json.load(f)
        return self._minimax

    def voice_id(self):
        mc = self.minimax()
        if self.voice_override:
            return self.voice_override
        return (mc.get("voice_setting") or {}).get("voice_id", "")

    def clip_path(self, clip_id):
        """A recorded game clip, if that id exists. `MMK000123` or `000123`."""
        cid = str(clip_id or "").strip().upper()
        if not cid:
            return None
        if not cid.startswith("MMK"):
            cid = "MMK" + cid[-6:]
        path = os.path.join(self.clip_dir, cid + ".ogg")
        return path if os.path.exists(path) else None

    def _cache_path(self, text):
        voice = self.voice_id() or "shared"
        norm = "".join(text.split()).strip("。！？!?…・")
        key = hashlib.sha1((voice + "\x00" + norm).encode("utf-8")).hexdigest()[:16]
        return os.path.join(self.cache_dir, key + "." + self.output_format)

    def speak(self, text, clip=None):
        """Return the path to the audio for this line.

        A given clip id wins over synthesis. Otherwise a cached render is
        reused, and a fresh one is made if not.
        """
        if clip:
            path = self.clip_path(clip)
            if path:
                return path
        text = (text or "").strip()
        if not text:
            raise VoiceError("nothing to speak")
        out = self._cache_path(text)
        if os.path.exists(out) and os.path.getsize(out) > 0:
            return out
        flac = out + ".flac"
        self._render_sync(text, flac)
        if self.output_format == "flac":
            os.replace(flac, out)
            return out
        self._to_opus(flac, out)
        os.remove(flac)
        return out

    def _render_sync(self, text, flac_path):
        mc = self.minimax()
        payload = {
            "model": mc.get("model_id", "speech-2.8-hd"),
            "text": text,
            "stream": False,
            "voice_setting": {**dict(mc.get("voice_setting") or {}), "voice_id": self.voice_id()},
            "audio_setting": {"sample_rate": 32000, "bitrate": 128000, "format": "flac", "channel": 1},
        }
        headers = {"Authorization": f"Bearer {mc['api_key']}", "Content-Type": "application/json"}
        try:
            r = requests.post(self.endpoint, json=payload, headers=headers,
                              timeout=(10, self.timeout))
        except requests.RequestException as e:
            raise VoiceError(f"tts request failed: {type(e).__name__}: {e}") from e
        if r.status_code != 200:
            raise VoiceError(f"tts http {r.status_code}: {r.text[:400]}")
        try:
            data = r.json()
        except ValueError:
            raise VoiceError(f"tts non-JSON response: {r.text[:400]}")
        base = data.get("base_resp") or {}
        if base.get("status_code", 0) != 0:
            raise VoiceError(f"tts api {base.get('status_code')}: {base.get('status_msg')}")
        hexdata = (data.get("data") or {}).get("audio") or ""
        if not hexdata:
            raise VoiceError("tts api returned no audio")
        with open(flac_path, "wb") as f:
            f.write(binascii.unhexlify(hexdata))

    def _to_opus(self, flac_path, out_path):
        res = subprocess.run(
            [self.ffmpeg, "-y", "-loglevel", "error", "-i", flac_path,
             "-c:a", "libopus", "-b:a", "48k", "-vbr", "on", "-application", "voip", out_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace")
        if res.returncode != 0 or not os.path.exists(out_path):
            raise VoiceError(f"ffmpeg failed: {(res.stderr or '').strip()[:300]}")


def selftest(line):
    cfg = common.load_config()
    v = Voice(cfg)
    path = v.speak(line)
    size = os.path.getsize(path)
    print(f"[voice] voice_id={v.voice_id()}")
    print(f"[voice] wrote {path} ({size} bytes)")
    print(f"[voice] cache_dir={v.cache_dir}")
    return 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--selftest" in sys.argv:
        raise SystemExit(selftest(args[0] if args else "百花、こんにちは。"))
    print('usage: python runtime/voice.py --selftest "日本語のせりふ"')
