# Composing a character: the generic library and the character bundle

<!-- doc: plan -->

A plan to implement, not a survey. It says what the two layers are, where the
seam leaks today with a receipt for each, and the numbered steps that close
it. Every step names the files it touches, what done looks like, the check
that proves it, and how it stays idempotent when it is re-run after a partial
failure.

The reference for what is true now is `PROJECT.md`; the log of what happened
is `HISTORY.md`. Neither is edited by this plan.

---

## 1. The two layers, and the one rule

**The generic library** is everything that is the same for every character:
the mind and the relationship (`sim/`), her voice's assembly (`persona/`), a
body (`embodied/`), the clock and the shared world (`world/`), his machine
(`machine/`), the runtime (`scail.py`), the two programs (`tomoe/` for a
character with a world round her, `resident/` for one who lives on his
machine), and the mechanism prompts under `prompts/` and `tomoe/prompts/`,
which are instructions with the person taken out and character-shaped holes
left behind.

**The character bundle** is everything that is one person: who she is, where
she lives, who is around her, what her household earns, what she believes,
how she talks, what kind of thing she is, which model writes in her voice,
and which prompts she has rewritten rather than filled.

The rule the whole plan turns on:

> **A generic default may never be one character's file.** Where the library
> needs a person-shaped value it defaults to nothing, and a character who has
> not been given one either has that subsystem switched off or fails to
> start. A default that names a person is inherited silently by the next
> character, and silence is the failure mode this project cannot see.

That rule is already obeyed in exactly one place, and that place is the only
layer that has never leaked. The values that fill the holes in the shared
prompts are read from a file named per character (`character.neutral_file`),
and the default for that name in `config.py:DEFAULTS` is the empty string. A
character with no file of her own gets `(not established for this character)`
printed loudly, and `tools/fills_check.py` renders every role of every
registered character and fails on a hole that survives. Run today it reports
**every role of every character renders with no unfilled token** across all
four.

Every other person-shaped default in `config.py:DEFAULTS` names the first
character's file, and every one of them has leaked.

---

## 2. Where it leaks today

### 2.1 The root cause: defaults that are a person

`config.json` is generated from `config.py:DEFAULTS` and backfilled — the
merge takes DEFAULTS first and the file's value on top, and writes the merged
result back. A key a character's config does not carry is therefore filled in
from DEFAULTS on her first load and written into her file, where it looks
authored.

These defaults are the first character's own material:

| what it is | key | default |
|---|---|---|
| who is around her | `character.cast_file` | `data/cast.json` |
| their sheets | `character.cast_sheets_dir` | `prompts/cast` |
| her speech guide, both languages | `character.style_prompt`, `style_ja_prompt` | `prompts/style.md`, `prompts/style_ja.md` |
| how each person may sound | `character.voice_rules_file` | `characters/tomoe/voice_rules.json` |
| what she has decided about him | `character.beliefs_file` | `characters/tomoe/beliefs.json` |
| what she has decided about herself | `character.self_beliefs_file` | `characters/tomoe/self_beliefs.json` |
| who she is, as a prompt | `models.persona.prompt` | `prompts/bible.md` |
| her family as an economy | `world.household_file` | `characters/tomoe/household.json` |
| her map, her places, her school year | `world.geography_file`, `places_file`, `school_calendar_file` | the first character's |
| what is going round | `world.zeitgeist_file` | `characters/tomoe/zeitgeist.json` |
| what the people around her do, and their types | `cast.mechanisms_dir`, `cast.types_file` | the first character's world's |
| her save | `logging.db_path` | `data/world.db` |

Plus the first character's neighbourhood, hardcoded as data inside DEFAULTS:
the wards her local-news fetch reads (`config.py:2228`), the railway lines her
train board watches (`2314`, `2316`), the search terms her photo harvest uses
(`4597`, `4629`–`4641`), and the ~40 place words her scene classifier tests
against (`4713`–`4746`, `4763`–`4773`), which name Nerima, the Seibu Ikebukuro
line, Ikebukuro, Shakujii, Hikarigaoka, Toshimaen and eleven neighbouring
stations. Two browser profile directories name her as well
(`config.py:6137`, `6144`).

A character who is **not** in a world is saved by the blanking table
(`Config.WORLD_KEYS`), which empties the world's paths for her at load. A
character who **is** in a world is not saved by anything: she inherits the
first character's household, map, roster and sheets in full. That is the
fourth character's whole first day, and it is a property of the defaults, not
of her promotion.

### 2.2 Roster identity: she is on her own roster twice and the owner is not on it at all

Reproduced live against the fourth character's config, read-only:

```
[roster] 'れな' means both self and ringleader; keeping self       (and seven more)
[roster] 12 people, 99 names; 4 of them her own, from characters/rena/cast.json
role_of('Rena')      = 'self'
role_of('Rena-chan') = 'ringleader'
role_of('Tomoe')     = ''
```

Three separate faults in one table:

