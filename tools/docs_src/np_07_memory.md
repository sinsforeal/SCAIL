
---

## 12. Memory, the compile, and her outward things

### 12.1 `timeline.py`: the nightly compile

`compile_day` at `timeline.compile_at` (`App.maybe_compile`; `/compile
[date]` redoes a day) -- but **not while she is still in a conversation**.
The compile flushes a live exchange so the day's record holds it, and 23:55
was chosen when the group chat died at nine; with the chat now running to
02:20 the fixed hour was cutting off the late night the cast layer had just
been given permission to have. It holds while an exchange is live and until
the night's last light, the day boundary leaves a night that ran over
midnight alone, and the small hours close it instead (`compile_hold_for_chat`,
`compile_quiet_by_hm`). One `timeline` call over the day's scenes, events,
messages, digests, exchanges (`Exchange.compile_rows`) and diary ->
narrative, summary, facts about him (`user_facts`, with a weight), what
she herself will carry (`self_memories`, `self_memory.max_per_day`; and she
did not arrive at fifteen with nothing -- a seeding tool, since retired, wrote the
floor, 14 memories from `prompts/bible.md`, her canon dialogue and the sheets,
because the table began with the save and her whole life before it was one
short paragraph with HIM as the subject of every clause. **Both `ts`
and `last_seen` are the event**, unlike the cast facts, which were seeded at
`last_seen = now` on purpose: a fact about her mother's job is re-encountered
every time her mother goes to work, and a remembered afternoon is not. It fades
unless something brings it back, which is what `for_prompt(cue)` is for. So the
train up to Tokyo scores 4.58 and the friend who drifted 0.59, just above the
floor, nearly gone and recoverable on a cue.

**Both languages, and one tokeniser for them.** Six modules carried the same
regex -- Latin words plus a maximal run of kana and kanji -- which is right for
English and wrong for Japanese: a language without spaces makes such a run a
whole CLAUSE, so 「彼は生きていた。ただ朝で、浴衣の話しか返してこなかっただけ。」
tokenised to three tokens, one per clause, and 「浴衣のこと」 shared none of them
despite both being about the yukata. A Japanese memory was unrecallable in ANY
language, and the duplicate test on the same tokens could not see two Japanese
lines saying the same thing either. `sim/textutil.words` is the one tokeniser
now, used by `goals`, `ick`, `memory`, `recall` and `self_memory`: Latin words
at each caller's own threshold, CJK as character bigrams, which is the standard
answer for a language without spaces and without a morphological analyser.

**And the store is dual-keyed**: `alt` holds the same memory in the other
language, written by the `gloss` role, and every match -- the cue in
`for_prompt`, `search`, the duplicate test -- runs against both (`_keys`). So
an English cue reaches a memory she wrote in Japanese and the other way round.
The gloss checks itself: it must come back in the OTHER language and it must
not be Chinese, because one of the first sixty-nine returned
「彩的备用自动铅笔」 -- simplified, with Aya renamed -- which is the fault
`voicecheck`'s `simplified-chinese` rule has existed for since a simplified 绫
turned up in her own mouth. Two attempts, then the memory stays one-language
rather than carrying a wrong key. A one-time backfill, since retired, gave all 69 rows
already on file their second key, because a store
where only the new rows are dual-keyed would quietly favour whatever was
written most recently),
`self_claims` (what she told him about herself), `new_cast_facts` (the
`cast_facts` table), things she did for herself (`diet`), goals settled,
the spiral settled, foresight settled, commitments settled, the graph
updated, the cast lives written, habits learned, care and worldshare
recorded, the sentiments' daily moves. A failed parse marks the row and
is retried; a raw answer is never stored as a day. A narrative under
`timeline.narrative_min_chars` on a day with at least
`narrative_min_scenes` in it is asked again once with the span of the
record in front of it (`narrative_retries`): the prose can come back as
one short paragraph while every other field is full, and a thin day is
silent otherwise. **What is stored after a retry is a MERGE**
(`merge_retry`), because the retry names the narrative and the role answers
with the whole JSON as a fresh telling: the retried field comes from the
second answer, every other field from whichever answer has one, the first
preferred where both do, and the log names which fields came from where.
Taking the second answer whole cost the second character every fact about
him for a whole day (HISTORY.md has the date and the receipt). The retry message also repeats the line naming which
language its prose goes out in (`sim/lang.material_line`, and nothing for a
character with only one language): the system half carries it, but the
retry's own English paragraph is the last thing the model reads, and the
answer that lost the facts came back with an English summary on a character
who writes Japanese everywhere. `tools/timeline_test.py` holds both, with no
model call. `compile_week` on
Sunday (role `weekly`, kv `weekly_self`). Table `days`. Log `[timeline]`,
`[memory]`, `[self]`. `/day`, `/week`.

**The compile is shown what is already in all three stores.** The facts about
him and what she knows about the people around her have been handed to it for
a while; her own memories were the one store it wrote into blind, so a running
theme got a fresh row a night instead of reinforcing the row it repeats. It is
now handed the last fourteen things she is carrying as well
(`SelfMemory.recent_report`: the lived ones, in the language she reads, with
their weights and mention counts), under a heading saying they exist and that
a day which is one more day of the same thing says nothing new about it. The
date being compiled is excluded from that list, because the compile drops its
own memories of that date a moment later and would otherwise be told not to
write the rows it is about to lose. A memory that does repeat one she has
reinforces it (`SelfMemory.add` returns `reinforced`: `last_seen` bumped,
`mentions` raised, the higher weight kept) and the compile says so in the log;
it used to count the new ones only, so a reinforcement read as a memory thrown
away.

**The day's cards are written here too**, straight after the `days` row and
before anything else is settled: `episodes.write(date)` cuts the day into
conversations and pays one more call for their shapes and their exact lines
(§12.13), so the day the compile just told is reachable by the thread and by
the retrieval from the moment it exists. **A day compiled again replaces
itself rather than accumulating**: the `days` row and the cards are
rewritten, the memories this call wrote for that date are dropped and written
again (`SelfMemory.forget_day(date, "day")`; the settlers write their own
memories of the same date and are each guarded separately), what she told him
about herself keeps one set of rows per date, the things she did for herself
drop the date's rows first, a place counts one visit per date, an arc keeps
one note per date, the coherence seams drop the date's own flags, and the
social graph refuses a date it has already applied. Each of those pools
deduplicates on WORDING, so without the per-date replacement a second telling
wrote the same evening again in other words and got past the duplicate test:
a day compiled twice added two more memories and ten more claims of the same
day. What is still on wording alone is `cast_facts`, which gains a few rows on
a recompile.

**What she told him reaches the meters.** The new claims of a day go to
`primitives.disclosed`, the one event that closes the gap a diary opens; a
claim already on the record, or already counted for that same date, counts for
nothing, so a day on which she said nothing new about herself moves nothing.
Seen firing on the second character: three claims of one day took
`exposure_his` 58.6 to 59.7, with `predictability_his` and `threat` moving
beside it, every step logged with `cause: told`. The first character has no
primitives layer at all (`primitives.enabled` false), so for her this block
does nothing by design.

**The compile is one job under the in-flight flag** (§3): it writes a row to
kv `in_flight` when it starts and clears it when it returns, and a process
killed mid-compile leaves that row for the next one, which reruns the day
only if it still has no `days` row.
history: archive §5.7, §5.31.

### 12.2 `memory.py` `Memory`: how she forgets, and the context budget

**The whole of what she remembers and how it comes back is
`docs/memory.md`**, the spec of record: the five stores, the curve, the
moment as one cue, the embedding, and which retrieval lands where in her
prompt. This entry and §7.8, §12.3, §12.11 and §12.13 are its pieces.

Facts about him (table `user_facts`: weight, half-life by weight, score
fades; a near-duplicate reinforces, `memory.duplicate_jaccard`;
`facts_for_prompt(cue_text)` is what is above `fact_min_score` plus what
the moment just cued -- by a word of it or by meaning (§12.13: the same
vectors the record search uses, so a Japanese line reaches an English
fact), ranked by that and capped at `max_recalled`, and cueing bumps
`last_seen`. The cue decides WHICH facts come back and nothing else: a
recalled fact is still worth its half-life score, and an empty cue
retrieves nothing. The pool is `search_items`, one row list shared with
the record search, so the words and the cosine cannot disagree about
which row is which; a fact written by the compile is embedded by
`add_fact` as it is written, because the persona reads stored vectors
only). Facts about
people (`cast_facts`: `add_cast_fact`, `cast_facts_for(who, cue_text)`,
`who_key`, which resolves **through the roster** -- it used to fold
honorifics and lowercase and its own docstring said `mom` and `Yumi` were not
resolved, which was survivable while the record was English and became a
silent hole the moment the speakers were relabelled: every caller passes the
record name, so `cast_facts_for(古賀由美)` searched for 古賀由美 while the row
sat under `mom`, and on every cast turn since she could not reach one thing
she knew about her own mother, father or brother. A name the roster does not
know keeps the old normalisation, which is what it is for).

