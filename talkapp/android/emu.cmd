@echo off
rem Run the TALKAPP APK on the local Android emulator, with no hub, no bot and
rem no simulation. Starts the virtual device if it is not already up, waits for
rem Android to finish booting, installs talkapp\app\talkapp.apk over whatever
rem is there and launches the activity. This touches nothing the live system
rem uses: its own AVD, its own adb serial, its own console.
rem
rem   emu.cmd            start (if needed), install, launch
rem   emu.cmd --shot     the same, then capture a screenshot via emu-shot.cmd
rem   emu.cmd stop       shut this emulator down (that instance only)
rem
rem The device is started by re-entering this file under `start` with --serve,
rem so the emulator gets a console of its own and keeps running after this
rem script has installed and launched. --serve is not meant to be run by hand.
rem
rem This needs CPU virtualisation, which is currently switched off in this
rem machine's firmware; see the emulator setup report under data\retired\.
setlocal
cd /d "%~dp0"

set ANDROID_HOME=F:\REPS2\tools\android-sdk
set ANDROID_SDK_ROOT=F:\REPS2\tools\android-sdk
set ANDROID_AVD_HOME=F:\REPS2\tools\android-sdk\.avd
set ADB=%ANDROID_HOME%\platform-tools\adb.exe
set EMU=%ANDROID_HOME%\emulator\emulator.exe
set AVD=avd_api34
set PORT=5556
set SERIAL=emulator-%PORT%
set PKG=net.scail.talkapp
set ACTIVITY=%PKG%/.MainActivity
set APK=%~dp0..\app\talkapp.apk
set LOG=%~dp0emulator.log

rem A cold boot with working CPU acceleration is a couple of minutes. Raise
rem EMU_BOOT_MINUTES if it needs longer. Set EMU_ACCEL=off to let it try
rem without acceleration -- that does not currently reach a booted system.
if "%EMU_BOOT_MINUTES%"=="" set EMU_BOOT_MINUTES=15
if "%EMU_ACCEL%"=="" set EMU_ACCEL=auto
set /a MAXTRIES=%EMU_BOOT_MINUTES%*6

if /i "%~1"=="--serve" goto serve
if /i "%~1"=="stop" goto stop

if not exist "%APK%" (
  echo No APK at %APK% -- run build.cmd first.
  exit /b 1
)

"%ADB%" start-server >nul 2>&1

"%ADB%" -s %SERIAL% shell getprop sys.boot_completed 2>nul | findstr /b "1" >nul
if not errorlevel 1 (
  echo Emulator %SERIAL% is already booted.
  goto install
)

echo Starting %AVD% on port %PORT% -- a cold boot takes a few minutes.
echo Emulator output: %LOG%
start "TALKAPP emulator %AVD%" /min "%~f0" --serve

set /a TRIES=0
:waitboot
"%ADB%" -s %SERIAL% shell getprop sys.boot_completed 2>nul | findstr /b "1" >nul
if not errorlevel 1 goto booted
set /a TRIES+=1
if %TRIES% GEQ %MAXTRIES% (
  echo Gave up after %EMU_BOOT_MINUTES% minutes waiting for %SERIAL% to boot. See %LOG%.
  exit /b 1
)
ping -n 11 127.0.0.1 >nul
goto waitboot

:booted
echo Booted after about %TRIES% x 10 seconds.
"%ADB%" -s %SERIAL% shell wm dismiss-keyguard >nul 2>&1

:install
for /f "usebackq delims=" %%v in ("%~dp0..\app\talkapp.ver") do echo APK version: %%v
"%ADB%" -s %SERIAL% install -r "%APK%"
if errorlevel 1 (
  echo Install failed.
  exit /b 1
)
"%ADB%" -s %SERIAL% shell am start -n %ACTIVITY%
if errorlevel 1 (
  echo Launch failed.
  exit /b 1
)
echo Running. The app loads its page from the tailnet, so with no tailnet it
echo will show its shell and an error where the conversation would be.

if /i "%~1"=="--shot" (
  ping -n 16 127.0.0.1 >nul
  call "%~dp0emu-shot.cmd"
)
endlocal
exit /b 0

:serve
rem Foreground in its own console. The software renderer is chosen rather than
rem the host GPU because nothing here needs rendering speed and it behaves the
rem same on any machine; -gpu host is the faster choice for interactive use.
"%EMU%" -avd %AVD% -port %PORT% -no-window -no-audio -no-boot-anim -no-snapshot -no-metrics -gpu swiftshader -accel %EMU_ACCEL% > "%LOG%" 2>&1
exit /b

:stop
"%ADB%" -s %SERIAL% emu kill
echo Told %SERIAL% to shut down.
endlocal
exit /b 0
