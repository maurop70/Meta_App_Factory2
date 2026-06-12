# register_selfcheck_task.ps1 - Registers ClaudeAY nightly self-check and
# weekly digest in Windows Task Scheduler.
# Nightly at 03:00 (after the 02:00 backup so freshness check sees tonight's
# mirror). Digest Sundays at 08:00. Interactive user context (consistent
# with Antigravity_Dev_Backup).
$bridge = "C:\Dev\Antigravity_AI_Agents\Meta_App_Factory\claude-mcp-bridge"

if (-not (Test-Path "$bridge\self_check.py")) {
    Write-Error "self_check.py not found under $bridge - aborting."
    exit 1
}

$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

$nightlyAction = New-ScheduledTaskAction -Execute "PowerShell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -Command `"Set-Location '$bridge'; python self_check.py nightly`""
$nightlyTrigger = New-ScheduledTaskTrigger -Daily -At "03:00"
Register-ScheduledTask -TaskName "ClaudeAY_Nightly_SelfCheck" -Action $nightlyAction `
    -Trigger $nightlyTrigger -Settings $settings `
    -Description "ClaudeAY nightly self-check: contract suites, prod health, backup freshness" -Force

$digestAction = New-ScheduledTaskAction -Execute "PowerShell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -Command `"Set-Location '$bridge'; python self_check.py digest`""
$digestTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At "08:00"
Register-ScheduledTask -TaskName "ClaudeAY_Weekly_Digest" -Action $digestAction `
    -Trigger $digestTrigger -Settings $settings `
    -Description "ClaudeAY weekly digest of loop runs, autonomy events, audits, deploys" -Force

Write-Host "Self-check tasks registered."
