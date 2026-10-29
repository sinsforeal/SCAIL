import re
import math
import threading
import datetime
import logger
from sim import inflight
from sim import wiring
from sim.textutil import words as tokens

# Remembering on cue. When his message points at the past beyond the live
# window ("remember when", "last time", "you said", a date, a name from
# May) or simply names something that only the compiled days hold, she
# goes looking the way a person does: the compiled days, the cards, her
# talks and the messages BEHIND the thread's own verbatim cut are searched by
# words (no call), the best few excerpts go to one `recall`
# call that writes what she actually remembers, with the clarity it
# deserves (a day from last week is clear; the May era is ninety-nine days
# old and comes back in outline). The memory goes into that reply's
# situation and into the editor's knowledge. Runs in a thread during her
# read delay, like the lookup.
#
# `older_messages` at the bottom is the same search with no model behind it
# and a different customer: the continuity checker, which is shown only the
# last few messages and needs the older ones a DRAFT reaches for before it
# can tell a memory from an invention.

# One tokeniser for both languages (`sim/textutil.words`). The regex that
# was here treated a maximal run of kana and kanji as one token, which in a
# language without spaces is a whole clause -- so a Japanese line could not
# be matched by anything, in any language, including a near-identical
# Japanese line. Character bigrams fix that; the English minimum is
# unchanged.
_MIN_LATIN = 4

# Romaji to kana, greedy longest syllable first. A cue is written the way he
# types -- "yani neko", "makeine" -- and her own record is written in
# Japanese, so a word search over the two shares nothing at all: on
# 2026-09-06 the one row in her save that held ヤニねこ could not be reached by
# any English or romaji spelling of it. Where his list or the pages she has
# read hold both spellings of a title, that pairing is the answer and it is
# used first (`cross_script`); this is what is left when nothing holds the
# pair, and it is why "yani neko" reaches ヤニねこ (on ヤニ and ねこ) while "the
# smoking cat anime" reaches nothing -- a description is not a spelling of a
# title, and no store in this machine maps one to the other.
_KANA = {}
for _row, _kana in (
        ("a i u e o", "アイウエオ"), ("ka ki ku ke ko", "カキクケコ"),
        ("sa shi su se so", "サシスセソ"), ("ta chi tsu te to", "タチツテト"),
        ("na ni nu ne no", "ナニヌネノ"), ("ha hi fu he ho", "ハヒフヘホ"),
        ("ma mi mu me mo", "マミムメモ"), ("ya yu yo", "ヤユヨ"),
        ("ra ri ru re ro", "ラリルレロ"), ("wa wo n", "ワヲン"),
        ("ga gi gu ge go", "ガギグゲゴ"), ("za ji zu ze zo", "ザジズゼゾ"),
        ("da di du de do", "ダヂヅデド"), ("ba bi bu be bo", "バビブベボ"),
        ("pa pi pu pe po", "パピプペポ"),
        ("kya kyu kyo", "キャキュキョ"), ("sha shu sho", "シャシュショ"),
        ("cha chu cho", "チャチュチョ"), ("nya nyu nyo", "ニャニュニョ"),
        ("hya hyu hyo", "ヒャヒュヒョ"), ("mya myu myo", "ミャミュミョ"),
        ("rya ryu ryo", "リャリュリョ"), ("gya gyu gyo", "ギャギュギョ"),
        ("ja ju jo", "ジャジュジョ"), ("bya byu byo", "ビャビュビョ"),
        ("pya pyu pyo", "ピャピュピョ"), ("fa fi fe fo", "ファフィフェフォ"),
        ("she je che ti tu di du", "シェジェチェティトゥディドゥ")):
    # the kana of a row are one or two characters each; walk them in step
    _syl, _pos = _row.split(), 0
    for _s in _syl:
        _take = 2 if _pos + 1 < len(_kana) and _kana[_pos + 1] in "ャュョァィェォゥ" else 1
        _KANA[_s] = _kana[_pos:_pos + _take]
        _pos += _take


