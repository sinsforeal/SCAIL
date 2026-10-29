"""The readable view of what is known about an episode, on disk.

One Markdown file per (work, episode) under `recap.episodes_report_dir`,
written the moment an episode account lands, plus one index over all of them.
It is the same material `sim/episode_account.py` puts in the machine's store --
the account, the scenes in order, the sources it was merged from and how
complete it came out -- laid out for somebody reading it rather than for a
prompt.

**It is the MACHINE's, not a character's** (`tools/isolation.py`). An episode
of a television programme is the same episode whoever watched it: nothing here
is anybody's reading of it, nothing here is dated to a character's clock, and
one copy serves every character on the machine. What each of them made of the
episode stays in her own save.

Nothing in here fetches anything and nothing in here is a model call.

spec: docs/recap.md section 3e
"""
import json
import os
import re
import time
import urllib.parse

import logger

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")

# how far the level words go, worst first, so the index can sort on them
LEVELS = ("thin", "read-up", "watched")

LEVEL_WORDS = {
    "watched": "watched -- every scene in order, from several sources merged",
    "read-up": "read up -- the shape of the episode, from fewer sources",
    "thin": "thin -- one source, or one that carried little",
}


def slug(name, fallback=""):
    """A directory name for a show. Latin letters where the title has them and
    the fallback otherwise, so a Japanese-only title still gets a directory a
    person can type."""
    s = _SAFE.sub("-", str(name or "")).strip("-")[:60]
    return s or _SAFE.sub("-", str(fallback or "")).strip("-")[:60] or "show"


def show_dir(root, aid=None, title="", ja=""):
    """`<mal id>_<slug>` where the work has an id on his list, and the slug
    alone where it has not -- her own watchlist carries no ids, and an episode
    of a show she picked herself still gets a directory."""
    s = slug(title, ja)
    return os.path.join(str(root), (f"{int(aid)}_{s}" if aid else s))


def _bullets(head, rows):
    rows = [str(r).strip() for r in (rows or []) if str(r or "").strip()]
    if not rows:
        return []
    return [f"## {head}", ""] + [f"- {r}" for r in rows] + [""]


def anchor_source(row):
    """The source row for the episode's own dialogue, or None. `kind` is
    `transcript` and `note` carries the provenance the file was judged to
    be."""
    for src in (row.get("sources") or []):
        if str(src.get("kind") or "") == "transcript":
            return src
    return None


def anchor_words(row):
    """What the account is anchored on, in three words: whether the episode's
    own dialogue is behind it and where that dialogue came from.

    The provenance is named rather than collapsed: a fan listening transcript
    and a broadcast caption rip are both a subtitle file and they are not the
    same evidence -- the caption rip carries the speaker labels and the fan
    file is somebody's guess at what was said."""
    src = anchor_source(row)
    if src:
        prov = str(src.get("note") or "").strip().lower() or "subtitle"
        return f"subtitle ({prov})"
    kind = str(row.get("anchor_kind") or "")
    if "subtitle" in kind:
        # an account built before the sources carried the provenance
        return "subtitle"
    return "web only"


def anchor_file(row):
    """The name of the file the dialogue came from, without its directory."""
    src = anchor_source(row)
    url = str((src or {}).get("url") or "")
    return os.path.basename(url) if url else ""


def write_episode(root, row):
    """One episode's page. `row` is what `sim/episode_account.py` stored.
    Returns the path written, or "".

    Overwritten rather than versioned: this is a view of the store and the
    store is the record. The archive under `recap.archive_dir` is where
    nothing is ever overwritten."""
    if not root:
        return ""
    try:
        d = show_dir(root, row.get("aid"), row.get("show") or "", row.get("ja") or "")
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, "ep%02d.md" % int(row.get("ep") or 0))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(_page(row)))
        return path
    except OSError as e:
        logger.log(f"[episodes] the page was not written: {type(e).__name__}")
        return ""


