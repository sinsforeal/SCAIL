"""One place that knows who a name refers to.

Every person in her world carries three names and they are not
interchangeable:

- the **roster key** in `data/cast.json` (`Rena-chan`, `mom`) -- the stable
  handle the sheets and the prompt files are named after,
- the **role_id** (`ringleader`, `mother`) -- what the machinery thinks in,
  and the only one of the three that survives a recast,
- the **record name** (`香芝玲奈`) -- what the stored record calls her, because
  the record is Japanese and a Japanese chat log naming its speakers in
  romaji is the same English leak the glosses were.

Until this module there was no such place. Six modules matched names by
lowercasing and testing `in`, so `Rena` and `Rena-chan` became two girls in
one conversation and every rule keyed to a display string quietly skipped
the turns under the other label. Matching here is **exact against a built
alias table**, never a substring: the aliases come from the data (the roster
key, `ja`, `reading`, `name`, an explicit `aliases` list, and every nickname
the others' `calls` entries use for this person), so adding a name is an
edit to `data/cast.json` and no code.

Re-read whenever the file changes, like `places.json` and `voice_rules.json`.
"""
import json
import time
import os
import re

import atomic
import logger

_CACHE = {"path": None, "mtime": 0, "who": None, "alias": {}, "people": {}, "self": {},
          "rows": {}}


def _norm(s):
    """The form a name is looked up under. ASCII is case-insensitive because
    the roster keys are English; Japanese has no case to fold."""
    return str(s or "").strip().lower()


def _self_aliases(config):
    """Every way a model may write her own name: the pronouns, her name and
    its reading from the config, and whatever her sheet lists under
    `name` (`full`, `japanese`, `given`, `aliases`, `aliases_ja`)."""
    out = ["her", "she", "herself"]
    ch = config.character
    for v in (getattr(ch, "name", ""), getattr(ch, "name_ja", ""), getattr(ch, "reading_ja", "")):
        if v:
            out.append(str(v).lower())
    nm = (getattr(config, "character_sheet", None) or {}).get("name") or {}
    if isinstance(nm, dict):
        for k in ("full", "japanese", "given"):
            if nm.get(k):
                out.append(str(nm[k]).lower())
        for k in ("aliases", "aliases_ja"):
            for v in nm.get(k) or []:
                out.append(str(v).lower())
    seen, uniq = set(), []
    for a in out:
        if a and a not in seen:
            seen.add(a)
            uniq.append(a)
    return uniq


def _my_row_key(config, people):
    """The key of the row in a cast file that IS the running character.

    A character promoted out of somebody else's cast is still a row in that
    cast, because the people who were not promoted go on reaching for her
    through it and the process that keeps the world still needs to know where
    she is. In HER process that row is not a second girl: it is her. Found
    from the data -- the row whose `agent` is the hub id this process
    registers under, failing that the row whose Japanese name is the one her
    config gives her -- and never written down as a constant.

    Empty for a character who is in nobody else's cast, which is every
    character who keeps her own world."""
    hub = "".join(str(getattr(config.character, "name", "") or "").lower().split())
    ja = _norm(getattr(config.character, "name_ja", ""))
    for key, person in (people or {}).items():
        if not isinstance(person, dict):
            continue
        if hub and _norm(person.get("agent")) == hub:
            return key
        if ja and _norm(person.get("ja")) == ja:
            return key
    return ""


# A file being replaced is unreadable for as long as the replacement takes,
# and this function is called on every name in every line she writes. One
# rewrite of the cast roster produced 233 identical parse failures on one
# character and 131 on another inside 31 seconds. Say it once, then once a
# minute with the count, then say when it came back and how long it was gone.
_UNREADABLE = {"path": "", "since": 0.0, "n": 0, "said": 0.0}
_UNREADABLE_EVERY = 60.0


def _say_unreadable(path, e):
    st = _UNREADABLE
    now = time.time()
    if st["path"] != path or not st["since"]:
        st.update({"path": path, "since": now, "n": 1, "said": now})
        logger.log(f"[roster] cast file unreadable, names unresolved: {type(e).__name__}: {e}")
        return
    st["n"] += 1
    if now - st["said"] >= _UNREADABLE_EVERY:
        st["said"] = now
        logger.log(f"[roster] cast file still unreadable after {now - st['since']:.0f}s, "
                   f"{st['n']} read(s): {type(e).__name__}: {e}")


