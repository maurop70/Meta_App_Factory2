"""
MCP Bridge Server
-----------------
Receives telemetry from the Chrome Extension via WebSocket,
exposes it to Claude Code via MCP protocol,
and injects CLAUDE_RULES.md into every Antigravity dispatch.

Run with: python server.py
"""

import asyncio
import json
import logging
import os
import sys
from collections import deque
from datetime import datetime
from pathlib import Path

# ── Wire imports ──────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))
from shell_wire import execute as _shell_execute, AUDIT_LOG as _SHELL_AUDIT_LOG, LIVE_LOG as _SHELL_LIVE_LOG
from git_wire import execute_async as _git_execute_async
from ssh_wire import execute_async as _ssh_execute_async

import websockets
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Resource, Tool, TextContent

# ── Config ────────────────────────────────────────────────
WS_HOST = "localhost"
WS_PORT = 9001
RULES_PATH = Path(__file__).parent.parent / "rules" / "CLAUDE_RULES.md"
TELEMETRY_LOG = Path(__file__).parent.parent / "logs" / "telemetry.jsonl"
MAX_EVENTS = 200

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("mcp-bridge")

# ── State ─────────────────────────────────────────────────
telemetry_buffer: deque = deque(maxlen=MAX_EVENTS)
connected_extensions: set = set()

# ── WebSocket receiver ────────────────────────────────────
async def ws_handler(websocket):
    connected_extensions.add(websocket)
    log.info(f"Chrome extension connected ({len(connected_extensions)} active)")
    try:
        async for raw in websocket:
            try:
                event = json.loads(raw)
                event["_received_at"] = datetime.utcnow().isoformat()

                # ── Telemetry filter: exclude claude.ai traffic ──────────
                _url = event.get("url") or event.get("data", {}).get("url", "")
                if any(domain in str(_url) for domain in 
                       ("claude.ai", "anthropic.com", "assets-proxy.anthropic.com")):
                    log.debug(f"[TELEMETRY FILTER] Skipped external domain event: {str(event)[:80]}")
                    continue
                # ─────────────────────────────────────────────────────────

                # Drop console_error and page_error from external tabs
                if event.get("type") in ("console_error", "page_error"):
                    _url = (
                        event.get("url") or
                        event.get("data", {}).get("url", "") or
                        ""
                    )
                    if not _url or any(domain in str(_url) for domain in 
                                       ("claude.ai", "anthropic.com", "assets-proxy.anthropic.com")):
                        log.debug(f"[FILTER] Skipped external tab error: {event.get('type')}")
                        continue

                telemetry_buffer.append(event)
                TELEMETRY_LOG.parent.mkdir(parents=True, exist_ok=True)
                with open(TELEMETRY_LOG, "a", encoding="utf-8") as f:
                    f.write(json.dumps(event) + "\n")
                log.info(f"[TELEMETRY] {event.get('type','?')} — {str(event)[:120]}")
            except json.JSONDecodeError:
                log.warning(f"Bad JSON from extension: {raw[:80]}")
    except websockets.exceptions.ConnectionClosed:
        log.info("Chrome extension disconnected")
    finally:
        connected_extensions.discard(websocket)

async def start_ws_server():
    log.info(f"WebSocket listening on ws://{WS_HOST}:{WS_PORT}")
    async with websockets.serve(ws_handler, WS_HOST, WS_PORT):
        await asyncio.Future()

# ── MCP Server ────────────────────────────────────────────
mcp = Server("claude-mcp-bridge")

@mcp.list_resources()
async def list_resources():
    return [
        Resource(
            uri="telemetry://live",
            name="Live Browser Telemetry",
            description="Rolling buffer of console errors, network failures, page crashes",
            mimeType="application/json",
        ),
        Resource(
            uri="rules://claude",
            name="CLAUDE_RULES.md",
            description="Permanent architect rules injected into every Antigravity session",
            mimeType="text/markdown",
        ),
    ]

@mcp.read_resource()
async def read_resource(uri: str):
    if uri == "telemetry://live":
        events = list(telemetry_buffer)
        critical = [e for e in events if e.get("type") in
                    ("console_error", "page_error", "request_failed")]
        other = [e for e in events if e not in critical]
        payload = {"critical": critical, "other": other, "total": len(events)}
        return [TextContent(type="text", text=json.dumps(payload, indent=2))]
    if uri == "rules://claude":
        if RULES_PATH.exists():
            return [TextContent(type="text", text=RULES_PATH.read_text(encoding="utf-8"))]
        return [TextContent(type="text", text="# CLAUDE_RULES.md not found")]
    raise ValueError(f"Unknown resource: {uri}")

