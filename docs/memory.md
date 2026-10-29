# Memory: what she keeps, how it fades, and how it comes back

Spec of record for what a character remembers and how it reaches her
prompt: the five stores, the forgetting curve, the moment as one cue,
search by meaning off a local embedding, and which retrieval lands in
which part of the prompt. The prompt's own shape, the thread and the one
budget are `docs/context.md`; this is what fills it. Summary and
pointers: PROJECT.md §12.2 (facts), §7.8 (her own memories), §12.3
(recall and the diary), §12.11 (what she happens to know), §12.13 (the
cards and the embedding). Dated notes: HISTORY.md.

Query the live store before reporting on any of this. `/memory`,
`/self`, `/recalls`, `/known`, `/lookups` and `/episodes` each print what
is actually held.

## 1. The five stores

| what | where | written by | fades |
|---|---|---|---|
| facts about him | table `user_facts` | the nightly compile, `Memory.add_fact` | yes |
| facts about the people around her | table `cast_facts` | the compile, `Memory.add_cast_fact` | by age band |
| her own memories | table `self_memories` | the compile, the moment writer, and the seed of her own archive (§7a) | yes, except the standing ones |
| her past as cards | table `episodes` | the compile, `Cards.backfill` | never rewritten, ages out of the thread |
| things she looked up or watched | kv `known_things` | the lookup, the watching module, the visual-novel reader | no, capped |

**What was fetched about the world is in none of them.** A page about an
episode of a television programme, that page condensed, the verdict between
two candidate pages, a web search, a game's database card: those are the same
for anybody who looks, so they live in the machine's one store
(`machine/retrievals.py`, `sensors.retrievals_db`), which both characters read
and write and which pays for a fetch once. What she MADE of one -- that she
was told it, when, and what she took from it -- is memory, it fades, and it is
in the stores above.

A sixth, `sim/lore.py`, is what she happens to know from her own record:
off for the first character and on for the other three, whose source
material is a real archive read out by hand (1,664 claims over 346 radio
records for the second, 578 reachable claims for the third, 111 for the
fourth). It is retrieved by hand-written phrases rather than by score,
because overlap with conversational Japanese is mostly grammar and grammar
collides with any sentence. The store above and this one overlap on
purpose for a character whose archive holds both dated events and quoted
moments; §7a is which of the two carries what, and where each lands.

**What is not memory.** Her diary is hers, written, gated on the unsaid
outlet. A self-claim is a thing she has told him and must stay consistent
with. Her beliefs about him and about herself are their own stores. Those
are all in the carrying block beside the memories and are not part of
this system.

## 2. The forgetting curve

A fact carries a **weight** for how much the thing would stick: a passing
detail 1, a habit 3, his birthday or his work 5. Its score decays on a
half-life that grows with the weight, and the two stores use different
scales, because a fact about someone else is information and her own life
is not:

    facts about him       half-lives   5   14   35  120   400 days
    her own memories                  14   45  120  400  1200 days

A row is in front of her while its score is above the fade line
(`memory.fact_min_score`, `self_memory.min_score`, both 0.5). Below it
the row is **not deleted**, it is just not in front of her until
something cues it, which is what forgetting is like. A near-duplicate
reinforces the row it duplicates rather than adding a second
(`duplicate_jaccard`, 0.5): the row's `last_seen` is bumped, its mention
count raised and the higher of the two weights kept. The overlap is
measured over both of a row's language keys at once, which makes the test
strict in two ways worth knowing. The same event written in genuinely
different words is a new row -- the closest pairs already in the first
character's save sit at 0.44 to 0.49, just under the line, and two of them
are the same broken promise said twice. And a memory whose second-language
rendering failed cannot reach the line against a row that has one, because
the union then carries the other language's tokens on one side only. The
first is why the compile is shown what she already carries (§7): the model
not writing the duplicate is more reliable than the test catching it.
Anything that comes back on a cue has its
last-seen stamp bumped and its mention count raised, so a thing she keeps
meeting keeps standing.