def _say_readable(path):
    st = _UNREADABLE
    if st["path"] == path and st["since"]:
        logger.log(f"[roster] cast file readable again after {time.time() - st['since']:.0f}s "
                   f"and {st['n']} failed read(s)")
        st.update({"path": "", "since": 0.0, "n": 0, "said": 0.0})


def _table(config):
    path = getattr(config.character, "cast_file", "")
    if not path:
        return _CACHE
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return _CACHE
    # The table is one FILE read through one character's eyes: her own row is
    # in it, and every name resolves to a role by her reckoning. Two
    # characters may name the same cast file -- a character promoted out of
    # somebody else's cast reads that cast -- so the cache is keyed on who is
    # asking as well as on the file. It was keyed on the file alone, and in
    # any process that builds two of them (`tools/smoke.py`, a harness) the
    # second character was handed the first one's roster: her own name
    # resolved to a stranger and the other character's resolved to `self`.
    who = str(getattr(config.character, "name", "") or "")
    # her OWN people, when she is in a world she does not keep: a second
    # file, and a key in both is hers (`own_cast_file`)
    own_path = str(getattr(config.character, "own_cast_file", "") or "")
    try:
        own_mtime = os.path.getmtime(own_path) if own_path else None
    except OSError:
        own_mtime = None
    if (_CACHE["path"] == path and _CACHE["mtime"] == mtime and _CACHE["who"] == who
            and _CACHE.get("own_mtime") == own_mtime):
        return _CACHE
    try:
        # tried more than once: the file is replaced by a rename, and the
        # window a read can fail in is over before a second attempt
        data = atomic.read_json(path)
        people = data.get("people", {}) or {}
    except (OSError, ValueError) as e:
        _say_unreadable(path, e)
        return _CACHE
    _say_readable(path)
    # The keeper of a cast file has her own line in it, under `self`: her
    # Japanese name and what she calls each of them. For the character the
    # file belongs to that line is not a person and never enters the table.
    # For a character who READS the file it is the girl whose world she is
    # in -- somebody she is at school with every day -- and until she was a
    # person here, her fills could name her ("Tomoe (とも)") and nothing in
    # the process could tell who that was.
    owner = data.get("self") or {}
    owner_key = str(owner.get("key") or owner.get("name") or "")
    if owner_key and _norm(owner.get("ja")) != _norm(getattr(config.character, "name_ja", "")):
        people = dict(people)
        people.setdefault(owner_key, dict(owner))
    own_people, own_calls = {}, {}
    if own_path and own_mtime is not None:
        try:
            own_data = atomic.read_json(own_path)
            own_people = own_data.get("people", {}) or {}
            # what SHE calls her own people is a name for them: her mother is
            # お母さん in every line she writes, and without this the only row
            # claiming that word was the mother of the girl whose world she is
            # in, so her own mother's name resolved to somebody else's parent
            own_calls = {k: v for k, v in ((own_data.get("self") or {}).get("calls") or {}).items()
                         if k in own_people}
        except (OSError, ValueError) as e:
            logger.log(f"[roster] her own cast file unreadable: {type(e).__name__}: {e}")
    people = {k: dict(v, own=False) for k, v in people.items() if k not in own_people}
    people.update({k: dict(v, own=True) for k, v in own_people.items()})

    # what everybody calls everybody: Hinako's `calls` says れな means Rena,
    # so the nicknames are already in the data and need no guessing at where
    # a surname ends.
    nick = {}
    for _k, person in people.items():
        for whose, called in (person.get("calls") or {}).items():
            nick.setdefault(_norm(whose), set()).add(called)
    for whose, called in own_calls.items():
        nick.setdefault(_norm(whose), set()).add(called)

    # the row that is HER: taken out of the table and folded into her own
    # entry, names and all. It stayed a person for eleven days in a promoted
    # character's process, so every name she goes by resolved to a stranger
    # with her own face -- her planner listed her under where everybody is
    # today, her save carried a bond with her, and the boot log said her name
    # meant both self and somebody else eight times. The row stays in the
    # file: the process that keeps the world still needs it.
    mine_key = _my_row_key(config, people)
    mine = people.pop(mine_key, {}) if mine_key else {}

    # her own entry does not live in the cast (the cast is who is around her)
    me = {"key": getattr(config.character, "name", "") or "her",
          "role_id": "self",
          "ja": getattr(config.character, "name_ja", "") or getattr(config.character, "name", "") or "her",
          "reading": getattr(config.character, "reading_ja", ""),
          # a model labelling a line as hers reaches for a pronoun or a
          # spaced-out full name as readily as her name, and every one of
          # those has to resolve to her or the line is filed as a stranger's.
          # The names are hers, from her config and her sheet, never from here.
          "aliases": _self_aliases(config)}
    if mine_key:
        # every name that row goes by is a name for her: the handle the shared
        # record is keyed by, its Japanese name and reading, its aliases, and
        # what each of the others calls her
        me["handle"] = mine_key
        me["aliases"] = me["aliases"] + [mine_key, mine.get("name") or "", mine.get("ja") or "",
                                         mine.get("reading") or ""] \
            + [str(a) for a in (mine.get("aliases") or [])] \
            + sorted(nick.get(_norm(mine_key), set()))

    alias, table = {}, {}
    entries = [(me["key"], me)] + [(k, dict(v, key=k)) for k, v in people.items()]

    for key, person in entries:
        role = str(person.get("role_id") or "") or key
        rec = {"key": key, "role_id": role,
               "ja": person.get("ja") or "", "reading": person.get("reading") or "",
               "name": person.get("name") or key,
               # which school this person goes to, when they go to one. Her
               # brother has a timetable too and is at the local primary, so
               # "has school_days" is not the same question as "is in the room
               # with her at lunch"; only this key answers that one.
               "school": _norm(person.get("school") or ""),
               # the hub id of the process that speaks for this person, when
               # there is one -- see `agent_of` below
               "agent": str(person.get("agent") or "").strip(),
               # hers: in her own cast file. Every person is "own" for the
               # character who keeps her world; for a reader, only these
               "own": bool(person.get("own", True)),
               # is this person somebody's family rather than one of the
               # friend group? The row may say so itself; without the field
               # the five family role ids are the answer, which is what every
               # reader of this used before the field existed (`is_family`).
               "family": person.get("family")}
        table[role] = rec
        # the role_id resolves to itself, so a caller holding a key from
        # `relationships` resolves the same whether that dict is still keyed
        # by the roster name or has been moved onto role ids. It is what lets
        # that migration happen without the matching depending on it.
        names = {key, role, rec["ja"], rec["reading"], rec["name"]}
        names |= set(person.get("aliases") or ())
        names |= nick.get(_norm(key), set())
        for n in names:
            n = _norm(n)
            if not n:
                continue
            if n in alias and alias[n] != role:
                # a word that is two people's is HERS first: お母さん means the
                # woman in her kitchen, not the mother of the girl whose world
                # she is in, and it resolved to the other one because the
                # world's rows are read first. Her own people win it; anything
                # else is reported and the first claim stands.
                if person.get("own") and not table.get(alias[n], {}).get("own"):
                    logger.log(f"[roster] {n!r} means both {alias[n]} and {role}; hers is {role}")
                    alias[n] = role
                    continue
                logger.log(f"[roster] {n!r} means both {alias[n]} and {role}; keeping {alias[n]}")
                continue
            alias[n] = role

    _CACHE.update({"path": path, "mtime": mtime, "who": who, "own_mtime": own_mtime,
                   "alias": alias, "people": table, "self": me,
                   # the rows as the FILES have them, her own row already out:
                   # what a meter is seeded from, which needs the whole row and
                   # not the handful of fields the table keeps
                   "rows": {k: {kk: vv for kk, vv in v.items() if kk != "own"}
                            for k, v in people.items()}})
    n_own = sum(1 for r in table.values() if r.get("own") and r.get("role_id") != "self")
    logger.log(f"[roster] {len(table)} people, {len(alias)} names"
               + (f"; {n_own} of them her own, from {own_path}" if own_people else ""))
    return _CACHE


