# Plan: more accurate episode summaries

What she learns about an episode he just watched. Reference for the module as
built: PROJECT.md §10.9 and §12.12, spec `docs/recap.md`. This is the plan for
the next version of the same path; nothing here is built.

## 1. The pipeline as it stands

Identifying the episode. `sim/watching_him.py:80 parse_file` reduces a player
filename to (title, episode) in three shapes -- `[Group] Title 05 (...)`,
`Title - 02 (...)`, `Title - S01E26 - Name` -- and `AnimeKB.resolve_strict`
turns the title into an id on his mirrored list. The number comes from the
filename, never from the page. `sim/anime_kb.py:221 japanese_title` then asks
the list's own API (`api.myanimelist.net/v2/anime/{id}?fields=alternative_titles`,
`X-MAL-CLIENT-ID`) for the Japanese title, and that title is the whole search
key: with no Japanese title nothing is fetched at all
(`sim/watching_him.py:575-578`). An episode counts only once he is
`watching.min_minutes_in` (3.0) into the file.

The query. One form, one language: `recap.query_template` =
`{title} アニメ 第{ep}話 あらすじ 感想`, built at `sim/recap.py:342` and
`sim/recap.py:422`. A whole-series fallback (`{title} 全話 あらすじ ネタバレ`)
runs only when the first search returns no links at all.

The search. `recap.search_engines` is Bing then DuckDuckGo HTML
(`sim/recap.py:531 _search`). **Bing has been contributing nothing**: it wraps
each organic result in `<h2 class="">` around a `bing.com/ck/a?...&u=a1<base64>`
redirector, and `_result_links` (`sim/recap.py:544`) wants a bare `<h2>` and
drops every `bing.com` host, so it parses zero links out of 280 KB and every
search in practice runs on DuckDuckGo alone.

The source list. There is no source list -- whatever the engine ranks, minus
`recap.blocked_hosts`. That list bans, among others, `wikipedia.org`,
`myanimelist.net`, `anilist.co`, `annict.com`, `filmarks.com`, `anidb.net`,
`allcinema.net`, `syobocal.jp`, `anime-planet.com`, `bangumi.tv`, `kitsu.io`,
plus streaming and shops. It was written to keep the romaji title from landing
on database pages with no prose. It also bans the two sources that measured
best (§2).

Size limits. `recap.min_chars` 200, `recap.max_chars` 2200,
`recap.page_min_html` 25000, `recap.search_min_html` 15000,
`recap.candidates_max` 4, `recap.candidates_target` 4.

The harvest test. `Recap._episode_slice` (`sim/recap.py:666`) is the only test
a page has to pass: find the first occurrence of `第N話` / `N話` / `#N` /
`ep N`, cut at the next episode's marker or at `max_chars`, refuse a slice that
opens inside one of five blog list markers within 100 characters, cut at blog
furniture after 100 characters, and refuse a programme running order
(`_running_order`, `sim/recap.py:645`: three or more of the table's own
headings and fewer than one full stop per 200 characters).

The judge. `sim/watching_him.py:495 judge` -> `prompts/digest_judge.txt`: one
JSON call over the digests that survived, ranking on being about this episode,
covering it beginning to end as a sequence, being concrete, and being free of
review talk; `{"best": n, "why": "..."}`, `-1` for none.

The digest. `sim/watching_him.py:455 digest` -> `prompts/watching_digest.txt`,
one call per candidate page, 200-500 Japanese characters, `なし` for a page that
names the episode and carries no events.

The cache. Table `recaps` (`sim/recap.py:66`): `title, ja, kind, ep, text,
source, fetched_at, judged`, keyed on (`ja`, `ep`), newest row wins.
`remember` (`sim/recap.py:368`) stores the judge's winner with `judged=1` and
drops any unjudged row for the same episode; `sim/watching_him.py:532-537`
re-reads a row that is not judged.

What reaches her. The digest goes to `KnownThings.merge("anime:{id}", ...,
label "第N話")` (`sim/watching_him.py:592-596`, six labels kept per thing,
`sim/known.py:60`), to kv `watching_last`, and into her prompt as pinned
situation lines built by `situation_lines` (`sim/watching_him.py:702`) and
placed by `persona/persona.py:985-993`. Her line is the digest, or a
`watching.summary_max_chars` (1400) cut of the raw page when no digest could
be made. The raw page itself is never kept past `recaps`.

