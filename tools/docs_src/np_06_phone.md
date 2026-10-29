
---

## 11. Her phone (the digest, the lookups and the anime knowledge in `sim/`; the snoop and the X account are the first character's, `tomoe/`)

She learns about him only when she looks. Nothing here is a live feed
into her; every route into her picture of him passes `App.assess_learned`
(the ick).

### 11.0 `him_profile.py` `HimProfile`: what she has come to know about him

The digest is a transcript of one look and `user_facts` are one-liners;
nothing read the digests back over time, so she knew what he did at 10:04
and not what he is like. Once a day (`him_profile.every_hours`), from the
last `him_profile.digests` digests plus the facts and `Rhythm`'s hours,
the `him_profile` role writes her picture of him -- his hours, what he is
into this month, his tells, what the digests cannot settle -- into kv
`him_profile`. `prompt_text()` rides in her own reply beside her beliefs
about him; `digest_line()` goes into the next digest call, so a look can
say *as usual* or *not like him* instead of narrating every session as
news. history: §11.1.

### 11.1 `phone.py` `Phone`: the app that digests his PC

**Not built at all for a character whose sheet answers `sees_him: none`.**
`scail.App` leaves `self.phone` None for her and `App.latest_digest()` is the
one reader every call site goes through, so she has no app to open, no count
of how long he has been quiet and no row in her save saying she looked -- the
same rule that gives a character with no world a calendar that loads no data.
The role that writes a digest being off is not enough: with only that, the
open kept firing, wrote kv `phone_use` and `phone_last_look_ts` every time and
logged a line about his silence to a character who has never spoken to him.

The sensors write a raw feed, and **one process on the machine writes it**:
`machine/collector.py` (the machine's, started by the hub's launcher
`talkapp.cmd` when that is run, stopped with the hub by `restart.cmd`) runs the
system monitor and the telemetry collector
and also writes `sensors.telemetry_now_path` -- what is in front of him and
when he last touched anything -- plus the closed window sessions of the last
day beside it; a bot reads those through `machine/monitor_client.py`
`RemoteMonitor`, which answers `right_now`, `seconds_since_input` and
`attention_since` in the in-process shapes. `sensors.collector_in_process`
puts the whole stack back inside one bot, for a machine that has only one.
Two bots each running the stack copied his browser history twice a minute
into one temp file and wrote one feed with two id counters.

**The collector writes what it is holding the moment a reply is about to be
built.** `App.request_flush` touches `sensors.telemetry_flush_request_path`
immediately before the tick that answers his message and immediately before
the tick she may write first out of, then waits up to
`sensors.telemetry_flush_wait_seconds` for the feed's newest id to move.
`TelemetryCollector.check_flush_request` runs on every pass of the machine's
own loop (`sensors.telemetry_now_interval_seconds`, three seconds), re-reads
the sources, writes an entry with `flush_reason` `requested` and removes the
file; an empty buffer writes no entry and the file goes anyway. Both
characters ask, because the collector and the feed are the machine's, and
neither look is forced: the resident digests the new entry at once, the other
when she next opens the app. With no collector running the file stays, the
wait runs out, and one log line an hour says so rather than one per reply.

`should_look` is a felt decision after `phone.digest_min_minutes`
-- curiosity, boredom, loneliness and, strongest, his silence -- never a
timer; `look()` (role `phone`, `prompts/phone.txt`) consumes the pending
entries (`phone_last_consumed_id`, `max_entries_per_look`,
`max_raw_chars`) into a digest written from her side (table `digests`;
`digest_min_minutes`). **A look reads the NEWEST `max_entries_per_look`
entries** and drops what is older, logged: the app shows what he has been
doing lately, and oldest-first left her a permanent hour behind. The look's
relief on `curiosity` goes through `State._settle`, never through the
baseline. `live_line` (what his PC shows this moment, only
from the live monitor, `live_line_max_age_minutes`; every line of it and the
head of `window_trail` are written in the language she is addressed in, which
they were not -- the second character read `いまこの瞬間: his PC right now:`),
`day_shape_line`
(his first activity and longest quiet stretch, kv `his_first_active`),
`user_idle` (from real input, never from what is running),
`catalogue_text` (titles only). `his_side_now` is the same reading for a
MECHANISM role rather than for her -- `("at it", minutes in the window)`,
`("away", minutes since he touched anything)` or `(None, None)` with no
monitor to ask: `idle_minutes` answers None both for "he is at it" and for
"nobody measured", and `live_line` is written in her language and in her
program's words, so neither can be read by a role that is deciding rather
than speaking (§8.10).

**A look counts as something happening only when it shows something new of
his.** `Phone._fingerprint` reduces the entries a look consumed to the set of
what they SHOW -- the processes that were in front (an idle process dropped),
whether an image viewer was open, the files he opened, the hosts in either
browser's history, the notes on screen, whether anything played -- and
compares it with the same set from the last look (kv
`phone_last_fingerprint`, the newest 200 members kept). `Phone.last_look_novel`
is what remains, and `App.tick` reads it: a digest with nothing new in it does
not make the tick significant and buys no gauge read, with
`[state] the digest shows the same things as the last one; no gauge read on
it` in the log. The prose of a digest is different every time it is written,
so before this every one of her 58 looks over 48 hours was followed by a gauge
read tripped by her own sensor coming back rather than by anything of his
changing. If the fingerprint cannot be built the look counts as new, which is
the safe direction.

