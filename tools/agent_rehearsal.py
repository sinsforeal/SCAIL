"""One day of a character who runs herself, beside the character who keeps her world.

    python tools/agent_rehearsal.py rena
    python tools/agent_rehearsal.py <key> --root <dir>   # a bundle nobody has registered
    python tools/agent_rehearsal.py rena --step 20 --hours 24 --verbose

**What it proves.** Two whole processes, in one process: the character who
keeps the world and the character who only reads it, each built on a COPY of
her own live save, sharing one COPY of the world file, with the hub living in
this process and every model call answered from a canned reply that costs
nothing. It then advances one clock that both of them read, from the start of
her day to the end of it, calling the same day boundary, the same day planner,
the same room code and the same mailbox poll the live loop calls, and asserts
the runtime contract of the seam between them: a beat planned for her survives
the planner and reaches her mailbox at its hour, a turn relayed to her is
filed under whoever said it, a silence she chooses settles the wait at once,
nothing her sheet switches off writes to her save, her gauges are the ones her
config built, her prompt headings follow her sheet, her diary fires on her own
day, and the world file gains rows under her id about nobody but her.

Every fault it checks for is one that a structural check passed and a day of
running found (`data/retired/20260907_203328_rena_audit/REPORT.md` and
`data/retired/20260907_210559_rena_fixes/REPORT.md`). The three checks that
ran before her first day -- `tools/new_character.py verify`,
`tools/existence_matrix.py` and `tools/agent_seam_test.py` -- were all
structural, on one process, on a scratch save, with the model stubbed. This is
the behaviour check they had no room for.

**What it cannot prove.** Nothing about voice, believability or pacing: every
answer here is canned, so the words in the room are the recorder's and mean
nothing. Nothing about what a paid model does with her prompt: the shape of
an answer is asserted, never its content. Nothing about the network, the real
hub process, the scheduled tasks or a restart. Nothing about a day that runs
longer than one: a carry streak, a repeated opener or a room that goes stale
over a week is the live audit's question (`tools/agent_audit.py`), not this
one's. And nothing about the OWNER's own day beyond what the seam touches.

Nothing live is opened for writing, nothing is started and nothing is killed.
"""
import argparse
import io
import json
import os
import re
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# What each switchable section owns in her save.
#
# One table, in one place, read by this tool and imported by
# `tools/agent_audit.py` so the rehearsal and the live audit ask the same
# question of the same keys. It is BY SECTION and never by person: the
# section name is the one `Config.REQUIRES` uses, and the property that
# section needs is looked up there rather than repeated here.
#
# A row says: if this section is off for a character, these kv keys and these
# tables must not be written during her day. It is deliberately not derived
# from the code -- a derivation would follow whatever the code does, and what
# is being asked is whether the code does the right thing. Rena's phone-app
# open wrote `phone_use` fifty-one times with `sees_him: none` on her sheet.
SECTION_KEYS = {
    # --- sight of his machine (`sees_him`) ---
    # The app that reads his machine is an OBJECT rather than a section: it is
    # not built at all when her sheet says she sees nothing of him
    # (`sim/existence.py`), so its keys are listed under the section that is
    # the telemetry stack behind it.
    "sensors": {"kv": ["phone_last_look_ts", "phone_last_active_wall",
                       "phone_last_fingerprint", "phone_last_live",
                       "phone_last_consumed_id", "phone_account", "phone_force_next",
                       "phone_trail_shown", "phone_use", "his_first_active"],
                "tables": ["digests"]},
    "him_profile": {"kv": ["him_profile"], "tables": []},
    # the read receipts UPDATE a message row rather than adding one, so this
    # section's write is not visible in a row count; it is watched by its
    # absence of keys and named here so the row is not silently missing
    "receipts": {"kv": [], "tables": []},
    "notes": {"kv": ["notes_read", "vault_read_paths"], "tables": []},
    "vault_snoop": {"kv": ["snoop_counts", "snoop_downloads_seen", "snoop_last_ts",
                           "vault_read_paths", "phone_use"], "tables": []},
    "anime_sense": {"kv": ["anime_habits_date", "anime_shelf_check_date",
                           "anime_shelf_checks", "anime_shelf_hint_pending"],
                    "tables": []},
    "approach": {"kv": ["approaches"], "tables": []},
    "watching": {"kv": ["watching_last", "watching_recent", "watching_cursor",
                        "watching_queue", "watching_seen", "watching_short",
                        "watching_spoken", "watching_fetch_counts"], "tables": []},

    # --- a chat with him at all (`with_him`) ---
    "affection": {"kv": ["appraisal_levels", "appraisal_last_ts", "appraisal_night"],
                  "tables": []},
    "afterthought": {"kv": ["afterthought_for_ts", "afterthought_ignored_ts",
                            "afterthought_counts"], "tables": []},
    "attachment": {"kv": ["attachment", "attachment_log"], "tables": []},
    "beliefs": {"kv": ["beliefs"], "tables": []},
    "care": {"kv": ["care_history", "care_factor_cache"], "tables": []},
    "derive": {"kv": ["relationship_derived"], "tables": []},
    "expect": {"kv": ["expectations", "habits_him", "habits_checked"], "tables": []},
    "foresight": {"kv": ["foresight"], "tables": []},
    "ick": {"kv": ["ick_kinds", "charged", "ick_digest_last_ts"], "tables": []},
    "intent": {"kv": ["intent_counts"], "tables": []},
    "lookup": {"kv": ["lookups", "lookup_kb_misses", "lookup_counts", "search_counts"],
               "tables": []},
    "nudge": {"kv": ["nudge_last", "nudge_log", "nudge_fired_ts"], "tables": []},
    "reflect": {"kv": ["reflections", "reflect_last_ts", "reflect_cast_last",
                       "reflect_last_digest_ts", "reflect_counts",
                       "reflect_cast_counts"], "tables": []},
    "rhythm": {"kv": ["rhythm_said"], "tables": []},
    "rupture": {"kv": ["ruptures"], "tables": []},
    "withholding": {"kv": ["withholding", "withholding_log",
                           "withholding_handed_back"], "tables": []},
    "wonder": {"kv": ["questions", "wonder_seed", "wonder_last_ts", "wonder_counts"],
               "tables": []},

    # --- an account of her own (`has_account`) ---
    "posting": {"kv": ["x_post_held", "x_post_last_mode"], "tables": []},
    "curation": {"kv": ["x_action_queue", "x_action_counts", "x_post_last_ts",
                        "x_post_times", "x_replies_sent", "x_reply_times"],
                 "tables": []},
    "x": {"kv": ["x_reply_candidates", "x_reply_declined", "x_replies_seen",
                 "x_reply_last_ts"], "tables": []},
    "share_pick": {"kv": ["x_share_picks"], "tables": []},
    "scenery": {"kv": ["scenery_accounts", "scenery_lore", "scenery_query_i",
                       "scenery_last_run_ts", "scenery_last_send_ts",
                       "scenery_send_counts"], "tables": ["scenery"]},

    # --- a world SHE KEEPS (`world_owner`) ---
    # Every section here WRITES the world. A reader running any of them is a
    # second planner over one roster, each writing into its own save.
    "cast_arcs": {"kv": ["cast_arcs", "cast_arcs_last_date", "cast_evolve_last_date"],
                  "tables": []},
    "showrunner": {"kv": ["showrunner_last_date"], "tables": []},
    "gossip": {"kv": ["gossip"], "tables": []},
    "events": {"kv": ["event_stances"], "tables": []},
    "orbit": {"kv": ["orbit"], "tables": []},
    "npc": {"kv": ["npcs", "npc_counts", "npc_moments", "npc_last_ts",
                   "npc_last_check_ts"], "tables": []},
    "compare": {"kv": ["comparisons", "compare_last_ts", "compare_counts"],
                "tables": []},
    "social_graph": {"kv": ["social_graph"], "tables": []},

    # --- a body (`embodied`) ---
    "health": {"kv": ["health_days", "health_note_today"], "tables": []},
    "environment": {"kv": ["exposure"], "tables": []},
    "money": {"kv": ["money", "money_note_today"], "tables": []},
    "diet": {"kv": ["media_diet"], "tables": []},
    "situation": {"kv": ["situation", "journeys", "ledger_meals", "ledger_wearing"],
                  "tables": []},
    "household": {"kv": ["household"], "tables": []},

    # --- a world at all (`in_world`) ---
    "cast": {"kv": ["cast_beats", "cast_beats_prev", "cast_days", "cast_life",
                    "cast_plans", "cast_chat", "presence_beats",
                    "cast_quiet_pulls"], "tables": []},
    "cast_bond": {"kv": ["cast_bonds"], "tables": []},
    "social": {"kv": ["x_about_him", "x_engagement", "x_engagement_recent",
                      "x_followers_recent", "x_japan", "x_last_look_ts",
                      "x_last_noticed", "x_last_noticed_ts", "x_share_declined",
                      "x_shareable", "x_shared", "x_show_pending", "x_taste",
                      "x_taste_log", "x_look_counts", "x_share_looks"],
               "tables": ["seen_images"]},
    "exchange": {"kv": ["exchange_live", "cast_asleep", "behind", "exchange_counts",
                        "exchange_late_counts", "exchange_self_open_counts",
                        "exchange_alone_counts"], "tables": []},
    "family": {"kv": ["family_days"], "tables": []},
    "trains": {"kv": ["train_status"], "tables": []},
    "hazards": {"kv": ["hazards_ranks", "hazards_national", "hazards_seen"],
                "tables": []},

    # --- his machine in front of her (`resident`) ---
    "resident_sight": {"kv": ["resident_asleep", "resident_woken",
                              "resident_notes_seen", "resident_notes_since",
                              "noticed_said", "noticed_last_ts", "glance_last",
                              "glance_seen"], "tables": []},
    "eroge": {"kv": ["eroge_cursor", "eroge_day", "eroge_last"], "tables": []},
}

