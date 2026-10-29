
---

## 9. The people around her (the first character's own: `tomoe/`, cast, exchanges, the graph; the roster, the promises and the voice check are shared)

The friends are the canon three -- Rena-chan (香芝玲奈 Kashiba Rena, the
center), Hinako (米山日南子 Yoneyama Hinako, glasses and a braid, the one
who notices), Aya (前田亜矢 Maeda Aya, short black hair, the quiet one) --
and the family (mom Yumi, dad Kenji, Kaito, 11). Sheets, kanji, readings,
`aliases`, a `week` for every one of them (the parents' shifts and hours
included, so the plans layer can place them) and what each calls the others
live in `data/cast.json`; a rename
touches that file too, or `merge_sheets` re-seeds the old name as a fresh
sheet. Avatars in the app are files in `data/talkapp/avatars/`, named by roster
handle (`Rena-chan.jpg`, `Yumi.jpg`); the hub resolves whatever name the record
asks with through the roster (`GET /avatar/香芝玲奈` serves `Rena-chan.jpg`), so
the Japanese record names get their pictures and a file dropped in under a
Japanese name works too. **古賀健二 has no file** and draws the letter circle.

**Three names each, and they are not interchangeable** (`sim/roster.py`): the
**roster key** (`Rena-chan`, `mom`) that the sheets and prompt files are named
after, the **role_id** (`ringleader`, `mother`) that the machinery thinks in
and the only one that survives a recast, and the **record name** (香芝玲奈) that
the stored record uses, because the record is Japanese and a romaji speaker
label is the same English leak the glosses were. `role_of` / `key_of` /
`record_name` / `same` / `is_self` resolve any form -- key, role_id, Japanese
name, reading, a nickname harvested from everyone's `calls`, an explicit
`aliases` entry -- by **exact match against a built table, never a substring**;
re-read when the file changes, through `atomic.read_json`, which tries a
failed read twice more before it falls back to the table it already has: the
file is replaced by a rename and the window a read can fail in is over in
microseconds. A file that stays unreadable is said ONCE and then once a
minute with the count, and the recovery line names how long it lasted. A
patch script rewriting the roster in place once produced 233 identical parse
failures on one character and 131 on another in 31 seconds. Before it, six modules matched names by
lowercasing and testing `in`, so `Rena` and `Rena-chan` were two girls in one
conversation and every rule keyed to a label skipped the other one. Each
role_id resolves to itself, so a store keyed by roster name and one keyed by
role read the same. The stored speech record was relabelled once to match,
by a migration tool since retired.

**Whether a person is family is a fact on the row** (`roster.is_family`, and
`is_own` beside it for whose). Two questions read it -- who is in the group
chat (`sim/rooms.py:members_for`) and who could have been in the room where
something was said (`roster.witnessed`) -- and both used a global set of five
role ids. Two households in one world cannot both be `mother` and `sibling`,
so a reader's own mother sits under a role id of her own and that set said she
was not family. A row may carry `family: true|false`; without it the five ids
are the answer, so the character who keeps her world is unchanged.

**Who may hold a relationship meter is also the roster's answer**
(`roster.meter_rows`, read by `sim/state.py:_seed_people` and by the repair in
`tools/promoted_save_retire.py`, so a save seeded today and a save repaired
today hold the same rows). It was the cast file's `people` dict, read raw and
taken whole, which for a character promoted out of somebody else's cast meant
a meter on herself at closeness 45, meters on the world owner's mother, father
and brother, none on her own mother and brother -- they are in a second file --
and none at all on the girl whose world she reads, who is that file's keeper
rather than one of its people. A person the roster has and the cast files give
no numbers for is seeded from her own sheet's opening values
(`people.<key>.opens_at`), and seeded flat with a line in the log when the
sheet has none: choosing a closeness for somebody is authoring, not seeding.

### 9.1 `cast.py` `CastEngine`: the people as sources

Per date: seeded draws (mood, attention, friction), plans from each
sheet's week with a twist, the day's beats from one `cast_day` call (a
LINE, a group burst with nicknames in the words -- and sometimes a short
speaker prefix, which `cast.is_japanese` tolerates -- a
sticker, a call, something said in person, being left on read), their
lives written at the compile (`cast_life`). `due()` -> `deliver()` makes
beats events the director must reflect. `merge_sheets` carries
`data/cast.json` into `relationships`.

**Each of them gets a handful of concrete things for the day about to start**
(kv `cast_pockets`, `sim/pocket.py`, `cast.pocket_items`), written by the same
compile call that writes their day, from one extra key on an answer it already
makes plus what the stores already hold: their own day just gone, one thing
going round they have actually heard, a piece of the week assigned to them, the
beat of their own storyline, the fixture their week has them at. Each is put in
front of one call and then spent, and `/lives` names one nobody ever brought
up. Its absence is most of why a group chat told it is mostly made of concrete
things settled the plan again instead. **And the carry has to move**: after
`carry_about_her_max_streak` days of one person's carried thought being about
her, the prompt says today's is about their own life and one that is still
about her is dropped rather than rewritten -- all six of them were about her in
the record that prompted this and four were the identical sentence three days
running. **spec:
`docs/room-quality.md`.**

**Which room a person reaches her in is `rhythm.channel`, and it is prose.**
No room table, no per-person flag, no tie strength: each person's channel
line goes to the planner beside her share of the beats and the planner picks
every beat's `kind`, so a one-to-one with somebody exists on the days it
writes them a `line` beat. The confidante's line says LINE and she has one
most days; the rival's says group chat mostly and she can go a week without
one, in the group and the corridor instead. That is the sheet working. **But
`rhythm` is seeded once and never refreshed** -- `merge_sheets` keeps
`role_id` / `influence` / `ja` / `reading` / `calls` / `week` / `aliases`
current and copies the rest only when the key is missing -- so changing a
channel on a live character means the file and the `relationships` row
together.

**The chat's own silence is a number now, and one thing acts on it.**
The beats are placed once, when the plan is written, and an exchange
continues on a flat per-round probability, so a room dead for five hours was
in the same state as one that spoke a minute ago; the only thing pushing
against a silence was a sentence in the planner's prompt asking for none, and
the record's longest daytime gaps ran past five hours against a median of
three minutes. `group_silent_minutes()` is how long the group has held
nothing, read off the record and the live exchange. `_quiet_pull`, at the top
of `due()`, moves the earliest undelivered group beat of the day forward to
now once that passes `cast.quiet_after_minutes`, at most
`quiet_pull_max_per_day` times, never over a live conversation and never into
the dead part of the night -- the same argument `_fill_late` moves a beat on:
the intent is real and only the timing is impossible. kv `cast_quiet_pulls`.

**The late stretch is drawn, asked for, and repaired.** `_late_window` draws
tonight's last light per night (seeded, off the hour and the half hour, 21:20
to 02:20) and the planner is told it. A draw before `late_from_hm` is a night
the chat simply dies early and **nothing late is required** -- a mandatory late
block every night is as artificial as the 21:00 ceiling it replaced -- but
never before `night_floor_hm` (22:20). A negative draw says "no late stretch";
it does not say the group is over at half nine, which is what a -100 draw
plus tomorrow's pull comes to without the floor. And it is not a blind
draw: `_group_morning` reads the earliest thing anybody in the
group has to be at tomorrow (their `week` fixtures for that weekday, the school
start on a school day, her own promises) and pulls the end in by
`late_morning_pull` of every minute earlier than `late_morning_ref_hm`, so they
turn in together before a school day and let it run before a Sunday. The week
is read from `cast.json` and not from `relationships`, which never carries it; `_fill_late` inserts low-salience
`group` beats if the plan came back without them, and tops up the share of the
day that is about NOTHING (`idle_share`; beats carry `"idle": true`) if it came
back short. Both repairs log loudly, because if they fire every day the planner
is what needs fixing rather than the repair. This exists because the sleep model
reads that stretch (§8.4) and had nothing to read: every group turn in the
record sat at 12:00, 20:00 or 21:00, nothing after 21:37 in eight days, and
every beat was a time, a place or an obligation. Her schedule was never the
constraint -- she has `phone=free` to 01:30 -- the planner simply never used the
window. A prompt asking a model for purposeless messages loses to an input full
of plans, so code decides WHEN one is needed and the person still writes her own
words from it.

