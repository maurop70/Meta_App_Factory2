# 🧠 Alpha V2 Genesis: Technical Architect's Guide

> **Version**: 3.0 — V3 Streaming + Factory Web Evolution | **Last Updated**: 2026-02-27

---

## 📡 Data Pipeline Flow

```
User Action (UI Open / "Refine Scan")
         │
         ▼
   server.py (Flask API, Port 5005)
         │
         ▼
   Loki Engine (skills/loki/loki.py)
         │
         ├──→ [Budget Gate Check: Mon-Tue 9a-4p?]
         │         YES → N8N Webhook (alpha-research-v3)
         │         NO  → Load Alpha_Data/upcoming_events.json (local cache)
         │
         ├──→ yfinance → SPX Price, VIX Level, 5-Day Trend
         │
         ├──→ OptionsChain → Expiry & Strike Selection (7 DTE or 45 DTE)
         │
         ├──→ Alpha Confidence Score Synthesis:
         │         • Sentiment (BEARISH / NEUTRAL / BULLISH)
         │         • Volatility Signal (VIX Rank + Regime)
         │         • Macro Risk Level (HIGH / LOW)
         │
         └──→ Watchdog → Trade Proposal (ROLL / HOLD / WAIT)
                   │
                   ▼
            JSON Payload → React UI (Port 5173)
```

---

## 🌉 N8N Bridge & Self-Healing Architecture

Every time `server.py` restarts, it executes the **Self-Healing Boot Sequence**:

1. **Tunnel Creation**: Opens a fresh `ngrok` HTTPS tunnel on Port 5005.
2. **Verification**: Performs a GET to the public URL to confirm tunnel integrity.
3. **N8N Sync**: Calls the n8n API (`PUT /api/v1/workflows/{N8N_WORKFLOW_ID}`) to reprogram the `Push_to_Alpha_UI` node with the new tunnel URL.
4. **Warm-Up**: Triggers `loki_engine.run_strategy()` to pre-populate `portfolio.json` and `market_memo.md` before any UI requests arrive.

### N8N API Interaction

| Action | Method | Endpoint |
| :--- | :--- | :--- |
| Fetch Workflow | `GET` | `/api/v1/workflows/{id}` |
| Update Tunnel URL | `PUT` | `/api/v1/workflows/{id}` |

> **Validation Note**: The n8n API v1 `PUT` endpoint rejects unknown `settings` keys. The `self_heal_n8n()` function in `server.py` filters the `settings` payload to only include API-supported keys (`saveExecutionProgress`, `saveManualExecutions`, etc.) before pushing.

---

## 🔗 N8N Workflow Inventory

| Workflow Name | Webhook Path | Trigger | Data Returned |
| :--- | :--- | :--- | :--- |
| **Alpha Research V3** | `/webhook/alpha-research-v3` | `POST` from Loki | Market sentiment, macro outlook, SPX bias |
| **Macro Event Tracker** | `/webhook/alpha-macro-poll` | Scheduled (n8n cron) | Upcoming BEA/FOMC events as JSON array |
| **Gemini Agent Bridge** | `/webhook/gemini-bridge` | Internal agents | AI command routing |
| **Elite Council** | Internal | Multi-agent trigger | Advisory panel consensus |

### Genesis V3 Payload Contract

**Request (from `loki.py` → n8n):**

```json
{
  "prompt": "<market_context_and_question>",
  "chatInput": "<same_prompt>",
  "input": "<same_prompt>"
}
```

**Response (from n8n → `loki.py`):**

```json
{
  "output": "<AI_research_text>"
}
```

> **Note**: All three field names (`prompt`, `chatInput`, `input`) are sent simultaneously for LangChain compatibility.

### Macro Event Payload Contract

**N8N pushes to `/api/hot_update` (POST):**

