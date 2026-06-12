# register_backup_task.ps1 - Registers backup_dev.ps1 in Windows Task Scheduler.
# Runs as the interactive user on purpose: Google Drive for Desktop only syncs
# inside the logged-on user's session, so SYSTEM/S4U contexts would write to a
# dead mount. If the user is logged out at 2:00 AM, -StartWhenAvailable fires
# the backup at next logon instead.
$taskName = "Antigravity_Dev_Backup"
$scriptPath = "C:\Dev\Antigravity_AI_Agents\Meta_App_Factory\backup_dev.ps1"

if (-not (Test-Path $scriptPath)) {
    Write-Error "Backup script not found at $scriptPath - aborting registration."
    exit 1
}

Write-Host "Registering daily scheduled task '$taskName'..."
$action = New-ScheduledTaskAction -Execute "PowerShell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$scriptPath`""
$trigger = New-ScheduledTaskTrigger -Daily -At "02:00"
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description "Daily incremental backup of C:\Dev to Google Drive" -Force
Write-Host "Task registered successfully."
