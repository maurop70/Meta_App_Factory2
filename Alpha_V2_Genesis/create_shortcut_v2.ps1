
# Reliable Shortcut Creator for Alpha Architect

try {
    # Dynamically resolve paths
    $ScriptDir = $PSScriptRoot
    $TargetBatch = Join-Path $ScriptDir "launch_alpha_suite.bat"
    
    # Verify target exists
    if (-not (Test-Path $TargetBatch)) {
        Write-Error "Target batch file not found: $TargetBatch"
        exit 1
    }

    # Determine Desktop Path
    $DesktopPath = [Environment]::GetFolderPath("Desktop")
    # Check if OneDrive desktop is active (common in enterprise/modern Windows)
    $OneDriveDesktop = Join-Path $env:USERPROFILE "OneDrive\Desktop"
    if (Test-Path $OneDriveDesktop) {
        $DesktopPath = $OneDriveDesktop
    }

    $ShortcutFile = Join-Path $DesktopPath "Alpha Architect.lnk"
    
    # Create Shortcut
    $WScriptShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WScriptShell.CreateShortcut($ShortcutFile)
    $Shortcut.TargetPath = $TargetBatch
    $Shortcut.WorkingDirectory = $ScriptDir
    $Shortcut.WindowStyle = 1 # Normal window
    $Shortcut.Description = "Launch Alpha Architect (Antigravity)"
    
    # Use a generic system icon (graph/chart style) from shell32.dll
    # Icon index 44 in shell32.dll is often a star or favorites icon, 
    # Index 165 is often a chart/graph icon in newer Windows versions, or we fallback to cmd.exe
    $Shortcut.IconLocation = "shell32.dll,165" 
    
    $Shortcut.Save()
    Write-Host "Success: Shortcut created at '$ShortcutFile'"
    Write-Host "Target: '$TargetBatch'"
}
catch {
    Write-Error "Failed to create shortcut: $_"
    exit 1
}