**Her own memories have two extra rules.** A memory whose source is the
seeding of her biography is *standing*: it is part of who she is, its
score is its weight for good, and it never fades. None of it fades, so
something other than the fade line has to choose which of it rides:
anything at the top of the scale is in every prompt, and the remaining
slots walk the rest in weight order, one step a character day, so the
whole biography comes round instead of the same few lines standing there
for ever (`self_memory.standing_in_prompt`; 8 on the first character, 0
on the second). And retrieval is **mood congruent**: a memory whose
valence matches the mood she is in scores higher
(`mood_congruent`, `congruence_weight`, `congruence_floor`). People do
not retrieve evenly, feeling low surfaces the low ones, and it is keyed
on mood rather than on the feeling of the minute because a mood is what
colours retrieval.

The cast sheet ages the same way in bands rather than by score: a
friend's situation from `memory.cast_age_days` ago is given "as of" then,
and past `cast_forget_days` she has lost track of it.

## 3. The cue is the moment, from one owner

`sim/recall.py moment_cue` builds one cue text: **what he just wrote, her
own last line, and the scene she is in** (where, with whom, what is
happening). Every retrieval asks with it, because the deliberate search
of the record and her prompt's own recall of a faded fact are the same
question asked twice. It used to be his newest message alone, so where
she was, who she was with and what she had just said cued nothing.

The cue decides WHICH rows come back and nothing else. A recalled fact is
still worth its half-life score, so cueing a thing does not make it
important, and an empty cue retrieves nothing at all.

Words are matched with one tokeniser for both languages
(`sim/textutil.words`: Latin words of four characters or more, CJK
bigrams). A maximal run of kana and kanji is a whole clause, so bigrams
are what make a Japanese line reachable by anything, including a nearly
identical Japanese line.

**A cue in one script, a record in the other.** He types "yani neko" and
her record says ヤニねこ; the two share no token at all, so a word search
over them comes back empty however good it is. `sim/recall.cross_script`
widens the cue with the other script's words for the titles it names,
before anything is matched, from three local sources in that order and
with no fetch (this runs on the loop thread): a thing she knows by name
(kv `known_things`), whose name list carries the romaji and the Japanese
spelling of one work; his own list (`AnimeKB.entries`), which pairs the
title he calls it with the English one; and, where neither holds the pair,
the kana the romaji itself transliterates to (`sim/recall.kana_forms`,
both scripts, strict -- every letter has to belong to a syllable, so
"neko" converts and "smoking" does not). That is what lets "yani neko"
reach ヤニねこ, on ヤニ and ねこ.

**What it cannot do, plainly.** A DESCRIPTION is not a spelling. Nothing
in this machine maps "the smoking cat anime" to ヤニねこ -- his list does
not hold the title, no page she has read holds it, and there is no
dictionary here that would -- so that cue reaches the row on nothing, and
the honest answer is that she does not know. The transliteration also
brings noise: やに is inside あやに ("to Aya"), so two cast-chat rows come
back with the real one, at a quarter of its score. `recall.cross_script`
false turns the whole widening off.

## 4. Search by meaning

Words are exact and cheap and cannot see that 「浴衣のこと」 and "the yukata
evening" are the same thing. `sim/embed.py` adds a cosine to the word
score of every pool whose rows have a stable identity to embed.

- **One small multilingual sentence model** (`embed.model`,
  multilingual-e5-small) on his GPU, loaded on first use, with the query
  and passage prefixes the model expects and normalised vectors, so a
  cosine is a dot product.
- **Vectors live in the save**, table `embeddings`, keyed by the pool,
  the row and the model, embedded once and never twice. A pool nobody has
  asked about costs nothing. A recompiled day's rows are forgotten so
  they are embedded again.
