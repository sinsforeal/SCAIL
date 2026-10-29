# Stop and start the live processes, safely and in the right order.
#
# Doing this by hand is three commands per process and two of them are easy to
# get wrong. The order matters -- the mirror daemon goes up before the
# characters, because a character reads the mirror -- and ending the scheduled
# task is not enough on its own, because the launcher ends in `pause` so the
# task stays "running" with a live child underneath it.
#
# WHAT IT WILL NOT DO. It never kills by image name. A filter over running
# processes once killed another program and left the
# bot untouched, so every process here is found by its exact command line --
# `scail.py` with her config for the second character, `scail.py` without it
# for the first -- and if a target matches more than one process it stops and
# says so rather than guessing. Nothing outside this project can match.
#
# FOUR MODES. By default every target named is stopped and started again.
# `-StopOnly` stops and does not start. `-StartOnly` starts what is down and
# leaves anything already up exactly as it is: the cold start after a reboot,
# or bringing back the one process that died, without interrupting the rest.
# startall.cmd is that mode; restart.cmd is the one that stops things.
# `-Shutdown` puts the whole of SCAIL down on purpose and leaves a record of
# it -- every target, no start, and then the reason written into every
# character's save so that the stretch nobody wrote her comes back as an
# honest blank instead of a day the machinery invents from placeholders when
# she is started again. stopall.cmd is that mode.
#
# WHY -Shutdown SKIPS THE BUILD CHECK, when the rule everywhere else is smoke
# before everything. Smoke protects a START: it refuses when a fix on disk
# will not import, because starting on that code takes a character off the air
# rather than improving her. A shutdown starts nothing, so there is nothing
# for it to protect -- and it would be the wrong thing here in two ways. It
# takes about a minute, which is a minute of a stop somebody is standing over
# or of a bot that has run out of money going on spending; and code that fails
# to import is a REASON to shut down, so refusing on it would leave the
# machine up in exactly the state the operator was trying to end. The build
# check comes back at the next startall.cmd, before anything runs again.
#
# Called by restart.cmd (or startall.cmd, or stopall.cmd); run those rather
# than this.

param(
    [string]$Target = "all",
    [switch]$NoSmoke,
    [switch]$List,
    # Stop and do not start. What it is for: a one-off script that writes a
    # store whose only writer is one of these processes -- a save, the mirror
    # -- and which refuses to run while that process is up. The start is a
    # `restart.cmd <key>` of its own afterwards, so smoke runs before anything
    # comes back.
    [switch]$StopOnly,
    # Start and never stop. A process that is already serving is left alone --
    # a start must not be a way to interrupt something by accident -- so the
    # only thing this can do to a running target is print its pid.
    [switch]$StartOnly,
    # Stop the whole of SCAIL on purpose and write down that it happened.
    # Every target whatever -Target says: a shutdown that left one character
    # running would leave her alone on a machine whose other processes are gone.
    [switch]$Shutdown,
    # The one plain sentence that goes onto every character's record and into
    # logs/shutdowns.log. It is read at her next boot and is the difference
    # between a blank she can account for and a blank she cannot.
    [string]$Why = "",
    # Whose decision the stop was: "operator" is his, "no_credit" is the
    # machine's own -- the bot asking to be shut down because there is no
    # money left to answer with. She is told a different thing in each case.
    [string]$Kind = "operator"
)

# Deliberately NOT "Stop". Walking the process table touches system processes
# whose command line cannot be read, and under Stop the first of those aborts
# the enumeration inside the pipeline -- which reported every process as not
# running, restarted a hub that was already up, and left it dead on the port.
$ErrorActionPreference = "Continue"
Set-Location (Split-Path -Parent $PSScriptRoot)

if ($StartOnly -and $StopOnly) {
    Write-Host "-StartOnly and -StopOnly ask for opposite things. Pick one."
    exit 2
}
if ($Shutdown -and $StartOnly) {
    Write-Host "-Shutdown and -StartOnly ask for opposite things. Pick one."
    exit 2
}
if ($Shutdown -and ($Kind -ne "operator") -and ($Kind -ne "no_credit")) {
    Write-Host "-Kind is 'operator' (his decision) or 'no_credit' (the machine's own). Got '$Kind'."
    exit 2
}
if ($Shutdown -and -not $Why) {
    # An empty reason is a record that says nothing, and it is also an
    # argument a native call would drop rather than pass as "".
    $Why = "stopped from stopall.cmd, no reason given"
}

