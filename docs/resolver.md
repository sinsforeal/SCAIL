# Deciding which work he means

Spec for `sim/resolver.py`, the resolving half of `sim/watching_him.py`
(`parse_file`, `parse_special`, `path_marks`), `AnimeKB.resolve_candidates` /
`resolve_strict` / `resolve_special` / `entry`, and the id-aware key in
`sim/recap.py`. PROJECT §12.12 is the summary; the dated log is HISTORY §12.12
and §11.3.

## 1. The question, and why it is three questions

He opens a file. Before anything about it can reach her, three things have to
be decided, and they are decided in different places because they are
different kinds of question.

**Which work is it.** A fact, and the machine holds every piece of evidence:
the folder the file sits in, the season number in the filename, the episode
number, each candidate's episode count and edition on his own list, and the id
his list logs a few minutes later. This is code's, in one parser and one
ranked resolver.

**Is a fetched page about that work.** Mostly arithmetic -- a one-episode work
has no episode 2 and no next-episode preview -- and where arithmetic runs out
it is a reading of the page's own text.

**Which of her remembered rows is about this moment.** On the reply path, so
it is code's too: one shared content word, a cap on rows that arrived on a
cosine alone, each row's own mean cosine subtracted (`docs/memory.md` §4).

Only the residue of the second question, and the ties of the first, are a
model's. That is the `which_one` role, and it answers with an id out of a
table code built.

## 2. What the machine already knew and was not reading

The fault this was built for: he opened
`D:\Videos\Example Show\OVA\Example Show - S00E01 - OVA.mkv`, and the second
character told him the plot of a different work with full confidence. Every
piece of evidence was on the disk.

* `parse_file` called `ntpath.basename` and threw the folder away. The folder
  said `OVA`.
* `_SEASON_EP` matched `S00E01`, did not capture the season and returned
  episode 1. Season zero is the specials season in the naming convention his
  library uses.
* MyAnimeList gives the 2006 one-episode OVA (1480) and the 2007 26-episode
  television run (2604) the identical Japanese title エグザンプル, and his
  mirror holds `ova, 1, summer 2006` against `tv, 26, summer 2007`.
* `resolve_strict` walked his titles in the order sqlite returned them and
  took the first row that matched either of its two rules, so `Example Show`
  inside `Example Show OVA` at a length ratio of 0.73 answered for the
  television series -- and every `Example Show - S01E<n>` he played resolved to
  a work with one episode.
* The shared page store was keyed on the Japanese title and the episode
  number, so both works hashed to one key and the one row that existed was
  the series'.

## 3. What code decides

### 3.1 The whole path, and season zero

`path_marks(path)` reads the FOLDERS: a segment of `OVA`, `OAD`, `ONA`, `SP`,
`Special`, `Specials`, `Season 0`, `Season 00`, `S0` marks the file as a
special, and `Season N` gives the season. The innermost segment wins, because
a path runs from the general to the particular.

`parse_file` declines a file the folders mark as a special and a file numbered
in season zero: it answers `(None, None)`, which is what lets `parse_special`
and `AnimeKB.resolve_special` have their turn. That route existed all along
and its own docstring said what it was for; it never ran, because `parse_file`
answered first.

`parse_special` reads three markers in order -- the `- OVA` word at the end of
the name, a season-zero number, the folder -- and STRIPS a trailing
`- S00E<n>` off the base title, because `Example Show - S00E01` matches no
special on his list and `Example Show` matches the one he watched. Where no OVA
word follows it, the season-zero number is the special's own number.

### 3.2 The ranking

`AnimeKB.resolve_candidates(term, ep=None, kind="")` returns every entry on
his list the term could mean, best first, each with the rule that matched it:

1. **the title as written** -- case and runs of space levelled, nothing else.
   This is the tier that separates `K-On!!` from `K-On!`: the normalisation
   strips the punctuation that is the whole difference between a sequel and
   its parent, and eighteen of his 702 titles used to resolve to a sibling
   for exactly that reason.
