"""What Japan is talking about right now, filtered to what would reach her.

The entity floats free of the actual world unless the world keeps arriving:
the calendar has the season and her wards' festivals, the hazards feed has
the ground and the sky, and nothing had the rest -- what is on the news,
what is trending, what somebody her age in her part of the city would have
seen on her phone today. This pulls public Japanese feeds (no auth, no scraping beyond
RSS) plus the X trends the look session already saw, and one small model
call reads the pile the way her demographic would: most of it does not
reach her at all, some of it is everywhere, a little of it is exactly her.

    python tools/zeitgeist.py [--config config_<key>.json] fetch [--limit 80]
    python tools/zeitgeist.py [--config config_<key>.json] report

**Which character this is for is an argument, and the paths follow from her
config.** The filtering is hers all the way down: how she is described to the
role that judges the headlines (`sim/observer.py`), her declared taste, her
calendar, her model, and how many days and headlines she keeps. This took no
argument and loaded `config.json`, so when a second character in the same
world ran it -- her own loop, her own four-hour tick -- the feed came back
judged in the FIRST character's terms, was written to the first character's
file, consumed the shared seen-set so those headlines would never be offered
to the first character again, and left the file her own config names empty.
The reader is `world.zeitgeist_file`; what has already been offered is a list
beside it, so each character has her own.

Feeds rot (the Yahoo RSS paths for trains all went 404); a dead feed is
logged and skipped, never fatal.
"""
import argparse
import json
import os
import re
import sys
import time
import datetime
import xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import atomic  # noqa: E402
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import requests
from config import Config
from llm import LLM
from sim import observer

# Where this character's feed and her own list of what has been offered live.
# Both come from her config; the fallbacks are what the paths were when there
# was one character. `paths_for` is the one place either is decided.
OUT = "data/zeitgeist.json"
SEEN = "data/zeitgeist_seen.json"
# The trends tab as the machine last saw it: public names, one harvest, read
# by whoever asks. It is not a person's file and is not keyed to one.
TRENDS = "data/x/trends.json"


def paths_for(cfg):
    """(the feed she reads, the list of what she has already been offered).

    The feed is `world.zeitgeist_file` -- the same key the reader in her
    process opens -- and the offered list sits beside it under the same stem,
    so a character's own directory holds both and no two characters share
    either."""
    out = str(getattr(cfg.world, "zeitgeist_file", "") or OUT)
    stem, ext = os.path.splitext(out)
    return out, stem + "_seen" + (ext or ".json")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36",
      "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
      "Accept-Language": "ja,en;q=0.8"}

# Public RSS. Each entry: name, url, and a budget of newest items to take.
SOURCES = [
    {"name": "NHK 主要", "url": "https://www.nhk.or.jp/rss/news/cat0.xml", "budget": 12},
    {"name": "NHK 社会", "url": "https://www.nhk.or.jp/rss/news/cat1.xml", "budget": 8},
    {"name": "NHK 文化・エンタメ", "url": "https://www.nhk.or.jp/rss/news/cat2.xml", "budget": 8},
    {"name": "NHK スポーツ", "url": "https://www.nhk.or.jp/rss/news/cat7.xml", "budget": 5},
    {"name": "Yahoo トピックス", "url": "https://news.yahoo.co.jp/rss/topics/top-picks.xml", "budget": 10},
    {"name": "Yahoo エンタメ", "url": "https://news.yahoo.co.jp/rss/topics/entertainment.xml", "budget": 10},
    {"name": "Yahoo 地域", "url": "https://news.yahoo.co.jp/rss/topics/local.xml", "budget": 6},
    {"name": "livedoor トップ", "url": "https://news.livedoor.com/topics/rss/top.xml", "budget": 8},
    {"name": "livedoor エンタメ", "url": "https://news.livedoor.com/topics/rss/ent.xml", "budget": 8},
    {"name": "コミックナタリー", "url": "https://natalie.mu/comic/feed/news", "budget": 10},
    {"name": "音楽ナタリー", "url": "https://natalie.mu/music/feed/news", "budget": 10},
    {"name": "映画ナタリー", "url": "https://natalie.mu/eiga/feed/news", "budget": 6},
    {"name": "アニメ！アニメ！", "url": "https://animeanime.jp/rss20/index.rdf", "budget": 10},
    {"name": "モデルプレス", "url": "https://mdpr.jp/rss", "budget": 10},
]


