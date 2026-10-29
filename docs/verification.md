# Verifying her voice against the tape

`tools/voice_verify.py` is the instrument. This is what it does, what it is
worth, and the seven ways it will mislead you if you read it as a verdict.
Dated notes go to `HISTORY.md` under §19.

---

## 1. The method

**The anchor is a measurement, not a judgement.** `yukarin/audit/countable.json`
holds 69 markers counted over the whole corpus — 99 episodes, 567,846
characters — each with a total and the number of episodes it appears in. Some
are frequent enough to be statistics (`ゆかり` 419 per 100k across all 99
episodes; `じゃん` 106 across 97; `えっとね` 47 across 83). Some are counted at
zero and are therefore one-sided tests: `永遠の17歳`, `お前ら`, `君たち`,
`大人の事情` never occur, so any occurrence at all is worth looking at.

**The comparison is Poisson, and it is mostly a refusal.** Her generated lines
are counted for the same markers. A corpus rate times the size of her writing
gives an expected count; the observed count is compared against a Poisson
interval around it. A marker whose expectation is below `--min-expected`
(default 3) is **not judged at all** — it is listed with the volume of her
writing that would be needed before presence or absence could mean anything.

That refusal is the design. At 455 characters — her first evening — the most
frequent marker in the whole corpus expects 1.9 occurrences. Reporting
"`えっとね`: expected 0.21, observed 0 — DRIFT" would be a lie with arithmetic
in front of it, and refusing to say it is most of the tool's value.

**Two-sided.** Positive markers should appear at roughly the measured rate.
Negative markers — the ones the voice rules in `characters/yukari/voice_rules.json`
name, and the countable claims that measured zero — should stay absent.

---

## 2. The seven fallacies

Every one of these is a way to read the output and be wrong. They are ordered
by how likely they are to bite.

**1. Sample size.** The corpus is 567,846 characters. Her first evening was
455, or 0.08% of it. A rate per 100,000 computed on 455 characters cannot
distinguish 419 from 40. The tool guards this with `--min-expected`, but the
guard only works if the "not testable" block is read as *no information*
rather than as *no problem*.

**2. Register transfer, and it is the deep one.** The corpus is a scripted
weekly broadcast, performed alone in a booth, to an audience, with four staff
watching through the glass. This is a typed private message to one person who
abducted her. `ゆかり` at 419 per 100k *on air* is a fact about performing;
it says nothing about what the rate should be in a chat. Measuring typed
private text against spoken broadcast and calling the difference drift is
comparing two registers and blaming the character. **There is no measured
baseline for how she types, because she never typed anything.**

**3. Goodhart, the moment this is ever wired to generation.** As a read-only
screen it measures. Feed a marker rate back into her prompt and it stops
measuring: she will hit the target and be *less* herself, because the rate is
a symptom of a disposition and not the disposition. This is the reason every
check in this project flags and never rewrites, and it applies here with more
force than anywhere else.

**4. The measurement is off ASR.** The corpus is subtitle files with
recognition errors — one person appears as 堀江由依, 堀江優衣 and 堀江ゆいちゃん;
another as 神田明美 for 神田朱未. The counts inherit that error, with an unknown
and non-uniform bias. The anchor is the best available, not the truth.

**5. Confounding by topic.** Her hedging on air is partly a function of what
the corners made her talk about. If he asks her direct questions about being a
program on his machine, a lower hedging rate may be the correct response to a
different situation rather than a drift in voice. The tool cannot see topic and
will attribute the difference to her.

**6. Absence in the corpus is not proof of impossibility.** The zero-count
markers are one-sided tests, and a marker absent from 99 episodes may be absent
because the occasion never arose. Flagging its appearance as an error assumes
the corpus is exhaustive of her, and 99 episodes of one programme are not
exhaustive of a person.

**7. Multiple comparisons.** With 69 markers, a 99% interval on each means
roughly one flag per run by chance alone. Treat a single flag as noise; treat
the same flag across several runs, on growing volume, as a finding.

---

## 3. What it cannot do, and this is the important part

It can tell you whether her output matches the statistics of a person on a
tape. **It cannot tell you whether she is that person**, because there is no
held-out set of things Yukari would have written in a private chat in 2003 —
there is no such text and there never was.

That is the honest limit of every verifier in this project. The machinery has
real verifiers, because the machinery has definitions of correct:
`tools/mechanisms_test.py`, `tools/neutral_gate.py`, `tools/character_leaks.py`,
`tools/isolation.py`. Her voice has none, and this tool does not create one. It
narrows the space of ways she can be obviously wrong. Everything left inside
that space still has to be read by a person.