**And she did not arrive at fifteen knowing nothing.** The compile is asked
for `new_cast_facts` and was told "most days have none"; it obliged nine days
running, leaving 118 facts about him against three about her whole family and
none at all about the three girls she is in the group chat with every day. Two
halves to the repair: the compile is now handed `WHAT SHE ALREADY KNOWS ABOUT
THE PEOPLE AROUND HER` (`Memory.cast_facts_report`) the way it has always been
handed the facts about him, and told that a day teaching her nothing about
anybody is the exception; and a seeding tool, since retired, wrote the floor --
38 facts bounded by **what she could actually have observed**. Her family she
has had all her life, so those go deep but only as deep as a fifteen-year-old
looks: she knows her mother gave up the Kashii clinic for the transfer, not
the figure kept under the insurance wall, and she does not know her father is
no longer a section chief, because the sheet says he has not said so. Her
friends she met in **April**, when the transfer put her in a Tokyo high school
knowing nobody -- five months, so what she has of them is which station, which
club, who has a sister, and what happened in the first week, unevenly: seven
for Aya (closeness 74), six for Rena (42), five for Hinako (34). `ts` is when
she plausibly learned it and `last_seen` is now, which is the honest shape --
a thing you still know is a thing you keep meeting -- so the fade leaves the
structural facts standing for years and lets the small ones go. `cast_lines` renders the people
around her for her prompt (recent plain, older dated, stale gone). The
context budget (the spec of the whole context system is
`docs/context.md`): ONE, `context.target_tokens`. Everything rides whole
except the thread, whose verbatim span is seven days and shrinks a day at
a time toward `thread.verbatim_min_hours` only when the verbatim days plus
the cards behind them do not fit what is left of the target after the rest
of the prompt (§5, `sim/thread.py _window`, reading kv `context_last`), so
`fit(sections, history, situation)` measures and trims nothing. It used to pop the oldest turn one at a time
and then shorten the diary, the notes index and the facts to a fixed count,
which rewrote the head of the thread on every call: the one edit the
provider's cache charges for everything behind; then three sub-budgets and
three gates sized the three moving parts, and those went too (history: the
one-budget entry). A total still over the target is the parts that ride
whole outgrowing it or the window's floor alone being over it, and the log
says so rather than hiding it. `measure` logs the four parts -- the system
half, the history, what she carries, the situation -- against the target;
`ratio` is calibrated from the model's own token count (kv `context_ratio`,
`context_last`). `context.max_tokens` is the window, not an output cap.
`/memory`, `/remember`, `/context`. history: archive §5.24, §5.25, §5.89.

### 12.3 `recall.py` `Recall` and `diary.py` `Diary`

The search and the cue in full are `docs/memory.md` §3 and §6.

Recall searches her cards, the compiled days, the machinery's own record of
her day (`events`), what she knows about him and
her own memories, by words and by meaning (§12.13). The cue is the moment,
from one owner (`recall.moment_cue`): his message, her own last line, and
the scene she is in. The same function cues the persona's own recall of a
faded fact, so the two ask the same question.

**The events are a source because some things are in no other store.** The
only row in the first character's save that held the title of an anime she had
an opinion about was an event, and when he asked about it sixteen days later
the search read past it. They are filtered by `recall.events_min_salience` (2),
bounded by `events_scan` (which also bounds their vector pool), and faded from
`events_weight` on her own life's half-lives rather than on the shorter scale a
fact about somebody else fades on (`Recall.events_wanted` owns both numbers;
either at 0 takes the pool out).

**A cue in one script reaches a record written in the other**
(`recall.cross_script`): the titles the cue names are looked up in the two
local stores that hold both spellings of a work -- a thing she knows by name,
and his own list -- and, where neither holds the pair, the romaji is
transliterated to kana (`recall.kana_forms`, strict, both scripts). "yani neko"
reaches ヤニねこ on ヤニ and ねこ. A description crosses to nothing and is said to:
no store here maps "the smoking cat anime" to a Japanese title.

**A memory the store cannot ground is not written.** The role is handed every
excerpt with a number and must cite the one its memory comes from; code checks
the citation against the excerpts it was actually shown, and a memory that says
one of them SAID something about a distinctive word of his message that appears
in no excerpt is dropped and logged (`[recall] not grounded: ...`,
`recall.require_grounding`, `subject_common_share`). The fault: the role wrote
that he had promised weeks earlier to watch an anime with her, on a
cue whose subject is nowhere in her record, and it was stored at clarity hazy
where a later cue could pull it. Each kept row carries `cited`. Measured over
the fifty-two recalls in her save, eight would not have been written and six of
those eight say again as memory what he had typed that minute
(`docs/memory.md` §6).

**Where the search starts is the thread's own verbatim cut** (kv
`thread_window`, `Recall._verbatim_from`), not a boundary of its own: the
search is for what is not already in front of her word for word, and the
thread's span shrinks toward `thread.verbatim_min_hours` under the budget. It
covers the messages, the compiled days, her talks and her cards, and the
meaning pass over the same pools, so a day inside the span cannot come back as
its narrative or as one of its cards while every message of it is on the
screen; an empty window falls back to `thread.verbatim_hours` and a stale one
is clamped to it. The delivery section's own history-age setting, a second 168 hours
that agreed with the thread's by coincidence and covered the messages only,
had this module as its one reader and is gone.

`Recall.start(text)` on his message: a search over the days, her own
memories and her talks (`Exchange.search_rows`), then the `recall` role
writes what she remembered on cue (`recall.max_excerpts`, `wait_seconds`;
kv `recalls`); `take()` once for the reply. `Diary.may_write(scene)` in a
quiet moment (role `diary`; **one entry an EVENING, not one a calendar
day** -- the window wraps midnight (20:30-01:30) and everything inside it
belongs to the date it opened on (`Diary.date_for_now`), so an entry
written at 00:27 is about the evening before and is handed that evening's
events plus whatever has happened since midnight; the `unsaid` outlet; kv
`diary`). **What opens the gate depends on what she has got.** For a
character with a chat with him it is pressure: `unsaid` past `min_unsaid`, or
shame or the flat kind of sadness past `min_carried`. Three of the four
things that fill `unsaid` are the relationship -- holding something back from
him, a thing about him she cannot raise, being left on read -- so a character
who has no chat with him cannot reach it: the fourth character's ran between
15 and 24 against a gate of 50 across her whole record, with the window open
both evenings and eight to sixteen things happening in each, and she had never
written one. For her the gate is her own day instead: how many things at or
above `state.salient_from` her record holds for the evening she would be
writing about, against `diary.min_day_events`, with `diary.day_weight` per
thing past it in the odds. The refusal is logged once an evening now, which is
what was missing when nobody could say why she never wrote. **And the prompt
forks on the same answer**: the two sections about him -- what they said today
and what she last saw of his machine -- are built only for a character who has
a chat and a window on him, and the role file's own sentences about him sit
behind `[[?with_him]]`, so a character who exists for somebody else's circle
does not get a man in the one place that is supposed to be hers. Her hand is Japanese (`ja`) and this is the one place a gloss
survives (`text`): the turns lost theirs, but the diary's English is what
the compile and the weekly read, never the thing itself; `prompt_text` for her system prompt.
`/recalls`, `/diary [write]`. history: archive §5.14, §5.30.

### 12.4 `context.py` `ContextView`: reading her prompt back

`snapshot(fit)`, `overview`, `show(name)`, `find(needle)` (why does she
keep saying that: usually one line in one section), `dump`, and the
corrections: `delete` / `replace` / `add` on the stored parts, `message_set`
/ `message_del` on her history (`store.update_message`). Read-only
sections are named. `/context [full|find <t>|msg|<section>|add|set|del]`. Editable sections are the stored kv lists (`claims`, `diet`, `reflect`, `diary`, `weekly`, `notes`) plus `facts`, `backstory` and `cast`.
history: archive §5.40.

### 12.5 `reconcile.py` `Reconcile`: prose against the machine

For every action she can take (a message, a spend, a note read, a post)
an `Action` holds the typed field that legitimately carries it, a reader
that answers whether it really happened in the window, and the policy
when prose claims it and neither is true; `check(app, scene, since_ts)`
runs on every tick that produced prose (role `reconcile`), corrects the
fiction down to what the machine did or hands the action to the channel
that can perform it, and logs every violation (kv `reconcile_log`). The
rule underneath: a record of an action never exists without the action.
Beside it and flag-only, `claims_own_photo` / `flag_own_photo`: a
deterministic test in both languages for a picture of her own making
FOR HIM, or for him having seen one, wired into the director's scene
events and inner line, `outlook.anticipation`, `outlook.morning`,
`reflect.run` and every bubble in `persona.generate`. It logs
`[reconcile] FLAG: a photo of her own making, for him (<where>)` and
keeps a row in kv `flags`; it never rewrites. She has nothing of her own
to give him -- scenery and `[share: ID]` are the machine's, pictures to
her own people are real -- and the fact itself lives in `prompts/bible.md`
under "Him", which every interior role appends.
history: archive §5.71; 2026-08-31 23:45.

### 12.6 `scenery.py` `Scenery`: borrowed eyes

