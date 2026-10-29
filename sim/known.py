"""Things she has looked up or watched, kept as things she knows, found again
by name.

A lookup used to reach exactly one reply -- the one that followed his
message -- and then survive as a 160-character fact about him under the
forgetting curve. The 600-character digest of who 丸井みつば is went into a
list only the `/lookups` command ever read, so a mention of her the next day
started from nothing. An episode he watched stayed in the room for
`watching.fresh_hours` and then left her context for good.

So a thing she has read up on is stored here with its NAMES -- as he typed
it, as the page spells it, and the aliases the page gives (みつば, 丸井みつば,
みっちゃん) -- and any later message of his that carries one of those names
brings the whole digest back into her situation, pinned, free, with no
window. Her own record works the same way (`sim/lore.py`: phrases decide the
match); this is the same idea for the things she learned from him.

kv `known_things`: [{key, names, kind, text, source, show, ts, hits}], newest
last, capped at `lookup.known_keep`. Substring match on names of two
characters or more, longest name first, at most `lookup.known_max_lines` per
message. The substring trap (`sim/lore.py` learned it: a two-character name
fires inside a longer word) is accepted here for the same reason it is there:
these are proper names he chose to type, and the alternative is a tokeniser
that is not installed.
"""

import logger
from sim import works


class KnownThings:
    def __init__(self, config, store, clock):
        self.config = config
        self.store = store
        self.clock = clock

    def _all(self):
        return list(self.store.get("known_things", []) or [])

    def add(self, key, names, kind, text, source="", show="", extra=None):
        """Keep (or replace) one thing. `names` are what he might type.

        `extra` is the rest of what the resolution found -- whether it is
        hers, the part, the MyAnimeList id, when it was last on his screen --
        written in the same breath as the row. It used to be a second pass
        over the store (`Lookup._mark_known`) and a row could exist for a
        moment without the two fields that say whose it is."""
        key = str(key or "").strip()
        text = " ".join(str(text or "").split())
        names = [str(n).strip() for n in (names or []) if n and len(str(n).strip()) >= 2]
        if not key or not text or not names:
            return False
        seen, uniq = set(), []
        for n in names:
            if n not in seen:
                seen.add(n)
                uniq.append(n)
        rows = [r for r in self._all() if r.get("key") != key]
        row = {"key": key, "names": uniq, "kind": str(kind or ""), "text": text,
               "source": str(source or ""), "show": str(show or ""),
               "ts": self.clock.now_ts(), "hits": 0}
        for k, v in (extra or {}).items():
            if k not in row:
                row[k] = v
        rows.append(row)
        keep = int(getattr(self.config.lookup, "known_keep", 200) or 200)
        self.store.set("known_things", rows[-keep:])
        logger.log(f"[known] kept {key} ({kind}): {len(uniq)} name(s), {len(text)} chars")
        return True

    def merge(self, key, names, kind, label, part, source="", show="", max_parts=6):
        """Add one labelled part to a thing, keeping the others: a show gathers
        its episodes (第7話, 第8話, 第9話...) rather than forgetting all but the
        last. The newest `max_parts` are kept and the text is their join, so a
        mention of the show brings back what he has watched of it lately."""
        key = str(key or "").strip()
        part = " ".join(str(part or "").split())
        if not key or not part:
            return False
        rows = self._all()
        cur = next((r for r in rows if r.get("key") == key), None)
        parts = [p for p in (cur.get("parts") if cur else []) or [] if p.get("label") != label]
        parts.append({"label": str(label or ""), "text": part, "ts": self.clock.now_ts()})
        parts = parts[-int(max_parts):]
        text = " / ".join(f"{p['label']}: {p['text']}" if p.get("label") else p["text"] for p in parts)
        allnames = list((cur.get("names") if cur else []) or []) + list(names or [])
        ok = self.add(key, allnames, kind, text, source=source, show=show)
        if ok:
            rows = self._all()
            for r in rows:
                if r.get("key") == key:
                    r["parts"] = parts
            self.store.set("known_things", rows)
        return ok

    def mark(self, key, fields):
        """Write fields onto a thing already kept. One owner for the write:
        the lookup patched the store itself and so did the sight."""
        rows, hit = self._all(), False
        for r in rows:
            if r.get("key") == key:
                r.update(fields or {})
                hit = True
        if hit:
            self.store.set("known_things", rows)
        return hit

    def seen_now(self, key):
        """This thing is on his screen at this moment. What is in front of
        him is a property of the thing, not a second store: the automatic
        lookup's context and her sight's line read the same row, so they
        cannot name two different shows in one tick."""
        return self.mark(key, {"seen_ts": self.clock.now_ts()})

    def get(self, key):
        return next((r for r in self._all() if r.get("key") == key), None)

    def drop(self, key):
        """Forget one thing, by key. For a record that should never have been
        kept -- a person's name answered with a random show, before results
        were judged. `/known drop <key>`."""
        rows = self._all()
        keep = [r for r in rows if r.get("key") != key]
        if len(keep) == len(rows):
            return False
        self.store.set("known_things", keep)
        logger.log(f"[known] dropped {key}")
        return True

    def remove_part(self, key, label):
        """Take one labelled part off a thing (an episode that did not really
        get watched); the thing stays if parts remain."""
        rows = self._all()
        cur = next((r for r in rows if r.get("key") == key), None)
        if not cur:
            return False
        parts = [p for p in (cur.get("parts") or []) if p.get("label") != label]
        if len(parts) == len(cur.get("parts") or []):
            return False
        if not parts:
            return self.drop(key)
        cur["parts"] = parts
        cur["text"] = " / ".join(f"{p['label']}: {p['text']}" if p.get("label") else p["text"] for p in parts)
        self.store.set("known_things", rows)
        logger.log(f"[known] {key}: part {label} removed")
        return True

    def keys(self):
        return {r.get("key") for r in self._all()}

    def listing(self):
        rows = self._all()
        if not rows:
            return "she knows nothing yet by name"
        return "\n".join(f"{r.get('key')}  [{', '.join(r.get('names') or [])}]  {r.get('kind')} via {r.get('source')} ({len(r.get('text') or '')} chars, recalled {r.get('hits') or 0}x)"
                         for r in rows)

    def recall(self, text, exclude=(), count=True, bare=False):
        """The things his text names, longest name first, capped.

        A BARE row is a work the resolution could name and had nothing to say
        about -- a title off a page in front of him that neither her record
        nor the knowledge base nor a search filled in. It is a real row,
        because what is on his screen is a property of the thing rather than a
        second store (`sim/works.py`), but it is not something she knows, so
        it stays out of her situation and does not stop a real lookup. Only
        the resolution itself asks for it."""
        text = str(text or "")
        if not text.strip():
            return []
        low = text.lower()
        ex = {str(k) for k in (exclude or ())}
        hits = []
        for r in self._all():
            if r.get("key") in ex:
                continue
            if r.get("bare") and not bare:
                continue
            best = ""
            for n in r.get("names") or []:
                if n.lower() in low and len(n) > len(best):
                    best = n
            if best:
                hits.append((len(best), r, best))
        hits.sort(key=lambda h: (-h[0], -(h[1].get("ts") or 0)))
        cap = int(getattr(self.config.lookup, "known_max_lines", 2) or 2)
        out = [h[1] for h in hits[:cap]]
        if out and count:
            rows = self._all()
            for r in rows:
                if any(r.get("key") == o.get("key") for o in out):
                    r["hits"] = int(r.get("hits") or 0) + 1
            self.store.set("known_things", rows)
            logger.log("[known] recalled by name: " + ", ".join(f"{h[2]} -> {h[1]['key']}" for h in hits[:cap]))
        return out

    @staticmethod
    def situation_line(rec, t, config=None):
        """One pinned line in her language. `t(en, jp)` is the persona's.

        A row may also carry the verdict on whether the work is HERS, written
        by the one resolution (`sim/works.py`). When it says the work is not
        hers, that is said here too and it is said every time the name comes
        back: a false part she was stopped from claiming on Tuesday is one she
        will claim again on Friday if the record she recalls is silent about
        it. A row marked `verdict_only` has nothing else in it -- its text is
        the title and no more -- and offering that back to her as something
        she read up on earlier would be a small lie, so it says the verdict
        alone."""
        src = rec.get("source") or ""
        v = rec.get("role") or None
        said = works.verdict_line(config, v, (rec.get("names") or [""])[0], t) if (config and v) else ""
        if said and rec.get("verdict_only"):
            return said
        line = t(f"you already know this one, from when you read up on it earlier ({src}) -- you have known it since before this conversation, "
                 f"so it is not something you just looked up and you never say it is; it is yours to use, not to recite: {rec['text']}",
                 f"これはもう知っている（前に調べたもの・{src}）。この会話より前から知っていることで、いま調べたものではないし、"
                 f"調べたとも言わない。知っていることとして使う。そのまま読み上げない: {rec['text']}")
        if said:
            line += " " + said
        return line
