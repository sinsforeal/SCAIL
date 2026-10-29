"""What a work is, and who answers about it -- one path, whatever named it.

A work reaches her three ways: he types its name, he opens its page, or her
own sight lands on it. Each of those used to resolve it for itself, and on
2026-09-03 all three failed on the same title in the same evening: the page
in front of him was filed as a person and never asked about, the automatic
lookup spent a web search and came back with an unrelated 1967 show, and the
one place that had the answer -- her own record, and the roles the knowledge
base lists for her -- was asked by nobody. She denied a part she had played.

So the question "what is this thing, and was she in it" is answered here,
once, in one order, and the answer is written to one record.

**The order is cheapest-and-surest first.** Every step but the last is local
sqlite or a file already in memory, so the whole resolution costs
milliseconds and no model call:

  1. what she already knows by name (`sim/known.py`) -- and if a record
     answers, NOTHING is fetched: that record is the answer, which is what
     stops the same title being bought twice from two directions;
  2. his own list, for the canonical title and the MyAnimeList id (a title
     he has watched is a work, whatever the page's brackets say);
  3. the roles the knowledge base lists for her (`AnimeKB.roles_of`), matched
     on the work's title, the page's English alias, the id, and the
     character's name -- so a character's page for a part she played
     resolves as hers too;
  4. her own record (`sim/lore.py`), which is the authority on what a part
     meant to her and carries the work's Japanese name in its own tags --
     which is how a romaji page title reaches a record written in Japanese
     without a network call;
  5. a person or a character the knowledge base knows by that name: not a
     work, and never searched;
  6. a web search -- only when the thing is a work, nothing above knew it,
     and the caller allows one.

**Whoever answers decides what kind of thing it is.** A page's brackets
cannot: on MyAnimeList "B-gata H-kei (Yamada's First Time: B Gata H Kei)" is
a work and "Mitsuba Marui (Mitsudomoe)" is a character, and they are the same
shape. So the shape may say "unknown" and the knowledge base settles it.

**"Was she in it" has THREE answers, not two.** `hers` was a boolean, so
"she is in it" and "nothing here knew" were the same value, and on 2026-09-04
the second character told him she played a part in a work she has never been
in -- with no cast information of any kind in front of the model to contradict
it. `her_part_verdict` answers yes, no or not-checked, and **a flat no is only
said when two independent local tables agree**: her own mirrored filmography
has no row for the work, AND the work's own cast is mirrored and does not name
her. Where the second is missing the answer is not-checked, and not-checked
says nothing at all -- 222 of his 701 titles have no mirrored cast, and works
she really is in are among them, so a check built on the cast table alone
would have answered "not yours" about her own parts. Her filmography is the
authority; the cast is the second witness. Everything is read from the
machine's mirror (`data/mal_history.db`), read-only, no fetch: a verdict costs
two indexed sqlite reads and no model call, and a missing table is silence
rather than a guess.

**Who she is on that list is an id** (`character.mal_person_id`), never a
name: her given name alone matches nine other people in the cast rows by
substring. The id is also the switch -- a character with none never reads the
mirror and never gets a line.

**One record.** Whatever is found is written once, to `known_things`, with
who wanted it (`asked_by`), whether it is hers, the part, the verdict, the id,
and when it was last in front of him. Her sight's `glance_last`, the situation line the
persona pins, the automatic lookup's idea of what is open in front of him and
the lore retrieval's offered set all read that one row, so nothing here can
name a stale show while another part of the same tick names the right one.
"""
import re
import time

import logger
from sim import sight

# The kinds of record that mean "a part she played, or a work she was in".
# `role` is the character, `career` the year it happened in, `work` the thing
# itself; her record for the 2010 lead that started all this is a `career`
# one, and a check for `role` alone (which is what the glance had) matches
# none of the three.
ROLE_KINDS = ("role", "career", "work")


def norm(s):
    """A name with the punctuation taken out, for comparing two spellings of
    one title: the same rule `AnimeKB` uses, so an id resolved there and a
    name matched here cannot disagree."""
    return re.sub(r"[^a-z0-9぀-ヿ一-鿿]", "", str(s or "").lower())


def _tokens(s):
    """The words of a name, for a person written either way round: a page
    says "Mitsuba Marui" and a cast row says "Marui Mitsuba"."""
    return frozenset(w for w in re.split(r"[^a-z0-9぀-ヿ一-鿿]+", str(s or "").lower()) if w)


def _clean(names):
    out, seen = [], set()
    for n in names or []:
        n = " ".join(str(n or "").split())
        if len(n) < 2 or n.lower() in seen:
            continue
        seen.add(n.lower())
        out.append(n)
    return out


def _near(a, b):
    """One name inside the other, when both are long enough for that to mean
    something: "bocchitherock" in "bocchitherockmovie" and never "girl" in
    "girlshigh"."""
    a, b = norm(a), norm(b)
    if not a or not b:
        return False
    if a == b:
        return True
    return len(a) >= 6 and len(b) >= 6 and (a in b or b in a)


# ---------------- the local sources ----------------

