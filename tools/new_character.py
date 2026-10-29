"""A character is a bundle plus the library: compose her, then verify her.

One directory per character, `characters/<key>/`, holding everything that is
one person and nothing that is not -- who she is, where she lives, who is
around her, what she believes, how she talks, which prompts she has rewritten,
and the manifest that says what kind of thing she is and how she is run. The
library holds everything that is the same for everybody. `docs/bundle.md` is
the reference; `docs/character-layers-plan.md` is why.

    python tools/new_character.py list
    python tools/new_character.py compose <key> --diff   # write nothing, say what differs
    python tools/new_character.py compose <key>          # config, prompts, register row, launcher, save
    python tools/new_character.py verify <key>           # build her and fail on a leak
    python tools/new_character.py verify --all

**compose** writes, in this order: her config (from the library's defaults,
the machine's settings, her manifest's overrides and her bundle's files); her
prompt directory, as a copy of the bundle's; her row in the register; her
launcher, staged as `<launcher>.next` because a running console reads a batch
file by byte offset; and last her save, created only when the path does not
exist and seeded by building her once with the model and the network refused,
so the meters come from `sim/roster.py:meter_rows` and never from a clone.

**verify** builds her whole App on a scratch save with the model and the
network refused, renders her prompts, and fails on a surviving hole, a path
that is neither hers nor the machine's nor the world's, another registered
character's material in her prompts or in her seeded save, a roster that does
not resolve her to herself, a missing world owner, a meter on somebody who is
neither hers nor the owner nor him, or an existence answer that disagrees with
her sheet.

A secret is never written into a bundle. `characters/machine.json` names the
keys that are pasted in once; compose keeps whatever the character's existing
config already carries for each, and leaves a new character's empty with a
line saying so.
"""
import argparse
import copy
import filecmp
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

BUNDLES = "characters"
MACHINE = os.path.join(BUNDLES, "machine.json")

# a file path or a URL is not somebody's name: the same cut the log-side check
# makes before it looks for one
_NOPATH = __import__("re").compile(r"\S+[\\/]\S+|https?://\S+")


def set_root(root):
    """Where the bundles live. `--root` points the whole tool at a directory of
    scratch bundles, so a promotion can be composed and verified end to end
    without a byte of the live tree moving."""
    global BUNDLES, MACHINE
    BUNDLES = root
    MACHINE = os.path.join(root, "machine.json")
    if not os.path.exists(MACHINE):
        MACHINE = os.path.join("characters", "machine.json")


def bundle_dir(key):
    return os.path.join(BUNDLES, key)


def load_json(path, default=None):
    try:
        with io.open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {} if default is None else default


def keys_with_bundles():
    """Every registered character, and whether she has a bundle directory.

    When `--root` points somewhere else, the bundles in that directory are the
    list instead: a scratch bundle is not in the operator's register and must
    not be."""
    from tools import registry
    rows = registry.characters()
    if os.path.abspath(BUNDLES) != os.path.abspath("characters"):
        rows = []
        for name in sorted(os.listdir(BUNDLES)):
            b = load_json(os.path.join(BUNDLES, name, "bundle.json"))
            if b.get("key"):
                rows.append(b)
    return [(r, os.path.isdir(bundle_dir(r["key"]))) for r in rows]


# ---------------------------------------------------------------- the config


def _put(d, dotted, value):
    parts = dotted.split(".")
    cur = d
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = value


def _dig(d, dotted):
    cur = d
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _flat(d, pre=""):
    out = {}
    for k, v in (d or {}).items():
        p = pre + k
        if isinstance(v, dict):
            out.update(_flat(v, p + "."))
        else:
            out[p] = v
    return out


