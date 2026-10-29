"""Offline payload and cache checks for Momoka's generated voice."""
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from channels.tts_handler import TTSQueue
from config import Section


class Response:
    status_code = 200
    content = b"flac"
    text = ""
    def __init__(self, data=None):
        self.data = data or {"base_resp": {"status_code": 0}, "data": {"audio": "666c6163"}}
    def json(self):
        return self.data
    def raise_for_status(self):
        pass


def main():
    q = object.__new__(TTSQueue)
    q.config = SimpleNamespace(tts=SimpleNamespace(
        voice_id="sample_voice", emotion_enabled=True, language_boost="Japanese",
        pronunciation_dict={"tone": ["\u767e\u82b1/\u3082\u3082\u304b", "\u4e00\u609f/\u3044\u3061\u3054"]}, interjection_tags=True,
        sync_endpoint="https://api.minimax.io/v1/t2a_v2", sync_timeout_seconds=5,
        async_fallback_timeout_seconds=2))
    q._minimax_cfg = {"model_id": "speech-2.8-hd", "api_key": "test",
                      "voice_setting": {"voice_id": "shared", "speed": 1}}
    with tempfile.TemporaryDirectory() as tmp:
        flac = os.path.join(tmp, "line.flac")
        calls = []
        def post(url, **kwargs):
            calls.append((url, kwargs))
            return Response()
        with patch("channels.tts_handler.requests.post", post):
            assert q._render_sync("百花、ふふ。", flac, "joy", "(sighs)")
        payload = calls[0][1]["json"]
        assert payload["text"] == "(sighs) 百花、ふふ。"
        assert payload["voice_setting"]["emotion"] == "happy"
        assert payload["language_boost"] == "Japanese"
        assert payload["pronunciation_dict"] == {"tone": ["\u767e\u82b1/\u3082\u3082\u304b", "\u4e00\u609f/\u3044\u3061\u3054"]}
        assert Path(flac).read_bytes() == b"flac"
        q.config.tts.pronunciation_dict = Section({"tone": ["\u767e\u82b1/\u3082\u3082\u304b", "\u4e00\u609f/\u3044\u3061\u3054"]})
        assert q._key("百花。", "joy")
        with patch("channels.tts_handler.requests.post", post):
            assert q._render_sync("百花。", flac, "joy")
        assert calls[-1][1]["json"]["pronunciation_dict"] == {"tone": ["\u767e\u82b1/\u3082\u3082\u304b", "\u4e00\u609f/\u3044\u3061\u3054"]}
        base = q._key("百花。", "joy")
        assert base != q._key("百花。", "sad")
        assert base != q._key("百花。", "joy", "(sighs)")
        q._minimax_cfg["model_id"] = "speech-2.8-turbo"
        assert base != q._key("百花。", "joy")
        q._minimax_cfg["model_id"] = "speech-2.8-hd"
        q._minimax_cfg["voice_setting"]["speed"] = 1.1
        assert base != q._key("百花。", "joy")
        q._minimax_cfg["voice_setting"]["speed"] = 1
        seq = [Response({"base_resp": {"status_code": 0}, "task_id": 12, "file_id": 34})]
        gets = [Response({"base_resp": {"status_code": 0}, "status": "Success", "file_id": 34}),
                Response({"base_resp": {"status_code": 0}, "file": {"download_url": "https://example.test/audio"}}),
                Response()]
        with patch("channels.tts_handler.requests.post", side_effect=seq) as p, \
             patch("channels.tts_handler.requests.get", side_effect=gets) as g:
            assert q._render_async("百花。", flac, "sadness", "(sighs)")
        submitted = p.call_args.kwargs["json"]
        assert submitted["voice_setting"]["emotion"] == "sad"
        assert submitted["language_boost"] == "Japanese"
        assert submitted["pronunciation_dict"]["tone"] == ["\u767e\u82b1/\u3082\u3082\u304b", "\u4e00\u609f/\u3044\u3061\u3054"]
        assert submitted["text"] == "(sighs) 百花。"
        assert g.call_count == 3
        q.tg = SimpleNamespace(clip_for=lambda text: "recorded.ogg")
        assert q.render("百花。", emotion="joy", interjection="(sighs)") == "recorded.ogg"
    print("tts expression: pass")


if __name__ == "__main__":
    main()
