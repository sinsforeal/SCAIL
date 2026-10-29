@echo off
rem Live SCAIL: 千代田百花 (Chiyoda Momoka), the one character this fork runs.
rem Telegram + PC sensors on the real clock. Window stays open on exit.
rem
rem It starts her and nothing else. The MyAnimeList mirror daemon used to be
rem started from here, which meant `restart.cmd momoka` could never restart it:
rem the daemon is single-instance by a lock file, so the start line found the
rem old one and exited. It is the machine's process, not hers -- task SCAIL_mal,
rem mal_daemon.cmd -- and restart.cmd manages it between the hub and the
rem characters.
setlocal
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
title SCAIL Momoka (live)
rem a detached console does not always inherit a PATH with python on it
set "PY=python"
if exist "C:\Python314\python.exe" set "PY=C:\Python314\python.exe"
if not exist "%~dp0logs" mkdir "%~dp0logs"
"%PY%" resident\run.py --config config_momoka.json --db data\momoka.db
echo.
echo scail exited. window stays open.
pause
