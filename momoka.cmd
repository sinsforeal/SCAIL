@echo off
rem Live SCAIL V4, the one resident character: 千代田百花 (Chiyoda Momoka).
rem She has her own config and her own save. The singleton lock is keyed to the
rem database path. Window stays open on exit.
rem
rem She is a `resident`-program character, so this runs the same entry point the
rem other residents do and names her config and her save on the command line --
rem resident\run.py falls back to the second character's when they are absent,
rem which is what these two flags are here to prevent.
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
echo scail (Momoka) exited. window stays open.
pause
