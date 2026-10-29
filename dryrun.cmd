@echo off
rem Accelerated dry run of one day in her life, console only, no sensors.
rem Edit the start time / speed / hours / injected messages here.
setlocal
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
title SCAIL dry run
rem a detached console does not always inherit a PATH with python on it
set "PY=python"
if exist "C:\Python314\python.exe" set "PY=C:\Python314\python.exe"
if exist data\dryrun.db del data\dryrun.db
"%PY%" resident\run.py --config config_momoka.json --db data/dryrun.db --sim "2026-08-19 07:30" --speed 20 --hours 4 --say "09:05|you awake? i saw a cat that looked exactly like the one in that video" --say "10:40|ok going to bed for real. talk later"
echo.
echo dry run finished. window stays open.
pause