1. **Her own row in the world's roster is still a stranger.** The self row is
   synthesised from her config and prepended, so her name resolves to
   `self`; her person row in the world's file keeps its own role and its own
   aliases, which collide with hers eight times at every boot.
2. **The owner of the world is not a person on a reader's roster.** The
   world's own-line block sits at the top level of the roster file, not among
   the people, so a reader has no row for her, cannot resolve her name, and
   files everything she says as a stranger's. In the group chat already
   stored in the reader's save, seventeen turns are filed under three
   speakers of which one is unresolvable to her.
3. **The five family role ids belong to whoever owns the world.** A reader
   inherits `mother`, `father` and `sibling` pointing at the owner's parents
   and brother, while her own mother and brother sit under separate ids and
   are therefore not family to the code that asks. `sim/roster.py:FAMILY_ROLES`
   is a global set of five strings; `sim/rooms.py` and `roster.witnessed`
   both read it.

The own-line block is also keyed by the first character's name — `tomoe` at
the top level of the world's roster file, `self` in the reader's own file —
and the function that reads it is named after her (`tomoe/cast.py:tomoe_sheet`),
with a fallback that returns nothing at all for any future owner not named
that.

### 2.3 The save is seeded from the raw roster file, bypassing every rule

`sim/state.py:_seed_people` opens `character.cast_file` and takes its
`people` dict whole. It does not go through `sim/roster.py`, so it does not
see the reader's own file, does not drop her own row, and does not add the
owner. The meters are seeded once and never re-read.

The fourth character's live save, read-only, carries eleven relationship rows
and eleven matching sentiment rows: **herself** (as the owner's friend, at
closeness 45), the owner's rival and confidante, the owner's **mother, father
and brother** under the three family role ids, her own brother and mother,
her own two friends, and him. There is no row for the owner.

Fixing the roster alone does not fix this. The seed already ran.

### 2.4 The household is read with the first character's family keys hardcoded

`tomoe/briefs.py:household_brief` looks up members by literal key — `dad`,
`mom`, `kaito` — and prints labels to match. The fourth character's household
file names her people `mom`, `keita`, `shiori`, `father`, `grandmother`.
Rendered live, her household brief reads:

```
HER HOUSEHOLD (the same figures every time; money talk must agree with these):
  dad: ,  --
  mom: Kashiba Miwa, 41 -- part time, registered sales assistant …
  grandmother: Kashiba Fumie, 72 -- …
```

An empty father line for a girl whose household file states the absence of a
father as its central fact, no brother, and no little sister anywhere — while
her brother and her sister are both named in her own records. Every
world-facing call reads that block.

The reader is also reached through a default: `getattr(config.world,
"household_file", "characters/tomoe/household.json")`. And two of the four characters
still name the first character's household file in that key today; only the
blanking table stops it reaching them.

### 2.5 What the guards cannot see

The name check that runs in smoke (`tools/character_names.py`) reports
"shared code names nobody" and is right about what it looks at: it tokenises
`scail.py`, `config.py`, `llm.py`, `store.py`, `logger.py`, `netwatch.py`,
`singleton.py` and every `.py` under `sim/`, `persona/`, `embodied/`,
`world/`, `machine/`, drops comment and docstring lines, and matches whole
words against a list of names built from the character sheets and the roster
files.

What it does not look at:

- **Place names are not in its list at all.** The list is built from the
  `name.*` fields of the sheets and the roster rows, so no ward, station,
  line, school or neighbourhood is ever searched for.
- **`prompts/` is scanned only for the seven dialect words**, never for names
  or places.
- **`prompts_asumin/`, `prompts_rena/`, `prompts_yukarin/` are never
  scanned.**
- **`tools/`, `channels/`, `sensors/`, `talkapp/`, `car/` are never scanned.**
- **Only `*.py` is globbed**, so no `.html`, `.json`, `.txt` or `.md` inside
  a scanned directory is seen.
- A name preceded or followed by a word character escapes the boundary, which
  is why a profile path naming her in DEFAULTS was invisible (the path that
  showed it is `F:/Chrome_Profiles/SCAIL_tomoe` now, and DEFAULTS carries none).

Three live findings it therefore misses, each verified:

- `embodied/situation.py:485`, `486`, `488` — the shared body layer hands
  every embodied character three named stations on the first character's
  commute as her own lived experience: *"she got a seat at Ekoda"*, *"she
  moved cars at Ekoda"*, *"someone's backpack in her back the whole way from
  Sakuradai"*.
- `talkapp/app/index.html:1691` — the hub serves all four characters and the
  story view labels **every** character's own turns with the first
  character's name: `esc(it.me ? "Tomoe" : it.who)`.
- `tools/devoice.py:52` — a live model instruction that opens *"one fifteen
  year old girl, Koga Tomoe. She is from Fukuoka, lives in Nerima and goes to
  school in Ikebukuro"*, in a tool any character's process can call; and
  `tools/night_review.py:95`, `102`, where the fallbacks for an unnamed
  speaker are the first character's name and her friend's.

The prompt-leak scanner (`tools/prompt_leaks.py`) exists and would catch the
prompt-side of the third; it is not run by smoke.

