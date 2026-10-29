# Grounded watching & the Japanese knowledge base -- `sim/watchlist.py` + `sim/recap.py`

Spec of record. Summary: PROJECT.md §10.9 (grounded watching) and
§11.3 (the KB she looks things up in). Dated notes: HISTORY.md Part C
(built; the KB generalisation; the Chrome-leak reap). Was
`docs/planned/watched-media-recap.md` (the design and the source
verification).

## 1. Purpose

When a scene has her watching an episode, the `experience` role used to
invent both the title and the plot from the model's own knowledge, which
is often wrong (K-On ep15 came out as a lyrics scene; it is the marathon
episode) and pure confabulation for anything the model does not know. This
pins a REAL title and episode from her own watchlist and hands the
`experience` call a REAL Japanese あらすじ for that episode, so she reacts
to what actually happened, in her own register. One search and a few page
fetches per new episode, cached; no model call in the fetcher itself, and
the ones that read a fetched page are the callers' and are cheap (§7).
Vision-watching (per frame) was the alternative and costs orders of
magnitude more.

## 2. The watchlist (`Watchlist`)

Her own shows, with a cursor -- his MAL shelf is his, this is hers. kv
`watchlist`: `[{title, ja, kind: anime|drama, ep, total, added, last_ts}]`,
seeded once from `watchlist.seed`; a show she chose herself also carries
`own`, `his` (it is on his list too) and `why`.

- `current()` -- the show she would put on next: an unfinished one
  (`ep <= total`, or no total), the one with the oldest `last_ts`, so she
  rotates rather than binges.
- `advance(title)` -- she watched an episode: `ep += 1` (never past
  `total`), stamp `last_ts`. Called after a kept watching beat.
- `pick_own()` -- a show of her own, and the one model call in this
  class (role `watch_pick`): her taste sheet, the accounts she keeps
  liking and what is going round decide it, his list is context rather
  than a fence, and the pick lands at episode 1 marked as hers. Code
  decides when (`pick_due`): at most `watchlist.max_open` unfinished, and
  no oftener than `watchlist.pick_every_days` once `watchlist.keep_min`
  are open. kv `watch_pick_ts` and `watch_pick_log`.
- `queries()` -- the Japanese titles of her open shows, joined into what
  she searches X for, so her searches seek her own things.
- `add / remove / set_ep / report` -- the ops surface.

## 3. The recap fetcher (`Recap`, Selenium + keyless HTTP)

`Recap.synopsis(entry, ep, llm=...)` is the whole path for one episode and
both watching modules go through it: the cache when it holds a row a reader
chose, then the episode's own subtitle file as an anchor, then a fixed list
of sources fetched in parallel with the Japanese search, one digest per
candidate, one judge over all of them, one row. It returns the text, the
digest, the ordered scenes, the confidence and the judge's reason, or `None`.
Never raises. `recap_for(entry, ep)` is the older single-page shape, kept for
the lookup path when he names an episode in chat; given a model client it
routes into `synopsis` too.

- **Cache first**: table `recaps` (title, ja, kind, ep, text, source,
  fetched_at, judged, confidence, candidates, reason, anchor, scenes,
  archive), keyed on (`ja`, `ep`). A hit is instant and offline, and is only
  trusted when its confidence says it was compared with something (§3a).
- **Search**: `query_template` = `{title} {ep}話 あらすじ 感想`, run against
  `search_engines` (Bing, then DuckDuckGo HTML, both `lang=ja`); the
  organic result URLs are parsed out (`_result_links`: bing `h2>a`, ddg
  `result__a` / `uddg=`), the engines' own domains and `blocked_hosts`
  (streaming, shops, wikipedia, booklive...) dropped. If the episode query
  finds nothing, the bare `{title} {series_suffix}` is tried (a
  whole-series page). **DuckDuckGo carries every search in practice**: Bing
  wraps each organic result in `<h2 class="">` and a
  `bing.com/ck/a?...&u=a1<base64>` redirector, so `_result_links` -- which
  wants a bare `<h2>` and drops any bing.com host -- parses nothing out of
  its 280 KB, and a probe that decoded the redirector got Roblox and
  YouTube for a Japanese episode query. Repairing the parse (with
  `mkt=ja-JP`) or dropping Bing from `recap.search_engines` and saving the
  fetch is open.
- **Fetch**: a throwaway-profile headless Chrome (NEVER her X profile),
  `page_load_strategy="none"`, `get()`, poll `page_source` until
  `page_min_html` (the good sources -- Fandom, some blogs -- reset the
  connection after load, so the html is read before waiting on load), **or
  until the source stops growing** for `poll_settle` polls, whichever comes
  first. The size threshold was standing in for "the page has finished
  arriving" and a small page can never reach it, so a 9 KB official episode
  page -- complete on the first poll -- cost the full 15.6-second budget
  every time. A page that has not STARTED arriving has also stopped growing,
  so the break needs `poll_min` polls behind it and `poll_min_html` bytes in
  hand: a site that redirected late sat at 3.4 KB for two polls and its
  episode section came out as its own title, 37 characters. Up to
  `candidates_max` result pages are tried in order.
- **Extract**: per-host article container (`HOST_SELECTORS`: ameblo
  `.skin-entryBody`, hatena `.entry-content`, goo, livedoor, cinema.ne.jp,
  dramataro...) then generic containers, then a whole-page strip -- so nav
  / sidebar / archive is dropped.