**Her promises are facts the plan carries, and the plan gives a promise
its hour.** The planner is handed what she has promised BY ID with the date
written out (`Commitments.planner_lines`: the day being planned and the day
after, `time not fixed` when none was said); a beat about one keeps its
date and time, a promise the day cannot keep becomes a beat about it
falling through and is never moved, and a promise with no time takes one
from the plan -- the beat names `promise` and `at`, and
`Commitments.pin_time` makes that the promise's hour for the schedule, the
director, every speaker and the settle. **Every relative day is dated**
(`_absolute_days`): `tomorrow (<date>)`, `明日の夜(<date>)` in
`settled` and in `about`, because those lines are read again when the next
day is planned and the bare word then means a different day; the planner
and each beat's writer are told which day they are writing and what 明日
means inside it. **What yesterday settled is carried "unless a beat today
changes it", so the planner is also given what has stopped being owed**
(`Commitments.closed_brief`, §9.7): nothing else could ever tell it a
promise was finished, so a line saying one was still due outlived the
promise itself and every friend's turn was written against a debt that no
longer existed. **A plan to go to something public names the calendar entry
it means** (`dates_ahead`, `event_of`, `_settled_from`; docs/cast-exchange.md):
the planner is shown what is on with the day or the span of each, every beat
and settled line about a public event carries the entry's date and title in
an `event` field, and code refuses the beat or the line when the calendar has
nothing of that name on that date. What is kept rides in the line as
`[calendar: <date> <title>]`, so the next day's planner, both sides of every
exchange and the ledger all see the same binding, and the carry expires on
the entry's day. It is the entry and not the word "festival" that decides,
because a festival she had already been to came back six days running and the
last time it came back with the word taken out, as "meet dad at the station
tomorrow". kv `cast_days`, `cast_plans`,
`cast_beats`, `cast_life`. `/cast`, `/beats`, `/lives`. **A picture between friends is its description and nothing else** (his call):
the bracket is the whole of it, no file is attached and none is needed, and the
pool of real photographs is kept for what she sends HIM, which he opens.
**The group carries on without her** whenever her turn
comes due and she is not in it -- her phone away counts, not only her
declining -- and a beat of another kind waits rather than ending a live
group chat. **What today has already been over** (`Exchange.covered_today`)
reaches every friend's turn and the beat writer. **spec:
`docs/cast-exchange.md` §2-3.** history: archive §5.16, §5.86; §9.1.

### 9.2 `exchange.py` `Exchange`: her side of her social life

**Each of them is an agent with a sheet of their own.**
`prompts/cast/<key>.md` is that person's document, written the way her bible is
and IN JAPANESE because everything they say is: who they are, what they want,
what they do not know, and 話し方 -- how they sound, naming the forms and the
first person. It is the system prompt for their call (`cast.person_sheet`, read
fresh; an honorific comes off the key rather than costing somebody their sheet
in silence), and the role prompt under it is only the contract. One role prompt
with a `role` field pasted in had given six people one voice.

**Under the sheet, a set of mechanisms** (`tomoe/cast_mechanisms.py`,
`data/cast_mechanisms/<key>.json`): per person, what makes them do a thing,
what stops them, what doing it gets them, in the same shape the extracted
character uses and marked `authored` so it can never be quoted as a
measurement. A sheet gives a model an adjective to perform; a mechanism gives
it something to run, and a suppressor in front of the person is a real answer
too. The sheet stays the system prompt and the block goes in the user message
of the three calls where somebody speaks or is planned for -- their own turn,
their own beat, and the day plan, which gets everybody's mechanisms and
nobody's secrets, because one call writing for six people holding a secret is
six people holding it. Each mechanism names the roles that may see it, a
mechanism no call renders is DEAD the way a gauge nothing acts on is
(`tools/cast_mechanisms_test.py`, in smoke), and over
`cast.mechanisms_max_chars` the rarest is dropped first. The personality type
each person was written FROM is in a file of his (`cast.types_file`) that
nothing assembling a call may open; `tools/cast_type_test.py` counts its
markers in the record and is the only reader. **spec:
`docs/cast-mechanisms.md`.**

A beat that wants an answer becomes a paced exchange: the opener verbatim
from the planner, one side's turns per loop pass on the clock, his
message pushing her turn back. Her turns (`cast_reply`) carry her state
with `directed_line(who)` -- never his register -- her meters with them,
her record of the day (events, what she said to people today, money),
what she owes them, the nicknames, and `prompts/style_ja.md`, which is the
other half of her voice (`style.md` is how she writes to HIM and has no
business in a call to Aya); their turns (`cast_turn`) one call per speaker
with their own sheet, day, life and graph edges, nothing of her interior; a
group is multi-agent.

A turn is `{who, ja, hm}`: `ja` is what was said, there is no English gloss
any more, and a turn without Japanese is dropped (`cast.is_japanese`, which
ignores the Latin speaker prefix a group burst carries by design). An exchange's
`gist` is Japanese, written by the model as part of the same answer; a beat
saved unanswered keeps the planner's English line as its gist instead, which
is what `search_rows` gives recall to match his English cue words against. Two
consecutive turns saying the same thing with the words moved are collapsed
to the first (`sim/textutil.drop_repeats`, the same test the bubbles get): a
person repeats herself, she does not paraphrase herself.

**The summary is written only from turns that survived the filter.** `gist` and `about_him` are assigned after the check that a bubble came back, not before it, on both sides of the room; when nothing survived, the record keeps the summary it already had and that round is counted as a round that added nothing before the room closes. Written the other way round, two rooms in one evening stored a sentence saying what she said in them -- one of them a promise to her brother she never made -- and the round that produced literally nothing was the one round never counted as having produced nothing.

**A room that loops is caught four ways, and none of them rewrites a line.**
The whole-message test above compares one speaker with herself, and neither
loop in the record is that shape, so: a sentence-level filter over the room's
last `repeat_window_turns` turns from anybody drops a bubble more than half of
whose long sentences have already been said (`sim/textutil.echoed_by`, used by
the owner's cleaner and by a participant's writer, which had nothing); a moves
ledger keeps the one-line summary every writing call already returns, renders
it to both writers and carries it on the ask to a member who writes her own
turns (`sim/rooms.moves_block`); a round in which a bubble was dropped or a
move was played twice is stale, and each stale round multiplies
`group_continue_p` by `stale_drag` while two in a row end the room; and the
pace reads the reachability of everybody who just spoke and of whoever speaks
next, hers off the scene's phone access, rather than the opener alone.
**A stamp is outside all of it** (`is_stamp`): a bubble that is only 「[スタンプ: …]」 is never compared with anything and never counts as a dropped bubble, because two girls sending うん as a stamp twice in an evening is agreement rather than a loop -- all three deletions on one character that day were the same stamp, and one of them cost the room a round. A run of the identical bubble inside one answer is still collapsed. `group_bubble_chars` counts a bubble too long for the medium in the record and
in the log and cuts nothing. **spec: `docs/room-quality.md`**, and
`tools/room_quality.py` measures a room off any save.

**The dialect is flagged, never redrafted.** `_slip_ok` says why a Hakata slip
is the TRUE reading now -- alone with the confidante (`slip_with_roles`, by role
so it survives a recast, and never in a group, because the point of a mask is
the audience), real anger, genuinely short of sleep, or cornered by that person
-- and that, with the family case, reaches `voicecheck` as `context`, where a
rule's `skip_when` turns it off. A second mechanism here used to hold its own
copy of the patterns and spend a call rewriting a slip; it is gone (§9.10).

