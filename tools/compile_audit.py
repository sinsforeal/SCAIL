"""The nightly compile, run end to end on a copy of a save and checked
against the record.

    python tools/compile_audit.py --date 2026-09-03
    python tools/compile_audit.py --date 2026-09-03 --config config_yukarin.json --db data/yukarin.db

Builds the App the way the loop does (`tools/harness.build_on`), takes a
census of everything the compile writes, calls `App.compile(date)` -- the
whole path, backup and program hooks and all -- then takes the census again
and prints one line per output with what it wrote. `--twice` runs the compile
a second time on the same copy, which is what `/compile <date>` does, and
reports what doubled.

It spends: the day role, the cards role, the coherence role and whatever the
settlers ask for. A few cents a character.
"""
import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools import harness  # noqa: E402


# ---------------- the census ----------------

def _sql(app, q, args=()):
    with app.store.lock:
        return app.store.conn.execute(q, args).fetchall()


def census(app, date):
    """Everything the compile can write, counted."""
    st, c = app.store, {}
    c["days"] = {r["date"]: (len(r["narrative"] or ""), len(r["summary"] or ""))
                 for r in _sql(app, "SELECT * FROM days")}
    c["day_row"] = st.get_day(date)
    c["user_facts"] = [r["fact"] for r in _sql(app, "SELECT fact FROM user_facts ORDER BY id")] \
        if _has_col(app, "user_facts", "id") else st.user_facts()
    c["self_memories"] = [(r["rid"] if "rid" in r.keys() else r["id"], r["text"])
                          for r in _sql(app, "SELECT * FROM self_memories")]
    c["cast_facts"] = [(r["who"], r["fact"]) for r in _sql(app, "SELECT who, fact FROM cast_facts")]
    c["episodes"] = [dict(r) for r in _sql(app, "SELECT * FROM episodes WHERE date=? ORDER BY start_ts", (date,))]
    c["episodes_all"] = len(_sql(app, "SELECT id FROM episodes"))
    c["embeddings"] = {r[0]: r[1] for r in _sql(app, "SELECT kind, COUNT(*) FROM embeddings GROUP BY kind")}
    c["self_claims"] = st.get("self_claims", [])
    c["places"] = st.get("places", [])
    c["arcs"] = st.get("arcs", [])
    c["diet"] = st.get("media_diet", [])
    c["goals"] = st.get("goals", [])
    c["coherence"] = st.get("coherence_flags", [])
    c["worldshare"] = st.get("him_share", {})
    c["weekly_self"] = st.get("weekly_self", [])
    c["compiled_dates"] = st.get("compiled_dates", [])
    c["relationships"] = str(app.state.relationships or "")
    c["exposure_his"] = _exposure(app)
    c["kv_keys"] = len(_sql(app, "SELECT key FROM kv"))
    return c


def _has_col(app, table, col):
    try:
        return any(r[1] == col for r in _sql(app, f"PRAGMA table_info({table})"))
    except Exception:
        return False


def _exposure(app):
    prim = getattr(app.state, "primitives", None)
    if prim is None:
        return None
    try:
        return round(float(prim.get(app.state._him_key() or "him", "exposure_his")), 4)
    except Exception as e:
        return f"unreadable: {type(e).__name__}: {e}"


# ---------------- the checks ----------------

def _norm(s):
    import re
    return re.sub(r"[\s　「」『』\"'“”‘’、。,.!?！？…・\-–—]+", "", str(s or "")).lower()


def check_anchors(app, date):
    """Every anchor of every card of the day, against the episode's own text."""
    from sim.cards import Cards
    segs = {}
    for i, s in enumerate(app.episodes.segment(date), 1):
        segs[(s["room"], round(s["start_ts"]))] = _norm(" ".join(t for _, _, t in s["lines"]))
    ok = bad = 0
    misses = []
    for r in app.episodes.for_date(date):
        body = segs.get((r["room"], round(r["start_ts"])))
        if body is None:                     # match on room alone if the ts drifted
            body = next((v for (room, _), v in segs.items() if room == r["room"]), "")
        for a in Cards.anchors_of(r):
            if _norm(a.get("text", "")) and _norm(a.get("text", "")) in body:
                ok += 1
            else:
                bad += 1
                misses.append((r["room"], a.get("text", "")[:80]))
    return ok, bad, misses


