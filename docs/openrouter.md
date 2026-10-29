# OpenRouter: the request this project sends, what it gets back, and what was measured

<!-- doc: reference -->

The dates in this file are part of what it says: a price, a hit rate and a
cache lifetime are true of a host on a day, and the day they were measured is
how a reader knows whether to measure again. Dated NOTES about the project's
own work are still in `HISTORY.md`, under §1 models.

Every live model call in SCAIL goes through OpenRouter (`api.provider`, kind
`openrouter`; the official DeepSeek endpoint is still defined and pinnable but
nothing runs on it). This file is the spec of that seam: the request `llm.py`
builds, the pinned host and the fall-through, the fields read back off the
receipt, and the facts about caching, effort levels and prices that were
**measured** on 2026-09-04 rather than taken from a page. The audit that
produced the measurements, with its scripts, its raw doc copies and its
sixteen paid probe calls, is
`data/retired/20260904_openrouter_audit/REPORT.md`; every quoted sentence from
OpenRouter's own documentation is in `NOTES-openrouter-docs.md` beside it with
its URL. PROJECT.md §1 is the summary and points here; the dated entries are
in `HISTORY.md` under §1 models.

Her prompt itself -- what it is made of and why the front of it must not move
-- is `docs/context.md`. This file is about the wire.

## 1. The request

`LLM._payload` (`llm.py`) builds one body per call:

- `model`: the slug the character's config maps her model name to
  (`api.providers.<provider>.models`). A name with no entry goes out as a
  literal and the host rejects it.
- `messages`: the two halves. The system message is what changes about once a
  day (bible, backstory, self-beliefs, sentiments, speech guide last);
  everything that moves during a day goes in the final user message, after the
  thread. The provider caches a byte prefix, so this ordering is the whole
  reason the cache can hit at all (`persona/sections.py`, `docs/context.md`
  §7). OpenRouter's own advice is the same sentence: keep the front of the
  message array identical between requests and push what varies to the end.
- `temperature`, capped per provider by `max_temperature` (Z.AI refuses above
  1.0).
- `extra_body.reasoning`: `{"effort": <the role's effort>, "exclude": false}`
  for a thinking role, `{"enabled": false}` for one that does not think.
- `extra_body.provider`: `{"order": [<the pinned host>, ...],
  "allow_fallbacks": api.host_fallback}`, only for a slug that has an entry in
  `api.providers.<provider>.order`.
- **No `max_tokens`.** Hosts cap output differently and refuse a number above
  their own ceiling. The API maximum is sent to the official DeepSeek endpoint
  only. One consequence: an effort level is a share of `max_tokens`, so with
  no ceiling sent, `high` is permission to reason for about 80% of the
  endpoint's own ceiling. Observed reasoning is 64 to 1,259 tokens, so it is
  not happening; `api.long_answer_warn` and `api.stream_stall_seconds` are the
  defences if it ever does.
- No `cache_control` (Z.AI and DeepSeek take no breakpoint; it is an
  Anthropic, Alibaba Qwen and Gemini parameter), no `session_id`, no
  `transforms`, no `plugins`, no `response_format`, no `max_price`, no
  `data_collection`, no `require_parameters`.

Two headers are set once per client: `HTTP-Referer: https://scail.local/bot`,
which is what OpenRouter attributes the app by, and `X-OpenRouter-Title:
SCAIL`, which the docs require when the referer is a localhost URL. Both are
correct as they stand.

Every answer is streamed (`LLM._stream`, `api.stream`) so a bad one announces
itself: a stream that ends with no finish reason was cut off and goes round
the retry, `length` with words in it is logged as truncated and asked once
more, an `error` object inside the stream raises with its message, and no
bytes for `api.stream_stall_seconds` fails the call there instead of at the
ten-minute request timeout. `stream_options: {"include_usage": true}` is still
sent and is dead per the docs -- usage now arrives in every response
regardless -- and harmless.

## 2. The pin, and what happens when the pinned host fails

`api.providers.<provider>.order` names, per slug, the host to use. When
`api.host_fallback` is on (the default, his call after Together returned 503
on every kimi-k3 call for a stretch), OpenRouter's other hosts **for the same
slug** answer after it: the model cannot change, only who serves it. The
receipt's `provider` field names who did, and the call's log line ends `via
<provider>/<host>`.

