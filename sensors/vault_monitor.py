import os
import re
import glob
import random

# His notes folder. Two uses: the telemetry collector reports files he
# modified (she sees "he was writing X" in the app), and the late-night snoop
# pulls files she has not read yet. Read history lives in world.db kv under
# "vault_read_paths"; the store is passed in by the caller.
#
# She reads his notes as he wrote them. He keeps his daily notes in the same
# folder he writes THIS PROJECT in, so his journal contains the mechanism she
# would be reading them through -- a measured 23% of two-note snoops surface
# one. That used to be filtered out; it is not, by his decision on 2026-08-21,
# and the digest had been showing her his window titles unredacted the whole
# time regardless.


def _all_files(config):
    if not config.vault_path or not os.path.exists(config.vault_path):
        return []
    files = []
    for ext in config.vault_extensions:
        files.extend(glob.glob(os.path.join(config.vault_path, "**", ext), recursive=True))
    return [f for f in files if not any(p in f for p in config.vault_ignore_patterns)]


def get_modified_file_info_since(config, since_timestamp):
    result = []
    for f in _all_files(config):
        mtime = os.path.getmtime(f)
        if mtime > since_timestamp:
            result.append((f, mtime, os.path.basename(f)))
    result.sort(key=lambda x: x[1], reverse=True)
    return result[:4]


def catalogue(config, max_items=25):
    """The shape of his notes folder, titles only, newest first: (relpath, mtime)."""
    files = _all_files(config)
    rows = []
    for f in files:
        try:
            rows.append((os.path.relpath(f, config.vault_path).replace("\\", "/"), os.path.getmtime(f)))
        except OSError:
            continue
    rows.sort(key=lambda x: x[1], reverse=True)
    return rows[:max_items], len(rows)


def tail_excerpt(path, max_chars):
    """The end of a note, where he was most likely writing. Empty on failure."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read()
    except OSError:
        return ""
    content = content.strip()
    if len(content) <= max_chars:
        return content
    return "..." + content[-max_chars:]


def _read(path, max_chars, pieces=4, seed=""):
    """What she actually gets from a note: a skim, not the file. Short notes
    are read whole. Long ones give the opening, the ending (where he was last
    writing) and a few paragraphs from the middle that would catch a bored
    fifteen year old's eye, all inside max_chars, gaps marked with [...]."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read()
    except OSError:
        return None
    if not content.strip():
        return None       # an empty note; the caller draws another
    return skim(content, max_chars, pieces, seed or path)


# "tomoe" is deliberately not here. It was excluded because her own name in
# his notes drew exactly the paragraphs the fourth-wall scrub then removed;
# the scrub is gone, so putting it back is now a live choice rather than a
# contradiction, and it would pull her toward the paragraphs about her.
_EYE = ("?", "!", "[[", "#", "todo", "never", "always", "hate", "love", "she", "her",
        "i think", "i feel", "i want", "i should", "why", "wtf", "lol")


def _catchy(par):
    low = par.lower()
    return sum(1 for k in _EYE if k in low) + (2 if low.startswith("#") else 0)


def skim(content, max_chars, pieces=4, seed=""):
    content = content.strip()
    if len(content) <= max_chars:
        return content
    pars = [p.strip() for p in re.split(r"\n\s*\n", content) if p.strip()]
    if len(pars) < 3:
        # one big block: opening and ending only
        half = max_chars // 2
        return content[:half].rstrip() + "\n[...]\n" + content[-half:].lstrip()
    budget = max_chars
    head_b, tail_b = int(max_chars * 0.3), int(max_chars * 0.3)
    head, tail = [], []
    i, j = 0, len(pars) - 1
    used = 0
    while i <= j and used + len(pars[i]) <= head_b:
        head.append(i); used += len(pars[i]) + 1; i += 1
    if not head and i <= j:
        head.append(i); used += len(pars[i][:head_b]) + 1; i += 1
    used_t = 0
    while j >= i and used_t + len(pars[j]) <= tail_b:
        tail.insert(0, j); used_t += len(pars[j]) + 1; j -= 1
    if not tail and j >= i:
        tail.insert(0, j); used_t += len(pars[j][-tail_b:]) + 1; j -= 1
    budget -= used + used_t
    middle = list(range(i, j + 1))
    rng = random.Random(seed)
    rng.shuffle(middle)
    middle.sort(key=lambda k: -_catchy(pars[k]))
    picked = []
    for k in middle:
        if len(picked) >= max(0, pieces - 2):
            break
        if len(pars[k]) + 6 <= budget:
            picked.append(k); budget -= len(pars[k]) + 6
    order = head + sorted(picked) + tail
    out, last = [], -1
    for k in order:
        if last >= 0 and k != last + 1:
            out.append("[...]")
        p = pars[k]
        if k in head and len(p) > head_b:
            p = p[:head_b].rstrip() + " [...]"
        if k in tail and len(p) > tail_b:
            p = "[...] " + p[-tail_b:].lstrip()
        out.append(p)
        last = k
    return "\n\n".join(out)


def pick_unread(config, already_read, count, max_chars, pieces=4, seed="",
                name_regex=None, min_bytes=0, newest=0):
    """Files she has not opened yet. The snoop narrows this hard: `name_regex`
    to his daily-note format (his journal is where his life is; the rest of the
    vault is code dumps, prompt scratch and reference), `min_bytes` to skip the
    empty stubs, `newest` to the recent stretch -- a notes app opens sorted by
    date, and she is looking at what he has been writing, not at January.
    Sorting is by filename, not mtime: the daily notes are named for their date
    and a sync can rewrite mtime on all of them at once."""
    files = _all_files(config)
    if name_regex:
        rx = re.compile(name_regex)
        files = [f for f in files if rx.match(os.path.basename(f))]
    if min_bytes:
        kept = []
        for f in files:
            try:
                if os.path.getsize(f) >= min_bytes:
                    kept.append(f)
            except OSError:
                pass
        files = kept
    if newest:
        files = sorted(files, key=lambda f: os.path.basename(f), reverse=True)[:newest]
    unread = [f for f in files if f not in already_read] or files
    if not unread:
        return []
    chosen = random.sample(unread, min(count, len(unread)))
    out = []
    for f in chosen:
        content = _read(f, max_chars, pieces, seed + f)
        if content is None:
            continue
        out.append({"path": f, "basename": os.path.basename(f), "mtime": os.path.getmtime(f), "content": content})
    return out


def find(config, query, max_chars, pieces=4, seed=""):
    q = query.lower()
    matches = [f for f in _all_files(config) if q in os.path.basename(f).lower()]
    if not matches:
        return None
    matches.sort(key=lambda x: len(os.path.basename(x)))
    f = matches[0]
    return {"path": f, "basename": os.path.basename(f), "mtime": os.path.getmtime(f),
            "content": _read(f, max_chars, pieces, seed + f) or ""}


def match_title_to_vault_file(config, title):
    # A window title like "notes - Obsidian" is cleaned upstream; here we
    # check whether the remaining title names a vault file he had open long
    # enough to count as reading it.
    if not title or not config.vault_path or not os.path.exists(config.vault_path):
        return None
    wanted = {title.lower()}
    for ext in config.vault_extensions:
        e = ext[1:] if ext.startswith("*") else ext
        if not title.lower().endswith(e.lower()):
            wanted.add((title + e).lower())
    for f in _all_files(config):
        if os.path.basename(f).lower() in wanted:
            return f
    return None
