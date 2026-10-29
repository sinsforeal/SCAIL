@echo off
rem Capture the emulator's screen to a PNG. Default target is
rem talkapp\android\shots\talkapp_<yyyymmdd_hhmmss>.png; pass a path to choose
rem your own. exec-out is what keeps the bytes intact -- plain `adb shell
rem screencap -p` corrupts a PNG on Windows by translating line endings.
rem
rem   emu-shot.cmd
rem   emu-shot.cmd F:\somewhere\before.png
setlocal
cd /d "%~dp0"

set ANDROID_HOME=F:\REPS2\tools\android-sdk
set ADB=%ANDROID_HOME%\platform-tools\adb.exe
set SERIAL=emulator-5556

"%ADB%" -s %SERIAL% shell getprop sys.boot_completed 2>nul | findstr /b "1" >nul
if errorlevel 1 (
  echo %SERIAL% is not booted -- run emu.cmd first.
  exit /b 1
)

set OUT=%~1
if "%OUT%"=="" (
  for /f "delims=" %%t in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set STAMP=%%t
  if not exist "%~dp0shots" mkdir "%~dp0shots"
  call set OUT=%%~dp0shots\talkapp_%%STAMP%%.png
)

"%ADB%" -s %SERIAL% exec-out screencap -p > "%OUT%"
if errorlevel 1 (
  echo Screencap failed.
  exit /b 1
)
for %%f in ("%OUT%") do echo Screenshot: %%~ff  (%%~zf bytes)
endlocal
exit /b 0