# task name, how to recognise its process, its launcher, and what to call it
# in the output. The one row written here belongs to the MACHINE rather than to
# any character -- the daemon that keeps his MyAnimeList watch history mirrored
# -- so it stays in the script; the characters are read from `characters.json`
# (tools/registry.py), so a third one is a row in that file and not an edit to
# this script. The old table was two hand-written rows whose first matched the
# first character as "scail.py NOT followed by the second one's config", which
# would have matched a third character's process and killed it under the first
# one's name.
#
# The TALKAPP hub used to be a second machine row (task SCAIL_hub, launcher
# talkapp.cmd). This fork does not run it: Momoka is a resident with the VN
# channel and `talkapp.enabled` is false, so the hub is dead weight -- and its
# server reads `config.json`, which this fork does not keep, so starting it
# only produced a task that ran and died. It is no longer a target here.
$KNOWN = @{
    "mal" = @{ Task = "SCAIL_mal"; Match = 'mal_history\.py"?\s+daemon'; Name = "the MAL daemon"; Launcher = "mal_daemon.cmd" }
}
# The machine's own process first, then the characters. The mirror daemon comes
# before the characters because a character reads the mirror.
$ORDER = @("mal")
$regPath = Join-Path (Get-Location) "characters.json"
if (Test-Path $regPath) {
    $reg = Get-Content $regPath -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($row in $reg.characters) {
        if (-not $row.key) { continue }
        $KNOWN[$row.key] = @{ Task = $row.task; Match = $row.match; Name = $row.name; Launcher = $row.launcher }
        $ORDER += $row.key
    }
} else {
    Write-Host "characters.json is missing: only the machine's own processes can be restarted from here."
}

function Task-Exists($task) {
    # A missing task is the one failure that looks like nothing happening:
    # `schtasks /run` on a name that does not exist prints an error nobody
    # reads and the process simply never comes up.
    schtasks /query /tn $task 2>&1 | Out-Null
    return ($LASTEXITCODE -eq 0)
}

function Task-Targets($task, $launcher) {
    # $null when the task is missing, $true when it already runs THIS
    # launcher, $false when it exists but runs another one. The XML form is
    # read rather than the LIST form because the field labels are localized
    # and this machine's locale is Japanese.
    $xml = schtasks /query /tn $task /xml 2>&1
    if ($LASTEXITCODE -ne 0) { return $null }
    $text = ($xml -join "`n")
    return ($text -match [regex]::Escape($launcher))
}

function Ensure-Task($key) {
    # A task that already runs the right launcher is left alone. A task that
    # is missing, or that runs a launcher from somewhere else, is (re)created
    # here with the command this used to print for a person to type. The row
    # in characters.json is the operator's statement that she runs; the task
    # is only the mechanism (no elevation, no trigger of its own: it is run
    # by name from here and nowhere else).
    #
    # The wrong-launcher case is not hypothetical: on 2026-09-17 the hub and
    # the MAL daemon tasks still named SCAILV3, so startall.cmd reported both
    # as "DID NOT COME UP" while the task itself ran and its child died at
    # once. Checking only that the task EXISTS made a start a no-op on a
    # machine whose tasks were made from another checkout.
    $k = $KNOWN[$key]
    $cmd = Join-Path (Get-Location) $k.Launcher
    if (-not (Test-Path $cmd)) {
        Write-Host "  the launcher $($k.Launcher) is not on disk, so $($k.Name) cannot be started from here."
        return $false
    }
    $state = Task-Targets $k.Task $cmd
    if ($state -eq $true) { return $true }
    if ($state -eq $false) {
        Write-Host "  the scheduled task $($k.Task) runs another launcher; repointing it at $cmd"
        # a running task cannot be replaced under itself
        schtasks /end /tn $k.Task 2>&1 | Out-Null
        Start-Sleep -Milliseconds 700
    } else {
        Write-Host "  the scheduled task $($k.Task) does not exist; creating it for $($k.Name)"
    }
    schtasks /create /tn $k.Task /tr "cmd /c $cmd" /sc once /st 23:59 /f 2>&1 | Out-Null
    if (Task-Exists $k.Task) {
        Write-Host "  set $($k.Task) -> cmd /c $cmd"
        return $true
    }
    Write-Host "  could not create $($k.Task); create it by hand and run this again:"
    Write-Host "    schtasks /create /tn $($k.Task) /tr ""cmd /c $cmd"" /sc once /st 23:59 /f"
    return $false
}