```json
[
  {
    "event": "FOMC Minutes",
    "event_name": "FOMC Minutes Release",
    "date": "2026-02-26",
    "impact": "HIGH",
    "impact_level": "HIGH",
    "strategic_rationale": "Fed signals matter for rate expectations.",
    "strategic_note": "Monitor for hawkish/dovish pivot."
  }
]
```

---

## 🗂️ N8N Project Architecture (v2.4)

As of v2.4, the n8n workspace has been restructured from a flat workspace into **7 domain-grouped team projects** via `migrate_v2.py`.

```
n8n Cloud Workspace
├── Alpha Architect (8)       ← Trading intelligence, Genesis, Macro, Ledger
├── HR Agents (15)            ← Resume parsing, CVs, email classifiers, chatbot
├── Specialist Agents (16)    ← Architect, CFO, CMO, Critic, Pitch, Elite Council
├── Loki — Formulator (4)     ← Formulation Engine, Ice Cream R&D, Ingredients
├── Meta App Factory (8)      ← Auto-generated app webhook workflows
├── Alexa (1)                 ← Alex Insight Engine
└── System & Infra (8)        ← Gemini Bridge, Claude Executor, Atomizer, Errors
```

**Migration Tooling** (located at `n8n_migration/`):

| Script | Purpose |
| :--- | :--- |
| `migrate_v2.py` | Project creation + workflow transfer via n8n API |
| `build_registry.py` | Auto-generates project/workflow registry from live instance |
| `inject_sentinel.py` | Deploys Sentinel monitoring into project workflows |
| `vault.py` | Credential vault management for PAT and API key storage |
| `deep_audit.py` | Full workspace audit: workflows, credentials, webhooks |
| `credential_healing.py` | Detects and repairs broken credential bindings |

> **Note**: n8n Cloud's team project limit required workflow consolidation during migration. The `migrate_v2.py` script handles the 3-project limit by grouping related domains.

---

## 🐙 GitHub Deployment Pipeline (Planned)

Audited on 2026-02-26 — **no GitHub integration currently exists** anywhere in the ecosystem. Zero GitHub/Git nodes across all workflows, no PAT in any `.env`, no push logic.

**Planned 4-Phase Integration:**

```
Phase 1: Credential Setup
  └── GitHub PAT (repo scope) → master_credentials.json → vault.py

Phase 2: git_deployer.py (new module in Meta_App_Factory/)
  └── init repo → commit → push via PAT → return repo URL

Phase 3: n8n Workflow (optional)
  └── /webhook/github-push → GitHub API nodes → INVENTORY log

Phase 4: Factory Integration
  └── factory.py Step 10 → git_deployer → sync_manifest.json → Sentinel whitelist
```

**Status**: Planned. Awaiting GitHub PAT provisioning.

---

## 🛡️ Reliability Patterns

### Market Data Fallback (Tiered yfinance Strategy)

```
Primary   → ticker.history(period="1d")         [Most robust, OHLCV data]
Secondary → ticker.info.get('regularMarketPrice') [Fast metadata fallback]
Tertiary  → Last-known cached value in portfolio.json
```

### Macro Data Fallback

```
Primary   → N8N Macro Event Tracker webhook response
Secondary → Alpha_Data/upcoming_events.json (last successful poll)
Tertiary  → Empty events list (UI displays "No events found" gracefully)
```

### N8N Response Parsing (JSON Safety)

The Loki engine strips markdown code fences and logs raw response snippets before parsing, preventing `JSONDecodeError` on malformed or empty n8n responses. Error classification differentiates:

- `timeout` — network issues
- `json_error` — malformed payload
- `http_{code}` — n8n execution errors

---

## 📂 File System Mapping

