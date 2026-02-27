@echo off
title Meta App Factory Launcher
color 0B
echo.
echo  ===================================================
echo    META APP FACTORY - ELITE COUNCIL SYSTEM
echo    Antigravity Launch Sequence v2.1
echo  ===================================================
echo.

:: ── Step 0: Preflight Check ──────────────────────────────────
echo  [0/4] Running Preflight Check...
cd /d "%~dp0\Alpha_V2_Genesis"
python preflight.py --app meta --dir "%~dp0"
echo.

:: ── Step 1: Ensure Docker Desktop is Running ──────────────────
echo  [1/4] Checking Docker Engine...
docker info >nul 2>&1
if %ERRORLEVEL% EQU 0 goto DOCKER_READY

echo        Docker is NOT running. Starting Docker Desktop...
start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
echo        Waiting for Docker daemon to initialize...
set /a WAIT_COUNT=0

:DOCKER_WAIT
timeout /t 5 /nobreak >nul
docker info >nul 2>&1
if %ERRORLEVEL% EQU 0 goto DOCKER_READY
set /a WAIT_COUNT+=1
if %WAIT_COUNT% GEQ 24 (
    echo.
    echo  [ERROR] Docker did not start within 120 seconds.
    echo          Please start Docker Desktop manually and retry.
    pause
    exit /b 1
)
echo        Still waiting... (%WAIT_COUNT%/24)
goto DOCKER_WAIT

:DOCKER_READY
echo        Docker Engine: READY
echo.

:: ── Step 2: Start Container ──────────────────────────────────
echo  [2/4] Starting Docker Container: meta_factory...
docker start adv_autonomous_agent-meta_factory-1
if %ERRORLEVEL% NEQ 0 (
    echo        [WARN] Container may not exist. Attempting docker-compose up...
    cd /d "%~dp0"
    docker compose up -d 2>nul || docker-compose up -d 2>nul
)
timeout /t 3 /nobreak >nul
echo.

:: ── Step 3: Activate N8N Workflows for Meta App Factory ──────
echo  [3/4] Activating N8N Meta Workflows...
cd /d "%~dp0\Alpha_V2_Genesis"
python n8n_lifecycle.py activate meta
timeout /t 1 /nobreak >nul
echo.

:: ── Step 4: Open Swagger + Launch UI ─────────────────────────
echo  [4/4] Launching Elite Council...
start http://localhost:8000/docs
cd /d "%~dp0\Adv_Autonomous_Agent"
start python ui.py "Elite_Council"
echo.

echo  ===================================================
echo    Startup Complete. Neural Network is Online.
echo    Press any key to SHUT DOWN and deactivate N8N.
echo  ===================================================
pause

:: ─── CLEANUP: Deactivate N8N workflows on shutdown ───────────
echo.
echo  Shutting down N8N Meta workflows...
cd /d "%~dp0\Alpha_V2_Genesis"
python n8n_lifecycle.py deactivate meta

echo.
echo  ===================================================
echo    SESSION ENDED. N8N workflows deactivated.
echo  ===================================================
pause