function Find-One($rx) {
    # Every process, matched on its command line. Narrowing by image name
    # first looked tidier and returned nothing, because the launcher is a
    # `cmd.exe` window with the interpreter underneath it and the name to
    # filter on depends on which layer you happen to catch.
    # The leading comma is load-bearing. A function that returns a one-element
    # array has it unrolled to a bare object on the way out, so `.Count` came
    # back empty rather than 1, every process read as not running, nothing was
    # ever stopped, and the start then launched a duplicate that the port and
    # the singleton lock had to refuse.
    return ,@(Get-CimInstance Win32_Process |
        Where-Object { $_.CommandLine -and ($_.CommandLine -match $rx) -and ($_.Name -match 'python') })
}

function Show-Running() {
    Write-Host ""
    foreach ($k in $ORDER) {
        $p = Find-One $KNOWN[$k].Match
        $pids = if ($p.Count) { ($p | ForEach-Object { $_.ProcessId }) -join ", " } else { "not running" }
        "{0,-8} {1,-16} {2}" -f $k, $KNOWN[$k].Name, $pids | Write-Host
    }
    Write-Host ""
}

function Stop-One($key) {
    $k = $KNOWN[$key]
    $before = Find-One $k.Match
    if ($before.Count -gt 1) {
        # two of the same character is the singleton lock failing, or a stale
        # child. Either way a script must not choose which to kill.
        Write-Host "  REFUSING: $($k.Name) matches $($before.Count) processes: $(($before | ForEach-Object { $_.ProcessId }) -join ', ')"
        Write-Host "  Look at them and stop the right one by hand."
        return $false
    }
    if ($before.Count -eq 1) {
        $procId = $before[0].ProcessId
        # The launcher window has to go too, and it is the reason a restart by
        # hand is fiddly: every .cmd here but the daemon's, which detaches and
        # exits, ends in `pause`, so ending the task
        # kills the interpreter and leaves the console sitting at "press any
        # key". The task then still counts as RUNNING, and the next
        # `schtasks /run` is silently ignored -- which is exactly how this
        # script failed the first time it was used. Kill the parent console as
        # well and the task genuinely ends.
        # The console FIRST, then the interpreter. cmd reads a batch file by
        # byte offset while it runs, so a console whose child has just died
        # carries on from the next line of whatever the file says NOW -- and on
        # 2026-09-03 the launcher had been edited under it, so the old hub
        # console started a second hub that took the port before the task's
        # own instance could (HISTORY §14).
        $parent = $before[0].ParentProcessId
        if ($parent) {
            $pp = Get-CimInstance Win32_Process -Filter "ProcessId=$parent" -ErrorAction SilentlyContinue
            # The console has to be THIS target's launcher, not merely a
            # console in this directory. The daemon used to be started by
            # `start` from inside run.cmd, which makes the first character's
            # launcher console its parent -- so the old check would have killed
            # her console while stopping the daemon. Fall back to the directory
            # test only for a row with no launcher named.
            $mine = if ($k.Launcher) { $pp.CommandLine -match [regex]::Escape($k.Launcher) } else { $pp.CommandLine -match [regex]::Escape($PWD.Path) }
            if ($pp -and $pp.Name -match 'cmd|conhost' -and $mine) {
                try { Stop-Process -Id $parent -Force -ErrorAction Stop } catch {}
            }
        }
        try { Stop-Process -Id $procId -Force -ErrorAction Stop } catch {}
        schtasks /end /tn $k.Task 2>&1 | Out-Null
        Start-Sleep -Seconds 2
        if (Get-Process -Id $procId -ErrorAction SilentlyContinue) {
            Write-Host "  $($k.Name): pid $procId is still alive after being asked twice"
            return $false
        }
        Write-Host "  stopped $($k.Name) (pid $procId)"
    } else {
        schtasks /end /tn $k.Task 2>&1 | Out-Null
        Write-Host "  $($k.Name) was not running"
    }
    return $true
}

