"""Every kind of character the sheet can declare, built once each.

A character says what kind of thing she is with five answers on her sheet
(`embodied`, `in_world`, `sees_him`, `has_account`, `with_him`) and everything else
follows: which sections run, which world paths are blanked, which program
builds the rest of her. Two kinds have ever been booted -- the first
character's (a body, a world, a phone-app view, an account) and the second's
(a body, no world, resident, no account). The third character's in-world
package was the first to answer "a body, a world, no account", and it could
not build her system prompt: the taste module was built for every embodied
character and read the account store, and the account monitor made a
directory from a blanked key. Nothing had ever tried that combination, so
nothing had failed.

This tries all of them. For each combination of the answers it writes a whole
scratch BUNDLE under the temp directory -- her sheet, her values for the holes
in the library's prompts, her voice, her speech guide, her household, her map
and, when she is in a world, a world of two people written for the run --
composes her config from it with `tools/new_character.py`, builds the whole
App the way smoke does (console, no sensors, the logger stubbed, every model
call and every network connection refused), renders her system prompt and what
she carries the way the first reply would, and asserts that none of it names a
character who actually runs. The program is the one the answer implies
(`tomoe` for a character in a world, `resident` for one who is not).

Every kind used to be built from a copy of `config.json` with the identity
block rewritten, which meant forty builds of the FIRST character in a costume:
her fills, her household, her map and her roster, and by construction no leak
could show. Nothing here is read out of a character who runs; the name and the
place belong to nobody (`tools/fixtures/neutral_fills.json`).

Reported by default; `--strict` fails on any combination that does not
build, for smoke once every combination does.

    python tools/existence_matrix.py              # the table
    python tools/existence_matrix.py --strict     # exit 1 on a failing row
    python tools/existence_matrix.py --only "embodied,in_world,digest,no_account"
"""
import argparse
import io
import itertools
import json
import os
import re
import sys
import tempfile
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

SEES = ("digest", "resident", "none")


def _stub_logger():
    import logger
    logger.setup = lambda out_dir: None
    logger.finish = lambda: None
    logger.log = lambda m, to_console=True: None
    logger.log_llm = lambda *a, **k: None
    logger.write_artifact = lambda *a, **k: None


def _label(embodied, in_world, sees, account, owner=True, with_him="chat"):
    # A world has one writer and any number of readers (docs/shared-world.md),
    # so "in a world" is two kinds of character and not one: the one who keeps
    # it and the one who reads it. The reader runs none of the machinery that
    # writes the world (`Config.REQUIRES`, the `world_owner` property) and
    # takes those rows out of the file instead, which is a different build.
    # Outside a world the question does not arise and the row is not doubled.
    return ",".join([
        "embodied" if embodied else "no_body",
        "in_world" if in_world else "no_world",
        sees,
        "account" if account else "no_account",
    ] + (["owns_world" if owner else "reads_world"] if in_world else [])
      + ([] if with_him == "chat" else ["no_him"]))


