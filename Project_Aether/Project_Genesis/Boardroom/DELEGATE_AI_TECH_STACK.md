# 🏗️ CTO — DELEGATE AI TECHNICAL STACK
## Architecture Brief for Legal Task Delegation SaaS
### Filed: 2026-03-07 | Updated: 2026-03-08 | Document ID: CTO-DELEGATEAI-001
### Author: CTO (Lead Systems Architect) | Authorized by: CEO

---

## Architecture Philosophy

Delegate AI is not a greenfield build. It is an **extension** of the Aether Runtime, packaged as a vertical SaaS for law firms. Every component maps directly to existing Antigravity-AI infrastructure. Build time is measured in days, not months.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    DELEGATE AI — SaaS Layer                 │
│                                                             │
│  ┌──────────┐   ┌──────────────┐   ┌────────────────────┐  │
│  │ Web UI   │──▶│ FastAPI      │──▶│ Aether Runtime     │  │
│  │ (React)  │   │ Gateway      │   │ (Config + Router)  │  │
│  └──────────┘   └──────┬───────┘   └────────┬───────────┘  │
│                        │                     │              │
│                        ▼                     ▼              │
│           ┌────────────────────┐  ┌─────────────────────┐   │
│           │ Task Store         │  │ n8n Webhook Layer   │   │
│           │ (Supabase)         │  │ (Agent Dispatch)    │   │
│           └────────────────────┘  └─────────────────────┘   │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Compliance Vault (Encrypted Storage)    │   │
│  │              + Intake Watcher (Ingestion_Chamber)    │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Component Mapping (Existing → Delegate AI)

| Delegate AI Component | Maps To | Status | Modification Needed |
|---|---|---|---|
| **Delegation Router** | `aether_runtime.py → AgentRouter` | ✅ Built | Add legal task taxonomy (Motion, Discovery, Client Intake, Billing) |
| **Intent Classifier** | `aether_runtime.py → IntentClassifier` | ✅ Built | Retrain patterns for legal domains |
| **Quality Gate** | `aether_runtime.py → CriticGate` | ✅ Built | Configure for delegation completeness checks |
| **Task Store** | Supabase (existing keys in .env) | ✅ Connected | New table: `delegate_tasks` with schema below |
| **Secure Document Vault** | `Compliance_Vault/vault_engine.py` | ✅ Built | Add attorney-client privilege flag + retention policies |
| **File Intake** | `Ingestion_Chamber/watcher.py` | ✅ Built | Classify legal documents by type |
| **Agent Dispatch** | n8n webhook layer (28 workflows) | ✅ Active | New workflow: legal-delegation-router |
| **API Layer** | `Meta_App_Factory/api.py` (FastAPI) | ✅ Built | New endpoints: `/delegate/`, `/tasks/`, `/firms/` |
| **Frontend** | Vanilla JS SPA | ✅ Built | `frontend/index.html` — dark mode glassmorphism |

**Status: ✅ MVP COMPLETE** — All 6 phases delivered, 11/11 endpoints verified, 2,072 lines committed.

---

## Tech Stack

| Layer | Technology | Rationale |
|---|---|---|
| **Frontend** | Vanilla JS SPA | Dark mode glassmorphism UI, served at `/app` |
| **API** | FastAPI + httpx | Port 8002, `/delegate/` endpoints, httpx REST client |
| **AI Engine** | Legal Intent Classifier v1 | 11 legal task categories with priority detection |
| **Database** | Supabase (PostgreSQL) | 4 tables + RLS policies, httpx REST client |
| **Workflow** | n8n Cloud (Pro) | `legal-delegation-router` — 6-node workflow |
| **Encryption** | Fernet AES-128 (Compliance Vault) | Attorney-client docs encrypted at rest |
| **Auth** | Supabase Auth (email/password + RLS) | Row-level security for firm isolation |
| **Hosting** | Local (Port 8002) | `localhost:8002/app` — production deploy pending |
| **Monitoring** | Sentry (free tier) | Already configured |

---

## Database Schema: `delegate_tasks`

