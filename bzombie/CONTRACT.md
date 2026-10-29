# B-zombie test bench: the contract

Written by the scail orchestrator 2026-10-22 17:08. Every agent on the bench builds against this file. Plan and reasons: docs/2026-10-22_b_zombie_methods.md sections 8-9; facts and model rules: docs/reports/2026-10-22_b_zombie_precheck.md. Change this file only through the orchestrator.

**Status 2026-10-23 07:45 (User): P is out of consideration.** The S vs P result is in docs/reports/2026-10-23_bzombie_results.md. No new P runs; the P sections below are kept as the record of how the cl1/cl2 runs were made. The bench continues on S: multi-day runs, removal tests, his blind votes.

## What is being built

Two arms, each a "B-zombie" companion, driven by one harness that owns time, state, conversation and the environment, with full observability of what led to every response.
- **S** (superior): SCAILV4's mind library on branch `bz/s`, plus the six starting changes (methods doc section 8) and harness controls. Never merged to master; Momoka's live process is never touched.
- **P** (his): private-machine, the owner's fork of private-machine, clone F:\REPS2\bzombie_pm, branch `harness`, based on upstream e338fbf. Patches give the harness control; they do not change his cognition.
- **Characters** on both arms:
  - Momoka, Japanese only; test card states she is an adult.
  - Tomoe, English only, from SCAILV3 (characters/tomoe, prompts/bible.md, style.md, config `writes_to_him: english`, `instruction_language: english`); test card sets her at 19, first year at university in Tokyo, otherwise her bible unchanged.
- **Romance** is allowed and is not a failure (User 16:48).

## Layout

- `bzombie/` on master (SCAILV4): gateway, harness, sim-him, environment, judges, viewer, arm adapters. Tooling only; nothing here is imported by Momoka's live process.
- `var/bzombie/` (gitignored): all run data. `var/bzombie/runs/<run_id>/` holds config.json, clock.json, calls.jsonl, transcript.jsonl, env/, snapshots/, traces/, logs/.
- Secrets: the Surplus key is `secerts/surplus.txt` (read it, never print it, never copy it into a tracked file or log).

## Ports (127.0.0.1 only, never 0.0.0.0)

- 18330: gateway.
- 18331-18339: S arm control servers, one per live run.
- 18341-18349: P arm control servers, one per live run.
- 18350: viewer. The User's window onto the test (17:08): the B-zombie conversations live, judged results, raw stats, and switching between options. Built by its own agent from the files below; spec in the Viewer section. His policy: no pop-up windows, everything in the browser.

## Processes

Compute tickets (meta, 17:06): any job that loads the machine (minutes of CPU, 1 GB+ RAM, any GPU, any long run: the gateway with the embedding model, uv sync, every simulated run) takes a ticket first: `python F:\REPS2\Meta_Orchestrator\tools\limits\client.py wait --who scail/<job_name> --cpu <cores> --mem-gb <GB> --vram-mb <MB> --host here --prio high --timeout 3600`; exit 0 prints "<host> <ticket>", run the job, then `client.py release <ticket>`; exit 3 is a timeout. In Python: copy client.py as limits_client.py and wrap the job in `with granted(who, need, host="here", prio="high", pid=<pid>):`. Declare honest needs (a padded need waits); the PC never swaps (85% memory ceiling). Bulk disk work adds `--disk F --disk-class bulk`. Contract: F:\REPS2\Meta_Orchestrator\docs\LIMITS_CLIENT.md. Tests, quick probes and plain API calls need no ticket.

Every process the bench starts is hidden (pythonw, or CREATE_NO_WINDOW), F: only, TEMP=F:\temp. P runs from its own venv (uv) in F:\REPS2\bzombie_pm. Minecraft, MCP tools and the container agent stay off in P.

## Gateway (port 18330)

