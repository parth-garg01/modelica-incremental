# Registers a Windows Scheduled Task that runs one watchdog check at 02:00 daily
# (when usage limits reset), so the run resumes even if the watchdog loop window
# was closed. Current-user task, no admin needed.
# Remove with:  Unregister-ScheduledTask -TaskName JournalUpgradeResume -Confirm:$false
$repo = Split-Path -Parent $PSScriptRoot
$pwsh = (Get-Command pwsh).Source
$action = New-ScheduledTaskAction -Execute $pwsh -Argument "-NoProfile -File `"$repo\scripts\watchdog.ps1`" -Once" -WorkingDirectory $repo
$trigger = New-ScheduledTaskTrigger -Daily -At "02:00"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 12)
Register-ScheduledTask -TaskName JournalUpgradeResume -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Get-ScheduledTask -TaskName JournalUpgradeResume | Select-Object TaskName, State
