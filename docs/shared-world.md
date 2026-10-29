# The shared world

His ask: *"the future state will be full agents but with the possibility of
them continuing to exist only as cast members until they are promoted to a full
agent. So we need a shared world; that would be the first thing."*

A character today keeps everything she knows about the world she lives in in
her own save: the people's days, where each of them is, what the day settled
(`sim/ledger.py`), the group chat and every exchange, who thinks what of whom,
the pool of what is going round. That is right for one process and impossible
for two. A second process running one of those people as a character of her own
would read none of it, and would plan a Saturday the first process never had --
her own school hours, her own promises, her own version of a conversation both
of them were in.

So the world gets a file. `world/shared.py` is that file's reader and writer;
`docs/peer-talk.md` is the other half of the same problem, two characters
saying things to each other, and this is what they say them *about*.

---

## 1. What a world is

A world is a set of characters and cast members who share one present: one
clock, one calendar, one set of people, one set of facts about where those
people are. Two characters are in the same world exactly when their configs
name the same `world_shared.id`. The file is
`<world.shared_dir>/<world_shared.id>/world.db`, one sqlite file per world.

A world is not a character and not a program. Nothing in `world/shared.py`
names a person, imports a program or knows what kind of character is reading
it; what a person is called arrives as an argument.

## 2. One writer, many readers

**The world has exactly one owner**: the character whose config says
`world_shared.owner`. She writes every row that is about the world, and
everybody else opens the file through a `mode=ro` URI and reads -- except for
the rows that are about HERSELF, which is the partition below.

- A reader never takes a copy. A file copy of a database being written is a
  torn image, and this file is written a row at a time while other processes
  are reading it. `mode=ro` is the same answer `tools/dbcopy.py` gives for the
  live saves.
- A reader that calls a write outside her partition is refused and the refusal
  is logged. There is no second answer to reconcile with, so there is nothing
  to reconcile.
- The owner's connection stays open; a reader opens one per look and closes it,
  because a reader is a different process and holds nothing between looks.
- The schema is created on the owner's first write, and a `version` row in
  `meta` says which shape it is. An owner that finds a higher version than it
  writes does not open the file at all.

**A character writes the rows that are about herself** (`world_shared.reader_writes_own_rows`,
default on; the check is `world/shared.py:_may_write`). She may write:

- a `whereabouts` row whose person is her, under the source `her own day`, which
  is what her own day planner settled -- her whole day at once
  (`put_own_day`), replacing what she wrote for that date before, because a
  block that MOVED in a re-plan is a different natural key and both answers
  would otherwise stand;
- a `members` row whose member is her;
- a `settled` line under the source `her own plan`, and never over a line the
  file already has: that table's natural key is the date and the line and
  carries no person, so hers lands where there is nothing and the owner's
  wording of a line both of them settled stands.

Anything else -- a row about another person, a row in any of the owner's six
tables -- is refused with the fault logged. Conflicts are impossible by key:
the person and the source are in the natural key of the whereabouts table, and
the room and the member in the membership table's. And a writer who is not the
owner does not stamp `meta`'s `world`, `owner` or `written` keys: opening the
file to say where you are is not claiming the world. She records herself under
`writers` instead, a JSON list of who else has written and when each of them
last did.

**The owner prefers her rows for a window.** Where the owner's process lists
where everybody is today, picks the hour of a beat for somebody, or reads how
reachable a person's phone is, a window that person wrote about herself
outranks the owner's draw of her week, and the draw stands for every window she
wrote nothing for (`world/shared.py:_prefer_own`, `CastEngine.their_own_where`,
and the same preference in the day's one truth, which drops an absence over a
window she has written). There is no switch on the reading side: a file that
holds two answers must be read one way by everybody.

**It is a copy, not the truth.** Every fact still has exactly one owner in the
owner's own save, and every world write sits beside the write that already
records the thing. Nothing in the owner's process reads the world file to
decide anything. If the two disagree, the save is right and the world has a
missing write.

## 3. What is in it, and who writes each table