def _load(path, default):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def _save(path, data):
    atomic.write_json(path, data, indent=2)


def _text(el):
    return re.sub(r"\s+", " ", (el.text or "")).strip() if el is not None else ""


def feed_items(url, log=print):
    """(title, description, link) newest first; tolerant of RSS 2.0, RSS 1.0 and Atom."""
    try:
        r = requests.get(url, headers=UA, timeout=20)
        r.raise_for_status()
    except Exception as e:
        log(f"  ! {url}: {type(e).__name__}: {str(e)[:80]}")
        return []
    try:
        root = ET.fromstring(r.content)
    except ET.ParseError:
        # a feed with a stray control character in it (mdpr.jp) still has
        # its titles; take them by regex rather than lose the source
        body = r.content.decode("utf-8", "replace")
        out = []
        for m in re.finditer(r"<item>(.*?)</item>", body, re.S):
            blk = m.group(1)
            t = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", blk, re.S)
            l = re.search(r"<link>(.*?)</link>", blk, re.S)
            d = re.search(r"<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>", blk, re.S)
            if t:
                out.append((re.sub(r"\s+", " ", t.group(1)).strip(), re.sub(r"<[^>]+>", "", d.group(1))[:200].strip() if d else "", l.group(1).strip() if l else ""))
        log(f"  ~ {url}: parsed loosely, {len(out)} item(s)")
        return out
    out = []
    for item in root.iter():
        tag = item.tag.split("}")[-1]
        if tag not in ("item", "entry"):
            continue
        title = desc = link = ""
        for ch in item:
            t = ch.tag.split("}")[-1]
            if t == "title":
                title = _text(ch)
            elif t in ("description", "summary", "content"):
                desc = re.sub(r"<[^>]+>", "", _text(ch))[:200]
            elif t == "link":
                link = _text(ch) or ch.get("href", "")
        if title:
            out.append((title, desc, link))
    return out


def gather(limit, log=print, seen_path=SEEN):
    seen = set(_load(seen_path, []))
    rows = []
    alive = 0
    for src in SOURCES:
        items = feed_items(src["url"], log)
        if items:
            alive += 1
        n = 0
        for title, desc, link in items:
            key = title[:80]
            if key in seen or n >= src["budget"]:
                continue
            rows.append({"source": src["name"], "title": title, "desc": desc, "link": link, "key": key})
            n += 1
    log(f"looked at {len(SOURCES)} feed(s), {alive} alive, {len(rows)} new headline(s)")
    trends = _load(TRENDS, {})
    tr = []
    if trends and time.time() - float(trends.get("at", 0)) < 12 * 3600:
        tr = [t for t in trends.get("trends", []) if t][:25]
    return rows[:limit], tr


def her_sheet(cfg):
    """Her declared taste (data/taste.json, his to edit) as a block."""
    t = _load(cfg.world.taste_file, {})
    parts = []
    for k in ("loves", "likes", "tolerates", "avoids"):
        v = t.get(k)
        if v:
            parts.append(f"{k}: " + "; ".join(v) if isinstance(v, list) else f"{k}: {v}")
    return "\n".join(parts) or "(no taste sheet)"