def _page(row):
    ep = int(row.get("ep") or 0)
    ja = str(row.get("ja") or "")
    show = str(row.get("show") or "")
    eng = str(row.get("english") or "")
    level = str(row.get("level") or "thin")
    # the title in three scripts, on one line, with the ones that repeat
    # dropped: a show whose romaji and English titles are the same word should
    # not be written out twice
    names, seen = [], set()
    for n in (ja, show, eng):
        n = str(n or "").strip()
        if n and n.lower() not in seen:
            seen.add(n.lower())
            names.append(n)
    out = [f"# {names[0] if names else '(untitled)'} -- episode {ep}", ""]
    if len(names) > 1:
        out += ["*" + " / ".join(names[1:]) + "*", ""]
    if row.get("ep_title"):
        out += [f"Episode title: {row['ep_title']}", ""]
    built = row.get("built_at") or 0
    out += [
        "| | |",
        "|---|---|",
        f"| completeness | **{level}** -- "
        f"{LEVEL_WORDS.get(level, '').split(' -- ', 1)[-1]} |",
        f"| account | {int(row.get('chars') or 0)} characters, "
        f"{len(row.get('scenes') or [])} scene(s) |",
        f"| anchored on | {row.get('anchor_kind') or 'nothing -- no transcript and no official blurb'} |",
        f"| anchor | {anchor_words(row)} |",
        f"| anchor file | {anchor_file(row) or '(none -- web pages only)'} |",
        f"| sources merged | {sum(1 for s in (row.get('sources') or []) if s.get('used'))}"
        f" of {len(row.get('sources') or [])} read |",
        f"| work | {('mal:%d' % int(row['aid'])) if row.get('aid') else '(not on his list)'} |",
        f"| written | {time.strftime('%Y-%m-%d %H:%M', time.localtime(built)) if built else '?'} |",
        f"| by | {row.get('model') or '?'} |",
        "",
    ]
    out += ["## The account", "", str(row.get("account") or "(none)"), ""]
    scenes = row.get("scenes") or []
    if scenes:
        out += ["## Scene by scene", ""]
        out += [f"{i + 1}. {s}" for i, s in enumerate(scenes)]
        out += [""]
    out += _bullets("Parts", row.get("parts"))
    out += _bullets("Running gags", row.get("gags"))
    out += _bullets("Lines", row.get("quotes"))
    out += _bullets("What it points at", row.get("references"))
    if row.get("endcard"):
        out += ["## How it ends", "", str(row["endcard"]), ""]
    out += _bullets("Not settled by any source", row.get("missing"))
    srcs = row.get("sources") or []
    if srcs:
        out += ["## Sources", "",
                "| used | what it is | characters | where |", "|---|---|---|---|"]
        for s in srcs:
            out.append("| %s | %s | %d | %s |" % (
                "yes" if s.get("used") else "no", s.get("kind") or "?",
                int(s.get("chars") or 0), (s.get("url") or "").replace("|", "%7C")))
        out += [""]
    if row.get("archive"):
        out += [f"Everything fetched for it is under `{row['archive']}`.", ""]
    return out


def write_index(root):
    """`INDEX.md` over every episode page on disk: what is on file and how
    complete it is. Rebuilt whole, because it is a listing of a directory and
    reading the directory is cheaper than keeping a second record of it."""
    if not root or not os.path.isdir(str(root)):
        return ""
    rows = []
    try:
        for d in sorted(os.listdir(root)):
            p = os.path.join(root, d)
            if not os.path.isdir(p):
                continue
            for f in sorted(os.listdir(p)):
                m = re.match(r"ep(\d+)\.md$", f)
                if not m:
                    continue
                rows.append((d, int(m.group(1)), _index_row(os.path.join(p, f))))
    except OSError as e:
        logger.log(f"[episodes] the index was not built: {type(e).__name__}")
        return ""
    out = ["# Episodes on file", "",
           "Every episode an account has been written for, and how complete it came out.",
           "`watched` means several sources were merged and every scene is in order;",
           "`thin` means one source carried little and it would be read up again.", "",
           "The `anchor` column says whether the episode's own dialogue is behind",
           "the account and where that dialogue came from; `web only` means it is",
           "built on what people wrote about the episode and nothing else.", "",
           "| show | ep | completeness | anchor | scenes | characters | page |",
           "|---|---|---|---|---|---|---|"]
    for d, ep, info in sorted(rows, key=lambda r: (r[0].lower(), r[1])):
        out.append("| %s | %d | %s | %s | %s | %s | [%s](%s/ep%02d.md) |" % (
            info.get("title") or d, ep, info.get("level") or "?",
            info.get("anchor") or "?",
            info.get("scenes") or "?", info.get("chars") or "?", "open", d, ep))
    counts = {}
    for _d, _e, info in rows:
        counts[info.get("level") or "?"] = counts.get(info.get("level") or "?", 0) + 1
    out += ["", "%d episode(s) on file: %s." % (
        len(rows), ", ".join(f"{n} {k}" for k, n in sorted(counts.items())) or "none"), ""]
    path = os.path.join(str(root), "INDEX.md")
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(out))
        return path
    except OSError as e:
        logger.log(f"[episodes] the index was not written: {type(e).__name__}")
        return ""


