@echo off
rem MyAnimeList mirror daemon: keeps data/mal_history.db current forever
rem (list updates + new episodes every 5 min, full panel reconcile every 6 h,
rem plus the hourly look at whether the outage in front of MyAnimeList is over).
rem
rem This is the machine's process, not a character's: there is one of it and it
rem mirrors HIS watch history. The scheduled task SCAIL_mal runs this file, and
rem restart.cmd stops and starts it between the hub and the characters.
rem
rem It launches the daemon DETACHED under pythonw, which has no console at all,
rem so nothing appears on his desktop and nothing can be closed by accident.
rem Two consequences worth knowing:
rem   - there is no `pause` at the end, unlike the other launchers here. A pause
rem     would hold a console open, which is the thing pythonw is chosen to
rem     avoid; and because this file exits at once, the task never sits at a
rem     "press any key" prompt with the next `schtasks /run` silently ignored.
rem   - no `>>` redirect either. cmd binds a redirect on `start` to `start`
rem     itself rather than to the process it detaches, which sent eight days of
rem     the daemon's lines to a handle that goes nowhere. The daemon writes
rem     logs\mal_daemon.log itself (its --log, defaulted).
rem
rem Single instance, by the lock file beside the mirror: a second one prints
rem the pid of the first and exits.
rem
rem Needs the MAL login done once: python tools\mal_history.py login
rem To watch it work, run it in a window of your own instead -- with a console
rem its log is a tee, so the lines appear in both places:
rem   python tools\mal_history.py daemon --interval 300 --reconcile 6
setlocal
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
rem a detached console does not always inherit a PATH with python on it
set "PYW=pythonw"
if exist "C:\Python314\pythonw.exe" set "PYW=C:\Python314\pythonw.exe"
if not exist "%~dp0logs" mkdir "%~dp0logs"
start "" "%PYW%" -u "%~dp0tools\mal_history.py" daemon --interval 300 --reconcile 6
