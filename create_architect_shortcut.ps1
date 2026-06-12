$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [Environment]::GetFolderPath('Desktop')
$ShortcutPath = "$DesktopPath\ClaudeAY - Architect Desk.lnk"
$BaseDir = "C:\Dev\Antigravity_AI_Agents\Meta_App_Factory"

if (Test-Path $BaseDir) {
    $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = "$BaseDir\Launch_ClaudeAY.bat"
    $Shortcut.WorkingDirectory = "$BaseDir"
    $Shortcut.IconLocation = "$BaseDir\claudeay_icon.ico"
    $Shortcut.Save()
    Write-Host "SUCCESS: Created desktop shortcut at $ShortcutPath"
} else {
    Write-Error "Meta App Factory directory not found at $BaseDir"
}