| table | what it holds | written where | read by |
|---|---|---|---|
| `roster` | the cast rows a reader may know: the roster key, the name, the Japanese name, the role, what each of them calls the others, their week | `CastEngine.day_to_world`, after the day is planned | anybody in the world, to know who a name means |
| `whereabouts` | one row per person per window: date, from, to, place, who with, how reachable, and which source said so | `CastEngine.day_to_world` for everybody on the roster; `CastEngine.own_day_to_world` for the character the process runs, when the world is somebody else's | a reader planning her own day against theirs, and the owner's planner, which prefers a person's own rows |
| `settled` | what the day fixed, in the plan's own wording | `Ledger._settled_to_world`, as the day's one truth accepts a line -- the owner's lines, and a reader's own plan's under her own source | a reader who must not contradict it |
| `rooms` | the group chat and every two-person exchange, one row per turn: date, room, who, the time, the words, the gloss, who else was in the room | `Exchange._turn_to_world`, inside the stamping of the turn | a reader who was in that room |
| `members` | who is in each room and since when: the room, the person, the moment she joined, the moment she left, and her hub id when she runs as her own process | `Rooms.join` / `Rooms.leave` (`sim/rooms.py`), the moment it happens | a reader deciding whether she was in the room when a thing was said |

The store lets a character write the membership row that says SHE is in a room,
and no caller takes it: the only rooms a reader's own process opens are her own
circle's (§9), which are not the world's, and their names would put people the
owner has never met into the world file. The rooms she is in that ARE the
world's are opened by the owner, who writes the row as she asks her in.
| `graph` | what each of them privately holds about another: regard, irritation, and the line of view | `compile_to_world()` at the compile | a reader deciding how somebody treats her |
| `orbit` | the people around the people: whose brother, whose coach | `compile_to_world()` | a reader who may hear of them |
| `gossip` | what is going round that is nobody's own business, with its heat and who has heard it | `compile_to_world()` | a reader who may repeat it |
| `events` | what the day's record says happened, at the salience it was filed under | `compile_to_world()` | a reader's own compile |

Every row carries a `ts` in machine local time and the writing character's id.
Machine local because a world holds two processes on two character clocks and
one machine, and the machine's clock is the only one both of them agree about.

**A roster row is never a sheet.** What a person is called and when their week
has them somewhere is public in the world; what they think, feel, want or hold
against anybody is not, and lives only in the owner's save and in the sheets
under `prompts/cast/`. The one exception is deliberate and is the `graph`
table: what one of them holds about another is exactly what a second process
running that person would need in order to be that person, and it is written as
the compile settles it rather than as a running feeling.

**Every write is one row the moment the thing exists**, never a batch at the
end of a tick, and every write is guarded: a world write that fails is logged
by exception type and the pass goes on. The guard is inside `world/shared.py`
rather than at the ten call sites, so a caller cannot forget it.

**A rewritten row is the same row.** Each table has a natural key -- the person
and the window, the date and the line, the room and the time and the words --
so re-planning a day, or reading the settled lines a hundred times while
building prompts, leaves the same rows rather than a hundred copies. The
ledger's writer keeps a per-day set of what it has already said, because
`Ledger.settled` is read on every prompt build.

## 4. What stays hers

Nothing that is her rather than the world:

- her gauges and everything that moves them;
- her memory, her episodes, her diary, her own record of herself;
- her thread with him, and every message either way;
- her model of him, her expectations, her questions, her attachment;
- her sentiments and her meters about the people in the roster -- the world
  says Rena's day was cancelled, not how she feels about Rena;
- her plans, her schedule and her body.

Two characters in one world therefore agree about what happened and disagree
about what it meant, which is the only arrangement that is worth two processes.

## 5. Switching it on

`world_shared` is a switchable section and its row in `Config.REQUIRES` is
`in_world`: a character with no world has no shared world, and the section is
forced off for her at load. The directory is a key of the flat `world` section,
`world.shared_dir`, and is in `Config.WORLD_KEYS` for the same property, so a
character with no world has no *path* to anybody else's world rather than
merely never being pointed at one. That is what keeps `tools/isolation.py`
green: the second character's loaded config names no world directory at all.

