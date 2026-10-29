@echo off
rem His machine is watched once: the collector belongs to the machine and not
rem to a character. Both characters read what it writes
rem (`data/telemetry_now.json`, `data/telemetry_feed.jsonl`, the `.attention`
rem file beside them), so it runs on its own rather than inside a bot.
rem talkapp.cmd starts one too; this is the launcher for a machine with no hub.
cd /d F:\REPS2\SCAILV4
set PYTHONIOENCODING=utf-8
set "PY=python"
if exist "C:\Python314\python.exe" set "PY=C:\Python314\python.exe"
title SCAIL collector
"%PY%" machine\collector.py --config config_momoka.json
echo.
echo collector exited.
pause
