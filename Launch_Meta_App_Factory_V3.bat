@echo off
title Meta App Factory V3
color 0B
echo.
echo  ===================================================
echo    META APP FACTORY V3 - Launching...
echo  ===================================================
echo.

:: ── Auto-Detect Google Drive Path (Non-blocking GOTO) ──────
set "GDRIVE="
if exist "%USERPROFILE%\My Drive (maurotgs@gmail.com)\Antigravity-AI Agents\Meta_App_Factory" (
    set "GDRIVE=%USERPROFILE%\My Drive (maurotgs@gmail.com)"
    goto :GDRIVE_FOUND
)
if exist "%USERPROFILE%\My Drive\Antigravity-AI Agents\Meta_App_Factory" (
    set "GDRIVE=%USERPROFILE%\My Drive"
    goto :GDRIVE_FOUND
)
if exist "%USERPROFILE%\Google Drive\Antigravity-AI Agents\Meta_App_Factory" (
    set "GDRIVE=%USERPROFILE%\Google Drive"
    goto :GDRIVE_FOUND
)
for %%d in (G H I D E F) do (
    if exist "%%d:\My Drive (maurotgs@gmail.com)\Antigravity-AI Agents\Meta_App_Factory" (
        set "GDRIVE=%%d:\My Drive (maurotgs@gmail.com)"
        goto :GDRIVE_FOUND
    )
    if exist "%%d:\My Drive\Antigravity-AI Agents\Meta_App_Factory" (
        set "GDRIVE=%%d:\My Drive"
        goto :GDRIVE_FOUND
    )
)

echo  [FATAL] Google Drive not found! Make sure Google Drive is installed
echo          and the Antigravity-AI Agents folder is synced.
pause
exit /b 1

:GDRIVE_FOUND
set "FACTORY_DIR=%GDRIVE%\Antigravity-AI Agents\Meta_App_Factory"
echo  [OK] Google Drive: %GDRIVE%
echo  [OK] Factory Dir:  %FACTORY_DIR%
echo.

cd /d "%FACTORY_DIR%"

:: ── Step 0: Cleanup Stale Processes ────────────────────────
echo  [0/3] Clearing Port 5173 (Alpha/Vite) for a clean start...
taskkill /f /im python.exe /t 2>nul
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173" 2^>nul') do taskkill /f /PID %%a 2>nul
timeout /t 2 /nobreak >nul

:: ── Bootstrap Environment (Python, Node, .env) ────────────
if exist bootstrap_env.bat (
    call bootstrap_env.bat
) else (
    echo  [WARN] bootstrap_env.bat not found, using system Python
    set "PYTHON=python"
)

:: ── Start Backend (api.py on port 5000) ───────────────────
echo  [1/3] Starting Backend on port 5000...
start "Meta Factory Backend" /min "%PYTHON%" api.py

:: ── Gateway Stabilization Delay ──────────────────────────
echo  [1.2/3] Waiting for API Gateway to stabilize...
timeout /t 5 /nobreak >nul

:: ── Set PYTHONPATH for shared_modules resolution ─────────
set "PYTHONPATH=%CD%;%CD%\shared_modules;%PYTHONPATH%"

:: ── Auto-Start Resonance (Aether-Native) ────────────────────
echo  [1.5/3] Starting Resonance (Backend & UI)...
start "Resonance Backend" /min cmd /c "cd Resonance && \"%PYTHON%\" server.py"
start "Resonance Frontend" /min cmd /c "cd Resonance\resonance_ui && npm.cmd run dev -- --host --port 5174"

:: ── Auto-Start Neural Network Clusters ──────────────────────
echo  [1.6/3] Starting C-Suite and Elite Nodes...
start "C-Suite Cluster" /min cmd /c "cd CFO_Agent && \"%PYTHON%\" server.py"
start "Phantom QA Elite" /min cmd /c "cd Phantom_QA_Elite && Launch_Phantom_QA.bat"
start "Master Architect Elite" /min cmd /c "cd Master_Architect_Elite_Logic && Launch_Master_Architect.bat"
start "CLO Legal Dept" /min cmd /c "cd apps\CLO_Agent && \"%PYTHON%\" legal_engine.py"

:: ── Start Autonomous Service Exposure (Ngrok Zero-Trust) ──
echo  [1.7/3] Exposing CFO Auditor's Desk via Ngrok (Zero-Trust)...
start "Ngrok Zero-Trust Tunnel" /min "%PYTHON%" skills\expose_localhost.py

:: ── Start n8n Credential Watchdog (V3 Active Self-Repair) ──
echo  [1.8/3] Starting Aether Watchdog Daemon...
start "V3 Watchdog Daemon" /min "%PYTHON%" n8n_watchdog.py --daemon

:: ── Start Frontend UI (Auto-detect port 5173 vs 5174) ────
echo  [2/3] Starting Factory UI...
cd factory_ui
if not exist node_modules npm.cmd install
set PORT=5173
netstat -ano | findstr ":5173 " >nul
if %errorlevel% equ 0 (
    echo  [WARN] Port 5173 is in use - likely Alpha_V2. Auto-healing to port 5174...
    set PORT=5174
)
start "Meta Factory UI" /min cmd /k "npm.cmd run dev -- --host --port %PORT%"
cd ..

:: ── Open Browser ──────────────────────────────────────────
echo  [3/3] Opening browser...
ping 127.0.0.1 -n 4 >nul
start http://localhost:%PORT%

echo.
echo  ===================================================
echo    Meta App Factory is running!
echo    Backend:  http://localhost:5000
echo    Frontend: http://localhost:5173
echo    Machine:  %COMPUTERNAME%
echo    Press any key to SHUTDOWN...
echo  ===================================================
pause >nul

:: ── CLEANUP ───────────────────────────────────────────────
echo  Shutting down...
taskkill /FI "WINDOWTITLE eq Meta Factory Backend" /F 2>nul
taskkill /FI "WINDOWTITLE eq V3 Watchdog Daemon" /F 2>nul
taskkill /FI "WINDOWTITLE eq Meta Factory UI" /F 2>nul
echo  Meta App Factory stopped.
pause
