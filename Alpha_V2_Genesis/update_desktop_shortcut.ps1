$path = "$env:USERPROFILE\OneDrive - Gelato Petrini\Desktop\Alpha Architect (Antigravity).lnk"
$shell = New-Object -COM WScript.Shell
$shortcut = $shell.CreateShortcut($path)
$shortcut.TargetPath = "C:\Users\mpetr\My Drive (maurotgs@gmail.com)\Antigravity-AI Agents\Alpha_Architect\launch_alpha_suite.bat"
$shortcut.WorkingDirectory = "C:\Users\mpetr\My Drive (maurotgs@gmail.com)\Antigravity-AI Agents\Alpha_Architect"
$shortcut.Description = "Launch Alpha Architect (Antigravity)"
$shortcut.Save()
Write-Host "Shortcut updated: $path"
