# ════════════════════════════════════════════════════════
#  Resonance — Portable Desktop Shortcut Creator
#  Auto-detects Google Drive path. Works on any PC.
# ════════════════════════════════════════════════════════

$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [Environment]::GetFolderPath('Desktop')
$ShortcutPath = "$DesktopPath\Resonance.lnk"

# Auto-detect Google Drive Root (cascading search)
$PossibleRoots = @(
    "$env:USERPROFILE\My Drive",
    "$env:USERPROFILE\My Drive (maurotgs@gmail.com)",
    "$env:USERPROFILE\Google Drive",
    "G:\My Drive",
    "H:\My Drive",
    "I:\My Drive",
    "D:\My Drive"
)

$BaseDir = ""
foreach ($Root in $PossibleRoots) {
    $TestDir = "$Root\Antigravity-AI Agents\Meta_App_Factory\Resonance"
    if (Test-Path $TestDir) {
        $BaseDir = $TestDir
        break
    }
}

if ($BaseDir -eq "") {
    Write-Error "Resonance directory not found in any Google Drive root."
    exit 1
}

$BatchPath = "$BaseDir\Launch_Resonance_V3.bat"

# Check for a custom icon, fall back gracefully
$IconPath = ""
if (Test-Path "$env:USERPROFILE\.gemini\resonance_icon.ico") {
    $IconPath = "$env:USERPROFILE\.gemini\resonance_icon.ico"
} elseif (Test-Path "$BaseDir\resonance_icon.ico") {
    $IconPath = "$BaseDir\resonance_icon.ico"
}

$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "C:\Windows\System32\cmd.exe"
$Shortcut.Arguments = "/c `"$BatchPath`""
$Shortcut.WorkingDirectory = $BaseDir
if ($IconPath -ne "") {
    $Shortcut.IconLocation = "$IconPath,0"
}
$Shortcut.Save()

Write-Host "[OK] Resonance shortcut created/updated at: $ShortcutPath"
Write-Host "     Target: $BatchPath"
Write-Host "     Machine: $env:COMPUTERNAME"
