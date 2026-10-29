# TALKAPP -- `talkapp/server.py`, `channels/talkapp_bot.py`, `talkapp/app/`, `talkapp/android/`

Spec of record. Summary: PROJECT.md §6. Dated notes: HISTORY.md §5.75,
§5.83, §5.95 (photos), §5.97 (stickers), and Part B for the APK / push
history.

## 1. Purpose

The messenger she lives in, on his phone. It exists because Telegram
refuses the things the illusion needs: her 既読 at the exact moment
`store.mark_read` fires (her schedule becomes visible), his reads as real
events (app focused + bubble on screen) instead of a window-title
inference, a typing indicator driven by her compose delays, the group
chat as she sees it, and room for more than one character.

## 2. Processes and the seam

- **The hub** (`talkapp/server.py`, `Hub`): a standalone aiohttp process
  on `talkapp.host:port` (127.0.0.1:8765), fronted by `tailscale serve`
  for HTTPS on the tailnet (`https://YOUR-TAILNET-HOST.ts.net`), never
  the public internet; `talkapp.token` is the second wall (the server
  refuses to start without one). In SCAILV3 it was started by `talkapp.cmd` /
  the `SCAIL_hub` task, **before the bot** (the bot waits
  `talkapp.boot_wait_seconds`, 120). **This fork does not run the hub at
  all**: Momoka is a resident on the VN channel, `talkapp.enabled` is false,
  and the `SCAIL_hub` task was deleted on 2026-09-17. The code below is kept
  for reference and for a fork that turns TALKAPP on.
- **The adapter** (`channels/talkapp_bot.py`, `TalkappInterface`): a
  `Channel` (`channels/base.py`) like `TelegramInterface` -- the same
  nine-method surface (the seam the LINE experiment proved) plus what
  only this channel has, which the base gives Telegram as no-ops --
  synchronous `requests` because the loop already polls.
  `talkapp.enabled` picks it. Telegram is not a live channel in this fork:
  the object is only the console dry-run sink or the fallback for a config
  with neither the VN stage nor TALKAPP (`scail.py`).
- **The app** (`talkapp/app/index.html`, one file: CSS, JS, service
  worker at the root): served by the hub; `BUILD` stamp + `/ver` make the
  client reload itself when the file on disk is newer. The native Android
  APK (`talkapp/android/`) wraps it; the phone runs Firefox, the desktop
  Chrome. Web push (`talkapp.push_enabled`) is wired and dormant.

## 3. The hub's record

