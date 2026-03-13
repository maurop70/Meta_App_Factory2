"""
Delegate AI — API Router
=========================
Project Genesis | Phase 1: Schema + API
FastAPI router providing delegation endpoints.

Uses Supabase REST API directly via httpx (no supabase-py dependency).
Mounts into the existing Meta_App_Factory API as a sub-router,
or runs standalone on port 8002 for development.

Usage:
    Standalone:  python delegate_api.py
    Integrated:  app.include_router(delegate_router, prefix="/delegate")
"""

# ── V3.0 Resilience Integration ──────────────────────────
import os as _os, sys as _sys
_FACTORY_DIR = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
_sys.path.insert(0, _FACTORY_DIR)
try:
    from factory import safe_post
    from local_state_manager import StateManager as _StateManager
    _v3_sm = _StateManager()
    _V3_AVAILABLE = True
except ImportError:
    _V3_AVAILABLE = False
# ── End V3 Integration ──────────────────────────────────

from auto_heal import healed_post, auto_heal, diagnose

def _v3_preflight():
    """V3: Ping Resonance_Watchdog_V3 before execution."""
    if not _V3_AVAILABLE:
        return True
    try:
        import json as _j
        _cfg_path = _os.path.join(_FACTORY_DIR, "resilience_config.json")
        if not _os.path.exists(_cfg_path):
            return True
        with open(_cfg_path) as _f:
            _cfg = _j.load(_f)
        _url = _cfg.get("cloud_health", {}).get("watchdog_url", "")
        if not _url:
            return True
        import requests as _rq
        _r = _rq.get(_url, timeout=5)
        return _r.status_code == 200
    except Exception:
        return False


import os
import sys
import json
import uuid
import httpx
from datetime import datetime, timezone
from typing import Optional, List, Any
from enum import Enum

# ── FastAPI + Pydantic ──
from fastapi import FastAPI, APIRouter, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ── Aether Runtime (for AI classification) ──
RUNTIME_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(RUNTIME_DIR)
sys.path.insert(0, PARENT_DIR)

try:
    from dotenv import load_dotenv
    # Try Project Genesis .env first, fall back to parent
    genesis_env = os.path.join(RUNTIME_DIR, ".env")
    parent_env = os.path.join(PARENT_DIR, "..", ".env")
    if os.path.exists(genesis_env):
        load_dotenv(genesis_env)
    elif os.path.exists(parent_env):
        load_dotenv(parent_env)
except ImportError:
    pass

try:
    from aether_runtime import ConfigLoader, AgentRouter, IntentClassifier
    RUNTIME_AVAILABLE = True
except ImportError:
    RUNTIME_AVAILABLE = False
    print("[WARNING] Aether Runtime not available -- AI classification uses built-in legal classifier")

try:
    from delegation_router import delegation_router as _del_router, confidentiality_router as _conf_router
    ROUTER_AVAILABLE = True
except ImportError:
    ROUTER_AVAILABLE = False
    _del_router = None
    _conf_router = None


# ══════════════════════════════════════════════════
#  SUPABASE REST CLIENT (via httpx)
# ══════════════════════════════════════════════════

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY", "")

class SupabaseClient:
    """Lightweight Supabase REST client using httpx. No supabase-py dependency."""

    def __init__(self, url: str, key: str):
        self.base_url = url.rstrip("/")
        self.rest_url = f"{self.base_url}/rest/v1"
        self.key = key
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        self._client = httpx.Client(timeout=15.0)

    def _request(self, method: str, table: str, params: dict = None, json_data: Any = None, extra_headers: dict = None) -> dict:
        url = f"{self.rest_url}/{table}"
        headers = {**self.headers}
        if extra_headers:
            headers.update(extra_headers)
        resp = self._client.request(method, url, params=params, json=json_data, headers=headers)
        if resp.status_code >= 400:
            raise HTTPException(status_code=resp.status_code, detail=f"Supabase error: {resp.text}")
        try:
            return resp.json() if resp.text else []
        except Exception:
            return []

    def select(self, table: str, columns: str = "*", filters: dict = None, order: str = None, limit: int = None, offset: int = None) -> list:
        params = {"select": columns}
        if filters:
            for k, v in filters.items():
                params[k] = f"eq.{v}"
        if order:
            params["order"] = order
        if limit:
            headers = {**self.headers, "Range": f"{offset or 0}-{(offset or 0) + limit - 1}"}
        else:
            headers = self.headers
        return self._request("GET", table, params=params, extra_headers=headers if limit else None)

    def insert(self, table: str, data: dict) -> list:
        return self._request("POST", table, json_data=data)

    def update(self, table: str, data: dict, match: dict) -> list:
        params = {}
        for k, v in match.items():
            params[k] = f"eq.{v}"
        return self._request("PATCH", table, params=params, json_data=data)

    def health_check(self) -> bool:
        try:
            resp = self._client.get(f"{self.base_url}/rest/v1/", headers=self.headers, params={"select": "1"})
            return resp.status_code < 500
        except Exception:
            return False


