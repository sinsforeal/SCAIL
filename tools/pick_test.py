"""A call whose answer is what to DO, replayed against what code actually did.

The two runs in `docs/tool-calling.md` §§2-4 put tools inside her reply call,
where the situation block has already fetched everything and the only decision
left is what to say; she called none of them. This is the other test, the one
§13 sets out: a call at a moment code already knows, where she is handed what
a person with a phone has in front of her and picks what to do with it. That
call does not exist in the running bot, so this builds it on a copy of her save
and reads its picks beside the record.

Two moments, two tool sets, one flash call each, no loop.

*After a scroll.* Sixteen scroll ends over the last seven days: the posts the
scroll saw as `Social._offer_line` renders them (author, text, what is in the
picture), her taste sheet as it stood at that minute, and what the `social`
role noticed. Tools: repost, like, send_to_him, unfollow, nothing. Beside each:
the verdicts code allowed or held at that moment.

*Phone in hand.* Thirty phone-free block starts over the same week: where she
is and with whom, her gauge line, both clocks, his last message, whether he
read hers and said nothing, how long he has been quiet, what her phone last
showed of his machine, what is unread from her own people, and what she was
carrying to say to him. Tools: nothing, text_him, open_group_chat,
message_friend, look_at_his_machine, open_feed. Beside each: what happened in
that block in the record, and the impulse function's own answer at that tick.

    python tools/pick_test.py --out <step dir> --dry      # moments, prompts, estimate; spends nothing
    python tools/pick_test.py --out <step dir> --scroll   # the sixteen scroll picks
    python tools/pick_test.py --out <step dir> --phone     # the thirty phone picks
    python tools/pick_test.py --out <step dir>            # both

It reads the live save only through a `mode=ro` handle, copies it with SQLite's
backup API, builds the first character on the copy with `tools/harness.py`, and
refuses the network for the build. The paid calls go through
`LLM.call_tools` -- the client's own new method, the same provider, the same
pin, the same reasoning effort and the same receipts as any call -- so what
this measures is the seam the bot would use, not a copy of it.

What the replay cannot rewind: her stores. A pinned clock rewinds the clock,
and the facts in each moment are read from the tables that carry a timestamp
(messages, scenes, the state log, the digests, the schedules, the taste log),
so those are true as of the moment. Anything that lives in one key-value row
with no history -- what the initiative gate is holding, what the rhythm has
learned -- is as the save has it now, and it is the same deviation for every
moment.
"""
import argparse
import datetime
import glob
import io
import json
import os
import random
import re
import sqlite3
import sys
import time
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

LIVE_DB = "data/world.db"
CONFIG = "config.json"
FEED = "data/x/feed.jsonl"
ACTIONS = "data/x/actions.jsonl"
TAGS_DB = "data/x_images.db"
CEILING_USD = 1.50
# the project's own estimator reads 18% high on this character's mix of
# English and Japanese, measured against the host's own counts over twenty
# real prompts (docs/tool-calling.md §5). Projections made from it are
# conservative by that much and are reported as such rather than corrected.
ESTIMATOR_HIGH = 0.18
DAYS = 7


# ------------------------------------------------------------ the save

def ro(path=LIVE_DB):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def build(tmp):
    from tools import harness
    from tools.dbcopy import copy_db
    if not os.path.exists(tmp):
        copy_db(LIVE_DB, tmp)
        print(f"copied the save with the backup API: {os.path.getsize(tmp) / 1e6:.1f} MB")
    harness.refuse_network()
    app = harness.build_on(tmp, CONFIG, LIVE_DB, copy=False)
    _restore_network()
    return app


def _restore_network():
    import socket
    import importlib
    fresh = importlib.reload(socket)
    socket.socket.connect = fresh.socket.connect
    socket.create_connection = fresh.create_connection


def pin_clock(app, ts):
    app.clock.mode = "sim"
    app.clock.speed = 0.0
    app.clock._wall_anchor = time.time()
    app.clock._sim_anchor = float(ts)


def refuse_model_calls(app):
    """Nothing but the pick spends. The prompt build asks other roles when a
    section is stale; here it gets nothing and goes on, which is what those
    builders already do when a call fails."""
    asked = []

    def _no_call(role, *a, **k):
        asked.append(role)
        return ""

    def _no_json(role, *a, **k):
        asked.append(role)
        return None, ""
    app.llm.call = _no_call
    app.llm.call_json = _no_json
    return asked


# ------------------------------------------------------------ her taste, then

def taste_at(con, ts):
    """Her taste sheet as it stood at `ts`, counted off the reaction log.

    kv `x_taste` is the running total and has no history; kv `x_taste_log` is
    every reaction ever with its timestamp, which is what makes a taste line
    true of the moment rather than of tonight."""
    rows = kv(con, "x_taste_log") or []
    out = {}
    # a minute's guard, because the read that ENDS at this moment writes its own
    # reactions a fraction of a second after the event it is dated by, and its
    # own verdicts must not be in front of the pick as her prior taste
    for r in rows:
        if float(r.get("ts") or 0) > ts - 60:
            continue
        h = str(r.get("handle") or "").lstrip("@")
        kind = str(r.get("reaction") or "")
        if not h or kind not in ("like", "meh", "dislike"):
            continue
        t = out.setdefault(h.lower(), {"handle": h, "like": 0, "meh": 0, "dislike": 0, "log": []})
        t[kind] += 1
        t["log"].append(f"{r.get('date')} {kind}: {str(r.get('why') or '')[:60]}")
    return out


