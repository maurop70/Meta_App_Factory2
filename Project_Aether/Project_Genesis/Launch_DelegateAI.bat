@echo off
REM ═══════════════════════════════════════════════════
REM  DELEGATE AI — Launch Script
REM  Project Genesis | Aether Runtime
REM ═══════════════════════════════════════════════════

echo.
echo  ============================================
echo   DELEGATE AI — Legal Task Delegation API
echo   Project Genesis ^| Aether Runtime
echo  ============================================
echo.

REM ── Locate Google Drive ──
set "GDRIVE="
for %%D in (
    "%USERPROFILE%\My Drive"
    "%USERPROFILE%\Google Drive"
    "G:\My Drive"
) do (
    if exist "%%~D\Antigravity-AI Agents" (
        set "GDRIVE=%%~D"
        goto :found_drive
    )
)
echo [ERROR] Google Drive not found!
pause
exit /b 1

:found_drive
echo [OK] Google Drive: %GDRIVE%

set "PROJECT=%GDRIVE%\Antigravity-AI Agents\Meta_App_Factory\Project_Aether\Project_Genesis"

REM ── Locate Python ──
set "PYTHON="
where python >nul 2>&1 && set "PYTHON=python" && goto :found_python
where python3 >nul 2>&1 && set "PYTHON=python3" && goto :found_python
for /f "delims=" %%P in ('where /r "%LOCALAPPDATA%\Programs\Python" python.exe 2^>nul') do (
    set "PYTHON=%%P"
    goto :found_python
)
echo [ERROR] Python not found!
pause
exit /b 1

:found_python
echo [OK] Python: %PYTHON%

REM ── Install deps if needed ──
%PYTHON% -c "import fastapi" >nul 2>&1 || (
    echo [INSTALL] Installing dependencies...
    %PYTHON% -m pip install -r "%PROJECT%\requirements.txt" --quiet
)

REM ── Launch ──
echo.
echo [LAUNCH] Starting Delegate AI API on port 8002...
echo          API Docs: http://localhost:8002/docs
echo          Health:   http://localhost:8002/health
echo.

cd /d "%PROJECT%"
%PYTHON% delegate_api.py --port 8002
pause
