# Performance

Where the time goes when the four characters run, measured rather than
reasoned, and what is worth changing. The raw numbers, the exact commands and
the scripts that produced them are in
`data/retired/20260910_1558_performance_study/REPORT.md`; every figure below
is traceable to a line in it.

The measurements are taken from two weeks of the system's own record: 11,827
model calls in 532 run directories under `logs/`, the live saves read through
`file:...?mode=ro`, and the runtime built in a probe process against scratch
copies. No paid call was made to produce them and nothing was restarted.

## 1. Where the time actually goes

### Two clocks, and only one of them is the machine's

Almost all of the elapsed time belongs to the provider. Over sixteen days the
four characters spent **28.7 hours inside model calls**, at a mean of 8.7
seconds each, for $27.01. Against that, everything the machine does itself to
prepare a call -- rebuilding the whole conversation history, assembling both
halves of the prompt, every store read involved -- is **82.5 milliseconds**,
or 0.9% of one average call. Local compute is not the problem and no amount of
work on it will be felt.

The interesting split is inside the provider time, and it is not the one the
architecture is built around.

| where a second spent on the provider goes | seconds | hours | share |
|---|---|---|---|
| generating the answer itself | 52,525 | 14.6 | 50.9% |
| generating tokens that never reach the answer | 26,375 | 7.3 | 25.6% |
| thrown away: the call was abandoned at the ten-minute limit | 11,537 | 3.2 | 11.2% |
| waiting for the first token to come back | 7,469 | 2.1 | 7.2% |
| thrown away: the answer ran to the host's output ceiling | 5,315 | 1.5 | 5.1% |

**92.8% of the wait is the answer being written a token at a time, at about 66
tokens a second.** Only 7.2% is the wait before the first token -- the part
that a shorter prompt or a warmer cache could shorten. The system is designed
around the size and cache-friendliness of its prompts; the clock says the size
of its answers is what costs.

### Twenty-six calls consumed a sixth of all the time and returned nothing

Of 11,827 calls, twenty-six -- 0.22% -- burned 16,852 seconds, 16.3% of every
second spent on the provider, and produced nothing usable. Every one was on
the same model at the same host.

They arrived in two bursts, not as a steady tax:

| day | seconds on the provider | of that, thrown away | share |
|---|---|---|---|
| 2026-08-25 to 09-02 | 20,494 | 0 | 0% |
| 2026-09-03 | 7,981 | 967 | 12.1% |
| 2026-09-04 | 17,316 | 4,348 | 25.1% |
| 2026-09-05 to 09-07 | 24,538 | 0 | 0% |
| 2026-09-08 | 22,925 | 6,136 | 26.8% |
| 2026-09-09 | 9,769 | 5,401 | **55.3%** |

On the last day in the record, more than half of all the time the system spent
waiting on the provider went into nine calls that returned nothing. This is a
live condition, not a historical one.

There are two distinct failures behind it.

**A model that loops inside its own thinking and never writes a word.**
Twenty-one calls, 11,537 seconds, all on the last two days. Each was cut at
the ten-minute request limit with a message of the form "still writing after
8614 chunks (0 chars); the answer is a runaway". Zero characters after
thousands of chunks means every token was reasoning. The roles hit were the
one that decides what she does with her phone in her hand (`pick`, six times),
her account of an episode she watched (`episode_account`, ten times), a
friend's words in a room (`cast_reply`, `cast_turn`), what she wakes up
wanting (`morning`), the one that puts her day-zero picture of him where
months of knowing him would leave it (`settle_beliefs`), and the digest of his
machine (`phone`).

The guard that exists for this cannot see it. In `llm.py`, the repetition
check counts only characters of *content*:

    if delta.get("content"):
        content.append(delta["content"])
        chars += len(delta["content"])
    r = delta.get("reasoning_content") or delta.get("reasoning")
    if r:
        reasoning.append(r)
    ...
    if guard_at and chars >= next_check:

A model looping in its reasoning stream never increments `chars`, so the
check is never reached. The stall timeout does not fire either, because chunks
keep arriving steadily. Only the ten-minute ceiling stops it, and it pays the
full ten minutes every time.