def his_title(anime_kb, names):
    """(anime_id, title) for the first of these names that is a title in his
    own list. Local, strict, no network: this decides that a thing is a WORK
    when the page's brackets cannot.

    The RANKED answer (`AnimeKB.resolve_strict`), which is nothing at all
    when two entries of one franchise tie. That matters here more than
    anywhere: the verdict about whether a work is one of hers used to be
    computed from whichever entry sqlite returned first, so for the eighteen
    titles that resolved to a sibling it was a verdict about another work's
    cast. Nothing resolved means the verdict stays nobody-checked, which is
    what it already does correctly for a work with no id at all -- and
    nobody-checked says nothing to her."""
    if anime_kb is None:
        return None, None
    for n in names:
        try:
            hit = anime_kb.resolve_strict(n)
            if not hit:
                cands = anime_kb.resolve_candidates(n)
                if len(cands) > 1:
                    logger.log(f"[resolver] {n!r} could be "
                               + " or ".join(f"mal:{c['aid']} {c['title']}" for c in cands[:3])
                               + "; nothing is said about whose work it is")
        except Exception as e:
            logger.log(f"[works] his list not read: {type(e).__name__}")
            return None, None
        if hit:
            return hit[0], hit[1]
    return None, None


def her_role(config, anime_kb, names, aid=None):
    """The role the knowledge base lists for HER in this work, as
    (anime_id, anime, character), or None.

    Matched four ways, because a page names a work four ways: the id when the
    window carried one, the work's title, the page's English alias, and the
    character's own name -- a character's page is a page about a part, and if
    the part is hers it is hers.

    Who she is on that list is a config key (`watching.her_seiyuu_name`),
    never her chat name: her given name alone matches nine other people in
    the cast rows by substring, and which of them answered was down to the
    order sqlite happened to return."""
    if anime_kb is None:
        return None
    who = str(getattr(getattr(config, "watching", None), "her_seiyuu_name", "") or "").strip()
    if not who:
        return None
    try:
        roles = anime_kb.roles_of(who)
    except Exception as e:
        logger.log(f"[works] her roles not read: {type(e).__name__}")
        return None
    want = [n for n in names if n]
    toks = {_tokens(n) for n in want}
    for row in roles or []:
        r_aid, an, ch = row[0], row[1], row[2]
        if aid and r_aid and int(aid) == int(r_aid):
            return (r_aid, an, ch)
        if any(_near(an, n) for n in want):
            return (r_aid, an, ch)
        if ch and (_tokens(ch) in toks or any(norm(ch) == norm(n) for n in want)):
            return (r_aid, an, ch)
    return None


# ---------------- was she in it: yes, no, or nobody checked ----------------

# What a verdict looks like when nothing could be established. `why` is for
# the log and for the boot line; nothing addressed to her is ever built from a
# not-checked verdict.
NOT_CHECKED = {"verdict": "unknown", "parts": [], "who_instead": (), "aid": None,
               "title": "", "credits": 0, "cast_at": 0, "why": ""}


def her_person_id(config):
    """Which person on MyAnimeList this character IS, as a string, or "".

    Empty is the honest answer for somebody who has never been in anything,
    and it is what switches the whole check off: `Config.REQUIRES` turns an
    empty id into the missing property the `role_check` section needs, so the
    first character's boot prints why and no code here is ever reached for
    her."""
    ch = getattr(config, "character", None)
    return str(getattr(ch, "mal_person_id", "") or "").strip()


def role_check_on(config):
    """Is the check live for this character: the section on AND an id to be."""
    rc = getattr(config, "role_check", None)
    if rc is None or not getattr(rc, "enabled", False):
        return False
    return bool(her_person_id(config))


def _name_tokens(who):
    """Her own name as words, from the mirror's row for her id rather than
    from anything spelled in shared code."""
    toks = set()
    for form in ((who or {}).get("name", ""), (who or {}).get("name_jp", "")):
        toks |= set(_tokens(form))
    return {t for t in toks if len(t) >= 3}


def _near_name(cast, mine):
    """The part whose name most resembles hers, and who really plays it:
    (character, actress). This is the specific correction the 2026-09-04
    incident needed -- the work she claimed has a main character who shares
    her given name and is played by somebody else -- and it is the ONLY name
    from a cast list that is ever put in front of her."""
    best = None
    for ch, _billing, va, _pid in cast or []:
        share = _tokens(ch) & mine
        if not share:
            continue
        rank = (len(share), max((len(x) for x in share), default=0))
        if best is None or rank > best[0]:
            best = (rank, (ch, va))
    return best[1] if best else ()


