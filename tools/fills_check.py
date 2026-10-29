"""Every role of every configured character, rendered; a hole nobody filled fails.

A shared mechanism prompt carries `[[TOKEN]]`s that each character fills from
her own sidecar (`character.neutral_file`). A token added to a shared prompt
makes a hole in every fills file that already exists, and `Config.fill` writes
`(not established for this character)` where the value should be -- loud on
the console once per role, which is a line a reader has to be present for.
On 2026-09-05 fourteen tokens were added; the next day twelve of them had no
value in either of the third character's packages and twenty-one had none in
the second character's file. None of the twenty-one reached her, because each
sat in a role her program does not build or inside a fork her existence drops
-- and nothing but a reading established that.

So this renders every role's prompt through `Config.fill` for every
character in `characters.json` (and any config given), the way the running
bot would, and fails on a placeholder that survives: a token inside a fork
the character drops is not a hole, and a role whose section is switched off
for her is skipped and named. A hole is reported with the roles it reaches.

    python tools/fills_check.py                         # every character in the register
    python tools/fills_check.py --config asumin/persona/card/records_only/character/config_resident.json
    python tools/fills_check.py --all-roles             # do not skip roles whose section is off
"""
import argparse
import io
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

PLACEHOLDER = "(not established for this character)"


def _configs_from_register():
    try:
        with open("characters.json", encoding="utf-8") as fh:
            reg = json.load(fh)
    except (OSError, ValueError) as e:
        print(f"characters.json unreadable: {type(e).__name__}: {e}")
        return []
    return [(row.get("name") or row.get("key"), row["config"]) for row in reg.get("characters", [])
            if row.get("config")]


def _load(cfgpath):
    """`Config` rewrites the file it is given, so it gets a copy."""
    from config import Config
    tmp = os.path.join(tempfile.gettempdir(), "scail_fills_" + os.path.basename(cfgpath))
    shutil.copy2(cfgpath, tmp)
    return Config(tmp)


def _section_of(c, role):
    """The switchable section a role belongs to, by name, or None.

    Most roles share their section's name (`diary`, `spiral`, `posting`); the
    rest carry it as a prefix or a suffix (`x_post` is the account's,
    `cast_day` and `reflect_cast` are the cast's, `scenery_judge` is the
    scenery's). A role that matches no switchable section is the mind's and
    always runs. Named by string because nothing in the code records which
    section calls which role; the skip is printed with its reason so a wrong
    match is visible rather than silent."""
    switchable = {k for k, v in c.raw.items() if isinstance(v, dict) and "enabled" in v}
    parts = role.split("_")
    cands = [x for x in (role, "_".join(parts[:2]), "_".join(parts[-2:]), parts[0], parts[-1]) if x in switchable]
    if not cands:
        return None
    # a role that names two sections (`reflect_cast`: the reflection, about a
    # cast member) needs both, so the one that is off is the one that decides
    off = [x for x in cands if not c.raw[x].get("enabled")]
    return off[0] if off else cands[0]


def _section_off(c, role):
    sect = _section_of(c, role)
    return sect is not None and not c.raw[sect].get("enabled")


def check(cfgpath, who="", all_roles=False, quiet=False):
    c = _load(cfgpath)
    who = who or getattr(c.character, "name", cfgpath)
    holes = {}          # token -> roles it reaches
    skipped = []
    unread = []
    n = 0
    for role, m in sorted((c.raw.get("models") or {}).items()):
        path = (m or {}).get("prompt") if isinstance(m, dict) else None
        if not path:
            continue
        if not all_roles and _section_off(c, role):
            skipped.append(f"{role} ({_section_of(c, role)} off)")
            continue
        if not os.path.exists(path):
            unread.append(f"{role} -> {path}")
            continue
        n += 1
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        out = c.fill(text, role)
        if PLACEHOLDER not in out:
            continue
        # which tokens: re-fill with the missing-name collector exposed by the
        # config's own warning line is console-only, so find them here
        import re
        fills = c._fills()
        for m2 in re.finditer(r"\[\[([A-Z][A-Z0-9_]+)\]\]", _forked_only(c, text, role)):
            if fills.get(m2.group(1)) is None:
                holes.setdefault(m2.group(1), set()).add(role)
    if not quiet:
        print(f"{who}: {n} role prompt(s) rendered"
              + (f", {len(skipped)} skipped because the section is off ({', '.join(skipped)})" if skipped else "")
              + (f"; {len(unread)} prompt file(s) missing: {', '.join(unread)}" if unread else ""))
        for tok, roles in sorted(holes.items()):
            print(f"  HOLE {tok}: reaches {', '.join(sorted(roles))}")
    return holes, unread


def _forked_only(c, text, role):
    """The text after the character's forks are applied and before the
    tokens are filled, so a token inside a dropped fork does not count."""
    cond = c.conditions()

    def block(m):
        sense, name, body = m.group(1), m.group(2), m.group(3)
        if name not in cond:
            return ""
        keep = cond[name] if sense == "?" else not cond[name]
        return body if keep else ""
    while True:
        text, k = c._BLOCK.subn(block, text)
        if not k:
            break
    return text


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", action="append", default=[], help="a config to check (repeatable); default: every character in characters.json")
    ap.add_argument("--all-roles", action="store_true", help="render roles whose section is switched off too")
    args = ap.parse_args(argv)
    targets = [(None, p) for p in args.config] or _configs_from_register()
    if not targets:
        print("nothing to check")
        return 1
    bad = 0
    for who, path in targets:
        holes, unread = check(path, who or "", all_roles=args.all_roles)
        bad += len(holes) + len(unread)
    if bad:
        print(f"{bad} hole(s) or missing prompt file(s): a token with no value renders as "
              f"'{PLACEHOLDER}' and the model fills it on its own")
        return 1
    print("every role of every character renders with no unfilled token")
    return 0


if __name__ == "__main__":
    sys.exit(main())
