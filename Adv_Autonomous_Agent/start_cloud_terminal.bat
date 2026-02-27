@echo off
:: CLOUD TERMINAL LAUNCHER
:: Force execution from this Drive Directory to prevent local data creation
cd /d "%~dp0"

:: Set PYTHONPATH to ensure robust imports from this location
set "PYTHONPATH=%~dp0;%~dp0..\..\skills;%PYTHONPATH%"

echo ===================================================
echo   ADV AUTONOMOUS AGENT - CLOUD TERMINAL
echo   Current Directory: %cd%
echo   Mode: DISPLAY ONLY (Data writes to Drive)
echo   Target: Project_Debug_Phoenix
echo ===================================================

:: Ensure dependencies are installed
echo Checking for missing dependencies...
python -m pip install -r requirements.txt

:: Run UI with Debug Project Context
python ui.py Project_Debug_Phoenix

pause
