# The judge-role A/B, read: pro against flash on the first character's four judge roles

<!-- doc: reference -->

What was compared, how it was verified, what it found, and what to do with
it. The data is kv `model_ab` in `data/world.db`, read read-only on
2026-09-03 07:5x; the mechanism is `model_tier` in `config.json` (PROJECT §1
*Providers*, `docs/model-harness.md` §6). The pairs themselves are the
receipts: every judgement below names its pair number, and the pairs are
dumped to `data/voicelab/_ab_dump.txt` with the exchange each commit
judgement read beside it in `data/voicelab/_ab_exchanges.txt`.

## 1. What the A/B is

Four of the first character's roles are judges rather than writers: the
commitments judge (`commit`), the day's compile (`timeline`), the coherence
read of the compiled day (`coherence`) and the cast's day planner
(`cast_day`). `model_tier.use_pro` puts them on `deepseek-v4-pro`; every other
role of hers is on `deepseek-v4-flash`. With `shadow_flash` on, each pro call
is repeated once on flash on the same input, and both answers are kept with
their timings. The pro answer is the one that ran; the flash answer is never
used. The question the harness asks is whether pro earns its place on these
four roles.

## 2. What was collected

| role | pairs | pro time | flash time | input | pro per call | flash per call |
|---|---|---|---|---|---|---|
| commit | 35 | 2.1 s | 2.5 s | ~1,100 tok | $0.0017 | $0.0002 |
| timeline | 2 | 30 s | 62 s | ~33,000 tok | | |
| coherence | 1 | 27 s | 23 s | ~17,400 tok | | |
| cast_day | 2 | 29 s | 29 s | ~13,100 tok | | |

Forty pairs from 2026-08-31 23:46 to 2026-09-03 06:37. Prices are the mean
of Tomoe's own ledger over the same days. Flash's mean time on the commit
role is dragged up by three outliers of 16, 10 and 9 seconds; its median is
under a second.

**Two limits of the data.** The store keeps each answer cut at 2,500
characters and does not keep the input, so the three long roles can be
compared only on their openings and against the record; and 35 of the 40
pairs are one role, so the verdict is really a verdict about the
commitments judge.

## 3. How the commit pairs were verified

The commitments judge reads one exchange between her and a person in her life
(in Japanese) and says what SHE agreed to: a named person, a concrete thing, a
real date; three kinds (attend, buy, bring); cancellations and amendments of
the open commitments it is shown. For every one of the 35 pairs I found the
exchange it read (kv `cast_chat`, matched by her clock, which is his plus the time difference), read it, decided what a careful reader would record, and
scored each answer against that. The open list at the time is kv
`commitments`.

## 4. What the commit pairs show

