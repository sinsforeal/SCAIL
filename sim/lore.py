"""What she happens to know, retrieved a few lines at a time.

The persona dataset is 1,664 claims over 346 records and nothing read it. All
of it is hers -- her own programme, the people in the booth, what she said on
air about her flat and her family -- and none of it reached the running
character, so she could be told the name of her own radio show and answer as
though he had said "recordings of your voice".

The design is `docs/yukarin-lorebook.md` §3.2 and the split it makes is the
important part. **What is true of her every minute is not retrieved**: her
register, her sentence endings, her mechanisms, the four people behind the
booth glass. That lives in the bible, where it is always true. This is for the
*occasional* -- the shoes somebody took by mistake, the ten-year-old tin of
crab, the flat she used to check the listing for -- which is worth having only
on the turn it comes up and is noise on every other.

So the two things this module is really made of are both refusals:

  * it retrieves nothing unless the conversation names something a record is
    about, because a bucket that always fires is a character who always has a
    fact to tell you; and
  * a record it has offered is not offered again off her own words, because
    the failure mode of every lorebook is an anecdote calcifying into a
    catchphrase inside a week.

**Who said the naming word decides whether an already-told record comes back.**
The conversation is asked, not his newest message alone, and her own words
count: she is often the one who raised the thing, and what she just said should
be able to remind her of the rest of it. But she is also the one who just told
it, and her telling stays in the window for the next few turns, so an anecdote
she has already given him names its own record again on the next call and on
the one after that. On 2026-09-02 she told the story about being stopped at
Umeda station and denying who she was; the record was retrieved off her own
telling at 15:37, 16:09, 16:14 and 16:21, she told it three turns running, and
the continuity editor eventually threw away a whole drafted reply for repeating
itself -- a paid call spent on what the suppression exists to stop one layer
earlier. His messages never once named it.

So the two sides of the conversation are kept apart. A record HE names is
always reachable, at any distance, because a person asked twice about her own
job answers twice -- that is what `lore.suppress_days` being 0 means and it is
his decision. A record only HER OWN words name is held for
`lore.own_words_days` once she has been offered it, because that is not the
conversation reaching for something, it is the anecdote feeding itself.

**A record is found by name, never by resemblance.** Every record carries a
short list of phrases somebody would actually type when they mean it -- the
programme's name, the character's name, the thing itself -- written by reading
each record (`yukarin/persona/triggers.json`, `yukarin/tools/triggers.py`).
Those phrases decide the match and nothing else does. Her own words stay the
payload: once a record is chosen, what is rendered is her claim off the tape.

The alternative was tried at length and cannot be made to work. Comparing his
message against the record's text is comparing it against conversational
speech, which is mostly grammar, and grammar collides with any sentence by
accident. Weighting by how rare a fragment is in the record set makes it worse
rather than better, because every record here is about the same person: her
subject words -- 黒うさぎ, 矢野, 弟 -- are the COMMON ones and score low, while
the character runs that happen to span a question's grammar are rare and score
high. Asked the name of her own programme, the fragments that stood out were
「ってどん」, 「どんな」, 「な番組」, 「組なの」; her programme's record shared none of
them and a record about a witch won on 「どんな」. Five repairs were measured and
all five failed the same way: dividing by the heaviest fragments only, an
absolute floor on the shared weight, dropping the pure kana, requiring a
distinctive fragment to be shared. A list of names has no grammar in it, so
the fault is gone rather than tuned around.

**`lore.era_gate` is off, by his decision, and with it off none of what
follows runs**: nothing is withheld, nothing is cut back, and every claim of
every record is reachable. The mechanism is kept because it works and because
the flag is one line.

Claims marked as coming from after the corpus ends are withheld while the gate
is on. The first pass marked them on the largest year printed in the sentence
rather than on when the thing described began, which shut the record of her own
radio programme -- it opens in 2003 and the same sentence traces it to 2016 --
along with her debut single and two roles she had been playing for years, and a
character who cannot reach her own show reads as somebody with no career at
all. That is why the flag went off. The verdicts have since been read again
(`yukarin/audit/lore_gate.py`): 165 of the 178 are genuinely after her, and the
13 that begin in her past and run on past the window carry `until_then`, the
part of the bullet that had happened by then -- the bullet stays held and that
part is what she may volunteer. So turning the gate on now costs her the
sequels, the chart placings and the arena shows, and not her own programme. The
one thing that opens the rest is him: when he watches a work she is in, the
record for it is released and nothing else is (`sim/watching_him.py`), and with
the gate off that mechanism has nothing to release and idles.
"""

