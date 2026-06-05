$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [Environment]::GetFolderPath('Desktop')
$ShortcutPath = "$DesktopPath\Meta App Factory.lnk"

# Auto-detect Base Path
$PossiblePaths = @(
    "C:\Dev\Antigravity_AI_Agents\Meta_App_Factory",
    "$env:USERPROFILE\My Drive (maurotgs@gmail.com)\Antigravity-AI Agents\Meta_App_Factory",
    "$env:USERPROFILE\My Drive\Antigravity-AI Agents\Meta_App_Factory",
    "$env:USERPROFILE\Google Drive\Antigravity-AI Agents\Meta_App_Factory",
    "G:\My Drive\Antigravity-AI Agents\Meta_App_Factory",
    "H:\My Drive\Antigravity-AI Agents\Meta_App_Factory"
)

$BaseDir = ""
foreach ($Path in $PossiblePaths) {
    if (Test-Path $Path) {
        $BaseDir = $Path
        break
    }
}

if ($BaseDir -eq "") {
    Write-Error "Meta App Factory directory not found."
    exit 1
}

$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "$BaseDir\Launch_ClaudeAY.bat"
$Shortcut.WorkingDirectory = "$BaseDir"
$Shortcut.IconLocation = "$BaseDir\claudeay_icon.ico"
$Shortcut.Save()

Write-Host "CLEANUP: Redirected 'Meta App Factory' shortcut to Launch_ClaudeAY.bat."
Write-Host "Target: $BaseDir\Launch_ClaudeAY.bat"