def role_of(config, who):
    """The role_id this name refers to, or "" when nobody owns it."""
    t = _table(config)
    return t["alias"].get(_norm(who), "")


def rec_of(config, who):
    """Everything known about the person this name refers to, or {}."""
    t = _table(config)
    return t["people"].get(role_of(config, who), {})


def record_name(config, who):
    """What the record calls this person -- her Japanese name where there is
    one, and the name as given when the roster has never heard of them (a
    classmate named once in passing is still allowed to have said something)."""
    return rec_of(config, who).get("ja") or str(who or "")


def key_of(config, who):
    """The roster key, for a sheet (`prompts/cast/<key>.md`) or a cast.json
    lookup. Falls back to the name as given."""
    return rec_of(config, who).get("key") or str(who or "")


def same(config, a, b):
    """Are these two names the same person? Two unknown names are not the
    same person just because neither resolved."""
    ra = role_of(config, a)
    return bool(ra) and ra == role_of(config, b)


def is_self(config, who):
    return role_of(config, who) == "self"


def self_names(config):
    """Every name that means the running character herself, as the roster
    resolves them: her config name, her Japanese name and its reading, what
    her own sheet gives as her aliases, and what each person on her roster
    calls her.

    Wanted where the answer has to leave this process and be asked again
    somewhere `is_self` cannot be called -- the group view his phone draws
    (`channels/talkapp_bot.py _group`), which had one character's names
    spelled into the client and so put a fourth character's turns on the
    wrong side of a room she was sent."""
    t = _table(config)
    return sorted(n for n, role in t["alias"].items() if role == "self")


