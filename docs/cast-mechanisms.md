# A cast member as a set of mechanisms

A character sheet says what somebody is like. It gives a model adjectives to
perform, and a model performing an adjective produces the same girl in every
room. A mechanism says what makes a person do a thing, what stops them doing
it, and what doing it gets them — trigger, suppressor, function — so there is
something to run instead. The extracted character already works this way
(`docs/character-method.md` §2); the difference here is that these are
**authored rather than coded off a tape**, and every entry says so in its own
`tier` field, so nothing in this set can ever be quoted as a measurement.

`tomoe/cast_mechanisms.py` is the loader, the validator and the renderer.
`docs/cast-exchange.md` §2a is where the sheets are described; this is the
layer underneath them.

## The files

`data/cast_mechanisms/<roster key>.json`, one per person on the roster — the
`people` keys of `data/cast.json` — read fresh whenever the file changes, the
way the sheets and the roster are, so authoring a mechanism lands on the next
call. **A person with no file has no block**: the calls go out exactly as they
did before anybody wrote one, and that is the normal state while the set is
being written.

    {
      "_note": "authored, not extracted: tier 3 everywhere",
      "who": "<roster key>",
      "mechanisms": [
        {"id": "<stable, never reused>", "name": "<a function phrase, humans only>",
         "trigger": "<the condition under which it fires>",
         "suppressor": "<what stops it>",
         "function": "<what doing it gets her>",
         "variation": ["<a form it takes>", "<another>"],
         "frequency": "high | medium | low | rare",
         "class": "hers | the format's | a moment",
         "tier": "authored",
         "ja": {"trigger": "…", "response": "…", "unless": "…"},
         "readers": ["cast_turn", "cast_beat", "cast_day"]}
      ],
      "drivers": [
        {"id": "…", "text_ja": "…", "mechanisms": ["<mechanism id>", …]}
      ],
      "secrets": [
        {"id": "…", "fact_ja": "…", "knows": ["<roster key>", …],
         "reveal": "<prose, for the arc writer>", "tier": "authored"}
      ]
    }

`class` is the same three-way split as the codebook's: something that is hers,
something the setting imposes on anybody in it, and a one-off moment.

## The two layers, and the codes

A file has two layers, and every instance says which it is in its own
`tier` field.

**Authored** is the hand-written one, above: somebody's mechanisms written
from her sheet and her roster row. Each one now also carries a `code`, the id
of the entry of the mechanism codebook that covers it (`docs/codebook.md`),
taken from `data/codebook/loss_ledger.json` and never typed into the file --
so a re-compile after the ledger moves picks the move up. An instance the
ledger sends nowhere carries `code: null` with `code_reason` saying why; the
two on the roster today are a Sunday behind a counter and a Saturday morning
that belongs to a little sister, both of which the codebook refuses as
one-occasion moments.

**Derived** is written by `tools/compile_type.py` from the person's private
prior and the compile table (`docs/character-method.md` §3.1), and it is regenerated
on every compile: one instance per code of her four cells, with the cell's
trigger and suppressor, the frequency band her health setting leaves it at,
and the wordings in the language of the call that renders it. Nothing about
the prior reaches the file -- not the letters, not the names of the four
positions -- and `tools/cast_mechanisms_test.py` greps for the whole
vocabulary over the mechanisms files, the sheets and the prompt directories.

A derived instance also carries `en` beside `ja`. The rooms the people around
her talk in are Japanese and always render `ja`; a character's own block
renders the language she herself is addressed in, which for the first
character is English.

## The two stress modes

Two derived instances per person carry a `gauge_trigger` instead of firing on
an occasion: one that starts when a gauge has sat at or above a line for a
span of hours, and one that starts when a gauge reaches its end. The
readings come from the compile table and sit just under the level
`state.discharge.rules` fires that gauge at, so the second is on in the hour
the gauge reaches its end rather than only after it has discharged.

The renderer does two things with one:

- **in the block**, always, as a conditional rather than a standing habit:
  「そういう状態が何時間も続いたとき、…」 / "when it has been like this for
  hours: ...". A reader of the block should know the shape of it without
  being told it is happening now.
- **in front of the call**, only while the reading holds, as one line that
  says what has been going on and never what she does about it. A line
  naming the response would be an instruction to perform the response.
  `cast_mechanisms.mode_line` is the line; it fails closed, so without a way
  to ask how long a gauge has been above a line the mode that needs a span
  does not start at all, and where both hold the one at a gauge's end wins.

Nobody on the roster has gauges of her own, so no mode is ever on for any of
them today and the path is proved on a fabricated reading in the test. The
first character reads her real gauges: her block is a section of the system
half of her prompt (`persona/sections.py`) and her mode line is one tagged
bucket in what she carries into the moment, which is where an hourly thing
belongs.

A compiled file also carries `baselines` -- the gauge baselines her health
setting proposes, each with a line saying where the number came from -- and
`compiled`, which records the table version, the codebook version and the
health setting. **The baselines are a proposal.** Moving a running
character's baselines is the owner's call and the compile does not do it.

## Who sees what

`readers` names the roles a mechanism may reach, and nothing outside that list
sees it. Four calls render a block, which is what makes "has a reader" a
claim somebody can check:

