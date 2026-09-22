# Keeps the overnight journal-upgrade session alive across internet drops.
# Every 15 minutes: if online and no Claude Code process is running, resume
# the most recent session in this repo; if one is already running, leave it.
# Usage (from repo root):  pwsh scripts\watchdog.ps1 [-SkipPermissions]
# -SkipPermissions passes --dangerously-skip-permissions so an unattended
# resume never blocks on a permission prompt. Only use it if you accept that.
param([switch]$SkipPermissions, [int]$IntervalMinutes = 15)

$repo = Split-Path -Parent $PSScriptRoot
$log = Join-Path $repo "logs\watchdog.log"
New-Item -ItemType Directory -Force (Split-Path $log) | Out-Null
$prompt = "Resume the overnight journal-upgrade run. Read docs/journal_upgrade/STATUS.md first, check git log and any running/finished experiment logs in logs/, then continue from the next unfinished step without redoing completed work."

function Log($msg) { "$(Get-Date -Format o) $msg" | Tee-Object -FilePath $log -Append }

function Test-Online {
    try { Invoke-WebRequest -Uri "https://api.anthropic.com" -Method Head -TimeoutSec 10 -UseBasicParsing | Out-Null; return $true }
    catch { return [bool]$_.Exception.Response }  # any HTTP response (even 404) means the network is up
}

function Test-ClaudeRunning {
    $procs = Get-CimInstance Win32_Process | Where-Object {
        $_.ProcessId -ne $PID -and $_.CommandLine -match 'claude' -and $_.CommandLine -notmatch 'watchdog\.ps1'
    }
    return [bool]$procs
}

Log "watchdog started (interval ${IntervalMinutes}m, skipPermissions=$SkipPermissions)"
while ($true) {
    if (-not (Test-Online)) {
        Log "offline, waiting"
    } elseif (Test-ClaudeRunning) {
        Log "online, Claude Code already running, leaving it alone"
    } else {
        Log "online and no Claude Code process found, resuming session"
        $claudeArgs = @("--continue", "-p", $prompt)
        if ($SkipPermissions) { $claudeArgs += "--dangerously-skip-permissions" }
        Push-Location $repo
        try { & claude @claudeArgs *>>(Join-Path $repo "logs\resume_$(Get-Date -Format yyyyMMdd_HHmmss).log") }
        finally { Pop-Location }
        Log "resumed session exited (code $LASTEXITCODE)"
    }
    Start-Sleep -Seconds ($IntervalMinutes * 60)
}
