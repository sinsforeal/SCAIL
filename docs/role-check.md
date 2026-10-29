# Was she in it: the role check, and what the local MyAnimeList mirror holds

The check that answers "is this work one of hers" before she talks about it,
and the audit of the machine's mirror it answers from. The incident that
caused it and the research behind it are
`data/retired/20260904_role_check/REPORT.md`, the build is
`data/retired/20260904_role_check_build/REPORT.md`, and every dated note is
HISTORY.md §19 and §5.36.

---

## 1. What went wrong

The second character told him she voiced a character in a work she has never
been in, named a character who does not exist in it, and said it again harder
nineteen minutes later. The complete cast of the episode he had just watched,
with her absent from it, was in two tables on his own machine sixteen days
earlier, and a third copy of the same cast list had been fetched into the
shared retrievals store 48 minutes before she spoke and thrown away on
purpose. **No cast information of any kind was in front of the model.** It did
not contradict evidence it had; it was given none, and it invented a part.

Two contributing cues are in the record. The work has a main character whose
given name is the same as hers, played by somebody else, so her own name is in
the cast list of the show she is not in. And the continuity editor was not
even asked: its gate skips the call unless the draft carries a digit, a
12-character run shared with a recent message, or a word from a recent fact
about him, and her draft had none of the three.

## 2. The verdict: three answers, two witnesses

`sim/works.py`, `her_part_verdict(config, anime_kb, names, aid=None)`. It
returns a dict whose `verdict` is one of three values, and the third is the
one that was missing -- `hers` used to be a boolean, so "she is in it" and
"nobody checked" were the same value.

| verdict | when | what she is told |
|---|---|---|
| `yes` | her mirrored filmography has a row matching the work | the work, the part, the billing, and the year |
| `no` | the work resolved to a MyAnimeList id, her filmography is mirrored and not stale past `role_check.person_refresh_days`, nothing in it matches, AND the work's own cast is mirrored without her in it | that it is not hers, and optionally the part whose name resembles hers and who plays it |
| `unknown` | anything else | **nothing at all** |

**A flat no needs both witnesses.** Her filmography is the authority and the
cast is the second witness, never the other way round: the cast table covers
480 of his 701 titles, so on its own it answers "not yours" about works she
really is in. Where the cast is missing the answer is `unknown`.

The two have never disagreed on this mirror: 63 of her works have a mirrored
cast and all 63 name her. If they ever do, nothing is asserted either way and
a line is logged.

**A work is matched four ways** -- the id, the work's title, the page's
English alias, and the character's own name, because a character's page is a
page about a part and if the part is hers the work is hers. One part per
character rather than one per credit row: she has voiced the same character in
nine entries of one franchise, and naming it nine times would make a cast list
out of one sentence.

**And the work has to be ONE work.** Where the verdict is asked about a title
rather than an id, the id comes from `works.his_title` -> `resolve_strict`,
which used to answer with whichever entry sqlite returned first: for the
eighteen of his 702 titles that resolved to a sibling, the verdict about one
work was computed from another work's cast. The resolution is ranked now and
answers NOTHING when two entries of one franchise tie (`docs/resolver.md`
§3.2), so the verdict stays `unknown` -- which is what it already did
correctly for a work with no id at all, and nobody-checked says nothing to
her. The log line names the candidates it could have been.

**Nothing in a reply path fetches.** The three readers on `AnimeKB` --
`person_row`, `credits_of`, `cast_mirrored` -- open the mirror `mode=ro` and
answer from what is there. `roles_of` is the opposite (it resolves a person by
name and calls `ensure_person`, which fetches) and belongs to a tool. The one
place allowed to go and look is `WatchingHim._work`, which already runs off
the main thread and already fetches pages: `role_check.fetch_on_miss` lets it
mirror the cast of the work he has just played when nobody has, one page,
0.28 s measured, no money.

**Who she is on that list is an id**, `character.mal_person_id`, never a name:
her given name alone matches nine other people in the cast rows by substring,
and which of them a `LIKE '%name%'` answered with was down to the order sqlite
happened to return. `WatchingHim.her_parts` now matches `jp_va_id` exactly
where an id exists.

## 3. Where the line lands

