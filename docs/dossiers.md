# One file per play: what it joins, from where, and what it looks like

`machine/dossier.py` writes one Markdown file for every episode he finishes,
and rewrites a rolling list of the last ten plays beside it. Config section
`dossier`; the spec of what a play IS is `machine/plays.py`.

Nothing in a dossier is new information. Every piece of it was already on disk
in one of four stores and nothing joined them, so answering "what did he just
watch, and what is his history with it" meant opening all four by hand. It
makes no model call and, apart from two small page reads named in section 5,
no network call either.

## 1. Where it runs, and why there

Three character processes tail the same media-player history. A dossier built
inside a character's loop would be built three times, in three saves, by three
programs, and each of them would pay for the same two page reads.

So it is the machine's, and it is called by the MyAnimeList mirror daemon
(`tools/mal_history.py daemon`, `_build_dossiers`) -- the one process per
machine, already running every five minutes, already the writer of the list
mirror. Its failures are swallowed by exception type, like the subtitle
mirror's beside it: the list mirror's own work must not stop because a page
did not answer.

**Built once per play**, keyed on the epoch the file opened at, which both
player logs write from the same call. `data/dossiers.db` holds the marker, so
a restart mid-day rebuilds nothing and a play cannot get two files.

**Built after the play ENDS.** How far he got and how long he was actually in
it are only known then. `machine/plays.py` reads the player's end-of-play
record; where the player has recorded no end -- which is every machine until
`tools/mpv/scail_logger.lua` has written that log once -- the fallback is the
gap to the next file opened, and every line quoting a duration says which of
the two it came from.

**A play under `dossier.min_watched_minutes` is a skim**, not a play: one line
in the rolling file, no dossier. A file that is on nothing in his list -- the
same folder holds music, radio recordings and camera clips -- is listed the
same way, because it has no episode, no cast and no history to join.

**The first sweep on a machine starts where the rolling file starts**, not at
the beginning of three years of history: the horizon is fixed at the tenth
newest play the first time a sweep runs and is never moved. `per_cycle_cap`
plays are built per pass, oldest first, so a backlog is worked off over the
hour rather than in a burst.

## 2. The manual door

    python -m machine.dossier --last            # the newest finished play
    python -m machine.dossier --last 3          # the newest three
    python -m machine.dossier --epoch 1788834607
    python -m machine.dossier --path "...\Show - S01E03.mkv"
    python -m machine.dossier --sweep           # what the daemon does, by hand
    python -m machine.dossier --list            # what has been built
    python -m machine.dossier --force           # rebuild one that is there
    python -m machine.dossier --no-fetch        # leave the two gaps as gaps

`--epoch` and `--path` ignore the horizon, so any play in the history log can
be built by hand.

## 3. What it joins, and out of which table

| section | where it comes from |
|---|---|
| the file, the open and the end | `mpv_history.log` (`epoch\|path`) and `mpv_plays.log`, read by `machine/plays.py` |
| which work it is | `sim/watching_him.py` `parse_file` / `parse_special` and `sim/anime_kb.py` `resolve_candidates`, the same two readings the character-side watcher makes |
| what he played around it | every line of `mpv_history.log` inside `hours_before` / `hours_after`, each resolved the same way |
| earlier plays of the same folder and the same file | the whole history log |
| already finished on his list | `anime.status` and `anime.watched_episodes` against `anime.num_episodes` -- see section 4 |
| the episode's three titles | the retrieval store, `recap` / `eptitles\|mal:<id>\|ep0` -- English, romaji, Japanese, and it says which is missing |
| the judged digest and its scenes | the retrieval store, `recap` / `anime\|mal:<id>\|<edition>\|ep<n>` for the page and its meta, and `page_digest` keyed on the hash of that page for the digest itself |
| the confidence, the sources and which agreed | the same row's meta: `confidence`, `candidates` with a verdict each, `reason`, `anchor` |
| his score, status, note, favourites rank | `anime`, `anime_detail`, `favorites` (`kind='anime'`) |
| every dated episode watch | `episodes` (anime_id, ep, watched_at, source) |
| the franchise | title-stem grouping over `anime` (section 4), with `anime_detail` for studio and season |
| each credited actor | `anime_cast` for the credits, `favorites` (`kind='people'`) for the rank, `anime_cast` joined to `anime` for their other shows and his scores, `person` / `person_role` for a filmography |
| his overall mean | `AVG(score)` over `anime` where a score is set |

Every read of `data/mal_history.db` and `data/retrievals.db` is
`mode=ro`. **Nothing here writes the list mirror**: the daemon owns that file
and holds it open, so the two page reads go into this module's own store.

## 4. Two rules worth stating

**Already finished is computed, never read off a flag.** MyAnimeList carries
an `is_rewatching` field, `sensors/mal_monitor.py` fetches it, and it is true
only while he has gone to the site and marked an entry as being rewatched --
which he does not do. It is not a column on this mirror at all. A play of a
thirteen-of-thirteen show he finished in 2022 therefore read as a first watch
everywhere the flag was trusted. What answers the question is his standing:
marked completed, or every episode marked watched. The dossier prints the
standing and says plainly that the site's own flag answers a question about
what he clicked.

The character-side watcher has a second flag with a third meaning:
`WatchingHim.poll` sets `again` when the same episode key is already in the
remembered set, which is "she has been told about this episode before", not
"he has seen this show before". That one is correct for what it does and is
not the answer to this question either.

**A franchise is grouped by title stem**, because the mirror holds no relation
rows. The shortest title on his list that the played title starts with is the
franchise's name, and everything starting with that name is in it; a stem
under six characters is refused, so a short title cannot swallow the list. The
table is ordered by when each entry came out -- the year read out of the
season string and the season turned into its place in the year, because `fall
2007` sorts alphabetically into nonsense.

## 5. The two page reads

Both are capped, cached in `data/dossiers.db` with a time-to-live
(`fetch_ttl_days`), spaced by `fetch_delay_seconds`, and logged by exception
type on failure. Both read MyAnimeList's own origin; the community wrapper in
front of it is never used, for the reason `sim/anime_kb.py` gives at the top.

* **An actor's filmography** (`actor_fetch_cap`, default 3, main roles first).
  The mirror holds a filmography for thirteen people against 11,851 cast rows,
  so for everybody else "what else has she done" is his own list and nothing
  beyond it. Parsed with `sim/anime_kb.py` `parse_person`, which is the only
  parser for that page; an empty parse is treated as a failed fetch and
  nothing is cached, so the next build tries again.
* **A missing premiere date** (`premiere_fetch_cap`, default 2). A plan-to-watch
  entry carries no dates on a list at all, so a sequel is a blank row in the
  franchise table until one call to the list interface fills it. Answering
  "still unannounced" is a real answer and is cached as one.

## 6. The files

`reports/dossiers/<YYYY-MM-DD_HHMM>_<slug>.md`, stamped and slugged from the
play's own open time and the work it resolved to, all in machine local time.
Five sections: **The play**, **The episode**, **Your history with the show**,
**The cast**, **What is missing on disk**. The cast section is a table of
every credited actor and a section apiece for `cast_detail_cap` of them.

`reports/dossiers/last-ten.md` is rebuilt whole from the store on every build,
so it cannot drift from it: `last_n` rows of when, what, how long, and either
a link to the dossier or the word for why there is none.

The last section is the point of the exercise as much as the rest: it names
what the mirror does not hold for this play -- which credited actors have no
bio and no filmography, which entries in the franchise have no premiere date,
whether the list has any dated episode watches for the work, whether the
retrieval store has a page for the episode at all.
