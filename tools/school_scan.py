"""One-off scan: school vocabulary in what the second character is sent.

Renders every role's prompt with her config and reports every line that holds a
fifteen-year-old's school day, the first character's household or cast, or the
phone-app sense of how she sees him. Kept because the same sweep is wanted
after any change to a shared mechanism prompt.

    python tools/school_scan.py            # her config
    python tools/school_scan.py --config config.json
"""
import argparse
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

from config import Config  # noqa: E402

SCHOOL = re.compile(
    r"\b(school|schools|schoolgirl|class|classes|classroom|classmate|classmates|homeroom"
    r"|lesson|lessons|teacher|teachers|homework|cram|club|clubs|uniform|uniforms|bell|bells"
    r"|recess|exam|exams|term|semester|fifteen|15|high school|desk|blazer|satchel"
    r"|pencil case|form room|assembly|playground|schoolyard|rooftop|gym class|prefect)\b"
    r"|cleaning duty|lunch break|between lessons|after school|school day|school gate"
    r"|学校|教室|授業|先生|宿題|部活|制服|クラス|高校|中学|女子高生|給食|掃除|放課後|期末|中間|塾|下校|登校|同級生|同僚|生徒|担任",
)
HOUSE = re.compile(r"\b(mother|mum|mom|father|dad|brother|sister|parents|household|family)\b", re.I)
APP = re.compile(r"(app on (her|your) phone|phone app|her phone|on her phone|the app\b|long[- ]distance)", re.I)


def names():
    try:
        import tools.character_names as cn  # noqa
    except Exception:
        cn = None
    out = []
    for mod in (cn,):
        for attr in ("NAMES", "PEOPLE", "FORBIDDEN"):
            v = getattr(mod, attr, None) if mod else None
            if isinstance(v, (list, tuple, set)):
                out += [str(x) for x in v]
    return sorted(set(out))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config_yukarin.json")
    args = ap.parse_args()
    cfg = Config(path=args.config)
    people = names()
    person = re.compile("|".join(re.escape(n) for n in people), re.I) if people else None

    seen, hits = {}, []
    models = json.load(io.open(args.config, encoding="utf-8")).get("models", {})
    for role in sorted(models):
        spec = models[role]
        if not isinstance(spec, dict) or not spec.get("prompt"):
            continue
        path = spec["prompt"]
        try:
            text = cfg.prompt_text(role)
        except Exception as e:
            print("  !! %-18s %s" % (role, e))
            continue
        if path in seen:
            continue
        seen[path] = role
        for i, line in enumerate(text.splitlines(), 1):
            for label, rx in (("school", SCHOOL), ("house", HOUSE), ("sight", APP)):
                m = rx.search(line)
                if m:
                    hits.append((path, role, i, label, m.group(0), line.strip()[:150]))
            if person:
                m = person.search(line)
                if m:
                    hits.append((path, role, i, "person", m.group(0), line.strip()[:150]))

    by = {}
    for path, role, i, label, hit, line in hits:
        by.setdefault(path, []).append((role, i, label, hit, line))
    for path in sorted(by):
        print("\n=== %s  (role %s)" % (path, by[path][0][0]))
        for role, i, label, hit, line in by[path]:
            print("  %s:%d [%s: %s] %s" % (path, i, label, hit, line))
    print("\n%d line(s) across %d file(s); %d prompt file(s) rendered"
          % (len(hits), len(by), len(seen)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