def compose_config(key, note=print):
    """The config this bundle and the library make, as a tree.

    Nothing is written and nothing is read out of the character's own config
    except the secrets, which a bundle must not carry."""
    from config import DEFAULTS, _merge
    b = load_json(os.path.join(bundle_dir(key), "bundle.json"))
    if not b:
        raise SystemExit("[compose] %s has no bundle: %s" % (key, bundle_dir(key)))
    machine = load_json(MACHINE)
    cfg = _merge(DEFAULTS, machine.get("settings") or {})
    cfg = _merge(cfg, b.get("config_overrides") or {})

    for ckey, name in sorted((b.get("files") or {}).items()):
        _put(cfg, ckey, (bundle_dir(key) + "/" + name).replace("\\", "/"))
    for ckey in b.get("blank") or []:
        cur = _dig(cfg, ckey)
        if isinstance(cur, bool):
            blank = False
        elif isinstance(cur, (int, float)):
            blank = 0
        elif isinstance(cur, list):
            blank = []
        elif isinstance(cur, dict):
            blank = {}
        else:
            blank = ""
        _put(cfg, ckey, blank)
    _put(cfg, "logging.db_path", b.get("db") or "")

    # the secrets: pasted in once, never in a bundle. Whatever her existing
    # config carries is kept; a character who has none is composed with them
    # empty and told so.
    live = load_json(b.get("config") or ("config_%s.json" % key))
    absent = []
    for ckey in machine.get("secrets") or []:
        v = _dig(live, ckey)
        if v in (None, ""):
            absent.append(ckey)
            continue
        _put(cfg, ckey, v)
    if absent:
        note("  note %d secret(s) not carried over (no config of hers to read them from): %s"
             % (len(absent), ", ".join(absent)))
    return cfg, b


def _json_bytes(tree):
    return json.dumps(tree, indent=2, ensure_ascii=False) + "\n"


def diff_config(key, note=print):
    """(same, lines) -- what the composed config says that the live one does not."""
    cfg, b = compose_config(key, note=note)
    live_path = b.get("config") or ("config_%s.json" % key)
    live = load_json(live_path)
    a, c = _flat(live), _flat(cfg)
    lines = []
    for k in sorted(set(a) | set(c)):
        if a.get(k, "<absent>") != c.get(k, "<absent>"):
            lines.append("      %-44s live %s | composed %s"
                         % (k, json.dumps(a.get(k, "<absent>"), ensure_ascii=False)[:44],
                            json.dumps(c.get(k, "<absent>"), ensure_ascii=False)[:44]))
    order = "" if list(_flat(live)) == list(_flat(cfg)) else "key order differs"
    return (not lines), lines, order


# ---------------------------------------------------------------- compose


def _copy_tree(src, dst, note):
    if not os.path.isdir(src):
        return 0
    n = 0
    for base, dirs, names in os.walk(src):
        rel = os.path.relpath(base, src)
        out = dst if rel == "." else os.path.join(dst, rel)
        os.makedirs(out, exist_ok=True)
        for f in names:
            s, d = os.path.join(base, f), os.path.join(out, f)
            if os.path.exists(d) and filecmp.cmp(s, d, shallow=False):
                continue
            shutil.copy2(s, d)
            n += 1
    if n:
        note("  wrote %d file(s) into %s" % (n, dst))
    return n


