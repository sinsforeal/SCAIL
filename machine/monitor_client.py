"""The bots' view of his machine when the collector is its own process.

`machine/collector.py` is the one process on this machine that watches the
keyboard, the foreground window and the browser history, and it writes two
files as it goes: `sensors.telemetry_now_path`, what is in front of him this
second and when he last touched anything, every few seconds; and beside it
`<same>.attention.json`, the window sessions of the last day, whenever one
ends. This reads them and answers the three questions `sim/phone.py` and
`sim/receipts.py` used to put to the in-process monitor, in the same shapes,
so neither knows the difference.

Why it exists: each bot used to run the whole sensor stack inside itself. Two
bots meant two processes copying his 180 MB browser history into ONE temp
file every thirty seconds, and two id counters appending to one feed -- 157
duplicate ids, every entry read twice by each character, and from 02:52 on
2026-09-03 the Chrome half of the feed blind for both while the copies
collided. His machine is one thing and it is watched once.

When the collector is not running the answers are "unknown", which reads as
present and awake: nobody is put to sleep on a guess.
"""
import json
import os
import time

import logger


class RemoteMonitor:
    def __init__(self, config):
        self.config = config
        self.path = config.telemetry_now_path
        self.attention_path = os.path.splitext(self.path)[0] + ".attention.json"
        self.stale_after = float(getattr(config, "telemetry_now_stale_seconds", 30) or 30)
        self._now = {}
        self._now_mtime = 0.0
        self._att = []
        self._att_mtime = 0.0
        self._warned = False

    def _read(self, path, last_mtime, last_value):
        try:
            m = os.path.getmtime(path)
        except OSError:
            return None, 0.0
        if m == last_mtime:
            return last_value, m
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f), m
        except (OSError, ValueError):
            # a torn read while the collector replaces the file: keep the last good one
            return last_value, last_mtime

    def _warn(self, what):
        if not self._warned:
            logger.log(f"[machine] the collector is not running: it {what}. talkapp.cmd starts it; "
                       "until then his machine reads as present and awake")
            self._warned = True

    def _load(self):
        val, m = self._read(self.path, self._now_mtime, self._now)
        if val is None:
            self._warn("has never written " + self.path)
            return {}
        self._now, self._now_mtime = val, m
        age = time.time() - m
        if age > self.stale_after:
            self._warn(f"stopped writing ({int(age)} s since {self.path} changed)")
            return {}
        if self._warned:
            logger.log("[machine] the collector is writing again")
            self._warned = False
        return self._now

    def alive(self):
        return bool(self._load())

    def right_now(self):
        """(process, title, seconds in that window, seconds since input), or
        (None, "", 0, idle) when he is idle -- the in-process monitor's shape."""
        d = self._load()
        if not d:
            return None, "", 0, 0.0
        now = time.time()
        idle = max(0.0, now - float(d.get("last_input_ts") or now))
        proc = d.get("proc") or None
        if d.get("is_idle") or not proc or str(proc).startswith("[SYSTEM IDLE"):
            return None, "", 0, idle
        return proc, d.get("title") or "", max(0.0, now - float(d.get("window_start") or now)), idle

    def seconds_since_input(self):
        d = self._load()
        if not d:
            return 0.0
        return max(0.0, time.time() - float(d.get("last_input_ts") or time.time()))

    def attention_since(self, since_ts):
        """Window sessions (start, end, process, title) touching the window
        after since_ts, the live one included, and when he last touched anything."""
        d = self._load()
        val, m = self._read(self.attention_path, self._att_mtime, self._att)
        if val is not None:
            self._att, self._att_mtime = val, m
        out = [tuple(s) for s in (self._att or []) if len(s) == 4 and float(s[1]) >= float(since_ts)]
        last_input = float(d.get("last_input_ts") or 0) if d else 0
        if d and not d.get("is_idle") and d.get("proc") and d.get("window_start"):
            out.append((float(d["window_start"]), time.time(), d["proc"], d.get("title") or ""))
        return out, last_input

    def stop(self):
        return None
