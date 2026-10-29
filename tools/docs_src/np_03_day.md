
---

## 8. Her day (the wake and the director in `sim/`, the body and the place in `embodied/`, the day's planner and the household facts in the program)

### 8.1 `schedule.py`: the day's blocks

**The planner is the program's, the wake is shared.** `sim/schedule.py`
holds what is true of any character's day -- `wake_time`, the contiguity
check (`validate`), `block_at`, `describe`, `presence_label` and
`check_people` -- and each program writes the day itself:
`tomoe/schedule.py` is the schoolgirl's (the timetable, the skeleton with
her commute in it, `generate`, `replan`, the flat-day and kept-promise
flags), `resident/schedule.py` a flat and a week of her own. Everything
below about bells, lessons and classmates is the first character's
planner.

Once per date (`ensure`, at the day boundary): `wake_time` (with the sleep
model on, the wake falls out of the night: bedtime, hours slept, how rough
it was; `schedule.wake`, kv `wake_days`), `skeleton` from the calendar's
school-day template, then the `schedule` role fills the day honouring the
events she has said yes to (`events.py`), the family brief, the household,
her health note and her money note (`health_note_today`,
`money_note_today`), the open threads. An open promise with a start time on that date is an ALARM: `Health._alarm_for`
pulls the night's wake back to it minus
`schedule.wake.commitment_lead_minutes`
before the hours are measured, so a morning she has to be up for costs her
the sleep; `Commitments._wake_needs_redrawing` throws away the drawn night
the moment such a promise binds, so it is decided when she agrees and not
when the plan is built. Whether she actually gets up is `_rising`: duty is
not the term (school is compliance and has its own branch) -- a `want` goal
naming the morning against an `avoid` one, the event stance and who PUSHED
it, and `belonging` below its ref, which pulls her up out of a morning she
dreads because absence is the danger; against a short night and `unwell`.
Signed, clamped, `early_max_min` before the alarm or `snooze_max_min`
past it, applied before the hours are measured (`schedule.wake.rising`).
**Beating the alarm is a rested body's trick**: the early side is scaled by
how close the night gets her to her need and shuts entirely past
`early_needs_rest_hours` short of it, so on six hours of a needed eight and
a half the most that wanting the morning buys is being up when it goes
instead of lying there. She was rising 25 minutes EARLY on a 2.35-hour
deficit because she was keen, which is not what a fifteen-year-old does.
The snooze side is deliberately not gated -- being short of sleep is the
reason people snooze. **And the alarm reaches backwards into the night
before it** (`Health._sleep`): `planned_bed_*` is the same hour whatever
tomorrow holds and the delay only ever pushes it later, so the system was
taking her sleep and then charging her for being late with it -- she never
had the evening to decide about. The shortfall between her usual bedtime
and `alarm - need_hours` is closed by `early_bed_pull` of it, scaled by
what the morning is worth to her (the same `_pull_for` that decides whether
she gets up for it) and by what keeps her up on any other night (the same
anxiety / unsaid / screen delay, which scales the ceiling too so the phone
can win). Capped at `early_bed_max_min`. **The record says she knew either
way**: "turned in 50 min early for the morning", or "she knew she had to be
up and stayed on her phone anyway", or -- for a morning she does not want --
"she had to be up and did not go to bed for it".
**On an alarm morning the structural floor does not apply**: `wake.free_min`
means "she does not get up before eight for nothing", and a promise with a
time on it is not nothing -- clamping the drawn wake back up to it threw
away a night the sleep model had already planned around being up, and left
the two records disagreeing by forty minutes with the plan following the
wrong one. The only floor then is `wake.school_min`, the earliest this
system ever has her up. After the plan is built, `_promises_kept` logs any
timed promise the blocks do not cover (`[schedule] the plan does not keep a
promise: ...`); it flags and never rewrites, because a day where she is
late is a real day and the commitment settling BROKEN a day later was the
only signal before. `replan(change)` keeps the day up
to now and re-asks the rest when the director reports a
`schedule_change`; `/schedule regen` throws away today's cached wake and
rebuilds the plan, which is how a fix to the drawing reaches a day already
begun. Table `schedules` (date, blocks, notes); `describe`.

**A school day is one block per bell, and what she can do with her phone
follows from where she is.** `_school_windows` sorts the timetable's own
windows -- morning homeroom, six periods, lunch, cleaning duty, final
homeroom -- and fills every hole between them with a break, so the day
cannot come out with a gap or an overlap however the times are edited;
`_school_blocks` gives each one its words, its company and its phone rule.
Fifteen blocks between the first bell and the last where there were four.
The times and the phone rule live in `school_day` in
`data/school_calendar.json` and nothing in the code carries a bell; the
constant `SCHOOL_DAY` in `schedule.py` is only what stands in when that
file gives none.

**A lesson is `phone_access: "none"` and the ten minutes after it are
`"glance"`.** The school rule is the phone off and in the bag in a lesson
unless a teacher says otherwise, so a lesson, either homeroom and an exam
are `none`; a break and cleaning duty are a look and nothing long; the
lunch break is `free`, being the one stretch of the day long enough to
answer somebody properly. The value has to *change* at those boundaries and
not merely be permissive, because `maybe_reply` redraws the reply plan only
when it changes: a whole school day on one value gave a message one coin
flip and then nothing until the train home. `_flat_school_day` says so in
the log when a planned school day comes back with a single value, and never
rewrites it -- an exam morning or a school trip legitimately is one stretch.

