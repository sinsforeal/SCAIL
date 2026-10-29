"""Who runs as a process, read from one list.

`characters.json` at the project root is the operator's register of
characters: one row each, with her config, her save, her program, her
launcher, her scheduled task and the exact command line her process is found
by. Before it, the restarter held a hand-written table of exactly two bots
whose first row matched the first character as "`scail.py` NOT followed by the
second one's config" -- so a third character launched with her own config
would have been matched as the first one and killed by `restart.cmd tomoe`.

**A bot never reads this.** A character that could read the register could
read another character's config and save; what she may know of a peer is her
own `peer_talk.contacts` and the words that actually arrive
(`docs/peer-talk.md`). This module is for the tools.

    python tools/registry.py            # the table, and what is missing
"""
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "characters.json")

_FIELDS = ("key", "name", "hub_id", "config", "db", "program", "launcher", "task", "match")


def characters(path=""):
    """[{key, name, hub_id, config, db, program, launcher, task, match}], in
    the order the file lists them, which is the order they are started in. A
    row missing a field is returned with it empty rather than dropped: a
    half-written row should be visible, not silently absent."""
    p = path or PATH
    try:
        with io.open(p, encoding="utf-8") as f:
            rows = json.load(f).get("characters") or []
    except (OSError, ValueError):
        return []
    out = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("key"):
            continue
        out.append({k: str(row.get(k, "") or "") for k in _FIELDS})
    return out


def bundles(path=""):
    """key -> her manifest, for every registered character who has a bundle.

    The register is a PROJECTION of the manifests: every field of a row is
    also in `characters/<key>/bundle.json`, which is where the rest of what
    she is lives. Two copies of one fact drift, so `main` below fails when
    they disagree and names the field."""
    out = {}
    for r in characters(path):
        p = os.path.join(ROOT, "characters", r["key"], "bundle.json")
        try:
            with io.open(p, encoding="utf-8") as f:
                out[r["key"]] = json.load(f)
        except (OSError, ValueError):
            continue
    return out


def programs(path=""):
    """The program packages the register names. What `tools/character_names.py`
    must not read as a person: a package directory is named after the
    character it runs, and a path into it is a file of hers."""
    return {r["program"] for r in characters(path) if r["program"]}


def main():
    rows = characters()
    if not rows:
        print("no characters registered: %s is missing or empty" % PATH)
        return 1
    print("%-8s %-16s %-10s %-22s %-18s %s" % ("key", "name", "hub id", "config", "save", "task"))
    bad = 0
    for r in rows:
        print("%-8s %-16s %-10s %-22s %-18s %s" % (r["key"], r["name"], r["hub_id"], r["config"], r["db"], r["task"]))
        for f in _FIELDS:
            if not r[f]:
                print("    MISSING %s" % f)
                bad += 1
        for f in ("config", "db", "launcher"):
            if r[f] and not os.path.exists(os.path.join(ROOT, r[f])):
                print("    %s does not exist: %s" % (f, r[f]))
                bad += 1
        bdir = os.path.join(ROOT, "characters", r["key"])
        if not os.path.isdir(bdir):
            print("    NO BUNDLE: characters/%s/ -- everything that is this person should be "
                  "in it (docs/bundle.md)" % r["key"])
            bad += 1
            continue
        b = bundles().get(r["key"])
        if not b:
            print("    NO MANIFEST: characters/%s/bundle.json" % r["key"])
            bad += 1
            continue
        for f in _FIELDS:
            if str(b.get(f, "") or "") != r[f]:
                print("    %s: the register says %r and her manifest says %r"
                      % (f, r[f], b.get(f, "")))
                bad += 1
    print("\n%d character(s), programs: %s" % (len(rows), ", ".join(sorted(programs())) or "none"))
    print("%d bundle(s) under characters/, each one everything that is that person"
          % len(bundles()))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
