"""Take the owner's interior out of a promoted character's save.

A character promoted out of somebody else's cast starts from a copy of that
character's save (`docs/shared-world.md` §7). What is copied is not only the
world she is now in and may read: it is the other girl's household, the other
girl's bonds with her own mother and brother, the pressures a showrunner wrote
over the other girl's record, and the threads her director left open. On
2026-09-07 the first character's promoted friend was running with a bond to
herself under her own nickname, four arcs opened about a man she has no chat
with and about her own name in the third person, and an open thread whose
people were three girls she is one of.

The rule is the roster (`sim/roster.py`): after her own row folds into her own
entry and the world file's keeper becomes a person on it, the roster is the
whole statement of who exists for her. This takes out of the save everything
that names somebody it does not have, everything that names HER as though she
were somebody else, and the day that was planned before her own fills were
hers:

  the bonds  -- a row that resolves to herself, a row naming somebody the
                roster has never heard of, a row for a member of the OWNER's
                household (her household is her own file's, and a mother in
                the world's cast is the world owner's mother), and the row for
                the man she has no chat with when her sheet says so;
  the arcs   -- all of them: the writer of arcs is off for a character who
                does not keep her world, so every arc in her save was written
                by a run that predates the rule, over the other girl's record;
  the threads-- a row whose people name her, or name somebody off the roster;
  the day    -- the schedule and the scenes for today and after, when they
                were written before this pass, because they were written under
                fills that named another girl's ward, station and family; her
                own boot plans the day again from her real ones;
  the plan   -- what the day settled, filtered to lines her own circle could
                know, and beats written for people who are not hers;
  the orbit  -- relatives seeded out of the world's cast file by a register
                that is switched off for her.

Nothing is edited in place and nothing is deleted before it is written out:
the rows go to a file under `data/retired/` first, whole, and a person can
read them. `tomoe/app.py retire_owner_interior_once` runs this at her next
boot behind kv `owner_interior_retired`. On a stopped save it is a command:

    python tools/promoted_save_retire.py --config config_rena.json [--apply]

Nobody is named here. Which character this is comes from the config it is
pointed at.
"""
import argparse
import datetime
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim import roster

# The kv that says this ran. Read before anything is touched, written after.
MARKER = "owner_interior_retired"
# and the kv for the second pass below, which is separate because the first one
# had already run on a live save before the second was written
MARKER_METERS = "meters_reconciled"
# what a `people` column may say that is not a person
NOT_A_PERSON = {"", "alone", "nobody", "no one", "none", "her", "she", "herself",
                "the group", "everyone", "everybody",
                # the room she is in rather than anybody in it. The writer of a
                # thread copies the ledger's who-she-is-with, and "class" is
                # eight of the world owner's own rows; the fourth character's
                # first one made this check fail on a save with nothing wrong
                # in it.
                "class", "the class"}


def _decode(text):
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return {"_raw": text}


def _kv(conn, key, default=None):
    row = conn.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
    return _decode(row[0]) if row else default


def _no_such_person(config, name):
    """Does this name mean nobody on her roster? Generic words a `people`
    column uses for an empty room are not names and are not looked up."""
    n = str(name or "").strip()
    if n.lower() in NOT_A_PERSON:
        return False
    return not roster.role_of(config, n)


def bonds_to_drop(config, rels):
    """(key, why) for every relationship row that is not hers to hold."""
    with_him = str(getattr(getattr(config.character, "existence", None), "with_him", "") or "").lower()
    out = []
    for key, r in (rels or {}).items():
        if not isinstance(r, dict):
            continue
        name = str(r.get("name") or key)
        role = str(r.get("role_id") or "")
        if roster.is_self(config, key) or roster.is_self(config, name):
            out.append((key, "this is her: a bond with herself, under the name the world's "
                             "cast files her by"))
            continue
        if role == "partner" and with_him == "none":
            out.append((key, "she has no chat with him at all (her sheet's `with_him`), and the "
                             "row is the other girl's side of one"))
            continue
        if _no_such_person(config, key) and _no_such_person(config, name):
            out.append((key, "nobody on her roster goes by this name"))
            continue
        # whose family: the roster answers whether this person is family
        # (`sim/roster.py:is_family`, a flag on the row or the five role ids)
        # and whether she is one of HER people; a family row that is not hers
        # is the world owner's household
        if roster.is_family(config, key) and not roster.is_own(config, key):
            out.append((key, "the household in the world's cast is the world owner's; hers is "
                             "her own file's"))
    return out