def her_part_verdict(config, anime_kb, names, aid=None):
    """Is this work hers? A dict whose `verdict` is "yes", "no" or "unknown".

    yes -- her mirrored filmography has a row for it, matched the four ways a
      page names a work: the id, the work's title, the page's English alias,
      and the character's own name. `parts` is [(character, billing, year)].
    no -- the work resolved to a MyAnimeList id, her filmography is mirrored
      and not stale past `role_check.person_refresh_days`, nothing in it
      matches, and the work's own cast IS mirrored without her in it.
      `who_instead` names the part whose name resembles hers when
      `role_check.say_who_instead` is on.
    unknown -- anything else, and it says nothing to her.

    Local and read-only throughout. This is called from reply paths, so it
    must never fetch: a title nobody has mirrored is unknown, and going and
    looking is the watching worker's business, off the main thread."""
    if not role_check_on(config):
        return dict(NOT_CHECKED, why="the role check is off for this character")
    if anime_kb is None:
        return dict(NOT_CHECKED, why="his mirror is not open")
    rc = config.role_check
    pid = her_person_id(config)
    try:
        who = anime_kb.person_row(pid)
    except Exception as e:
        logger.log(f"[roles] her row on his mirror not read: {type(e).__name__}")
        return dict(NOT_CHECKED, why="her row could not be read")
    if not who or not who.get("credits"):
        return dict(NOT_CHECKED, why="her filmography is not mirrored")
    want = _clean(list(names or []))
    if not want and not aid:
        return dict(NOT_CHECKED, why="nothing named a work")
    try:
        credits = anime_kb.credits_of(pid)
    except Exception as e:
        logger.log(f"[roles] her credits not read: {type(e).__name__}")
        return dict(NOT_CHECKED, why="her credits could not be read")
    out = dict(NOT_CHECKED, aid=(int(aid) if aid else None),
               title=(want[0] if want else ""), credits=len(credits))
    toks = {_tokens(x) for x in want}
    # One part per CHARACTER, not one per credit row. A part she has carried
    # through a franchise has nine rows and is one part; naming it nine times
    # would make a cast list out of one sentence. The row for the id we were
    # handed wins, so the billing and the year are the thing in front of her
    # rather than the franchise's first entry.
    by_char, hit_rows, hit_aid, hit_title = {}, 0, None, ""
    for r_aid, an, ch, billing, year in credits:
        exact = bool(aid and r_aid and int(aid) == int(r_aid))
        same = exact
        if not same and any(_near(an, x) for x in want):
            same = True
        if not same and ch and (_tokens(ch) in toks or any(norm(ch) == norm(x) for x in want)):
            same = True
        if not same:
            continue
        hit_rows += 1
        key = norm(ch) or str(r_aid)
        if key not in by_char or exact:
            by_char[key] = (ch, billing, year)
        if exact or hit_aid is None:
            if exact or not hit_aid:
                hit_aid, hit_title = r_aid, an
    if by_char:
        out.update(verdict="yes", parts=list(by_char.values())[:3],
                   aid=out["aid"] or hit_aid, title=hit_title or out["title"],
                   why=f"{hit_rows} row(s) of her {len(credits)} credits, "
                       f"{len(by_char)} part(s)")
        return out
    # Nothing of hers matched. That is not yet a no: the work has to be a work
    # this mirror can name, her filmography has to be recent enough to be
    # believed as complete, and the work's own cast has to be here to agree.
    if not out["aid"]:
        t_aid, t_title = his_title(anime_kb, want)
        if t_aid:
            out["aid"] = t_aid
            out["title"] = out["title"] or (t_title or "")
    if not out["aid"]:
        return dict(out, why="the work has no MyAnimeList id here, so nothing can be said")
    days = float(getattr(rc, "person_refresh_days", 30) or 30)
    age_d = (time.time() - float(who.get("fetched_at") or 0)) / 86400.0
    if age_d > days:
        return dict(out, why=f"her filmography was mirrored {age_d:.0f} days ago, past {days:.0f}")
    try:
        cast_at, cast = anime_kb.cast_mirrored(out["aid"])
    except Exception as e:
        logger.log(f"[roles] the cast of {out['aid']} not read: {type(e).__name__}")
        return dict(out, why="the cast could not be read")
    if not cast_at or not cast:
        return dict(out, why="nobody has mirrored this work's cast")
    try:
        pid_i = int(pid)
    except (TypeError, ValueError):
        pid_i = 0
    if any(p == pid_i for _ch, _b, _va, p in cast):
        # The two witnesses disagree, which has never happened on this mirror
        # (63 of her works have a mirrored cast and all 63 name her). If it
        # ever does, nothing is asserted either way.
        logger.log(f"[roles] {out['aid']}: the cast names her and her filmography does not; "
                   f"nothing said either way")
        return dict(out, why="the two tables disagree")
    out["cast_at"] = cast_at
    if getattr(rc, "say_who_instead", True):
        out["who_instead"] = _near_name(cast, _name_tokens(who))
    return dict(out, verdict="no",
                why=f"none of her {len(credits)} credits, and the cast of {len(cast)} does not name her")