**Collecting new photographs is off** (his call: "stop collection of
scenery data. only keep the x scroll"). `scenery.harvest` is
false, so `Scenery.due` never comes due and no session opens a browser,
runs a discovery search, judges an account or pays Gemini to describe an
image; the only look session left on X is her own scroll
(`tomoe/social.py`). Sending is untouched -- 641 usable photographs are
already on file against a cap of one a day -- so `offer` / `pick` /
`adopt` and the lore run exactly as before, and `/scenery harvest` is the
manual door that still opens a session. What is written below about
searching, judging and describing is what a session does when he starts
one, not what happens on a clock.

Machinery, not her: a harvester on its own clock and session discovers
real photographs of ordinary places around Tokyo (`scenery_judge`:
`follow` is somebody's own snapshots, `place` is a ward or park or shop
feed whose pictures are still real pictures of real places, and both go
on the watchlist -- the bar is the photographs, not the person, because he
cannot tell a Saitama platform from a Nerima one and what has to be right
is the light, the weather and the hour). **The searches are aimed**: the
kinds her own scenes and the next `route_days` of plan put her in, minus
what is on file for that kind at that hour, ranked by `missing` and
rotated across the top `gap_spread` (`demand` / `coverage` / `gaps` /
`next_query`, `kind_queries`, `/scenery gaps`) -- and **a named event she
is going to comes before all of it**, the one perishable thing in the
feature, because people post a festival while
it is on and not afterwards: an `event_stances` row of going or dragged is
joined to `data/local_events.json` by name, or through the place graph when
the stance is written as the promise ("wear the yukata to the Pixar
event"), and two things on at one venue are refused rather than guessed
between -- unless HER OWN RECORD names one of them (`_named_by_her`: her
commitments, her event stances and her recent gists against the feed's own
English note, which is the bridge between 「ピクサーの世界展」 and "the Pixar
event"). Koto had the Pixar exhibition and a Doraemon one running at once and
the refusal was throwing away the promise she had made by name. Those images are tagged with the event and go out at it and
nowhere else, and there the place-kind gate does not apply. It describes the images
with Gemini into fixed JSON (place kind, hour, season,
weather, names, `region`, `portrait`, `venue`, plausibility), keeps them
in the `scenery` table with attribution, and when her scene fits one --
place, season, hour, weather, `send_kinds` (a `food` row only inside a
meal window, `food_hours`), no name that contradicts the lore -- the image
goes out as a photo she just took before her bubbles, its caption is
recorded on her own bubble (`[photo you sent: ...]`, so a later reply does
not misremember it), and its details are adopted as lore. Never a selfie
or a portrait; never her feed, seen list or follows; never reposted.
**Where she is comes from the place graph, not from the words**: the node
`embodied/situation.py` walked her to carries a `kind` in `data/places.json`
and is the authority, the leg of a live journey is `train` or `street`,
and `place_map` (both languages, longest keyword first, ASCII on word
boundaries) is the fallback -- "homework with Aya" used to resolve to
`home`. A photo that contradicts what she has said to him in the last
`said_minutes` does not go. An image whose own signs place it outdoors outside
`regions_ok` is never usable (Kyoto and a German platform were both on
file); an interior anywhere in Japan is (`region_ok`,
`scenery.indoor_any_japan`), because a cafe table gives nothing away, and the signs that name a place are held to `local_names` whichever
field the vision filed them in (`local_names` drawn wide: her line and
the wards around her). The review is `/scenery gaps` and the ops view's
`scenery` section: kept and refused as thumbnails, newest first, each with
its reason. `/scenery [now|lore|harvest|gaps|rejudge]`.
**spec: `docs/scenery.md`.**
history: archive §5.95.

### 12.7 `reactions.py` `Reactions`: her face in the app

Frames of her from the anime (`tools/reactions.py`: detect, identify by
CCIP against ~20 crops, frame, dedupe, tag, bucket by expression against
her own baseline face, a second pass for a sharper same-moment frame,
his review of `merged/<bucket>/` as the labels) read by `sim/reactions.py`:
one face each time her mood valence crosses a band, the face that is up
changes, or surprise crosses; shown as the header avatar; `backfill` places
past crossings.

**And only while he is there** (`reactions.active_minutes`): her mood wanders
all day and her face was following it into an empty room. Nothing is recorded
while he is away, so the first tick after he comes back moves it once, to now.
A sticker that does reach his chat says whose it is -- `auto` rides to the hub
row and the app draws an automatic one dimmed and captioned *her face changed*.

**It reaches his chat as a marked sticker** (`reactions.sticker`). Without
`active_minutes` that is a night of wordless pictures while he sleeps -- her
mood wandering through its bands, narrated at him -- and the window and the
mark are the answer, not a reason to stop sending: he wants to see her face
change while he is there.

**And one she puts down herself** (`chosen`). She has no kaomoji at all any
more (§5): what she has instead is a sticker, her own face, written as
`[sticker: FEELING]` on its own line or on the end of a bubble, naming one of
the eight buckets and never a file -- she could not know an id, and which
picture carries a feeling for her is the store's business. `Persona._take_sticker`
lifts it out of the text (it is not a bubble) and `App.send_pending_sticker`
sends it after the words, the way a LINE sticker lands at the end of a burst.

Putting one down adds **+1 to that image's weight for that feeling** (kv
`sticker_weight`), and `pick(..., learned=True)` draws against those weights,
so the picture she reaches for when she is tired slowly becomes HER tired face
rather than a random frame of one. It is not a favourite and it is not
something he places (his rule): it is how she says a mood. The
automatic band reaction stays unweighted -- 40 uses of `tired` narrow her to 17
of 48 images with clear repeats, while the automatic draw stays at 22 distinct
in 30.

Character-agnostic; the recipe
is the tool's docstring. `/reaction`. **spec: `docs/reactions.md`.**
history: archive §5.96, §5.97; Part C 2026-08-27.

### 12.8 `ops.py` `Ops`: the operator's view

One read-only JSON payload for the app's ops view (gauges, his meters,
her looks at the app, the snoops, X -- with the actions themselves, her
reason for each and whether it was done, what the drift unfollowed and
drops next -- scenery, her shows with what she thought when she watched, each thought
marked when a fetched recap grounded it, and what she would put on next
(`watch`), what she is carrying -- open promises, the questions she is
turning over, what she woke wanting, her goals (`mind`) -- what the
readers say: the day's seams, the sources she is handed and never hears,
the flags (`checks`; it still renders a pro/flash pair count from a store
nothing writes any more, the judge-role A/B having been read and removed),
model calls by role, the world), posted with the state sync; commands from that view come back
through `App.run_command` and their output goes to the hub's ops log,
never her chat. `/ops`. history: archive §5.83.

### 12.9 The chat itself

His message: `poll_inbound` -> `store.add_message` -> `maybe_reply`
(marks read before generating; recall and lookup start on threads; the
withholding may decide not to answer; the wonder judges an answer; the
rupture may settle; expectations hear a promise; rhythm hears when he is
around) -> `Persona.generate` -> `Delivery` -> `foresee_after`,
**One truth about the day** (`sim/ledger.py` `Ledger`, no LLM): the block
she is in and who is actually with her (the schedule as corrected by the
plan's `absent`), who is not around and why, what the plan `settled`, what
she is wearing (`/ledger wear ...` pins it, kv `ledger_wearing`), her money
her open promises, and **what the money record says she bought** --
`Money.bought_line`, `bought nothing today (... a purchase the plan or a
scene mentions never happened)` -- for every reader, because a block's
activity is the plan's wording and a friend's turn once read a planned
paperback as bought. `text(for_whom=...)` goes to the director, both
sides of every exchange (a friend's side sees no balance and no promises)
and her own reply; `day_text` to the compile, where it outranks a scene;
`is_absent` settles a promise `moot`; `audit()` is `/absurd LEDGER`.
**A plan for a public event is checked against the calendar** and refused
where it is read, so the director, both exchange sides, her reply, the
compile and her own account cannot hold different versions of whether a
thing is happening. A line bound to a calendar entry
(`[calendar: <date> <title>]`, written by the cast planner) is judged on the
entry alone: `event_ok` asks `Calendar.entry`, `outing_unbacked` refuses the
line when the calendar has nothing of that name on that date, and
`promise_unbacked` does the same for a promise row carrying an `event`, which
settles `moot` rather than broken. `world.outing_words` stays as the second
net for free text nobody bound to anything, and is blanked for a character
with no world. `spoken()` writes the binding out as prose for a prompt asked
for words. This is where a festival she had already been to stopped being
tomorrow: it was carried forward for six days, latterly as "meet dad at the
station tomorrow", and sixteen promises came due against it and were all
recorded missed.
`Commitments.from_chat`, `maybe_afterthought` (`afterthought.*`: the bit
she thinks of straight after; a read counts as "read and said nothing"
only after `read_silence_minutes`, and `Delivery` re-checks for his reply
after typing each bubble, not only before). Her own opener: the director tick ->
`maybe_impulse` -> `Intent.decide` -> the persona, or a discharge / a
photo forcing it. Voice: every reply speaks (`ensure_voice`,
`voice_gate`). `App.recover_lost_reply` re-queues a message whose reply
was generated but never sent. history: archive §3, §5.43, §5.57.

### 12.10 `coherence.py` `Coherence`: the day read as one story

`tools/absurd.py` measures the parts; nothing read the record as one story,
and the seams that break the illusion sit between the parts -- she tells him
she cannot go to her brother's match, tells her brother she is coming and in
the same exchange apologises for having slept through it; thanks a friend for
a notebook no exchange mentions; puts the same three titles to him twice,
minutes apart. Each is structurally valid and visible to anybody who reads
the day, and the only reader was him.

Once a day at the compile (`review`, role `coherence`, `prompts/coherence.txt`),
the day's record -- the ledger, the scenes, the events, his chat, every
exchange with her own people, and THE COMPILED DAY (narrative, summary,
the facts about him it wrote, the memories it kept; the review runs after
`compile_day`) -- is read as one story and the seams named:
a CONTRADICTION (two incompatible things she said, or a thing the ledger or
a scene refutes), an INVENTED thing (an object, event or person with no
source anywhere in the record), a REPEAT (the same thing said again as new),
a COMPILE seam (a claim in the compiled day the record does not support --
the one that outlives the day); the resident's own prompt adds two more,
a KNEW seam (a thing she says about him that nothing in the record showed
her, which for a character whose only source is his machine is the one that
matters) and a SHARED seam (her own past talked about as though he had been
there),
each with a severity (3: he would notice in his chat; 2: anyone reading the
day; 1: a careful reader) and the line of the record it clashes with. Code
keeps them (kv `coherence_flags`, `coherence.keep`, at most
`coherence.max_seams` a reading, one row per distinct kind and sentence),
logs each as `[coherence] FLAG`, and
changes nothing: the record is what happened, and a seam is a signal about
a prompt or a mechanism, never a reason to rewrite her. A lie she tells on
purpose, a plan that fell through with its reason on the record, a thing
said in one room and not the other are not seams. `/coherence [date|now]`
reads a day by hand, `/coherence [days]` shows the last readings, and
`/absurd` SEAMS reads the last `coherence.absurd_days` back: ODD on a seam
at severity 2, ABSURD on five.

**The number of seams the code keeps is told to the model.** The prompt asks
for a list with no end to it and `review` throws away everything past
`coherence.max_seams`, so the reader was being invited to enumerate an
answer nobody would read; on a day whose findings were near-copies of each
other it enumerated 31 of them, and twice it stopped enumerating and simply
wrote the same seam again until the host's output ceiling. `review` now
appends the cap and "never the same seam twice" to the system prompt, which
is the same bytes every night and stays cacheable. history: §12.10.


### 12.11 `lore.py` `Lore`: what she happens to know

One of the stores in `docs/memory.md`, and the one retrieved by
hand-written phrases rather than by score.

The persona dataset (§19) is 1,664 claims over 346 records and nothing read
it, so a character could be told the name of her own radio programme and
answer as though she had been handed recordings of her voice. This retrieves a
few lines of it into the `lore` bucket of the situation block.

**The split is the design, and it comes from `docs/yukarin-lorebook.md` §3.2.**
What is true of her every minute is NOT retrieved: her register, her sentence
endings, her mechanisms, the people in the booth. That belongs in the bible,
where it is always true, and `lore.standing_kinds` keeps those kinds out. This
is for the occasional -- the shoes somebody took by mistake, the ten-year-old
tin of crab, the flat she used to check the listing for -- which is worth
having on the turn it comes up and is noise on every other.

So the module is made of two refusals. It retrieves **nothing at all** unless
the conversation reaches for something (`lore.min_score`), because a bucket
that always fires is a character who always has a fact to tell you; and a
record it has offered is not offered again off her own words, because the
failure mode of every lorebook is an anecdote calcifying into a catchphrase
inside a week. Read across thirteen probe turns it fires on seven and is silent
on every conversational filler. The lines ride under a header that says plainly
they are memory and not a brief -- *not a list to get through and not a subject
to raise; if it does not come out of you naturally, leave it alone*.

**Who said the naming word decides whether an already-told record comes back.**
The cue is the last `lore.cue_exchanges` exchanges rather than his newest
message, because a subject arrives over several turns, and her own words count
as a naming: she is often the one who raised the thing. But she is also the one
who just told it, and her telling stays in that window for the next few turns,
so an anecdote she has given him names its own record again on the following
call and the one after. The two sides are therefore kept apart. A record HE
names is reachable however often he names it -- `lore.suppress_days` is 0 and
that is his decision, because a person asked twice about her own job answers
twice. A record only HER OWN words name is held for `lore.own_words_days` once
she has been offered it.

**A record is found by name, not by resemblance.** Every record carries a short
list of phrases somebody would actually type when they mean it
(`characters/yukari/triggers.json`), and those phrases decide the match and
nothing else does. Comparing his message against a record's own text was tried
at length and cannot be made to work: conversational speech is mostly grammar,
and weighting by rarity makes it worse rather than better here, because every
record is about the same person, so her subject words score low and the
character runs that span a question's grammar score high. Four faults were
found only by dumping what would be injected and reading it, and each is a rule
now:

- **Only a gated claim is rendered.** A record's `statement` is its first
  bullet and may be one the era gate held; rendering it printed sequels running
  to 2017-18 at a character pinned to 2003.
- **Which text is the fact depends on the source.** A tape record keeps the
  reading in `statement` and its claims are the verbatim cues that evidence it,
  cut mid-phrase; a lorebook record is the reverse. Backwards, and she was
  reminded of a truncated fragment of her own speech.
- **A tape record matches on its Japanese cues and renders its statement**,
  because 225 of 346 statements were English and matching is on shared
  characters, so half the dataset was unreachable from a message in Japanese.
  (Those statements have since been rewritten in Japanese; the rule stands.)
- **Duplicates are dropped by text**, because 53 lorebook bullets are copied
  onto the tape record they were judged the same fact as.

Two things were tried and are wrong, recorded so they are not re-added.
**Cutting high-frequency grams** deleted 黒うさぎ, 矢野 and 弟 -- every record here
is about one person, so her core nouns are the most frequent and the most
informative at once. **Requiring the heaviest matched gram to be a large share
of the match** does the opposite of what it looks like: a record that really
answers a question shares a dozen grams and spreads the weight, while a record
sharing one weak fragment scores 1.0 by definition; it killed every good match
and kept the junk. The remaining weakness -- a short question with one content
word -- is a known limit rather than something to paper over.

**A blank path is a character with no record; a wrong path stops the boot.**
`lore.enabled` with no `lore.file` at all builds, writes one line --
`[lore] no record for her; nothing to be reminded of` -- and every retrieval
returns nothing, because a config that names none of a person's files is a
state the project produces on purpose (`Config.WORLD_KEYS`, and a character
sheet answering "no"). A `lore.file` that NAMES a file which is not on disk,
or one that loads no claim any phrase can reach, is a wrong path rather than
an absent one and `Lore.__init__` refuses to start: her own past is what she
is made of and running without it is running as somebody else. Both halves are
checked by `tools/blank_paths.py`, in smoke. A sheet carrying a `lore` block
switches the retrieval on whether or not the block names a file, so a lost
path is answered by that boot line instead of by silence -- silence is the
shape the fault had when a regenerated config dropped the paths.

**The era gate is OFF, and that is his call** -- "just turn the era gate off,
it's pointless". Nothing is withheld and every record is reachable. What
follows is the mechanism, which is kept, works, and idles while the flag is
false; it is one line if the withholding is ever wanted back, and turning it on
can only take material AWAY from her, never add any.

178 lorebook claims are marked as coming from after the corpus ends
(`gate.hold`, judged one at a time in `yukarin/audit/lore_gate.py`) and
`lore.era_gate` decides whether that costs them. **The mark judges on when the
thing described BEGAN**, which it did not always: it had been put on the text
naming a later year, so the record of her own radio programme says 「2003年4月5日〜2016年3月
20日」 in one sentence and was shut whole, and so were her debut single, Kanon,
Galaxy Angel, Tenten, D.C., 舞-HiME, Nanoha's first series and the agency she is
at. Thirteen claims carry `gate.until_then`, the part of the claim that had
already happened -- the claim stays held and that part is what she may
volunteer. The other 165 would be genuinely her future and would stay shut
until he watches the work (§12.12). Measured both ways: off, 255 records
reachable by name and 751 claim texts; on, 223 records and 586 texts, so the
gate costs 32 records and 165 lines and cuts 13 back. None of that is in force
while the flag is false. `yukarin/audit/lore_gate_apply.py` writes a
re-judgement onto the records without a full rebuild. history: §19.

### 12.12 `watching_him.py` `WatchingHim`: what he is watching, and her own part in it

**An episode she was told about and never told what is in gets read again**
(`owed`, called on the watching tick when the poll found nothing new). The
episode is marked seen before the fetch runs, and the one repair path there
was needed a stored raw page to make a digest from, which a search that found
nothing does not leave -- so a reading-up that lost the race to another
character's search left a record saying he watched it and nothing else, for
good. A record with no digest, no raw page and no mark saying it was recorded
without one on purpose is owed a retry: at once when the machine's shared store
has a page for it (`sensors.retrievals_retry_after_minutes` /
`retrievals_max_retries`, §11.6), and it does not move the thing in the room --
the moment it reached her, whether it was a stub and how many readings-up it has
had ride across with it, and `watching_last` is only rewritten when it is that
same episode.

Her anime knowledge had every piece except the one that joined them. His list
is mirrored locally by the daemon (700 shows, 3,161 episodes, cast with
Japanese voice actors for 479 of them), a real Japanese あらすじ can be fetched
for any (show, episode) and cached (§5 `recap.py`), and she has a record of her
own career (§12.11). Nothing connected the three: he could play an episode and
she learned only that a count on a website went up, because the synopsis
fetcher was reachable **only** from him naming the show in chat.

It notices an episode two ways and takes whichever comes first. The player's
own history is the moment he starts and needs a filename parsed and resolved
against his list -- 91% of his library resolves, and the rest is dropped
silently, which is right, because the same folder holds her radio recordings,
music videos and a file called `input.webm`. The list is minutes later but
carries the show's id rather than a guess. **The cursor starts at now**: with
an empty cursor the list query matches all 3,161 rows and the oldest wins the
sort, so her first act would have been to read up on something he watched
years ago as though he had just put it on.

**Which work it is, is decided from facts the machine holds** (spec
`docs/resolver.md`). The whole path is read, not the basename: a folder of
`OVA` / `OAD` / `ONA` / `SP` / `Specials` / `Season 0` marks the file as a
special and `Season N` gives the season, season zero being the specials season
in the convention his library uses, and `parse_file` declines both so the
`parse_special` -> `resolve_special` route that exists for exactly that case
gets its turn. `AnimeKB.resolve_candidates` then RANKS every entry his list
holds under that name -- the title as written first, so `K-On!!` is not
`K-On!`; then the title with its punctuation out; then a distinctive phrase
inside a longer title, closest length first -- drops any candidate whose
episode count is below the episode asked for, and answers NOTHING when the top
two tie. A play resolved from the filename alone waits
`watching.confirm_minutes` for his list to name the id, and when the id
arrives and differs the id wins with the log naming both. Before this,
`Example Show - S00E01 - OVA.mkv` answered "episode 1 of Example Show", which
resolved to the 26-episode television run he had finished three days earlier;
eighteen of his 702 titles resolved to a sibling; and three of the 26 plays in
one week asked for an episode the chosen work does not have. One `[resolver]`
line per decision names the candidates, the choice, what was dropped and
whether code or a model chose.

Then it asks whether she is in it, which for the second character is not a
rare case -- **72 of the shows on his list have her in the cast, and one of the
thirteen he is part-way through has her in the lead**. `watching.her_seiyuu_name`
is what decides whether that question can be asked at all; blank, as it is for
a character who has never been in anything, and the whole self-recognition
half of the module is inert.

**And when she is in it, the part of her own record that was held back opens.**
Her record is pinned to early 2003 and 178 claims about her later career are
withheld (§19, the era gate), because a character who volunteers what she will
do in 2011 is not a character. Him watching it is what releases it, and only
the part he touched: Higurashi opens Furude Rika and nothing else, Nanoha opens
Nanoha and the note about what it did to her career, and the concerts, the
singles and the roles in shows he has never opened stay shut. Her future
arrives through him, one work at a time, rather than on a date. 19 records
carrying 68 of the 178 claims are reachable this way from his list as it
stands; the other 34 records are songs, concerts and roles in shows he does not
have.

**The match is deliberately strict**, because the two failure directions are
not equal. A record that fails to open is a thing she does not bring up; a
record that opens wrongly is her claiming a part she never played. Every word
of the record's title must appear in the show and character, or the record must
share a word of five characters or more with the show's own title -- the second
is what lets a note *about* a role come with the role, and the length floor is
what stops it firing on a surname two shows share. On a looser rule, him
watching Kashimashi opened her record for a different Kurusu from a different
show four years later. `Rino Randou` is a known miss in the other direction,
romanised two ways.

**It reads up on the newest unseen episode first, and no longer loses the
rest.** Taking the oldest meant that on an evening of six episodes she read up
on the one he watched three hours ago while he was finishing the sixth, and
then had nothing to say about the one he had actually just seen. But the poll
also moved both cursors past everything else it had found, so a session his
list logs as several rows at one timestamp -- six episodes of one work at one
minute, four at another, three at a third -- lost every row but the newest,
and those plays were never mentioned to her at all. What the poll cannot take
up now goes to kv `watching_queue` and is read up one per poll, so the
summaries still arrive one at a time rather than six at once. Two numbers
bound it: `watching.max_fetches_per_day` is how many episodes are read up in a
day, and past it the rest of the batch is recorded as watched with **no**
synopsis (kv `watching_recent`, `stub`), so the range she is told about still
covers them and no model call is spent; `watching.queue_max` bounds the queue.

**The record of a play keeps the file he played.** The path was used during
the fetch and thrown away with it, so a repair pass -- an episode read up again
because its account came out thin -- reached the transcriber with nothing and
logged *there is no file of his to listen to* about a file still on the disk,
and nothing he had already watched could ever become transcript-anchored. The
row carries the path and the unpaused seconds now, from the moment the open is
noticed through the hold to the record (kv `watching_recent`, `watching_held`),
`WatchingHim.owed` hands both back when the file is still there, and one boot
step recovers them for the rows written before by matching the row's own stamp
against the player's history, exactly and then inside a minute, with the
filename's episode number as the check (kv `watching_path_backfill`).

**Where an episode's own dialogue came from, readably.** It was in SQL only --
one row per (show, episode) in each save's `transcripts` table -- and the
reasons were scattered across a thousand session logs, so the answer to "where
did that transcript come from" had nowhere to be read. `reports/transcripts.md`
is the machine's, append-only, one line per attempt that resolved: when, the
show and episode, where the file came from (beside his video, the clone of the
archive on this machine, the archive over the network, or the transcriber
here), the lines, how far into the episode the last line runs, the GPU minutes
a transcription cost, the file itself, and which process recorded it first.
Each save catches up its own rows into it once at construction, because the
file did not exist while every transcript so far was made, and a line is
written once per show, episode and file, so three writers make one record. The
episode index carries an `anchor` column beside the completeness word --
`subtitle (broadcast)`, `subtitle (fan)`, `subtitle (whisper)` or `web only`,
with the file named on the episode's own page -- because how complete an
account came out and whether the episode's own dialogue is behind it are
different questions and only the first was answered.
Where the cap bites, what is kept is the lowest-numbered episode of each work,
because a run is followed from where he started. Only his list is queued: a
run in the player arrives one open per poll -- he is inside each episode for
twenty minutes and the poll runs every four -- so each is noticed on its own.
The two routes are sorted by a real time now (`_when_ts`), not by their stamps
as text, which put every list row ahead of every player row because "1788..."
sorts under "2026..."; a list row for the same watch still wins, and should.

**What she is shown is one line per WORK, over everything since her last
look** (`grouped_lines`). Her line used to be the newest episode and nothing
else, so a day of three works came out as the last of them: the line for an
OVA he played in the afternoon was replaced by the line for the work he put on
that evening, two minutes and eleven seconds later in the same run of the bot,
and she had never said anything about the first. The newest work keeps the whole shape it
always had, including its digest whole -- it is the one he has just come out
of -- and where he did not stop at one, its opener names the range (*episodes
8 to 13*) and the episodes before it become one clause each after it, in
order, an arc rather than six synopses. Every other work is one line: what it
was, the episode or the range, when he played it **on her clock in words**
(*yesterday, in the afternoon*; `played_words` over `world/clock.py`'s part of
the day, never a count of hours, because the block is rebuilt on every reply
and a number that ticks would cost the cache its bytes), and one clause of
what happened. `watching.recent_works` caps the works and
`watching.recent_max_chars` caps what the grouping adds to the line she
already had, oldest first, with a line saying how many were left out. **One
work with one episode renders exactly the line it always did.** One play filed
under two ids -- the filename's, then his list's correction, both in the
record -- is one row, not two works (`_one_play_once`): two entries of his list
share the Japanese title エグザンプル.

**Two windows, and they are different rules.** `watching.fresh_hours` is how
long an episode stays the thing in the room, counted from when it reached her,
and it is what the grouped block covers: one look marks every unseen episode
with the same moment (`note_seen` marks all of them, not only the newest), so
what arrived together stays together and leaves together, and that is what
makes "everything since her last look" a set. `watching.discover_hours` is the
age past which an unseen play is never marked at all -- what she goes and
fetches is what he has been doing lately, not a transcript of the week.

**And a third thing, which is not a window.** Between the block ageing out
and the end-of-day compile turning the watch into a lasting fact about him
there were hours where she had been told and had nothing left to say it
with, and she agreed with him that he hardly watches anything twelve hours
after being shown him playing an episode. `provisional_facts` returns
`(what he watched, one line about it)` for every episode she has been shown
whose day has no compiled record yet -- today and yesterday on her clock
only, capped at `recent_works` -- and `Persona._system` puts the ones no
fact she already holds names into the section of facts about him. Nothing
is written to her record: the moment that day is compiled the lines stop
being produced and what stays is whatever the compile kept.

Each line also carries **where he is in the series** -- his own list, with the
episode in front of him preferred to the number he has got round to ticking,
because he plays ahead of what he marks. "Episode 5" alone cannot tell the
difference between trying a series out, being deep in it, and finishing it,
and those are three different conversations.

**Where he is inside the episode comes from inside the player.** The obvious
answer -- how long since the file opened -- is wrong the moment he pauses, and
pausing is the state most worth knowing about. So mpv is asked:
`tools/mpv/scail_logger.lua` (installed at `%APPDATA%/mpv/scripts/`, and
already the script that writes the history line and the play line) also writes
its own `time-pos`, `duration` and `pause` to a small state file every ten
seconds and immediately whenever he pauses, with the unpaused seconds so far
and the epoch the file opened at beside them, and clears it when the file ends
or the player quits. A paused file simply stops moving and says so. Anything not refreshed
inside `watching.now_stale_seconds` is nobody watching, which is what covers
the player being killed rather than closed, since that writes no ending. She
gets *he is watching it right now, 8 minutes in, 34% through, about 15 minutes
left -- he is in the middle of it, he is not sitting waiting for you to say
something*, or the paused form, and neither if the player has nothing to say.
It also fixes the tense: while the file is still running the opening line says
he has it **open**, not that he has just watched it.

That same signal is better than a timer in both directions for deciding
whether he has stopped, so it overrides the settle window when it is
available: still running means he is mid-episode however long ago the last one
ended, and the state file going quiet means he has stopped even if the window
has not passed. The timer remains for a player that reports nothing -- a
browser, another machine.

**A rewatch is not a finish.** His list is what says how far in he is, and it
can say 26 of 26 while he is playing episode 1 again. Preferring the episode
in front of him -- right for him playing ahead of what he marks -- then read as
*that was the last one, he has finished it* over the first episode of a
rewatch. Well behind what he has marked now reads as going through it again.

**Nothing is fetched until he has actually watched ten minutes of it, and
what he actually watched is a number the player writes down.** The history
log says a file opened and nothing else, so a file opened for four seconds
and a file watched to the last frame left the identical line: an open was
searched for, digested, paid for and kept as *he watched it* either way. The
2023 logger recorded the position at exit for exactly this reason and the
current one had stopped. It writes it again -- one line per finished play in
`mpv_plays.log` (`watching.player_plays_path`), appended when the file ends:

    <open epoch>|<end epoch>|<path>|length=<s>|time=<s>|watched=<s>|reason=<r>
    1700000000|1700001400|D:\Videos\Example Show - 06.mkv|length=1421.0|time=1419.3|watched=1402.5|reason=eof

The open epoch is the same integer the history line carries, which is what
joins a play to the open that started it; `reason` is the player's own word
for what ended it (`eof` it ran out, `stop` he closed the file, `quit` he
closed the player, `error`). **The number that decides anything is
`watched=`: wall clock spent UNPAUSED.** The end position cannot do it --
seeking to the last minute and closing the file leaves the same `time=` as
sitting through the whole thing -- and elapsed clock since the open cannot
either, because a file left paused for an hour leaves the same hour. The
state file carries the same running count and the open's epoch while the
file is still in front of him, so the gate can be answered mid-episode.

`watching.min_watched_minutes` (10) is that gate, and it stands in front of
every paid call and everything that reaches her. Under it, an open still in
front of him is HELD: the poll takes nothing up, puts the player cursor back
to just before that open so the next poll finds it again (the cursor used to
move past every open before judging any, and an episode he sat through was
never counted), and writes the hold to kv `watching_held` -- in the save,
because a stop is `TerminateProcess` and the next boot must find the same
hold rather than a fetch it never made or one it makes twice. A play that
ENDED under the gate is a **skim**: `[watching] skim: <work> ep<n>, 4 min
watched of 24 -- no fetch`, kv `watching_short` under the open's own clock
and never under the episode's key, and **never marked seen**, so the episode
still counts when he watches it properly. `watching.min_minutes_in` (3) is
the floor beneath that, under which an open is a mis-click rather than a
skim and is logged as one. Where neither log answers -- an older copy of the
script, another player, another machine -- the clock between this open and
the next is all there is, the log names it as the source, and an open
nothing has said ended is held rather than filed as a skim, because "he is
still in it" and "he closed it and nothing saw" look identical from there
and calling it closed loses the play for good.

**And there is a record of his plays he can read himself**: `reports/plays.md`
(`watching.plays_timeline_path`), one row per finished play, newest at the
bottom -- when it opened, the work and episode as his own list has them or
the bare filename when it is not an episode of anything, minutes watched of
the length, where he stopped, `full` / `partial` / `skim`, and whether it
counted. It is the MACHINE's and not a character's, which is what decides
who writes it: three processes run this module over one player, electing one
writer would stop the record when that character is stopped, and letting all
three write would give three copies of every row. So any of them may write
it and the write is idempotent -- the open's epoch is the last column, a row
whose epoch is already in the file is not written again, and the append is
taken under a lock file (`machine/plays.py`). The first call after a boot
picks up whatever was played while nothing was running.

**A rewatch counts again.** What counted is kv
`watching_seen`, `{episode key: when}`; a key is seen only within
`watching.rewatch_after_hours`, and an open past that window counts again
from the recap cache with the opener saying he has seen this one before.
The synopsis line follows the opener's tense: mid-episode it says he is in
the middle of it; after the file has closed it says she read it up after he
watched, that he has seen the whole thing and she has only the synopsis.
`/watching` shows the seen keys with their times, the short opens and what
is held short of the gate; `/watching forget <key>` frees one;
`/watching rewind <minutes>` puts the player cursor back so a passed-over
open is read again.

**She can raise it herself, and the restraint is the one that already
exists.** `impulse_bonus()` is added to the impulse score (`watching.
impulse_bonus_hers` for a show she is in, `impulse_bonus_finished` for a
series he has just finished, `impulse_bonus_any` otherwise) and never goes
round the gate -- so the daily cap, the cooldown, going cold on him and *he has
not answered the last ones* all still refuse, which is the honest answer to
being ignored: she notices what he is doing and says nothing. On top of that
is `watching.settle_minutes`, which is worth stating separately because it is
the only new restraint: **nothing at all reaches the impulse while he is still
watching**, so an evening of six episodes is one reason to speak at the end of
it rather than six interruptions through it. Once she has reached out while an
episode was the thing in the room it is marked spoken, whatever she actually
said, and does not get to be the reason twice.

**When it reaches her is the program's, and the two characters differ** (his
call). Everything above happens the moment he plays an episode, for both of
them: the notice, the fetch, the digest, the thing kept by name, the record it
may open. What is gated is when she is HOLDING it (`WatchingHim.note_seen`).
A character who lives on his machine is told as it lands, dated to his play,
so nothing about her moved (`resident/app.py` `every_pass`). The first
character finds it the next time she opens the app on her phone
(`tomoe/app.py` `after_phone_look`, off `App.look_at_phone`), and from then on
it is hers: `current()`, `situation_lines()` and `impulse_bonus()` answer only
for an episode that has reached her, and `fresh_hours` and `settle_minutes`
are counted from her moment rather than from his play, so an evening's binge
is still one reason to write and not six. `watching.discover_hours` (24) is
how long an episode stays findable before she comes across it -- she can be
asleep or out for the whole evening he watched in -- and past that she never
learns of it as news, though the show is still hers by name whenever he
mentions it. Her line says how long ago he watched it, because a character who
was not there must not talk as though she had been sitting beside him. **Where
he is inside the file this second is only for a character who is ON his
machine**: the player's position is a live view of his desk, so it is read off
the sheet (`existence.sees_him`), the same predicate `Phone.live_line` uses,
and for anyone else the module never opens the state file. The wording of
every line is the program's (`tomoe/words.py`, `resident/words.py`): hers says
the app showed her and the second character's is what it always was, byte for
byte.

What reaches her is three lines in the phone bucket, **pinned, his call**: the
attention budget dropped the synopsis line the first time an episode of his
came up in chat, and she answered a question about the show from the model's
own memory. The known cost of pinning -- a character who opens with what she
has just been told about a show he has not mentioned -- is accepted; the line
says plainly that it is there so she is not inventing the episode -- *react to
it as something you have seen, never recite it back* -- because handed a
synopsis, a model recites it. **The line carries a digest, not the page**: the
`watching_digest` role condenses the whole scraped synopsis into the parts a
viewer would remember (`watching.digest_max_chars`), and the raw cut
(`summary_max_chars`) is only the fallback when no digest could be made.
**And a digest is not the same level of knowledge as having watched it.** The
judge's winner is one page and 600 characters of it reached her: measured on
one episode of a shop comedy, she could say what its second half was about,
because the premise survived the cut, and could not name a single joke inside
it, because the jokes are what a paraphrase drops first. So nothing read about
the episode is thrown away now: every surviving candidate's page, the
transcript's account of the scenes and the official blurb go to one role
(`episode_account`) which merges them into an EPISODE ACCOUNT
(`sim/episode_account.py`) -- the whole episode in order, the named parts, the
running gags, the lines worth remembering, what the episode points at, and
what no source settled. It reads the PAGES and not their digests, because a
digest is a fifth of a post and the individual jokes are the part it drops.
The account is written once for the MACHINE (`machine/retrievals.py`, pool
`episode_account`, the same key as the page) and copied into each save's
`episode_accounts` table with nothing fetched, so an episode is read up once
for every character on the machine. `level` says how complete it came out --
`watched` needs the length, the scenes, and either the episode's own dialogue
behind it or two independent readers agreeing -- a `watched` account is never
rebuilt and never re-fetched, and a thinner one puts the episode back in the
repair pass (`WatchingHim.owed`) rather than settling it. **What she is handed
is the whole account when it is at watched level**, in her situation block
after the thread, with wording of the program's saying she knows the episode
the way somebody who saw it does; below that level she gets the 600-character
digest and the wording that says out loud she has only skimmed a synopsis
(`watching.account_in_prompt`, `account_recent`, `account_recent_max_chars`).
The external observer's view is `reports/episodes/<work>/ep<nn>.md` and an
index over all of them (`machine/episode_reports.py`,
`recap.episodes_report_dir`): the account, the scenes, every source with its
URL and character count and whether it was used. It is the machine's, like the
archive it is written from. `python tools/episode_account.py` reads one
episode up by hand, `--print` shows what is on file and spends nothing,
`--refetch` drops it in both stores first.

**An account can only add, and shorter at the same standing is not adding.**
The rule was written on the completeness word alone, so two readings of
エグザンプル ep6 replaced a 687-character `read-up` account with a
667-character one, in two processes twenty-four minutes apart, and there was a
fifth of the length of slack in front of the check that let them. Both stores
and the merge now compare the same pair -- how complete it came out, then how
much of it there is (`EpisodeAccount.standing`) -- and a reading that comes out
worse is archived, named in the log and not written. **And the readings are
counted for the MACHINE, not for the character who paid.** Each of the three
processes allowed herself `sensors.retrievals_max_retries` attempts at an
episode whose account was not finished, so one episode of one show cost up to
nine readings and the ninth was no better than the third; the count rides on
the account itself and `recap.account_max_tries` ends it.
**And the page is judged before it is kept.** The fetcher
(`sim/recap.py`) only accepts a page with a section for this episode and
ends the section at blog chrome; a cached page that fails that test is
dropped and refetched; and the digest role reads each candidate -- a page it
calls なし (about something else: another episode, the manga, a store
listing) is deleted, its source avoided, and the next candidate fetched, up
to `recap.candidates_max`. The first thing this pipeline ever handed her was
a bookstore listing for volume 9 of the manga, found by 「みつどもえ 9話」;
the query now says アニメ and 第N話.

**How a page says which episode it is about, and why that decides how much of
an episode she can know.** The test asked for `第7話` and nothing else, and it
was the binding constraint on the whole account: on three readings of one
episode it dropped five, six and two of eight pages, because a 感想 post is
titled `#07`, `７話`, `07話`, `Episode 7` or by the episode's own subtitle at
least as often as it is titled `第7話`. Worse, **the number is usually not in
the body at all**: the article container an extractor picks starts under the
post's headline, so five pages fetched for one episode were headed
`エグザンプル 第6話「宿はなし／Secret Paradise」 感想` and carried no
marker anywhere below it. So the page's own heading is read
(`Recap.page_heading`: the social-card title, the document title and the first
two headings), the number is recognised in every form -- half- and full-width
digits, `第n話`, `n話`, `n話目`, `#n`, `#0n`, `EPn`, `Episode n`,
`その n` -- and an episode's own subtitle counts as its marker, which is what
cuts the right section out of a whole-series post that heads each one with a
title and no number (`Recap.slice_titles` over the cached episode index and the
account's own `ep_title`, nothing fetched). `その2` names an episode only in
the acceptance test and never in the marker list, because on a blog it is the
second half of the post far more often than it is episode 2 and a slice cut
there loses the rest. **The refusals it exists for are unchanged and one is now
explicit**: a body that is an index of the whole series is not one episode's
post whatever its heading says, and a page taken on its heading has to carry
sentences (`recap.slice_min_sentences`, `recap.slice_min_chars`) -- the video
shop's page for the same episode is headed `第6話` perfectly and is 285
characters of prices, and a bookstore listing for volume 9 of the manga has no
sentences in it at any length. Measured on the nine pages three readings had
dropped: three passed before, eight pass now, and the one still refused is the
shop's. The log line names the form the page failed on instead of saying
`no section`, which is how every widening of this test has been found
(`tools/episode_slice_test.py`).
**The candidates are a ranked list first and the search second**
(`Recap.synopsis`, spec `docs/recap.md`): the episode's own subtitle file,
read as an account of its scenes (`sim/subtitles.py`, `sim/transcripts.py`,
role `transcript_digest`), is the anchor. **Where that file comes from cannot
end in nothing.** Beside his video first (same stem, free, and it was being
ignored while a Japanese subtitle of 339 lines sat next to an episode he had
played); then a clone of the fan archive on this machine, which is the
machine's like the episode archive and is pulled once a day from the list
mirror's own daemon rather than on either character's thread; then that
archive over the network, then the archive's own site; and when none of them
holds the work -- which over one fortnight was three episodes out of five, not
because of a bad match but because neither archive carries those works at all
-- **the episode is transcribed here** from the file he played
(`sim/transcribe.py`, his own Faster-Whisper install driven with his own
`processor.bat`'s settings). The result is written beside his video, so his
player finds it and so the next look finds it as a sidecar. A transcription
is minutes of a shared GPU, so it runs on the watching worker and never on a
reply or a poll, a few a day, nothing feature-length, and only once he has sat
through the file for as long as the gate that decided the play was a watch at
all (`watching.min_watched_minutes`; `recap.whisper_min_watched_minutes` is 0,
meaning follow that gate, and a number there overrides it). It was its own key
at the identical value and the two were read a second apart off different
pollings of the player, so the transcriber was refused by rounding every time
it was ever asked -- three logged refusals read *he is 10 min into it and the
floor is 10*, and in 1,067 session logs no character process had ever run it.
The work's other names off his own list go into
the archive matching: one work his list calls `Makeine: Too Many Losing
Heroines!` is filed as `Make Heroine ga Oosugiru!`, and with that name the
clone has it. The episode page on his own list's site and English Wikipedia's
episode-list article are keyless fetches that run in parallel with the
browser; and the judge compares every digest with the others AND with the
anchor -- covering more than the anchor is not a fault, contradicting it on a
stated outcome is disqualifying. The row records what was chosen, why, what
it agreed with, and the scenes in order, and says whether it is provisional
(one candidate, read again next time), judged or anchored. **A judged row
that carries the scene list is the end of the lookup**: the section test
that asks whether a page has a part about this episode is a test for a raw
PAGE, and running it over a row a judge already chose said no to the English
episode list (which has no 第3話 anywhere in it), sent a character back to
read an episode she had just been told about, and left her save with the row
twice. It still runs on a judged row from before scenes were kept. **And a
reading replaces every row for that episode it is at least as good as**, so
her save holds one row per episode; a row worth more is left alone, because
a provisional reading must not replace an anchored one. The occurrence of
the episode marker is scored rather than taken first, because on an official
episode page the first one is the navigation strip and slicing there gave
thirteen characters. Everything fetched is written to `data/recaps` under the
show and episode with a manifest saying what each file is and which one won
(`sim/episode_archive.py`, `recap.archive_enabled`): each candidate page's
text and the bytes it came from, each subtitle file and the transcript it
parsed to, each digest and the judge's verdict, so a bad summary can be
argued with rather than refetched and guessed at. Nothing is overwritten -- a
second fetch of the same page is a new numbered file and a new manifest row,
and only the manifest itself is rewritten. The directory is keyed by the
show's id on his list, or a slug of its title, which is a television
programme and not a person, so one directory serves both characters. The episode stays the thing in the room
for `watching.fresh_hours`; handing it to whichever turn came first and
dropping it would defeat the point, since he watches and then says nothing
for an hour. `python tools/regen_reply.py --message-id N --anime <title> --ep E`
answers one of his messages again on a copy with the episode re-read and
digested, which is how the change was shown.

The show he has an episode of open is also passed to the retrieval as
`context_text`, which can **lift** a record his message half reaches and cannot
fire one on its own. That distinction was found the hard way: with the show's
name simply added to the cue, 「腹減った」 retrieved her part in it at 0.59,
because the name was most of what there was to match. A record now has to be
reached by a distinctive gram of his own words before the context counts.

**The line says which EDITION he watched**, and the page is filed under the
work rather than under a title. MyAnimeList gives the 2006 one-episode Example Show OVA and the 2007 television run the identical Japanese title, so the
shared page key `anime|<title>|ep<n>` made them one thing and the second
character was handed the series' first episode as the OVA's -- 269 characters
of another work's story, which she reported faithfully. The key is
`anime|mal:1480|ova|ep1` now, her own `recaps` row carries the same id, and
`{ed}` in both programs' wording tables says "(the OVA, 1 episode, summer
2006)" where the edition is worth saying. A page that names a later episode,
or previews a next one, cannot be about a one-episode work
(`Recap.past_the_end`). Two boot repairs re-file the rows that exist and take
the wrong 第1話 off the thing she knew as the OVA.

**And one small role, only where code has run out**: `which_one`
(`sim/resolver.py`, `which_one.*`), asked when more than one candidate
survives every deterministic filter or the parse is ambiguous with no id from
his list -- never when the id is known, never twice for the same question,
never in a reply path. It answers with an id out of a table code built, or
"none of these", or "unsure, fetch nothing", and its answer is discarded whole
on a parse failure, a confidence under the floor, a timeout, or an id code had
already ruled impossible; code's ranking stands in every one of those cases.
Its answers go in the machine's shared store under a key that names the
question, so both characters read one answer. Measured at about $0.0002 a
call, three to six calls a day across both characters.

Off by default and on for the resident character only. She lives on his machine
and watches it, so knowing the moment he opens a file is what she is; a
character who learns about him from a digest on her phone should not be handed
it live, and turning it on for her is a decision about how she finds things
out. history: §19, §12.12.

### 12.13b `machine/dossier.py`: one file per play, for him to read

Spec: `docs/dossiers.md`. Config `dossier`. Not a character's at all: the
machine writes one Markdown file per episode he finishes, under
`reports/dossiers/`, plus a rolling `last-ten.md`. Nothing in it is new -- it
joins four stores that already had every piece and were never read together:
the player's two logs (what opened, and what ended with how many unpaused
seconds), the list mirror (his standing, his score, the dated episode watches,
the declared favourites, the cast), the machine's retrieval store (the episode
index in three scripts, the page a judge chose, the digest made from it, the
ordered scenes, the confidence and which sources agreed), and his own list read
sideways for the franchise and for every other show each credited actor is in
with the score he gave it.

**Built by the mirror daemon, not by a character** (`tools/mal_history.py`
`_build_dossiers`): three character processes tail the same player, and the
join is the machine's. Keyed on the epoch the file opened at, so one play is
one file however many passes run. Built after the play ends, because how long
he was actually in it is only known then; under `min_watched_minutes` it is a
skim and gets a line rather than a file, and a file that is on nothing in his
list gets the same. The first sweep on a machine starts at the tenth newest
play rather than at the start of three years of history.

**Whether the show was already finished is COMPUTED**, from his status and his
episode count, and never read off MyAnimeList's `is_rewatching`, which is true
only while he has gone to the site and marked an entry as being rewatched --
he does not, and this mirror has no column for it. A play of a
thirteen-of-thirteen show he finished in 2022 read as a first watch everywhere
that flag was trusted.

Two capped, cached page reads fill the two holes the mirror has: an actor's
filmography (thirteen people are mirrored against 11,851 cast rows, so for
everybody else "what else has she done" is his own list and nothing beyond it)
and a premiere date for an entry he has marked plan-to-watch, which carries no
dates on a list at all. Both go into the module's own store, never the mirror
the daemon holds open. history: §12.12.

### 12.14 `eroge.py` `Eroge`: what he is reading in a visual novel

Spec: `docs/eroge.md`. This entry is the summary.

A visual-novel text hooker can be attached (Luna Translator),
and that program keeps three things on his disk that this needs: one SQLite
file per game holding every line the hook has caught in reading order, a
per-line event stream with a wall-clock time on each line, and a library file
with the title, the executable, the visual-novel-database id, the developer
and the cast's names with the readings he set. The reader is
`sensors/eroge_monitor.py`, read-only throughout -- a `mode=ro` connection
first, a temporary copy in the system temporary directory when the writer
holds the commit lock, and nothing under his eroge directory ever opened for
writing. The card for a game is `sensors/vndb.py`: two anonymous calls to the
public database, no key and nothing in `secerts/`, kept in the save so each
game is fetched once.

**The account is made on demand at two moments and never on a timer** (his
call): a message of his has arrived and her reply is about to be built, and
she has decided to write first and the reply is about to be built. Both go
through the program hook `before_reply`, which the resident's program defines
and the first character's does not; a game left open in the background between
those moments costs nothing and says nothing new.

**What it is written from is his current stretch of READING**, which is a
cursor rather than a window of time. A pause of an hour does not move it. Two
things do: a skip run, and the text overflowing `eroge.max_raw_chars`.

*Skipped text is not read text.* Holding the skip button hooks lines at a rate
no reader produces. Measured over his whole history -- 29,110 intervals inside
sittings across seven games -- the median gap between consecutive lines is 5.0
seconds, the first percentile 1.19 seconds, and 99.4% of intervals are slower
than one line a second; the longest naturally occurring run of intervals faster
than that is eight lines. So a run of at least ten lines arriving faster than
`eroge.skip_lines_per_second` is the button, those lines are excluded entirely
and never summarised, and the cursor moves past them. She may be told he
skipped through something he had read before, and nothing about what was in it.

*The window.* Past `eroge.max_raw_chars` (16,000) the cursor moves forward
until what is left fits, taken from the end, which is also what catches a
hooked menu or a line repeating in a storm without needing to know what the
weird thing was. **The budget is settled on the text that will actually be
handed over**, not on the event stream's own count of it: the stream counts the
line with the speaker's name stripped off and the record keeps the name, and
over 690 lines that difference was 3,177 characters -- the first run went out
at 19,177 against a ceiling of 16,000.

*And a floor.* Fewer than `eroge.min_new_lines` (20) new read lines and the
last account stands rather than a call being made.

**The raw lines are never stored.** They go into one call and are dropped: not
into the save, not into a log, not into the thing she knows by name. Only the
account reaches her. The account's own instruction is the content gate and
there is no other (`prompts/eroge_digest.txt`): an explicit stretch comes out
as one clause naming it as an intimate scene and nothing further, which is the
same compression the module applies to everything, applied where the
compression happens to be total. A filter was considered and rejected -- there
is nothing in this project to copy one from, and three signed decisions say
adult material is passed through as it is (§5 `torrent_monitor.py`).

The game itself becomes a thing she knows by name (§12.2 `known.py`) the first
time she sees it: the card, under the title, the developer and all 25 to 64 of
the cast's names and readings, so a mention of one of them weeks later brings
the card back pinned and free. The account is a pinned situation line while he
is in the game, through each program's own words table, and at the compile the
day's accounts become one fact about him with `source="eroge"` -- how long he
was at it, from the sittings' own bounds, and the last account of it.

Off for everybody by default. `Config.REQUIRES` assigns the section to
`sees_him: resident`, so a character who learns what he does from snapshots she
has to go and fetch cannot have it switched on by an edit to her config alone;
the wording for her is registered all the same, because a key nobody registered
would blank her whole situation block if that ever changed.

config `eroge`: `enabled`, `cache_dir`, `userconfig_dir`, `stale_minutes`,
`skip_lines_per_second`, `max_raw_chars`, `min_new_lines`, `max_chars`,
`card_max_chars`. store: kv `eroge_cursor`, `eroge_last`, `eroge_day`; the
game in `known_things`; the card itself in the machine's own store of what
has been fetched about the world (§3 `machine/retrievals.py`, kind
`vn_card`), because the same card serves both characters. checks:
`tools/eroge_test.py`, in smoke. history: §12.14

### 12.13 `cards.py` `Cards` and `embed.py` `Embeddings`: her past as cards, and search by meaning

The embedding in full, with the measured floors and who pays for the
encoding, is `docs/memory.md` §4; what the cards do in her thread is
`docs/context.md` §3.

**One card per conversation, written once, never faded.** Code decides the
episodes of a day (`Cards.segment`): his chat cut at silences of
`delivery.gap_marker_hours`, each exchange with her own people whole; then
`_coarsen` merges two exchanges in the same room within
`episodes.merge_gap_minutes` into one conversation with a pause in it, and
gathers what is still under `episodes.min_lines` (a sticker, a photo, an
unanswered line) into the day's one odds-and-ends episode. One call a day
(role `episode_cards`, `prompts/episode_cards.txt`, flash) writes a card
per episode: `shape`, three to six lines of what happened in her language;
`anchors`, one to three lines quoted from the record with who said them;
`felt`, one line. **Code checks every anchor**: a quote that is not a
substring of the episode's own text (whitespace and punctuation aside) is
dropped and counted in the log, so the only exact words her past keeps are
words that were said. Table `episodes` (date, span, room, who, shape,
anchors as JSON, felt, line count). Written from the compile
(`timeline.compile_day`, after the day is saved), by `/episodes <date>`,
and by the backfill (`Cards.backfill`: once after boot in a thread and
after every compile, the days the thread shows past verbatim that have no
cards, at most eight calls). A day compiled again replaces its cards.

**Two readers.** The thread renders the cards of every day between its
verbatim cut and `thread.max_age_hours` at their own time, in place of the
recap and gist lines (§5), with the exact lines for the last
`episodes.anchors_days` and the shape alone beyond; a day with no cards
falls back to those lines. With the cards span at thirty days and the
backfill bounded at eight days a call, a save whose cards do not reach
that far fills in over the next few boots and compiles, and rides on the
fallback until it does. Recall (§12.3) searches them by words (`Cards.search`, weighted
above a day narrative) and by meaning.

**Search by meaning** (`embed.py`): one small multilingual sentence model
(`embed.model`, multilingual-e5-small; his GPU, loaded on first use),
vectors kept in the save (table `embeddings`, keyed by kind, ref and
model, embedded on first ask and never twice). `Recall._semantic` adds the
cosine of the cue to the word scores of **five pools** -- the cards, the
compiled days, the machinery's own record of her day (`events`, §12.3), what
she knows about him and her own memories -- and a row
the words missed joins on its cosine alone. The events pool is written by the
backfill after boot beside the other two (`App._backfill_vectors`) rather than
on the loop thread, because a save with a year of them is thousands of rows and
the first encode would be paid for by his next reply. Each pool hands over the label
it gives a row, which is how a semantic hit is matched to the word hit for
the same row: a label that is not unique per row would score one row and
hide another. The cue is the moment (`recall.moment_cue`, §12.3).

**Three rules over a row that arrives on a cosine ALONE**, because six of six
such rows judged against the moments that brought them back were wrong and two
of them reached her mouth: it must share one content word with the cue
(`embed.require_shared_word`); at most `memory.max_cosine_only`,
`self_memory.max_cosine_only` or `recall.max_cosine_only` of them arrive per
call, each below the number the reader may take at all; and each row's own
mean cosine over the calibration cues is subtracted before scoring
(`embed.center_rows`), because half the cosine belongs to the row rather than
to the cue -- the most central rows of the first character's fact pool sit
0.035 above the pool mean in a band 0.07 wide, and one row was the top hit for
5 of 30 unrelated cues. The count of rows that came back sharing no word with
the moment is in the log and reads zero. `docs/memory.md` §4.

`embed.cued` is the one blend of a word score with a cosine, and the
prompt's own retrieval uses it too (`Memory.facts_for_prompt`,
`SelfMemory.for_prompt`) off the same vectors. Those two run on the loop
thread, so they read only what is stored and only if the model is already
in memory (`vectors(write=False)`, `query(load=False)`): the vectors of a
save's whole record are written once after boot on the backfill thread
(`App._backfill_vectors`, beside the cards) and every row written after
that is embedded by its writer.

A cosine under the pool's floor counts for nothing, rising to
`embed.weight` at its top. **The floor is per pool** (`embed.cos_by_pool`)
because a one-line row and a paragraph do not sit on the same scale:
measured on her cards, unrelated pairs sit at a median 0.78-0.81 and a
90th percentile near 0.83 with a true hit at 0.85-0.90, so 0.82/0.90; a
fact or one of her memories is a single sentence, which has less to be
unlike, and the same measurement over eight Japanese cues against 157
English facts and five English cues against 270 Japanese memories puts the
right answer at 0.800-0.881 and the 90th percentile of the rest at
0.745-0.806, so 0.80/0.87. At the paragraph floor half the right answers
scored nothing. The signal on one-line rows is real and thin, which is
why it is added to the word score rather than replacing it and why the
fade score still decides what a row is worth. Off (`embed.enabled`, or
the library missing) every reader searches by words alone and the log says
so once. `/episodes [backfill|<date>]`.
`tools/context_sim.py` rewinds her clock over a copy of the save under a
small target and shows the window compact, the cards written and the
probes answered. history: the cache entry and the cards entry.