def kana_forms(word):
    """The katakana and hiragana a romaji word would be written in, or an
    empty set when it is not romaji at all.

    Strict: every letter has to belong to a syllable, so "neko" converts and
    "smoking" and "difference" do not, which is what keeps English words from
    turning into kana noise. Both scripts, because a Japanese title mixes them
    (ヤニねこ is katakana then hiragana) and one form of it would miss."""
    w = str(word or "").strip().lower()
    if not w or not w.isascii() or not w.isalpha() or len(w) < 3:
        return set()
    out, i = [], 0
    while i < len(w):
        for n in (3, 2, 1):
            syl = _KANA.get(w[i:i + n])
            if syl and (n > 1 or w[i:i + 1] in "aiueon"):
                out.append(syl)
                i += n
                break
        else:
            # a doubled consonant is a small tsu ("kotto"), anything else is
            # not romaji and the whole word is left alone
            if i + 1 < len(w) and w[i] == w[i + 1] and w[i] not in "aiueon":
                out.append("ッ")
                i += 1
                continue
            return set()
    kata = "".join(out)
    hira = "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in kata)
    return {kata, hira}


def cross_script(text, anime_kb=None, store=None, limit=8):
    """The other script's words for the titles this cue names: the tokens to
    add to a word search so a cue in one language can reach a record written
    in the other.

    Three local sources, in order of authority, and no network -- this runs on
    the loop thread:

      * a thing she knows by name (kv `known_things`), whose names carry the
        romaji AND the Japanese spelling of the same work;
      * his own list (`AnimeKB.entries`), which pairs the title he calls it
        with the English one;
      * failing both, the kana the romaji itself transliterates to.

    Returns (extra tokens, what it did) so the caller can log where the
    crossing came from, and say plainly when there was nothing to cross."""
    t = str(text or "")
    if not t.strip():
        return set(), ""
    low = t.lower()
    extra, notes = set(), []

    def add(name, why):
        w = tokens(name, _MIN_LATIN)
        if w and not w <= extra:
            extra.update(w)
            notes.append(f"{why} {name}")

    if store is not None:
        try:
            for r in (store.get("known_things", []) or []):
                names = [str(n) for n in (r.get("names") or []) if str(n).strip()]
                if not any(len(n) >= 4 and n.lower() in low for n in names):
                    continue
                for n in names:
                    if len(n) >= 2 and n.lower() not in low:
                        add(n, "a thing she knows by name:")
                if len(notes) >= limit:
                    break
        except Exception as e:
            logger.log(f"[recall] what she knows not read for the cue: {type(e).__name__}")
    if anime_kb is not None and len(notes) < limit:
        try:
            for e in anime_kb.entries():
                pair = [str(e.get("title") or ""), str(e.get("eng") or "")]
                if not any(len(p) >= 6 and p.lower() in low for p in pair):
                    continue
                for p in pair:
                    if len(p) >= 3 and p.lower() not in low:
                        add(p, "on his list:")
                if len(notes) >= limit:
                    break
        except Exception as e:
            logger.log(f"[recall] his list not read for the cue: {type(e).__name__}")
    # and the kana of the romaji words themselves, singly and as one run
    for run in re.findall(r"[A-Za-z]+(?:[ '\-][A-Za-z]+)*", t):
        parts = re.split(r"[ '\-]+", run)
        forms = [kana_forms(p) for p in parts]
        if len(parts) > 1 and all(forms):
            for f in kana_forms("".join(parts)) or set():
                extra |= tokens(f, _MIN_LATIN)
        for p, f in zip(parts, forms):
            if f and p.lower() not in _STOP:
                for one in f:
                    extra |= tokens(one, _MIN_LATIN)
    return extra, "; ".join(notes)


_STOP = set("that this with have from what when were your just like about they them then than there their been will would could should really maybe think know going want said says told back time first talked stuff remember thing things something yeah like lol haha still again".split())


def moment_cue(store, scene=None, his_text=""):
    """The moment as one cue text: what he just wrote, her own last line, and
    the scene she is in (where, with whom, what is happening).

    One owner, because the deliberate search of the record and the persona's
    recall of a faded fact are the same question asked twice, and until now
    the second one was asked of his newest message alone -- so where she was,
    who she was with and what she herself had just said cued nothing. His
    message stays the TRIGGER wherever there is one (`Recall.start`); this
    only widens what the record is searched for. `scene` defaults to the
    scene on record, which is the director's own current one."""
    parts = []
    if str(his_text or "").strip():
        parts.append(str(his_text)[:600])
    try:
        for m in reversed(store.recent_messages(6) or []):
            if m.get("role") != "user" and str(m.get("text") or "").strip():
                parts.append(str(m["text"])[:300])
                break
    except Exception:
        pass
    try:
        sc = scene if scene is not None else (store.last_scene() or {})
    except Exception:
        sc = {}
    for k in ("location", "activity", "with_who"):
        if (sc or {}).get(k):
            parts.append(str(sc[k]))
    return " ".join(parts)