def _index_row(path):
    """The header facts of one episode page, read back off the page itself, so
    the index needs no store of its own."""
    d = {}
    try:
        with open(path, encoding="utf-8") as fh:
            head = fh.read(4000)
    except OSError:
        return d
    m = re.search(r"^# (.+?) -- episode", head, re.M)
    if m:
        d["title"] = m.group(1).strip()
    m = re.search(r"\| completeness \| \*\*(\w[\w-]*)\*\*", head)
    if m:
        d["level"] = m.group(1)
    m = re.search(r"\| account \| (\d+) characters, (\d+) scene", head)
    if m:
        d["chars"], d["scenes"] = m.group(1), m.group(2)
    m = re.search(r"\| anchor \| (.+?) \|", head)
    if m:
        d["anchor"] = m.group(1).strip()
    elif re.search(r"\| anchored on \| .*subtitle", head):
        # a page written before the column existed
        d["anchor"] = "subtitle"
    elif re.search(r"\| anchored on \| ", head):
        d["anchor"] = "web only"
    m = re.search(r"\| anchor file \| (.+?) \|", head)
    if m and not m.group(1).startswith("("):
        d["anchor_file"] = m.group(1).strip()
    return d


def write(root, row):
    """One episode's page and the index over all of them, which is what a
    caller wants every time. Returns the episode's path."""
    p = write_episode(root, row)
    if p:
        write_index(root)
    return p


def read_row(root, aid=None, title="", ja="", ep=0):
    """Whether a page exists for this episode, and what its header says.
    For a reader (the dossier) that wants to link to it."""
    d = show_dir(root, aid, title, ja)
    p = os.path.join(d, "ep%02d.md" % int(ep or 0))
    if not os.path.exists(p):
        return None
    row = _index_row(p)
    row["path"] = p
    return row


def dump_json(root, row):
    """The same row beside the page, for a reader that wants the fields rather
    than the prose. The page is what a person opens; this is what a tool
    parses, and neither has to be re-derived from the other."""
    try:
        d = show_dir(root, row.get("aid"), row.get("show") or "", row.get("ja") or "")
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, "ep%02d.json" % int(row.get("ep") or 0))
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(row, fh, ensure_ascii=False, indent=1)
        return p
    except (OSError, TypeError, ValueError) as e:
        logger.log(f"[episodes] the row was not written: {type(e).__name__}")
        return ""


# ---------------- the transcript log ----------------
#
# Where an episode's own dialogue came from was readable only in SQL: the
# `transcripts` table in each save, one row per (show, episode), and the
# reasons scattered across a thousand session logs. He asked where he could
# see it and there was nowhere. So one append-only file, the machine's like
# everything else here, one line per attempt that resolved.

TRANSCRIPT_HEAD = (
    "# Transcripts on file\n"
    "\n"
    "Every attempt at an episode's own dialogue that resolved, oldest first.\n"
    "**Append-only**: a line is written once per (show, episode, file) and never\n"
    "rewritten, so an episode that was a miss and later got a file has both\n"
    "lines and the order says which came first. `dialogue` is how far into the\n"
    "episode the last line runs; `GPU` is the time the transcriber spent, and\n"
    "is blank for a file that already existed. `by` names the process that\n"
    "recorded the attempt first: a subtitle file found once is found for the\n"
    "machine, so a second character finding the same file adds no line.\n"
    "\n"
    "| when | show | ep | where it came from | lines | dialogue | GPU | file | by |\n"
    "|---|---|---|---|---|---|---|---|---|\n")


def transcript_outcome(row):
    """`sidecar` / `mirror` / `archive` / `whisper` / `miss` for one attempt.

    The words say WHERE the file came from, which is the question the log
    exists to answer -- `provenance` says what kind of subtitle it is
    (broadcast, streaming, fan, whisper) and the two are different facts. An
    older row carries no `origin`, so the provenance and the source stand in."""
    if str(row.get("status") or "") != "ok":
        return "miss"
    prov = str(row.get("provenance") or "").lower()
    if prov == "whisper":
        return "whisper"
    origin = str(row.get("origin") or "").lower()
    if "beside his video" in origin:
        return "sidecar"
    if "on this machine" in origin:
        return "mirror"
    if origin:
        return "archive"
    src = str(row.get("source") or "")
    return "sidecar" if (src and not src.lower().startswith("http")) else "archive"


def _dialogue_minutes(row):
    """How far into the episode the last line runs, in minutes, or 0. The
    number that says whether a transcript covers the episode or its first ten
    minutes."""
    lines = row.get("lines") or []
    try:
        return max(float(x.get("end") or x.get("start") or 0) for x in lines) / 60.0
    except (ValueError, TypeError, AttributeError):
        return 0.0


def _file_words(src):
    """A file name a person can read: the basename, and percent-escapes
    decoded. An archive's URL carries the Japanese episode title escaped, and
    one of them ran to 700 characters of `%E3%81%A1` in the table."""
    name = os.path.basename(str(src or ""))
    try:
        name = urllib.parse.unquote(name)
    except Exception:
        pass
    return name[:90].replace("|", "%7C")