Two more guards have a blind spot worth naming. The one that proves the
shared prompts render back unchanged (`tools/neutral_gate.py`) compares the
first character's rendering byte for byte against a kept baseline — so an
**untokenised** first-character literal in a shared prompt passes trivially,
because it renders back identically. And the matrix that builds forty kinds
of character (`tools/existence_matrix.py`) builds each of them from a copy of
the first character's config with only the identity block rewritten: it
proves every kind of character *builds*, and by construction cannot see a
leak.

### 2.6 The four characters, layer by layer

`composed` = written from her own material into her own place. `inherited` =
the value came from a default or a clone that names somebody else.

| layer | first character | second | third | fourth (promoted) |
|---|---|---|---|---|
| identity block in her config | authored | generated by a tool of her own | generated by a tool of her own | generated by the promotion tool |
| what kind of thing she is | her sheet | her sheet | her sheet | her sheet, with a reason per answer |
| values for the prompt holes | her own file | her own file | her own file | her own file, generated |
| her voice and speech guide | hers | hers | hers | seeded from her cast sheet, marked as a seed |
| the other role prompts | the library's | 17 rewritten, rest the library's | 6 rewritten, rest the library's | none rewritten |
| who is around her | hers | her own file | her own file | **the world's roster, with herself on it and the owner absent** |
| her own circle | n/a (she owns the world) | n/a | n/a | her own file, hand-authored after promotion |
| her household as an economy | hers | **names the first character's file, saved only by blanking** | **names the first character's file, saved only by blanking** | hers, hand-authored; read with the first character's member keys |
| her flat | in the world's map | her own file | her own file | her own file, hand-authored |
| what she believes | hers | hers | hers | blank on purpose |
| her save | hers | hers | hers | **seeded from the world's roster: herself, the owner's parents and brother** |
| where her files live | `data/` root | `data/` root, name-suffixed | a directory outside `data/` | a directory under `data/` |

The last row is its own problem: four conventions for the same idea. There is
no single place that is "everything that is this character", so there is
nothing a check can point at and say *this and only this is hers*.

---

## 3. The system

### 3.1 A character is a bundle plus the library

One directory per character, `characters/<key>/`, holding everything that is
her and nothing that is not. At the repository root rather than under `data/`,
because `data/` is where the bot's own state and caches live and a bundle is
authored input; and because the operator's register is already
`characters.json` at the root, and a bundle is that row expanded.

```
characters/<key>/
  bundle.json         her key, name, hub id, program, world and side of it,
                      launcher, task, the command-line pattern, and the
                      roles whose model differs from the default
  sheet.json          what kind of thing she is, her temperament, her
                      roster identity, the holes nobody has filled yet
  fills.json          the values for the character-shaped holes in the
                      library's prompts
  household.json      her family as an economy
  home.json           her flat, room by room
  cast.json           the people who are hers
  cast/               their sheets, in their language
  beliefs.json        what she has decided about him
  self_beliefs.json   what she has decided about herself
  voice_rules.json    how each person around her may sound
  records.json  memories.json  triggers.json  timeline.json
  zeitgeist.json  taste.json
  prompts/            only the role files she has rewritten, plus her own
                      voice (bible.md) and her speech guide (style.md)
```

Anything absent is absent, not defaulted. A subsystem whose file she has not
got is either switched off by her existence answers or refuses to start.

The two files that already work this way keep working: her sheet and her
fills move into the bundle as `sheet.json` and `fills.json`, and the
generated config points at them there.

### 3.2 One tool, two verbs

`tools/new_character.py compose <key>` reads `characters/<key>/` and the
library and writes, in this order:

1. `config_<key>.json` — from `config.py:DEFAULTS`, with the machine's
   settings and secrets merged in memory, every person-shaped key pointed at
   the bundle, and every role whose model or prompt the bundle overrides
   rewritten.
2. `prompts_<key>/` — a copy of `characters/<key>/prompts/`, so the running
   tree keeps the shape it has today and the bundle stays the source.
3. Her row in `characters.json`.
4. `<key>.cmd.next` beside the launchers, never `<key>.cmd` over a running
   process.
5. An **empty** save at her database path, seeded from her sheets: her
   gauges at her retuned baselines, her relationship and sentiment meters
   from her roster as her roster resolves it, her beliefs from her own files,
   her records from her own timeline. Never a copy of another character's
   save.

`tools/new_character.py verify <key>` builds her whole App on a scratch save
with the model and the network refused, renders everything she would say, and
fails on any of:

- a placeholder that survives in any role prompt her existence keeps;
- a path-shaped value in her config that is neither under her bundle, nor on
  the machine's list, nor on the world's list;
- a name, place, household member or roster key belonging to any **other**
  registered character, appearing in her rendered prompts or in her seeded
  save;
- her own key resolving to anything but herself on her roster, or an alias
  collision logged during the build;
- the owner of her world absent from her roster, when she is in a world she
  does not own;
- a relationship meter on a person who is neither hers, nor the owner, nor
  him;
