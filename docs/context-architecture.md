# Context management: what her prompt is made of, and a shape for it to grow into

A draft for his decision, and now partly built (§7 says what). **Since
then the sub-budgets it proposes -- `history_budget_tokens`,
`carried_budget_tokens`, `situation_budget_tokens`, the attention gate's
character caps, the persona's carried-block gate (since removed) over floors -- were built, measured
and removed again**: one budget, `context.target_tokens`, and the thread's
window fits itself to what is left of it (HISTORY 2026-09-04, the
one-budget entry; `sim/thread.py _window`). Read the budget passages below
as history.
The measurements are from two days of receipts (HISTORY: the cache entry and
the budget entry) and from the `[context]` meter lines of the live runs.

## 1. What is in front of her today

Every reply is one chat-completion request in three parts, in this order:

1. **The system half** (`persona/sections.py` `SYSTEM`): the bible, the
   backstory, what she has decided about herself, what people are to her,
   and the style file last. Changes about once a day. Second character:
   about 9k tokens; first: about 10k.
2. **The thread** (`sim/thread.py`): both rooms as one history, verbatim
   for the last 24 to 48 hours (the `thread.verbatim_hours` cut, on the
   nearest midnight), then one line per exchange with her people and one
   recap per day of his chat (the compile's summary), gone after seven
   days (`max_age_hours`). Second character: 163 turns, 17k tokens; first
   character: 79 turns, about 15k tokens. Append-only within a day (HISTORY: the
   cache entry), so it is a cache prefix.
3. **The final user message**: his newest message, then the `<carrying>`
   block (`CARRIED`: facts about him on a forgetting curve, her beliefs
   about him, the charged and the unsaid, his list, the notes she read,
   the cast sheets, her own memories, the diary, what she is into, her
   reflection, what she has told him, the air in Japan, a rupture or a
   spiral; 8k to 15k tokens), then the `<situation>` block (the attention
   gate's 16 to 23 lines from five buckets, her moment, the slot; 5k to
   6k tokens).

Three things are already the persistent side of the llama.cpp proposal and
are not in the prompt at all: the whole message record and every
exchange (`messages`, `cast_chat`), the compile's narrative and summary per
day (`days`), and her canon (`sim/lore.py`: 507 records reachable by name,
at most three lines a message, nothing otherwise).

**Sizes against the budget.** The budget was 128k window / 100k target /
60k history and is now doubled (256k / 200k / 120k, his call; HISTORY: the
budget entry). Both live models have a 1M window on every OpenRouter host. What
the prompts actually measure:

| call | median tokens | largest seen |
|---|---|---|
| persona, second character | 30k | 41k |
| persona, first character | 38.5k | 40k |
| cast reply, first character | 37.7k | 41.7k |
| compile (timeline) | 33k to 41k | 41k |

So nothing was ever near the old budget, and the old count cap on the
history (a count of 300 messages under `delivery`, removed with the cache work) was the
only limit that bit: the first character had 321 messages in the week, so
every new message dropped the oldest and rewrote the day recap at the head
of the thread.

**What the trim does today** (`sim/memory.py` `fit`): when the measured
total is over target it pops the oldest history turns one by one and
writes one marker line, then the diary to one entry, the notes to four,
the facts to 25. Size-driven, but message-by-message, so when it ever
fires it will rewrite the head of the thread on every call. It has not
fired on either character.

## 2. The llama.cpp proposal, and what maps

ggml-org/llama.cpp discussion #27713 ("Automatic Context Continuation /
Infinite Conversation Mode") separates the **active context** (what the
model is sent) from the **persistent history** (everything, stored
locally), compacts when the active context passes a threshold (70 to 95%
of the window) by summarising the older part into **structured memory
entries**, keeps "important information (system instructions, project
requirements, tool state, decisions)" **verbatim or referenced**, and
retrieves from the persistent side by **keyword, semantic or hybrid**
search. Parameters: reserve percentage, compaction threshold, summary
strategy, retention policy, retrieval method.