The store is a declared wire (`sim/wiring.py`). `tomoe/app.py` builds it, names
it on the App as a program slot, and attaches it to its three writers -- the
cast engine, the exchange and the ledger. A character whose program does not
build one has `None` there, and every writer tests for it.

## 6. Reading it

    python world/shared.py --id <world id>

prints the row counts and the last row of each table. `python tools/world_test.py`
drives a plan, a settled line and a turn through the live code paths on a copy
of the owner's save with the model stubbed and the network refused, then opens
the same file from a second `Config` as a reader and reads every row back.

## 7. How a cast member is promoted

A cast member becomes a character by the route `docs/peer-talk.md` §4 already
describes -- her own config, sheet, prompts, save, program, launcher and one
registry row -- plus two lines: `world_shared.id` set to the same world, and
`world_shared.owner` left false. She then reads the roster, the whereabouts,
the settled lines and the rooms she was in, and plans her day against a present
somebody else is keeping.

**She is one person, and the owner is a person.** She is still a row in the
cast file she reads, because everybody who has not been promoted goes on
reaching for her through it and the owner's process still needs to know where
she is. In HER process that row is not a second girl: `sim/roster._table`
finds it -- the row whose `agent` is the hub id her process registers under,
failing that the row whose Japanese name is her config's -- and folds it into
her own entry, so its key, its Japanese name, its reading and every nickname
the others call her by all resolve to `self`. `roster.handle(config)` returns
that key, which is what the shared record and her own edges are keyed by. The
other way round, the keeper of the cast file has a line in it -- `self`,
carrying `key`, `role_id`, `role`, `agent`, `ja`, `reading` and what she calls
each of them -- and for a reader that line becomes a person on her roster,
because the girl whose world she is in is somebody she is at school with every
day. It is not a person for the character the file belongs to.

Without those two her process ran with one girl split in two and one missing:
her own nickname resolved to a stranger with her own face (eight boot lines
saying her name meant both `self` and a role), the name her own fills use for
the owner resolved to nobody, and what her own mother and brother call her
came back empty because the key their `calls` map uses was somebody else's
handle. A word that is two people's is HERS: `お母さん` means the woman in her
own kitchen, and it resolved to the other girl's mother until her own people
won the collision.

**Her fills must be hers before her first schedule is written.** Promotion
copies a save and writes a fills file; a boot in between plans a day out of
whichever fills are on disk at that minute, and that day is then in her save
with her ward, her station and her family in it wrong. Hers were corrected the
next morning and everything written under the old ones went on driving her
week: the day's plan, the scenes, the open threads, the arcs and the bonds.
See §7a for what that costs and how it is undone.

What this increment does **not** give her, and what a promoted agent still
needs:

1. ~~**A second writer.**~~ Built since, as the partition in §2:
   she writes the rows about herself under her own id and her own planner's
   name, and the owner's planner prefers them for a window. The claim protocol
   was not needed -- the natural keys already carry the person and the source,
   so two writers cannot land on one row.

   One consequence of that has a rule of its own now. The owner's process
   plans a day for the promoted girl's row too, so the world file carries
   where SHE is, including the absences her plan fixed for her -- and her own
   day's one truth read them back and told her, about herself in the third
   person, that she was at her grandmother's from 16:00 to 22:00.
   `sim/ledger.py:absent` drops a row whose person resolves to her
   (`roster.is_self`), the same test `tomoe/cast.py:world_where` already makes
   before it lists where everybody is. It stays a row about her in the file,
   because the owner's process needs it; it is not a row she is handed. The
   world-reader check seeds absences for two people and asserts that she gets
   the one that is not her and does not get her own.

   The same file says where the owner's household is, and none of them is
   anybody she has met. `world_where` drops a person who is family in that
   world and is not one of her own people (`roster.is_family` and
   `roster.is_own` together), so the owner's father and brother stopped
   appearing under who is free with her after school and in her own circle's
   day planner.
2. ~~**A turn she speaks.**~~ Built since, in `docs/peer-talk.md` §4b: the
   owner's room asks her through the hub and appends what comes back by the
   one path a turn already takes, so her words reach the rooms table with her
   as the speaker. The rooms table is still written only by the owner.
