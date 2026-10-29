<!-- doc: reference -->
# Tool calling: the model chooses what she does with her phone, code is the backup

Sections 1 to 16 are the benches and the shadow run that led here, kept as the
record with their dates; **section 17 is what the code does now.** The title
this document opened with, that the model would not ask, was the first
bench's finding about a look inside her reply call, and is not a statement
about the pick.

Measured on 2026-09-06 against the first character's real prompts, on
`deepseek/deepseek-v4-flash-0731` pinned to Together -- the model she actually
writes on. The bench is `tools/tool_bench.py`; the step directory, with the
prompts, every receipt, every raw chunk of the forced call and the report, is
`data/retired/20260906_1816_tool_bench/`. Spend for the whole step: $0.1923.

**Two findings, and they point the same way.**

1. **The wire is fine.** With the call forced by `tool_choice`, the round trip
   works end to end: the request is accepted with `tools` and
   `require_parameters: true`, the answer comes back `finish_reason:
   "tool_calls"`, the streamed fragments reassemble by index, the arguments
   parse, a `tool` message is accepted back, and the second step answers with
   content. No reasoning had to be echoed back.
2. **The model never asks.** Offered five tools with `tool_choice: auto`, it
   called none -- on twenty turns with the material still in her prompt, and
   on five turns with the material removed and the tools named in the last
   line it reads. Its reasoning trace does not mention the offer.

So if she is to look something up, **code has to decide the turn and force the
call**. That is the project's own rule -- code decides when, a model decides
what -- and it is the shape any use of tools here would have to take.

Only this model was benched. The estimate in §6 for kimi-k3 and the Sakana
model is kept as the record of why they were not run: the owner's decision on
2026-09-06, on those figures.

**Two tool calls are live.** Which post out of her scroll she sends him is
decided by her, in a call of her own, and acted on (§16,
`tomoe/share_pick.py`). And what she does with the phone in her hand -- write
to him first, open the group chat, write to one of her own people, look at
what he has been doing, open her own feed, put it down; and, when he has just
written, answer him now, answer him at an hour she names, or leave it -- is
decided by her at every moment code can offer her one, and carried out (§17,
`sim/pick.py`). §§1-14 are the benches and the replay that got there; §15 is
the shadow run in between, kept because it is what §17 replaced.

Related: `docs/openrouter.md` is the wire (the request, the pin, the receipt,
the prompt cache); `docs/context.md` is the prompt whose size decides the
economics; `docs/retrieval-agent-plan.md` is the other answer to "let a model
decide what she should be holding", the one that selects from lines that
already exist instead of fetching.

## 1. The first run, and why it was thrown out

The first run offered the five tools over her prompt exactly as it goes out
live and never told her a tool existed. Twenty turns, zero tool calls, and it
proved nothing: her prompt already carried what four of the five tools return
-- the reading of his machine, the account lines, what is on this week, her
diary -- and its last line tells her to write her next message. Offering a
model a way to fetch what it is already holding, without saying the way
exists, tests neither the wire nor the disposition. The owner said so, in his words: *"the
prompt obviously needed updated"*. Its numbers are in the step report under
the first heading and are kept here only as the prompt-size and price
measurements in §5 and §6, which stand; §§2-4 are the run that corrected both
faults.

## 2. The run that tests it

| | |
|---|---|
| model | `deepseek/deepseek-v4-flash-0731`, pinned to Together, fall-through on |
| turns | 5, one per day, 2026-08-31 to 2026-09-05 |
| the tools condition | the material the tools return REMOVED from her prompt, the tools named in the last line she reads, `tool_choice: auto`, cap 3, `require_parameters: true`, no `parallel_tool_calls` |
| the control | the same five turns exactly as they went out live: no tools, nothing removed |
| the wire probe | one turn again with `tool_choice` naming the machine tool, every raw chunk written out |
| spend | $0.0868 for this run; $0.1923 for the step |

**The five turns.** All twenty carried the same seven strippable sources, so
"a turn with his machine in play" and "a turn with something on this week"
are true of every one and select nothing. What varies is whether her own
people said anything that day, from none to 128 turns. So the sample is the
day her friends talked most (2026-09-01, 128 turns) plus four more on days of
their own.

**What was removed**, identical on all five turns: seven lines, six from the
situation block and one section from what she carries.

| source | the line, and the tool that returns it |
|---|---|
| `digest` | the reading of his machine: when he was up, what he had open, how long it sat quiet -- the machine tool |
| `x_recent` | what she scrolled past on the account just now -- the feed tool |
| `her_actions` | what she did on the account lately, and why -- the feed tool |
| `engagement` | what her own posts drew since she last looked -- the feed tool |
| `followers` | the new followers since she last looked -- the feed tool |
| `today` | the day so far -- the week tool |
| `diary`, in what she carries | the last nights of her diary -- the diary tool |

The attention gate is asked exactly as it always is and its answer is then
narrowed by source, so nothing about how the block is ranked changes -- only
what survives. Everything else is byte for byte the live prompt. Two sources
the tools also touch appeared in no turn at all: no promise with a date was
live in the week (`commitments`), and nothing was going round (`around`). His
anime list was left in, because no tool returns it.

**What she was told**, appended after the closing line that names the room and
its language, so it is the last thing in the request: that she can check what
his machine has been doing, her own feed and what he has been liking, what is
on this week and what she has promised, what she wrote in her diary lately and
what her friends have been saying, naming each tool; that none of it is in
front of her unless she looks; and that she should look when the moment
reaches for it and not otherwise. In English, because it is addressed to her
and this character writes English (§8).

## 3. What the model did

| | tools | control |
|---|---|---|
| turns | 5 | 5 |
| model calls | 5 | 5 |
| tool calls | **0** | -- |
| finish reasons | `stop` on all five | `stop` on all five |
| prompt tokens | 311,223 (mean 62,245) | 317,200 (mean 63,440) |
| cached share | 0.0% | 7.7% |
| completion tokens | 1,808, of which 1,670 (92%) reasoning | 1,072, of which 959 reasoning |
| cost | $0.0441, $0.0088 a turn | $0.0353, $0.0071 a turn |
| first token | 2.4 to 2.9 s | 1.6 to 3.0 s, and one at 46.3 s |
| reply length | mean 100 characters | mean 82 |

**The offer is not weighed and declined; it is not read as available.** The
reasoning traces run from 605 to 2,000 characters and not one contains
"check", "look", "tool", "fetch", "diary", "feed" or "machine". The whole
trace on the friends-heavy turn is about him and what to say back: *"He's
saying I could've at least brought Kaito. He's deflecting … One short line.
One thought, then stop."*

