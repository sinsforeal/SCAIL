@echo off
rem Build the TALKAPP APK and release it: the gradle task copies it to
rem talkapp\app\talkapp.apk (served at /app/talkapp.apk) and writes
rem talkapp.ver, which the running app reads via /ver to offer the update.
rem The toolchain lives under F:\REPS2\tools (JDK 17, SDK 34, gradle 8.7).
setlocal
cd /d "%~dp0"
set JAVA_HOME=F:\REPS2\tools\jdk17-home
set ANDROID_HOME=F:\REPS2\tools\android-sdk
call F:\REPS2\tools\gradle-8.7-home\bin\gradle.bat assembleDebug --no-daemon -q
endlocal
