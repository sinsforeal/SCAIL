"""A character whose config names none of a person's files still builds.

A blank path is not a broken config: it is a state the project produces on
purpose. `Config.WORLD_KEYS` empties every world path for a character with no
world, `Config.ACCOUNT_KEYS` empties the account's, and a character sheet that
answers "no body" or "no account" is meant to leave the modules behind those
paths with nothing to read rather than with somebody else's life. So every
module that reads a configured path has to treat an empty one the way
`world/calendar.py` does -- no data at all, in the constructor, so that
anything added to the class later inherits the silence -- and not the way an
unguarded `open()` does, which is to die at boot on `''`.

This builds the whole App with every person-shaped path in a config blanked at
once. The classification is the project's own: the path-shaped values
`tools/isolation.py:paths` finds, minus the ones under its MACHINE and NEUTRAL
prefixes, which are the machine's and the mechanism's rather than anybody's.
Nothing is read from or written to the config it starts from: the blanked copy
goes to a temporary file, because `Config.__init__` writes its merged result
back to its own path, and the save is a fresh temporary file.

The other half of the same rule is checked here too, on her own record
(`sim/lore.py`): a path that NAMES a file which is not on disk is a wrong path
rather than an absent one, and it still stops the boot.

    python tools/blank_paths.py                          # both configs
    python tools/blank_paths.py --config config_yukarin.json
    python tools/blank_paths.py --keep                   # leave the scratch config to read
"""

import argparse
import glob
import io
import json
import os
import sys
import tempfile
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

from tools import isolation  # noqa: E402


def person_paths(raw):
    """Every path-shaped value in a config that names a person.

    `isolation.paths` finds the path-shaped values; its MACHINE and NEUTRAL
    prefixes name the ones that belong to his machine and to the mechanism
    prompts, and those are shared on purpose and stay."""
    out = {}
    for key, value in isolation.paths(raw).items():
        if key.startswith(isolation.MACHINE) or key.startswith(isolation.NEUTRAL):
            continue
        out[key] = value
    return out


def _put(d, dotted, value):
    cur = d
    parts = dotted.split(".")
    for p in parts[:-1]:
        if not isinstance(cur.get(p), dict):
            return False
        cur = cur[p]
    if parts[-1] not in cur:
        return False
    cur[parts[-1]] = value
    return True


def switch_off_what_reads(raw, blanked):
    """Whatever the library refuses to run without a file it has just been
    denied.

    A character with no map, no places, no school year and no household is not
    in a world, and one with no roster and no sheets has no cast:
    `Config.PERSON_FILES` says, per key, which section or which property of her
    existence has to be true for the file to be needed, and the boot refuses
    the pair. Answering the same question here is what makes this a character
    who has none of those files rather than a character with a hole in her, and
    it is the difference the refusal was added to draw."""
    from config import Config
    off = []
    for key in blanked:
        sect, needs = Config.PERSON_FILES.get(key, (None, None))
        if sect and _put(raw, sect + ".enabled", False):
            off.append(sect)
        elif needs and _put(raw, "character.existence." + needs, False):
            off.append("not " + needs)
    return sorted(set(off))