def check_language(app, memories):
    """Her memories in the language she writes."""
    import re
    ja = str(getattr(app.config.character, "writes_to_him", "english")).lower().startswith("ja")
    out = []
    for rid, text in memories:
        has_cjk = bool(re.search(r"[぀-ヿ一-鿿]", str(text)))
        if ja and not has_cjk:
            out.append((rid, str(text)[:90]))
        if (not ja) and has_cjk:
            out.append((rid, str(text)[:90]))
    return out


def check_coverage(app, date, narrative):
    """Does the narrative cover the day's scenes: the span of the record
    against the span the prose names, measured by the hours it mentions and
    by the locations of the first and last scene."""
    scenes = app.store.scenes_for_date(date)
    if not scenes:
        return "no scenes on record"
    first, last = scenes[0], scenes[-1]
    n = narrative or ""
    hits = sum(1 for s in scenes if s.get("location") and str(s["location"]).split(",")[0].strip().lower() in n.lower())
    return (f"{len(scenes)} scenes {first.get('hm')}-{last.get('hm')}; "
            f"{hits}/{len(scenes)} scene locations named in the prose; {len(n)} chars")


def check_vectors(app, kind, refs):
    """Which of these refs have a vector."""
    if not refs:
        return 0, 0
    have = set()
    for i in range(0, len(refs), 400):
        chunk = [str(r) for r in refs[i:i + 400]]
        q = ",".join("?" * len(chunk))
        for r in _sql(app, f"SELECT ref FROM embeddings WHERE kind=? AND ref IN ({q})", (kind, *chunk)):
            have.add(str(r[0]))
    return len(have), len(refs)


def check_leaks(app):
    """Nothing of the other character in this one's compile output."""
    try:
        from tools import character_leaks
    except ImportError:
        return "tools/character_leaks.py not importable"
    for name in ("check", "run", "main", "scan"):
        fn = getattr(character_leaks, name, None)
        if callable(fn):
            try:
                return f"{name}(): {fn(app)}"
            except TypeError:
                pass
    return "no callable entry point found"


# ---------------- the run ----------------

def diff(before, after, date):
    out = []
    d0, d1 = before["day_row"], after["day_row"]
    out.append(("days row", "WROTE" if d1 else "MISSING",
                f"narrative {len(d1['narrative']) if d1 else 0} chars, summary "
                f"{len(d1['summary']) if d1 else 0} chars"
                + (f" (was {len(d0['narrative'])})" if d0 else " (no row before)")))
    nf = [f for f in after["user_facts"] if f not in before["user_facts"]]
    out.append(("facts about him", f"+{len(nf)}", "; ".join(x[:70] for x in nf[:4]) or "(none new)"))
    nm = [m for m in after["self_memories"] if m not in before["self_memories"]]
    out.append(("her memories", f"+{len(nm)}", "; ".join(str(x[1])[:60] for x in nm[:4]) or "(none new)"))
    nc = [x for x in after["cast_facts"] if x not in before["cast_facts"]]
    out.append(("cast facts", f"+{len(nc)}", "; ".join(f"{w}: {f[:50]}" for w, f in nc[:4]) or "(none new)"))
    out.append(("cast sheet", "CHANGED" if after["relationships"] != before["relationships"] else "unchanged",
                f"{len(before['relationships'])} -> {len(after['relationships'])} chars"))
    for key, label in (("places", "places"), ("arcs", "arcs"), ("diet", "her things"),
                       ("goals", "goals"), ("self_claims", "self claims"),
                       ("coherence", "coherence seams"), ("weekly_self", "week compile")):
        b, a = before.get(key) or [], after.get(key) or []
        out.append((label, f"{len(b)} -> {len(a)}", ""))
    out.append(("episode cards", f"{len(before['episodes'])} -> {len(after['episodes'])}",
                ", ".join(f"{r['room']} ({r['n_lines']} lines)" for r in after["episodes"][:6])))
    out.append(("embeddings", json.dumps(after["embeddings"]),
                "was " + json.dumps(before["embeddings"])))
    out.append(("what he now holds of her (primitives exposure_his)",
                f"{before['exposure_his']} -> {after['exposure_his']}",
                "moved" if before["exposure_his"] != after["exposure_his"] else "DID NOT MOVE"))
    out.append(("compiled_dates", f"{len(before['compiled_dates'])} -> {len(after['compiled_dates'])}",
                "date in" if date in (after["compiled_dates"] or []) else "DATE NOT RECORDED"))
    return out