# Initialize client
db: Optional[SupabaseClient] = None
if SUPABASE_URL and SUPABASE_KEY:
    _candidate = SupabaseClient(SUPABASE_URL, SUPABASE_KEY)
    # Check if tables exist before committing to SUPABASE mode
    try:
        _candidate.select("delegate_tasks", limit=1)
        db = _candidate
        print(f"[OK] Supabase connected: {SUPABASE_URL}")
    except Exception as _e:
        err_str = str(_e)
        if "PGRST205" in err_str or "Could not find" in err_str:
            print(f"[INFO] Supabase reachable but tables not created yet.")
            print("       Run 001_delegate_schema.sql in Supabase SQL Editor.")
            print("       Falling back to LOCAL MODE (in-memory).")
            db = None
        elif "401" in err_str or "403" in err_str:
            print(f"[WARN] Supabase auth failed -- check SUPABASE_KEY. Falling back to LOCAL.")
            db = None
        else:
            # Some other error, try local mode
            print(f"[WARN] Supabase error: {err_str[:100]}. Falling back to LOCAL.")
            db = None
else:
    print("[INFO] Running in LOCAL MODE -- no Supabase connection")
    print("   Set SUPABASE_URL and SUPABASE_KEY in .env to enable database")


# ══════════════════════════════════════════════════
#  LOCAL STORAGE FALLBACK
#  When Supabase isn't configured, use in-memory store
# ══════════════════════════════════════════════════

LOCAL_TASKS = []
LOCAL_FIRMS = [{
    "id": "00000000-0000-0000-0000-000000000001",
    "name": "Antigravity Test Firm",
    "size": "SMALL",
    "practice_areas": ["General Practice", "Technology Law"],
    "subscription_tier": "PILOT",
    "seat_count": 5,
    "contact_email": "executive@antigravity.ai",
    "created_at": datetime.now(timezone.utc).isoformat(),
}]
LOCAL_ACTIVITY = []


# ══════════════════════════════════════════════════
#  ENUMS & MODELS
# ══════════════════════════════════════════════════

class TaskCategory(str, Enum):
    MOTION = "MOTION"
    DISCOVERY = "DISCOVERY"
    CLIENT_INTAKE = "CLIENT_INTAKE"
    BILLING = "BILLING"
    RESEARCH = "RESEARCH"
    FILING = "FILING"
    CORRESPONDENCE = "CORRESPONDENCE"
    REVIEW = "REVIEW"
    CONTRACT = "CONTRACT"
    COMPLIANCE = "COMPLIANCE"
    OTHER = "OTHER"

class TaskPriority(str, Enum):
    URGENT = "URGENT"
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"

class TaskStatus(str, Enum):
    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    REVIEW = "REVIEW"
    COMPLETE = "COMPLETE"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"


class DelegationRequest(BaseModel):
    prompt: str = Field(..., description="Natural language delegation")
    firm_id: str = Field(default="00000000-0000-0000-0000-000000000001")
    created_by: Optional[str] = None
    assigned_to: Optional[str] = None
    matter_number: Optional[str] = None
    due_date: Optional[str] = None
    confidential: bool = False
    skip_ai: bool = False


class TaskUpdateRequest(BaseModel):
    status: Optional[TaskStatus] = None
    assigned_to: Optional[str] = None
    priority: Optional[TaskPriority] = None
    actual_hours: Optional[float] = None
    notes: Optional[str] = None


class FirmCreateRequest(BaseModel):
    name: str
    size: str = "SMALL"
    practice_areas: List[str] = []
    contact_email: Optional[str] = None
    contact_name: Optional[str] = None
    seat_count: int = 1


# ══════════════════════════════════════════════════
#  LEGAL INTENT CLASSIFIER
# ══════════════════════════════════════════════════

