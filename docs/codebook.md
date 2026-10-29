# The mechanism codebook: the file, the schema, and the version discipline

<!-- doc: reference -->

The codebook is the closed vocabulary of text-visible behaviours that any
character in this project is described against. It lives in `data/codebook/`
and it is the thing every `code` field written anywhere else points into. This
document says what the file is, what each field means, what the rules for
adding to it are, and what happens when the version changes.

What the vocabulary covers and why it is divided the way it is belongs to
`docs/character-method.md` §2.4 and §2.7; why a mechanism had to become a unit at all, and the
reliability gate a code has to pass before anything may rest on it, belongs to
the same guide's §2 and §4. Neither is repeated here.

## 1. The files

| file | what it is |
|---|---|
| `data/codebook/v0.1.json` | the codebook itself: the twenty families with their counts, and every entry with its full schema |
| `data/codebook/v0.1.md` | the same, readable: one section per family, one block per entry, and the counts, the one-subject entries and the merges at the end |
| `data/codebook/loss_ledger.json` | five mappings and their coverage: the scope document's own candidates, the extracted candidates, the authored candidates, the authored mechanisms of the people around the first character, and the first character's bible read as mechanisms -- each to the entry that covers it, or marked lost with the reason |
| `data/codebook/loss_ledger.md` | the same, readable |
| `tools/codebook_check.py` | the check, run by smoke: a failure stops a restart |

All four are generated together by `data/retired/20260906_consolidate/build_v01.py`
from the entry modules beside it. **Edit the entry modules and re-run the
build; never edit the four files by hand**, because the next build overwrites
them and because the ledger and the codebook have to agree about which entries
exist.

The three inventories the entries were consolidated from are kept at
`data/retired/20260906_codebook_scope/`: the two extractions sorted into
families with their candidates, the authored material sorted the same way, and
the mind library's own 171 mechanisms with the gate of each by file and line.

## 2. The entry

One entry is one behaviour with one trigger. Every field is load-bearing and
the ones that buy agreement between two coders are `suppressor`, `excludes`
and `near_misses`.

| field | what it holds |
|---|---|
| `id` | `F<n>.<function-phrase>`; stable, never reused, never renamed |
| `family` | one of the twenty, and the id's prefix must match it |
| `layer` | `occurrence` (it happened at these cues) or `function` (it did this for her, in context) |
| `definition` | one sentence, in observable terms, text only |
| `trigger` | the condition under which it fires |
| `suppressor` | the condition under which the trigger is present and it does not fire |
| `occasions` | the fixed list of occasions on which it could fire, written for both a broadcast and a typed chat, so that an absence is a datum rather than a silence |
| `function` | what it does for her, one sentence |
| `variation` | three surface forms that differ; if they do not differ it is a tic and belongs to the marker battery |
| `includes` | the rule for what counts |
| `excludes` | one row per nearest neighbour: the neighbour's id, and the rule that separates them |
| `anchors` | real instances, by the inventories' own ids |
| `near_misses` | two instances that look like it and are not, with why |
| `provenance` | the observer-rated instrument the definition borrows from, declared off-label, or `bespoke` |
| `tunes` | the module in the mind library a rate would tune, the dial by name, and whether it is a threshold or a gauge's baseline -- or "no home" |
| `sources` | which inventory candidates merged into it, by their names, and which scope candidate it carries |
| `status` | `anchored` or `theory-derived` (§3) |
| `single_source` | true when every anchor comes from one person |
| `version` | the codebook version the entry was frozen in |

**`class` is not a field.** Whether an instance is hers, the format's or a
single moment is decided per subject at coding time; the code itself is
neutral, and an entry carrying a class would decide it for every character at
once.

Anchors are written in a form that names no person: an item from either
extraction keeps its inventory id (`A186`, `Y18`), a sentence of a bible or a
speech guide keeps its id (`tb35`, `ys04`), and an authored mechanism of
somebody in the circle around the first character is written
`cast.<phrase>` -- the phrase halves are unique across the six files, so the
reference resolves to exactly one mechanism while the person it belongs to
lives only in the loss ledger, which is not part of the codebook.