def handle(config):
    """What the RECORD calls the running character herself.

    She has the same three names as anybody else here, and they are the same
    three: her config gives her a name, and -- when she was promoted out of
    somebody else's cast -- that cast still carries a row for her under the
    handle every shared record about her is keyed by. The two are different
    strings, so anything that looks HER up in a record two processes share
    (the world file's edges, an edge key in a save) has to ask for the handle
    and not for the config name.

    Resolved from the data and never written down as a constant: the cast row
    whose `agent` field is this process's hub id is her own row, and failing
    that the row whose Japanese name is the one her config gives her. A
    character who is in nobody else's cast has neither, and her config name is
    what the record calls her -- which is the answer every character had
    before this existed.
    """
    ch = getattr(config, "character", None)
    name = str(getattr(ch, "name", "") or "")
    # her own row is folded into her own entry when the table is built, and
    # the handle it was keyed by is kept there
    mine = _table(config)["self"].get("handle")
    if mine:
        return mine
    # the same expression the hub registers her under (channels/talkapp_bot.py)
    hub = "".join(name.lower().split())
    rec = by_agent(config, hub) if hub else {}
    if rec.get("key"):
        return rec["key"]
    ja = _norm(getattr(ch, "name_ja", ""))
    if ja:
        for r in _table(config)["people"].values():
            # her own entry in the table is keyed by the config name, which is
            # the answer this is looking past
            if r.get("role_id") == "self":
                continue
            if _norm(r.get("ja")) == ja:
                return r.get("key") or name
    return name


FAMILY_ROLES = {"mother", "father", "sibling", "grandmother", "grandfather"}


