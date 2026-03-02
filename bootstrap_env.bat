@echo off
:: ═══════════════════════════════════════════════════════════════
::  Meta App Factory — Portable Environment Bootstrap
::  Called by ALL launch scripts. Sets up machine-agnostic env.
::  NO hardcoded paths. Everything is auto-detected.
:: ═══════════════════════════════════════════════════════════════

:: ── 1. Python Auto-Detection (cascading search) ──────────────
set "PYTHON="

:: Strategy: Try common install locations, then fall back to PATH
:: This covers: Microsoft Store, python.org, custom installs
for /f "delims=" %%p in ('where python 2^>nul') do (
    set "PYTHON=%%p"
    goto :PYTHON_FOUND
)

:: Manual scan of common locations (if 'where' fails due to Store alias)
for /d %%d in ("%LOCALAPPDATA%\Python\pythoncore-*") do (
    if exist "%%d\python.exe" (
        set "PYTHON=%%d\python.exe"
        goto :PYTHON_FOUND
    )
)
for /d %%d in ("%LOCALAPPDATA%\Programs\Python\Python*") do (
    if exist "%%d\python.exe" (
        set "PYTHON=%%d\python.exe"
        goto :PYTHON_FOUND
    )
)

:: Last resort: try bare 'python' and 'python3'
python --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "PYTHON=python"
    goto :PYTHON_FOUND
)
python3 --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "PYTHON=python3"
    goto :PYTHON_FOUND
)

echo.
echo  [FATAL] Python not found on this machine!
echo          Install Python 3.10+ from python.org
pause
exit /b 1

:PYTHON_FOUND
echo  [OK] Python: %PYTHON%

:: ── 2. Runtime Data Isolation (per-machine) ──────────────────
:: Use %LOCALAPPDATA% which is unique per Windows user/machine.
:: This ensures PC1 and PC2 never conflict on runtime files.
if not defined ALPHA_RUNTIME_DIR (
    set "ALPHA_RUNTIME_DIR=%LOCALAPPDATA%\AlphaArchitect\Alpha_Data"
)
if not exist "%ALPHA_RUNTIME_DIR%" mkdir "%ALPHA_RUNTIME_DIR%"
echo  [OK] Runtime Dir: %ALPHA_RUNTIME_DIR%

:: ── 3. Machine Identity (for logging/diagnostics) ───────────
set "ALPHA_MACHINE_ID=%COMPUTERNAME%"
echo  [OK] Machine ID: %ALPHA_MACHINE_ID%

:: ── 4. .env Auto-Setup ──────────────────────────────────────
:: If .env doesn't exist but env.template does, create a copy
:: and prompt the user to add their API keys.
set "PROJECT_ROOT=%~dp0"
set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"

if not exist "%PROJECT_ROOT%\.env" (
    if exist "%PROJECT_ROOT%\env.template" (
        echo.
        echo  [SETUP] No .env found. Creating from template...
        copy "%PROJECT_ROOT%\env.template" "%PROJECT_ROOT%\.env" >nul
        echo  [SETUP] Created %PROJECT_ROOT%\.env
        echo  [SETUP] *** IMPORTANT: Edit .env and add your API keys! ***
    )
)

:: Also handle Alpha_V2_Genesis sub-env
if not exist "%PROJECT_ROOT%\Alpha_V2_Genesis\.env" (
    if exist "%PROJECT_ROOT%\.env" (
        echo  [SETUP] Syncing .env to Alpha_V2_Genesis...
        copy "%PROJECT_ROOT%\.env" "%PROJECT_ROOT%\Alpha_V2_Genesis\.env" >nul
    )
)

:: ── 5. Node.js Check ─────────────────────────────────────────
where node >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo  [OK] Node.js: found
) else (
    echo  [WARN] Node.js not found. UI features may not work.
)

echo.
echo  ────────────────────────────────────────────────────
echo   Environment Ready [%ALPHA_MACHINE_ID%]
echo  ────────────────────────────────────────────────────
echo.
