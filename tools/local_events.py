"""Find real events in her actual wards and put them in her calendar.

`data/school_calendar.json` is hand-written: her school year, the national
run of seasons, and the local fixtures worth writing down once. This is the
other half -- what her ward is actually doing this month, discovered rather
than authored, so a fireworks night or a shrine festival can appear in her
life the way it appears in a real teenager's: because it is on.

Sources are the wards' own feeds, which is why this can be trusted. Which
wards, and how near a place has to be to be part of her life, are in HER OWN
MAP under `local_events` (`world.geography_file`): they were a list in this
file until 2026-09-07, of one character's two wards, in a tool a second
character's process has already run.

A feed gives an announcement, not an event: the pubDate is when the ward
posted it and the actual date is in the page. So each new item's page is
fetched and one small model call reads it for (a) whether this would touch
her life at all -- most ward business does not -- and (b) when it actually
happens. Everything kept carries its source URL.

    python tools/local_events.py [--config config_<key>.json] fetch [--limit 12] [--all]
    python tools/local_events.py [--config config_<key>.json] report

Written to `world.local_events_file`, which world/calendar.py merges with the
hand-written calendar. The hand-written file is never touched.

**What a ward has announced is the WORLD's, not a person's**, so two
characters in one world name one file and it has one writer: the character
whose config says she owns the world fetches, and everybody else in it reads
what she wrote (`docs/shared-world.md`). The config is an argument because
this hardcoded `config.json` and the output path both, so run for anybody
else it read the wrong calendar and wrote over the first character's file.
"""
import argparse
import io
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import atomic  # noqa: E402

import requests

from config import Config
from llm import LLM

# The fallbacks are what these were when there was one character; the live
# answer comes from her config through `paths_for`.
OUT = "data/local_events.json"
SEEN = "data/local_events_seen.json"


def paths_for(cfg):
    """(the file the calendar merges, the list of pages already read). The
    first is `world.local_events_file`, the same key the calendar opens; the
    second sits beside it under the same stem."""
    out = str(getattr(cfg.world, "local_events_file", "") or OUT)
    stem, ext = os.path.splitext(out)
    return out, stem + "_seen" + (ext or ".json")

# Where this part of the city announces what is on: her own map's
# `local_events.sources` block (`world.geography_file`). It used to be a list
# here, of the first character's two wards and their feeds, in a tool a second
# character's process has already run.
#
# kind "rss": an announcement feed. kind "links": a listing page, from which
# detail pages matching `pattern` are followed. The listings are what carry
# fireworks and festivals; the ward feeds never do, because a bon odori is run
# by a shrine and a hanabi by a committee, and neither writes a press release.
# kind "page": ONE page that lists MANY events -- the neighbourhood committee
# layer, and the only place her own festivals exist.
def neighbourhood(cfg):
    """Her map's `local_events` block, or {} for a character whose map has
    none: then there is nothing to fetch and nothing to judge against."""
    path = str(getattr(cfg.world, "geography_file", "") or "")
    if not path or not os.path.exists(path):
        return {}
    try:
        with io.open(path, encoding="utf-8") as fh:
            return json.load(fh).get("local_events") or {}
    except (OSError, ValueError):
        return {}

PAGES = "data/local_events_pages.json"

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def _load(path, default):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def _save(path, data):
    atomic.write_json(path, data, indent=2)


def feed_items(url, log=print):
    """(title, link) for each item, oldest last. Tolerant of both RSS shapes."""
    try:
        r = requests.get(url, headers=UA, timeout=20)
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except Exception as e:
        log(f"  ! {url}: {type(e).__name__}: {e}")
        return []
    out = []
    for item in root.iter():
        if not item.tag.endswith("item"):
            continue
        title = link = ""
        for child in item:
            tag = child.tag.split("}")[-1]
            if tag == "title":
                title = (child.text or "").strip()
            elif tag == "link":
                link = (child.text or "").strip()
        if title and link:
            out.append((title, link))
    return out


def listing_links(url, pattern, log=print, limit=40):
    """Detail pages linked from a listing page, in the order they appear -- so
    the soonest events come first, which is what the daily limit should spend
    itself on."""
    import urllib.parse
    try:
        r = requests.get(url, headers=UA, timeout=25)
        r.raise_for_status()
        html = r.content.decode(r.apparent_encoding or "utf-8", "replace")
    except Exception as e:
        log(f"  ! {url}: {type(e).__name__}: {e}")
        return []
    out, seen = [], set()
    for m in re.finditer(r'href="([^"]+)"', html):
        href = m.group(1)
        if not re.search(pattern, href):
            continue
        full = urllib.parse.urljoin(url, href)
        if full in seen:
            continue
        seen.add(full)
        out.append((full, full))
        if len(out) >= limit:
            break
    return out


