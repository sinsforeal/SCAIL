# The model harness -- providers, hosts, and the ranking

<!-- doc: reference -->

Spec of record for `yukarin/tools/llmx.py`, `yukarin/tools/providers.py` and
`providers.db` (the extraction side), for `tools/bot_model_test.py` and
the findings that chose the live bot's provider (§6), and a pointer to
the bot's own client, `llm.py` (PROJECT §1 *Providers*). Dated notes:
HISTORY.md §19 and, for the bot, §1. The pipeline that runs on the
extraction side: `docs/yukarin.md`.

## 1. Why it exists

Every DeepSeek call the bot and the extraction make goes to the official
endpoint at list price, and almost all of the output is reasoning. The
same model revision is served by thirty-odd hosts on OpenRouter at a
quarter of the price, and other flash-class models sit in the same band.
Two things had to be known before moving any traffic: **which hosts
actually reproduce the official extraction**, and which are unusable.
The answers are in `providers.db`, measured, with a human control.

## 2. `yukarin/tools/llmx.py` -- one client, receipts on every call

    LLMX().call(provider, model, system, user, tag, temperature, extra)
    LLMX().call_json(...)          re-asks an answer that does not parse; never hands raw text on

Providers:

- `deepseek` -- the official endpoint (key from `config.json`). It applies
  a low default output cap when the field is absent, so it is sent the
  API maximum explicitly; **no other provider gets a `max_tokens` field at
  all** (his rule: no output limits). A `length` finish anywhere is a
  fault to read, not a setting to raise.
- `openrouter` -- key `secerts/openrouter.txt`; `extra` merges into the
  request body (the provider pin lives there); the recommended
  attribution headers are sent.
- `or:<slug>` -- DeepSeek v4 flash 0731 through OpenRouter pinned to one
  host, `allow_fallbacks: false` in the bench (the live bot lets the pinned
  host fail through to the next host for the slug, `api.host_fallback`), so
  `served_by` is that host or the call fails. **The bare `deepseek-v4-flash` slug serves the old revision**;
  the pipeline names `-0731`. Every pinned call carries
  `reasoning: {effort: high}` because the hosts default to little or no
  reasoning while the official endpoint reasons by default -- measured:
  CoreWeave without it 4.7k output tokens and 12 mechanisms, with it 44k
  and 16; the `max_tokens` and native `thinking` request forms broke its
  JSON. `oi` is an alias for `or:open-inference`.
- `vertex` -- Gemini on Vertex through the bot's own service account
  (`config.vision`), region `global`, thinking budget set explicitly
  (unset, Gemini 3.7 flash returned ~2.7k tokens and 5-6 mechanisms per
  episode). The token refresh is under a lock; ten threads refreshing at
  once handed four of them a half-refreshed token (4x 401).

`YPROVIDER` (default `deepseek`) is the provider every pipeline tool uses;
`YPROVIDER=or:deepinfra` or `YPROVIDER=oi` moves the whole pipeline.

Every call is a line in `yukarin/logs/calls.jsonl`: ts, tag, provider,
model, endpoint, pin, **served_by** (OpenRouter's `provider` field;
`official`; `vertex:<region>`), status, seconds, tokens in/out, reasoning
tokens where reported, finish reason, answer length, error text. The raw
answer text is in `logs/raw/<tag>_a<attempt>.txt`. A 429 backs off for
tens of seconds per attempt (upstream rate limits are real; three-second
retries were useless).

## 3. `yukarin/tools/providers.py` -- the ranking and its database

    python yukarin/tools/providers.py run              every DeepSeek-0731 host cheaper than official, 2 episodes
    python yukarin/tools/providers.py run glm qwen gemini      the other models' rows
    python yukarin/tools/providers.py fable <slug> <ep> <same> <compat> <missing>   the human match, entered by hand
    python yukarin/tools/providers.py rank             host_health + ranking -> providers.db, providers_ranking.md