function Start-One($key) {
    $k = $KNOWN[$key]
    if (-not (Ensure-Task $key)) { return $false }
    # a task left "running" at a pause prompt swallows the request without a
    # word, so make sure it is genuinely stopped before asking for it
    schtasks /end /tn $k.Task 2>&1 | Out-Null
    Start-Sleep -Milliseconds 700
    schtasks /run /tn $k.Task 2>&1 | Out-Null
    Start-Sleep -Seconds 10
    $after = Find-One $k.Match
    if ($after.Count -eq 1) {
        Write-Host "  started $($k.Name) -- pid $($after[0].ProcessId)"
        return $true
    }
    Write-Host "  $($k.Name) DID NOT COME UP (matched $($after.Count) processes)"
    return $false
}

function Start-IfDown($key) {
    # The whole of -StartOnly, one target at a time. A process that is up is
    # left running and only reported: somebody asking for a start is asking
    # for the thing to be up, not for the copy that is serving right now to be
    # replaced by a fresh one. Two matches is the case a script must never
    # settle by killing one, the same as in Stop-One, so it counts as a
    # failure and nothing is touched.
    $k = $KNOWN[$key]
    $now = Find-One $k.Match
    if ($now.Count -gt 1) {
        Write-Host "  REFUSING: $($k.Name) matches $($now.Count) processes: $(($now | ForEach-Object { $_.ProcessId }) -join ', ')"
        Write-Host "  Look at them and stop the right one by hand."
        return $false
    }
    if ($now.Count -eq 1) {
        Write-Host "  $($k.Name) is already running (pid $($now[0].ProcessId))"
        return $true
    }
    # A staged launcher may only be moved into place while nothing is reading
    # the file, and a target that is down is exactly that. Without this a
    # cold start would run the old launcher and leave the staged one waiting
    # for a restart that a start was meant to save.
    Swap-Staged $key
    return (Start-One $key)
}

