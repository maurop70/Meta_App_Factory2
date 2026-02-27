$TargetFile = "$PSScriptRoot\start_alpha.py"
try {
    $DesktopPath = [Environment]::GetFolderPath("Desktop")
    if (-not (Test-Path $DesktopPath)) {
        # Fallback for OneDrive users
        $DesktopPath = "$env:USERPROFILE\OneDrive\Desktop"
    }
}
catch {
    $DesktopPath = "$env:USERPROFILE\Desktop"
}

$ShortcutFile = "$DesktopPath\Alpha Architect.lnk"
$WScriptShell = New-Object -ComObject WScript.Shell
$Shortcut = $WScriptShell.CreateShortcut($ShortcutFile)
$Shortcut.TargetPath = "python.exe"
$Shortcut.Arguments = """$TargetFile"""
$Shortcut.WorkingDirectory = "$PSScriptRoot"
$Shortcut.IconLocation = "python.exe,0"
$Shortcut.Description = "Launch Alpha Architect Agent"
$Shortcut.Save()
Write-Host "Shortcut created at $ShortcutFile"