# Keys that are about him and belong to no one section: the boot repair pass
# takes them out of a save whose sheet answers `sees_him: none` or
# `with_him: none` (`sim/repairs.py:NO_HIM_KV`), and nothing may put them back
# during her day. Three of them have a writer that no switched-off section
# owns -- what she has told somebody about him, her phone-use counter and his
# mood on her state row -- so this list is checked separately from the table
# above and is the one that catches a section that is ON writing about a man
# she has no chat with.
NO_HIM_KV = ["his_mood", "his_first_active", "him_share", "foresight", "care_history",
             "relationship_derived", "phone_use", "phone_last_look_ts",
             "phone_debt_done", "phone_last_consumed_id", "phone_last_active_wall"]

FAILURES = []
NOTES = []


def refuse_browser():
    """Every browser this process would start raises instead.

    The Japanese knowledge base and the account both drive a real Chrome
    through a driver on this machine (`sim/recap.py`, `tomoe/social.py`), and
    a pass of the loop reaches one of them. Refusing at the socket is not
    enough: the driver is a local executable, so it starts, fails to be
    reached, and spends thirty seconds of wall time per pass shutting itself
    down. Every caller catches whatever the browser raises and goes on, which
    is what makes refusing it honest rather than broken."""
    try:
        from selenium import webdriver
    except Exception:
        return

    def _refuse(*a, **k):
        raise RuntimeError("this rehearsal does not start a browser")
    for name in ("Chrome", "Firefox", "Edge", "Remote"):
        if hasattr(webdriver, name):
            setattr(webdriver, name, _refuse)


def check(ok, what, detail=""):
    print(("  ok   " if ok else "  FAIL ") + what + (f"  -- {detail}" if detail else ""))
    if not ok:
        FAILURES.append(what)
    return ok


def skip(what, why):
    """A check this run could not exercise. Said out loud and counted, so a
    rehearsal that proved less than it looks like it proved says so."""
    print("  --   " + what + "  -- not exercised: " + why)
    NOTES.append(what + ": " + why)


# ------------------------------------------------------------------ the stubs

