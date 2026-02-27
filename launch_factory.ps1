# ═══════════════════════════════════════════════════════════
#  META APP FACTORY - MASTER LAUNCHER (V3)
#  Boots FastAPI backend (port 8000) + React frontend (5173)
#  with safe port assassination before launch.
# ═══════════════════════════════════════════════════════════

$ErrorActionPreference = 'SilentlyContinue'
$FactoryRoot = $PSScriptRoot
$FrontendDir = Join-Path $FactoryRoot 'factory_ui'

Write-Host ''
Write-Host '  META APP FACTORY - V3 LAUNCHER' -ForegroundColor Cyan
Write-Host '  --------------------------------' -ForegroundColor DarkCyan
Write-Host ''

# -- STEP 1: Port Assassination (Safe Boot) --
Write-Host '  [1/3] Clearing ports...' -ForegroundColor Yellow

$pids8000 = (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue).OwningProcess | Sort-Object -Unique
foreach ($procId in $pids8000) {
    if ($procId -and $procId -ne 0) {
        $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "    Killing port 8000: $($proc.ProcessName) (PID $procId)" -ForegroundColor DarkYellow
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        }
    }
}

$pids5173 = (Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue).OwningProcess | Sort-Object -Unique
foreach ($procId in $pids5173) {
    if ($procId -and $procId -ne 0) {
        $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "    Killing port 5173: $($proc.ProcessName) (PID $procId)" -ForegroundColor DarkYellow
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        }
    }
}

Write-Host '    Ports 8000 and 5173 clear.' -ForegroundColor Green
Start-Sleep -Milliseconds 500

# -- STEP 2: Launch Backend (FastAPI on port 8000) --
Write-Host '  [2/3] Launching Backend (api.py on :8000)...' -ForegroundColor Yellow

Start-Process cmd -ArgumentList @('/c', "title Factory Backend && cd /d ""$FactoryRoot"" && python api.py && pause")

Write-Host '    Backend server starting.' -ForegroundColor Green
Start-Sleep -Seconds 2

# -- STEP 3: Launch Frontend (Vite/React on port 5173) --
Write-Host '  [3/3] Launching Frontend (npm run dev on :5173)...' -ForegroundColor Yellow

Start-Process cmd -ArgumentList @('/c', "title Factory Frontend && cd /d ""$FrontendDir"" && npm run dev && pause")

Write-Host '    Frontend dev server starting.' -ForegroundColor Green

# -- DONE --
Write-Host ''
Write-Host '  FACTORY ONLINE' -ForegroundColor Green
Write-Host '  ---------------' -ForegroundColor DarkGreen
Write-Host '  Backend:  http://localhost:8000' -ForegroundColor White
Write-Host '  Frontend: http://localhost:5173' -ForegroundColor White
Write-Host ''
Write-Host '  Open http://localhost:5173 in your browser.' -ForegroundColor Cyan
Write-Host ''