3. ~~**Her removal from the cast.**~~ Built since: a cast row may carry
   `agent: "<hub id>"`, and from that moment the owner's process asks her
   instead of writing her, in the exchange and in the day's beats alike. She
   keeps her row, because everybody who has not been promoted still speaks to
   her through it.
4. **A world clock both of them agree about.** Both characters read
   `world/clock.py` with their own timezone from their own config; nothing
   checks that two characters in one world are on one clock.
5. **A reader's cache.** Every read opens a connection and runs a query. That
   is right for a few looks a minute and wrong for a prompt build that wants
   the roster on every call.

## 7a. What the save she was copied from still held

Promotion starts her from a copy of the owner's save, and what is in it is not
only a world she may now read. It is the other girl's interior: her bonds with
her own mother, father and brother, her bond with the promoted girl under the
nickname the world files her by, the slow pressures a showrunner wrote over
her record, and the threads her director left open. None of it is written any
more -- the writers are off (§8.1), her own row is herself on her roster (§7),
and her fills are hers -- and all of it went on being read.

So it is moved out of the save, once, and deleted:
`tomoe/app.py retire_owner_interior_once` at her next boot, or
`python tools/promoted_save_retire.py --config <her config> --apply` on a
stopped one. What goes, and the rule for each:

| what | the rule |
|---|---|
| a bond | it resolves to herself; or to nobody on her roster; or it is a member of the OWNER's household (a family role that is not one of her own people -- her household is her own file's); or it is the man she has no chat with, when her sheet's `with_him` says `none` |
| every arc | the section that writes arcs is off for a character who does not keep her world, so every arc in her save predates the rule and was written over the other girl's record |
| a thread | its `people` name her (she is not one of the people in her own thread), or somebody the roster does not have |
| today's plan and scenes | the schedule row and the scenes for today and after, when they were written before this pass: they were planned under the old fills. Her own boot plans the day again -- `App.ensure_day` finds no row and asks the program, which calls the day planner because it is past `schedule.generate_at` |
| the day's settled lines | all of them, in `cast_beats` and `cast_beats_prev`: the planner that wrote them was reading the world's open threads, and "the flea market on Thursday with the group -- carried from yesterday" names nobody and is the school's plan. What the world settles reaches her through the day's one truth, which reads the world file; her own plan's settled lines are her own circle's from here |
| a beat | it is for somebody who is not one of her own people |
| the orbit | relatives seeded out of the world's cast file by a register that is switched off for her (`tomoe/app.py` builds no orbit at all when the section is off, which is what let it seed) |

The rows go to `data/retired/<stamp>_promoted/<save>.json` verbatim. kv
`owner_interior_retired` marks it done, and a character who keeps her own
world never enters it. The mind is built before the program is, so the bonds
are reloaded onto the state object afterwards: without that the next
`state.save()` writes every one of them back.

One line at her boot says what moved:

    [promoted] the interior of the character this save was copied from is
    retired: 5 bond(s), 4 arc(s), 1 thread(s), 1 day(s) of plan and 44
    scene(s) written before her own fills were, 1 line(s) of the day's plan
    her own people could not know, 10 relative(s) of the world's
    -> data/retired/20260907_0800_promoted/rena.json

### 7b. And the second pass: her meters settled against her roster

The pass above takes out what is the other girl's. It does not put anything
back, and it does not touch what each person is to her -- so after it ran on a
live save there was still no meter at all on the girl whose world she reads,
and the sentiment rows still held what she felt about the owner's mother,
father and brother and about a man she has no chat with. Both are the same
fault as the bonds were, one step behind: the meters are seeded once and never
re-read, and the sentiments are seeded once from the meters.

`tomoe/app.py reconcile_meters_once`, behind kv `meters_reconciled`, and
`tools/promoted_save_retire.py:reconcile_meters` on a stopped save. It is a
second marker rather than an extension of the first because the first had
already run on a live save before this existed.

