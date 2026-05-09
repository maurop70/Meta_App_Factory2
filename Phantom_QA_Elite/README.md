# Phantom QA Elite

**Autonomous Multi-Agent Quality Assurance Command Center**  
*Antigravity-AI | Port 5030*

## Overview

Phantom QA Elite is a standalone, commercially-viable quality assurance application that automates the roles of a Senior QA Lead, Penetration Tester, and UX Researcher through three specialized AI agents.

## The Three Agents

| Agent | Role | Technology |
|---|---|---|
| 🏗️ **The Architect** | Scans the target app, discovers endpoints via OpenAPI, and generates a comprehensive test plan | Gemini 2.5 Flash |
| 👻 **The Ghost User** | Spawns a Playwright browser as a specific user persona and exercises the UI | Playwright + Gemini 2.5 Flash |
| 🔍 **The Skeptic** | Attacks every API endpoint with edge-case payloads, malformed JSON, and stress tests | aiohttp + Gemini 2.5 Flash |

## Quick Start

```bash
# One-click launch (Windows)
Launch_Phantom_QA.bat

# Manual launch
cd backend
pip install -r requirements.txt
python -m playwright install chromium
python server.py
```

Dashboard: http://localhost:5030

## API Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/health` | GET | Health check |
| `/api/dashboard` | GET | Dashboard stats |
| `/api/pulse` | GET | Scan all C-Suite ports |
| `/api/test/full` | POST | Run full 3-agent test bench |
| `/api/test/architect` | POST | Architect-only test plan |
| `/api/test/ghost` | POST | Ghost User UI test only |
| `/api/test/skeptic` | POST | Skeptic API attack only |
| `/api/reports` | GET | List test history |
| `/api/reports/{id}` | GET | Get specific report |
| `/api/warroom/respond` | POST | War Room protocol |

## War Room Integration

Phantom QA Elite exposes the standardized `/api/warroom/respond` endpoint:

```json
{
  "agent": "Phantom_QA_Elite",
  "role": "Chief Quality Assurance Officer",
  "perspective": "...",
  "confidence": 0.92
}
```

## Architecture

```
Phantom_QA_Elite/
├── Launch_Phantom_QA.bat
├── backend/
│   ├── server.py              (FastAPI, port 5030)
│   ├── memory_store.py        (SQLite persistent memory)
│   ├── warroom_interface.py   (War Room protocol)
│   └── agents/
│       ├── architect.py       (Test Planner)
│       ├── ghost_user.py      (Playwright UI Tester)
│       └── skeptic.py         (API Bug Hunter)
└── frontend/
    ├── index.html
    ├── styles.css
    └── app.js
```

---
*Antigravity-AI | Phantom QA Elite v1.0.0*
