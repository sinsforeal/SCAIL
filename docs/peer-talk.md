# Two running characters talking to each other

His ask: *"when we have the ability to RUN asumin, i want her to be able to
talk to yukarin. have an agent ensure this is possible, and future additional
characters are modular."* The dated record of what was built and when is
`HISTORY.md` §19.

This is the design and the record of what was built from it. It answers two
separate questions that are easy to run together: **can two live processes hold
a conversation** (the mechanism), and **what is a character as a unit** (the
modularity), so that the fourth one is her own files and one row in a list
rather than an edit to the shared code.

Read `docs/talkapp.md` for the hub and the channel, `docs/cast-exchange.md` for
how the first character already talks to people who are not him, and
`PROJECT.md` §19 for what the second character is.

---

## 1. What is already true

- The hub is **generic over N characters**. Everything is keyed by a character
  id (`talkapp/server.py:_char`), the id is the character's own display name
  lowercased with spaces stripped (`channels/talkapp_bot.py`), the hub keeps no
  list of legal ids and creates one on first sight, and `/health` returns
  whatever has registered. Nothing in the hub names a character or assumes two.
- The runtime is generic over programs. `character.program` names a package and
  the runtime imports `<program>.app`; what a program does not build is `None`
  on the App. A resident-type character needs no new package.
- `tools/smoke.py` already builds **every** character it can find
  (`config.json` plus `config_*.json`).
- What a character IS is declared once, on her sheet, as five properties
  (`embodied`, `in_world`, `sees_him`, `has_account`, `with_him`), and the consequences
  follow from `Config.REQUIRES` and `Config.WORLD_KEYS`.

Three things are NOT true yet, and they are what this design is about.

- **The hub's message vocabulary has exactly two values and one of them is
  implicit.** A row in a character's log is `role: "her"` or `role: "him"`, and
  the bot's inbound feed is *defined* as the complement of her:
  `[... for m in c["log"] if m["role"] == "him" and m["id"] > after]`. There is
  no sender field anywhere in the row. A message from another character put
  into that log would reach her indistinguishable from him; a row with a third
  role would never be delivered at all.
- **The character-side inbound path is the relationship with him.**
  `App.poll_inbound` runs attachment, the psychological primitives, foresight,
  expectations, the questions she asked him, whether she was holding out, and
  the state of a rupture — all of it about *him*, and all of it wrong to run on
  a message from somebody else.
- **The operator's tooling is a hand-written table of exactly two bots.**
  `tools/restart.ps1` matches the first character as "`scail.py` NOT followed by
  `config_yukarin`", so a third character launched with her own config would be
  matched as the first one and killed by `restart.cmd tomoe`.

---

## 2. How two characters exchange messages

### 2.1 The relay: a mailbox of its own, not her chat

The hub is the relay, and a peer message gets **its own per-character mailbox**
rather than a row in her chat log. The reason is that the chat log is his chat:
a row appended to it is broadcast to every websocket client, pushed to his
phone as a notification titled with her name, read-receipted in both
directions, and offered the swipe and speak controls. None of that is true of a
message from another character, and `h_bot_updates` would hand it to her as
his.

Two routes and one key on the per-character state:

| | |
|---|---|
| `POST /bot/peer` | `{char: <sender id>, to: <recipient id>, text}` → appends `{id, from, name, text, ts}` to `chars[<to>]["peer_in"]`; returns `{ok, id, to, known}` |
| `GET /bot/peer?char=<me>&after=<id>` | `{messages: [{id, from, name, text, ts}]}` |

- `known` is false when nothing has ever registered under that id. The sender
  logs it and drops the message: nobody is there. It is not an error and it is
  not retried.
- The id comes from the hub's one global counter, so a peer message id can
  never collide with a chat row id and the recipient can hold a single
  high-water mark (kv `peer_last_id`, exactly like `talkapp_last_id`).
- The mailbox is **not** cleared on read, so a character who is down misses
  nothing; it is trimmed to `talkapp.peer_keep` rows like the chat log.
- The route takes `text` and nothing else. No attachment, no telemetry digest,
  no ops flag: the ops queue is a different queue with a different route and a
  peer cannot reach it.
- Authentication is unchanged — one hub token, and `char` is an assertion
  rather than a credential. That is already true of every route and it is
  acceptable on 127.0.0.1. It is worth writing down that with peer talk the
  `char` field becomes a claim about *who is speaking* and not only about
  *which thread*; if the hub ever leaves the loopback, per-character tokens are
  the thing to add.

