@echo off
rem Start the B-zombie gateway hidden on 127.0.0.1:18330. Stop with stop.cmd.
set TEMP=H:\SCAIL\temp
set TMP=H:\SCAIL\temp
start "" /B "C:\Python314\pythonw.exe" "%~dp0launch.py"