class Recorder:
    """Every model call of one App, recorded and answered from a canned reply.

    Shaped per role, because a day needs the answers to parse: the day script,
    the beat, each person's line, her own turn in a room, her state deltas,
    her diary. A role this has no shape for is answered `None`, which every
    JSON caller in the tree must already handle -- and the roles it was asked
    for and had no shape for are printed at the end, so a rehearsal never
    passes on a day that quietly did nothing."""

    def __init__(self, app, label, beats=(), ja="録音された返事"):
        self.label = label
        self.calls = []
        self.unshaped = set()
        self.beats = list(beats)
        self.ja = ja
        # ...and a counter in every stand-in turn, because two turns with the
        # same words are a repeat and the room drops the second one, ends a
        # round early and takes the person off the list she may be written to
        # on. A stub that says one sentence all day rehearses a day in which
        # nobody ever says anything new.
        self._said = 0
        # her next room answer is a silence: set by the driver for the one
        # ask it wants handed back empty
        self.silent_next = False
        self.silences = 0
        app.llm.call = self.call
        app.llm.call_json = self.call_json
        app.llm.call_tools = self.call_tools

    # what the plain-text roles get
    def call(self, role, messages, *a, **k):
        self.calls.append(role)
        return "recorded answer"

    def call_tools(self, role, messages, tools, *a, **k):
        """The tool-calling seam, answered with the one choice that is always
        offered and always safe: she does nothing with the phone.

        Stubbed for the same reason as the other two. The client is what
        retries a failed call, with a real sleep between the tries, so a
        rehearsal that stubbed only the text and JSON calls spent
        three-quarters of its wall time asleep inside the pick."""
        self.calls.append(role)
        return {"calls": [{"id": "", "name": "nothing", "arguments": {}, "raw": "{}"}],
                "text": "", "finish": "tool_calls", "usage": {}, "served_by": "",
                "seconds": 0.0, "first_token_s": 0.0, "faults": [], "model": ""}

    def call_json(self, role, messages, *a, **k):
        self.calls.append(role)
        fn = getattr(self, "_r_" + role, None)
        if fn is None:
            self.unshaped.add(role)
            return None, ""
        return fn(messages), ""

    def count(self, role, since=0):
        return self.calls[since:].count(role)

    # ---- the shapes a day needs

    def _r_schedule(self, messages):
        # the skeleton is what a rejected answer falls back to, and the
        # skeleton is a real day. Answering with no blocks is the honest
        # canned answer: the day is the character's own, not the recorder's.
        return {"blocks": None, "notes": "(recorded)"}

    def _r_director(self, messages):
        return {"location": "", "activity": "", "with": "", "phone_access": "",
                "sensory": "", "events": [], "share_worthy": False, "share_hint": "",
                "open_threads": [], "resolved_threads": [], "schedule_change": None,
                "next_tick_minutes": 30}

    def _r_sleep(self, messages):
        return self._r_director(messages)

    def _r_state(self, messages):
        return {"deltas": {}, "relationships": {}, "reasons": "recorded", "his_mood": ""}

    def _r_cast_day(self, messages):
        return {"beats": [dict(b) for b in self.beats], "settled": [], "absent": [],
                "notes": ""}

    def _r_cast_beat(self, messages):
        return {"ja": self.ja, "photo": ""}

    def _r_cast_life(self, messages):
        return {"text": "recorded day", "carry": ""}

    def _said_now(self):
        self._said += 1
        return "%s%d" % (self.ja, self._said)

    def _r_cast_turn(self, messages):
        n = self._said_now()
        return {"turns": [{"who": "?", "ja": n}], "gist": n, "about_him": ""}

    def _r_cast_reply(self, messages):
        return self._r_cast_turn(messages)

    def _r_peer_reply(self, messages):
        if self.silent_next:
            self.silent_next = False
            self.silences += 1
            return {"messages": [], "gist": ""}
        return {"messages": [self._said_now()], "gist": "recorded"}

    def _r_diary(self, messages):
        return {"ja": "録音された日記", "text": "a recorded diary entry"}

    def _r_pick(self, messages):
        return {"do": "nothing", "arguments": {}}

    def _r_editor(self, messages):
        return {"ok": True, "issues": [], "notes": ""}

    def _r_timeline(self, messages):
        return {"narrative": "recorded", "summary": "recorded", "user_facts": [],
                "memories": [], "people": [], "goals": []}

    def _r_reconcile(self, messages):
        return {"drop": [], "keep": []}

    def _r_coherence(self, messages):
        return {"ok": True, "issues": []}

    def _r_morning(self, messages):
        return {"ja": "", "text": ""}

    def _r_bond(self, messages):
        return {"promises": [], "confidences": []}


class Hub:
    """The messenger hub, in this process, routing between two Apps.

    `peer_send(to, text, room)` puts a message in the named character's
    mailbox; `peer_updates(after)` is what that character's process reads.
    One log line per delivery, so the driver can say what reached whom and
    when, and so a wait that ran to its deadline is visible as the absence of
    an early answer rather than inferred."""

    def __init__(self):
        self.n = 100000        # past any cursor a copied save is carrying
        self.mail = {}         # hub id -> [message]
        self.log = []          # (ts, from, to, room id, about, asking, silent, text)
        self.now = lambda: 0.0

    def channel_for(self, frm):
        """The two methods a character's process calls on its channel, bound
        to the character doing the calling: the hub knows who sent what."""
        hub = self

        class _Ch:
            def peer_send(self, to, text, room=None):
                return hub.deliver(frm, to, text, room)

            def peer_updates(self, after=0):
                return [dict(m) for m in hub.mail.get(frm, [])
                        if int(m["id"]) > int(after or 0)]
        return _Ch()

    def deliver(self, frm, to, text, room=None, name=""):
        self.n += 1
        m = {"id": self.n, "from": str(frm), "name": str(name or frm),
             "text": str(text), "ts": self.now(), "room": room}
        self.mail.setdefault(str(to), []).append(m)
        env = room if isinstance(room, dict) else {}
        self.log.append({"ts": self.now(), "from": str(frm), "to": str(to),
                         "room": str(env.get("id") or ""), "about": str(env.get("about") or ""),
                         "asking": bool(env.get("asking")), "silent": bool(env.get("silent")),
                         "text": str(text)[:80]})
        return True

    def asks_to(self, who):
        return [r for r in self.log if r["to"] == who and r["asking"]]

    def answers_from(self, who):
        return [r for r in self.log if r["from"] == who and not r["asking"]]


# ---------------------------------------------------------------- the setting

def _bundle(root, key):
    p = os.path.join(ROOT, root, key, "bundle.json")
    try:
        with io.open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _row_for(key, root):
    """Her register row, or her manifest for a character nobody has
    registered. A bundle under `--root` is how a promotion is rehearsed
    before anybody puts a row in the operator's list."""
    from tools import registry
    row = next((r for r in registry.characters() if r["key"] == key), None)
    b = _bundle(root, key)
    if row:
        return row, b
    if not b:
        raise SystemExit("[rehearsal] %s is neither registered nor a bundle under %s"
                         % (key, root))
    return {"key": key, "name": b.get("name", key), "hub_id": b.get("hub_id", key),
            "config": b.get("config", ""), "db": b.get("db", ""),
            "program": b.get("program", "")}, b


