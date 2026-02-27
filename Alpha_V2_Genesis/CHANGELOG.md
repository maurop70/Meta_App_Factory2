# 📋 Alpha V2 Genesis — Changelog

All notable changes to this project are documented in this file.  
Format: `[vX.Y] YYYY-MM-DD — Description`

---

## [v2.4] 2026-02-26 — N8N Multi-Project Migration & GitHub Pipeline Audit

### N8N Workspace Reorganization

Migrated **62 workflows** from a flat n8n Cloud workspace into **7 domain-grouped team projects**:

| Project | Workflows | Key Domains |
|---|---|---|
| **Alpha Architect** | 8 | Alpha suite, Genesis v3, Macro Tracker, Ledger Cron |
| **HR Agents** | 15 | Resume parsing, CV extraction, email classifiers, policy chatbot |
| **Specialist Agents** | 16 | Architect, CFO, CMO, Critic, Pitch Director, Elite Council |
| **Loki — Master Formulator** | 4 | Formulation Engine, Ice Cream R&D, Ingredient Library |
| **Meta App Factory** | 8 | MetaApp webhook workflows, Factory trigger |
| **Alexa** | 1 | Alex Insight Engine |
| **System & Infra** | 8 | Gemini Bridge, Claude Executor, Atomizer, Error Workflow |

### Added

- **Migration Tooling** (`n8n_migration/`):
  - `migrate_v2.py` — Project creation + workflow transfer via n8n API (adapted for 3 team project limit).
  - `build_registry.py` — Auto-generates project/workflow registry from live n8n instance.
  - `inject_sentinel.py` — Deploys Sentinel monitoring into project workflows.
  - `vault.py` — Credential vault management for PAT and API key storage.
  - `deep_audit.py` — Full workspace audit: workflows, credentials, webhooks, duplicates.
  - `credential_healing.py` — Detects and repairs broken credential bindings post-migration.

### GitHub Pipeline Audit

- **Finding**: No GitHub integration exists anywhere in the Antigravity ecosystem. Zero GitHub/Git nodes across all 64 workflows, no PAT/tokens in any `.env`, no push logic in factory code.
- **Patch Plan Documented**: 4-phase plan — (1) PAT + vault setup, (2) `git_deployer.py` module, (3) optional n8n GitHub Push workflow, (4) wire into factory launch sequence.
- **Status**: Planned (not yet built). Awaiting GitHub PAT from user.

---

## [v2.3] 2026-02-25 — Stability Suite & N8N Lifecycle Management

### Added

- **N8N Lifecycle Management** (`n8n_lifecycle.py`):
  - Activates N8N workflows on app launch, deactivates on close.
  - Graceful shutdown handler: `atexit` + `SIGINT`/`SIGTERM` + Windows `CTRL_CLOSE_EVENT`.
  - CLI: `python n8n_lifecycle.py activate|deactivate alpha|meta|all`.
  - Integrated into `server.py` via `register_shutdown_hook('alpha')`.
- **Preflight Check** (`preflight.py`):
  - Pre-launch validation: `.env` keys, Python deps, N8N connectivity, Docker status, port availability.
  - Profiles: `alpha`, `meta`, `generic`. Launch aborts if critical failures found.
- **Execution Budget Guard** (`n8n_budget_guard.py`):
  - Queries N8N API for execution counts. Warns at 70%, blocks at 90% of monthly limit (default: 10,000).
  - Tracks 30 historical snapshots in `Alpha_Data/n8n_execution_log.json`.
- **Error Aggregator** (`error_aggregator.py`):
  - Centralized JSONL error log at `~/.antigravity/error_log.jsonl`.
  - All apps write to the same file. Auto-rotates at 10MB. Filter by app/severity.
- **Circuit Breaker** (`circuit_breaker.py`):
  - Stops calling dead N8N webhooks after 5 consecutive failures.
  - 5 min cooldown → HALF_OPEN (1 test call allowed) → CLOSED after 2 successes.
  - Persists state to disk at `~/.antigravity/circuit_breakers/`.
- **Config Snapshot** (`config_snapshot.py`):
  - Auto-snapshots configs before mutations (ngrok URL changes, workflow patches).
  - Keeps last 10 versions per file. Supports `--restore` for rollback.
- **Telemetry Dashboard** (`telemetry_dashboard.py`):
  - Unified health view aggregating Budget, Errors, Circuit Breakers, and Snapshots.
  - CLI: `python telemetry_dashboard.py` or `--json` for UI consumption.

### Updated