LEGAL_PATTERNS = {
    TaskCategory.MOTION: [
        "motion", "brief", "memorandum", "summary judgment", "dismiss",
        "injunction", "suppress", "compel", "reconsider",
    ],
    TaskCategory.DISCOVERY: [
        "discovery", "interrogator", "deposition", "subpoena", "document request",
        "production", "rfi", "rog", "admission",
    ],
    TaskCategory.CLIENT_INTAKE: [
        "intake", "new client", "onboarding", "engagement letter",
        "retainer agreement", "conflict check",
    ],
    TaskCategory.BILLING: [
        "bill", "invoice", "timesheet", "hours", "fee",
        "retainer", "payment", "accounts receivable",
    ],
    TaskCategory.RESEARCH: [
        "research", "case law", "statute", "precedent", "analyze",
        "westlaw", "lexis", "memo",
    ],
    TaskCategory.FILING: [
        "file", "filing", "court", "efile", "serve", "service",
        "clerk", "deadline", "docket",
    ],
    TaskCategory.CORRESPONDENCE: [
        "letter", "email", "draft", "respond", "correspondence",
        "communicate", "notify", "send",
    ],
    TaskCategory.REVIEW: [
        "review", "proofread", "edit", "revise", "redline",
        "comment", "approve", "sign off",
    ],
    TaskCategory.CONTRACT: [
        "contract", "agreement", "lease", "nda", "terms",
        "negotiate", "clause", "amendment",
    ],
    TaskCategory.COMPLIANCE: [
        "compliance", "regulatory", "audit", "ethics",
        "conflict", "reporting", "disclosure",
    ],
}

PRIORITY_SIGNALS = {
    TaskPriority.URGENT: ["urgent", "asap", "immediately", "emergency", "rush", "critical", "today"],
    TaskPriority.HIGH: ["high priority", "important", "soon", "this week", "expedite"],
    TaskPriority.LOW: ["low priority", "when you can", "no rush", "whenever", "backlog"],
}


def classify_legal_task(prompt: str) -> dict:
    """Classify a natural-language delegation into category + priority."""
    prompt_lower = prompt.lower()

    # Category
    category_scores = {}
    for category, keywords in LEGAL_PATTERNS.items():
        score = sum(1 for kw in keywords if kw in prompt_lower)
        if score > 0:
            category_scores[category.value] = score

    if category_scores:
        best_category = max(category_scores, key=category_scores.get)
        confidence = min(category_scores[best_category] / 3.0, 1.0)
    else:
        best_category = TaskCategory.OTHER.value
        confidence = 0.1

    # Priority
    detected_priority = TaskPriority.NORMAL.value
    for priority, signals in PRIORITY_SIGNALS.items():
        if any(s in prompt_lower for s in signals):
            detected_priority = priority.value
            break

    # Title
    title = prompt.split(".")[0].split(",")[0].strip()
    if len(title) > 80:
        title = title[:77] + "..."

    return {
        "category": best_category,
        "priority": detected_priority,
        "title": title,
        "confidence": round(confidence, 2),
        "all_scores": dict(sorted(category_scores.items(), key=lambda x: -x[1])),
        "classifier": "legal_intent_v1",
        "classified_at": datetime.now(timezone.utc).isoformat(),
    }


# ══════════════════════════════════════════════════
#  API ROUTER — DELEGATION
# ══════════════════════════════════════════════════

delegate_router = APIRouter(tags=["Delegate AI"])


@delegate_router.get("/info")
async def delegate_root():
    """Delegate AI service info."""
    return {
        "service": "Delegate AI — Legal Task Delegation API",
        "version": "1.0.0",
        "phase": "MVP Phase 1",
        "mode": "SUPABASE" if db else "LOCAL",
        "endpoints": {
            "POST /delegate/": "Submit a natural-language delegation",
            "GET /delegate/{task_id}": "Get task details",
            "PATCH /delegate/{task_id}": "Update task",
            "GET /delegate/tasks": "List tasks with filters",
            "GET /firms/{firm_id}/analytics": "Firm analytics",
            "POST /firms/": "Create a new firm",
        },
    }