def dupes(a, b):
    """What the second run doubled."""
    out = []
    if len(b["user_facts"]) != len(a["user_facts"]):
        out.append(f"user_facts {len(a['user_facts'])} -> {len(b['user_facts'])}")
    if len(b["self_memories"]) != len(a["self_memories"]):
        out.append(f"self_memories {len(a['self_memories'])} -> {len(b['self_memories'])}")
    if len(b["cast_facts"]) != len(a["cast_facts"]):
        out.append(f"cast_facts {len(a['cast_facts'])} -> {len(b['cast_facts'])}")
    if len(b["episodes_all"] if isinstance(b["episodes_all"], list) else [b["episodes_all"]]) and \
            b["episodes_all"] != a["episodes_all"]:
        out.append(f"episodes rows (all dates) {a['episodes_all']} -> {b['episodes_all']}")
    for key in ("places", "arcs", "diet", "goals", "self_claims", "coherence", "weekly_self"):
        if len(b.get(key) or []) != len(a.get(key) or []):
            out.append(f"{key} {len(a.get(key) or [])} -> {len(b.get(key) or [])}")
    if len(b["days"]) != len(a["days"]):
        out.append(f"days rows {len(a['days'])} -> {len(b['days'])}")
    return out


def gates(app):
    """The two gates round the compile, read rather than assumed."""
    from world.clock import hm_to_minutes
    c = app.config.timeline
    out = []
    live = app._program_call("exchange_live", default=None)
    out.append(("exchange_live hook", "absent (no exchanges for this character)" if live is None
                else f"present, live={live}", "the compile holds while it is True"))
    out.append(("compile_hold_for_chat", str(getattr(c, "compile_hold_for_chat", True)), ""))
    out.append(("quiet-by hour", getattr(c, "compile_quiet_by_hm", "04:00"),
                f"= {hm_to_minutes(getattr(c, 'compile_quiet_by_hm', '04:00'))} min; a night that ran over "
                f"is closed once the clock passes it even with an exchange live"))
    out.append(("compile_at", c.compile_at, ""))
    return out