def filter_call(cfg, llm, rows, trends, log=print):
    from world.calendar import Calendar
    from world import rails
    cal = Calendar(cfg)
    today = datetime.date.today()
    head = "\n".join(f"[{i}] ({r['source']}) {r['title']}" + (f" -- {r['desc'][:120]}" if r["desc"] else "") for i, r in enumerate(rows))
    tr = ", ".join(trends) if trends else "(none seen)"
    # What she is like, as an observer wrote it, never her own character
    # sheet: this role decides which headlines would reach her at all and
    # must not think it is her (`sim/observer.py`, his call 2026-09-05).
    note = observer.block(cfg, llm, None)
    # Where she actually gets on a train. Without it the role was inventing a
    # commute to make a travel story relevant, because it had her taste sheet
    # and the date and nothing at all about her railway (`world/rails.py`).
    travel = rails.block(cfg)
    user = (
        (note + "\n\n" if note else "")
        + f"DATE: {cal.describe(today)}\n\n"
        + (travel + "\n\n" if travel else "")
        + f"HER TASTE SHEET (declared; what she is into and what she is not):\n{her_sheet(cfg)}\n\n"
        f"TRENDING ON X IN JAPAN TODAY (what the trends tab showed, in order): {tr}\n\n"
        f"HEADLINES (Japanese public feeds, newest first, index in brackets):\n{head}\n"
    )
    system = cfg.role_system("zeitgeist")
    data, raw = llm.call_json("zeitgeist", [{"role": "system", "content": system}, {"role": "user", "content": user}])
    if not isinstance(data, dict):
        log("  ! filter call returned nothing usable")
        return []
    out = []
    for it in (data.get("items") or [])[:cfg.world.zeitgeist_max_per_fetch]:
        if not isinstance(it, dict):
            continue
        try:
            idx = int(it.get("index", -1))
        except (TypeError, ValueError):
            idx = -1
        src = rows[idx] if 0 <= idx < len(rows) else {}
        reach = str(it.get("reach", "")).strip().lower()
        if reach not in ("everyone", "her feed", "niche"):
            continue
        try:
            days = max(1, min(14, int(it.get("days", 3))))
        except (TypeError, ValueError):
            days = 3
        # Why it reaches her, checked against her own railway and dropped when
        # it names one she does not ride. Flagged, never rewritten: the story
        # was true and only the reason was invented, so the item stays and
        # goes in front of her with no reason attached rather than with a
        # commute she has not got.
        hook = str(it.get("hook", ""))[:160]
        bad = rails.refuse(hook, cfg)
        if bad:
            log(f"  ! reason dropped, {bad[0]}: {bad[1]} -- {hook}")
            hook = ""
        out.append({
            "date": today.isoformat(),
            "ja": str(it.get("ja", "") or src.get("title", ""))[:120],
            "text": str(it.get("text", ""))[:160],
            "reach": reach,
            "hook": hook,
            "kind": str(it.get("kind", ""))[:24],
            "days": days,
            "source": src.get("source", "") or ("X trends" if it.get("trend") else ""),
            "link": src.get("link", ""),
        })
    return out


def cmd_fetch(args):
    cfg = Config(args.config)
    out, seen_path = paths_for(cfg)
    print(f"for {args.config} -> {out}")
    llm = LLM(cfg)
    rows, trends = gather(args.limit, log=print, seen_path=seen_path)
    if not rows and not trends:
        print("nothing new")
        return
    items = filter_call(cfg, llm, rows, trends)
    data = _load(out, {"items": []})
    cutoff = (datetime.date.today() - datetime.timedelta(days=cfg.world.zeitgeist_days)).isoformat()
    kept = [i for i in data.get("items", []) if i.get("date", "") >= cutoff]
    have = {i["ja"][:40] for i in kept}
    added = 0
    for it in items:
        if it["ja"][:40] in have:
            continue
        kept.append(it)
        added += 1
        print(f"  + [{it['reach']}] {it['ja'][:70]} -- {it['hook'][:80]}")
    data = {"updated": time.time(), "items": kept[-cfg.world.zeitgeist_keep:]}
    _save(out, data)
    seen = set(_load(seen_path, []))
    seen.update(r["key"] for r in rows)
    _save(seen_path, sorted(seen)[-4000:])
    print(f"kept {added} of {len(rows)} headline(s) + {len(trends)} trend(s); {len(data['items'])} current")


def cmd_report(args):
    data = _load(paths_for(Config(args.config))[0], {"items": []})
    for it in data.get("items", []):
        print(f"{it['date']} [{it['reach']:8s}] {it['ja'][:60]} | {it['text'][:70]} | {it['hook'][:70]}")
    print(f"{len(data.get('items', []))} item(s); updated {datetime.datetime.fromtimestamp(data.get('updated', 0)):%Y-%m-%d %H:%M}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    # whose feed this is. The judging is per character, so the argument is
    # not a convenience: without it every character wrote the first one's file
    ap.add_argument("--config", default="config.json",
                    help="the character this fetch is for; her world.zeitgeist_file is written")
    sub = ap.add_subparsers(dest="cmd")
    f = sub.add_parser("fetch")
    f.add_argument("--limit", type=int, default=80)
    sub.add_parser("report")
    a = ap.parse_args()
    if a.cmd == "fetch":
        cmd_fetch(a)
    else:
        cmd_report(a)