def write_blanked(cfgpath, out_dir):
    """The config with every person-shaped path emptied, and its own save."""
    with io.open(cfgpath, encoding="utf-8") as f:
        raw = json.load(f)
    blanked = sorted(person_paths(raw))
    for key in blanked:
        _put(raw, key, "")
    for key in isolation.PERSON_KEYS:
        _put(raw, key, "")
    switch_off_what_reads(raw, blanked + list(isolation.PERSON_KEYS))
    db = os.path.join(out_dir, os.path.basename(cfgpath) + ".db").replace("\\", "/")
    _put(raw, "logging.db_path", db)
    path = os.path.join(out_dir, "blank_" + os.path.basename(cfgpath))
    with io.open(path, "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2, ensure_ascii=False)
    return path, db, blanked


def build(cfgpath, dbpath):
    """The App, the way the loop builds it, on a save this call creates."""
    import scail
    argv = sys.argv
    sys.argv = ["scail.py", "--config", cfgpath, "--console", "--no-sensors", "--db", dbpath]
    try:
        args = scail.parse_args()
    finally:
        sys.argv = argv
    return scail.App(args)


def _silence(quiet=True):
    """A build here writes a run's worth of boot lines and nobody reads them."""
    import logger
    if quiet:
        logger.setup = lambda out: None
        logger.finish = lambda: None
        logger.log = lambda m, to_console=True: None
        logger.log_llm = lambda *a, **k: None
        logger.write_artifact = lambda *a, **k: None


def check(cfgpath, out_dir, quiet=True):
    """Build one character with nothing of hers on disk. Returns an error, or
    an empty string when she built."""
    path, db, blanked = write_blanked(cfgpath, out_dir)
    print("  %s: %d person-shaped path(s) blanked" % (os.path.basename(cfgpath), len(blanked)))
    if os.path.exists(db):
        os.remove(db)
    _silence(quiet)
    real, sys.stdout = sys.stdout, io.StringIO()
    try:
        app = build(path, db)
        # Constructing is most of it, but the two halves of her prompt are
        # what a character exists to produce, and both read the files this
        # blanked: her cast, her beliefs, her record, her style guide.
        app.persona.system_for("him")
        app.persona.carried_for()
    except Exception as e:
        sys.stdout = real
        traceback.print_exc(limit=6)
        return "%s: %s" % (type(e).__name__, e)
    finally:
        sys.stdout = real
    built = sorted(k for k, v in vars(app).items() if v is not None and not k.startswith("_"))
    print("    built, %d module(s) on the App" % len(built))
    try:
        app.store.conn.close()
    except Exception:
        pass
    return ""


def wrong_record(cfgpath, out_dir, quiet=True):
    """The other half of the rule: a path that NAMES a record which is not
    on disk still stops the boot.

    A blank path is a character who has no record of her own, and she builds.
    A path pointing at a file that is not there is a wrong path, and a
    character running without the past her own config says she has is running
    as somebody else. Both halves are checked here because they are one
    decision, and the loud half is the one that has no other way of being
    noticed. Returns an error, or an empty string when the boot refused."""
    path, db, _blanked = write_blanked(cfgpath, out_dir)
    with io.open(path, encoding="utf-8") as f:
        raw = json.load(f)
    raw.setdefault("lore", {})
    raw["lore"]["enabled"] = True
    raw["lore"]["file"] = os.path.join(out_dir, "no_such_record.json").replace("\\", "/")
    with io.open(path, "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2, ensure_ascii=False)
    if os.path.exists(db):
        os.remove(db)
    _silence(quiet)
    app = None
    real, sys.stdout = sys.stdout, io.StringIO()
    try:
        app = build(path, db)
    except SystemExit:
        return ""
    except Exception as e:
        return "the boot stopped, but on %s: %s" % (type(e).__name__, e)
    finally:
        sys.stdout = real
        try:
            app.store.conn.close()
        except Exception:
            pass
    return "a record named in the config and not on disk did not stop the boot"


def one_blank_while_it_runs(cfgpath, out_dir, quiet=True):
    """The third case: ONE person-shaped file emptied while the thing that
    reads it is still running.

    A blank path with the subsystem off is a character who has not got that
    thing. A blank path with the subsystem ON is a hole, and until the
    defaults were emptied it could not happen, because the merge quietly filled
    it with the first character's file. Returns an error, or an empty string
    when the boot refused with the key named."""
    from config import Config
    with io.open(cfgpath, encoding="utf-8") as f:
        raw = json.load(f)
    # which rows apply is a question about the LOADED config, not the file: her
    # sheet and what kind of thing she is switch sections off at load, and a
    # section the file leaves on may be off by the time anything reads it.
    applied = os.path.join(out_dir, "applied_" + os.path.basename(cfgpath))
    with io.open(applied, "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2, ensure_ascii=False)
    real, sys.stdout = sys.stdout, io.StringIO()
    try:
        loaded = Config(applied).raw
    finally:
        sys.stdout = real
    rows = Config._person_file_rows(loaded, (loaded.get("character") or {}).get("existence") or {})
    key = next((k for k, v, _why in rows if v.strip()), "")
    if not key:
        # she has none of the subsystems that need a file of their own, so
        # there is no hole to make
        return "-"
    _put(raw, key, "")
    db = os.path.join(out_dir, os.path.basename(cfgpath) + ".hole.db").replace("\\", "/")
    _put(raw, "logging.db_path", db)
    path = os.path.join(out_dir, "hole_" + os.path.basename(cfgpath))
    with io.open(path, "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2, ensure_ascii=False)
    if os.path.exists(db):
        os.remove(db)
    _silence(quiet)
    app = None
    real, sys.stdout = sys.stdout, io.StringIO()
    try:
        app = build(path, db)
    except SystemExit as e:
        if key in str(e):
            return ""
        return "the boot stopped and did not name %s: %s" % (key, str(e)[:160])
    except Exception as e:
        return "the boot stopped, but on %s: %s" % (type(e).__name__, e)
    finally:
        sys.stdout = real
        try:
            app.store.conn.close()
        except Exception:
            pass
    return "%s was emptied while what reads it is on, and she started anyway" % key


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", default="", help="one config; every one of them by default")
    ap.add_argument("--keep", action="store_true", help="leave the scratch config and save behind")
    args = ap.parse_args()

    configs = [args.config] if args.config else sorted(
        set(["config.json"] + glob.glob("config_*.json")))
    out_dir = os.path.join(tempfile.gettempdir(), "scail_blank_paths")
    os.makedirs(out_dir, exist_ok=True)

    print("\n  a character whose config names none of a person's files")
    bad, loud, holes = [], [], []
    for cfgpath in configs:
        if not os.path.exists(cfgpath):
            continue
        err = check(cfgpath, out_dir)
        if err:
            bad.append((cfgpath, err))
            print("    DID NOT BUILD  %s" % err)
        err = wrong_record(cfgpath, out_dir)
        if err:
            loud.append((cfgpath, err))
            print("    RECORD NOT THERE AND SHE STARTED  %s" % err)
        else:
            print("    and a record named in the config and missing stops the boot")
        err = one_blank_while_it_runs(cfgpath, out_dir)
        if err == "-":
            print("    (no subsystem of hers needs a file of its own, so there is no hole "
                  "to make)")
        elif err:
            holes.append((cfgpath, err))
            print("    HOLE UNDER A RUNNING SUBSYSTEM  %s" % err)
        else:
            print("    and one file emptied while what reads it is on stops the boot, by name")
    if not args.keep:
        for p in glob.glob(os.path.join(out_dir, "*")):
            try:
                os.remove(p)
            except OSError:
                pass
    print()
    if bad:
        print("  %d character(s) did not build with a blank path: %s"
              % (len(bad), ", ".join(c for c, _ in bad)))
        print("  A blank path is the empty case, not a crash. Fix it in the module's "
              "constructor, the way world/calendar.py does.")
        return 1
    if loud:
        print("  %d character(s) started with a record their config names and disk has not: %s"
              % (len(loud), ", ".join(c for c, _ in loud)))
        print("  A named file that is not there is a wrong path, not an absent one, and a "
              "character without the past her config gives her is running as somebody else.")
        return 1
    if holes:
        print("  %d character(s) started with one of her own files emptied under a subsystem "
              "that is on: %s" % (len(holes), ", ".join(c for c, _ in holes)))
        print("  `Config.PERSON_FILES` says which subsystem needs which file; an empty one "
              "under a running subsystem used to be filled from the first character's.")
        return 1
    print("  every character built with every person-shaped path blank, and refused to start "
          "with one of them emptied under a subsystem that is on")
    return 0


if __name__ == "__main__":
    sys.exit(main())
