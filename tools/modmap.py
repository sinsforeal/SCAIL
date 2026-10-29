"""One page of what every module is, read off the code: `docs/modmap.md`.

The project is ninety-odd modules in five packages plus two programs, and
the question a reader has before touching one -- what is it, who owns it,
what does it read, who hands it its collaborators, which check covers it,
where is its spec -- was answered by reading it. This writes the answer as a
table, from the source, so that it is never stale by more than a run:

    module          the file, with its line count
    kind            shared (the mind library), program (one character's),
                    machine (his machine's sensors), runtime, tools
    what            the first line of its docstring
    wires           the collaborators it declares in WIRES (sim/wiring.py)
    config          the config sections it reads (`config.<section>` /
                    `c.<section>` / `self.config.<section>`)
    roles           the model roles it calls: the role name given to the
                    client's call, to the prompt loader or to the
                    role-system builder
    kv              the kv keys it reads and writes (`store.get("k")`,
                    `store.set("k")`), counted
    spec            `docs/<module>.md` if one exists
    checks          the `tools/*` scripts that name the file

Generated; `tools/docs_check.py` resolves every path in it.

    python tools/modmap.py             # writes docs/modmap.md
    python tools/modmap.py --print
"""
import argparse
import ast
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

OUT = os.path.join("docs", "modmap.md")
PACKAGES = [
    ("", "runtime"), ("sim", "shared"), ("persona", "shared"), ("embodied", "shared"),
    ("world", "shared"), ("machine", "machine"), ("sensors", "machine"), ("channels", "runtime"),
    ("talkapp", "runtime"), ("tomoe", "program"), ("tomoe/world", "program"), ("resident", "program"),
]
_CFG = re.compile(r"\b(?:self\.config|config|\bc)\.([a-z_][a-z0-9_]*)\b")
_ROLE = re.compile(r"\b(?:call_json|call|prompt_text|role_system)\(\s*\"([a-z_0-9]+)\"")
_KV_R = re.compile(r"store\.get\(\s*\"([a-z_0-9]+)\"")
_KV_W = re.compile(r"store\.set\(\s*\"([a-z_0-9]+)\"")


def _files():
    for d, kind in PACKAGES:
        base = d or "."
        # SCAILV4 runs one resident and no world program: a package that is
        # not in this tree (`tomoe`, `tomoe/world`) is simply absent, not an
        # error. A missing directory is skipped the way an absent module is.
        if not os.path.isdir(base):
            continue
        for f in sorted(os.listdir(base)):
            if f.endswith(".py") and not f.startswith("_"):
                yield (os.path.join(d, f) if d else f).replace("\\", "/"), kind


def _wires(tree):
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for st in node.body:
                if isinstance(st, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "WIRES" for t in st.targets):
                    try:
                        vals = ast.literal_eval(st.value)
                        out.append((node.name, tuple(vals) if isinstance(vals, (tuple, list)) else (vals,)))
                    except (ValueError, SyntaxError):
                        out.append((node.name, ("?",)))
    return out


def _sections():
    """The config's section names, so `c.something` that is not a section is
    not reported as one."""
    try:
        with open("config.py", encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "DEFAULTS" for t in node.targets):
                return {k.value for k in node.value.keys if isinstance(k, ast.Constant)}
    except (OSError, SyntaxError):
        pass
    return set()


def _checks_naming():
    """tool -> set of source files it names by path."""
    out = {}
    for f in sorted(os.listdir("tools")):
        if not f.endswith(".py"):
            continue
        try:
            with open(os.path.join("tools", f), encoding="utf-8") as fh:
                src = fh.read()
        except OSError:
            continue
        names = set(re.findall(r"[\"'`]((?:sim|persona|embodied|world|machine|sensors|channels|talkapp|tomoe|resident)/[a-z_0-9/]+\.py|scail\.py|config\.py|llm\.py|store\.py)[\"'`]", src))
        if names:
            out[f] = names
    return out


def rows():
    sections = _sections()
    naming = _checks_naming()
    out = []
    for path, kind in _files():
        try:
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
            tree = ast.parse(src)
        except (OSError, SyntaxError):
            continue
        doc = (ast.get_docstring(tree) or "").strip().split("\n")[0].strip()
        doc = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "(dated)", doc)
        lines = src.count("\n") + 1
        wires = _wires(tree)
        cfg = sorted({s for s in _CFG.findall(src) if s in sections})
        roles = sorted(set(_ROLE.findall(src)))
        kvr, kvw = set(_KV_R.findall(src)), set(_KV_W.findall(src))
        stem = os.path.splitext(os.path.basename(path))[0]
        spec = f"docs/{stem}.md" if os.path.exists(f"docs/{stem}.md") else ""
        checks = sorted(t for t, names in naming.items() if path in names)
        out.append(dict(path=path, kind=kind, lines=lines, doc=doc, wires=wires, cfg=cfg, roles=roles,
                        kvr=len(kvr), kvw=len(kvw), spec=spec, checks=checks))
    return out


def render():
    rs = rows()
    by_kind = {}
    for r in rs:
        by_kind.setdefault(r["kind"], []).append(r)
    lines = ["# The module map", "",
             "<!-- doc: generated by tools/modmap.py; edit the code, not this file -->", "",
             "Every module in the live tree, read off the source: what it is, what it reads,",
             "what it declares it is handed (`sim/wiring.py`), which model roles it calls, and",
             "which tools name it. A module with a spec has it under `docs/`; one with no",
             "check naming it is covered only by the whole-App build in `tools/smoke.py`.", "",
             f"{len(rs)} modules, {sum(r['lines'] for r in rs):,} lines.", ""]
    order = ["runtime", "shared", "machine", "program"]
    titles = {"runtime": "The runtime, the channels and the hub", "shared": "The mind library (shared by every character)",
              "machine": "His machine (shared, the machine's own)", "program": "The programs (one character's each)"}
    for kind in order:
        if kind not in by_kind:
            continue
        lines += [f"## {titles[kind]}", "",
                  "| module | lines | what | wires | config | roles | kv r/w | spec | checks |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for r in by_kind[kind]:
            wires = "; ".join(f"{cls}: {', '.join(w)}" for cls, w in r["wires"]) if r["wires"] else ""
            lines.append("| `%s` | %d | %s | %s | %s | %s | %d/%d | %s | %s |" % (
                r["path"], r["lines"], r["doc"].replace("|", "/")[:90], wires.replace("|", "/")[:120],
                ", ".join(r["cfg"])[:120], ", ".join(r["roles"])[:100], r["kvr"], r["kvw"],
                f"`{r['spec']}`" if r["spec"] else "", ", ".join(f"`tools/{c}`" for c in r["checks"])[:160]))
        lines.append("")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--print", action="store_true")
    args = ap.parse_args(argv)
    text = render()
    if args.print:
        print(text)
        return 0
    old = ""
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as fh:
            old = fh.read()
    if old != text:
        with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        print(f"wrote {OUT}")
    else:
        print(f"{OUT} unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