| what | the rule |
|---|---|
| a meter dropped | the same rule as a bond above, asked again against the roster as it now resolves |
| a meter added | somebody the roster has and the meters have not, at her own sheet's opening values (`people.<key>.opens_at`). This is how the owner gets one: she is the cast file's KEEPER rather than one of its people, so the raw seed could never have reached her |
| what somebody is to her | a sentiment row about a person the meters no longer have. The row a newly added meter gets is written by `sim/sentiment.py:seed_row`, the same function the first seeding uses, so a repaired save and a fresh one hold the same numbers for the same person |
| every day planned before this pass | every schedule row up to and including today, and today's scenes. Today's was written from the owner's map and the owner's household, and the day after a day is written from the day before it |

Who a character may hold a meter on at all is one statement,
`sim/roster.py:meter_rows`, and both the fresh seeding (`sim/state.py`) and
this repair ask it, so a save seeded today and a save repaired today hold the
same rows. The line at her boot:

    [promoted] her meters are settled against her roster: 0 dropped, 1 added,
    6 row(s) of what somebody is to her dropped, 1 day(s) and 2 scene(s)
    planned before this pass -> data/retired/<stamp>_promoted/rena_meters.json

---

## 8. A non-owner

The third character was started in the first character's world with
`world_shared.owner` false, and her first forty-five minutes showed what
promotion had left undone: her process runs the same world program, so it
built a **second world on the same roster inside her own save**. Its own pool
of rumours (three at 15:26), its own weekly pressures (four arcs, one about
the first character's money), its own day's script for six people, and eight
beats planned for the others, five of them written as her own and dropped at
the agent seam. Two planners over one roster, each writing into its own save,
only the owner's reaching `data/worlds/tokyo/world.db`. Every one of those
subsystems was doing exactly what it was written to do.

The rule, and it follows from the two keys her config already carries:
**a character who is in a world she does not own reads the world and runs
none of the machinery that writes it.**

### 8.1 What is switched off, and why each

The existence table does it, not her config. `Config.REQUIRES` gains a fifth
property, `world_owner`, and `_existence_implies` adds it to what a character
lacks when she has no world at all, or when the shared world is on and her
config does not say she owns it. A character alone in a world with the shared
file switched off keeps writing her own world, because nobody is reading it.

| section | what it writes into the world |
|---|---|
| `cast_arcs` | each person's own week, and the thread they are on |
| `showrunner` | the pressures behind those weeks, once a week |
| `gossip` | the pool of what is going round, and who has heard it |
| `events` | what the day's record says happened, and at what salience |
| `orbit` | the people around the people: whose brother, whose coach |
| `npc` | everybody who is not the cast: the till, the platform, the classroom |
| `compare` | measuring herself against the room, which reads the others' days |
| `social_graph` | who privately holds what about whom: the regard, the irritation and the line of view, settled once a day from what each person witnessed |

Two more are not sections and are gated in the program, because the sections
they live in stay on for her: **the cast planner's day**
(`CastEngine.plan_day`, and `presence_beat` beside it, which invents a line
for somebody sitting with her, and `CastEngine.due`, which is the other end of
the same rule -- a plan already in her save keeps coming due on her clock) and
**the exchange's own starting of rooms** (`Exchange.start`, `self_open` and
`alone_beat`). A room has one owner (`docs/peer-talk.md` §4b) and it is the
process that starts it. She is still a participant in every room she is asked
into, which arrives through her mailbox (`sim/peers.py`) and never through
`tomoe/exchange.py`.

And one is not a section either but belongs here for the opposite reason: **the
ward events fetch** (`maybe_local_events`). What a ward has announced is the
world's rather than anybody's judgement of it, two characters in one world have
the same wards and the same calendar and name the same file, so it has one
writer and the reader reads what the owner wrote. The national news feed beside
it is NOT of that kind and every character in a world runs her own: the
selection is her observer note, her declared taste, her calendar, her model and
her own keep -- see the dated entry in HISTORY under the world section.

What stays on is everything that is her rather than the world: her gauges, her
body, her own day planner, her diary, her reflection, her record of herself,
her persona, her thread, and her turns in a room somebody asks her into. Her
boot says so in one line:

    [config] she is in the world 'tokyo' and does not own it, so she reads the
    world file and runs none of the machinery that writes it: cast_arcs,
    compare, events, gossip, npc, orbit, showrunner, social_graph