def _owner_of(world_id, root):
    """The registered character who KEEPS that world. A world has one writer
    and any number of readers; the rehearsal is the two of them side by side,
    so a reader with no owner in the register has nothing to rehearse
    against."""
    from tools import registry
    for r in registry.characters():
        b = _bundle("characters", r["key"]) or _bundle(root, r["key"])
        w = b.get("world") or {}
        if str(w.get("id") or "") == world_id and w.get("owner"):
            return r, b
    return None, {}


def _copy_world(world_id, dst_dir):
    from tools.dbcopy import copy_db
    src = os.path.join(ROOT, "data", "worlds", world_id, "world.db")
    d = os.path.join(dst_dir, "scail_scratch_worlds", world_id)
    os.makedirs(d, exist_ok=True)
    dst = os.path.join(d, "world.db")
    if os.path.exists(src):
        copy_db(src, dst)
    return dst


def _kv_snapshot(app):
    """Every kv key and the bytes under it, plus a row count per table. The
    unit of "did this section write" is a key that appeared or changed."""
    cur = app.store.conn.execute("SELECT key, value FROM kv")
    kv = {r[0]: r[1] for r in cur.fetchall()}
    tables = {}
    for t in ("scenes", "events", "state_log", "schedules", "days", "messages",
              "digests", "user_facts", "threads", "reply_prompts", "swipes"):
        try:
            tables[t] = app.store.conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
        except Exception:
            tables[t] = -1
    return {"kv": kv, "tables": tables}


def _off_sections(config):
    """The sections her sheet switches off: every row of `Config.REQUIRES`
    whose section carries an `enabled` flag that is false. Derived from HER
    config rather than from the property, so a section switched off by hand
    counts the same as one the existence table switched off -- both are
    "nothing here runs", and both must leave her save alone."""
    from config import Config
    off = []
    for sect in sorted(Config.REQUIRES):
        s = getattr(config, sect, None)
        if s is not None and getattr(s, "enabled", True) is False:
            off.append(sect)
    return off


# ---------------------------------------------------------------- the driving

def _pass(app):
    """One turn of the loop, the parts a day on the seam goes through.

    `App.run` is a `while True` with sleeps in it and no single-pass entry
    point, so the passes it makes are made here in its own order: the day
    boundary and the plan, the program's own two hooks (the beats, the
    exchange, the people), where her body is, and the mailbox. A director
    tick is taken when the director says it is due, which is what puts a
    scene under the presence beat.

    ONE step of the loop is left out on purpose. The last hook of a pass is
    the feeds, the account's queue and the trains, and it reaches the network
    and starts a browser on the machine this is running on. It is no part of
    the seam between two characters, and a rehearsal that opened a browser
    window would be doing something to his machine rather than reading it."""
    app.ensure_day()
    app.maybe_generate_schedule()
    app._program_call("every_pass")
    app.poll_inbound()
    app._program_call("loop_pass")
    app._guarded("where", app._situation_tick)
    app._program_call("after_situation")
    app._guarded("peer", app.peers.tick, app.director.current)
    if app.director.due(app.schedule):
        app.ordinary_tick()


