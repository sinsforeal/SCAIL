"""The absurdity audit: is anything here impossible for a fifteen-year-old?

`tools/smoke.py` proves the machine is well formed -- no dead config keys, no
unbound names, every prompt file present. It cannot tell you that the ringleader
of her friendship group sent five messages a day, that a gate was set below a
value the data never reaches, or that she went seven hours unable to speak to
the girl sitting across the table from her. Every one of those was live on
2026-08-27, every one was structurally valid, and every one was obvious the
moment somebody looked at the number.

So this looks at the numbers. Each check states what would be ABSURD in plain
words, measures it, and reports OK / ODD / ABSURD. It reads the save read-only
and runs no model, so it is safe against the running bot.

    python tools/absurd.py             # everything
    python tools/absurd.py --verbose   # with the measured value on every check

The checks are grouped by the KIND of absurdity, because the kinds recur:

  DEAD GATE      a threshold the data never reaches, so the branch never runs
  FROZEN         a state that has been true implausibly long
  NEVER FIRED    a mechanism that has never once happened
  UNREACHED      a field code reads that is empty for everybody
  VOLUME         a rate no human would produce
  SILENCE        a gap in her day nobody would leave
  ONE VOICE      the cast writing in one voice, the agents collapsing back
  PARROT         a phrase of hers turning into a stuck record
  GHOST PLACE    a place in her mouth that her world does not have
  MONEY          money spent that the log never saw
  DROPPED        somebody on the roster her life stopped touching
  REPEAT BEAT    the planner writing the same day twice
  UNSAVED        a model call whose answer reaches nothing that outlives today
  UNHEARD        a line she is handed every call and never once admitted
  SEAMS          the day read as one story does not hold together

Adding a check is a function returning (level, headline, detail) and a line in
CHECKS. Keep the headline a plain sentence about HER, not about the code.
"""
import argparse
import collections
import datetime
import json
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logger
logger.log = lambda m, to_console=True: None

from config import Config

OK, ODD, ABSURD = "ok", "odd", "ABSURD"


class Save:
    """Read-only view of the save, so a check cannot damage what it audits."""

    def __init__(self, path):
        self.con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)

    def kv(self, key, default=None):
        r = self.con.execute("select value from kv where key=?", (key,)).fetchone()
        if not r:
            return default
        try:
            return json.loads(r[0])
        except (TypeError, ValueError):
            return default

    def rows(self, sql, args=()):
        return self.con.execute(sql, args).fetchall()


# ---------------------------------------------------------------- DEAD GATE

def dead_gauge_gates(cfg, s):
    """A gate on a gauge that the gauge has never reached is a branch that has
    never run. `slip_energy_below` was 30 against a floor of 45."""
    hist = collections.defaultdict(list)
    for (blob,) in s.rows("select gauges from state_log order by id desc limit 2000"):
        try:
            d = json.loads(blob)
        except (TypeError, ValueError):
            continue
        for k, v in d.items():
            try:
                hist[k].append(float(v))
            except (TypeError, ValueError):
                pass
    if not hist:
        return OK, "no recorded states to judge gates against", ""

    gates = [("exchange", "slip_energy_below", "energy", "below"),
             ("exchange", "slip_anger_from", "anger", "above"),
             ("state", "stress_from", "stress", "above")]
    bad = []
    for section, key, gauge, sense in gates:
        thr = getattr(getattr(cfg, section, None), key, None)
        vals = hist.get(gauge)
        if thr is None or not vals:
            continue
        hit = sum(1 for v in vals if (v <= thr if sense == "below" else v >= thr))
        lo, hi = min(vals), max(vals)
        if hit == 0:
            bad.append(f"{key}={thr} but {gauge} ranged {lo:.0f}-{hi:.0f} over {len(vals)} states: never once")
        elif hit < len(vals) * 0.01:
            bad.append(f"{key}={thr}: {gauge} reached it {hit} time(s) in {len(vals)}")
    if any("never once" in b for b in bad):
        return ABSURD, "a gate is set where her state never goes, so the branch is dead", "; ".join(bad)
    if bad:
        return ODD, "a gate fires so rarely it may as well be off", "; ".join(bad)
    return OK, "every gauge gate is reachable", ""


# ------------------------------------------------------------------ FROZEN

def frozen_unread(cfg, s):
    """A message of his sitting unread for hours is usually the design working
    -- she was asleep, or in class, or at a desk with her phone face down. It
    is only absurd when her phone is in her hand and free and she still has not
    looked. Judging it on the clock alone made this cry wolf on every school
    day, which is how a checker gets ignored."""
    rows = s.rows("select id, ts from messages where role='user' "
                  "and (read_ts is null or read_ts=0) order by ts")
    if not rows:
        return OK, "nothing of his is sitting unread", ""
    oldest = min(r[1] for r in rows)
    mins = (time.time() - oldest) / 60.0
    scene = s.rows("select phone_access, location from scenes order by rowid desc limit 1")
    access = (scene[0][0] if scene else "") or "?"
    where = (scene[0][1] if scene else "") or "?"
    detail = f"{len(rows)} unread, oldest {mins:.0f} min; her phone is `{access}` at {where[:40]}"
    if access == "free" and mins > 120:
        return ABSURD, "her phone is free in her hand and he is still unanswered", detail
    if access == "free" and mins > 45:
        return ODD, "she is free and has not answered him", detail
    if mins > 600:
        return ODD, "he has been unanswered for ten hours across every kind of access", detail
    return OK, "he is unanswered for a reason her day explains", detail


def frozen_exchange(cfg, s):
    """An exchange deferred over and over is the attention model eating her
    social life: this is what ran for 453 minutes."""
    live = s.kv("exchange_live")
    if not live:
        return OK, "no exchange is stuck mid-flight", ""
    pushed = int(live.get("pushed", 0))
    started = float(live.get("started_ts", 0) or 0)
    age = (time.time() - started) / 60.0 if started else 0
    detail = f"{live.get('who')} ({live.get('kind')}), {len(live.get('turns', []))} turns, " \
             f"pushed {pushed}, {age:.0f} min old"
    cap = int(getattr(cfg.exchange, "busy_max_pushbacks", 4) or 4)
    if pushed > cap:
        return ABSURD, "she has been deferring the same person past the cap", detail
    if age > getattr(cfg.exchange, "group_max_live_minutes", 180) * 1.5:
        return ODD, "an exchange has been open far longer than its own limit", detail
    return OK, "the live exchange is progressing", detail


# ------------------------------------------------------------- NEVER FIRED