def verdict_line(config, v, name, t):
    """The one line she reads about it, in her language, or "" for silence.

    The wording is the program's (`sim/sight.py`), so a character who lives
    on his machine and one who is told by an app each say it as she would.
    Nothing is ever built from a not-checked verdict: silence is the answer
    when nothing was established, and a line hedged with "as far as I know"
    would be the same invention with a qualifier on it."""
    if not v or v.get("verdict") not in ("yes", "no"):
        return ""
    name = " ".join(str(name or v.get("title") or "").split())
    if not name:
        return ""
    if v["verdict"] == "yes":
        parts = list(v.get("parts") or [])
        if not parts:
            return ""
        _ch, _billing, year = (list(parts[0]) + ["", "", 0])[:3]
        # What named the work may have been the PART: a character's page is a
        # page about a part, and if the part is hers the work is hers. The
        # work's slot then takes the work's own title rather than the
        # character's name, which read as "the work Takamachi Nanoha".
        if any(norm(name) == norm(c) for c, _b, _y in parts) and v.get("title"):
            name = " ".join(str(v["title"]).split())
        # And a part she has carried through a franchise matches many works
        # with many years; naming the earliest states it as the year of the
        # thing in front of her. One work matched, one year said.
        y = _year(year) if len(parts) == 1 else ""
        # Two at most. She has voiced three parts in one show and the line is
        # not a cast list; the existing wording named two and this keeps that.
        who_en = "; ".join(_billed(c, b, True) for c, b, _y in parts[:2])
        who_ja = "、".join(_billed(c, b, False) for c, b, _y in parts[:2])
        return t(*sight.w2(config, "role_yes", n=name, who_en=who_en, who_ja=who_ja,
                           y_en=(f", {y}" if y else ""),
                           y_ja=(f"{y}年の作品。" if y else "")))
    line = t(*sight.w2(config, "role_no", n=name))
    who = v.get("who_instead") or ()
    if len(who) == 2 and who[0] and who[1]:
        line += t(*sight.w2(config, "role_no_near", ch=_person(who[0]), va=_person(who[1])))
    return line


def _person(name):
    """A name off the mirror, family-given with the comma out, which is how he
    thinks of a Japanese name and so how she says it."""
    s = " ".join(str(name or "").split())
    if "," in s:
        fam, _, giv = s.partition(",")
        return f"{fam.strip()} {giv.strip()}".strip()
    return s


# How MyAnimeList bills a part, in both languages. Anything else it says
# (it uses "?" for a row with no billing) renders as no billing at all rather
# than as a word she would not use.
_BILLING = {"Main": ("a lead", "主演"), "Supporting": ("a supporting part", "脇役")}


def _billed(ch, billing, en):
    """A part and how it was billed, in one language: "Tsukishima Shiori (a
    supporting part)" or "Tsukishima Shiori（脇役）". A billing MyAnimeList does
    not give (it writes "?") renders as the name alone."""
    b = _BILLING.get(str(billing or ""), ("", ""))[0 if en else 1]
    if not b:
        return _person(ch)
    return f"{_person(ch)} ({b})" if en else f"{_person(ch)}（{b}）"


def _year(year):
    """The year as a string, or "" when the credit predates the year column
    on his mirror. A zero is never printed: "0年の" is worse than silence."""
    try:
        y = int(year or 0)
    except (TypeError, ValueError):
        y = 0
    return str(y) if 1900 < y < 2200 else ""


def _name_forms(name):
    """The ways somebody would type this title: whole, and the part before the
    first separator.

    An OVA is recorded as "ゆゆ式 こまらせたり、こまらされたり" and typed as
    "ゆゆ式のOVA". The lead has to be long enough to be a name rather than a
    word -- three characters where any of them is Japanese, five for pure
    latin -- which is the same floor `sim/anime_sense.py` puts on the same
    trick, and it is what keeps "Example" out of "Example Show"."""
    whole = " ".join(str(name or "").split())
    if not whole:
        return []
    out = [whole]
    lead = re.split(r"[\s:：,、・\-–—(（\[]", whole, 1)[0].strip()
    if lead and lead != whole:
        floor = 3 if re.search(r"[぀-ヿ一-鿿]", lead) else 5
        if len(lead) >= floor:
            out.append(lead)
    return out


def _names_here(names, text):
    """The form of one of these names that appears in this text, or ""."""
    best = ""
    for nm in names or []:
        for form in _name_forms(nm):
            if form and form in text and len(form) > len(best):
                best = form
    return best


def editor_facts(config, store, texts, extra=(), max_n=None):
    """The works named here, each marked hers or not hers, for the continuity
    editor. English: this is machinery talking to itself.

    The editor had twelve labelled blocks of evidence and none of them named a
    work of hers, which is why it could not catch a part she never played --
    it caught the repetition when she said it a second time and had nothing to
    say about the claim itself. A verdict is a checkable fact, so a claim
    against it is a false statement rather than a matter of voice, and the
    flag-never-rewrite behaviour is untouched: the editor says so and SHE
    drafts again."""
    if not role_check_on(config):
        return ""
    low = " ".join(str(x or "") for x in (texts or []))
    if not low.strip():
        return ""
    cap = int(max_n if max_n is not None else getattr(config.role_check, "editor_facts_max", 6) or 6)
    seen, rows = set(), []
    def offer(name, v):
        if not v or v.get("verdict") not in ("yes", "no"):
            return
        key = (v.get("aid"), v.get("verdict"))
        if key in seen:
            return
        seen.add(key)
        rows.append((name, v))
    for name, v in (extra or ()):
        # what named a work on this tick and may have no record yet: the
        # episode he played, the page in front of him
        here = _names_here([name], low)
        if here:
            offer(name, v)
    try:
        for r in (store.get("known_things", []) or []):
            v = r.get("role") or None
            if not v:
                continue
            named = _names_here(r.get("names") or [], low)
            if named:
                offer(named, v)
    except Exception as e:
        logger.log(f"[roles] the things she knows not read for the editor: {type(e).__name__}")
    if not rows:
        return ""
    out = ["WORKS OF HERS, CHECKED AGAINST THE LOCAL MYANIMELIST MIRROR (these are"
           " checkable facts, not matters of voice: a claim of a part the list"
           " marks NOT HERS is a false statement about her own career):"]
    for name, v in rows[:cap]:
        aid = f" (MAL {v['aid']})" if v.get("aid") else ""
        if v["verdict"] == "yes":
            who = "; ".join(f"{_person(c)} ({b}{(', ' + str(y)) if y else ''})"
                            for c, b, y in (v.get("parts") or []))
            out.append(f"- {name}{aid} -- HERS. She plays {who}.")
        else:
            near = ""
            w = v.get("who_instead") or ()
            if len(w) == 2 and w[0] and w[1]:
                near = (f" The part whose name resembles hers is {_person(w[0])},"
                        f" played by {_person(w[1])}.")
            out.append(f"- {name}{aid} -- NOT HERS. Her mirrored filmography holds"
                       f" {v.get('credits') or 0} credits and none is in this work, and the"
                       f" work's own cast is mirrored and does not name her.{near}"
                       f" Any claim of a part in it is false.")
    return "\n".join(out)