Mapped onto her:

| proposal | here, today | gap |
|---|---|---|
| persistent history, unlimited | the save: every message, exchange, day, fact | none |
| active context, threshold-compacted | the thread's curve is TIME-driven (36h), not size-driven; `fit` is size-driven but per message | compaction should be by size, at a boundary, whole units at a time |
| structured memory entries | facts (weighted, fading), her own memories (fading), cast facts, day summaries, exchange gists | the day and the exchange are one line each and cannot be reached once they leave the thread |
| important things verbatim | commitments, claims, expectations as mechanisms; nothing verbatim survives the curve | the lines that mattered should be kept as quoted anchors |
| keyword / semantic / hybrid retrieval | keyword only: token overlap on his newest message (Latin words, CJK bigrams); lore by hand-written phrases | no semantic retrieval; the cue is one message |

The proposal's own weakness is that it summarises by recency alone: what
falls off the back is what gets compressed, whatever it was. Her design
already refuses that in one place (the forgetting curve keeps a weight-5
fact in front of her for weeks and a passing detail for days) and the
right shape keeps refusing it.

## 3. What is wrong with the current shape

Not the decay. A fact that fades is not deleted; it leaves the prompt and
comes back on a cue (`facts_for_prompt`), which is what forgetting is
like, and the same rule governs her own memories. What is wrong is around
it:

1. **Her past is indexed by time only, and time is the wrong key past two
   days.** After the verbatim window a day of his chat is its summary line
   and an exchange is its gist, both placed at their time in the thread,
   and after seven days they are gone from the prompt entirely. The
   narrative the compile wrote for an evening two weeks ago is in the save and nothing
   can bring it back into a reply, however exactly he asks about that
   evening. Her canon has retrieval; her own lived days do not.
