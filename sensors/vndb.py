import re
import time

import logger

# The public visual-novel database (https://api.vndb.org/kana), one card per
# game: the title in both forms, the developer, the release date, the length,
# the rating, two sentences of what it is about, and the four leads with their
# Japanese names.
#
# No key and nothing in `secerts/`: reading is anonymous by the API's own
# documentation, and `POST /vn` and `POST /character` were both proved to
# answer 200 without any form of authentication. The rate limit is 200
# requests per five minutes; this makes two per game, ONCE, so his whole
# library costs sixteen calls and a new game costs two. The answer is kept in
# the MACHINE's store of what has been fetched about the world
# (`machine/retrievals.py`, kind `vn_card`) and not in a character's save: a
# game's card is the same card whoever looks it up, so one fetch serves both.
#
# The tag list is deliberately not on the card. The database's tags for these
# titles are an act-by-act description of the sex scenes, and there is nothing
# on a card that needs them: the title, the developer, the story and the cast
# are what makes a mention of the game land. Character biographies are kept
# because they are plot and personality -- but they carry `[spoiler]` markup
# inline rather than in a field of their own, and in one measured case the
# spoiler was 985 of 1,070 characters, so the markup and its contents are cut
# before anything is read.
#
# A network failure is logged by exception TYPE and never by text: a request
# exception quotes the URL it failed on.

ENDPOINT = "https://api.vndb.org/kana"
TIMEOUT = 20

_VN_FIELDS = ("title,alttitle,released,length,length_minutes,rating,votecount,"
              "description,developers{name}")
_CHAR_FIELDS = "name,original,vns{id,role}"

# how much a role counts for on the card: the leads first, and never by the
# length of the biography -- one protagonist gets 47 characters and a
# supporting spirit gets 1,070
_ROLES = {"main": 0, "primary": 1, "side": 2, "appears": 3}

_SPOILER = re.compile(r"\[spoiler\].*?\[/spoiler\]", re.S | re.I)
_LINK = re.compile(r"\[url=[^\]]*\](.*?)\[/url\]", re.S | re.I)
_CREDIT = re.compile(r"\[from[^\]]*\][\s\S]*$", re.I)
_MARKUP = re.compile(r"\[/?[a-z][^\]]*\]", re.I)


def _post(path, body):
    """One call, one retry. A transient connection reset happened about once
    in sixty calls when this was measured, and it is not a throttle."""
    import requests
    for attempt in (1, 2):
        try:
            r = requests.post(ENDPOINT + path, json=body, timeout=TIMEOUT,
                              headers={"User-Agent": "scail/1"})
            if r.status_code != 200:
                logger.log(f"[vndb] {path} answered {r.status_code}")
                return None
            return r.json()
        except Exception as e:
            logger.log(f"[vndb] {path} failed: {type(e).__name__}"
                       + (", asking again" if attempt == 1 else ""))
            time.sleep(1.0)
    return None


def plain(s):
    """The database's own markup out: the spoiler blocks with their contents,
    the cross-links down to their text, the fan-translation credit line, and
    anything else in brackets."""
    s = _SPOILER.sub(" ", str(s or ""))
    s = _LINK.sub(r"\1", s)
    s = _CREDIT.sub(" ", s)
    s = _MARKUP.sub(" ", s)
    return " ".join(s.split())


def _sentences(text, limit, count=2):
    """The first sentences of the description, whole, inside `limit`."""
    text = plain(text)
    if not text:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", text)
    out = ""
    for p in parts[:count]:
        if len(out) + len(p) + 1 > limit:
            break
        out = (out + " " + p).strip()
    return out or text[:limit]


def fetch(vndb_id, limit=600):
    """The card for one database id, as text, or "". Two calls, no cache."""
    vid = str(vndb_id or "").strip().lstrip("vV")
    if not vid.isdigit():
        return ""
    vn = _post("/vn", {"filters": ["id", "=", "v" + vid], "fields": _VN_FIELDS})
    rows = (vn or {}).get("results") or []
    if not rows:
        logger.log(f"[vndb] v{vid} has no record")
        return ""
    g = rows[0]
    title = str(g.get("title") or "")
    alt = str(g.get("alttitle") or "")
    devs = [str((d or {}).get("name") or "") for d in (g.get("developers") or [])]
    head = title + (f" ({alt})" if alt and alt != title else "")
    bits = [d for d in (devs[0] if devs else "", str(g.get("released") or "")) if d]
    if g.get("length"):
        mins = g.get("length_minutes")
        bits.append(f"length {g['length']}" + (f" ({int(mins)} min)" if mins else ""))
    if g.get("rating"):
        bits.append(f"rating {g['rating']}/100" + (f" ({int(g['votecount'])} votes)"
                                                   if g.get("votecount") else ""))
    lines = [head, " | ".join(bits)]
    about = _sentences(g.get("description"), max(120, limit // 2))
    if about:
        lines.append(about)

    cast = _post("/character", {"filters": ["vn", "=", ["id", "=", "v" + vid]],
                                "fields": _CHAR_FIELDS, "results": 100})
    people = []
    for ch in (cast or {}).get("results") or []:
        role = ""
        for v in ch.get("vns") or []:
            if str((v or {}).get("id") or "") == "v" + vid:
                role = str(v.get("role") or "")
        name = str(ch.get("name") or "")
        orig = str(ch.get("original") or "")
        if not name:
            continue
        people.append((_ROLES.get(role, 9), name, orig, role))
    people.sort(key=lambda p: p[0])
    if people:
        lines.append("Cast: " + "; ".join(
            f"{n}" + (f" ({o}, {r})" if o else f" ({r})") for _k, n, o, r in people[:4]))
    return "\n".join(l for l in lines if l)[:int(limit)]


def card(retrievals, vndb_id, limit=600):
    """The card for one game, fetched once for the MACHINE and read by both
    characters (`machine/retrievals.py`, kind `vn_card`).

    A game's card is the same card whoever looks it up, so it is the world's
    and not hers; what she made of the game is her own store's business.
    Whichever process gets there first fetches and the other reads the row."""
    vid = str(vndb_id or "").strip().lstrip("vV")
    if not vid.isdigit() or retrievals is None:
        return ""
    row = retrievals.get_or_fetch("vn_card", vid, lambda: fetch(vid, limit), model="vndb")
    return str((row or {}).get("text") or "")