def never_fired(cfg, s):
    """A mechanism that has never happened is either impossible or unwired --
    the dialect rules flagged 0 of 319 turns for weeks. But a thing built this
    afternoon has not had a chance yet, and calling that absurd is noise. Each
    entry carries how many days it should have had.

    `days` is roughly how long a working version would take to fire once."""
    # (key, built on, days a working version needs to fire once, what it means).
    # The date is when the MECHANISM was written, not how old the save is: a
    # thing built this afternoon on a month-old save has had an afternoon, and
    # calling that absurd is exactly the noise that gets an audit ignored.
    watch = [("voice_flags", "2026-08-27", 1, "the voice checker has never flagged a line"),
             ("knew_late", "2026-08-27", 7, "she has never once known she was going to be late"),
             ("sticker_weight", "2026-08-27", 3, "she has never put a sticker down"),
             ("recaps", "2026-08-24", 3, "the knowledge base has never cached anything"),
             # each of these stopped producing today and was noticed by
             # accident rather than by a check
             ("npcs", "2026-08-28", 2, "she has never run into anybody who is not her cast"),
             ("scenery_lore", "2026-08-25", 3, "she has never sent him a photograph"),
             ("reactions_log", "2026-08-26", 2, "her face has never changed")]
    today = datetime.date.today()
    empty, young = [], []
    for key, built, days, said in watch:
        v = s.kv(key)
        if key == "recaps":
            try:
                v = s.rows("select count(*) from recaps")[0][0]
            except Exception:
                v = None
        if not (v is None or (hasattr(v, "__len__") and len(v) == 0) or v == 0):
            continue
        try:
            had = (today - datetime.date.fromisoformat(built)).days
        except ValueError:
            had = 99
        if had >= days:
            empty.append(f"{said} -- {had}d old, needs {days}")
        else:
            young.append(f"{said} ({had}d old, give it {days})")
    if len(empty) >= 3:
        return ABSURD, "several mechanisms have never fired, and have had the time to", "; ".join(empty)
    if empty:
        return ODD, "a mechanism has never fired and has had the time to", "; ".join(empty)
    if young:
        return OK, "nothing has failed to fire; some are too new to judge", "; ".join(young)
    return OK, "the watched mechanisms have all fired", ""


# --------------------------------------------------------------- UNREACHED

def unreached_fields(cfg, s):
    """A field the code reads that is empty for every single person. `week`
    was read by two callers and present for nobody."""
    rels = s.kv("relationships", {}) or {}
    people = {k: v for k, v in rels.items() if k != "him" and isinstance(v, dict)}
    if not people:
        return OK, "no cast to check", ""
    bad = []
    for field in ("week", "rhythm", "stance", "role_id", "ja"):
        have = [k for k, v in people.items() if v.get(field)]
        if not have:
            bad.append(f"`{field}` is empty for all {len(people)}")
        elif len(have) < len(people) / 2:
            bad.append(f"`{field}` only on {len(have)} of {len(people)}")
    if any("all" in b for b in bad):
        return ABSURD, "a field the code reads is empty for everybody", "; ".join(bad)
    if bad:
        return ODD, "a field is missing for most of the cast", "; ".join(bad)
    return OK, "the cast fields reach the people who need them", ""


# ------------------------------------------------------------------ VOLUME

def message_volume(cfg, s):
    """Nobody her age sends five messages a day to their closest friends."""
    chat = s.kv("cast_chat", []) or []
    if not chat:
        return OK, "no exchanges recorded yet", ""
    days = len({e.get("date") for e in chat}) or 1
    per = collections.Counter()
    for e in chat:
        for t in e.get("turns", []):
            per[t.get("who")] += 1
    if not per:
        return OK, "no turns recorded", ""
    rates = {k: v / days for k, v in per.items()}
    detail = ", ".join(f"{k} {v:.1f}/day" for k, v in sorted(rates.items(), key=lambda x: -x[1]))
    top = max(rates.values())
    if top < 8:
        return ABSURD, "her whole social world speaks less than one person would", detail
    if top < 20:
        return ODD, "the chat is quieter than a real one", detail
    return OK, "the chat carries a believable amount of talk", detail


def one_sided(cfg, s):
    """An 'exchange' where only one person ever spoke is not an exchange."""
    chat = s.kv("cast_chat", []) or []
    if not chat:
        return OK, "no exchanges recorded yet", ""
    solo = [e for e in chat if len({t.get("who") for t in e.get("turns", [])}) <= 1]
    share = len(solo) / len(chat)
    detail = f"{len(solo)} of {len(chat)} had one voice in them"
    if share > 0.30:
        return ABSURD, "most of her conversations are one person talking to nobody", detail
    if share > 0.15:
        return ODD, "a lot of conversations never got an answer", detail
    return OK, "her conversations have two sides", detail


# ----------------------------------------------------------------- SILENCE

def waking_silence(cfg, s):
    """A teenager does not go eight WAKING hours with nobody reaching her.

    Waking is the word that matters. Measured across the whole clock this
    check calls every night an absurdity: the first run after a replan cried
    ABSURD over 00:23-08:12, which is her asleep. The window comes from the
    night she actually had (`health_days[date].sleep`), and the beats before
    she woke belong to the tail of the night before, not to this day."""
    beats = s.kv("cast_beats", {}) or {}
    date = beats.get("date", "")
    sleep = ((s.kv("health_days", {}) or {}).get(date) or {}).get("sleep") or {}
    wake = str(sleep.get("wake") or "07:30")[:5]
    bed = str(sleep.get("bedtime") or "00:30")[:5]

    def m(hm):
        return int(hm[:2]) * 60 + int(hm[3:5])

    end = m(bed) + (24 * 60 if m(bed) < m(wake) else 0)
    rows = sorted(b.get("time", "") for b in beats.get("beats", []) if b.get("time"))
    rows = [r for r in rows if m(wake) <= m(r) <= end]
    if len(rows) < 2:
        return OK, "not enough beats in her waking day to judge", ""
    points = [wake] + rows + [bed]
    gaps = []
    for a, b in zip(points, points[1:]):
        span = (m(b) + (24 * 60 if m(b) < m(a) else 0)) - m(a)
        gaps.append((span, a, b))
    worst, a, b = max(gaps)
    detail = (f"longest gap {worst // 60}h{worst % 60:02d}, {a}-{b}, over {len(rows)} beats "
              f"in her waking day ({wake} to {bed})")
    if worst >= 300:
        return ABSURD, "nobody reaches her for five hours of her waking day", detail
    if worst >= 210:
        return ODD, "there is a long dead stretch in her day", detail
    return OK, "her day has people in it throughout", detail