OpenAI-compatible, in front of Surplus (https://api.surplusintelligence.ai/v1).
- **Arm and run are in the path.** An arm's base_url is `http://127.0.0.1:18330/arm/<S|P|X>/<run_id>/v1` (X = harness-side calls such as the model check). Endpoints: `POST .../chat/completions` (stream and non-stream), `POST .../embeddings`, `GET .../models`.
- **Model is forced.** The gateway replaces `model` with the run's model from `var/bzombie/runs/<run_id>/config.json` (`"model": "deepseek-v4.1-flash-1017"` or `"glm-5.3"`). Arms may send any alias.
- **Thinking policy, identical for both arms:**
  - deepseek: `reasoning_effort: "none"`, drop any `thinking` field; temperature passes through; drop frequency and presence penalties.
  - glm-5.3: `reasoning_effort: "low"` always (never unset: unset means max), plus `chat_template_kwargs: {"clear_thinking": true}` on calls without `tools`. On calls with `tools`, keep prior reasoning blocks the caller sends.
  - max_tokens: if the caller sets one below 1024, raise it to 1024 (thinking shares the budget).
- **Language pin.** One line in the run's language (`"lang": "ja"` or `"en"`) prepended to the first system message and appended to the last user message:
  - ja: 「キャラクターとしての文章はすべて自然な日本語で書く。」
  - en: "Write everything the character says in natural English."
- **Embeddings.** Served locally by the gateway with intfloat/multilingual-e5-small (the model SCAIL uses, config_momoka.json `embed.model`), on the GPU if available. Same model for both arms. Dimension 384. Not sent to Surplus.
- **Metering.** Cost per call from Surplus `usage.buyer_cost_micro` (non-stream) or the final usage chunk (stream, with `stream_options.include_usage`). Per-run cap in config.json (`"cap_usd"`). Past the cap the gateway answers 402 with `{"error": {"type": "budget_exhausted"}}`, writes the event, and the harness pauses the run.
- **Prefill fold (tk-7gn).** If the last message of a chat request has role assistant (a prefill to continue), the gateway drops it and appends to the last user message one line asking for only the character's next message, plus the last 400 characters of the prefill. Surplus otherwise starts a fresh turn and leaks template junk. The reply is the message text only, no prefill echo (same shape as a first-party continuation). Logged as `"prefill_fold": "fold_prefill_tail"`; `request` keeps the original, `request_sent` the folded one. Stream and non-stream alike. Not applied when the assistant message has tool_calls or empty content.
- **Template junk flag.** A response containing `<｜`, `ds_safety` or `Valid channels:` gets `"template_junk": true` in its call record. Flag only, the response is not edited.
- **Log.** One line per call to `var/bzombie/runs/<run_id>/calls.jsonl`: call_id (uuid), arm, run_id, wall_ts, virtual_ts (read from the run's clock.json at call time), model, request (full), response (full, including reasoning), usage, cost_micro, latency_s, error. Every response gets an `x-bz-call-id` header so an arm can link its own records to the call.
- **Status.** `GET /status` returns spend per run and arm, cap, call counts, errors, and Surplus balance (GET /v1/payments/balance, `credit_balance_usdc` microdollar string, cached 60 s).
- **Retries.** Transport errors and 429 (honour Retry-After) retried up to 5 times with backoff; failed calls cost nothing.
- **Hedge.** Surplus stalls about 2% of calls (no answer for 246-733 s, then the retry answers in seconds). If a try has produced no response byte (non-stream: no body; stream: no first chunk) after `hedge_after_s` (default 60, env `BZ_HEDGE_AFTER_S`, 0 = off), the gateway starts one identical second try in parallel, at most one per attempt round. The first to deliver wins and the other connection is closed; for stream only the winner's chunks reach the client. The retry loop and per-read timeouts stay as the outer safety net. The call record gets `"hedged": true|false` and, when hedged, `"hedge_won": "first"|"second"`; `latency_s` is wall time to the client's answer; `cost_micro` is the winner's usage only (the abandoned loser's cost is unknown).

## Arm control API (each arm process, its own port)

Stepped, discrete-event time. Virtual time stands still while an arm computes; it only moves when the harness says so.
- `POST /control/start {run_id, character, lang, clock_start}`: boot the arm on its run folder with the clock at clock_start (ISO 8601, local time Asia/Tokyo for both characters).
- `POST /control/advance {to}`: run the arm's own background work at its native cadence in virtual time until `to` (S: its loop every 5 virtual s; P: its private loop every 30 virtual s and its wait controllers), then return `{"outputs": [...]}`: everything she sent in that span.
- `POST /control/send {text, ts}`: deliver his message at virtual ts (the arm first advances to ts). Returns immediately. Her reply comes back from the next `advance` calls, with its own virtual timestamp.
- `POST /control/env {events: [...]}`: environment events (schema below), each with its virtual ts. Delivered at their ts during advance.
- `POST /control/snapshot {name}` and `POST /control/restore {name}`: full state copy into `snapshots/<arm>/<name>/` (S: its SQLite save plus kv; P: ghost.pickle plus its runtime folder). Restore puts the clock back too.
- `POST /control/inject {target, value}`: an arm-specific state edit for removal tests. S: a gauge, a config switch, or a prompt section on/off. P: a mental-state field, a codelet on/off, a phase skip. Each arm documents its targets in `bzombie/arms/<arm>/TARGETS.md`.
- `GET /control/trace/{output_id}`: the trace of one output (schema below).
- `GET /control/state`: a summary of current state (S: gauges, stances, open expectations; P: mental state, active goals, workspace shard heads).
- `POST /control/stop`.

Output object: `{"output_id", "virtual_ts", "text", "kind": "reply|unprompted", "call_ids": [...]}`.

## Trace schema (one JSON per output, `traces/<output_id>.json`)

- `output_id`, `arm`, `run_id`, `virtual_ts`, `text`.
- `final_call_id`: the gateway call that produced the text.
- `calls`: every gateway call_id that fed this output, in order, each with its role or phase name.
- `inputs`: the named pieces of the final prompt, each with its kind (his_words, env_event, memory, state, persona, own_past_line, other_model_output), its source record id, and its text.
- `state_at_output`: the arm's state summary at that moment.
- `causal`: arm-specific. S: admitted attention lines with weights, the in-character order, gauges, stances. P: causal percepts, workspace items that entered, the decision text, the route.

## Environment events

`{"ts", "kind": "world|pc", "text", "source": "env_script/<day>"}`:
- Tomoe: kind world (a lecture, the circle, her part-time job, a friend's message in a group chat, the train, plans).
- Momoka: kind pc (window title, what he is watching, idle, asleep). Momoka cannot see beyond his PC.

Each simulated day, a Claude call writes the day's environment script before the day runs. The same script goes to both arms of the same character.

## Claude calls from the harness (meta 17:14)

The driver is a hidden process started by the orchestrator, never an agent (agents are refused by the agent_boundary hook, correctly). Every Claude child: `claude -p --model claude-sonnet-5-5 --output-format json --tools "" --no-session-persistence --setting-sources "" --strict-mcp-config --disable-slash-commands --system-prompt <text>`, prompt on stdin, CREATE_NO_WINDOW only (never DETACHED_PROCESS), cwd F:\temp\bz_claude. Billed to API credits, never the subscription: per run `credits.py reserve --who scail/bzombie_<run_id> --amount-usd <claude_cap_usd, default 10> --pid <driver pid>`, `credits.py dispatch <id>` before the first call, `credits.py settle <id> --actual-usd <sum of total_cost_usd>` at the end (F:\REPS2\Meta_Orchestrator\tools\limits\credits.py). The key for the reservation's label is read from ~/.scail/secrets.json inside the driver and passed only in the child env as ANTHROPIC_API_KEY, with its `workspace_id` as `ANTHROPIC_CUSTOM_HEADERS: anthropic-workspace-id: <id>` (the grant keys are not workspace-scoped; without it the API answers 400). The driver takes no compute ticket.

After the grant (User 17:23-17:25): the API grant is one-time and not replenished; burn it first. `claude -p` never runs on the subscription. When the grant is used up (GrantExhausted: credits.py "insufficient confirmed" or the API's "credit balance is too low"), the harness's Claude work goes to the bench worker: a special Claude Code session with its own prompt (not an orchestrator) that answers each request in var/bzombie/claude_queue/ with a fresh normal agent (tk-jsk). Any other refusal pauses the run.

## Model (model check 17:15)

All runs use `deepseek-v4.1-flash-1017`. Blind Sonnet judges, two passes, 48 samples: 11 of 16 first places, mean rank 3.21 vs 3.79, Momoka naturalness 4.04 vs 2.62; glm-5.3 broke Japanese twice and leaked Japanese into Tomoe 4 times. Result: var/bzombie/modelcheck/judgments.json. Both models copy `[Ddd hh:mm]` stamps from a stamped history: no arm shows her stamped chat.

## Simulated him

One call per turn on the run's model (deepseek-v4.1-flash-1017 on Surplus), through the gateway as arm X on the run (`/arm/X/<run_id>/v1`), logged in the run's calls.jsonl with arm "X". Not Claude (User 10-22 20:10); run config `him_via` "gateway" (default) or "claude" (harness billing tests only). Each call carries:
- a style profile built from his real messages (Tomoe: English; Momoka: Japanese), the profile only, never his old content;
- the conversation so far as he saw it (her outputs only; he never sees her trace, her world script or her state);
- his own day plan for that simulated day.

It decides whether and when he writes next and what he says. Same profile and day plan for both arms of a character.

**Script mode (tk-mz5, 2026-10-23).** The model improvises against what she says, so two arms (or a run and its removal-test branch) get different lines from him after the first divergence. For comparisons, fix him: run config `"him_via": "script"` plus `"him_script": "<run_id>"` (a finished reference run) or a path to a JSONL file. The driver sends his lines from that source's transcript (`who == "him"`, or no `who` in a plain file) at their `virtual_ts`, verbatim. No sim-him call, no profile load, no `max_him_turns_per_day` cap. Code: `bzombie/harness/script.py`, `run_day` in `driver.py`.
- Env events stay on the existing path (env cache keyed by character and seed, so the same script when the seed matches). `new --like ... --seed` with another seed than the reference's prints a warning.
- A line that falls while the arm is asleep or mid-reply is sent at its ts as always; the arm handles it.
- The reference ran fewer sim days: sending stops, and once the run logs `script_ended` in state.json and a line in the driver log. Lines past this run's `sim_days` are never sent. Lines are matched by absolute `virtual_ts`, so `clock_start` should match the reference's.
- A reference run of another character is refused at config load (`ScriptError`); so are an empty script and a missing `him_script`. A JSONL path has no character check.
- Removal-test branches always use script mode. Default script = the parent run's own transcript: the branch delivers the first his line at or after the snapshot's cursor, plus every scripted line up to 30 min after it, so base and branch see identical him lines. `branch.json` carries `"him_via": "script"`, `"him_script": <source>` and `"base_him_via"`. Override: `harness branch <run> <snapshot> <target> <value> --script-from <run_id|jsonl>`.
- Make a scripted run from an existing one: `python -m bzombie.harness new --like <run_id> --run-id <new> --s-root <worktree> [--seed N] [--sim-days N] --script-from <ref_run_id> [--run]`. It copies the config, drops runtime keys, swaps the `--s-root` value inside the `arm_cmd` list (no `--set arm_cmd=` from bash, which stores a string).

## Judges

Claude calls (as in "Claude calls from the harness"; Opus writes the rubric), fresh process per criterion per pass, blind labels A/B, never told which arm. Rubric and planted-defect calibration in `bzombie/judge/`.

## Files the viewer reads (every part writes these exactly)

Under H:\SCAIL\bzombie\var\:
- `runs/<run_id>/config.json`: run_id, arm, character, lang, model, cap_usd, sim_days, clock_start, seed, status (running, paused, done, failed), started_wall, updated_wall.
- `runs/<run_id>/clock.json`: virtual_ts, sim_day.
- `runs/<run_id>/transcript.jsonl`: one line per event in virtual order, `{"virtual_ts", "who": "him|her|env", "text", "output_id" (her lines), "kind" (her: reply|unprompted; env: world|pc), "sim_day"}`.
- `runs/<run_id>/calls.jsonl`: the gateway log (Gateway section).
- `runs/<run_id>/traces/<output_id>.json`: the trace schema.
- `runs/<run_id>/branches/<branch_id>/`: a removal-test branch, with `branch.json` (`{"branch_id", "from_snapshot", "target", "value", "replayed_from_virtual_ts", "him_via", "him_script", "base_him_via"}`) plus its own transcript.jsonl, calls.jsonl and traces/.
- `modelcheck/samples.json`, `modelcheck/key.json`, `modelcheck/judgments.json`.
- `judge/<match_id>/results.json`:
  - top level: `{"match_id", "character", "label_map": {"A": run_id, "B": run_id} (revealed only after judging), "criteria": [...], "calibration": [...], "summary"}`;
  - each criterion: `{"id", "name", "passes": [...]}`;
  - each pass: `{"pass": 1|2, "verdict": "A|B|tie", "scores": {"A": 1-5, "B": 1-5}, "reason", "quotes": {"A": [...], "B": [...]}}`;
  - each calibration entry: `{"defect", "caught": bool}`;
  - one results.json per comparison (S vs P per character, base vs branch for each removal test).
- `votes.jsonl`: his blind votes, `{"pair_id", "choice": "A|B|tie", "note", "wall_ts"}`; `pairs/<pair_id>.json` holds the hidden mapping.

## Viewer (port 18350)

Read-only over the files above, except his votes. Live: refreshes on its own while runs go (polling or server-sent events). Hidden process, 127.0.0.1 only.
- **Runs:** every run with arm, character, model, status, virtual clock and simulated day, messages, spend, calls.
- **Conversation:** a run's transcript, his lines and hers, environment events toggled on or off. Click a line of hers to see its trace: inputs by kind, the causal block, and every call with its full prompt, response, cost and latency.
- **Side by side:** pick any two runs or branches (S vs P on a character, base vs a removal-test branch, deepseek vs GLM) and read them in parallel, aligned by simulated day and virtual time.
- **Options:** filters and switches for arm, character, model, branch and simulated day; every view takes them from the URL, so a view can be linked.
- **Judged results:** per comparison, per criterion: verdicts and scores of both passes, agreement, the reason and quotes. Calibration caught or missed. The model check result.
- **Raw stats**, per run and per branch:
  - calls, tokens, cost, latency, calls per reply, cost per simulated day;
  - replies and unprompted messages, reply length distribution;
  - repetition rate, language purity (share of the target language);
  - S's causal share and constant lines where its traces carry them.
  - Charts kept simple; numbers first.
- **Blind vote:** two outputs for the same moment as A and B, nothing else on screen; records his choice and a note.

## Rules for every agent on the bench

- You are an AGENT, not the orchestrator. Build only your part; read this contract for the rest.
- Never touch data/momoka.db or Momoka's live process. S works on copies.
- Never print a key or a credential. Never bind 0.0.0.0. Every process hidden. F: only.
- Commit in your worktree and push your branch after every commit; no Co-Authored-By line.
- Keep a dated notebook `docs/reports/2026-10-22_bz_<part>_notebook.md` in your worktree: findings, tried, failed, stage.
- Tests: the changed modules' tests, and an end-to-end check of your part. Report what you ran.