**An answer that runs to the host's ceiling.** Five calls, 5,315 seconds, all
from the role that reads the finished day back looking for seams
(`coherence`), each returning between 113,884 and 131,072 output tokens --
131,072 being the host's own cap -- and taking between 967 and 1,152 seconds.
Here the repetition check did run, and found no literal repeat of the last 400
characters four times over, so it let the answer go to the ceiling.

### A quarter of the time is spent on tokens that are then discarded

Setting the runaways aside, 26,375 seconds -- 25.6% of all provider time --
went into reasoning tokens. Thinking is already a per-role decision in the
configuration, so this is attributable:

| role, in words | seconds thinking | share of its own time | per call | effort |
|---|---|---|---|---|
| her reply to him (`persona`) | 5,971 | 76% | 9.6 s | medium |
| the chain of thought she falls into (`spiral`) | 4,196 | 98% | 42.4 s | medium |
| what she does with her phone in her hand (`pick`) | 3,781 | 51% | 22.9 s | medium |
| her account of an episode (`episode_account`) | 3,768 | 42% | 139.6 s | high |
| her diary entry (`diary`) | 3,090 | 93% | 110.4 s | medium |
| a friend's reply in a room (`cast_reply`) | 2,701 | 44% | 4.4 s | medium |
| a friend's beat in her day (`cast_beat`) | 2,240 | 83% | 6.6 s | medium |
| what the day left her with (`reflect`) | 1,989 | 76% | 19.3 s | medium |
| the spoken line (`voice`) | 1,214 | 96% | 6.4 s | medium |

The role that produces a spoken line spends 96% of its time thinking to
produce, on average, 318 tokens. Her account of an episode is set to the
highest effort and spends 139.6 seconds per call on reasoning.

Whether that thinking earns its keep is a question about her voice, not about
performance, and this study cannot answer it -- see section 3.

### The prompt is large, and its size is nearly free

One call's payload for the first character measures 40,535 bytes of system
prompt, 177,956 bytes of history in 371 messages, and 37,474 bytes of what she
carries into the moment. Over the fortnight 110.7 million prompt tokens were
sent and 29.3% came back served from the provider's cache.

None of that costs much time. Sorting every call by prompt size:

| prompt tokens | calls | median wait for the first token |
|---|---|---|
| under 2,000 | 1,178 | 0.69 s |
| 5,000 to 10,000 | 898 | 0.90 s |
| 20,000 to 40,000 | 281 | 1.28 s |
| over 80,000 | 209 | 3.02 s |

Forty times the prompt buys about four times the wait, on a component that is
7.2% of the total. Comparing calls of the same role at the same prompt size,
warm against cold, **a cached prefix saves a median of 1.03 seconds** and at
best 2.02 seconds.

Against that, the runtime deliberately holds a call back for fifteen seconds
so that a burst reads the first call's prefix out of the cache. Over the
fortnight those holds cost **662 seconds of wall clock to buy at most 91
seconds** of first-token time. The trade is measured, and it loses.

The care taken over the two-halves prompt split is still right -- it protects
the cache, and the cache protects the bill -- but it is a cost decision, not a
speed one, and the bill is $27 for sixteen days.

### Calls run one after another

Within a single character's process, 82% of call-seconds are strictly serial:
summing every call's duration gives 78,211 seconds, and the union of the
intervals they occupy gives 64,328 -- 17.8% overlap. Any given process has a
call outstanding only 4.6% of its lifetime, so the system is not saturated; it
is idle, then serial, then idle again.

The daily compile is where that hurts most. It blocks the loop for a median of
62 seconds, a mean of 151, and once for 23.6 minutes, and it is made of 14.8
model calls issued one at a time, 107.6 seconds of provider time, which is 71%
of the block. Two roles account for two thirds of it: reading the finished day
back for seams (36.8 s per compile) and writing the day as one story (34.1 s).
Most of the rest -- the English glosses, each friend's day, the social graph,
the questions the day answered, his habits -- do not depend on each other.

### How long she takes to answer him, and why that is mostly not a machine question

From her live save, across 347 answered messages over 123.7 days, the median
gap from his message to her first reply is **96.5 seconds**; on the second
character's save 100.2 seconds, on the third's 114.0. The write of her message
to its delivery stamp is 0.0 seconds throughout: the send itself is free.