**A group chat is a venue, not an errand.** The one-to-one numbers are the
originals; the group has its own. `group_continue_p` (0.87) and
`group_max_rounds` (12) set the length -- E[rounds] = (1-p^R)/(1-p), so 2.18
became 6.25 -- `group_max_live_minutes` (180) lets one run for an evening,
`group_jump_in_p` (0.7) puts more than one other voice in a round, and
`max_per_day` covers every kind of exchange EXCEPT in-person, so the group
used to compete with LINE and the kitchen for the same slots -- and an
evening of five library exchanges with the confidante spent the day by
16:31 and left her mother in the kitchen as a one-line stub. The budget is
the phone's, not the room's: `wants` lets an `in_person` beat through
whatever the count says, and neither increment charges it. The cheapest lever was the prompt:
turns per call had NO code bound, so "one or two turns" was the whole of it,
and `cast_turn` / `cast_reply` now ask for one to four and say what a turn is
-- one MESSAGE, not one thought. A day went from about 48 group messages to
**134 at five group exchanges, 158 at six, 183 at seven, 204 at eight**, at
0.43 calls a message. (An earlier analytic model said 231; it did not know
about absences, and `tools/chat_project.py` drives the real code now.)

**She is not the chat** (`exchange.group_without_her`, 3). Her silence used
to close a group: `_her_turns` came back empty and the exchange finished, so
three girls stopped talking to each other the moment she did not answer. Most of a
day's group conversations came out **one message long** for that reason, and
each of those stubs also charged her `reply_miss_standing`. Now they carry on without her for up
to three passes and she can walk back into what they said; only then does it
end, as "she never came back to it". The idle beats (`idle_share`, the ones
about nothing) are what this rescues: they were the stubs.

**And the room does not need her to have been in it at all**
(`Exchange.alone_beat`, `exchange.alone_beats_per_day`). The passes above
only ever ran inside a conversation she had stepped out of, so a group beat
the day's phone budget or the late reserve refused her never reached them: it
was filed as one unanswered line by `CastEngine.save_beat` and that was the
end of the room, with the other two girls in the chat the whole time. **17 of
the 47 group conversations in a week were exactly that row.** Such a beat now
opens a conversation with her out of it from the first turn -- the side starts
as theirs, `skipped` starts at one, and the same `group_without_her` passes
bound it, with a `group_continue_p` roll in the hand-off so it thins out
instead of running its six. Her phone budget is not charged, because the
budget is what she can ANSWER; nor is her standing, because a room she was
never offered is the machine's cap and not her silence. She reads it in the
thread when her phone comes back. kv `exchange_alone_counts`.

**She can start one** (`Exchange.self_open`, `exchange.self_open_per_day` 1).
Every beat is somebody reaching HER -- the planner is refused any beat
written as her, and that rule stays -- so she opened **none** of the 47 group
conversations in a week and three girls opened all of them. This is the other
door, and it is shaped like her urge to text him (`sim/impulse.py`): flat
refusals first, each sayable in the log (a live conversation, no phone, the
day's cap, fewer than `group_without_her_min` friends awake, past the night's
last light, the room quiet for less than `self_open_quiet_minutes`, a
friend's own beat due inside `self_open_clear_minutes`), then a score on her
own gauges (`self_open_weights`: loneliness, boredom, craving, and belonging
by how far UNDER par it is) against `self_open_threshold`, then the impulse's
own soft edge. Her words come from `_her_turns` with an empty turns list and
one extra line in the ask saying the room is empty and she is picking it up
-- the same assembly, `persona.system_for("friend")` and the one thread and
the carried block after it, because a second assembly is how her friend turns
went eleven days without her interior. kv `exchange_self_open_counts`.

**One name per person, and every person is told their own first person.**
`voice_line` renders `cast.json`'s `voice`, and no sheet's `voice` named a
first person -- the 一人称 lived only in `prompts/cast/<key>.md`, twenty-five
lines into Japanese prose in the system prompt, while the line next to the
transcript said how she sounds and left the pronoun out. `first_person` is a
field on each person now and it goes in first. The other half was the name:
the OPENER of an exchange reaches `_one_speaker` as the record name and a
jumper-in used to reach it as the roster handle, so Aya's own prompt said
`SPEAKER: Aya` and `what Aya holds about Rena-chan` above a sheet saying
前田亜矢 and a transcript in which every line is 前田亜矢. The pool resolves,
the SPEAKER line resolves at the point of use, `SocialGraph.brief_for` renders
both ends of an edge through the roster, and `roster.one_name` replaces every
capitalised handle in the assembled prompt -- `mom`, `dad` and `him` are
English words before they are keys.

**Nobody repeats their own message** (`no_repeat_own_turns`, 6), and
neither does she -- by contract first (`cast_reply.txt`: her own earlier
messages are said; a standing point is advanced, answered or dropped; an
answered worry gets a reaction to the answer, and a dodge uses something
new), with the near-duplicate refusal on her own lines as the guard. The
guard exists because a guard can only catch the verbatim copy; the
reworded restatement is the prompt's to prevent. A speaker is
shown their own last turns in this conversation and told that a point still
standing is dropped, sharpened or replaced -- never restated -- and a turn
that comes back a near-duplicate of one of them is dropped in code
(`near_duplicate` against that speaker's own lines, where `drop_repeats` sees
only a consecutive run).

**A group chat is mostly not arrangements.** The same fifty-one messages were
100% logistics -- 明日 21, 10時 16, 日曜 11, フリマ 9, 手帳 8, and not one joke,
photo, complaint about the heat or piece of gossip. The group prompt now says
what a group chat is made of and that a settled plan is not settled again.
The negotiation underneath it was sound: Hinako pushed, Rena deflected for
her, Aya bridged, and 「流れたら、もう誘わないから」 got a commitment out of her.
The bones were right and the texture was not.

**Nobody is chained to the phone** (`_gap` / `_away`). Every gap used to be
`prev_len/6 + U(20,150) + n/3`, bounded about 29-198 seconds by construction,
so a three-hour chat was a two-minute metronome: mean 1.9 min, median 1.9, max
3.2 over thousands of samples. `away_p` of the time a gap is an absence
instead, and the absence has a REASON that carries its own length (`AWAY`: the
loo, a video then another one, dinner, the bath, homework, somebody in the
room, went outside, fell asleep with it on their chest), weighted so the
late-night ones are the sleepy kind. Median stays 2.2 min -- most answers are
still quick -- and p90 goes to 20-27 with a tail to about 70.

An absence is not free, and one of them ends a night rather than pausing it.
Every absence multiplies the chance the conversation keeps going by
`away_drag`, so a chat that has already stopped for somebody's dinner and
somebody's bath thins out instead of running its twelve rounds regardless (34
messages a late night -> 26, 127 minutes -> 99). And **falling asleep means
sleep**: the person is written to kv `cast_asleep` until `sleep_wake_hm` the
next morning, out of the speaker pool (`_awake_friends`), unable to open a beat
(`wants`), and when everybody who was in it has gone the exchange ends with
"they had all gone to sleep". Nobody's tiredness is modelled -- this is drawn,
not simulated, and it is the one way a person's night ends.

**A beat nobody answered is still something that was said**
(`CastEngine.save_beat`). A beat is a model call in that person's own voice and
its words lived in kv `cast_beats` -- overwritten by the next day's plan, one
day of grace in `cast_beats_prev` -- while the only durable trace was the
planner's ENGLISH line in `events`. Everything that reads her social life reads
`cast_chat`, where a beat appeared only if it happened to become an exchange.
One that `wants()` refuses (the budget spent, the group chat already running,
the sender asleep) is now written there as a one-turn row marked `unanswered`
-- unless it is a low-salience idle beat and the coin lands (`exchange.stub_stamp_p`):
then she stamps back from her own set, code only, never with the phone away,
and the row carries her half-attention instead of a one-voice stub.