2. **the title with its punctuation out** -- the old exact rule.
3. **a distinctive phrase inside a longer title**, ranked by closest length
   first, with the old floors (six characters, a ratio of 0.6).

`ep` DROPS a candidate that cannot have that episode: a one-episode OVA is
not the twenty-fifth episode of anything. Three of the 26 plays in one week
asked for an episode the chosen work does not have and nothing looked.

`kind` is a hint -- `special` for a file the folders mark as one, `tv` for a
numbered season -- and it orders candidates inside a tier rather than dropping
any, because his own naming is looser than the mirror's.

`resolve_strict` returns the top candidate when the ranking is decisive and
**nothing at all** when it is not (`AnimeKB.ambiguous`: the top two matched
the same way and neither is nearer). Silence costs one remark she never
makes; a wrong answer costs a synopsis in the shared store, a digest, a
judge's verdict, a thing she knows by name, a fact about him and a sentence to
him that he can see is false.

### 3.3 The id from his list beats the parse

His list is exact and late: it logs the episode with the show's own id,
typically half an hour after he pressed play. So a play resolved from the
filename ALONE waits `watching.confirm_minutes` for it
(`WatchingHim._await_id`): the player's cursor is put back so the next poll
finds the same open again, exactly as a too-short open does. When the id
arrives and differs, the id wins and the log names both. Past the window the
parse stands.

A list row counts as the same watch only when its own id is one of the works
the filename could mean, or when the filename's title is inside the list
row's title. The episode number alone is not enough: he marks episodes of
several shows in an evening and two of them can share a number.

### 3.4 A page that cannot be about this work

`Recap.past_the_end(text, ep, total)` rejects a page that names an episode
this work does not have, and -- for a one-episode work -- a page carrying a
next-episode preview (`次回予告`, `次回、`, `次回は`, `つづく`). The existing guard
(`Recap.wrong_episode`) only fires when a page names ANOTHER episode of the
same entry by its subtitle, so a namesake's episode 1 walked past it: the page
that reached her was the television series' first episode and ended in a
preview of its second.

### 3.5 A page is named by the work, not by a title

`Recap._shared_key` is `anime|mal:1480|ova|ep1` when an id is known and the
old `anime|<title>|ep<n>` when none is (her own watchlist carries no ids).
Her save's `recaps` table has an `aid` column with the same meaning, added
under a pragma guard. A reader with an id never reads a row belonging to
another id, and reads a row filed under a title only when that title cannot
mean anything else (`Recap._resolves_to`: his list holds exactly one entry of
that name and it is the one asked for).

The edition in the key comes from one place (`Recap._edition`, his own
mirror through the `anime_kb` wire), so two callers naming one work cannot
produce two keys.

### 3.6 The line she reads says which edition

`WatchingHim.situation_lines` fills `{ed}` in both programs' wording tables
(`tomoe/words.py`, `resident/words.py`) from the work's own row on his list:
`(the OVA, 1 episode, summer 2006)`, and nothing at all for an ordinary
television run, which needs no label. Her rejected first draft on the day of
the fault had the edition right, from the machine-telemetry line, and the
rewrite fell back on the watching line, which said only "episode 1".

## 4. What the model decides

### 4.1 The role

`which_one`, `prompts/which_one.txt`, on the cheap model both characters use
for mechanism roles. The prompt names nobody and says nothing about how she
sees him. It is handed a question, what is known about the moment, and a
table of at most `which_one.max_candidates` rows: an id, what that candidate
is (edition, episode count, season) and the first 300 characters of its own
text, quoted as it stands in whatever language it is in. Nothing of her
interior goes in.

It answers one JSON object: `chosen` (an id from the table, `null` for none
of these, or `"unsure"` for fetch nothing and wait), `confidence`, and `why`
in one sentence. **Ids only, never text**: the caller looks the id up in its
own table and uses its own object, so nothing the model writes can reach her,
and `why` goes to the log and the store and nowhere else.

