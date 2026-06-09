# claude-mcp-bridge

The execution layer that gives ClaudeAY the ability to act on the world —
run code, manage git, deploy to production servers, read and write files.

---

## 1. Overview

The MCP bridge is the physical hands of the ClaudeAY system. It sits between
the AI (Claude or Gemini) and the local filesystem, git repositories, and
production servers. Every action ClaudeAY takes in the world flows through
one of the five wire modules — all enforcing the same blocklist, sandbox, and
audit discipline.

The bridge serves two AI planes simultaneously:

- **MCP plane**: Claude Code connects via MCP protocol. Tools are called
  directly from Claude's context window over stdio + WebSocket.
- **Gemini plane**: Antigravity connects via `ay_client.py` function calling.
  Same wire modules, different entry point.

Both planes share the same safety layer. One blocklist, one sandbox, one audit trail.

---

## 2. Architecture — Two Planes

```
┌──────────────────────────────────────────────────────────────────┐
│                        claude-mcp-bridge                          │
│                                                                    │
│  ┌─────────────────────────────┐  ┌───────────────────────────┐  │
│  │  MCP PLANE                  │  │  GEMINI PLANE              │  │
│  │  mcp_server/server.py       │  │  ay_client.py             │  │
│  │  WebSocket :9001            │  │  send_mandate()           │  │
│  │  10 MCP tools               │  │  4 Gemini tools           │  │
│  └─────────────┬───────────────┘  └────────────┬──────────────┘  │
│                │                               │                   │
│                └──────────────┬────────────────┘                  │
│                               ▼                                   │
│              ┌─────────────────────────────────┐                  │
│              │  WIRE MODULES (shared)           │                  │
│              │  shell_wire.py      (Phase 1)    │                  │
│              │  git_wire.py        (Phase 2)    │                  │
│              │  ssh_wire.py        (Phase 3)    │                  │
│              │  fs_wire.py         (Phase 4)    │                  │
│              │  playwright_wire.py (Phase 6)    │                  │
│              └─────────────────────────────────┘                  │
└──────────────────────────────────────────────────────────────────┘
```

**MCP plane**: Claude calls tools via the MCP protocol. `mcp_server/server.py`
is the stdio server that registers 11 tools and 2 resources. The WebSocket
listener on port 9001 receives telemetry events from the Chrome extension.

**Gemini plane**: `ay_client.py` runs a Gemini 2.5 Pro function-calling loop.
Gemini decides which tool to invoke; `ay_client.py` dispatches the call to the
corresponding wire module and feeds the result back.

---

## 3. Entry Points

| File | Command | Purpose |
|---|---|---|
| `mcp_server/server.py` | `python claude-mcp-bridge/mcp_server/server.py` | Start MCP server (port 9001 WebSocket + stdio) |
| `loop_ui.py` | `python claude-mcp-bridge/loop_ui.py` | Terminal REPL — starts auto_trigger + autonomy_trigger daemons |
| `claudeay_ui_server.py` | `python claude-mcp-bridge/claudeay_ui_server.py` | Web UI bridge (port 9002) — start manually when needed |
| `_smoke_test.py` | `python claude-mcp-bridge/_smoke_test.py` | Validate all wires after any change |

`loop_ui.py` is the primary daily entry point. It starts the two background
daemons (`auto_trigger` at 30s, `autonomy_trigger` at 60s) and then opens
the interactive REPL.

---

## 4. Wire Modules — Phases 1–5

### Phase 1 — Shell Wire (`shell_wire.py`)

Safe, audited local shell execution. Serves both the MCP `execute_shell` tool
and the Gemini `execute_local_shell` function. All commands pass through a
hard regex blocklist before any subprocess is spawned — destructive OS commands
(rm -rf, format, dd) are refused before reaching the OS. CWD is sandboxed to
`SHELL_WIRE_ALLOWED_ROOTS`. stdout/stderr are streamed live to
`logs/shell_wire_live.log` via threads so long-running commands can be polled
via `get_shell_log`.

**Note**: git commands are blocked in shell_wire. Use git_wire for all git work.

### Phase 2 — Git Wire (`git_wire.py`)

Wraps common git operations with the shell_wire safety model. Three built-in
safety patches: (1) shell_wire blocks raw "git" commands, forcing all git work
through this module; (2) per-repo `asyncio.Lock` prevents two autonomous tasks
from mutating the same repo simultaneously; (3) push/pull network failures
return exit_code 502 so callers distinguish "blocked" from "unreachable" from
"command failed".

Supported operations: status, log, diff, add, commit, push, pull, branch,
reset_file, stash. Force-push, reset --hard, and pushes to `prod`/`production`
branches are permanently blocked.

### Phase 3 — SSH Wire (`ssh_wire.py`)