def compose(key, write=True, note=print):
    if not write:
        same, lines, order = diff_config(key, note=note)
        note("  %s: %d key(s) differ from the config she runs on%s"
             % (key, len(lines), ("; " + order) if order else ""))
        for l in lines:
            note(l)
        return 0 if same else len(lines)
    cfg, b = compose_config(key, note=note)

    # 1. the config
    path = b.get("config") or ("config_%s.json" % key)
    with io.open(path, "w", encoding="utf-8") as f:
        f.write(_json_bytes(cfg))
    note("  wrote %s" % path)

    # 2. her prompt directory. `prompts/` is the library's own: the three files
    #    in it that are a character -- her voice and her speech guide in each
    #    language -- are checked against the bundle rather than written back,
    #    because writing into the shared directory would touch every character.
    src = os.path.join(bundle_dir(key), "prompts")
    if b.get("prompts_generated"):
        _copy_tree(src, b["prompts_dir"], note)
    elif os.path.isdir(src):
        for f in sorted(os.listdir(src)):
            s, d = os.path.join(src, f), os.path.join(b.get("prompts_dir") or "prompts", f)
            if os.path.exists(d) and not filecmp.cmp(s, d, shallow=False):
                note("  DIFFERS from her bundle and is in the library's own prompt directory, "
                     "so it is not written back: %s" % d)

    # 3. her row in the register. A bundle that says it is not registered is a
    #    scratch character -- a promotion being tried out, a kind of character
    #    the matrix builds -- and the operator's list is left alone.
    scratch = b.get("registered") is False
    if scratch:
        note("  her manifest says she is not registered: the register and the launcher are "
             "left alone")
    else:
        reg = load_json("characters.json")
        rows = reg.get("characters") or []
        row = {k: b.get(k, "") for k in ("key", "name", "hub_id", "config", "db",
                                         "program", "launcher", "task", "match")}
        for i, r in enumerate(rows):
            if r.get("key") == key:
                keep = {k: v for k, v in r.items() if k.startswith("_")}
                rows[i] = dict(row, **keep)
                break
        else:
            rows.append(row)
        reg["characters"] = rows
        with io.open("characters.json", "w", encoding="utf-8") as f:
            f.write(_json_bytes(reg))
        note("  wrote her row in characters.json")

    # 4. the launcher, staged. Never over a running console: cmd reads a batch
    #    file by byte offset, and an edited launcher under a running process
    #    started a second hub on the port.
    launcher = "" if scratch else (b.get("launcher") or "")
    if launcher and not os.path.exists(launcher):
        with io.open(launcher + ".next", "w", encoding="utf-8", newline="\r\n") as f:
            f.write("@echo off\r\ncd /d %s\r\npython scail.py --config %s\r\npause\r\n"
                    % (ROOT, b.get("config") or ""))
        note("  staged %s.next (the restarter moves it into place)" % launcher)

    # 5. her own people's meters, read before anything is seeded from them.
    #    A row at 0/0/0 is what the world owner's roster carries for a
    #    household the owner has never met, and a promoted character's own
    #    cast file is written from those rows, so her save held her mother and
    #    her brother as strangers (`sim/roster.py:flat_own_meters`).
    flat, where = {}, ""
    try:
        from config import Config
        from sim import roster
        _cfg = Config(path)
        where = str(_cfg.character.own_cast_file or _cfg.character.cast_file or "")
        flat = roster.flat_own_meters(_cfg)
    except Exception as e:
        note("  note her own people's meters were not read: %s: %s" % (type(e).__name__, e))
    if flat:
        for who, why in sorted(flat.items()):
            note("  REFUSED %s: %s" % (who, why))
        note("  nothing is seeded from those. Give each of them closeness, standing and tension "
             "in %s, or say the zeros are meant with \"numbers\": \"unset\"."
             % (where or "her cast file"))
        return len(flat)

    # 6. her save, last, and only when there is none: an existing save is left
    #    alone and named. Seeded by building her once with the model and the
    #    network refused, so the meters come from `sim/roster.py:meter_rows`.
    db = b.get("db") or ""
    if not db:
        note("  no save named in her manifest")
    elif os.path.exists(db):
        note("  her save exists and is left alone: %s" % db)
    else:
        from tools import harness
        harness.refuse_network()
        harness.refuse_model_before_build()
        os.makedirs(os.path.dirname(db) or ".", exist_ok=True)
        app = harness.build_on(db, path, db, copy=False)
        app.state.save()
        note("  seeded an empty save at %s: %d meter(s) from her roster"
             % (db, len(app.state.relationships or {})))
    return 0


# ---------------------------------------------------------------- verify