def named_in(config, store, text, extra=()):
    """Does this text name a work a verdict exists for? The reason string for
    the continuity editor's gate, or "".

    The gate skips the editor call unless the draft carries a number, a run
    shared with a recent message, or a word from a recent fact about him. Her
    false claim tripped none of the three and the call was skipped, so the
    check would have been built and never asked about the sentence it exists
    for."""
    if not role_check_on(config):
        return ""
    low = str(text or "")
    if not low.strip():
        return ""
    for name, v in (extra or ()):
        if not (name and v and v.get("verdict") in ("yes", "no")):
            continue
        here = _names_here([name], low)
        if here:
            return f"the draft names {here}, a work the mirror has a verdict on"
    try:
        for r in (store.get("known_things", []) or []):
            v = r.get("role") or None
            if not v or v.get("verdict") not in ("yes", "no"):
                continue
            named = _names_here(r.get("names") or [], low)
            if named:
                return f"the draft names {named}, a work the mirror has a verdict on"
    except Exception as e:
        logger.log(f"[roles] the gate could not read what she knows: {type(e).__name__}")
    return ""


# ---------------- a verdict that rests on what HIS list holds ----------------
#
# The other half of the same question. `her_part_verdict` answers "was she in
# it" off her own mirrored filmography; this answers "is this title on his
# list at all", which is what a continuity verdict rests on when it says she
# cannot claim not to know a show because she has seen his list. On 2026-09-06
# the editor failed an honest draft on exactly that ground and the title is not
# on his list (`data/retired/20260906_1831_yanineko_check/REPORT.md`).

# The words a verdict uses when its ground is his own list of what he watches.
_HIS_LIST = re.compile(r"\bhis\s+(anime\s+|mal\s+)?(list|shelf|watch\s?list|watchlist|history)\b"
                       r"|\bmyanimelist\b|\bmal\s+list\b|\banime\s+list\b", re.I)
# and a claim of not knowing a thing, which is what makes the list the ground
_NOT_KNOWING = re.compile(r"claims?\s+(not\s+to\s+know|she\s+does\s?n[o\u2019']?t\s+know)"
                          r"|does\s?n[o\u2019']?t\s+know|pretend(s|ing)?\s+not\s+to\s+know"
                          r"|never\s+(seen|heard|watched)|has\s?n[o\u2019']?t\s+seen", re.I)
_A_WORK = re.compile(r"\b(anime|manga|show|series|movie|film|ova|ona|episode|game)\b", re.I)
# The words that LEAD a claim rather than name a thing. A verdict says "she
# claims she doesn't know the smoking cat anime", and the title in that
# sentence is the last three words of it; without peeling these off the phrase
# handed to his list was "t know the smoking cat anime (", which resolves to
# nothing however many of his titles it is compared with.
_LEADS = frozenset("""a an the that this his her their some any one it its
    she he they we you i know knows knowing known knew seen see saw watch
    watched watching heard hear about of on in at from and but not never even
    ever does doesnt don dont didn didnt did do is isnt was wasnt are arent
    were been being has hasnt have havent had cant wont ive im shes hes
    t s claims claim claiming pretend pretends pretending say says said
    thinks think really just still also""".split())
# A word for a KIND of thing is not the name of one, and "anime" is in every
# list summary ever shown to her, so left in it satisfied the second witness
# on its own and the verdict stood.
_JUST_A_KIND = frozenset("anime manga show shows series movie film ova ona "
                         "episode game one thing".split())


