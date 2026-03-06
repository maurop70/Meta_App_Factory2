# 🦅 Alpha V2 Genesis: Professional Trading Intelligence Suite

> **Version**: 2.6 — Production Release | **Last Updated**: 2026-03-06

Alpha V2 Genesis is an autonomous trading companion designed to synthesize real-time market data, AI-driven sentiment, and macroeconomic research into actionable SPX options strategies. It operates as a fully self-healing, budget-gated intelligence system backed by an n8n cloud research brain and a local Glassmorphic dashboard.

---

## 🚀 Quick Start

### Prerequisites

| Requirement | Notes |
| :--- | :--- |
| Python 3.10+ | `pip` must be in PATH |
| Node.js & npm | For the React UI (`alpha_ui/`) |
| ngrok account | Free tier is sufficient |
| n8n Cloud account | Required for the AI Research Brain |
| `.env` file | See **Configuration** section below |

### Launch (Single Command)

Double-click or run the master launch script from the project root:

```powershell
.\launch_alpha_suite.bat
```

This orchestrates a full boot sequence:

1. **Kills** any stale `python`, `node`, and `ngrok` processes.
2. **Starts** the Flask backend on **Port 5008** (with ngrok self-healing tunnel).
3. **Waits** 10 seconds for the tunnel and n8n sync to complete.
4. **Launches** the React UI on **Port 5173**.

### Access

Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## 🏗️ Architecture Overview

The system operates on a **Dual-Strategy** framework:

| Regime | VIX Level | Strategy | DTE |
| :--- | :--- | :--- | :--- |
| **Low Volatility** | VIX < 15 | Tactical Iron Condor | 7 DTE |
| **High Volatility** | VIX ≥ 15 | Core Income Iron Condor | 45 DTE |

### Core Components

| Component | Location | Role |
| :--- | :--- | :--- |
| **Loki Engine** | `skills/loki/loki.py` | Orchestrates data fetching, strategy synthesis, memo generation |
| **Flask Backend** | `server.py` | Unified API layer, ngrok tunnel manager, hot-update receiver |
| **React Dashboard** | `alpha_ui/` | Glassmorphic UI for real-time monitoring |
| **Trade Entry Portal** | `alpha_ui/` + `server.py` | OCR-powered trade capture with batch commit & portfolio sync |
| **Strategy Ledger** | `strategy_ledger.py` | Daily thesis drift auditing, Greek decomposition, challenger scanning |
| **Alert Manager** | `alert_manager.py` | Windows toast + ntfy.sh mobile + email push alerts |
| **Infrastructure Supervisor** | `infrastructure_supervisor.py` | Background sentinel for n8n and server health |
| **Volatility Sentry** | `volatility_sentry.py` | Real-time VIX regime monitor |
| **N8N Health Guard** | `server.py` | Auto-activates deactivated N8N workflows on every boot |
| **N8N Research Brain** | Cloud (n8n) | `alpha-research-v3` webhook; macro polling and sentiment |

### N8N Workflows (Alpha Architect Project)

| Workflow | Webhook | Purpose |
| :--- | :--- | :--- |
| **Alpha Architect - Genesis (v3)** | `alpha-research-v3` | Primary AI research brain |
| **Alpha_V2_Macro_Event_Tracker** | `alpha-macro-poll` | Polls BEA/FOMC economic calendar |
| **Alpha Ledger Daily Cron** | — (scheduled) | Daily 09:15 EST ledger recalibration |
| **Alpha Phase 3 Logic (Push Mode)** | `alpha-decision` | Trade decision push channel |

> **N8N Project**: All Alpha workflows now reside in the **Alpha Architect** team project (1 of 7 domain projects). See **N8N Project Organization** below.

### N8N Project Organization

As of v2.5, the n8n workspace is organized into **7 domain-grouped team projects** (62 workflows total):

| Project | Workflows | Purpose |
| :--- | :--- | :--- |
| **Alpha Architect** | 8 | Trading intelligence, market research, macro tracking |
| **HR Agents** | 15 | Resume parsing, email classification, policy chatbot |
| **Specialist Agents** | 16 | Architect, CFO, CMO, Critic, Pitch Director, Elite Council |
| **Loki — Master Formulator** | 4 | Formulation Engine, Ice Cream R&D, Ingredient Library |
| **Meta App Factory** | 8 | Auto-generated app webhook workflows |
| **Alexa** | 1 | Alex Insight Engine |
| **System & Infra** | 8 | Gemini Bridge, Claude Executor, Atomizer, Error Trigger |

---

## 🛡️ Stability Suite & Budget Optimization

### Budget Guard

- **Execution Window**: Live AI research is triggered **ONLY** on **Monday to Friday** between **9:00 AM – 4:00 PM EST**.
- **Standby Mode**: Outside these hours, the system bypasses cloud calls and uses local cached data (`Alpha_Data/upcoming_events.json`) to remain fully operational at zero cost.
- **Throttled Pings**: Infrastructure health checks are limited to **5-minute intervals**.

### Stability Modules (7 Built-In)

