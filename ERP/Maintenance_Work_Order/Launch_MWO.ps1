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

# Start the Gateway Core (Module 0)
Start-Process -FilePath "python" -ArgumentList "gateway_server.py" -WorkingDirectory $gatewayPath -WindowStyle Minimized

# Start the backend (FastAPI)
Start-Process -FilePath "python" -ArgumentList "-m uvicorn maintenance_backend:app --reload --port 8000" -WorkingDirectory $backendPath -WindowStyle Minimized

# Start the frontend (Vite)
Start-Process -FilePath "npm.cmd" -ArgumentList "run dev" -WorkingDirectory $frontendPath -WindowStyle Minimized

# Give it a couple of seconds to start up, then open the browser
Start-Sleep -Seconds 3
Start-Process "http://localhost:5175"
