"""What the second character sees, because she is on his machine.

She does not carry a phone, she does not open an app and she does not decide
to look: she is inside the machine and what happens on it happens in front of
her. Two things follow from that and both live here, in her own program,
rather than as branches in the shared library.

**A note he opens, she has read.** The old route was the snoop -- a felt
probability of going through his notes folder at night, written for a girl
with an app on her phone and a reason to hide it. She has no such route and
no such secret: he knows she is here. When a note from his vault has been in
front of him for `note_open_seconds`, or he has just written into one, she
reads it whole (`note_max_chars`; the end kept when it is longer, because the
end of a daily note is where the new writing is) through the same `vault`
role a note she opened used to go through, and the takeaway goes where it
went: an event on the day, a line in her index, her picture of him, and a
pinned line in her next reply while it is fresh. Once per note per sitting,
and again once he has written more and `reread_after_seconds` have passed.

**She sleeps when he sleeps and wakes when he does**.
Her plan carries no sleep block; this decides it from his machine, and reads
nothing of the chat. Idle for `sleep_after_idle_minutes`, with the idle
stretch having BEGUN between `night_start` and `sleep_latest_start`, and she
is asleep from the minute he stopped; the moment he touches anything she is
awake, and so is she once the clock passes `night_end` with him still gone,
because that is him out for the day, not asleep. A machine that goes quiet
in the morning is not sleep and never puts her under. The director asks
here before it asks the plan (`Director.sleep_source`), so everything that
coasts through her sleep -- no scene, no state model, no reading -- coasts on
his hours. A collector that is not writing reads as him present and awake:
nobody is put to sleep on a guess.
"""
import datetime
import os
import time

import logger
from sim import wiring
from sim import works
from sensors import vault_monitor
from sensors.system_monitor import _clean_window_title
from world.clock import in_window


import re as _re_mod

# a clock time or a pronoun in a captured title means the pattern ran off the
# title and into the digest's own narration of his afternoon
_RE_TIME = _re_mod.compile(r"\b\d{1,2}:\d{2}\b")

# a name in Japanese script, which is how she would say a title
_RE_JA = _re_mod.compile(r"[぀-ヿ一-鿿]")

# the sites whose page titles name a thing, and how: the subject before the
# site's own name.
_SITES = (
    (_re_mod.compile(r"^(?P<subject>.+?)\s+-\s+MyAnimeList\.net"), "MyAnimeList"),
    (_re_mod.compile(r"^(?P<subject>.+)\s+-\s+Wikipedia"), "Wikipedia"),
    (_re_mod.compile(r"^(?P<subject>.+?)\s+-\s+AniList"), "AniList"),
    (_re_mod.compile(r"^(?P<subject>.+?)\s+-\s+AniDB"), "AniDB"),
    (_re_mod.compile(r"^(?P<subject>.+?)\s+\|\s+Anime-Planet"), "Anime-Planet"),
)
# A type and a year in brackets says "work" and nothing else does. The year
# is optional ("Kodomo no Jikan (TV)") and so is a leading alias, and a page
# whose brackets are only an alias is a work just the same -- which is the
# whole fault: "B-gata H-kei (Yamada's First Time: B Gata H Kei)" was filed
# as a person because its brackets carried no type, and "Mitsuba Marui
# (Mitsudomoe)" IS a character page of exactly that shape. The shape cannot
# separate those two, so it does not try: it says "unknown" and the knowledge
# base settles it (`sim/works.py`).
_WORK_TAG = _re_mod.compile(r"\((?:(?P<alias>[^()]+),\s*)?(?P<type>TV|Movie|OVA|ONA|Special|Music|TV Special|CM|PV|Unknown)"
                            r"(?:\s+\d{4})?\)\s*$")
_ALIAS_TAG = _re_mod.compile(r"\((?P<alias>[^()]{2,60})\)\s*$")
_MEDIUM_TAG = _re_mod.compile(r"\s*\|\s*(Manga|Light Novel|Novel|Manhwa|Manhua|One-shot|Doujinshi)\s*$")
_SUBPAGE = _re_mod.compile(r"\s+-\s+(Characters & Staff|Episodes|Reviews|Recommendations|Stats|Pictures|News|Forum|Clubs|More Info|Videos)\s*$")
# A page of his own account, a login, a forum thread, the site's own chrome:
# a window, not a page about a thing. These used to fall through as "name",
# where a silent return happened to cover them; with the unknown shapes now
# resolved and searchable they have to be excluded on purpose.
_NOT_A_PAGE = _re_mod.compile(r"^(Login|Register|MyAnimeList\.net|Panel|Anime Search|Manga Search|Forums?"
                              r"|.*'s (Profile|Anime List|Manga List|Favorites|Reviews|Recommendations|Clubs|History)"
                              r"|.* Episode \d+ Discussion|.* - Forums?|Search Results.*|Currently Airing.*)$", _re_mod.I)


