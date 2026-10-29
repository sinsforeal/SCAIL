"""The world file, written by the character who owns it and read by another.

Everything a character knows about the world she lives in is in her own save,
so a second process running one of the people beside her would plan a day the
first process never had. `world/shared.py` is the copy that crosses the
boundary. What has to be true of it is three things, and this drives all three
through the code that runs live rather than through the store's own writers:

1. the plan writes who is where, and who these people are;
2. the day's one truth writes a line the day has settled, as it accepts it;
3. an exchange writes a turn the moment it is stamped.

Then a SECOND `Config` -- the other character's config file, copied so nothing
of hers is touched, pointed at the same world as a reader rather than as the
owner -- opens the same file through a `mode=ro` URI and reads every row back.

And the partition (docs/shared-world.md §2): that second character writes the
rows about HERSELF and only those -- her own day's windows land, a row about
somebody else and a row in any other table are refused, the world goes on
saying who keeps it -- and the owner's planner then prefers her rows for a
window and falls back to its own draw of her week where she wrote nothing.
The owner's own rows are proved unchanged against a copy of the live world
file, taken through sqlite so the copy is not a torn image and never written.

The first character is built on a copy of her save with the model stubbed and
the network refused, and the world directory is pointed at a temp directory,
so this spends nothing and touches neither live save nor the live world.

    python tools/world_test.py
"""
import io
import json
import os
import shutil
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

from sim import roster                # noqa: E402
from sim.wiring import wire            # noqa: E402
from tools import harness              # noqa: E402
from world.shared import SharedWorld   # noqa: E402

WORLD_ID = "worldtest"
FAILS = []


def ok(label, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + label + (f": {detail}" if detail else ""))
    if not cond:
        FAILS.append(label)
    return cond


class Canned:
    """`LLM.call_json`, answered from a table instead of from a provider.

    A role nobody expected raises rather than returning an empty answer, so a
    path this harness has not thought about announces itself."""

    def __init__(self, answers):
        self.answers = answers
        self.asked = []

    def install(self, app):
        app.llm.call_json = self._call
        app.llm.call = self._refuse

    def _refuse(self, *a, **k):
        raise AssertionError("this harness writes no prose: only call_json is answered")

    def _call(self, role, messages, **k):
        self.asked.append(role)
        if role not in self.answers:
            raise AssertionError(f"the harness has no answer for the role {role!r}")
        return self.answers[role], json.dumps(self.answers[role], ensure_ascii=False)


def point_at(app, tmp, owner=True):
    """Send this App's world writes to a temp directory, and rebuild the three
    wires that carry them. The config object is the one the App holds, so the
    modules read the same switch the runtime would have handed them."""
    app.config.world.shared_dir = tmp
    app.config.world_shared.enabled = True
    app.config.world_shared.id = WORLD_ID
    app.config.world_shared.owner = owner
    app.world_shared = SharedWorld(app.config)
    wire(app.cast, world_shared=app.world_shared)
    wire(app.exchange, world_shared=app.world_shared)
    wire(app.ledger, world_shared=app.world_shared)
    return app.world_shared


def reader_config(tmp):
    """The other character's config, copied, pointed at the same world as a
    reader. Her file is copied because `Config` writes the merged defaults back
    to the path it was given, and nothing of hers is his harness's to rewrite."""
    from config import Config
    src = "config_yukarin.json"
    if not os.path.exists(src):
        return None
    dst = os.path.join(tmp, "config_reader.json")
    shutil.copyfile(src, dst)
    cfg = Config(path=dst)
    cfg.world.shared_dir = tmp
    cfg.world_shared.enabled = True
    cfg.world_shared.id = WORLD_ID
    cfg.world_shared.owner = False
    return cfg


def live_copy(tmp):
    """The live world file as a read-only INPUT: copied through sqlite's own
    backup so the copy is whole (a file copy of a database being written is a
    torn image), into the temp directory. Nothing here writes to either."""
    try:
        with open("config.json", "r", encoding="utf-8") as fh:
            c = json.load(fh)
        wid = str((c.get("world_shared") or {}).get("id") or "")
        home = str((c.get("world") or {}).get("shared_dir") or "")
        src = os.path.join(home, wid, "world.db") if (wid and home) else ""
        if not src or not os.path.exists(src):
            return "", ""
        out = os.path.join(tmp, "live")
        os.makedirs(os.path.join(out, wid), exist_ok=True)
        a = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
        b = sqlite3.connect(os.path.join(out, wid, "world.db"))
        with b:
            a.backup(b)
        a.close()
        b.close()
        return out, wid
    except (OSError, ValueError, sqlite3.Error) as e:
        print(f"  note the live world was not copied: {type(e).__name__}: {e}")
        return "", ""


def overlaps(a, b):
    """Do these two windows of a day cover any of the same time?"""
    return a[0] < b[1] and b[0] < a[1]