# ---------------------------------------------------------------- ONE VOICE

def one_voice(cfg, s):
    """Four agents, four sheets, one call each -- and nothing checks that they
    come out sounding like four people. The failure this catches is the cast
    collapsing back into a single writer, which is what the whole multi-agent
    split was built to stop: it looks perfectly healthy from every other angle,
    because every turn is well formed and in the right mouth."""
    rows = s.kv("cast_chat", []) or []
    ends = ("よ", "ね", "な", "じゃん", "だし", "の", "か", "笑", "！", "。")
    prof = {}
    for x in rows[-40:]:
        for t in x.get("turns", []):
            ja = (t.get("ja") or "").strip()
            who = t.get("who") or "?"
            if not ja:
                continue
            p = prof.setdefault(who, {"n": 0, "chars": 0, "q": 0, "e": collections.Counter()})
            p["n"] += 1
            p["chars"] += len(ja)
            p["q"] += 1 if ("?" in ja or "？" in ja) else 0
            for e in ends:
                if ja.rstrip().endswith(e):
                    p["e"][e] += 1
                    break
    people = {k: v for k, v in prof.items() if v["n"] >= 12}
    if len(people) < 3:
        return OK, "not enough turns yet to tell their voices apart", ""
    means = {k: v["chars"] / v["n"] for k, v in people.items()}
    lo, hi = min(means.values()), max(means.values())
    spread = (hi - lo) / max(hi, 1)
    detail = ", ".join(f"{k} {means[k]:.0f} chars/turn, {100 * people[k]['q'] // people[k]['n']}% questions"
                       for k in sorted(people, key=lambda x: -means[x]))
    if spread < 0.12:
        return ABSURD, "her friends all write the same length of message", detail
    if spread < 0.22:
        return ODD, "their voices are closer together than four people would be", detail
    return OK, "they do not all sound the same", detail


# ------------------------------------------------------------------- PARROT

def parrot(cfg, s):
    """A tic is character; the same eight characters in a quarter of everything
    she says is a stuck record. Measured on HER lines only, over every day in
    the record, so a phrase that is merely today's mood does not count."""
    from sim import roster
    rows = s.kv("cast_chat", []) or []
    mine, days = [], set()
    for x in rows:
        for t in x.get("turns", []):
            ja = (t.get("ja") or "").replace(" ", "").replace("　", "")
            # her own turns, by what the record calls her. It used to be
            # the end of the FIRST character's given name in kanji, so on
            # anybody else this measured nobody's lines at all.
            if ja and roster.same(cfg, t.get("who") or "", roster.handle(cfg)):
                mine.append((x.get("date", ""), ja))
                days.add(x.get("date", ""))
    if len(mine) < 40:
        return OK, "not enough of her own lines yet to judge", ""
    n = 8
    seen = collections.Counter()
    where = collections.defaultdict(set)
    for date, ja in mine:
        grams = {ja[i:i + n] for i in range(max(0, len(ja) - n + 1))}
        for g in grams:
            seen[g] += 1
            where[g].add(date)
    top = [(c, g) for g, c in seen.items() if len(where[g]) >= 3]
    if not top:
        return OK, "nothing she says has hardened into a phrase", f"{len(mine)} lines over {len(days)} days"
    top.sort(reverse=True)
    count, gram = top[0]
    share = count / len(mine)
    detail = (f"{gram!r} in {count} of {len(mine)} of her lines ({100 * share:.0f}%), "
              f"on {len(where[gram])} different days")
    if share >= 0.25:
        return ABSURD, "one phrase is in a quarter of everything she says", detail
    if share >= 0.12:
        return ODD, "a phrase of hers is hardening into a tic", detail
    return OK, "nothing she says has hardened into a phrase", detail


# -------------------------------------------------------------- GHOST PLACE

