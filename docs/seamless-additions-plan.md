# Seamless additions: what it takes to add or promote a character today, and the work that makes it one step

<!-- doc: plan -->

A plan, not a reference. What is true now is in `PROJECT.md` section 20 and in
`docs/bundle.md`, `docs/promotion.md` and `docs/shared-world.md`; dated notes
are in `HISTORY.md`. This document says where a new character or a promoted
cast member still costs hand work or still runs into a wall the design has not
removed, and the numbered work that closes each, with the check that proves it.

## 1. Where it stands

The measure is the throwaway promotion recorded under
`data/retired/20260907_1100_promotion_proof/` (Hinako, a cast member of the
first character, promoted into a bundle under that directory as a reader of the
world `tokyo`, composed, verified and booted with the model stubbed; nothing
registered, nothing started). Every check passed: her own key resolves to her,
the owner is a person on her roster, no alias names two people, every meter is
on somebody her roster has, every path in her config is her bundle's or the
world's or the machine's, no other registered character's name or place is in
her prompts or her seeded save, her schedule call carries none of them, and she
runs none of the eight sections that write the world and none of the
twenty-five that read his machine.

**Every one of those checks is STRUCTURAL, and the paragraph above was read as
saying more than it says.** They were made on one process, on a scratch save,
with the model stubbed and the clock standing still. What they answer is
whether a bundle composes into a character who builds and whose material is
her own. What they cannot answer is what happens when she runs for a day
beside the character who keeps her world, and that is where every fault
actually found lived: the owner's day planner deleting every beat it planned
for her, so she opened nothing for two days and the refusal spun in the log at
one line every five seconds; every relayed turn filed in an owner-side queue
under the owner's name, so her copy of the group chat stopped a day short and
three of its turns were in the wrong mouth; a silence she chose read as a
three-minute timeout; the phone-app open firing fifty-one times for a character
whose sheet says she sees nothing of him; two gauges whose owner section is off
sitting in her store with something moving one of them; the headings of what
she carries defining her against a man she has no chat with; residue about him
left in her save; her news picker giving her a commute on a line her own map
does not reach; and her diary never firing. The evidence is
`data/retired/20260907_203328_rena_audit/REPORT.md` and the repairs are
`data/retired/20260907_210559_rena_fixes/REPORT.md`.

Two tools now cover what the structural checks could not, and
`docs/agent-character.md` is the reference built from them: the runtime
contract as numbered invariants, each with the check that proves it.
`tools/agent_rehearsal.py` lives one day of her clock with BOTH processes up on
copies of the live saves, the model, the network and the browser refused and
the hub in the process, and asserts the seam; it runs inside
`tools/new_character.py` in its verify mode and inside `tools/smoke.py` for
every registered character who reads a world she does not keep.
`tools/agent_audit.py` asks fourteen mechanical questions of a character who is
already running, read-only. Neither of them says anything about whether she is
believable, which is still a read and still costs an hour.

What the promotion tool derived on its own: her bundle manifest, her sheet with
the existence answers, her fills, her gauge baselines with the behaviour
sentence beside each, her birth window, her bible and speech guide seeded from
her own sheet and voice line, her roster identity, an empty save seeded from
her roster (three meters). Then compose wrote her config and her prompt
directory and verify ran the checks.

What still had to be done by hand, in the order the tool prints it:

| step | who does it | why the tool cannot |
|---|---|---|
| her household as a file (`household.json`) | author | her sheet names her people in prose; the figures the director and the day's briefs read are not in it |
| her map (`map.json`) | author | no address, station, walk or ward on a cast row; the school and the ward's public places are copied from the owner's map and say so |
| her flat (`home.json`) and what is going round for her (`zeitgeist.json`) | author | nothing on a cast row describes either |
| her own day beyond her week: fixtures, habits, curfew, twists | author | a running character plans from more than a cast row's week |
| her bible and speech guide finished from the seed | author | the seed is her sheet's paragraph, not a voice |
| what she believes about herself and about him, how each person may sound | author, or left blank on purpose | blank reads as "decided nothing yet", which is right for day one |
| the numbers for her own people (closeness, standing, tension) | author | Rena's mother and brother still sit at zero for this reason |
| `agent: "<hub id>"` on her row in the world's cast file | author, by hand in `data/cast.json` | the tool refuses to edit the owner's roster file for her |
| her row in `characters.json`, her launcher as `<key>.cmd.next`, her scheduled task | compose, once her manifest says `registered: true` | left alone while she is unregistered, by design |
| the secrets (eight keys) | copied from a live config at compose time | a bundle never holds a secret |
| `restart.cmd <key>` | the operator | the only way a process survives |

