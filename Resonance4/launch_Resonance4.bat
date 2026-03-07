@echo off
title Resonance4 Launcher
color 0B
echo.
echo  ============================================
echo    Resonance4 - Antigravity Launch
echo  ============================================
echo.

cd /d "%~dp0"

REM Auto-install dependencies
if exist requirements.txt (
    echo [1/4] Installing dependencies...
    pip install -r requirements.txt -q 2>nul
) else (
    echo [1/4] No requirements.txt found, skipping...
)

REM Check Docker
echo [2/4] Checking Docker...
docker info >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Docker not running. Starting Docker Desktop...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    timeout /t 15 /nobreak >nul
)

REM Activate N8N Workflows
echo [3/4] Activating N8N workflows...
if exist n8n_lifecycle.py (
    python -c "import json,sys,os; sys.path.insert(0,'.'); from n8n_lifecycle import set_workflow_active; cfg=json.load(open('config.json')); wid=cfg.get('n8n_workflow_id',''); from dotenv import load_dotenv; load_dotenv(); key=os.getenv('N8N_API_KEY',''); set_workflow_active(wid,True,key,cfg.get('app_name','')) if wid and key else print('No workflow ID or API key')"
) else (
    echo    No lifecycle manager found, skipping...
)

REM Launch UI
echo [4/4] Launching Resonance4 UI...
python ui.py

REM === CLEANUP: Deactivate N8N workflows on shutdown ===
echo.
echo  Shutting down N8N workflows...
if exist n8n_lifecycle.py (
    python -c "import json,sys,os; sys.path.insert(0,'.'); from n8n_lifecycle import set_workflow_active; cfg=json.load(open('config.json')); wid=cfg.get('n8n_workflow_id',''); from dotenv import load_dotenv; load_dotenv(); key=os.getenv('N8N_API_KEY',''); set_workflow_active(wid,False,key,cfg.get('app_name','')) if wid and key else print('No workflow ID or API key')"
)
echo  N8N workflows deactivated.

pause
