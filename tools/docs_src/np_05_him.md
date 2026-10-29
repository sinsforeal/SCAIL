
---

## 10. Her picture of him (`sim/`: beliefs, expectations, the stances)

### 10.1 `model_of_him.py` `ModelOfHim` and `model_of_her.py` `ModelOfHer`

Beliefs she has decided (`characters/tomoe/beliefs.json` seeds a fresh save, then
`settle_against_history` puts the day-zero picture where months of him
would have left it; `characters/tomoe/self_beliefs.json` for her own). Each carries
certainty, evidence, what she has riding on it, strain. `strain(bid,
amount, why)` (fades on `beliefs.strain_half_life_days`; a certain belief
does not wear by degrees), `confirm` (raises evidence; without it every
belief could only erode), `_graduate` (demonstrated past arguing: for him
it becomes a `user_fact`, for her it stays marked known),
`due_revision` / `revise` (one call, role `settle_beliefs`, rewrites in
her own voice; the old wording kept; never in the same breath as the
discovery -- `App.maybe_revise` waits for a quiet moment). Writers: the
ick, foresight, expectations, wonder, comparison, goals, attachment
episodes. `prompt_text`, `brief` (for the ick: what there is to violate).
`/beliefs`, `/self`. history: archive §5.41, §5.44.

### 10.2 `ick.py` `Ick`: what a discovery costs her

Every route into her picture of him passes `App.assess_learned` (gates
are about volume, not significance): the `ick` role scores a thing
against her beliefs and her kinds (`kinds_text`: what she has already run
into, copied back exactly), multiplied by her unease (`_state_multiplier`:
only unease adds) and by what the circle would make of it
(`_circle_multiplier`; `SocialGraph.witnessed_heat`). Items live in kv
`charged` with a half-life; `carrying()` (hot, cannot raise without
admitting how she knows), `unraised()` (hot, could raise), `teasable()`
(cooled and familiar: just how he is), `bars(text)` (the thread pressure
may not push out a thing she cannot raise). Warms `surprise`. kv
`ick_kinds`. `/ick`. history: archive §5.41, §5.89.

### 10.3 `approach.py` `Approach`: getting at a sealed thing

The outlet for what she carries and cannot admit knowing: `due(scene)` is
pure code (pressure from live charge, time, nowhere else to put it;
opportunity and cost, never importance), `write` (role `approach`) **decides
and writes no words of hers** -- the subject she steers toward, the angle she
comes at it from and how close that comes to giving her away -- and her own
call is handed the subject and the angle as a hint and writes the message.
`note` records the subject before the bubbles go and lets the pressure down.
kv `approaches` (rows from before this carry a `line` instead of a `subject`;
nothing was migrated). `/approach`. history: archive §5.62.

### 10.4-10.5 `withholding.py`, `attachment.py`: the two stances she takes toward him

Both specified in full in `docs/stances.md`, and they read each other: the
attachment stance is one of withholding's pressures.

**Both are off for the second character** (her sheet, `mechanisms_absent`, his
call): neither has fired once in her whole life -- 127 run
directories with no `[withhold]` and no `[attach]` line in any of them -- and
the pressures they sum are made of tension, resentment, an open rupture and a
stance that have never moved for her. Nothing else changes for her: every
output of either is derived from a live episode row, so with no row there is no
situation line, no register line, an impulse bonus of 0, a delay multiplier of
1 and a withholding pressure of 0.0, which is what they already returned. The
one reader that did move was `/sweep`, which computed the pressure whatever the
section said: it now shows no `withhold` column for a character who has not got
the decision, so a gauge whose only mover was that column cannot read as alive.
Nothing loses a gauge: withholding wrote `unsaid`, `awkwardness`, `guilt`,
`validation_craving` and his tension only while a hold ran, and each has other
writers.

**10.4 `withholding.py` `Withholding`: not answering, on purpose.**

Not answering on purpose: pressure from tension, anger, shame, sadness,
resentment, a rupture, tit-for-tat, gone cold, where she stands, the
attachment stance; one `withhold` call writes the decision (kind, minutes,
why, what breaks it); holding costs unsaid / awkwardness / guilt; the
sulk nobody noticed irks; `resolve()` raises what her own impulse must
clear -- never a lock; caving costs shame. Aims anger / sadness at him.
A `silence` consumes his message while it runs and gives it back to her
reply path once if the clock runs out with him still quiet
(`silence_hands_back`), which a restart still never does.
kv `withholding`, `withholding_log`, `withholding_handed_back`. `/withhold`. **spec:
`docs/stances.md` §3.** history: archive §5.64, §5.92.

**10.5 `attachment.py` `Attachment`: protest, deactivation, the switch.**