- **Episode slice, and it is the test**: keep this episode's section (`第N話`,
  full-width digits, `#N` and `ep N` too), ending at the next marker for any
  OTHER episode. **The occurrence is scored, not taken first.** The first
  occurrence of the marker is usually the navigation: an official page for
  one episode of a thirteen-episode show opens with a strip listing all
  thirteen titles, so slicing at the first `第12話` ran from one nav entry to
  the next and gave thirteen characters -- under `min_chars`, so the page was
  dropped and the 249 characters of official あらすじ two paragraphs below
  were never seen. So every occurrence is scored: one with another episode's
  marker within `index_entry_gap` characters behind it is an index entry and
  is set aside, and among what is left the one with the most prose after it
  wins. Where the tighter end-at-any-marker rule leaves less than `min_chars`
  the old end-at-the-next-episode rule gets its turn, so a post that mentions
  an earlier episode in passing is not cut at the mention.
  `Recap._season_page` reports a body carrying markers for most of a series,
  so that case reads as *slice it better* rather than *skip the page*.
  **A page with no section for this episode is not
  a synopsis of it and is skipped**, whatever else it says: the first
  synopsis the watching module ever handed the second character was a
  bookstore listing for volume 9 of the manga, found by 「みつどもえ 9話」
  and accepted whole because the body was taken when no section was
  found. The query says アニメ and 第{ep}話 now. The slice **ends at blog
  chrome** (`Recap.CHROME`: プロフィール, 最新記事, コメント, カテゴリ...) after a
  hundred characters, or a short post runs `max_chars` into the author's
  sidebar. Two further refusals, both because the section test alone lets a
  page through that names the episode and describes none of it:
  - **a slice that OPENS in a list of other articles is that list**, not a
    post -- one of the five list markers (最近の記事, 最新記事, 最近のコメント,
    最新コメント, 月別アーカイブ) inside the first hundred characters means the
    episode marker was the page's title and what follows is the sidebar. A
    blog's archive of titles and dates reached the digest role that way and
    it wrote a plot out of nothing (a word invented, a beetle invented);
  - **a running order is not a synopsis** (`_running_order`): three or more
    of a programme table's own headings (`RUNNING_ORDER_MARKS`: 構成,
    パート 内容, アイキャッチ, オープニングテーマ, 次回予告, キャスト, 分類...) and
    fewer than one 。 per 200 characters. Both conditions, so a post that
    quotes the preview and the ending theme survives. Measured on one
    show's five stored rows: the four blog pages carry none of the headings
    and a full stop every 44 to 120 characters, the table carries eight
    headings and one full stop in 683.
- **The page's own heading is part of the test, and it is where the number
  usually is** (`Recap.page_heading`, `Recap._names_episode`,
  `Recap._by_heading`). The article container `_extract` picks starts UNDER the
  post's headline, so a 感想 post's number never reached the slice: five pages
  fetched for one episode were headed
  `エグザンプル 第6話「宿はなし／Secret Paradise」 感想` and carried no
  marker anywhere in the body. The social-card title, the document title and
  the first two `<h1>`s are read together, and the number is recognised in
  every form the pages actually use -- half- and full-width digits, `第n話`,
  `n話`, `n話目`, `#n`, `#0n`, `EPn`, `Episode n`, `その n` -- against the text
  flattened one character for one (`_flat`: `７` and `＃` written half-width),
  so every offset still points at the same place and a slice cut on it is the
  same slice. **An episode's own subtitle is a marker too**
  (`Recap.slice_titles` over the `eptitles` cache and the account's own
  `ep_title`, nothing fetched), which is what cuts the right section out of a
  whole-series post that heads each episode with a title and no number. `その2`
  counts only in the acceptance test and never in the marker list: the marker
  list also decides where a section ENDS, and on a blog `その2` is the second
  half of the post far more often than it is episode 2. Two refusals stand over
  a page taken on its heading alone: a body that is an index of the whole
  series is not one episode's post (`_season_page`), and the body has to carry
  `slice_min_sentences` sentences in `slice_min_chars` characters -- the video
  shop's page for the same episode is headed `第6話` perfectly and is 285
  characters of prices and service copy, and a bookstore listing has no
  sentences in it at any length. Measured on the nine pages three readings of
  two episodes had dropped: three passed before, eight pass now, and the one
  still refused is the shop's. **The refusal is logged with the form it failed
  on** rather than as `no section for ep7`, which said nothing about what was
  looked for. `tools/episode_slice_test.py` covers every form with fixtures,
  including a listing that must still fail.
- **A cached row is tested the same way**: no section -- or a running order,
  or a sidebar -- and it is deleted and refetched, so a bad row from before
  a test existed cures itself.
- **The wrong episode, where the number matches and the title does not**
  (`Recap.wrong_episode`, `Recap.episode_titles`): one request per series
  against the list site's episode index gives every episode's English, romaji
  and Japanese subtitle, cached under kind `eptitles`. A page whose head
  carries a different episode's subtitle, and not this one's, is about
  another episode or another series; a bookstore listing for volume 9 of the
  manga was once accepted as episode 9 and only the missing-section test
  caught it, by luck.
