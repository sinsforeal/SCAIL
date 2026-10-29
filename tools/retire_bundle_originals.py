"""Move each character's material out of the place it used to live, once every
process is reading it from her bundle.

The bundle move COPIES and repoints and takes nothing away
(`docs/bundle.md`). It has to: six processes are running when it happens, and
each of them reads a path per call -- the roster on the first read of the day,
the household on every world-facing call, a prompt on its mtime -- so a file
that disappears mid-day is a crash or a silent blank.

This is the other half, and it runs AFTER the restart. It refuses to move
anything unless both of these are true for every registered character:

  * no config on disk still names the old path, and
  * her process started after her config was repointed, so the process in
    memory is reading the bundle and not the old place.

What it moves goes to `data/retired/<stamp>_bundle_originals/`, keeping its
path under it, and nothing is ever deleted.

    python tools/retire_bundle_originals.py            # check and say
    python tools/retire_bundle_originals.py --apply    # check, then move
"""
import argparse
import datetime
import io
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

from tools import isolation, registry  # noqa: E402


def _configs():
    """Every config file on disk, as a flat map of path-shaped values."""
    out = {}
    import glob
    for p in sorted(set(["config.json"] + glob.glob("config_*.json"))):
        try:
            with io.open(p, encoding="utf-8") as f:
                out[p] = isolation.paths(json.load(f))
        except (OSError, ValueError):
            continue
    return out


def _running():
    """[(command line, started)] for every python process on this machine.

    Read through PowerShell's process table rather than by image name: this
    project has killed a program out of another program that way once."""
    ps = ("Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'py*' } | "
          "Select-Object CommandLine,CreationDate | ConvertTo-Json -Compress")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=60)
        rows = json.loads(r.stdout or "[]")
    except Exception as e:                                        # noqa: BLE001
        print("  could not read the process table (%s): every start time is unknown"
              % type(e).__name__)
        return None
    if isinstance(rows, dict):
        rows = [rows]
    out = []
    for row in rows or []:
        cl = str((row or {}).get("CommandLine") or "")
        when = str((row or {}).get("CreationDate") or "")
        if not cl:
            continue
        # PowerShell renders a CIM date as `/Date(<milliseconds>)/`; the
        # WMI shape (yyyymmddHHMMSS) is read too, so this keeps working if the
        # command is ever changed to `wmic`
        ts = None
        ms = re.search(r"/Date\((-?\d+)", when)
        if ms:
            ts = int(ms.group(1)) / 1000.0
        else:
            m = re.search(r"(\d{4})-?(\d\d)-?(\d\d)[T ]?(\d\d):?(\d\d):?(\d\d)", when)
            if m:
                ts = datetime.datetime(*(int(x) for x in m.groups())).timestamp()
        out.append((cl, ts))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true", help="move the originals")
    args = ap.parse_args()

    rows = registry.characters()
    cfgs = _configs()
    procs = _running()

    plan, blocked = [], []
    for r in rows:
        key = r["key"]
        man = registry.bundles().get(key) or {}
        origins = man.get("origins") or {}
        if not origins:
            blocked.append("%s: her manifest records no origins, so there is nothing to move "
                           "and nothing to check" % key)
            continue

        # 1. her process started after her config was repointed
        cfg_mtime = os.path.getmtime(r["config"]) if os.path.exists(r["config"]) else 0
        if procs is None:
            blocked.append("%s: the process table could not be read" % key)
        else:
            pat = re.compile(r["match"])
            mine = [(cl, ts) for cl, ts in procs if pat.search(cl)]
            if not mine:
                blocked.append("%s: no process matches %r -- she is not running, so nothing "
                               "proves the bundle is what she reads" % (key, r["match"]))
            elif any(ts is None for _cl, ts in mine):
                blocked.append("%s: her process has no readable start time" % key)
            elif min(ts for _cl, ts in mine) < cfg_mtime:
                blocked.append("%s: her process started %s, before her config was repointed at "
                               "%s -- it is still reading the old paths"
                               % (key,
                                  datetime.datetime.fromtimestamp(
                                      min(ts for _cl, ts in mine)).strftime("%Y-%m-%d %H:%M"),
                                  datetime.datetime.fromtimestamp(cfg_mtime).strftime("%Y-%m-%d %H:%M")))

        for name, old in sorted(origins.items()):
            new = os.path.join("characters", key, name)
            if not os.path.exists(old):
                continue
            if not os.path.exists(new):
                blocked.append("%s: %s is not in her bundle, so %s must stay" % (key, name, old))
                continue
            # 2. nobody's config still names it
            named = ["%s:%s" % (p, k) for p, P in cfgs.items()
                     for k, v in P.items()
                     if os.path.abspath(v) == os.path.abspath(old)]
            if named:
                blocked.append("%s: %s is still named by %s" % (key, old, ", ".join(named)))
                continue
            plan.append((key, old, new))

    print("[bundle] %d original(s) ready to move, %d thing(s) in the way" % (len(plan), len(blocked)))
    for b in blocked:
        print("   NOT YET  " + b)
    for key, old, new in plan:
        print("   move     %-52s (it is %s)" % (old, new))
    if blocked:
        print("\nNothing was moved. Restart first (`restart.cmd all`), then run this again.")
        return 1
    if not args.apply:
        print("\nNothing was moved. `--apply` moves them.")
        return 0

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    out = os.path.join("data", "retired", stamp + "_bundle_originals")
    for key, old, _new in plan:
        dst = os.path.join(out, old.replace("\\", "/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(old, dst)
        print("   moved    %s -> %s" % (old, dst))
    with io.open(os.path.join(out, "WHY.md"), "w", encoding="utf-8") as f:
        f.write("# The places each character's material used to live\n\n"
                "Moved by `tools/retire_bundle_originals.py` once every process was reading it "
                "from `characters/<key>/` instead. Each file is byte-identical to the copy in "
                "her bundle, except her sheet, whose record paths were repointed at the bundle "
                "when it was made.\n\n")
        for key, old, new in plan:
            f.write("- `%s` -> `%s` (%s)\n" % (old, new, key))
    print("\n%d original(s) moved to %s" % (len(plan), out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
