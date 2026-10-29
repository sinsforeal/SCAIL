@echo off
rem Stop and start the live processes in the right order, after smoke.
rem
rem   restart.cmd              the MAL daemon and every character
rem   restart.cmd mal          mal, or any character's key from characters.json
rem   restart.cmd all --no-smoke     skip the build check (say why in the log)
rem   restart.cmd --list       what it would act on, and nothing else
rem
rem The MAL daemon goes up before the characters. Processes are matched on
rem their exact command line, never by image name, and a target matching more
rem than one process stops the script. The TALKAPP hub is not a target: this
rem fork does not run it (see tools/restart.ps1).
rem
rem A launcher .cmd cannot be edited while its console is reading it, so a
rem change is staged beside it as <launcher>.next and swapped in here, between
rem the stop and the start.
rem
rem Documented in PROJECT.md section 14 and in CLAUDE.md under Running.

setlocal
cd /d "%~dp0"

set TARGET=%1
if "%TARGET%"=="" set TARGET=all

set SMOKE=
if /i "%2"=="--no-smoke" set SMOKE=-NoSmoke
if /i "%1"=="--no-smoke" (set TARGET=all& set SMOKE=-NoSmoke)

set LIST=
if /i "%2"=="--list" set LIST=-List
if /i "%1"=="--list" (set TARGET=all& set LIST=-List)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\restart.ps1" -Target %TARGET% %SMOKE% %LIST%
exit /b %ERRORLEVEL%