Most of that gap is on purpose. The configuration says she takes 20 to 240
seconds to notice a message when her phone is free, then 6 to 50 seconds
scaled by how she is to compose, then types at 0.045 seconds a character
between a 4-second floor and a 45-second ceiling. A median near 100 seconds is
what those numbers describe.

Two parts of the machine's time sit inside that window and two do not. The
call that asks what she does with the phone in her hand runs before the timer
is set from a clock reading taken earlier, so its duration is partly absorbed.
The call that writes her reply runs after the timer expires, and is additive:
its 12.6-second mean is real added delay, of which 9.6 seconds is thinking.
And a runaway on either blows straight through the design.

### Local compute, in full

Everything here was profiled directly and none of it matters much.

- **Building one character's runtime: 0.51 seconds.** Two fifths of it is one
  call to `inspect.stack()` in the registration of how she sees him
  (`sim/sight.py`), which reads the source file of every frame on the stack.
  Once per process.
- **Rebuilding the whole conversation history: 32.8 milliseconds**, 371
  messages, 177,956 bytes, in exactly 13 SQL statements with no repeated
  query. Across all 11,827 calls of the fortnight that is 390 seconds against
  103,222 -- 0.38%. This runs once per model call, as designed, and the design
  is not expensive.
- **Assembling the system prompt: 45.6 milliseconds** in 155 SQL statements,
  of which 103 are the same two key reads repeated (66 times for what people
  are to her, 37 for the kinds of thing that put her off). Measured, those 103
  repeats cost 4.3 milliseconds. Not worth touching.
- **The store.** The largest table in a 22.2 MB save holds 3,080 rows and the
  whole file sits in the page cache. There is no index on the timestamp or
  date columns that are queried, and it does not matter at this size; a scan
  is microseconds.
- **Memory.** A built character adds 2.5 to 7 MB on top of a 160 MB
  interpreter-and-imports floor. Four processes come to roughly 660 MB against
  31.9 GB. The four do not contend for memory.
- **The one genuinely numeric piece of work** -- embedding what she knows and
  remembers so it can be reached by meaning -- takes about 17 seconds at boot
  for 1,556 rows, on the GPU, on a background thread. It is already
  delegated to a library and is not on any critical path.

The one local cost worth naming is a filesystem question asked in an inner
loop. Before every name lookup, the roster asks the operating system for the
modification time of the cast file, to decide whether its cached table is
stale. That costs 11.26 microseconds and happens 1,656 times in one prompt
assembly and 1,074 times in one history rebuild. Answering it at most once
every two seconds instead -- measured by substituting the call in a probe
process, not by editing anything -- takes the two together from 79.3
milliseconds to 48.9, a 38% cut. In absolute terms it is 30 milliseconds
against an 8,700-millisecond call.

### The check before every restart

`python tools/smoke.py` takes **2 minutes 56 seconds**, and it runs before
every restart. Under a profile, **163.6 of those 175 seconds -- 93% -- are 56
sequential launches of a fresh Python interpreter**, at 2.92 seconds each,
each re-importing the project from scratch (importing the model client alone
costs 0.867 seconds, almost all of it the vendor package). Constructing all
four runtimes, which is the fault class smoke was written to catch, is 4.44
seconds of the 175.

Separately, and not a performance matter: smoke's docstring says a run without
`--tick` never leaves the machine, and that is not true. Blocking every
provider entry point and running it shows exactly one call that would have
gone out, from the constructor of her picture of him, which seeds itself on a
save that has no value yet and then settles that seed against her history.

## 2. What the Algorithmica book applies to here, and what it does not

*Algorithms for Modern Hardware* is a book about making a CPU do arithmetic
faster. Its method transfers to this project completely. Almost none of its
techniques do, and pretending otherwise would produce a worthless report.

### The method transfers

The book opens its profiling chapter by saying that "staring at the source
code or its assembly is a popular, but not the most effective way of finding
performance issues", and insists that modern systems are too complex to reason
about and must be measured. That is the whole of what this study did, and it
paid immediately: three plausible suspects turned out to be nothing (the
history rebuild, the repeated store reads, the missing indexes) and the real
cost -- twenty-six calls out of twelve thousand -- would never have been found
by reading code.

