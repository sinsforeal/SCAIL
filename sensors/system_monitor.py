import os
import time
import threading
import ctypes
import ctypes.wintypes
import datetime
import re
from collections import Counter
import psutil
import logger
from sensors import bands
from sensors import blocklist
from sensors import vault_monitor

try:
    import win32gui
    import win32process
except ImportError:
    win32gui = None
    win32process = None


user32 = ctypes.windll.user32


def _get_foreground_window_info():
    if not win32gui:
        return None, None, None

    try:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None, None, None

        title = win32gui.GetWindowText(hwnd)
        _, pid = win32process.GetWindowThreadProcessId(hwnd)

        try:
            proc = psutil.Process(pid)
            proc_name = proc.name()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            proc_name = "unknown"

        return proc_name, title, pid
    except Exception:
        return None, None, None


def _is_md5_filename(filename):
    name_no_ext = os.path.splitext(filename)[0]
    return bool(re.fullmatch(r'[0-9a-fA-F]{32}', name_no_ext))


def _extract_filename_from_title(title, process_name):
    if not title:
        return ""

    known_patterns = {
        "jpegview": r'^(.*?\.\w+)',
        "irfanview": r'^(.*?\.\w+)',
        "photoviewer": r'^(.*?\.\w+)',
    }

    proc_lower = process_name.lower().replace(".exe", "")
    for key, pattern in known_patterns.items():
        if key in proc_lower:
            match = re.search(pattern, title)
            if match:
                return match.group(1).strip()

    parts = title.split(" - ")
    if parts:
        candidate = parts[0].strip()
        if '.' in candidate and len(candidate) < 260:
            return candidate

    return ""


def _extract_chrome_tab_title(title):
    if not title:
        return ""
    suffix = " - Google Chrome"
    if title.endswith(suffix):
        return title[:-len(suffix)].strip()
    return title.strip()