import io
import json
import math
import os

import logger
from sim import works
from sim.attention import tag
from sim.watching_him import WatchingHim

# Kinds that are standing rather than occasional. Her register and her
# mechanisms are true every minute and belong in the bible; retrieving "how she
# refers to herself" as a line of the day would be noise competing for room
# with something she actually did.
_STANDING = ("register", "mechanism")

# The kinds of record that are a part she played or a work she was in. One
# list, in `sim/works.py`, so the retrieval and the resolution cannot
# disagree about what counts as her own career.
_ROLE_KINDS = works.ROLE_KINDS


class Lore:
    def __init__(self, config, store, clock):
        self.config = config
        self.store = store
        self.clock = clock
        self._mtime = None
        self._recs = []
        self._weight = {}
        # A blank path and a wrong path are different things and are answered
        # differently. No path at all is a character who has no record of her
        # own: she builds, every retrieval below returns nothing, and the one
        # boot line says so, because an empty path used to fail silently and
        # the only sign of it was a retrieval that never fired. A path that
        # NAMES a file is a promise: if the file is not there, or holds no
        # claim anything can reach, that is a wrong path rather than an absent
        # one and she does not start, because her own past is what she is made
        # of and running without it is running as somebody else.
        if getattr(config.lore, "enabled", False):
            path = getattr(config.lore, "file", "") or ""
            if not path:
                logger.log("[lore] no record for her; nothing to be reminded of")
            else:
                if not os.path.exists(path):
                    raise SystemExit(f"[lore] lore.enabled but the record is missing: {path!r}; refusing to start")
                self._load()
                if not self._recs:
                    raise SystemExit(f"[lore] the record at {path} loaded no reachable claims; refusing to start")
                logger.log(f"[lore] {len(self._recs)} claim(s) reachable by name from {path}")

    # ---------------- the record ----------------

    def _contact(self):
        """The works he has brought her into contact with, written by
        `sim/watching_him.py` when he watches something she is in."""
        try:
            return list(self.store.get("lore_contact", []) or [])
        except Exception:
            return []

    def _phrases(self):
        """The phrases that let a record be found, by record id: the record
        file's own list and the memory file's, merged (`triggers_file`,
        `memory_triggers_file`)."""
        out, stamp = {}, 0.0
        for key in ("triggers_file", "memory_triggers_file"):
            path = getattr(self.config.lore, key, "")
            if not path or not os.path.exists(path):
                continue
            try:
                d = json.load(io.open(path, encoding="utf-8"))
            except (OSError, ValueError) as e:
                logger.log(f"[lore] phrases not read ({key}): {type(e).__name__}")
                continue
            out.update(d.get("records", d) or {})
            try:
                stamp += os.path.getmtime(path)
            except OSError:
                pass
        return out, stamp

    def _memories(self, phrases):
        """Her seeded memories as records (`lore.memory_file`,
        yukarin/week/memory_records.py). His call: a line off the corpus is
        her record, not a memory she is carrying, so it is found by name
        like the rest and never rotated through a prompt. Rendered with its
        month, because when she said it is part of what it is."""
        path = getattr(self.config.lore, "memory_file", "")
        if not path or not os.path.exists(path):
            return [], 0.0, 0
        try:
            raw = json.load(io.open(path, encoding="utf-8"))
        except (OSError, ValueError) as e:
            logger.log(f"[lore] memory records not read: {type(e).__name__}")
            return [], 0.0, 0
        recs, unnamed = [], 0
        for r in raw.get("records", raw) or []:
            if r.get("status", "active") != "active":
                continue
            keys = [str(p).strip().lower() for p in (phrases.get(r["id"]) or []) if str(p).strip()]
            if not keys:
                unnamed += 1
                continue
            text = str(r.get("statement") or "").strip()
            if not text:
                continue
            when = str(r.get("date") or "")[:7]
            recs.append({"id": r["id"], "keys": keys, "texts": [f"{when}: {text}" if when else text],
                         "rank": int(r.get("importance") or 0),
                         "kind": "memory", "title": "", "tags": []})
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            mtime = 0.0
        return recs, mtime, unnamed

    def _load(self):
        c = self.config.lore
        path = getattr(c, "file", "")
        if not path or not os.path.exists(path):
            self._recs = []
            return
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            return
        phrases, pmtime = self._phrases()
        memories, mmtime, munnamed = self._memories(phrases)
        # The set of works he has touched is part of what the record MEANS, so
        # it belongs in the cache key beside the file's own timestamp. Keyed on
        # the file alone, a record opened by him watching an episode would stay
        # shut until somebody edited the file.
        contact = self._contact()
        stamp = (mtime, pmtime, mmtime, len(contact))
        if stamp == self._mtime:
            return
        try:
            raw = json.load(io.open(path, encoding="utf-8"))
        except (OSError, ValueError) as e:
            logger.log(f"[lore] not read: {type(e).__name__}")
            self._recs = []
            return
        skip = set(getattr(c, "standing_kinds", None) or _STANDING)
        gate_on = bool(getattr(c, "era_gate", False))
        recs, held, released, unnamed, partial = [], 0, 0, 0, 0
        for r in raw:
            if r.get("status", "active") != "active" or r.get("kind") in skip:
                continue
            keys = [str(p).strip().lower() for p in (phrases.get(r["id"]) or []) if str(p).strip()]
            if not keys:
                # A record nobody would name is a record that never fires. Four
                # are like that on purpose: a list of prices, a count of
                # attempts with no subject in it.
                unnamed += 1
                continue
            # Which text of a record is the FACT depends on where the record
            # came from, and getting this backwards served her truncated
            # fragments of her own speech as things she knows.
            #   * a record read off the tape carries the reading in
            #     `statement` -- "She has one brother, six years younger" --
            #     and its claims are the verbatim cues that evidence it, cut
            #     mid-phrase. The statement is the fact; the claims are the
            #     receipts, and the corpus is the era, so no gate applies.
            #   * a lorebook record is the other way round: prose claims, and
            #     a `statement` that is only its first bullet and may be one
            #     the era gate held.
            tape = any(str(p.get("source", "")).startswith("corpus")
                       for cl in (r.get("claims") or []) for p in (cl.get("provenance") or []))
            # Has he opened this one? A claim held for being after her era is
            # released when he watches the work it is about -- her future
            # reaches her through him, one work at a time, rather than on a
            # date. See sim/watching_him.py for why the match is strict.
            opened = WatchingHim.record_opens(r.get("title", ""), contact)
            texts = []
            if tape and str(r.get("statement") or "").strip():
                texts.append(str(r["statement"]).strip())
            for cl in r.get("claims") or []:
                if not any(str(p.get("source", "")) == "lorebook.v1"
                           for p in (cl.get("provenance") or [])):
                    continue
                gate = cl.get("gate") or {}
                if gate_on and gate.get("hold"):
                    if not opened:
                        held += 1
                        # A bullet that begins in her past and runs on past the
                        # window carries the part of it that had happened by
                        # then (yukarin/audit/lore_gate.py). That part is hers
                        # and is what she may volunteer until he opens the work.
                        part = str(gate.get("until_then") or "").strip()
                        if part:
                            partial += 1
                            texts.append(part)
                        continue
                    released += 1
                t = str(cl.get("text") or "").strip()
                if t:
                    texts.append(t)
            if not texts:
                continue
            # The record's own `statement` is its first bullet and is NOT
            # necessarily one of the claims that survived the gate. Rendering
            # it reached straight past the era gate: her Nanoha record has
            # three held claims and one available, the statement is the first
            # held one, and the retrieval printed sequels running to 2017-18 at
            # a character pinned to 2003. So only an available claim is ever
            # rendered.
            # `kind`, the title and the tags travel with the record. A reader
            # that wants to know whether a title is HERS asks what kind of
            # record it is (the glance tested `kind == "role"` against a dict
            # that had no kind at all, so her own record could never answer),
            # and the tags carry the work's Japanese name beside the romaji
            # one, which is the only local bridge from a romaji page title to
            # a record written in Japanese.
            recs.append({"id": r["id"], "keys": keys, "texts": texts,
                         "rank": int(r.get("importance") or 0),
                         "kind": str(r.get("kind") or ""), "title": str(r.get("title") or ""),
                         "tags": [str(x) for x in (r.get("tags") or []) if x]})
        recs.extend(memories)
        unnamed += munnamed
        # A phrase that names one record points straight at it. One carried by
        # several -- her programme's name is on the programme, on the spin-off
        # and on the album that ran beside it -- points at all of them and is
        # worth proportionately less, so a record the message names twice beats
        # one it half-names once.
        df = {}
        for r in recs:
            for k in set(r["keys"]):
                df[k] = df.get(k, 0) + 1
        n = max(1, len(recs))
        top = math.log(1.0 + n)
        self._weight = {k: math.log(1.0 + n / float(v)) / top for k, v in df.items()}
        self._recs = recs
        self._mtime = stamp
        note = f"[lore] {len(recs)} record(s) she can be reminded of by name"
        if memories:
            note += f", {len(memories)} of them her own memories off the tape"
        if unnamed:
            note += f"; {unnamed} with no phrase, so never found"
        if gate_on:
            note += (f"; {held} claim(s) held until the corpus extends"
                     + (f", {partial} of them leaving the part that is her past" if partial else "")
                     + (f"; {released} released by what he has watched" if released else ""))
        else:
            note += "; the era gate is off, so all of it"
        logger.log(note)

    # ---------------- suppression ----------------

    def _used(self):
        return self.store.get("lore_used", {}) or {}

    def _offered_within(self, days):
        """The records offered inside the last `days`. At 0 the cutoff is the
        current moment and nothing is inside it, which is how `suppress_days`
        turns the hold off without being a special case."""
        cutoff = self.clock.now_ts() - float(days or 0) * 86400
        return {k for k, ts in self._used().items() if float(ts or 0) >= cutoff}

    def _suppressed(self):
        return self._offered_within(self.config.lore.suppress_days)

    def note_offered(self, ids):
        if not ids:
            return
        used = self._used()
        now = self.clock.now_ts()
        for i in ids:
            used[i] = now
        self.store.set("lore_used", used)

    # ---------------- retrieval ----------------

    def match(self, text):
        """The records this text names, as (record, the line about it), with
        no side effects: nothing offered, nothing counted. For a reader that
        wants to know whether a title is hers (the glance) rather than to put
        a line in front of her."""
        if not self.config.lore.enabled:
            return []
        self._load()
        said = str(text or "").lower()
        out = []
        for r in self._recs or []:
            hit = [k for k in r.get("keys", []) if k in said]
            if hit:
                out.append((r, self._render(r, hit)))
        return out

    def work_named(self, names, kinds=()):
        """(record, the line about it) for a role-shaped record whose OWN
        title or tags are one of these names, or None.

        The retrieval proper is by trigger phrase and by nothing else, and
        that rule stands: a phrase is what somebody would type when they mean
        the record. But a work can also arrive as a name nobody typed -- the
        title of the page in front of him -- and a page spells it in romaji
        while her record is written in Japanese. Her records carry both
        spellings in their own tags, so the two are compared as names, whole
        and normalized, never as substrings and never by resemblance.
        `sim/works.py` is the one caller.
        """
        if not self.config.lore.enabled:
            return None
        self._load()
        norm = works.norm
        want = {norm(n) for n in (names or []) if norm(n) and len(norm(n)) >= 4}
        if not want:
            return None
        kinds = set(kinds or ())
        for r in self._recs or []:
            if kinds and str(r.get("kind") or "") not in kinds:
                continue
            for n in [r.get("title") or ""] + list(r.get("tags") or []):
                if norm(n) in want:
                    return r, self._render(r, [str(n).lower()])
        return None

    def lines(self, cue_text, context_text="", echo_text=""):
        """At most `max_lines` things she knows that this moment named.

        Returns tagged lines for the `lore` bucket, or nothing at all -- which
        is the common case and the point. A record scores only for the phrases
        of its own that appear in what was said, so the length of the message
        does not enter into it: a chatty three-turn window and a four-word
        question that both name her programme score the same.

        `context_text` is what the moment is about besides his words -- the
        show he has an episode of open -- and is read exactly like his words,
        because the name of the show he is watching is as good a way of naming
        her part in it as typing it.

        `echo_text` is her own recent messages. It names a record exactly as
        his words do, and it is the ONLY side of the conversation an already
        offered record is held against (see the module docstring).
        """
        c = self.config.lore
        if not c.enabled:
            return []
        self._load()
        if not self._recs:
            return []
        said = (str(cue_text or "") + "\n" + str(context_text or "")).lower()
        echo = str(echo_text or "").lower()
        if not said.strip() and not echo.strip():
            return []
        gone = self._suppressed()
        already = self._offered_within(getattr(c, "own_words_days", 0.0))
        scored, self_fed = [], []
        for r in self._recs:
            hit = [k for k in r["keys"] if k in said]
            mine = [k for k in r["keys"] if k not in hit and k in echo]
            if not hit and not mine:
                continue
            if r["id"] in gone:
                continue
            # Nothing but her own telling named it, and she has been offered it
            # already: that is the anecdote feeding itself, not the
            # conversation reaching for it.
            if not hit and r["id"] in already:
                self_fed.append(r["id"])
                continue
            # 「黒うさぎ」 and 「いたずら黒うさぎ」 are one naming, not two: a phrase
            # inside another phrase of the same record is already counted.
            named = hit + mine
            named = [k for k in named if not any(k != o and k in o for o in named)]
            score = sum(self._weight.get(k, 1.0) for k in named)
            if score >= float(c.min_score):
                scored.append((score, r["rank"], r, named, bool(hit)))
        if self_fed:
            logger.log("[lore] already told, and only her own words named it again: "
                       + ", ".join(self_fed))
        if not scored:
            return []
        # what she reaches for first is what the message named most squarely;
        # between two of those, the one the dataset says matters more to her
        scored.sort(key=lambda x: (-x[0], -x[1]))
        out, offered, chars = [], [], 0
        # 53 lorebook bullets are copied onto the tape record they were judged
        # the same fact as, and kept in their own record too, so the same
        # sentence can be retrieved twice from two ids
        seen = set()
        # A part she played, in a work HE has just named, is not a line she can
        # afford to lose to a crowded tick. On 2026-09-03 he named a 2010 lead
        # of hers, her record for it was retrieved at full score, and the whole
        # block's character cap threw all three lore lines away, so she denied
        # the part. A retrieved line is ordinary and takes its chances; that
        # one is pinned and bypasses the budget. Bounded to `pin_max`, and
        # only when HIS side of the conversation named it: her own telling
        # naming her own anecdote is the loop the suppression exists to stop.
        role_kinds = set(getattr(c, "role_kinds", None) or _ROLE_KINDS)
        pin_score = float(getattr(c, "pin_score", 1.0))
        pin_max = int(getattr(c, "pin_max", 1))
        pinned = 0
        for score, _rank, r, hit, by_him in scored:
            if len(out) >= int(c.max_lines):
                break
            text = self._render(r, hit)
            key = "".join(str(text).split())
            if key in seen:
                continue
            seen.add(key)
            if len(text) > int(c.max_chars_per_line):
                text = text[: int(c.max_chars_per_line)].rstrip() + "…"
            pin = bool(by_him and pinned < pin_max and score >= pin_score
                       and str(r.get("kind") or "") in role_kinds)
            if not pin and chars + len(text) > int(c.max_chars):
                break
            chars += len(text)
            if pin:
                pinned += 1
                logger.log(f"[lore] {r['id']} ({score:.2f}) is a part she played and he named it: pinned")
            out.append(tag(text, source="lore", weight=min(1.0, score), kind="fact", pin=pin))
            offered.append((r["id"], score))
        if offered:
            self.note_offered([i for i, _ in offered])
            logger.log("[lore] " + ", ".join(f"{i} ({s:.2f})" for i, s in offered))
        return out

    @staticmethod
    def _render(rec, hit):
        """The part of the record that is about the phrase he used.

        A record is several claims and only one of them is the answer: her
        programme's record opens with the dates and carries the segment names
        four bullets down. So the claim rendered is the one that says the thing
        he named, and the record's own opening line when none of them does --
        for a record off the tape that opening line is the reading of the cues,
        which is the fact, while the cues themselves are fragments cut
        mid-phrase.
        """
        best, mark = rec["texts"][0], (0, 0)
        for t in rec["texts"]:
            low = t.lower()
            # first the phrase he actually used, then how much of the rest of
            # what the record is about the line names -- "1997年3月26日
            # ポリドールからデビューCD「勇気をください」" over "デビュー期（1997-2000）",
            # both of which answer "when did you debut" and only one of which
            # says anything
            score = (sum(1 for k in hit if k in low),
                     sum(1 for k in rec["keys"] if k in low))
            if score > mark:
                best, mark = t, score
        return best