No LLM. `threat` from his silence, being left on read, tension, ruptures
and scars, the unanswered streak, scaled by attachment; an episode opens
when threat holds, picks protest or deactivate from what her beliefs and
her last episodes pull toward, switches when the running one fails (a
push gives out after `protest_exhaust_hours` of quiet, counted from his
last message: one he has answered has not brought nothing back),
closes on burn-out or once the threat has actually gone (his message is
not a resolution by itself). Readers: the register (a stance before a
mood), impulse, streak, withholding pressure, delays, shape, what a
person near her could SEE. The end of an episode is evidence about the
beliefs it bet on. kv `attachment`, `attachment_log`. `/attach`. **spec:
`docs/stances.md` §2.** history: archive §5.79.

### 10.6 `foresight.py` `Foresight`: what she expects him to do next

One `foresee` call when she sends (and refreshed while he is quiet,
`App.maybe_foresee_refresh`): the chance he answers, the window, the
tone, what may land badly, what his silence would mean, her plan --
with her last predictions AND their outcomes so the model sees where she
was wrong. The record writes the outcome: his next message closes the
live one (minutes, inside the window or not); the compile closes what is
older than `stale_hours` as a silence. `accuracy()` is her calibration.
Readers: her situation block, the intent, the withholding, the impulse
(`impulse_weight` x (1 - reply_p)). **The risk each prediction names is
scored here too** (`score_risks`, every pass and after his message):
happened if his next mood read is cold inside `risk_hours`, passed if
not, unclear if nothing came; happened warms guilt and shame
(`risk_guilt`, `risk_shame`), passed warms relief (`risk_relief`). It was
mirrored into the expectations as rows once, and seventy-nine of eighty
rows on a save were that mirror. kv `foresight` (`keep`; `risk_state` on
the row). `/foresee`. history: archive §5.87.

### 10.7 `expectations.py` `Expectations`: his word held to the record

Three kinds, all settled by code off the record: `do` (he said he would;
role `expect_him` names it, when it is due in his local time, how she
could know, the words that would show it, the belief it rests on; kept
when a message or a digest carries the words before the deadline, missed
when it passes), `around` (mirrored from `rhythm_said`), `habit` (learned once a day at the compile from a week of
digests, role `habits_him`, kv `habits_him`; each window checked against
the digests that covered it; a miss is a small event she can notice).
Kept `do`: the belief confirmed, a little relief. Missed `do` / `around`:
strain, resentment, tension, an event, and the row is raisable in her
situation block until she brings it up or it ages out. `tick()` every
pass, no model. kv `expectations` (`expect.keep`), `habits_checked`.
`/expect [now]`. history: archive §5.91.

### 10.8 `wonder.py` `Wonder`: questions she is curious about

A question is an object: what she wants to know, kind (`test_him`,
`compare_self`, `understand`), the belief it bears on, a charge, whether
she would ask it straight. Code decides when one forms (`due`: curiosity
over its rest or something just seen -- `seed(why)` from a look, a snoop,
a discovery; cooldown, `max_per_day`, a cap on open ones); the `wonder`
role decides what. The intent gets `candidates()` by id and may pick one;
the persona puts it in her words; the send marks it asked (`note_asked`,
and a reply to him that voices an open question in its own words marks
it asked too, `voiced`, `voiced_min_words`);
his next message inside `answer_hours` is judged by `wonder_answer`
(confirmed / disconfirmed / dodged / unclear + what she learned). Effects
are code: confirm / strain the belief; `compare_self` moves attachment
(like her: closer); dodged warms curiosity and leaves it standing; what
she learned becomes a fact about him. At the compile `review(date)` judges
open questions older than `review_after_hours` against the day's chat as
answers he gave on his own, and past `open_max_age_days` a question fades.
kv `questions`, `wonder_counts`,
`wonder_last_ts`, `wonder_seed`. `/wonder [now]`. history: archive §5.93.

### 10.9 `goals.py` `Goals` and `outlook.py` `Outlook`: what she wants

