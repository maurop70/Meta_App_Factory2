$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [Environment]::GetFolderPath('Desktop')
$ShortcutPath = "$DesktopPath\Meta App Factory.lnk"

# Auto-detect Google Drive Root
$PossibleRoots = @(
    "$env:USERPROFILE\My Drive (maurotgs@gmail.com)",
    "$env:USERPROFILE\My Drive",
    "$env:USERPROFILE\Google Drive",
    "G:\My Drive",
    "H:\My Drive"
)

$BaseDir = ""
foreach ($Root in $PossibleRoots) {
    $TestDir = "$Root\Antigravity-AI Agents\Meta_App_Factory"
    if (Test-Path $TestDir) {
        $BaseDir = $TestDir
        break
    }
}

if ($BaseDir -eq "") {
    Write-Error "Meta App Factory directory not found in Google Drive roots."
    exit 1
}

$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "$BaseDir\Launch_Meta_App_Factory_V3.bat"
$Shortcut.WorkingDirectory = "$BaseDir"
$Shortcut.IconLocation = "$BaseDir\factory_icon.ico"
$Shortcut.Save()

Write-Host "CLEANUP: Redirected 'Meta App Factory' shortcut to V3 WEB UI."
Write-Host "Target: $BaseDir\Launch_Meta_App_Factory_V3.bat"

