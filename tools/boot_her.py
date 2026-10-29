"""Construct the whole App as HER and report what breaks.

`tools/smoke.py` does this for the character the machinery was written around.
This does it for a second one, so "which modules have to be gated on
`existence`" stops being a list I reasoned out from module names and becomes a
list of things that actually failed.

It never touches a live save: her database is created fresh in a temp file,
`--console` and `--no-sensors` are forced, and nothing reaches Telegram, the
app or the sensors.

    python tools/boot_her.py --config config_yukarin.json
"""

import argparse
import io
import os
import sys
import tempfile
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", default="config_yukarin.json")
    args = ap.parse_args()

    tmp = os.path.join(tempfile.gettempdir(), "boot_her.db")
    for suffix in ("", "-wal", "-shm", ".lock"):
        try:
            os.remove(tmp + suffix)
        except OSError:
            pass

    import scail
    argv = sys.argv
    sys.argv = ["scail.py", "--console", "--no-sensors", "--config", args.config, "--db", tmp]
    try:
        real_args = scail.parse_args()
    finally:
        sys.argv = argv

    print("[boot] constructing the App with %s\n" % args.config)
    try:
        app = scail.App(real_args)
    except Exception:
        print("FAILED to construct:\n")
        traceback.print_exc()
        print("\nThat traceback names the first module that assumes something she is not.")
        return 1

    print("\n[boot] constructed. Now the reports, one at a time -- a failure here is a")
    print("       module reading something she does not have.\n")
    checks = [
        ("state.wiring_report", lambda: app.state.wiring_report()),
        ("state.affect_report", lambda: app.state.affect_report()),
        ("state.system_prompt", lambda: app.state.system_prompt()),
        ("state.mood_tags", lambda: app.state.mood_tags()),
        ("persona._system (her whole prompt)", lambda: app.persona._system()),
        ("persona.system_for('him')", lambda: app.persona.system_for("him")),
    ]
    for name in ("goals", "situation", "ledger", "health", "body", "cast", "social", "schedule"):
        obj = getattr(app, name, None)
        if obj is None:
            checks.append((name + " (not constructed)", lambda: "absent"))
            continue
        # a subsystem her existence switched off is not called by the App, so
        # calling it here would test something that never runs -- and it was
        # doing exactly that, giving a woman with no body a menstrual cycle
        sect = getattr(app.config, name, None)
        if sect is not None and getattr(sect, "enabled", True) is False:
            checks.append(("%s (off: her existence)" % name, lambda: "off"))
            continue
        for meth in ("report", "line", "text", "brief"):
            if hasattr(obj, meth):
                checks.append(("%s.%s" % (name, meth), (lambda o=obj, m=meth: getattr(o, m)())))
                break

    bad = []
    for label, fn in checks:
        try:
            out = fn()
            n = len(out) if isinstance(out, str) else 0
            print("  ok    %-38s %s" % (label, ("%d chars" % n) if n else ""))
        except Exception as e:
            bad.append((label, e))
            print("  FAIL  %-38s %s: %s" % (label, type(e).__name__, str(e)[:90]))

    print()
    if bad:
        print("%d failed. Each is a module that has to be gated on `existence`," % len(bad))
        print("or read something her sheet says she does not have:")
        for label, e in bad:
            print("  - %-36s %s" % (label, type(e).__name__))
        return 1
    print("nothing failed. She constructs and reports as she is.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