## 3. Anchored and theory-derived

An entry whose `anchors` list is not empty is **anchored**: the project's own
material holds instances of it. An entry with an empty list is
**theory-derived**: the scope document names the behaviour, and none of the
852 extracted items, 207 authored items or 171 library mechanisms reaches it.
Version 0.1 holds both, because the codebook is meant to be the whole map
rather than the part the current corpus happens to cover: a family with five
entries and one anchor states a bound about the material, and a family with
five entries and no entries at all would state nothing at all.

The two are held to the same standard. A theory-derived entry with a vague
definition, fewer than three differing surface forms, or an `excludes` that
names no real neighbour fails the check exactly as an anchored one does.

**The pilot codes anchored entries only.** A theory-derived entry has nothing
to compute an agreement figure against, so it takes no part in the reliability
run; it enters the coded pass when a coder finds an instance of it, which is
the point at which it becomes anchored and the version has to move.

**The second tier.** `data/codebook/v0.1_theory.json` is a companion file for
entries something else needed and neither an anchored nor a theory-derived
entry of the frozen file covers -- the compile table
(`docs/character-method.md` §3.1) is what needed the first of them. They are written
top-down, with this schema, an empty `anchors` list, `status`
theory-derived, and a `provenance` naming what asked for the entry. The
check reads the two files as one book: the same schema for both, no id in
both, an `excludes` neighbour resolving into either, and a printed count of
how many entries of the two still wait for a record to anchor them. The
frozen file is not touched, because a version is changed deliberately and
rarely (§5) and adding an entry to it would be a change of version.
`data/codebook/compile_v0.1.md` lists the companion's entries with their
families and the cell each came from.

`single_source` marks an entry whose anchors all come from one person. It is
not a fault -- it is the honest state of much of the material -- but it means
agreement across subjects has not been shown for that entry, and a card that
rests on one should say so.

## 4. The rules for what becomes an entry

- **Split by trigger, never by surface.** Two behaviours that look alike and
  fire on different conditions are two codes; two that look different and fire
  on the same condition are one. Self-presentation is four codes and not one
  because an incoming compliment, her own claim about to be made, her own
  error just made and a judgement nobody has offered are four triggers.
- **Two codes stay two when a suppressor separates them.** The test case is
  deciding for a group against a worry that arrives as an instruction: the
  surface is identical, and instant silent compliance satisfies the second and
  leaves the first still firing.
- **A candidate with one observation behind it is a moment, not an entry.**
  This applies to the material's candidates. It does not apply to the scope's,
  which become entries with no anchors rather than being dropped.
- **A code that needs a face, a voice or a body to define is refused.** A
  channel may add evidence to a code; a code that cannot be seen in a subtitle
  file cannot be in a vocabulary shared between a tape, a chat log and a
  written sheet. The check refuses a definition that names one.
- **No subject's name in any field.** The codebook is shared between every
  character; a name in an entry would make it one character's.
- **A feeling is not a code.** A feeling is a gauge with a baseline and a
  reader; a code is what she does while the gauge is where it is.

## 4a. The two coding rules

Binding on every coder, human or model, and enforced by the coded pass:

- **A played role is the format's, never the person's.** A span the
  context labels mark as a played role (`asumin/corpus/context/<ep>.json`,
  a segment whose `context` is in the tool's `PLAYED_ROLES`; on the third
  character's programme the kindergarten corner, where she answers
  letters as a teacher talking to children) may be coded only under the
  format family. A person-level instance whose span lies inside such a
  segment is dropped by the coded pass and counted in the chunk's
  verification as `in_played_role`. Every reader in the pilot, the
  hand-coded anchor included, coded those lines as her own moves under
  seven entries; the rule exists so that a tool says it once rather than
  each reader deciding.
