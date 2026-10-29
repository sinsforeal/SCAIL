# SCAIL features (his names)

Written 2026-10-22 from the scout (docs/reports/SCAIL_SCOUT_20261022.md). Read whole before searching for a feature he names; a landing that moves one updates its line. State is as observed 2026-10-22 15:00, not re-checked since.

## VN reader (the channel)
- State: down. Browser visual-novel reader on 127.0.0.1:8770, served inside Momoka's process. Not running now.
- Open: none logged.
- Code: channels/vn_bot.py:111 (VnInterface), port at channels/vn_bot.py:67, front end view/app.js.

## Momoka (the process)
- State: not running. SCAIL_momoka task last ran 09-20 06:40, result -1073741510 (stopped). Start: momoka.cmd -> resident/run.py --config config_momoka.json --db data/momoka.db.
- Open: BUILD_BACKLOG.md items 13, 11, 19, 15.
- Code: resident/run.py:22, scail.py (main), config_momoka.json (running config), characters/momoka/sheet.json.

## MAL daemon
- State: running. Task SCAIL_mal, pythonw pid 24232 at scout time: `tools/mal_history.py daemon --interval 300 --reconcile 6`. Last result 0.
- Open: none.
- Code: tools/mal_history.py:934 (cmd_daemon), tools/mal_history.py:1938 (main). Secret by name: MAL client id in secerts/.

## MAL watchdog
- State: running. Task SCAIL_mal_watchdog, every 5 min plus at logon and startup, runs `pythonw.exe -u F:\REPS2\SCAILV4\tools\mal_watchdog.py` directly. Last result 0.
- Open: tools/mal_watchdog_setup.ps1 registered a wscript shim in a local-only commit; scaffold edits it to match the live task (pythonw direct).
- Code: tools/mal_watchdog.py:121, tools/mal_watchdog_setup.ps1.

## GitHub reply watch
- State: running since 2026-10-27 16:14. Task SCAIL_gh_watch every 15 min runs `C:\Python314\pythonw.exe tools\gh_watch.py`; a reply, review or state change by anyone but the owner on our PRs/issues in flamingrickpat/private-machine becomes a scail tracker issue (the User 10-27 16:11). Filing tested 16:14 (tk-yzb, closed).
- Open: none.
- Code: tools/gh_watch.py (REPOS list, ME), state var/gh_watch.json, log logs/gh_watch.log.

## B-zombie viewer
- State: running on http://127.0.0.1:18350/ (data H:\SCAIL\bzombie\var): bench conversations live, judged results, raw stats, option switching. Was down from the 10-25 PC loss until 10-28 08:13 (nothing restarted it); since then task SCAIL_bz_viewer (logon + every 15 min) runs `pythonw -m bzombie.viewer start`, which exits at once when it is up.
- Open: none.
- Code: bzombie/viewer/__main__.py (start/stop/serve, pid and log in %TEMP%\bz_viewer_18350.*), bzombie/viewer/server.py, bzombie/viewer/data.py:13 (DEFAULT_DATA), tools/bz_viewer_task.ps1.

## Sensors (his PC)
- State: part of Momoka's process; idle while she is down. Includes chrome, system, media, torrent, eroge, vault, X, MAL monitors.
- Code: sensors/ (vault_monitor.py:24), machine/monitor_client.py.

## Collector
- State: idle. Task SCAIL_collector last ran 09-17.
- Open: none.
- Code: machine/collector.py:46, sensors/telemetry_collector.py.

## Scene director
- State: part of Momoka's process.
- Open: none logged.
- Code: sim/director.py:14.

## Stage manager
- State: part of Momoka's process.
- Open: none logged.
- Code: sim/stage_manager.py:92.

## Saves and backlog (VN)
- State: data/momoka.db is her save; the reader keeps a backlog and saves. Gate: `python -m unittest tests.test_vn_saves -v`.
- Open: none logged.
- Code: tests/test_vn_saves.py, channels/vn_bot.py.

## Voice
- State: MiniMax clone voice through the TTS handler; idle while she is down.
- Open: none logged.
- Code: channels/tts_handler.py, data/minimax/minimax_tts.py, sim/voicecheck.py.

## TypeSafe
- State: 18 uses, 13 on after the 2026-10-22 audit (docs/reports/2026-10-22_typesafe_audit.md). Cut: scene_director (constant staging 57/57), foresee (scored worse than the model, Brier 0.117 vs 0.077), wonder_answer and ick (model runs first anyway), inbound_signals (gate skipped 52 of 65 of his messages incl. compliments, apologies, news). Key replaced 10-22 18:51 in secerts/typesafe.txt (63/63 probes 200). Idle while Momoka is down.
- Open: unknown-value uses with no live data (which_one, intent, said_when, rupture_settle, expect_him, habits_him, affection, wonder, lookup, state_appraisal): judge on her next live week.
- Code: resident/app.py, resident/sight.py, config.py (grep typesafe).

## Smoke test
- State: works as a pre-restart gate; runs on a copy of her save.
- Open: none.
- Code: tools/smoke.py:110.

## Restart
- State: `tools/restart.ps1 -Target momoka` or `restart.cmd momoka`; run only after smoke passes.
- Open: none.
- Code: tools/restart.ps1, restart.cmd.

## Reports from runtime (his viewing history, not committed)
- State: reports/dossiers, reports/episodes, reports/plays.md, reports/transcripts.md are written by machine/dossier.py, machine/episode_reports.py, machine/plays.py, sim/transcripts.py. Gitignored.