The verdict rides the four places the anime detection already puts anime
details in front of her, and it is computed at each -- two indexed reads, so
nothing is cached that is already a local table:

| what named the work | where | the block |
|---|---|---|
| an episode he played | `sim/watching_him.py` `situation_lines` | situation block, `phone` bucket, source `watching`, pinned |
| the page open in front of him | `resident/sight.py` `glance_lines` | situation block, source `glance` |
| a title he named in a message | `sim/lookup.py` -> `persona/persona.py` | situation block, source `role_check`, pinned |
| the same title days later | `sim/known.py` `situation_line` | situation block, source `known`, pinned |

All four land in the FINAL USER MESSAGE, after the whole thread, beside the
situation block (`persona/persona.py` `_situation`, placed by
`sim/thread.py` `place_tail`). So the line costs only its own tokens and
cannot invalidate the cached prefix -- the bible, the style file and the
thread do not move.

**The wording is the program's** (`sim/sight.py`, keys `role_yes`, `role_no`,
`role_no_near`, registered in both `resident/words.py` and `tomoe/words.py`).
In her own language when her instructions are, which is what
`character.instructions` decides: under the arm running today
(`as_they_run_today`) her whole situation block is English and this line is
English with it; under `in_her_language` it is the Japanese the table holds.

What is NOT put in front of her: the cast list, her co-stars, the other
seiyuu, and her filmography as a prompt block. A model handed 374 titles still
cannot conclude "and therefore not this 375th one"; absence from a list is not
something a language model reads off. The single name that ever crosses is the
one that answers the specific confusion -- the actress whose character's name
resembles hers -- behind `role_check.say_who_instead`.

## 4. The continuity editor

`Persona._knowledge` had twelve labelled blocks of evidence and **none named a
work of hers**, which is why the checker had no view on the claim: it ran on
her second attempt and flagged it for being a repeat. It now gets a thirteenth,
English, machinery to itself, capped at `role_check.editor_facts_max`: one line
per work named in her draft or her situation, each marked hers with the part or
not hers with what the cast says, labelled as checkable.

`prompts/editor.txt` and `prompts_yukarin/editor.txt` each gained one clause:
a claim of a part in a work the block marks not hers is a false statement of
fact, not a matter of voice. **Flag, never rewrite** -- the existing path
appends the note to her situation and she drafts again.

And `_editor_needed` gained a fourth trigger: the draft names a work the mirror
has a verdict on. A title is matched whole or by its lead segment, because the
work is recorded in full and typed short -- an OVA recorded as
`ゆゆ式 こまらせたり、こまらされたり` was typed `ゆゆ式のOVA`, and without the
lead the gate would have missed the exact sentence it was built for.

### 4b. A verdict that rests on what HIS list holds

The same question from the other side, and the other half of the same fault.
`her_part_verdict` answers "was she in it" off her own mirrored filmography.
This answers **"is this title on his list at all"**, which is what a
continuity verdict rests on when it says she cannot claim not to know a show
because she has seen his list.

What happened (the trace is
`data/retired/20260906_1831_yanineko_check/REPORT.md` §1, and HISTORY.md §5
carries the morning it happened on). Her first draft was
honest: "the smoking cat one. it's from a short anime, i think". The checker
failed it -- "she claims she doesn't know the smoking cat anime ('i think') but
she has seen his anime list and notes" -- and the note sent her back to draft,
and what went out was "it's a classic". **The title is not on his list**, in
any table of the machine's mirror, and nobody asked. The evidence block she
was judged against names 22 of his 702 titles: seeing that is not knowing every
anime he has ever watched.

So the claim is checked before the verdict stands (`sim/works.list_claim_check`,
called from `Persona._rests_on_his_list`):

