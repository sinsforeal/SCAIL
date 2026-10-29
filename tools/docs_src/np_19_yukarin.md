
---

## 19. Yukarin (`yukarin/`): the second persona, extracted -- and the model harness

Spec: `docs/yukarin.md`; the harness: `docs/model-harness.md`; running the
same extraction on somebody else: `docs/character-method.md` §6 and
`docs/extraction-runbook.md`. Dated
notes: HISTORY.md §19; the 700-line work log this entry replaced sits in
HISTORY.md under its own 2026-09-03 heading.

**The glance** (`resident/sight.py`): every poll her sight reads his
foreground window title, and a page on one of the databases (MyAnimeList,
Wikipedia, AniList, AniDB, Anime-Planet) that he stays on
`glance_dwell_seconds` is resolved. `page_of` reads the SHAPE of the title
and no more -- a type in brackets or a `| Manga` mark proves a work, and a
bare title or an alias in brackets proves nothing, because a work and a
character's page are written the same way -- and the resolution settles
what it is. It is the thing in the room for `glance_fresh_minutes`: pinned
and hers to act on when she was in it, background otherwise, an event, a
thing she knows by name, and for her own work a reason to reach out first
(`glance_impulse_bonus`, said once).

**One resolution for a work, whoever named it** (`sim/works.py`, `identify`):
what she already knows by name first, and if a record answers nothing is
fetched at all; then his own list for the canonical title and the id; then
the three-state verdict on whether the work is hers (`her_part_verdict`,
below -- matched on the title, the page's alias, the id and the character's
name, against her own mirrored filmography rather than under a name); then her
own record (`Lore.match`, and
`Lore.work_named` for a record whose own title or tags are the name on the
page, which is how a romaji page reaches a record written in Japanese with
no call); then a person or a character the list knows, which is never
searched; and a web search last, only for a work nothing here has heard of.
Whatever is found is written once, to `known_things`, with whether it is
hers, the part, the verdict, the id and when it was last on his screen; her
sight's `glance_last`, her situation's recall and the automatic lookup's idea
of what is open in front of him all read that one row. Her sight, and the
lookup off a message of his, are the two callers.

**Was she in it: yes, no, or nobody checked** (`sim/works.py`
`her_part_verdict`; spec `docs/role-check.md`). `hers` was a boolean, so "she
is in it" and "nothing here knew" were one value, and she told him she had
voiced a part in a work she has never been in with no cast
information of any kind in front of the model. **A flat no is only said when
two independent local tables agree**: her own mirrored filmography has no row
for the work AND the work's own cast is mirrored without her in it. Anything
else is nobody-checked and says nothing -- the cast table covers 480 of his
701 titles, so on its own it would answer "not yours" about her own parts.
Her filmography is the authority, the cast the second witness, and they have
never disagreed here (63 of her works have a mirrored cast; all 63 name her).
Who she is on that list is `character.mal_person_id`, an id and never a name,
and that id is also the switch: `Config.REQUIRES` assigns the section to the
derived property `voice_actress`, so the first character prints
`not resident and not voice_actress, so these are off: role_check` and never
reads the mirror. The line she gets is the program's wording (`role_yes`,
`role_no`, `role_no_near`) and rides the four places the anime detection
already delivers anime details -- the episode he played, the page in front of
him, a title he named, and the same title days later -- all of them after the
thread, so it cannot invalidate the cache. The continuity editor gets the same
verdicts as a thirteenth block of evidence, English, and a fourth reason to be
asked at all (a work the mirror has a verdict on, matched whole or by its lead
segment: the OVA is recorded in full and typed `ゆゆ式のOVA`). Flag, never
rewrite. No fetch in a reply path; `role_check.fetch_on_miss` mirrors a
missing cast in the watching worker, which was already fetching.
history: 2026-09-04.