- **A cosine is a score, not a verdict**, and the floor under which it
  counts for nothing is **measured on the save it is used on**, once per
  boot, per pool (`sim/embed._calibrate`). Each pool takes a sample of
  real cues out of this save's record, scores them against a sample of
  its own stored vectors, and sets its floor `embed.calibrate_margin`
  above the `calibrate_pct`th percentile (90) of that distribution; the
  full-weight point moves with it, keeping the band width the config
  gives the pool. `embed.min_cos` (0.82), `top_cos` (0.90) and the lower
  pair a one-line pool has of its own (`cos_by_pool`, 0.80/0.87) are the
  fallback for a pool with too few rows to measure, and `embed.calibrate`
  false puts everything back on them.
- **One floor does not fit two saves.** A Japanese cue against Japanese
  rows sits about 0.06 higher than an English cue against English rows.
  Measured with 30 real cues per save: the fixed 0.80 left 8.8% of the
  first character's facts above the floor and **100%** of the second
  character's own memories and episode cards, so her whole pool counted
  as a hit on every cue and every deliberate search in her log read
  `selfmem 21`. The tables are in HISTORY.md under memory.
- **A pair that has to be measured the way the retrieval asks it.** The
  rows are stored with the model's passage prefix and a cue is asked with
  its query prefix; pairing stored vectors with each other reads 0.04 to
  0.08 high, by a different amount per pool, so a floor taken from that
  would switch retrieval off altogether.
- **A row the words missed joins on its cosine alone.** That is the whole
  point: a paraphrase, or a Japanese cue reaching an English fact. **Three
  rules over those rows**, because six of six such rows judged against the
  moments that brought them back were wrong and two of them reached her
  mouth (the audit is in `data/retired/20260904_seam_5/REPORT.md`):
  - **one shared content word** (`embed.require_shared_word`). Every wrong
    row shared no word at all with its cue -- a folder of his against a
    festival group chat, the same folder against a hair clip -- and
    requiring one would have stopped all six. It is weaker than the word
    search's own test (one Latin word of four characters for a fact, two
    keys for one of her own memories), so a row the words nearly found
    still gets in on its meaning.
  - **a cap per call**, below the number the reader may take at all:
    `memory.max_cosine_only` (2 of 4), `self_memory.max_cosine_only`
    (1 of 3), `recall.max_cosine_only` (2 of 5). A run of cosine-only rows
    used to take every slot and leave the word hit out.
  - **each row's own mean cosine subtracted** (`embed.center_rows`,
    `Embeddings.centred`). Half the cosine belongs to the row rather than
    to the cue: averaged over 30 unrelated cues the most central rows of
    the first character's fact pool sit at 0.804 against a pool mean of
    0.769, a spread of 0.035 where the whole band from floor to full
    weight is 0.07, and one row was the top hit for 5 of 30 cues that had
    nothing in common. The row's mean is measured in the same pass as the
    floor, so it costs nothing extra, and the pool's mean is added back so
    the numbers stay on the scale the floor was measured on. It cuts both
    ways by design: a row that is far from everything gains, which is
    right, and four such pairs on the first character's save clear the
    floor now that did not -- all four sharing a content word with their
    cue.
- **It can be turned off, and it is on.** Set `embed.enabled` false, or
  let the library go missing, and every reader falls back to words alone
  and says so once in the log. Both characters run with it on; the boot
  line `[embed] <model> on cuda` is how to tell.

**Who pays for the encoding.** The persona runs on the loop thread, so
its two retrievals read stored vectors only and refuse to load the model
(`vectors(write=False)`, `query(load=False)`): encoding a pool of a few
hundred rows there would be paid for by his next reply. A background pass
after boot writes the vectors of the whole record
(`App._backfill_vectors`, beside the cards), and every row written after
that is embedded by whoever wrote it. On a save with a few months of
record that pass writes a few hundred vectors and takes seconds.

**Each pool hands over the label it gives a row**, which is how a
semantic hit is matched to the word hit for the same row. A label that is
not unique per row would score one row and hide another.

## 5. Where each retrieval lands in the prompt

This is the integration. Seven retrievals run on one reply to him, an
eighth on a turn with one of her own people, and they land in three
different places (`docs/context.md` §1 for the shape).

