@echo off
title Resonance Launcher
color 0B
echo.
echo  ============================================
echo    Resonance - V3 Web App Launch
echo  ============================================
echo.

cd /d "%~dp0"

REM === Python Path ===
set PYTHON=C:\Users\mpetr\AppData\Local\Python\pythoncore-3.14-64\python.exe
if not exist "%PYTHON%" (
    set PYTHON=python
)

REM === [1/4] Install Backend Dependencies ===
echo [1/4] Installing backend dependencies...
if exist requirements.txt (
    "%PYTHON%" -m pip install -r requirements.txt -q 2>nul
)

REM === [2/4] Activate N8N Workflow ===
echo [2/4] Activating N8N workflow...
if exist n8n_lifecycle.py (
    "%PYTHON%" -c "import json,sys,os; sys.path.insert(0,'.'); from n8n_lifecycle import set_workflow_active; cfg=json.load(open('config.json')); wid=cfg.get('n8n_workflow_id',''); from dotenv import load_dotenv; load_dotenv(); key=os.getenv('N8N_API_KEY',''); set_workflow_active(wid,True,key,cfg.get('app_name','')) if wid and key else print('No workflow ID or API key')"
) else (
    echo    No lifecycle manager found, skipping...
)

REM === [3/4] Install Frontend Dependencies ===
echo [3/4] Installing frontend (first run only)...
if exist resonance_ui\package.json (
    if not exist resonance_ui\node_modules (
        cd resonance_ui
        npm.cmd install
        cd ..
    )
)

REM === [4/4] Launch Backend + Frontend ===
echo [4/4] Starting Resonance...
echo.
echo    Backend:  http://localhost:5006
echo    Frontend: http://localhost:5174
echo.

REM Start backend in background
start "Resonance Backend" /min "%PYTHON%" server.py

REM Start frontend
cd resonance_ui
start "Resonance Frontend" cmd /k "npm.cmd run dev -- --host --port 5174"
cd ..

REM Open browser
ping 127.0.0.1 -n 5 >nul
start http://localhost:5174

echo  Resonance is running!
echo  Press any key to SHUTDOWN...
pause >nul

REM === CLEANUP ===
echo.
echo  Shutting down...
taskkill /FI "WINDOWTITLE eq Resonance Backend" /F 2>nul
taskkill /FI "WINDOWTITLE eq Resonance Frontend" /F 2>nul

if exist n8n_lifecycle.py (
    "%PYTHON%" -c "import json,sys,os; sys.path.insert(0,'.'); from n8n_lifecycle import set_workflow_active; cfg=json.load(open('config.json')); wid=cfg.get('n8n_workflow_id',''); from dotenv import load_dotenv; load_dotenv(); key=os.getenv('N8N_API_KEY',''); set_workflow_active(wid,False,key,cfg.get('app_name','')) if wid and key else print('No workflow ID or API key')"
    echo  N8N workflow deactivated.
)

echo  Resonance stopped.
pause