The book's distinction between instrumentation and statistical profiling maps
directly onto the two tools used here: the per-call record the runtime already
writes is instrumentation, and it is what found the runaways; a sampling
profile over the built runtime is what found the filesystem question in the
inner loop.

Its rule about when to optimise transfers too, in the negative direction. The
book's own language comparison puts pure Python at roughly 5,000 times slower
than a tuned native library on the same arithmetic. That would be alarming if
this project did arithmetic. It does not: its Python does 82.5 milliseconds of
work per 8,700-millisecond call, so even a hundredfold speedup of every line
of it would move the total by under one percent.

### One model from the book fits the shape of this system exactly

The external memory model treats a program as running against a two-level
store, counts only the round trips to the slow level, and ignores everything
that happens between them. Its justification is a latency ratio -- a read from
memory at 50 nanoseconds against a read from a disk at 5 milliseconds, a
factor of about 100,000.

This system has the same shape with a far worse ratio. A read from local
memory is nanoseconds; a call to the provider is a mean of 8.7 seconds. Every
lesson the model draws follows:

- **Count the round trips, not the work between them.** The right unit of cost
  here is one model call, and the right questions are how many there are, how
  long each takes, and how many return nothing.
- **A block is fetched whole, so a wasted trip costs the same as a useful
  one.** A call abandoned after ten minutes costs exactly what a good one
  would have; that is why twenty-six calls dominate twelve thousand.
- **Locality is what caching buys.** The provider's prompt cache is an
  eviction-policy problem straight out of the book's chapter on them, and the
  measurements above are the eviction data: the cache goes cold after twenty
  to thirty seconds of idle, and the recorded longest gap that still came back
  warm was 97 minutes.

The one place a CPU-level idea lands literally is the book's section on system
calls, which is about the cost of crossing into the kernel and the value of
not doing it in a loop. The freshness question the roster asks the filesystem
1,656 times per prompt is that, in miniature, and it is worth about 30
milliseconds.

### What does not apply, and why

There is no compute-bound inner loop in this codebase. I looked for one and
there is nothing to report: the only vectorised numerical work in the system
is the sentence embedding, and that is already inside a library running on the
GPU, taking 17 seconds once at boot on a background thread. Everything else is
string assembly, JSON, SQLite over files small enough to sit in the page
cache, and waiting on a socket.

So the following chapters have nothing to offer this project, and no
recommendation in this document is derived from them:

- **Instruction-level parallelism, branchless programming, instruction
  scheduling.** There is no hot branch. The interpreter's dispatch overhead
  swamps any branch cost by orders of magnitude, and the whole interpreter is
  under one percent of the time.
- **SIMD and vectorisation.** Nothing here is a numeric kernel over an array.
- **Compilation flags, contract programming, compile-time computation.** The
  code is not compiled.
- **Arithmetic, number theory, integer division, bit manipulation.** The
  system does essentially no arithmetic.
- **Cache lines, alignment and packing, cache associativity, prefetching,
  structure-of-arrays layouts.** These govern how a few hundred nanoseconds
  are spent. The unit of cost here is eight seconds.
- **The algorithm and data-structure case studies** -- sorting, binary search,
  static B-trees, hash tables, matrix multiplication, the transforms. The
  largest collection this system searches has 3,080 rows.

If the project ever gains a real compute problem -- ranking a large corpus by
meaning on the CPU, scoring every message against every other -- the last
third of the book becomes relevant. It is not relevant now.

## 3. What to change, ranked by measured impact

### 1. Stop a model that loops inside its own thinking

**Saves:** 11,537 seconds over the fortnight, 11.2% of all provider time, and
on the worst recorded day the great majority of it. This is happening now: it
began on 2026-09-08 and the last day of record spent 55.3% of its provider
time this way.

**Why it is not caught:** the repetition check counts characters of content,
and a reasoning runaway produces none, so the check is never reached. The
stall timeout does not fire because chunks keep arriving. Only the ten-minute
request limit stops it, at full price.

**What to do:** apply the same repetition check to the reasoning stream that
already exists for the content stream, and give each role a ceiling on
reasoning tokens beyond which the call is abandoned. A call that has emitted
several thousand reasoning tokens and not one character of content is not
going to recover.