`data/talkapp/state.json`: `seq`, `subs`, and per character (`chars[cid]`)
`name`, `log` (the message rows, `talkapp.log_keep`), `typing_until`,
`group`, `presence`, `ops`, `ops_queue`, `ops_log`, `reaction`. This is the
CHANNEL's record, the way Telegram's servers hold the chat; the bot's
save is the simulation's truth. A row: `id`, `role` (`her` / `him`),
`kind` (`text` / `voice` / `photo` / `sticker`), `text`, `media`, `ts`,
`read_ts`, `ext` (the bot's message id), `bucket` (stickers). Media
(voice notes, photos, stickers) is copied into `data/talkapp/media/`.
`_char("")` is a 400 (an ops call without `char` once created a nameless
character the app listed beside her).

## 4. Routes

| route | who | what |
|---|---|---|
| `GET /`, `/app/*`, `/sw.js`, `/ver` | phone | the app, the worker, the build stamp |
| `GET /chars`, `/history?char&before` | phone | the roster; the last 80 rows, typing, group, presence, reaction. `/chars` leaves out a character registered hidden -- one who has no chat with him -- unless the caller passes `all=1`, and every row carries `hidden` so the caller can tell which is which. The home list and the Android notification service ask without the flag; the ops switcher asks with it |
| `WS /ws` | phone | live events: `message`, `typing`, `kidoku`, `read`, `edit`, `delete`, `group`, `ops`, `ops_result`, `reaction`; the phone sends its own events (`_phone_event`: his reads, his messages) |
| `GET /media/<f>`, `/avatar/<Name>`, `/reaction/<f>`, `/scenery/<name>` | phone | files; the avatar falls back to a letter circle; scenery is the ops view only. A media file is cacheable: a year and `immutable` when its name starts with the millisecond it was copied in (voice, photo -- that name can never stand for other bytes), a day when it does not (a reaction frame is named after the frame). `?dl=<name>` sends the same file as an attachment under that name, sanitised to letters, digits, dot, dash and underscore |
| `GET /file/<name>` | phone | a text file the bot left in `data/talkapp/files/` (`/context full`: her whole prompt), linked from the ops log |
| `GET /vapid`, `POST /subscribe`, `/push_test` | phone | web push |
| `POST /bot/register` | bot | `{char, name}` |
| `GET /bot/updates?char` | bot | his new messages since the bot's last id |
| `POST /bot/send`, `/bot/edit`, `/bot/delete`, `/bot/typing` | bot | her bubbles and their edits |
| `POST /bot/voice`, `/bot/photo`, `/bot/sticker` | bot | media rows; a sticker takes `ts` in the past (the backfill) and is inserted where its time falls, `quiet` skips the push |
| `GET /bot/reads?char` | bot | his view-based reads of her rows, for `store.mark_read` |
| `POST /bot/state` | bot | her reads of his rows, the group view, presence, ops payload, the current reaction (broadcast when changed) |
| `GET /app` | phone | what the phone is running against what is served: `installed`, `served`, `state` (current / behind / never reported). The page posts its own `versionCode` on every `/ver` poll, so whether a built APK was ever installed is something the system knows instead of a question for him |
| `GET /ops`, `POST /ops/cmd` | phone | the ops payload + command log; a slash command queued for the bot, never the chat |
| `GET /bot/ops?char`, `POST /bot/ops_result` | bot | the queue, cleared on read; the command's output |
| `GET /health` | anyone with the token | liveness |

Every route checks the token (`_authed`: header or `?key=`).

## 5. What rides on the poll (`TalkappInterface`)

Every loop pass (`get_new_messages`, and between bubbles for
interruption): his messages come down (kv `talkapp_last_id`); his exact
reads come down and are stamped with `store.mark_read` (`sim/receipts.py`
prefers a stamped `read_ts`). Throttled to `talkapp.state_push_seconds`
(20): her reads of his messages, the group chat as she sees it
(`_group()`: delivered beats plus yesterday's, all of `cast_chat`, the
live exchange, every room she was sent that somebody else owns
(`peer_rooms`), the names that mean her (`me`), the graph payload; sent
only when its SHA-1 changed; every beat, exchange and turn stamped with
the real instant it happened, `_ts`),

one presence line (`_presence()`: where she is as a phone could show,
`schedule.presence_label` on the block she is in, with the program's own
words (`presence_words` and `presence_by_phone` in its words table) -- the
second character's table has no whereabouts words, so she gets the phone
rule alone, asleep or online, because a schoolgirl's word table matched
"bath" to "away" while she was replying from it),
the ops payload (`Ops.payload`), and the current reaction
(`reaction_provider`). `get_ops_commands` / `post_ops_result` close the
ops loop through `App.run_command`.

Sends: `send_typing` (the indicator for `talkapp.typing_seconds`),
`send_message` (returns the hub row id, stored as `tg_id`), `edit_message`
/ `delete_message`, `send_voice` / `send_audio`, `send_document`,
`send_photo(path)` (a `photo` row before the bubbles that caption it),
`send_sticker(path, bucket, ts, quiet)`.

## 6. The app

**Reaching the top of the chat loads the page before it.** The hub has always
taken a `before` timestamp and answered with the 80 rows under it; the client
asked once per open, with the character id and nothing else, and assigned the
answer -- so the top of the scroll was whatever row was eightieth from the end
at the moment the chat was opened, and reaching it did nothing, because nothing
was listening. A scroll listener on the chat container calls the route with
`before: msgs[0].ts` when he is near the top, PREPENDS the page (never
assigns), stops on an empty page (the hub sends no `has_more`), and holds the
line he was reading by moving the scroll offset by exactly the height the new
rows added, the way `renderOps` keeps its offset across an `innerHTML`
rebuild. A page still in flight when he opens another character or reloads the
same chat does not land in the new list. `reloadChat` and `openChar` are
unchanged: the newest page, scrolled to the bottom. **`takeSwipes` merges on an
older page**, because the hub bounds the `swipes` it sends to the rows of the
page it served (`h_history`), so an assignment there would drop the candidates
of every newer message on screen -- measured: the newest page of the second
character's chat carries one message's candidates and all three older pages
carry none. Which model writes her words is about the chat rather than the
page and an older page leaves it alone. Checked by
`data/retired/20260906_1955_rena_rooms/scrollback_test.js`, which lifts the
real functions out of the client and pages the second character's whole log
(299 rows, four pages) against a DOM stub; run against the previous client it
says the client cannot scroll back at all.

Views: home (roster with previews), chat (bubbles, voice player, photo
`<img>` -- tapping any photo, hers or one in a friends' room, opens it
full size in a lightbox overlay, tap again to close --, sticker as a bare LINE-sized image, the header avatar = her
reaction when there is one with the bucket beside the presence line,
typing, 既読 marks, his reads observed by an IntersectionObserver -- a
bubble of hers on a visible screen is a read), her phone (the group chat
and each LINE thread, built from the group payload; a burst splits per
`Name:` prefix and its gloss with it; `backstage` shows undelivered
beats), irl (the in-person moments), ops (the payload sections, the
command menus, the command log). `canon(who)` maps a prefix to the roster
name; nicknames never appear as prefixes.

**Which bubbles are on her side comes down in the payload.** `_group` sends
`me`: every name that means the open character, as her own roster resolves them
(`sim/roster.self_names` -- her config name, her Japanese name and its reading,
her sheet's aliases, and what each person on her roster calls her). It was a
pattern with one character's names written into the client, and that was wrong
twice: it never matched the name her own exchange turns are actually filed
under, so 135 of the first character's own bubbles were drawn as somebody
else's; and read for anybody else it matched the ROOM OWNER's name, so a room
the fourth character had been sent drew the owner's turns as her own. A payload
from a bot too old to send `me` marks nothing as hers, which lasts one push.

**The group tab for a character who owns no conversation.** A character who
reads a world somebody else keeps writes no beat and holds no exchange, so
`cast_beats` and `cast_chat` are empty for her and the only record of the
friends' chat she has is her copy of the rooms she was sent (kv `peer_rooms`,
`docs/peer-talk.md` §4b.5). `_group` draws it: one exchange row per room, the
kind and the owner off the record, `present` beside it, and every turn on the
real instant it was said. Her panel used to hold one bubble -- a
leftover sticker beat her own planner had written before the world-reader rule
went on -- above a group chat she had spoken six turns in. The day the header
names falls back to the newest room she was shown when she has no beat record,
or it read "her , times on your clock".

**Audio in a bubble.** Both ways a line of hers gets a sound end in the same
place: the file name on the bubble's `voice` field. A voice note she sent
arrives as `POST /bot/voice` with no `attach_to` and the hub hangs it on her
newest text bubble within `VOICE_ATTACH_SECONDS`; a line he tapped names its
bubble in `attach_to` and lands there however long the render took. The chat
draws the two the same: a bubble that has a file gets the inline
`<audio controls>` player -- a scrub bar, and beside it a save control
(`a.dl`, a small ⤓). Playing it streams from the hub, which tells the phone
to keep the file, so every play after the first reads the phone's own disk.
The save control is the same URL with `dl` set to
`<character>_<YYYY-MM-DD>_<HHMM>.<ext>` on his clock, which makes the hub send
it as an attachment; in the app that reaches Android's download manager and
lands in the phone's public Downloads directory, with a toast naming it. The
speaker (`sayButton`, a small 🔊) is only for a line
with **no** sound yet, and only on a character whose bot renders on request
-- `tts.on_demand` in her own config, which the bot declares as `speak` at
registration and the client reads into `CAN_SPEAK`. Tested by
`data/retired/20260904_001648_voice_cache/voice_save_test.js`, which lifts the
real `bubble` and `stamp` out of the client and runs them against a DOM stub
and the hub's own rows, and by the header test beside its step record (media_headers_test.py under data/retired) beside it, which calls
the media route as a plain method and reads the headers it would send.

**Finding the audio file for a line she spoke**, from a time on his clock:

1. In `data/talkapp/state.json`, under `chars.<character>.log`, find the row
   whose `ts` (a Unix timestamp on his clock) is the minute wanted. Its
   `voice` field is the file name; a standalone note has it on `media` with
   `kind` `voice` instead.
2. That file is `data/talkapp/media/<name>` -- the hub's copy, prefixed with
   the millisecond it was posted, which is when the render finished, not when
   the line was said.
3. The bot's own kept copy is `<tts.cache_dir>/<key>.ogg`, `data/voice/` for
   both characters, where the key is the part of the hub's name after the
   underscore. `data/voice/index.json` maps that key to the exact text, the
   first render and the number of uses.
4. The key is `sha1(voice_id + NUL + text with all whitespace removed and
   trailing 。！？!?…・ stripped)`, first 16 hex characters
   (`channels/tts_handler.py:_key`). The voice is `tts.voice_id` from that
   character's own config, `shared` when she has none, which is what keeps
   one character from being handed the other's audio for the same words.
5. The raw FLAC before the Opus conversion is
   `data/tts_jobs/outputs/out_<YYYYMMDD_HHMMSS_micro>.flac`, stamped with the
   moment the render started. `session.log` in the run directory for that
   hour names the line at that second -- `[TTS] rendering:` for a voice note
   she sent, `[TTS] he asked to hear:` for one he tapped.

The ops commands are **menus of buttons**, one open at a time (`OPS_MENUS`:
her, day, him, people, X, scenery, her head, memory, world, run). It was one
flat strip that grew every time a command was added. Every button is a real
command -- checked against the dispatch in `scail.py`, since a button that
names a command that does not exist just returns "unknown command" and
looks like a bug in the thing it was meant to inspect.

**Everything in the app is drawn on HIS clock.** The record keeps her wall
time and her date -- a date string and "21:07" -- which is a time only if you
already know whose clock it is, and the app had two of them: his chat thread
stamped from the message's real `ts` through the browser (his), her phone and
the irl panel printed the record's string raw (hers). Many hours apart, two
taps apart, neither labelled. `_ts` in the adapter turns each row back into a
moment on her clock (`WorldClock.ts_of`) and the app draws it with the same
`hm(ts)` his own bubbles use, so a group line at her 20:18 reads 07:18 to him.
`tlabel` / `ttitle`: his time in the row, hers in the hover. The day separator
comes from that instant too (`dayOf`), so it agrees with the times beneath it
-- her evening is his same-day morning, her morning is the day before his --
and the panel header names its unit: *her <date>, times on your clock*.
A row with no stamp keeps its own string, so an old payload still renders.
Ordering is by the instant, which also fixed the bucket sort: it compared
`date + "HH:MM"` as text, so a beat at 00:23 sorted to the head of its day
instead of into the night it belongs to.

**A link out of the app goes to his browser.** The WebView used a plain
`WebViewClient`, so tapping a scenery thumbnail loaded x.com in place: no
address bar, no way back but the back key. `MainActivity.shouldOverrideUrl
Loading` compares the host with the hub's own and hands anything else to
`ACTION_VIEW` with `FLAG_ACTIVITY_NEW_TASK`, falling through to the WebView
if nothing takes it. APK 349723.

**A download is either an install or a file he keeps.** A WebView downloads
nothing by itself: it calls the app's save handler (`save` in MainActivity.java), which hands the APK link and
any foreign host to the system browser as before, and puts a file under the
hub's own `/media/` into `DownloadManager` -- public Downloads, the name from
the link's `dl`, the completion notification on, and a toast saying where it
went. Before this every download went to the browser, so tapping save on a
voice note opened it in whatever app claimed the URL instead of keeping it.

**Notifications** are native, not web push: `NotifyService` (a foreground
service in the APK) holds one WebSocket to the hub and posts the
notification itself, so the delay is the socket's round trip. One slot per
character (`1000 + hash(cid) % 1000`), nothing while `MainActivity.visible`,
and the tray cleared when the app opens.

A reply is one to three bubbles and each one arrives as its own socket
event, so each one used to ping the phone -- three alerts for one thing to
say. Inside `talkapp.notify_burst_seconds` of the FIRST bubble of a burst
from the same character, the notification is rebuilt with every line of the
burst in it (`InboxStyle`) and `setOnlyAlertOnce`, so the tray updates in
silence: one ping per burst, at its start, and the rest fill it in. The
window is served in `/chars`, so it changes without a new APK. It is timed
from the first bubble, not the last, so a long burst cannot roll the window
forward indefinitely. Opening the app clears the burst state as well as the
tray -- otherwise the next thing she said after he closed it would be folded
into the old burst and arrive silently.

## 7. Config

`talkapp.*`: `enabled`, `host`, `port`, `boot_wait_seconds`, `token`,
`push_enabled`, `notify_burst_seconds`, `typing_seconds`, `log_keep`,
`state_push_seconds`.
`telegram.max_message_length`, `telegram.console_only` are shared.
`character.name` is the registered character id's display name.

## 8. Invariants and edge cases

- Hub before bot; restart both when a route changes; the bot alone when
  only the bot changed. Launch only through the scheduled tasks.
- Nothing is recorded before the action: a bubble is written to the
  store once the hub has accepted it; a lost reply is re-queued by
  `App.recover_lost_reply`.
- A sticker or a photo is a hub row, never a `messages` row: it is the
  operator's window, not something she said, and is never in her
  context.
- Her wall time never reaches a screen unlabelled. The record is hers;
  the app is his. Anything drawn from a record's `hm` carries the `ts`
  the adapter stamped, and a turn earlier than the exchange that opened
  it has crossed midnight (a chat past the last light), so it takes the
  next day.
- The group payload is the whole `cast_chat` record (`exchange.keep`);
  beats older than yesterday survive only as the exchanges they became.
- The hub loads its state once; a stray entry is dropped at `_load`, and
  an edit to `data/talkapp/state.json` while the hub runs is overwritten by its next
  save.
- The token lives in `config.json` only; `_redact` keeps Telegram's out
  of logs, the hub's never enters a URL the app logs.

## 9. Ops

`/ops` (the payload as JSON), the app's ops bar (every slash command;
`/context` the sections, `/context <name>` one, `/context full` her whole
prompt as a page via `/file/`),
`/push_test` from the app's menu. `tools/smoke.py` builds the App with the
adapter in console mode.