The graph is the one of the eight whose object is still built for her, because
every reader of the edges takes them through it and there is nowhere else to
put them: `SocialGraph` for a character who does not own the world reads the
file's `graph` rows instead of her save, seeds nothing, updates nothing and
writes nothing, and says so once at her boot:

    [graph] read from the world file: the edges are the world's, and none of
    them hers to seed, move or write

### 8.2 What she reads instead

Where a switched-off subsystem's output was read by something that stays on,
the reader takes the world file's rows through `world/shared.py`. Never a
second writer, and never a second copy: each of these opens a `mode=ro`
connection for the look and closes it.

| what she needs | where it came from | where it comes from now |
|---|---|---|
| what the day settled | the plan in her own save | `settled_lines(date)` (`Ledger.settled`) |
| who is not around today | the plan's `absent` list | the `whereabouts` rows the owner wrote for an absence (`Ledger.absent`) |
| where everybody is, and how reachable | her own draw of their week | `CastEngine.world_where`, behind `plans_brief`, `plan_line`, `available` and `free_after_school` |
| what is going round | her own pool | `gossip_lines()`, in the half of her prompt that moves during a day |
| the people around the people | her own orbit | `orbit_lines()`, beside it |
| what each of them holds about her, and about each other | her own edges, seeded from the cast sheets and moved by a paid update of her own | the `graph` rows, through the same `SocialGraph` object her cast turns, day planner, spiral settle, witnessed-goal price, ick, promises, `/graph` and backstage already read |
| who was in a room when a thing was said | -- | `members()`, as the agent seam left it |

`world_shared.read_rows` (8) is how many rows of one table she puts in front
of a model. Her own whereabouts are her own day planner's and are hers to
know; the owner's row about her stands as what the others believe.

**Nothing changed for the owner.** Her boot note, her prompt bytes and her
planner are what they were, and she still plans a beat FOR a member who runs
her own process -- the room asks her through the hub, which is the seam's
design and not this rule's business.

### 8.2a What her first forty-five minutes wrote, and where it went

The rule went on after such a character had already been running, so her save
already held a world of her own: her draw of the roster's week, her day's
script for six people whose day the owner had fixed, her pool of rumours, her
orbit and her edges. Nothing new is written now, but every reader of one of
those keys was reading a second world's answer instead of the owner's, and the
day's beats kept coming due on her clock and surfacing one line at a time in
the one view she has.

So they are moved out of the save, once, and deleted:
`tomoe/app.py retire_second_world_once` at her next boot, or
`python tools/second_world_retire.py --db <save> --out <file> --apply` on a
stopped one. Eight keys (`cast_beats`, `cast_beats_prev`, `cast_arcs`,
`cast_days`, `cast_plans`, `gossip`, `orbit`, `social_graph`) and the `events`
rows of kind `cast`, whose only writer is the beat delivery a reader now
refuses. They go to `data/retired/<stamp>_second_world/<save>.json` verbatim --
kept where a person can read them, because they are one process's answer to a
question that was not its own. kv `second_world_retired` marks it done, and a
character who owns her world never enters it. The same pass repairs her record
of the rooms she is in (`docs/peer-talk.md` §4b.5): a turn filed twice, once
under the relaying process's name and once under whoever said it, becomes one
turn, and every turn is stamped with its day.

One line at her boot says what moved:

    [world] the world this process wrote in a world it does not keep is
    retired: cast_arcs, cast_beats, cast_days, cast_plans, gossip, orbit,
    social_graph, 2 record row(s) of the day's beats, 1 room(s) of hers
    repaired (2 turn(s) filed under the wrong speaker dropped, 15 dated)
    -> data/retired/20260906_2006_second_world/rena.json

### 8.3 Proved