def is_family(config, who):
    """Is this person somebody's family rather than one of the friend group?

    The question two rooms ask: who is in a group chat, and who could have
    been in the room where something was said. A row answers it itself with
    `family`; without the field the five role ids above are the answer, so the
    character who keeps her world is unchanged.

    The field is what a second character in the same world needs. Her own
    mother and brother are on her own roster under role ids of their own
    (`rena_mother`, `rena_brother`), because two households in one world cannot
    both be `mother` and `sibling` -- so the five ids said her own mother was
    not family and put her in the group chat, while the OWNER's mother, who is
    family and is not hers, was correctly kept out of it. Marking her own two
    rows fixes the first without touching the second.

    Whose family is a different question and is asked by adding `is_own`: for
    a reader, a family row that is not one of her own people is the world
    owner's household.

    A row in a SHARED roster may answer whose, by naming that character
    instead of saying yes: `"family": "<roster key>"`. A promoted character's
    mother and brother stay on the world's roster so that her own process can
    resolve them, and to everybody else in that world they read as two more
    people in the group -- which is how the next character promoted out of it
    came up holding a relationship meter on somebody else's mother. Named, the
    row is family to her and to nobody else, and the owner's answer is
    unchanged."""
    rec = rec_of(config, who)
    if not rec:
        return False
    flag = rec.get("family")
    if isinstance(flag, str) and flag.strip():
        return same(config, flag, handle(config))
    if flag is not None:
        return bool(flag)
    return str(rec.get("role_id") or "") in FAMILY_ROLES


def family_of(config, who):
    """The roster key of the character whose family this person is, when the
    row says so, and "" when it does not."""
    rec = rec_of(config, who) or {}
    flag = rec.get("family")
    return flag.strip() if isinstance(flag, str) else ""


def witnessed(config, who, ex):
    """Was this person in the room where that exchange happened?

    The group is every friend's; a LINE thread, a call and the kitchen belong
    to their two ends. One rule, because two readers need it and they must
    agree: what a person's own history shows them (`sim/thread.py`) and what
    counts as having put something in front of them (`sim/commitments.py`).
    Written twice, they would drift, and a promise settled against a room the
    other reader says she was never in is a promise nobody can audit."""
    if str((ex or {}).get("kind", "")) == "group":
        # The group chat is the friend group, and SOMEBODY's household is out
        # of it whoever's it is. `is_family` answers "is this my family", which
        # is the right question for the meters and the wrong one here: a
        # promoted character's mother and brother stay on the world's roster
        # so her own process can resolve them, they answer no to that
        # question, and every group turn the owner copied into the world file
        # named the two of them as having been in a school group chat.
        return not is_family(config, who) and not family_of(config, who)
    return same(config, (ex or {}).get("who", ""), who)


def everyone(config):
    """role_id -> record, for the callers that need to walk the cast."""
    return dict(_table(config)["people"])


def meter_rows(config):
    """({roster key: the row to seed a relationship meter from}, {key: why not}).

    The one statement of who this character may hold a meter on, so that the
    save's first seeding and the pass that repairs a save seeded wrong cannot
    give two answers.

    Everybody on her roster, minus:

      herself     -- a character promoted out of somebody else's cast is a row
                     in that cast, and her save carried a bond with that row at
                     closeness 45, under her own nickname;
      the world owner's household -- a mother in the world's cast is the world
                     owner's mother; hers is in her own file, under a role id
                     of her own;
      him         -- when her sheet says she has no chat with him at all, the
                     row is the other girl's side of one.

    A person the roster has and neither cast file gives numbers for -- the girl
    whose world she reads, who is the file's keeper and not one of its people
    -- is seeded from her own sheet's opening values (`people.<key>.opens_at`),
    and is seeded without numbers, loudly, when the sheet has none: choosing a
    closeness for somebody is authoring, not seeding."""
    t = _table(config)
    rows, refused = {}, {}
    ex = getattr(getattr(config, "character", None), "existence", None)
    with_him = str(getattr(ex, "with_him", "chat") or "chat").lower()
    sheet_people = (getattr(config, "character_sheet", None) or {}).get("people") or {}
    # in the order the files have them, so that a save seeded before this
    # existed and one seeded now hold the same rows in the same order
    order = list(t["rows"])
    order += [rec.get("key") or role for role, rec in t["people"].items()
              if role != "self" and (rec.get("key") or role) not in t["rows"]]
    for key in order:
        rec = rec_of(config, key)
        role = str(rec.get("role_id") or "")
        if not rec or role == "self":
            continue
        if role == "partner" and with_him == "none":
            refused[key] = "she has no chat with him at all (her sheet's `with_him`)"
            continue
        if is_family(config, key) and not is_own(config, key):
            refused[key] = ("the household in the world's cast is the world owner's; "
                            "hers is her own file's")
            continue
        whose = family_of(config, key)
        if whose and not same(config, whose, handle(config)):
            refused[key] = ("this is %s's mother or brother, and a character does not hold a "
                            "meter on another character's family" % whose)
            continue
        row = dict(t["rows"].get(key) or {})
        if "closeness" not in row:
            # a sheet may describe her people in a sentence each rather than in
            # rows, and a string has no opening values in it
            _sp = sheet_people.get(key)
            opens = (_sp.get("opens_at") or {}) if isinstance(_sp, dict) else {}
            if opens:
                row = {"role_id": rec.get("role_id") or role, "name": rec.get("name") or key,
                       "role": str(row.get("role") or ""),
                       "closeness": opens.get("closeness"), "standing": opens.get("standing"),
                       "tension": opens.get("tension")}
                row = {k: v for k, v in row.items() if v not in (None, "")}
            else:
                row = {k: v for k, v in row.items() if not str(k).startswith("_")}
                logger.log(f"[roster] {key} is on her roster with no numbers in either cast "
                           f"file and no opening values on her sheet (people.{key}.opens_at); "
                           f"the meter is seeded flat")
        rows[key] = row
    return rows, refused


