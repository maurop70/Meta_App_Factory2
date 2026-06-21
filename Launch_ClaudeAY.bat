@echo off
title ClaudeAY — Architect Terminal

:: Activate local Python 3.12 virtual environment to avoid Python 3.14 incompatibilities
if exist "%~dp0venv\Scripts\activate.bat" (
    echo [INFO] Activating virtual environment...
    call "%~dp0venv\Scripts\activate.bat"
)
echo ================================================
echo   ClaudeAY — Claude + Antigravity Bridge
echo ================================================
echo.

:: ── Launch Full Meta App Factory Microservices ───────────
echo Actuating all Meta App Factory services in background...
start "MAF Stack" cmd /c "cd /d %~dp0 && Launch_Web_UI.bat"
timeout /t 5 /nobreak >nul

:: ── Start ClaudeAY UI ────────────────────────────────────
echo Starting ClaudeAY Web UI (Port 9002)...
start "ClaudeAY UI" /min cmd /c "cd /d %~dp0 && python claude-mcp-bridge/claudeay_ui_server.py"
timeout /t 2 /nobreak >nul

:: ── Open Browser ──────────────────────────────────────────
start "" "http://localhost:9002"

echo.
echo ClaudeAY is running with all MAF microservices!
echo MCP Bridge:  ws://localhost:9001
echo Master Architect: http://localhost:5050
echo Web UI:      http://localhost:9002
echo MAF UI:      http://localhost:5173
timeout /t 5 >nul
