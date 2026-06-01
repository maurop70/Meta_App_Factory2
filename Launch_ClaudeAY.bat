@echo off
title ClaudeAY — Architect Terminal
echo ================================================
echo   ClaudeAY — Claude + Antigravity Bridge
echo ================================================
echo.
echo Starting Claude MCP Bridge (Port 9001)...
start "Claude MCP Bridge" /min cmd /k "cd /d %~dp0 && python claude-mcp-bridge/mcp_server/server.py"

echo Waiting for bridge to initialize...
timeout /t 3 >nul

echo Starting ClaudeAY Loop UI...
start "ClaudeAY Loop" cmd /k "cd /d %~dp0 && python claude-mcp-bridge/loop_ui.py"

echo.
echo ClaudeAY is starting...
echo MCP Bridge: ws://localhost:9001
echo Loop UI: open in the ClaudeAY terminal
echo.
echo You can now type your intent in the ClaudeAY terminal.
timeout /t 2 >nul