def bonds_to_add(config, rels):
    """(key, row) for everybody the roster has and the meters have not.

    The other direction of the same reconciliation. The seed ran once, from
    the cast file read raw, and the girl whose world she reads is that file's
    KEEPER rather than one of its people -- so the one person she is at school
    with every day, and whose paragraph is in her own voice file, had no meter
    at all. `sim/roster.py:meter_rows` is the same statement of who she may
    hold a meter on that a fresh save is now seeded from, so a save repaired
    here and a save seeded today hold the same rows."""
    want, _refused = roster.meter_rows(config)
    return [(k, v) for k, v in want.items() if k not in (rels or {})]


def sentiments_to_drop(config, rels, sents):
    """(key, why) for every sentiment row about somebody who is not in the
    meters.

    What each person is to her is seeded once from the meters and moves with
    what happens; a row about somebody the meters no longer have is a feeling
    about a person who is not in her life. The first pass took the bonds and
    left these, so her save still held what she felt about the world owner's
    mother, father and brother, about a man she has no chat with, and about
    herself under two names."""
    out = []
    for key in list(sents or {}):
        if key in (rels or {}):
            continue
        if roster.is_self(config, key):
            out.append((key, "this is her: what she feels about herself, filed as a person"))
        elif _no_such_person(config, key):
            out.append((key, "nobody on her roster goes by this name"))
        else:
            out.append((key, "she holds no meter on this person any more"))
    return out


def threads_to_drop(config, rows):
    out = []
    for t in rows:
        people = [p.strip() for p in str(t.get("people") or "").replace("、", ",").split(",")]
        why = ""
        for p in people:
            if p and roster.is_self(config, p):
                why = "she is listed as one of the people in it: written about another girl's day"
                break
            if _no_such_person(config, p):
                why = "it names %r, who is nobody on her roster" % p
                break
        if why:
            out.append((t, why))
    return out


def collect(conn, config, today):
    """Everything this pass would move, read and decided and not yet touched."""
    rels = _kv(conn, "relationships", {}) or {}
    bonds = bonds_to_drop(config, rels)
    arcs = _kv(conn, "arcs", None)
    cols = ("id", "text", "status", "people", "created_ts", "updated_ts", "created_date", "resolved_date")
    threads = [dict(zip(cols, r)) for r in conn.execute(
        "SELECT id, text, status, people, created_ts, updated_ts, created_date, resolved_date FROM threads")]
    days = [r[0] for r in conn.execute("SELECT date FROM schedules WHERE date>=? ORDER BY date", (today,))]
    scenes = conn.execute("SELECT COUNT(*) FROM scenes WHERE date>=?", (today,)).fetchone()[0]
    beats = {}
    for k in ("cast_beats", "cast_beats_prev"):
        rec = _kv(conn, k, None)
        if isinstance(rec, dict) and rec:
            beats[k] = rec
    return {
        "bonds": bonds,
        "arcs": arcs,
        "threads": threads_to_drop(config, threads),
        "schedules": days,
        "scenes": scenes,
        "beats": beats,
        "orbit": _kv(conn, "orbit", None) if not config.orbit.enabled else None,
        "relationships_before": rels,
    }


def _clean_beats(config, rec):
    """A day's plan with what her own circle cannot know taken out of it.

    Every settled line, and a beat written for somebody who is not one of her
    own people. Every line, rather than only the ones that name a name,
    because the planner that wrote them was reading the world's open threads:
    "the flea market on Thursday with the group -- carried from yesterday"
    names nobody and is the school's plan, and it reached a friend at another
    school as the thing her day had fixed. What the world settled reaches her
    through the day's one truth (`sim/ledger.py`), which reads the world file;
    her own plan's settled lines are her own circle's from here."""
    out = dict(rec)
    settled = [s for s in (rec.get("settled") or []) if isinstance(s, str)]
    out["settled"] = []
    beats = [b for b in (rec.get("beats") or []) if isinstance(b, dict)]
    out["beats"] = [b for b in beats if roster.is_own(config, str(b.get("who") or ""))]
    dropped = (len(settled) - len(out["settled"])) + (len(beats) - len(out["beats"]))
    return out, dropped


