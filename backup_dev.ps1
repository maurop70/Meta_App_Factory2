# backup_dev.ps1 - Incremental mirror of C:\Dev to Google Drive.
# Excludes dependency/cache directories (node_modules, venvs, .git, builds).
# /MIR mirrors deletions into the backup; recovery net is Google Drive trash (30 days).
# NOTE: SQLite DBs copied while services run may be torn copies; authoritative
# recovery for code is GitHub, for the ERP DB the archives/ snapshots.
# This script NEVER throws and always exits 0, so callers (Launch_MWO.ps1) are never blocked.

$source      = "C:\Dev"
# Path updated 2026-06-12: the backups folder was relocated to Drive root
# (old location "My Drive\Antigravity-AI Agents\backups" was emptied in the
# move). Guard 1 now checks the Drive mount root itself.
$driveRoot   = "C:\Users\mpetr\My Drive"
$destination = Join-Path $driveRoot "backups\Dev"
$excludeDirs = @("node_modules", ".venv", "venv", "env", "__pycache__", ".git", ".pytest_cache", "dist", "build")

# Guard 1: Google Drive must be mounted, otherwise we would silently create an
# orphan local folder that never syncs.
if (-not (Test-Path $driveRoot)) {
    Write-Warning "Google Drive not mounted ($driveRoot missing). Backup SKIPPED."
    exit 0
}

# Guard 2: source sanity. If C:\Dev is missing or hollowed out, /MIR would purge
# the backup to match (the classic mirror disaster). Skip instead.
if (-not (Test-Path (Join-Path $source "Antigravity_AI_Agents"))) {
    Write-Warning "Source sanity check failed ($source\Antigravity_AI_Agents missing). Backup SKIPPED."
    exit 0
}

Write-Host "Starting incremental backup: $source -> $destination"
$sw = [System.Diagnostics.Stopwatch]::StartNew()
robocopy $source $destination /MIR /XD $excludeDirs /R:2 /W:5 /NDL /NFL /NJH /NJS
$code = $LASTEXITCODE
$sw.Stop()
$secs = [int]$sw.Elapsed.TotalSeconds

# Robocopy exit codes: 0 = no changes, 1-7 = copied/synchronized OK, >=8 = real failure.
if ($code -ge 8) {
    Write-Warning "Backup FAILED (robocopy exit code $code) after ${secs}s. Check Drive quota/permissions."
} elseif ($code -eq 0) {
    Write-Host "Backup OK: no changes detected (${secs}s)."
} else {
    Write-Host "Backup OK: changes synchronized (robocopy code $code, ${secs}s)."
}
exit 0
