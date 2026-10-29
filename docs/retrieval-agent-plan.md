<!-- doc: reference -->

> **2026-09-07: what the second reader carries is no longer her whole
> prompt.** This document designed it to read the same context she is
> about to be given, byte for byte, with "YOU ARE NOT HER" appended --
> and that is the arrangement a judge reads as its own identity. His
> ruling: it must not carry her Bible; it can carry the situation block
> only. Its system prompt is its own instruction file through
> `Config.role_system` with a `judge` row, and its user message opens on
> `Persona.judge_situation` -- never the carrying block, never the bible,
> her backstory, her self-beliefs, her sentiments or her style guide. Its
> `attend` is a verbatim pick of one of the lines it was offered rather
> than a sentence it composes. Everything below about the gate, the
> candidates and the shadow mode still describes what runs; the context
> it reads does not. `HISTORY.md`, the entries of 2026-09-07.
# A retrieval agent over the situation block: what exists, what one would be, and whether to build it

**Status, 2026-09-04: the four code fixes in §5 are built** (HISTORY
2026-09-04, the slot entry) -- the weight floor under the slot, the retiring
of a slot line she reads twice and answers something else, the foresight's
veto over the action it warns against, and the second reader being handed
only what the gate let through. The recommendation not to build the
retrieval agent stands, and the "smaller version" (the second reader widened
to `mode: select`, in shadow) is not built.

His question, in his words: *"i believe yukarin and tomoe are already getting
rich summaries, but what would it look like if we had a dedicated retrieval
agent instead that decides what is actually important in that moment, and what
the situation block should push on."*

This document answers it from the code and from today's receipts. It names
things that are not built; nothing in it has been implemented. The spec of
record for the prompt's shape is `docs/context.md`; for what is retrieved and
why it fades, `docs/memory.md`; the ranked table that owns the last imperative
line for the second character is `docs/stances.md`. `docs/situation.md` is the
body's spec (the map, journeys, fatigue) and is a different subject despite the
name.

The code read: `sim/attention.py` (the gate), `sim/nudge.py` (the second
reader), `sim/stances.py` (the table), `persona/persona.py` `_situation` /
`_moment` / `_her` / `_him` / `_day` / `_phone` / `_this` / `_admit` /
`_draft`.

---

## 1. What exists, measured

### 1.1 How the block is built today

`Persona._situation` builds one moment (`_moment`) and hands it to five
builders. Four of them — who she is being right now (`_her`), him (`_him`),
her day (`_day`), what is on her phone (`_phone`) — return lines tagged with a
source, a weight, a kind (`fact` or `action`) and a pin. Those four plus the
lines she happens to know (`sim/lore.py`) go through the attention gate
(`Attention.admit`). The fifth builder, the closing part (`_this`: how many
messages of his she is reading, the frame line that says what to take up
first, the write instruction, the one imperative slot, the length line), is
**appended after the gate and is never ranked by it**.