@mcp.list_tools()
async def list_tools():
    return [
        Tool(
            name="get_telemetry_summary",
            description="Returns prioritised browser errors for Claude to analyse",
            inputSchema={"type": "object", "properties": {
                "last_n": {"type": "integer", "default": 50}
            }},
        ),
        Tool(
            name="clear_telemetry",
            description="Clears telemetry buffer after issue resolved",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_rules",
            description="Returns current CLAUDE_RULES.md content",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="update_rules",
            description="Appends a new rule section to CLAUDE_RULES.md",
            inputSchema={"type": "object", "properties": {
                "section": {"type": "string"}
            }, "required": ["section"]},
        ),
        # ── Shell Wire ─────────────────────────────────────────
        Tool(
            name="execute_shell",
            description=(
                "Execute a shell command on the local Windows/Linux machine. "
                "Returns stdout, stderr, exit_code, duration_ms, timed_out, blocked. "
                "Subject to a hard blocklist (destructive OS commands refused). "
                "Working directory must be within SHELL_WIRE_ALLOWED_ROOTS. "
                "Use for: git, pip, npm, pytest, uvicorn, deploy scripts, curl."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Raw command string to execute."
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Working directory. Defaults to MAF root if omitted."
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "default": 30,
                        "description": "Max execution time in seconds (1–120)."
                    },
                    "shell": {
                        "type": "string",
                        "enum": ["auto", "powershell", "cmd", "bash"],
                        "default": "auto",
                        "description": "'auto' uses PowerShell on Windows, bash elsewhere."
                    },
                },
                "required": ["command"],
            },
        ),
        Tool(
            name="get_shell_log",
            description=(
                "Returns the live output log from the most recent shell_wire execution. "
                "Poll this during long-running commands (pip install, npm, deploys) "
                "to check progress without waiting for the call to return."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        # ── Git Wire ────────────────────────────────────────────
        Tool(
            name="git_operation",
            description=(
                "Execute a safe, audited git operation via git_wire. "
                "Supports: status, log, diff, add, commit, push, pull, branch, reset_file, stash. "
                "Enforces: no force-push, no push to prod/production, no reset --hard/clean. "
                "Push/pull failures caused by network errors return exit_code 502. "
                "Use this instead of execute_shell for all git work."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["status", "log", "diff", "add", "commit", "push",
                                 "pull", "branch", "reset_file", "stash"],
                        "description": "Git operation to perform.",
                    },
                    "args": {
                        "type": "object",
                        "description": (
                            "Operation-specific arguments. "
                            "commit: {message}, push/pull: {branch}, "
                            "add: {paths: []}, log: {n}, diff: {staged: bool}, "
                            "branch: {name}, reset_file: {file}, stash: {action: push|pop}."
                        ),
                        "default": {},
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Repository path. Defaults to MAF root if omitted.",
                    },
                },
                "required": ["operation"],
            },
        ),
        # ── SSH Wire ─────────────────────────────────────────
        Tool(
            name="execute_remote_shell",
            description=(
                "Execute a shell command on an approved remote production server via SSH. "
                "Approved hosts: maf-production-nyc1 (104.248.233.220), "
                "mwo-production-nyc1 (68.183.30.128). "
                "Any other host_ip is blocked. "
                "Subject to a remote command blocklist (rm -rf /, reboot, shutdown, mkfs, etc.). "
                "Network failures return exit_code 502 (Gateway Unreachable). "
                "Auth: root user, key-based only."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "host_ip": {
                        "type": "string",
                        "description": (
                            "IP address of the target server. "
                            "Must be in the approved host list."
                        ),
                    },
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute on the remote host.",
                    },
                    "timeout": {
                        "type": "integer",
                        "default": 60,
                        "description": "Command timeout in seconds.",
                    },
                },
                "required": ["host_ip", "command"],
            },
        ),
    ]

@mcp.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "get_telemetry_summary":
        n = arguments.get("last_n", 50)
        events = list(telemetry_buffer)[-n:]
        errors = [e for e in events if e.get("type") in
                  ("console_error", "page_error", "request_failed")]
        summary = {
            "window": f"last {n} events",
            "total_events": len(events),
            "critical_count": len(errors),
            "critical_events": errors,
            "all_events": events,
        }
        return [TextContent(type="text", text=json.dumps(summary, indent=2))]
    if name == "clear_telemetry":
        telemetry_buffer.clear()
        return [TextContent(type="text", text="Telemetry buffer cleared.")]
    if name == "get_rules":
        content = RULES_PATH.read_text(encoding="utf-8") if RULES_PATH.exists() else "No rules file found."
        return [TextContent(type="text", text=content)]
    if name == "update_rules":
        section = arguments["section"]
        RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(RULES_PATH, "a", encoding="utf-8") as f:
            f.write(f"\n\n{section}\n")
        return [TextContent(type="text", text=f"Rule appended to {RULES_PATH}")]
    # ── Shell Wire handlers ───────────────────────────────
    if name == "execute_shell":
        command = arguments.get("command", "").strip()
        if not command:
            return [TextContent(type="text",
                                text=json.dumps({"error": "No command provided"}))]
        loop   = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: _shell_execute(
                command=command,
                cwd=arguments.get("cwd"),
                timeout_seconds=int(arguments.get("timeout_seconds", 30)),
                shell=arguments.get("shell", "auto"),
            ),
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    if name == "get_shell_log":
        content = (
            _SHELL_LIVE_LOG.read_text(encoding="utf-8")
            if _SHELL_LIVE_LOG.exists()
            else "[no shell activity yet]"
        )
        return [TextContent(type="text", text=content)]
    # ── Git Wire handler ──────────────────────────────────
    if name == "git_operation":
        operation = arguments.get("operation", "").strip()
        if not operation:
            return [TextContent(type="text",
                                text=json.dumps({"error": "No operation provided"}))]
        result = await _git_execute_async(
            operation=operation,
            args=arguments.get("args") or {},
            cwd=arguments.get("cwd"),
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    # ── SSH Wire handler ──────────────────────────────────
    if name == "execute_remote_shell":
        host_ip = arguments.get("host_ip", "").strip()
        command = arguments.get("command", "").strip()
        if not host_ip or not command:
            return [TextContent(type="text",
                                text=json.dumps({"error": "host_ip and command are required"}))]
        result = await _ssh_execute_async(
            host_ip=host_ip,
            command=command,
            timeout=int(arguments.get("timeout", 60)),
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    raise ValueError(f"Unknown tool: {name}")

# ── Entry point ───────────────────────────────────────────
async def main():
    ws_task = asyncio.create_task(start_ws_server())
    async with stdio_server() as (read_stream, write_stream):
        await mcp.run(read_stream, write_stream,
                      mcp.create_initialization_options())
    ws_task.cancel()

if __name__ == "__main__":
    asyncio.run(main())
