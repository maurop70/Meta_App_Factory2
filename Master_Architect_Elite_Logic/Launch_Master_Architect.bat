@echo off
chcp 65001 >nul 2>&1
title Master Architect Elite Logic — Port 5050

echo ════════════════════════════════════════════════════
echo   Master Architect Elite Logic — Launcher
echo   Port 5050 ^| Meta App Factory ^| Antigravity V3
echo ════════════════════════════════════════════════════
echo.

:: ── Detect script directory (Google Drive safe) ───────
set "MA_DIR=%~dp0"
set "MA_DIR=%MA_DIR:~0,-1%"

:: ── Detect Factory root (one level up) ────────────────
for %%I in ("%MA_DIR%\..") do set "FACTORY_DIR=%%~fI"

:: ── Load environment ─────────────────────────────────
if exist "%FACTORY_DIR%\.env" (
    echo [ENV] Loading Factory .env...
    for /f "usebackq tokens=1,* delims==" %%A in ("%FACTORY_DIR%\.env") do (
        set "%%A=%%B" 2>nul
    )
)
if exist "%MA_DIR%\.env" (
    echo [ENV] Loading local .env...
    for /f "usebackq tokens=1,* delims==" %%A in ("%MA_DIR%\.env") do (
        set "%%A=%%B" 2>nul
    )
)

:: ── Find Python ──────────────────────────────────────
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found in PATH.
    echo         Install Python 3.11+ from python.org
    pause
    exit /b 1
)

:: ── Install dependencies if needed ───────────────────
if exist "%MA_DIR%\requirements.txt" (
    echo [DEPS] Checking dependencies...
    python -m pip install -q -r "%MA_DIR%\requirements.txt" 2>nul
)

:: ── Check port 5050 ─────────────────────────────────
set "MA_PORT=5050"
netstat -ano | findstr ":5050 " | findstr "LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo [WARN] Port 5050 is in use. Trying 5051...
    set "MA_PORT=5051"
    netstat -ano | findstr ":5051 " | findstr "LISTENING" >nul 2>&1
    if %errorlevel% equ 0 (
        echo [ERROR] Ports 5050 and 5051 are both in use.
        pause
        exit /b 1
    )
)

echo.
echo [START] Launching Master Architect on port %MA_PORT%...
echo         URL: http://localhost:%MA_PORT%
echo         Health: http://localhost:%MA_PORT%/api/health
echo.

:: ── Launch ──────────────────────────────────────────
set "MA_PORT=%MA_PORT%"
cd /d "%MA_DIR%"
python server.py

echo.
echo [EXIT] Master Architect has stopped.
pause