- **`launch.bat`** — Added preflight step 0 (aborts if failed) + N8N lifecycle hooks.
- **`Launch_Meta_Factory.bat`** — Added preflight step 0 + N8N lifecycle hooks.
- **`server.py`** — Added `register_shutdown_hook('alpha')` after warm-up.
- **`factory.py`** — New apps inherit all 7 stability modules + `workflow_id` in `config.json`.
- **`vite.config.js`** — Added `preserveSymlinks: true` to fix blank UI from Google Drive junction.

### N8N Trigger Frequency Patches

- **Macro Event Tracker**: `0 */6 * * *` (6h) → `*/30 * * * *` (30 min)
- **Ledger Daily Cron**: Verified correct at `15 14 * * 1-5` (09:15 EST, Mon-Fri)
- **Genesis v3**: Webhook-triggered (no schedule to adjust)

---

## [v2.2.1] 2026-02-24 — Vite Launch Fix

### Fixed

- **`launch_alpha_suite.bat`** — Vite dev server failed to start on Windows with a `SyntaxError: missing ) after argument list`. Root cause: `node node_modules\.bin\vite` was invoking the **bash-formatted shim** (a shell script) instead of the Windows batch shim. Changed to `node_modules\.bin\vite.cmd --host`, which correctly launches the Vite dev server on Windows. UI now starts reliably on first launch.

---

## [v2.2] 2026-02-24 — Alert System, Theta Curve & Trade Journal

### Added

- **`alert_manager.py`** — Three-channel push alert system (Priority 3):
  - **Windows Desktop Toast**: Native W10/11 balloon notification, zero setup, fires immediately.
  - **ntfy.sh Mobile Push**: Free mobile alerts via `ntfy.sh/alpha-v2-genesis-alerts`. No account or API key. Confirmed working on iOS/Android with "Instant delivery in doze mode" enabled.
  - **SMTP Email**: Optional. Add `ALERT_EMAIL`, `SMTP_USER`, `SMTP_PASS` to `.env` to activate.
  - **4 pre-built alert templates**: `alert_thesis_broken()`, `alert_pivot_recommended()`, `alert_dte_exit_window()`, `alert_profit_target()`.
  - Built-in de-duplication: each alert fires once per position per session via `pstate["alerts_sent"]`.
- **`GET /api/journal`** — Flask endpoint returning `Alpha_Data/trade_journal.json` sorted newest-first (Priority 5).

### Updated

- **`strategy_ledger.py`**:
  - `JOURNAL_PATH` constant added (`Alpha_Data/trade_journal.json`).
  - `track_closed_positions()` — On every ledger run, compares known positions to currently OPEN portfolio. Archives any closed position to trade journal with: entry/close dates, credit, realized P&L, % of max profit, days held, entry rating, worst drift score, max drawdown%.
  - Alert triggers wired in `run_ledger()`: THESIS BROKEN → CRITICAL, PIVOT → WARN, 21-DTE → WARN, 50% profit → INFO. All de-duplicated per position.
  - `fetch_leg_data()` and `compute_position_greeks()` already updated (v2.1) with real Black-Scholes Greeks.
- **`App.jsx`** — Three UI upgrades:
  - **`ThetaDecayCurve` component** (Priority 4): SVG mini-chart inside `LedgerCard` showing projected theta decay from current mark → $0 at expiry. Power-curve model (0.65 exponent) captures gamma acceleration near expiry. Features: 50% profit yellow dashed line, 21-DTE exit grey dashed line, per-catalyst colored event markers (red/yellow), blue gradient fill, current-mark dot label.
  - **`tradeJournal` state + `fetchJournal()`**: Fetches `/api/journal` on mount and every 5 minutes alongside ledger poll.
  - **📘 Trade Journal panel** (Priority 5): Full-width styled table at bottom of dashboard, visible only when closed trades exist. Columns: Trade ID, Strategy, Opened, Closed, Days, Entry Credit, Close Mark, P&L (colour-coded), % Max, Drawdown, Rating. Shows aggregate average P&L% in panel header.

### Architecture Notes

- **ntfy.sh topic**: `alpha-v2-genesis-alerts` — permanent, free, no expiry. Subscribe on phone: ntfy app → add subscription → `alpha-v2-genesis-alerts` (default server, instant delivery ON).
- **Alert channel priority**: Windows toast fires first (sub-second, local), ntfy fires second (2–5s, cross-device), email fires last (optional, async).
- **Journal lifecycle**: Position transitions OPEN → missing from portfolio.json → archived to journal on next ledger run. State entry is removed after archival to keep `ledger_state.json` lean.

---

## [v2.1] 2026-02-23 — Strategy Ledger, Greek Intelligence & N8N Cron

### Added