def older_messages(store, clock, text, before_ts, limit=5, scan=1500, min_overlap=2, common_share=0.02):
    """The few messages older than `before_ts` that `text` is reaching for,
    found by word overlap alone -- no model call.

    The continuity checker is shown the last handful of messages and nothing
    else, so a true quotation of anything further back read to it as an
    invention: at message 121 she referred to his having called her 本物,
    which he did at message 54, eight hours earlier, and the checker binned
    the draft. Raising the window is not the answer, because the whole record
    does not fit and a long record is a worse thing to read carefully. This
    searches instead, on the draft's own words, and hands back only what the
    draft actually touches.

    Matched on DISTINCTIVE words only. A shared "tacos" means the draft is
    reaching for that evening; a shared "actually" means nothing, and a plain
    overlap count is mostly the second kind -- the first version of this handed
    the checker five old messages that had nothing to do with the draft. A word
    in more than `common_share` of the record is dropped as furniture, and what
    is left is weighted by how rare it is, so one uncommon word beats three
    ordinary ones. Divided by the message's own length, so a long rambling one
    does not win on size alone. Returned oldest first, as they were said.

    Measured against the live record at 2 per cent: "yeah ok. i guess. anyway
    what are you doing" reaches nothing, "you said you made tacos that night"
    reaches the one message in May where he said it, and a line about the
    yukata reaches the evening Rena picked the obi. At 6 per cent the small
    talk pulled five unrelated messages, which is the noise this is for."""
    words = tokens(text, _MIN_LATIN) - _STOP
    if not words:
        return []
    rows = [m for m in store.recent_messages(scan)
            if m.get("ts", 0) < before_ts and (m.get("text") or "").strip()]
    if not rows:
        return []
    toks = [tokens(m["text"], _MIN_LATIN) for m in rows]
    df = {w: 0 for w in words}
    for mw in toks:
        for w in words & mw:
            df[w] += 1
    ceiling = max(2, int(len(rows) * common_share))
    weight = {w: 1.0 / math.log2(2 + n) for w, n in df.items() if 0 < n <= ceiling}
    if not weight:
        return []
    scored = []
    for m, mw in zip(rows, toks):
        ov = weight.keys() & mw
        if len(ov) >= min_overlap:
            scored.append((sum(weight[w] for w in ov) / (len(mw) ** 0.3 or 1), m))
    scored.sort(key=lambda x: (-x[0], -x[1].get("ts", 0)))
    best = [m for _, m in scored[:limit]]
    best.sort(key=lambda m: m.get("ts", 0))
    return best


# What a memory of a past exchange asserts. The grounding test only applies
# to a recall that says one of them SAID something, which is the claim the
# store can be asked about; a recall of how a day felt asserts nothing of the
# kind. Both languages, because the second character remembers in Japanese.
_CLAIMS_AN_EXCHANGE = re.compile(
    r"\b(you|he|we)\s+(said|told|promised|asked|mentioned|wrote|talked|agreed)\b"
    r"|って言っ|と言っ|って言って|言ってた|約束し", re.I)


