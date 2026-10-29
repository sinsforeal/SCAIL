# The character bundle: one directory that is one person

<!-- doc: reference -->

Everything that is one character lives in `characters/<key>/`, and everything
that is the same for every character lives in the library. One prefix is hers;
anything of hers outside it has to argue for itself, and anything under
somebody else's is the fault the whole arrangement exists to find.

`docs/character-layers-plan.md` is why. This is what is built.

---

## 1. What is in a bundle

```
characters/<key>/
  bundle.json         her key, name, hub id, program, world and side of it,
                      launcher, task, the command-line pattern, her save,
                      which of her files answer which config key, which keys
                      her existence empties, and every config value that is
                      hers rather than the library's
  sheet.json          what kind of thing she is, her temperament, her roster
                      identity, the holes nobody has filled yet
  fills.json          the values for the character-shaped holes in the
                      library's prompts
  household.json      her family as an economy
  objects.json        the things in her flat
  home.json           her flat, room by room
  map.json            her part of the city
  cast.json           the people who are hers
  cast/               their sheets, in their language
  beliefs.json        what she has decided about him
  self_beliefs.json   what she has decided about herself
  voice_rules.json    how each person around her may sound
  records.json  memories.json  triggers.json  memory_triggers.json
  timeline.json  zeitgeist.json  taste.json
  prompts/            only the role files she has rewritten, plus her own
                      voice (bible.md) and her speech guide (style.md)
```

Anything absent is absent, not defaulted. A subsystem whose file she has not
got is either switched off by her existence answers or refuses to start
(`Config.PERSON_FILES`).

`characters/machine.json` is beside them and is not a person: the settings
that belong to this machine and are shared on purpose -- his telemetry, his
history, the vendor tools, the hub -- plus the NAMES of the values that are
pasted in once. A secret is never written into a bundle: compose keeps
whatever the character's existing config already carries for each of them,
and leaves a new character's empty with a line saying so.

---

## 2. The manifest

`bundle.json` is the operator's register row expanded, plus what the register
does not need to know.

| field | what |
|---|---|
| `key` `name` `hub_id` `config` `db` `program` `launcher` `task` `match` | the register row. `tools/registry.py` fails when a row and a manifest disagree, and names the field |
| `world` | `{id, owner}` -- which world she is in and whether she keeps it |
| `prompts_dir` | the directory her config's prompt paths point at |
| `prompts_generated` | whether that directory is a copy compose writes. False for the character whose prompt directory IS the library's own (`prompts/`): the three files in it that are hers are checked against her bundle rather than written back, because writing into the shared directory would touch every character |
| `registered` | `false` for a character who is not in the operator's list and must not be: a promotion being tried out, a kind of character the matrix builds. Compose leaves `characters.json` and the launcher alone |
| `files` | config key -> the plain name that file takes inside her bundle |
| `blank` | the config keys her existence empties. Written empty in her file as well, so a character with no world has no path to another one's household rather than merely never being shown it |
| `holes` | the files promotion could not write. Her boot refuses to start until they exist |
| `origins` | where each file was read from before the bundle existed. `tools/retire_bundle_originals.py` works from this list |
| `config_overrides` | everything her config says that the library's defaults and the machine's settings do not |

Her sheet is the one file the bundle EDITS on the way in: it names her own
record, and the sheet wins over the config (`Config._apply_character`), so a
bundle whose sheet still named the old place would read her record from
outside it.

---

## 3. One tool, two verbs

`tools/new_character.py`.

**`compose <key>`** writes, in this order:

1. `config_<key>.json` -- the library's defaults, the machine's settings, her
   manifest's overrides, her bundle's files, the keys her existence empties,
   and the secrets carried over from her existing config.
2. her prompt directory, as a copy of the bundle's.
3. her row in `characters.json`.
4. `<launcher>.next` beside the launchers, never over a running console.
5. her save, LAST and only when the path does not exist: seeded by building
   her once with the model and the network refused, so her meters come from
   `sim/roster.py:meter_rows` and never from a clone of somebody else's save.

`--diff` writes nothing and says what differs. In smoke that is a failure: a
difference means either a hand edit to a config the bundle does not know about
or a bundle that has moved on without being composed, and the file is the one
that runs.

**`verify <key>`** builds her whole App on a scratch save with the model and
the network refused and fails on any of:

1. a hole that survives in a role prompt her existence keeps;
2. a path in her config that is neither under her bundle, nor the machine's,
   nor a mechanism prompt, nor the world she shares;
3. a name or place belonging to another registered character, in her rendered
   prompts or in her seeded save;
4. a file in her bundle that is another character's byte for byte -- which is
   the assertion the name test cannot make when the two are in one world,
   because the owner's mother, father and brother are rows on the roster they
   share and every one of those names cancels out;
5. her own key on her roster resolving to anything but herself, or a name that
   means two people;
6. the owner of her world missing from her roster, when she reads a world she
   does not own;
7. a meter on somebody who is neither hers, nor the owner, nor him;
8. an existence answer in her config that disagrees with her sheet.

`--root <dir>` points the whole tool at a directory of scratch bundles, so a
promotion can be composed and verified end to end without a byte of the live
tree moving.

---

## 4. Where a bundle comes from

**Promotion.** `tools/promote_cast.py <roster key>` turns one of the people on
the roster into a bundle: her sheet, her fills, her voice and her speech
guide, all derived from her roster row, her sheet in her own language and her
mechanisms. It writes no config at all -- compose does that, so there is one
statement of what a config is made of rather than two that drift.
`docs/promotion.md` is the full account, including what it cannot write.

**By hand.** A bundle is a directory of JSON. `tools/existence_matrix.py`
writes forty of them, one per kind of character the sheet can declare, with a
name and a place that belong to nobody
(`tools/fixtures/neutral_fills.json`), composes each and asserts that none of
them says a name belonging to a character who runs.

---

## 5. The originals

The move that made the bundles COPIED and repointed and took nothing away.
It had to: six processes were running, and each reads a path per call -- the
roster on the first read of the day, the household on every world-facing call,
a prompt on its mtime -- so a file that disappears mid-day is a crash or a
silent blank.

`tools/retire_bundle_originals.py` is the other half, and it runs after the
restart. It refuses to move anything unless, for every registered character,
no config on disk still names the old path AND her process started after her
config was repointed. What it moves goes to
`data/retired/<stamp>_bundle_originals/`, keeping its path under it.

---

## 6. What is checked, and by what

| what | where |
|---|---|
| every registered character has a bundle, and it agrees with her row | `tools/registry.py`, in smoke |
| composing her bundle gives the config she runs on | `tools/new_character.py compose --all --diff`, in smoke |
| her bundle is hers alone, built and rendered | `tools/new_character.py verify --all`, in smoke |
| nothing of hers is outside her bundle, and nothing under another's | `tools/isolation.py`, every pair, in smoke |
| every kind of character builds from a bundle that names nobody | `tools/existence_matrix.py --strict`, in smoke |
| no default in the library is one person's file | `tools/defaults_person_test.py`, in smoke |
| every role of every character renders with no unfilled token | `tools/fills_check.py`, in smoke |
| the shared code and prompts name nobody | `tools/character_names.py`, in smoke |