Eleven rows. Before today the same list was six scattered files in four
conventions, no verify step, and a first day spent as the first character
(HISTORY 2026-09-07). The four authored files are real authoring and should
stay hand work with a model's draft; the two roster edits and the register step
are mechanical and are what section 3 removes.

## 2. What a single shared world still cannot give a new reader

These are the open items of `docs/shared-world.md` section 7, unchanged by
today's work, and they bound how seamless a fifth reader can be:

1. ~~**She cannot say where she is.**~~ Closed by step 4 (2026-09-07): she
   writes the rows about herself, and the owner's planner prefers them for a
   window. Her own circle's rooms and words still land in her own save and
   never reach the world.
2. **Nothing checks two characters are on one clock.** Each reads
   `world/clock.py` with her own timezone from her own config.
3. **Every read of the world reopens the file.** Right for a few looks a
   minute; wrong for a prompt build that wants the roster on every call.
4. **A reader's own circle has no group room.** A LINE group of her own people
   needs a room name that does not collide with the world's `group`, and she
   cannot knock on the owner's group chat with an opener through the hub.
5. **The owner's process still plans a beat FOR a promoted member**, and asks
   her through the hub within 180 seconds or the room proceeds without her.
   That is the seam's design, and it means a promoted character's presence in
   the owner's rooms is on the owner's schedule, not hers.

## 3. The work, in order

Each step is independently landable; each names the check that proves it; each
patch is idempotent (skipped when the new text is already in the file) with
originals under `data/retired/<ts>_<step>/`. Smoke clear before every restart.

### Step 1: one command from cast row to registered character

`tools/promote_cast.py <key> --register --hub-id <id>` does what the proof did
by hand: writes the bundle, marks `agent` on her row in the owner's cast file
(a guarded data edit, refused when the row already carries a different agent),
confirms the `self` block carries `key`, `role_id`, `role` and `agent`, sets
`registered: true` in her manifest, then runs compose (config, prompt
directory, register row, launcher `.next`, empty seeded save) and verify. It
stops with the list of authored files she still lacks and refuses to register
her while any of them is missing (`Config.PERSON_FILES` refuses her boot anyway;
the tool says so before the operator finds out at the restart).

**Done looks like:** the proof's steps 01 to 05 are one command and one
output. **Check:** the promotion proof in smoke, on a throwaway bundle under a
temp directory, asserting the same list verify asserts today.

### Step 2: drafts for the four authored files

The tool writes a DRAFT of `household.json`, `map.json`, `home.json` and
`zeitgeist.json` from her sheet, her row's week and the world's shared places,
every invented value marked `INVENTED` the way `characters/rena/cast.json` marks them,
and prints the file list for the author to finish. A draft is a model call
(one per file, flash, cents) with the schema each reader expects; the reader's
own loader is the validator. Bible and speech guide stay seeded from her sheet
and are finished by the author; the tool never writes a voice.

**Done looks like:** a promoted character boots on drafts with every invented
value visible in the files. **Check:** the four loaders accept the drafts;
verify passes; the leak assertion passes.

### Step 3: the numbers for her own people

`promote_cast.py` and `new_character.py compose` seed her own people's meters
from their sheets' stated closeness/standing/tension, and refuse a sheet that
leaves them at zero unless the sheet says `numbers: unset` on purpose. Rena's
mother and brother are the live case and get numbers from him.

