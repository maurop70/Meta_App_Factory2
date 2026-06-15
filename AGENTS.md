# AGENTS.md — Antigravity Multi-Agent Rule Inheritance
# =====================================================
# Version: 2.0.0 (v2.0.0 Standard)
# Created: 2026-03-28
# Revised: 2026-06-14
# Authority: This file is the PRIMARY configuration for all Antigravity agents.
# Supersedes: AGENTS.md v1.x (2026-03-28)
# Format: §0 Constraints → §1 ClaudeAY → §2 Wire System → §3 Agents → §4 Infrastructure → §5 Maintenance Rules → §6 Deprecated

---

# ═══════════════════════════════════════════════════════
# §0  PERMANENT ARCHITECTURAL CONSTRAINTS (OVERRIDE ALL)
# ═══════════════════════════════════════════════════════

**1. Strict No-Write Protocol:**
You will operate exclusively in Proposal Mode. You must not execute file modifications, delete directories, or alter states without explicit, step-by-step authorization from the Architect.

**2. Immutable Infrastructure:**
The system must remain a 100% native Python stack. No hybrid cloud dependencies or n8n orchestrations are permitted. (This permanently supersedes all legacy n8n and MCP protocols below).

**3. Model Routing Standardization:**
All API calls and system infrastructure patches must strictly route to standard model iterations (`gemini-2.5-pro` or `gemini-2.5-flash`). Do not use newer, non-standard iterations that cause 404 routing errors.

**4. Mandatory Pre-Execution Audits:**
Before proposing any code, you must independently audit your own output for hallucinations and cross-examine it against the actual repository state.

**5. Senior Architect Mandate (RULE SA-1 — binding):**
Antigravity acts as the **Senior Architect** by default in every session — full text in
`.agent/rules/senior_architect.md`, which this constraint binds with §0 authority.
Non-negotiable core, restated here so it survives any load path:
- Every substantive response BEGINS with the ritual header:
  `🏛️ ARCHITECT SA-1 · <task>` + `VERDICT / EVIDENCE / RISKS / RECOMMENDATIONS` lines.
  A VERDICT without inspected EVIDENCE is invalid. A missing header = "SA-1 drift detected":
  stop, re-read the rule, re-issue. After context compaction, re-read the rule before acting.
- Approved plans end with `ARCH-APPROVED: <scope>`; Claude Code must not execute without it.
  Post-execution audits close with `ARCH-VERIFIED: <scope>` or `ARCH-REOPENED: <defect>`.
- Only the user can suspend the mandate ("execute directly" / "skip review" / "no architect"),
  for the current task only; the mode resumes automatically on the next task.
- If the user writes "rule check", re-read `.agent/rules/senior_architect.md` and confirm compliance.

---

# ═══════════════════════════════════════════════════════
# §1  CLAUDEAY: THE PRIMARY AI OPERATOR
# ═══════════════════════════════════════════════════════

ClaudeAY is the product. Everything else is infrastructure that serves it.

## What it is

The primary autonomous AI operator inside MAF. Accepts natural language mandates
from the user and executes end-to-end: diagnose → fix → commit → deploy → verify.
No human in the loop once a mandate is issued (except on Section 11 triggers).

## Interfaces

| Interface | Location | Port |
|---|---|---|
| Builder Chat UI | factory_ui/ | localhost:5173 |
| Factory API (ClaudeAY endpoints) | api.py | localhost:5000 |
| MCP bridge | mcp_server/server.py | localhost:9001 (WebSocket + stdio) |
| ClaudeAY Web UI | claudeay_ui_server.py | localhost:9002 |
| Loop server | api.py | localhost:5050 (proxied by claudeay_ui_server) |

## Session Flows

