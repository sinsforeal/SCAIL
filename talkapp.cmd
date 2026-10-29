@echo off
rem TALKAPP hub: the messenger server his phone connects to over Tailscale.
rem Runs beside the bot in its own window, like the MAL daemon.
cd /d "%~dp0"
title TALKAPP hub
rem His machine is watched once: the collector (machine\collector.py) is the
rem machine's own process, started here because the hub is the machine's too
rem and goes up first. pythonw, so no window; single instance; it logs to
rem logs\machine_collector.log. restart.cmd stops it with the hub.
set "PY=python"
if exist "C:\Python314\python.exe" set "PY=C:\Python314\python.exe"
set "PYW=pythonw"
if exist "C:\Python314\pythonw.exe" set "PYW=C:\Python314\pythonw.exe"
if not exist "%~dp0logs" mkdir "%~dp0logs"
start "" "%PYW%" -u "%~dp0machine\collector.py" >> "%~dp0logs\machine_collector.stdout.log" 2>&1
"%PY%" talkapp\server.py
pause