**Check:** `tools/world_reader_test.py` asserts no meter of a reader's own
person sits at 0/0/0 without the marker.

### Step 4: a second writer for the shared world, partitioned by person

The one-writer rule stays for everything the owner owns. Add a per-character
partition: a reader writes ONLY the rows about herself (`whereabouts` where
`person` is her, `members` where she joined or left, her own `settled` lines
about her own plan), under her own `char_id`, and the owner's process reads
them back where it plans a beat for her or lists where everybody is. Conflicts
are impossible by key: the natural keys already carry the person and the
source. The owner's row about her from "their week" becomes the fallback when
she has written nothing for the window.

**Done looks like:** Rena's own day planner's blocks appear in the owner's
"where each of them is today" for Rena, and the owner's beat for her lands
inside a window where Rena has her phone. **Check:** `tools/world_test.py`
drives a reader's write and the owner's read on a scratch world; the owner's
process refuses a reader's row about anybody but herself.

**LANDED 2026-09-07.** `world/shared.py:_may_write` is the partition and
`_prefer_own` the preference; `CastEngine.own_day_to_world` writes her day at
`day_planned` and at every re-plan; `CastEngine.their_own_where` is what the
owner's line, her phone and who is free after school read first, and
`Ledger._own_windows` is the same preference in the day's one truth.
`world_shared.reader_writes_own_rows` switches her writes off; the reading side
has no switch, because a file holding two answers must be read one way by
everybody. `tools/world_test.py` is in smoke and drives all of it, including
the owner's own rows read back unchanged from a copy of the live world file.

### Step 5: one clock, checked

At boot a character in a shared world writes her timezone and her clock's
offset into the world's `meta`; a second character in the same world refuses
to start if hers differs. **Check:** `tools/world_reader_test.py` with two
configs on two zones asserts the refusal.

### Step 6: a reader's cache

`world/shared.py` keeps the roster and the day's whereabouts for one prompt
build (invalidated on the file's mtime), so a reader's prompt build opens the
file once. **Check:** a counter of opens per build in the world test.

### Step 7: a group room of her own

A reader's own circle gets a room name derived from her key (`group:<key>`),
opened by `Exchange.start` with her own people only, written to her own save,
never to the world. Her knocking on the owner's group chat is a hub request
carrying her opener, which the owner's room accepts as the next turn.
**Check:** the seam test opens both on stubs; the world file gains no row.

### Step 8: her tools from her sheet

Promotion already gives a character the pick tools her existence answers
allow (`sim/pick.py`); a new character with `with_him: none` gets two, one
with a chat with him gets nine. Step 7's group room adds `open_own_group` for a
reader with a circle. **Check:** the boot line `[pick] LIVE ... Tools: ...` for
the promoted character in the proof.

### Step 9: the register drives everything

`characters.json` is already a projection of the four manifests. The hub reads
it for hidden rows, the restarter for tasks and launchers, smoke for whom to
build, the isolation and leak checks for whose material is whose. Anything that
still lists characters by hand (grep for the four keys outside `characters/`
and `characters.json`) reads the register instead. **Check:**
`tools/registry.py --strict` fails on a key named anywhere the register is not
the source.

### Step 10: the documents

`docs/promotion.md` becomes the one-command story with the author's list;
`docs/shared-world.md` section 7 records the second writer and the clock;
`PROJECT.md` section 20 via `tools/docs_src`; `CONFIG.md` via the assembler
for every new key; `docs/README.md` rows; one dated HISTORY entry per landed
step. This document is retired to `data/retired/` when step 9 lands, and the
index row goes with it.

## 4. Recommendation

Steps 1 to 3 first: they turn the eleven-row table into "run one command, then
finish four files and a bible", and they are what the next promotion will hit.
Step 4 is the one design change; it is the difference between a reader who is
in the world and a reader who is only read about, and it is his call because
it ends the one-writer rule for one partition. Steps 5 and 6 are small and can
go with step 4. Steps 7 and 8 are what make a promoted character's own life
visible in her own rooms. Step 9 is what stops the fifth character from being
listed somewhere by hand.