**Agreement.** On 14 of 35 both answers are right, almost all of them
correctly empty: doubt about the obi, a lemon tea offered by a friend, a
question left open, a mother's chat about dinner (#0, #3, #6, #9, #17, #18,
#21, #23, #25, #29, #32, #33, #37, #39). On 5 more both make the same
mistake, and it is the same mistake each time: re-recording a promise that is
already on the open list as a new one. 「写真、今日こそ送るけん」 to Rena (#20,
#22) was already `c178808387914`; both wrote it again.

**Where they differ, pro is right more often: 8 pairs to 2.**

Pro right, flash wrong:

- #1 -- flash re-records the notebook promise to Aya that is already open
  (`c178814393515`); pro amends the open one's date instead.
- #4 -- Hinako offers to buy drinks and Tomoe accepts a lemon tea; flash
  records a 150-yen purchase by Tomoe. Pro records nothing.
- #8 -- Rena: 「写真、明日の夜までには送るから」. Pro amends the open photo
  promise to tomorrow; flash records nothing.
- #11 -- 「お母さんが結んでくれるなら、ちゃんと着ていくけん。約束する」. Pro: one
  promise to her mother. Flash: two, the second being that her mother will tie
  the obi, which is not hers to do.
- #16 -- a breakfast repeat of the yukata promise to her mother. Pro records
  nothing. Flash records two promises **to Rena, who is not in the exchange**:
  send the photos, go to Hime in yukata.
- #19 -- 「うん、寄ろっか … ちゃんと行くけん。約束やけん」 to Hinako about the
  clips. Both get it; flash adds the Sanrio purikura, which Tomoe raised as a
  question (「祭りの前に寄る？」) and nobody settled.
- #31 -- Aya: 「今日、ちゃんと渡すけんね。約束やけん」. Pro: return the notebook
  today. Flash: nothing.
- #38 -- Kaito asks whether she is really going tomorrow; she answers about
  his knee and tells him to get up on time. Flash records a promise to go to
  the festival with Kaito. Pro records nothing.

Flash right, pro wrong:

- #26 -- her father, the night before: 「8時45分、駅前や。遅れるなよ」 /
  「ちゃんと起きるけん」. Flash records the 08:45 meeting for the next morning;
  pro records nothing.
- #36 -- Aya: 「写真ちゃんと送るけんね」. On the first read (#35) both miss it;
  on the re-read flash records it, pro misses it again.

**The kind of mistake differs, and that is the finding.** Pro's errors are
misses (#5 「クリップ、ちゃんと買うけん。約束する」 not recorded; #26; #35) and
one invention (#30: a promise to Kaito to get up on time, in an exchange with
her mother -- and that one is in her live commitments as `c178838732022`).
Flash's errors are inventions: three times it wrote a promise to a person who
was not in the exchange, lifted from the open list it was shown (#5 the
notebook, #16 Rena twice, #38 Kaito). A missed promise costs her a beat later;
an invented one becomes a thing she "said" and the ledger, the cast and the
compile all build on it. On this role the dearer model is the safer one, and
it is also, on the mean, the faster one.

**A fault of neither model, and already handled.** Five pairs re-emit an
open promise as new: 「今日こそ送るけん」 said again reads as a new promise to
both of them. The caller folds it (`Commitments._bind` treats the same thing to
the same person as a restatement and moves the date), and the store confirms
it: one photo promise to Rena, not five. What the caller did NOT catch is the
cross-person invention -- a promise to a person who was not in the exchange --
and one of pro's landed (`c178838732022`). One more thing the store shows: the
clip promise of 09-03 07:15 is filed under her mother, because the judge
wrote the counterparty as 「ひなちゃん」, the roster did not resolve it, and
the caller fell back to the person she was talking to.

## 5. The three long roles, on what can be seen

**timeline** (#13, #27; 09-01 and 09-02 compiles). Both write a full day in
order. Flash's opening is denser with exact times and quoted lines; pro's is
plainer. Pro was the one kept (the `days` table for both dates opens with the
pro text). Flash took twice as long on both (84 s and 41 s against 29 s and
31 s). The coherence read of 09-01 (below) flagged one line of pro's compile
that the record supports: she did tell Hinako she was not sure she would
wear the yukata (「私、ほんとに浴衣着るんかな」 in #5, #6, #11, #12), so the
flag against the compile was the flag's error, not the compile's.

**coherence** (#14, 09-01). Both found the same first seam and both misread
it: 「rena couldn't come. i went alone」 to him is about the Otsuka festival of
08-29, whose photos are the ones she keeps not sending, not about that day.
Neither reader had the earlier festival in view. Pro's fourth seam is a real
catch flash missed: her exchange says 「レモンティー、もらおうかな」 and the
scene twenty minutes later has her holding a cold oolong tea. Flash's fourth
and fifth seams read the compile as contradicting the record where the
record supports the compile. Pro slightly ahead; both need the earlier days
in their window before "went alone" can be judged.

**cast_day** (#15, #28). Pro's beats are the record's threads carried
forward: the silver cicada clip, the notebook with two stars, Rena's sister's
fever, the 19:00 meeting at 姫, Rena dark from 19:00 because her mother took
her phone. Flash on 09-01 writes English role names ("Rena-chan", "mom") where
the record uses their Japanese names, and on 09-02 keeps Aya absent "at home
with her visiting grandmother", which was 09-01's reason and had ended
(「ばあば、今日までだから」). Pro ahead on both days.

## 6. What to do with it

**His decision (2026-09-03 08:3x): flash for the judge roles too, the A/B
off, and the two faults fixed at the caller.** `model_tier.use_pro` and
`shadow_flash` are false in both configs and in the defaults.

- **A promise binds only to somebody who was in the exchange**
  (`Commitments._bind`): the counterparty of a private one, a speaker in a
  group one. That is the guard against the invention flash made three times
  and pro once; a promise the judge writes to anybody else is logged
  `[commit] not bound` and dropped.
- **The coherence reader is given the compiled summaries of the previous two
  days** (`coherence.context_days`), so 「rena couldn't come. i went alone」
  is judged against the festival of 08-29 rather than called a contradiction.
- Not fixed: a counterparty the roster cannot resolve (「ひなちゃん」) falls
  back to the person she was talking to. The aliases are the roster's to
  widen.
- **The second character is out of this.** Her judge roles moved to flash on
  2026-09-03 and her `use_pro` is off; her pairs (kimi against flash, a
  handful) were not read here.