def rehearse(key, root="characters", step_minutes=20, hours=24, start_hm="06:00",
             verbose=False):
    from tools import harness
    from sim import roster

    row, b = _row_for(key, root)
    ex = ((b.get("config_overrides") or {}).get("character") or {}).get("existence") or {}
    if not ex:
        # a registered character's answers are in her config, which is what
        # her process reads
        pass
    world = b.get("world") or {}
    world_id = str(world.get("id") or "")
    if not world_id or world.get("owner"):
        raise SystemExit("[rehearsal] %s keeps her own world or is in none; this rehearses a "
                         "character who READS somebody else's" % key)
    orow, _ob = _owner_of(world_id, root)
    if not orow:
        raise SystemExit("[rehearsal] no registered character keeps the world %r" % world_id)

    print("[rehearsal] %s reads the world %r, which %s keeps" % (key, world_id, orow["key"]))
    harness.refuse_network()
    harness.refuse_model_before_build()
    refuse_browser()
    d = tempfile.mkdtemp(prefix="scail_rehearsal_%s_" % key)
    wpath = _copy_world(world_id, d)
    print("[rehearsal] copies under %s; the world file is %s"
          % (d, "copied" if os.path.exists(wpath) else "EMPTY (there was none to copy)"))

    t0 = time.time()
    owner = harness.build_on(os.path.join(d, "owner.db"), orow["config"], orow["db"])
    her = harness.build_on(os.path.join(d, "her.db"), row["config"], row["db"])
    print("[rehearsal] both built in %.1fs" % (time.time() - t0))
    if verbose:
        # the harness stubs the logger so a tool leaves no run directory
        # behind; put the narrative back on the console without one
        import logger
        logger.log = lambda m, to_console=True: print("     " + str(m)[:160])

    # one clock, read by both. The rehearsal is a day on HER clock, and the
    # two of them are in one world, so there is one reading of the time.
    start = owner.clock.ts_of(owner.clock.date_str(), start_hm)
    state = {"now": start}
    for app in (owner, her):
        app.clock.now_ts = lambda s=state: s["now"]
        app.clock.sleep = lambda _s: None

    for app in (owner, her):
        # nothing is delivered to him in a rehearsal. Both of these are
        # copies of a save and the chat is not what is being rehearsed, and
        # without it the owner's bubbles print to this console as if they had
        # been sent.
        app.delivery.withhold = "rehearsal"

    hub = Hub()
    hub.now = lambda s=state: s["now"]
    for app, hid in ((owner, orow["hub_id"]), (her, row["hub_id"])):
        ch = hub.channel_for(hid)
        app.tg.peer_send = ch.peer_send
        app.tg.peer_updates = ch.peer_updates
        app.peers.rooms.channel = app.tg

    # the beat the owner's planner is handed for her, at an hour her own day
    # gives her the phone. It is a plain line and never an outing: a beat
    # proposing a day the calendar has not got is dropped before it is stored,
    # and that drop would read here as the fault this is looking for.
    her_name = roster.record_name(owner.config, key) or row["name"]
    hers = roster.by_agent(owner.config, row["hub_id"]) or {}
    her_key = str(hers.get("key") or "")
    if not her_key:
        raise SystemExit("[rehearsal] %s's row in the world's cast file does not carry "
                         "`agent: %s`, so the owner's process would still write her words"
                         % (key, row["hub_id"]))
    her_rec_name = roster.record_name(owner.config, her_key)
    other = ""
    for k2, r2 in roster.everyone(owner.config).items():
        kk = str(r2.get("key") or k2)
        if kk == her_key or roster.is_agent(owner.config, kk):
            continue
        if str(r2.get("role_id") or "") in ("self", "partner") or roster.is_family(owner.config, kk):
            continue
        other = kk
        break
    orec = Recorder(owner, orow["key"], beats=[], ja="録音された返事")
    hrec = Recorder(her, row["key"], ja="録音された答え")
    beat_hm = group_hm = ""

    # her save, before anything of hers runs
    before = _kv_snapshot(her)
    seen_before = _room_turns(her)

    # ---- the day
    passes = int(hours * 60 / step_minutes)
    asked = []

    spent = {orow["key"]: 0.0, row["key"]: 0.0}
    silence = {"armed": False, "at": 0}

    def _both(first, second):
        for app, k in ((first, orow["key"] if first is owner else row["key"]),
                       (second, orow["key"] if second is owner else row["key"])):
            t = time.time()
            try:
                _pass(app)
            except Exception as e:
                import traceback
                print("  !!   %s failed at %s: %s: %s" % (app.config.character.name,
                                                          app.clock.hm(), type(e).__name__, e))
                if verbose:
                    traceback.print_exc()
            spent[k] += time.time() - t
        # The ask she is to answer with a silence is armed as soon as one ask
        # has been through, not at the top of the next pass: the settling
        # steps below answer an ask inside the same pass it was sent in, so a
        # flag set once a pass was always set too late -- and arming on the
        # SECOND one armed it on the last ask of the day, with nothing after
        # it to answer, as soon as the rooms started ending when a round
        # added nothing.
        if not silence["armed"] and len(hub.asks_to(row["hub_id"])) >= 1:
            hrec.silent_next = True
            silence["armed"] = True
            silence["at"] = len(hub.asks_to(row["hub_id"]))

    def _open_asks():
        return len(hub.asks_to(row["hub_id"])) - len(hub.answers_from(row["hub_id"]))

    now = start
    for i in range(passes):
        state["now"] = now
        _both(owner, her)
        if i == 0:
            # The day the copy was taken already has a plan in it, and the
            # planner does not rewrite a day it has planned. Re-planned here,
            # once, through the planner itself with the canned day script:
            # writing the beats into the store instead is what let the fault
            # this looks for run for two days unseen. The beats go at hours
            # HER OWN day gives her the phone, read off the plan her process
            # has just written: a beat at an hour her phone is away is
            # answered with a refusal, which is correct and proves nothing.
            today = owner.clock.date_str()
            beat_hm, group_hm = _phone_hours(her, today, owner.clock.hm(), hours)
            orec.beats = [{"time": beat_hm, "who": her_rec_name, "kind": "line",
                           "salience": 3,
                           "about": "she says what time everybody is meeting"}]
            if other and group_hm:
                # a beat that opens the GROUP room, so the owner relays the
                # other speakers' turns to her and her own turn in it comes
                # round to be asked for
                orec.beats.append({"time": group_hm,
                                   "who": roster.record_name(owner.config, other),
                                   "kind": "group", "salience": 4,
                                   "about": "she asks the group about the homework"})
            owner.cast.plan_day(owner.store.get_schedule(today) or {}, today, force=True)
            kept = [b for b in (owner.cast.beats_for(today) or {}).get("beats", [])
                    if roster.is_agent(owner.config, b.get("who", ""))]
            print("[rehearsal] the day was re-planned through the planner at %s, with a beat "
                  "for her at %s and a group beat at %s, both at hours her own plan leaves her "
                  "phone free: %d beat(s), %d of them hers%s"
                  % (owner.clock.hm(), beat_hm, group_hm or "(none free)",
                     len((owner.cast.beats_for(today) or {}).get("beats", [])), len(kept),
                     " (" + ", ".join("%s %s" % (b.get("time"), b.get("kind")) for b in kept) + ")"
                     if kept else ""))
        # An ask waits ten minutes for a beat and three for a turn, and a pass
        # of this rehearsal is twenty. Left there, every ask would time out on
        # the step rather than on anything the seam did. While one is open the
        # clock moves in half-minutes and she goes first, which is the order
        # the wall clock puts them in.
        for _ in range(4):
            if _open_asks() <= 0:
                break
            state["now"] += 30
            _both(her, owner)
        n = len(hub.asks_to(row["hub_id"]))
        if n > len(asked):
            asked = hub.asks_to(row["hub_id"])
            if verbose:
                print("     %s  ask -> %s (%s)" % (owner.clock.hm(), row["hub_id"],
                                                   asked[-1]["about"] or "turn"))
        now = max(start + (i + 1) * step_minutes * 60, state["now"] + 60)
    after = _kv_snapshot(her)
    print("[rehearsal] %d pass(es) of %d min over %s, %d model call(s) recorded "
          "(%d owner, %d hers); %.0fs in the owner's passes and %.0fs in hers"
          % (passes, step_minutes, owner.clock.date_str(), len(orec.calls) + len(hrec.calls),
             len(orec.calls), len(hrec.calls), spent[orow["key"]], spent[row["key"]]))
    unshaped = sorted(orec.unshaped | hrec.unshaped)
    if unshaped:
        print("[rehearsal] roles asked for that the recorder has no shape for, answered "
              "None: " + ", ".join(unshaped))

    print()
    assertions(owner, her, orow, row, hub, orec, hrec, before, after, world_id,
               her_key, her_rec_name, beat_hm,
               silence["armed"] and len(hub.asks_to(row["hub_id"])) > silence["at"],
               seen_before, verbose)
    return d