**The chips at the top of that screen are every character on the hub,
including one he has no chat with.** A character whose sheet answers `none` to
having a chat with him registers hidden, so that his phone lists no
conversation for her -- and the switcher was built from the same `/chars` call
as the home list, which left her backstage with no door even though the hub
was serving her payload and would take her commands. `loadOps` asks
`/chars?all=1`; the home list and the notification service still ask without
it. Choosing her makes her the current character, which is what the ops
payload, the command post and the screen's title all key off. Nothing else may
follow: the live socket drops a message, a typing flag, a read mark, a face or
a model change about a hidden character rather than letting it edit the chat
state, which still belongs to whichever chat was open last, and a first open
of the ops view lands on somebody he has a chat with rather than on her.

A command from the ops bar is a `POST /ops/cmd` with the character and the
text; the hub keeps the last 20 on that character's queue, her bot drains
them on its next pass (`GET /bot/ops` clears the queue on read), runs each
one and posts the answer to `POST /bot/ops_result`, which the app reads back
from `GET /ops` and shows in the ops log. Nothing of this enters her chat.
`tools/poke.py <char> <command> [--wait N]` is the same door from a terminal:
it reads the token out of `config.json`, queues the command, and with `--wait`
follows that character's newest run directory `session.log` and the hub's ops
log so the answer and what the bot did are both visible where it was typed.
It is how the three forcing commands (`/idle`, `/reply [again]`,
`/selfstart [why]`) are used while testing, and it never opens a save.