| retrieval | asks with | lands in | how it appears |
|---|---|---|---|
| facts about him above the fade line, plus faded ones the moment cued (`Memory.facts_for_prompt`) | the moment cue | the carrying block, the facts section | plain lines, capped at `memory.max_facts` plus `max_recalled` |
| her own memories: the standing ones on their rotation, the live ones, plus any the moment cued (`SelfMemory.for_prompt`) | the moment cue | the carrying block, her own memories section | plain lines, `max_in_prompt` plus `max_recalled` |
| facts about a person, for a turn with them (`Memory.cast_facts_for`) | the last few turns of that exchange | the cast turn's prompt | `cast_facts_max` lines |
| a thing she has looked up or watched, matched by NAME (`KnownThings.recall`) | his newest message | the situation block, pinned | the whole digest, no window, free |
| what is happening in the visual novel he is reading (`Eroge.glance_lines`) | nothing -- it is made at the moment the reply is built, from the lines he has read since his last skip | the situation block, pinned | the account, while he is still in the game; the raw lines are nowhere |
| an episode he played, read up on in the background (`WatchingHim.current`) | nothing he typed: it arrives when she comes across it, which is as he plays it for a character who is on his machine and her next look at the app for one who is not (`note_seen`) | the situation block, pinned | the opener and the episode's digest, for `watching.fresh_hours` counted from that moment |
| what she happens to know (`Lore.lines`) | the naming phrase | the situation block | a few lines, `lore.max_lines` |
| a whole conversation past the verbatim cut (`Thread.build`) | the moment cue | the thread | in full, marked as having come back, before the messages being answered |
| what she remembered on cue, written by a model (`Recall`) | his message | the situation block, pinned | one line, and none at all when the thread is bringing that same conversation back in full |

Two things follow from that table. The carrying block is where the
*durable* record lands, so it changes slowly and sits after the cached
prefix. The situation block is where *this minute's* retrieval lands, so
a thing she looked up yesterday and a thing she just remembered arrive in
the same place, pinned, next to the one action line.

**One cue, answered once.** The last two rows of the table can be the same
conversation: the thread puts an exchange from past the verbatim cut back in
front of her word for word, and the deliberate search compiles one line about
the same evening into the situation block. Nothing coordinated them.
Measured on a copy of the first character's save, nine of
twelve cues taken from an exchange behind the cut had both retrievals answer
with that conversation, and in eight of the nine it was the strongest row the
paid call was given. So the situation block asks the thread what it is about
to carry (`Thread.brought_back`, which chooses exactly as `build` does
without building anything) and drops the pinned line when the strongest row
it was written from is a conversation that will be above it in full
(`Recall.already_in_thread`); the memory is still kept in kv `recalls` and
the continuity editor is still told she remembers it. The question runs one
way only. The thread's own choice is made from the cue and its window and
never from what the search found, because the head of the thread is the
provider's cache prefix and a byte of it that moved with somebody else's
retrieval would be charged for everything behind it. The search itself cannot
do the skipping today: it runs in a thread during her read delay, before the
thread for that reply exists, and it is handed no `Thread` to ask.

## 6. Recall: the deliberate search

When his message points at the past beyond the verbatim window
(`recall.trigger_regex`: "remember when", "last time", "you said", a
date, a name) or simply names something only the compiled days hold, she
goes looking the way a person does. `Recall.start` runs in a thread
during her read delay, like a lookup, so nothing blocks.

It searches, by words, with no model call: the compiled days, the
messages, **the machinery's own record of her day (`events`)**, her talks
with the people around her (matched on the one English gist each exchange
carries, quoted back in what was actually said), what she knows about him
through that pool's own row list, her own memories, and her cards. Then
the meaning pass adds the cosine over five pools: the cards, the compiled
days, the events, what she knows about him, and her own memories. The best
`recall.max_excerpts` go to one `recall` role call that writes what she
actually remembers, with the clarity it deserves: a day from last week is
clear, a day from three months ago comes back in outline. `take()` hands
it to one reply.