- **`strategy_ledger.py`** — Lead Quant Architect engine. Four integrated modules:
  - **Event-Triggered Trade Rationale**: Automatically generates a scored entry report (0–9 rubric, pros/cons, catalyst calendar) when a new `OPEN` position is detected in `portfolio.json`.
  - **Thesis Drift Detector**: Daily recalibration comparing original entry conditions (VIX, SPX, IV Rank, IV-HV spread) to current market. Flags INTACT / DRIFTING / BROKEN status.
  - **Challenger Scanner**: Scans for fresh Iron Condor alternatives at optimal delta-based strikes. Issues `PIVOT RECOMMENDED` alert if challenger offers meaningfully better margin.
  - **Log Intelligence Parser**: Reads `alpha.log` to extract N8N failure counts, confidence score trends, and system health into the Ledger report.
  - Outputs: `Alpha_Data/LEDGER.md` (human-readable living document) + `Alpha_Data/ledger_state.json` (machine-readable for API).
- **N8N Workflow: `Alpha Ledger Daily Cron`** (ID: `tbQnSD6n9JHHvZ3D`) — Fires at **09:15 EST, Mon–Fri**. Calls `POST /api/ledger/refresh`. Fully active and wired to self-healing.
- **`Alpha_Data/ledger_cron_meta.json`** — Stores cron workflow ID for self-heal targeting.
- **`/api/ledger` (GET)** — Flask endpoint returning current ledger state JSON + LEDGER.md markdown.
- **`/api/ledger/refresh` (POST)** — Triggers background ledger recalibration (non-blocking).
- **`greek_decompose.py`** (scratch) — Live Greek decomposition tool: fetches real option marks, IV, calculates IV-HV spread, net daily theta, and provides IV-vs-Theta attribution for any open position.
- **`trade_review.py`** (scratch) — Full historical trade review: VIX regime analysis, HV30 vs IV spread, 52-week percentile, catalyst calendar, scored entry rating, and 20-day IV outlook.

### Updated

- **`infrastructure_supervisor.py`** — Now does 4 things: N8N health ping, local server health, **portfolio.json watcher** (triggers ledger on new OPEN positions), and **daily 09:15 recalibration cron**.
- **`server.py`**:
  - Added `heal_ledger_cron()` — self-heals Ledger Cron workflow URL on every restart.
  - **Static URL Detection**: Boot sequence now compares new ngrok URL to stored URL. Skips N8N reprogramming if URL unchanged (fast path for static ngrok domains, saves 2–3s startup time).
  - Updates `connection_info.json` with `url_is_static` flag for portability tracking.
- **`launch_alpha_suite.bat`**:
  - Enabled `infrastructure_supervisor.py` (was commented out).
  - Added `start "" http://localhost:5173` (browser auto-opens on launch).
  - Updated title and step labels to match v2.1 architecture.
  - Step count: 3 → 4.
- **`Alpha_V2_Genesis` Desktop Shortcut**:
  - Icon updated: `imageres.dll,106` → `shell32.dll,162` (chart icon).
  - Description added: `Alpha V2 Genesis — Antigravity Trading System (Loki + Strategy Ledger + N8N)`.
- **`App.jsx`** — Three UI fixes:
  - Strategic Regime Rationale: was reading `data.rationale` (undefined) → now reads `loki_proposal.rationale`.
  - Volatility Agent: `FORECAST:` label replaced with full `N8N FORECAST` badge (colour-coded BULLISH/NEUTRAL/BEARISH, Genesis v3 / Local Cache source indicator, plain-English implication).
  - Defense Matrix (STABLE state): Old simulation panel replaced with dedicated **Challenger Trade Scan** panel showing current vs challenger strikes, Cost to Switch, New Entry Credit, Net P&L if Switched.

### Fixed

- **Rationale missing in UI**: `data.rationale` (top-level key, never set) → `loki_proposal.rationale` (correct path).
- **Forecast badge invisible**: N8N forecast was a small yellow text with no context. Now a full badge with source and trading implication.
- **Challenger Trade never displayed**: STABLE state used `data.expert_opinions.simulation` (never set in this state). Now correctly uses `data.expert_opinions.defense` with `data.market_state === 'STABLE'` guard.

### Architecture Notes

- **Portability**: ngrok free static domain (`*.ngrok-free.dev`) confirmed — URL is permanent across PC restarts and cross-machine. Self-healing re-programs N8N only when the URL actually changes.
- **N8N Cron self-heals**: `heal_ledger_cron(public_url)` called at every boot, just after `self_heal_n8n()`, ensuring the daily trigger always points to the active machine.

### Added

- `INSTALL.md` — Full commercial installation guide with prerequisites, n8n import steps, and post-install verification checklist.
- `CHANGELOG.md` — This file. Replaces stale internal test artifacts.
- `python-dotenv` added to `requirements.txt` (was an implicit dependency; now explicit).

### Updated