def _others_material(mine_cfg, my_key):
    """Every name and place that belongs to another registered character and
    not to this one.

    The check that reads a run's log for one character's material appearing in
    another's output already builds a character's own record as a set of names
    (`tools/character_leaks.py:known`). This inverts it: the union of every
    OTHER character's record, minus this character's own, minus the world they
    legitimately share.

    What counts as another character's material is her names, her places, her
    roster's keys (`tools/character_names.py:material`, which reads them off
    the sheets, the cast files and the maps) and the members of her household.
    The record-derived set is not used as the THEIRS side: it is built by two
    regexes over whole files including their prose, so it holds `Born`,
    `Casual Japanese`, `シート` and `バイト` as well as names, and a check that
    fails on those is a check nobody can leave switched on. It is used as the
    HERS side, which is the direction it is safe in: a word anywhere in her
    own record is hers, and subtracting too much there costs a report, never a
    false failure."""
    import glob as _glob
    from config import Config
    from tools import character_leaks, character_names, registry
    mine = character_leaks.known(mine_cfg)
    my_world = ""
    ws = getattr(mine_cfg, "world_shared", None)
    if getattr(ws, "enabled", False):
        my_world = str(getattr(ws, "id", "") or "")
    share = {my_key}
    for r in registry.characters():
        if r["key"] == my_key or not my_world:
            continue
        try:
            other = Config(path=r["config"])
        except SystemExit:
            continue
        ows = getattr(other, "world_shared", None)
        if getattr(ows, "enabled", False) and str(getattr(ows, "id", "")) == my_world:
            share.add(r["key"])   # one world: her places and her people are in both by design

    out = {}
    for lit, row in character_names.material().items():
        if row["who"] & share or lit in mine:
            continue
        out[lit] = ",".join(sorted(row["who"]))
    # and the people in her house, whom no roster names
    for r in registry.characters():
        if r["key"] in share:
            continue
        for p in _glob.glob(os.path.join(bundle_dir(r["key"]), "household.json")):
            for who in (load_json(p).get("members") or {}).values():
                for f in ("name", "name_ja", "reading", "full"):
                    n = str((who or {}).get(f) or "").strip() if isinstance(who, dict) else ""
                    if len(n) >= 3 and n not in mine and n not in character_leaks.STOP:
                        out.setdefault(n, r["key"])
    return out