**Why the events are in it.** Some things are in no other store. The one
row in the first character's save that holds the title of the anime she
met on her timeline -- and had an opinion about -- is an
event, and nothing retrieved it: when he asked about that anime sixteen
days later the search read past the only row that knew, and the role
invented an exchange instead (the trace is
`data/retired/20260906_1831_yanineko_check/REPORT.md`). Events are
filtered by salience (`recall.events_min_salience`, 2: a passing line
about a train is not a thing anybody goes looking for), bounded by
`events_scan` (1,200 rows, newest first, which also bounds the vector
pool), and they fade like the rest: an event's score is
`recall.events_weight` decayed on **her own life's half-lives**
(`self_memory.half_life_days`, by salience) rather than on the shorter
scale a fact about somebody else fades on, because a thing that happened
to her is not information about a third party. `events_min_salience` or
`events_scan` at 0 takes the whole pool out (`Recall.events_wanted`, the
one owner of both numbers, asked by the word search, the meaning search
and the vector backfill).

**What the answer has to cite, and what code checks.** Every excerpt is
handed over with a number, and the role must name the one its memory comes
from (`from` in its JSON). Code verifies two things and writes nothing
when either fails, logging `[recall] not grounded: <what it wrote>` with
the reason:

- the citation has to be one of the excerpts it was actually shown -- a
  number in the list, or a date or row id that appears in one of their
  labels;
- a memory that says one of them SAID something has to be about a thing
  the excerpts hold. The subject is the words of his message that are
  distinctive over her record (a word in more than
  `recall.subject_common_share` of the rows is grammar and names
  nothing); the test applies only when the memory takes one of those words
  up, and then that word has to appear in an excerpt.

Measured over the fifty-two recalls in the first character's save (the
day and the table are in HISTORY.md under memory), eight would not have
been written, and read one by one, six of
the eight say again as a remembered thing what he had typed that same
minute -- "he told me once that I should dry my hair before I catch a
cold" against his own message saying it, "Miku... that's the name he used
for me once" against his line about somebody else reminding him of Miku.
The other two are memories whose substance is real and whose opening
echoes his new phrase; losing a hazy line is the price of not storing an
invention, and every drop is in the log. `recall.require_grounding` false
puts it back.

**Where it starts looking is the thread's own verbatim cut**, read off kv
`thread_window` (`Recall._verbatim_from`) rather than being a number of
its own. What this search is for is the record that is NOT already in
front of her word for word, and the thread's span is not a constant: it
shrinks a whole day at a time toward `thread.verbatim_min_hours` when the
verbatim days plus the cards do not fit the one budget (`docs/context.md`
§3). Reading the cut is what keeps the two from drifting -- when the span
shrinks recall reaches further in, and when it is a week recall starts a
week back. The boundary covers the messages, the compiled days, her talks
and her cards alike, and the meaning pass over the same pools, so a day
inside the span cannot come back as its narrative or as one of its cards
while every message of it is on the screen. An empty window falls back to
`thread.verbatim_hours`; one left behind on an earlier day is clamped to
that same span. What she knows about him and her own memories are not
windowed at all: they are the durable record and are not in the thread.
It used to have a boundary of its own: a second setting of 168 hours
under the delivery section, agreeing with the thread's by coincidence,
moving with nothing, and covering the messages only. That key had no other
reader and is gone (HISTORY, the entry on where the deliberate search
stops).

The same search with no model behind it (`older_messages`) serves the
continuity checker, which is shown only the last few messages and needs
the older ones a draft reaches for before it can tell a memory from an
invention.

## 7. Writing: who writes what, and when

The nightly compile (`sim/timeline.py`) is the main writer. It is asked
for new facts about him, new facts about the people around her, and the
few things from the day she herself would still be carrying, each with a
weight and a word for how it sits. It was once told that most days have
none, and obliged nine days running, leaving 118 facts about him against
three about her whole family; it is now handed what she already knows
about the people around her and told that a day teaching her nothing
about anybody is the exception.