```text
Alpha_V2_Genesis/
├── server.py                      # Flask API + ngrok tunnel manager
├── launch_alpha_suite.bat         # Master launch script
├── infrastructure_supervisor.py   # Background n8n + server health monitor
├── volatility_sentry.py           # Real-time VIX regime watcher
├── .env                           # Secrets (gitignored)
├── requirements.txt               # Python dependencies
│
├── ── Stability Suite ──
├── n8n_lifecycle.py               # Activate/deactivate N8N workflows + graceful shutdown
├── preflight.py                   # Startup validation (env, deps, connectivity)
├── n8n_budget_guard.py            # Execution budget tracking & warnings
├── error_aggregator.py            # Centralized error logging (JSONL)
├── circuit_breaker.py             # Failure prevention with cooldowns
├── config_snapshot.py             # Auto-versioned config backups
├── telemetry_dashboard.py         # Unified system health view
│
├── Alpha_Data/
│   ├── portfolio.json             # Live position data (written by n8n hot-update)
│   ├── upcoming_events.json       # Macro event cache (written by n8n)
│   ├── connection_info.json       # ngrok tunnel metadata
│   ├── n8n_execution_log.json     # Budget guard history
│   └── .config_snapshots/         # Versioned config backups
│
├── skills/
│   ├── loki/loki.py               # Core strategy orchestrator (Loki Engine)
│   ├── macro/                     # Risk level constants, event normalization
│   ├── watchdog/                  # Position Greek analysis, trade proposals
│   ├── sentiment/                 # News headline sentiment scoring
│   └── risk/                      # Binary risk guardian logic
│
├── utils/
│   └── n8n_bridge.py              # Standardized n8n communication layer
│
└── alpha_ui/
    ├── src/                       # React components (Glassmorphic design)
    └── public/config.json         # Runtime API base URL (Port 5005)
```

---

## 🛡️ Stability Suite (7 Modules)

All modules are inherited by every app created via `factory.py`.

| Module | Purpose | CLI |
| :--- | :--- | :--- |
| `preflight.py` | Pre-launch validation of .env, deps, N8N, Docker, ports | `python preflight.py --app alpha` |
| `n8n_lifecycle.py` | Activate/deactivate N8N workflows + graceful shutdown | `python n8n_lifecycle.py activate alpha` |
| `n8n_budget_guard.py` | Track N8N execution usage; warn at 70%, block at 90% | `python n8n_budget_guard.py` |
| `error_aggregator.py` | Centralized JSONL error log at `~/.antigravity/` | `python error_aggregator.py` |
| `circuit_breaker.py` | Stop calling dead webhooks after 5 failures; 5 min cooldown | `python circuit_breaker.py` |
| `config_snapshot.py` | Auto-snapshot configs before mutations; restore support | `python config_snapshot.py --list` |
| `telemetry_dashboard.py` | Unified health view aggregating all subsystems | `python telemetry_dashboard.py` |

### N8N Lifecycle Management

```text
App Launch:
  launch.bat → preflight.py → n8n_lifecycle.py activate alpha → server.py → UI

App Close:
  User closes Vite window → launch.bat cleanup → n8n_lifecycle.py deactivate alpha
  OR: Force-close terminal → server.py atexit/signal handler → deactivate alpha
```

- `register_shutdown_hook()` catches: `atexit`, `SIGINT`, `SIGTERM`, Windows `CTRL_CLOSE_EVENT`
- Workflows are only active while the app is running → prevents execution burn

---

## 🔑 Key Configuration Constants (`server.py`)

| Constant | Value | Purpose |
| :--- | :--- | :--- |
| `PORT` | `5005` | Flask server port |
| `N8N_WORKFLOW_ID` | `VkE0dmwynRPMIyjdmiONL` | N8N workflow ID for self-healing sync |
| `N8N_NODE_NAME` | `Push_to_Alpha_UI` | N8N node to reprogram with tunnel URL |

---

## 🐳 Docker Deployment (Optional)

A `Dockerfile` is available in the `Meta_App_Factory` root for containerized deployments. When running in Docker:

- Mount secrets via environment variables (do not bake `.env` into the image).
- Use `ngrok` authtoken from environment to establish external tunnel.
- The ngrok tunnel URL is ephemeral per container start; the self-healing boot sequence handles re-registration with n8n automatically.

See `Meta_App_Factory/Dockerfile` and `Meta_App_Factory/Launch_Meta_Factory.bat` for full build instructions.