**The instrument** is the frozen v2 extraction prompt on two hand-read
episodes (one from the first year, one from the third), pinned with no
fallback, reasoning requested. Two episodes, not ten (his call: "we don't
need to waste multiple runs, just do 2 shot").

**Who is tested**: every host of DeepSeek-0731 with input price under the
official $0.22/M (and output under $0.66/M) -- the threshold is the
official price, nothing above it; glm-5.3-flash at its cheapest tier of
hosts; qwen3.8-flash at its one host; Gemini on Vertex. The official
endpoint's own v2 maps are a row too, matched the same way.

**The control is Fable.** Fable produced the same deliverable on the same
two episodes (`extract/providers/fable/`, 32 and 33 mechanisms, every
quote verified), and the `fable_*` columns of every row are Fable's
by-hand match of that row's list against those: same / compatible /
missing per mechanism. No model judges anything (the earlier glm judge
was removed and its values cleared). The ranking sorts on recall vs
Fable, then quote validity, then price.

**Speed** is output tokens per second with thinking included -- a host
that skips the reasoning pass looks fast per episode and is not -- with a
speed rank column and a by-speed section in the report.

**Database** `providers.db`:

- `providers` -- the model page: slug, name, endpoint tag, quantisation,
  prices per M in/out, context, max output. Other models' hosts are keyed
  `glm:<host>`, `qwen:<host>`, `gemini:vertex`; the human control is
  `fable`, the official endpoint `official`.
- `runs` -- one row per row x episode: served_by, seconds, tokens,
  mechanisms, the official run's count, verified quotes, frame length,
  error, `reasoning` (effort=high), and the `fable_*` match counts. Rows
  made before every host call carried the reasoning request live in
  `runs_noreason`.
- `host_health` -- per host from the call log: calls, ok, 429s, other
  HTTP errors, empty answers, last error, verdict: **UNUSABLE** (never a
  usable answer), **FLAKY** (rate-limits two concurrent requests, or
  drops answers), **OK**. The report ends with the hosts to avoid.
- `ranking` -- the computed table (recall vs Fable, quote validity,
  mechanism ratio, seconds, output tokens, tok/s, speed rank, note).

On disk the row directories replace `:` with `__` (Windows).

## 4. What the ranking found

Against the human control on the two episodes (share of Fable's 65
mechanisms also found, same or compatible); every usable row matched by
hand, the rest recorded as failed with the reason:

- **qwen3.8-flash at Alibaba** leads (~0.79), 100% valid quotes, second
  fastest by throughput -- and rate-limits under concurrency (run it a few
  at a time).
- **The official DeepSeek endpoint is mid-pack (~0.65)**: strong on the
  dense first-year episode, weak on the third-year one.
- DeepSeek-0731 at **Relace** (fp4, 0.73) and **CoreWeave** (fp8, 0.70)
  score above official on the third-year episode, at CoreWeave's speed
  matching qwen's -- and neither ever returned the dense first-year
  episode (CoreWeave truncated it on every attempt; Relace errored and
  reset), so each is a one-episode row.
- **Parasail** (fp8) is the best host with both episodes, 0.60, at half
  the throughput.
- The fp8 hosts with two clean episodes, **DeepInfra** and **Together**,
  sit around 0.52-0.54 at roughly half the throughput.
- glm-5.3-flash is consistent across its hosts (0.35-0.51), almost never
  misquotes, and reads about half as deep as official on the dense
  episode.
- Gemini 3.7 flash with thinking on: ~0.39, few entries, the most precise
  ones.
- **Unusable**: OpenInference (the cheapest; will not run the reasoning
  pass even when asked -- 0.09), DigitalOcean (garbage/empty), Baidu and
  BaseTen (429 every time), Venice and Inceptron (empty answers), Makora
  (244 keyword entries on one episode, fine on the other), Morph (generic
  labels), Ambient and Mancer (no parsed answer on an episode before the
  run was stopped).

The model's claim about its own identity is not evidence: a DeepSeek
call pinned to the DeepSeek provider answered "I am Claude".

## 5. Operating notes

- The official DeepSeek account ran out of balance during the extraction
  (~$11 at list price for ~16M output tokens, nearly all reasoning). Both
  the extraction and the live bot moved to OpenRouter, and neither
  character now runs on the first-party endpoint: the official provider
  is still defined and pinnable by hand, and a call on it fails while the
  balance is empty.
- OpenRouter has no platform rate limit on paid models; every 429 was an
  upstream host refusing, and the pin forbids the reroute OpenRouter would
  otherwise do silently.
- `yukarin/tools/control.py` was the earlier ten-episode matrix; the two test episodes'
  files were merged into the database and the rest retired to
  `data/retired/<ts>/yukarin_control_10ep/`. It is superseded by
  `yukarin/tools/providers.py`.


## 6. The bot on the hosts -- the persona-role test and what it decided

Running the bot and extracting a persona are different tasks (his words),
so the bot got its own test, `tools/bot_model_test.py`: the persona role's
last two real calls from run `2026-08-31_18-16-30` (her 07:41 and 07:52,
the whole 150-message thread, thinking on, ONE line demanded), replayed
as sent on each candidate with the role's own settings, no output limit,
host pinned with no fallback; the official DeepSeek reply the bot used
beside them, and a reply written by hand after reading the thread (Fable)
as the control. Twice: at the role's temperature 1.3
(`data/model_test/20260831_persona/verdict.md`) and at 1.0 for every
provider with a 30 s cap (`.../20260831_persona_t1/verdict.md`); every
answer verbatim in each `report.md`. Ratings 0-10 are the hand read
against the bible, the style rules and the situation.

    python tools/bot_model_test.py extract logs/<run> [n]      the last n calls of every role -> data/model_test/<ts>/cases.jsonl
    python tools/bot_model_test.py run <dir> <provider> [workers] [timeout s]
    python tools/bot_model_test.py show <dir> <case> [tail]    the case as the bot sent it
    python tools/bot_model_test.py report <dir>                summary table + every answer side by side

The tool writes every raw response the moment it lands (`<dir>/raw/`) and
records an empty answer as a result rather than re-asking in silence --
two paid answers were lost on 2026-08-31 to a silent retry that was then
killed. One attempt per case; a long batch goes to the background.

**Findings, temperature 1.0 (after the bot's own cleaning of the answer):**

| provider | #39 | #48 | s | what decided it |
|---|---|---|---|---|
| DeepSeek 0731 @ Together | 6 | 8 | 4-6 | level with the official endpoint; ~170 thinking tokens like official's 459; never a form the bot cannot clean |
| official DeepSeek (at 1.3) | 4 | 8 | 3-6 | the reference; account empty |
| qwen3.8-flash @ Alibaba | 8 | 8 | 6-11 | the best lines; wrote the history's `[voice note you sent with it: …]` label on both (now caught); 429s under concurrency |
| glm-5.3-flash @ Z.AI | 6 | 8 | 9-13 | strong at 1.0 -- which is its ceiling: it refuses the role's 1.3 (HTTP 400, code 1210); voice lines garbled |
| glm-5.3-flash @ Relace | 3 | 4 | 3-6 | invents images, keeps a ledger |
| Gemini 3.7 flash (Vertex) | 6 | 4 | 14-24 | never broke the frame, writes proper voice lines, dodges the substance, slow |
| DeepSeek @ CoreWeave | 5 | 0 | 2-8 | empty content on 3 of 4 long threads (the reasoning reaches an answer, no text follows) |
| DeepSeek @ Relace | 2 | -- | 249 | 13k thinking tokens for one muddled line |
| DeepSeek @ DeepInfra | -- | 7 | 449 | the line is fine; seven minutes is not a reply |
| DeepSeek @ Parasail | 0 | -- | 45 | word salad, Japanese and an emoji in his chat |

What the two rounds established:

- **Frame-breaking follows the model, latency follows the host.** The same
  DeepSeek revision is 4 s at Together, minutes at Relace and DeepInfra,
  nothing at CoreWeave: `reasoning.effort=high` means a different budget
  on each host. qwen and glm copy the history's labels; DeepSeek on any
  host that answered did not (Parasail excepted, which fell apart).
- **The timestamp label is not a discriminator.** `[07:53 · read 07:55 ·
  you, to him]` was typed by five of six providers at 1.0 and by the
  official endpoint on 2 of its 4 persona answers in the run; the bot
  strips it (`persona._clean`). The voice-note label it did not strip;
  `persona._extract_voice` now takes any `[voice…: …]` form as the voice
  line, so qwen's and glm's habit costs nothing.
- **Temperature 1.0 beat 1.3 for every provider** on these two cases,
  official included; the persona role runs at 1.0 now.
- **The extraction ranking does not transfer.** qwen led the extraction
  (0.785 recall vs the human read) and wrote the best bot lines, but the
  bot's chat is a long multi-turn thread with a strict frame, and the
  ranking never tests that. CoreWeave and Relace, above official in the
  extraction, are out for the bot on delivery alone.
- **Z.AI cannot run the persona as configured** (temperature ceiling 1.0).

**Decision (his):** both characters run through the Together provider,
one provider and no fallback (a fallback can change the model, not just
the host); the official endpoint and `qwen` are defined and pinnable by
hand. Every role of the first character is DeepSeek v4 flash 0731 there.
The second character's nine roles that write in her voice -- her replies,
her diary, both reflections, her wonder, her morning, her anticipation,
her approach, her spiral and the rewrite of a belief about herself -- are
`kimi-k3` on the same provider (the bench that chose it is
`docs/yukarin-voice-models.md`) and her remaining sixty-six roles are
flash. A call that fails after `api.max_retries` is logged and written to
the missed-call list for the catch-up, never answered by a different
model under the same name. The provider rule and the ops commands are in
PROJECT §1 *Providers*; the outage catch-up in §8.2. (The chain, the
strikes and the tier this section once described are gone.)

Two samples at one temperature: the official/Together/qwen differences
are inside sampling noise; the disqualifications (empties, minutes of
thinking, the temperature cap, garbage) are not.


## 7. Output caps -- what a host advertises, and what it does

A long reasoning call dies in three different ways, and each host has its
own. **The published `max_completion_tokens` is not a promise**: sending
it changes nothing about where the host actually stops.

| host / model | advertised | what it does | how it reads in `yukarin/logs/calls.jsonl` |
|---|---|---|---|
| Together, DeepSeek 0731 | 943,718 | **truncates at 131,072** on some calls, whether or not the field is sent | `out 131072`, `chars 0`, `finish length` -- to the token, five times |
| Together, DeepSeek 0731 | 943,718 | on others runs past 200k and is **aborted at ~1,800 s** -- OpenRouter's request wall, not the client's (a read timeout does not trip while the response streams) | `s 1800.4-1800.6`, `out 189224` and `219556`, `chars 0`, `finish error` |
| Alibaba, DeepSeek v4 pro | 393,216 | **cuts on time**, at ~596 s, with nothing written | `s 596.1`, `out 51976`, `chars 0`, `finish error` -- four calls, all within a second of each other |
| Alibaba, qwen3.8-flash | 131,072 | truncates at 65,536 with the field absent | `out 65536`, `finish length`, 23k chars of JSON cut mid-list |
| DeepSeek official | 393,216 | honours the field | the bot sets it; PROJECT §1 |

Three lessons, all paid for. **The failure costs the whole call**: every
one of these returns `chars 0`, so ten minutes and 50-220k output tokens
buy nothing -- there is no partial answer to salvage. **A truncation and
an abort look nothing alike**: `length` is a cap, `error` with usage
present is the host giving up, and only the second gets worse when you
raise a limit. And **131,072 is not a ceiling** -- it is where Together
truncates when it truncates; a call that gets past it runs until the
1,800 s wall. There is no number that makes a runaway safe. The only
lever is keeping the expected output well under both, which is what the
chunk size is for.

"No output cap" (his rule) therefore means sending the endpoint's own
maximum explicitly, and then not trusting it. `yukarin/tools/llmx.py` reads the figure
once from OpenRouter's public endpoints table (`_endpoint_max_out`) and
sends it for any pinned host but CoreWeave (whose JSON broke under a
`max_tokens`, harness §2); the client's own timeout is 1200 s for a
cluster call, because a healthy one has run 592 s and the client must
never be what cuts an answer. Every row in `yukarin/logs/calls.jsonl` carries
`temperature` -- the pipeline has always run at 0.2, `LLMX.call`'s
default, never overridden by any tool (verified against the session
record on 2026-08-31 before the reduce ran).

**`yukarin/tools/cap_probe.py` measures a host before the work does.** One
call that forces a long generation (count to 100,000, which a model will
do until something stops it), the finish reason read as the answer:
`length` at N is a hard ceiling of N, `stop` at N means the ceiling is
above N, `error` with no content means the host aborts rather than
truncates. Results accumulate in `yukarin/logs/caps.json`. A host is
probed before it is trusted with a stage.

**Sizing the reduce's calls, so the cap stays a non-issue.** 1,842
mechanism observations; a cluster line is ~51 tokens (measured on the
qwen call). At 600 entries a level-1 call is ~31k tokens in and its
*content* out is fixed by the data -- every member key echoed once (~12
tokens) plus a name and a function per cluster -- ~18k tokens; at 250,
~13k in / ~7.5k out; the level-2 merge ~41k in / ~15k out whatever the
chunking; a synth call is ~1.7k in for ten members and ~250 out. Nothing
here approaches any limit. What fills the budget is reasoning: on
Together the same model spent 39k-131k+ tokens thinking over a 6k-token
episode. So smaller batches do not cut what comes back; they cut how
much thinking one call can run away with, and what one lost call costs.

**Measured, at Together, one entry-chunk per call:**

| entries per call | in | out | seconds | result |
|---|---|---|---|---|
| 200 | 9,479 | 52,446 | 323 | stop, 122 clusters -- 79 of them singletons |
| 400 | 20,882 | 74,639 | 592 | stop, 71 clusters |
| 400 | 19,763 | 85,215 | 488 | stop, 130 clusters (the retry of the row below) |
| 400 | 19,763 | 131,072 | 880 | **length, no content** |
| 400 | 21,316 | 131,072 | 862 | **length, no content** |
| 600 | 30,431-31,149 | 63,427-127,501 | 291-506 | stop, three of three |

Output does not scale with input, and time tracks output: doubling the
chunk from 200 to 400 cost 1.4x the tokens and 1.8x the seconds, and put
three of five first attempts into the 131,072 ceiling. The other end
matters too -- a narrow window clusters badly, because a mechanism only
merges with itself when its episodes land in the same call: 200 entries
gave 122 clusters where 400 gave 71. The setting is a squeeze between a
host's ceiling above and the clustering's quality below; 300 is where it
sits for a flash-class model.

The run of record: `YPROVIDER=or:together YMAP=v2 YCHUNK=300`, clusters
cached per chunk (`sheet/l1_v2/`) and whole (`yukarin/sheet/clusters_v2.json`),
every synthesised cluster written as it lands (`sheet/synth_v2/`), so a
rerun asks only for what is missing, and the merge in rounds capped at
`YMERGE` (120) records a call.

**Parasail was tried for one run and dropped** (2026-09-01). Four level-1
calls and a probe were enough to exhaust it: every further call came back
429 with `"limit_source":"upstream_provider_shared_pool"` -- the limit is
on a pool shared across OpenRouter's users, so it is not raised by
spending more, and a stage of 200 synth calls on eight workers could not
run there at all. It is also the host that scored 0 in the persona test
(word salad at 1.3, harness §6), and the rerun at 1.0 that would have
given it a fair reading is the thing the 429s blocked. His call: "if the
garbage is rate limited don't use it."

`YPROVIDER=qwen` is an alias for qwen3.8-flash pinned to Alibaba with
`reasoning.effort=high`, the row that led the ranking; a 429 there waits
(30 s, 60 s, ... ten times) instead of spending an attempt.

**Pro.** `YPROVIDER=pro` is DeepSeek v4 pro pinned to Alibaba (the host
the bot's pro roles run on; 17 hosts serve it on OpenRouter, Alibaba at
$1.42/$2.83 per M, 393,216 output maximum, sent explicitly). His call on
2026-08-31 after the flash merge ran away: "switch reduce to pro model".
The merge went pairwise from that run on and then to rounds (below);
`yukarin/tools/reduce_merge.py` rebuilds it from the level-1 answers on
disk when a run died after level 1.

## 8. What a host does to a long call, and what the pipeline does back

Three findings about hosts, and one answer that covers all three.

**A host cuts a long generation, and the shape of the cut differs.**
Together truncates at 131,072 output tokens (`finish length`) on some
calls and lets others run to OpenRouter's 1,800 s request wall
(`finish error`, 219,556 tokens once); Alibaba cuts DeepSeek pro on time
at ~596 s; qwen at Alibaba truncates at 65,536. Section 7 has the table.
No `max_tokens` value prevents any of it.

**A cut used to cost the whole call.** Unstreamed, the body of a
truncated response is empty: ten minutes and 131k output tokens bought
`chars 0`. That happened eight times in one night.

**The answer: stream, keep what arrived, and ask for the rest.**
`llmx.call` streams every request (`stream: true`,
`stream_options.include_usage`), assembles the content from the deltas,
and records `finish` and usage from the stream. When the finish is
`length` or the stream is cut, `llmx.call_long` hands the model its own
partial answer as an assistant turn and a user turn telling it to
continue from exactly where it stopped -- up to four instalments. The
model's compliance is not assumed: `llmx.objects()` reads only whole
JSON objects out of the instalments, stitched and then scrubbed of the
code fence and the "Continuing:" line a model writes anyway, so neither
the nudge nor its echo can reach the data. An object severed by the cut
is recovered from the joined text (a continuation begins mid-string,
which inverts quote parity if a piece is scanned alone).

`yukarin/tools/continue_test.py` proves that path without spending a
call: a fake host streams an answer cut mid-object, then answers the
continuation with a fence and a preamble. It asserts that the second
request carried `system, user, assistant, user`, that the nudge was
injected, that all four clusters come back with the severed one whole,
and that no fence, prose or nudge text survives into the objects. Run it
whenever any of streaming, salvage, continuation or scrub changes.

**Concurrency is measured, not guessed** (`yukarin/tools/conc_probe.py`).
It fires N calls at once, each with its own arithmetic to do, and reads
three things: whether the host accepts them, how much it slows, and
whether the answers are still right and still attached to the right
request. Together, 2026-09-01: clean at 4, 8, 12, 16, 24 and 32 at once
-- 32/32 correct, no 429, median latency 1.4 s to 3.6 s -- while the
reduce already held three level-1 calls, so 35 in flight. Parasail
refused at about six with `limit_source: upstream_provider_shared_pool`,
a pool shared across OpenRouter's users that spending cannot raise, and
was dropped. `yukarin/tools/cap_probe.py` is the same idea for the output
ceiling: one forced long generation, `length` at N meaning a hard N,
`stop` meaning the ceiling is above N, `error` with no content meaning
the host aborts rather than truncates.

**The stages are sequential; the parallelism is inside each.** Level 1
(`YL1WORKERS`, 8) clusters every chunk, then the merge rounds
(`YMWORKERS`, 8) run batch-parallel within a round and sequentially
between rounds, because each round consumes the last one's output, then
synth (`YWORKERS`, 24) writes one entry per final cluster. Synth cannot
overlap the merge: a cluster is not final until the last round has left
it alone.

**A dead run is picked up, not restarted.** Every unit of work is cached
as it completes -- a level-1 chunk in `sheet/l1_v2/`, a merge call in
`sheet/merge_v2/` keyed by what went into it, the merged set in
`yukarin/sheet/clusters_v2.json`, each synthesised entry in `sheet/synth_v2/` --
so a crash costs only the call in flight. `yukarin/tools/reduce_run.py`
reruns the reduce until the sheet exists (20 attempts), printing what is
already cached at each attempt.