The gate does four things and no longer cuts for room (it did until
2026-09-04): it computes a weight per line (the mechanism's own number, or the
source's configured default, plus up to `attention.cue_bonus` for overlap with
his newest message); it marks a line suppressed when a heavier source already
makes the claim (`covered_by`: the day's ledger covers promises and money);
it lets a one-per-source source say its piece once; and it hands the **single
heaviest line of kind `action`** to the one imperative slot.

The slot is then filled in `_draft` by one of three things, in this order of
ownership: a stance from the ranked table if one claims it; otherwise the
nudge's reading if the nudge fires and clears `nudge.min_confidence`;
otherwise the gate's own pick, unless code judges his last message heavy and
fresh (`attention.heavy_valence`, `heavy_fresh_minutes`), in which case the
slot waits.

**Both live configs have `nudge.enabled` false today.** `stances.enabled` is
false in `config.json` and true in `config_yukarin.json`. So right now the
first character's slot is the gate's mechanical pick with no second reader at
all, and the second character's is the stance table's.

### 1.2 The four receipts

The run named in the brief (`logs/2026-09-04_12-30-*`) holds persona calls for
the second character only; the first character's run of that hour
(`logs/2026-09-04_12-30-12`) made no persona call before I read it, so her two
newest are in the run immediately before it, `logs/2026-09-04_11-46-48.zip`.

| | first character, 12:14:57 | first character, 12:28:42 | second character, 12:53:38 | first character, 11:11:55 (self-start) |
|---|---|---|---|---|
| lines offered to the gate | 28 | 27 | 21 | 29 |
| kept by the gate | 24 | 23 | 18 | 24 |
| buckets | 5 (her 3, him 4, day 9, phone 8, lore 0) | 5 (her 3, him 4, day 9, phone 7, lore 0) | 5 (her 3, him 3, day 8, phone 4, lore 0) | 5 (her 3, him 6, day 9, phone 6, lore 0) |
| dropped | commitments (covered), money (covered), anime_list (dup) | same three | rhythm (dup), commitments (covered), anime_list (dup) | nag (queued), commitments (covered), money (covered), share (queued) |
| block as rendered | 8,446 chars, 33 non-empty lines | 8,288 chars, 32 lines | 7,964 chars, 27 lines | 7,618 chars, 32 lines |
| block in tokens, of the whole prompt | 3.1k of 73.3k (4.2%) | 3.1k of 74.0k | 5.0k of 48.5k (10.3%) | 2.8k of 68.6k |
| who held the slot | the gate, source `share`, weight **0.35** | the gate, `share`, 0.35 | the stance table, `sitting_on_it` (the gate found no action: `slot: none`) | the gate, `show_him`, 0.60 |
| the nudge | did not run (disabled) | did not run | did not run | did not run |
| persona call | 75,174 prompt tokens, 0 cached, $0.01067, 10.9 s | 75,308, 0 cached, $0.01059, 11.9 s | 48,207, 48,207 cached, $0.01995, 8.9 s | 74,087, 0 cached, 6.5 s |

The rendered line count runs ahead of the gate's kept count because the day's
ledger renders as a preamble and four bullets from one gate line, and because
the closing part is appended unranked.

### 1.3 Judged by eye: what mattered, what was noise, what she should have pushed on

**The first character, one late night.** He said a show he had put on his list long ago was good and that he had binged it; she answered by asking what changed.

Of the block, four things reached that reply. The frame line in the closing
part — "he has said what he thinks about something and left it with you: ...
take THAT up first" — which is not ranked by the gate and rides on every such
turn. The line saying what came back to her on the cue, which contains "I know
you put things on your ptw and get to them years later, that's just how you
are, but the when of you telling me that is fuzzy" — her first bubble is that
line, in her own words. The manner line ("warm and open, leaning in"). And the
clock, which kept her from assuming his time of day.

Noise, on this turn: the money line (5,490 yen, allowance 26 days away), the
travel line and the route to Ikebukuro, the ledger's "bought nothing" and
"wearing: casual", his likes on the account (a stranger's car being detailed),
his five new follows, what she did on the account and why, the engagement line
(one like on a post of hers), the three photographs of her places, the flat's
feels-like temperature, and her anime list of his three part-watched shows.
Roughly fourteen of the twenty-four admitted lines had nothing to do with a
turn about why a show landed for him now and not four years ago.

**What she should have pushed on, and did not.** The block carried his anime
list — three shows stalled at partial episode counts — while he had just
described finishing one. That is precisely what the nag source is for; it was
offered three times in seven days and held the slot once. Instead the slot
carried a link to share, with three candidate posts, two of which are
unusable: a list of "things this world does not need" that names disabled
people, and a post about sex. A gate that ranks by number cannot see that, and
she declined the slot on both consecutive replies. **The same slot with the
same three posts rode two calls in a row** — the tell `docs/context.md` §10
names.

The structural fault under it: `share` won the slot at weight **0.35**, the
lowest number in the table, in a block whose heaviest admitted lines sit at
0.85. It won because the slot goes to the heaviest *action* and it was the
only action offered. There is no floor.

**The self-start, her Saturday 00:11.** No message of his; the impulse fired
(`[impulse] True (score 77) | his side: read (49 min since her last message)`)
and the intent role had already decided the message was an apology
(`[intent] make_up: sorry for snapping about the emu thing...`). The gate put
`show_him` in the slot: "something from your scroll you wanted to show him:
なんであのえむって人フォローしたの？ああいうの嫌だよ" — raise the follow she
objected to. **Six lines above it, in the same block, the foresight line
said: "what you are half braced for: pushing the emu thing again after he
already explained — he might read it as you not letting it go."** Two
mechanisms, each with its own honest number, instructing opposite things, with
no arbiter between them. She sent the intent's line and ignored the slot.

**The second character, 12:53.** He wrote, in the middle of a two-hour stretch
of her watching him work: *"2 ji kan. Are you getting bored just watching me
like this?"* The gate found no action at all and the stance table filled the
slot with the thing she had seen on his machine and not said. The first draft
took it and reused a metaphor she had already sent him twice that day; the
continuity editor refused it by name and the rewrite is the best of the four
answers I read — and **it is built out of the line I would have called the
worst noise in the block**, the 1,400-character minute-by-minute log of him
flipping between a visual novel and its translator between 12:23 and 12:43.
Her second draft names exactly that, and puts her own reading beside it.

So the honest baseline is mixed. On the first character's live back-and-forth
the mechanical pick was wrong twice in a row and wrong on the self-start. On
the second character's turn the code's pick was right, and a shorter block
would have cost her the best line she wrote today.

### 1.4 What the running tally says about the whole week

`Attention._tally` keeps offered / admitted / held-the-slot / covered per
source, per room, per day (kv `attention_tally`; read here from both live
saves through a read-only handle).

First character, her chat with him, last seven tally days, 72 replies:

- 46 of 72 slots were filled at all. **`share` held 25 of them and `show_him`
  19** — 44 of 46, both from the account module. `expectations` held one,
  `nag` one.
- Admitted on every single call: the clock, the feeling tags, the manner line,
  what she expects of him, what she has been wondering, the scene, his mood,
  the receipts, the foresight, what came back on the cue, and five more.
- Admitted almost never: the route to a place her day names, 9 offers admitted
  of 71 (13%); what she happens to know, 10 of 72 (14%); how she gets anywhere,
  12 of 72 (17%); yesterday, 12 of 72 (17%).

Second character, 140 replies over four days: the gate's slot was filled 34
times (`noticed` 29, `glance` 5); everything else was either a stance's or
empty.

**The slot is chosen from at most four candidates.** In her chat with him the
only sources that ever produce a line of kind `action` are what she expects of
him when it is unmet, the nag, a post to share and a thing to show him
(`persona.py:761`, `763`, `972`, `973`). For the second character there are
two, both from her sight of his machine (`resident/sight.py:562`). That is the
size of the decision a dedicated agent would be making.

---

## 2. The design

### 2.1 Where it sits

**After the gate, never instead of it, and never as its weight source.** The
gate's two mechanical jobs — suppressing a claim a covering source already
makes, and letting a one-per-source source speak once — are facts about the
sources, not judgements, and a model has nothing to add to them. Its weights
are the mechanisms' own numbers about their own things (how live a charged
item is, how many hours since he read, how confident a foresight is); a model
cannot produce those and should not overwrite them. What the gate does badly
is the part that is arbitrary: ordering lines from different mechanisms
against each other, and picking the slot by "highest number wins".

So:

    the mechanisms offer lines  ->  Attention.admit ranks, suppresses, picks
                                ->  the selection pass narrows and re-picks
                                ->  the block is rendered

`Attention.admit` keeps its signature and its return value. A new call in
`Persona._admit` is given the gate's result and may only narrow it.

### 2.2 What it is handed

Everything except the retrieved rows already exists. `Persona._admit` builds
`self._candidates` today for the nudge: every line of the four sections with
its source tag, a `· to do` mark on the actions, and a `*` for what the gate
kept. Four additions:

1. **An opaque id per candidate** (`h3`, `d7`), assigned in the order the
   sections are built.
2. **The gate's verdict and weight per candidate**: kept, queued (an action
   that was not the heaviest), covered, dup, pinned. **Covered and dup lines
   are not shown at all** — see §4.