function Swap-Staged($key) {
    # Replace a launcher from a staged copy while its console is dead.
    #
    # A launcher cannot be edited under a running process: cmd reads a batch
    # file by byte offset while it runs, so a console whose child has just died
    # carries on from the next line of whatever the file says NOW -- which is
    # how an edited talkapp.cmd started a second hub on the port. The window
    # where an edit is safe is exactly here, between the stop and the start.
    # So a change to a launcher is written beside it as `<launcher>.next` and
    # picked up on the next restart. Consuming the staged file is what makes a
    # re-run do nothing.
    $k = $KNOWN[$key]
    if (-not $k.Launcher) { return }
    $live = Join-Path (Get-Location) $k.Launcher
    $next = "$live.next"
    if (-not (Test-Path $next)) { return }
    if (-not (Test-Path $live)) { return }
    if ((Find-One $k.Match).Count) {
        Write-Host "  $($k.Launcher) NOT replaced: its process is still up"
        return
    }
    $consoles = @(Get-CimInstance Win32_Process |
        Where-Object { $_.Name -match 'cmd' -and $_.CommandLine -and ($_.CommandLine -match [regex]::Escape($k.Launcher)) })
    if ($consoles.Count) {
        Write-Host "  $($k.Launcher) NOT replaced: a console is still reading it (pid $(($consoles | ForEach-Object { $_.ProcessId }) -join ', '))"
        return
    }
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $keep = Join-Path (Get-Location) ("data\retired\" + $stamp + "_launcher")
    New-Item -ItemType Directory -Force -Path $keep | Out-Null
    Copy-Item $live (Join-Path $keep $k.Launcher) -Force
    Move-Item $next $live -Force
    Write-Host "  replaced $($k.Launcher) from $($k.Launcher).next -- the old one is in data/retired/$($stamp)_launcher/"
}

$targets = if ($Target -eq "all") { $ORDER } elseif ($KNOWN.ContainsKey($Target)) { @($Target) } else {
    Write-Host "unknown target '$Target'. Use: all, $($ORDER -join ', ')"
    exit 2
}

# A shutdown is the whole machine and nothing less. There is no such thing as
# shutting down one character: the others would go on writing beside her.
if ($Shutdown) { $targets = $ORDER }

if ($List) {
    # Read-only: what this script would act on, and whether it could.
    "{0,-8} {1,-16} {2,-16} {3,-16} {4,-8} {5}" -f "target", "what", "task", "launcher", "task?", "pids" | Write-Host
    foreach ($k in $ORDER) {
        $p = Find-One $KNOWN[$k].Match
        $pids = if ($p.Count) { ($p | ForEach-Object { $_.ProcessId }) -join ", " } else { "not running" }
        $staged = if (Test-Path (Join-Path (Get-Location) ($KNOWN[$k].Launcher + ".next"))) { "  [a staged launcher is waiting]" } else { "" }
        "{0,-8} {1,-16} {2,-16} {3,-16} {4,-8} {5}{6}" -f $k, $KNOWN[$k].Name, $KNOWN[$k].Task, $KNOWN[$k].Launcher,
            $(if (Task-Exists $KNOWN[$k].Task) { "yes" } else { "MISSING" }), $pids, $staged | Write-Host
    }
    exit 0
}

if ($Shutdown) {
    Write-Host "Shutting the whole of SCAIL down: $Why"
    Write-Host "Reason recorded as '$Kind'. Nothing is being started, so the build check is skipped (see the header)."
}
Write-Host "Running now:"
Show-Running

if ((-not $NoSmoke) -and (-not $Shutdown)) {
    # The rule is smoke before every restart, and the reason is that a fix on
    # disk that fails to import takes the character off the air rather than
    # improving her. Refusing here is the whole point of running it.
    Write-Host "Building the whole App against a copy of the save (tools/smoke.py)..."
    $smoke = & python tools/smoke.py 2>&1
    $ok = ($smoke | Select-String -SimpleMatch "[smoke] all clear")
    if (-not $ok) {
        Write-Host ""
        ($smoke | Select-String -Pattern "FAIL|FAILURE" | Select-Object -First 12) | ForEach-Object { Write-Host "  $_" }
        Write-Host ""
        Write-Host "SMOKE FAILED -- nothing was stopped or started. Fix it, or pass --no-smoke if you know why."
        exit 1
    }
    Write-Host "  smoke all clear"
}

# -StartOnly has no stop phase at all: not the processes, not the collector,
# not the reap. Reaping is a stop's tidying up, and `mal_history.py reap` kills
# every browser on the mirror's profile whether or not a daemon owns it, so
# running it here would take the running daemon's own Chrome. A daemon that is
# down and being started reaps for itself: it finds the lock naming a pid that
# is gone and calls the reaper before it opens a browser.
if (-not $StartOnly) {
    # stop in reverse order so the characters are down before the machine's own
    Write-Host ""
    Write-Host "Stopping:"
    # @() around the filter: with one target the pipeline hands back a bare string,
    # and [array]::Reverse has no overload for one, so a single-target restart
    # printed a binding error before it did the right thing anyway.
    $stopOrder = @($ORDER | Where-Object { $targets -contains $_ })
    [array]::Reverse($stopOrder)
    # What was up before any of it was touched, so the record of the stop can
    # name each process and its pid. Read here and not after: the point of the
    # next few lines is that those pids stop existing.
    $wasUp = @{}
    if ($Shutdown) {
        foreach ($k in $stopOrder) {
            $p = Find-One $KNOWN[$k].Match
            if ($p.Count -eq 1) { $wasUp[$k] = $p[0].ProcessId }
        }
    }
    foreach ($k in $stopOrder) {
        if (-not (Stop-One $k)) {
            # A restart abandons the rest, because it is about to start things
            # again and half a machine on new code beside half a machine on
            # old code is worse than a machine nobody touched. A shutdown is
            # the opposite: what was asked for is that everything is down, so
            # one target that refuses -- two processes matching, which no
            # script may settle by choosing one -- must not leave the other
            # five running. Carry on, and say at the end what is still up --
            # which is read back from the process table rather than counted
            # here, so a target that would not die is in that list too.
            if (-not $Shutdown) { Write-Host ""; Write-Host "Stopped early. Nothing restarted."; exit 1 }
        }
    }
    # The daemon drives a headless Chrome through chromedriver, and a force-kill
    # runs no exit path at all, so both survive it holding the profile
    # (F:\Chrome_Profiles\SCAIL_mal) that the next one needs. The next daemon start does reap
    # them itself -- it finds the lock file's owner gone and calls the reaper -- but
    # only if that start happens, so reap here too: a stop that is never followed
    # by a start should leave nothing of his browser behind.
    if ($targets -contains "mal") {
        & python tools/mal_history.py reap 2>&1 | ForEach-Object { Write-Host "  $_" }
    }

    # A launcher can only be edited while nothing is reading it, which is now.
    foreach ($k in $stopOrder) { Swap-Staged $k }
}

if ($Shutdown) {
    # The processes are down, so each save's own writer is gone and the marker
    # can be written without a second writer on an open database. The tool
    # checks that for itself, per character, from the lock file beside her
    # save, and refuses for anyone whose process is somehow still up.
    Write-Host ""
    Write-Host "Writing the record of the stop into every character's save:"
    $marked = & python tools/shutdown_mark.py --kind $Kind --why $Why 2>&1
    $markBad = $LASTEXITCODE
    $marked | ForEach-Object { Write-Host "  $_" }
    $markedKeys = @($marked | ForEach-Object {
        if ($_ -match '\(([a-z0-9_]+)\): (marked stopped|already marked)') { $matches[1] } })

    # The machine's own record of the stop, beside the per-character one. A
    # character's save says what happened to HER; this says what happened to
    # the machine, and it is the only place a stop of the mirror daemon is
    # written down at all.
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $stoppedText = if ($wasUp.Count) {
        (($stopOrder | Where-Object { $wasUp.ContainsKey($_) } | ForEach-Object { "$_ $($wasUp[$_])" }) -join ", ")
    } else { "nothing was running" }
    $stillUp = @($ORDER | Where-Object { (Find-One $KNOWN[$_].Match).Count })
    $line = "{0}  kind={1}  why={2}  stopped: {3}  still up: {4}  marked: {5}" -f `
        $stamp, $Kind, ('"' + $Why + '"'), $stoppedText,
        $(if ($stillUp.Count) { $stillUp -join ", " } else { "none" }),
        $(if ($markedKeys.Count) { $markedKeys -join ", " } else { "nobody" })
    $log = Join-Path (Get-Location) "logs\shutdowns.log"
    New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null
    Add-Content -Path $log -Value $line -Encoding UTF8
    Write-Host ""
    Write-Host "logs/shutdowns.log: $line"

    Write-Host ""
    Write-Host "Now running:"
    Show-Running
    if ($stillUp.Count) {
        Write-Host "STILL UP: $($stillUp -join ', '). Everything else is down."
        Write-Host "Each of these matched more than one process, or would not die, so this script would not choose for you. Look at them and stop them by hand."
    } else {
        Write-Host "Everything is down. Nothing will be written for anybody -- no schedule, no scenes, no messages, no compile -- until startall.cmd brings it back."
    }
    if ($markBad) {
        Write-Host "Some characters were NOT marked (see the lines above). Whoever was missed will come back with no account of the gap."
    }
    Write-Host "The record of the stop: logs/shutdowns.log for the machine, and one row per character in her own save, which she reads at her next boot and turns into a single temporal-gap event."
    exit ($stillUp.Count + $markBad)
}

if ($StopOnly) {
    Write-Host ""
    Write-Host "Stopped and not started (-StopOnly). Bring it back with restart.cmd <key>."
    Show-Running
    exit 0
}

function Ensure-EmbedServer {
    # The one shared embedding service (tools/embed_server.py, 127.0.0.1:18320)
    # that every character's embed.url points at. Hidden (pythonw has no
    # console, WindowStyle Hidden), never detached, and only when nothing is
    # listening already, so a restart never replaces a warm model.
    $up = @(Get-NetTCPConnection -State Listen -LocalPort 18320 -ErrorAction SilentlyContinue)
    if ($up.Count) { Write-Host "  embed server already listening on 18320"; return }
    $pyw = "C:\Python314\pythonw.exe"
    if (-not (Test-Path $pyw)) { Write-Host "  embed server NOT started: $pyw missing"; return }
    Start-Process -FilePath $pyw -ArgumentList "tools\embed_server.py", "18320" -WindowStyle Hidden -WorkingDirectory (Get-Location).Path
    Write-Host "  embed server started on 18320 (model loads on the first call)"
}

Write-Host ""
Write-Host "Starting:"
if (($targets -contains "momoka") -or ($targets.Count -gt 1)) { Ensure-EmbedServer }
$bad = 0
foreach ($k in ($ORDER | Where-Object { $targets -contains $_ })) {
    $started = if ($StartOnly) { Start-IfDown $k } else { Start-One $k }
    if (-not $started) { $bad++ }
}

Write-Host ""
Write-Host "Now running:"
Show-Running
Write-Host "Newest run directories:"
Get-ChildItem logs -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 3 |
    ForEach-Object {
        $log = Join-Path $_.FullName "session.log"
        $errs = if (Test-Path $log) { @(Select-String -Path $log -Pattern "Traceback|\[error\]" -ErrorAction SilentlyContinue).Count } else { "-" }
        "  logs/{0}   {1} error line(s)" -f $_.Name, $errs | Write-Host
    }
exit $bad