### 4.2 When it is asked, and when it is not

Code decides, narrowly. Only when more than one candidate survives every
deterministic filter, or the parse is ambiguous and his list has no id yet;
never when his list has already named the id; never twice for the same
question. Two callers, both on threads that are already fetching:
`WatchingHim._work` and `Lookup._which_work`. **Never in a reply path**, the
same rule `works.her_part_verdict` is written to.

### 4.3 What is thrown away

Code's own ranking stands, and nothing waits, when the answer does not parse
twice (`LLM.call_json`, `api.json_retries`), when `confidence` is under
`which_one.min_confidence`, when the id is not in the table it was handed (an
entry the episode count had already ruled impossible, or one invented), and
when the call has not come back inside `which_one.timeout_seconds`. The call
finishes on its own after a timeout and the paid answer still reaches the
store, because the store is written inside the call rather than held by the
waiter.

### 4.4 Where the answer is kept

**The identity of a work is a fact about the world, so it goes in the
machine's shared store** (`machine/retrievals.py`, pool `resolved`) under a
key that names the question and never the character --
`play|skygirls|ep1|special|1480+2604`, `named|kanon|ep2|144+1530` -- with the
model's slug on the row, so a re-decision by another model is a new row. Both
characters read the one answer, and `get_or_fetch`'s claim keeps two
processes that notice the same play in the same minute from asking twice.

**A question about HER RECORD must never go there**, because its candidates
are her memories and her facts, and a key naming them would put one
character's record in a file the other reads. `Resolver.record_relevance` is
the only writer for that answer and it writes to her own save (kv
`resolved_relevance`). Today the relevance question is decided in code on the
reply path and nothing calls it; it exists so that the invariant is in the
code rather than only in this document.

### 4.5 What it costs

Measured against the cheap roles already running: about $0.0002 a call. Code
asks it three to six times a day across both characters, so under a cent a
week. One real call, timed: 785 tokens in, 65 out, 1.2 seconds.

## 5. The log

One `[resolver]` line per decision, whoever made it: the question, every
candidate with its id and edition, what was chosen, what was dropped and why,
whether code or the model chose, and the model's own sentence when there was
one. Before this the only trace of the wrong choice was a line about episode
titles in the middle of a fetch, and nothing at all in the line she read.

The other `[resolver]` lines: his list naming a different id from the parse's,
a stored page refused because it was filed under a title rather than an id,
and a title that could be two works of his, which is why nothing is said about
whose work it is.

## 6. What must not change

* It never stops her. No answer of its is a veto on a reply, a bubble or a
  send, and every failure leaves code's own choice standing.
* It never edits her words. It returns ids from a list it was handed.
* It never fetches inside the reply path.
* The prompt carries no person (`tools/neutral_gate.py`) and the shared code
  names nobody (`tools/character_names.py`, `tools/sight_words.py`).
* The decision is written to the store the moment it exists.
* The relevance decision over her record is never written to the machine's
  store.

## 7. The repairs at boot

Two one-off passes in `sim/repairs.py`, each flagged in the save so the second
boot does nothing, with what changed copied to `data/retired/<timestamp>_*`
first.

`key_pages_by_id_once` writes the work's id onto every row of her own
`recaps` table whose title his list resolves without ambiguity, and moves a
row in the machine's store only when its title is carried by more than one
entry of his list -- the collisions, which is the whole of the fault. A row
under a title only one work has stays where it is and is still read by a
caller with no id, so nothing that was paid for is paid for twice.

`drop_wrong_editions_once` takes the part off a thing she knows by name whose
text is another edition's story: two ids holding byte-identical text are one
page filed twice, and the row whose work has fewer episodes than the one the
page belongs to is the wrong one. `KnownThings.remove_part` drops the row with
it when no part remains.
