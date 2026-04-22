"""
CMO Agent — FastAPI Server
══════════════════════════════════════════════════════════════
Standalone marketing intelligence command center.
Port: 5020 | Serves frontend + API

Engine Modules:
  • Market Research (Flash) — TAM/SAM/SOM, competitive intel
  • Brand Architect (Pro) — Brand identity generation
  • GTM Planner (Pro) — Go-to-market playbooks
  • Persona Engine (Flash + Dr. Aris) — Audience profiling
  • Campaign Planner (Flash) — Campaign strategy & calendars
  • Competitive Matrix (Flash) — SWOT, positioning, moat analysis

War Room Interface:
  • /api/warroom/respond — Standardized CMO_Elite perspective
══════════════════════════════════════════════════════════════
"""

import os
import sys
import logging

# Ensure telemetry directory exists
log_dir = "/var/log/aether_net"
os.makedirs(log_dir, exist_ok=True)

# Configure Telemetry with both Stream and File handlers
logger = logging.getLogger("cmo_elite")
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s [%(name)s] %(levelname)s: %(message)s', datefmt="%H:%M:%S")

# Console Handler
ch = logging.StreamHandler(sys.stdout)
ch.setFormatter(formatter)
logger.addHandler(ch)

# Telemetry File Handler
fh = logging.FileHandler(os.path.join(log_dir, "cmo_elite.log"))
fh.setFormatter(formatter)
logger.addHandler(fh)
import sys
import json
import asyncio
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# ── Load environment from parent Meta_App_Factory ──────────
ROOT = Path(__file__).resolve().parent.parent
META_ROOT = ROOT.parent.parent.parent  # Meta_App_Factory
ENV_PATH = META_ROOT / ".env"

if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
else:
    # Try grandparent (Antigravity-AI Agents)
    alt_env = META_ROOT.parent / ".env"
    if alt_env.exists():
        load_dotenv(alt_env)

# ── Import Engines ─────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from engines.market_research import analyze_market
from engines.brand_architect import generate_brand_identity
from engines.brand_visual import generate_brand_visual, clear_chat_session
from engines.brand_critic import critique_brand
from engines.gtm_planner import generate_gtm_plan
from engines.persona_engine import generate_personas
from engines.campaign_planner import generate_campaign
from engines.competitive_matrix import analyze_competitive_landscape
from warroom_interface import warroom_respond
from memory_store import (
    save_analysis, get_recent_analyses, save_brand_identity,
    get_active_brand, save_personas, get_personas,
    save_campaign, get_campaigns, get_project_context,
    get_dashboard_stats,
    create_project, list_projects, get_project_detail,
    rename_project, archive_project, get_project_history,
    duplicate_project
)

# ═══════════════════════════════════════════════════════════
#  APP INITIALIZATION
# ═══════════════════════════════════════════════════════════

