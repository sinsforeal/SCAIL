"""A character in a world she does not keep reads it and writes none of it.

    python tools/world_reader_test.py        # exit 1 on any failure; run by smoke

One world has one writer (`docs/shared-world.md`). Everything that WRITES the
world -- the people's own week and the pressures behind it, what is going
round, what the day's record says happened, the people around the people, the
strangers, and measuring herself against the room -- is switched off for
anybody else in that world by the existence table (`Config.REQUIRES`, the
`world_owner` property), and what stays on reads the owner's rows instead.

Two builds, both on copies, both with every model call and every network
connection refused, sharing one scratch world directory:

  the OWNER, from `config.json`, who plans a day and writes it into a scratch
  world file through the live writers;

  the READER, from a config that names the same world and does not own it,
  who is asserted to build none of the machinery that writes it, to refuse
  every opening that would have put words in somebody else's mouth, and to
  carry the owner's settled lines, absences, whereabouts, pool and orbit in
  her own prompt and her own day's one truth.

Nothing live is opened for writing: both saves are `tools/dbcopy.copy_db`
copies and the world directory is under the temp directory
(`tools/harness.scratch_config`).
"""
import json
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

FAILURES = []

# The reader's config: any character whose config names a world and does not
# own it. Named as a file here, in a tool, and nowhere in the shared code.
READER_CONFIG = "config_rena.json"
READER_DB = "data/rena.db"

# the sections that write the world, which is the whole of the rule
WRITERS = ("cast_arcs", "showrunner", "gossip", "events", "orbit", "npc", "compare",
           "social_graph")
# and what stays on, because it is her rather than the world
# (the scenery harvest is not here: it runs on the account's browser profile
# and is the account's in Config.REQUIRES, so a reader with no account has it off)
STAYS = ("cast", "exchange", "family", "diary", "memory",
         "world_shared")


def _norm(s):
    return str(s or "").strip().lower()


def check(ok, what, detail=""):
    print(("  ok   " if ok else "  FAIL ") + what + (f"  -- {detail}" if detail else ""))
    if not ok:
        FAILURES.append(what)
    return bool(ok)


def _seeded_day(app, today, absent_who):
    """A day fixed by the owner: one settled line and the people her plan
    removed.

    Two of them, because a reader has to come out of this with one and not the
    other. The owner's process plans a day for the promoted girl's row too --
    the people who were not promoted still reach for her through it -- so the
    world file says where SHE is, and her own day's one truth read it back and
    told her, in the third person, that she was at her grandmother's."""
    app.store.set("cast_beats", {
        "date": today, "beats": [], "notes": "",
        "settled": ["the reading list is due on Friday"],
        "absent": [{"who": who, "from": "16:00", "to": "22:00",
                    "why": "at her grandmother's"} for who in absent_who]})