- `README.md` — Full commercial rewrite: architecture table, N8N workflow inventory, troubleshooting matrix, port config guide, license notice.
- `ARCHITECT.md` — Full commercial rewrite: ASCII data pipeline diagram, N8N API payload contracts, reliability pattern tiers, Docker deployment notes.
- `USER_GUIDE.md` — Full commercial rewrite: tabular dashboard guide, VIX regime explainer, portfolio how-to, FAQ section.
- `.agent/manifest.md` — Updated to v2.0 with full integration point registry and budget gate documentation.

---

## [v1.9] 2026-02-23 — N8N Workflow Reliability Fixes

### Fixed

- **Genesis V3 JSON Parsing**: Added markdown code-fence stripping and structured error classification (`timeout`, `json_error`, `http_{code}`) to prevent crashes on malformed n8n responses.
- **Hardcoded Dates Eliminated**: Removed all static date references from macro event polling. System now uses dynamic date ranges relative to `datetime.now()`.
- **Macro Event Tracker Stability**: Fixed high-failure-rate issue caused by the Macro Event Tracker workflow. Added local cache fallback so the UI never shows broken or empty event cards.
- **API Key Consistency**: Standardized `N8N_API_KEY` usage across all n8n-facing modules via `.env` — no more hardcoded keys.
- **Prompt Field Compatibility**: `bridge.py` now sends prompts under all three LangChain field names (`prompt`, `chatInput`, `input`) to ensure compatibility with n8n Gemini Agent Bridge.

---

## [v1.8] 2026-02-20 — Docker & Bridge Integration

### Added

- `Dockerfile` — Full containerized deployment of the Meta App Factory.
- ngrok-to-Docker bridge integration: n8n can now reach the containerized server via Ngrok tunnel.
- `.gitignore` — Prevents accidental commit of `.env`, logs, `__pycache__`, and `ngrok.exe`.

### Fixed

- Docker container environment now reads secrets from environment variables (not baked-in `.env`).

---

## [v1.7] 2026-02-18 — Macro Outlook Debugging

### Fixed

- **7-Day Outlook Empty**: Resolved root cause — n8n Genesis v3 workflow was returning data under a non-standard key. Server-side normalization added.
- **Fallback Chain**: System now gracefully degrades from n8n → `upcoming_events.json` → empty state with UI message, rather than crashing.
- **Macro Event Display**: FOMC Minutes and Q4 GDP events now correctly surface in the `Macro Risk Radar` card.

---

## [v1.6] 2026-02-17 — Port Sync & Self-Healing

### Fixed

- **UI Port Mismatch**: All `alpha_ui` API references updated from Port 5000 → Port 5005. `config.json` is now the single source of truth for `apiBaseUrl`.
- **Self-Healing Port Mechanism**: Server writes its active port to `Alpha_Data/connection_info.json`; UI reads this at runtime to auto-sync.

### Added

- `infrastructure_supervisor.py` — Background process monitoring n8n and server health at 5-minute intervals.
- `volatility_sentry.py` — Real-time VIX regime watcher running as a background subprocess.
- Auto-dependency check in `launch_alpha_suite.bat` — runs `pip install -r requirements.txt` before launch.

---

## [v1.5] 2026-02-13 — Portability & System State Migration

### Changed

- All hardcoded local paths replaced with `os.path` relative resolution from `__file__`.
- Local artifacts (logs, memory, scratch data) relocated to Google Drive directory structure for cross-machine portability.
- `.env.template` standardized for clean "Warm Start" on any machine.

### Added

- `sync_manifest.json` — Verifies portable setup integrity.

---

## [v1.4] 2026-02-11 — Dual-Strategy Framework

### Added

- **Tactical (7-DTE)** Iron Condor strategy for low-volatility regimes (VIX < 15).
- **Core Income (45-DTE)** Iron Condor strategy for high-volatility regimes (VIX ≥ 15).
- VIX-based automatic strategy selector in Loki Engine.
- Strategy mode label displayed prominently in UI Strategy Ribbon.

### Fixed

- Dynamic expiration date logic — eliminated all hardcoded expiry dates. `loki.py` now fetches valid future expiration dates from Yahoo Finance at runtime, with fallback to nearest valid future date.

---

## [v1.0] 2026-02-11 — Initial Release

### Added

- Loki Engine (`skills/loki/loki.py`) — Core strategy brain.
- Flask Backend (`server.py`) — Unified API layer with ngrok self-healing tunnel.
- React Dashboard (`alpha_ui/`) — Glassmorphic UI for real-time monitoring.
- N8N integration for AI research and macro event polling.
- Budget Guard — Execution window limiting cloud calls to Mon–Tue 9a–4p EST.
- Alpha Confidence Score — Composite signal from sentiment, volatility, and macro risk.
- Watchdog — Trade proposal engine with Greek/DTE threshold logic.