- **A page a one-episode work cannot have** (`Recap.past_the_end`): a page
  that names an episode past the work's own episode count, and -- for a work
  with one episode -- a page carrying a next-episode preview (次回予告, 次回、,
  次回は, つづく). The guard above it only fires when a page names ANOTHER
  episode of the SAME entry by its subtitle, so a namesake's episode 1 walked
  past it: the page that reached the second character was the television
  series' first episode where the work was a one-episode OVA of the same
  Japanese title, and it ended in a preview of episode 2. The episode count
  comes from his own mirror through the `anime_kb` wire. `docs/resolver.md`
  §3.4.
- **`avoid`**: a caller that has judged a source useless passes its URL,
  and that source is skipped in search and treated as a miss in cache. The
  fetcher can tell a page *mentions* the episode; only a reader can tell
  it is *about* it.
- **Where the dialogue came from is readable outside SQL.**
  `recap.transcripts_report` (`reports/transcripts.md`) is append-only and the
  machine's, one line per attempt that resolved: when, show, episode, where the
  file came from (`sidecar` / `mirror` / `archive` / `whisper` / `miss`), lines,
  how far into the episode the last line runs, GPU minutes, the file, and the
  process that recorded it first. `Transcripts._catch_up_log` puts a save's own
  rows in once at construction -- and only its own, because a character never
  reads another character's save -- and the de-duplication on show, episode,
  outcome and file name makes three writers one record. The table gained
  `origin` and `gpu_seconds` for it: `provenance` says what KIND of subtitle a
  file is (broadcast, streaming, fan, whisper) and says nothing about where it
  was found, which is the question a person asks first.
- Result capped at `max_chars`, stored, returned.

## 3a. A fixed source list first, search second, then one judge

The old harvest returned the first page that passed the section test, from
whatever the engine ranked. What is fetched now is a ranked list, and the
first three need no browser at all, so they run in a thread pool alongside
the Selenium search (`fetch_workers`, `Recap.candidates`).

1. **The episode page on his own list's site** (`list_episode_url`): the
   synopsis is the page's own description meta tag, one regex, no container
   walk, no login. English, and scene by scene on a multi-sketch show, which
   is the case every Japanese source has been thin on. It names its own
   upstream in the text, which says how complete to expect it to be.
   **Reached only when the caller passes an anime id**, which his plays have
   and a show on her own list has not. When it gives nothing -- an older
   show whose episode pages carry no synopsis, or a request that errors --
   it says so in one line, by exception TYPE and never the URL, because a
   URL can carry a key. It used to be dropped in silence, and then the only
   way to tell whether it had been read at all was to open the archive and
   count what was in it.
2. **English Wikipedia's `List of <show> episodes`** (`wikipedia_api`,
   `wikipedia_list_title`), as wikitext, cached whole under kind `wikieps` --
   the article carries every episode, so one request serves a series. Three
   traps handled: his list writes a title with spaces the article has not, so
   the spaceless and the base title get a try; a list article often
   transcludes one sub-article per season, which is fetched; and **one
   article can hold five series, each with its own episode 1**, so the
   article is read section by section and a section is used only when its
   heading is this show. Where several sections carry the number and none is
   this show, nothing is returned -- reading the whole article gave a
   spin-off's sports tournament in place of a season's Valentine episode.
3. **The Japanese search**, as before, filling the set to
   `candidates_target`. This is where the official あらすじ page arrives, now
   that the slice can reach it.

Two hosts were unbanned for exactly these two pages and nothing else, by his
approval in `docs/episode-summaries-plan.md`; Japanese Wikipedia stays banned
because its episode table has title, writer, storyboard and air date and no
summary column at all.

**A page between `anchor_min_chars` and `anchor_max_chars` is kept and marked
as the anchor** rather than discarded, and the fullest of them is the one
used, because an anchor is a fact check and more of the episode checks more
of it. The official blurb is 200-250 characters, never wrong and never
complete: the right thing to check a summary against and the wrong thing to
summarise. Below `anchor_min_chars` a slice is the page's own furniture and
is not a candidate at all -- a blog's title bar with its advertising strip
under it came to 172 characters and stood as the anchor four real candidates
were measured against. When the anchor is the only thing found it is digested and stored
provisional anyway -- a thin true answer, read again next time -- because
setting it aside as the anchor and then storing nothing would be worse than
what this replaced.

**The digest** (`Recap.digest_page`, role `watching_digest`) runs once per
candidate and now answers in JSON: whether the page is about the episode at
all, the digest itself, and the **scenes in order**, one line each. The
scenes come out of the same call, so the record gains a scene list for no
extra call.

**The judge** (`Recap.judge_candidates`, role `digest_judge`) gets every
digest together and compares them **with each other and with the anchor**. A
candidate that names the scenes in order beats one that names its themes; one
that names more scenes beats one that names fewer, provided the extra scenes
are corroborated. Against the anchor: covering more than it is not a fault,
because the anchor is usually incomplete, but contradicting it on a stated
outcome disqualifies. It returns the winner, the reason, and which other
candidates agreed -- and that agreement is what makes a row worth keeping.

**Three cache states, and the column says which** (`Recap.confidence`):

- **provisional** -- one candidate, or one nothing corroborated, or a row
  from before any of this. Read once so an episode is never blank, and
  refetched on the next read.
- **judged** -- chosen among at least two candidates with at least one
  agreeing.
- **anchored** -- judged against a transcript or the official blurb. Trusted
  without a re-read.

Every row also carries `candidates` (the URLs fetched and each one's
verdict), `reason` (the judge's line), `anchor` (what it was measured
against) and `scenes`. **The provisional rule applies to her own watching
too**: that path used to store the first passing page and trust it forever,
and four of the nine episode rows in the two saves came that way.