def _phone_hours(her, date_str, after_hm, hours):
    """(the hour to plant her beat at, the hour to plant the group beat at).

    Both read off HER OWN plan for the day: the first two blocks after the
    rehearsal has started, inside the rehearsed stretch, that leave her phone
    free. A beat at an hour her phone is away is refused by her own gate,
    which is right and proves nothing about the seam."""
    from world.clock import hm_to_minutes, minutes_to_hm
    lo = hm_to_minutes(after_hm) + 45
    hi = lo + int(hours * 60)
    free = []
    for b in ((her.store.get_schedule(date_str) or {}).get("blocks") or []):
        if str(b.get("phone_access") or "") not in ("free", "quick"):
            continue
        try:
            s = hm_to_minutes(str(b.get("start") or ""))
        except Exception:
            continue
        if lo <= s <= hi:
            free.append(s)
    free.sort()
    if not free:
        # she has no free window in the rehearsed stretch: fall back to the
        # clock so the ask still happens and the refusal is what is seen
        return minutes_to_hm(lo, wrap=True), minutes_to_hm(lo + 60, wrap=True)
    first = free[0] + 10
    rest = [s for s in free if s >= first + 40]
    return (minutes_to_hm(first, wrap=True),
            minutes_to_hm(rest[0] + 10, wrap=True) if rest else "")


def _room_turns(her):
    """Every turn in her record of a room somebody else keeps, as
    (room, speaker, words). The unit the relay checks work in."""
    out = []
    seen = her.store.get("peer_rooms", {}) or {}
    for rm, blob in (seen.items() if isinstance(seen, dict) else []):
        for t in ((blob or {}).get("turns") or []):
            out.append((str(rm), str(t.get("who") or ""), str(t.get("ja") or "")))
    return out


# --------------------------------------------------------------- the checks