@delegate_router.post("/")
async def create_delegation(request: DelegationRequest):
    """
    Submit a natural-language delegation.
    
    Example:
        POST /delegate/
        {"prompt": "Draft the Smith discovery response, assign to Sarah, due Friday, bill to matter 2024-0847"}
    """
    # Step 1: AI Classification
    if request.skip_ai:
        classification = {
            "category": "OTHER", "priority": "NORMAL",
            "title": request.prompt[:80], "confidence": 0.0,
            "classifier": "manual", "classified_at": datetime.now(timezone.utc).isoformat(),
        }
    else:
        classification = classify_legal_task(request.prompt)

    # Step 2: Build task record
    task_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    task = {
        "id": task_id,
        "firm_id": request.firm_id,
        "title": classification["title"],
        "description": request.prompt,
        "original_prompt": request.prompt,
        "category": classification["category"],
        "priority": classification["priority"],
        "status": TaskStatus.ASSIGNED.value if request.assigned_to else TaskStatus.PENDING.value,
        "billable": True,
        "confidential": request.confidential,
        "matter_number": request.matter_number,
        "ai_classification": classification,
        "created_at": now,
        "updated_at": now,
    }
    if request.created_by:
        task["created_by"] = request.created_by
    if request.assigned_to:
        task["assigned_to"] = request.assigned_to
    if request.due_date:
        task["due_date"] = request.due_date

    # Step 3: Store
    if db:
        try:
            result = db.insert("delegate_tasks", task)
            stored = result[0] if isinstance(result, list) and result else task
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    else:
        stored = task
        LOCAL_TASKS.append(task)

    # Step 4: Log activity
    activity = {
        "id": str(uuid.uuid4()),
        "task_id": task_id,
        "firm_id": request.firm_id,
        "action": "CREATED",
        "new_value": classification["category"],
        "metadata": json.dumps({"classification": classification}),
        "created_at": now,
    }
    if db:
        try:
            db.insert("task_activity", activity)
        except Exception:
            pass
    else:
        LOCAL_ACTIVITY.append(activity)

    # Step 5: Route to agent (Phase 2)
    routing = None
    if ROUTER_AVAILABLE and _del_router:
        routing = _del_router.route(classification["category"], classification["priority"])
        _del_router.log_to_boardroom(task_id, routing, request.prompt)

    return {
        "status": "delegated",
        "task": stored,
        "classification": classification,
        "routing": routing,
    }


@delegate_router.get("/tasks", name="list_tasks")
async def list_tasks(
    firm_id: str = Query(default="00000000-0000-0000-0000-000000000001"),
    status: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = Query(default=50, le=200),
):
    """List tasks with filters."""
    if db:
        filters = {"firm_id": firm_id}
        if status:
            filters["status"] = status
        if category:
            filters["category"] = category
        try:
            tasks = db.select("delegate_tasks", filters=filters, order="created_at.desc", limit=limit)
            return {"tasks": tasks, "count": len(tasks)}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        tasks = [t for t in LOCAL_TASKS if t.get("firm_id") == firm_id]
        if status:
            tasks = [t for t in tasks if t.get("status") == status]
        if category:
            tasks = [t for t in tasks if t.get("category") == category]
        return {"tasks": tasks[:limit], "count": len(tasks)}


@delegate_router.get("/{task_id}")
async def get_task(task_id: str):
    """Get task details + activity log."""
    if db:
        try:
            tasks = db.select("delegate_tasks", filters={"id": task_id})
            if not tasks:
                raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
            task = tasks[0]
            activity = db.select("task_activity", filters={"task_id": task_id}, order="created_at.asc")
            task["activity_log"] = activity
            return task
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        task = next((t for t in LOCAL_TASKS if t["id"] == task_id), None)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        task["activity_log"] = [a for a in LOCAL_ACTIVITY if a["task_id"] == task_id]
        return task


@delegate_router.patch("/{task_id}")
async def update_task(task_id: str, request: TaskUpdateRequest):
    """Update task fields."""
    if db:
        existing = db.select("delegate_tasks", filters={"id": task_id})
        if not existing:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        task = existing[0]
    else:
        task = next((t for t in LOCAL_TASKS if t["id"] == task_id), None)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    updates = {}
    if request.status and request.status.value != task.get("status"):
        updates["status"] = request.status.value
        if request.status == TaskStatus.COMPLETE:
            updates["completed_at"] = datetime.now(timezone.utc).isoformat()
    if request.assigned_to:
        updates["assigned_to"] = request.assigned_to
    if request.priority:
        updates["priority"] = request.priority.value
    if request.actual_hours is not None:
        updates["actual_hours"] = request.actual_hours
    if request.notes:
        existing_notes = task.get("notes") or []
        if isinstance(existing_notes, str):
            existing_notes = json.loads(existing_notes) if existing_notes else []
        existing_notes.append({"text": request.notes, "timestamp": datetime.now(timezone.utc).isoformat()})
        updates["notes"] = existing_notes

    if not updates:
        return {"status": "no_changes", "task_id": task_id}

    if db:
        try:
            result = db.update("delegate_tasks", updates, {"id": task_id})
            return {"status": "updated", "task_id": task_id, "changes": list(updates.keys()), "task": result[0] if result else None}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        task.update(updates)
        return {"status": "updated", "task_id": task_id, "changes": list(updates.keys()), "task": task}




# ══════════════════════════════════════════════════
#  FIRMS ENDPOINTS
# ══════════════════════════════════════════════════

firms_router = APIRouter(prefix="/firms", tags=["Firms"])