**Confidence:** high. Every one of the twenty-one calls is in the record with
its abandon message, and the reason the guard misses them is visible in eight
lines of `llm.py`.

**Work:** small -- one guard in the streaming loop, one configuration key,
one line of logging.

**What could go wrong:** a ceiling set too low would cut a legitimately long
deliberation. The observed good calls sit far below the runaways, so there is
room, but the ceiling should be per role and derived from the recorded
distribution rather than guessed. Worth also checking whether the burst is a
change at the host rather than in the prompts: every one of the twenty-six
was on the same model at the same host, and there were nine clean days
before it.

### 2. Stop an answer that runs to the host's output ceiling

**Saves:** 5,315 seconds, 5.1% of all provider time, in five calls.

**What to do:** the role that reads the finished day back for seams needs a
ceiling of its own well below the host's 131,072 tokens. Its ordinary answers
average 13,229 tokens, so a cap of about twice that would have stopped all
five without touching a normal one. The repetition check should also look for
near-repeats rather than an exact match of the last 400 characters four times,
which is what let these through.

**Confidence:** high on the measurement, medium on the near-repeat change,
which is a heuristic and can misfire.

**Work:** small for the cap, medium for a better repetition test.

**What could go wrong:** a cap truncates a genuine long answer instead of
rejecting it; the answer must be discarded rather than stored half-written,
which the project's rule against recording a thing before it happened already
demands.

### 3. Review which roles are allowed to think, and how hard

**Saves:** up to 26,375 seconds, 25.6% of all provider time, if thinking were
switched off everywhere -- which is not the proposal. Realistically, the roles
where it is most obviously disproportionate are the spoken line (96% of its
time thinking for a 318-token answer), her account of an episode (set to the
highest effort, 139.6 seconds of thinking per call), and the chain of thought
she falls into (98%, 42.4 seconds per call). Those three alone are 9,178
seconds, 8.9% of the total.

**Confidence:** high that this is where the seconds are; **low that spending
them is wrong.** This is the one recommendation in this document that cannot
be settled by measurement of the kind done here. Thinking may be exactly what
makes her answers hers, and the project's standing position is that her voice
is not to be tuned for tidiness.

**What to do first:** not a change -- a measurement. Take a set of recorded
prompts for one role, re-ask each with thinking on and off, and read the two
answers side by side. That costs paid calls and is a decision for the owner to
authorise, with a cost estimate first. Do the cheapest role first, and start
with the machinery roles rather than the ten that write in her voice.

**Work:** the configuration change is trivial. The evidence needed before it
is not.

**What could go wrong:** her voice changes and nobody notices for days,
because the change is diffuse. Any trial should be on one role at a time with
the answers read, never on a batch.

### 4. Find out why two roles' answers keep failing to parse

**Saves:** 5,295 seconds, 5.1% of all provider time, spent re-asking for 371
answers that came back malformed. Two roles are 81% of it: a friend's reply in
a room (184 re-asks, 1,768 seconds) and a friend's turn in an exchange (117
re-asks, 722 seconds).

**Confidence:** high on the cost, unknown on the cause -- I did not diagnose
why those two roles in particular produce unparseable answers so often.

**Work:** unknown until the cause is known. Reading a sample of the malformed
answers out of the per-call record is the first hour of it.

**What could go wrong:** little. Re-asking is already the correct behaviour
for a malformed answer; this is about making it rarer, not removing it.

### 5. Let the independent parts of the daily compile run at the same time

**Saves:** the compile blocks the loop for a median of 62 seconds and a mean
of 151, of which 107.6 seconds is model calls made one after another. Two of
those calls are two thirds of the time and are probably ordered; the remaining
dozen -- the glosses, each friend's day, the social graph, the questions the
day answered, his habits, the episode cards -- appear independent. Running
them together would plausibly return 40 to 60 seconds per compile per
character per day.

**Confidence:** medium. The saving is an estimate from the serial times; I did
not verify which of those calls truly have no ordering between them, and that
verification is the bulk of the work.

**Work:** medium. The ordering has to be established from the code, not
assumed, and the shared world has exactly one writer for everything its owner
owns, which constrains what may run concurrently.

**What could go wrong:** two calls that quietly depend on each other through
the day's one truth about where she is and who she is with would produce a
day that contradicts itself, which is worse than a slow compile. This is the
recommendation most likely to break something subtle, and it should be last
of the five.