`tools/world_reader_test.py`, in smoke, so it stops a restart. Two builds on
copies sharing one scratch world directory, every model call and every network
connection refused: the owner plans a day and writes it through the live
writers, then a character who names the same world and does not own it is
built and asserted to switch off all eight sections, to build no planner, arc,
pool, record, orbit, stranger or ruler that runs, to refuse every opening that
would put words in somebody else's mouth, to be refused by the file itself if
she writes, and to carry the owner's settled lines, absence, whereabouts,
reachability, pool, orbit and edges in her own ledger and her own prompt. The
edges are checked both ways: the compile's settled stage writes no edge into
her save and seeds none, and what the people around her hold about HER reads
back as the file's rows at the file's numbers -- not, as it did, as what they
hold about the character whose world it is.
`tools/existence_matrix.py` now has the two world kinds as separate rows --
36 combinations, all clear -- because a reader is a different build from an
owner and nothing had ever tried one.

## 9. A reader's own circle

A reader answers in the owner's rooms and, before her circle landed
(HISTORY 2026-09-07 04:50), had nobody else: her cast file was the world's roster, every person in it was the
owner's to plan, and her process refused every room. Rena's mechanisms --
filling an empty evening, closing a plan for everybody -- had no room to
fire in, and her planner, running the same program as the owner's, said
"her" with the first character's name.

**Two cast files.** `character.cast_file` stays the world's roster, read for
names and for the people she shares with the owner. `character.own_cast_file`
(and `own_cast_sheets_dir` for their sheets) is HER OWN people: the ones the
owner does not know, and her own family, which the world's roster also
carries so the owner's planner knows they exist. `sim/roster._table` loads
both; a key in both files is hers; every record carries `own`, and
`roster.is_own(config, who)` is the one question (`own_keys` the list). For
the character who keeps her world every person is her own. The boot line
reads `[roster] N people, M names; K of them her own, from <file>`.

**And a row says whether that person is family.** Two households in one world
cannot both be `mother` and `sibling`, so a reader's own mother and brother
are on the roster under role ids of their own -- and the five family role ids,
which are what the group chat and "was this person in the room" are decided
by, therefore said her own mother was not family while the OWNER's mother was.
A row may carry `family: true|false` and settle it; without the field the five
ids are the answer, so the character who keeps her world is unchanged.

In a SHARED roster the row says WHOSE, by naming that character instead of
answering yes: `"family": "<roster key>"`. A promoted character's mother and
brother stay on the world's roster so that her own process can resolve them,
and to everybody else in that world they read as two more people in the group
-- which is how the next character promoted out of it came up holding a
relationship meter on somebody else's mother, found by promoting a second
person and booting her (`data/retired/20260907_1100_promotion_proof/`). Named,
the row is family to her and to nobody else, `sim/roster.py:meter_rows`
refuses a meter on another character's mother or brother with that reason on
the row, and the owner's answer is unchanged: they were never her family and
`is_family` still says so.
`roster.is_family(config, who)` is the question, and whose family is that
question with `is_own` beside it: for a reader, a family row that is not one of
her own people is the owner's household, which is how her meters, her rooms and
where-everybody-is-today all drop them in one place instead of four.