**It is shown what is already in all three stores, her own included.** The
facts about him and what she knows about the people around her were handed
to it from the start; her own memories were the one store it wrote into
blind, so a running theme got a fresh row a night instead of reinforcing
the row it repeats. It now gets the last fourteen things she is carrying
(`SelfMemory.recent_report`: the lived ones, in the language she reads,
with their weights and how often each has come back) under a heading
saying they exist and that a day which is one more day of the same thing
says nothing new about it. The day being redone is left out of that list,
because the compile drops its own memories of that date a moment later
(`forget_day`) and would otherwise be told not to write the rows it is
about to lose. A memory that does repeat one she has reinforces it and the
compile says so in the log; it used to count the new ones only, so a
reinforcement read as a memory thrown away.

Her own memories are also written during the day when something moves far
enough (`self_memory.moment_min_delta`, `moment_min_total`,
`moment_max_per_day`).

**What she reads has to be in her own language.** Every mechanism that
keeps a memory writes English. The door where they all arrive is the one
place to fix that, so a memory in the language she does not write is
turned at the door: the model is already asked for the same line in the
other language as a second search key, and the two change places. A row
still in the wrong language is skipped rather than shown, and the repair
pass at each compile clears them.

**Which evening a row came out of.** One evening can leave her a memory of
her own, a fact about the friend who was there and a card: three rows that
can all land in one prompt with nothing to say they are one thing. Every row
now keeps the mechanism that wrote it (`source`) and the day it is about
(`date`) -- the facts had neither, and the hour a fact was written is the hour
the compile ran and not the hour of the thing -- and a nullable `card_id` for
the one conversation it came out of. The card writer fills that in: when a
day's cards are written, and again on the pass that follows every boot and
every compile (`Cards.link_day`, `Cards.relink`, `/episodes relink`), each row
of that date that was written in the moment and has no card yet is given the
conversation its own timestamp sits inside.

It is deliberately strict, because a wrong link would be read later as
evidence. Only a row whose writer says which side of her life it came from is
placed at all -- writing to him, or talking to one of her own people; the
odds-and-ends card never answers, because its span runs from the first stray
line of the day to the last and containment proves nothing about it; and of
the cards left the shortest span wins. Anything concluded later -- the compile
telling a whole day, a promise settled, a goal given up, a spiral ending -- is
placed nowhere and keeps its writer and its date instead. Measured on a copy
of the first character's save: 13 of the 41 rows of the last fourteen days
that were written in the moment, and none of the 73 the compile wrote about
whole days. `/episodes fed [date]` and `Cards.report` show what each card left
in her record. This is lineage and nothing else: no row is dropped, merged,
scored or retrieved differently for having one.

## 7a. The seed: a character read out of a real archive

`sim/seed_memories.py`. A character built by reading a real archive
(`docs/character-method.md`) arrives with two files of her own life, and
they are not the same kind of thing:

- **the dated once-events** -- a trip, an illness, an audition, a move, a
  purchase -- each with the day or the span the archive supports and the
  episode and cue index it was said at. `character.timeline_file`.
- **the quoted moments** -- her own verbatim lines. `lore.memory_file`,
  named to the seeder as `character.memories_file`.

**The seed writes the first and never the second.** A line off the archive
is her record, found when a message names it and silent otherwise, which is
his decision and the reason the moments are a retrieval file
(`sim/lore.py._memories`). The once-events reached her through nothing at
all before this: not a word of his, not the cosine, not the deliberate
search. So they go into `self_memories` and are reachable by all three.

**The overlap is recorded, not removed.** The seeder reads the moments file
to see which of its rows is the same moment of tape as a timeline event,
matched on the episode and cue index within three (the extraction's own
drift class: a receipt one to three cues high, always in that direction).
Where both files hold an event the timeline row is the one written, because
it is the one with the dated receipt, and the moments row it duplicates is
named on that row's `receipt`. The moments file is not edited: the row stays
in the retrieval, which is where he put it.

