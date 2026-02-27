# 🛠️ Alpha V2 Genesis: Installation Guide

> **Version**: 2.4 — Production Release | **Last Updated**: 2026-02-26

---

## 📋 Prerequisites

Before installing, ensure the following are available on your machine:

| Tool | Version | Download |
| :--- | :--- | :--- |
| **Python** | 3.10+ | [python.org](https://python.org) |
| **Node.js** | 18+ (LTS) | [nodejs.org](https://nodejs.org) |
| **npm** | Bundled with Node.js | — |
| **ngrok** | Any (account required) | [ngrok.com](https://ngrok.com) |
| **n8n Cloud** | Active account | [app.n8n.cloud](https://app.n8n.cloud) |
| **Git** | Optional (for cloning) | [git-scm.com](https://git-scm.com) |

---

## 📥 Step 1 — Install Python Dependencies

Open a terminal in the project root and run:

```powershell
pip install -r requirements.txt
```

**Contents of `requirements.txt`:**

```
flask
flask-cors
yfinance
pandas
numpy
requests
pyngrok
python-dotenv
```

> If you see `ModuleNotFoundError` on launch, re-run this command. The `install_dependencies.bat` script automates this step.

---

## 📦 Step 2 — Install UI Dependencies

```powershell
cd alpha_ui
npm install
cd ..
```

This installs all React dependencies into `alpha_ui/node_modules/`.

---

## 🔐 Step 3 — Configure Environment Variables

Create a `.env` file in the project root (copy from `.env.template` if available):

```env
NGROK_AUTH_TOKEN=<your_ngrok_auth_token>
N8N_API_KEY=<your_n8n_api_key>
WEBHOOK_URL=https://<your-n8n-instance>/webhook/alpha-research-v3
N8N_CLAUDE_WEBHOOK_URL=https://<your-n8n-instance>/webhook/claude-bridge
SENTRY_DSN=<optional_sentry_dsn>
```

### How to Get These Values

| Variable | Where to Find |
| :--- | :--- |
| `NGROK_AUTH_TOKEN` | [ngrok Dashboard](https://dashboard.ngrok.com/get-started/your-authtoken) → "Your Authtoken" |
| `N8N_API_KEY` | n8n Cloud → Settings → API → Create API Key |
| `WEBHOOK_URL` | n8n Cloud → Your Workflow → Copy Webhook URL |
| `SENTRY_DSN` | Optional. [sentry.io](https://sentry.io) → Project → Settings → SDK Setup |

---

## ☁️ Step 4 — Import N8N Workflows

The system requires the following n8n workflows to be active:

1. **Alpha Research V3** — Primary AI research brain
2. **Macro Event Tracker** — Economic calendar polling

To import:

1. Log in to [app.n8n.cloud](https://app.n8n.cloud)
2. Navigate to the **Alpha Architect** project (workflows are organized into 7 domain projects as of v2.4)
3. Click **"New Workflow"** → **"Import from JSON"**
4. Upload the `n8n_blueprint.json` file from this project (if provided by your vendor)
5. **Activate** each workflow using the toggle in the top-right corner of the workflow editor

> **Note (v2.4)**: N8N workflows are now organized into team projects. Alpha-related workflows belong in the **Alpha Architect** project. See `CHANGELOG.md` for the full 7-project mapping.

> **Critical**: Both research workflows must be in **Active** state. Inactive workflows will cause the system to fall back to cached data indefinitely.

---

## 🏃 Step 5 — First Launch

Run the master launch script:

```powershell
.\launch_alpha_suite.bat
```

Watch the console for:

```
✅ Tunnel Verification: SUCCESS
✅ Antigravity: n8n Workflow '...' successfully synced.
✅ Warm-up Complete: portfolio.json and market_memo.md initialized.
🤖 Alpha Server listening on Port 5005...
```

Then open [http://localhost:5173](http://localhost:5173) in your browser.

---

## ✅ Post-Install Verification Checklist

- [ ] `http://localhost:5005` returns `{"status": "online"}`
- [ ] `http://localhost:5173` loads the Glassmorphic dashboard
- [ ] The **Market Data** card shows a live SPX price (not 0.00)
- [ ] At least one position is visible in the **Active Trade** card (if `portfolio.json` is populated)
- [ ] Console shows `✅ Antigravity: n8n Workflow ... successfully synced`
- [ ] `python preflight.py --app alpha` passes all checks
- [ ] `python telemetry_dashboard.py` shows all subsystems healthy

---

## 🔄 Updating the Application

### Python Backend

Pull latest changes and reinstall dependencies:

```powershell
pip install -r requirements.txt --upgrade
```

### UI Frontend

```powershell
cd alpha_ui
npm install
cd ..
```

### N8N Workflows

Re-import updated `n8n_blueprint.json` via n8n Cloud → Import from JSON. Existing credentials are preserved.

---

## 🆘 Support & Troubleshooting

See the **Troubleshooting** section in `README.md` for common issues and fixes.

For commercial support, contact the Antigravity AI team.
