# `machine/retrievals.py` -- one store of what was fetched about the world

Spec of record. Summary: PROJECT.md §11.6 (the sensors entry's last
paragraph). Dated notes: HISTORY.md (the shared-store entry). The build and
its measurements: `data/retired/20260904_retrievals/REPORT.md`.

## 1. Purpose

Two characters run as two processes over one library, and both watch the
same machine. A page about an episode he played, that page condensed by a
role that names nobody, the verdict between two candidate pages, the web
search behind a lookup, a game's database card: these are the same whoever
is looking. Before this store each character fetched, digested and judged
them in her own save, so the second character's five synopses of a show
were not the first's, and both bots polling his player would fetch the same
episode inside the same minute. His rule: **one shared flash call, a shared
database of retrievals, the same architecture wherever it applies without
causing issues.**

The store is the machine's, like the collector and the image tag store, and
holds what was fetched about the world. What a character MADE of it -- her
own record of what she was told, her reading of it in her own words, the
things she knows by name, her memories and facts -- stays in her own save.
That is the line the isolation rule already draws (`tools/isolation.py`,
`sensors.retrievals_db` in its machine table).

## 2. Schema

One SQLite file at `sensors.retrievals_db` (default `data/retrievals.db`),
WAL mode so two processes read while one writes, a busy timeout, one lock.

    retrievals(kind, key, model, text, source, meta, fetched_at, judged, by)
        PRIMARY KEY (kind, key, model)
    inflight(kind, key, started, by)

`kind` is the pool (`recap`, `vn_card`, `resolved`, ...). `key` names the
THING -- an anime id and episode, a URL or a page's normalised title, a
database id -- and never the character. `model` is who wrote the text, so a
re-digest by another model is a new row rather than a silent overwrite. `by`
is the character id that fetched it, so a reuse can be attributed in the log.

**A page's key names the WORK, not a title** (`Recap._shared_key`):
`anime|mal:1480|ova|ep1`. A title is not a name for a work -- MyAnimeList
gives a 2006 one-episode OVA and a 2007 26-episode television run the
identical Japanese title -- so `anime|<title>|ep<n>` made two works one
thing, and the row that existed was the series'. The old form is still
written and read when there is no id to name, which is what her own
watchlist has; a reader that knows the id will not accept a row filed under a
title unless that title cannot mean anything else. The edition in the key
comes from one place, his own mirror, so two callers naming one work cannot
produce two keys. `docs/resolver.md` §3.5.

**The `resolved` pool holds a decision rather than a fetch**: which of
several candidate works a play or a typed title means, as an id, with the
candidates, the confidence and the reason in `meta`. Its key names the
question -- `play|skygirls|ep1|special|1480+2604` -- so both characters read
one answer and neither pays for it twice. A question about a CHARACTER'S OWN
RECORD (is this memory about this moment) is never keyed here: it belongs in
her save, and `sim/resolver.py record_relevance` is its only writer.

## 3. The claim: one call, whoever gets there first

`get_or_fetch(kind, key, fetch_fn, model, ttl=None)`:

1. A stored row is returned at once.
2. Otherwise the caller claims the key (`INSERT OR IGNORE` into `inflight`).
   If the claim is hers, she fetches; the row is written the moment the
   answer exists, never held, and the claim is cleared in the same
   transaction as the write (`finish`).
3. If another process holds the claim and it is younger than
   `sensors.retrievals_inflight_stale_seconds` (600), she wait-polls up to
   `retrievals_inflight_wait_seconds` (120) for the row and reads it.
4. A claim older than the stale window is taken over, because a bot is
   stopped with `Stop-Process -Force` and leaves its claims behind.
5. A fetch that found nothing marks the claim `failed` rather than clearing
   it, so everybody waiting on it stops waiting at once and goes and looks
   for itself instead of waiting out the timeout. The next process to reach
   the key takes a failed claim over, and `sweep_claims` at boot removes it.

Three log lines make the saving visible: `[retrievals] <kind> <key>:
fetched by <char>`, `... reused (fetched by <other> Nm ago)`, `... waited
Ns for <other>'s fetch`.

## 3b. The claim over a whole reading-up

**What has to happen once for the machine is the QUESTION, not one fetch of
one address.** `get_or_fetch` covers a single call behind a single key, which
is right for a page condensed by a role or a game's card; it is not enough
for an episode, because the candidate set comes from a live web search per
process and three processes searching for one episode get three different
sets.

The three characters who watch his media player once resolved episode 5 of
one show at 17:29:57, 17:30:09 and 17:30:20 on the same afternoon and each ran
her own search (the day and the receipts: HISTORY.md, one reading-up per
episode). The first character's set held a page with a section for that
episode; the second character's held five pages without one. The store is
written only after a search succeeds, so the second character's search --
begun nine seconds before the first character's page was written -- found
nothing to reuse, and her record of that episode is empty. A nine-second race
decided which resident learned what the episode was about.