## 3d. The episode's own subtitle file, and the archive on disk

**The order, and it cannot come away with nothing.** The stored page, then
the subtitle -- **beside his video, in the clone of the archive on this
machine, in that archive over the network, in the fan archive's own site,
and, when none of them has it, transcribed here from the file he played** --
and then the web candidates as before, with the subtitle's account of the
scenes as the anchor that disqualifies a page about the wrong episode. Two
sources are wired and off with their reasons in the config: a release index
whose pages carry no extracted subtitle at all, and a service that needs an
account nobody has.

Why it was reshaped: over one fortnight the two internet archives were asked
for five episodes and found two. The three misses were not bad matches --
**neither archive carried those works at all, under any name**, out of 3,532
anime television directories in one and 4,525 entries in the other. Meanwhile
a Japanese subtitle of 339 lines was sitting beside one of the very episodes
he had played, and nothing looked.

**`sim/subtitles.py`** finds one episode's Japanese subtitle file.

* **Beside his video** (`sidecar`, `local_subtitles_enabled`): the video's own
  directory, the video's own stem, one of the subtitle extensions, with or
  without a language suffix (`local_subtitle_suffixes`), and a `Subs` folder
  beside it. Free, instant, and the video itself is never opened. The day's
  one attempt is not spent on it, so a machine that gains a subtitle an hour
  later is not locked out until tomorrow.
* **The clone of the archive on this machine** (`subtitles_local_mirror`):
  the same directory-per-show layout, walked on disk. The repository is 3.71
  GB packed, so it is cloned shallow, one branch, sparse to the three folders
  this walks, and Windows' path limit needs `core.longpaths`. It is the
  MACHINE's, like the episode archive beside it (`tools/isolation.py`), and
  `refresh_local_mirror` pulls it at most once a day **from the list mirror's
  own daemon** -- never on either character's thread, because a pull of that
  working tree is not something a reply should wait behind.
* **The same archive over the network**, the fallback when there is no clone.
  Rate-limited, and it was the first network hop of every miss.
* **The fan archive's own site**, whose download path needs no account even
  though its JSON API does.
* And **the work's OTHER names** go into the matching, off his own list's
  local mirror: an archive files a show under whichever romanisation its
  uploader used, and one work his list calls
  `Makeine: Too Many Losing Heroines!` is filed as
  `Make Heroine ga Oosugiru!`. With that name the clone has it: 118 files,
  this episode among them. Without it, nothing matched.

Three checks on whatever is found, each of which a real file has failed: a `.sup` is bitmap images and every packed archive
needs unpacking, both refused by name; a track named as translated from
English is not a transcript; and **a file in a folder marked Japanese is not
always a Japanese transcript** -- one show's files are a Chinese group's
listening script, one of them dual-language with the Japanese layer 309 lines
of 723 -- so the share of lines carrying Japanese script is measured on the
file (`subtitles_min_ja_share`). A broadcast or streaming caption rip
outranks a fan transcript, and it brings the speaker free: the label in the
line (`（唯(ゆい)）`) is lifted out with its reading dropped. One attempt per
show and episode per day, hit or miss, so a show with no file is not looked
for on every tick (`subtitles_retry_hours`).

**`sim/transcribe.py`: when nothing can be fetched, the episode is listened
to.** His own `Faster-Whisper-XXL Pro` install does it, driven with the
command his own `processor.bat` builds -- Japanese, transcribe, the large
model, SRT out, `cuda:0`, and his own flags after them (`whisper_exe`,
`whisper_args`) -- so his batch file stays the reference and this follows it.
Nothing under that directory is touched, and the exe takes the video itself,
so there is no separate audio extraction. The result is written **beside his
video** under the video's own stem, so his player finds it next time (never
over a file already there: that one is the sidecar case, read one step
earlier), and into the episode archive with its origin noted, so the rest of
the path cannot tell it from a downloaded one. The console text goes to a
file in that archive slot; the log gets the exit code and the duration and
nothing else. A crash on teardown with the file written counts as a success,
which is what his own bridge does.

Four restraints, because it is minutes of a GPU the reaction-image tool also
wants: **never on the reply path or the poll** (its one caller is the watching
worker, which is already off the loop and already fetching pages);
`whisper_max_per_day`; `whisper_max_minutes`; and **only once he has watched
`whisper_min_watched_minutes` of it**. That last is a different question from
whether the episode counts as watched at all (`watching.min_minutes_in`,
three minutes): three minutes says he did not merely brush the file, ten says
he settled into it, and a GPU job is worth the stronger evidence. The
fetching steps are gated on the first and not on this. One run serves both
characters: the claim and the answer go in the machine's own store of what
was fetched about the world (pool `whisper`), keyed on the work and the
episode and never on a character -- and after the first run the subtitle is
beside the video anyway, so the second character finds it as a sidecar and
asks nobody.

**`sim/transcripts.py`** holds table `transcripts` (ja, show, ep, source,
provenance, n_lines, lines, account, scenes, quotes, status, fetched_at,
archive) and turns the file into an account by one call, role
`transcript_digest`, prompt `prompts/transcript_digest.txt`: the scenes in
the order they happen with the outcome of each, plus up to six exact lines
worth quoting. **That account is the anchor, never her line** -- twenty-four
minutes is three to five hundred lines of speech with no stage directions,
and a model asked to summarise that writes a plot out of dialogue and gets
the visual gags wrong. It is the digest only when no web candidate survived.
A miss is a row too, with status `miss`.