Three more things depend on the blocks being small. `cast.py` writes an
`in_person` beat only where the schedule has them together, so a morning
naming nobody is a morning in which none can be written; a four-hour block
gives the director nothing to move through, which is how one activity
string came to be repeated eight times across two and a quarter hours; and
`presence_label` turns the block into the line his messenger shows under
her name, so "in class" and "asleep" stop being the same silence.

**The words are the program's** (`presence_words` and `presence_by_phone`
in `tomoe/words.py` and `resident/words.py`, through `sim/sight.py`; the
label takes the config). The first character's table is a schoolgirl's
world -- in class, on the train, at lunch, cleaning duty -- and the second
character's is empty, because "bath" matched "away" while she was replying
from it: she gets her plan's phone rule alone, asleep or online. The
phone-rule fallback is the program's too (a dark phone is "away" for one,
"asleep" for the other). `tools/sight_words.py` fails on the school words
in shared code.

**Who is beside her comes from the roster, never from a literal.**
`_friends` asks `roster.classmates`, which reads `school: "same"` from
`data/cast.json` -- a fact about a person, kept on the person, because
having a timetable is not the same question as being in her room (her
brother has one and is at the local primary). `check_people` then drops any
name in a block's `with` that nobody on the roster owns and says so
(`[schedule] FLAG ...: nobody on the roster is ...`), at generation and at
replan. A name there is a claim that somebody is in the room, and every
mechanism downstream keys on the roster: a stale one is not a cosmetic error
but an empty chair the record cannot see, occupied by a person the director
keeps describing. `NOT_PEOPLE` -- the words a `with` may hold that are not a
person -- is defined here and imported by `ledger.py`, so the gate that
keeps a stranger out and the audit that reports one read the same list.
Log `[schedule]`, `[wake]`. `/schedule [regen]`, `/replan`. history: archive §5.1, §5.15.

### 8.2 `director.py` `Director`: the scene