**Two lengths on that screen.** What her phone last showed her of his machine
goes into the payload whole (`Ops._phone`, `last_digest`) and is drawn in a
`<pre>` that wraps, inside a view that scrolls, in a section that folds; it
used to be cut at 900 characters, which is shorter than most digests either
character writes, so the field ended mid-sentence with no way to read the
rest. An answer to a command is a different road and is capped where the hub
files it (`ops_log`, 30,000 characters a row, 60 rows kept). An answer that
outgrows that belongs in `data/talkapp/files/`, served at `/file/<name>`, the
way `/context full` sends her whole prompt -- not on a bigger row.

The view is rebuilt from each payload the bot pushes, about every
`talkapp.state_push_seconds`, by assigning `innerHTML` on the scrolling
container; `renderOps` keeps the scroll offset across that, or a long digest
would throw him back to the top mid-read.

## Links and previews

A URL in a bubble is a blue link (`--link` in both themes) that opens in
his browser -- the Android shell hands any host but the hub's to the
system (`shouldOverrideUrlLoading`). The first link in a message gets a
card under the text (`previewCard`): the client asks the hub
`GET /preview?url=` (`Hub.h_preview`, keyed, cached an hour, a failed
lookup is a card with just the host). An X status is resolved through
fxtwitter's JSON (author, text, photo or video thumbnail); any other page
by its OpenGraph tags (`og:title`, `og:description`, `og:image`,
`og:site_name`). The voice-note player is appended with
`insertAdjacentHTML` before the card: `innerHTML +=` re-parses the bubble
and detaches the card node the fetch is about to fill.