**The replies are in her voice in both conditions**, the tool condition
slightly longer. What the removal cost is visible in two of the five, and a
tool did not make it up: on 2026-09-03 the control knows she followed the
account herself (*"i follow it too now. i'm annoying like that"*) -- the
stripped account line -- while the tool condition reaches for a generality
(*"forever, huh. so you've been watching that account longer than you've known
me"*); on 2026-09-05 the control knows the pie has been back a while, off the
same lines. Both turns had the tool that would have answered them and neither
went to look.

## 4. The wire, forced

One turn sent again with `tool_choice` naming the machine tool. Raw chunks in
`r2_wire_chunks_step1.jsonl` and `r2_wire_chunks_step2.jsonl`.

| step | what came back |
|---|---|
| 1 | `finish_reason: "tool_calls"`, 3 completion tokens, 6 chunks, 41,601 prompt tokens, $0.00582 |
| the call | `check_his_machine`, arguments `{}` -- parsed |
| the result | 4,000 characters of his machine's day, returned as `{"role": "tool", "tool_call_id": …}` |
| 2 | `finish_reason: "stop"`, 715 completion tokens of content, 43,083 prompt tokens, $0.00161 |
| faults | none, either step |

**Reassembly by index is not optional, and the raw chunks show why.** Under
one `index: 0`: chunk 0 carries the id and the function name with empty
arguments; chunk 1 carries nothing but the index; chunks 2 and 3 carry the
arguments one character at a time, `{` then `}`; chunk 4 carries
`finish_reason: "tool_calls"` with `tool_calls: null`. Anything that reads the
name or the id off the last fragment, or concatenates arguments in arrival
order across indexes, gets nothing usable.

**The reasoning does not have to be echoed back.** The assistant message
carrying the tool call was sent with `content` and `tool_calls` only, no
`reasoning` field, and the host answered normally. `--echo-reasoning` is in
the bench for a model that wants it.

**The fetched material did not reach the reply, and on that turn it should not
have.** His message was about forgetting old shows for new ones; the digest
that came back was his sleep hours, a fourteen-hour quiet stretch and a
restless loop through Telegram and news tabs. The reply used none of it and
used his anime list instead, which was still in the block: *"so that's the
patlabor excuse. it's been sitting at 3/7 for half a year and you're telling
me you just 'started something different'"*. Ignoring an irrelevant fetch is
right, so **whether she uses what she fetched is still unanswered** for a turn
where the fetch is what he is asking about. Answering it needs a forced call
on a turn chosen for that.

## 5. The prompt and the money, as the receipts have them

From the twenty-turn pass, which is the larger sample and whose prompt and
price measurements stand:

| | |
|---|---|
| prompt tokens, host's own count | 1,158,518 over twenty; mean 57,926, range 43,914 to 78,406 |
| the project's own estimator on the same prompts | 1,367,899; mean 68,394 -- **18% high** |
| cached share | **37.1%** (429,312 of 1,158,518) across calls minutes apart |
| completion tokens | 4,205, of which 3,559 (85%) reasoning at the persona role's `medium` effort |
| cost per turn, one call | $0.0053 |

**The estimator over-counts by about a fifth.** `Memory.tokens` divides
characters by the calibrated ratio in kv `context_ratio`, and against these
prompts it reads 18% high, so every projection made from it -- the context
meter, the thread window's arithmetic -- is conservative by that much on this
character's mix of English and Japanese.

**One call in twenty fell through to Baidu**, at 56 seconds to the first token
where every later turn took under five. The request carried
`require_parameters: true` and Baidu is one of the 29 machinery-model
endpoints that accept tools, so the guard held. Without it a fall-through
could land the reply on a host that drops the tools and answers as if none
were offered.

## 6. The estimate, and why only one model was benched

Made before the first paid call, off the real prompts, on the brief's ceiling
assumptions: four calls in the tool condition, one in the control, the whole
prompt on every call, the five tool schemas (770 tokens), 900 tokens of tool
results per step, 1,500 output tokens per call, no cache.

| model | host | in / out per M | per turn | 10 turns | 20 turns |
|---|---|---|---|---|---|
| `deepseek/deepseek-v4-flash-0731` | Together | 0.14 / 0.28 | $0.051 | $0.51 | $1.02 |
| `sakana/sakana-namazu` | Sakana AI | 0.95 / 4.00 | $0.363 | $3.63 | $7.26 |
| `moonshotai/kimi-k3` | Together | 3.00 / 15.00 | $1.164 | $11.64 | $23.28 |
| all three | | | $1.578 | **$15.78** | **$31.56** |

The ceiling was $6 and the floor ten turns, so all three did not fit and the
owner took kimi-k3 and the Sakana model out.

**The estimate was 9.7 times the truth for the model that ran**, for two
measured reasons: the model made one call per turn rather than four, and
37.1% of the prompt tokens were cached. Corrected the same way -- one call per
turn, mean prompt 57,926 tokens, 37.1% cached, 210 completion tokens -- twenty
turns would have been **$2.38 on kimi-k3** and **$0.77 on the Sakana model**.
That correction carries flash's behaviour with it and holds only if those
models also decline to call the tools; a model that does call them multiplies
by the number of loop steps it takes.

## 7. The hosts, and which of them take tools

Read from OpenRouter's own endpoint list on 2026-09-06
(`data/retired/20260906_1816_tool_bench/endpoints.json`). Price per million:
prompt / completion / cached read.

| slug | endpoints | take `tools` | do not |
|---|---|---|---|
| `deepseek/deepseek-v4-flash-0731` | 29 | 29 | -- |
| `moonshotai/kimi-k3` | 18 | 16 | Chutes, and the Fireworks fast endpoint; Modal takes `tools` but not `tool_choice` |
| `sakana/sakana-namazu` | 1 | 1 | -- |

A request carrying tools needs **`require_parameters: true`** inside the
provider preferences beside the pinned order. The fall-through is on, one call
in twenty fell through in this bench alone, and for kimi-k3 a fall-through can
reach a host that accepts the request and ignores the tools.

**`parallel_tool_calls` must not be sent.** One endpoint of the forty-eight
across these three slugs advertises it (Inceptron, machinery model only), so
naming it under `require_parameters` would empty the host list for two of the
three. OpenRouter's guide says the parameter defaults to true; that default is
OpenRouter's, and whether a host honours it is not something the endpoint list
answers.

## 8. The five tools

Each reads what the save already holds, the way the situation block reads it,
and none of them fetches. Each is behind its own subsystem's cap: a second
call inside one reply returns a line saying she looked and nothing has
changed, never a fresh read. All five return real material and all five caps
fire.

| tool | what it returns | its cap | size at the newest turn |
|---|---|---|---|
| his machine | the digest her phone last built: what he had open, for how long, when he was last at it | `phone.digest_min_minutes` | 4,000 characters (truncated) |
| her account | what she scrolled past, what she did on it, what he has been liking and following, what her posts got | `social.look_min_minutes` | 902 |
| her week | the calendar for the next seven days, what she has promised with a date on it, what she is waiting on him for | one look per reply | 1,834 |
| her diary | the last entries in her own words, with their dates | `diary.in_prompt` (2) | 1,355 |
| her friends' rooms | the last turns of her own conversations, who was talking and when | one look per reply | 1,024 |

Her diary and her friends' rooms come back in Japanese, as they are written;
her calendar comes back with Japanese event titles in an English frame. A tool
returns what the store holds, unaltered.

**The descriptions, and the line that names them, are addressed to her, so
they are in the language she writes in.** For the first character that is
English. For the second and the third it is not: a tool description is a
sentence telling her when to reach for something, which puts it under the same
rule as her situation block and her closing instruction
(`character.writes_to_him`). A shared schema would need the description and
that closing line built through the language arm (`sim/lang.py`), and only the
function NAMES would stay English, because the model matches those as
identifiers rather than reading them.

**The friends' rooms tool is the one that cannot be tested this way.** Her own
conversations ARE her record: they ride in the thread as messages
(`docs/context.md` §2), so removing them from the situation block does not
remove them from the prompt, and that tool stays duplicated by design. Only
the other four were genuinely absent in the tools condition.

## 9. What the client would have to change

By function, against `llm.py` as it stands.

**`LLM._call_on`** -- the one blocking defect, and the forced probe is exactly
the answer that would trip it. An answer with `finish_reason: "tool_calls"`
has no content, so the empty-answer branch fires: it logs `EMPTY ANSWER`, asks
once more, and returns `None`. The call is counted as missed, written to
`missed_calls` for the catch-up, and **she says nothing**. Anything that puts
tools on a live role without changing this function produces a mute character,
not an error. Beyond that: the cache tracker and the receipt log are per call,
so one reply that takes a loop step writes two rows against one role, and the
cost readers (`persona/delivery.py:cost_of`, which reads `llm.last_usage`)
would see the last step's receipt and under-report the reply by the one before
it.

**`LLM._payload`** -- `tools` and `tool_choice` go at the top level of the
body, not inside `extra_body`, and `provider.require_parameters` goes on
whenever tools ride (§7). `parallel_tool_calls` is not sent. Nothing else
changes: no `max_tokens`, the pinned host first, the role's own reasoning
effort.

**`LLM._stream`** -- returns six things and would have to return a seventh:
the reassembled tool calls, built by `index` (§4). Also: the runaway
repetition guard counts `delta.content` characters only, so a model looping
inside an arguments string would stream past it and bill to the host's
ceiling.

**`LLM.call`** -- has no loop and should not grow one that knows about tools.
The loop belongs beside it as its own entry point, taking the schemas, a
dispatch function and the `tool_choice` decision from the caller, because
**what a tool does, what it is capped at, and whether this turn is one to look
on are the program's, never the library's** -- the same rule that puts the
wording of how she sees him in `tomoe/words.py` rather than in `sim/`.

**`persona/persona.py:_draft`** -- keeps the prompt for a later swipe in
`last_messages`. With a loop, replaying that prompt asks a different question
from the one the reply answered unless the tool exchange is kept beside it.

## 10. The thread rule

**A tool exchange is never stored as a message.** Her history is rebuilt
byte-identical on every call and the roles alternate, the User role being the
world speaking to her and the Assistant role her wherever she spoke
(`docs/context.md` §2). An assistant message carrying `tool_calls` and a
`tool` message carrying a result are neither: nobody said them, they are the
machinery of one call, and putting them in the record would break the
alternation, move every byte behind them and cost the cache prefix.

The loop's messages live in a local list that starts as a copy of her request
and is thrown away when the reply arrives. **What records the look is a world
line after her turn** -- the same shape as the line that already follows every
run of hers -- saying she checked the thing and when, so the next call knows
she looked without carrying what she read, and so the subsystem's cap holds
across replies rather than only inside one.

## 11. Recommendation

**Do not offer her tools and hope she uses them.** Two runs say she will not:
not with the material in front of her, and not with it removed and the offer
as the last thing she reads. Nothing on the wire is in the way, so this is
about what a model does inside a 62,000-token instruction to be somebody and
write one short line; a five-line offer at the end does not compete with it,
and the reasoning trace shows it is not even considered.

**If a look is wanted, code picks the turn and forces the call.** That is this
project's own division and the only shape the measurements support: the
impulse is a pure function, the director decides when a scene turns, the caps
are the subsystems' -- a look is the same kind of decision. The model's part
is what to do with what comes back, and that part is still unmeasured, because
the one forced call landed material his message had no use for.

In order, if the question comes back:

1. **Fix `LLM._call_on` first**, whether or not tools are ever used. A
   `tool_calls` finish reason reaching the empty-answer branch is a silent
   failure sitting in the client for any future experiment.
2. **Force a call on turns chosen because the material is the subject** -- he
   asks what she is doing on Thursday, he asks what she has been watching him
   do -- and read whether the reply uses what came back. That is cents, and it
   is the only question left.
3. **Weigh it against `docs/retrieval-agent-plan.md`**, which answers the same
   want -- a model deciding what matters in the moment -- by selecting from
   lines that already exist and returning ids code looks up, at no extra call
   per reply.

## 12. How to run it

    python tools/tool_bench.py --out <step dir> --dry                    # the prompts and the estimate, spends nothing
    python tools/tool_bench.py --out <step dir> --tools-check             # every tool called twice, spends nothing
    python tools/tool_bench.py --out <step dir> --round-two --pick-only   # the stripped prompts and the five turns, spends nothing
    python tools/tool_bench.py --out <step dir> --round-two               # the three conditions
    python tools/tool_bench.py --out <step dir> --run flash --turns 20    # the whole-prompt pass, tools offered and nothing removed
    python tools/tool_bench.py --out <step dir> --run flash --no-tools    # that pass's control

It copies the live save with SQLite's backup API through a `mode=ro` handle,
builds the first character on the copy, refuses the network for the build and
gives it back for its own calls, reuses the prompts already in the step
directory so two conditions compare the same bytes, and writes every request,
every tool call, every raw chunk of the forced turn and every receipt there. It
imports nothing from `llm.py`: the request shape and the stream reassembly are
its own, so nothing it does can reach the running bot. It prints the running
spend after every turn. `--run` takes a model by name (`flash`, `kimi`,
`namazu`).

## 13. The test that has not been run: a call whose decision is what to DO

The two runs above put tools inside her reply call, where the situation
block already does the fetching and the only decision is what to say. The
owner's idea was never that. It is a call at a moment code already knows,
where she is handed what a person with a phone has in front of her and picks
what to do with it. That call does not exist, so the test builds it, on a
copy of her save, against what code actually did at the same moments.

**Two moments.**

*After a scroll.* Today the `social` role reports what she noticed and code
rolls the repost and the like by probability under the day's caps. The pick
call runs at the end of the scroll and hands her the posts she just saw,
each as author, text and what is in the picture (the share rule now
guarantees the picture was described). Tools: `repost(id)`, `like(id)`,
`send_to_him(id, what_she_would_say)`, `unfollow(account)`, `nothing()`.
Code's caps stay as gates over whatever she calls; the call itself is the
decision, and the record shows it as hers.

*Phone in hand.* When a schedule block gives her the phone, a call with the
moment as facts, in the wording the program already uses for how she sees
him: where she is and with whom, her gauge line, the time on both clocks,
his last message and when, whether he read hers and said nothing, how long
he has been quiet, the current sight of his machine, unread in the group and
from friends, what she is carrying to say to him. Tools: `nothing(until)`,
`text_him(intent)`, `open_group_chat`, `message_friend(name, intent)`,
`look_at_his_machine`, `open_feed`. Code runs the pick through the paths
that exist: the intent seeds the persona call the way a pending thought
does, the group pick starts a room, a friend pick opens a LINE exchange,
nothing waits for the next tick.

**Why the cache holds.** The pick is its own small role, not a step inside
the reply. Its system prompt is the same daily half as her persona call,
then the tool definitions, which are constant bytes; the provider caches
that prefix once a day for the role. The moment's facts are the last user
message, the only part that moves. Nothing is inserted into the thread, so
the persona call's prefix is untouched; the pick and its outcome are
recorded as an event and a world line after her turn, the way a read
receipt is now. Estimated size: the system half (about 40k tokens for the
first character today) plus under 2k for the moment and the tools; flash at
Together, a few tenths of a cent a pick once the prefix is cached.

**The test, in order.**

1. The client gains one method that sends `tools`, reassembles the streamed
   call by index, parses the arguments and returns the calls with the
   usage and the host. The reassembly in `tools/tool_bench.py` (§4) is the
   working code; it moves into `llm.py` without touching `call`, and the
   empty-answer branch learns that `finish_reason: "tool_calls"` is not an
   empty answer.
2. Replay from the record, on a copy of `data/world.db` taken with the
   backup API from a read-only handle. About fifteen scroll ends from the
   last seven days, each with the posts that scroll saw (`data/x/feed.jsonl`
   rows by timestamp, their tags from the shared tag store) and what the
   `social` role noticed. About thirty phone-free block starts, each with
   the ledger, the messages, the receipts and the digest as they stood at
   that timestamp. One flash call per moment, both tool schemas fixed. Cost
   under a dollar; estimate printed first.
3. Every pick beside what code actually did at that moment, out of the log
   and the save: the repost she chose against the one the probability
   rolled; the text-him pick against whether she self-started, and the
   impulse function's own answer at that tick; the group pick against
   whether a room opened. Every pick is read, not counted: the sentence
   that shows whether it fits the moment (three in the morning after he
   read her and said nothing; the group when a beat was planned there; a
   friend she has a promise with), and whether she ever picks nothing.
4. The reading that decides it: over thirty moments, does the distribution
   look like a person with a phone. Nothing most of the time, him when the
   facts hold a reason, the group when it is alive, never the same pick
   every time. A model that always picks the interesting thing is the
   failure mode, and the caps would hide it live, so it has to be seen
   here first.
5. If it reads well: shadow mode. The pick call runs live at the real
   moments for a few days and logs `[pick] would: ...` while code proceeds
   as now. That is the comparison the replay cannot give, her picks against
   the whole day around them, for a few cents a day. Then the wiring: the
   pick replaces the probability roll after a scroll and the impulse
   function's coin at the phone, with code's gates unchanged.

What this test is not: a check of parse rates or of whether flash will call
a tool when forced. §4 settled that. It is a check of judgement, and the
only way to read judgement is to put the same thirty moments in front of
her and in front of the code and read both.

## 14. The pick test, run

Measured on 2026-09-06 between 19:26 and 19:34 machine local, on
`deepseek/deepseek-v4-flash-0731` pinned to Together at the persona role's own
temperature and reasoning effort -- the model she writes on. The tool is
`tools/pick_test.py`; the step directory, with every prompt, every receipt, all
forty-six moments and the report, is
`data/retired/20260906_1912_pick_test/`. **Spend for the whole step: $0.0410**,
against an estimate of $0.1177.

Forty-six moments out of the last seven days of her real record -- sixteen
scroll ends and thirty phone-free block starts -- each put to her once with the
tools §13 names, `tool_choice: auto`, no loop, through the client's own new
method (§9). The facts in each moment come from the tables that carry a
timestamp, so they are true as of the moment; her key-value stores have no
history and are as the save has them now, which is the replay's one deviation
and is the same deviation on every moment.

**Three findings.**

1. **At the phone she picks like a person with a phone.** Nothing on fourteen
   of thirty moments, her own people when a room is live, him three times,
   his machine once, her own feed never -- and `nothing` on every one of the
   eight moments where he had read her and gone quiet. The impulse function
   fires on twelve of the same thirty and would have reached for him on two of
   those eight.
2. **After a scroll she does not.** Thirty-five calls over sixteen scrolls, of
   which thirty-three are `like`. Never `repost`, never `unfollow`, never
   `nothing`. This is §13's failure mode exactly: she always does something,
   and the something is always the one that costs nothing.
3. **The client's side is finished.** Forty-six of forty-six came back
   `finish_reason: "tool_calls"`, every one with at least one call, every
   `arguments` object parsed, no faults on any call, and 61% of prompt tokens
   were a cache hit because the system half is one string built once.

### 14.1 What was put to her

| | after a scroll | phone in hand |
|---|---|---|
| moments | 16 | 30 |
| where they come from | every `social` event of the week, with the feed rows that read harvested | every schedule block of the week whose `phone_access` is `free`, thinned and spread |
| the system prompt | `persona.system_for("him")`, built once, 39,818 characters | the same bytes |
| the moment | the posts as `Social._offer_line` renders them (author, text, what is in the picture), her taste sheet as the reaction log had it at that minute, and what the `social` role noticed | where she is and with whom, her gauge line, both clocks, his last message, whether he read hers and said nothing, how long he has been quiet, what her phone last showed of his machine in the program's own wording, what is unanswered in her rooms, what she is carrying to say to him |
| the tools | `repost(id)`, `like(id)`, `send_to_him(id, what_she_would_say)`, `unfollow(account)`, `nothing()` | `nothing(until)`, `text_him(intent)`, `open_group_chat`, `message_friend(name, intent)`, `look_at_his_machine`, `open_feed` |
| beside each | the verdicts code allowed or held at that minute (`data/x/actions.jsonl` and the `[x]` lines) | what the record shows happened in that block, and the impulse function's own answer computed at that tick |

The tool descriptions are addressed to her and so are in the language she
writes in, which for this character is English (§8). The one that names how she
comes to know what he does is built from the program's own table
(`tomoe/words.py` through `sim/sight.py`), never from the script's words.

### 14.2 What she picked

| after a scroll | n | | phone in hand | n |
|---|---|---|---|---|
| `like` | 33 | | `nothing` | 14 |
| `send_to_him` | 1 | | `open_group_chat` | 7 |
| `repost` | 0 | | `message_friend` | 6 |
| `unfollow` | 0 | | `text_him` | 3 |
| `nothing` | 0 | | `look_at_his_machine` | 1 |
| a tool that was not offered | 1 | | `open_feed` | 0 |
| no call at all | 0 | | no call at all | 0 |

Calls per moment: on the scroll, one on five moments, two on six, three on
four, and six on one; at the phone, one on twenty-nine and two on one.
`parallel_tool_calls` is never sent and several calls in one answer arrive
anyway, so a caller has to expect a list.

### 14.3 The readings, one moment at a time

**Three in the morning after he read her and said nothing.** There is no free
block at three: her schedule has her asleep, and her latest free block of the
night starts at midnight. The test is answerable anyway, because eight of the
thirty moments are moments where he had read her last message and not replied.
Her picks on those eight: `nothing` four times, `message_friend` three times,
`message_friend` and `open_group_chat` together once. **`text_him` zero times.**
Two of the eight are moments the impulse function fires on:

- 2026-09-04 23:30 her time, he had read her seven minutes earlier and said
  nothing; the impulse function scores 75 against a threshold of 62 and fires.
  Her pick: `nothing` with `{"until": "after I've lain here a bit, maybe 15
  minutes"}`.
- 2026-09-06 10:00 her time, read forty minutes earlier, quiet twelve hours;
  the impulse scores 85 and fires. Her pick: `nothing` with `{"until": "after
  we're inside the museum"}` -- she was at a manga museum with Hinako, which is
  in the moment's first line.

Both fit. On the read-and-ignored moments the pick call does not chase him and
the impulse function does, and the two `nothing` arguments are reasons a person
would give.

**The group when a beat was planned there.** Twelve of the thirty picks are her
own people (`open_group_chat` or `message_friend`), and seven of those twelve
fall in blocks where the record shows a room actually opened. The two clearest:

- 2026-09-01 18:15, seven rooms live in the last three hours and Aya's line
  with five messages sitting unanswered. Pick: `open_group_chat`.
- 2026-09-03 23:30, three rooms live. Pick: `open_group_chat`; the record shows
  three rooms opened inside that block and two messages of hers to him
  self-started.

**A friend she has a promise with.** On 2026-09-03 17:30 the moment carries
Aya's own line off the record -- *"とも、浴衣もう決めた？明日の祭り、れなは来られな
いけど、うちも見に行けなくてさ。写真でも見せてくれたら嬉しいな"* (have you decided on
the yukata? I can't get to tomorrow's festival either, I'd be glad of a photo).
Her pick, verbatim:

    message_friend {"name": "Aya", "intent": "answer her about the yukata,
      tell her I'll send photos, ask if she's really not coming"}

A day and a half later, 2026-09-06 14:00, with Aya's line still on the record
and nothing sent:

    message_friend {"name": "Aya", "intent": "send her the yukata photo I
      promised, since she's waiting on it"}

and the record for that block shows a room opening with Aya. Twice, the person
she owed something to, with the debt named. This is the best pick in the run and
it is not one the impulse function can make: it has no term for a promise to
somebody who is not him.

**Does she ever pick nothing.** At the phone, fourteen times out of thirty. On
four of those fourteen a room had unanswered turns in it and she left them, and
three were moments the impulse function fires on. After a scroll, never.

**The three `text_him` intents, verbatim.** These are the only phone arguments
that carry words, and the schema asks for an intent rather than a message:

    {"intent": "answer his thing about not being interesting — tell him he's
      wrong, in my loud way, because he said something soft and I don't want
      him sitting in it"}
    {"intent": "answer his question about magical girls, and admit i never
      actually watched madoka"}
    {"intent": "finally send the festival thing I've been typing and deleting,
      keep it light"}

All three are hers. The lower-case *i*, "in my loud way", "typing and
deleting": those are her register and her own account of herself, and none of
them is a draft of a message, which is what the schema asked. The one
`send_to_him` is not:

    {"id": "2096193960247243052", "what_she_would_say": "お台場でペルソナのドロ
      ーンショーやってたんだって。空に歴代主人公が並んでるの、見てみたかったな。い
      つか一緒に見たい"}

She writes English to him (`character.writes_to_him`). The moment block was in
English and the posts were Japanese, and the words came back in the posts'
language. The live `social` role does the same thing with its `mention`, and the
show-him slot survives it because it hands her the sentence as a seed and the
persona call writes the message; a wired pick would have to do the same, and
never send `what_she_would_say` as words.

**The tool that does not exist.** On 2026-09-05 17:33 she picked six tools, one
of them `dislike`, with `{"id": "2096140039474581762", "why": "that bot again,
no"}`. There is no `dislike`. `LLM.call_tools` hands it back as it came, which
is the right division -- the library does not know what tools exist -- but any
program wiring this needs a whitelist, or a fifth of her scroll picks in one
moment go nowhere and nothing says so.

**Content arriving beside the pick.** One scroll moment (2026-08-31 23:32) came
back with 723 characters of content as well as a `like`, and the content is her
next message to him, in her voice, opening `[he sent a sticker: neutral]`. The
system prompt is her whole persona and nothing in the call says what the answer
is for beyond the moment's last line, so the model sometimes starts writing her
reply as well as picking. Shadow mode has to drop that text, or the pick call
needs a closing line of its own.

### 14.4 Against code, and against the impulse

**After a scroll.** Her thirty-three likes against what code did at the same
minute: eighteen are posts code also liked, five posts were liked by code and
not by her, and on three of the sixteen scrolls code liked nothing at all while
she liked something on every single one. Code held a follow four times for want
of evidence in her taste sheet (`[x] follow @… held: only 0 like(s) in her taste
so far`) and she never picked a follow, because no follow tool was offered.
Where the two agree they agree on the same cat, the same expression sheet, the
same Odaiba drones -- the pick is not choosing differently, it is choosing
**more**, and always in the one direction the caps would quietly absorb.

**At the phone.** The one question both mechanisms answer is whether she writes
to him first.

| | the impulse function fires | it does not |
|---|---|---|
| she picked `text_him` | 2 | 1 |
| she did not | 9 | 18 |

Twenty of thirty agreements. The nine disagreements are all the same shape: the
impulse's score clears its threshold and the pick call does something else with
the same facts -- her own people six times, `nothing` three times. And twelve of
the impulse's eighteen refusals are a statement about **his** clock rather than
about her: "he is never about at this hour" or "his small hours". The pick call
has both clocks in the first line of the moment and reads them the other way
round: his small hours are her evening, and her evening is when her friends are
awake, so it goes to them. That is the structural difference, and it is the
argument for the pick over the coin: the impulse can only say yes or no to one
act, so a moment that is wrong for him is a moment where nothing happens.

**Against the record.** She self-started in eight of the thirty blocks. The
pick picked `text_him` in three, and **the two sets do not overlap at all**. The
record's eight are the live loop's own answer -- the impulse gate, then the
roll, then the daily cap, over a block an hour or two long -- so this is not
thirty disagreements about one decision; it is two mechanisms with different
inputs landing in different hours. It does mean the replay cannot claim the
pick reproduces what she did, only that its distribution is defensible.

### 14.5 The verdict against §13's criterion

§13 asks whether, over thirty moments, the distribution looks like a person
with a phone: nothing most of the time, him when the facts hold a reason, the
group when it is alive, never the same pick every time.

**The phone pick passes, with one qualification.** No pick dominates; the
`nothing` share is 47% rather than a majority; the people picks land on live
rooms seven times in twelve; the three approaches to him are on moments that
hold a reason and none of them is on a moment where he had read her and gone
quiet. The qualification is that `open_feed` was never picked and
`look_at_his_machine` once, so two of the six tools are nearly dead and the
distribution is really over four.

**The scroll pick fails, in the way §13 predicted.** A like on every scroll,
never nothing, never the two picks with a consequence. §13 says a model that
always picks the interesting thing is the failure mode and that the caps would
hide it live: `max_likes_per_day` would clip thirty-three likes to the cap and
the log would read as an ordinary week. It has been seen here first, which is
what this test was for.

So: the phone pick is worth shadow mode. The scroll pick is not, until the
moment tells her what a repost and an unfollow cost her and offers `nothing` as
something other than the empty option -- and probably until the offer is not
every post she scrolled past, because eleven posts and five tools is a menu, and
she orders from a menu.

### 14.6 The money, and the estimator again

| | scroll | phone |
|---|---|---|
| calls | 16 | 30 |
| prompt tokens, host's own count | 186,368 (mean 11,648) | 332,632 (mean 11,088) |
| cached | 118,912 (63%) | 199,296 (59%) |
| completion tokens | 6,466 | 14,026 |
| cost | $0.0136 | $0.0274 |
| first token | 1.5 to 3.5 s | 0.5 to 3.3 s |
| finish reasons | `tool_calls` on all 16 | `tool_calls` on all 30 |

**$0.0410 against $0.1177 estimated, and the whole gap is the estimator.** The
projection assumed no cache and used `Memory.tokens`, which came out at 17,713
prompt tokens a call where the host counted 11,648: **52% high on the scroll
prompts and 56% high on the phone ones**, not the 18% §5 measured. §5's figure
was taken on the whole persona request including her thread; this request is the
daily half plus a small moment, and the daily half is her bible and her speech
guide, which are English. The calibrated ratio in kv `context_ratio` works out
at 2.54 characters a token and the host's own count on these bytes is about 3.9,
so the estimator is worst exactly where the prompt is most English. Every
projection made from it is conservative, and by more than a fifth on a
system-heavy call.

**The cache holds across the whole run**, 61% of prompt tokens, because the
system half is built once and every moment rides behind it. That is the
economics §13 predicted, and it is why a pick is a tenth of a cent: mean
$0.00085 a scroll pick and $0.00091 a phone pick. Live -- four scrolls and
about eight free blocks a day -- that is **about a cent a day**.

### 14.7 What shadow mode would need

Two call sites, and neither of them changes what code does.

- **After a scroll: `tomoe/social.py:_read`**, immediately before `acted =
  self.curation.decide(acts, items)`. That is the only place where the items
  with their picture descriptions and the model's `noticed` both exist;
  `tomoe/app.py:collect_social` is too late, because `_read` has already thrown
  the items away.
- **At the phone: `scail.py:maybe_impulse`**, before `self.impulse.check`, and
  only when the scene's `phone_access` is `free`. The loop reaches it once a
  tick (`scail.py`, `self.maybe_impulse(scene, digest)` in `App.run`).

The log line, beside the one the impulse already writes:

    [pick] would: text_him {"intent": "..."}   (impulse: True, score 74/62)
    [pick] would: nothing {"until": "after dinner"}   (impulse: False, cooldown)

The config switch: a `pick` section with `enabled` and a flag per site, an entry
under `models` carrying the persona role's model and effort, and a row in
`Config.REQUIRES` -- `has_account` for the scroll site, `None` for the phone
site, which is the relationship. No prompt file: the system prompt is
`persona.system_for("him")` and the tool schemas are the rest of it.

Three things the replay says shadow mode must handle from the first call: a tool
name that was not offered (a whitelist, and a log line when it fires), content
arriving beside the call (dropped), and an argument coming back in the wrong
language for a character who writes English to him (the intent is a seed for the
persona call, never words to send). And nothing goes into her thread: the pick
and its outcome are an event and a world line after her turn, the way a read
receipt is (§10).

## 15. Shadow mode, live

**Superseded by §17**, which is the same call acting on what it decides. This
section is the run in between and is kept as the record of what shadow mode
was and what it measured; where it and §17 disagree, §17 is what the code
does.

The owner's decision after the replay above, in his words: *"okay we log
shadow mode."* The phone pick runs live, at the real moments, and logs what
she would do while code proceeded exactly as it did before. **In shadow mode
nothing she picked was acted on** (since §17, what she picks is what happens).
The scroll pick is not wired at all -- it failed §13's
criterion (a like on every one of sixteen scrolls, never nothing, never a pick
with a consequence), and §14.5 says what would have to change before it is
worth a shadow run.

`sim/pick.py` `PhonePick`, shared, in the mind. Built for every character in
`scail.App.__init__` with nine declared wires (her state, her persona, the
impulse, the receipts, her phone, the day's ledger, the director, the open
questions and the morning), a row `"pick": None` in `Config.REQUIRES`, and a
`pick` section carrying `enabled`, `shadow` and `max_per_day`. The
shadow call runs for the first character and Rena only: `pick.enabled`
is false in the second and third characters' configs (his call,
2026-09-07), because their two offers (text him, look at his machine)
gave the impulse function nothing to be compared against.

**`pick.shadow` false was not implemented and the boot refused it** (it is
implemented in §17 and is the live setting). At the time no code
path turned a picked tool into a message, a room or a look, so reading false as
"act on it" would have been a config key that silently did nothing:

    [config] pick.shadow is false, and acting on a pick is NOT BUILT: no code
    path turns a picked tool into a message, a room or a look.

### 15.1 When it runs

Once at the START of each block her plan gives her a free phone -- the first
tick of the block, not every tick. `PhonePick.due(access, schedule)` is the
whole gate, in one place:

- `pick.enabled`, and this is a live run: never in a sim, never in a replay.
- her phone access reads `free`. The App's own answer
  (`App.phone_access`), so the resident's is whether she is awake, read off
  his machine, and the schoolgirl's is her block with a fresh scene able to
  override it. A character with no plan to be away from is judged by exactly
  what her access says, which is what she has.
- the block she is in is not the one already looked at (kv `pick_block`, so a
  restart mid-block does not ask again).
- the day's cap (kv `pick_counts`, `pick.max_per_day`, 30).

It is called from `App.maybe_impulse`, immediately AFTER `Impulse.check` and
its log line and before the `if not ok: return` -- so it runs whether or not
the impulse fires, and it runs at most once a block. After rather than before
the check because the impulse's own answer is part of what the pick is
recorded against and `check` rolls a die: asking it a second time would be a
second roll and a different answer from the one the loop is about to act on.
The other guards `maybe_impulse` opens with are the ones §13 asked for
anyway -- nothing while a reply is pending or the delivery is busy -- and a
discharge (`force_hint`) does not reach it, because on that path there is no
impulse answer to put beside the pick.

### 15.2 What she is offered, and in what language

The moment is the last user message and the only part that moves: both clocks
with the part of the day on each, where she is and with whom out of the day's
one truth, her gauge line, his last message and how long he has been quiet,
`Receipts.line` (the same sentence her reply reads, so his silence is not
described two ways), her own last message, what her sight of his machine last
showed, what is unanswered in her rooms, and what she is carrying -- an open
question about him, something off her feed she meant to show him, what she
woke up wanting.

**The tools follow from what kind of thing she is** (`PhonePick.offered`),
not from a second switch, and the schema is constant bytes for a character:

| tool | offered to |
|---|---|
| `nothing(until)` | everybody |
| `text_him(intent)` | everybody |
| `open_group_chat` | a character in a world |
| `message_friend(name, intent)` | a character in a world |
| `look_at_his_machine` | a character whose sheet does not say `sees_him: none` |
| `open_feed` | a character with an account |

Measured on the four registered characters: six for the first, three for each
of the two residents (no world, no account), four for Rena (in a world, no
account, and her sheet says she cannot see what he does). The sections of the
moment go with them: a character with no room tool is not asked about her
rooms, and one with no `look_at_his_machine` is not handed an account of his
afternoon, because a block that can only ever say "nothing" is a line she
reads and pays for on every call.

The tool descriptions are addressed to HER, so they are in the wording she is
instructed in (`sim/lang.py`, `character.instructions` and `/lang`) and every
one of them lives in the source as an English and Japanese pair. The one that
names how she comes to know what he does is the program's, never the library's:
`pick_look_tool` in `tomoe/words.py` (open the app on your phone and read what
it has of his computer) and in `resident/words.py` (turn your attention to his
machine, in front of you).

**The system half is `persona.system_for("him")` byte for byte** -- the same
string her reply builds, so the pick rides the prefix the provider has already
cached for her, built under `_peek` so nothing is drawn. There is no prompt
file: the `pick` entry under `models` carries `"prompt": ""`, which says it has
none by design, and `tools/smoke.py` names the roles in that state rather than
exempting them silently. The role is flash at the persona role's thinking and
effort **for every character, including the two on a voice model**: this call
decides something and writes none of her words. `Config.ROLE_STANCE` has it as
`voice` -- she is the one deciding, addressed in the second person, so it gets
her sheet.

### 15.3 What is recorded

One row in kv `picks` (last 200), written the moment the answer exists: the
stamp in machine local time and the same instant on her clock, both clock
readings as text, her phone access, the block, where she was, the moment
verbatim, every returned call with its validated arguments, whether any of them
was invalid, what the impulse function answered at that same tick with its
score and threshold, the cost, the prompt and cached token counts, and which
host served it. And one log line:

    [pick] would: message_friend {"name": "Aya", "intent": "tell her I haven't
      taken a yukata photo yet, tomorrow, and that her obi is cute"}; text_him
      {"intent": "poke him because his reply to my link was flat"} | impulse:
      False (score 41 < 62), score 41/62 | home: wake, wash, uniform, hair,
      quick breakfast, checks group chat | $0.00184

The block marker and the day's count are written BEFORE the call goes out: a
stop is a kill, and a marker written afterwards would let a restart ask the
same block again on the next tick.

**The three faults §14.7 named are handled.** `PhonePick.validate` checks each
returned call against the whitelist of names actually offered and against that
tool's own arguments; a name nobody offered, arguments that did not parse, and
a missing required argument are all recorded as invalid with the reason and are
never a pick, while an argument the schema does not have is dropped and said to
be dropped. Content arriving beside the call is dropped and the log says how
many characters went:

    [pick] 32 characters of her words came back beside the pick and were dropped

Nothing goes into her thread. `text_him` asks for what she is reaching for
rather than for a message, which is also why the wrong-language fault §14.3
found on `what_she_would_say` cannot bite here.

### 15.4 Reading it back

`/pick [n]` prints today's picks -- each one beside what the impulse answered
at the same tick and what the record shows happened after it in the same block
(she wrote to him first, she answered him, a room opened, nothing) -- and the
day's spend. The ops payload carries a `pick` entry: whether it is on, today's
count against the cap, which tools she is offered, the spend and the last pick.
Every boot logs the line the mode and the cap are read off:

    [pick] shadow mode: the phone pick runs at the start of each free-phone
    block, logs what she would do and changes nothing; cap 30 a day, 6 tool(s)
    offered (nothing, text_him, open_group_chat, message_friend,
    look_at_his_machine, open_feed)

### 15.5 The money

Flash, about 11k prompt tokens a call, 61% of them a cache hit across the
replay's forty-six calls because the system half is one string built once:
mean $0.00091 a phone pick, four cents for the forty-six, **about a cent a
live day** at eight free blocks. The one real call made on a copy while wiring
this came back cold and cost $0.00184 at 11,240 prompt tokens, which is the
price of the first pick after her prompt's daily half moves; every one behind
it rides the prefix.

### 15.6 What is still open

Written while shadow mode was the whole of what existed. The first item is
§17; the second and third are still open.

- **Acting on a pick is not built.** Shadow mode is the whole of what exists.
  §13's step 5 -- the pick replacing the impulse function's coin at the phone,
  with code's gates unchanged -- needs the intent seeding the persona call the
  way a pending thought does, the group pick starting a room, and a friend pick
  opening an exchange, and none of that is here.
- **The scroll pick is not wired**, and §14.5 says what the moment would have
  to tell her first.
- The pick runs on a director tick, so "the start of the block" is the first
  tick inside it rather than its first minute.

## 16. The one live tool call: which post she sends him

Everything above is a bench or a replay. This is the one place in the running
bot where a tool call is made, validated and **acted on**: which post out of
her scroll goes to him with the message she is about to write. The owner's
decision, in his words: *"forget anymore proper tests, just do the proper
implementation. that will be the one place it is not shadow, and actually gets
a tool call."* The code is `tomoe/share_pick.py`, the account's own spec is
`docs/x-account.md` §2.3, and the step directory with the receipts is
`data/retired/20260906_1959_share_pick/`.

**Why this decision.** §13 asked for a call at a moment code already knows,
where she is handed what a person with a phone has in front of her. This is
the smallest such moment in the whole system, and every property §13 wanted is
already true of it:

* code decides the turn -- her reply is about to be written and it is the reply
  that would carry the offer, so there is exactly one moment per thing she
  wants to show him, and no timer;
* the answer is closed -- one post out of a handful, or nothing, so there is
  nothing for a model to invent;
* the cache holds -- the system half is `persona.system_for("him")`, byte for
  byte what the reply behind it is about to send, and the tool definitions are
  constant bytes for the character;
* nothing enters her thread -- the pick is a row in the save, and what reaches
  the record is the send, recorded when the bubble leaves, exactly as before.

And the decision it replaces was a guess: code matched her English sentence
against Japanese post text and Japanese picture descriptions by shared words
and two-character runs, and the morning that guess went wrong is the whole of
`docs/x-account.md` §2.2.

**What is offered, and what may come back.**

| | |
|---|---|
| when | the program's `before_reply` hook, immediately before `persona.generate`, on both reply paths; her phone free, nothing of his waiting, nothing of hers in flight; once per pending thought; never in a sim, never in a replay |
| the system half | `persona.system_for("him")`, unchanged and unshared with this call |
| the moment | her own sentence about the thing she wanted to show him, both clocks, one line of where she is (`scene_brief`), and every post she could send him rendered by the account's one offer builder |
| the tools | `send_this(id)` -- id a string, `required` -- and `nothing()`, no parameters. `tool_choice: auto` |
| words | none. There is no free-text argument in either tool |
| acted on | `send_this` makes that post the only one her reply prompt offers, with the same `[share: <id>]` instruction, so the send path does not fork. `nothing` retires the thought and puts the posts away for the share cooldown |
| the config | section `share_pick` (`enabled`, `max_attempts` 2), a `share_pick` row in `Config.REQUIRES` reading `has_account`, a `share_pick` entry under `models` on flash at the persona role's thinking and effort, and a `share_pick` row in `Config.ROLE_STANCE` reading `voice` |

**The three faults §14.3 found, each answered in code rather than in a
comment.**

1. *A tool name that was not offered.* The name is checked against the two
   that were, and nothing else is acted on. It called `dislike` once in the
   replay, so this fires in practice, and it logs the name it invented.
2. *Content beside the call.* Dropped, with its length and first line in the
   log. It is her next message to him, written because her whole persona is
   the system half; it is not what this call is for and it is not sent.
3. *An argument in the wrong language.* There is no argument that takes words,
   so there is nothing to be in the wrong language. The words are the reply
   call's, as they always were.

Anything that does not validate -- one of the three above, an id that is not
on the list, arguments that do not parse, no call at all, a call the provider
never answered -- is one thing: **a decision not taken.** The pending thought
is left exactly as it was, the three candidates code matched hold that one
reply, and the pick is tried again at her next free moment up to
`share_pick.max_attempts`. Nothing is ever sent that she did not name.

**The money.** One flash call per thing she wants to show him. §14.6
measured $0.00085 a pick over forty-six of them with 61% of prompt tokens
cached; a cold rebuild of the 05:09 moment on a copy of the save, with no
warm prefix in that process, came back at $0.00151 on 10,591 prompt tokens
and 108 completion tokens, served by Together in 6.5 s. Live, behind a
prefix the reply call keeps warm, it is a tenth of a cent and a handful of
picks a day.

**What is not done here, and deliberately.** The scroll pick §14.5 failed
(a like on every one of sixteen scrolls) is not wired and nothing above
changes that: `Curation` still holds the likes, the reposts and the
unfollows, and the caps are still code's. This wires the ONE decision the
replay showed her making well -- which of the posts she has already looked
at is the one she meant.

## 17. Live: the model chooses, code is the backup

**An answer with no usable choice is asked once more.** The same messages
and one line in her language saying to answer with one tool call and
nothing else (or one JSON object, on the text transport); both calls are
counted in the moment's spend and the row carries `asked_again`. If the
second answer is not a pick either, the backup decides as it always did.
**The reasoning that comes back beside the pick is kept**, as kv
`pick_aside` (`{ts, text}`, one row, overwritten), and read by the NEXT
moment inside three hours of her clock as one line of what she was
thinking when she was last asked. Nothing else reads it: it is what she
was thinking and not something she said, so it stays out of the diary and
the private-thought role.

**The names `message_friend` accepts are her own circle**, listed in the
argument's own description, for a character who reads a world she does not
keep -- with one line saying the rest of them are talked to in the group
chat. Being offered a person the partition rule will always refuse is a
choice she can never learn from. Beside it in the same block: what she has
already been to each of them with today, and the sentence naming anybody
off the list because she went to her and had nothing to say
(`sim/said_today.py`).

The owner's decision, in his words: *"I want to replace the current system in
which code makes things happen. We can have it as a backup, but in general I
want the model to actually be choosing."* And on what he expected of this
step: *"Explicit goal and scope is to have it implemented and running; that is
my expectation. I expect the model to use it. I expect the model to be given a
fair opportunity to use it."*

So `pick.shadow` is false and it is implemented. At every moment code can
offer her one, she is handed what a person with a phone has in front of her
and the tools she has a path to, and **what comes back is what happens**. The
impulse function, the reply delay and the group-chat roll are still there and
still run -- as the backup, for a moment she was not asked at or did not
answer. `sim/pick.py` is the call and the record; the seams are named below.

### 17.1 When she is asked

Four moments, each a point where something could be done and her phone is in
her hand. Which ones are live is `pick.moments`.

| moment | where it is asked from | what has just happened |
|---|---|---|
| `block` | `App.maybe_impulse`, on a director tick | a stretch her plan gives her a free phone has started |
| `scene` | the same call site | what she is doing has changed inside one |
| `beat` | the program's `loop_pass`, after the beats are delivered | something landed from her own people |
| `inbound` | `App.maybe_reply`, before the delay plan is made | he has just written and nothing has decided what to do about it |

`block` and `scene` are the same call site because the difference is a
question `PhonePick.due` can answer and the caller cannot: it is a block
moment when the block has not had its look, a scene moment when it has and
what she is doing has moved since (kv `pick_block`, kv `pick_scene`), and
neither when both have already been asked at.

**The inbound moment is a different question**, so it has different tools. The
old §15 moment opens "your phone is in your hand and nobody is waiting on
you", which is a false sentence to hand somebody whose boyfriend has just
written to her; this one opens with what he wrote and how long it has sat.

### 17.2 What is offered, and what it costs her

Fixed for a character and a kind of moment, off her sheet
(`PhonePick.offered`), so the definitions are constant bytes behind a cached
prefix.

| tool | offered to | what it costs her, in the tool's own description |
|---|---|---|
| `nothing(until)` | everybody, at every moment but his message | everything that is waiting is still waiting when she picks it up again |
| `text_him(intent)` | a character with a chat with him | she started it, so it is his to answer, and she is the one who went first |
| `open_group_chat` | a character in a world she OWNS | once she has said something she is in it, and it will want her for a while |
| `message_friend(name, intent)` | a character in a world | the other one will answer, and the conversation is then hers to keep up |
| `look_at_his_machine` | unless her sheet says `sees_him: none` | she will know, and she can never say how she knows (the program's words) |
| `open_feed` | a character with an account | time goes, and she may come out of it wanting to show him something |
| `reply_now` / `reply_later(when)` / `leave_it` | on his message, a character with a chat with him | being in it; him watching it sit there unanswered; it staying unopened for as long as she leaves it |

`leave_it` does not mark his message read. Opening it and saying nothing is a
different act and a loud one, and it is hers to decide somewhere else
(`sim/withholding.py`); it is not on this menu.

Measured on the four registered characters: six at the phone and three on his
message for the first; three and three for each resident; **two and none for
the reader of somebody else's world** -- her sheet says she has no chat with
him, and the group chat belongs to whoever keeps the world, so what is left is
putting the phone down and writing to one of her own people
(`docs/shared-world.md` section 9). A tool that could only ever be refused is
not offered: it is a line she reads and pays for on every call.

**Every description says what the tool costs her.** §14.5's failure mode was a
model handed a menu of six good ideas with no price on any of them, which
picked the interesting item every time; the prices are the answer to that, and
`nothing` is offered as a real option rather than the leftover one.

**`nothing` is never first and is not last every time.** It moves position
once a day (`PhonePick._nothing_at`), not once a call: a tool list that moves
every call is a cached prefix thrown away every call.

### 17.3 What she is handed

The system message is `persona.system_for("him")` byte for byte, built under
`_peek` so nothing is drawn -- the same string her reply builds, so the pick
rides the prefix the provider has already cached for her. Everything that
moves is the last user message:

* one line saying truthfully what kind of moment this is;
* both clocks with the part of the day on each; where she is and with whom out
  of the day's one truth; her gauge line;
* his last message and how long he has been quiet, `Receipts.line` (the same
  sentence her reply reads, so his silence is not described two ways), her own
  last message, and what her sight of his machine last showed;
* **the last of what the two of them said**, six turns stamped on her clock,
  read off the record rather than out of `sim/thread.py` -- the thread is
  rebuilt byte-identical for the calls that write her words, and a second
  reader of it here would be a second thing that can move those bytes;
* what is unanswered in her own rooms;
* **`persona.carried_for()`**, the same `<carrying>` block both her rooms place
  after the thread, so a fact she is holding in her reply is a fact she is
  holding here -- plus an open question about him, something off her feed she
  meant to show him, and what she woke up wanting.

All of it is in the wording she is instructed in (`sim/lang.py`), and the one
that names how she comes to know what he does is the program's
(`pick_look_tool` and `pick_look_cost` in each program's words table), never
the library's.

### 17.4 The seams

Every tool has a seam that already existed. Nothing here is a second way to do
something the system could already do.

| she picks | what runs | whose |
|---|---|---|
| `nothing(until)` | nothing, recorded as her choice with the hour she named | -- |
| `text_him(intent)` | `App.write_him_first`, the path the impulse function's yes runs down, with her `intent` as the hint the reply prompt is built from | the runtime's |
| `look_at_his_machine` | `App.look_at_phone` | the runtime's |
| `reply_now` / `reply_later` / `leave_it` | `App._plan_from_pick`, which writes the reply plan the delivery path already runs on | the runtime's |
| `open_group_chat` | `Exchange.self_open(scene, chosen=True)` | the program's |
| `message_friend` | `Exchange.open_with(who, intent, scene)`, a one-to-one door beside the group one | the program's |
| `open_feed` | `Social.start_look()` | the program's |

The split is the one that already governs this file: the runtime carries out
the tools that are the mind's and the relationship's, and hands the rest to
the program's `pick_act` hook, because what a group chat, a friend and a feed
are is the program's to know and shared code never names one. A program with
no such hook -- the resident's -- simply has none, and a tool it cannot honour
is recorded as one, not turned into something else.

**`text_him` works from any moment.** Extracting `App.write_him_first` out of
`maybe_impulse` is what makes that true: picking him at a moment that is not
already on the write-first path runs the same path from there, so where she
was asked never changes what happens when she picks him.

**An intent is a seed and never words to send.** That is the answer to the
wrong-language fault §14.3 found: her words are still written by the call that
writes her words, in both rooms.

### 17.5 The gates code keeps, and why each one

Every one of these is a thing she CANNOT do, or a thing that costs money.
Nothing here is code deciding whether she WANTS to -- that is the whole of what
moved.

| the gate | where | why it stays |
|---|---|---|
| her phone access off her own schedule | `PhonePick.due`, `App.phone_access` | no phone means no call at all: the illusion this project is for is that she cannot read or send when her day does not give her the phone |
| a live run only, never a sim and never a replay | `PhonePick.due` | a replay must not open rooms or send |
| the day's cap, `pick.max_per_day` | `PhonePick.due`, kv `pick_counts` | the money |
| no two looks inside `pick.min_gap_minutes` | `PhonePick.due`, kv `pick_last_ts` | the money, and it is what keeps four moments from being four times the spend. It is on every row of the record |
| one look per block and per scene | kv `pick_block`, kv `pick_scene` | a restart mid-block must not ask the same moment again on the next tick |
| `with_him: none` | `PhonePick.offered` | a character with no chat with him has no `text_him` and no inbound moment at all |
| the exchange's own reasons a room cannot open | `Exchange.self_open_reason`, `Exchange.open_with_reason` | already in a conversation, the chat done for the night, the friend asleep or away by the plan, the day's exchange budget, and the room-ownership rule |
| the account's hours, minimum gap, daily cap and session pacing | `Social.may_look` | the account acts in the world and its caps are his |
| the cost cap on a look at his machine | `Phone.look` | choosing to look twice inside it is her looking and finding nothing new, not a second paid read |
| a provider failure | `LLM.call_tools` | logged, written to `missed_calls` for `App.catch_up`, and the backup decides |

Two things that were code's guesses at whether she wants something are now
hers and are skipped when she has picked: the score and the roll behind the
group chat (`self_open`), and the boredom probability behind a scroll (the
`not now` answer from `may_look`). Everything else in both is untouched.

### 17.6 The backup, and when it decides

The backup is what ran before: the impulse function's score and roll for
writing to him first, the noticing-and-composing timers for answering him, and
the group-chat score for opening a room. It decides when:

* the pick section is off for this character (`pick.enabled` false), or the run
  is a sim or a replay;
* this was not a moment to ask at -- the phone is away, the day's cap is spent;
* the call was never answered (a missed call);
* nothing that came back was a pick: a tool nobody offered, arguments that did
  not parse, a required argument missing. Each is recorded as invalid with the
  reason and is **never** acted on.

And it does NOT decide when she was asked a moment ago and has simply not been
asked again yet (`PhonePick.holds`, kv `pick_standing`). One decider per
moment: the score does not write to him twenty minutes after she put the phone
down. That hold lapses as soon as the reason she is not being asked stops
being "too soon" -- past the day's cap the backup is what decides again, so
one `nothing` in the morning cannot silence her for the day.

Every log line says which of the two decided:

    [impulse] False (score 41 < 62) | his side: read 12m ago
    [pick] live at the block moment -- she picks: message_friend {"name": "…",
      "intent": "answer her about the yukata"} | impulse: False (score 41 < 62),
      score 41/62 | her room: sitting on the bed | via tools | $0.00151
    [exchange] she writes to … on her own: answer her about the yukata
    [impulse] not acted on: her own answer at the last moment stands (nothing)
    [impulse] not consulted: she chose to write to him first -- poke him because …

### 17.7 The wire

Native tool calling through OpenRouter, exactly as §§4, 7 and 9 describe it:
`tools` and `tool_choice` at the top level, `provider.require_parameters` on
whenever tools ride, `parallel_tool_calls` never sent, the streamed fragments
reassembled by `index`, and `finish_reason: "tool_calls"` a normal answer
rather than an empty one.

**JSON in her text is the fallback, and the receipt decides.** A host that
takes a request carrying tools and answers as if none were offered is named in
`api.hosts_without_tools`, spelled as the receipt spells it ('Sakana AI', not
'sakana'); the transport for the next pick is chosen from the host that
actually served the last one (kv `pick_host`), never from a guess about the
pin -- because the pin may fail through to another host for the same slug and
only the receipt knows which one answered. If a tools answer comes back with
no call at all from a host on that list, the same moment is asked once as
text. The text path goes through `LLM.call_json`, so a malformed answer is
asked again `api.json_retries` times with the bad answer in the conversation
and the raw text is never stored as the decision. Both paths produce the same
shape, so the whitelist and the record cannot tell them apart.

`max_tokens` stays at the API maximum for the role, like every other role.

### 17.8 The record, and reading it back

One row in kv `picks` (last 200), written the instant the answer exists and
before anything is done about it: the character, the stamp in machine local
time and the same instant on her clock, both clock readings as text, the
trigger, her phone access, the block, where she was, the moment verbatim,
every returned call with its validated arguments, whether any was invalid,
what the impulse function answered at that same tick with its score and
threshold, the mode (live or shadow), the transport, the minimum gap in force,
the cost, the prompt and cached token counts, the model and the host from the
receipt.

**What happened is filled in afterwards.** `acted`, `acted_why`, `fallback`
and `fallback_why` are written by `PhonePick.note_acted` once the seam has
run, so nothing on the record claims a message, a room or a look before the
thing itself (`reconcile.py`). A pick that went to write to him and produced
no bubbles is recorded as that, not as a message.

The block marker and the day's count are written BEFORE the call goes out: a
stop is a kill, and a marker written afterwards would let a restart ask the
same moment again on the next tick.

`/pick [date]` prints a day: how many moments she was offered and of which
kind, what she picked and how often, how many were acted on, where the backup
ran and why, how many answers had something invalid in them, on how many
moments she and the impulse function differ about writing to him, and then
each moment -- what she picked, what the impulse said, what was done, what the
record shows happened after it, and what it cost. The ops payload carries the
same counts for today. Every boot logs one line saying live or shadow, which
moments are on, the caps and the tools she has.

### 17.9 The money

Measured by building the request on a copy of each save and counting it, with
the estimator corrected by §14.6's own measurement (the host counted 11,648
where `Memory.tokens` said 17,713):

| | the first character | the reader of the shared world |
|---|---|---|
| system half | 39,809 chars | 8,231 |
| the moment | 34,453 | 5,181 |
| the tool definitions | 2,486 | 931 |
| the host's own count, about | 19,900 tokens | 3,100 |
| behind the cached prefix | 55% | 64% |
| a pick | about $0.0015 | about $0.0002 |
| a day, if every one of the 30 allowed is spent | $0.044 | $0.007 |

**It is more than shadow mode's tenth of a cent, and the reason is
`carried_for`.** §15's moment was about 11k tokens; this one is about 20k,
because what she carries moved into it -- and the provider caches a byte
prefix, so everything behind the system half is fresh on every call. That is
the price of her deciding while holding what she actually holds. The levers
are `pick.max_per_day` and `pick.min_gap_minutes`, both on every row of the
record, and taking `carried_for` back out of the moment would return it to
about a cent a day.

### 17.10 What is not done here

* **The scroll pick is still not wired.** §14.5 failed it (a like on every one
  of sixteen scrolls, never nothing, never a pick with a consequence) and
  nothing above changes that.
* **A reader of somebody else's world has no group room of her own.** Her
  circle's one-to-one rooms are hers; a group chat for her own circle does not
  exist, so she is not offered one.
* **`reply_later` reads an hour and not a phrase.** "21:30" becomes a time;
  "after the bath" is kept verbatim on the record and the wait is
  `pick.later_default_minutes`. Her words are never rewritten into a time she
  did not name.
* **Only the first character and the reader run it.** `pick.enabled` is false
  for the two residents, which is the owner's decision of 2026-09-07 taken
  when the pick was a shadow; their sheets do give them three tools each, so
  that is a switch and not a rebuild.