Every `director.tick_minutes` while awake (`needs.red_tick_minutes` when a
need is red), one scene from the `director` role: location, activity, who
is with her, `phone_access`, a sensory line, events,
`share_worthy`, `ate`, `spent`, a `schedule_change`. **It writes nothing of
what is on her mind and nothing of what she would say**: both fields were read
back to her, and one of them she typed. `share_worthy` stays as a pull, and
the scene's `share_hint` key is still set by what her sight puts in front of
her (a note she has just opened, the week's shelf, the account) rather than by
a paraphrase of her. The night is ONE
scene (`sleep_scene`, role `sleep`, written when she goes under;
`sleeping()` is rebuilt from the scenes table on boot, not a flag in the
dict). The night's message carries the date and `THE TIME OF YEAR` from
the clock (`WorldClock.time_of_year`, in her instruction language) and the
prompt names no season of its own: what the room is like -- what is
running, what comes in the window, how early it gets light -- is asked for
from the date it is given. The prompt carries her body now (situation, health, hunger, money),
the family line (`_family_txt` never lets the tick down), the friends'
line, what Japan is on about, the open threads, the spiral's line, what
just happened (`extra_events`: discharges, cast beats, hazards, journeys).
`due(schedule)`, `phone_access(schedule)`, `asleep_block`. Table `scenes`
(ts, date, hm, scene, raw); kv `director_last_tick_ts`,
`director_next_tick_minutes`, `open_threads`, `sleep_scene_ts`. `/scene`.
Invariant: the director is TOLD where she is on the way (situation) and
may not put her at school before she has arrived. For a character with
`household.enabled` (`sim/household.py`) the director is also shown her
household -- her things with a state and the moves allowed -- and returns
`household_changes`, checked by code against the seed and the day's budget
and written as events; her own director prompt then carries no voice fields. history: archive §5.2, §5.15.

**An event that differs from the last one only in its figures is not written**
(`_same_but_the_figures`, kv `last_life_event`). A tick is asked for a scene
whether or not anything has happened, and a machine he has walked away from
produces the same true sentence every time: "He's been away from the machine
for 116 / 177 / 237 / 371 / 485 minutes, nothing touched since 04:19" was 32 of
the 35 events written about him in one day. Nothing downstream can tell those
from 32 things happening, so her day so far, her diary and the compile all read
them as a day of events, and she reported one observation to him in four
messages across 25 hours. Digits, clock times and the words that only ever
carry a figure are stripped from both sentences and what is left is compared;
only the immediately previous event is compared, because a thing that genuinely
happens twice with a gap between is two events. The line is `[director] event
dropped, the last one said this with different numbers`. The household's moves
are not compared: those are states of things in her flat and two of them are
never the same sentence with a number changed.


**The hole and the catch-up.** kv `director_last_model_ts` is the last
scene the model actually wrote; a tick whose answer did not parse writes a
placeholder cut from the schedule block and leaves that key alone. When
the two drift apart by more than 2.5 ticks, or `App.catch_up` has set
`director.catch_up`, the next prompt carries `THE RECORD HAS A HOLE: from
HH:MM to HH:MM nobody wrote her` with the schedule blocks that passed, and
asks for the whole stretch as one scene, events in order, ending where
she is now -- the night scene's idea applied to an outage. The trigger:
`LLM.call` writes every call that no provider answered to kv
`missed_calls` (`/missed`); once a provider is back (`llm.last_ok_ts`) the
loop runs `App.catch_up` before the tick: `director.catch_up` set, the
next phone look forced (`phone.force_next`, so his telemetry for the
stretch is digested and the X action queue runs), the rows moved to
`missed_calls_done`. `/catchup` does the same by hand and forces the tick.
The state model then reads the catch-up scene's events as it reads any
scene's, so what she went through in the hole moves her.
### 8.3 `situation.py` `Situation`: a situated body, no LLM

**The replay.** The one-scene catch-up writes hours as a scene stamped
now, and every reader then runs at now with its own clock (the state read
three hours as one quiet tick; the anticipation dreaded "tomorrow's"
ceremony at 11:44). `python tomoe\run.py --replay "<from>" "<to>"
[--speed N]` (her program's entry point, or `resident\run.py` for the
second character; machine-local times, the bot stopped) re-lives the
stretch instead: the
save is copied to `data/retired/<ts>_replay/`, what the bot wrote inside
the window is retired (`Store.retire_window`: scenes, events but the
world's kinds, state_log, self_memories), the gauges go back to the
snapshot at FROM (`Store.gauges_at`), the director is pointed at FROM,
today's anticipation keys are dropped and the missed rows marked
`replayed`; then the loop runs the window on a sim clock at `--speed`
with the delivery withholding every bubble (`Delivery.withhold`), the
reply, the impulse, phone looks, X actions, hazards and sensors off, and
stops at TO (`_replay_finish`, kv `replays`) without compiling. Every
scene, event, gauge move and memory lands at its real time from the
mechanism that owns it. Nothing reaches him from inside the hole: a line
written at 09:30 cannot be sent at 11:50 as if it were 09:30, so what is
unread waits for the live loop with the gap honest in the thread. A
window holding a message of hers is refused. The replay is only as good
as the schedule: a calendar event the planner folded into "classes" does
not happen in a replay either (the planner rule in `prompts/schedule.txt`).
**The estimate comes first** (his rule): before anything is touched the
command prints the window's ticks (`director.tick_minutes`), ~3 model
calls a tick, the cost at `replay.usd_per_tick` and the wall minutes at
`replay.speed`; past `replay.cost_warn_usd` it refuses without `--yes`.
**The temporal gap** is the honest alternative: `--replay FROM TO --gap`,
or `/gap` from ops for the hole the record knows (the last model scene to
now, widened by the missed calls), writes one event of kind `gap` at the
hole's end -- `[08:40-11:59] the record has nothing for this stretch:
nobody wrote her; she lived it unrecorded` -- points
`director_last_model_ts` past it so `_hole` never asks for it, marks the
missed rows `skipped`, and keeps kv `gaps`. The compile and the coherence
read see a blank, never a stretch invented at the wrong hour. The span
carries its date at each end when the two ends fall on different days of
hers, and its length in the unit that fits it -- minutes, hours or days --
so a stop of three days does not read as one evening. A caller may pass a
second sentence naming the cause, which goes into the event after the
first.

**Coming back from a deliberate stop** (`sim/downtime.py`, config
`downtime`). A stop is `Stop-Process -Force`, so the process being stopped
writes nothing on its way out and the next one would otherwise see an
empty stretch as work outstanding. The stop tool writes kv `stopped` on
each character's save once her process is confirmed down -- when, why, and
whether it was a deliberate stop or the account running out of money --
and `downtime.on_boot` is the read at the other end, one of the `[boot]`
lines and never in a replay: it clears the marker, works out the stretch
from the marker to now, closes the open row in kv `stops` (the last 50,
with how long she was away and whether it was written as a gap), and past
`downtime.gap_after_minutes` calls `App.temporal_gap` with the reason as
the event's second sentence. Under that many minutes she simply comes
back, and the log says so. No marker is the ordinary case -- a crash, a
kill by hand, a machine that lost power -- and says nothing. A marker
stamped in the future or before anything in the save is clamped, and the
boot line says it was not trusted.

**The account running out of money** is the same record reached from the
provider. `downtime.no_credit` is called from both out-of-balance branches
of the client: a status code of 402, or one of a short list of phrases
that say in words that money is what is missing (a bare `402` in the text
is not enough -- it turns up in a token count). It writes this character's
own marker at once, then launches `downtime.shutdown_command` detached to
stop the whole machine, so every other character's save gets the same
reason by the ordinary route. Once per process. It refuses unless
`downtime.enabled` and `downtime.shutdown_on_no_credit` are on, the clock
is live and the machine is Windows, and it refuses outright with
`SCAIL_NO_SHUTDOWN` in the environment: a sim, a replay, a dry run and
smoke can never stop his machine. The client's own log line and its
`return None` are unchanged; the stop happens as well, never instead.

No LLM. A place graph (`data/places.json`; every node carries a `kind` for
the scenery picker, and the three girls have their own homes on her line --
`aya_home` Sakuradai, `rena_home` Ekoda, `hinako_home` Shiinamachi -- which
were right in `cast.json` and absent here, so "at Aya's" resolved to nothing
and left her body where it was), journeys that run on the
clock from where she actually is (the train feed on a train leg, the
weather on a walk leg, the rush, what she wears and carries, running when
late), one seeded roll per leg for the things that happen on the way, and
a `fatigue` gauge that accumulates by what she is doing and recovers only
at rest. Readers: her read delay and composing, the impulse, the shape,
the register ("wiped is wiped"), the director (TOLD where she is; it may
not put her at school before she arrives), her situation block -- which
also carries the FACTS about getting anywhere, so a vehicle is never
invented: `travel_line` (the modes the map actually has for her, and that
there is no bus in it) and `trip_lines` (the real legs, lines and minutes
to a place her promises or her plan name, clause by clause so a
three-promise line does not resolve to the wrong one;
`situation_block.trip_lines`, `trip_min_minutes`). Pickups
through `Family.can_pickup`. kv `situation`, `journeys`. `/where`. **spec:
`docs/situation.md`.** history: archive §5.84.

`minutes_to(node)` is what the journey honestly costs from where she is --
the figure `Commitments.running_late` needs to know whether she will make a
promise (§9.7); what she BELIEVES about it is that module's business.

### 8.4 `body.py` `Body` and `health.py` `Health`: the body

`Body`: the setting of a scene (indoor / outdoor, room feels-like with
the AC once it is hot enough, `environment.ac_from_feels`,
`heat_from_feels`), exposure hours outdoors in heat or rain per date
(`note_exposure`, `note_wet` with `health.wet_exposure_factor` for
soaked), meals (`meal_kind` from the director's `ate` or the words of the
block; `note_meal` moves hunger at once; kv `last_meal_ts`), `red(gauges)`
(hungry / exhausted), the needs line for the director.

`Health`: per-day draws (`health_days`: a cold from yesterday's exposure,
the cycle, a bad night; `health.seed`), the sleep model (`_sleep`: score
from bedtime, wake, hours against need, factors; the energy target),

**What keeps her up is the chat, not the phone** (`_chat_alive`). Her own rule,
in her own words: 「みんな起きてるのに私だけ寝るなんて無理!」 -- she is not held by a
screen in the abstract, she is held by the group still being ALIVE, because
being the one who drops out first is unthinkable. Other people's group turns
between `chat_alive_after_hm` and `chat_alive_until_min` feed `delay`; her own
are excluded, because what holds her is that THEY are still talking. One term
buys both behaviours, since the early-bed block derives `resist` from `delay`:
a live chat pushes her bedtime later AND makes her refuse to turn in early for
a morning she promised, which is exactly the trade the source describes. An
exchange keeps the date it STARTED on, so one opening at 23:20 and running to
00:40 carries its later turns under yesterday -- both sides of midnight count,
and an exchange dated today at 23:30 belongs to the NEXT night and does not.
What the planner puts in that stretch is §9.1.

`effects()` -> the per-hour targets the world terms pull toward (composes
two conditions on one gauge by taking the worse), `tags()` for her mood
tags, `schedule_note` for the 05:00 plan (a sick day changes it). Owner
of `unwell`; never touches mood. `/health`. history: archive §5.18, §5.19, §5.89.

### 8.5-8.7 `family.py`, `money.py`, `events.py`: the household facts her day is planned against

Three constraints the schedule, the director and the cast prompts all read:
who is in the house, what she can afford, what she has already agreed to.

**8.5 `family.py` `Family`: where her parents are, and the car.**

Drawn from `characters/tomoe/household.json` with seeded per-day variation, no LLM:
dad's commute and overtime, the Wednesday no-overtime day, the Friday
nomikai, the Saturday golf day, the Hakata trip; mom's Life shifts and
the Sunday call to Kashii; the car in the monthly lot. `where(who, ts)`,
`car_at_home`, `can_pickup(ts, from_node)` (the honest answer: no car,
nobody home, dad drunk, past his cut-off, a coin he can lose), `trip(date)`
(a family day out about one Sunday in five), `brief(date)` for the
schedule writer, the beat writer and the director. The house as an economy
and the one thing she has not been told are prompt text the PROGRAM writes
(`tomoe/briefs.py`: `household_brief`, `household_secret`, and
`geography_brief` for the real addresses and her line's stops); the
director asks its program for them by name (`Director._brief`), so a
character with no world is handed nothing rather than somebody else's
household. Both are world-facing only: the persona may not tell her. kv
`family_days`. `/family`. history: archive §5.72, §5.85.

**Whoever this household has, and no member written into the code.** The
module asked the file for `dad` and `mom` by those keys and printed a label to
match; the brief looked up `dad`, `mom` and one brother by name. So a girl
whose file names her mother, her brother, her sister, her grandmother and the
ABSENCE of a father was handed `dad: ,  --` as the first line of her
household, no brother and no sister, in every call that builds her world.
`household_brief` walks whatever members the file has, in the file's order,
labelled by the relation each member states (`relation`), takes the work
block, the grandmother block or the plain note as the member's shape has it,
and prints a member with no name as the file's own words about the absence.
`Family.has(who)` is a member with a name, and a drawn day is fingerprinted
with what the module read out of the household, so a day drawn under a
different household is re-drawn: the draw is seeded by the date, so an
unchanged household hands back exactly the same day, and a save copied from
another character no longer carries her family into a day. Without that, the
promoted character's planner was told "dad is home all day (his day off)" and
"the car is at home in the monthly lot" out of a cached row, hours after her
own household file was written.

**And the day's spine names her places, not the first character's**
(`tomoe/schedule.py:skeleton`, `_day_words`). The walk to the station, the
after-school block, the Saturday and who is at breakfast and at dinner were
string literals, so every embodied character in this program walked to Nerima
station on the Seibu Ikebukuro line and ate with mom and Kaito. They are a
`day_words` block in her own map file now, with a default that names nobody's
station and nobody's family, so a character with no map gets a day with the
right shape and no places in it. The map's own `areas` list says which parts
of the city it prints and what to call each of them; two ward names used to be
in the reader.

**8.6 `money.py` `Money`: her allowance.**

Balance, the allowance day (`ensure_allowance` hands it over on the day or
the first day she is around after), the director's `spent` clamped to
the balance, reservations for commitments (`reserve` / `release`), a
money log (`money.log_keep`). "Just bought a cola" that the log never saw
is an embellishment: `spent_today` is the record the cast prompts get.

**One purchase, once.** The director runs every `tick_minutes` and is not
shown what the last scene bought, so it re-narrates it, and the same
purchase goes into the log twice in twenty minutes with her balance paying
twice. An identical `on` and `yen` inside
`money.duplicate_minutes` (45) is refused, and `Money.line` now tells the
director what she has already bought today -- which also makes the third
grape ice of the week visible as the tic it is. kv `money`. `/money`.
history: archive §5.22.

**8.7 `events.py` `Events`: what she has said yes to.**

Before the schedule is built, one call (`events` role) decides her stance
on the upcoming calendar events (going / dragged / skipping), kept in kv
`event_stances`; the schedule must honour a yes, the director may deviate
the way she would; the stress load reads what she is committed to. A stance
that is really one of her own promises takes its day from the promise and
not from the sentence (`_when_from_the_promise`, matched against the open
commitments): the model reads the prose, and prose that says "tomorrow"
still says it tomorrow.
`/events`. history: archive §5.69, §5.70.

### 8.8 `records.py` `Records`: threads, cast sheets, places, arcs

Threads (table `threads`): the director's open / resolved lists reconciled
by head (`_head`, `_sim`; the tail is rewritten every tick), deduped,
dormant after `threads.dormant_after_days`; `pressing_thread` is the
thing she has been not-saying to him once it has sat long enough.
`cast_sheet` renders a person for a prompt (with `influence`, the clear
pressure they put on her). Places (kv `places`, `places.in_prompt`) and
arcs (kv `arcs`, `showrunner.max_arcs`). The household, the map and the
geography left here for the program's own brief module (§8.5). `/threads`,
`/places`, `/arcs`. history: archive §5.10, §5.39, §5.55.

### 8.9 `rhythm.py` `Rhythm`: when he is around, learned and told

From the record alone: `profile()` per hour of his day (how much of him is
in it, his median latency, faded by age), `learned_now(ts)`; from what he
has said (`hear`, role `said_when`, kv `rhythm_said`): `expectation(ts)`
-1..+1, faded. `usual_now` combines them. `presence()` (is he at the
phone right now, from his last latency and freshness) replaces the old
`tempo`; `in_exchange()` with hysteresis (kv `in_exchange`);
`noticing_seconds(access)`, `reply_seconds()`, `delay_cap()` (being tense
does not slow her when he is right there); `silence_factor(ts)` (an hour
of silence at 03:00 his time is not an hour of being left; read by
`State.felt_hours` and the loneliness climb); `notices()` for her prompt.
`/rhythm`. history: archive §5.63.

### 8.10 `impulse.py`, `intent.py`, `shape.py`: does she text, what
kind, what shape

`Impulse.score(state, scene, silent_hours)` is a pure function of her
gauges, the scene, the silence, his tension, the unanswered streak
(counted in messages, not bubbles), the spiral bonus, the sentiment bonus
and **his own hours** (`Rhythm.learned_now`, learned from the record: 0.29
at 06:00, 1.00 at 10:00, 0.01 at 04:30). `impulse.presence_floor` is the
hour he is simply never there and she does not text into it;
`presence_weight` makes a quiet hour a weaker pull than a busy one rather
than the same one. `check` gates it (`impulse.*`: caps, `burst_gap_minutes`, the phone
must be free); `App.maybe_impulse(scene, digest, force_hint, media)`
runs it (a discharge or a photo forces it with the hint as the whole
reason). kv `impulse_last_ts`.

`initiative.py` `Initiative` is the gate BEFORE the score: whether she may
reach out first at all, which is a different question from whether she wants
to. `Impulse.check` asks it, and so does the afterthought, so there is one
owner and no guard per caller. Three rules. **His coming back** is a reason
she might write and never a certainty: the program that can see whether he is
at his machine calls `observe_away(seconds, state)` every pass
(`resident/app.py`), and the transition from away to here rolls once --
`return_p_base` + `return_p_per_hour` per hour gone (to `return_p_hours_cap`)
+ `return_p_unsaid` x how far `unsaid` is over its rest, capped
`return_p_max`. Taken, she writes somewhere in `return_delay_minutes`; not
taken, nothing self-started for `return_hold_minutes`. Both are logged with
the odds (`[impulse] his return: p=0.54 (gone 6h, unsaid 58) -> in 13 min`).
A character nothing tells has no return rule at all. **Being ignored** raises
the bar with each unanswered message: `backoff_minutes` by streak, x
`backoff_read_factor` when he has OPENED it and said nothing and x
`backoff_unseen_factor` when he has not (`Receipts`, through
`Impulse.read_state`), with `max_unanswered_per_day` under it as a backstop.
**His small hours** (`quiet_start_his`-`quiet_end_his`, in his clock) are
quiet. Through it anyway: a gauge at its end, and the two stances that enter
without waiting (`sim/stances.py` `URGENT`), both logged as
`[impulse] override: ...` with what the gate had been holding her for.
Everything is in the save (`initiative_away_since`, `initiative_return`,
`initiative_hold_until`, `initiative_unanswered_counts`); the backoff itself
is read off the record of what she actually sent. `/impulse` prints the gate
under the score; `tools/initiative_test.py` proves it on a copy.

`Intent.decide(scene, silent_hours, share_hint)` (role `intent`) names
the kind of opener -- share / check-in / confront / make_up / question
(`wonder`) / the X account's own doing (`_account_line`) -- with the
feeling that is deciding it (`_carrying`) and per-kind daily caps (kv
`intent_counts`). `Intent.last_question` carries an asked question to the
send. **It returns the SUBJECT of the urge in two to five words, never a
sentence and never anything she could send**, and `reason_line` renders it to
her as a subject: it is a judge, and after its sheet was taken away it was
still writing finished first-person messages that reached his chat.

**The role is told what part of the day it is on each clock and whether he is
at his machine this minute.** `WorldClock.both_daypart()` puts the words on
both readings and names the gap between them, and `Intent._his_machine_line`
asks the phone for the monitor's own reading (`Phone.his_side_now`: at it and
how long in the window, away and how long since, or nothing when no monitor is
running). The receipt above it answers a different question -- has he opened
what she sent -- and `unseen` is true both of a man asleep and of a man three
feet from his keyboard, so with two bare clock readings and nothing else the
role wrote her "are you still awake?" to send at his Saturday mid-morning.
`prompts/intent.txt` names the two lines and rules the question out; a
`check_on` is asking after him, not asking whether he is up.

`Shape.draw(unread, intent_kind, scene)` draws the message shape (bubble
count, length, a question or not, `shape.kinds`) from her state, the
situation's `shape_bias` and the register, before the persona writes; the
persona fills it, and the drawn line is the LAST instruction in her prompt
so the draft is the right size in one pass (no redraft, no post-hoc trim).

**`shape.tell_length` false and she is told none of it** -- no length, no
bubbles, and the reason clause on the feelings rule ("what you feel shows in
how short you are... what you ask") drops with them, because it is a length
instruction wearing a style rule's clothes. The classes and the weights were
measured on the first character's English, and on the second, who they were
never fitted to, "curt" and "short" both saying ONE line came to four messages
in ten: 39 of 39 a single bubble, median 28 characters, 36% ending on a
question back at him. Off for her, on for the first character, and what she
writes is what goes.

It still says **what his message obliges her to take up first**
(`shape.engage_line`, read from his own words because it is a "when"). Three
cases, in the order they beat each other: he has told her what she is ("why do
you sound like a slave to them lmao?") and she does not take that lying down or
agree with it to be nice; he asked something, and her FIRST bubble answers the
question he actually asked; he put an opinion about the world in front of her
and left it there, and she takes THAT up rather than her own day. The first
beats the partial licence outright, the other two ride with it. It exists
because she once answered his remark that a Pixar exhibit sounded interesting
with three clauses about her own standing, none of them touching what he
raised. history: archive §5.4, §5.32, §5.74.

### 8.10a `pick.py` `PhonePick`: what she does with the phone, decided by her

The impulse above can only answer one question -- does she write to him now --
so a moment that is wrong for him is a moment where nothing happens, and a
promise to somebody who is not him has no term in it at all. This asks the
other question at every moment code can offer her one, and **what comes back
is what happens**. The impulse function, the reply delay and the group-chat
roll still run, as the backup for a moment she was not asked at or did not
answer. The replay that earned it is `docs/tool-calling.md` §14 (forty-six
real moments, $0.041: defensible at the phone, a like-everything machine after
a scroll, so the scroll pick is still not wired), §15 is the shadow run in
between, and the live wiring is **§17**. `pick.shadow` true is that shadow
mode, unchanged and still available.

**When.** Four moments, `pick.moments`: the start of a stretch her plan gives
her a free phone (`block`), a change of what she is doing inside one (`scene`),
something landing from her own people (`beat`), and him writing (`inbound`).
The first two are asked from `App.maybe_impulse` right after `Impulse.check`
and its log line -- after, because the impulse's answer is part of what the
pick is recorded against and `check` rolls a die; `beat` from the program's
`loop_pass` after the beats are delivered; `inbound` from `App.maybe_reply`
before the delay plan is made. A discharge reaches none of them.

**A character who reads a world she does not keep is offered only her own circle** by name in the `message_friend` argument, with one line saying the rest of them are talked to in the group chat: she picked one of the owner's people and was refused by the partition rule, which is a fact about the file layout and not about the girl, and a chooser offered a thing it is never allowed to do learns nothing. **What she has already been to each of them with today** rides in the same block, and so does the sentence naming anybody off the list because she went to her and had nothing to say (`sim/said_today.py`, §9.8c).

**The gates are code's and are all in `PhonePick.due`**: `pick.enabled`, a live
run (never a sim, never a replay), `App.phone_access() == "free"` so there is
no call at all when the phone is not in her hand, the day's cap (kv
`pick_counts`, `pick.max_per_day`), no two looks inside `pick.min_gap_minutes`
(kv `pick_last_ts`, and the figure is on every row), and one look per block and
per scene (kv `pick_block`, kv `pick_scene`) so a restart does not ask the same
moment twice.

**What she is offered follows from what kind of thing she is**
(`PhonePick.offered`), not from a second switch: `nothing(until)` for
everybody, `text_him(intent)` with a chat with him, `message_friend(name,
intent)` in a world, `open_group_chat` in a world she OWNS (the group room
belongs to whoever keeps the world), `look_at_his_machine` unless her sheet
says `sees_him: none`, `open_feed` with an account; and on his message the
tools are `reply_now`, `reply_later(when)` and `leave_it` instead, because the
question is a different one. Six and three for the first character, three and
three for each resident, two and none for the reader of the shared world. Every
description says what the tool COSTS her, and `nothing` is never first and
moves position once a day rather than once a call, which is the cached prefix.
The sections of the moment go with the tools. The descriptions are addressed to
her and are behind the language switch (`sim/lang.py`); the two that name how
she comes to know what he does are `pick_look_tool` and `pick_look_cost` in
each program's words table.

**The prompt is her own daily half plus the tools.** The system message is
`persona.system_for("him")` byte for byte, built under `_peek` so nothing is
drawn, which puts the pick behind the prefix the provider has already cached
for her reply. The moment is everything that moves: what kind of moment it is,
both clocks, where she is and with whom, her gauge line, his side off the
record, the last six turns between them, what is unanswered in her rooms, and
`persona.carried_for()` -- the same `<carrying>` block both her rooms place
after the thread, so what she holds while deciding is what she holds while
speaking. The `pick` entry under `models` is flash at the persona role's
thinking and effort for EVERY character, including the two on a voice model,
because this call decides something and writes none of her words;
`"prompt": ""` says it has no file of its own by design. `Config.ROLE_STANCE`
has it as `voice`.

**The seams.** The runtime carries out what is the mind's and the
relationship's -- `App.write_him_first` (the path the impulse's yes runs down,
with her `intent` as the hint), `App.look_at_phone`, `App._plan_from_pick`
(the reply plan the delivery path already runs on) -- and hands the rest to the
program's `pick_act` hook, which is `Exchange.self_open(chosen=True)`,
`Exchange.open_with` and `Social.start_look` for the character with a world and
an account, and does not exist for a resident. Every hard gate on those stays:
the exchange's own reasons a room cannot open, the account's hours and caps,
the cost cap on a look. What is skipped is code's guess at whether she WANTS
it -- the group chat's score and roll, and the boredom probability behind a
scroll. **A choice her world cannot honour is recorded with the reason and is
never rewritten into a different action.**

**The wire.** Native tool calling where the host takes tools, and the same
question as JSON in her text where it does not -- decided from the receipt of
the last pick (kv `pick_host`, `api.hosts_without_tools`), never from a guess
about the pin. The text path goes through `LLM.call_json`, so a malformed
answer is asked again `api.json_retries` times and is never stored raw.

**The record.** One row in kv `picks` (last 200) written the moment the answer
exists -- the character, both clocks, the trigger, phone access, where she was,
the moment verbatim, every call with its validated arguments, the impulse's
answer with its score, the mode, the transport, the gap in force, the cost, the
tokens, the model and the host. `acted`, `acted_why`, `fallback` and
`fallback_why` are filled in AFTER the seam has run, so nothing claims a
message, a room or a look before the thing itself. The block marker and the
day's count are written before the call goes out, because a stop is a kill.
`PhonePick.validate` is the whitelist: a tool nobody offered, arguments that
did not parse and a missing required argument are recorded as invalid with the
reason, are never a pick, and leave the backup to decide; an argument the
schema has not got is dropped. **An answer with no usable choice in it is asked once more** -- the same messages and one line saying to answer with one tool call and nothing else -- and both calls are counted in the moment's spend; if the second is not a pick either, the backup decides as before. **Her reasoning arriving beside the pick is kept**, as kv `pick_aside` (`{ts, text}`, one row, overwritten), and read by the NEXT moment inside three hours of her clock as one line of what she was thinking when she was last asked. Nothing else reads it: it is what she was thinking and not something she said, so it goes nowhere near the diary or the private-thought role. It used to be logged as dropped and dropped, and in one nine-hour window five of twenty-two moments came back that way, one of them better interior writing than several roles that cost more. Nothing enters her thread. `PhonePick.holds` is the one
place the backup is refused: while the only reason she has not been asked again
is that this is the same moment or too soon after the last one, her own answer
stands. `/pick [date]` prints a day -- moments by kind, what she picked, how
many were acted on, where the backup ran, how often she and the impulse differ
about writing to him, and the spend; the ops payload carries the same counts;
every boot logs live or shadow with the moments, the caps and the tools. About
$0.0015 a pick for the first character and $0.0002 for the reader, four cents
a day at the cap. Proved by `tools/pick_live_test.py`, in smoke. **All four
characters run it live** (`pick.enabled`), with the same caps: the two
residents were on the impulse function alone, which for the third character
answered no permanently -- her tension sits above `impulse.withdraw_silent_from`
and that gate is shut and stays shut.

### 8.11 `diet.py` `MediaDiet`: what she is into

0-3 one-liners a day from the compile (`things_recent`), the accounts her
taste keeps liking (`liked_accounts`, from kv `x_taste`), a brief for her
system prompt and one line for the director. kv `media_diet`. history: archive §5.21.

### 8.12 `world/shared.py` `SharedWorld`: the world as a file two processes read

Everything a character knows about the world around her is in her own save, so
a second process running one of the people beside her as a character of her own
would plan a day the first process never had. The world therefore gets a file
of its own: one sqlite file per world under
`<world.shared_dir>/<world_shared.id>/world.db`, with **one writer** -- the
character whose config says `world_shared.owner` -- and any number of readers,
who open it through a `mode=ro` URI and never take a copy.

Eight tables, each row stamped in machine local time and carrying the writing
character's id: who the people are and what they are called (`roster`, never a
sheet), where each of them is between two times and how reachable
(`whereabouts`), what the day fixed (`settled`), every turn of the group chat
and of every two-person exchange (`rooms`), what each of them privately holds
about another (`graph`), the people around the people (`orbit`), what is going
round (`gossip`) and what the record says happened (`events`).

**One writer for everything the owner owns, and a partition for everybody
else** (docs/shared-world.md §2). A character who only lives in the
world writes the rows that are about HERSELF -- the windows her own day planner
puts her in (`CastEngine.own_day_to_world`, as her day is settled and again
when it changes), the membership row that says she is in a room, and the lines
her own plan settled -- each under her own id and a source naming her own
planner, and nothing else: a row about another person or in any of the owner's
six tables is refused with the fault logged (`_may_write`). Conflicts are
impossible by key, because the person and the source are already in the natural
key. She does not stamp who keeps the world; she records herself under `meta`'s
`writers`. And the owner's planner PREFERS a person's own rows for the windows
they cover -- where everybody is today, how reachable somebody's phone is, who
is free after school, and the absences in the day's one truth -- with its own
draw of her week as the fallback for a window she wrote nothing for
(`_prefer_own`, `CastEngine.their_own_where`). `world_shared.reader_writes_own_rows`
switches her writes off; the reading side has no switch.

It is a copy and not the truth: every fact still has one owner in the owner's
own save, nothing in the owner's process reads the file to decide anything, and
each write sits beside the write that already records the thing -- the plan
(`CastEngine.day_to_world`), the day's one truth as it accepts a line
(`Ledger._settled_to_world`), the exchange inside the stamping of a turn
(`Exchange._turn_to_world`) and the compile (`compile_to_world()`). Every write
is one row the moment the thing exists and is guarded inside the store, so a
world write can never take a tick down. Each table has a natural key, so a
re-planned day or a settled line read on every prompt build leaves one row.

`world_shared` is `in_world` in `Config.REQUIRES` and `world.shared_dir` is
`in_world` in `Config.WORLD_KEYS`, so a character with no world has no path to
anybody else's world rather than merely never being shown it. The store is a
declared wire, built by the program. `python world/shared.py --id <world id>`
prints the counts and the last row of each table; `tools/world_test.py` drives
a plan, a settled line and a turn through the live paths on a copy of the save
and reads them back from a second `Config`, then drives the partition: a
character who does not keep the world writes her own day, is refused a row
about anybody else and a row in any other table, and the owner's read prefers
hers for a window -- with the owner's own rows proved unchanged against a copy
of the live world file. What a promoted cast member still needs from the world
is §7 of `docs/shared-world.md`.

**A character who is in a world she does not own reads it and runs none of the
machinery that writes it** (`docs/shared-world.md` §8, from the third
character's first forty-five minutes, which built a second world on the same
roster inside her own save). `Config.REQUIRES` carries a fifth property,
`world_owner`, and the eight sections that write the world -- the people's own
weeks and the pressures behind them, the pool of what is going round, the
day's record of what happened, the people around the people, the strangers,
measuring herself against the room, and who privately holds what about whom --
are assigned to it, so they are off for a reader and, as before, for a
character with no world at all. Three more
are gated in the program because their sections stay on for her: the cast
planner's day, a beat of that plan coming due (`CastEngine.due`, the other end
of the same rule -- a plan already in the save keeps arriving on her clock),
and the exchange's own starting of rooms. And one is gated the other way
round: what her ward has announced is the world's rather than anybody's
judgement of it, so the ward events fetch has one writer and a reader reads
the file the owner wrote, while the national news feed is per character because
its whole selection is hers. What stays on reads
the world file: the settled lines and the absences in the day's one truth,
everybody's whereabouts and reachability behind the cast engine, and the pool
and the orbit in the half of her prompt that moves during a day. The social
graph is the one of the eight whose object is still built for a reader,
because every reader of the edges takes them through it: it reads the file's
rows rather than her save, seeds nothing and runs no update, and it is keyed
on what the record calls the running character (`sim/roster.handle`, resolved
from the cast row that carries her hub id) rather than on a name written into
the module.
`world_shared.read_rows` bounds what a reader puts in front of a model.
A save written before the rule went on is emptied of its second world once, at
the reader's next boot: eight keys and the record rows of the day's beats moved
verbatim to `data/retired/<stamp>_second_world/<save>.json` and deleted, kv
`second_world_retired` marking it done (`tomoe/app.py
retire_second_world_once`, `tools/second_world_retire.py` for a stopped save).
`tools/world_reader_test.py` is in smoke; `tools/existence_matrix.py` builds
the two world kinds as separate rows.