**What her process does for her own people, and only for them**
(`tomoe/cast.py`, `CastEngine._people`): their day (`plans`, out of both
files' weeks), their draws, their lives, the day's beats (`plan_day`, with a
paragraph telling the planner these people are not in the group chat and no
`group` beat may be written; the late group stretch is not planned and a
`group` beat is dropped), the beats coming due (`due`, a beat for somebody
on the world's roster is dropped whatever wrote it), somebody in the room
saying a thing (`presence_beat`). Each person's words come from her own
sheet under `own_cast_sheets_dir`, checked before the world's directory
(`person_sheet`), and her own line -- what she calls people -- is the
`self` block of her own file (`tomoe_sheet`). `Exchange.start` opens a room
with one of her own people; the group chat, the others carrying a beat
without her, and every room with one of the world's people are still the
owner's and still refused. Every row lands in her own save (`cast_plans`,
`cast_days`, `cast_beats`, `cast_chat`, `rooms`, her thread); the copy into
the world file is guarded on `owner` at every write and is never taken.
The ledger's absences and settled lines are the world's rows followed by
her own plan's (`sim/ledger.py`); a person's reachability is the world's
row for the world's people and her own plan for hers.

**And her own whereabouts now reach the world** (§2). Her day
planner writes her blocks as `whereabouts` rows under her own id the moment
her day is settled and again whenever it changes, and the lines her own plan
settled go in under her own planner's name; the owner's process reads those
rows in place of its own draw of her week, so where she says she is, is where
the world has her. What she is NOT writing is who she is with: the people
beside her are her own circle's and are not in this world. Her own circle's
rooms and words still land in her own save alone.

**Her own circle's calls carry her circle's world and nothing else.** These
people are not at her school, are not in the group chat and have never met
anybody in it, and the one call that plans their day was being handed the
world's: where the owner, the owner's father and the owner's brother are
today, what the owner's classmates privately hold about her, what she calls
those classmates, and the school's open threads. The planner turned one of
those threads into its own settled line, and every beat writer is given the
settled lines, so a friend at another school spent her evening replying to a
plan her class had made at lunch. What is filtered, and where:

| what | rule |
|---|---|
| where each of them is today | `CastEngine.plans_brief(date, own_only=True)` for her own planner: her own people's plans only. The director's call is unchanged and still reads the world's rows |
| where SHE is | `world_where` drops the row for herself: the owner's process plans her day too, and where she is, is her own schedule's answer |
| what they privately hold | the edges block is filtered to the people in the plan, so a reader's block is empty and is not written |
| what she calls people | her own line lists what she calls the people in THIS call |
| open threads | `Records.threads_brief(keep=...)`, and the reader's rule drops a thread naming somebody outside her circle |
| what the day settled | `CastEngine.settled_line` drops the same lines, so no beat writer of hers is given one; the room prompt of one of her own people gets the day's one truth with those lines out (`Exchange._settled_txt(who=...)`), and her own side of the room is not filtered, because she is in that world |
| what she has promised | the same, for the planner's promise block: a promise she made at school is not this circle's business |

The rule is one function, `roster.mentions_outside(config, text)`, over every
name the roster knows for somebody who is neither hers nor her. It is always
false for the character who keeps her world -- everybody there is hers -- and
`CastEngine._own_lines` returns what it was given, unchanged, for her.

**"Her" is the character the process runs.** `CastEngine._her()` and the
exchange's name lines resolve `config.character.name` through the roster;
`Exchange._calls_me` reads what a person calls her from the entry of their
`calls` whose key is one of her own names. Before this every one of those
was the literal `"Tomoe"`, which on a promoted character's roster is the
girl whose world she reads.

**Rena's circle** (`characters/rena/cast.json`, sheets under `prompts_rena/cast/`,
mechanisms `data/cast_mechanisms/Nanami.json` and `Yuzuki.json`, types in
`data/cast_types.json`): Matsuoka Nanami, a year above her at the Wednesday
K-pop class near Ikebukuro east exit, the one room where Rena is not the one
who decides; Okamoto Yuzuki, her middle-school best friend at a girls'
school in Nakano, who answers six hours late and whom Rena fixes a Saturday
for; and her brother Keita and her mother Miwa, whose rows and sheets are
copied beside them. Everything not on her sheet, her bible or her roster
row is marked INVENTED in the file. Her bible carries one paragraph on the
two of them. `tools/world_reader_test.py` checks that her process plans a
day for nobody on the world's roster and delivers no beat for one, that her
roster has no row for herself and resolves the owner, that her save holds no
bond, arc or thread that is the other girl's, and that the prompt her own
circle's day is planned from -- built with the model stubbed -- carries none
of the other girl's household names, none of the world's private edges and
none of the world's whereabouts. The names come from
`tools/character_names.py`, never from a literal.

**Her own family are family.** Her mother and brother have roles of their
own (`rena_mother`, `rena_brother`), so the room code, which asks whether a
speaker's role is a family role, said no about her own mother: no household
block in front of the one person who speaks from it. It asks her config now
(`sentiment.family_roles`, which lists hers). The household itself is her
own file's, and the module that draws the parents' day
(`tomoe/family.py`) asks the members of THAT household who exists: her
household has a mother, no father and no car, and until it asked, her day
planner was told every day that "dad is home all day (his day off)" out of
an empty schedule block and its own defaults.

**Not built:** a group of her own (a LINE group with her own people would
need a room name that does not collide with the world's `group`), and her
knocking on the owner's group chat (a reader asking the owner to open the
group with her opener, through the hub).