UNSET = "unset"


def flat_own_meters(config):
    """{key: why} for each of HER OWN people whose meter would be seeded at
    closeness 0, standing 0, tension 0 with nothing on the row saying that was
    decided.

    Zero is not a small number here: it is what a row carries when nobody has
    chosen one. A promoted character's household stays on the world owner's
    roster, where a zero means the owner has never met the person, and her own
    cast file was written from those rows -- so the two people she lives with
    were seeded into her save as strangers and stayed there.

    A row that means it says so: `"numbers": "unset"`, which is also how the
    owner's roster carries a household that is not hers to hold a meter on.

    `docs/seamless-additions-plan.md` step 3."""
    t = _table(config)
    rows, _refused = meter_rows(config)
    out = {}
    for key, row in rows.items():
        if not is_own(config, key) or role_of(config, key) == "self":
            continue
        if str((t["rows"].get(key) or {}).get("numbers") or "").lower() == UNSET:
            continue
        stated = [row.get(k) for k in ("closeness", "standing", "tension")]
        if any(v is None for v in stated):
            # nobody wrote a number for this person anywhere: not in either
            # cast file and not in her sheet's opening values. `meter_rows`
            # says so in the log and seeds the meter flat. What this is about
            # is a row that STATES zero, which reads as a decision and is not
            # one.
            continue
        if any(float(v or 0) for v in stated):
            continue
        out[key] = ("closeness, standing and tension are all zero and nothing on the row says "
                    "that was decided (a row that means it carries \"numbers\": \"unset\")")
    return out


def is_own(config, who):
    """Is this person HERS to plan, speak and open a room with. Everybody
    is, for the character who keeps her world; in a world she only reads,
    the people in her own cast file (`own_cast_file`) and nobody else."""
    if not getattr(config, "world_reader", False):
        return True
    rec = rec_of(config, who)
    return bool(rec) and bool(rec.get("own")) and rec.get("role_id") != "self"


def own_keys(config):
    """The roster keys of her own people (all of the cast for an owner)."""
    return [r["key"] for r in _table(config)["people"].values()
            if r.get("role_id") != "self" and is_own(config, r["key"])]


def _outside_names(config):
    """Every name that means somebody in the world who is NOT one of her own
    people and is not her: the roster of the world she reads, minus her
    circle. Empty for the character who keeps her world -- everybody there is
    hers -- so nothing below it costs her a byte."""
    t = _table(config)
    outside = {role for role, rec in t["people"].items()
               if role != "self" and not is_own(config, rec.get("key", ""))}
    if not outside:
        return []
    return sorted((n for n, role in t["alias"].items() if role in outside and len(n) >= 2),
                  key=len, reverse=True)