**Somebody she is sitting WITH says something** (`CastEngine.presence_beat`,
called every pass from the loop). The planner writes a day in advance and
cannot know she would still be at that table two hours later: she can sit
across from Aya all morning while the day holds one four-minute conversation
with her and a LINE exchange with somebody else runs at the same table. The scene knows who she is with (`with_who`) and the cast layer
never read it. Code decides when -- somebody in the room has not spoken to her
for `cast.presence_gap_minutes` (25), under `presence_max_per_day` (5) -- and
that person writes her own words through the ordinary beat path. Never for
him, never for a name the roster does not own, never for somebody dormant.

**A table is not one person.** This read `with_who` as a single name and
returned nothing the moment it held a comma, so the only scenes that could
ever produce a presence beat were the ones where she was alone with somebody
-- which at school is never, because she is at lunch with the group. Her
whole first school day of term passed with friends named in the block and not
one word between them, and every non-family in-person conversation on record
came from a break day where the plan happened to seat her with exactly one
person. Now everybody in the room is a candidate: the one she is already in a
live exchange with is dropped (a presence beat never opens a second
conversation on top of the first), anyone inside the gap is dropped, and code
picks the most overdue, so the quiet one at the table gets her turn before
the girl she has been talking to all lunch.

**One girl, one name, in every seat.** Read from Rena's chair
(`tools/context_audit.py`) the prompt called her four things at once: 古賀朋絵 in
the transcript, とも on the sheet, `Tomoe` in the stored stance lines and the
promise list, and `Rena-chan` in the roster of who else is reading -- which also
listed Rena herself, because the exclusion compared a roster handle with a
Japanese record name. The friends' user block is normalised at render, the
group roster uses record names and excludes the speaker through the roster, the
sheet header and the promise brief use her record name, and the beat prompt is
normalised the same way.

**Her friends see her by the name the record uses.** The labels around a
speaker's call said "Tomoe" while the transcript said 古賀朋絵 and the sheet said
they call her とも: three names for one girl, in the prompt, which is the fault
the roster exists to stop. `EARLIER EXCHANGES WITH 古賀朋絵`, `attention for
古賀朋絵`, `WHAT 古賀朋絵 HAS PROMISED THIS SPEAKER`, and `calls_line` resolves the
`calls` map's roster keys to record names (`calls 古賀朋絵 とも, 米山日南子 ひな`).
`tomoe/prompts/cast_turn.txt` and `cast_day.txt` name her the same way.

**A beat that lands while the group chat is running joins it** (`absorb`).
A group beat used to go through `start`, which ends whatever she is in -- so
Rena dropping a photo into the chat at 23:50 was the thing that killed the
chat it was meant to be part of. It is appended as her turn instead, the side
flips back to Tomoe, and the conversation gets a round and one absence back,
because somebody new arriving is exactly what keeps a chat alive.
A one-to-one beat from the very person she is talking to, on the same
channel, joins the live exchange the same way -- their next line in this
conversation, never a second one -- and `presence_beat` does not fire for
the person she is with in a live exchange (two in-person exchanges with
Aya at 09:37 came from that).

**Beats landing together wait their turn** (`hold_back`, `cast.hold`). The
loop takes due beats one at a time; a beat that lands while an exchange is
live and she has not yet had her turn in it (side hers, no rounds) is put
back undelivered and comes whole on a later pass, up to
`exchange.hold_minutes` past its own time. Two events due in one pass used
to open and drop each other within the second, and the dropped one cost
her standing for a message she was never given a turn to answer; an
exchange closed before her turn was due is never charged (`_finish`).

**A chat that is past the night's last light is over** (`_past_last_light`).
`_late_window` draws when the group turns in and `_group_morning` pulls it in
by what everybody has on tomorrow, but nothing enforced it once a conversation
had STARTED: a beat at 23:50 on a night meant to end at 00:07 ran to 02:38 on
the three-hour live cap, which undid the whole point of them turning in
together before a school morning. The check reads the small hours as belonging
to the evening they came out of and runs from the last light **until the group
wakes** (`CastEngine._after_last_light`, the one owner of the rule, asked by the
planner and by delivery alike): a fixed six hours reached 08:13 after a 02:13
night and refused a 07:30 morning chat, which is nobody's overrun. Nights now
run about half an hour past their own end -- people finish the thread, they do
not stop dead on a clock -- against two hours before.

**And the plan does not schedule into it.** A beat placed past
tonight's end would open and shut in the same tick and cost her standing for
a message nothing would have let her answer, so `_fill_late`
moves such a beat back into the evening -- the intent is real, somebody wanted
to reach her tonight -- and a close that was nobody's choice (the curfew, the
others asleep, the opener dropping it before her first turn) is not charged to
her at all.

**Her prompt does not carry every line of it, and it is the thread that
cuts it.** At a couple of hundred group messages a day, two days of
exchanges whole is ~23k characters, and most of it is about nothing by
design. The exchange had a section of its own in her system prompt that
kept the newest group conversations verbatim and rendered the older ones
as the gist they already carry; that section and the function behind it
are gone, because her friends' talk reaches her through the thread
(`sim/thread.py`) and the thread applies the same cut on its own curve --
verbatim inside the verbatim span, then the conversation's card, or one
line at its own time saying how many messages, until when and what it came
to where no card covers it. A cast member's own thread carries no cards at
all: a card is written per conversation across every room, her chat with
him among them, so their past conversations reach them as those lines.

**She is not always available, and owing him an answer is not the same as
being with him.** `_busy_with_him` was true from the moment his message landed
until she replied, so a message that arrived while she was ASLEEP froze every
exchange: 456 minutes, Kaito's beat dying in her doorway and Aya's dying while
she sat across a library table from her. It now means she is actually sending,
or his message is newer than `busy_window_minutes`; deferrals are capped at
`busy_max_pushbacks`; and an `in_person` exchange is never deferred at all,
because a phone does not stop you talking to the person in the room.

**What she carries from the other room** (`tomoe/carried.py`). Her chat with him
and her chat with her friends are two rooms, and each was represented in the
other by a keyhole of raw messages: the cast calls got `recent_messages(4)` cut
to 80 characters, laid out exactly like the conversation she was actually in.
Wrong twice -- too little, and the wrong KIND of thing, because a transcript in
a prompt reads as a conversation to answer and the one thing she must never be
confused about is which conversation she is in.

`Carried.him(cue)` gives a cast call a corpus instead: where it stands with him
(who wrote last, how long ago, whether she owes him an answer), what she knows
about him with the fade already applied (`Memory.facts_for_prompt`, cued by
what is being said around her), what is still open between them, whether
something is unsaid, and only then the last `him_messages_shown` (10) messages
at `him_message_chars` (160) -- labelled a record and not a conversation
waiting on her. `Carried.circle()` was the mirror in her own prompt while she
talks to him: whether the group chat is live right now and who is waiting on
whom, what it has been about (gists), where she stands with each of them and
how many conversations she has been out of, and who is asleep on the chat. No
model call: all of it is assembled from what the record already holds. Nothing
calls it now: the system-prompt section it fed was built and blanked on every
call while the thread is on, and was deleted; putting the circle back into her
prompt through the attention gate is a prompt addition and his call.

THEIR side still sees none of his chat: a friend's turn has that person's
sheet, their day and edges, the chat as it stands and their earlier exchanges
with Tomoe, and nothing of her private mind or her DMs.

**A slow answer costs her, and missing the chat compounds** (`_reply_cost`, at
`_finish`). Past `reply_slow_minutes` a group or LINE exchange takes `standing`
off whoever opened it; never answering costs more. kv `behind` rises on a group
conversation she stayed out of, falls when she took part, caps, and **scales the
cost of the next one** -- the compounding, and why she over-attends. Read back
in her own turn prompt (`_behind_line`), so it is not a number nothing acts on.
Both are her own rules from the bible and neither had a mechanism: she could
ignore the group for a week at no cost.

