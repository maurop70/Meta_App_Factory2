@echo off
title ClaudeAY — Architect Terminal
echo ================================================
echo   ClaudeAY — Claude + Antigravity Bridge
echo ================================================
echo.
echo Starting Claude MCP Bridge (Port 9001)...
start "Claude MCP Bridge" /min cmd /k "cd /d %~dp0 && python claude-mcp-bridge/mcp_server/server.py"

echo Starting ClaudeAY Web UI Server (Port 9002)...
start "ClaudeAY Server" /min cmd /k "cd /d %~dp0 && python claude-mcp-bridge/claudeay_ui_server.py"

echo Waiting for servers to initialize...
timeout /t 4 >nul

echo Opening ClaudeAY in browser...
start http://localhost:9002

echo.
echo ClaudeAY is running.
echo MCP Bridge:  ws://localhost:9001
echo Web UI:      http://localhost:9002
timeout /t 2 >nul
