# Bench worker

Result: once the one-time API grant is gone, the harness's Claude work (sim-him turns, env days, profiles, judges) goes through a queue folder to a special Claude Code session, which answers each request with a fresh subagent. The worker is NOT an orchestrator: it owns nothing and coordinates nothing.

## Start it

`F:\REPS2\SCAILV4\bzombie\worker\launch_bench_worker.cmd` (after bz/worker is merged to master; from the worktree it works the same, it resolves its own folder). It copies CLAUDE.md and settings.json into `F:\REPS2\SCAIL_bench_worker\` and starts `claude` there hidden (`start_hidden.ps1`, Start-Process -WindowStyle Hidden). `BENCH_DRY_RUN=1` prints the claude line and starts nothing. Not wired into restart_windows or rc_reconnect.

Claude line: `--dangerously-skip-permissions --model claude-sonnet-5-5 --name "scail bench" --system-prompt-file CLAUDE.md --strict-mcp-config --disallowedTools <same deny list as launch_scail.cmd>` plus the start prompt "Start the loop.". No channel flag, no --mcp-config (user-scope feed and pick-assist MCP stay out). System prompt replaced, never appended.

## Home folder

`F:\REPS2\SCAIL_bench_worker\` is outside the SCAILV4 tree, so SCAILV4's CLAUDE.md, project hooks (tracker_watch, handoff) and handoff plugin state do not load. F:\REPS2 has no CLAUDE.md and no .claude. User-scope hooks (rtk, full_suite_gate, PermissionRequest auto-allow) still load, harmless. `.claude\settings.json` is refreshed by the launcher from `bzombie/worker/settings.json`: fast-jev-compaction off, autoCompactEnabled true. Usage accounting is on meta's side (that folder counts as SCAILV4).

## Queue protocol (var/bzombie/claude_queue/)

- Harness writes `<req_id>.req.json` (tmp then rename): req_id, task, model "sonnet", system, prompt, run_id, virtual_ts, created_wall, fresh true.
- Worker answers with `<req_id>.ans.json`: req_id, text, is_error, error, answered_wall, agent_model. Harness polls every 1 s, then moves both to `done/`.
- `worker.json` {pid, session_label, last_seen_wall} is the heartbeat. Older than 10 min (or missing) when a request would be written: run pauses `worker_down`, nothing is written. No answer in `queue_timeout_s` (default 900): run pauses `worker_timeout`, the request moves to `done/<id>.req.json.timeout`.
- `worker_io.py` is the worker's helper: list, show, model, answer, beat, watch. The worker writes the reply text to `<id>.ans.txt` with the Write tool, `answer` turns it into the atomic `.ans.json`.

## Run config (harness side)

`claude_billing`: "auto" (default; credits first, on GrantExhausted at reserve or mid-run it settles and switches the live session to the queue, same call continues there), "credits" (pause as before), "queue" (no reservation). `queue_timeout_s`: 900. Calls log to `claude_calls.jsonl` with `billing` credits or queue; queue calls cost_usd 0.

## Worker rules (meta terms 17:30)

- Before each subagent: `client.py status`, read `token_order:`. On no_new_agents or stop_at_limit start none, leave the request queued (the harness pauses worker_timeout, the right outcome). The 5% weekly reserve is the User's.
- One fresh general-purpose subagent per request, model from the request (default sonnet), prompt = system text, prompt text, "Answer with the reply text only. Use no tools.". Never reused, never shared.
- The subagent returns only the reply text; the worker writes it straight to the answer file and does not echo it into chat.
- Edits nothing but `.ans.txt`/`.ans.json` and worker.json. No momoka.db, no credentials in output.