2. **The cue is too small.** Retrieval keys on his newest message alone
   (facts, self memories, the thread's recall of an exchange). Where she
   is, who she is with, what the scene is about, what she herself just
   said: none of it cues anything. And it is token overlap, so a
   paraphrase misses and a Japanese line cannot cue an English memory
   unless the gloss happens to share a bigram.
3. **Nothing verbatim survives.** A summary of the evening he first told
   her about his work is not the sentence he used. The thing a person
   keeps of a conversation is two or three lines, exact, and the rest as
   shape. The compile writes shape only.
4. **The window is a fixed clock, not a budget.** With a 200k target and a
   thread of 17k, a fixed 36 hours verbatim is far below what she could
   afford, and the number was chosen for a 128k budget she never
   approached. The cost of a longer verbatim window is now cached reads:
   a 100k prompt at the hit rate costs $0.03 on kimi-k3, at the miss rate
   $0.30.
5. **The `<carrying>` sections are all-or-nothing.** The facts section is
   the 40 highest-scoring facts whatever the moment; her diary is the last
   two nights whatever the moment. Only the situation block competes for
   room by relevance (the attention gate). The interior should compete
   the same way.

## 4. The shape proposed

Four tiers, one budget, one retrieval path. The tiers are what the model
is sent; the budget decides how much of each; retrieval decides which
lines of the lower tiers earn a place.

### 4.1 Tier 0: the standing self

The system half as it is. Changes when he edits the bible or when the
nightly self-revision moves a belief. Cached.

### 4.2 Tier 1: the verbatim window, sized by budget

The thread as it is, but the verbatim cut is **the newest whole days that
fit `history_budget_tokens`**, not a fixed number of hours. Measured with
the calibrated ratio already in `memory.tokens`. Compaction is a day at a
time, at the compile, at a midnight boundary: the oldest verbatim day
becomes its **episode cards** (4.3) and leaves the thread. So the head of
the thread rewrites at most once a day, and the cache pays one miss for
it. `verbatim_hours` becomes a floor (never less than this much verbatim)
and the budget the ceiling.

Within the window nothing changes: stamps written once, the two rooms
interleaved, the recalled exchange at the end.

### 4.3 Tier 2: episode cards (new)

One card per episode, written by the compile, never rewritten, never
faded, stored in a new table `episodes` and retrievable. An episode is a
conversation with him (bounded by silences of `delivery.gap_marker_hours`),
an exchange with her people (already a unit: `cast_chat` row), or a day
with nothing said (one card for the day). Fields:

- `when` (start and end, both clocks), `room`, `who`
- `shape`: three to six lines of what happened, in her language, from
  the compile (it already writes the day narrative; this is the same
  work at a finer grain)
- `anchors`: one to three lines **quoted verbatim** from the record, the
  ones that mattered, chosen by the compile with a stated reason; a
  promise, a thing he said about her, a thing she said she would not say
  again. This is the proposal's "important information verbatim", and
  it is the only place her past keeps exact words.
- `felt`: the gauges that moved most, from `state_log`, and the feeling's
  name (the same fields her own memories carry)
- `left`: what it changed -- a fact written, a promise opened, a meter
  moved, a question about him raised -- as references into those tables,
  so a card and the mechanism it fed cannot disagree
- `keys`: the tokeniser's words and bigrams over shape and anchors, and
  an embedding (4.5)

The thread's per-day recap lines are replaced by the cards of the days
just outside the verbatim window: the last seven days' cards ride in the
`<carrying>` block as a **recent past** section, newest last, one card
each, shape only. Older cards are retrieved (4.5). The day summary in
`days` stays as the compile's own record; the card is what she reads.

### 4.4 Tier 3: what she knows

Facts about him, cast facts, her own memories, her beliefs about him,
what she has told him: as they are, with the forgetting curve as it is.
Two changes:

- **Retrieval joins the curve.** Today a faded fact returns only on token
  overlap with his newest message. It should return on the same cue and
  the same retrieval path as the cards (4.5). The score stays the
  half-life score; the cue is what gets bigger.
- **The carried sections compete for room.** Each section keeps a floor
  (what always rides: the top facts by weight, tonight's diary entry) and
  the rest of the block is filled by retrieval score across sections, up
  to a `carried_budget_tokens`. The attention gate already does this for
  the situation block, with buckets and weights and a report line; the
  same gate over the interior is the change. This is the answer to §3.5.

### 4.5 One retrieval path, hybrid, with a real cue

One function, `recall.retrieve(cue, pools, budget)`, used by the cards,
the facts, her own memories, the thread's exchange recall and lore:

- **The cue** is the moment, not one message: his last two messages, her
  last message, the director's scene line (place, company, what is
  happening), the day's plan line from the ledger. Weighted: his newest
  message most.
- **Keyword** as today (`sim/textutil.words`: Latin words, CJK bigrams),
  which is cheap, exact and already bilingual at the character level.
- **Semantic**: a local multilingual sentence embedding (a small
  multilingual model on the GPU the reactions already use; vectors as
  blobs in the save, cosine over a few thousand rows in numpy, no
  service, no key, no second provider). This is what lets a Japanese
  line cue an English memory and a paraphrase cue an exact one.
- **Hybrid score** = the pool's own fade score x (keyword overlap +
  cosine), with lore's two refusals applied to every pool: nothing unless
  the cue names something, and a line she was just shown is not shown
  again off her own words.
- The result is labelled by source and age, the way the thread labels a
  recalled exchange ("this came back to you"), and the log line names
  what was retrieved and why, the way `[lore]` and `[attention]` do.

### 4.6 The budget, as one table

`context` keeps `max_tokens`, `target_tokens`, `history_budget_tokens`
and gains `carried_budget_tokens` and `situation_budget_tokens`. The
meter prints the four against their budgets on every persona call, as it
prints the sections now. Compaction (4.2) is the only thing that acts on
the history budget; the two gates act on theirs; the system half is what
it is. When the total is still over target after all three, that is a
config problem and the log says so; nothing trims message by message
any more.