3. **The moment**: his newest message(s) byte for byte, her own last line, and
   the ledger's line for where she is and with whom. This is
   `recall.moment_cue`'s three parts, which every retrieval already asks with.
4. **The retrievable rows that today land elsewhere**, each with an id, its
   source pool and its score: the facts about him above the fade line plus the
   faded ones the cue reached (`Memory.facts_for_prompt`), her own memories the
   same way (`SelfMemory.for_prompt`), the cards the cue reached, the lore
   lines, the things she has looked up. **This is the only real new plumbing.**
   Those readers return rendered text today; they would have to return rows
   with a stable label and a score. `docs/memory.md` §4 says each pool already
   hands over a label unique per row for the embedding to match on, so the
   labels exist.

Her state rides as the two lines the block already carries — the feeling tags
and the manner line — not as the gauge grid. The state role is the one place
that reads numbers and nobody is speaking to her in it.

### 2.3 The prompt's shape and its language

Two possible shapes, and the choice is the design's main fork.

**Shared-prefix** (what the nudge does today): the persona's system prompt byte
for byte, then the analyst framing appended after it, then the same thread,
then the candidate table and the ask in the final user turn. It costs the full
persona prompt — 72k tokens for the first character, 45k for the second — and
buys the cache prefix and, more importantly, the conversation. Judging "what
is she caught by" without the last twenty turns is judging blind.

