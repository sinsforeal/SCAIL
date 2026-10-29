"""What somebody has to bring up today, and whether they brought it up.

A group chat asked for "not arrangements" and given nothing else to be about
becomes a loop. Measured in the world's own record on 2026-09-07: every one
of six people's one carried thought was about the character whose world it
is, four of them the identical sentence three days running, and half of what
was going round was known to one person or to nobody, so the filter that
shows a speaker only what she has heard showed most of them nothing. The
prompt told each of them a group chat is mostly made of concrete things and
then handed them the day's plan and each other.

A pocket is the missing input: three or four concrete things ONE person
could bring up today, assembled from what already exists about her -- the
day's own record of her, what is going round that she has heard, the week's
news, the beat of whatever is running in her life, and what she is into --
each shown to at most one call and then marked, so nobody produces the same
offering twice and the operator can see which of them never reached a word.

Nobody is named here and nothing is invented here. Each program fills the
pockets of the people it writes: the character who keeps a world fills the
world's (`tomoe/cast.py`, at the compile, for the day about to start), and a
character who runs herself fills her OWN from her own material and never
from somebody else's roster (`sim/peers.py`) -- inventing for people who are
not hers is the fault the partition exists to stop.

kv `cast_pockets`: {date: {person: {"items": [{id, what, source}],
"used": [id]}}}.
"""
import logger

# days of pockets kept in the save: enough for the operator's view to see an
# item that was offered and never said, and no more
KEEP_DAYS = 7


class Pocket:
    """One store, read and written by whoever owns the people in it."""

    def __init__(self, config, store, clock):
        self.config = config
        self.store = store
        self.clock = clock

    # ---------------- the store ----------------

    def _all(self):
        rec = self.store.get("cast_pockets", {}) or {}
        return rec if isinstance(rec, dict) else {}

    def _save(self, rec):
        for d in sorted(rec)[:-KEEP_DAYS]:
            rec.pop(d, None)
        self.store.set("cast_pockets", rec)

    def row(self, date, who):
        r = (self._all().get(str(date)) or {}).get(str(who)) or {}
        return r if isinstance(r, dict) else {}

    def put(self, date, who, items):
        """Today's things for one person, replacing whatever was there.

        An item is `{"what": ..., "source": ...}`; the id is this pocket's
        own and is what `used` records, so two items with the same words are
        still two items."""
        rows = []
        for i, it in enumerate(items or []):
            what = str((it or {}).get("what") or "").strip()
            if not what:
                continue
            rows.append({"id": "p%d" % (len(rows) + 1), "what": what[:200],
                         "source": str((it or {}).get("source") or "")[:40]})
        if not rows:
            return 0
        rec = self._all()
        day = rec.setdefault(str(date), {})
        day[str(who)] = {"items": rows, "used": []}
        self._save(rec)
        return len(rows)

    def unused(self, date, who, limit=4):
        r = self.row(date, who)
        used = set(r.get("used") or [])
        return [i for i in (r.get("items") or []) if i.get("id") not in used][:int(limit or 4)]

    def mark(self, date, who, ids):
        """These were put in front of somebody who then wrote words. Recorded
        after the call, never before it: a thing offered to a call that came
        back with nothing was not offered at all."""
        ids = [str(x) for x in (ids or []) if x]
        if not ids:
            return 0
        rec = self._all()
        day = rec.get(str(date)) or {}
        r = day.get(str(who))
        if not isinstance(r, dict):
            return 0
        used = list(r.get("used") or [])
        added = [i for i in ids if i not in used]
        if not added:
            return 0
        r["used"] = used + added
        self._save(rec)
        return len(added)

    # ---------------- into a call ----------------

    def block(self, date, who, limit=4, ja=False):
        """(the lines to put in the call, the ids they were).

        The caller marks the ids once the call has come back with words. Empty
        when this person has nothing today, which is a real answer: a day with
        nothing concrete in it is a day of listening."""
        rows = self.unused(date, who, limit)
        if not rows:
            return "", []
        head = ("今日、話に出せること（それぞれ一度だけ。出さなくてもいい）:"
                if ja else
                "THINGS YOU COULD BRING UP TODAY (each once, and only if the moment is "
                "actually there -- an unsaid one is not a debt):")
        body = "\n".join("  - %s" % r["what"] for r in rows)
        return head + "\n" + body, [r["id"] for r in rows]

    # ---------------- the operator's view ----------------

    def report(self, stale_days=2):
        """What was offered, what was said, and what nobody ever brought up.

        The last is the point: an item offered for two days and never said is
        either a thing nobody would say or a thing the calls never reached,
        and both are worth seeing -- the same way `/sweep` names a feeling
        nothing reads."""
        rec = self._all()
        if not rec:
            return "pockets: nothing written yet"
        days = sorted(rec)
        today = self.clock.date_str()
        offered = said = 0
        never = []
        for d in days:
            for who, r in sorted((rec.get(d) or {}).items()):
                if not isinstance(r, dict):
                    continue
                used = set(r.get("used") or [])
                for it in (r.get("items") or []):
                    offered += 1
                    if it.get("id") in used:
                        said += 1
                    elif d < today and len([x for x in days if x > d]) >= stale_days - 1:
                        never.append("%s %s: %s" % (d, who, str(it.get("what"))[:70]))
        out = ["pockets: %d item(s) offered over %d day(s), %d reached a call"
               % (offered, len(days), said)]
        for line in never[-6:]:
            out.append("  never brought up: " + line)
        return "\n".join(out)


