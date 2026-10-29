import json
import os
import re
import sys
import copy

# which language she is being addressed in, for `conditions()` and
# `prompt_text()`. It imports nothing but `os`, so there is no cycle back.
from sim import lang as _lang
from sim import existence as _existence


def _strip_html_comments(text):
    """A prompt file without its `<!-- ... -->` notes. The notes are for the
    person editing the file (provenance, a reminder); the model never gets
    them, and a leading one used to be the first bytes of the system
    prompt, which the provider's cache then keyed on."""
    return re.sub(r"<!--.*?-->[ \t]*\r?\n?", "", text or "", flags=re.S).strip()

# Every operational value lives here. config.json overrides; missing keys are
# backfilled into config.json on load so a fresh file always shows the full
# surface. Reading a key that is not in DEFAULTS is a bug.
DEFAULTS = {
    "api": {
        "base_url": "https://api.deepseek.com",
        "api_key": "",
        "max_retries": 3,
        # Every role's max_tokens is the API maximum (393216). A cap that is too
        # low fails silently and expensively: the persona spent its whole 3000
        # thinking and returned nothing, so she read him and said nothing, and
        # her diary was being cut off mid-entry without anyone noticing.
        # max_tokens is a ceiling and not an allocation, so headroom is free.
        # The caps were also the only thing bounding a runaway answer, and this
        # is what replaces that: anything longer than this is called out.
        "long_answer_warn": 8000,
        # a JSON role whose answer does not parse is asked to fix it this many
        # times before the caller sees None (the compile of 2026-08-26 kept a
        # broken answer as the day's memory)
        # a JSON role's answer that does not parse is asked again this many
        # times (LLM.call_json). Two, not one: with reasoning on, the cast
        # roles answer in the chat's own label format one call in ten, and a
        # second miss on one retry was a turn nobody spoke (the A/B of
        # 2026-09-04)
        "json_retries": 2,
        # a request that has not answered in this many seconds is a failure:
        # the coherence read ran 1152 s to 131072 output tokens on the loop
        # thread with nothing to stop it, and the retry sent the runaway back
        # as its prompt for another 1081 s
        "request_timeout_seconds": 600,
        # an answer with no words (reasoning only, finish stop) is asked again this many times
        "empty_retries": 1,
        # every answer is streamed and read as it is written (LLM._stream), so
        # a bad one announces itself: a stream that ends with no finish reason
        # was cut off and goes round the retry; finish `length` is the host's
        # own output cap and the answer is logged TRUNCATED and asked again
        # once (`empty_retries`), then given up on rather than sent as half a
        # reply. False sends the old single-body request.
        "stream": True,
        # no bytes for this long is a dead host, not a slow one: the call
        # fails here instead of at request_timeout_seconds, which still
        # bounds the whole answer. Reasoning streams too, so a live host is
        # never silent for long
        "stream_stall_seconds": 240,
        # An answer that has begun repeating itself word for word is ended
        # where the repetition starts (LLM._stream). Past this many characters
        # the last 400 are counted against everything written before them, and
        # an answer whose tail has already been written this many times is
        # abandoned. The day auditor looped five times over 2026-09-03 and
        # 2026-09-04, each to the host's 131072-token ceiling after about
        # nineteen minutes; these numbers stop each of them inside the first
        # 2% and fire on none of the other 8,349 calls on disk. 0 turns the
        # guard off.
        "repeat_guard_chars": 6000,
        "repeat_guard_copies": 4,
        # The largest answer `LLM.call_json` will hand back to the model when
        # asking it to fix its own JSON. Above this the original question is
        # asked again instead: a runaway is not repairable and sending it back
        # bills its whole length as prompt (two calls at 150,000 prompt tokens
        # on 2026-09-04).
        "json_retry_max_chars": 8000,
        # Who answers. `provider` is the one to use; `providers` names each
        # one -- the official DeepSeek endpoint (kind deepseek, key api_key,
        # the API-maximum max_tokens sent) or a host on OpenRouter (kind
        # openrouter, key from openrouter_key_file, no max_tokens sent, the
        # role's thinking flag mapped to `reasoning`) -- with the slug each of
        # the bot's model names maps to there and, per slug, the host order
        # pinned with no fallback outside it. The official account ran dry
        # on 2026-08-31 and the persona test put DeepSeek at Together level
        # with official at half the latency (data/model_test/20260831_persona_t1).
        "provider": "together",
        "providers": {
            "official": {"kind": "deepseek", "base_url": "https://api.deepseek.com",
                         "models": {"deepseek-v4-flash": "deepseek-v4-flash", "deepseek-v4-pro": "deepseek-v4-pro"}},
            "together": {"kind": "openrouter",
                         # kimi-k3 is the second character's model since 2026-09-02
                         # (docs/yukarin-voice-models.md). A model name missing from
                         # a provider's map falls through as a literal and the host
                         # rejects it.
                         "models": {"deepseek-v4-flash": "deepseek/deepseek-v4-flash-0731", "deepseek-v4-pro": "deepseek/deepseek-v4-pro",
                                    "kimi-k3": "moonshotai/kimi-k3",
                                    # the second character's voice model since 2026-09-04
                                    # (his call): one host, 262k window, reasoning on
                                    "sakana-namazu": "sakana/sakana-namazu",
                                    # the five the chat's model toggle needed
                                    # and the table did not have (his list,
                                    # 2026-09-04). The dated DeepSeek names
                                    # are their own entries: -0731 and -0813
                                    # are different slugs from the undated
                                    # ones already here, not aliases.
                                    "deepseek-v4-flash-0731": "deepseek/deepseek-v4-flash-0731",
                                    "deepseek-v4-pro-0813": "deepseek/deepseek-v4-pro-0813",
                                    "gemini-3.8-flash": "google/gemini-3.8-flash",
                                    "glm-5.3-flash": "z-ai/glm-5.3-flash",
                                    "glm-5.3": "z-ai/glm-5.3",},
                         # Together does not serve pro; the judge roles' pro calls go to
                         # the cheapest fp8 hosts that answered cleanly in the ranking
                         "order": {"deepseek/deepseek-v4-flash-0731": ["together"],
                                   "moonshotai/kimi-k3": ["together"],
                                   "sakana/sakana-namazu": ["Sakana AI"],
                                   "deepseek/deepseek-v4-pro": ["alibaba", "gmicloud", "coreweave"],
                                   # every pin is the host name OpenRouter's
                                   # own receipt reports, not the endpoint
                                   # tag: pinned under the tag, every call
                                   # logs a fall-through that never happened
                                   "deepseek/deepseek-v4-pro-0813": ["StreamLake", "Alibaba", "DeepSeek"],
                                   # Vertex's global endpoint was at 19% uptime
                                   # when this was measured; AI Studio also
                                   # accepts temperature and Vertex does not
                                   "google/gemini-3.8-flash": ["Google AI Studio"],
                                   "z-ai/glm-5.3-flash": ["Z.AI", "Novita", "GMICloud"],
                                   "z-ai/glm-5.3": ["Z.AI", "Friendli", "AkashML"],}},
            "qwen": {"kind": "openrouter",
                     "models": {"deepseek-v4-flash": "qwen/qwen3.8-flash", "deepseek-v4-pro": "deepseek/deepseek-v4-pro",
                                "kimi-k3": "moonshotai/kimi-k3", "sakana-namazu": "sakana/sakana-namazu",
                                "deepseek-v4-flash-0731": "deepseek/deepseek-v4-flash-0731",
                                "deepseek-v4-pro-0813": "deepseek/deepseek-v4-pro-0813",
                                "gemini-3.8-flash": "google/gemini-3.8-flash",
                                "glm-5.3-flash": "z-ai/glm-5.3-flash",
                                "glm-5.3": "z-ai/glm-5.3",},
                     "order": {"qwen/qwen3.8-flash": ["alibaba"],
                               "moonshotai/kimi-k3": ["alibaba"],
                               "sakana/sakana-namazu": ["Sakana AI"],
                               "deepseek/deepseek-v4-pro": ["alibaba", "gmicloud", "coreweave"],
                               "deepseek/deepseek-v4-flash-0731": ["together"],
                               "deepseek/deepseek-v4-pro-0813": ["StreamLake", "Alibaba", "DeepSeek"],
                               "google/gemini-3.8-flash": ["Google AI Studio"],
                               "z-ai/glm-5.3-flash": ["Z.AI", "Novita", "GMICloud"],
                               "z-ai/glm-5.3": ["Z.AI", "Friendli", "AkashML"],}}
        },
        # The models the chat's toggle offers for her voice (`/voicemodel`,
        # the control in the chat header). Names from the active provider's
        # own table; one that provider cannot serve is not offered. This is
        # the menu, not the choice -- the choice is kv `voice_model_override`
        # and lives on her save, per character, for the run.
        "voice_models": ["kimi-k3", "deepseek-v4-flash-0731", "deepseek-v4-pro-0813",
                         "sakana-namazu", "gemini-3.8-flash", "glm-5.3-flash", "glm-5.3"],
        "openrouter_key_file": "secerts/openrouter.txt",
        # when the pinned host fails, OpenRouter's next host for the SAME
        # slug answers (his call, after Together returned 503 on every
        # kimi-k3 call for a stretch); the model cannot change, only who
        # serves it, and the receipt (`served_by`, the `via` in the log)
        # names who did. Off: the pinned host or a missed call.
        "host_fallback": True,
        # The hosts that accept a request carrying `tools` and answer as if
        # none were offered, as OpenRouter's own endpoint list has them
        # (`docs/tool-calling.md` §7). Spelled EXACTLY as the receipt spells
        # them (`served_by`, the `via` in the log): 'Sakana AI', not 'sakana'.
        # A call that has to pick a tool asks the same question as JSON in her
        # text when the last receipt names one of these, so the transport is
        # decided by who actually answered and never by a guess about the pin.
        "hosts_without_tools": ["Chutes", "Fireworks"],
        # A call that goes out this soon after the previous call of the same
        # role FINISHED is not evidence about the prompt cache, so it is
        # counted on its own line in `/provider` and never as a cold call
        # (`LLM._track_cache`). Measured on Z.AI at 44k tokens: the entry a
        # call writes is not readable for about ten seconds after that call
        # completes, and the delay may scale with the prompt, since at 15k it
        # was readable in 8.5 s (2026-09-04,
        # data/retired/20260904_openrouter_audit/REPORT.md §1).
        "cache_settle_seconds": 15,
        # THE FIRST CALL OF A BURST GOES OUT ALONE. At the day boundary about
        # fifteen calls of one role go out back to back, each inside the
        # settle window of the one before, so none of them could read the
        # entry the one before wrote and every one of them was billed at the
        # uncached rate. With this on, a call that would go out inside the
        # settle window of a COLD call of the same role on the same system
        # prefix waits out the remainder first, and the rest of the burst
        # then reads that prefix. At most one wait per burst, whatever
        # happens: a role whose host does not cache at all must not pay
        # fifteen of them. The log line is `[cache] <role>: held Ns so the
        # burst reads the first call's prefix`.
        "cache_burst_hold": True,
        # There is no second PROVIDER and no fallback between providers, his
        # call. A provider maps a model NAME to its own slug, so a provider
        # fallback can change the MODEL and not just the host, and nothing
        # downstream reads which model actually answered; and with one host
        # in the chain the cooldown demoted the only host there was and
        # answered nothing for thirty minutes on a wobble (2026-09-03). A
        # call that fails after `max_retries` is logged, written to kv
        # `missed_calls`, and caught up when the host is back
        # (`App.catch_up`). `qwen` stays defined and pinnable via
        # `/provider qwen`, a decision somebody takes.
    },

    # One entry per LLM role. prompt is a file under prompts/. With thinking on,
    # DeepSeek spends max_tokens on reasoning first (thousands of tokens even at
    # low effort) and can return an empty answer, so thinking is reserved for
    # the persona and every JSON role answers directly.
    # ---- the six sections a patch anchor ate on 2026-08-31, rebuilt from
    # ---- config.json (values identical; the comments are in HISTORY's era)
    "models": {
        "director": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 1.0, "effort": "low", "max_tokens": 393216, "prompt": "prompts/director.txt"},
        "sleep": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 1.0, "effort": "low", "max_tokens": 393216, "prompt": "prompts/sleep.txt"},
        "state": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.6, "effort": "low", "max_tokens": 393216, "prompt": "prompts/state.txt"},
        "schedule": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 1.0, "effort": "medium", "max_tokens": 393216, "prompt": "prompts/schedule.txt"},
        "phone": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.7, "effort": "low", "max_tokens": 393216, "prompt": "prompts/phone.txt"},
        "persona": {"model": "deepseek-v4-flash", "thinking": True, "temperature": 1.0, "effort": "medium", "max_tokens": 393216, "prompt": ""},
        "timeline": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.9, "effort": "medium", "max_tokens": 393216, "prompt": "prompts/timeline.txt"},
        "episode_cards": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.6, "effort": "low", "max_tokens": 393216, "prompt": "prompts/episode_cards.txt"},
        "vault": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.7, "effort": "low", "max_tokens": 393216, "prompt": "prompts/vault.txt"},
        "downloads": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.8, "effort": "low", "max_tokens": 393216, "prompt": "prompts/downloads.txt"},
        "ick": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.4, "effort": "low", "max_tokens": 393216, "prompt": "prompts/ick.txt"},
        "revise": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.9, "effort": "low", "max_tokens": 393216, "prompt": "prompts/revise.txt"},
        "revise_self": {"model": "deepseek-v4-flash", "thinking": True, "temperature": 0.9, "effort": "medium", "max_tokens": 393216, "prompt": "prompts/revise_self.txt"},
        "rupture": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.5, "effort": "low", "max_tokens": 393216, "prompt": "prompts/rupture.txt"},
        "rupture_settle": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.5, "effort": "low", "max_tokens": 393216, "prompt": "prompts/rupture_settle.txt"},
        "spiral": {"model": "deepseek-v4-flash", "thinking": True, "temperature": 1.0, "effort": "medium", "max_tokens": 393216, "prompt": "prompts/spiral.txt"},
        "spiral_settle": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.5, "effort": "low", "max_tokens": 393216, "prompt": "prompts/spiral_settle.txt"},
        "settle_beliefs": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.5, "effort": "low", "max_tokens": 393216, "prompt": "prompts/settle_beliefs.txt"},
        "note_read": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.7, "effort": "low", "max_tokens": 393216, "prompt": "prompts/note_read.txt"},
        "voice": {"model": "deepseek-v4-flash", "thinking": True, "temperature": 1.0, "effort": "medium", "max_tokens": 393216, "prompt": "prompts/voice.txt"},
        "showrunner": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 1.0, "effort": "medium", "max_tokens": 393216, "prompt": ""},
        "cast_arc": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 1.0, "effort": "medium", "max_tokens": 393216, "prompt": ""},
        "cast_evolve": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 1.0, "effort": "medium", "max_tokens": 393216, "prompt": ""},
        "cast_reply": {"model": "deepseek-v4-flash", "thinking": True, "temperature": 1.0, "effort": "medium", "max_tokens": 393216, "prompt": ""},
        "peer_reply": {"model": "deepseek-v4-flash", "thinking": True, "temperature": 1.0, "effort": "medium", "max_tokens": 393216, "prompt": "prompts/peer_reply.txt"},
        "cast_turn": {"model": "deepseek-v4-flash", "thinking": True, "temperature": 1.0, "effort": "medium", "max_tokens": 393216, "prompt": ""},
        "graph": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.5, "effort": "low", "max_tokens": 393216, "prompt": "prompts/graph.txt"},
        "npc_moment": {"model": "deepseek-v4-flash", "thinking": True, "temperature": 1.0, "effort": "medium", "max_tokens": 393216, "prompt": ""},
        "gloss": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.0, "effort": "low", "max_tokens": 393216, "prompt": "prompts/gloss.txt"},
        # the important parts of an episode he is watching, condensed from
        # the whole scraped synopsis into a few hundred Japanese characters
        # for her situation block (sim/watching_him.py). Machinery, not her:
        # the prompt carries no person and the output is a digest she reads.
        "watching_digest": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.2, "effort": "low", "max_tokens": 393216, "prompt": "prompts/watching_digest.txt"},
        # chooses among several pages' digests of one episode, or rejects them
        # all (sim/watching_him.py; how many are read is `recap.candidates_target`)
        "digest_judge": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.0, "effort": "low", "max_tokens": 393216, "prompt": "prompts/digest_judge.txt"},
        # which of several candidate works he means, when the deterministic
        # filters leave more than one (sim/resolver.py; the `which_one`
        # section). Machinery: the prompt names nobody, the answer is an id
        # out of a table code built, and it never runs in a reply path.
        "which_one": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.0, "effort": "low", "max_tokens": 393216, "prompt": "prompts/which_one.txt"},
        # the episode's own subtitle file read as an account of its scenes in
        # order (sim/transcripts.py): the ground truth the judge holds web
        # candidates against, and the digest when none of them survives.
        # Machinery, not her: the prompt carries no person.
        "transcript_digest": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.0, "effort": "low", "max_tokens": 393216, "prompt": "prompts/transcript_digest.txt"},
        # everything read about one episode merged into ONE account of it
        # (sim/episode_account.py): every scene in order, the named parts, the
        # running gags, the lines, what the episode points at. The judge above
        # answers which single page to trust; this answers what happened, and
        # the two are not the same question. Machinery, not her: the prompt
        # carries no person, and the answer is a record of a television
        # episode that every character on the machine reads.
        # It is the one role here that SYNTHESISES rather than condenses, and
        # on low effort it condensed: asked for 1,200 to 3,000 characters over
        # six pages and a transcript it returned 214, which is a summary of
        # the summaries and is the thing this exists to stop. Thinking on,
        # effort high, because completeness is the whole point of the role and
        # it runs once per episode for the whole machine.
        "episode_account": {"model": "deepseek-v4-flash", "thinking": True, "temperature": 0.2, "effort": "high", "max_tokens": 393216, "prompt": "prompts/episode_account.txt"},
        # what is happening in the visual novel he is reading, written from
        # the lines his text hooker caught while he read them
        # (sim/eroge.py). Machinery, not her: the prompt carries no person,
        # and it is the prompt rather than a filter that decides what an
        # explicit stretch comes out as.
        "eroge_digest": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.2, "effort": "low", "max_tokens": 393216, "prompt": "prompts/eroge_digest.txt"},
        "him_profile": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.5, "effort": "low", "max_tokens": 393216, "prompt": "prompts/him_profile.txt"},
        "gossip": {"model": "deepseek-v4-flash", "thinking": True, "temperature": 1.0, "effort": "medium", "max_tokens": 393216, "prompt": ""},
        "orbit": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.4, "effort": "low", "max_tokens": 393216, "prompt": ""},
        "bond": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.5, "effort": "low", "max_tokens": 393216, "prompt": "prompts/bond.txt"},
        "nudge": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.4, "effort": "low", "max_tokens": 393216, "prompt": "prompts/nudge.txt"},
        "commit": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.4, "effort": "low", "max_tokens": 393216, "prompt": "prompts/commit.txt"},
        "reflect_cast": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 1.0, "effort": "low", "max_tokens": 393216, "prompt": "prompts/reflect_cast.txt"},
        "compare": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.9, "effort": "low", "max_tokens": 393216, "prompt": ""},
        "commit_him": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.4, "effort": "low", "max_tokens": 393216, "prompt": "prompts/commit_him.txt"},
        "recall": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.6, "effort": "low", "max_tokens": 393216, "prompt": "prompts/recall.txt"},
        "withhold": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.8, "effort": "low", "max_tokens": 393216, "prompt": "prompts/withhold.txt"},
        "said_when": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.2, "effort": "low", "max_tokens": 393216, "prompt": "prompts/said_when.txt"},
        "approach": {"model": "deepseek-v4-flash", "thinking": True, "temperature": 1.0, "effort": "medium", "max_tokens": 393216, "prompt": "prompts/approach.txt"},
        "intent": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.9, "effort": "low", "max_tokens": 393216, "prompt": "prompts/intent.txt"},
        "experience": {"model": "deepseek-v4-flash", "thinking": True, "temperature": 1.0, "effort": "medium", "max_tokens": 393216, "prompt": "prompts/experience.txt"},
        "morning": {"model": "deepseek-v4-flash", "thinking": True, "temperature": 1.0, "effort": "medium", "max_tokens": 393216, "prompt": "prompts/morning.txt"},
        "anticipation": {"model": "deepseek-v4-flash", "thinking": True, "temperature": 1.0, "effort": "medium", "max_tokens": 393216, "prompt": "prompts/anticipation.txt"},
        "reflect": {"model": "deepseek-v4-flash", "thinking": True, "temperature": 1.0, "effort": "medium", "max_tokens": 393216, "prompt": "prompts/reflect.txt"},
        "local_events": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.2, "effort": "low", "max_tokens": 393216, "prompt": ""},
        "events": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.6, "effort": "low", "max_tokens": 393216, "prompt": ""},
        "devoice": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.4, "effort": "low", "max_tokens": 393216, "prompt": "prompts/devoice.txt"},
        "affection": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.4, "effort": "low", "max_tokens": 393216, "prompt": "prompts/affection.txt"},
        "lookup": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.2, "effort": "low", "max_tokens": 393216, "prompt": "prompts/lookup.txt"},
        "lookup_gist": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.5, "effort": "low", "max_tokens": 393216, "prompt": "prompts/lookup_gist.txt"},
        "search_gist": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.3, "effort": "low", "max_tokens": 393216, "prompt": "prompts/search_gist.txt"},
        # a fan-encyclopedia page about a character he named, condensed to
        # what a viewer knows (sim/lookup.py, `lookup.character_pages`)
        "character_digest": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.2, "effort": "low", "max_tokens": 393216, "prompt": "prompts/character_digest.txt"},
        "x_post": {"model": "deepseek-v4-flash", "thinking": True, "temperature": 1.0, "effort": "medium", "max_tokens": 393216, "prompt": ""},
        # answering somebody who answered a post of hers: one judge over the
        # batch waiting under her posts (which one, or none), then one call in
        # her voice for the one she picked (tomoe/replies.py)
        "x_reply_judge": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.3, "effort": "low", "max_tokens": 393216, "prompt": ""},
        "x_reply": {"model": "deepseek-v4-flash", "thinking": True, "temperature": 1.0, "effort": "medium", "max_tokens": 393216, "prompt": ""},
        # what the account does with a post she has just sent him: repost
        # it, like it only, or neither. Her taste decides it -- a roll used
        # to (tomoe/curation.py, act_on_shared). A judge: it decides about a
        # post and writes none of her words, so it gets no character sheet.
        "x_repost_judge": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.3, "effort": "low", "max_tokens": 393216, "prompt": ""},
        "x_account": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.4, "effort": "low", "max_tokens": 393216, "prompt": "prompts/x_account.txt"},
        "editor": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.2, "effort": "low", "max_tokens": 393216, "prompt": "prompts/editor.txt"},
        # The VN channel's three passes. Machinery, not her, except the last:
        # the staging director decides how a scene is framed, the emotion role
        # labels a feeling from a closed set, and neither writes a word anyone
        # reads. `quality_rewrite` DOES write in her words -- it says the same
        # thing shorter -- so it is a voice role (`Config.ROLE_STANCE`) and
        # joins `LLM.VOICE_ROLES`. All three are off unless a character's
        # bundle turns the section on (`scene_director`, `emotion`, `quality`).
        "scene_director": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.4, "effort": "low", "max_tokens": 393216, "prompt": "prompts/scene_director.txt"},
        # The out-of-character console behind the director button
        # (`sim/stage_manager.py`). It talks to the player in English about the
        # scene and proposes one for his approval; it never speaks as her. Off
        # unless a bundle turns its section on.
        "stage_manager": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.6, "effort": "low", "max_tokens": 393216, "prompt": "prompts/stage_manager.txt"},
        "emotion": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.0, "effort": "low", "max_tokens": 393216, "prompt": "prompts/emotion.txt"},
        "quality_rewrite": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.9, "effort": "low", "max_tokens": 393216, "prompt": "prompts/quality_rewrite.txt"},
        "social": {"model": "deepseek-v4-flash", "thinking": True, "temperature": 0.9, "effort": "medium", "max_tokens": 393216, "prompt": ""},
        # which post from her scroll she sends him: the one call in this
        # project whose answer is a tool call that is acted on
        # (tomoe/share_pick.py). It speaks AS her -- the system half is her
        # whole persona assembly, not this file -- so the prompt named here is
        # only the closing instruction, and a character addressed in another
        # language names her own copy of it the way she does for every other
        # role. Flash and the persona's own thinking and effort, because it is
        # her judgement about a post and she writes on flash. It runs once per
        # thing she wants to show him, behind the system half the reply is
        # about to send anyway, so most of the prompt is a cache hit: the
        # replay of forty-six moments that decided this was worth wiring
        # measured $0.0009 a pick and four cents for all forty-six
        # (data/retired/20260906_1912_pick_test/). A character whose voice is
        # on another model keeps this on flash, as the director is: it decides
        # rather than writes.
        "share_pick": {"model": "deepseek-v4-flash", "thinking": True, "temperature": 1.0, "effort": "medium", "max_tokens": 393216, "prompt": ""},
        "diary": {"model": "deepseek-v4-flash", "thinking": True, "temperature": 1.0, "effort": "medium", "max_tokens": 393216, "prompt": "prompts/diary.txt"},
        "reconcile": {"model": "deepseek-v4-flash", "temperature": 0.2, "max_tokens": 393216, "prompt": "prompts/reconcile.txt"},
        "weekly": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.9, "effort": "medium", "max_tokens": 393216, "prompt": "prompts/weekly.txt"},
        "cast_day": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 1.0, "effort": "medium", "max_tokens": 393216, "prompt": ""},
        "cast_beat": {"model": "deepseek-v4-flash", "thinking": True, "temperature": 1.0, "effort": "medium", "max_tokens": 393216, "prompt": ""},
        "cast_life": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.9, "effort": "low", "max_tokens": 393216, "prompt": ""},
        "foresee": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.5, "effort": "low", "max_tokens": 393216, "prompt": "prompts/foresee.txt"},
        "expect_him": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.3, "effort": "low", "max_tokens": 393216, "prompt": "prompts/expect_him.txt"},
        "wonder": {"model": "deepseek-v4-flash", "thinking": True, "temperature": 0.9, "effort": "medium", "max_tokens": 393216, "prompt": "prompts/wonder.txt"},
        "wonder_answer": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.3, "effort": "low", "max_tokens": 393216, "prompt": "prompts/wonder_answer.txt"},
        "scenery_judge": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.3, "effort": "low", "max_tokens": 393216, "prompt": ""},
        "habits_him": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.3, "effort": "low", "max_tokens": 393216, "prompt": "prompts/habits_him.txt"},
        "zeitgeist": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.5, "effort": "medium", "max_tokens": 393216, "prompt": "prompts/zeitgeist.txt"},
        "taste": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.4, "effort": "low", "max_tokens": 393216, "prompt": "prompts/taste.txt"},
        "coherence": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.2, "effort": "low", "max_tokens": 393216, "prompt": "prompts/coherence.txt"},
        "observer": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.3, "effort": "low", "max_tokens": 393216, "prompt": "prompts/observer.txt"},
        "watch_pick": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.8, "effort": "low", "max_tokens": 393216, "prompt": "prompts/watch_pick.txt"},
        # What she would do with the phone in her hand (sim/pick.py). Flash,
        # at the persona role's own thinking and effort, for every character
        # INCLUDING the two on a voice model: this call decides something and
        # writes none of her words, so it has no more business on her voice
        # model than the director has. No prompt file of its own -- the system
        # half is `persona.system_for("him")` byte for byte, which is what
        # puts the pick behind the same cached prefix as her reply, and the
        # tool definitions are the rest of the instruction.
        "pick": {"model": "deepseek-v4-flash", "thinking": True, "temperature": 1.0, "effort": "medium", "max_tokens": 393216, "prompt": ""},
        # B-zombie experiment (sim/bz.py): the in-character order, one call per reply
        "bz_order": {"model": "deepseek-v4-flash", "thinking": False, "temperature": 0.8, "effort": "low", "max_tokens": 393216, "prompt": "prompts/bz_order.txt"}
    },

    "peer_talk": {
        # Two running characters talking to each other over the hub
        # (docs/peer-talk.md, sim/peers.py). Off, and with no contacts, for
        # every character until one is written in: a character with an empty
        # list has no peer, no mailbox to poll and no conversation, which is
        # why the row in Config.REQUIRES is None rather than a property of
        # her existence. Peer talk needs no body, no world and no account.
        "enabled": False,
        # Who she can write to. One row per peer: `id` is the peer's hub id
        # (her display name lowercased with the spaces out, which is what she
        # registers with), `name` is what THIS character calls her, and
        # `language` is the room's language ("" = the way she writes to her
        # own people). Nothing else about a peer is knowable from here: a
        # character never reads another character's config or save, and what
        # she learns of a peer is the words that arrive.
        "contacts": [],
        # How many turns of HERS one conversation may run to. At the cap it is
        # closed and further messages are still received and read. Two
        # characters each holding their own cap is what stops two bots talking
        # forever without either having to trust the other to stop.
        "max_turns": 6,
        # and how many messages she may send to peers in a day, counted with
        # store.bump_today so a restart does not reset it
        "max_per_day": 12,
        # the floor under two sends of hers, on top of the reading-and-typing
        # delay taken from the length of what she is answering
        "min_gap_seconds": 90,
        # how quiet it has to have been, in either direction, before she opens
        # something new
        "min_gap_minutes": 45,
        # the chance per loop pass that she opens one, inside the window
        # below. Sized so an opener lands somewhere across the window rather
        # than at its first minute.
        "open_p": 0.02,
        "open_from_hm": "09:00",
        "open_to_hm": "24:00",
        # conversations kept in the save, and how long one may stay live
        # before it has trailed off
        "keep": 60,
        "live_minutes": 120,
        # How many turns of a room she is in but does not own she keeps
        # on her own side (kv `peer_rooms`). She is a participant there:
        # what she holds of that room is the words that arrived, who said
        # them and when, and nothing else.
        "room_keep": 60,
        # And how many turns she may say in a day in rooms she does not own,
        # counted on its own key (kv `room_counts`). Separate from
        # `max_per_day` above because the two are different things: that one
        # is her own conversations, this one is somebody else's room asking
        # her. A room turn used to spend the conversation budget, so twelve
        # answers in the group chat put a character out of a section that is
        # switched off for her anyway. Generous, because the pacing of a room
        # is its owner's and this is only a stop against a runaway.
        "room_max_per_day": 60
    },
    "world_shared": {
        # The world as a file more than one process may read (world/shared.py,
        # docs/shared-world.md). Everything a character knows about the world
        # around her is in her own save, so a second process running one of
        # the people beside her as a character of her own would plan a day the
        # first process never had. The owner writes a copy of the day's public
        # facts -- who is where, what the day settled, every turn spoken in
        # every room, the edges, the orbit, the pool -- and anybody else in the
        # same world reads them.
        "enabled": False,
        # Which world. The file is `<world.shared_dir>/<id>/world.db`, so two
        # characters share a world exactly when they name the same id.
        "id": "",
        # One writer per world: the character whose config says this. Everybody
        # else opens the file read-only and never writes a row.
        "owner": False,
        # How many rows of one of the world's tables a READER takes into a
        # prompt: who is where, what is going round, the people around the
        # people. The owner's own modules have their own limits and do not
        # read this; it bounds what a non-owner puts in front of a model in
        # place of a subsystem that is switched off for her.
        "read_rows": 8,
        # Whether a character who does NOT own this world writes the rows that
        # are about herself: the windows her own day planner puts her in, the
        # rooms she is in, and the lines her own plan settled, each under her
        # own id and a source naming her own planner (world/shared.py,
        # docs/shared-world.md §2). Everything else in the file stays the
        # owner's and a row about anybody else is refused. Switched off she
        # writes nothing at all, and the owner's draw of her week on the
        # world's roster is all the world ever has of where she is.
        "reader_writes_own_rows": True
    },
    "character": {
        # her name, its kanji and its reading: hers, in her config, never here
        "name": "",
        # which program runs her. This fork carries `resident` alone (on his
        # machine): the runtime imports `<program>.app` and asks it to build
        # her world, her people, her account and her sight; what a program
        # does not build does not exist in her process.
        "program": "resident",
        "name_ja": "",
        "reading_ja": "",
        "user_name": "User",
        # Which language she writes to him in. The first character is bilingual
        # and the arrangement is load-bearing for her -- English with him is
        # the one room her English lives in, and everything else in her life is
        # Japanese -- so the instruction was written straight into
        # persona.py. A character who has only one language was then told, in
        # her own assembled prompt, to write in the other one.
        "writes_to_him": "english",
        # Which set of instructions ADDRESSED TO HER she is given -- her
        # situation block, the section headers above it, the closing block that
        # says what to write and how. An arm to be compared, not a decision:
        # `as_they_run_today` (the control, preserved byte for byte),
        # `in_english`, `in_her_language`. All of them live side by side in the
        # code (`sim/lang.py`); `SCAIL_INSTRUCTIONS` overrides for a run and
        # `sim.lang.set_override` for one process, so a harness can build the
        # same character's prompt every way without a restart or a config edit.
        #
        # Not the same question as `writes_to_him`, which is what language she
        # ANSWERS in: a character can be instructed in English and write
        # Japanese, and that is what both characters did until 2026-09-02.
        # `auto` is decided from `instruction_language` below: her own
        # language when this switch has a second one to render for her, the
        # control when it has not. It was the control for everybody until
        # 2026-09-07, because every bench bought up to 2026-09-02 had been
        # bought under it -- and that bench was the second character's
        # voice, which says nothing about a character composed afterwards.
        # Two of the four declared Japanese and were instructed in English.
        "instructions": "auto",
        # Which language the arm `in_her_language` renders for this character,
        # and what a role writing material she reads is told to write in.
        # A separate question from `writes_to_him` and from `instructions`,
        # and it must not be read off either: the first character is
        # bilingual, her chat with him is the one room her English lives in,
        # and every measurement taken on her was taken with her instructions
        # in English -- so hers is "english", `in_her_language` renders the
        # same bytes as `in_english` for her, and `/lang ja` tells him there
        # is nothing to switch her to. Japanese is the only value that
        # renders anything today, because every wording behind the switch
        # lives in the source as an English/Japanese pair (`sim/lang.py`).
        "instruction_language": "english",
        # PERSON-SHAPED PATHS, EMPTY HERE AND ALWAYS. Every path in this
        # block is one character's own material -- her speech guide in each
        # language, the roster of who is around her, their sheets, how each of
        # them may sound, what she has decided about him and about herself.
        # A config that does not carry the key has it written in from here on
        # its first load, where it then looks authored, so a default that is
        # one person's file is inherited by the next character in silence:
        # the fourth character's first day was the first character's
        # household, map, roster and sheets, out of these lines. Her own
        # config names hers, and `Config.PERSON_FILES` refuses the boot when a
        # section that reads one of them is on and the path is empty or names
        # a file that is not on disk.
        "style_prompt": "",
        "style_ja_prompt": "",
        "cast_file": "",
        "cast_sheets_dir": "",
        # HER OWN people, for a character in a world somebody else keeps:
        # a second cast file and a second sheets directory, empty for the
        # character who owns her world (her cast file is her circle). A
        # reader plans, speaks and opens rooms with the people in this
        # file only, writes all of it to her own save and none of it to
        # the world, and still answers in the owner's rooms when asked.
        # The world's roster stays on `cast_file`, read for names, and a
        # key in both files is hers (docs/shared-world.md section 9).
        "own_cast_file": "",
        "own_cast_sheets_dir": "",
        "voice_rules_file": "",
        "voice_flags_keep": 200,
        "beliefs_file": "",
        "self_beliefs_file": "",
        # What KIND of existence this character has. Three independent
        # properties rather than two named modes, so a second character picks
        # a combination instead of inheriting the first one's assumptions.
        # A sheet overrides any of them under `existence`.
        #
        #   embodied   she has a body: hunger, fatigue, comfort, illness, and
        #              a physical place to be. False for someone who lives in
        #              a machine, and then the gauges that measure a body are
        #              declared absent on the sheet as well.
        #   in_world   her day advances whether or not he is there: a
        #              schedule, places, a cast, weather, a clock of her own.
        #              This is the whole of `sim/schedule.py` and most of the
        #              day's ledger.
        #   sees_him   how she learns what he is doing. "digest" is the app on
        #              her phone: a felt decision to look, gated by access and
        #              by how long he has been quiet. "resident" is continuous
        #              and ungated -- she is on his machine and simply sees it,
        #              which makes the telemetry her environment rather than
        #              something she checks. "none" is a character who has no
        #              window onto him at all.
        #
        # The combinations are all meaningful and none is special-cased. A
        # character can be embodied and in a world and resident on his machine
        # at once: a life that advances AND a permanent view of his desktop.
        "existence": {
            "embodied": True,
            "in_world": True,
            "sees_him": "digest",
            # Whether she has any contact with him at all. "chat" is the
            # relationship: a chat of her own with him, the impulse to write
            # first, everything she feels and expects of him. "none" is a
            # character who exists for somebody else's circle and not for
            # him -- Rena, promoted out of the first character's cast: she
            # knows of him only what her friend lets slip, writes to nobody
            # but her own people, and his phone does not list her.
            "with_him": "chat",
            # Whether the player drives the story instead of her. True for a
            # visual-novel character: she never writes to him first and never
            # follows up on her own, so the impulse and afterthought paths are
            # shut (`scail.py:maybe_impulse`, `scail.py:maybe_afterthought`).
            # The same energy shows in where she is and what she was doing when
            # he arrives, not in a message.
            "player_driven": False,
            # Whether she holds an account of her own out in public. False and
            # nothing posts, nothing curates and nothing measures her taste
            # drifting away from his -- the second character has none, twice
            # over: in the fiction the account is his and she is resident on
            # his machine, and outside it the real person left that medium.
            "has_account": True
        },
        # Which person she is on MyAnimeList, as the id in the URL of that
        # person's page, or "" for somebody who has never been in anything.
        #
        # An ID and never a name. Her given name alone matches nine other
        # people in his mirror's cast rows by substring, and which of them a
        # `LIKE '%name%'` answered with was down to the order sqlite happened
        # to return. This is also the SWITCH: `Config.REQUIRES` turns an empty
        # id into the missing property the `role_check` section needs, so a
        # character who has never acted never reads his mirror, never pays a
        # read and never gets a line about a part.
        #
        # The sheet may set it too (`data/characters/<id>.json`), and the
        # sheet wins, so a regenerated config cannot lose it.
        "mal_person_id": "",
        # What fills the character-shaped holes in a mechanism prompt
        # (`Config.fill`). One file per character; the values for the character
        # the prompts were written around are the exact spans that came out of
        # them, so her rendering is byte-identical to the old files.
        "neutral_file": "",
        # The dated once-events of her past, for a character who was read out
        # of a real archive: a trip, an illness, an audition, a move, a
        # purchase, each with the day or the span the archive supports and the
        # episode and cue index it was said at. `sim/seed_memories.py` writes
        # them into her memory store once, at boot, so that her past can be
        # reached by meaning and by the deliberate search and not only by
        # somebody naming it. Empty for a character with no such archive,
        # which is most of them, and then nothing runs and nothing is logged.
        "timeline_file": "",
        # Her quoted moments off the same archive, which stay in the retrieval
        # (`lore.memory_file`) and are NOT written into the store. Named here
        # because the seeder reads it to see which of its rows are the same
        # moment of tape as a timeline event, so that the overlap between the
        # two routes into her prompt is recorded on the row rather than found
        # later.
        "memories_file": ""
    },

    # How far the instruction arm reaches. The arm itself is
    # `character.instructions` and it covers what the prompt builder writes:
    # her section headers, her situation block, the closing instruction. This
    # section is what it reaches BEYOND that -- the sentences under those
    # headers, which other roles wrote.
    "language": {
        # Whether the roles that write her material are told which language
        # to write it in while she is being instructed in her own language.
        # Off, and the switch moves the labels and leaves the prose under
        # them in whatever the roles happened to write: her own language over
        # an English digest, an English fact list and English beliefs about
        # him, which is what the second character read before this existed.
        "enabled": True,
        # The roles whose OUTPUT she reads inside her own prompt. Each is
        # given one line naming the language, keys and fixed choices
        # excepted (`sim.lang.material_line`). Nothing already in the record
        # is touched: a fact written in English stays as written until the
        # forgetting curve drops it.
        #
        # A role is on this list only when its output is prose FOR HER and
        # nothing else. Four roles that write into her prompt are left off on
        # purpose, because code reads their words as data: the phone's digest
        # is scanned with English patterns for the one thing off his screen
        # she remarks on, the director's scene and the day's plan carry
        # places and activities other modules match on, and the state role is
        # gauge arithmetic with nobody being addressed in it. Their LABEL in
        # her prompt is already in her language; the account under it is the
        # machine's. The editor is off the list too and forks inside its own
        # prompt instead (`[[?her_language]]`), because the note it writes is
        # put in front of her and the verdict beside it is for the log.
        "material_roles": ["anticipation", "approach", "commit", "commit_him", "diary", "downloads", "experience", "expect_him", "foresee", "habits_him", "him_profile", "ick", "lookup_gist", "morning", "note_read", "nudge", "recall", "reflect", "revise", "revise_self", "rupture", "search_gist", "settle_beliefs", "spiral", "timeline", "vault", "weekly", "withhold", "wonder", "wonder_answer"]
    },

    "world": {
        "character_timezone": "Asia/Tokyo",
        "user_timezone": "local",
        "weather_enabled": True,
        "weather_latitude": 35.6895,
        "weather_longitude": 139.6917,
        "weather_refresh_minutes": 60,
        "weather_cache_path": "data/weather_cache.json",
        "holidays_file": "data/jp_holidays.json",
        # PERSON-SHAPED PATHS, EMPTY HERE, for the same reason as the block
        # in `character`: her school's year, her map, her household as an
        # economy, what is going round where she is, her taste sheet and the
        # places she keeps going back to are one person's, and a default that
        # is one person's file is inherited by the next character in silence.
        # `Config.WORLD_KEYS` blanks these for a character with no world;
        # `Config.PERSON_FILES` refuses the boot for one who has a world and
        # no file of her own.
        "school_calendar_file": "",
        "geography_file": "",
        # Where the worlds live, one directory each. A character with no world
        # of her own has no path to anybody else's (Config.WORLD_KEYS).
        "shared_dir": "data/worlds",
        "household_file": "",
        "character_file": "",
        "local_events_file": "data/local_events.json",
        "local_events_every_days": 3,
        "zeitgeist_file": "",
        "zeitgeist_every_hours": 4,
        "zeitgeist_days": 7,
        "zeitgeist_keep": 80,
        "zeitgeist_max_per_fetch": 10,
        "zeitgeist_in_prompt": 8,
        "taste_file": "",
        # Where she is when she is not with him, for a character who has no
        # world but has a home of her own. Read only by `schedule.own_day`,
        # which plans her day from it and from nothing else -- no calendar,
        # no weather, no cast, no feed of the present. Empty for anyone whose
        # world is the live one.
        "home_file": "",
        "places_file": "",
        "event_lookahead_days": 10,
        "calendar_describe_limit": 8,
        # The words that make a line a claim about a PUBLIC event -- one that
        # either is on the calendar for that day or does not exist. A plan
        # naming one of these on a date the calendar has nothing on is
        # refused (`sim/ledger.py:outing_unbacked`). Blanked by
        # `Config.WORLD_KEYS` for a character with no world, who has no
        # calendar to check against and no public events to be wrong about.
        "outing_words": ["festival", "matsuri", "hanabi", "fireworks", "bon odori",
                         "\u796d", "\u82b1\u706b", "\u76c6\u8e0a", "\u7e01\u65e5"]
    },

    "reconcile": {
        "enabled": True,
        "log_keep": 200
    },

    # System One (typesafe.ai; `typesafe.py`, `docs/system-one.md`): a hosted
    # classifier for code's half of the split, never a voice role, never a
    # stage role, and never a provider fallback. The service is System One, the
    # code is `typesafe`, and the model it calls is Jev (`jev-latest`). It is
    # deliberately NOT a key in `models`: the stage's pickers move LLM roles and
    # must not offer this. Off pays nothing and changes nothing. Each use carries
    # its own switch and threshold, because a threshold belongs to the action
    # that consults it.
    "typesafe": {
        "enabled": False,
        "key_file": "secerts/typesafe.txt",
        "model": "jev-latest",
        "timeout_seconds": 20,
        "floor": 0.6,
        "uses": {
            "reconcile": {"enabled": False, "threshold": 0.5},
            "sight_activity": {"enabled": False, "threshold": 0.5},
            "emotion": {"enabled": False, "threshold": 0.35},
            "inbound_signals": {"enabled": False, "threshold": 0.5},
            # the VN staging (`sim/scene.py`, design section 3.1): place,
            # camera, transition, mood, bgm and vocal action in one batch.
            # Place has a lower floor because its many-way choice spreads
            # probability. Music and vocal actions have separate floors;
            # uncertainty falls back to the held or mood-based track and no
            # vocal tag respectively.
            "scene_director": {"enabled": False, "threshold": 0.3,
                               "music_threshold": 0.5, "vocal_threshold": 0.6},
            # the work resolver's identity question (`sim/resolver.py`,
            # design section 3.1): one choice over code's own candidate ids.
            # Off until a run carries logged `which_one` calls to test against.
            "which_one": {"enabled": False, "threshold": 0.5},
            # what became of her unasked question (`sim/wonder.py`, design
            # section 3.1): one choice over the five verdicts. Off until a run
            # carries logged `wonder_answer` calls to test against.
            "wonder_answer": {"enabled": False, "threshold": 0.5},
            # the urge she is acting on when she reaches out (`sim/intent.py`,
            # design section 3.1): one choice over the nine kinds. The words
            # (`about`, `test`, `question`) stay the role's. Off until the
            # logged `intent` calls have been read.
            "intent": {"enabled": False, "threshold": 0.5},
            # the two numbers of her prediction (`sim/foresight.py`, design
            # section 3.1): `reply_p` and `reply_minutes` as scores; the words
            # (`tone`, `risk`, `plan`) stay the role's. Floor 0.3: at 0.3 the
            # V3 sample gives 0.94 on the answers Jev commits to.
            "foresee": {"enabled": False, "threshold": 0.3},
            # what he said about when he is reachable (`sim/rhythm.py`, design
            # section 3.1): two choices, did he say anything and which kind.
            # Floor 0.5: the V3 sample gives 18/18 at it.
            "said_when": {"enabled": False, "threshold": 0.5},
            # whether he named a thing she might look up, and which kind
            # (`sim/lookup.py`, design section 3.1). Floor 0.5: the V3 sample
            # gives 20/20 raw and 18/18 at it.
            "lookup": {"enabled": False, "threshold": 0.5},
            # how much her circle would make of it, and how private it is
            # (`sim/ick.py`, design section 3.2): two scores on the role's own
            # 0-5 scale; `strain`/`weight` and the note stay the role's. Floor
            # 0.3: the V3 sample gives 0.93 at it.
            "ick": {"enabled": False, "threshold": 0.3},
            # the warmth each of his messages leaves her at (`sim/appraisal.py`,
            # design section 3.1): one score per marked message on the role's
            # 5-95 scale; the `why` stays the role's. Floor 0.5: 14/14 on the V3
            # sample's real answers.
            "affection": {"enabled": False, "threshold": 0.5},
            # the label on the questions she turns over (`sim/wonder.py`, design
            # section 3.2): the role writes the text, one choice per question
            # names its kind, a chained call. Floor 0.5: 16/16 on the V3 sample.
            "wonder": {"enabled": False, "threshold": 0.5},
            # whether what just happened mended the rupture (`sim/rupture.py`,
            # design section 3.1): one choice over mended/tried/worse/nothing;
            # the note and `by` stay the role's. Floor 0.5: 0.87 on the V3 sample.
            "rupture_settle": {"enabled": False, "threshold": 0.5},
            # whether he committed to anything, and how firm each commitment is
            # (`sim/expectations.py`, design section 3.1): a choice for `found`
            # and one score per commitment. Floor 0.5: 20/20 on the V3 sample.
            "expect_him": {"enabled": False, "threshold": 0.5},
            # how solid each habit of his is, from a week of digests
            # (`sim/expectations.py`, design section 3.1): one score per habit.
            # Floor 0.5: 0.94 on the V3 sample.
            "habits_him": {"enabled": False, "threshold": 0.5},
            # the gauge appraisal (`sim/appraisal_gauge.py`, design section 14):
            # one switch for the whole scorer. Off in DEFAULTS; only a bundle
            # turns it on, and turning it off is the whole rollback.
            "state_appraisal": {"enabled": False, "threshold": 0.6}
        }
    },

    "clock": {
        "mode": "real",
        "sim_start": "",
        "sim_speed": 60.0
    },

    "director": {
        # Who writes the scene she is in. "model" asks the director role every
        # tick: a second writer over the plan, which is what a character with a
        # world round her needs, because her day is full of people and places
        # the plan cannot know the state of. "plan" cuts the scene straight
        # from the schedule block in code -- where she is, what she is doing,
        # who is with her, whether she can be reached -- and makes no call at
        # all. For a character with no world, whose whole day is written once
        # from her own home file, the second writer was paying about $0.09 a
        # day to paraphrase the block back (66 to 83 scenes a day, 25 of 25
        # settings written "indoors") and was the only thing in her process
        # free to state a fact her day does not contain.
        "scene_source": "model",
        "tick_minutes": 20,
        "tick_min_minutes": 10,
        "tick_max_minutes": 90,
        "coast_when_asleep": True,
        "sleep_keywords": ["asleep", "sleeping", "lights out"],
        "recent_scenes_in_prompt": 6,
        "recent_days_in_prompt": 2,
        "max_open_threads": 8
    },


    "threads": {
        # small ongoing things as records: open / dormant / resolved
        # A thread about him that she has not raised builds pressure until it
        # becomes the thing she opens with. Without this every outlet for
        # `unsaid` was private -- the diary and an X post -- so the pressure
        # vented and the thread never reached him: one thread had resolved in
        # three days, and "why he really went quiet for three months: still
        # unasked" simply sat there.
        "pressure_after_days": 0.75,
        "pressure_per_day": 26,
        "pressure_unsaid_ref": 45,
        "pressure_per_unsaid": 0.9,
        "pressure_threshold": 40,
        "match_threshold": 0.5,
        "dormant_after_days": 3,
        "dormant_in_prompt": 5,
        "resolved_in_prompt": 5
    },

    "cast_defaults": {
        # meters for people the day compile adds to the cast
        "closeness": 30, "standing": 50, "tension": 10, "max_people": 30
    },

    "places": {"in_prompt": 12, "max_places": 60},

    "derive": {
        # His relationship meters, worked out from the message record instead
        # of typed into cast.json. The same numbers have to serve a fresh
        # install with no history and one carrying the whole May 2026 chat,
        # which a hard-coded closeness of 62 cannot do.
        "enabled": True,
        # The derived figure is not only a starting point: the live meters
        # drift toward it, slowly, forever. Otherwise closeness is a ratchet
        # that only the model can turn and only ever upward.
        "gravity_enabled": True,
        "gravity_every_hours": 6,
        "gravity_closeness_per_day": 2.0,
        "gravity_standing_per_day": 2.5,
        "gravity_tension_per_day": 3.0,
        # where a stranger starts
        "cold_closeness": 8, "cold_standing": 50, "cold_tension": 0,
        # closeness: contact DAYS, faded by age, deeper when both of them spoke
        "closeness_half_life_days": 45,
        "closeness_days_ref": 9.0,      # this many good recent days ~ 63% of the ceiling
        "closeness_ceiling": 72,
        "day_depth_ref": 12,            # exchanged messages in a day for full depth
        "day_floor": 0.35,              # a day where only one of them spoke still counts a little
        # what she knows about him is closeness a silence cannot take back
        "facts_ref": 30, "facts_ceiling": 22, "facts_max": 22,
        # knowing him survives a gap, but not untouched
        "known_floor": 0.45, "known_half_life_days": 30,
        # standing: does he carry his half of it
        # standing has three terms because the message ratio alone barely
        # moves: who starts the day, and how long he leaves her waiting
        "standing_span": 40,
        "standing_starts_span": 34,
        "standing_half_life_days": 6,      # how she has been treated lately, not on average
        "standing_absent_from_days": 2, "standing_absent_per_day": 4.5, "standing_absent_max": 26,
        "standing_per_wait_hour": 2.2, "standing_wait_max": 22,
        # tension: how long he has been quiet, and the worst silence they have had
        "tension_per_quiet_day": 6, "tension_gap_max": 30,
        "scar_from_days": 21, "scar_tension": 18, "scar_half_life_days": 10
    },


    "social": {
        # X as the second app on her phone (read-only). She may open it when
        # her phone is free, inside these hours, not more often than
        # look_min_minutes, at most max_looks_per_day, if x_monitor pacing
        # allows, with a probability that rises with boredom. What she
        # noticed stays in her situation block for recent_hours.
        "enabled": True,
        "hours_start": "07:00",
        "hours_end": "01:00",
        "retry_after_minutes": 8,   # a failed look retries this soon, and does not count
        "look_min_minutes": 90,
        "max_looks_per_day": 4,
        "base_probability": 0.35,
        "boredom_weight": 0.6,
        # posts from her last looks she may send him as a link ([share: ID]
        # in her reply becomes the URL), kept for share_hours
        "share_enabled": True,
        "share_hours": 24,
        # after she sends him a post, no share is in front of her for this long
        "share_cooldown_hours": 6,
        # A post she may send him is looked at BEFORE it is offered: every
        # picture on it is described and the description rides the offer, and a
        # post whose pictures could not be described is not offered at all.
        # Those looks are outside the vision day-budget
        # (`vision.max_calls_per_day`, spent by the scenery harvester by the
        # time she scrolls) and capped here instead.
        "share_looks_per_day": 20,
        # a post she sent him is liked and reposted by the account (curation caps apply)
        "like_shared": True,
        "repost_shared": True,
        # The FALLBACK only: the probability the account reposts a post she
        # sent him, rolled once per share, and used when her pick cannot run
        # (`curation.share_pick` off, no judge, or her taste has nothing on
        # that account yet). The log says which happened.
        "repost_shared_p": 0.35,
        # the look's own "might say" line rides her reply prompts as the thing
        # she wanted to show him (x_show_pending): from this salience, for
        # this long, at most this many prompts. share_salience is the impulse
        # path's bar without a mention. "look what i found" had stopped: the
        # only path was the impulse at salience 4.
        "share_salience": 4,
        "show_him_salience": 3,
        "show_him_hours": 12,
        "show_him_shows_max": 8,
        # ...and this many showings of the same line in the one imperative
        # slot with her answering something else, after which it is done
        "show_him_declines": 2,
        "share_declines": 2,        # the same for the posts on offer, put away for share_cooldown_hours
        # her own posts' likes, reposts and replies, read on the look and
        # given to her -- the account was a monologue
        "read_engagement": True,
        "engagement_posts": 6,
        "engagement_replies_max": 2,
        # being noticed answers the wanting-to-be-noticed, a little, and
        # is a small good thing; the move is here rather than left to the
        # state model, which reads the event and may charge nothing
        "engagement_craving_relief": 4,
        # ...and moves pride up by this much per new thing a post drew
        "engagement_pride": 3,
        "share_max_items": 6,
        "max_posts_per_read": 25,
        # how long what she saw on her last scroll stays in front of her: two
        # hours, not six -- a thing seen on a timeline is on a person's mind
        # for an hour or two, and at six the "emu person" was still in her
        # situation block all evening after she had said it (2026-09-04)
        "recent_hours": 2,
        # at the end of a look she also glances at the account's Likes tab;
        # likes not in her own action log are his, and she sees them
        "peek_likes": True,
        "likes_scrolls": 2,
        # and at the profile's following count; if it grew, the newest
        # follows are read and attributed the same way
        "check_follows": True,
        # and at the top of the followers list: anybody new who follows the
        # account is followed back (curation.follow_back) and is from then on
        # an account she cannot unfollow. The first read is a baseline and
        # nobody on it counts as new.
        "check_followers": True,
        "her_actions_in_prompt": 5,   # her own likes / follows / unfollows with reasons, in her prompt
        "his_likes_hours": 24,
        # a search of her own in a look, from data/taste.json queries; and
        # the trends tab for the zeitgeist filter
        "discover_p": 0.5,
        "discover_scrolls": 2,
        "trends_p": 0.5
    },


    "share_pick": {
        # WHICH post from her scroll she sends him, decided by her rather than
        # by code's text match against her own sentence (tomoe/share_pick.py,
        # docs/x-account.md section 2.3, docs/tool-calling.md section 16). The
        # one call in this project whose answer is a tool call that is acted
        # on: `send_this(id)` makes that post the only one her reply prompt
        # offers, `nothing` puts the thought away. Not the key of the same
        # name under `curation`, which is a different decision: what the
        # ACCOUNT does in public with a post she has just sent him.
        "enabled": True,
        # An answer that did not validate -- a tool name that was not offered,
        # an id that was not on the list, arguments that did not parse -- is a
        # decision not taken: the three candidates code matched stand for that
        # reply and the pick is tried again at her next free moment, this many
        # times per thing she wants to show him. Two, because a third ask of
        # the same question on the same list is a loop, and the offer it falls
        # back to is what shipped before this existed.
        "max_attempts": 2
    },

    # What she happens to know, retrieved a few lines at a time (sim/lore.py).
    # The persona dataset is 1,664 claims and the whole design question is how
    # little of it to show her: `min_score` is what stops the bucket firing on
    # every turn. A claim the era gate holds is never offered. `suppress_days`
    # is 0 and locks nothing out: a record she has already been reminded of is
    # reachable again the moment he names it, because a person asked twice
    # about her own job answers twice. Above 0 it holds a used record for that
    # many days, which is a repetition guard nobody asked for and which shut
    # her career record on the one message that reached for it.
    # `own_words_days` is the same hold applied to HER side of the window
    # alone, which is where the repetition actually came from.
    "lore": {
        "enabled": False,
        "file": "",
        # Whether a claim marked as coming from after the corpus ends is
        # withheld. **OFF, and his decision.** It was catching the wrong thing:
        # the mark had been put on the text naming a later year rather than on
        # when the thing described began, so the record of her own radio show
        # was shut -- it opens in 2003 and the same sentence traces it to 2016
        # -- along with her debut single and the roles she was already playing.
        # A character who cannot reach her own programme reads as somebody with
        # no career at all, which is what he saw in her replies.
        #
        # That fault has since been fixed and the gate stays off, because he
        # asked for it off. Thirteen claims now carry the part of themselves
        # that had already happened (`gate.until_then`), so turning this on
        # would withhold 165 claims and cut 13 back rather than shutting them:
        # her programme, her debut single, her agency and the roles she was
        # playing in 2002-2004 would stay reachable. With it off nothing is
        # withheld and nothing is cut, and the mechanism that releases a work
        # when he watches it (sim/watching_him.py) has nothing to release.
        "era_gate": False,
        # How many exchanges of the real conversation the retrieval is asked
        # against. His newest message alone is too small a window: a subject
        # arrives over several turns, and HER OWN WORDS are a cue -- she is
        # often the one who raised the thing, so what she just said should be
        # able to remind her of the rest of it.
        "cue_exchanges": 3,
        # standing material -- her register, her mechanisms -- is true every
        # minute and belongs in the bible, not in a bucket that competes with
        # what she is doing
        "standing_kinds": ["register", "mechanism"],
        # The phrases that let a record be found, by record id, written by
        # reading each one (yukarin/tools/triggers.py). Nothing else decides a
        # match: comparing his message against the record's own text compares
        # it against conversational speech, which is mostly grammar, and the
        # question about a show was answered by a record about a
        # witch on the strength of 「どんな」. A character with no list here can
        # be reminded of nothing.
        "triggers_file": "",
        # Her seeded memories as records (yukarin/week/memory_records.py), his
        # call: a fact off the corpus is her record and is found by name, not
        # rotated through the prompt as a memory. Their phrases are a second
        # list, merged with the first. Empty for a character with none.
        "memory_file": "",
        "memory_triggers_file": "",
        # How squarely the message has to name a record before she is reminded
        # of it. A phrase carried by one record alone is worth 1.0 and one
        # shared by three about 0.8, so below 1.0 a single naming is enough and
        # the list of phrases is what holds the silence; above 1.0 the message
        # has to name the same record twice.
        "min_score": 0.5,
        "max_lines": 3,
        "max_chars": 900,
        "max_chars_per_line": 320,
        "suppress_days": 0.0,
        # How long a record she has already been offered stops being reachable
        # from HER OWN recent messages. His words reach it whatever this says.
        # The cue is the last `cue_exchanges` exchanges and her own telling of
        # an anecdote stays in that window for the next few turns, so without
        # this the retrieval hands her back the story she just told, turn after
        # turn: on 2026-09-02 the Umeda station anecdote came back four times
        # in forty-five minutes, she told it three turns running, and the
        # continuity editor threw away a drafted reply for repeating it. Set to
        # 0 to let her own words reach a told record again immediately.
        "own_words_days": 3.0,
        # A part she played, in a work HE has just named, is not a line she
        # can afford to lose. On 2026-09-03 he named a 2010 lead of hers, the
        # record was retrieved at full score, and the whole block's character
        # cap threw all three retrieved lines away on a crowded tick, so she
        # denied the part. A retrieved line is ordinary and takes its chances
        # against everything else she is carrying; a record of one of these
        # kinds, named by HIM, at or above `pin_score`, is pinned and bypasses
        # the budget. `pin_max` bounds it: pinned lines are the ones the gate
        # cannot drop, so there is never more than one of them from here.
        "role_kinds": ["role", "career", "work"],
        "pin_score": 1.0,
        "pin_max": 1,
    },

    "memory": {
        # how she forgets (sim/memory.py). A fact about him has a weight 1-5
        # (the compile sets it: passing detail 1, habit 3, name/work/birthday
        # 5) and a half-life by weight; its score is weight * 2^(-age/half);
        # below fact_min_score it is out of her prompt until a word in his
        # message cues it (then it comes back and is refreshed). A fact
        # learned again reinforces instead of duplicating. Cast situations
        # older than cast_age_days are shown dated, older than
        # cast_forget_days she has lost track of.
        "enabled": True,
        "half_life_days": [5, 14, 35, 120, 400],
        "fact_min_score": 0.5,
        "max_facts": 40,
        # what she knows about the people around her (cast_facts), same
        # half-lives as the facts about him, shown per person
        "cast_facts_max": 6,
        "max_recalled": 4,
        # ...of which this many may be rows the WORDS never found, which came
        # back on a cosine alone. Below max_recalled by design: a run of
        # cosine-only rows used to take every slot and leave the word hit out,
        # and every by-meaning row judged on 2026-09-04 was wrong.
        "max_cosine_only": 2,
        "duplicate_jaccard": 0.6,
        "cast_age_days": 14,
        "cast_forget_days": 45
    },

    "context": {
        # The one budget over her prompt: target_tokens. The model's window
        # is max_tokens (1M on both live models; this is not an output cap).
        # Everything in the prompt rides whole -- the system half, what she
        # carries, the situation block -- and the thread's verbatim window
        # fits itself to what is left of the target after them, whole days
        # at a midnight (sim/thread.py _window). Tokens are estimated at
        # chars_per_token and the ratio is calibrated from the model's own
        # prompt_tokens on every persona call (kv context_ratio). The
        # sub-budgets that used to sit under this one (history, carried,
        # situation, per-section warn sizes) went on 2026-09-04: measured
        # prompts of 30-50k against a 64k target, and the gates they drove
        # were cutting the situation block for the sake of a number here.
        "max_tokens": 256000,
        "target_tokens": 200000,
        "chars_per_token": 3.0
    },

    "diet": {
        # her media diet (tomoe/diet.py): what she is into, from her X taste
        # (accounts at or above account_min_score likes-minus-dislikes), the
        # things the day compile saw her do for herself (kept keep entries,
        # shown for things_days), her own likes and posts.
        "enabled": True,
        "keep": 120,
        "things_days": 14,
        "account_min_score": 2
    },

    "money": {
        # her allowance (embodied/money.py): allowance_yen from mom on
        # allowance_day each month; the director spends from it per scene
        # (`spent`), never below zero; under broke_ratio of the allowance she
        # is "nearly broke" in her tags, her situation and the schedule.
        "enabled": True,
        "allowance_yen": 5000,
        "allowance_day": 1,
        "start_balance_yen": 2800,
        "broke_ratio": 0.15,
        # the director does not see what the last scene bought and re-narrates
        # it: the same purchase inside this many minutes is one purchase
        "duplicate_minutes": 45,
        "log_keep": 200
    },

    "attachment": {
        # Attachment behaviour under threat (sim/attachment.py): protest
        # (pursue, test, escalate) or deactivate (go cold, get busy,
        # minimise), and the switch between them. Threat is read off the
        # record, the strategy is drawn from her self-beliefs, the meters,
        # the sentiments, the gauges and what the last episodes got her.
        "enabled": True,
        # threat terms (sum, then scaled by attachment sentiment)
        "silence_from_hours": 3.0,
        "silence_full_hours": 14.0,
        "silence_floor": 0.35,          # a silence at an hour he is never about still counts this much
        "w_silence": 0.55,
        "read_left_minutes": 45,
        "w_read_left": 0.3,
        "tension_from": 30.0,
        "w_tension": 0.35,
        "w_rupture": 0.3,
        "rupture_hers_factor": 0.5,     # a break she caused threatens less than one he did
        "scar_days": 14,
        "w_scar": 0.08,
        "w_scars_cap": 0.2,
        "w_streak": 0.12,
        "w_streak_cap": 0.3,
        "attachment_floor": 0.4,        # scale at zero attachment
        # episode
        "engage_from": 0.5,
        "engage_minutes": 30,           # threat must hold this long; no flapping
        "release_below": 0.3,
        "release_fraction": 0.6,        # or this far down from the episode's peak
        "max_hours": 36.0,
        "max_switches": 3,
        "keep": 60,
        "event_salience": 2,
        "memory_weight": 3,
        # selection: signed pulls, + protest / - deactivate
        "base": 0.3,
        "belief_floor": 0.3,            # a belief with no evidence still pulls this fraction
        "strain_discount": 0.7,         # a belief under full strain pulls this much less
        "belief_pulls": {"wont_stay_quiet": 0.5, "alone_is_shameful": 0.3,
                         "not_come_looking": -0.5, "slip_ends_it": -0.35,
                         "seen_undoes_me": -0.4, "mask_holds": -0.3},
        "history_episodes": 4,
        "history_weight": 0.35,
        "history_half_life_days": 10.0,
        "w_closeness": 0.4,
        "w_tension_select": 0.5,
        "w_attachment": 0.4,
        "w_resentment": 0.5,
        "w_anxiety": 0.6,
        "w_anger": 0.4,
        "w_shame": 0.7,
        "w_sadness": 0.5,
        # switching
        "protest_exhaust_hours": 5.0,
        "protest_streak_stop": 3,
        "shame_switch": 60.0,
        "rebound_min_hours": 4.0,
        "rebound_from": 62.0,           # longing or craving
        "rebound_p_base": 0.05,
        "rebound_p_per_hour": 0.04,
        "rebound_p_per_need": 0.5,
        "rebound_p_cap": 0.6,
        "sadness_on_give_up": 8.0,
        "shame_on_break": 10.0,
        "soft_cap": 85.0,
        "resentment_on_burnout": 2.0,
        # what an episode's end says about her beliefs: negative strains,
        # positive confirms, by strategy and outcome
        "belief_tests": {
            "protest": {"resolved": {"not_come_looking": -6.0, "wont_stay_quiet": 4.0},
                        "failed": {"not_come_looking": 5.0, "wont_stay_quiet": -3.0}},
            "deactivate": {"resolved": {"not_come_looking": -8.0, "mask_holds": 3.0},
                           "failed": {"not_come_looking": 3.0, "mask_holds": 2.0}},
            "rebound": {"mask_holds": -5.0, "seen_undoes_me": -3.0}
        },
        # readers
        "impulse_protest": 22.0,
        "impulse_deactivate": 30.0,
        "protest_extra_streak": 2,
        "withhold_deactivate": 0.3,
        "delay_protest": 0.7,
        "delay_deactivate": 1.6
    },

    "commitments": {
        # promises to named people that stake something outside her head
        # (sim/commitments.py): yen put aside from her allowance, a window
        # the schedule must keep, her standing with that person. The commit
        # model names what she agreed to in an exchange; code binds it only
        # with a cast counterparty and a real date inside the horizon; the
        # compile settles it from the record alone (a scene with them in the
        # window, a spend that names the thing) and never reverses it.
        "enabled": True,
        # what she can be carrying at once -- this is the real bound on
        # accumulation, checked when a promise binds
        "max_open": 6,
        # a rate limit on the CALL, not on how much she may promise. At 3
        # it truncated a real day: the FamilyMart trip, the yukata and the
        # hand cream all bound in one 23:40 batch, and the library at 9
        # that she agreed to with Aya hours later was never even asked
        # about -- so the plan never reached the 05:00 schedule and she
        # went on talking to him about it. `max_open` keeps the ceiling;
        # when this one bites it now says so in the log.
        "max_new_per_day": 6,
        "max_days_ahead": 14,
        "similar_threshold": 0.4,
        "attend_slack_minutes": 90,
        "buy_match": 0.3,
        # what keeping and breaking cost, applied once at settle
        "kept_regard": 4,
        "kept_standing": 3,
        "kept_pride": 8,
        "broken_regard": 8,
        "broken_irritation": 15,
        "broken_standing": 8,
        "broken_closeness": 4,
        "broken_guilt": 18,
        "broken_shame": 10,
        # calling it off herself, in words, before the day
        "cancel_guilt": 5,
        "cancel_irritation": 5,
        # She came, so it is kept. She was late, so it is not the same as
        # having been on time: `attend_slack_minutes` is 90, and turning up at
        # half past twelve for a nine o'clock was settling with the same
        # regard, the same pride and the same "she kept her word".
        # Is she going to make it? The map already knows what a place costs to
        # reach; nothing compared it to the clock, so she could be at the genkan
        # with a nine o'clock promise and no idea. `warn_within_minutes` is how
        # close to the wire it starts being on her mind at all.
        #
        # She is not honest with herself about it: `optimism_minutes` is what she
        # shaves off the real journey when she is already behind -- the belief that
        # she can still make it if the lights go her way. Past `knows_late_minutes`
        # of true shortfall the optimism stops working and **she knows**, which is
        # the point: a lateness she walked into knowingly is hers, and one she never
        # saw coming is the system being unfair to her.
        "warn_within_minutes": 45,
        "optimism_minutes": 8,
        "knows_late_minutes": 12,
        # a lateness she saw coming and walked into costs more than one that
        # happened to her
        "knew_guilt_factor": 1.6,
        "late_after_minutes": 15,
        "late_regard": 1,           # instead of kept_regard
        "late_pride": 2,            # instead of kept_pride
        "late_irritation": 6,       # the person who was waiting
        "late_guilt": 6,
        "memory_weight_kept": 2,
        "memory_weight_broken": 3,
        "keep": 80,
        # promises to HIM (text_by / send / tell), named by the commit_him
        # role from her own messages and settled off the message record
        "him_enabled": True,
        "him_messages_shown": 12,
        "him_settle_seconds": 90,
        "him_max_new_per_day": 5
    },

    "exchange": {
        # a beat landing while she has not yet answered the live exchange
        # waits a pass, up to this many minutes past its own time
        "hold_minutes": 20,
        # a low-salience idle beat she gives no exchange gets a stamp-only
        # reply from her own set at this probability (code, no model call)
        "stub_stamp_p": 0.5,
        # THE CHAT SO FAR carries each turn's stamp and a marker for a gap of
        # this many minutes; 0 turns the markers off
        "chat_gap_marker_minutes": 20,
        # her side of her social life (tomoe/exchange.py). Two authors now: the
        # beat's own ja lands verbatim as the other side's opener, then her
        # reply (cast_reply, seeing her state) and their continuation
        # (cast_turn, seeing ONLY what that person could know -- never her
        # interior) alternate. One author wrote both sides before, so nobody
        # could surprise anybody and her friends answered her feelings
        # instead of her words.
        "enabled": True,
        "kinds": ["line", "group", "call", "video", "in_person"],
        "min_salience": 2,
        # every kind of exchange shares this, so the group used to compete
        # with LINE and the kitchen for the same eight slots
        "max_per_day": 12,
        # ...and a separate allowance for the late stretch, because the day's
        # budget is SPENT by then: on the days that hit the cap the eighth
        # exchange starts between 21:13 and 23:12, so a late beat would land
        # as an opener nobody ever answers -- and `Health._chat_alive` counts
        # TURNS, so the chat meant to keep her up would still read as zero.
        # These slots are for late group beats only and are not usable by day.
        "late_reserved": 3,
        "keep": 120,
        "in_prompt": 20,          # exchanges of today + yesterday shown whole (two days run to ~12)
        # ...except the group, which at the new volume is a couple of hundred
        # messages a day: the newest `group_full_recent` group conversations go
        # in verbatim and the older ones as the gist they already carry. Two
        # days of group chat whole is ~23k characters against a `chat` section
        # budgeted at 1,000 tokens, and most of it is about nothing on purpose.
        "group_full_recent": 2,
        # the pause between turns is longer at night and when the next
        # speaker's own day has them in class or at a fixture; a picture is
        # looked at before it is answered. Multipliers on the pause.
        "pace_night": 2.4,          # 01:00-06:00
        "pace_late": 1.6,           # 22:00-01:00
        "pace_busy": 2.2,           # availability 0.15 (class, a fixture)
        "pace_glance": 1.5,         # availability 0.5
        "pace_photo_seconds": [20, 70],
        # Nobody sits chained to the phone. Every gap between messages was
        # `prev_len/6 + U(20,150) + n/3` -- bounded about 29-198 seconds by
        # construction, so a three-hour chat came out as a continuous
        # two-minute drip with no tail at all: mean 1.9 min, median 1.9, max
        # 3.2 over thousands of samples. Real ones go quiet because somebody
        # got up. `away_p` is the chance a gap is an absence instead of a
        # pause, and the reasons carry their own lengths (`tomoe/exchange.py`
        # AWAY), weighted so the late-night ones are the sleepy kind.
        "away_p": 0.22,
        # How much of her chat with him her own side of an exchange can see. It
        # was four messages truncated to 80 characters, a literal from when an
        # exchange was six turns long: her friends ask her about him and she
        # was answering from a keyhole.
        "him_messages_shown": 10,
        "him_message_chars": 160,
        # An absence is not free. Every one of them multiplies the chance the
        # conversation keeps going: a chat that has already stopped twice for
        # somebody's dinner and somebody's bath is thinning out, and it should
        # die of that rather than run its rounds regardless.
        "away_drag": 0.94,
        # And one reason ends a night rather than pausing it. Somebody who
        # fell asleep on the chat is out until the morning -- no turns, no
        # beats, out of the speaker pool -- and when everybody who was in it
        # has gone, the chat is over. `sleep_wake_hm` is her clock, which is
        # theirs; the jitter is minutes either side so they do not all wake at
        # the same minute.
        "sleep_wake_hm": "07:10",
        "sleep_wake_jitter_min": 40,
        "interrupt_delay_seconds": 120,
        # Being mid-conversation with him is a reason to make the girls wait a
        # couple of minutes. It is NOT a reason to go silent for seven hours,
        # which is what happened: `_busy_with_him` was true from the moment his
        # message landed until she answered it, and on 2026-08-27 a message
        # that arrived while she was asleep froze every exchange for 453
        # minutes -- Kaito's beat died in her doorway and Aya's was dying while
        # she sat across the table from her at the library. Only a RECENT
        # message means she is actually with him.
        "busy_window_minutes": 12,
        # and never for ever: after this many deferrals the person in front of
        # her gets an answer whatever her phone is doing
        "busy_max_pushbacks": 4,
        "max_live_minutes": 45,
        # how many times she may answer within one exchange, and the chance
        # the other person comes back after each of her replies
        "max_rounds": 2,
        # A group chat is not a bounded errand: it is a venue that runs for
        # hours. At `continue_p` 0.6 and 4 rounds the expected length was 2.2
        # rounds -- about ten messages -- and five of those a day is fifty
        # messages between four girls, which is not a chat. The one-to-one
        # numbers stay where they are; only the group is opened up.
        "group_max_rounds": 12,
        "group_continue_p": 0.87,
        # She is not the chat. Her silence used to end it -- one message from
        # Rena, no answer, the exchange closed and three girls stopped talking
        # to each other. On 2026-08-28 four of the seven group conversations
        # were one message long for exactly that reason. The others carry on
        # without her for this many passes, and she can walk back into what
        # they said; only then is it over.
        "group_without_her": 6,
        # ...and at least this many of them have to be awake for it to be a
        # chat rather than one girl talking to herself. Reached now whenever
        # she cannot take her turn -- asleep, at school, at the table -- and
        # not only when she reads it and says nothing, which was the one case
        # the first version covered and the rarest of the three.
        "group_without_her_min": 2,
        # ...and the room does not need her to have been in it at all. A group
        # beat the day's phone budget or the late reserve refuses her was
        # filed as one unanswered line and that was the end of it: 17 of the
        # 47 group conversations in a week are exactly that row, and the other
        # two girls were in the chat the whole time. Now the beat opens a
        # conversation with her out of it from the first turn, the others
        # carry it under the same `group_without_her` passes, and she reads it
        # when her phone comes back. Capped per day, because each round of one
        # is one to three model calls nobody was owed. 0 turns it off.
        "alone_beats_per_day": 3,
        # She may start one herself. Every beat is somebody reaching HER --
        # the planner is refused any beat written as her (`tomoe/cast.py`) and
        # that stays -- so in the whole record she opens none of the 47 group
        # conversations, while three girls open all of them. This is the other
        # door: at most this many a day, decided the way her urge to text him
        # is decided (`sim/impulse.py`: a hard gate, then a score, then a soft
        # roll), and written in her own voice through the room she already
        # talks to them in. 0 disables it.
        "self_open_per_day": 1,
        # how quiet the room has to have been before she is the one to break
        # it, in minutes; and how close a friend's own beat may be before she
        # leaves it to them, because two openers a minute apart is not a girl
        # starting a conversation, it is a collision.
        "self_open_quiet_minutes": 95,
        "self_open_clear_minutes": 30,
        # the score her own state has to make for it, on the same scale the
        # impulse uses: loneliness, boredom and being left out push, and
        # having just been in the chat does not.
        "self_open_threshold": 26.0,
        "self_open_weights": {"loneliness": 0.22, "boredom": 0.16,
                              "validation_craving": 0.14, "belonging_low": 0.30},
        # A speaker may not say again what they have already said in this
        # conversation. Aya sent the same three-bubble block four times in
        # twenty minutes on 2026-08-28: the prompt asked her not to and
        # nothing checked. Compared against that speaker's OWN last turns.
        "no_repeat_own_turns": 6,
        # THE SAME THING SAID AGAIN, in the three shapes the old test could
        # not see. `no_repeat_own_turns` above compares whole messages by one
        # speaker; the loops in the record were a sentence repeated inside a
        # longer message (07:17 and 07:21 on 2026-09-07: the messages 57%
        # alike, the sentence in them identical) and an echo of SOMEBODY ELSE
        # two minutes later (21:44 and 21:46 on 2026-09-06). A message is
        # split on sentence enders; a sentence of at least `repeat_min_chars`
        # characters that anybody in the room has said inside the last
        # `repeat_window_turns` turns is a repeat, and a message that is more
        # than half repeats is dropped and logged. A short deliberate echo is
        # never touched, and nothing is ever rewritten or asked for again.
        "repeat_min_chars": 12,
        "repeat_window_turns": 20,
        # WHAT THE CONVERSATION HAS ALREADY TRIED. Every call that writes a
        # turn returns a one-line gist and the record kept only the last one,
        # so nothing could tell a call that a move had been made: one girl
        # played "fine, I will ask, but I am still the one who decides" at
        # 07:19 and again at 07:23 in different words. The room keeps the
        # list, both writers are shown this many of its newest entries, and
        # the ask to a member who writes her own turns carries it.
        "moves_shown": 8,
        # A ROUND THAT ADDED NOTHING. One where the repeat filter dropped a
        # bubble, or where somebody's move was the move they made last time.
        # Each one multiplies the chance the room continues; two in a row and
        # it is over. At 0.87 a round with nothing to weigh it the group ran
        # its twelve rounds whether or not anybody had anything to say.
        "stale_drag": 0.5,
        # A GROUP MESSAGE IS ONE THOUGHT typed with a thumb. This is a LOG
        # threshold and nothing else: a bubble longer than this is counted on
        # the room's record and named in the log, never cut, never asked for
        # again and never rewritten. Her 07:30 was three clauses of interior
        # at half past seven on the way to school, which is a fact about the
        # prompt and not something to paper over.
        "group_bubble_chars": 90,
        # ...and how far back "already said" reaches, in hours of her clock.
        # The check could see the live conversation only, so a line came back
        # word for word in the NEXT one: Aya's line about the notebook went
        # out at 07:21 on 2026-09-02 and again at 13:14, with the earlier copy
        # sitting in the prompt that wrote the second. 0 turns the wider
        # window off and leaves the live conversation as the whole of it.
        "no_repeat_hours": 12,
        # SHE WENT TO SOMEBODY AND HAD NOTHING TO SAY. The room logged it
        # and nothing acted on it, so the chooser was offered the same
        # person again on the next pass and took her: one character opened
        # a chat with the same friend four times in an evening, and the
        # filter deleted every bubble. This many minutes of her clock and
        # that person is off the list of people she may write to; the
        # chooser is told so in words, with the time she comes back. 0
        # turns the gate off.
        "reopen_after_nothing_minutes": 120,
        "group_max_live_minutes": 180,
        "continue_p": 0.6,
        # a group round is multi-agent: each member decides to jump in on
        # their own draw (base chance scaled by their attention), each with
        # their own call and their own edges, capped per round
        "group_jump_in_p": 0.7,
        "group_max_speakers": 3,
        # How long a room waits for a turn from somebody who runs as her
        # own process before going on without her (sim/rooms.py: a cast
        # row carrying `agent`). Her process has to read her mailbox,
        # build a prompt and be answered by a model, so this is seconds
        # rather than one pass; past it the room says so in the log and
        # never asks her again in that conversation, because the one
        # thing it must not do is write the turn for her.
        "agent_turn_deadline_seconds": 180,
        # and how long a beat waits. Longer, because a beat is the thing
        # she OPENS with: nothing is live, nobody is sitting in front of
        # a chat, and a beat that arrives late is still the day going as
        # planned. Past it the beat is dropped and the log says so: a
        # plan is not a promise that somebody spoke.
        "agent_beat_deadline_seconds": 600,
        # how many of a room's turns go out with an ask. She is sent what
        # she has not seen since she joined, capped here.
        "agent_context_turns": 12,
        # 「メッセージ来てたし 返事早くしないと 友達じゃなくなっちゃう」 -- her own words,
        # with a stated consequence, and nothing charged her for it. A slow
        # answer to a friend costs standing with them; no answer at all costs
        # more. Small numbers: this is a slow pressure, not an event.
        "reply_slow_minutes": 25,
        "reply_slow_standing": 1.5,
        "reply_miss_standing": 3.0,
        "reply_slow_belonging": 2.0,
        # 「休んだら みんなの話についていけなくなるもん。その1日が命とりなの」 -- missing the
        # chat compounds: each group conversation she is not in raises
        # `behind`, taking part works it off, and the cost of the NEXT miss is
        # scaled by it. That is the compounding, and it is why she over-attends.
        "behind_step": 1.0,
        "behind_decay": 1.0,
        "behind_max": 6.0,
        "behind_compound": 0.35,
        # when a slip out of the register she performs is the TRUE reading and
        # the checker is told not to flag it (voicecheck `context` / a rule's
        # `skip_when`). Which register that is belongs to the character's own
        # rule file and is named nowhere here. Her sheet
        # says the mask slips when she is tired, angry or cornered; the source
        # says the plainer thing, that it comes off for the person she has
        # stopped performing for. `slip_energy_below` was 30, which 337
        # recorded states never reached (her floor is 45); 54 is her measured
        # p10, so "tired" is the tiredest tenth of her nights rather than a
        # state she never has.
        "slip_anger_from": 50,
        "slip_energy_below": 54,
        "slip_tension_from": 50,
        # by role, so it survives a recast: alone with the confidante the mask
        # is down and the dialect is not a mistake. Never in a group.
        "slip_with_roles": ["confidante"]
    },

    # Everybody who is not the cast. She rode a packed train with nobody on
    # it, stood in a konbini with nobody behind the till, and spent a school
    # day in a building holding one class of girls none of whom were ever in
    # the room. Who is plausibly somewhere comes from that place's `kind` in
    # `data/places.json`; code picks the slot, the model writes the person.
    # They never enter `relationships`, the graph or `cast_chat` -- an
    # encounter leaves an `events` row and nothing else.
    "npc": {
        "enabled": True,
        "seed": "scail",
        # at most this many a day, and never two in a row inside `gap_minutes`
        "max_per_day": 4,
        "gap_minutes": 45,
        # the roll happens on a cadence, not on every pass of the loop
        "check_minutes": 15,
        # the chance per check, by the place's kind. A konbini is a
        # transaction and nearly always has one; a park is mostly empty of
        # anybody who would speak to her.
        "place_p": {
            "konbini": 0.55, "school": 0.30, "commute": 0.16, "station": 0.16,
            "shop": 0.22, "library": 0.14, "shotengai": 0.16, "museum": 0.14,
            "city": 0.12, "park": 0.08, "shrine": 0.10, "home": 0.0,
        },
        "place_p_default": 0.08,
        # somebody on her own is who gets spoken to; three girls together are
        # a wall
        "alone_multiplier": 1.0,
        "with_people_multiplier": 0.45,
        # how often the person is one she has seen at this place before. This
        # is what gives the konbini a regular clerk instead of a new stranger
        # every single visit.
        "known_face_p": 0.55,
        # a name is learned where you would learn one: at school, or off
        # somebody met this many times
        "name_after": 4,
        # a face met this often is named by `/npc` as a cast candidate; 0 is
        # never. You do not remember the person on the till, and a stranger
        # who keeps turning up does not change her life -- the value of the
        # other people is that they are THERE (`around`), not that they matter.
        "promote_after": 0,
        "keep": 60,
        "moments_keep": 120,
    },
    "social_graph": {
        # tomoe/social_graph.py: what the people around her actually think, of
        # her and of each other, as edges (view + regard + irritation)
        # updated once a day at the compile from what each person WITNESSED.
        # Ground truth her guesses are settled against; readers: cast turns,
        # the day planner, the spiral settle, the witnessed-goal price, the
        # showrunner, the ick, /graph and the app's backstage.
        # The edges belong to the WORLD, so the section is assigned to
        # `world_owner` in Config.REQUIRES: a character in a world somebody
        # else keeps has it off, seeds and updates nothing, and every one of
        # those readers takes the owner's compiled edges out of the world file
        # through the same object.
        "enabled": True,
        "max_updates_per_day": 5,
        # clamps on one day's movement: irritation is fast, regard is earned
        "regard_step": 8,
        "irritation_step": 15,
        "irritation_half_life_days": 5,
        "view_max_chars": 220,
        # how many of a speaker's edges reach their cast_turn prompt
        "in_prompt_edges": 6
    },

    # her past as cards (sim/cards.py): code cuts a day into episodes (his
    # chat at silences of delivery.gap_marker_hours, each exchange with her
    # people whole); one call a day at the compile writes a card per
    # episode -- the shape in her language, one to three lines quoted exactly
    # (an anchor that is not in the record is dropped), what it left her
    # feeling. Never faded, never rewritten; a day compiled again replaces
    # its cards. The thread shows the cards of the days past its verbatim
    # window at their time; recall searches them by words and by meaning
    "episodes": {
        "enabled": True,
        "anchors_max": 3,
        # lines of one episode handed to the writer; a 200-line group night
        # is cut at this and the card says so in its count
        "max_lines_per_episode": 160,
        # two exchanges in the same room this close are one conversation with
        # a pause in it; an episode still under min_lines after merging (a
        # sticker, a photo, one unanswered line) goes into the day's one
        # odds-and-ends card. Before this: 20 to 27 cards a day
        "merge_gap_minutes": 120,
        "min_lines": 3,
        # the thread shows a card's exact lines and feeling for this many
        # days back, the shape alone beyond; the words stay in the card
        "anchors_days": 3
    },

    # sentence embeddings for retrieval (sim/embed.py), local, on the GPU,
    # vectors kept in the save. A cosine under min_cos counts for nothing
    # (unrelated Japanese sentences sit near 0.7 on e5); above it, 0..1
    # times weight, the size of one strong word overlap. Off, every reader
    # searches by words alone
    "embed": {
        "enabled": True,
        "model": "intfloat/multilingual-e5-small",
        "batch_size": 32,
        # empty = load the model in this process (sentence-transformers, torch).
        # A URL such as "http://127.0.0.1:18320/v1/embeddings" = post the texts
        # there (OpenAI embeddings shape, `input_type` query|passage, the
        # server adds the e5 prefix) and never import torch; tools/embed_server.py
        # is the one shared process. url_timeout is seconds per request, one retry
        "url": "",
        "url_timeout": 30,
        # measured on her cards: unrelated pairs median 0.78-0.81, 90th
        # percentile ~0.83, a true hit 0.85-0.90 in either language. Nothing
        # under min_cos; weight at top_cos and above. Scaled so a 0.88 hit
        # ranks beside a good word match (~2) and the floor is noise (~0.4)
        "min_cos": 0.82,
        "top_cos": 0.90,
        # a pool of ONE-LINE rows sits on a different scale: with nothing
        # but a sentence to go on, everything is closer to everything, so
        # both ends come down. Measured over eight Japanese cues against her
        # 157 English facts and five English cues against her 270 Japanese
        # memories: the right answer 0.800-0.881, the 90th percentile of the
        # rest 0.745-0.806. So the signal is real and thin, which is why it
        # is ADDED to the word score rather than replacing it and why the
        # fade score still decides what a row is worth. [floor, top] per
        # pool; a pool not named here is on min_cos/top_cos
        "cos_by_pool": {"fact": [0.80, 0.87], "selfmem": [0.80, 0.87]},
        "weight": 3.0,
        # ...and those two hand-set numbers are only right for the save they
        # were measured on. Re-measured 2026-09-04 on both saves with 30 real
        # cues each: a Japanese cue against Japanese rows sits about 0.06
        # higher than an English cue against English rows, so 0.80 left 9% of
        # the first character's facts above the floor and 100% of the second
        # character's own memories and episode cards above it -- her whole
        # pool counted as a hit on every cue. So each pool measures its own
        # floor once per boot (`sim/embed._calibrate`) from real cues out of
        # this save's record against this pool's stored vectors, and puts it
        # `calibrate_margin` above the `calibrate_pct`th percentile. The
        # measurement wants the percentile higher -- the true top hit for a
        # cue sits at the 99th percentile of the rest on this model -- but 90
        # is where it starts. False, or a pool with fewer than
        # `calibrate_min_rows` rows or a save with fewer than
        # `calibrate_min_cues` messages, and the numbers above stand
        "calibrate": True,
        "calibrate_pct": 90,
        "calibrate_margin": 0.01,
        "calibrate_sample": 400,
        "calibrate_cues": 40,
        "calibrate_min_rows": 5,
        "calibrate_min_cues": 12,
        # Half the cosine belongs to the ROW rather than to the cue. Averaged
        # over 30 unrelated cues, the most central rows of the first
        # character's fact pool sit at 0.804 against a pool mean of 0.769 --
        # a spread of 0.035 where the whole band from floor to full weight is
        # 0.07 -- and one row was the top hit for 5 of 30 cues that had
        # nothing in common. That is what put the same folder of his in front
        # of her for a festival group chat and for a hair clip. So each row's
        # own mean over the calibration cues is subtracted before scoring: a
        # row that is close to everything gains nothing by it, and a row that
        # is close to THIS cue keeps its lead. Measured in the same pass as
        # the floor, so it costs nothing extra; False restores the raw cosine.
        "center_rows": True,
        # A row that arrives on a cosine ALONE, with no word in common with
        # the moment, must share at least one content word with the cue.
        # Every one of the six by-meaning rows judged wrong on 2026-09-04
        # shared no word at all with the cue that brought it back, and this
        # would have stopped all six. It is a weaker test than the word
        # search's own (which wants one Latin word of four characters, or two
        # keys for her own memories), so a row the words nearly found still
        # gets in on its meaning.
        "require_shared_word": True
    },

    "recall": {
        # remembering on cue (sim/recall.py): his message points at the past
        # (trigger_regex) or strongly matches the compiled record (score
        # without a cue); the record is searched by words, the best
        # excerpts go to one call that writes what she remembers with its
        # clarity; in a thread during her read delay.
        "enabled": True,
        "trigger_regex": "remember|last time|you said|you told|back in|that time|when you|did you ever|the other day|last week|in may|before you|used to|first time|\\b\\d{1,2}/\\d{1,2}\\b",
        "min_score_without_cue": 1.6,
        "max_excerpts": 5,
        # How many of those excerpts may be rows the WORDS never found, which
        # joined on a cosine alone. On 2026-09-04 a cosine-only row took third
        # place of five and reached her mouth ("I know you looked at a meme post on a forum, but I can't place when"). Below
        # `max_excerpts`, so the words always keep some room.
        "max_cosine_only": 2,
        # The machinery's own record of her day (`events`) is searched too,
        # by words and by meaning: some things are in no other store, and her
        # one encounter with a title she was later asked about sat in this
        # table for sixteen days while the retrieval read past it. Salience is
        # the filter and the weight: an event fades on her own life's
        # half-lives (`self_memory.half_life_days`) from `events_weight`,
        # because a thing that happened to her is not a fact about somebody
        # else. `events_scan` bounds both the search and the vector pool.
        "events_min_salience": 2,
        "events_scan": 1200,
        "events_weight": 0.8,
        # A cue he typed in English or romaji, crossed to the Japanese the
        # record is written in: a thing she knows by name and his own list
        # both hold a title's two spellings, and what is left when neither
        # does is the kana the romaji itself transliterates to. Local, no
        # fetch -- this runs on the loop thread.
        "cross_script": True,
        # What the answer has to cite, and what the code checks. The role must
        # name the excerpt the memory comes from, and a memory that says one
        # of them SAID something about a word of his message that is in none
        # of the excerpts is not written (`[recall] not grounded: ...`).
        # `subject_common_share` is which of his words name a thing at all: a
        # word in more than 2 per cent of her rows is grammar.
        "require_grounding": True,
        "subject_common_share": 0.02,
        "max_per_day": 20,
        "wait_seconds": 25,
        "keep": 60
    },

    "intent": {
        # typed initiation (sim/intent.py): when the impulse fires, one call
        # names the urge (share / ask / complain / check_on / tease /
        # continue / nothing) before the persona writes.
        "enabled": True,
        # The feeling deciding this, named for the call. `confront` and
        # `make_up` have been valid kinds since this was written and nothing
        # ever pointed at them, so the model reached for them roughly never.
        # Ordered by which wins when several are up: shame first, because it is
        # the one that stops her.
        "shame_from": 45,
        "anger_from": 40,
        "guilt_from": 50,
        "sadness_from": 45,
        "pride_from": 60
    },

    "experience": {
        # what she makes of what she watches / reads / listens to / plays
        # (sim/outlook.py): a scene whose activity matches trigger_regex
        # gets one call; the result joins her media diet.
        "enabled": True,
        "trigger_regex": "watch|episode|\\banime\\b|manga|reading|novel|listening|song|playlist|earphones|headphones|playing|switch|game|youtube|drama|movie|film",
        # the cue above is cheap and catches the verb; this is the OBJECT, and
        # the activity must carry one. Without it "reading" matched "reading
        # his reply" and "switch" matched "switching", so 48 of the 61 eligible
        # scenes over five days were him, the chat, the steam in the bath or
        # her dad talking -- and since only `max_per_day` fire, the slot was
        # usually spent on his messages before a watching scene ever came up.
        # A title on her watchlist counts as an object too, so a scene that
        # names the show without saying "episode" still qualifies.
        "object_regex": "\\banime\\b|episode|\\bep\\s?\\d|manga|\\bnovel\\b|\\bbook\\b|youtube|\\bvideo\\b|\\bclips?\\b|\\bmusic\\b|\\bsong\\b|playlist|\\balbum\\b|\\bdrama\\b|\\bmovie\\b|\\bfilm\\b|\\bgame\\b|\\bswitch\\b|earphones|headphones|\\bshow\\b|\\bstream\\b",
        # of those, the ones that are watching an episode: her watchlist is
        # consulted and a real あらすじ fetched (music / games / manga are not)
        "watch_regex": "watch|episode|\\banime\\b|drama|movie|film|\\bep\\s?\\d",
        "max_per_day": 3,
        "min_gap_minutes": 120
    },
    "recap": {
        # grounded watching (sim/recap.py): a real Japanese あらすじ for the
        # episode she is on, fetched once and cached in the `recaps` table,
        # so the experience call reacts to what actually happened. Selenium,
        # a throwaway Chrome profile. No model call.
        "enabled": True,
        # no window (the fetch happens while she is mid-scene and a Chrome
        # opening itself is not part of that). Off to watch a fetch when a
        # site starts giving the wrong text; `/headless off` does it live.
        "headless": True,
        "query_template": "{title} アニメ 第{ep}話 あらすじ 感想",
        "series_suffix": "全話 あらすじ ネタバレ",
        # when HE names a series: a fuller Japanese premise/overview
        "overview_query": "{title} アニメ あらすじ 登場人物 どんな話",
        "seiyuu_query": "{name} 声優 プロフィール 出演",
        "work_query": "{title} ゲーム あらすじ 概要 登場人物",
        "search_engines": ["https://www.bing.com/search?q={q}&setlang=ja",
                            "https://html.duckduckgo.com/html/?q={q}&kl=jp-jp"],
        "candidates_max": 4,
        "blocked_hosts": ["youtube.com", "amazon.co", "netflix.com", "twitter.com", "x.com",
                          "instagram.com", "booklive.jp", "dmm.co", "abema.tv", "filmarks.com",
                          "justwatch.com", "ja.wikipedia.org", "anidb.app", "anidb.net", "anizukan.com",
                          "anilist.co", "livechart.me", "annict.com", "shikimori",
                          "anime-planet.com", "bangumi.tv", "allcinema.net", "syobocal.jp",
                          "cal.syoboi.jp", "kitsu.io", "notic.me"],
        "min_chars": 200,
        "max_chars": 2200,
        "page_timeout_seconds": 30,
        "poll_seconds": 1.3,
        "poll_max": 12,
        "page_min_html": 25000,
        "search_min_html": 15000,
        # HOW MANY CANDIDATES the judge gets, and how short a page has to be
        # before it is the anchor rather than a candidate. The official
        # あらすじ page is 200-250 characters, never wrong and never complete:
        # the right thing to check a summary against and the wrong thing to
        # summarise, so it is kept and marked rather than discarded.
        "candidates_target": 4,
        "anchor_max_chars": 300,
        # and below this a slice is the page's own heading and not even an
        # anchor -- a title bar with an advertising strip came to 172, and a
        # site that had not finished loading gave 37. The official blurb, which
        # is what an anchor is for, measures 200 to 250.
        "anchor_min_chars": 200,
        # An episode marker with another episode's marker this close behind it
        # is an index entry -- a nav strip, a season page's list of titles --
        # and not the heading of this episode's section. A page for one
        # episode of a 2010 show carries all thirteen titles at the top, and
        # slicing at the first marker gave thirteen characters.
        "index_entry_gap": 40,
        # What a page taken on the strength of its HEADING has to have before
        # it counts as an account of the episode: this many sentences, and
        # this much of a body. The heading is what recovers a 感想 post whose
        # body carries no number at all, and it is also what a shop's listing
        # page for the same episode gets exactly right -- the video shop's
        # page for エグザンプル ep6 is headed `第6話` and is 285 characters
        # of prices and service copy, where the four blog posts recovered this
        # way run 2,200 to 9,600. A listing has no sentences in it whatever
        # its length, and no page of prices is long. Either at 0 turns that
        # half of the test off.
        "slice_min_sentences": 3,
        "slice_min_chars": 600,
        # The page-source poll stops when the source has not grown for this
        # many polls. `page_min_html` was standing in for "it has finished
        # arriving", and a 9 KB official episode page can never reach it, so a
        # small good page cost the whole 15.6-second budget every time. A page
        # that has not STARTED arriving has also stopped growing, so the break
        # needs a few polls behind it and a page big enough to be a page.
        "poll_settle": 2,
        "poll_min": 4,
        "poll_min_html": 8000,
        # the keyless sources, fetched in parallel with each other and with
        # the browser
        "fetch_workers": 4,
        "http_timeout_seconds": 20,
        "list_episode_url": "https://myanimelist.net/anime/{id}/_/episode/{ep}",
        "list_episode_index_url": "https://myanimelist.net/anime/{id}/_/episode",
        "wikipedia_api": "https://en.wikipedia.org/w/api.php",
        "wikipedia_list_title": "List of {title} episodes",
        # where every fetched page, subtitle file, transcript, digest and
        # verdict is written, with a manifest per episode saying what each
        # file is and where it came from. Shared between characters on
        # purpose: it is a cache of public pages about television episodes,
        # keyed by show and episode, with nobody's life in it
        # (tools/isolation.py names it as the machine's).
        "archive_dir": "data/recaps",
        "archive_enabled": True,
        # THE EPISODE'S OWN SUBTITLE FILE, downloaded keyless from a fan
        # archive and its mirror, parsed to lines with timestamps and (on a
        # caption rip) speakers, and turned into an account of the scenes in
        # order by the `transcript_digest` role. That account is the anchor
        # the judge measures web candidates against, and the digest when no
        # web candidate survives. Never her line: twenty-four minutes is
        # 300-500 lines of speech with no stage directions.
        "subtitles_enabled": True,
        "subtitles_user_agent": "scail-recap/1.0",
        "subtitles_mirror_tree": "https://api.github.com/repos/Ajatt-Tools/kitsunekko-mirror/git/trees/main:subtitles",
        "subtitles_mirror_raw": "https://raw.githubusercontent.com/Ajatt-Tools/kitsunekko-mirror/main/subtitles",
        "subtitles_archive_index": "https://jimaku.cc/",
        "subtitles_archive_base": "https://jimaku.cc",
        # a file in a folder marked Japanese is not always a Japanese
        # transcript: one show's files are a Chinese group's listening script,
        # and one of those is dual-language with the Japanese layer 309 lines
        # of 723. The share of lines carrying Japanese script is measured on
        # the file rather than assumed from where it sat.
        "subtitles_min_ja_share": 0.6,
        "subtitles_min_lines": 40,
        "subtitles_try_files": 3,
        # one attempt per show and episode per day, hit or miss, so a show
        # with no file is not looked for on every tick
        "subtitles_retry_hours": 24,
        # HOW MUCH OF THE SUBTITLE FILE THE ACCOUNT ROLE SEES. It is the
        # model's window that bounds this and not a number chosen to be safe:
        # a 24-minute episode renders to 15,000-25,000 characters of
        # `[mm:ss] speaker: line` and a 24,000 ceiling was cutting the middle
        # out of an ordinary episode -- and the middle is where a running gag
        # is established. At 90,000 a feature-length file still fits.
        "transcript_prompt_chars": 90000,
        # and the account the transcript role writes, which is the anchor the
        # web candidates are held against. It was 1,600 characters, which is
        # about the length of a synopsis, so the anchor could not carry more
        # of the episode than the pages it was checking.
        "transcript_account_chars": 3000,
        # ---- THE EPISODE ACCOUNT (sim/episode_account.py) ----
        # Everything read about one episode -- every surviving digest, the
        # subtitle file's own account of the scenes, the official blurb --
        # merged by the `episode_account` role into ONE record: every scene in
        # order with how it comes out, the named parts, the running gags, the
        # lines worth remembering, what the episode points at, and what no
        # source settled. Written once for the MACHINE and read by every
        # character without fetching anything.
        #
        # It exists because the winner of the judge is one page. On
        # 2026-09-08 an episode of a shop comedy reached the third character
        # as 600 characters of one fan's post: the B-part's premise survived
        # and every individual joke in it did not, which is the difference
        # between having read a synopsis and having watched the episode.
        "account_enabled": True,
        # HOW MANY PAGES ARE READ FOR ONE, and it is deliberately more than
        # the judge needs. Four candidates settle which page to trust; a
        # background reference or a running gag is typically named by one
        # 感想 post out of six and by none of the official sources, so the
        # account's caller widens both the "keep" and the "try" caps.
        "account_candidates": 6,
        "account_tried_max": 8,
        # HOW MUCH OF EACH PAGE THE MERGE READS. `max_chars` (2,200) was
        # chosen for what is STORED as the winning synopsis. The account reads
        # the pages themselves rather than their digests -- a digest is 200 to
        # 500 characters made out of a 2,200-character post, and what it drops
        # first is the individual jokes, which is the whole point -- and a
        # 感想 post puts its best detail two thirds of the way down.
        "account_page_chars": 8000,
        # the ceiling on the stored account. Not a budget -- the account is
        # never cut to fit a prompt, which is the thing it replaces -- but a
        # bound on one row.
        "account_max_chars": 4000,
        # WHAT COUNTS AS COMPLETE, and it is measured on what went in rather
        # than on how it reads. `watched` needs the length, the scenes, and
        # either the episode's own dialogue behind it or two independent
        # readers agreeing: one blogger's misreading can produce a long
        # confident account, and that is the case this word exists to name.
        # A complete account is never rebuilt and never re-fetched.
        "account_min_chars": 900,
        "account_min_scenes": 3,
        # and the floor under which it is `thin` rather than `read-up`
        "account_thin_chars": 400,
        # How many readings-up ONE EPISODE gets before an account that is
        # still not at watched level is left alone -- counted for the machine,
        # on the account itself, not per character. Each of the three
        # processes allowed herself `sensors.retrievals_max_retries` attempts
        # at the same episode, so one episode cost up to nine readings and the
        # last of them was no better than the third. 0 for no limit.
        "account_max_tries": 3,
        # THE EXTERNAL OBSERVER'S VIEW: one Markdown page per episode with the
        # account, the scenes, the sources and their URLs, and an index over
        # all of them. The MACHINE's, like the archive and the per-play
        # dossiers beside it (`tools/isolation.py`): an episode of a
        # television programme is the same episode whoever watched it.
        "episodes_report_dir": "reports/episodes",
        # WHERE AN EPISODE'S OWN DIALOGUE CAME FROM, readably. The answers were
        # only in SQL -- one row per (show, episode) in each save's
        # `transcripts` table -- and the reasons were scattered across a
        # thousand session logs, so there was nowhere to look. Append-only, one
        # line per attempt that resolved, the machine's like the episode pages
        # (`machine/episode_reports.py`, `tools/isolation.py`).
        "transcripts_report": "reports/transcripts.md",
        # WHERE THE EPISODE'S OWN WORDS COME FROM, in the order they are tried.
        # The fetch used to be the two internet archives and nothing else, and
        # it missed three of five episodes in a fortnight -- not on a bad
        # match, but because neither archive carries those works at all under
        # any name. So the path now starts on his own disk and ends in a
        # transcription, and cannot come away with nothing.
        #
        # 1. THE FILE ALREADY BESIDE HIS VIDEO. Free, instant, and it was
        # being ignored: a Japanese subtitle of 339 lines sits next to an
        # episode he played, and the fetcher was asking the internet for it.
        # The stem is the video's; the suffixes below are the forms a
        # release names a language track with.
        "local_subtitles_enabled": True,
        "local_subtitle_suffixes": ["", ".ja", ".jp", ".jpn", ".jpn-ja", ".japanese",
                                    ".ja-jp", ".jaJP", ".Japanese"],
        # 2. THE ARCHIVE MIRROR, ON THIS MACHINE. The repository is 3.71 GB
        # with its history, so it is cloned shallow, one branch, sparse to
        # the three folders the lookup walks. Reading it off the disk needs
        # no network at all, and the API tree fetch it replaces is
        # rate-limited and was the first network hop of every miss. The API
        # stays as the fallback for a machine that has not cloned it.
        # The directory is the MACHINE's, like the episode archive beside it:
        # it is an archive of television, with nobody's life in it, and one
        # copy serves both characters (`tools/isolation.py`).
        "subtitles_local_mirror": "data/subtitles_mirror/kitsunekko",
        "subtitles_local_refresh_hours": 24,
        # 4. A release index that answers about torrents rather than about
        # subtitles. Its JSON feed works and every field is about the
        # torrent; a release page carries no extracted subtitle attachment at
        # all, so getting a subtitle from it means fetching the release,
        # which this project does not do. Wired and off, so the decision is
        # in the config rather than only in a report.
        "animetosho_enabled": False,
        "animetosho_json": "https://feed.animetosho.org/json",
        # 5. A subtitle service that needs an account. Off while the key is
        # blank, which it is.
        "opensubtitles_enabled": False,
        "opensubtitles_api": "https://api.opensubtitles.com/api/v1",
        "opensubtitles_key": "",
        # 6. AND WHEN NOTHING CAN BE FETCHED, THE EPISODE IS TRANSCRIBED from
        # the file he played. His own install does the work
        # (`Faster-Whisper-XXL Pro`), driven with the settings from his own
        # `processor.bat` so that his batch file stays the reference and this
        # follows it. The arguments are his, in his order; the exe takes the
        # video and writes the .srt itself.
        "whisper_enabled": True,
        "whisper_exe": "",
        "whisper_args": ("--language Japanese --task transcribe --model large "
                         "--output_format srt --device cuda:0 --beep_off --check_files "
                         "--beam_size 15 --patience 2.0 --compute_type float16 "
                         "--vad_method pyannote_v3 --standard_asia --verbose=true"),
        # A transcription is minutes of the GPU, and the GPU is shared with
        # the reaction-image tool. So: never on the reply path or the poll,
        # a few a day, nothing feature-length, and only once he has clearly
        # settled into the episode rather than sampled it -- ten minutes in
        # is that point, and it is a different question from whether the
        # episode counts as watched (`min_minutes_in`, three minutes), which
        # the fetching steps above are gated on and this one is not.
        "whisper_max_per_day": 4,
        "whisper_max_minutes": 40,
        # HOW LONG HE MUST HAVE SAT THROUGH IT, and 0 means the SAME number
        # that decided the play was a watch at all
        # (`watching.min_watched_minutes`) rather than a second one beside it.
        # It used to be its own key at the identical value, and the two were
        # read at different instants off different pollings of the player: the
        # read-up fired on a reading of 600 seconds and the transcriber was
        # asked a second later with 599. It was refused by rounding every time
        # it was ever asked -- three logged refusals read "he is 10 min into it
        # and the floor is 10" -- and in 1,067 session logs no character
        # process has ever run it. A number here overrides the gate.
        "whisper_min_watched_minutes": 0,
        "whisper_timeout_seconds": 3600,
        # for the episode's length, beside the ffmpeg `tts.ffmpeg` names
        "ffprobe": "ffprobe",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    },
    "household": {
        # Her flat and her week as things with a STATE, moved by the director
        # under a daily budget and met by her as facts (sim/household.py).
        # For a character with no world of her own: the director had nothing
        # to move, wrote the same scene for hours, and then wrote her thoughts
        # instead. OFF by default; the seed file lists the objects, states and
        # moves, every one from her home file, so a move is always something
        # she said happens to her.
        "enabled": False,
        "file": "",
        # moves the director may make in one day; most ticks move nothing
        "incidents_per_day": 2,
        # how many objects the one line in her situation carries
        "situation_max_objects": 8
    },
    "watching": {
        # what HE watches, noticed as it happens and read up on
        # (sim/watching_him.py). Distinct from `watchlist`, which is her own
        # shows: this is his, and the whole point is that the Japanese
        # synopsis fetcher above was reachable only from him naming a show in
        # chat, so an episode he actually played taught her nothing.
        #
        # OFF by default and on for both characters as they stand -- but they
        # LEARN IT AT DIFFERENT MOMENTS, and the moment is the program's
        # rather than this flag's. A character who lives on his machine is
        # told as the module lands it, dated to his play (`resident/app.py`
        # `every_pass` -> `WatchingHim.note_seen(at_play=True)`); a character
        # who learns what he is doing in snapshots she has to go and fetch is
        # told when she next fetches one, dated to that (`tomoe/app.py`
        # `after_phone_look` -> the same call without the flag), and her
        # freshness and settle windows run from then. Turning it on is a
        # decision about how a character finds things out, which is why it is
        # not a default.
        "enabled": False,
        # the player's own history, one `epoch|path` line per file opened
        "player_history_path": "%APPDATA%/mpv/mpv_history.log",
        "player_history_tail": 400,   # lines read per poll, newest last
        # where he is in the file open in front of him, written from inside
        # the player by tools/mpv/scail_logger.lua. How long since the file
        # opened cannot answer this, because he pauses -- so mpv reports its
        # own position and pause state, refreshed every 10s and at once when
        # he pauses. It also carries the unpaused seconds so far and the epoch
        # the file opened at, so the fetch gate below can be answered while he
        # is still in the file. A state file older than the staleness below is
        # nobody watching, which covers the player being killed rather than
        # closed.
        "now_playing_path": "%APPDATA%/mpv/mpv_now.json",
        "now_stale_seconds": 60,
        "remember_episodes": 200,     # so a rewatch is not announced twice
        # her name as his cast mirror spells it, and blank for a character who
        # has never been in anything -- which is what decides whether "you are
        # in this one" can ever appear
        "her_seiyuu_name": "",
        # whether contact with her own work releases the part of her record
        # the era gate holds (sim/lore.py). The mechanism is hers alone; a
        # character with no held claims is unaffected either way.
        "open_her_record": True,
        # the fallback cut of the raw synopsis, used only when the digest
        # below could not be made (no model client, or the role failed)
        "summary_max_chars": 1400,
        # the digest: the whole synopsis condensed by `watching_digest` into
        # the parts a viewer would remember, cut here as a ceiling. She gets
        # this line on EVERY message while the episode is fresh, and the line
        # is pinned in her situation block so the attention budget cannot
        # drop it -- it did, at 1,400 characters and the phone section's
        # default weight, the first time an episode of his came up in chat.
        "digest_max_chars": 600,
        # AND THE ACCOUNT, WHICH IS NOT CUT. The digest above is still what
        # the opener and the impulse read -- a short line about the episode is
        # the right thing there. What goes into her situation block for the
        # episode he has just watched is the whole account
        # (`recap.account_enabled`, `sim/episode_account.py`): every scene in
        # order, the parts, the gags, the lines, what the episode points at.
        # It costs 1,500 to 4,000 characters against a situation block of
        # 12,000 to 20,000, it sits after the thread where a byte that changes
        # costs only itself, and the alternative is a character who has been
        # told what an episode was about talking to somebody who watched it.
        "account_in_prompt": True,
        # how many of the episodes he watched TODAY get their whole account
        # rather than one clause in the arc. The newest is always one of them.
        "account_recent": 2,
        # and the ceiling over those extra accounts together, so a run of six
        # cannot put six accounts in one prompt. The newest is never dropped.
        "account_recent_max_chars": 6000,
        # THE FLOOR UNDER WHICH AN OPEN IS NOT A PLAY. A file opened for five
        # seconds was fetched, digested and kept as "he watched"; under this many minutes it is a mis-click and is logged
        # as an open and closed, not as a skim. What decides whether a play
        # is read up on is `min_watched_minutes` below, which is higher and
        # measures a different thing. 0 = the old behaviour, count on open.
        "min_minutes_in": 3.0,
        # THE FETCH GATE, and the number that separates a watch from a skim.
        # Nothing is fetched, digested, marked seen or told to her until he
        # has actually watched this many minutes of the file: UNPAUSED
        # SECONDS as the player counts them (`watched=` in the plays log and
        # in the state file), never the position and never wall clock since
        # the file opened. Seeking to the last minute and closing the file
        # leaves the same position as sitting through the whole thing, and a
        # file left paused for an hour leaves the same elapsed clock as an
        # hour watched. A play that ends under this is a SKIM: it goes in his
        # own timeline, it is not marked seen, and no model call is spent on
        # it. `min_minutes_in` above is the lower floor, under which an open
        # is not a play at all.
        "min_watched_minutes": 10.0,
        # Every finished play, written by the same script as the history line:
        # when the file opened, when it ended, how long it is, where he
        # stopped, how many unpaused seconds he sat through, and what ended
        # it. The open's epoch is shared with the history line, which is what
        # joins the two. Read by machine/plays.py.
        "player_plays_path": "%APPDATA%/mpv/mpv_plays.log",
        # HIS OWN READABLE RECORD of what the player has finished, one row per
        # play, newest at the bottom, in plain text he can open. It is the
        # machine's rather than a character's: whichever process gets there
        # first writes the row, keyed on the open's epoch so three processes
        # over one player cannot write a play twice (machine/plays.py).
        "plays_timeline_path": "reports/plays.md",
        "rewatch_after_hours": 24.0,   # an episode he opens again after this long counts again, and she is told it is a rewatch
        # How long a play whose work was resolved FROM THE FILENAME ALONE is
        # held for his list to name the id. The two routes are not equal: the
        # player is the moment he starts and carries a filename to guess from,
        # his list is minutes later and carries the show's own id. Once the id arrived long after the page had
        # been fetched, for a different work, and nobody compared them. Inside
        # this window a title-only resolution waits; when the id arrives and
        # differs, the id wins and the log names both. 0 turns the wait off.
        "confirm_minutes": 8.0,
        "poll_minutes": 4,
        # How long after the last episode she treats him as having STOPPED.
        # Nothing reaches the impulse before this, so an evening of six
        # episodes is one reason to speak at the end rather than six
        # interruptions through it.
        "settle_minutes": 25,
        # what it adds to the impulse score. It is added, never a shortcut
        # round the gate, so the daily cap, the cooldown, going cold on him
        # and "he has not answered the last ones" all still refuse.
        "impulse_bonus_hers": 14.0,       # a show she is in
        "impulse_bonus_finished": 7.0,    # he has just finished a series
        "impulse_bonus_any": 3.0,
        # how long the episode stays the thing in the room, counted from when
        # it reached HER. He watches and then says nothing for an hour, so
        # handing the summary to whichever turn came first and dropping it
        # would defeat the point.
        "fresh_hours": 6.0,
        # and how long it stays findable BEFORE that, for a character who only
        # comes across it when she goes and fetches what he has been doing.
        # She can be asleep or out for the whole evening he watched in; a day
        # is what "lately" means here, and the line says how long ago he
        # watched it. Past this she never learns of that episode as news --
        # the show is still hers by name (`sim/known.py`) if he mentions it.
        # Unused by a character who is told as it lands.
        "discover_hours": 24.0,
        # WHAT SHE IS SHOWN WHEN SHE LOOKS, when he has played more than one.
        # Her line used to be the newest episode and nothing else, so an
        # evening of six and a day of three works both came out as one
        # episode. The block is now one line per WORK, newest play first.
        #
        # Three works, because the situation block is 3k to 5k tokens of an
        # 80k to 110k prompt and the gate drops nothing for room
        # (docs/context.md §5): a work's line costs 300 to 600 characters
        # against a block of 12k to 20k. Nothing measured has reached three, so it bounds the
        # worst case rather than cutting anything real. Oldest dropped first.
        "recent_works": 3,
        # and the ceiling over the whole grouped block: two episode digests'
        # worth (`digest_max_chars` is 600), which is the order the single
        # pinned episode already costs, so the block never grows by more than
        # one line's worth. The newest work is never dropped for it.
        "recent_max_chars": 1200,
        # How many episodes the record of what he has watched lately keeps.
        # It is read by the grouped block, so it has to outlast a binge: two
        # of the largest batch his own list has ever logged at one minute.
        "recent_keep": 24,
        # A BATCH IS NOT LOST ANY MORE. His list logs a session as several
        # rows at one timestamp (several episodes of one work at one timestamp); the poll took the newest and moved the cursor past the rest,
        # so five plays vanished. What the poll cannot take now waits in a
        # queue and is read up one per poll. These two bound what that can
        # cost: at most this many episodes are read up in a day, and past it
        # the rest of the batch is recorded as watched with no synopsis, so
        # the range she is told about is still right. One fetch is three to
        # five pages, a digest call each and one judge on the cheap model.
        "max_fetches_per_day": 8,
        "queue_max": 20
    },

    "dossier": {
        # One Markdown file per play of an episode, joining what is already on
        # disk about it: the play itself, the episode in three scripts with its
        # judged digest, his history with the show, the cast, and what the
        # mirror does not hold (machine/dossier.py, docs/dossiers.md). Nothing
        # in it is fetched for a character and nothing is a model call.
        #
        # THE MACHINE'S, NOT A CHARACTER'S, and that is what this section is
        # for. Three character processes tail the same media player, so a
        # dossier built inside a character's loop would be built three times
        # over three saves. It is built by the MyAnimeList mirror daemon
        # (`tools/mal_history.py daemon`), which is the one process per
        # machine, and an already-built play is skipped on its open time. The
        # daemon has no character and builds no Config, so it reads these
        # values out of the config FILE, first one on disk -- the same way it
        # already reads the subtitle mirror's path.
        "enabled": True,
        "dir": "reports/dossiers",          # one file per play, and the rolling one
        "db_path": "data/dossiers.db",      # what has been built, and the two cached page reads
        "last_n": 10,                       # how many plays `last-ten.md` carries
        # How many are built in one pass of the daemon, oldest first. The very
        # first pass meets a backlog of everything the player has ever opened,
        # and a play may read up to three actors' pages; the daemon comes back
        # every five minutes, so an evening is caught up within the hour and
        # nothing is read in a burst.
        "per_cycle_cap": 3,
        # Under this many unpaused minutes it is a skim rather than a play: one
        # line in the rolling file and no dossier. The player's own end-of-play
        # record gives the number (`watching.player_plays_path`, read through
        # machine/plays.py); where that file does not exist yet the gap to the
        # next file opened is the estimate, and every line quoting a duration
        # says which of the two it came from. Its own key rather than the
        # watcher's `watching.min_watched_minutes` because the two answer
        # different questions -- that one decides whether a character is told
        # about a play at all, this one whether the machine writes a file about
        # it -- and both stand at ten minutes today.
        "min_watched_minutes": 10.0,
        # the window of "what you played around it", in hours either side
        "hours_before": 6.0,
        "hours_after": 6.0,
        # Every credited actor is a row in the cast table; this many of them
        # get a section of their own under it, main roles first. A supporting
        # actor with forty of his shows behind her turned one dossier into
        # thirty-eight kilobytes, most of it a list nobody was going to read.
        "cast_detail_cap": 9,
        # ...and how many of an actor's other shows on his list that section
        # names, best-scored first.
        "actor_list_cap": 12,
        # How many credited actors' pages are read per play, main roles first.
        # The mirror holds a filmography for thirteen people against 11,851
        # cast rows, so for everybody else "what else has she done" is his own
        # list and nothing beyond it. Read from the list site's own origin,
        # never the community wrapper in front of it, and cached in the
        # module's own store rather than in the mirror the daemon holds open.
        "actor_fetch_cap": 3,
        # ...and how many works in the franchise with no premiere date on disk
        # are looked up. A plan-to-watch entry carries no dates on a list at
        # all, so a sequel reads as a blank row until one call fills it.
        "premiere_fetch_cap": 2,
        "fetch_delay_seconds": 1.5,      # between two page reads, so the source is not hammered
        "fetch_ttl_days": 120,           # a cached page older than this is read again
        "fetch_timeout_seconds": 25
    },

    "role_check": {
        # Whether a work named anywhere near her is checked against her own
        # filmography before she talks about it (`sim/works.py`,
        # `her_part_verdict`). Once the second character told him she
        # played a part in a work she has never been in; the complete cast of
        # the episode he had just watched, with her absent from it, was in two
        # tables on his own machine long before she said it, and
        # nothing asked. The verdict is three-valued -- yes, no, or nobody
        # checked -- and nobody-checked says nothing at all.
        #
        # Free: two indexed sqlite reads against the machine's mirror, no
        # model call and no fetch. Assigned in `Config.REQUIRES` to the
        # derived property `voice_actress`, which is simply
        # `character.mal_person_id` being set, so this flag is only ever the
        # second of two switches.
        "enabled": True,
        # How stale her mirrored filmography may be before a flat "no" is
        # downgraded to nobody-checked. Her career gains a few credits a
        # season, so a month is generous; a positive is unaffected, because a
        # row that exists is a part she played whenever it was mirrored.
        "person_refresh_days": 30,
        # Whether the worker that reads up on an episode he played also
        # mirrors that work's cast when nobody has -- the second witness a
        # flat "no" needs. It runs in `sim/watching_him.py`'s background
        # thread, which already fetches pages, and NEVER in a reply path: one
        # MyAnimeList page, measured at 0.28 s, no money. Off, and a work
        # whose cast nobody has mirrored simply stays nobody-checked.
        "fetch_on_miss": True,
        # Whether the denial also names the part whose name resembles hers and
        # who really plays it. On: the work she claimed has a lead who shares
        # her given name, which is most of why the claim happened, and a bare
        # "you are not in it" leaves her to wonder who is and invent an
        # answer. It is the ONLY name out of a cast list that is ever put in
        # front of her.
        "say_who_instead": True,
        # How many verdicts the continuity editor is handed as checkable
        # facts. It gets one line per work named in her draft or her
        # situation, English, machinery to itself.
        "editor_facts_max": 6,
        # Whether a work named in HER OWN DRAFT (rather than only in what
        # reached her) opens the editor's gate. The gate skipped the call on
        # the draft that made the false claim, because it had no number, no
        # run shared with a recent message and no word from a fact about him.
        "titles_from_draft": True
    },

    "which_one": {
        # The one model role in the resolver (`sim/resolver.py`): which of
        # several candidate works he means, when every deterministic filter
        # has run and more than one is left. Code decides WHEN it is asked and
        # a model decides WHAT, and its answer is an id out of a table code
        # built -- never a word she reads.
        #
        # It runs in the worker that reads up on an episode he played and in
        # the lookup's own thread, NEVER in a reply path. A failure, a
        # timeout, an unparseable answer, a confidence under the floor or an
        # id code had already ruled impossible all leave code's own ranking
        # standing, so this can neither stop her nor delay her.
        #
        # Measured cost: about $0.0002 a call on the cheap model, three to six
        # calls a day across both characters -- under a cent a week. It is not
        # asked when his list has already named the id, and never twice for
        # the same question: the answer goes in the machine's shared store
        # (pool `resolved`) under a key that names the question and never the
        # character, so both characters read the one answer.
        "enabled": True,
        # Under this the answer is discarded whole and the ranking stands. A
        # role that never says "unsure" is not being asked a real question and
        # one that always says it is being asked the wrong one, so the floor
        # is deliberately not high.
        "min_confidence": 0.5,
        # The cap on the wait. Past it code's answer stands; the call finishes
        # on its own and the paid answer still reaches the store, because the
        # store is written inside the call rather than held by the waiter.
        "timeout_seconds": 30,
        # rows in the table it is handed, each with the first 300 characters
        # of its own text
        "max_candidates": 6
    },

    "watchlist": {
        # her own shows, with a cursor (sim/watchlist.py). The list here is
        # planted into kv `watchlist` once, the first time a save is built,
        # and never read again; edit live with /watch. `ja` is the search
        # title. EMPTY BY DEFAULT: two shows were named here and every
        # character built since started watching those two, so three of them
        # were recapping and transcribing the same pair beside the one show
        # each had chosen for herself. A character with no planted list starts
        # with none and `Watchlist.pick_own` gives her one at the next compile.
        "seed": [],
        # a show of her own (role watch_pick, at the compile): from her sheet,
        # the accounts she keeps liking and what is going round, never his
        # list; when fewer than keep_min are unfinished, or every pick_every_days
        "pick_enabled": True,
        "keep_min": 2,
        "max_open": 3,
        "pick_every_days": 7,
        "pick_tries": 4                 # picks refused for being on his list before giving up
    },

    "morning": {
        # A morning thought is only honest in the morning. Without this, a
        # restart or a restore later in the day would produce one at four in
        # the afternoon; with it, the day simply has none, which is the
        # truthful outcome.
        "latest_hm": "13:00",
        # at the wake tick: what today is to her, first person (sim/outlook.py)
        "enabled": True
    },

    "replay": {
        # a hole in the record re-lived on her clock (scail.py --replay,
        # PROJECT 8.2). The estimate printed before anything is touched:
        # ticks = window / director.tick_minutes, cost = ticks x usd_per_tick
        # (measured 2026-08-31 at Together: a tick is a director call ~12.5k
        # in, an anticipation ~5k, a state read ~3k, ~600 out: ~$0.003).
        # Past cost_warn_usd the replay refuses without --yes; --gap writes a
        # temporal-gap event for the window instead (his rule: an extreme
        # catch-up is reported with its cost and may be skipped as a gap).
        "speed": 30,
        "usd_per_tick": 0.003,
        "cost_warn_usd": 0.5
    },

    "downtime": {
        # the stretch during which nobody was running her (sim/downtime.py).
        # A stop is Stop-Process -Force, so the process being stopped writes
        # nothing on its way out: the stop tool writes kv `stopped` on each
        # save once the process is down, and the next boot of that character
        # reads it, closes the row in kv `stops` and writes the stretch as a
        # temporal gap. Without it the director sees an empty stretch as
        # work outstanding and asks a model to write hours nobody lived.
        "enabled": True,
        # how long a stop has to have lasted before it is worth putting on
        # her record. Under this she simply comes back; a restart for a code
        # fix takes a minute or two and is nothing that happened to her.
        "gap_after_minutes": 20,
        # the provider answering that the account is empty stops the whole
        # machine, because no retry fixes it and every character is about to
        # get the same answer. Only in a live run on Windows, and never with
        # SCAIL_NO_SHUTDOWN in the environment.
        "shutdown_on_no_credit": True,
        # what is launched to do it, relative to the project root
        "shutdown_command": "stopall.cmd"
    },

    "anticipation": {
        # before what she can see coming (sim/outlook.py): his usual first
        # activity (read off the app's day shapes) less than before_minutes
        # away; a calendar event today (from event_morning_from_minutes
        # after midnight) or tomorrow (from event_eve_from_minutes). One
        # call; a line in her situation for hours_in_prompt; small deltas.
        "enabled": True,
        "before_minutes": 60,
        "event_morning_from_minutes": 540,
        "event_eve_from_minutes": 1200,
        "hours_in_prompt": 3,
        "gauges_it_may_move": ["mood", "anxiety", "validation_craving", "curiosity", "boredom", "loneliness"]
    },

    "reflect": {
        # her private mind about him (sim/reflect.py): after the app showed
        # her something, or when curiosity / being read-and-left has built
        # up, alone with a quiet minute, one call turns it over. Private
        # (kv reflections, in_prompt of them in her system prompt as things
        # she thought), moves the listed gauges, leaves the director an
        # inner line. Never sent.
        "enabled": True,
        "alone_only": True,
        "min_gap_minutes": 75,
        "max_per_day": 5,
        "curiosity_from": 70,
        "jealousy_from": 60,
        "guilt_from": 55,
        "ignored_minutes": 60,
        "keep": 60,
        # How many of them ride in her system prompt. Two was less than half a
        # morning: she writes five to eight reflections a day, so a thought
        # lived in her prompt for about three hours and anything that fired in
        # the afternoon was gone before the evening she would have said it in.
        # A comparison against one of her friends is written into this same
        # list (tomoe/compare.py) and fires about four times a fortnight, so at
        # two it could reach her words to him only by luck, and on the record
        # it never did. Six is one day of them at the observed rate, which is
        # the honest window for "something she is carrying today". Measured on
        # the live save: the newest six render to 1,625 characters against 502
        # for two, so **+1,123 characters on the system prompt**, +3.7% of the
        # 30,585-character him arm. It does not add a cache break -- this
        # section already moves several times a day -- it makes each existing
        # one that much longer.
        "in_prompt": 6,
        # computed gauges are not in here: state.apply refuses them anyway,
        # and a list naming what it cannot move is the "declared and unread"
        # fault in miniature
        "gauges_it_may_move": ["curiosity", "anxiety", "validation_craving", "loneliness", "unsaid", "jealousy", "guilt"],
        # about anyone else: a person she talked with today, chosen by
        # pressure (tension, standing, the length of the exchange), read
        # from the record of what was said; reaches her prompt, the
        # director, and cast_reply for that person
        "cast_enabled": True,
        "cast_min_gap_minutes": 120,
        "cast_max_per_day": 3,
        "cast_score_from": 1.4,
        "cast_gauges_it_may_move": ["anxiety", "loneliness", "unsaid", "anger", "sadness", "awkwardness", "validation_craving", "curiosity"]
    },

    "affection": {
        # How warm she is toward him. Two halves, and the split is the point.
        #
        # The structural half (state.affection_from) is attachment, closeness,
        # relief, tension and resentment: it is what a week of being ignored
        # does, and it needs no messages at all to work.
        #
        # This half is what his messages actually left her feeling. It is read
        # on a cycle rather than per message, because a message is not scored
        # as it arrives -- she is answering it then. One call reads the
        # exchange since the last cycle and gives each of HIS messages the
        # level of warmth it leaves her at, in a band the code sets. The
        # levels fade by age and blend into the target, taking at most
        # max_weight of it, so the structural causes always have a say and a
        # silent fortnight still cools her with nothing to read.
        #
        # This replaces arithmetic that could not tell "busy, talk later" from
        # "busy, sorry, i'll message you tonight".
        "enabled": True,
        "review_enabled": True,
        # When: once a day, as she goes under, over everything since the
        # last read. The day is the unit a person settles up in, and an
        # evening can only be judged against the morning it followed if
        # both are in front of the same call.
        # min_messages counts the exchange, not his half -- his half of a
        # day is a modest number of messages, so counting only his would put the
        # floor at the whole day. A day under it is not read and rolls into
        # the next night. min_his stops a night of her talking to herself
        # being read as him.
        "min_messages": 20,
        "min_his": 3,
        "window_messages": 250,
        # how much of the exchange before the new messages goes in for context
        "context_seconds": 3600,
        # the band. One message is a message, not a verdict on the relationship
        "neutral": 45,
        "level_min": 5.0,
        "level_max": 95.0,
        # not a cap on how much of a conversation gets read -- context is
        # the only bound that matters. This is a backstop against a model
        # that returns nonsense, nothing more.
        "max_per_cycle": 200,
        # how a message stops mattering: faded, never forgotten. 20 hours
        # let one bad night own the figure by morning (53 -> 26 on 08-26);
        # a person's warmth is the last few days of him, not the last one
        "half_life_hours": 48.0,
        # fresh-message-equivalents at which the levels own their full share
        "full_weight_at": 4.0,
        "max_weight": 0.5,
        "keep_hours": 96,
        "max_kept": 200,
        # Bench switch (tk-z1q affpath): read his fresh messages shortly after
        # she has answered them, instead of only once at night. Off: the read
        # is the nightly one and nothing below runs. On: after her reply
        # (scail.py, the reply turn) the same read runs when the minimums
        # below hold, then affection takes one event-sized step toward the
        # target the new rows give it.
        "on_message": False,
        # the exchange since the last read, her lines counted (his one message
        # and her answer to it make 2), and how many of them his
        "on_message_min_messages": 2,
        "on_message_min_his": 1,
        # at most one read per this many minutes (counted from the last
        # attempt, so a call that comes back unreadable is not retried on the
        # next line). A burst of lines inside the window is read together by
        # the next read, which picks up everything since the last one.
        "on_message_cooldown_minutes": 4,
        # a cost bound on a long chatty day: reads per local date
        "on_message_max_per_day": 24,
        # how far affection steps toward the new target after a read, in
        # hours of affection_from.inertia_per_hour (6/h): 0.5 = 3 points,
        # the same as state.affection_from.on_event_hours
        "on_message_step_hours": 0.5
    },

    "stress": {
        # Susceptibility is DERIVED from data/self_beliefs.json -- how much of
        # her identity is load-bearing and how concentrated it is -- so a
        # different character is differently fragile with no code change. These
        # are the shape of that derivation, not her values.
        "enabled": True,
        "susceptibility_base": 1.0,
        "per_invested": 0.35,
        "per_concentration": 0.60,
        "per_anxiety_baseline": 0.25,
        "susceptibility_min": 0.55,
        "susceptibility_max": 1.60,

        # what counts as load, and how much. Every term is something the
        # simulation already tracks; stress invents no new bookkeeping.
        "load_weights": {
            "unfinished": 0.16, "rupture": 0.20, "unspeakable": 0.16, "unsaid": 0.12,
            "body": 0.14, "belonging": 0.10, "him": 0.12, "ahead": 0.08, "money": 0.05
        },
        "cost_full": 60.0,
        "charge_full": 160.0,
        "silence_full": 36.0,
        "broke_below": 800,
        "bad_night": 0.35,

        "floor": 6.0,
        "scale": 70.0,

        # the asymmetry, which is the whole mechanism: a bad fortnight is still
        # on her during the quiet Sunday at the end of it
        "rise_per_hour": 9.0,
        "fall_per_hour": 2.2,
        "recovery_base": 0.5,
        "recovery_alone": 0.35,
        "recovery_comfortable": 0.2,
        "recovery_slept": 0.7,
        # exhaustion forces rest; without this the compounding has no way down
        "exhaustion_from": 70.0,
        "recovery_per_stress": 0.9,

        "relief": {
            "slept_well": 14.0, "bath": 6.0, "diary": 5.0, "post": 3.0, "cried": 8.0, "gave_up": 9.0,
            "goal_got": 9.0, "rupture_mended": 16.0, "warm_exchange": 5.0,
            "held_by_the_group": 7.0
        },
        # One guard for all eight, rather than eight guards. Every site that
        # raises a release is polled rather than edge-triggered -- a bath is a
        # scene setting that lasts a block, a warm exchange is a mood that
        # lasts an hour -- so without a cooldown the same bath relieves her on
        # every director tick.
        "relief_gap_default": 90,
        "relief_gap_minutes": {"slept_well": 600, "held_by_the_group": 600, "bath": 300},
        # how far above her own baseline belonging has to sit before an evening
        # counts as the group having actually held her
        "held_from": 12.0,

        # what high stress does to the rest of her, capped so the loop cannot
        # run away: three of these feed each other
        "compounds_from": 45.0,
        "compound_cap": 1.9,
        "compounds": {
            "spiral": 0.7, "body_noise": 0.6, "delay": 0.45,
            "sleep_cost": 0.8, "shame": 0.5, "withdraw": 0.6
        }
    },

    "hazards": {
        # The ground moving, and the sky. She lives in Nerima and none of this
        # existed: on 2026-08-23 at 02:00 a M5.9 in southern Ibaraki put the 23
        # wards at 5-weak and she slept through it with the system unaware.
        "enabled": True,
        # LATENCY. Measured off JMA's own publication filenames: ~90s to the
        # first report, ~4 minutes to per-ward shindo. That is the floor and
        # every relay inherits it, so the seismic feed is a WEBSOCKET rather
        # than a poll -- adding a poll interval to a thing she physically felt
        # is absurd. EEW (緊急地震速報) is the only sub-10-second signal there
        # is, and it is the honest one: her phone screaming IS the event.
        "websocket": True,
        # Which observation points are hers, in her own config and EMPTY here:
        # this was one ward in one city, so every character's file carries
        # it whether she has ever been there or not, and the next
        # character in a world would have inherited it in silence.
        # A character with none has nothing for this section to read
        # and it switches itself off at her boot (`Config.NEIGHBOURHOOD`).
        "her_wards": [],
        "her_area_names": [],
        # felt here, at her own ward
        "felt_from": 20,
        # and big enough elsewhere to be on every channel
        "news_from": 50,
        "backfill_limit": 100,
        # how recent a quake still counts as something happening TO her. Older
        # than this and it is a thing she remembers, not a thing she is in --
        # at 36 the first live start delivered a 28-hour-old 5-weak as a fresh
        # event and woke her for it.
        "backfill_hours": 6,
        # and nothing older than this may wake her, whatever its salience
        "fresh_hours": 2,
        "keep": 400,
        # the sky, which is known about for days and is polled
        "weather": True,
        # Her prefecture, as JMA's own area code. It is the code in the
        # warning bulletin's filename (`..._VPWW53_130000.xml`) in the
        # developer feed, which is what says which of the 47 bulletins is
        # hers; her ward comes out of the bulletin body, against `her_wards`.
        "jma_area": "130000",
        "weather_poll_minutes": 20,
        # The feed hands back the newest bulletin there is, and after a hole in
        # the process that can be days old. It is still the right answer to "is
        # a warning up" and it is not news.
        "warning_max_age_hours": 12,
        # The lowest rung that is a thing she is HAVING rather than a line in
        # the record: 1 注意報, 2 警報, 3 特別警報. Every live one at any rung is
        # kept and shown by `/hazards`; this is what reaches her day and her
        # brief. A 注意報 is out over some part of Tokyo most days of the year,
        # so 1 would put "there is a weather warning up" in front of her about
        # two hundred times a year and teach her to stop hearing it.
        "warning_from": 2,
        # what the country has been dealing with: standing knowledge, not her
        # day. The M7.1 in Kumamoto on 2026-07-28 was 震度7 and she would know
        # about it for months; she was three hundred miles away.
        "national": True,
        "national_poll_hours": 6,
        "national_shindo_from": 5,
        # And the sky, which had none of this. The lowest rank of storm this
        # keeps, out of JMA's own bulletins (`_national_weather`):
        #   8  an emergency warning (特別警報) over a prefecture, and nothing else
        #   7  and a named river at its top flood level, and a cloudburst over
        #      one of the big cities -- 100mm in an hour over Nagoya on
        #      2026-09-08 stopped the subway and shut every school in the city
        #   5  and a cloudburst anywhere at all
        # Above 8 switches the source off and skips the fetch. An ordinary 警報
        # is on none of these rungs: there are thousands a year, and announcing
        # them is how a system teaches her to ignore the one that matters.
        "national_weather_rank_from": 5,
        "national_memory_days": 45,
        "national_keep": 40,
        # Five was the whole of this list while it was earthquakes. With the
        # storms in it, five lines is one bad week of weather and the
        # earthquakes fall off the bottom.
        "national_in_prompt": 8,
        # salience that gets a sleeping girl out of bed. 5 is a 5-weak
        # where she is, or a tsunami warning, or the EEW alarm going off.
        "wake_from": 5,
        # a later report of the SAME quake this much worse goes again as a
        # correction: 3 -> 6-strong must never be filed as a duplicate
        "revision_step": 5,
        # and a bigger one this soon after is a sequence, not a repeat
        "sequence_hours": 72,
        # A typhoon is never an event on its own -- there are ~25 a year and
        # almost none touch Tokyo. It is only ever the reason for rain she is
        # actually standing in, and this is how much rain counts.
        "heavy_rain_mm": 4.0
    },

    "trains": {
        # Whether her train is running. geography.json says her commute is the
        # Seibu Ikebukuro line, with Seibu Toshima one stop and Toei Oedo for
        # Hikarigaoka -- none of which are JR East, so the JR status page he
        # sent covers what she CHANGES onto at Ikebukuro, not the train she
        # gets. Yahoo's Kanto page has all 150 lines in one HTML table,
        # including all three of hers (84, 91, 131). Its RSS is gone and
        # Seibu's own domain does not resolve from here.
        #
        # ODPT (his access token, 2026-08-25) is the official feed and wins
        # for every line it carries -- but the public API has NO Seibu and NO
        # JR East (TokyoMetro, Toei, TWR, MIR, TamaMonorail, Yokohama only),
        # so it covers her Oedo line and the Metro lines she changes onto,
        # and Yahoo stays for the two Seibu lines and JR. odpt_lines maps the
        # railway id to the Yahoo name so the state stays keyed one way.
        "enabled": True,
        "poll_minutes": 6,
        "odpt_key": "",
        "odpt_url": "https://api.odpt.org/api/v4",
        "odpt_lines": {},
        # the Challenge API (a second token, api-challenge.odpt.org) is where
        # Seibu and JR East live. **The Challenge token expires 2026-10-01**;
        # after that the poll logs one line and drops back to Yahoo for those
        # lines until a new token is pasted in. JR East comes per line like the public
        # feed; Seibu is ONE operator-wide row with a text and no status, so
        # it is applied to her Seibu lines only when the text stops saying
        # 平常 (Yahoo keeps the per-line status the rest of the time, and the
        # official text becomes the detail when something is wrong).
        "odpt_challenge_key": "",
        "odpt_challenge_url": "https://api-challenge.odpt.org/api/v4",
        "odpt_challenge_lines": {},
        "odpt_operator_lines": {},
        # Her own lines and the ones she changes onto, in her own config and
        # EMPTY here for the same reason as the wards above: a train board
        # with no line to watch has nothing to read, and the section
        # switches itself off (`Config.NEIGHBOURHOOD`).
        "her_lines": [],
        "her_salience": 4,
        # the ones she changes onto at Ikebukuro: a suspension there reshapes
        # the day for everyone she knows, but it is not her getting to school
        "nearby_lines": [],
        "nearby_salience": 2
    },

    "withholding": {
        # Not answering, on purpose. Everything that made her slow was
        # mechanical -- delay_factor, the glance roll, the schedule -- and in
        # all of it she is TRYING to answer and something is in the way. She
        # could not look at a message, understand it, and leave it there.
        # Being left on read was modelled on his side only.
        "enabled": True,
        # when there is anything to decide
        "tension_from": 25.0,
        "weight_tension": 0.9,
        "weight_anger": 0.7,
        "weight_shame": 0.5,
        "weight_sadness": 0.35,
        "weight_resentment": 0.6,
        "weight_rupture": 0.35,
        "tit_for_tat_minutes": 40,
        "weight_tit_for_tat": 0.25,
        # gone off him: leaving it there is easy when she does not care
        "cold_from": 30,
        "weight_cold": 0.6,
        # where she stands with him (the `standing` meter): under
        # standing_secure_from a sulk costs more than she has, over it she
        # can afford to leave him waiting
        "standing_secure_from": 50,
        "weight_standing_low": 0.4,
        "weight_standing_high": 0.2,
        "threshold": 0.55,
        "min_gap_hours": 5,
        "max_per_day": 2,
        "messages_shown": 10,
        "min_minutes": 8,
        "max_minutes": 240,
        # what it costs to keep it up
        "charge_every_minutes": 20,
        "unsaid_per_hour": 9.0,
        "awkward_per_hour": 7.0,
        "awkward_soft_cap": 85.0,
        "guilt_per_hour": 6.0,
        "guilt_soft_cap": 70.0,
        "shame_on_cave": 7.0,
        "shame_soft_cap": 70.0,
        # INTENT OVERRIDES. She decided not to answer; she did not decide to
        # stop wanting things. Her own impulse can always break it -- it just
        # has to clear this much more than usual -- and her resolve erodes,
        # much faster while he has not noticed she is doing it.
        "resolve_base": 22.0,
        "resolve_decay_per_hour": 4.0,
        "resolve_decay_per_unnoticed_hour": 9.0,
        # the sulk nobody noticed: worse than not sulking, and she knows it
        "irk_after_hours": 1.0,
        "irk_full_hours": 3.0,
        "irk_craving_per_hour": 7.0,
        "irk_tension_per_hour": 2.5,
        "irk_soft_cap": 90.0,
        # an empty persona answer whose reasoning chose silence becomes a
        # `silence` this long, instead of a retry
        "silence_from_empty_minutes": 90,
        # a silence whose clock runs out while he has still written nothing
        # gives his message back to her reply path, once, and she is offered
        # it again rather than it staying read and unanswered for good
        "silence_hands_back": True,
        "always_breaks": ["sorry", "you ok", "you okay", "are you alright", "my fault"],
        "breaks_if_words": 2,
        "keep": 200
    },

    "rhythm": {
        # When he is around, learned from when he has been around. This
        # replaces a parsed window: that heard a short break message and
        # built an object with a start, an end and a penalty fired off a clock,
        # which is declared rather than derived and knew what he said and
        # nothing about what he does. The record already holds his hours.
        "enabled": True,
        "messages_scanned": 600,
        "half_life_days": 21.0,
        "latency_cap_minutes": 720,
        "min_samples": 3,
        "neighbour_weight": 0.5,
        "cache_seconds": 120,
        # the tempo: how live this exchange is right now, which is the whole of
        # "he only has a few minutes" without him having to say so
        "turns_scanned": 14,
        "burst_minutes": 12,
        "burst_full": 6,
        "stale_minutes": 25,
        "slow_minutes": 20,
        "weight_latency": 0.5,
        "weight_density": 0.3,
        "weight_fresh": 0.2,
        "one_sided_factor": 0.4,
        # what a live exchange does to her delay
        # PRESENCE: is he at the phone. One number, decaying, from receipts
        # (his chat focused -- the strongest signal, and the one the old tempo
        # ignored entirely while inferring it from message gaps), then him
        # having spoken, then the learned hour as a weak prior. The old tempo
        # had three terms and one signal: latency, density and freshness are
        # all "how recently was he active", so weighting them counted one piece
        # of evidence three times and called it confidence.
        "presence_read": 0.95,
        "presence_read_half_min": 6.0,
        "presence_active": 0.45,
        "presence_spoke": 0.85,
        "presence_spoke_half_min": 4.0,
        "presence_quick": 0.9,
        "quick_reply_minutes": 3.0,
        "presence_prior": 0.35,
        # bimodal with hysteresis: entering costs more than staying, so a
        # ninety-second lull does not drop her out of the exchange and back in
        "enter_above": 0.55,
        "stay_above": 0.35,
        # NOTICING is all presence buys. Composing is her (state.compose_factor)
        # and is not capped.
        "notice_live_seconds": [4, 25],
        "notice_glance_seconds": [90, 600],
        "notice_idle_seconds": [40, 900],
        "he_left_extra_seconds": [60, 240],
        # what she picks up about how he is being, against four months of him
        "notice_faster_ratio": 0.4,
        "notice_slower_ratio": 2.5,
        "tempo_from": 0.45,
        "fast_seconds": [8, 45],
        # A live exchange makes her a bit likelier to answer under the desk.
        # A BIT. At 2.2 this came out at 0.88-0.95 and she answered him through
        # class, dinner and the bath queue -- which is her being bound to his
        # reply, and her having a life of her own is the entire premise. The
        # ceiling is the real guard: however live it is, there is always a
        # solid chance the answer is "not now, she is busy".
        "glance_boost": 1.4,
        "glance_ceiling": 0.6,
        "delay_factor_cap": 1.15,
        # an hour he is never about in is not an hour of being ignored
        "quiet_hour_factor": 0.4,
        # And what he has actually told her. Not a booking: nothing fires off a
        # clock, nothing punishes him for being wrong, and it fades. It moves
        # what she EXPECTS, which is what makes his being there or not being
        # there land -- him saying "I'm up, talk to me" outweighs the record for
        # an hour and is worth nothing tomorrow.
        "hear_enabled": True,
        "said_trigger_words": ["break", "work", "shift", "busy", "free", "off in",
                               "back in", "home in", "asleep", "sleep", "leaving",
                               "driving", "meeting", "lunch", "hour", "minute", "min",
                               "later", "tonight", "tomorrow", "away", "up in", "on in"],
        "said_min_chars": 8,
        "said_min_confidence": 0.5,
        "said_max_per_message": 2,
        "said_max_hours": 16,
        "said_dedupe_minutes": 20,
        "said_half_life_hours": 6.0,
        "said_weight": 0.85,
        "said_line_from": 0.25,
        "said_keep": 200,
        # the lines she gets
        "tempo_live_line": 0.6,
        "quiet_line_below": 0.15,
        "busy_line_above": 0.7
    },

    "approach": {
        # Getting at a sealed thing without admitting how she knows it. A
        # discovery from the snoop used to be unraisable for as long as it
        # stayed hot, which at charge 100 against a 9-day half-life and a carry
        # floor of 12 is twenty-seven days -- so the largest fact she held about
        # him sat in her prompt for a month and the only thing that ever
        # happened to it was that it stopped mattering. People circle a thing
        # like that instead: they ask the general form of the specific question
        # and hope he answers it himself.
        "enabled": True,
        # it has to still be worth circling, and to have had time to work on her
        "min_live": 25.0,
        "days_full": 6.0,
        # pressure = these four, against `threshold`
        "weight_charge": 1.0,
        "weight_age": 0.35,
        "weight_unsaid": 0.4,
        "weight_attachment": 0.3,
        "threshold": 0.85,
        # opportunity and cost. She does not do this in front of people, she
        # does not do it twice in a night, and she will not go at the same
        # thing more than max_per_item times however much it is pushing --
        # after that she has asked what she can ask without giving herself away.
        "min_gap_hours": 20,
        "max_per_day": 1,
        "per_item_gap_days": 3.0,
        "max_per_item": 3,
        "unsaid_over_baseline": 25.0,
        # shame is the gauge that makes her hide, and this is the most exposing
        # thing she can do short of confessing
        "shame_blocks_from": 55.0,
        # what it does to the thing and to her
        "discharge": 0.25,
        "unsaid_relief_base": 6.0,
        "unsaid_relief_per_charge": 0.12,
        "unsaid_relief_max": 20.0,
        "awkward_per_risk": 4.0,
        "awkward_soft_cap": 85.0,
        "risk_shame_from": 3,
        "shame_on_close_call": 8.0,
        "shame_soft_cap": 70.0,
        "messages_shown": 10,
        "keep": 200
    },

    "events": {
        # What she is actually doing about what is on. Runs once a day, just
        # before the schedule is generated, so the plan can honour what she has
        # agreed to -- the old order built the plan first and let the cast
        # comment on it, which meant nobody in her life could ever cause her to
        # go anywhere. Stances: going / dragged / avoiding / cannot / not hers,
        # and `dragged` is the common honest one: somebody with standing over
        # her decided, and her choice was whether to spend something refusing.
        "enabled": True,
        "lookahead_days": 8,
        "max_per_day": 10,
        "keep": 24
    },

    "lookup": {
        # she quietly looks up a thing he mentions (sim/lookup.py): cheap
        # regex gate on his message, then one call to name the thing, his
        # MAL list / MAL search / a web search, one call for the gist; in
        # a thread during her read delay (the reply waits up to
        # wait_seconds for it). The gist reaches the reply, kv lookups and
        # her facts about him (fact_weight). He is never told.
        "enabled": True,
        # The regex only fires on genre words or a quoted title, so naming a
        # series outright -- which is how people actually talk -- missed
        # entirely: a question naming a series outright got nothing, while anime_kb resolves the series name and holds the whole cast. So the other trigger is simply whether a
        # phrase in his message resolves against his own history.
        "kb_trigger": True,
        "kb_min_chars": 4,
        "kb_max_candidates": 40,
        # a single distinctive word may be checked against MAL search, but only
        # counts if the answer turns out to be something he has watched
        "kb_api_max_candidates": 2,
        "kb_api_min_chars": 5,
        "trigger_regex": "watch|watching|watched|read|reading|listen|song|album|band|play|playing|played|game|anime|manga|movie|film|show|episode|\\bep\\s?\\d|series|season|book|novel|youtube|stream|finished|started|binge|\u300c|\u300d|\\\"[^\\\"]{3,}\\\"|'[^']{3,}'",
        # How the message is gated before the classifier reads it. "regex" is
        # the English keyword gate above plus the history probe; "model" sends
        # EVERY inbound message to the classifier, which is the only gate that
        # works for a character who chats in Japanese -- a short Japanese remark about a favourite character
        # has no keyword in it. One flash call a message; the cap below is on
        # finds, so attempts are not what it counts.
        "gate": "regex",
        # lookups that FOUND something, per day. It used to count attempts,
        # which under a model gate would have spent the day's dozen on a
        # dozen ordinary messages.
        "max_per_day": 12,
        "wait_seconds": 25,
        "timeout_seconds": 12,
        "keep": 80,
        "fact_weight": 2,
        # A character he names, in any script, is read up on at a fan
        # encyclopedia rather than his list's card: the pixiv dictionary has
        # the full name, temperament, relationships and running jokes; MAL's
        # card has a romaji name and a voice actor. Only when the show is
        # ANCHORED -- open in front of him, named in the message, or in the
        # last few lookups -- so a bare kana word is never searched on its
        # own. Fetched through the synopsis fetcher's browser, condensed by
        # `character_digest`, cached in `recaps` (kind "character").
        # a search she asks for: `[search: what she wants to know]` on its own
        # line in a draft runs one web search and one `search_gist` call, and
        # the reply is written again with the answer in front of her
        # (`Persona.generate`). Her style file has to tell her the line
        # exists; both files do (`prompts/style.md`, section "Looking
        # something up"), so it is on for both characters.
        # search_per_day caps every search, hers and her sight's.
        "on_request": False,
        "search_per_day": 8,
        # A request of hers for a thing the automatic lookup off his
        # message fetched this recently is answered out of what she
        # already knows: no web request, no gist call, no second record
        # written over the first, and her situation says she knew it
        # rather than that she just looked it up. Kept at the window the
        # lookup's own gist rides in her situation (situation_hours), so
        # the thing she is being answered from is the thing in front of
        # her. 0 turns the short-circuit off.
        "search_known_hours": 6.0,
        "character_pages": True,
        "character_query": "site:dic.pixiv.net {show} {name}",
        "character_hosts": ["dic.pixiv.net/a/"],
        "character_max_chars": 600,
        # A lookup used to reach one reply and then survive as a 160-character
        # fact. Two ways it stays with her now (his call, "do both"):
        # the last `situation_max` lookups of the last `situation_hours` are
        # in her situation on every message, so a conversation about a thing
        # continues without a second search --
        "situation_hours": 6.0,
        "situation_max": 3,
        # -- and every looked-up or watched thing is kept as a KNOWN thing
        # with its names (sim/known.py, kv `known_things`) and comes back into
        # her situation whenever a message of his names it, with no window.
        # At most `known_max_lines` per message; `known_keep` things kept.
        "known_max_lines": 2,
        "known_keep": 200,
        # How long the page last resolved on his screen (`sim/works.py`)
        # counts as being in front of him, for the one line that tells the
        # classifier what he is looking at. It read the module that watches
        # his player instead, and named an episode he had finished while a
        # different work was open in front of him.
        "in_front_minutes": 30.0,
        # How many of HER OWN last turns the classifier is told about, so a
        # message about a thing she sent him is anchored on the thing: a post
        # she shared (its author, its text and what the picture on it is), a
        # thing she looked up, a title she named. It used to be handed his
        # message alone, and "nani kore?" about a link she had sent one turn
        # earlier came back as nothing worth looking up.
        "anchor_turns": 3
    },

    "posting": {
        # her own posts on X, from her day (tomoe/posting.py). Checked each
        # director tick, and three things have to be true with no fourth: her
        # phone is free (which is also how "she is awake" is known -- the
        # night is the one block of her day whose phone is off), she is inside
        # her budget (curation.max_posts_per_24h / post_min_gap_hours), and
        # she feels like it -- a probability from base + unsaid + mood swing +
        # boredom + loneliness (+ event_bonus when something salient happened
        # today). There is no window of hours: `hours_start` / `hours_end`
        # were 08:00-01:00, a clock hour standing in for a wake the sleep
        # model draws anywhere between 06:20 and 11:05, and they shut the
        # fifty minutes of free phone a school morning has before she leaves
        # the house. Mode by gauges: vent (unsaid >=
        # vent_unsaid or mood <= vent_mood), bright, bored, plain. Posting
        # relieves unsaid by unsaid_relief. The post itself goes through
        # curation (dry-run until sensors.x_posting_enabled).
        "enabled": True,
        "base_probability": 0.02,
        "unsaid_weight": 0.5,
        "mood_swing_weight": 0.4,
        "boredom_weight": 0.3,
        "loneliness_weight": 0.2,
        "event_bonus": 0.08,
        "event_salience": 4,
        "cover_shame": 45,
        "vent_anger": 42,
        "vent_sadness": 45,
        "bright_pride": 62,
        "vent_unsaid": 55,
        "vent_mood": 35,
        "bright_mood": 75,
        "bored_boredom": 65,
        "unsaid_relief": 12,
        # a low hour vents only with this much unsaid behind it; the rest of
        # the day is a weighted pick among seen / into / bored / plain, never
        # the same kind twice running
        "vent_unsaid_low_mood": 30,
        "seen_weight": 3,
        "into_weight": 2,
        "bored_weight": 3,
        "plain_weight": 2,
        "seen_fresh_hours": 12,
        "engagement_bonus": 0.05,
        # how many of her own posts the composer is shown. Nineteen posts in a
        # fortnight had one shape -- a detail, a hedge, an abstract feeling, a
        # closing sentence naming that feeling -- and six were not enough to
        # see it. The composer reads them for the shape as well as the words.
        "recent_posts_shown": 10,
        # how long a yes she could not act on keeps (tomoe/posting.py). A
        # yes that lands while his message is unread or her bubbles are
        # still going out is written to the save and taken up at the next
        # quiet tick instead of evaporating; the gate is rolled about every
        # 20 minutes, so 90 gives a hold four or five chances at a quiet
        # tick and still refuses to post a feeling from another part of her
        # day. Her date turning over ends it too, whichever comes first.
        "hold_max_minutes": 90
    },

    "taste": {
        # tomoe/taste.py: her verdicts over the carded accounts, in batches
        "judge_batch": 40
    },

    "curation": {
        # what she may do on the X account per day, and the evidence the
        # code demands before it lets her: a follow needs follow_min_likes
        # reactions to that account in her taste sheet, an unfollow needs
        # unfollow_min_dislikes and no likes, and anything he liked or
        # followed is never unfollowed (his side of the account is his).
        "enabled": True,
        "max_likes_per_day": 6,
        "max_follows_per_day": 2,
        "max_unfollows_per_day": 2,
        # Her posts are budgeted on a ROLLING 24 HOURS, not on the calendar
        # date the other four are: her day does not end where the date does --
        # she is awake with her phone in bed until 01:10 or 01:30 -- so a
        # midnight reset put that hour on the wrong side of the cap and three
        # of her first twenty-two posts landed in the first sixty seconds of a
        # date, which made two a day read as three one night and one the next.
        # `post_min_gap_hours` is the ONE gap (it was two settings, 3 and 4,
        # and a post written at three burned a call, was held at four, and
        # pushed her next attempt to six); a skip spends it as a post does.
        "max_posts_per_24h": 2,
        "post_min_gap_hours": 4,
        "max_reposts_per_day": 1,        # the post whose photo she sent him
        "post_max_chars": 140,
        "follow_min_likes": 2,
        # an account she found by searching needs only one like to follow
        "follow_min_likes_discovered": 1,
        # the drop list from her verdicts (tomoe/taste.py) is acted on at this
        # pace, inside max_unfollows_per_day
        "drift_unfollows_per_day": 2,
        "unfollow_min_dislikes": 3,
        # somebody new follows the account: it follows them back, with no
        # evidence asked for, because that is what an account does. Its own
        # daily budget, so a day of new followers never spends the follows she
        # chose for herself; the two caps add up to the day's total.
        "follow_back": True,
        "follow_back_per_day": 3,
        # A post she has just sent him: what the account then does with it
        # in public is her pick, not a coin flip. One judge call
        # (`x_repost_judge`) puts the post to her taste -- her sheet, her
        # reactions to that account, her verdict on it, what the account has
        # reposted lately -- with the fact that she has just sent it to him,
        # and answers repost / like only / neither. Off here, or with nothing
        # of hers to judge from, the probabilities below are the fallback.
        "share_pick": True,
        # how many of the account's recent reposts the judge is shown, so a
        # timeline with one note in it is something it can see
        "share_pick_recent": 6
    },

    "x": {
        # tomoe/replies.py: answering somebody who answered a post of hers.
        "enabled": True,
        #  Everything posted under it
        # before this date was not written by her, and she cannot answer for words she
        # did not write and does not know the reason for. A reply under a post
        # older than this is dropped at read-in and never becomes a candidate,
        # so it reaches neither her prompt nor her store as "a reply to you".
        "replies_not_before": "2026-08-22",
        # a rolling 24 hours, like her posting budget and for the same reason:
        # she is on her phone in bed past midnight and her day does not end
        # where the date does
        "replies_max_per_day": 3,
        "reply_cooldown_minutes": 45,
        # how many wait in front of the judge at once, and how long a reply is
        # still worth answering: an answer to a two-day-old reply is not a
        # conversation
        "reply_candidates_max": 6,
        "reply_candidate_hours": 36,
        "reply_max_chars": 140,
        # the account line in her situation: how long news of new followers
        # stays there. It is the CHANGE since she last looked, never a running
        # total -- a standing count is telemetry, not news.
        "followers_line_hours": 24
    },

    "cast": {
        # each person's own day, one line at the compile (cast_life), kept
        # and shown to the beat writer and to their own speaker calls
        # each person's day from the `week` on their sheet, seeded, with a
        # twist drawn with twist_p: the cancellation, the lateness, the
        # phone taken away. Known to us (/cast day), not to her.
        "plans_enabled": True,
        "twist_p": 0.25,
        "lives_enabled": True,
        "lives_keep": 10,
        "lives_shown": 4,
        # WHAT EACH OF THEM HAS TO BRING UP, written at the compile for the
        # day about to start and spent one call at a time (`sim/pocket.py`).
        # Their own day, whatever they said they would bring up, one thing
        # going round that they have actually heard, a piece of the week
        # assigned to them, the beat of their own storyline, the fixture
        # their week has them at. The group chat is told it is mostly made of
        # concrete things and was handed the day's plan and each other, so it
        # settled the plan again: 77% of 175 group turns carried a time, a
        # plan or an obligation.
        "pocket_items": 4,
        # A CARRY THAT HAS TO MOVE. `carry` is the one thing still on a
        # person's mind going into tomorrow and it is what the next day is
        # written from. On 2026-09-07 all six of them were about the
        # character whose world it is and four were the identical sentence
        # three days running. After this many consecutive days about her, the
        # prompt says today's is about their own life and a carry that is
        # still about her is dropped rather than rewritten.
        "carry_about_her_max_streak": 1,
        # the people around her as sources: a seeded daily draw per person
        # (mood, attention, friction) and a social script written once a day
        # at the schedule generation; beats land on the clock as events the
        # director must reflect. Nobody sees a beat before its time.
        "enabled": True,
        "seed": "scail",
        "default_volatility": 0.6,
        # The late stretch of the group chat: the thing the sleep model reads
        # to decide she could not go to bed (`Health._chat_alive`). Asked for
        # in the prompt AND repaired here, because a prompt asking a model to
        # write purposeless messages loses to an input full of plans: the
        # record had every group turn at 12:00, 20:00 or 21:00 and nothing
        # after 21:37 in eight days. `late_tail_min_*` are minutes past 23:00,
        # so -100..200 is 21:20..02:20 -- drawn per night, never a round hour.
        # A NEGATIVE draw is a night the chat simply dies early, and then
        # nothing late is required: a mandatory late block every night is as
        # artificial as the 21:00 ceiling it replaced (his call). Nobody
        # else's tiredness is modelled.
        "late_from_hm": "23:00",
        # ...but never before this. A negative draw is a night that dies early,
        # not a curfew in the early evening: -100 with tomorrow's pull on top
        # put 2026-08-28's group to bed at 21:27 on a Friday in the summer
        # holidays, and every beat after it died on arrival. The floor is the
        # earliest a chat of four fifteen-year-olds is plausibly over.
        "night_floor_hm": "22:20",
        "late_tail_min_lo": -100,
        "late_tail_min_hi": 200,
        "late_beats_min": 2,
        # The chat knows what tomorrow holds. If they all have to be up early
        # -- school, a club fixture, somebody's match -- it dies earlier,
        # together, the way a real group does; a lie-in for everybody lets it
        # run. `ref_hm` is the hour that costs nothing; every hour earlier than
        # that than the group's first commitment pulls the end in by
        # `morning_pull` of the difference.
        "late_morning_ref_hm": "10:00",
        "late_morning_pull": 0.55,
        # a beat that is about NOTHING -- a video, a shop find, a bad fringe,
        # two words about the heat. Real teenagers do not run a committee.
        "idle_share": 0.34,
        # Somebody she is physically WITH says something, unplanned. The
        # planner writes a day in advance and cannot know she would still be
        # at that table two hours later: on 2026-08-28 she sat across from Aya
        # from 09:05, and the day held ONE four-minute conversation with her
        # at 09:10 while a LINE exchange with Hinako ran 37 minutes at the same
        # table. `presence_gap_minutes` is how long the silence has to have
        # been; the person still writes her own words.
        "presence_enabled": True,
        "presence_gap_minutes": 25,
        "presence_max_per_day": 5,
        # Nothing in the mechanism knows the group chat has gone quiet: the
        # beats are placed once when the plan is written and an exchange runs
        # on a flat per-round probability, so a room dead for five hours is in
        # the same state as one that spoke a minute ago. With this on, a group
        # beat later in the day is moved to now once the room has held nothing
        # for `quiet_after_minutes`, at most `quiet_pull_max_per_day` times,
        # never into the dead part of the night and never over a live
        # conversation. ON since 2026-09-05, to be watched live.
        "quiet_pull_enabled": True,
        "quiet_after_minutes": 95,
        "quiet_pull_max_per_day": 2,
        "reversion": 0.25,
        # The day's social budget: a floor, plus the cast's own reach. This is
        # the SUM of their attention, not the mean -- on the mean the whole
        # world got about eight moments a day whoever was in it, and every day
        # in the record had a three-to-four hour silence inside her waking
        # hours. Each person is then given her own share of the total.
        "beats_base": 5,
        "beats_per_attention": 3.5,
        "beats_min": 2,
        "beats_max": 20,
        # a beat at or above this salience interrupts the director's timestep
        "interrupt_salience": 3,
        # drift guard: share of salient events about him above which the
        # showrunner is told to lean the next week toward her own people
        "him_share_warn": 0.7,
        # A person on the roster as a set of mechanisms -- trigger,
        # suppressor, function -- rather than a description
        # (tomoe/cast_mechanisms.py, docs/cast-mechanisms.md). One file per
        # roster key in `mechanisms_dir`; a person with no file has no block
        # and her calls go out unchanged. `mechanisms_max_chars` is the byte
        # ceiling on one person's block in one prompt, and over it the
        # rarest mechanisms are dropped first: what a person does every day
        # is what a reader of the block needs, and the once-a-month one is
        # what the day could have gone without.
        # Raised from 1800 to 3600 on 2026-09-06, when the compile added a
        # derived layer of about fifteen instances under everybody's
        # hand-written ones: at the old ceiling the whole derived layer and
        # both stress modes were the first thing dropped, since they are the
        # rarest, and the compile would have written a block nobody read.
        "mechanisms_dir": "",
        "mechanisms_max_chars": 3600,
        # The ceiling on the CHARACTER's own block in her own prompt, which
        # is a different size of thing: it rides in the half of her prompt
        # that changes about once a day rather than in a call about somebody
        # else, so it is charged to the cache once and not per turn.
        "own_mechanisms_max_chars": 9000,
        # The personality type each person was written from, and the
        # observable markers it was translated into. NOTHING that assembles
        # a call may read this file -- not a prompt builder, not a role, not
        # a prompt. It is for the author and for `tools/cast_type_test.py`,
        # which counts the markers in the record and says whether the
        # described behaviour actually appears. Naming the type to the model
        # would be telling it the answer.
        "types_file": ""
    },

    "cast_arcs": {
        # the people's own lives (tomoe/cast_arcs.py): weekly, each role gets one
        # or two personal arcs with loosely dated beats, a want for the week
        # (a goal that may pull Tomoe in), and a one-line running record; plus
        # an inter-cast web (who is tense/close with whom this week). Keyed by
        # role_id so the lore filling a role can be re-cast without losing the
        # machinery. The daily beat-writer (cast.py) reads these so beats are
        # driven by the people's own plots and the group's tensions, not just
        # the random walk. weekday 6 = Sunday; also runs once when there are
        # none. roles_focus = how many people carry an active arc at once
        # (the rest tick along on the draw); the others still appear in beats.
        "enabled": True,
        "weekday": 6,
        "min_days_between": 6,
        "arcs_per_person": 2,
        "roles_focus": 4,
        "beats_lookahead_days": 10,
        "days_in_prompt": 7,
        "keep_records": 40,
        # a person with an arc beat within a day is more present: their daily
        # draw gets this attention bump (the walk is seeded from their life)
        "arc_active_attention_bump": 18,
        # evolution: the cast itself changes over time. On the weekly day, with
        # evolve_probability, at most one change (add a new person, retire one
        # to dormant, or shift a relationship). Roles are categories, so adds
        # can share a role (a second friend, a classmate). max_people caps the
        # active, non-dormant cast (excluding him).
        "evolve_enabled": True,
        "evolve_probability": 0.35,
        "evolve_min_days_between": 13,
        "max_people": 12
    },

    "environment": {
        # where her body is: the weather line is outside; what she feels is
        # the ambient of her setting (outdoors / air-conditioned indoors or
        # transit / indoors without / bath). The director names the setting
        # per scene; between ticks it is read off the block's words, and an
        # indoor place switches the air-con on above ac_from_feels.
        "enabled": True,
        "ac_from_feels": 28,
        "heat_from_feels": 12,
        "ac_feels": 27,
        "heated_feels": 20,
        "transit_feels": 26,
        "bath_feels": 30,
        # a room without air-con sits this many degrees inside the outside
        "indoor_offset": 3,
        "outdoor_keywords": ["street", "walk", "walking", "park", "outside", "balcony", "bike", "cycling", "shrine", "festival", "beach", "river", "bus stop", "platform", "courtyard", "schoolyard", "on the way", "heading to", "konbini run", "rooftop", "veranda"],
        "indoor_keywords": ["home", "room", "kitchen", "school", "class", "cafe", "house", "shop", "konbini", "store", "library", "mall", "karaoke", "restaurant", "gym", "hall", "apartment", "lobby", "clinic", "cram"],
        "transit_keywords": ["train", "seibu", "subway", "bus", "metro", "yamanote", "commute", "ride home"],
        "bath_keywords": ["bath", "shower", "ofuro"]
    },

    "needs": {
        # hunger as a gauge: rises with the hours (slower asleep), a meal
        # resets it (the director's `ate`, or meal words in the scene/block
        # pull it down at meal_pull_per_hour), and past hungry_from it
        # presses on mood and comfort. Rest is the energy gauge.
        "enabled": True,
        "hunger_per_hour": 9,
        "hunger_asleep_factor": 0.3,
        "after_meal": 8,
        "snack_drop": 25,
        "meal_pull_per_hour": 80,
        "hungry_from": 60,
        "starving_from": 80,
        "hunger_mood_per_hour": 2,
        "hunger_comfort_per_hour": 3,
        # 1 + 2 of the needs plan (2026-08-19): mechanical consequences and
        # director-local deviation. Outdoors in heat drains energy and counts
        # as exposure (health reads yesterday's exposure into the cold odds);
        # a red need (hunger >= red_hunger, energy <= red_energy) tightens
        # the director's tick and lets it deviate inside the block (a
        # fridge raid, a nap) without a replan; a replan only when the
        # director moves a later block.
        "heat_from_feels": 33,
        "heat_energy_per_hour": 4,
        "rain_mm_from": 0.5,
        "red_hunger": 70,
        "red_energy": 25,
        "red_tick_minutes": 20,
        "director_may_deviate": True,
        "meal_keywords": ["breakfast", "lunch", "dinner", "supper", "eating", "eats", "bento", "curry", "ramen", "udon", "soba", "gyudon", "meal", "okonomiyaki", "yakisoba", "family restaurant", "saizeriya", "gusto", "mcdonald", "mos burger", "sushi", "onigiri lunch", "at the table"],
        "snack_keywords": ["snack", "konbini", "ice cream", "pocky", "crepe", "taiyaki", "onigiri", "jelly drink", "bread", "melon pan", "cafe", "starbucks", "parfait", "chips", "candy", "kakigori", "takoyaki"]
    },

    "health": {
        # her body, mechanically: a cold now and then, a cycle, bad nights.
        # Seeded per day; effects are targets the world terms pull toward.
        "enabled": True,
        "seed": "scail",
        "cold_p_per_day": 0.025,
        "cold_days_min": 2,
        "cold_days_max": 5,
        "cycle_days": 28,
        "cycle_start": "2026-08-03",
        "period_days": 5,
        # yesterday's hours outdoors in heat or rain (kv exposure) raise the
        # odds of a cold starting today, per hour
        "exposure_cold_p_per_hour": 0.02,
        # an hour walked in rain without an umbrella counts this many hours of
        # exposure (embodied/situation.py hands it to Body.note_wet at arrival)
        "wet_exposure_factor": 2.0,
        "pull_per_hour": 6,
        "cold_energy_target": 35,
        "cold_comfort_target": 35,
        # health moves the body, and mood follows: mood is computed from its
        # causes and being ill is one of them. It moved mood directly before,
        # which is two systems owning one gauge.
        "cold_unwell_target": 62,
        "period_unwell_target": 48,
        "rough_night_unwell_target": 30,
        "period_comfort_target": 38,
        "period_anxiety_target": 48,
        # How well she slept is no longer a coin flip. Each night is scored
        # 0-100 from concrete terms and banded good/ok/poor/rough; the score
        # sets how tired she is and (with her bedtime) when she wakes. Seeded
        # per night, computed at the midnight rollover from her evening state,
        # the overnight forecast and when she last ate.
        "sleep": {
            "enabled": True,
            "planned_bed_free": "01:30",     # skeleton lights-out
            "planned_bed_school": "00:50",
            "need_hours_free": 8.5,           # what her body wants
            "need_hours_school": 7.0,
            "need_jitter_hours": 0.4,
            # wound-up delay to actually falling asleep (minutes)
            "delay_base_min": 10,
            "delay_jitter_min": 15,
            "delay_ref": 55,                  # gauge value where anxiety/unsaid start to bite
            "delay_per_anxiety": 0.6,         # extra minutes per point over ref
            "delay_per_unsaid": 0.4,
            "screen_ref": 60,                 # curiosity/boredom this high = on the phone late
            # 「みんな起きてるのに私だけ寝るなんて無理!」 -- the group chat still being
            # alive is what actually keeps her up, and it is a different thing
            # from her phone in the abstract. Counts OTHER people's turns in
            # the group after `after_hm` (and into the small hours, to
            # `until_min` minutes past midnight -- 150 is 02:30, the latest
            # the chat is allowed to run): what holds her there is that they
            # are still talking. How late it actually runs varies by night and
            # is the planner's to decide; nobody else's tiredness is modelled. Feeds `delay`, so it also feeds `resist`
            # in the early-bed block -- a live chat both pushes her bedtime
            # later and makes her refuse to turn in early for a morning.
            "chat_alive_after_hm": "23:00",
            "chat_alive_until_min": 150,
            "chat_alive_per_turn_min": 6.0,
            "chat_alive_max_min": 75.0,
            "delay_screen_min": 20,
            "delay_max_min": 120,
            # The night before a promise with an hour on it. `planned_bed_*`
            # is the same hour whatever tomorrow holds and the delay only ever
            # pushes it later, so the system took her sleep and then charged
            # her for being late with it. The alarm now reaches backwards: how
            # much of the shortfall she actually closes is what the morning is
            # worth to her (`schedule.wake.rising`), against the phone and the
            # wound-up head that keep her up on any other night.
            "early_bed_max_min": 60,     # the most she brings it forward
            "early_bed_pull": 0.7,       # of the shortfall, at a full pull
            "early_bed_note_min": 10,    # under this it is not a decision
            "early_bed_knew_pull": 0.3,  # over this, staying up was one
            # heat: the BEDROOM ambient overnight (~03:00), not the street. She
            # sleeps with the AC on, so the room holds near the set-point
            # (config.environment.ac_feels) whenever it is hot enough out to run
            # it (ac_from_feels); on a cool night the room just sits a little
            # under the outside. Only a heatwave the AC can't fully beat, or a
            # muggy night with the AC off, bites.
            "heat_feels_ok": 27,              # at/below this room feels-like the night is comfortable
            "heat_pen_per_deg": 4.0,          # points per room-degree over ok
            "heat_pen_max": 34,
            "ac_struggle_from": 36,           # outdoor feels-like where the AC starts losing
            "ac_struggle_leak": 0.3,          # room-degrees gained per outdoor-degree over that
            "humid_ref": 80,                  # muggy (only counts on a warm room / AC off)
            "humid_pen_per_pct": 0.4,
            "humid_pen_max": 8,
            # an unsettled mind
            "mind_ref": 55,
            "anxiety_pen_per_pt": 0.5,
            "unsaid_pen_per_pt": 0.35,
            "mind_pen_max": 22,
            # food
            "late_meal_hours": 2.0,           # ate within this many hours of bed
            "late_meal_pen": 8,
            "hungry_to_bed_ref": 60,
            "hungry_pen_per_pt": 0.3,
            "hungry_pen_max": 10,
            # body
            "cramp_pen": 16,                  # period day 1-2
            "cold_pen": 14,                   # a cold >=2 days deep
            # duration vs need
            "short_pen_per_hour": 12,
            "short_pen_max": 40,
            "long_grog_from_hours": 10.5,
            "long_grog_pen": 6,
            # a poor night pushes the wake later (free: sleep in; school: snooze
            # under the alarm), minutes per 10 score points below 'ok'
            "free_oversleep_per_10": 12,
            "school_snooze_per_10": 4,
            "oversleep_max_min": 60,
            "wake_jitter_min": 6,
            "free_wake_floor": "08:00",       # a backstop, not a shaper: on a free
            "free_wake_ceil": "11:30",        # night bed ~01:40 + ~8.5h needs room
            "school_alarm": "06:45",
            "school_wake_ceil": "07:15",
            # score bands
            "good_from": 74,
            "ok_from": 55,
            "poor_from": 36,                  # below this = 'rough'
            # what energy pulls toward the next morning, per band
            "energy_target_good": 72,
            "energy_target_ok": 62,
            "energy_target_poor": 42,
            "energy_target_rough": 28
        }
    },

    "diary": {
        # her diary: first person, for herself, never addressed to anyone.
        # Not forced: when alone with her phone in these hours, unsaid at or
        # above min_unsaid, with a probability rising with it. Once an EVENING,
        # not once a calendar day: the window wraps midnight and she is on her
        # phone in bed for the last hour of it, so everything written inside it
        # belongs to the date the window opened on (`Diary.date_for_now`). On
        # the date, an entry written at 00:27 marked that day done and closed
        # its own 20:30 window, which left the small hours as the only chance
        # from then on -- twelve of the first fifteen entries were written
        # between 00:01 and 00:59, each about a day twenty-five minutes old.
        "enabled": True,
        "hours_start": "20:30",
        "hours_end": "01:30",
        # shame or sadness she is sitting on gets her writing even on a day
        # that left little unsaid
        "min_carried": 40,
        "carried_weight": 0.5,
        # her own day, which is the gate for a character with no chat with
        # him: how many things at or above `state.salient_from` her record
        # holds for the evening she would be writing about, and how much each
        # one past the line adds to the odds. Read only when she has nobody to
        # say things to, so the character who has is unchanged.
        "min_day_events": 4,
        "day_weight": 0.06,
        "min_unsaid": 50,
        "base_probability": 0.35,
        "unsaid_weight": 1.2,
        "relief": 30,
        # writing about a thing she has not asked him barely helps
        "relief_when_unasked": 10,
        "max_chars": 2500,
        "keep": 400,
        "in_prompt": 2
    },

    "agenda": {
        # What is coming, joined from the stores that already hold a dated
        # thing (sim/agenda.py): the calendar's holidays and what is on, her
        # open promises, what he said he would do, who the day's plan has
        # taken out of a day, and the lines today has settled. Nothing here
        # decides anything; it puts them in one order. `days` is how far
        # ahead it looks, `max_items` how many lines the block in her prompt
        # may carry (nearest first) and `in_prompt` whether she reads it at
        # all. The block rides in the SYSTEM half, so its dates are written
        # absolutely and its bytes move once a day.
        "enabled": True,
        "days": 7,
        "max_items": 12,
        "in_prompt": True
    },

    "weekly": {
        # Sunday at the day compile: a first-person paragraph of how the week
        # felt (her own sense of it), kept in her prompt
        "enabled": True,
        "weekday": 6,
        "in_prompt": 1
    },

    "anime_sense": {
        # Her sense of what he watches, from his episode history
        # (data/mal_history.db, kept current by tools/mal_history.py's daemon;
        # the bot only reads it). shelf_check: once a week she has looked at his
        # list and what he left hanging sits in her head as something to bring
        # up -- it lands as a director share_hint so intent/persona decide
        # whether she nags, teases, asks or lets it go. habits: what the
        # analysis knows about how he watches, written into user_facts through
        # memory (refreshed every habits_every_days; duplicates reinforce).
        # kb: when he names a series or a seiyuu, the lookup gets the real card
        # (cast with JP voices, studio, year, his own standing with it) instead
        # of synopsis fluff; seiyuu cards cross-reference his list.
        "enabled": True,
        "shelf_check_enabled": True,
        "shelf_check_weekday": 5,        # Saturday (his time)
        "shelf_check_min_days": 6,
        "stale_days": 21,                # untouched this long = 'left hanging'
        "nag_close_eps": 4,              # 'you are N eps from the end' when N <= this
        "nag_cold_max": 3,
        "habits_enabled": True,
        "habits_every_days": 30,
        "kb_enabled": True,
        "situation_line": True,          # 'his anime right now: ...' in her situation
        # the weekly hint rides her own prompts (reply or self-start) until she
        # brings his list up, it has been shown nag_shows_max times, or her day
        # ends. The share_hint path alone never landed: the impulse said no all
        # day while they were mid-conversation, and the hint died unsaid.
        "nag_in_prompt": True,
        "nag_shows_max": 10
    },

    "showrunner": {
        # weekly arcs (slow pressures). weekday 6 = Sunday. Runs at the day
        # compile; also runs once as soon as there is a compiled day and no arcs.
        "enabled": True,
        "weekday": 6,
        "min_days_between": 6,
        "max_arcs": 4,
        "days_in_prompt": 7,
        "calendar_lookahead_days": 21
    },

    "schedule": {
        "generate_at": "05:00",
        # when the director reports a schedule_change, the rest of the day
        # is re-planned around it (blocks already past stay as they were)
        "replan_on_change": True,
        "max_replans_per_day": 3,
        # When she wakes is drawn once per day (kv wake_days), not the fixed
        # skeleton hour. With the health sleep model on (the normal case) the
        # wake falls out of the night — bedtime plus how long and how well she
        # slept (health.sleep) — and this only clamps it to the structural
        # window (the slow-wake block ends 10:30) and rounds it. The base /
        # jitter / energy knobs below are the FALLBACK used only when the sleep
        # model is off.
        "wake": {
            "enabled": True,
            # an alarm: a promise with a start time on it pulls the wake back
            # to `from_hm` minus this, never past `free_min` / `school_min`.
            # Without it the night drew 10:10 for a morning she had already
            # agreed to be at the library at 9, and the plan the generator was
            # told to keep could not be kept -- a promise broken by arithmetic.
            # 75 = out of bed, dressed, fed, and across Nerima.
            "commitment_lead_minutes": 75,
            # Whether she actually gets up when it goes off. An alarm is the
            # earliest she COULD be up, not a guarantee, and duty is not what
            # moves her: school is compliance (a bell, a register, her mother)
            # and is already modelled by the school branch -- up at the last
            # possible minute, never earlier. What gets a fifteen year old out
            # of bed is wanting the morning, or being afraid of not being
            # there. Her own record carries both: an open `want` goal naming
            # it against an `avoid` one, the event stance (`going` vs
            # `dragged`, and WHO decided it -- a thing Rena settled for her is
            # not a thing she rises early for), and `Sentiments.belonging` --
            # when her place in the circle is thin, missing the thing is the
            # danger, so it pulls her up even out of a morning she dreads.
            # Against all of that: a short night and a body that is not well.
            # Net pull is signed and clamped to [-1, +1]; positive means up
            # before the alarm, negative means snoozing past it.
            "rising": {
                "early_max_min": 25,        # the most she is up BEFORE it
                "snooze_max_min": 45,       # the most she stretches past it
                "want_pull": 1.0,           # an open `want` goal names this morning
                "avoid_push": 0.9,          # an `avoid` goal does
                "pusher_push": 0.8,         # somebody else decided it for her
                "stance_going_pull": 0.5,
                "stance_not_hers_push": 0.6,
                "belonging_ref": 45,        # below this, absence is the danger
                "belonging_pull": 1.2,      # per belonging-point below ref, /100
                # per hour short of need. At 0.10 a 2.35-hour deficit moved
                # the scale by 0.23 against pulls of 1.74 -- sleep pressure
                # was a rounding error in a model about getting out of bed.
                "short_sleep_push": 0.25,
                "unwell_push": 0.012,       # per point of unwell
                # how short of her need she can be and still beat the alarm
                # at all. Anticipatory waking is a rested body's trick; past
                # this the early side is shut and wanting the morning only
                # buys being up when it goes instead of lying there.
                "early_needs_rest_hours": 1.5
            },
            "free_min": "08:00",
            "free_max": "11:30",   # same backstop as health.sleep.free_wake_ceil; keep them equal
            "school_min": "06:20",
            "school_max": "07:15",
            "round_to": 5,         # round the drawn wake to the nearest N minutes
            # fallback-only (sleep model off):
            "seed": 8123,
            "free_base": "09:30",
            "school_base": "06:45",
            "free_jitter_min": 22,      # gaussian sigma, minutes
            "school_jitter_min": 6,
            "energy_ref": 45,           # energy below this pushes wake later
            "energy_min_per_point": 0.7
        }
    },

    # What a feeling about another person is made of, before it has a name.
    # `sim/primitives.py`, spec `docs/primitives.md`. Nothing in the loop reads
    # it yet.
    #
    # There are no baselines here and that is the point. A relational quantity
    # rests at nothing when nothing has happened, because a baseline is where
    # something returns when it is left alone and there is no such place for a
    # history that does not exist. Baselines stay with the body and the
    # emotions, which she has alone in an empty room.
    "primitives": {
        # Off by default. The first character's relationship is described by
        # the meters in her cast file and by sim/sentiment.py, and switching
        # her over is `docs/primitives.md` §7 step 3 -- which changes what she
        # feels and is gated behind recomputing her primitives from the record
        # she already has (§6). A character who starts at zero turns it on.
        "enabled": False,
        "ceiling": 100.0,
        # per hour. Exposure is absent on purpose: what has been seen cannot be
        # unseen, so it is a ratchet with no decay term, and that is what makes
        # the opening condition of a character who has been read to the bottom
        # irreversible. Reciprocity drifts toward zero fastest, because people
        # do forgive a ledger; cost_of_loss barely moves, because it is the
        # integral of everything else and cannot be set in a day.
        "decay_per_hour": {
            "attention_hers": 0.6,
            "attention_his": 0.4,
            "predictability_hers": 0.05,
            "reciprocity": 0.06,
            "cost_of_loss": 0.02,
            "threat": 0.1
        },
        # attachment = attention x (cost of loss / 100) x this
        "attachment_gain": 1.0,
        # longing reaches its full pull at this many hours of silence
        # withholding needs something not yet shown AND a reason to care
        # whether he gets it
        "withhold_needs_unshown": 15.0,
        "withhold_needs_attention": 20.0,
        # the ick is a prediction error, so it needs a model to violate
        "ick_needs_model": 25.0,
        # a rupture needs enough of him seen that a break means something.
        # Kept because `admitted` crosses on the same pair and a rupture now
        # reads the latch: what breaks is being let in.
        "rupture_needs_exposure": 30.0,
        # The territory, which is a latch and not a gradient: a character whose
        # sheet sorts people into inside and outside with nothing between needs
        # a crossing, not a score that can differ between two messages. What
        # crosses it is her having done to him what he did to her -- seen
        # enough of him, and able to call what he does.
        "admit_needs_exposure": 45.0,
        "admit_needs_predictability": 40.0,
        # Fright: what he can do to her, times how little she can call what he
        # does next. Below the first it is not worth saying; above the second
        # it is the loudest thing about her and beats every other register.
        "fright_from": 25.0,
        "fright_hard_from": 55.0,
        # How much of his message the fright is worth, per point over
        # `fright_from`. An unrehearsed contact from somebody who can hurt her
        # moves anxiety, and that is the whole of her second driver arriving as
        # a number rather than as a sentence in a prompt.
        "fright_anxiety": 0.35,
        "fright_stress": 0.20,
        # The act needs a gap, and a gap needs something of her he has not got.
        "perform_needs_room": 20.0,
        # And the only way that gap ever opens for somebody who started with
        # all of her: an interior he was not there for. It does not unsee
        # anything -- exposure is still a ratchet -- it dilutes his share,
        # because she keeps happening. Small: a night's diary is not a
        # secret life.
        "private_step": 2.0,
        # An hour of her own day she did not hand over, counted once per
        # schedule block. Her diary at 2.0 a night was the only writer of
        # this in production, against `observe_step` running every tick the
        # other way, so the gap her act performs in could never open: 2 of a
        # required 20. A block is worth a quarter of a diary entry, which
        # puts a day of her own at about six points and the act within reach
        # in three days rather than nine. 0 for a character with no day.
        "private_block_weight": 0.25,
        # ...and the only way it closes again: something she told him about
        # herself. Fed by the timeline compile's `self_claims`, which already
        # names them daily and appends only the ones that are new, so this
        # costs no call. Calibrated against the real rate -- the first
        # character has made 77 of them over 14 days, a median of 6 a day --
        # and diminishing like `observe`, so three months of talking gets him
        # most of the way and never quite all of it.
        "disclose_step": 0.9,
        # what telling him also gives him: a little more ability to call what
        # she does, and one more thing he could use. The same coupling
        # `private_threat_share` applies in the other direction, which is why
        # intimacy and exposure to harm move together rather than separately.
        "disclose_share": 0.5,
        "log_rows": 200,
        # how much one thing she sees of him is worth, before the diminishing
        # term. She is resident on his machine, so this fires often and small
        # rather than rarely and large; below `observe_floor` it stops writing,
        # which is what stops a full row being rewritten forever.
        "observe_step": 3.0,
        "observe_floor": 0.15,
        # his message: attention moves with what it cost him, predictability
        # only when he did the thing she could have called, and the ledger
        # tips toward him because he gave and she has not.
        "message_attention": 6.0,
        # and what it puts in her head. Until this existed `attention_hers`
        # had no writer anywhere, so attachment, longing, guilt and having
        # anything worth withholding were all pinned at zero for the whole of
        # a character's life -- four derivations that could not leave the
        # floor whatever happened to her.
        "message_attention_hers": 5.0,
        # watching him is attending to him, at a smaller rate than looking is
        # worth as exposure: for a resident character this fires on every
        # window title
        "observe_attention_share": 0.5,
        # cost of loss is the integral and cannot be set: this is what it
        # gains per hour at full attention, and its own decay takes it back
        # down when she stops carrying him
        "cost_per_hour_at_full": 0.06,
        # what she takes back also comes off what he can show and what he can
        # call in advance, because both were made of the same material
        "private_threat_share": 0.5,
        "answered_predictability": 2.5,
        "message_reciprocity": 4.0,
        # and the only entry she controls. A resident character with no world
        # has almost no way to give, so without a feed here reciprocity can
        # only ever run against her, and a ledger that moves one way is not a
        # ledger. A task done for him is the feed.
        "gave_reciprocity": 7.0,
        # The ledger's unit is unanswered reach, not volume. A message that
        # goes this long without an answer is charged once, in whichever
        # direction it ran: he writes into her silence and it runs against her,
        # she writes into his and it runs the other way, which is what
        # resentment is made of.
        "owed_hours": 6.0,
        "unanswered_reciprocity": 2.0,
        # her one currency in this premise: she saw a thing and did not raise
        # it, and the discretion held for the whole time it was hot
        "held_back_reciprocity": 1.5,
        # and his: he told her a thing she could have read anyway. It costs him
        # nothing informationally, because she can see the screen, and
        # everything socially, because he is handing over what she would
        # otherwise have had to take.
        "told_anyway_reciprocity": 3.0,
        # How well she can call him only ever rose -- an answered question
        # added 2.5 and nothing anywhere subtracted -- so it reached its
        # ceiling in three days and being frightened of him, which is the
        # threat times how little she can call him, became arithmetically
        # impossible. Prediction error is the event that lowers it. Above
        # `sure_from` a small thing bounces off and does nothing at all;
        # certainty has no partial position to retreat to, so a charge over
        # `shock_from` takes it down in one step instead.
        "sure_from": 85.0,
        "shock_from": 55.0,
        "shock_predictability": 30.0,
        "error_predictability": 0.25,
        # and a discovery about HER that big is evidence he will use what he
        # holds: it writes the threat with a floor under it, which decay will
        # not go below, and puts him back outside
        "demonstrated_threat": 20.0,
        # A thing she told him that the record did not already hold is a
        # disclosure, and it is what stops closeness falling on `kept_private`
        # alone. Measured on her own words: how many of them her own record
        # does not already contain.
        "disclose_min_words": 8,
        "disclose_looks_back": 200,
        "disclose_min_share": 0.5,
        # and something large enough going across at once closes the act
        "close_act_weight": 0.9
    },

    "state": {
        # the state model is called only when something happened (a message,
        # a digest, an event at or above min_event_salience, waking, a note,
        # a snoop); quiet ticks decay deterministically. llm_on_quiet_ticks
        # restores the old every-tick behavior.
        "llm_on_quiet_ticks": False,
        # where a feeling comes from (State.sources): an open rupture or a
        # live withholding aims it at him, a person's sentiment at that
        # person. Friend exchanges get "not at you"; nothing else invents one.
        "sources": {"min_level": 30, "sentiment_from": 35},
        "min_event_salience": 3,
        # a delta toward a crowded end of a gauge is scaled down (mood 85 is
        # hard to raise, easy to dent); relationship meters may move at most
        # this much per person per meter per day, in either direction net
        "diminishing_returns": True,
        "relationship_daily_budget": 8,
        # mechanical world terms, per hour, applied in decay() before any model:
        "world": {
            "enabled": True,
            # weather: physical_comfort is pulled toward a target that falls
            # comfort_per_degree_* below 60 for each degree past these
            # feels-like thresholds (halved indoors)
            "comfort_hot_from": 27,
            "comfort_per_degree_hot": 3.0,
            "comfort_cold_from": 10,
            "comfort_per_degree_cold": 2.0,
            "comfort_pull_per_hour": 6,
            # sleep restores energy; awake past late_from spends it
            "sleep_energy_per_hour": 7,
            "late_from": "23:30",
            "late_energy_per_hour": 4,
            # block kinds from keywords: dull (class, homework, commute, chores) / social (friends, out)
            "boredom_dull_per_hour": 4,
            "boredom_social_per_hour": 6,
            "dull_keywords": ["class", "homework", "worksheet", "commute", "train", "cleaning", "chores", "study", "cram"],
            # the names on her roster are added at runtime (App.world_terms)
            "social_keywords": ["friends", "group", "karaoke", "festival", "cafe", "purikura"],
            # an exam within exam_days pulls anxiety up toward a floor that rises as it nears
            "exam_days": 4,
            "exam_anxiety_floor": 62,
            "exam_anxiety_per_hour": 3,
            # read and ignored (after impulse.read_ignored_minutes)
            # curiosity about him (state.gauges.curiosity)
            "curiosity_silent_per_hour": 4,
            "curiosity_busy_ignored_per_hour": 6,
            "attention_curiosity_release": 15,
            "ignored_craving_per_hour": 4,
            "ignored_anxiety_per_hour": 2,
            # his message being read releases some craving before the model reads its tone
            "attention_craving_release": 5,
            # What his silence and his arrival do to how much she has in her.
            # Both 0 for a character whose energy comes from sleep and food, so
            # the terms do nothing at all for her; set for a character who has
            # no other supply. Contact is the only thing that puts anything
            # back, which is what makes an unanswered day cost her something
            # visible rather than something she only says. The gauge's own
            # drift toward its resting value is the floor, so this cannot empty
            # her and leave her there.
            "energy_alone_per_hour": 0.0,
            "energy_alone_floor": 10.0,
            "attention_energy_release": 0.0,
            # his attention cools jealousy, mechanically. It no longer warms
            # affection: that is computed now (state.affection_from), and a
            # flat bump per message was the whole reason it could only rise.
            "attention_jealousy_release": 12,
            # being left on read stops being only an ache and starts being a
            # coldness; slow, capped, and it comes off faster than it went on
            "tension_ignored_after_minutes": 90,
            "tension_ignored_per_hour": 3.5,
            "tension_ignored_cap": 55,
            "attention_tension_release": 6,
            "attention_relief_bump": 14.0,
            "attention_relief_soft_cap": 70
        },
        # gauges are 0-100. decay_per_hour drifts each gauge toward its baseline.
        # Every gauge declares what sort of thing it is. This is not
        # bookkeeping: `mood` used to sit here as a peer of its own causes and
        # be written by the same call that wrote them, which is why across 112
        # recorded states it ran from 50 to 84 -- twenty-nine points above its
        # baseline and never more than five below. She could not have a bad day
        # unless she was ill, and `state.py`'s `mood < 30` branch had never once
        # executed. See PROJECT 16.1.
        #
        #   kind    : emotion (has an object, fades in hours, feeds mood)
        #             drive   (appetitive, wants something, only weakly feeds mood)
        #             body    (physical, feeds mood)
        #             derived (computed from the others; the model may not write it)
        #   valence : -1 bad, 0 neither, +1 good
        #   arousal : +1 activating, 0 neutral, -1 deactivating
        #
        # The emotion set must span the valence x arousal grid. An empty
        # quadrant is not a gap in the data, it is a feeling the character
        # cannot have: the whole low-arousal-negative corner was empty, which
        # is the mechanical reason nothing could put her mood down. `/gauges`
        # prints the grid and names any empty cell.
        "gauges": {
            "energy": {"baseline": 60, "decay_per_hour": 4, "kind": "body", "valence": 0, "arousal": 1},
            # mood is computed (state._derive_mood) and refused at the write
            # site if a model tries to move it anyway
            "mood": {"baseline": 55, "decay_per_hour": 4, "kind": "derived", "valence": 1, "arousal": 0, "model_may_move": False},
            "anxiety": {"baseline": 40, "decay_per_hour": 4, "kind": "emotion", "valence": -1, "arousal": 1},
            # anger: there was none, in a girl whose own sheet gives her a
            # temper for injustice under the manners. It is also what makes a
            # rupture a rupture rather than a sulk, and what puts something felt
            # behind a relationship's `tension`. Fades fast; she does not hold
            # onto it, she swallows it and it comes out as something else.
            "anger": {
                "baseline": 8, "decay_per_hour": 7, "kind": "emotion", "valence": -1, "arousal": 1,
                "tells": "a real temper under the manners, and mostly about unfairness rather than about him -- "
                         "somebody talked over, a rule applied to her and not to others, being made to look stupid. "
                         "She almost never shows it, so raise it for the thing that happened and expect it to come "
                         "out sideways",
                "tags": [[45, "angry about something, and holding it in"], [25, "irritated under it"]]
            },
            # sadness: the deactivating one, and not loneliness. Loneliness is
            # appetitive and drives her toward the phone; this drives her away
            # from everything. A goal that failed used to charge a belief, write
            # a memory and produce no feeling at all. Slow to lift.
            "sadness": {
                "baseline": 12, "decay_per_hour": 2, "kind": "emotion", "valence": -1, "arousal": -1,
                "tells": "the flat kind, and not loneliness: something was lost, something she wanted did not "
                         "happen, somebody was unkind. Loneliness wants the phone; this wants nothing",
                "tags": [[45, "sad in a way that has gone quiet rather than loud"], [28, "a bit down and not saying why"]]
            },
            # shame: not guilt. Guilt is "I did a bad thing" and drives repair,
            # which is already wired to make_up and the impulse. Shame is "I am
            # a bad thing" and drives hiding, which nothing could produce. For
            # this girl it is the master emotion -- the fear of being thought
            # weird, going to pieces when somebody sees her properly.
            "shame": {
                "baseline": 5, "decay_per_hour": 3, "kind": "emotion", "valence": -1, "arousal": -1,
                "tells": "not guilt. Guilt is having done a bad thing and wanting to fix it. This is having been "
                         "seen -- caught out, laughed at, the accent slipping in front of people, somebody reading "
                         "her properly -- and wanting to not exist for a while",
                "tags": [[45, "mortified about something and wants to not be looked at"], [25, "small about something"]]
            },
            # pride: everything good she could feel was either about him
            # (affection) or generic (mood). Nothing registered "I did that", so
            # the goals system only had a downside.
            "pride": {
                "baseline": 15, "decay_per_hour": 5, "kind": "emotion", "valence": 1, "arousal": 1,
                "tells": "something of hers came off: she said the thing, she was asked along, she got the mark, "
                         "somebody copied her. She would not say it out loud",
                "tags": [[60, "quietly pleased about it and would die before saying so"]]
            },
            # relief: the good/deactivating corner, which the grid check found
            # empty. Relief was only ever modelled as the absence of anxiety --
            # a _settle on a bad gauge and nothing positive produced -- so a
            # threat passing felt like nothing rather than like something.
            # Fades fast: it is the shortest-lived thing she feels.
            # longing: what attachment feels like at a distance. Written by
            # code (sentiment.longing) from how attached she is and how long he
            # has been gone, so the model is not shown it and cannot move it.
            "longing": {
                "baseline": 6, "decay_per_hour": 5, "kind": "emotion", "valence": -1, "arousal": 0,
                "model_may_move": False, "owner": "affection",
                "tags": [[55, "missing him in a way that is taking up room"], [30, "missing him"]]
            },
            # belonging: how held she is by the circle, which is the
            # counterweight to him. Code owns it (sentiment.belonging) from her
            # standing with them and how recently they had her, so the model is
            # not shown it and cannot move it. High = held.
            "belonging": {
                "baseline": 45, "decay_per_hour": 4, "kind": "drive", "valence": 1, "arousal": -1,
                "model_may_move": False,
                "tags": [[62, "solid with the group at the moment"], [22, "on the outside of them lately, and it is sitting there"]]
            },
            # fondness: warm toward the people of her own circle, one at a
            # time. NOT belonging, which is her standing in the group -- how
            # held she is, whether they could leave her out -- and is a drive
            # that wants something. This is the pleasant residue of having
            # been with one of them: they kept what they said they would, a
            # thing that was wrong between them got sorted, she told one of
            # them something real, an ordinary afternoon with them was good.
            # It occupies the good/neutral cell of the grid for a character
            # who has a circle and no chat with him, which is otherwise empty
            # for her: warmth toward him was the only thing in it, and a girl
            # with friends can feel fondness for them.
            #
            # Owned by the section that already keeps what she holds with
            # them (`cast_bond`, tomoe/cast_psych.py), so a character with no
            # circle does not have the gauge at all rather than resting at a
            # constant. Code moves it; the model is not shown it.
            "fondness": {
                "baseline": 30, "decay_per_hour": 3, "kind": "emotion", "valence": 1, "arousal": 0,
                "model_may_move": False, "owner": "cast_bond",
                "tags": [[60, "warm toward her own people at the moment: whatever else the day was, one of them was good to her"],
                         [42, "fond of them, and it is sitting somewhere pleasant"],
                         [-16, "flat toward the people she is closest to; it is not a row, there is just nothing warm there today"]]
            },
            # stress: not a feeling and it does not behave like one. Code owns
            # it (sim/stress.py) as an integrator over her load: fast up, slow
            # down, and only as far down as the load allows. `body` rather than
            # `emotion` because it is a state of the whole animal, and because
            # the emotion grid should not have to make room for something that
            # is not an emotion.
            "stress": {
                "baseline": 12, "decay_per_hour": 0, "kind": "body", "valence": -1, "arousal": 1,
                "model_may_move": False,
                "tags": [[70, "wound up, running on nothing, everything is a bit much"],
                         [45, "carrying more than is showing"]]
            },
            "relief": {
                "baseline": 8, "decay_per_hour": 9, "kind": "emotion", "valence": 1, "arousal": -1,
                "tells": "a thing she was braced for did not happen, or the waiting ended. Code warms it when he "
                         "answers and when the record disproves something she had talked herself into, so raise it "
                         "only for a relief of your own",
                "tags": [[45, "relieved, like something braced for did not happen"]]
            },
            "loneliness": {"baseline": 35, "decay_per_hour": 2, "kind": "drive", "valence": -1, "arousal": 0},
            "boredom": {"baseline": 30, "decay_per_hour": 6, "kind": "drive", "valence": -1, "arousal": -1},
            "validation_craving": {"baseline": 50, "decay_per_hour": 3, "kind": "drive", "valence": -1, "arousal": 1},
            "physical_comfort": {"baseline": 60, "decay_per_hour": 6, "kind": "body", "valence": 1, "arousal": 0},
            # unwell: how rotten her body feels. Not the room being
            # uncomfortable (physical_comfort, owned by body.py and driven by
            # the weather and the air-con) and not sadness -- you can be ill
            # in a pleasant room and it is not a feeling about anything. This
            # is what health.py moves, and mood follows it as a body term:
            # health affects mood and needed its own carrier to do it through.
            "unwell": {
                "baseline": 4, "decay_per_hour": 3, "kind": "body", "valence": -1, "arousal": -1,
                "model_may_move": False,
                "tags": [[45, "physically rotten, wants to lie down"], [25, "a bit off physically"]]
            },
            # things unsaid: fills with what the day leaves in her (salient
            # events, being read and ignored, what she saw and did not send);
            # writing in her diary empties it
            "unsaid": {"baseline": 25, "decay_per_hour": 2, "kind": "drive", "valence": -1, "arousal": 1},
            # hunger is mechanical only (needs.*): no drift, no model deltas
            "hunger": {"baseline": 30, "decay_per_hour": 0, "kind": "body", "valence": -1, "arousal": 0, "model_may_move": False},
            # curiosity about him: what he is doing, who he is talking to.
            # Rises with his silence and with his PC being busy while her
            # message sits read and unanswered; a look at the app relieves
            # it; his message relieves it; the state model may feed it
            # (a digest that stings, a jealous pang)
            "curiosity": {"baseline": 40, "decay_per_hour": 3, "kind": "drive", "valence": 0, "arousal": 1},
            # jealousy: needled about who he is with. Rises when the app shows
            # him busy with other people or his likes/follows show other girls
            # (the state model moves it, like the curiosity pang); his
            # attention to her relieves it; fades fast on its own.
            "jealousy": {"baseline": 15, "decay_per_hour": 6, "kind": "emotion", "valence": -1, "arousal": 1},
            # affection: warm toward him, wants to be close now. The positive
            # approach drive (most others are deficits). His message warms her
            # a little mechanically; a good exchange or a sweet moment more.
            # affection: warm toward him, wants to be close now. Computed
            # from its causes (state.affection_from) and refused at the
            # write site, so decay_per_hour is 0 -- the derivation owns it.
            # It stays an emotion rather than becoming kind "derived":
            # `affect()` skips derived gauges, so marking it that way would
            # have quietly taken the largest positive term out of the sum
            # mood is computed from, and emptied the good/neutral cell of
            # the grid. Code-owned and still felt is what longing and
            # belonging already are.
            "fatigue": {"baseline": 5, "decay_per_hour": 0, "kind": "body", "valence": -1, "arousal": -1, "model_may_move": False, "tells": "what the day has taken out of her body: walking in heat, a packed train, hours on her feet; recovers only lying down, in the bath, asleep. Code moves it; you never do.", "tags": [[70, "properly exhausted; the phone is heavy and the replies come out short and misspelt"], [45, "legs heavy from the day, wiped, would rather lie down than type"]]},
            "affection": {"baseline": 45, "decay_per_hour": 0, "kind": "emotion", "valence": 1, "arousal": 0,
                          "owner": "affection",
                          "tags": [[70, "feeling warm and close to him, wants to reach out"], [58, "soft toward him right now"], [-30, "gone off him: cool, short, not interested in being close right now"], [-15, "cannot stand him at the moment; everything he says grates, and it is not hidden"]],
                          "model_may_move": False},
            # guilt: she was short with him, went cold, or left him on read
            # and it sits with her. The state model raises it; making up or
            # a warm message settles it; fades on its own.
            "guilt": {"baseline": 10, "decay_per_hour": 4, "kind": "emotion", "valence": -1, "arousal": 0},
            # awkwardness: she knows something about him she cannot unknow and
            # has to talk to him anyway. Not jealousy (who else has him) and not
            # anxiety (how she stands): the squirm of holding a thing she is not
            # going to raise. Fades in hours; the knowing behind it does not.
            "awkwardness": {
                "baseline": 5, "decay_per_hour": 3.5, "kind": "emotion", "valence": -1, "arousal": 1,
                # the ick owns it (one owner per gauge, 16.1). The old
                # hand-written delta schema left it out while the gauge list
                # above it did not, which is the drift the generated schema
                # exists to stop -- so make the intent explicit.
                "model_may_move": False,
                "tags": [[40, "squirming about something that is not going to be brought up"]]
            },
            # the grid's "neither" row was empty: a feeling with no valence of
            # its own. Code-owned: the ick (prediction error) and foresight (a
            # reply she had written off, or far outside the window) warm it;
            # it is gone within the hour. Read by the register, the mood tags
            # and the arousal axis.
            "surprise": {
                "baseline": 5, "decay_per_hour": 25.0, "kind": "emotion", "valence": 0, "arousal": 1,
                "model_may_move": False,
                "tags": [[35, "caught off guard by something and still recalibrating; a beat of 'wait' before anything else"]]
            }
        },

        # Mood is a slow, unattributed residue of the emotion layer plus her
        # body, and only weakly of the drives -- being bored or hungry should
        # not set a mood the way being ashamed does. Each gauge contributes
        # `valence * (how far it is from its own rest) * its kind's points`, so
        # a gauge at rest contributes nothing and an unusually calm afternoon
        # lifts her. Mood then moves toward that at `inertia_per_hour`, which is
        # slower than any emotion fades: that lag is what makes it a mood and
        # not a readout.
        "mood_from": {
            "emotion_points": 14.0,
            "body_points": 9.0,
            "drive_points": 5.0,
            "max_swing": 45.0,
            "inertia_per_hour": 3.0,
            # the same sum on the arousal axis, for naming the state
            "arousal_points": 12.0,
            "arousal_swing": 45.0
        },
        # What she feels toward him, computed rather than written.
        #
        # Every mechanical write used to be upward: +6 on any message he sent,
        # before the model read the tone, and +10 on a mend; decay only ever
        # returned it to its baseline. So a cold message warmed her exactly as
        # much as a kind one, and across 72 states it ran 45 to 100 and never
        # once went under 45. That is the shape mood failed in.
        #
        # None of the terms are new. Attachment is what he is to her over
        # weeks; closeness is what the record actually supports (derive.py
        # holds it honest); relief is him being here right now; and tension and
        # resentment are the two ways she goes off him, one in hours and one in
        # weeks. Silence therefore cools her by itself, which is the thing that
        # was impossible.
        "affection_from": {
            "enabled": True,
            # an emotion, so hours -- not mood's most-of-a-day
            "inertia_per_hour": 6.0,
            # how far it may move when something actually happens (his
            # message, a state call) rather than waiting for the next decay
            "on_event_hours": 0.5,
            "attachment": 0.45,
            "attachment_rest": 40.0,
            "closeness": 0.30,
            "closeness_rest": 50.0,
            "relief": 0.55,
            "tension": -0.40,
            "tension_rest": 15.0,
            "resentment": -0.55,
            # while a break stands, on top of what it did to tension and guilt
            "rupture_open": -12.0
        },
        # The gauge appraisal (`sim/appraisal_gauge.py`): System One scores the
        # 16 dimensions over the live tick context and code maps the levels
        # through the table below into the integer `deltas` `apply` takes. The
        # switch is `typesafe.uses.state_appraisal`; this block is only the
        # numbers, so an off switch leaves an inert table and there is no
        # second enable. `weights[dimension][gauge]` is signed points per unit
        # of the normalised level; `thresholds` overrides a dimension's floor
        # where the 0-4 scale or a many-option choice spreads probability.
        "appraisal": {
            # one dimension may contribute at most this many points to one
            # gauge, before the sum and apply's own max_delta_per_update
            "max_points_per_dimension": 4,
            # how_activating scales the dimensions that carry bad news: min at
            # a flat event, max at a jolting one
            "gain_from_arousal": {"min": 0.6, "max": 1.2},
            "weights": {
                "how_good_or_bad": {"relief": 3, "sadness": -2, "anxiety": -2},
                "unfairness": {"anger": 3},
                "wanted_and_blocked": {"sadness": 2},
                "exposure": {"shame": 2},
                "achievement": {"pride": 2},
                "uncertainty": {"anxiety": 2, "curiosity": 2, "unsaid": 1},
                "holding_back": {"unsaid": 2},
                "warmth_from_him": {"relief": 3, "validation_craving": -2, "loneliness": -2},
                "attention_from_him": {"validation_craving": -2, "loneliness": -1},
                "who_else_has_him": {"jealousy": 2, "curiosity": 2},
                "her_fault": {"guilt": 2}
            },
            "thresholds": {
                # section 2's choices with more than two options, and the
                # five-option one especially: the probability is spread, so
                # the floor comes down off the universal 0.6
                "is_this_new": 0.5,
                "whose_doing": 0.5,
                "holding_back": 0.5,
                "attention_from_him": 0.5
            }
        },
        # gauges the state model may not move; the world terms own them
        # what counts as something happening rather than a day going by. One
        # number, because two readers were carrying their own copy of it: the
        # mechanical fill of `unsaid` and, since 2026-09-07, how much of a day
        # a character with nobody to say things to has behind her when the
        # diary asks whether there is anything to write (`sim/diary.py`).
        "salient_from": 3,
        # mechanical fill of `unsaid`: per salience point of an event at or
        # above the line above, per hour read-and-ignored, per X scroll at the
        # same salience
        "unsaid_per_salience": 2,
        "unsaid_ignored_per_hour": 3,
        "unsaid_social": 4,
        # loneliness climbs on its own while he is silent, capped per hour,
        # weighted by how much of him she expects at this hour (world usual_w)
        "loneliness_per_silent_hour": 1.5,
        # true: no drift to baseline for loneliness while he has been silent
        # over 2 h, so the climb above accumulates (bench overlays only so far)
        "loneliness_hold_when_silent": False,
        # minutes the state call's `reasons` for a notable update (a feeling
        # gauge moved by felt_carry_min_delta or more) stays in her mood line
        # as text; 0 = off (bench only so far, tk-z1q 10-25)
        "felt_carry_minutes": 0,
        "felt_carry_min_delta": 5,
        # true: a felt carry raised by sadness or anxiety (hurt, worry) stays
        # in her mood line past felt_carry_minutes until resolved (a later
        # state call lowers that gauge by felt_carry_min_delta or more, or his
        # message is read as warm or about her), at most
        # felt_carry_hold_max_minutes. Needs felt_carry_minutes on.
        "felt_carry_hold_until_resolved": False,
        "felt_carry_hold_max_minutes": 1440,
        # held5: "max" (default) keeps an update as the carry when ONE feeling
        # gauge moved by felt_carry_min_delta; "sum" when the summed |delta|
        # over the feeling gauges + validation_craving + unsaid reaches
        # felt_carry_min_sum (small moves spread over many gauges count).
        # With "sum" and the hold on, an update is held when the summed
        # positive deltas of sadness, anxiety, anger, loneliness,
        # validation_craving, unsaid reach felt_carry_hold_min_sum; a later
        # update whose net push on those six is <= -felt_carry_hold_min_sum
        # resolves it; consecutive held updates join into one thread.
        "felt_carry_rule": "max",
        "felt_carry_min_sum": 10,
        "felt_carry_hold_min_sum": 10,
        # held6: true = while a carry is held, her mood line also carries
        # the line her bundle writes for how that feeling shows in her
        # (fills file key `felt_carry_show`: sadness, anxiety, anger).
        "felt_carry_show": False,
        # held7: true = a held carry clears only when the state call says the
        # cause is settled (its `carry_resolved` field, given the held text
        # as input) or at felt_carry_hold_max_minutes. The relief rule, the
        # gauge-drop rule and "his message was warm" no longer clear it.
        # Needs felt_carry_hold_until_resolved on.
        "felt_carry_cause_held": False,
        # minutes after her last line with no answer from him at which the
        # state update runs once with a silence event; re-armed by his next
        # message. 0 = off.
        "silence_call_minutes": 0,
        # who is with her owns part of loneliness: the climb is scaled by
        # (1 - company) and company settles it toward rest. `talk_relief`
        # is the settle when an exchange she took part in ends, times the
        # attachment to that person / 100. Family at a discount: her fear
        # is being alone at break, not at dinner.
        "company": {
            "enabled": True,
            "family_factor": 0.6,
            "loneliness_settle_per_hour": 6.0,
            "talk_relief": 5.0
        },
        # habituation: with nothing new from him, a model delta pushing a
        # gauge the same way as last tick is scaled by repeat_factor per
        # repeat (0.55, 0.30, 0.17 ...). A standing situation is charged
        # once; anger sat at 80 for eleven hours on 2026-08-26 because the
        # state model re-charged "he left" on every tick. reasons_shown is
        # how many of its own last reasons lines the model is shown.
        "habituation": {
            "enabled": True,
            "repeat_factor": 0.55,
            "max_repeats": 5,
            "reasons_shown": 3
        },
        "max_delta_per_update": 15,
        # A gauge that has never once crossed its own baseline is either
        # one-directional by design or broken, and the wiring report cannot
        # tell which -- so it only says so when there was room to go the
        # other way. guilt rests at 10 and of course has never been below
        # it; affection rests at 45 and has never been below it either,
        # which is the same shape as the failure mood had.
        "one_way_warn_from": 20,
        # Misattribution: her body's bad day contaminating how she reads his.
        # People do this reliably and she had no way to -- the state model read
        # his message knowing nothing about her blood sugar. Only the bad
        # direction counts: being well rested does not make her generous, it
        # just stops the distortion.
        # A gauge at its end is an event, not a level (sim/discharge.py):
        # at `at` (or under `floor`) the gauge resets to `reset_to` and the
        # rule's behaviour happens -- say (a forced message with `hint` as
        # the whole intent), look, spiral, or act (`text` as an event the
        # next scene must reflect, `side` on other gauges, `relieve` a
        # stress release). One firing per gauge per cooldown, max_per_day
        # in all. Reset is to a level, not to rest.
        "discharge": {
            "enabled": True,
            "cooldown_hours": 4,
            "max_per_day": 4,
            "keep": 60,
            "rules": [
                    {
                                "gauge": "anger",
                                "at": 92,
                                "reset_to": 62,
                                "action": "say",
                                "cooldown_hours": 4,
                                "hint": "SHE HAS HIT THE END OF IT: the anger comes out at him, sharp and unedited, one or two lines, and then she stops -- no softening, no explanation, nothing else in the message",
                                "text": "she threw the phone onto the bed and stood in the middle of her room breathing",
                                "side": {
                                            "unsaid": -15,
                                            "relief": 6
                                },
                                "relieve": ""
                    },
                    {
                                "gauge": "unsaid",
                                "at": 92,
                                "reset_to": 45,
                                "action": "say",
                                "cooldown_hours": 4,
                                "hint": "THE THING SHE HAS BEEN NOT SAYING COMES OUT, badly worded, because she cannot hold it another minute; it is not planned and it shows",
                                "text": "she wrote the whole thing out in the notes app, read it twice, and did not send it",
                                "side": {
                                            "relief": 8
                                },
                                "relieve": "diary"
                    },
                    {
                                "gauge": "loneliness",
                                "at": 93,
                                "reset_to": 58,
                                "action": "say",
                                "cooldown_hours": 5,
                                "hint": "she reaches out because she cannot stand it another minute, with no pretext at all, and it shows: short, a little naked, not clever",
                                "text": "she lay on the floor with the phone face-down and cried, not much, and felt stupid about it",
                                "side": {
                                            "sadness": 5,
                                            "relief": 4
                                },
                                "relieve": ""
                    },
                    {
                                "gauge": "sadness",
                                "at": 90,
                                "reset_to": 55,
                                "action": "act",
                                "cooldown_hours": 4,
                                "text": "she cried, properly, into the pillow, and came out of it emptier and a little lighter",
                                "side": {
                                            "relief": 10,
                                            "energy": -8
                                },
                                "relieve": "cried"
                    },
                    {
                                "gauge": "anxiety",
                                "at": 92,
                                "reset_to": 66,
                                "action": "spiral",
                                "cooldown_hours": 4,
                                "text": "her chest did the tight thing and she could not sit still; she paced the room and checked her phone four times",
                                "side": {
                                            "energy": -6
                                },
                                "relieve": ""
                    },
                    {
                                "gauge": "validation_craving",
                                "at": 92,
                                "reset_to": 50,
                                "action": "say",
                                "cooldown_hours": 5,
                                "hint": "she fishes: a half-message that exists to be noticed -- a 'nothing', a sigh in text, a thing left hanging -- and she knows exactly what she is doing",
                                "text": "she took four photos of nothing in particular and posted none of them",
                                "side": {
                                            "shame": 4
                                },
                                "relieve": ""
                    },
                    {
                                "gauge": "boredom",
                                "at": 92,
                                "reset_to": 40,
                                "action": "look",
                                "cooldown_hours": 3,
                                "text": "she rolled over and opened every app on her phone twice",
                                "side": {},
                                "relieve": ""
                    },
                    {
                                "gauge": "stress",
                                "at": 92,
                                "reset_to": 60,
                                "action": "act",
                                "cooldown_hours": 6,
                                "text": "she gave up on the day: lay down, phone on silent, did nothing for an hour and hated it",
                                "side": {
                                            "energy": -10,
                                            "relief": 6
                                },
                                "relieve": "gave_up"
                    },
                    {
                                "gauge": "shame",
                                "at": 90,
                                "reset_to": 55,
                                "action": "act",
                                "cooldown_hours": 4,
                                "text": "she went small: deleted the message she was drafting, turned the phone over, did not want to be looked at by anybody",
                                "side": {
                                            "unsaid": 8
                                },
                                "relieve": ""
                    },
                    {
                                "gauge": "jealousy",
                                "at": 90,
                                "reset_to": 50,
                                "action": "look",
                                "cooldown_hours": 4,
                                "text": "she went through the account again looking for the thing she was afraid of and did not find it, which did not help",
                                "side": {
                                            "anxiety": 5
                                },
                                "relieve": ""
                    }
        ]
        },
        "body_noise": {
            "enabled": True,
            "weights": {"hunger": 0.45, "energy": -0.45, "unwell": 0.5, "physical_comfort": -0.4},
            "report_from": 0.25,
            # the reverse: a wound-up head with the body near rest reads
            # itself as the body (a stomach, "coming down with something")
            "reverse_body_under": 0.10,
            "reverse_anxiety_over": 30,
            "reverse_stress_over": 60,
            # the correction: noise falling from past report_from to under
            # clear_below takes `relief` x (the noise it fell from) of each
            # relief gauge's height above rest off, once per cooldown, and
            # the next state call is told
            "clear_below": 0.12,
            "relief": 0.5,
            "relief_gauges": ["anxiety", "anger", "sadness"],
            "relief_cooldown_hours": 4
        },
        # Two feelings both up that do not cancel, named for the prompt (mood
        # tags) and the reports. `at` is [threshold for a, threshold for b].
        # State.blends(); at most two shown.
        "blends": [
            {"a": "longing", "b": "anger", "at": [40, 50], "text": "wanting him and furious with him at the same time, and neither cancels the other"},
            {"a": "affection", "b": "anger", "at": [58, 50], "text": "fond of him and angry with him at once; it comes out as sharpness she then half takes back"},
            {"a": "relief", "b": "sadness", "at": [45, 45], "text": "bittersweet: the thing is over, she is glad, and it still hurts"},
            {"a": "pride", "b": "shame", "at": [45, 40], "text": "proud of a thing and embarrassed about the same thing"},
            {"a": "jealousy", "b": "guilt", "at": [40, 40], "text": "jealous, and ashamed of being jealous"},
            {"a": "curiosity", "b": "anxiety", "at": [50, 55], "text": "wants to know and is afraid of the answer"},
            {"a": "belonging", "b": "loneliness", "at": [60, 60], "text": "surrounded and still lonely: the people there are not the person missing"}
        ],
        # How long his silence feels, as against how long it is. Prompt-facing
        # only: the impulse keeps the true figure, because anxiety and craving
        # are already weights in it and feeding it a number those same gauges
        # inflated would count them twice.
        "felt_time": {
            "enabled": True,
            "weights": {"loneliness": 0.45, "validation_craving": 0.35, "anxiety": 0.25, "boredom": 0.20},
            "min_factor": 0.6,
            "max_factor": 2.2
        }
    },

    # An ick is not a category, it is prediction error against her picture of
    # him (sim/ick.py, sim/model_of_him.py). A discovery costs her exactly what
    # it takes away from a belief she is invested in, so nothing is listed
    # anywhere as shocking, and the same discovery stops costing her anything
    # once the belief has been rewritten to accommodate it.
    "ick": {
        "enabled": True,
        # how much a belief being about her own place with him adds to the cost
        "about_her_weight": 0.6,
        # private in itself (bodily, ashamed, money lost) carries weight even
        # when it fits her picture of him perfectly
        "intimate_weight": 0.5,
        # what counts as a 100: not the theoretical maximum (two beliefs at full
        # strain, which nothing real reaches) but one belief she has a lot riding
        # on, badly contradicted, and private with it. Scaling against the
        # maximum put the worst thing in his real data at 24 of 100.
        "charge_ceiling": 3.2,
        # strain put on the belief per point the model scored, out of 5
        "strain_per_point": 22,
        # habituation: 1/(1+seen)^power. At 0.85 the second time is 0.55 of the
        # first, the third 0.39, the fifth 0.24.
        # the girls in her class never find out and she never tells them, but
        # she runs everything past them in her head. A thing they would have
        # something to say about costs her more than the same thing in private.
        "circle_weight": 0.5,
        # and it only bites to the extent she is currently in the grip of what
        # people think
        "circle_anxiety_ref": 40,
        "novelty_power": 0.85,
        # habituation damps, it does not zero. Her seeded kinds carry counts in
        # the tens, which alone would take a genuinely belief-breaking discovery
        # down to three percent and make her unshockable about anything she has
        # ever seen before.
        "novelty_floor": 0.15,
        # how many of the sorts of thing she has already run into are shown to
        # the scoring call, so it can say which one this is instead of coining a
        # fresh label for the same thing
        "kinds_in_prompt": 24,
        # a loose net under the model's own matching, not the matcher itself
        "kind_jaccard": 0.5,
        "max_kinds": 80,
        "max_chars": 2000,
        # a message too short to contain anything is not assessed
        "message_min_chars": 25,
        # the app fires constantly; do not pay for a call every look
        "digest_min_gap_minutes": 90,
        "cast_in_prompt": 6,
        # what she already knows about him, so a thing she has known for months
        # is not scored as a discovery
        "known_shown": 40,
        # how wound up she was when she found it; only unease adds
        "anxiety_weight": 0.5,
        "jealousy_weight": 0.6,
        "loneliness_weight": 0.3,
        "tired_below": 30,
        "tired_bonus": 0.1,
        "max_state_multiplier": 1.6,
        # under this the belief still takes the strain but nothing happens to her
        "min_charge": 8,
        "awkwardness_per_charge": 0.9,
        "surprise_per_charge": 0.35,
        "surprise_soft_cap": 80,
        "awkwardness_soft_cap": 85,
        "unsaid_per_charge": 0.35,
        "unsaid_soft_cap": 90,
        "event_salience": 3,
        # the knowing outlives the squirm: the charge halves in this many days
        "half_life_days": 9,
        "carry_floor": 12,
        "in_prompt": 3,
        "max_items": 80,
        # cooled off AND met this often: it is just how he is, and she can say so
        # Past this many sightings a sort of thing is not a discovery any
        # more, it is a fact about him: the multiplier goes to zero and it
        # stops being assessed. At the flat floor of 0.15 a kind she had met
        # fifty times still charged eight points, and eight points of
        # awkwardness a day is a standing tax nothing earned.
        "settled_after": 12,
        # ...except where the thing is about HER. The tenth must cost what the
        # first did, and this is the top of the 0-5 scale the scoring role
        # writes on the belief it touches.
        "about_her_top": 4.5,
        # How settled she is with him: the share of what she has met over this
        # many days whose sort she had already run into. At 1.0 nothing he does
        # is news; at 0.0 every look is new. Where the window holds fewer than
        # `settled_min` it reads the last `settled_window` of the record
        # instead, because a share of one is not a reading.
        "settled_days": 1.0,
        "settled_min": 3,
        "settled_window": 12,
        "teasable_after_seen": 2,
        "teasable_in_prompt": 3,
        # a thread this close to something charged is never what she raises
        "bar_jaccard": 0.35,
        "source_words": {
            "snoop": "she went through his things on the app; he does not know she looked, and she could not ask about it without admitting that",
            "digest": "the app on her phone showed her while she was checking on him; he gave her that app, so she is allowed to have seen it",
            "x": "she saw it on X, on his own account, where anyone could have seen it",
            "photo": "he sent it to her himself",
            "lookup": "he mentioned it and she quietly looked up what it actually was; he was not hiding it and she could admit she looked",
            "told": "he told her himself, in a message, unprompted",
            "seen": "it was on his screen in front of her; she lives on his machine and he knows it, so there is nothing to hide about having seen it"
        }
    },

    # Her picture of him: what she has decided he is, seeded from
    # character.beliefs_file and rewritten as it fails (sim/model_of_him.py).
    "beliefs": {
        "enabled": True,
        "in_prompt": 8,
        # a contradiction she found a reason for fades; only repeated pressure
        # gets a belief rewritten
        "strain_half_life_days": 11,
        # past this it shows in her prompt as a thing she is holding together
        "straining_from": 30,
        # what it takes to make her let a piece of it go: she defends what she
        # has most riding on, and what she has actual grounds for, longest
        "revise_base": 45,
        "revise_per_invested": 55,
        "revise_per_evidence": 25,
        # what a revision costs the belief
        # what being borne out gives a belief (per point of fit, out of 5)
        "evidence_per_fit": 12,
        "confidence_per_fit": 8,
        "strain_relieved_per_fit": 9,
        "confidence_lost": 20,
        "invested_lost": 12,
        "evidence_gained": 15,
        # Being at the top of the scale has to mean something rather than just
        # being where the number stopped. Past certain_from she is not weighing
        # the belief any more, and certainty does not erode: a real contradiction
        # takes the whole thing down at once instead of costing it 22 points.
        # Past graduate_from on evidence it is not a belief at all any more, it is
        # something she knows about him, so it moves into user_facts and stops
        # soaking up confirmations -- but it can still be shattered, because a
        # proven thing does not wear away either, it breaks.
        "certain_from": 92,
        "graduate_from": 85,
        # what counts as a real contradiction rather than a niggle. strain_per_point
        # is 22, so this is the model scoring 3 or worse out of 5.
        "shatter_min_strain": 12,
        "event_salience": 3,
        # a fresh belief set on a save that already has months of history would
        # have her shocked by things she has lived with since spring, so it is
        # settled against what she already knows, once, at seed
        "settle_on_seed": True,
        "settle_min_facts": 8,
        "settle_strain_scale": 2.5,
        # how many of her beliefs may come out of the settle visibly under
        # strain. The model will hand back a 3 or a 4 for every belief a real
        # person has ever fallen short of, and nine at once is not a girl four
        # months in, it is a crisis. Which ones is the model's call; how many is
        # not.
        "settle_max_straining": 3,
        "settle_max_revisions": 4,
        "settle_facts_shown": 60
    },

    # What she is trying to do (sim/goals.py). Her morning want was written
    # to kv every day and read by nothing, while every person in the cast had
    # a want the beat writer acted on.
    # Emotional contagion. His state reached her as message content and as
    # read receipts and never as a state, so there was no route by which his
    # being flat could make her flat -- and co-regulation is most of what being
    # with somebody consists of. The state model reads his mood off how he
    # wrote; code decides how much of it she takes, scaled by what he is to her
    # (sim/sentiment.py). She is never told it happened.
    "contagion": {
        "enabled": True,
        "strength": 9.0,
        # catching is stronger downward than up, which is the part of this the
        # research is clearest about
        "negative_bias": 1.35,
        "default_susceptibility": 0.5,
        # what he sounded like six hours ago is not what he is now
        "half_life_hours": 5.0,
        "forget_below": 0.2,
        "soft_cap": 88,
        # a positive weight means his being low RAISES it (anxiety, sadness);
        # a negative weight means his being low lowers it (mood is derived and
        # is not in here at all -- it follows these)
        # `affection` is deliberately not in here: how she feels toward him
        # is an appraisal of him, not a state she catches off him. Catching
        # is for affect.
        "valence_gauges": {"sadness": 1.0, "anxiety": 0.8},
        "arousal_gauges": {"energy": 0.7, "boredom": -0.4}
    },

    # What a person is to her, as against how she feels this afternoon
    # (sim/sentiment.py). Every emotion here is episodic and object-free and
    # every relationship meter is bookkeeping over the record; neither is a
    # durable felt orientation toward a named person, so `closeness 48` did no
    # felt work and she could be warm at 8pm and neutral at 8am with nothing
    # carried. Seeded once from the meters, then fed only by things that
    # carry a person.
    # Social comparison (tomoe/compare.py): code decides when (a peer in the
    # scene or just talked with, her craving / shame / anxiety over rest and
    # belonging under par, a daily cap, a cooldown), the `compare` role
    # decides what (who, dimension, direction, the thought, which self-belief
    # it lands on). Upward: envy toward that person, shame, craving, anxiety,
    # a strain on the belief. Downward: pride. The thought goes out through
    # the reflections channel.
    "compare": {
        "enabled": True,
        # Comparisons she actually MAKES in a day, not calls asked. The model
        # answers `fires: false` four times in five and this counted the
        # asking, so two refusals closed the day: over a fortnight the layer
        # was asked 20 times and fired 4. What bounds the spend is
        # `cooldown_hours`, which is charged whatever the answer was.
        "max_per_day": 2,
        "cooldown_hours": 3,
        "base_p": 0.12,
        "weights": {"validation_craving": 0.45, "shame": 0.35, "anxiety": 0.25},
        "belonging_weight": 0.3,
        "dimensions": ["looks", "body", "clothes", "being_behind", "dating", "popularity", "grades", "money", "family", "other"],
        "envy_gain": 14,
        "shame_gain": 10,
        "craving_gain": 8,
        "anxiety_gain": 5,
        "pride_gain": 8,
        "strain_gain": 12,
        "confirm_gain": 6,
        "soft_cap": 85,
        "keep": 80
    },
    "sentiment": {
        "enabled": True,
        "ceiling": 100.0,
        # weeks, not hours, and toward nothing rather than a baseline: what
        # somebody is to you goes if nothing keeps happening
        "half_life_days": {"attachment": 70, "resentment": 45, "respect": 90, "contempt": 60, "envy": 40},
        "seed_attachment_from_closeness": 0.9,
        "seed_resentment_from_tension": 0.7,
        # respect is earned. `standing` is how she is placed with somebody,
        # which is a different thing entirely -- seeded at 0.8 it had her
        # looking up to her own father, Kaito and Hinako on day one.
        "seed_respect_from_standing": 0.3,
        "log_from": 0.5,
        "prompt_from": 32,
        "max_in_prompt": 4,
        # longing: what attachment feels like at a distance. She is in a
        # relationship conducted across a great distance and had no gauge for
        # missing somebody -- `loneliness` is a deficit that wants any contact,
        # this is about one person and is not entirely unpleasant.
        "longing_needs_attachment": 20,
        "longing_full_hours": 16,
        "longing_scale": 85,
        "longing_per_hour": 9.0,
        # belonging: her standing with the circle times how recently they had
        # her. Family is not in it -- you belong to a family whether it is going
        # well or not, and her named fear is being left out at break.
        "family_roles": ["mother", "father", "sibling"],
        "belonging_half_life_hours": 20.0,
        "belonging_floor": 0.35,
        "belonging_per_hour": 7.0,
        # the zero-sum: what being on her phone with him costs her with them
        "phone_debt_enabled": True,
        "phone_debt_free": 4,
        "phone_debt_per_message": 0.6,
        "phone_debt_max": 4.0,
        # you catch the mood of somebody who matters to you, not a stranger's
        "contagion_floor": 0.15,
        # attachment reaches, resentment does not. Resentment is the only thing
        # in the system that can hold her back for weeks.
        "impulse_attachment": 10.0,
        "impulse_resentment": 16.0,
        "delay_resentment": 0.5,
        # what things that carry a person are worth
        "mend_attachment": 2.2,
        "mend_respect": 1.2,
        "scar_resentment": 3.4,
        "failed_bid_resentment": 1.6,
        "attention_attachment": 0.45,
        "compile_max_delta": 6.0
    },

    # Rupture and repair (sim/rupture.py). Before this a fight healed by the
    # passage of time -- guilt decayed at 4 an hour, tension drifted down, and
    # `intent` could return `make_up` with nothing behind it, so a day of
    # saying nothing repaired a row as well as an apology did and better than a
    # failed one. Nothing could be broken, so nothing could be earned.
    "rupture": {
        # At or above this severity, a break that settled WORSE rather than
        # mended puts him back outside her territory -- for a character who
        # has one (sim/primitives.py:expel). What makes being let in mean
        # anything is that it can be lost.
        "expel_severity": 4,
        "enabled": True,
        "max_kept": 60,
        # noticing one: a jump in the gauges that carry a break, in a tick that
        # had something said in it. A rupture is not a bad mood.
        "anger_weight": 1.0,
        "guilt_weight": 1.0,
        "shame_weight": 0.7,
        "sadness_weight": 0.6,
        "min_score": 9.0,
        "messages_shown": 10,
        "scars_shown": 5,
        "scars_in_prompt": 3,
        # what opening one does
        "tension_per_severity": 6.0,
        "guilt_per_severity": 7.0,
        "guilt_soft_cap": 75,
        # an old unmended thing makes the next one land harder
        "scar_scale_per": 0.15,
        "scar_scale_cap": 0.6,
        # Time does not repair: while one is open these are held off their
        # decay, so the day cannot quietly file it away. This is the single
        # most load-bearing setting here.
        "holds_gauges": ["guilt", "anger", "sadness"],
        "hold_decay_factor": 0.3,      # a held gauge decays at this fraction of its rate...
        "hold_floor": 25,              # ...toward baseline + this, never below it, until the rupture is settled or scarred
        # what mending one is worth. Closeness ends up ABOVE where it started:
        # a pair who have broken something and mended it are closer than a pair
        # who never broke anything, and that is the whole point of the object.
        "closeness_on_mend": 2.2,
        "tension_off_on_mend": 9.0,
        "guilt_off_on_mend": 12.0,
        "relief_on_mend": 28.0,
        "relief_soft_cap": 80,
        # no affection line here: mending raises closeness and relief and
        # takes tension off, and the derivation turns those into warmth
        # worth about twice the flat +10 this used to add.
        "memory_weight_mend": 4,
        # a bid nobody takes. This has to hurt or making one costs nothing.
        "shame_on_failed_bid": 16.0,
        "shame_soft_cap": 80,
        "sadness_on_failed_bid": 12.0,
        "sadness_soft_cap": 75,
        "tension_on_failed_bid": 5.0,
        "anger_on_worse": 14.0,
        "anger_soft_cap": 70,
        # what time actually does: turns an open thing into a scar. Cast meters
        # have no gravity, so what this takes off closeness stays off.
        "scar_after_hours": 40,
        "closeness_on_scar": 1.8,
        "memory_weight_scar": 4,
        "event_salience": 3
    },

    # Anxiety as a process rather than a level (sim/spiral.py). Everything in
    # here is about how the mechanism works, which is human; what makes it this
    # girl's is entirely in her own numbers -- her anxiety baseline is her
    # propensity, her cast meters decide who can start one, and her
    # self-beliefs decide what a chain is pulled toward and how far it runs.
    "spiral": {
        "enabled": True,
        "min_gap_minutes": 45,
        "max_per_day": 3,
        "max_kept": 60,
        # A chain runs while the belief it is heading for is still pulling, so
        # what she has most riding on carries her furthest: 95 invested is six
        # steps, 45 is three. max_steps_hard is a backstop, not the mechanism.
        "steps_per_invested": 16.0,
        "max_steps_hard": 7,
        "start_base": 0.55,
        # The self-feeding term. This is the one gate in the project that
        # accelerates instead of damping, because that is the thing being
        # modelled: three steps in, the fourth is likelier, not less likely.
        # The brakes are opportunity and the caps, never the chain.
        "extend_base": 0.45,
        "extend_per_step": 0.28,
        # Who can start one: not a list of people, a measure of how unsettled
        # her standing with them is. Somebody she is placed well with and has
        # nothing outstanding with cannot seed anything.
        "tension_weight": 0.65,
        "standing_weight": 0.45,
        "envy_weight": 0.4,         # someone she measures herself against can seed a chain
        "standing_settled_at": 62,
        "seed_min": 0.15,
        # her rest is not neutral: the level is the propensity, and being
        # above rest on top of it accelerates. Capped so a very wound-up
        # evening cannot make it a certainty.
        "pressure_cap": 1.2,
        # Rumination needs somewhere to happen. She is fine while she is with
        # them and starts on the train home.
        "busy_factor": 0.35,
        "min_energy": 25,
        # What going over it costs. Through _warm, so the gauge saturates
        # gracefully while the thought carries on getting worse; those two
        # curves are meant to come apart. Mood is left to the state model off
        # the event rather than pushed through its baseline by hand.
        "anxiety_per_step": 7.0,
        "arrived_anxiety": 12.0,
        "anxiety_soft_cap": 88,
        "pitch_per_step": 18,
        # He answered. She feels better and nothing has been settled.
        "reassurance_relief": 9.0,
        "fade_hours": 14,
        "events_shown": 14,
        "chat_shown": 8,
        "in_prompt": 2,
        # the social term the impulse never had
        "impulse_weight": 0.30,
        "event_salience": 2,
        # what the record having the last word is worth
        "settle_min_steps": 2,
        "borne_out_fit": 4.0,
        "disconfirm_strain": 26.0,
        "disconfirm_relief": 20.0,
        "max_also_touches": 2,
        "memory_weight": 3
    },

    "goals": {
        "enabled": True,
        "min_chars": 12,
        # the same want two mornings running is one want she is carrying
        "same_jaccard": 0.45,
        "carry_to_standing": 2,
        "max_kept": 60,

        # What a day that did not go her way costs. Nothing used to: a
        # `missed` appended a line to the goal's history and left it
        # wanting, so a goal she failed and a goal she had not got round
        # to were the same object.
        "fail_base": 8.0,
        "fail_per_carried": 3.0,
        "fail_per_invested": 10.0,
        # a day she let go past is about her; a move that did not land has
        # an explanation available and she will take it
        "fail_missed_scale": 1.0,
        "fail_tried_scale": 0.5,
        # in front of people, which for her is the whole of it
        "fail_witnessed_scale": 1.6,
        # the graph prices the audience: the same witnessed stumble costs
        # more in front of an irritated group than a warm one (0 disables)
        "witnessed_heat_spread": 0.4,
        # what an outcome is worth as evidence for the belief underneath
        # it, out of 5
        "got_fit": 3.0,
        "tried_fit": 1.0,
        "give_up_fit": 4.0,

        # When she stops wanting it. Not a trait and not a count of tries:
        # a want survives while it is holding up something she believes
        # about herself, so one anchored to nothing much dies quietly at
        # three failures and one holding up ninety points of self she
        # carries well past sense. Point the code at a different
        # self_beliefs.json and a different girl gives up somewhere else.
        "give_up_base": 18.0,
        "give_up_per_invested": 70.0,
        # giving up is the expensive one: the failure that ended it counts
        # double. Not the accumulated cost -- the belief has already been
        # strained for each of those, one at a time.
        "give_up_strain_mult": 2.0,
        # past this share of the way to giving up it shows in her prompt
        "tiring_at": 0.6,

        # a day that went against her stays with her longer than one that
        # went her way
        # What an outcome feels like, as opposed to what it costs. Without
        # this the goals only had a downside: a failure charged a belief and
        # wrote a memory, and getting the thing produced nothing at all.
        "pride_on_got": 16.0,
        "pride_soft_cap": 80,
        "sadness_per_fail": 9.0,
        "sadness_on_give_up": 18.0,
        "sadness_soft_cap": 75,
        "shame_on_witnessed": 14.0,
        "shame_soft_cap": 80,
        "memory_weight_fail": 3,
        "memory_weight_got": 2,
        "memory_weight_given_up": 4,
        "event_salience": 3
    },

    # Her own memory of her own life (sim/self_memory.py), which she had
    # nothing of: facts about him had weights, half-lives and cue recall, and
    # her own past was one summary a day.
    "self_memory": {
        "enabled": True,
        # slower to go than a fact about him. A fact about someone else is
        # information; this is her, and a weight 5 memory is for good.
        "half_life_days": [14, 45, 120, 400, 1200],
        "min_score": 0.5,
        "max_in_prompt": 8,
        "max_recalled": 3,
        # ...of which this many may be rows the WORDS never found. Her own
        # memories are the pool this matters most in: on the second
        # character's save every one of her twenty-one memories cleared the
        # old fixed floor for every Japanese cue, so the cosine chose the
        # three she read at random.
        "max_cosine_only": 1,
        # How many of what she is MADE OF sit in the prompt, in slots of their
        # own beside the max_in_prompt she has lived through. A memory written
        # in from her own record (source `seed`) does not fade at all -- a
        # person does not gradually stop knowing their own job -- so the fade
        # line cannot choose among them and this cap does. Anything at weight 5
        # is in every prompt; the remaining slots walk the rest in weight
        # order, one step a character day, so the whole record comes round.
        # Only the second character has memories of this kind; the first has
        # none, so the number does nothing in her save.
        "standing_in_prompt": 8,
        # looser than the bar for facts about him: two wordings of one
        # afternoon are one afternoon she keeps thinking about
        "duplicate_jaccard": 0.5,
        "max_per_day": 5,
        # the moments write themselves (state._moment, npc._record): a tick whose
        # biggest move is moment_min_delta, or whose moves sum to moment_min_total,
        # keeps the state model's own reasons line as a memory, at most
        # moment_max_per_day a day; the compile then authors at most
        # compile_max_per_day of its own and mostly reinforces what the day wrote
        "compile_max_per_day": 2,
        "moment_min_delta": 8,
        "moment_min_total": 14,
        "moment_max_per_day": 6,
        "moment_npc_salience": 3,
        # Mood-congruent retrieval: how she feels selects what she surfaces, and
        # what she surfaces deepens how she feels. The second self-feeding loop
        # after the spiral. Keyed on `mood`, which lags, because a mood is what
        # colours retrieval and not the feeling of the minute. The floor stops
        # a good day from making an unhappy memory unreachable.
        "mood_congruent": True,
        "congruence_weight": 0.6,
        "congruence_floor": 0.45
    },

    "care": {
        # sim/care.py: her investment in him from the record, and whether
        # her checking matches it. scale_checking multiplies the app-look
        # and snoop rolls by 0.5..1.5 from investment (off until he says).
        "enabled": True,
        "window_days": 7,
        # The narrowest span the per-day rates will divide by. The window is
        # how far back to look; this is the floor on how long there has to have
        # been a record before a rate means anything, so a character who has
        # existed for an hour is not divided by a week (which read as caring
        # about nothing) nor by an hour (which would read as checking on him
        # forty-eight times a day).
        "min_window_hours": 12.0,
        "reaches_full_per_day": 3.0,
        "balance_full_ratio": 3.0,
        "slow_minutes": 120.0,
        "left_after_minutes": 360,
        "checks_full_per_day": 8.0,
        "snoop_weight": 2.0,
        "weights": {"initiative": 1.0, "balance": 0.5, "responsiveness": 1.0, "not_left_on_read": 0.7, "attention": 1.0,
                    "head_share": 1.2, "attachment": 1.2, "affection": 0.8, "not_resentful": 0.5},
        "silence_full_hours": 12.0,
        "his_slow_minutes": 180.0,
        "checks_base_per_day": 4.0,
        "uncertainty_gain": 1.2,
        "scale_checking": False
    },

    "foresight": {
        # sim/foresight.py: what she expects him to do next, written down at
        # each send and checked by the record
        "enabled": True,
        "keep": 60,
        "stale_hours": 12,          # an open prediction past this is a silence
        "window_slack": 1.5,        # answered inside reply_minutes x this counts as inside
        "surprise_reply_p_under": 0.35,
        "surprise_bump": 12,
        "surprise_soft_cap": 70,
        "refresh_hours": 3,         # while he is quiet, a fresh reading this often
        "refresh_silent_from": 2,   # ... once he has been quiet this long
        "impulse_weight": 8.0,      # reaching again inside her own window costs (1 - reply_p) x this
        # the risk each prediction names, scored against his next mood read
        # (`score_risks`): happened if it is cold inside risk_hours, passed if
        # not; happened warms guilt and shame, passed warms relief
        "risk_hours": 6,
        "risk_guilt": 6,
        "risk_shame": 4,
        "risk_relief": 5
    },

    # Expectations of him (sim/expectations.py): signed, checkable, with a
    # due time and a source -- what he said he would do (`expect_him`), when
    # he said he would be around (mirrored from rhythm_said), what foresight
    # said might land badly, and his habits learned from a week of digests
    # (`habits_him`, once a day). Settled by code off the record; a missed
    # one strains the belief it rested on, moves resentment and tension,
    # and sits in her prompt as raisable until she brings it up.
    # Questions she is curious about (sim/wonder.py): formed by the `wonder`
    # call when curiosity is over its rest or something just reached her
    # (a look, a snoop); handed to the intent by id; the send marks one
    # asked; his answer inside answer_hours is judged by `wonder_answer`
    # and confirms or strains the belief it bore on (test_him), moves
    # attachment (compare_self), or warms curiosity and leaves it standing
    # (dodged). The one route by which a belief about him is tested by
    # asking him.
    # Borrowed eyes (tomoe/scenery.py): real photographs from real, ordinary
    # Japanese accounts she follows for the purpose, described by her eyes,
    # kept with their source, and -- when her scene, the season, the hour
    # and the weather fit -- sent as a photo she just took, with her bubbles
    # as the caption. What a sent photo showed is adopted into
    # `scenery_lore` so later photos and her words stay consistent. Never
    # reposted anywhere.
    "reactions": {
            "enabled": True,
            # Whose face. A directory name rather than a path, which is how it
            # escaped every check that looks for a path: the second character
            # was configured to publish frames of the FIRST character's face as
            # her own mood. Empty here, hers in her own config
            # (`Config.PERSON_FILES`), and the images are
            # data/reactions/<character>/reactions.db, built by tools/reactions.py
            "character": "",
            # The automatic band reaction changes her FACE (the app header), and it
        # used to send that face into his chat as well. Overnight that was five stickers with no words -- her mood
        # wandering through its bands, narrated at him. A sticker is how SHE
        # says a mood in a reply (`Reactions.chosen`), not a status feed.
        "sticker": True,
        # and the face only moves while he is actually in the chat: her mood
        # wanders all day, and following it into an empty room is what made
        # five changes overnight. Nothing is recorded while he is away, so the
        # first tick after he comes back moves it once, to now.
        "active_minutes": 20,
            "repeat_days": 7,                # never the same image twice inside this
            "min_gap_minutes": 20,           # two crossings closer than this show one face
            "surprise_from": 35,             # the surprise gauge over this is its own crossing
            "anger_from": 55,
            "sadness_from": 55,
            "anxiety_from": 60,
            "awkward_from": 50,
            "tired_below": 30,
            "fatigue_from": 60,
    },
    "scenery": {
            "enabled": True,
            # Whether new photographs are still being collected. OFF (his call). With this false `Scenery.due` never comes due,
            # so no harvest session opens a browser, runs a discovery search,
            # judges an account or pays Gemini to describe an image; the
            # harvest was ~70 Gemini descriptions, ~17 judge looks and ~35
            # `scenery_judge` calls a day. Everything after collection is
            # untouched: 641 usable photographs are on file, and `offer` /
            # `pick` / `adopt` still send one a day from them. `/scenery
            # harvest` is the manual door and still runs a session.
            "harvest": False,
            # What her photo harvest searches for, and the place words her
            # scene classifier tests against: hers, in her own config, and
            # EMPTY here. Twenty searches and forty place words named one
            # ward, one railway line and one shopping street, and every
            # character inherited them. With no queries there is nothing to
            # harvest and the section switches itself off
            # (`Config.NEIGHBOURHOOD`).
            "queries": [],
            "search_scrolls": 3,
            "judge_per_session": 8,
        # 9 is about three sessions a day. At 3 the harvest ran seven or eight
        # a day and spent 100-130 Gemini calls plus 50-60 judge calls for a
        # base she sends one photograph a day from; a third of that keeps the
        # base rolling
        "harvest_every_hours": 9,
        # a food photo is plausible on her desk: these scene kinds may send a `food` row when nothing of the place fits
        "food_at": ["room", "home", "konbini", "cafe", "school"],
        # a food photo only inside a meal window (her hour), and the hint
        # names the meal; outside them no food row is offered
        "food_hours": {"lunch": [11, 15], "dinner": [18, 22]},
        "send_kinds": ["station", "train", "konbini", "park", "street", "shotengai", "cafe", "shop", "shrine", "river", "city", "food", "sky", "library", "museum"],
        # where an image plainly is, from its own signs (the `region` the
        # vision reads). A street she sends as hers has to be a street she
        # could be standing in: Kyoto and a German platform were both on file.
        # "unknown" is allowed -- most photographs say nothing about where
        # they are, and that is exactly what makes them usable.
        # Anywhere he would read as her part of the world. He cannot tell a
        # Saitama platform from a Nerima one and does not want to: what has to
        # be right is the light, the weather and the hour. Kyoto's Minami-za
        # and a German Hauptbahnhof are what this is for.
        "regions_ok": ["unknown", "tokyo", "saitama", "kanagawa", "chiba", "kanto"],
        # an interior gives nothing away: a cafe table or a ramen counter
        # anywhere in Japan is usable; only the outdoors has to be her part
        "indoor_any_japan": True,
        # What to search for, by the place kind that needs filling. The
        # harvest aims itself: the kinds her next two days actually pass
        # through, weighted by what the base is short of (`gaps`). Her own
        # places by name where she has one, the vibe where she does not.
        "kind_queries": {},
        # how many usable rows of a kind counts as covered, and how far back
        # her own scenes are read to know which kinds she actually stands in
        # searches per harvest session: the base is short of authors, not of
        # passes over the same six
        "searches_per_run": 2,
        # A named event she is going to is the one perishable thing here:
        # people post it while it is on and not afterwards. It jumps the gap
        # queue until this many of its images are on file, and those images
        # go out at that event and nowhere else.
        "event_target": 4,
        "event_days": 2,
        "gap_target": 6,
        # how many of the worst gaps the search rotates across. One at a time
        # would fill a kind to the target before touching the next, and leave
        # her with six konbini shelves and still no platform.
        "gap_spread": 3,
        "demand_days": 14,
        # today and tomorrow: the plan is what the harvest aims at
        "route_days": 2,
        # how far back her own bubbles count as "what she has just said". A
        # photo has to agree with them; "going to the library at 9" said at
        # two in the morning is not a claim about where she is at three.
        "said_minutes": 90,
        "accounts_per_run": 6,
        "user_scrolls": 1,
            "harvest_per_run": 10,
            "min_quality": 2,
            "send_p": 0.35,
            "send_max_per_day": 1,
            "min_gap_hours": 20,
            # per author, and per rolling window -- a flat lifetime cap put a
            # whole account's remaining photographs out of reach for ever
            # once three had gone
            "max_used_per_author": 3,
            "author_window_days": 30,
            # the post a sent photo came from is liked / reposted from the
            # account (curation.queue_direct); real posts by real people
            "like_sent": True,
            "repost_sent": True,
            # the FALLBACK only, rolled once per sent photo, for when her
            # pick cannot run (`curation.share_pick`)
            "repost_sent_p": 0.35,
            # rows whose vision answer never came back (the budget, the quota,
            # a 401) are asked again at the next session, this many a run;
            # 103 such rows sat "rejected" for good against 92 usable
            "redescribe_per_run": 12,
            # A friend's picture is its DESCRIPTION and nothing else (his call,
            # 2026-09-03): the words in the chat are the whole of it, nobody
            # opens a file, and this pool is for the photographs she sends HIM,
            # which he does open. There was a key here that matched a friend's
            # planned picture to a real row by words in common; a friend then
            # spent a photograph out of the one place they are ever looked at,
            # and the caption in the chat described the wish rather than the
            # file underneath it.
            "local_kinds": [
                    "station",
                    "konbini",
                    "park",
                    "street",
                    "shotengai",
                    "school",
                    "room",
                    "home",
                    "library"
            ],
            "local_names": [],
        # Her scene -> the database's place kinds, for the picker. The node
        # she is standing on (data/places.json `kind`) is the authority; this
        # is the fallback for free text, matched longest-keyword-first and on
        # word boundaries for ASCII, so "homework" is no longer "home". Both
        # languages: what she says aloud and what her friends write is
        # Japanese, and the picker reads what she actually said.
        "place_map": {},
    },
    "wonder": {
        "enabled": True,
        "max_per_day": 2,
        "max_per_call": 3,
        "max_open": 6,
        "cooldown_hours": 6,
        "curiosity_over": 15,
        "candidates": 3,
        "in_prompt": 2,
        "answer_hours": 8,
        "reask_hours": 48,
        "confirm_gain": 8,
        "strain_gain": 8,
        "self_confirm_gain": 4,
        "similar_attachment": 4,
        "unlike_attachment": -2,
        "dodged_curiosity": 8,
        "dodged_charge": 10,
        "keep": 60,
        # a reply of hers that says an open question in its own words marks it asked
        "voiced_min_words": 5,
        # at the compile, open questions this old are judged against the day's chat
        "review_after_hours": 24,
        "review_max_per_compile": 6,
        # past this an open question fades: she stopped turning it over
        "open_max_age_days": 7
    },
    "expect": {
        "enabled": True,
        "keep": 80,
        "trigger_words": ["i'll", "ill ", "i will", "gonna", "going to", "will ", "later", "tonight", "tomorrow", "promise",
                          "send", "call", "watch", "read", "tell you", "let you know", "back in", "after work", "in a bit", "when i"],
        "min_chars": 8,
        "max_per_message": 3,
        "min_confidence": 0.5,
        "max_days_ahead": 3,
        "grace_minutes": 45,
        "around_belief": "would_defend",
        "raise_for_hours": 48,
        "kept_confirm": 6,
        "kept_relief": 6,
        "missed_strain": 10,
        "missed_resentment": 4,
        "missed_tension": 6,
        "habits_enabled": True,
        "habits_days": 7,
        "habits_min_digests": 8,
        "habits_max": 6,
        "habit_grace_minutes": 60,
        "habit_miss_curiosity": 8
    },

    "family": {
        # tomoe/family.py: the parents' days drawn from data/household.json
        # schedules, seeded by the date; the car; pickups; family days
        "enabled": True,
        "seed": 7,
        "trip_p": 0.2,                 # a family day on a free Sunday / holiday / Saturday
        "twist_p": 0.15,               # one thing off the timetable, some days
        "dad_cutoff_hm": "23:30",      # past this he is in bed and not coming
        "dad_willing_weeknight": 0.5,
        "dad_willing_weekend": 0.85,
        "far_minutes": 35,
        "mom_daylight_from_hm": "08:00",
        "mom_daylight_to_hm": "17:30",
        "mom_far_minutes": 15
    },

    "situation": {
        # embodied/situation.py: where her body is, continuously. Journeys run on
        # the clock from data/places.json; reality lands on the legs (the
        # train feed, the weather, the rush windows); fatigue accumulates by
        # what she is doing and recovers only at rest.
        "enabled": True,
        "delayed_minutes": 12,       # a train leg on a line reported delayed
        "stopped_minutes": 30,       # ... or suspended
        "packed_minutes": 3,         # the rush-hour Seibu is slower
        "change_minutes": 6,
        "late_event_from": 10,       # minutes late that become an event
        "keep_journeys": 40,
        # fatigue points per hour by what she is doing (heat scales the
        # positive rates: x(1 + (feels - heat_free_feels) / heat_per_degree))
        "walk_per_hour": 14.0,
        "packed_per_hour": 8.0,
        "train_per_hour": 2.0,
        "out_per_hour": 4.0,
        "sitting_per_hour": 1.5,
        "rest_per_hour": 8.0,
        "bath_per_hour": 14.0,
        "sleep_per_hour": 16.0,
        "heat_free_feels": 28,
        "heat_per_degree": 6.0,
        # readers
        "tired_from": 45,
        "wiped_from": 70,
        "fatigue_delay_weight": 0.6,   # delay x(1 + fatigue/100 * this)
        "walking_delay": 1.6,
        "packed_delay": 1.25,
        # walking speed, clothing and load, running late, vehicles, the weather
        # on her, and the things that can happen on the way -- see situation.py
        "walk_tired": 1.1,
        "walk_wiped": 1.3,
        "walk_heat_per_degree": 0.02,
        "walk_rain": 1.12,
        "yukata_keywords": ["yukata", "festival", "matsuri", "bon odori", "fireworks", "hanabi"],
        "yukata_walk": 1.35,
        "yukata_sweat": 1.3,
        "uniform_sweat": 1.15,
        "school_bag_load": 1.12,
        "shopping_keywords": ["shopping", "bags", "haul", "bought", "supermarket run", "errand for mom"],
        "shopping_load": 1.15,
        "hurry_tolerance_minutes": 4,
        "run_time_factor": 0.72,
        "run_fatigue_factor": 2.4,
        "run_bump_factor": 3.0,
        "run_sweat_factor": 1.8,
        "car_keywords": ["car", "drive", "drives", "driving", "pick her up", "picks her up", "lift"],
        "car_min_minutes": 8,
        "car_factor": 0.6,
        "bike_factor": 0.45,
        "forget_umbrella_p": 0.25,
        "sweat_from_feels": 30,
        "sweat_comfort_per_hour": 22.0,
        "sweat_event_from": 7.0,
        "sweat_line_from": 4.0,
        "p_bump": 0.012,
        "p_found": 0.006,
        "p_cat": 0.02,
        "p_neighbour": 0.01,
        "p_trip": 0.003,
        "p_bike_chain": 0.01,
        "p_seat": 0.06,
        "p_close": 0.004,
        "p_missed": 0.03,
        "p_bag": 0.05,
        "p_dog": 0.015,
        "p_car_talk": 0.3,
        "texting_window_minutes": 3,
        "texting_bump_factor": 4.0,
        "running_delay": 2.5
    },

    "impulse": {
        # impulse = weighted gauges + event salience + silence, scaled by phone access
        # hunger and low energy pull the other way: a starving or exhausted
        # her reaches for food or the pillow before the phone
        "weights": {"loneliness": 0.35, "boredom": 0.25, "validation_craving": 0.25, "anxiety": 0.10, "hunger": -0.12, "energy": 0.08, "curiosity": 0.10, "jealousy": 0.15, "affection": 0.20, "guilt": 0.18, "fatigue": -0.12,
                    # Shame is the one that makes her hide. Tension was the only
                    # thing in here that could make her reach out less, so before
                    # this she could go quiet because she was cross with him and
                    # never because she could not face anybody.
                    "shame": -0.30,
                    # Anger mostly is not at him (see its `tells`), so it wants
                    # telling -- she complains to the one person who takes her
                    # side. Anger *at him* goes through tension, which is a gate.
                    "anger": 0.12,
                    # Sadness is the deactivating one: it wants nothing, and it
                    # pulls against loneliness, which wants the phone.
                    "sadness": -0.15,
                    # Something good happened and he is who she tells.
                    "pride": 0.14,
                    # like hunger: the body wanting to be left alone
                    "unwell": -0.10,
                    # the one that is actually about him rather than about a
                    # deficit: missing a particular person, which is what her
                    # whole situation is made of
                    "longing": 0.32,
                    # The counterweight, and the only term in here that makes
                    # her want him LESS for a good reason rather than a bad one.
                    # An evening where the group was good to her used to leave
                    # her wanting him exactly as much as one where they were not.
                    "belonging": -0.26},
        "silence_hours_weight": 3.0,
        "silence_hours_cap": 8,
        "event_share_bonus": 25,
        "threshold": 62,
        "phone_access_factor": {"free": 1.0, "glance": 0.55, "none": 0.0},
        # HE IS HERE AND NOT ATTENDING HER. A resident can see him at the
        # machine and see that what is in front of him is not her
        # (`resident/sight.py:attention_observation`). That is the same
        # observation the presence gate was a statistic for, in the other
        # direction: knowing he is here and busy with his own thing is a
        # reason a girl reaches, not a wall (`sim/impulse.py:60-76`,
        # `:186-198`). Added on the impulse's own scale, beside the 18 for a
        # page of hers being open in front of him.
        "here_not_attending_bonus": 18.0,
        # A self-start every ninety minutes was the bar; forty-five is still
        # above the 45-minute "she just texted him" window below, so the two
        # do not collapse into one, and it no longer outlasts the unanswered
        # backoff it is supposed to leave room under.
        "cooldown_minutes": 45,
        "max_self_started_per_day": 6,
        # unanswered self-started messages in a row before she stops
        "max_unanswered_streak": 2,
        # Both caps above count times she reached out, not bubbles. One message
        # of hers is three to six bubbles seconds apart, so counting rows spent
        # the whole day's allowance on a single hello (it did, on 2026-08-21:
        # six bubbles at 23:54 and she could not open her mouth again until
        # midnight). Anything closer together than this is one time she spoke;
        # it has to sit above typing_max_seconds x a full batch and far below
        # cooldown_minutes.
        "burst_gap_minutes": 10,
        # How much his own hours weigh on her reaching for him. `presence_floor`
        # is the hour he is simply never there  and
        # she does not text into it; `presence_weight` makes a 0.3 hour a weaker
        # pull than a 1.0 hour rather than the same one. Both read
        # `Rhythm.learned_now`, which is learned from the record and nothing else.
        "presence_floor": 0.12,
        "presence_weight": 0.35,
        "min_sleep_gate_energy": 15,
        # he read it and left it: after this many minutes the impulse gets a bonus
        "read_ignored_minutes": 45,
        # Tension is the only term that lowers the score. Everything else in
        # weights pushes toward contact, so without this there is no state in
        # which she deliberately goes quiet on him.
        "withdraw_from": 30,          # below this it costs her nothing
        "withdraw_weight": 45,        # full strength at tension 100
        "withdraw_silent_from": 42,   # past this she simply does not reach out
        # squirming is not the same as going cold: she still wants him, she just
        # cannot be normal yet. A subtraction, never a gate.
        "awkward_from": 25,
        "awkward_weight": 20,
        "read_ignored_bonus": 15,

        # Whether she may reach out first at all, asked before the score and
        # before her wanting to (sim/initiative.py). A discharge and the two
        # stances that enter without waiting go through it and are logged.
        #
        # HIS COMING BACK. Only a character who can see whether he is at his
        # machine is ever told he has come back, and for her his first touch
        # used to be a doorbell: the sleep coasting ended, a director tick ran
        # at once, and the impulse was asked with eight hours of silence
        # behind it (a score far over the threshold). It is now a reason she MIGHT
        # write, rolled once, with the odds rising by how long he was gone and
        # how much she is holding, and a delay of minutes if she takes it, so a return often starts with him writing first.
        "return_away_minutes": 45,      # gone this long before coming back is a return
        "return_p_base": 0.10,
        "return_p_per_hour": 0.05,      # per hour he was gone
        "return_p_hours_cap": 8.0,
        "return_p_unsaid": 0.25,        # x how far unsaid is over its rest (full at +60)
        "return_p_max": 0.55,
        "return_delay_minutes": [4, 25],  # she took it: she writes somewhere in here
        "return_hold_minutes": 90,      # she did not: nothing self-started for this long
        # BEING IGNORED. `max_unanswered_streak` capped the run at two and
        # nothing stood between the first unanswered message and the second
        # but the ordinary cooldown, so reaching into her own silence cost
        # exactly what reaching into his did. By streak, in minutes.
        "backoff_minutes": [0, 45, 150, 420],
        "backoff_read_factor": 1.5,     # he opened it and said nothing: that is an answer
        "backoff_unseen_factor": 1.0,   # he has not looked: he may be away from the desk
        "max_unanswered_per_day": 3,
        # THE USER'S NIGHT. Her own sleep may be his, but a night he spends at the
        # machine was a night she could talk into at any hour. In his clock.
        "quiet_start_his": "23:00",
        "quiet_end_his": "07:00"
    },

    # WHAT SHE DOES WITH THE PHONE, asked as a call that picks a tool
    # (sim/pick.py, docs/tool-calling.md §17). At a moment code already knows
    # she is handed the moment as facts and the tools she has a path to -- put
    # it down, write to him first, open the group, write to one of her own
    # people, look at what he has been doing, open her own feed; and when he
    # has just written, answer him now, answer him at an hour she names, or
    # leave it -- and what comes back is what happens. The impulse function,
    # the reply delay and the group-chat roll are the backup, for a moment she
    # was not asked at or did not answer. About 20k prompt tokens a call for
    # the first character with 55% of them behind the cached prefix, $0.0015 a
    # pick and four cents a day if every one the cap allows is spent (§17.9).
    "pick": {
        "enabled": True,
        # SHADOW MODE. True logs what she would do and changes nothing, which
        # is what ran from 2026-09-06; false is live -- code carries out what
        # she picks through the seam each tool already has, and the impulse
        # function, the reply delay and the group-chat roll become the backup
        # for a moment she was not asked at or did not answer.
        "shadow": False,
        # THE MONEY, half of it: how many moments a day she may be asked at,
        # whatever happens. On every row of the record.
        "max_per_day": 30,
        # and the other half: no two looks closer together than this, whichever
        # kinds of moment they are. Four kinds of moment without it is four
        # times the spend on a busy evening.
        "min_gap_minutes": 25,
        # WHICH MOMENTS she is asked at. `block` is the start of a stretch her
        # plan gives her a free phone, `scene` a change of what she is doing
        # inside one, `beat` something landing from her own people, `inbound`
        # him writing -- where the question is not what to do with the phone
        # but what to do about his message.
        "moments": {"block": True, "scene": True, "beat": True, "inbound": True},
        # She answered him "later" and named an hour code could not read. Her
        # words stand on the record; this is how long the wait is instead.
        "later_default_minutes": 45,
        # She left his message where it was. This is how long before she is
        # asked about it again, rather than a timer she never set answering it
        # for her.
        "leave_it_minutes": 90,
        # Her `text_him` goes through the same gate every other self-started
        # message goes through (`sim/initiative.py`: the bar that rises with
        # each message of hers he has left unanswered), and the moment tells
        # her what her unanswered ones are. Off by default so the live
        # character's behaviour is unchanged until her owner turns it on; the
        # bz S arm turns it on (bzombie/arms/s/make_run.py, tk-xfk).
        "hold_by_initiative": False,
        # A look is due when something changed since her last one (sim/pick_change.py:
        # he wrote, a pc event, a world event, a gauge moved, an expectation came due,
        # his silence crossed a step), not when the clock says so. `min_gap_minutes` is
        # then only the floor and `ceiling_minutes` the longest she goes unasked. Off by
        # default so the live character is unchanged; the bz S arm turns it on (tk-y7j).
        "due_on_change": False,
        "ceiling_minutes": 180,
        "gauge_move": 12,
        "event_salience": 2,
        "silence_steps_hours": [2, 6, 12]
    },

    # The thing she thinks of straight after she has already sent it. Nothing
    # else in the system can produce "wait, ignore that": the impulse only runs
    # on a director tick, it refuses while delivery is busy, and it blocks a
    # second self-started message for half the cooldown. This is its own gate,
    # checked every pass of the loop inside a short window after her own
    # message, and it gets likelier when she is squirming, holding something, or
    # has been read and left.
    # what she has come to know about him from weeks of looking at the app
    # (sim/him_profile.py): once a day, from the last `digests` digests
    # something to talk about that is not the four of them (tomoe/gossip.py).
    # 77% of the group chat carried a time, a plan or an obligation because
    # the group's own business was the only thing in the world.
    "gossip": {
        "enabled": True,
        "every_hours": 20,
        "new_per_run": 3,
        "max_live": 5,          # how many the prompts are shown
        "keep": 40,             # rows on file
        "cool_per_day": 1.5,    # heat lost a day
        "warm_on_use": 1.0,     # heat gained when somebody brings it up
        "cold_below": 1.0,      # under this it is not going round any more
        "shows_max": 3          # stated in her turn this many times unsaid, then it steps aside for the day
    },

    # one thread (sim/thread.py): her chat with him and her talk with her own
    # people as ONE chat-completion history -- the User role is the world
    # speaking to her, the Assistant role is her wherever she spoke, every
    # message labelled [time · room · who], rebuilt every call (the history
    # never caches; the system prefix still does)
    "thread": {
        # the curve: every message in full inside verbatim_hours; past that an
        # exchange is one line at its time (how many messages, until when,
        # what it came to) and a day of his chat is the day as she remembers
        # it; past max_age_hours nothing -- by then it is her memories. An
        # exchange past verbatim whose words touch what is being said now
        # comes back in full (recall_max a call, recall_min_overlap tokens).
        # the curve, by clock (his call, 2026-09-04): verbatim_hours of
        # record in full, then every day back to max_age_hours as its cards,
        # then nothing. The verbatim span shrinks a day at a time toward
        # verbatim_min_hours only when the verbatim days plus the cards do
        # not fit what is left of context.target_tokens after the rest of
        # the prompt and a reserve for the day being lived; chosen once a
        # day of her clock (kv thread_window) so the head of the thread, and
        # the cache prefix, moves once a day
        "verbatim_hours": 168,
        "verbatim_min_hours": 36,
        "max_age_hours": 720,
        "recall_max": 2,
        "recall_min_overlap": 2
    },

    # the nudge (sim/nudge.py): a second reader of everything she carries, who
    # is not her, saying what she is actually caught by right now; `live`
    # places it in the slot when confidence clears min_confidence, `shadow`
    # only logs it beside the gate's pick, `friends` runs it on her turns
    # with her own people too
    # What she does with what she has seen: one named stance out of a ranked,
    # first-match, pinned, hysteretic table (sim/stances.py, docs/stances.md).
    # Off by default: a character with no relational quantities behind her has
    # nothing for the table to read, and the register chain is what she has.
    "stances": {
        "enabled": False,
        # Hysteresis. Every threshold in mood_tags, register, blends,
        # delay_factor, impulse.score and withholding.pressure is a bare
        # comparison re-evaluated per call, so a quantity sitting on one flaps
        # the line on and off between two consecutive generations. A stance is
        # entered only after its condition has held this long -- except the two
        # urgent rows, because a person who has just been frightened does not
        # wait -- and the table falling back to "even with him" has to hold for
        # `hold_minutes` before the stance she was in is dropped.
        "min_minutes": 12.0,
        "hold_minutes": 25.0,
        # how long after she put him back outside that stance still describes
        # her: two days, after which being outside is just where he is
        "expel_hours": 48.0,
        # carrying something she read and cannot raise: the item has to be
        # live and she has to be squirming about it
        "carrying_awkwardness": 45.0,
        # held in mind by name: a message of his that reached a record of hers,
        # while that message is still the one in front of her
        "settler_minutes": 30.0,
        # sitting on something she could say: how long an item she could raise
        # has to have sat there unraised before not raising it is a stance
        "sat_on_minutes": 60.0,
        # ...and whether being told to name it fires once per THING rather than
        # on every reply until she raises it. A character who is inside his
        # machine has something unraised nearly all the time, so the one
        # imperative line of her prompt was an instruction to name something
        # off his screen on most turns of most days. On, the instruction is
        # spent on the first reply after the item settles and the stance goes
        # on holding, which is what pays her for the restraint
        # (`settle_discretion`). Default off: the first character looks at a
        # digest a few times a day and has never had this fault.
        "name_it_once": False,
        # outside his notice: what evidence he keeps her in mind has to be
        # under, and how long his machine has to have been busy with nothing
        # toward her
        "unnoticed_below": 25.0,
        "active_hours": 3.0,
        # needling: how settled she has to be with him before a thing that used
        # to knock her sideways is something to tease him about (sim/ick.py:
        # the share of what she has met lately whose sort she already knew)
        "settled_from": 0.6,
        # and how long a discretion stance has to have held over one item
        # before leaving it alone is a thing she chose rather than a thing that
        # went cold: the credit side of the ledger she controls
        "discretion_minutes": 30.0
    },
    "nudge": {
        # off (his call, 2026-08-30): the unhedged slot line addresses what she
        # carries on its own, and code holds it on a heavy message of his
        "enabled": False,
        # the nudge is the reader of `unsaid` at a threshold, not a call on
        # every message: what she carries (the nag, a post to show him, a
        # promise) warms `unsaid` while it waits, and when the gauge crosses
        # unsaid_min the nudge fires -- with him or with her own people --
        # decides what comes out, and the gauge settles by unsaid_relief.
        # Below it nothing rides in the slot and no carried thing happens.
        # The nag comes out only with him; in a friend's room the same
        # pressure comes out as the push-back or what belongs there
        "fire_on_unsaid": True,
        "unsaid_min": 45,
        "min_gap_minutes": 45,
        "unsaid_relief": 12,
        "unsaid_per_carried": 3,
        "unsaid_soft_cap": 85,
        # the ongoing test: every live reply to him is drafted once more with
        # the gate's line in the slot instead of the nudge's, logged as
        # [nudge-ab] and kept in kv nudge_ab (/nudgeab), never sent
        "compare": True,
        "mode": "live",
        "friends": True,
        "min_confidence": 0.5,
        "max_chars": 360
    },

    # attention (sim/attention.py): every line of her situation block is a
    # claim with a weight; a source without a weight of its own gets one
    # here; a covering source suppresses what it already says; the heaviest
    # ACTION rides the one slot she reads (last but for LENGTH), the rest
    # queue. Nothing is dropped for room: the per-section [lines, chars]
    # budgets, the block total and the pin ceiling went on 2026-09-04; the
    # one budget over the prompt is context.target_tokens
    "attention": {
        "enabled": True,
        # the slot's one action line waits when his last message is heavy:
        # his_mood.valence at or under this, read within heavy_fresh_minutes
        "heavy_valence": -1,
        "heavy_fresh_minutes": 30,
        "cue_bonus": 0.3,               # a line that touches what he just said
        # the imperative line reads as an order, so an action lighter than
        # this does not take it: it rides as a plain line in its own section.
        # A link to share held the slot 25 times in a week at 0.35, the
        # lowest weight in the table, because it was the only action offered.
        # Her chat with him only: the friend room's one action is a rumour at
        # 0.45, and this would empty that slot instead of raising its bar
        "slot_min_weight": 0.5,
        # ...and neither does the action the live prediction says she is
        # braced against: this many words shared between the risk and the
        # line (or one handle the source says its item is about). 0 is off
        "foresight_veto_overlap": 2,
        "section_default": {"her": 0.6, "him": 0.5, "day": 0.5, "phone": 0.4, "them": 0.6, "himf": 0.4},
        "weights": {
            "register": 0.8, "directed": 0.7, "attachment": 0.85, "withholding": 0.85, "unsent": 0.6,
            "felt": 0.7, "receipts": 0.7, "rhythm": 0.5, "his_mood": 0.5, "foresight": 0.5,
            "expectations": 0.6, "wonder": 0.4, "nag": 0.55, "gap_days": 0.7,
            "body": 0.6, "around": 0.35, "today": 0.8, "goals": 0.6, "commitments": 0.55, "ledger": 0.85,
            "travel": 0.3, "trip": 0.4, "money": 0.4, "shape_of_day": 0.6, "yesterday": 0.5,
            "morning": 0.65, "anticipation": 0.5, "lore": 0.3,
            "digest": 0.7, "digest_live": 0.5, "anime_list": 0.5, "x_recent": 0.5, "his_likes": 0.5, "his_follows": 0.4,
            "her_actions": 0.35, "share": 0.35, "show_him": 0.6, "engagement": 0.6, "recall": 0.6,
            # the friend turn (tomoe/exchange.py): the person, her day, him as facts
            "bond": 0.85, "behind": 0.6, "known": 0.5, "thought": 0.6, "promise": 0.65, "gossip": 0.45,
            # above `promise`, which is only colour: this is the one she can
            # discharge in the message she is about to write, and a promise
            # she is never shown a way to keep is a debt that only grows
            "owed_send": 0.8,
            "said": 0.7, "threads": 0.5, "settled": 0.85, "him_last": 0.5
        },
        "covered_by": {"ledger": ["commitments", "money"], "settled": ["money"]},
        "one_per_source": ["rhythm", "anime_list", "lookup"],
        # the tally: per day, per room, per source -- offered / admitted / slot /
        # covered (kv attention_tally); `/attention tally`, `/absurd` UNHEARD
        "tally_days": 14,
        "unheard_days": 7,              # the window UNHEARD reads
        "unheard_min_offers": 8,        # a source offered fewer times than this is too new to judge
        # dead-on-average BY DESIGN: situational lines the cue bonus lifts
        # when their subject is touched; UNHEARD does not count them
        "unheard_ok": ["travel", "lore"]
    },

    # the day read as one story at the compile (sim/coherence.py): contradictions,
    # invented things, repeats -- flagged in kv coherence_flags, never rewritten
    "coherence": {
        "enabled": True,
        "max_seams": 12,                # kept per day from one reading
        "keep": 200,                    # rows kept in kv coherence_flags
        "absurd_days": 2,               # the window `/absurd` SEAMS reads
        # the compiled summaries of this many previous days go in front of the
        # reader, so a line that refers back is judged, not called invented
        "context_days": 2
    },

    # what she holds with the people around her (tomoe/cast_psych.py): rupture and
    # repair, their promises to her, leaving somebody on read, confidences --
    # the him-side mechanics turned toward the cast
    "cast_bond": {
        "enabled": True,
        "min_turns": 2,                 # an exchange shorter than this is not read
        "scar_after_hours": 48,
        "tension_per_severity": 6,
        "guilt_per_severity": 4,
        "closeness_on_mend": 3,
        "tension_off_on_mend": 8,
        "guilt_off_on_mend": 6,
        "closeness_on_scar": 4,
        "mend_attachment": 3,
        "mend_respect": 2,
        "scar_resentment": 3,
        "failed_bid_shame": 4,
        "failed_bid_resentment": 2,
        "promise_default_hours": 24,
        "promise_grace_hours": 6,
        "missed_resentment": 3,
        "missed_tension": 4,
        "kept_respect": 2,
        "kept_relief": 4,
        # warmth toward her own people (`state.gauges.fondness`), which this
        # section owns. Four things raise it and three take it off, all of
        # them moments this module already reads, so a character with a
        # circle has a good feeling that is about them and not about him.
        "mend_fondness": 3,          # per severity, a thing between them got sorted
        "kept_fondness": 5,          # they did what they said they would
        "confided_fondness": 3,      # she told one of them something real
        "together_fondness": 2.5,    # an ordinary exchange with one of them that broke nothing
        "fondness_soft_cap": 88,
        "broke_fondness": 4,         # per severity, a new break with one of them
        "failed_bid_fondness": 3,    # she reached to mend it and they did not take it
        "missed_fondness": 4,        # they said they would and did not
        # leaving them on read: a roll off her standing with them
        "leave_threshold": 0.4,
        "leave_max_per_day": 1,
        "leave_min_gap_hours": 20,
        "leave_tension_from": 35,
        "leave_weight_tension": 0.6,
        "leave_weight_resentment": 0.5,
        "leave_weight_rupture": 0.3,
        "leave_weight_low_mood": 0.3,
        # ...and being fond of them is what stops her: the reader that makes
        # `state.gauges.fondness` act rather than sit in a report
        "leave_weight_fondness": 0.5,
        "max_confidences": 12,
        "event_salience": 3,
        "memory_weight": 3
    },

    # the people who are not the cast but belong to somebody in it (tomoe/orbit.py):
    # Rena's sister was one sentence in cast_facts and a different person
    # every time she came up
    "orbit": {
        "enabled": True,
        "max_people": 40,
        "max_facts": 8
    },

    "him_profile": {
        "enabled": True,
        "every_hours": 24,
        "digests": 40,
        "min_digests": 8
    },

    "afterthought": {
        "enabled": True,
        # not instantly: she has to have sat with it for a moment
        "min_seconds": 45,
        "window_minutes": 12,
        "base_probability": 0.10,
        # only unease adds; each is measured from its own baseline
        "awkward_weight": 0.35,
        "unsaid_weight": 0.25,
        "craving_weight": 0.20,
        "read_ignored_bonus": 0.20,
        # a read is "read and said nothing" only after this long: at 47 seconds
        # he is typing, and she wrote "you read it and vanished again" over a
        # reply that landed while her bubble was still going out
        "read_silence_minutes": 4,
        # the re-roll window: a message gets a SECOND once-only chance when his
        # read has sat unanswered (the warm roll lands ~1 minute in, before a
        # read can have sat read_silence_minutes, so the ignored bonus never
        # applied; and past window_minutes the impulse's cooldowns held every
        # path shut until minute 45)
        "ignored_window_minutes": 30,
        "max_probability": 0.65,
        "max_per_day": 2,
        "max_bubbles": 2,
        "phone_access_factor": {"free": 1.0, "glance": 0.4, "none": 0.0}
    },

    "receipts": {
        # inferred read receipts: Telegram window in front after her message = read;
        # PC busy but chat never opened = seen; PC quiet = unseen
        "enabled": True,
        # Which desktop app counts as him reading her. This is the ONLY route
        # by which she learns he has read something: LINE gives a bot no
        # read-receipt event either ("you can't use the Messaging API to verify
        # that a message you sent was read"), so the window sensor is it,
        # whichever channel is live. Switching to LINE while this still said
        # Telegram made her blind to him reading her.
        "telegram_process_names": ["Telegram.exe", "Unigram.exe", "LINE.exe"],
        # Which window title counts as HER conversation is her own name and
        # nothing else (`sim/receipts.py`). There used to be a list here to add
        # more titles to it, and in both characters' files it held one entry
        # which was that same name; dropped 2026-09-04, his call.
        # no input at all for this long and he is not at the machine, whatever
        # happens to be on screen
        "idle_after_minutes": 20,
        "read_min_seconds": 2
    },

    "bz": {
        # B-zombie experiment, S arm (sim/bz.py, bzombie/CONTRACT.md). Six
        # starting changes, each behind its own switch, all off by default so
        # a live character is untouched.
        # 1. state as an order: one call per reply writes one in-character
        # order, placed last in her prompt
        "order": False,
        # with the order on, the mood_tags line and the register clause are
        # dropped unless kept here
        "keep_mood_tags": False,
        "keep_register": False,
        # 2. situation lines byte-identical across the last N persona calls
        # are flagged; cut_constant drops them from the prompt
        "cut_constant": False,
        "constant_window": 8,
        "constant_min_chars": 12,
        # lines containing any of these stay (persona and rules text)
        "protect": ["you are ", "never ", "always ", "rule"],
        # 3. the order names what he said or asked; a code check records it
        "answer_first": False,
        # 4. embedding echo counts, fed to the order. threshold 0 = the
        # embed pool's own calibrated floor
        "echo": False,
        "echo_pool": "messages",
        "echo_threshold": 0.0,
        "echo_window": 12,
        # 5. mood words say rising or easing, not the level
        "trend": False,
        "trend_delta": 6.0,
        "trend_history": 12,
        # 6. reality labels on wonder, foresight and spiral rows; recall
        # renders them; a check flags reply claims that match no input
        "reality": False
    },

    "bz_s10": {
        # S arm surface checks (persona/s10.py, tk-7wb and tk-wnp). Pure code,
        # no model call of its own; both off by default so a live character is
        # untouched, the bz S arm turns them on (bzombie/arms/s/make_run.py).
        # 1. bubble budget: how many bubbles a reply may have, from how much
        # he wrote. The prompt states it and the split enforces it (extra
        # lines are folded into the last bubble, never dropped).
        "budget": False,
        # [up to this many words, bubbles]; the first row he fits in wins
        "budget_table_en": [[3, 1], [10, 2], [25, 3], [60, 4]],
        # the same for a message in Japanese, counted in characters
        "budget_table_ja": [[6, 1], [20, 2], [50, 3], [120, 4]],
        # bubbles for a message longer than the last row
        "budget_over": 5,
        "budget_min": 1,
        # state moves it down by state_delta (once) when energy is under
        # tired_energy or tension with him / anger at him is at upset_from
        "budget_tired_energy": 30,
        "budget_upset_from": 40,
        "budget_state_delta": -1,
        # 2. repetition check: a draft is read against her last `window` sent
        # lines and his last message; on a finding it goes back once to the
        # persona's redraft with a short note (never a second time)
        "repeat_check": False,
        "repeat_window": 40,
        # character n-gram Dice at or above this is a near-duplicate line
        "repeat_dice": 0.6,
        "repeat_min_chars": 8,
        # a shared run of this many words (English), or characters (Japanese)
        "repeat_phrase_words": 4,
        "repeat_phrase_ja_chars": 8,
        # share of an opener's bigrams found in his message to call it an echo
        "repeat_echo": 0.6,
        # overlap with an unanswered question of hers to call a question a re-ask
        "repeat_reask": 0.4,
        "repeat_kinds": ["near_dup", "phrase", "opener", "signoff", "reask", "echo"]
    },

    "reunion": {
        # When he was last at the stage, for a visual-novel character
        # (`sim/reunion.py`). The channel stamps him on every touch
        # (`channels/vn_bot.py`) and the persona reads one line on his next
        # turn: how long he was gone. It replaces the read-receipt and
        # inferred-presence model for a VN, which has no away channel -- he is
        # either at the stage or the story is not happening. Off by default.
        "enabled": False,
        # Being away is a message gap: this long or longer with nothing from
        # him. Six hours is the classification, not the visit -- the stage
        # touch only says he came back.
        "min_away_minutes": 360,
        # A touch within this many seconds counts as still present.
        "present_window_seconds": 120
    },

    "notes": {
        # reading his notes on purpose (his mention, director's choice, /read).
        # She skims: opening + ending + a few catchy middle paragraphs, at most
        # skim_chars in total, skim_pieces pieces. Never the whole file.
        "enabled": True,
        "skim_chars": 1800,
        "skim_pieces": 5,
        "index_in_prompt": 20,
        "index_max": 200,
        # the director may open at most this many notes per day on her own
        "director_max_per_day": 3
    },

    "phone": {
        # she reads his activity feed only when she looks at her phone.
        # Whether she looks is felt, not timed (phone.look): after
        # digest_min_minutes, each tick a probability from curiosity +
        # boredom + loneliness, scaled down when she can only glance or is
        # with people; at sure_from_curiosity she checks the moment she can;
        # otherwise she sometimes sees the app and leaves it. A look takes
        # look_relief off curiosity.
        "digest_min_minutes": 8,
        "look": {
            "enabled": True,
            "base_probability": 0.45,
            "curiosity_weight": 0.8,
            "boredom_weight": 0.3,
            "loneliness_weight": 0.2,
            "glance_factor": 0.35,
            "with_people_factor": 0.3,
            "sure_from_curiosity": 75,
            # How long he has been quiet is the strongest reason to check, and
            # it is a fact rather than a mood, so it gets its own term instead
            # of being routed through the curiosity gauge (which other things
            # push to the floor). ignored_weight is the same gap when he read
            # her and said nothing.
            "silence_weight": 0.45,
            "ignored_weight": 0.70,
            "silence_cap_hours": 6,
            "sure_from_silence_hours": 10,
            "look_relief": 15
        },
        # when she looks, the app also shows his PC's live status (what is in
        # front, how long since he touched it); kept in her context this long
        "live_line": True,
        # How long he has to have been off the machine before the digest stops
        # being news and becomes history. Past this her phone leads with the
        # absence -- "he has not touched his machine for 9h; nothing has
        # happened on it since" -- and the digest follows as what it showed when
        # he last was. Once a four-hour-old digest read as the
        # present tense and she texted him as though he were sitting there.
        "stale_minutes": 45,
        "live_line_max_age_minutes": 45,
        # the app also shows the shape of his notes folder (titles only,
        # newest first) and the shape of his day (first activity, long quiet)
        "vault_catalogue_items": 25,
        "day_shape": True,
        # how much of the feed the digest is written from, per look. The
        # same for both characters (his call, 2026-09-04): the digest of his
        # machine is as rich for the first as for the second, and the only
        # difference the design wants is WHEN it arrives -- her phone look,
        # never live -- and that the app showed it rather than she watched
        # it. At 9000 and six she was handed a fifth of what the resident
        # got and asked for a glance
        "max_raw_chars": 40000,
        "max_entries_per_look": 12,
        # anything older than this is skipped, not read: she was asleep or the
        # bot was down, and the app does not show her yesterday as news
        "max_entry_age_hours": 8,
        # ONE running account of the last this many hours, replaced on every
        # look (kv `phone_account`), rather than a fresh digest of each batch
        # of flushed entries. The writer is handed the account it wrote last
        # time plus the raw material since, and returns the account again: the
        # last hour in full specifics, an older stretch compressed to a line,
        # anything past the window dropped, and the length rule is the size of
        # the whole account rather than of the new part. A batch per flush left
        # her prompt showing the last batch dated "N minutes ago", with a seam
        # at every look and whatever fell between two of them told twice or not
        # at all
        "rolling_hours": 2,
        # past this many pending flushes the oldest are dropped, so a long
        # absence does not become a dozen looks reporting stale news
        "max_backlog_entries": 12,
        # A look whose fingerprint holds nothing the last look did not makes no
        # call and leaves the standing account alone. The fingerprint (what
        # processes were in front, which sites, whether pictures were opened,
        # which notes, whether media played) was already computed and already
        # logged; what followed it was a paid rewrite of the same stretch every
        # time. It matters most for a character who is inside the machine and
        # therefore looks on every tick. A forced look (`/look`, the catch-up)
        # is never skipped.
        "skip_unchanged": True
    },

    # What the resident character sees because she is on his machine
    # (resident/sight.py): a note he opens she has read, and she sleeps when he
    # sleeps. Only for a character whose sheet says `sees_him: resident`;
    # Config.REQUIRES switches it off for everyone else.
    "resident_sight": {
        "enabled": True,
        "poll_seconds": 10,
        # the glance: the page in front of him, read every poll from the
        # window title. A page about a work he has stayed on this long is
        # resolved -- her record, what she read before, then a search with her
        # name beside the title -- and is the thing in the room for
        # glance_fresh_minutes; her own work is a reason to reach out first
        # (glance_impulse_bonus, on the impulse's scale; watching's is 14)
        # once he has been on it glance_settle_seconds. The same page is not
        # resolved again inside glance_again_hours.
        "glance_enabled": True,
        "glance_dwell_seconds": 15,
        "glance_settle_seconds": 45,
        "glance_fresh_minutes": 25,
        "glance_again_hours": 12,
        "glance_impulse_bonus": 18.0,
        # He is "here" while his machine has seen input this recently. The
        # idle seconds say he is at the desk; the glance and the activity
        # classifier say what he is on. Together they are the observation the
        # impulse weighs as "here but not attending her"
        # (`sim/impulse.py:here_not_attending_bonus`).
        "here_seconds": 120,
        # a vault note in front of him this long counts as open
        "note_open_seconds": 20,
        # the whole note up to this; beyond it the beginning and the end
        "note_max_chars": 6000,
        "min_note_chars": 80,
        # a note he keeps writing in is read again after this, not on every save
        "reread_after_seconds": 900,
        # a note read this recently is pinned into her next reply
        "fresh_minutes": 30,
        # asleep once his machine has been idle this long inside the night
        # window, from the minute he stopped; awake the moment he touches it
        "sleep_after_idle_minutes": 40,
        # sleep can only begin with an idle stretch that STARTED between
        # night_start and sleep_latest_start; a machine that goes quiet in the morning is not sleep
        "night_start": "22:00",
        "sleep_latest_start": "05:00",
        # and she is up by this whether or not he is back: past it, an idle
        # machine is him out for the day
        "night_end": "11:00",
    },

    # What he is reading in a Japanese visual novel, out of the text hooker's
    # own files (sensors/eroge_monitor.py: the per-game record of the lines the
    # hook caught, the per-line event stream with a wall-clock time on it, and
    # the game library with the visual-novel-database id and the cast). The
    # card for a game comes from the public database (sensors/vndb.py), free
    # and anonymous, once per game.
    #
    # OFF by default and on for the character who is on his machine. The
    # master switch below assigns it to `sees_him: resident`, so a character
    # who learns what he does from snapshots she has to go and fetch cannot
    # have it switched on by an edit to her config alone -- that is a decision
    # about what she can see, and it is his to make.
    "eroge": {
        "enabled": False,
        # his text hooker's own directories, read-only and never written
        "cache_dir": "eroge/luna/cache/translation_record",
        "userconfig_dir": "eroge/luna/userconfig",
        # nothing hooked for this long is nobody playing, and the same gap
        # ends a session -- so a resume simply looks like a start
        "stale_minutes": 10.0,
        # Where his current stretch of READING begins is a cursor, not a
        # timer: it moves only when a skip run breaks the stretch or when the
        # window below overflows. A pause of an hour with the game open does
        # not move it and costs nothing.
        #
        # Lines arriving faster than this are him holding the skip button, not
        # reading. Measured across many sittings: the median gap between lines is 5.0 seconds,
        # the first percentile 1.19 seconds, 99.4% slower than one line a
        # second. Skipped lines are excluded entirely and never summarised.
        "skip_lines_per_second": 1.0,
        # the raw text handed to the digest, taken from the END. Past this the
        # cursor moves forward until what is left fits, which is also what
        # catches a hooked menu or a line repeating in a storm.
        "max_raw_chars": 16000,
        # and a floor before a call is worth making: fewer new read lines than
        # this and the last digest stands. A game left open in the background
        # for hours therefore costs nothing and says nothing new.
        "min_new_lines": 20,
        # the scene digest's ceiling, the same as the watching module's
        "max_chars": 600,
        "card_max_chars": 600,
    },

    "vault_snoop": {
        # Not a timer and not a window: she snoops when she feels like it. A
        # felt probability per tick, the same idiom as the phone's look --
        # pushed by the uneasy gauges (anxiety, loneliness, jealousy,
        # curiosity), only when she is alone with a free phone (nobody snoops
        # with friends around), rarer than a glance at the app because it is
        # a more loaded act. Late night raises it; nothing forces it. The old
        # fixed window + his-PC-idle were dropped 2026-08-19: that window never fired.
        "enabled": True,
        # base is the floor: what she does on a day when nothing is wrong. At
        # ~36 alone-with-her-phone ticks in a free day it works out near one
        # snoop a day, with roughly a quarter of calm days having none.
        "base_probability": 0.035,
        "anxiety_weight": 0.18,          # each gauge adds max(0, value - ITS baseline)/100
        "loneliness_weight": 0.15,       # * weight -- unease only ever adds. Centring on a
        "jealousy_weight": 0.18,         # flat 50 pinned p at zero (jealousy rests at 15),
        "curiosity_weight": 0.09,        # and two-sided terms ate the base on her good days
        "night_bonus": 0.05,             # added between night_start and night_end
        "night_start": "23:00",
        "night_end": "02:30",
        "sure_from_anxiety": 85,         # this wound up: she just does it
        "min_minutes_between": 180,      # spacing is the only cap; no per-day limit (his call)
        # the coast case: she is in bed, meant to be asleep. Checked every poll
        # through the night, so the per-check odds are scaled hard down and it
        # only counts for the first lying_awake_minutes of the sleep block
        # (lying awake is how it starts; nobody snoops at 5 am).
        "lying_awake_factor": 0.025,
        "lying_awake_minutes": 90,
        # WHICH notes she can open. A uniform draw over the whole vault was 9%
        # prompt-engineering scratch (an LLM system prompt landed in a live
        # sample) and mostly stale reference; the daily note is the one place a day is actually written down. His format is a leading date.
        "daily_notes_only": True,
        "daily_note_regex": r"^\d{4}-\d{2}-\d{2}",
        "min_note_bytes": 200,           # skip the empty and one-line stubs
        "recent_notes_pool": 20,         # draw from the newest N; 0 = all of them
        "files_per_snoop": 2,
        # a nervous late-night skim: shorter than a daytime read
        "skim_chars": 1200,
        "skim_pieces": 4,
        # Downloads come along with every snoop: what was torrented this week (qBittorrent's on-disk state, read-only, no login;
        # sensors.torrent_backup_dir) is in the same late-night read as the
        # notes, one reaction. Recent downloads are read from the client's on-disk state.
        "downloads_enabled": True,
        "downloads_window_days": 7,
        "downloads_max_items": 12
    },

    "talkapp": {
        # TALKAPP: the messenger she lives in (talkapp/server.py, a separate
        # hub process; channels/talkapp_bot.py is the adapter on the same
        # nine-method seam the LINE experiment proved). His phone reaches the
        # hub over Tailscale (tailscale serve fronts localhost with HTTPS);
        # the hub itself binds localhost and never faces the internet.
        # enabled switches the live channel; console dry runs are unaffected.
        "enabled": False,
        # a reply is one to three bubbles and each one used to ping his phone,
        # because the Android service posts a notification per socket event.
        # Inside this many seconds of the last one from the same character,
        # the notification is UPDATED instead (all the lines of the burst in
        # it, no sound, no heads-up). Measured against her real sends: half
        # the gaps between bubbles are 6s and nine in ten are under 48s, so
        # 45 keeps a burst together and still pings for an afterthought that
        # arrives a minute later. Served to the app in /chars, so it changes
        # without a new APK.
        "notify_burst_seconds": 45,
        "host": "127.0.0.1",
        "port": 8765,
        # how long the bot waits for the hub at boot before giving up:
        # run.cmd started before talkapp.cmd was a two-second fatal
        "boot_wait_seconds": 120,
        # the second wall behind the tailnet; the server refuses to start
        # without one. Set the real value in config.json, like bot_token.
        "token": "",
        # web push to his phone when the page is not open
        "push_enabled": True,
        # how long one typing signal keeps the indicator lit
        "typing_seconds": 9,
        # hub-side message log length per character
        "log_keep": 3000,
        # how often the adapter pushes her reads / group chat / presence up
        "state_push_seconds": 20,
        # hub-side peer mailbox length per character. Not cleared on read,
        # so a character who is down misses nothing (talkapp/server.py).
        "peer_keep": 400
    },
    "vn": {
        # The visual-novel channel: her turns on a koikano stage instead of in
        # chat bubbles. It is picked by `vn.enabled` ahead of TALKAPP and
        # Telegram in scail.py App.__init__; with it off the fork runs on the
        # phone as before. The view is served by a stdlib HTTP server inside
        # the channel, so no hub process and no network are needed.
        "enabled": False,
        "host": "127.0.0.1",
        "port": 8770,
        # Where the VN view and the koikano assets live. The corpus is read in
        # place, never copied or written: the renderer may keep using it.
        "character_dir": "extracted_games/koikano/by_character/MOMOKA_百花",
        "inventory": "extracted_games/koikano/koikano_work/inventory/expression_inventory.json",
        "labels": "extracted_games/koikano/koikano_work/inventory/expression_labels.json",
        "reviewed_labels": "",
        "sprite_dir": "png_sprites",
        "face_dir": "png_faces",
        "voice_dir": "voice",
        # the player page (reused from the phase-1 prototype) and the one dir
        # this channel writes into
        "view_dir": "view",
        "out_dir": "data/vn",
        # the face she rests on before her first turn and when a feeling is
        # outside her recorded set
        "default_expression": "neutral",
        # How the sprite is framed. The canvas is drawn this many times the
        # viewport height, anchored to the top, so the bottom cut of the art
        # (her socks -- she has no feet) falls below the visible area and she
        # reads from the head to about the knee. 1.0 shows the whole figure.
        "sprite_zoom": 1.55,
        # Idle motion on the stage: a slow breathing bob (a few pixels, a few
        # seconds a cycle) and, off by default, a slow lateral sway. The page
        # reads these as its own defaults; a player can switch either off in
        # the view. The channel's default is deliberate for this stage, so it
        # beats `prefers-reduced-motion`; that machine setting only decides
        # when the player and the channel have both said nothing.
        "idle_motion": True,
        "idle_sway": False,
        # The staging pass's backgrounds and the emotion overlays, read in
        # place from the same corpus as the sprites. Both are the game's
        # extracted art and belong to no character (`tools/isolation.py`,
        # MACHINE). `bg_dir` is walked once by `sim/scene.py`; `emotion_dir`
        # is the overlay art a label can carry.
        "bg_dir": "extracted_games/koikano/png/scene/bg",
        "emotion_dir": "extracted_games/koikano/png/scene/emotion"
    },
    "scene_director": {
        # The VN staging pass (`sim/scene.py`): where she is being shown,
        # decided before her draft is written and appended inside the
        # situation block, never the cached system half. Off unless a
        # character's bundle turns it on; the channel draws what it returns.
        "enabled": False,
        # whether the `scene_director` role is asked at all. Off and the
        # staging comes from the scene's own words and the mood band.
        "use_model": False,
        "bg_dir": "",
        "default_bg": "BG02a01",
        # a place name -> a background id, extending the verified table in
        # `sim/scene.py`
        "places": {}
    },
    "stage_manager": {
        # The out-of-character console behind the director button
        # (`sim/stage_manager.py`, `docs/2026-09-17_vn_stage_manager_scope.md`).
        # He talks to it in English; it knows the scene and the catalogs and
        # proposes a scene for his approval. Nothing is written and no scene is
        # started until he approves. Off unless a character's bundle turns it on.
        "enabled": False,
        # how many turns of the console chat ride in its context
        "history_turns": 20
    },
    "emotion": {
        # The 28-label feeling for the VN face (`sim/emotion.py`). Local and
        # deterministic by default; `use_model` asks the `emotion` role.
        "enabled": False,
        "use_model": False,
        "default_label": "neutral"
    },
    "quality": {
        # The last look at her draft (`sim/quality.py`): forbidden phrases,
        # repeated openers and runs, and the length. Post-processing only, so
        # her prompt is untouched.
        "enabled": False,
        # whether `quality_rewrite` (her voice) is asked to shorten an
        # over-long draft, rather than cutting it at a sentence end
        "use_model": False,
        # 0 means the length is not capped
        "max_chars": 0,
        "repeat_run": 16,
        "recent_messages": 8,
        "openers": True,
        # phrase -> what replaces it; an empty replacement drops the phrase
        "forbidden": {},
        # The tics that are HERS and that a model overdoes. The authored bible
        # measures them on her lines (`docs/koikano-bible-hyakka.md`: the speech
        # guide and the mechanisms), so they are capped per draft, not banned:
        # the first `max` occurrences stand and the rest are dropped, which
        # leaves the habit reading as hers instead of as a model's fill.
        # `phrases` maps the literal mark to its per-draft cap; `doubled_group`
        # caps the wider immediate-repeat move (a 2-4 character kana/kanji
        # group said twice, the doubled ん counted separately in the guide) by
        # count. `source` names the evidence so a cap can be audited and
        # reverted. The bible reads most of these per register and cannot be
        # read here, so the caps are set loose enough to leave an H scene alone.
        "caps": {"source": "", "phrases": {}, "doubled_group": 0}
    },
    "shape": {
        # Code decides how much she says; the model decides what. Unbounded,
        # every reply was 3-6 articulate bubbles (median bubble 89 chars, 6%
        # under 30, over four days measured) because a model completes.
        # sim/shape.py draws a shape from her state and the occasion, the
        # persona is told it, and the draft is enforced against it: one
        # redraft, then whole bubbles are dropped. Hurt collapses the draw
        # to curt/short -- being properly upset is LESS text, never more.
        "enabled": True,
        # Whether the drawn length is TOLD to her. False and she is told
        # nothing about how much to send and nothing about bubbles: she writes
        # what she writes and it goes as written. The classes and the weights
        # were measured off the first character's English, and on a character
        # they were never fitted to they came out as one line four times in
        # ten -- 39 of 39 messages a single bubble, 36% ending on a question
        # back at him. His call for the second character, 2026-09-02: let her
        # reply how she wants.
        #
        # This is the LENGTH only. The draw still runs and the engage line
        # still goes in, because what his message obliges her to take up is
        # about WHAT she answers, not how much -- and it is the line that
        # stops her answering a different question than the one asked.
        "tell_length": True,
        # name: [max bubbles, max characters in all]. URLs are free.
        "kinds": {
            "curt": [1, 40],
            "short": [1, 90],
            "plain": [2, 220],
            "full": [3, 420],
            "spill": [6, 900]
        },
        # base weights of the draw before her state moves them
        "weights": {"curt": 6, "short": 34, "plain": 38, "full": 18, "spill": 4},
        # upset = max(anger, tension with him, sadness). Past these the draw
        # collapses; the register line says how it sounds, this says how much.
        "upset_curt_from": 55,
        "upset_short_from": 40,
        # upset = max(tension with him, anger if aimed at him, sadness if
        # aimed at him x this); the collapse eases back toward the ordinary
        # draw over this many hours after the rupture's last attempt
        "upset_sadness_weight": 0.6,
        "upset_fade_hours": 36,
        "tired_energy": 30,
        # a spill needs what a 1am essay actually needs: alone, free phone,
        # late, and pressure (max of unsaid, loneliness) at least this
        "spill_pressure_from": 65,
        "night_from": 22,
        # him asking something, or writing a lot, earns a fuller answer
        "question_full_bonus": 8,
        "long_msg_chars": 240,
        # completeness is a variable: probability she is told she may answer
        # only part of what he sent (higher when upset)
        "engage_partial_p": 0.35,
        "engage_upset_p": 0.75,
        # tk-mfx: when his message asks her to go along or agree (sim/shape.py
        # wants_kind) and her state plus her card's base temper say she would
        # resist, the plan line says push back first. Off by default; the bz S
        # arm turns it on with a base and a `how` per character.
        "pushback": {"enabled": False, "base": 0.3, "threshold": 0.5, "min_gap_minutes": 20, "how": ""}
        # NO enforcement at all, his call: the drawn line is the LAST
        # instruction in her prompt so the first draft is the right size, and
        # whatever she wrote is what goes. No second call, no trim, no bubble
        # cap applied afterwards; `max_chars` is a guide inside the drawn
        # line, never a cut.
    },
    "situation_block": {
        # the <situation> block of the persona prompt: how many of today's
        # events and how long each, the caps on the day summaries, how long
        # a cut draft stays readable, and how long after his last message a
        # rhythm notice / his mood still count as "now" (a latency statistic
        # from an exchange ten hours ago sat beside "he has been silent 10 h")
        "events_max": 4,
        # How often she is handed one thing off his screen to remark on. It
        # was once per TITLE, and a machine that never stops producing titles
        # had her remarking on his browsing in every reply; a person looking
        # over a shoulder does not. Zero means every fresh title, as before.
        "noticed_min_gap_minutes": 60,
        # What of the block a character is shown at all. Every line below had
        # a reader in the first character's world and none in the second's,
        # and a line with no reader is not neutral: she reads it. Translating
        # it would not help; removing it does. Defaults keep the first
        # character's block as it is; the second character's config is lean.
        "primitives_numbers": True,   # "WHERE HE STANDS WITH YOU: he is on your mind 100; ..." -- the numbers line; the gate CONDITIONS stay either way
        "habits_line": True,          # "his day, as you have it: in a program (18-23) ..." every message; a MISSED habit still shows
        "ledger_preamble": True,      # the three-line explanation over the day's ledger; off, it is one word
        # How many of the day's LATER blocks the ledger names, with their
        # times. 0 shows only the block she is in now, which is what every
        # reader of the ledger has ever been given.
        #
        # A character who is asked what she is doing later has to answer from
        # something, and with nothing in front of her she answers from her own
        # last message. The second character told him on the Friday evening
        # that her recording was 午前 -- the morning -- with her own week file,
        # her household and the next day's plan all saying the evening; the
        # claim then sat in the thread and she repeated it four times over the
        # next twelve hours, including in a prompt whose own morning thought
        # said 今夜は収録 two lines above. This is the fact she was missing.
        # It is a number rather than a flag because a thirteen-block day would
        # otherwise put nine lines in her situation.
        "ledger_rest_of_day": 0,
        "lore_preamble": "full",      # "full" or "short": what is said over the things she happens to know
        "feel_tags_max": 0,           # feeling tags she is shown, strongest first; 0 = every one the state produces
        "event_chars": 160,
        "summary_chars": 420,
        "unsent_hours": 6,
        "unsent_chars": 220,
        "live_hours": 1.5,
        # What the narration of his machine competes at once she has already
        # been shown it. A fresh one is still pinned and rides as news; this
        # is the second and every call after, and at 0.25 it reaches her when
        # what he said reaches for it. She reported something off his screen
        # in 29 of 95 replies, at 32% whether or not he had asked her
        # anything, which is a slot rather than somebody noticing.
        "digest_stale_weight": 0.25,
        # Her own repeated phrases, counted in code off her own last messages
        # and named to her. Her coinage was written back into her prompt by
        # the roles that read her record and she then used it in ten replies
        # in twelve hours; this is her hearing what she has been reaching for.
        "own_phrases_from": 16,       # how many of her own last messages are read
        "own_phrases_min": 4,         # how many of them a phrase must be in
        "own_phrases_max": 5,         # how many phrases are named
        # how she would actually get to a place her day names, off the place
        # graph (embodied/situation.py: travel_line, trip_line). She said she would
        # do her homework "on the bus" and there is no bus in the map; a model
        # with no fact invents the one that sounds right. 0 trip_lines turns
        # the routes off; the travel line (what modes exist for her at all)
        # always goes in.
        "trip_lines": 2,
        "trip_min_minutes": 12,
    },
    "delivery": {
        # a continuity editor reads each draft against what she demonstrably
        # knows (facts, his list, notes read, the digest, recent chat) and, on
        # a real contradiction, sends her back once with a plain note. A
        # character's sheet may say she has not got it (`mechanisms_absent:
        # continuity_editor`), which is how it is off for the second character;
        # with it off there is no call and no evidence bundle, one line at boot
        # instead of one per reply, and the repetition the gate finds in code is
        # logged and nothing else
        "editor_enabled": True,
        # and it runs only when the draft has something to check -- a number,
        # a word from a fact about him, a run shared with one of her recent
        # messages (Persona._editor_needed); a draft with none of those gets
        # no call, because a pass verdict does nothing (2026-09-04)
        "editor_gate": True,
        # how much of the conversation it is shown, and how it reaches past
        # that. The window is small on purpose: a long record is a worse
        # thing to read carefully, and the whole of it does not fit. So the
        # draft's own words are searched against everything older instead
        # (sim/recall.older_messages, no model call), and only the few
        # messages the draft actually touches are added. Without this, a
        # true quotation of anything past the window read as an invention
        # and the draft was binned and paid for twice.
        "editor_recent_messages": 10,
        "editor_lookback": True,
        "editor_lookback_max": 5,        # at most this many older messages
        "editor_lookback_scan": 1500,    # how far back the search itself reads
        "editor_lookback_min_overlap": 2,  # words shared with the draft before a message counts
        # and only DISTINCTIVE words count: one appearing in more than this
        # share of the record is furniture, not a reference. At 6 per cent
        # a generic filler line reached five unrelated messages; at 2 it reaches none, and a distinctive line still reaches the evening it belongs to.
        "editor_lookback_common_share": 0.02,
        # a reply to him that comes back mostly in Japanese is flagged in the log and the events -- never redrafted
        "language_flag": True,
        # her own bubbles in her history carry [sent / read] stamps in her
        # time, so being left on read is visible in the record itself
        # a timed-out send is not a send: retry, and only mark a bubble
        # delivered if it actually left
        "offline_wait_seconds": 900,   # hold a bubble this long for the network
        "send_attempts": 3,
        "send_retry_seconds": 4,
        # how long the words themselves take, before her state multiplies it
        "compose_seconds": [6, 50],
        # a jump in the record used to look exactly like the next thing
        # anybody said. The silences are what the history is about.
        "gap_marker_hours": 1.5,
        # mood-aware delivery: how fast and how much she answers depends on
        # how she is. Read delay is scaled by a factor from tension with him,
        # mood and craving (clamped); the glance reply chance moves with it;
        # the persona gets a register line ("short and cool" / "eager").
        "mood_delivery": {
            "enabled": True,
            # gone off him: at or below cold_from her register is cold and
            # her delay grows by cold_weight per 100 below it; at or below
            # hate_from she does not like him and is not hiding it
            "affection_cold_from": 30,
            "affection_hate_from": 15,
            "cold_weight": 0.8,
            # the `standing` meter with him: at or under standing_low her
            # register is careful and deferential; at or over standing_high
            # with tension down it is easy and sure of itself
            "standing_low": 35,
            "standing_high": 70,
            "tension_weight": 1.5,
            "mood_weight": 0.8,
            "craving_weight": 0.9,
            "energy_weight": 0.5,
            "comfort_weight": 0.5,
            "min_factor": 0.4,
            "max_factor": 3.0,
            "cool_tension": 35,
            "eager_craving": 70,
            # holding something she is not going to say: slower to answer, and
            # it shows in how she answers
            "shame_weight": 0.9,
            "anger_weight": 0.35,
            "awkward_weight": 0.8,
            "sad_register": 45,
            "shame_register": 45,
            "anger_register": 40,
            "awkward_register": 45,
            "surprise_register": 35
        },
        # She stops when he cuts in. Her bubbles go out one at a time with a
        # typing delay between them, and the whole batch used to land whatever
        # arrived meanwhile, so he could answer her second bubble and still get
        # the third and fourth as though she had not noticed. The first one is
        # already out of her mouth; from the second on she can stop.
        # If the model comes back with nothing, his message is already marked
        # read and she has silently ignored him forever. That is the one thing
        # this system must never do, so it goes back in the queue.
        "reply_retries": 2,
        # How many of her own last messages a new bubble is checked against
        # before it goes out (`Persona._drop_already_sent`, near_duplicate).
        # The burst-level dedup only ever saw a run inside one reply, so the
        # same sentence went to him twice two hours apart, after he had
        # answered it. 12 of hers is about a morning of talking; the pair that
        # got through were five apart.
        "no_repeat_recent": 12,
        # A reply can also be lost between being generated and being sent: the
        # bubbles sit on the delivery thread's queue, and if the process stops
        # there they are gone while his message is already marked read. Checked
        # once at boot -- his newest message read with nothing after it, inside
        # this many hours, means the reply died in flight and goes back.
        "recover_lost_reply_hours": 6,
        "interruptible": True,
        # While she is mid-message the only thing that matters is whether he
        # cuts in, and a full pass of the loop can take half a minute when there
        # are model calls in it -- long enough that his message reached the store
        # after her last bubble had already gone (2026-08-21 09:50). During a
        # send the loop does nothing but collect the post.
        "busy_poll_seconds": 2,
        # ...but never for longer than this, so a stuck pending count cannot
        # spin the loop forever doing nothing else
        "busy_poll_max_seconds": 180,
        "typing_seconds_per_char": 0.045,
        "typing_min_seconds": 4,
        "typing_max_seconds": 45,
        "read_delay_free_seconds": [20, 240],
        "read_delay_glance_seconds": [120, 900],
        "glance_reply_probability": 0.4,
        "split_on_blank_lines": True
    },

    "timeline": {
        "compile_at": "23:55",
        # ...but the compile FLUSHES a live exchange, and the group chat can now
        # run to 02:20, so a fixed hour cut off the late night it had just been
        # given permission to have. It holds while she is mid-conversation and
        # until the night's last light, and a night that ran past midnight is
        # closed in the small hours -- by `compile_quiet_by_hm` at the latest.
        "compile_hold_for_chat": True,
        "compile_quiet_by_hm": "04:00",
        # the day's prose can come back as one short paragraph while every
        # other field is full (08-27: 82 scenes in, 556 chars out, covering
        # its first two hours). Below `narrative_min_chars` on a day with at
        # least `narrative_min_scenes` in it, the compile asks once more with
        # the span of the record in front of it. A thin day is otherwise
        # silent: it parses, it saves, and the hole only shows months later.
        "narrative_min_chars": 900,
        "narrative_min_scenes": 25,
        "narrative_retries": 1
    },

    "telegram": {
        "bot_token": "",
        "chat_id": "",
        "max_message_length": 4096,
        "poll_seconds": 5,
        # messages he sent while she was down are still messages; do not drop them
        "flush_queue_on_start": False,
        # console mode prints outbound messages instead of sending; used by dry runs
        "console_only": False
    },

    "sensors": {
        "enabled": True,
        # WHAT WAS FETCHED ABOUT THE WORLD, KEPT ONCE FOR THE WHOLE
        # MACHINE (machine/retrievals.py): the page for an episode and the
        # verdict a judge reached on it, a page condensed by a role that names
        # nobody, a web search, a game's database card. Both characters read
        # and write it, because a television episode is the same episode
        # whoever is watching and one fetch should serve both; what each of
        # them made of it stays in her own save. A fetch is claimed before it
        # starts, so two processes reaching the same thing in the same minute
        # pay for it once.
        "retrievals_db": "data/retrievals.db",
        # a claim older than this was left behind by a process that was killed
        # mid-fetch -- a stop is Stop-Process -Force -- and is taken over
        "retrievals_inflight_stale_seconds": 600,
        # how long to wait on the other character's fetch of the same thing
        # before going ahead alone. It is also the timeout on a claim held
        # across a whole reading-up (`sim/recap.py`), which is a search, four
        # page fetches, a digest each and a judge; a claimant that comes back
        # with nothing releases the claim marked failed, so the ones waiting
        # stop waiting long before this.
        "retrievals_inflight_wait_seconds": 120,
        # An episode he watched whose record holds no synopsis and no raw page
        # is a reading-up that lost a race rather than one nobody ran. It is
        # tried again as soon as the machine's shared store holds a page for
        # it, and otherwise this long after the last try, at most this many
        # extra times for the episode (`WatchingHim.owed`). 0 retries turns
        # the repair off.
        "retrievals_retry_after_minutes": 30,
        "retrievals_max_retries": 2,
        "telemetry_jsonl_path": "data/telemetry_feed.jsonl",
        "telemetry_state_path": "data/telemetry_state.json",
        "telemetry_pending_log_path": "data/telemetry_pending.txt",
        "telemetry_poll_interval_seconds": 30,
        # The buffer reaches the feed on a character count, on this
        # heartbeat, or the moment a bot asks (the request path below). A
        # flush is a file write and costs nothing; what costs is the digest a
        # character makes of the feed, and that is her own decision, so a
        # short heartbeat is cheap. Five minutes is the floor under how stale
        # the feed can be when nobody has asked; the request path is what
        # makes a reply current.
        "telemetry_heartbeat_interval_seconds": 300,
        "telemetry_flush_threshold_chars": 18000,
        # A bot about to build a reply touches this file. The machine's own
        # loop sees it within telemetry_now_interval_seconds, re-reads the
        # sources, writes whatever is held as an entry with flush_reason
        # "requested" and removes the file; an empty buffer writes nothing and
        # the file goes anyway. Pictures opened shortly before a message had their tags still in the buffer.
        "telemetry_flush_request_path": "data/telemetry_flush_request",
        # how long the bot waits for a new entry to reach the feed after
        # asking, before going ahead with what the feed already held
        "telemetry_flush_wait_seconds": 4,
        # His machine is watched once. The collector is its own process
        # (machine/collector.py, started by talkapp.cmd) and a bot reads what it
        # writes; True runs the whole sensor stack inside the bot instead, which
        # is only right when there is exactly one bot on the machine.
        "collector_in_process": False,
        "telemetry_now_path": "data/telemetry_now.json",
        "telemetry_now_interval_seconds": 3,
        "telemetry_now_stale_seconds": 30,
        "system_monitor_enabled": True,
        "system_monitor_poll_ms": 1000,
        # What anything he had open may be CALLED in front of a character:
        # one list of patterns (regular expressions, case-insensitive) that
        # every sensor emitting such a name asks (sensors/blocklist.py).
        # The window monitor blanks the title at the source
        # (SystemMonitor._poll_foreground) -- the window and its process still
        # count, its name does not -- when the title matches, or when the
        # process is one of window_title_blank_processes; a file manager's
        # title is the FOLDER it is showing and an editor's is the PATH of the
        # open file, so that one blanking covers all three. The browsing-log
        # reader (sensors/chrome_monitor.py) drops a visit whose PAGE TITLE
        # matches, which the address-based chrome_junk_filters cannot do: a Google search whose query was a path once put this project's
        # name in her digest from a google.com address.
        # A coding session's title became a keyword in her
        # model of his habits, and the assistant's animated status glyph,
        # repainting the title twice a second, was reported to her as him
        # working across 110 windows in two minutes (2026-09-04). Every
        # terminal title is blanked because the assistant's session titles
        # carry no word a pattern could catch.
        "window_title_blocklist": ["^[◐◑◒◓✳✴✻✽✶]", "Claude Code", "- Claude$", "^Claude$", "Claude Platform", "^claude\\.ai/", "^Administrator: +SCAIL ", "TALKAPP hub", "SCAIL"],
        "window_title_blank_processes": ["WindowsTerminal.exe", "cmd.exe", "conhost.exe", "powershell.exe", "pwsh.exe", "OpenConsole.exe"],
        # Programs whose own NAME no character may be shown, on top of their
        # titles. Blanking the terminal titles left "WindowsTerminal" itself,
        # and for a terminal the program name IS what he is doing: it once stood in the second character's rolling account of his
        # machine, her window trail, her live status line, her picture of his
        # habits, her facts about him and her own written reflections, with
        # every title already blank. A window on this list keeps its clock and
        # its minutes and loses its name (sensors/blocklist.py `hidden`), so
        # the account still says he was at the machine for those minutes
        # instead of reading as a quiet stretch.
        # python.exe and pythonw.exe are the characters themselves, the hub and
        # the mirror daemon. The busiest-process line named `python` twice and
        # the second character reported it to him as something on his machine.
        "hidden_processes": ["WindowsTerminal.exe", "cmd.exe", "conhost.exe", "powershell.exe", "pwsh.exe",
                             "OpenConsole.exe", "python.exe", "pythonw.exe"],
        # How hard he was working, said as a band rather than as a count
        # (sensors/bands.py). Every figure a character ever recited about his
        # machine came out of one function and it rounded nothing; the second
        # character's accounts carried a mean of 38 numerals each and she read
        # the keypress total and the uptime back to him. Typing is banded on
        # keys per minute rather than on the total, because a total says
        # nothing without the span it happened in; a burst is long past
        # burst_long_seconds. The clock a window run started at and how long
        # it ran are NOT banded: she is watching him continuously and what
        # time he got up is hers to know (his call).
        "bands": {
            "typing_hard_per_minute": 60.0,
            "typing_steady_per_minute": 20.0,
            "typing_light_per_minute": 4.0,
            "burst_long_seconds": 30.0,
            "uptime_long_days": 7.0,
            "uptime_days_days": 2.0,
            "uptime_today_days": 0.5,
            "clicks_many": 60.0,
            "clicks_some": 10.0,
        },
        "system_stats_interval_seconds": 60,
        "typing_burst_gap_seconds": 3,
        "image_viewer_processes": ["JPEGView.exe", "jpegview.exe", "JPEGView64.exe", "IrfanView.exe", "i_view64.exe"],
        "chrome_process_names": ["chrome.exe"],
        "chrome_history_path": "",
        "chrome_max_raw_entries": 20000,
        "chrome_idle_gap_threshold_minutes": 20,
        # Addresses no character may be shown. The reader drops a visit whose
        # URL contains any of these (both browsers: the Firefox reader adds
        # firefox_junk_filters to this list). Three kinds:
        # sign-in pages, whose query strings carry live tokens; the machine's
        # own addresses, which is where her messenger and his other chatbot
        # software sit; and the tools this project is built and served with.
        # The assistant's chat titles are the reason for the third kind -- his browser history holds them, all of them a page title away from being
        # read to her as a site he visited. Same fault as the terminal titles
        # window_title_blocklist blanks, one source further out -- and the
        # page TITLE of a visit that survives these is read against that same
        # blocklist, because an address says nothing about what the page was
        # called.
        "chrome_junk_filters": ["chrome-extension://", "chrome://", "accounts.google.com", "mail.google.com", "login", "signin", "oauth", "google.com/url?", "localhost", "127.0.0.1", "claude.ai", "claude.com", "anthropic.com", "openrouter.ai", "deepseek.com"],
        # Live page-content scraping (CDP into his running Chrome) is OFF by
        # design: it needs a Chrome launched with --remote-debugging-port and
        # the cold-fetch fallback can't read logged-in / JS pages. The digest
        # is fed by the browsing log instead (title + host per visit, from
        # chrome_monitor.get_history_since). Leave this False unless a
        # debug-port Chrome is set up (see PROJECT.md).
        "chrome_scrape_enabled": False,
        "chrome_scrape_time_threshold_seconds": 120,
        "chrome_scrape_interaction_threshold_keypresses": 5,
        "chrome_scrape_max_text_length": 5000,
        "chrome_cdp_port": 9222,
        # Image viewing reaches her as windows, not one line per picture. A run
        # of images viewed with less than image_window_gap_minutes between them
        # is one "session". A session of image_window_summarize_min or more is
        # collapsed to a single dated summary (when, how many, who/series,
        # ratings, average score); a shorter one keeps full per-image detail.
        # image_context_max_detailed caps how many individual images can carry
        # full detail across one look; past that, even short sessions summarize.
        "image_window_gap_minutes": 5,
        "image_window_summarize_min": 3,
        "image_context_max_detailed": 6,
        # image runs older than this are not described at all; then at most
        # image_max_windows_per_look of what is left
        "image_max_age_hours": 4,
        "image_max_windows_per_look": 3,
        "scrape_log_path": "data/scrape_log.txt",
        # His second browser.  The path is
        # per-machine and lives in config.json like chrome_history_path, not
        # here; the profile is set per machine.
        "firefox_enabled": True,
        "firefox_history_path": "",
        "firefox_junk_filters": ["about:", "moz-extension://", "view-source:", "file:///"],
        "audacious_process_names": ["audacious.exe"],
        # qBittorrent's on-disk torrent state (.fastresume + .torrent per
        # torrent); read-only, no Web UI needed. Empty = the default location
        # %LOCALAPPDATA%\qBittorrent\BT_backup.
        "torrent_backup_dir": "",
        "vault_path": "",
        "vault_extensions": ["*.md", "*.txt"],
        # and this project's own documents when he copies one into the vault:
        # she read the voice bench as a note about her and came out of it "a
        # number and a cost" (2026-09-04)
        "vault_ignore_patterns": [".obsidian", ".trash", "yukarin-voice-models.md"],
        "vault_read_time_threshold_seconds": 120,
        "vault_max_file_length": 1500,
        # how much of the end of an edited note rides along in the telemetry entry
        "vault_excerpt_chars": 700,
        "gelbooru_enabled": False,
        "gelbooru_api_key": "",
        "gelbooru_user_id": "",
        "gelbooru_ratings_json_path": "data/gelbooru/ratings.json",
        "gelbooru_ground_truth_json_path": "data/gelbooru/ground_truth.json",
        "gelbooru_cleaned_json_path": "data/gelbooru/cleaned_for_llm.json",
        "gelbooru_request_delay": 0.1,
        "gelbooru_cache_path": "data/gelbooru/gelbooru_cache.json",
        # user counts as AFK for the snoop gate after this many idle seconds
        "user_idle_seconds": 1200,
        # MyAnimeList: public list + recently-watched RSS, no auth. Activity
        # reaches her through the phone digest; the shelf summary sits in her
        # system prompt; /anime gives him a dated recap.
        "mal_enabled": True,
        "mal_username": "",
        # optional: a MAL API v2 client id (X-MAL-CLIENT-ID). Public endpoints
        # work without it; with it the official API is used for the list.
        "mal_client_id": "",
        "mal_poll_minutes": 30,
        "mal_list_refresh_hours": 12,
        "mal_list_path": "data/mal_list.json",
        "mal_state_path": "data/mal_state.json",
        "mal_shelf_watching_max": 10,
        "mal_shelf_completed_max": 12,
        # Per-episode watch history (exact minute he watched each episode),
        # built by tools/mal_history.py into its own SQLite DB. The bot only
        # READS that DB (no browser): new episode events since it last looked
        # reach her through the phone digest, the way list activity does. On
        # first sight it takes the current tip as the mark so the backfilled
        # history is not dumped into her lap.
        "mal_history_enabled": True,
        "mal_history_db": "data/mal_history.db",
        "mal_history_max_events": 8,
        # a note he writes on an anime is an event, not just a field on a
        # card the lookup might one day build
        "mal_notes_max_events": 5,
        "mal_notes_max_chars": 400,

        # X (Twitter): her account, read through a real logged-in Chrome
        # profile (x_login.cmd opens it for the manual login). Read-only
        # until x_actions_enabled; the Following tab only, never For You.
        # Pacing is the ban-safety: few scrolls, uneven pauses, a gap between
        # looks, a daily cap. The simulation gates looks further (phone in
        # hand, bored) on top of these.
        "x_enabled": True,
        "x_profile_dir": "",
        # A COPY of that profile, logged into the same account, for the offline
        # tools (tools/x_analyze.py). Her look, her posting and the scenery
        # harvest share the one profile and take turns for it, and a second
        # Chrome on a held profile kills the first -- so a tool that wanted a
        # session had to wait for a gap between her looks. On its own copy it
        # does not. Blank = use hers and take the turn.
        "x_tools_profile_dir": "",
        # no window: her looks, her posts and the scenery harvest all run
        # through this profile, and a Chrome opening itself on his desktop
        # every half hour is not something she does. Headless Chrome names
        # itself "HeadlessChrome" in the user agent, so open_driver rewrites
        # the UA over CDP and hides navigator.webdriver on every document.
        # Turn this off to WATCH a look happen when the parsing breaks;
        # `/headless off` does the same live, for the next session only.
        "x_headless": True,
        # the tag store: what a picture IS, kept once and shared, never in
        # her save because an image is the same image whoever looks at it
        "x_images_db": "data/x_images.db",
        "x_data_dir": "data/x",
        "x_window_size": "1100,900",
        "x_page_wait_seconds": 12,
        "x_scroll_pause_min": 2.5,
        "x_scroll_pause_max": 6.5,
        "x_feed_scrolls_min": 3,
        "x_feed_scrolls_max": 7,
        "x_following_reloads": 4,
        # the per-look glance at the top of the followers page (newest first):
        # how many screens. Two is about twenty accounts, which is more than a
        # day's new followers and cheap enough to do on every look.
        "x_followers_scrolls": 2,
        "x_following_reload_wait_min": 20,
        "x_following_reload_wait_max": 45,
        "x_session_min_gap_minutes": 35,
        "x_max_sessions_per_day": 10,
        # her hand on the account (tomoe/curation.py). Off = every decision is
        # written to actions.jsonl as dry_run and nothing is sent. Posting
        # has its own switch.
        "x_actions_enabled": False,
        "x_posting_enabled": False,
        # uBlock Origin, loaded into every scraping Chrome (her X profile and
        # the MAL one) so an ad is never read as content. See docs/selenium.md for
        # why three separate things are needed to make Chrome accept it.
        "chrome_extension_dir": "data/extensions/uBlock0.chromium"
    },

    "vision": {
        # Her eyes. Gemini on Vertex AI, its own provider and its own key (the
        # service account in secerts/), nothing to do with the DeepSeek roles in
        # `models`. Two callers: a photo he sends over Telegram, and the images
        # on X posts she stops at. Everything else she knows is text.
        "enabled": True,
        "key_path": "secerts/project-7a56f373-e1de-4a94-9b8-bf340e6401b9.json",
        "project_id": "",                # blank = take it from the key file
        "region": "global",              # gemini-3.8-flash is global-only on this project
        # the BARE id: `sensors/vision.py` builds
        # .../publishers/google/models/<model>:generateContent, so the publisher
        # is already in the path and a "google/" prefix (the OpenRouter form)
        # would 404
        "model": "gemini-3.8-flash",
        "temperature": 0.2,              # description, not invention
        # Gemini 3.x always spends some tokens thinking even at budget 0, and
        # thinking shares max_output_tokens with the answer. Too tight a cap
        # returns an empty answer, the same trap DeepSeek's reasoning sets.
        "thinking_budget": 0,
        "max_output_tokens": 1200,
        "timeout_seconds": 45,
        "fetch_timeout_seconds": 15,
        "max_image_bytes": 8000000,
        "max_images_per_call": 4,
        # a hard ceiling on Gemini calls a day, per character (each save keeps
        # its own count in kv vision_calls, so it survives a restart; kept in
        # memory it was reset by every restart and held on two days in nine).
        # The harvest and her own looks share it; a spent day stops both
        "max_calls_per_day": 80,
        # When a call fails for a reason that will pass -- the credentials, the
        # quota, a 5xx, the network -- wait and come back rather than asking
        # again straight away. Doubles per consecutive failure to the cap, and
        # one good answer clears it.
        "backoff_seconds": 60,
        "backoff_max_seconds": 1800,         # backstop; 4 looks x 8 = 32, plus his photos
        "prompt_photo": "prompts/vision_photo.txt",
        "prompt_x": "prompts/vision_x.txt",
        # a photo he sends: she looks at it before she answers
        "telegram_enabled": True,
        # the X timeline: only the posts she would actually stop at, and never
        # more than x_max_per_scroll of them in one look
        "x_enabled": True,
        "x_max_per_scroll": 8,       # measured: her sessions carry 5-17 eligible
                                    # images, median 8; 5 covered only 65% of them
        "x_max_images_per_post": 2,
        "x_max_output_tokens": 900
    },

    "network": {
        # How the machine losing its connection is handled and logged. A 66
        # minute DNS outage on 2026-08-20 produced ~90 identical poll-error
        # lines and no statement that the network was down.
        "down_after_failures": 3,     # consecutive failures before we call it down
        "recheck_seconds": 30,
        "skip_model_work": True,      # while down, do not burn LLM retries on a dead link
        "resend_undelivered": True    # her bubbles wait for the network instead of vanishing
    },

    "tts": {
        # how many of her own recent spoken lines the voice call is shown, so
        # it does not say the same thing twice. 21 near-duplicate pairs in 40
        # lines before this, including one repeated three minutes later with
        # the punctuation moved.
        "no_repeat_recent": 8,
        # Voice lines only, never whole messages. Every reply gets one short
        # spoken Japanese phrase (the persona may supply it inline as
        # [voice: ...]; otherwise the voice model writes one from the bubbles).
        # The gate below can still hold it; by default it holds nothing.
        "enabled": True,
        "always": False,
        # Whether a `[voice: ...]` line the persona writes on its own is spoken
        # and attached to the reply. She was never asked for one; the history
        # shows her earlier voice notes as labels and the model imitated them,
        # so a reply carried a spoken aside in a dialect that is not hers,
        # attached to the text as if it were its reading. False: nothing in
        # her history invites one, one written anyway is stripped and never
        # spoken, and audio on a message is only its own text, read on request
        # (`on_demand`). His call for the second character.
        "aside_from_persona": False,
        # The other way of having a voice: she sends no voice note at all, and
        # every line she writes carries a speaker in the app that renders it
        # when he taps it and plays it from the cache every time after. The two are independent, so a character can have both,
        # either or neither. Nothing is synthesised until he asks for it.
        "on_demand": False,
        # Where her voice comes from when the VN channel speaks a line:
        # "tts" synthesises every line, "exact" plays a recorded koikano clip
        # only when the line is one she said verbatim on tape, and
        # "approximate" also plays a near miss -- long enough, high normalized
        # edit-distance ratio, one unique best by a margin, and the words
        # unchanged (only pauses may differ). The stage control overrides this;
        # a wrong clip is worse than silence, so the default is exact. The old
        # boolean `clip_partial` still seeds the mode where this is absent
        # (false -> exact, true -> approximate). Read by
        # `channels/vn_bot.py:clip_for`; see `docs/voice.md`.
        "voice_mode": "exact",
        "minimax_script_path": "",
        "minimax_config_path": "",
        # Whose voice. The MiniMax config file is shared by everything on this
        # machine and names one voice, so without this a second character
        # speaks in the first one's voice. Empty means "whatever the MiniMax
        # config says", which is the existing behaviour for the first
        # character; a character's own config sets her own id.
        "voice_id": "",
        # Explicit MiniMax delivery is opt-in per character. Unmapped labels
        # leave emotion unset so the model reads the line naturally.
        "emotion_enabled": False,
        "language_boost": "",
        "pronunciation_dict": {},
        "interjection_tags": False,
        # The MiniMax async task API (what the script uses) takes minutes per
        # line at times (3-11 min seen 2026-08-19); the synchronous endpoint
        # returns a short line inline in about a second. "sync" renders
        # directly with the same voice settings and falls back to the
        # script; "script" is the old path.
        "mode": "sync",
        "sync_endpoint": "https://api.minimax.io/v1/t2a_v2",
        "sync_timeout_seconds": 45,
        "async_fallback_timeout_seconds": 35,
        # a line still unsent when the process stops is re-queued on the
        # next boot, unless it is older than this (a voice note for a
        # message from an hour ago would be strange)
        "recover_max_age_minutes": 30,
        "ffmpeg": "ffmpeg",
        "max_per_day": 200,
        "cooldown_minutes": 0,
        "require_alone": False,
        "with_self_started": True,
        "max_chars": 40,
        "cache_dir": "data/voice"
    },

    "logging": {
        "out_dir": "logs",
        # sim / dry runs log here instead, so they never touch a live run
        "dry_run_out_dir": "logs/dryrun",
        # a dated copy of world.db at every day compile
        "backup_dir": "data/backups",
        "backup_keep": 21,
        "db_path": "",
        "console_status_interval_seconds": 30
    }
}


def _merge(defaults, override):
    out = copy.deepcopy(defaults)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


class Section:
    def __init__(self, data):
        for k, v in data.items():
            # dicts that are DATA rather than sub-sections: they get iterated
            # or .get()-ed by name, so wrapping them in a Section breaks them
            # with "config key 'get' is not defined in DEFAULTS"
            setattr(self, k, Section(v) if isinstance(v, dict) and k not in (
                "gauges", "weights", "self_open_weights", "phone_access_factor", "source_words",
                "load_weights", "compounds", "relief", "relief_gap_minutes", "gauge_baselines",
                "half_life_days", "valence_gauges", "arousal_gauges", "kinds", "place_map", "food_hours",
                "kind_queries", "section_default", "covered_by", "cos_by_pool",
                "forbidden", "caps") else v)

    def __getattr__(self, name):
        raise AttributeError(f"config key '{name}' is not defined in DEFAULTS")


class Config:
    _drift_reported = False   # once per process, not once per construction

    def __init__(self, path="config.json", character_file=None):
        # character_file overrides world.character_file, so a harness can run
        # a different person without editing his config.json
        self._character_override = character_file
        self.path = path
        loaded = {}
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
        merged = _merge(DEFAULTS, loaded)
        if merged != loaded:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(merged, f, indent=2, ensure_ascii=False)
        self.raw = merged
        for k, v in merged.items():
            setattr(self, k, Section(v) if isinstance(v, dict) else v)

        # what this character turns out to be, in lines, for the log to record
        # once it exists (`_note`)
        self.boot_notes = []
        # her temperament before the check, so a gauge she adds is validated
        # by the same rule as one the mechanism ships with
        self.character_sheet = {}
        # Did what kind of thing she is actually get applied? The rules used
        # to hang off reading her sheet, so a config with no sheet beside it
        # was built with every subsystem on and every path live, and nothing
        # said so. Recorded rather than assumed, because the failure is silent
        # by nature: a character who was never narrowed looks exactly like a
        # character who needed no narrowing.
        self._existence_applied = False
        self._apply_character(merged)
        if not self._existence_applied:
            raise SystemExit(
                "[config] what kind of character this is was never applied: no subsystem was "
                "switched off, no world path was blanked, and the existence table was not "
                "checked.\n         `Config._apply_character` must reach `_existence_implies` "
                "on every path, with or without a character sheet.")
        self._check_person_files(merged)
        self._check_gauges(merged)
        self._check_drift(loaded, DEFAULTS, where=path)

        # The sensor modules were written against a flat config object. Give
        # them one, built from the sensors section, so they stay untouched.
        self.sensor_view = Section(merged["sensors"])
        self.sensor_view.out_dir = merged["logging"]["out_dir"]

    def _note(self, line):
        """A line about what this character is: printed now, and kept so the
        log can have it too.

        `Config` is built before `logger.setup` opens `session.log`, so the two
        lines naming the sections a sheet switches off went to stdout and
        nowhere else -- and `yukarin.cmd` does not redirect stdout, so no run
        of hers had ever recorded which of her subsystems are off.
        `scail.App.__init__` re-emits these into the log as soon as it is
        open."""
        print(line)
        self.boot_notes.append(line)

    def _apply_character(self, merged):
        """The character sheet's own temperament, over the mechanism's defaults.

        `gauge_baselines` retunes what already exists -- a calm character's
        anxiety baseline is 25 and a raw one's is 55, and neither is a property
        of the simulation. `gauges` adds ones this person needs and another
        does not; they carry a full spec because `_check_gauges` will demand it
        of them exactly as it does of the built-in set.

        The sheet is optional; what follows from what kind of thing she is, is
        not. `character.existence` is answered in the config whether or not
        there is a sheet beside it, so `_existence_implies` runs at the end of
        this either way. It used to run only where the sheet was read, so a
        config with no sheet -- or with an unreadable one -- kept every
        in-world subsystem switched on, kept every world path pointing at
        somebody's household, and never reached `_check_existence_table`, the
        check that refuses to boot when a switchable section has not been
        assigned to a kind of character."""
        sheet = self._read_sheet(merged)
        self.character_sheet = sheet
        if sheet:
            self._from_sheet(merged, sheet)
        self._existence_implies(merged)
        self._mechanisms_absent(merged, sheet)

    def _read_sheet(self, merged):
        """Her sheet, or nothing if she has not got one."""
        path = self._character_override or merged.get("world", {}).get("character_file", "")
        if not path or not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError) as e:
            print(f"[config] character sheet unreadable ({e}); the defaults stand")
            return {}

    def _from_sheet(self, merged, sheet):
        """What her sheet says about her, over the mechanism's defaults."""
        temp = sheet.get("temperament") or {}
        spec = merged["state"]["gauges"]
        retuned = added = 0
        for name, base in (temp.get("gauge_baselines") or {}).items():
            if name in spec:
                try:
                    spec[name]["baseline"] = float(base)
                    retuned += 1
                except (TypeError, ValueError):
                    pass
        for name, g in (temp.get("gauges") or {}).items():
            if name in spec:
                spec[name].update(g)
            else:
                spec[name] = dict(g)
                added += 1
        # `gauges_absent` is the counterpart of `gauges`, and it exists because
        # a character can lack something the mechanism assumes. A person inside
        # a machine has no hunger, no fatigue and no body to feel comfortable
        # in, and before this there was no way for a sheet to say so -- only to
        # retune a baseline, which leaves the gauge alive at a number that
        # describes nothing. A gauge the mechanism computes from (mood reads
        # every gauge's kind) simply stops contributing when it is not there.
        gone = 0
        for name in (temp.get("gauges_absent") or []):
            if spec.pop(name, None) is not None:
                gone += 1
        # what kind of existence she has, if she says (config.character.existence)
        ex = sheet.get("existence")
        if isinstance(ex, dict):
            merged["character"].setdefault("existence", {})
            for k in ("embodied", "in_world", "sees_him", "has_account", "with_him"):
                if k in ex:
                    merged["character"]["existence"][k] = ex[k]
            # `self.character` was built into a Section before this method
            # ran, so mutating the dict underneath it is not enough -- the
            # Section holds its own copy of a nested dict. Rebuild it, or the
            # sheet's answer is read from the file and then thrown away.
            self.character = Section(merged["character"])
        # who she is on MyAnimeList, if her sheet says: the id decides whether
        # the role check runs at all, so it belongs beside the rest of what
        # she IS rather than in a generated file that could lose it
        if str(sheet.get("mal_person_id", "") or "").strip():
            merged["character"]["mal_person_id"] = str(sheet["mal_person_id"]).strip()
            self.character = Section(merged["character"])
        # her own record, if her sheet has one: the paths live on the sheet
        # so that a regenerated config cannot lose them (it did, silently:
        # `tools/make_yukarin_config.py` had no override for them and
        # `sim/lore.py` returns nothing on an empty path). The sheet wins.
        # A `lore` block with no path in it still switches the retrieval on,
        # so that the blank path is answered by the one boot line that says
        # she has no record rather than by silence, which is the shape the
        # regeneration fault had. A path that names a file which is not on
        # disk still stops the boot: that is a wrong path, not an absent one.
        lore = sheet.get("lore")
        if isinstance(lore, dict):
            merged.setdefault("lore", {})
            for k in ("file", "triggers_file", "memory_file", "memory_triggers_file"):
                if lore.get(k):
                    merged["lore"][k] = str(lore[k])
            merged["lore"]["enabled"] = True
            self.lore = Section(merged["lore"])
        if retuned or added or gone:
            who = (sheet.get("name") or {}).get("full") or sheet.get("id", "?")
            print(f"[config] {who}: {retuned} baseline(s) retuned, {added} gauge(s) of her own"
                  + (f", {gone} she does not have" if gone else ""))

    # A switch a sheet may name that is not a whole section, because the thing
    # it turns off has not got one. The continuity check on her drafts lives
    # under `delivery`, with the rest of what happens to a message on its way
    # out, and `delivery` carries no `enabled` flag of its own.
    NAMED_SWITCHES = {"continuity_editor": ("delivery", "editor_enabled")}

    def _mechanisms_absent(self, merged, sheet):
        """The machinery this character has not got: `mechanisms_absent` on her
        sheet, the counterpart of `gauges_absent` beside it.

        This is NOT the existence table, and the difference is the whole reason
        it exists. `REQUIRES` derives what a character has from what KIND of
        thing she is -- a body, a world, an account -- and none of these follows
        from those four answers. The continuity check on her drafts reads a
        draft against facts about him, her own claims and the whole record as
        well as against a world, so a character with no world still has three of
        its four kinds of evidence; not answering him on purpose is about the
        relationship, which every character has. Each row here is a measured
        decision about ONE character, with the measurement on the sheet beside
        it, and it is on the sheet rather than in her generated config because
        the sheet wins at load: a re-run of `tools/make_yukarin_config.py`
        cannot lose it.

        A name nobody has decided about stops the boot, the way a section
        missing from `REQUIRES` does. A typo here would otherwise read as a
        mechanism switched off and leave it running."""
        gone = sheet.get("mechanisms_absent")
        if not isinstance(gone, dict):
            return
        off, unknown = [], []
        for name in gone:
            if str(name).startswith("_"):
                continue
            if name in self.NAMED_SWITCHES:
                sect, key = self.NAMED_SWITCHES[name]
            elif isinstance(merged.get(name), dict) and "enabled" in merged[name]:
                sect, key = name, "enabled"
            else:
                unknown.append(str(name))
                continue
            merged[sect][key] = False
            setattr(self, sect, Section(merged[sect]))
            off.append(str(name))
        if unknown:
            raise SystemExit(
                "[config] her sheet says she has not got %s, and there is no such section and no such "
                "named switch: %s\n"
                "         A section is switched off by its own name; anything else needs a row in "
                "Config.NAMED_SWITCHES saying which key it is."
                % (len(unknown), ", ".join(sorted(unknown))))
        if off:
            self._note("[config] and her sheet says she has not got: %s" % ", ".join(sorted(off)))

    def roles_off(self):
        """The roles in `models` this character never calls, and why.

        `/model` builds its table out of `models`, which is the same for every
        character, so the continuity check printed there with its model beside
        the roles that do run and looked live."""
        out = {}
        if not getattr(self.delivery, "editor_enabled", True):
            out["editor"] = "her drafts are not read for continuity"
        return out

    # ------------------------------------------------------------------
    # THE MASTER SWITCH: one row per switchable subsystem, naming the property
    # of a character's existence that has to be true for it to mean anything.
    # `None` is machinery -- it belongs to the mind, to the relationship, or to
    # the machine, and every character has it.
    #
    # `_check_existence_table` refuses to start if a section carrying an
    # `enabled` flag is missing from this table, so a subsystem cannot quietly
    # run for a character it makes no sense for. That is the whole point: the
    # second character's first boot gave her a school day in a ward she does
    # not live in, friends her roster had never heard of, a menstrual cycle,
    # and an X account drifting from his taste to hers, and every one of those
    # subsystems was ALREADY gated on its own `enabled` flag. What was missing
    # was any way for a sheet that says "no body, no world" to reach them.
    #
    # Derived rather than listed per character on purpose. A sheet says what
    # KIND of thing she is, once, and the consequences follow; a hand-written
    # list of flags in every new character's config is the same debt as a
    # hand-written closeness of 62.
    # ---------------------------------------------------------------- roles
    # What her character sheet is to a role that ends its system prompt with
    # her -- one row for every module that calls `role_system`, and the boot
    # refuses a caller that has no row.
    #
    # "voice": the role writes her words. Her diary, the week read back, her
    # private thoughts about him and about the people around her, the
    # half-second of measuring herself, her wondering, what today is from the
    # pillow, what she is bracing for, what she makes of what she is watching,
    # what she remembers on a cue, what she took from scrolling the account.
    # Each of these produces first-person prose that goes into her prompt or
    # her record, and each already carries its own head-voice instruction.
    #
    # "judge": the role decides something ABOUT her and hands the answer to
    # code. It is a neutral party and gets no sheet at all (his call,
    # 2026-09-05). The sheet is written in the second person and opens "You
    # are <her name> ... you never mention prompts, models, systems", and it
    # sat LAST in the system prompt, so a judge read it as its own identity:
    # measured over 2026-09-04 and 09-05, the role that picks which urge she
    # has returned a finished message in her voice instead of the
    # second-person intention it was asked for on 13 of 13 answers, and one of
    # them went into the last line of her situation block and was sent as her
    # next bubble twelve seconds later; the role that predicts his reply wrote
    # the same field in three different persons in one day; the warmth scorer
    # wrote thirteen score reasons as her, addressed to him.
    #
    # A judge that genuinely needs to know what she is like gets
    # `sim/observer.py` -- a short third-person digest of her, generated from
    # the bible and cached on its hash -- never the bible itself.
    ROLE_STANCE = {
        "diary": "voice", "weekly": "voice", "reflect": "voice",
        "reflect_cast": "voice", "compare": "voice", "wonder": "voice",
        "morning": "voice", "anticipation": "voice", "experience": "voice",
        "recall": "voice", "social": "voice",
        # one step of the chain she talks herself down, and the two that
        # rewrite what she has decided about him and about herself: her
        # sentences, held in her head and read back in her own prompt
        "spiral": "voice", "revise": "voice", "revise_self": "voice",
        # These do not call `role_system`: they build her whole voice
        # assembly through `persona.system_for` (her reply to him, her turns
        # with her own people, a turn to another running character, a post on
        # the account she looks after, and which post out of her scroll she
        # sends him). They are listed so the table names
        # every path by which her sheet reaches a system prompt, and so
        # `tools/smoke.py` can prove that no judge is on any of them.
        "persona": "voice", "cast_reply": "voice", "peer_reply": "voice",
        "x_post": "voice", "x_reply": "voice",
        # and two more that build it: the one short thing she says out loud
        # while a message goes, and what she says to a stranger in her
        # world. Both are words of hers that are stored and read back.
        "voice": "voice", "npc_moment": "voice",
        # and a fifth that does not call `role_system` either: what she would
        # do with the phone builds `persona.system_for` and offers tools. It
        # is her deciding, addressed to her in the second person, so it gets
        # her sheet like the four above it.
        "pick": "voice",
        # It decides rather than writes, and it is still hers: the question is
        # which post SHE wanted to show him, and the answer is worth nothing
        # from a neutral party reading her over somebody's shoulder. So it
        # gets her sheet, through the same assembly her reply gets, and it is
        # given no way to write words (`tomoe/share_pick.py`: two tools, no
        # free-text argument).
        "share_pick": "voice",

        "intent": "judge", "foresee": "judge", "affection": "judge",
        # the second reader of everything she carries. It used to be handed
        # her whole assembly with "YOU ARE NOT HER" after it, which is the
        # arrangement a judge reads as its own identity; it gets its own
        # instruction and her situation block now, and nothing else (his call).
        "nudge": "judge",
        "taste": "judge", "zeitgeist": "judge",
        # whether she answers a reply under one of her posts, and which one:
        # a decision handed back to code, so it gets no character sheet
        "x_reply_judge": "judge",
        # and what the account does with a post she has just sent him
        "x_repost_judge": "judge",
        # the VN staging pass and the feeling label: both decide something
        # ABOUT her and hand the answer to code, and neither writes a word
        # anyone reads, so neither gets her sheet. The rewrite role does write
        # in her words -- it shortens her own draft -- so it is a voice.
        "scene_director": "judge", "emotion": "judge",
        "quality_rewrite": "voice",
        # the out-of-character console behind the director button: it talks to
        # the player ABOUT the scene and never writes in her words, so it is a
        # judge and gets no character sheet
        "stage_manager": "judge",
    }

    REQUIRES = {
        # CONTACT WITH HIM. `with_him: none` on the sheet is a character who has
        # no chat with him, and these are the sections that are the relationship
        # and nothing else: what she feels and expects of him, the ick, the
        # rupture, what she holds back from him, what she wonders about him,
        # her thoughts about him, his hours, his meters, the typed urge to
        # write first and the afterthought once she has. The impulse function
        # itself has no flag and is stopped in `App.maybe_impulse`; the pick
        # stops offering `text_him`. `approach` is a discovery from the snoop
        # and so needs sight of him rather than contact.
        # SIGHT OF HIM. `sees_him: none` on the sheet is a character who has
        # no view of his machine at all, and these are the sections that read
        # it: the telemetry stack itself (`sensors`), the profile written from
        # her digests, the read receipts inferred from his screen, his notes
        # and his vault, what he plays as he plays it, and the habit facts from
        # his anime history. A character held digests of his screen with `none` on her sheet,
        # because nothing but the pick and the persona had ever read the
        # answer. The scenery harvest is assigned to the account: it runs on
        # the account's browser profile, which is blanked for a character
        # without one, and a world's reader had it fail on an empty path.
        # the mind: her past kept as cards, and the meaning-search over it
        "episodes": None, "embed": None,
        # a body: something that eats, sleeps, bleeds, gets cold, has money
        "health": "embodied", "needs": "embodied", "environment": "embodied",
        "money": "embodied", "diet": "embodied", "situation": "embodied",
        "household": "embodied",

        # a world: people around her who are not him, and places to be in
        "cast": "in_world", "cast_bond": "in_world",
        "social": "in_world", "exchange": "in_world",
        "family": "in_world",
        "world_shared": "in_world",
        "scenery": "has_account", "trains": "in_world",
        "hazards": "in_world",

        # a world SHE KEEPS. Every section here WRITES the world rather than
        # reading it: the people's own week and the pressures behind it, what
        # is going round, what the day's record says happened, the people
        # around the people, the strangers she passes, measuring herself
        # against the room, and who privately holds what about whom. Two
        # processes in one world both running these are
        # two planners over one roster, each writing into its own save and
        # only the owner's reaching the world file -- which is what the third
        # character's first forty-five minutes were: her own pool of rumours,
        # her own arcs, and eight beats planned for people whose day the
        # owner had already fixed. A character with no world at all lacks
        # this property too, so these stay off for her exactly as before.
        "cast_arcs": "world_owner", "showrunner": "world_owner",
        "gossip": "world_owner", "events": "world_owner",
        "orbit": "world_owner", "npc": "world_owner",
        # `social_graph` reaches its readers a different way from the seven
        # above it, and is here for the same reason. The object is built for a
        # reader too, and every reader of it (the cast turns, the day planner,
        # the spiral settle, the witnessed-goal price, the ick, the promises,
        # /graph and the app's backstage) takes the owner's compiled edges out
        # of the world file through it. Being off is what stops the daily paid
        # update over her own witnessed record and the writing into her save:
        # a reader had seeded twelve edges of her own and would have moved
        # them nightly against edges the owner had already settled.
        "compare": "world_owner", "social_graph": "world_owner",

        # an account of her own, out in public
        "posting": "has_account", "curation": "has_account",
        # answering the people who answer her: no account, nobody to answer
        "x": "has_account",
        # ...and which post out of it she sends him: no account, no posts
        "share_pick": "has_account",

        # everything else is the mind, the relationship or the machine, and
        # every character has it whatever kind of thing she is
        "affection": "with_him", "afterthought": "with_him", "agenda": None, "anime_sense": "sees_him",
        # two running characters talking to each other: the mind and the
        # relationship, and a character with no contacts has no peer
        "peer_talk": None,
        "anticipation": None, "approach": "sees_him", "attachment": "with_him",
        "attention": None, "beliefs": "with_him", "care": "with_him", "coherence": None,
        "commitments": None,
        # emotional contagion is the route by which his mood becomes hers.
        # A character with no chat with him has no such route, and with it
        # on she was asked every tick what he sounded like and once stored
        # the answer -- a row reading "None" in the save of a girl who has
        # never spoken to him.
        "contagion": "with_him", "derive": "with_him", "diary": None,
        # the per-play dossier: the machine's own join over his player's log,
        # his list mirror and the machine's retrieval store, written by the
        # mirror daemon rather than by any character's loop. No character
        # reads it and none of it touches a save, so it needs no property of
        # hers -- but it carries a flag, so it has to be decided here.
        "dossier": None,
        "expect": "with_him", "experience": None, "foresight": "with_him", "goals": None,
        "him_profile": "sees_him", "ick": "with_him", "intent": "with_him", "memory": None,
        # Going and reading about a thing he mentioned is a web search, and it
        # needs no body and no world. It sat in the `in_world` block for a
        # week because it was filed next to family and gossip rather than
        # thought about, and that one row switched off the ONLY path from
        # something he says to the Japanese synopsis fetcher -- for the
        # character who is in many of the shows on his list.
        "lookup": "with_him",
        "morning": None, "notes": "sees_him", "nudge": "with_him", "primitives": None,
        "reactions": None, "recall": None, "recap": None, "receipts": "sees_him",
        "reunion": "player_driven",
        "bz_channel": None,
        # the hosted classifier beside the gates it sharpens (`typesafe.py`,
        # `docs/system-one.md`): the machine and the mind, so every character
        # may have it and a bundle decides which uses are on
        "typesafe": None,
        "reconcile": None, "reflect": "with_him", "rhythm": "with_him", "rupture": "with_him",
        # the machine's own stop, and every character resumes from one: what
        # kind of thing she is decides nothing about whether she was running
        # when the machine went down
        "downtime": None,
        "self_memory": None, "sentiment": None, "shape": None, "spiral": None,
        # the relationship: what she does with what she has seen of him
        "stances": None,
        # her own record of herself: every character may have one, and a
        # character with no file simply retrieves nothing
        "lore": None,
        "stress": None, "vault_snoop": "sees_him", "weekly": None,
        # what she would do with the phone in her hand: the mind and the
        # relationship. WHICH tools she is offered follows from her existence
        # (`PhonePick.offered`) rather than from a second switch -- a
        # character with nobody in her world is not offered a group chat, and
        # one with no account is not offered a feed.
        "pick": None,
        # the one control over the language she is addressed in: the mind and
        # the relationship, and every character is addressed in something
        "language": None,
        # hers alone: the property is `sees_him: resident`, which the switch
        # below turns into the missing property "resident" for everyone else
        "resident_sight": "resident",
        # what he is reading in a visual novel. The lines themselves are
        # the running text of the scene while he reads it, which is not
        # what "shown as-is" has covered anywhere else here, so it is
        # assigned to the same property as her other direct sight of his
        # machine rather than to None: a character who sees him in
        # snapshots does not get it by having her config edited.
        "eroge": "resident",
        # noticing what he watches is about HIM, so it needs no property of
        # hers; what it can then say depends on `watching.her_seiyuu_name`
        "watching": "sees_him",
        # which of several candidate works he means: a question about the
        # world, off the reply path, needing no body, no world and no account
        "which_one": None,
        # whether a work is one of HERS. Not a property of her body, her world
        # or an account -- it is a fact about her career -- so the property is
        # derived from the one thing that decides it: whether her sheet or her
        # config names a person on MyAnimeList. Empty and the section switches
        # itself off at her boot with the reason printed.
        "role_check": "voice_actress",
        "withholding": "with_him", "wonder": "with_him",
        "sensors": "sees_him", "talkapp": None, "tts": None, "vision": None,
        "vn": None,
        # The VN channel's own three passes: machinery of the mind and the
        # machine, off unless a bundle turns them on. A character with no VN
        # stage still has them; they simply do nothing.
        "scene_director": None, "emotion": None, "quality": None,
        # the out-of-character console behind the director button: machinery of
        # the stage, off unless a bundle turns it on, and a character with no
        # stage simply never opens it
        "stage_manager": None,
    }

    # The same switch over the `world` section, which is one flat section
    # rather than one per subsystem and so cannot carry an `enabled` flag of
    # its own. A character with no world does not merely never read the
    # household, the place graph and the school calendar -- she has no path to
    # them, so a subsystem that forgets its gate finds nothing rather than
    # finding the first character's mother. Blanked rather than repointed: an
    # empty path is honest, and a copy of somebody else's file with the names
    # changed is a second character to maintain.
    #
    # A string key is emptied, a number goes to 0 and a boolean to False.
    #
    # `home_file` is deliberately NOT in this table and must not be added to
    # it. Every key here points at the live present -- this city, this school
    # calendar, this ward's events -- and a character with no world has no
    # business reading any of it. A home file is the opposite: it is the only
    # world she does have, written from her own record, with no feed behind it.
    # Blanking it would leave her the one-block day this whole table exists to
    # stop being a lie.
    # The account's keys under `sensors`: the browser profile that is logged
    # in as her, the directory her posts and likes are written to, the image
    # store. A character with no account has no path to them, so a subsystem
    # that reads the shared X log finds nothing rather than finding the first
    # character's posts -- which is how they reached the second character's
    # system prompt as her own on 2026-09-03.
    ACCOUNT_KEYS = ("x_enabled", "x_actions_enabled", "x_posting_enabled", "x_data_dir",
                    "x_profile_dir", "x_tools_profile_dir", "x_images_db")

    WORLD_KEYS = {
        "household_file": "in_world", "places_file": "in_world",
        "geography_file": "in_world", "school_calendar_file": "in_world",
        "shared_dir": "in_world",
        "local_events_file": "in_world", "holidays_file": "in_world",
        # a public event is a thing her ward puts on; a character with no
        # world has no ward, no calendar and nothing to check a plan against
        "outing_words": "in_world",
        # the fetchers behind those two files are subprocesses with no
        # character in their arguments: one config in, one file out, so a
        # second character's national feed came back written in the first
        # one's terms, naming a brother and a father she has not got
        "zeitgeist_every_hours": "in_world", "local_events_every_days": "in_world",
        # weather is something a body is out in
        "weather_enabled": "embodied",
        # the taste sheet is the account's
        "taste_file": "has_account",
    }

    # Her part of the city, as a list rather than as a path. `PERSON_FILES`
    # below cannot see these -- there is no file to look for -- and
    # `WORLD_KEYS` cannot either, because they are not under `world`. Each was
    # the first character's neighbourhood written into the library's defaults:
    # the wards her seismic feed treats as hers, the railway lines her train
    # board watches, and what her photo harvest searches for. A character who
    # has not been given one has nothing for that subsystem to read, so it is
    # switched off at her boot with the reason printed, the way the role check
    # switches itself off for a character who is nobody on MyAnimeList.
    NEIGHBOURHOOD = {
        "hazards": ("her_wards", "which observation points are hers"),
        "trains": ("her_lines", "which railway lines are her own"),
        "scenery": ("queries", "what to search for"),
    }

    # THE OTHER HALF OF THE SAME RULE: a person-shaped path that is EMPTY while
    # the thing that reads it is running.
    #
    # An empty path is a state this project produces on purpose -- `WORLD_KEYS`
    # above empties the world's files for a character with no world, and every
    # reader of one is written as the empty case. What has never been an
    # honest state is an empty path under a subsystem that IS running: nobody
    # decided that, it is what a character who was never given a file of her
    # own looks like, and until the defaults were emptied she did not look like
    # it because she silently inherited the first character's file instead.
    #
    # Each row says when the file has to be there. `section` is a switchable
    # section: the file is needed while that section is on. `needs` is a
    # property of her existence: the file is needed while she HAS that thing,
    # which is the right test for a path no single section owns -- her map is
    # read by the day's planner, the director, the situation and the account,
    # and blanked by `WORLD_KEYS` for a character with no world, so the
    # question is whether she is in a world and not which of the four is on.
    #
    # A key that is absent from this table is a key whose empty value is a
    # designed answer: no speech guide in the other language, no beliefs about
    # him yet, no record of her own, no circle of her own.
    PERSON_FILES = {
        # a world she is in: her map, the places she keeps going back to, her
        # school's year, her family as an economy. The fourth character's day
        # planner read the first character's map and the first character's
        # household for a day, because her config named them and nothing asked
        # whether they were hers.
        "world.geography_file": (None, "in_world"),
        "world.places_file": (None, "in_world"),
        "world.school_calendar_file": (None, "in_world"),
        "world.household_file": (None, "in_world"),
        # an account of her own, out in public
        "world.taste_file": (None, "has_account"),
        # the people around her, which is the section and not the property: a
        # character with no world may still have a circle, and the second and
        # the third both do.
        "character.cast_file": ("cast", None),
        "character.cast_sheets_dir": ("cast", None),
        "cast.mechanisms_dir": ("cast", None),
        "cast.types_file": ("cast", None),
        # and her face, which is a directory NAME rather than a path
        "reactions.character": ("reactions", None),
    }

    # The rows above whose value is not a path, so only the empty test applies
    # and there is no file to look for on disk.
    PERSON_NOT_PATHS = ("reactions.character",)

    # How she learns what he is doing. A value outside this set reads as "not
    # resident" everywhere it is tested, so a typo would quietly give her the
    # app on her phone instead of his machine in front of her.
    SEES_HIM = ("digest", "resident", "none")
    WITH_HIM = ("chat", "none")

    @staticmethod
    def _check_existence_answers(ex):
        """All four answers are present, and `sees_him` is one of the three.

        An absent answer is read as "she has it" by every test of it, which is
        the same default -- runs for everybody -- that `_check_existence_table`
        refuses for a section nobody has decided about."""
        missing = [k for k in ("embodied", "in_world", "sees_him", "has_account") if k not in ex]
        if missing:
            raise SystemExit(
                "[config] character.existence does not say what kind of character this is: %s "
                "unanswered.\n         An unanswered property reads as yes everywhere it is "
                "tested." % ", ".join(missing))
        w = str(ex.get("with_him", "chat") or "chat").lower()
        if w not in Config.WITH_HIM:
            raise SystemExit(
                "[config] character.existence.with_him is %r, which is none of %s."
                % (ex.get("with_him"), ", ".join(Config.WITH_HIM)))
        seen = str(ex.get("sees_him") or "").lower()
        if seen not in Config.SEES_HIM:
            raise SystemExit(
                "[config] character.existence.sees_him is %r, which is none of %s. Anything else "
                "reads as 'not resident' and she is handed the other kind of sight."
                % (ex.get("sees_him"), ", ".join(Config.SEES_HIM)))

    @classmethod
    def _check_existence_table(cls, merged):
        """Every switchable subsystem is assigned to the master switch.

        A new section with an `enabled` flag and no row in REQUIRES is a
        subsystem nobody has decided about, and the default for an undecided
        subsystem has always been "runs for everybody" -- which is how a
        character with no body came to have a menstrual cycle. Refused at boot
        the way a gauge without `kind`/`valence`/`arousal` is refused."""
        have = {k for k, v in merged.items() if isinstance(v, dict) and "enabled" in v}
        missing = sorted(have - set(cls.REQUIRES))
        if missing:
            raise SystemExit(
                "[config] %d switchable section(s) are not in Config.REQUIRES, so nothing has "
                "decided what kind of character they are for: %s\n"
                "         Add each to the table in config.py with the existence property it "
                "needs, or None if every character has it."
                % (len(missing), ", ".join(missing)))
        stale = sorted(set(cls.REQUIRES) - have)
        if stale:
            print("[config] %d row(s) in Config.REQUIRES name a section that no longer has an "
                  "enabled flag: %s" % (len(stale), ", ".join(stale)))

    @classmethod
    def _check_role_stance(cls, merged):
        """Every role named in ROLE_STANCE is still a role.

        The other half of the guard is in `role_system` itself, which stops on
        a caller with no row; this half catches the row left behind when a
        role is renamed or removed, which would otherwise read as a decision
        somebody made about something that no longer runs."""
        models = merged.get("models") or {}
        gone = sorted(r for r in cls.ROLE_STANCE if r not in models)
        if gone:
            print("[config] %d row(s) in Config.ROLE_STANCE name a role that is not in "
                  "`models`: %s" % (len(gone), ", ".join(gone)))
        bad = sorted(r for r, v in cls.ROLE_STANCE.items() if v not in ("voice", "judge"))
        if bad:
            raise SystemExit(
                "[config] Config.ROLE_STANCE rows must read 'voice' or 'judge': %s"
                % ", ".join(bad))

    def _existence_implies(self, merged):
        ex = (merged.get("character") or {}).get("existence") or {}
        self._check_existence_table(merged)
        self._check_role_stance(merged)
        self._check_existence_answers(ex)
        self._existence_applied = True
        lacks = [p for p in ("embodied", "in_world", "has_account") if not ex.get(p, True)]
        if str(ex.get("sees_him", "digest") or "digest").lower() != "resident":
            lacks.append("resident")
        # and whether she sees him at all: a sheet answering `none` is a
        # character with no window on his machine, and the sections that
        # read it are assigned to this in REQUIRES
        if str(ex.get("sees_him", "digest") or "digest").lower() == "none":
            lacks.append("sees_him")
        # and whether she has him at all: `none` is a character with no chat
        # with him, and the relationship layer is assigned to this
        if str(ex.get("with_him", "chat") or "chat").lower() == "none":
            lacks.append("with_him")
        # and whether the PLAYER drives the story instead of her. A
        # visual-novel character is played, not messaging: her own sections
        # that only make sense when she reaches out are assigned to this, and
        # the ones that replace them (the reunion clock) stay off for a
        # character who does have a chat of her own to write into.
        if not ex.get("player_driven", False):
            lacks.append("player_driven")
        # and whether she has ever been in anything, which is the id on her
        # sheet and nothing else. Derived here rather than listed per
        # character for the same reason as the line above it: a sheet says
        # what KIND of thing she is, once, and the consequences follow.
        if not str((merged.get("character") or {}).get("mal_person_id", "") or "").strip():
            lacks.append("voice_actress")
        # and whether the world she is in is HERS to keep. One writer per
        # world (docs/shared-world.md): the character whose config says
        # `world_shared.owner`. Everybody else in that world reads the file
        # and runs none of the machinery that writes it, which is the same
        # consequence, from the same table, as having no world at all -- and
        # a character with no world is not an owner either, so the sections
        # that used to be assigned to `in_world` are assigned to this and
        # stay off for her. A character alone in a world with the shared file
        # switched off keeps writing her own world, because nobody else is
        # reading it.
        ws = merged.get("world_shared") or {}
        if not ex.get("in_world", True) or (ws.get("enabled") and not ws.get("owner")):
            lacks.append("world_owner")
        off = []
        for sect, need in sorted(self.REQUIRES.items()):
            if need is None or need not in lacks:
                continue
            if isinstance(merged.get(sect), dict) and merged[sect].get("enabled", False):
                merged[sect]["enabled"] = False
                setattr(self, sect, Section(merged[sect]))
                off.append(sect)
        blanked = []
        w = merged.get("world") or {}
        for key, need in sorted(self.WORLD_KEYS.items()):
            if need not in lacks or key not in w or not w[key]:
                continue
            w[key] = False if isinstance(w[key], bool) else (0 if isinstance(w[key], (int, float)) else "")
            blanked.append(key)
        if blanked:
            self.world = Section(w)
        if "has_account" in lacks:
            sv = merged.get("sensors") or {}
            for key in self.ACCOUNT_KEYS:
                if key in sv and sv[key]:
                    sv[key] = False if isinstance(sv[key], bool) else (0 if isinstance(sv[key], (int, float)) else "")
                    blanked.append("sensors." + key)
            self.sensors = Section(sv)
        # a world somebody else keeps gets its own line, because "not
        # world_owner" says nothing to a person reading a boot log: she is in
        # a named world and reads it.
        reading = []
        if ex.get("in_world", True) and "world_owner" in lacks:
            reading = [s for s in off if self.REQUIRES.get(s) == "world_owner"]
            off = [s for s in off if s not in reading]
        # never a reason in the general line: for a character with no world it
        # says nothing the line already says, and for a reader it is the line
        # below, in words
        lacks = [p for p in lacks if p != "world_owner"]
        if off:
            self._note("[config] not %s, so these are off: %s"
                       % (" and not ".join(lacks), ", ".join(off)))
        if reading:
            self._note("[config] she is in the world %r and does not own it, so she reads the "
                       "world file and runs none of the machinery that writes it: %s"
                       % (str(ws.get("id") or ""), ", ".join(reading)))
        if blanked:
            self._note("[config] and nothing of the world's own: %s" % ", ".join(blanked))

        # A gauge whose OWNER section is switched off is not a feeling resting
        # at its baseline: it is a feeling she has not got. Taken out of the
        # spec here, the way a sheet's `gauges_absent` takes out the four a
        # body in a real world feels, so that the state is built without it,
        # the mood computation does not average in a constant, the store stops
        # holding it, and `/sweep` does not have to call it dead. The fourth
        # character's warmth toward him read exactly 45 on all 220 status lines
        # of 2026-09-07 and still fed her mood, and her missing him moved with
        # no owner to move it. Not a removal from `config.py:DEFAULTS`, which
        # every character shares and two of them need: what a character has is
        # derived from what she is, once, here.
        spec = (merged.get("state") or {}).get("gauges") or {}
        gone = []
        for name in sorted(spec):
            owner = (spec[name] or {}).get("owner")
            owner_sect = merged.get(str(owner)) if owner else None
            if isinstance(owner_sect, dict) and not owner_sect.get("enabled", True):
                spec.pop(name)
                gone.append("%s (%s)" % (name, owner))
        if gone:
            self._note("[config] and these are feelings she has not got, because what would move "
                       "them is off: " + ", ".join(gone))

        # and a section with no neighbourhood has nothing to read
        empty = []
        for sect, (key, what) in sorted(self.NEIGHBOURHOOD.items()):
            s = merged.get(sect)
            if not (isinstance(s, dict) and s.get("enabled", False)) or s.get(key):
                continue
            s["enabled"] = False
            setattr(self, sect, Section(s))
            empty.append("%s (%s.%s: %s)" % (sect, sect, key, what))
        if empty:
            self._note("[config] and these have no part of a city to read, so they are off: %s"
                       % ", ".join(empty))

    @classmethod
    def _person_file_rows(cls, merged, ex):
        """(key, value, why) for every row of PERSON_FILES that applies to this
        character, with `why` naming what makes it apply."""
        out = []
        for key, (sect, needs) in sorted(cls.PERSON_FILES.items()):
            if sect is not None:
                s = merged.get(sect)
                if not (isinstance(s, dict) and s.get("enabled", False)):
                    continue
                why = "the %s section is on" % sect
            else:
                if not ex.get(needs, True):
                    continue
                why = "she is %s" % {"in_world": "in a world", "embodied": "embodied",
                                     "has_account": "holding an account"}.get(needs, needs)
            cur = merged
            for part in key.split("."):
                cur = cur.get(part) if isinstance(cur, dict) else None
            out.append((key, str(cur or ""), why))
        return out

    def _check_person_files(self, merged):
        """A file that is one person's, named by nobody, while the thing that
        reads it is running.

        Run after what kind of character she is has been applied, so that a
        path this very load blanked (`WORLD_KEYS`) is judged together with the
        sections that load switched off. Two failures, one message: an empty
        path under a running subsystem, and a path naming a file that is not on
        disk -- which has always stopped the boot for her own record and is the
        same fault seen from the other end."""
        ex = (merged.get("character") or {}).get("existence") or {}
        who = str((merged.get("character") or {}).get("name") or "") or self.path
        empty, gone = [], []
        for key, value, why in self._person_file_rows(merged, ex):
            if not value.strip():
                empty.append("  %s is empty, and %s" % (key, why))
            elif key not in self.PERSON_NOT_PATHS and not os.path.exists(value):
                gone.append("  %s names %s, which is not on disk, and %s" % (key, value, why))
        if not (empty or gone):
            return
        raise SystemExit(
            "[config] %s has no file of her own where the library needs one:\n%s\n"
            "         A default that is one character's file was how this used to be filled "
            "in silence.\n         Name hers in %s, or switch off what reads it "
            "(`Config.PERSON_FILES` says which)."
            % (who, "\n".join(empty + gone), self.path))

    @staticmethod
    def _check_drift(loaded, defaults, path="", where="config.json"):
        """Keys a config file still carries that DEFAULTS no longer has.

        The merge keeps config.json's value over the default and keeps extra
        keys, which is what makes changing a default a two-file job. A key
        removed or renamed in DEFAULTS therefore lingers in config.json doing
        nothing, and -- worse -- a key whose *value* changed keeps the old one
        silently. Four of these accumulated in one afternoon
        (cold_mood_target, period_mood_target, period_anxiety_floor and the
        sadness targets). Reported, not deleted: config.json is his file.
        `python tools/smoke.py` shows them; nothing removes them for you.

        Two of these dicts are not sections of config keys at all: the
        attachment layer's pulls and tests are keyed by the id of one of HER
        self-beliefs, read as data (`sim/attachment.py:_belief_pull` goes
        through `config.raw`). Every id a character has that the first
        character has not would otherwise be reported as a dead key -- 16 of
        them for the second character, and they are the ones that work.

        An EMPTY dict in DEFAULTS is the third case, and the same one seen from
        further along: it is a map whose keys are the character's, defaulting
        to nothing at all because a default that is one person's part of a city
        is inherited by the next character in silence. The railway lines a
        train board watches and the search terms a photo harvest uses are
        keyed by the operator and by the kind of place, and every one of those
        keys would otherwise read as dead."""
        data_keyed = ("belief_pulls", "belief_tests")
        stale = []
        for k, v in (loaded or {}).items():
            here = f"{path}{k}"
            if k not in defaults:
                stale.append(here)
            elif (isinstance(v, dict) and isinstance(defaults.get(k), dict)
                  and defaults[k] and k not in data_keyed):
                stale += Config._check_drift(v, defaults[k], here + ".")
        if path == "" and stale and not Config._drift_reported:
            Config._drift_reported = True
            print(f"[config] {len(stale)} key(s) in {where} that DEFAULTS no longer has "
                  f"(harmless, but they are dead): {', '.join(stale[:12])}"
                  + (" ..." if len(stale) > 12 else ""))
        return stale

    @staticmethod
    def _check_gauges(merged):
        """A gauge has to say what sort of thing it is, and the emotion set has
        to span the valence x arousal grid. This is a load-time check because
        the failure it prevents is invisible at runtime: `mood` sat among its
        own causes with no declared kind, was written by the same call that
        wrote them, and ran +29 above its baseline and never more than -5 below
        for the whole of the record. Nothing errored. She simply could not have
        a bad day, and a `mood < 30` branch sat there never executing.

        An empty grid cell is not a gap in the data. It is a feeling the
        character cannot have. See PROJECT 16.1."""
        spec = merged.get("state", {}).get("gauges", {})
        kinds = ("emotion", "drive", "body", "derived")
        bad = []
        for name, g in spec.items():
            if g.get("kind") not in kinds:
                bad.append(f"{name}: kind must be one of {kinds}, got {g.get('kind')!r}")
            # A gauge may name the SECTION that writes it, and then a
            # character for whom that section is switched off does not have
            # the gauge at all (`sim/state.py:owner_off`). An owner naming a
            # section nothing knows about would silently never be off.
            owner = g.get("owner")
            if owner is not None and owner not in Config.REQUIRES:
                bad.append(f"{name}: owner {owner!r} is not a section in Config.REQUIRES")
            for axis in ("valence", "arousal"):
                if g.get(axis) not in (-1, 0, 1):
                    bad.append(f"{name}: {axis} must be -1, 0 or 1, got {g.get(axis)!r}")
        if bad:
            print("[FATAL] gauge spec (config.state.gauges):")
            for line in bad:
                print("  " + line)
            sys.exit(1)
        filled = {(g.get("valence"), g.get("arousal")) for g in spec.values() if g.get("kind") == "emotion"}
        missing = [(v, a) for v in (1, -1) for a in (1, 0, -1) if (v, a) not in filled]
        if missing:
            names = {1: "good", -1: "bad"}
            arou = {1: "activating", 0: "neutral", -1: "deactivating"}
            for v, a in missing:
                print(f"[gauges] nothing occupies {names[v]}/{arou[a]}: that is a feeling she cannot have "
                      f"(see PROJECT 16.1, /gauges)")

    def model(self, role):
        m = self.raw["models"].get(role)
        if not m:
            print(f"[FATAL] no model config for role '{role}'")
            sys.exit(1)
        return m

    # ---------------- the character-shaped holes in a mechanism prompt ----------------
    #
    # A prompt that runs the machinery is not a prompt about a person, and for
    # most of them the two were written into one file. `tomoe/prompts/showrunner.txt`
    # opened by naming a fifteen-year-old in Nerima and listing her friends as
    # the arcs to choose from; `tomoe/prompts/orbit.txt` told the model that this
    # character's mother, father and brother are cast. Both are mechanism files
    # with a person pasted in, and a second character invoking them is handed
    # the first one's life.
    #
    # So the file keeps the rule and marks the person's place with {{TOKEN}},
    # and the value comes from the character. **The rule that makes this safe:
    # a token's value for the character the prompt was written around is the
    # exact span that was removed**, so rendering reproduces the original file
    # byte for byte and her behaviour cannot change. `tools/neutral_gate.py`
    # is that check and it runs in smoke.
    #
    # A token with no value is a fault, not a blank: a character who has not
    # said what fills a hole gets a line saying the hole is empty, never the
    # other character's answer.
    #
    # `[[NAME]]` and not `{{NAME}}` because the prompts already use the curly
    # form for their own output-schema placeholders, which the mechanism fills
    # at call time (`{{DELTAS}}`, `{{TELLS}}` in state.txt). Sharing a
    # delimiter would mean a reserved list that every new mechanism token has
    # to remember to join; two delimiters means a collision is impossible and
    # a reader can see at a glance which side owns a hole.
    # Digits allowed: a prompt that carries two example lists of the same kind
    # gets a `2` on the second, and a name class that excluded digits left
    # `[[COMMIT_WHAT_EG2]]` standing in the prompt as literal text.
    _TOKEN = re.compile(r"\[\[([A-Z][A-Z_0-9]*)\]\]")

    def _fills(self):
        """Her values for the holes, loaded once. The sidecar is the file that
        holds what the sheet and the cast file do not: the example lists and
        the shape of a day that mechanism prompts used to carry inline."""
        if getattr(self, "_fills_cache", None) is not None:
            return self._fills_cache
        path = getattr(self.character, "neutral_file", "") or ""
        data = {}
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
            except (OSError, ValueError) as e:
                print(f"[config] the character's prompt fills are unreadable ({e})")
        out = {k: v for k, v in data.items() if not k.startswith("_")}
        # What the record marks her own lines with, in capitals. DERIVED rather
        # than authored, because code writes the same label into the text the
        # prompt is judging (`sim/commitments.py`, `self._her_caps`) and the
        # two have to be the same string: the shared prompt that judges what
        # she just promised him said her side was the lines marked TOMOE,
        # which named the first character to every character's process and was
        # stale even for her -- code had moved to her config name. A fills
        # file may still override it.
        out.setdefault("NAME_CAPS", str(getattr(self.character, "name", "") or "her").upper())
        self._fills_cache = out
        return self._fills_cache

    # A hole is not the only kind of difference between two characters using
    # one mechanism file. Most of what made the second character's forked
    # prompts differ was not her name, it was her CONDITION: she has no shared
    # history with him, no world to have a day in, and she watches his machine
    # rather than deciding to open an app. Those are properties of an
    # existence, not of a person, and a third character with the same
    # properties needs the same sentences.
    #
    #   [[?name]] ... [[/name]]     kept when the condition holds
    #   [[^name]] ... [[/name]]     kept when it does not
    #
    # The tags are inline and the author owns the whitespace: dropping a block
    # removes exactly the tags and what is between them and nothing else, so a
    # paragraph that should vanish whole takes its own trailing newline inside
    # the closing tag. Predictable beats clever here, because
    # `tools/neutral_gate.py` compares the first character's rendering byte for
    # byte and a rule that guessed at blank lines would fail it for the wrong
    # reason.
    _BLOCK = re.compile(r"\[\[([?^])([a-z_0-9]+)\]\](.*?)\[\[/\2\]\]", re.S)
    # `[[+name]]` -- where a character may add a rule of her own. Empty for
    # anyone who has not, which is most of them.
    _SLOT = re.compile(r"\[\[\+([a-z_0-9]+)\]\]")

    @property
    def world_reader(self):
        """Whether the world she is in is one somebody else keeps.

        One accessor, because the difference has to be asked by the day's
        planner, by the exchange and by the day's one truth, and reading the
        two keys by hand in each of them is how a second planner over one
        roster came to exist. True only when the shared world is on and her
        config does not say she owns it: a character alone in a world with no
        shared file writes it as she always has, because nobody is reading
        it. The sections that WRITE the world are already off for her
        (`Config.REQUIRES`, the `world_owner` property); this is for the
        three places where what stays on has to know which way to read."""
        ws = getattr(self, "world_shared", None)
        return bool(getattr(ws, "enabled", False)) and not bool(getattr(ws, "owner", False))

    @property
    def resident(self):
        """Whether she lives on his machine rather than reading a digest of it.

        One accessor, because the difference has to be asked in several places
        and reading the sheet field by hand in each of them is how a mechanism
        written for a girl with a phone in her pocket ends up running for a
        character who is inside the machine. A resident sees what he does
        continuously and without deciding to; that is her sheet's own wording
        and it is the whole of what this property means."""
        ex = getattr(self.character, "existence", None)
        return str(getattr(ex, "sees_him", "digest") or "digest").lower() == "resident"

    def conditions(self):
        """The named facts a prompt may branch on. A closed set derived from
        what the character declares, plus anything she names herself under
        `conditions` in her fills file -- so a prompt cannot branch on
        something nobody defined, and a typo is caught by the gate rather than
        silently dropping a rule."""
        ex = getattr(self.character, "existence", None)
        sees = str(getattr(ex, "sees_him", "digest") or "digest").lower()
        out = {
            "embodied": bool(getattr(ex, "embodied", True)),
            "in_world": bool(getattr(ex, "in_world", True)),
            "resident": sees == "resident",
            "digest": sees == "digest",
            "unseen": sees == "none",
            # Whether she has a chat with him at all. A prompt that tells a
            # role it will be given "the messages with him" and asks what his
            # silence did to her is describing a relationship, and a
            # character who exists for somebody else's circle has not got
            # one: her diary role was still being handed both sentences.
            "with_him": _existence.has_chat(self),
            # A character on the primitives starts every relational quantity at
            # zero, so "she has no history with him" and "she is on the
            # primitives" are the same condition today. Named for the thing a
            # prompt actually cares about rather than for the module.
            "no_history": bool(getattr(self.primitives, "enabled", False)),
            # Whether she is being instructed in her own language right now
            # (`character.instructions` and the switch over it). A prompt
            # forks on this where one line of it belongs to one arm only:
            # the editor's note is put in front of her and the verdict
            # beside it goes to the log, so the two go out in different
            # languages and neither can be read off the other.
            "her_language": _lang.reads_ja(self),
            # Whether the section that reads what mood he is in runs for
            # her at all. Read off the section rather than off the sheet,
            # because the existence table has already switched it off for
            # a character with no chat with him and it may also be off by
            # hand: the state prompt asks what he sounds like, and a role
            # asked a question nothing will read is a question that gets
            # answered anyway.
            "contagion": bool(getattr(getattr(self, "contagion", None), "enabled", False)),
            # held7: the state call is asked whether a held carry's cause is
            # settled (state.felt_carry_cause_held, needs the hold on), so its
            # prompt carries the rule for the `carry_resolved` field
            "cause_held": bool(getattr(getattr(self, "state", None), "felt_carry_cause_held", False))
                          and bool(getattr(getattr(self, "state", None), "felt_carry_hold_until_resolved", False)),
        }
        own = (self._fills() or {}).get("conditions")
        if isinstance(own, dict):
            for k, v in own.items():
                out[str(k).lower()] = bool(v)
        return out

    def fill(self, text, role=""):
        """Her values for the holes, and only the blocks her condition keeps."""
        if "[[" not in text:
            return text
        cond = self.conditions()
        unknown = []

        def block(m):
            sense, name, body = m.group(1), m.group(2), m.group(3)
            if name not in cond:
                unknown.append(name)
                return ""
            keep = cond[name] if sense == "?" else not cond[name]
            return body if keep else ""

        # innermost first, so a block inside a block resolves
        while True:
            text, n = self._BLOCK.subn(block, text)
            if not n:
                break
        if unknown:
            print("[config] prompt %s branches on %s, which no character defines"
                  % (role or "?", ", ".join(sorted(set(unknown)))))
        fills = self._fills()
        missing = []

        # A named place a character may add a rule of her own. The third kind
        # of difference between two characters on one mechanism file is neither
        # her name nor her condition: it is a rule true of her and of nobody
        # else -- "she does not explain her own psychology" comes from one
        # character's first driver and would be wrong advice for another. A
        # slot costs a line of data; without one it costs a forked file, and a
        # forked file drifts from the original the first time the mechanism is
        # fixed.
        slots = (fills.get("slots") or {}) if isinstance(fills.get("slots"), dict) else {}

        def slot(m):
            v = slots.get(m.group(1))
            if not v:
                return ""
            return "\n".join(str(x) for x in v) if isinstance(v, list) else str(v)

        text = self._SLOT.sub(slot, text)

        def one(m):
            name = m.group(1)
            v = fills.get(name)
            if v is None:
                missing.append(name)
                return "(not established for this character)"
            return "\n".join(str(x) for x in v) if isinstance(v, list) else str(v)

        out = self._TOKEN.sub(one, text)
        if missing:
            # Loud, once per role: a hole nobody filled is a hole the model
            # will fill on its own, which is how a second character acquires
            # the first one's habits.
            key = (role, tuple(sorted(set(missing))))
            seen = getattr(self, "_fill_warned", None)
            if seen is None:
                seen = self._fill_warned = set()
            if key not in seen:
                seen.add(key)
                print("[config] %s has no value for %s (role %s)"
                      % (getattr(self.character, "name", "this character"),
                         ", ".join(sorted(set(missing))), role or "?"))
        return out

    _prompt_cache = {}

    def prompt_text(self, role):
        """A role's prompt file, filled for this character. The file is read
        once per change (mtime), because the bible is asked for by every
        interior role on every tick and was read off disk each time."""
        path = self.model(role)["prompt"]
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            mtime = None
        hit = self._prompt_cache.get(path)
        if hit is None or hit[0] != mtime:
            with open(path, "r", encoding="utf-8") as f:
                # an HTML comment in a prompt file is a note for whoever
                # edits it (the promotion tool leaves its provenance that
                # way), never for the model: it went out as the first bytes
                # of a promoted character's system prompt
                hit = (mtime, _strip_html_comments(f.read()))
            self._prompt_cache[path] = hit
        # and the language its prose goes out in, when this role writes
        # something she will read and she is being addressed in her own
        # language. After the cache and after `fill`, because the arm can
        # move between two calls and the cache is keyed on the file.
        return self.fill(hit[1], role) + _lang.material_line(self, role)

    def role_system(self, role, extra=""):
        """The system prompt of a role that runs beside her: its own
        instruction, and her character sheet only if the role speaks as her.

        `Config.ROLE_STANCE` decides, and a role with no row stops the
        process here rather than quietly inheriting whichever behaviour the
        last edit left. A judge is a neutral party: it sees its instruction,
        what the caller hands it, and -- where it needs to know what she is
        like -- the observer's digest (`sim/observer.py`), never the sheet.
        The sheet is written TO her, in the second person, and used to sit
        last in the system prompt where a judge read it as its own identity.
        """
        stance = self.ROLE_STANCE.get(role)
        if stance is None:
            raise SystemExit(
                "[config] role_system(%r): Config.ROLE_STANCE has no row for this role, so "
                "nothing has decided whether it writes as her or judges her.\n"
                "         Add it as 'voice' (the role writes her words and gets her character "
                "sheet) or 'judge' (the role decides something about her, hands the answer to "
                "code, and gets no sheet)." % role)
        body = self.prompt_text(role) + ("\n\n" + extra if extra else "")
        if stance != "voice":
            return body
        return body + "\n\n---\nHER CHARACTER SHEET:\n" + self.prompt_text("persona")

    def read_text(self, path, default=""):
        if not path or not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as f:
            return _strip_html_comments(f.read())