@firms_router.post("/")
async def create_firm(request: FirmCreateRequest):
    """Create a new law firm."""
    firm = {
        "id": str(uuid.uuid4()),
        "name": request.name,
        "size": request.size,
        "practice_areas": request.practice_areas,
        "subscription_tier": "PILOT",
        "seat_count": request.seat_count,
        "contact_email": request.contact_email,
        "contact_name": request.contact_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if db:
        try:
            result = db.insert("firms", firm)
            return {"status": "created", "firm": result[0] if isinstance(result, list) and result else firm}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        LOCAL_FIRMS.append(firm)
        return {"status": "created", "firm": firm}


@firms_router.get("/{firm_id}")
async def get_firm(firm_id: str):
    """Get firm details."""
    if db:
        try:
            firms = db.select("firms", filters={"id": firm_id})
            if not firms:
                raise HTTPException(status_code=404, detail="Firm not found")
            return firms[0]
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        firm = next((f for f in LOCAL_FIRMS if f["id"] == firm_id), None)
        if not firm:
            raise HTTPException(status_code=404, detail="Firm not found")
        return firm


@firms_router.get("/{firm_id}/analytics")
async def firm_analytics(firm_id: str):
    """Delegation analytics — billable hours, completion rates, category breakdown."""
    if db:
        try:
            all_tasks = db.select("delegate_tasks", filters={"firm_id": firm_id})
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        all_tasks = [t for t in LOCAL_TASKS if t.get("firm_id") == firm_id]

    total = len(all_tasks)
    if total == 0:
        return {"firm_id": firm_id, "total_tasks": 0, "message": "No tasks yet. Start delegating!"}

    completed = [t for t in all_tasks if t.get("status") == "COMPLETE"]
    billable_hours = sum(float(t.get("actual_hours") or 0) for t in all_tasks if t.get("billable"))
    categories = {}
    for t in all_tasks:
        cat = t.get("category", "OTHER")
        categories[cat] = categories.get(cat, 0) + 1

    return {
        "firm_id": firm_id,
        "total_tasks": total,
        "completed": len(completed),
        "completion_rate": round(len(completed) / total * 100, 1),
        "billable_hours_tracked": round(billable_hours, 2),
        "category_breakdown": dict(sorted(categories.items(), key=lambda x: -x[1])),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ══════════════════════════════════════════════════
#  APP
# ══════════════════════════════════════════════════

app = FastAPI(
    title="Delegate AI — Legal Task Delegation API",
    description="AI-powered task delegation for law firms. Part of the Aether Runtime.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(delegate_router, prefix="/delegate")
app.include_router(firms_router)

# Serve frontend
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

FRONTEND_DIR = os.path.join(RUNTIME_DIR, "frontend")
if os.path.isdir(FRONTEND_DIR):
    @app.get("/app")
    async def serve_frontend():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
async def root():
    return {
        "service": "Delegate AI API",
        "version": "1.0.0",
        "project": "Project Genesis — Aether Runtime",
        "mode": "SUPABASE" if db else "LOCAL",
        "endpoints": ["/delegate/", "/firms/", "/health", "/docs"],
    }


@app.get("/health")
async def health():
    """Service health check."""
    supabase_ok = db.health_check() if db else False
    return {
        "status": "healthy",
        "checks": {
            "api": "[OK] Active",
            "supabase": "[OK] Connected" if supabase_ok else ("[WARN] Configured but unreachable" if db else "[--] Local mode"),
            "aether_runtime": "[OK] Available" if RUNTIME_AVAILABLE else "[--] Not loaded",
            "classifier": "[OK] Legal Intent v1 (11 categories)",
        },
        "mode": "SUPABASE" if db else "LOCAL",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ══════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="Delegate AI API")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8002)
    args = parser.parse_args()

    print("\n" + "=" * 55)
    print("  DELEGATE AI — Legal Task Delegation API")
    print("  Project Genesis | Aether Runtime")
    print("=" * 55)
    print(f"\n[>] Server:       http://localhost:{args.port}")
    print(f"[>] API Docs:     http://localhost:{args.port}/docs")
    print(f"[>] Health:       http://localhost:{args.port}/health")
    print(f"[>] Delegate:     POST http://localhost:{args.port}/delegate/")
    print(f"[>] Analytics:    GET  http://localhost:{args.port}/firms/{{firm_id}}/analytics")
    print(f"[>] Mode:         {'SUPABASE' if db else 'LOCAL (in-memory)'}\n")

    uvicorn.run(app, host=args.host, port=args.port)
# V3 AUTO-HEAL ACTIVE
