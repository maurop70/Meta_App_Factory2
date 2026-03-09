@echo off
REM ═══════════════════════════════════════════════════════════
REM  Sentinel Bridge — One-Click Launcher
REM  Meta App Factory / Aether Layer
REM ═══════════════════════════════════════════════════════════

title Sentinel Bridge - Autonomous Reminder System
echo.
echo  ========================================
echo   Shield  SENTINEL BRIDGE  v1.0
echo   Autonomous Reminder System
echo  ========================================
echo.

REM ── Detect project root ────────────────────────────────────
set "SENTINEL_DIR=%~dp0"
cd /d "%SENTINEL_DIR%"

REM ── Detect Python ──────────────────────────────────────────
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found in PATH.
    echo Please install Python 3.10+ and add to PATH.
    pause
    exit /b 1
)

REM ── Check dependencies ────────────────────────────────────
echo [1/3] Checking dependencies...
python -c "import fastapi" >nul 2>&1
if %errorlevel% neq 0 (
    echo   Installing dependencies...
    pip install -r requirements.txt --quiet
)

REM ── Check if first run ────────────────────────────────────
if not exist "data" (
    echo.
    echo [FIRST RUN] Running configuration wizard...
    echo.
    python sentinel_config.py
)

REM ── Start the server ──────────────────────────────────────
echo.
echo [2/3] Starting Sentinel Bridge on port 5009...
echo.
start /min "Sentinel-API" python sentinel_server.py

REM ── Wait and verify ───────────────────────────────────────
echo [3/3] Waiting for server startup...
timeout /t 4 >nul

REM ── Open dashboard ────────────────────────────────────────
echo.
echo  ========================================
echo   Sentinel Bridge is ACTIVE
echo   API:       http://localhost:5009
echo   Telemetry: http://localhost:5009/api/telemetry
echo  ========================================
echo.

start http://localhost:5009

echo Press any key to stop Sentinel Bridge...
pause >nul

REM ── Graceful shutdown ─────────────────────────────────────
echo Shutting down Sentinel Bridge...
taskkill /fi "WINDOWTITLE eq Sentinel-API" /f >nul 2>&1
echo Done.