def _get_system_stats():
    try:
        cpu_percent = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        boot_time = psutil.boot_time()
        uptime_seconds = time.time() - boot_time

        top_procs = []
        for proc in psutil.process_iter(['name', 'cpu_percent', 'memory_info']):
            try:
                info = proc.info
                if info['cpu_percent'] and info['cpu_percent'] > 0:
                    mem_mb = info['memory_info'].rss / (1024* 1024) if info['memory_info'] else 0
                    top_procs.append({
                        "name": info['name'],
                        "cpu_percent": info['cpu_percent'],
                        "memory_mb": round(mem_mb, 1)
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        top_procs.sort(key=lambda x: x['cpu_percent'], reverse=True)
        top_procs = top_procs[:10]

        return {
            "cpu_percent": cpu_percent,
            "memory_percent": mem.percent,
            "memory_used_gb": round(mem.used / (1024** 3), 1),
            "memory_total_gb": round(mem.total / (1024 **3), 1),
            "uptime_seconds": int(uptime_seconds),
            "top_processes": top_procs
        }
    except Exception as e:
        return {"error": str(e)}


class SystemMonitor:
    def __init__(self, config):
        self.config = config
        self.enabled = config.system_monitor_enabled
        self.poll_interval_ms = config.system_monitor_poll_ms
        self.image_viewer_processes = [p.lower() for p in config.image_viewer_processes]
        self.chrome_processes = [p.lower() for p in config.chrome_process_names]
        self.stats_interval = config.system_stats_interval_seconds
        self.typing_burst_gap = config.typing_burst_gap_seconds
        self.chrome_scrape_time_threshold = config.chrome_scrape_time_threshold_seconds
        self.chrome_scrape_keypress_threshold = config.chrome_scrape_interaction_threshold_keypresses

        self._lock = threading.Lock()
        self._running = False

        self._current_window = None
        self._current_title = None
        self._current_start = None
        self._current_keypresses = 0
        self._current_mouse_clicks = 0

        # Input and Idle tracking variables
        self._last_input_time = time.time()
        self._is_idle = False

        self._window_sessions = []
        # attention log: every finalized session for the last day, independent
        # of consume_accumulated(), so read receipts can be inferred live
        self._attention = []
        self._chrome_tabs = []
        self._input_activity = {
            "total_keypresses": 0,
            "categories": {"alphanumeric": 0, "navigation": 0, "function": 0, "modifier": 0, "mute": 0, "vol_down": 0, "vol_up": 0, "media_ctrl": 0, "other": 0},
            "mouse_distance_pixels": 0,
            "mouse_clicks": 0,
            "typing_bursts": []
        }
        self._system_stats = {}
        self._opened_files = []
        # the processes whose title is blanked whatever it says, read once
        self._title_blank_procs = None

        self._last_mouse_pos = None
        self._prev_key_states = {}
        self._last_keypress_time = 0
        self._current_burst_start = 0
        self._current_burst_count = 0

        self._last_stats_time = 0

        self._gelbooru_queue = []
        self._gelbooru_results = {}
        self._scrape_queue = []
        self._scrape_results = {}

        self._gelbooru_classifier = None
        self._web_scraper = None

        if self.enabled:
            psutil.cpu_percent(interval=None)

    def set_gelbooru_classifier(self, classifier):
        self._gelbooru_classifier = classifier

    def set_web_scraper(self, scraper):
        self._web_scraper = scraper

    def start(self):
        if not self.enabled:
            logger.log("[SYSMON] Disabled by config.")
            return

        self._running = True
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

        self._gelbooru_thread = threading.Thread(target=self._gelbooru_worker, daemon=True)
        self._gelbooru_thread.start()

        self._scrape_thread = threading.Thread(target=self._scrape_worker, daemon=True)
        self._scrape_thread.start()

        logger.log(f"[SYSMON] Started. Poll: {self.poll_interval_ms}ms | Stats: {self.stats_interval}s")

    def stop(self):
        self._running = False

    def _poll_loop(self):
        while self._running:
            try:
                self._poll_foreground()
                self._poll_input()
                self._poll_system_stats()
            except Exception as e:
                logger.log(f"[SYSMON ERROR] Poll: {e}")

            time.sleep(self.poll_interval_ms / 1000.0)

    def _poll_foreground(self):
        # Prevent tracking rogue window changes if the user walked away
        if self._is_idle:
            return

        proc_name, title, pid =_get_foreground_window_info()
        if not proc_name:
            return
        title = self._allowed_title(proc_name, title)

        now = time.time()

        if proc_name != self._current_window or title != self._current_title:
            self._finalize_current_session(now)
            self._current_window = proc_name
            self._current_title = title
            self._current_start = now
            self._current_keypresses = 0
            self._current_mouse_clicks = 0

    def _allowed_title(self, proc_name, title):
        """The title a character may be handed, or "" -- blanked, never
        dropped: dropping the window would leave `right_now()` on the one
        before it. Blanked when `sensors/blocklist.py` says the name is one
        she must not be shown, or the process is in
        `sensors.window_title_blank_processes`. The window still counts, with
        its process and its minutes; only its name is gone.

        A file manager's title is the FOLDER it is showing and an editor's is
        the PATH of the open file, so blanking the title here is what keeps a
        folder name and a path out of every reader downstream -- the same list
        also reaches his browsing history, which arrives by another sensor
        (`sensors/chrome_monitor.py`)."""
        if not title:
            return title
        if self._title_blank_procs is None:
            self._title_blank_procs = {str(x).lower() for x in (getattr(self.config, "window_title_blank_processes", None) or [])}
        if str(proc_name or "").lower() in self._title_blank_procs:
            return ""
        if blocklist.hidden(self.config, proc_name):
            return ""
        return "" if blocklist.blocks(self.config, title) else title

    def _finalize_current_session(self, end_time):
        if not self._current_window or not self._current_start:
            return

        duration = end_time - self._current_start
        if duration < 0.5:
            return

        session = {
            "process_name": self._current_window,
            "window_title": self._current_title or "",
            "start_time": self._current_start,
            "end_time": end_time,
            "duration_seconds": round(duration, 1),
            "keypresses_during": self._current_keypresses,
            "mouse_clicks_during": self._current_mouse_clicks,
            "is_image_viewer": False,
            "is_chrome": False,
            "image_filename": "",
            "chrome_tab_title": "",
            "md5": ""
        }

        proc_lower = self._current_window.lower()

        if proc_lower in self.image_viewer_processes:
            session["is_image_viewer"] = True
            filename =_extract_filename_from_title(self._current_title, self._current_window)
            session["image_filename"] = filename
            if filename and _is_md5_filename(filename):
                md5 = os.path.splitext(filename)[0].lower()
                session["md5"] = md5
                if md5 not in self._gelbooru_results:
                    with self._lock:
                        self._gelbooru_queue.append(md5)

        elif proc_lower in self.chrome_processes:
            session["is_chrome"] = True
            tab_title =_extract_chrome_tab_title(self._current_title)
            session["chrome_tab_title"] = tab_title

            eligible_for_scrape = (
                duration >= self.chrome_scrape_time_threshold or
                self._current_keypresses >= self.chrome_scrape_keypress_threshold
            )
            if tab_title and eligible_for_scrape and self.config.chrome_scrape_enabled:
                if tab_title not in self._scrape_results:
                    with self._lock:
                        self._scrape_queue.append({
                            "title": tab_title,
                            "duration": duration,
                            "keypresses": self._current_keypresses,
                            "timestamp": end_time
                        })

        if hasattr(self.config, 'vault_read_time_threshold_seconds') and duration >= self.config.vault_read_time_threshold_seconds:
            title_clean =_clean_window_title(self._current_title, self._current_window)
            matched_path = vault_monitor.match_title_to_vault_file(self.config, title_clean)
            if matched_path:
                session["read_vault_file"] = matched_path

        with self._lock:
            self._window_sessions.append(session)
            self._attention.append((session["start_time"], end_time, session["process_name"], session["window_title"]))
            cutoff = end_time - 86400
            while self._attention and self._attention[0][1] < cutoff:
                self._attention.pop(0)

    def right_now(self):
        """What is in front on his PC this second and how long since he touched
        it: (process, title, seconds_in_window, seconds_since_input)."""
        with self._lock:
            proc = self._current_window
            title = self._current_title or ""
            start = self._current_start or time.time()
            idle = time.time() - self._last_input_time
            is_idle = self._is_idle
        if is_idle or not proc or proc.startswith("[SYSTEM IDLE"):
            return None, "", 0, idle
        return proc, title, time.time() - start, idle

    def seconds_since_input(self):
        """Seconds since the last real keypress, click or mouse move. Processes running in the background do not count."""
        with self._lock:
            return time.time() - self._last_input_time

    def attention_since(self, since_ts):
        """Sessions (start, end, process, title) touching the window after since_ts, including the live one."""
        now = time.time()
        with self._lock:
            out = [a for a in self._attention if a[1] >= since_ts]
            if self._current_window and self._current_start and not self._is_idle:
                out.append((self._current_start, now, self._current_window, self._current_title or ""))
            last_input = self._last_input_time
        return out, last_input

    def _poll_input(self):
        now = time.time()

        total_new_presses = 0
        categories = {"alphanumeric": 0, "navigation": 0, "function": 0, "modifier": 0, "mute": 0, "vol_down": 0, "vol_up": 0, "media_ctrl": 0, "other": 0}

        for vk in range(1, 255):
            state = user32.GetAsyncKeyState(vk)
            was_pressed = (state & 0x0001) != 0

            if was_pressed:
                total_new_presses += 1
                cat =_categorize_vk(vk)
                categories[cat] += 1

        mouse_pos = ctypes.wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(mouse_pos))
        current_pos = (mouse_pos.x, mouse_pos.y)

        mouse_dist = 0
        if self._last_mouse_pos:
            dx = current_pos[0] - self._last_mouse_pos[0]
            dy = current_pos[1] - self._last_mouse_pos[1]
            mouse_dist = (dx* dx + dy* dy)** 0.5
        self._last_mouse_pos = current_pos

        lbutton = user32.GetAsyncKeyState(0x01) & 0x0001
        rbutton = user32.GetAsyncKeyState(0x02) & 0x0001
        new_clicks = (1 if lbutton else 0) + (1 if rbutton else 0)

        has_input = total_new_presses > 0 or new_clicks > 0 or mouse_dist > 5

        # IDLE Logic Interception
        if has_input:
            self._last_input_time = now
            if self._is_idle:
                self._is_idle = False
                self._finalize_current_session(now)
                # Force the next foreground grab to start a new legit window session
                self._current_window = None
                self._current_title = None
        else:
            if now - self._last_input_time >= 30 and not self._is_idle:
                self._is_idle = True
                self._finalize_current_session(now)
                # Inject explicit IDLE pseudo window session
                self._current_window = "[SYSTEM IDLE / AFK]"
                self._current_title = ""
                self._current_start = now
                self._current_keypresses = 0
                self._current_mouse_clicks = 0

        with self._lock:
            self._input_activity["total_keypresses"] += total_new_presses
            for cat, count in categories.items():
                self._input_activity["categories"][cat] += count
            self._input_activity["mouse_distance_pixels"] += int(mouse_dist)
            self._input_activity["mouse_clicks"] += new_clicks

            self._current_keypresses += total_new_presses
            self._current_mouse_clicks += new_clicks

            if total_new_presses > 0:
                if now - self._last_keypress_time > self.typing_burst_gap:
                    if self._current_burst_count > 3:
                        self._input_activity["typing_bursts"].append({
                            "start": self._current_burst_start,
                            "end": self._last_keypress_time,
                            "count": self._current_burst_count
                        })
                    self._current_burst_start = now
                    self._current_burst_count = 0

                self._current_burst_count += total_new_presses
                self._last_keypress_time = now

    def _poll_system_stats(self):
        now = time.time()
        if now - self._last_stats_time < self.stats_interval:
            return

        stats = _get_system_stats()
        with self._lock:
            self._system_stats = stats
        self._last_stats_time = now

    def _gelbooru_worker(self):
        while self._running:
            md5 = None
            with self._lock:
                if self._gelbooru_queue:
                    md5 = self._gelbooru_queue.pop(0)

            if md5 and self._gelbooru_classifier:
                result = self._gelbooru_classifier.classify_by_md5(md5)
                if result:
                    with self._lock:
                        self._gelbooru_results[md5] = result
                    logger.log(f"[SYSMON] Gelbooru classified: {md5[:12]}... score={result.get('local_score', '?')}")
                else:
                    with self._lock:
                        self._gelbooru_results[md5] = {"error": "not_found"}
                    logger.log(f"[SYSMON] Gelbooru miss: {md5[:12]}...")
            else:
                time.sleep(0.5)

            time.sleep(0.2)

    def _scrape_worker(self):
        while self._running:
            item = None
            with self._lock:
                if self._scrape_queue:
                    item = self._scrape_queue.pop(0)

            if item and self._web_scraper:
                title = item["title"]
                if title not in self._scrape_results:
                    result = self._web_scraper.scrape_and_summarize(title)
                    with self._lock:
                        self._scrape_results[title] = result
                    if result.get("summary"):
                        logger.log(f"[SYSMON] Scraped+summarized: {title[:50]}...")
                    elif result.get("error"):
                        logger.log(f"[SYSMON] Scrape failed: {title[:50]}... ({result['error']})")
            else:
                time.sleep(1.0)

            time.sleep(0.5)

    def consume_accumulated(self):
        self._wait_for_pending_gelbooru()

        with self._lock:
            if self._current_burst_count > 3:
                self._input_activity["typing_bursts"].append({
                    "start": self._current_burst_start,
                    "end": self._last_keypress_time,
                    "count": self._current_burst_count
                })
                self._current_burst_count = 0

            sessions = list(self._window_sessions)
            self._window_sessions = []

            input_act = dict(self._input_activity)
            input_act["categories"] = dict(self._input_activity["categories"])
            input_act["typing_bursts"] = list(self._input_activity["typing_bursts"])
            self._input_activity = {
                "total_keypresses": 0,
                "categories": {"alphanumeric": 0, "navigation": 0, "function": 0, "modifier": 0, "mute": 0, "vol_down": 0, "vol_up": 0, "media_ctrl": 0, "other": 0},
                "mouse_distance_pixels": 0,
                "mouse_clicks": 0,
                "typing_bursts": []
            }

            stats = dict(self._system_stats)
            gelbooru = dict(self._gelbooru_results)
            scrape = dict(self._scrape_results)
            opened = list(self._opened_files)
            self._opened_files = []

        for session in sessions:
            if session.get("md5") and session["md5"] in gelbooru:
                session["gelbooru_data"] = gelbooru[session["md5"]]
            if session.get("chrome_tab_title") and session["chrome_tab_title"] in scrape:
                session["scrape_data"] = scrape[session["chrome_tab_title"]]

        return {
            "window_sessions": sessions,
            "input_activity": input_act,
            "system_stats": stats,
            "opened_files": opened
        }

    def _wait_for_pending_gelbooru(self, max_wait=10):
        deadline = time.time() + max_wait
        while time.time() < deadline:
            with self._lock:
                pending = len(self._gelbooru_queue)
            if pending == 0:
                return
            time.sleep(0.3)
        with self._lock:
            remaining = len(self._gelbooru_queue)
        if remaining > 0:
            logger.log(f"[SYSMON] Gelbooru drain timeout. {remaining} items still pending.")

    def get_buffer_info(self):
        with self._lock:
            return len(self._window_sessions), self._input_activity["total_keypresses"]


def _categorize_vk(vk):
    if vk == 0xAD: return "mute"
    if vk == 0xAE: return "vol_down"
    if vk == 0xAF: return "vol_up"
    if vk in (0xB0, 0xB1, 0xB2, 0xB3): return "media_ctrl"

    if (0x30 <= vk <= 0x39) or (0x41 <= vk <= 0x5A) or (0x60 <= vk <= 0x69):
        return "alphanumeric"
    if vk in (0x20, 0x08, 0x09, 0x0D, 0x2E):
        return "alphanumeric"
    if vk in (0x25, 0x26, 0x27, 0x28, 0x21, 0x22, 0x23, 0x24):
        return "navigation"
    if 0x70 <= vk <= 0x87:
        return "function"
    if vk in (0x10, 0x11, 0x12, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0x5B, 0x5C):
        return "modifier"
    return "other"


_DIGITS = re.compile(r"[\d.,:%+\-]+")


_BROWSER_SUFFIX = blocklist.BROWSER_SUFFIX


def _clean_window_title(title, process_name):
    if not title:
        return ""

    proc_lower = process_name.lower()

    if "notepad++" in proc_lower:
        basename = title.split("\\")[-1].split(" - ")[0].strip()
        return basename

    if "windowsterminal" in proc_lower or "cmd" in proc_lower:
        if "python" in title.lower():
            parts = title.split("python")[-1].strip()
            return f"python {parts}" if parts else ""
        return ""

    if "onecommander" in proc_lower:
        return title.strip()

    if "explorer" in proc_lower:
        return title.strip()

    if "firefox" in proc_lower or "chrome" in proc_lower:
        for suffix in [" — Mozilla Firefox", " - Google Chrome"]:
            if title.endswith(suffix):
                return title[:-len(suffix)].strip()
        return title.strip()

    first_part = title.split(" - ")[0].strip()
    if "\\" in first_part:
        return first_part.split("\\")[-1]
    return first_part


def _merge_key(title):
    """A title with its numbers taken out, for deciding whether two consecutive
    windows are the same window.

    A price page, a chart, an unread badge and a clock all repaint their own
    title several times a minute, and each repaint used to be a line. What is
    left after the digits go is the page."""
    return _DIGITS.sub("#", title or "")


def _fmt_dur(sec):
    if sec >= 60:
        return f"{int(sec // 60)}m{int(sec % 60)}s"
    return f"{int(sec)}s"


def _image_full_detail(s):
    """Full per-image block (filename + Gelbooru tags): the old behavior, kept
    for short viewing sessions and the first few images of a look."""
    lines = [f"  {s['image_filename']}"]
    gd = s.get("gelbooru_data")
    if gd and "error" not in gd:
        chars = ", ".join(gd.get("characters", [])) or "unknown"
        lines.append(f"  Characters: {chars}")
        lines.append(f"  Rating: {gd.get('gelbooru_rating', '?')}")
        if gd.get("wholesome_tags"):
            lines.append(f"  Wholesome: {', '.join(gd['wholesome_tags'])}")
        if gd.get("unwholesome_tags"):
            lines.append(f"  Unwholesome: {', '.join(gd['unwholesome_tags'])}")
        if gd.get("neutral_tags"):
            lines.append(f"  Neutral: {', '.join(gd['neutral_tags'])}")
        lines.append(f"  Score: {gd.get('local_score', '?')}/10 (0=unwholesome 5=neutral 10=wholesome)")
    elif s.get("md5") and (gd is None or (isinstance(gd, dict) and gd.get("error") == "not_found")):
        lines[0] += " [not on gelbooru]"
    return "\n".join(lines)


def _summarize_image_window(group):
    """One dated block for a burst of image views: when, how many, who/what
    series, the rating spread and the average score. She never sees the raw
    tags of thirty pictures, only this glance."""
    starts = [g["start_time"] for g in group]
    lo, hi = min(starts), max(starts)
    t0 = datetime.datetime.fromtimestamp(lo).strftime("%H:%M")
    t1 = datetime.datetime.fromtimestamp(hi).strftime("%H:%M")
    span = hi - lo
    span_str = _fmt_dur(span) if span >= 1 else "moments"
    chars, series, ratings, scores, no_data = Counter(), Counter(), Counter(), [], 0
    for s in group:
        gd = s.get("gelbooru_data")
        if gd and "error" not in gd:
            for c in gd.get("characters", []):
                chars[c] += 1
            for c in gd.get("copyrights", []):
                series[c] += 1
            if gd.get("gelbooru_rating"):
                ratings[gd["gelbooru_rating"]] += 1
            if isinstance(gd.get("local_score"), (int, float)):
                scores.append(gd["local_score"])
        else:
            no_data += 1
    when = f"[{t0}-{t1}]" if t1 != t0 else f"[{t0}]"
    lines = [f"{when} JPEGView, image session: {len(group)} pictures over {span_str}"]
    if chars:
        lines.append("  Mostly: " + ", ".join(f"{c} ({k})" if k > 1 else c for c, k in chars.most_common(4)))
    if series:
        lines.append("  Series: " + ", ".join(f"{c} ({k})" if k > 1 else c for c, k in series.most_common(3)))
    if ratings:
        rr = ", ".join(f"{r} x{k}" for r, k in ratings.most_common())
        lines.append(f"  Ratings: {rr}" + (f"; {no_data} not on gelbooru" if no_data else ""))
    elif no_data:
        lines.append(f"  {no_data} not on gelbooru")
    if scores:
        avg = round(sum(scores) / len(scores), 1)
        lines.append(f"  Score: avg {avg}/10 (range {int(min(scores))}-{int(max(scores))}) — 0=unwholesome 5=neutral 10=wholesome")
    return "\n".join(lines)


def _group_image_windows(img_sessions, gap_seconds):
    """Split image sessions (sorted by start) into bursts separated by > gap."""
    groups, cur, last = [], [], None
    for s in img_sessions:
        st = s["start_time"]
        if last is not None and st - last > gap_seconds:
            groups.append(cur)
            cur = []
        cur.append(s)
        last = st
    if cur:
        groups.append(cur)
    return groups


# What a window whose program may not be named is called instead. Plain, true
# of every program on that list, and it names none of them: the account still
# says he was at the machine for those minutes, which is what stops a reader
# concluding the machine was quiet through the hours he worked.
HIDDEN_WINDOW = "at the keyboard"


def _shown_title(config, session):
    """The title of a stored window session, or "" when the list blocks it.

    The monitor blanks a title as the window closes, so the feed on disk holds
    whatever the list said at the time it was written. A pattern added since
    then reaches nothing unless the stored title is read through the list
    again here, which is the last point before it becomes prose."""
    t = _clean_window_title(session["window_title"], session["process_name"])
    return "" if blocklist.blocks(config, session["window_title"]) or blocklist.blocks(config, t) else t


def _span_minutes(data):
    """How long the window sessions in this block cover, for a keys-per-minute
    band when the collector recorded no typing bursts to measure against."""
    sess = data.get("window_sessions") or []
    if not sess:
        return 1.0
    try:
        first = min(float(s.get("start_time") or 0) for s in sess)
        last = max(float(s.get("end_time") or 0) for s in sess)
    except ValueError:
        return 1.0
    return max(1.0, (last - first) / 60.0)


def format_system_activity(data, image_opts, config, t=None):
    """The raw activity a character's account of his machine is written from.

    `t` is the (english, japanese) chooser of whoever is being written for
    (`sim/phone.py:_t`); without one every band renders English, which is what
    a tool reading this block for a developer wants.

    What the machine reports about ITSELF -- how hard he was typing, in what
    shape, how long it has been up -- is banded (`sensors/bands.py`). What
    happened and when is not: a window run keeps the clock it started at and
    how long it ran."""
    parts = []
    t = t or bands._t_default

    stats = data.get("system_stats", {})
    if stats and "error" not in stats:
        # The CPU and RAM percentages went out on every look and nothing but
        # the account-writing role ever read them; what came back was "barely
        # breathing at 0.8% CPU with 36.5% RAM used" in a message to him. A
        # machine labouring is worth a word and a machine idling is not worth
        # a figure.
        parts.append("SYSTEM: " + bands.uptime(config, stats.get("uptime_seconds", 0), t))

        top_procs = [p for p in stats.get("top_processes", [])
                     if not blocklist.hidden(config, p.get("name"))]
        if top_procs:
            # the names, not the percentages: which of these is using 7.6%
            # of a core is a fact about scheduling, and the only reader it
            # ever had was the model that then quoted it
            proc_strs = [p["name"].replace(".exe", "") for p in top_procs[:5]]
            parts.append("TOP: " + ", ".join(proc_strs))

    input_act = data.get("input_activity", {})
    if input_act.get("total_keypresses", 0) > 0 or input_act.get("mouse_clicks", 0) > 0:
        # `1616 keys (alphanumeric:1374, navigation:4, ...)` is the line she
        # read back to him as "キー八個押して". The category breakdown had no
        # reader at all beyond the model. What is worth keeping is the rate,
        # which is what "hammering at something" actually means, and that
        # needs the span the keys happened in rather than the total.
        spans = [(b.get("count", 0), max(0.0, float(b.get("end", 0)) - float(b.get("start", 0))))
                 for b in (input_act.get("typing_bursts") or [])]
        minutes = sum(s for _k, s in spans) / 60.0 if spans else _span_minutes(data)
        said = [x for x in (bands.typing(config, input_act.get("total_keypresses", 0), minutes, t),
                            bands.bursts(config, spans, t),
                            bands.clicks(config, input_act.get("mouse_clicks", 0), t)) if x]
        if said:
            parts.append("INPUT: " + t(", ", "、").join(said))

    sessions = data.get("window_sessions", [])
    if sessions:
        opts = image_opts or {}
        gap_seconds = opts.get("gap_seconds", 5 * 60)
        summarize_min = opts.get("summarize_min", 3)
        max_detailed = opts.get("max_detailed", 6)

        # An image-view session is a JPEGView/IrfanView window with a filename.
        # Group them into bursts; a burst of summarize_min+ collapses to one
        # dated summary, a shorter one keeps full detail, and full detail stops
        # once max_detailed individual images have been spent this look. The
        # first image session of a burst carries the block; the rest are
        # suppressed so a 30-image run is one entry, not thirty.
        def _is_img(s):
            return s.get("is_image_viewer") and s.get("image_filename")

        suppress_old = set()    # windows past max_windows: dropped entirely

        img_sessions = sorted((s for s in sessions if _is_img(s)), key=lambda s: s["start_time"])
        groups = _group_image_windows(img_sessions, gap_seconds)
        # She is glancing at an app, not auditing him. Only image runs from the
        # last max_age_hours are described at all -- anything older is his
        # afternoon, not news -- and then only the most recent max_windows of
        # those, so a heavy burst inside the window is still bounded.
        max_age_hours = opts.get("max_age_hours", 0)
        if max_age_hours:
            cutoff = time.time() - max_age_hours * 3600
            old_groups = [g for g in groups if g[-1].get("end_time", 0) < cutoff]
            for g in old_groups:
                for sess in g:
                    suppress_old.add(id(sess))
            groups = [g for g in groups if g[-1].get("end_time", 0) >= cutoff]
        max_windows = opts.get("max_windows", 0)
        if max_windows and len(groups) > max_windows:
            for g in groups[:-max_windows]:
                for s in g:
                    suppress_old.add(id(s))
            groups = groups[-max_windows:]
        block_for = {}          # id(first session) -> rendered block
        suppress = suppress_old  # id(session) -> hide (covered by its group's block)
        detailed_used = 0
        for g in groups:
            first = id(g[0])
            for s in g[1:]:
                suppress.add(id(s))
            if len(g) < summarize_min and detailed_used + len(g) <= max_detailed:
                block_for[first] = "\n".join(_image_full_detail(s) for s in g)
                detailed_used += len(g)
            else:
                block_for[first] = _summarize_image_window(g)

        # Consecutive windows with the same app and the same cleaned title are
        # one thing he was doing, not N things. This used to emit a line per
        # session, and a terminal repaints its own title about once a second:
        # 53% of every session ever recorded is WindowsTerminal, and a quarter
        # of the phone model's whole budget went on "[15:39] WindowsTerminal
        # (1s)" repeated, while real browsing was truncated off the front to
        # make room for it.
        #
        # Collapsing is not summarising. The duration is summed and the switch
        # count kept, so a collapsed line says strictly MORE than any of the
        # lines it replaces -- "in the terminal for 14 minutes" was never
        # recoverable from four hundred one-second lines.
        #
        # A window carrying something of its own is never merged: an image with
        # a Gelbooru block, or a Chrome tab with a scraped page summary, is a
        # thing to read rather than a switch to count.
        runs = []
        for s in sessions:
            if _is_img(s) and id(s) in suppress:
                continue
            mergeable = not _is_img(s) and not (s.get("is_chrome") and s.get("scrape_data"))
            hide = blocklist.hidden(config, s["process_name"])
            title_now = "" if hide else _shown_title(config, s)
            # every hidden program shares one key, so nine terminal runs in a
            # row are one line of the account rather than nine
            key = ((HIDDEN_WINDOW if hide else s["process_name"]), _merge_key(title_now)) if mergeable else None
            if key is not None and runs and runs[-1]["key"] == key:
                r = runs[-1]
                r["dur"] += s.get("duration_seconds", 0) or 0
                r["count"] += 1
                r["last"] = s
                r["last_title"] = title_now
            else:
                runs.append({"key": key, "first": s, "last": s,
                             "dur": s.get("duration_seconds", 0) or 0, "count": 1,
                             "first_title": title_now, "last_title": title_now})

        parts.append("")
        parts.append("ACTIVE WINDOWS:")
        for r in runs:
            s = r["first"]
            start_str = datetime.datetime.fromtimestamp(s["start_time"]).strftime("%H:%M")
            hide = blocklist.hidden(config, s["process_name"])
            proc_clean = HIDDEN_WINDOW if hide else s["process_name"].replace(".exe", "")
            title_clean = "" if hide else _shown_title(config, s)
            if r["count"] > 1:
                end_str = datetime.datetime.fromtimestamp(r["last"].get("end_time", s["start_time"])).strftime("%H:%M")
                when = f"[{start_str}-{end_str}]" if end_str != start_str else f"[{start_str}]"
                head = f"{when} {proc_clean} ({_fmt_dur(r['dur'])} over {r['count']} windows)"
            else:
                head = f"[{start_str}] {proc_clean} ({_fmt_dur(r['dur'])})"
            # both ends when the numbers moved: a ticker's range is the only
            # part of it worth a line, and it is also what stops two different
            # things that differ by a number from being reported as one
            last_title = r.get("last_title") or ""
            if r["count"] > 1 and last_title and last_title != title_clean:
                title_clean = f"{title_clean} ... {last_title}"
            line = f"{head} {title_clean}" if title_clean else head

            if _is_img(s):
                block = block_for.get(id(s))
                if block is not None:
                    # a full-detail block hangs under the window line; a summary
                    # replaces it (it already states when and how many)
                    if block.lstrip().startswith("["):
                        parts.append(block)
                        continue
                    line += "\n" + block

            if s.get("is_chrome") and s.get("scrape_data"):
                sd = s["scrape_data"]
                if sd.get("summary"):
                    line += f"\n  [PAGE] {sd['summary'][:250]}"

            parts.append(line)

    if not parts:
        return ""

    return "\n".join(parts)