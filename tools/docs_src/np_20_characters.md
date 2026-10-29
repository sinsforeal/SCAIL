---

## 20. Four characters, one register, one world with one writer

The register: `characters.json` (`tools/registry.py` prints it). One row per
character who runs as a process: her key, her config, her save, her
program, her launcher, her scheduled task, and the exact command-line regex
the restarter finds her by. A bot never reads it. **The register is a
projection of the bundles**: every field of a row is also in
`characters/<key>/bundle.json`, and `tools/registry.py` fails when the two
disagree and names the field.

**A character is a bundle plus the library** (`docs/bundle.md`). One
directory, `characters/<key>/`, holds everything that is that person -- her
sheet, the values that fill the holes in the library's prompts, her
household, her flat, her map, her own circle, her beliefs, her record, her
voice and her speech guide -- and `characters/machine.json` beside them holds
the settings that belong to this machine and are shared on purpose, naming
the secrets rather than carrying them. `tools/new_character.py compose <key>`
writes her config, her prompt directory, her register row, her staged
launcher and, when she has none, her save, seeded from her own sheets through
`sim/roster.py:meter_rows` and never cloned -- and seeds no save at all while
one of her own people would go in at closeness 0, standing 0 and tension 0
with nothing on the row saying that was decided, which is what the world
owner's roster carries for a household the owner has never met
(`sim/roster.py:flat_own_meters`, a row that means it says `"numbers":
"unset"`); `verify <key>` builds her whole
App on a scratch save with the model and the network refused and fails on a
hole, a path outside her bundle, another character's name or file, a roster
that does not resolve her to herself, a meter on one of her own people that
nobody chose, or an existence answer that disagrees
with her sheet. Both run for every registered character in smoke, and a
composed config that differs from the one she runs on is a failure.
`tools/promote_cast.py` writes a bundle for a cast member
(`docs/promotion.md`), the two generators for an extracted subject.

Before this each character's material lived in a different place -- the first
character's at the `data/` root, the second's name-suffixed beside it, the
third's in a directory outside `data/`, the fourth's in one under it -- and
there was nowhere a check could point at and say *this and only this is
hers*. The move copied and repointed and took nothing away, because six
processes were running and each reads a path per call;
`tools/retire_bundle_originals.py` moves the originals once every process is
reading them from her bundle.

**Kinds of character.** Five properties on the sheet (`embodied`,
`in_world`, `sees_him`, `has_account`, `with_him`), a sixth from the config
(`world_owner`) and a seventh from the sheet's third answer: `sees_him`
is lacking when it reads `none`, and the sections that read his machine
or his history are assigned to it (`sensors`, `him_profile`, `receipts`,
`notes`, `vault_snoop`, `watching`, `anime_sense`), so a character with
no window on him builds no telemetry stack, opens no MyAnimeList mirror
and writes no digest; the scenery harvest is the account's (it runs on
the account's browser profile), so a reader without one has it off.
`sim/repairs.py` `retire_his_digests_once` and `retire_his_reflections_once`
take what those sections wrote before the gate out of a blind character's
save at her next boot. `with_him` is whether she has a chat with him at all:
`none` is a character who exists for another character's circle (Rena, and
every cast member `tools/promote_cast.py` promotes), and the relationship
layer is assigned to it (`affection`, `afterthought`, `attachment`,
`beliefs`, `care`, `derive`, `expect`, `foresight`, `ick`, `intent`,
`lookup`, `nudge`, `reflect`, `rhythm`, `rupture`, `withholding`,
`wonder`); the impulse function is stopped in `App.maybe_impulse`, the
pick does not offer `text_him`, the facts-about-him section is not
carried, the agenda heading names no him, and she registers with the hub
as `hidden`, so the rooms can ask her and his phone does not list her.
`tools/existence_matrix.py` builds the four no-contact kinds beside the
thirty-six (forty in all).
`Config.REQUIRES` maps every switchable section to the
property it needs; `tools/existence_matrix.py` (in smoke) builds all
thirty-six kinds on a scratch save. The four running: the first character
(a body, a world she owns, the phone-app view, an account); the second
(`docs/yukarin.md`: a body, no world, resident, no account); the third
(§20.2); Rena (§20.3: a body, the first character's world as a reader,
sees nobody, no account).