def title_phrases(text, limit=14):
    """The title-shaped phrases in a sentence about a work, longest first.

    Three shapes, because a verdict names a work the way a person does: in
    brackets or quotes, as the words in front of a word like "anime" ("the
    smoking cat anime"), or as a run of kana and kanji. Every tail of the
    words before the work word is offered, with the leading claim words
    peeled, because which of them is the title is exactly what is not known
    yet -- and one that is a title resolves while the rest resolve to
    nothing."""
    t = str(text or "")
    out = []

    def bare(w):
        return re.sub(r"[^a-z0-9]", "", str(w).lower())

    def keep(p):
        p = " ".join(str(p or "").split()).strip(" .,!?;:'\"()[]\u2019")
        while " " in p and bare(p.split(" ", 1)[0]) in _LEADS:
            p = p.split(" ", 1)[1].strip()
        p = p.strip(" .,!?;:'\"()[]\u2019")
        floor = 3 if re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", p) else 4
        if (len(p) >= floor and bare(p) not in _LEADS and bare(p) not in _JUST_A_KIND
                and p not in out):
            out.append(p)

    for m in re.finditer('\u300c([^\u300d]{2,60})\u300d|\u300e([^\u300f]{2,60})\u300f'
                         '|"([^"]{3,60})"' + r"|'([^']{3,60})'", t):
        keep(next((g for g in m.groups() if g), ""))
    for m in re.finditer(r"((?:[A-Za-z0-9][A-Za-z0-9'\u2019\-]*\s+){1,5})"
                         r"(anime|manga|show|series|movie|film|ova|ona|game)\b", t, re.I):
        words, work = m.group(1).split(), m.group(2)
        for i in range(len(words)):
            keep(" ".join(words[i:] + [work]))
            keep(" ".join(words[i:]))
    for m in re.finditer(r"[\u3040-\u30ff\u4e00-\u9fff]{2,30}", t):
        keep(m.group(0))
    out.sort(key=len, reverse=True)
    return out[:limit]


def his_list_holds(anime_kb, phrases):
    """Does his own list hold any of these titles? (verdict, title, why),
    the verdict being "yes", "no" or "unknown".

    Local and read-only, through the same ranked resolution the resolver uses
    (`AnimeKB.resolve_candidates`, `docs/resolver.md` §3.2), so a title that
    is on his list under another spelling still answers yes. "unknown" when
    nobody could look: no mirror open, or a mirror with no list in it."""
    if anime_kb is None:
        return "unknown", "", "his list is not open here, so nothing can be said"
    try:
        n = len(anime_kb.entries())
    except Exception as e:
        logger.log(f"[roles] his list not read: {type(e).__name__}")
        return "unknown", "", "his list could not be read"
    if not n:
        return "unknown", "", "his list is not mirrored here"
    for p in phrases or ():
        try:
            cands = anime_kb.resolve_candidates(p)
        except Exception:
            cands = []
        if cands:
            return "yes", p, (f"{p!r} is mal:{cands[0]['aid']} {cands[0]['title']} "
                              f"on his list of {n}")
    return "no", (phrases[0] if phrases else ""), (f"none of {len(phrases or ())} title(s) named "
                                                   f"is one of the {n} on his list")


def list_claim_check(config, anime_kb, problem, draft="", seen=""):
    """Does a continuity verdict rest on what his list holds, and does it?

    `problem` is the checker's own sentence, `draft` what she wrote, `seen`
    what she has actually been SHOWN of him (his list as she reads it, the
    notes she has read, the digest) -- the second witness, and deliberately
    not the conversation: his own message naming a thing is what she is
    answering, never evidence that she has seen it.

    A flat "his list does not hold it" needs both witnesses to be silent, the
    same rule `her_part_verdict` is written to. Anything else is "unknown",
    and unknown leaves the verdict exactly as it was."""
    out = {"rests": False, "verdict": "unknown", "subject": "", "why": ""}
    text = str(problem or "")
    if not text.strip():
        return out
    out["rests"] = bool(_HIS_LIST.search(text)) or bool(_NOT_KNOWING.search(text) and _A_WORK.search(text))
    if not out["rests"]:
        return dict(out, why="the verdict does not rest on his list")
    phrases = title_phrases(text)
    low = str(draft or "").lower()
    # the phrase she actually wrote comes first: that is the claim, and the
    # checker's paraphrase of it is not
    phrases.sort(key=lambda p: (p.lower() in low, len(p)), reverse=True)
    if not phrases:
        return dict(out, why="the verdict names no title to check")
    verdict, subject, why = his_list_holds(anime_kb, phrases)
    if verdict != "no":
        return dict(out, verdict=("holds" if verdict == "yes" else "unknown"),
                    subject=subject, why=why)
    # the mirror places the work some other way -- her own filmography, or the
    # work's cast (`docs/role-check.md` §2). Then it is a work this machine
    # knows and the verdict is left alone.
    if role_check_on(config):
        try:
            v = her_part_verdict(config, anime_kb, phrases[:3])
        except Exception as e:
            logger.log(f"[roles] the part verdict was not asked: {type(e).__name__}")
            v = {}
        if v.get("verdict") in ("yes", "no"):
            return dict(out, verdict="holds", subject=phrases[0],
                        why=f"the mirror places {phrases[0]!r} as mal:{v.get('aid')}")
    shown = str(seen or "").lower()
    here = next((p for p in phrases if p and p.lower() in shown), "")
    if here:
        return dict(out, verdict="unknown", subject=here,
                    why=f"{here!r} is not on his list, but it is in what she has been shown of him")
    return dict(out, verdict="absent", subject=phrases[0],
                why=why + ", and it is in nothing she has been shown of him")