- an existence answer in her config that disagrees with her sheet.

Promotion of somebody on the roster becomes: **write a bundle**. The
promotion tool keeps everything it is good at — deriving her fills from her
cast sheet and her mechanisms, moving her gauge baselines off the defaults
with the behaviour sentence beside each, computing her birth window from her
age and the school intake, seeding her voice and her speech guide from her
own paragraph — and its output becomes `characters/<key>/` rather than six
files scattered across the tree. Composition is then the same one tool for
her as for a character written from scratch.

### 3.3 The rule for a prompt she has rewritten: replace or slot, never prepend

Three kinds of prompt, three rules.

**Her voice and her speech guide are replaced, and there is no generic
version.** There is no such thing as a default bible. The keys that name them
default to nothing, and composition fails if the bundle has no file. Today
they default to the first character's, which is how a character with no
prompt directory of her own would speak as her.

**A mechanism prompt is replaced whole or not at all.** These files are one
instruction with an answer schema at the end; a paragraph bolted on the front
leaves the body still saying the old thing underneath it, and nothing can
check which one the model obeyed. The project already settled this argument
when it retired the tool that rewrote prompts by substitution: what is
character-bearing in a mechanism prompt is the psychology written into it,
not the proper nouns, and porting one is reading and rewriting. So a bundle
file of the same name replaces the library file for that role, and every role
the bundle does not carry keeps pointing at the library's, which is filled
from her values.

**A change smaller than a rewrite is a named place in the library file.** The
mechanism already exists: a library prompt may carry a marked slot, and a
character's fills file may put one paragraph in it. Three are in use today.
This is the route for "she needs one rule added here", and it is preferable
to a rewrite because the library file stays one file and the difference stays
one paragraph that can be read on its own.

Prepending is rejected for a second reason as well. The provider caches a
byte prefix; the assembled prompt is deliberately split so that what changes
once a day sits in front of what changes during a day. A per-character
paragraph prepended to a shared file moves every byte behind it, and the
whole file is billed again on every call.

### 3.4 What already is this system and stays

- The values for the prompt holes, their per-character file, the check that
  renders every role of every character and fails on a surviving hole, and
  the gate that proves the first character's rendering is byte-identical to
  the original. This layer is the model for the rest.
- The declaration of what kind of thing a character is, the table that maps
  every switchable subsystem to the property it needs, the refusal to start
  when a subsystem is unassigned, and the blanking of the world's paths for a
  character with no world.
- The classification of a shared file into the machine's, a prompt with no
  person in it, the world's, or a leak.
- The two tables of how she sees him, one per program, and the fork in the
  shared prompts.
- The split of her prompt into what changes once a day and what changes
  during it, and the single assembly both rooms build from.
- The two roster files, one for the world and one for her own people, and the
  question of whose a person is.
- The matrix that builds every kind of character the sheet can declare.
- The register, the restarter, the staged launcher, and the refusal to
  restart when the build check fails.

### 3.5 What moves

- Her sheet and her values-for-holes file move from two places under `data/`
  into her bundle.
- The third character's material moves from a directory outside `data/`, the
  second character's from name-suffixed files at the `data/` root, and the
  fourth character's from a directory under `data/`, all into bundles.
- The promotion tool's output moves from six scattered files to one bundle.
- The seeding of her relationship meters moves from reading the roster file
  raw to asking the roster layer.
- The reading of her household moves from three hardcoded member keys to
  whatever her file names.

### 3.6 What is new

- The bundle directory and its manifest.
- The compose verb and the verify verb.
- The empty save seeded from her sheets.
- The rule in the roster layer that says which row is her and who the owner
  of a world she reads is.
- A family flag on a roster row, so the five family role ids stop being the
  world owner's by definition.
- The extension of the name check to places, to the prompt directories, and
  to the file types it currently cannot see.

---

## 4. The steps

Each step is independently landable and independently checkable. The order is
chosen so that no step depends on a later one, and so that the two steps that
change live behaviour for a running character come after the checks that
would catch a mistake.

Every step that edits a file by string anchors on a whole line with its
indentation, copies the file to `data/retired/<timestamp>_<step>/` first when
the edit is a span rather than a unique line, and skips its own edit when the
new text is already present — the re-run guard is "the old text is in the new
text and the new text is already in the file".

Run `python tools/smoke.py` after every step. A step is not done until smoke
is clean.

---

### Step 1 — Stop the library defaulting to a person

**Files:** `config.py` (the defaults), `config.json`, `config_yukarin.json`,
`config_asumin.json`, `config_rena.json`.

Set every person-shaped default in `config.py:DEFAULTS` to the empty string:
the file of who is around her, their sheets directory, both speech guides,
the file of how people sound, both belief files, the prompt that is her voice,
her household file, her map, her places, her school calendar, what is going
round, her taste sheet, the directory of what the people around her do, their
types file, and her save's path.

Before changing each one, confirm the four live configs already carry the
value explicitly. They do — the backfill wrote it into every one of them on
first load — so **no running character changes behaviour**. What changes is
that the fifth character can no longer inherit.