---

## 🔥 V3 Streaming Engine (SSE)

> Added in V3.0 (2026-02-27)

The V3 engine replaces the synchronous n8n webhook loop with **Server-Sent Events (SSE)** for real-time, token-by-token streaming from Gemini.

### Architecture

```text
React UI (App.jsx)
     │
     ▼ POST /api/chat/stream
FastAPI (server.py)
     │
     ▼
stream_bridge.py / factory_stream.py
     │
     ├──→ Vault (vault_client.py) → GEMINI_API_KEY
     ├──→ Gemini REST API (streamGenerateContent, alt=sse)
     ├──→ Context Injection (_build_system_prompt)
     │         • dashboard_context (live UI state)
     │         • Local files (strategy_ledger.py, market_memo.md)
     ├──→ Supabase Memory (memory_engine.py)
     └──→ LangSmith Telemetry (LANGCHAIN_API_KEY from Vault)
                │
                ▼
         SSE data: chunks → React ReadableStream
```

### Key Files

| File | Purpose |
| :--- | :--- |
| `stream_bridge.py` | Alpha V3 SSE bridge (Gemini streaming) |
| `factory_stream.py` | Factory SSE bridge (reads registry.json, commands.json) |
| `memory_engine.py` | Supabase-backed conversation persistence |

### Context Injection

The `_build_system_prompt()` function enriches every LLM call with:

1. **Dashboard Context** — live metrics from the React UI (SPX price, VIX, signals)
2. **Local Files** — reads `strategy_ledger.py` and `market_memo.md` at call time
3. **Conversation History** — last 6 turns from `.Gemini_state/.stream_history.json`

---

## 🔐 Encrypted Vault (V2.0)

All secrets stored in `vault.enc` (Fernet-encrypted), managed by `vault_client.py`.

| Key | Purpose |
| :--- | :--- |
| `GEMINI_API_KEY` | Google Gemini API |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_KEY` | Supabase anon/service key |
| `LANGCHAIN_API_KEY` | LangSmith tracing |
| `N8N_API_KEY` | n8n REST API |
| `N8N_WORKFLOW_ID` | Self-healing workflow |
| `NGROK_AUTH_TOKEN` | Tunnel authentication |
| `ALPHA_API_KEY` | Alpha service key |

Auto-unlock: `.vault_pw` file (gitignored).

---

## 📊 LangSmith Telemetry

Configured automatically on boot via environment variables:

| Variable | Value |
| :--- | :--- |
| `LANGCHAIN_TRACING_V2` | `true` |
| `LANGCHAIN_ENDPOINT` | `https://api.smith.langchain.com` |
| `LANGCHAIN_PROJECT` | `Alpha_V3_Streaming` or `Meta_App_Factory` |

---

## 🏭 Factory Web Evolution (V3.0)

The Meta App Factory has been migrated from Tkinter to React/FastAPI:

| Component | Old (V2) | New (V3) |
| :--- | :--- | :--- |
| Frontend | `launcher.py` (Tkinter) | `factory_ui/` (Vite/React) |
| Backend | `api.py` (minimal) | `api.py` (Full FastAPI + SSE) |
| App Generator | `ui_designer.py` (Tkinter templates) | `ui_designer.py` (React/Vite + FastAPI scaffold) |
| Launch | `Launch_Meta_Factory.bat` | `launch_factory.ps1` (port kill + dual server) |

### Factory API Endpoints

| Endpoint | Method | Purpose |
| :--- | :--- | :--- |
| `/` | GET | Service info |
| `/execute` | POST | Trigger supervisor task |
| `/api/registry` | GET | List registered apps |
| `/api/commands` | GET | Serve commands.json |
| `/api/agents/status` | GET | Agent health check (7 agents) |
| `/api/chat/stream` | POST | SSE streaming chat |
| `/api/chat/clear` | POST | Clear chat history |
| `/api/health` | GET | Health check |