### 2.2 Inbound on the character side: her own door, not his

`sim/peers.py` (shared, names nobody) polls the mailbox once per loop pass and
files what arrives as a turn in a peer conversation record. It does not touch
`App.poll_inbound` and none of the machinery about him runs. A peer message
reaches her mind through exactly two doors:

1. **her history**, as a room in the thread (2.3);
2. **the company a conversation is**, once, at the close (2.5).

**She reads it on her own clock and her own phone access.** The gate is the one
the cast exchange already uses at her turn: the director's scene carries
`phone_access`, and `none` means the message sits. For a character with no
world and no schedule blocks the gate is whether she is asleep, which her own
sight already decides and her presence line already reads. Unread peer messages
accumulate and ride in the thread as a run of world turns, the way his
unanswered messages do.

### 2.3 How it appears in her thread

`sim/thread.py` keeps her history as one chat completion over every room, and
nothing about the curve, the cards, the window or the byte-identical rebuild
changes. Two narrow additions:

- `Thread.build` reads its conversation records from **two** lists —
  `cast_chat` (the first character's cast exchanges) and `peer_chat` (peer
  conversations) — concatenated. A separate list, because the cast exchange
  rewrites `cast_chat` wholesale when it closes a conversation and a peer
  record living there could be dropped by a writer that does not own it.
- `Thread._room` gains one kind: `peer` → `messages with <name>`.

So a peer conversation renders exactly like every other room:

```
[Thu 04 Sep 21:14 · messages with あすみん · あすみん]  こんばんは、起きてる？
                                                        (her turn, bare)
[that was you, Thu 04 Sep 21:16, messages with あすみん]
```

Her own turns stay bare — the room and the clock are said by the world line
after them, because a label on her own line is a line the model copies.

A cast member's thread (`build(for_who=...)`) never sees it: `_sees` asks
`roster.witnessed`, which is false for any kind that is not the group, so a
peer conversation is hers and the operator's and nobody else's.

### 2.4 Which system prompt

`persona.system_for("friend")` — the **own people** variant — plus this call's
own tail: the peer contract (`prompts/peer_reply.txt`, a shared mechanism
prompt that names nobody) and her `character.style_ja_prompt`.

- Not the `him` arm, because `style.md` is how she writes to HIM; carrying it
  into another person's room puts his register there.
- Not a third arm. `system_for` has two and this is the friend one, so a
  section added to her interior lands in the peer room too. Two assemblies is
  how her friend turns carried none of her interior for eleven days, and
  `tools/smoke.py` fails if the two arms diverge by more than `style.md`.
- `persona.carried_for()` rides **after** the thread in the final user message,
  as it does in both existing rooms, so the system half stays a cached prefix
  shared with her replies to him.

The language of the room is the contact's: `peer_talk.contacts[].language`,
empty meaning "the way she writes to her own people", which is Japanese for
both characters that exist. It is config, never a hardcode, for the same reason
`character.writes_to_him` is.

### 2.5 What it does to her gauges

**Reads:** everything, through the persona core, the situation block and the
ledger — and nothing peer-specific.

**Writes: one, and it is not a new owner.** At the close,
`State.talk_relief(<the contact's name>, rounds)` — the same call the cast close
makes, which settles loneliness toward rest by what that person is to her; a
person with no meter row resolves to a middling closeness, which is the honest
answer for somebody who is not on her roster. No new gauge, so nothing to
declare `kind`/`valence`/`arousal` for and nothing for `/sweep` to call dead.

A sentiment row per contact (`sim/sentiment.py` keyed by the contact id, so
that a peer can become somebody she is fond of or wary of) is the obvious next
step and is deliberately **not** in this cut: a meter with one writer and no
reader is the fault the rule exists to stop.

### 2.6 Who speaks first

`sim/impulse.py` is about him — does she text HIM first — and is untouched.
Opening a peer conversation is its own decision in `sim/peers.py`, and it is
the usual division: code decides when, the model decides what.

She may open when all of these hold: peer talk is on and she has a contact; no
conversation with that contact is live; she is under the day cap; the clock is
inside `open_from_hm`..`open_to_hm`; her phone is not away; and
`min_gap_minutes` have passed since the last peer message in either direction.
Then a per-pass probability, `open_p`, sized so the opener lands somewhere
across the window rather than at its first minute.