class Recall:
    WIRES = ("episodes", "embed", "memory", "anime_kb")

    def __init__(self, config, llm, store, clock, self_memory=None):
        self.config = config
        self.self_memory = self_memory
        self.llm = llm
        self.store = store
        self.clock = clock
        self.thread = None
        self.result = None
        wiring.declare(self)

    def busy(self):
        return self.thread is not None and self.thread.is_alive()

    def start(self, text, extra=""):
        """`text` is his message; `extra` the rest of the moment (her own last
        line, where she is), which widens the search and never the trigger."""
        c = self.config.recall
        if not c.enabled or self.busy() or not text:
            return False
        counts = self.store.get("recall_counts", {})
        if counts.get(self.clock.date_str(), 0) >= c.max_per_day:
            return False
        cue = bool(re.search(c.trigger_regex, text, re.I))
        hits = self._search(text, extra)
        if not hits or (not cue and hits[0][0] < c.min_score_without_cue):
            return False
        self.result = None
        self.thread = threading.Thread(target=self._run, args=(text, hits, cue), daemon=True)
        self.thread.start()
        return True

    def take(self):
        if self.busy():
            self.thread.join(timeout=self.config.recall.wait_seconds)
        r, self.result = self.result, None
        return r

    # ---------------- searching the record (no model) ----------------

    def _verbatim_from(self):
        """Where the thread's verbatim span actually starts, as a timestamp.

        This search is for what is NOT already in front of her word for word,
        so the boundary has to be the one the thread used and not a second
        number that happens to agree with it. `sim/thread.py _window` chooses
        the cut once a character day, on a midnight, moving it forward a whole
        day at a time toward `thread.verbatim_min_hours` when the verbatim
        days plus the cards do not fit the one budget, and writes it to kv
        `thread_window`. Reading that value is what stops the two drifting: a
        span the budget shrank means recall reaches further in on the same
        day, and a full week means recall starts a week back.

        An empty kv -- a save whose thread has never been built -- falls back
        to the configured span. A stale one, written on an earlier day because
        no thread has been built yet today, is clamped to that same span, so a
        window left behind by a bot that was off for a week cannot send the
        search over days that are verbatim now."""
        floor = self.clock.now_ts() - float(self.config.thread.verbatim_hours) * 3600
        kv = self.store.get("thread_window") or {}
        try:
            cut = float(kv.get("verbatim_from") or 0)
        except (TypeError, ValueError):
            cut = 0.0
        return max(cut, floor) if cut > 0 else floor

    def _event_weight(self, row, now):
        """How much an event of her day is worth to a search of the record.

        The same forgetting curve the other stores get, on HER OWN life's
        half-lives (`self_memory.half_life_days`) rather than the shorter
        scale a fact about somebody else fades on: an event is a thing that
        happened to her. Salience is the weight, so the day the ground shook
        stays reachable for a year and an ordinary afternoon does not."""
        try:
            hl = list(self.config.self_memory.half_life_days)
            sal = max(1, min(len(hl), int(row.get("salience") or 1)))
            age = max(0.0, (now - float(row.get("ts") or 0)) / 86400.0)
            base = float(getattr(self.config.recall, "events_weight", 0.8) or 0.8)
            return base * math.exp(-math.log(2) * age / float(hl[sal - 1]))
        except (TypeError, ValueError, IndexError, ZeroDivisionError):
            return 0.0

    @staticmethod
    def events_wanted(config):
        """(the salience to search from, how many rows to read), or (0, 0)
        when the events are not a source for this character.

        One owner for the two numbers, because three readers ask -- the word
        search, the meaning search and the vector backfill -- and a zero has
        to mean off in all three rather than falling back to the default."""
        c = getattr(config, "recall", None)
        try:
            sal = int(getattr(c, "events_min_salience", 2))
            scan = int(getattr(c, "events_scan", 1200))
        except (TypeError, ValueError):
            return 0, 0
        return (sal, scan) if sal > 0 and scan > 0 else (0, 0)

    def _events(self, words, window, from_date, now):
        """The salient events a cue reaches, as search rows. The label is
        `<date> #<id>`, and the meaning search gives the same row the same
        label, or one row would be scored twice under two names."""
        out = []
        sal, scan = self.events_wanted(self.config)
        if not sal:
            return out
        try:
            rows = self.store.salient_events(min_salience=sal, before_ts=window or None,
                                             limit=scan)
        except Exception as e:
            logger.log(f"[recall] the events were not read: {type(e).__name__}")
            return out
        for r in rows:
            if from_date and str(r.get("date") or "") >= from_date:
                continue
            ov = words & tokens(r.get("text") or "", _MIN_LATIN)
            if ov:
                out.append((len(ov) / (len(words) ** 0.5) * self._event_weight(r, now),
                            "event", f"{r.get('date')} #{r.get('id')}",
                            str(r.get("text") or "")[:500], ov))
        return out

    def _search(self, text, extra=""):
        words = tokens(text, _MIN_LATIN) - _STOP
        if extra:
            words |= tokens(extra, _MIN_LATIN) - _STOP
        if not words:
            return []
        # A cue in one script cannot reach a record written in the other on
        # words alone, so the titles this cue names are looked up in the two
        # local stores that hold both spellings, and a romaji word is
        # transliterated (`cross_script`). Nothing is fetched: this runs on
        # the loop thread.
        if getattr(self.config.recall, "cross_script", True):
            try:
                more, why = cross_script(f"{text} {extra}", self.anime_kb, self.store)
                new = more - words
                if new:
                    words |= new
                    logger.log(f"[recall] cross-script: {len(new)} form(s) added to the cue ("
                               + (why if why else "nothing here holds a Japanese title for what "
                                  "he named, so the syllables of the romaji itself: "
                                  + ", ".join(sorted(new)[:8])) + ")")
            except Exception as e:
                logger.log(f"[recall] the cue was not crossed to the other script: "
                           f"{type(e).__name__}: {str(e)[:80]}")
        window = self._verbatim_from()
        # the cut is a midnight of her clock, so a day whose date is on or
        # after it is a day the thread still carries message by message. It
        # must not come back as its narrative or as one of its cards either:
        # remembering a thing that is on the screen in front of her is the
        # fault this boundary exists to prevent.
        from_date = self.clock.date_str(window)
        scored = []
        for d in self.store.recent_days(400):
            if str(d.get("date") or "") >= from_date:
                continue
            body = f"{d.get('summary', '')} {d.get('narrative', '')}"
            bw = tokens(body, _MIN_LATIN)
            ov = words & bw
            if ov:
                scored.append((len(ov) / (len(words) ** 0.5), "day", d["date"], d.get("summary") or d.get("narrative", "")[:600], ov))
        # the machinery's own record of her day. Some things are in no other
        # store at all (`docs/memory.md` §6), which is how her one encounter
        # with a title stayed unreachable for sixteen days.
        scored.extend(self._events(words, window, from_date, self.clock.now_ts()))
        # the whole record, not the scene she is in: a memory she is recalling
        # may have been made in another scene thread
        for m in self.store.recent_messages(2000, scene_id="*"):
            if m["ts"] >= window:
                continue
            mw = tokens(m["text"] or "", _MIN_LATIN)
            ov = words & mw
            if len(ov) >= 2:
                when = self.clock.to_char(m["ts"]).strftime("%Y-%m-%d %H:%M")
                scored.append((len(ov) / (len(words) ** 0.5) * 0.8, "message", when, f"{'HIM' if m['role'] == 'user' else 'HER'}: {m['text'][:300]}", ov))
        # her talks with the people around her: what Rena said last week is
        # as findable as what he said
        try:
            from sim import talks
            for when, who, kind, turns, gist in talks.search_rows(self.store):
                if str(when)[:10] >= from_date:
                    continue
                # her talks are Japanese; his cue words are English. The gist
                # is the one English line each exchange carries, so that is
                # what a cue can match -- the excerpt quoted back is still what
                # was actually said.
                body = gist or " ".join(t.get("text") or t.get("ja", "") for t in turns)
                tw = tokens(body, _MIN_LATIN)
                ov = words & tw
                if len(ov) >= 2:
                    excerpt = " / ".join(f"{t['who']}: {(t.get('ja') or t.get('text', ''))[:120]}" for t in turns[:5])
                    scored.append((len(ov) / (len(words) ** 0.5) * 0.9, "talk", f"{when} with {who}", excerpt[:400], ov))
        except Exception:
            pass
        # what she knows about him, through the pool's own row list, so the
        # word search and the meaning search name the same rows
        if self.memory is not None:
            for it in self.memory.search_items(_MIN_LATIN):
                ov = words & it["keys"]
                if ov:
                    scored.append((len(ov) / (len(words) ** 0.5) * it["mult"], "fact", it["label"], it["body"], ov))
        # her own life is searched too, and weighted above the day narratives:
        # she remembers what happened to her better than she remembers the shape
        # of the day it happened in
        if self.self_memory:
            scored.extend(self.self_memory.search(words))
        # her past as cards: the shape of an evening and its exact lines
        if self.episodes is not None:
            try:
                scored.extend(row for row in self.episodes.search(words)
                              if str(row[2])[:10] < from_date)
            except Exception as e:
                logger.log(f"[recall] cards not searched: {type(e).__name__}")
        # and by meaning, over the pools that have a stable identity to embed:
        # a paraphrase, or a Japanese cue for an English card, reaches what
        # the words could not
        if self.embed is not None:
            try:
                scored = self._semantic((text + " " + extra).strip(), scored, window, from_date,
                                        cue_words=words)
            except Exception as e:
                logger.log(f"[recall] meaning search failed: {type(e).__name__}: {str(e)[:80]}")
        scored.sort(key=lambda x: -x[0])
        return scored[: self.config.recall.max_excerpts]

    def _semantic(self, cue, scored, window=0.0, from_date="", cue_words=()):
        """Adds the cosine of the cue to the word scores of every pool whose
        rows have a stable identity to embed -- the cards, the compiled days,
        what she knows about him and her own memories -- and a row the words
        missed joins on its cosine alone.

        A row that joins on its cosine alone must share one content word with
        the cue even so, and at most `recall.max_cosine_only` of them join
        per search: the excerpts this hands the paid call are what she says
        she remembers, and a cosine-only row took third place of five and
        came out of her mouth as a thing she could not place.

        The vectors are the same ones her prompt's own retrieval reads
        (`sim/embed.py`, one table keyed by kind and row id), so a pool is
        embedded once however many readers it has. Each pool hands over the
        label it gives a row, which is also how a semantic hit is matched to
        the word hit for the same row: a label that is not unique per row
        would score one row and hide another."""
        q = self.embed.query(cue)
        if q is None:
            return scored
        pools = []
        if self.episodes is not None:
            # the same boundary the word search uses, or the cosine would hand
            # back by meaning exactly the days the words were told to skip
            rows = [r for r in self.episodes.rows()
                    if not window or float(r["start_ts"] or 0) < window]
            pools.append(("episode", "episode", [(r["id"], self.episodes.text_of(r)) for r in rows],
                          {str(r["id"]): (f"{self.clock.to_char(r['start_ts']).strftime('%Y-%m-%d %H:%M')} {r['room']}",
                                          self.episodes.text_of(r)[:500]) for r in rows}))
        ev = []
        _sal, _scan = self.events_wanted(self.config)
        if _sal:
            try:
                ev = [r for r in self.store.salient_events(min_salience=_sal,
                                                           before_ts=window or None, limit=_scan)
                      if not from_date or str(r.get("date") or "") < from_date]
            except Exception as e:
                logger.log(f"[recall] the events were not read by meaning: {type(e).__name__}")
        if ev:
            pools.append(("event", "event",
                          [(r["id"], str(r.get("text") or "")) for r in ev],
                          {str(r["id"]): (f"{r.get('date')} #{r.get('id')}",
                                          str(r.get("text") or "")[:500]) for r in ev}))
        days = [d for d in self.store.recent_days(400)
                if not from_date or str(d.get("date") or "") < from_date]
        pools.append(("day", "day", [(d["date"], f"{d.get('summary', '')} {(d.get('narrative') or '')[:800]}") for d in days],
                      {str(d["date"]): (d["date"], d.get("summary") or (d.get("narrative") or "")[:600]) for d in days}))
        for pool, kind, owner in (("fact", "fact", self.memory), ("selfmem", "her own", self.self_memory)):
            if owner is None:
                continue
            items = owner.search_items(_MIN_LATIN) if pool == "fact" else owner.search_items()
            pools.append((pool, kind, [(it["ref"], it["embed"]) for it in items],
                          {str(it["ref"]): (it["label"], it["body"]) for it in items}))
        index = {(kind, when): i for i, (_, kind, when, _, _) in enumerate(scored)}
        added, by_pool = 0, {}
        want_word = bool(getattr(self.config.embed, "require_shared_word", False)) and cue_words
        cap = int(getattr(self.config.recall, "max_cosine_only", self.config.recall.max_excerpts))
        lonely, no_word = [], 0
        for pool, kind, items, label in pools:
            vecs = self.embed.vectors(pool, items)
            texts = {str(r): t for r, t in items}
            for ref, v in vecs.items():
                sc = self.embed.score(self.embed.cosine(q, v), pool, ref=ref)
                if sc <= 0:
                    continue
                when, body = label[ref]
                i = index.get((kind, when))
                if i is not None:
                    s0, k0, w0, b0, ov0 = scored[i]
                    scored[i] = (s0 + sc, k0, w0, b0, ov0)
                    added += 1
                    by_pool[pool] = by_pool.get(pool, 0) + 1
                    continue
                # nothing of the words found this row
                if want_word and not (tokens(texts.get(str(ref), "") + " " + body, _MIN_LATIN)
                                      - _STOP) & set(cue_words):
                    no_word += 1
                    continue
                lonely.append((sc, pool, kind, when, body))
        lonely.sort(key=lambda x: -x[0])
        over = max(0, len(lonely) - cap)
        for sc, pool, kind, when, body in lonely[:cap]:
            if (kind, when) in index:
                continue
            scored.append((sc, kind, when, body, set()))
            index[(kind, when)] = len(scored) - 1
            added += 1
            by_pool[pool] = by_pool.get(pool, 0) + 1
        if added or no_word or over:
            logger.log(f"[recall] meaning: {added} row(s) scored above the floor ("
                       + ", ".join(f"{k} {v}" for k, v in sorted(by_pool.items())) + ")"
                       + (f"; {no_word} dropped for sharing no word with the moment" if no_word else "")
                       + (f"; {over} over the by-meaning cap of {cap}" if over else ""))
        return scored

    # ---------------- the remembering ----------------

    def _run(self, text, hits, cue):
        """The flag round the work (`sim/inflight.py`): one paid call on a
        daemon thread, with nothing on disk to say it had begun."""
        with inflight.job(self.store, "recall", about=str(text)[:80], redo={"text": str(text)[:600]}):
            self._remember(text, hits, cue)

    def _remember(self, text, hits, cue):
        try:
            today = self.clock.date_str()
            self.store.bump_today("recall_counts", today)
            now = self.clock.now().date()
            ex, refs = [], []
            for n, (score, kind, when, body, ov) in enumerate(hits, start=1):
                # Every excerpt is headed by a reference the answer has to
                # copy back, and the code checks it against this list. Before
                # this the answer cited nothing and nothing could be checked:
                # on 2026-09-06 the role wrote a memory of an exchange about a
                # title that is in none of the excerpts and it was stored.
                refs.append({"n": n, "label": f"{kind} {when}", "kind": kind,
                             "when": when, "body": body})
                if kind == "her own":
                    # the label carries the row id so a semantic hit can be
                    # matched to the word hit for the same memory; what she
                    # is shown is the date
                    ex.append(f"[{n}] [something she remembers of her own, {when[:10]}] {body}")
                    continue
                if kind == "fact":
                    ex.append(f"[{n}] [something she knows about him] {body}")
                    continue
                try:
                    age = (now - datetime.date.fromisoformat(when[:10])).days
                except ValueError:
                    age = "?"
                if kind == "event":
                    ex.append(f"[{n}] [something that happened in her day, {when[:10]}, "
                              f"{age} days ago] {body}")
                    continue
                ex.append(f"[{n}] [{kind} {when}, {age} days ago] {body}")
            user = (f"TODAY: {self.clock.both()}\nWHAT HE JUST WROTE: {text[:600]}\n\nWHAT THE RECORD HOLDS THAT MATCHES:\n" + "\n\n".join(ex))
            system = self.config.role_system("recall")
            data, raw = self.llm.call_json("recall", [{"role": "system", "content": system}, {"role": "user", "content": user}])
            if not isinstance(data, dict) or not str(data.get("memory", "")).strip() or data.get("clarity") == "none":
                logger.log("[recall] nothing she remembers about that")
                return
            cited, why = self._grounded(str(data["memory"]).strip(), str(data.get("from") or ""),
                                        text, refs)
            if why:
                logger.log(f"[recall] not grounded: {str(data['memory']).strip()[:160]} -- {why}")
                return
            rec = {"date": today, "hm": self.clock.hm(), "cue": text[:120], "memory": str(data["memory"]).strip()[:600],
                   "clarity": str(data.get("clarity", "hazy"))[:10], "from": [f"{k} {w}" for _, k, w, _, _ in hits[:3]],
                   "cited": cited}
            self.store.set("recalls", (self.store.get("recalls", []) + [rec])[-self.config.recall.keep:])
            self.result = rec
            logger.log(f"[recall] ({rec['clarity']}) {rec['memory'][:160]}")
        except Exception as e:
            logger.log(f"[recall] failed: {type(e).__name__}: {e}"[:200])

    def _grounded(self, memory, cite, his_text, refs):
        """(the excerpt this memory is grounded in, why it is not).

        Two tests, and both are about the RECORD rather than about the words:

        * the answer has to cite one of the excerpts it was handed, by its
          number or by its own date or id. A citation of something it was not
          shown is a citation of nothing;
        * a memory that says one of them SAID something has to be about a
          thing the excerpts hold. The subject is the words of his message
          that are distinctive over her record (a word in more than
          `subject_common_share` of the rows names nothing), the test applies
          only when the memory takes one of them up, and then that word has to
          appear in an excerpt. On 2026-09-06 the role was cued by "the
          smoking cat anime", took the phrase up, and wrote that he had
          promised to watch it with her in August; the word is in no excerpt
          and nothing in the record is about it.

        Measured over the fifty-two recalls already in the first character's
        save: eight would not have been written, and reading them, six say
        again as a memory what he had just that minute typed. The measurement
        is in this step's report."""
        if not getattr(self.config.recall, "require_grounding", True):
            return "", ""
        want = " ".join(str(cite or "").split())
        hit = None
        for r in refs:
            if not want:
                break
            if want == str(r["n"]) or f"[{r['n']}]" == want:
                hit = r
                break
            for mark in re.findall(r"\d{4}-\d{2}-\d{2}|#\d+", want):
                if mark in r["label"]:
                    hit = r
                    break
            if hit:
                break
        if hit is None:
            return "", (f"it cites {want!r}, which is not one of the "
                        f"{len(refs)} excerpt(s) it was shown"
                        if want else "it cites no excerpt at all")
        if not _CLAIMS_AN_EXCHANGE.search(memory or ""):
            return hit["label"], ""
        subject = self._subject(his_text)
        taken = subject & tokens(memory, _MIN_LATIN)
        if not taken:
            return hit["label"], ""
        here = set()
        for r in refs:
            here |= tokens(r["body"], _MIN_LATIN)
        if taken & here:
            return hit["label"], ""
        return "", (f"it says one of them said something about "
                    + ", ".join(sorted(taken)) + ", which is in none of the "
                    f"{len(refs)} excerpt(s) the record gave it")

    def _subject(self, his_text):
        """The words of his message distinctive enough to name a thing.

        The same furniture rule `older_messages` uses, over the compiled days
        and her own record rather than over the messages: a word in more than
        `recall.subject_common_share` of the rows is grammar or weather and
        names nothing."""
        cue = tokens(his_text, _MIN_LATIN) - _STOP
        if not cue:
            return set()
        bodies = []
        try:
            bodies += [f"{d.get('summary', '')} {d.get('narrative', '')}"
                       for d in self.store.recent_days(400)]
        except Exception:
            pass
        if self.self_memory is not None:
            try:
                bodies += [it["embed"] for it in self.self_memory.search_items()]
            except Exception:
                pass
        if self.memory is not None:
            try:
                bodies += [it["embed"] for it in self.memory.search_items(_MIN_LATIN)]
            except Exception:
                pass
        if not bodies:
            return set()
        df = {}
        for b in bodies:
            for w in tokens(b, _MIN_LATIN) & cue:
                df[w] = df.get(w, 0) + 1
        share = float(getattr(self.config.recall, "subject_common_share", 0.02) or 0.02)
        ceiling = max(2, int(len(bodies) * share))
        return {w for w in cue if df.get(w, 0) <= ceiling}

    @staticmethod
    def already_in_thread(rec, refs):
        """Is the line she just remembered a retelling of a conversation the
        thread is bringing back word for word?

        Two retrievals answer one cue over one record. `sim/thread.py` puts a
        whole exchange from past the verbatim cut back in front of her, marked
        as having just come back; this writes one compiled line about the same
        rows into the situation block, pinned. Nothing coordinated them, so she
        could be handed the exact words and a paraphrase of them at once --
        measured on a copy of the first character's save on 2026-09-04, nine of
        twelve cues taken from an exchange behind the cut had both retrievals
        answer with that same conversation, and in eight of the nine it was the
        strongest row the paid call was given.

        The strongest row decides, because it is the one the written line is
        mostly about: when it is one of the exchanges the thread is carrying in
        full -- the talk itself, or a card that began inside it -- the words are
        above and the line is not restated. A line built on anything else
        stands, and so does a card that reaches back over a conversation the
        thread has not got, which is the safe way round: she gets the extra
        line rather than losing a memory.

        `refs` come from `Thread.brought_back()`. The question runs one way
        only: the thread's own choice is made from the cue and its window and
        never from what this found, because its head is the prompt's cache
        prefix."""
        src = ((rec or {}).get("from") or [None])[0]
        if not src or not refs:
            return False
        kind, _, label = str(src).partition(" ")
        if kind == "talk":
            return any(label == r.get("talk_label") for r in refs)
        if kind == "episode":
            part = label.split(" ", 2)
            if len(part) < 3:
                return False
            when, room = f"{part[0]} {part[1]}", part[2]
            return any(r.get("room") == room and str(r.get("stamp") or "") <= when <= str(r.get("end_stamp") or "")
                       for r in refs)
        return False

    @staticmethod
    def situation_line(rec, config=None):
        """`config` says which language she is addressed in; without one the
        line stays English, which is what every non-prompt caller wants."""
        if not rec:
            return ""
        from sim.lang import reads_ja
        if config is not None and reads_ja(config):
            how = {"clear": "これははっきり覚えている", "hazy": "細かい言葉までではなく、輪郭で思い出す",
                   "faint": "うっすらとしか覚えていない"}.get(rec.get("clarity"), "覚えている")
        else:
            how = {"clear": "you remember this clearly", "hazy": "it comes back to you in outline, not word for word", "faint": "you only faintly remember"}.get(rec.get("clarity"), "you remember")
        return f"{how}: {rec['memory']}"