**And a look with nothing new in it makes no call** (`phone.skip_unchanged`).
The fingerprint was computed and the log line written all along, and then a
full account was paid for anyway; for a character who is inside the machine and
therefore looks on every tick that was 97 accounts in three days against the
first character's 27, and on the last three days of real looks 16% of hers and
22% of his held nothing the look before had not. The standing account is LEFT
ALONE, never blanked, because her prompt reads it and clearing it would take
her picture of his machine away in exactly the case where nothing has happened
to replace it; the entries are consumed so the stretch is not offered again,
and the live status line is refreshed, that being the half that is this minute
rather than this stretch. `[phone] account not rewritten: nothing in this look
that the last one did not show` is the line. A forced look is never skipped.

**How hard he was working is a band, not a count** (`sensors/bands.py`,
thresholds `sensors.bands.*`). One function made every figure a character ever
recited about his machine and it rounded none of them: the keypress total with
its per-category breakdown, the count and seconds of each typing burst, the CPU
and RAM percentages, the busiest processes' shares and the uptime in hours and
minutes. Over three days the second character's accounts carried a mean of 38
numerals and 9.2 clock times each, and what came back out of her was the
uptime in hours and the number of keys he pressed at four in the morning. Now
the typing is banded on keys per MINUTE -- a total says nothing without the
span it happened in -- the bursts are a count of long and short runs, the
uptime is "not restarted in over a week", the percentages are gone entirely
and the busiest processes keep their names and lose their shares. **What is
not banded is when a window ran and for how long**: she is watching him
continuously and what time he got up is hers to know (his call). The band
wording lives once, in both languages, and the caller passes the `t(en, ja)`
of whoever is being written for, so the resident on her own arm reads hers;
the mind's language module is not imported into `sensors/`, which the
collector loads, so the closure comes down from `sim/phone.py` instead.

**One running account of the last `phone.rolling_hours`, not a digest per
batch.** The writer is handed the account it wrote last time (kv
`phone_account`, replaced on every look, dropped whole once it is older than
its own window; `Phone.account()` reads it) plus the raw material that has come
in since, and returns the account again: the last hour in full specifics, an
older stretch compressed to a line, anything past the window dropped, and the
eight to fourteen sentences are the size of the whole account rather than of
the new part. The row in table `digests` is still written, as the day's log the
diary, the compile, `reflect`, `wonder` and `HimProfile` read. A batch per
flush left her prompt showing the last batch dated "N minutes ago", so there
was a seam at every look and whatever fell between two of them was told twice
or not at all.

**A digest older than `phone.stale_minutes` is history, and says so.**
`latest_digest` leads with the absence when he has not touched the machine --
*"he has not touched his machine for 9h; nothing has happened on it since.
what it showed when he last was, at that time: ..."* -- instead of
handing her the content with the idle line appended behind it. She once read
a four-hour-old digest as the present tense and texted him as though he were
sitting there, while `phone_last_live` in the same save said his PC had been
idle for eight hours. She can still see what he was doing; she cannot
mistake it for what he is doing. `App.feed_backlog` counts what has piled
up.

**His absence is only ever said on a MEASURED idle figure, and how long since
she looked is said as that and nothing more.** `look` stores the minutes since
his last input as a number beside the status line (`phone_last_live.idle_min`,
from `Phone.idle_minutes`); rows written before that carry it in their own
prose and are still read. With no figure at all, a digest older than
`phone.stale_minutes` is handed over as history with the hour on it -- *"what
the app showed you when you last opened it, around 11:07 his time (nothing
newer has come in since): ..."*, the wording each program's
(`digest_as_history`) -- and nothing is claimed about him. The row's own age
used to stand in for a missing figure, which turns how long since she looked
into how long since he touched anything: an eleven-hour-old look was read to
her as "he has not touched his machine for 10h07" while he was at the machine
throughout.

**For a resident, `latest_digest` also fills the gap the collector leaves,
and it runs whether or not she has just looked.** A digest summarises the
entries `machine/collector.py` has flushed, and it flushes on a character
count, on a five-minute heartbeat, or the moment a bot asks, so one built this
second is at worst a few seconds behind him. On top of the digest it puts how old that is, then
`window_trail` from the account's own `to_ts` -- every foreground window since,
sessions under twenty seconds dropped and returns merged, at most eight -- then
`live_line`. **A picture is exempt from that floor, and it is named rather than
listed.** An image viewer puts the bare filename in its title and his picture
files are named by their own content hash, so `_viewer_md5` reads the hash off
the title and `_picture_words` looks it up in the classifier's own cache
(`sensors/gelbooru_classifier.py` `cached_classifications`: read-only, re-read
when the file changes, never written from here, no network and no model call).
The item becomes `JPEGView: general, Oyama Mahiro of Onii-chan wa Oshimai
(30s)`, and a run of consecutive pictures collapses into one item with the
count, the span, the spread of the board's own ratings and the series --
`JPEGView: 24 pictures over 3 min -- explicit x12, questionable x7; Saru Getchu
x22`. The rating goes through as the site wrote it, explicit included (his
call); the tag names never do. Both wordings are the program's
(`resident/words.py`, `tomoe/words.py`). Before this, twenty-four classified
pictures reached her as two hashed filenames: a rating lives only in the feed's
classified rows, only a digest renders those, and the twenty-second floor had
dropped every one-second picture besides. `App.tick` used to take the text a fresh look returned instead of
calling this, so a look left her LESS current than no look: she answered a
message about a video he had open holding a digest that ended three minutes
before he opened it, and named it four minutes later on a tick where she had
not looked.