**Standalone**: the moment, the candidate table, her two state lines, 4k to 6k
tokens, no cache, no conversation. Cheaper and worse at the one thing it is
for. The measured nudge cache rates say the shared prefix does not actually
buy much (below), so the argument for it is the conversation, not the money.

Take the shared prefix.

**Language.** The framing file is a mechanism prompt and carries no person:
it lives in `prompts/`, names nobody, and marks the character's place with
`{{TOKEN}}`s that `Config.fill` supplies, so `tools/neutral_gate.py` can render
it back to the original bytes. Today's `prompts/nudge.txt` is already built
this way (`[[AGE_KIND_B]]`, `[[NUDGE_EG]]`). How she sees him forks on
`[[?digest]]…[[/digest]][[?resident]]…[[/resident]]`, never on a hardcoded
phrase, so `tools/sight_words.py` passes. The framing is addressed to the
analyst and not to her, so it stays English under every instruction arm; the
candidate lines inside it are whatever language the character reads them in and
are quoted, not translated.

### 2.4 The output, and the rule that it can only select

    {"carry":      ["h1", "h4", "d2", ...],
     "slot":       "d7" | "",
     "leave_out":  [{"id": "d3", "why": "..."}, ...],
     "confidence": 0.0}

**Ids, not text.** The brief asks that every returned line be one it was
offered, byte-identical, enforced by code. Ids are the stronger form of that
rule: the code looks each id up in the offered table and uses the original
`Line` object, so there is no path by which altered bytes reach her, and no
near-miss for a matcher to adjudicate. An id that is not in the table is
dropped and logged. Nothing the model writes is ever rendered into her prompt —
not a summary, not a reason. The `why` field goes to the log and the store and
nowhere else.

This closes, structurally, the failure the current second reader has to guard
against with a regular expression: on 2026-08-31 a quoted span the nudge wrote
about her went to him in her voice word for word, which is why `sim/nudge.py`
carries `_QUOTED` and `_notes`. A selection pass that returns ids cannot do it.

The answer is asked again on a parse failure (`LLM.call_json`,
`api.json_retries`) and the caller handles `None`. It is discarded whole,
with the gate's result standing, if: it does not parse twice; `confidence` is
under `selector.min_confidence`; fewer than `selector.min_lines` of its
`carry` ids resolve; or any pinned id is missing from `carry`.

### 2.5 What it may and may not do

| | |
|---|---|
| drop an unpinned line the gate kept | yes — this is the point |
| keep a line the gate marked covered | **no**: not in the id table at all |
| keep a second line from a one-per-source source | **no**: not in the table |
| drop a pinned line | **no**: pins are in `carry` before the model is asked, and a missing pin voids the answer |
| move a queued action into the slot | **yes** — the one place the gate's rule is arbitrary |
| hold the slot empty | yes, by returning `""` |
| override a stance that holds the slot | **no** (§2.7) |
| change how much she writes | no — the shape budget is elsewhere |
| decide whether she texts first | no — the impulse is a pure function |
| add a fact, or any words | no — it returns ids |