def assertions(owner, her, orow, row, hub, orec, hrec, before, after, world_id,
               her_key, her_rec_name, beat_hm, silence_driven, seen_before, verbose):
    from sim import roster, existence

    hid = row["hub_id"]
    today = owner.clock.date_str()

    # 1. the beat survives the planner and reaches her mailbox
    beats = (owner.cast.beats_for(today) or {}).get("beats", []) or []
    mine = [b for b in beats if roster.is_agent(owner.config, b.get("who", ""))]
    check(bool(mine),
          "the owner's day planner stored a beat for her, with no words in it",
          "%d of %d beat(s) are hers" % (len(mine), len(beats)))
    beat_asks = [a for a in hub.asks_to(hid) if a["about"] == "beat"]
    check(bool(beat_asks), "and the ask for it reached her mailbox",
          "%d beat ask(s), first at %s" % (len(beat_asks),
                                           owner.clock.hm(beat_asks[0]["ts"]) if beat_asks else "-"))
    if beat_asks and mine:
        want = str(mine[0].get("time") or beat_hm)
        got = owner.clock.hm(beat_asks[0]["ts"])
        check(got >= want, "at its own hour rather than at the day boundary",
              "planned %s, asked %s" % (want, got))

    # 2. a room the owner opened asked her, and her answer reaches the record
    all_asks = hub.asks_to(hid)
    check(bool(all_asks), "a room the owner opened asked her through the hub",
          "%d ask(s): %s" % (len(all_asks),
                             ", ".join("%s in %s" % (a["about"] or "turn", a["room"])
                                       for a in all_asks[:4])))
    answers = [a for a in hub.answers_from(hid) if not a["silent"] and a["text"].strip()]
    check(bool(answers), "and her answer came back through the hub as a turn in that room",
          "%d answer(s)" % len(answers))
    # her words, in the owner's own record of the day and in the world file,
    # under her name and nobody else's
    said = {a["text"].strip() for a in answers}
    beats = (owner.cast.beats_for(today) or {}).get("beats", []) or []
    in_record = [b for b in beats
                 if roster.is_agent(owner.config, b.get("who", ""))
                 and any(s and s[:40] in str(b.get("ja") or "") for s in said)]
    world_rows = []
    for r in (owner.world_shared.turns(today) or []):
        if any(s and s[:40] in str(r.get("ja") or "") for s in said):
            world_rows.append(r)
    wrong = sorted({str(r.get("who")) for r in world_rows
                    if not roster.same(owner.config, str(r.get("who") or ""), her_key)})
    if world_rows or in_record:
        check(not wrong,
              "her answer landed in the owner's record and in the world's rooms table under "
              "her name",
              "%d beat(s) of hers carry her words, %d row(s) in the world file%s"
              % (len(in_record), len(world_rows),
                 "; under the wrong name: " + ", ".join(wrong) if wrong else ""))
    else:
        skip("her answer landed in the owner's record and in the world's rooms table under "
             "her name",
             "her answers arrived but the day ended before the owner wrote a room turn "
             "out of them")
    # the mid-conversation ask is a second shape of the same wire and does not
    # come round every day; said out loud rather than counted as proved
    if not [a for a in all_asks if a["about"] != "beat"]:
        NOTES.append("no mid-conversation turn ask came round to her: only the beat ask was "
                     "exercised")
        print("       (only the ask that opens a moment was exercised; no conversation of the "
              "owner's ran long enough to come round to her turn)")

    # only the turns this run added: her record is a copy of a live save and
    # already holds whatever the running process filed, rightly or not
    relayed = [t for t in _room_turns(her) if t not in seen_before]
    others = [t for t in relayed if t[1] and not roster.is_self(her.config, t[1])]
    if others:
        names = sorted({t[1] for t in others})
        owner_name = roster.record_name(her.config, orow["hub_id"]) or orow["name"]
        # the fault this catches: one process relaying four people's words and
        # every one of them filed under the relaying process's own name. The
        # room the beat opens has more than one speaker in it, so a record
        # naming only the owner is the whole set filed wrong.
        check(names != [owner_name],
              "the relayed turns of the other speakers are filed under THEIR names",
              "%d turn(s) arrived, from: %s" % (len(others), ", ".join(names[:6])))
    else:
        skip("the relayed turns of the other speakers are filed under THEIR names",
             "no turn of anybody else's was relayed to her inside the rehearsed day")

    queue = her.store.get("room_in", []) or []
    check(not queue, "her owner-side queue is empty at the end of the day",
          "%d row(s) left in it" % len(queue))

    # 3. a silence is an answer
    if silence_driven:
        sil = [a for a in hub.answers_from(hid) if a["silent"]]
        check(bool(sil), "a chosen silence went back to the room at once, as an answer",
              "%d silence(s) sent" % len(sil))
        live = owner.exchange.live() or {}
        waiting = [w for w in (live.get("awaiting") or []) if w.get("key") == her_key]
        check(not waiting, "and the owner's wait settled on it rather than running to a deadline",
              "still waiting on %d" % len(waiting))
        empties = [t for t in relayed if not t[2].strip()]
        check(not empties, "neither record gained an empty turn",
              "%d empty turn(s) in her record" % len(empties))
    else:
        skip("a chosen silence settles the owner's wait at once",
             "no ask reached her after the one that was armed to be answered empty, so there was "
             "nothing for her to answer with a silence")

    # 4. nothing a switched-off section owns was written to her save
    off = _off_sections(her.config)
    wrote = []
    for sect in off:
        owns = SECTION_KEYS.get(sect)
        if not owns:
            continue
        for k in owns["kv"]:
            b, a = before["kv"].get(k), after["kv"].get(k)
            if a is not None and a != b:
                wrote.append("%s wrote kv %s" % (sect, k))
        for t in owns["tables"]:
            if after["tables"].get(t, 0) > before["tables"].get(t, 0):
                wrote.append("%s wrote %d row(s) to %s"
                             % (sect, after["tables"][t] - before["tables"][t], t))
    check(not wrote, "no section her sheet switches off wrote to her save",
          "; ".join(wrote[:5]) if wrote
          else "%d section(s) off, %d key(s) and %d table(s) watched"
               % (len(off), sum(len(SECTION_KEYS.get(s, {}).get("kv", [])) for s in off),
                  sum(len(SECTION_KEYS.get(s, {}).get("tables", [])) for s in off)))
    unowned = sorted(s for s in off if s not in SECTION_KEYS)
    if unowned:
        print("       (%d switched-off section(s) own nothing in this tool's table, so nothing "
              "was watched for them: %s)" % (len(unowned), ", ".join(unowned[:8])))

    if not existence.sees_him(her.config) or not existence.has_chat(her.config):
        put_back = [k for k in NO_HIM_KV
                    if after["kv"].get(k) is not None and after["kv"].get(k) != before["kv"].get(k)]
        check(not put_back, "and nothing of his was written back into a save the repair pass "
                            "had cleared", ", ".join(put_back[:6]) or "none of %d key(s)"
                            % len(NO_HIM_KV))

    # 5. her gauges are the ones her config built
    spec = set((her.config.state.gauges or {}).keys())
    stored = set((her.store.get("gauges", {}) or {}).keys())
    extra = sorted(stored - spec)
    named = []
    for g in extra:
        owner_sect = str(((her.config.state.gauges or {}).get(g) or {}).get("owner") or "")
        named.append("%s (nothing her config builds%s)"
                     % (g, ", owner %s" % owner_sect if owner_sect else ""))
    check(not extra,
          "the gauges in her store after the day are the gauges her config built for her",
          "; ".join(named[:4]) if extra else "%d gauge(s), and %d her config declares and her "
          "store has not yet" % (len(stored), len(spec - stored)))

    # 6. her carrying block's headings follow her sheet
    carried = her.persona.carried_for()
    heads = [l.strip() for l in carried.split("\n") if l.strip().startswith("##")]
    if existence.has_chat(her.config):
        skip("her carrying block's headings do not define her against him",
             "she has a chat with him, so the with-him headings are hers")
    else:
        # The same block, rendered with the one answer the fork reads turned
        # the other way, and with the section that carries the heading given
        # something to say so that both arms render it. If the two headings
        # are the same bytes then the section is reused with the relationship's
        # wording and she is carrying a heading that defines her against a man
        # she has no chat with. Asked this way rather than by looking for a
        # word, because a word is what the fork exists to remove.
        mine, forced = _fork_headings(her)
        check(bool(mine) and mine != forced,
              "her carrying block's headings fork on her sheet rather than being the ones "
              "written for a character who has a chat with him",
              "%d heading(s), %d of them worded for her rather than for a chat with him"
              % (len(mine), len(mine - forced)))

    # 7. her diary
    diary = her.store.get("diary", []) or []
    if not her.config.diary.enabled:
        skip("her diary fired inside her own window", "the diary section is off for her")
    elif diary:
        check(True, "her diary fired inside her own window during the day",
              "%d entry(ies), newest %s" % (len(diary), (diary[-1] or {}).get("date", "?")))
    else:
        # the gate is named by the code that gates it, so this cannot say a
        # reason the diary does not have. `may_write` returns (may it, why
        # not) and is what `App.ordinary_tick` asks before every entry.
        c = her.config.diary
        scene = her.director.current or {}
        try:
            _ok, why = her.diary.may_write(scene)
        except Exception as e:
            why = "%s: %s" % (type(e).__name__, e)
        check(False, "her diary fired inside her own window during the day",
              "no entry; the gate it is standing at now is %r (window %s-%s, needs unsaid "
              "%s or something carried %s; she is at unsaid %d, phone %r)"
              % (why, c.hours_start, c.hours_end, c.min_unsaid, c.min_carried,
                 int(her.state.gauges.get("unsaid", 0) or 0),
                 str(scene.get("phone_access") or "-")))

    # 8. the world file has rows under her id about nobody but her
    bad = _world_rows(her, world_id, row["hub_id"])
    check(not bad, "the world file's rows under her id are about herself and nothing else",
          "; ".join(bad[:4]) if bad else "checked every table that carries a person")

    # 9. no row invented for somebody who is not hers
    invented = []
    rel = her.store.get("relationships", {}) or {}
    for k, v in (rel.items() if isinstance(rel, dict) else []):
        if roster.is_own(her.config, k) or roster.is_self(her.config, k):
            continue
        got = [f for f in ("situation", "last_seen", "unresolved") if (v or {}).get(f)]
        if got:
            invented.append("%s: %s" % (k, ", ".join(got)))
    lives = her.store.get("cast_life", {}) or {}
    for k in (lives if isinstance(lives, dict) else {}):
        if not roster.is_own(her.config, k):
            invented.append("%s: a day of her own written by this process" % k)
    check(not invented,
          "nothing in her save invents a situation or a day for one of the owner's people",
          "; ".join(invented[:4]) if invented else "%d person(s) on her roster checked"
          % len(rel))

    # 10. her prompts name nobody else who runs
    leaked = _leaks(her)
    check(not leaked, "no prompt of hers names another registered character",
          ", ".join(leaked[:6]) if leaked else "her system prompt and what she carries")

    # 11. the news relevance step, if it ran
    _news_check(her, hrec)