- **One row per entry per chunk.** A coded pass records every entry
  present or absent in every chunk, and an anchor written by hand takes
  the same shape. Logging an entry once at its clearest occurrence in an
  episode is a different measurement and is not the protocol; the pilot's
  agreement against its anchor was mostly this difference.

## 5. The version discipline

The version is on the file, on every entry, and in the filename. **A change of
version invalidates every `code` field written under the previous one**: a
coded episode, a cast member's mechanism and a character's mechanisms file all
record which version they were coded against, and a prevalence computed across
two versions is a number about two different instruments.

So a version is changed deliberately and rarely, and changing it means:

1. a new `data/codebook/v<new>.json` and `.md`;
2. the loss ledger re-run, because the mapping from a candidate to an entry
   has moved;
3. every `code` field re-derived from the new ledger, not edited in place;
4. `tools/codebook_check.py`'s `VERSION` moved, which is what makes the
   refusal in the next paragraph fire.

**The check refuses a mismatch.** If the file's version and the check's differ,
or an entry inside the file carries a version other than the file's, the check
fails and, because smoke runs it, the restart stops. That is deliberate: a
half-moved version is worse than either version, since it is the state in which
a coded pass silently mixes two instruments.

Within one version, ids are frozen. A wrong id is corrected by adding the right
one and marking the wrong one lost in the ledger, never by renaming, because a
rename is invisible to everything that already points at the old name.

## 6. What the check enforces

`python tools/codebook_check.py`, run by smoke, and a failure stops a restart:

- the file exists, parses, and its version matches the check's;
- no duplicate id; every id is `F<n>.<phrase>` and its family matches;
- every field of §2 present, with a definition that is one finished sentence,
  at least four occasions, three distinct surface forms, at least two
  `excludes` rows and exactly the near misses the schema asks for;
- every `excludes` neighbour is an id that is in the book, and no entry
  excludes itself;
- an entry called anchored has anchors, and one called theory-derived has
  none;
- `provenance` names an instrument or says `bespoke`; `tunes` says threshold,
  baseline or no home;
- no `class` field on any entry;
- no character's name anywhere in the file, using the same name list as
  `tools/character_names.py`, with a `<program>/<module>.py` path exempted the
  way that check exempts it;
- the loss ledger exists, carries the same version, and sends nothing to an
  entry that is not in the book;
- the companion file, if there is one, carries the same version, holds only
  theory-derived entries, and shares no id with the frozen file.

It also prints the entry count per family with the anchored and theory-derived
split, which is the table to read after any change.

## 7. What version 0.1 holds

189 entries over the twenty families: 138 anchored and 51 theory-derived, with
81 resting on one subject's anchors. The families the corpus cannot reach are
the ones with the most theory-derived entries -- requests and refusals,
approach and initiative, decision and commitment, the picture of another
person -- and that is a statement about a solo broadcast with no second person
in the room, not about the two people in it.

The loss ledger's coverage, the share of each source's real mechanisms that
some entry can express, against the evaluation plan's 90% bar: the scope
document's own 128 candidates 100%, the extracted candidates 98.4% (121 of
123), the authored candidates 100%, the authored mechanisms of the people
around the first character 100% of the 58 the inventory does not call a
moment, and the first character's bible read as mechanisms 100%. The two
extracted candidates that are lost are one function counted in two families: a
word doubled at a feeling's peak, which is a form with no function of its own
and belongs to the marker battery.

The 128 candidates are carried by 117 distinct entries: fourteen entries carry
more than one candidate, because the scope names the same trigger twice under
two descriptions (the poke when he goes quiet and following up an unanswered
question are one silence), and eight candidates take two entries each, because
what the scope names as one behaviour has two triggers under it. The ledger's
scope table gives the reason on every such row. One case is the owner's to
overrule rather than mine: a refusal that lands flat with its hedges outside
it, which names the shape of a refusal rather than a second trigger and is
therefore held as a surface form of the refusal that stays in the room.