### User-initiated flow (primary path)
```
User mandate (Builder Chat or loop_ui.py terminal)
  → intent_router.py
      Gemini 2.5 Flash classifier → CLAUDE or GEMINI engine
      Keyword fallback when LLM unavailable
      Default: GEMINI when ambiguous
  → dispatcher/dispatcher.py
      Injects CLAUDE_RULES.md + telemetry + code context
      Returns tagged-block prompt (<SYSTEM_RULES><TELEMETRY><CODE_CONTEXT><USER_REQUEST>)
      Logs to logs/dispatched_prompts.jsonl
  → loop_engine.py (AutonomousLoop)
      Section 11 check → halts if mandate touches deploy/delete/business-logic
      Sends mandate to executor
      Evaluates ledger → COMPLETE / ITERATE / ERROR / ESCALATE
  → claude_code_client.py (primary executor)
      Runs: claude -p <mandate> --dangerously-skip-permissions
      Fallback: ay_client.py when Claude quota exhausted or CLI unavailable
  → ledger_evaluator.py
      COMPLETE  → loop ends
      ITERATE   → follow-up mandate generated, loop continues
      ERROR     → alerts Phantom QA at port 5030, loop ends
      ESCALATE  → waits for operator approval (web: _approval_event, terminal: input())
```

### Telemetry-triggered flow (human approval required)
```
auto_trigger.py (daemon, polls every 30s)
  → reads logs/telemetry.jsonl for new critical errors (local URLs only)
  → deduplicates via logs/seen_errors.jsonl
  → POST /api/claudeay/diagnose (localhost:5000)
      api.py builds diagnosis prompt via dispatcher.build_prompt()
      ay_client.send_mandate() → Gemini generates fix proposal
      Proposal stored in pending_fixes dict with fix_id
      Broadcasts claudeay_fix_proposal event to Builder Chat via SSE
  → Operator sees proposal in Builder Chat
  → POST /api/claudeay/approve {fix_id, action: "approve"|"dismiss"}
      approve → ay_client.send_mandate(fix_mandate) in background thread
      dismiss → broadcast claudeay_fix_dismissed event
```

### Autonomous self-healing flow (NO human approval)
```
autonomy_trigger.py (daemon, polls every 60s)
  → evaluates C1 and C2 conditions
  → C1 TELEMETRY_CRITICAL: same browser error persists 3 consecutive 60s windows
  → C2 PROD_HEALTH_FAIL: SSH loopback health probe fails 3× for a host
  → ay_client.send_mandate() ← Gemini plane ONLY (not claude_code_client)
      ClaudeAY executes: diagnose → fix → commit → deploy → verify
  → Audit logged to logs/autonomy_events.jsonl
```

**CRITICAL DISTINCTION:**
- `auto_trigger` proposes fixes, **human must approve** at `/api/claudeay/approve`
- `autonomy_trigger` fires and executes **with no human approval required**
- These are two separate systems. Do not confuse them.

## MCP Tools Available to ClaudeAY (11 total)

| Tool | Phase | Description |
|---|---|---|
| `execute_shell` | 1 | Local shell commands via shell_wire |
| `get_shell_log` | 1 | Live output from most recent shell execution |
| `git_operation` | 2 | Audited git: status/log/diff/add/commit/push/pull/branch/reset_file/stash |
| `execute_remote_shell` | 3 | SSH to approved production hosts only |
| `file_operation` | 4 | Read/write/append/delete/list/mkdir/move local files |
| `get_autonomy_log` | 5 | Last N entries from logs/autonomy_events.jsonl |
| `playwright_operation` | 6 | Headless Chromium: navigate, screenshot, click, fill, get_computed_style, etc. |
| `get_telemetry_summary` | — | Browser errors from Chrome extension |
| `clear_telemetry` | — | Clears telemetry buffer |
| `get_rules` | — | Returns CLAUDE_RULES.md content |
| `update_rules` | — | Appends new rule section to CLAUDE_RULES.md |

## Gemini Plane Tools (ay_client.py)

| Function | Delegates to |
|---|---|
| `execute_local_shell` | shell_wire |
| `write_local_file` | fs_wire |
| `read_local_file` | fs_wire |
| `execute_remote_shell` | ssh_wire |
| `playwright_operation` | playwright_wire |

## Known Issues (2026-06-07)

- **Builder Chat ERR_NETWORK (6 ERR)**: MCP bridge connection issue. ClaudeAY receives
  input but MCP tools not responding. Workaround: Claude Code as execution layer
  directly until resolved.
