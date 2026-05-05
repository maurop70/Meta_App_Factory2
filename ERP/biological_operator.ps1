Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

function Take-Screenshot($Filename) {
    $Screen = [System.Windows.Forms.SystemInformation]::VirtualScreen
    $Bitmap = New-Object System.Drawing.Bitmap $Screen.Width, $Screen.Height
    $Graphics = [System.Drawing.Graphics]::FromImage($Bitmap)
    $Graphics.CopyFromScreen($Screen.Left, $Screen.Top, 0, 0, $Bitmap.Size)
    $Bitmap.Save($Filename)
}

Start-Process "chrome.exe" "-incognito http://localhost:5175/login"
Start-Sleep -Seconds 5

[System.Windows.Forms.SendKeys]::SendWait("ERP-3000")
Start-Sleep -Milliseconds 500
[System.Windows.Forms.SendKeys]::SendWait("{TAB}")
Start-Sleep -Milliseconds 500
[System.Windows.Forms.SendKeys]::SendWait("3456")
Start-Sleep -Milliseconds 500
[System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
Start-Sleep -Seconds 3

[System.Windows.Forms.SendKeys]::SendWait("{TAB}")
Start-Sleep -Milliseconds 500
[System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
Start-Sleep -Seconds 2

[System.Windows.Forms.SendKeys]::SendWait("{TAB}")
Start-Sleep -Milliseconds 500
[System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
Start-Sleep -Seconds 2

[System.Windows.Forms.SendKeys]::SendWait("{TAB}")
Start-Sleep -Milliseconds 200
[System.Windows.Forms.SendKeys]::SendWait("{TAB}")
Start-Sleep -Milliseconds 200
[System.Windows.Forms.SendKeys]::SendWait("{TAB}")
Start-Sleep -Milliseconds 200
[System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
Start-Sleep -Seconds 1

[System.Windows.Forms.SendKeys]::SendWait("{TAB}")
Start-Sleep -Milliseconds 200
[System.Windows.Forms.SendKeys]::SendWait("{TAB}")
Start-Sleep -Milliseconds 200
[System.Windows.Forms.SendKeys]::SendWait("{TAB}")
Start-Sleep -Milliseconds 200
[System.Windows.Forms.SendKeys]::SendWait("Biological operator validation.")
Start-Sleep -Milliseconds 500

[System.Windows.Forms.SendKeys]::SendWait("{F12}")
Start-Sleep -Seconds 2
[System.Windows.Forms.SendKeys]::SendWait("^+P")
Start-Sleep -Milliseconds 500
[System.Windows.Forms.SendKeys]::SendWait("Go offline")
Start-Sleep -Milliseconds 500
[System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
Start-Sleep -Seconds 1
[System.Windows.Forms.SendKeys]::SendWait("{F12}")
Start-Sleep -Seconds 1

[System.Windows.Forms.SendKeys]::SendWait("{TAB}")
Start-Sleep -Milliseconds 200
[System.Windows.Forms.SendKeys]::SendWait("{TAB}")
Start-Sleep -Milliseconds 200
[System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
Start-Sleep -Seconds 2

Take-Screenshot("C:\Users\mpetr\.gemini\antigravity\brain\45ca18f7-c824-42c9-a5b5-601dab828135\artifacts\biological_telemetry.png")

[System.Windows.Forms.SendKeys]::SendWait("{F12}")
Start-Sleep -Seconds 2
[System.Windows.Forms.SendKeys]::SendWait("^+P")
Start-Sleep -Milliseconds 500
[System.Windows.Forms.SendKeys]::SendWait("Go online")
Start-Sleep -Milliseconds 500
[System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
Start-Sleep -Seconds 1
[System.Windows.Forms.SendKeys]::SendWait("{F12}")
