#!/usr/bin/env python3
"""Run the leak-free build + gate for one or all five koikano subjects, hidden children.

    python tools/koikano/run_leak_free.py --out F:\\temp\\gate_split [--char 百花 ...]
    --full-dir <root>   root holding the full-corpus bibles (default: skipped); if given, <root>/<slug>/layers
                        is passed as --annot-dir (holdout lines' face/gesture tags only)

Per subject: koikano_bible.py --build-only --out <out>/<slug>, then
koikano_bible_gate.py --leak-free --bible-dir <out>/<slug>.  Prints the gate check lines.
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SUBJECTS = ["百花", "真優", "千奈", "アリス", "真里亜"]
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def run(cmd):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       creationflags=CREATE_NO_WINDOW, env=env)
    sys.stdout.buffer.write((r.stdout or "").encode("utf-8", "replace"))
    if r.returncode != 0:
        sys.stderr.write(r.stderr[-800:])
        raise SystemExit(r.returncode)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--char", action="append")
    ap.add_argument("--full-dir", default=None)
    ap.add_argument("--full", action="store_true", help="full-corpus build + gate instead (same markers), for the leak-free comparison")
    a = ap.parse_args()
    sys.path.insert(0, HERE)
    import koikano_bible as kb
    import markers_io
    for ch in a.char or SUBJECTS:
        slug = kb.SLUGS[ch]
        out = os.path.join(a.out, slug)
        if a.full:   # full-corpus control run: default builder (doc into <out>, never docs/) + same markers + default gate
            run([sys.executable, "-I", os.path.join(HERE, "koikano_bible.py"), "--char", ch, "--out", out,
                 "--doc", os.path.join(out, "bible_readable.md")])
        else:
            run([sys.executable, "-I", os.path.join(HERE, "koikano_bible.py"), "--char", ch, "--out", out, "--build-only"])
        n = markers_io.apply_to_dir(out, slug)   # the subject's own rule markers; none for 百花 (default 13)
        print("%s: %d own-rule markers applied to the %s bible" % (ch, n, "full-corpus" if a.full else "build-only"))
        cmd = [sys.executable, "-I", os.path.join(HERE, "koikano_bible_gate.py"), "--char", ch, "--bible-dir", out]
        if not a.full:
            cmd.append("--leak-free")
        if a.full_dir and not a.full:
            cmd += ["--annot-dir", os.path.join(a.full_dir, slug, "layers")]
        run(cmd)


if __name__ == "__main__":
    main()