def retire(conn, config, out_path, today, apply=True, log=print):
    """Move it all out. Returns a summary; writes `out_path` first."""
    got = collect(conn, config, today)
    moved = {"when": datetime.datetime.now().isoformat(timespec="seconds"),
             "today": today,
             "bonds": {k: got["relationships_before"].get(k) for k, _w in got["bonds"]},
             "bonds_why": {k: w for k, w in got["bonds"]},
             "arcs": got["arcs"],
             "threads": [t for t, _w in got["threads"]],
             "threads_why": {str(t["id"]): w for t, w in got["threads"]},
             "schedules": [], "scenes": [], "beats": got["beats"], "orbit": got["orbit"]}
    for d in got["schedules"]:
        for r in conn.execute("SELECT date, ts, blocks, notes FROM schedules WHERE date=?", (d,)):
            moved["schedules"].append({"date": r[0], "ts": r[1], "blocks": _decode(r[2]), "notes": r[3]})
    cols = ("id", "ts", "date", "hm", "location", "activity", "phone_access", "with_who",
            "sensory", "inner", "share_worthy", "events", "raw")
    for r in conn.execute("SELECT %s FROM scenes WHERE date>=? ORDER BY id" % ", ".join(cols), (today,)):
        moved["scenes"].append(dict(zip(cols, r)))

    n_beats = 0
    beats_after = {}
    for k, rec in got["beats"].items():
        cleaned, dropped = _clean_beats(config, rec)
        n_beats += dropped
        if dropped:
            beats_after[k] = cleaned

    summary = {"file": out_path, "bonds": len(moved["bonds"]),
               "arcs": len(got["arcs"] or []) if isinstance(got["arcs"], list) else 0,
               "threads": len(moved["threads"]), "schedules": len(moved["schedules"]),
               "scenes": len(moved["scenes"]), "beat_lines": n_beats,
               "orbit": len((got["orbit"] or {}).get("people", []) or []) if got["orbit"] else 0}
    if not any(summary[k] for k in ("bonds", "arcs", "threads", "schedules", "scenes",
                                    "beat_lines", "orbit")):
        log("nothing of the owner's interior is left in this save")
        return dict(summary, file="")

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(moved, f, ensure_ascii=False, indent=1)
    for k, w in got["bonds"]:
        log("bond %s: %s" % (k, w))
    for t, w in got["threads"]:
        log("thread %s: %s" % (t["id"], w))
    if not apply:
        log("nothing was changed (--apply to move it)")
        return summary

    rels = dict(got["relationships_before"])
    for k, _w in got["bonds"]:
        rels.pop(k, None)
    # INSERT OR REPLACE, the way the store's own writer does it: a save whose
    # meters have been seeded in memory and not yet written has no row here at
    # all, and an UPDATE against a missing row changes nothing and says
    # nothing. A world reader's FIRST boot then reloaded her meters out of a
    # save that had none and came up with an empty set.
    conn.execute("INSERT OR REPLACE INTO kv(key,value) VALUES(?,?)",
                 ("relationships", json.dumps(rels, ensure_ascii=False)))
    if got["arcs"] is not None:
        conn.execute("DELETE FROM kv WHERE key=?", ("arcs",))
    for t, _w in got["threads"]:
        conn.execute("DELETE FROM threads WHERE id=?", (t["id"],))
    conn.execute("DELETE FROM schedules WHERE date>=?", (today,))
    conn.execute("DELETE FROM scenes WHERE date>=?", (today,))
    for k, rec in beats_after.items():
        conn.execute("INSERT OR REPLACE INTO kv(key,value) VALUES(?,?)",
                     (k, json.dumps(rec, ensure_ascii=False)))
    if got["orbit"] is not None:
        conn.execute("DELETE FROM kv WHERE key=?", ("orbit",))
    conn.commit()
    return summary