## 10. Another answer to the same message, and which model writes it

Two controls in the chat, his design: a swipe on any message of hers,
and the model her voice is written on.

### 10.1 The prompt is frozen at reply time

Every reply she delivers keeps the exact chat-completion request it was
drawn from, in HER save, table `reply_prompts`:

| column | what |
|---|---|
| `msg_id` | the `messages` row the first bubble of the burst made -- the anchor |
| `msg_ids` | every row of that burst, so a swipe asked for on the third bubble finds the same prompt as one asked for on the first |
| `char` | the character id, so a row is never read as somebody else's |
| `ts`, `model` | when, and the model name the call went out on |
| `messages_json` | the whole array: the system prompt, the thread, the final user turn with the carrying block and the situation in it |
| `params_json` | temperature, thinking, effort, max_tokens as they were |
| `text`, `sat` | the bubbles she sent, joined; and which candidate the conversation now goes on from |

`Persona._draft` keeps the array it went out on (`last_messages`) and what
the call cost; `Persona.generate` files both under the bubbles it settled on
(`last_reply_prompt`) after the editor and the search re-draft, and before
the nudge comparison draft, which sends a prompt she was never given. The
row itself is written by `Delivery._freeze` the moment the first bubble has
a row, and extended as each further bubble lands -- never held to the end of
the burst, because a stop is `Stop-Process -Force`. `Delivery._prompt_for`
files a prompt only against the bubbles it actually produced, so `/send
<text>`, a replaced reply and a photo caption carry none.

