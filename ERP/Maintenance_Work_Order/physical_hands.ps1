Add-Type -AssemblyName System.Windows.Forms

# Bring the window to front or launch it
Start-Process "http://localhost:8080/login"
Start-Sleep -Seconds 4

# Send the ID
[System.Windows.Forms.SendKeys]::SendWait("ERP-1000")
Start-Sleep -Milliseconds 500

# Tab to PIN field
[System.Windows.Forms.SendKeys]::SendWait("{TAB}")
Start-Sleep -Milliseconds 500

# Send the PIN
[System.Windows.Forms.SendKeys]::SendWait("1234")
Start-Sleep -Milliseconds 500

# Submit
[System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
