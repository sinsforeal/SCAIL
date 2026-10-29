"""His machine's own collector: one per machine, belonging to neither character.

    python machine\\collector.py                     # forever; talkapp.cmd starts it
    python machine\\collector.py --once              # one poll, print the now file, exit

What it runs is exactly what each bot used to run inside itself: the system
monitor (foreground window, keyboard, mouse, the image viewer, the pictures'
tags, the pages worth scraping) and the telemetry collector (browser history,
media, the notes folder, his anime list), writing `sensors.telemetry_jsonl_path`,
the one feed both characters read. Plus what a bot can no longer read out of
its own memory: `sensors.telemetry_now_path` -- what is in front of him and
when he last touched anything -- every few seconds, and the closed window
sessions of the last day beside it whenever one ends. `machine/monitor_client.py`
reads both. It also answers a bot that is about to build a reply and wants
the buffer on disk now (`sensors.telemetry_flush_request_path`): the file is
checked on every pass of the loop below, so the feed is at worst a few seconds
behind him rather than a heartbeat.

Single instance, by the same lock a bot uses on its save (`singleton.py`): a
second copy exits at once. Logs to logs/machine_collector.log; the run
directories under logs/ belong to the characters.
"""
import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)

import logger  # noqa: E402
from config import Config  # noqa: E402
import atomic  # noqa: E402
from singleton import AlreadyRunning, Singleton  # noqa: E402

MARKER = "collector.py"


def _write_json(path, data):
    atomic.write_json(path, data)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.json", help="the machine's config: sensors and api only")
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()
    c = Config(args.config)
    sv = c.sensor_view
    logger.setup_file(os.path.join(c.logging.out_dir, "machine_collector.log"))
    lock = Singleton(sv.telemetry_now_path + ".lock", marker=MARKER)
    try:
        lock.acquire()
    except AlreadyRunning as e:
        print(f"[machine] {e}; exiting", flush=True)
        return 0
    from llm import LLM
    from sensors import telemetry_collector
    from sensors.system_monitor import SystemMonitor
    llm = LLM(c)
    mon = SystemMonitor(sv)
    if sv.gelbooru_enabled:
        from sensors.gelbooru_classifier import GelbooruClassifier
        mon.set_gelbooru_classifier(GelbooruClassifier(sv))
    if sv.chrome_scrape_enabled:
        from sensors.web_scraper import WebScraper
        mon.set_web_scraper(WebScraper(sv, llm))
    mon.start()
    col = telemetry_collector.TelemetryCollector(sv, system_monitor_instance=mon)
    logger.log(f"[machine] collector up (pid {os.getpid()}): feed {sv.telemetry_jsonl_path}, now {sv.telemetry_now_path}")
    att_path = os.path.splitext(sv.telemetry_now_path)[0] + ".attention.json"
    every = float(sv.telemetry_now_interval_seconds)
    last_key = None
    try:
        while True:
            now = time.time()
            proc, title, in_window, idle = mon.right_now()
            _write_json(sv.telemetry_now_path, {
                "ts": now, "pid": os.getpid(),
                "proc": proc, "title": title, "is_idle": proc is None,
                "window_start": (now - in_window) if proc else None,
                "last_input_ts": now - idle,
            })
            # A bot about to build a reply asks for the buffer by touching a
            # file. The check belongs in this loop because it wakes every few
            # seconds, where the collector's own thread wakes only every
            # sensors.telemetry_poll_interval_seconds.
            try:
                col.check_flush_request()
            except Exception as e:
                logger.log(f"[machine] flush request not served: {type(e).__name__}: {e}")
            # the closed sessions only: the live one is in the now file and the
            # reader appends it, so it is never counted twice
            sessions, _li = mon.attention_since(now - 86400)
            live_start = (now - in_window) if proc else None
            closed = [list(s) for s in sessions
                      if not (live_start is not None and abs(float(s[0]) - live_start) < 1.0)]
            key = (len(closed), closed[-1][1] if closed else 0)
            # An empty list is this process having accumulated nothing yet, not
            # a day with nothing in it: the monitor's session history is in
            # memory and starts empty, so the first pass after a collector
            # restart used to write [] over the stored 24 hours and the bot's
            # reading of how long his machine had been busy lost its ground.
            # Nothing is written until there is something to write.
            if key != last_key and closed:
                _write_json(att_path, closed)
                last_key = key
            if args.once:
                with open(sv.telemetry_now_path, encoding="utf-8") as f:
                    print(f.read())
                break
            time.sleep(every)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            col.force_flush()
            col.stop()
        except Exception:
            pass
        try:
            mon.stop()
        except Exception:
            pass
        lock.release()
        logger.log("[machine] collector down")
    return 0


if __name__ == "__main__":
    sys.exit(main())