The
record (kv `cast_chat`) reaches her state like his message does, the compile,
recall, the app. `/chat`. **spec: `docs/cast-exchange.md` §4.** history: archive §5.29, §5.73; Part C 2026-08-27.

### 9.10 `voicecheck.py`: is this line in the voice it should be in

`characters/tomoe/voice_rules.json`, keyed by speaker (`Tomoe`, `Kenji`), by role
(`role:diary`) or `_all`; a rule is `find` / `why` / an optional `unless` that
makes it fine (a quotation, an honorific), and a role set may `inherit` a
speaker's rules rather than restate them. `voicecheck.note` runs on every turn,
every beat, and -- through `LLM.call`, the one place every role's output passes
-- every role, including ones that do not exist yet. It writes `[voice]` to the
log and a row to kv `voice_flags`, and **changes nothing**: a line in the wrong
voice is a signal about the prompt, and correcting it quietly hides the signal
(the first Chinese-character blocklist would have mangled 写真 nine times).
Adding a person or a role is an entry in the json and no code.

A rule may also declare **`skip_when`**, naming what the caller knows that a
regex cannot see -- `family` for the kitchen, `slip` when her state says the
mask is legitimately down -- and the caller passes `context` (§9.2). That is how
a conditional rule (her Hakata is hers at home and a slip in front of Rena)
lives in the rule file instead of a second copy of the patterns. A rule SET may
in turn declare a **`context`** that is always true of it: the twelve role sets
that are her private mind (anticipation, reflect, spiral, diary, wonder and the
rest) declare `inner`, and the dialect rule skips it, because a mask is for
other people and there is nobody in her own head. The caller could not say so --
`LLM.call` has a role name and knows nothing about her. The speaker is
resolved through the roster before the rule sets are chosen, or a whole person's
rules silently never run: relabelling the record in Japanese took every flag to
zero until that was added.

An answer that had to parse as JSON reaches the check as **`machinery`**, passed
by `LLM.call_json` through `LLM.call`. Its keys and the fields the code reads
back are English by construction, so a rule about how a person writes cannot say
anything about it -- while a rule that is true of any answer at all, Hangul or a
simplified Chinese character, still runs. The three roles that answer in prose
and are still the machine talking (the app's account of him, a note of his
summarised, the week written into the record) say the same of themselves with a
`context` in the rule file. Before this the second character's "she writes
Japanese only" rule fired on all 33 calls of a morning -- every scene the
director wrote, every state delta -- and buried the one real flag, which was her
own reply.

`tools/voicelint.py` runs the real checker over the real record, read-only, so a
regex is measured before it is trusted -- it caught `たい` flagging 「聞きたい」 and a
bare `ばい` that would have eaten 「やばい」. `/voicecheck` is the report (it
was a second `/voice` branch that the voice queue's own answer had always
reached first, so it never once ran).
history: Part C 2026-08-27.

### 9.2b `npc.py` `People`: everybody who is not the cast

The cast is seven people with sheets, a graph and a place in her prompts.
Everybody else in Tokyo did not exist: she rode a packed train with
`with: "strangers"` in the schedule and nobody on it, stood in a konbini with
nobody behind the till, and spent a school day in a building holding one class
of girls none of whom were ever in the room.

**Who is plausibly there comes from the place.** `data/places.json` already
gives every node a `kind` -- konbini, station, school, library, park, shrine,
museum, shotengai, city -- and `_WHO_IS_THERE` maps each kind to the roles that
populate it, weighted: a konbini is mostly the person on the till, a platform
has a school kid from another school and somebody standing too close, a shrine
has an old woman. `home` is empty because her family IS the cast; a friend's
flat is `kind: home` and is not her home, so it gets their mother.

**Three things a person can be**, which is how it works in life: a face she
will never see again; a face she knows by sight and has no name for -- code
reuses a face already seen AT THAT PLACE with `known_face_p`, weighted by how
often she has met them, which is what gives the konbini a regular clerk instead
of a new stranger every visit; and a face with a name, only where you would
learn one (school, or `name_after` meetings). A new draw that comes back as
somebody already on the record IS that person: one row per face, matched on
either name form, or the same clerk accumulates a row a night.