### 4.7 What each tier costs the cache

| tier | changes | cache effect |
|---|---|---|
| system half | once a day | hit |
| verbatim window | append within a day; one compaction a day | hit up to the newest turn; one miss a day |
| carried block | every call, at the end | its own tokens only |
| situation | every call, at the end | its own tokens only |

A longer verbatim window is the one place the cost goes up linearly even
when cached: 100k of history is $0.03 a call cached on kimi-k3 and
$0.30 a call on a cold host (as on the night Together went down and Morph
served the call at 0 cached tokens, in 92 seconds). At 100
persona calls a day that is $3 against $30. The history budget is
therefore a cost dial as much as a memory one, and 60k to 120k is the
range to test in, not 200k.

## 5. What to build first

In this order, each step useful alone and each proven on a copy of the
save before it runs live:

1. **Cards from the compile.** The `episodes` table and the compile
   writing one card per episode, with anchors. Nothing reads them yet
   except `/episodes`. This is the persistent side and costs nothing in
   the prompt.
2. **The window by budget.** The verbatim cut chosen by
   `history_budget_tokens` at the compile, whole days, floor at
   `verbatim_hours`; the recent-past section of cards replaces the day
   recap lines. Then set the budget by reading the cache receipts for a
   week.
3. **The cue and the hybrid retrieval**, first for the cards (a new pool,
   nothing else changes), then the facts and her own memories moved onto
   the same function. The embedding model chosen by a bench on her own
   record: does 「浴衣のこと」 find the yukata evening's card, does his
   English question find her Japanese memory.
4. **The interior gate**: the carried sections competing under a budget,
   with the attention gate's machinery.

## 6. Decisions that are his

- Whether her past should keep **exact words** at all (4.3 anchors). It
  is the biggest change in kind: today nothing she says about a past
  evening is a quotation, and a quoted line is a stronger claim than a
  paraphrase when the record is wrong.
- The **history budget** as a cost dial (4.7): how many days verbatim is
  worth what per day.
- **Local embeddings** on his GPU, or none. The keyword half works
  without them; the cross-language half does not.