Leave the neighbourhood data in the defaults for now; step 9 moves it.

**Done looks like:** a config generated from the defaults alone names no file
belonging to a person.

**Check:** a new test, `tools/defaults_person_test.py`, added to smoke: build
a config from the defaults with nothing merged in, run the path finder that
the isolation check already uses over it, and fail if any path-shaped value
is non-empty and is not under the machine's or the mechanism prompts'
prefixes. Also confirm the four live configs are byte-identical to their
pre-step selves except for the backfill's key order.

**Idempotent because:** the edit is a value replacement anchored on the whole
line including its indentation, skipped when the value is already empty.

---

### Step 2 — Refuse to start on a missing person-shaped file for a subsystem that is on

**Files:** `config.py`.

Add a table beside the existing one that maps a switchable section to the
existence property it needs: for each person-shaped key, the section that
reads it. At load, after the existence answers have switched sections off and
the world's paths have been blanked, fail with a message naming the key, the
section and the character if the section is on and the key is empty, or if
the key names a file that is not on disk.

The distinction the project already draws holds: an empty path is a state the
config produces on purpose and every reader treats it as no data at all; a
path naming a file that is not there is a wrong path and stops the boot. This
step adds the third case — an empty path under a subsystem that is running.

**Done looks like:** a character whose household section is on and whose
household file is empty does not boot.

**Check:** the check that builds a character with every person-shaped path
blanked at once (`tools/blank_paths.py`) still passes, because it blanks the
paths of subsystems the sheet has already switched off. Add a case to it that
blanks one path while its section is on, and assert the boot refuses with the
key named.

**Idempotent because:** the table is a module-level dict; the step inserts it
only when the name is absent from the file.

---

### Step 3 — The roster knows which row is her and who owns the world she reads

**Files:** `sim/roster.py`, `data/cast.json`, `characters/rena/cast.json`,
`characters/rena/sheet.json` (until step 6 moves it), `tomoe/cast.py`,
`tomoe/exchange.py`.

Three changes, at the source.

**Her own row.** Her sheet gains a roster identity block naming her key in
the world's roster file. The table builder drops that person row from the
people it loads and merges its Japanese name, reading, aliases and what each
person calls her into her own row, so nothing is lost and nothing collides.
For a character who owns her world the block is absent and nothing changes.

**The owner as a person.** The own-line block at the top of a roster file
becomes a person on the roster of anyone who reads that file and did not
write it, under a role id her sheet names. Rename the block's key from the
first character's name to `self` in the world's roster file, keep reading the
old key as a fallback for one release, and rename the function that reads it
to say what it does rather than who she is.

**Family.** Add an optional flag on a roster row marking that person as this
character's family. The five role ids stay as the default for a row without
the flag, so the first character is unchanged; a reader's own file marks her
own mother and brother, and the owner's parents stop being anybody's family
but the owner's.

**Done looks like:** built against the fourth character's config, her own key
resolves to herself, the owner's name resolves to a person, no alias
collision is logged, and her family is her own.

**Check:** extend the world-reader test with four assertions — her key
resolves to herself; the owner resolves to a person with a role id; the boot
produces no line saying a name means two things; the people the code counts
as her family are hers. Take the reader's config from the register rather
than hardcoding one, so a second reader is covered.

**Idempotent because:** the roster identity block is read with a default of
absent; renaming the own-line key is a data edit guarded on the new key not
already being present; the family flag defaults to the old behaviour.

---

### Step 4 — The meters are seeded through the roster, and a save already seeded wrong is repaired

**Files:** `sim/state.py`, `sim/repairs.py`, `tools/second_world_retire.py`
or a new pass beside it.

Change the seeding of her relationship meters to ask the roster layer for
everyone rather than opening the roster file and taking its people dict. That
single change gives it her own row dropped, her own people included, the
owner present, and the blank-path case already handled.

Add a one-off repair, marked in the save the way the others are, that
reconciles an already-seeded set of meters against the roster as it now
resolves: drop a meter on a person the roster does not have, drop the meter
she has on herself, add a meter at the sheet's opening values for a person
the roster has and the meters do not. Write the old rows to
`data/retired/<timestamp>_<name>/` before touching them, as every repair
does.

**Done looks like:** the fourth character's meters name her own four people,
the owner, and him — and not herself, not the owner's parents, not the
owner's brother.

**Check:** a reader of the save prints the meter keys beside the roster's own
keys plus the owner plus him, and the two lists are equal. Assert it in the
world-reader test on a copy of her save.

**Idempotent because:** the repair is gated on its own marker key in the
save, like the nine that already exist; re-running it after a partial failure
finds the marker and does nothing, and the reconciliation itself is written
as a comparison against the roster rather than as a list of deletions, so
running it twice on an unmarked save produces the same result.

---

### Step 5 — The household is read as the file names it

**Files:** `tomoe/briefs.py`, `tomoe/family.py`.