def main():
    tmp = tempfile.mkdtemp(prefix="scail_world_")
    db = os.path.join(tmp, "world.db")
    print(f"[world] temp: {tmp}")

    harness.refuse_network()
    harness.refuse_model_before_build()
    app = harness.build_on(db)
    w = point_at(app, tmp)
    print(f"[world] the owner writes {w.path}")

    d = app.clock.date_str()
    canned = Canned({
        "cast_day": {
            "beats": [{"time": "12:40", "who": "Rena-chan", "kind": "group", "salience": 2,
                       "about": "she says the four of them are eating on the roof at lunch"}],
            "settled": ["they are eating on the roof at lunch"],
            "notes": "a harness day",
            "absent": [],
        },
        "cast_beat": {"ja": "屋上でお昼にしよ"},
        "cast_life": {"text": "a harness day", "carry": ""},
    })
    canned.install(app)

    # ---- 1. the plan
    schedule = {"date": d, "blocks": [
        {"start": "08:30", "end": "15:30", "activity": "school", "location": "school",
         "with": "", "phone_access": "none"},
        {"start": "15:30", "end": "22:00", "activity": "home", "location": "home",
         "with": "", "phone_access": "free"}]}
    app.cast.plan_day(schedule, d, force=True)
    where = w.whereabouts(d)
    roster_rows = w.roster()
    ok("the plan wrote who is where", bool(where), f"{len(where)} row(s)")
    ok("the plan wrote the roster mirror", bool(roster_rows), f"{len(roster_rows)} person/people")
    ok("a roster row carries no sheet",
       all(set(r) == {"key", "name", "ja", "role_id", "calls", "week", "ts", "char_id"} for r in roster_rows))
    if where:
        r = where[0]
        ok("a whereabouts row is stamped and owned", bool(r["ts"]) and bool(r["char_id"]),
           f"{r['person']} {r['from_hm']}-{r['to_hm']} {r['place']} ({r['source']})")

    # ---- 2. the day's one truth
    lines = app.ledger.settled(d)
    settled = w.settled(d)
    ok("the ledger wrote the line it accepted", bool(settled),
       "; ".join(x["line"] for x in settled)[:90] or f"the ledger had {len(lines)} line(s)")
    n_before = len(settled)
    app.ledger.settled(d)
    ok("reading it again writes nothing twice", len(w.settled(d)) == n_before)

    # ---- 3. a turn, as it is stamped
    live = {"date": d, "hm": "12:41", "who": "Rena-chan", "kind": "group", "turns": [],
            "rounds": 0, "skipped": 0, "aways": 0, "side": "theirs", "gist": "", "about_him": ""}
    app.store.set("exchange_live", live)
    app.exchange._awake = lambda *a, **k: True
    took = app.exchange.absorb({"who": "Rena-chan", "kind": "group", "ja": "屋上いこ"})
    turns = w.turns(d)
    ok("a turn arrives as the exchange stamps it", bool(took) and bool(turns),
       (turns[-1]["room"] + " " + turns[-1]["who"] + " " + turns[-1]["ja"]) if turns else "absorb took nothing")
    if turns:
        ok("the turn says who else was in the room", bool(turns[-1]["witnessed_by"]),
           turns[-1]["witnessed_by"][:70])

    # ---- 4. a second Config, reading the same file
    cfg = reader_config(tmp)
    if cfg is None:
        print("  note no second character's config in the tree; the reader half is not run")
    else:
        r = SharedWorld(cfg, char_id="reader")
        ok("the reader is not the owner", not r.owner and r.enabled)
        ok("the reader opened the same file", r.path == w.path, r.path)
        ok("the reader reads the whereabouts", len(r.whereabouts(d)) == len(where), f"{len(r.whereabouts(d))} row(s)")
        ok("the reader reads the settled lines", len(r.settled(d)) == len(w.settled(d)))
        ok("the reader reads the turns", len(r.turns(d)) == len(turns))
        ok("the reader reads the roster", len(r.roster()) == len(roster_rows))
        wrote = r.put_settled(d, "a reader may not write this")
        ok("a write of the owner's own kind is refused", wrote is False and len(w.settled(d)) == n_before)
        counts = r.counts() or {}
        print("  " + " | ".join(f"{k} {v}" for k, v in counts.items()))

    # ---- 5. the partition: the rows she writes about herself
    if cfg is not None:
        person = next((n for n in (app.cast.plans(d) or {}) if not roster.is_self(app.config, n)), "")
        key = roster.key_of(app.config, person) if person else ""
        mine = SharedWorld(cfg, char_id="reader", me=key)
        # one row of the owner's that her own day does not cover, so the
        # fallback is a row and not an absence
        w.put_whereabouts(d, key, "06:30", "07:30", place="the early train",
                          reach="glance", source="their week")
        hers = [("07:30", "16:00", "the studio", "none"), ("20:00", "22:00", "home", "free")]
        n = mine.put_own_day(d, key, hers)
        ok("she writes her own day", n == 2, f"{n} window(s) as {key}")
        rows = mine.rows("whereabouts", "date=? AND person=? AND source=?",
                         (d, key, SharedWorld.OWN_DAY)) or []
        ok("her rows carry her own source and her own id",
           len(rows) == 2 and all(x["char_id"] == "reader" for x in rows))
        ok("a row about somebody else is refused",
           mine.put_whereabouts(d, "somebody else", "09:00", "10:00",
                                source=SharedWorld.OWN_DAY) is False)
        ok("a row in one of the owner's tables is refused",
           mine.put_gossip("x", "a rumour that is not hers to write") is False
           and mine.put_person("x", name="nobody") is False
           and mine.put_turn(d, "group", "somebody", "12:00", "ここは私の部屋じゃない") is False)
        ok("a settled line must name one of her own planners",
           mine.put_settled(d, "a line with no planner behind it") is False
           and mine.put_settled(d, "her own plan settled this",
                                source=SharedWorld.OWN_PLAN) is True)
        # the preference, row by row: hers stand, the owner's stand where she
        # wrote nothing, and the owner's rows that cover her own windows go
        raw = w.rows("whereabouts", "date=? AND person=?", (d, key)) or []
        merged = [x for x in w.whereabouts(d) if x["person"] == key]
        windows = [(x["from_hm"], x["to_hm"]) for x in merged if x["source"] == SharedWorld.OWN_DAY]
        dropped = [x for x in raw if x not in merged]
        ok("the owner's read prefers her rows for a window",
           len(windows) == 2 and all(any(overlaps((x["from_hm"], x["to_hm"]), win) for win in windows)
                                     for x in dropped),
           f"{len(dropped)} of the owner's row(s) covered by her own")
        ok("and falls back to the owner's row where she wrote nothing",
           any(x["source"] == "their week" and x["from_hm"] == "06:30" for x in merged))
        ok("nobody else's rows moved",
           len([x for x in w.whereabouts(d) if x["person"] != key])
           == len([x for x in (w.rows("whereabouts", "date=?", (d,)) or []) if x["person"] != key]))
        # and what the owner's planner is told, which is the point of it
        line = app.cast.plan_line(person, d)
        ok("the owner's line for her is her own day", "the studio" in line and "school" not in line, line[:90])

        def ts_at(hm):
            """A moment at this hour of her today, from the clock she runs on."""
            now = app.clock.now_ts()
            cur = app.clock.hm(now)
            return now + ((int(hm[:2]) * 60 + int(hm[3:])) - (int(cur[:2]) * 60 + int(cur[3:]))) * 60

        ok("her phone is read from her own row",
           app.cast.available(person, ts_at("09:00")) == 0.15
           and app.cast.available(person, ts_at("21:00")) == 1.0,
           "09:00 in the studio with the phone away, 21:00 at home with it")
        mc = sqlite3.connect(f"file:{w.path}?mode=ro", uri=True)
        meta = {k: v for k, v in mc.execute("SELECT key, value FROM meta").fetchall()}
        mc.close()
        ok("the world still says who keeps it",
           meta.get("owner") == w.char_id and meta.get("world") == WORLD_ID,
           f"owner={meta.get('owner')} world={meta.get('world')}")
        ok("and she is recorded as a writer of her own rows",
           "reader" in str(meta.get("writers") or ""), str(meta.get("writers") or "")[:80])

    # ---- 6. nothing changed for the owner's own rows
    home, wid = live_copy(tmp)
    if not home:
        print("  note no live world file to read; the owner's-rows check is not run")
    else:
        from types import SimpleNamespace as NS
        cfg2 = NS(world_shared=NS(enabled=True, id=wid, owner=True, reader_writes_own_rows=True),
                  world=NS(shared_dir=home), character=NS(name="owner"))
        live = SharedWorld(cfg2, char_id="owner")
        con = sqlite3.connect(f"file:{live.path}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        days = [x[0] for x in con.execute("SELECT DISTINCT date FROM whereabouts ORDER BY date")]
        same, rows, stood_down = True, 0, 0
        for day in days:
            was = [dict(x) for x in con.execute(
                "SELECT * FROM whereabouts WHERE date=? ORDER BY date, from_hm", (day,))]
            rows += len(was)
            got = live.whereabouts(day)
            # nothing is rewritten on the way out: every row that comes back
            # is one of the stored rows, unchanged
            same = same and all(r in was for r in got)
            # and the only rows left out are the OWNER's, for a person whose
            # own process wrote a window about herself over the top of them.
            # This used to be "the list comes back exactly as stored", which
            # was true only while the owner was the world's one writer.
            for r in was:
                if r in got:
                    continue
                stood_down += 1
                if str(r.get("source") or "") == SharedWorld.OWN_DAY:
                    same = False
        con.close()
        ok("the owner's own rows read back unchanged", same and bool(days),
           f"{rows} row(s) over {len(days)} day(s) of the live world, read through the "
           f"preference; {stood_down} of the owner's rows stood down for a window a second "
           f"writer wrote about herself")

    w.close()
    print()
    if FAILS:
        print(f"[world] {len(FAILS)} FAILURE(S): {', '.join(FAILS)}")
        return 1
    print(f"[world] all clear; the world file is {w.path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
