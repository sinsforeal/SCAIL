# Answering a message again, and putting the answer where the old one was

Nothing that is added to a character reaches a reply she has already sent.
When a mechanism is fixed, the only way to see what the reply *should* have
been is to draw it again with the machinery as it is now -- on a copy, with
her history cut back to the moment -- and the only way to make the chat
carry it is to put it there through her own bot, so her store and his phone
agree. Two tools, one for each half.

    python tools/regen_reply.py   --message-id 140 [--anime Mitsudomoe --ep 9]
    python tools/replace_reply.py --message-id 141 --text-file new.txt

## 1. Regenerating (`tools/regen_reply.py`)

In order:

1. **A consistent copy of the save**, with sqlite's backup API. A plain file
   copy of an open database returns the on-disk image from before the
   process started writing; one such copy showed 0 rows in every table.
2. **History cut back, and the future with it**: every message after his is
   deleted from the copy and his is marked unread; so is every row newer than
   his message in the timestamped tables (events, facts about him, her own
   memories, scenes, state, digests, threads, cast facts). Without that cut a
   regenerated reply to message 140 quoted message 142. kv rows carry no
   time and are not cut; that is the known remainder. What she actually sent
   is read off first, for the comparison at the end.
3. **The whole App built on the copy**, `--console --no-sensors`, so it
   registers with no hub and nothing can reach him or the live save. The
   logger is stubbed except for the lines worth reading (`[watching]`,
   `[recap]`, `[lookup]`, `[attention]`, `[persona]`, `[context]`).
4. **Optionally, the episode re-read**: `--anime <title as his list spells
   it> --ep N` runs the watching module's fetch synchronously -- synopsis
   from the recap cache if a valid one is there, else through the browser --
   and makes the digest, so the reply is drawn with the episode in the room.
5. **The lookup the loop would have started**: `Lookup.start` on his text,
   waited for, so a name he dropped is looked up (the pixiv page for a
   character, the card for a show) before she answers.
6. **The reply path itself**: `ensure_day`, `maybe_generate_schedule`, a
   forced director tick with his text, then `persona.generate` with what
   was looked up. Nothing is delivered.
7. **Then and now**, printed side by side, with the situation lines the
   watching module offered and the lookup's gist above them.

It spends model calls: a director tick, the state role, the digest roles once
each, the persona, the continuity check on her draft for a character who has
that check, and a lookup's classifier and digest. Well under a dollar. For a
character whose sheet says she has not got the check -- the second one -- the run says so in its first lines, because no `[editor]` line at
all used to look exactly like a gate that had declined. The copy is `%TEMP%/scail_regen.db` and is overwritten by
the next run.

**What it is for.** Showing a fix. The reply it prints is what she would say
*now*; whether that is better is read, not measured, and the log lines it
keeps are the evidence that the mechanism did what it was changed to do
(the synopsis line present, the lookup fired, the attention budget kept
what it should).

## 2. Putting it in the chat (`tools/replace_reply.py`)

Her sent reply has two records: the row in her store (`messages.id`) and the
message on the hub (`messages.tg_id`, the hub's id, which the app shows).
Both must change, and the voice note attached to the hub message is the old
text spoken. The tool does all three through the running bot and the hub,
never by writing to the live save from outside:

1. `/context msg set <store id> <text>` through the hub's ops queue -- the
   bot rewrites its own row;
2. `POST /bot/edit {char, id: <hub id>, text}` -- the hub rewrites the message
   and the app redraws it;
3. if the message carries a voice note: the new text rendered through her own
   `TTSQueue.render` (same synthesis, same cache, her voice) and attached with
   `POST /bot/voice {attach_to: <hub id>}`, which replaces the note in place.
   `--no-voice` skips this.

It ends by reading the store back and saying whether it matches.

**Adding rather than replacing**: the ops command `/send <text>` delivers a
message as her through her own delivery queue and store, with her typing
pauses; used from the app's ops bar or `POST /ops/cmd`. **Removing**:
`/context msg drop <store id>` deletes from the store and the hub. The first
time a regenerated reply was put into the chat it went in with `/send` under
the original, which read as two answers to one message; replacing is the
right shape when the original is wrong.

## 3. Traps, each one met

- **The log lies by omission.** `[persona] 1 bubble(s): ...` and `[sent ] ...`
  print the first 80 characters. A five-line message reads in the log as one
  line, and looked, once, as though four lines had been lost. Read the store.
- **Store id is not hub id.** 141 in the store was 1813 on the hub. The tool
  reads `tg_id`; do not guess.
- **The hub's edit changes text only.** The voice note stays the old text
  unless re-rendered; the tool does it.
- **Regenerating changes what is in the room.** `--anime/--ep` stores the
  fetched episode in the COPY's `watching_last`; the live save is untouched
  and the live bot finds its own synopsis on its next persona call (the lazy
  re-read in `WatchingHim.current`).
- **A tool of the same purpose was discarded once**
  (`data/retired/20260902_002730_regen_discarded/regen_replies.py`, with
  `--n` / `--ids` / `--fresh`); the documents pointed at it for a day after
  it was gone. This one is the one that exists.

## 4. The same two halves, inside the running bot

Both halves of this also exist as controls in the chat: a swipe on one of
her messages draws that reply again, and keeping one puts it where the old
one was. **`docs/talkapp.md` §10 is the spec.** The differences are
what a live control needs and a tool does not:

- **the prompt is frozen, not rebuilt.** These tools cut a COPY of the save
  back to the moment and rebuild the prompt from it, which is the only way
  to answer again with machinery that has since changed. A swipe keeps the
  exact messages array the reply went out on (`store.reply_prompts`, written
  as the bubble leaves) and sends that; nothing is copied and nothing is
  cut, and on the same model the host answers nearly all of it out of its
  cache. The one exception is a reply from before the freeze existed, which
  has no kept array: a swipe on one of those runs the copy and the cut once
  (`sim/reconstruct.py`, which is where both now live and which this tool
  imports), files the rebuilt array marked `reconstructed`, and draws from
  that (`docs/talkapp.md` §10.7).
- **the model is his to pick.** A swipe goes out on whatever the chat's
  model control is toggled to (kv `voice_model_override`, her voice roles
  only), so the same frozen prompt can be compared across models.
- **every answer is kept.** `store.swipes` holds them all, the delivered
  reply as number 0; only the one he keeps reaches her record.
- **keeping one is these three steps exactly**: `/context msg set`, `POST
  /bot/edit`, and the voice note rendered again and re-attached.

These tools stay. Showing what a FIX would have done needs the copy and the
cut, and a swipe deliberately refuses both.