So `sim/recap.py:synopsis` holds the claim across the whole path. Four calls
on the store, and any caller that does its own fetching uses the same four:

    mine, held = retrievals.claim(pool, key)
    if not mine:
        row = retrievals.wait_for(pool, key, held=held)   # the page, or None
        ...
        mine, held = retrievals.claim(pool, key)          # take it over
    ... search, fetch the pages, digest each, judge them ...
    retrievals.finish(pool, key, text, ...)               # or .fail(pool, key)

`claim` is the same protocol as before, plus: a claim marked failed is ours
to take. `wait_for` polls for the row, stops the moment the claim is marked
failed, and reads the store ONCE more when the claim has simply gone --
because the write and the release are one transaction, a claim that has
disappeared means the row is already there. A waiter that gets the page
copies it into her own record (`Recap._from_shared` -> `_adopt`): she was
told the same thing at the same moment, and what is hers is the record of
having been told it.

The key is the one `_share` writes under, computed the same way from the same
entry (`_shared_key(kind, ja, ep, aid, edition)`), so a waiter is polling for
the row the claimant is about to write and not for a neighbouring key.

## 3c. An episode that came back empty is read again

The claim removes the race; it does not fill a record the race already
emptied. `WatchingHim.owed` (PROJECT §12.12) is the other half: a record with
no digest, no raw page and no mark saying it was recorded without one on
purpose is owed another reading-up, as soon as the shared store holds a page
for it -- which costs a lookup and no search -- and otherwise
`sensors.retrievals_retry_after_minutes` (30) after the last try, at most
`sensors.retrievals_max_retries` (2) more times. The count of readings-up
begun is written on the record as the item is handed over, before the work
runs, which is what stops a search that keeps failing from being run on every
poll for ever.

## 4. What goes through it, and what stays per character

| fetched about the world, shared | made of it by her, per save |
|---|---|
| every page `sim/recap.py` fetches: episode pages, series premises, voice-actor bios, encyclopedia pages, episode-title lists | her `recaps` row: the record of what SHE was told and when; a shared hit is copied into it with nothing fetched |
| each page's digest (`watching_digest`) and each judge verdict (`digest_judge`) | -- |
| the arriving lookup's web search (one-month window) and the character-page condensing (`character_digest`) | the lookup's classifier over his message and her own reading of the result (`lookup`, `lookup_gist`): both carry her name and viewpoint, neither is shareable |
| a game's card (`vn_card`, `docs/eroge.md`) | the game as a thing she knows by name, her memories, her facts |

`sim/watching_him.py` needed no change: its fetch, digest and judge all run
through `Recap`. Nothing about her -- her cue, her reading, her record of
being told -- ever enters the store.

## 5. The migration

`sim/repairs.py share_recaps_once`, keyed on kv `recaps_shared_once`, runs
once per character at boot: every row of her per-save `recaps` table is
copied into the store if the store lacks that key, newer wins per key,
`judged` kept. On the two live saves that was seven rows each, no key held
by both, so the second character's Mitsudomoe synopses were the first's the
moment both had booted. The log line is `[repair] N of M page(s) about the
world copied from her save into the machine's store; it now holds K`.

A second pass re-files what the first carried across under the WORK rather
than under a title (`repairs.key_pages_by_id_once`, kv
`pages_keyed_by_id_once`): her own rows get the work's id where his list
resolves the title without ambiguity, and a row in the store moves only when
its title is carried by more than one entry of his list. Everything else
stays where it is and stays readable, so no page is fetched again for the
sake of a key. `docs/resolver.md` §7.

## 6. Config

`sensors.retrievals_db`, `sensors.retrievals_inflight_stale_seconds`,
`sensors.retrievals_inflight_wait_seconds` (which is also the timeout on a
claim held across a whole reading-up), `sensors.retrievals_retry_after_minutes`
and `sensors.retrievals_max_retries` (the repair in §3c). The store is built once in the
shared runtime, before the program is asked, and reaches `Recap` and
`Lookup` as a declared wire (`retrievals`); a wire still None after the
build fails smoke.

## 7. Invariants

- The key names the thing, never the character.
- A row is written the moment the answer exists.
- A failed fetch leaves no row and no claim.
- Nothing a character made of a retrieval is in the store.
- The store's path is in the isolation tool's machine table; a per-person
  path there is a fault.

## 8. Tests

`tools/retrievals_test.py` (`--store`, in smoke): one fetch serves two
characters; an arrival mid-fetch waits and reads rather than pays; a
different model is a different row; a failed fetch leaves no row and no
claim; a stale claim is taken over; **three threads racing one episode key
run one search between them and all three hold the result**; and a claimant
whose search found nothing releases the claim marked failed, so the next one
searches immediately rather than at the timeout (measured 0.6 s of a 6 s
timeout). `tools/isolation.py` passes with the new path.
