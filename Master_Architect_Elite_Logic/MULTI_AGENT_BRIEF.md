# Multi-Agent Brief: Elite Triad Build Protocol

## Overview
This brief defines the collaborative handshake between three Elite C-Suite agents for any new project build in the Meta App Factory ecosystem.

## Agent Roster

| Agent | Port | Role | Accent | Trigger |
|---|---|---|---|---|
| **CMO Agent** | 5020 | GTM Strategy & Audience Persona | Rose/Magenta | `/webhook/cmo-v2` |
| **Master Architect** | 5050 | System Design & Logic Gate | Electric Cyan | `POST /api/review` |
| **Phantom QA** | 5030 | Outcome Validation & UI Testing | Emerald Green | Browser-based test |

## Build Sequence

```
┌─────────────────────────────────────────────────────┐
│  Phase 1: CMO Strategy (Port 5020)                  │
│  Input: Project brief, target audience              │
│  Output: Audience persona, GTM playbook, KPIs       │
│  Webhook: POST /webhook/cmo-v2                      │
├─────────────────────────────────────────────────────┤
│  Phase 2: Master Architect Review (Port 5050)       │
│  Input: CMO strategy + proposed architecture        │
│  Output: Triad score (Structural/Logic/Security)    │
│  API: POST /api/review                              │
│  Gate: AUTO_APPROVE (≥85) | CHALLENGE (60-84)       │
│        | REJECT (<60 → build terminated)            │
├─────────────────────────────────────────────────────┤
│  Phase 3: Factory Construction                      │
│  Input: Architect-approved blueprint                │
│  Output: Complete application directory             │
│  API: POST /api/build/stream (Factory SSE)          │
├─────────────────────────────────────────────────────┤
│  Phase 4: Phantom QA Validation (Port 5030)         │
│  Input: Built application URL                       │
│  Output: Screenshot evidence, pass/fail, score      │
│  Gate: GATE_BLOCKED if score < threshold            │
└─────────────────────────────────────────────────────┘
```

## n8n Workflow Integration

### Existing Workflows
- **Master Architect Elite — Pre-Deploy Gate** (`wunoJBl6p6hfiHOX`) — ACTIVE
- **Gemini Agent Bridge** (`1JjyTk5VwmBItQvG`) — ACTIVE, now with Mandatory Review node

### Webhook Endpoints
```json
{
  "CMO":       "https://humanresource.app.n8n.cloud/webhook/cmo-v2",
  "Architect": "https://humanresource.app.n8n.cloud/webhook/master-architect-review",
  "Critic":    "https://humanresource.app.n8n.cloud/webhook/critic-v2"
}
```

### Institutional Memory
Every build pulls from `GET /api/patterns` to reuse battle-tested code.
Every regression is tracked via `GET /api/regressions`.
Health is pinged every 15 minutes via the Architect Health Cron.

## Sample Build Request
```json
{
  "project_name": "CustomerMetrics",
  "brief": "Real-time B2B customer health dashboard",
  "cmo_strategy": {
    "audience": "SaaS operations managers, 30-45",
    "tone": "professional, data-driven",
    "kpis": ["churn_reduction", "nps_score", "feature_adoption"]
  },
  "architect_review": {
    "description": "React+FastAPI dashboard with Supabase auth",
    "change_type": "new_build",
    "components": ["auth", "dashboard", "api"]
  },
  "phantom_qa": {
    "test_urls": ["http://localhost:5173"],
    "scenarios": ["login_flow", "dashboard_load", "export_csv"]
  }
}
```
