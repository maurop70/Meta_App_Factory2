"""
server.py — GeoTalent Scout FastAPI Backend
=============================================
Project Aether | Meta_App_Factory | GeoTalent-Scout
Port: 8080

Endpoints:
  POST /api/scout           — Run full scouting pipeline
  GET  /api/employees       — List internal employee database
  POST /api/trigger-workflow — Trigger the drive_manager_workflow
  GET  /api/health          — Health check
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
import logging
from datetime import datetime, timezone

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi import FastAPI, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional

# ── Path Setup ────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FACTORY_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
ROOT_DIR = os.path.abspath(os.path.join(FACTORY_DIR, ".."))

sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, FACTORY_DIR)

# Load .env files (root + factory)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT_DIR, ".env"))
    load_dotenv(os.path.join(FACTORY_DIR, ".env"))
except ImportError:
    pass

from scouting_logic import GeoTalentScout

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("GeoTalent")

# ══════════════════════════════════════════════════════════════
#  APP INIT
# ══════════════════════════════════════════════════════════════

app = FastAPI(
    title="GeoTalent Scout API",
    description="Aether-based agentic talent scouting service",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5179",
        "http://localhost:8080",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize scout engine
scout_engine = GeoTalentScout()

# In-memory cache for last scout results (used by CSV export)
_last_scout_result = {"candidates": [], "summary": {}}

# ══════════════════════════════════════════════════════════════
#  REQUEST MODELS
# ══════════════════════════════════════════════════════════════

class ScoutRequest(BaseModel):
    role_title: str
    location: str
    job_description: str

class WorkflowTriggerRequest(BaseModel):
    action: str = "ensure_folder"  # ensure_folder | upload_file
    folder_name: Optional[str] = None
    parent_path: Optional[str] = None
    file_name: Optional[str] = None
    file_content: Optional[str] = None
    parent_id: Optional[str] = None

# ══════════════════════════════════════════════════════════════
#  ENDPOINTS
# ══════════════════════════════════════════════════════════════

@app.get("/")
def root():
    return {
        "service": "GeoTalent Scout",
        "version": "1.0.0",
        "status": "operational",
        "parent": "Project_Aether",
        "port": 8080,
        "endpoints": {
            "scout": "POST /api/scout",
            "employees": "GET /api/employees",
            "export_csv": "GET /api/export/csv",
            "upload_roster": "POST /api/upload-roster",
            "trigger_workflow": "POST /api/trigger-workflow",
            "health": "GET /api/health",
        },
    }


@app.post("/api/scout")
def run_scout(req: ScoutRequest):
    """
    Run the full scouting pipeline:
    1. Extract keywords + certifications from job description
    2. Search external candidates (SerpApi stub)
    3. Cross-reference internal employee database
    4. Return ranked candidate list
    """
    try:
        result = scout_engine.scout(req.role_title, req.location, req.job_description)
        # Cache results for CSV export
        _last_scout_result["candidates"] = result.get("candidates", [])
        _last_scout_result["summary"] = result.get("summary", {})
        _last_scout_result["role"] = req.role_title
        _last_scout_result["location"] = req.location
        return result
    except Exception as e:
        logger.error("Scout failed: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/employees")
def list_employees(search: Optional[str] = None):
    """List internal employees, optionally filtered by search query."""
    employees = scout_engine.get_all_employees()

    if search:
        q = search.lower()
        employees = [
            e for e in employees
            if q in e.get("Full Name", "").lower()
            or q in e.get("Home Email", "").lower()
            or q in e.get("Job Title", "").lower()
            or q in e.get("Mobile Phone", "").lower()
        ]

    return {
        "total": len(employees),
        "employees": employees,
    }


@app.post("/api/trigger-workflow")
def trigger_workflow(req: WorkflowTriggerRequest):
    """
    Trigger the drive_manager_workflow.json via n8n webhook.
    Actions: ensure_folder, upload_file
    """
    webhook_url = os.getenv("WEBHOOK_URL", "https://humanresource.app.n8n.cloud/webhook/drive-manager")

    try:
        payload = {
            "action": req.action,
            "folder_name": req.folder_name,
            "parent_path": req.parent_path,
            "file_name": req.file_name,
            "file_content": req.file_content,
            "parent_id": req.parent_id,
        }
        # Remove None values
        payload = {k: v for k, v in payload.items() if v is not None}

        _v3_status = healed_post(webhook_url, payload)


        resp = type("Resp", (), {"status_code": 200 if _v3_status == "sent" else 503, "ok": _v3_status == "sent", "text": _v3_status, "json": lambda: {"status": _v3_status}})()
        return {
            "status": "triggered",
            "webhook_url": webhook_url,
            "action": req.action,
            "response_code": resp.status_code,
            "response_body": resp.text[:500] if resp.text else "",
        }
    except ImportError:
        return JSONResponse({"error": "requests library not installed"}, status_code=503)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/sync-log")
def get_sync_log(lines: int = 50):
    """Read the latest lines from SYNC_TEST_Mauro-Home-PC.txt."""
    sync_path = os.path.join(ROOT_DIR, "SYNC_TEST_Mauro-Home-PC.txt")
    try:
        with open(sync_path, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
        return {
            "total_lines": len(all_lines),
            "lines": [l.rstrip() for l in all_lines[-lines:]],
        }
    except FileNotFoundError:
        return {"total_lines": 0, "lines": [], "note": "Sync log not found"}


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "GeoTalent Scout",
        "employees_loaded": len(scout_engine.employees),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "serp_api": "active" if os.getenv("SERP_API_KEY") else "stub",
    }


# ══════════════════════════════════════════════════════════════
#  CSV EXPORT & ROSTER UPLOAD
# ══════════════════════════════════════════════════════════════





@app.get("/api/export/csv")
def export_csv():
    """
    Export the last scout results as a CSV file.
    Open in Google Sheets by uploading to Drive or opening directly.
    """
    import csv
    import io

    candidates = _last_scout_result.get("candidates", [])
    if not candidates:
        return JSONResponse(
            {"error": "No scout results to export. Run a scout first."},
            status_code=404,
        )

    # CSV columns
    columns = [
        "Name", "Source", "Match Score", "Platform", "Job Title",
        "Email", "Phone", "Location", "Profile URL", "Notes",
        "AI Verified", "Status",
    ]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)

    for c in candidates:
        writer.writerow([
            c.get("name", ""),
            c.get("source", ""),
            c.get("match_score", ""),
            c.get("platform", ""),
            c.get("extracted_title", c.get("Job Title", "")),
            c.get("email", c.get("Home Email", "")),
            c.get("phone", c.get("Mobile Phone", "")),
            c.get("location", c.get("ZIP/Postal Code", "")),
            c.get("contact", ""),
            c.get("notes", "")[:200],
            "Yes" if c.get("ai_verified") else "",
            c.get("Status", c.get("status", "")),
        ])

    output.seek(0)
    role = _last_scout_result.get("role", "scout").replace(" ", "_")
    filename = f"GeoTalent_Scout_{role}.csv"

    # Also save a copy to the GeoTalent-Scout directory for Drive sync
    csv_path = os.path.join(SCRIPT_DIR, filename)
    try:
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            f.write(output.getvalue())
        logger.info("CSV exported to %s", csv_path)
    except Exception as e:
        logger.warning("Could not save CSV to disk: %s", e)

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/upload-roster")
async def upload_roster(
    file: UploadFile = File(...),
    format: str = Form(default="auto"),
):
    """
    Upload an employee roster (CSV or JSON) to replace/update the internal database.
    The file is saved to Meta_App_Factory/data/employees.json.

    CSV must have columns: Employee Number, Full Name, Mobile Phone,
    Home Email, Department Code, Job Title, ZIP/Postal Code, Status
    """
    content = await file.read()
    fname = file.filename or "roster"

    try:
        # Detect format
        if format == "auto":
            format = "csv" if fname.lower().endswith(".csv") else "json"

        if format == "csv":
            import csv
            import io
            text = content.decode("utf-8-sig")  # Handle BOM
            reader = csv.DictReader(io.StringIO(text))
            employees = []
            for row in reader:
                emp = {
                    "Employee Number": row.get("Employee Number", ""),
                    "Full Name": row.get("Full Name", ""),
                    "Mobile Phone": row.get("Mobile Phone", ""),
                    "Home Email": row.get("Home Email", ""),
                    "Department Code": row.get("Department Code", ""),
                    "Job Title": row.get("Job Title", ""),
                    "ZIP/Postal Code": row.get("ZIP/Postal Code", ""),
                    "Status": row.get("Status", "Active"),
                    "status": row.get("Status", "Active"),
                }
                employees.append(emp)
        else:
            employees = json.loads(content)
            if not isinstance(employees, list):
                return JSONResponse({"error": "JSON must be an array of employee objects"}, status_code=400)

        # Save to the employees.json file
        emp_path = os.path.join(FACTORY_DIR, "data", "employees.json")
        os.makedirs(os.path.dirname(emp_path), exist_ok=True)

        with open(emp_path, "w", encoding="utf-8") as f:
            json.dump(employees, f, indent=2, ensure_ascii=False)

        # Reload into the scout engine
        scout_engine.employees = scout_engine._load_employees()

        logger.info("Roster uploaded: %d employees from %s", len(employees), fname)

        return {
            "status": "success",
            "employees_loaded": len(employees),
            "file": fname,
            "saved_to": emp_path,
        }

    except Exception as e:
        logger.error("Roster upload failed: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)


# ── Serve built UI if available ───────────────────────────────
UI_DIST = os.path.join(SCRIPT_DIR, "ui", "dist")
if os.path.isdir(UI_DIST):
    app.mount("/", StaticFiles(directory=UI_DIST, html=True), name="ui")


# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n[*] Starting GeoTalent Scout on port 8080")
    print(f"[i] {len(scout_engine.employees)} employees loaded")
    print(f"[>] Swagger docs: http://localhost:8080/docs")
    print(f"[>] Scout:        POST http://localhost:8080/api/scout\n")
    uvicorn.run(app, host="0.0.0.0", port=8080)

# V3 MIGRATION COMPLETE
# V3 AUTO-HEAL ACTIVE