**The row.** `text` is the archive's Japanese and `alt` its English reading,
which are exactly the store's two search keys, so no model is asked
anything. `weight` is the middle of the scale for every row, and `feeling`
and `valence` are empty, for one reason: nothing in a once-event judges what
losing it would cost her or how it sat, and a wrong value in either is worse
than none. `source` is the seed's word, so the row never fades
(`STANDING_SOURCES`). `receipt` is the event's stable id, the basis its date
rests on, every episode and cue index the claim was found at, and the
moments row it covers; no prompt reads it, and its first field is what makes
running the seed twice add nothing.

**The date and the felt age are different columns and the difference is the
point.** `date` is what the archive gives: a day she stated, the broadcast
day it bounds a thing by, or -- for most of them -- the span itself, written
`1994-04-01..1996-03-31`. Nothing between those bounds is asserted, so no
day inside them is invented, and `SelfMemory.prompt_text` shows a month and
a day only when the value is a plain calendar day. `ts` and `last_seen` are
an ordering device: the last event of the archive is fixed at the day before
the save's first day, so her remembered life ends where her lived record
begins, and the rest runs back at its true distance. A life keeps its real
intervals that way -- a childhood memory sits as far back as a childhood
memory should -- and a bounded event uses the middle of its span, which is
why that arithmetic is in this column and not in `date`.

**When it runs.** Once, from the program that runs her
(`resident/app.py:build`), when her config names a timeline and either the
table is empty or the kv marker `selfmem_seed` is behind `SEED_VERSION`.
Insert-only on the stable id, so a re-run adds nothing and never touches a
row's mention count or its last-seen stamp. It builds the vectors of the
rows it wrote before it returns, so her past is reachable by meaning on the
first reply rather than after the pass that follows boot, and logs one line:
`[memory] seeded N memories from her timeline (M dated, K bounded), N of
them indexed by meaning`. A named file that is not on disk is a wrong path
rather than an absent one: it logs, writes nothing and writes no marker, so
the next boot tries again. A character with no such file is silent.

**Where the two routes land, and what stops one event being told twice.**
The retrieval puts a named record in the situation block; the store puts the
standing rows in the carrying block on their rotation
(`self_memory.standing_in_prompt`) and hands the deliberate search the whole
pool. `SelfMemory.search_items` withholds standing rows from the search when
`standing_in_prompt` is 0 -- the retrieval is serving them then, and serving
them twice is the same line twice. Above 0 that guard does not fire, which
is the price of the store's route existing at all: a search by meaning over
her own past needs the rows in the pool. So for a character with both files
and a rotation switched on, an event told in both can appear once as a
retrieved record and once as a memory. Nothing in the code prevents it
today. The blunt instrument is her `status` field in the moments file, which
`sim/lore.py` already honours; the cost of using it is her measured
retrieval, so it is his call and not a patch on the way past.

## 8. Config

`memory.*`: `half_life_days`, `fact_min_score`, `max_facts`,
`max_recalled`, `max_cosine_only`, `duplicate_jaccard`, `cast_facts_max`, `cast_age_days`,
`cast_forget_days`.
`self_memory.*`: `half_life_days`, `min_score`, `max_in_prompt`,
`max_recalled`, `max_cosine_only`, `standing_in_prompt`, `duplicate_jaccard`, `max_per_day`,
`compile_max_per_day`, the moment thresholds, `mood_congruent`,
`congruence_weight`, `congruence_floor`.
`embed.*`: `enabled`, `model`, `batch_size`, `min_cos`, `top_cos`,
`cos_by_pool`, `weight`, `calibrate`, `calibrate_pct`,
`calibrate_margin`, `calibrate_sample`, `calibrate_cues`,
`calibrate_min_rows`, `calibrate_min_cues`, `center_rows`,
`require_shared_word`.
`recall.*`: `enabled`, `trigger_regex`, `min_score_without_cue`,
`max_excerpts`, `max_cosine_only`, `max_per_day`, `wait_seconds`, `keep`,
`events_min_salience`, `events_scan`, `events_weight`, `cross_script`,
`require_grounding`, `subject_common_share`.
`character.timeline_file` and `character.memories_file` are the two files the
seed reads (§7a), empty for a character with no archive of her own.
`episodes.*` and `lore.*` are in their own entries; the cards' side is
`docs/context.md` §3.