# ---------------- what a character who runs herself has to say ----------------

def own_items(store, t=None, limit=4):
    """A pocket for the character whose process this is, from HER material.

    Her scene, her own people's chats, what she is watching, the day's own
    record -- everything already in her save, no call and no roster but her
    own. A character in somebody else's world may not invent for that
    world's people, so nothing here reads a cast, a plan or a room she does
    not keep.

    `t` is the caller's language pair (`sim/lang.py say`), because the lines
    are addressed to her. Ordinary code, so a resident with a circle of her
    own gets a pocket too."""
    t = t or (lambda en, ja: en)
    out = []
    try:
        scene = store.get("director_current", {}) or {}
        bit = str(scene.get("sensory") or scene.get("activity") or "").strip()
        if bit:
            out.append({"what": t("what she is in the middle of: ", "いましていること: ") + bit[:140],
                        "source": "her day"})
    except Exception as e:
        logger.log(f"[pocket] her scene was not read: {type(e).__name__}: {e}")
    try:
        rows = [x for x in (store.get("cast_chat", []) or []) if isinstance(x, dict)]
        for x in reversed(rows[-4:]):
            g = str(x.get("gist") or "").strip()
            if g:
                out.append({"what": t("something from her own people: ", "自分の側の人の話: ") + g[:140],
                            "source": "her own circle"})
                break
    except Exception as e:
        logger.log(f"[pocket] her own circle was not read: {type(e).__name__}: {e}")
    try:
        wl = store.get("watchlist", []) or []
        for w in reversed(wl[-6:]):
            title = str((w or {}).get("ja") or (w or {}).get("title") or "").strip()
            if title:
                out.append({"what": t("what she is watching: ", "見ているもの: ") + title[:80],
                            "source": "her watchlist"})
                break
    except Exception as e:
        logger.log(f"[pocket] her watchlist was not read: {type(e).__name__}: {e}")
    try:
        for ev in reversed(store.recent_events(8) or []):
            text = str((ev or {}).get("text") or "").strip()
            kind = str((ev or {}).get("kind") or "")
            if text and kind not in ("cast_chat", "peer_chat"):
                out.append({"what": t("something that happened to her: ", "自分に起きたこと: ") + text[:140],
                            "source": "her own record"})
                break
    except Exception as e:
        logger.log(f"[pocket] her day's record was not read: {type(e).__name__}: {e}")
    return out[:int(limit or 4)]
