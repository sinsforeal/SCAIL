import os
import glob
import time
import datetime

# His torrent downloads, read straight from qBittorrent's on-disk state
# (%LOCALAPPDATA%/qBittorrent/BT_backup: a .fastresume per torrent with the
# added/completed times, a .torrent beside it with the name and size). No Web
# UI, no credentials, works whether or not the client is running; read-only.
# This is what she finds when she snoops: what he lined up, and when --
# often a show appears here days before its first episode shows on his list.
# 


def _bdecode(b, i=0):
    c = b[i:i + 1]
    if c == b"i":
        j = b.index(b"e", i)
        return int(b[i + 1:j]), j + 1
    if c == b"l":
        i += 1
        out = []
        while b[i:i + 1] != b"e":
            v, i = _bdecode(b, i)
            out.append(v)
        return out, i + 1
    if c == b"d":
        i += 1
        out = {}
        while b[i:i + 1] != b"e":
            k, i = _bdecode(b, i)
            v, i = _bdecode(b, i)
            out[k] = v
        return out, i + 1
    j = b.index(b":", i)
    n = int(b[i:j])
    return b[j + 1:j + 1 + n], j + 1 + n


def _s(x):
    return (x or b"").decode("utf-8", "replace") if isinstance(x, bytes) else str(x or "")


def backup_dir(config=None):
    d = getattr(config, "torrent_backup_dir", "") if config is not None else ""
    if d:
        return os.path.expandvars(d)
    return os.path.expandvars(r"%LOCALAPPDATA%\qBittorrent\BT_backup")


def recent(config=None, days=7, limit=25):
    """Torrents added in the last `days`, newest first:
    [{name, added_ts, completed_ts, size_bytes, files, done, category}]."""
    bt = backup_dir(config)
    if not os.path.isdir(bt):
        return []
    since = time.time() - days * 86400
    rows = []
    for f in glob.glob(os.path.join(bt, "*.fastresume")):
        # cheap pre-filter: a fastresume not touched since the window started
        # can still hold an old added_time, but a recently added torrent is
        # always recently written, so skip old files
        try:
            if os.path.getmtime(f) < since - 30 * 86400:
                continue
            d, _ = _bdecode(open(f, "rb").read())
        except Exception:
            continue
        added = int(d.get(b"added_time", 0) or 0)
        if added < since:
            continue
        h = os.path.basename(f)[:-11]
        name, nfiles, size = _s(d.get(b"qBt-name")), 0, 0
        tf = os.path.join(bt, h + ".torrent")
        if os.path.exists(tf):
            try:
                t, _ = _bdecode(open(tf, "rb").read())
                info = t.get(b"info", {})
                name = name or _s(info.get(b"name.utf-8") or info.get(b"name"))
                if b"files" in info:
                    nfiles = len(info[b"files"])
                    size = sum(int(x.get(b"length", 0)) for x in info[b"files"])
                else:
                    nfiles = 1
                    size = int(info.get(b"length", 0) or 0)
            except Exception:
                pass
        rows.append({
            "name": name or h[:12], "added_ts": added,
            "completed_ts": int(d.get(b"completed_time", 0) or 0),
            "size_bytes": size, "files": nfiles,
            "done": bool(d.get(b"completed_time", 0)),
            "category": _s(d.get(b"qBt-category")),
        })
    rows.sort(key=lambda r: -r["added_ts"])
    return rows[:limit]


def _gb(n):
    return f"{n / 1e9:.1f} GB" if n >= 1e8 else f"{n / 1e6:.0f} MB" if n else "?"


def describe(rows, tz=None):
    """Plain lines for her to skim, newest first:
    '- Tue 08-18 18:55  Example Show batch (9.9 GB, 36 files, finished 19:20)'."""
    out = []
    for r in rows:
        a = datetime.datetime.fromtimestamp(r["added_ts"], tz)
        line = f"- {a.strftime('%a %m-%d %H:%M')}  {r['name'][:90]} ({_gb(r['size_bytes'])}"
        if r["files"] > 1:
            line += f", {r['files']} files"
        if r["done"]:
            c = datetime.datetime.fromtimestamp(r["completed_ts"], tz)
            line += f", finished {c.strftime('%H:%M') if c.date() == a.date() else c.strftime('%m-%d %H:%M')}"
        else:
            line += ", still downloading"
        out.append(line + ")")
    return "\n".join(out)
