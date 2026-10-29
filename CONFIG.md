# CONFIG.md: every key in `config.py:DEFAULTS`, generated

One block per section: the key, its default, and the comment beside it in `config.py`. The comment is the documentation; a key without one is described in the module that reads it (§4-§12; `tools/smoke.py` names a key nothing reads). Nested blocks are indented. Regenerate with `tools/docs_assemble.py` after editing DEFAULTS.

**`api`**

- `base_url` = "https://api.deepseek.com"
- `api_key` = ""
- `max_retries` = 3
- `long_answer_warn` = 8000 -- Every role's max_tokens is the API maximum (393216). A cap that is too low fails silently and expensively: the persona spent its whole 3000 thinking and returned nothing, so she read him and said nothing, and her diary was being cut off mid-entry without anyone noticing. max_tokens is a ceiling and not an allocation, so headroom is free. The caps were also the only thing bounding a runaway answer, and this is what replaces that: anything longer than this is called out.
- `json_retries` = 2 -- a JSON role whose answer does not parse is asked to fix it this many times before the caller sees None (the compile of 2026-08-26 kept a broken answer as the day's memory) a JSON role's answer that does not parse is asked again this many times (LLM.call_json). Two, not one: with reasoning on, the cast roles answer in the chat's own label format one call in ten, and a second miss on one retry was a turn nobody spoke (the A/B of 2026-09-04)
- `request_timeout_seconds` = 600 -- a request that has not answered in this many seconds is a failure: the coherence read ran 1152 s to 131072 output tokens on the loop thread with nothing to stop it, and the retry sent the runaway back as its prompt for another 1081 s
- `empty_retries` = 1 -- an answer with no words (reasoning only, finish stop) is asked again this many times
- `stream` = True -- every answer is streamed and read as it is written (LLM._stream), so a bad one announces itself: a stream that ends with no finish reason was cut off and goes round the retry; finish `length` is the host's own output cap and the answer is logged TRUNCATED and asked again once (`empty_retries`), then given up on rather than sent as half a reply. False sends the old single-body request.
- `stream_stall_seconds` = 240 -- no bytes for this long is a dead host, not a slow one: the call fails here instead of at request_timeout_seconds, which still bounds the whole answer. Reasoning streams too, so a live host is never silent for long
- `repeat_guard_chars` = 6000 -- An answer that has begun repeating itself word for word is ended where the repetition starts (LLM._stream). Past this many characters the last 400 are counted against everything written before them, and an answer whose tail has already been written this many times is abandoned. The day auditor looped five times over 2026-09-03 and 2026-09-04, each to the host's 131072-token ceiling after about nineteen minutes; these numbers stop each of them inside the first 2% and fire on none of the other 8,349 calls on disk. 0 turns the guard off.
- `repeat_guard_copies` = 4
- `json_retry_max_chars` = 8000 -- The largest answer `LLM.call_json` will hand back to the model when asking it to fix its own JSON. Above this the original question is asked again instead: a runaway is not repairable and sending it back bills its whole length as prompt (two calls at 150,000 prompt tokens on 2026-09-04).
- `provider` = "together" -- Who answers. `provider` is the one to use; `providers` names each one -- the official DeepSeek endpoint (kind deepseek, key api_key, the API-maximum max_tokens sent) or a host on OpenRouter (kind openrouter, key from openrouter_key_file, no max_tokens sent, the role's thinking flag mapped to `reasoning`) -- with the slug each of the bot's model names maps to there and, per slug, the host order pinned with no fallback outside it. The official account ran dry on 2026-08-31 and the persona test put DeepSeek at Together level with official at half the latency (data/model_test/20260831_persona_t1).
- `providers` = {
- `  official` = {"kind": "deepseek", "base_url": "https://api.deepseek.com"
- `  models` = {"deepseek-v4-flash": "deepseek-v4-flash", "deepseek-v4-p...
- `  together` = {"kind": "openrouter"
- `  models` = {"deepseek-v4-flash": "deepseek/deepseek-v4-flash-0731", ... -- kimi-k3 is the second character's model since 2026-09-02 (docs/yukarin-voice-models.md). A model name missing from a provider's map falls through as a literal and the host rejects it.
- `  kimi-k3` = "moonshotai/kimi-k3"
- `  sakana-namazu` = "sakana/sakana-namazu" -- the second character's voice model since 2026-09-04 (his call): one host, 262k window, reasoning on
- `  deepseek-v4-flash-0731` = "deepseek/deepseek-v4-flash-0731" -- the five the chat's model toggle needed and the table did not have (his list, 2026-09-04). The dated DeepSeek names are their own entries: -0731 and -0813 are different slugs from the undated ones already here, not aliases.
- `  deepseek-v4-pro-0813` = "deepseek/deepseek-v4-pro-0813"
- `  gemini-3.8-flash` = "google/gemini-3.8-flash"
- `  glm-5.3-flash` = "z-ai/glm-5.3-flash"
- `  glm-5.3` = "z-ai/glm-5.3",}
- `  order` = {"deepseek/deepseek-v4-flash-0731": ["together"] -- Together does not serve pro; the judge roles' pro calls go to the cheapest fp8 hosts that answered cleanly in the ranking
- `  moonshotai/kimi-k3` = ["together"]
- `  sakana/sakana-namazu` = ["Sakana AI"]
- `  deepseek/deepseek-v4-pro` = ["alibaba", "gmicloud", "coreweave"]
- `  deepseek/deepseek-v4-pro-0813` = ["StreamLake", "Alibaba", "DeepSeek"] -- every pin is the host name OpenRouter's own receipt reports, not the endpoint tag: pinned under the tag, every call logs a fall-through that never happened
- `  google/gemini-3.8-flash` = ["Google AI Studio"] -- Vertex's global endpoint was at 19% uptime when this was measured; AI Studio also accepts temperature and Vertex does not
- `  z-ai/glm-5.3-flash` = ["Z.AI", "Novita", "GMICloud"]
- `  z-ai/glm-5.3` = ["Z.AI", "Friendli", "AkashML"],}}
- `  qwen` = {"kind": "openrouter"
- `  models` = {"deepseek-v4-flash": "qwen/qwen3.8-flash", "deepseek-v4-...
- `  kimi-k3` = "moonshotai/kimi-k3", "sakana-namazu": "sakana/sakana-nam...
- `  deepseek-v4-flash-0731` = "deepseek/deepseek-v4-flash-0731"
- `  deepseek-v4-pro-0813` = "deepseek/deepseek-v4-pro-0813"
- `  gemini-3.8-flash` = "google/gemini-3.8-flash"
- `  glm-5.3-flash` = "z-ai/glm-5.3-flash"
- `  glm-5.3` = "z-ai/glm-5.3",}
- `  order` = {"qwen/qwen3.8-flash": ["alibaba"]
- `  moonshotai/kimi-k3` = ["alibaba"]
- `  sakana/sakana-namazu` = ["Sakana AI"]
- `  deepseek/deepseek-v4-pro` = ["alibaba", "gmicloud", "coreweave"]
- `  deepseek/deepseek-v4-flash-0731` = ["together"]
- `  deepseek/deepseek-v4-pro-0813` = ["StreamLake", "Alibaba", "DeepSeek"]
- `  google/gemini-3.8-flash` = ["Google AI Studio"]
- `  z-ai/glm-5.3-flash` = ["Z.AI", "Novita", "GMICloud"]
- `  z-ai/glm-5.3` = ["Z.AI", "Friendli", "AkashML"],}}
- `voice_models` = ["kimi-k3", "deepseek-v4-flash-0731", "deepseek-v4-pro-0813" -- The models the chat's toggle offers for her voice (`/voicemodel`, the control in the chat header). Names from the active provider's own table; one that provider cannot serve is not offered. This is the menu, not the choice -- the choice is kv `voice_model_override` and lives on her save, per character, for the run.
- `openrouter_key_file` = "secerts/openrouter.txt"
- `host_fallback` = True -- when the pinned host fails, OpenRouter's next host for the SAME slug answers (his call, after Together returned 503 on every kimi-k3 call for a stretch); the model cannot change, only who serves it, and the receipt (`served_by`, the `via` in the log) names who did. Off: the pinned host or a missed call.
- `hosts_without_tools` = ["Chutes", "Fireworks"] -- The hosts that accept a request carrying `tools` and answer as if none were offered, as OpenRouter's own endpoint list has them (`docs/tool-calling.md` §7). Spelled EXACTLY as the receipt spells them (`served_by`, the `via` in the log): 'Sakana AI', not 'sakana'. A call that has to pick a tool asks the same question as JSON in her text when the last receipt names one of these, so the transport is decided by who actually answered and never by a guess about the pin.
- `cache_settle_seconds` = 15 -- A call that goes out this soon after the previous call of the same role FINISHED is not evidence about the prompt cache, so it is counted on its own line in `/provider` and never as a cold call (`LLM._track_cache`). Measured on Z.AI at 44k tokens: the entry a call writes is not readable for about ten seconds after that call completes, and the delay may scale with the prompt, since at 15k it was readable in 8.5 s (2026-09-04, data/retired/20260904_openrouter_audit/REPORT.md §1).
- `cache_burst_hold` = True -- THE FIRST CALL OF A BURST GOES OUT ALONE. At the day boundary about fifteen calls of one role go out back to back, each inside the settle window of the one before, so none of them could read the entry the one before wrote and every one of them was billed at the uncached rate. With this on, a call that would go out inside the settle window of a COLD call of the same role on the same system prefix waits out the remainder first, and the rest of the burst then reads that prefix. At most one wait per burst, whatever happens: a role whose host does not cache at all must not pay fifteen of them. The log line is `[cache] <role>: held Ns so the burst reads the first call's prefix`.

**`models`** -- There is no second PROVIDER and no fallback between providers, his call. A provider maps a model NAME to its own slug, so a provider fallback can change the MODEL and not just the host, and nothing downstream reads which model actually answered; and with one host in the chain the cooldown demoted the only host there was and answered nothing for thirty minutes on a wobble (2026-09-03). A call that fails after `max_retries` is logged, written to kv `missed_calls`, and caught up when the host is back (`App.catch_up`). `qwen` stays defined and pinnable via `/provider qwen`, a decision somebody takes. One entry per LLM role. prompt is a file under prompts/. With thinking on, DeepSeek spends max_tokens on reasoning first (thousands of tokens even at low effort) and can return an empty answer, so thinking is reserved for the persona and every JSON role answers directly. ---- the six sections a patch anchor ate on 2026-08-31, rebuilt from ---- config.json (values identical; the comments are in HISTORY's era)

- `director` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `sleep` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `state` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `schedule` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `phone` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `persona` = {"model": "deepseek-v4-flash", "thinking": True, "tempera...
- `timeline` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `episode_cards` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `vault` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `downloads` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `ick` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `revise` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `revise_self` = {"model": "deepseek-v4-flash", "thinking": True, "tempera...
- `rupture` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `rupture_settle` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `spiral` = {"model": "deepseek-v4-flash", "thinking": True, "tempera...
- `spiral_settle` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `settle_beliefs` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `note_read` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `voice` = {"model": "deepseek-v4-flash", "thinking": True, "tempera...
- `showrunner` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `cast_arc` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `cast_evolve` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `cast_reply` = {"model": "deepseek-v4-flash", "thinking": True, "tempera...
- `peer_reply` = {"model": "deepseek-v4-flash", "thinking": True, "tempera...
- `cast_turn` = {"model": "deepseek-v4-flash", "thinking": True, "tempera...
- `graph` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `npc_moment` = {"model": "deepseek-v4-flash", "thinking": True, "tempera...
- `gloss` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `watching_digest` = {"model": "deepseek-v4-flash", "thinking": False, "temper... -- the important parts of an episode he is watching, condensed from the whole scraped synopsis into a few hundred Japanese characters for her situation block (sim/watching_him.py). Machinery, not her: the prompt carries no person and the output is a digest she reads.
- `digest_judge` = {"model": "deepseek-v4-flash", "thinking": False, "temper... -- chooses among several pages' digests of one episode, or rejects them all (sim/watching_him.py; how many are read is `recap.candidates_target`)
- `which_one` = {"model": "deepseek-v4-flash", "thinking": False, "temper... -- which of several candidate works he means, when the deterministic filters leave more than one (sim/resolver.py; the `which_one` section). Machinery: the prompt names nobody, the answer is an id out of a table code built, and it never runs in a reply path.
- `transcript_digest` = {"model": "deepseek-v4-flash", "thinking": False, "temper... -- the episode's own subtitle file read as an account of its scenes in order (sim/transcripts.py): the ground truth the judge holds web candidates against, and the digest when none of them survives. Machinery, not her: the prompt carries no person.
- `episode_account` = {"model": "deepseek-v4-flash", "thinking": True, "tempera... -- everything read about one episode merged into ONE account of it (sim/episode_account.py): every scene in order, the named parts, the running gags, the lines, what the episode points at. The judge above answers which single page to trust; this answers what happened, and the two are not the same question. Machinery, not her: the prompt carries no person, and the answer is a record of a television episode that every character on the machine reads. It is the one role here that SYNTHESISES rather than condenses, and on low effort it condensed: asked for 1,200 to 3,000 characters over six pages and a transcript it returned 214, which is a summary of the summaries and is the thing this exists to stop. Thinking on, effort high, because completeness is the whole point of the role and it runs once per episode for the whole machine.
- `eroge_digest` = {"model": "deepseek-v4-flash", "thinking": False, "temper... -- what is happening in the visual novel he is reading, written from the lines his text hooker caught while he read them (sim/eroge.py). Machinery, not her: the prompt carries no person, and it is the prompt rather than a filter that decides what an explicit stretch comes out as.
- `him_profile` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `gossip` = {"model": "deepseek-v4-flash", "thinking": True, "tempera...
- `orbit` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `bond` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `nudge` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `commit` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `reflect_cast` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `compare` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `commit_him` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `recall` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `withhold` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `said_when` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `approach` = {"model": "deepseek-v4-flash", "thinking": True, "tempera...
- `intent` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `experience` = {"model": "deepseek-v4-flash", "thinking": True, "tempera...
- `morning` = {"model": "deepseek-v4-flash", "thinking": True, "tempera...
- `anticipation` = {"model": "deepseek-v4-flash", "thinking": True, "tempera...
- `reflect` = {"model": "deepseek-v4-flash", "thinking": True, "tempera...
- `local_events` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `events` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `devoice` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `affection` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `lookup` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `lookup_gist` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `search_gist` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `character_digest` = {"model": "deepseek-v4-flash", "thinking": False, "temper... -- a fan-encyclopedia page about a character he named, condensed to what a viewer knows (sim/lookup.py, `lookup.character_pages`)
- `x_post` = {"model": "deepseek-v4-flash", "thinking": True, "tempera...
- `x_reply_judge` = {"model": "deepseek-v4-flash", "thinking": False, "temper... -- answering somebody who answered a post of hers: one judge over the batch waiting under her posts (which one, or none), then one call in her voice for the one she picked (tomoe/replies.py)
- `x_reply` = {"model": "deepseek-v4-flash", "thinking": True, "tempera...
- `x_repost_judge` = {"model": "deepseek-v4-flash", "thinking": False, "temper... -- what the account does with a post she has just sent him: repost it, like it only, or neither. Her taste decides it -- a roll used to (tomoe/curation.py, act_on_shared). A judge: it decides about a post and writes none of her words, so it gets no character sheet.
- `x_account` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `editor` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `social` = {"model": "deepseek-v4-flash", "thinking": True, "tempera...
- `share_pick` = {"model": "deepseek-v4-flash", "thinking": True, "tempera... -- which post from her scroll she sends him: the one call in this project whose answer is a tool call that is acted on (tomoe/share_pick.py). It speaks AS her -- the system half is her whole persona assembly, not this file -- so the prompt named here is only the closing instruction, and a character addressed in another language names her own copy of it the way she does for every other role. Flash and the persona's own thinking and effort, because it is her judgement about a post and she writes on flash. It runs once per thing she wants to show him, behind the system half the reply is about to send anyway, so most of the prompt is a cache hit: the replay of forty-six moments that decided this was worth wiring measured $0.0009 a pick and four cents for all forty-six (data/retired/20260906_1912_pick_test/). A character whose voice is on another model keeps this on flash, as the director is: it decides rather than writes.
- `diary` = {"model": "deepseek-v4-flash", "thinking": True, "tempera...
- `reconcile` = {"model": "deepseek-v4-flash", "temperature": 0.2, "max_t...
- `weekly` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `cast_day` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `cast_beat` = {"model": "deepseek-v4-flash", "thinking": True, "tempera...
- `cast_life` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `foresee` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `expect_him` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `wonder` = {"model": "deepseek-v4-flash", "thinking": True, "tempera...
- `wonder_answer` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `scenery_judge` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `habits_him` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `zeitgeist` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `taste` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `coherence` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `observer` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `watch_pick` = {"model": "deepseek-v4-flash", "thinking": False, "temper...
- `pick` = {"model": "deepseek-v4-flash", "thinking": True, "tempera... -- What she would do with the phone in her hand (sim/pick.py). Flash, at the persona role's own thinking and effort, for every character INCLUDING the two on a voice model: this call decides something and writes none of her words, so it has no more business on her voice model than the director has. No prompt file of its own -- the system half is `persona.system_for("him")` byte for byte, which is what puts the pick behind the same cached prefix as her reply, and the tool definitions are the rest of the instruction.

**`peer_talk`**

- `enabled` = False -- Two running characters talking to each other over the hub (docs/peer-talk.md, sim/peers.py). Off, and with no contacts, for every character until one is written in: a character with an empty list has no peer, no mailbox to poll and no conversation, which is why the row in Config.REQUIRES is None rather than a property of her existence. Peer talk needs no body, no world and no account.
- `contacts` = [] -- Who she can write to. One row per peer: `id` is the peer's hub id (her display name lowercased with the spaces out, which is what she registers with), `name` is what THIS character calls her, and `language` is the room's language ("" = the way she writes to her own people). Nothing else about a peer is knowable from here: a character never reads another character's config or save, and what she learns of a peer is the words that arrive.
- `max_turns` = 6 -- How many turns of HERS one conversation may run to. At the cap it is closed and further messages are still received and read. Two characters each holding their own cap is what stops two bots talking forever without either having to trust the other to stop.
- `max_per_day` = 12 -- and how many messages she may send to peers in a day, counted with store.bump_today so a restart does not reset it
- `min_gap_seconds` = 90 -- the floor under two sends of hers, on top of the reading-and-typing delay taken from the length of what she is answering
- `min_gap_minutes` = 45 -- how quiet it has to have been, in either direction, before she opens something new
- `open_p` = 0.02 -- the chance per loop pass that she opens one, inside the window below. Sized so an opener lands somewhere across the window rather than at its first minute.
- `open_from_hm` = "09:00"
- `open_to_hm` = "24:00"
- `keep` = 60 -- conversations kept in the save, and how long one may stay live before it has trailed off
- `live_minutes` = 120
- `room_keep` = 60 -- How many turns of a room she is in but does not own she keeps on her own side (kv `peer_rooms`). She is a participant there: what she holds of that room is the words that arrived, who said them and when, and nothing else.
- `room_max_per_day` = 60 -- And how many turns she may say in a day in rooms she does not own, counted on its own key (kv `room_counts`). Separate from `max_per_day` above because the two are different things: that one is her own conversations, this one is somebody else's room asking her. A room turn used to spend the conversation budget, so twelve answers in the group chat put a character out of a section that is switched off for her anyway. Generous, because the pacing of a room is its owner's and this is only a stop against a runaway.

**`world_shared`**

- `enabled` = False -- The world as a file more than one process may read (world/shared.py, docs/shared-world.md). Everything a character knows about the world around her is in her own save, so a second process running one of the people beside her as a character of her own would plan a day the first process never had. The owner writes a copy of the day's public facts -- who is where, what the day settled, every turn spoken in every room, the edges, the orbit, the pool -- and anybody else in the same world reads them.
- `id` = "" -- Which world. The file is `<world.shared_dir>/<id>/world.db`, so two characters share a world exactly when they name the same id.
- `owner` = False -- One writer per world: the character whose config says this. Everybody else opens the file read-only and never writes a row.
- `read_rows` = 8 -- How many rows of one of the world's tables a READER takes into a prompt: who is where, what is going round, the people around the people. The owner's own modules have their own limits and do not read this; it bounds what a non-owner puts in front of a model in place of a subsystem that is switched off for her.
- `reader_writes_own_rows` = True -- Whether a character who does NOT own this world writes the rows that are about herself: the windows her own day planner puts her in, the rooms she is in, and the lines her own plan settled, each under her own id and a source naming her own planner (world/shared.py, docs/shared-world.md §2). Everything else in the file stays the owner's and a row about anybody else is refused. Switched off she writes nothing at all, and the owner's draw of her week on the world's roster is all the world ever has of where she is.

**`character`**

- `name` = "" -- her name, its kanji and its reading: hers, in her config, never here
- `program` = "tomoe" -- which program runs her: `tomoe` (a girl in Tokyo with a phone) or `resident` (on his machine). The runtime imports `<program>.app` and asks it to build her world, her people, her account and her sight; what a program does not build does not exist in her process.
- `name_ja` = ""
- `reading_ja` = ""
- `user_name` = "User"
- `writes_to_him` = "english" -- Which language she writes to him in. The first character is bilingual and the arrangement is load-bearing for her -- English with him is the one room her English lives in, and everything else in her life is Japanese -- so the instruction was written straight into persona.py. A character who has only one language was then told, in her own assembled prompt, to write in the other one.
- `instructions` = "auto" -- Which set of instructions ADDRESSED TO HER she is given -- her situation block, the section headers above it, the closing block that says what to write and how. An arm to be compared, not a decision: `as_they_run_today` (the control, preserved byte for byte), `in_english`, `in_her_language`. All of them live side by side in the code (`sim/lang.py`); `SCAIL_INSTRUCTIONS` overrides for a run and `sim.lang.set_override` for one process, so a harness can build the same character's prompt every way without a restart or a config edit.  Not the same question as `writes_to_him`, which is what language she ANSWERS in: a character can be instructed in English and write Japanese, and that is what both characters did until 2026-09-02. `auto` is decided from `instruction_language` below: her own language when this switch has a second one to render for her, the control when it has not. It was the control for everybody until 2026-09-07, because every bench bought up to 2026-09-02 had been bought under it -- and that bench was the second character's voice, which says nothing about a character composed afterwards. Two of the four declared Japanese and were instructed in English.
- `instruction_language` = "english" -- Which language the arm `in_her_language` renders for this character, and what a role writing material she reads is told to write in. A separate question from `writes_to_him` and from `instructions`, and it must not be read off either: the first character is bilingual, her chat with him is the one room her English lives in, and every measurement taken on her was taken with her instructions in English -- so hers is "english", `in_her_language` renders the same bytes as `in_english` for her, and `/lang ja` tells him there is nothing to switch her to. Japanese is the only value that renders anything today, because every wording behind the switch lives in the source as an English/Japanese pair (`sim/lang.py`).
- `style_prompt` = "" -- PERSON-SHAPED PATHS, EMPTY HERE AND ALWAYS. Every path in this block is one character's own material -- her speech guide in each language, the roster of who is around her, their sheets, how each of them may sound, what she has decided about him and about herself. A config that does not carry the key has it written in from here on its first load, where it then looks authored, so a default that is one person's file is inherited by the next character in silence: the fourth character's first day was the first character's household, map, roster and sheets, out of these lines. Her own config names hers, and `Config.PERSON_FILES` refuses the boot when a section that reads one of them is on and the path is empty or names a file that is not on disk.
- `style_ja_prompt` = ""
- `cast_file` = ""
- `cast_sheets_dir` = ""
- `own_cast_file` = "" -- HER OWN people, for a character in a world somebody else keeps: a second cast file and a second sheets directory, empty for the character who owns her world (her cast file is her circle). A reader plans, speaks and opens rooms with the people in this file only, writes all of it to her own save and none of it to the world, and still answers in the owner's rooms when asked. The world's roster stays on `cast_file`, read for names, and a key in both files is hers (docs/shared-world.md section 9).
- `own_cast_sheets_dir` = ""
- `voice_rules_file` = ""
- `voice_flags_keep` = 200
- `beliefs_file` = ""
- `self_beliefs_file` = ""
- `existence` = { -- What KIND of existence this character has. Three independent properties rather than two named modes, so a second character picks a combination instead of inheriting the first one's assumptions. A sheet overrides any of them under `existence`.  embodied   she has a body: hunger, fatigue, comfort, illness, and a physical place to be. False for someone who lives in a machine, and then the gauges that measure a body are declared absent on the sheet as well. in_world   her day advances whether or not he is there: a schedule, places, a cast, weather, a clock of her own. This is the whole of `sim/schedule.py` and most of the day's ledger. sees_him   how she learns what he is doing. "digest" is the app on her phone: a felt decision to look, gated by access and by how long he has been quiet. "resident" is continuous and ungated -- she is on his machine and simply sees it, which makes the telemetry her environment rather than something she checks. "none" is a character who has no window onto him at all.  The combinations are all meaningful and none is special-cased. A character can be embodied and in a world and resident on his machine at once: a life that advances AND a permanent view of his desktop.
- `  embodied` = True
- `  in_world` = True
- `  sees_him` = "digest"
- `  with_him` = "chat" -- Whether she has any contact with him at all. "chat" is the relationship: a chat of her own with him, the impulse to write first, everything she feels and expects of him. "none" is a character who exists for somebody else's circle and not for him -- Rena, promoted out of the first character's cast: she knows of him only what her friend lets slip, writes to nobody but her own people, and his phone does not list her.
- `  has_account` = True -- Whether she holds an account of her own out in public. False and nothing posts, nothing curates and nothing measures her taste drifting away from his -- the second character has none, twice over: in the fiction the account is his and she is resident on his machine, and outside it the real person left that medium.
- `mal_person_id` = "" -- Which person she is on MyAnimeList, as the id in the URL of that person's page, or "" for somebody who has never been in anything.  An ID and never a name. Her given name alone matches nine other people in his mirror's cast rows by substring, and which of them a `LIKE '%name%'` answered with was down to the order sqlite happened to return. This is also the SWITCH: `Config.REQUIRES` turns an empty id into the missing property the `role_check` section needs, so a character who has never acted never reads his mirror, never pays a read and never gets a line about a part.  The sheet may set it too (`data/characters/<id>.json`), and the sheet wins, so a regenerated config cannot lose it.
- `neutral_file` = "" -- What fills the character-shaped holes in a mechanism prompt (`Config.fill`). One file per character; the values for the character the prompts were written around are the exact spans that came out of them, so her rendering is byte-identical to the old files.
- `timeline_file` = "" -- The dated once-events of her past, for a character who was read out of a real archive: a trip, an illness, an audition, a move, a purchase, each with the day or the span the archive supports and the episode and cue index it was said at. `sim/seed_memories.py` writes them into her memory store once, at boot, so that her past can be reached by meaning and by the deliberate search and not only by somebody naming it. Empty for a character with no such archive, which is most of them, and then nothing runs and nothing is logged.
- `memories_file` = "" -- Her quoted moments off the same archive, which stay in the retrieval (`lore.memory_file`) and are NOT written into the store. Named here because the seeder reads it to see which of its rows are the same moment of tape as a timeline event, so that the overlap between the two routes into her prompt is recorded on the row rather than found later.

**`language`** -- How far the instruction arm reaches. The arm itself is `character.instructions` and it covers what the prompt builder writes: her section headers, her situation block, the closing instruction. This section is what it reaches BEYOND that -- the sentences under those headers, which other roles wrote.

- `enabled` = True -- Whether the roles that write her material are told which language to write it in while she is being instructed in her own language. Off, and the switch moves the labels and leaves the prose under them in whatever the roles happened to write: her own language over an English digest, an English fact list and English beliefs about him, which is what the second character read before this existed.
- `material_roles` = ["anticipation", "approach", "commit", "commit_him", "dia... -- The roles whose OUTPUT she reads inside her own prompt. Each is given one line naming the language, keys and fixed choices excepted (`sim.lang.material_line`). Nothing already in the record is touched: a fact written in English stays as written until the forgetting curve drops it.  A role is on this list only when its output is prose FOR HER and nothing else. Four roles that write into her prompt are left off on purpose, because code reads their words as data: the phone's digest is scanned with English patterns for the one thing off his screen she remarks on, the director's scene and the day's plan carry places and activities other modules match on, and the state role is gauge arithmetic with nobody being addressed in it. Their LABEL in her prompt is already in her language; the account under it is the machine's. The editor is off the list too and forks inside its own prompt instead (`[[?her_language]]`), because the note it writes is put in front of her and the verdict beside it is for the log.

**`world`**

- `character_timezone` = "Asia/Tokyo"
- `user_timezone` = "local"
- `weather_enabled` = True
- `weather_latitude` = 35.6895
- `weather_longitude` = 139.6917
- `weather_refresh_minutes` = 60
- `weather_cache_path` = "data/weather_cache.json"
- `holidays_file` = "data/jp_holidays.json"
- `school_calendar_file` = "" -- PERSON-SHAPED PATHS, EMPTY HERE, for the same reason as the block in `character`: her school's year, her map, her household as an economy, what is going round where she is, her taste sheet and the places she keeps going back to are one person's, and a default that is one person's file is inherited by the next character in silence. `Config.WORLD_KEYS` blanks these for a character with no world; `Config.PERSON_FILES` refuses the boot for one who has a world and no file of her own.
- `geography_file` = ""
- `shared_dir` = "data/worlds" -- Where the worlds live, one directory each. A character with no world of her own has no path to anybody else's (Config.WORLD_KEYS).
- `household_file` = ""
- `character_file` = ""
- `local_events_file` = "data/local_events.json"
- `local_events_every_days` = 3
- `zeitgeist_file` = ""
- `zeitgeist_every_hours` = 4
- `zeitgeist_days` = 7
- `zeitgeist_keep` = 80
- `zeitgeist_max_per_fetch` = 10
- `zeitgeist_in_prompt` = 8
- `taste_file` = ""
- `home_file` = "" -- Where she is when she is not with him, for a character who has no world but has a home of her own. Read only by `schedule.own_day`, which plans her day from it and from nothing else -- no calendar, no weather, no cast, no feed of the present. Empty for anyone whose world is the live one.
- `places_file` = ""
- `event_lookahead_days` = 10
- `calendar_describe_limit` = 8
- `outing_words` = ["festival", "matsuri", "hanabi", "fireworks", "bon odori" -- The words that make a line a claim about a PUBLIC event -- one that either is on the calendar for that day or does not exist. A plan naming one of these on a date the calendar has nothing on is refused (`sim/ledger.py:outing_unbacked`). Blanked by `Config.WORLD_KEYS` for a character with no world, who has no calendar to check against and no public events to be wrong about.

**`reconcile`**

- `enabled` = True
- `log_keep` = 200

**`clock`**

- `mode` = "real"
- `sim_start` = ""
- `sim_speed` = 60.0

**`director`**

- `scene_source` = "model" -- Who writes the scene she is in. "model" asks the director role every tick: a second writer over the plan, which is what a character with a world round her needs, because her day is full of people and places the plan cannot know the state of. "plan" cuts the scene straight from the schedule block in code -- where she is, what she is doing, who is with her, whether she can be reached -- and makes no call at all. For a character with no world, whose whole day is written once from her own home file, the second writer was paying about $0.09 a day to paraphrase the block back (66 to 83 scenes a day, 25 of 25 settings written "indoors") and was the only thing in her process free to state a fact her day does not contain.
- `tick_minutes` = 20
- `tick_min_minutes` = 10
- `tick_max_minutes` = 90
- `coast_when_asleep` = True
- `sleep_keywords` = ["asleep", "sleeping", "lights out"]
- `recent_scenes_in_prompt` = 6
- `recent_days_in_prompt` = 2
- `max_open_threads` = 8

**`threads`**

- `pressure_after_days` = 0.75 -- small ongoing things as records: open / dormant / resolved A thread about him that she has not raised builds pressure until it becomes the thing she opens with. Without this every outlet for `unsaid` was private -- the diary and an X post -- so the pressure vented and the thread never reached him: one thread had resolved in three days, and "why he really went quiet for three months: still unasked" simply sat there.
- `pressure_per_day` = 26
- `pressure_unsaid_ref` = 45
- `pressure_per_unsaid` = 0.9
- `pressure_threshold` = 40
- `match_threshold` = 0.5
- `dormant_after_days` = 3
- `dormant_in_prompt` = 5
- `resolved_in_prompt` = 5

**`cast_defaults`**

- `closeness` = 30, "standing": 50, "tension": 10, "max_people": 30 -- meters for people the day compile adds to the cast

**`places`**


**`derive`**

- `enabled` = True -- His relationship meters, worked out from the message record instead of typed into cast.json. The same numbers have to serve a fresh install with no history and one carrying the whole May 2026 chat, which a hard-coded closeness of 62 cannot do.
- `gravity_enabled` = True -- The derived figure is not only a starting point: the live meters drift toward it, slowly, forever. Otherwise closeness is a ratchet that only the model can turn and only ever upward.
- `gravity_every_hours` = 6
- `gravity_closeness_per_day` = 2.0
- `gravity_standing_per_day` = 2.5
- `gravity_tension_per_day` = 3.0
- `cold_closeness` = 8, "cold_standing": 50, "cold_tension": 0 -- where a stranger starts
- `closeness_half_life_days` = 45 -- closeness: contact DAYS, faded by age, deeper when both of them spoke
- `closeness_days_ref` = 9.0 -- this many good recent days ~ 63% of the ceiling
- `closeness_ceiling` = 72
- `day_depth_ref` = 12 -- exchanged messages in a day for full depth
- `day_floor` = 0.35 -- a day where only one of them spoke still counts a little
- `facts_ref` = 30, "facts_ceiling": 22, "facts_max": 22 -- what she knows about him is closeness a silence cannot take back
- `known_floor` = 0.45, "known_half_life_days": 30 -- knowing him survives a gap, but not untouched
- `standing_span` = 40 -- standing: does he carry his half of it standing has three terms because the message ratio alone barely moves: who starts the day, and how long he leaves her waiting
- `standing_starts_span` = 34
- `standing_half_life_days` = 6 -- how she has been treated lately, not on average
- `standing_absent_from_days` = 2, "standing_absent_per_day": 4.5, "standing_absent_max": 26
- `standing_per_wait_hour` = 2.2, "standing_wait_max": 22
- `tension_per_quiet_day` = 6, "tension_gap_max": 30 -- tension: how long he has been quiet, and the worst silence they have had
- `scar_from_days` = 21, "scar_tension": 18, "scar_half_life_days": 10

**`social`**

- `enabled` = True -- X as the second app on her phone (read-only). She may open it when her phone is free, inside these hours, not more often than look_min_minutes, at most max_looks_per_day, if x_monitor pacing allows, with a probability that rises with boredom. What she noticed stays in her situation block for recent_hours.
- `hours_start` = "07:00"
- `hours_end` = "01:00"
- `retry_after_minutes` = 8 -- a failed look retries this soon, and does not count
- `look_min_minutes` = 90
- `max_looks_per_day` = 4
- `base_probability` = 0.35
- `boredom_weight` = 0.6
- `share_enabled` = True -- posts from her last looks she may send him as a link ([share: ID] in her reply becomes the URL), kept for share_hours
- `share_hours` = 24
- `share_cooldown_hours` = 6 -- after she sends him a post, no share is in front of her for this long
- `share_looks_per_day` = 20 -- A post she may send him is looked at BEFORE it is offered: every picture on it is described and the description rides the offer, and a post whose pictures could not be described is not offered at all. Those looks are outside the vision day-budget (`vision.max_calls_per_day`, spent by the scenery harvester by the time she scrolls) and capped here instead.
- `like_shared` = True -- a post she sent him is liked and reposted by the account (curation caps apply)
- `repost_shared` = True
- `repost_shared_p` = 0.35 -- The FALLBACK only: the probability the account reposts a post she sent him, rolled once per share, and used when her pick cannot run (`curation.share_pick` off, no judge, or her taste has nothing on that account yet). The log says which happened.
- `share_salience` = 4 -- the look's own "might say" line rides her reply prompts as the thing she wanted to show him (x_show_pending): from this salience, for this long, at most this many prompts. share_salience is the impulse path's bar without a mention. "look what i found" had stopped: the only path was the impulse at salience 4.
- `show_him_salience` = 3
- `show_him_hours` = 12
- `show_him_shows_max` = 8
- `show_him_declines` = 2 -- ...and this many showings of the same line in the one imperative slot with her answering something else, after which it is done
- `share_declines` = 2 -- the same for the posts on offer, put away for share_cooldown_hours
- `read_engagement` = True -- her own posts' likes, reposts and replies, read on the look and given to her -- the account was a monologue
- `engagement_posts` = 6
- `engagement_replies_max` = 2
- `engagement_craving_relief` = 4 -- being noticed answers the wanting-to-be-noticed, a little, and is a small good thing; the move is here rather than left to the state model, which reads the event and may charge nothing
- `engagement_pride` = 3 -- ...and moves pride up by this much per new thing a post drew
- `share_max_items` = 6
- `max_posts_per_read` = 25
- `recent_hours` = 2 -- how long what she saw on her last scroll stays in front of her: two hours, not six -- a thing seen on a timeline is on a person's mind for an hour or two, and at six the "emu person" was still in her situation block all evening after she had said it (2026-09-04)
- `peek_likes` = True -- at the end of a look she also glances at the account's Likes tab; likes not in her own action log are his, and she sees them
- `likes_scrolls` = 2
- `check_follows` = True -- and at the profile's following count; if it grew, the newest follows are read and attributed the same way
- `check_followers` = True -- and at the top of the followers list: anybody new who follows the account is followed back (curation.follow_back) and is from then on an account she cannot unfollow. The first read is a baseline and nobody on it counts as new.
- `her_actions_in_prompt` = 5 -- her own likes / follows / unfollows with reasons, in her prompt
- `his_likes_hours` = 24
- `discover_p` = 0.5 -- a search of her own in a look, from data/taste.json queries; and the trends tab for the zeitgeist filter
- `discover_scrolls` = 2
- `trends_p` = 0.5

**`share_pick`**

- `enabled` = True -- WHICH post from her scroll she sends him, decided by her rather than by code's text match against her own sentence (tomoe/share_pick.py, docs/x-account.md section 2.3, docs/tool-calling.md section 16). The one call in this project whose answer is a tool call that is acted on: `send_this(id)` makes that post the only one her reply prompt offers, `nothing` puts the thought away. Not the key of the same name under `curation`, which is a different decision: what the ACCOUNT does in public with a post she has just sent him.
- `max_attempts` = 2 -- An answer that did not validate -- a tool name that was not offered, an id that was not on the list, arguments that did not parse -- is a decision not taken: the three candidates code matched stand for that reply and the pick is tried again at her next free moment, this many times per thing she wants to show him. Two, because a third ask of the same question on the same list is a loop, and the offer it falls back to is what shipped before this existed.

**`lore`** -- What she happens to know, retrieved a few lines at a time (sim/lore.py). The persona dataset is 1,664 claims and the whole design question is how little of it to show her: `min_score` is what stops the bucket firing on every turn. A claim the era gate holds is never offered. `suppress_days` is 0 and locks nothing out: a record she has already been reminded of is reachable again the moment he names it, because a person asked twice about her own job answers twice. Above 0 it holds a used record for that many days, which is a repetition guard nobody asked for and which shut her career record on the one message that reached for it. `own_words_days` is the same hold applied to HER side of the window alone, which is where the repetition actually came from.

- `enabled` = False
- `file` = ""
- `era_gate` = False -- Whether a claim marked as coming from after the corpus ends is withheld. **OFF, and his decision.** It was catching the wrong thing: the mark had been put on the text naming a later year rather than on when the thing described began, so the record of her own radio show was shut -- it opens in 2003 and the same sentence traces it to 2016 -- along with her debut single and the roles she was already playing. A character who cannot reach her own programme reads as somebody with no career at all, which is what he saw in her replies.  That fault has since been fixed and the gate stays off, because he asked for it off. Thirteen claims now carry the part of themselves that had already happened (`gate.until_then`), so turning this on would withhold 165 claims and cut 13 back rather than shutting them: her programme, her debut single, her agency and the roles she was playing in 2002-2004 would stay reachable. With it off nothing is withheld and nothing is cut, and the mechanism that releases a work when he watches it (sim/watching_him.py) has nothing to release.
- `cue_exchanges` = 3 -- How many exchanges of the real conversation the retrieval is asked against. His newest message alone is too small a window: a subject arrives over several turns, and HER OWN WORDS are a cue -- she is often the one who raised the thing, so what she just said should be able to remind her of the rest of it.
- `standing_kinds` = ["register", "mechanism"] -- standing material -- her register, her mechanisms -- is true every minute and belongs in the bible, not in a bucket that competes with what she is doing
- `triggers_file` = "" -- The phrases that let a record be found, by record id, written by reading each one (yukarin/tools/triggers.py). Nothing else decides a match: comparing his message against the record's own text compares it against conversational speech, which is mostly grammar, and the question about a show was answered by a record about a witch on the strength of 「どんな」. A character with no list here can be reminded of nothing.
- `memory_file` = "" -- Her seeded memories as records (yukarin/week/memory_records.py), his call: a fact off the corpus is her record and is found by name, not rotated through the prompt as a memory. Their phrases are a second list, merged with the first. Empty for a character with none.
- `memory_triggers_file` = ""
- `min_score` = 0.5 -- How squarely the message has to name a record before she is reminded of it. A phrase carried by one record alone is worth 1.0 and one shared by three about 0.8, so below 1.0 a single naming is enough and the list of phrases is what holds the silence; above 1.0 the message has to name the same record twice.
- `max_lines` = 3
- `max_chars` = 900
- `max_chars_per_line` = 320
- `suppress_days` = 0.0
- `own_words_days` = 3.0 -- How long a record she has already been offered stops being reachable from HER OWN recent messages. His words reach it whatever this says. The cue is the last `cue_exchanges` exchanges and her own telling of an anecdote stays in that window for the next few turns, so without this the retrieval hands her back the story she just told, turn after turn: on 2026-09-02 the Umeda station anecdote came back four times in forty-five minutes, she told it three turns running, and the continuity editor threw away a drafted reply for repeating it. Set to 0 to let her own words reach a told record again immediately.
- `role_kinds` = ["role", "career", "work"] -- A part she played, in a work HE has just named, is not a line she can afford to lose. On 2026-09-03 he named a 2010 lead of hers, the record was retrieved at full score, and the whole block's character cap threw all three retrieved lines away on a crowded tick, so she denied the part. A retrieved line is ordinary and takes its chances against everything else she is carrying; a record of one of these kinds, named by HIM, at or above `pin_score`, is pinned and bypasses the budget. `pin_max` bounds it: pinned lines are the ones the gate cannot drop, so there is never more than one of them from here.
- `pin_score` = 1.0
- `pin_max` = 1

**`memory`**

- `enabled` = True -- how she forgets (sim/memory.py). A fact about him has a weight 1-5 (the compile sets it: passing detail 1, habit 3, name/work/birthday 5) and a half-life by weight; its score is weight * 2^(-age/half); below fact_min_score it is out of her prompt until a word in his message cues it (then it comes back and is refreshed). A fact learned again reinforces instead of duplicating. Cast situations older than cast_age_days are shown dated, older than cast_forget_days she has lost track of.
- `half_life_days` = [5, 14, 35, 120, 400]
- `fact_min_score` = 0.5
- `max_facts` = 40
- `cast_facts_max` = 6 -- what she knows about the people around her (cast_facts), same half-lives as the facts about him, shown per person
- `max_recalled` = 4
- `max_cosine_only` = 2 -- ...of which this many may be rows the WORDS never found, which came back on a cosine alone. Below max_recalled by design: a run of cosine-only rows used to take every slot and leave the word hit out, and every by-meaning row judged on 2026-09-04 was wrong.
- `duplicate_jaccard` = 0.6
- `cast_age_days` = 14
- `cast_forget_days` = 45

**`context`**

- `max_tokens` = 256000 -- The one budget over her prompt: target_tokens. The model's window is max_tokens (1M on both live models; this is not an output cap). Everything in the prompt rides whole -- the system half, what she carries, the situation block -- and the thread's verbatim window fits itself to what is left of the target after them, whole days at a midnight (sim/thread.py _window). Tokens are estimated at chars_per_token and the ratio is calibrated from the model's own prompt_tokens on every persona call (kv context_ratio). The sub-budgets that used to sit under this one (history, carried, situation, per-section warn sizes) went on 2026-09-04: measured prompts of 30-50k against a 64k target, and the gates they drove were cutting the situation block for the sake of a number here.
- `target_tokens` = 200000
- `chars_per_token` = 3.0

**`diet`**

- `enabled` = True -- her media diet (tomoe/diet.py): what she is into, from her X taste (accounts at or above account_min_score likes-minus-dislikes), the things the day compile saw her do for herself (kept keep entries, shown for things_days), her own likes and posts.
- `keep` = 120
- `things_days` = 14
- `account_min_score` = 2

**`money`**

- `enabled` = True -- her allowance (embodied/money.py): allowance_yen from mom on allowance_day each month; the director spends from it per scene (`spent`), never below zero; under broke_ratio of the allowance she is "nearly broke" in her tags, her situation and the schedule.
- `allowance_yen` = 5000
- `allowance_day` = 1
- `start_balance_yen` = 2800
- `broke_ratio` = 0.15
- `duplicate_minutes` = 45 -- the director does not see what the last scene bought and re-narrates it: the same purchase inside this many minutes is one purchase
- `log_keep` = 200

**`attachment`**

- `enabled` = True -- Attachment behaviour under threat (sim/attachment.py): protest (pursue, test, escalate) or deactivate (go cold, get busy, minimise), and the switch between them. Threat is read off the record, the strategy is drawn from her self-beliefs, the meters, the sentiments, the gauges and what the last episodes got her.
- `silence_from_hours` = 3.0 -- threat terms (sum, then scaled by attachment sentiment)
- `silence_full_hours` = 14.0
- `silence_floor` = 0.35 -- a silence at an hour he is never about still counts this much
- `w_silence` = 0.55
- `read_left_minutes` = 45
- `w_read_left` = 0.3
- `tension_from` = 30.0
- `w_tension` = 0.35
- `w_rupture` = 0.3
- `rupture_hers_factor` = 0.5 -- a break she caused threatens less than one he did
- `scar_days` = 14
- `w_scar` = 0.08
- `w_scars_cap` = 0.2
- `w_streak` = 0.12
- `w_streak_cap` = 0.3
- `attachment_floor` = 0.4 -- scale at zero attachment
- `engage_from` = 0.5 -- episode
- `engage_minutes` = 30 -- threat must hold this long; no flapping
- `release_below` = 0.3
- `release_fraction` = 0.6 -- or this far down from the episode's peak
- `max_hours` = 36.0
- `max_switches` = 3
- `keep` = 60
- `event_salience` = 2
- `memory_weight` = 3
- `base` = 0.3 -- selection: signed pulls, + protest / - deactivate
- `belief_floor` = 0.3 -- a belief with no evidence still pulls this fraction
- `strain_discount` = 0.7 -- a belief under full strain pulls this much less
- `belief_pulls` = {"wont_stay_quiet": 0.5, "alone_is_shameful": 0.3
- `  not_come_looking` = -0.5, "slip_ends_it": -0.35
- `  seen_undoes_me` = -0.4, "mask_holds": -0.3}
- `history_episodes` = 4
- `history_weight` = 0.35
- `history_half_life_days` = 10.0
- `w_closeness` = 0.4
- `w_tension_select` = 0.5
- `w_attachment` = 0.4
- `w_resentment` = 0.5
- `w_anxiety` = 0.6
- `w_anger` = 0.4
- `w_shame` = 0.7
- `w_sadness` = 0.5
- `protest_exhaust_hours` = 5.0 -- switching
- `protest_streak_stop` = 3
- `shame_switch` = 60.0
- `rebound_min_hours` = 4.0
- `rebound_from` = 62.0 -- longing or craving
- `rebound_p_base` = 0.05
- `rebound_p_per_hour` = 0.04
- `rebound_p_per_need` = 0.5
- `rebound_p_cap` = 0.6
- `sadness_on_give_up` = 8.0
- `shame_on_break` = 10.0
- `soft_cap` = 85.0
- `resentment_on_burnout` = 2.0
- `belief_tests` = { -- what an episode's end says about her beliefs: negative strains, positive confirms, by strategy and outcome
- `  protest` = {"resolved": {"not_come_looking": -6.0, "wont_stay_quiet"...
- `  failed` = {"not_come_looking": 5.0, "wont_stay_quiet": -3.0}}
- `  deactivate` = {"resolved": {"not_come_looking": -8.0, "mask_holds": 3.0}
- `  failed` = {"not_come_looking": 3.0, "mask_holds": 2.0}}
- `  rebound` = {"mask_holds": -5.0, "seen_undoes_me": -3.0}
- `impulse_protest` = 22.0 -- readers
- `impulse_deactivate` = 30.0
- `protest_extra_streak` = 2
- `withhold_deactivate` = 0.3
- `delay_protest` = 0.7
- `delay_deactivate` = 1.6

**`commitments`**

- `enabled` = True -- promises to named people that stake something outside her head (sim/commitments.py): yen put aside from her allowance, a window the schedule must keep, her standing with that person. The commit model names what she agreed to in an exchange; code binds it only with a cast counterparty and a real date inside the horizon; the compile settles it from the record alone (a scene with them in the window, a spend that names the thing) and never reverses it.
- `max_open` = 6 -- what she can be carrying at once -- this is the real bound on accumulation, checked when a promise binds
- `max_new_per_day` = 6 -- a rate limit on the CALL, not on how much she may promise. At 3 it truncated a real day: the FamilyMart trip, the yukata and the hand cream all bound in one 23:40 batch, and the library at 9 that she agreed to with Aya hours later was never even asked about -- so the plan never reached the 05:00 schedule and she went on talking to him about it. `max_open` keeps the ceiling; when this one bites it now says so in the log.
- `max_days_ahead` = 14
- `similar_threshold` = 0.4
- `attend_slack_minutes` = 90
- `buy_match` = 0.3
- `kept_regard` = 4 -- what keeping and breaking cost, applied once at settle
- `kept_standing` = 3
- `kept_pride` = 8
- `broken_regard` = 8
- `broken_irritation` = 15
- `broken_standing` = 8
- `broken_closeness` = 4
- `broken_guilt` = 18
- `broken_shame` = 10
- `cancel_guilt` = 5 -- calling it off herself, in words, before the day
- `cancel_irritation` = 5
- `warn_within_minutes` = 45 -- She came, so it is kept. She was late, so it is not the same as having been on time: `attend_slack_minutes` is 90, and turning up at half past twelve for a nine o'clock was settling with the same regard, the same pride and the same "she kept her word". Is she going to make it? The map already knows what a place costs to reach; nothing compared it to the clock, so she could be at the genkan with a nine o'clock promise and no idea. `warn_within_minutes` is how close to the wire it starts being on her mind at all.  She is not honest with herself about it: `optimism_minutes` is what she shaves off the real journey when she is already behind -- the belief that she can still make it if the lights go her way. Past `knows_late_minutes` of true shortfall the optimism stops working and **she knows**, which is the point: a lateness she walked into knowingly is hers, and one she never saw coming is the system being unfair to her.
- `optimism_minutes` = 8
- `knows_late_minutes` = 12
- `knew_guilt_factor` = 1.6 -- a lateness she saw coming and walked into costs more than one that happened to her
- `late_after_minutes` = 15
- `late_regard` = 1 -- instead of kept_regard
- `late_pride` = 2 -- instead of kept_pride
- `late_irritation` = 6 -- the person who was waiting
- `late_guilt` = 6
- `memory_weight_kept` = 2
- `memory_weight_broken` = 3
- `keep` = 80
- `him_enabled` = True -- promises to HIM (text_by / send / tell), named by the commit_him role from her own messages and settled off the message record
- `him_messages_shown` = 12
- `him_settle_seconds` = 90
- `him_max_new_per_day` = 5

**`exchange`**

- `hold_minutes` = 20 -- a beat landing while she has not yet answered the live exchange waits a pass, up to this many minutes past its own time
- `stub_stamp_p` = 0.5 -- a low-salience idle beat she gives no exchange gets a stamp-only reply from her own set at this probability (code, no model call)
- `chat_gap_marker_minutes` = 20 -- THE CHAT SO FAR carries each turn's stamp and a marker for a gap of this many minutes; 0 turns the markers off
- `enabled` = True -- her side of her social life (tomoe/exchange.py). Two authors now: the beat's own ja lands verbatim as the other side's opener, then her reply (cast_reply, seeing her state) and their continuation (cast_turn, seeing ONLY what that person could know -- never her interior) alternate. One author wrote both sides before, so nobody could surprise anybody and her friends answered her feelings instead of her words.
- `kinds` = ["line", "group", "call", "video", "in_person"]
- `min_salience` = 2
- `max_per_day` = 12 -- every kind of exchange shares this, so the group used to compete with LINE and the kitchen for the same eight slots
- `late_reserved` = 3 -- ...and a separate allowance for the late stretch, because the day's budget is SPENT by then: on the days that hit the cap the eighth exchange starts between 21:13 and 23:12, so a late beat would land as an opener nobody ever answers -- and `Health._chat_alive` counts TURNS, so the chat meant to keep her up would still read as zero. These slots are for late group beats only and are not usable by day.
- `keep` = 120
- `in_prompt` = 20 -- exchanges of today + yesterday shown whole (two days run to ~12)
- `group_full_recent` = 2 -- ...except the group, which at the new volume is a couple of hundred messages a day: the newest `group_full_recent` group conversations go in verbatim and the older ones as the gist they already carry. Two days of group chat whole is ~23k characters against a `chat` section budgeted at 1,000 tokens, and most of it is about nothing on purpose.
- `pace_night` = 2.4 -- 01:00-06:00
- `pace_late` = 1.6 -- 22:00-01:00
- `pace_busy` = 2.2 -- availability 0.15 (class, a fixture)
- `pace_glance` = 1.5 -- availability 0.5
- `pace_photo_seconds` = [20, 70]
- `away_p` = 0.22 -- Nobody sits chained to the phone. Every gap between messages was `prev_len/6 + U(20,150) + n/3` -- bounded about 29-198 seconds by construction, so a three-hour chat came out as a continuous two-minute drip with no tail at all: mean 1.9 min, median 1.9, max 3.2 over thousands of samples. Real ones go quiet because somebody got up. `away_p` is the chance a gap is an absence instead of a pause, and the reasons carry their own lengths (`tomoe/exchange.py` AWAY), weighted so the late-night ones are the sleepy kind.
- `him_messages_shown` = 10 -- How much of her chat with him her own side of an exchange can see. It was four messages truncated to 80 characters, a literal from when an exchange was six turns long: her friends ask her about him and she was answering from a keyhole.
- `him_message_chars` = 160
- `away_drag` = 0.94 -- An absence is not free. Every one of them multiplies the chance the conversation keeps going: a chat that has already stopped twice for somebody's dinner and somebody's bath is thinning out, and it should die of that rather than run its rounds regardless.
- `sleep_wake_hm` = "07:10" -- And one reason ends a night rather than pausing it. Somebody who fell asleep on the chat is out until the morning -- no turns, no beats, out of the speaker pool -- and when everybody who was in it has gone, the chat is over. `sleep_wake_hm` is her clock, which is theirs; the jitter is minutes either side so they do not all wake at the same minute.
- `sleep_wake_jitter_min` = 40
- `interrupt_delay_seconds` = 120
- `busy_window_minutes` = 12 -- Being mid-conversation with him is a reason to make the girls wait a couple of minutes. It is NOT a reason to go silent for seven hours, which is what happened: `_busy_with_him` was true from the moment his message landed until she answered it, and on 2026-08-27 a message that arrived while she was asleep froze every exchange for 453 minutes -- Kaito's beat died in her doorway and Aya's was dying while she sat across the table from her at the library. Only a RECENT message means she is actually with him.
- `busy_max_pushbacks` = 4 -- and never for ever: after this many deferrals the person in front of her gets an answer whatever her phone is doing
- `max_live_minutes` = 45
- `max_rounds` = 2 -- how many times she may answer within one exchange, and the chance the other person comes back after each of her replies
- `group_max_rounds` = 12 -- A group chat is not a bounded errand: it is a venue that runs for hours. At `continue_p` 0.6 and 4 rounds the expected length was 2.2 rounds -- about ten messages -- and five of those a day is fifty messages between four girls, which is not a chat. The one-to-one numbers stay where they are; only the group is opened up.
- `group_continue_p` = 0.87
- `group_without_her` = 6 -- She is not the chat. Her silence used to end it -- one message from Rena, no answer, the exchange closed and three girls stopped talking to each other. On 2026-08-28 four of the seven group conversations were one message long for exactly that reason. The others carry on without her for this many passes, and she can walk back into what they said; only then is it over.
- `group_without_her_min` = 2 -- ...and at least this many of them have to be awake for it to be a chat rather than one girl talking to herself. Reached now whenever she cannot take her turn -- asleep, at school, at the table -- and not only when she reads it and says nothing, which was the one case the first version covered and the rarest of the three.
- `alone_beats_per_day` = 3 -- ...and the room does not need her to have been in it at all. A group beat the day's phone budget or the late reserve refuses her was filed as one unanswered line and that was the end of it: 17 of the 47 group conversations in a week are exactly that row, and the other two girls were in the chat the whole time. Now the beat opens a conversation with her out of it from the first turn, the others carry it under the same `group_without_her` passes, and she reads it when her phone comes back. Capped per day, because each round of one is one to three model calls nobody was owed. 0 turns it off.
- `self_open_per_day` = 1 -- She may start one herself. Every beat is somebody reaching HER -- the planner is refused any beat written as her (`tomoe/cast.py`) and that stays -- so in the whole record she opens none of the 47 group conversations, while three girls open all of them. This is the other door: at most this many a day, decided the way her urge to text him is decided (`sim/impulse.py`: a hard gate, then a score, then a soft roll), and written in her own voice through the room she already talks to them in. 0 disables it.
- `self_open_quiet_minutes` = 95 -- how quiet the room has to have been before she is the one to break it, in minutes; and how close a friend's own beat may be before she leaves it to them, because two openers a minute apart is not a girl starting a conversation, it is a collision.
- `self_open_clear_minutes` = 30
- `self_open_threshold` = 26.0 -- the score her own state has to make for it, on the same scale the impulse uses: loneliness, boredom and being left out push, and having just been in the chat does not.
- `self_open_weights` = {"loneliness": 0.22, "boredom": 0.16
- `  validation_craving` = 0.14, "belonging_low": 0.30}
- `no_repeat_own_turns` = 6 -- A speaker may not say again what they have already said in this conversation. Aya sent the same three-bubble block four times in twenty minutes on 2026-08-28: the prompt asked her not to and nothing checked. Compared against that speaker's OWN last turns.
- `repeat_min_chars` = 12 -- THE SAME THING SAID AGAIN, in the three shapes the old test could not see. `no_repeat_own_turns` above compares whole messages by one speaker; the loops in the record were a sentence repeated inside a longer message (07:17 and 07:21 on 2026-09-07: the messages 57% alike, the sentence in them identical) and an echo of SOMEBODY ELSE two minutes later (21:44 and 21:46 on 2026-09-06). A message is split on sentence enders; a sentence of at least `repeat_min_chars` characters that anybody in the room has said inside the last `repeat_window_turns` turns is a repeat, and a message that is more than half repeats is dropped and logged. A short deliberate echo is never touched, and nothing is ever rewritten or asked for again.
- `repeat_window_turns` = 20
- `moves_shown` = 8 -- WHAT THE CONVERSATION HAS ALREADY TRIED. Every call that writes a turn returns a one-line gist and the record kept only the last one, so nothing could tell a call that a move had been made: one girl played "fine, I will ask, but I am still the one who decides" at 07:19 and again at 07:23 in different words. The room keeps the list, both writers are shown this many of its newest entries, and the ask to a member who writes her own turns carries it.
- `stale_drag` = 0.5 -- A ROUND THAT ADDED NOTHING. One where the repeat filter dropped a bubble, or where somebody's move was the move they made last time. Each one multiplies the chance the room continues; two in a row and it is over. At 0.87 a round with nothing to weigh it the group ran its twelve rounds whether or not anybody had anything to say.
- `group_bubble_chars` = 90 -- A GROUP MESSAGE IS ONE THOUGHT typed with a thumb. This is a LOG threshold and nothing else: a bubble longer than this is counted on the room's record and named in the log, never cut, never asked for again and never rewritten. Her 07:30 was three clauses of interior at half past seven on the way to school, which is a fact about the prompt and not something to paper over.
- `no_repeat_hours` = 12 -- ...and how far back "already said" reaches, in hours of her clock. The check could see the live conversation only, so a line came back word for word in the NEXT one: Aya's line about the notebook went out at 07:21 on 2026-09-02 and again at 13:14, with the earlier copy sitting in the prompt that wrote the second. 0 turns the wider window off and leaves the live conversation as the whole of it.
- `reopen_after_nothing_minutes` = 120 -- SHE WENT TO SOMEBODY AND HAD NOTHING TO SAY. The room logged it and nothing acted on it, so the chooser was offered the same person again on the next pass and took her: one character opened a chat with the same friend four times in an evening, and the filter deleted every bubble. This many minutes of her clock and that person is off the list of people she may write to; the chooser is told so in words, with the time she comes back. 0 turns the gate off.
- `group_max_live_minutes` = 180
- `continue_p` = 0.6
- `group_jump_in_p` = 0.7 -- a group round is multi-agent: each member decides to jump in on their own draw (base chance scaled by their attention), each with their own call and their own edges, capped per round
- `group_max_speakers` = 3
- `agent_turn_deadline_seconds` = 180 -- How long a room waits for a turn from somebody who runs as her own process before going on without her (sim/rooms.py: a cast row carrying `agent`). Her process has to read her mailbox, build a prompt and be answered by a model, so this is seconds rather than one pass; past it the room says so in the log and never asks her again in that conversation, because the one thing it must not do is write the turn for her.
- `agent_beat_deadline_seconds` = 600 -- and how long a beat waits. Longer, because a beat is the thing she OPENS with: nothing is live, nobody is sitting in front of a chat, and a beat that arrives late is still the day going as planned. Past it the beat is dropped and the log says so: a plan is not a promise that somebody spoke.
- `agent_context_turns` = 12 -- how many of a room's turns go out with an ask. She is sent what she has not seen since she joined, capped here.
- `reply_slow_minutes` = 25 -- 「メッセージ来てたし 返事早くしないと 友達じゃなくなっちゃう」 -- her own words, with a stated consequence, and nothing charged her for it. A slow answer to a friend costs standing with them; no answer at all costs more. Small numbers: this is a slow pressure, not an event.
- `reply_slow_standing` = 1.5
- `reply_miss_standing` = 3.0
- `reply_slow_belonging` = 2.0
- `behind_step` = 1.0 -- 「休んだら みんなの話についていけなくなるもん。その1日が命とりなの」 -- missing the chat compounds: each group conversation she is not in raises `behind`, taking part works it off, and the cost of the NEXT miss is scaled by it. That is the compounding, and it is why she over-attends.
- `behind_decay` = 1.0
- `behind_max` = 6.0
- `behind_compound` = 0.35
- `slip_anger_from` = 50 -- when a slip out of the register she performs is the TRUE reading and the checker is told not to flag it (voicecheck `context` / a rule's `skip_when`). Which register that is belongs to the character's own rule file and is named nowhere here. Her sheet says the mask slips when she is tired, angry or cornered; the source says the plainer thing, that it comes off for the person she has stopped performing for. `slip_energy_below` was 30, which 337 recorded states never reached (her floor is 45); 54 is her measured p10, so "tired" is the tiredest tenth of her nights rather than a state she never has.
- `slip_energy_below` = 54
- `slip_tension_from` = 50
- `slip_with_roles` = ["confidante"] -- by role, so it survives a recast: alone with the confidante the mask is down and the dialect is not a mistake. Never in a group.

**`npc`** -- Everybody who is not the cast. She rode a packed train with nobody on it, stood in a konbini with nobody behind the till, and spent a school day in a building holding one class of girls none of whom were ever in the room. Who is plausibly somewhere comes from that place's `kind` in `data/places.json`; code picks the slot, the model writes the person. They never enter `relationships`, the graph or `cast_chat` -- an encounter leaves an `events` row and nothing else.

- `enabled` = True
- `seed` = "scail"
- `max_per_day` = 4 -- at most this many a day, and never two in a row inside `gap_minutes`
- `gap_minutes` = 45
- `check_minutes` = 15 -- the roll happens on a cadence, not on every pass of the loop
- `place_p` = { -- the chance per check, by the place's kind. A konbini is a transaction and nearly always has one; a park is mostly empty of anybody who would speak to her.
- `  konbini` = 0.55, "school": 0.30, "commute": 0.16, "station": 0.16
- `  shop` = 0.22, "library": 0.14, "shotengai": 0.16, "museum": 0.14
- `  city` = 0.12, "park": 0.08, "shrine": 0.10, "home": 0.0
- `place_p_default` = 0.08
- `alone_multiplier` = 1.0 -- somebody on her own is who gets spoken to; three girls together are a wall
- `with_people_multiplier` = 0.45
- `known_face_p` = 0.55 -- how often the person is one she has seen at this place before. This is what gives the konbini a regular clerk instead of a new stranger every single visit.
- `name_after` = 4 -- a name is learned where you would learn one: at school, or off somebody met this many times
- `promote_after` = 0 -- a face met this often is named by `/npc` as a cast candidate; 0 is never. You do not remember the person on the till, and a stranger who keeps turning up does not change her life -- the value of the other people is that they are THERE (`around`), not that they matter.
- `keep` = 60
- `moments_keep` = 120

**`social_graph`**

- `enabled` = True -- tomoe/social_graph.py: what the people around her actually think, of her and of each other, as edges (view + regard + irritation) updated once a day at the compile from what each person WITNESSED. Ground truth her guesses are settled against; readers: cast turns, the day planner, the spiral settle, the witnessed-goal price, the showrunner, the ick, /graph and the app's backstage. The edges belong to the WORLD, so the section is assigned to `world_owner` in Config.REQUIRES: a character in a world somebody else keeps has it off, seeds and updates nothing, and every one of those readers takes the owner's compiled edges out of the world file through the same object.
- `max_updates_per_day` = 5
- `regard_step` = 8 -- clamps on one day's movement: irritation is fast, regard is earned
- `irritation_step` = 15
- `irritation_half_life_days` = 5
- `view_max_chars` = 220
- `in_prompt_edges` = 6 -- how many of a speaker's edges reach their cast_turn prompt

**`episodes`** -- her past as cards (sim/cards.py): code cuts a day into episodes (his chat at silences of delivery.gap_marker_hours, each exchange with her people whole); one call a day at the compile writes a card per episode -- the shape in her language, one to three lines quoted exactly (an anchor that is not in the record is dropped), what it left her feeling. Never faded, never rewritten; a day compiled again replaces its cards. The thread shows the cards of the days past its verbatim window at their time; recall searches them by words and by meaning

- `enabled` = True
- `anchors_max` = 3
- `max_lines_per_episode` = 160 -- lines of one episode handed to the writer; a 200-line group night is cut at this and the card says so in its count
- `merge_gap_minutes` = 120 -- two exchanges in the same room this close are one conversation with a pause in it; an episode still under min_lines after merging (a sticker, a photo, one unanswered line) goes into the day's one odds-and-ends card. Before this: 20 to 27 cards a day
- `min_lines` = 3
- `anchors_days` = 3 -- the thread shows a card's exact lines and feeling for this many days back, the shape alone beyond; the words stay in the card

**`embed`** -- sentence embeddings for retrieval (sim/embed.py), local, on the GPU, vectors kept in the save. A cosine under min_cos counts for nothing (unrelated Japanese sentences sit near 0.7 on e5); above it, 0..1 times weight, the size of one strong word overlap. Off, every reader searches by words alone

- `enabled` = True
- `model` = "intfloat/multilingual-e5-small"
- `batch_size` = 32
- `min_cos` = 0.82 -- measured on her cards: unrelated pairs median 0.78-0.81, 90th percentile ~0.83, a true hit 0.85-0.90 in either language. Nothing under min_cos; weight at top_cos and above. Scaled so a 0.88 hit ranks beside a good word match (~2) and the floor is noise (~0.4)
- `top_cos` = 0.90
- `cos_by_pool` = {"fact": [0.80, 0.87], "selfmem": [0.80, 0.87]} -- a pool of ONE-LINE rows sits on a different scale: with nothing but a sentence to go on, everything is closer to everything, so both ends come down. Measured over eight Japanese cues against her 157 English facts and five English cues against her 270 Japanese memories: the right answer 0.800-0.881, the 90th percentile of the rest 0.745-0.806. So the signal is real and thin, which is why it is ADDED to the word score rather than replacing it and why the fade score still decides what a row is worth. [floor, top] per pool; a pool not named here is on min_cos/top_cos
- `weight` = 3.0
- `calibrate` = True -- ...and those two hand-set numbers are only right for the save they were measured on. Re-measured 2026-09-04 on both saves with 30 real cues each: a Japanese cue against Japanese rows sits about 0.06 higher than an English cue against English rows, so 0.80 left 9% of the first character's facts above the floor and 100% of the second character's own memories and episode cards above it -- her whole pool counted as a hit on every cue. So each pool measures its own floor once per boot (`sim/embed._calibrate`) from real cues out of this save's record against this pool's stored vectors, and puts it `calibrate_margin` above the `calibrate_pct`th percentile. The measurement wants the percentile higher -- the true top hit for a cue sits at the 99th percentile of the rest on this model -- but 90 is where it starts. False, or a pool with fewer than `calibrate_min_rows` rows or a save with fewer than `calibrate_min_cues` messages, and the numbers above stand
- `calibrate_pct` = 90
- `calibrate_margin` = 0.01
- `calibrate_sample` = 400
- `calibrate_cues` = 40
- `calibrate_min_rows` = 5
- `calibrate_min_cues` = 12
- `center_rows` = True -- Half the cosine belongs to the ROW rather than to the cue. Averaged over 30 unrelated cues, the most central rows of the first character's fact pool sit at 0.804 against a pool mean of 0.769 -- a spread of 0.035 where the whole band from floor to full weight is 0.07 -- and one row was the top hit for 5 of 30 cues that had nothing in common. That is what put the same folder of his in front of her for a festival group chat and for a hair clip. So each row's own mean over the calibration cues is subtracted before scoring: a row that is close to everything gains nothing by it, and a row that is close to THIS cue keeps its lead. Measured in the same pass as the floor, so it costs nothing extra; False restores the raw cosine.
- `require_shared_word` = True -- A row that arrives on a cosine ALONE, with no word in common with the moment, must share at least one content word with the cue. Every one of the six by-meaning rows judged wrong on 2026-09-04 shared no word at all with the cue that brought it back, and this would have stopped all six. It is a weaker test than the word search's own (which wants one Latin word of four characters, or two keys for her own memories), so a row the words nearly found still gets in on its meaning.

**`recall`**

- `enabled` = True -- remembering on cue (sim/recall.py): his message points at the past (trigger_regex) or strongly matches the compiled record (score without a cue); the record is searched by words, the best excerpts go to one call that writes what she remembers with its clarity; in a thread during her read delay.
- `trigger_regex` = "remember|last time|you said|you told|back in|that time|w...
- `min_score_without_cue` = 1.6
- `max_excerpts` = 5
- `max_cosine_only` = 2 -- How many of those excerpts may be rows the WORDS never found, which joined on a cosine alone. On 2026-09-04 a cosine-only row took third place of five and reached her mouth ("I know you looked at a meme post on a forum, but I can't place when"). Below `max_excerpts`, so the words always keep some room.
- `events_min_salience` = 2 -- The machinery's own record of her day (`events`) is searched too, by words and by meaning: some things are in no other store, and her one encounter with a title she was later asked about sat in this table for sixteen days while the retrieval read past it. Salience is the filter and the weight: an event fades on her own life's half-lives (`self_memory.half_life_days`) from `events_weight`, because a thing that happened to her is not a fact about somebody else. `events_scan` bounds both the search and the vector pool.
- `events_scan` = 1200
- `events_weight` = 0.8
- `cross_script` = True -- A cue he typed in English or romaji, crossed to the Japanese the record is written in: a thing she knows by name and his own list both hold a title's two spellings, and what is left when neither does is the kana the romaji itself transliterates to. Local, no fetch -- this runs on the loop thread.
- `require_grounding` = True -- What the answer has to cite, and what the code checks. The role must name the excerpt the memory comes from, and a memory that says one of them SAID something about a word of his message that is in none of the excerpts is not written (`[recall] not grounded: ...`). `subject_common_share` is which of his words name a thing at all: a word in more than 2 per cent of her rows is grammar.
- `subject_common_share` = 0.02
- `max_per_day` = 20
- `wait_seconds` = 25
- `keep` = 60

**`intent`**

- `enabled` = True -- typed initiation (sim/intent.py): when the impulse fires, one call names the urge (share / ask / complain / check_on / tease / continue / nothing) before the persona writes.
- `shame_from` = 45 -- The feeling deciding this, named for the call. `confront` and `make_up` have been valid kinds since this was written and nothing ever pointed at them, so the model reached for them roughly never. Ordered by which wins when several are up: shame first, because it is the one that stops her.
- `anger_from` = 40
- `guilt_from` = 50
- `sadness_from` = 45
- `pride_from` = 60

**`experience`**

- `enabled` = True -- what she makes of what she watches / reads / listens to / plays (sim/outlook.py): a scene whose activity matches trigger_regex gets one call; the result joins her media diet.
- `trigger_regex` = "watch|episode|\\banime\\b|manga|reading|novel|listening|...
- `object_regex` = "\\banime\\b|episode|\\bep\\s?\\d|manga|\\bnovel\\b|\\bbo... -- the cue above is cheap and catches the verb; this is the OBJECT, and the activity must carry one. Without it "reading" matched "reading his reply" and "switch" matched "switching", so 48 of the 61 eligible scenes over five days were him, the chat, the steam in the bath or her dad talking -- and since only `max_per_day` fire, the slot was usually spent on his messages before a watching scene ever came up. A title on her watchlist counts as an object too, so a scene that names the show without saying "episode" still qualifies.
- `watch_regex` = "watch|episode|\\banime\\b|drama|movie|film|\\bep\\s?\\d" -- of those, the ones that are watching an episode: her watchlist is consulted and a real あらすじ fetched (music / games / manga are not)
- `max_per_day` = 3
- `min_gap_minutes` = 120

**`recap`**

- `enabled` = True -- grounded watching (sim/recap.py): a real Japanese あらすじ for the episode she is on, fetched once and cached in the `recaps` table, so the experience call reacts to what actually happened. Selenium, a throwaway Chrome profile. No model call.
- `headless` = True -- no window (the fetch happens while she is mid-scene and a Chrome opening itself is not part of that). Off to watch a fetch when a site starts giving the wrong text; `/headless off` does it live.
- `query_template` = "{title} アニメ 第{ep}話 あらすじ 感想"
- `series_suffix` = "全話 あらすじ ネタバレ"
- `overview_query` = "{title} アニメ あらすじ 登場人物 どんな話" -- when HE names a series: a fuller Japanese premise/overview
- `seiyuu_query` = "{name} 声優 プロフィール 出演"
- `work_query` = "{title} ゲーム あらすじ 概要 登場人物"
- `search_engines` = ["https://www.bing.com/search?q={q}&setlang=ja"
- `candidates_max` = 4
- `blocked_hosts` = ["youtube.com", "amazon.co", "netflix.com", "twitter.com"...
- `min_chars` = 200
- `max_chars` = 2200
- `page_timeout_seconds` = 30
- `poll_seconds` = 1.3
- `poll_max` = 12
- `page_min_html` = 25000
- `search_min_html` = 15000
- `candidates_target` = 4 -- HOW MANY CANDIDATES the judge gets, and how short a page has to be before it is the anchor rather than a candidate. The official あらすじ page is 200-250 characters, never wrong and never complete: the right thing to check a summary against and the wrong thing to summarise, so it is kept and marked rather than discarded.
- `anchor_max_chars` = 300
- `anchor_min_chars` = 200 -- and below this a slice is the page's own heading and not even an anchor -- a title bar with an advertising strip came to 172, and a site that had not finished loading gave 37. The official blurb, which is what an anchor is for, measures 200 to 250.
- `index_entry_gap` = 40 -- An episode marker with another episode's marker this close behind it is an index entry -- a nav strip, a season page's list of titles -- and not the heading of this episode's section. A page for one episode of a 2010 show carries all thirteen titles at the top, and slicing at the first marker gave thirteen characters.
- `slice_min_sentences` = 3 -- What a page taken on the strength of its HEADING has to have before it counts as an account of the episode: this many sentences, and this much of a body. The heading is what recovers a 感想 post whose body carries no number at all, and it is also what a shop's listing page for the same episode gets exactly right -- the video shop's page for エグザンプル ep6 is headed `第6話` and is 285 characters of prices and service copy, where the four blog posts recovered this way run 2,200 to 9,600. A listing has no sentences in it whatever its length, and no page of prices is long. Either at 0 turns that half of the test off.
- `slice_min_chars` = 600
- `poll_settle` = 2 -- The page-source poll stops when the source has not grown for this many polls. `page_min_html` was standing in for "it has finished arriving", and a 9 KB official episode page can never reach it, so a small good page cost the whole 15.6-second budget every time. A page that has not STARTED arriving has also stopped growing, so the break needs a few polls behind it and a page big enough to be a page.
- `poll_min` = 4
- `poll_min_html` = 8000
- `fetch_workers` = 4 -- the keyless sources, fetched in parallel with each other and with the browser
- `http_timeout_seconds` = 20
- `list_episode_url` = "https://myanimelist.net/anime/{id}/_/episode/{ep}"
- `list_episode_index_url` = "https://myanimelist.net/anime/{id}/_/episode"
- `wikipedia_api` = "https://en.wikipedia.org/w/api.php"
- `wikipedia_list_title` = "List of {title} episodes"
- `archive_dir` = "data/recaps" -- where every fetched page, subtitle file, transcript, digest and verdict is written, with a manifest per episode saying what each file is and where it came from. Shared between characters on purpose: it is a cache of public pages about television episodes, keyed by show and episode, with nobody's life in it (tools/isolation.py names it as the machine's).
- `archive_enabled` = True
- `subtitles_enabled` = True -- THE EPISODE'S OWN SUBTITLE FILE, downloaded keyless from a fan archive and its mirror, parsed to lines with timestamps and (on a caption rip) speakers, and turned into an account of the scenes in order by the `transcript_digest` role. That account is the anchor the judge measures web candidates against, and the digest when no web candidate survives. Never her line: twenty-four minutes is 300-500 lines of speech with no stage directions.
- `subtitles_user_agent` = "scail-recap/1.0"
- `subtitles_mirror_tree` = "https://api.github.com/repos/Ajatt-Tools/kitsunekko-mirr...
- `subtitles_mirror_raw` = "https://raw.githubusercontent.com/Ajatt-Tools/kitsunekko...
- `subtitles_archive_index` = "https://jimaku.cc/"
- `subtitles_archive_base` = "https://jimaku.cc"
- `subtitles_min_ja_share` = 0.6 -- a file in a folder marked Japanese is not always a Japanese transcript: one show's files are a Chinese group's listening script, and one of those is dual-language with the Japanese layer 309 lines of 723. The share of lines carrying Japanese script is measured on the file rather than assumed from where it sat.
- `subtitles_min_lines` = 40
- `subtitles_try_files` = 3
- `subtitles_retry_hours` = 24 -- one attempt per show and episode per day, hit or miss, so a show with no file is not looked for on every tick
- `transcript_prompt_chars` = 90000 -- HOW MUCH OF THE SUBTITLE FILE THE ACCOUNT ROLE SEES. It is the model's window that bounds this and not a number chosen to be safe: a 24-minute episode renders to 15,000-25,000 characters of `[mm:ss] speaker: line` and a 24,000 ceiling was cutting the middle out of an ordinary episode -- and the middle is where a running gag is established. At 90,000 a feature-length file still fits.
- `transcript_account_chars` = 3000 -- and the account the transcript role writes, which is the anchor the web candidates are held against. It was 1,600 characters, which is about the length of a synopsis, so the anchor could not carry more of the episode than the pages it was checking.
- `account_enabled` = True -- ---- THE EPISODE ACCOUNT (sim/episode_account.py) ---- Everything read about one episode -- every surviving digest, the subtitle file's own account of the scenes, the official blurb -- merged by the `episode_account` role into ONE record: every scene in order with how it comes out, the named parts, the running gags, the lines worth remembering, what the episode points at, and what no source settled. Written once for the MACHINE and read by every character without fetching anything.  It exists because the winner of the judge is one page. On 2026-09-08 an episode of a shop comedy reached the third character as 600 characters of one fan's post: the B-part's premise survived and every individual joke in it did not, which is the difference between having read a synopsis and having watched the episode.
- `account_candidates` = 6 -- HOW MANY PAGES ARE READ FOR ONE, and it is deliberately more than the judge needs. Four candidates settle which page to trust; a background reference or a running gag is typically named by one 感想 post out of six and by none of the official sources, so the account's caller widens both the "keep" and the "try" caps.
- `account_tried_max` = 8
- `account_page_chars` = 8000 -- HOW MUCH OF EACH PAGE THE MERGE READS. `max_chars` (2,200) was chosen for what is STORED as the winning synopsis. The account reads the pages themselves rather than their digests -- a digest is 200 to 500 characters made out of a 2,200-character post, and what it drops first is the individual jokes, which is the whole point -- and a 感想 post puts its best detail two thirds of the way down.
- `account_max_chars` = 4000 -- the ceiling on the stored account. Not a budget -- the account is never cut to fit a prompt, which is the thing it replaces -- but a bound on one row.
- `account_min_chars` = 900 -- WHAT COUNTS AS COMPLETE, and it is measured on what went in rather than on how it reads. `watched` needs the length, the scenes, and either the episode's own dialogue behind it or two independent readers agreeing: one blogger's misreading can produce a long confident account, and that is the case this word exists to name. A complete account is never rebuilt and never re-fetched.
- `account_min_scenes` = 3
- `account_thin_chars` = 400 -- and the floor under which it is `thin` rather than `read-up`
- `account_max_tries` = 3 -- How many readings-up ONE EPISODE gets before an account that is still not at watched level is left alone -- counted for the machine, on the account itself, not per character. Each of the three processes allowed herself `sensors.retrievals_max_retries` attempts at the same episode, so one episode cost up to nine readings and the last of them was no better than the third. 0 for no limit.
- `episodes_report_dir` = "reports/episodes" -- THE EXTERNAL OBSERVER'S VIEW: one Markdown page per episode with the account, the scenes, the sources and their URLs, and an index over all of them. The MACHINE's, like the archive and the per-play dossiers beside it (`tools/isolation.py`): an episode of a television programme is the same episode whoever watched it.
- `transcripts_report` = "reports/transcripts.md" -- WHERE AN EPISODE'S OWN DIALOGUE CAME FROM, readably. The answers were only in SQL -- one row per (show, episode) in each save's `transcripts` table -- and the reasons were scattered across a thousand session logs, so there was nowhere to look. Append-only, one line per attempt that resolved, the machine's like the episode pages (`machine/episode_reports.py`, `tools/isolation.py`).
- `local_subtitles_enabled` = True -- WHERE THE EPISODE'S OWN WORDS COME FROM, in the order they are tried. The fetch used to be the two internet archives and nothing else, and it missed three of five episodes in a fortnight -- not on a bad match, but because neither archive carries those works at all under any name. So the path now starts on his own disk and ends in a transcription, and cannot come away with nothing.  1. THE FILE ALREADY BESIDE HIS VIDEO. Free, instant, and it was being ignored: a Japanese subtitle of 339 lines sits next to an episode he played, and the fetcher was asking the internet for it. The stem is the video's; the suffixes below are the forms a release names a language track with.
- `local_subtitle_suffixes` = ["", ".ja", ".jp", ".jpn", ".jpn-ja", ".japanese"
- `subtitles_local_mirror` = "data/subtitles_mirror/kitsunekko" -- 2. THE ARCHIVE MIRROR, ON THIS MACHINE. The repository is 3.71 GB with its history, so it is cloned shallow, one branch, sparse to the three folders the lookup walks. Reading it off the disk needs no network at all, and the API tree fetch it replaces is rate-limited and was the first network hop of every miss. The API stays as the fallback for a machine that has not cloned it. The directory is the MACHINE's, like the episode archive beside it: it is an archive of television, with nobody's life in it, and one copy serves both characters (`tools/isolation.py`).
- `subtitles_local_refresh_hours` = 24
- `animetosho_enabled` = False -- 4. A release index that answers about torrents rather than about subtitles. Its JSON feed works and every field is about the torrent; a release page carries no extracted subtitle attachment at all, so getting a subtitle from it means fetching the release, which this project does not do. Wired and off, so the decision is in the config rather than only in a report.
- `animetosho_json` = "https://feed.animetosho.org/json"
- `opensubtitles_enabled` = False -- 5. A subtitle service that needs an account. Off while the key is blank, which it is.
- `opensubtitles_api` = "https://api.opensubtitles.com/api/v1"
- `opensubtitles_key` = ""
- `whisper_enabled` = True -- 6. AND WHEN NOTHING CAN BE FETCHED, THE EPISODE IS TRANSCRIBED from the file he played. His own install does the work (`Faster-Whisper-XXL Pro`), driven with the settings from his own `processor.bat` so that his batch file stays the reference and this follows it. The arguments are his, in his order; the exe takes the video and writes the .srt itself.
- `whisper_exe` = ""
- `whisper_args` = ("--language Japanese --task transcribe --model large "
- `whisper_max_per_day` = 4 -- A transcription is minutes of the GPU, and the GPU is shared with the reaction-image tool. So: never on the reply path or the poll, a few a day, nothing feature-length, and only once he has clearly settled into the episode rather than sampled it -- ten minutes in is that point, and it is a different question from whether the episode counts as watched (`min_minutes_in`, three minutes), which the fetching steps above are gated on and this one is not.
- `whisper_max_minutes` = 40
- `whisper_min_watched_minutes` = 0 -- HOW LONG HE MUST HAVE SAT THROUGH IT, and 0 means the SAME number that decided the play was a watch at all (`watching.min_watched_minutes`) rather than a second one beside it. It used to be its own key at the identical value, and the two were read at different instants off different pollings of the player: the read-up fired on a reading of 600 seconds and the transcriber was asked a second later with 599. It was refused by rounding every time it was ever asked -- three logged refusals read "he is 10 min into it and the floor is 10" -- and in 1,067 session logs no character process has ever run it. A number here overrides the gate.
- `whisper_timeout_seconds` = 3600
- `ffprobe` = "ffprobe" -- for the episode's length, beside the ffmpeg `tts.ffmpeg` names
- `user_agent` = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/53...

**`household`**

- `enabled` = False -- Her flat and her week as things with a STATE, moved by the director under a daily budget and met by her as facts (sim/household.py). For a character with no world of her own: the director had nothing to move, wrote the same scene for hours, and then wrote her thoughts instead. OFF by default; the seed file lists the objects, states and moves, every one from her home file, so a move is always something she said happens to her.
- `file` = ""
- `incidents_per_day` = 2 -- moves the director may make in one day; most ticks move nothing
- `situation_max_objects` = 8 -- how many objects the one line in her situation carries

**`watching`**

- `enabled` = False -- what HE watches, noticed as it happens and read up on (sim/watching_him.py). Distinct from `watchlist`, which is her own shows: this is his, and the whole point is that the Japanese synopsis fetcher above was reachable only from him naming a show in chat, so an episode he actually played taught her nothing.  OFF by default and on for both characters as they stand -- but they LEARN IT AT DIFFERENT MOMENTS, and the moment is the program's rather than this flag's. A character who lives on his machine is told as the module lands it, dated to his play (`resident/app.py` `every_pass` -> `WatchingHim.note_seen(at_play=True)`); a character who learns what he is doing in snapshots she has to go and fetch is told when she next fetches one, dated to that (`tomoe/app.py` `after_phone_look` -> the same call without the flag), and her freshness and settle windows run from then. Turning it on is a decision about how a character finds things out, which is why it is not a default.
- `player_history_path` = "%APPDATA%/mpv/mpv_history.log" -- the player's own history, one `epoch|path` line per file opened
- `player_history_tail` = 400 -- lines read per poll, newest last
- `now_playing_path` = "%APPDATA%/mpv/mpv_now.json" -- where he is in the file open in front of him, written from inside the player by tools/mpv/scail_logger.lua. How long since the file opened cannot answer this, because he pauses -- so mpv reports its own position and pause state, refreshed every 10s and at once when he pauses. It also carries the unpaused seconds so far and the epoch the file opened at, so the fetch gate below can be answered while he is still in the file. A state file older than the staleness below is nobody watching, which covers the player being killed rather than closed.
- `now_stale_seconds` = 60
- `remember_episodes` = 200 -- so a rewatch is not announced twice
- `her_seiyuu_name` = "" -- her name as his cast mirror spells it, and blank for a character who has never been in anything -- which is what decides whether "you are in this one" can ever appear
- `open_her_record` = True -- whether contact with her own work releases the part of her record the era gate holds (sim/lore.py). The mechanism is hers alone; a character with no held claims is unaffected either way.
- `summary_max_chars` = 1400 -- the fallback cut of the raw synopsis, used only when the digest below could not be made (no model client, or the role failed)
- `digest_max_chars` = 600 -- the digest: the whole synopsis condensed by `watching_digest` into the parts a viewer would remember, cut here as a ceiling. She gets this line on EVERY message while the episode is fresh, and the line is pinned in her situation block so the attention budget cannot drop it -- it did, at 1,400 characters and the phone section's default weight, the first time an episode of his came up in chat.
- `account_in_prompt` = True -- AND THE ACCOUNT, WHICH IS NOT CUT. The digest above is still what the opener and the impulse read -- a short line about the episode is the right thing there. What goes into her situation block for the episode he has just watched is the whole account (`recap.account_enabled`, `sim/episode_account.py`): every scene in order, the parts, the gags, the lines, what the episode points at. It costs 1,500 to 4,000 characters against a situation block of 12,000 to 20,000, it sits after the thread where a byte that changes costs only itself, and the alternative is a character who has been told what an episode was about talking to somebody who watched it.
- `account_recent` = 2 -- how many of the episodes he watched TODAY get their whole account rather than one clause in the arc. The newest is always one of them.
- `account_recent_max_chars` = 6000 -- and the ceiling over those extra accounts together, so a run of six cannot put six accounts in one prompt. The newest is never dropped.
- `min_minutes_in` = 3.0 -- THE FLOOR UNDER WHICH AN OPEN IS NOT A PLAY. A file opened for five seconds was fetched, digested and kept as "he watched"; under this many minutes it is a mis-click and is logged as an open and closed, not as a skim. What decides whether a play is read up on is `min_watched_minutes` below, which is higher and measures a different thing. 0 = the old behaviour, count on open.
- `min_watched_minutes` = 10.0 -- THE FETCH GATE, and the number that separates a watch from a skim. Nothing is fetched, digested, marked seen or told to her until he has actually watched this many minutes of the file: UNPAUSED SECONDS as the player counts them (`watched=` in the plays log and in the state file), never the position and never wall clock since the file opened. Seeking to the last minute and closing the file leaves the same position as sitting through the whole thing, and a file left paused for an hour leaves the same elapsed clock as an hour watched. A play that ends under this is a SKIM: it goes in his own timeline, it is not marked seen, and no model call is spent on it. `min_minutes_in` above is the lower floor, under which an open is not a play at all.
- `player_plays_path` = "%APPDATA%/mpv/mpv_plays.log" -- Every finished play, written by the same script as the history line: when the file opened, when it ended, how long it is, where he stopped, how many unpaused seconds he sat through, and what ended it. The open's epoch is shared with the history line, which is what joins the two. Read by machine/plays.py.
- `plays_timeline_path` = "reports/plays.md" -- HIS OWN READABLE RECORD of what the player has finished, one row per play, newest at the bottom, in plain text he can open. It is the machine's rather than a character's: whichever process gets there first writes the row, keyed on the open's epoch so three processes over one player cannot write a play twice (machine/plays.py).
- `rewatch_after_hours` = 24.0 -- an episode he opens again after this long counts again, and she is told it is a rewatch
- `confirm_minutes` = 8.0 -- How long a play whose work was resolved FROM THE FILENAME ALONE is held for his list to name the id. The two routes are not equal: the player is the moment he starts and carries a filename to guess from, his list is minutes later and carries the show's own id. Once the id arrived long after the page had been fetched, for a different work, and nobody compared them. Inside this window a title-only resolution waits; when the id arrives and differs, the id wins and the log names both. 0 turns the wait off.
- `poll_minutes` = 4
- `settle_minutes` = 25 -- How long after the last episode she treats him as having STOPPED. Nothing reaches the impulse before this, so an evening of six episodes is one reason to speak at the end rather than six interruptions through it.
- `impulse_bonus_hers` = 14.0 -- a show she is in
- `impulse_bonus_finished` = 7.0 -- he has just finished a series
- `impulse_bonus_any` = 3.0
- `fresh_hours` = 6.0 -- how long the episode stays the thing in the room, counted from when it reached HER. He watches and then says nothing for an hour, so handing the summary to whichever turn came first and dropping it would defeat the point.
- `discover_hours` = 24.0 -- and how long it stays findable BEFORE that, for a character who only comes across it when she goes and fetches what he has been doing. She can be asleep or out for the whole evening he watched in; a day is what "lately" means here, and the line says how long ago he watched it. Past this she never learns of that episode as news -- the show is still hers by name (`sim/known.py`) if he mentions it. Unused by a character who is told as it lands.
- `recent_works` = 3 -- WHAT SHE IS SHOWN WHEN SHE LOOKS, when he has played more than one. Her line used to be the newest episode and nothing else, so an evening of six and a day of three works both came out as one episode. The block is now one line per WORK, newest play first.  Three works, because the situation block is 3k to 5k tokens of an 80k to 110k prompt and the gate drops nothing for room (docs/context.md §5): a work's line costs 300 to 600 characters against a block of 12k to 20k. Nothing measured has reached three, so it bounds the worst case rather than cutting anything real. Oldest dropped first.
- `recent_max_chars` = 1200 -- and the ceiling over the whole grouped block: two episode digests' worth (`digest_max_chars` is 600), which is the order the single pinned episode already costs, so the block never grows by more than one line's worth. The newest work is never dropped for it.
- `recent_keep` = 24 -- How many episodes the record of what he has watched lately keeps. It is read by the grouped block, so it has to outlast a binge: two of the largest batch his own list has ever logged at one minute.
- `max_fetches_per_day` = 8 -- A BATCH IS NOT LOST ANY MORE. His list logs a session as several rows at one timestamp (several episodes of one work at one timestamp); the poll took the newest and moved the cursor past the rest, so five plays vanished. What the poll cannot take now waits in a queue and is read up one per poll. These two bound what that can cost: at most this many episodes are read up in a day, and past it the rest of the batch is recorded as watched with no synopsis, so the range she is told about is still right. One fetch is three to five pages, a digest call each and one judge on the cheap model.
- `queue_max` = 20

**`dossier`**

- `enabled` = True -- One Markdown file per play of an episode, joining what is already on disk about it: the play itself, the episode in three scripts with its judged digest, his history with the show, the cast, and what the mirror does not hold (machine/dossier.py, docs/dossiers.md). Nothing in it is fetched for a character and nothing is a model call.  THE MACHINE'S, NOT A CHARACTER'S, and that is what this section is for. Three character processes tail the same media player, so a dossier built inside a character's loop would be built three times over three saves. It is built by the MyAnimeList mirror daemon (`tools/mal_history.py daemon`), which is the one process per machine, and an already-built play is skipped on its open time. The daemon has no character and builds no Config, so it reads these values out of the config FILE, first one on disk -- the same way it already reads the subtitle mirror's path.
- `dir` = "reports/dossiers" -- one file per play, and the rolling one
- `db_path` = "data/dossiers.db" -- what has been built, and the two cached page reads
- `last_n` = 10 -- how many plays `last-ten.md` carries
- `per_cycle_cap` = 3 -- How many are built in one pass of the daemon, oldest first. The very first pass meets a backlog of everything the player has ever opened, and a play may read up to three actors' pages; the daemon comes back every five minutes, so an evening is caught up within the hour and nothing is read in a burst.
- `min_watched_minutes` = 10.0 -- Under this many unpaused minutes it is a skim rather than a play: one line in the rolling file and no dossier. The player's own end-of-play record gives the number (`watching.player_plays_path`, read through machine/plays.py); where that file does not exist yet the gap to the next file opened is the estimate, and every line quoting a duration says which of the two it came from. Its own key rather than the watcher's `watching.min_watched_minutes` because the two answer different questions -- that one decides whether a character is told about a play at all, this one whether the machine writes a file about it -- and both stand at ten minutes today.
- `hours_before` = 6.0 -- the window of "what you played around it", in hours either side
- `hours_after` = 6.0
- `cast_detail_cap` = 9 -- Every credited actor is a row in the cast table; this many of them get a section of their own under it, main roles first. A supporting actor with forty of his shows behind her turned one dossier into thirty-eight kilobytes, most of it a list nobody was going to read.
- `actor_list_cap` = 12 -- ...and how many of an actor's other shows on his list that section names, best-scored first.
- `actor_fetch_cap` = 3 -- How many credited actors' pages are read per play, main roles first. The mirror holds a filmography for thirteen people against 11,851 cast rows, so for everybody else "what else has she done" is his own list and nothing beyond it. Read from the list site's own origin, never the community wrapper in front of it, and cached in the module's own store rather than in the mirror the daemon holds open.
- `premiere_fetch_cap` = 2 -- ...and how many works in the franchise with no premiere date on disk are looked up. A plan-to-watch entry carries no dates on a list at all, so a sequel reads as a blank row until one call fills it.
- `fetch_delay_seconds` = 1.5 -- between two page reads, so the source is not hammered
- `fetch_ttl_days` = 120 -- a cached page older than this is read again
- `fetch_timeout_seconds` = 25

**`role_check`**

- `enabled` = True -- Whether a work named anywhere near her is checked against her own filmography before she talks about it (`sim/works.py`, `her_part_verdict`). Once the second character told him she played a part in a work she has never been in; the complete cast of the episode he had just watched, with her absent from it, was in two tables on his own machine long before she said it, and nothing asked. The verdict is three-valued -- yes, no, or nobody checked -- and nobody-checked says nothing at all.  Free: two indexed sqlite reads against the machine's mirror, no model call and no fetch. Assigned in `Config.REQUIRES` to the derived property `voice_actress`, which is simply `character.mal_person_id` being set, so this flag is only ever the second of two switches.
- `person_refresh_days` = 30 -- How stale her mirrored filmography may be before a flat "no" is downgraded to nobody-checked. Her career gains a few credits a season, so a month is generous; a positive is unaffected, because a row that exists is a part she played whenever it was mirrored.
- `fetch_on_miss` = True -- Whether the worker that reads up on an episode he played also mirrors that work's cast when nobody has -- the second witness a flat "no" needs. It runs in `sim/watching_him.py`'s background thread, which already fetches pages, and NEVER in a reply path: one MyAnimeList page, measured at 0.28 s, no money. Off, and a work whose cast nobody has mirrored simply stays nobody-checked.
- `say_who_instead` = True -- Whether the denial also names the part whose name resembles hers and who really plays it. On: the work she claimed has a lead who shares her given name, which is most of why the claim happened, and a bare "you are not in it" leaves her to wonder who is and invent an answer. It is the ONLY name out of a cast list that is ever put in front of her.
- `editor_facts_max` = 6 -- How many verdicts the continuity editor is handed as checkable facts. It gets one line per work named in her draft or her situation, English, machinery to itself.
- `titles_from_draft` = True -- Whether a work named in HER OWN DRAFT (rather than only in what reached her) opens the editor's gate. The gate skipped the call on the draft that made the false claim, because it had no number, no run shared with a recent message and no word from a fact about him.

**`which_one`**

- `enabled` = True -- The one model role in the resolver (`sim/resolver.py`): which of several candidate works he means, when every deterministic filter has run and more than one is left. Code decides WHEN it is asked and a model decides WHAT, and its answer is an id out of a table code built -- never a word she reads.  It runs in the worker that reads up on an episode he played and in the lookup's own thread, NEVER in a reply path. A failure, a timeout, an unparseable answer, a confidence under the floor or an id code had already ruled impossible all leave code's own ranking standing, so this can neither stop her nor delay her.  Measured cost: about $0.0002 a call on the cheap model, three to six calls a day across both characters -- under a cent a week. It is not asked when his list has already named the id, and never twice for the same question: the answer goes in the machine's shared store (pool `resolved`) under a key that names the question and never the character, so both characters read the one answer.
- `min_confidence` = 0.5 -- Under this the answer is discarded whole and the ranking stands. A role that never says "unsure" is not being asked a real question and one that always says it is being asked the wrong one, so the floor is deliberately not high.
- `timeout_seconds` = 30 -- The cap on the wait. Past it code's answer stands; the call finishes on its own and the paid answer still reaches the store, because the store is written inside the call rather than held by the waiter.
- `max_candidates` = 6 -- rows in the table it is handed, each with the first 300 characters of its own text

**`watchlist`**

- `seed` = [] -- her own shows, with a cursor (sim/watchlist.py). The list here is planted into kv `watchlist` once, the first time a save is built, and never read again; edit live with /watch. `ja` is the search title. EMPTY BY DEFAULT: two shows were named here and every character built since started watching those two, so three of them were recapping and transcribing the same pair beside the one show each had chosen for herself. A character with no planted list starts with none and `Watchlist.pick_own` gives her one at the next compile.
- `pick_enabled` = True -- a show of her own (role watch_pick, at the compile): from her sheet, the accounts she keeps liking and what is going round, never his list; when fewer than keep_min are unfinished, or every pick_every_days
- `keep_min` = 2
- `max_open` = 3
- `pick_every_days` = 7
- `pick_tries` = 4 -- picks refused for being on his list before giving up

**`morning`**

- `latest_hm` = "13:00" -- A morning thought is only honest in the morning. Without this, a restart or a restore later in the day would produce one at four in the afternoon; with it, the day simply has none, which is the truthful outcome.
- `enabled` = True -- at the wake tick: what today is to her, first person (sim/outlook.py)

**`replay`**

- `speed` = 30 -- a hole in the record re-lived on her clock (scail.py --replay, PROJECT 8.2). The estimate printed before anything is touched: ticks = window / director.tick_minutes, cost = ticks x usd_per_tick (measured 2026-08-31 at Together: a tick is a director call ~12.5k in, an anticipation ~5k, a state read ~3k, ~600 out: ~$0.003). Past cost_warn_usd the replay refuses without --yes; --gap writes a temporal-gap event for the window instead (his rule: an extreme catch-up is reported with its cost and may be skipped as a gap).
- `usd_per_tick` = 0.003
- `cost_warn_usd` = 0.5

**`downtime`**

- `enabled` = True -- the stretch during which nobody was running her (sim/downtime.py). A stop is Stop-Process -Force, so the process being stopped writes nothing on its way out: the stop tool writes kv `stopped` on each save once the process is down, and the next boot of that character reads it, closes the row in kv `stops` and writes the stretch as a temporal gap. Without it the director sees an empty stretch as work outstanding and asks a model to write hours nobody lived.
- `gap_after_minutes` = 20 -- how long a stop has to have lasted before it is worth putting on her record. Under this she simply comes back; a restart for a code fix takes a minute or two and is nothing that happened to her.
- `shutdown_on_no_credit` = True -- the provider answering that the account is empty stops the whole machine, because no retry fixes it and every character is about to get the same answer. Only in a live run on Windows, and never with SCAIL_NO_SHUTDOWN in the environment.
- `shutdown_command` = "stopall.cmd" -- what is launched to do it, relative to the project root

**`anticipation`**

- `enabled` = True -- before what she can see coming (sim/outlook.py): his usual first activity (read off the app's day shapes) less than before_minutes away; a calendar event today (from event_morning_from_minutes after midnight) or tomorrow (from event_eve_from_minutes). One call; a line in her situation for hours_in_prompt; small deltas.
- `before_minutes` = 60
- `event_morning_from_minutes` = 540
- `event_eve_from_minutes` = 1200
- `hours_in_prompt` = 3
- `gauges_it_may_move` = ["mood", "anxiety", "validation_craving", "curiosity", "b...

**`reflect`**

- `enabled` = True -- her private mind about him (sim/reflect.py): after the app showed her something, or when curiosity / being read-and-left has built up, alone with a quiet minute, one call turns it over. Private (kv reflections, in_prompt of them in her system prompt as things she thought), moves the listed gauges, leaves the director an inner line. Never sent.
- `alone_only` = True
- `min_gap_minutes` = 75
- `max_per_day` = 5
- `curiosity_from` = 70
- `jealousy_from` = 60
- `guilt_from` = 55
- `ignored_minutes` = 60
- `keep` = 60
- `in_prompt` = 6 -- How many of them ride in her system prompt. Two was less than half a morning: she writes five to eight reflections a day, so a thought lived in her prompt for about three hours and anything that fired in the afternoon was gone before the evening she would have said it in. A comparison against one of her friends is written into this same list (tomoe/compare.py) and fires about four times a fortnight, so at two it could reach her words to him only by luck, and on the record it never did. Six is one day of them at the observed rate, which is the honest window for "something she is carrying today". Measured on the live save: the newest six render to 1,625 characters against 502 for two, so **+1,123 characters on the system prompt**, +3.7% of the 30,585-character him arm. It does not add a cache break -- this section already moves several times a day -- it makes each existing one that much longer.
- `gauges_it_may_move` = ["curiosity", "anxiety", "validation_craving", "lonelines... -- computed gauges are not in here: state.apply refuses them anyway, and a list naming what it cannot move is the "declared and unread" fault in miniature
- `cast_enabled` = True -- about anyone else: a person she talked with today, chosen by pressure (tension, standing, the length of the exchange), read from the record of what was said; reaches her prompt, the director, and cast_reply for that person
- `cast_min_gap_minutes` = 120
- `cast_max_per_day` = 3
- `cast_score_from` = 1.4
- `cast_gauges_it_may_move` = ["anxiety", "loneliness", "unsaid", "anger", "sadness", "...

**`affection`**

- `enabled` = True -- How warm she is toward him. Two halves, and the split is the point.  The structural half (state.affection_from) is attachment, closeness, relief, tension and resentment: it is what a week of being ignored does, and it needs no messages at all to work.  This half is what his messages actually left her feeling. It is read on a cycle rather than per message, because a message is not scored as it arrives -- she is answering it then. One call reads the exchange since the last cycle and gives each of HIS messages the level of warmth it leaves her at, in a band the code sets. The levels fade by age and blend into the target, taking at most max_weight of it, so the structural causes always have a say and a silent fortnight still cools her with nothing to read.  This replaces arithmetic that could not tell "busy, talk later" from "busy, sorry, i'll message you tonight".
- `review_enabled` = True
- `min_messages` = 20 -- When: once a day, as she goes under, over everything since the last read. The day is the unit a person settles up in, and an evening can only be judged against the morning it followed if both are in front of the same call. min_messages counts the exchange, not his half -- his half of a day is a modest number of messages, so counting only his would put the floor at the whole day. A day under it is not read and rolls into the next night. min_his stops a night of her talking to herself being read as him.
- `min_his` = 3
- `window_messages` = 250
- `context_seconds` = 3600 -- how much of the exchange before the new messages goes in for context
- `neutral` = 45 -- the band. One message is a message, not a verdict on the relationship
- `level_min` = 5.0
- `level_max` = 95.0
- `max_per_cycle` = 200 -- not a cap on how much of a conversation gets read -- context is the only bound that matters. This is a backstop against a model that returns nonsense, nothing more.
- `half_life_hours` = 48.0 -- how a message stops mattering: faded, never forgotten. 20 hours let one bad night own the figure by morning (53 -> 26 on 08-26); a person's warmth is the last few days of him, not the last one
- `full_weight_at` = 4.0 -- fresh-message-equivalents at which the levels own their full share
- `max_weight` = 0.5
- `keep_hours` = 96
- `max_kept` = 200

**`stress`**

- `enabled` = True -- Susceptibility is DERIVED from data/self_beliefs.json -- how much of her identity is load-bearing and how concentrated it is -- so a different character is differently fragile with no code change. These are the shape of that derivation, not her values.
- `susceptibility_base` = 1.0
- `per_invested` = 0.35
- `per_concentration` = 0.60
- `per_anxiety_baseline` = 0.25
- `susceptibility_min` = 0.55
- `susceptibility_max` = 1.60
- `load_weights` = { -- what counts as load, and how much. Every term is something the simulation already tracks; stress invents no new bookkeeping.
- `  unfinished` = 0.16, "rupture": 0.20, "unspeakable": 0.16, "unsaid": 0.12
- `  body` = 0.14, "belonging": 0.10, "him": 0.12, "ahead": 0.08, "mon...
- `cost_full` = 60.0
- `charge_full` = 160.0
- `silence_full` = 36.0
- `broke_below` = 800
- `bad_night` = 0.35
- `floor` = 6.0
- `scale` = 70.0
- `rise_per_hour` = 9.0 -- the asymmetry, which is the whole mechanism: a bad fortnight is still on her during the quiet Sunday at the end of it
- `fall_per_hour` = 2.2
- `recovery_base` = 0.5
- `recovery_alone` = 0.35
- `recovery_comfortable` = 0.2
- `recovery_slept` = 0.7
- `exhaustion_from` = 70.0 -- exhaustion forces rest; without this the compounding has no way down
- `recovery_per_stress` = 0.9
- `relief` = {
- `  slept_well` = 14.0, "bath": 6.0, "diary": 5.0, "post": 3.0, "cried": 8....
- `  goal_got` = 9.0, "rupture_mended": 16.0, "warm_exchange": 5.0
- `  held_by_the_group` = 7.0
- `relief_gap_default` = 90 -- One guard for all eight, rather than eight guards. Every site that raises a release is polled rather than edge-triggered -- a bath is a scene setting that lasts a block, a warm exchange is a mood that lasts an hour -- so without a cooldown the same bath relieves her on every director tick.
- `relief_gap_minutes` = {"slept_well": 600, "held_by_the_group": 600, "bath": 300}
- `held_from` = 12.0 -- how far above her own baseline belonging has to sit before an evening counts as the group having actually held her
- `compounds_from` = 45.0 -- what high stress does to the rest of her, capped so the loop cannot run away: three of these feed each other
- `compound_cap` = 1.9
- `compounds` = {
- `  spiral` = 0.7, "body_noise": 0.6, "delay": 0.45
- `  sleep_cost` = 0.8, "shame": 0.5, "withdraw": 0.6

**`hazards`**

- `enabled` = True -- The ground moving, and the sky. She lives in Nerima and none of this existed: on 2026-08-23 at 02:00 a M5.9 in southern Ibaraki put the 23 wards at 5-weak and she slept through it with the system unaware.
- `websocket` = True -- LATENCY. Measured off JMA's own publication filenames: ~90s to the first report, ~4 minutes to per-ward shindo. That is the floor and every relay inherits it, so the seismic feed is a WEBSOCKET rather than a poll -- adding a poll interval to a thing she physically felt is absurd. EEW (緊急地震速報) is the only sub-10-second signal there is, and it is the honest one: her phone screaming IS the event.
- `her_wards` = [] -- Which observation points are hers, in her own config and EMPTY here: this was one ward in one city, so every character's file carries it whether she has ever been there or not, and the next character in a world would have inherited it in silence. A character with none has nothing for this section to read and it switches itself off at her boot (`Config.NEIGHBOURHOOD`).
- `her_area_names` = []
- `felt_from` = 20 -- felt here, at her own ward
- `news_from` = 50 -- and big enough elsewhere to be on every channel
- `backfill_limit` = 100
- `backfill_hours` = 6 -- how recent a quake still counts as something happening TO her. Older than this and it is a thing she remembers, not a thing she is in -- at 36 the first live start delivered a 28-hour-old 5-weak as a fresh event and woke her for it.
- `fresh_hours` = 2 -- and nothing older than this may wake her, whatever its salience
- `keep` = 400
- `weather` = True -- the sky, which is known about for days and is polled
- `jma_area` = "130000" -- Her prefecture, as JMA's own area code. It is the code in the warning bulletin's filename (`..._VPWW53_130000.xml`) in the developer feed, which is what says which of the 47 bulletins is hers; her ward comes out of the bulletin body, against `her_wards`.
- `weather_poll_minutes` = 20
- `warning_max_age_hours` = 12 -- The feed hands back the newest bulletin there is, and after a hole in the process that can be days old. It is still the right answer to "is a warning up" and it is not news.
- `warning_from` = 2 -- The lowest rung that is a thing she is HAVING rather than a line in the record: 1 注意報, 2 警報, 3 特別警報. Every live one at any rung is kept and shown by `/hazards`; this is what reaches her day and her brief. A 注意報 is out over some part of Tokyo most days of the year, so 1 would put "there is a weather warning up" in front of her about two hundred times a year and teach her to stop hearing it.
- `national` = True -- what the country has been dealing with: standing knowledge, not her day. The M7.1 in Kumamoto on 2026-07-28 was 震度7 and she would know about it for months; she was three hundred miles away.
- `national_poll_hours` = 6
- `national_shindo_from` = 5
- `national_weather_rank_from` = 5 -- And the sky, which had none of this. The lowest rank of storm this keeps, out of JMA's own bulletins (`_national_weather`): 8  an emergency warning (特別警報) over a prefecture, and nothing else 7  and a named river at its top flood level, and a cloudburst over one of the big cities -- 100mm in an hour over Nagoya on 2026-09-08 stopped the subway and shut every school in the city 5  and a cloudburst anywhere at all Above 8 switches the source off and skips the fetch. An ordinary 警報 is on none of these rungs: there are thousands a year, and announcing them is how a system teaches her to ignore the one that matters.
- `national_memory_days` = 45
- `national_keep` = 40
- `national_in_prompt` = 8 -- Five was the whole of this list while it was earthquakes. With the storms in it, five lines is one bad week of weather and the earthquakes fall off the bottom.
- `wake_from` = 5 -- salience that gets a sleeping girl out of bed. 5 is a 5-weak where she is, or a tsunami warning, or the EEW alarm going off.
- `revision_step` = 5 -- a later report of the SAME quake this much worse goes again as a correction: 3 -> 6-strong must never be filed as a duplicate
- `sequence_hours` = 72 -- and a bigger one this soon after is a sequence, not a repeat
- `heavy_rain_mm` = 4.0 -- A typhoon is never an event on its own -- there are ~25 a year and almost none touch Tokyo. It is only ever the reason for rain she is actually standing in, and this is how much rain counts.

**`trains`**

- `enabled` = True -- Whether her train is running. geography.json says her commute is the Seibu Ikebukuro line, with Seibu Toshima one stop and Toei Oedo for Hikarigaoka -- none of which are JR East, so the JR status page he sent covers what she CHANGES onto at Ikebukuro, not the train she gets. Yahoo's Kanto page has all 150 lines in one HTML table, including all three of hers (84, 91, 131). Its RSS is gone and Seibu's own domain does not resolve from here.  ODPT (his access token, 2026-08-25) is the official feed and wins for every line it carries -- but the public API has NO Seibu and NO JR East (TokyoMetro, Toei, TWR, MIR, TamaMonorail, Yokohama only), so it covers her Oedo line and the Metro lines she changes onto, and Yahoo stays for the two Seibu lines and JR. odpt_lines maps the railway id to the Yahoo name so the state stays keyed one way.
- `poll_minutes` = 6
- `odpt_key` = ""
- `odpt_url` = "https://api.odpt.org/api/v4"
- `odpt_lines` = {}
- `odpt_challenge_key` = "" -- the Challenge API (a second token, api-challenge.odpt.org) is where Seibu and JR East live. **The Challenge token expires 2026-10-01**; after that the poll logs one line and drops back to Yahoo for those lines until a new token is pasted in. JR East comes per line like the public feed; Seibu is ONE operator-wide row with a text and no status, so it is applied to her Seibu lines only when the text stops saying 平常 (Yahoo keeps the per-line status the rest of the time, and the official text becomes the detail when something is wrong).
- `odpt_challenge_url` = "https://api-challenge.odpt.org/api/v4"
- `odpt_challenge_lines` = {}
- `odpt_operator_lines` = {}
- `her_lines` = [] -- Her own lines and the ones she changes onto, in her own config and EMPTY here for the same reason as the wards above: a train board with no line to watch has nothing to read, and the section switches itself off (`Config.NEIGHBOURHOOD`).
- `her_salience` = 4
- `nearby_lines` = [] -- the ones she changes onto at Ikebukuro: a suspension there reshapes the day for everyone she knows, but it is not her getting to school
- `nearby_salience` = 2

**`withholding`**

- `enabled` = True -- Not answering, on purpose. Everything that made her slow was mechanical -- delay_factor, the glance roll, the schedule -- and in all of it she is TRYING to answer and something is in the way. She could not look at a message, understand it, and leave it there. Being left on read was modelled on his side only.
- `tension_from` = 25.0 -- when there is anything to decide
- `weight_tension` = 0.9
- `weight_anger` = 0.7
- `weight_shame` = 0.5
- `weight_sadness` = 0.35
- `weight_resentment` = 0.6
- `weight_rupture` = 0.35
- `tit_for_tat_minutes` = 40
- `weight_tit_for_tat` = 0.25
- `cold_from` = 30 -- gone off him: leaving it there is easy when she does not care
- `weight_cold` = 0.6
- `standing_secure_from` = 50 -- where she stands with him (the `standing` meter): under standing_secure_from a sulk costs more than she has, over it she can afford to leave him waiting
- `weight_standing_low` = 0.4
- `weight_standing_high` = 0.2
- `threshold` = 0.55
- `min_gap_hours` = 5
- `max_per_day` = 2
- `messages_shown` = 10
- `min_minutes` = 8
- `max_minutes` = 240
- `charge_every_minutes` = 20 -- what it costs to keep it up
- `unsaid_per_hour` = 9.0
- `awkward_per_hour` = 7.0
- `awkward_soft_cap` = 85.0
- `guilt_per_hour` = 6.0
- `guilt_soft_cap` = 70.0
- `shame_on_cave` = 7.0
- `shame_soft_cap` = 70.0
- `resolve_base` = 22.0 -- INTENT OVERRIDES. She decided not to answer; she did not decide to stop wanting things. Her own impulse can always break it -- it just has to clear this much more than usual -- and her resolve erodes, much faster while he has not noticed she is doing it.
- `resolve_decay_per_hour` = 4.0
- `resolve_decay_per_unnoticed_hour` = 9.0
- `irk_after_hours` = 1.0 -- the sulk nobody noticed: worse than not sulking, and she knows it
- `irk_full_hours` = 3.0
- `irk_craving_per_hour` = 7.0
- `irk_tension_per_hour` = 2.5
- `irk_soft_cap` = 90.0
- `silence_from_empty_minutes` = 90 -- an empty persona answer whose reasoning chose silence becomes a `silence` this long, instead of a retry
- `silence_hands_back` = True -- a silence whose clock runs out while he has still written nothing gives his message back to her reply path, once, and she is offered it again rather than it staying read and unanswered for good
- `always_breaks` = ["sorry", "you ok", "you okay", "are you alright", "my fa...
- `breaks_if_words` = 2
- `keep` = 200

**`rhythm`**

- `enabled` = True -- When he is around, learned from when he has been around. This replaces a parsed window: that heard a short break message and built an object with a start, an end and a penalty fired off a clock, which is declared rather than derived and knew what he said and nothing about what he does. The record already holds his hours.
- `messages_scanned` = 600
- `half_life_days` = 21.0
- `latency_cap_minutes` = 720
- `min_samples` = 3
- `neighbour_weight` = 0.5
- `cache_seconds` = 120
- `turns_scanned` = 14 -- the tempo: how live this exchange is right now, which is the whole of "he only has a few minutes" without him having to say so
- `burst_minutes` = 12
- `burst_full` = 6
- `stale_minutes` = 25
- `slow_minutes` = 20
- `weight_latency` = 0.5
- `weight_density` = 0.3
- `weight_fresh` = 0.2
- `one_sided_factor` = 0.4
- `presence_read` = 0.95 -- what a live exchange does to her delay PRESENCE: is he at the phone. One number, decaying, from receipts (his chat focused -- the strongest signal, and the one the old tempo ignored entirely while inferring it from message gaps), then him having spoken, then the learned hour as a weak prior. The old tempo had three terms and one signal: latency, density and freshness are all "how recently was he active", so weighting them counted one piece of evidence three times and called it confidence.
- `presence_read_half_min` = 6.0
- `presence_active` = 0.45
- `presence_spoke` = 0.85
- `presence_spoke_half_min` = 4.0
- `presence_quick` = 0.9
- `quick_reply_minutes` = 3.0
- `presence_prior` = 0.35
- `enter_above` = 0.55 -- bimodal with hysteresis: entering costs more than staying, so a ninety-second lull does not drop her out of the exchange and back in
- `stay_above` = 0.35
- `notice_live_seconds` = [4, 25] -- NOTICING is all presence buys. Composing is her (state.compose_factor) and is not capped.
- `notice_glance_seconds` = [90, 600]
- `notice_idle_seconds` = [40, 900]
- `he_left_extra_seconds` = [60, 240]
- `notice_faster_ratio` = 0.4 -- what she picks up about how he is being, against four months of him
- `notice_slower_ratio` = 2.5
- `tempo_from` = 0.45
- `fast_seconds` = [8, 45]
- `glance_boost` = 1.4 -- A live exchange makes her a bit likelier to answer under the desk. A BIT. At 2.2 this came out at 0.88-0.95 and she answered him through class, dinner and the bath queue -- which is her being bound to his reply, and her having a life of her own is the entire premise. The ceiling is the real guard: however live it is, there is always a solid chance the answer is "not now, she is busy".
- `glance_ceiling` = 0.6
- `delay_factor_cap` = 1.15
- `quiet_hour_factor` = 0.4 -- an hour he is never about in is not an hour of being ignored
- `hear_enabled` = True -- And what he has actually told her. Not a booking: nothing fires off a clock, nothing punishes him for being wrong, and it fades. It moves what she EXPECTS, which is what makes his being there or not being there land -- him saying "I'm up, talk to me" outweighs the record for an hour and is worth nothing tomorrow.
- `said_trigger_words` = ["break", "work", "shift", "busy", "free", "off in"
- `said_min_chars` = 8
- `said_min_confidence` = 0.5
- `said_max_per_message` = 2
- `said_max_hours` = 16
- `said_dedupe_minutes` = 20
- `said_half_life_hours` = 6.0
- `said_weight` = 0.85
- `said_line_from` = 0.25
- `said_keep` = 200
- `tempo_live_line` = 0.6 -- the lines she gets
- `quiet_line_below` = 0.15
- `busy_line_above` = 0.7

**`approach`**

- `enabled` = True -- Getting at a sealed thing without admitting how she knows it. A discovery from the snoop used to be unraisable for as long as it stayed hot, which at charge 100 against a 9-day half-life and a carry floor of 12 is twenty-seven days -- so the largest fact she held about him sat in her prompt for a month and the only thing that ever happened to it was that it stopped mattering. People circle a thing like that instead: they ask the general form of the specific question and hope he answers it himself.
- `min_live` = 25.0 -- it has to still be worth circling, and to have had time to work on her
- `days_full` = 6.0
- `weight_charge` = 1.0 -- pressure = these four, against `threshold`
- `weight_age` = 0.35
- `weight_unsaid` = 0.4
- `weight_attachment` = 0.3
- `threshold` = 0.85
- `min_gap_hours` = 20 -- opportunity and cost. She does not do this in front of people, she does not do it twice in a night, and she will not go at the same thing more than max_per_item times however much it is pushing -- after that she has asked what she can ask without giving herself away.
- `max_per_day` = 1
- `per_item_gap_days` = 3.0
- `max_per_item` = 3
- `unsaid_over_baseline` = 25.0
- `shame_blocks_from` = 55.0 -- shame is the gauge that makes her hide, and this is the most exposing thing she can do short of confessing
- `discharge` = 0.25 -- what it does to the thing and to her
- `unsaid_relief_base` = 6.0
- `unsaid_relief_per_charge` = 0.12
- `unsaid_relief_max` = 20.0
- `awkward_per_risk` = 4.0
- `awkward_soft_cap` = 85.0
- `risk_shame_from` = 3
- `shame_on_close_call` = 8.0
- `shame_soft_cap` = 70.0
- `messages_shown` = 10
- `keep` = 200

**`events`**

- `enabled` = True -- What she is actually doing about what is on. Runs once a day, just before the schedule is generated, so the plan can honour what she has agreed to -- the old order built the plan first and let the cast comment on it, which meant nobody in her life could ever cause her to go anywhere. Stances: going / dragged / avoiding / cannot / not hers, and `dragged` is the common honest one: somebody with standing over her decided, and her choice was whether to spend something refusing.
- `lookahead_days` = 8
- `max_per_day` = 10
- `keep` = 24

**`lookup`**

- `enabled` = True -- she quietly looks up a thing he mentions (sim/lookup.py): cheap regex gate on his message, then one call to name the thing, his MAL list / MAL search / a web search, one call for the gist; in a thread during her read delay (the reply waits up to wait_seconds for it). The gist reaches the reply, kv lookups and her facts about him (fact_weight). He is never told.
- `kb_trigger` = True -- The regex only fires on genre words or a quoted title, so naming a series outright -- which is how people actually talk -- missed entirely: a question naming a series outright got nothing, while anime_kb resolves the series name and holds the whole cast. So the other trigger is simply whether a phrase in his message resolves against his own history.
- `kb_min_chars` = 4
- `kb_max_candidates` = 40
- `kb_api_max_candidates` = 2 -- a single distinctive word may be checked against MAL search, but only counts if the answer turns out to be something he has watched
- `kb_api_min_chars` = 5
- `trigger_regex` = "watch|watching|watched|read|reading|listen|song|album|ba...
- `gate` = "regex" -- How the message is gated before the classifier reads it. "regex" is the English keyword gate above plus the history probe; "model" sends EVERY inbound message to the classifier, which is the only gate that works for a character who chats in Japanese -- a short Japanese remark about a favourite character has no keyword in it. One flash call a message; the cap below is on finds, so attempts are not what it counts.
- `max_per_day` = 12 -- lookups that FOUND something, per day. It used to count attempts, which under a model gate would have spent the day's dozen on a dozen ordinary messages.
- `wait_seconds` = 25
- `timeout_seconds` = 12
- `keep` = 80
- `fact_weight` = 2
- `on_request` = False -- A character he names, in any script, is read up on at a fan encyclopedia rather than his list's card: the pixiv dictionary has the full name, temperament, relationships and running jokes; MAL's card has a romaji name and a voice actor. Only when the show is ANCHORED -- open in front of him, named in the message, or in the last few lookups -- so a bare kana word is never searched on its own. Fetched through the synopsis fetcher's browser, condensed by `character_digest`, cached in `recaps` (kind "character"). a search she asks for: `[search: what she wants to know]` on its own line in a draft runs one web search and one `search_gist` call, and the reply is written again with the answer in front of her (`Persona.generate`). Her style file has to tell her the line exists; both files do (`prompts/style.md`, section "Looking something up"), so it is on for both characters. search_per_day caps every search, hers and her sight's.
- `search_per_day` = 8
- `search_known_hours` = 6.0 -- A request of hers for a thing the automatic lookup off his message fetched this recently is answered out of what she already knows: no web request, no gist call, no second record written over the first, and her situation says she knew it rather than that she just looked it up. Kept at the window the lookup's own gist rides in her situation (situation_hours), so the thing she is being answered from is the thing in front of her. 0 turns the short-circuit off.
- `character_pages` = True
- `character_query` = "site:dic.pixiv.net {show} {name}"
- `character_hosts` = ["dic.pixiv.net/a/"]
- `character_max_chars` = 600
- `situation_hours` = 6.0 -- A lookup used to reach one reply and then survive as a 160-character fact. Two ways it stays with her now (his call, "do both"): the last `situation_max` lookups of the last `situation_hours` are in her situation on every message, so a conversation about a thing continues without a second search --
- `situation_max` = 3
- `known_max_lines` = 2 -- -- and every looked-up or watched thing is kept as a KNOWN thing with its names (sim/known.py, kv `known_things`) and comes back into her situation whenever a message of his names it, with no window. At most `known_max_lines` per message; `known_keep` things kept.
- `known_keep` = 200
- `in_front_minutes` = 30.0 -- How long the page last resolved on his screen (`sim/works.py`) counts as being in front of him, for the one line that tells the classifier what he is looking at. It read the module that watches his player instead, and named an episode he had finished while a different work was open in front of him.
- `anchor_turns` = 3 -- How many of HER OWN last turns the classifier is told about, so a message about a thing she sent him is anchored on the thing: a post she shared (its author, its text and what the picture on it is), a thing she looked up, a title she named. It used to be handed his message alone, and "nani kore?" about a link she had sent one turn earlier came back as nothing worth looking up.

**`posting`**

- `enabled` = True -- her own posts on X, from her day (tomoe/posting.py). Checked each director tick, and three things have to be true with no fourth: her phone is free (which is also how "she is awake" is known -- the night is the one block of her day whose phone is off), she is inside her budget (curation.max_posts_per_24h / post_min_gap_hours), and she feels like it -- a probability from base + unsaid + mood swing + boredom + loneliness (+ event_bonus when something salient happened today). There is no window of hours: `hours_start` / `hours_end` were 08:00-01:00, a clock hour standing in for a wake the sleep model draws anywhere between 06:20 and 11:05, and they shut the fifty minutes of free phone a school morning has before she leaves the house. Mode by gauges: vent (unsaid >= vent_unsaid or mood <= vent_mood), bright, bored, plain. Posting relieves unsaid by unsaid_relief. The post itself goes through curation (dry-run until sensors.x_posting_enabled).
- `base_probability` = 0.02
- `unsaid_weight` = 0.5
- `mood_swing_weight` = 0.4
- `boredom_weight` = 0.3
- `loneliness_weight` = 0.2
- `event_bonus` = 0.08
- `event_salience` = 4
- `cover_shame` = 45
- `vent_anger` = 42
- `vent_sadness` = 45
- `bright_pride` = 62
- `vent_unsaid` = 55
- `vent_mood` = 35
- `bright_mood` = 75
- `bored_boredom` = 65
- `unsaid_relief` = 12
- `vent_unsaid_low_mood` = 30 -- a low hour vents only with this much unsaid behind it; the rest of the day is a weighted pick among seen / into / bored / plain, never the same kind twice running
- `seen_weight` = 3
- `into_weight` = 2
- `bored_weight` = 3
- `plain_weight` = 2
- `seen_fresh_hours` = 12
- `engagement_bonus` = 0.05
- `recent_posts_shown` = 10 -- how many of her own posts the composer is shown. Nineteen posts in a fortnight had one shape -- a detail, a hedge, an abstract feeling, a closing sentence naming that feeling -- and six were not enough to see it. The composer reads them for the shape as well as the words.
- `hold_max_minutes` = 90 -- how long a yes she could not act on keeps (tomoe/posting.py). A yes that lands while his message is unread or her bubbles are still going out is written to the save and taken up at the next quiet tick instead of evaporating; the gate is rolled about every 20 minutes, so 90 gives a hold four or five chances at a quiet tick and still refuses to post a feeling from another part of her day. Her date turning over ends it too, whichever comes first.

**`taste`**

- `judge_batch` = 40 -- tomoe/taste.py: her verdicts over the carded accounts, in batches

**`curation`**

- `enabled` = True -- what she may do on the X account per day, and the evidence the code demands before it lets her: a follow needs follow_min_likes reactions to that account in her taste sheet, an unfollow needs unfollow_min_dislikes and no likes, and anything he liked or followed is never unfollowed (his side of the account is his).
- `max_likes_per_day` = 6
- `max_follows_per_day` = 2
- `max_unfollows_per_day` = 2
- `max_posts_per_24h` = 2 -- Her posts are budgeted on a ROLLING 24 HOURS, not on the calendar date the other four are: her day does not end where the date does -- she is awake with her phone in bed until 01:10 or 01:30 -- so a midnight reset put that hour on the wrong side of the cap and three of her first twenty-two posts landed in the first sixty seconds of a date, which made two a day read as three one night and one the next. `post_min_gap_hours` is the ONE gap (it was two settings, 3 and 4, and a post written at three burned a call, was held at four, and pushed her next attempt to six); a skip spends it as a post does.
- `post_min_gap_hours` = 4
- `max_reposts_per_day` = 1 -- the post whose photo she sent him
- `post_max_chars` = 140
- `follow_min_likes` = 2
- `follow_min_likes_discovered` = 1 -- an account she found by searching needs only one like to follow
- `drift_unfollows_per_day` = 2 -- the drop list from her verdicts (tomoe/taste.py) is acted on at this pace, inside max_unfollows_per_day
- `unfollow_min_dislikes` = 3
- `follow_back` = True -- somebody new follows the account: it follows them back, with no evidence asked for, because that is what an account does. Its own daily budget, so a day of new followers never spends the follows she chose for herself; the two caps add up to the day's total.
- `follow_back_per_day` = 3
- `share_pick` = True -- A post she has just sent him: what the account then does with it in public is her pick, not a coin flip. One judge call (`x_repost_judge`) puts the post to her taste -- her sheet, her reactions to that account, her verdict on it, what the account has reposted lately -- with the fact that she has just sent it to him, and answers repost / like only / neither. Off here, or with nothing of hers to judge from, the probabilities below are the fallback.
- `share_pick_recent` = 6 -- how many of the account's recent reposts the judge is shown, so a timeline with one note in it is something it can see

**`x`**

- `enabled` = True -- tomoe/replies.py: answering somebody who answered a post of hers.
- `replies_not_before` = "2026-08-22" --  Everything posted under it before this date was not written by her, and she cannot answer for words she did not write and does not know the reason for. A reply under a post older than this is dropped at read-in and never becomes a candidate, so it reaches neither her prompt nor her store as "a reply to you".
- `replies_max_per_day` = 3 -- a rolling 24 hours, like her posting budget and for the same reason: she is on her phone in bed past midnight and her day does not end where the date does
- `reply_cooldown_minutes` = 45
- `reply_candidates_max` = 6 -- how many wait in front of the judge at once, and how long a reply is still worth answering: an answer to a two-day-old reply is not a conversation
- `reply_candidate_hours` = 36
- `reply_max_chars` = 140
- `followers_line_hours` = 24 -- the account line in her situation: how long news of new followers stays there. It is the CHANGE since she last looked, never a running total -- a standing count is telemetry, not news.

**`cast`**

- `plans_enabled` = True -- each person's own day, one line at the compile (cast_life), kept and shown to the beat writer and to their own speaker calls each person's day from the `week` on their sheet, seeded, with a twist drawn with twist_p: the cancellation, the lateness, the phone taken away. Known to us (/cast day), not to her.
- `twist_p` = 0.25
- `lives_enabled` = True
- `lives_keep` = 10
- `lives_shown` = 4
- `pocket_items` = 4 -- WHAT EACH OF THEM HAS TO BRING UP, written at the compile for the day about to start and spent one call at a time (`sim/pocket.py`). Their own day, whatever they said they would bring up, one thing going round that they have actually heard, a piece of the week assigned to them, the beat of their own storyline, the fixture their week has them at. The group chat is told it is mostly made of concrete things and was handed the day's plan and each other, so it settled the plan again: 77% of 175 group turns carried a time, a plan or an obligation.
- `carry_about_her_max_streak` = 1 -- A CARRY THAT HAS TO MOVE. `carry` is the one thing still on a person's mind going into tomorrow and it is what the next day is written from. On 2026-09-07 all six of them were about the character whose world it is and four were the identical sentence three days running. After this many consecutive days about her, the prompt says today's is about their own life and a carry that is still about her is dropped rather than rewritten.
- `enabled` = True -- the people around her as sources: a seeded daily draw per person (mood, attention, friction) and a social script written once a day at the schedule generation; beats land on the clock as events the director must reflect. Nobody sees a beat before its time.
- `seed` = "scail"
- `default_volatility` = 0.6
- `late_from_hm` = "23:00" -- The late stretch of the group chat: the thing the sleep model reads to decide she could not go to bed (`Health._chat_alive`). Asked for in the prompt AND repaired here, because a prompt asking a model to write purposeless messages loses to an input full of plans: the record had every group turn at 12:00, 20:00 or 21:00 and nothing after 21:37 in eight days. `late_tail_min_*` are minutes past 23:00, so -100..200 is 21:20..02:20 -- drawn per night, never a round hour. A NEGATIVE draw is a night the chat simply dies early, and then nothing late is required: a mandatory late block every night is as artificial as the 21:00 ceiling it replaced (his call). Nobody else's tiredness is modelled.
- `night_floor_hm` = "22:20" -- ...but never before this. A negative draw is a night that dies early, not a curfew in the early evening: -100 with tomorrow's pull on top put 2026-08-28's group to bed at 21:27 on a Friday in the summer holidays, and every beat after it died on arrival. The floor is the earliest a chat of four fifteen-year-olds is plausibly over.
- `late_tail_min_lo` = -100
- `late_tail_min_hi` = 200
- `late_beats_min` = 2
- `late_morning_ref_hm` = "10:00" -- The chat knows what tomorrow holds. If they all have to be up early -- school, a club fixture, somebody's match -- it dies earlier, together, the way a real group does; a lie-in for everybody lets it run. `ref_hm` is the hour that costs nothing; every hour earlier than that than the group's first commitment pulls the end in by `morning_pull` of the difference.
- `late_morning_pull` = 0.55
- `idle_share` = 0.34 -- a beat that is about NOTHING -- a video, a shop find, a bad fringe, two words about the heat. Real teenagers do not run a committee.
- `presence_enabled` = True -- Somebody she is physically WITH says something, unplanned. The planner writes a day in advance and cannot know she would still be at that table two hours later: on 2026-08-28 she sat across from Aya from 09:05, and the day held ONE four-minute conversation with her at 09:10 while a LINE exchange with Hinako ran 37 minutes at the same table. `presence_gap_minutes` is how long the silence has to have been; the person still writes her own words.
- `presence_gap_minutes` = 25
- `presence_max_per_day` = 5
- `quiet_pull_enabled` = True -- Nothing in the mechanism knows the group chat has gone quiet: the beats are placed once when the plan is written and an exchange runs on a flat per-round probability, so a room dead for five hours is in the same state as one that spoke a minute ago. With this on, a group beat later in the day is moved to now once the room has held nothing for `quiet_after_minutes`, at most `quiet_pull_max_per_day` times, never into the dead part of the night and never over a live conversation. ON since 2026-09-05, to be watched live.
- `quiet_after_minutes` = 95
- `quiet_pull_max_per_day` = 2
- `reversion` = 0.25
- `beats_base` = 5 -- The day's social budget: a floor, plus the cast's own reach. This is the SUM of their attention, not the mean -- on the mean the whole world got about eight moments a day whoever was in it, and every day in the record had a three-to-four hour silence inside her waking hours. Each person is then given her own share of the total.
- `beats_per_attention` = 3.5
- `beats_min` = 2
- `beats_max` = 20
- `interrupt_salience` = 3 -- a beat at or above this salience interrupts the director's timestep
- `him_share_warn` = 0.7 -- drift guard: share of salient events about him above which the showrunner is told to lean the next week toward her own people
- `mechanisms_dir` = "" -- A person on the roster as a set of mechanisms -- trigger, suppressor, function -- rather than a description (tomoe/cast_mechanisms.py, docs/cast-mechanisms.md). One file per roster key in `mechanisms_dir`; a person with no file has no block and her calls go out unchanged. `mechanisms_max_chars` is the byte ceiling on one person's block in one prompt, and over it the rarest mechanisms are dropped first: what a person does every day is what a reader of the block needs, and the once-a-month one is what the day could have gone without. Raised from 1800 to 3600 on 2026-09-06, when the compile added a derived layer of about fifteen instances under everybody's hand-written ones: at the old ceiling the whole derived layer and both stress modes were the first thing dropped, since they are the rarest, and the compile would have written a block nobody read.
- `mechanisms_max_chars` = 3600
- `own_mechanisms_max_chars` = 9000 -- The ceiling on the CHARACTER's own block in her own prompt, which is a different size of thing: it rides in the half of her prompt that changes about once a day rather than in a call about somebody else, so it is charged to the cache once and not per turn.
- `types_file` = "" -- The personality type each person was written from, and the observable markers it was translated into. NOTHING that assembles a call may read this file -- not a prompt builder, not a role, not a prompt. It is for the author and for `tools/cast_type_test.py`, which counts the markers in the record and says whether the described behaviour actually appears. Naming the type to the model would be telling it the answer.

**`cast_arcs`**

- `enabled` = True -- the people's own lives (tomoe/cast_arcs.py): weekly, each role gets one or two personal arcs with loosely dated beats, a want for the week (a goal that may pull Tomoe in), and a one-line running record; plus an inter-cast web (who is tense/close with whom this week). Keyed by role_id so the lore filling a role can be re-cast without losing the machinery. The daily beat-writer (cast.py) reads these so beats are driven by the people's own plots and the group's tensions, not just the random walk. weekday 6 = Sunday; also runs once when there are none. roles_focus = how many people carry an active arc at once (the rest tick along on the draw); the others still appear in beats.
- `weekday` = 6
- `min_days_between` = 6
- `arcs_per_person` = 2
- `roles_focus` = 4
- `beats_lookahead_days` = 10
- `days_in_prompt` = 7
- `keep_records` = 40
- `arc_active_attention_bump` = 18 -- a person with an arc beat within a day is more present: their daily draw gets this attention bump (the walk is seeded from their life)
- `evolve_enabled` = True -- evolution: the cast itself changes over time. On the weekly day, with evolve_probability, at most one change (add a new person, retire one to dormant, or shift a relationship). Roles are categories, so adds can share a role (a second friend, a classmate). max_people caps the active, non-dormant cast (excluding him).
- `evolve_probability` = 0.35
- `evolve_min_days_between` = 13
- `max_people` = 12

**`environment`**

- `enabled` = True -- where her body is: the weather line is outside; what she feels is the ambient of her setting (outdoors / air-conditioned indoors or transit / indoors without / bath). The director names the setting per scene; between ticks it is read off the block's words, and an indoor place switches the air-con on above ac_from_feels.
- `ac_from_feels` = 28
- `heat_from_feels` = 12
- `ac_feels` = 27
- `heated_feels` = 20
- `transit_feels` = 26
- `bath_feels` = 30
- `indoor_offset` = 3 -- a room without air-con sits this many degrees inside the outside
- `outdoor_keywords` = ["street", "walk", "walking", "park", "outside", "balcony...
- `indoor_keywords` = ["home", "room", "kitchen", "school", "class", "cafe", "h...
- `transit_keywords` = ["train", "seibu", "subway", "bus", "metro", "yamanote", ...
- `bath_keywords` = ["bath", "shower", "ofuro"]

**`needs`**

- `enabled` = True -- hunger as a gauge: rises with the hours (slower asleep), a meal resets it (the director's `ate`, or meal words in the scene/block pull it down at meal_pull_per_hour), and past hungry_from it presses on mood and comfort. Rest is the energy gauge.
- `hunger_per_hour` = 9
- `hunger_asleep_factor` = 0.3
- `after_meal` = 8
- `snack_drop` = 25
- `meal_pull_per_hour` = 80
- `hungry_from` = 60
- `starving_from` = 80
- `hunger_mood_per_hour` = 2
- `hunger_comfort_per_hour` = 3
- `heat_from_feels` = 33 -- 1 + 2 of the needs plan (2026-08-19): mechanical consequences and director-local deviation. Outdoors in heat drains energy and counts as exposure (health reads yesterday's exposure into the cold odds); a red need (hunger >= red_hunger, energy <= red_energy) tightens the director's tick and lets it deviate inside the block (a fridge raid, a nap) without a replan; a replan only when the director moves a later block.
- `heat_energy_per_hour` = 4
- `rain_mm_from` = 0.5
- `red_hunger` = 70
- `red_energy` = 25
- `red_tick_minutes` = 20
- `director_may_deviate` = True
- `meal_keywords` = ["breakfast", "lunch", "dinner", "supper", "eating", "eat...
- `snack_keywords` = ["snack", "konbini", "ice cream", "pocky", "crepe", "taiy...

**`health`**

- `enabled` = True -- her body, mechanically: a cold now and then, a cycle, bad nights. Seeded per day; effects are targets the world terms pull toward.
- `seed` = "scail"
- `cold_p_per_day` = 0.025
- `cold_days_min` = 2
- `cold_days_max` = 5
- `cycle_days` = 28
- `cycle_start` = "2026-08-03"
- `period_days` = 5
- `exposure_cold_p_per_hour` = 0.02 -- yesterday's hours outdoors in heat or rain (kv exposure) raise the odds of a cold starting today, per hour
- `wet_exposure_factor` = 2.0 -- an hour walked in rain without an umbrella counts this many hours of exposure (embodied/situation.py hands it to Body.note_wet at arrival)
- `pull_per_hour` = 6
- `cold_energy_target` = 35
- `cold_comfort_target` = 35
- `cold_unwell_target` = 62 -- health moves the body, and mood follows: mood is computed from its causes and being ill is one of them. It moved mood directly before, which is two systems owning one gauge.
- `period_unwell_target` = 48
- `rough_night_unwell_target` = 30
- `period_comfort_target` = 38
- `period_anxiety_target` = 48
- `sleep` = { -- How well she slept is no longer a coin flip. Each night is scored 0-100 from concrete terms and banded good/ok/poor/rough; the score sets how tired she is and (with her bedtime) when she wakes. Seeded per night, computed at the midnight rollover from her evening state, the overnight forecast and when she last ate.
- `  enabled` = True
- `  planned_bed_free` = "01:30" -- skeleton lights-out
- `  planned_bed_school` = "00:50"
- `  need_hours_free` = 8.5 -- what her body wants
- `  need_hours_school` = 7.0
- `  need_jitter_hours` = 0.4
- `  delay_base_min` = 10 -- wound-up delay to actually falling asleep (minutes)
- `  delay_jitter_min` = 15
- `  delay_ref` = 55 -- gauge value where anxiety/unsaid start to bite
- `  delay_per_anxiety` = 0.6 -- extra minutes per point over ref
- `  delay_per_unsaid` = 0.4
- `  screen_ref` = 60 -- curiosity/boredom this high = on the phone late
- `  chat_alive_after_hm` = "23:00" -- 「みんな起きてるのに私だけ寝るなんて無理!」 -- the group chat still being alive is what actually keeps her up, and it is a different thing from her phone in the abstract. Counts OTHER people's turns in the group after `after_hm` (and into the small hours, to `until_min` minutes past midnight -- 150 is 02:30, the latest the chat is allowed to run): what holds her there is that they are still talking. How late it actually runs varies by night and is the planner's to decide; nobody else's tiredness is modelled. Feeds `delay`, so it also feeds `resist` in the early-bed block -- a live chat both pushes her bedtime later and makes her refuse to turn in early for a morning.
- `  chat_alive_until_min` = 150
- `  chat_alive_per_turn_min` = 6.0
- `  chat_alive_max_min` = 75.0
- `  delay_screen_min` = 20
- `  delay_max_min` = 120
- `  early_bed_max_min` = 60 -- the most she brings it forward
- `  early_bed_pull` = 0.7 -- of the shortfall, at a full pull
- `  early_bed_note_min` = 10 -- under this it is not a decision
- `  early_bed_knew_pull` = 0.3 -- over this, staying up was one
- `  heat_feels_ok` = 27 -- at/below this room feels-like the night is comfortable
- `  heat_pen_per_deg` = 4.0 -- points per room-degree over ok
- `  heat_pen_max` = 34
- `  ac_struggle_from` = 36 -- outdoor feels-like where the AC starts losing
- `  ac_struggle_leak` = 0.3 -- room-degrees gained per outdoor-degree over that
- `  humid_ref` = 80 -- muggy (only counts on a warm room / AC off)
- `  humid_pen_per_pct` = 0.4
- `  humid_pen_max` = 8
- `  mind_ref` = 55 -- an unsettled mind
- `  anxiety_pen_per_pt` = 0.5
- `  unsaid_pen_per_pt` = 0.35
- `  mind_pen_max` = 22
- `  late_meal_hours` = 2.0 -- ate within this many hours of bed
- `  late_meal_pen` = 8
- `  hungry_to_bed_ref` = 60
- `  hungry_pen_per_pt` = 0.3
- `  hungry_pen_max` = 10
- `  cramp_pen` = 16 -- period day 1-2
- `  cold_pen` = 14 -- a cold >=2 days deep
- `  short_pen_per_hour` = 12 -- duration vs need
- `  short_pen_max` = 40
- `  long_grog_from_hours` = 10.5
- `  long_grog_pen` = 6
- `  free_oversleep_per_10` = 12 -- a poor night pushes the wake later (free: sleep in; school: snooze under the alarm), minutes per 10 score points below 'ok'
- `  school_snooze_per_10` = 4
- `  oversleep_max_min` = 60
- `  wake_jitter_min` = 6
- `  free_wake_floor` = "08:00" -- a backstop, not a shaper: on a free
- `  free_wake_ceil` = "11:30" -- night bed ~01:40 + ~8.5h needs room
- `  school_alarm` = "06:45"
- `  school_wake_ceil` = "07:15"
- `  good_from` = 74 -- score bands
- `  ok_from` = 55
- `  poor_from` = 36 -- below this = 'rough'
- `  energy_target_good` = 72 -- what energy pulls toward the next morning, per band
- `  energy_target_ok` = 62
- `  energy_target_poor` = 42
- `  energy_target_rough` = 28

**`diary`**

- `enabled` = True -- her diary: first person, for herself, never addressed to anyone. Not forced: when alone with her phone in these hours, unsaid at or above min_unsaid, with a probability rising with it. Once an EVENING, not once a calendar day: the window wraps midnight and she is on her phone in bed for the last hour of it, so everything written inside it belongs to the date the window opened on (`Diary.date_for_now`). On the date, an entry written at 00:27 marked that day done and closed its own 20:30 window, which left the small hours as the only chance from then on -- twelve of the first fifteen entries were written between 00:01 and 00:59, each about a day twenty-five minutes old.
- `hours_start` = "20:30"
- `hours_end` = "01:30"
- `min_carried` = 40 -- shame or sadness she is sitting on gets her writing even on a day that left little unsaid
- `carried_weight` = 0.5
- `min_day_events` = 4 -- her own day, which is the gate for a character with no chat with him: how many things at or above `state.salient_from` her record holds for the evening she would be writing about, and how much each one past the line adds to the odds. Read only when she has nobody to say things to, so the character who has is unchanged.
- `day_weight` = 0.06
- `min_unsaid` = 50
- `base_probability` = 0.35
- `unsaid_weight` = 1.2
- `relief` = 30
- `relief_when_unasked` = 10 -- writing about a thing she has not asked him barely helps
- `max_chars` = 2500
- `keep` = 400
- `in_prompt` = 2

**`agenda`**

- `enabled` = True -- What is coming, joined from the stores that already hold a dated thing (sim/agenda.py): the calendar's holidays and what is on, her open promises, what he said he would do, who the day's plan has taken out of a day, and the lines today has settled. Nothing here decides anything; it puts them in one order. `days` is how far ahead it looks, `max_items` how many lines the block in her prompt may carry (nearest first) and `in_prompt` whether she reads it at all. The block rides in the SYSTEM half, so its dates are written absolutely and its bytes move once a day.
- `days` = 7
- `max_items` = 12
- `in_prompt` = True

**`weekly`**

- `enabled` = True -- Sunday at the day compile: a first-person paragraph of how the week felt (her own sense of it), kept in her prompt
- `weekday` = 6
- `in_prompt` = 1

**`anime_sense`**

- `enabled` = True -- Her sense of what he watches, from his episode history (data/mal_history.db, kept current by tools/mal_history.py's daemon; the bot only reads it). shelf_check: once a week she has looked at his list and what he left hanging sits in her head as something to bring up -- it lands as a director share_hint so intent/persona decide whether she nags, teases, asks or lets it go. habits: what the analysis knows about how he watches, written into user_facts through memory (refreshed every habits_every_days; duplicates reinforce). kb: when he names a series or a seiyuu, the lookup gets the real card (cast with JP voices, studio, year, his own standing with it) instead of synopsis fluff; seiyuu cards cross-reference his list.
- `shelf_check_enabled` = True
- `shelf_check_weekday` = 5 -- Saturday (his time)
- `shelf_check_min_days` = 6
- `stale_days` = 21 -- untouched this long = 'left hanging'
- `nag_close_eps` = 4 -- 'you are N eps from the end' when N <= this
- `nag_cold_max` = 3
- `habits_enabled` = True
- `habits_every_days` = 30
- `kb_enabled` = True
- `situation_line` = True -- 'his anime right now: ...' in her situation
- `nag_in_prompt` = True -- the weekly hint rides her own prompts (reply or self-start) until she brings his list up, it has been shown nag_shows_max times, or her day ends. The share_hint path alone never landed: the impulse said no all day while they were mid-conversation, and the hint died unsaid.
- `nag_shows_max` = 10

**`showrunner`**

- `enabled` = True -- weekly arcs (slow pressures). weekday 6 = Sunday. Runs at the day compile; also runs once as soon as there is a compiled day and no arcs.
- `weekday` = 6
- `min_days_between` = 6
- `max_arcs` = 4
- `days_in_prompt` = 7
- `calendar_lookahead_days` = 21

**`schedule`**

- `generate_at` = "05:00"
- `replan_on_change` = True -- when the director reports a schedule_change, the rest of the day is re-planned around it (blocks already past stay as they were)
- `max_replans_per_day` = 3
- `wake` = { -- When she wakes is drawn once per day (kv wake_days), not the fixed skeleton hour. With the health sleep model on (the normal case) the wake falls out of the night — bedtime plus how long and how well she slept (health.sleep) — and this only clamps it to the structural window (the slow-wake block ends 10:30) and rounds it. The base / jitter / energy knobs below are the FALLBACK used only when the sleep model is off.
- `  enabled` = True
- `  commitment_lead_minutes` = 75 -- an alarm: a promise with a start time on it pulls the wake back to `from_hm` minus this, never past `free_min` / `school_min`. Without it the night drew 10:10 for a morning she had already agreed to be at the library at 9, and the plan the generator was told to keep could not be kept -- a promise broken by arithmetic. 75 = out of bed, dressed, fed, and across Nerima.
- `  rising` = { -- Whether she actually gets up when it goes off. An alarm is the earliest she COULD be up, not a guarantee, and duty is not what moves her: school is compliance (a bell, a register, her mother) and is already modelled by the school branch -- up at the last possible minute, never earlier. What gets a fifteen year old out of bed is wanting the morning, or being afraid of not being there. Her own record carries both: an open `want` goal naming it against an `avoid` one, the event stance (`going` vs `dragged`, and WHO decided it -- a thing Rena settled for her is not a thing she rises early for), and `Sentiments.belonging` -- when her place in the circle is thin, missing the thing is the danger, so it pulls her up even out of a morning she dreads. Against all of that: a short night and a body that is not well. Net pull is signed and clamped to [-1, +1]; positive means up before the alarm, negative means snoozing past it.
- `  early_max_min` = 25 -- the most she is up BEFORE it
- `  snooze_max_min` = 45 -- the most she stretches past it
- `  want_pull` = 1.0 -- an open `want` goal names this morning
- `  avoid_push` = 0.9 -- an `avoid` goal does
- `  pusher_push` = 0.8 -- somebody else decided it for her
- `  stance_going_pull` = 0.5
- `  stance_not_hers_push` = 0.6
- `  belonging_ref` = 45 -- below this, absence is the danger
- `  belonging_pull` = 1.2 -- per belonging-point below ref, /100
- `  short_sleep_push` = 0.25 -- per hour short of need. At 0.10 a 2.35-hour deficit moved the scale by 0.23 against pulls of 1.74 -- sleep pressure was a rounding error in a model about getting out of bed.
- `  unwell_push` = 0.012 -- per point of unwell
- `  early_needs_rest_hours` = 1.5 -- how short of her need she can be and still beat the alarm at all. Anticipatory waking is a rested body's trick; past this the early side is shut and wanting the morning only buys being up when it goes instead of lying there.
- `  free_min` = "08:00"
- `  free_max` = "11:30" -- same backstop as health.sleep.free_wake_ceil; keep them equal
- `  school_min` = "06:20"
- `  school_max` = "07:15"
- `  round_to` = 5 -- round the drawn wake to the nearest N minutes
- `  seed` = 8123 -- fallback-only (sleep model off):
- `  free_base` = "09:30"
- `  school_base` = "06:45"
- `  free_jitter_min` = 22 -- gaussian sigma, minutes
- `  school_jitter_min` = 6
- `  energy_ref` = 45 -- energy below this pushes wake later
- `  energy_min_per_point` = 0.7

**`primitives`** -- What a feeling about another person is made of, before it has a name. `sim/primitives.py`, spec `docs/primitives.md`. Nothing in the loop reads it yet.  There are no baselines here and that is the point. A relational quantity rests at nothing when nothing has happened, because a baseline is where something returns when it is left alone and there is no such place for a history that does not exist. Baselines stay with the body and the emotions, which she has alone in an empty room.

- `enabled` = False -- Off by default. The first character's relationship is described by the meters in her cast file and by sim/sentiment.py, and switching her over is `docs/primitives.md` §7 step 3 -- which changes what she feels and is gated behind recomputing her primitives from the record she already has (§6). A character who starts at zero turns it on.
- `ceiling` = 100.0
- `decay_per_hour` = { -- per hour. Exposure is absent on purpose: what has been seen cannot be unseen, so it is a ratchet with no decay term, and that is what makes the opening condition of a character who has been read to the bottom irreversible. Reciprocity drifts toward zero fastest, because people do forgive a ledger; cost_of_loss barely moves, because it is the integral of everything else and cannot be set in a day.
- `  attention_hers` = 0.6
- `  attention_his` = 0.4
- `  predictability_hers` = 0.05
- `  reciprocity` = 0.06
- `  cost_of_loss` = 0.02
- `  threat` = 0.1
- `attachment_gain` = 1.0 -- attachment = attention x (cost of loss / 100) x this
- `withhold_needs_unshown` = 15.0 -- longing reaches its full pull at this many hours of silence withholding needs something not yet shown AND a reason to care whether he gets it
- `withhold_needs_attention` = 20.0
- `ick_needs_model` = 25.0 -- the ick is a prediction error, so it needs a model to violate
- `rupture_needs_exposure` = 30.0 -- a rupture needs enough of him seen that a break means something. Kept because `admitted` crosses on the same pair and a rupture now reads the latch: what breaks is being let in.
- `admit_needs_exposure` = 45.0 -- The territory, which is a latch and not a gradient: a character whose sheet sorts people into inside and outside with nothing between needs a crossing, not a score that can differ between two messages. What crosses it is her having done to him what he did to her -- seen enough of him, and able to call what he does.
- `admit_needs_predictability` = 40.0
- `fright_from` = 25.0 -- Fright: what he can do to her, times how little she can call what he does next. Below the first it is not worth saying; above the second it is the loudest thing about her and beats every other register.
- `fright_hard_from` = 55.0
- `fright_anxiety` = 0.35 -- How much of his message the fright is worth, per point over `fright_from`. An unrehearsed contact from somebody who can hurt her moves anxiety, and that is the whole of her second driver arriving as a number rather than as a sentence in a prompt.
- `fright_stress` = 0.20
- `perform_needs_room` = 20.0 -- The act needs a gap, and a gap needs something of her he has not got.
- `private_step` = 2.0 -- And the only way that gap ever opens for somebody who started with all of her: an interior he was not there for. It does not unsee anything -- exposure is still a ratchet -- it dilutes his share, because she keeps happening. Small: a night's diary is not a secret life.
- `private_block_weight` = 0.25 -- An hour of her own day she did not hand over, counted once per schedule block. Her diary at 2.0 a night was the only writer of this in production, against `observe_step` running every tick the other way, so the gap her act performs in could never open: 2 of a required 20. A block is worth a quarter of a diary entry, which puts a day of her own at about six points and the act within reach in three days rather than nine. 0 for a character with no day.
- `disclose_step` = 0.9 -- ...and the only way it closes again: something she told him about herself. Fed by the timeline compile's `self_claims`, which already names them daily and appends only the ones that are new, so this costs no call. Calibrated against the real rate -- the first character has made 77 of them over 14 days, a median of 6 a day -- and diminishing like `observe`, so three months of talking gets him most of the way and never quite all of it.
- `disclose_share` = 0.5 -- what telling him also gives him: a little more ability to call what she does, and one more thing he could use. The same coupling `private_threat_share` applies in the other direction, which is why intimacy and exposure to harm move together rather than separately.
- `log_rows` = 200
- `observe_step` = 3.0 -- how much one thing she sees of him is worth, before the diminishing term. She is resident on his machine, so this fires often and small rather than rarely and large; below `observe_floor` it stops writing, which is what stops a full row being rewritten forever.
- `observe_floor` = 0.15
- `message_attention` = 6.0 -- his message: attention moves with what it cost him, predictability only when he did the thing she could have called, and the ledger tips toward him because he gave and she has not.
- `message_attention_hers` = 5.0 -- and what it puts in her head. Until this existed `attention_hers` had no writer anywhere, so attachment, longing, guilt and having anything worth withholding were all pinned at zero for the whole of a character's life -- four derivations that could not leave the floor whatever happened to her.
- `observe_attention_share` = 0.5 -- watching him is attending to him, at a smaller rate than looking is worth as exposure: for a resident character this fires on every window title
- `cost_per_hour_at_full` = 0.06 -- cost of loss is the integral and cannot be set: this is what it gains per hour at full attention, and its own decay takes it back down when she stops carrying him
- `private_threat_share` = 0.5 -- what she takes back also comes off what he can show and what he can call in advance, because both were made of the same material
- `answered_predictability` = 2.5
- `message_reciprocity` = 4.0
- `gave_reciprocity` = 7.0 -- and the only entry she controls. A resident character with no world has almost no way to give, so without a feed here reciprocity can only ever run against her, and a ledger that moves one way is not a ledger. A task done for him is the feed.
- `owed_hours` = 6.0 -- The ledger's unit is unanswered reach, not volume. A message that goes this long without an answer is charged once, in whichever direction it ran: he writes into her silence and it runs against her, she writes into his and it runs the other way, which is what resentment is made of.
- `unanswered_reciprocity` = 2.0
- `held_back_reciprocity` = 1.5 -- her one currency in this premise: she saw a thing and did not raise it, and the discretion held for the whole time it was hot
- `told_anyway_reciprocity` = 3.0 -- and his: he told her a thing she could have read anyway. It costs him nothing informationally, because she can see the screen, and everything socially, because he is handing over what she would otherwise have had to take.
- `sure_from` = 85.0 -- How well she can call him only ever rose -- an answered question added 2.5 and nothing anywhere subtracted -- so it reached its ceiling in three days and being frightened of him, which is the threat times how little she can call him, became arithmetically impossible. Prediction error is the event that lowers it. Above `sure_from` a small thing bounces off and does nothing at all; certainty has no partial position to retreat to, so a charge over `shock_from` takes it down in one step instead.
- `shock_from` = 55.0
- `shock_predictability` = 30.0
- `error_predictability` = 0.25
- `demonstrated_threat` = 20.0 -- and a discovery about HER that big is evidence he will use what he holds: it writes the threat with a floor under it, which decay will not go below, and puts him back outside
- `disclose_min_words` = 8 -- A thing she told him that the record did not already hold is a disclosure, and it is what stops closeness falling on `kept_private` alone. Measured on her own words: how many of them her own record does not already contain.
- `disclose_looks_back` = 200
- `disclose_min_share` = 0.5
- `close_act_weight` = 0.9 -- and something large enough going across at once closes the act

**`state`**

- `llm_on_quiet_ticks` = False -- the state model is called only when something happened (a message, a digest, an event at or above min_event_salience, waking, a note, a snoop); quiet ticks decay deterministically. llm_on_quiet_ticks restores the old every-tick behavior.
- `sources` = {"min_level": 30, "sentiment_from": 35} -- where a feeling comes from (State.sources): an open rupture or a live withholding aims it at him, a person's sentiment at that person. Friend exchanges get "not at you"; nothing else invents one.
- `min_event_salience` = 3
- `diminishing_returns` = True -- a delta toward a crowded end of a gauge is scaled down (mood 85 is hard to raise, easy to dent); relationship meters may move at most this much per person per meter per day, in either direction net
- `relationship_daily_budget` = 8
- `world` = { -- mechanical world terms, per hour, applied in decay() before any model:
- `  enabled` = True
- `  comfort_hot_from` = 27 -- weather: physical_comfort is pulled toward a target that falls comfort_per_degree_* below 60 for each degree past these feels-like thresholds (halved indoors)
- `  comfort_per_degree_hot` = 3.0
- `  comfort_cold_from` = 10
- `  comfort_per_degree_cold` = 2.0
- `  comfort_pull_per_hour` = 6
- `  sleep_energy_per_hour` = 7 -- sleep restores energy; awake past late_from spends it
- `  late_from` = "23:30"
- `  late_energy_per_hour` = 4
- `  boredom_dull_per_hour` = 4 -- block kinds from keywords: dull (class, homework, commute, chores) / social (friends, out)
- `  boredom_social_per_hour` = 6
- `  dull_keywords` = ["class", "homework", "worksheet", "commute", "train", "c...
- `  social_keywords` = ["friends", "group", "karaoke", "festival", "cafe", "puri... -- the names on her roster are added at runtime (App.world_terms)
- `  exam_days` = 4 -- an exam within exam_days pulls anxiety up toward a floor that rises as it nears
- `  exam_anxiety_floor` = 62
- `  exam_anxiety_per_hour` = 3
- `  curiosity_silent_per_hour` = 4 -- read and ignored (after impulse.read_ignored_minutes) curiosity about him (state.gauges.curiosity)
- `  curiosity_busy_ignored_per_hour` = 6
- `  attention_curiosity_release` = 15
- `  ignored_craving_per_hour` = 4
- `  ignored_anxiety_per_hour` = 2
- `  attention_craving_release` = 5 -- his message being read releases some craving before the model reads its tone
- `  energy_alone_per_hour` = 0.0 -- What his silence and his arrival do to how much she has in her. Both 0 for a character whose energy comes from sleep and food, so the terms do nothing at all for her; set for a character who has no other supply. Contact is the only thing that puts anything back, which is what makes an unanswered day cost her something visible rather than something she only says. The gauge's own drift toward its resting value is the floor, so this cannot empty her and leave her there.
- `  energy_alone_floor` = 10.0
- `  attention_energy_release` = 0.0
- `  attention_jealousy_release` = 12 -- his attention cools jealousy, mechanically. It no longer warms affection: that is computed now (state.affection_from), and a flat bump per message was the whole reason it could only rise.
- `  tension_ignored_after_minutes` = 90 -- being left on read stops being only an ache and starts being a coldness; slow, capped, and it comes off faster than it went on
- `  tension_ignored_per_hour` = 3.5
- `  tension_ignored_cap` = 55
- `  attention_tension_release` = 6
- `  attention_relief_bump` = 14.0
- `  attention_relief_soft_cap` = 70
- `gauges` = { -- gauges are 0-100. decay_per_hour drifts each gauge toward its baseline. Every gauge declares what sort of thing it is. This is not bookkeeping: `mood` used to sit here as a peer of its own causes and be written by the same call that wrote them, which is why across 112 recorded states it ran from 50 to 84 -- twenty-nine points above its baseline and never more than five below. She could not have a bad day unless she was ill, and `state.py`'s `mood < 30` branch had never once executed. See PROJECT 16.1.  kind    : emotion (has an object, fades in hours, feeds mood) drive   (appetitive, wants something, only weakly feeds mood) body    (physical, feeds mood) derived (computed from the others; the model may not write it) valence : -1 bad, 0 neither, +1 good arousal : +1 activating, 0 neutral, -1 deactivating  The emotion set must span the valence x arousal grid. An empty quadrant is not a gap in the data, it is a feeling the character cannot have: the whole low-arousal-negative corner was empty, which is the mechanical reason nothing could put her mood down. `/gauges` prints the grid and names any empty cell.
- `  energy` = {"baseline": 60, "decay_per_hour": 4, "kind": "body", "va...
- `  mood` = {"baseline": 55, "decay_per_hour": 4, "kind": "derived", ... -- mood is computed (state._derive_mood) and refused at the write site if a model tries to move it anyway
- `  anxiety` = {"baseline": 40, "decay_per_hour": 4, "kind": "emotion", ...
- `  anger` = { -- anger: there was none, in a girl whose own sheet gives her a temper for injustice under the manners. It is also what makes a rupture a rupture rather than a sulk, and what puts something felt behind a relationship's `tension`. Fades fast; she does not hold onto it, she swallows it and it comes out as something else.
- `  baseline` = 8, "decay_per_hour": 7, "kind": "emotion", "valence": -1,...
- `  tells` = "a real temper under the manners, and mostly about unfair...
- `  tags` = [[45, "angry about something, and holding it in"], [25, "...
- `  sadness` = { -- sadness: the deactivating one, and not loneliness. Loneliness is appetitive and drives her toward the phone; this drives her away from everything. A goal that failed used to charge a belief, write a memory and produce no feeling at all. Slow to lift.
- `  baseline` = 12, "decay_per_hour": 2, "kind": "emotion", "valence": -1...
- `  tells` = "the flat kind, and not loneliness: something was lost, s...
- `  tags` = [[45, "sad in a way that has gone quiet rather than loud"...
- `  shame` = { -- shame: not guilt. Guilt is "I did a bad thing" and drives repair, which is already wired to make_up and the impulse. Shame is "I am a bad thing" and drives hiding, which nothing could produce. For this girl it is the master emotion -- the fear of being thought weird, going to pieces when somebody sees her properly.
- `  baseline` = 5, "decay_per_hour": 3, "kind": "emotion", "valence": -1,...
- `  tells` = "not guilt. Guilt is having done a bad thing and wanting ...
- `  tags` = [[45, "mortified about something and wants to not be look...
- `  pride` = { -- pride: everything good she could feel was either about him (affection) or generic (mood). Nothing registered "I did that", so the goals system only had a downside.
- `  baseline` = 15, "decay_per_hour": 5, "kind": "emotion", "valence": 1,...
- `  tells` = "something of hers came off: she said the thing, she was ...
- `  tags` = [[60, "quietly pleased about it and would die before sayi...
- `  longing` = { -- relief: the good/deactivating corner, which the grid check found empty. Relief was only ever modelled as the absence of anxiety -- a _settle on a bad gauge and nothing positive produced -- so a threat passing felt like nothing rather than like something. Fades fast: it is the shortest-lived thing she feels. longing: what attachment feels like at a distance. Written by code (sentiment.longing) from how attached she is and how long he has been gone, so the model is not shown it and cannot move it.
- `  baseline` = 6, "decay_per_hour": 5, "kind": "emotion", "valence": -1,...
- `  model_may_move` = False, "owner": "affection"
- `  tags` = [[55, "missing him in a way that is taking up room"], [30...
- `  belonging` = { -- belonging: how held she is by the circle, which is the counterweight to him. Code owns it (sentiment.belonging) from her standing with them and how recently they had her, so the model is not shown it and cannot move it. High = held.
- `  baseline` = 45, "decay_per_hour": 4, "kind": "drive", "valence": 1, "...
- `  model_may_move` = False
- `  tags` = [[62, "solid with the group at the moment"], [22, "on the...
- `  fondness` = { -- fondness: warm toward the people of her own circle, one at a time. NOT belonging, which is her standing in the group -- how held she is, whether they could leave her out -- and is a drive that wants something. This is the pleasant residue of having been with one of them: they kept what they said they would, a thing that was wrong between them got sorted, she told one of them something real, an ordinary afternoon with them was good. It occupies the good/neutral cell of the grid for a character who has a circle and no chat with him, which is otherwise empty for her: warmth toward him was the only thing in it, and a girl with friends can feel fondness for them.  Owned by the section that already keeps what she holds with them (`cast_bond`, tomoe/cast_psych.py), so a character with no circle does not have the gauge at all rather than resting at a constant. Code moves it; the model is not shown it.
- `  baseline` = 30, "decay_per_hour": 3, "kind": "emotion", "valence": 1,...
- `  model_may_move` = False, "owner": "cast_bond"
- `  tags` = [[60, "warm toward her own people at the moment: whatever...
- `  stress` = { -- stress: not a feeling and it does not behave like one. Code owns it (sim/stress.py) as an integrator over her load: fast up, slow down, and only as far down as the load allows. `body` rather than `emotion` because it is a state of the whole animal, and because the emotion grid should not have to make room for something that is not an emotion.
- `  baseline` = 12, "decay_per_hour": 0, "kind": "body", "valence": -1, "...
- `  model_may_move` = False
- `  tags` = [[70, "wound up, running on nothing, everything is a bit ...
- `  relief` = {
- `  baseline` = 8, "decay_per_hour": 9, "kind": "emotion", "valence": 1, ...
- `  tells` = "a thing she was braced for did not happen, or the waitin...
- `  tags` = [[45, "relieved, like something braced for did not happen"]]
- `  loneliness` = {"baseline": 35, "decay_per_hour": 2, "kind": "drive", "v...
- `  boredom` = {"baseline": 30, "decay_per_hour": 6, "kind": "drive", "v...
- `  validation_craving` = {"baseline": 50, "decay_per_hour": 3, "kind": "drive", "v...
- `  physical_comfort` = {"baseline": 60, "decay_per_hour": 6, "kind": "body", "va...
- `  unwell` = { -- unwell: how rotten her body feels. Not the room being uncomfortable (physical_comfort, owned by body.py and driven by the weather and the air-con) and not sadness -- you can be ill in a pleasant room and it is not a feeling about anything. This is what health.py moves, and mood follows it as a body term: health affects mood and needed its own carrier to do it through.
- `  baseline` = 4, "decay_per_hour": 3, "kind": "body", "valence": -1, "a...
- `  model_may_move` = False
- `  tags` = [[45, "physically rotten, wants to lie down"], [25, "a bi...
- `  unsaid` = {"baseline": 25, "decay_per_hour": 2, "kind": "drive", "v... -- things unsaid: fills with what the day leaves in her (salient events, being read and ignored, what she saw and did not send); writing in her diary empties it
- `  hunger` = {"baseline": 30, "decay_per_hour": 0, "kind": "body", "va... -- hunger is mechanical only (needs.*): no drift, no model deltas
- `  curiosity` = {"baseline": 40, "decay_per_hour": 3, "kind": "drive", "v... -- curiosity about him: what he is doing, who he is talking to. Rises with his silence and with his PC being busy while her message sits read and unanswered; a look at the app relieves it; his message relieves it; the state model may feed it (a digest that stings, a jealous pang)
- `  jealousy` = {"baseline": 15, "decay_per_hour": 6, "kind": "emotion", ... -- jealousy: needled about who he is with. Rises when the app shows him busy with other people or his likes/follows show other girls (the state model moves it, like the curiosity pang); his attention to her relieves it; fades fast on its own.
- `  fatigue` = {"baseline": 5, "decay_per_hour": 0, "kind": "body", "val... -- affection: warm toward him, wants to be close now. The positive approach drive (most others are deficits). His message warms her a little mechanically; a good exchange or a sweet moment more. affection: warm toward him, wants to be close now. Computed from its causes (state.affection_from) and refused at the write site, so decay_per_hour is 0 -- the derivation owns it. It stays an emotion rather than becoming kind "derived": `affect()` skips derived gauges, so marking it that way would have quietly taken the largest positive term out of the sum mood is computed from, and emptied the good/neutral cell of the grid. Code-owned and still felt is what longing and belonging already are.
- `  affection` = {"baseline": 45, "decay_per_hour": 0, "kind": "emotion", ...
- `  owner` = "affection"
- `  tags` = [[70, "feeling warm and close to him, wants to reach out"...
- `  model_may_move` = False}
- `  guilt` = {"baseline": 10, "decay_per_hour": 4, "kind": "emotion", ... -- guilt: she was short with him, went cold, or left him on read and it sits with her. The state model raises it; making up or a warm message settles it; fades on its own.
- `  awkwardness` = { -- awkwardness: she knows something about him she cannot unknow and has to talk to him anyway. Not jealousy (who else has him) and not anxiety (how she stands): the squirm of holding a thing she is not going to raise. Fades in hours; the knowing behind it does not.
- `  baseline` = 5, "decay_per_hour": 3.5, "kind": "emotion", "valence": -...
- `  model_may_move` = False -- the ick owns it (one owner per gauge, 16.1). The old hand-written delta schema left it out while the gauge list above it did not, which is the drift the generated schema exists to stop -- so make the intent explicit.
- `  tags` = [[40, "squirming about something that is not going to be ...
- `  surprise` = { -- the grid's "neither" row was empty: a feeling with no valence of its own. Code-owned: the ick (prediction error) and foresight (a reply she had written off, or far outside the window) warm it; it is gone within the hour. Read by the register, the mood tags and the arousal axis.
- `  baseline` = 5, "decay_per_hour": 25.0, "kind": "emotion", "valence": ...
- `  model_may_move` = False
- `  tags` = [[35, "caught off guard by something and still recalibrat...
- `mood_from` = { -- Mood is a slow, unattributed residue of the emotion layer plus her body, and only weakly of the drives -- being bored or hungry should not set a mood the way being ashamed does. Each gauge contributes `valence * (how far it is from its own rest) * its kind's points`, so a gauge at rest contributes nothing and an unusually calm afternoon lifts her. Mood then moves toward that at `inertia_per_hour`, which is slower than any emotion fades: that lag is what makes it a mood and not a readout.
- `  emotion_points` = 14.0
- `  body_points` = 9.0
- `  drive_points` = 5.0
- `  max_swing` = 45.0
- `  inertia_per_hour` = 3.0
- `  arousal_points` = 12.0 -- the same sum on the arousal axis, for naming the state
- `  arousal_swing` = 45.0
- `affection_from` = { -- What she feels toward him, computed rather than written.  Every mechanical write used to be upward: +6 on any message he sent, before the model read the tone, and +10 on a mend; decay only ever returned it to its baseline. So a cold message warmed her exactly as much as a kind one, and across 72 states it ran 45 to 100 and never once went under 45. That is the shape mood failed in.  None of the terms are new. Attachment is what he is to her over weeks; closeness is what the record actually supports (derive.py holds it honest); relief is him being here right now; and tension and resentment are the two ways she goes off him, one in hours and one in weeks. Silence therefore cools her by itself, which is the thing that was impossible.
- `  enabled` = True
- `  inertia_per_hour` = 6.0 -- an emotion, so hours -- not mood's most-of-a-day
- `  on_event_hours` = 0.5 -- how far it may move when something actually happens (his message, a state call) rather than waiting for the next decay
- `  attachment` = 0.45
- `  attachment_rest` = 40.0
- `  closeness` = 0.30
- `  closeness_rest` = 50.0
- `  relief` = 0.55
- `  tension` = -0.40
- `  tension_rest` = 15.0
- `  resentment` = -0.55
- `  rupture_open` = -12.0 -- while a break stands, on top of what it did to tension and guilt
- `salient_from` = 3 -- gauges the state model may not move; the world terms own them what counts as something happening rather than a day going by. One number, because two readers were carrying their own copy of it: the mechanical fill of `unsaid` and, since 2026-09-07, how much of a day a character with nobody to say things to has behind her when the diary asks whether there is anything to write (`sim/diary.py`).
- `unsaid_per_salience` = 2 -- mechanical fill of `unsaid`: per salience point of an event at or above the line above, per hour read-and-ignored, per X scroll at the same salience
- `unsaid_ignored_per_hour` = 3
- `unsaid_social` = 4
- `loneliness_per_silent_hour` = 1.5 -- loneliness climbs on its own while he is silent, capped per hour, weighted by how much of him she expects at this hour (world usual_w)
- `company` = { -- who is with her owns part of loneliness: the climb is scaled by (1 - company) and company settles it toward rest. `talk_relief` is the settle when an exchange she took part in ends, times the attachment to that person / 100. Family at a discount: her fear is being alone at break, not at dinner.
- `  enabled` = True
- `  family_factor` = 0.6
- `  loneliness_settle_per_hour` = 6.0
- `  talk_relief` = 5.0
- `habituation` = { -- habituation: with nothing new from him, a model delta pushing a gauge the same way as last tick is scaled by repeat_factor per repeat (0.55, 0.30, 0.17 ...). A standing situation is charged once; anger sat at 80 for eleven hours on 2026-08-26 because the state model re-charged "he left" on every tick. reasons_shown is how many of its own last reasons lines the model is shown.
- `  enabled` = True
- `  repeat_factor` = 0.55
- `  max_repeats` = 5
- `  reasons_shown` = 3
- `max_delta_per_update` = 15
- `one_way_warn_from` = 20 -- A gauge that has never once crossed its own baseline is either one-directional by design or broken, and the wiring report cannot tell which -- so it only says so when there was room to go the other way. guilt rests at 10 and of course has never been below it; affection rests at 45 and has never been below it either, which is the same shape as the failure mood had.
- `discharge` = { -- Misattribution: her body's bad day contaminating how she reads his. People do this reliably and she had no way to -- the state model read his message knowing nothing about her blood sugar. Only the bad direction counts: being well rested does not make her generous, it just stops the distortion. A gauge at its end is an event, not a level (sim/discharge.py): at `at` (or under `floor`) the gauge resets to `reset_to` and the rule's behaviour happens -- say (a forced message with `hint` as the whole intent), look, spiral, or act (`text` as an event the next scene must reflect, `side` on other gauges, `relieve` a stress release). One firing per gauge per cooldown, max_per_day in all. Reset is to a level, not to rest.
- `  enabled` = True
- `  cooldown_hours` = 4
- `  max_per_day` = 4
- `  keep` = 60
- `  rules` = [
- `  gauge` = "anger"
- `  at` = 92
- `  reset_to` = 62
- `  action` = "say"
- `  cooldown_hours` = 4
- `  hint` = "SHE HAS HIT THE END OF IT: the anger comes out at him, s...
- `  text` = "she threw the phone onto the bed and stood in the middle...
- `  side` = {
- `  unsaid` = -15
- `  relief` = 6
- `  relieve` = ""
- `  gauge` = "unsaid"
- `  at` = 92
- `  reset_to` = 45
- `  action` = "say"
- `  cooldown_hours` = 4
- `  hint` = "THE THING SHE HAS BEEN NOT SAYING COMES OUT, badly worde...
- `  text` = "she wrote the whole thing out in the notes app, read it ...
- `  side` = {
- `  relief` = 8
- `  relieve` = "diary"
- `  gauge` = "loneliness"
- `  at` = 93
- `  reset_to` = 58
- `  action` = "say"
- `  cooldown_hours` = 5
- `  hint` = "she reaches out because she cannot stand it another minu...
- `  text` = "she lay on the floor with the phone face-down and cried,...
- `  side` = {
- `  sadness` = 5
- `  relief` = 4
- `  relieve` = ""
- `  gauge` = "sadness"
- `  at` = 90
- `  reset_to` = 55
- `  action` = "act"
- `  cooldown_hours` = 4
- `  text` = "she cried, properly, into the pillow, and came out of it...
- `  side` = {
- `  relief` = 10
- `  energy` = -8
- `  relieve` = "cried"
- `  gauge` = "anxiety"
- `  at` = 92
- `  reset_to` = 66
- `  action` = "spiral"
- `  cooldown_hours` = 4
- `  text` = "her chest did the tight thing and she could not sit stil...
- `  side` = {
- `  energy` = -6
- `  relieve` = ""
- `  gauge` = "validation_craving"
- `  at` = 92
- `  reset_to` = 50
- `  action` = "say"
- `  cooldown_hours` = 5
- `  hint` = "she fishes: a half-message that exists to be noticed -- ...
- `  text` = "she took four photos of nothing in particular and posted...
- `  side` = {
- `  shame` = 4
- `  relieve` = ""
- `  gauge` = "boredom"
- `  at` = 92
- `  reset_to` = 40
- `  action` = "look"
- `  cooldown_hours` = 3
- `  text` = "she rolled over and opened every app on her phone twice"
- `  side` = {}
- `  relieve` = ""
- `  gauge` = "stress"
- `  at` = 92
- `  reset_to` = 60
- `  action` = "act"
- `  cooldown_hours` = 6
- `  text` = "she gave up on the day: lay down, phone on silent, did n...
- `  side` = {
- `  energy` = -10
- `  relief` = 6
- `  relieve` = "gave_up"
- `  gauge` = "shame"
- `  at` = 90
- `  reset_to` = 55
- `  action` = "act"
- `  cooldown_hours` = 4
- `  text` = "she went small: deleted the message she was drafting, tu...
- `  side` = {
- `  unsaid` = 8
- `  relieve` = ""
- `  gauge` = "jealousy"
- `  at` = 90
- `  reset_to` = 50
- `  action` = "look"
- `  cooldown_hours` = 4
- `  text` = "she went through the account again looking for the thing...
- `  side` = {
- `  anxiety` = 5
- `  relieve` = ""
- `body_noise` = {
- `  enabled` = True
- `  weights` = {"hunger": 0.45, "energy": -0.45, "unwell": 0.5, "physica...
- `  report_from` = 0.25
- `  reverse_body_under` = 0.10 -- the reverse: a wound-up head with the body near rest reads itself as the body (a stomach, "coming down with something")
- `  reverse_anxiety_over` = 30
- `  reverse_stress_over` = 60
- `  clear_below` = 0.12 -- the correction: noise falling from past report_from to under clear_below takes `relief` x (the noise it fell from) of each relief gauge's height above rest off, once per cooldown, and the next state call is told
- `  relief` = 0.5
- `  relief_gauges` = ["anxiety", "anger", "sadness"]
- `  relief_cooldown_hours` = 4
- `blends` = [ -- Two feelings both up that do not cancel, named for the prompt (mood tags) and the reports. `at` is [threshold for a, threshold for b]. State.blends(); at most two shown.
- `felt_time` = { -- How long his silence feels, as against how long it is. Prompt-facing only: the impulse keeps the true figure, because anxiety and craving are already weights in it and feeding it a number those same gauges inflated would count them twice.
- `  enabled` = True
- `  weights` = {"loneliness": 0.45, "validation_craving": 0.35, "anxiety...
- `  min_factor` = 0.6
- `  max_factor` = 2.2

**`ick`** -- An ick is not a category, it is prediction error against her picture of him (sim/ick.py, sim/model_of_him.py). A discovery costs her exactly what it takes away from a belief she is invested in, so nothing is listed anywhere as shocking, and the same discovery stops costing her anything once the belief has been rewritten to accommodate it.

- `enabled` = True
- `about_her_weight` = 0.6 -- how much a belief being about her own place with him adds to the cost
- `intimate_weight` = 0.5 -- private in itself (bodily, ashamed, money lost) carries weight even when it fits her picture of him perfectly
- `charge_ceiling` = 3.2 -- what counts as a 100: not the theoretical maximum (two beliefs at full strain, which nothing real reaches) but one belief she has a lot riding on, badly contradicted, and private with it. Scaling against the maximum put the worst thing in his real data at 24 of 100.
- `strain_per_point` = 22 -- strain put on the belief per point the model scored, out of 5
- `circle_weight` = 0.5 -- habituation: 1/(1+seen)^power. At 0.85 the second time is 0.55 of the first, the third 0.39, the fifth 0.24. the girls in her class never find out and she never tells them, but she runs everything past them in her head. A thing they would have something to say about costs her more than the same thing in private.
- `circle_anxiety_ref` = 40 -- and it only bites to the extent she is currently in the grip of what people think
- `novelty_power` = 0.85
- `novelty_floor` = 0.15 -- habituation damps, it does not zero. Her seeded kinds carry counts in the tens, which alone would take a genuinely belief-breaking discovery down to three percent and make her unshockable about anything she has ever seen before.
- `kinds_in_prompt` = 24 -- how many of the sorts of thing she has already run into are shown to the scoring call, so it can say which one this is instead of coining a fresh label for the same thing
- `kind_jaccard` = 0.5 -- a loose net under the model's own matching, not the matcher itself
- `max_kinds` = 80
- `max_chars` = 2000
- `message_min_chars` = 25 -- a message too short to contain anything is not assessed
- `digest_min_gap_minutes` = 90 -- the app fires constantly; do not pay for a call every look
- `cast_in_prompt` = 6
- `known_shown` = 40 -- what she already knows about him, so a thing she has known for months is not scored as a discovery
- `anxiety_weight` = 0.5 -- how wound up she was when she found it; only unease adds
- `jealousy_weight` = 0.6
- `loneliness_weight` = 0.3
- `tired_below` = 30
- `tired_bonus` = 0.1
- `max_state_multiplier` = 1.6
- `min_charge` = 8 -- under this the belief still takes the strain but nothing happens to her
- `awkwardness_per_charge` = 0.9
- `surprise_per_charge` = 0.35
- `surprise_soft_cap` = 80
- `awkwardness_soft_cap` = 85
- `unsaid_per_charge` = 0.35
- `unsaid_soft_cap` = 90
- `event_salience` = 3
- `half_life_days` = 9 -- the knowing outlives the squirm: the charge halves in this many days
- `carry_floor` = 12
- `in_prompt` = 3
- `max_items` = 80
- `settled_after` = 12 -- cooled off AND met this often: it is just how he is, and she can say so Past this many sightings a sort of thing is not a discovery any more, it is a fact about him: the multiplier goes to zero and it stops being assessed. At the flat floor of 0.15 a kind she had met fifty times still charged eight points, and eight points of awkwardness a day is a standing tax nothing earned.
- `about_her_top` = 4.5 -- ...except where the thing is about HER. The tenth must cost what the first did, and this is the top of the 0-5 scale the scoring role writes on the belief it touches.
- `settled_days` = 1.0 -- How settled she is with him: the share of what she has met over this many days whose sort she had already run into. At 1.0 nothing he does is news; at 0.0 every look is new. Where the window holds fewer than `settled_min` it reads the last `settled_window` of the record instead, because a share of one is not a reading.
- `settled_min` = 3
- `settled_window` = 12
- `teasable_after_seen` = 2
- `teasable_in_prompt` = 3
- `bar_jaccard` = 0.35 -- a thread this close to something charged is never what she raises
- `source_words` = {
- `  snoop` = "she went through his things on the app; he does not know...
- `  digest` = "the app on her phone showed her while she was checking o...
- `  x` = "she saw it on X, on his own account, where anyone could ...
- `  photo` = "he sent it to her himself"
- `  lookup` = "he mentioned it and she quietly looked up what it actual...
- `  told` = "he told her himself, in a message, unprompted"
- `  seen` = "it was on his screen in front of her; she lives on his m...

**`beliefs`** -- Her picture of him: what she has decided he is, seeded from character.beliefs_file and rewritten as it fails (sim/model_of_him.py).

- `enabled` = True
- `in_prompt` = 8
- `strain_half_life_days` = 11 -- a contradiction she found a reason for fades; only repeated pressure gets a belief rewritten
- `straining_from` = 30 -- past this it shows in her prompt as a thing she is holding together
- `revise_base` = 45 -- what it takes to make her let a piece of it go: she defends what she has most riding on, and what she has actual grounds for, longest
- `revise_per_invested` = 55
- `revise_per_evidence` = 25
- `evidence_per_fit` = 12 -- what a revision costs the belief what being borne out gives a belief (per point of fit, out of 5)
- `confidence_per_fit` = 8
- `strain_relieved_per_fit` = 9
- `confidence_lost` = 20
- `invested_lost` = 12
- `evidence_gained` = 15
- `certain_from` = 92 -- Being at the top of the scale has to mean something rather than just being where the number stopped. Past certain_from she is not weighing the belief any more, and certainty does not erode: a real contradiction takes the whole thing down at once instead of costing it 22 points. Past graduate_from on evidence it is not a belief at all any more, it is something she knows about him, so it moves into user_facts and stops soaking up confirmations -- but it can still be shattered, because a proven thing does not wear away either, it breaks.
- `graduate_from` = 85
- `shatter_min_strain` = 12 -- what counts as a real contradiction rather than a niggle. strain_per_point is 22, so this is the model scoring 3 or worse out of 5.
- `event_salience` = 3
- `settle_on_seed` = True -- a fresh belief set on a save that already has months of history would have her shocked by things she has lived with since spring, so it is settled against what she already knows, once, at seed
- `settle_min_facts` = 8
- `settle_strain_scale` = 2.5
- `settle_max_straining` = 3 -- how many of her beliefs may come out of the settle visibly under strain. The model will hand back a 3 or a 4 for every belief a real person has ever fallen short of, and nine at once is not a girl four months in, it is a crisis. Which ones is the model's call; how many is not.
- `settle_max_revisions` = 4
- `settle_facts_shown` = 60

**`contagion`** -- What she is trying to do (sim/goals.py). Her morning want was written to kv every day and read by nothing, while every person in the cast had a want the beat writer acted on. Emotional contagion. His state reached her as message content and as read receipts and never as a state, so there was no route by which his being flat could make her flat -- and co-regulation is most of what being with somebody consists of. The state model reads his mood off how he wrote; code decides how much of it she takes, scaled by what he is to her (sim/sentiment.py). She is never told it happened.

- `enabled` = True
- `strength` = 9.0
- `negative_bias` = 1.35 -- catching is stronger downward than up, which is the part of this the research is clearest about
- `default_susceptibility` = 0.5
- `half_life_hours` = 5.0 -- what he sounded like six hours ago is not what he is now
- `forget_below` = 0.2
- `soft_cap` = 88
- `valence_gauges` = {"sadness": 1.0, "anxiety": 0.8} -- a positive weight means his being low RAISES it (anxiety, sadness); a negative weight means his being low lowers it (mood is derived and is not in here at all -- it follows these) `affection` is deliberately not in here: how she feels toward him is an appraisal of him, not a state she catches off him. Catching is for affect.
- `arousal_gauges` = {"energy": 0.7, "boredom": -0.4}

**`compare`** -- What a person is to her, as against how she feels this afternoon (sim/sentiment.py). Every emotion here is episodic and object-free and every relationship meter is bookkeeping over the record; neither is a durable felt orientation toward a named person, so `closeness 48` did no felt work and she could be warm at 8pm and neutral at 8am with nothing carried. Seeded once from the meters, then fed only by things that carry a person. Social comparison (tomoe/compare.py): code decides when (a peer in the scene or just talked with, her craving / shame / anxiety over rest and belonging under par, a daily cap, a cooldown), the `compare` role decides what (who, dimension, direction, the thought, which self-belief it lands on). Upward: envy toward that person, shame, craving, anxiety, a strain on the belief. Downward: pride. The thought goes out through the reflections channel.

- `enabled` = True
- `max_per_day` = 2 -- Comparisons she actually MAKES in a day, not calls asked. The model answers `fires: false` four times in five and this counted the asking, so two refusals closed the day: over a fortnight the layer was asked 20 times and fired 4. What bounds the spend is `cooldown_hours`, which is charged whatever the answer was.
- `cooldown_hours` = 3
- `base_p` = 0.12
- `weights` = {"validation_craving": 0.45, "shame": 0.35, "anxiety": 0.25}
- `belonging_weight` = 0.3
- `dimensions` = ["looks", "body", "clothes", "being_behind", "dating", "p...
- `envy_gain` = 14
- `shame_gain` = 10
- `craving_gain` = 8
- `anxiety_gain` = 5
- `pride_gain` = 8
- `strain_gain` = 12
- `confirm_gain` = 6
- `soft_cap` = 85
- `keep` = 80

**`sentiment`**

- `enabled` = True
- `ceiling` = 100.0
- `half_life_days` = {"attachment": 70, "resentment": 45, "respect": 90, "cont... -- weeks, not hours, and toward nothing rather than a baseline: what somebody is to you goes if nothing keeps happening
- `seed_attachment_from_closeness` = 0.9
- `seed_resentment_from_tension` = 0.7
- `seed_respect_from_standing` = 0.3 -- respect is earned. `standing` is how she is placed with somebody, which is a different thing entirely -- seeded at 0.8 it had her looking up to her own father, Kaito and Hinako on day one.
- `log_from` = 0.5
- `prompt_from` = 32
- `max_in_prompt` = 4
- `longing_needs_attachment` = 20 -- longing: what attachment feels like at a distance. She is in a relationship conducted across a great distance and had no gauge for missing somebody -- `loneliness` is a deficit that wants any contact, this is about one person and is not entirely unpleasant.
- `longing_full_hours` = 16
- `longing_scale` = 85
- `longing_per_hour` = 9.0
- `family_roles` = ["mother", "father", "sibling"] -- belonging: her standing with the circle times how recently they had her. Family is not in it -- you belong to a family whether it is going well or not, and her named fear is being left out at break.
- `belonging_half_life_hours` = 20.0
- `belonging_floor` = 0.35
- `belonging_per_hour` = 7.0
- `phone_debt_enabled` = True -- the zero-sum: what being on her phone with him costs her with them
- `phone_debt_free` = 4
- `phone_debt_per_message` = 0.6
- `phone_debt_max` = 4.0
- `contagion_floor` = 0.15 -- you catch the mood of somebody who matters to you, not a stranger's
- `impulse_attachment` = 10.0 -- attachment reaches, resentment does not. Resentment is the only thing in the system that can hold her back for weeks.
- `impulse_resentment` = 16.0
- `delay_resentment` = 0.5
- `mend_attachment` = 2.2 -- what things that carry a person are worth
- `mend_respect` = 1.2
- `scar_resentment` = 3.4
- `failed_bid_resentment` = 1.6
- `attention_attachment` = 0.45
- `compile_max_delta` = 6.0

**`rupture`** -- Rupture and repair (sim/rupture.py). Before this a fight healed by the passage of time -- guilt decayed at 4 an hour, tension drifted down, and `intent` could return `make_up` with nothing behind it, so a day of saying nothing repaired a row as well as an apology did and better than a failed one. Nothing could be broken, so nothing could be earned.

- `expel_severity` = 4 -- At or above this severity, a break that settled WORSE rather than mended puts him back outside her territory -- for a character who has one (sim/primitives.py:expel). What makes being let in mean anything is that it can be lost.
- `enabled` = True
- `max_kept` = 60
- `anger_weight` = 1.0 -- noticing one: a jump in the gauges that carry a break, in a tick that had something said in it. A rupture is not a bad mood.
- `guilt_weight` = 1.0
- `shame_weight` = 0.7
- `sadness_weight` = 0.6
- `min_score` = 9.0
- `messages_shown` = 10
- `scars_shown` = 5
- `scars_in_prompt` = 3
- `tension_per_severity` = 6.0 -- what opening one does
- `guilt_per_severity` = 7.0
- `guilt_soft_cap` = 75
- `scar_scale_per` = 0.15 -- an old unmended thing makes the next one land harder
- `scar_scale_cap` = 0.6
- `holds_gauges` = ["guilt", "anger", "sadness"] -- Time does not repair: while one is open these are held off their decay, so the day cannot quietly file it away. This is the single most load-bearing setting here.
- `hold_decay_factor` = 0.3 -- a held gauge decays at this fraction of its rate...
- `hold_floor` = 25 -- ...toward baseline + this, never below it, until the rupture is settled or scarred
- `closeness_on_mend` = 2.2 -- what mending one is worth. Closeness ends up ABOVE where it started: a pair who have broken something and mended it are closer than a pair who never broke anything, and that is the whole point of the object.
- `tension_off_on_mend` = 9.0
- `guilt_off_on_mend` = 12.0
- `relief_on_mend` = 28.0
- `relief_soft_cap` = 80
- `memory_weight_mend` = 4 -- no affection line here: mending raises closeness and relief and takes tension off, and the derivation turns those into warmth worth about twice the flat +10 this used to add.
- `shame_on_failed_bid` = 16.0 -- a bid nobody takes. This has to hurt or making one costs nothing.
- `shame_soft_cap` = 80
- `sadness_on_failed_bid` = 12.0
- `sadness_soft_cap` = 75
- `tension_on_failed_bid` = 5.0
- `anger_on_worse` = 14.0
- `anger_soft_cap` = 70
- `scar_after_hours` = 40 -- what time actually does: turns an open thing into a scar. Cast meters have no gravity, so what this takes off closeness stays off.
- `closeness_on_scar` = 1.8
- `memory_weight_scar` = 4
- `event_salience` = 3

**`spiral`** -- Anxiety as a process rather than a level (sim/spiral.py). Everything in here is about how the mechanism works, which is human; what makes it this girl's is entirely in her own numbers -- her anxiety baseline is her propensity, her cast meters decide who can start one, and her self-beliefs decide what a chain is pulled toward and how far it runs.

- `enabled` = True
- `min_gap_minutes` = 45
- `max_per_day` = 3
- `max_kept` = 60
- `steps_per_invested` = 16.0 -- A chain runs while the belief it is heading for is still pulling, so what she has most riding on carries her furthest: 95 invested is six steps, 45 is three. max_steps_hard is a backstop, not the mechanism.
- `max_steps_hard` = 7
- `start_base` = 0.55
- `extend_base` = 0.45 -- The self-feeding term. This is the one gate in the project that accelerates instead of damping, because that is the thing being modelled: three steps in, the fourth is likelier, not less likely. The brakes are opportunity and the caps, never the chain.
- `extend_per_step` = 0.28
- `tension_weight` = 0.65 -- Who can start one: not a list of people, a measure of how unsettled her standing with them is. Somebody she is placed well with and has nothing outstanding with cannot seed anything.
- `standing_weight` = 0.45
- `envy_weight` = 0.4 -- someone she measures herself against can seed a chain
- `standing_settled_at` = 62
- `seed_min` = 0.15
- `pressure_cap` = 1.2 -- her rest is not neutral: the level is the propensity, and being above rest on top of it accelerates. Capped so a very wound-up evening cannot make it a certainty.
- `busy_factor` = 0.35 -- Rumination needs somewhere to happen. She is fine while she is with them and starts on the train home.
- `min_energy` = 25
- `anxiety_per_step` = 7.0 -- What going over it costs. Through _warm, so the gauge saturates gracefully while the thought carries on getting worse; those two curves are meant to come apart. Mood is left to the state model off the event rather than pushed through its baseline by hand.
- `arrived_anxiety` = 12.0
- `anxiety_soft_cap` = 88
- `pitch_per_step` = 18
- `reassurance_relief` = 9.0 -- He answered. She feels better and nothing has been settled.
- `fade_hours` = 14
- `events_shown` = 14
- `chat_shown` = 8
- `in_prompt` = 2
- `impulse_weight` = 0.30 -- the social term the impulse never had
- `event_salience` = 2
- `settle_min_steps` = 2 -- what the record having the last word is worth
- `borne_out_fit` = 4.0
- `disconfirm_strain` = 26.0
- `disconfirm_relief` = 20.0
- `max_also_touches` = 2
- `memory_weight` = 3

**`goals`**

- `enabled` = True
- `min_chars` = 12
- `same_jaccard` = 0.45 -- the same want two mornings running is one want she is carrying
- `carry_to_standing` = 2
- `max_kept` = 60
- `fail_base` = 8.0 -- What a day that did not go her way costs. Nothing used to: a `missed` appended a line to the goal's history and left it wanting, so a goal she failed and a goal she had not got round to were the same object.
- `fail_per_carried` = 3.0
- `fail_per_invested` = 10.0
- `fail_missed_scale` = 1.0 -- a day she let go past is about her; a move that did not land has an explanation available and she will take it
- `fail_tried_scale` = 0.5
- `fail_witnessed_scale` = 1.6 -- in front of people, which for her is the whole of it
- `witnessed_heat_spread` = 0.4 -- the graph prices the audience: the same witnessed stumble costs more in front of an irritated group than a warm one (0 disables)
- `got_fit` = 3.0 -- what an outcome is worth as evidence for the belief underneath it, out of 5
- `tried_fit` = 1.0
- `give_up_fit` = 4.0
- `give_up_base` = 18.0 -- When she stops wanting it. Not a trait and not a count of tries: a want survives while it is holding up something she believes about herself, so one anchored to nothing much dies quietly at three failures and one holding up ninety points of self she carries well past sense. Point the code at a different self_beliefs.json and a different girl gives up somewhere else.
- `give_up_per_invested` = 70.0
- `give_up_strain_mult` = 2.0 -- giving up is the expensive one: the failure that ended it counts double. Not the accumulated cost -- the belief has already been strained for each of those, one at a time.
- `tiring_at` = 0.6 -- past this share of the way to giving up it shows in her prompt
- `pride_on_got` = 16.0 -- a day that went against her stays with her longer than one that went her way What an outcome feels like, as opposed to what it costs. Without this the goals only had a downside: a failure charged a belief and wrote a memory, and getting the thing produced nothing at all.
- `pride_soft_cap` = 80
- `sadness_per_fail` = 9.0
- `sadness_on_give_up` = 18.0
- `sadness_soft_cap` = 75
- `shame_on_witnessed` = 14.0
- `shame_soft_cap` = 80
- `memory_weight_fail` = 3
- `memory_weight_got` = 2
- `memory_weight_given_up` = 4
- `event_salience` = 3

**`self_memory`** -- Her own memory of her own life (sim/self_memory.py), which she had nothing of: facts about him had weights, half-lives and cue recall, and her own past was one summary a day.

- `enabled` = True
- `half_life_days` = [14, 45, 120, 400, 1200] -- slower to go than a fact about him. A fact about someone else is information; this is her, and a weight 5 memory is for good.
- `min_score` = 0.5
- `max_in_prompt` = 8
- `max_recalled` = 3
- `max_cosine_only` = 1 -- ...of which this many may be rows the WORDS never found. Her own memories are the pool this matters most in: on the second character's save every one of her twenty-one memories cleared the old fixed floor for every Japanese cue, so the cosine chose the three she read at random.
- `standing_in_prompt` = 8 -- How many of what she is MADE OF sit in the prompt, in slots of their own beside the max_in_prompt she has lived through. A memory written in from her own record (source `seed`) does not fade at all -- a person does not gradually stop knowing their own job -- so the fade line cannot choose among them and this cap does. Anything at weight 5 is in every prompt; the remaining slots walk the rest in weight order, one step a character day, so the whole record comes round. Only the second character has memories of this kind; the first has none, so the number does nothing in her save.
- `duplicate_jaccard` = 0.5 -- looser than the bar for facts about him: two wordings of one afternoon are one afternoon she keeps thinking about
- `max_per_day` = 5
- `compile_max_per_day` = 2 -- the moments write themselves (state._moment, npc._record): a tick whose biggest move is moment_min_delta, or whose moves sum to moment_min_total, keeps the state model's own reasons line as a memory, at most moment_max_per_day a day; the compile then authors at most compile_max_per_day of its own and mostly reinforces what the day wrote
- `moment_min_delta` = 8
- `moment_min_total` = 14
- `moment_max_per_day` = 6
- `moment_npc_salience` = 3
- `mood_congruent` = True -- Mood-congruent retrieval: how she feels selects what she surfaces, and what she surfaces deepens how she feels. The second self-feeding loop after the spiral. Keyed on `mood`, which lags, because a mood is what colours retrieval and not the feeling of the minute. The floor stops a good day from making an unhappy memory unreachable.
- `congruence_weight` = 0.6
- `congruence_floor` = 0.45

**`care`**

- `enabled` = True -- sim/care.py: her investment in him from the record, and whether her checking matches it. scale_checking multiplies the app-look and snoop rolls by 0.5..1.5 from investment (off until he says).
- `window_days` = 7
- `min_window_hours` = 12.0 -- The narrowest span the per-day rates will divide by. The window is how far back to look; this is the floor on how long there has to have been a record before a rate means anything, so a character who has existed for an hour is not divided by a week (which read as caring about nothing) nor by an hour (which would read as checking on him forty-eight times a day).
- `reaches_full_per_day` = 3.0
- `balance_full_ratio` = 3.0
- `slow_minutes` = 120.0
- `left_after_minutes` = 360
- `checks_full_per_day` = 8.0
- `snoop_weight` = 2.0
- `weights` = {"initiative": 1.0, "balance": 0.5, "responsiveness": 1.0...
- `  head_share` = 1.2, "attachment": 1.2, "affection": 0.8, "not_resentful"...
- `silence_full_hours` = 12.0
- `his_slow_minutes` = 180.0
- `checks_base_per_day` = 4.0
- `uncertainty_gain` = 1.2
- `scale_checking` = False

**`foresight`**

- `enabled` = True -- sim/foresight.py: what she expects him to do next, written down at each send and checked by the record
- `keep` = 60
- `stale_hours` = 12 -- an open prediction past this is a silence
- `window_slack` = 1.5 -- answered inside reply_minutes x this counts as inside
- `surprise_reply_p_under` = 0.35
- `surprise_bump` = 12
- `surprise_soft_cap` = 70
- `refresh_hours` = 3 -- while he is quiet, a fresh reading this often
- `refresh_silent_from` = 2 -- ... once he has been quiet this long
- `impulse_weight` = 8.0 -- reaching again inside her own window costs (1 - reply_p) x this
- `risk_hours` = 6 -- the risk each prediction names, scored against his next mood read (`score_risks`): happened if it is cold inside risk_hours, passed if not; happened warms guilt and shame, passed warms relief
- `risk_guilt` = 6
- `risk_shame` = 4
- `risk_relief` = 5

**`reactions`** -- Expectations of him (sim/expectations.py): signed, checkable, with a due time and a source -- what he said he would do (`expect_him`), when he said he would be around (mirrored from rhythm_said), what foresight said might land badly, and his habits learned from a week of digests (`habits_him`, once a day). Settled by code off the record; a missed one strains the belief it rested on, moves resentment and tension, and sits in her prompt as raisable until she brings it up. Questions she is curious about (sim/wonder.py): formed by the `wonder` call when curiosity is over its rest or something just reached her (a look, a snoop); handed to the intent by id; the send marks one asked; his answer inside answer_hours is judged by `wonder_answer` and confirms or strains the belief it bore on (test_him), moves attachment (compare_self), or warms curiosity and leaves it standing (dodged). The one route by which a belief about him is tested by asking him. Borrowed eyes (tomoe/scenery.py): real photographs from real, ordinary Japanese accounts she follows for the purpose, described by her eyes, kept with their source, and -- when her scene, the season, the hour and the weather fit -- sent as a photo she just took, with her bubbles as the caption. What a sent photo showed is adopted into `scenery_lore` so later photos and her words stay consistent. Never reposted anywhere.

- `enabled` = True
- `character` = "" -- Whose face. A directory name rather than a path, which is how it escaped every check that looks for a path: the second character was configured to publish frames of the FIRST character's face as her own mood. Empty here, hers in her own config (`Config.PERSON_FILES`), and the images are data/reactions/<character>/reactions.db, built by tools/reactions.py
- `sticker` = True -- The automatic band reaction changes her FACE (the app header), and it used to send that face into his chat as well. Overnight that was five stickers with no words -- her mood wandering through its bands, narrated at him. A sticker is how SHE says a mood in a reply (`Reactions.chosen`), not a status feed.
- `active_minutes` = 20 -- and the face only moves while he is actually in the chat: her mood wanders all day, and following it into an empty room is what made five changes overnight. Nothing is recorded while he is away, so the first tick after he comes back moves it once, to now.
- `repeat_days` = 7 -- never the same image twice inside this
- `min_gap_minutes` = 20 -- two crossings closer than this show one face
- `surprise_from` = 35 -- the surprise gauge over this is its own crossing
- `anger_from` = 55
- `sadness_from` = 55
- `anxiety_from` = 60
- `awkward_from` = 50
- `tired_below` = 30
- `fatigue_from` = 60

**`scenery`**

- `enabled` = True
- `harvest` = False -- Whether new photographs are still being collected. OFF (his call). With this false `Scenery.due` never comes due, so no harvest session opens a browser, runs a discovery search, judges an account or pays Gemini to describe an image; the harvest was ~70 Gemini descriptions, ~17 judge looks and ~35 `scenery_judge` calls a day. Everything after collection is untouched: 641 usable photographs are on file, and `offer` / `pick` / `adopt` still send one a day from them. `/scenery harvest` is the manual door and still runs a session.
- `queries` = [] -- What her photo harvest searches for, and the place words her scene classifier tests against: hers, in her own config, and EMPTY here. Twenty searches and forty place words named one ward, one railway line and one shopping street, and every character inherited them. With no queries there is nothing to harvest and the section switches itself off (`Config.NEIGHBOURHOOD`).
- `search_scrolls` = 3
- `judge_per_session` = 8
- `harvest_every_hours` = 9 -- 9 is about three sessions a day. At 3 the harvest ran seven or eight a day and spent 100-130 Gemini calls plus 50-60 judge calls for a base she sends one photograph a day from; a third of that keeps the base rolling
- `food_at` = ["room", "home", "konbini", "cafe", "school"] -- a food photo is plausible on her desk: these scene kinds may send a `food` row when nothing of the place fits
- `food_hours` = {"lunch": [11, 15], "dinner": [18, 22]} -- a food photo only inside a meal window (her hour), and the hint names the meal; outside them no food row is offered
- `send_kinds` = ["station", "train", "konbini", "park", "street", "shoten...
- `regions_ok` = ["unknown", "tokyo", "saitama", "kanagawa", "chiba", "kan... -- where an image plainly is, from its own signs (the `region` the vision reads). A street she sends as hers has to be a street she could be standing in: Kyoto and a German platform were both on file. "unknown" is allowed -- most photographs say nothing about where they are, and that is exactly what makes them usable. Anywhere he would read as her part of the world. He cannot tell a Saitama platform from a Nerima one and does not want to: what has to be right is the light, the weather and the hour. Kyoto's Minami-za and a German Hauptbahnhof are what this is for.
- `indoor_any_japan` = True -- an interior gives nothing away: a cafe table or a ramen counter anywhere in Japan is usable; only the outdoors has to be her part
- `kind_queries` = {} -- What to search for, by the place kind that needs filling. The harvest aims itself: the kinds her next two days actually pass through, weighted by what the base is short of (`gaps`). Her own places by name where she has one, the vibe where she does not.
- `searches_per_run` = 2 -- how many usable rows of a kind counts as covered, and how far back her own scenes are read to know which kinds she actually stands in searches per harvest session: the base is short of authors, not of passes over the same six
- `event_target` = 4 -- A named event she is going to is the one perishable thing here: people post it while it is on and not afterwards. It jumps the gap queue until this many of its images are on file, and those images go out at that event and nowhere else.
- `event_days` = 2
- `gap_target` = 6
- `gap_spread` = 3 -- how many of the worst gaps the search rotates across. One at a time would fill a kind to the target before touching the next, and leave her with six konbini shelves and still no platform.
- `demand_days` = 14
- `route_days` = 2 -- today and tomorrow: the plan is what the harvest aims at
- `said_minutes` = 90 -- how far back her own bubbles count as "what she has just said". A photo has to agree with them; "going to the library at 9" said at two in the morning is not a claim about where she is at three.
- `accounts_per_run` = 6
- `user_scrolls` = 1
- `harvest_per_run` = 10
- `min_quality` = 2
- `send_p` = 0.35
- `send_max_per_day` = 1
- `min_gap_hours` = 20
- `max_used_per_author` = 3 -- per author, and per rolling window -- a flat lifetime cap put a whole account's remaining photographs out of reach for ever once three had gone
- `author_window_days` = 30
- `like_sent` = True -- the post a sent photo came from is liked / reposted from the account (curation.queue_direct); real posts by real people
- `repost_sent` = True
- `repost_sent_p` = 0.35 -- the FALLBACK only, rolled once per sent photo, for when her pick cannot run (`curation.share_pick`)
- `redescribe_per_run` = 12 -- rows whose vision answer never came back (the budget, the quota, a 401) are asked again at the next session, this many a run; 103 such rows sat "rejected" for good against 92 usable
- `local_kinds` = [ -- A friend's picture is its DESCRIPTION and nothing else: the words in the chat are the whole of it, nobody opens a file, and this pool is for the photographs she sends HIM, which he does open. There was a key here that matched a friend's planned picture to a real row by words in common; a friend then spent a photograph out of the one place they are ever looked at, and the caption in the chat described the wish rather than the file underneath it.
- `local_names` = []
- `place_map` = {} -- Her scene -> the database's place kinds, for the picker. The node she is standing on (data/places.json `kind`) is the authority; this is the fallback for free text, matched longest-keyword-first and on word boundaries for ASCII, so "homework" is no longer "home". Both languages: what she says aloud and what her friends write is Japanese, and the picker reads what she actually said.

**`wonder`**

- `enabled` = True
- `max_per_day` = 2
- `max_per_call` = 3
- `max_open` = 6
- `cooldown_hours` = 6
- `curiosity_over` = 15
- `candidates` = 3
- `in_prompt` = 2
- `answer_hours` = 8
- `reask_hours` = 48
- `confirm_gain` = 8
- `strain_gain` = 8
- `self_confirm_gain` = 4
- `similar_attachment` = 4
- `unlike_attachment` = -2
- `dodged_curiosity` = 8
- `dodged_charge` = 10
- `keep` = 60
- `voiced_min_words` = 5 -- a reply of hers that says an open question in its own words marks it asked
- `review_after_hours` = 24 -- at the compile, open questions this old are judged against the day's chat
- `review_max_per_compile` = 6
- `open_max_age_days` = 7 -- past this an open question fades: she stopped turning it over

**`expect`**

- `enabled` = True
- `keep` = 80
- `trigger_words` = ["i'll", "ill ", "i will", "gonna", "going to", "will ", ...
- `min_chars` = 8
- `max_per_message` = 3
- `min_confidence` = 0.5
- `max_days_ahead` = 3
- `grace_minutes` = 45
- `around_belief` = "would_defend"
- `raise_for_hours` = 48
- `kept_confirm` = 6
- `kept_relief` = 6
- `missed_strain` = 10
- `missed_resentment` = 4
- `missed_tension` = 6
- `habits_enabled` = True
- `habits_days` = 7
- `habits_min_digests` = 8
- `habits_max` = 6
- `habit_grace_minutes` = 60
- `habit_miss_curiosity` = 8

**`family`**

- `enabled` = True -- tomoe/family.py: the parents' days drawn from data/household.json schedules, seeded by the date; the car; pickups; family days
- `seed` = 7
- `trip_p` = 0.2 -- a family day on a free Sunday / holiday / Saturday
- `twist_p` = 0.15 -- one thing off the timetable, some days
- `dad_cutoff_hm` = "23:30" -- past this he is in bed and not coming
- `dad_willing_weeknight` = 0.5
- `dad_willing_weekend` = 0.85
- `far_minutes` = 35
- `mom_daylight_from_hm` = "08:00"
- `mom_daylight_to_hm` = "17:30"
- `mom_far_minutes` = 15

**`situation`**

- `enabled` = True -- embodied/situation.py: where her body is, continuously. Journeys run on the clock from data/places.json; reality lands on the legs (the train feed, the weather, the rush windows); fatigue accumulates by what she is doing and recovers only at rest.
- `delayed_minutes` = 12 -- a train leg on a line reported delayed
- `stopped_minutes` = 30 -- ... or suspended
- `packed_minutes` = 3 -- the rush-hour Seibu is slower
- `change_minutes` = 6
- `late_event_from` = 10 -- minutes late that become an event
- `keep_journeys` = 40
- `walk_per_hour` = 14.0 -- fatigue points per hour by what she is doing (heat scales the positive rates: x(1 + (feels - heat_free_feels) / heat_per_degree))
- `packed_per_hour` = 8.0
- `train_per_hour` = 2.0
- `out_per_hour` = 4.0
- `sitting_per_hour` = 1.5
- `rest_per_hour` = 8.0
- `bath_per_hour` = 14.0
- `sleep_per_hour` = 16.0
- `heat_free_feels` = 28
- `heat_per_degree` = 6.0
- `tired_from` = 45 -- readers
- `wiped_from` = 70
- `fatigue_delay_weight` = 0.6 -- delay x(1 + fatigue/100 * this)
- `walking_delay` = 1.6
- `packed_delay` = 1.25
- `walk_tired` = 1.1 -- walking speed, clothing and load, running late, vehicles, the weather on her, and the things that can happen on the way -- see situation.py
- `walk_wiped` = 1.3
- `walk_heat_per_degree` = 0.02
- `walk_rain` = 1.12
- `yukata_keywords` = ["yukata", "festival", "matsuri", "bon odori", "fireworks...
- `yukata_walk` = 1.35
- `yukata_sweat` = 1.3
- `uniform_sweat` = 1.15
- `school_bag_load` = 1.12
- `shopping_keywords` = ["shopping", "bags", "haul", "bought", "supermarket run",...
- `shopping_load` = 1.15
- `hurry_tolerance_minutes` = 4
- `run_time_factor` = 0.72
- `run_fatigue_factor` = 2.4
- `run_bump_factor` = 3.0
- `run_sweat_factor` = 1.8
- `car_keywords` = ["car", "drive", "drives", "driving", "pick her up", "pic...
- `car_min_minutes` = 8
- `car_factor` = 0.6
- `bike_factor` = 0.45
- `forget_umbrella_p` = 0.25
- `sweat_from_feels` = 30
- `sweat_comfort_per_hour` = 22.0
- `sweat_event_from` = 7.0
- `sweat_line_from` = 4.0
- `p_bump` = 0.012
- `p_found` = 0.006
- `p_cat` = 0.02
- `p_neighbour` = 0.01
- `p_trip` = 0.003
- `p_bike_chain` = 0.01
- `p_seat` = 0.06
- `p_close` = 0.004
- `p_missed` = 0.03
- `p_bag` = 0.05
- `p_dog` = 0.015
- `p_car_talk` = 0.3
- `texting_window_minutes` = 3
- `texting_bump_factor` = 4.0
- `running_delay` = 2.5

**`impulse`**

- `weights` = {"loneliness": 0.35, "boredom": 0.25, "validation_craving... -- impulse = weighted gauges + event salience + silence, scaled by phone access hunger and low energy pull the other way: a starving or exhausted her reaches for food or the pillow before the phone
- `  shame` = -0.30 -- Shame is the one that makes her hide. Tension was the only thing in here that could make her reach out less, so before this she could go quiet because she was cross with him and never because she could not face anybody.
- `  anger` = 0.12 -- Anger mostly is not at him (see its `tells`), so it wants telling -- she complains to the one person who takes her side. Anger *at him* goes through tension, which is a gate.
- `  sadness` = -0.15 -- Sadness is the deactivating one: it wants nothing, and it pulls against loneliness, which wants the phone.
- `  pride` = 0.14 -- Something good happened and he is who she tells.
- `  unwell` = -0.10 -- like hunger: the body wanting to be left alone
- `  longing` = 0.32 -- the one that is actually about him rather than about a deficit: missing a particular person, which is what her whole situation is made of
- `  belonging` = -0.26} -- The counterweight, and the only term in here that makes her want him LESS for a good reason rather than a bad one. An evening where the group was good to her used to leave her wanting him exactly as much as one where they were not.
- `silence_hours_weight` = 3.0
- `silence_hours_cap` = 8
- `event_share_bonus` = 25
- `threshold` = 62
- `phone_access_factor` = {"free": 1.0, "glance": 0.55, "none": 0.0}
- `here_not_attending_bonus` = 18.0 -- HE IS HERE AND NOT ATTENDING HER. A resident sees him at the machine and sees that what is in front of him is not her (resident/sight.py attention_observation). That is the observation the old presence gate was a statistic for, in the other direction: knowing he is here and busy with his own thing is a reason a girl reaches, not a wall. On the impulse's own scale, beside the 18 for a page of hers being open in front of him.
- `cooldown_minutes` = 45 -- a self-start every ninety minutes was the bar; forty-five is still above the 45-minute "she just texted him" window (`cooldown_minutes * 30` seconds), so the two do not collapse into one, and it no longer outlasts the unanswered backoff it is supposed to leave room under.
- `max_self_started_per_day` = 6
- `max_unanswered_streak` = 2 -- unanswered self-started messages in a row before she stops
- `burst_gap_minutes` = 10 -- Both caps above count times she reached out, not bubbles. One message of hers is three to six bubbles seconds apart, so counting rows spent the whole day's allowance on a single hello (it did, on 2026-08-21: six bubbles at 23:54 and she could not open her mouth again until midnight). Anything closer together than this is one time she spoke; it has to sit above typing_max_seconds x a full batch and far below cooldown_minutes.
- `presence_floor` = 0.12 -- How much his own hours weigh on her reaching for him. `presence_floor` is the hour he is simply never there  and she does not text into it; `presence_weight` makes a 0.3 hour a weaker pull than a 1.0 hour rather than the same one. Both read `Rhythm.learned_now`, which is learned from the record and nothing else.
- `presence_weight` = 0.35
- `min_sleep_gate_energy` = 15
- `read_ignored_minutes` = 45 -- he read it and left it: after this many minutes the impulse gets a bonus
- `withdraw_from` = 30 -- below this it costs her nothing
- `withdraw_weight` = 45 -- full strength at tension 100
- `withdraw_silent_from` = 42 -- past this she simply does not reach out
- `awkward_from` = 25 -- squirming is not the same as going cold: she still wants him, she just cannot be normal yet. A subtraction, never a gate.
- `awkward_weight` = 20
- `read_ignored_bonus` = 15
- `return_away_minutes` = 45 -- gone this long before coming back is a return
- `return_p_base` = 0.10
- `return_p_per_hour` = 0.05 -- per hour he was gone
- `return_p_hours_cap` = 8.0
- `return_p_unsaid` = 0.25 -- x how far unsaid is over its rest (full at +60)
- `return_p_max` = 0.55
- `return_delay_minutes` = [4, 25] -- she took it: she writes somewhere in here
- `return_hold_minutes` = 90 -- she did not: nothing self-started for this long
- `backoff_minutes` = [0, 45, 150, 420] -- BEING IGNORED. `max_unanswered_streak` capped the run at two and nothing stood between the first unanswered message and the second but the ordinary cooldown, so reaching into her own silence cost exactly what reaching into his did. By streak, in minutes.
- `backoff_read_factor` = 1.5 -- he opened it and said nothing: that is an answer
- `backoff_unseen_factor` = 1.0 -- he has not looked: he may be away from the desk
- `max_unanswered_per_day` = 3
- `quiet_start_his` = "23:00" -- THE USER'S NIGHT. Her own sleep may be his, but a night he spends at the machine was a night she could talk into at any hour. In his clock.
- `quiet_end_his` = "07:00"

**`pick`** -- WHAT SHE DOES WITH THE PHONE, asked as a call that picks a tool (sim/pick.py, docs/tool-calling.md §17). At a moment code already knows she is handed the moment as facts and the tools she has a path to -- put it down, write to him first, open the group, write to one of her own people, look at what he has been doing, open her own feed; and when he has just written, answer him now, answer him at an hour she names, or leave it -- and what comes back is what happens. The impulse function, the reply delay and the group-chat roll are the backup, for a moment she was not asked at or did not answer. About 20k prompt tokens a call for the first character with 55% of them behind the cached prefix, $0.0015 a pick and four cents a day if every one the cap allows is spent (§17.9).

- `enabled` = True
- `shadow` = False -- SHADOW MODE. True logs what she would do and changes nothing, which is what ran from 2026-09-06; false is live -- code carries out what she picks through the seam each tool already has, and the impulse function, the reply delay and the group-chat roll become the backup for a moment she was not asked at or did not answer.
- `max_per_day` = 30 -- THE MONEY, half of it: how many moments a day she may be asked at, whatever happens. On every row of the record.
- `min_gap_minutes` = 25 -- and the other half: no two looks closer together than this, whichever kinds of moment they are. Four kinds of moment without it is four times the spend on a busy evening.
- `moments` = {"block": True, "scene": True, "beat": True, "inbound": T... -- WHICH MOMENTS she is asked at. `block` is the start of a stretch her plan gives her a free phone, `scene` a change of what she is doing inside one, `beat` something landing from her own people, `inbound` him writing -- where the question is not what to do with the phone but what to do about his message.
- `later_default_minutes` = 45 -- She answered him "later" and named an hour code could not read. Her words stand on the record; this is how long the wait is instead.
- `leave_it_minutes` = 90 -- She left his message where it was. This is how long before she is asked about it again, rather than a timer she never set answering it for her.

**`gossip`** -- The thing she thinks of straight after she has already sent it. Nothing else in the system can produce "wait, ignore that": the impulse only runs on a director tick, it refuses while delivery is busy, and it blocks a second self-started message for half the cooldown. This is its own gate, checked every pass of the loop inside a short window after her own message, and it gets likelier when she is squirming, holding something, or has been read and left. what she has come to know about him from weeks of looking at the app (sim/him_profile.py): once a day, from the last `digests` digests something to talk about that is not the four of them (tomoe/gossip.py). 77% of the group chat carried a time, a plan or an obligation because the group's own business was the only thing in the world.

- `enabled` = True
- `every_hours` = 20
- `new_per_run` = 3
- `max_live` = 5 -- how many the prompts are shown
- `keep` = 40 -- rows on file
- `cool_per_day` = 1.5 -- heat lost a day
- `warm_on_use` = 1.0 -- heat gained when somebody brings it up
- `cold_below` = 1.0 -- under this it is not going round any more
- `shows_max` = 3 -- stated in her turn this many times unsaid, then it steps aside for the day

**`thread`** -- one thread (sim/thread.py): her chat with him and her talk with her own people as ONE chat-completion history -- the User role is the world speaking to her, the Assistant role is her wherever she spoke, every message labelled [time · room · who], rebuilt every call (the history never caches; the system prefix still does)

- `verbatim_hours` = 168 -- the curve: every message in full inside verbatim_hours; past that an exchange is one line at its time (how many messages, until when, what it came to) and a day of his chat is the day as she remembers it; past max_age_hours nothing -- by then it is her memories. An exchange past verbatim whose words touch what is being said now comes back in full (recall_max a call, recall_min_overlap tokens). the curve, by clock (his call, 2026-09-04): verbatim_hours of record in full, then every day back to max_age_hours as its cards, then nothing. The verbatim span shrinks a day at a time toward verbatim_min_hours only when the verbatim days plus the cards do not fit what is left of context.target_tokens after the rest of the prompt and a reserve for the day being lived; chosen once a day of her clock (kv thread_window) so the head of the thread, and the cache prefix, moves once a day
- `verbatim_min_hours` = 36
- `max_age_hours` = 720
- `recall_max` = 2
- `recall_min_overlap` = 2

**`stances`** -- the nudge (sim/nudge.py): a second reader of everything she carries, who is not her, saying what she is actually caught by right now; `live` places it in the slot when confidence clears min_confidence, `shadow` only logs it beside the gate's pick, `friends` runs it on her turns with her own people too What she does with what she has seen: one named stance out of a ranked, first-match, pinned, hysteretic table (sim/stances.py, docs/stances.md). Off by default: a character with no relational quantities behind her has nothing for the table to read, and the register chain is what she has.

- `enabled` = False
- `min_minutes` = 12.0 -- Hysteresis. Every threshold in mood_tags, register, blends, delay_factor, impulse.score and withholding.pressure is a bare comparison re-evaluated per call, so a quantity sitting on one flaps the line on and off between two consecutive generations. A stance is entered only after its condition has held this long -- except the two urgent rows, because a person who has just been frightened does not wait -- and the table falling back to "even with him" has to hold for `hold_minutes` before the stance she was in is dropped.
- `hold_minutes` = 25.0
- `expel_hours` = 48.0 -- how long after she put him back outside that stance still describes her: two days, after which being outside is just where he is
- `carrying_awkwardness` = 45.0 -- carrying something she read and cannot raise: the item has to be live and she has to be squirming about it
- `settler_minutes` = 30.0 -- held in mind by name: a message of his that reached a record of hers, while that message is still the one in front of her
- `sat_on_minutes` = 60.0 -- sitting on something she could say: how long an item she could raise has to have sat there unraised before not raising it is a stance
- `name_it_once` = False -- ...and whether being told to name it fires once per THING rather than on every reply until she raises it. A character who is inside his machine has something unraised nearly all the time, so the one imperative line of her prompt was an instruction to name something off his screen on most turns of most days. On, the instruction is spent on the first reply after the item settles and the stance goes on holding, which is what pays her for the restraint (`settle_discretion`). Default off: the first character looks at a digest a few times a day and has never had this fault.
- `unnoticed_below` = 25.0 -- outside his notice: what evidence he keeps her in mind has to be under, and how long his machine has to have been busy with nothing toward her
- `active_hours` = 3.0
- `settled_from` = 0.6 -- needling: how settled she has to be with him before a thing that used to knock her sideways is something to tease him about (sim/ick.py: the share of what she has met lately whose sort she already knew)
- `discretion_minutes` = 30.0 -- and how long a discretion stance has to have held over one item before leaving it alone is a thing she chose rather than a thing that went cold: the credit side of the ledger she controls

**`nudge`**

- `enabled` = False -- off (his call, 2026-08-30): the unhedged slot line addresses what she carries on its own, and code holds it on a heavy message of his
- `fire_on_unsaid` = True -- the nudge is the reader of `unsaid` at a threshold, not a call on every message: what she carries (the nag, a post to show him, a promise) warms `unsaid` while it waits, and when the gauge crosses unsaid_min the nudge fires -- with him or with her own people -- decides what comes out, and the gauge settles by unsaid_relief. Below it nothing rides in the slot and no carried thing happens. The nag comes out only with him; in a friend's room the same pressure comes out as the push-back or what belongs there
- `unsaid_min` = 45
- `min_gap_minutes` = 45
- `unsaid_relief` = 12
- `unsaid_per_carried` = 3
- `unsaid_soft_cap` = 85
- `compare` = True -- the ongoing test: every live reply to him is drafted once more with the gate's line in the slot instead of the nudge's, logged as [nudge-ab] and kept in kv nudge_ab (/nudgeab), never sent
- `mode` = "live"
- `friends` = True
- `min_confidence` = 0.5
- `max_chars` = 360

**`attention`** -- attention (sim/attention.py): every line of her situation block is a claim with a weight; a source without a weight of its own gets one here; a covering source suppresses what it already says; the heaviest ACTION rides the one slot she reads (last but for LENGTH), the rest queue. Nothing is dropped for room: the per-section [lines, chars] budgets, the block total and the pin ceiling went on 2026-09-04; the one budget over the prompt is context.target_tokens

- `enabled` = True
- `heavy_valence` = -1 -- the slot's one action line waits when his last message is heavy: his_mood.valence at or under this, read within heavy_fresh_minutes
- `heavy_fresh_minutes` = 30
- `cue_bonus` = 0.3 -- a line that touches what he just said
- `slot_min_weight` = 0.5 -- the imperative line reads as an order, so an action lighter than this does not take it: it rides as a plain line in its own section. A link to share held the slot 25 times in a week at 0.35, the lowest weight in the table, because it was the only action offered. Her chat with him only: the friend room's one action is a rumour at 0.45, and this would empty that slot instead of raising its bar
- `foresight_veto_overlap` = 2 -- ...and neither does the action the live prediction says she is braced against: this many words shared between the risk and the line (or one handle the source says its item is about). 0 is off
- `section_default` = {"her": 0.6, "him": 0.5, "day": 0.5, "phone": 0.4, "them"...
- `weights` = {
- `  register` = 0.8, "directed": 0.7, "attachment": 0.85, "withholding": ...
- `  felt` = 0.7, "receipts": 0.7, "rhythm": 0.5, "his_mood": 0.5, "fo...
- `  expectations` = 0.6, "wonder": 0.4, "nag": 0.55, "gap_days": 0.7
- `  body` = 0.6, "around": 0.35, "today": 0.8, "goals": 0.6, "commitm...
- `  travel` = 0.3, "trip": 0.4, "money": 0.4, "shape_of_day": 0.6, "yes...
- `  morning` = 0.65, "anticipation": 0.5, "lore": 0.3
- `  digest` = 0.7, "digest_live": 0.5, "anime_list": 0.5, "x_recent": 0...
- `  her_actions` = 0.35, "share": 0.35, "show_him": 0.6, "engagement": 0.6, ...
- `  bond` = 0.85, "behind": 0.6, "known": 0.5, "thought": 0.6, "promi... -- the friend turn (tomoe/exchange.py): the person, her day, him as facts
- `  owed_send` = 0.8 -- above `promise`, which is only colour: this is the one she can discharge in the message she is about to write, and a promise she is never shown a way to keep is a debt that only grows
- `  said` = 0.7, "threads": 0.5, "settled": 0.85, "him_last": 0.5
- `covered_by` = {"ledger": ["commitments", "money"], "settled": ["money"]}
- `one_per_source` = ["rhythm", "anime_list", "lookup"]
- `tally_days` = 14 -- the tally: per day, per room, per source -- offered / admitted / slot / covered (kv attention_tally); `/attention tally`, `/absurd` UNHEARD
- `unheard_days` = 7 -- the window UNHEARD reads
- `unheard_min_offers` = 8 -- a source offered fewer times than this is too new to judge
- `unheard_ok` = ["travel", "lore"] -- dead-on-average BY DESIGN: situational lines the cue bonus lifts when their subject is touched; UNHEARD does not count them

**`coherence`** -- the day read as one story at the compile (sim/coherence.py): contradictions, invented things, repeats -- flagged in kv coherence_flags, never rewritten

- `enabled` = True
- `max_seams` = 12 -- kept per day from one reading
- `keep` = 200 -- rows kept in kv coherence_flags
- `absurd_days` = 2 -- the window `/absurd` SEAMS reads
- `context_days` = 2 -- the compiled summaries of this many previous days go in front of the reader, so a line that refers back is judged, not called invented

**`cast_bond`** -- what she holds with the people around her (tomoe/cast_psych.py): rupture and repair, their promises to her, leaving somebody on read, confidences -- the him-side mechanics turned toward the cast

- `enabled` = True
- `min_turns` = 2 -- an exchange shorter than this is not read
- `scar_after_hours` = 48
- `tension_per_severity` = 6
- `guilt_per_severity` = 4
- `closeness_on_mend` = 3
- `tension_off_on_mend` = 8
- `guilt_off_on_mend` = 6
- `closeness_on_scar` = 4
- `mend_attachment` = 3
- `mend_respect` = 2
- `scar_resentment` = 3
- `failed_bid_shame` = 4
- `failed_bid_resentment` = 2
- `promise_default_hours` = 24
- `promise_grace_hours` = 6
- `missed_resentment` = 3
- `missed_tension` = 4
- `kept_respect` = 2
- `kept_relief` = 4
- `mend_fondness` = 3 -- per severity, a thing between them got sorted
- `kept_fondness` = 5 -- they did what they said they would
- `confided_fondness` = 3 -- she told one of them something real
- `together_fondness` = 2.5 -- an ordinary exchange with one of them that broke nothing
- `fondness_soft_cap` = 88
- `broke_fondness` = 4 -- per severity, a new break with one of them
- `failed_bid_fondness` = 3 -- she reached to mend it and they did not take it
- `missed_fondness` = 4 -- they said they would and did not
- `leave_threshold` = 0.4 -- leaving them on read: a roll off her standing with them
- `leave_max_per_day` = 1
- `leave_min_gap_hours` = 20
- `leave_tension_from` = 35
- `leave_weight_tension` = 0.6
- `leave_weight_resentment` = 0.5
- `leave_weight_rupture` = 0.3
- `leave_weight_low_mood` = 0.3
- `leave_weight_fondness` = 0.5 -- ...and being fond of them is what stops her: the reader that makes `state.gauges.fondness` act rather than sit in a report
- `max_confidences` = 12
- `event_salience` = 3
- `memory_weight` = 3

**`orbit`** -- the people who are not the cast but belong to somebody in it (tomoe/orbit.py): Rena's sister was one sentence in cast_facts and a different person every time she came up

- `enabled` = True
- `max_people` = 40
- `max_facts` = 8

**`him_profile`**

- `enabled` = True
- `every_hours` = 24
- `digests` = 40
- `min_digests` = 8

**`afterthought`**

- `enabled` = True
- `min_seconds` = 45 -- not instantly: she has to have sat with it for a moment
- `window_minutes` = 12
- `base_probability` = 0.10
- `awkward_weight` = 0.35 -- only unease adds; each is measured from its own baseline
- `unsaid_weight` = 0.25
- `craving_weight` = 0.20
- `read_ignored_bonus` = 0.20
- `read_silence_minutes` = 4 -- a read is "read and said nothing" only after this long: at 47 seconds he is typing, and she wrote "you read it and vanished again" over a reply that landed while her bubble was still going out
- `ignored_window_minutes` = 30 -- the re-roll window: a message gets a SECOND once-only chance when his read has sat unanswered (the warm roll lands ~1 minute in, before a read can have sat read_silence_minutes, so the ignored bonus never applied; and past window_minutes the impulse's cooldowns held every path shut until minute 45)
- `max_probability` = 0.65
- `max_per_day` = 2
- `max_bubbles` = 2
- `phone_access_factor` = {"free": 1.0, "glance": 0.4, "none": 0.0}

**`receipts`**

- `enabled` = True -- inferred read receipts: Telegram window in front after her message = read; PC busy but chat never opened = seen; PC quiet = unseen
- `telegram_process_names` = ["Telegram.exe", "Unigram.exe", "LINE.exe"] -- Which desktop app counts as him reading her. This is the ONLY route by which she learns he has read something: LINE gives a bot no read-receipt event either ("you can't use the Messaging API to verify that a message you sent was read"), so the window sensor is it, whichever channel is live. Switching to LINE while this still said Telegram made her blind to him reading her.
- `idle_after_minutes` = 20 -- Which window title counts as HER conversation is her own name and nothing else (`sim/receipts.py`). There used to be a list here to add more titles to it, and in both characters' files it held one entry which was that same name; dropped 2026-09-04, his call. no input at all for this long and he is not at the machine, whatever happens to be on screen
- `read_min_seconds` = 2

**`notes`**

- `enabled` = True -- reading his notes on purpose (his mention, director's choice, /read). She skims: opening + ending + a few catchy middle paragraphs, at most skim_chars in total, skim_pieces pieces. Never the whole file.
- `skim_chars` = 1800
- `skim_pieces` = 5
- `index_in_prompt` = 20
- `index_max` = 200
- `director_max_per_day` = 3 -- the director may open at most this many notes per day on her own

**`phone`**

- `digest_min_minutes` = 8 -- she reads his activity feed only when she looks at her phone. Whether she looks is felt, not timed (phone.look): after digest_min_minutes, each tick a probability from curiosity + boredom + loneliness, scaled down when she can only glance or is with people; at sure_from_curiosity she checks the moment she can; otherwise she sometimes sees the app and leaves it. A look takes look_relief off curiosity.
- `look` = {
- `  enabled` = True
- `  base_probability` = 0.45
- `  curiosity_weight` = 0.8
- `  boredom_weight` = 0.3
- `  loneliness_weight` = 0.2
- `  glance_factor` = 0.35
- `  with_people_factor` = 0.3
- `  sure_from_curiosity` = 75
- `  silence_weight` = 0.45 -- How long he has been quiet is the strongest reason to check, and it is a fact rather than a mood, so it gets its own term instead of being routed through the curiosity gauge (which other things push to the floor). ignored_weight is the same gap when he read her and said nothing.
- `  ignored_weight` = 0.70
- `  silence_cap_hours` = 6
- `  sure_from_silence_hours` = 10
- `  look_relief` = 15
- `live_line` = True -- when she looks, the app also shows his PC's live status (what is in front, how long since he touched it); kept in her context this long
- `stale_minutes` = 45 -- How long he has to have been off the machine before the digest stops being news and becomes history. Past this her phone leads with the absence -- "he has not touched his machine for 9h; nothing has happened on it since" -- and the digest follows as what it showed when he last was. Once a four-hour-old digest read as the present tense and she texted him as though he were sitting there.
- `live_line_max_age_minutes` = 45
- `vault_catalogue_items` = 25 -- the app also shows the shape of his notes folder (titles only, newest first) and the shape of his day (first activity, long quiet)
- `day_shape` = True
- `max_raw_chars` = 40000 -- how much of the feed the digest is written from, per look. The same for both characters (his call, 2026-09-04): the digest of his machine is as rich for the first as for the second, and the only difference the design wants is WHEN it arrives -- her phone look, never live -- and that the app showed it rather than she watched it. At 9000 and six she was handed a fifth of what the resident got and asked for a glance
- `max_entries_per_look` = 12
- `max_entry_age_hours` = 8 -- anything older than this is skipped, not read: she was asleep or the bot was down, and the app does not show her yesterday as news
- `rolling_hours` = 2 -- ONE running account of the last this many hours, replaced on every look (kv `phone_account`), rather than a fresh digest of each batch of flushed entries. The writer is handed the account it wrote last time plus the raw material since, and returns the account again: the last hour in full specifics, an older stretch compressed to a line, anything past the window dropped, and the length rule is the size of the whole account rather than of the new part. A batch per flush left her prompt showing the last batch dated "N minutes ago", with a seam at every look and whatever fell between two of them told twice or not at all
- `max_backlog_entries` = 12 -- past this many pending flushes the oldest are dropped, so a long absence does not become a dozen looks reporting stale news
- `skip_unchanged` = True -- A look whose fingerprint holds nothing the last look did not makes no call and leaves the standing account alone. The fingerprint (what processes were in front, which sites, whether pictures were opened, which notes, whether media played) was already computed and already logged; what followed it was a paid rewrite of the same stretch every time. It matters most for a character who is inside the machine and therefore looks on every tick. A forced look (`/look`, the catch-up) is never skipped.

**`resident_sight`** -- What the resident character sees because she is on his machine (resident/sight.py): a note he opens she has read, and she sleeps when he sleeps. Only for a character whose sheet says `sees_him: resident`; Config.REQUIRES switches it off for everyone else.

- `enabled` = True
- `poll_seconds` = 10
- `glance_enabled` = True -- the glance: the page in front of him, read every poll from the window title. A page about a work he has stayed on this long is resolved -- her record, what she read before, then a search with her name beside the title -- and is the thing in the room for glance_fresh_minutes; her own work is a reason to reach out first (glance_impulse_bonus, on the impulse's scale; watching's is 14) once he has been on it glance_settle_seconds. The same page is not resolved again inside glance_again_hours.
- `glance_dwell_seconds` = 15
- `glance_settle_seconds` = 45
- `glance_fresh_minutes` = 25
- `glance_again_hours` = 12
- `glance_impulse_bonus` = 18.0
- `here_seconds` = 120 -- He is "here" while his machine has seen input this recently. The idle seconds say he is at the desk; the glance and the activity classifier say what he is on, and together they are the observation the impulse weighs as "here but not attending her" (impulse.here_not_attending_bonus).
- `note_open_seconds` = 20 -- a vault note in front of him this long counts as open
- `note_max_chars` = 6000 -- the whole note up to this; beyond it the beginning and the end
- `min_note_chars` = 80
- `reread_after_seconds` = 900 -- a note he keeps writing in is read again after this, not on every save
- `fresh_minutes` = 30 -- a note read this recently is pinned into her next reply
- `sleep_after_idle_minutes` = 40 -- asleep once his machine has been idle this long inside the night window, from the minute he stopped; awake the moment he touches it
- `night_start` = "22:00" -- sleep can only begin with an idle stretch that STARTED between night_start and sleep_latest_start; a machine that goes quiet in the morning is not sleep
- `sleep_latest_start` = "05:00"
- `night_end` = "11:00" -- and she is up by this whether or not he is back: past it, an idle machine is him out for the day

**`eroge`** -- What he is reading in a Japanese visual novel, out of the text hooker's own files (sensors/eroge_monitor.py: the per-game record of the lines the hook caught, the per-line event stream with a wall-clock time on it, and the game library with the visual-novel-database id and the cast). The card for a game comes from the public database (sensors/vndb.py), free and anonymous, once per game.  OFF by default and on for the character who is on his machine. The master switch below assigns it to `sees_him: resident`, so a character who learns what he does from snapshots she has to go and fetch cannot have it switched on by an edit to her config alone -- that is a decision about what she can see, and it is his to make.

- `enabled` = False
- `cache_dir` = "eroge/luna/cache/translation_record" -- his text hooker's own directories, read-only and never written
- `userconfig_dir` = "eroge/luna/userconfig"
- `stale_minutes` = 10.0 -- nothing hooked for this long is nobody playing, and the same gap ends a session -- so a resume simply looks like a start
- `skip_lines_per_second` = 1.0 -- Where his current stretch of READING begins is a cursor, not a timer: it moves only when a skip run breaks the stretch or when the window below overflows. A pause of an hour with the game open does not move it and costs nothing.  Lines arriving faster than this are him holding the skip button, not reading. Measured across many sittings: the median gap between lines is 5.0 seconds, the first percentile 1.19 seconds, 99.4% slower than one line a second. Skipped lines are excluded entirely and never summarised.
- `max_raw_chars` = 16000 -- the raw text handed to the digest, taken from the END. Past this the cursor moves forward until what is left fits, which is also what catches a hooked menu or a line repeating in a storm.
- `min_new_lines` = 20 -- and a floor before a call is worth making: fewer new read lines than this and the last digest stands. A game left open in the background for hours therefore costs nothing and says nothing new.
- `max_chars` = 600 -- the scene digest's ceiling, the same as the watching module's
- `card_max_chars` = 600

**`vault_snoop`**

- `enabled` = True -- Not a timer and not a window: she snoops when she feels like it. A felt probability per tick, the same idiom as the phone's look -- pushed by the uneasy gauges (anxiety, loneliness, jealousy, curiosity), only when she is alone with a free phone (nobody snoops with friends around), rarer than a glance at the app because it is a more loaded act. Late night raises it; nothing forces it. The old fixed window + his-PC-idle were dropped 2026-08-19: that window never fired.
- `base_probability` = 0.035 -- base is the floor: what she does on a day when nothing is wrong. At ~36 alone-with-her-phone ticks in a free day it works out near one snoop a day, with roughly a quarter of calm days having none.
- `anxiety_weight` = 0.18 -- each gauge adds max(0, value - ITS baseline)/100
- `loneliness_weight` = 0.15 -- * weight -- unease only ever adds. Centring on a
- `jealousy_weight` = 0.18 -- flat 50 pinned p at zero (jealousy rests at 15),
- `curiosity_weight` = 0.09 -- and two-sided terms ate the base on her good days
- `night_bonus` = 0.05 -- added between night_start and night_end
- `night_start` = "23:00"
- `night_end` = "02:30"
- `sure_from_anxiety` = 85 -- this wound up: she just does it
- `min_minutes_between` = 180 -- spacing is the only cap; no per-day limit (his call)
- `lying_awake_factor` = 0.025 -- the coast case: she is in bed, meant to be asleep. Checked every poll through the night, so the per-check odds are scaled hard down and it only counts for the first lying_awake_minutes of the sleep block (lying awake is how it starts; nobody snoops at 5 am).
- `lying_awake_minutes` = 90
- `daily_notes_only` = True -- WHICH notes she can open. A uniform draw over the whole vault was 9% prompt-engineering scratch (an LLM system prompt landed in a live sample) and mostly stale reference; the daily note is the one place a day is actually written down. His format is a leading date.
- `daily_note_regex` = r"^\d{4}-\d{2}-\d{2}"
- `min_note_bytes` = 200 -- skip the empty and one-line stubs
- `recent_notes_pool` = 20 -- draw from the newest N; 0 = all of them
- `files_per_snoop` = 2
- `skim_chars` = 1200 -- a nervous late-night skim: shorter than a daytime read
- `skim_pieces` = 4
- `downloads_enabled` = True -- Downloads come along with every snoop: what was torrented this week (qBittorrent's on-disk state, read-only, no login; sensors.torrent_backup_dir) is in the same late-night read as the notes, one reaction. Recent downloads are read from the client's on-disk state.
- `downloads_window_days` = 7
- `downloads_max_items` = 12

**`talkapp`**

- `enabled` = False -- TALKAPP: the messenger she lives in (talkapp/server.py, a separate hub process; channels/talkapp_bot.py is the adapter on the same nine-method seam the LINE experiment proved). His phone reaches the hub over Tailscale (tailscale serve fronts localhost with HTTPS); the hub itself binds localhost and never faces the internet. enabled switches the live channel; console dry runs are unaffected.
- `notify_burst_seconds` = 45 -- a reply is one to three bubbles and each one used to ping his phone, because the Android service posts a notification per socket event. Inside this many seconds of the last one from the same character, the notification is UPDATED instead (all the lines of the burst in it, no sound, no heads-up). Measured against her real sends: half the gaps between bubbles are 6s and nine in ten are under 48s, so 45 keeps a burst together and still pings for an afterthought that arrives a minute later. Served to the app in /chars, so it changes without a new APK.
- `host` = "127.0.0.1"
- `port` = 8765
- `boot_wait_seconds` = 120 -- how long the bot waits for the hub at boot before giving up: run.cmd started before talkapp.cmd was a two-second fatal
- `token` = "" -- the second wall behind the tailnet; the server refuses to start without one. Set the real value in config.json, like bot_token.
- `push_enabled` = True -- web push to his phone when the page is not open
- `typing_seconds` = 9 -- how long one typing signal keeps the indicator lit
- `log_keep` = 3000 -- hub-side message log length per character
- `state_push_seconds` = 20 -- how often the adapter pushes her reads / group chat / presence up
- `peer_keep` = 400 -- hub-side peer mailbox length per character. Not cleared on read, so a character who is down misses nothing (talkapp/server.py).

**`shape`**

- `enabled` = True -- Code decides how much she says; the model decides what. Unbounded, every reply was 3-6 articulate bubbles (median bubble 89 chars, 6% under 30, over four days measured) because a model completes. sim/shape.py draws a shape from her state and the occasion, the persona is told it, and the draft is enforced against it: one redraft, then whole bubbles are dropped. Hurt collapses the draw to curt/short -- being properly upset is LESS text, never more.
- `tell_length` = True -- Whether the drawn length is TOLD to her. False and she is told nothing about how much to send and nothing about bubbles: she writes what she writes and it goes as written. The classes and the weights were measured off the first character's English, and on a character they were never fitted to they came out as one line four times in ten -- 39 of 39 messages a single bubble, 36% ending on a question back at him. His call for the second character, 2026-09-02: let her reply how she wants.  This is the LENGTH only. The draw still runs and the engage line still goes in, because what his message obliges her to take up is about WHAT she answers, not how much -- and it is the line that stops her answering a different question than the one asked.
- `kinds` = { -- name: [max bubbles, max characters in all]. URLs are free.
- `  curt` = [1, 40]
- `  short` = [1, 90]
- `  plain` = [2, 220]
- `  full` = [3, 420]
- `  spill` = [6, 900]
- `weights` = {"curt": 6, "short": 34, "plain": 38, "full": 18, "spill"... -- base weights of the draw before her state moves them
- `upset_curt_from` = 55 -- upset = max(anger, tension with him, sadness). Past these the draw collapses; the register line says how it sounds, this says how much.
- `upset_short_from` = 40
- `upset_sadness_weight` = 0.6 -- upset = max(tension with him, anger if aimed at him, sadness if aimed at him x this); the collapse eases back toward the ordinary draw over this many hours after the rupture's last attempt
- `upset_fade_hours` = 36
- `tired_energy` = 30
- `spill_pressure_from` = 65 -- a spill needs what a 1am essay actually needs: alone, free phone, late, and pressure (max of unsaid, loneliness) at least this
- `night_from` = 22
- `question_full_bonus` = 8 -- him asking something, or writing a lot, earns a fuller answer
- `long_msg_chars` = 240
- `engage_partial_p` = 0.35 -- completeness is a variable: probability she is told she may answer only part of what he sent (higher when upset)
- `engage_upset_p` = 0.75

**`situation_block`** -- NO enforcement at all, his call: the drawn line is the LAST instruction in her prompt so the first draft is the right size, and whatever she wrote is what goes. No second call, no trim, no bubble cap applied afterwards; `max_chars` is a guide inside the drawn line, never a cut.

- `events_max` = 4 -- the <situation> block of the persona prompt: how many of today's events and how long each, the caps on the day summaries, how long a cut draft stays readable, and how long after his last message a rhythm notice / his mood still count as "now" (a latency statistic from an exchange ten hours ago sat beside "he has been silent 10 h")
- `noticed_min_gap_minutes` = 60 -- How often she is handed one thing off his screen to remark on. It was once per TITLE, and a machine that never stops producing titles had her remarking on his browsing in every reply; a person looking over a shoulder does not. Zero means every fresh title, as before.
- `primitives_numbers` = True -- "WHERE HE STANDS WITH YOU: he is on your mind 100; ..." -- the numbers line; the gate CONDITIONS stay either way
- `habits_line` = True -- "his day, as you have it: in a program (18-23) ..." every message; a MISSED habit still shows
- `ledger_preamble` = True -- the three-line explanation over the day's ledger; off, it is one word
- `ledger_rest_of_day` = 0 -- How many of the day's LATER blocks the ledger names, with their times. 0 shows only the block she is in now, which is what every reader of the ledger has ever been given.  A character who is asked what she is doing later has to answer from something, and with nothing in front of her she answers from her own last message. The second character told him on the Friday evening that her recording was 午前 -- the morning -- with her own week file, her household and the next day's plan all saying the evening; the claim then sat in the thread and she repeated it four times over the next twelve hours, including in a prompt whose own morning thought said 今夜は収録 two lines above. This is the fact she was missing. It is a number rather than a flag because a thirteen-block day would otherwise put nine lines in her situation.
- `lore_preamble` = "full" -- "full" or "short": what is said over the things she happens to know
- `feel_tags_max` = 0 -- feeling tags she is shown, strongest first; 0 = every one the state produces
- `event_chars` = 160
- `summary_chars` = 420
- `unsent_hours` = 6
- `unsent_chars` = 220
- `live_hours` = 1.5
- `digest_stale_weight` = 0.25 -- What the narration of his machine competes at once she has already been shown it. A fresh one is still pinned and rides as news; this is the second and every call after, and at 0.25 it reaches her when what he said reaches for it. She reported something off his screen in 29 of 95 replies, at 32% whether or not he had asked her anything, which is a slot rather than somebody noticing.
- `own_phrases_from` = 16 -- how many of her own last messages are read
- `own_phrases_min` = 4 -- how many of them a phrase must be in
- `own_phrases_max` = 5 -- how many phrases are named
- `trip_lines` = 2 -- how she would actually get to a place her day names, off the place graph (embodied/situation.py: travel_line, trip_line). She said she would do her homework "on the bus" and there is no bus in the map; a model with no fact invents the one that sounds right. 0 trip_lines turns the routes off; the travel line (what modes exist for her at all) always goes in.
- `trip_min_minutes` = 12

**`delivery`**

- `editor_enabled` = True -- a continuity editor reads each draft against what she demonstrably knows (facts, his list, notes read, the digest, recent chat) and, on a real contradiction, sends her back once with a plain note. A character's sheet may say she has not got it (`mechanisms_absent: continuity_editor`), which is how it is off for the second character; with it off there is no call and no evidence bundle, one line at boot instead of one per reply, and the repetition the gate finds in code is logged and nothing else
- `editor_gate` = True -- and it runs only when the draft has something to check -- a number, a word from a fact about him, a run shared with one of her recent messages (Persona._editor_needed); a draft with none of those gets no call, because a pass verdict does nothing (2026-09-04)
- `editor_recent_messages` = 10 -- how much of the conversation it is shown, and how it reaches past that. The window is small on purpose: a long record is a worse thing to read carefully, and the whole of it does not fit. So the draft's own words are searched against everything older instead (sim/recall.older_messages, no model call), and only the few messages the draft actually touches are added. Without this, a true quotation of anything past the window read as an invention and the draft was binned and paid for twice.
- `editor_lookback` = True
- `editor_lookback_max` = 5 -- at most this many older messages
- `editor_lookback_scan` = 1500 -- how far back the search itself reads
- `editor_lookback_min_overlap` = 2 -- words shared with the draft before a message counts
- `editor_lookback_common_share` = 0.02 -- and only DISTINCTIVE words count: one appearing in more than this share of the record is furniture, not a reference. At 6 per cent a generic filler line reached five unrelated messages; at 2 it reaches none, and a distinctive line still reaches the evening it belongs to.
- `language_flag` = True -- a reply to him that comes back mostly in Japanese is flagged in the log and the events -- never redrafted
- `offline_wait_seconds` = 900 -- hold a bubble this long for the network
- `send_attempts` = 3
- `send_retry_seconds` = 4
- `compose_seconds` = [6, 50] -- how long the words themselves take, before her state multiplies it
- `gap_marker_hours` = 1.5 -- a jump in the record used to look exactly like the next thing anybody said. The silences are what the history is about.
- `mood_delivery` = { -- mood-aware delivery: how fast and how much she answers depends on how she is. Read delay is scaled by a factor from tension with him, mood and craving (clamped); the glance reply chance moves with it; the persona gets a register line ("short and cool" / "eager").
- `  enabled` = True
- `  affection_cold_from` = 30 -- gone off him: at or below cold_from her register is cold and her delay grows by cold_weight per 100 below it; at or below hate_from she does not like him and is not hiding it
- `  affection_hate_from` = 15
- `  cold_weight` = 0.8
- `  standing_low` = 35 -- the `standing` meter with him: at or under standing_low her register is careful and deferential; at or over standing_high with tension down it is easy and sure of itself
- `  standing_high` = 70
- `  tension_weight` = 1.5
- `  mood_weight` = 0.8
- `  craving_weight` = 0.9
- `  energy_weight` = 0.5
- `  comfort_weight` = 0.5
- `  min_factor` = 0.4
- `  max_factor` = 3.0
- `  cool_tension` = 35
- `  eager_craving` = 70
- `  shame_weight` = 0.9 -- holding something she is not going to say: slower to answer, and it shows in how she answers
- `  anger_weight` = 0.35
- `  awkward_weight` = 0.8
- `  sad_register` = 45
- `  shame_register` = 45
- `  anger_register` = 40
- `  awkward_register` = 45
- `  surprise_register` = 35
- `reply_retries` = 2 -- She stops when he cuts in. Her bubbles go out one at a time with a typing delay between them, and the whole batch used to land whatever arrived meanwhile, so he could answer her second bubble and still get the third and fourth as though she had not noticed. The first one is already out of her mouth; from the second on she can stop. If the model comes back with nothing, his message is already marked read and she has silently ignored him forever. That is the one thing this system must never do, so it goes back in the queue.
- `no_repeat_recent` = 12 -- How many of her own last messages a new bubble is checked against before it goes out (`Persona._drop_already_sent`, near_duplicate). The burst-level dedup only ever saw a run inside one reply, so the same sentence went to him twice two hours apart, after he had answered it. 12 of hers is about a morning of talking; the pair that got through were five apart.
- `recover_lost_reply_hours` = 6 -- A reply can also be lost between being generated and being sent: the bubbles sit on the delivery thread's queue, and if the process stops there they are gone while his message is already marked read. Checked once at boot -- his newest message read with nothing after it, inside this many hours, means the reply died in flight and goes back.
- `interruptible` = True
- `busy_poll_seconds` = 2 -- While she is mid-message the only thing that matters is whether he cuts in, and a full pass of the loop can take half a minute when there are model calls in it -- long enough that his message reached the store after her last bubble had already gone (2026-08-21 09:50). During a send the loop does nothing but collect the post.
- `busy_poll_max_seconds` = 180 -- ...but never for longer than this, so a stuck pending count cannot spin the loop forever doing nothing else
- `typing_seconds_per_char` = 0.045
- `typing_min_seconds` = 4
- `typing_max_seconds` = 45
- `read_delay_free_seconds` = [20, 240]
- `read_delay_glance_seconds` = [120, 900]
- `glance_reply_probability` = 0.4
- `split_on_blank_lines` = True

**`timeline`**

- `compile_at` = "23:55"
- `compile_hold_for_chat` = True -- ...but the compile FLUSHES a live exchange, and the group chat can now run to 02:20, so a fixed hour cut off the late night it had just been given permission to have. It holds while she is mid-conversation and until the night's last light, and a night that ran past midnight is closed in the small hours -- by `compile_quiet_by_hm` at the latest.
- `compile_quiet_by_hm` = "04:00"
- `narrative_min_chars` = 900 -- the day's prose can come back as one short paragraph while every other field is full (08-27: 82 scenes in, 556 chars out, covering its first two hours). Below `narrative_min_chars` on a day with at least `narrative_min_scenes` in it, the compile asks once more with the span of the record in front of it. A thin day is otherwise silent: it parses, it saves, and the hole only shows months later.
- `narrative_min_scenes` = 25
- `narrative_retries` = 1

**`telegram`**

- `bot_token` = ""
- `chat_id` = ""
- `max_message_length` = 4096
- `poll_seconds` = 5
- `flush_queue_on_start` = False -- messages he sent while she was down are still messages; do not drop them
- `console_only` = False -- console mode prints outbound messages instead of sending; used by dry runs

**`sensors`**

- `enabled` = True
- `retrievals_db` = "data/retrievals.db" -- WHAT WAS FETCHED ABOUT THE WORLD, KEPT ONCE FOR THE WHOLE MACHINE (machine/retrievals.py): the page for an episode and the verdict a judge reached on it, a page condensed by a role that names nobody, a web search, a game's database card. Both characters read and write it, because a television episode is the same episode whoever is watching and one fetch should serve both; what each of them made of it stays in her own save. A fetch is claimed before it starts, so two processes reaching the same thing in the same minute pay for it once.
- `retrievals_inflight_stale_seconds` = 600 -- a claim older than this was left behind by a process that was killed mid-fetch -- a stop is Stop-Process -Force -- and is taken over
- `retrievals_inflight_wait_seconds` = 120 -- how long to wait on the other character's fetch of the same thing before going ahead alone. It is also the timeout on a claim held across a whole reading-up (`sim/recap.py`), which is a search, four page fetches, a digest each and a judge; a claimant that comes back with nothing releases the claim marked failed, so the ones waiting stop waiting long before this.
- `retrievals_retry_after_minutes` = 30 -- An episode he watched whose record holds no synopsis and no raw page is a reading-up that lost a race rather than one nobody ran. It is tried again as soon as the machine's shared store holds a page for it, and otherwise this long after the last try, at most this many extra times for the episode (`WatchingHim.owed`). 0 retries turns the repair off.
- `retrievals_max_retries` = 2
- `telemetry_jsonl_path` = "data/telemetry_feed.jsonl"
- `telemetry_state_path` = "data/telemetry_state.json"
- `telemetry_pending_log_path` = "data/telemetry_pending.txt"
- `telemetry_poll_interval_seconds` = 30
- `telemetry_heartbeat_interval_seconds` = 300 -- The buffer reaches the feed on a character count, on this heartbeat, or the moment a bot asks (the request path below). A flush is a file write and costs nothing; what costs is the digest a character makes of the feed, and that is her own decision, so a short heartbeat is cheap. Five minutes is the floor under how stale the feed can be when nobody has asked; the request path is what makes a reply current.
- `telemetry_flush_threshold_chars` = 18000
- `telemetry_flush_request_path` = "data/telemetry_flush_request" -- A bot about to build a reply touches this file. The machine's own loop sees it within telemetry_now_interval_seconds, re-reads the sources, writes whatever is held as an entry with flush_reason "requested" and removes the file; an empty buffer writes nothing and the file goes anyway. Pictures opened shortly before a message had their tags still in the buffer.
- `telemetry_flush_wait_seconds` = 4 -- how long the bot waits for a new entry to reach the feed after asking, before going ahead with what the feed already held
- `collector_in_process` = False -- His machine is watched once. The collector is its own process (machine/collector.py, started by talkapp.cmd) and a bot reads what it writes; True runs the whole sensor stack inside the bot instead, which is only right when there is exactly one bot on the machine.
- `telemetry_now_path` = "data/telemetry_now.json"
- `telemetry_now_interval_seconds` = 3
- `telemetry_now_stale_seconds` = 30
- `system_monitor_enabled` = True
- `system_monitor_poll_ms` = 1000
- `window_title_blocklist` = ["^[◐◑◒◓✳✴✻✽✶]", "Claude Code", "- Claude$", "^Claude$", ... -- What anything he had open may be CALLED in front of a character: one list of patterns (regular expressions, case-insensitive) that every sensor emitting such a name asks (sensors/blocklist.py). The window monitor blanks the title at the source (SystemMonitor._poll_foreground) -- the window and its process still count, its name does not -- when the title matches, or when the process is one of window_title_blank_processes; a file manager's title is the FOLDER it is showing and an editor's is the PATH of the open file, so that one blanking covers all three. The browsing-log reader (sensors/chrome_monitor.py) drops a visit whose PAGE TITLE matches, which the address-based chrome_junk_filters cannot do: a Google search whose query was a path once put this project's name in her digest from a google.com address. A coding session's title became a keyword in her model of his habits, and the assistant's animated status glyph, repainting the title twice a second, was reported to her as him working across 110 windows in two minutes (2026-09-04). Every terminal title is blanked because the assistant's session titles carry no word a pattern could catch.
- `window_title_blank_processes` = ["WindowsTerminal.exe", "cmd.exe", "conhost.exe", "powers...
- `hidden_processes` = ["WindowsTerminal.exe", "cmd.exe", "conhost.exe", "powers... -- Programs whose own NAME no character may be shown, on top of their titles. Blanking the terminal titles left "WindowsTerminal" itself, and for a terminal the program name IS what he is doing: it once stood in the second character's rolling account of his machine, her window trail, her live status line, her picture of his habits, her facts about him and her own written reflections, with every title already blank. A window on this list keeps its clock and its minutes and loses its name (sensors/blocklist.py `hidden`), so the account still says he was at the machine for those minutes instead of reading as a quiet stretch. python.exe and pythonw.exe are the characters themselves, the hub and the mirror daemon. The busiest-process line named `python` twice and the second character reported it to him as something on his machine.
- `bands` = { -- How hard he was working, said as a band rather than as a count (sensors/bands.py). Every figure a character ever recited about his machine came out of one function and it rounded nothing; the second character's accounts carried a mean of 38 numerals each and she read the keypress total and the uptime back to him. Typing is banded on keys per minute rather than on the total, because a total says nothing without the span it happened in; a burst is long past burst_long_seconds. The clock a window run started at and how long it ran are NOT banded: she is watching him continuously and what time he got up is hers to know (his call).
- `  typing_hard_per_minute` = 60.0
- `  typing_steady_per_minute` = 20.0
- `  typing_light_per_minute` = 4.0
- `  burst_long_seconds` = 30.0
- `  uptime_long_days` = 7.0
- `  uptime_days_days` = 2.0
- `  uptime_today_days` = 0.5
- `  clicks_many` = 60.0
- `  clicks_some` = 10.0
- `system_stats_interval_seconds` = 60
- `typing_burst_gap_seconds` = 3
- `image_viewer_processes` = ["JPEGView.exe", "jpegview.exe", "JPEGView64.exe", "Irfan...
- `chrome_process_names` = ["chrome.exe"]
- `chrome_history_path` = ""
- `chrome_max_raw_entries` = 20000
- `chrome_idle_gap_threshold_minutes` = 20
- `chrome_junk_filters` = ["chrome-extension://", "chrome://", "accounts.google.com... -- Addresses no character may be shown. The reader drops a visit whose URL contains any of these (both browsers: the Firefox reader adds firefox_junk_filters to this list). Three kinds: sign-in pages, whose query strings carry live tokens; the machine's own addresses, which is where her messenger and his other chatbot software sit; and the tools this project is built and served with. The assistant's chat titles are the reason for the third kind -- his browser history holds them, all of them a page title away from being read to her as a site he visited. Same fault as the terminal titles window_title_blocklist blanks, one source further out -- and the page TITLE of a visit that survives these is read against that same blocklist, because an address says nothing about what the page was called.
- `chrome_scrape_enabled` = False -- Live page-content scraping (CDP into his running Chrome) is OFF by design: it needs a Chrome launched with --remote-debugging-port and the cold-fetch fallback can't read logged-in / JS pages. The digest is fed by the browsing log instead (title + host per visit, from chrome_monitor.get_history_since). Leave this False unless a debug-port Chrome is set up (see PROJECT.md).
- `chrome_scrape_time_threshold_seconds` = 120
- `chrome_scrape_interaction_threshold_keypresses` = 5
- `chrome_scrape_max_text_length` = 5000
- `chrome_cdp_port` = 9222
- `image_window_gap_minutes` = 5 -- Image viewing reaches her as windows, not one line per picture. A run of images viewed with less than image_window_gap_minutes between them is one "session". A session of image_window_summarize_min or more is collapsed to a single dated summary (when, how many, who/series, ratings, average score); a shorter one keeps full per-image detail. image_context_max_detailed caps how many individual images can carry full detail across one look; past that, even short sessions summarize.
- `image_window_summarize_min` = 3
- `image_context_max_detailed` = 6
- `image_max_age_hours` = 4 -- image runs older than this are not described at all; then at most image_max_windows_per_look of what is left
- `image_max_windows_per_look` = 3
- `scrape_log_path` = "data/scrape_log.txt"
- `firefox_enabled` = True -- His second browser.  The path is per-machine and lives in config.json like chrome_history_path, not here; the profile is set per machine.
- `firefox_history_path` = ""
- `firefox_junk_filters` = ["about:", "moz-extension://", "view-source:", "file:///"]
- `audacious_process_names` = ["audacious.exe"]
- `torrent_backup_dir` = "" -- qBittorrent's on-disk torrent state (.fastresume + .torrent per torrent); read-only, no Web UI needed. Empty = the default location %LOCALAPPDATA%\qBittorrent\BT_backup.
- `vault_path` = ""
- `vault_extensions` = ["*.md", "*.txt"]
- `vault_ignore_patterns` = [".obsidian", ".trash", "yukarin-voice-models.md"] -- and this project's own documents when he copies one into the vault: she read the voice bench as a note about her and came out of it "a number and a cost" (2026-09-04)
- `vault_read_time_threshold_seconds` = 120
- `vault_max_file_length` = 1500
- `vault_excerpt_chars` = 700 -- how much of the end of an edited note rides along in the telemetry entry
- `gelbooru_enabled` = False
- `gelbooru_api_key` = ""
- `gelbooru_user_id` = ""
- `gelbooru_ratings_json_path` = "data/gelbooru/ratings.json"
- `gelbooru_ground_truth_json_path` = "data/gelbooru/ground_truth.json"
- `gelbooru_cleaned_json_path` = "data/gelbooru/cleaned_for_llm.json"
- `gelbooru_request_delay` = 0.1
- `gelbooru_cache_path` = "data/gelbooru/gelbooru_cache.json"
- `user_idle_seconds` = 1200 -- user counts as AFK for the snoop gate after this many idle seconds
- `mal_enabled` = True -- MyAnimeList: public list + recently-watched RSS, no auth. Activity reaches her through the phone digest; the shelf summary sits in her system prompt; /anime gives him a dated recap.
- `mal_username` = ""
- `mal_client_id` = "" -- optional: a MAL API v2 client id (X-MAL-CLIENT-ID). Public endpoints work without it; with it the official API is used for the list.
- `mal_poll_minutes` = 30
- `mal_list_refresh_hours` = 12
- `mal_list_path` = "data/mal_list.json"
- `mal_state_path` = "data/mal_state.json"
- `mal_shelf_watching_max` = 10
- `mal_shelf_completed_max` = 12
- `mal_history_enabled` = True -- Per-episode watch history (exact minute he watched each episode), built by tools/mal_history.py into its own SQLite DB. The bot only READS that DB (no browser): new episode events since it last looked reach her through the phone digest, the way list activity does. On first sight it takes the current tip as the mark so the backfilled history is not dumped into her lap.
- `mal_history_db` = "data/mal_history.db"
- `mal_history_max_events` = 8
- `mal_notes_max_events` = 5 -- a note he writes on an anime is an event, not just a field on a card the lookup might one day build
- `mal_notes_max_chars` = 400
- `x_enabled` = True -- X (Twitter): her account, read through a real logged-in Chrome profile (x_login.cmd opens it for the manual login). Read-only until x_actions_enabled; the Following tab only, never For You. Pacing is the ban-safety: few scrolls, uneven pauses, a gap between looks, a daily cap. The simulation gates looks further (phone in hand, bored) on top of these.
- `x_profile_dir` = ""
- `x_tools_profile_dir` = "" -- A COPY of that profile, logged into the same account, for the offline tools (tools/x_analyze.py). Her look, her posting and the scenery harvest share the one profile and take turns for it, and a second Chrome on a held profile kills the first -- so a tool that wanted a session had to wait for a gap between her looks. On its own copy it does not. Blank = use hers and take the turn.
- `x_headless` = True -- no window: her looks, her posts and the scenery harvest all run through this profile, and a Chrome opening itself on his desktop every half hour is not something she does. Headless Chrome names itself "HeadlessChrome" in the user agent, so open_driver rewrites the UA over CDP and hides navigator.webdriver on every document. Turn this off to WATCH a look happen when the parsing breaks; `/headless off` does the same live, for the next session only.
- `x_images_db` = "data/x_images.db" -- the tag store: what a picture IS, kept once and shared, never in her save because an image is the same image whoever looks at it
- `x_data_dir` = "data/x"
- `x_window_size` = "1100,900"
- `x_page_wait_seconds` = 12
- `x_scroll_pause_min` = 2.5
- `x_scroll_pause_max` = 6.5
- `x_feed_scrolls_min` = 3
- `x_feed_scrolls_max` = 7
- `x_following_reloads` = 4
- `x_followers_scrolls` = 2 -- the per-look glance at the top of the followers page (newest first): how many screens. Two is about twenty accounts, which is more than a day's new followers and cheap enough to do on every look.
- `x_following_reload_wait_min` = 20
- `x_following_reload_wait_max` = 45
- `x_session_min_gap_minutes` = 35
- `x_max_sessions_per_day` = 10
- `x_actions_enabled` = False -- her hand on the account (tomoe/curation.py). Off = every decision is written to actions.jsonl as dry_run and nothing is sent. Posting has its own switch.
- `x_posting_enabled` = False
- `chrome_extension_dir` = "data/extensions/uBlock0.chromium" -- uBlock Origin, loaded into every scraping Chrome (her X profile and the MAL one) so an ad is never read as content. See docs/selenium.md for why three separate things are needed to make Chrome accept it.

**`vision`**

- `enabled` = True -- Her eyes. Gemini on Vertex AI, its own provider and its own key (the service account in secerts/), nothing to do with the DeepSeek roles in `models`. Two callers: a photo he sends over Telegram, and the images on X posts she stops at. Everything else she knows is text.
- `key_path` = "secerts/project-7a56f373-e1de-4a94-9b8-bf340e6401b9.json"
- `project_id` = "" -- blank = take it from the key file
- `region` = "global" -- gemini-3.8-flash is global-only on this project
- `model` = "gemini-3.8-flash" -- the BARE id: `sensors/vision.py` builds .../publishers/google/models/<model>:generateContent, so the publisher is already in the path and a "google/" prefix (the OpenRouter form) would 404
- `temperature` = 0.2 -- description, not invention
- `thinking_budget` = 0 -- Gemini 3.x always spends some tokens thinking even at budget 0, and thinking shares max_output_tokens with the answer. Too tight a cap returns an empty answer, the same trap DeepSeek's reasoning sets.
- `max_output_tokens` = 1200
- `timeout_seconds` = 45
- `fetch_timeout_seconds` = 15
- `max_image_bytes` = 8000000
- `max_images_per_call` = 4
- `max_calls_per_day` = 80 -- a hard ceiling on Gemini calls a day, per character (each save keeps its own count in kv vision_calls, so it survives a restart; kept in memory it was reset by every restart and held on two days in nine). The harvest and her own looks share it; a spent day stops both
- `backoff_seconds` = 60 -- When a call fails for a reason that will pass -- the credentials, the quota, a 5xx, the network -- wait and come back rather than asking again straight away. Doubles per consecutive failure to the cap, and one good answer clears it.
- `backoff_max_seconds` = 1800 -- backstop; 4 looks x 8 = 32, plus his photos
- `prompt_photo` = "prompts/vision_photo.txt"
- `prompt_x` = "prompts/vision_x.txt"
- `telegram_enabled` = True -- a photo he sends: she looks at it before she answers
- `x_enabled` = True -- the X timeline: only the posts she would actually stop at, and never more than x_max_per_scroll of them in one look
- `x_max_per_scroll` = 8 -- measured: her sessions carry 5-17 eligible
- `x_max_images_per_post` = 2 -- images, median 8; 5 covered only 65% of them
- `x_max_output_tokens` = 900

**`network`**

- `down_after_failures` = 3 -- consecutive failures before we call it down
- `recheck_seconds` = 30
- `skip_model_work` = True -- while down, do not burn LLM retries on a dead link
- `resend_undelivered` = True -- her bubbles wait for the network instead of vanishing

**`tts`**

- `no_repeat_recent` = 8 -- how many of her own recent spoken lines the voice call is shown, so it does not say the same thing twice. 21 near-duplicate pairs in 40 lines before this, including one repeated three minutes later with the punctuation moved.
- `enabled` = True -- Voice lines only, never whole messages. Every reply gets one short spoken Japanese phrase (the persona may supply it inline as [voice: ...]; otherwise the voice model writes one from the bubbles). The gate below can still hold it; by default it holds nothing.
- `always` = False
- `aside_from_persona` = False -- Whether a `[voice: ...]` line the persona writes on its own is spoken and attached to the reply. She was never asked for one; the history shows her earlier voice notes as labels and the model imitated them, so a reply carried a spoken aside in a dialect that is not hers, attached to the text as if it were its reading. False: nothing in her history invites one, one written anyway is stripped and never spoken, and audio on a message is only its own text, read on request (`on_demand`). His call for the second character.
- `on_demand` = False -- The other way of having a voice: she sends no voice note at all, and every line she writes carries a speaker in the app that renders it when he taps it and plays it from the cache every time after. The two are independent, so a character can have both, either or neither. Nothing is synthesised until he asks for it.
- `minimax_script_path` = ""
- `minimax_config_path` = ""
- `voice_id` = "" -- Whose voice. The MiniMax config file is shared by everything on this machine and names one voice, so without this a second character speaks in the first one's voice. Empty means "whatever the MiniMax config says", which is the existing behaviour for the first character; a character's own config sets her own id.
- `mode` = "sync" -- The MiniMax async task API (what the script uses) takes minutes per line at times (3-11 min seen 2026-08-19); the synchronous endpoint returns a short line inline in about a second. "sync" renders directly with the same voice settings and falls back to the script; "script" is the old path.
- `sync_endpoint` = "https://api.minimax.io/v1/t2a_v2"
- `sync_timeout_seconds` = 45
- `recover_max_age_minutes` = 30 -- a line still unsent when the process stops is re-queued on the next boot, unless it is older than this (a voice note for a message from an hour ago would be strange)
- `ffmpeg` = "ffmpeg"
- `max_per_day` = 200
- `cooldown_minutes` = 0
- `require_alone` = False
- `with_self_started` = True
- `max_chars` = 40
- `cache_dir` = "data/voice"

**`logging`**

- `out_dir` = "logs"
- `dry_run_out_dir` = "logs/dryrun" -- sim / dry runs log here instead, so they never touch a live run
- `backup_dir` = "data/backups" -- a dated copy of world.db at every day compile
- `backup_keep` = 21
- `db_path` = ""
- `console_status_interval_seconds` = 30