def _sheet(embodied, in_world, sees, account, path, with_him="chat"):
    """The smallest sheet the config accepts: who she is and what kind."""
    sheet = {
        "_note": "synthetic, written by tools/existence_matrix.py; never a person",
        "id": "matrix",
        "name": "Matrix",
        "existence": {"embodied": embodied, "in_world": in_world, "sees_him": sees, "has_account": account,
                      "with_him": with_him},
        "temperament": {},
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(sheet, fh, indent=1)


def _bundle(d, key, embodied, in_world, sees, account, owner=True, with_him="chat"):
    """A whole scratch bundle for one kind of character, under `d`.

    Everything that is this person: her sheet, her values for the holes in the
    library's prompts, her voice, her speech guide and the manifest that says
    how she is run. Nothing is copied out of a character who actually runs --
    which is the whole point. The matrix used to build each kind from a copy
    of the FIRST character's config with the identity block rewritten, so
    every one of the forty was her in a costume: her fills, her household, her
    map, her roster, and by construction no leak could show.
    """
    bdir = os.path.join(d, key)
    os.makedirs(os.path.join(bdir, "prompts"), exist_ok=True)
    _sheet(embodied, in_world, sees, account, os.path.join(bdir, "sheet.json"), with_him=with_him)
    with io.open(os.path.join(ROOT, "tools", "fixtures", "neutral_fills.json"),
                 encoding="utf-8") as fh:
        fills = json.load(fh)
    with io.open(os.path.join(bdir, "fills.json"), "w", encoding="utf-8") as fh:
        json.dump(fills, fh, ensure_ascii=False, indent=1)
    # her prompt directory IS the bundle's here: this builds a character
    # rather than installing one, so there is nothing to generate a copy for.
    prompts_dir = os.path.join(bdir, "prompts").replace("\\", "/")
    with io.open(os.path.join(bdir, "prompts", "bible.md"), "w", encoding="utf-8") as fh:
        fh.write(BIBLE)
    with io.open(os.path.join(bdir, "prompts", "style.md"), "w", encoding="utf-8") as fh:
        fh.write(STYLE)
    world = _scratch_world(d, in_world)
    for name, blob in (("household.json", HOUSEHOLD), ("map.json", MAP), ("taste.json", TASTE)):
        with io.open(os.path.join(bdir, name), "w", encoding="utf-8") as fh:
            json.dump(blob, fh, ensure_ascii=False, indent=1)
    manifest = {
        "_note": "synthetic, written by tools/existence_matrix.py; never a person",
        "key": key, "name": "Sample Test", "hub_id": key,
        "config": os.path.join(d, "config_%s.json" % key).replace("\\", "/"),
        "db": os.path.join(d, "save.db").replace("\\", "/"),
        "program": "tomoe" if in_world else "resident",
        "launcher": "", "task": "", "match": "",
        "world": {"id": "matrix", "owner": bool(owner)},
        "prompts_dir": prompts_dir,
        "prompts_generated": True,
        "registered": False,
        "files": {"world.character_file": "sheet.json",
                  "character.neutral_file": "fills.json",
                  "world.household_file": "household.json",
                  "world.geography_file": "map.json",
                  "world.taste_file": "taste.json"},
        "blank": [],
        "config_overrides": {
            "character": {
                "name": "Sample",
                "program": "tomoe" if in_world else "resident",
                "existence": {"embodied": embodied, "in_world": in_world, "sees_him": sees,
                              "has_account": account, "with_him": with_him},
                "style_prompt": prompts_dir + "/style.md",
                "style_ja_prompt": prompts_dir + "/style.md",
                # the world's roster and its sheets, written for this run
                "cast_file": world.pop("_cast_file", ""),
                "cast_sheets_dir": world.pop("_cast_sheets_dir", ""),
            },
            "models": {"persona": {"prompt": prompts_dir + "/bible.md"}},
            "world_shared": {"enabled": True, "id": "matrix", "owner": bool(owner)},
            "talkapp": {"enabled": False},
            # no face of her own, so nothing publishes somebody else's
            "reactions": {"enabled": False, "character": ""},
            # the world she is in, written for this run and nobody's
            "world": world,
            "cast": {"mechanisms_dir": world.pop("_mechanisms_dir", ""),
                     "types_file": world.pop("_types_file", "")},
        },
    }
    with io.open(os.path.join(bdir, "bundle.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)
    return bdir, manifest


HOUSEHOLD = {
    "_what": "synthetic, written by tools/existence_matrix.py; never a person",
    "members": {
        "mother": {"relation": "mother", "name": "Sample One", "age": 42,
                   "work": "part time, at the shop by the station"},
    },
    "money": {"month": "an ordinary month; nothing spare and nothing short"},
    "schedules": {"mother": {"work_place": "the shop", "days": ["mon", "tue", "thu", "fri"],
                             "from": "09:30", "to": "16:30"}},
}

MAP = {
    "_what": "synthetic, written by tools/existence_matrix.py; never a place",
    "home": {"station": "North", "address_en": "1-1-1 North, Sample City",
             "what": "a flat on the second floor, ten minutes from the station"},
    "station": {"name_ja": "北駅", "address_en": "1-1 North, Sample City",
                "lines": ["the Central line (her commute, inbound)"],
                "what": "one island platform"},
    "school": {"name": "Sample High School", "address_en": "2-2 South, Sample City"},
    "commute": {"leaves_home": "07:40", "route": "walk to North -> the Central line -> South",
                "stops_inbound": ["North", "Middle", "South"]},
    "areas": [{"key": "home_area", "name": "North Ward"},
              {"key": "school_area", "name": "South Ward"}],
    "home_area": {"places": {"the shopping street": "shops, a supermarket, a bakery"}},
    "school_area": {"places": {"the station mall": "shops and a food floor"}},
    "elsewhere": {},
}

TASTE = {"_what": "synthetic, written by tools/existence_matrix.py",
         "likes": [], "dislikes": [], "queries": []}

CAST = {
    "_comment": "synthetic, written by tools/existence_matrix.py; never a person",
    "self": {"key": "Owner", "name": "Owner", "ja": "所有者", "role_id": "world_owner",
             "role": "the character who keeps this world", "agent": "owner"},
    "people": {
        "One": {"name": "One", "ja": "一号", "reading": "いちごう", "role_id": "ringleader",
                "role": "a friend from her class", "closeness": 50, "standing": 50, "tension": 10,
                "week": {}, "aliases": []},
        # somebody in the scratch world who runs her own process, so the ask
        # that goes out to a member who writes her own turns can be built and
        # read here (`sim/rooms.py`)
        "Two": {"name": "Two", "ja": "二号", "reading": "にごう", "role_id": "confidante",
                "role": "a friend from the club", "closeness": 45, "standing": 50, "tension": 10,
                "week": {}, "aliases": [], "agent": "two"},
    },
}


def _scratch_world(d, in_world):
    """A whole world for this run: a roster of two, their sheets, their
    mechanisms, their types, the places and the school year. Nothing is read
    out of the live world, so a kind of character that is IN a world is built
    against one that belongs to nobody.

    Returns the `world` block her config takes, with the two `cast` paths
    under private keys the caller pops off."""
    w = os.path.join(d, "world")
    os.makedirs(os.path.join(w, "cast"), exist_ok=True)
    os.makedirs(os.path.join(w, "cast_mechanisms"), exist_ok=True)

    def put(name, blob):
        p = os.path.join(w, name)
        with io.open(p, "w", encoding="utf-8") as fh:
            json.dump(blob, fh, ensure_ascii=False, indent=1)
        return p.replace("\\", "/")

    cast = put("cast.json", CAST)
    types = put("cast_types.json", {"_what": "synthetic", "types": {}})
    places = put("places.json", {"_what": "synthetic", "nodes": [
        {"key": "home", "name": "her flat", "kind": "home"},
        {"key": "school", "name": "Sample High School", "kind": "school"}]})
    school = put("school_calendar.json", {"_what": "synthetic", "terms": [], "breaks": [],
                                          "events": [], "fixtures": [], "days": {}})
    holidays = put("jp_holidays.json", {})
    events = put("local_events.json", {"_what": "synthetic", "events": []})
    for who in CAST["people"]:
        with io.open(os.path.join(w, "cast", who.lower() + ".md"), "w", encoding="utf-8") as fh:
            fh.write("# %s\n\nA friend. Synthetic, written by tools/existence_matrix.py.\n" % who)
        with io.open(os.path.join(w, "cast_mechanisms", who + ".json"), "w",
                     encoding="utf-8") as fh:
            json.dump({"_what": "synthetic", "person": who, "mechanisms": []}, fh,
                      ensure_ascii=False, indent=1)
    return {
        "places_file": places if in_world else "",
        "school_calendar_file": school if in_world else "",
        "holidays_file": holidays if in_world else "",
        "local_events_file": events if in_world else "",
        "shared_dir": os.path.join(d, "worlds").replace("\\", "/") if in_world else "",
        "_mechanisms_dir": os.path.join(w, "cast_mechanisms").replace("\\", "/"),
        "_types_file": types,
        "_cast_file": cast,
        "_cast_sheets_dir": os.path.join(w, "cast").replace("\\", "/"),
    }


BIBLE = """# Who she is

Sample Test, fifteen, in Sample City. She goes to school, she has two friends
called One and Two, and she is on her phone more than she means to be.

This file belongs to nobody. It exists so that every kind of character the
sheet can declare can be built and rendered without borrowing a real
character's voice.
"""

STYLE = """# How she writes

Short sentences. She says the plain thing first. No images she would not have
made, and no feeling given a place or a size.
"""


def _room_checks(app, in_world, owner):
    """What a room hands a writer, on a character who does not exist.

    Three things this cannot be allowed to lose, because each of them was
    absent for weeks before anybody read a transcript: the handful of concrete
    things a speaker has to bring up, the record of what the conversation has
    already tried, and that record travelling on the ask to somebody who
    writes her own turns. A new character composed from a bundle gets all
    three or none, so it is checked on every kind rather than on the one that
    happens to run.

    Returns "" when it holds, else what is missing."""
    from sim.pocket import Pocket
    date = app.clock.date_str()
    if in_world and owner:
        # a person with something to say and a conversation with a move in it
        from sim import roster
        key = "One"
        Pocket(app.config, app.store, app.clock).put(
            date, key, [{"what": "the thing that happened at the shop", "source": "their day"}])
        rec = {"date": date, "hm": "17:00", "who": key, "kind": "group", "rounds": 1,
               "moves": [{"who": "One", "hm": "16:58", "gist": "asked whether anybody is coming"}],
               "turns": [{"who": "One", "ja": "ねえ、今日どうする？", "hm": "16:58"}]}
        seen = {}

        def record(role, messages, **kw):
            seen["text"] = "\n\n".join(str(m.get("content") or "") for m in messages)
            return None, ""

        app.llm.call_json = record
        app.exchange._one_speaker(roster.record_name(app.config, key), "group", rec["turns"], rec=rec)
        text = seen.get("text") or ""
        if "THINGS YOU COULD BRING UP TODAY" not in text:
            return "an in-world speaker's turn carries no pocket"
        if "MOVES ALREADY MADE IN THIS CONVERSATION" not in text:
            return "an in-world speaker's turn carries no moves ledger"
        # ...and the same list on the ask to somebody who writes her own turns
        rooms = app.exchange._rooms()
        rooms.join("group", "Two")
        if not rooms.ask("group", "group", date, "Two", turns=rec["turns"], moves=rec["moves"]):
            return "the ask to a member who writes her own turns went nowhere"
        out = app.store.get("room_out", []) or []
        env = (out[-1] if out else {}).get("room") or {}
        if not env.get("moves"):
            return "the ask envelope carries no moves list"
    if not in_world and getattr(app, "peers", None) is not None:
        # a character with a circle of her own and no world still has
        # something of her own to bring up
        app.store.set("director_current", {"activity": "at her desk", "sensory": "the fan on low"})
        block, ids = app.peers._pocket_block()
        if not block or not ids:
            return "a resident with a circle gets no pocket"
    return ""


def build_one(embodied, in_world, sees, account, keep=False, owner=True, with_him="chat"):
    """(ok, note): the App built, or the exception type and where."""
    from tools import harness
    tag = _label(embodied, in_world, sees, account, owner, with_him).replace(",", "_")
    d = tempfile.mkdtemp(prefix="scail_matrix_" + tag + "_")
    key = "matrix"
    db = os.path.join(d, "save.db")
    # a whole bundle of her own, and her config composed from it by the one
    # tool that composes a config (`tools/new_character.py`), so this builds
    # what a fifth character would be rather than a copy of the first one
    _bundle(d, key, embodied, in_world, sees, account, owner=owner, with_him=with_him)
    from tools import new_character
    new_character.set_root(d)
    try:
        cfgtree, man = new_character.compose_config(key, note=lambda *a: None)
        cfg = man["config"]
        with io.open(cfg, "w", encoding="utf-8") as fh:
            json.dump(cfgtree, fh, ensure_ascii=False, indent=1)
        app = harness.build_on(db, cfg, copy=False)
        harness.refuse_model(app)
        # built is not bootable: the third character's in-world package built
        # and then could not render her system prompt, so the prompt and what
        # she carries are rendered here the way the first reply would
        rendered = app.persona.system_for("him") + "\n" + app.persona.carried_for()
        # and she says nobody's name but her own. A character composed from a
        # bundle that names nobody must render prompts that name nobody: this
        # is the same assertion `tools/new_character.py verify` makes, run on
        # a character who does not exist.
        said = _leaks(app.config, rendered)
        if said:
            return False, "built, and her prompt names: " + ", ".join(said[:6])
        # what smoke asks of a built App: no declared wire left None while
        # the App holds the thing
        un = []
        try:
            un = app.unwired()
        except Exception as e:
            un = [f"unwired() itself failed: {type(e).__name__}"]
        if un:
            return False, "built, but unwired: " + ", ".join(str(u) for u in un[:4])
        # ...and what her rooms hand a writer: the pocket, the moves ledger,
        # and the moves on the ask to somebody who writes her own turns
        bad = _room_checks(app, in_world, owner)
        if bad:
            return False, "built, but " + bad
        return True, "built (%s)" % app.program.__name__ if getattr(app, "program", None) else "built"
    except SystemExit as e:
        return False, f"SystemExit: {str(e)[:110]}"
    except Exception as e:
        tb = traceback.extract_tb(e.__traceback__)
        where = ""
        for fr in reversed(tb):
            p = fr.filename.replace("\\", "/")
            if "/tools/" not in p and "/site-packages/" not in p and "harness" not in p:
                where = f" at {os.path.relpath(p, ROOT) if p.startswith(ROOT.replace(chr(92), '/')) else p}:{fr.lineno}"
                break
        return False, f"{type(e).__name__}: {str(e)[:90]}{where}"
    finally:
        new_character.set_root("characters")
        # the singleton lock holds the save open; leave the directory to the
        # temp cleaner unless asked to keep it
        if keep:
            print("   kept", d)


_THEIRS = None


def _leaks(cfg, text):
    """Every registered character's name or place that this synthetic
    character's prompt says. Built once: it is the same set for every row."""
    global _THEIRS
    if _THEIRS is None:
        from tools import new_character
        _THEIRS = new_character._others_material(cfg, "")
    from tools import character_leaks
    said = set()
    for line in text.split("\n"):
        line = re.sub(r"\S+[\\/]\S+|https?://\S+", " ", line)
        said |= set(character_leaks.JA.findall(line)) | set(character_leaks.EN.findall(line))
    return sorted(n for n in _THEIRS if n in said)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--strict", action="store_true", help="exit 1 if any combination fails to build")
    ap.add_argument("--only", help="one combination, as the label column prints it")
    ap.add_argument("--keep", action="store_true", help="say where each scratch directory is")
    args = ap.parse_args(argv)
    _stub_logger()
    from tools import harness
    harness.refuse_network()
    harness.refuse_model_before_build()
    # the set of names that belong to a character who actually runs, built
    # once and before any scratch character is: building it loads the four
    # real configs, and doing that in the middle of a row made the row's
    # answer depend on which row ran first
    global _THEIRS
    from config import Config as _C
    from tools import new_character as _nc
    _THEIRS = _nc._others_material(_C(path="config.json"), "")
    print("  %d name(s) and place(s) belong to a character who runs; none of them may appear "
          "in a character composed from a bundle that names nobody" % len(_THEIRS))
    rows = []
    for embodied, in_world, sees, account, owner, with_him in itertools.product(
            (True, False), (True, False), SEES, (True, False), (True, False), ("chat", "none")):
        if not in_world and not owner:
            continue      # outside a world there is no world to own or read
        # a character with no contact with him is only ever somebody's
        # circle: in a world, with no sight of him and no account. The other
        # combinations are not kinds anybody has asked for, and each costs a
        # build in smoke.
        if with_him == "none" and (not in_world or sees != "none" or account):
            continue
        label = _label(embodied, in_world, sees, account, owner, with_him)
        if args.only and label != args.only:
            continue
        ok, note = build_one(embodied, in_world, sees, account, keep=args.keep, owner=owner,
                             with_him=with_him)
        rows.append((label, ok, note))
        print(f"  {'ok  ' if ok else 'FAIL'} {label:44s} {note}")
    bad = [r for r in rows if not r[1]]
    print(f"{len(rows) - len(bad)} of {len(rows)} kinds of character build; {len(bad)} do not")
    if bad:
        kinds = sorted({r[0] for r in bad})
        print("  failing: " + "; ".join(kinds))
    return 1 if (bad and args.strict) else 0


if __name__ == "__main__":
    sys.exit(main())
