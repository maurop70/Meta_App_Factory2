@echo off
setlocal enabledelayedexpansion
title Phantom QA Elite — Launching...

echo.
echo ============================================================
echo.
echo   PHANTOM QA ELITE — Autonomous Quality Assurance
echo   Antigravity-AI
echo.
echo ============================================================
echo.

:: ── Detect Python ──
set "PYTHON_CMD="
where python >nul 2>&1 && set "PYTHON_CMD=python"
if not defined PYTHON_CMD (
    where python3 >nul 2>&1 && set "PYTHON_CMD=python3"
)
if not defined PYTHON_CMD (
    echo [ERROR] Python not found. Please install Python 3.10+
    pause
    exit /b 1
)
echo [OK] Python: %PYTHON_CMD%

:: ── Navigate to backend ──
cd /d "%~dp0backend"

:: ── Install dependencies ──
echo [INFO] Installing dependencies...
%PYTHON_CMD% -m pip install -r requirements.txt --quiet 2>nul
echo [OK] Dependencies installed

:: ── Install Playwright Chromium ──
echo [INFO] Installing Playwright Chromium (first run may take ~200MB)...
%PYTHON_CMD% -m playwright install chromium --quiet 2>nul
if errorlevel 1 (
    echo [WARN] Playwright install failed — Ghost User tests will be skipped
) else (
    echo [OK] Playwright Chromium ready
)

:: ── Start server ──
echo.
echo [INFO] Starting Phantom QA Elite on port 5030...
echo.
start "PhantomQA" %PYTHON_CMD% server.py

:: ── Wait for server ──
timeout /t 3 /nobreak >nul

:: ── Open browser ──
echo [INFO] Opening dashboard...
start http://localhost:5030

echo.
echo ============================================================
echo   Phantom QA Elite is running at http://localhost:5030
echo   Press Ctrl+C in the server window to stop
echo ============================================================
echo.