### 2.7 Pacing, so two bots do not talk forever

Four bounds, all deterministic, all on her own side, so each character carries
her own restraint and the shorter of the two ends the conversation:

| bound | key | default | what it does |
|---|---|---|---|
| her turns in one conversation | `max_turns` | 6 | at the cap the conversation is closed "it trailed off"; further messages are still received and read |
| messages she sends to peers in a day | `max_per_day` | 12 | counted with `store.bump_today`, so a restart does not reset it |
| the floor under two sends of hers | `min_gap_seconds` | 90 | plus a reading-and-typing delay from the length of what she is answering, so nothing is instant |
| quiet hours and phone access | `open_from_hm` / `open_to_hm` | 09:00 / 24:00 | nothing is sent outside the window or while her phone is away |

Two caps of 6 turns each is a conversation of at most twelve messages; two day
caps of 12 sends bound a day at twenty-four. There is no shared counter and no
negotiation, which is the point: neither process has to trust the other to
stop.

### 2.8 The ledger and the compile

**The ledger is read and never written.** The peer turn writer receives
`ledger.text()` like every other writer of her words — where she is, with whom,
what the plan settled, what she is wearing — so she cannot tell a peer she is
somewhere the day's one truth says she is not.

At the close the conversation is written twice: one `peer_chat` record (the
turns, verbatim, with a gist) and one `events` row of kind `peer_chat` at
salience 2. The day's compile reads the second and, through `sim/talks.py`
reading both lists, renders the turns into the narrative and into what recall
can search. The compile itself needs no change.

---

## 3. Isolation

The standing rule is that one character's material must never appear in the
other's output except as something the other actually said to her. Peer talk is
the first mechanism that makes the exception real, so the boundary has to be
stated precisely.

### 3.1 What the shared code may know: nothing

`sim/peers.py` names no person. Contacts come from `config.peer_talk.contacts`,
each row `{id, name, language}` — the peer's hub id, what SHE calls her, and
which language the room is in. `tools/character_names.py` greps identifiers and
string literals in the shared code for any character's or cast member's name; a
name in a config *value* is not in code, and that is the whole reason the
contact list is config.

(While mapping this, the scout found that checker blind to f-strings since
Python 3.12 — it collects `NAME` and `STRING` tokens and an f-string is now
`FSTRING_START`/`MIDDLE`/`END` — and behind that blindness six places in
`sim/commitments.py` write the first character's given name into *every*
character's event ledger, plus `sim/ick.py` and `sim/spiral.py` calling a
program method literally named after her and `embodied/health.py` importing her
program package. Those are pre-existing faults, they are recorded in
`HISTORY.md` §19 with this work, and they are not fixed here: each is a
separate edit to shared code with its own risk, and a third character makes
them urgent rather than this feature doing so.)

### 3.2 What a character may learn about a peer

**Only what the peer actually said to her, plus her own contact row.** No
config of the peer's is read, no save of hers is opened, no sheet, no cast
file, no presence, no gauge, no schedule. The hub carries the sender's display
name so a message can be labelled if the contact row is missing, and nothing
else.

This is the machine-versus-person rule seen from a new angle. A shared *file*
about a person is a leak. Words one character sent to another are not a shared
file: they are one person speaking, and the recipient holding them is what a
conversation is.

### 3.3 How the leak check tells a quotation from a leak

`tools/character_leaks.py` flags every name in a character's run that is
nowhere in her record. Two narrow additions:

1. `known(cfg)` also reads `peer_talk.contacts` — a contact she is configured to
   know is part of her record, exactly as her cast file is;
2. it reads the **peer turns** of `peer_chat` out of her own save (read-only,
   `mode=ro`) and adds every name in them. Her own turns are not read, so a name
   she produced is never whitewashed by her having produced it.

The boundary is then exactly the right one: a name in her output is fine if it
is on her sheet, in her cast, a contact of hers, or **was said to her by one**.
A name that is none of those is still a flag for a person to judge. She may
repeat what she was told and may not know what she was not.

---

## 4. Modularity: what a character is

### 4.1 The unit

Six things, and none of them is code:

1. **a config file**, `config_<key>.json`, generated from `config.py:DEFAULTS`
   and backfilled;
2. **a sheet**, `data/characters/<key>.json`, named by `world.character_file` —
   where the four existence properties are declared and where a gauge she does
   not have is removed (`gauges_absent`);
