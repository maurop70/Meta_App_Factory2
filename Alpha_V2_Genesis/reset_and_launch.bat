@echo off
title ALPHA V2 RESET & LAUNCH
cd /d "%~dp0"

echo [1/3] Clearing Pipeline...
taskkill /F /IM python.exe /IM node.exe /IM ngrok.exe 2>nul
echo.

echo [1.5/3] Ensuring Dependencies...
python -m pip install flask-cors pyngrok flask python-dotenv
echo.

echo [2/3] Hard-Coding UI Configuration...
python -c "import json; import os; path = 'alpha_ui/public/config.json'; os.makedirs(os.path.dirname(path), exist_ok=True); open(path, 'w').write(json.dumps({'apiBaseUrl': 'http://localhost:5005'}))"
echo Config synced to Port 5005.

echo [3/3] Launching Bridge (Port 5005)...
start "Alpha Bridge (Server)" python server.py
timeout /t 5

echo [3/3] Launching UI...
cd alpha_ui
start "Alpha UI" npm run dev

echo.
echo ===================================================
echo   SYSTEM RESET COMPLETE
echo   1. Server running on Port 5005
echo   2. UI connected via localhost:5005
echo   3. N8N Sync Active
echo ===================================================
pause
