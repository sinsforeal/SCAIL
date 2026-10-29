
---

## 13. Data model

`data/world.db` is the live save (`store.py` `Store`, sqlite; one bot per
db). Never point a sim at it. Superseded files go to
`data/retired/<timestamp>/`, never deleted; `App.backup_db` keeps dated
copies under `data/backups/` for `backup_keep` days.

**Tables.** `scenes` (ts, date, hm, scene json, raw), `events` (ts, date,
kind, text, salience), `state_log` (ts, date, gauges json, reasons;
written when something happened), `schedules`, `days` (narrative,
summary, user_facts), `messages` (role, text, self_started, delivered_ts,
read_ts, tg_id), `digests`, `threads`, `user_facts`, `kv` (everything
else, JSON by key), `self_memories` (with `receipt`, filled only on a row
written in from a character's own archive), `cast_facts`, `seen_images`,
`scenery`, `reply_prompts` (the prompt a delivered reply was drawn from,
frozen at the moment she sent it, `reconstructed` marking one rebuilt after
the fact) and `swipes` (every answer to one of those prompts with its model,
its tokens and its cost -- number 0 is what she actually sent, and only the
one he sits reaches her record, so her history never carries a version she
did not send); the anime KB (`anime_kb`, `anime_cast`, `person`,
`person_role`) in the MAL daemon's db; `data/reactions/<name>/reactions.db`
(`reactions`, `videos`, `appearances`) built by the tool. The hub keeps
its own log in `data/talkapp/state.json`. **What was fetched about the world
is the machine's, not a character's**, and lives outside every save: §11.6
lists those stores, and `data/retrievals.db` (§11.6, `docs/retrievals.md`) is
the one both characters read so a page is fetched and condensed once.

**Files she reads as reference** (edited by hand or by a tool, re-read on
change): `data/cast.json` (the sheets, kanji, nicknames, weeks),
`characters/tomoe/household.json`, `data/places.json`, `characters/tomoe/map.json`,
`data/school_calendar.json`, `data/jp_holidays.json`,
`data/local_events.json` (tool), `characters/tomoe/zeitgeist.json` (tool),
`characters/tomoe/beliefs.json` / `characters/tomoe/self_beliefs.json` (seed a fresh save only),
`characters/tomoe/taste.json` (his), `characters/tomoe/voice_rules.json` (what counts as out of
voice, per speaker and per role), `prompts/bible.md`, `prompts/style.md`,
`prompts/style_ja.md` (her Japanese, for everyone who is not him), and
`prompts/cast/<key>.md` -- one character sheet per person, theirs the way the
bible is hers.

**kv keys by module** -- generated from the code at the end of this
file (§18). A key that appears there and in no module is a leftover.

---

## 14. Running and operating

    python tomoe\run.py                   # the first character, live (resident\run.py: the second)
    python tomoe\run.py --console --no-sensors
    python tomoe\run.py --sim "2026-08-18 09:00" --speed 60 --hours 5 --say "10:35|hey"
    dryrun.cmd                            # sim, own db (data/dryrun.db), console
    run.cmd                               # the first character, live
    yukarin.cmd                           # the second character, live, beside her
    mal_daemon.cmd                        # the MyAnimeList mirror daemon, detached under pythonw
    mal_watchdog.cmd                      # one health check of the daemon above; the scheduled task below runs this every 5 min
    tools/mal_watchdog_setup.ps1          # (re)registers that scheduled task; run once, or again if it's ever lost
    restart.cmd [all|mal|<key>] [--no-smoke]   # the way to bounce anything; the character keys are characters.json's
    restart.cmd --list                    # what it would act on, its task and its pid, and nothing else
    startall.cmd [--no-smoke]             # start whatever is down, in the same order; anything already up is left running
    stopall.cmd [--no-credit] <reason>   # stop the whole of it on purpose, with the reason on every character's record
    python tools/smoke.py                 # before every restart
    python tools/registry.py              # the register: every character that runs as a process

**Every character that runs as a process is a row in `characters.json`** at
the project root, read by `tools/registry.py`: the key the operator types at
a command line, her full name, the id she registers with the hub, her config,
her save, the program package that builds the rest of her, her launcher, her
scheduled task, and the exact command-line pattern her process is found by.
The restarter's table and its start order come out of that file, and
`tools/character_names.py` takes its list of program packages from it, so
adding a character is her config, her sheet, her prompts, her save, a
launcher, a scheduled task and one row -- no code. The pattern is written by
hand in the row rather than derived from the launcher, because the restarter
KILLS what it matches and a derived pattern that drifts kills the wrong
thing. **A bot never reads the register**: a character that could read it
could read another character's config and save, and what she may know of
another character is her own `peer_talk.contacts` and the words that arrive
(§9.9, `docs/peer-talk.md`). `python tools/registry.py` prints the table and
names any field or file a row is missing.

**`restart.cmd` is how a process is bounced**, and it exists because doing it
by hand is three commands per process and two of them are easy to get wrong.
It runs the build check first and **refuses to restart anything if it fails**,
because a fix on disk that will not import takes a character off the air rather
than improving her. It stops in reverse order and starts the machine's own
processes first.

**The hub is not a target of this fork.** The TALKAPP hub (`SCAIL_hub`,
`talkapp.cmd`) is not run: Momoka is a resident on the VN channel,
`talkapp.enabled` is false, and the hub's server reads `config.json`, which
this fork does not keep. Its task was deleted on 2026-09-17; `tools/restart.ps1`
no longer knows the name.

**Two targets, and one of them is the machine's.** The MyAnimeList mirror
daemon is written into the script, because it does not belong to a character --
there is one of it and it serves the machine -- while the characters come out
of the register. The order is the daemon, then the characters: a character
reads the mirror, and the daemon is what keeps it current. `restart.cmd mal`
bounces the daemon alone; `restart.cmd --list` prints the whole table -- each
target's task, its launcher, whether that task exists, and the pid it currently
matches -- and does nothing else, which is the cheapest way to check the
matching before trusting it with a kill. **A task that exists but runs another
checkout's launcher is repointed**, not left in place: on 2026-09-17 the hub and
daemon tasks still named SCAILV3, so `startall.cmd` started the wrong
`talkapp.cmd` and reported the hub as not coming up while its task sat at a
`pause` prompt.

**The daemon was outside all this to begin with, and could not be restarted
at all.** `run.cmd` started it, so `restart.cmd tomoe` looked like it would
cover it; but the daemon is single-instance by a lock file beside the mirror,
so the start line found the old one alive and exited, and a daemon started in
August went on running August's code through every restart of everything
around it. It now has a task of its own (`SCAIL_mal`, `mal_daemon.cmd`), and
`run.cmd` loses its start line. Three things that path needs and the others do
not. Its launcher **detaches the daemon under `pythonw` and then exits**, so
there is no console on his desktop to be closed by accident and no `pause` for
the task to sit at -- and therefore no redirect either, because cmd binds a
redirect on `start` to `start` rather than to the process it detaches, which
sent eight days of the daemon's lines to a handle that goes nowhere; the daemon
writes its own log. Its match is on the command line's `mal_history.py daemon`,
with the quote before `daemon` optional so it is found whether it was launched
with a full path or a relative one. And **it drives a headless Chrome through
chromedriver, which a force-kill leaves standing**: `Stop-Process -Force` runs
no exit path at all, so the driver and its nine Chrome processes go on holding
the profile the next one needs -- measured on the live machine, not supposed: a
chromedriver with nine Chrome processes under it, parented to the daemon. The
next daemon start does reap them
itself -- it finds the lock naming a pid that is gone and calls
`sensors/chrome_reaper.py` -- but only if that start happens, so the restarter
reaps between the stop and the start as well (`mal_history.py reap`, which also
says what the lock file claims). A stop that is never followed by a start
should leave nothing of his browser behind.

**The daemon's own restart-on-crash is a second, independent scheduled
task, `SCAIL_mal_watchdog`.** Everything above only covers a daemon a HUMAN
restarts -- `SCAIL_mal`'s own trigger is still `/sc once`, a one-shot, so
nothing brings a dead daemon back by itself unless someone runs
`restart.cmd`/`startall.cmd` by hand. `mal_watchdog.cmd`
(`tools/mal_watchdog.py`, registered by `tools/mal_watchdog_setup.ps1`, run
once or again if the task is ever lost) runs every 5 minutes, at logon, and
at startup, hidden (no console flashes on his desktop), and does exactly one
check per run, then exits: match the same command line this script matches
(`mal_history\.py"?\s+daemon`, `tools/restart.ps1:110`'s own pattern), and
if nothing matches, `schtasks /run /tn SCAIL_mal` -- literally what
`restart.cmd mal` does to start it. The daemon's own lock file
(`tools/mal_history.py:805-828`) is what makes a race between the two safe:
whichever `schtasks /run` actually spawns a process first wins, and the
other's `daemon` command finds a live lock and exits at once ("already
running (pid ...); exiting."), so a `restart.cmd` stop followed by a
watchdog cycle can never produce two daemons. If a process IS matched but
`meta.daemon_last_ts` (read read-only, the same way `sensors/mal_monitor.py`
reads it) is more than 30 minutes old, the daemon is hung rather than dead:
the watchdog kills that exact pid (never a guess, never anything else on
the machine) and relaunches the same way -- the next daemon start's own
stale-lock handling and orphan-Chrome reap cover the rest, nothing new was
needed there. It never touches Momoka, any other character, or
`tools/smoke.py`, on purpose: a broken build for a character, or a Momoka
compose issue, must never be the reason his MyAnimeList mirror falls
behind. Measured live on 2026-09-22: killed at 12:15:44, the watchdog's
next scheduled check (12:16:50) found it down and relaunched it, new pid
confirmed up at 12:17:02 -- about 80 seconds of downtime, and
`meta.daemon_last_ts` was already advancing again within 20 seconds of the
new pid starting. Its own log: `logs/mal_watchdog.log`, dated 24h lines,
one per check.

**The detail tables (`anime_detail`, `anime_cast`, `anime_kb`, `person`)
were empty in this checkout until 2026-09-22** -- `anime`/`episodes`
carried over from the fork, but nobody had run the two manual commands that
fill the rest of it. Filled once by hand (`python tools/mal_history.py
enrich`, twice -- the first pass timed out on 15 titles, the second caught
them; then `... cast`, twice the same way, one `URLError` caught on the
retry) run LIVE against the running daemon, not stopped first: WAL mode
(`tools/mal_history.py:61`) plus short, idempotent, per-title commits on
both sides made that safe, confirmed by watching `logs/mal_daemon.log` for
the whole run and finding no `database is locked` anywhere, and
`meta.daemon_last_ts` kept advancing throughout. Result: `anime_detail`
704/704, `anime_cast` 11,913 rows over 486 titles, `anime_kb` 487 (one
title has a cast page with nobody listed, so it is stamped fetched but adds
no `anime_cast` rows), `person` 0 -- that last one is correct as it stands
and not a gap in the refill: `person`/`person_role` are filled by a
different, per-seiyuu fetch inside `sim/anime_kb.py` that runs on a MISS
while a character is actually asking about a voice actor (`fetch_on_miss`,
`config_momoka.json`'s `role_check` block), not by the bulk `cast` command,
so it only fills once Momoka is running and the topic comes up. `enrich`'s
own client id lookup (`_client_id`, `tools/mal_history.py:1070`) now falls
back to `config_momoka.json`'s `sensors.mal_client_id` when root
`config.json`'s is empty, which it is by default -- neither config file is
written by this, only read, in that order. The daemon now also does a
small throttled slice of `enrich` itself every loop (`_enrich_due`, default
at most every 30 minutes, 5 titles a pass, `--detail-enrich-minutes` /
`--detail-enrich-batch` to change it, 0 minutes disables it), so a title
newly added to the list gets its detail row within a day or two without
anyone running `enrich` by hand again -- verified directly by deleting one
title's `anime_detail` row on the live db and calling `_enrich_due`, which
put it straight back. `cast` stays a manual command, not added to the
loop: its cast/seiyuu scrape is a public HTML page per title at ~1 req/s,
much slower than the API call `enrich` makes, and nothing on the daemon's
own path (the list sync, the history poll, watch-time math) reads
`anime_cast` the way it reads `anime_detail`, so there is no cost to
leaving it manual.

**`startall.cmd` brings everything up without stopping anything**, which is
what a machine that has just been rebooted, or a single process that has died,
needs. It is the same script in a third mode (`tools/restart.ps1 -StartOnly`,
beside `-StopOnly`): the same table, the same order, the same build check
first, and then, per target, the pid of what is already running or a start of
what is not. It has no stop phase at all, so it does not stop the collector
with the hub and does not reap the browser the mirror daemon leaves behind --
`mal_history.py reap` kills every browser on that profile whether or not a
daemon owns it, and a daemon that is down reaps for itself on the way in, from
the lock file naming a pid that is gone. A target matching more than one
process is reported and left alone, the same refusal a stop makes and for the
same reason. The one thing it can leave wrong it says out loud: a hub that was
down and comes up under characters that were already running leaves them
registered with a hub that no longer exists, they will not register again by
themselves, and `restart.cmd all` is the fix. Killing one of them to fix her is
the thing a start is not allowed to do.

**`stopall.cmd` puts the whole of it down on purpose and writes down that it
happened**, and the record is the reason it exists. A character who is stopped
and started again has a stretch of hours during which nobody wrote her -- no
schedule, no scenes, no messages, no compile -- and when she comes back the day
machinery has to account for that stretch somehow. With nothing on her record
to say what happened it fills the stretch in from placeholders, and she carries
a day that reads as lived because nothing said otherwise. A stop that leaves no
record is what this replaces. So the stop writes into every character's save
the moment it happened, one plain sentence of reason, and whose decision it was
(the `stopped` row, with the last fifty on a list beside it in `stops`); her
next boot reads that, turns the span between the stop and her return into a
single temporal-gap event, and clears it. Everything means everything -- the
hub, the mirror daemon, the collector and every character in the register --
because a character left running under a hub that has been stopped cannot be
reached from his phone at all, and there is no `restart.cmd`-style single
target here. **The two kinds of stop are told apart on her record**: without
`--no-credit` the stop is his and she is told what he said about it; with it
the stop is the machine's own -- the bot with no money left to answer with,
shutting itself down rather than failing every call -- which is a different
thing to come back to, and is why the bot can launch this itself.

Three things it does differently from a restart, each for a reason. **It runs
no build check.** Smoke protects a start, by refusing when a fix on disk will
not import; nothing is starting here, it costs about a minute of a stop
somebody is standing over, and code that fails to import is a REASON to shut
down rather than a reason to leave the machine up. The check comes back at the
next `startall.cmd`. **A target that refuses does not abandon the rest.** A
restart stops early on a target matching two processes, because half a machine
on new code beside half a machine on old code is worse than a machine nobody
touched; a shutdown was asked for everything being down, so it counts the
refusal, carries on, and ends by naming what is still up and exiting non-zero.
**And the marker is written by a tool of its own after the processes are gone**
(`tools/shutdown_mark.py`, which also takes `--dry-run`), because the save's
own writer is the bot and two writers on one open save is the fault the lock
file exists for. It refuses twice, and both refusals are the tool rather than
caution: it will not write behind a running process, tested by the holder named
in the lock file beside the save, since a handle opens for a process that has
already exited; and it will not overwrite a marker that is already there,
because a marker on a save is a stop nobody has resumed from and ITS timestamp
is the honest beginning of the stretch nobody wrote her. Beside the
per-character record there is the machine's own, one line per stop appended to
`logs/shutdowns.log`: the local time, the reason, every process stopped with
its pid, anything still up, and who was marked. That is the only place a stop
of the hub or the mirror daemon is written down at all.

**A launcher is replaced from a staged copy, in the one window where that is
safe.** cmd reads a batch file by byte offset while it runs, so a launcher
cannot be edited under its own console -- an edited `talkapp.cmd` once had the
old hub console run the tail of the new file and start a second hub on the
port. The window where an edit is safe is between the stop and the start, and
that is where the restarter does it: a change to a launcher is written beside
it as `<launcher>.next`, and after the stops it checks that nothing matches
that target and no console is reading the file, keeps a copy of the old one
under `data/retired/<timestamp>_launcher/`, and moves the staged file into
place. Consuming the staged file is what makes a second run do nothing.

**A missing scheduled task used to look like nothing happening.**
`schtasks /run` on a name that does not exist prints an error into a pipe
nobody reads, and the process simply never comes up. The start now refuses
before it asks, names the task, and prints the one `schtasks /create` line
that creates it (which needs no elevation).

Two things it handles that cost an evening to find. **Every launcher but the
daemon's ends in
`pause`**, so ending the scheduled task kills the interpreter and leaves the
console sitting at "press any key" -- the task still counts as RUNNING and the
next `schtasks /run` is swallowed without a word. It kills the console as well,
and ends the task again before starting it. And **it finds each process by its
exact command line, never by image name**, and a target matching
more than one process stops the script rather than letting it guess. A filter
over running processes once killed a program from another program. Each
character has an entry point of her own that registers her words and hands
the rest to the shared runtime -- `tomoe/run.py` and `resident/run.py` --
and the pattern in her register row looks for that entry point by name. The
first character is matched positively on hers; she used to be matched as
"`scail.py` NOT followed by the second one's config", which would have read a
third character launched with a config of her own as the first character and
killed her. The cost of the positive match is that starting the first
character by hand as `python scail.py` is no longer found, which is the safe
direction: the failure is "does not find her" rather than "kills the wrong
process". The second character's row still matches the older
`scail.py` + her config form beside her own entry point. And **it
kills the launcher console before the interpreter it launched**: cmd reads a
batch file by byte offset while it runs, so a console whose child has just
died carries on from the next line of whatever the file says now -- the old
hub console ran the tail of an edited `talkapp.cmd` and started a second hub
on the port. Never edit a launcher under a running process. The collector
(`machine/collector.py`, started by `talkapp.cmd`) is stopped with the hub.

The bug that made its own first run useless is worth keeping in mind for any
script like it: a PowerShell function returning a one-element array has it
unrolled to a bare object, so a count of 1 reads as empty, every process read
as not running, nothing was stopped, and the start then launched duplicates
that the port and the per-database lock had to refuse. `return ,@(...)` is the
fix and the comma is load-bearing.

**Asking a character to answer an old message again**
(`tools/regen_reply.py`; the procedure, and how the answer is put into the
chat with `tools/replace_reply.py`, is `docs/regen-reply.md`) is how a change
to what she knows is measured,
because nothing that is added to her reaches a reply she has already sent. It
defaults to the second character and takes `--config` and `--db` for any
other. (An earlier tool of the same purpose was discarded and is under
`data/retired/`.)

    python tools/regen_reply.py --message-id 138                          # one of his messages, by id
    python tools/regen_reply.py --message-id 138 --anime Mitsudomoe --ep 9  # re-read that episode first

For each message it takes a copy of the save **with sqlite's own backup, not a
file copy** -- an open save copied with the bot up came back with 0 rows in
every table, which is the one trap in this whole path -- deletes every message
after the target from the COPY so she cannot see what she went on to say,
builds the App on it with `--console --no-sensors` so it registers with no hub,
sets the day up the way the loop does (`ensure_day`, free for a character with
no world), and then makes the two calls the live reply path makes: a forced
director tick, and `persona.generate`. It refuses to run if the App it built
would reach a channel. Her live save is opened read-only, nothing is sent, and
it costs roughly four or five model calls per message.

It prints what she said then beside what she says now, and under each the
memories that were in front of her, the records the retrieval offered, and the
attention gate's line -- which is the one that says whether a retrieved record
reached her prompt at all rather than being dropped in competition. `lore 0`
there usually means the record was spent: one already offered inside
`lore.suppress_days` is not offered again, and `--fresh` forgets that on the
copy so the effect can be seen.

**The clock is not rewound.** She answers at the hour the tool is run, so a
message from the evening replayed near midnight can be answered as though he
has turned up late. That is her reading the time, not the change failing.

**That tool answers offline and writes nothing**, which is right for measuring
a change and wrong for seeing one: the conversation in the app does not move.
`tools/replace_reply.py` moves it: given one of her sent messages by id and the
new text, it replaces the message in her store, on his phone through the hub,
and in the voice note, so the two records agree and the chat shows one message
where it was. The procedure is `docs/regen-reply.md`. (An earlier tool that
took her last reply back and had the bot answer again was retired; it is under
`data/retired/`.)

    python tools/isolation.py             # what a second character shares with the first
    python tools/character_leaks.py       # names in a run that are not in that character's record
                                          #   (--out FILE|DIR, --text: the same check over any output about her)
    python tools/character_names.py       # a name or a place of hers in what the characters share:
                                          #   the library, the hub, the sensors, the channels, the car,
                                          #   the tools, both programs and every prompt directory, in
                                          #   .py .html .js .txt .md .json; --all for every finding,
                                          #   --write-known to rewrite tools/known_literals.json
    python tools/prompt_leaks.py          # every role prompt of hers, rendered, read for another character
    python tools/defaults_person_test.py  # no default in config.py:DEFAULTS is one person's file
    python tools/blank_paths.py           # every character still builds with every person's path blank,
                                          #   and refuses to start with one of them emptied under a
                                          #   subsystem that is on
    python tools/registry.py              # the register of characters that run as a process
    python tools/agent_rehearsal.py <key> # one day of a character who runs herself, on the
                                          #   clock, beside the character who keeps her world:
                                          #   both built on copies, the hub in the process, the
                                          #   model, the network and the browser refused; asserts
                                          #   the seam's runtime contract (docs/agent-character.md).
                                          #   In smoke for every reader of somebody else's world,
                                          #   and in new_character.py verify
    python tools/agent_audit.py <key>     # the read-only audit of a character who is already
                                          #   running: the process, the hub, every ask matched to
                                          #   what she did with it, the beats she was planned,
                                          #   her record of a room against the world file, what a
                                          #   switched-off section has written, her gauges, what
                                          #   is left about him, a carry that has not moved, a log
                                          #   line that is spinning, and the cost by role
    python tools/voice_verify.py          # her lines against the tape's own measured markers
    python tools/<x>_test.py              # situation / family / stress / attachment / character / gaps /
                                          #   compare / expect / wonder / discharge / scenery / reaction / source / recap /
                                          #   retrievals / eroge / swipes / flush / poke / initiative / inflight
    python tools/reactions.py ...         # reaction images (recipe in its docstring)
    python tools/seed_memories.py --config C --report   # what the seed of an extracted
                                          #   character's own past is made of; --db a COPY to rehearse it
    python tools/regen_reply.py --message-id N   # answer one of his messages again, with what she knows now
    python yukarin/tools/triggers.py      # the phrases that let one of her records be found
    python yukarin/tools/fix_trigger_substrings.py   # lengthen a phrase that fires inside a longer word
    python tools/local_events.py, zeitgeist.py, mal_history.py, x_analyze.py, x_delete.py, forge.py, devoice.py, telemetry_sim.py

Launch the live bots and the mirror daemon only through the scheduled
tasks, and go through `restart.cmd` rather than doing it by hand: the task
names are `SCAIL_mal` and one per character in the register, the daemon starts
before any bot, a bot started as a child of a tool's shell dies
silently minutes later, and no task has an at-logon trigger. By hand it is `schtasks /end /tn <task>`,
then `Stop-Process` the console the launcher left at "press any key", then
`schtasks /run /tn <task>`. **Find the process by its exact command line, the
pattern in its register row, and never by image name**: a filter over running
processes once killed a program from another program and left the bot
untouched.

**Secrets**: `config.json` holds the DeepSeek key, the ODPT tokens and the
hub token (127.0.0.1 only); `secerts/` holds the Vertex service account and
the OpenRouter key; the MiniMax key is in the shared MiniMax config named by
`tts.minimax_config_path`; `HF_TOKEN` is in his user environment. None of it
goes anywhere, and none of it is printed: a network failure is logged by
exception TYPE, because a requests exception quotes the URL it failed on and
those URLs carry `key=` (`netwatch.redact`).

**Commands** (`/help`, `/help <command>`; from Telegram or the app's ops
bar; never into her chat):

| command | what |
|---|---|
| `/day [date]` | the compiled narrative of a day, or the scenes so far today |
| `/scene`, `/tick`, `/idle` | the director's current scene; force a tick; run one ordinary loop pass now -- the tick and everything that reads the scene it wrote |
| `/schedule [regen]`, `/replan` | today's plan, block by block; regen redraws the wake and rebuilds it |
| `/where` | her body: node, journey, fatigue, typing, the last journeys |
| `/family` | the parents' day, where they are now, whether a pickup is on |
| `/cast`, `/beats [plan]`, `/chat`, `/lives` | the cast's day, the social script, her exchanges, their lives |
| `/peers [tick\|flush]` | another running character: who she may write to, what she has sent today, the conversation in flight; `tick` runs one pass now, `flush` closes what is open the way the compile does |
| `/health`, `/money`, `/diet` | her body's day; her allowance; what she is into |
| `/japan [now]`, `/trains`, `/hazards`, `/time` | the world |
| `/state`, `/gauges`, `/set <what> <0-100>`, `/sweep [gauge\|him\|all]`, `/affect` | the gauges and meters; fix one by hand; is a value read |
| `/impulse`, `/intents`, `/selfstart [why]` | would she text him now; the urges behind her openers; make her write first NOW past the gate that would have held her, with an optional reason she is handed |
| `/reflect [now [name]]`, `/spiral [now\|settle]`, `/compare [now]` | her private mind |
| `/beliefs [revise]`, `/self [revise]`, `/goals`, `/commit` | what she has decided, wants, promised |
| `/attach`, `/withhold`, `/rupture [settle]`, `/approach [now]`, `/ick` | the stances toward him |
| `/sentiment`, `/foresee [now]`, `/expect [now]`, `/wonder [now]`, `/care [days]`, `/rhythm`, `/receipt` | what people are to her; her model of him |
| `/discharge`, `/reaction [now\|BUCKET\|off\|backfill [H]]`, `/scenery [now\|lore\|harvest\|gaps\|rejudge]` | events at a gauge's end; her face; borrowed eyes and what the base is short of |
| `/memory`, `/remember`, `/recalls`, `/claims`, `/graph`, `/diary [write]`, `/morning`, `/derive [apply]`, `/world`, `/week` | memory and the record |
| `/look`, `/digest [n]`, `/snoop`, `/read <note>`, `/notes`, `/lookups`, `/anime [from] [to]`, `/known [drop <key> \| unpart <key> <label>]`, `/watching [forget <aid:ep> \| rewind <minutes>]` | her phone about him; what she knows by name; what he is watching, what was counted, and putting the player cursor back |
| `/send <text>`, `/reply [again]` | a message typed as her, through her own delivery and store; answer his newest unread message NOW instead of when her plan says, `again` putting his newest message back to unread first |
| `/x [taste\|sheet\|drift\|judge\|japan\|likes\|follows\|status\|actions\|post]` | the X account |
| `/context [full\|find <t>\|msg\|<section>\|add\|set\|del]`, `/compile [date]` | her prompt, corrected; redo a day |
| `/showrun`, `/arcs`, `/castarcs [now\|evolve]`, `/threads`, `/places` | arcs, threads, places |
| `/attention [tally [days]]`, `/coherence [date\|now\|days]`, `/absurd [full]` | what she was handed and what she never hears; the day read as one story, flag only; the audit |
| `/say <japanese>`, `/vision`, `/ops`, `/headless [on\|off]`, `/voice`, `/voicecheck` | her spoken line, eyes, the operator payload, the browsers' window, the voice line and its queue, lines flagged out of voice |
| `/swipe [list [id] \| <id> [model]]`, `/sit <id> <n>`, `/voicemodel [<name>\|auto]` | draw one of her replies again from the prompt frozen when she sent it, with no argument listing which replies can be drawn at all; make the conversation go on from the answer he picked (the one write of the three); the model her voice roles are written on, which the chat header is the control for |
| `/provider [<name>\|auto]`, `/model [<name>]`, `/speed`, `/missed`, `/catchup`, `/gap` | who answers and pinning one; what every role is on, and a name pinning them all for this run; a tiny call on each; the calls nothing answered; covering a hole, or writing it down as a hole |
| `/lang [ja\|en\|auto]` | the language everything addressed to this character is written in: with no argument, the arm in force, where the choice came from, and the material roles it carries; `ja` her own language and `en` English from the next prompt on; `auto` forgets the choice and lets her config decide. Saved on her own save, so it survives a restart. It refuses a character whose `character.instruction_language` is english, because the third arm would render the same bytes as the second for her |

**Forcing what would otherwise wait on her clock.** `/idle` runs one ordinary
loop pass now, `/reply [again]` answers his newest message now instead of when
her plan says, and `/selfstart [why]` makes her write first past the gate that
would have held her. None of them is a shortcut: `/idle` and the loop call one
method (`App.ordinary_tick`), `/reply` sets the plan due and lets
`App.maybe_reply` run, `/selfstart` goes through `App.maybe_impulse` by the
door a discharge uses -- and the last two really send. Each refuses and says
why (no plan yet, her phone away, a send in flight, nothing of his unread)
rather than doing half of it. From a terminal against the RUNNING bot:
`python tools/poke.py <tomoe|yukari> /idle --wait 30`, which puts the command
on the hub's ops queue exactly as the app's ops bar does and then follows that
character's run directory `session.log` and the hub's ops log while it lands.

---

**Checking it is sane, not merely well formed.** `tools/smoke.py` proves the
machine is structurally sound -- no dead config keys, no unbound names, every
prompt file present -- and cannot tell you that a gate sits below a value her
state never reaches, that a field two callers read is empty for everybody, that
the ringleader of her friendship group sends five messages a day, or that she
spent seven hours unable to answer the girl across the table. Every one of
those faults was structurally valid and obvious the moment somebody read the
number.

`tools/absurd.py` (and `/absurd`, `/absurd full`) asks the other question: is
anything here impossible for a fifteen-year-old? Each check states what would
be ABSURD in plain words about HER, measures it, and reports ok / odd / ABSURD,
grouped by the kind of absurdity because the kinds recur -- DEAD GATE, FROZEN,
NEVER FIRED, UNREACHED, VOLUME, SILENCE, ONE VOICE, PARROT, GHOST PLACE,
MONEY, DROPPED, REPEAT BEAT, UNSAVED, STRANGERS, REPEATS, GROUP, KEYS, LEDGER,
PROVENANCE, REGISTER, UNHEARD and SEAMS. Read-only, no model, safe against the
running bot. A check must not cry wolf or it gets ignored, so the unread one reads her
phone access (unanswered while asleep is the design working), the never-fired
one measures from the date the MECHANISM was written rather than the age of the
save, and the silence one measures her WAKING day from the night she actually
had -- it first cried ABSURD over 00:23-08:12, which is her asleep.

**REPEATS and GROUP exist because everything they measure was found by hand.**
Aya sending the same three-bubble block four times in twenty minutes, the
afterthought paraphrasing the burst it followed, her own spoken line repeated
three minutes later with the punctuation moved -- each was fixed where it
happened (`drop_repeats`, `near_duplicate` against her last six,
`no_repeat_own_turns`, `tts.no_repeat_recent`) and nothing was watching for the
next one. A model with no sight of what it just said will always drift back
there, so REPEATS compares every speaker against themselves, per speaker per
day, across the cast turns, her messages and her spoken lines -- and over the
last two days only, because a check that cannot go green once a fault is fixed
is a check nobody reads. GROUP asks whether their chat is a group of teenagers
or a committee: `one_sided` catches a conversation nobody answered and VOLUME
catches one that is too quiet, and neither catches a day of
fifty-one messages between four girls of which every one is about the meeting
time. It reports the day's turn-count shape and the share of messages carrying
a time or a plan; 15, 1, 11, 51, 1, 1, 1 at 68% arrangements is the reading to
recognise.

**UNHEARD and SEAMS read what the gate and the compile keep.** Forty statuses
compete for sixteen lines, so UNHEARD reads the gate's own tally (kv
`attention_tally`) over `attention.unheard_days` and names a source handed to
her `attention.unheard_min_offers` times and admitted in none -- a mechanism
alive in the store and absent from her. SEAMS reads the day-as-a-story
flags (kv `coherence_flags`, §12.10) over `coherence.absurd_days`: ODD on a
contradiction, an invented thing or a repeat a reader would notice, ABSURD on
five. Both are flag-only readers of a record; neither runs a model.

KEYS watches the second language key (`self_memories.alt`): how many memories
carry one, any gloss that came back in the language it started in, and any that
came back in Chinese. All three fail silently -- nothing breaks, she simply
stops being able to remember a thing from one side -- and the first version of
the check cried wolf by asking whether a line CONTAINED any CJK, which calls a
memory of English prose quoting 「おやすみ」 Japanese. It counts now, through
`cast.is_japanese`, which has done it properly since a `ja` field turned out to
be full of English.

The later six catch failures nothing else can see. ONE VOICE compares the four
agents' turn statistics and flags them converging, which is the multi-agent
cast quietly collapsing back into one writer. PARROT takes eight-character
n-grams of her own lines across days and flags one that has hardened into a
tic. GHOST PLACE checks every scene's location against `places.json`, because a
place her map does not have is how "at Aya's" left her body where it was for
weeks. MONEY catches a balance below zero and the same purchase logged twice.
DROPPED names anybody on the roster, not marked dormant, whose life has not
touched hers in a week. REPEAT BEAT compares planned beats for the same person
across days, because her friends living the same day over is the most boring
way a simulated life dies. UNSAVED is the one that pays for itself: it holds a table of every role and
where its answer lands (`SINKS`), and flags two things -- a role that ran and
is in nobody's table, and a role whose sink is empty. It exists because nobody
had ever asked where a beat's words went, and the answer was kv `cast_beats`,
which tomorrow's plan overwrites. A recovery tool, since retired, put back what could
be put back: every `cast_beat` call and its answer is in a run's
`llm_calls.jsonl`, so the words survive even where the save has forgotten them
-- gated on a delivery event in `events`, because the logs hold every beat that
was ever WRITTEN, and a replan's discarded morning and tonight's unlived beats
are not things that happened.

Two of the six found something on their first run,
and two of them found bugs in themselves -- the roster resolution and a tuple
row -- which is the reason a check is written against the real save.

`tools/context_audit.py` reads her world from each cast member's chair. It
builds the REAL prompts against a copy of the save with the model stubbed out
and prints them, so a person can read what Rena actually reads, and runs the
checks a careful reader would otherwise do by eye: every speaker label resolves
through the roster, the speaker is not among the people she is told are also
reading, no clock is unlabelled, no English prose sits inside the Japanese
record. Its first run found a live `TypeError` in `calls_line` that smoke could
not see (smoke constructs the app; it does not build a friend's turn), and four
naming faults in the prompts themselves.

`tools/docs_check.py` asks whether the docs still describe the code that is
there, and `tools/smoke.py` runs it on every check. Every backticked token in
PROJECT.md, CONFIG.md, HANDOVER.md, CLAUDE.md, the `docs/` specs and the
`tools/docs_src/` chapters that has the shape of an identifier is resolved:
config keys against `config.py` DEFAULTS, functions and attributes against the
source, files against the filesystem, kv keys against a `store.set` or
`store.get`. A doc that names a renamed key or a deleted function is worse than
no doc, because it is believed. First run: 1,197 references, of which nine were
stale -- a phone key that had been renamed to `phone.digest_min_minutes`, a
trains key that is `trains.her_lines`, a state key whose section is actually
top-level `contagion`, three methods attributed to a class called Cast when it
is `CastEngine`, a guard deleted the day before, and CONFIG.md's own header
pointing at a generator path that no longer exists. It cannot see a stale
CLAIM, only a stale NAME; the prose still wants reading, and reading it turned
up more than the tool did.

Two projections sit beside it, both read-only and modelless:
`tools/night_review.py` costs a night of the late group chat (windows, message
volume, gaps, model calls per agent) and `tools/chat_project.py` composes the
dials into a day, so a volume target can be aimed at.

## 15. Status

The running state (pids, log dir, what to watch, open items) is the head
of `HANDOVER.md`; the dated story is `HISTORY.md`.

**Two characters run live**, each its own process against its own save,
both registered with the one hub. The first is everything below. The second
(§19) has been up for hours rather than days: she boots clean, watches his
machine, reads his notes, answers in Japanese, has a voice he can tap on any
line, can be reminded of things out of her own record, sees the page about a
work the minute he opens it and knows whether she was in it, and can look a
thing up before she answers. What has NOT been
seen for her is any of the long arcs -- her ledger, her attachment, her
picture of him -- because they are integrals and she is hours old. What
stands for the first character:

- **Solid** (built, dry-run, and seen working live over days): the loop,
  the schedule and director, the state and its readers, delivery on
  TALKAPP with real 既読 and typing, the compile with the forgetting
  curve, the app about him and the snoop, X as her own account (the
  drift), the cast day and exchanges in Japanese, the social graph,
  sentiments, ruptures, spirals, stress, goals, commitments, attachment,
  withholding, approach, rhythm, foresight, expectations, the situated
  body with journeys, family and the car, health and sleep, money,
  hazards and trains, zeitgeist and local events, voice.
- **Seen once, not yet through a full cycle**: a discharge; a comparison;
  a scenery photo sent; a reaction from a real change of face; an
  attachment episode; a journey; a `cast_facts` row (the first, 08-27).
- **Built, never seen** (the watch list in HANDOVER): a KB row cached
  live; a grounded episode reaching her `experience` call; a withholding
  from an empty answer (`hold_from_silence`); a `LOOKUP:` out of the
  download snoop; an expectation of kind `around` (a `do` has since come
  due, been missed and been raised with him, and a learned `habit` has been
  checked and kept; the `risk` rows on the save are the retired mirror,
  which foresight now scores itself); a question asked and judged;
  the body-settled correction; a family day; `[state] habituated`; a group
  burst with the nicknames; a broken promise reaching her through the
  person owed; the friends' edges with each other moving (no writer).
- **Open on the second character, and each is his call rather than a bug**
  (all of them in the handover): her ledger cannot climb out of the premise's
  -70 by anything she does, only by decay, which takes about seven weeks;
  her attachment reads zero and will for weeks, because cost of loss is an
  integral; her picture of him needs eight digests and she has four; she
  can read the first character's name off his window titles, which is either
  the best material in the project or a leak; and her `closeness` meter of
  him is read by nothing -- the sweep says DEAD, because her affection is
  derived from her primitives rather than from his meters, so whether that
  meter should feed anything of hers or come off her sheet is undecided.
- **Parked, by his call**: the care governor (`care.scale_checking`);
  `learn` for the reactions until a few hundred corrections exist; the
  "she remembers her old friends' names" continuity incident (residue +
  noticer, HISTORY §15.3); Telegram stickers; his rating as a pick
  weight; scenery tap-to-enlarge and Telegram `send_photo`; the turns-in-2h
  measure for photos; foresight calibration in
  the prompt, the mood trajectory, the `[0,0]` habit window; the wonder
  friend-question; discharge floors; at-logon triggers for the tasks.

---

### `register.py`: does everybody still sound like themselves

`voicecheck` measures dialect and `ONE VOICE` only sees the extreme.
Nothing measured whether a person is different in the group from
one-to-one, or whether the cast has flattened into one voice over a
fortnight. `fingerprint` counts message length and eleven written-Japanese
markers (ね よ じゃん さ かな w/笑 ！ ？ です/ます emoji 〜) per speaker and per
room; `room_contrast` is the distance between a speaker's group and
one-to-one registers; `distinctness` is their distance from the cast mean;
`drift` compares this week with last and marks **`flattening` only when
that distance FELL** -- a voice whose markers all rose is its sheet
arriving, and the first version of this check cried wolf on exactly that.
`tools/voicelint.py --register` prints it; `/absurd REGISTER` reads it.

## 16. Conventions

Fix what is inside the ask and say what changed. Verify with the store's
own reader before quoting a number. Demonstrate by running the thing.
Comments explain why, never patch notes. Delete dead code. No hardcoded
operational values: everything in `config.py:DEFAULTS`, in both files.
One log directory per run. Retire, never delete. The running bot never
edits its own persona. Write plain technical English: the fact first,
then the reason.

**Dated notes go to `HISTORY.md`**, under the section number they belong
to; this file holds only what is true now. `HANDOVER.md` is the header:
running state, what to watch, open items, nothing older. **A large module
gets a spec** (`docs/<module>.md`: purpose, mechanism, config, store,
readers and writers, invariants and edge cases, ops and tests, history
pointers); the PROJECT entry stays under ~20 lines and points at it.
The threshold: more than one prompt role, or more than ~500 lines, or
more than one file. Keep the spec current with the code the way this
file is; the story of how it got there stays in HISTORY.

**Gauges** (the rules that came from `mood` running 50-84 for 112 states
while a `mood < 30` branch never executed):
1. every gauge declares `kind` / `valence` / `arousal`; the App refuses
   to start otherwise;
2. a derived gauge is refused at the write site, not omitted from the
   prompt;
3. the emotion set spans the valence x arousal grid -- an empty cell is a
   feeling she cannot have;
4. one owner per gauge;
5. a threshold nobody can reach is dead code: query `state_log` first;
6. measure deviation from rest, signed; a term measured only above its
   baseline is zero almost always;
7. a feeling must have a reader (`/sweep` names DEAD ones);
8. a release settles at the baseline, never through it; a mechanical
   bump loses value near its cap; `_nudge` is the signed move.

**A file another process reads is replaced, never rewritten in place**
(`atomic.py`: `replace`, `write_json`, `read_json`). Four processes run over
this tree at once and several files cross between them -- the cast roster, the
hub's message log, the machine's telemetry snapshot, the mirror of his list,
the weather cache, the episode archive's index, a character's bundle under
`characters/<key>/`. `open(path, "w")` truncates first and fills after, so
every reader in that window gets a prefix and a parse error. The replacement
goes to a temp file beside the destination, is fsynced and renamed over it.
There is no writing in place as a fallback: measured with a reader opening the
file 400,000 times a second, the rename hit a sharing violation about once in
forty writes and a fallback that then wrote in place handed two readers an
empty file. When the rename will not go the old file is left exactly as it
was, complete and one revision behind, and the new bytes stay beside it. On
Windows a read can still fail while the name is moving, which is why the
reader tries again. `tools/atomic_test.py`, in smoke.

**Records.** Nothing is recorded before the action it claims happened;
`reconcile.py` corrects prose that claims a send or a spend the record
lacks. Every timestamp written is machine local time; her clock belongs
in the text only when it is the subject, labelled. A JSON role's answer
that does not parse is asked again; a caller handles `None` and never
stores the raw answer.

**Config.** A key read by code but absent from DEFAULTS is a crash. When
patching `config.py` by string, anchor on a whole line with its
indentation. Every role's `max_tokens` stays at the API maximum. Names
used as keys (`relationships`, `cast.json`, avatars, `who` prefixes) are
the roster names; a rename touches the bible, `cast.json`, the store, the
avatars, and the tests.

**Tests.** `tools/smoke.py` before every restart; every `tools/*_test.py`
builds the App on a copy of the save and must not write to the live one
(the reactions test copies into the live `data/talkapp/reactions/`
folder; harmless, untidy). A non-idempotent patch script re-run after a
partial failure has doubled its inserts; make patch scripts assert on
their anchors, and a one-off fix of the save (`tools/fix_*.py`) backs the
db up to `data/retired/<ts>/` first and does nothing on a second run.
Smoke also parses `config.py` with `ast` and fails on a key written twice
at any depth in DEFAULTS: two had been sitting there (`situation_block`,
`state.gauges.stress`), identical pastes, the second silently winning, and
`dupscan` cannot see them because it looks for repeated blocks of code.