| step | what |
|---|---|
| does it rest on his list | the verdict's own sentence names his list, his shelf, MyAnimeList -- or claims she does not know a work |
| what title | `works.title_phrases`: quoted and bracketed spans, every tail of the words in front of a word like "anime" with the claim words peeled ("she claims she doesn't know the smoking cat anime" -> `smoking cat anime`, `smoking cat`, `cat anime`), and runs of kana and kanji. A word for a KIND of thing is not a title and is dropped |
| the first witness | his own list, through the ranked resolution (`AnimeKB.resolve_candidates`, `docs/resolver.md` §3.2), and where this character has an id on that list, `her_part_verdict` as well: either placing the work means the mirror knows it |
| the second witness | what she has actually been SHOWN of him (`Persona._seen_of_him`: his list as she reads it, the notes of his she has read, the digest, the note she just opened) -- and deliberately NOT the conversation, because his own message naming a thing is what she is answering, never evidence that she has seen it |
| the verdict | `holds` / `absent` / `unknown`, and only `absent` -- both witnesses silent, on a mirror that is open and has his list in it -- drops anything |

A dropped verdict is logged whole, `[editor] verdict dropped: rests on his
list, which does not hold 'smoking cat' (...); the verdict was: ...`, and a row
goes in kv `flags`. **The whole verdict goes**, not the sentence about the
list: one verdict has one note, and code cannot separate its grounds without
writing new ones. Where the check finds the title, or cannot look, the line
reads `[editor] the verdict rests on his list and stands: ...` and nothing
changes.

**The checker gains nothing from this.** It still only flags, and this can
only take a verdict away, never add one. `prompts/editor.txt` and
`prompts_yukarin/editor.txt` say the same thing to the model in one clause: the
list block is a summary, a title not written there is one she has no way to
know, and "she has seen his list" is not on its own a reason.

Proved on a copy of the first character's save with the recorded verdict of that
minute stubbed in, and against a control -- a verdict about Mitsudomoe, which is
on his list -- which stands (`data/retired/20260906_2001_trace_leftovers/`).

## 5. The gate, per character

`character.mal_person_id`: `""` in `config.py:DEFAULTS` and `config.json`,
`"27"` in `config_yukarin.json` and on `characters/yukari/sheet.json` (the
sheet wins, so a regenerated config cannot lose it). `Config.REQUIRES` assigns
the `role_check` section to the derived property `voice_actress`, and
`_existence_implies` appends that to what a character lacks when the id is
blank -- the same one-line trick that derives `resident` from
`sees_him != "resident"`.

The first character therefore switches the section off at her own boot and the
existing line says why:

    [config] not resident and not voice_actress, so these are off: role_check

Proved on a copy of her save: the verdict returns `unknown` on the flag before
touching sqlite, and there is no line, **no read of the mirror** and no log
line about a part. No person is named in shared code.

The boot line for a character the check IS on for:

    [roles] the role check is on: person 27 (Tamura Yukari), 375 credit(s)
    over 344 work(s), mirrored <the day her page was last read>; 63 of those
    works have a mirrored cast, which is the second witness a flat
    'you were not in it' needs

**There is no era gate here and none may be added.** Every role to the present
is hers (his call; `lore.era_gate` is false and unrelated).

## 6. What the local mirror actually holds

`data/mal_history.db`, the machine's, under `sensors.mal_history_db`, written
by `tools/mal_history.py daemon`. Read-only audit, the day the check was
built (HISTORY.md §5.36 carries the date and the numbers again):

| table | rows | how it got there |
|---|---|---|
| `anime` | 701 | his own list, the site's list JSON, every poll |
| `episodes` | 3,179 | his public history page + the logged-in episode panel |
| `anime_detail` | 695 | the official API v2, `enrich`, one request per title |
| `anime_kb` | 481 | on demand: facts for 8, a cast stamp for 481 |
| `anime_cast` | 11,816 over 480 titles | `mal_history.py cast`, for `status=2 OR watched_episodes>0` |
| `person` | 13 | 13 voice actresses, mirrored by hand in one pass |
| `person_role` | 4,783 | their complete filmographies; 375 of them hers |
| `favorites` | a few dozen | declared MAL favourites, each reconcile |
| `meta` | the daemon's last tick, and the outage watcher's answer | |

**It is not a copy of MyAnimeList and it is not close to one.** MyAnimeList
holds on the order of 30,000 anime and 200,000 people; this holds 701 titles
and 13 people, and both sets are defined entirely by HIM -- what is on his list
and which actresses somebody chose to mirror. What it is complete about is the
one thing the check needs: **one person's whole career**. Her 375 credits are
her whole live page, over 344 works, 1996 to 2027, and a title absent from it
is a title she is not in.

