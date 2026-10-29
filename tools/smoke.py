"""Boot everything against a copy of the save and report, without touching the
live bot.

Written after a restart killed the running process on boot: `Goals.__init__`
had gained a parameter at one call site and not at its definition, and nothing
found out until the live process died and the log stopped after the telemetry
line. Every subsystem is constructed in App.__init__, so simply constructing an
App catches that whole class of failure in a few seconds.

    python tools/smoke.py            # construct everything, print the reports
    python tools/smoke.py --tick     # and run one director tick (costs calls)

Console mode and a scratch copy of the database: it never reaches Telegram, X,
the sensors or the live save. It writes its log under logs/dryrun/ like any
other dry run, so the live run directories are left alone.

SCAILV4 runs one character (Momoka) on one config, so this reads
`config_momoka.json` and `data/momoka.db` rather than the SCAILV3 register.
"""
import argparse
import ast
import glob
import io
import os
import sys
import tempfile
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

# SCAILV4 is Momoka alone on one config. The SCAILV3 gate hardcoded
# `config.json` (Tomoe) and walked `config_*.json`; in this fork there is one
# live config and one save, so both are named once here.
MAIN_CONFIG = "config_momoka.json"
MAIN_DB = "data/momoka.db"


def _static_faults(root="."):
    """Names referenced in a function and never bound in it, and `+` at the end
    of a line followed by `+` at the start of the next. Both are what a patch
    that lands half an edit leaves behind."""
    import symtable
    builtins_ = set(dir(__import__("builtins")))
    skip = {"logs", "data", "secerts", "__pycache__", "retired", "tmp", "var"}  # tmp/: agent worktrees, incl. other repos
    files = []
    for base, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in skip and not d.startswith(".")]
        files += [os.path.join(base, f) for f in names if f.endswith(".py")]

    def walk(table, path, known, out):
        if table.get_type() == "function":
            for sym in table.get_symbols():
                if not sym.is_referenced():
                    continue
                # NOT is_global(): a name a function never binds resolves as
                # a global lookup, so excluding those excluded the whole fault.
                # `known` is the real test -- is there a module-level binding,
                # an import or a builtin for it to find at runtime.
                if (sym.is_assigned() or sym.is_parameter() or sym.is_free()
                        or sym.is_imported() or sym.is_declared_global()):
                    continue
                name = sym.get_name()
                if name in known or name in builtins_:
                    continue
                out.append((path, table.get_name(), table.get_lineno(), name))
        for child in table.get_children():
            walk(child, path, known, out)

    names, plus = [], []
    for path in files:
        try:
            src = io.open(path, encoding="utf-8").read()
            tree = ast.parse(src)
            st = symtable.symtable(src, path, "exec")
        except (SyntaxError, UnicodeDecodeError):
            continue
        known = {s.get_name() for s in st.get_symbols()}
        # symtable does not list the module dunders
        known |= {"__file__", "__name__", "__doc__", "__package__", "__spec__", "__loader__"}
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for a in node.names:
                    known.add((a.asname or a.name).split(".")[0])
        walk(st, path, known, names)
        lines = src.split("\n")
        for i in range(len(lines) - 1):
            if lines[i].rstrip().endswith("+") and lines[i + 1].strip().startswith("+"):
                plus.append((path, i + 1, lines[i].strip()))
    return names, plus


from tools.dbcopy import copy_db as _copy_save  # noqa: E402 -- SQLite's backup, never a file copy


