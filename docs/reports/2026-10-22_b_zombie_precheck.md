# B-zombie test: pre-check notebook

Orchestrator notebook, 2026-10-22 16:47. The User's order 16:42: "Find the dependencies first and unearth anything that needs settled before doing the full plan." Then 16:45: research the GLM 5.3 and DeepSeek docs before going further. Plan context: docs/2026-10-22_b_zombie_methods.md section 8, revised by the User 16:38. Two arms only: S (superior) vs P (private-machine). Claude agents judge. All B-zombie calls go to Surplus Intelligence on deepseek-v4.1-flash-1017 and glm-5.3. Characters: Momoka in Japanese, and Tomoe in English on both arms.

## Settled (each with what was run)

1. **P's dependencies are public.** pyproject.toml needs pm-workflows and pm-coder from GitHub; uv.lock pins pm-coder d9c9ca4 and pm-workflows 073e988. `git ls-remote` returned both heads (pm-minecraft 46a1b37 too, not needed). License MIT.
2. **Python 3.12.1 is present** (`py -3.12`). uv is not installed. Plan: uv into a venv on F:, with UV_CACHE_DIR and UV_PYTHON_INSTALL_DIR on F:.
3. **P runs on one model for every call.** Its config has chat roles `Default` and `UnitTestEvaluator` only (config.example.yaml). So in the match, S also runs one model for every role.
4. **P's thinking controls.** P sends a reasoning effort per call (none to max; its inner-thought and main-cognition stages turn thinking off; docs/subsystems/inference-settings.md:6, 33, 80).
5. **Surplus works.** Probes (F:\temp\scail_cost\probe.py; the key is read from secerts/surplus.txt, never printed):
   - The whole grant is the budget, unspent.
   - Cost comes back per response as `usage.buyer_cost_micro` (microdollars). A 2.8-4k-token call costs 6-61 micro, far under list price. Balance: GET /v1/payments/balance (meta, SURPLUS_LLMS_20261022.txt:41-46).
   - Streaming works; usage arrives in the last chunk with `stream_options.include_usage`.
   - Caching is automatic on both models: deepseek cached 3,072 of 4,017 prompt tokens on the repeat (61 to 22 micro); GLM cached 2,816 of 2,819.
   - Rate limit 1,200 calls a minute per key; concurrency undocumented (meta).
6. **Thinking behaviour differs.**
   - deepseek-v4.1-flash-1017 accepts `reasoning_effort: none` (0 thinking). At `low` it still spent 93 thinking tokens and returned 2 characters.
   - glm-5.3 rejects `none`; it accepts only low, high or max. At `low`, a short reply used 0 thinking tokens. With no effort set and max_tokens 200, it spent 192 tokens thinking and returned empty content.
   - So P's "thinking off" calls will 400 on GLM unless something maps them, and every call needs max_tokens headroom.
7. **Embeddings.** Surplus venice-embed-1 returned "no healthy sellers" at 16:43 ($0.1625 per M when up, per meta). P needs an OpenAI-style /v1/embeddings endpoint. S uses multilingual-e5 locally on the GPU (sim/embed.py). Plan: one local endpoint serving the same multilingual-e5 to both arms. Same model on both sides, and it handles Japanese.
8. **Tomoe's English mode exists.** SCAILV3 config.json: `writes_to_him: english`, `instruction_language: english`, English prompts/bible.md and style.md (plus style_ja.md). V4 still reads both keys (28 references in 10 files, including sim/lang.py and persona/persona.py). S gets Tomoe as a chat-shape character bundle; her world program (tomoe/) is not needed, since P has no world either.
9. **GitHub.** gh is logged in as the owner. His repo allows forks and has issues and discussions. The PR is docs-only (tk-q5k).

## Decisions taken (mine)

- **One local gateway for both arms**, bound to 127.0.0.1, in front of Surplus. Both arms set it as base_url. It:
  - applies one thinking policy to both arms (maps `none` to `low` on GLM);
  - enforces max_tokens headroom;
  - meters spend per arm from buyer_cost_micro and stops at each arm's share;
  - logs every call per arm.

  That makes "same model" literally the same request shape, and gives one cost ledger.
- **Single model per run on both arms** (point 3).
- **Same embedding model on both arms** (point 7).
- **Content.** User 16:48: "Romantic is not a failure." Judges do not penalise romance. Both test cards state an adult age:
  - Tomoe's bible makes her 15, and no romantic scene runs with a 15-year-old character. Her test card sets her at 19 (first year at university), the rest unchanged; her V3 files are untouched. If he wants her kept at 15, her scenes stay non-romantic instead.
  - Momoka's age is a deliberate gap in her sheet; her test card states she is an adult.

## Model research (two Sonnet agents, 16:46-16:47) and pass-through probe (16:48, F:\temp\scail_cost\probe2.py)

DeepSeek V4.1 Flash 1017 (official name now `deepseek-flash`; sources api-docs.deepseek.com thinking_mode, create-chat-completion, json_mode, kv_cache, news261017):
- Thinking is on by default. `reasoning_effort` takes none, low, high or max; `thinking: {type: disabled}` also works. Probe: both pass through Surplus; 0 thinking.
- Temperature only applies with thinking off. top_p is fixed at 1.0 in non-thinking mode. frequency and presence penalties are dead. Probe: temperature 1.5 accepted.
- With tools and thinking on, prior `reasoning_content` must be sent back on every later turn, or the call 400s. Without tools it is ignored.
- JSON mode: `response_format json_object`; the prompt must say "json" and show the shape; it can return empty content, so retry. Probe: valid JSON.
- 1017 is tuned shorter and for agent harnesses. State length and voice explicitly.
- No official role-play or Japanese guidance. Pin the language in the system prompt.
- Caching: automatic prefix units. Keep the long system prompt byte-stable and put volatile text last.

GLM 5.3 (sources docs.z.ai glm-5.3, thinking-mode, cache, struct-output, function-calling; HF zai-org/GLM-5.3; Together quickstart):
- Thinking cannot be disabled. Effort is low, high or max; an omitted value falls back to max. Probe, no effort set: 1,467 thinking tokens, 20.8 s, 50 micro for one short line. The gateway must always set an effort.
- `clear_thinking: true` is recommended for chat deployments: prior thinking is not kept. Probe: via `chat_template_kwargs` it passes through; 0 thinking, 1.9 s, no reasoning_content. As a top-level field: 6 thinking tokens, 7.7 s.
- Sampling: temperature 1.0, top_p 0.95; change only one.
- JSON: `response_format json_object`, schema in the system message, validate after. Probe: valid JSON at low. Tools: OpenAI schema, tool_choice auto only; thinking blocks go back with tool results.
- Officially English and Chinese only. No Japanese guidance; test for Chinese leakage. 5.3 is more verbose than 5.2.

Gateway policy from this (applies to both arms, both models):
- deepseek: `reasoning_effort: none` on every call, temperature as the arm sets it, no penalties.
- GLM: `reasoning_effort: low` plus `chat_template_kwargs.clear_thinking: true` on chat calls. Tool loops keep thinking blocks per the docs. Never send a call without an effort.
- Language: one pinning line in the target language at the top of the system prompt and one at the end of the last message, for both arms.
- Every arm's long prompt stays byte-stable at the front for caching.

## Open

- Momoka thread export for P: CSV name,message,timestamp from a copy of her save.
- Cost per reply on P: one measured exchange after install. Rough estimate from the probes (2.8-4k tokens cost 2-61 micro): S about $0.001-0.003 a reply, P about $0.005-0.02 a reply. The budget covers several hundred P replies. Time, not money, is the constraint: P makes 15+ calls per reply.