Replace the three hardcoded member lookups with a walk over whatever the
household file's members contain, taking each member's stated relation as its
label. Remove the default that names the first character's household file
from the reader; an empty path is no household, which step 2 now makes an
error for a character whose household section is on.

Do the same for the two keys the day-planning half reads (the family's
schedules and their vehicle): absent is absent, not missing.

**Done looks like:** the fourth character's household brief names her mother,
her brother, her sister and her grandmother, states the absence of a father
as her file states it, and contains no empty line.

**Check:** a new case in the family test that renders the household brief for
every registered character whose household section is on and fails on a line
with an empty name, on a member in the file that the brief does not mention,
and on a label the file does not contain.

**Idempotent because:** it is a rewrite of one function body, anchored on the
function's own definition line, skipped when the new body is already there.

---

### Step 6 — The bundle: one directory per character

**Files:** new `characters/<key>/` for all four; `config.json`,
`config_yukarin.json`, `config_asumin.json`, `config_rena.json` repointed;
`tools/isolation.py` gains the bundle prefix; the old locations moved to
`data/retired/<timestamp>_bundles/`.

Move, per character: her sheet and her values-for-holes file into the bundle
as `sheet.json` and `fills.json`; her household, flat, own roster, own
sheets, beliefs, self-beliefs, voice rules, records, memories, triggers,
timeline, what is going round and her taste sheet into the bundle under their
plain names; her prompt directory into `characters/<key>/prompts/`, with
`prompts_<key>/` kept as the generated copy the running config points at.

Write `bundle.json`: her key, name, hub id, program, the world she is in and
whether she owns it, her launcher, her scheduled task, the command-line
pattern her process is found by, and the roles whose model differs from the
default. That is the register row plus the two facts about her world plus her
model choices, in one place, and the register row becomes a projection of it.

Add the bundle prefix to the isolation check's classification, so
`characters/<key>/` is hers by construction and anything of hers outside it
is reported.

**Done looks like:** every path in every character's config points either
into her own bundle, at the machine's shared files, at the mechanism prompts,
or at the world she shares — and nowhere else.

**Check:** run the isolation check for each registered character against each
other one, not just against the first. Extend the register reader to fail on
a registered character with no bundle directory, and on a bundle whose
manifest disagrees with her row.

**Idempotent because:** each move is "copy into the bundle if the bundle does
not have it, then repoint the config key, then retire the old file", and each
of the three tests its own postcondition first. A partial run leaves the old
file in place and the config unrepointed, which is the starting state for that
file.

---

### Step 7 — Compose

**Files:** new `tools/new_character.py`; `tools/promote_cast.py` retargeted
to write a bundle; `characters.json`.

Write the compose verb as described in section 3.2. Order of writes matters:
the config first, because everything else is checked against it; then the
prompt directory; then the register row; then the staged launcher; then the
save last, because a save is the only artefact that cannot simply be
overwritten on a re-run.

Retarget the promotion tool: it keeps every derivation it does today and
writes them into `characters/<key>/` instead of into six places. Its own
list of what it cannot write stays, and moves onto the bundle's sheet as the
holes it already records.

**Done looks like:** composing each of the four existing characters from her
bundle produces a config byte-identical to the one she runs on today, apart
from key order.

**Check:** a compose-and-diff mode that writes to a temporary directory and
reports the difference against the live files, run for all four in smoke. A
difference is a finding, not a failure, until the four are clean; then it
becomes a failure.

**Idempotent because:** every write is to a path derived from the key and is
a full overwrite of a generated file, except the register row (matched on the
key and replaced in place, appended only when absent), the launcher (staged
as the `.next` file the restarter moves), and the save (created only when the
path does not exist; an existing save is left alone and named).

---

### Step 8 — Verify

**Files:** new verify verb in `tools/new_character.py`; `tools/smoke.py`.

Build her App on a scratch save with the model and the network refused, the
way the matrix already does; render her system prompt, what she carries, and
every role prompt her existence keeps; then run the seven assertions in
section 3.2.

The leak assertion is the one worth building carefully. The material of every
**other** registered character is already computable — the check that reads a
run's log for one character's material appearing in another's output builds
exactly that set from a character's sheet, roster, beliefs, voice rules,
fills, voice files, cast sheets and world files. Invert it: build that set
for every other character, subtract the world they legitimately share and the
machine's, and search the rendered prompts and the seeded save for what is
left.

Run verify for every registered character in smoke, and make it fail rather
than report.

