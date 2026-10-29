@echo off
rem Put the whole of SCAIL down on purpose, and leave a record that it happened.
rem
rem   stopall.cmd                           stop everything, on purpose
rem   stopall.cmd why words here            the same, with his reason on every record
rem   stopall.cmd --no-credit <reason>      the machine's own decision, launched by the bot
rem
rem WHY IT IS NOT CALLED shutdown.cmd. Windows has a `shutdown` command of
rem its own, three keystrokes from turning his machine off, and a console
rem that does not search the current directory first resolves the bare word
rem to that one rather than to this file. This name sits beside
rem startall.cmd, says what it does, and collides with nothing.
rem
rem Everything means everything: the hub, the MyAnimeList mirror daemon, the
rem collector the hub starts, and every character in characters.json. There is
rem no shutting down one of them -- the others would go on writing beside her,
rem and a character left under a hub that has been stopped cannot be reached
rem from his phone at all. Use restart.cmd <key> for one process.
rem
rem THE FAILURE IT EXISTS FOR. A character who is stopped and started again has
rem a stretch of hours during which nobody wrote her: no schedule, no scenes, no
rem messages, no compile. When she comes back, the day machinery has to account
rem for that stretch somehow, and with nothing on her record to say what
rem happened it fills it in from placeholders -- a day that reads as lived
rem because nothing said otherwise, which is the one thing this project cannot
rem afford her to carry. So the stop writes the reason and the moment into every
rem character's save, and her next boot turns the span between that moment and
rem her return into one temporal-gap event: a blank she knows about instead of a
rem day she was told she had. A stop that leaves no record is what this replaces.
rem
rem It runs no build check, unlike restart.cmd and startall.cmd. Smoke protects
rem a start, and nothing is starting; the reasons in full are in the header of
rem tools/restart.ps1. The check comes back at the next startall.cmd.
rem
rem The two kinds of stop are told apart on her record. Without --no-credit the
rem stop is his: he shut the machine down and this is what he said about it.
rem With it, the stop is the machine's own -- the bot with no money left to
rem answer with, shutting itself down rather than failing every call -- and she
rem is told a different thing about the gap when she comes back.
rem
rem No `pause` at the end. The other launchers pause because a scheduled task
rem holds their console and ending the task must not close it out from under
rem the interpreter; this one is run from a terminal, and the bot launches it
rem detached, where a pause would leave a window standing forever.
rem
rem Bring it all back with startall.cmd, which does run smoke.
rem
rem Documented in PROJECT.md section 14 and in CLAUDE.md under Running.

setlocal
cd /d "%~dp0"

if /i "%~1"=="--help" goto :usage
if /i "%~1"=="-h" goto :usage
if "%~1"=="/?" goto :usage

rem The reason is the rest of the command line, quoted or not: `stopall.cmd
rem moving the machine` and `stopall.cmd "moving the machine"` are the same
rem thing. It is collected one argument at a time with %~1, which takes the
rem quotes off, rather than from %* -- a reason he typed in quotes came out of
rem %* with them still on, and a value beginning with a quote broke the next
rem `if` before it ever reached PowerShell.
set "KIND=operator"
if /i "%~1"=="--no-credit" goto :nocredit
goto :collect
:nocredit
set "KIND=no_credit"
shift
:collect
set "ARGS="
:more
if "%~1"=="" goto :ready
if defined ARGS (set "ARGS=%ARGS% %~1") else (set "ARGS=%~1")
shift
goto :more
:ready
if not defined ARGS set "ARGS=no reason given"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\restart.ps1" -Shutdown -Kind %KIND% -Why "%ARGS%"
exit /b %ERRORLEVEL%

:usage
echo Stop the whole of SCAIL on purpose and write down why.
echo.
echo   stopall.cmd                           stop everything, on purpose
echo   stopall.cmd why words here            the same, with his reason on every record
echo   stopall.cmd --no-credit ^<reason^>      the machine's own decision, launched by the bot
echo.
echo Everything goes down: the hub, the mirror daemon, the collector and every
echo character. The reason is written into every character's save and into
echo logs/shutdowns.log. startall.cmd brings it all back.
exit /b 0