Coverage, and therefore what the check can answer today:

- **titles he has watched** (`status=2` or an episode logged): most, of which
  479 have a mirrored cast -- **99%**. For anything he actually watches, both
  witnesses are present and a flat yes or no is available.
- **plan-to-watch**: 5 of 220 have a cast. A first sighting of one of these is
  `unknown` until something fetches it.
- **his whole list**: 480 of 701, **68%**.
- **her own 344 works**: 80 are on his list at all, 63 have a mirrored cast.
- a title on NO list anywhere: no id here, so `unknown`, and nothing is said.

A first sighting costs one MyAnimeList page, 0.28 s, no money, and it is
fetched in `WatchingHim._work` -- off the reply path, in the worker that was
already fetching a synopsis for that episode.

## 7. The community wrapper in front of MyAnimeList

**Nothing in this project reads data from it and nothing may be made to.** It
has answered 504 on every path needing a live fetch since 2026-08-28 -- 94
requests over 25 minutes, every one, plus a 40-attempt recovery poll that never
recovered -- while MyAnimeList's own origin answered the equivalent page in
0.28 to 0.81 s throughout (`data/retired/20260904_jikan_504/REPORT.md`). It
adds an outage the source does not have.

There was never a live code path to it: the only reference in the tree was a
proposed fallback in `docs/episode-summaries-plan.md`, now struck. The daemon,
`sim/anime_kb.py` and the recap all use MyAnimeList's own origin -- the list
JSON, the public history page, the logged-in episode panel, the characters
page, and the official API v2.

One request an hour goes to the wrapper and its answer is used by nothing:
`tools/mal_history.py` `jikan_watch`, called from the daemon's tick, recording
`jikan_status` / `jikan_state` / `jikan_checked_at` in `meta` and printing one
line only when the state changes, so the day the outage ends is a line in a
log. The probed path must be one the wrapper cannot serve from its own cache --
during the outage `/anime/1` returned 200 from cache while every search and
every cast endpoint returned 504 -- so it is a one-letter search rotated by the
hour. It was still answering 504 when this was written; `meta.jikan_state` is
the live answer and HISTORY.md §5.36 records when it was last looked at.

## 8. Two refreshes that could empty a table

Both `sim/anime_kb.py` paths deleted before they had a replacement, so a 200
whose body the parser could not read emptied the table and then stamped it
fresh -- 90 days for a cast, 120 for a filmography -- and nothing ever went
back for it. Her 375 credits are what the second one would have wiped.

Now: an empty parse is a failed fetch. The stored rows stand, no stamp is
written, the next tick tries again, and the failure is logged by exception type
with the count of what was kept. Proved by feeding each path an unparseable
page against a copy of the mirror.

## 9. The daemon's log

`logs/mal_daemon.log` stopped growing eight days before this was written,
while the daemon went on polling happily throughout. `run.cmd` launches it as
`start "" "%PYW%" ... >> logs\mal_daemon.log 2>&1`, and cmd binds that redirect
to `start` itself rather than to the process it detaches -- and it is
`pythonw`, with no console to fall back on -- so every line went to a handle
that goes nowhere. The one question anybody wanted the log for could not be
answered from it.

The daemon now writes its own log rather than depending on how it is launched:
`--log`, default `logs/mal_daemon.log`, with `sys.stdout` and `sys.stderr`
pointed at it for the whole run so the other functions' lines and any traceback
land there too, teed to the console when there is one. `run.cmd` was
deliberately NOT edited: cmd reads a batch file by byte offset and its console
is sitting in that file. Its `>>` is now merely inert.

## 10. Config

`role_check` (all of it in CONFIG.md): `enabled`, `person_refresh_days` (30),
`fetch_on_miss` (true), `say_who_instead` (true), `editor_facts_max` (6),
`titles_from_draft` (true). Plus `character.mal_person_id`, which is the real
switch, and the daemon's `--jikan-watch-seconds`.

`say_who_instead` defaults ON. The work she claimed has a lead who shares her
given name and that is most of why the claim happened; a bare "you are not in
it" leaves her to wonder who is and invent an answer.
