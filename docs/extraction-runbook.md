# The extraction runbook: one page, for a fresh subject

<!-- doc: reference -->

**What this is.** The steps, in order, for an agent handed material and told to
make a character from it. Every step names what it produces and points into
`docs/character-method.md` for the reasoning behind it. **This page decides
nothing**: where it and the guide disagree, the guide is right and this page is
stale.

**Before the first step.** Read `docs/character-method.md` §1 (the premise and
the nine invariants), §5 (the operating rules, all of them paid for in money or
a night's work) and §6 (the procedure this page is the short form of). Read
`docs/verification.md` before quoting any count as a finding.

**Three rules that apply at every step.** Everything the subject produces lives
under that subject's own tree. Every number is computed by code over files on
disk, and a model interprets and never counts. Every claim carries a receipt
that code re-finds in the material, and what cannot be found is dropped and the
dropped share reported -- that share is the invention measure.

---

## Phase 0 -- decide what this is (half a day)

| | do | read |
|---|---|---|
| 0.1 | Write the intake note: the file count, the hours, the naming pattern, which channels exist (audio? video? speaker tags? secondary text?), and **which variant of the four you are running** | guide §7.1 |
| 0.2 | Copy that variant's column out of the table and keep it beside the note. It is the list of steps that change | guide §7.2 |
| 0.3 | Decide the toolset: the base is `yukarin/tools/`, and the coded half has to be lifted out of `asumin/tools/` | guide §9.1 |
| 0.4 | If the run will spend: announce it first -- what is running, roughly how long, what it costs -- and set a spend cap on the client | guide §5.1 |

## Phase 1 -- the material, with no model involved (a day)

| | do | read |
|---|---|---|
| 1.1 | Build the corpus. **Change the two filename regexes first.** Verify the session count, the gaps in the numbering, and that the cue count is identical before and after cleaning | guide §6 step 2, §9.2 |
| 1.2 | Build the readable index and let it name the era blocks from the broadcast dates | §6 step 3 |
| 1.3 | Write the reading views, one plain file per session | §6 step 5 |
| 1.4 | Build the surface battery **from scratch for this subject**, as a data file and not as code. Count the family, not the spelling | §6 step 6, §9.2 |

## Phase 2 -- who is speaking (a day, and the most expensive stage of an untagged run)

| | do | read |
|---|---|---|
| 2.1 | Untagged material: one attribution call per session, labels re-argued for this programme rather than reused. Tagged material: parse the speaker column, normalise the label set by hand against the cast list, and print the label counts | §6 step 4, §7.2 |
| 2.2 | Assert full ordered coverage in code; repair a near miss mechanically and re-ask garbage | §6 step 4 |
| 2.3 | **Have two independent readers attribute the same three sessions** and report the cue agreement. This is the one layer that can be called solved, and only if it is measured | §3.2, §4.1 |
| 2.4 | **Label the not-her spans by speaker in at least five sessions.** Skipping it is the largest structural hole in the work so far | §6 step 4a |
| 2.5 | Spot-read two sessions at the span boundaries | §3.2 |
| 2.6 | Run the surface battery over the *other* voices as well as hers. This is where a marker gets returned to its owner | §6 step 6 |
| 2.7 | Compute the bounding measures and the negative space, and get the absent list out of it | §6 step 7 |

## Phase 3 -- the control, before any brief is accepted (a day)

| | do | read |
|---|---|---|
| 3.1 | Read six sessions end to end and write findings with cue receipts. **Before** seeing any extraction, or it is not a control | §6 step 8 |
| 3.2 | Name the pass for what it is. A long-context model reading is not a human ceiling | §3.2, §4.3 |

## Phase 4 -- the free discovery pass, whose product is a book (three days)

| | do | read |
|---|---|---|
| 4.1 | Freeze the brief to disk. **A floor and no ceiling** -- "if you have found three, you have stopped early" -- and nothing about how many to expect | §5.6 |
| 4.2 | One call per session, three runs, her attributed cues only, numbered, with borrowed prose compressed to one context line | §6 step 9 |
| 4.3 | Verify every quote against the cue it cites, in code. Store the verified-over-offered ratio per session | §5.7 |
| 4.4 | Report the run-to-run agreement on cited cues | §6 step 9 |
| 4.5 | Score the brief against the control of 3.1 and rewrite it on that number, not on the count of mechanisms | §6 step 10 |
| 4.6 | Reduce by function, chunks of 300. Assert entry conservation and read the purity statistic. **The output is a draft** | §6 step 11 |
| 4.7 | Consolidate into a frozen codebook version, full schema, then freeze. **This is the step that decides whether any later number means anything** | §6 step 12, §2.1 |

## Phase 5 -- can it be coded reliably at all (two days, and a stop point)

| | do | read |
|---|---|---|
| 5.1 | Label the contexts of every span. This is also the segment list the coded pass chunks at | §6 step 13 |
| 5.2 | Probe every host you intend to use for its output ceiling and its concurrency | §5.4 |
| 5.3 | Run the reliability pilot on three sessions, **from at least two model families**, plus an anchor read | §6 step 14 |
| 5.4 | Compute alpha per entry at both units, and the span overlap | §4.2 |
| 5.5 | **The gate**: median cross-family alpha at or above 0.67, at least 60% of entries above it. A within-family figure is an upper bound and may not be substituted. Rewrite failing entries' exclusions and near misses, at most twice, then the answer for this corpus is **no** | §4.2, §4.3 |
| 5.6 | Fix the two rules the protocol needs before another coding call: the sampling rule (once at its clearest occurrence, or once per chunk -- say which) and the played-role rule | §4.5, §5.6 |

## Phase 6 -- the numbers (a week, mostly reading)

| | do | read |
|---|---|---|
| 6.1 | The coded pass over the corpus, five codings from two or more families, **eight concurrent**. Report concurrency, call count and spend at ten minutes; read the ledger at ten and thirty | §6 step 15, §5.1 |
| 6.2 | Holdout, specificity, the n-gram counting baseline, and the cross-subject control | §6 step 16, §4.4, §4.6 |
| 6.3 | Judgement: every surviving entry read with its evidence in context and classed | §6 step 17 |
| 6.4 | Portability per entry per context. Only portable entries may found a claim about her off duty | §6 step 18, §4.6 |
| 6.5 | Facts into records with the importance grade written down; the moments with their counts; the retrieval phrases, swept for one that fires inside a longer word | §6 step 19 |
| 6.6 | The trigger table and the gauge baselines, each naming its measurement | §6 step 20 |
| 6.7 | The five-factor profile off the portable entries, with a confidence and receipts per dimension | §6 step 21 |

## Phase 7 -- the person behind the voice (two days)

| | do | read |
|---|---|---|
| 7.1 | Commission the speculative readings: one call per session, the eight categories, told to speculate about the person and **not** to write a profile. Delete the categories that need a laugh or a face if only a transcript exists | §6 step 22, §3.2 step one |
| 7.2 | Split the corpus into a fit block and a held-out block, and hold out the **sessions** | §3.2 step one |
| 7.3 | Count the convergence per candidate trait, in two blocks, with the net in the source. Read the matched sentences before keeping a trait | §3.2 step three |
| 7.4 | Drop what an evidenced entry contradicts, whatever the count | §3.2 step four |
| 7.5 | Score the held-out block: confirmed, revised or contradicted, per the rubric | §3.2 step five |
| 7.6 | Name the frame on every surviving row. **The count of rows with no frame must be zero** | §2.5, §3.2 step two |
| 7.7 | Check every gap claim where the record touches it | §3.2 |

## Phase 8 -- the files (two days)

| | do | read |
|---|---|---|
| 8.1 | The card: drivers, the trigger table, the baselines, the records, the moments with counts, the profile, the tier on every row, the bounds as an explicit no-data block ending with what could close each gap | §6 step 24 |
| 8.2 | The speech guide, **and its sort file beside it** | §10.1 |
| 8.3 | The bible's off-tape section, every line marked record or reading, closing with what was dropped | §10.2 |
| 8.4 | The seed self-beliefs file, confidence set by the stated rule | §10.3 |
| 8.5 | **The type, derived last.** A type that will not settle means the pattern is not coherent and the entries need another pass | §3.6, §6 step 28 |

## Phase 9 -- make her run (a day, plus the rewrites)

| | do | read |
|---|---|---|
| 9.1 | Her bundle, her sheet's five existence answers with a reason each, and her type on the sheet | §11 steps 1-2 |
| 9.2 | Her prompt directory. **Survey the shared prompts first**: the ones that presuppose a relationship are rewrites, not substitutions, and that is the largest single piece of work in the phase | §11 steps 3-3a |
| 9.3 | Compose her: config, prompts, register row, launcher staged as `.next`, save | §11 steps 4-8 |
| 9.4 | Verify her in isolation, then run the whole build check. **It must end all clear before any restart** | §11 steps 10-11 |
| 9.5 | Her retrieval, tested in must-fire and must-be-silent pairs | §11 step 12 |
| 9.6 | A day run, read against whatever baseline she is being compared with | §6 step 30 |
| 9.7 | Live. Then the audit on day two, against her own words | §6 step 31, §4.1 |

## Phase 10 -- what the procedure owes back (half a day, compute only)

| | do | read |
|---|---|---|
| 10.1 | The loss ledger against the free pass. A version is not frozen as a full version below 90% | §4.7 |
| 10.2 | The data-hunger curve on nested subsets of three, six, twelve, twenty-four and all sessions | §4.7, §8 |
| 10.3 | Write the dated note to `HISTORY.md` under the docs section, the running state to the `HANDOVER.md` header, and nothing dated into the guide | §5.8 |

---

## The stop points

Four places where the honest answer may be to stop, and each one is cheap
compared with what continuing costs.

- **After 5.5**, if two rewrites do not reach the gate: this corpus cannot be
  coded reliably with this book, and it has cost a few dollars and a few days
  of reading to establish.
- **After 6.2**, if the card does not beat n-gram counting on the
  discrimination test and adds nothing on top of it: the reading has
  established nothing as a description of a person.
- **After 7.5**, if most candidate traits are contradicted rather than
  confirmed: the readings are reading the programme, and the convergence count
  was counting a house style.
- **After 8.5**, if the type will not settle: the pattern is not coherent, and
  the response is another pass over the entries rather than a pick between two
  letters.

## The five failures most likely to be repeated

Each of these has already happened once on this project and cost money or a
night's work. The full table is `docs/character-method.md` §5.9.

1. **Using the running character's reply client for a long read.** It discards
   what arrived on a cut and buys the reasoning again. Use the extraction
   client, which streams and keeps what arrived.
2. **A serial coded pass.** Eight concurrent is the default and a serial run is
   wrong, not slow. A pilot expected to take thirty minutes ran seven hours and
   $2.12 because nobody read the ledger for two hours.
3. **A chunk asked whole a third time.** Handle a think-only death inside the
   retry loop: hand the reasoning back once, halve the chunk at the nearest
   segment boundary on the second, never ask it whole again.
4. **A brief that names a range.** Every model returns that range. A floor and
   no ceiling.
5. **A marker noticed while reading a session that later falls in the held-out
   block.** Drop every marker derived from a held-out session; two of five
   apparent drifts on one run were selection on the test set arriving as a
   finding.
