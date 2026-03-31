@echo off
title Resonance
color 0B
echo.
echo  ===================================================
echo    RESONANCE - Launching Alex...
echo  ===================================================
echo.

:: ── Auto-Detect Google Drive Path ──────────────────────────
set "GDRIVE="
if exist "%USERPROFILE%\My Drive\Antigravity-AI Agents\Meta_App_Factory\Resonance" (
    set "GDRIVE=%USERPROFILE%\My Drive"
    goto :GDRIVE_FOUND
)
if exist "%USERPROFILE%\Google Drive\Antigravity-AI Agents\Meta_App_Factory\Resonance" (
    set "GDRIVE=%USERPROFILE%\Google Drive"
    goto :GDRIVE_FOUND
)
for %%d in (G H I D E F) do (
    if exist "%%d:\My Drive\Antigravity-AI Agents\Meta_App_Factory\Resonance" (
        set "GDRIVE=%%d:\My Drive"
        goto :GDRIVE_FOUND
    )
)
echo  [FATAL] Google Drive not found! Make sure Google Drive is installed
echo          and the Antigravity-AI Agents folder is synced.
pause
exit /b 1

:GDRIVE_FOUND
set "APP_DIR=%GDRIVE%\Antigravity-AI Agents\Meta_App_Factory\Resonance"
echo  [OK] Google Drive: %GDRIVE%
echo  [OK] App Dir:      %APP_DIR%
echo.

cd /d "%APP_DIR%"

:: ── Bootstrap Environment ─────────────────────────────────
if exist "..\bootstrap_env.bat" (
    call "..\bootstrap_env.bat"
) else (
    echo  [WARN] bootstrap_env.bat not found, using system Python
    set "PYTHON=python"
)

:: ── Install Python dependencies (if needed) ───────────────
if exist requirements.txt (
    echo  [0/3] Checking Python dependencies...
    "%PYTHON%" -m pip install -r requirements.txt -q 2>nul
)

:: ── Start Backend (server.py on port 5006) ────────────────
echo  [1/3] Starting Backend on port 5006...
start "Resonance Backend" /min "%PYTHON%" server.py

:: ── Start Frontend UI (port 5174) ─────────────────────────
echo  [2/3] Starting Frontend on port 5174...
cd resonance_ui
if not exist node_modules (
    echo        Installing dependencies - first run...
    npm.cmd install
)
start "Resonance Frontend" /min cmd /k "npm.cmd run dev -- --host --port 5174"
cd ..

:: ── Sync Desktop Shortcut (portable across PCs) ──────────
if exist "%APP_DIR%\create_resonance_shortcut.ps1" (
    echo  [SYNC] Refreshing desktop shortcut for this PC...
    powershell -ExecutionPolicy Bypass -File "%APP_DIR%\create_resonance_shortcut.ps1" >nul 2>&1
)

:: ── Open Browser ──────────────────────────────────────────
echo  [3/3] Suppressing browser tab (Headless Mode Active)...
ping 127.0.0.1 -n 5 >nul
:: start http://localhost:5174

echo.
echo  ===================================================
echo    Resonance is running!
echo    Backend:  http://localhost:5006
echo    Frontend: http://localhost:5174
echo    Machine:  %COMPUTERNAME%
echo    Press any key to SHUTDOWN...
echo  ===================================================
pause >nul

:: ── CLEANUP ───────────────────────────────────────────────
echo  Shutting down...
taskkill /FI "WINDOWTITLE eq Resonance Backend" /F 2>nul
taskkill /FI "WINDOWTITLE eq Resonance Frontend" /F 2>nul
echo  Resonance stopped.
pause
