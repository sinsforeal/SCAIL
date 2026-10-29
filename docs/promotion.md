# Promoting a cast member to a character

His ask: *"the future state will be full agents but with the possibility of
them continuing to exist only as cast members until they are promoted to a full
agent."* This is the generator between the two states: what it may write, what
it may not, and what a promoted character still lacks before anybody starts
her.

`tools/promote_cast.py` is the tool. `docs/peer-talk.md` §4 says what a
character is as a unit; `docs/shared-world.md` §7 says what she gets from the
world and what the world still owes her; `docs/cast-mechanisms.md` says what
her mechanisms file and her type file are.

## The two states

A person beside the first character exists today as four files, none of which
runs anything:

| file | what it carries |
|---|---|
| `data/cast.json`, her row | her role, her meters with the first character, her week, her aliases, what she calls each of the others, her `voice` line |
| `prompts/cast/<key>.md` | who she is, in her own language, written to be read by the calls where she speaks |
| `data/cast_mechanisms/<key>.json` | what she does, when, and what stops her; her drivers; what she does not say |
| `data/cast_types.json`, her entry | the author's prior, and one sentence of behaviour per axis. No call may read it |

A character who runs is a BUNDLE: one directory, `characters/<key>/`, holding
everything that is that person, and a manifest saying how she is run
(`docs/bundle.md`). Promotion writes that directory and nothing else --
no config, no launcher, no register row -- and `tools/new_character.py
compose <key>` makes the rest of it from the bundle, which is what makes
composition the same one tool for a promoted character as for one written
from scratch.

## What the tool writes

    python tools/promote_cast.py Rena-chan --dry-run
    python tools/promote_cast.py Rena-chan --root C:/temp/bundles
    python tools/promote_cast.py Rena-chan            # into characters/rena-chan/

With `--root` the whole character, and everything compose would make from
her, lands inside that one directory and nothing outside it is touched, which
is how a promotion is checked before it is allowed anywhere near the tree.

| what | where | written from |
|---|---|---|
| her sheet | `characters/<key>/sheet.json` | her row, her sheet, her mechanisms, the behaviour lines of her type |
| her fills | `characters/<key>/fills.json` | the same, plus the world's map for the school, the line and the city |
| her voice | `characters/<key>/prompts/bible.md` | her sheet under `prompts/cast/`, seeded whole |
| her speech guide | `characters/<key>/prompts/style.md` | the 話し方 paragraph of that sheet, her `voice` and `first_person` lines, and the project's two rules about how a feeling and a situation may be written |
| her manifest | `characters/<key>/bundle.json` | her key and hub id, the world she reads and that she does not own it, which of her files answer which config key, the files she still lacks, and every config value that is hers rather than the library's |

The manifest says `registered: false`, so compose writes her config, her
prompt directory and her save and leaves the operator's register and the
launchers alone: who runs is his decision. The row it would add is printed at
the end of a run, and so is the command that composes her.

`--dry-run` prints all of it and writes nothing. Her config is never written
by this tool: the machine's settings and every secret are merged in memory by
compose and never enter a bundle.

## The five existence answers

Every one is decided from her own material and carries the reason on the sheet
beside it. For a girl on the first character's roster they come out as
**embodied, in a world, seeing nothing of his machine, no account** -- a
combination `tools/existence_matrix.py` builds and renders, and which neither
character who runs today has.

- **embodied**, because her row gives her a week in a real city: school hours,
  fixtures with times, a walk to a station, a curfew, a phone that gets taken
  away.
- **in a world**, because she is on the roster of a world that exists, at the
  same school (`school: "same"` on her row) and on the same line.
- **sees_him: none**, because nothing on her row or her sheet gives her any
  sight of his machine. What she has of him is what she has been told, which
  her row records as a stance and not as a feed.
- **has_account: false**, because no account of her own is named anywhere in
  her material.
- **with_him: none**, because she is promoted for her friend's circle and
  not for him: no chat with him, nothing felt or expected of him, and his
  phone does not list her (the relationship layer is off by
  `Config.REQUIRES`, `sim/pick.py` offers her no `text_him`, and
  `channels/talkapp_bot.py` registers her hidden). A promoted character
  also gets a cast file of her own beside the world's, `own_cast_file`,
  for the people the owner does not know (`docs/shared-world.md` section 9);
  the tool does not write that file, it is authored.

Nothing else is switched by hand. Every consequence of those five is left to
`Config` at load, which is what stops a promoted character quietly keeping a
subsystem the first character has and she should not.

## Her numbers, and the letters that never reach her