**`sim/episode_archive.py`** writes everything fetched to
`data/recaps` under the show and the episode: each candidate's extracted text
and its raw HTML, each subtitle file and the transcript it parsed to, each
digest, and the judge's verdict. **Nothing is overwritten** -- a re-fetch
writes the next version -- and `manifest.json` per episode says what each
file is, the URL it came from, when it arrived, how big it was, and which one
the judge chose with its reason and confidence. The directory is keyed by
show and episode with nobody's life in it, which is why one copy serves both
characters (`tools/isolation.py` names it as the machine's).

Verified sources (when: HISTORY Part C): anime via ameblo / hatena / goo blogs
(K-On ep15, a real Aパート/Bパート あらすじ); jdrama via `cinema.ne.jp`
(明日、私は誰かのカノジョ, a whole-series page) and `dramataro.com`. Weak
spots handled by trying several candidates: `blog.goo.ne.jp` DNS-failed
once here; official episode pages are thin in-character teasers.

## 3e. The episode account: what somebody who watched it would know

Everything above answers **which single page about this episode should be
trusted**. That is not the question a person who sat through the episode can
answer. The judge's winner is one blogger's reading of it, a few hundred
characters, and by the time it reached a character it had been cut again to
`watching.digest_max_chars` -- 600 characters. Measured on one episode of a
shop comedy: the character could say what its second half was about, because
the premise survived the cut, and could not name a single joke inside it,
because the jokes are exactly what a 600-character paraphrase drops
(HISTORY.md section 5.16).

So the losers are no longer thrown away. `sim/episode_account.py` takes
**every surviving digest with its scene list**, the transcript's account of the
scenes, and the official blurb, and merges them with ONE call (role
`episode_account`, `prompts/episode_account.txt`) into a single Japanese
record: the whole episode as prose in the order it happens, the scenes one line
each with how each comes out, the named パート, the running gags, up to eight
lines worth remembering, **what the episode points at** -- a place, a product,
another work, a meme of its era -- and what no source settled.

**The merge is a union, not a choice.** A scene one source has and the others
have not is still a scene of the episode. Where two sources contradict each
other the transcript settles it, then the anchor, and where neither can, the
disputed part is left out rather than picked. The prompt refuses anything no
source in front of it carries, and says why: an account that is missing
something is repaired by fetching more, and an account that invented something
is worth nothing. That is also why the `references` list is the part only a fan
post can fill -- an official page never mentions the background a shop's staff
recognise.

**A wider candidate set than the judge needs.** `Recap.candidates` takes `want`
and `tried_max` overrides (`recap.account_candidates`, `recap.account_tried_max`)
and the account's caller uses them: four pages settle which one to trust; a
running gag or a background reference is typically named by one 感想 post out
of six and by none of the official sources.

**Three levels, and the level decides whether it is ever built again**
(`EpisodeAccount._level`, measured on what went IN and never on how it reads):

- **watched** -- at least `account_min_chars` and `account_min_scenes`, and
  either the episode's own dialogue behind it or two independent readers
  agreeing. Never rebuilt, never re-fetched.
- **read-up** -- shorter, or one source.
- **thin** -- one source that carried little.

One blogger's misreading can produce a long confident account, which is why
length alone can never reach the top level.

**The cache rule changed with it.** `Recap.synopsis` used to end the lookup on
a judged page. It now ends the lookup on a judged page **with a watched account
beside it**; an episode read up before accounts existed is read up once more,
and once only, because the account is then in the machine's store and every
character after that reads it without fetching or paying for anything.

**Where it lives.** The machine's store (`machine/retrievals.py`, pool
`episode_account`) under the same key the fetched page uses -- the work's id
and edition where there is one. Her own save keeps her copy in table
`episode_accounts`, which is her record of having been told it; a character who
finds the machine's copy adopts it with nothing fetched. It is a table of its
own and not columns on `recaps` because `Recap.remember` DELETES the rows a new
reading replaces, and a re-read is exactly when an account is most wanted.
A fuller account is never overwritten by a thinner one, in either store.

**The external observer's view** (`machine/episode_reports.py`,
`recap.episodes_report_dir`, default `reports/episodes/`): one Markdown page per
episode -- the title in every script it has, the completeness and what it was
anchored on, the account, the scenes in order, the parts, the gags, the lines,
the references, what no source settled, and a table of every source with its
URL and its character count saying which ones were used -- plus `INDEX.md` over
all of them, and an `ep<nn>.json` beside each page for a tool that wants the
fields rather than the prose. It is the MACHINE's, like the archive it is
written from (`tools/isolation.py`): an episode of a television programme is
the same episode whoever watched it.

**Reading it up by hand**: `python tools/episode_account.py --ja <title> --ep N
--id <mal id> --english <title>` builds on a COPY of a save and reads one
episode up; `--print` shows what is on file and spends nothing; `--refetch`
drops the page and the account in BOTH stores first; `--plays N` does the last
N plays of his player instead of a named episode.

**Only-add is measured on a pair, not on the word.** `EpisodeAccount.standing`
is (how complete it came out, how many characters of it there are), and the
merge, her own table and the machine's pool all refuse a write whose standing
is lower than what is held. The rule used to compare the completeness word
alone with a fifth of the length of slack in front of it, so two readings of
エグザンプル ep6 replaced a 687-character `read-up` account with a
667-character one, in two processes twenty-four minutes apart, and the record
went backwards twice. A reading that comes out worse is archived under
the show and episode, named in the log, and is not the record.

