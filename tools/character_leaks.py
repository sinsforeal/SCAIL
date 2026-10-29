"""Names in a character's run that are not in that character's record.

Every fault of the second character's first boot was the same fault: a
subsystem wrote content about somebody else's life, and it was found by a
person reading the log. She was given a school day in a ward she does not live
in, friends the roster has never heard of, gossip about a teacher at a school
she does not attend. All of them share one property a machine can check --
**they name a person or a place that is nowhere in her record.**

`tools/prompt_leaks.py` does this for the prompts, before anything runs.
This does it for what a run actually produced. Between them they cover the two
ways one character's material reaches another: written into the instructions,
and written into the output.

What counts as hers: her sheet, her cast file, her roster, her beliefs, her
neutral fills, her own prompt files, her save's own people, the peers her
config names, and every name another character actually said to her (only
their turns, never hers: she may repeat what she was told and may not know
what she was not). Anything else
that looks like a name -- a run of kanji, a capitalised word, a place suffix --
is reported with the line it appeared in, for a person to judge. It is a flag,
never a rewrite, and it is deliberately noisy in the direction of showing too
much: a false positive costs a glance, a missed one costs a character.

A run is not the only thing that produces text about a character. A prompt
assembled by a harness, a reply regenerated off an old prompt, a persona card
written from a corpus -- each is output about her, and each was written by
somebody who had to reimplement this loop to check it, because the only way in
was a run directory. `--text` and `--out` are that way in: the same record,
the same two regexes, the same whole-name comparison, over a string or over
the files of a directory instead of over `session.log`.

    python tools/character_leaks.py                          # the newest run
    python tools/character_leaks.py --config config_yukarin.json
    python tools/character_leaks.py --log logs/2026-09-01_18-01-08
    python tools/character_leaks.py --top 40
    python tools/character_leaks.py --out asumin/harness/out/prompts/records_only
    python tools/character_leaks.py --out reply.md --out notes.txt
    python tools/character_leaks.py --text "the reply to check"
"""

import argparse
import collections
import glob
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

# A kanji run of two or more, or a katakana run of three or more: the shapes a
# Japanese name or place takes. Hiragana is excluded -- it is grammar far more
# often than it is a name, and the noise would swamp the signal.
JA = re.compile(r"[\u4e00-\u9fff]{2,}|[\u30a0-\u30ff\u30fc]{3,}")
EN = re.compile(r"\b[A-Z][a-z]{2,}(?:[- ][A-Z][a-z]{2,})*\b")

# Words that are capitalised because they start a sentence or are ordinary
# English, not because they name anybody. Kept short on purpose: a name wrongly
# on this list is a name this tool stops being able to see.
STOP = set("""The This That These Those There Their They Then Than And But For Nor Yet So
When While Where What Which Who Whom Whose Why How If Because Since Although Though
She Her Hers He His Him It Its They Them We Us You Your I My Mine
Not No Yes Maybe Nothing Nobody Something Someone Anything Anyone Everything Everyone
One Two Three Four Five Six Seven Eight Nine Ten
Monday Tuesday Wednesday Thursday Friday Saturday Sunday
January February March April May June July August September October November December
Today Tomorrow Yesterday Morning Afternoon Evening Night Now Later Soon Still Just
About After Again Against Almost Alone Already Also Always Another Any Around
Back Been Before Being Both Come Could Did Does Doing Done Down During Each Even Ever
Every First From Get Give Going Good Had Has Have Having Here Hour Into Keep Kept
Last Left Less Let Like Little Long Look Made Make Many More Most Much Must Near Need
Never New Next Once Only Open Other Out Over Own Part Past Put Read Real Right Said
Same Saw Say Says Second See Seen Set Should Show Side Small Some Sort Still Stop
Sure Take Tell Thing Think Time Told Too Took Turn Under Until Very Want Was Way Well
Went Were Will With Without Word Work Would Write Written Year
Yeah Yep Okay Oleh Oh Ah Hmm Well Actually Anyway Basically Probably Perhaps
""".split())

# Log tags whose text is machinery, not content about her life. A path, a model
# name and a provider are not leaks.
SKIP_TAGS = {"boot", "llm", "voice", "backup", "config", "primitives", "netwatch",
             "ab", "talkapp", "telegram", "vision", "TTS", "loop", "singleton",
             "store", "japan", "hazards", "sensors", "status",
             # the sensor daemons announce themselves in their own words
             "GELBOORU", "SYSMON", "TELEMETRY", "MAL", "WATCH"}
TAG = re.compile(r"^\[\d\d:\d\d:\d\d\]\s+\[([^\]]+)\]\s*(.*)$")


def _strings(o, out):
    if isinstance(o, str):
        out.append(o)
    elif isinstance(o, dict):
        for k, v in o.items():
            out.append(str(k))
            _strings(v, out)
    elif isinstance(o, (list, tuple)):
        for v in o:
            _strings(v, out)


