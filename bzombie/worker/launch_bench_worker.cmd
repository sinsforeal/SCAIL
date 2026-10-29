@echo off
rem SCAIL bench worker launcher (orchestrator 10-22 17:30, meta terms). Starts the worker session HIDDEN via
rem start_hidden.ps1 (Start-Process -WindowStyle Hidden; it keeps its console; same permission mode as launch_scail.cmd,
rem so it never waits on a prompt). Not wired into restart_windows or rc_reconnect. No channel flag, no --mcp-config
rem (--strict-mcp-config keeps the user-scope feed and pick-assist MCP servers out). The launcher exits at once.
rem BENCH_DRY_RUN=1 prints the resolved values and the claude line, writes nothing, starts nothing.
rem Home folder F:\REPS2\SCAIL_bench_worker is outside the SCAILV4 tree: SCAILV4's CLAUDE.md, project hooks and handoff
rem state do not load there. F:\REPS2 itself has no CLAUDE.md and no .claude (checked 10-22 17:30).
setlocal
for %%i in ("%~dp0.") do set "SRC=%%~fi"
set "HOME_DIR=F:\REPS2\SCAIL_bench_worker"
set "MP=F:\REPS2\Meta_Orchestrator"
set "TEMP=F:\temp"
set "TMP=F:\temp"
set "PYTHONUTF8=1"
set "BZ_PY=%MP%\.venv\Scripts\python.exe"
set "BZ_IO=%SRC%\worker_io.py"
set "BZ_QUEUE=H:\SCAIL\bzombie\var\claude_queue"
set "MODEL_ID=claude-sonnet-5-5"
rem Clean environment: a launch from inside a Claude Code session must not inherit the child markers.
for %%v in (CLAUDECODE CLAUDE_CODE_CHILD_SESSION CLAUDE_CODE_SESSION_ID CLAUDE_CODE_BRIDGE_SESSION_ID CLAUDE_CODE_MESSAGING_SOCKET CLAUDE_CODE_MESSAGING_TOKEN CLAUDE_PID CLAUDE_CODE_ENTRYPOINT CLAUDE_CODE_SESSION_ATTENDED CLAUDE_EFFORT CLAUDE_CODE_EXECPATH CLAUDE_CODE_ENABLE_FUNCTION_HOOKS CLAUDE_CODE_PARENT_SESSION_ID) do set "%%v="
set "CLAUDE_CODE_USE_POWERSHELL_TOOL=0"
if defined BENCH_DRY_RUN (
  echo DRY_RUN home=%HOME_DIR%
  echo DRY_RUN src=%SRC%
  powershell -NoProfile -File "%SRC%\start_hidden.ps1" -HomeDir "%HOME_DIR%" -Model %MODEL_ID% -DryRun
  endlocal
  exit /b 0
)
if not exist "%HOME_DIR%\.claude\" mkdir "%HOME_DIR%\.claude"
if not exist "F:\temp\" mkdir "F:\temp"
if not exist "%BZ_QUEUE%\done\" mkdir "%BZ_QUEUE%\done"
copy /y "%SRC%\CLAUDE.md" "%HOME_DIR%\CLAUDE.md" >nul
if errorlevel 1 (
  echo launcher: cannot copy CLAUDE.md to %HOME_DIR%, not starting
  exit /b 1
)
copy /y "%SRC%\settings.json" "%HOME_DIR%\.claude\settings.json" >nul
if errorlevel 1 (
  echo launcher: cannot write %HOME_DIR%\.claude\settings.json, not starting
  exit /b 1
)
powershell -NoProfile -File "%SRC%\start_hidden.ps1" -HomeDir "%HOME_DIR%" -Model %MODEL_ID%
endlocal
exit /b %errorlevel%