- Whether the **recent past** (the last seven days' cards) rides on every
  call or only when the cue reaches for a day.

## 7. What is built, and what changed on the way

Built on his go-ahead, proven on copies of both saves with
`tools/context_sim.py` (the clock rewound a week under a 4k history
budget, and the carried block under a 9k one) and the probes kept beside
the patch scripts in `data/retired/20260903_225842_context_stage_ab/`
(HISTORY: the cards entry and the retrieval entry). **Everything in §4 is
built except what the last two bullets name.**

- **4.2, the window by budget.** `Thread._window`: the newest whole days
  that fit the budget x `thread.fill`, floor at `verbatim_hours`, chosen
  once a day and kept in kv `thread_window`. Every cut on a midnight, no
  count cap anywhere. The head of the thread moved once a day in the
  simulation, at the compaction, and never otherwise.
- **4.3, the cards** (`sim/cards.py`), with one change from the draft: the
  cards of the days past verbatim ride **in the thread at their own time**,
  not in the carried block. A card is stable text once written, so in the
  thread it is part of the cached prefix and keeps the chronology; in the
  carried block it would be re-sent uncached on every call. The exact lines
  show for `episodes.anchors_days`, the shape alone beyond. The `left`
  field (references into the mechanisms a card fed) is not built.
- **4.5, the retrieval**, for all four pools: keyword as before, plus the
  cosine of a local multilingual embedding (`sim/embed.py`) over the cards,
  the compiled days, what she knows about him and her own memories.
  `embed.cued` is the one blend of a word score with a cosine and has four
  callers, off one vector table keyed by pool and row, so a pool is
  embedded once however many readers it has.
- **4.5's cue**, from one owner: `recall.moment_cue` is what he just
  wrote, her own last line and the scene, and it cues both the record
  search and the persona's own recall of a faded fact. The second of those
  was his newest message and nothing else.
- **4.4's retrieval half**: a faded fact and a faded memory come back on
  the cosine as well as on a shared word, and the fade score is untouched
  by it -- the cue decides what comes back, not what a row is worth.
- **4.4's interior gate**: the persona's carried-block gate (since removed) fits the carried block to
  `carried_budget_tokens` over `persona/sections.py FLOOR_LINES` -- a floor
  of item lines per named section that always rides, the rest of the line
  lists ranked by the moment and dropped from the bottom, a section not
  named riding whole. `carried_budget_tokens` and
  `situation_budget_tokens` exist; nothing trims message by message any
  more (`memory.fit` measures only) and the meter prints the four parts
  against their budgets.
- **Not built**: the situation block's own budget DECIDES nothing yet --
  it is measured and logged when over, while the attention gate still
  admits by its own character caps; the `left` field of a card; and the
  vectors of the compiled days, which are written by the first search that
  asks for them rather than by the boot backfill. The boot backfill covers
  what she knows and what she remembers; a card is embedded by
  `Cards.write` as it is written.

What Stage A and B showed that the draft had not said: **the cosine floor
is a property of the pool's row length, not of the model.** `min_cos`
0.82 was measured on cards, which are paragraphs; a fact or a memory is
one line, which has less to be unlike, so the whole range comes down and
0.82 sat above half the right answers (the honey-in-curry fact scored zero
for 「カレーに蜂蜜を入れる話」 at 0.815). Measured on both saves the one-line
pools want 0.80/0.87 (`embed.cos_by_pool`). And the persona cannot ask for
meaning at any price: it runs on the loop thread, so it reads stored
vectors only and never loads the model, the record is embedded once after
boot on the backfill thread, and a row written while she is running is
embedded by its writer.

What the simulation showed that the draft had not said: a card per
`cast_chat` exchange is far too fine for the first character (twenty-plus
a day, most a single sticker), so episodes are merged by room and the
small ones gathered; and the semantic floor has to be measured, not
guessed -- e5-small puts unrelated pairs at 0.78 to 0.83.

What the ceiling test and the compile audit showed after that (HISTORY:
the final-pass entry): **the cards were riding under no budget.** The
history budget sized the verbatim days and the cards of the days past
them were added on top, so at a small budget the thread came out larger
than the verbatim days it had replaced; `Thread._window` now counts the
rendered cards of the days past the cut, and a day moved into verbatim
costs its record and saves its cards. **The window recomputes when the
budget changes**, not only at her midnight, so a config edit takes effect
at the restart. **What cannot shrink** sets the floor of the whole: the
system half (about 11k tokens for the first character, 10k for the
second), the carried floors (8k and 6k), the verbatim floor of
`thread.verbatim_hours` with its cards (18k for both), and the situation
-- about 40k each, so a ceiling under that is a permanent fault state,
not a test. The live test ceiling is 64k (target 64000, history 29000,
carried 16000, situation 8000), which cuts the first character to about
four and a half days verbatim with cards for the rest and drops nothing
from either carried block. The ceiling is not a cost lever: across 36k to
200k the day's spend moves by under a dollar, because the expensive part
is the carried block and the situation re-sent uncached every call. And
two card faults: a card's language is `character.writes_to_him`, not the
instruction arm (the second character's past had been handed back to her
in English), and a day compiled again replaces its cards, memories and
claims rather than appending them.

## 8. The design, stated for another project

Everything above is tied to this project's modules. This is the same
design with the names taken out, for an agent building it elsewhere. The
tests at the end are what proved it here; build them first.

**Invariants.**

1. The provider caches the longest identical byte prefix of a request.
   Therefore: a byte that changes early costs everything behind it, and
   the request is ordered stable-first: the standing self (changes daily
   or less), then the conversation history (append-only within a day),
   then everything that moves during a day (the carried block), then the
   moment (the situation), then the newest message. Nothing may rewrite
   an old message's bytes: timestamps are written once and absolute,
   never "a day ago"; labels never age.
2. Every cut of the history sits on a day boundary of the character's
   clock, so the head of the history moves at most once a day. Never
   round to the nearest boundary (it moves at noon), never cap by count
   (each new message shifts the head), never trim message by message.
3. Compaction is size-driven, whole units at a time, once a day: the
   verbatim window is the newest whole days that fit the history budget
   times a fill share, never fewer than a configured floor of hours, and
   the days past it are represented by their cards. The rendered cards
   count toward the same budget. The window is chosen once per day and
   stored; it is recomputed when the budget itself changes.
4. A card is one per conversation, written once by the nightly compile,
   never faded, never rewritten (a recompiled day replaces its cards):
   `shape` (three to six lines in the character's language), `anchors`
   (one to three lines quoted verbatim with the speaker, each verified by
   code as a substring of the conversation's text after whitespace and
   punctuation are stripped, dropped otherwise), `felt` (one line), the
   span, the room, the line count. Code decides the episodes: the chat
   with the user cut at silences; each exchange with other people whole;
   same-room exchanges within two hours merged; anything under three lines
   gathered into one odds-and-ends card for the day. The history renders
   a card at its own time, with the quotes for the most recent few days
   and the shape alone beyond, and falls back to the day's summary line
   when a day has no card.
5. Retrieval is one function over every pool (cards, compiled days, facts,
   the character's own memories): word overlap (Latin words, CJK character
   bigrams) plus the cosine of a local multilingual sentence embedding,
   with vectors stored per pool and row and written when the row is
   written, so nothing is embedded twice and the reply path never loads
   the model. The cue is the moment, not the newest message alone: the
   user's last messages, the character's last line, the scene. The cosine
   floor is measured per pool, not guessed: on multilingual-e5-small,
   unrelated paragraph pairs sit at 0.78 to 0.83 and one-line rows lower,
   a true hit 0.85 to 0.90 for paragraphs and 0.80 to 0.88 for lines;
   the score is zero under the floor and rises to a weight at a top that
   is what a right answer scores. A row the words missed joins on its
   cosine alone. The fade score of a row is untouched by retrieval: the
   cue decides what comes back, not what a row is worth.
6. Four budgets, one meter: history, carried, situation, and a target for
   the whole. Each carried section keeps a floor of lines that always
   ride; the rest compete on retrieval score against the moment and drop
   from the bottom until the block fits. The meter prints the four parts
   against their budgets on every call, and a total still over target is
   logged as a config fault, never trimmed silently. Measure the floors
   (system half, carried floors, verbatim floor with cards, pinned
   situation lines) before choosing a ceiling; a ceiling under their sum
   is a permanent fault state.
7. What a process holds only in memory dies with it, and a forced stop
   runs no shutdown hook. Persist the chosen window, the counters and the
   card index at the moment they change, not on exit.

**Build order.** Prefix stability first (ordering, absolute stamps,
day-aligned cuts), measured by diffing consecutive requests; then cards
from the compile with the substring check; then the window by budget with
cards counted; then embeddings and the one retrieval function with the
floors measured on the project's own rows; then the carried gate. Each
step is useful alone.

**Tests that proved it here.** (a) A rewind simulation: build the system
on a copy of the record, pin the clock to a past date, hide everything
after it, step forward in hours, at each step build the request as a
reply would and diff it against the previous build; report the index of
the first differing message, and fail if the head changes more than once
a day. Run it under a small history budget so the compaction is seen.
(b) A cosine probe: a set of cues in both languages against the pools,
printing the median, the 90th percentile and the top hits, to set the
floors. (c) A build-twice test: build, mutate the persisted state, drop
the object, build again on the same file, assert it survived. (d) A
before-and-after dump of every prompt section at the live budget: nothing
dropped and every section byte-identical when the ceiling is not reached.