def main():
    from tools import harness
    harness.refuse_network()
    harness.refuse_model_before_build()
    from sim import roster

    d = tempfile.mkdtemp(prefix="scail_world_reader_")
    owner_db = os.path.join(d, "owner.db")
    reader_db = os.path.join(d, "reader.db")

    # ---- 1. the owner, unchanged
    print("[world] building the world's owner on a copy of her save")
    owner = harness.build_on(owner_db, "config.json", "data/world.db")
    check(owner.config.world_reader is False, "the world's owner is not a reader of it")
    check(all(getattr(owner.config, s).enabled for s in WRITERS),
          "and every section that writes the world is still on for her",
          ", ".join(WRITERS))
    check(owner.cast._reads_world() is False and owner.exchange._reads_world() is False,
          "her planner still plans and her rooms are still hers to start")
    check(owner.world_shared.enabled and owner.world_shared.owner,
          "she holds the world file as its writer", owner.world_shared.path)
    # the edges are keyed on both sides by what the record calls a person, and
    # the running character's own name in that record is resolved from the
    # roster rather than written down: for a character who is in nobody's cast
    # it must still be exactly her config name, or every edge in her save
    # about her stops matching
    check(owner.social_graph.me == owner.config.character.name,
          "the owner is named in her own edges by her config name", owner.social_graph.me)
    own_edges = ((owner.store.get("social_graph", {}) or {}).get("edges", {}) or {})
    about_her = [k for k in own_edges if k.split("|", 1)[-1] == owner.social_graph.me]
    check(len(about_her) >= 1 and bool(owner.social_graph.tomoe_lines().strip()),
          "and the edges her save already holds about her still match",
          f"{len(about_her)} of {len(own_edges)} edge(s)")

    # ---- 2. a day, written into the world by the live writers
    today = owner.clock.date_str()
    live_rows = [k for k, r in (owner.state.relationships or {}).items()
                 if k != "him" and isinstance(r, dict) and not r.get("dormant")]
    who = live_rows[0] if live_rows else ""
    _seeded_day(owner, today, live_rows[:2])
    settled = owner.ledger.settled(today)
    owner.cast.day_to_world(today)
    owner.store.set("gossip", {"items": [
        {"id": "g1", "text": "somebody in the second year is leaving after the term", "heat": 6.0,
         "knows": []}]})
    owner.store.set("orbit", {"people": [
        {"owner": who, "relation": "older brother", "name": "the one at the bike shop",
         "facts": ["fixes everybody's punctures"], "status": ""}]})
    from tomoe.app import compile_to_world
    compile_to_world(owner, today)
    counts = owner.world_shared.counts() or {}
    check(counts.get("settled", 0) >= 1 and counts.get("whereabouts", 0) >= 1
          and counts.get("gossip", 0) >= 1 and counts.get("orbit", 0) >= 1,
          "the owner's day is in the world file",
          ", ".join(f"{k} {counts.get(k, 0)}" for k in ("roster", "whereabouts", "settled", "gossip", "orbit")))

    # ---- 3. the reader
    print("[world] building a character who is in the same world and does not own it")
    reader = harness.build_on(reader_db, READER_CONFIG, READER_DB)
    check(reader.config.world_reader is True and reader.world_shared.enabled
          and not reader.world_shared.owner,
          "she is in the world and does not own it", reader.config.world_shared.id)
    check(os.path.abspath(reader.world_shared.path) == os.path.abspath(owner.world_shared.path),
          "and both processes are looking at one file", reader.world_shared.path)

    note = next((n for n in reader.config.boot_notes if "does not own it" in n), "")
    check(bool(note) and all(s in note for s in WRITERS),
          "the boot note names the world and every section it switches off", note[:120])
    off = [s for s in WRITERS if getattr(reader.config, s).enabled]
    check(not off, "and none of them is on for her", ", ".join(off) or "all off")
    on = [s for s in STAYS if not getattr(reader.config, s).enabled]
    check(not on, "her mind, her body, her day and her rooms are untouched",
          ", ".join(on) or ", ".join(STAYS))

    # the one section of the eight whose object is still built for her: every
    # reader of the edges takes them through it, and for a reader it reads the
    # owner's rows out of the world file
    check(reader.social_graph is not None and reader.config.social_graph.enabled is False,
          "her graph object is built and the section that writes the edges is off")

    live = [n for n in ("cast_arcs", "showrunner", "gossip", "events", "orbit", "people", "compare")
            if getattr(reader, n, None) is not None
            and getattr(reader.config, {"people": "npc"}.get(n, n)).enabled]
    check(not live, "no planner, arc, pool, record, orbit, stranger or ruler runs in her process",
          ", ".join(live) or "none")

    # ---- 4. she writes nothing of the world
    beat = {"time": reader.clock.hm(), "who": roster.record_name(reader.config, who),
            "kind": "group", "text": "somebody reaches into the day", "salience": 3}
    # her copied save still carries the beats her process planned before this
    # rule existed, so the question is whether the call writes a NEW one
    # her process plans a day for HER OWN people only (`own_cast_file`);
    # with the model refused the call returns nothing, and what matters is
    # that no person of the world's is in what it would plan for
    theirs = [n for n in reader.cast._people() if not roster.is_own(reader.config, n)]
    check(not theirs, "her process plans a day for nobody on the world's roster",
          ", ".join(theirs) or f"{len(reader.cast._people())} of her own")
    reader.store.set("cast_beats", {"date": today, "beats": [dict(beat, done=False)], "settled": []})
    check(reader.cast.due() == [], "and a beat for one of the world's people is never delivered by her")
    reader.store.set("cast_beats", {})
    check(reader.cast.presence_beat({"with_who": roster.record_name(reader.config, who)}) is None,
          "nobody sitting with her says a line she wrote")
    # A room of her own with one of her OWN people is hers and may well be
    # running on the save this was copied from, so the question is not whether
    # she is in a conversation -- it is whether a beat naming one of the
    # WORLD'S people opens one, and whether anything she is already in belongs
    # to her circle.
    was_live = reader.exchange.live()
    opened = reader.exchange.start(beat, {"phone_access": "free"})
    still = reader.exchange.live()
    check(opened is None and still == was_live,
          "a beat for one of the world's people opens no conversation in her process",
          f"she was in {(was_live or {}).get('who') or 'none'} before and after")
    check(was_live is None or roster.is_own(reader.config, was_live.get("who", "")),
          "and any room she is already in is with one of her own people",
          (was_live or {}).get("who") or "none")
    check(reader.exchange.self_open({"phone_access": "free"}) is None,
          "and she starts no room of her own")
    check(reader.exchange.alone_beat(beat, {"phone_access": "free"}) is None,
          "and the others carry nothing without her")
    check(reader.world_shared.put_settled(today, "she wrote a line into somebody else's world") is False,
          "a write from a reader is refused by the file itself")
    # the compile stage that used to run a paid update over her own witnessed
    # record and write the moved edges into her save
    was_graph = reader.store.get("social_graph", None)
    from tomoe.app import compile as compile_stage
    compile_stage(reader, today, "settled")
    check(reader.store.get("social_graph", None) == was_graph
          and reader.social_graph.seed_if_empty() == 0
          and reader.store.get("social_graph", None) == was_graph,
          "the compile settles no edge of hers and seeds none: the edges are the owner's")

    # ---- 5. she reads all of it
    check(reader.ledger.settled(today) == settled and bool(settled),
          "the day's one truth carries the settled lines the owner fixed", "; ".join(settled)[:90])
    ab = reader.ledger.absent(today)
    check(any(lo == "16:00" and hi == "22:00" for _n, lo, hi, _w in ab),
          "and the person the owner's day removed is absent for her too",
          "; ".join(f"{n} {lo}-{hi}: {w}" for n, lo, hi, w in ab)[:90])
    # ...but not HER, when the owner's plan is the one that removed her: the
    # world file carries where the promoted girl is, and her own ledger read it
    # back and told her she was at her grandmother's, about herself
    hers = [n for n, _lo, _hi, _w in ab if roster.is_self(reader.config, n)]
    check(not hers, "and her own absence, written about her in the owner's plan, is not one "
                    "of the rows she is handed", ", ".join(hers) or f"{len(ab)} row(s), none hers")
    where = reader.cast.world_where(today)
    check(bool(where), "she knows where everybody is, from the world file",
          f"{len(where)} person/people")
    brief = reader.cast.plans_brief(today)
    check(bool(brief.strip()) and any(n in brief for n in where),
          "the line her director reads is those rows", brief.splitlines()[0][:90] if brief else "")
    name = next(iter(where))
    check(bool(reader.cast.plan_line(name, today)),
          "and each of them has a day she can read off", reader.cast.plan_line(name, today)[:90])
    # what her reachability comes from, at this minute, for everybody the
    # world file has a row for: the row's own `reach`, and 1.0 for anybody
    # the day has nowhere in particular right now
    now_hm = reader.clock.hm()
    wrong = []
    for nm, rows in where.items():
        cover = [r for r in rows if r[1] and r[2] and r[1] <= now_hm < r[2]]
        want = 1.0
        if cover:
            reach = cover[0][3]
            want = {"class": 0.15, "none": 0.15, "glance": 0.5, "away": 0.0}.get(reach, 1.0)
            if reach == "class":
                want = 0.5 if "12:35" <= now_hm < "13:20" else 0.15
        got = reader.cast.available(nm)
        if abs(got - want) > 1e-9:
            wrong.append(f"{nm}: {got} not {want}")
    check(not wrong, "how reachable each of them is comes from the same rows",
          "; ".join(wrong) or f"{len(where)} checked at {now_hm}")

    # the people around her ride in the half of her prompt that moves during
    # a day (`persona/sections.py`: CARRIED), after the thread
    reader.persona.system_for("him")
    carried = reader.persona.carried_for()
    check("somebody in the second year is leaving" in carried,
          "what is going round is in her prompt, and the owner wrote it")
    ob = reader.persona._world_orbit()
    check(bool(ob) and ob.splitlines()[0] in carried,
          "so are the people around the people, out of the same file",
          (ob.splitlines()[0] if ob else "nothing")[:80])
    led = reader.ledger.text()
    check("the reading list is due on Friday" in led,
          "and the day's ledger she is handed is the day the owner fixed")

    # what the people around her hold, out of the file, and about HER: the
    # module carried one character's name as a constant and selected with it,
    # so every one of these readers answered about the world's owner
    rows = {(str(r.get("holder") or ""), str(r.get("about") or "")): r
            for r in (reader.world_shared.graph() or [])}
    check(bool(rows), "the owner's edges are in the world file", f"{len(rows)} edge(s)")
    mine = reader.social_graph.tomoe_lines()
    wrong = [h for (h, a), r in rows.items() if a == reader.social_graph.me
             and f"- {h}: regard {r['regard']}, irritation {r['irritation']}" not in mine]
    check(bool(mine.strip()) and not wrong,
          "what they hold about HER is every one of the file's rows about her, at the file's numbers",
          "; ".join(wrong) or f"{reader.social_graph.me}: " + "; ".join(mine.splitlines())[:90])
    stale = ((reader.store.get("social_graph", {}) or {}).get("edges", {}) or {})
    differs = [k for k in stale
               if tuple(k.split("|", 1)) in rows
               and k.split("|", 1)[-1] == reader.social_graph.me
               and int(stale[k].get("regard", -1)) != int(rows[tuple(k.split("|", 1))]["regard"])]
    check(all(f"- {k.split('|', 1)[0]}: regard {stale[k]['regard']}," not in mine for k in differs),
          "and where her own save still holds a different number, the file's is what she reads",
          ", ".join(differs) or "her save holds no differing edge about her")
    check(len(reader.social_graph.payload()) == len(rows)
          and len(reader.social_graph.report().splitlines()) == len(rows),
          "the backstage payload and /graph are the file's rows too", f"{len(rows)} edge(s)")
    check(reader.social_graph.drift_lines() == "",
          "and a week's drift is nothing for her: the file holds where the edges stand today")
    holder = next((h for (h, _a) in rows), "")
    check(bool(reader.social_graph.brief_for(holder).strip()),
          "a speaker's own edges are there for the rooms she is asked into",
          reader.social_graph.brief_for(holder).splitlines()[0][:90] if holder else "")

    # ---- 6. she is one person, and the girl whose world it is, is a person
    #
    # She is a row in the cast file she reads, because the people who were not
    # promoted still reach for her through it. In her own process that row is
    # her: folded into her own entry, names and all (`sim/roster.py`). It was
    # a second girl for eleven days -- her own nickname resolved to a stranger
    # with her own face, her save carried a bond with her, and her planner put
    # her on the list of where everybody is today.
    her_ja = _norm(reader.config.character.name_ja)
    twins = [r["key"] for r in roster.everyone(reader.config).values()
             if r.get("role_id") != "self"
             and (_norm(r.get("ja")) == her_ja or roster.is_self(reader.config, r.get("key", "")))]
    check(not twins, "her own row in the world's cast is her, not a second girl on her roster",
          ", ".join(twins) or "no twin")
    check(roster.role_of(reader.config, roster.handle(reader.config)) == "self"
          and reader.social_graph.me == roster.handle(reader.config),
          "and the handle the shared record keys her by still resolves to her",
          roster.handle(reader.config))
    owner_block = json.load(open(reader.config.character.cast_file, encoding="utf-8")).get("self") or {}
    okey = str(owner_block.get("key") or "")
    orec = roster.rec_of(reader.config, okey)
    check(bool(okey) and bool(orec) and orec.get("role_id") != "self"
          and not roster.is_own(reader.config, okey)
          and roster.record_name(reader.config, okey) == owner_block.get("ja"),
          "the girl whose world she reads is a person on her roster, and not one of her own",
          f"{okey} -> {orec.get('role_id', '-')} ({roster.record_name(reader.config, okey)})")

    # what her save holds after the once-pass: no bond, arc or thread naming
    # somebody her roster does not have, and none naming HER as a third party
    from tools.promoted_save_retire import bonds_to_drop, threads_to_drop
    left = bonds_to_drop(reader.config, reader.state.relationships or {})
    check(not left, "no bond in her save is the other girl's to hold",
          "; ".join(f"{k}: {w}" for k, w in left) or f"{len(reader.state.relationships or {})} of hers")
    check(not reader.records.arcs(), "and no arc: the section that writes them is not hers to run",
          "; ".join(a.get("title", "") for a in reader.records.arcs()) or "none")
    bad_threads = threads_to_drop(reader.config, reader.store.threads_by_status("open")
                                  + reader.store.threads_by_status("dormant", 50))
    check(not bad_threads, "and no open thread names somebody off her roster",
          "; ".join(f"{t['id']}: {w}" for t, w in bad_threads) or "none")

    # her own people's meters are hers to author. A row at 0/0/0 is the world
    # owner's zero on somebody the owner has never met, and her own cast file
    # was written from those rows: her mother and her brother were seeded into
    # her save as strangers and stayed there.
    flat = roster.flat_own_meters(reader.config)
    check(not flat, "every one of her own people's meters is a number somebody chose",
          "; ".join(f"{k}: {w}" for k, w in sorted(flat.items()))
          or ", ".join(sorted(roster.own_keys(reader.config))))

    # ---- 7. what her own circle's day is planned from
    #
    # Her own people are hers alone: not at her school, not in the group chat,
    # and they have never met anybody in it. The one call that plans their day
    # was handed the world's whereabouts, the world's private edges and the
    # world's open threads, and turned a plan the school made at lunch into
    # the thing her own friend's evening replied to.
    from tools import character_names
    fam = roster.FAMILY_ROLES
    theirs = sorted({n for n in character_names.names()
                     if roster.role_of(owner.config, n) in fam
                     or roster.is_self(owner.config, n)}, key=len, reverse=True)
    check(len(theirs) >= 3, "the other girl's household has names to look for", ", ".join(theirs[:8]))
    captured = {}

    def _capture(role, messages, **k):
        captured[role] = "\n".join(m.get("content", "") for m in messages)
        return {"beats": []}, ""

    reader.llm.call_json = _capture
    reader.cast.plan_day(reader.schedule or {"date": today, "blocks": []}, today, force=True)
    plan_prompt = captured.get("cast_day", "")
    check(bool(plan_prompt), "her own circle's day is planned by one call", f"{len(plan_prompt)} chars")
    # a word that means one of HER OWN people on her own roster is not the
    # other girl's name: お母さん is the woman in her own kitchen
    hits = [n for n in theirs if n in plan_prompt and not roster.is_own(reader.config, n)]
    check(not hits, "and nobody in the other girl's household is in what it is planned from",
          ", ".join(hits) or f"{len(theirs)} name(s) looked for")
    edges = [f"- {str(r.get('holder') or '')}: regard" for r in (reader.world_shared.graph() or [])]
    held = [e for e in edges if e in plan_prompt]
    check(not held, "nor what the world's people privately hold",
          ", ".join(held) or f"{len(edges)} edge(s) looked for")
    where_own = [n for n in reader.cast.world_where(today) if n in plan_prompt]
    check(not where_own, "nor where any of the world's people is today",
          ", ".join(where_own) or f"{len(reader.cast.world_where(today))} looked for")

    print()
    if FAILURES:
        print(f"[world] {len(FAILURES)} failure(s): " + "; ".join(FAILURES[:6]))
        return 1
    print("[world] a non-owner runs none of the machinery that writes the world and reads all of it")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