def page_updated(text):
    """The date a ward page says it was last revised. This is how we learn the
    committees have posted: the register carries an update stamp, and a shrine
    that has fixed its dates changes the page before it changes the world."""
    m = re.search(r"更新日\s*[：:]\s*(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日", text)
    if m:
        return "%04d-%02d-%02d" % (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return ""


def page_text(url, limit=4000):
    try:
        r = requests.get(url, headers=UA, timeout=20)
        r.raise_for_status()
        html = r.content.decode(r.apparent_encoding or "utf-8", "replace")
    except Exception:
        return ""
    html = re.sub(r"(?is)<(script|style|nav|footer|header).*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;?", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()[:limit]


SCHEMA = ('{"keep": true, "name": "...", "start": "YYYY-MM-DD", "end": "YYYY-MM-DD", '
          '"where": "the venue and the ward, as the page gives it", '
          '"reach": "walk | her line | a trip | too far", '
          '"what": "one line, plain English, what it would be to her"}')

SYSTEM = """You are reading a ward's announcement page to decide whether it belongs in the calendar of one [[AGE_WORD]] year old girl.

She is [[WHO_SCHOOL]]. She is on her phone constantly, cares what her friends think, has no money, and would not go anywhere on her own that her friends were not going.

KEEP an event only if it could plausibly touch her life or be visible from it: a shrine festival or bon odori, fireworks, a park event, a seasonal thing (blossoms, illuminations, autumn leaves), a food or shopping street event, an anime or culture event, something at a station or a mall she uses, a big sports event that closes roads, snow or a typhoon warning that changes a day.

DROP everything that is ward business rather than life: employment support months, health screenings for adults, council meetings, business seminars, tax deadlines, welfare procedures, recruitment, consultations, anything aimed at over-65s or at parents of infants. Most of what a ward publishes is this. Dropping is the normal answer.

It must be LOCATED. Give `where` as the venue and ward the page names, and `reach` as one of:

    walk       -- {REACH_WALK}
    her line   -- {REACH_LINE}
    a trip     -- {REACH_TRIP}
    too far    -- {REACH_TOO_FAR}

DROP anything that is `too far`, and drop a `trip` unless it is the sort of thing a whole group of [[AGE_WORD]] year olds plans weeks ahead. A famous fireworks display on the other side of the city is not her life; {NEAR_EXAMPLE} is.

Give the real dates from the page, not the date it was published. If the page gives no date at all, drop it. If it runs over several days, give the range.

`what` is one plain line about what it would mean to her, not a description of the event: "the shopping street closes and everyone goes after school", "fireworks she would watch from the park with the group".

Output ONLY this JSON: """ + SCHEMA

# The register gives many events on one page, so the whole page is read once
# and every event on it comes back together. The judgement is identical; only
# the shape of the answer differs, which is why this reuses SYSTEM verbatim
# rather than restating rules that would then drift apart.
LIST_SCHEMA = ('{"events": [' + SCHEMA + ', ...]}')

LIST_SYSTEM = SYSTEM.rsplit("Output ONLY this JSON:", 1)[0] + """This page is a REGISTER: it lists many separate events, each with its own name, date and address. Read the whole page and return every event on it that passes the rules above, as a list. Events are usually run by a neighbourhood association (町会 / 自治会 / 地区委員会) or a shrine, and those are exactly the ones that matter to her: they are in her own streets.

Japanese era dates: 令和8年 is 2026. 令和9年 is 2027. A weekday in brackets after the day is a weekday, not a second date. A range like "7月18日（土曜）、19日（日曜）" is one event over two days.

Do not merge separate events, and do not invent a date for an event whose date the page says is still being confirmed (開催情報確認中) -- drop those.

Output ONLY this JSON: """ + LIST_SCHEMA


def instructions(cfg, nb):
    """(the per-page instruction, the register instruction), for THIS
    character: her age and who she is from her own fills, and how near a place
    has to be from her own map. A character whose map says nothing about reach
    gets the four answers described in general terms, which is honest: nobody
    has told her where her life is."""
    reach = nb.get("reach") or {}
    where = {
        "REACH_WALK": reach.get("walk") or "her own neighbourhood, and around her school",
        "REACH_LINE": reach.get("her line") or "anywhere on her own line: near enough that the "
                                              "group would go",
        "REACH_TRIP": reach.get("a trip") or "across the city with a change or two. She would "
                                             "only go for something big, with other people, "
                                             "planned in advance",
        "REACH_TOO_FAR": reach.get("too far") or "another prefecture, or over about ninety minutes",
        "NEAR_EXAMPLE": nb.get("near_example") or "the one on her own side of it",
    }
    def render(text):
        for k, v in where.items():
            text = text.replace("{%s}" % k, str(v))
        return cfg.fill(text, "local_events")
    return render(SYSTEM), render(LIST_SYSTEM)


def keep_event(kept, data, link, ward, today, log=print):
    """One classified event onto the kept list, or a printed reason it is not.
    Shared by the per-page reader and the register reader so the two cannot
    drift apart on what counts as located, dated and near enough."""
    if not isinstance(data, dict) or not data.get("keep"):
        return False
    start = str(data.get("start", ""))[:10]
    end = str(data.get("end", "") or start)[:10]
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", start):
        log(f"  - {str(data.get('name', ''))[:44]}  (no usable date)")
        return False
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", end) or end < start:
        end = start
    reach = str(data.get("reach", "")).strip().lower()
    if reach.startswith("too far"):
        log(f"  - {str(data.get('name', ''))[:44]}  (too far)")
        return False
    where = str(data.get("where", ""))[:100]
    key = (str(data.get("name", ""))[:120], start)
    ev = {"name": key[0] or link, "start": start, "end": end,
          "note": (str(data.get("what", ""))[:200] + (f" [{where}]" if where else "")),
          "where": where, "reach": reach, "source": link, "ward": ward,
          "discovered": today}
    kept["events"] = [e for e in kept["events"]
                      if (e.get("name", ""), e.get("start")) != key]
    kept["events"].append(ev)
    log(f"  + {start}..{end}  {ev['name'][:48]}  [{reach}] {where[:40]}")
    return True


def read_register(src, llm, kept, pages, today, args, list_system):
    """A page that lists many events, read in one call.

    The page's hash is the thing that matters operationally: a chokai register
    is static for weeks and then, one evening in June, every festival in the
    ward appears on it at once. Re-reading an unchanged page costs a call and
    tells us nothing, so an unchanged hash is skipped and the changed one is
    reported -- that IS the committees posting.
    """
    import hashlib
    url = src["url"]
    urls = [url]
    if src.get("months"):
        # a month-at-a-time calendar: this month and the next ones
        y, m = int(today[:4]), int(today[5:7])
        urls = []
        for i in range(int(src["months"]) + 1):
            mm, yy = (m + i - 1) % 12 + 1, y + (m + i - 1) // 12
            urls.append(f"{url}?type=2&year={yy}&month={mm}")
    got = 0
    for u in urls:
        text = page_text(u, limit=24000)
        if not text:
            print(f"  ! {u[:70]}: page would not load")
            continue
        h = hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]
        was = pages.get(u, {})
        updated = page_updated(text)
        if was.get("hash") == h and not args.all:
            print(f"  = unchanged since {was.get('checked', '?')}"
                  + (f" (page says updated {updated})" if updated else ""))
            continue
        if was and was.get("hash") != h:
            print(f"  ! THE PAGE CHANGED since {was.get('checked', '?')}"
                  + (f"; it now says updated {updated}" if updated else ""))
        user = f"TODAY IS {today}.\nURL: {u}\n\nPAGE:\n{text}"
        data, _ = llm.call_json("local_events",
                                [{"role": "system", "content": list_system},
                                 {"role": "user", "content": user}])
        rows = (data or {}).get("events") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            print("  ? register unreadable")
            continue
        for row in rows:
            if keep_event(kept, row, u, src["name"], today):
                got += 1
        pages[u] = {"hash": h, "checked": today, "updated": updated,
                    "kept": got, "trust": src.get("trust", "official")}
    return got


def fetch(args):
    cfg = Config(args.config)
    nb = neighbourhood(cfg)
    system, list_system = instructions(cfg, nb)
    out, seen_path = paths_for(cfg)
    print(f"for {args.config} -> {out}")
    llm = LLM(cfg)
    seen = set(_load(seen_path, []))
    pages = _load(PAGES, {})
    kept = _load(out, {"_note": "Discovered from the wards' own feeds by tools/local_events.py. "
                                "Hand-written events live in school_calendar.json and are never "
                                "touched by this.", "events": []})
    today = time.strftime("%Y-%m-%d")
    found = 0
    looked = 0
    # fireworks and festivals first: a sparse ward feed of welfare notices must
    # not spend the run before the listings get a look
    sources = nb.get("sources") or []
    if not sources:
        print("  her map names no announcement feed (local_events.sources), so there is "
              "nothing to fetch")
        return
    for src in sorted(sources, key=lambda x: 0 if x.get("kind") == "links" else 1):
        name, url = src["name"], src["url"]
        spent = 0
        print(f"[{name}]")
        if src.get("kind") == "page":
            found += read_register(src, llm, kept, pages, today, args, list_system)
            continue
        if src.get("kind") == "links":
            items = listing_links(url, src["pattern"])
            print(f"  {len(items)} listing(s)")
        else:
            items = feed_items(url)
            print(f"  {len(items)} item(s) in the feed")
        for title, link in items:
            if link in seen and not args.all:
                continue
            if spent >= src.get("budget", 4) or looked >= args.limit:
                print("  (budget spent)")
                break
            looked += 1
            spent += 1
            seen.add(link)
            text = page_text(link)
            if not text:
                print(f"  ? {title[:44]}: page would not load")
                continue
            user = f"TODAY IS {today}.\nTITLE: {title}\nURL: {link}\n\nPAGE:\n{text}"
            data, _ = llm.call_json("local_events",
                                    [{"role": "system", "content": system},
                                     {"role": "user", "content": user}])
            if not isinstance(data, dict) or not data.get("keep"):
                why = (data or {}).get("what", "") if isinstance(data, dict) else "unreadable"
                print(f"  - {title[:44]}  ({str(why)[:40] or 'not her life'})")
                continue
            start = str(data.get("start", ""))[:10]
            end = str(data.get("end", "") or start)[:10]
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", start):
                print(f"  - {title[:44]}  (no usable date)")
                continue
            reach = str(data.get("reach", "")).strip().lower()
            if reach.startswith("too far"):
                print(f"  - {title[:44]}  (too far: {str(data.get('where', ''))[:36]})")
                continue
            where = str(data.get("where", ""))[:100]
            ev = {"name": str(data.get("name", title))[:120], "start": start, "end": end,
                  "note": (str(data.get("what", ""))[:200] + (f" [{where}]" if where else "")),
                  "where": where, "reach": reach, "source": link, "ward": name,
                  "discovered": today}
            kept["events"] = [e for e in kept["events"] if e.get("source") != link]
            kept["events"].append(ev)
            found += 1
            print(f"  + {start}..{end}  {ev['name'][:48]}  [{reach}] {where[:40]}")
    kept["events"].sort(key=lambda e: e["start"])
    # forget what is well past; the calendar only ever asks about now
    cutoff = time.strftime("%Y-%m-%d", time.localtime(time.time() - 45 * 86400))
    before = len(kept["events"])
    kept["events"] = [e for e in kept["events"] if e["end"] >= cutoff]
    kept["_fetched"] = today
    _save(out, kept)
    _save(seen_path, sorted(seen)[-2000:])
    _save(PAGES, pages)
    print(f"\nlooked at {looked} new item(s), kept {found}, "
          f"dropped {before - len(kept['events'])} stale; {len(kept['events'])} on file")


def report(args):
    kept = _load(paths_for(Config(args.config))[0], {"events": []})
    print(f"{len(kept.get('events', []))} discovered event(s), last fetched {kept.get('_fetched', 'never')}")
    for e in kept.get("events", []):
        print(f"  {e['start']}..{e['end']}  {e['name'][:60]}")
        print(f"      {e.get('reach', '?')}: {e.get('where', '')[:70]}")
        print(f"      {e['note'][:90]}")
        print(f"      {e.get('ward', '')} -- {e.get('source', '')}")


def main():
    ap = argparse.ArgumentParser()
    # whose calendar this is. It hardcoded config.json and the output path
    # both, so a second character in the same world read the wrong calendar
    # and wrote over the first one's file.
    ap.add_argument("--config", default="config.json",
                    help="the character this fetch is for; her world.local_events_file is written")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--limit", type=int, default=12, help="how many new pages to read this run")
    f.add_argument("--all", action="store_true", help="re-read items already seen")
    f.set_defaults(func=fetch)
    r = sub.add_parser("report")
    r.set_defaults(func=report)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