def _build(cfgpath, dbpath):
    """The App for one character, on a copy of her save, the way the loop
    builds it: scail's own parser, so this never drifts from the real flags."""
    import scail
    argv = sys.argv
    sys.argv = ["scail.py", "--config", cfgpath, "--console", "--no-sensors", "--db", dbpath]
    try:
        real_args = scail.parse_args()
    finally:
        sys.argv = argv
    return scail.App(real_args)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tick", action="store_true", help="also run one director tick (spends model calls)")
    ap.add_argument("--db", default=MAIN_DB, help="save file to copy from")
    args = ap.parse_args()

    tmp = os.path.join(tempfile.gettempdir(), "scail_smoke.db")
    _copy_save(args.db, tmp)
    print(f"[smoke] copied {args.db} -> {tmp} (sqlite backup, a coherent image of a live save)")

    # Stub the whole logger, not just `log`. Stubbing only `log` still lets
    # App.__init__ call `logger.setup()`, which creates a real timestamped run
    # directory under logs/ complete with an ACTIVE pid file -- this script left
    # one behind on its first day, which is the same mess a throwaway App made
    # in the morning.
    import logger
    logger.setup = lambda out_dir: None
    logger.finish = lambda: None
    logger.log = lambda m, to_console=True: None
    logger.log_llm = lambda *a, **k: None
    logger.write_artifact = lambda *a, **k: None

    failures = []

    def check(label, fn):
        try:
            out = fn()
            print(f"  ok   {label}")
            return out
        except Exception as e:
            failures.append(label)
            print(f"  FAIL {label}: {type(e).__name__}: {e}")
            traceback.print_exc(limit=4)
            return None

    def _wiring(app, label):
        """A declared wire still None where the App holds the thing to attach
        is built-and-never-wired, the fault sim/wiring.py exists to catch."""
        bad = app.unwired()
        n = sum(len(getattr(type(o), "WIRES", ())) for o in vars(app).values())
        if bad:
            failures.append(f"wiring ({label})")
            print(f"  FAIL built and not attached ({label}): {', '.join(bad)}")
        else:
            print(f"  ok   every declared wire attached or nothing there to attach ({label}): {n} declared")

    print("[smoke] config")
    from config import Config
    cfg = check("Config loads and the gauge spec validates", lambda: Config(MAIN_CONFIG))
    if cfg is None:
        return 1

    print(f"[smoke] {MAIN_CONFIG} vs DEFAULTS")
    import json as _json
    from config import DEFAULTS as _D
    with io.open(MAIN_CONFIG, encoding="utf-8") as f:
        _loaded = _json.load(f)
    _stale = Config._check_drift(_loaded, _D)
    if _stale:
        print(f"  note {len(_stale)} dead key(s) in {MAIN_CONFIG}: {', '.join(_stale[:8])}")
    else:
        print("  ok   no dead keys")

    # A key written twice in the DEFAULTS literal: Python keeps the last one
    # silently, so the file reads as if both are live and editing the first
    # does nothing. `situation_block` sat there duplicated for a day. dupscan
    # looks for repeated blocks of code and does not see this, so it is read
    # off the source's own syntax tree.
    print("[smoke] DEFAULTS has no key written twice")
    import ast as _ast, collections as _c
    _dups = []
    for _n in _ast.walk(_ast.parse(io.open("config.py", encoding="utf-8").read())):
        if isinstance(_n, _ast.Assign) and any(getattr(t, "id", "") == "DEFAULTS" for t in _n.targets):
            def _scan(d, path=""):
                ks = [k.value for k in d.keys if isinstance(k, _ast.Constant)]
                for k, c in _c.Counter(ks).items():
                    if c > 1:
                        _dups.append(f"{path}{k} (x{c})")
                for k, v in zip(d.keys, d.values):
                    if isinstance(v, _ast.Dict) and isinstance(k, _ast.Constant):
                        _scan(v, f"{path}{k.value}.")
            _scan(_n.value)
    if _dups:
        failures.append("duplicate DEFAULTS keys")
        print(f"  FAIL {len(_dups)} duplicated key(s) in config.py DEFAULTS: {', '.join(_dups[:6])}")
    else:
        print("  ok   no duplicated keys")

    print("[smoke] every prompt file a role names")
    # A role whose `prompt` is empty has no file of its own BY DESIGN, and says
    # so by carrying the key empty rather than by leaving it out: `pick` builds
    # `persona.system_for("him")` and offers tools, and the tool definitions are
    # the rest of its instruction. Named in the line below, so a role that
    # merely lost its path is visible rather than silently exempt.
    _own = {r: m["prompt"] for r, m in cfg.raw["models"].items() if m["prompt"]}
    _none = sorted(r for r, m in cfg.raw["models"].items() if not m["prompt"])
    # A role whose prompt lives under a directory this fork does not carry
    # (`tomoe/prompts/...`) belongs to the SCAILV3 library and is off here:
    # Momoka's bundle never turns its section on, so the file is neither
    # present nor wanted. A role whose own directory exists is still held to
    # its file, so a path that merely lost its file is visible.
    def _owned_here(p):
        d = os.path.dirname(p)
        return (not d) or os.path.isdir(d)
    _foreign = sorted(r for r, p in _own.items() if not _owned_here(p))
    missing = [r for r, p in _own.items() if _owned_here(p) and not os.path.exists(p)]
    if missing:
        failures.append("prompt files")
        print(f"  FAIL missing prompt file(s) for role(s): {missing}")
    else:
        print(f"  ok   {len(_own) - len(_foreign)} role(s) of this fork, every prompt file present"
              + (f"; {len(_foreign)} role(s) of the SCAILV3 library, off here: "
                 f"{', '.join(_foreign)}" if _foreign else ""))

    print("[smoke] names that are used but never set, and broken + chains")
    # Two faults shipped on 2026-08-21 and neither showed until she woke up,
    # because both sit inside a function that only runs on a live path:
    # `spiral_txt` was put in the director's prompt without its assignment
    # (every tick raised NameError), and a line inserted into intent.py's
    # concatenation left a stray trailing `+`, so the next line was a unary
    # plus on a string. Import does not catch either, ast.parse does not, and
    # constructing the app does not.
    bad_names, bad_plus = _static_faults()
    if bad_names or bad_plus:
        failures.append("static")
        for path, fn, line, name in bad_names:
            print(f"  FAIL {path}:{line} in {fn}(): '{name}' is used and never set")
        for path, line, text in bad_plus:
            print(f"  FAIL {path}:{line} a line ends with + and the next starts with +: {text[:60]}")
    else:
        print("  ok   no unbound names, no broken + chains")

    # A program's subprocess says whose it is. A tool started from a
    # character's loop with no config in its arguments loads `config.json`,
    # which is the FIRST character: the national news feed ran in the fourth
    # character's process at 19:35 on 2026-09-06, was judged in the first
    # character's terms, and was written to the first character's files while
    # the file her own config names stayed empty. Two call sites, both in one
    # program, and the fault is invisible until two characters run one
    # program.
    print("[smoke] a tool a program starts carries the character's config")
    import re as _re
    from tools.registry import programs as _registry_programs
    _progs = sorted(_registry_programs())
    _bad = []
    for _prog in _progs:
        for _fn in sorted(glob.glob(os.path.join(_prog, "*.py"))):
            with open(_fn, encoding="utf-8") as _f:
                _src = _f.read()
            for _m in _re.finditer(r"subprocess\.(?:run|Popen)\(\s*\[(.*?)\]", _src, _re.S):
                _call = _m.group(1)
                if "tools/" not in _call and "tools\\" not in _call:
                    continue
                if "--config" in _call:
                    continue
                _bad.append((_fn, _src[: _m.start()].count("\n") + 1,
                             " ".join(_call.split())[:70]))
    if _bad:
        failures.append("subprocess config")
        for _fn, _ln, _txt in _bad:
            print(f"  FAIL {_fn}:{_ln} a tool is started with no --config: {_txt}")
    else:
        print(f"  ok   every tool started from {len(_progs)} program(s) is told whose config to load")

    # SCAILV3 checked the mechanism prompts here (`tools/neutral_gate.py`):
    # the `{{holes}}` where the person used to be, and that her fills rendered
    # them back byte for byte. Those prompts and their baseline snapshot belong
    # to the v3 library and are not in this fork, so the check does not run;
    # Momoka's own fills are still held to `tools/fills_check.py` below.
    import subprocess

    # a second character reading the first one's household, place graph or
    # school calendar. Every switchable subsystem is assigned to an existence
    # property in `Config.REQUIRES` and every world file to `Config.WORLD_KEYS`;
    # this proves the result -- that nothing shared between two characters is
    # shaped like a person.
    # every character against every OTHER one, not each against the first. A
    # pair that does not include the first character was never checked, and a
    # bundle is a per-character prefix: the question "is anything of hers
    # outside her own directory, and is anything under somebody else's" only
    # answers itself when both sides are named.
    _all_cfgs = sorted(glob.glob("config_*.json"))
    if len(_all_cfgs) > 1:
        print("[smoke] one character reading another's life, every pair")
        for cfgpath in _all_cfgs:
            worst = ""
            for against in _all_cfgs:
                if against == cfgpath:
                    continue
                r = subprocess.run([sys.executable, os.path.join("tools", "isolation.py"),
                                    "--config", cfgpath, "--against", against],
                                   capture_output=True, text=True, encoding="utf-8", errors="replace")
                body = [l.strip() for l in (r.stdout or "").splitlines() if l.strip()]
                tail = next((l for l in reversed(body)
                             if l.startswith(("Isolated", "NOT ISOLATED"))), "(no output)")
                if r.returncode:
                    failures.append("isolation: %s vs %s" % (cfgpath, against))
                    print("  FAIL %-22s vs %-22s %s" % (cfgpath, against, tail))
                    for l in body:
                        if l.startswith(("world.", "character.", "logging.", "UNDER ")):
                            print("       " + l[:110])
                else:
                    worst = worst or tail
                    for l in body:
                        if "outside it" in l and not l.startswith("0 "):
                            worst = l
            if worst:
                print("  ok   %-24s %s" % (cfgpath, worst[:96]))

    # the operator's register is a projection of the bundles: every field of a
    # row is also in `characters/<key>/bundle.json`, and two copies of one fact
    # drift
    print("[smoke] every registered character has a bundle, and it agrees with her row")
    r = subprocess.run([sys.executable, os.path.join("tools", "registry.py")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    lines = [l for l in (r.stdout or "").splitlines() if l.strip()]
    if r.returncode:
        failures.append("register vs bundles")
        for l in lines:
            if l.strip().startswith(("MISSING", "NO BUNDLE", "NO MANIFEST")) or ": the register says" in l:
                print("  FAIL " + l.strip()[:120])
    else:
        print("  ok   " + (lines[-1].strip() if lines else "checked"))

    # and composing each of them from her bundle gives the config she runs on.
    # A difference here is either a hand edit to a config that the bundle does
    # not know about, or a bundle that has moved on without being composed;
    # either way one of the two is stale and the file is the one that runs.
    print("[smoke] every character's config is what her bundle composes")
    r = subprocess.run([sys.executable, os.path.join("tools", "new_character.py"),
                        "compose", "--all", "--diff"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    lines = [l for l in (r.stdout or "").splitlines() if l.strip()]
    if r.returncode:
        failures.append("compose")
        print("  FAIL " + (lines[-1].strip() if lines else "(no output)"))
        for l in lines:
            if "live " in l and "composed " in l:
                print("   " + l.strip()[:120])
    else:
        print("  ok   " + (lines[-1].strip() if lines else "checked"))

    # and building her from it names nobody else: a hole that survived, a path
    # outside her bundle, another character's material in her prompts or her
    # meters, a roster that does not resolve her to herself
    print("[smoke] every character's bundle is hers alone, built and rendered")
    r = subprocess.run([sys.executable, os.path.join("tools", "new_character.py"),
                        "verify", "--all"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    lines = [l for l in (r.stdout or "").splitlines() if l.strip()]
    if r.returncode:
        failures.append("bundle verify")
        print("  FAIL " + (lines[-1].strip() if lines else "(no output)"))
        for l in lines:
            if l.strip().startswith("FAIL"):
                print("   " + l.strip()[:130])
    else:
        print("  ok   " + (lines[-1].strip() if lines else "checked"))

    # And the same rule one level up, in the library's own defaults. The merge
    # fills a key a character's config does not carry from `config.py:DEFAULTS`
    # and writes it into her file, where it then looks authored: a default that
    # is one person's household, roster, map or save is inherited by the next
    # character in silence, which is what the fourth character's first day was.
    print("[smoke] no default in the library is one person's file")
    r = subprocess.run([sys.executable, os.path.join("tools", "defaults_person_test.py")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    lines = [l for l in (r.stdout or "").splitlines() if l.strip()]
    if r.returncode:
        print("  FAIL " + (lines[-1].strip() if lines else "(no output)"))
        for l in lines:
            if l.strip().startswith(("FAIL", "  FAIL", "       ")):
                print("   " + l.strip()[:120])
        failures.append("person-shaped defaults")
    else:
        print("  ok   " + (lines[-1].strip() if lines else "checked"))

    # The same table seen from the other side: a blanked path is a state the
    # project PRODUCES, so every module that reads one has to be the empty
    # case rather than dying on ''. Two did -- the relationship meters' cast
    # file and the beliefs seed -- and they were found by a harness building a
    # third character, not by a check.
    print("[smoke] a character whose config names none of a person's files still builds")
    r = subprocess.run([sys.executable, os.path.join("tools", "blank_paths.py"),
                        "--config", MAIN_CONFIG],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    lines = [l for l in (r.stdout or "").splitlines() if l.strip()]
    if r.returncode:
        print("  FAIL " + (lines[-1].strip() if lines else "(no output)"))
        for l in lines[:12]:
            print("   " + l.strip()[:120])
        failures.append("blank paths")
    else:
        print("  ok   " + (lines[-1].strip() if lines else "checked"))

    # The closed vocabulary every character's behaviour is coded against
    # (data/codebook/, docs/codebook.md). Every `code` field written anywhere
    # else points into it, so a renamed id, a neighbour that has gone, or a
    # version that has moved silently invalidates work that has already been
    # done; and a person's name in an entry would make the shared vocabulary
    # one character's.
    print("[smoke] the mechanism codebook loads, its neighbours resolve, and nobody is named")
    r = subprocess.run([sys.executable, os.path.join("tools", "codebook_check.py")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    lines = [l for l in (r.stdout or "").splitlines() if l.strip()]
    if r.returncode:
        print("  FAIL " + (lines[-1].strip() if lines else "(no output)"))
        for l in lines:
            if l.strip().startswith("FAIL") or l.startswith("   "):
                print("   " + l.strip()[:120])
        failures.append("codebook")
    else:
        print("  ok   " + (lines[0].strip() if lines else "checked"))

    # SCAILV3 drove a cast member's mechanisms here
    # (`tools/cast_mechanisms_test.py`). Momoka's bundle drops the cast
    # section (`config.cast` is off), so there is no cast to load.

    # SCAILV3 checked the seam for a cast member running her own process
    # (`tools/agent_seam_test.py`). Momoka has no cast, so the field it reads
    # is nowhere on her rows.

    # A structural check on one process, on a scratch save, with the model
    # stubbed, is what passed before the fourth character's first day. What it
    # could not see was a day: the owner's planner deleting every beat it
    # planned for her, every relayed turn filed under the owner's name, a
    # chosen silence read as a timeout, and four things about a man she has no
    # chat with written into her save. This lives one day of her clock with
    # both processes up, on copies, and asserts the seam's runtime contract.
    print("[smoke] a day of a character who runs herself, beside the one who keeps her world")
    import json as _js
    from tools import registry as _registry
    _readers = []
    for _row in _registry.characters():
        _b = os.path.join("characters", _row["key"], "bundle.json")
        if not os.path.exists(_b):
            continue
        _w = (_js.load(io.open(_b, encoding="utf-8")).get("world") or {})
        if _w.get("id") and not _w.get("owner"):
            _readers.append(_row["key"])
    if not _readers:
        print("  ok   no registered character reads somebody else's world")
    for _key in _readers:
        r = subprocess.run([sys.executable, os.path.join("tools", "agent_rehearsal.py"), _key],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        lines = [l for l in (r.stdout or "").splitlines() if l.strip() and not l.startswith("[config]")]
        if r.returncode:
            print("  FAIL " + _key + ": " + (lines[-1].strip() if lines else "(no output)"))
            for l in lines:
                if "FAIL" in l:
                    print("   " + l.strip()[:130])
            failures.append("agent rehearsal (%s)" % _key)
        else:
            print("  ok   " + _key + ": " + (lines[-1].strip()[:140] if lines else "checked"))

    # SCAILV3 checked a character reading a world she does not keep
    # (`tools/world_reader_test.py`). Momoka has no world (`world.id` is
    # empty), so there is nothing for her to read and none for her to write.

    # SCAILV3 drove the world file itself here (`tools/world_test.py`).
    # Momoka has no world, so the plan, the day's one truth and a turn write
    # nothing shared.

    # The personality type each person was written FROM is the author's note
    # to himself. The whole point of the exercise is to describe the behaviour
    # and never name the type, so that the measurement asks whether the
    # behaviour appears rather than whether a model can act out four letters
    # it was handed. One tool reads that file (tools/cast_type_test.py); a
    # prompt builder, a role or a prompt reading it would be telling the model
    # the answer.
    print("[smoke] nothing that assembles a call reads the personality types")
    _leaks = []
    for _root in ("sim", "persona", "resident", "prompts", "prompts_momoka"):
        if not os.path.isdir(_root):
            continue
        for _d, _subs, _fs in os.walk(_root):
            for _f in _fs:
                if not _f.endswith((".py", ".txt", ".md", ".json")):
                    continue
                _p = os.path.join(_d, _f)
                try:
                    _text = io.open(_p, encoding="utf-8", errors="replace").read()
                except OSError:
                    continue
                if "cast_types" in _text or "types_file" in _text:
                    _leaks.append(_p)
    if "cast_types" in io.open("scail.py", encoding="utf-8").read():
        _leaks.append("scail.py")
    if _leaks:
        failures.append("cast types read by a call")
        print("  FAIL the type file is meant for the author and one tool: " + ", ".join(_leaks[:6]))
    else:
        print("  ok   the type file is read by tools/cast_type_test.py and by nothing that builds a prompt")

    # the other direction of the same fault. `neutral_gate` proves no character
    # is written into the instructions; this reads what the last run actually
    # produced and names anybody in it who is not in that character's record.
    # It belongs here because here is the moment it is wanted: smoke runs
    # before every restart, so it reads the run that is about to be replaced.
    # Reported, never failed -- a fetched ward event is a name in no sheet, and
    # a check that cries wolf is a check nobody runs.
    print("[smoke] names in the last run that are not in the character's record")
    for cfgpath in [MAIN_CONFIG]:
        r = subprocess.run([sys.executable, os.path.join("tools", "character_leaks.py"),
                            "--config", cfgpath, "--top", "6"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        body = [l for l in (r.stdout or "").splitlines() if l.strip()]
        head = next((l.strip() for l in body if l.strip().startswith(("NAMES NOT", "no name"))), "")
        who = next((l.strip() for l in body if ", run " in l), cfgpath)
        print("  %-52s %s" % (who[:52], head or "(no run to read)"))

    # how she sees him -- an app on her phone, or his machine in front of her
    # -- is the program's to say, never the library's (sim/sight.py). Her
    # editor once binned a true remark about his uptime because the library
    # had told it she has an app.
    # and the shared code names nobody: her own name, her family's and her
    # friends' are hers, and a name in the mechanism is the first character
    # baked into it (her commute was the shared skeleton for a day)
    print("[smoke] nothing new in what the characters share names one of them or her places")
    r = subprocess.run([sys.executable, os.path.join("tools", "character_names.py")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    lines = [l for l in (r.stdout or "").splitlines() if l.strip()]
    if r.returncode:
        print("  FAIL " + (lines[0].strip() if lines else "(no output)"))
        for l in lines[1:][:12]:
            print("   " + l.strip()[:120])
        failures.append("character names")
    else:
        print("  ok   " + (lines[-1].strip() if lines else "checked"))

    # A role that judges her -- scores, sorts, predicts, checks, extracts -- is
    # a neutral party and gets no character sheet. The sheet is written TO her
    # and opens "You are <her name> ... you never mention prompts, models,
    # systems", and it sat last in a judge's system prompt: the urge picker
    # returned a finished message in her voice instead of the second-person
    # intention it was asked for on 13 of 13 answers over 2026-09-04 and 09-05,
    # and one of them was sent as her next bubble twelve seconds later.
    print("[smoke] every role that asks for her character sheet has been decided about")
    r = subprocess.run([sys.executable, os.path.join("tools", "role_stance.py")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    lines = [l for l in (r.stdout or "").splitlines() if l.strip()]
    if r.returncode:
        print("  FAIL " + (lines[0].strip() if lines else "(no output)"))
        for l in lines[1:][:12]:
            print("   " + l.strip()[:120])
        failures.append("role stance")
    else:
        print("  ok   " + (lines[0].strip() if lines else "checked"))

    # SCAILV3 ran `tools/judge_prompts.py` here, over `config.json` and
    # `config_yukarin.json`. Momoka has one config and `tools/role_stance.py`
    # above already checks that no judge role is handed her sheet.

    # SCAILV3 drove a share through the social account here
    # (`tools/share_pick_test.py`). Momoka has no account (`has_account` is
    # false, `social` and `share_pick` are off), so nothing is posted.

    # SCAILV3 drove every tool through the pick seam here
    # (`tools/pick_live_test.py`). That test reads the v3 register
    # (`characters.json`) and `config_rena.json` for its second case, neither
    # of which is in this fork; the seam itself is exercised by hand. The
    # command table below still holds the tools her sheet offers.

    print("[smoke] the shared code and prompts do not say how she sees him")
    r = subprocess.run([sys.executable, os.path.join("tools", "sight_words.py"), "--no-school"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    lines = [l for l in (r.stdout or "").splitlines() if l.strip()]
    if r.returncode:
        print("  FAIL " + (lines[-1].strip() if lines else "(no output)"))
        for l in lines[:-1][:12]:
            print("   " + l.strip()[:120])
        failures.append("sight words")
    else:
        print("  ok   " + (lines[-1].strip() if lines else "checked"))

    # A role with no character sheet writes the record and never what it
    # did to her. The role that read his notes over her shoulder was asked
    # for "how it landed on her" and the paragraph was stored as her own
    # memory of having felt it; nine more did the same in a smaller field.
    print("[smoke] no prompt of a role without her sheet asks for her interior")
    r = subprocess.run([sys.executable, os.path.join("tools", "interior_words.py")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    lines = [l for l in (r.stdout or "").splitlines() if l.strip()]
    if r.returncode:
        print("  FAIL " + (lines[-1].strip() if lines else "(no output)"))
        for l in [l for l in lines if not l.strip().startswith("skipped")][:12]:
            print("   " + l.strip()[:120])
        failures.append("interior words")
    else:
        print("  ok   " + (lines[-1].strip() if lines else "checked"))

    # What the shape of a window title may claim about the page in front of
    # him. A MyAnimeList page whose brackets are only an English alias was
    # filed as a person for months, and the resolution returned before her own
    # record, her roles or a search were asked. The table is real titles out
    # of his telemetry; the resolution itself (her record and her roles first,
    # one record, no second fetch) needs her save and is the same tool without
    # `--shape`.
    print("[smoke] what a window title may claim about the page in front of him")
    r = subprocess.run([sys.executable, os.path.join("tools", "work_resolve_test.py"), "--shape"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    lines = [l for l in (r.stdout or "").splitlines() if l.strip()]
    if r.returncode:
        print("  FAIL " + (lines[-1].strip() if lines else "(no output)"))
        for l in [l for l in lines if l.strip().startswith("FAIL")][:12]:
            print("   " + l.strip()[:120])
        failures.append("work titles")
    else:
        print("  ok   " + (lines[-1].strip() if lines else "checked"))

    # The reader of his text hooker's files, against his real files, read-only.
    # It needs Windows and his eroge directory, so it runs only for a character
    # who has the section switched on.
    if any((_json.load(io.open(p, encoding="utf-8")).get("eroge") or {}).get("enabled")
           for p in [MAIN_CONFIG]):
        print("[smoke] what he is reading in a visual novel, read out of the hooker's own files")
        r = subprocess.run([sys.executable, os.path.join("tools", "eroge_test.py"),
                            "--config", MAIN_CONFIG],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        lines = [l for l in (r.stdout or "").splitlines() if l.strip()]
        # the check's own verdict, named rather than taken by position: one
        # that dies before printing anything of its own used to have its
        # FAIL line quote whatever the config had said last
        said = [l for l in lines if l.strip().startswith("[eroge]")]
        if r.returncode:
            print("  FAIL " + (said[-1].strip() if said else "(no output of its own)"))
            for l in [l for l in lines if l.strip().startswith("FAIL")][:12]:
                print("   " + l.strip()[:120])
            failures.append("eroge reader")
        else:
            print("  ok   " + (said[-1].strip() if said else "checked"))

    # One fetch about the world, read by both characters. The claim protocol
    # is what stops two processes paying for the same episode in the same
    # minute, and it is checked here on a temp store with no App and no model
    # call; the whole run (`python tools/retrievals_test.py`) builds both
    # characters on copies and checks the migration too.
    # Three of the machine's own guarantees, each on temp files with no App,
    # no save and no model call: a file replaced under a reader is never half
    # a file; one watch of one episode leaves one row on this machine's clock;
    # a stream nobody got an answer from is still on the record and a burst of
    # calls waits once so the rest can read the first one's cached prefix.
    for tool, what in (
            ("atomic_test.py", "a file replaced under a reader is never half a file"),
            ("mal_history_test.py", "one row per watch of one episode, on this machine's clock"),
            ("provider_test.py", "an abandoned stream is on the record; a burst waits once"),
            ("vn_voice_test.py", "her voice comes from synthesis, an exact recording, or a pause-only near miss")):
        print(f"[smoke] {what}")
        r = subprocess.run([sys.executable, os.path.join("tools", tool)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        lines = [l for l in (r.stdout or "").splitlines() if l.strip()]
        if r.returncode:
            print("  FAIL " + (lines[-1].strip() if lines else (r.stderr or "")[-200:]))
            for l in [l for l in lines if l.strip().startswith("FAIL")][:12]:
                print("   " + l.strip()[:120])
            failures.append(tool.replace("_test.py", ""))
        else:
            print("  ok   " + (lines[-1].strip() if lines else "checked"))

    print("[smoke] one fetch about the world, claimed once and read by both")
    r = subprocess.run([sys.executable, os.path.join("tools", "retrievals_test.py"), "--store"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    lines = [l for l in (r.stdout or "").splitlines() if l.strip()]
    if r.returncode:
        print("  FAIL " + (lines[-1].strip() if lines else "(no output)"))
        for l in [l for l in lines if l.strip().startswith("FAIL")][:12]:
            print("   " + l.strip()[:120])
        failures.append("shared retrievals")
    else:
        print("  ok   " + (lines[-1].strip() if lines else "checked"))

    # Drawing one of her replies again keeps the prompt it was drawn from and
    # every answer to it; what is checked here is that the tables and their
    # readers hold, on a temp save with no character in it. The whole run
    # (`python tools/swipes_test.py`) builds the second character on a copy
    # and drives a reply through the real path with the model stubbed.
    print("[smoke] the prompt a reply was drawn from, and the other answers to it")
    r = subprocess.run([sys.executable, os.path.join("tools", "swipes_test.py"), "--store"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    lines = [l for l in (r.stdout or "").splitlines() if l.strip()]
    if r.returncode:
        print("  FAIL " + (lines[-1].strip() if lines else "(no output)"))
        for l in [l for l in lines if l.strip().startswith("FAIL")][:12]:
            print("   " + l.strip()[:120])
        failures.append("swipes")
    else:
        print("  ok   " + (lines[-1].strip() if lines else "checked"))

    # Her own record has to reach the rooms with her own people, not only her
    # chat with him. For eleven days it reached neither; from 2026-09-06 it
    # reaches both. Three cases on a fresh save, no model call and no network:
    # a friend names something in her record and the record's own words are in
    # her assembled prompt, the next turn where only her own reply names it
    # again carries nothing, and a room that named nothing of hers carries
    # nothing either.
    print("[smoke] her own record in the rooms with her own people")
    r = subprocess.run([sys.executable, os.path.join("tools", "lore_rooms_test.py")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    lines = [l for l in (r.stdout or "").splitlines() if l.strip()]
    if r.returncode:
        print("  FAIL " + (lines[-1].strip() if lines else "(no output)"))
        for l in [l for l in lines if "FAIL" in l][:12]:
            print("   " + l.strip()[:120])
        failures.append("her record in her own rooms")
    else:
        print("  ok   " + (lines[-1].strip() if lines else "checked"))

    # SCAILV3 drove a closing room here (`tools/room_record_test.py`). A room
    # is closed when she finishes with somebody of her own; Momoka has no
    # cast and no group room (the only person on her roster is him, and that
    # room is her chat with him), so the test has nobody to close a room with.

    # SCAILV3 checked the machine's on-demand flush here
    # (`tools/flush_test.py`). Momoka's `sensors` section is off, so there is
    # no collector buffer for a reply to ask about.

    # /idle, /reply and /selfstart force what normally waits on her clock, and
    # the whole of their value is that they take the loop's own path. What is
    # checked here is that there is only one such path: the loop's ordinary
    # pass and the forced one are the same method, so the loop's branch may
    # hold nothing but the call to it. The whole run
    # (`python tools/poke_test.py`) builds the second character on a copy and
    # drives all three with the model stubbed.
    print("[smoke] forcing a tick, a reply or an opener takes the loop's own path")
    r = subprocess.run([sys.executable, os.path.join("tools", "poke_test.py"), "--static"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    lines = [l for l in (r.stdout or "").splitlines() if l.strip()]
    if r.returncode:
        print("  FAIL " + (lines[-1].strip() if lines else "(no output)"))
        for l in [l for l in lines if l.strip().startswith("FAIL")][:12]:
            print("   " + l.strip()[:120])
        failures.append("forcing a tick or a reply")
    else:
        print("  ok   " + (lines[-1].strip() if lines else "checked"))

    # a token added to a shared prompt is a hole in every character's fills
    # file that already existed, and Config.fill writes a placeholder into
    # her prompt where the value should be. Twelve of the fourteen tokens
    # added on 2026-09-05 had no value in the third character's packages the
    # next day. Rendered through fill(), so a token inside a fork she drops
    # is not a hole; a role whose section is off for her is skipped.
    print("[smoke] every role of every character renders with no unfilled token")
    r = subprocess.run([sys.executable, os.path.join("tools", "fills_check.py")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    lines = [l for l in (r.stdout or "").splitlines() if l.strip() and not l.startswith("[config]")]
    if r.returncode:
        print("  FAIL " + (lines[-1].strip() if lines else "(no output)"))
        for l in lines[:12]:
            print("   " + l.strip()[:120])
        failures.append("fills")
    else:
        print("  ok   " + (lines[-1].strip() if lines else "checked"))

    # SCAILV3 built one of every character kind the sheet can declare here
    # (`tools/existence_matrix.py`). This fork carries the resident shape
    # alone; `tools/new_character.py verify` above already builds and renders
    # Momoka's own prompt.

    # the two generated indexes, regenerated here so the docs check below
    # reads the current code's version: which checks run and what every
    # module is
    print("[smoke] the checks index and the module map regenerated")
    for _gen in ("checks_index.py", "modmap.py"):
        r = subprocess.run([sys.executable, os.path.join("tools", _gen)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        lines = [l for l in (r.stdout or "").splitlines() if l.strip()]
        print(("  ok   " if not r.returncode else "  FAIL ") + (lines[-1].strip() if lines else _gen))
        if r.returncode:
            failures.append(_gen)

    # a doc that names a config key, a function or a file the code does not
    # have is worse than no doc, because it is believed
    # SCAILV3 audited the docs against the code here (`tools/docs_check.py`).
    # That checker is written for the v3 tree and its `config.json`; the two
    # generated indexes above are what this fork keeps in step, and the docs
    # themselves are read by hand.

    print("[smoke] blocks that appear twice in a row")
    # The other half of a patch that landed badly. A non-idempotent script
    # re-run after a partial failure duplicates its inserts, and a doubled
    # block is valid Python: it imports, it parses, the App builds. It has
    # happened four times, and the fourth ran contagion at double strength for
    # a day before anyone noticed the log line printed twice.
    from tools import dupscan
    dupes = dupscan.scan(".")
    if dupes:
        failures.append("duplicated blocks")
        for path, line, length, first in dupes:
            print(f"  FAIL {path}:{line} {length} line(s) repeated immediately: {first[:70]}")
    else:
        print("  ok   nothing duplicated")

    # Every character, not the first one only: the construction check gated
    # every restart of both bots and had only ever built the first. Eighteen
    # of the second's subsystems are off and her program builds different
    # objects, so a changed signature on her path passed the gate that guards
    # her restart.
    print("[smoke] constructing the whole app for every character (this is the part that catches a changed signature)")
    import scail
    others = []
    for cfgpath in [p for p in sorted(glob.glob("config_*.json")) if p != MAIN_CONFIG]:
        try:
            with io.open(cfgpath, encoding="utf-8") as f:
                dbp = (_json.load(f).get("logging") or {}).get("db_path", "")
        except Exception:
            dbp = ""
        if dbp and os.path.exists(dbp):
            tmp2 = os.path.join(tempfile.gettempdir(), "scail_smoke_" + os.path.basename(dbp))
            _copy_save(dbp, tmp2)
            others.append((cfgpath, tmp2))
    for cfgpath, dbp in others:
        other = check(f"App.__init__ ({cfgpath})", lambda: _build(cfgpath, dbp))
        if other is not None:
            def _lore(o=other):
                if not o.config.lore.enabled:
                    return "lore off"
                assert o.lore is not None and o.lore._recs, "lore is on and the record is empty"
                return f"{len(o.lore._recs)} claim(s) reachable"
            _lr = check(f"her own record loads ({cfgpath})", _lore)
            if _lr:
                print(f"       {_lr}")
            check(f"persona._system ({cfgpath})", lambda o=other: o.persona._system())
            check(f"thread ({cfgpath})", lambda o=other: o.thread.build())
            leak = [s for s in scail.PROGRAM_SLOTS if getattr(other, s, None) is not None]
            print(f"       program slots built for her: {', '.join(leak) or 'none'}")
            _wiring(other, cfgpath)
    app = check(f"App.__init__ ({MAIN_CONFIG})", lambda: _build(MAIN_CONFIG, tmp))
    if app is None:
        return 1
    _wiring(app, MAIN_CONFIG)

    print("[smoke] names read before a local of the same name is bound")
    # A local named like a module shadows it for the whole function, and the
    # read above the assignment raises at runtime: `sight = self.sight` in
    # the persona's situation builder killed every reply of both characters
    # for an evening, and neither the App build nor the prompt render took
    # that branch. pyflakes sees it statically; smoke fails on it.
    import subprocess
    _pf = subprocess.run([sys.executable, "-m", "pyflakes", "scail.py", "config.py", "llm.py", "store.py", "sim", "persona",
                          "embodied", "world", "machine", "resident", "channels"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    _bad = [l for l in (_pf.stdout or "").splitlines() if "referenced before assignment" in l or "undefined name" in l]
    if _bad:
        failures.append("shadowed names")
        for l in _bad[:10]:
            print(f"  FAIL {l.strip()}")
    else:
        print("  ok   none")

    print("[smoke] the command table")
    # every row names a method that exists; a method touching a program slot
    # its row does not name would run into a None for a character without it;
    # every command has a help row and every help row a command
    import inspect, textwrap
    bad = []
    heads = {cmd.split()[0] for _, rows in app.HELP for cmd, _ in rows}
    for name, (meth, needs, _arg) in app.COMMANDS.items():
        fn = getattr(type(app), meth, None)
        if fn is None:
            bad.append(f"{name}: no method {meth}")
            continue
        touched = {n.attr for n in ast.walk(ast.parse(textwrap.dedent(inspect.getsource(fn))))
                   if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "self"
                   and n.attr in scail.PROGRAM_SLOTS}
        if touched - set(needs):
            bad.append(f"{name}: touches {', '.join(sorted(touched - set(needs)))} and its row does not say so")
        if name not in heads:
            bad.append(f"{name}: no help row")
    for h in sorted(heads - set(app.COMMANDS)):
        bad.append(f"help row {h}: no such command")
    if bad:
        failures.append("command table")
        for b in bad:
            print(f"  FAIL {b}")
    else:
        print(f"  ok   {len(app.COMMANDS)} commands, every slot they touch declared, every one with a help row")

    print("[smoke] the reports that make a miswiring visible")
    for label, fn in (("state.wiring_report", lambda: app.state.wiring_report()),
                      ("state.affect_report", lambda: app.state.affect_report()),
                      ("state.system_prompt", lambda: app.state.system_prompt()),
                      ("state.mood_tags", lambda: app.state.mood_tags()),
                      ("persona._system (her whole prompt)", lambda: app.persona._system()),
                      ("goals.report", lambda: app.goals.report()),
                      ("commitments.report", lambda: app.commitments.report()),
                      ("attachment.report", lambda: app.attachment.report()),
                      ("commitments.situation_line", lambda: app.commitments.situation_line()),
                      ("spirals.report", lambda: app.spirals.report()),
                      ("model_of_him.report",
                       lambda: app.model_of_him.report() if app.model_of_him
                       else "(no picture of him: she has no chat with him at all)"),
                      ("model_of_her.report", lambda: app.model_of_her.report())):
        check(label, fn)

    print()
    print(app.state.wiring_report())
    print()
    print(app.state.affect_report().split(chr(10) + chr(10))[1])

    # one person: every call that writes her words builds from
    # persona.system_for, and the him-side prompt is the friend-side core
    # plus style.md and nothing else. Two assemblies were how her friend
    # turns carried none of her interior for eleven days.
    def _one_person():
        him = app.persona.system_for("him")
        core = app.persona.system_for("friend")
        assert core and him.startswith(core), "the him-side system prompt does not begin with the friend-side core"
        tail = him[len(core):].strip()
        assert tail == app.persona.style.strip(), f"the him-side tail is not style.md alone ({len(tail)} chars)"
        # SCAILV3 also read tomoe/exchange.py and tomoe/posting.py here to prove
        # her rooms built from the same core; that character is not in this fork,
        # so the source-file half cannot run. The rendered-prompt half below
        # still holds for Momoka.
        # the two halves: nothing she carries is in the system prompt, and
        # every carried section that has text is in the block
        from persona import sections as _sec
        carried = app.persona.carried_for()
        for name in _sec.CARRIED:
            text = (app.persona._sections.get(name) or "").strip()
            if text:
                assert text[:80] in carried, f"carried section '{name}' is not in the <carrying> block"
                assert text[:80] not in him, f"carried section '{name}' is still in the system prompt"
        return f"friend core {len(core)} chars; him = core + style.md ({len(him)}); carried {len(carried)} chars"
    _r = check("one person: friend-side system = persona core, him-side = core + style.md", _one_person)
    if _r:
        print(f"       {_r}")

    def _outing_binding():
        """A plan for a public event names the calendar entry it means, and
        a name the calendar has not got on that date is refused. The word
        list alone could not see the paraphrase: the same festival came back
        as "meet dad at the station tomorrow" and rode another day."""
        led, cal = app.ledger, app.calendar
        if not (led and cal and getattr(app.config.world, "outing_words", None)):
            return "no world of her own: nothing to check a plan against"
        import datetime as _dt
        d = app.clock.now().date()
        found = None
        for i in range(0, int(app.config.world.event_lookahead_days) + 1):
            dd = d + _dt.timedelta(days=i)
            for e in cal.events(dd):
                found = (dd, e["name"])
                break
            if found:
                break
        assert found, "the calendar has nothing at all in the lookahead; a plan has no date to name"
        dd, name = found
        mark = led.event_mark(dd.isoformat(), name)
        assert led.event_ok("%s %s" % (dd.isoformat(), name)), f"the calendar will not own its own entry: {name[:40]}"
        assert led.outing_unbacked("meet him at the station in the morning " + mark, dd.isoformat()) == "", \
            "a line bound to a real entry is refused"
        assert led.outing_unbacked("meet him at the station in the morning "
                                   + led.event_mark(dd.isoformat(), "夏の大花火大会 2026"), dd.isoformat()), \
            "a line naming an entry the calendar has not got on that date is accepted"
        assert app.cast is None or app.cast.event_of({"event": "%s %s" % (dd.isoformat(), name)}, dd.isoformat(), "smoke") == mark, \
            "the planner's binding does not validate against the calendar"
        assert app.cast is None or app.cast.event_of({"event": "2000-01-01 nothing"}, dd.isoformat(), "smoke") is None, \
            "the planner may name a date the calendar has nothing on"
        return f"a plan may name {name[:40]} on {dd.isoformat()}, and nothing else on that date"
    _r = check("a plan for a public event names a calendar entry", _outing_binding)
    if _r:
        print(f"       {_r}")

    def _thread():
        from sim.thread import WORLD_HEAD
        import re as _re
        msgs = app.thread.build()
        if not msgs:
            return "the save has no messages yet; nothing to merge"
        for a, b in zip(msgs, msgs[1:]):
            assert a["role"] != b["role"], "two consecutive messages with the same role"
        # her own turns are bare: no label of the record's on anything she
        # said, and the world's line about it after every run of them
        label = _re.compile(r"^\[(?:(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\b|\d{1,2}:\d{2}|that was you,)")
        for i, m in enumerate(msgs):
            if m["role"] != "assistant":
                continue
            bad = [ln for ln in m["content"].split("\n") if label.match(ln)]
            assert not bad, f"a turn of hers carries the record's label: {bad[0][:60]}"
            assert i + 1 < len(msgs) and msgs[i + 1]["content"].startswith(WORLD_HEAD), \
                "a turn of hers with no world line after it"
        rooms = sum(1 for m in msgs if "· chat with him" in m["content"] or "to him]" in m["content"])
        theirs = sum(1 for m in msgs if "LINE with" in m["content"] or "group chat" in m["content"] or "in person," in m["content"])
        if rooms and not theirs:
            # A character with no cast has no second room to merge into this
            # one, so the assertion below cannot apply: it is the same skip
            # `_cast_thread` makes. The save having messages is what makes this
            # reachable -- a fork whose character is castless failed here the
            # moment she and he had said anything at all.
            from sim import roster
            if not any(str(roster.rec_of(app.config, k).get("role_id")) == "ringleader"
                       for k in roster.everyone(app.config)):
                return f"{len(msgs)} messages; him-room {rooms}, no cast room (her cast is off)"
        assert rooms and theirs, f"one room missing from the thread (him {rooms}, theirs {theirs})"
        return f"{len(msgs)} messages after merging; him-room {rooms}, their rooms {theirs}"
    _t = check("thread: one history, both rooms, roles alternating", _thread)
    if _t:
        print(f"       {_t}")

    def _cast_thread():
        from sim import roster
        friend = next((k for k in roster.everyone(app.config) if str(roster.rec_of(app.config, k).get("role_id")) == "ringleader"), None)
        if not friend:
            return "no ringleader on the roster (her cast is off); nothing to check"
        msgs = app.thread.build(for_who=friend)
        for a, b in zip(msgs, msgs[1:]):
            assert a["role"] != b["role"], "two consecutive messages with the same role"
        assert not any("chat with him" in m["content"] or "to him]" in m["content"] for m in msgs), "a friend's thread carries her chat with him"
        return f"{friend}: {len(msgs)} messages, none from her chat with him"
    _ct = check("thread: a cast member's witnessed rooms only, roles alternating", _cast_thread)
    if _ct:
        print(f"       {_ct}")

    def _him_room_tail():
        """The room with him ends on his own newest messages -- or on the line
        saying there are none -- and then on the closing line, and on nothing
        else. At 20:07 on 2026-09-05 five group-chat turns in Japanese were
        the last thing in that prompt and she answered them, in Japanese, and
        it went to him."""
        from sim import thread as _th
        msgs = app.thread.build()
        frame, none = app.persona.frame_line(), app.persona.frame_line(his=False)
        closing = _th.closing_line(app.config, language=str(app.config.character.writes_to_him),
                                   why="you want to check on him", first=True)
        out = _th.place_tail(msgs, "<carrying>\n(x)\n</carrying>\n\n<situation>\n(x)\n</situation>",
                             frame, none, closing)
        assert out[:-1] == msgs[:-1], "place_tail moved a message before the last one"
        last = out[-1]["content"]
        assert last.rstrip().endswith(closing), "his room's final turn does not end on the closing line"
        under = last[: -len(closing)]
        if frame in under:
            under = under.split(frame)[-1]
            bad = [ln for ln in under.split("\n") if ln.startswith("[") and _th.HIM_TURN not in ln]
            assert not bad, f"his room's final turn carries somebody else's line under the frame: {bad[0][:70]}"
            shape = f"{len([l for l in under.splitlines() if l.strip()])} line(s) of his under the frame"
        else:
            assert none in under, \
                "his room's final turn ends on neither his newest messages nor the line saying there are none"
            shape = "nothing of his: the one line saying so"
        return shape + ", then the closing line"
    _ht = check("the room with him: only his own newest messages under the frame line", _him_room_tail)
    if _ht:
        print(f"       {_ht}")

    unrendered = [t for t in ("{{TELLS}}", "{{DELTAS}}") if t in (app.state.system_prompt() or "")]
    if unrendered:
        failures.append("state prompt placeholders")
        print(f"  FAIL the state prompt still contains {unrendered}")

    if args.tick:
        print()
        print("[smoke] one director tick")
        check("director tick", lambda: app.tick())

    print()
    if failures:
        print(f"[smoke] {len(failures)} FAILURE(S): {', '.join(failures)}")
        return 1
    print("[smoke] all clear")
    return 0


if __name__ == "__main__":
    sys.exit(main())
