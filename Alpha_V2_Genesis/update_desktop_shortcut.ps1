$desktop = [Environment]::GetFolderPath('Desktop')
$path = Join-Path $desktop "Alpha V2 Genesis.lnk"
$target = "C:\Users\mpetr\My Drive (maurotgs@gmail.com)\Antigravity-AI Agents\Meta_App_Factory\Alpha_V2_Genesis\launch_alpha_suite.bat"
$workdir = "C:\Users\mpetr\My Drive (maurotgs@gmail.com)\Antigravity-AI Agents\Meta_App_Factory\Alpha_V2_Genesis"
# Use the true ICO file we just created
$iconPath = "C:\Users\mpetr\My Drive (maurotgs@gmail.com)\Antigravity-AI Agents\Meta_App_Factory\Alpha_V2_Genesis\alpha_v2_genesis_true.ico"

# If previous shortcut exists, remove it to force refresh
if (Test-Path $path) { Remove-Item $path }

$shell = New-Object -COM WScript.Shell
$shortcut = $shell.CreateShortcut($path)
$shortcut.TargetPath = $target
$shortcut.WorkingDirectory = $workdir
$shortcut.IconLocation = "$iconPath,0"
$shortcut.Description = "Launch Alpha V2 Genesis Trading System"
$shortcut.Save()

# Force Explorer to refresh icons
$code = @"
    [DllImport("shell32.dll", EntryPoint = "SHChangeNotify")]
    public static extern void SHChangeNotify(long wEventId, uint uFlags, IntPtr dwItem1, IntPtr dwItem2);
"@
Add-Type -MemberDefinition $code -Namespace Shell32 -Name NativeMethods
[Shell32.NativeMethods]::SHChangeNotify(0x08000000, 0x0000, [IntPtr]::Zero, [IntPtr]::Zero)

Write-Host "✅ Shortcut Re-Created on Desktop: $path"
Write-Host "✅ Target: $target"
Write-Host "✅ Icon Path: $iconPath"
Write-Host "✅ Shell Notification Sent to refresh icons"