**Most of them are simply there.** An encounter is rare and that is right;
what was wrong is that between encounters nobody existed. `around(scene)`
is the ambient population of wherever she is -- one or two roles from the
place's table, the face she has seen most there first -- computed in code,
deterministic within the hour, never a model call and never an event. The
director is told (`PEOPLE SIMPLY THERE`), the scene carries it (`around`)
and her own prompt reads it as background ("people about, nobody in
particular"). You do not remember the person on the till, and a stranger
who keeps turning up does not change her life: `promote_after` is 0 (never)
and `/npc` names no candidates. The value of the other people is that they
are there, not that they matter.

**Code decides when and who, the model decides what.** The gate is the place's
own `place_p`, an alone multiplier (three girls together are a wall), a gap, a
daily cap and a roll on a cadence rather than on every pass of the loop. The
slot -- known face or new, and which role -- is picked in code and handed over.
Most encounters have no words in them at all, which the prompt says plainly,
and money is not the encounter's to spend: her purse is a record kept elsewhere.

**They stay out of the cast machinery.** An NPC never enters `relationships`,
`sentiments`, the graph, `cast_chat` or the group -- no standing, no closeness,
no beat -- because the empty-person fault was a name reaching a lookup with
no row for it. One door out: an `events` row, which is what
everything else in her day comes through. The director reads the day's events,
so the scene answers a stranger; the diary reads them all; her own voice to him
reads only `salience >= 2`, so the person on the till never reaches her chat
with him and something that stayed with her does. A face she keeps meeting is a
cast candidate named by `/npc`, and nothing here writes `data/cast.json`:
promotion is his. kv `npcs`, `npc_moments`, `npc_counts`. `/npc`.

**One person in every room.** `_her_turns` builds its system prompt from
`persona.system_for("friend")` -- the same assembly as her replies to him,
byte for byte, without `style.md` -- FIRST (so the cache prefix is shared),
then its own tail: `cast_reply.txt`, `style_ja.md`, her stickers. From
08-19 to 08-30 it built from the bible alone, and half of everything she
said in a day carried none of what she had decided about herself,
remembered, wrote last night or was into; `tools/smoke.py` now fails if
the two assemblies diverge by more than `style.md`. With the nudge on
(`nudge.friends`; it is off) it fires on her turn at the `unsaid` threshold
with the bond line as the gate's pick.
**Her friend turn sits on the same thread**: the
messages are the persona core, then `thread.build(live_turns=...)` --
both rooms, one clock, the exchange in flight as its tail -- then the
call's own block, which says which room she is writing in NOW and that
the other rooms are answered there. `THE CHAT SO FAR`, `EARLIER
EXCHANGES` and the carried him-block are what the thread replaced: there
is no flag any more, and the presence of the thread object is what
decides, so those blocks are only what a call built without one falls
back to. **Her turn goes through the gate.** The block she reads with her own
people is built the way `persona._situation` is: a fixed header (time,
where, how she is, who and her meters), then tagged lines through
`attention.admit` -- `them` (bond, behind, known, thought, a promise on
the record, anything she has promised to SEND them and can put in this
message as 「[写真: …]」, each rumour an action candidate), `day` (yesterday, today,
what she said today, money, threads, the settled ledger), and `him` as
facts only (`_him_lines`: his last message and when, the gap, how he
sounded, expectations, the digest -- never her private questions about him
or the thing she is not-saying to him; those ride only in his room) so he
can come up in her rooms
-- one action stated in the slot, last before the ask; a rumour held there
is charged a showing (`Gossip.charge_shown`, `gossip.shows_max`) and steps
aside for the day when unsaid; him is the `himf` section (3 lines); the nag / show-him / share never
candidates there. `[attention] (who) ...`, kv `attention_last_friend`.
**And every other mouth.** A cast member's turn (`_one_speaker`) sits on
their own thread -- `thread.build(for_who=...)`: only the rooms that
person witnessed (the group for a friend; their own LINE, calls and
kitchen; never her chat with him), with THEM as the Assistant role and her
and everyone else as the world speaking to them, the same curve applied,
the exchange in flight as its tail, and the call's block saying which room
they are writing in NOW. In the fallback block form, `THE CHAT SO FAR`
carries each turn's own stamp and a `[N minutes with nothing said]`
marker at `exchange.chat_gap_marker_minutes`. The latest compiled day is
labelled by its age, not always "yesterday".

### 9.2c-9.2e `gossip.py`, `stickers.py`, `orbit.py`: the fixed sets around the cast channel

Three owned sets the exchange reads, and none of them is the cast: what is
going round, which stamps a person has, whose little sister that is.

**9.2c `gossip.py` `Gossip`: something to talk about that is not the four of them.**

Measured over 175 group turns, 77% carried a time, a plan or an obligation
and 13% carried anything else -- the chat was a committee because the
committee's business was the only thing in the world. `cast_arcs`,
`cast_life` and `social_graph` are all about the group or about her; this
is the rest of it. Every `gossip.every_hours` the `gossip` role writes up
to `new_per_run` things going round -- a teacher, a second-year, a shop
closing, a video -- from the faces she has actually met (`tomoe/npc.py`),
`tomoe/world/zeitgeist.py`, the calendar and what she noticed about Japan on her
own timeline (kv `x_japan`, `_timeline_seen`). Each carries a `heat` that falls
`cool_per_day` and rises `warm_on_use`, a `knows` list so a person who has
not heard a thing cannot repeat it, and `kind` (person / school / couple /
shop / seen / nothing). **A rumour about anybody the roster owns is
refused**: that is the cast, and the cast has arcs. The planner sees the
warm ones (such a beat is `idle`), a speaker sees only what that speaker
knows, her own reply sees the warm ones. **`knows` is seeded when the item is
born and grows when it is said**: a school thing, a person or a couple is known
to everybody at that school on the roster, a shop or a place to whoever lives
or passes there per `cast_plans` in either language (falling back to the school
when no week names it), a thing everybody has seen to everybody; and anybody in
the room when it is stated has heard it from then on, read where a turn lands
rather than where one is cleaned, so a turn written by somebody's own process
counts too. Before that, six of twelve were known to one person and the
speaker filter hid them: one girl could bring up 6 of the 12 on file and now
brings up 11. `/gossip` names an item nobody has heard two days after it was
born. kv `gossip`.
history: §9.1.

**9.2d `stickers.py`: a fixed set of stamps.**

The record narrated stamps -- 「（悲しそうなキツネのスタンプ）」 -- and invented
each one fresh, so nobody's stamps were ever twice the same. There are no
images and none are wanted: a stamp read as text is what he sees. What was
missing is that it be the SAME stamp. `SETS` holds five, one per role
(overridable per person with `stamps` in `data/cast.json`); `line_for` puts
only that person's own on their prompt; a stamp is written
「[スタンプ: 名前]」, the same shape as the photo marker, so every reader
carries it; `snap()` pulls a name they do not own to the nearest one they
do, or drops it, logged. The app draws it as a stamp. history: §9.1.

**9.2e `orbit.py` `Orbit`: the people who belong to somebody in the cast.**

Rena's little sister was one sentence in `cast_facts` and a different
person every time she came up. One row per person outside the cast who
belongs to somebody in it: owner (a roster key), relation, a name only if
the record ever gave one, `ja`, the facts the record has put on them,
`status` (the fever) with its date, and two standings -- how Tomoe stands
with them and how the owner does, a sentence and a slow number each.
Written once a day at the compile by the `orbit` role from the day's
exchanges and `new_cast_facts`; code matches by owner+relation or by name,
drops a row that IS cast (a name the roster owns, or a self-owned family
relation -- her family is the cast), clamps nudges to +-2 and caps. Read
by the exchange (`line_for(who)`: a speaker knows the people in their own
life), the planner and her own prompt (`brief`), and the gossip pool
(`owns`: an orbit person is off limits like the cast). kv `orbit`;
`/orbit`. history: §9.2e.

### 9.3-9.4 `social_graph.py`, `cast_arcs.py`: the cast's own ground truth

What the people hold and where their own lives are going, both written away
from her.

**9.3 `social_graph.py` `SocialGraph`: what they actually think.**

Ground truth per holder (`view`, `regard`, `irritation`; friends to
Tomoe and to each other, family only to Tomoe), rewritten at the compile
from what each person witnessed; readers: each speaker's own edges, the
lines her guesses settle against, `witnessed_heat` (a stumble costs more
in front of an irritated group), the showrunner's drift, the app's
backstage. A view is the holder's own thought in Japanese; one that comes back in
English is flagged (`[graph] FLAG`) and kept. Known gap: friend-to-friend
edges have no writer. kv `social_graph`. `/graph`. **spec: `docs/cast-exchange.md` §5.** history: archive §5.76.

**9.4 `cast_arcs.py` `CastArcs` and `Showrunner`.**

Arcs: each person's own life by role, written weekly (`run`, role
`cast_arc`; `_focus` picks who carries one: attention x volatility +
tension) and evolved (`evolve`, role `cast_evolve`); `day_nudge` raises a
person's attention on a day their arc moves; `context_for_beats` for the
planner. kv `cast_arcs`. The showrunner (role `showrunner`, weekly) sets
her arcs from the calendar, the receipts, the cast and the graph's drift,
leaning toward her own people when the week was mostly him
(`cast.him_share_warn`); kv `arcs` via `records`. Both live in
`tomoe/cast_arcs.py` and share the one weekly gate (`weekly_due`: on the
section's weekday, once a day at most, not inside `min_days_between` of
the last run, and straight away when there is nothing yet). `/castarcs`,
`/arcs`.
history: archive §5.11, §5.35.

### 9.5 `reflect.py` `Reflection`: her private mind

A private thought, in a quiet moment, about him (`run`, role `reflect`:
from the digest, the app, his notes, the receipts) or about a person in
her own life (`run_cast`, role `reflect_cast`: from the exchange record
only; `cast_subject` picks by pressure, not rota). **`after_reading(scene,
why, record)` is the third way in**: something of his she has just read, with
the record handed to the call under a heading of its own, the day's cap and
the alone rule holding and the minimum gap not, because it is an event rather
than the standing pressure the gap spaces out. kv `reflections`
(`reflect.keep`), counts and gaps per kind. Readers: her system prompt
(`prompt_text`), the intent (`inner_hint`;
a thought about Rena is not what she carries toward him), the person's
own reply call (`about(who)`), the comparison's thought goes out through
this channel. `/reflect`. history: archive §5.27.

### 9.6 `compare.py` `Comparison`: measuring herself against them

Code decides when (a peer in the scene or just talked with; pressure
from craving, shame, anxiety above their rest and belonging below par;
`compare.max_per_day`, cooldown); one call (`compare` role) decides what
from the record only, and `fires: false` is the common answer. Upward:
`envy` toward that person, shame, craving, a little anxiety, a strain on
the self-belief it lands on (`ModelOfHer.strain`); downward: a little
pride; level: only the thought, through the reflections channel, never
said aloud. kv `comparisons`, `compare_counts`, `compare_last_ts`.
`/compare [now]`. history: archive §5.90.