def reconcile_meters(conn, config, out_path, today, apply=True, log=print):
    """The second pass: the meters, the sentiments and the days planned before
    her own material was hers.

    The first pass took out what was the other girl's. This one settles what is
    left against the roster as it now resolves, and it is separate because the
    first had already run on a live save before this was written:

      the meters     -- a row the roster no longer has goes, and a row the
                        roster has and the meters have not is added at her own
                        sheet's opening values;
      the sentiments -- the same list, one step behind: they are seeded once
                        from the meters and the first pass did not touch them,
                        so what she felt about the world owner's household was
                        still there after the bonds were gone;
      the days       -- every schedule written before this pass ran, today's
                        included, because today's was written from the world
                        owner's map and the world owner's household and the
                        day after it is written from the day before it. Her own
                        boot plans today again from her own material; the
                        scenes for today go with it, the way the first pass
                        takes them, and the days already lived stay.

    The rows are written out whole before anything is deleted, the way the
    first pass writes them."""
    import time
    rels = _kv(conn, "relationships", {}) or {}
    sents = _kv(conn, "sentiments", {}) or {}
    drop = bonds_to_drop(config, rels)
    add = bonds_to_add(config, rels)
    after = {k: v for k, v in rels.items() if k not in {k2 for k2, _w in drop}}
    after.update(dict(add))
    sdrop = sentiments_to_drop(config, after, sents)
    days = [r[0] for r in conn.execute("SELECT date FROM schedules WHERE date<=? ORDER BY date",
                                       (today,))]
    moved = {"when": datetime.datetime.now().isoformat(timespec="seconds"), "today": today,
             "bonds_dropped": {k: rels.get(k) for k, _w in drop},
             "bonds_dropped_why": {k: w for k, w in drop},
             "bonds_added": dict(add),
             "sentiments_dropped": {k: sents.get(k) for k, _w in sdrop},
             "sentiments_dropped_why": {k: w for k, w in sdrop},
             "schedules": [], "scenes": []}
    for d in days:
        for r in conn.execute("SELECT date, ts, blocks, notes FROM schedules WHERE date=?", (d,)):
            moved["schedules"].append({"date": r[0], "ts": r[1], "blocks": _decode(r[2]),
                                       "notes": r[3]})
    cols = ("id", "ts", "date", "hm", "location", "activity", "phone_access", "with_who",
            "sensory", "inner", "share_worthy", "events", "raw")
    if days:
        for r in conn.execute("SELECT %s FROM scenes WHERE date>=? ORDER BY id"
                              % ", ".join(cols), (today,)):
            moved["scenes"].append(dict(zip(cols, r)))
    summary = {"file": out_path, "bonds_dropped": len(drop), "bonds_added": len(add),
               "sentiments_dropped": len(sdrop), "schedules": len(moved["schedules"]),
               "scenes": len(moved["scenes"])}
    if not any(summary[k] for k in ("bonds_dropped", "bonds_added", "sentiments_dropped",
                                    "schedules")):
        log("her meters, what each of them is to her and her days already agree with her roster")
        return dict(summary, file="")

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(moved, f, ensure_ascii=False, indent=1)
    for k, w in drop:
        log("meter %s dropped: %s" % (k, w))
    for k, _row in add:
        log("meter %s added: on her roster and not in her meters, at her sheet's opening values" % k)
    for k, w in sdrop:
        log("what %s is to her dropped: %s" % (k, w))
    if days:
        log("%d day(s) of plan and %d scene(s) written before this pass: %s"
            % (len(days), len(moved["scenes"]), ", ".join(days)))
    if not apply:
        log("nothing was changed (--apply to move it)")
        return summary

    # the sentiment row a newly added meter gets is the row the seed would have
    # written for her, from the same formula (`sim/sentiment.py:seed_row`)
    from sim import sentiment as sentiment_mod
    now = time.time()
    sents_after = {k: v for k, v in sents.items() if k not in {k2 for k2, _w in sdrop}}
    for k, row in add:
        if k not in sents_after:
            sents_after[k] = sentiment_mod.seed_row(config.sentiment, row, now)
    conn.execute("INSERT OR REPLACE INTO kv(key,value) VALUES(?,?)",
                 ("relationships", json.dumps(after, ensure_ascii=False)))
    if sents:
        conn.execute("INSERT OR REPLACE INTO kv(key,value) VALUES(?,?)",
                     ("sentiments", json.dumps(sents_after, ensure_ascii=False)))
    if days:
        conn.execute("DELETE FROM schedules WHERE date<=?", (today,))
        conn.execute("DELETE FROM scenes WHERE date>=?", (today,))
    conn.commit()
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", required=True, help="her config, which names her roster and her save")
    ap.add_argument("--db", default="", help="her save; her config's own by default")
    ap.add_argument("--out", default="", help="where the rows go; data/retired/<ts>_promoted/<db>.json by default")
    ap.add_argument("--date", default="", help="the first day to re-plan; today by default")
    ap.add_argument("--apply", action="store_true", help="move it (otherwise print and touch nothing)")
    args = ap.parse_args(argv)

    import config as configmod
    c = configmod.Config(args.config)
    db = args.db or str(c.logging.db_path)
    today = args.date or datetime.date.today().isoformat()
    stem = os.path.splitext(os.path.basename(db))[0] or "save"
    out = args.out or os.path.join("data", "retired",
                                   datetime.datetime.now().strftime("%Y%m%d_%H%M") + "_promoted",
                                   stem + ".json")
    conn = sqlite3.connect(db)
    s = retire(conn, c, out, today, apply=args.apply)
    print(json.dumps(s, ensure_ascii=False, indent=1))
    m = reconcile_meters(conn, c, out.replace(".json", "_meters.json"), today, apply=args.apply)
    print(json.dumps(m, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