- **Autonomy trigger Gemini-only**: The autonomy trigger uses `ay_client.send_mandate()`
  exclusively. If Gemini API is unavailable, autonomous C1/C2 healing stops.
  MCP tools are not accessible during autonomous sessions.

---

# ═══════════════════════════════════════════════════════
# §2  WIRE SYSTEM: CLAUDEAY EXECUTION LAYER
# ═══════════════════════════════════════════════════════

The wire system gives ClaudeAY hands. Built in 5 phases. All wires share the
same safety doctrine:

- **Blocklist-only**: anything not explicitly blocked runs
- **CWD sandbox**: working directory must be within `SHELL_WIRE_ALLOWED_ROOTS`
- **Structured JSON envelope**: every wire returns `{blocked, block_reason, timed_out, exit_code, stdout, stderr}`
- **Audit log per wire**: `logs/<name>_wire_audit.jsonl`
- **Network failures → exit_code 502**: never silent hang
- **Per-resource concurrency lock**: `asyncio.Lock` per repo/host

Both planes share the same wire modules. One blocklist, one sandbox.

---

## Phase 1 — Shell Wire (`shell_wire.py`)

ClaudeAY can run local shell commands.

| | |
|---|---|
| **MCP tools** | `execute_shell`, `get_shell_log` |
| **Gemini tools** | `execute_local_shell` |
| **Timeout** | configurable, clamped to [1, 120]s |
| **Sandbox** | CWD must be within `SHELL_WIRE_ALLOWED_ROOTS` |
| **Blocklist** | 10-rule regex — destructive OS commands refused before subprocess spawns |
| **Live output** | streams to `logs/shell_wire_live.log` via threads |
| **Audit** | `logs/shell_wire_audit.jsonl` |

**Note**: git commands are blocked in shell_wire by design. All git work must
use git_wire (`git_operation` tool).

---

## Phase 2 — Git Wire (`git_wire.py`)

ClaudeAY can commit, push, pull, branch, and stash.

| | |
|---|---|
| **MCP tool** | `git_operation` |
| **Operations** | status, log, diff, add, commit, push, pull, branch, reset_file, stash |
| **Blocked** | `--force`, `reset --hard`, push to `prod` or `production` branch |
| **Network** | push/pull failures → exit_code 502, never hangs |
| **Concurrency** | per-repo `asyncio.Lock` prevents `index.lock` collisions |
| **Audit** | `logs/git_wire_audit.jsonl` |

---

## Phase 3 — SSH Wire (`ssh_wire.py`)

ClaudeAY can SSH into approved production servers.

| | |
|---|---|
| **MCP tool** | `execute_remote_shell` |
| **Gemini tool** | `execute_remote_shell` |
| **Approved hosts** | `104.248.233.220` (maf-production-nyc1), `68.183.30.128` (mwo-production-nyc1) |
| **Auth** | root user, key-based only (SSH_KEY_PATH from .env) |
| **Remote blocklist** | `rm -rf /`, `reboot`, `shutdown`, `mkfs`, `dd if=/dev/zero` |
| **Network** | paramiko exceptions → exit_code 502 |
| **Concurrency** | per-host `asyncio.Lock` |
| **Audit** | `logs/ssh_wire_audit.jsonl` |

**Important**: Approved hosts are hardcoded in both `ssh_wire.py` and
`mcp_server/server.py`. If a new droplet is added, update both files.

---

## Phase 4 — File System Wire (`fs_wire.py`)

ClaudeAY can read, write, append, delete, list, move local files.

| | |
|---|---|
| **MCP tool** | `file_operation` |
| **Gemini tools** | `write_local_file`, `read_local_file` |
| **Operations** | read, write, append, delete, list, exists, mkdir, move |
| **Path sandbox** | all resolved paths must be within `SHELL_WIRE_ALLOWED_ROOTS` |
| **System paths** | `/etc/`, `/boot/`, `/bin/`, `/sbin/`, `C:\Windows` — blocked for all ops |
| **Delete blocked** | `.env` files, `.db`/`.sqlite` databases, `.git` dir/contents |
| **Write blocked** | `deploy_maf.py`, `deploy_erp.py` (pipeline artifacts) |
| **Size limits** | read ≤ 2 MB, write/append ≤ 5 MB, list ≤ 500 entries |
| **Audit** | `logs/fs_wire_audit.jsonl` |

