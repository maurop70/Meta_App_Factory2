@echo off
setlocal
cd /d "%~dp0"

echo ========================================================
echo   Starting Venture Architect Agent Backend...
echo ========================================================
echo.

:: Check for .env file
if not exist "..\.env" (
    echo WARNING: No .env file found in root directory.
    echo Please create one with GEMINI_API_KEY
    pause
    exit /b 1
)

:: Set environment variables from root .env
for /f "usebackq tokens=1,* delims==" %%A in ("..\.env") do (
    set "%%A=%%B"
)

cd backend
python server.py

pause
