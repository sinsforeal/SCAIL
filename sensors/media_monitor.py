import os
import subprocess
import time
from pathlib import Path
import pythoncom
import win32com.client
from datetime import datetime

try:
    import win32gui
    import win32process
    import psutil
except ImportError:
    win32gui = None
    win32process = None
    psutil = None

_audacious_history = []


def get_media_changes_since(config, activity_since):
    global _audacious_history

    current_tracks = _get_audacious_current(config)
    now = time.time()
    for track in current_tracks:
        if not _audacious_history or _audacious_history[-1][1] != track:
            _audacious_history.append((now, track))

    recent_audacious = [(ts, trk) for ts, trk in _audacious_history if ts >= activity_since]

    recent_images =_get_recent_images(activity_since)
    recent_vids = _get_recent_mpv(activity_since)

    if not recent_images and not recent_vids and not recent_audacious:
        return ""

    output = "MEDIA ACTIVITY:\n"

    if recent_images:
        output += "Recently Opened Images:\n"
        for ts, path in recent_images:
            dt_str = datetime.fromtimestamp(ts).strftime('%H:%M:%S')
            filename = Path(path).name
            output += f"[{dt_str}] Viewed Image: {filename}\n"

    if recent_vids:
        output += "\nRecently Opened Video/Audio (MPV):\n"
        for ts, path in recent_vids:
            dt_str = datetime.fromtimestamp(ts).strftime('%H:%M:%S')
            filename = Path(path).name
            output += f"[{dt_str}] Played Media: {filename}\n"

    if recent_audacious:
        output += "\nAudacious History:\n"
        for ts, track in recent_audacious:
            dt_str = datetime.fromtimestamp(ts).strftime('%H:%M:%S')
            output += f"[{dt_str}] Played: {track}\n"

    return output.strip()


def _get_recent_images(activity_since):
    appdata = os.getenv('APPDATA')
    if not appdata:
        return []

    recent_dir = Path(appdata) / 'Microsoft' / 'Windows' / 'Recent'
    image_exts = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff'}
    recent_images = []

    pythoncom.CoInitialize()
    shell = None
    try:
        shell = win32com.client.Dispatch("WScript.Shell")
        for lnk_file in recent_dir.glob('*.lnk'):
            try:
                mtime = lnk_file.stat().st_mtime
                if mtime >= activity_since:
                    shortcut = shell.CreateShortCut(str(lnk_file))
                    target = shortcut.Targetpath
                    if Path(target).suffix.lower() in image_exts:
                        recent_images.append((mtime, target))
                    del shortcut
            except Exception:
                continue
    finally:
        if shell:
            del shell
        pythoncom.CoUninitialize()

    recent_images.sort(key=lambda x: x[0])
    return recent_images


def _get_recent_mpv(activity_since):
    appdata = os.getenv('APPDATA')
    if not appdata:
        return []

    log_file = Path(appdata) / 'mpv' / 'mpv_history.log'
    if not log_file.exists():
        return []

    recent_vids = []
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for line in lines:
            parts = line.strip().split('|', 1)
            if len(parts) == 2:
                ts = float(parts[0])
                if ts >= activity_since:
                    recent_vids.append((ts, parts[1]))
    except Exception:
        pass

    return recent_vids


def _get_audacious_current(config):
    if not win32gui or not psutil:
        return []

    audacious_names = [p.lower() for p in config.audacious_process_names]
    if not audacious_names:
        return []

    tracks = []

    def _enum_callback(hwnd, results):
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
            try:
                proc = psutil.Process(pid)
                proc_name = proc.name().lower()
                exe_path = proc.exe()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                return

            if proc_name in audacious_names:
                title = win32gui.GetWindowText(hwnd)
                if title and title.strip() and title.lower() != "audacious":
                    status = ""
                    try:
                        if exe_path:
                            audtool_path = Path(exe_path).parent / "audtool.exe"
                            if audtool_path.exists():
                                res = subprocess.run(
                                    [str(audtool_path), "playback-status"],
                                    capture_output=True,
                                    text=True,
                                    errors="replace",
                                    timeout=2,
                                    creationflags=subprocess.CREATE_NO_WINDOW
                                )
                                status = res.stdout.strip().lower()
                    except Exception:
                        pass

                    if status == "stopped":
                        return

                    cleaned =_clean_audacious_title(title)
                    if cleaned:
                        if status == "paused":
                            cleaned = f"{cleaned} [PAUSED]"
                        results.append(cleaned)
        except Exception:
            pass

    found_titles = []
    try:
        win32gui.EnumWindows(_enum_callback, found_titles)
    except Exception:
        pass

    seen = set()
    for title in found_titles:
        if title not in seen:
            tracks.append(title)
            seen.add(title)

    return tracks


def _clean_audacious_title(title):
    if not title:
        return ""
    if " - Audacious" in title:
        title = title.rsplit(" - Audacious", 1)[0].strip()
    if title.lower() == "audacious":
        return ""
    return title