**Why frozen.** A swipe re-runs that array byte for byte. By the time he
asks, her gauges have decayed, the director has written another scene and
the thread has grown; a prompt rebuilt at that moment would answer a
different question and would quietly rewrite what she was answering.

### 10.2 Drawing it again

`persona/delivery.py` holds the engine, as functions over the App the way
`sim/inflight.py` settles what a dead process left. A draw sends the frozen
messages to whichever model the chat is toggled to, with the FROZEN sampling
settings, and writes the answer to `swipes` the moment it exists:
`(msg_id, n, model, text, voice_path, ts, prompt_tokens, completion_tokens,
cached_tokens, cost)`. **Candidate 0 is what she actually sent.**

The answer is split the way a reply is split -- the spoken line lifted out
and the draft cleaned with the persona's own two pure passes -- but NOT with
`Persona._split`, which also lifts a sticker out, banks a search she asked
for and resolves a shared post. Those are things a reply does on its way
out; a candidate he is only looking at must do none of them.

**The cache.** On the same model the swipe's prompt is byte-identical to the
original's for the whole system-plus-thread prefix, so the host answers
nearly all of it out of its cache and a draw costs little more than its
output. On a different model it is a cold call and the whole prompt is
billed fresh. `cached_tokens` is kept per candidate and shown in the strip
(`N cached`) and in `/swipe list` for exactly that reason: the difference
is visible rather than assumed.