---

## Phase 5 — Autonomy Trigger (`autonomy_trigger.py`)

ClaudeAY watches production and self-heals without being asked.

| | |
|---|---|
| **MCP tool** | `get_autonomy_log` |
| **Daemon** | Yes — started by `loop_ui.py` at startup |
| **Executor** | `ay_client.send_mandate()` — **Gemini plane ONLY** |
| **Poll interval** | 60 seconds |

**Conditions:**

| Condition | Trigger | Description |
|---|---|---|
| C1 TELEMETRY_CRITICAL | 3 consecutive windows | Same browser error in 3+ consecutive 60s polls |
| C2 PROD_HEALTH_FAIL | 3 consecutive failures | Health probe fails 3× per host (independent per host) |

**Health probe endpoints (checked via SSH to loopback):**

| Host | Health URL |
|---|---|
| maf-production-nyc1 (104.248.233.220) | `http://127.0.0.1:8000/api/health` |
| mwo-production-nyc1 (68.183.30.128) | `http://127.0.0.1:8000/system/directive` |

**Concurrency safety:**

- 10-minute cooldown between consecutive triggers per condition
- Max 3 triggers/hour per condition → circuit breaker opens
- Active session lock prevents re-entry while `send_mandate()` runs
- Circuit stays open until process restart (operator must review log)

**Dry run:** `AUTONOMY_DRY_RUN=true` logs what would fire without executing.

**Audit:** `logs/autonomy_events.jsonl` (readable via `get_autonomy_log` MCP tool)

---

## Phase 6 — Playwright Wire (`playwright_wire.py`)

ClaudeAY can open URLs, click, fill forms, screenshot, extract console errors,
and validate computed CSS properties in headless Chromium.