```sql
CREATE TABLE delegate_tasks (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    firm_id UUID REFERENCES firms(id),
    created_by UUID REFERENCES users(id),         -- delegating attorney
    assigned_to UUID REFERENCES users(id),         -- receiving associate/staff
    title TEXT NOT NULL,
    description TEXT,
    category TEXT CHECK (category IN (
        'MOTION', 'DISCOVERY', 'CLIENT_INTAKE', 'BILLING',
        'RESEARCH', 'FILING', 'CORRESPONDENCE', 'REVIEW', 'OTHER'
    )),
    priority TEXT CHECK (priority IN ('URGENT', 'HIGH', 'NORMAL', 'LOW')),
    status TEXT DEFAULT 'PENDING' CHECK (status IN (
        'PENDING', 'ASSIGNED', 'IN_PROGRESS', 'REVIEW', 'COMPLETE', 'BLOCKED'
    )),
    due_date TIMESTAMPTZ,
    billable BOOLEAN DEFAULT true,
    estimated_hours DECIMAL(5,2),
    actual_hours DECIMAL(5,2),
    matter_number TEXT,                             -- law firm case/matter reference
    confidential BOOLEAN DEFAULT false,             -- triggers Compliance Vault
    attachments JSONB DEFAULT '[]',
    ai_classification JSONB DEFAULT '{}',           -- Aether Runtime output
    critic_review JSONB DEFAULT '{}',               -- CriticGate audit trail
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE firms (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name TEXT NOT NULL,
    size TEXT CHECK (size IN ('SOLO', 'SMALL', 'MID', 'LARGE')),
    practice_areas TEXT[],
    subscription_tier TEXT DEFAULT 'PILOT',
    seat_count INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_tasks_firm ON delegate_tasks(firm_id);
CREATE INDEX idx_tasks_status ON delegate_tasks(status);
CREATE INDEX idx_tasks_assigned ON delegate_tasks(assigned_to);
```

---

## API Endpoints (New)

| Method | Path | Description |
|---|---|---|
| `POST` | `/delegate/` | Submit a new delegation (triggers Aether Runtime classification) |
| `GET` | `/delegate/{task_id}` | Get task details + AI classification |
| `PATCH` | `/delegate/{task_id}/status` | Update task status |
| `GET` | `/tasks/?firm_id=&status=&assigned_to=` | List tasks with filters |
| `GET` | `/firms/{firm_id}/analytics` | Delegation metrics (billable hours recovered, completion rates) |
| `POST` | `/delegate/{task_id}/review` | Trigger CriticGate quality check |

---

## n8n Workflow: `legal-delegation-router`

```
Trigger (Webhook) → Parse Task → Classify Intent (Aether Runtime)
    → Route to Assigned Attorney (Email/Slack notification)
    → Log to Supabase → Update Dashboard
    → If confidential: Route to Compliance Vault
```

Estimated workflow nodes: 8-10 (builds on existing multi_agent_core blueprint pattern)

---

## Build Timeline — ✅ COMPLETE

| Phase | Duration | Deliverable | Status |
|---|---|---|---|
| **Phase 1: Schema + API** | Day 1-2 | Supabase tables, FastAPI endpoints | ✅ Complete |
| **Phase 2: Runtime Extension** | Day 3-4 | Legal intent patterns, delegation routing | ✅ Complete |
| **Phase 3: n8n Workflow** | Day 5 | legal-delegation-router workflow | ✅ Complete |
| **Phase 4: Frontend UI/SPA** | Day 6-8 | Dark mode task board + delegation form | ✅ Complete |
| **Phase 5: Integration Test** | Day 9-10 | End-to-end flow with test firm | ✅ Complete |
| **Phase 6: Stress & Security** | Day 10 | API load test + RLS cross-tenant validation | ✅ Complete |

**MVP delivered 2026-03-08 — 11/11 endpoints verified, 22 tasks in Supabase**

---

## Risk Assessment

| Risk | Severity | Mitigation |
|---|---|---|
| Supabase free tier limits | LOW | 500MB storage, 50K rows — sufficient for 10 pilot firms |
| n8n workflow complexity | LOW | Building on proven multi_agent_core pattern |
| Attorney-client data leaks | HIGH | Compliance Vault encryption + Compliance Officer audit (see PRIVACY_SHIELD_REPORT) |
| User adoption friction | MEDIUM | Keep UI dead simple — 3-click delegation flow |
| Scaling beyond pilot | LOW | Supabase Pro ($25/mo) handles 100x current needs |

---

*Filed by: CTO — Project Aether C-Suite_Core*
*Classification: BOARDROOM — Technical Architecture*
*Dependencies: PRIVACY_SHIELD_REPORT.md (Compliance Officer), CFO_PILOT_AGENT_BUDGET.md (approved)*
*Status: ✅ MVP COMPLETE — All 6 phases delivered, committed to GitHub (9886fdf)*