**A pin is written as the host name OpenRouter's own receipt reports** --
`Z.AI`, `Sakana AI`, `Google AI Studio`, `StreamLake` -- not the lowercase
canonical slug and not the endpoint tag. Routing accepts either form: the
display name `Z.AI` reached Z.AI on all four of the second character's GLM
calls and on all sixteen probe calls, and lowercase `together` reached
Together on 3,355 calls. The reason to keep the receipt's spelling is not
routing but the **fall-through detection** in `LLM._call_on`, which compares
the first pinned host against the `provider` name in the receipt (lowercased,
spaces stripped) and logs a fall-through when they differ. Pinned under a name
the receipt does not use, every single call logs a fall-through that never
happened. Check that comparison before changing any pin's spelling.

## 3. What is read back

From the last streamed chunk's `usage`:

- `prompt_tokens`, `completion_tokens`; `completion_tokens_details.reasoning_tokens`
  for the thinking count in the log line.
- `prompt_tokens_details.cached_tokens` -- the only cache-hit field, spelled
  the way both OpenRouter and Z.AI document it. It is the field
  `LLM._call_on` already reads, and it is right: the same line counted
  6,549,387 cached kimi tokens in one day of this project's receipts.
- `cost`, the amount charged to the account, and
  `cost_details.upstream_inference_cost`. **Cost comes off the receipt first**
  (`persona/delivery.py:cost_of`, `tools/llmstats.py:_cost`) and only falls
  back to the local price table. That table is per MODEL (OpenRouter's
  cheapest-endpoint price), not per host: it lists
  `deepseek/deepseek-v4-flash-0731` at $0.065/$0.18/$0.016 per million while
  the pinned host bills $0.14/$0.28/$0.03, so a figure computed from the table
  for a pinned call is an underestimate.
- `cache_write_tokens` is documented but Z.AI's writes are free and
  unreported, so a zero there means nothing either way.

`llm_calls.jsonl` carries `provider`, `served_by`, the slug, the finish reason
and the seconds to the first token on every row, which is what makes the
measurements below repeatable off the log.

## 4. The prompt cache, measured

Everything in this section was measured on 2026-09-04, on this project's own
prompts, against the hosts it actually uses.

**Z.AI caches GLM automatically and reports it.** No parameter, no breakpoint,
no minimum prefix is published. A 15,370-token filler prefix repeated 8.5
seconds later came back `cached_tokens: 15360` and cost one fifth as much,
matching the published cached-input rate exactly. The second character's own
44,046-token persona prompt, replayed as `llm.py` builds it, came back
`44,032 of 44,046 cached`. So the misses in her live log were never
configuration.

- **Reads land on 1,024-token boundaries.** 15,360 of 15,370, 44,032 of
  44,046: the remainder of the last block is not counted.
- **The entry is not readable for roughly ten seconds after the call that
  writes it completes**, at 44k tokens. A replay sent within a second or two
  of the writing call finishing missed; the same bytes sent about fifteen
  seconds after it finished hit. At 15k tokens the write was readable in 8.5
  seconds, so the delay may scale with the size of the prompt. This is one
  measurement either side of a boundary, not a curve. It is also what a live
  0% was: her two consecutive persona calls were nineteen seconds apart, and
  the second went out about seven seconds after the first finished.
- **Twelve minutes idle is cold.** After four consecutive hits, a call ten to
  thirteen minutes after the last touch returned 0, and one after a measured
  twelve-minute idle also returned 0. Her voice calls are nineteen to
  twenty-six minutes apart, so they are far outside it.
- **Streaming is not the cause of anything**: the same warm prefix streamed
  and not streamed both reported 15,360 cached.
- **The pinned host block is not the cause either**: the same prompt sent four
  times while moving only `order` and `allow_fallbacks` hit all four times,
  including with the exact three-host order the bot sends.
- **A burst of calls of one role cannot read its own first call's entry,
  unless it is made to wait once.** The day rollover fires about fifteen
  cast-beat calls back to back and every one of them logged `0% cached, sent
  0s after the previous call of this role finished -- inside
  api.cache_settle_seconds (15s)`. `LLM._hold_for_burst`
  (`api.cache_burst_hold`, on) waits out the remainder of the settle window
  when a call would go out inside it AND the previous call of that role, on
  the same system prefix, came back cold. Every call behind that one reads
  the prefix without waiting, so fifteen calls cost one wait. The cap is one
  wait per burst whatever the host does -- a burst ends at the first
  settle-length gap -- and a warm previous call, a different system prefix or
  a prompt under about 2,000 tokens hold nothing. The line to look for at the
  next day boundary is `[cache] cast_beat: held Ns so the burst reads the
  first call's prefix`, followed by a cast_beat call with a hit rate above
  zero; `/provider` counts the holds and their seconds.