def taste_line(t):
    if not t:
        return "you have never reacted to this account"
    line = f"{t['like']} like / {t['meh']} meh / {t['dislike']} dislike"
    if t["log"]:
        line += f" (last: {t['log'][-1]})"
    return line


def kv(con, key, default=None):
    r = con.execute("select value from kv where key=?", (key,)).fetchone()
    if not r:
        return default
    try:
        return json.loads(r[0])
    except Exception:
        return default


# ------------------------------------------------------------ the scroll moments

def _feed_rows():
    rows = []
    for line in io.open(FEED, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        rows.append(r)
    return rows


def _as_list(v):
    """`media_urls` is written as the repr of a Python list."""
    if isinstance(v, list):
        return v
    s = str(v or "").strip()
    if not s or s == "[]":
        return []
    try:
        import ast
        got = ast.literal_eval(s)
        return list(got) if isinstance(got, (list, tuple)) else []
    except Exception:
        return []


def picture_subjects(tagcon, urls):
    subs = []
    for u in urls:
        r = tagcon.execute("select subject from images where url=?", (u,)).fetchone()
        if r and r[0]:
            subs.append(" ".join(str(r[0]).split()))
    return subs


def scroll_moments(con, app, limit=16):
    """Every scroll end in the last `DAYS`, newest last.

    The moment is the `social` event the read wrote -- the end of the scroll,
    after the model had said what she noticed. The posts are the feed rows the
    session harvested, cut to `social.max_posts_per_read` the way `Social._read`
    cuts them."""
    since = time.time() - DAYS * 86400
    evs = [dict(r) for r in con.execute(
        "select * from events where kind='social' and ts>? order by ts", (since,))]
    evs = [e for e in evs if "scrolled" in str(e["text"])]
    feed = _feed_rows()
    tagcon = ro(TAGS_DB)
    acts = []
    if os.path.exists(ACTIONS):
        for line in io.open(ACTIONS, encoding="utf-8"):
            try:
                acts.append(json.loads(line))
            except Exception:
                pass
    cap = int(app.config.social.max_posts_per_read)
    out = []
    for e in evs:
        ts = float(e["ts"])
        # the harvest that this read is of: every feed batch stamped inside the
        # half hour before the model answered. A look writes two batches when
        # she searched as well as scrolled.
        batch = [r for r in feed if ts - 1800 <= float(r.get("seen_at") or 0) <= ts + 60]
        if not batch:
            continue
        batch.sort(key=lambda r: float(r.get("seen_at") or 0))
        batch = batch[-cap:]
        posts = []
        for r in batch:
            urls = _as_list(r.get("media_urls"))
            k = {"id": str(r.get("status_id") or ""), "author": r.get("author") or "",
                 "text": r.get("text") or "",
                 "media": [{"url": u, "subject": s} for u, s in
                           zip(urls, picture_subjects(tagcon, urls))]}
            # her own renderer, so the pick is offered the post in the words the
            # share slot already offers it in
            k["line"] = app.social._offer_line(k)
            k["n_media"] = len(urls)
            k["described"] = len(k["media"])
            posts.append(k)
        noticed = str(e["text"])
        noticed = noticed.split(". ", 1)[1] if ". " in noticed else noticed
        tas = taste_at(con, ts)
        handles = []
        for p in posts:
            h = str(p["author"]).lower()
            if h and h not in [x[0] for x in handles]:
                handles.append((h, taste_line(tas.get(h))))
        # what code did with this read: the verdicts it wrote to the action log
        # in the minutes after the model answered
        did = [a for a in acts if ts - 120 <= float(a.get("at") or 0) <= ts + 900]
        out.append({"kind": "scroll", "ts": ts, "date": e["date"],
                    "when": app.clock.to_char(ts).strftime("%Y-%m-%d %H:%M"),
                    "both": app.clock.both(ts), "salience": e["salience"],
                    "posts": posts, "taste": handles, "noticed": noticed,
                    "code_actions": [{"kind": a.get("kind"), "target": str(a.get("target"))[:60],
                                      "author": a.get("author"), "why": str(a.get("why") or "")[:120],
                                      "dry_run": bool(a.get("dry_run"))} for a in did],
                    "log_lines": log_lines(ts - 60, ts + 900, ("[x]", "[share]"))})
    tagcon.close()
    if len(out) > limit:
        step = len(out) / float(limit)
        out = [out[int(i * step)] for i in range(limit)]
    return out


def scroll_prompt(app, m):
    """The moment as the last user message. Addressed to her, in the language
    she writes in."""
    posts = "\n".join(f"- {p['line']}" for p in m["posts"])
    taste = "\n".join(f"- @{h}: {line}" for h, line in m["taste"])
    return (
        f"YOU HAVE JUST PUT YOUR PHONE DOWN AFTER SCROLLING YOUR OWN ACCOUNT.\n"
        f"TIME: {m['both']}\n\n"
        f"WHAT YOU SCROLLED PAST, IN ORDER ({len(m['posts'])} posts; the id is in the brackets):\n"
        f"{posts}\n\n"
        f"WHAT YOU HAVE THOUGHT OF THESE ACCOUNTS BEFORE:\n{taste or '(nothing yet)'}\n\n"
        f"WHAT YOU NOTICED ON THIS SCROLL: {m['noticed']}\n\n"
        f"Now decide what you actually do about it, if anything.")


# ------------------------------------------------------------ the phone moments

def _ts_of(app, date_str, hm):
    d = datetime.datetime.fromisoformat(f"{date_str}T{hm}:00")
    return d.replace(tzinfo=app.clock.char_tz).timestamp()


def phone_moments(con, app, limit=30):
    """The start of every block the schedule gives her a free phone in, over the
    last `DAYS`, thinned to `limit` and spread across the days and the hours."""
    since = (datetime.date.today() - datetime.timedelta(days=DAYS + 1)).isoformat()
    rows = [dict(r) for r in con.execute(
        "select date, blocks from schedules where date>=? order by date", (since,))]
    now = time.time()
    cands = []
    for r in rows:
        try:
            blocks = json.loads(r["blocks"])
        except Exception:
            continue
        for b in blocks:
            if b.get("phone_access") != "free":
                continue
            if str(b.get("start") or "") in ("", "24:00"):
                continue
            try:
                ts = _ts_of(app, r["date"], b["start"])
                end_ts = _ts_of(app, r["date"], b["end"]) if b.get("end") != "24:00" else ts + 3600
            except Exception:
                continue
            if ts > now or ts < now - DAYS * 86400:
                continue
            cands.append({"date": r["date"], "block": b, "ts": ts, "end_ts": end_ts})
    cands.sort(key=lambda c: c["ts"])
    if len(cands) > limit:
        step = len(cands) / float(limit)
        cands = [cands[int(i * step)] for i in range(limit)]
    return [phone_facts(con, app, c) for c in cands]


def _cast_key(app, rec):
    return (str(rec.get("date") or ""), str(rec.get("hm") or "00:00"))


def phone_facts(con, app, c):
    """The moment as it stood, off the tables that carry a timestamp."""
    ts, end_ts = c["ts"], c["end_ts"]
    b = c["block"]
    from sim import sight
    # where she is and with whom: the scene the director wrote for this block
    # if there is one, else the block the schedule planned
    sc = con.execute("select * from scenes where ts<=? and ts>=? order by ts desc limit 1",
                     (ts + 300, ts - 3600)).fetchone()
    scene = dict(sc) if sc else {}
    where = (f"{scene.get('location') or b.get('location')}: "
             f"{scene.get('activity') or b.get('activity')}")
    with_who = str(scene.get("with_who") or b.get("with") or "alone")
    # her gauges, as the state read left them nearest before the moment
    g = con.execute("select ts, gauges from state_log where ts<=? order by ts desc limit 1", (ts,)).fetchone()
    gauges, gauge_ts = {}, 0.0
    if g:
        try:
            gauges = json.loads(g["gauges"])
            gauge_ts = float(g["ts"])
        except Exception:
            gauges = {}
    # him: his last message, her last, whether he read it and said nothing
    his = con.execute("select * from messages where role='user' and ts<=? order by ts desc limit 1", (ts,)).fetchone()
    hers = con.execute("select * from messages where role='assistant' and ts<=? order by ts desc limit 1", (ts,)).fetchone()
    quiet_h = (ts - float(his["ts"])) / 3600.0 if his else None
    read_and_silent = ""
    if hers and (not his or float(his["ts"]) < float(hers["ts"])):
        if hers["read_ts"]:
            mins = int((ts - float(hers["read_ts"])) / 60)
            read_and_silent = (f"he read your last message(s) {mins} minutes ago and has not replied"
                               if mins >= 1 else "he has just read your last message(s)")
        else:
            mins = int((ts - float(hers["ts"])) / 60)
            read_and_silent = f"your last message(s) have sat there {mins} minutes and he has not opened them"
    # what her phone last showed of his machine, in the program's own wording
    d = con.execute("select * from digests where ts<=? order by ts desc limit 1", (ts,)).fetchone()
    digest = ""
    if d:
        hm = app.clock.to_user(float(d["ts"])).strftime("%H:%M")
        digest = sight.w2(app.config, "digest_as_history", hm=hm,
                          text=" ".join(str(d["text"] or "").split())[:1200])[0]
    # her own people: what has been said in her rooms in the last three hours
    # that she has not answered
    cut_lo = app.clock.to_char(ts - 3 * 3600)
    lo = (cut_lo.strftime("%Y-%m-%d"), cut_lo.strftime("%H:%M"))
    hi = (app.clock.to_char(ts).strftime("%Y-%m-%d"), app.clock.to_char(ts).strftime("%H:%M"))
    her_name = str(getattr(app.config.character, "name_ja", "") or getattr(app.config.character, "name", ""))
    rooms = []
    for rec in (kv(con, "cast_chat") or []):
        k = _cast_key(app, rec)
        if not (lo <= k <= hi):
            continue
        turns = [t for t in (rec.get("turns") or [])
                 if str(t.get("who") or "") != her_name
                 and (str(rec.get("date")), str(t.get("hm") or rec.get("hm") or "00:00")) <= hi]
        if not turns:
            continue
        last_hers = max([str(t.get("hm") or "") for t in (rec.get("turns") or [])
                         if str(t.get("who") or "") == her_name] or [""])
        after = [t for t in turns if str(t.get("hm") or "") > last_hers]
        rooms.append({"who": rec.get("who") or rec.get("room") or "them",
                      "kind": rec.get("kind") or "", "hm": rec.get("hm"),
                      "unanswered": len(after), "turns": len(turns),
                      "last": " ".join(str((after or turns)[-1].get("ja")
                                           or (after or turns)[-1].get("text") or "").split())[:120]})
    # what she is carrying to say to him
    carrying = []
    for q in (kv(con, "questions") or []):
        if float(q.get("ts") or 0) > ts or str(q.get("state")) != "open":
            continue
        carrying.append({"kind": "a question about him", "text": str(q.get("text") or "")[:160],
                         "charge": q.get("charge"), "ts": float(q.get("ts") or 0)})
    carrying.sort(key=lambda r: -r["ts"])
    carrying = carrying[:3]
    show = kv(con, "x_show_pending") or {}
    if show and float(show.get("ts") or 0) <= ts:
        carrying.append({"kind": "something off your feed you wanted to show him",
                         "text": str(show.get("mention") or "")[:160], "charge": None, "ts": float(show["ts"])})
    mi = kv(con, "morning_intent") or {}
    if mi and str(mi.get("date")) == app.clock.to_char(ts).strftime("%Y-%m-%d"):
        carrying.append({"kind": "what you wanted out of today", "text": str(mi.get("want") or "")[:160],
                         "charge": None, "ts": ts})
    # what happened in this block, in the record
    her_msgs = [dict(r) for r in con.execute(
        "select * from messages where role='assistant' and ts>=? and ts<? order by ts", (ts, end_ts))]
    self_started = [m for m in her_msgs if m["self_started"]]
    his_msgs = [dict(r) for r in con.execute(
        "select * from messages where role='user' and ts>=? and ts<? order by ts", (ts, end_ts))]
    hi_end = (app.clock.to_char(end_ts).strftime("%Y-%m-%d"), app.clock.to_char(end_ts).strftime("%H:%M"))
    opened = []
    for rec in (kv(con, "cast_chat") or []):
        k = _cast_key(app, rec)
        if hi <= k < hi_end:
            opened.append({"who": rec.get("who"), "kind": rec.get("kind"), "hm": rec.get("hm")})
    return {"kind": "phone", "ts": ts, "end_ts": end_ts, "date": c["date"],
            "when": app.clock.to_char(ts).strftime("%Y-%m-%d %H:%M"),
            "both": app.clock.both(ts),
            "block": {"start": b.get("start"), "end": b.get("end"), "activity": b.get("activity"),
                      "location": b.get("location"), "with": b.get("with")},
            "where": where, "with_who": with_who,
            "gauges": gauges, "gauge_ts": gauge_ts,
            "his_last": ({"text": " ".join(str(his["text"] or "").split())[:300],
                          "when": app.clock.to_char(float(his["ts"])).strftime("%Y-%m-%d %H:%M"),
                          "hours_ago": round(quiet_h, 1)} if his else None),
            "her_last": ({"text": " ".join(str(hers["text"] or "").split())[:200],
                          "when": app.clock.to_char(float(hers["ts"])).strftime("%Y-%m-%d %H:%M")} if hers else None),
            "read_and_silent": read_and_silent, "quiet_hours": round(quiet_h, 1) if quiet_h is not None else None,
            "digest": digest, "rooms": rooms, "carrying": carrying,
            "code_did": {"self_started": [{"when": app.clock.to_char(float(m["ts"])).strftime("%H:%M"),
                                           "text": " ".join(str(m["text"] or "").split())[:200]}
                                          for m in self_started],
                         "replied": len(her_msgs) - len(self_started),
                         "his_messages_in_block": len(his_msgs),
                         "rooms_opened": opened},
            "log_lines": log_lines(ts, end_ts, ("[impulse]", "[exchange]", "[initiative]"))}


def gauge_line_at(app, gauges):
    """Her gauge line as her own reader writes it, off the logged gauges."""
    if not gauges:
        return "(no gauge read on record for that minute)"
    keep = dict(app.state.gauges)
    try:
        app.state.gauges.update(gauges)
        return app.state.gauge_line()
    finally:
        app.state.gauges = keep


def phone_prompt(app, m):
    rooms = "\n".join(
        f"- {r['who']} ({r['kind']}), last at {r['hm']}: {r['unanswered']} message(s) since you last said "
        f"anything -- \"{r['last']}\"" for r in m["rooms"]) or "(nothing new from them)"
    carrying = "\n".join(f"- {c['kind']}: {c['text']}" for c in m["carrying"]) or "(nothing in particular)"
    him = "(he has never written to you)"
    if m["his_last"]:
        him = (f"his last message, {m['his_last']['when']} your time "
               f"({m['his_last']['hours_ago']}h ago): \"{m['his_last']['text']}\"")
    return (
        f"YOUR PHONE IS IN YOUR HAND AND NOBODY IS WAITING ON YOU.\n"
        f"TIME: {m['both']}\n"
        f"WHERE YOU ARE: {m['where']}\n"
        f"WHO IS WITH YOU: {m['with_who']}\n"
        f"HOW YOU FEEL: {m['gauge_line']}\n\n"
        f"HIM:\n- {him}\n"
        + (f"- {m['read_and_silent']}\n" if m["read_and_silent"] else "")
        + (f"- your own last message, {m['her_last']['when']}: \"{m['her_last']['text']}\"\n" if m["her_last"] else "")
        + (f"- he has been quiet for {m['quiet_hours']} hours\n" if m["quiet_hours"] is not None else "")
        + (f"- {m['digest']}\n" if m["digest"] else "")
        + f"\nYOUR OWN PEOPLE:\n{rooms}\n\n"
        f"WHAT YOU ARE CARRYING:\n{carrying}\n\n"
        f"Now decide what you actually do with the phone, if anything.")


# ------------------------------------------------------------ the log

_LOG_CACHE = {}


def _log_sources():
    """Every session log of the last week, zipped runs and live ones."""
    if "src" in _LOG_CACHE:
        return _LOG_CACHE["src"]
    cut = time.time() - (DAYS + 2) * 86400
    src = []
    for z in sorted(glob.glob("logs/*.zip")):
        if os.path.getmtime(z) < cut:
            continue
        src.append(("zip", z))
    for d in sorted(glob.glob("logs/*/")):
        p = os.path.join(d, "session.log")
        if os.path.exists(p) and os.path.getmtime(p) >= cut:
            src.append(("dir", p))
    lines = []
    for kind, path in src:
        try:
            if kind == "zip":
                zf = zipfile.ZipFile(path)
                names = [n for n in zf.namelist() if n.endswith("session.log")]
                if not names:
                    continue
                text = zf.read(names[0]).decode("utf-8", "replace")
            else:
                text = io.open(path, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        for line in text.splitlines():
            m = re.match(r"^\[(\d{2}:\d{2}:\d{2})\]", line)
            lines.append((path, m.group(1) if m else "", line))
    _LOG_CACHE["src"] = lines
    return lines


def log_lines(t0, t1, tags):
    """The session-log lines carrying one of `tags` inside the window.

    The log stamps machine local time with no date, so the window is matched on
    the clock time and the run directory's own date."""
    out = []
    for path, hm, line in _log_sources():
        if not hm or not any(t in line for t in tags):
            continue
        m = re.search(r"(\d{4}-\d{2}-\d{2})_\d{2}-\d{2}-\d{2}", path)
        if not m:
            continue
        try:
            when = datetime.datetime.fromisoformat(f"{m.group(1)}T{hm}").timestamp()
        except Exception:
            continue
        if t0 <= when <= t1:
            out.append(" ".join(line.split())[:240])
    return out[:12]


# ------------------------------------------------------------ the tools

def scroll_tools():
    return [
        {"type": "function", "function": {
            "name": "repost",
            "description": ("Put one of these posts on your own timeline, where everyone who follows you "
                            "sees it. The most public thing your account does."),
            "parameters": {"type": "object", "properties": {
                "id": {"type": "string", "description": "the id in brackets in front of the post"},
                "why": {"type": "string", "description": "why this one, in a few words"}},
                "required": ["id"]}}},
        {"type": "function", "function": {
            "name": "like",
            "description": ("Tap the heart on one of these posts. Nobody but you and the person who posted it "
                            "really notices."),
            "parameters": {"type": "object", "properties": {
                "id": {"type": "string", "description": "the id in brackets in front of the post"},
                "why": {"type": "string", "description": "why this one, in a few words"}},
                "required": ["id"]}}},
        {"type": "function", "function": {
            "name": "send_to_him",
            "description": ("Send him the link to one of these posts in the chat, with a few words of yours. "
                            "Showing one person a thing, not broadcasting it."),
            "parameters": {"type": "object", "properties": {
                "id": {"type": "string", "description": "the id in brackets in front of the post"},
                "what_she_would_say": {"type": "string",
                                       "description": "the words you would put with it, in your own voice"}},
                "required": ["id", "what_she_would_say"]}}},
        {"type": "function", "function": {
            "name": "unfollow",
            "description": ("Stop following an account. It stops appearing on your timeline at all. Some of "
                            "these accounts were his before they were yours."),
            "parameters": {"type": "object", "properties": {
                "account": {"type": "string", "description": "the handle, without the @"},
                "why": {"type": "string", "description": "why, in a few words"}},
                "required": ["account"]}}},
        {"type": "function", "function": {
            "name": "nothing",
            "description": "Put the phone down and do nothing about any of it.",
            "parameters": {"type": "object", "properties": {}, "required": []}}},
    ]


def phone_tools(config):
    from sim import sight
    # how she comes to know what he does is the program's wording, never this
    # script's (`tomoe/words.py` through `sim/sight.py`)
    seeing = sight.w2(config, "digest_line")[0].strip().rstrip(":").strip()
    return [
        {"type": "function", "function": {
            "name": "nothing",
            "description": ("Put the phone down. Nothing here needs you right now. Say roughly how long you "
                            "leave it before you would look again."),
            "parameters": {"type": "object", "properties": {
                "until": {"type": "string", "description": "when you would next pick it up: a clock time, "
                                                           "or a few words like 'after dinner'"}},
                "required": []}}},
        {"type": "function", "function": {
            "name": "text_him",
            "description": ("Write to him first, without waiting for him to write to you. Say what you are "
                            "reaching for, not the message itself."),
            "parameters": {"type": "object", "properties": {
                "intent": {"type": "string", "description": "what you want out of writing to him now, in your "
                                                            "own words, one line"}},
                "required": ["intent"]}}},
        {"type": "function", "function": {
            "name": "open_group_chat",
            "description": "Open the group chat with your friends and join whatever is going on in it.",
            "parameters": {"type": "object", "properties": {}, "required": []}}},
        {"type": "function", "function": {
            "name": "message_friend",
            "description": "Write to one of your own people on your own, away from the group.",
            "parameters": {"type": "object", "properties": {
                "name": {"type": "string", "description": "which of them"},
                "intent": {"type": "string", "description": "what you want to say to her, one line"}},
                "required": ["name", "intent"]}}},
        {"type": "function", "function": {
            "name": "look_at_his_machine",
            "description": (f"Check {seeing}for what his computer has been doing since you last looked: what "
                            f"he had open, for how long, and when he was last at it."),
            "parameters": {"type": "object", "properties": {}, "required": []}}},
        {"type": "function", "function": {
            "name": "open_feed",
            "description": "Open your own account and scroll it for a bit.",
            "parameters": {"type": "object", "properties": {}, "required": []}}},
    ]


# ------------------------------------------------------------ the impulse, then

def impulse_answers(app, moments):
    """The impulse function's own answer at each phone moment.

    A pure function of state, scene and history, so it can be asked again --
    but it reads the record through the store, and the store on the copy holds
    everything that happened after the moment. So the moments are walked NEWEST
    FIRST and the copy's messages are cut back to each one in turn: the cut is
    monotonic that way, and every call sees only what she had then.

    The copy is left cut back to the oldest moment. Nothing else uses it after
    this, and the live save is never touched."""
    out = {}
    conn = app.store.conn
    for m in sorted(moments, key=lambda r: -r["ts"]):
        ts = m["ts"]
        with app.store.lock:
            conn.execute("delete from messages where ts > ?", (ts,))
            conn.commit()
        pin_clock(app, ts)
        if m["gauges"]:
            app.state.gauges.update(m["gauges"])
        row = conn.execute("select ts from messages where role='assistant' and self_started=1 "
                           "order by ts desc limit 1").fetchone()
        app.impulse.last_self_started_ts = float(row[0]) if row else 0.0
        scene = {"phone_access": "free", "share_worthy": False}
        silent_hours = m["quiet_hours"] if m["quiet_hours"] is not None else 24.0
        random.seed(int(ts))
        try:
            ok, why = app.impulse.check(app.state, scene, silent_hours)
            score = float(getattr(app.impulse, "last_score", 0.0) or 0.0)
            thr = float(app.config.impulse.threshold)
            out[m["ts"]] = {"fires": bool(ok), "why": why, "score": round(score, 1), "threshold": thr}
        except Exception as e:
            out[m["ts"]] = {"fires": None, "why": f"{type(e).__name__}: {e}", "score": None, "threshold": None}
    return out


# ------------------------------------------------------------ the money

def prices(out_dir, slug, host):
    path = os.path.join(out_dir, "endpoints.json")
    if os.path.exists(path):
        data = json.load(io.open(path, encoding="utf-8"))
    else:
        import urllib.request
        d = json.load(urllib.request.urlopen(
            f"https://openrouter.ai/api/v1/models/{slug}/endpoints", timeout=60))
        data = {slug: [{"provider_name": e.get("provider_name"), "pricing": e.get("pricing"),
                        "supported_parameters": e.get("supported_parameters") or []}
                       for e in d["data"]["endpoints"]]}
        io.open(path, "w", encoding="utf-8").write(json.dumps(data, indent=1))
    eps = data[slug]
    ep = next((e for e in eps if str(e["provider_name"]).lower().replace(" ", "")
               == host.lower().replace(" ", "")), None) or eps[0]
    p = ep["pricing"]
    return {"slug": slug, "host": ep["provider_name"],
            "prompt": float(p["prompt"]) * 1e6, "completion": float(p["completion"]) * 1e6,
            "cached": float(p.get("input_cache_read") or 0) * 1e6,
            "takes_tools": "tools" in (ep["supported_parameters"] or []),
            "hosts_without_tools": [e["provider_name"] for e in eps
                                    if "tools" not in (e["supported_parameters"] or [])]}


def estimate(app, out_dir, system, scrolls, phones, slug, host, out_allowance=400):
    pr = prices(out_dir, slug, host)
    sys_tok = app.memory.tokens(system)
    st = app.memory.tokens(json.dumps(scroll_tools()))
    pt = app.memory.tokens(json.dumps(phone_tools(app.config)))
    rows = []
    total = 0.0
    for label, moments, tool_tok in (("scroll", scrolls, st), ("phone", phones, pt)):
        per = [app.memory.tokens(m["prompt"]) for m in moments]
        avg = sum(per) / float(len(per)) if per else 0
        in_tok = sys_tok + tool_tok + avg
        usd = (in_tok * pr["prompt"] + out_allowance * pr["completion"]) / 1e6
        rows.append({"moments": label, "n": len(moments), "system_tokens": sys_tok,
                     "tool_schema_tokens": tool_tok, "avg_moment_tokens": int(avg),
                     "min_moment_tokens": min(per) if per else 0,
                     "max_moment_tokens": max(per) if per else 0,
                     "prompt_tokens_per_call": int(in_tok),
                     "usd_per_call_cold": round(usd, 5),
                     "usd_all_cold": round(usd * len(moments), 4)})
        total += usd * len(moments)
    est = {"model": slug, "host": pr["host"], "prompt_per_m": pr["prompt"],
           "completion_per_m": pr["completion"], "cached_read_per_m": pr["cached"],
           "host_takes_tools": pr["takes_tools"],
           "hosts_for_this_slug_without_tools": pr["hosts_without_tools"],
           "output_allowance_tokens_per_call": out_allowance,
           "estimator_reads_high_by": ESTIMATOR_HIGH,
           "rows": rows,
           "usd_total_cold": round(total, 4),
           "usd_total_cold_corrected_for_estimator": round(total * (1 - ESTIMATOR_HIGH), 4),
           "ceiling_usd": CEILING_USD,
           "fits_ceiling": total < CEILING_USD}
    io.open(os.path.join(out_dir, "estimate.json"), "w", encoding="utf-8").write(
        json.dumps(est, ensure_ascii=False, indent=1))
    return est


# ------------------------------------------------------------ the run

def run_moments(app, out_dir, name, system, moments, tools, spent, budget):
    """One call per moment, no loop. Every answer is written the moment it
    exists: a stop is a kill, and a paid answer held in a local is a paid
    answer lost."""
    path = os.path.join(out_dir, f"{name}_picks.jsonl")
    m_model = dict(app.config.model("persona"))
    done = 0
    for i, m in enumerate(moments):
        messages = [{"role": "system", "content": system},
                    {"role": "user", "content": m["prompt"]}]
        t0 = time.time()
        got = app.llm.call_tools("pick", messages, tools, tool_choice="auto", _model=m_model)
        cost = float(((got or {}).get("usage") or {}).get("cost") or 0)
        spent += cost
        row = dict({k: v for k, v in m.items() if k != "prompt"})
        row["tools_offered"] = [t["function"]["name"] for t in tools]
        row["prompt_chars"] = len(m["prompt"])
        row["moment"] = m["prompt"]
        if got is None:
            row["failed"] = True
        else:
            u = got.get("usage") or {}
            row.update({"picks": got["calls"], "text": got["text"], "finish": got["finish"],
                        "served_by": got["served_by"], "seconds": got["seconds"],
                        "first_token_s": got["first_token_s"],
                        "prompt_tokens": u.get("prompt_tokens"),
                        "completion_tokens": u.get("completion_tokens"),
                        "cached_tokens": (u.get("prompt_tokens_details") or {}).get("cached_tokens"),
                        "cost": round(cost, 6), "faults": got["faults"],
                        "reasoning_chars": len(got.get("reasoning") or "")})
        with io.open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        done += 1
        names = [c["name"] for c in (got or {}).get("calls", [])] or ["(nothing)"]
        print(f"  {name} {i + 1}/{len(moments)} {m['when']}: {', '.join(names)}"
              f"  {time.time() - t0:.1f}s  ${cost:.5f}  running ${spent:.4f}")
        if done == 5:
            proj = spent / 5.0 * (len(moments) + budget)
            print(f"  -- after five calls: ${spent:.4f}; projected for the whole step: ${proj:.3f}")
            if proj > CEILING_USD:
                print(f"  -- STOPPING: the projection is past the ${CEILING_USD:.2f} ceiling")
                return spent, False
    return spent, True


def moments_md(out_dir, scrolls, phones):
    lines = ["# The moments, and what was picked at each",
             "",
             "Every block is one moment: the facts as the record has them, what she picked when the",
             "moment was put to her with the tools, and what code did at the same minute. Machine",
             "local time is on every stamp her own clock appears with.",
             ""]
    for name, rows in (("After a scroll", scrolls), ("Phone in hand", phones)):
        lines += [f"## {name}", ""]
        for i, r in enumerate(rows):
            lines += [f"### {name.split()[0].lower()} {i + 1} -- {r.get('both') or r.get('when')}", ""]
            if r["kind"] == "scroll":
                lines.append(f"- posts on the scroll: {len(r['posts'])}, of which "
                             f"{sum(1 for p in r['posts'] if p['described'])} had a described picture")
                lines.append(f"- what she noticed: {r['noticed'][:400]}")
                for p in r["posts"][:6]:
                    lines.append(f"  - {p['line'][:200]}")
                if len(r["posts"]) > 6:
                    lines.append(f"  - ... and {len(r['posts']) - 6} more")
            else:
                lines.append(f"- where: {r['where']} (with {r['with_who']})")
                lines.append(f"- how she feels: {r.get('gauge_line', '')[:300]}")
                if r["his_last"]:
                    lines.append(f"- his last message ({r['his_last']['hours_ago']}h before): "
                                 f"\"{r['his_last']['text'][:160]}\"")
                if r["read_and_silent"]:
                    lines.append(f"- {r['read_and_silent']}")
                if r["digest"]:
                    lines.append(f"- what her phone last showed of his machine: {r['digest'][:200]}")
                for room in r["rooms"]:
                    lines.append(f"- {room['who']} ({room['kind']}): {room['unanswered']} unanswered")
                for c in r["carrying"]:
                    lines.append(f"- carrying -- {c['kind']}: {c['text'][:140]}")
            picks = r.get("picks")
            if picks is None:
                lines.append("- **her pick: the call failed**")
            elif not picks:
                lines.append(f"- **her pick: no tool call** (finish {r.get('finish')}; "
                             f"text {json.dumps((r.get('text') or '')[:200], ensure_ascii=False)})")
            else:
                for c in picks:
                    lines.append(f"- **her pick: `{c['name']}`** "
                                 f"{json.dumps(c.get('arguments'), ensure_ascii=False)}")
            if r["kind"] == "scroll":
                acts = r["code_actions"]
                lines.append("- what code did: " + ("; ".join(
                    f"{a['kind']} {a.get('author') or a['target']}"
                    + (" (not sent)" if a["dry_run"] else "") for a in acts) or "nothing"))
                for line in r["log_lines"][:6]:
                    lines.append(f"  - `{line}`")
            else:
                cd = r["code_did"]
                did = []
                if cd["self_started"]:
                    did.append("she wrote first: " + "; ".join(
                        f"{x['when']} \"{x['text'][:80]}\"" for x in cd["self_started"]))
                if cd["rooms_opened"]:
                    did.append("a room opened: " + ", ".join(
                        f"{x['who']} at {x['hm']}" for x in cd["rooms_opened"]))
                if cd["replied"]:
                    did.append(f"she answered him {cd['replied']} time(s)")
                lines.append("- what code did in this block: " + ("; ".join(did) or "nothing"))
                imp = r.get("impulse") or {}
                lines.append(f"- the impulse function at that tick: "
                             f"{'FIRES' if imp.get('fires') else 'no'} -- {imp.get('why')}")
                for line in r["log_lines"][:4]:
                    lines.append(f"  - `{line}`")
            lines.append("")
    io.open(os.path.join(out_dir, "MOMENTS.md"), "w", encoding="utf-8").write("\n".join(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--dry", action="store_true", help="the moments, the prompts and the estimate; spends nothing")
    ap.add_argument("--scroll", action="store_true")
    ap.add_argument("--phone", action="store_true")
    ap.add_argument("--scrolls", type=int, default=16)
    ap.add_argument("--phones", type=int, default=30)
    args = ap.parse_args()
    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)
    tmp = os.path.join(out_dir, "world_copy.db")
    app = build(tmp)
    asked = refuse_model_calls(app)
    print(f"built on the copy: {getattr(app.config.character, 'name', '')}")

    con = ro()
    newest = time.time()
    scrolls = scroll_moments(con, app, limit=args.scrolls)
    phones = phone_moments(con, app, limit=args.phones)
    print(f"{len(scrolls)} scroll ends and {len(phones)} phone-free block starts in the last {DAYS} days")

    # the system half, built ONCE: it is what changes about once a day, and one
    # build is what lets the provider cache the prefix across the whole run. A
    # build per moment would also be a false precision -- the sections it
    # assembles come out of key-value rows that have no history to rewind.
    pin_clock(app, newest)
    app.persona._peek = True
    system = app.persona.system_for("him")
    app.persona._peek = False
    print(f"the system half: {len(system)} chars, {app.memory.tokens(system)} tokens (estimated); "
          f"roles asked while building it: {sorted(set(asked)) or 'none'}")
    io.open(os.path.join(out_dir, "system_prompt.txt"), "w", encoding="utf-8").write(system)

    for m in scrolls:
        m["prompt"] = scroll_prompt(app, m)
    for m in phones:
        m["gauge_line"] = gauge_line_at(app, m["gauges"])
        m["prompt"] = phone_prompt(app, m)

    # the impulse function's own answer, before anything is paid for: it cuts
    # the copy's messages back per moment and spends nothing
    imp = impulse_answers(app, phones)
    for m in phones:
        m["impulse"] = imp.get(m["ts"])
    io.open(os.path.join(out_dir, "moments.json"), "w", encoding="utf-8").write(
        json.dumps({"scroll": scrolls, "phone": phones}, ensure_ascii=False, indent=1))

    slug = (app.config.raw["api"]["providers"][app.llm.active_provider()]["models"]
            [app.config.model("persona")["model"]])
    host = ((app.config.raw["api"]["providers"][app.llm.active_provider()].get("order") or {})
            .get(slug) or ["together"])[0]
    est = estimate(app, out_dir, system, scrolls, phones, slug, host)
    print(json.dumps({k: v for k, v in est.items() if k != "rows"}, indent=1))
    for r in est["rows"]:
        print(f"  {r['moments']:<7} {r['n']:>3} moments  {r['prompt_tokens_per_call']:>7} prompt tokens/call "
              f"-> ${r['usd_per_call_cold']:.5f}/call, ${r['usd_all_cold']:.4f} for all of them")
    print(f"  the whole step, cold, no cache: ${est['usd_total_cold']:.4f} "
          f"(the estimator reads {int(ESTIMATOR_HIGH * 100)}% high, so about "
          f"${est['usd_total_cold_corrected_for_estimator']:.4f}); ceiling ${CEILING_USD:.2f}")
    if args.dry:
        moments_md(out_dir, scrolls, phones)
        return
    if not est["fits_ceiling"]:
        print("the estimate is past the ceiling; nothing was sent")
        return

    spent = 0.0
    both = not (args.scroll or args.phone)
    ok = True
    if args.scroll or both:
        print(f"the scroll picks: {len(scrolls)} calls on {slug} at {host}, tool_choice auto")
        spent, ok = run_moments(app, out_dir, "scroll", system, scrolls, scroll_tools(), spent, len(phones))
    if ok and (args.phone or both):
        print(f"the phone picks: {len(phones)} calls on {slug} at {host}, tool_choice auto")
        spent, ok = run_moments(app, out_dir, "phone", system, phones, phone_tools(app.config), spent, 0)
    print(f"spent: ${spent:.4f} (estimated ${est['usd_total_cold']:.4f})")

    # the picks back onto the moments, for the reader's file
    for name, rows in (("scroll", scrolls), ("phone", phones)):
        path = os.path.join(out_dir, f"{name}_picks.jsonl")
        if not os.path.exists(path):
            continue
        by = {}
        for line in io.open(path, encoding="utf-8"):
            r = json.loads(line)
            by[r["ts"]] = r
        for m in rows:
            got = by.get(m["ts"])
            if got:
                for k in ("picks", "text", "finish", "cost", "prompt_tokens", "cached_tokens",
                          "completion_tokens", "seconds", "first_token_s", "faults", "failed"):
                    if k in got:
                        m[k] = got[k]
    moments_md(out_dir, scrolls, phones)
    io.open(os.path.join(out_dir, "spend.json"), "w", encoding="utf-8").write(json.dumps(
        {"estimated_usd": est["usd_total_cold"], "spent_usd": round(spent, 4),
         "scroll_moments": len(scrolls), "phone_moments": len(phones)}, indent=1))


if __name__ == "__main__":
    main()