def _peer_said(cfg):
    """Every message another character sent her, out of her own save, without
    opening it for writing.

    A file copy of a live sqlite database returns a stale image, so this is a
    read-only URI connection on the save itself; a save that is not there, or
    has never held a peer conversation, gives nothing back and nothing about
    the report changes."""
    path = getattr(cfg.logging, "db_path", "") or ""
    if not path or not os.path.exists(path):
        return []
    out = []
    try:
        import sqlite3
        conn = sqlite3.connect("file:%s?mode=ro" % path.replace("\\", "/"), uri=True, timeout=5)
        try:
            mine = str(getattr(cfg.character, "name", "") or "")
            for key in ("peer_chat", "peer_live"):
                r = conn.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
                if not r or not r[0]:
                    continue
                rows = json.loads(r[0])
                if isinstance(rows, dict):
                    rows = [rows]
                for x in rows or []:
                    if not isinstance(x, dict):
                        continue
                    for t in (x.get("turns") or []):
                        if str(t.get("who") or "") == mine:
                            continue
                        out.append(str(t.get("ja") or t.get("text") or ""))
        finally:
            conn.close()
    except Exception as e:
        print("  (what a peer said was not read: %s)" % type(e).__name__)
    return out


def known(cfg):
    """Every name the character's own record contains."""
    ch = cfg.character
    texts = []
    for attr in ("character_file", "cast_file", "beliefs_file", "self_beliefs_file",
                 "voice_rules_file", "neutral_file",
                 # her own circle, whom the world's roster does not have, and
                 # her own record. Her record is the largest thing she knows
                 # about herself: a second character born in the same
                 # prefecture had her own birthplace read as somebody else's
                 # material, because the only files consulted here were the
                 # generated ones.
                 "own_cast_file", "memories_file", "timeline_file"):
        p = getattr(ch, attr, "")
        if p and os.path.exists(p):
            try:
                _strings(json.load(io.open(p, encoding="utf-8")), texts)
            except ValueError:
                texts.append(io.open(p, encoding="utf-8").read())
    for attr in ("file", "memory_file", "triggers_file", "memory_triggers_file"):
        p = getattr(getattr(cfg, "lore", None), attr, "")
        if p and os.path.exists(p):
            try:
                _strings(json.load(io.open(p, encoding="utf-8")), texts)
            except ValueError:
                pass
    for p in (getattr(ch, "style_prompt", ""), getattr(ch, "style_ja_prompt", ""),
              # her voice. It has no key of its own: it is the persona role's
              # prompt, and the key this used to read does not exist, so her
              # bible had never been part of her own record here.
              str(((cfg.raw.get("models") or {}).get("persona") or {}).get("prompt") or "")):
        if p and os.path.exists(p):
            texts.append(io.open(p, encoding="utf-8").read())
    for d in (getattr(ch, "cast_sheets_dir", ""), getattr(ch, "own_cast_sheets_dir", "")):
        if d and os.path.isdir(d):
            for f in glob.glob(os.path.join(d, "*")):
                try:
                    texts.append(io.open(f, encoding="utf-8").read())
                except OSError:
                    pass
    # what her world has actually announced is hers too: the ward events and
    # the national feed are fetched, not authored, so their names are in no
    # sheet and every one of them read as a leak on the first character
    for attr in ("local_events_file", "zeitgeist_file", "holidays_file",
                 "school_calendar_file", "places_file", "geography_file",
                 "household_file", "taste_file", "home_file"):
        p = getattr(cfg.world, attr, "")
        if p and os.path.exists(p):
            try:
                _strings(json.load(io.open(p, encoding="utf-8")), texts)
            except ValueError:
                pass
    # Who she is configured to write to, and what they have actually said to
    # her. A peer contact is part of her record the way her cast file is: she
    # is meant to know that person. And a name inside a message another
    # character SENT her is quotable the moment it arrives -- which is exactly
    # the boundary this check has to draw, because the one thing peer talk
    # must not become is a way for one character's life to turn up in the
    # other's mouth unprompted. Only the peer's turns are read: a name she
    # produced herself is not made hers by her having produced it.
    for row in (getattr(getattr(cfg, "peer_talk", None), "contacts", None) or []):
        if isinstance(row, dict):
            texts += [str(row.get("name") or ""), str(row.get("id") or "")]
    texts += _peer_said(cfg)
    texts += [ch.name, getattr(ch, "name_ja", ""), getattr(ch, "reading_ja", "")]
    blob = "\n".join(t for t in texts if t)
    return set(JA.findall(blob)) | set(EN.findall(blob))


def newest_log(cfg):
    """The newest run of THIS character.

    Two bots write into one `logs/`, so "the newest directory" is whichever of
    them restarted last and reading it under the other one's record reports
    every name in it. A run says whose it is in the line where it registers
    with the hub; a console run does not register, so it falls back to the
    newest of all and says so by printing which run it read.
    """
    ds = sorted((d for d in glob.glob(os.path.join("logs", "*")) if os.path.isdir(d)),
                key=os.path.getmtime, reverse=True)
    want = "registered '%s'" % "".join(cfg.character.name.lower().split())
    for d in ds:
        p = os.path.join(d, "session.log")
        if not os.path.exists(p):
            continue
        head = io.open(p, encoding="utf-8", errors="replace").read(4000)
        if want in head:
            return d
    return ds[0] if ds else ""