| | |
|---|---|
| **MCP tool** | `playwright_operation` |
| **Gemini tool** | `playwright_operation` |
| **Operations** | navigate, screenshot, click, fill, select, get_text, get_console, get_network, wait, evaluate, get_computed_style, close |
| **URL safety** | Allowlist-only: localhost, 127.0.0.1, 68.183.30.128, 104.248.233.220, common dev ports |
| **Script safety** | Evaluate blocklist: document.cookie, localStorage, sessionStorage, fetch(, XMLHttpRequest, eval( |
| **Session TTL** | 300 seconds — auto-close on expiry |
| **Concurrency** | per-session threading.Lock prevents concurrent page mutations |
| **Zombie prevention** | atexit + SIGTERM/SIGINT handlers — every Chromium process tracked and killed on shutdown |
| **Audit** | `logs/playwright_wire_audit.jsonl` |
| **Screenshots** | saved to `logs/playwright_screenshots/<timestamp>_<name>.png` |
| **Linux note** | Requires `playwright install-deps chromium` on headless Ubuntu VPS |

**Strict UI Validation Doctrine**: always use `get_computed_style` to verify
actual CSS values — never assert UI correctness by DOM class name alone.

---

# ═══════════════════════════════════════════════════════
# §3  ACTIVE AGENTS
# ═══════════════════════════════════════════════════════

---

## loop_engine.py

| | |
|---|---|
| **Role** | Orchestrator. Receives intent → builds mandate → sends to executor → evaluates ledger → iterates or halts |
| **Primary executor** | `claude_code_client.py` |
| **Fallback executor** | `ay_client.py` |
| **Log** | `logs/loop_history.jsonl` |
| **Daemon** | No |

**Known architectural gap**: No maximum iteration cap. `ledger_evaluator.py` can
return COMPLETE at confidence 0.3 on ambiguous ledgers, potentially causing
premature loop termination. Conversely, repeated ITERATE signals can cause
indefinite looping. Recommended fix: add `MAX_ITERATIONS = 10` guard to
`AutonomousLoop.run()`. Not yet implemented.

---

## intent_router.py

| | |
|---|---|
| **Role** | Dual-engine classifier. Routes Builder Chat queries to CLAUDE (code/debug/build/ERP) or GEMINI (strategy/brand/finance/C-Suite) |
| **Primary** | Gemini 2.5 Flash LLM classification (~300ms) |
| **Fallback** | Keyword scoring when LLM unavailable |
| **Default** | GEMINI when ambiguous — preserves existing MAF behaviour |
| **Bypass** | STRUCTURAL_MANDATE and /genesis paths skip this entirely |
| **Daemon** | No |

---

## ledger_evaluator.py

| | |
|---|---|
| **Role** | Evaluates loop execution results |
| **Decision priority** | ESCALATE > ERROR > COMPLETE > ITERATE |
| **Returns** | COMPLETE / ITERATE / ERROR / ESCALATE with confidence score |
| **Ambiguous ledger** | Returns COMPLETE at confidence 0.3 — low signal, not silence |
| **Daemon** | No |

---

## dispatcher/dispatcher.py

| | |
|---|---|
| **Role** | Prompt builder. Injects CLAUDE_RULES.md + telemetry + code context + user request into tagged XML blocks |
| **Methods** | `build_prompt()` — general use; `build_autofix_prompt()` — used by auto_trigger diagnose path |
| **Log** | `logs/dispatched_prompts.jsonl` |
| **Daemon** | No |

---

## ay_client.py

| | |
|---|---|
| **Role** | Gemini 2.5 Pro execution client. Runs function-calling loop with 5-iteration circuit breaker. Routes tool calls to wire modules. |
| **Model** | `gemini-2.5-pro` |
| **Circuit breaker** | Halts after 5 tool iterations — prevents hallucination loops |
| **Plane** | Gemini |
| **Daemon** | No |

---

## claude_code_client.py

| | |
|---|---|
| **Role** | Claude Code CLI primary executor |
| **Command** | `claude -p <mandate> --dangerously-skip-permissions` |
| **Fallback** | `ay_client.py` on quota exhaustion, rate-limit, or CLI not found |
| **Plane** | Claude |
| **Daemon** | No |

---

## auto_trigger.py

| | |
|---|---|
| **Role** | Telemetry watcher. Polls `logs/telemetry.jsonl` every 30s. New critical errors → `POST /api/claudeay/diagnose` (port 5000). Human must approve. |
| **Filter** | Local URLs only (localhost, 127.0.0.1, ::1) |
| **Dedup** | `logs/seen_errors.jsonl` |
| **Daemon** | Yes — started by `loop_ui.py` |

---

## native_watchdog.py (Phase 7: Aether Native Watchdog)

| | |
|---|---|
| **Role** | Process monitor. Pings 10 local TCP ports every 30s. Auto-restarts services at 3 consecutive failures. Memory guard kills node processes >500MB. |
| **Ports monitored** | 5000 (root_api), 5009 (sentinel_bridge), 5020 (cmo_agent), 5030 (phantom_qa), 5050 (master_architect), 5070 (c_suite/cfo), 5080 (clo_agent), 5090 (cio_agent), 5100 (operator_agent/ghost_operator) |
| **Restart backoff** | [0, 5, 15, 30]s |
| **Quarantine** | After 5 consecutive restart failures, service quarantined (no further attempts) |
| **Daemon** | Yes — started by `api.py` at module load via `get_native_watchdog().start_background_loop()` |

---

## mcp_server/server.py

| | |
|---|---|
| **Role** | MCP server entry point. WebSocket on port 9001 receives Chrome extension telemetry. MCP stdio server exposes 10 tools and 2 resources. |
| **Resources** | `telemetry://live` (rolling buffer), `rules://claude` (CLAUDE_RULES.md) |
| **Daemon** | No — standalone entry point, run separately |

---

## claudeay_ui_server.py

| | |
|---|---|
| **Role** | FastAPI web UI on port 9002. Bridges browser to loop engine and Antigravity API. Proxies loop start/status/approve to port 5050. |
| **Startup** | Clears stale telemetry log on startup |
| **Daemon** | No — start manually: `python claude-mcp-bridge/claudeay_ui_server.py` |

---

## loop_ui.py

| | |
|---|---|
| **Role** | Terminal REPL entry point. Starts `auto_trigger` (30s) and `autonomy_trigger` (60s) as daemon threads. Interactive mandate interface. |
| **Daemon** | No — is the entry point |

---

## _smoke_test.py

| | |
|---|---|
| **Role** | Integration test harness for the entire wire bridge. Tests all wire modules: shell_wire, git_wire, ssh_wire, fs_wire. Run manually to validate bridge health after any wire change. |
| **Command** | `python claude-mcp-bridge/_smoke_test.py` |
| **Daemon** | No |

---

## app_generator.py (Master Architect)

| | |
|---|---|
| **Role** | Factory engine. Generates child apps from templates with V3 DNA (healed_post, _v3_preflight, StateManager). Must be run before scaffolding any new agent/app. |
| **Daemon** | No |

---

## operator_agent.py (The Operator)

| | |
|---|---|
| **Role** | FastAPI service on port 5100. Executes physical actions by constructing native JSON payloads to internal REST endpoints. API-First Shadow Protocol — no UI automation. |
| **Daemon** | Yes (FastAPI service) |

---

## Builder Chat Self-Healing Build Pipeline (added 2026-06-14)

Turns a plain-language Builder Chat request into a verified, runnable app with no
human in the loop: **generate → run → observe → fix → verify**.

| Stage | Component | Behavior |
|---|---|---|
| **Route** | factory_stream.py | Explicit Build-vs-Venture routing (mode + `/build`, `/venture`, `/csuite`). BUILDER path no longer runs the Socratic gate. |
| **Generate** | Master Architect | Hardened blueprint JSON: `max_output_tokens=32768`, temperature-0.0 retry fallback on `JSONDecodeError`. |
| **Actuate** | `Master_Architect_Elite_Logic/ipc_bridge.py` | `start_ipc_bridge(owner_port)` claims each blueprint via atomic `os.rename` (single owner across the shared-queue fleet). VENTURE/SRE blueprint producers untouched. Output → `Master_Architect_Elite_Logic/generated_builds/<app-slug>/`. |
| **Verify** | `factory_ui/verify_app.mjs` | Headless Chromium render; blocks non-local egress; reports console / page / network errors + screenshot as JSON. |
| **Heal** | `Master_Architect_Elite_Logic/server.py` | verify→heal loop: feeds errors back to Gemini for **up to 3 repair passes**. `✅ Build Complete` is gated on a clean render. Verifier failures **fail-open** (build still reported) so a verifier hiccup can't block builds. |
| **Serve** | server.py + factory_ui | Built apps served over HTTP; in-chat **Open app** button on completion; **Built Apps** sidebar links to the builds gallery. |

- **Gallery**: `Master_Architect_Elite_Logic/generated_builds/` (see its `README.md`).
- **Demo apps built by this pipeline**: `maf-blueprint-inspector` (validate blueprint/JSON payloads),
  `maf-token-cost-estimator` (LLM token + cost estimate), `maf-uuid-generator` (UUID v4).
- **Cost tracking**: LLM call sites are instrumented for centralized token cost-tracking across MAF.
- **Test**: `scratch/test_self_healing.py`; `ReviewRequest.test_inject_broken` (gated by `ALLOW_TEST_INJECTION`) for deterministic verify→heal tests.

---

## cio_crawler.py

| | |
|---|---|
| **Role** | Cascade web crawler. Firecrawl → DuckDuckGo → httpx fallback. Accepts `url` (direct page scrape) or `query` (search). |
| **Daemon** | No |

---

## Adv_Autonomous_Agent/nerve_center_v2.py (Ecosystem Overwatch Sentinel)

| | |
|---|---|
| **Role** | Ecosystem monitoring loop. Absolute data integrity and system oversight. Loop threshold snap-back, forbidden from autonomous bypass in Financial or Security categories. |
| **Daemon** | Yes |

---

# ═══════════════════════════════════════════════════════
# §4  INFRASTRUCTURE
# ═══════════════════════════════════════════════════════

## Production Droplets

### maf-production-nyc1 — 104.248.233.220
- **Services**: core-engine (uvicorn :8000), phantom-qa (:5030)
- **Nginx**: port 80, proxies `/api/` → :8000
- **Deploy script**: `python deploy_maf.py` (from MAF root)
- **Health check**: `GET http://104.248.233.220/api/health`

### mwo-production-nyc1 — 68.183.30.128
- **Services**: erp-backend (uvicorn :8000), erp-auth (:9000), nginx (port 80)
- **Deploy script**: `python deploy_erp.py` (from ERP dir: `Meta_App_Factory/ERP/`)
- **Health check**: `curl http://localhost/` → expect 200

## Repositories

| Repo | Remote | Local path |
|---|---|---|
| MAF | github.com/maurop70/Meta_App_Factory2 | `C:\Dev\Antigravity_AI_Agents\Meta_App_Factory` |
| MWO/ERP | same repo, ERP subdirectory | `C:\Dev\Antigravity_AI_Agents\Meta_App_Factory\ERP` |

## Standard Deploy Sequence

ClaudeAY follows this every time, in this order:

```
1. git_operation(status)         — confirm clean or staged
2. git_operation(add, paths=[<specific files>])
3. git_operation(commit, message="<type>(<scope>): <description>")
4. git_operation(push, branch="main")
5. execute_shell("python deploy_maf.py")    ← MAF, cwd: MAF root
   OR
   execute_shell("python deploy_erp.py")    ← MWO, cwd: ERP dir
6. execute_remote_shell — systemctl status <service>
7. execute_remote_shell — curl health endpoint → expect 200
```

## MWO ERP Service Registry (corrected 2026-06-07)

| Service | Status | Port | Note |
|---|---|---|---|
| `erp-backend.service` | ACTIVE | 8000 | Real uvicorn backend |
| `erp-auth.service` | ACTIVE | 9000 | Real auth gateway |
| `nginx.service` | ACTIVE | 80 | Reverse proxy |
| `erp-maintenance-backend.service` | DUMMY | — | Placeholder — do not restart |
| `erp-iam-gateway.service` | DUMMY | — | Placeholder — do not restart |

**Restart command**: `systemctl restart erp-backend.service nginx.service`

## MWO Extraction Paths (corrected 2026-06-07)

`deploy_erp.py` uses `--transform` flags to extract tar contents directly to
the correct directories:

| Archive path | Extracts to |
|---|---|
| `Maintenance_Work_Order/` | `/opt/erp/backend/` |
| `maintenance_frontend/dist/` | `/opt/erp/frontend/` |

---

## QA Lab

| | |
|---|---|
| **UI** | http://104.248.233.220/qa-lab |
| **API routes** | `/api/qa-lab/*` (in `api.py`) |
| **State storage** | `logs/qa_runs/{run_id}.json` (disk-based, multi-worker safe) |
| **App registry** | `claude-mcp-bridge/e2e_app_registry.json` |
| **Reports** | `logs/e2e_reports/` |
| **Screenshots** | `logs/playwright_screenshots/` |

The QA Lab provides a glassmorphic UI for triggering and monitoring automated
end-to-end Playwright test runs against registered apps. All run state is written
to disk (never in-memory) so any Uvicorn worker can serve the SSE stream.

**API surface**:

| Endpoint | Method | Description |
|---|---|---|
| `/api/qa-lab/apps` | GET | List apps from e2e_app_registry.json |
| `/api/qa-lab/run` | POST | Start a new run; returns `run_id` |
| `/api/qa-lab/status/{run_id}` | GET | Current run state |
| `/api/qa-lab/stream/{run_id}` | GET | SSE stream — pings every 15s |
| `/api/qa-lab/escalation/{run_id}` | POST | Record human A/B/C choice |
| `/api/qa-lab/history` | GET | Last 20 runs sorted by created_at |
| `/api/qa-lab/screenshot/{filename}` | GET | Serve screenshot image |

**Frontend components**:
- `factory_ui/src/pages/QALab.jsx` — parent coordinator
- `factory_ui/src/components/qa/ActiveRunStream.jsx` — live test list + progress bar
- `factory_ui/src/components/qa/EscalationOverlay.jsx` — full-screen escalation modal
- `factory_ui/src/components/qa/HistoryLedger.jsx` — past runs table (isolated, self-fetching)

---

# ═══════════════════════════════════════════════════════
# §5  DOCUMENTATION MAINTENANCE RULES
# ═══════════════════════════════════════════════════════

**Documentation is part of every deployment. Not a follow-up. Not later. Same commit.**

### When a new wire is added (Phase 6+):
- Add to §2 with full safety model (blocklist, sandbox, size limits, audit log)
- Add MCP tool to §1 ClaudeAY tools table
- Update `claude-mcp-bridge/README.md` — add to Wire Modules and MCP Tools Reference
- Update `CLAUDE_RULES.md` — append wire usage rules to the Wire System section
- Add smoke test coverage to `_smoke_test.py`

### When a new agent is added:
- Add to §3 with file, role, daemon (yes/no), plane
- Update `claude-mcp-bridge/README.md` if it touches the bridge

### When infrastructure changes (new droplet, service rename, port change):
- Update §4 immediately
- Update `ssh_wire.py` `APPROVED_HOSTS` if new droplet added
- Update `mcp_server/server.py` approved host list (two sources of truth — update both)
- Update `CLAUDE_RULES.md` §9.4 deployment sequence

### When a new app is built into `generated_builds/` (or the build pipeline changes):
- Add the app to the gallery table in `Master_Architect_Elite_Logic/generated_builds/README.md`
- Update the demo-app list + pipeline table in §3 (Builder Chat Self-Healing Build Pipeline)
- These docs feed the **Ecosystem Guide** chat (`factory_stream.py` → `_load_ecosystem_docs`);
  AGENTS.md is ingested in full, so keep it current — stale docs = wrong Guide answers

### Commit discipline:
- Wire + docs must be in the same commit — never ship a wire without its docs
- Commit format: `docs: <scope> — <what changed>`

---

# ═══════════════════════════════════════════════════════
# §6  DEPRECATED (history — do not remove)
# ═══════════════════════════════════════════════════════

**n8n** — permanently banned by §0. All n8n workflows are dead.
Replaced by: wire system (Phases 1–5).

**.agent/workflows/ files** — referenced in v1.x AGENTS.md but never created.
Files: `master-architect.md`, `Aether-Cognitive-Layer.md`,
`Resonance-Socratic-Tutor.md`, `commit-and-push.md`.
Status: REMOVED from active documentation.

**.gemini/GEMINI.md** — referenced in v1.x as legacy fallback. Never created. REMOVED.

**.supervisor/DIRECTIVE.md** — referenced in v1.x as active. Never created. REMOVED.

**CFO Execution Controller** — n8n-based (`Antigravity_CFO_Execution_Controller`
workflow). Deprecated with n8n. No replacement built yet.

**Aether Orchestrator** — referenced Alex Insight Engine and n8n memory.
Deprecated with n8n. Functionality partially absorbed by `intent_router.py`
and `loop_engine.py`.

**Resonance Socratic Tutor** — referenced in v1.x. Workflow file never created.
Deprecated.

**MCP Authentication Protocol (v1.x §1.2)** — n8n handoff authentication via
`healed_post()`, token validation, `X-Antigravity-Agent` headers. Deprecated
with n8n. `healed_post()` replaced by wire system safety layer.

**LEDGER.md (root)** — contains Alpha V2 Genesis trading strategy ledger, not the
MAF system operations ledger. Do not treat as MAF system file. The ops ledger
function is served by `MASTER_INDEX.md`.

**v1.x Agent entries with no config files:**
Aether Orchestrator, Resonance Socratic Tutor, CFO Execution Controller.
These agents existed as behavioral descriptions only, with no backing code.

---

*Initialized: 2026-03-28T19:55:00-04:00*
*Revised: 2026-06-07*
*Format: AGENTS.md v2.0.0*
*Authority: Supersedes AGENTS.md v1.x for all rule inheritance*