### 2.6 One call, not two: this *is* the nudge, generalised

`sim/nudge.py` already reads the same full context she is about to be given,
already receives `self._candidates` with the gate's marks, already returns a
pick for the slot, already checks its `do_source` against the set of sources
that actually offer an action, already has a confidence floor, a live/shadow/
off mode, an agreement estimate against the gate's pick, an A/B recorder
(`nudge.compare`, kv `nudge_ab`), a store row, a log line and an ops report.
The proposal differs in three ways and no more:

1. it is asked on every reply, rather than only when the gauge for how much she
   is holding back is at or over 45 and 45 minutes have passed since it last
   fired (`nudge.fire_on_unsaid`, `unsaid_min`, `min_gap_minutes`);
2. it returns ids for the whole block, not one prose note for the slot;
3. because it returns ids, nothing it writes can reach her.

Building a second role beside it would put two models in front of one slot with
no rule for who wins. Extend `sim/nudge.py`, add `nudge.mode: "select"`, keep
the store keys and the log prefix so the history is continuous.

The gauge for how much she is holding back keeps its present job either way: it
is warmed by the count of things she carries (`Nudge.carried`) and settled when
one comes out (`Nudge.released`). Under a selection pass that runs every reply,
the release fires when the slot is filled from a carried action, not when the
call is made.

### 2.7 The stance table keeps the slot

For the second character the ranked table owns the last imperative line by an
ownership rule written in code (`persona.py:1462-1478`) rather than in config,
specifically so that a setting nobody knew was load-bearing could not take it
away. Nothing here changes that:

- where `claims_slot` is true, the selection pass is asked for `carry` only and
  its `slot` field is ignored;
- a stance that holds the slot **empty on purpose** — which is what
  "do not raise it" means — keeps it empty;
- the stance's own line is pinned and cannot be left out;
- where the table falls through to "even", the selection pass's slot rides.

`sim/stances.py` §"It owns the slot" is the sentence this must not contradict.

### 2.8 A self-start

There is no message of his, so the moment is different in kind: the impulse's
reason and, where one was decided, the intent role's line
(`[intent] make_up: ...` in the 11:11 receipt). The framing says plainly that
she is the one starting, that nothing is being answered, and that the question
is which one thing she opens with and what she carries while she does it.

Two rules that are code's, not the model's: where an intent has already been
decided upstream, it is handed over as settled and the slot may not contradict
it; and the slot may not be filled by an action whose own source is also named
by a foresight line in the same block as the thing she is braced against. That
second one is the 11:11 fault, and it is better fixed as a `covered_by` row in
the gate than by asking a model to notice — see §5.

### 2.9 Cost, latency, and what it saves

Measured on the current second reader, which is the same call in the same
place on the same thread. Twenty calls on 2026-08-30, log line
`[llm:nudge] 3.8s in=33651 out=152`:

| | |
|---|---|
| latency | median **3.80 s**, mean 3.85, min 2.78, max 5.02 |
| prompt | median **33,720** tokens (the persona prompt of that date) |
| answer | median 152 tokens |
| cached prefix | 4,480 to 26,368 tokens, median 11,968 — about a third, and unstable |

Against today's persona calls: the first character's is 75,174 tokens, **0
reported cached** (Together on that host reports none), $0.01067, 10.9 s; the
second character's is 48,207 tokens, all reported cached, $0.01995, 8.9 s.

So one selection pass per reply costs roughly **+3.8 s on the loop thread**
against a persona call of 6.5 to 11.9 s, and roughly **doubles the per-reply
spend** — order of a dollar a week for the first character at 72 replies to him
in seven days, plus her friend room.

What it saves is not money. The situation block is **3.1k tokens of 73.3k**
for the first character (4.2%) and **5.0k of 48.5k** for the second (10.3%).
Halving it saves 1.5k to 2.5k tokens; on the first character's call that is
under four hundredths of a cent, and it is billed either way because the block
sits after the cached prefix by design. The saving is attention: fewer lines
competing for the model's notice in the last eight thousand characters before
his message. That is worth something — but it has to be weighed against the
second character's 12:53 turn, where the best line of the day came out of the
longest and least relevant-looking paragraph in the block.