**Nobody writes anybody else's words.** `plan_day` is two stages. The
`cast_day` role plans the SHAPE of the day and nothing else -- time, who,
channel, salience, and `about`, one plain English sentence saying what that
person is reaching her about. Then `_speak_beat` calls each of them
separately (`cast_beat`), with **her own sheet as the system prompt** and the
contract underneath it, exactly as `Exchange._one_speaker` already does for
her turns: her day's draw, where she is, what she privately holds, and what
has already been said. One writer ventriloquising six people had put 俺 in a
fifteen-year-old girl's mouth, and no rule downstream can put back a voice
that was never there. It also told the writer "Hakata-ben ONLY from Tomoe",
which is wrong for a family whose sheets all say 家では博多が出る. A `group`
beat is one person's opening; the others answer in their own calls.

**The day's budget is the cast's own reach.** `plan_day` took the MEAN of
their attention, so the whole social world got about eight moments a day
whoever was in it -- six people, the group chat, LINE and the kitchen
between them -- and every day in the record had a three-to-four hour silence
sitting inside her waking hours while a ringleader whose sheet says she pulls
the group around all day got two beats. It is the SUM now
(`beats_base + beats_per_attention * sum(attention)/100`, capped at
`beats_max`), and each person is handed her own share of the total with the
channel her sheet says she lives on, rather than the model dividing it by
taste. Measured on the same day: 7 beats -> 16, group chat 2 -> 6, the
longest waking silence 4h30 -> 2h13. A beat written as HER is dropped
(`_HERS`): a beat is somebody reaching her, and her own turns come from the
exchange.

### 9.7 `commitments.py` `Commitments`: a promise with something on it