**And the trail leaves a record, so the digest is not told to break her own
afternoon to her.** The same windows reach her twice otherwise -- live in the
trail, then again in the digest that reads the same stretch off the feed once
the collector flushes. `latest_digest` writes what it handed her to kv
`phone_trail_shown`, `look` puts it in front of the digest role as something
she has already watched happen, and the record is cleared when the digest is
stored, so it always holds what she has seen since the last one. Nothing is
cut from the raw activity: the trail carries only foreground windows over
twenty seconds, so narrowing the span would lose the browser history and the
searches underneath it. What changes is what the digest may present as new,
and it may still name one of those windows where what came after it changes
what it meant. `/look`, `/digest`. history: archive §5.5, §5.67.

**A look is also the moment an episode he played reaches her.** It is the one
moment a character who learns about him in digests can be told anything, so
the runtime calls the program's `after_phone_look` hook whenever a look
actually happened, digest or not (`App.look_at_phone`, off
`Phone.last_look_ts`), and the first character's program hangs
`WatchingHim.note_seen()` on it: what he played while she was elsewhere has
already been noticed and read up on in the background, and this is where it
comes into her hands (§12.12). The digest prose itself is not told about the
episode -- the raw activity already carries his player's window, and handing
the digest role a synopsis it never fetched would put a second, unjudged
retelling of the episode beside the pinned one.

### 11.2 `snoop.py` `Snoop` and `notes.py` `Notes`: his vault and his torrents

`Snoop.eligible` is a felt probability from the uneasy gauges (signed from
their own rest), only alone and free with the phone, more when lying
awake; `run` (roles `vault` and `downloads`) reads a few of his notes
(`vault_snoop.*`, `sensors.vault_path`) and this week's torrents; kv `snoop_*`,
`vault_read_paths`. `Notes.read(query_or_file, reason)` (role `note_read`)
skims a named note when he mentions it, when she is curious, or when it is on
his screen in front of a resident; `notes_read`; `index_text` in her prompt.
`/snoop`, `/read`, `/notes`. history: archive §5.6, §5.9, §5.26.

**All three roles write the RECORD and none of them writes her.** What was in
front of her, in two to four sentences, third person, past tense, with the one
or two lines a reader would stop on quoted as they stand and a download named
as the name stands; nothing about how it landed. The one number they score is
IMPACT, 1 to 5: how much of a day this would take out of anyone who read it,
which is what every reader of the event's `salience` column already uses it
for. Whether she raises it is not scored anywhere -- the pick offers her
`text_him` on her own sheet at every moment she has the phone.

**What it did to her is the private thought's** (`sim/reflect.py`,
`Reflection.after_reading`), asked the moment the record exists: it has her
sheet, writes first person, moves her gauges, and lands as a `(private) ...`
row beside the record. The reason is the program's word
(`reflect_why_snoop`, `reflect_why_note`), and so is the sentence the record
is filed under (`note_event_line`, a pair, so a character who reads Japanese
reads it in her own language).

### 11.3 `lookup.py` `Lookup`: she quietly looks it up