READABLE = (".md", ".txt", ".json", ".jsonl", ".log", ".csv", ".py")


def from_log(path):
    """The content lines of a run: the tagged lines, machinery skipped.

    Returns the lines and how many came from each subsystem."""
    lines, tags = [], collections.Counter()
    for raw in io.open(path, encoding="utf-8", errors="replace"):
        m = TAG.match(raw.rstrip("\n"))
        if not m:
            continue
        tag, text = m.group(1), m.group(2)
        head = tag.split()[0].split(":")[0]
        if head in SKIP_TAGS:
            continue
        tags[head] += 1
        lines.append(text)
    return lines, tags


def from_files(paths):
    """The lines of files, or of every readable file under a directory.

    No tag to skip and nothing to strip: a harness's prompt, a card, a
    regenerated reply and a report are all content by construction, which is
    the point of reading them at all."""
    lines, tags = [], collections.Counter()
    for p in paths:
        if os.path.isdir(p):
            found = sorted(f for f in glob.glob(os.path.join(p, "**", "*"), recursive=True)
                           if os.path.isfile(f) and os.path.splitext(f)[1].lower() in READABLE)
        else:
            found = [p]
        for f in found:
            try:
                body = io.open(f, encoding="utf-8", errors="replace").read().splitlines()
            except OSError as e:
                print("  (%s not read: %s)" % (f, type(e).__name__))
                continue
            lines += body
            tags[os.path.relpath(f)] += len(body)
    return lines, tags


def scan(lines, mine):
    """Every name in these lines that is not in her record, with where it
    appeared. The comparison is whole-name against whole-name: `mine` is
    extracted from her record by these same two regexes. It was briefly
    `name in blob`, a substring test, which is the fault this project has now
    paid for eight times -- "Rena" is inside a longer word in her sheet and
    vanished from the report."""
    hits = collections.defaultdict(list)
    for text in lines:
        # a file path or a URL is not somebody's name
        text = re.sub(r"\S+[\\/]\S+|https?://\S+", " ", text)
        for name in set(JA.findall(text)) | set(EN.findall(text)):
            if name in mine or name in STOP:
                continue
            if len(hits[name]) < 2:
                hits[name].append(text.strip()[:150])
            else:
                hits[name].append("")
    return hits


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", default="config_yukarin.json")
    ap.add_argument("--log", default="", help="a run directory; the newest by default")
    ap.add_argument("--out", action="append", default=[],
                    help="a file, or a directory of files, of output about her instead of a run")
    ap.add_argument("--text", default="", help="one string of output about her instead of a run")
    ap.add_argument("--top", type=int, default=25, help="how many names to show")
    args = ap.parse_args()

    from config import Config
    cfg = Config(path=args.config)
    mine = known(cfg)

    if args.out or args.text:
        lines, tags = from_files(args.out) if args.out else ([], collections.Counter())
        if args.text:
            body = args.text.splitlines()
            lines += body
            tags["(the text given)"] += len(body)
        source = ", ".join(args.out) if args.out else "the text given"
        what = "WHAT WAS READ (file: lines)"
    else:
        run = args.log or newest_log(cfg)
        path = os.path.join(run, "session.log")
        if not os.path.exists(path):
            raise SystemExit("no session.log in %s" % run)
        lines, tags = from_log(path)
        source = "run " + os.path.basename(run.rstrip("/\\"))
        what = "WHAT RAN (subsystem: lines)"

    hits = scan(lines, mine)

    print("\n  %s, %s" % (cfg.character.name, source))
    print("  existence: embodied=%s in_world=%s sees_him=%s"
          % (cfg.character.existence.embodied, cfg.character.existence.in_world,
             cfg.character.existence.sees_him))
    print("  %d content lines from %d source(s); %d names in her own record"
          % (len(lines), len(tags), len(mine)))

    print("\n  " + what)
    print("  " + ", ".join("%s %d" % (k, v) for k, v in tags.most_common(20))
          + (", and %d more" % (len(tags) - 20) if len(tags) > 20 else ""))

    if not hits:
        print("\n  no name outside her record. Nothing to read.\n")
        return 0

    order = sorted(hits.items(), key=lambda kv: -len(kv[1]))
    print("\n  NAMES NOT IN HER RECORD (%d distinct, most frequent first)" % len(order))
    print("  Each is a flag for a person to judge, not a fault by itself.\n")
    for name, where in order[:args.top]:
        print("  %-22s x%-3d %s" % (name, len(where), where[0]))
        if len(where) > 1 and where[1]:
            print("  %-22s      %s" % ("", where[1]))
    if len(order) > args.top:
        print("\n  ... and %d more (--top)" % (len(order) - args.top))
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