### 6. Drop or shorten the deliberate fifteen-second hold before a burst

**Saves:** 662 seconds of wall clock over the fortnight, against at most 91
seconds of first-token time that the resulting cache hits actually bought.

**Confidence:** medium. The latency side is measured directly, comparing warm
and cold calls of the same role at the same prompt size. The money side is
not: I did not isolate what the hold saves on the bill, only that the bill is
$27.01 for sixteen days, so there is not much there to save.

**Work:** trivial -- one configuration value.

**What could go wrong:** the hold may be doing something the latency numbers
do not show, such as keeping a burst of a friend's turns coherent by keeping
them on the same cached prefix. Before changing it, read why it was added.

### 7. Answer the cast-file freshness question once every couple of seconds

**Saves:** 30.4 milliseconds of the 79.3 it takes to put a call's payload
together -- a 38% cut of the local work, and 0.35% of an average call.

**Confidence:** high; measured by substituting the call in a probe process and
re-timing the same two functions.

**Work:** trivial.

**Why it is on the list at all:** not for the live bot, where it is invisible,
but because it is a few lines and it makes every tool and every future
batch operation over prompts proportionally faster. Do it when touching that
file for another reason.

### 8. Run the checks before a restart in parallel

**Saves:** up to about 140 seconds of the 176 that `tools/smoke.py` takes,
which is developer time before every restart rather than production time.
93% of that run is 56 sequential launches of a fresh interpreter at 2.92
seconds each, on a machine with ten cores.

**Confidence:** high on the measurement. Medium on the saving, because the
launches contend for the disk and for the same source tree.

**Work:** small to medium -- a process pool over the existing list, with the
output collected per check so the report still reads in order.

**What could go wrong:** those checks are subprocesses on purpose. Some of
them almost certainly rely on a clean interpreter with nothing else imported,
which is exactly what a fresh process gives them; a pool preserves that, but
running them concurrently against the same scratch save does not. The database
each one touches has to be separated first.

### Also worth fixing, though not for speed

Smoke makes one paid model call, from the constructor of her picture of him,
which seeds itself against her history on a save that has no value for it yet.
Its docstring promises it does not. The cost is negligible; the broken
guarantee is not, because it is the check that runs before every restart and
it is meant to be free and offline. Either give the seeding path a way to be
told not to settle, or have smoke arrange that the value is present.

### Measured, and not worth changing

Stated plainly so that nobody spends a day on them:

- **Rebuilding the conversation history on every model call is cheap.** 32.8
  milliseconds, 13 SQL statements, no repeated query, 0.38% of the fortnight's
  provider time. The design is sound and the implementation is not the cost.
- **The repeated key reads during prompt assembly are cheap.** 103 redundant
  reads, 4.3 milliseconds. Tidy them if the file is open anyway; do not plan
  work around them.
- **The store needs no indexes.** The largest table queried without one holds
  3,080 rows in a 22 MB file that sits entirely in the page cache.
- **Memory is not a constraint and the four characters do not contend for
  it.** Each adds 2.5 to 7 MB over a 160 MB floor.
- **Shrinking the prompt would buy almost no time.** The wait before the first
  token is 7.2% of all provider time, and quadrupling the prompt from 5,000 to
  20,000 tokens moves the median from 0.90 to 1.09 seconds. The two-halves
  split is still right, but as a defence of the bill.

## 4. What is not known

- **A live character's CPU share was not measured.** No character was running
  during the study and the brief forbade starting one. The cost of one pass of
  the main loop therefore has no figure; the log's status line is throttled to
  once every thirty seconds and cannot resolve it. What the record does bound
  is that a pass usually completes inside a second of work on top of its
  five-second sleep.
- **Contention between the four characters, and with everything else on the
  machine, was not measured.** Memory is not a constraint; disk and CPU
  contention with the nineteen unrelated Python processes on the box is
  unknown.
- **Whether thinking earns its quarter of the time is open**, and needs paid
  paired calls and a reading of the answers, not a profile.
- **What happens inside the 56 subprocesses smoke starts** was not
  instrumented.
- **The hub and the machine's collector** were not measured. Neither was
  running and neither appears in the per-call record.