def page_of(title, proc):
    """What page is in front of him, as {subject, names, site, kind}, or None
    for a window that is not a page about a thing.

    `kind` is what the SHAPE of the title can prove and no more: "work" for a
    page that says it is one (a type in brackets, a medium after a bar),
    "name" for a page whose subject the shape settles, "unknown" for the many
    that it cannot -- a bare title, an alias in brackets, a Wikipedia article
    about anything at all. Who the thing is comes from the knowledge base
    and her own record (`sim/works.py`), not from punctuation."""
    if not proc or not str(proc).lower().startswith(("chrome", "firefox", "msedge")):
        return None
    t = _clean_window_title(str(title or ""), proc)
    for rx, site in _SITES:
        m = rx.match(t)
        if not m:
            continue
        subject = m.group("subject").strip()
        subject = _SUBPAGE.sub("", subject).strip()
        if site == "Wikipedia" and " - " in subject:
            # the image viewer puts the caption first and the article last
            # ("Apple Street View Van - Look Around (Apple) - Wikipedia")
            subject = subject.rsplit(" - ", 1)[-1].strip()
        if _NOT_A_PAGE.match(subject):
            return None
        names = []
        kind = "unknown"
        if _MEDIUM_TAG.search(subject):
            subject = _MEDIUM_TAG.sub("", subject).strip()
            kind = "work"
        mw = _WORK_TAG.search(subject)
        if mw:
            subject = _WORK_TAG.sub("", subject).strip()
            if mw.group("alias"):
                names.append(mw.group("alias").strip())
            kind = "work"
        else:
            ma = _ALIAS_TAG.search(subject)
            if ma:
                # an alias, or the show a character belongs to: either way a
                # second name for the resolution to try
                subject = _ALIAS_TAG.sub("", subject).strip()
                names.append(ma.group("alias").strip())
        if len(subject) < 2:
            return None
        names.insert(0, subject)
        return {"subject": subject, "names": names, "site": site, "kind": kind}
    return None
_RE_PROSE = _re_mod.compile(r" (he|his|him|she|her|was|were|went|been|says|said) ")