| role | the call | what it gets |
|---|---|---|
| `cast_turn` | `Exchange._one_speaker` | that one speaker's mechanisms, her drivers, and what she knows and does not say |
| `cast_beat` | `CastEngine._speak_beat` | the same, for the person opening a conversation |
| `cast_day` | `CastEngine.plan_day` | every person's mechanisms, **and no secrets at all** |
| `persona` | the character's own prompt, through `OwnMechanisms` and `persona/sections.py` | her own mechanisms, in the half of her prompt that changes about once a day |

A secret reaches only the two calls where that person is speaking for herself,
as 「知っているけど言わないこと」. The planner writes for six people in one
call, so a secret put in front of it is a secret six people are holding; its
`knows` list is the roster keys of who has been told, and the `reveal` is prose
for the arc writer (`cast_arc`) and for nobody else.

The block goes in the **user** message, under its own heading, after the
person's sheet material and before the day's ledger — where
`cast_psych.line_for_them` already lands. The character sheet stays the system
prompt (`prompts/cast/<key>.md`), because that is what it has always been.

## What never reaches a prompt

The id, the `name` field (a function phrase written for a human reader), the
`class`, the `tier`, the `code`, the receipts, and the top-level English
`trigger` / `suppressor` / `function` / `variation`, which are the author's
and the audit's. What renders is one rendering block, as one line per
mechanism — trigger → response, and the suppressor in brackets: the `ja`
object in the rooms the people around her talk in, which are written in
Japanese, and for a character's own block the object in the language she
herself is addressed in. The three cast prompt files each carry one
paragraph saying that the person **runs on** these and never describes one:
`tomoe/prompts/cast_turn.txt`, `tomoe/prompts/cast_beat.txt`,
`tomoe/prompts/cast_day.txt`.

## The cap

`cast.mechanisms_max_chars` (3600) is the ceiling on one person's block in one
prompt, and over it the **rarest go first**: what a person does every day is
what a reader of the block most needs, and the once-a-month one is what the
day could have gone without. The drivers and the secrets are not dropped —
they are a paragraph and a line or two, and dropping the want while keeping
the behaviour would leave the behaviour unexplained.

## The checks

`tools/cast_mechanisms_test.py` runs on fixtures under
`tools/fixtures/cast_mechanisms/` — a sound file, a file with a mechanism no
call renders, and a file carrying one of every fault — and then on whatever
real files exist. `tools/smoke.py` runs it as a block that stops a restart.

The validator refuses: an id used twice (a driver pointing at it is then
ambiguous), a `frequency` or a `class` outside the fixed sets (a typo sorts
silently to the bottom and is the first thing the cap drops), a `readers` entry
naming no role in `models`, a driver naming a mechanism that is not in its own
file, a secret held from somebody not on the roster, and a `ja` object with no
trigger or no response, which renders to nothing at all.

**A mechanism must have a reader.** One whose `readers` name only roles that
never ask for a block is reported DEAD, exactly as a gauge nothing acts on is
DEAD in `/sweep`: it is written into the record and read by nothing.

## The type file, and what it is not

`data/cast_types.json` holds, per roster key, the four-letter personality type
each person was written from, one line per axis of the behaviour it was
translated into, and the observable markers that behaviour should leave in a
turn. **Nothing that assembles a call may read it** — not a prompt builder, not
a role, not a prompt. `tools/smoke.py` greps `sim/`, `persona/`, `tomoe/`,
`resident/`, `scail.py` and both prompt directories for it and fails on a hit.
The whole point of the exercise is that the type is described rather than
named: telling a model the four letters is handing it the answer, and what
comes back is then an impression of a type rather than a person behaving.

`tools/cast_type_test.py` is the one reader. It builds the App on a copy of the
save (`tools/harness.py`), counts each axis's markers over that person's own
turns in the record, and prints the type the author intended beside the pole
each count favours. A marker is either a Japanese surface form, counted as a
substring, or one of the structural facts about a turn the tool implements
(opening the exchange, answering last, asking a question back, naming a time,
several messages in a row, a very short or very long message, a stamp, a
picture). A marker written in plain English with no entry in that table would
count zero for ever and read as absent behaviour, so the tool names it.

**What the measurement can show**: whether the behaviour the author described
appears, and roughly at the rate he meant. A person written to open rooms who
opens none in a hundred turns is a mechanism that did not land, and that is
fixable in her file.

**What it cannot show**: that anybody is a type. The markers are the author's
own operationalisation counted on his own material, so they agree with him by
construction; there is one coder and no second, so there is no agreement
figure; the poles are not scaled against each other, so "favours E" means only
"more of the markers listed under one pole than the other"; and no published
norm applies to invented teenagers in a simulated chat, so none is cited.

## Config

| key | default | what it is |
|---|---|---|
| `cast.mechanisms_dir` | `data/cast_mechanisms` | where the files are |
| `cast.mechanisms_max_chars` | 3600 | the ceiling on one person's block in one prompt; it was 1800 until the derived layer arrived, which the old ceiling dropped first |
| `cast.own_mechanisms_max_chars` | 9000 | the ceiling on the CHARACTER's own block in her own prompt, which rides in the half that changes about once a day and is charged to the cache once rather than per turn |
| `cast.types_file` | `data/cast_types.json` | the author's type file; read by one tool and nothing else |

Both paths carry a different value in each character's config, the way
`character.cast_file` does. A path shared between two characters must belong to
the machine (`tools/isolation.py`), and a person's mechanisms are that person's.