def _fork_headings(her):
    """(the headings she carries, the headings she would carry if her sheet
    said she has a chat with him).

    A heading only renders when its section has something to say, so the one
    section that carries a forked heading is given a line first: what she has
    told somebody about herself. Everything is written into the SCRATCH save
    and the answer on her sheet is put back, so nothing live is touched and
    the two renders differ in exactly one thing."""
    ex = her.config.character.existence
    was = getattr(ex, "with_him", "none")
    had = her.store.get("self_claims", None)
    seeded = list(had or []) + [{"date": her.clock.date_str(),
                                 "text": "a line put here by the rehearsal, so the heading "
                                         "over it has to render"}]
    try:
        her.store.set("self_claims", seeded)
        mine = _heads(her)
        ex.with_him = "chat"
        forced = _heads(her)
    except Exception:
        return set(), set()
    finally:
        ex.with_him = was
        her.store.set("self_claims", had)
    return mine, forced


def _heads(her):
    """The headings of what she carries, built fresh.

    `carried_for` renders the sections of the LAST system-prompt build, so a
    render taken without building the system prompt first answers about the
    previous one and every fork reads as dead."""
    her.persona.system_for("friend")
    text = her.persona.carried_for()
    return {l.strip() for l in text.split("\n") if l.strip().startswith("##")}


def _world_rows(her, world_id, char_id):
    """Every row in the world file carrying her id, read back, and whether it
    is about her. The partition (`world/shared.py`) says a character who does
    not keep the world writes only the rows about herself, in three tables;
    the rest of the file is the owner's. Who a row is about is resolved
    through the roster, because the world file spells a person by her roster
    key and her own record spells her by her Japanese name."""
    import sqlite3
    from sim import roster
    path = getattr(her.world_shared, "path", "")
    if not path or not os.path.exists(path):
        return ["there is no world file to read"]
    me = roster.key_of(her.config, her.config.character.name)
    bad = []
    con = sqlite3.connect("file:%s?mode=ro" % path.replace("\\", "/"), uri=True)
    try:
        tables = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        for t in sorted(tables):
            cols = [r[1] for r in con.execute("PRAGMA table_info(%s)" % t)]
            if "char_id" not in cols:
                continue
            rows = con.execute("SELECT * FROM %s WHERE char_id = ?" % t, (char_id,)).fetchall()
            if not rows:
                continue
            person_col = next((c for c in ("person", "member", "who", "owner", "holder")
                               if c in cols), "")
            if not person_col:
                # a table with no person column says nothing about whose row
                # it is. The settled lines are the live case: they have no
                # person and the owner reads them into its own ledger, which
                # is the design and not a breach.
                if t not in ("settled", "meta"):
                    bad.append("%s carries %d row(s) of hers and no column saying who they "
                               "are about" % (t, len(rows)))
                continue
            i = cols.index(person_col)
            wrong = sorted({str(r[i]) for r in rows
                            if str(r[i]) and not roster.same(her.config, str(r[i]), me)})
            if wrong:
                bad.append("%s has %d row(s) of hers about %s"
                           % (t, len(rows), ", ".join(wrong[:3])))
    finally:
        con.close()
    return bad


def _leaks(her):
    """Every registered character's name or place that her rendered prompt
    says. The same two readers `tools/character_leaks.py` and
    `tools/new_character.py verify` use, so the three cannot give three
    answers about one prompt."""
    from tools import new_character, character_leaks, character_names, registry  # noqa: F401
    # building that set loads every registered character's config, and each
    # one prints its own boot notes: not this check's output
    out, sys.stdout = sys.stdout, io.StringIO()
    try:
        theirs = new_character._others_material(her.config, "")
    finally:
        sys.stdout = out
    text = her.persona.system_for("him") + "\n" + her.persona.carried_for()
    said = set()
    for line in text.split("\n"):
        line = re.sub(r"\S+[\\/]\S+|https?://\S+", " ", line)
        said |= set(character_leaks.JA.findall(line)) | set(character_leaks.EN.findall(line))
    return sorted(n for n in theirs if n in said)


def _news_check(her, hrec):
    """Whether a national story made relevant to her names a station or a
    line her own map does not give her. Her news picker wrote that she takes
    a line through a station her sheet puts her nowhere near, to a class on
    the other side of the city, and she had not said it out loud yet.

    The step itself runs in a TOOL on its own clock (`tools/zeitgeist.py`),
    not in the loop, so a rehearsal of one day never exercises it. What CAN
    be asked here is whether what is on her disk stands up: every line of
    hers is put through the same judge the fetcher and the reader both use
    (`world/rails.py`, `refuse`), which reads the lines she rides and the
    stations she uses out of her own map and her own train watch and answers
    with the name it got wrong and why."""
    path = str(getattr(her.config.world, "zeitgeist_file", "") or "")
    if not path or not os.path.exists(path):
        skip("what is going round is made relevant to her by places she has",
             "she has no file of what is going round to read")
        return
    try:
        blob = json.load(io.open(path, encoding="utf-8"))
    except (OSError, ValueError) as e:
        skip("what is going round is made relevant to her by places she has",
             "her file of what is going round did not read (%s)" % type(e).__name__)
        return
    items = blob.get("items") if isinstance(blob, dict) else blob
    from world import rails
    bad = []
    for it in (items or []):
        hook = str((it or {}).get("hook") or "")
        if not hook:
            continue
        got = rails.refuse(hook, her.config)
        if got:
            bad.append("%s: %s" % (got[0], got[1]))
    check(not bad, "what is going round is made relevant to her by places she has",
          "; ".join(bad[:4]) if bad
          else "%d line(s) of hers, each put through the judge her own map and train watch "
               "settle" % len(items or []))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("key", help="the character who reads somebody else's world")
    ap.add_argument("--root", default="characters",
                    help="where the bundles live; a scratch directory rehearses a promotion "
                         "nobody has registered")
    ap.add_argument("--step", type=int, default=20, help="minutes of her clock per pass")
    ap.add_argument("--hours", type=float, default=24, help="how much of her day to live")
    ap.add_argument("--start", default="06:00", help="what time of her day it starts at")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    import logger
    if not args.verbose:
        logger.log = lambda m, to_console=True: None
    rehearse(args.key, root=args.root, step_minutes=args.step, hours=args.hours,
             start_hm=args.start, verbose=args.verbose)
    print()
    if FAILURES:
        print("[rehearsal] %d failure(s): %s" % (len(FAILURES), "; ".join(FAILURES[:5])))
        return 1
    if NOTES:
        print("[rehearsal] the seam holds over one day, with %d check(s) not exercised"
              % len(NOTES))
    else:
        print("[rehearsal] the seam holds over one day: her beat survived the planner and "
              "reached her, her turn came back and was filed by its speaker, her silence "
              "settled the wait, and nothing she has not got wrote to her save")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