Two holes worth naming before anything else changes:

* **The first occurrence of the episode marker is usually the navigation.**
  The official site page for one episode carries a nav strip listing all
  thirteen episode titles, so the slice runs from the nav entry `第12話` to the
  nav entry `第13話` and is thirteen characters long -- under `min_chars`, so
  the page is dropped and the 249 characters of official あらすじ two
  paragraphs below are never seen. Log receipt:
  `[recap] https://www.mitsudomoe-anime.com/episode/ep12.html: no section for
  ep12; skipped` (run `2026-09-03_19-28-13`). Reproduced offline against the
  live page: `_extract` gives 1,063 characters, `_episode_slice(body, 12)`
  gives `'第12話 「君に届かない」'`.
* **Her own watching has no judge and no digest.** The watchlist path
  (`Outlook.experience` -> `Recap.recap_for`) still takes the first page that
  passes the section test, stores it unjudged, and hands the raw text to the
  experience call at up to 1,400 characters. Four of the nine stored episode
  rows came that way and none has a digest.

## 2. What the measurement showed

Nine stored rows, hand-checked against the best account findable on the web.
Two wrong, four thin, three right but noisy; none clean. Detail and receipts
are in the report beside this plan
(`data/retired/<ts>_summaries_plan/REPORT.md`). The two conclusions that drive
the ranking below:

* the accounts that named every scene in order, for every episode checked,
  came from an **English episode-list summary**, reachable in one keyless
  request per episode at `myanimelist.net/anime/{id}/_/episode/{n}` in the
  page's `og:description` meta tag, and upstream at English Wikipedia's
  `List of <show> episodes`. Both hosts are banned by `recap.blocked_hosts`
  today;
* the **official あらすじ** page (and its mirror in a streaming catalogue) is
  never wrong and never complete: 200-250 characters, in character, covering
  the first sketch only. It is the right anchor for a fact check and the wrong
  thing to summarise.

## 3. The sources, ranked

Rank by what each proved, with the request form. A fetch is a plain keyless
HTTP GET unless marked Selenium.

