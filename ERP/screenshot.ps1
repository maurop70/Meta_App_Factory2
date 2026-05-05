Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$Screen = [System.Windows.Forms.SystemInformation]::VirtualScreen
$Bitmap = New-Object System.Drawing.Bitmap $Screen.Width, $Screen.Height
$Graphics = [System.Drawing.Graphics]::FromImage($Bitmap)
$Graphics.CopyFromScreen($Screen.Left, $Screen.Top, 0, 0, $Bitmap.Size)
$Bitmap.Save("C:\Users\mpetr\.gemini\antigravity\brain\66398479-cfb8-43b0-ad6b-ae577c7ded64\artifacts\desktop_telemetry.png")