def mentions_outside(config, text):
    """Does this line name somebody her own circle has never heard of?

    Her own people are hers alone: they are not at her school, they are not in
    the group chat, and a line about somebody in it put in front of one of
    them is a line about a stranger. The lines are shared stores -- what the
    day settled, an open thread -- so the question is asked of the text, in
    every form the roster knows a name by.

    Always False for the character who keeps her world: there is nobody
    outside her own circle there."""
    s = str(text or "")
    if not s.strip():
        return False
    low = s.lower()
    for n in _outside_names(config):
        if n.isascii():
            if re.search(r"(?<![a-z0-9])" + re.escape(n) + r"(?![a-z0-9])", low):
                return True
        elif n in s:
            return True
    return False


def only_own(config, lines):
    """`lines` with every one that names somebody outside her circle dropped."""
    return [x for x in (lines or []) if not mentions_outside(config, x)]


# ---------------- who speaks for herself ----------------
#
# A cast row may carry one more field, `agent`, holding the hub id her own
# process registers under. It is the operator's statement that this person is
# no longer only somebody in the record: she runs beside this character, with
# her own config, her own save and her own model, and she says her own words.
#
# Nothing else about the row changes. Her sheet, her mechanisms, her week and
# her whereabouts stay exactly as they were, because the people who have NOT
# been promoted still speak to her through them, and this character's planner
# still needs to know where she is. What changes is one thing: the process
# that plans the day stops putting words in her mouth and asks her instead
# (`sim/rooms.py`, `docs/peer-talk.md`).


def agent_of(config, who):
    """The hub id of the process that speaks for this person, or "" when the
    words in her mouth are still this character's process's to write."""
    return str(rec_of(config, who).get("agent") or "")


def is_agent(config, who):
    """Does this person write her own turns?"""
    return bool(agent_of(config, who))


def agents(config):
    """{roster key: hub id} for everybody on the roster who runs herself.

    Empty for every character today, which is the whole of what keeps the
    unmarked path byte-for-byte what it was."""
    return {rec["key"]: rec["agent"] for rec in _table(config)["people"].values() if rec.get("agent")}


def by_agent(config, hub_id):
    """The roster record of the person whose process registers under this hub
    id, or {}. How words arriving from another process are attributed to
    somebody in this character's world rather than to a stranger."""
    hub = _norm(hub_id)
    if not hub:
        return {}
    for rec in _table(config)["people"].values():
        if _norm(rec.get("agent")) == hub:
            return rec
    return {}


def classmates(config):
    """The roster keys of the girls who are in the room with her at school.

    The day's skeleton used to carry two names in a string literal, `Miki`
    and `Yuzu`. They were recast out of `data/cast.json` as Hinako and Aya
    and the literal was never touched, so on the first school day of term
    the planner seated her at lunch with two people the roster had never
    heard of: `role_of` returned nothing for either, so no bond, no
    sentiment, no beat and no exchange could key on them, and the director
    wrote them into the scene as decoration over an empty record. Who is at
    her school is a fact about a person, so it lives on the person."""
    return [rec["key"] for _role, rec in _table(config)["people"].items()
            if rec.get("school") == "same"]

def one_name(config, text):
    """`text` with every roster HANDLE replaced by the name the record uses.

    A prompt is assembled from many stores, and some of them keep English
    prose a model wrote months of character-time ago: "Aya spent the afternoon
    at the stationery store" from `cast_life`, "Hinako's birthday is close"
    from an arc, a beat gist in the planner's English. Those sat in the same
    prompt as a sheet saying 前田亜矢 and a transcript where every line is
    前田亜矢 -- two names for one girl, which is the fault this table exists to
    stop. Only capitalised handles: `mom`, `dad` and `him` are English words
    before they are keys, and replacing them mangles the prose they sit in."""
    import re
    pairs = []
    for _role, rec in _table(config)["people"].items():
        for h in {rec.get("key", ""), rec.get("name", "")}:
            nm = rec.get("record") or rec.get("ja") or ""
            if h and nm and h[:1].isupper() and h != nm:
                pairs.append((h, nm))
    # longest first, so "Rena-chan" is not half-taken by a shorter handle
    for h, nm in sorted(set(pairs), key=lambda x: -len(x[0])):
        text = re.sub(r"\b" + re.escape(h) + r"\b", nm, text)
    return text