| Module | Purpose |
| :--- | :--- |
| `preflight.py` | Pre-launch validation of .env, deps, N8N, Docker, ports |
| `n8n_lifecycle.py` | Activate/deactivate N8N workflows + graceful shutdown |
| `n8n_budget_guard.py` | Track N8N execution usage; warn at 70%, block at 90% |
| `error_aggregator.py` | Centralized JSONL error log at `~/.antigravity/` |
| `circuit_breaker.py` | Stop calling dead webhooks after 5 failures; 5 min cooldown |
| `config_snapshot.py` | Auto-snapshot configs before mutations; restore support |
| `telemetry_dashboard.py` | Unified health view aggregating all subsystems |

All modules are inherited by every new app created via `factory.py`.

### N8N Health Guard (v2.6)

On every server boot, the system automatically checks all critical Alpha N8N workflows and **re-activates any that have gone offline**. This prevents the "all intelligence sources offline" issue.

- Protected workflows: Genesis v3, Research v2 Robust, Macro Event Tracker, Ledger Daily Cron
- Uses `POST /api/v1/workflows/{id}/activate` endpoint
- Zero-intervention — fully automatic

---

## 📸 Trade Entry Portal (v2.6)

The **Trade Execution Portal** provides OCR-powered trade capture from broker screenshots:

1. **Paste or upload** a broker screenshot into the Broker Evidence area
2. **Gemini 2.5 Flash Vision** extracts ticker, strategy, strikes, and credit/debit
3. **Draft Cards** appear for each detected trade (supports multi-trade screenshots)
4. Click **"Commit All"** to batch-upload, or review/edit individual drafts
5. Trades auto-sync to `portfolio.json`, `trade_journal.json`, and trigger a Strategy Ledger refresh

| Feature | Description |
| :--- | :--- |
| **OCR Engine** | Gemini 2.5 Flash — extracts Iron Condors, verticals, and multi-leg spreads |
| **Batch Queue** | Upload multiple screenshots; drafts accumulate until committed |
| **Portfolio Sync** | Commits auto-update `portfolio.json` (OPEN/CLOSE) and `trade_journal.json` |
| **Delete Entries** | 🗑️ icon on each log entry to remove test/incorrect trades |
| **Evidence Storage** | Screenshots saved to `Alpha_Data/executions/` with unique IDs |

---

## ⚙️ Configuration

### Environment Variables (`.env`)

Create a `.env` file in the project root with the following keys:

```env
NGROK_AUTH_TOKEN=<your_ngrok_auth_token>
N8N_API_KEY=<your_n8n_api_key>
WEBHOOK_URL=https://<your-n8n-instance>/webhook/alpha-research-v3
N8N_CLAUDE_WEBHOOK_URL=https://<your-n8n-instance>/webhook/claude-bridge
SENTRY_DSN=<optional_sentry_dsn_for_error_tracking>
```

> **Security Note**: Never commit `.env` to version control. It is listed in `.gitignore`.

### Key Data Files (`Alpha_Data/`)

| File | Purpose |
| :--- | :--- |
| `portfolio.json` | Live position data — auto-synced by Trade Entry Portal |
| `trade_journal.json` | Closed + open trade archive — auto-synced by Trade Entry Portal |
| `executions/execution_history.json` | Full execution log with evidence links |
| `upcoming_events.json` | Local cache of macroeconomic calendar (populated by n8n) |
| `connection_info.json` | Auto-generated ngrok tunnel metadata |

### Port Configuration

| Service | Default Port | Override Location |
| :--- | :--- | :--- |
| Flask Backend | **5008** | `server.py` → `PORT` variable |
| React UI | **5173** | `alpha_ui/vite.config.js` |
| API Base URL | `http://localhost:5008` | `alpha_ui/public/config.json` |

---

## 🛠️ Troubleshooting

| Symptom | Likely Cause | Fix |
| :--- | :--- | :--- |
| **"Empty Outlook"** cards | `upcoming_events.json` missing or stale | Run on Mon-Fri to trigger n8n poll; or manually populate the JSON |
| **"Is Server Running?"** UI error | Flask not started or port mismatch | Check `server.py` is running on Port 5008 |
| **n8n sync fails on boot** | Expired `N8N_API_KEY` or invalid Workflow ID | Regenerate key in n8n Cloud settings |
| **ngrok tunnel error** | Stale processes or expired auth token | `taskkill /f /im ngrok.exe` then relaunch |
| **Macro events not updating** | N8N Macro Event Tracker disabled | Verify workflow is active in n8n Cloud |

---

## 📜 Maintenance

- **Updating N8N Webhook URLs**: Modify `WEBHOOK_URL` in `.env`. The self-healing bridge reads this on startup.
- **Updating the Research Brain**: Import the latest `n8n_blueprint.json` via n8n Cloud → Settings → Import.
- **Port Conflicts**: Update `PORT` in `server.py` and `apiBaseUrl` in `alpha_ui/public/config.json`.
- **Adding Dependencies**: Update `requirements.txt` and re-run `pip install -r requirements.txt`.

---

## 📄 License & Commercial Use

© 2026 Antigravity AI. All rights reserved.
This software is proprietary. Redistribution or commercial use requires an explicit written license from the author.

---

*Alpha V2 Genesis v2.6 — Lead Quant Architect + OCR Trade Entry + N8N Health Guard + Stability Suite*
