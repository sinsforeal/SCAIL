"""Every module that asks for her character sheet has been decided about.

`Config.role_system` stops the process on a role with no row in
`Config.ROLE_STANCE`, but only when that role actually fires -- and a role
that runs once a week fires long after the edit that added it. This is the
same check made statically: find every `role_system("<role>")` call site in
the tree and refuse a role the table does not name.

Exit 1 and print the offenders, or exit 0 and print the tally. In
`tools/smoke.py`, so it fails at build time.
"""
import os
import re
import sys

CALL = re.compile(r"""role_system\(\s*["']([a-z_0-9]+)["']""")
SKIP_DIRS = {".git", "__pycache__", "data", "logs", "node_modules", "secerts",
             "venv", ".venv", "build", "dist"}


def call_sites(root="."):
    out = []
    for dirpath, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for name in names:
            if not name.endswith(".py"):
                continue
            path = os.path.join(dirpath, name)
            try:
                text = open(path, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            if "role_system(" not in text:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                for role in CALL.findall(line):
                    out.append((path.replace("\\", "/").lstrip("./"), i, role))
    return sorted(set(out))


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    sys.path.insert(0, os.path.abspath(root))
    from config import Config

    table = getattr(Config, "ROLE_STANCE", None)
    if not isinstance(table, dict) or not table:
        print("Config.ROLE_STANCE is missing or empty: nothing has decided which roles "
              "speak as her and which judge her")
        return 1

    sites = call_sites(root)
    missing = [(p, i, r) for p, i, r in sites if r not in table]
    if missing:
        print("%d call site(s) ask for her character sheet for a role Config.ROLE_STANCE does "
              "not name:" % len(missing))
        for p, i, r in missing:
            print("  %s:%d  role_system(%r)" % (p, i, r))
        print("Add each as 'voice' (the role writes her words) or 'judge' (the role decides "
              "something about her and gets no sheet).")
        return 1

    named = {r for _p, _i, r in sites}
    unused = sorted(set(table) - named)
    voice = sorted(r for r in named if table[r] == "voice")
    judge = sorted(r for r in named if table[r] == "judge")
    print("%d call site(s) over %d role(s): %d speak as her (%s); %d judge her and get no "
          "sheet (%s)" % (len(sites), len(named), len(voice), ", ".join(voice),
                          len(judge), ", ".join(judge)))
    if unused:
        print("rows naming a role nothing calls role_system for: " + ", ".join(unused))
    return 0


if __name__ == "__main__":
    sys.exit(main())