def ghost_place(cfg, s):
    """Her body stands on a node in `places.json`. A scene whose location
    matches nothing there is a place her world does not have -- which is not
    cosmetic: it is how "at Aya's" resolved to nothing for weeks and left her
    body wherever it had been, and how the scenery picker loses its bearings."""
    try:
        with open("data/places.json", "r", encoding="utf-8") as f:
            places = json.load(f)
    except OSError:
        return OK, "no place map to check against", ""
    words = []
    for key, node in (places.get("nodes") or {}).items():
        words.append(key.replace("_", " ").lower())
        words.append(str(node.get("name", "")).lower())
        for k in node.get("keywords", []):
            words.append(str(k).lower())
    words = [w for w in words if len(w) >= 3]
    rows = s.rows("select date, hm, location from scenes order by rowid desc limit 120")
    miss = []
    for date, hm, location in rows:
        loc = str(location or "").lower()
        if not loc:
            continue
        if not any(w in loc for w in words):
            miss.append(f"{date} {hm} {str(location)[:60]}")
    if not miss:
        return OK, "every place she has been is a place her world has", f"{len(rows)} scenes checked"
    detail = f"{len(miss)} of {len(rows)} scenes: " + "; ".join(miss[:3])
    if len(miss) >= max(6, len(rows) // 10):
        return ABSURD, "she keeps standing somewhere her world does not have", detail
    return ODD, "a place she was in is not on her map", detail


# -------------------------------------------------------------------- MONEY

def money_sense(cfg, s):
    """Fifteen-year-olds have a fixed allowance and no overdraft. Two of the
    same purchase twenty minutes apart is the machine writing twice, and a
    balance below zero is not a mood, it is a bug."""
    m = s.kv("money", {}) or {}
    log = m.get("log", []) or []
    bal = m.get("balance")
    dupes = []
    for a, b in zip(log, log[1:]):
        if a.get("on") == b.get("on") and a.get("date") == b.get("date") and a.get("yen") == b.get("yen"):
            dupes.append(f"{a.get('date')} {a.get('hm')}/{b.get('hm')} {a.get('on','')[:40]} {a.get('yen')}")
    detail = f"balance {bal} yen over {len(log)} entries"
    if isinstance(bal, (int, float)) and bal < 0:
        return ABSURD, "she has spent money she does not have", detail
    if dupes:
        return ODD, "the same purchase is in the log twice", detail + "; " + "; ".join(dupes[:3])
    return OK, "her money adds up", detail


# ------------------------------------------------------------------ DROPPED

def dropped_person(cfg, s):
    """Somebody on the roster, not marked dormant, whom nothing has touched for
    a week. Either her life quietly stopped including them -- which is a thing
    that happens and should be MARKED, not silent -- or a beat budget is
    starving them."""
    rels = s.kv("relationships", {}) or {}
    rows = s.kv("cast_chat", []) or []
    beats = []
    for key in ("cast_beats", "cast_beats_prev"):
        b = s.kv(key, {}) or {}
        for x in b.get("beats", []):
            beats.append((b.get("date", ""), x.get("who", "")))
    # the record names people in Japanese and the roster in handles: one
    # person, whatever the row calls them (this check first reported that
    # every friend she has had "never" been in her life)
    from sim import roster

    def role(name):
        return roster.role_of(cfg, name) or str(name or "")

    last = {}
    for x in rows:
        for t in x.get("turns", []):
            w = role(t.get("who") or "")
            last[w] = max(last.get(w, ""), x.get("date", ""))
    for date, who in beats:
        w = role(who)
        last[w] = max(last.get(w, ""), date)
    today = max([d for d in last.values() if d] or [""])
    if not today:
        return OK, "no record to judge yet", ""
    stale = []
    for k, r in rels.items():
        if k == "him" or r.get("dormant"):
            continue
        name = r.get("name", k)
        seen = last.get(role(name), "") or last.get(role(k), "")
        if not seen:
            stale.append(f"{name}: never")
            continue
        days = (datetime.date.fromisoformat(today) - datetime.date.fromisoformat(seen)).days
        if days >= 7:
            stale.append(f"{name}: {days}d")
    detail = "; ".join(stale) if stale else f"{len(rels) - 1} people, all seen within a week"
    if any(x.endswith("never") for x in stale):
        return ABSURD, "somebody on her roster has never been in her life", detail
    if stale:
        return ODD, "somebody has been out of her life for a week and is not marked dormant", detail
    return OK, "everybody on her roster is still in her life", detail


# --------------------------------------------------------------- REPEAT BEAT

def repeat_beat(cfg, s):
    """The planner writing the same day twice. Two beats that are the same
    thing, today and yesterday or twice in one day, means her friends are on a
    loop -- the most boring way a simulated life dies."""
    import difflib
    rows = []
    # `cast_beats_prev` only moves over when the DATE changes, so between her
    # midnight and `schedule.generate_at` both records hold the same day and
    # comparing them finds twenty identical beats at ratio 1.00 -- today's plan
    # against itself. The app was fixed for this window; this was not, and it
    # would have cried ABSURD every night for those hours.
    keys = ["cast_beats", "cast_beats_prev"]
    if ((s.kv("cast_beats", {}) or {}).get("date")
            and (s.kv("cast_beats", {}) or {}).get("date") == (s.kv("cast_beats_prev", {}) or {}).get("date")):
        keys = ["cast_beats"]
    for key in keys:
        b = s.kv(key, {}) or {}
        for x in b.get("beats", []):
            txt = (x.get("text") or x.get("ja") or "").strip()
            if txt:
                rows.append((b.get("date", ""), x.get("who", ""), x.get("time", ""), txt))
    if len(rows) < 6:
        return OK, "not enough planned beats to judge", ""
    hits = []
    for i, a in enumerate(rows):
        for b in rows[i + 1:]:
            if a[1] != b[1]:
                continue
            r = difflib.SequenceMatcher(None, a[3][:160], b[3][:160]).ratio()
            if r >= 0.82:
                hits.append(f"{a[1]} {a[0]} {a[2]} vs {b[0]} {b[2]} ({r:.2f})")
    detail = f"{len(rows)} beats compared" + ("; " + "; ".join(hits[:3]) if hits else "")
    if len(hits) >= 4:
        return ABSURD, "her friends are living the same day over again", detail
    if hits:
        return ODD, "the planner wrote the same beat twice", detail
    return OK, "no day of theirs is a copy of another", detail


# ------------------------------------------------------------------ UNSAVED
#
# Where each role's answer ends up. A model call that leaves nothing behind is
# money spent on a thought nobody can ever have again -- which is what was
# happening to `cast_beat`: forty-odd calls a day writing her friends' actual
# Japanese, kept in kv `cast_beats` until the next day's plan overwrote it,
# while the only durable trace was the planner's ENGLISH line in `events`.
#
# ("kv", key)        the key exists and is not empty
# ("kv_day", key)    a dict keyed by date has today in it
# ("table", sql)     the query returns a row for today
# ("none", why)      it deliberately leaves nothing: say why, out loud
SINKS = {
    "director": ("table", "select 1 from scenes where date=? limit 1"),
    "persona": ("table", "select 1 from messages where date=? and role='assistant' limit 1"),
    "editor": ("none", "it edits the bubbles that are then sent and stored"),
    "revise": ("none", "it rewrites a draft that is then sent and stored"),
    "revise_self": ("none", "it rewrites a draft that is then sent and stored"),
    "reconcile": ("none", "it corrects the text that is then sent and stored"),
    "recall": ("none", "it reads the record, it does not add to it"),
    "voice": ("table", "select 1 from events where date=? and kind='voice' limit 1"),
    "gloss": ("table", "select 1 from self_memories where alt!='' limit 1"),
    "him_profile": ("kv", "him_profile"),
    "gossip": ("kv", "gossip"),
    "orbit": ("kv", "orbit"),
    "bond": ("kv", "cast_bonds"),
    "nudge": ("kv", "nudge_last"),
    "wonder_answer": ("kv", "questions"),
    "coherence": ("kv", "coherence_flags"),
    "watch_pick": ("kv", "watchlist"),
    "showrunner": ("kv", "showrunner_last_date"),
    "state": ("table", "select 1 from state_log where date=? limit 1"),
    "cast_beat": ("table", "select 1 from events where date=? and kind='cast' limit 1"),
    "cast_day": ("kv", "cast_beats"),
    "cast_reply": ("kv", "cast_chat"),
    "cast_turn": ("kv", "cast_chat"),
    "cast_life": ("kv", "cast_life"),
    "npc_moment": ("kv", "npc_moments"),
    "cast_arc": ("kv", "cast_arcs"),
    "cast_evolve": ("kv", "cast_arcs"),
    "anticipation": ("kv", "anticipation"),
    "experience": ("table", "select 1 from events where date=? and kind='her_thing' limit 1"),
    "morning": ("kv", "morning_intent"),
    "reflect": ("kv", "reflections"),
    "reflect_cast": ("kv", "reflections"),
    "spiral": ("kv", "spirals"),
    "spiral_settle": ("kv", "spirals"),
    "wonder": ("kv", "questions"),
    "compare": ("kv_day", "compare_counts"),
    "foresee": ("kv", "foresight"),
    "expect_him": ("kv", "expectations"),
    "commit": ("kv", "commitments"),
    "commit_him": ("kv", "commitments"),
    "ick": ("kv", "charged"),
    "graph": ("kv", "social_graph"),
    "lookup": ("kv", "lookups"),
    "lookup_gist": ("kv", "lookups"),
    "phone": ("kv", "phone_last_look_ts"),
    "snoop": ("kv_day", "snoop_counts"),
    "vault": ("table", "select 1 from events where kind='note_read' limit 1"),
    "scenery_judge": ("table", "select 1 from scenery limit 1"),
    "scenery_describe": ("table", "select 1 from scenery limit 1"),
    # today is compiled tonight, so the day to look for is the one before
    "timeline": ("table", "select 1 from days limit 1"),
    "diary": ("kv", "diary"),
    "schedule": ("table", "select 1 from schedules where date=? limit 1"),
    "sleep": ("kv_day", "health_days"),
    # `habits_him` WRITES the habit list; `habits_checked` is the window log
    # that fills later in the day and is pruned to today, so an empty one at
    # 07:00 is the design, not a loss
    "habits_him": ("kv", "habits_him"),
    "approach": ("kv", "approaches"),
    "said_when": ("none", "it dates a thing he said, for the answer being written"),
    "affection": ("kv", "appraisal_levels"),
    "events": ("kv", "event_stances"),
    "intent": ("none", "it decides the shape of the reply being written"),
    "rupture_settle": ("kv", "ruptures"),
    "social": ("table", "select 1 from events where kind='social' limit 1"),
    "x_post": ("kv", "x_post_last_ts"),
    "note_read": ("table", "select 1 from events where kind='note_read' limit 1"),
    "taste": ("kv", "taste_drift"),
    "weekly": ("kv", "weekly_self"),
}


def _calls_today(days=1):
    """Roles that ran, from the run logs -- the only record of a call made."""
    import glob
    import zipfile
    counts = collections.Counter()
    cutoff = time.time() - days * 86400
    sources = []
    for f in glob.glob("logs/*/llm_calls.jsonl"):
        if os.path.getmtime(f) < cutoff:
            continue
        # A tool run makes real calls against a COPY of the save, so its calls
        # land nowhere the live record can see -- and UNSAVED then reports a
        # role that "left nothing behind" when what happened is that a test
        # ran it. The bot connects to a channel; a tool says so in its own log.
        # The bot always writes the narrative; a tool that stubs the logger
        # writes none, so a run with no session.log was never the bot.
        try:
            head = open(os.path.join(os.path.dirname(f), "session.log"),
                        encoding="utf-8", errors="replace").read(4000)
        except OSError:
            continue
        if "console-only mode" in head:
            continue
        sources.append((None, f))
    for z in glob.glob("logs/*.zip"):
        if os.path.getmtime(z) < cutoff:
            continue
        try:
            zf = zipfile.ZipFile(z)
        except (OSError, zipfile.BadZipFile):
            continue
        # the same rule inside a rotated run: a tool's log gets zipped like
        # any other and would otherwise come back in through this door
        try:
            sess = [n for n in zf.namelist() if n.endswith("session.log")]
            head = zf.read(sess[0])[:4000].decode("utf-8", "replace") if sess else ""
        except (OSError, KeyError, zipfile.BadZipFile):
            head = ""
        if not sess or "console-only mode" in head:
            continue
        for n in zf.namelist():
            if n.endswith("llm_calls.jsonl"):
                sources.append((zf, n))
    for zf, name in sources:
        try:
            data = zf.read(name).decode("utf-8", "replace") if zf else open(
                name, encoding="utf-8", errors="replace").read()
        except (OSError, KeyError):
            continue
        for line in data.splitlines():
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("role"):
                counts[d["role"]] += 1
    return counts


def unsaved_calls(cfg, s):
    """A model call whose answer reaches nothing that outlives the day.

    This is the check that would have caught `cast_beat`: nobody had ever
    asked where a beat's words went, and the answer was kv `cast_beats`, which
    tomorrow's plan overwrites."""
    counts = _calls_today()
    if not counts:
        return OK, "no calls in the logs to account for", ""
    date = s.kv("cast_beats", {}).get("date") or ""
    # the calls are a machine day; her record is dated on her clock, and at
    # her morning the plan day is already the new one while last night's
    # calls landed under yesterday's. A sink counts if either day has it.
    dates = [date]
    try:
        import datetime as _dt
        dates.append((_dt.date.fromisoformat(date) - _dt.timedelta(days=1)).isoformat())
    except ValueError:
        pass
    unmapped, empty = [], []
    for role, n in counts.items():
        sink = SINKS.get(role)
        if not sink:
            unmapped.append(f"{role} x{n}")
            continue
        kind, arg = sink
        if kind == "none":
            continue
        try:
            if kind == "kv":
                ok = bool(s.kv(arg))
            elif kind == "kv_day":
                ok = any((s.kv(arg, {}) or {}).get(d) for d in dates)
            else:
                ok = any(s.rows(arg, (d,)) for d in dates) if "?" in arg else bool(s.rows(arg))
        except sqlite3.Error:
            ok = True          # a query that cannot run is a bug in this table
        if not ok:
            empty.append(f"{role} x{n} -> {arg} is empty")
    detail = f"{sum(counts.values())} calls in {len(counts)} roles"
    if unmapped:
        detail += "; nobody has said where these land: " + ", ".join(sorted(unmapped))
    if empty:
        detail += "; " + "; ".join(empty)
    if empty:
        return ABSURD, "a model call today left nothing behind in the record", detail
    if unmapped:
        return ODD, "a model call runs that nothing here accounts for", detail
    return OK, "every call made today landed somewhere that outlives the day", detail



# ------------------------------------------------------------------ REGISTER
#
def register_check(cfg, s):
    """Do the friends still sound like themselves, and like different people
    in different rooms. Reads `tools/register.py` over the stored turns: a
    speaker whose group and one-to-one registers are the same (distance
    under `flat`) and a speaker whose markers moved by half in a week."""
    from tools import register
    from sim import roster
    rows = []
    for ex in (s.kv("cast_chat", []) or []):
        for t in ex.get("turns", []):
            rows.append({"who": t.get("who") or "?", "ja": t.get("ja") or "", "kind": ex.get("kind", ""), "date": ex.get("date", "")})
    if len(rows) < 40:
        return OK, "too few turns to fingerprint yet", f"{len(rows)} turns"
    fp = register.fingerprint(rows)
    flat = 0.06
    con = register.room_contrast(fp)
    same = [f"{w} {v['distance']:.3f}" for w, v in con.items() if v["distance"] < flat]
    dr = register.drift(rows)
    # a voice whose markers all moved UP is its sheet arriving, not a fault:
    # only movement toward the cast mean is flattening
    flattening = [f"{w} {v['distinct_before']:.3f}->{v['distinct_now']:.3f}" for w, v in dr.items() if v["flattening"]]
    detail = ((f"{len(rows)} turns; room contrast " + ", ".join(f"{w} {v['distance']:.2f}" for w, v in sorted(con.items())))
              if con else f"{len(rows)} turns; no speaker has enough in both rooms")
    grew = [f"{w}: {'; '.join(v['moved'][:3])}" for w, v in dr.items() if v["moved"] and not v["flattening"]]
    if grew:
        detail += "; found its own voice this week: " + " | ".join(grew[:3])
    if same or flattening:
        return ODD, "somebody's register has flattened", (detail
                + ("; the same in both rooms: " + ", ".join(same) if same else "")
                + ("; drifting toward everyone else: " + ", ".join(flattening) if flattening else ""))
    return OK, "everybody sounds like themselves, and differently by room", detail


# ------------------------------------------------------------------ PROVENANCE
#
def provenance(cfg, s):
    """Where her memories of the last three days came from. The compile
    writes from the record and has invented (memory 78: a classmate and a
    rumour in no event); the mechanisms that lived a thing -- commitments,
    scenery, ruptures, spirals, goals -- write at the moment. A week in which
    most of what she carries was written by the compile is a week she
    half-made up."""
    try:
        rows = s.rows("select coalesce(source,'compile'), count(*) from self_memories "
                      "where ts > strftime('%s','now') - 3*86400 group by 1")
    except sqlite3.Error:
        return OK, "no source column yet", ""
    total = sum(n for _src, n in rows)
    if not total:
        return OK, "no memories in the last three days", ""
    by = {src: n for src, n in rows}
    compiled = by.get("compile", 0)
    detail = f"{total} in three days: " + ", ".join(f"{k} {v}" for k, v in sorted(by.items(), key=lambda kv: -kv[1]))
    if total >= 6 and compiled / total > 0.7:
        return ODD, "most of what she remembers was written by the compile, not lived", detail
    return OK, "her memories mostly come from the moments that made them", detail


# ------------------------------------------------------------------ LEDGER
#
def ledger_check(cfg, s):
    """Does the day contradict its own ledger: an absent person still in a
    schedule block's `with`, a promise KEPT to somebody who was absent, a
    `with` name the roster does not know. Today's plan day and the day
    before, because at her morning the plan is already tomorrow's."""
    import datetime as _dt
    from sim.ledger import Ledger
    from world.clock import WorldClock
    import json as _json

    class _View:            # the read-only save, shaped like the store the ledger reads
        def get(self, key, default=None):
            return s.kv(key, default)

        def get_schedule(self, date):
            r = s.rows("select date, blocks, notes from schedules where date=?", (date,))
            return {"date": r[0][0], "blocks": _json.loads(r[0][1]), "notes": r[0][2]} if r else None
    st = _View()
    clock = WorldClock(cfg)
    led = Ledger(cfg, st, clock)
    date = (st.get("cast_beats", {}) or {}).get("date") or clock.date_str()
    dates = [date]
    try:
        dates.append((_dt.date.fromisoformat(date) - _dt.timedelta(days=1)).isoformat())
    except ValueError:
        pass
    faults = []
    for d in dates:
        faults += [f"{d} {f}" for f in led.audit(d)]
    absent = sum(len(led.absent(d)) for d in dates)
    settled = sum(len(led.settled(d)) for d in dates)
    detail = f"{absent} absence(s), {settled} settled fact(s) on the ledger over {len(dates)} day(s)"
    if faults:
        return ABSURD, "the day contradicts its own ledger", detail + "; " + "; ".join(faults[:6])
    return OK, "nothing in the day contradicts the ledger", detail


# ------------------------------------------------------------------ STRANGERS
#
def strangers(cfg, s):
    """The people who are not her friends, and the ways that goes wrong.

    Five things, all of which have happened or nearly did while this was being
    built: a face standing somewhere that kind of place cannot hold, the same
    person on the record twice, a stranger wearing a name her roster owns
    (a classmate called あや IS her confidante to everything that reads the
    record), a moment with nothing in it, and more of them in a day than the
    cap allows."""
    from tomoe.npc import _WHO_IS_THERE, _AT_A_FRIENDS
    from sim import roster
    faces = s.kv("npcs", {}) or {}
    moments = s.kv("npc_moments", []) or []
    if not faces and not moments:
        return OK, "she has not run into anybody yet", "nothing on the record"
    bad = []
    # 1. somebody who could not be there
    for fid, f in faces.items():
        kind, role = f.get("kind", ""), f.get("role", "")
        pop = _AT_A_FRIENDS if (kind == "home" and f.get("place") != "home") else _WHO_IS_THERE.get(kind, [])
        if role and pop and role not in [r for r, _w in pop]:
            bad.append(f"{f.get('label', fid)} is {role!r} at a {kind}")
    # 2. one person, two rows
    seen = {}
    for fid, f in faces.items():
        for nm in {str(f.get("ja") or "").strip().lower(), str(f.get("label") or "").strip().lower()} - {""}:
            k = (f.get("place", ""), nm)
            if k in seen:
                bad.append(f"{f.get('label', fid)} is on the record twice at {f.get('place')}")
            seen[k] = fid
    # 3. a stranger wearing a name she already knows
    for fid, f in faces.items():
        for nm in (f.get("ja"), f.get("name")):
            if nm and roster.role_of(cfg, nm):
                bad.append(f"a stranger is called {nm!r}, which is her {roster.role_of(cfg, nm)}")
    # 4. a moment with nothing in it
    empty = [m for m in moments if not m.get("lines") and not m.get("what")]
    if empty:
        bad.append(f"{len(empty)} moment(s) with neither words nor anything that happened")
    # 5. more in a day than the cap
    cap = int(getattr(cfg.npc, "max_per_day", 4) or 4)
    per = collections.Counter(m.get("date", "") for m in moments)
    over = [f"{d} had {n}" for d, n in per.items() if n > cap]
    if over:
        bad.append("past the daily cap: " + ", ".join(over[:3]))
    bad = list(dict.fromkeys(bad))       # one fault, said once
    days = len(per) or 1
    detail = (f"{len(faces)} face(s), {len(moments)} moment(s) over {days} day(s), "
              f"{sum(per.values()) / days:.1f} a day (cap {cap})"
              + ("; " + "; ".join(bad[:4]) if bad else ""))
    if len(bad) >= 3:
        return ABSURD, "the people she meets are not people", detail
    if bad:
        return ODD, "something is off about the strangers", detail
    return OK, "the strangers are where strangers are", detail



# ------------------------------------------------------------------ REPEATS
#
def repeats(cfg, s):
    """Anybody saying the same thing twice.

    This is the most persistent fault in the project and every instance of it
    has been found BY HAND: Aya sending the same three-bubble block four times
    in twenty minutes, the afterthought paraphrasing the burst it followed,
    Hinako asking about the flea market three ways, her own spoken line
    repeated three minutes later with the punctuation moved. Each was fixed
    where it happened -- `drop_repeats`, `near_duplicate` against her last six,
    `no_repeat_own_turns`, `tts.no_repeat_recent` -- and nothing was watching
    for the next one. A model with no sight of what it just said will always
    drift back here, so this is the check that has to exist rather than another
    guard in another prompt.

    Compared per SPEAKER within one day, so two people agreeing is not a
    repeat. `near_duplicate` ignores anything under twelve characters, which is
    what stops 「うん」 twice from counting."""
    from sim.textutil import near_duplicate
    # the last two days only. Scanning the whole kept record would hold this
    # red on a fault already fixed, for as long as `exchange.keep` remembers
    # the day it happened on -- and a check that cannot go green is a check
    # nobody reads.
    recent = {(datetime.date.today() - datetime.timedelta(days=k)).isoformat() for k in (0, 1)}
    said = {}

    def add(who, when, text):
        if text and len(str(text)) >= 12 and when in recent:
            said.setdefault((who, when), []).append(str(text))

    for x in (s.kv("cast_chat", []) or []):
        for t in x.get("turns", []) or []:
            add(t.get("who", "?"), x.get("date", ""), t.get("ja") or t.get("text"))
    try:
        for r in s.rows("select date, text from messages where role='assistant' order by id desc limit 200"):
            add("HER to him", r[0], r[1])
    except Exception:
        pass
    try:
        for r in s.rows("select date, text from events where kind='voice' order by ts desc limit 120"):
            add("HER out loud", r[0], r[1])
    except Exception:
        pass

    worst, pairs = [], 0
    for (who, when), lines in said.items():
        for i in range(len(lines)):
            for j in range(i + 1, len(lines)):
                if near_duplicate(lines[i], lines[j], 0.80):
                    pairs += 1
                    worst.append(f"{who} on {when}: {lines[j][:44]!r}")
    detail = f"{pairs} repeat(s) across {len(said)} speaker-day(s) in the last two days" + (
        "; " + "; ".join(worst[:3]) if worst else "")
    if pairs >= 8:
        return ABSURD, "people are saying the same things over and over", detail
    if pairs >= 3:
        return ODD, "somebody is repeating themselves", detail
    return OK, "nobody says the same thing twice", detail


# -------------------------------------------------------------------- GROUP
#
def group_quality(cfg, s):
    """Is the group chat a group of teenagers or a committee?

    `one_sided` catches a conversation nobody answered and VOLUME catches one
    that is too quiet. Neither catches the thing that was actually wrong on
    2026-08-28: fifty-one messages between four girls of which every single one
    was about the meeting time -- 明日 21, 10時 16, 日曜 11, 手帳 8, and not one
    joke, photo, complaint about the heat or piece of gossip. A group chat is a
    room they live in, not an agenda, and a day of pure logistics is the shape
    to catch.

    Also the SHAPE of the day: turn counts of 15, 1, 11, 51, 1, 1, 1 say the
    group only exists when she is in it. Both are read off the record rather
    than guessed at."""
    day = datetime.date.today().isoformat()
    rows = [x for x in (s.kv("cast_chat", []) or []) if x.get("kind") == "group"]
    if len(rows) < 3:
        return OK, "not enough group chat to judge", f"{len(rows)} exchange(s) on file"
    by_day = {}
    for x in rows:
        by_day.setdefault(x.get("date", ""), []).append(x)
    when = max(by_day)
    todays = by_day[when]
    turns = [t for x in todays for t in x.get("turns", []) or []]
    counts = [len(x.get("turns", []) or []) for x in todays]
    # a message about arrangements says so: a time, a day, a meeting word
    PLAN = ("時", "明日", "あした", "日曜", "土曜", "集合", "待ち合わせ", "予定", "手帳",
            "何時", "行く?", "行ける", "駅で")
    plan = sum(1 for t in turns if any(w in (t.get("ja") or "") for w in PLAN))
    share = plan / len(turns) if turns else 0
    stubs = sum(1 for n in counts if n <= 1)
    detail = (f"{when}: {len(todays)} exchange(s), turns {counts}, "
              f"{plan}/{len(turns)} messages about arrangements ({share:.0%}), {stubs} stub(s)")
    if turns and share >= 0.85:
        return ABSURD, "their group chat is nothing but arrangements", detail
    if (turns and share >= 0.70) or stubs >= max(3, len(todays) // 2):
        return ODD, "the group reads more like a committee than a chat", detail
    return OK, "their group chat has a life outside the plan", detail



# --------------------------------------------------------------------- KEYS
#
def dual_keys(cfg, s):
    """Can a memory be found from a cue in the other language?

    `self_memories.alt` is the second search key, and three things can go wrong
    with it quietly. It can be MISSING, and a store where only some rows are
    dual-keyed favours whichever ones have it. It can come back in the SAME
    language as the memory, which is not a key at all -- it just doubles the
    tokens it already had. And it can come back in Chinese: one of the first
    sixty-nine did, 「彩的备用自动铅笔」, simplified and with Aya renamed 彩.

    `SelfMemory.gloss` guards all three at write time. This is the check that
    the guard is holding, because the failure is silent -- nothing breaks, she
    simply stops being able to remember things in one direction."""
    import json as _json
    import re as _re
    rows = s.rows("select rowid, text, alt from self_memories")
    if not rows:
        return OK, "she has no memories of her own yet", ""

    # counted, not sniffed: a memory of English prose quoting 「おやすみ」 is
    # English, and a presence test called it Japanese and cried wolf on a good
    # gloss the first time this ran
    from tomoe.cast import is_japanese

    def cjk(t):
        return is_japanese(str(t or ""))

    try:
        with open(cfg.character.voice_rules_file, "r", encoding="utf-8") as fh:
            pat = _re.compile([r for r in _json.load(fh)["_all"]["rules"]
                               if r["id"] == "simplified-chinese"][0]["find"])
    except Exception:
        pat = None
    missing = [r for r in rows if not str(r[2] or "").strip()]
    same, chinese = [], []
    for _rid, text, alt in rows:
        if not str(alt or "").strip():
            continue
        if cjk(text) == cjk(alt):
            same.append(str(text)[:40])
        if pat and pat.search(str(alt)):
            chinese.append(str(alt)[:40])
    have = len(rows) - len(missing)
    detail = (f"{have}/{len(rows)} dual-keyed"
              + (f"; {len(same)} gloss(es) in the same language as the memory" if same else "")
              + (f"; {len(chinese)} in Chinese: {chinese[0]}" if chinese else ""))
    if chinese or len(same) >= 3:
        return ABSURD, "her second language key is wrong, not just missing", detail
    if same or len(missing) > max(3, len(rows) // 5):
        return ODD, "some of her memories can only be found in one language", detail
    return OK, "her memories can be found in either language", detail


# ---------------------------------------------------------------- UNHEARD

def unheard(cfg, s):
    """Forty statuses compete for sixteen lines. A source the gate is
    offered every call and admits in none is a mechanism alive in the
    store and absent from her -- a dead line with a config block. The
    tally is kept by `Attention._tally`; covered lines (a heavier source
    said it) are the design and are not counted against a source."""
    from sim.attention import Attention
    days = int(getattr(cfg.attention, "unheard_days", 7) or 7)
    min_offers = int(getattr(cfg.attention, "unheard_min_offers", 8) or 8)
    tot = Attention.tally_totals(s.kv("attention_tally", {}) or {}, days)
    if not tot:
        return OK, "the gate has not kept a tally yet", ""
    # a source retired from a room stops being offered; its old zeros must
    # not keep the check red for a week (a check that cannot go green once
    # a fault is fixed is a check nobody reads)
    recent = Attention.tally_totals(s.kv("attention_tally", {}) or {}, 2)
    never, rare, detail = [], [], []
    for room, srcs in tot.items():
        who = "him" if room == "him" else "them"
        for src, (off, adm, slot, cov) in srcs.items():
            if src in set(getattr(cfg.attention, "unheard_ok", ()) or ()):
                continue      # dead-on-average by design; the cue bonus lifts it
            r = (recent.get(room, {}) or {}).get(src, [0, 0, 0, 0])
            if r[0] - r[3] <= 0:
                continue      # not offered any more: retired, not unheard
            live = off - cov
            if live < min_offers:
                continue
            if adm == 0:
                never.append(f"{src} ({who}: {live} offers)")
            elif live >= 3 * min_offers and adm / live < 0.05:
                rare.append(f"{src} ({who}: {adm} of {live})")
    if never:
        detail = "never admitted: " + ", ".join(never) + ("; barely: " + ", ".join(rare) if rare else "")
        if len(never) >= 3:
            return ABSURD, "several things she carries never reach her", detail
        return ODD, "a thing she carries never reaches her", detail
    if rare:
        return ODD, "a thing she carries almost never reaches her", "barely: " + ", ".join(rare)
    n = sum(len(v) for v in tot.values())
    return OK, f"everything she is handed reaches her at least sometimes ({n} sources over {days} days)", ""


# ------------------------------------------------------------------ SEAMS

def seams(cfg, s):
    """The day read as one story (`sim/coherence.py`, at the compile): a
    contradiction, an invented thing, a repeat. Flag only; a seam is a
    signal about a prompt or a mechanism, and this is where it is read."""
    days = int(getattr(cfg.coherence, "absurd_days", 2) or 2)
    rows = s.kv("coherence_flags", []) or []
    if not rows:
        return OK, "the day has not been read as a story yet", ""
    lo = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    recent = [r for r in rows if str(r.get("date", "")) >= lo]
    if not recent:
        return OK, f"the last {days} day(s) hold together as a story", ""
    loud = [r for r in recent if int(r.get("severity", 1)) >= 2]
    detail = "; ".join(f"{r.get('date')} s{r.get('severity')} {r.get('kind')} ({r.get('where', '')}): {str(r.get('what', ''))[:110]}"
                       for r in sorted(recent, key=lambda r: -int(r.get("severity", 1)))[:6])
    if len(loud) >= 5:
        return ABSURD, "the day does not hold together as a story", detail
    if loud:
        return ODD, "the day has a seam a reader would notice", detail
    return OK, f"only small seams in the last {days} day(s)", detail


CHECKS = [
    ("DEAD GATE", dead_gauge_gates),
    ("FROZEN", frozen_unread),
    ("FROZEN", frozen_exchange),
    ("NEVER FIRED", never_fired),
    ("UNREACHED", unreached_fields),
    ("VOLUME", message_volume),
    ("VOLUME", one_sided),
    ("SILENCE", waking_silence),
    ("ONE VOICE", one_voice),
    ("PARROT", parrot),
    ("GHOST PLACE", ghost_place),
    ("MONEY", money_sense),
    ("DROPPED", dropped_person),
    ("REPEAT BEAT", repeat_beat),
    ("UNSAVED", unsaved_calls),
    ("STRANGERS", strangers),
    ("REPEATS", repeats),
    ("GROUP", group_quality),
    ("KEYS", dual_keys),
    ("LEDGER", ledger_check),
    ("PROVENANCE", provenance),
    ("REGISTER", register_check),
    ("UNHEARD", unheard),
    ("SEAMS", seams),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/world.db")
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()

    cfg = Config(a.config)
    s = Save(a.db)
    print(f"absurdity audit of {a.db}\n")
    counts = collections.Counter()
    for kind, fn in CHECKS:
        try:
            level, headline, detail = fn(cfg, s)
        except Exception as e:
            level, headline, detail = ODD, f"the check itself failed: {type(e).__name__}: {e}", ""
        counts[level] += 1
        mark = {OK: "  ok  ", ODD: "  ODD ", ABSURD: " !!!! "}[level]
        print(f"{mark}{kind:<12} {headline}")
        if detail and (a.verbose or level != OK):
            print(f"              {detail}")
    print()
    if counts[ABSURD]:
        print(f"{counts[ABSURD]} absurd, {counts[ODD]} odd, {counts[OK]} fine.")
        print("An ABSURD line is something no fifteen-year-old would do. It is not a")
        print("crash and no test will catch it; it wants a person to look.")
    elif counts[ODD]:
        print(f"{counts[ODD]} odd, {counts[OK]} fine. Nothing impossible.")
    else:
        print("nothing absurd.")
    return 1 if counts[ABSURD] else 0


if __name__ == "__main__":
    sys.exit(main())