The gate is per character (`lookup.gate`): `regex` is the English keyword
gate plus `_names_a_thing` (does a phrase match anything in his own anime
history, `AnimeKB.resolve_candidates` -- the ranking rather than one answer,
because this question is only whether he named a thing at all, and two entries
of one franchise are a tie the resolution settles later); `model` sends every inbound message to
the classifier, which is the only gate that can see a Japanese sentence and
is what the second character runs on. The classifier is told what is IN
PLAY -- the episode he has open (`Lookup.watching`), **what SHE last put in
front of him** and the shows recent
lookups landed on, in Japanese where the KB has it -- and a character named
in Japanese counts only with a show anchored; it returns `name` and `show`.
**What she last sent is part of what is in play** (`_last_of_hers`,
`lookup.anchor_turns`, 3 of her own turns): a post she shared with its author,
its text and what its picture is (kv `x_shared`, `docs/x-account.md` §2.2), a
thing she looked up since that turn, a title she named that resolves on his own
list (local only, no search). His "nani kore?" about a link she had sent one
turn earlier was answered "nothing in it worth looking up" because the call was
handed his three words and an unrelated show, while the post was in the save
the whole time.
Then on a thread (`lookup.wait_seconds`): **a character with a show goes to
the fan encyclopedia first** (`Recap.character_page`: `lookup.character_query`
against `lookup.character_hosts`, the pixiv dictionary; the article's URL
carries the full name; cached in `recaps` as kind "character"; condensed by
`character_digest` to `lookup.character_max_chars`, and that digest is the
gist), else the card from the KB or the MAL list or a search, a gist in her
words (`lookup_gist`); a fact with `lookup.fact_weight`; `take()` once for
the reply; `_shows_in_play` keeps a character name in the right show (kv
`recent_anime_ids`). `lookup.max_per_day` counts finds, not attempts.
**What she found stays with her two ways.** The last `lookup.situation_max`
lookups of the last `lookup.situation_hours` are pinned in her situation on
every message. And every found thing is kept in `sim/known.py` (kv
`known_things`, `lookup.known_keep`) with its names -- as typed, the page's
full name, the aliases the digest role lists -- and comes back into her
situation whenever a message of his carries one of them, at most
`lookup.known_max_lines` a message, no window. A watched show accumulates its
episodes' digests there too (`KnownThings.merge`, from `sim/watching_him.py`).
Substring match on names, longest first; the same trap as `sim/lore.py`.
**And she can look a thing up before she answers.** `Lookup.search` is
one web search and one `search_gist` call on the calling thread, kept by
name as a thing she knows and counted against `lookup.search_per_day`,
which is its own cap and not the finds cap above. Two callers ask for
one: `lookup.on_request` lets her write `[search: what she wants to
know]` on its own line in a draft, in which case the reply is written
again with the answer in front of her (on for both characters; each style
file has a section telling her the line exists, one per reply, and that a
thing not found is said as not found), and the resident's sight asks for
one about a page he has open. A question
about a work she already knows by name also reads that series' own
Japanese Wikipedia lead, because a results page for 「2期」 showed a manga
volume. Whether she was in the work is carried in two fields of the
answer and never in the gist's prose.
**One truth about who went looking.** Every record either path writes
carries `asked_by`: "her" when a draft of hers asked, "arrived" for the
automatic path off his message and for the sight's own search. Her
situation is worded from it, so the reply she writes cannot claim a search
that did not run -- the line for the automatic path says what sent her
looking, and the line for a thing she knows by name says she has known it
since before this conversation. Two things `search` refuses before it
spends anything. It refuses outright when her day gives her no way to look
(the scene's `phone_access` is `none`, passed in by the caller that holds
the scene, else read off the newest scene): the reply path guards its own
call, and the sight's did not. And a request for a thing the automatic
path fetched within `lookup.search_known_hours` is answered out of
`known_things` -- no web request, no gist call, no second record over the
first, and the answer is marked as something she knew rather than
something she just looked up, keeping its original `asked_by`.
The two paths divide by what they are for: the automatic one takes the
names and titles he mentions, and hers takes the questions she has about
them.
history: §11.3 2026-09-02 20:43. When he names a thing,
`_attach_kb` also pulls (via `sim/recap.py`, the Japanese knowledge base --
fetch once, cache in `recaps`, reuse) a fuller overview by kind: an anime
series (+ the named episode's beats, `Recap.episode_in`), a seiyuu's
Japanese Wikipedia bio, or a game / eroge's premise. Searched by the KANJI
title / name (`AnimeKB.japanese_title` / `person_name_jp`), Wikipedia
first. **Which work a title he typed means is the ranked resolution**
(`Lookup._which_work`, `docs/resolver.md`): his own list first, with an entry
that cannot have the episode he named dropped, and where more than one
survives the `which_one` role is asked -- on this thread, which is already
paying for two calls, and never on a reply path. Only when his list has
nothing of that name does it fall through to the MyAnimeList search, which
answers every query and so can never decide anything on its own. Her download snoop can emit `LOOKUP:` to investigate one of his
torrents the same way. kv `lookups`, `lookup_counts`, `lookup_kb_misses`.
`/lookups`, `/kb`. history: archive §5.28. **KB / recap spec: `docs/recap.md`.**

### 11.4 `anime_sense.py` `AnimeSense` and `anime_kb.py` `AnimeKB`

The MAL daemon (`tools/mal_history.py`, its own scheduled task `SCAIL_mal`
through `mal_daemon.cmd`, detached under `pythonw`, no console, logging to
`logs/mal_daemon.log`; a target of `restart.cmd`, §14) keeps his
per-episode watch history in its own db. **One watch of one episode is one
row, and the logged-in panel is the stamp of record.** The daemon has two
per-episode sources and they were three hours apart on every row they shared:
the panel behind the login renders on his account's clock, which is this
machine's, and the public history page is fetched without a login and renders
on MyAnimeList's own, three hours behind. His player settles which is true: for the
watch the panel stamps 21:05, his own player log has the file opening at
20:30 the same evening and the page said 6:05 PM. The same three hours put a relative label a day out: on
the page "Yesterday" means the SITE's yesterday, so between midnight here and
midnight there this machine's yesterday is a day later, and 34 watches carried
a second row a day after the first with the identical label (HISTORY.md, the
mirror's stamps). Every label is now
resolved against the site's own calendar and converted
(`_resolve_history_time`, `_site_to_local`, `MAL_SITE_TZ`), the moment the page
was read is on the row (a `scraped_at` column on the `episodes` table), and a
page row is not written where the panel has one while a panel row takes any page row for that episode
out with it (`_upsert_episodes`). The 152 rows already written are corrected by
`python tools/mal_history.py migrate-stamps --apply`, with the daemon stopped;
it prints every row it changes and may be run twice.
`python tools/mal_history_test.py`, in smoke. `AnimeSense.shelf` (active,
cold, recently finished, his pace), `situation_line` (what he is in the
middle of), `anime_in_the_air` (only when anime is what they are talking
about), the weekly `shelf_check` (kv `anime_shelf_checks`; the pending
hint rides BOTH paths -- a scene share_hint via `App.maybe_shelf_nag` for
a self-start, and `nag_line` in the him-block of every prompt she writes
that day (`nag_in_prompt`), because the share_hint path alone never
landed while they were mid-conversation; it clears when a message of
hers touches his list (`mentioned`: anime words or a shelf title, in
`foresee_after`), after `nag_shows_max` prompts, or at her day's end),
`habits` (how he watches, written to
`user_facts` sourced to his history). `AnimeKB`: series facts, cast with
Japanese voices, seiyuu cards and characters, fetched once and cached
(tables `anime_kb`, `anime_cast`, `person`, `person_role`, the last with a
`year` per credit); `has(aid)`
separates a thing he watched from a thing that exists. `/anime`.

**What a reply may ask it, and what it may not.** `person_row`, `credits_of`
and `cast_mirrored` open the mirror `mode=ro` and answer from what is there, so
the role check costs two indexed reads and a title nobody has mirrored is
"not checked" rather than a fetch. `ensure`, `ensure_person`, `resolve` and
`find_person` reach the network and belong to a tool or a worker thread.
**Neither refresh may empty a table**: both deleted before they had a
replacement, so a 200 whose body the parser could not read emptied the cast (or
her 375 credits) and stamped it fresh for 90 days (or 120), and nothing ever
went back for it; an empty parse is now a failed fetch, the rows stand
unstamped and the type is logged with the count of what was kept.
**Nothing here goes through the community wrapper in front of MyAnimeList and
nothing may be made to** -- 504 on every uncached path since 2026-08-28 while
the origin answered in under a second -- and the daemon asks it once an hour
purely so the day the outage ends is a line in a log (`jikan_watch`, `meta`
keys `jikan_state` / `jikan_status`, read by nothing). The daemon also writes
its OWN log now (`--log`, default `logs/mal_daemon.log`), because a launcher
cannot do it for it: cmd binds a redirect on `start` to `start` rather than to
the `pythonw` it detaches, so eight days of its lines went to a handle that
goes nowhere. **Its browser is ten processes and that is Chrome's shape, not
the daemon's**: one chromedriver on profile `F:\Chrome_Profiles\SCAIL_mal`, and under the
browser process a crash handler, a GPU process, the network service, the
storage service, the ad blocker's extension renderer and three page renderers
(the MyAnimeList tab, Chrome's spare, a site-isolated ad or login frame). The
ad blocker is loaded on purpose -- MyAnimeList serves ads inside the pages the
daemon reads, and a blocked request is one that never becomes data -- and the
X scraper's browser (`C:\ChromeProfileX`) has the same nine children for the
same reason. A stop of the daemon leaves that tree behind (the lock's
`finally` never runs under a forced stop); the restarter reaps it
(`mal_history.py reap`, `sensors/chrome_reaper.py`) and so does the daemon's
own next start. Fewer processes would mean Chrome flags (no GPU process, no
site isolation) at the cost of the isolation the ad frames get; left as is.
`docs/role-check.md`.
history: archive §5.36, §5.37; 2026-09-04.

### 11.5 `social.py` `Social` + `sensors/x_monitor.py`: X as her own account

**What the account does now that it did not.** The gate's kinds: a vent
needs a spike (anger, sadness, jealousy, unsaid) or a low hour WITH unsaid
behind it (`vent_unsaid_low_mood`); otherwise a weighted pick among `seen`
(a thing on the timeline, `x_last_noticed` within `seen_fresh_hours`),
`into` (what she is into, from `diet`), `bored` and `plain`, never the same
kind twice running (`x_post_last_mode`). Engagement reaches her: on a look
the account's own posts are read back (`_engagement`, `read_engagement`;
`parse_articles` now carries `counts`), new likes / reposts / replies since
last time become a `social` event and `engagement_line` in her prompt, the
replies' text fetched for up to `engagement_replies_max` posts
(`x_monitor.fetch_replies`), and the posting gate reads it
(`engagement_bonus`). The first thing a post ever draws is not the size of
the tenth: a post that had nothing and now has something is salience 3, the
same as somebody replying, and says so in the line; a count that was already
moving is 2. The counts, the event and her own situation line all say
「the post」 and no person, because the same words go both to the model
reading her scroll, where she is "she", and into her prompt, where she is
"you". The thing she wanted to show him: a look's own
`mention` at `show_him_salience` rides her reply prompts as `x_show_pending`
(`show_him_line`, `show_him_hours`, `show_him_shows_max`) with the
`[share: ID]` links and the subject handles the noticing named; cleared
when a share resolves OR when a delivered bubble says it in her own words
(`_show_done_by` from `note_sent`: a subject handle whole or by a stem,
two shared words or bigrams, or one distinctive word; everyday words never
count) -- an item with no post behind it used to hold the slot until she
had said it twice (history: the double send entry). "look what i found"
had stopped because it only ever reached the impulse at salience 4. A
photo she sends him has its source post liked and reposted from the
account (`scenery.adopt` -> `curation.act_on_shared`, `x_monitor.repost_status`,
`curation.max_reposts_per_day`; `scenery.like_sent` / `repost_sent`): real
posts by real people, never a picture of the account's own making. **What
the account does with anything she has just sent him -- a link out of her
feed or a photograph out of a post -- is her taste's pick, not a roll**
(`docs/x-account.md` §2.1, `curation.share_pick`): one judge
(`x_repost_judge`), given how it reached him and what her sheet, her
reactions and her verdict say about that account, answers repost / like only
/ neither, and `social.repost_shared_p` and `scenery.repost_sent_p` are only
what happens when the pick cannot run.

**She cannot hand him a post she has not looked at** (his rule; `docs/
x-account.md` §2.2). A post becomes a share candidate at the end of a look,
and every picture on it is described there and then -- the same tagger that
names the series and the character, into the same shared tag store
(`_see_share_images`; a picture already in the store costs nothing). A post
whose pictures could not be described is not on offer at all and the log
says why: `[share] held: <id> image not seen (<reason>)`. **Those looks are
outside the vision day-budget**: `reason="share"` in `sensors/vision.py`
`look`, which still counts the call and says `[vision] share look outside the
day's budget: <id>`, with `social.share_looks_per_day` as their own ceiling.
Two things made them necessary. The day's eighty calls had gone to the scenery
harvester twenty-nine minutes before she scrolled, so nothing on that timeline
was tagged; and the ranking that decides which pictures she opens on a scroll
is her liking of the account, which is lowest on exactly the account she was
about to quote to somebody she cares about. **The offer names the post**:
author, text and what is in the picture, in one builder for both slots
(`_offer_line`, read by `show_him_line` and `share_line`), never the bare
nineteen-digit id it used to be; and the post her own sentence is ABOUT is
always in it, matched on that sentence against the post's text and its
picture's description (`share_offer`) rather than being the last three by
recency. What she saw follows the post out: kv `x_shared`, the `[share]` log
line, the event the delivery writes, and her own copy of the link in the
thread (`sim/thread.py`).

**WHICH post she sends him is her own pick, and it is the one tool call in
the running bot** (`tomoe/share_pick.py`, `docs/x-account.md` §2.3,
`docs/tool-calling.md` §16; the owner's call after the forty-six-moment
replay). At the moment her reply is about to be written, if a show-him
thought is standing and has not had its pick, one flash call goes out behind
`persona.system_for("him")` -- the same bytes the reply is about to send, so
the prefix is cached -- carrying her own sentence, both clocks, one line of
where she is, and **every** post she could send him rather than the three
code used to match. Two tools, constant bytes, `tool_choice: auto`, and no
free-text argument in either: `send_this(id)` makes that post the only one
her reply prompt then offers, with the same `[share: <id>]` instruction so
the send path does not fork; `nothing` retires the thought and puts the
posts away for `share_cooldown_hours` through the keys the reply path
already writes (`share_pick_declined` -> `_put_away`). What used to decide
it was a text match between an English sentence and Japanese posts, which is
a guess, and §2.2 is the morning it guessed wrong. The name is checked
against the two offered, text arriving beside the call is dropped, and an id
that is not on the list, arguments that do not parse, no call at all or a
call nobody answered are all one thing -- **a decision not taken**: the
thought stands, the three candidates code matched hold that reply, and it is
tried again at her next free moment up to `share_pick.max_attempts` (2).
Her phone has to be free, nothing of his waiting and nothing of hers in
flight; never in a sim and never in a replay, because a replay cannot rewind
what her account holds. Every decision is written the moment it exists and
before it is acted on (kv `x_share_picks`: the thought, the ids offered, the
verdict, the cost, the host), and the log reads `[share] she picked <id>
@<who> (<n> offered) | $<cost>` or `[share] she would rather not`.

The record is total: the sensor's actions log keeps every decision and
every done action with its why, `x_verdicts` every verdict with its why,
kv `x_taste_log` every reaction (`/x unfollowed`, `/x taste all`, `/x
taste <handle>`); the taste sheet's per-account `log` is only the last
eight. `/x following [hers|keep|leave|drop|unjudged|all]` is the follow
list itself: kind, verdict, likes, HERS on the ones she added. The account was his and is becoming hers. A look (code decides when; its
own Chrome session; a few images through Gemini) is read by the `social`
role into what she noticed, her taste sheet, notes about Japan and him,
proposed actions and posts to share; `Curation.decide` validates against
caps and evidence and queues, the queue runs at the NEXT look;
`Taste.judge` verdicts every inherited account against `characters/tomoe/taste.json`
and `Curation.drift` unfollows the drop list at a pace (`/x drift` is the
ruler); `posting.py` writes her own posts, text only, on **three
conditions and no fourth** -- her phone is free (which is also how "she is
awake" is known), she is inside `curation.max_posts_per_24h` /
`post_min_gap_hours`, and she feels like it. **The cap rolls over the last
24 hours rather than resetting at midnight** (kv `x_post_times`), because
her day does not end where the date does; there is no window of hours at
all, the 08:00-01:00 one having been a clock hour standing in for a wake
the sleep model draws between 06:20 and 11:05; her recent moves
reach the persona WITH reasons. **A yes she cannot act on is held until the
next quiet tick, not dropped** (his call): the roll is the impulse and it
happened, so a yes that lands while a message of his is unread or her own
bubbles are still going out goes to the save (kv `x_post_held`, with the
gate's sentence, the mode and the gauges the roll read) instead of reaching
neither branch of the call site unlogged, with the gap unspent -- 27 of the
58 rolls in the two days she posted nothing fell in that window. The next
tick with his side quiet takes it up with no second roll, through
`Curation.decide` and the gap stamp exactly as a fresh yes; it lapses after
`posting.hold_max_minutes` or when her date turns over, one hold at a time,
and a restart settles or lapses it at boot. **The composer reads the same person and the
same day as every other room she writes in** (history: the festival entry): it was built from
`Config.role_system` over a day summary written for it alone, so her account
was the one place she wrote from with no interior, no ledger and no settled
plan, and it called a festival tomorrow four times after the festival had
happened. It now assembles `persona.system_for("friend")` + `x_post.txt` +
`style_ja.md`, with `persona.carried_for()` (her media diet and the pictures
she stopped on come with it), `Ledger.text` and
`posting.recent_posts_shown` of her own posts at the head of the user text;
smoke fails if any of them stops arriving. **She may drop an account she is tired of,
never one that is listening to her**: `_protected` is the single list of
what she cannot unfollow, each entry with its reason in words -- his side
of the account (a post he liked, a follow of his, an account that was
there before her), anybody who follows the account back, and anybody who
has since gone private. Each list carries those two badges per account
(`x_monitor._badge`, read from the markup, never inferred), and the last
guard is at the browser: `set_follow` reads the profile in front of it
before an unfollow and refuses on either, because the list it decided from
may be days old (`unfollow_refused` in the action log, `/x followers`).
The other half of the same rule: somebody new who follows the account is
followed back at `curation.follow_back_per_day`, with no evidence asked
for, on its own budget so it never spends the follows she chose -- except
an account she deliberately unfollowed, which would undo her own drift.
The followers list is read at the top of every look
(`social.check_followers`, `x_monitor.check_new_followers`); the first
read is a baseline and nobody on it counts as new; the whole list is
`python tools/x_analyze.py --followers`, taken once (148 followers, 34
mutual, 4 private). The offline tools run on their own copy of her
logged-in Chrome profile (`sensors.x_tools_profile_dir`,
`open_driver(config, profile_dir)`), so they no longer wait for a gap
between her looks.
Nothing is recorded before the action. The session runs with no window
(`sensors.x_headless`): headless Chrome names itself in the user agent, so
`open_driver` rewrites the UA over CDP and hides `navigator.webdriver` on
every document. `/headless off` puts the window back for the next session,
X and the knowledge base together, when a parse has to be watched.
**She can answer somebody who answered her** (`tomoe/replies.py`): a reply
under one of HER posts, never a stranger's post on the timeline. The account
has been hers since 2026-08-22 and was his before that, so a reply under a
post older than `x.replies_not_before` is dropped at READ-IN on the parent post's
date -- those words are his, she did not write them, and she cannot answer for
them -- and never becomes a candidate, never reaches her prompt, never lands in
her store; a post whose own date the markup did not carry is treated as before
the cutoff. The first read-in of all is a baseline and answers nothing, with
the count in the log, because the first boot with this code is handed whatever
is under her last six posts. The gate is the posting gate's shape (phone free,
not mid-conversation with him, `x.replies_max_per_day` 3 over a rolling 24
hours, `x.reply_cooldown_minutes` 45, a candidate stale at
`x.reply_candidate_hours`), the decision is one `x_reply_judge` call over the
whole batch (a judge: no character sheet; a declined batch is remembered by its
id set and not paid for again), and the words are one `x_reply` call built as
her posts are -- `persona.system_for("friend")`, the call's instruction,
`style_ja.md`, her carried block AFTER the thread of her post and their answer.
`x_monitor.reply_to_status` sends it through the same profile and the same
"did the text leave the box" test as a post, and **only when that confirms**
does `Curation.note_replied` write the sent record (keyed on the reply's own
id: the dedupe), the budget and the event. **What counts as new is her record
against what was fetched, never X's read state**: no notifications page, no
unread badge -- a reply is new when its id is not in `x_replies_seen`, a
follower when the handle is not in `followers.json`, a like when the per-post
count is above the stored one (a like has no id, so likes are counted rather
than listed). He can read the account's notifications from his own browser and
consume nothing of hers; the one hazard is a Chrome opened on HER profile
directory while a session of hers runs, which kills hers. New followers are now
news to her as well as an action of hers (`Social.followers_line`): the change
since she last looked, `x.followers_line_hours` on it, never a running total.
`python tools/replies_test.py` proves the whole path on a copy of the save with
the sender stubbed.
**spec: `docs/x-account.md`.**
history: archive §5.12, §5.20, §5.82, §5.92; 2026-09-05.

### 11.6 `sensors/` (Windows only; `--no-sensors` runs anywhere)

`telemetry_collector.py` (the feed, run by `machine/collector.py` and by
nobody else: Chrome via CDP and history, and his second browser --
`chrome_monitor.py` copies each browser's history to a temp file per
process and only when it changed, and reads Firefox behind
`sensors.firefox_enabled` from `sensors.firefox_history_path`, writing a
second block of the same shape into the feed beside the Chrome one.
Firefox keeps its history in write-ahead-log mode, so the copy takes the
log and the shared-memory index with it and the memoization key stats
them too; without that the reader is behind by however long it has been
since the last checkpoint --,
`system_monitor.py` for windows and input, `media_monitor.py`,
`vault_monitor.py` for his notes, `torrent_monitor.py`, flushed by size,
by heartbeat, or on request), `eroge_monitor.py` (his text hooker's own files: the
per-game record of every line it has caught, the per-line event stream
with a wall-clock time on each, and the game library with the
visual-novel-database id and the cast -- read-only, on a temporary copy
when the writer holds the lock, and it keeps nothing) with `vndb.py`
beside it (the public database, anonymous, one card per game
and heartbeat), `mal_monitor.py`, `web_scraper.py`, `chrome_reaper.py` (kills
the Chrome a scraper left behind when it died without `driver.quit()`, by
the profile directory it holds, never by image name), `x_monitor.py` (the
Chrome session for X: feed, likes, follows, search, user posts; also the
scenery harvester's client), `gelbooru_classifier.py` + `image_tags.py`
(reading the anime image he is looking at, a shared tag vocabulary; five
things about the pair are worth knowing before anything is built on them.
**A picture is looked up only when its filename is exactly 32 hexadecimal
characters** -- `system_monitor._is_md5_filename`, a `re.fullmatch` on the
name with the extension off -- so the hash is read off the title of the
viewer's window and the sensor never opens or hashes the file itself; his
pictures happen to be named by their own content hash, and any other picture
he opens is invisible to this path. **The local nought-to-ten reading cannot
distinguish an even split from nothing rated**: `_compute_local_score` returns
5.0 when no tag of the picture is in the ratings file at all, and an equal
count of wholesome and unwholesome tags also computes 5.0, so a reader cannot
tell "middling" from "unknown" -- the board's own rating word is the field to
trust. **A failed lookup is remembered as a permanent miss**: a fetch that
raises or comes back empty writes `None` under that hash and saves the cache,
so a picture missed during a network outage is never asked about again until
the file is edited by hand. **`sensors.gelbooru_request_delay` is read into
the object and never used**, so nothing throttles consecutive lookups. And
**the classifier writes no row into the shared tag store beside it**: every
one of `data/x_images.db`'s rows comes from the picture-opening side of her
own scroll (`tomoe/social.py`), the classifier keeps its own flat JSON cache,
and the two cannot be joined as they stand -- the store keys on the first 16
hexadecimal characters of the SHA-1 of a picture's URL and the classifier on
the picture's own MD5, and their rating words differ. Full reading:
`data/retired/20260904_gelbooru/REPORT.md`, plan
`docs/image-tagging-plan.md`),
`sensors/blocklist.py` holds the one rule about what anything he had open
may be CALLED in front of a character (`sensors.window_title_blocklist`,
compiled once), and every sensor that emits such a name asks it.
`system_monitor.py` blanks a window's title at the source
(`_allowed_title` in `_poll_foreground`: the blocklist, plus every process
in `sensors.window_title_blank_processes`, which is the terminals) so the
assistant's sessions, the project's own consoles and files never reach a
character by any route; the window still counts, nameless (history: the
window-title entry). **A file manager's title is the FOLDER it is showing
and an editor's is the PATH of the open file**, so that one blanking is
also what keeps a folder name and a path out of every reader.
**A PROGRAM'S OWN NAME IS A NAME TOO** (`blocklist.hidden`,
`sensors.hidden_processes`, the same six terminals): for a terminal
"WindowsTerminal" is itself what he is doing, and with every title already
blank it stood in the second character's rolling account of his machine,
her window trail, her live status line, her picture of his habits, her
facts about him and her own written reflections. A hidden window keeps its
clock and its minutes and loses its name -- rendered as "at the keyboard",
never dropped, because dropping it would leave the account saying the
machine was quiet through the hours he typed four thousand keys into it,
and consecutive hidden windows merge into one item. Four renderers ask:
the raw activity the digest role is handed
(`system_monitor.format_system_activity`, which also drops a hidden
process from the list of the busiest), her live status line and her window
trail (`sim/phone.py`), and the busiest-process line. **And the stored feed
is read through the blocklist as well as written through it**: the monitor
blanks a title when the window closes, so a title recorded before a pattern
was added is still on disk and used to be re-rendered whole
(`_shown_title`, and `Phone._sessions_from_feed`). The same
list reaches his browsing history, where `chrome_monitor.py` drops a visit
whose PAGE TITLE matches -- a Google search whose query was a path put the
project's name in a digest from a google.com address that no address
filter names. The address side is `sensors.chrome_junk_filters`, which
both browsers' readers apply to the URL of every visit
(`sensors.firefox_junk_filters` is added on top for Firefox): sign-in
pages, whose query strings carry live tokens; the machine's own addresses,
which is where her messenger and his other chatbot software sit; and the
sites this project is built and served through, because the assistant's
chat titles name the characters and the work on them. `vision.py` (Gemini on
Vertex, region `global`: `look([images],
instruction)`; her eyes for X images, photos he sends, scenery; the day's
call count against `vision.max_calls_per_day` is kept in the save, kv
`vision_calls` `{date: n}`, so a restart does not reset it, and every call
is counted, the machine's date standing in when a caller gives none. **One
caller is never refused by that ceiling**: a picture on a post she is about
to send another person, `look(reason="share")`, which is counted like every
other call, logs that it went past the day's number, and is capped by the
share pipeline's own `social.share_looks_per_day` -- she cannot hand him a
thing she has not seen, and the harvester had spent the day's allowance by
the time she scrolled). Config
for these is flat keys in `sensors` / `sensor_view` / `vision`. Every
browser this bot drives is headless -- X (`sensors.x_headless`), the
knowledge base (`recap.headless`), the MAL daemon (`cmd_daemon`, always);
the only windowed Chromes are the ones a person logs in through
(`x_login.cmd`, `mal_history.py login`). `/headless on|off` is the toggle.

**One store of what was fetched about the world** (spec: `docs/retrievals.md`; `machine/retrievals.py`,
`sensors.retrievals_db`, default `data/retrievals.db`) sits beside the image
tag store one file over and makes the same claim: a page about an episode of a
television programme, that page condensed by a role that names nobody, the
verdict between two candidate pages, the web search behind an arriving lookup
and a game's database card are the same whoever is looking, so they are fetched
once for the machine and both characters read them. A row is `(pool, key,
model)` -- the key names the THING and never the character, the model is who
wrote the text, so a re-digest by another model is a new row rather than a
silent overwrite. A fetch is CLAIMED before it starts (table `inflight`),
because both bots poll his media player and would otherwise fetch, digest and
judge the same episode inside the same minute: whoever gets there first
fetches, the other waits for the row and reads it, a claim older than
`sensors.retrievals_inflight_stale_seconds` is taken over because a bot is
stopped with `Stop-Process -Force`, and a fetch that found nothing marks the
claim failed so everybody waiting stops waiting NOW and goes and looks, rather
than waiting the timeout out for a row that is not coming. **The claim covers
the QUESTION, not one fetch of one address** (`Recap.synopsis`,
`Retrievals.claim` / `wait_for` / `finish` / `fail`): the candidate set comes
from a live web search per process, so three processes searching for one
episode get three different sets, and the search is what has to happen once.
The claim is taken before the search and held through the pages, the digests
and the judge; the answer and the release are one transaction, so a waiter
cannot see the claim gone with the row not yet there. Three characters once
resolved one episode inside twenty-three seconds, each ran her own search, and
the one that finished nine seconds too early to read the others' page was left
holding a record of that episode with nothing in it (HISTORY.md, one
reading-up per episode). Written the moment the answer
exists, never held. What each character MADE of a retrieval is in her own save.
**An episode whose record holds no synopsis and no raw page is read again**
(`WatchingHim.owed`, §12.12): as soon as the shared store holds a page for it,
which costs a lookup and no search, and otherwise after
`sensors.retrievals_retry_after_minutes` (30), at most
`sensors.retrievals_max_retries` (2) more times, with the count of readings-up
begun written on the record before each one so a search that keeps failing is
not run every poll for ever. `python tools/retrievals_test.py`, and `--store`
in smoke: three threads on one key run one search and all three hold the
result, a claimant that found nothing releases and the next one searches
without waiting out the timeout, and a stale claim is taken over.
history: archive §7, §5.60, §5.67.