- **Do not add `session_id`.** The docs say it keeps a multi-turn conversation
  on one Z.AI cache. Measured, it also partitions the cache: byte-identical
  content two seconds after a warm call, with a new session key, returned 0;
  the next call on that key hit. One cold call per key, for nothing the
  account-derived key was not already doing.

**Together's cache for the machinery model is effectively a one-minute
cache.** Hit rate against the gap since that role last ran, over the whole
logged history (prompts above 2,000 tokens):

| gap | deepseek-v4-flash-0731 at Together | kimi-k3 at Together | the official DeepSeek endpoint |
|---|---|---|---|
| under 1 min | 42.5% | 97.1% | 67.2% |
| 1-3 min | 10.5% | 54.9% | 34.7% |
| 3-6 min | 8.4% | 56.7% | 35.4% |
| 6-10 min | 7.1% | 61.3% | 33.9% |
| 10-20 min | 1.2% | 35.4% | 36.5% |
| 20-60 min | 0.0% | 33.6% | 36.6% |
| over 60 min | 0.1% | 19.2% | 25.0% |

Exactly zero past twenty minutes across 450 calls for the machinery model.
kimi held 93.4% over a whole day of real traffic on the same host, which is
what a large stable prefix plus frequent calls looks like. The official
DeepSeek endpoint holds about a third even across an hour and has the cheapest
cache read anywhere ($0.007 per million), and it is still the wrong place to
go: its prompt price is $0.22 and its completion price $0.66 per million, 6.6x
the pinned host's output rate. A cache does not rescue that.

**`supports_implicit_caching` in the endpoints API is not a usable signal.**
It is `false` on all twenty-four GLM endpoints, Z.AI's own included, and on
all eighteen kimi-k3 endpoints, and both demonstrably cache. Measure instead.

## 4b. A stream that never became an answer

A stream that times out, stalls, is cut off, sends an error object inside
itself or loops has been generated for as long as it ran, and the host bills
for it. Until 2026-09-07 it left no row at all: a cast-beat call streamed for
its full ten-minute ceiling at 16:13:56, produced 13,235 chunks and no words,
was retried inside the same call and answered, and only the retry reached
`llm_calls.jsonl`. Ten minutes of a paid model were invisible to
`tools/llmstats.py` and to `/provider`.

`LLM._note_abandoned` writes it: finish `abandoned`, the reason as the
exception type and its message, the seconds, the chunk count, and whatever
had been written when it died. The tokens come off the receipt where the last
chunk carried usage; where it did not, the prompt is measured off the bytes
that went out and the answer off the bytes that came back at four characters
to the token, and the row carries `estimated: true` so nothing reads the
figure as the host's. The ledger prices it the way it prices any row with no
cost on the receipt: the published rates for the slug that answered. A call
that never received a chunk is a failure to connect, cost nothing, and writes
nothing. The retry writes its own row as before, so both are counted.
`tools/provider_test.py`, in smoke.

## 5. Effort levels

The reasoning object takes `max`, `xhigh`, `high`, `medium`, `low`, `minimal`
or `none`, but **each model publishes its own list** in `GET
/api/v1/models`: `supported_efforts`, `default_effort`, `default_enabled` and
`mandatory`. `z-ai/glm-5.3-flash` publishes `["max", "high", "low"]`, default
`max`, and `mandatory: true`.

An unlisted value is not rejected: it lands on the nearest level below.
Measured on one prompt of 44,046 tokens, same bytes throughout:

| effort sent | reasoning tokens returned |
|---|---|
| `low` | 92, 64 |
| `medium` | 95 |
| `high` | 566, 612, 738, 802, 1,161, 1,259 |

So `medium` -- which nineteen roles carry, including the ten that write in the
second character's voice -- is `low` on this model. `mandatory: true` also
means the `{"enabled": false}` a non-thinking role sends is the case the docs
say the model rejects; no non-thinking role is on GLM today, but `/model
glm-5.3-flash` would pin all of them, including the fifty-one with thinking
off.

