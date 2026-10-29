# Starts the bench worker claude session hidden (Start-Process -WindowStyle Hidden). Called by launch_bench_worker.cmd.
# -DryRun prints the claude line and starts nothing.
param([Parameter(Mandatory = $true)][string]$HomeDir, [string]$Model = "claude-sonnet-5-5", [switch]$DryRun)
$deny = "Artifact,ArtifactData,ArtifactComments,ArtifactCheck,DesignSync,Workflow,ScheduleWakeup,ReportFindings,SendFeedback,ReadNotifications,AskUserQuestion,Skill,EnterPlanMode,ExitPlanMode"
# Windows PowerShell does not quote array elements: the quotes below are part of the command line.
# --disallowedTools takes a variable number of values: written as one token, and the prompt goes first, so the
# prompt is never swallowed as a deny rule (meta 10-22 18:05: "Deny rule Start / the / loop. matches no tool").
$args2 = @('"Start the loop."', "--dangerously-skip-permissions", "--model", $Model, "--name", '"scail bench"',
           "--system-prompt-file", "CLAUDE.md", "--strict-mcp-config", "--disallowedTools=`"$deny`"")
if ($DryRun) { Write-Output ("DRY_RUN claude " + ($args2 -join " ")); exit 0 }
Start-Process -FilePath "claude" -WorkingDirectory $HomeDir -WindowStyle Hidden -ArgumentList $args2