Remote shell execution over SSH via paramiko. Three built-in patches:
(1) host allowlist — only IPs in `APPROVED_HOSTS` are reachable (currently
104.248.233.220 and 68.183.30.128 — hardcoded, not configurable via env);
(2) per-host `asyncio.Lock` prevents simultaneous SSH sessions to the same
server; (3) paramiko exceptions, socket errors, and timeouts return exit_code
502 ("Gateway Unreachable").

### Phase 4 — File System Wire (`fs_wire.py`)

Safe local file operations. Path sandbox shares `SHELL_WIRE_ALLOWED_ROOTS`
as the single source of truth. Deletes blocked for `.env`, `.db`/`.sqlite`,
and `.git`. Writes blocked for `deploy_maf.py` and `deploy_erp.py` (pipeline
artifacts — must be edited via Claude Code directly). Size limits prevent OOM
on large reads/writes.

### Phase 6 — Playwright Wire (`playwright_wire.py`)

Headless Chromium browser automation. ClaudeAY can open URLs, click, fill forms,
screenshot pages, extract console errors and failed network requests, run
JavaScript expressions, and extract actual computed CSS property values.

The `get_computed_style` operation implements the Strict UI Validation Doctrine:
verify real CSS values (e.g. `backdropFilter`, `display`, `color`) instead of
asserting DOM class names that may be purged by Tailwind/Vite.

Sessions are keyed by UUID, persist for 300 seconds, and are fully cleaned up
on process exit via atexit and SIGTERM/SIGINT handlers — no Chromium zombies.

**Linux install note**: headless Ubuntu VPS requires:
```
pip install playwright
playwright install chromium
playwright install-deps chromium   # installs OS-level libs: libnss3, libgbm1, etc.
```

---

### Phase 5 — Autonomy Trigger (`autonomy_trigger.py`)

Proactive self-healing loop. Monitors two condition types:

- **C1 TELEMETRY_CRITICAL**: same critical browser error persists across 3
  consecutive 60s polling windows
- **C2 PROD_HEALTH_FAIL**: remote service health probe returns non-200 for 3
  consecutive polls (independent per host, checked via SSH to loopback)

When a condition fires, calls `ay_client.send_mandate()` directly — Gemini
plane only, no human approval. Circuit breaker: max 3 triggers/hour per
condition, 600s cooldown between triggers.

---

## 5. MCP Tools Reference

| Tool | Wire | Key safety rule | Audit log |
|---|---|---|---|
| `execute_shell` | shell_wire | Regex blocklist + CWD sandbox | shell_wire_audit.jsonl |
| `get_shell_log` | shell_wire | Read-only — returns live log | — |
| `git_operation` | git_wire | No force-push, no reset-hard | git_wire_audit.jsonl |
| `execute_remote_shell` | ssh_wire | Approved hosts only (2 IPs) | ssh_wire_audit.jsonl |
| `file_operation` | fs_wire | No .env/.db delete, no deploy write | fs_wire_audit.jsonl |
| `get_autonomy_log` | — | Read-only — returns JSONL entries | autonomy_events.jsonl |
| `playwright_operation` | playwright_wire | URL allowlist + eval blocklist | playwright_wire_audit.jsonl |
| `get_telemetry_summary` | — | Reads in-memory telemetry buffer | telemetry.jsonl |
| `clear_telemetry` | — | Clears in-memory buffer | — |
| `get_rules` | — | Read-only CLAUDE_RULES.md | — |
| `update_rules` | — | Append-only to CLAUDE_RULES.md | — |

**MCP Resources:**

| URI | Description |
|---|---|
| `telemetry://live` | Rolling buffer of console errors, network failures, page crashes |
| `rules://claude` | CLAUDE_RULES.md content injected into every session |

---

## 6. Gemini Tools Reference

| Function in ay_client.py | Wire | Maps to MCP tool |
|---|---|---|
| `execute_local_shell(command)` | shell_wire | `execute_shell` |
| `write_local_file(relative_path, content)` | fs_wire | `file_operation` (write) |
| `read_local_file(relative_path)` | fs_wire | `file_operation` (read) |
| `execute_remote_shell(host_ip, command, timeout)` | ssh_wire | `execute_remote_shell` |
| `playwright_operation(operation, ...)` | playwright_wire | `playwright_operation` |

All four functions preserve the `STDOUT:\n...\nSTDERR:\n...` return format
expected by Gemini function-calling callers.

---

## 7. Safety Model

**Blocklist doctrine**: anything not explicitly blocked runs. The blocklist is
a regex deny-list of known-destructive patterns. No allowlist — all legitimate
dev workflows pass through without configuration.

**CWD sandbox**: all working directories must resolve within paths listed in
`SHELL_WIRE_ALLOWED_ROOTS` (semicolon-separated in `.env`, defaults to MAF
root + TEMP). Any path resolution outside the sandbox is blocked before
execution.

**IP allowlist**: SSH wire only accepts connections to hardcoded approved hosts.
Approved IPs are not configurable via `.env` — changing the allowlist requires
a code change and commit to prevent accidental production access to wrong hosts.
Both `ssh_wire.py` and `mcp_server/server.py` maintain this list — update both.