## 9. Store and log

Tables `user_facts`, `cast_facts`, `self_memories`, `episodes`,
`embeddings`, and `events` read (never written) by the deliberate search
through `Store.salient_events`. kv `known_things`, `recalls` (each row
carrying `cited`, the excerpt the answer named), `diary`. The three stores each
carry `source` (the mechanism that wrote the row), `date` (the day it is
about) and `card_id` (the conversation it came out of, usually null).
`self_memories` also carries `receipt`, filled only on a row written in from
a character's own archive (§7a), and kv `selfmem_seed` records that the seed
has run and at which version.

Log lines worth reading:

- `[memory] N faded fact(s) came back on a cue (k by meaning, no shared
  word)` and `[self] N thing(s) of her own came back on a cue (...)`.
  Read WHAT came back, not how much: the count by meaning is the cosine's
  own claim and the only way to see whether it is working.
- `[recall] meaning: N row(s) scored above the floor (fact 2, episode 1)`
  on a deliberate search.
- `[recall] cross-script: N form(s) added to the cue (...)`, and what it
  crossed from: a thing she knows by name, a title on his list, or the
  kana of the romaji itself when nothing here holds the pair.
- `[recall] not grounded: <what the model wrote> -- <the reason>`. A
  memory that was not written. Read the reason: "it cites no excerpt at
  all" is the role ignoring its schema, and "it says one of them said
  something about <word>, which is in none of the excerpts" is the fault
  this exists for.
- `[embed] <model> on cuda` once at first use, `[embed] N <pool>
  vector(s) written` when a pool grows, `[embed] N row(s) of what she
  knows and what she remembers can be reached by meaning` once after
  boot. `[embed] off: ...` means every reader is on words alone.
- `[embed] <pool>: floor 0.80 -> 0.866, full weight 0.87 -> 0.936 (90th
  percentile of 28 cue(s) against 21 row(s), median 0.837)` once per pool
  per boot: the floor this save measured for itself. A pool with no such
  line had too few rows or too few cues and is on the configured floor.
- `[known] kept <key> (<kind>): N name(s), M chars` when a thing she
  looked up is kept by name.
- `[recall] the exchange itself is coming back into the thread in full; the
  line she remembered is not restated in the situation` when one cue was
  about to be answered twice.
- `[episodes] <date>: N row(s) of what she keeps now name the conversation
  they came from` when a day's cards are written, and the same count over M
  carded days on the pass after a boot or a compile.

## 10. Tells

- **Nothing ever comes back by meaning.** Either the model never loaded,
  the backfill never ran, or the floor is above what this model scores
  for a true hit. The boot line says how many rows can be reached and
  `/episodes` prints the vector count per pool and the floor each one
  measured for itself.
- **The same count comes back every time**, and it is round -- the size of
  the pool. The floor is under the whole pool, so the cosine is a
  constant and not a score. That is the state the second character's own
  memories were in before the floor was measured per save.
- **A fact comes back that has nothing to do with the moment.** The cue
  is too wide, or a pool's label is not unique per row.
- **She cannot reach a thing she plainly knows about her own family.** The
  name resolution through the roster is the thing to check: the store is
  keyed by the roster handle and the record names people in Japanese.
- **Her own memories crowd out the days she has lived**, or the reverse.
  The two kinds have separate slots for exactly this reason.
- **An English line in her head** for a character who writes Japanese: the
  repair pass has not run, or a new writer bypassed the door.

## 11. Tests

`tools/smoke.py` builds every reader against a copy of the save and calls
every report. `tools/expect_test.py`, `tools/family_test.py` and
`tools/character_test.py` cover the fact stores from their own angles.
`tools/context_sim.py` rewinds her clock over a copy and answers probe
cues, which is the one way to watch retrieval work over days rather than
in one call. `tools/seed_memories.py` says what the seed of a character's
own archive is made of and rehearses it against a copy of a save; it
refuses a save named in `characters.json`, because a character's own
process does that at boot and nothing needs doing to her by hand.
