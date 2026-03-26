@echo off
REM ═══════════════════════════════════════════════════════════
REM  CMO Agent — One-Click Launcher
REM  Antigravity-AI | Port 5020
REM ═══════════════════════════════════════════════════════════
title CMO Agent - Marketing Intelligence Command Center

echo.
echo  ╔═══════════════════════════════════════════════════╗
echo  ║  📢 CMO Agent — Launching...                      ║
echo  ╚═══════════════════════════════════════════════════╝
echo.

REM ── Detect Python ──────────────────────────────────────
set "PYTHON_CMD="
where python >nul 2>&1 && set "PYTHON_CMD=python"
where python3 >nul 2>&1 && set "PYTHON_CMD=python3"
if "%PYTHON_CMD%"=="" (
    echo [ERROR] Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

echo  [INFO] Using: %PYTHON_CMD%

REM ── Navigate to backend ────────────────────────────────
cd /d "%~dp0backend"

REM ── Install dependencies if needed ─────────────────────
if not exist "__pycache__" (
    echo  [INFO] Installing dependencies...
    %PYTHON_CMD% -m pip install -r requirements.txt --quiet
)

REM ── Launch the server ──────────────────────────────────
echo.
echo  [INFO] Starting CMO Agent on port 5020...
echo  [INFO] Dashboard: http://localhost:5020
echo  [INFO] API Docs:  http://localhost:5020/docs
echo.

REM ── Open browser after short delay ─────────────────────
start "" cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:5020"

REM ── Run the server (blocking) ──────────────────────────
%PYTHON_CMD% server.py

pause