### 10.3 Keeping one

Looking at a candidate changes nothing at all -- it is a read of `swipes`,
and `viewing` in the client is never sent anywhere. Keeping one is the only
write, and it is the same three steps `tools/replace_reply.py` does by hand:

1. her record takes the words, through `/context msg set`'s own path
   (`ContextView.message_set`), never an outside write;
2. the hub's copy is edited (`POST /bot/edit`), so his phone shows what her
   record holds;
3. a row that had audio on it has the note rendered again through her own
   `TTSQueue.render` and re-attached (`POST /bot/voice attach_to`) -- a hub
   edit changes text and leaves the audio, which would otherwise be the old
   words spoken.

One candidate maps onto the rows the burst already has, in order. The shape
is kept where the counts agree, which is nearly always -- both characters
send one bubble per reply (`delivery.split_on_blank_lines`). A longer answer
folds its surplus into the LAST row rather than adding one, because a new
row would be stamped now and would sort after everything he has said since;
a shorter one drops the rows it does not need, from her record and from the
hub both.

Because `sim/thread.py` rebuilds the thread from the store on every call,
the next reply carries the version he kept and no other. **A candidate
nobody kept is in no prompt anywhere.** Nothing is written to `events`: a
draw is the operator looking, not something she did.

### 10.4 The model toggle

`llm.py` names the nine roles that write in her words in one place
(`LLM.VOICE_ROLES`: persona, revise_self, spiral, approach, morning,
anticipation, reflect, diary, wonder). The toggle sets kv
`voice_model_override` on her save and `LLM.call` honours it for those roles
only -- her director, her state read and her judges stay where her config
put them. It is the narrower switch, so it wins over `/model`'s all-roles
pin for those roles: picking a model in the chat header has to move her
voice even when every role is pinned.

`api.voice_models` is the menu (seven names, his list); a name the active
provider has no slug for is not offered, because it would go out as a
literal and be rejected. **The choice is live and is never written to the
config file**, like `/model` -- it is a thing he flicks between two replies.
`tools/set_model.py` is what keeps a choice.

### 10.5 Routes and commands

| route | who | what |
|---|---|---|
| `POST /swipe {char, id}` | phone | draw that reply again; queued for her bot, like a line he taps to hear |
| `POST /sit {char, id, n}` | phone | keep answer n; checked against what the hub holds |
| `POST /model {char, model}` | phone | the model her voice is written on; checked against what her bot said it accepts |
| `POST /bot/swipes` | bot | the candidates for one message and which is sitting; kept BESIDE the log, trimmed to the messages still in it. MERGED with what is held: a post carrying only `pending` (a waiting line, or the empty string to clear it) or only `reconstructed` leaves the candidates alone, and a post of candidates leaves those two alone |
| `WS` | phone | `swipes` (a candidate landed, one was kept, or the waiting line changed; carries `pending` and `reconstructed`) and `model` (the toggle took) |
| `GET /history` | phone | now also `swipes`, `voice_model`, `voice_models`, because the chat can be opened straight from a notification |
| `POST /bot/state` | bot | now also `voice_model` / `voice_models`, broadcast as `model` when either changes |

