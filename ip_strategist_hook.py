"""
ip_strategist_hook.py — Factory API Extension for IP Evaluation v2.0
=====================================================================
Meta App Factory | Antigravity-AI

FastAPI router that extends api.py via secondary import.
Provides /api/ip/evaluate, /api/ip/filing, /api/ip/conflicts,
/api/ip/claims, /api/ip/ledger, and /api/ip/status endpoints.

Integration:
    # In api.py (one-line safe import):
    try:
        from ip_strategist_hook import ip_router
        app.include_router(ip_router)
    except ImportError:
        pass
"""

import os
import sys
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

# ── Resolve paths ──────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REGISTRY_PATH = os.path.join(SCRIPT_DIR, "registry.json")
MASTER_INDEX_PATH = os.path.join(SCRIPT_DIR, "MASTER_INDEX.md")
LEDGER_PATH = os.path.join(SCRIPT_DIR, "LEDGER.md")

# Add the skills library to path for import
SKILLS_LIB = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "_ANTIGRAVITY_SKILLS_LIBRARY"))
if SKILLS_LIB not in sys.path:
    sys.path.insert(0, SKILLS_LIB)

from ip_strategist import (
    evaluate, generate_filing, get_info,
    resolve_conflicts, generate_claims_from_readme,
    append_ledger, read_ledger,
)


# ══════════════════════════════════════════════════
#  ROUTER
# ══════════════════════════════════════════════════

ip_router = APIRouter(prefix="/api/ip", tags=["IP Strategist"])


# ── Request Models ─────────────────────────────────────────

class IPEvalRequest(BaseModel):
    app_name: str

class IPFilingRequest(BaseModel):
    app_name: str
    filing_type: str = "patent"  # "patent" or "trademark"
    report: Optional[dict] = None  # If None, re-evaluate first

class IPConflictRequest(BaseModel):
    app_name: str


# ── Endpoints ──────────────────────────────────────────────

@ip_router.post("/evaluate")
async def evaluate_ip(req: IPEvalRequest):
    """
    Evaluate an application for intellectual property protection potential.
    Scans source code for patent-worthy innovations and trademark readiness.
    Returns confidence_score (0.0-1.0) — Shield unlocks at > 0.7.
    """
    app_dir = _resolve_app_dir(req.app_name)

    if not app_dir or not os.path.isdir(app_dir):
        raise HTTPException(
            status_code=404,
            detail=f"App directory not found for '{req.app_name}'. Check registry.json."
        )

    report = evaluate(req.app_name, app_dir, REGISTRY_PATH)

    # Log the evaluation
    append_ledger("EVALUATION_RUN", req.app_name,
                  extra=f"CONFIDENCE: {report.get('confidence_score', 0)}",
                  ledger_path=LEDGER_PATH)

    return report


@ip_router.post("/filing")
async def generate_filing_doc(req: IPFilingRequest):
    """
    Generate USPTO-standard filing documentation.
    Auto-logs to LEDGER.md on every filing generation.
    """
    if req.filing_type not in ("patent", "trademark"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid filing_type '{req.filing_type}'. Must be 'patent' or 'trademark'."
        )

    # If no report provided, run evaluation first
    report = req.report
    if not report:
        app_dir = _resolve_app_dir(req.app_name)
        if not app_dir or not os.path.isdir(app_dir):
            raise HTTPException(
                status_code=404,
                detail=f"App directory not found for '{req.app_name}'."
            )
        report = evaluate(req.app_name, app_dir, REGISTRY_PATH)

    filing = generate_filing(req.app_name, report, req.filing_type)

    # ── AUDIT LOG: Filing initiated ──
    append_ledger("FILING_INITIATED", req.app_name,
                  filing_type=req.filing_type,
                  ledger_path=LEDGER_PATH)

    return filing


@ip_router.post("/conflicts")
async def check_conflicts(req: IPConflictRequest):
    """
    Cross-reference app against MASTER_INDEX.md and registry.json
    to detect internal IP duplication.
    """
    app_dir = _resolve_app_dir(req.app_name)
    if not app_dir:
        app_dir = ""

    result = resolve_conflicts(
        req.app_name, app_dir,
        master_index_path=MASTER_INDEX_PATH,
        registry_path=REGISTRY_PATH,
    )

    # Log the conflict check
    append_ledger("CONFLICT_CHECK", req.app_name,
                  extra=f"CONFLICTS: {result['conflicts_found']}",
                  ledger_path=LEDGER_PATH)

    return result


@ip_router.post("/claims")
async def generate_claims(req: IPEvalRequest):
    """
    Generate patent claims from README.md and config.json.
    """
    app_dir = _resolve_app_dir(req.app_name)
    if not app_dir or not os.path.isdir(app_dir):
        raise HTTPException(
            status_code=404,
            detail=f"App directory not found for '{req.app_name}'."
        )

    claims = generate_claims_from_readme(app_dir, req.app_name)
    return claims


@ip_router.get("/ledger")
async def get_ledger(limit: int = 50):
    """Return recent audit ledger entries."""
    entries = read_ledger(ledger_path=LEDGER_PATH, limit=limit)
    return {
        "total_entries": len(entries),
        "entries": entries,
    }


@ip_router.get("/status")
async def ip_status():
    """IP Strategist module status and capabilities."""
    info = get_info()
    info["status"] = "operational"
    info["endpoints"] = {
        "evaluate": "POST /api/ip/evaluate",
        "filing": "POST /api/ip/filing",
        "conflicts": "POST /api/ip/conflicts",
        "claims": "POST /api/ip/claims",
        "ledger": "GET /api/ip/ledger",
        "status": "GET /api/ip/status",
    }
    return info


# ── Helpers ────────────────────────────────────────────────

def _resolve_app_dir(app_name: str) -> Optional[str]:
    """Resolve an app's directory from the factory registry or known paths."""

    # 1. Try registry.json (dict-keyed: apps.AppName)
    if os.path.exists(REGISTRY_PATH):
        try:
            with open(REGISTRY_PATH, "r") as f:
                data = json.load(f)
                apps = data.get("apps", {})

                # Dict-keyed registry
                if isinstance(apps, dict):
                    for key, app_data in apps.items():
                        if key.lower() == app_name.lower():
                            if app_data.get("path"):
                                return os.path.join(SCRIPT_DIR, app_data["path"])
                            if app_data.get("directory"):
                                return app_data["directory"]
                            # Fallback: use key as directory name
                            candidate = os.path.join(SCRIPT_DIR, key)
                            if os.path.isdir(candidate):
                                return candidate
                # List-keyed registry (legacy)
                elif isinstance(apps, list):
                    for app in apps:
                        if app.get("name", "").lower() == app_name.lower():
                            if app.get("path"):
                                return app["path"]
                            if app.get("directory"):
                                return app["directory"]
        except (json.JSONDecodeError, OSError):
            pass

    # 2. Fallback: check sibling directories
    candidates = [
        os.path.join(SCRIPT_DIR, app_name),
        os.path.join(SCRIPT_DIR, app_name.replace(" ", "_")),
        os.path.join(SCRIPT_DIR, app_name.replace("-", "_")),
    ]

    for candidate in candidates:
        if os.path.isdir(candidate):
            return candidate

    return None