def her_record(lore, names):
    """(record, the line about it) from her own record for a work these names
    name, or None -- role-shaped records only, matched by name.

    Two ways in, and both are the record's own words rather than a
    resemblance: the trigger phrases somebody would type (`Lore.match`), and
    the record's title and tags, which carry the work's Japanese name beside
    the romaji one. The second is what lets a romaji page title reach a
    record written in Japanese with no call and no network."""
    if lore is None:
        return None
    kinds = set(ROLE_KINDS)
    try:
        for rec, text in lore.match(" / ".join(names)):
            if str(rec.get("kind") or "") in kinds:
                return rec, text
    except Exception as e:
        logger.log(f"[works] her record not read: {type(e).__name__}")
        return None
    try:
        hit = lore.work_named(names, kinds=kinds)
    except AttributeError:
        return None
    except Exception as e:
        logger.log(f"[works] her record not searched by title: {type(e).__name__}")
        return None
    return hit


def a_person(anime_kb, names):
    """The name of a person or a character the knowledge base knows, exactly
    -- not a work, and not a thing to search for. Exact only: `find_person`
    is generous by substring on purpose for a name he typed, and a page title
    is not a guess."""
    if anime_kb is None:
        return ""
    for n in names:
        try:
            pid, nm = anime_kb.find_person(n, search=False)
        except Exception:
            pid, nm = None, None
        if pid and (_tokens(nm) == _tokens(n) or norm(nm) == norm(n)):
            return str(nm or n)
        try:
            hit = anime_kb.find_character(n)
        except Exception:
            hit = None
        if hit:
            # (anime_id, character, role, jp_va, title, status, score)
            ch = hit[1] if isinstance(hit, (tuple, list)) and len(hit) > 1 else ""
            if ch and _tokens(ch) == _tokens(n):
                return str(ch)
    return ""


# ---------------- the one path ----------------

