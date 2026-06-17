$ErrorActionPreference = "Stop"

# Auto-Backup C:\Dev to Google Drive before launching (non-fatal: a backup
# problem must never block the application launch)
try {
    & "c:\Dev\Antigravity_AI_Agents\Meta_App_Factory\backup_dev.ps1"
} catch {
    Write-Warning "Dev backup skipped: $_"
}

$gatewayPath = "c:\Dev\Antigravity_AI_Agents\Meta_App_Factory\ERP\Module_0_Gateway"
$backendPath = "c:\Dev\Antigravity_AI_Agents\Meta_App_Factory\ERP\Maintenance_Work_Order"
$frontendPath = "c:\Dev\Antigravity_AI_Agents\Meta_App_Factory\ERP\maintenance_frontend"

# 1. Start the Gateway Core (Module 0)
Write-Host "[*] Launching Module 0 Gateway (Port 9000)..." -ForegroundColor Cyan
Start-Process -FilePath "python" -ArgumentList "gateway_server.py" -WorkingDirectory $gatewayPath -WindowStyle Minimized

# Poll until Gateway is responsive
$gatewayReady = $false
for ($i = 1; $i -le 15; $i++) {
    try {
        $socket = New-Object System.Net.Sockets.TcpClient("127.0.0.1", 9000)
        if ($socket.Connected) {
            $gatewayReady = $true
            $socket.Close()
            break
        }
    } catch {}
    Start-Sleep -Seconds 1
}

if (-not $gatewayReady) {
    Write-Error "Gateway failed to start on port 9000."
    Exit 1
}
Write-Host "[+] Gateway online." -ForegroundColor Green

# 2. Start the backend (FastAPI)
Write-Host "[*] Launching MWO Backend (Port 8000)..." -ForegroundColor Cyan
Start-Process -FilePath "python" -ArgumentList "-m uvicorn maintenance_backend:app --reload --port 8000" -WorkingDirectory $backendPath -WindowStyle Minimized

# Poll until Backend is responsive
$backendReady = $false
for ($i = 1; $i -le 15; $i++) {
    try {
        $socket = New-Object System.Net.Sockets.TcpClient("127.0.0.1", 8000)
        if ($socket.Connected) {
            $backendReady = $true
            $socket.Close()
            break
        }
    } catch {}
    Start-Sleep -Seconds 1
}

if (-not $backendReady) {
    Write-Error "MWO Backend failed to start on port 8000."
    Exit 1
}
Write-Host "[+] Backend online." -ForegroundColor Green

# 3. Start the frontend (Vite)
Write-Host "[*] Launching Vite Frontend (Port 5175)..." -ForegroundColor Cyan
Start-Process -FilePath "npm.cmd" -ArgumentList "run dev" -WorkingDirectory $frontendPath -WindowStyle Minimized

# Give Vite a moment to initialize
Start-Sleep -Seconds 2
Write-Host "[+] All services successfully orchestrated!" -ForegroundColor Green
Start-Process "http://localhost:5175"

