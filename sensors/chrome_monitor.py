import os
import sqlite3
import shutil
import tempfile
import datetime
from urllib.parse import urlsplit
import logger
from sensors import blocklist


def _host(url):
    """The bare host of a URL, no scheme/www/port, for the browsing log.
    Kept short on purpose: she sees where he was, not the full querystring."""
    try:
        h = urlsplit(url).hostname or ""
    except Exception:
        return ""
    if h.startswith("www."):
        h = h[4:]
    return h


# One copy per change, one temp file per process. Two bots each copying the
# 180 MB history into ONE temp path every thirty seconds drifted into the same
# second at 02:52 on 2026-09-03 and blinded both for the rest of the night;
# and Chrome rewrites the file on every visit, so an unchanged file has nothing
# new in it and a copy of it is 180 MB of disk for nothing.
_CACHE = {}


def _cached(kind, paths, since_timestamp, compute):
    """`paths` is every file the answer depends on. Firefox keeps its history
    in write-ahead-log mode: places.sqlite only moves at a checkpoint, while
    the log beside it moves on every visit, so a key built on the main file
    alone hands back an answer that is minutes old for as long as Firefox
    goes without one. Chrome passes its one file and is unaffected."""
    stamps = []
    for p in paths:
        try:
            st = os.stat(p)
        except OSError:
            continue
        stamps.append((p, st.st_mtime_ns, st.st_size))
    key = (tuple(stamps), since_timestamp) if stamps else None
    if key is not None and _CACHE.get(kind + "_key") == key:
        return _CACHE[kind + "_value"]
    value = compute()
    if key is not None:
        _CACHE[kind + "_key"] = key
        _CACHE[kind + "_value"] = value
    return value


def get_history_since(config, since_timestamp):
    return _cached("chrome", [config.chrome_history_path], since_timestamp,
                   lambda: _chrome_history_since(config, since_timestamp))


def _chrome_history_since(config, since_timestamp):
    history_path = config.chrome_history_path
    if not os.path.exists(history_path):
        return "", 0

    temp_db_path = os.path.join(tempfile.gettempdir(), f"scail_chrome_{os.getpid()}.sqlite")
    conn = None
    try:
        shutil.copy2(history_path, temp_db_path)
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        webkit_since = (since_timestamp + 11644473600.0)* 1000000.0
        query = "SELECT url, title, last_visit_time FROM urls WHERE last_visit_time > ? ORDER BY last_visit_time DESC"
        cursor.execute(query, (webkit_since,))
        rows = cursor.fetchall()
    except Exception as e:
        logger.log(f"[CHROME ERROR] SQLite extraction failed: {e}")
        return "", 0
    finally:
        # the connection has to go before the file can. A torn copy of a live
        # history raises inside execute(), and closing in the except branch was
        # too late: the open handle made os.remove fail with WinError 32, and
        # that second exception escaped the poll entirely, so one transient
        # came back every thirty seconds for the life of the process.
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        try:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)
        except OSError:
            pass

    parsed_visits = []
    seen_titles = set()

    for row in rows:
        url, title, raw_time = row
        if not title or not title.strip() or any(j in url.lower() for j in config.chrome_junk_filters):
            continue
        # The junk filters work on the address; a page title carries a name of
        # its own and reaches her as prose. A search whose query was a path
        # put his project's name in her digest on 2026-09-04 from a
        # google.com address that no filter names. Dropped, not blanked: a
        # visit with no title is not a visit.
        if blocklist.blocks(config, title):
            continue

        unix_time = (raw_time / 1000000.0) - 11644473600.0
        dt = datetime.datetime.fromtimestamp(unix_time)

        if title not in seen_titles:
            parsed_visits.append({"url": url, "title": title.strip(), "dt": dt})
            seen_titles.add(title)

    if not parsed_visits:
        return "", 0

    parsed_visits.reverse()

    raw_output = "CHROME ACTIVE BROWSING LOG:\n"
    for i in range(len(parsed_visits)):
        v = parsed_visits[i]
        _h = _host(v['url'])
        raw_output += f"[{v['dt'].strftime('%H:%M:%S')}] {v['title']}" + (f"  ({_h})" if _h else "") + "\n"

        if i < len(parsed_visits) - 1:
            next_v = parsed_visits[i + 1]
            diff_mins = int((next_v['dt'] - v['dt']).total_seconds() / 60)
            if diff_mins > config.chrome_idle_gap_threshold_minutes:
                raw_output += f"   --- [ IDLE GAP DETECTED: {diff_mins} minutes ] ---\n"

    return raw_output, len(parsed_visits)