def verify(key, note=print):
    """Build her on a scratch save and fail on any of the seven."""
    from config import Config
    from sim import roster
    from tools import harness, registry

    fails = []

    def check(ok, what, detail=""):
        note(("  ok   " if ok else "  FAIL ") + what + (("  -- " + detail) if detail else ""))
        if not ok:
            fails.append(what)

    b = load_json(os.path.join(bundle_dir(key), "bundle.json"))
    if not b:
        raise SystemExit("[verify] %s has no bundle" % key)
    # her row, or the manifest itself for a character who is not in the
    # operator's register and must not be
    row = next((r for r in registry.characters() if r["key"] == key), b)

    harness.refuse_network()
    harness.refuse_model_before_build()
    d = tempfile.mkdtemp(prefix="scail_verify_%s_" % key)
    db = os.path.join(d, "scratch.db")
    app = harness.build_on(db, row["config"], row["db"], copy=False)
    cfg = app.config

    # 1. no hole survives in a role prompt her existence keeps. The same
    #    renderer the fills check runs, so the two cannot give two answers
    #    about the same prompt.
    from tools import fills_check
    holes, unread = fills_check.check(row["config"], quiet=True)
    check(not holes and not unread,
          "every role prompt her existence keeps renders with no hole left",
          ", ".join(sorted(holes) + unread)[:100] or "no unfilled token, every prompt file there")

    # 2. every path she reads is hers, the machine's, the mechanism prompts' or
    #    the world she shares
    from tools import isolation
    mine_pre = (bundle_dir(key).replace("\\", "/") + "/", "prompts/", "logs/", "data/retired/")
    world_ok = set(isolation.WORLD) | {"logging.db_path"}
    if b.get("prompts_generated") and b.get("prompts_dir"):
        mine_pre += (b["prompts_dir"].replace("\\", "/") + "/",)
    stray = []
    for ckey, v in sorted(isolation.paths(cfg.raw).items()):
        p = v.replace("\\", "/")
        if ckey.startswith(isolation.MACHINE) or ckey.startswith(isolation.NEUTRAL):
            continue
        if p.startswith(mine_pre):
            continue
        if ckey in world_ok:
            continue
        stray.append("%s=%s" % (ckey, v))
    check(not stray, "every path in her config is her bundle, the machine, a mechanism prompt "
                     "or the world she shares", ", ".join(stray[:4]))

    # 3. no other character's material in her prompts or in her seeded save
    theirs = _others_material(cfg, key)
    blob = [app.persona._system(), app.persona.carried_for()]
    for role, spec in sorted((cfg.raw.get("models") or {}).items()):
        p = str((spec or {}).get("prompt") or "")
        if p and os.path.exists(p) and not fills_check._section_off(cfg, role):
            try:
                blob.append(cfg.fill(io.open(p, encoding="utf-8").read(), role))
            except Exception:                                    # noqa: BLE001
                pass
    seeded = []
    _collect(app.state.relationships, seeded)
    _collect(app.store.get("sentiments", {}), seeded)
    # whole name against whole name, never a substring: `Rena` sits inside a
    # longer word and a substring test both misses names and invents them
    from tools import character_leaks
    text = "\n".join(blob) + "\n" + "\n".join(seeded)
    said = set()
    for line in text.split("\n"):
        line = _NOPATH.sub(" ", line)
        said |= set(character_leaks.JA.findall(line)) | set(character_leaks.EN.findall(line))
    found = sorted({"%s (%s)" % (n, who) for n, who in theirs.items() if n in said})
    check(not found, "no other character's name or place is in her prompts or her seeded save",
          ", ".join(found[:6]) or "%d looked for" % len(theirs))

    # 3b. and no file in her bundle IS another character's file.
    #
    # The name test cannot see this one when the two are in one world: the
    # owner's mother, father and brother are rows on the roster they share, so
    # a reader handed the owner's household file is handed names her own
    # roster legitimately has, and every one of them cancels out. The
    # structural question has no such hole -- two people do not have the same
    # household, the same flat, the same record or the same face -- and it is
    # the question the fault actually asks.
    same_file = []
    for r in registry.characters():
        if r["key"] == key:
            continue
        for name in sorted(os.listdir(bundle_dir(key))):
            a = os.path.join(bundle_dir(key), name)
            c = os.path.join(bundle_dir(r["key"]), name)
            if not (os.path.isfile(a) and os.path.isfile(c)):
                continue
            if os.path.getsize(a) < 8 or name == "bundle.json":
                continue
            if filecmp.cmp(a, c, shallow=False):
                same_file.append("%s is %s's" % (name, r["key"]))
    check(not same_file, "no file in her bundle is another character's, byte for byte",
          ", ".join(same_file[:4]) or "%d file(s)" % len(os.listdir(bundle_dir(key))))

    # 4. her own key resolves to herself, and no name means two people
    handle = roster.handle(cfg)
    twins = [r.get("key") for r in roster.everyone(cfg).values()
             if r.get("role_id") != "self" and roster.is_self(cfg, str(r.get("key") or ""))]
    check(bool(handle) and roster.role_of(cfg, handle) == "self" and not twins,
          "her own key on her roster is her, and nobody else's",
          "%s -> %s%s" % (handle, roster.role_of(cfg, handle),
                          ("; twin: " + ", ".join(twins)) if twins else ""))
    collisions = [n for n in cfg.boot_notes if "means both" in n]
    check(not collisions, "no name on her roster means two people",
          collisions[0][:90] if collisions else "none")

    # 5. the owner of a world she reads is a person on her roster
    if getattr(cfg, "world_reader", False):
        own = load_json(str(getattr(cfg.character, "cast_file", "") or "")).get("self") or {}
        okey = str(own.get("key") or "")
        orec = roster.rec_of(cfg, okey) if okey else {}
        check(bool(okey) and bool(orec) and orec.get("role_id") != "self",
              "the owner of the world she reads is a person on her roster",
              "%s -> %s" % (okey or "(no keeper line)", (orec or {}).get("role_id", "-")))
    else:
        note("  ok   she is not a reader of somebody else's world: no owner to look for")

    # 6. every meter is on somebody her roster gives her
    want, refused = roster.meter_rows(cfg)
    him = {"him", app.state._him_key() or "him"}
    bad = [k for k in (app.state.relationships or {}) if k not in want and k not in him]
    check(not bad, "every meter is on somebody her roster has, or on him",
          ", ".join(bad[:6]) or "%d meter(s)" % len(app.state.relationships or {}))

    # 7. the existence answers in her config are her sheet's
    sheet_ex = {k: v for k, v in ((cfg.character_sheet or {}).get("existence") or {}).items()
                if not str(k).startswith("_")}
    live_ex = cfg.character.existence
    off = [k for k, v in sheet_ex.items() if getattr(live_ex, k, None) != v]
    check(bool(sheet_ex) and not off,
          "what kind of thing she is comes from her sheet and her config agrees",
          ", ".join(off) or ", ".join("%s=%s" % (k, v) for k, v in sorted(sheet_ex.items())))

    # 8. every one of her own people's meters is a number somebody chose
    flat = roster.flat_own_meters(cfg)
    check(not flat, "every one of her own people's meters is a number somebody chose",
          "; ".join("%s: %s" % (k, w) for k, w in sorted(flat.items()))
          or "%d of her own" % len(roster.own_keys(cfg)))

    # 9. and, for a character who lives in a world somebody else keeps, a day
    #    of her clock beside that somebody. The eight above are structural:
    #    one process, a scratch save, the model stubbed. Everything that went
    #    wrong on the fourth character's first day went wrong at runtime, on
    #    the seam, over a day (`tools/agent_rehearsal.py`), and none of the
    #    eight could have seen any of it.
    b_world = (b.get("world") or {})
    if b_world.get("id") and not b_world.get("owner"):
        note("  ..   living a day of her clock beside the character who keeps her world")
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "agent_rehearsal.py"),
                            key, "--root", os.path.dirname(bundle_dir(key)) or "characters"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        out = [l for l in (r.stdout or "").splitlines()
               if l.strip() and not l.startswith("[config]")]
        for line in out:
            if "FAIL" in line or line.startswith("[rehearsal]"):
                note("   " + line.strip()[:150])
        check(not r.returncode, "the seam holds over a day of her clock",
              (out[-1].strip()[:90] if out else "no output"))
    else:
        note("  ok   she keeps her own world or is in none: there is no seam to live a day on")

    return fails