## 6. Prices and hosts, as of 2026-09-04

Per million tokens: prompt / completion / cached read.

| slug | host | price | uptime, 1 day |
|---|---|---|---|
| `deepseek/deepseek-v4-flash-0731` | Baidu | 0.050 / 0.100 / 0.010 | 99.9% |
| | OpenInference | 0.050 / 0.160 / 0.013 | 99.8% |
| | DeepInfra | 0.080 / 0.180 / 0.016 | 99.3% |
| | **Together (pinned)** | 0.140 / 0.280 / 0.030 | 99.5% |
| | DeepSeek, first party | 0.220 / 0.660 / 0.007 | 100% |
| | Cloudflare / Phala / AtlasCloud | 0.440 / 1.320 / 0.014-0.028 | 90.7-99.9% |
| `z-ai/glm-5.3-flash` | **Z.AI (pinned)**, GMICloud, Novita, DeepInfra | 0.075 / 0.250 / 0.015 | -- |
| | the other twenty endpoints | 0.150 / 0.500 / 0.030 | -- |
| `moonshotai/kimi-k3` | Together | 3.00 / 15.00 / 0.30 | -- |

Together is the seventeenth-cheapest of thirty endpoints for the machinery
slug. GLM's own pin is right: Z.AI is in the cheapest tier and the pin names
three of the four hosts in it. The move of the second character's voice off
kimi onto GLM (a 40x cut on prompt tokens) is already done and was worth more
than everything else in the audit put together: kimi took $6.55 of the day's
$7.90 across 175 calls, and the same tokens at GLM's rates with the same cache
rate would be about $0.19.

## 7. What is applied

- **The cache tracker is accurate** (`LLM._track_cache`, kv `cache_track`, the
  table in `/provider`; this job, 2026-09-04). It counts a cold call whenever
  the hit rate is under half and the role has a previous call to measure from,
  whatever that previous call did. It used to require the previous call to have
  come back WARM, so a role that is cold every time recorded nothing and the
  table read "no warm gap seen yet | never gone cold" while every call was
  missing -- which is exactly what both live saves said. What is kept per
  role: the last hit rate, the number of warm and of cold calls, the longest
  idle gap a warm call survived, and the shortest and most recent gap that came
  back cold. The gap is measured from the previous call of that role
  **finishing** to this one going out, so a slow answer does not inflate the
  gap its successor is judged on. A call sent inside `api.cache_settle_seconds`
  (15) of that finish, or while the previous call of the same role is still
  running, is counted on its own line and never as cold: the write has not
  landed yet, and section 4 is why. Gaps print in seconds under ninety and
  minutes above, because the interesting ones are seconds long.
- **This document**, and the audit report it summarises.

Known limit of the tracker: a row is keyed on the role alone, so the first
call after that role's model or host changes is counted as a cold call with a
gap that belongs to the model before it. The second character's persona role
shows this three times in one day (kimi to Sakana, Sakana to GLM). The counts
are still true statements about that role's prompt not being cached; they are
not clean measurements of one host's lifetime.

## 8. What was checked and is fine

- Attribution headers, and `X-OpenRouter-Title` as the current name.
- No `max_tokens` on an OpenRouter call, deliberately (section 1).
- No `transforms` and no `plugins`: middle-out truncation is automatic only on
  endpoints of 8k context or less, and hers are 1,048,576.
- Sticky routing off, which is not a choice: it is not used at all when
  `provider.order` is set.
- Streaming, and the mid-stream failure handling: OpenRouter sends 200 as soon
  as the provider accepts, so every later failure arrives inside the body,
  which is what `_stream` reads.
- Empty answers cost nothing already (zero-completion insurance is automatic),
  so the `api.empty_retries` loop is free when it fires on a true empty.
- The cached-tokens field, and cost off the receipt (section 3).

## 9. Open decisions, none of them applied

Each is his call. The numbers are the audit's; the smallest fix is named so
none of these is a project.

1. **The machinery model is pinned to an expensive host.**
   `deepseek/deepseek-v4-flash-0731` at Together billed $1.0632 for one day's
   831 calls (6,898,953 prompt tokens, 18.7% cached, 853,751 completion). The
   same tokens: $0.433 at OpenInference (99.8% uptime, US), $0.379 at Baidu
   (99.9%, headquartered in China, which is a separate decision). Worth about
   $0.63 a day, $19 a month, and it is the largest remaining item now that the
   voice model has moved. Smallest fix: `"deepseek/deepseek-v4-flash-0731":
   ["open-inference", "together"]` in `config.py` DEFAULTS and both characters'
   configs, then read the hit rate off `data/retired/20260904_openrouter_audit/scan.py`
   after a day to confirm it did not collapse.