app = FastAPI(
    title="CMO Agent — Marketing Intelligence Command Center",
    description="Standalone CMO Agent by Antigravity-AI",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -- Serve Frontend Static Files ----
FRONTEND_DIR = ROOT / "frontend"
GENERATED_DIR = FRONTEND_DIR / "generated"
GENERATED_DIR.mkdir(parents=True, exist_ok=True)

# Mount Global Projects for cross-agent file sharing
import sys
SYSTEM_CORE_PATH = ROOT.parent / ".system_core"
if str(SYSTEM_CORE_PATH) not in sys.path:
    sys.path.append(str(SYSTEM_CORE_PATH))
from project_manager import GLOBAL_PROJECTS_DIR

if not GLOBAL_PROJECTS_DIR.exists():
    GLOBAL_PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/project-files", StaticFiles(directory=str(GLOBAL_PROJECTS_DIR)), name="project_files")

if FRONTEND_DIR.exists():
    app.mount("/generated", StaticFiles(directory=str(GENERATED_DIR)), name="generated")
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


# ── Global Exception Handler ──────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch any unhandled exception and return clean JSON."""
    error_msg = str(exc)[:300]
    print(f"[CMO_Elite ERROR] {request.method} {request.url.path}: {error_msg}")
    return JSONResponse(
        {"error": f"Engine error: {error_msg}", "agent": "CMO_Elite"},
        status_code=500
    )


# ═══════════════════════════════════════════════════════════
#  ROUTES — Frontend
# ═══════════════════════════════════════════════════════════

@app.get("/")
async def serve_frontend():
    """Serve the CMO Agent frontend."""
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return JSONResponse({"error": "Frontend not found", "path": str(index_path)})


# ═══════════════════════════════════════════════════════════
#  ROUTES — API Endpoints
# ═══════════════════════════════════════════════════════════

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    has_key = bool(os.getenv("GEMINI_API_KEY"))
    return {
        "status": "online",
        "agent": "CMO_Elite",
        "version": "1.0.0",
        "gemini_configured": has_key,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/dashboard")
async def get_dashboard(project_name: str = ""):
    """Get dashboard stats and recent activity, optionally scoped to a project."""
    stats = get_dashboard_stats()
    recent = get_recent_analyses(project_name=project_name or None, limit=5)

    # Strip heavy result data from recent activity — only need metadata
    recent_light = [
        {k: v for k, v in item.items() if k != "result"}
        for item in recent
    ]

    # Project-specific data
    project_info = None
    if project_name:
        detail = get_project_detail(project_name)
        if detail:
            # Lightweight history — strip full result JSON, keep only metadata
            light_history = [
                {"id": h.get("id"), "module": h.get("module"),
                 "input_summary": h.get("input_summary"), "created_at": h.get("created_at")}
                for h in detail.get("history", [])
            ]
            detail["history"] = light_history
            project_info = detail

    return {
        "stats": stats,
        "recent_activity": recent_light,
        "project": project_info
    }


# ── Safe Body Parser ────────────────────────────────────────

async def safe_parse_body(request: Request) -> dict:
    """Safely parse JSON body — returns {} if body is empty/invalid."""
    try:
        body = await request.json()
        return body if isinstance(body, dict) else {}
    except Exception:
        return {}


# ── Market Research ─────────────────────────────────────────

@app.post("/api/market-research")
async def api_market_research(request: Request):
    """Run market research analysis."""
    body = await safe_parse_body(request)
    user_input = body.get("input", "")
    project_name = body.get("project_name", "default")
    
    if not user_input:
        return JSONResponse({"error": "No input provided"}, status_code=400)
    
    # Get persistent context
    context = get_project_context(project_name)
    extra_context = body.get("context", "")
    if extra_context:
        context = f"{context}\n\nUSER CONTEXT: {extra_context}"
    
    result = await analyze_market(user_input, context)
    
    # Save to memory
    save_analysis("market_research", result, project_name, user_input[:200])
    
    return result


# ── Brand Studio ────────────────────────────────────────────

@app.post("/api/brand-studio")
async def api_brand_studio(request: Request):
    """Generate a brand identity."""
    body = await safe_parse_body(request)
    user_input = body.get("input", "")
    project_name = body.get("project_name", "default")
    
    if not user_input:
        return JSONResponse({"error": "No input provided"}, status_code=400)
    
    context = get_project_context(project_name)
    extra_context = body.get("context", "")
    if extra_context:
        context = f"{context}\n\nUSER CONTEXT: {extra_context}"
    
    result = await generate_brand_identity(user_input, context)
    
    # Save to persistent memory
    if "error" not in result:
        save_brand_identity(project_name, result)
    save_analysis("brand_studio", result, project_name, user_input[:200])
    
    return result


# ── Brand Studio: Visualize ─────────────────────────────────

@app.post("/api/brand-studio/visualize")
async def api_brand_visualize(request: Request):
    """Generate a brand concept image from brand identity."""
    body = await safe_parse_body(request)
    identity = body.get("identity", {})
    mockup_type = body.get("mockup_type", "brand_board")
    project_name = body.get("project_name", "default")
    user_feedback = body.get("feedback", None)

    if not identity:
        return JSONResponse({"error": "No brand identity provided"}, status_code=400)

    result = await generate_brand_visual(
        identity=identity,
        mockup_type=mockup_type,
        project_name=project_name,
        user_feedback=user_feedback,
    )
    
    # Save the successful visual to marketing memory
    if not result.get("error") and result.get("image_url"):
        save_analysis(
            module="brand_visual",
            result=result,
            project_name=project_name,
            input_summary=mockup_type
        )
        
    return result

@app.get("/api/memory/visuals/{project_name}")
async def api_memory_visuals(project_name: str, limit: int = 20):
    """Retrieve generated brand visuals for a project."""
    visuals = get_recent_analyses(module="brand_visual", project_name=project_name, limit=limit)
    return JSONResponse({"visuals": visuals})

# ── Brand Studio: Critique ──────────────────────────────────

@app.post("/api/brand-studio/critique")
async def api_brand_critique(request: Request):
    """Run Marcus Vane brand critique on identity + optional image."""
    body = await safe_parse_body(request)
    identity = body.get("identity", {})
    image_path = body.get("image_path", None)
    project_name = body.get("project_name", "default")
    user_feedback = body.get("feedback", "")

    if not identity:
        return JSONResponse({"error": "No brand identity to critique"}, status_code=400)

    context = get_project_context(project_name)
    extra_context = body.get("context", "")
    if extra_context:
        context = f"{context}\n\n{extra_context}"

    result = await critique_brand(
        identity=identity,
        image_path=image_path,
        context=context,
        user_feedback=user_feedback,
    )
    save_analysis("brand_critique", result, project_name, identity.get("company_name", "")[:100])
    return result


# ── Brand Studio: Refine ────────────────────────────────────

@app.post("/api/brand-studio/refine")
async def api_brand_refine(request: Request):
    """Refine brand identity based on user feedback + critic notes."""
    body = await safe_parse_body(request)
    original_input = body.get("input", "")
    feedback = body.get("feedback", "")
    critic_notes = body.get("critic_notes", "")
    project_name = body.get("project_name", "default")

    if not original_input or not feedback:
        return JSONResponse({"error": "Input and feedback required"}, status_code=400)

    context = get_project_context(project_name)
    refinement_context = f"""{context}

USER REFINEMENT FEEDBACK: {feedback}

CRITIC NOTES (Marcus Vane): {critic_notes}

IMPORTANT: Incorporate the user's feedback and the critic's suggestions into the refined brand identity.
Make specific changes based on the feedback while keeping the core brand strategy intact."""

    result = await generate_brand_identity(original_input, refinement_context)

    if "error" not in result:
        save_brand_identity(project_name, result)
        clear_chat_session(project_name)
    save_analysis("brand_refinement", result, project_name, f"Refined: {feedback[:100]}")
    return result


# ── GTM Planner ─────────────────────────────────────────────

@app.post("/api/gtm-plan")
async def api_gtm_plan(request: Request):
    """Generate a go-to-market playbook."""
    body = await safe_parse_body(request)
    user_input = body.get("input", "")
    project_name = body.get("project_name", "default")
    
    if not user_input:
        return JSONResponse({"error": "No input provided"}, status_code=400)
    
    context = get_project_context(project_name)
    extra_context = body.get("context", "")
    if extra_context:
        context = f"{context}\n\nUSER CONTEXT: {extra_context}"
    
    result = await generate_gtm_plan(user_input, context)
    
    save_analysis("gtm_plan", result, project_name, user_input[:200])
    
    return result


# ── Persona Builder ─────────────────────────────────────────

@app.post("/api/personas")
async def api_personas(request: Request):
    """Generate audience personas with Dr. Aris audit."""
    body = await safe_parse_body(request)
    user_input = body.get("input", "")
    project_name = body.get("project_name", "default")
    
    if not user_input:
        return JSONResponse({"error": "No input provided"}, status_code=400)
    
    context = get_project_context(project_name)
    extra_context = body.get("context", "")
    if extra_context:
        context = f"{context}\n\nUSER CONTEXT: {extra_context}"
    
    result = await generate_personas(user_input, context)
    
    # Save personas to memory
    if "error" not in result:
        save_personas(project_name, result)
    save_analysis("personas", result, project_name, user_input[:200])
    
    return result


# ── Campaign Planner ────────────────────────────────────────

@app.post("/api/campaigns")
async def api_campaigns(request: Request):
    """Generate a marketing campaign plan."""
    body = await safe_parse_body(request)
    user_input = body.get("input", "")
    project_name = body.get("project_name", "default")
    
    if not user_input:
        return JSONResponse({"error": "No input provided"}, status_code=400)
    
    context = get_project_context(project_name)
    extra_context = body.get("context", "")
    if extra_context:
        context = f"{context}\n\nUSER CONTEXT: {extra_context}"
    
    result = await generate_campaign(user_input, context)
    
    if "error" not in result:
        save_campaign(project_name, result)
    save_analysis("campaign", result, project_name, user_input[:200])
    
    return result


# ── Competitive Analysis ────────────────────────────────────

@app.post("/api/competitive-analysis")
async def api_competitive_analysis(request: Request):
    """Run competitive landscape analysis."""
    body = await safe_parse_body(request)
    user_input = body.get("input", "")
    project_name = body.get("project_name", "default")
    
    if not user_input:
        return JSONResponse({"error": "No input provided"}, status_code=400)
    
    context = get_project_context(project_name)
    extra_context = body.get("context", "")
    if extra_context:
        context = f"{context}\n\nUSER CONTEXT: {extra_context}"
    
    result = await analyze_competitive_landscape(user_input, context)
    
    save_analysis("competitive_analysis", result, project_name, user_input[:200])
    
    return result


# ── Memory / History ────────────────────────────────────────

@app.get("/api/memory/brand/{project_name}")
async def api_get_brand(project_name: str):
    """Get the active brand identity for a project."""
    brand = get_active_brand(project_name)
    return brand or {"message": "No brand identity found for this project"}


@app.get("/api/memory/personas/{project_name}")
async def api_get_personas(project_name: str):
    """Get all personas for a project."""
    return get_personas(project_name)


@app.get("/api/memory/campaigns/{project_name}")
async def api_get_campaigns(project_name: str):
    """Get all campaigns for a project."""
    return get_campaigns(project_name)


@app.get("/api/memory/history")
async def api_get_history(module: str = None, project_name: str = None, limit: int = 20):
    """Get analysis history."""
    return get_recent_analyses(module, project_name, limit)


from engines.legacy_verification import run_legacy_audit

# ── Legacy Verification ─────────────────────────────────────

@app.post("/api/legacy-audit")
async def api_legacy_audit(request: Request):
    """Compare user's legacy documents against CMO's findings."""
    body = await safe_parse_body(request)
    legacy_text = body.get("legacy_text", "")
    project_name = body.get("project_name", "default")
    
    if not legacy_text:
        return JSONResponse({"error": "No legacy documentation provided"}, status_code=400)
    
    # Get pristine CMO context
    cmo_context = get_project_context(project_name)
    if not cmo_context:
        return JSONResponse({"error": "No CMO findings exist for this project yet. Run engines first."}, status_code=400)
    
    result = await run_legacy_audit(legacy_text, cmo_context)
    
    # Save audit result to persistent memory
    save_analysis("legacy_audit", result, project_name, legacy_text[:200])
    
    return result

# ═══════════════════════════════════════════════════════════
#  PROJECT MANAGEMENT
# ═══════════════════════════════════════════════════════════


@app.get("/api/projects")
async def api_list_projects(status: str = "active"):
    """List all projects with summary stats."""
    return list_projects(status)


@app.post("/api/projects")
async def api_create_project(request: Request):
    """Create a new project."""
    body = await safe_parse_body(request)
    name = body.get("name", "")
    display_name = body.get("display_name", "")
    description = body.get("description", "")
    if not name:
        return JSONResponse({"error": "Project name is required"}, status_code=400)
    project = create_project(name, display_name, description)
    return project


@app.get("/api/projects/{project_name}")
async def api_get_project(project_name: str):
    """Get full project detail with all engine results."""
    detail = get_project_detail(project_name)
    if not detail:
        return JSONResponse({"error": "Project not found"}, status_code=404)
    return detail


@app.put("/api/projects/{project_name}")
async def api_update_project(project_name: str, request: Request):
    """Rename or update a project."""
    body = await safe_parse_body(request)
    new_name = body.get("name", None)
    display_name = body.get("display_name", None)
    result = rename_project(project_name, new_name, display_name)
    return result or {"error": "Project not found"}


@app.delete("/api/projects/{project_name}")
async def api_archive_project(project_name: str):
    """Archive a project (soft delete)."""
    archive_project(project_name)
    return {"status": "archived", "project": project_name}


@app.get("/api/projects/{project_name}/history")
async def api_project_history(project_name: str, limit: int = 50):
    """Get paginated history of all engine runs for a project."""
    return get_project_history(project_name, limit)

@app.get("/api/projects/{project_name}/assets")
async def api_project_assets(project_name: str):
    """Return a list of URLs for all assets within a specific project's CMO folder."""
    try:
        from project_manager import list_project_files
        files = list_project_files(project_name, "cmo")
        
        assets = []
        for f in files:
            ext = f.suffix.lower()
            url_path = f"/project-files/{project_name}/cmo/{f.name}"
            
            asset_type = "unknown"
            if ext in [".png", ".jpg", ".jpeg", ".webp"]:
                asset_type = "image"
            elif ext == ".pptx":
                asset_type = "presentation"
            elif ext == ".json":
                asset_type = "data"
                
            assets.append({
                "name": f.name,
                "url": url_path,
                "type": asset_type,
                "size": f.stat().st_size
            })
            
        return {"assets": sorted(assets, key=lambda x: x["name"])}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/projects/{project_name}/duplicate")
async def api_duplicate_project(project_name: str, request: Request):
    """Duplicate a project and all its data."""
    body = await safe_parse_body(request)
    new_name = body.get("display_name", "")
    result = duplicate_project(project_name, new_name)
    if not result:
        return JSONResponse({"error": "Source project not found"}, status_code=404)
    return result


# ═══════════════════════════════════════════════════════════
#  WAR ROOM INTERFACE
# ═══════════════════════════════════════════════════════════

@app.post("/api/warroom/respond")
async def api_warroom_respond(request: Request):
    """
    War Room integration endpoint.
    
    The future standalone War Room app will call this endpoint to get
    the CMO's perspective on any topic during a boardroom deliberation.
    
    Expected payload:
    {
        "topic": "string — the deliberation topic",
        "context": "string — additional context",
        "agents_present": ["CEO", "CFO", "CTO", "Critic"]
    }
    
    Returns standardized CMO_Elite response.
    """
    body = await safe_parse_body(request)
    topic = body.get("topic", "")
    context = body.get("context", "")
    agents_present = body.get("agents_present", [])
    
    if not topic:
        return JSONResponse({"error": "No topic provided"}, status_code=400)
    
    # Enrich context with persistent memory
    project_name = body.get("project_name", "default")
    memory_context = get_project_context(project_name)
    if memory_context:
        context = f"{context}\n\nCMO MEMORY (prior analyses):\n{memory_context}"
    
    result = await warroom_respond(topic, context, agents_present)
    
    return result


@app.get("/api/warroom/status")
async def api_warroom_status():
    """Report the CMO Agent's readiness for War Room integration."""
    has_key = bool(os.getenv("GEMINI_API_KEY"))
    return {
        "agent": "CMO_Elite",
        "role": "Chief Marketing Officer",
        "status": "ready" if has_key else "no_api_key",
        "capabilities": [
            "market_research", "brand_strategy", "gtm_planning",
            "persona_building", "campaign_planning", "competitive_analysis",
            "psychological_profiling"
        ],
        "api_version": "1.0.0",
        "port": 5020,
        "warroom_endpoint": "/api/warroom/respond",
        "response_schema": {
            "agent": "CMO_Elite",
            "status": "decisive",
            "perspective": "string",
            "data_points": ["string"],
            "recommendations": ["string"],
            "confidence_score": 0.0
        }
    }


# ═══════════════════════════════════════════════════════════
#  STARTUP
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    
    print("""
====================================================================
                                                              
   CMO AGENT -- Marketing Intelligence Command Center      
                                                              
   Port: 5020                                                 
   Dashboard: http://localhost:5020                            
   API Docs:  http://localhost:5020/docs                       
                                                              
   War Room:  /api/warroom/respond                             
   Health:    /api/health                                      
                                                              
   Engines:                                                    
     - Market Research (Gemini Flash)                          
     - Brand Architect (Gemini Pro)                            
     - GTM Planner (Gemini Pro)                                
     - Persona Engine + Dr. Aris (Gemini Flash)                
     - Campaign Planner (Gemini Flash)                         
     - Competitive Matrix (Gemini Flash)                       
                                                              
   Antigravity-AI | CMO_Elite v1.0.0                           
                                                              
====================================================================
    """)
    
    uvicorn.run(app, host="0.0.0.0", port=5020, log_level="info")