After an exchange (`from_exchange`, role `commit`) or after she has said
something to him (`from_chat`, role `commit_him`): one call names what she
committed to; code decides whether it binds (a cast counterparty and a
real date; for him one of `HIM_KINDS` and a date; `_week_line` gives the
model the dates so 明日 resolves). **A time said later is the promise's time** (`amended` in the `commit`
answer: an hour or a date named by either side for an open promise, not
refused, updates it -- `[commit] amended with ...`), **the last word in an
exchange counts** on a cancel, and `_promises_kept` names an untimed promise
the plan has no block for as well as a timed one it does not cover. The lines
this writes into the event ledger name `character.name` ("… told him she
would", "… promised"): the module is shared, and six of those lines wrote
the FIRST character's given name into every character's ledger until
`tools/character_names.py` was taught to read f-strings again (the tokeniser
stopped handing them over as plain strings in 3.12, so the guard had been
reporting shared code as clean).
**The prose never keeps a relative day**:
`_drop_relative_day` takes today / tonight / tomorrow / 明日 / 今日 and the
rest out of `what`, because the `date` beside it is the record of the day
and a sentence that says "tomorrow" still says it tomorrow -- one promise
was dated the 28th and read by the events model as the 29th, so it sat on
two days and the day it was dated had no block for it. Money can be
reserved. **The verb decides which record settles it, and the four are
`attend` / `buy` / `bring` / `send`**: a promise to send a person in her
world something goes out through the chat itself, so `_check_send` looks
for a message of HERS carrying a picture or a video, in a room that person
was in (`roster.witnessed`, the one rule `sim/thread.py` also reads), any
day from the promise to the day it is due. Her saying she sent it does not
count. Only `attend` and `bring` need her standing there, so only those two
go moot when the other person could not come -- somebody shut in at home is
exactly who a picture gets sent to. `send` means one thing to him and
another to a friend, so the branch is on who it was made to and never on
the verb. `owed_sends(who)` puts an open one in front of her in her own
turn with them (§9.2), because a promise she is given no way to keep is a
debt that only grows. **A promise to SEND is settled where it is kept** (`settle_sends_now`, called from the exchange the moment a finished room lands in the store, at the head of `from_exchange` before the judge is asked, and at the head of `settle`): the same record `_check_send` reads, so nothing she says about it counts. Settled only at the compile, sending the photograph at 16:01 left the promise open all evening -- the judge was shown it as still outstanding and opened a fresh one for the same act, and the chooser took "send her the photos you promised" three more times while the repeat filter deleted the words. The judge is also told in words that a thing she DID in the exchange is not a commitment and that an open one said again is not a new one. `settle(date)`
at the compile from the record only -- kept, broke, called off in words
(`_cancel`: honest, not free) -- and the counterparty's edge moves
(`_move_edge`). `closed_brief` tells the day's planner what has stopped
being owed, which is the only thing that stops it carrying a settled line
forward for ever (§9.1). **Late is measured, not rounded to kept**: `_late` is the
minutes past the hour she named, and past `late_after_minutes` the settle
still says kept (she came) but says how late in the `why`, gives
`late_regard` and `late_pride` instead of the full ones, no standing,
`late_irritation` on the edge of the person who was waiting, `late_guilt`,
and a self-memory that says she got there late and what she had said.
`attend_slack_minutes` is 90, so turning up at half past twelve for a nine
o'clock was settling with the same regard, the same pride and the same
"she kept her word"; a broken promise reaches her only through the person she
broke it to (`brief_for(who)` in their turn). **A promise is not kept at
home**: an `attend` promise whose words match no scene of the day is kept
only by a scene away from home (`_at_home`: her room, the kitchen, the
genkan; not somebody else's house, not the walk home) -- Kaito in her
doorway did not keep the match. `situation_line`,
`director_line`, `schedule_lines` (windows the plan must keep),
`morning_line`. `max_open` (6) bounds what she is carrying; `max_new_per_day`
and `him_max_new_per_day` are rate limits on the CALL and now LOG when they
bite -- at 3 they silently ate a real agreement (the library at 9 with
Aya), so nothing reached the schedule and she went on talking about it.
A promise with a `from_hm` for a future date throws away that date's drawn
wake and night (`_wake_needs_redrawing`), so the alarm is set when she
agrees, not when the plan is built (§8.1, §8.4). kv `commitments`, `commit_him_last_ts`. `/commit`.
history: archive §5.78.


**Is she going to make it?** `running_late` resolves the soonest timed promise
of today to a node, asks `Situation.minutes_to` what the journey actually
costs, and compares it to the clock -- nothing did that before, so she could
stand at the genkan with a nine o'clock and no idea. She is not honest with
herself about it: `optimism_minutes` is what she shaves off when she is already
behind, so there is a band where she IS late and does not believe it. Past
`knows_late_minutes` (set beyond the optimism, or the self-deception has no
room) she **knows**, and kv `knew_late` takes the moment. `_close` reads it: the
why names when she knew, the self-memory says she said nothing, the feeling is
ashamed rather than sheepish, and the guilt is scaled by `knew_guilt_factor`. A
lateness she walked into is hers; one she never saw coming is the system being
unfair to her.

### 9.9 `sim/peers.py` `Peers`: another running character, talking to her

Two characters are two processes with two saves and two models, and the hub
they both register with is the relay (`docs/peer-talk.md`, `docs/talkapp.md`
§11). `POST /bot/peer` puts a message in the recipient's own mailbox --
`chars[<to>]["peer_in"]`, never a row in her chat log, because a row there is
his chat and would be pushed to his phone, read-receipted and answerable by
him -- and `GET /bot/peer?char=&after=` reads what has been put in hers, the
cursor held by the reading bot (kv `peer_last_id`) so nothing is delivered
twice and a bot that was down misses nothing. `Channel.peer_send` /
`Channel.peer_updates` are the seam; a channel with no other characters on it
returns False and [].

**Not the path his messages take.** `App.poll_inbound` runs the relationship
with him -- attachment, the primitives, foresight, the expectations of him,
the questions she asked him, the state of a rupture -- and none of that is
true of somebody else's message. A peer message reaches her through two
doors and no others: her history, as a room of its own, and the company a
conversation is, once, at the close.

Code decides when, the model decides what. `Peers.tick(scene)` runs once a
pass from the loop: read the mailbox always; answer only inside
`open_from_hm`..`open_to_hm`, only while the scene's `phone_access` is not
`none`, only under `max_per_day` sends, only `min_gap_seconds` after her last
one, and only after a reading-and-typing delay taken from the length of what
she is answering. Her turns in one conversation stop at `max_turns`, and
`live_minutes` closes what has trailed off. She opens one herself at
`open_p` a pass when nothing is live, the same window holds, and it has been
quiet `min_gap_minutes` in either direction. Two characters each holding
their own caps is what stops two bots running away with each other: neither
has to trust the other to stop.

The call that writes her words is `persona.system_for("friend")` -- the same
person she is with him, byte for byte, without `style.md`, which is how she
writes to HIM -- then `prompts/peer_reply.txt` and her `style_ja_prompt`,
with `persona.carried_for()` after the thread as in every other room. Role
`peer_reply`, one of `LLM.VOICE_ROLES`, so the chat header's model toggle
moves it with the rest of her voice. Measured on the second character:
41,856 of 42,007 prompt tokens cached, $0.0007 for one answer.

Her history: `Thread._records()` reads kv `cast_chat`, kv `peer_chat` and kv
`peer_rooms` together (separate lists, because the cast exchange rewrites its
own list whole when it closes a conversation), and `Thread._room` renders the kind as
`messages with <name>` -- the name being what HER config calls the peer, so
nothing of the other character's record reaches it. A cast member's thread
never sees it (`roster.witnessed` is false for any kind that is not the
group). At the close: one kv `peer_chat` record, one `events` row of kind
`peer_chat` at salience 2, and `State.talk_relief`, which settles loneliness
toward its baseline by what that person is to her -- the same call the cast
close makes, so `sim/state.py` stays the one owner of the gauge. `sim/talks.py`
reads both lists, so the day's compile and recall see a peer conversation
without either knowing there is an engine. The ledger is read
(`ledger.text()` rides in the call) and never written.

Who her peers are is `peer_talk.contacts` in her own config: the peer's hub
id, what this character calls her, and the language of the room. Nothing else
about a peer is knowable -- no config of hers is read, no save, no sheet, no
presence -- and `sim/peers.py` names nobody. `tools/character_leaks.py` reads
the contacts and the peer's own turns out of her save as part of her record,
so a name she was told is quotable and a name she was not is still a flag.
`Config.REQUIRES` assigns the section `None`: every character may have a peer,
and one with an empty list has none. Built for every character in
`App.__init__`; `/peers [tick|flush]`. history: §19.

### 9.8b `sim/rooms.py` `Rooms`: a room, and who is in it

A person on the roster may carry one more field, `agent: "<hub id>"`
(`data/cast.json`, read by `sim/roster.py`: `agent_of`, `is_agent`, `agents`,
`by_agent`): the operator's statement that she runs as her own process. From
that moment this process writes no word of hers. `Exchange._one_speaker`
refuses her before it builds a prompt, `_their_turns` asks her through the hub
instead and the record's `awaiting` holds the room until she writes or
`exchange.agent_turn_deadline_seconds` (180) passes -- and going on without her
never means somebody else writes her turn. `CastEngine._speak_beat` writes
nothing for her either: the beat is still planned, and at its own hour
`deliver` puts the moment in her mailbox and holds the beat for
`agent_beat_deadline_seconds` (600). What comes back is appended by `_append`,
the one path a turn already takes, so it reaches the record, the thread and the
world's rooms table stamped where it landed. Nothing else about her row
changes: everybody who has not been promoted still speaks to her through her
sheet, her mechanisms and her week.

A room is the group chat or the two ends of an exchange, named as the world's
`rooms` table names it, and it now has a membership with the moment each person
joined and left: kv `rooms` in the owner's save, copied into the world file's
`members` table the instant it changes, so another process reads who is in a
room without opening anybody's save. Settled by the owner from the roster when
a room starts (`rooms.members_for`), printed on every join and leave. Every
turn goes to the members who run their own process, except the speaker, and
only if they were in the room at that moment -- so a joiner gets what came
after she joined and nothing before. Nothing here touches the network: kv
`room_out` is emptied by `Peers.tick`, the one object holding a hub connection,
and kv `room_in` is drained by the room's owner. On the other side of the wire
`Peers` treats a message carrying a `room` as a turn rather than a message to
her, needs no contact row for it, and writes her turn through
`persona.system_for("friend")` and her own thread; a participant runs none of
the room's machinery, which is why a third promoted person needs no new code.
`POST /bot/peer` carries one optional `room` field and reads none of it.
`tools/agent_seam_test.py` (in smoke). Spec: `docs/peer-talk.md` §4b.

A participant's copy of such a room is kv `peer_rooms`, capped at
`peer_talk.room_keep`: the words, who said them, when, and on which day. A
turn is filed under whoever SAID it -- the envelope carries the speaker on
every turn, and the message's `name` is the process that relayed it, so filing
the sender told her the room's owner had said somebody else's words. The same
turn arrives twice, once inside the ask that wants her words and once as the
relay of it, and two rows are one row when the speaker, the words and the day
match; the second arrival may add the clock the first one lacked and nothing
else. **Three readers**: the call that writes her next turn there, her own
history (`Thread._records` reads it as one conversation per room per day, and
`Thread.build(live_room=...)` keeps the live copy from being read twice), and
the group view on his phone. It had one, so six turns of her
own in the group chat left no trace in her history and drew nothing on his
screen. history: §19.
history: §19.

### 9.8c `sim/said_today.py` `SaidToday`: what she has already said to whom today

The room's memory of what it has tried dies with the room (`moves_block`,
§9.2), which is the wrong shape for the loop it was aimed at: one
character confirmed the same arrangement seven times to one friend across six
different rooms in one evening, and another sent the same photograph across
four. This
is the memory that crosses rooms -- kv `said_today`, `{date, people:
{name: [{hm, gist, room}]}, cooled: {name: until_ts}}`, one line per finished
conversation from the summary the writing call already returned, capped at 12
a person, thrown away on the first write of a new date. No model call.

Written from `tomoe/exchange.py _finish` (the counterparty of a private room,
every other speaker of a group one) and from `sim/peers.py` when a member who
writes her own turns finishes her side. Read by three: the call that writes
her turn gets it as a tagged block beside the promise line; the moment she is
asked what she does with the phone gets one line a person (`sim/pick.py`); and
a member who writes her own turns is handed the room owner's list in the
envelope beside the moves ledger, and reads her own out of her own save.

**It also holds the one gate.** After she opened a chat with somebody and had
nothing to say, or the filter dropped every bubble of hers in a one-to-one
with her, that person is off the list for `exchange.reopen_after_nothing_minutes`
of her clock (`cool`, `[pick] <name> is off the list until <hm>`).
`open_with_reason` refuses the room while it holds, so the backup path honours
it too, and the chooser is told in words with the time she comes back. Every
piece of its state is in the save, so a second instance in the process is the
same thing seen twice. Nobody is named in it.
history: §9.2, §9.7.


### 9.8 `care.py` `Care` and `worldshare.py`: rulers, not levers

`Care.measure(days)`: her initiative, the balance of the chat, her answer
speed, leaving him on read, how often she opens the app about him and his
notes, how much of her head he takes, the durable side (attachment,
resentment, the affection target) -> `investment` 0-100; the realism
check `checking_expected` (investment x uncertainty) against
`checking_actual`. `care.scale_checking` (off, his call) would multiply
the look and snoop rolls by `checking_factor`. kv `care_history` (one
row a day at the compile). `/care`.
**Every rate here divides by how long there has been a record**, not by
`window_days`, floored at `care.min_window_hours`. It was a flat divisor,
so a character an hour old was divided by a week and read as caring about
nothing whatever she did -- the second character's first evening reported
"checking expected 5.3 a day, actual 0.0" while she had looked twice in the
hour she had been alive. The floor is the other half: two looks in five
minutes is not forty-eight a day either.

`worldshare.measure(store, date)`: the share of the day's rows that
mention him -- inner lines, events, state reasons, thoughts, memories,
the message ratio -- and a composite; kv `him_share`, `/world`. Nothing
reads either back into her. history: archive §5.80, §5.88.