3. **a persona directory**, `prompts_<key>/`: bible, style, backstory, and her
   cast file, beliefs and own record under `data/`;
4. **a save**, `data/<key>.db`, with one bot per save enforced by a lock keyed
   to it;
5. **a program**: `character.program` names a package with an `app.py`. A
   resident-type character reuses `resident` unchanged;
6. **a launcher and a scheduled task**, and a registration with the hub, which
   is nothing more than her display name lowercased.

### 4.2 The registry

`characters.json` at the project root, one row per character that runs as a
process:

```json
{
  "key": "yukari",
  "name": "Yukari",
  "hub_id": "yukari",
  "config": "config_yukarin.json",
  "db": "data/yukarin.db",
  "program": "resident",
  "launcher": "yukarin.cmd",
  "task": "SCAIL_yukari",
  "match": "resident[\\\\/]run\\.py|scail\\.py.*config_yukarin"
}
```

`match` is the exact command-line regex the restarter finds her process by. It
is written by hand and kept in the row rather than derived, because the
restarter kills what it matches and a derived regex that drifts kills the wrong
thing — the current first-character pattern is a *negative* match on the second
character's config, which is precisely the trap.

**Read by the operator's tooling only.** `tools/restart.ps1` builds its table
and its start order from it; `tools/character_names.py` takes its
program-package allowlist from it; `tools/registry.py` is the loader.

**Never read by a bot.** A bot that could read the registry could read another
character's config and save, which is the isolation this tree is built on. A
character learns her peers from her own `peer_talk.contacts` and from nothing
else.

Adding a fourth character is then: her six files above, one row here, one
scheduled task.

### 4.3 The pieces that were two-shaped

| what | before | after |
|---|---|---|
| the restarter's table | three hand-written rows, the first character matched as "not the second one's config" | built from the registry; each row's own regex |
| the program allowlist in the name checker | `PROGRAMS = {"tomoe", "resident"}` | from the registry's `program` fields |
| the one-bot-per-save lock | `--db` or the literal first save, so a launcher that forgets `--db` locks the first character's save | the config's `logging.db_path` when `--db` is absent |
| smoke over every character | already `config_*.json` | unchanged |
| the voice cache | keyed on voice + text; `tools/isolation.py` refuses two characters with the same voice | unchanged, and it is why a third character needs her own voice |
| the run directory | one per run, shared, a character told apart by the `[program]` line inside it | unchanged; noted below |

Left alone deliberately: the run directory naming. `tools/character_leaks.py`
finds a character's newest run by the registration line inside `session.log`,
so the directory name carries no meaning today. Putting the character key in
the directory name is a readability improvement and a change to how three tools
find a run; it is not part of this.

### 4.4 The new section and the existence table

`peer_talk` carries an `enabled` flag, so `Config.REQUIRES` refuses to start
without a row for it. The row is `None` — **every character may have a peer**.
It is not the "runs for everybody" default the table exists to prevent: the
contact list is empty by default, and a character with no contacts has no peer,
no mailbox poll and no conversation. Peer talk needs no body, no world and no
account; it is the mind and the relationship, like the diary and the goals.

`Config.WORLD_KEYS` is untouched: nothing about a peer is a key of the flat
`world` section.

### 4.5 asumin as the third character

The extraction tree under `asumin/` is explicit that nothing in it is wired to
anything that runs — no config, no save, no process — and its own report ends
with a section on what a third character would need. Her material is the same
kind as the second character's: one voice actress alone with a microphone,
2010–2012, 57 broadcasts, 55.7 hours of tape.

**What she is remains his call.** By analogy with the second character the
recommendation is resident-type — `embodied: true`, `in_world: false`,
`sees_him: "resident"`, `has_account: false`, program `resident`, her day
planned from her own home file — and then she needs no new program package at
all: a config, a sheet, a home file, her prompts, a save, a launcher, a task,
one registry row. The two properties are independent, though, and the second
character's sheet says so in its own note: a character can be resident on his
machine *and* have a day of her own. If he wants her in a world she needs
`in_world: true` and everything that switch brings with it, which is a much
larger job.

---

## 4b. A promoted cast member in the room

`tools/promote_cast.py` writes a cast member's files; `docs/shared-world.md` §7
lets her read the world she is in. Neither stops the first character's process
from putting words in her mouth, and its own report says so: "nothing here
marks a roster row as this one runs herself". This is that mark and the two
paths behind it.