def get_24h_history_raw(config):
    since = datetime.datetime.now().timestamp() - 86400
    res, _= get_history_since(config, since)
    return res


def get_firefox_history_since(config, since_timestamp):
    path = config.firefox_history_path or ""
    return _cached("firefox", [path, path + "-wal"] if path else [], since_timestamp,
                   lambda: _firefox_history_since(config, since_timestamp))


def _firefox_history_since(config, since_timestamp):
    history_path = config.firefox_history_path
    if not history_path or not os.path.exists(history_path):
        return "", 0

    temp_db_path = os.path.join(tempfile.gettempdir(), f"scail_firefox_{os.getpid()}.sqlite")
    # Firefox holds places.sqlite in write-ahead-log mode and only folds the
    # log into the main file at a checkpoint, so the main file on its own is
    # behind by however long it has been since the last one -- seventeen
    # minutes and four visits when this was measured. Copying the log and its
    # shared-memory index beside it lets SQLite recover them into the copy.
    sidecars = ("-wal", "-shm")
    conn = None
    try:
        shutil.copy2(history_path, temp_db_path)
        for suffix in sidecars:
            side = history_path + suffix
            if os.path.exists(side):
                shutil.copy2(side, temp_db_path + suffix)
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        # Firefox stores visit_date as microseconds since Unix epoch
        ff_since = int(since_timestamp *1000000)
        query = """
            SELECT p.url, p.title, h.visit_date
            FROM moz_historyvisits h
            JOIN moz_places p ON h.place_id = p.id
            WHERE h.visit_date > ?
            ORDER BY h.visit_date DESC
        """
        cursor.execute(query, (ff_since,))
        rows = cursor.fetchall()
    except Exception as e:
        logger.log(f"[FIREFOX ERROR] SQLite extraction failed: {e}")
        return "", 0
    finally:
        # the connection has to go before the file can. A torn copy of a live
        # history raises inside execute(), and closing in the except branch was
        # too late: the open handle made os.remove fail with WinError 32, and
        # that second exception escaped the poll entirely, so one transient
        # came back every thirty seconds for the life of the process.
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        # all three, or the next process opens its fresh copy against the
        # log this one left behind
        for leftover in (temp_db_path,) + tuple(temp_db_path + x for x in sidecars):
            try:
                if os.path.exists(leftover):
                    os.remove(leftover)
            except OSError:
                pass

    parsed_visits = []
    seen_titles = set()

    junk_filters = config.chrome_junk_filters + config.firefox_junk_filters

    for row in rows:
        url, title, visit_date = row
        if not title or not title.strip() or any(j in url.lower() for j in junk_filters):
            continue
        if blocklist.blocks(config, title):
            continue

        unix_time = visit_date / 1000000.0
        dt = datetime.datetime.fromtimestamp(unix_time)

        if title not in seen_titles:
            parsed_visits.append({"url": url, "title": title.strip(), "dt": dt})
            seen_titles.add(title)

    if not parsed_visits:
        return "", 0

    parsed_visits.reverse()

    raw_output = "FIREFOX ACTIVE BROWSING LOG:\n"
    for i in range(len(parsed_visits)):
        v = parsed_visits[i]
        _h = _host(v['url'])
        raw_output += f"[{v['dt'].strftime('%H:%M:%S')}] {v['title']}" + (f"  ({_h})" if _h else "") + "\n"

        if i < len(parsed_visits) - 1:
            next_v = parsed_visits[i + 1]
            diff_mins = int((next_v['dt'] - v['dt']).total_seconds() / 60)
            if diff_mins > config.chrome_idle_gap_threshold_minutes:
                raw_output += f"   --- [ IDLE GAP DETECTED: {diff_mins} minutes ] ---\n"

    return raw_output, len(parsed_visits)


def get_firefox_24h_history_raw(config):
    since = datetime.datetime.now().timestamp() - 86400
    res,_ = get_firefox_history_since(config, since)
    return res