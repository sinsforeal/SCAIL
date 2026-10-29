@echo off
rem Bring everything up: the MyAnimeList mirror daemon, then every character
rem in characters.json, in that order, after smoke.
rem
rem   startall.cmd              start whatever is down
rem   startall.cmd --no-smoke   skip the build check (say why in the log)
rem   startall.cmd --list       what it would act on, and nothing else
rem
rem It starts what is down and touches nothing that is up: a target already
rem running has its pid printed and is left alone, and a target matching more
rem than one process is reported and left alone as well. Nothing here kills
rem anything. restart.cmd is the one that stops: use it to put a code change on
rem the air, and this after a reboot or when one process has died.
rem
rem The daemon goes up before the characters, because a character reads the
rem mirror. The TALKAPP hub is not started: this fork does not run it (see
rem tools/restart.ps1).
rem
rem Everything goes through the scheduled tasks, and that is not a preference:
rem a bot started as a child of a tool's shell dies silently minutes later. A
rem registered character whose task is missing has it created here.
rem
rem Documented in PROJECT.md section 14 and in CLAUDE.md under Running.

setlocal
cd /d "%~dp0"

set SMOKE=
if /i "%1"=="--no-smoke" set SMOKE=-NoSmoke

set LIST=
if /i "%1"=="--list" set LIST=-List

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\restart.ps1" -Target all -StartOnly %SMOKE% %LIST%
exit /b %ERRORLEVEL%