def identify(names, config=None, store=None, clock=None, known=None, anime_kb=None,
             lore=None, search=None, site="", mal_id=None, shape="", why="",
             allow_search=True, access=None, asked_by="arrived", in_front=False):
    """What this thing is, and who answered. Returns the one record, or None
    when the names are not worth a record at all.

    `shape` is what whatever named it could already tell: "work" (a page that
    says so, or a term he called a work), "name" (a person), "" / "unknown"
    when it cannot tell. `search` is `Lookup.search` or None; a search runs
    only for a work nothing local knew, and only when `allow_search`.
    `in_front` marks the record as being on his screen right now, which is
    what the automatic lookup reads for its own context."""
    names = _clean(names)
    if not names:
        return None
    kind = "work" if shape == "work" else ("name" if shape == "name" else "page")
    hers, part, gist, source, aid = False, "", "", "", (int(mal_id) if mal_id else None)
    verdict = None

    # 1. what she already knows by name: the answer, and the end of it. A bare
    #    row -- a title nobody could say anything about -- is not an answer,
    #    so it only gets its stamp refreshed and the resolution goes on.
    if known is not None:
        try:
            for r in known.recall(" / ".join(names), count=False, bare=True)[:1]:
                if in_front:
                    known.seen_now(r.get("key"))
                if r.get("bare") and not r.get("hers"):
                    break
                logger.log(f"[works] {names[0]!r}: nothing fetched -- she has it as {r.get('key')}")
                return {"key": r.get("key"), "names": list(r.get("names") or names), "kind": r.get("kind") or kind,
                        "hers": bool(r.get("hers")), "part": str(r.get("part") or ""), "aid": r.get("aid"),
                        "gist": str(r.get("text") or ""), "source": r.get("source") or "",
                        "asked_by": str(r.get("asked_by") or "arrived"), "site": site,
                        # the verdict rides the row it was written on, so the
                        # glance, the lookup's context and her recall of the
                        # same work cannot answer differently on one tick
                        "role": r.get("role") or None,
                        "verdict_only": bool(r.get("verdict_only")),
                        "from_known": True, "searched": False}
        except Exception as e:
            logger.log(f"[works] what she knows not read: {type(e).__name__}")

    # 2. his own list: the canonical title and the id, and proof it is a work
    t_aid, t_title = his_title(anime_kb, names)
    if t_aid:
        aid, kind = aid or t_aid, "work"
        if t_title and not any(norm(t_title) == norm(n) for n in names):
            names.append(t_title)

    # 3. the roles the list gives her -- and, when this character has an id
    #    on that list, the three-state verdict, which is also how a work that
    #    is NOT hers becomes a thing she can be right about
    if role_check_on(config):
        verdict = her_part_verdict(config, anime_kb, names, aid=aid)
        role = None
        if verdict.get("verdict") == "yes":
            p = (verdict.get("parts") or [("", "", 0)])[0]
            role = (verdict.get("aid"), verdict.get("title"), p[0])
    else:
        # nobody has said who she is on that list: the old name-matched path,
        # which for a character with no name there answers None and costs
        # nothing
        role = her_role(config, anime_kb, names, aid=aid)
    if role:
        r_aid, an, ch = role
        hers, part, source = True, str(ch or ""), "her roles on MyAnimeList"
        aid = aid or r_aid
        if kind != "name":
            kind = "work"
        for n in (an, ch):
            if n and not any(norm(n) == norm(x) for x in names):
                names.append(str(n))
    elif verdict and verdict.get("verdict") == "no":
        aid = aid or verdict.get("aid")
        if kind != "name":
            kind = "work"
        logger.log(f"[roles] {names[0]!r}"
                   + (f" ({verdict['aid']})" if verdict.get("aid") else "")
                   + f": NOT hers -- {verdict.get('why')}"
                   + (f"; the near name is {verdict['who_instead'][0]}, played by {verdict['who_instead'][1]}"
                      if len(verdict.get("who_instead") or ()) == 2 else ""))

    # 4. her own record: the authority on what it was to her, and where the
    #    work's Japanese name comes from without a call
    rec = her_record(lore, names)
    if rec:
        r, text = rec
        hers = True
        part = part or str(r.get("title") or "")
        gist = str(text or "")[:400]
        source = ("her own record + " + source) if source else "her own record"
        if kind != "name":
            kind = "work"
        for n in [r.get("title") or ""] + list(r.get("tags") or []):
            n = " ".join(str(n or "").split())
            if len(n) >= 3 and not any(norm(n) == norm(x) for x in names):
                names.append(n)

    # 5. a person, or a character of somebody else's: nothing to look up
    if not hers and kind != "work":
        who = a_person(anime_kb, names)
        if who:
            kind = "name"
            logger.log(f"[works] {names[0]!r}: a name the list knows ({who}), not a work")
            return {"key": "", "names": names, "kind": "name", "hers": False, "part": "", "aid": None,
                    "gist": "", "source": "his history", "asked_by": asked_by, "site": site,
                    "from_known": False, "searched": False}

    # 6. the web, last: a work she has never heard of
    searched = False
    if not hers and not gist and kind == "work" and allow_search and search is not None:
        try:
            r = search(f"{_her_name(config)} {names[0]}".strip(), why=why, access=access)
        except Exception as e:
            logger.log(f"[works] search failed: {type(e).__name__}")
            r = None
        if r:
            searched = True
            gist, hers, part = str(r.get("gist") or ""), bool(r.get("hers")), str(r.get("part") or "")
            source = r.get("source") or "web"
            if r.get("known_key"):
                # the search kept its own record; this is that record
                if known is not None and in_front:
                    known.seen_now(r["known_key"])
                return {"key": r["known_key"], "names": names, "kind": kind, "hers": hers, "part": part,
                        "aid": aid, "gist": gist, "source": source,
                        "asked_by": str(r.get("asked_by") or asked_by), "site": site,
                        "from_known": bool(r.get("from_known")), "searched": True}

    if not (hers or gist or (kind == "work" and aid)):
        # he is reading about something nobody here has heard of. That is
        # scenery, and scenery does not get a record.
        return None
    key = f"work:{names[0]}" if kind == "work" else f"{kind}:{names[0]}"
    # A work the mirror says is NOT hers is not a bare row. A bare row is a
    # title nothing could say anything about, and it stays out of her
    # situation; "you are not in this one" is something to say, and it is the
    # sentence this whole path exists to make available.
    said_no = bool(verdict and verdict.get("verdict") == "no")
    bare = not (hers or gist or said_no)
    text = gist or _plain(names, part)
    # A row that exists ONLY because the mirror says the work is not hers has
    # no content of its own: its text is the title. What she is handed for it
    # is the verdict and not "you read this up earlier".
    verdict_only = bool(said_no and not gist and not part)
    out = {"key": key, "names": names[:10], "kind": kind, "hers": hers, "part": part, "aid": aid,
           "gist": text, "source": source or "his history", "asked_by": asked_by, "site": site,
           "role": (verdict if (verdict and verdict.get("verdict") in ("yes", "no")) else None),
           "verdict_only": verdict_only,
           "from_known": False, "searched": searched, "bare": bare}
    if known is not None:
        try:
            known.add(key, out["names"], kind, text, source=out["source"],
                      extra={"hers": hers, "part": part, "aid": aid, "site": site, "bare": bare,
                             "role": out["role"], "verdict_only": verdict_only,
                             "asked_by": asked_by, "seen_ts": (clock.now_ts() if (clock and in_front) else 0)})
        except Exception as e:
            logger.log(f"[works] not kept: {type(e).__name__}")
    logger.log(f"[works] {names[0]!r} -> {kind}" + (f", hers as {part}" if hers else "")
               + f" [{out['source']}]" + ("" if searched else " (nothing fetched)"))
    return out


def _her_name(config):
    """Her name as a search would have to spell it, for the one question a
    search is ever asked here: was she in this."""
    ch = getattr(config, "character", None)
    return str(getattr(ch, "name_ja", "") or getattr(ch, "name", "") or "").strip()


def _plain(names, part):
    """The record's text when nothing wrote prose: the work and the part."""
    return f"『{names[0]}』" + (f" -- {part}" if part else "")


def in_front_of_him(store, clock, config, within_minutes=None):
    """The work last resolved as being on his screen, while it is still
    there: the one record, read by the automatic lookup so its context names
    what is actually open rather than the last thing a player touched."""
    if store is None:
        return None
    mins = within_minutes
    if mins is None:
        mins = float(getattr(getattr(config, "lookup", None), "in_front_minutes", 30.0) or 30.0)
    best = None
    now = clock.now_ts() if clock else 0
    for r in (store.get("known_things", []) or []):
        ts = float(r.get("seen_ts") or 0)
        if ts <= 0 or (now - ts) > mins * 60:
            continue
        if best is None or ts > float(best.get("seen_ts") or 0):
            best = r
    return best