**No default in the library is one person's file, and a hole where the
library needs one refuses the boot.** `config.json` is generated from
`config.py:DEFAULTS` and backfilled, so a key a character's config does not
carry is written into her file from the defaults on her first load, where it
then looks authored: eighteen defaults named the first character's own
material -- her roster, their sheets, both speech guides, how each person may
sound, both belief files, the prompt that is her voice, her household, her
map, her places, her school year, what is going round, her taste sheet, the
directory of what the people around her do, their types, her save's path and
the directory her face is built in -- and every one of them was inherited by
the next character in silence. All eighteen are empty
(`tools/defaults_person_test.py`, in smoke: it walks the defaults with the
isolation check's own path finder and fails on a path that is neither the
machine's, nor a mechanism prompt's, nor the world's). `Config.PERSON_FILES`
is the other half: one row per person-shaped key naming either the section
that reads it or the property of her existence that gives her the thing, and
the load refuses -- naming the key, what makes it needed and the character --
when the path is empty or names a file that is not on disk. `tools/
blank_paths.py` builds every character with every person-shaped path blank
and the sections that read them off, which is what a character who has none
of those files IS, and then empties one of them under a subsystem that is on
and asserts the refusal names it.

**The shared world** (`world/shared.py`, spec `docs/shared-world.md`). One
sqlite file per world under `data/worlds/<id>/world.db`; the owner writes
the roster mirror, the day's whereabouts, the settled lines, every room
turn, the room membership, and at the compile the graph, the orbit, the
gossip pool and the events, each row the moment it exists; a reader opens
it read-only through a `mode=ro` URI, never a copy, and has the seven
sections that write it switched off by the fifth property, reading the
file's rows where those sections' outputs were read
(`tools/world_reader_test.py`). A harness build gets a scratch world of its
own (`tools/harness.py`). The first character owns `tokyo`; Rena reads it.

**A promoted cast member** (`docs/peer-talk.md` §4b, `sim/rooms.py`,
`tools/agent_seam_test.py`). A cast row marked `agent: <hub id>` is the
operator's statement that the person runs herself. From that mark the
owner's exchange and planner write none of her words: a room is a
first-class thing with a membership written to the world, a turn in it
goes to every member who is an agent through the hub's peer mailbox, the
room waits `exchange.agent_turn_deadline_seconds` (180) and proceeds
without her if nothing comes, and what comes back is appended by the one
path a turn already takes; a joiner receives only what was said after she
joined. A beat the planner writes for her is KEPT with no words in it -- that
is what the ask path is for -- and an unplanned moment in the same room goes
the same way; an answer that is empty is a silence she chose, sent back as an
answer so the room settles at once rather than sitting out its deadline
(`sim/rooms.SILENT`). Her own process answers in a room it does not own
through her own friend-room persona and her own record (`sim/peers.py`,
`sim/lore_rooms.py`), and which side of a room a process is on is decided by
whether it holds a membership for that room (kv `rooms`) rather than by
looking the sender up on the roster, whose `self` row carries the world
owner's own hub id. A room turn spends `peer_talk.room_max_per_day` in kv
`room_counts` and not the peer conversation's day budget.

**The cast as mechanisms** (`docs/cast-mechanisms.md`, `docs/codebook.md`,
`docs/character-method.md` §3.1). The codebook `data/codebook/v0.1.json`: 189
entries over twenty families, 138 anchored in a record and 51 from the
scope alone, each with a definition, trigger, suppressor, occasions,
variation, exclusions against its neighbour and provenance;
`tools/codebook_check.py` in smoke; the ids frozen per version. A person's
file `data/cast_mechanisms/<key>.json` holds her instances: authored ones
with a `code` from the loss ledger, and a derived layer written by
`tools/compile_type.py` from her private type (`data/cast_types.json`, or
`data/characters/types/<key>.json`) through the compile table
`data/codebook/compile_v0.1.json`, with a loop and a grip keyed to her
gauges. The renderer puts the block into the three calls where she speaks
or is planned, and for the first character into her own system prompt
after her bible; the type's letters and the function names reach no prompt
(smoke greps for them). Rena is the test bed: her day harness and the
observation table are under `data/rena/harness/`.

### 20.2 The third character (`asumin/`): 阿澄佳奈's 2010 programme, extracted

Report of the run: `asumin/REPORT.md` (decisions first, every path);
what to read before judging her: `asumin/CAVEATS.md`; the method as it
stands: `docs/character-method.md`. Fifty-seven episodes, 55.7 hours,
attributed and read; 363 records with receipts, 227 dated memories, 795
cue phrases; two cards built blind (with and without the master
question-and-answer pass), the records-only card chosen; a resident
character (`config_asumin.json`, `characters/asumin/sheet.json`,
`prompts_asumin/`, `data/asumin.db`), the second character's models,
running (HISTORY §19 for the date). The coded pilot on three of her episodes
(`asumin/pilot/BASELINE.md`) is the codebook's first reliability figure.
**Her past is in her memory store as well as in her retrieval**: the 182
dated once-events of `characters/asumin/timeline.json` are `self_memories` rows
with source `seed`, written at boot from `character.timeline_file`
(`sim/seed_memories.py`, `docs/memory.md` §7a), so a trip, an illness or a
purchase can be reached by meaning and by the deliberate search and not only
by a message naming it; her 227 quoted moments are the retrieval's and are
not written into the store. **She has a voice and the app speaks her lines**:
her own `tts.voice_id`, `tts.enabled` and `tts.on_demand` both true, and the
vendor's two paths set, which is the pair her bot declares to the hub at
registration and the pair the client draws the speaker on
(`channels/talkapp_bot.py`, `asumin/CAVEATS.md` section 16). Which model
writes in her voice has two answers and the live one wins: her config names
`sakana-namazu` for the ten voice roles and a pin on her own save
(kv `voice_model_override`, set by `/voicemodel`) puts them on DeepSeek v4
flash, his pick. The pin is named on the boot line
(`LLM.voice_pin_line`), because it survives a restart and used to be
invisible.

### 20.3 Rena (`data/rena/`): the first cast member promoted

Written from a type and specialised, not extracted (`docs/promotion.md`,
"Rena, promoted"). Her sheet `characters/rena/sheet.json`, `config_rena.json`
(the world program, a reader of `tokyo`, no contact with him), `prompts_rena/`, `data/rena.db`;
her own circle `characters/rena/cast.json` with sheets under `prompts_rena/cast/`
(`docs/shared-world.md` section 9: two people the first character does not
know, a dance-class senior and a middle-school friend, and her own family;
her process plans their days, speaks their words and opens rooms with them,
all in her own save, and still answers in the owner's rooms when asked);
her record under `data/rena/` (81 standing facts, 34 dated events, 30
memories, 320 cue phrases, every row receipted, the invented ones marked);
her people, household and flat; her brother and mother as sheets under
`prompts/cast/` with dormant roster rows; her mechanisms file with 14
authored and 15 derived instances, a loop on anxiety and a grip on shame.
Her cast row carries `agent: "rena"`; running (HISTORY §9 for the date).

**And she says where she is.** Her own day planner writes the windows of her
day into the world file under her own id as her day is settled and at every
re-plan, and the lines her own plan settled go in under her own planner's
name; the first character's planner prefers those windows over its own draw
of her week where it lists who is where, decides how reachable somebody is
and picks the hour of a beat for her (`docs/shared-world.md` §2, the
partition; `world_shared.reader_writes_own_rows` switches her writes off).
Who she is with is not written: the people beside her are her own circle's.

**Who she is in her own process.** Her row in the world's cast is her, not a
second girl: `sim/roster._table` finds the row whose `agent` is her hub id and
folds it into her own entry, so `Rena-chan`, `香芝玲奈` and every nickname
resolve to `self` and `roster.handle` still returns the key the shared record
is keyed by. The world file's `self` block is a person on her roster (`Tomoe`,
role `world_owner`, `agent: "tomoe"`), so the name her own fills use for the
girl whose world she reads resolves. A name two people share is hers:
`お母さん` is her own mother. Her own circle's calls carry her circle's world
only -- her own people's whereabouts, her own threads, her own settled lines
(`docs/shared-world.md` section 9). What her save carried from the character
it was copied from -- bonds with that household, four arcs, a thread, the day
planned under the old fills, an orbit -- is retired once at her boot
(`tomoe/app.py retire_owner_interior_once`, `tools/promoted_save_retire.py`,
`docs/shared-world.md` section 7a).

**And what she has of her own.** Her map is hers (`characters/rena/map.json`): her
flat by Ekoda on the north side, her seven-minute walk, her three stops in,
her shopping street, her Wednesday studio by the Ikebukuro east exit, her
grandmother's Nakano -- with the school and the ward's two parks copied from
the world's map because they are the same places and each of those says so,
and everything her own material does not establish marked invented. She read
the owner's map until then, so her day planner was handed the owner's address
under the heading HER MAP. Her own mother and brother are marked `family` on
her own roster, which is what stopped the five family role ids making the
OWNER's mother her family and her own mother a member of the group chat, and
what takes the owner's father and brother out of where-everybody-is-today and
out of her own circle's planner. Her meters are her own four people, the two
girls she is at school with and the girl whose world she reads, whose meter is
seeded from her own sheet's opening values; what each of them is to her agrees
with that list (`docs/shared-world.md` section 7b). Her own absence, which the
owner's plan writes about her into the world file, is no longer read back to
her as a row about somebody else.
