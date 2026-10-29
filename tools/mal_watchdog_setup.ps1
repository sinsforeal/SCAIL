# Registers the 5-minute watchdog for the MAL mirror daemon as its own
# scheduled task, SCAIL_mal_watchdog -- separate from SCAIL_mal itself, and
# independent of restart.cmd/startall.cmd/tools/smoke.py (none of those gate
# this, and this never touches any of them, Momoka, or any other character).
#
# schtasks.exe's plain CLI (what tools/restart.ps1 uses for SCAIL_mal) can
# only give a task one trigger and cannot mark it Hidden, and this needs
# three triggers (every 5 minutes, at logon, at startup) and Hidden so
# nothing flashes on his desktop twelve times an hour -- so this uses the
# ScheduledTasks module instead. Safe to re-run: -Force replaces the task
# with the same definition rather than erroring if it already exists.
#
# Run once by hand, no elevation needed (matches SCAIL_mal: interactive
# token, current user, no /ru):
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\mal_watchdog_setup.ps1

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$taskName = "SCAIL_mal_watchdog"
# Matches the live task (checked 2026-10-22): pythonw runs the watchdog directly,
# no cmd.exe or wscript shim, so nothing flashes.
$py = "C:\Python314\pythonw.exe"
$script = Join-Path (Get-Location) "tools\mal_watchdog.py"
if (-not (Test-Path $py) -or -not (Test-Path $script)) {
    Write-Host "pythonw ($py) or the watchdog ($script) is not on disk -- nothing to register."
    exit 1
}

$action = New-ScheduledTaskAction -Execute $py -Argument "-u `"$script`"" -WorkingDirectory (Get-Location)

# Every 5 minutes forever, plus at logon and at boot -- "where possible"
# because AtStartup only fires anything once someone is logged on anyway,
# given the InteractiveToken logon type this and SCAIL_mal both use.
$triggers = @(
    (New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 3650)),
    (New-ScheduledTaskTrigger -AtLogOn),
    (New-ScheduledTaskTrigger -AtStartup)
)

# Hidden: no console window every 5 minutes. IgnoreNew: a check that is
# still running (should never take more than ~15s, but a hung schtasks call
# could) is not joined by a second one. A short execution time limit so a
# genuinely stuck watchdog run does not sit forever either.
$settings = New-ScheduledTaskSettingsSet -Hidden -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 4) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $triggers -Settings $settings -Force | Out-Null

$check = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($check) {
    Write-Host "registered $taskName -- $($check.Triggers.Count) trigger(s), state $($check.State)"
} else {
    Write-Host "registration did not stick -- check manually with: Get-ScheduledTask -TaskName $taskName"
    exit 1
}
