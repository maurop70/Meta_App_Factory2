@echo off
title ClaudeAY — Architect Terminal
echo ================================================
echo   ClaudeAY — Claude + Antigravity Bridge
echo ================================================
echo.

:: ── Server Layer ─────────────────────────────────────────
start "MCP Bridge" cmd /c "cd /d %~dp0 && python claude-mcp-bridge/mcp_server/server.py"
timeout /t 2 /nobreak >nul

start "Master Architect" cmd /c "cd /d %~dp0 && python Master_Architect_Elite_Logic/server.py"
timeout /t 3 /nobreak >nul

start "ClaudeAY UI" cmd /c "cd /d %~dp0 && python claude-mcp-bridge/claudeay_ui_server.py"
timeout /t 2 /nobreak >nul

:: ── Open Browser ──────────────────────────────────────────
start "" "http://localhost:9002"

echo.
echo ClaudeAY is running.
echo MCP Bridge:  ws://localhost:9001
echo Master Architect: http://localhost:5050
echo Web UI:      http://localhost:9002
timeout /t 2 >nul