**The search**: `[search: ...]` on its own line in her draft runs one web
search and one `search_gist` call and the reply is written again with the
answer (`lookup.on_request`, on for her; `search_per_day` caps hers and her
sight's); a question about a work she knows by name also reads the series'
Japanese Wikipedia lead. Her style file's 調べる section tells her the line
exists. A part she played, in a work he has NAMED, is pinned in the
retrieval, at full score and at most one line, so the attention budget
cannot drop it on a crowded tick (`lore.role_kinds`, `lore.pin_score`,
`lore.pin_max`). A pinned line bypasses the cap but its characters still
count toward it, so the cap fires on the first ordinary line after it;
giving pinned lines their own reserve, and deciding what happens when they
alone exceed the cap, is undecided.
history: 2026-09-03 20:45, 2026-09-03 23:50.

A second persona beside the first character -- 田村ゆかり's 2003 radio
persona, wanted as a companion that watches his machine -- built by a
different method: **extracted from her own broadcasts**, ninety-nine
episodes on disk, her pattern as data with receipts. The pipeline is
`yukarin/tools/`: `yukarin/tools/corpus.py` (SRT to cues),
`yukarin/tools/fingerprint.py` (regex counts of the countable claims),
`yukarin/tools/attribute.py` (her / mail / read / song / other per cue),
`yukarin/tools/extract.py` (register, mechanisms, moments and facts, every
evidence quote verified against the cue it cites; the dropped share is the
invention measure), `yukarin/tools/reduce.py` (two-level clustering into the
sheet) and `yukarin/tools/audit.py` (a prompt scored against the sheet). No
model judges anything: the control is a close reading, six episodes read end
to end in `docs/yukarin-manual-notes.md`.

**The harness** (`yukarin/tools/llmx.py`, `yukarin/tools/providers.py`,
`providers.db`): one client for the official DeepSeek endpoint, OpenRouter
hosts pinned with no fallback, and Gemini on Vertex; every call logged with
provider, endpoint and who served it; no output limits. `YPROVIDER` moves
the whole pipeline to one host and the default is DeepSeek v4 flash at
Together (`llmx.DEFAULT`, his call). Every call is streamed and a cut is
continued, only whole JSON objects are read out of the instalments
(`llmx.call_long` / `objects`, `yukarin/tools/continue_test.py`), and every
finished unit is cached so `yukarin/tools/reduce_run.py` picks a failed run
up rather than repeating it.

**The persona dataset** (`yukarin/persona/`, `yukarin/tools/persona_build.py`,
spec `docs/yukarin.md` §8) is what she is driven from, and no model is called
anywhere in it: 152 hand-consolidated fact records over 454 cues, the
lorebook's 550 bullets imported verbatim with their quotes located and their
era stamped, and the register summed by code. One record shape, the
provenance kind (`stated` / `evidence` / `measured` / `authored`) on the
provenance entry rather than the record, ids computed in code, a receipt that
does not resolve failing the build, and contradiction parked in
`yukarin/persona/conflicts.json` with nothing resolved in code. Every record's
statement is in Japanese, written from the cues, with the English kept beside
it as `s_en`. **The sheet** is `yukarin/sheet/yukarin_extracted_v2.json`
(spec §3): 1,842 observations in 77 mechanisms, 410 evidence quotes, judged by
reading in `docs/yukarin-judgement.md` -- sound as evidence, unreliable as a
taxonomy, 72% recall against the hand-read episodes. `yukarin/tools/bounds.py`
maps the pattern to five drivers and counts what the corpus cannot answer:
initiation, family and reciprocal friendship stay unspecified because 99
broadcast episodes have no private relationship in them.

**She runs live beside the first character**: `config_yukarin.json`, save
`data/yukarin.db`, her own lock, `yukarin.cmd` behind the `SCAIL_yukari`
scheduled task, registered with the one hub. Her sheet is
`characters/yukari/sheet.json` and four declared properties (`embodied`,
`in_world`, `sees_him`, `has_account`) drive `Config._existence_implies`;
`Config.REQUIRES` assigns every switchable section to one of them and
`_check_existence_table` refuses to start if one is unassigned;
`Config.WORLD_KEYS` blanks the flat `world` keys so a character with no world
has no path to the other one's household. The four answers live in the config
and the sheet only overrides them, so the rules run whether or not there is a
sheet on disk: `_apply_character` reads the sheet if there is one and reaches
`_existence_implies` either way, and `Config.__init__` refuses to finish if it
did not (`_existence_applied`). It used to hang off the sheet, so a config
with no sheet beside it kept every in-world subsystem on, kept every world
path live, and never reached the check that a switchable section has been
assigned to a kind of character at all. `_check_existence_answers` refuses a
sheet or config that leaves one of the four unanswered, or that spells
`sees_him` as anything but digest, resident or none -- an unanswered property
reads as yes everywhere it is tested, and a misspelt `sees_him` reads as "not
resident" and hands her the other kind of sight. `in_world` stays false and
that is the decision. Her day is planned from her home file alone
(`schedule.own_day`), her sleep is read off his machine
(`resident/sight.py`, kv `resident_asleep`) because she has no pocket and no
phone, her household (`sim/household.py`, `characters/yukari/objects.json`) is
what her director writes instead of her thoughts, her record is retrieved as
lore (`lore.memory_file`), and a note he leaves open is read whole
(`Notes.read`) while her snoop stays off (`vault_snoop.enabled` false).

**And her sheet also says what machinery she has not got**, which the four
existence properties cannot answer because none of it follows from having a
body, a world or an account. `mechanisms_absent` on her sheet
(`Config._mechanisms_absent`, the counterpart of the `gauges_absent` beside it)
names a section, whose own `enabled` flag goes false, or one of
`Config.NAMED_SWITCHES` for a thing with no section of its own; a name that is
neither stops the boot, the way a section missing from `Config.REQUIRES` does.
Six rows, each with its measurement on the sheet, all his call:
the continuity check on her drafts (`delivery.editor_enabled`, 18 refusals in
142 checks); not answering him on purpose and the attachment stance, neither of
which has fired once in 127 runs of hers; what breaks between them and anxiety
as a chain of inference, the same; and what she eats, which was a flag with no
reader at all, because the meals are one of the slots only the first
character's program builds. The week read back at the compile is deliberately
kept: it has never fired because it needs seven days of her and she has four.

**Her config is generated and now keeps what is in it.**
`tools/make_yukarin_config.py` used to write `DEFAULTS` plus its own
`OVERRIDES` over the top, on the claim that everything deliberate about her was
in that dict; 86 keys of her live file said otherwise, so a re-run would have
handed the role that writes her words the first character's bible, put her
menstrual cycle, her physical needs, the weather and an allowance back on, and
switched her flat, the visual novel and what he is watching off. Her file now
goes UNDER `DEFAULTS` the way `config.json` does at every boot, the sheet's own
answers (the existence block, her MyAnimeList id, the machinery she has not
got) are copied from the sheet rather than typed in the tool, and the switches
that were hand-set are written down in `OVERRIDES` with the reason on each.
`--out` writes a copy to compare against her live file, and the difference is
nothing; `--fresh` says what would be left if her file were gone -- 30 keys,
which are which model writes in her voice and twenty tunings of her prompt.

**Her voice**: nine roles that write in her voice run on `kimi-k3` -- persona,
diary, reflect, wonder, morning, anticipation, approach, spiral, revise_self
-- and the other 67 on `deepseek-v4-flash`; `tools/set_model.py` moves every
role together or not at all and `/model` pins them for one run. Two written
approaches sit side by side under `prompts_yukarin/`, each holding the bible
and speech guide that belong together, picked by `models.persona.prompt`,
`character.style_prompt` and `character.style_ja_prompt`:
`prompts_yukarin/voice_as_she_writes_in_text/` is the authored control every
existing measurement was taken under, and `prompts_yukarin/voice_replica_in_text/`
is what runs (his call, after `docs/yukarin-voice-models.md`). Her line is
spoken only when he taps it (`tts.on_demand` on, `tts.always` off). **What language she is ADDRESSED in is one switch.** The arm is
`character.instructions` (`sim/lang.py`): `as_they_run_today` the control,
`in_english`, `in_her_language`, or `auto`, **which is the default and is
what an unset value means**: her own language when she declares one this
switch can render, and the control when she does not. It covers everything the prompt
builder writes at her -- her section headers, every bucket of her situation
block, the closing instruction that says what to write and how -- and
`character.instruction_language` says which language `in_her_language`
renders for a given character, so the first character, whose chat with him is
the one room her English lives in, has no second arm and the command says so
instead of switching her. `/lang ja|en|auto` writes kv
`instructions_override` on her save and the boot reads it back, so the arm
moves between two replies and survives a restart without a config edit; the
boot line and `/provider` name the arm AND what decided it, which is how a
character instructed in the wrong language stops being invisible: while the
control was everybody's default, two of the four declared Japanese and were
instructed in English, because only one of them had ever been switched by
hand. The `language`
section carries the other half: the roles named in `language.material_roles`
(30 of them) are given one line telling them which language their PROSE goes
out in, because the arm cannot reach the sentences other roles wrote -- the
facts about him, the notes she read, what she has decided about herself. Four
roles are off that list because code reads their words as data (the digest's
English patterns, the scene and the plan's places and activities, the state
role's arithmetic), and the editor forks in its own prompt instead
(`[[?her_language]]`, a condition `Config.conditions()` publishes), because
the note it writes is put in front of her and the verdict beside it goes to
the log. Measured on 24 draws over six real moments: the arm alone moves
nothing in her replies (`data/retired/20260904_lang_switch/REPORT.md`).

**No school day reaches her.** A fifteen-year-old's day was the last of the
first character's life left in prompts the second character renders, and it
was in prose rather than in code. It is out of them by the same two
mechanisms the rest of the separation uses: the first character's world sits
inside a `[[?in_world]]...[[/in_world]]` block (what is going round her school
and what the girls there are watching, in the watch pick; the ward and the
month in the sleep prompt), and a wording that has to differ per character is
a `[[TOKEN]]` filled from `data/characters/neutral/<id>.json` with the first
character's exact original span as her value -- what she promises that nobody
could watch her do, her age as one word, who skims a search result, the room
beyond her own at night. `tools/sight_words.py` renders every role's prompt
for every character whose sheet says `in_world` is false and fails on school
vocabulary in either language, so the next mechanism prompt written around a
schoolgirl is caught before a restart rather than after one. Her own files
(`prompts_yukarin/`) name a school only in her own past, which is hers: junior
high drama club, a commercial high school, contacts since primary school.

**The checks that keep two characters apart**: `tools/isolation.py` classifies
every path as hers, the machine's, a neutral mechanism prompt or shared and
person-shaped, and fails on the last; `tools/neutral_gate.py` renders every
role's prompt and proves a shared prompt comes back byte for byte for the
character it was written around; `tools/character_leaks.py` and
`tools/prompt_leaks.py` name anybody in a run's output or its instructions who
is not in that character's record. `tools/voice_verify.py` screens her output
against the tape and refuses to judge a marker there is not enough writing to
test (`docs/verification.md`); `tools/voicelab.py` benches one variable at a
time and scores nothing; `tools/quote_audit.py` counts every quoted line in a
persona file against her attributed words, because a line quoted once becomes
a catchphrase.

Not built and said so: `threat` has no writer for "he did something that shows
he will use what he has", which wants a judgement rather than an arithmetic;
the third viewer in `sim/ledger.py` (docs/primitives.md §7 step 4); and
`audit.py score`, the only automated read of the sheet against the close
reading, has still never run. Outstanding on the corpus: `ep100_5` is the one
broadcast without a week-shape sheet, and ~500 further episodes are available
for about $20, which would move the era rather than answer what the corpus
cannot.