1. **The episode page on his own list's site**, `myanimelist.net/anime/{id}/_/
   episode/{n}`. The id is already known (`AnimeKB`); the slug is ignored, so
   no lookup is needed. The synopsis is the `og:description` meta tag -- one
   regex, no container walk, no JavaScript, no login, 60-90 KB. English.
   Scene-by-scene for a gag show. It names its own upstream in the text
   (`(Source: Wikipedia)`, `(Source: Crunchyroll)`, `(Source: Official YouTube
   Release)`), which is a usable confidence signal: a Wikipedia-sourced one is
   an episode-list summary and complete; an official-blurb-sourced one is a
   one-paragraph hook.
2. **English Wikipedia's episode list**, `List of <show> episodes`, via the
   action API (`/w/api.php?action=parse&page=...&prop=text`) or the REST HTML
   endpoint. The summary column carries roughly 60-120 words per episode, with
   outcomes. Exists for most TV series with a broadcast run; missing for
   shorts. The REST endpoint rate-limits (HTTP 429 after a handful of requests
   in a row), so one request per episode with the project's own user agent and
   the article cached whole -- the article carries every episode, so one fetch
   serves a whole series.
3. **A Japanese sketch-by-sketch review blog**, found by the current search.
   The best Japanese source for a gag show: an `■あらすじ` list naming each
   sketch in order. Its habit is to end every sketch with `・・・` rather than
   give the outcome, which is exactly what the digest role has twice completed
   by guessing. Treat as a scene list, not a source of outcomes. Hosts already
   handled by `HOST_SELECTORS`: hatenablog, ameblo, goo, livedoor, fc2, jugem,
   note.
4. **The show's own site, the `あらすじ` page for that episode.** Never wrong,
   200-250 characters, first sketch only, in character. Its URL shape is
   guessable per show but not general; find it by search restricted to the
   show's own domain. Requires the fix in §5 to be reachable at all. **Static
   on an older show's site and a JavaScript index on a modern one**: an
   episode page from a 2010 site is 9 KB of plain HTML carrying the whole
   あらすじ, while a current show's story index gives 17 KB of chrome and 331
   characters of extractable text, so a modern official site needs the
   Selenium path or the streaming mirror below.
5. **A streaming catalogue's per-episode blurb.** Video Market
   (`videomarket.jp/title/{id}`) serves every episode's blurb in one 250 KB
   plain-HTML page, and it is the same official text as the show's own site.
   Same value and same limit as rank 4, one request for the whole series.
6. **A show-specific fan wiki** (`<show>.fandom.com`, per-episode pages with a
   Summary section). Scene-by-scene where it exists, which is for popular
   shows only. Refuses a plain fetch (HTTP 402 to a library user agent);
   needs the Selenium path. English.
7. **The community TV database** (`thetvdb.com`, per-episode overviews, an API
   behind a key). Unverified here; listed because it has per-episode overview
   text in several languages and would be the fallback where 1 and 2 are
   thin.

Ranked above all of them, but not a candidate -- **the episode's Japanese
subtitle file**, which for most shows downloads with one keyless request and
is the ground truth every candidate is checked against rather than a synopsis
to choose. §7a.

Not sources, and why:

* **Japanese Wikipedia's episode table has no summary column** for any of the
  shows checked -- 話数 / サブタイトル / 脚本 / 絵コンテ / 演出 / 作画監督 / 放送日
  and nothing else, and no sub-segment titles. `wikipedia.org` should stay
  banned for *Japanese*; the English episode list is a different article and
  should be allowed.
* **The programme running order** (a parts-and-eyecatches table) names the
  episode and describes none of it. Already refused by `_running_order`.
* **The streaming players** are JavaScript applications: U-NEXT returns 53 KB
  of chrome and no text, Bandai Channel 288 KB of unrendered Vue templates,
  dAnime carries a series blurb and, for an old show, no episode list at all.
  Selenium would render them for a 96-character teaser; not worth a browser.
* **AniList** refuses a plain fetch (403) and its schema has no per-episode
  synopsis field -- `streamingEpisodes` is titles and thumbnails.
* ~~**The community API in front of his list**~~ -- **STRUCK 2026-09-04. Do not use it, and do not keep it as a fallback.** It has answered HTTP 504 on every path that needs a live MyAnimeList fetch since 2026-08-28: 94 requests over 25 minutes, every one of them, plus a 40-attempt recovery poll over ten minutes that never recovered, while MyAnimeList's own origin answered the equivalent page in 0.28 to 0.81 s throughout (`data/retired/20260904_jikan_504/REPORT.md`). A fallback that has been down for a week is a silent hole, not a fallback, and the wrapper adds an outage the source does not have on top of a three-requests-a-second limit. **Everything here goes to MyAnimeList's own origin**, which is what the daemon and `sim/anime_kb.py` already do -- the list JSON, the public history page, the logged-in episode panel, the characters page, and the official API v2. The daemon watches for the outage ending (`jikan_watch`, one request an hour, recorded in `meta` and read by nothing); see `docs/role-check.md` §7.
* **Review aggregators** (Filmarks, Annict, Anime News Network) carry ratings
  and reviews, not plot.

Query form per source and show type:

| source | request | show type it is for |
| --- | --- | --- |
| list site episode page | `myanimelist.net/anime/{id}/_/episode/{n}`, read `og:description` | everything; best on multi-sketch gag shows |
| list site episode index | `myanimelist.net/anime/{id}/_/episode`, one request per series: every episode's English, romaji and Japanese subtitle plus air date | the wrong-episode test and a better query |
| English episode list | action API, `List of {english title} episodes`, cache the whole article | any series with a broadcast run |
| Japanese review blog | the current search, `{ja title} アニメ 第{ep}話 あらすじ 感想` | gag shows, older shows, anything the English sources are thin on |
| the show's own site | `{ja title} 公式 第{ep}話 あらすじ`, restricted to the show's domain | anything currently or recently on air |
| streaming catalogue | `videomarket.jp` title page, cache the whole page | anything licensed there |
| fan wiki | `{english title} wiki episode {n}` restricted to `fandom.com`, Selenium | popular shows |

## 4. Fetch several, then judge

Today the harvest returns the first page that passes the section test, and the
candidate path digests up to `recap.candidates_target` pages found by one
search. Change both to a **fixed source list first, search second**.

* Build the candidate set from the ranked list: request ranks 1, 2, 4/5 (the
  official blurb, whichever is cheaper for that show) **in parallel**, then
  run the existing Japanese search and take blog candidates until the set
  holds `candidates_target` (a new key under `recap`) pages. The first three are keyless HTTP and
  cost no browser; only the blogs need Selenium.
* Digest each candidate as now, once per page.
* The judge gets **all of them together and compares them against each
  other**, not against a bar. Two additions to `prompts/digest_judge.txt`:
  * a candidate that names the episode's scenes **in the order they happen**
    beats one that names its themes, and a candidate that names more scenes
    beats one that names fewer, provided every scene it names is corroborated;
  * where an **anchor** is supplied (the official blurb, or a transcript --
    §7), a candidate that contradicts the anchor on a stated outcome is
    disqualified, and a candidate that agrees with it and goes further is
    preferred. State plainly that the anchor is usually incomplete, so
    covering more than the anchor is not a fault.
* The judge returns `{"best": n, "why": "...", "corroborated": [n, ...]}` --
  the winner, the reason, and which other candidates agreed with it. The
  agreement list is what makes a row trustworthy (§6).
* A single candidate is never judged and never trusted: with one candidate the
  row is stored provisional and re-read next time.

## 5. The acceptance tests in code

`_episode_slice` is the harvest test and needs one fix and four additions.
Each is testable offline against a stored page.

* **The fix: the first occurrence of the marker is usually the nav.** Score
  every occurrence of the episode marker in the body and slice at the best
  one, rather than the first. A marker followed within ~40 characters by
  another episode's marker is an index entry; a marker followed by prose (a
  full stop within the next 200 characters, or 200 characters with no other
  episode marker) is a heading. Take the last index-like occurrence's
  successor, or plainly: the occurrence with the most prose after it before
  the next marker. Receipt for why: the official page's slice is thirteen
  characters because both its own nav entries were taken.
* **A running order** -- three or more programme-table headings and under one
  full stop per 200 characters. Built.
* **A list of other articles** -- a blog list marker inside the first 100
  characters. Built.
* **A season page**: the body carries markers for more than half the episodes
  of the series and the slice for this one is shorter than `min_chars`. That
  is the official-site case above and the "all thirteen titles" case, and it
  should be reported as *fix the slice*, not *skip the page*.
* **A blurb under N characters** stays a candidate but is flagged
  `anchor_only`: too short to be the digest (`anchor_max_chars` (a new key under `recap`), ~300),
  never discarded, handed to the judge as the anchor rather than as a
  candidate.
* **The wrong episode, where the number matches and the title does not.** The
  cheapest true test available is the episode's own subtitle, and the store
  does not have it: `mal_history.db`'s `episodes` table is a watch log
  (`anime_id, ep, watched_at, raw, source`) with no titles. One request per
  series supplies them all: `myanimelist.net/anime/{id}/_/episode` returns 73
  KB carrying, per episode, the English title, the romaji title and **the
  Japanese subtitle in kana and kanji** (`Maji de Hen Suru Go Byou Mae
  (マジで変する５秒前)`), plus the air date. Cache that per series in `recaps`
  under a new kind, and the test is then: if the page names an episode
  subtitle beside this number and it is not this episode's subtitle, the page
  is about another series' episode N. This is the case nothing catches today
  -- a bookstore listing for volume 9 of the manga was accepted as episode 9
  once, and only the missing-section test caught it, by luck. The same cached
  subtitle also gives the digest role and the judge the episode's real title
  to check against, and gives the search a better query
  (`{ja title} {ja subtitle} 感想`) for a show whose episode numbers are
  ambiguous across seasons.

Add each as its own offline check in `tools/recap_test.py` with the real page
text that motivated it, kept beside the test as a fixture rather than fetched.

## 6. The cache rule

A row in `recaps` is one of three things, and the column says which:

* **provisional** -- one candidate, or a candidate no other candidate
  corroborated. Read once (so an episode is never blank), and **refetched on
  the next read**. This is what `judged=0` means today, and the behaviour is
  already there (`sim/watching_him.py:532-537`); it must apply to the
  watchlist path too, which today stores unjudged rows and trusts them.
* **judged** -- the judge chose it among at least two candidates and at least
  one other candidate agreed with it on the scenes it names.
* **anchored** -- judged, and it agreed with the official blurb or a
  transcript. Trusted without a re-read.

Every row carries what was decided and why, so the next reader does not have
to guess: `source` (the winning URL, already there), plus `candidates` (a JSON
list of the URLs fetched and each one's verdict), `reason` (the judge's line),
`anchor` (the URL of the anchor used, if any) and `confidence` (provisional /
judged / anchored). `judged INTEGER` becomes that column, or stays and gains
the others beside it -- either way `_ensure_table`'s `PRAGMA table_info`
backfill covers the migration, and a row from before the change reads as
provisional.

One thing that had to happen before any of this: **the live saves did not
have the `judged` column.** It is added in `Recap._ensure_table` at
construction, so the first restart after the build is what created it; before that
`Recap.judged` returned False for every row through its own exception
handler, which was the safe direction -- every row re-read -- but nothing
recorded the choice. Both saves now carry `judged`, `confidence`,
`candidates`, `reason`, `anchor`, `scenes` and `archive`.

## 7. Transcripts

A transcript is the ground truth a summary should be checked against, and the
question was whether getting one costs compute and delay. For most shows it
costs neither: **the subtitle file already exists on the internet and
downloads with a plain keyless request.** Only where it does not is
transcription the answer, and that part is a proposal only.

### 7a. The subtitle file as an internet source

Verified against the five shows in the sample. A Japanese subtitle file
downloads today, per episode, with no login, for four of them.

| show | Japanese subtitle file | coverage |
| --- | --- | --- |
| ぼっち・ざ・ろっく！ | yes | 12 of 12, four independent complete sets |
| けいおん!! | yes | 26 of 26, three complete sets plus a streaming rip |
| ゆるゆり♪♪ | yes | 12 of 12, two complete sets |
| ちいかわ | yes | 73 episodes covered; the broadcast run is far longer |
| みつどもえ | **partial** | **episodes 1-4 of 13, and nothing else anywhere** |

Two sources, both plain HTTP:

* **`jimaku.cc`.** The web download path needs no account, which is the
  correction to the usual assumption -- only the JSON API does
  (`/api/entries/search` returns HTTP 401 without a key; an account is needed
  to generate one). The home page is a server-rendered index of about 4,500
  entries, so the catalogue is greppable anonymously; an entry page lists its
  files; and `GET /entry/{id}/download/{filename}` returns the file with no
  cookie and no key. Entry ids for the sample: 1833, 3655, 1506, 9605, 1648.
* **The mirror on GitHub** (`Ajatt-Tools/kitsunekko-mirror`, browsable at
  `subtitles.ajatt.top`), where every file link points at
  `raw.githubusercontent.com` -- so a download is a raw GET, which is the
  easiest thing in this list to script. It carries more files than the
  original archive per show. `kitsunekko.net` itself is up and its directory
  listings are plain HTML, but it ships mostly zip/rar/7z archives, so a
  fetcher has to unpack.

Three cautions the survey turned up, each of which has to be a code check:

* **A file in a "Japanese" folder is not always a Japanese transcript.** The
  みつどもえ files are a Chinese fansub group's listening transcript
  (`Original Script:漫游字幕组`), and one of them is a dual-language script
  where the Japanese layer is 309 lines of 723 and the rest is Chinese,
  karaoke and a scrolling banner. Test the file, not the folder: the share of
  lines that are Japanese script.
* **A `.sup` file is bitmap images**, not text, and would need optical
  recognition. Refuse it.
* **A machine translation is not a transcript.** One archive offers
  "translated from English" tracks for these shows; those are worthless as
  ground truth. Prefer, in order: a broadcast-caption rip, a streaming
  closed-caption rip, then anything else.

**What the good files give beyond the lines.** A broadcast-caption rip carries
speaker labels and sound annotations -- 295 of 473 cues in one episode are
prefixed `（唯(ゆい)）`, `（律(りつ)）` and the like -- so the speaker comes
free without matching against the cast list. A fan listening transcript gives
none of that.

**Sketch boundaries: from the filename, not the file.** A gap analysis on one
gag-show episode (293 lines) found only two unambiguous gaps, the opening
(37.8 s) and the ending (95.5 s); the body is a scatter of 8-17 second gaps
with no way to tell a sketch break from a pause in visual comedy. So a
transcript alone does **not** segment a sketch show. What does: the streaming
rips name every sketch in the filename, separated by a divider
(`ちいかわ.S01E01.かためのプリン_ホットケーキ . スフィンクス_ほんものだ . …`), and
those titles turn up in the dialogue -- the sketch called `スフィンクス_ほんものだ`
has the line `（ハチワレ）本物だ` at 00:01:38. Aligning the filename's titles
against the transcript gives sketch names with timestamps. Failing that, the
programme running order -- the table this pipeline currently refuses as a
synopsis -- names the sketches in order and is the right input for
segmentation even though it is the wrong input for a summary.

**Broadcaster captions are not a separate route.** Japanese broadcast captions
are ARIB data multiplexed into the transport stream; getting a file means
recording the broadcast and demuxing it (`Caption2Ass`, `libaribcaption`).
That is exactly what the best archive files already are, so the archive is the
route and the broadcaster is not. Streaming services do carry Japanese closed
captions -- the archives hold rips labelled as such -- and fetching one
directly needs an authenticated player session, which is not worth doing when
the rip is already a file.

**Where it sits in the pipeline.** A `transcripts` table beside `recaps`, same
(show, episode) key, holding the lines with timestamps and the speaker where
the file gives one, plus the source URL and the file's provenance
(broadcast / streaming / fan / unknown). One keyless request per episode, no
GPU, no delay. It is read by the judge as the anchor (§4) and by recall as a
quote source; **it is never the digest**, for the reason in §7b.

**Coverage is the catch, and it is not about age.** The 2010 show with three
complete subtitle sets is better covered than the 2022 show whose broadcast
run outran its rips. What decides coverage is whether a show reached a
Japanese-caption streaming service or was captured off Japanese television
with captions on. So the transcript tier is a bonus per episode, never a
dependency: the pipeline must work identically with no transcript, and the
gag show that produced both wrong digests is exactly the show with no
transcript past episode 4.

### 7b. Transcribing the rest, as a proposal only

For the episodes with no subtitle file. Nothing here is to be built without
his say.

**What it would give.** A transcript per episode: every line of dialogue with
a timestamp, and with the cast list already in the store (`anime_cast`, voice
actors for 479 shows) the speaker can often be attached. Three uses, in order
of value:

* **ground truth for the judge.** A candidate that says the father refused
  when the transcript has him agreeing is disqualified on a fact, not on
  style. Both wrong digests in §2 are exactly this failure -- an outcome
  invented where the source trailed off -- and a transcript catches both.
* **anchors.** Sketch boundaries (a gag show's episode is four to six shorts,
  and the running-order table names them; a transcript with a long silence and
  a new set of speakers marks the same boundary), and the exact lines she could
  quote back.
* **never the digest itself.** A 24-minute episode is 300-500 lines of
  dialogue with no stage directions; a model asked to summarise it writes a
  plot from speech alone and gets the visual gags wrong. The transcript is a
  check and a quote source.

**What it costs.** On the machine's 4070 Super, `faster-whisper` with the
`large-v3` model in float16 transcribes a 24-minute episode in roughly 1.5-4
minutes of GPU time (10-20x realtime with VAD and batching), less with
`medium`; `whisper.cpp` with CUDA is in the same range. Japanese word error
rate on clean anime audio is acceptable for fact-checking and poor on names --
which is survivable, because the names are already known from the cast list
and can be given to the transcriber as an initial prompt. Disk is small: an
SRT for an episode is 20-40 KB, so his whole library is tens of megabytes.
The GPU is shared with the reaction-image tool (`tools/reactions.py`), so the
two must not run at once.

**Where it would sit.** The same `transcripts` table as §7a, with the
provenance recorded as transcribed rather than downloaded, so a downloaded
caption rip always outranks a transcription. The judge reads a row when there
is one. Nothing else in the pipeline changes: the digest is still made from
web candidates, the situation line is still the digest.

**The delay, and the two ways round it.** He opens the file and she has a
minute or two before he expects her to know something; a full transcription is
longer than that.

* **Transcribe the first N minutes while he watches.** The player already
  reports its position (`watching.now_playing_path`), and an episode counts
  only at `watching.min_minutes_in` (3 minutes). Transcribing the first five
  minutes takes well under a minute and covers the setup and usually the first
  sketch -- enough to check the opening of every candidate, which is where the
  official blurb also lands. The rest continues in the background and upgrades
  the row.
* **Transcribe the library ahead of him.** His list carries what he is
  part-way through (thirteen series) and the player history says which file is
  next in a folder. A nightly pass over the next unwatched episode of each
  open series is a dozen episodes, under an hour of GPU, and by the time he
  opens one the transcript is already there. This is the version with no delay
  at all, and it costs the GPU when nothing else wants it.

**What it does not solve.** A show he is watching that is not on his list, and
the first episode of anything new. Those fall back to the web path. And it is
only worth building for the shows §7a cannot reach -- for four of the five in
the sample, downloading the file is free and instant and transcribing would be
a worse copy of it.

## 8. What reaches her

Keep her line short and make the record wide.

* **Her situation line stays the digest**, `watching.digest_max_chars` (600),
  pinned. It is what she skimmed, and a longer one is a recitation.
* **The record gains a scenes list.** `KnownThings` stores one text per
  episode label today. Store beside it, on the `recaps` row rather than in her
  known-things, a `scenes` list -- one line per scene or sketch, in order,
  with its title where the source names one -- and the exact lines worth
  quoting when a transcript exists. Nothing reads that by default. It is what
  `sim/lore.py` retrieval and a later question ("what happened when the cat
  went missing") pull from, so recall can quote a scene rather than restate the
  digest.
* **The digest role gains one instruction**, and it is the one both wrong
  digests broke: where the source ends a scene with `・・・` the digest ends the
  scene there. It is in the prompt already and was ignored twice, so it should
  also be a code check -- a digest sentence asserting an outcome for a scene
  whose source text ends in an ellipsis is a flag the judge is told about, not
  a rewrite of her words.

## 9. The measurement

A scored set, and it is the only way to tell whether any of this helped.

`tools/recap_test.py` is 19 offline checks on parsing with no notion of
accuracy. Extend it in two parts:

* keep the offline checks, and add one fixture per acceptance test in §5, each
  the real page text that motivated it, stored under
  `tools/fixtures/recap/<host>_<show>_ep<N>.txt`;
* add a scored mode, `python tools/recap_test.py --scored`, over
  a fixture file, tools/fixtures/recap/truth.json (to be created): **twenty episodes with hand-checked
  truth** -- the show, the id, the episode, the ordered list of scenes, and
  for each scene its outcome in one clause. Pick them to cover the cases that
  have failed: a multi-sketch gag show (five episodes, since one supplied both
  wrong digests), a plain-narrative series, a short-form show, an old show with
  no English episode list, a current show with an official あらすじ page still
  up, and one episode whose number matches another series' episode.

The score per episode: scenes found in order (recall), scenes named that are
not in the truth (invention), outcomes stated that contradict the truth
(error). The headline number is **episodes with no error and at least
two-thirds of the scenes**, and it is run before and after every change in the
build order below. Today's rate on the nine rows measured by hand is 0 of 9.

Building the truth file is hand work and it is the expensive part: roughly an
hour per five episodes, and it must be done from a source that is not the
pipeline's own (a transcript, the English episode list, and the official blurb
agreeing).

## 10. Build order and what each step costs

Cost is per episode, and "a call" is one flash-tier model call.

1. **Fix the slice** (§5, the nav case), and add the fixture tests. No new
   calls, no new fetches. Immediately makes the official あらすじ page and every
   season-index page reachable. Run the scored set first to have a before.
   Free alongside it: `_page_source` polls until the page source reaches
   `recap.page_min_html` (25,000) or `recap.poll_max` (12) polls of
   `recap.poll_seconds` (1.3) elapse, so **a small page always costs the full
   15.6 seconds** -- an old show's official episode page is 9 KB and can never
   reach the threshold. Break the poll when the page has stopped growing
   between two polls, which is the condition the threshold was standing in
   for.
2. **Add the two English sources** (ranks 1 and 2) as fetched-first candidates,
   keyless HTTP, no browser. Two extra HTTP fetches, two extra digest calls,
   the same one judge call. Removes `myanimelist.net` and the English episode
   list from `blocked_hosts` -- and only those; Japanese Wikipedia stays
   banned.
3. **Parallel fetch and the anchor** (§4): fetch the candidate set at once
   rather than in sequence, mark a short official blurb as the anchor, teach
   the judge to use it. Cost unchanged; latency drops, because the browser is
   no longer in the critical path for the first three candidates.
4. **The cache columns and the provisional rule** (§6), and the same rule on
   the watchlist path. No new calls; a provisional row costs a refetch on next
   read, which is the point.
5. **The scenes list and the record** (§8). One extra field out of the digest
   role, no extra call.
6. **The subtitle file as the anchor** (§7a): one keyless request per episode
   against the index and one for the file, a `transcripts` table, the
   provenance checks (Japanese-script share, refuse bitmap subtitles, refuse
   machine translations), and the judge told to use the transcript as the
   anchor in preference to the official blurb. No new model calls -- the judge
   call already exists and this changes what it is given. The transcript is
   too long for a prompt whole, so the judge gets the lines that fall inside
   each candidate's claimed scenes, or the first N minutes' worth; deciding
   that slice is the one design question in this step.
7. **The scored set to twenty episodes** (§9). Hand work, no calls. Cheaper
   after step 6, because a transcript is most of the hand-checking.
8. **Transcribing what has no file** (§7b), only on his say.

Steps 1 to 5 leave the per-episode cost at 4-5 fetches (three of them
keyless), `n` digest calls where `n` is the candidate count (3-4), and one
judge call -- about one more digest call than today, and one fewer browser
fetch. Step 6 adds two keyless fetches and no calls.

## 11. What is built

Steps 1 to 7 above are built; step 8, transcribing locally what no archive
has, is not and stays a proposal. The reference for the module as it now is
is `docs/recap.md`; the build note with its measurements is in `HISTORY.md`.
In short:

* **the slicer scores every occurrence of the episode marker** rather than
  taking the first, so an official あらすじ page behind a thirteen-title
  navigation strip is reachable, and a body carrying markers for most of a
  series is reported as an index rather than skipped;
* **one path for both watching modules**, `Recap.synopsis`: his (a file
  opening in the player) and hers (a show on her own list), where hers used
  to take the first passing page and trust it forever;
* **a ranked source list first, the search second**, with the two keyless
  English sources fetched in parallel with the browser -- and the two hosts
  his approval unbans, and only those;
* **the judge compares candidates with each other and with an anchor**, and
  says which others agreed; the row records the candidates, the reason, the
  anchor and the scenes in order, and is marked provisional, judged or
  anchored;
* **the episode's own subtitle file** downloaded keyless from a fan archive
  and its mirror, checked for being a Japanese transcript rather than a
  Chinese one, a bitmap or a translation, and turned into a scenes-in-order
  account by one flash call (`transcript_digest`) -- the anchor, and the
  digest only when no web candidate survived;
* **everything fetched is kept on disk** under `data/recaps`, versioned
  rather than overwritten, with a manifest per episode saying what each file
  is, where it came from, when, and which one the judge chose;
* **a scored truth set** at `tools/fixtures/recap/truth.json` over the
  episodes the two saves hold, and `tools/recap_test.py --scored` to run it.

Every new key is read with a default and all of them are now in `config.py`
and both character configs, the `transcript_digest` role with them; his own
list's site is unbanned and the Wikipedia ban is narrowed to the Japanese
one, so the two ranked English sources are read. Both characters have been
restarted on it.