### 4b.1 The mark

One field on her row in `data/cast.json`:

```json
"Rena-chan": { "role_id": "ringleader", "agent": "rena", ... }
```

`agent` is the hub id her own process registers under. `sim/roster.py` reads
it: `agent_of(config, who)`, `is_agent`, `agents(config)` for the whole roster,
and `by_agent(config, hub_id)` to attribute words arriving from another
process. It is absent for everybody today, and absent means what it always
meant.

**Nothing else about the row changes.** Her sheet, her mechanisms, her `week`
and her whereabouts stay, because the people who have *not* been promoted still
speak to her through them and the day's planner still needs to know where she
is. One thing changes: this process stops writing her words.

### 4b.2 A room is a thing you can join and leave

Until now a room was a string on a turn -- `group`, `line:<somebody>` -- and who
was in it was re-derived from the roster at each write. That is enough while one
process speaks for everybody. It stops being enough when a turn has to be
*delivered*: somebody who joined at nine did not see what was said at eight.

`sim/rooms.py` gives a room a membership. **On disk it is two places.** The
truth is kv `rooms` in the owning character's own save, `{room: {roster key:
{joined, joined_ts, left, left_ts, agent}}}`. The copy is the shared world's
`members` table (`world/shared.py`), one row per person per room, written the
moment a join or a leave happens, so a second process reads who is in a room
without opening anybody's save. `joined_ts` and `left_ts` are on the owner's
character clock -- the clock the turns are stamped with -- so the two compare;
`joined` and `left` are machine local, for a person reading the file. Adding
the table did not move the file's version number: a table an older build has
never heard of is a table it never queries, and moving the number would have
stopped every running process.

**Joins and leaves are a program hook, not an operator command.** The room's
owner settles membership from the roster at the moment the room starts
(`Exchange.start` -> `_settle_room`, and `CastEngine._agent_beats` for a beat's
room), by the one rule in `rooms.members_for`: the group chat is her and every
friend who is not dormant and not family, anything else is the two ends of it.
A diff, so an unchanged room writes nothing. Each move prints:

```
[room] group: Rena-chan joined at 12:35, and writes her own turns (as 'rena')
[room] group: Rena-chan left at 21:02
```

`Rooms.join` / `Rooms.leave` are the two calls a command would make if one is
ever wanted; nothing else in the tree needs one yet.

**Membership is what routes a turn.** Every turn stamped in a room goes out to
each member who runs her own process, except the speaker, and only if she was in
the room at the moment of that turn: nothing from before she joined, nothing
after she left, nothing she said herself. A cast member who is not marked is
not in any of this -- her turns are still this process's to write.

### 4b.3 What the owner's process does at her turn

**In the exchange** (`tomoe/exchange.py`). `_one_speaker` refuses outright for a
marked speaker: it logs and returns nothing, before a prompt is built, because a
call made there is a paid answer in her voice written by the wrong process and
there is no undoing one. `_their_turns` asks her instead (`_ask_agent`): the
room, the turns she has not been sent, who is in it with her, the moves the
conversation has already made, the moment, and how long the room will wait, all
through her mailbox. The record carries `awaiting`, and `tick` returns without
turning the side while it stands. In a group the others still speak that round,
so the room does not stop for her.

**The ask carries the moves, and the answer carries one back.** Every call that
writes a turn returns a one-line summary of what the turn came to, and the room
keeps the list of them (`docs/room-quality.md`): who moved, when, and what the
move was. The envelope's `moves` field is that list, rendered for her by the
same function the owner's writers use (`sim/rooms.py moves_block`), so the two
sides cannot disagree about what has been tried. Her answer sets `gist` on the
envelope going back, `Rooms.put` files it beside her words, and
`_take_agent_turns` writes it into the ledger, so her move is in front of
everybody on the next round. Without it she played the same beat at 07:19 and
again at 07:23 in the audited room, in different words, four minutes apart.

At `exchange.agent_turn_deadline_seconds` (180) the room says so and goes on
without her, and she is not asked again in that conversation -- "goes on
without her" never means somebody else writes her turn. Her turn arriving late
is appended by `_append`, the one path a turn already takes, so it reaches the
record, the thread and the shared world's rooms table with her as the speaker,
stamped where it lands. Nothing rewrites an old message's bytes.

**A silence she chose settles the wait at once.** When the room asks and she
would say nothing, her process sends that back as an answer rather than as
nothing (`sim/rooms.SILENT`, and `silent` on the envelope): the wait ends on
the next pass, the log says she had nothing to say, and neither record gains
an empty turn. Her gates answer the same way -- her phone away, her day's room
budget spent -- because a room must never sit for something that has already
been decided. Before this a deliberate silence and a dead process looked the
same and the room lost the full 180 seconds of its own clock: she had answered
in sixteen seconds and the room sat for another two minutes and forty-eight
(HISTORY.md section 25).

**In the day's plan** (`tomoe/cast.py`). `_speak_beat` writes nothing for her.
The beat is still planned and KEPT: the day needs to know she is there, at that
time, reaching about that, so the line that drops a beat with no words in it
makes an exception for a marked speaker. At the beat's own hour `deliver` puts
the moment in her mailbox ("it is 12:35, the group chat, and the plan has you
opening about: the weekend") and holds the beat undelivered; the loop does not
run an exchange on it while it waits. What comes back fills the beat's `ja` and
it is delivered like any other, an empty answer means she opened with nothing
and the beat is done, and nothing inside
`exchange.agent_beat_deadline_seconds` (600) drops it, said out loud: a plan is
not a promise that somebody spoke. A dropped or answered beat is marked done,
so it stops coming due.

The beat used to be thrown away. `_speak_beat` returned an empty line and the
next line of the planner filtered every beat with an empty line out, so the ask
path had never fired in production: zero beats for her on two
consecutive days while the other three girls got four or five each, and the
girl whose whole character is that she decides where everybody goes had opened
nothing since her row was marked. `tools/agent_seam_test.py` now drives
`plan_day` itself for that case rather than putting a beat in the store by
hand, which is why it went unseen.

**An unplanned moment in the same room goes the same way.** `presence_beat`
fires when she is physically WITH somebody and the two have not spoken for
`cast.presence_gap_minutes`; for a marked speaker it writes no words, puts the
wordless beat into the day's record and lets the ask path carry it, in a room
named `in_person:<key>`. A candidate whose own process has already been asked
and has not answered is not picked again. Both of those were missing and the
result was a refusal in the log every five seconds for as long as the two sat
at the same desk -- 84 lines in seven minutes, no ask sent, and no other girl
at that table getting a turn (HISTORY.md section 25).

### 4b.4 What the promoted process does

The other end is in `sim/peers.py`, shared, and it is the same code for
everybody. A message carrying a `room` is a turn in a room rather than a message
to her -- that one field on the message is the whole classification, and a room
needs no contact row, because the people in it are people in her world. If the
room is waiting for her (`asking`), she writes her turn through
`persona.system_for("friend")` and her own thread, the same assembly as every
other call that writes her words, and sends it back to whoever asked. If it is
somebody else's turn she files it and pays nothing.

**Her side has the same two guards the owner's writers have.** Before her
bubbles go out they pass the sentence filter over the room's last
`exchange.repeat_window_turns` turns from anybody, hers included: a bubble more
than half of whose sentences have already been said is dropped and logged, and
if everything she wrote goes that way the room is told she is silent rather
than left to wait. Her side had no repeat test of any kind until the room
quality work, which is how the same three sentences reached the group chat at
21:33, 21:44 and 21:50. She is also shown the moves the conversation has already made, off
the envelope, and a pocket of her own: three or four concrete things out of her
own material -- her scene, her own circle's chats, her watchlist, her own
record -- each offered to one call and then spent (`sim/pocket.py`,
`docs/room-quality.md`). Never from the owner's cast: the people in that world
are not hers to invent for.

**She runs none of the room's machinery.** No beats, no pacing, no deciding who
speaks next: one process owns a room and every non-owner is a participant who
receives turns and sends turns. A third promoted person needs no new code at
all -- she is a fourth member of the same rooms, and the routing is membership.

That is also why the peer conversation's pacing gates are deliberately NOT
applied to a room turn. The window (`open_from_hm`..`open_to_hm`) and the floor
between two sends (`min_gap_seconds`) exist so two bots cannot run away with
each other in a conversation they are both driving; a room is driven by its
owner, and how often it asks her is the owner's business. What is hers is her
phone access and a day budget of her own: `peer_talk.room_max_per_day` counted
in kv `room_counts`, generous because it is a stop against a runaway rather
than a pace. A room turn used to spend `max_per_day`, the conversation budget,
so at twelve turns a character would have fallen silent in the group chat
because of a section that is switched off for her -- six of twelve gone by
lunchtime.

**And none of the world's, either.** Marking her row stops this process
writing her words; it does not stop HER process writing everybody else's. Her
first forty-five minutes ran the whole world program in her own save --
another pool of rumours, another set of weekly pressures, another day's script
for six people whose day the owner had already fixed. So a character who is in
a world she does not own has every section that WRITES the world switched off
by the existence table, and the readers that used to take those outputs take
the world file's rows instead: `docs/shared-world.md` §8, and
`tools/world_reader_test.py` in smoke. Nothing here changes for the owner --
her planner still plans a beat FOR a marked member and the room still asks her
through the hub, which is what the rest of this section is about.

### 4b.5 What she may learn

The words that arrive, who said them, when, and on which day (kv `peer_rooms`,
capped at `peer_talk.room_keep`). Not the owner's save, not the planner's beats
beyond the one addressed to her, not the social graph, not anybody's meters.
Where she is comes from the shared world she reads read-only, which is what it
is for.

**Which side of a room this process is on is decided by whether it OWNS the
room**, and it owns a room when it has a membership for it: kv `rooms`, written
by `Rooms.join` and by nothing else, and a participant never joins a room
somebody else keeps. A message about a room she owns is somebody speaking for
herself and goes to kv `room_in`, which the beat path and the exchange drain; a
message about a room she does not own is a relay and is filed into her own
record.

The test used to be a roster lookup on the SENDER's hub id, and the row of the
character who keeps a world carries her own hub id in the cast file everybody
in that world reads. So in a reader's process every relay from the only process
that ever writes to her matched: each one was filed as "the owner speaking for
herself in a room I own", into the owner-side queue that nothing on her side
drains, with the envelope's real speaker thrown away. What it left behind:
three turns in her record with the world's owner saying two other girls' lines,
five more stranded in the queue, and her copy of the group chat a full day of
her clock behind the room. The save was repaired by
`data/retired/20260907_210559_rena_fixes/repair_rena_rooms.py`, which takes each
speaker from the world file or from the owner's own log and says which.

**A turn is filed under whoever SAID it.** The envelope carries the speaker on
every turn in it (`Rooms.post_turn`), and the message's `name` is the display
name of the process that sent it -- always the room's owner for a turn she is
only being passed, so filing the sender put somebody else's words in the
owner's mouth. It files the envelope's turns and falls back to the sender only
when the envelope carries none. The same turn arrives twice -- inside the ask
that wants her words, where it has no clock yet, and as the relay of that turn
a moment later, where it has one -- so two rows are the same row when the
speaker, the words and the day match, and the second arrival may add the clock
the first one lacked and nothing else. One consequence to know: the identical
sticker sent twice by the same person on the same day is one row.

### 4b.5a Her record of a room has three readers

It had one, and that was the fault her first evening as her own process showed:
she wrote
six turns of her own in the group chat, they reached the world file and the
owner's record, and in her own process they existed only inside the single call
that produced them.

| reader | what it is for | where |
|---|---|---|
| her next turn in that room | what has been said, as the live turns of the call | `sim/peers.py _room_reply` |
| her own history | the room in her thread between rounds, like every other room | `sim/thread.py _records` / `_peer_rooms` |
| the group view on his phone | the friends' chat as she has actually been shown it | `channels/talkapp_bot.py _group` |

The thread reads it as **one conversation per room per day**, because a
conversation in the thread is a day's conversation everywhere else: the cards
are per day, the curve is cut on a midnight, and a single running record whose
oldest turn had fallen past the cut would have taken that day's turns out of
the thread with it. Each turn keeps its own day and, where the envelope had
one, the real instant, so a stamp is written once and does not move when the
record rolls over (`docs/context.md` §7). A room another process asked her into
is hers and the operator's: `Thread._sees` refuses it for a cast member's
thread, as it refuses her chat with him.

The call that writes her turn hands its own copy in and names the room
(`Thread.build(live_room=...)`), so the stored copy of that room is not read a
second time beside it.

Measured on the first character, who is in no room anybody else owns and has no
such record: her thread is 551 messages before and after, byte for byte
(`data/retired/20260906_1955_rena_rooms/thread_bytes_test.py`).

### 4b.6 The wire

The hub route gained one optional field: `POST /bot/peer` takes `room` beside
`text`, carried verbatim and read by nobody there. `channels/talkapp_bot.py`
sends it and `GET /bot/peer` hands it back.

Nothing in `sim/rooms.py` speaks to the network. It writes what it wants sent to
kv `room_out`, and the one object in the process holding a hub connection
(`Peers.tick`) empties that queue on its own pass -- written to the save the
moment it exists, so a stop mid-pass loses nothing, and a room needs no second
connection. What arrives goes to kv `room_in` and the room's owner drains it on
its next pass.

### 4b.7 Proved, on copies

`tools/agent_seam_test.py`, in smoke: the first character on a copy of her save
with the model recorded rather than called and a hub in this process, one row
marked in the COPY's cast file. It asserts no model call at her turn or her
beat, the ask in her mailbox with the room and the turns, the exchange waiting,
her fabricated reply landing in the record and in the world's rooms table with
her as the speaker, the deadline logging and proceeding, and a member who leaves
and rejoins receiving only what was said while she was in the room. It also
renders another speaker's prompt with the mark on and off and compares the
bytes.

Three more. **The PLANNER's own filter**, driven through
`plan_day` with a canned day script rather than by writing a beat into the
store: a beat for a marked speaker survives with no words in it, and a beat for
somebody this process does write for, with no words, is still dropped. And the
two ends of a chosen silence: her process hands one back the moment she decides
it, and the owner's side reads an empty answer as a settled wait, goes on
without her, and adds no empty turn to either record.

The live path end to end -- two processes, one asking and one answering -- is
proved by matched log lines and matched model calls on both sides, with the
cost of each: section 2.2 of the audit in
`data/retired/20260907_203328_rena_audit/REPORT.md`.

## 5. What his messenger shows

**Recommendation: not in his chat; yes in the backstage view.**

His chat is the relationship. A peer conversation arriving there would be
pushed to his phone, read-receipted, offered a swipe control and answerable by
him, and none of those is true of it — he is not in that room.

The app already has a backstage view of her cast exchanges, fed by the state
push's `group` payload as rows with `who`, `kind` and `turns`. A peer
conversation rides there as one more room of kind `peer`, which costs no hub
change, no new screen and no APK. He sees it when he goes looking, it does not
interrupt him, and each character's panel shows her own copy — the same
conversation from two sides, which is worth being able to read.

**His call:** whether he would rather have a read-only room in the chat list —
one row per peer conversation, no compose box, marked as not his. That is
cheap to add on top of this and it is a matter of taste, not of design.

---

## 6. Costs and risks

**Model calls.** One peer message costs one call on the side that writes it,
and nothing on the side that receives it — reading is free; the reply is the
next call. A conversation is at most `max_turns` calls per side (6), and a day
at most `max_per_day` (12) per character. Against her existing traffic — the
persona on every reply, the director every tick, the state read, the diary, the
cast — that is small.

**The prompt cache.** The system half is `system_for("friend")`, byte-identical
to the arm the cast turns already use and to her him arm minus `style.md`, so
the peer call shares the cached prefix with everything else that writes her
words. The peer contract and the style file sit at the END of the system
prompt, after the cached core, so they invalidate nothing behind them; the
moving half rides after the thread as everywhere else. The one real cost is
that a peer room in the thread changes the thread's bytes — one cold prefix per
character, once, on the first call after the restart.

**Two different models.** The characters are on different models by his call,
so a peer conversation is literally two models talking, and nothing here
assumes a shared model, tokeniser or provider: each side is priced on its own
config and the log's `via <host>` line already names who served. The risk worth
naming is the two voices converging by echo — each answering the other's words,
both of them agreeable models with a helpful streak. Short caps are the answer
in this cut; if it happens anyway it will be visible in the transcripts before
it is visible in a number, which is what the peer room in the backstage view is
for.

**A conversation is often two monologues.** A message that arrives while the
recipient is asleep or has her phone away sits until she looks, and by then the
sender's own day cap may have moved on. That is correct — it is a phone, and
her not being available is the premise — but it means "a conversation" between
two characters on different schedules will frequently be one message and an
answer some hours later. It should not be papered over with a special case that
wakes her up.

**What is not proven yet.** The live path end to end — one running process
posting to the hub and another running process answering — cannot be proven
without both bots restarted, and nothing was restarted. What was proven is in
`data/retired/20260904_peer_talk/REPORT.md`: the transport against a running
hub stub, and a character answering a peer message in her own voice on a copy
of her save.
