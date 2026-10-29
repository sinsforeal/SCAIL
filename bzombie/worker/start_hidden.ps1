# Starts the bench worker claude session hidden (Start-Process -WindowStyle Hidden). Called by launch_bench_worker.cmd.
# -DryRun prints the claude line and starts nothing.
param([Parameter(Mandatory = $true)][string]$HomeDir, [string]$Model = "claude-sonnet-5-5", [switch]$DryRun)
$deny = "Artifact,ArtifactData,ArtifactComments,ArtifactCheck,DesignSync,Workflow,ScheduleWakeup,ReportFindings,SendFeedback,ReadNotifications,AskUserQuestion,Skill,EnterPlanMode,ExitPlanMode"
# Windows PowerShell does not quote array elements: the quotes below are part of the command line.
# --disallowedTools takes a variable number of values: written as one token, and the prompt goes first, so the
# prompt is never swallowed as a deny rule (meta 10-22 18:05: "Deny rule Start / the / loop. matches no tool").
$args2 = @('"Start the loop."', "--dangerously-skip-permissions", "--model", $Model, "--name", '"scail bench"',
           "--system-prompt-file", "CLAUDE.md", "--strict-mcp-config", "--disallowedTools=`"$deny`"")
# Under meta's worker supervisor (the User 10-27 22:17, meta 240815f): it sets CLAUDE_WORKER=scail_bench so the
# agents' call and context caps count this session, writes the worker hook subset, and restarts a fresh session on
# exit or at the soft cap. One supervisor per name (pid file); stop file <HomeDir>\var\workers\scail_bench.stop.
$sup = @("F:\REPS2\Meta_Orchestrator\tools\worker_supervise.py", "--name", "scail_bench", "--dir", "`"$HomeDir`"", "--") + $args2
if ($DryRun) { Write-Output ("DRY_RUN python " + ($sup -join " ")); exit 0 }
Start-Process -FilePath "F:\REPS2\Meta_Orchestrator\.venv\Scripts\python.exe" -WorkingDirectory $HomeDir -WindowStyle Hidden -ArgumentList $sup