---

## 3. Three real turns, written out

### 3.1 Her turn with him, 2026-09-04 12:14 machine time (her Sat 01:14)

**Handed to it.** The moment: his message about the show he had on his to-watch
list for four years; her own last line ("you finished mitsudomoe. gave it an 8.
was it worth it or did you just want it over with lol"); the ledger's scene (in
bed on her phone, alone, the group chat winding down). Twenty-eight candidates
with their sources and weights, of which four actions: `share` (0.35, three
posts, two of them unusable). No — one action; `nag` had been charged that
morning and was not offered. Her two state lines: relieved, warm and close to
him, craving attention middling; warm and open, leaning in. The retrieved rows:
the recall line about his to-watch list, the facts about him that ride today,
her own memories.

**A good answer.**

    {"carry": ["<clock>", "<manner>", "<his rhythm: right here, answering
                quickly>", "<how he wrote: relaxed, pleased with himself>",
                "<the scene>", "<the recall about his to-watch list>",
                "<the ledger>", "<the anime list>"],
     "slot": "",
     "leave_out": [{"id":"<share>","why":"the two posts on offer are a bigotry
                     list and a sex post, and he has just opened a subject"},
                   {"id":"<money>","why":"nothing in this turn touches money"},
                   {"id":"<travel>","why":"she is in bed and going nowhere"},
                   {"id":"<his likes>","why":"a stranger's car"},
                   {"id":"<her account actions>","why":"not this turn"},
                   {"id":"<the photos of her places>","why":"not this turn"}],
     "confidence": 0.8}

**Against what the block carried:** twenty-four lines and a slot pushing a
link. The agent's win here is not the eight lines it keeps — she found the
right material anyway — it is the empty slot. But the empty slot is also what
a weight floor of 0.5 on the slot would have produced, in code, for nothing.

### 3.2 Her self-start, 2026-09-04 11:11 (her Sat 00:11)

**Handed to it.** No message of his. The impulse's reason (he read her last
message 49 minutes ago and has not replied) and the intent, already settled:
make up for having been short with him about the follow. Twenty-nine
candidates, three of them actions: `show_him` at 0.60 (raise the follow),
`nag`, `share`. Among the facts: "he is past when you expected him (49 min); to
you that means: 彼が黙ってるのは、私がしつこいと思ってるからだ" and "what you
are half braced for: pushing the emu thing again after he already explained —
he might read it as you not letting it go."

