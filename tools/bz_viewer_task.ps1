# Registers SCAIL_bz_viewer: keeps the B-zombie viewer (http://127.0.0.1:18350/) up.
# At logon and every 15 min it runs `pythonw -m bzombie.viewer start`, which exits at once when the viewer answers
# /api/options and otherwise starts it hidden (CREATE_NO_WINDOW). Written 2026-10-28 after the viewer stayed down
# from the 10-25 PC loss until the User found the page not loading.
$ErrorActionPreference = "Stop"
$repo = "F:\REPS2\SCAILV4"
$py = "C:\Python314\pythonw.exe"
$action = New-ScheduledTaskAction -Execute $py -Argument "-m bzombie.viewer start" -WorkingDirectory $repo
$logon = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$every = New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Minutes 15)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName "SCAIL_bz_viewer" -Action $action -Trigger @($logon, $every) -Settings $settings `
    -Description "Keeps the B-zombie viewer on 127.0.0.1:18350 up (tools/bz_viewer_task.ps1)" -Force | Out-Null
Get-ScheduledTask -TaskName "SCAIL_bz_viewer" | Select-Object TaskName, State
