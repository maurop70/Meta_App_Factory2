@echo off
title ALPHA V2 GENESIS — ANTIGRAVITY TRADING SYSTEM
color 0A

echo.
echo  ============================================================
echo       ALPHA V2 GENESIS ^| ANTIGRAVITY TRADING SYSTEM
echo       Lead Quant Architect ^| Strategy Ledger v2.2
echo  ============================================================
echo.

:: ── Portable Environment Bootstrap ──────────────────────────
:: Auto-detects Python, sets ALPHA_RUNTIME_DIR, creates .env if needed
call "%~dp0..\bootstrap_env.bat"
if %ERRORLEVEL% NEQ 0 exit /b 1


:: 1. Force-kill existing processes for a clean start
echo.
taskkill /f /im ngrok.exe 2>nul

:: Kill the Vite dev server specifically (port 5175) not all node processes
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5175" 2^>nul') do taskkill /f /PID %%a 2>nul
timeout /t 2 /nobreak >nul

:: Set Project Root (handles paths with spaces via %~dp0)
cd /d "%~dp0"
set "PYTHONPATH=%~dp0"

:: 2. Start Flask Backend + ngrok + Loki Engine
echo  [1/4] Starting Alpha Backend (Flask + ngrok + Loki)...
start "Alpha Server" /min "%PYTHON%" "%~dp0server.py"
echo        Server starting in background...

echo  [2/4] Waiting for server stabilization (ngrok tunnel + warm-up)...
timeout /t 12 /nobreak >nul

:: 3. Infrastructure Supervisor (Portfolio Watchdog + Daily Ledger Cron)
echo  [3/4] Launching Infrastructure Supervisor (Ledger Watchdog)...
start "Infrastructure Supervisor" /min "%PYTHON%" "%~dp0infrastructure_supervisor.py"
timeout /t 2 /nobreak >nul

:: 4. React UI (Vite)
echo  [4/4] Launching Alpha UI (Vite Dev Server)...
cd /d "%~dp0alpha_ui"
start "" http://localhost:5175

:: Use .cmd shim directly to avoid ExecutionPolicy block
"%~dp0alpha_ui\node_modules\.bin\vite.cmd" --host --port 5175

echo.
echo  ============================================================
echo       SESSION ENDED. Restart script to resume.
echo  ============================================================
pause