**And a reading is counted for the MACHINE.** Each of the three character
processes allowed herself `sensors.retrievals_max_retries` attempts at an
episode whose account was not at watched level, so one episode cost up to nine
readings; `tries` on the account itself is the count and
`recap.account_max_tries` (3) ends it. The claim in `machine/retrievals.py`
already stops two processes searching the same episode at the same moment --
what it could not stop was the same episode being read up again nine times
over an hour.

## 3b. The knowledge base: what she looks up (`Lookup._attach_kb`, `Recap`)

The same fetcher is a general Japanese knowledge base -- fetch once, cache
in `recaps` under a `kind`, reuse forever (no repeated queries). When his
message names a thing, the lookup (`sim/lookup.py`) attaches, via `Recap`,
a fuller Japanese overview by kind:
- **anime** -> `series_overview` (the series premise) and, if he gave an
  episode number (`Recap.episode_in`: `8話`, `ep 8`, `S1E8`, `#8` -- never
  a bare number), `recap_for` for that episode's beats;
- **seiyuu** -> `person_overview` (the voice actor's Japanese Wikipedia
  bio -- richer than the MAL role list);
- **game / eroge** -> `work_overview` (the game / visual novel's premise;
  reads an アダルトゲーム as one).

All overviews read Japanese **Wikipedia** first (`_wikipedia_intro`: the
article's `<p>` lead + 概要/あらすじ or a person's 人物/来歴, cut at the first
stop-SECTION heading `id="..."` so an infobox occurrence does not truncate
the lead; refs and leaked inline JSON stripped), a blog/search fallback
otherwise. Anime / seiyuu searches use the **kanji** title
(`AnimeKB.japanese_title` / `person_name_jp`, from the MAL API and cached)
-- the romaji title finds only database sites, which `recap.blocked_hosts`
excludes. The overview / beats ride into her prompt as extra `looked_up`
lines with a label (`overview_label`: "who X is (the seiyuu)", "what that
game is"), to react to, never to recite. She is never told she looked.

**She can also investigate what she snoops.** The download snoop
(`tomoe/snoop.py`, `downloads` role) may emit a `LOOKUP: <title>` line when
one of his torrents (a game, an eroge, an anime) is something she would
actually look up; snoop then fetches its overview (`work_overview` /
`series_overview`), appends what she found to her reaction, and stores it
in the KB and as a private `lookup` event -- what she does with knowing is
the ick / withholding layer's business.

`/kb` shows the base (counts by kind, recent rows).

## 3c. Character pages (`Recap.character_page`, `Lookup._character_page`)

A character he names -- in any script -- is read at a fan encyclopedia
rather than his list's card, which has a romaji name and a voice actor and
nothing else. `Lookup` decides (classifier, told what is IN PLAY; a Japanese
name counts only with a show anchored -- see PROJECT §11.3) and calls
`character_page(name, show, lookup.character_query, lookup.character_hosts)`:
the query `site:dic.pixiv.net {show} {name}` against `search_engines`, the
first hit under a `character_hosts` prefix, the page through the same
throwaway Chrome, `_extract`ed, cached in `recaps` as kind `character`
under `ja = "show:name"` with the URL as source. **The full name comes free
with the hit**: a pixiv dictionary article's URL is its title, URL-encoded
(丸井みつば from `/a/%E4%B8%B8...`). The caller condenses the page with the
`character_digest` role (`prompts/character_digest.txt`: full name and
place in the show, temperament and running jokes, the two or three defining
relationships by name, what the show is remembered for doing with them, the
voice actor; なし for a page about someone else) to `lookup.character_max_chars`,
and that digest is the lookup's gist -- it reaches her as the pinned lookup
line, in her language. Shown on 丸井みつば: 3,624 characters of article to a
digest that carried 「みっちゃん」, 「ちょっとおませなサドガール」, the mutual abuse
with 杉崎みく, and 高垣彩陽.

## 4. How it reaches her (`Outlook.experience`)

`experience()` fires on a scene whose activity matches
`experience.trigger_regex` and also names a thing to have an experience OF
-- a category noun (`experience.object_regex`) or a title on her own
watchlist, because her verbs attach to him as readily as to a show and a
scene can say "K-On" and never say "episode" -- under a daily cap and a
gap between them (`experience.max_per_day`, `experience.min_gap_minutes`).
If the activity also matches `experience.watch_regex`
(watch / episode / drama / movie, not music / games / manga) and the
watchlist has a `current()` show, that show's title+episode is pinned in
the prompt ("SHE IS WATCHING: <title> episode N, use exactly this") and
`recap_for` is called **with the model client**, so her own watching gets the
same anchor and the same judge his does; the あらすじ
goes into the prompt under
`この話で実際に起きること` for her to react to (spoilers are fine -- she
just watched it). On a kept beat the cursor advances. Only the episode she
is ON is fetched, so she never knows future beats. Music / a game / manga
still free-pick as before.

**It does NOT get the same candidate set, and for a while reached neither of
the English sources.** `Recap.candidates` reaches the English episode list only
when the caller gives it an English title and his list's episode page only
when the caller gives it an anime id, and this caller gave neither -- so her
own watching ran on the Japanese blog search alone while his ran on three
sources, for the whole of the accurate-summaries build. The receipt was on
disk: the three episodes of her own list that had been fetched
(`data/recaps/Makeine-Too-Many-Losing-Heroines/ep001/`,
`Bocchi-the-Rock/ep002/`, `Chiikawa/ep002/`) carried no page from either
English source, and every directory keyed by an id -- every episode of his --
carried both. The English title her own list already holds is passed now, so
the English episode list is read; the id is not, because a show on her own
list has none and this caller holds no handle on his list's mirror, so his
list's episode page and the episode-title cross-check are still his path's
only.

## 5. Config

`experience.trigger_regex`, `experience.object_regex`,
`experience.watch_regex`, `experience.max_per_day`,
`experience.min_gap_minutes`; `watchlist.seed` and the gates on a pick of
her own (`watchlist.pick_enabled`, `watchlist.keep_min`,
`watchlist.max_open`, `watchlist.pick_every_days`, `watchlist.pick_tries`);
`recap.*` (`enabled`, `headless`, `query_template`, `series_suffix`, `overview_query`, `seiyuu_query`, `work_query`, `search_engines`, `candidates_max`,
`blocked_hosts`, `min_chars`, `max_chars`, `page_timeout_seconds`,
`poll_seconds`, `poll_max`, `page_min_html`, `search_min_html`,
`user_agent`), and under the same section the keys the accurate-summaries
build added: `candidates_target`, `anchor_max_chars`, `index_entry_gap`,
`poll_settle`, `fetch_workers`, `http_timeout_seconds`, `list_episode_url`,
`list_episode_index_url`, `wikipedia_api`, `wikipedia_list_title`,
`archive_dir`, `archive_enabled`, `subtitles_enabled`,
`subtitles_user_agent`, `subtitles_mirror_tree`, `subtitles_mirror_raw`,
`subtitles_archive_index`, `subtitles_archive_base`,
`subtitles_min_ja_share`, `subtitles_min_lines`, `subtitles_try_files`,
`subtitles_retry_hours`, `transcript_prompt_chars`,
`transcript_account_chars`; `slice_min_sentences` and `slice_min_chars` (what a
page taken on its heading alone must carry), `account_max_tries` (readings-up
per episode for the machine) and `transcripts_report` (the readable log of where
each episode's dialogue came from). Every one of those is read with a default in the
code, so the modules run against a config that has not got them yet.
`recap.candidates_target` (pages the judge chooses between),
`watching.summary_max_chars` (the raw cut, fallback only),
`watching.digest_max_chars` (the `watching_digest` role's ceiling);
`lookup.character_pages`, `lookup.character_query`, `lookup.character_hosts`,
`lookup.character_max_chars`; the roles `watch_pick`, `watching_digest`,
`digest_judge`, `transcript_digest` and `character_digest` under `models`.

## 6. Store

kv `watchlist`, kv `watch_pick_ts` and kv `watch_pick_log`. Table `recaps`
(one row per fetched episode, cached until it fails the episode-section
test or a digest role rejects it; `confidence` says provisional / judged /
anchored and a provisional row is read again rather than trusted, with
`candidates`, `reason`, `anchor`, `scenes` and `archive` beside it saying
what was decided and why; kind `series` for a series overview,
`seiyuu` for a voice actor and `eroge` for a game -- the kind
`work_overview` was called with -- all at ep 0; kind `character` at
ep 0 under `show:name` for encyclopedia pages; kind `eptitles` at ep 0 for a
series' episode subtitles and `wikieps` for its English episode list).

**And the machine's own store beside it**: `machine/retrievals.py`, its own
SQLite file at `sensors.retrievals_db` (`data/retrievals.db`), in
`tools/isolation.py`'s machine table. Every row written to `recaps` is written
there too, under the pool `recap` and a key that names the WORK where there is
an id to name it -- `anime|mal:1480|ova|ep1` -- and `<kind>|<title>|ep<n>`
where there is not (her own watchlist carries no ids). A title is not a name
for a work: two entries of his list share the Japanese title エグザンプル and
both hashed to one key. Her own `recaps` row carries the same id in an `aid`
column, and a reader that knows which edition it wants is never handed the
other one (`docs/resolver.md` §3.5). The key names the thing and never the
character. So is each page's digest (pool
`page_digest`, keyed on the page's own text and on the model that condensed
it) and each verdict between candidate pages (pool `digest_verdict`, keyed on
the exact question that was asked). Both characters read and write that file,
so an episode is fetched, digested and judged ONCE between them rather than
once each -- which is what both bots polling his media player would otherwise
cost. A fetch is claimed before it starts, so two processes reaching the same
episode in the same minute still pay for it once. The `recaps` table stays her
own record of what she has been TOLD, and when the machine's copy answers a
question her save cannot, the row is copied into her save with nothing
fetched. A page that turns out not to be about the episode is dropped from
both. One pass at boot (`sim/repairs.py share_recaps_once`, kv
`recaps_shared_once`) carried what each save already held into the machine's
store: 7 rows from each of the two saves, 14 in the store, no key held by
both. A second pass (`repairs.key_pages_by_id_once`, kv
`pages_keyed_by_id_once`) re-files a row whose title belongs to more than one
work under the work's id and writes the id onto her own rows.
Table `transcripts`, one row per episode a subtitle file was looked for,
`status` `ok` or `miss`. kv `subs_attempts` (one fetch attempt per show and
episode per day) and kv `subs_index` (the fan archive's entry index, a day
old at most). kv `watching_last` carries the current episode's `summary`,
`digest`, `scenes`, `quotes` and `confidence`; kv `watching_recent` carries
the same without the wide parts, **and both carry the file he played and the
unpaused seconds he sat through** (`path`, `watched`), which is what lets a
repair pass hand the transcriber a file rather than an episode number. kv
`watching_path_backfill` marks the one boot step that recovered those for the
rows written before they existed, by matching the row's own stamp against the
player's history. Table `episode_accounts` carries `tries`, how many readings
this episode has had for the whole machine. Table `transcripts` carries
`origin` (where the file was found) and `gpu_seconds` (what a transcription
cost), and kv `transcripts_report_caught_up` marks the one pass that put a
save's own transcript rows into the readable log.

## 7. Invariants and edge cases

- **`Recap` holds no model client of its own.** The three roles it drives --
  `watching_digest` once per candidate, `transcript_digest` once per subtitle
  file, `digest_judge` once over the survivors -- take the client as a call
  ARGUMENT from whichever module has one, and it is never stored on the
  object. `Recap` is built before the client exists and is not wired to it;
  a collaborator kept as an attribute set after construction would have to be
  a declared wire (`sim/wiring.py`), and a parameter is the honest shape for
  something used once per call. `character_digest` in `sim/lookup.py` is the
  caller's as before.
- **What reaches her stays a short line; the record is wide.** Her situation
  line is the digest at `watching.digest_max_chars`. The scenes in order, the
  exact lines a transcript gives, the candidates, the judge's reason and the
  confidence go on the `recaps` row and into kv `watching_last`, where a
  question weeks later can reach them. Nothing reads the scenes by default.
- **A table is not an account, and なし beats a plot written out of one.**
  `prompts/watching_digest.txt` returns なし for a page that names this
  episode but carries no events -- a running order, a cast list, an archive
  of other articles' titles, a navigation strip -- and says that a row
  marked 〆 in a running order names the character who shouts the show's
  title over the end of a segment, not the character that segment is about.
  Reading a 〆 row the other way is what put the wrong sister in a sketch.
  `prompts/digest_judge.txt` disqualifies a candidate that restates a
  running order, however complete the table behind it was.
- Selenium runs on a fresh temp profile, never her X session; `--no-sensors`
  / no-selenium boxes get `webdriver is None` and recap stays off (the
  model free-picks as before).
- Chrome lifecycle: every fetch opens a throwaway `recap_*` temp profile
  and `_close` quits it, reaps any Chrome/chromedriver still bound to that
  exact profile (headless orphans renderers; a bot killed mid-fetch never
  runs quit), and removes the temp dir. `Recap.__init__` calls
  `sweep_orphans` -- reap on the way IN -- so a restart clears anything a
  killed fetch left. Without this the throwaway profiles pile up as
  forever-running headless Chrome and disk dirs. `sweep_orphans` counts
  only DIRECTORIES it actually removed: the prefix also matches the test's
  scratch db, `rmtree` does nothing to a file, and the boot line reported
  the same six every restart.
- Headless is `recap.headless` (on). `/headless off` opens a window for
  the next fetch, X and the KB together, when a site has to be watched.
- A failed fetch (network, all candidates thin) returns `None` and the
  beat still happens, just ungrounded -- never a crash, never a blank.
- `advance` never passes `total`; a finished show drops out of `current()`.
- Fetch only the current episode: no future spoilers in her head.

## 8. Ops and tests

`/kb` (the knowledge base). `/watch` (list), `/watch add T|ja|kind|ep|total`, `/watch rm T`,
`/watch ep T N`, `/watch recap` (fetch the current episode now, to eyeball
a source), `/watch pick` (make her pick a show of her own now, past the
gates).

`python tools/episode_slice_test.py` is 35 offline checks over the episode
test: every form a 感想 post writes its number in, each against the same body
so only the heading differs; the same headings asked about the wrong episode;
an episode's own subtitle with no number anywhere, in the heading and in the
body; a whole-series post sectioned `#05` / `#06` / `#07`, where the right
section has to be cut and has to stop before the next one; and a bookstore
listing headed `第7話` whose body is twelve manga volumes, which must still
fail and whose refusal must name the form it was taken on.

`tools/recap_test.py` has two halves. `python tools/recap_test.py` is 56
offline checks with no network: the cursor, the link parse, the container
extract, the cache, the subtitle name tests and parser, the archive's
versioning and index, and one acceptance check per failure that motivated it,
each against the real page kept as a fixture in `tools/fixtures/recap` -- the
official page's nav strip, the programme running order, a blog's archive of
other articles, a blurb short enough to be the anchor, and a page whose
number matches and whose episode subtitle does not.

`python tools/recap_test.py --scored` scores accuracy rather than parsing,
against `tools/fixtures/recap/truth.json`: the episode rows the two live
saves hold, hand-checked against sources the pipeline did not read. Per
episode it counts the scenes named, whether they are named in the order they
happen, scenes invented and outcomes contradicted; the headline is episodes
with no error and at least two-thirds of the scenes. It reads the live saves
read-only. `--scored --run` runs the pipeline itself on a COPY
(`tools/harness.build_on`), which spends model calls and fetches pages;
`--only "Mitsudomoe:12"` narrows it. `--scored --archive` scores a run that
has already happened by reading the winning digest back out of the archive,
which costs nothing and is half the reason the archive exists.
