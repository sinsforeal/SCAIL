"""Blocks of code that appear twice in a row.

A patch script that writes per edit, is not idempotent, and gets re-run after a
partial failure duplicates its inserts. It has happened four times in this
project: the sentiment config, the contagion block, the `longing` gauge, and
`State.update_from_llm`'s `catch_his_mood` -- which then ran the contagion at
double the configured strength for a day and raised nothing at all, because a
doubled block is valid Python that imports, parses, constructs and runs.

Nothing else here can see it. `ast.parse` is happy, the import is happy, and
building the whole App is happy. The signature is simple though: N consecutive
lines immediately followed by the same N lines.

A block only counts if it does something -- two lines of substance, one of
which calls or assigns -- so a pair of identical `parts.append("")` stays a
layout idiom rather than a finding.

    python tools/dupscan.py [path ...]

`tools/smoke.py` runs this on every check.
"""
import ast
import io
import os
import sys

MAX_BLOCK = 10
SKIP_DIRS = {"logs", "data", "secerts", "__pycache__", "retired", "tmp", "var"}  # tmp/: agent worktrees, incl. other repos
_QUOTES = (chr(34) * 3, chr(39) * 3)


def _trivial(line):
    t = line.strip()
    if not t or t.startswith("#") or t.startswith(_QUOTES):
        return True
    return t in ("}", "]", ")", "})", "],", "),", "else:", "try:", "pass", "continue", "return")


def scan_file(path):
    """[(line_no, block_length, first_line)] for every immediately repeated block."""
    try:
        lines = io.open(path, encoding="utf-8", errors="replace").read().splitlines()
    except OSError:
        return []
    out = []
    i = 0
    while i < len(lines):
        hit = 0
        for length in range(MAX_BLOCK, 1, -1):
            if i + 2 * length > len(lines):
                continue
            if lines[i:i + length] != lines[i + length:i + 2 * length]:
                continue
            body = [x for x in lines[i:i + length] if not _trivial(x)]
            if len(body) < 2 or not any("(" in x or "=" in x for x in body):
                continue
            hit = length
            break
        if hit:
            out.append((i + 1, hit, lines[i].strip()))
            i += 2 * hit
        else:
            i += 1
    return out


def scan(root="."):
    """[(path, line_no, block_length, first_line)] over every .py under root."""
    out = []
    for base, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for n in sorted(names):
            if n.endswith(".py"):
                path = os.path.join(base, n)
                for line_no, length, first in scan_file(path):
                    out.append((path, line_no, length, first))
    return out


# ------------------------------------------------ the same def, twice, apart

# The block scan above needs the two copies to touch. `llm.py` carried three
# methods defined twice with identical bodies and sixty lines between the
# copies: the second won, the first was unreachable, and every check in the
# project was happy -- it parses, it imports, it builds. So the second pass
# parses instead of comparing lines, and asks a different question: is any
# name defined twice in one class or one module?
#
# A property and its setter answer to one name on purpose, and so does an
# `@overload` stub, so a decorator that says which of the two this is exempts
# it. The walk stops at class scope: a helper redefined inside one function
# body is a local idiom, not a copy nobody can reach.
_KEEPS_ITS_NAME = ("setter", "getter", "deleter", "overload", "register",
                   "singledispatch", "singledispatchmethod")


def _decorator_names(fn):
    out = []
    for d in fn.decorator_list:
        node = d.func if isinstance(d, ast.Call) else d
        if isinstance(node, ast.Attribute):
            out.append(node.attr)
        elif isinstance(node, ast.Name):
            out.append(node.id)
    return out


def redefinitions(path):
    """[(line of the first, line of the second, scope, name, "identical" or
    "different")] for every function defined twice in one class or module."""
    try:
        src = io.open(path, encoding="utf-8", errors="replace").read()
        tree = ast.parse(src)
    except (OSError, SyntaxError, ValueError):
        return []
    out = []

    def scope(node, where):
        seen = {}
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not any(n in _KEEPS_ITS_NAME for n in _decorator_names(child)):
                    body = "|".join(ast.dump(s) for s in child.body)
                    if child.name in seen:
                        first_line, first_body = seen[child.name]
                        out.append((first_line, child.lineno, where or "the module", child.name,
                                    "identical" if first_body == body else "different"))
                    else:
                        seen[child.name] = (child.lineno, body)
            elif isinstance(child, ast.ClassDef):
                scope(child, (where + "." if where else "") + child.name)

    scope(tree, "")
    return out


def scan_redefinitions(root="."):
    """[(path, first, second, scope, name, how)] over every .py under root."""
    out = []
    for base, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for n in sorted(names):
            if n.endswith(".py"):
                path = os.path.join(base, n)
                for row in redefinitions(path):
                    out.append((path,) + row)
    return out


def main():
    roots = sys.argv[1:] or ["."]
    found = []
    again = []
    for r in roots:
        found += scan(r) if os.path.isdir(r) else [(r,) + h for h in scan_file(r)]
        again += (scan_redefinitions(r) if os.path.isdir(r)
                  else [(r,) + h for h in redefinitions(r)])
    for path, line_no, length, first in found:
        print(f"{path}:{line_no}  {length} line(s) repeated immediately: {first[:80]}")
    for path, first_line, second_line, where, name, how in again:
        print(f"{path}:{second_line}  {name} is defined again in {where} "
              f"(the first is at :{first_line}, {how} body); the first can never run")
    print(f"\n{len(found)} duplicated block(s)" if found else "\nno duplicated blocks")
    print(f"{len(again)} name(s) defined twice in one scope" if again
          else "no name defined twice in one scope")
    return 1 if (found or again) else 0


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.exit(main())
