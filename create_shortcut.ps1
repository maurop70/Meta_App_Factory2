$WshShell = New-Object -ComObject WScript.Shell
$ShortcutPath = "$([Environment]::GetFolderPath('Desktop'))\Meta App Factory.lnk"
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "C:\Users\mpetr\My Drive\Antigravity-AI Agents\Meta_App_Factory\Launch_Meta_Factory.bat"
$Shortcut.WorkingDirectory = "C:\Users\mpetr\My Drive\Antigravity-AI Agents\Meta_App_Factory"
# Note: Windows .lnk files usually require .ico for the IconLocation to show up reliably.
$Shortcut.IconLocation = "C:\Users\mpetr\My Drive\Antigravity-AI Agents\Meta_App_Factory\factory_icon.ico"
$Shortcut.Save()
Write-Host "Shortcut created on Desktop with icon path set."