The hub answers none of it itself: it has no model, no key and no copy of
the prompt a redraw must be made from. The candidates live in
`chars[cid].swipes[<hub message id>]` and never in `log` -- a candidate
nobody kept is not something she said, so it is never a row, never a
notification and never a chat preview.

Commands (`/help` has the lines): `/swipe [<id> [model]] | list [id]`,
`/sit <id> <n>`, `/voicemodel [name|auto]`. An id may be the hub's or the
record's; the hub's is tried first, because the app is what asks (141 in the
store was 1813 on the hub).

### 10.6 In the app

One quiet three-dot button (`⋯`) at the foot of each of her bubbles opens a
menu with two rows: **Regenerate** (draw again, on the model the header is
toggled to; greyed while a draw or a rebuild is in flight) and **Swipes...
(N)** (open the viewer; N is how many answers exist, the sent one included).
A bubble with more than one answer also carries a small "N answers" tap
target, and a waiting line under it while something is in flight. The
bubble itself always shows the one the conversation goes on from; looking
happens in the viewer and changes nothing.

The viewer is a sheet over the chat: the time and her name at the top, then
the model, tokens in (with what the host served out of its cache), tokens
out and cost of the candidate on screen, green with "the one the
conversation goes on from" on the sitting one, and "what she sent" on
number 0; the candidate in full; then `‹ 2/4 ›` to walk them, **Regenerate**,
and **Keep this** -- the only control that writes, present only when the
one on screen is not the sitting one. A record whose prompt was rebuilt
rather than kept says so in the viewer in the warning colour, and the
"N answers" tag under the bubble carries "rebuilt".

The strip this replaced (a `⟳` glyph, arrows and a `keep` chip inside the
bubble) was not recognisable from the phone. The header carries a chip
with the model name; tapping it opens a picker of `voice_models` plus
`auto`, and the bot pushes its state the moment the pick takes, so the
chip changes within the poll rather than after the next throttled push
(it used to lag by up to `talkapp.state_push_seconds` and read as a tap
that did nothing). The APK is a WebView over this page, so no Android
source changed and no new APK is needed for any of it.

### 10.7 A reply from before the prompt was kept

Every reply sent before the freeze went in (the dated line is in
HISTORY.md under the channels section) has no `reply_prompts` row, and the array it went out on
cannot be read back out of the record. It can be rebuilt, and a swipe on
such a reply does that first: `sim/reconstruct.py` -- the same copy and
cut `tools/regen_reply.py` uses -- takes a consistent copy of the save
through sqlite's backup API, cuts the history and every timestamped table
back to the moment of the message she was answering, builds the whole
runtime on the copy in console mode with no sensors, and runs the assembly
once with the model stubbed. What that produces is the array (240 turns
and 78k characters for the second character's message 274, 2.6 s of
assembly on top of the runtime build).

It runs as a **second process** (`python -m sim.reconstruct`), started by
`App.rebuild_reply_prompt` from a thread beside the loop: a runtime built
beside a live one inside the same process would take over the log
directory, the network watch and the one-per-save lock. While it runs the
bot posts a waiting line for the message (`post_swipes_state`), the chat
shows it, and a second tap on the same message is refused rather than
starting another. When it lands the row is filed with `reconstructed = 1`,
what she sent is filed as candidate 0, the first draw goes out on the
toggled model, and the ops log gets the report. A failure (the message is
not hers, nothing of his precedes it, the copy could not be cut) is one
line in the ops log and the waiting line is cleared.

What comes back is not what she was given. The parts read out of the
record -- her history, what she carries, her own words -- are the same
bytes; the parts that were live at the time and are not kept per minute
are rebuilt from the nearest thing the record holds. The row, the viewer
and `/swipe list` all say so.

Checked by `tools/swipes_test.py` (the tables in `tools/smoke.py --store`
form; the whole run builds the second character on a copy and drives a reply
through the real path with the model stubbed).
