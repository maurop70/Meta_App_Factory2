@echo off
title Meta App Factory V3
color 0B
echo.
echo  ===================================================
echo    META APP FACTORY V3 - Launching...
echo  ===================================================
echo.

:: ── Auto-Detect Google Drive Path ──────────────────────────
:: Google Drive Stream mounts at: %USERPROFILE%\My Drive
:: Google Drive Mirror mounts at: %USERPROFILE%\Google Drive
:: Some setups use: G:\My Drive
set "GDRIVE="
if exist "%USERPROFILE%\My Drive\Antigravity-AI Agents\Meta_App_Factory" (
    set "GDRIVE=%USERPROFILE%\My Drive"
    goto :GDRIVE_FOUND
)
if exist "%USERPROFILE%\Google Drive\Antigravity-AI Agents\Meta_App_Factory" (
    set "GDRIVE=%USERPROFILE%\Google Drive"
    goto :GDRIVE_FOUND
)
for %%d in (G H I D E F) do (
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

:: ── Bootstrap Environment (Python, Node, .env) ────────────
if exist bootstrap_env.bat (
    call bootstrap_env.bat
) else (
    echo  [WARN] bootstrap_env.bat not found, using system Python
    set "PYTHON=python"
)

:: ── Start Backend (api.py on port 8000) ───────────────────
echo  [1/3] Starting Backend on port 8000...
start "Meta Factory Backend" /min "%PYTHON%" api.py

:: ── Start Frontend UI (port 5173) ─────────────────────────
echo  [2/3] Starting Factory UI on port 5173...
cd factory_ui
if not exist node_modules (
    echo        Installing dependencies (first run)...
    npm.cmd install
)
start "Meta Factory UI" /min cmd /k "npm.cmd run dev -- --host --port 5173"
cd ..

:: ── Open Browser ──────────────────────────────────────────
echo  [3/3] Opening browser...
ping 127.0.0.1 -n 4 >nul
start http://localhost:5173

echo.
echo  ===================================================
echo    Meta App Factory is running!
echo    Backend:  http://localhost:8000
echo    Frontend: http://localhost:5173
echo    Machine:  %COMPUTERNAME%
echo    Press any key to SHUTDOWN...
echo  ===================================================
pause >nul

:: ── CLEANUP ───────────────────────────────────────────────
echo  Shutting down...
taskkill /FI "WINDOWTITLE eq Meta Factory Backend" /F 2>nul
taskkill /FI "WINDOWTITLE eq Meta Factory UI" /F 2>nul
echo  Meta App Factory stopped.
pause