def _collect(o, out):
    if isinstance(o, str):
        out.append(o)
    elif isinstance(o, dict):
        for k, v in o.items():
            out.append(str(k))
            _collect(v, out)
    elif isinstance(o, (list, tuple)):
        for v in o:
            _collect(v, out)


# ---------------------------------------------------------------- the verbs


def main():
    os.chdir(ROOT)
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("verb", choices=("list", "compose", "verify"))
    ap.add_argument("key", nargs="?", default="")
    ap.add_argument("--diff", action="store_true", help="compose: write nothing, say what differs")
    ap.add_argument("--all", action="store_true", help="every registered character")
    ap.add_argument("--root", default="characters",
                    help="where the bundles live; a scratch directory leaves the live tree alone")
    args = ap.parse_args()
    set_root(args.root)

    if args.verb == "list":
        bad = 0
        for r, has in keys_with_bundles():
            b = load_json(os.path.join(bundle_dir(r["key"]), "bundle.json"))
            print("  %-8s %-16s %-22s %s"
                  % (r["key"], r["name"], r["config"],
                     "%d file(s), %d key(s) emptied" % (len(b.get("files") or {}), len(b.get("blank") or []))
                     if has else "NO BUNDLE"))
            if not has:
                bad += 1
        return 1 if bad else 0

    keys = [r["key"] for r, _ in keys_with_bundles()] if (args.all or not args.key) else [args.key]

    if args.verb == "compose":
        n = 0
        for k in keys:
            print("[compose] %s" % k)
            n += compose(k, write=not args.diff)
        if args.diff:
            print("\n[compose] %d key(s) differ over %d character(s)" % (n, len(keys)))
        return 1 if (args.diff and n) else 0

    bad = []
    for k in keys:
        print("[verify] %s" % k)
        f = verify(k)
        if f:
            bad.append("%s: %s" % (k, "; ".join(f)))
    if bad:
        print("\n[verify] %d character(s) fail: %s" % (len(bad), " | ".join(bad)))
        return 1
    print("\n[verify] %d character(s), every bundle is hers alone" % len(keys))
    return 0


if __name__ == "__main__":
    sys.exit(main())
