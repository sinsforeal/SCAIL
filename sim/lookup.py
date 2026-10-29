import json
from sim import inflight
from sim import resolver as _resolver
from sim import wiring
from sim import works
import re
import threading
import urllib.parse
import urllib.request
import html
import logger

# When he mentions a thing ("just watched X", "that song", "this game"),
# she quietly goes and looks it up the way a person thumbs it into a
# search while the chat is open. Two model calls and a web request, off
# the main thread, during her read delay: one call reads his message and
# decides whether there is a thing worth looking up (most messages: no),
# then his MAL list is checked, then a search (MAL's API for anime, a
# plain web search otherwise) and a second call writes the three-line
# gist she now knows. The gist goes into the reply that follows (her
# situation: "you looked it up just now"), into kv lookups, and into what
# she knows about him as a weighted fact. He is never told she looked.
#
# There are two ways a search happens and they must never be confused in
# what she is told. One is the path above: it ARRIVES, off his message, with
# nothing of hers behind it. The other is `search()`, which she asks for --
# `[search: ...]` on its own line of a draft, or her sight at a page of his.
# Every record either path writes carries `asked_by` ("her" or "arrived"),
# and a record answered out of what she already knows carries `from_known`,
# so her situation can say she already knew the thing rather than tell her
# she just looked it up. Without that she claimed searches that never ran.

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}