def gate_run(config, db):
    """The two gates, exercised rather than read: an App on a copy with its
    clock parked past the compile hour, `App.compile` replaced by a recorder
    so nothing is spent, and `exchange_live` forced. Prints one line per case."""
    tmp = os.path.join(ROOT, "data", "retired", "compile_audit_tmp", "gates_" + os.path.basename(db))
    os.makedirs(os.path.dirname(tmp), exist_ok=True)
    from tools import harness
    app = harness.build_on(tmp, config, db, extra=["--sim", "2026-09-04 23:56", "--speed", "1"])
    harness.refuse_model(app)
    told = []
    app.compile = lambda d: told.append(d)
    prog = app.program
    live = {"v": False}
    setattr(prog, "exchange_live", lambda _app: live["v"])
    d = app.clock.date_str()
    prev = "2026-09-03"

    def case(name, want):
        told.clear()
        app.maybe_compile()
        got = list(told)
        print(f"   {name:58} told {got or 'nothing'}  ({'as designed' if (got == want) else 'NOT AS DESIGNED, wanted ' + str(want)})")

    app.compiled_dates = set(app.store.get("compiled_dates", [])) | {prev}
    live["v"] = True
    case("23:56, an exchange live: the compile holds", [])
    live["v"] = False
    case("23:56, nobody talking: the day is told", [d])
    # a night that ran past midnight, still live, past the quiet hour
    app2 = harness.build_on(tmp, config, db, extra=["--sim", "2026-09-05 04:30", "--speed", "1"], copy=False)
    harness.refuse_model(app2)
    told2 = []
    app2.compile = lambda x: told2.append(x)
    setattr(app2.program, "exchange_live", lambda _app: True)
    app2.compiled_dates.discard("2026-09-04")
    with app2.store.lock:
        app2.store.conn.execute("DELETE FROM days WHERE date=?", ("2026-09-04",))
        app2.store.conn.commit()
    app2.maybe_compile()
    print(f"   {'04:30 the next day, still talking, past the quiet hour':58} told {told2 or 'nothing'}  "
          + ("(as designed)" if told2 == ["2026-09-04"] else "(NOT AS DESIGNED, wanted ['2026-09-04'])"))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--date", required=True)
    p.add_argument("--config", default="config.json")
    p.add_argument("--db", default="data/world.db")
    p.add_argument("--tmp", default="")
    p.add_argument("--twice", action="store_true")
    p.add_argument("--week", action="store_true", help="call compile_week for the date even if it is not due")
    p.add_argument("--gates", action="store_true", help="exercise the hold-for-chat and quiet-by gates; no model calls")
    p.add_argument("--no-coherence", action="store_true",
                   help="skip the day's coherence read; nothing else in the compile depends on it, "
                        "and on 2026-09-04 it ran away twice at 131072 output tokens a call")
    a = p.parse_args()

    tmp = a.tmp or os.path.join(ROOT, "data", "retired", "compile_audit_tmp",
                                os.path.basename(a.db).replace(".db", "") + "_audit.db")
    os.makedirs(os.path.dirname(tmp), exist_ok=True)
    print(f"== building on a copy of {a.db} at {tmp}")
    app = harness.build_on(tmp, a.config, a.db)
    # never let a harness prune his real backups or write into them
    app.config.logging.backup_dir = os.path.join(os.path.dirname(tmp), "backups")

    print(f"== character {app.config.character.name}, program {app.config.character.program}, "
          f"her date now {app.clock.date_str()}, compiling {a.date}")
    print("== gates")
    for k, v, note in gates(app):
        print(f"   {k}: {v} {note}")
    if a.gates:
        print("== the gates exercised (no model calls)")
        gate_run(a.config, a.db)

    if a.no_coherence:
        app.config.coherence.enabled = False
        print("== the coherence read is off for this run")
    before = census(app, a.date)
    # the compile refuses a day it has already told, so let it tell this one
    app.compiled_dates.discard(a.date)
    t0 = time.time()
    app.compile(a.date)
    print(f"== compile took {time.time() - t0:.1f}s")
    after = census(app, a.date)

    print("== what the compile wrote")
    for item, verdict, receipt in diff(before, after, a.date):
        print(f"   {item:52} {verdict:22} {receipt}")

    d1 = after["day_row"]
    print("== narrative against the record")
    print("   " + check_coverage(app, a.date, d1["narrative"] if d1 else ""))
    ok, bad, misses = check_anchors(app, a.date)
    print(f"== anchors: {ok} verified as substrings of the episode, {bad} not found")
    for room, q in misses[:5]:
        print(f"   NOT FOUND in {room}: {q}")
    lang = check_language(app, [m for m in after["self_memories"] if m not in before["self_memories"]])
    print(f"== her new memories in the wrong language: {len(lang)}")
    for rid, t in lang[:5]:
        print(f"   {rid}: {t}")
    nf_refs = _new_fact_rids(app, before, after)
    print("== vectors: facts %d/%d, memories %d/%d, cards %d/%d" % (
        *check_vectors(app, "fact", nf_refs),
        *check_vectors(app, "selfmem", [r for r, _ in after["self_memories"] if (r, _) not in before["self_memories"]]),
        *check_vectors(app, "episode", [r["id"] for r in after["episodes"]])))
    print("== character leaks: " + str(check_leaks(app)))

    if a.week:
        from sim import timeline
        print("== week compile (forced)")
        t = timeline.compile_week(app.config, app.llm, app.store, app.clock, a.date, app.state)
        print("   " + (str(t)[:300] if t else "no text"))

    if a.twice:
        print("== running the compile again, the way /compile does")
        app.compiled_dates.discard(a.date)
        app.compile(a.date)
        third = census(app, a.date)
        d = dupes(after, third)
        print("   doubled: " + ("; ".join(d) if d else "NOTHING"))
        ok2, bad2, _ = check_anchors(app, a.date)
        print(f"   cards after the second run: {len(third['episodes'])} (was {len(after['episodes'])}), "
              f"anchors {ok2} verified / {bad2} not found")
        print(f"   embeddings: {json.dumps(third['embeddings'])}")

    print("== run directory " + str(getattr(__import__('logger'), 'RUN_DIR', '?')))


def _new_fact_rids(app, before, after):
    new = [f for f in after["user_facts"] if f not in before["user_facts"]]
    rids = []
    for r in app.memory.rows():
        if r["fact"] in new:
            rids.append(r["rid"])
    return rids


if __name__ == "__main__":
    main()