`Outlook.morning(schedule)` (role `morning`, at the day boundary): what
she woke up wanting and dreading, anchored to a self-belief
(`ModelOfHer.anchor_brief`); `experience` (role `experience`, on cue: a
thing she is doing becomes felt -- the cue is `trigger_regex` for the verb
AND `object_regex` (or a title on her watchlist) for the THING, because her
verbs attach to him as readily as to a show and "reading his reply" was
spending the day's `max_per_day`) and `anticipate` (role `anticipation`:
what she is looking forward to or bracing for; `anticipation.hours_in_prompt`).
kv `morning_intent`, `anticipation`, `experience_*`, `his_first_active`.
When the cue is her watching an episode, it is grounded: her own
watchlist (`sim/watchlist.py`, kv `watchlist`, a cursor per show) pins the
real title and episode, and `sim/recap.py` fetches a real あらすじ for that
episode, which the call reacts to instead of inventing the plot (K-On ep15
was confabulated as a lyrics scene; it is a marathon episode). **The fetch is
the judged path, the same one his watching uses** (`Recap.synopsis`): the
episode's own Japanese subtitle file as an anchor where one exists, then a
ranked source list fetched without a browser in parallel with the Japanese
search, one digest per candidate and one judge over all of them, and a row
marked provisional / judged / anchored. Her own watching used to take the
first page that passed the section test and trust it forever, and until
2026-09 it also had neither of the two English sources: they are reached only
with an English title and an id, and this caller passed neither. It passes
the title now, and `Recap.synopsis` resolves the id off his own list where
that list holds the show without ambiguity. What it never has is a file of
his to listen to, so a show of her own that no archive carries stays
ungrounded rather than being transcribed. `/watch`.
**The list becomes hers** (`Watchlist.pick_own`, role `watch_pick`,
`watchlist.pick_*`): at the compile, short of `keep_min` unfinished shows
or every `pick_every_days`, one call picks the next thing she would put
on from her own corner -- her sheet, the accounts she keeps liking, what
is going round -- with his list as context, not a fence: a pick that is
also his is marked `his` and kept (a show being his does not disqualify
it; a pick must simply never be FOR him), a duplicate of her own list is
re-asked, and the pick lands at episode 1 marked `own` with her reason
(kv `watch_pick_log`).
`/watch pick` forces one. Her searches on X seek her shows' Japanese
titles (`Taste.queries`).
**spec: `docs/recap.md`.**
A today-goal not re-formed the next morning is marked `lapsed` at the settle
(`open()` already read it so); `stress` and `health` read the raw rows and now
count live wants only.

`Goals.note_morning` makes the want a goal (the same want two mornings
running is one want carried); `settle(results, date, ...)` at the compile
puts each open goal against what happened, and an outcome costs her
(`cost_of`: what she had riding on it, whether it was witnessed, the
belief it held up), can make her give up (`give_up_at`: when keeping
wanting costs more than the thing holds up -- the expensive one), feels
like something (`_feel`), and may become a memory (`_remember`: a day
that went against her stays longer). Readers: `situation_line`,
`director_line`, `intent_hint` (the standing want about him she keeps not
acting on), the stress load. kv `goals` (`goals.max_kept`). `/goals`.
history: archive §5.33, §5.42, §5.44.

### 10.10 `receipts.py` `Receipts`: has he seen it

On Telegram: whether his desktop has HER chat open (`_is_her_chat`:
process and the exact title), read after `read_min_seconds`, idle after
`idle_after_minutes`; `status()` -> unseen / seen / read / replied;
`line` for her situation block, `brief` for the director and state. On
TALKAPP a stamped `read_ts` from the hub is trusted first. history: archive §5.8.

### 10.11 `cast_psych.py` `CastPsych`: what she holds with the people around her

Rupture and repair, expectations and withholding are keyed to him: a fight
with Rena healed by the clock, "Rena said she'd send the photo" came due
nowhere, and she could not once choose to leave Hinako on read. This is the
same four mechanics turned toward the cast, plus the one only friendships
have. One `bond` call when an exchange finishes (`after_exchange`, from
`App.on_talk`) says whether it broke something (`what`, `whose` hers /
theirs / both / unclear, severity), whether it mended one already open
(mended / tried / worse / nothing -- time is never an answer), what THEY
promised her (a due time and words), what they delivered, and what SHE told
them in confidence (`secret`, and `about` whom). Code moves the numbers:
her meters with them (`state.relationships[key]`), sentiments
(`sim/sentiment.py`), guilt / shame / relief, events, a memory by the
moment (`source="bond"`). The day boundary ages it (`age`): an open rupture
scars after `scar_after_hours` and takes closeness with it; a promise past
due is missed and costs resentment. `leave_it(who, kind)` is the roll off
her standing with them -- tension, resentment, an open rupture that is
theirs, a low hour -- that has her look at their message and leave it,
which the exchange treats as her not answering (the group carries on; a
line sits). Readers: her turn (`line_for_her`) and theirs (`line_for_them`)
in the exchange, her own prompt (`prompt_text`), the planner (`brief`), and
the loyalty line -- a confidence told to one friend `about` another shows
up in her turn with the second as a thing they do not know she said. Not
built yet: favours owed, and loyalty conflicts as a pressure of their own.
kv `cast_bonds`; `/bonds`. history: §10.11.