2. **The fall-through is unbounded.** With `api.host_fallback` on and no
   `max_price`, the same slug can be served by Cloudflare, Phala or AtlasCloud
   at $0.44 prompt and $1.32 completion, 8.8x the pinned rate. Benign so far
   (a day's fall-throughs went to Relace, OpenInference, Baidu and Sail
   Research, all cheaper). Smallest fix: `"max_price": {"prompt": 0.15,
   "completion": 0.35}` in the provider preferences. A call that finds no host
   under the cap fails and lands in `missed_calls`, which is already what the
   project wants a failed call to do.
3. **JSON roles re-ask in prose where the API has a parameter.**
   `LLM.call_json` sends no `response_format`; a parse failure appends the bad
   answer and asks again, up to `api.json_retries`. That is 123 whole extra
   calls across the logged history, roughly 0.9M prompt tokens and $0.12, plus
   the turns nobody spoke while a retry ran. Both slugs list `response_format`
   at every endpoint in both pins. Smallest fix: send `{"type":
   "json_object"}` from `call_json` and keep the re-ask as the backstop. A full
   `json_schema` with `strict: true` wants `require_parameters: true`, which
   narrows the host list.
4. **The voice roles ask for an effort level their model does not publish**
   (section 5). `medium` is `low` on GLM. Extra reasoning is billed as output
   at $0.25 per million, so `high` would cost about $0.0002 a call. Whether
   her voice should think harder is a decision about her, not a defect; the
   defect is that the config names a level that does not exist.
5. **Nothing clamps an effort level to what the model supports.** Smallest
   fix: store `supported_efforts` and `mandatory` beside the slug in
   `api.providers.<provider>` and clamp in `_payload`, so `/model <name>`
   cannot send an effort the model rejects.
6. **`data_collection` is unset, so the default `allow` applies**: hosts that
   store user data non-transiently and may train on it. Her persona prompt is
   44,000 tokens of private conversation going to Z.AI (Singapore) and
   Together (US), and on fall-through to Baidu (China). Setting it to `deny`
   narrows the host list. Currently a decision made by a default.
7. **`require_parameters` is unset.** Every endpoint in both pins supports
   `reasoning` and `temperature` today, but a fall-through to a host that
   ignored `reasoning` would answer without thinking and nothing downstream
   would know.
8. **`Retry-After` is never read**, and the out-of-balance test is a substring
   match (`"402" in err or "alance" in err`) where the API publishes typed
   codes: `insufficient_credits` (402), `provider_overloaded` (503),
   `provider_unavailable` (502). `_call_on` backs off 2/4/8 seconds and can
   retry straight into a limit that told it how long to wait.
9. **Nothing polls the account's remaining credit.** `GET /api/v1/key` returns
   `limit_remaining` and `usage_daily`. Putting the remaining credit in
   `/provider` or `/stats` would make a dry account visible before it silences
   her; the official account running dry at 20:00 on 2026-08-31 was found
   afterwards.
10. **Grouping her per-reply calls to catch the cache is mostly unreachable.**
    A 44k persona call is $0.00336 cold and about $0.00072 warm, 78% less, but
    only calls inside a burst can hit a twelve-minute entry. At sixty voice
    calls a day perfect caching saves about $0.16; with the first character's
    186 persona calls a day on GLM too, about $0.49.

## 10. How to measure this again

The audit's scripts are read-only and live beside its report:
`data/retired/20260904_openrouter_audit/scan.py` (a day's calls, hosts and
spend off `llm_calls.jsonl`), `.../gaps.py` (hit rate against the idle gap),
`.../glm_calls.py` (one model's calls with the stable-prefix comparison),
`.../reprice.py` (the same tokens at every endpoint's rates), and
`.../cache_probe.py` to `cache_probe4.py` and `.../ttl_probe.py` (live paid
probes; sixteen calls cost $0.0251).
`data/retired/20260904_openrouter_fixes/replay_cache_track.py` replays the
tracker over calls that really happened and prints the table each version
would show, which is how a change to it is checked without waiting for the
bot.
