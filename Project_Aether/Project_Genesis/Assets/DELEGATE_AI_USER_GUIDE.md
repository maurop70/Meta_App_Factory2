# DELEGATE AI — USER GUIDE
### Version 1.1.0 | Updated: 2026-03-08
### Product of Antigravity-AI | Powered by Project Aether

---

## Table of Contents

1. [Quick Start (2 Minutes)](#quick-start)
2. [System Requirements](#system-requirements)
3. [Creating Delegations](#creating-delegations)
4. [Task Categories](#task-categories)
5. [Priority & Routing](#priority--routing)
6. [Task Board (Frontend)](#task-board-frontend)
7. [API Reference](#api-reference)
8. [Analytics](#analytics)
9. [Security & Compliance](#security--compliance)
10. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Step 1: Install Dependencies

```bash
cd Project_Aether/Project_Genesis
pip install -r requirements.txt
```

Required packages: `fastapi`, `uvicorn`, `python-dotenv`, `httpx`

### Step 2: Configure Environment

Create a `.env` file in the `Project_Genesis` directory (or use the parent `Meta_App_Factory/.env`):

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-or-service-role-key
```

> **Note:** Without Supabase credentials, the API runs in LOCAL mode (in-memory storage — data resets on restart).

### Step 3: Launch

```bash
python delegate_api.py
```

Or use the batch launcher:

```bash
Launch_DelegateAI.bat
```

### Step 4: Access

| Service | URL |
|---------|-----|
| **Frontend (Task Board)** | http://localhost:8002/app |
| **API Documentation** | http://localhost:8002/docs |
| **Health Check** | http://localhost:8002/health |

---

## System Requirements

| Requirement | Minimum |
|-------------|---------|
| Python | 3.9+ |
| OS | Windows 10+, macOS, Linux |
| Port | 8002 (configurable via `--port`) |
| Database | Supabase (free tier) or LOCAL mode |
| Browser | Chrome, Firefox, Edge (modern) |

---

## Creating Delegations

Delegate AI accepts **natural language** task descriptions. The AI classifier automatically detects the task category, priority, and key details.

### Via Frontend

1. Open http://localhost:8002/app
2. Type your delegation in the input field:
   > *"Draft the Smith discovery response, assign to Sarah, due Friday, bill to matter 2024-0847"*
3. Review the AI classification preview (category, priority, confidence)
4. Click **Delegate**

### Via API

```bash
curl -X POST http://localhost:8002/delegate/ \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "URGENT: File motion to compel in the Johnson case",
    "firm_id": "00000000-0000-0000-0000-000000000001"
  }'
```

### Delegation Fields

| Field | Required | Description |
|-------|----------|-------------|
| `prompt` | **Yes** | Natural language description of the task |
| `firm_id` | No | UUID of the firm (defaults to test firm) |
| `created_by` | No | UUID of the delegating attorney |
| `assigned_to` | No | UUID of the receiving associate |
| `matter_number` | No | Case/matter reference for billing |
| `due_date` | No | Deadline (ISO 8601 format) |
| `confidential` | No | `true` triggers Compliance Vault routing |
| `skip_ai` | No | `true` bypasses AI classification |

---

## Task Categories

The Legal Intent Classifier v1 recognizes **11 task categories** with confidence scoring:

| Category | Trigger Keywords | Example |
|----------|-----------------|---------|
| **MOTION** | motion, file, compel, dismiss, suppress | *"File motion to compel discovery"* |
| **DISCOVERY** | discovery, interrogatories, deposition, subpoena | *"Draft Smith discovery response"* |
| **CLIENT_INTAKE** | intake, onboard, new client, engagement | *"Process new client intake for Jones"* |
| **BILLING** | invoice, bill, hours, payment, retainer | *"Send invoice for March billable hours"* |
| **RESEARCH** | research, case law, precedent, analyze | *"Research precedent for employment claim"* |
| **FILING** | file, court, submit, deadline, e-file | *"Submit filing with the clerk by 5pm"* |
| **CORRESPONDENCE** | letter, email, respond, notify, draft | *"Draft response letter to opposing counsel"* |
| **REVIEW** | review, revise, edit, proofread, redline | *"Review the Johnson contract for errors"* |
| **CONTRACT** | contract, NDA, agreement, clause, terms | *"Redline the NDA, fix indemnity clause"* |
| **COMPLIANCE** | compliance, regulation, audit, policy | *"Run quarterly compliance audit"* |
| **OTHER** | *(fallback)* | Tasks not matching any specific category |

### Priority Detection

The classifier also detects priority from language:

| Priority | Triggers |
|----------|----------|
| **URGENT** | "urgent", "immediately", "ASAP", "emergency", "rush" |
| **HIGH** | "important", "priority", "critical", "time-sensitive" |
| **NORMAL** | Default for all tasks |
| **LOW** | "when you can", "low priority", "no rush", "whenever" |

---

## Priority & Routing

When the Delegation Router is active, tasks are automatically routed to C-Suite agents based on category:

| Category | Routed To | SLA |
|----------|-----------|-----|
| MOTION | CTO | 2 hours (URGENT) / 24 hours |
| DISCOVERY | Deep_Crawler | 4 hours (URGENT) / 48 hours |
| CLIENT_INTAKE | CEO | 1 hour (URGENT) / 24 hours |
| BILLING | CFO | 4 hours (URGENT) / 48 hours |
| RESEARCH | Researcher | 8 hours (URGENT) / 72 hours |
| FILING | CTO | 1 hour (URGENT) / 24 hours |
| CORRESPONDENCE | Presentation_Expert | 4 hours / 48 hours |
| REVIEW | The_Critic | 4 hours / 48 hours |
| CONTRACT | Compliance_Officer | 4 hours / 48 hours |
| COMPLIANCE | Compliance_Officer | 2 hours / 24 hours |
| OTHER | CEO | 4 hours / 48 hours |

### Escalation Rules

- **URGENT** tasks escalate to the **CEO** if not acknowledged within 1 hour
- **Confidential** tasks route through the **Compliance Vault** with encrypted audit logging
- All delegations are logged to the **Boardroom Exchange** for transparency

---

## Task Board (Frontend)

The frontend at `http://localhost:8002/app` provides:

### Features
- **Delegation Form** — Natural language input with AI classification preview
- **Task Board** — All active tasks with priority color coding
- **Filter Bar** — Filter by status, category, or priority
- **Analytics** — Total tasks, completion rates, category breakdown
- **Agent Routing** — See which C-Suite agent handles each task
- **Toast Notifications** — Live feedback on delegation success/failure

### Task Status Flow

```
PENDING → ASSIGNED → IN_PROGRESS → REVIEW → COMPLETE
                                          ↘ BLOCKED
                                          ↘ CANCELLED
```

### Priority Color Coding

| Priority | Color |
|----------|-------|
| URGENT | 🔴 Red |
| HIGH | 🟠 Orange |
| NORMAL | 🔵 Blue |
| LOW | ⚪ Gray |

---

## API Reference

Base URL: `http://localhost:8002`

### Core Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | System health + Supabase connection status |
| `GET` | `/delegate/info` | Service info + version + mode |
| `POST` | `/delegate/` | Submit a new delegation |
| `GET` | `/delegate/tasks` | List tasks (with filters) |
| `GET` | `/delegate/{task_id}` | Get task details + activity log |
| `PATCH` | `/delegate/{task_id}` | Update task (status, hours, notes) |
| `POST` | `/delegate/route` | Get routing info for a category |

### Firm Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/firms/` | Create a new firm |
| `GET` | `/firms/{firm_id}` | Get firm details |
| `GET` | `/firms/{firm_id}/analytics` | Delegation analytics for a firm |

### Example: List Tasks with Filters

```bash
# All tasks for the default firm
curl http://localhost:8002/delegate/tasks

# Filter by status
curl "http://localhost:8002/delegate/tasks?status=IN_PROGRESS"

# Filter by category
curl "http://localhost:8002/delegate/tasks?category=MOTION"

# Combined filters with limit
curl "http://localhost:8002/delegate/tasks?status=PENDING&category=DISCOVERY&limit=10"
```

### Example: Update a Task

```bash
curl -X PATCH http://localhost:8002/delegate/{task_id} \
  -H "Content-Type: application/json" \
  -d '{
    "status": "COMPLETE",
    "actual_hours": 3.5,
    "notes": "Discovery response filed with court"
  }'
```

### Example: Firm Analytics

```bash
curl http://localhost:8002/firms/00000000-0000-0000-0000-000000000001/analytics
```

Returns:
```json
{
  "firm_id": "00000000-0000-0000-0000-000000000001",
  "total_tasks": 22,
  "by_status": { "PENDING": 12, "IN_PROGRESS": 5, "COMPLETE": 5 },
  "by_category": { "DISCOVERY": 6, "MOTION": 4, "BILLING": 3, ... },
  "completion_rate": 0.23,
  "avg_hours": 2.8
}
```

---

## Analytics

### Metrics Available

| Metric | Source | Description |
|--------|--------|-------------|
| Total Tasks | `/firms/{id}/analytics` | Count of all delegations |
| Completion Rate | `/firms/{id}/analytics` | Percentage of tasks marked COMPLETE |
| Category Breakdown | `/firms/{id}/analytics` | Tasks grouped by legal category |
| Status Distribution | `/firms/{id}/analytics` | Tasks by status (PENDING, IN_PROGRESS, etc.) |
| Average Hours | `/firms/{id}/analytics` | Mean actual hours per completed task |
| Billable Recovery | Frontend dashboard | Estimated hours recovered via delegation |

---

## Security & Compliance

### Privacy Shield (5 Layers)

| Layer | Protection | Status |
|-------|-----------|--------|
| 1. Data Minimization | AI only processes task metadata | ✅ Active |
| 2. Encryption at Rest | Fernet AES-128 in Compliance Vault | ✅ Active |
| 3. Transport Security | TLS 1.3 + rate limiting | ✅ Active |
| 4. Firm Isolation | Supabase Row-Level Security (RLS) | ✅ Active |
| 5. AI Restrictions | No training on data, stateless inference | ✅ Active |

### Compliance
- **ABA Model Rule 1.6** — Confidentiality ✅ Compliant
- **Audit Trail** — Every delegation logged to Boardroom Exchange
- **Confidential Tasks** — Routed through encrypted Compliance Vault
- **Data Retention** — Auto-deletion policies in place

---

## Troubleshooting

### API Won't Start

```
Error: SUPABASE_URL not set
```
**Fix:** Create a `.env` file with your Supabase credentials, or run in LOCAL mode (no `.env` needed — data stored in memory).

### "LOCAL mode" Warning

```
WARNING: Running in LOCAL mode (in-memory storage)
```
**This is normal** if no Supabase credentials are configured. Data will not persist between restarts. Add `.env` credentials for persistent storage.

### Port Already in Use

```
ERROR: [Errno 10048] Address already in use
```
**Fix:** Another process is using port 8002. Either stop it or use a different port:
```bash
python delegate_api.py --port 8003
```

### Frontend Not Loading

If `http://localhost:8002/app` shows a blank page:
1. Verify the API is running (`/health` returns `healthy`)
2. Check that `frontend/index.html` exists in the Project_Genesis directory
3. Try a hard refresh (Ctrl+Shift+R)

### Classification Wrong

If the AI classifier assigns the wrong category:
- Add more specific keywords to your delegation prompt
- Use `"skip_ai": true` in the API request to bypass classification and manually set the category

---

## Files Reference

| File | Purpose |
|------|---------|
| `delegate_api.py` | Main API server (FastAPI, 715 lines) |
| `delegation_router.py` | C-Suite agent routing engine (221 lines) |
| `frontend/index.html` | Task board SPA (425 lines) |
| `n8n/legal_delegation_router.json` | n8n workflow definition |
| `supabase/001_delegate_schema.sql` | Database schema (4 tables + seed data) |
| `requirements.txt` | Python dependencies |
| `Launch_DelegateAI.bat` | Windows launcher script |
| `.env` | Supabase credentials (not committed) |

---

*© 2026 Antigravity-AI. All rights reserved.*
*Delegate AI v1.1.0 | Powered by Project Aether | Privacy Shield: CLEARED*