The type file holds four letters and, per axis, one sentence of the behaviour
they were translated into. The tool reads the letters, moves a gauge's baseline
off the mechanism's default by a fixed amount per pole, and writes onto the
sheet **the sentence, never the letter** -- one `gauge_basis` line per gauge
naming the behaviour the number came from. Somebody who speaks first and keeps
speaking runs warmer and is bored sooner; somebody who decides by who will be
pleased and takes a short answer personally needs more answering; somebody who
fixes the hour and treats it as settled leaves less unsaid. The numbers are a
starting point and the author's to retune. What the tool guarantees is that
each came from a stated behaviour rather than from the first character's sheet.

## Whose material may be used

**Hers, and the world's public facts.** Her row, her sheet, her mechanisms, and
the names on the roster, the school and the line off the world's map. Nothing
is read out of another person's row: a peer's `note` and `stance` are that
person's inside, and they are the first character's view of them. Her own sheet
makes the point for the tool -- it says in as many words that she does not know
what one of her friends actually does after school and thinks she does.

So an example in her prompts is either something out of her own week and her
own mechanisms, or a shape with a name in it ("X has not answered since this
morning"). It is never a fact about X.

## Her age and her birthday

A roster row has no age. Her sheet says it in her own language, and her school
year with it. Two facts then constrain her birthday and neither gives a day:
her age today puts it in the twelve months ending today, and the Japanese
school year puts a first-year of high school among the intake born between the
second of April and the first of April of the following year. The tool writes
the overlap, the arithmetic for both, and a date in the middle of the span,
with the note that the day and the month are established by nothing and are the
author's to overrule.

## The two prompts that are ported, and why only two

Every shared mechanism prompt carries no person by construction
(`tools/neutral_gate.py`): the character-shaped spans are `[[TOKEN]]`s filled
from her own fills file. So a port is needed only where a shared file **is** a
person. Two are:

- `prompts/bible.md` is the first character herself, from her name down.
- `prompts/style.md` (and `prompts/style_ja.md`) is written for a girl who
  renders casual Japanese into English and slips into Hakata-ben when she is
  tired. A promoted cast member's row says Tokyo standard, no dialect, and
  Japanese to everybody including him.

`tools/forge.py`'s own survey agrees: of the shared prompts that still contain
a word from the first character's sheet, the only three that match on a name or
a dialect marker rather than on "Tokyo", "English", "Japanese" or "mom" are
those three files.

Both files the tool writes are **seeds**, and they are marked as such in their
own first line. The bible is her cast sheet, which is the only authored
statement of who she is that exists; the speech guide is her one authored
paragraph about how she talks. An author finishes both before she says
anything.

## What promotion cannot write

Listed under `holes` on the generated sheet and printed at the end of a run:

1. **Her household as a file.** Her sheet names her people in prose; nothing
   writes the figures the scene director and the day's briefs read.
2. **Her flat.** No address, no room, no walk to a station. The world's map
   holds the first character's home and the school they share; it does not hold
   hers.
3. **Her own day beyond the week on her row.** School hours, a few fixtures, an
   after-school habit, a curfew and a handful of twists. A character who runs
   plans a day from more than that.
4. **What she has decided about him, about herself, and how each person in her
   world may sound.** Her config leaves all three paths blank, which every
   reader takes as "she has decided nothing yet"; a path naming a file nobody
   wrote is a wrong path and stops a boot.

## What must be hers before she boots

The order matters, and it is the whole of the checklist. Everything on it is
cheap before her first boot and expensive after: a save is not a document, and
what is written into it under the wrong answer stays there and drives her week.
The tool prints the last two lines of this itself when it finishes.

1. **Her fills** (`characters/<key>/fills.json`). Her ward, her station,
   her household, her friends, and every example a prompt fills from them. A
   boot with somebody else's fills on disk plans a whole day out of them --
   her walk to the wrong station, breakfast with the wrong brother, lunch with
   the wrong girls -- and that day is then in her save. Examples count: the
   day planner's example beat named two girls in her class, and the one call
   it fills plans for the circle that has never met them.
2. **Her sheet** (`characters/<key>/sheet.json`), and the five existence
   answers on it, because everything switchable follows from them.
3. **Her own household file** (`characters/<key>/household.json`), with the members she
   actually has and a `schedules` block for the ones who work. The module that
   draws the parents' day says nothing about a member the household does not
   name, and draws a working week only from that block; an absent block is not
   an absent parent, it is a parent invented from the module's defaults.
4. **Her own circle**, if she is to have one: `character.own_cast_file` and
   `own_cast_sheets_dir`, with a `self` block saying what she calls each of
   them (`docs/shared-world.md` §9).
4b. **Her own family, marked in the world's roster.** Her mother and her
   brother stay on the world's roster so that her own process can resolve
   them, and to everybody else in that world they read as two more people in
   the group. The row says whose: `"family": "<her roster key>"`, which
   `sim/roster.py:is_family` reads as family to her and to nobody else. Found
   by promoting a second person out of the same world and watching her come up
   holding a relationship meter on somebody else's mother.
5. **Her row in the world's cast file gets `agent: "<hub id>"`**, which is how
   her own process recognises the row as herself and how the owner's process
   knows to ask her instead of writing her.
6. **The world file's `self` block carries `key`, `role_id`, `role` and
   `agent`**, which is how the girl whose world she reads becomes a person on
   her roster rather than a name her fills use and nothing resolves.

Then boot her once and read the roster line and the boot notes: `[roster] N
people, M names; K of them her own` and no line saying a name means both
`self` and somebody else.

## What a promoted character still lacks before she is started

Beyond the four holes above, and beyond what `docs/shared-world.md` §7 already
lists (a second writer, a turn she speaks, a world clock both agree about):

- ~~**Nothing marks her roster row as running herself.**~~ Built since: a row
  marked `agent: <hub id>` is a person who runs herself, the owner's process
  plans her beats and writes none of her words, and the room asks her through
  the hub (`docs/peer-talk.md` §4b, `sim/rooms.py`).
- ~~**Her mechanisms do not reach her own voice.**~~ Built since, in two parts: `tomoe/cast_mechanisms.py:own_key` finds her file by her roster row
  rather than by her config name, and a file whose rows name no `persona`
  reader -- which is every file written for somebody who was cast -- renders
  the rows for the call where she speaks into her own block instead.
- ~~**The isolation check has no category for the world.**~~ Built since.
  `tools/isolation.py` now sorts a shared path into the machine's, a prompt
  with no person in it, **the world's**, or a leak. The world category holds
  the roster, the sheets, the mechanisms and the types file, the map, the
  places, the school calendar, the national holidays, the ward's events and the
  shared-world directory, and it applies only when both configs name the same
  `world_shared.id` -- a character with no world has those blanked at load, so
  one of them on her config is still a leak and is still reported as one. What
  is still a PERSON inside one of those files is named beside it rather than
  called clean: the map's `home` block is the first character's flat, and a
  peer's `note` and `stance` on the roster are that peer's inside and the first
  character's reading of them.
- **Her record does not reach the rooms she speaks in.** `sim/lore.py` is asked
  for a line by the path that builds her chat with him and by nothing else. A
  promoted character on somebody else's roster may have no chat with him at
  all, in which case her whole record is unreachable however good it is.

## She keeps her row

The roster belongs to the world, not to the first character. A promoted
character's row in `data/cast.json` and her sheet under `prompts/cast/` stay
where they are, and her config points at the same two, because the people who
have **not** been promoted still speak to her through them. Removing her row
would take her out of everybody else's day.

## Rena, promoted

Done for real, into the live tree, on the owner's word: *"I want
to promote Rena first. We will use Rena as a test bed to verify the mechanisms
of the codebook from which it is compiled."* She is the first character
promoted out of another character's cast and the first in `characters.json`
who is in a world somebody else owns. **She has not been started**: no save, no
scheduled task, and her roster row is not marked `agent`, so the first
character's process still plans her day and writes her words.

### What the tool wrote

    python tools/promote_cast.py Rena-chan --slug rena

`--slug` is new. The roster key is what the world calls her and carries
whatever the first character calls her by (`Rena-chan`); every file of a
character who runs is named after the short name, and an honorific in a config
filename and a scheduled task name is the roster leaking into the operator's
list. The key still defaults to the roster's.

Out came `characters/rena/sheet.json`, `characters/rena/fills.json` (75
tokens filled), `config_rena.json`, `prompts_rena/bible.md`,
`prompts_rena/style.md` and `rena.cmd`, and the registry row was appended to
`characters.json` because the owner had said promote her. Nine gauge baselines
moved off the mechanism's defaults, each with the behaviour sentence it came
from beside it and no letter anywhere.

### What was authored on top

Everything the tool cannot write, plus her own record, which nothing had asked
for before:

| file | what it is | how much |
|---|---|---|
| `characters/rena/records.json` | standing facts about her life, each with a `tier` and a `receipt` | 81 records, 11 kinds |
| `data/rena/timeline.json` | dated once-events from her birth to today | 34 events, 24 on a day, 10 bounded |
| `characters/rena/memories.json` | those events as things she can be reminded of | 30 memories |
| `characters/rena/triggers.json` | the phrases that reach either | 320 phrases over 111 rows |
| `data/rena/people.json` | what SHE holds about each person, and the one thing she has wrong | 10 people |
| `characters/rena/household.json` | her household as an economy, for her day planner and her director | four in a 3DK |
| `characters/rena/home.json` | her flat, room by room, for her scene director | 6 rooms, 5 places |
| `prompts/cast/keita.md`, `prompts/cast/miwa.md` | her brother and her mother as sheets, in Japanese | two, with rows on the roster |
| `data/rena/harness/` | one school day put to her, twelve steps | see below |

All four record files are written by `data/rena/build_record.py`, which holds
the tables and the receipts and can be re-run.

### What constrains all of it

Her own sheet, her roster row, her mechanisms file, the first character's bible
where it names her, and **what the first character's record already holds**.
The yukata festival at the end of August and the two hours she was kept
waiting, the four days she chased the photos, the grounding over a test score, her sister's fever and
the handwritten fever log, and the obi she promised to tie tomorrow night are
all read off the shared world (`data/worlds/tokyo/world.db`) and the first
character's save, read-only, rather than invented beside them. Thirteen records
and four events say `invented` in their own receipt, and the largest of those
is deliberate: her material names a mother, a brother and a sister and no
father, so the household file states the absence and puts one fact under it
that she has never been told.

### The two rows on the roster, and why they are dormant

Her brother and her mother are people in this world and now have rows in
`data/cast.json`. Two things make them unlike every other row:

- their `role_id` is not one of the five the machinery counts as family
  (`sim/roster.py:FAMILY_ROLES`), because a role_id is unique across a roster
  and those five are the first character's household; and
- they carry `dormant: true`, which is the field every walk over the cast tests
  before it plans a day, draws attention or opens the group chat. That is what
  keeps the first character's process from planning them or letting them into
  her chat, and it is the honest state: she has never met either of them.

The cost is that Rena's own process reads her own household as dormant too, so
her family reaches her day through `characters/rena/household.json` and her scene
director rather than through the roster. A roster has no way to say "somebody
else's household in the same world", and that is the next thing this route
needs.

### Three faults promotion turned up

Each was found by building her and reading the prompts.

1. **Her own mechanisms did not reach her own prompt.** `OwnMechanisms` keyed
   its file on `character.name`, which is `Rena`, and her file is
   `Rena-chan.json`. Fixed at the source (`tomoe/cast_mechanisms.py:own_key`),
   which finds the roster row by the two things a config states about her and a
   roster row also states. Her file also names no `persona` reader, because it
   was written for somebody who was cast; when a file has mechanisms and none
   of them names `persona`, the rows for the call where she speaks
   (`cast_turn`) are now her own block. 5,300 characters of her, where there
   had been none.
2. **Her record was built and never attached.** `sim/lookup.py` declares a
   `lore` wire; the resident program attaches it and this one never had, because
   the first character has no record and `App.lore` is None for her. It showed
   at her boot as `[wiring] built and not attached: lookup.lore`.
3. **A character with no account crashed the reflection role.** Two keys were
   added to `sensors/x_monitor._paths` and not to its empty-path branch, so
   asking what he had followed raised `KeyError` rather than returning nothing.
   One list of names now serves both branches.

### And the one that is not fixed

**Her record never reaches the rooms she actually speaks in.** `sim/lore.py` is
asked for a line only by `Persona._situation`, which is her chat with him;
`tomoe/exchange.py` does not contain the word. Rena has no chat with him at all,
so all 111 of her rows are unreachable in practice. `tools/lore_test_rena.py`
fires 16 of 16 on the right record and stays silent on 16 of 16, and none of the
twelve assembled prompts of her day carries a retrieved line. It is the first
thing to fix before she is started, and it is a change to the exchange.

### Proof

`data/retired/20260906_rena/REPORT.md`, and `data/rena/harness/OBSERVE.md` for
what to watch once she runs. `tools/isolation.py` now has the third category
`docs/shared-world.md` wanted: ten paths that are the WORLD's rather than a
person's, counted as shared-and-right when two configs name the same world id,
with the block inside each that is still one character's named beside it.

## Proof

`data/retired/20260906_promote/REPORT.md` has the run: one cast member promoted
into a temp directory, the App built on her the way `tools/existence_matrix.py`
builds a scratch character (console, no sensors, the logger stubbed, every model
call and every outbound connection refused), her system prompt and her carried
block rendered, and `tools/character_test.py --sheet`,
`tools/fills_check.py --config` and `tools/isolation.py --config` run on the
result.
