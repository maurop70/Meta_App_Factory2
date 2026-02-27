@echo off
title ALPHA V2 GENESIS — ANTIGRAVITY TRADING SYSTEM
color 0A

echo.
echo  ============================================================
echo       ALPHA V2 GENESIS ^| ANTIGRAVITY TRADING SYSTEM
echo       Lead Quant Architect ^| Strategy Ledger v2.2
echo  ============================================================
echo.

:: 1. Force-kill existing processes for a clean start
echo  [0/4] Cleaning up stale processes...
taskkill /f /im ngrok.exe 2>nul
taskkill /f /im python.exe /t 2>nul

:: Kill the Vite dev server specifically (port 5173) not all node processes
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173" 2^>nul') do taskkill /f /PID %%a 2>nul
timeout /t 2 /nobreak >nul

:: Set Project Root
cd /d "%~dp0"
set "PYTHONPATH=%~dp0"

:: 2. Start Flask Backend + ngrok + Loki Engine
echo  [1/4] Starting Alpha Backend (Flask + ngrok + Loki)...
start "Alpha Server" /min python server.py
echo        Server starting in background...

echo  [2/4] Waiting for server stabilization (ngrok tunnel + warm-up)...
timeout /t 12 /nobreak >nul

:: 3. Infrastructure Supervisor (Portfolio Watchdog + Daily Ledger Cron)
echo  [3/4] Launching Infrastructure Supervisor (Ledger Watchdog)...
start "Infrastructure Supervisor" /min python infrastructure_supervisor.py
timeout /t 2 /nobreak >nul

:: 4. React UI (Vite) — use node directly to bypass PowerShell execution policy
echo  [4/4] Launching Alpha UI (Vite Dev Server)...
cd alpha_ui
start "" http://localhost:5173

:: Use .cmd shim directly to avoid ExecutionPolicy block AND bash-script SyntaxError
node_modules\.bin\vite.cmd --host

echo.
echo  ============================================================
echo       SESSION ENDED. Restart script to resume.
echo  ============================================================
pause