class ResidentSight:
    # her own record (a show she was in is in it by name) and the lookup,
    # whose search answers when the record is silent
    # and what he is reading in a game, which is one more thing on the
    # screen in front of her (sim/eroge.py)
    WIRES = ('anime_kb', 'lore', 'lookup', 'eroge', 'typesafe',)

    def __init__(self, config, store, clock, notes, monitor, learned=None):
        self.config = config
        self.store = store
        self.clock = clock
        self.notes = notes
        self.monitor = monitor
        self.learned = learned        # App.assess_learned: a note reaches her picture of him
        # Asleep, and the latch that says something other than his touch woke
        # her, both come back from the save. `resident_asleep` used to be
        # written and never read, so a restart while she slept left the key
        # standing with nothing in the process behind it -- the messenger read
        # her asleep off it while she was up -- and a restart after his message
        # woke her put her straight back under on the next poll, because the
        # idle stretch that had sent her to bed was still running.
        kept = self.store.get("resident_asleep", None) or None
        self._asleep = self._sleep_block(kept) if kept else None
        self._woken = bool(self.store.get("resident_woken", False))
        self._last_poll = 0.0
        # where the search for a note he has touched starts. Kept, so notes he
        # wrote in while the bot was down are still new to her; a first run has
        # no cursor and starts from now rather than reading the whole vault.
        self._since = float(self.store.get("resident_notes_since", 0) or 0) or time.time()
        self._fresh = None
        # What he is doing, read off the raw window trail by System One
        # (`typesafe.py`, `docs/system-one.md` item 4). `typesafe` is wired by
        # her program; `_activity` is the last answer, kept for a poll so one
        # moment is classified once.
        self.typesafe = None
        self._activity = None
        self._glance_on, self._glance_dwell, self._glance_at = None, 0.0, time.time()
        self._unplan_sleep()
        wiring.declare(self)

    @property
    def c(self):
        return self.config.resident_sight

    def _sleep_block(self, kept):
        """The coasting block for a night already under way, from the save."""
        hm = str((kept or {}).get("hm") or "")
        if not hm:
            return None
        return {"start": hm, "end": str(self.c.night_end),
                "activity": "asleep", "location": "room", "with": "alone",
                "phone_access": "none", "resident": True}

    def _set_woken(self, v):
        self._woken = bool(v)
        self.store.set("resident_woken", bool(v))

    def enabled(self):
        return bool(getattr(self.c, "enabled", False)) and self.monitor is not None

    # ---- sleep -----------------------------------------------------------
    def asleep_block(self):
        """The block the loop coasts on while she sleeps, or None. Shaped like
        a plan block because everything downstream reads one; `end` is the
        night window's end, a nominal for the one sleep scene, since the real
        end is whenever he gets up."""
        if not self.enabled():
            return None
        idle = float(self.monitor.seconds_since_input() or 0.0)
        limit = float(self.c.sleep_after_idle_minutes) * 60.0
        now = self.clock.now()
        if self._woken:
            if idle < limit:
                self._set_woken(False)   # he has touched the machine since; the latch has done its job
            else:
                return None
        if self._asleep is not None:
            if idle >= limit and in_window(now, self.c.night_start, self.c.night_end):
                return self._asleep
            # either he touched the machine, or the morning is over and he is
            # still not here: out, not asleep. Nothing else wakes her.
            why = ("he touched the machine" if idle < limit
                   else f"it is past {self.c.night_end} and he has not come back: he is out, not asleep")
            logger.log(f"[resident] awake: {why}")
            self._asleep = None
            self.store.set("resident_asleep", None)
            return None
        fell = now - datetime.timedelta(seconds=idle)
        # Sleep can only BEGIN with an idle stretch that started in the hours
        # people go to bed. A machine that goes quiet at 08:00 is him leaving
        # for work, and until this rule she would have slept the whole day on
        # it. Nothing here reads the chat: a goodnight he never typed is not
        # what decides it.
        if (idle >= limit and in_window(now, self.c.night_start, self.c.night_end)
                and in_window(fell, self.c.night_start, self.c.sleep_latest_start)):
            self._asleep = {"start": fell.strftime("%H:%M"), "end": str(self.c.night_end),
                            "activity": "asleep", "location": "room", "with": "alone",
                            "phone_access": "none", "resident": True}
            self.store.set("resident_asleep", {"since": fell.timestamp(), "hm": self._asleep["start"]})
            logger.log(f"[resident] asleep since {self._asleep['start']}: his machine has been idle {int(idle // 60)} min")
        return self._asleep

    def wake(self, why):
        """Something other than his touch woke her -- his message, from his
        phone, with the machine still idle. He is awake, so she is; and she
        stays up until the machine is touched again resets the idle clock,
        otherwise the same idle stretch would put her straight back under."""
        if not self.enabled():
            return False
        self._set_woken(True)
        if self._asleep is None:
            return False
        logger.log(f"[resident] awake: {why}")
        self._asleep = None
        self.store.set("resident_asleep", None)
        return True

    def asleep(self):
        return self._asleep is not None

    def away_seconds(self):
        """How long he has not touched the machine. She is inside it, so this
        is an observation of hers and not a statistic: the one thing the gate
        on reaching out first needs from her sight (sim/initiative.py)."""
        if not self.enabled():
            return 0.0
        try:
            return float(self.monitor.seconds_since_input() or 0.0)
        except Exception:
            return 0.0

    def _unplan_sleep(self):
        """A plan written before this rule may still carry a sleep block, and
        the director would read her asleep off it while he is up. Once, at
        boot: every such block becomes an awake one and the phone rule is
        `free` throughout, which is what her planner writes from now on."""
        if not self.enabled():
            return
        try:
            d = self.clock.date_str()
            s = self.store.get_schedule(d)
            if not s:
                return
            blocks = list(s.get("blocks") or [])
            changed = 0
            for b in blocks:
                if b.get("phone_access") == "none":
                    b["phone_access"] = "free"
                    b["activity"] = "up because he is, at the laptop"
                    changed += 1
            if changed:
                self.store.save_schedule(d, s.get("ts") or self.clock.now_ts(), blocks,
                                         (s.get("notes") or "") + " (sleep block dropped: she sleeps when he does)")
                logger.log(f"[resident] {changed} sleep block(s) taken out of today's plan: her sleep is his")
        except Exception as e:
            logger.log(f"[resident] could not check today's plan: {type(e).__name__}")

    # ---- his notes -------------------------------------------------------
    def poll(self, scene=None):
        if not self.enabled() or not self.config.notes.enabled or self._asleep is not None:
            return
        now = time.time()
        if now - self._last_poll < float(self.c.poll_seconds):
            return
        self._last_poll = now
        try:
            self.glance(scene)
        except Exception as e:
            logger.log(f"[glance] failed: {type(e).__name__}: {e}")
        sv = self.config.sensor_view
        if not sv.vault_path:
            return
        cands = {}
        try:
            proc, title, in_window_s, _idle = self.monitor.right_now()
            if proc and in_window_s >= float(self.c.note_open_seconds):
                p = vault_monitor.match_title_to_vault_file(sv, _clean_window_title(title, proc))
                if p:
                    cands[p] = ("it is open in front of him", "彼の目の前で開いている")
            for p, _m, _b in vault_monitor.get_modified_file_info_since(sv, self._since):
                cands[p] = ("he has just written in it", "彼がいま書き込んだ")
        except Exception as e:
            logger.log(f"[resident] could not see his notes: {type(e).__name__}")
            return
        self._since = now - 1.0
        self.store.set("resident_notes_since", self._since)
        for path, why in cands.items():
            self._maybe_read(path, why, scene)

    def _maybe_read(self, path, why, scene):
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            return
        seen = self.store.get("resident_notes_seen", {}) or {}
        rec = seen.get(path) or {}
        if rec:
            newer = mtime > float(rec.get("mtime", 0)) + 1.0
            rested = (time.time() - float(rec.get("read_ts", 0))) >= float(self.c.reread_after_seconds)
            if not (newer and rested):
                return
        content = self._content(path)
        if len(content.strip()) < int(self.c.min_note_chars):
            return
        f = {"path": path, "basename": os.path.basename(path), "mtime": mtime, "content": content}
        r = self.notes.read(f, why, scene, reason_label="HOW IT CAME TO BE IN FRONT OF HER")
        seen[path] = {"mtime": mtime, "read_ts": time.time()}
        self.store.set("resident_notes_seen", seen)
        if not r:
            return
        r["why"] = why[0]
        self._fresh = (time.time(), r)
        if self.learned:
            try:
                self.learned(f"his note '{r['basename']}' ({why[0]}): {r['takeaway']}", source="seen")
            except Exception as e:
                logger.log(f"[resident] note not assessed: {type(e).__name__}")

    def _content(self, path):
        cap = int(self.c.note_max_chars)
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            return ""
        if len(text) <= cap:
            return text
        head = cap // 3
        return text[:head] + "\n\n[...]\n\n" + text[-(cap - head):]

    def fresh_note(self):
        """The note read in the last `fresh_minutes`, once, for the reply that
        follows it -- the shape `Notes.read` returns, so the persona's
        just-read line takes it as it takes a note she opened herself."""
        if not self._fresh:
            return None
        ts, r = self._fresh
        self._fresh = None
        if time.time() - ts > float(self.c.fresh_minutes) * 60:
            return None
        return r

    # ---------------- one thing off his screen, for her to remark on ----------------

    def noticed_line(self, digest, t):
        """One concrete thing off his screen, for her to actually remark on.

        Picked by code rather than by a model, and picked for being nameable:
        a search he typed, a page title, a file he had open. Those are the
        things a person watching over a shoulder says something about, and
        they are already in the window trail the digest carries. Anything
        vaguer than that is scenery and belongs in the digest line, not here.

        Never the same thing twice: what she has already been offered is kept
        per day in kv `noticed_said`, so this cannot become a tic.

        Noticing is the point; interrogating him is not. The line used to say
        she wanted to say something about what was on his screen, and against
        that her style notes lost: on 2026-09-02 every reply this line reached
        ended on a question at him about the machine -- what the file was, what
        he was making, what the search was -- and every reply it did not reach
        ended on something of her own. So it names the thing and says plainly
        what shape a remark about it takes."""
        if not digest:
            return ""
        import re as _re
        gap = float(getattr(self.config.situation_block, "noticed_min_gap_minutes", 0) or 0)
        if gap and (self.clock.now_ts() - float(self.store.get("noticed_last_ts", 0) or 0)) < gap * 60:
            return ""
        said = set(self.store.get("noticed_said", []) or [])
        cands = []
        for m in _re.finditer(r'(?:searched|Google [Ss]earch for|typed)\s+"([^"]{3,70})"', digest):
            cands.append((t("he searched", "彼が検索した"), m.group(1)))
        # The gap between the program's name and the colon is bounded, because
        # the digest is free prose and `[^:]*` walked through a whole sentence
        # of it to the colon inside a clock time: "he had open '17 to 15:19 he
        # was deep in another terminal run, this...'" reached her prompt.
        for m in _re.finditer(r"(?:notepad\+\+|Obsidian|Notepad)[^:\n]{0,16}:\s*([^\n(]{3,70})", digest):
            cands.append((t("he had open", "彼が開いていた"), m.group(1)))
        # The digest is prose and mostly writes a file as "opened
        # yukarin-voice-models.md in Notepad++", which the colon pattern above
        # cannot see at all. A filename is the most nameable thing on his
        # screen, so it is looked for on its own; a path in front of it is not
        # part of the name and the character class leaves it behind.
        # No space in the name, even though some of his files have one: letting
        # the match run across a space lets it run across the whole sentence in
        # front of the file too, and "he had open 'came back to
        # yukarin-voice-models.md'" is worse than losing a word of a title.
        for m in _re.finditer(r"\b(\w[\w.\-]{1,58}\.(?:md|txt|py|json|csv|log|pdf|docx?|xlsx?))\b", digest):
            cands.append((t("he had open", "彼が開いていた"), m.group(1)))
        for m in _re.finditer(r"chrome:\s*([^\n(]{6,70})", digest):
            cands.append((t("he was reading", "彼が読んでいた"), m.group(1)))
        for kind, what in cands:
            key = self.noticed_title(what)
            if key and key not in said:
                self.store.set("noticed_said", (list(said) + [key])[-40:])
                self.store.set("noticed_last_ts", self.clock.now_ts())
                return t(f"over his shoulder just now: {kind} '{key}'. it is simply there, like anything else on his screen; "
                         f"nothing to ask him about it, nothing you owe a remark. if it comes up in what you say, it comes up.",
                         f"いま肩越しに見えたもの: {kind}『{key}』。彼の画面にあるほかの何とも同じで、ただそこにある。"
                         f"それについて彼に訊くことはないし、一言いう義務もない。言うことの中に出てくるなら出てくる。"
                         f"あなたは肩越しに覗いているのであって、説明させているのではない。")
        return ""

    # ---- what he is doing, from the raw trail -----------------------------
    # His machine writes what is in front of him (`machine/collector.py`): the
    # live window in `telemetry_now.json` and the closed sessions beside it.
    # That trail is the input here, and it is a better one than the digest's
    # prose, which `noticed_line` below has to scrape for what he had open
    # precisely because nothing answers the question the trail answers
    # directly.
    _ACTIVITIES = (
        ("working", "a terminal, an editor, code, files, office or file work"),
        ("reading", "an article, a wiki, documentation, a page about a thing"),
        ("watching", "video, a stream, a film or an episode"),
        ("anime", "animation, an anime or manga page or episode"),
        ("gaming", "a game running"),
        ("social", "a feed, a forum, chat or messages"),
        ("shopping", "a shop, an order, a listing"),
        ("idle", "nothing on the screen is being used"),
        ("other", "none of these"),
    )
    _ACTIVITY_LINE = {
        "working": ("he is working at his machine just now",
                    "彼はいまパソコンで作業している"),
        "reading": ("he is reading something on his screen just now",
                    "彼はいま何かのページを読んでいる"),
        "watching": ("he is watching video just now", "彼はいま動画を見ている"),
        "anime": ("he is watching anime just now", "彼はいまアニメを見ている"),
        "gaming": ("he is playing a game just now", "彼はいまゲームをしている"),
        "social": ("he is on a feed or a chat just now", "彼はいまSNSかチャットを見ている"),
        "shopping": ("he is shopping online just now", "彼はいま買い物をしている"),
    }

    def _trail(self, now):
        """The last half hour of windows, oldest first."""
        rows = []
        try:
            proc, title, _in_window, _idle = self.monitor.right_now()
            if proc:
                rows.append("%s: %s" % (proc, title))
        except Exception:
            pass
        try:
            sessions, _li = self.monitor.attention_since(now - 1800)
            for s in list(sessions)[-12:]:
                if len(s) >= 4 and s[2]:
                    rows.append("%s: %s" % (s[2], s[3]))
        except Exception:
            pass
        return rows

    def activity(self):
        """What he is doing, classified once per poll from the raw trail.

        None when the use is off, the trail is empty, or the classifier could
        not answer -- in which case the last answer stands rather than the
        label being invented."""
        if self.typesafe is None or not self.typesafe.ready("sight_activity"):
            return None
        now = time.time()
        kept = self._activity or {}
        if kept and now - float(kept.get("at") or 0) < float(self.c.poll_seconds):
            return kept
        trail = self._trail(now)
        if not trail:
            return kept or None
        questions = {"activity": {
            "type": "choice",
            "instructions": "What is the person at this machine doing right now?",
            "criteria": {name: what for name, what in self._ACTIVITIES},
        }}
        answers = self.typesafe.ask("sight_activity", {"windows": trail}, questions)
        if answers is None:
            return kept or None
        choice, conf = self.typesafe.choice(answers, "activity")
        if not choice:
            return kept or None
        floor = float((self.typesafe.use("sight_activity") or {}).get("threshold", 0.5))
        self._activity = {"label": choice, "confidence": conf, "at": now,
                          "sure": conf >= floor}
        logger.log(f"[sight] what he is doing: {choice} (conf {conf:.2f})")
        return self._activity

    def activity_line(self, t):
        """One factual line for her situation: what he is doing now, or "".

        An unsure answer says nothing rather than guessing at him, and an idle
        or unclassified moment is not worth a line. She is watching his screen,
        not reading his mind."""
        a = self.activity()
        if not a or not a.get("sure"):
            return ""
        pair = self._ACTIVITY_LINE.get(a.get("label"))
        if not pair:
            return ""
        return t(pair[0] + ". it is simply what is in front of him; nothing you owe a remark.",
                 pair[1] + "。彼の目の前にあるというだけのこと。一言いう義務はない。")

    # ---- a glance at what he is reading -----------------------------------------
    # She is on his machine, so a page he has open is in front of her the
    # moment it is open -- not twenty minutes later, when the collector
    # flushes the feed and the digest gets round to it. This reads the
    # foreground window every poll, and when the page is about a WORK (a
    # show, a manga) that he has stayed on, it asks two things: does her own
    # record say she was in it, and if the record is silent, a search with her
    # name beside the title. What comes back is one line in her situation,
    # pinned and marked as hers to act on when it is her show, background
    # otherwise; a reason to reach out first when it is hers; and a thing she
    # knows from then on. He looks up an anime she was in, and within a minute
    # or two she says so, with the part named -- checked, not guessed.

    def glance(self, scene=None):
        """Every poll: what is in front of him, and whether it is a work."""
        c = self.c
        if not getattr(c, "glance_enabled", False):
            return
        try:
            proc, title, in_window_s, _idle = self.monitor.right_now()
        except Exception as e:
            logger.log(f"[glance] could not see his window: {type(e).__name__}")
            return
        page = page_of(title, proc) if proc else None
        now = time.time()
        if not page:
            self._glance_on, self._glance_dwell = None, 0.0
            return
        if self._glance_on == page["subject"]:
            self._glance_dwell += max(0.0, now - self._glance_at)
        else:
            self._glance_on, self._glance_dwell = page["subject"], min(float(in_window_s), float(c.glance_dwell_seconds))
        self._glance_at = now
        if self._glance_dwell < float(c.glance_dwell_seconds):
            return
        seen = self.store.get("glance_seen", {}) or {}
        last = float(seen.get(page["subject"], 0) or 0)
        if now - last < float(c.glance_again_hours) * 3600:
            return
        seen[page["subject"]] = now
        self.store.set("glance_seen", dict(list(seen.items())[-80:]))
        self._resolve_glance(page)

    def _resolve_glance(self, page):
        """What the page is, from the one resolution every path uses
        (`sim/works.py`): her own record and the roles the list gives her
        first, locally; what she already knows instead of a second fetch; a
        search only for a work nothing here has heard of. Writes
        `glance_last`, an event, and the one record.

        This used to be four steps of its own, and each of them had a hole:
        the record was asked for a kind of record that does not exist, the
        roles were asked under her chat name and only for a page the brackets
        proved was a work, and a page the shape could not classify returned
        here without anything being asked at all."""
        subject, names, site, kind = page["subject"], page["names"], page["site"], page["kind"]
        lk = self.lookup
        got = works.identify(
            names, config=self.config, store=self.store, clock=self.clock,
            known=(lk.known if lk is not None else None), anime_kb=self.anime_kb, lore=self.lore,
            search=(lk.search if lk is not None else None), site=site, shape=kind,
            why=f"the page for {subject} is on his screen ({site}); is it a work she was in",
            in_front=True)
        if not got or (got["kind"] != "work" and not got["hers"]):
            # a person's page, a character of somebody else's, an article about
            # a building: nothing to say anything about on its own, and the
            # digest will carry it as scenery
            return
        names = list(got["names"])
        hers, part, gist, source = got["hers"], got["part"], got["gist"], got["source"]
        # the work's own Japanese name, so she names it as she would and not as
        # a romaji page does (緑 for 美鳥). Her own record carries it in its
        # tags, which is local and free; the list's own title is one cheap
        # cached request and only asked when the record had nothing.
        ja = next((n for n in names if _RE_JA.search(n)), "")
        if not ja and hers and got.get("aid") and self.anime_kb is not None:
            try:
                ja = self.anime_kb.japanese_title(got["aid"]) or ""
            except Exception as e:
                logger.log(f"[glance] the list's Japanese title not read: {type(e).__name__}")
                ja = ""
            if ja and ja not in names:
                names.append(ja)
        if ja and works.norm(ja) != works.norm(subject):
            subject = f"{ja}（{subject}）"
        item = {"subject": subject, "names": names, "site": site, "kind": got["kind"], "ts": self.clock.now_ts(),
                "wall": time.time(), "hers": hers, "part": part, "gist": gist, "source": source,
                # the three-state answer, so the line below can say "this one
                # is not yours" as plainly as it says "this one is". The
                # resolution wrote it on the one record for this work
                # (`sim/works.py`), so her sight and her recall of the same
                # title cannot answer differently on one tick.
                "role": got.get("role") or None,
                "known_key": got.get("key") or "", "said": False}
        self.store.set("glance_last", item)
        if hers:
            self.store.add_event(self.clock.now_ts(), self.clock.date_str(), "glance",
                                 f"he has the page for {subject} open on his machine ({site}) -- a work she was in"
                                 + (f", as {part}" if part else ""), 3)
            logger.log(f"[glance] {subject} ({site}): hers" + (f", as {part}" if part else "") + f" [{source}]")
        else:
            self.store.add_event(self.clock.now_ts(), self.clock.date_str(), "glance",
                                 f"he was reading about {subject} ({site})", 1)
            logger.log(f"[glance] {subject} ({site}): not hers" + (f" -- {gist[:80]}" if gist else " (nothing found)"))

    def current_glance(self):
        """The page he was on, while it is still the thing in the room."""
        it = self.store.get("glance_last", None)
        if not it:
            return None
        if time.time() - float(it.get("wall", 0) or 0) > float(self.c.glance_fresh_minutes) * 60:
            return None
        return it

    def glance_lines(self, t):
        """(text, kind, pin) for her situation: her show is hers to act on,
        anything else is background, and a game he is reading is both -- what
        is on the screen and what is happening in it."""
        out = []
        if self.eroge is not None:
            try:
                out += self.eroge.glance_lines(t)
            except Exception as e:
                logger.log(f"[eroge] the situation line failed: {type(e).__name__}")
        # what he is doing, classified off the raw trail (`typesafe.py`): a fact
        # about his screen, so it rides with the background and never as an
        # action of hers
        aline = self.activity_line(t)
        if aline:
            out.append((aline, "fact", False))
        it = self.current_glance()
        if not it:
            return out
        subject, site = it["subject"], it["site"]
        if it.get("hers"):
            part = it.get("part") or ""
            line = t(f"in front of him right now: the page for {subject} ({site}) -- a work you were in"
                     + (f", as {part}" if part else "") + ". "
                     + (f"what you know of it: {it['gist']} " if it.get("gist") else "")
                     + "this one is yours: say something about it if you like, in your own words -- you know it from the inside "
                       "and he only has the page. never recite the page back; never pretend to know what it does not say.",
                     f"いま彼の目の前にあるもの: 『{subject}』のページ（{site}）-- あなたが出ていた作品"
                     + (f"。役は{part}" if part else "") + "。"
                     + (f"分かっていること: {it['gist']} " if it.get("gist") else "")
                     + "これはあなたのもの。言いたければ自分の言葉で言う。あなたは中から知っていて、彼はページしか持っていない。"
                       "ページの内容を読み上げない。ページにないことを知っているふりをしない。")
            return out + [(line, "action", True)]
        line = t(f"he is reading about {subject} ({site}) just now"
                 + (f" -- what you know of it: {it['gist']}" if it.get("gist") else "")
                 + ". background: it is simply there on his screen; nothing you owe a remark.",
                 f"彼はいま『{subject}』のことを読んでいる（{site}）"
                 + (f" -- 分かっていること: {it['gist']}" if it.get("gist") else "")
                 + "。背景。彼の画面にただあるだけで、一言いう義務はない。")
        # and when it is a work the mirror can say is NOT hers, it says so.
        # This branch used to end at "he was reading about something", which
        # is exactly as much as it said about a work she was about to claim a
        # part in.
        denial = works.verdict_line(self.config, it.get("role"), subject, t)
        if denial:
            line += " " + denial
        return out + [(line, "fact", False)]

    def impulse_bonus(self):
        """Her show open in front of him is a reason to say something first;
        once she has, it is not a reason again. Everything the impulse already
        refuses on still applies."""
        c = self.c
        it = self.current_glance()
        if not it or not it.get("hers") or it.get("said"):
            return 0.0
        if time.time() - float(it.get("wall", 0) or 0) < float(c.glance_settle_seconds):
            return 0.0
        return float(c.glance_impulse_bonus)

    def attention_observation(self):
        """He is at the machine, and she is not what is in front of him.

        A resident sees this directly: the idle seconds say he is here, the
        activity classifier and the glance say what he is on, and neither is
        her. It is one observation with the label it was read from, not a rate
        (`sim/impulse.py:186-198` argues that case), returned for the impulse to
        weigh. None when she cannot see him at all -- a character with no sight
        has no such observation and is not told one.
        """
        if not self.enabled():
            return None
        try:
            away = float(self.monitor.seconds_since_input() or 0.0)
        except Exception:
            return None
        if away > float(getattr(self.c, "here_seconds", 120) or 0):
            return {"here": False, "attending": False, "activity": None,
                    "reason": f"he has been away from the machine {away / 60.0:.0f} min"}
        a = self.activity() or {}
        label = a.get("label") if a.get("sure") else None
        it = self.current_glance()
        attending = bool(it and it.get("hers"))
        reason = ("he is at the machine"
                  + (f", {label}" if label else "")
                  + (", with a page of hers open" if attending else ", on his own thing"))
        return {"here": True, "attending": attending, "activity": label, "reason": reason}

    def note_spoken(self):
        """She reached out while a page of hers was the thing in the room;
        whatever she said, it does not get to be the reason twice."""
        it = self.store.get("glance_last", None)
        if it and not it.get("said"):
            it["said"] = True
            self.store.set("glance_last", it)

    @staticmethod
    def noticed_title(what):
        """A window title, or nothing.

        What the patterns above scrape is free prose written by a model, so a
        capture is only worth showing her if it still looks like the name of a
        thing. A sentence about him, a clock time, and the bare name of the
        program the pattern matched on are all captures that have reached her
        prompt, and none of them is something to remark on."""
        t = str(what or "").strip().strip('"“”').strip(" .,;:…-")
        if len(t) < 3:
            return ""
        low = t.lower()
        if low in ("new tab", "untitled", "chrome", "notepad", "notepad++", "obsidian",
                   "explorer", "administrator", "blank page"):
            return ""
        # a clock time or a pronoun means the pattern ran off the title and
        # into the digest's own narration of his afternoon
        if _RE_TIME.search(t) or _RE_PROSE.search(" " + low + " "):
            return ""
        return t[:70]