**Done looks like:** verify passes for all four, and fails on a deliberately
broken bundle (one whose household file is another character's).

**Check:** the deliberate break, run once by hand and recorded in the step's
report; then verify in smoke for all four.

**Idempotent because:** it writes nothing outside a temporary directory.

---

### Step 9 — Every literal that should be a fill

**Files:** listed in section 5.

Move each literal named there out of shared code, shared prompts and shared
tools, into either a character's fills file or her bundle's own data. Where
the value is a list the library needs (the wards a news fetch reads, the
lines a train board watches, the search terms a photo harvest uses, the place
words a scene classifier tests), it becomes a bundle file and an empty
default, and the subsystem that reads it is switched off for a character
without one.

**Done looks like:** the shared body layer names no station, the shared app
names no character, and the two shared tools name none.

**Check:** step 10's extended name check.

**Idempotent because:** each is a single-line value replacement guarded on the
new text not already being present.

---

### Step 10 — The name check sees what it cannot see today

**Files:** `tools/character_names.py`, `tools/smoke.py`.

Four extensions:

1. **Places.** Add to the searched list every place name in every
   character's bundle — her home area, her school area, her line, her
   stations, her ward, her school — from the same files the names come from.
2. **Directories.** Add `channels/`, `sensors/`, `talkapp/`, `car/` and
   `tools/` to the scanned set. Keep the two program packages exempt, since a
   program is one character's by design; report a name from a character whose
   program is not that one.
3. **File types.** Glob `.py`, `.html`, `.js`, `.txt`, `.md` and `.json`
   inside the scanned directories, not `.py` alone.
4. **Boundaries.** Match a name inside an identifier as well as beside one,
   and report it separately so a false positive can be ruled out by reading
   rather than by the regex silently missing it.

Add the prompt directories — the shared one and each character's — to the
scan, for names as well as for dialect words. Add the prompt-leak scanner to
smoke.

**Done looks like:** the extended check run before step 9 names every literal
in section 5, and run after it names none.

**Check:** that before-and-after, recorded in the step's report.

**Idempotent because:** the lists it extends are module-level tuples; each
addition is guarded on the entry not already being present.

---

### Step 11 — The matrix builds a stranger, not the first character in a costume

**Files:** `tools/existence_matrix.py`.

Build each of the forty kinds from a scratch **bundle** — a minimal set of
files under a temporary directory, with a name and a place that belong to
nobody — composed by the tool from step 7, rather than from a copy of the
first character's config with the identity block rewritten. Then run the leak
assertion from step 8 on each: a character built from a bundle that names
nobody must render prompts that name nobody.

**Done looks like:** forty of forty build, and none of them says a name.

**Check:** the matrix in its strict mode, in smoke, as it already is.

**Idempotent because:** it writes only into a temporary directory.

---

### Step 12 — The documents

**Files:** `tools/docs_src/np_*.md` and the assembler, `CONFIG.md` through
the same assembler, `docs/README.md`, `docs/promotion.md`,
`docs/shared-world.md`, `HANDOVER.md`, `HISTORY.md`.

The reference gains the bundle and the compose tool as a module entry with
its config, its store, its invariants and its history pointer. The promotion
document becomes the front end that writes a bundle, and its list of what
promotion cannot write becomes the bundle's list of holes. The shared-world
document's account of a reader's own circle gains the roster identity rule.
The index gains this plan's successor, if one is needed. The handover header
carries the running state. `HISTORY.md` gets one dated entry per landed step,
under the section number the step belongs to.

**Done looks like:** the reference describes the system as built, and no
dated note has been written into it.

**Check:** the documentation checker, and the assembler's own count of
configuration sections as the canary that no defaults edit ate a span.

---

## 5. Every literal that should be a fill

Verified by reading, with the file and line. `(a)` is a leak to fix, `(b)` is
legitimately one character's own material in her own place, `(c)` is a
comment or docstring — left alone, but listed because the extended name check
will report them and a reader needs to know they are expected.

### The shared body layer — the most serious, and no guard can see it

| file:line | literal | why |
|---|---|---|
| `embodied/situation.py:485` | `Ekoda` | a station on the first character's line, in a live table of what happened to her on the train |
| `embodied/situation.py:486` | `Ekoda` | the same |
| `embodied/situation.py:488` | `Sakuradai` | the station one stop from the first character's home |

Every embodied character in any city gets these three sentences as her own
experience.

### The shared messenger

| file:line | literal | why |
|---|---|---|
| `talkapp/app/index.html:1691` | `Tomoe` | the hub serves four characters and labels every character's own turns with the first character's name |

### The shared defaults, as data

| file:line | what it is |
|---|---|
| `config.py:2228` | the wards the local-news fetch reads |
| `config.py:2314`, `2316` | the railway operator and the lines the train board watches |
| `config.py:4597` | the search terms the photo harvest uses |
| `config.py:4629`, `4630`, `4632`, `4634`, `4638`, `4639`, `4641` | the same, by kind of place |
| `config.py:4713`–`4746` | about forty place words the scene classifier tests against |
| `config.py:4763`, `4765`, `4772`, `4773` | the same, in the classifier's own branches |
| `config.py:6137`, `6144` | two browser profile directories named after the first character |

### The shared tools

| file:line | literal | why |
|---|---|---|
| `tools/devoice.py:52` | a live model instruction naming the first character, her home town, her ward and her school's ward | any character routed through it is corrected into her |
| `tools/night_review.py:95` | `"Tomoe"` as the fallback when no speaker is named | |
| `tools/night_review.py:102` | `"Rena-chan"` as the fallback when no friend is drawn | |
| `tools/absurd.py:367` | a filter on the end of the first character's given name in kanji | live code |
| `tools/local_events.py:11`, `12`, `68`, `70`, `84`, `85`, `93`, `96`, `201`, `209`, `210` | the first character's ward's feed, her address, her line and six neighbouring wards | this tool has already run inside the fourth character's process |
| `tools/zeitgeist.py:6` | the first character's age and ward, in the instruction | |
| `tools/chat_project.py:46`, `48`–`52`, `114`, `124`, `175` | the first character's whole roster as fixture values | |
| `tools/reasoning_ab.py:31`, `34`, `36`, `38`, `40` | her cast as the labels of the comparison cases | |
| `tools/agent_seam_test.py:46`, `48` | her friend and her rival as module constants, in a test smoke runs for every character | |

### The shared prompts

Scanned exhaustively for every character's name, every family member's name,
the ward, the line, the stations, the school area and the dialect markers:
**no shared mechanism prompt names anybody.** The only hits are the three
files that are a character by definition (her voice, her speech guide in each
language) and the directory of the people around her — all sanctioned, all
`(b)`.

What is still hardcoded in a shared prompt is her *situation* rather than her
name, sitting beside tokens that were already made:

| file:line | literal |
|---|---|
| `prompts/schedule.txt:1` | her school level and her city, next to a token for her home area |
| `prompts/schedule.txt:4` | a shopping complex in the first character's nearest big station, a crepe stand in a named district, a convenience store chain |
| `prompts/import_day.txt:1` | her age and her city, next to a token for her full name |
| `prompts/coherence.txt:1` | her city |
| `prompts/vision_photo.txt:1` | her city |
| `prompts/vision_x.txt:1` | her city, and an assumption about the language of the accounts |
| `prompts/him_profile.txt:1` | her city |

One benign hit worth recording so nobody removes it: `prompts/lookup_gist.txt:3`
names a real voice actress as a worked example of family-name-first ordering.

### Comments and docstrings in shared code

Around sixty, in `sim/` (`commitments`, `state`, `roster`, `memory`,
`sentiment`, `voicecheck`, `reflect`, `recall`, `reconcile`, `spiral`,
`director`, `peers`, `ick`, `ledger`, `records`, `repairs`, `self_memory`,
`textutil`, `timeline`, `him_profile`, `anime_sense`, `anime_kb`,
`receipts`), one in `persona/persona.py`, one in `scail.py`. Every one is a
failure history or a worked example, which is what the comments in this
project are for. `(c)` — leave them, and have the extended check report them
in a separate list so the two are never confused.

`world/`, `machine/`, `channels/`, `store.py` and `llm.py` name nobody at
all, in code or in comment. So does the whole of `resident/`.

---

## 6. Trade-offs, and the recommendation

**Where to put a bundle: a directory at the root, a directory under `data/`,
or leave the four conventions alone.** Under `data/` is the smallest move and
matches what the promoted character already has, but `data/` is where the
saves, the caches, the fetched feeds and the retired copies live, and a rule
of the form "everything under this prefix is hers" cannot be stated there
without listing exceptions. Leaving four conventions alone costs nothing
today and costs the whole of section 2 again on the fifth character.
**Recommended: a directory at the root**, because the property that makes the
whole plan checkable — one prefix that is hers and nothing outside it — is
worth the move, and because the operator's register already sits at the root
and a bundle is one of its rows expanded.

**Replace a role prompt, or prepend to it.** Prepending is cheaper to author
and lets a character adjust one rule without owning the whole file. It is
rejected because the library file underneath still says the old thing, so
neither a reader nor a check can tell which instruction the model followed;
and because the cached byte prefix means a prepended paragraph re-bills the
whole file behind it on every call. **Recommended: replace whole, or add one
paragraph in a named place the library file provides** — the second of which
already exists and is used three times.

**Empty the person-shaped defaults, or keep them and add a check.** Keeping
them and checking is less disruptive and would catch the same faults at boot.
It is rejected because it leaves the wrong value in the file: a character's
config would still carry another character's household path, and every reader
of that config — the isolation check, a person reading the file, the next
tool — would have to know that the value is inert. **Recommended: empty
them**, verified first against the four live configs so that no running
character changes.

**Repair the already-seeded meters, or leave them and let them drift.**
Leaving them is defensible for a young save. It is rejected because the
promoted character's meters currently include a relationship with herself,
which no later correction reaches: the seed runs once and is never re-read.
**Recommended: the marked one-off repair**, with the old rows kept, like the
nine repairs already in the loop.

**Do steps 1 to 5 first, or the bundle first.** The bundle is the larger
idea, but steps 1 to 5 are the five faults that are live right now and each
of them is small, checkable and independent. **Recommended: 1 to 5 first**,
then the bundle, then compose and verify, then the literals and the extended
check, in that order — the check comes after the fix so its before-and-after
is the proof.

The one thing to do first if only one thing is done: **step 1**. Four of the
five faults in section 2 are a default that is one character's file, inherited
by the next character in silence.