class Lookup:
    # `lore` is her own record, asked before anything is fetched: a work she
    # was in is a thing she knows, not a thing to look up (`sim/works.py`).
    # It is None for a character with no record of her own.
    # `retrievals` is the machine's store of what has been fetched about
    # the world (`machine/retrievals.py`). The search itself goes in it; what
    # she makes of the result, in her own words, does not.
    # `resolver` answers which of several candidate works a title he typed
    # means, when the ranking ties (`sim/resolver.py`). It is asked on THIS
    # thread, which is already making two model calls and a web request, and
    # never on a reply path.
    WIRES = ('watching', 'lore', 'retrievals', 'resolver',)
    KINDS = ("anime", "manga", "character", "seiyuu", "game", "music",
             "film", "show", "book", "product", "place", "person", "site", "other")

    def __init__(self, config, llm, store, clock, mal=None, memory=None, anime_kb=None, recap=None, typesafe=None):
        self.config = config
        self.llm = llm
        self.store = store
        self.clock = clock
        self.mal = mal
        self.memory = memory
        self.anime_kb = anime_kb    # series / seiyuu cards from his history DB (cast with JP voices, not synopsis)
        self.recap = recap          # a fuller JP overview + episode beats when HE names an anime/episode
        # The hosted classifier (`typesafe.py`, `docs/system-one.md`): when her
        # config turns the `lookup` use on, two choices -- did he name a
        # concrete thing at all, and which kind -- gate and label the lookup.
        # `term`/`name`/`show` stay the role's.
        self.typesafe = typesafe
        self.watching = None        # set by App: the episode he has open is the strongest anchor for a character name
        from sim.known import KnownThings
        self.known = KnownThings(config, store, clock)   # what she looked up, kept by name
        self.thread = None
        self.result = None      # the last finished lookup, consumed by the reply
        self.for_ts = 0
        wiring.declare(self)

    def busy(self):
        return self.thread is not None and self.thread.is_alive()

    # Ordinary English words are the whole problem for the API probe: MAL
    # search answers every query, and enough shows have plain-word English
    # titles that "annoying" comes back as My Senpai is Annoying -- one he has
    # actually watched, so even checking his list does not catch it. Nothing
    # here is ever probed.
    _STOP_KB = set((
        "about actually after again all almost already although always angry "
        "annoying another answer any anybody anyone anything arent autumn back "
        "basically bath bathroom because been before best better bigger bored "
        "boring both breakfast brother busy can chat class clever closer cloudy "
        "coffee could cute dad definitely didnt difficult dinner does doesnt doing "
        "dont dream drink each early easy enough evening ever everyone everything "
        "exam false family father feeling feelings few film fine finished finishing "
        "first food friday friend friends from funny game games getting girl girls "
        "going good goodbye great happy hard have hello here herself himself home "
        "homework honestly hour house how however hungry instead isnt just kitchen "
        "know large late lazy lesson like literally little lonely long looking loud "
        "lunch lunchbox making maybe message minute monday month more morning most "
        "mother movie much mum music myself never nice night nobody nope nothing "
        "obviously often okay older only other others own parents people person "
        "phone photo photos picture pictures please pretty probably question "
        "questions quiet rain really reason reasons remember right room sad said "
        "same saturday saying says scared school serious short should show shower "
        "shows silly simple since sister sleep sleepy small smaller snack some "
        "somebody someone something sometimes song songs sorry spring started "
        "starting station still stories story student stuff stupid such summer "
        "sunday sunny sure sweet talked talking teacher text than thanks that their "
        "them then there they thing things think this though thought thoughts "
        "thursday time tired today told tomorrow tonight too train true tuesday "
        "ugly until usually very video videos waiting want washing wasnt water "
        "weather wednesday week weekend weird were what whatever when which while "
        "who whom whose why will winter with wont worse would wrong yeah year "
        "yesterday younger your yourself "
    ).split())

    def _names_a_thing(self, text, api=True):
        """Does any phrase in his message resolve against his own anime history?

        A stronger signal than any keyword: if it resolves, she has a card for
        it with his score and the cast. Longest phrases first, so "K-On Movie"
        beats "K-On". Local sqlite, no model call and no network."""
        c = self.config.lookup
        if not (c.kb_trigger and self.anime_kb):
            return None
        words = re.findall(r"[A-Za-z][A-Za-z'\-!]{1,}|[぀-ヿ一-鿿]{2,}", text)
        cands = []
        for n in (3, 2, 1):
            for i in range(len(words) - n + 1):
                phrase = " ".join(words[i:i + n])
                if len(phrase) < c.kb_min_chars:
                    continue
                if n == 1 and phrase.lower() in self._STOP_KB:
                    continue
                cands.append(phrase)
        # his own titles first: local, strict, no network, no false positives.
        # The RANKING rather than one answer, because this question is only
        # "did he name a thing at all": two entries of one franchise are a tie
        # the resolver settles later (`_which_work`), and a tie is still a
        # thing named. Answering None here would have stopped `Kanon` from
        # triggering a lookup because his list carries the 2006 remake too.
        for phrase in cands[: c.kb_max_candidates]:
            try:
                ranked = self.anime_kb.resolve_candidates(phrase)
            except Exception:
                continue
            if ranked:
                return (phrase, (ranked[0]["aid"], ranked[0]["title"]))
        # Then, for a word distinctive enough to be a name, ask MAL search --
        # but only count it if the answer is something HE HAS WATCHED. Search
        # returns a hit for every query ("girl" gives Girl's High), so his list
        # is what separates a title from an ordinary word.
        if not api:
            return None
        seen = self.store.get("lookup_kb_misses", []) if self.store else []
        tried = 0
        for phrase in cands:
            if tried >= c.kb_api_max_candidates:
                break
            low = phrase.lower()
            # an honorific means it is somebody she knows, not a title. Without
            # this, "rena-chan" comes back from MAL search as Crayon Shin-chan.
            if any(low.endswith(h) for h in ("-chan", "-kun", "-san", "-sama", "-senpai", "chan")):
                continue
            if " " in phrase or len(phrase) < c.kb_api_min_chars or low in seen:
                continue
            # an ordinary word he typed in lower case is not a title: "working"
            # resolved to Working!! and "isn't" to a Railgun special, both on
            # his list, and she looked each one up. A title dropped into a
            # sentence carries its capital.
            if not phrase[0].isupper():
                continue
            tried += 1
            try:
                aid, title = self.anime_kb.resolve(phrase)
            except Exception:
                continue
            # and the word has to be IN the title it resolved to, whole: search
            # is fuzzy and "isn't" came back as a title that does not contain it
            tw = set(re.findall(r"[a-z0-9]+", str(title or "").lower()))
            if aid and self.anime_kb.has(aid) and re.sub(r"[^a-z0-9]", "", low) in tw:
                return (phrase, (aid, title))
            if self.store:
                self.store.set("lookup_kb_misses", (seen + [phrase.lower()])[-400:])
        return None

    def start(self, text, msg_ts):
        """Kick off a lookup for his message, if the cheap gate says it might name a thing."""
        c = self.config.lookup
        if not c.enabled or self.busy() or not text:
            return False
        named = None
        # "model": no keyword gate at all -- the classifier reads every message.
        # The English regex cannot see a Japanese sentence, and for a character
        # who chats in Japanese the gate was the whole reason nothing he named
        # was ever looked up.
        if getattr(c, "gate", "regex") != "model" and not re.search(c.trigger_regex, text, re.I):
            named = self._names_a_thing(text)
            if not named:
                return False
            logger.log(f"[lookup] he named something she has a card for: {named[0]!r} -> {named[1][1]}")
        counts = self.store.get("lookup_counts", {})
        if counts.get(self.clock.date_str(), 0) >= c.max_per_day:
            return False
        self.result = None
        self.for_ts = msg_ts
        self.thread = threading.Thread(target=self._run, args=(text,), daemon=True)
        self.thread.start()
        return True

    def take(self):
        """The finished lookup for the reply, once."""
        if self.busy():
            self.thread.join(timeout=self.config.lookup.wait_seconds)
        r, self.result = self.result, None
        return r

    # ---------------- the work ----------------

    def _run(self, text):
        """The flag round the work (`sim/inflight.py`). A lookup is two model
        calls and a web fetch on a daemon thread; a process killed in the
        middle of it left nothing behind that said it had started."""
        with inflight.job(self.store, "lookup", about=str(text)[:80], redo={"text": str(text)[:600]}):
            self._look(text)

    def _look(self, text):
        try:
            q = self._extract(text)
            if not q:
                logger.log("[lookup] nothing in it worth looking up")
                return
            term, kind = q["term"], q.get("kind", "")
            # A thing she already knows is not fetched, digested and kept again:
            # the recall in her situation brings it back by name, and that is
            # the one retrieval. Without this, みつば named a second time bought
            # a second digest and rewrote the record it was already in.
            try:
                had = self.known.recall(q.get("name") or term, count=False)
                if had:
                    logger.log(f"[lookup] already known ({had[0]['key']}); nothing fetched -- her recall carries it")
                    return
            except Exception:
                pass
            # Her own record and the roles the list gives her, before the web.
            # He named a 2010 lead of hers and the search came back with an
            # unrelated 1967 show; the answer was in two local files nobody
            # asked. A work that turns out to be hers is a thing she KNOWS --
            # the record `sim/works.py` writes is what her situation recalls by
            # name -- so nothing is fetched and nothing claims she just looked.
            if self.resolve_hers(q):
                return
            # a series or a seiyuu: the card from his history (cast with JP
            # voices, studio, year, where he stands with it) beats a synopsis
            found, source = "", ""
            gist = ""
            names = []
            # a character with a show behind it: the fan encyclopedia, which
            # knows who they are; his list's card only knows who voices them
            if kind in ("character", "anime character") and q.get("show") and q.get("name"):
                found, source, names = self._character_page(q["name"], q["show"], text)
                if found:
                    gist = found      # already a digest in her language; no second condensing
            if not found and self.anime_kb and kind in ("anime", "seiyuu", "voice actor", "person", "character", "anime character"):
                found, source = self._kb(term, kind)
            if not found:
                on_list = self._mal_list(term) if self.mal else ""
                found, source = self._search(term, kind)
                if on_list:
                    found = "ON HIS MAL LIST:" + chr(10) + on_list + chr(10) + chr(10) + (found or "")
                    source = "his list + " + source if source else "his anime list"
            if not found:
                logger.log(f"[lookup] '{term}': nothing came back")
                return
            gist = gist or self._gist(term, kind, found, text)
            if not gist:
                return
            self._count()     # a find, not an attempt
            rec = {"date": self.clock.date_str(), "hm": self.clock.hm(), "ts": self.clock.now_ts(),
                   "term": term, "kind": kind, "gist": gist, "source": source,
                   # whether the thing he named is a work of hers, from the
                   # resolution above rather than from anything the fetched
                   # page says about it
                   "role": getattr(self, "last_verdict", None),
                   "asked_by": "arrived"}
            # kept as a thing she knows, found again by any of its names
            try:
                keep_names = [n for n in ([q.get("name") or "", term] + list(names)) if n]
                if kind in ("anime", "manga") and self.anime_kb:
                    aid, _t = self.anime_kb.resolve(term)
                    ja = self.anime_kb.japanese_title(aid) if aid else ""
                    if ja:
                        keep_names.append(ja)
                key = f"{kind or 'thing'}:{(q.get('show') or '')}:{(q.get('name') or term)}"
                self.known.add(key, keep_names, kind, gist, source=source, show=q.get("show") or "")
                self._mark_known(key, {"asked_by": "arrived"})
                rec["known_key"] = key
            except Exception as e:
                logger.log(f"[known] not kept: {type(e).__name__}")
            # he named an anime (maybe an episode): pull a fuller JP overview
            # of the series, and if he said an episode number, that episode's
            # beats -- so she knows what he is talking about, not just the cast
            if self.recap:
                self._attach_kb(rec, term, kind, text, source)
            self.store.set("lookups", (self.store.get("lookups", []) + [rec])[-self.config.lookup.keep:])
            if self.memory:
                self.memory.add_fact(f"He mentioned {term}" + (f" ({kind})" if kind else "") + f": {gist[:160]}", self.config.lookup.fact_weight)
            self.store.add_event(self.clock.now_ts(), self.clock.date_str(), "lookup", f"(private) she looked up {term}: {gist[:120]}", 1)
            self.result = rec
            logger.log(f"[lookup] '{term}' via {source}: {gist[:160]}")
        except Exception as e:
            logger.log(f"[lookup] failed: {type(e).__name__}: {e}"[:200])

    def resolve_hers(self, q):
        """Was the thing he just named a work of hers? True when it was, and
        the one record has been written; nothing was fetched either way.

        Local only (`allow_search=False`): the web is the arriving lookup's
        own business a few lines further down, and a search run from here
        would be the second one for the same title."""
        # The verdict this resolution reached, for the reply that follows.
        # A work of hers returns True here and the lookup stops; a work the
        # mirror says is NOT hers goes on to be looked up like anything else,
        # and the denial rides the line that reports what she found.
        self.last_verdict = None
        if self.lore is None and self.anime_kb is None:
            return False
        names = [n for n in (q.get("name") or "", q.get("term") or "", q.get("show") or "") if n]
        try:
            got = works.identify(names, config=self.config, store=self.store, clock=self.clock,
                                 known=self.known, anime_kb=self.anime_kb, lore=self.lore,
                                 search=None, shape=("work" if q.get("kind") in ("anime", "manga") else ""),
                                 allow_search=False, asked_by="arrived")
        except Exception as e:
            logger.log(f"[works] not resolved for {names[:1]}: {type(e).__name__}: {e}"[:200])
            return False
        if got and got.get("role"):
            self.last_verdict = got["role"]
        if not got or not got.get("hers"):
            return False
        self.store.add_event(self.clock.now_ts(), self.clock.date_str(), "lore",
                             f"he named {got['names'][0]}"
                             + (f", which she was in as {got['part']}" if got.get("part") else ", a work she was in"), 2)
        logger.log(f"[lookup] {got['names'][0]}: a work of hers ({got.get('part') or 'part unnamed'}) "
                   f"via {got.get('source')}; nothing fetched")
        return True

    def _attach_kb(self, rec, term, kind, text, source):
        """Fetch a fuller Japanese overview from the knowledge base and attach
        it to the lookup, by kind: an anime series (+ the named episode's
        beats), a seiyuu's bio, or a game / eroge's premise. Cached, so a
        second mention of the same thing is free."""
        try:
            anime_ish = kind == "anime" or "series" in (source or "") or "anime" in (source or "")
            seiyuu_ish = kind in ("seiyuu", "voice actor", "person") or "seiyuu" in (source or "")
            game_ish = kind == "game"
            if anime_ish and self.anime_kb:
                title, ja = term, ""
                ep = self.recap.episode_in(text)
                aid, mtype = self._which_work(term, ep, text)
                if aid:
                    ent = self.anime_kb.entry(aid) or {}
                    title = ent.get("title") or title
                    mtype = mtype or ent.get("type", "")
                    ja = self.anime_kb.japanese_title(aid)
                search_title = ja or title      # kanji finds real あらすじ blogs; romaji finds databases
                ov = self.recap.series_overview(title, ja=search_title)
                if ov:
                    rec["overview"] = ov[:1600]
                    rec["overview_label"] = "what that show is about"
                if ep:
                    beats = self.recap.recap_for({"title": title, "ja": search_title,
                                                  "kind": "anime", "ep": ep,
                                                  "aid": aid, "mtype": mtype}, ep,
                                                 anime_id=aid)
                    if beats:
                        rec["episode"] = ep
                        rec["episode_beats"] = beats[:1600]
            elif seiyuu_ish and self.anime_kb:
                pid, nm = self.anime_kb.find_person(term)
                ja = self.anime_kb.person_name_jp(pid) if pid else ""
                ov = self.recap.person_overview(nm or term, ja=ja)
                if ov:
                    rec["overview"] = ov[:1600]
                    rec["overview_label"] = f"who {nm or term} is (the seiyuu)"
            elif game_ish:
                ov = self.recap.work_overview(term, ja=term)
                if ov:
                    rec["overview"] = ov[:1600]
                    rec["overview_label"] = "what that game is"
            if rec.get("overview") or rec.get("episode_beats"):
                logger.log(f"[lookup] kb extra for {term} ({kind}): overview={bool(rec.get('overview'))} ep={rec.get('episode')}")
        except Exception as e:
            logger.log(f"[lookup] kb extra failed: {type(e).__name__}: {e}"[:160])

    def _which_work(self, term, ep, his_text):
        """(anime_id, media type) for the work a title HE TYPED means.

        His own list first, ranked (`AnimeKB.resolve_candidates`): an entry
        that cannot have the episode he named is dropped, and where more than
        one survives the resolver's role is asked -- on this thread, which is
        already paying for two calls, and never on a reply path. Only when
        his list has nothing of that name does this fall through to the
        MyAnimeList search, which answers every query and so can never
        decide anything on its own.

        (None, "") when nothing local matched and the search found nothing."""
        try:
            cands = self.anime_kb.resolve_candidates(term, ep=ep)
        except Exception as e:
            logger.log(f"[resolver] his list not ranked for {term!r}: {type(e).__name__}")
            cands = []
        if cands and self.resolver is not None:
            for cd in cands:
                ent = self.anime_kb.entry(cd.get("aid")) or {}
                cd.setdefault("season", ent.get("season", ""))
                cd.setdefault("blurb", ent.get("synopsis", ""))
            q = f"which work he means by {term!r}" + (f" episode {ep}" if ep else "")
            key = "named|%s|ep%d|%s" % (_resolver.norm(term), int(ep or 0),
                                        "+".join(str(cd.get("aid")) for cd in cands))
            cue = (f"what he wrote: {str(his_text or '')[:400]}\n"
                   f"the title he typed: {term}"
                   + (f"\nthe episode he named: {ep}" if ep else ""))
            chosen, _by, _unsure = self.resolver.choose_work(q, cands, cue, key)
            if chosen:
                return int(chosen["aid"]), chosen.get("type", "")
            if cands:
                return None, ""
        if cands:
            return int(cands[0]["aid"]), cands[0].get("type", "")
        aid, _t = self.anime_kb.resolve(term)
        return (int(aid) if aid else None), ""

    def _count(self):
        today = self.clock.date_str()
        self.store.bump_today("lookup_counts", today)

    def _mark_known(self, key, fields):
        """Write extra fields onto the thing just kept. One owner for the
        write (`KnownThings.mark`): the sight used to patch the same rows."""
        try:
            return self.known.mark(key, fields)
        except Exception as e:
            logger.log(f"[known] {key} not marked: {type(e).__name__}")
            return False

    def _last_of_hers(self):
        """What SHE last put in front of him that his message could be about:
        a post she sent (its author, its text, and what the picture on it
        is), a thing she looked up, a title she named. Her last
        `lookup.anchor_turns` turns.

        "nani kore?" about a link she sent one turn earlier is exactly the
        case where the thing is knowable from the record and unknowable from
        the sentence: on 2026-09-06 this call was handed his message alone,
        answered "nothing in it worth looking up", and what he was asking
        about was in the save the whole time
        (`data/retired/20260906_1831_yanineko_check/REPORT.md` §2b)."""
        n = int(getattr(self.config.lookup, "anchor_turns", 3) or 0)
        if n <= 0:
            return []
        lines, first_ts = [], 0.0
        try:
            hers = [m for m in (self.store.recent_messages(40) or [])
                    if m.get("role") != "user" and str(m.get("text") or "").strip()][-n:]
        except Exception as e:
            logger.log(f"[lookup] what she last sent was not read: {type(e).__name__}")
            return []
        if not hers:
            return []
        first_ts = float(hers[0].get("ts") or 0)
        shared = self.store.get("x_shared", {}) or {}
        for m in hers:
            text = str(m.get("text") or "")
            hit = re.search(r"(?:x|twitter)\.com/\w+/status/(\d+)", text)
            meta = shared.get(hit.group(1)) if hit else None
            if isinstance(meta, dict) and (meta.get("author") or meta.get("text")):
                pic = str(meta.get("images") or "")[:160]
                lines.append(f"SHE SENT HIM THIS POST: @{meta.get('author', '')}: "
                             + str(meta.get("text", ""))[:160]
                             + (f" -- the picture on it: {pic}" if pic else
                                " -- nothing here says what the picture on it is"))
                continue
            try:
                named = self._names_a_thing(text, api=False)
            except Exception:
                named = None
            if named:
                lines.append(f"SHE NAMED THIS: {named[0]} ({named[1][1]})")
        try:
            for r in (self.store.get("lookups", []) or [])[-4:]:
                if float(r.get("ts") or 0) >= first_ts and str(r.get("term") or "").strip():
                    lines.append(f"SHE LOOKED UP {r['term']}: {str(r.get('gist') or '')[:120]}")
        except Exception:
            pass
        return lines

    def _in_play(self):
        """What the classifier needs to anchor a bare name: the page open in
        front of him, the episode he is playing, and the shows the last few
        lookups landed on. Japanese titles where the knowledge base has them,
        since that is what he types.

        The page comes from the one record the resolution writes
        (`sim/works.py`), never from the module that watches his player: on
        2026-09-03 this block told the classifier he had episode 13 of one
        show open while the page in front of him was a different work
        entirely, and the classifier anchored a bare name on the wrong one."""
        lines = []
        try:
            r = works.in_front_of_him(self.store, self.clock, self.config)
            if r:
                nm = next((n for n in (r.get("names") or []) if re.search(r"[぀-ヿ一-鿿]", n)), "") \
                    or (r.get("names") or [""])[0]
                lines.append(f"THE PAGE OPEN IN FRONT OF HIM RIGHT NOW: 『{nm}』"
                             + (f" -- a work she was in, as {r.get('part')}" if r.get("hers") and r.get("part") else ""))
        except Exception as e:
            logger.log(f"[lookup] what is in front of him not read: {type(e).__name__}")
        try:
            it = self.watching.current() if self.watching else None
            if it:
                lines.append(f"PLAYING RIGHT NOW: 『{it.get('ja') or it.get('title')}』 episode {it.get('ep')}")
        except Exception:
            pass
        # what SHE last put in front of him, before the shows: his "nani
        # kore?" is about that and about nothing else
        try:
            lines.extend(self._last_of_hers())
        except Exception as e:
            logger.log(f"[lookup] the anchor of what she sent was not built: {type(e).__name__}")
        try:
            names = []
            for aid in self._shows_in_play()[:4]:
                ja = self.anime_kb.japanese_title(aid) if self.anime_kb else ""
                t = ja or (self.anime_kb.brief(aid) or "").split("\n")[0][:40] if self.anime_kb else ""
                if t and t not in names:
                    names.append(t)
            if names:
                lines.append("TALKED ABOUT LATELY: " + "; ".join(f"『{n}』" for n in names))
        except Exception:
            pass
        return "\n".join(lines)

    def _named_typesafe(self, user):
        """(named, kind) from Jev: named is `no`/`yes`/None, and kind is one of
        the kinds or "" when the use is off or under its floor."""
        ts = self.typesafe
        if ts is None or not ts.ready("lookup"):
            return None, ""
        use = ts.use("lookup") or {}
        floor = float(use.get("threshold", 0.5))
        questions = {
            "named": {"type": "choice",
                      "instructions": "Does his message name a specific concrete thing she might "
                                      "quietly look up -- an anime, manga, game, song or artist, film, "
                                      "show, book, product, place, YouTuber, site, seiyuu, or an anime "
                                      "character by name? Only a concrete named thing, or one so "
                                      "clearly described that a search would find it. Not his "
                                      "feelings, not his plans, not generic words ('the show') unless "
                                      "the message makes the title clear. A bare Japanese word with no "
                                      "show anchored is not a character, it is a word.",
                      "criteria": {"yes": "he names a concrete thing",
                                   "no": "he names nothing concrete"}},
            "kind": {"type": "choice",
                     "instructions": "If he names one, which kind is it? A character counts as its "
                                     "own kind, not as the show it is from.",
                     "criteria": {k: k for k in self.KINDS}},
        }
        answers = ts.ask("lookup", {"his message and what is in play": user}, questions)
        if not answers:
            return None, ""
        n, nconf = ts.choice(answers, "named")
        if nconf is None or nconf < floor:
            return None, ""
        if n == "no":
            logger.log(f"[lookup] typesafe: he named nothing concrete (conf {nconf:.2f})")
            return "no", ""
        k, kconf = ts.choice(answers, "kind")
        if k in self.KINDS and kconf is not None and kconf >= floor:
            logger.log(f"[lookup] typesafe: {k} (conf {kconf:.2f})")
            return "yes", k
        return "yes", ""

    def _extract(self, text):
        ctx = self._in_play()
        user = (f"IN PLAY:\n{ctx}\n\n" if ctx else "") + f"HIS MESSAGE:\n{text[:1200]}"
        data, raw = self.llm.call_json("lookup", [
            {"role": "system", "content": self.config.prompt_text("lookup")},
            {"role": "user", "content": user}])
        # The classifier's `named` gates the lookup; its `kind` stands over the
        # role's when it answers above its floor. `term`/`name`/`show` stay the
        # role's.
        jnamed, jkind = self._named_typesafe(user)
        if jnamed == "no":
            return None
        if not isinstance(data, dict) or not data.get("term"):
            return None
        return {"term": str(data["term"]).strip()[:80], "kind": (jkind or str(data.get("kind", "") or ""))[:20],
                "name": str(data.get("name", "") or "").strip()[:40], "show": str(data.get("show", "") or "").strip()[:80]}

    def _character_page(self, name, show, his_text):
        """A character he named, read at the fan encyclopedia and condensed.

        The show is the anchor and the search key: `site:dic.pixiv.net 『show』
        name` finds the article, whose URL carries the full name (丸井みつば
        for みつば). Cached in `recaps` under that key, so a second mention is
        free. Returns (digest, source) or ("", "")."""
        c = self.config.lookup
        if not (getattr(c, "character_pages", False) and self.recap):
            return "", "", []
        try:
            text, full, url = self.recap.character_page(name, show, c.character_query, list(c.character_hosts))
        except Exception as e:
            logger.log(f"[lookup] character page failed: {type(e).__name__}")
            return "", "", []
        if not text:
            logger.log(f"[lookup] no encyclopedia page for {name} ({show})")
            return "", "", []
        raw = self._character_digest(name, show, full, text, url)
        if not raw or raw.startswith("なし"):
            logger.log(f"[lookup] the page for {name} ({show}) is not about that character: {url[:80]}")
            return "", "", []
        # the last line carries the names she is called by; they are what a
        # later message of his will be matched against
        aliases = []
        lines = raw.split("\n")
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip().startswith("別名"):
                aliases = [a.strip() for a in re.split(r"[、,，/／\s]+", lines[i].split(":", 1)[-1].split("：", 1)[-1]) if a.strip()]
                del lines[i]
                break
        digest = " ".join(" ".join(lines).split())
        names = [n for n in [name, full] + aliases if n]
        return digest[: int(c.character_max_chars)], f"pixiv dic ({full or name})", names

    def _character_digest(self, name, show, full, text, url):
        """The fan-encyclopedia page condensed by the `character_digest` role.

        The page is about a character in somebody else's show and the role that
        condenses it names nobody of ours and takes no point of view
        (`prompts/character_digest.txt`), so the answer belongs to the world:
        it goes in the machine's store under the same key the page is filed
        under, and the second character reads it for nothing."""
        def _call():
            try:
                out = self.llm.call("character_digest", [
                    {"role": "system", "content": self.config.prompt_text("character_digest")},
                    {"role": "user", "content": f"NAME AS HE TYPED IT: {name}\nSHOW: {show}\nFULL NAME FROM THE PAGE: {full}\n\n{text[:9000]}"}])
            except Exception as e:
                logger.log(f"[lookup] character digest failed: {type(e).__name__}")
                return None
            s = str(out or "").strip()
            return {"text": s, "source": url} if s else None
        if self.retrievals is None:
            return (_call() or {}).get("text") or ""
        try:
            model = str((self.config.model("character_digest") or {}).get("model") or "")
        except Exception:
            model = ""
        row = self.retrievals.get_or_fetch("character_digest", f"{show}:{name}", _call,
                                           model=model)
        return (row or {}).get("text") or ""

    def _shows_in_play(self, term=""):
        """The anime already in this conversation, newest first. A character
        name means nothing on its own -- "Rei" is in dozens of his shows -- so
        whatever they were just talking about decides it. Two sources: a
        series this lookup itself can resolve out of the term (he usually says
        "makeine, yanami was best girl" in one breath), and the series his
        recent lookups landed on."""
        ids = []
        try:
            for row in (self.store.get("recent_anime_ids", []) or [])[-6:]:
                aid = row.get("aid") if isinstance(row, dict) else row
                if aid and aid not in ids:
                    ids.append(aid)
        except Exception:
            pass
        if term:
            try:
                aid, _ = self.anime_kb.resolve(term)
                if aid and aid not in ids:
                    ids.insert(0, aid)
            except Exception:
                pass
        return ids

    def _remember_show(self, aid):
        """Keep what she just looked up, so the next character name lands in
        the right show."""
        try:
            rows = [r for r in (self.store.get("recent_anime_ids", []) or [])
                    if (r.get("aid") if isinstance(r, dict) else r) != aid]
            rows.append({"aid": aid, "ts": self.clock.now_ts()})
            self.store.set("recent_anime_ids", rows[-8:])
        except Exception:
            pass

    def _kb(self, term, kind):
        """The series card (or the seiyuu card) from his history DB. A seiyuu
        name is tried first when the kind says so, else as a title; a seiyuu he
        names who is also in the cast of something he watched resolves too."""
        try:
            prefer = self._shows_in_play(term)
            if kind in ("character", "anime character"):
                hit = self.anime_kb.find_character(term, prefer=prefer)
                if hit:
                    card = self.anime_kb.character_brief(hit)
                    if card:
                        return card, "his history (character card)"
            if kind in ("seiyuu", "voice actor", "person"):
                pid, nm = self.anime_kb.find_person(term)
                if pid:
                    card = self.anime_kb.person_brief(pid)
                    if card:
                        return card, "his history (seiyuu card)"
            # A name the classifier called a person is not tried as a show: the
            # MAL title search answers every query, and 高垣彩陽 came back as a
            # Chinese chibi short "from his history", which reached her prompt.
            if kind in ("seiyuu", "voice actor", "person", "character", "anime character"):
                return "", ""
            aid, title = self.anime_kb.resolve(term)
            if aid:
                self._remember_show(aid)
                card = self.anime_kb.brief(aid)
                if card:
                    return card, "his history (series card)"
            # a character or a seiyuu typed without the kind being caught.
            # Character first: he names them far more often than he names a
            # voice actor, and a character resolves off his own cast rows.
            hit = self.anime_kb.find_character(term, prefer=prefer)
            if hit:
                card = self.anime_kb.character_brief(hit)
                if card:
                    return card, "his history (character card)"
            pid, nm = self.anime_kb.find_person(term)
            if pid:
                card = self.anime_kb.person_brief(pid)
                if card:
                    return card, "his history (seiyuu card)"
        except Exception as e:
            logger.log(f"[lookup] kb failed: {type(e).__name__}")
        return "", ""

    def _mal_list(self, term):
        try:
            rows = self.mal.search_list(term) if hasattr(self.mal, "search_list") else []
        except Exception:
            rows = []
        return "\n".join(rows[:3])

    # A web search goes out of date, unlike a page about an episode that was
    # broadcast years ago, so the machine's copy of one is read for a month and
    # then fetched again.
    SEARCH_TTL_SECONDS = 30 * 86400

    def _search(self, term, kind):
        """What the web says about the thing he named: (text, where from).

        The fetch is about the WORLD -- his anime database's entry for a title,
        or the text of a page of search results -- so it is kept once for the
        machine and both characters read it. What she makes of it (`_gist`, in
        her own words and her own language) is hers and stays in her save."""
        key = "%s|%s" % (str(kind or "thing").strip().lower(), str(term or "").strip().lower())
        if self.retrievals is None:
            got = self._search_now(term, kind)
            return (got or {}).get("text") or "", (got or {}).get("source") or ""
        row = self.retrievals.get_or_fetch("web_search", key,
                                           lambda: self._search_now(term, kind),
                                           ttl=self.SEARCH_TTL_SECONDS)
        if not row:
            return "", ""
        return row.get("text") or "", row.get("source") or ""

    def _search_now(self, term, kind):
        """The fetch itself. None when nothing came back, so nothing is stored
        and the next caller may try again."""
        c = self.config.lookup
        sv = self.config.sensor_view
        if kind in ("anime", "manga") and getattr(sv, "mal_client_id", ""):
            typ = "manga" if kind == "manga" else "anime"
            url = f"https://api.myanimelist.net/v2/{typ}?q={urllib.parse.quote(term)}&limit=3&fields=synopsis,mean,media_type,num_episodes,start_date,genres"
            try:
                req = urllib.request.Request(url, headers={"X-MAL-CLIENT-ID": sv.mal_client_id, **UA})
                data = json.loads(urllib.request.urlopen(req, timeout=c.timeout_seconds).read().decode("utf-8"))
                out = []
                for n in data.get("data", [])[:3]:
                    a = n.get("node", {})
                    out.append(f"{a.get('title')} ({a.get('media_type', '')}, {a.get('start_date', '')[:4]}, mean {a.get('mean', '?')}, {a.get('num_episodes', '?')} eps; {', '.join(g['name'] for g in a.get('genres', [])[:4])}): {(a.get('synopsis') or '')[:500]}")
                if out:
                    return {"text": "\n".join(out), "source": "MAL"}
            except Exception as e:
                logger.log(f"[lookup] MAL search failed: {type(e).__name__}")
        # plain web search, results page text only
        try:
            url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(term + (f" {kind}" if kind else ""))
            req = urllib.request.Request(url, headers=UA)
            page = urllib.request.urlopen(req, timeout=c.timeout_seconds).read().decode("utf-8", "ignore")
            titles = re.findall(r'class="result__a"[^>]*>(.*?)</a>', page, re.S)
            snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', page, re.S)
            rows = []
            for t, s in list(zip(titles, snippets))[:5]:
                rows.append(html.unescape(re.sub(r"<[^>]+>", "", t)).strip() + ": " + html.unescape(re.sub(r"<[^>]+>", "", s)).strip())
            if rows:
                return {"text": "\n".join(rows), "source": "web"}
        except Exception as e:
            logger.log(f"[lookup] web search failed: {type(e).__name__}")
        return None

    def _gist(self, term, kind, found, his_text):
        data, raw = self.llm.call_json("lookup_gist", [
            {"role": "system", "content": self.config.prompt_text("lookup_gist")},
            {"role": "user", "content": f"WHAT HE WROTE: {his_text[:400]}\nTHE THING: {term} ({kind or 'unknown kind'})\n\nWHAT THE SEARCH SHOWED:\n{found[:3000]}"}])
        if not isinstance(data, dict) or not data.get("gist"):
            return ""
        # a series / seiyuu card carries names he cares about; give it room
        cap = 900 if "his history" in (found[:40] + " ") or "him:" in found or "he has seen them as" in found else 600
        return str(data["gist"]).strip()[:cap]

    # ---------------- a search she asked for ----------------

    def _cut_off(self, access=None):
        """True when her day leaves her no way to look anything up.

        The scene carries that rule for everything else that reads it
        (`sim/impulse.py`, `sim/diary.py`), so a caller holding the scene
        passes its own field and the rest read the newest scene: while she is
        up a new one is written every director tick, and the one scene that
        stands for hours is the night, when the answer is the same either
        way. `Persona.generate` used to be the only guard, so a search her
        sight asked for ran whatever her day said."""
        if access:
            return str(access) == "none"
        try:
            return str((self.store.last_scene() or {}).get("phone_access") or "") == "none"
        except Exception:
            return False

    def _from_known(self, query, why):
        """What she asked for, answered out of a thing she already has.

        The automatic path off his message keeps every find as a thing she
        knows, and while that is still fresh her situation is carrying it: a
        second fetch buys the same digest twice and writes over the record it
        is already in. `from_known` is what tells her situation to say she
        knows it rather than that she just looked it up, and `asked_by` stays
        whoever's it was, because she did not search now."""
        hours = float(getattr(self.config.lookup, "search_known_hours", 6.0) or 0)
        if hours <= 0:
            return None
        try:
            rows = self.known.recall(query, count=False)
        except Exception as e:
            logger.log(f"[search] what she knows not read: {type(e).__name__}")
            return None
        now = self.clock.now_ts()
        for r in rows:
            age = now - float(r.get("ts") or 0)
            if age > hours * 3600 or not str(r.get("text") or "").strip():
                continue
            logger.log(f"[search] '{query}': not fetched again -- {r.get('key')} came in {int(age // 60)} min ago and she has it")
            return {"date": self.clock.date_str(), "hm": self.clock.hm(), "ts": now,
                    "term": query, "kind": "search", "gist": str(r.get("text"))[:600],
                    "source": r.get("source") or "what she already knew", "why": str(why or "")[:160],
                    "hers": bool(r.get("hers")), "part": str(r.get("part") or ""),
                    "asked_by": str(r.get("asked_by") or "arrived"), "from_known": True,
                    "known_key": r.get("key")}
        return None

    def search(self, query, why="", keep_as=None, by="arrived", access=None):
        """One web search and one gist, now, on the calling thread: what she
        wanted to know (`[search: ...]` in her draft, or her sight at a page
        of his). Counted per day (`lookup.search_per_day`); kept by name as a
        thing she knows when `keep_as` is (key prefix, names, kind). `by` is
        who wanted it -- "her" when a draft of hers asked, "arrived" for
        anything the machinery started -- and goes on the record, so nothing
        downstream has to guess. `access` is the scene's phone rule when the
        caller holds the scene. Returns the record, or None when nothing came
        back, she cannot look right now, or the day's searches are spent."""
        c = self.config.lookup
        query = " ".join(str(query or "").split())[:120]
        if not c.enabled or not query:
            return None
        if self._cut_off(access):
            logger.log(f"[search] not run (she has no way to look anything up right now): {query}")
            return None
        had = self._from_known(query, why)
        if had:
            return had
        today = self.clock.date_str()
        cap = int(getattr(c, "search_per_day", 8) or 8)
        if self.store.today_count("search_counts", today) >= cap:
            logger.log(f"[search] not run ({cap} today already): {query}")
            return None
        found, source = self._search(query, "")
        # a question about a work she already knows by name (a page he had
        # open, a thing looked up before): the series' own Japanese lead --
        # the episode count, whether it went on -- answers "is there a season
        # 2" where a results page shows a manga volume. Cached after the first
        # read (`recaps`).
        try:
            if self.recap:
                for r in self.known.recall(query, count=False)[:1]:
                    if str(r.get("kind", "")) == "work" and r.get("names"):
                        ja = next((n for n in r["names"] if re.search(r"[぀-ヿ一-鿿]", n)), "")
                        ov = self.recap.series_overview(r["names"][0], ja=ja) if ja else None
                        if ov:
                            found = f"WHAT THE SERIES' OWN PAGE SAYS ({ja}):" + chr(10) + ov[:1800] + chr(10) + chr(10) + "SEARCH RESULTS:" + chr(10) + (found or '(none)')
                            source = "ja.wikipedia + " + (source or "web")
        except Exception as e:
            logger.log(f"[search] the series' page not read: {type(e).__name__}")
        if not found:
            logger.log(f"[search] '{query}': nothing came back")
            return None
        data, raw = self.llm.call_json("search_gist", [
            {"role": "system", "content": self.config.prompt_text("search_gist")},
            {"role": "user", "content": f"WHY SHE LOOKED: {why or 'she wanted to know'}\nWHAT SHE SEARCHED FOR: {query}\n\nWHAT THE SEARCH SHOWED:\n{found[:3000]}"}])
        self.store.bump_today("search_counts", today)
        if not isinstance(data, dict) or not str(data.get("gist") or "").strip():
            logger.log(f"[search] '{query}': the results did not answer it")
            return None
        rec = {"date": today, "hm": self.clock.hm(), "ts": self.clock.now_ts(), "term": query, "kind": "search",
               "gist": str(data["gist"]).strip()[:600], "source": source, "why": str(why or "")[:160],
               "hers": bool(data.get("hers")), "part": str(data.get("part") or "").strip()[:80],
               "asked_by": "her" if str(by) == "her" else "arrived"}
        if keep_as:
            try:
                prefix, names, kind = keep_as
                key = f"{prefix}:{names[0]}"
                if self.known.add(key, list(names), kind, rec["gist"], source=source):
                    self._mark_known(key, {"hers": rec["hers"], "part": rec["part"], "asked_by": rec["asked_by"]})
                    rec["known_key"] = key
            except Exception as e:
                logger.log(f"[known] not kept: {type(e).__name__}")
        self.store.set("lookups", (self.store.get("lookups", []) + [rec])[-self.config.lookup.keep:])
        self.store.add_event(self.clock.now_ts(), today, "lookup",
                             (f"(private) she wanted to know and looked up {query}: " if rec["asked_by"] == "her"
                              else f"(private) she looked up {query}: ") + rec["gist"][:120], 1)
        logger.log(f"[search] '{query}' via {source}: {rec['gist'][:160]}" + (f" (hers: {rec['part']})" if rec["hers"] else ""))
        return rec

    # ---------------- for her prompt ----------------

    def recent_text(self, days=7):
        rows = self.store.get("lookups", [])[-8:]
        return "\n".join(f"- {r['date'][5:]}: {r['term']}: {r['gist'][:140]}" for r in rows)
