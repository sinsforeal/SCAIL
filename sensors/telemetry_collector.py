import os
import json
import time
import threading
import datetime
import logger
from sensors import chrome_monitor
from sensors import media_monitor
from sensors import vault_monitor
from sensors import system_monitor as sysmon_module
from sensors.mal_monitor import MalMonitor

def get_max_file_id(config):
    path = config.telemetry_jsonl_path
    if not os.path.exists(path):
        return 0
    last_id = 0
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    eid = entry.get("id", 0)
                    if eid > last_id:
                        last_id = eid
                except json.JSONDecodeError:
                    continue
    except:
        pass
    return last_id

class TelemetryCollector:
    def __init__(self, config, system_monitor_instance=None):
        self.config = config
        self.jsonl_path = config.telemetry_jsonl_path
        self.pending_log_path = config.telemetry_pending_log_path
        self.poll_interval = config.telemetry_poll_interval_seconds
        self.heartbeat_interval = config.telemetry_heartbeat_interval_seconds
        self.flush_threshold = config.telemetry_flush_threshold_chars
        self.flush_request_path = config.telemetry_flush_request_path

        self._system_monitor = system_monitor_instance
        self._mal = MalMonitor(config)
        self._mal_text = ""

        self._lock = threading.Lock()
        # One poll-and-write pass at a time. The machine's own loop asks
        # for a flush from another thread, and two threads appending with
        # one id counter would write the same id twice. Reentrant because
        # the on-demand path holds it across the poll and the write.
        self._flush_lock = threading.RLock()
        self._activity_since = time.time()
        self._last_flush_time = time.time()
        self._estimated_chars = 0
        self._has_activity = False
        self._last_chrome_text = ""
        self._last_firefox_text = ""
        self._last_media_text = ""
        self._last_vault_info = []
        self._last_system_activity = {}
        self._entry_id = self._read_last_id()
        self._running = True

        if not os.path.exists(self.jsonl_path):
            with open(self.jsonl_path, 'w', encoding='utf-8') as f:
                pass

        self._write_pending_log()

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.log(f"[TELEMETRY] Collector started. Poll: {self.poll_interval}s | Heartbeat: {self.heartbeat_interval}s | Threshold: {self.flush_threshold} chars")

    def _read_last_id(self):
        return get_max_file_id(self.config)

    def _run_loop(self):
        while self._running:
            try:
                with self._flush_lock:
                    self._poll_sources()
                    self._check_flush()
                    # the sources were just read, so this pass does not read
                    # them again; it only serves a request that is waiting
                    self.check_flush_request(poll_first=False)
                self._write_pending_log()
            except Exception as e:
                logger.log(f"[TELEMETRY ERROR] Poll cycle: {e}")
            time.sleep(self.poll_interval)

    def _poll_sources(self):
        since = self._activity_since

        chrome_text, chrome_count = chrome_monitor.get_history_since(self.config, since)
        media_text = media_monitor.get_media_changes_since(self.config, since)
        vault_info = vault_monitor.get_modified_file_info_since(self.config, since)

        firefox_text = ""
        if self.config.firefox_enabled:
            firefox_text,_ = chrome_monitor.get_firefox_history_since(self.config, since)

        mal_new = self._mal.poll()
        if mal_new:
            self._mal_text = (self._mal_text + "\n" + mal_new).strip()
        mal_eps = self._mal.poll_episodes()
        if mal_eps:
            self._mal_text = (self._mal_text + "\n" + mal_eps).strip()
        mal_notes = self._mal.poll_notes()
        if mal_notes:
            self._mal_text = (self._mal_text + "\n" + mal_notes).strip()

        system_activity = {}
        if self._system_monitor:
            sessions_count, keypresses = self._system_monitor.get_buffer_info()
            system_activity = {"sessions": sessions_count, "keypresses": keypresses}

        estimated = 0
        if chrome_text:
            estimated += len(chrome_text)
        if firefox_text:
            estimated += len(firefox_text)
        if media_text:
            estimated += len(media_text)
        if self._mal_text:
            estimated += len(self._mal_text)
        if vault_info:
            estimated += len(vault_info)* 200
        if system_activity:
            estimated += system_activity.get("sessions", 0) * 150
            estimated += system_activity.get("keypresses", 0)

        with self._lock:
            self._estimated_chars = estimated
            self._has_activity = estimated > 0 or bool(vault_info) or bool(self._mal_text)
            self._last_chrome_text = chrome_text if chrome_text else ""
            self._last_firefox_text = firefox_text if firefox_text else ""
            self._last_media_text = media_text if media_text else ""
            self._last_vault_info = vault_info if vault_info else []
            self._last_system_activity = system_activity

    def _check_flush(self):
        with self._lock:
            has_content = self._has_activity
            over_threshold = self._estimated_chars >= self.flush_threshold

        time_since_flush = time.time() - self._last_flush_time
        heartbeat_due = time_since_flush >= self.heartbeat_interval

        if has_content and (over_threshold or heartbeat_due):
            reason = "threshold" if over_threshold else "heartbeat"
            self._flush(reason)

    def _flush(self, reason):
        with self._flush_lock:
            self._write_entry(reason)

    def _write_entry(self, reason):
        with self._lock:
            chrome_text = self._last_chrome_text
            firefox_text = self._last_firefox_text
            media_text = self._last_media_text
            mal_text = self._mal_text
            vault_info = list(self._last_vault_info)

        sysmon_data = {}
        if self._system_monitor:
            sysmon_data = self._system_monitor.consume_accumulated()

            for sess in sysmon_data.get("window_sessions", []):
                vid = sess.get("read_vault_file")
                if vid and os.path.exists(vid):
                    try:
                        mtime = os.path.getmtime(vid)
                        basename = os.path.basename(vid)
                        if not any(v[0] == vid for v in vault_info):
                            vault_info.append((vid, mtime, basename))
                    except Exception as e:
                        logger.log(f"[TELEMETRY] Error adding read vault file {vid}: {e}")

        self._entry_id += 1
        entry = {
            "id": self._entry_id,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "unix_time": time.time(),
            "flush_reason": reason,
            "chrome_telemetry": chrome_text.strip(),
            "firefox_telemetry": firefox_text.strip(),
            "media_telemetry": media_text.strip(),
            "mal_telemetry": mal_text.strip(),
            "vault_files": [{"path": p, "mtime": m, "basename": b,
                             "excerpt": vault_monitor.tail_excerpt(p, self.config.vault_excerpt_chars)} for p, m, b in vault_info],
            "system_activity": sysmon_data
        }

        with open(self.jsonl_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        self._activity_since = time.time()
        self._last_flush_time = time.time()

        with self._lock:
            self._estimated_chars = 0
            self._has_activity = False
            self._last_chrome_text = ""
            self._last_firefox_text = ""
            self._last_media_text = ""
            self._mal_text = ""
            self._last_vault_info = []
            self._last_system_activity = {}

        sysmon_sessions = len(sysmon_data.get("window_sessions", []))
        logger.log(f"[TELEMETRY] Flushed entry #{self._entry_id} ({reason}). Chrome: {len(chrome_text)} chars | Firefox: {len(firefox_text)} chars | Media: {len(media_text)} chars | Vault: {len(vault_info)} files | SysMon: {sysmon_sessions} sessions")
        self._write_pending_log()

    def _write_pending_log(self):
        with self._lock:
            chars = self._estimated_chars
            has_act = self._has_activity
            chrome = self._last_chrome_text
            firefox = self._last_firefox_text
            media = self._last_media_text
            vault = list(self._last_vault_info)
            sys_act = dict(self._last_system_activity)

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        time_since_flush = time.time() - self._last_flush_time
        time_to_heartbeat = max(0, self.heartbeat_interval - time_since_flush)

        lines = []
        lines.append(f"=== TELEMETRY PENDING BUFFER ===")
        lines.append(f"Last updated: {now}")
        lines.append(f"Accumulating since: {datetime.datetime.fromtimestamp(self._activity_since).strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Estimated buffer size: {chars} chars (threshold: {self.flush_threshold})")
        lines.append(f"Has activity: {has_act}")
        lines.append(f"Time to heartbeat flush: {int(time_to_heartbeat)}s")
        lines.append(f"Next entry ID will be: {self._entry_id + 1}")
        lines.append(f"")
        lines.append(f"--- CHROME BUFFER ---")
        if chrome:
            lines.append(chrome)
        else:
            lines.append("[empty]")
        lines.append(f"")
        lines.append(f"--- FIREFOX BUFFER ---")
        if firefox:
            lines.append(firefox)
        else:
            lines.append("[empty]")
        lines.append(f"")
        lines.append(f"--- MEDIA BUFFER ---")
        if media:
            lines.append(media)
        else:
            lines.append("[empty]")
        lines.append(f"")
        lines.append(f"--- VAULT CHANGES ---")
        if vault:
            for path, mtime, basename in vault:
                dt = datetime.datetime.fromtimestamp(mtime).strftime('%H:%M:%S')
                lines.append(f"  [{dt}] {basename}")
        else:
            lines.append("[empty]")
        lines.append(f"")
        lines.append(f"--- SYSTEM MONITOR ---")
        if sys_act:
            lines.append(f"  Sessions buffered: {sys_act.get('sessions', 0)}")
            lines.append(f"  Keypresses buffered: {sys_act.get('keypresses', 0)}")
        else:
            lines.append("[not active]")
        lines.append(f"")
        lines.append(f"=== END PENDING BUFFER ===")

        try:
            with open(self.pending_log_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(lines))
        except Exception:
            pass

    def check_flush_request(self, poll_first=True):
        """Somebody is about to build a reply: write what is held, now.

        The buffer otherwise reaches the feed on a character count or on the
        heartbeat, so anything he did inside the current window was invisible
        to a reply built during it. A bot touches the request file and this,
        called on every pass of the machine's loop, answers it within a few
        seconds. The sources are re-read first because the collector's own
        poll runs on a slower clock and the browser history of the last half
        minute would otherwise be left out.

        An empty buffer writes no entry and the request is still cleared: the
        ask means "if you have anything", not "write a row". A second request
        that arrives while this one is being served is answered by the same
        entry.
        """
        path = self.flush_request_path
        if not path:
            return False
        try:
            if not os.path.exists(path):
                return False
        except OSError:
            return False
        with self._flush_lock:
            if poll_first:
                try:
                    self._poll_sources()
                except Exception as e:
                    logger.log(f"[TELEMETRY] Sources not re-read for a requested flush: {type(e).__name__}: {e}")
            with self._lock:
                has_content = self._has_activity
            if not has_content and self._system_monitor:
                sessions_count, keypresses = self._system_monitor.get_buffer_info()
                has_content = sessions_count > 0 or keypresses > 0
            wrote = False
            if has_content:
                self._flush("requested")
                wrote = True
            try:
                os.remove(path)
            except FileNotFoundError:
                pass
            except OSError as e:
                logger.log(f"[TELEMETRY] Flush request file not removed: {type(e).__name__}: {e}")
        return wrote

    def force_flush(self):
        with self._lock:
            has_content = self._has_activity
        if has_content:
            self._flush("forced")
        elif self._system_monitor:
            sessions_count, keypresses = self._system_monitor.get_buffer_info()
            if sessions_count > 0 or keypresses > 0:
                self._flush("forced_sysmon")

    def get_buffer_status(self):
        with self._lock:
            return self._estimated_chars, self._has_activity

    def stop(self):
        self._running = False


def consume_new_entries(config, last_consumed_id):
    path = config.telemetry_jsonl_path
    if not os.path.exists(path):
        return [], last_consumed_id

    new_entries = []
    max_id = last_consumed_id

    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    eid = entry.get("id", 0)
                    if eid > last_consumed_id:
                        new_entries.append(entry)
                        if eid > max_id:
                            max_id = eid
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        logger.log(f"[TELEMETRY] Error reading entries: {e}")

    return new_entries, max_id


def merge_entries(entries):
    if not entries:
        return None

    merged = {
        "id": entries[-1]["id"],
        "timestamp": entries[-1]["timestamp"],
        "unix_time": entries[-1]["unix_time"],
        "flush_reason": "merged",
        "chrome_telemetry": "",
        "firefox_telemetry": "",
        "media_telemetry": "",
        "mal_telemetry": "",
        "vault_files": [],
        "system_activity": {
            "window_sessions": [],
            "input_activity": {
                "total_keypresses": 0,
                "categories": {"alphanumeric": 0, "navigation": 0, "function": 0, "modifier": 0, "mute": 0, "vol_down": 0, "vol_up": 0, "media_ctrl": 0, "other": 0},
                "mouse_distance_pixels": 0,
                "mouse_clicks": 0,
                "typing_bursts": []
            },
            "system_stats": {},
            "opened_files": []
        }
    }

    seen_vault_paths = set()
    chrome_parts = []
    firefox_parts = []
    media_parts = []
    mal_parts = []

    for entry in entries:
        mal = entry.get("mal_telemetry", "")
        if mal:
            mal_parts.append(mal)
        ct = entry.get("chrome_telemetry", "")
        if ct:
            chrome_parts.append(ct)
        ft = entry.get("firefox_telemetry", "")
        if ft:
            firefox_parts.append(ft)
        mt = entry.get("media_telemetry", "")
        if mt:
            media_parts.append(mt)
        for vf in entry.get("vault_files", []):
            if vf["path"] not in seen_vault_paths:
                merged["vault_files"].append(vf)
                seen_vault_paths.add(vf["path"])

        sa = entry.get("system_activity", {})
        if sa:
            merged["system_activity"]["window_sessions"].extend(sa.get("window_sessions", []))
            merged["system_activity"]["opened_files"].extend(sa.get("opened_files", []))

            entry_input = sa.get("input_activity", {})
            if entry_input:
                merged["system_activity"]["input_activity"]["total_keypresses"] += entry_input.get("total_keypresses", 0)
                merged["system_activity"]["input_activity"]["mouse_distance_pixels"] += entry_input.get("mouse_distance_pixels", 0)
                merged["system_activity"]["input_activity"]["mouse_clicks"] += entry_input.get("mouse_clicks", 0)
                merged["system_activity"]["input_activity"]["typing_bursts"].extend(entry_input.get("typing_bursts", []))
                for cat, count in entry_input.get("categories", {}).items():
                    if cat in merged["system_activity"]["input_activity"]["categories"]:
                        merged["system_activity"]["input_activity"]["categories"][cat] += count

            entry_stats = sa.get("system_stats", {})
            if entry_stats:
                merged["system_activity"]["system_stats"] = entry_stats

    merged["chrome_telemetry"] = "\n".join(chrome_parts)
    merged["firefox_telemetry"] = "\n".join(firefox_parts)
    merged["media_telemetry"] = "\n".join(media_parts)
    merged["mal_telemetry"] = "\n".join(mal_parts)

    return merged


def format_telemetry_for_context(entry, image_opts, config, t=None):
    parts = [f"LOCAL TIME: {entry['timestamp']}"]

    sa = entry.get("system_activity", {})
    if sa:
        sysmon_text = sysmon_module.format_system_activity(sa, image_opts, config, t)
        if sysmon_text:
            parts.append(sysmon_text)

    chrome = entry.get("chrome_telemetry", "")
    if chrome:
        parts.append(chrome)

    firefox = entry.get("firefox_telemetry", "")
    if firefox:
        parts.append(firefox)

    media = entry.get("media_telemetry", "")
    if media:
        parts.append(media)

    mal = entry.get("mal_telemetry", "")
    if mal:
        parts.append(mal)

    vault_files = entry.get("vault_files", [])
    if vault_files:
        v_parts = ["HIS NOTES FOLDER (files he edited or had open; the end of each note is shown, that is what he was writing):"]
        for v in vault_files:
            ex = (v.get("excerpt") or "").strip()
            if ex:
                v_parts.append(f"- {v['basename']}:\n  " + ex.replace("\n", "\n  "))
            else:
                v_parts.append(f"- {v['basename']}")
        parts.append("\n".join(v_parts))

    return "\n\n".join(parts)