**Circuit breaker**: the autonomy trigger disables itself after 3 autonomy fires
within any 1-hour window per condition. Circuit stays open until process restart.
Prevents runaway healing loops.

**Deploy scripts protected**: `deploy_maf.py` and `deploy_erp.py` cannot be
overwritten via `file_operation`. These are pipeline artifacts — edits must
go through Claude Code directly (where intent is visible) not autonomous writes.

---

## 8. Audit Logs

All logs written to `claude-mcp-bridge/logs/`:

| Log file | Written by | Contents |
|---|---|---|
| `shell_wire_audit.jsonl` | shell_wire | Every shell execution: command, cwd, exit_code, duration, blocked |
| `shell_wire_live.log` | shell_wire | Live streaming stdout/stderr from most recent execution |
| `git_wire_audit.jsonl` | git_wire | Every git operation: operation, args, result, exit_code |
| `ssh_wire_audit.jsonl` | ssh_wire | Every remote execution: host_ip, command, exit_code, duration |
| `fs_wire_audit.jsonl` | fs_wire | Every file operation: op, path, exit_code, bytes |
| `autonomy_events.jsonl` | autonomy_trigger | Every autonomy trigger event: condition, mandate, result |
| `playwright_wire_audit.jsonl` | playwright_wire | Every browser operation: op, session_id, exit_code, duration |
| `telemetry.jsonl` | mcp_server/server.py | Chrome extension events: console_error, page_error, request_failed |
| `loop_history.jsonl` | loop_engine | Every mandate sent/received by the autonomous loop |
| `dispatched_prompts.jsonl` | dispatcher | Every prompt built: instruction, length, timestamp |
| `seen_errors.jsonl` | auto_trigger | Dedup ledger — error signatures already diagnosed |

---

## 9. Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SHELL_WIRE_ALLOWED_ROOTS` | MAF root + TEMP | Semicolon-separated allowed CWD paths for shell/fs wires |
| `SHELL_WIRE_TIMEOUT` | 120 | Max execution seconds, clamped to [1, 120] |
| `AUTONOMY_DRY_RUN` | false | Set `true` to log trigger events without firing send_mandate |
| `AUTONOMY_TRIGGER_INTERVAL` | 60 | Autonomy trigger poll interval in seconds |
| `SSH_KEY_PATH` | `~/.ssh/id_rsa` | Path to SSH private key for ssh_wire |
| `GEMINI_API_KEY` | (required) | Gemini API key for ay_client and intent_router |
| `FIRECRAWL_API_KEY` | (optional) | Firecrawl API key for cio_crawler |

---

## 10. Adding a New Wire (Phase 6+)

Follow these steps exactly. Wire + docs must land in the same commit.

**Step 1 — Create `claude-mcp-bridge/newname_wire.py`**

Follow `shell_wire.py` pattern exactly. Implement:
- `execute(...)` — synchronous wrapper
- `execute_async(...)` — async version using `asyncio.Lock`
- `_blocked(command)` — blocklist check, returns `(True, reason)` or `(False, "")`
- `_audit(...)` — writes structured JSON to `logs/newname_wire_audit.jsonl`

Response envelope must include all fields:
```python
{
    "blocked": bool,
    "block_reason": str,
    "timed_out": bool,
    "exit_code": int,
    "stdout": str,
    "stderr": str,
    "duration_ms": int,
}
```

Network failures must return `exit_code=502`, not raise exceptions.

**Step 2 — Register in `mcp_server/server.py`**

```python
from newname_wire import execute_async as _newname_execute_async

# In list_tools():
Tool(name="newname_operation", description="...", inputSchema={...})

# In call_tool():
if name == "newname_operation":
    result = await _newname_execute_async(...)
    return [TextContent(type="text", text=json.dumps(result, indent=2))]
```

**Step 3 — Add to `ay_client.py`**

Add a sync wrapper function and register it in `send_mandate()` tools list
and the function dispatcher.

**Step 4 — Add to `.env`**

Document any new environment variables with sensible defaults.

**Step 5 — Write smoke test**

Add a `__main__` block or extend `_smoke_test.py` covering:
- Happy path
- Blocklist rejection
- Sandbox rejection
- Network failure → 502

**Step 6 — Update documentation (same commit)**

- `AGENTS.md §2`: add Phase section with full safety model
- `AGENTS.md §1`: add MCP tool to ClaudeAY tools table
- `claude-mcp-bridge/README.md`: add to Wire Modules section and MCP Tools Reference
- `claude-mcp-bridge/rules/CLAUDE_RULES.md`: append wire usage rules

**Step 7 — Commit with wire + docs together**

```
git add claude-mcp-bridge/newname_wire.py mcp_server/server.py ay_client.py \
        AGENTS.md claude-mcp-bridge/README.md claude-mcp-bridge/rules/CLAUDE_RULES.md
git commit -m "feat(bridge): Phase 6 — newname wire + docs"
```
