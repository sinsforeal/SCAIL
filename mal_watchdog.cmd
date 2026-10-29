@echo off
rem Five-minute health check for the MyAnimeList mirror daemon: is it up, and
rem is it stuck. Run by the scheduled task SCAIL_mal_watchdog
rem (tools/mal_watchdog_setup.ps1 registers it), independent of restart.cmd,
rem startall.cmd, and tools/smoke.py -- none of those gate this, and this
rem never touches any of them.
rem
rem One check per launch, not a loop: the scheduler supplies the 5-minute
rem cadence, this just runs tools/mal_watchdog.py and exits. Under pythonw,
rem same as mal_daemon.cmd, so nothing flashes on his desktop every 5 min.
rem Its own log: logs/mal_watchdog.log (dated lines, appended).
setlocal
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set "PYW=pythonw"
if exist "C:\Python314\pythonw.exe" set "PYW=C:\Python314\pythonw.exe"
if not exist "%~dp0logs" mkdir "%~dp0logs"
"%PYW%" -u "%~dp0tools\mal_watchdog.py"
