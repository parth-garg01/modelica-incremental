# Keeps the overnight journal-upgrade run going across internet drops and
# usage-limit exhaustion.
#
# Every 15 minutes:
#   offline                              -> wait
#   online, work active                  -> leave it alone
#   online, idle for 30+ minutes         -> resume the most recent session in this repo
#   resume reports a usage/rate limit    -> sleep until the next 02:00 (limit reset), then resume
#
# "Active" = an experiment script (src\journal_*.py) is running, or any file under
# logs/, results/, docs/journal_upgrade/, src/, or git HEAD changed in the last 30
# minutes. Process checks alone do not work: the VS Code extension keeps Claude
# processes alive even when the session is stalled.
#
# Usage (repo root):  pwsh scripts\watchdog.ps1          # loop
#                     pwsh scripts\watchdog.ps1 -Once    # single check (used by the 02:00 scheduled task)
param([switch]$Once, [int]$IntervalMinutes = 15, [int]$IdleMinutes = 30, [string]$ResetTime = "02:00")

$repo = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $repo "logs"
New-Item -ItemType Directory -Force $logDir | Out-Null
$log = Join-Path $logDir "watchdog.log"
$prompt = "Resume the overnight journal-upgrade run. Read docs/journal_upgrade/STATUS.md first, check git log and the experiment logs in logs/, then continue from the next unfinished step without redoing completed work. Standing rules are in STATUS.md."

function Log($msg) { "$(Get-Date -Format o) $msg" | Tee-Object -FilePath $log -Append | Out-Host }

function Test-Online {
    try { Invoke-WebRequest -Uri "https://api.anthropic.com" -Method Head -TimeoutSec 10 -UseBasicParsing | Out-Null; $true }
    catch { [bool]$_.Exception.Response }  # any HTTP response, even 404, means the network is up
}

function Test-Active {
    $experiment = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'src[\\/]journal_\w+\.py' }
    if ($experiment) { return $true }
    $cutoff = (Get-Date).AddMinutes(-$IdleMinutes)
    $paths = "logs", "results", "docs\journal_upgrade", "src", ".git\logs\HEAD" | ForEach-Object { Join-Path $repo $_ }
    $recent = Get-ChildItem $paths -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -gt $cutoff -and $_.Name -ne "watchdog.log" -and $_.Name -notlike "resume_*.log" } |
        Select-Object -First 1
    return [bool]$recent
}

function Get-NextReset {
    $t = [datetime]::ParseExact($ResetTime, "HH:mm", $null)
    $next = (Get-Date).Date.AddHours($t.Hour).AddMinutes($t.Minute)
    if ($next -le (Get-Date)) { $next = $next.AddDays(1) }
    $next
}

function Invoke-Resume {
    $out = Join-Path $logDir "resume_$(Get-Date -Format yyyyMMdd_HHmmss).log"
    Log "resuming session (output: $out)"
    Push-Location $repo
    try { & claude --continue -p $prompt --permission-mode auto *> $out } finally { Pop-Location }
    $text = Get-Content $out -Raw -ErrorAction SilentlyContinue
    if ($text -match '(?i)usage limit|rate limit|limit reached|hit your limit|credit') {
        $next = Get-NextReset
        Log "usage limit detected, sleeping until $next"
        if (-not $Once) { Start-Sleep -Seconds ([int]($next - (Get-Date)).TotalSeconds); Invoke-Resume }
    } else {
        Log "resumed session exited (code $LASTEXITCODE)"
    }
}

function Invoke-Check {
    if (-not (Test-Online)) { Log "offline, waiting"; return }
    if (Test-Active) { Log "online, work active, leaving it alone"; return }
    Invoke-Resume
}

Log "watchdog started (once=$Once, interval ${IntervalMinutes}m, idle ${IdleMinutes}m, reset $ResetTime)"
if ($Once) { Invoke-Check; exit }
while ($true) { Invoke-Check; Start-Sleep -Seconds ($IntervalMinutes * 60) }