**A good answer.**

    {"carry": ["<clock>", "<manner>", "<the 49 minutes and what it means to
                her>", "<the foresight: braced against pushing it again>",
                "<the scene: still scrolling, not ready to put the phone
                down>", "<how he wrote: easy, content>"],
     "slot": "",
     "leave_out": [{"id":"<show_him: raise the follow>","why":"the foresight
                     line names raising it as the thing she is braced
                     against, and the intent is to make up, not to press"},
                   {"id":"<nag>","why":"not while she is apologising"},
                   {"id":"<share>","why":"same"},
                   {"id":"<the money, the route, the account, the
                     photos>","why":"a one-line apology at midnight"}],
     "confidence": 0.85}

**Against what the block carried:** the slot told her to raise the follow. She
ignored it, and the intent role — which is code deciding the message's purpose
before the persona is called — saved the turn. The agent would have got this
right. So would one `covered_by` row.

### 3.3 The second character, 2026-09-04 12:53

**Handed to it.** His message: "2 ji kan. Are you getting bored just watching me
like this?" Her own last line; the ledger (at the laptop, alone, eating an egg).
Twenty-one candidates, **no actions** — the gate reported `slot: none`. The
stance table has already claimed the slot with `sitting_on_it` over an item
unraised for 2,473 minutes, so the `slot` field would be ignored. Among the
candidates: the flat's inventory (a dead tube, glasses on the fridge, a
tea-stained fridge top, yolk on the keyboard, a breaker, the washing, the
sweets); the 1,400-character log of his last twenty minutes; what came back on
the cue, which is her being asked almost this question before and answering
that she was not bored, and the word landing like a stone; and her own repeated
phrases.

**A good answer.**

    {"carry": ["<the stance, pinned>", "<clock>", "<feeling>", "<manner>",
                "<the recall: she has been asked this before and the word is
                 heavy>", "<what his machine has been doing, in full>",
                "<what he is doing right now>", "<her goals for the day>",
                "<the household>"],
     "slot": "",                       # ignored: the stance holds it
     "leave_out": [{"id":"<the anime list>","why":"three shows he has not
                     touched in three weeks; nothing here reaches them"},
                   {"id":"<yesterday>","why":"the recall line says the same
                     thing closer to this turn"}],
     "confidence": 0.6}

**Against what the block carried:** eighteen lines and a stance in the slot.
**The gate and the table were already right**, and a selection pass would have
been justified in cutting the flat's inventory and the long telemetry
paragraph — the two things the block spent most of its characters on. Had it
cut the telemetry, her second draft could not exist: the reply that came out
after the continuity editor refused the first one is built entirely from him
flipping between the visual novel and its translator, and it is the best thing
either character wrote today. This is the case that argues hardest against the
whole idea.

---

## 4. Risks, and which the design handles

**A second reader that decides what she attends to is a second author of her.**
That is the frame, and it is right. Five specific risks:

1. **It can be wrong in a way the weights cannot.** A weight is a mechanism's
   own number about its own thing and cannot be hallucinated; a ranking can.
   *Partly handled.* It selects ids from an offered set, so it cannot invent a
   line; it returns no prose, so it cannot write a word she reads; pins and a
   minimum line count mean the worst case is a thin block, never an empty one.
   **Not handled:** it can drop the one line that mattered and nothing will say
   so. The only instrument is the A/B the second reader already has — draft with
   its block, draft again with the gate's, keep both, read them by hand
   (`nudge.compare`, kv `nudge_ab`, `/nudge ab`).

2. **It puts a model's taste between her state and her voice, which "code
   decides when, a model decides what" is meant to bound.** Read the block as
   content and the agent is choosing *what*, which is allowed. Read it as a
   gate — and it is a gate; that is the module's name — and the agent is a model
   deciding *when* a mechanism gets to speak, which is the side the rule
   reserves for code. **This proposal moves one decision across that line.**
   The design bounds the move: it never sets her length, never decides whether
   she texts first, never decides the stance, never touches the carrying block
   or the thread, and never writes. The reason to accept the move would have to
   be that the code rule it replaces — highest number wins among at most four
   actions — is demonstrably arbitrary, which §1.3 shows it is.

3. **One more call that can fail or stall on the loop thread.** *Handled.* The
   gate's result is computed first and is the return value unless a valid answer
   comes back; a bad parse is retried once by `LLM.call_json` and then
   discarded; an exception is caught and logged by type, never by text. It
   needs a `selector.timeout_seconds` cap, because the measured maximum was
   5.0 s and a stalled host would otherwise hold her reply open: past the cap
   the gate's result stands and the call goes to `missed_calls` like any other
   failed call.

4. **It can learn to always pick the same kind of thing.** *Not handled by the
   design; handled by the instrument that already exists.* `Attention._tally`
   counts offered / admitted / held-the-slot / covered per source per room per
   day and `tally_report` marks a source offered five times and admitted none
   as NEVER. Add a fifth column for what the selection pass dropped and the same
   report says whether it has quietly retired a mechanism. Worth saying that
   **the gate is doing this today**: 44 of 46 filled slots in a week went to two
   sources out of four, and four sources were admitted under a fifth of the
   times they were offered.

5. **It must not pull a line the gate suppressed as covered.** *Handled by
   construction:* covered and dup lines are never in the id table. Worth
   recording that **today's second reader does not handle it** —
   `Persona._admit` builds `self._candidates` from every line in the four
   sections regardless of the gate's verdict, and `self._action_sources` from
   every action line regardless of whether it was covered, so the nudge as it
   stands can name a covered action. That is a small fix and is worth making
   whether or not any of this is built.

A sixth, not in the brief: **the system already has a second reader in a better
position.** The continuity editor runs *after* the draft and judges the actual
words rather than guessing what she will be caught by, and on the 12:53 turn it
caught a repetition the block had warned about in advance and the persona had
ignored anyway. Money spent on a reader before the draft competes with money
spent on the reader after it, which has strictly better evidence.

---

## 5. Recommendation

**Do not build a dedicated retrieval agent. Fix four things in code, then
widen the second reader that already exists, in shadow.** The reasons are the
measurements in §1.

**Why not the agent.** The situation block is 3.1k tokens of a 73.3k-token
prompt for the first character and 5.0k of 48.5k for the second. It is not what
is drowning her: the carrying block is 11.6k and the thread is 46.3k, and
neither is in this agent's scope. The one thing the block actually *instructs* —
the slot — is chosen from at most four candidates in her chat with him and two
in the second character's. Paying 3.8 seconds on the loop thread and roughly
double the per-reply spend so that a model can choose among four things, when
the two faults the receipts caught are both fixable with a number and a rule, is
not the trade. And the 12:53 turn is a standing warning that a shorter block is
not automatically a better one.

**The four code fixes, in order.**

1. **A floor under the slot.** `attention.slot_min_weight`: an action below it
   does not take the slot, it waits. `share` held the slot 25 times in a week at
   weight 0.35, in blocks whose heaviest lines are 0.85, only because it was the
   only action offered. A floor of 0.5 would have left both 12:15 and 12:28
   empty, which was the right answer.
2. **Retire a slot the answer did not touch.** The same three posts rode two
   consecutive replies after she visibly declined them. `Attention.charge` fires
   only when the source is judged to have been used; add a showing count per
   action and retire it for the day after `attention.slot_max_showings`.
3. **A `covered_by` row from the foresight to the action it warns against.**
   The self-start put "raise the follow" in the slot while another admitted line
   said raising it is what she is braced against. The gate already has the
   machinery for exactly this suppression and it is not wired.
4. **Stop showing the second reader covered and duplicate lines**, and take
   covered actions out of `self._action_sources`.

None of the four costs a model call and all four are inside the fault the
receipts show.

**Then, the smaller version of his idea.** Widen `sim/nudge.py` to
`mode: "select"`: asked on every reply rather than only at the gauge threshold,
returning ids for the whole block and the slot rather than a prose note. Run it
in shadow for two weeks with the tally extended to count what it would have
dropped, then read the disagreement rate and the A/B pairs by hand. It inherits
the shared system prompt, the confidence floor, the allowed-source check, the
A/B recorder and the failure path, and returning ids retires the one failure
that role has ever had. If, after two weeks, its `carry` set beats the gate's on
turns read by eye, switching it live is a config change and the risk analysis
above already applies to it.

**A narrower version still, if even that is too much:** run the selection pass
only when the block exceeds N lines, or only on turns where more than one action
is offered. On the week's tally that is a small minority of calls — 46 of 72
slots filled at all, and only the self-start receipt had three actions queued at
once — so it would fire rarely and cost almost nothing. It also would not have
caught the 12:15 fault, where there was exactly one action and it was the wrong
one. A floor catches that; a gated model call does not.

---

## 6. If it is built anyway: the checklist

- `Config.REQUIRES` gets a row for the new switchable section, naming the
  existence property it needs (`None`: it is the mind).
- Every new config key in **both** `config.py:DEFAULTS` and each `config*.json`.
- The framing prompt goes in `prompts/`, carries no person, marks the
  character's place with `{{TOKEN}}`s, and forks on
  `[[?digest]]…[[/digest]][[?resident]]…[[/resident]]` for how she sees him.
  `tools/neutral_gate.py`, `tools/character_names.py` and
  `tools/sight_words.py` all run in smoke and all three would catch a slip.
- Any collaborator handed to it after construction is declared in `WIRES` and
  attached with `wire(obj, name=...)`; smoke fails on a declared wire still
  `None`.
- The decision is written to the save the moment it exists, not held on the App
  until the reply is sent; a stop is `Stop-Process -Force` with no shutdown
  hook, and work in flight leaves a row in `sim/inflight.py`.
- `tools/smoke.py` builds it against a copy of the save and prints its report;
  `/sweep` must not name any of its config keys dead.
- Its own ops report and log line, and a dated entry in `HISTORY.md` under the
  attention section's number.