def _transcript_line(row, by=""):
    when = int(row.get("fetched_at") or 0) or int(time.time())
    ep = int(row.get("ep") or 0)
    mins = _dialogue_minutes(row)
    gpu = float(row.get("gpu_seconds") or 0)
    src = str(row.get("source") or "")
    # the file it WROTE for a transcription, which is the one his player will
    # find next time, not the video it listened to
    if str(row.get("provenance") or "") == "whisper" and src:
        src = os.path.splitext(src)[0] + ".srt"
    return "| %s | %s | %d | %s | %s | %s | %s | %s | %s |" % (
        time.strftime("%Y-%m-%d %H:%M", time.localtime(when)),
        str(row.get("show") or row.get("ja") or "?").replace("|", "%7C"),
        ep, transcript_outcome(row),
        int(row.get("n_lines") or 0) or "",
        f"{mins:.1f} min" if mins else "",
        f"{gpu / 60:.1f} min" if gpu else "",
        _file_words(src) or "",
        str(by or "?").replace("|", "%7C"))


def _transcript_key(row):
    """What makes two lines the same attempt: the show, the episode and the
    file. A second look that found the same file writes nothing; one that found
    a different file, or turned a miss into a hit, writes a line."""
    src = str(row.get("source") or "")
    return "|%s|%d|%s|%s|" % (str(row.get("show") or row.get("ja") or ""),
                              int(row.get("ep") or 0),
                              transcript_outcome(row), os.path.basename(src))


def _split_log(have):
    """The log's heading and its table rows, apart. The heading is everything
    down to and including the `|---|` rule; a row is any line under it that
    starts a table cell."""
    if not have.strip():
        return TRANSCRIPT_HEAD, []
    lines = have.splitlines()
    cut = 0
    for i, line in enumerate(lines):
        if line.startswith("|---"):
            cut = i + 1
            break
    head = "\n".join(lines[:cut]) + "\n" if cut else TRANSCRIPT_HEAD
    return head, [l for l in lines[cut:] if l.startswith("|")]


def _line_order(line):
    """A row's place in time: the stamp in its first cell, then the show and
    the episode so that two attempts recorded in the same minute keep a fixed
    order. The stamp is written `YYYY-MM-DD HH:MM`, which sorts as text."""
    cells = line.split("|")
    when = cells[1].strip() if len(cells) > 1 else ""
    show = cells[2].strip() if len(cells) > 2 else ""
    try:
        ep = int((cells[3] if len(cells) > 3 else "0").strip() or 0)
    except ValueError:
        ep = 0
    return (when, show, ep)


def note_transcript(path, row, by="", also=()):
    """Put one attempt in the readable log, and nothing when its line is
    already there. Returns the path when the file was written.

    `also` is a table of earlier attempts to catch up with on the first write
    -- the rows a save already held before this file existed. They go in under
    the same de-duplication, so running this twice writes one copy of each.

    **A line is written once and never rewritten, but the table is kept in
    time order.** Each save catches its own rows up as a block at
    construction, so appending put the third character's attempt from Monday
    under the first character's from Wednesday. The whole table is therefore
    re-rendered on every write with its rows sorted by their own stamp, the
    text of each line untouched; a live attempt is always the newest minute,
    so after the first re-render the sort changes nothing."""
    if not path or not row:
        return ""
    try:
        have = ""
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                have = fh.read()
        head, rows = _split_log(have)
        add, keys = [], set()
        for r in list(also or []) + [row]:
            k = _transcript_key(r)
            if k in keys or _same_attempt(have, r):
                continue
            keys.add(k)
            add.append(_transcript_line(r, by))
        ordered = sorted(rows + add, key=_line_order)
        if not add and ordered == rows and have.startswith(head):
            return ""
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(head + "\n".join(ordered) + ("\n" if ordered else ""))
        os.replace(tmp, path)
        return path
    except OSError as e:
        logger.log(f"[subs] the transcript log was not written: {type(e).__name__}")
        return ""


def _same_attempt(have, row):
    """Is this exact attempt -- show, episode, where it came from, file --
    already a line in the log."""
    src = str(row.get("source") or "")
    if str(row.get("provenance") or "") == "whisper" and src:
        src = os.path.splitext(src)[0] + ".srt"
    show = str(row.get("show") or row.get("ja") or "?")
    want = "| %s | %d | %s |" % (show, int(row.get("ep") or 0), transcript_outcome(row))
    for line in have.splitlines():
        if want in line and _file_words(src) in line:
            return True
    return False
