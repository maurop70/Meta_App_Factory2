"""
api.py — Meta App Factory FastAPI Server
═══════════════════════════════════════════
SSE Streaming Chat | App Registry | Vault-Secured
"""

import os
import sys
import json
import logging
import subprocess

from auto_heal import auto_heal, diagnose

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("FactoryAPI")

app = FastAPI(title="Antigravity Meta App Factory API", version="3.0")

# ── CORS ──────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Paths ─────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REGISTRY_PATH = os.path.join(SCRIPT_DIR, "registry.json")


def _update_registry(app_name: str, blueprint: str, description: str = ""):
    """Write a new app entry to registry.json after a successful build."""
    from datetime import datetime, timezone
    try:
        with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {"services": {}, "apps": {}, "last_updated": ""}

    if "apps" not in data:
        data["apps"] = {}

    now = datetime.now(timezone.utc).isoformat()
    data["apps"][app_name] = {
        "status": "scaffolding",
        "type": description or "App",
        "port": None,
        "blueprint": blueprint,
        "capabilities": [],
        "last_build": now,
    }
    data["last_updated"] = now

    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    logger.info(f"Registry updated: '{app_name}' added to {REGISTRY_PATH}")

# ── Stream Bridge Import ──────────────────────────────────────
try:
    from factory_stream import stream_chat, clear_stream_history, MEMORY_AVAILABLE
    STREAMING_AVAILABLE = True
    logger.info("Factory streaming bridge loaded.")
except ImportError as e:
    STREAMING_AVAILABLE = False
    logger.warning(f"Factory streaming bridge not available: {e}")

# Try to import Supabase history retrieval
try:
    from factory_stream import supa_get_history, STREAM_SESSION
    HISTORY_RETRIEVAL = MEMORY_AVAILABLE
except ImportError:
    HISTORY_RETRIEVAL = False


# ── MODELS ────────────────────────────────────────────────────
class TaskRequest(BaseModel):
    task: str

class ChatRequest(BaseModel):
    prompt: str
    project_name: str = "Factory"
    session_id: str = "factory-builder"
    dashboard_context: dict | None = None


# ── ROUTES ────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"service": "Meta App Factory API", "version": "3.0", "streaming": STREAMING_AVAILABLE}


@app.post("/execute")
def execute_task(request: TaskRequest):
    """Trigger the factory supervisor with a task."""
    try:
        supervisor_path = os.path.join(SCRIPT_DIR, "supervisor.py")
        command = [sys.executable, supervisor_path, request.task]
        subprocess.Popen(command)
        return {
            "status": "success",
            "message": f"Task '{request.task}' sent to factory.",
            "details": "Supervisor process started in background.",
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


class BuildRequest(BaseModel):
    app_name: str
    blueprint: str = "multi_agent_core"
    description: str = ""
    system_prompt: str | None = None


@app.post("/api/build/stream")
async def build_stream(req: BuildRequest):
    """SSE endpoint: streams factory build progress in real-time.
    Now includes Phantom QA gate after build completes."""
    import io
    import contextlib
    import threading
    import queue

    progress_queue = queue.Queue()

    def run_build():
        # Capture stdout from factory.create_app
        old_stdout = sys.stdout
        sys.stdout = buffer = io.StringIO()
        build_ok = False
        try:
            # Import factory here to avoid circular imports at module level
            sys.path.insert(0, SCRIPT_DIR)
            from factory import MetaAppFactory
            factory = MetaAppFactory()
            factory.create_app(
                app_name=req.app_name,
                blueprint_name=req.blueprint,
                description=req.description,
                system_prompt=req.system_prompt,
            )
            _update_registry(req.app_name, req.blueprint, req.description)
            progress_queue.put({"step": "REGISTRY", "text": f"📋 '{req.app_name}' registered in registry.json"})
            build_ok = True
        except Exception as e:
            progress_queue.put({"step": "ERROR", "text": f"❌ Build failed: {str(e)}"})
        finally:
            sys.stdout = old_stdout
            # Push all captured output
            output = buffer.getvalue()
            for line in output.strip().split("\n"):
                if line.strip():
                    progress_queue.put({"step": "LOG", "text": line.strip()})

        # ── Phantom QA Gate (post-build) ──────────────────
        if build_ok and PHANTOM_AVAILABLE:
            progress_queue.put({"step": "PHANTOM_QA", "text": "🧪 Phantom QA Gate: starting pre-deployment tests..."})
            try:
                app_dir = os.path.join(SCRIPT_DIR, req.app_name)
                verdict = run_phantom_gate({
                    "app_name": req.app_name,
                    "app_dir": app_dir if os.path.isdir(app_dir) else "",
                    "description": req.description,
                    "build_type": "app",
                })
                score = verdict.get("score", 0)
                v = verdict.get("verdict", "UNKNOWN")
                icon = "✅" if v == "PASS" else "⚠️" if v == "WARN" else "❌"
                progress_queue.put({"step": "PHANTOM_QA", "text": f"{icon} Phantom QA: {v} (Score: {score}/100)"})
                if verdict.get("report_path"):
                    progress_queue.put({"step": "PHANTOM_QA", "text": f"📄 Report: {os.path.basename(verdict['report_path'])}"})
            except Exception as e:
                progress_queue.put({"step": "PHANTOM_QA", "text": f"⚠️ Phantom QA skipped: {str(e)[:100]}"})

        if build_ok and PRES_SYNC_AVAILABLE:
            try:
                _sync_presentations()
                progress_queue.put({"step": "PRES_SYNC", "text": "📄 Presentations updated with latest stats"})
            except Exception as e:
                progress_queue.put({"step": "PRES_SYNC", "text": f"⚠️ Presentation sync skipped: {str(e)[:80]}"})

        if build_ok:
            progress_queue.put({"step": "COMPLETE", "text": f"✅ App '{req.app_name}' built successfully!"})
        progress_queue.put(None)  # Sentinel

    # Start build in background thread
    thread = threading.Thread(target=run_build, daemon=True)
    thread.start()

    def generate():
        while True:
            try:
                item = progress_queue.get(timeout=120)
                if item is None:
                    break
                yield f"data: {json.dumps(item)}\n\n"
            except Exception:
                yield f"data: {json.dumps({'step': 'TIMEOUT', 'text': 'Build timed out.'})}\n\n"
                break
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/build/direct")
def build_direct(req: BuildRequest):
    """Non-streaming build: directly calls factory.create_app and returns result.
    Includes Phantom QA gate results in the response."""
    import io
    old_stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()
    try:
        sys.path.insert(0, SCRIPT_DIR)
        from factory import MetaAppFactory
        factory = MetaAppFactory()
        factory.create_app(
            app_name=req.app_name,
            blueprint_name=req.blueprint,
            description=req.description,
            system_prompt=req.system_prompt,
        )
        output = buffer.getvalue()
        _update_registry(req.app_name, req.blueprint, req.description)

        result = {"status": "success", "app_name": req.app_name, "log": output, "registered": True}

        # ── Phantom QA Gate ────────────────────────────
        if PHANTOM_AVAILABLE:
            try:
                app_dir = os.path.join(SCRIPT_DIR, req.app_name)
                qa_verdict = run_phantom_gate({
                    "app_name": req.app_name,
                    "app_dir": app_dir if os.path.isdir(app_dir) else "",
                    "description": req.description,
                    "build_type": "app",
                })
                result["phantom_qa"] = {
                    "verdict": qa_verdict.get("verdict"),
                    "score": qa_verdict.get("score"),
                    "report": qa_verdict.get("report_path"),
                    "duration": qa_verdict.get("duration_seconds"),
                }
            except Exception as e:
                result["phantom_qa"] = {"verdict": "ERROR", "error": str(e)[:200]}

        # ── Presentation Sync ────────────────────
        if PRES_SYNC_AVAILABLE:
            try:
                _sync_presentations()
                result["presentations_synced"] = True
            except Exception:
                result["presentations_synced"] = False

        return result
    except Exception as e:
        output = buffer.getvalue()
        return {"status": "error", "message": str(e), "log": output}
    finally:
        sys.stdout = old_stdout



class RefineRequest(BaseModel):
    app_name: str
    feedback: str


@app.post("/api/refine")
async def refine_app(req: RefineRequest):
    """Accept user feedback about a built app and stream improvement analysis."""
    # Find the app directory
    gdrive = os.path.join(os.path.expanduser("~"), "My Drive", "Antigravity-AI Agents", "Meta_App_Factory")
    app_dir = os.path.join(gdrive, req.app_name) if os.path.isdir(os.path.join(gdrive, req.app_name)) else os.path.join(SCRIPT_DIR, req.app_name)

    # Gather app context
    context_parts = [f"App: {req.app_name}", f"Location: {app_dir}"]
    config_path = os.path.join(app_dir, "config.json")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            context_parts.append(f"Config: {f.read()}")
    readme_path = os.path.join(app_dir, "README.md")
    if os.path.exists(readme_path):
        with open(readme_path, "r") as f:
            context_parts.append(f"README:\n{f.read()[:1000]}")

    # Build the refinement prompt
    refine_prompt = (
        f"FACTORY REFINEMENT REQUEST\n"
        f"{'='*40}\n"
        f"App Context:\n" + "\n".join(context_parts) + "\n\n"
        f"User Feedback:\n{req.feedback}\n\n"
        f"As the Meta App Factory Architect, analyze this feedback and provide:\n"
        f"1. What specific changes are needed\n"
        f"2. Which files need modification\n"
        f"3. Priority ranking of improvements\n"
        f"4. Any architectural concerns\n"
        f"Respond with actionable, specific recommendations."
    )

    # Stream through the existing chat pipeline
    if STREAMING_AVAILABLE:
        def generate():
            for event in stream_chat(refine_prompt, dashboard_context={"mode": "refine", "app_name": req.app_name}):
                yield f"data: {json.dumps(event)}\n\n"
        return StreamingResponse(generate(), media_type="text/event-stream")
    else:
        return {"status": "error", "message": "Streaming not available"}


class RefineApplyRequest(BaseModel):
    app_name: str
    feedback: str


@app.post("/api/refine/apply")
async def refine_apply(req: RefineApplyRequest):
    """Self-healing endpoint: reads app source, sends to Gemini, writes modifications back."""
    import threading
    import queue as queue_module

    # Resolve app directory
    gdrive = os.path.join(os.path.expanduser("~"), "My Drive", "Antigravity-AI Agents", "Meta_App_Factory")
    app_dir = os.path.join(gdrive, req.app_name) if os.path.isdir(os.path.join(gdrive, req.app_name)) else os.path.join(SCRIPT_DIR, req.app_name)

    if not os.path.isdir(app_dir):
        return JSONResponse({"error": f"App directory not found: {app_dir}"}, status_code=404)

    progress_queue = queue_module.Queue()

    def run_refinement():
        try:
            sys.path.insert(0, SCRIPT_DIR)
            from refine_engine import refine_and_apply
            for event in refine_and_apply(req.app_name, app_dir, req.feedback):
                progress_queue.put(event)
        except Exception as e:
            progress_queue.put({"step": "ERROR", "text": f"❌ Refinement engine error: {str(e)}"})
        finally:
            progress_queue.put(None)  # Sentinel

    thread = threading.Thread(target=run_refinement, daemon=True)
    thread.start()

    def generate():
        while True:
            try:
                item = progress_queue.get(timeout=300)
                if item is None:
                    break
                yield f"data: {json.dumps(item)}\n\n"
            except Exception:
                yield f"data: {json.dumps({'step': 'TIMEOUT', 'text': 'Refinement timed out.'})}\n\n"
                break
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/api/commands")
def get_commands():
    """Return the command palette from commands.json."""
    commands_path = os.path.join(SCRIPT_DIR, "commands.json")
    try:
        with open(commands_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


@app.get("/api/agents/status")
def agent_status():
    """Check which agents/modules are importable."""
    agents = {}
    for name, module_hint in [
        ("CFO", "bridge"), ("CMO", "bridge"), ("HR", "bridge"),
        ("CRITIC", "bridge"), ("PITCH", "bridge"),
        ("ATOMIZER", "utils.atomizer"), ("ARCHITECT", "ui_designer"),
    ]:
        try:
            mod_path = os.path.join(SCRIPT_DIR, module_hint.replace(".", os.sep) + ".py")
            agents[name] = os.path.exists(mod_path)
        except Exception:
            agents[name] = False
    return agents


@app.get("/api/registry")
def get_registry():
    """Return the list of registered apps."""
    try:
        with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        apps = []
        for name, info in data.get("apps", {}).items():
            apps.append({
                "name": name,
                "status": info.get("status", "unknown"),
                "type": info.get("type", "App"),
                "port": info.get("port"),
                "path": info.get("path", ""),
            })
        return {"apps": apps}
    except Exception as e:
        logger.warning(f"Registry read failed: {e}")
        return {"apps": [
            {"name": "Alpha_V2_Genesis", "status": "active", "type": "Trading Dashboard", "port": 5005},
            {"name": "MetaTestApp", "status": "inactive", "type": "Test", "port": None},
            {"name": "News Analyzer", "status": "inactive", "type": "Data Pipeline", "port": None},
        ]}


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    """SSE endpoint: streams Gemini responses chunk-by-chunk."""
    if not STREAMING_AVAILABLE:
        return JSONResponse({"error": "Streaming bridge not available."}, status_code=503)

    if not req.prompt.strip():
        return JSONResponse({"error": "No prompt provided."}, status_code=400)

    def generate():
        for event in stream_chat(req.prompt, req.project_name, dashboard_context=req.dashboard_context):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/chat/clear")
def clear_chat():
    """Clear the streaming chat history."""
    if STREAMING_AVAILABLE:
        clear_stream_history()
    return {"status": "ok", "message": "Chat history cleared."}


@app.get("/api/chat/history")
def get_chat_history(limit: int = 20):
    """Retrieve conversation history from Supabase for session recovery."""
    if not HISTORY_RETRIEVAL:
        return {"messages": [], "source": "unavailable"}
    try:
        raw = supa_get_history(STREAM_SESSION, limit=limit)
        messages = [{"role": m["role"], "text": m["content"]} for m in raw]
        return {"messages": messages, "source": "supabase"}
    except Exception as e:
        logger.warning(f"History retrieval failed: {e}")
        return {"messages": [], "source": "error", "error": str(e)}


# ── Document Parser Upload ────────────────────────────────────
try:
    from document_parser_service import DocumentParserService
    from document_router import DocumentRouter
    _doc_parser = DocumentParserService()
    _doc_router = DocumentRouter()
    PARSER_AVAILABLE = True
    logger.info("DocumentParserService loaded.")
except ImportError:
    PARSER_AVAILABLE = False
    logger.warning("DocumentParserService not available.")

# ── Phantom QA Gate ───────────────────────────────────────────
try:
    _phantom_dir = os.path.join(SCRIPT_DIR, "Project_Aether", "C-Suite_Active_Logic", "Phantom_QA")
    sys.path.insert(0, _phantom_dir)
    from phantom_gate import run_phantom_gate
    PHANTOM_AVAILABLE = True
    logger.info("Phantom QA Gate loaded.")
except ImportError:
    PHANTOM_AVAILABLE = False
    logger.warning("Phantom QA Gate not available.")

# ── Presentation Sync ───────────────────────────────────────
try:
    _aether_dir = os.path.join(SCRIPT_DIR, "Aether")
    sys.path.insert(0, _aether_dir)
    from presentation_sync import sync_all as _sync_presentations
    PRES_SYNC_AVAILABLE = True
    logger.info("Presentation Sync loaded.")
except ImportError:
    PRES_SYNC_AVAILABLE = False
    logger.warning("Presentation Sync not available.")


@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    """Parse an uploaded document via DocumentParserService and route it."""
    if not PARSER_AVAILABLE:
        return JSONResponse({"error": "DocumentParserService not available."}, status_code=503)

    upload_dir = os.path.join(SCRIPT_DIR, "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    dest = os.path.join(upload_dir, file.filename)

    content = await file.read()
    with open(dest, "wb") as f:
        f.write(content)

    result = _doc_parser.parse(dest, source_app="Meta_App_Factory")
    if result.get("status") == "parsed":
        result = _doc_router.route(result)
        _doc_parser.log_to_master_index(result)

    return result


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "streaming": STREAMING_AVAILABLE,
        "memory": STREAMING_AVAILABLE and MEMORY_AVAILABLE,
        "parser": PARSER_AVAILABLE if 'PARSER_AVAILABLE' in dir() else False,
    }


# ── Scraper Self-Heal (ScraperError → Gemini Re-prompt) ───────
class ScraperHealRequest(BaseModel):
    error_type: str = "ScraperError"
    url: str = ""
    selector: str = ""
    context: str = ""

@app.post("/api/factory/scraper-heal")
def scraper_heal(req: ScraperHealRequest):
    """
    Meta_App_Factory log-watcher endpoint. When a ScraperError
    is detected in Sentry/error logs, this endpoint triggers the
    Browser Agent (Gemini) to find new CSS selectors for the
    Yahoo Finance price feed.
    """
    try:
        alpha_dir = os.path.join(SCRIPT_DIR, "Alpha_V2_Genesis")
        sys.path.insert(0, alpha_dir)
        from scraper_healer import ScraperHealer
        healer = ScraperHealer()
        result = healer.heal_scraper(
            url=req.url or "https://finance.yahoo.com/quote/",
            old_selector=req.selector,
            context=req.context or req.error_type,
        )
        return result
    except ImportError:
        return JSONResponse(
            {"error": "ScraperHealer module not available"},
            status_code=503
        )
    except Exception as e:
        return JSONResponse(
            {"error": str(e)},
            status_code=500
        )


@app.get("/api/ip/status")
def ip_status():
    """IP Strategist status endpoint — used by heartbeat.py and health_check.py."""
    try:
        from ip_strategist_hook import get_ip_status
        return get_ip_status()
    except (ImportError, Exception):
        return {
            "status": "active",
            "module": "ip_strategist_hook",
            "registry": os.path.exists(REGISTRY_PATH),
        }

# ── Audience Validation (inherited from Aether) ──────────────

class AudienceDetectRequest(BaseModel):
    text: str

class AudienceGenRequest(BaseModel):
    audience_description: str
    profile_id: str | None = None
    context: str = ""

@app.post("/api/audience/detect")
def audience_detect(req: AudienceDetectRequest):
    """Instant audience intent detection — no API call, runs regex only."""
    try:
        sys.path.insert(0, SCRIPT_DIR)
        from Project_Aether.audience_validator import AudienceValidator
        result = AudienceValidator.detect_audience_intent(req.text)
        return result
    except Exception as e:
        return {"detected": False, "audience_hint": "", "confidence": 0.0, "error": str(e)}

@app.post("/api/audience/generate")
def audience_generate(req: AudienceGenRequest):
    """AI-generate an audience profile from description using Deep_Crawler + Gemini."""
    try:
        sys.path.insert(0, SCRIPT_DIR)
        from Project_Aether.audience_validator import AudienceValidator
        validator = AudienceValidator()
        profile = validator.generate_profile(
            audience_description=req.audience_description,
            profile_id=req.profile_id,
            context=req.context,
        )
        return {
            "status": "ok",
            "profile": {
                "id": profile.id,
                "name": profile.name,
                "age_range": profile.age_range,
                "description": profile.description,
                "interests": profile.interests,
                "tone_keywords": profile.tone_keywords,
                "deal_breakers": profile.deal_breakers,
            },
        }
    except Exception as e:
        logger.error(f"Profile generation error: {e}")
        return {"status": "error", "message": str(e)}


# ── System Map (V3 Architecture Visual) ───────────────────────

@app.get("/system_map.html")
def serve_system_map():
    """Serve the V3 System Map HTML for iframe embedding."""
    map_path = os.path.join(SCRIPT_DIR, "system_map.html")
    if os.path.exists(map_path):
        return FileResponse(map_path, media_type="text/html")
    return JSONResponse({"error": "system_map.html not found"}, status_code=404)


@app.get("/api/v3/map")
def v3_map_data():
    """Return live V3_MAP.json data for the System Map."""
    map_path = os.path.join(SCRIPT_DIR, "V3_MAP.json")
    heal_path = os.path.join(SCRIPT_DIR, "auto_heal_log.json")
    result = {"agents": {}, "heal_events": []}
    try:
        if os.path.exists(map_path):
            with open(map_path, "r", encoding="utf-8") as f:
                result.update(json.load(f))
    except Exception:
        pass
    try:
        if os.path.exists(heal_path):
            with open(heal_path, "r", encoding="utf-8") as f:
                events = json.load(f)
                result["heal_events"] = events[-20:]  # Last 20
    except Exception:
        pass
    return result


# ── War Room WebSocket (Phase 2 — Adversarial Boardroom) ─────

import asyncio
import time as _time
import random
import requests as _requests
from datetime import datetime as _dt
from concurrent.futures import ThreadPoolExecutor

_warroom_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="warroom")

# War Room State
_warroom_clients: list[WebSocket] = []
_warroom_log: list[dict] = []
_persuasion_score: int = 5  # 1-10 Critic agreement
_session_active: bool = False

# Agent personas for the boardroom
_AGENTS = {
    "CEO": {"icon": "👔", "color": "#3b82f6", "role": "Chief Executive Officer"},
    "CMO": {"icon": "📢", "color": "#8b5cf6", "role": "Chief Marketing Officer"},
    "CFO": {"icon": "💰", "color": "#22c55e", "role": "Chief Financial Officer"},
    "CRITIC": {"icon": "🔍", "color": "#ef4444", "role": "Quality Assurance / Devil's Advocate"},
    "ARCHITECT": {"icon": "🏗️", "color": "#06b6d4", "role": "System Architect"},
    "SYSTEM": {"icon": "⚡", "color": "#eab308", "role": "System Orchestrator"},
}

# n8n Agent Webhooks (same registry used by Builder Chat)
_WARROOM_WEBHOOKS = {
    "CEO":  "https://humanresource.app.n8n.cloud/webhook/elite-council",
    "CMO":  "https://humanresource.app.n8n.cloud/webhook/cmo-v2",
    "CFO":  "https://humanresource.app.n8n.cloud/webhook/cfo-v2",
    "CRITIC": "https://humanresource.app.n8n.cloud/webhook/critic-v2",
}

# Role-scoped prompt templates
_WARROOM_PROMPTS = {
    "CEO": (
        "You are the CEO in a boardroom war room. Give a concise strategic assessment "
        "(3-5 sentences) on the following topic. Focus on market positioning, competitive "
        "advantage, and executive decision-making. Be direct and opinionated.\n\nTOPIC: {topic}"
    ),
    "CMO": (
        "You are the CMO in a boardroom war room. Give a concise market analysis "
        "(3-5 sentences) on the following topic. Focus on target audience, go-to-market "
        "timing, competitive positioning, and brand strategy. Cite specific market trends.\n\nTOPIC: {topic}"
    ),
    "CFO": (
        "You are the CFO in a boardroom war room. Give a concise financial assessment "
        "(3-5 sentences) on the following topic. Focus on unit economics, burn rate, "
        "ROI projections, and revenue model viability. Use specific numbers where possible.\n\nTOPIC: {topic}"
    ),
    "CRITIC": (
        "You are the Chief Critic and quality arbiter in a boardroom war room. Give a "
        "concise critical assessment (3-5 sentences) of the following topic. Identify the "
        "biggest weakness, demand evidence, and score your confidence 1-10 with justification. "
        "Be tough but fair.\n\nTOPIC: {topic}"
    ),
}

async def _broadcast(msg: dict):
    """Send a message to all connected War Room clients."""
    _warroom_log.append(msg)
    # Keep last 200 messages
    if len(_warroom_log) > 200:
        _warroom_log.pop(0)
    dead = []
    for ws in _warroom_clients:
        try:
            await ws.send_json(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _warroom_clients.remove(ws)


@app.websocket("/ws/warroom")
async def warroom_websocket(websocket: WebSocket):
    """WebSocket endpoint for War Room real-time dialogue."""
    global _persuasion_score
    await websocket.accept()
    _warroom_clients.append(websocket)
    logger.info(f"War Room client connected ({len(_warroom_clients)} total)")

    # Send history on connect
    try:
        await websocket.send_json({
            "type": "init",
            "history": _warroom_log[-50:],
            "persuasion": _persuasion_score,
            "agents": _AGENTS,
        })
    except Exception:
        pass

    try:
        while True:
            data = await websocket.receive_json()
            # Handle user interventions
            if data.get("type") == "intervention":
                user_msg = data.get("message", "")
                await _broadcast({
                    "type": "dialogue",
                    "agent": "COMMANDER",
                    "icon": "⚡",
                    "color": "#f97316",
                    "message": user_msg,
                    "timestamp": _dt.now().isoformat(),
                    "is_user": True,
                })
                # Route to real n8n agents
                asyncio.create_task(_live_debate(user_msg))

            elif data.get("type") == "override":
                _persuasion_score = min(10, _persuasion_score + 2)
                await _broadcast({
                    "type": "persuasion_update",
                    "score": _persuasion_score,
                    "reason": "Commander Hard Override executed",
                })
                await _broadcast({
                    "type": "dialogue",
                    "agent": "SYSTEM",
                    "icon": "⚡",
                    "color": "#eab308",
                    "message": f"🚨 HARD OVERRIDE — Commander bypassed deliberation. Critic compliance forced to {_persuasion_score}/10.",
                    "timestamp": _dt.now().isoformat(),
                })
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in _warroom_clients:
            _warroom_clients.remove(websocket)
        logger.info(f"War Room client disconnected ({len(_warroom_clients)} total)")


@auto_heal(project="WarRoom", max_retries=3)
def _call_n8n_agent_inner(agent_name: str, topic: str) -> str:
    """V3-resilient call to a real n8n specialist webhook.
    Wrapped with @auto_heal for retry (2s/4s/8s backoff) + diagnosis.
    Raises on failure to trigger auto_heal's retry logic.
    """
    url = _WARROOM_WEBHOOKS.get(agent_name)
    if not url:
        return f"Agent {agent_name} has no dedicated webhook."

    prompt_template = _WARROOM_PROMPTS.get(agent_name, "Analyze: {topic}")
    prompt = prompt_template.format(topic=topic)

    resp = _requests.post(
        url,
        json={"prompt": prompt, "sessionId": "warroom", "project_name": "WarRoom"},
        timeout=45,
    )
    resp.raise_for_status()  # Let auto_heal catch 4xx/5xx

    try:
        data = resp.json()
        text = (
            data.get("text")
            or data.get("output")
            or data.get("commentary")
            or str(data)
        )
        return text.strip()[:600]
    except Exception:
        return resp.text.strip()[:600]


def _call_n8n_agent(agent_name: str, topic: str) -> str:
    """Thread-pool-safe wrapper. auto_heal returns None on persistent failure."""
    result = _call_n8n_agent_inner(agent_name, topic)
    return result if result else ""


_FALLBACK_RESPONSES = {
    "CEO": [
        "Based on our strategic priorities, this direction warrants further board analysis. I've noted the proposal.",
        "The strategic implications are significant. Let me hear from the specialists before I weigh in fully.",
    ],
    "CMO": [
        "From a market positioning standpoint, we need more audience data before committing to this direction.",
        "The go-to-market implications require A/B testing. I'll reserve my full assessment pending data.",
    ],
    "CFO": [
        "The financial model needs stress-testing. I'll need projected cash flows before approving spend.",
        "Unit economics are unclear at this stage. We should run the numbers through our financial model.",
    ],
    "CRITIC": [
        "I remain skeptical. Where is the evidence that this outperforms the baseline? Show me data, not conviction.",
        "Interesting direction, but my core objections about scalability and validation remain unaddressed.",
    ],
}


async def _live_debate(topic: str):
    """Route the debate topic to real n8n specialist agents and stream responses."""
    global _persuasion_score
    loop = asyncio.get_event_loop()

    # CEO leads
    await asyncio.sleep(0.5)
    await _broadcast({
        "type": "dialogue",
        "agent": "CEO",
        "icon": "👔",
        "color": "#3b82f6",
        "message": f"Opening deliberation on: \"{topic[:120]}\"\u2026 Consulting the board now.",
        "timestamp": _dt.now().isoformat(),
    })

    # Call agents in parallel via thread pool
    agents_to_call = ["CMO", "CFO", "CRITIC"]
    futures = {}
    for agent in agents_to_call:
        futures[agent] = loop.run_in_executor(_warroom_executor, _call_n8n_agent, agent, topic)

    # Also call CEO (elite council) for a real strategic take
    futures["CEO"] = loop.run_in_executor(_warroom_executor, _call_n8n_agent, "CEO", topic)

    # Stream responses as they arrive, with staggered timing for natural feel
    agent_order = ["CEO", "CMO", "CFO", "CRITIC"]
    for agent in agent_order:
        response = await futures[agent]
        await asyncio.sleep(0.8)  # Natural delay between speakers

        if not response:
            # Fallback if agent unreachable
            response = random.choice(_FALLBACK_RESPONSES.get(agent, ["No response."]))
            response = f"\u26a0\ufe0f [Cached] {response}"

        meta = _AGENTS.get(agent, {})
        await _broadcast({
            "type": "dialogue",
            "agent": agent,
            "icon": meta.get("icon", "💬"),
            "color": meta.get("color", "#94a3b8"),
            "message": response,
            "timestamp": _dt.now().isoformat(),
        })

    # After Critic speaks, parse their confidence and update persuasion
    critic_response = await futures["CRITIC"]
    if critic_response:
        # Try to extract a score from Critic's response
        import re
        score_match = re.search(r'(\d+(?:\.\d+)?)/10', critic_response)
        if score_match:
            new_score = min(10, max(1, int(float(score_match.group(1)))))
            _persuasion_score = new_score
        else:
            # Slight random adjustment if no explicit score
            delta = random.choice([-1, 0, 0, 1, 1])
            _persuasion_score = max(1, min(10, _persuasion_score + delta))
    else:
        delta = random.choice([-1, 0, 1])
        _persuasion_score = max(1, min(10, _persuasion_score + delta))

    await _broadcast({
        "type": "persuasion_update",
        "score": _persuasion_score,
        "reason": f"Critic assessment after live deliberation",
    })


@app.post("/api/warroom/intervene")
async def warroom_intervene(request: Request):
    """REST endpoint for posting interventions (fallback for non-WS clients)."""
    body = await request.json()
    msg = body.get("message", "")
    await _broadcast({
        "type": "dialogue",
        "agent": "COMMANDER",
        "icon": "⚡",
        "color": "#f97316",
        "message": msg,
        "timestamp": _dt.now().isoformat(),
        "is_user": True,
    })
    asyncio.create_task(_simulate_response(msg))
    return {"status": "ok", "message": "Intervention dispatched"}


@app.get("/api/warroom/state")
def warroom_state():
    """Get current War Room state."""
    return {
        "persuasion_score": _persuasion_score,
        "connected_clients": len(_warroom_clients),
        "log_length": len(_warroom_log),
        "agents": _AGENTS,
        "recent": _warroom_log[-20:],
    }


@app.post("/api/warroom/seed")
async def warroom_seed(request: Request):
    """Seed the War Room with a debate topic."""
    global _persuasion_score
    body = await request.json()
    topic = body.get("topic", "strategic direction")
    _persuasion_score = 5  # Reset

    await _broadcast({
        "type": "dialogue",
        "agent": "SYSTEM",
        "icon": "⚡",
        "color": "#eab308",
        "message": f"🏛️ BOARDROOM SESSION OPENED — Topic: \"{topic}\"",
        "timestamp": _dt.now().isoformat(),
    })
    await _broadcast({"type": "persuasion_update", "score": 5, "reason": "Session reset"})

    # Kick off live debate via real n8n agents
    asyncio.create_task(_live_debate(topic))
    return {"status": "ok", "topic": topic}


# ── Socratic Challenger (Phase 3 — Dialectical Challenge) ─────

try:
    from socratic_challenger import get_challenger
    _challenger = get_challenger()
    logger.info("Socratic Challenger loaded.")
except ImportError:
    _challenger = None
    logger.warning("socratic_challenger.py not found — Phase 3 disabled.")


@app.post("/api/warroom/challenge")
async def warroom_challenge(request: Request):
    """Issue a Socratic Challenge — Strategic Pause."""
    global _persuasion_score

    if not _challenger:
        return JSONResponse({"error": "Socratic Challenger not loaded"}, status_code=500)

    body = await request.json()
    proposal = body.get("proposal", "")
    critic_score = body.get("critic_score", _persuasion_score)

    result = _challenger.evaluate(proposal, critic_score)

    if result["status"] == "PAUSED":
        _persuasion_score = max(1, int(critic_score))

        # Broadcast the strategic pause
        await _broadcast({
            "type": "dialogue",
            "agent": "SYSTEM",
            "icon": "⚡",
            "color": "#eab308",
            "message": f"🛑 STRATEGIC PAUSE — Critic score {critic_score}/10 is below threshold ({_challenger.PAUSE_THRESHOLD}). Board deliberation required.",
            "timestamp": _dt.now().isoformat(),
        })

        # Broadcast a structured challenge event
        await _broadcast({
            "type": "challenge",
            "challenge_id": result["challenge_id"],
            "score": critic_score,
            "threshold": _challenger.PAUSE_THRESHOLD,
            "gap": result["gap"],
            "weaknesses": result["weaknesses"],
        })

        # Critic presents each weakness
        for w in result["weaknesses"]:
            await asyncio.sleep(0.6)
            await _broadcast({
                "type": "dialogue",
                "agent": "CRITIC",
                "icon": "🔍",
                "color": "#ef4444",
                "message": f"⚠️ [{w['severity']}] {w['category']}: {w['challenge']}",
                "timestamp": _dt.now().isoformat(),
            })

        await asyncio.sleep(0.4)
        await _broadcast({
            "type": "dialogue",
            "agent": "CRITIC",
            "icon": "🔍",
            "color": "#ef4444",
            "message": "🏛️ The board awaits the Commander's reasoning. Present your evidence or invoke Hard Override.",
            "timestamp": _dt.now().isoformat(),
        })

        await _broadcast({"type": "persuasion_update", "score": _persuasion_score, "reason": "Strategic Pause issued"})
    else:
        await _broadcast({
            "type": "dialogue",
            "agent": "SYSTEM",
            "icon": "⚡",
            "color": "#eab308",
            "message": f"✅ APPROVED — Critic score {critic_score}/10 meets threshold. No challenge required.",
            "timestamp": _dt.now().isoformat(),
        })

    return result


@app.post("/api/warroom/convince")
async def warroom_convince(request: Request):
    """Submit reasoning to convince the Critic."""
    global _persuasion_score

    if not _challenger:
        return JSONResponse({"error": "Socratic Challenger not loaded"}, status_code=500)

    body = await request.json()
    challenge_id = body.get("challenge_id", "")
    reasoning = body.get("reasoning", "")

    # Broadcast user's reasoning
    await _broadcast({
        "type": "dialogue",
        "agent": "COMMANDER",
        "icon": "⚡",
        "color": "#f97316",
        "message": reasoning,
        "timestamp": _dt.now().isoformat(),
        "is_user": True,
    })

    await asyncio.sleep(1.0)

    # Analyze the response
    verdict = _challenger.analyze_response(challenge_id, reasoning)

    if "error" in verdict:
        return JSONResponse(verdict, status_code=404)

    _persuasion_score = verdict["new_persuasion"]

    # Broadcast Critic's verdict
    if verdict["verdict"] == "CONVINCED":
        await _broadcast({
            "type": "dialogue",
            "agent": "CRITIC",
            "icon": "🔍",
            "color": "#22c55e",  # Green when convinced
            "message": f"✅ {verdict['message']}",
            "timestamp": _dt.now().isoformat(),
        })
        await _broadcast({
            "type": "dialogue",
            "agent": "SYSTEM",
            "icon": "⚡",
            "color": "#eab308",
            "message": f"🏛️ PATH MARKED: User-Validated. The Architect may proceed with full board endorsement.",
            "timestamp": _dt.now().isoformat(),
        })
    else:
        await _broadcast({
            "type": "dialogue",
            "agent": "CRITIC",
            "icon": "🔍",
            "color": "#ef4444",
            "message": f"❌ {verdict['message']}",
            "timestamp": _dt.now().isoformat(),
        })

    # Broadcast challenge resolution event
    await _broadcast({
        "type": "challenge_resolved",
        "challenge_id": challenge_id,
        "verdict": verdict["verdict"],
        "validation": verdict["validation"],
        "new_persuasion": _persuasion_score,
    })
    await _broadcast({"type": "persuasion_update", "score": _persuasion_score, "reason": f"Convince result: {verdict['verdict']}"})

    return verdict


@app.post("/api/warroom/force_proceed")
async def warroom_force_proceed(request: Request):
    """Commander Hard Override — log risks and release lock."""
    global _persuasion_score

    if not _challenger:
        return JSONResponse({"error": "Socratic Challenger not loaded"}, status_code=500)

    body = await request.json()
    challenge_id = body.get("challenge_id", "")
    commander_note = body.get("note", "Commander override — proceeding.")

    override = _challenger.force_proceed(challenge_id, commander_note)

    if "error" in override:
        return JSONResponse(override, status_code=404)

    _persuasion_score = min(10, _persuasion_score + 2)

    # Broadcast the override
    await _broadcast({
        "type": "dialogue",
        "agent": "SYSTEM",
        "icon": "⚡",
        "color": "#eab308",
        "message": f"🚨 HARD OVERRIDE — Commander has bypassed Critic deliberation. Risk level: {override['risk_level'].upper()}.",
        "timestamp": _dt.now().isoformat(),
    })

    await asyncio.sleep(0.5)
    await _broadcast({
        "type": "dialogue",
        "agent": "CRITIC",
        "icon": "🔍",
        "color": "#ef4444",
        "message": f"📋 Override logged. {override['risk_description']} Audit required: {'YES (30 days)' if override['audit_required'] else 'No'}. Unaddressed weaknesses preserved in audit trail.",
        "timestamp": _dt.now().isoformat(),
    })

    await _broadcast({
        "type": "challenge_resolved",
        "challenge_id": challenge_id,
        "verdict": "OVERRIDE",
        "validation": f"Commander-Override ({override['risk_level']})",
        "new_persuasion": _persuasion_score,
        "risk_level": override["risk_level"],
    })
    await _broadcast({"type": "persuasion_update", "score": _persuasion_score, "reason": "Hard Override executed"})

    return override


# ── Phase 4: Incoming Watcher + n8n Archiver + Master Audit ───

import threading

try:
    from incoming_watcher import audit_incoming, watch_incoming
    _watcher_available = True
    logger.info("Incoming Watcher loaded.")
except ImportError:
    _watcher_available = False

try:
    from n8n_archiver import run_archive, list_workflows, identify_legacy
    _archiver_available = True
    logger.info("n8n Archiver loaded.")
except ImportError:
    _archiver_available = False

_watcher_thread = None


@app.post("/api/incoming/scan")
async def incoming_scan():
    """One-shot scan of projects/*/incoming/ directories."""
    if not _watcher_available:
        return JSONResponse({"error": "incoming_watcher.py not found"}, status_code=500)
    results = audit_incoming()
    return {"status": "ok", "files_detected": len(results), "results": results}


@app.post("/api/incoming/watch")
async def incoming_watch_start():
    """Start the background incoming file watcher."""
    global _watcher_thread
    if not _watcher_available:
        return JSONResponse({"error": "incoming_watcher.py not found"}, status_code=500)
    if _watcher_thread and _watcher_thread.is_alive():
        return {"status": "already_running"}
    _watcher_thread = threading.Thread(target=watch_incoming, args=(30,), daemon=True)
    _watcher_thread.start()
    return {"status": "watcher_started", "interval": 30}


@app.post("/api/n8n/archive")
async def n8n_archive(request: Request):
    """Archive legacy n8n workflows (V1/TEST/OLD)."""
    if not _archiver_available:
        return JSONResponse({"error": "n8n_archiver.py not found"}, status_code=500)
    body = await request.json() if request.headers.get("content-length", "0") != "0" else {}
    dry_run = body.get("dry_run", True)
    summary = run_archive(dry_run=dry_run)

    # Broadcast to War Room
    await _broadcast({
        "type": "dialogue",
        "agent": "SYSTEM",
        "icon": "⚡",
        "color": "#eab308",
        "message": f"🗄️ n8n ARCHIVE {'SCAN' if dry_run else 'COMPLETE'} — "
                   f"{summary['legacy_identified']} legacy workflows identified, "
                   f"{summary.get('archived', 0)} archived. "
                   f"Sole arbiter: {summary['sole_arbiter']}.",
        "timestamp": _dt.now().isoformat(),
    })
    return summary


@app.post("/api/audit/master_index")
async def audit_master_index():
    """Run a full Socratic Audit on MASTER_INDEX.md and post to War Room."""
    global _persuasion_score

    # Read MASTER_INDEX.md
    mi_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "MASTER_INDEX.md")
    if not os.path.exists(mi_path):
        return JSONResponse({"error": "MASTER_INDEX.md not found"}, status_code=404)

    with open(mi_path, "r", encoding="utf-8") as f:
        mi_content = f.read()

    lines = mi_content.strip().split("\n")
    sections = [l for l in lines if l.startswith("## ")]

    # Analyze the index
    analysis = {
        "total_lines": len(lines),
        "sections": len(sections),
        "self_healing_cycles": sum(1 for s in sections if "SELF_HEALING" in s),
        "deployed_modules": sum(1 for s in sections if "DEPLOY" in s.upper()),
        "error_entries": mi_content.count("### ERROR_ENTRY"),
        "fresh_boots": sum(1 for s in sections if "FRESH_BOOT" in s),
    }

    # Broadcast the audit initiation
    await _broadcast({
        "type": "dialogue",
        "agent": "SYSTEM",
        "icon": "⚡",
        "color": "#eab308",
        "message": f"📋 MASTER AUDIT INITIATED — Scanning MASTER_INDEX.md "
                   f"({analysis['total_lines']} lines, {analysis['sections']} sections, "
                   f"{analysis['self_healing_cycles']} healing cycles, "
                   f"{analysis['deployed_modules']} deployments).",
        "timestamp": _dt.now().isoformat(),
    })

    # Issue Socratic Challenge
    if _challenger:
        proposal = (
            f"MASTER_INDEX.md Audit — Current state: {analysis['total_lines']} lines, "
            f"{analysis['sections']} sections. Contains {analysis['self_healing_cycles']} "
            f"self-healing cycle logs (many UNKNOWN failures queued for review), "
            f"{analysis['error_entries']} error entries, {analysis['deployed_modules']} "
            f"deployed modules, {analysis['fresh_boots']} fresh boots. "
            f"Key sections: ERROR_REGISTRY, SELF_HEALING_CYCLE, "
            f"COMMERCIAL_INFRASTRUCTURE_UPGRADE, EXECUTIVE_LAYER_OVERHAUL."
        )

        _persuasion_score = 5  # Start neutral
        result = _challenger.evaluate(proposal, critic_score=6.0)

        if result["status"] == "PAUSED":
            _persuasion_score = 6
            await _broadcast({
                "type": "dialogue",
                "agent": "SYSTEM",
                "icon": "⚡",
                "color": "#eab308",
                "message": f"🛑 STRATEGIC PAUSE — MASTER_INDEX audit score 6.0/9.5. "
                           f"Gap: {result['gap']}. Critic deliberation required.",
                "timestamp": _dt.now().isoformat(),
            })

            await _broadcast({
                "type": "challenge",
                "challenge_id": result["challenge_id"],
                "score": 6.0,
                "threshold": _challenger.PAUSE_THRESHOLD,
                "gap": result["gap"],
                "weaknesses": result["weaknesses"],
            })

            for w in result["weaknesses"]:
                await asyncio.sleep(0.6)
                await _broadcast({
                    "type": "dialogue",
                    "agent": "CRITIC",
                    "icon": "🔍",
                    "color": "#ef4444",
                    "message": f"⚠️ [{w['severity']}] {w['category']}: {w['challenge']}",
                    "timestamp": _dt.now().isoformat(),
                })

            await asyncio.sleep(0.4)
            await _broadcast({
                "type": "dialogue",
                "agent": "CRITIC",
                "icon": "🔍",
                "color": "#ef4444",
                "message": "🏛️ Commander: The MASTER_INDEX audit reveals structural concerns. "
                           "Present your evidence or invoke Hard Override.",
                "timestamp": _dt.now().isoformat(),
            })

            await _broadcast({
                "type": "persuasion_update",
                "score": _persuasion_score,
                "reason": "MASTER_INDEX audit initiated",
            })

        result["analysis"] = analysis
        return result

    return {"status": "no_challenger", "analysis": analysis}


# ── Brand Studio API ──────────────────────────────────────
# Import BrandRegistry for the Brand Studio panel
try:
    sys.path.insert(0, os.path.join(SCRIPT_DIR, "Project_Aether"))
    from brand_guardian import BrandRegistry
    _brand_registry = BrandRegistry()
    BRAND_READY = True
    logger.info("BrandRegistry loaded.")
except ImportError:
    BRAND_READY = False
    _brand_registry = None
    logger.warning("BrandRegistry not available.")


class BrandDescribeRequest(BaseModel):
    project_name: str
    description: str


class BrandGenerateRequest(BaseModel):
    project_name: str


@app.get("/api/brand/{project_name}")
def get_brand(project_name: str):
    """Return current brand identity for a project."""
    if not BRAND_READY:
        return {"brand": None, "error": "BrandRegistry not available"}
    # Search for project directory
    for search_root in [SCRIPT_DIR, os.path.join(SCRIPT_DIR, "projects")]:
        project_dir = os.path.join(search_root, project_name)
        if os.path.isdir(project_dir):
            brand = _brand_registry.resolve(project_dir, tier="factory")
            return {"brand": brand}
    # Check if it's the Factory root itself
    if project_name in ("Meta_App_Factory", "Antigravity"):
        return {"brand": _brand_registry.master_brand}
    return {"brand": None}


@app.post("/api/brand/generate")
def brand_generate(req: BrandGenerateRequest):
    """AI-generate a brand identity for a project using CMO + Designer pattern."""
    if not BRAND_READY:
        return {"status": "error", "message": "BrandRegistry not available"}
    # Resolve project directory
    project_dir = None
    for search_root in [SCRIPT_DIR, os.path.join(SCRIPT_DIR, "projects")]:
        candidate = os.path.join(search_root, req.project_name)
        if os.path.isdir(candidate):
            project_dir = candidate
            break
    if not project_dir:
        return {"status": "error", "message": f"Project '{req.project_name}' not found"}

    # Generate brand using CMO agent via n8n (or fallback to template)
    from datetime import datetime
    brand_data = {
        "company_name": req.project_name,
        "mission": f"AI-powered solutions for {req.project_name}",
        "tagline": f"{req.project_name} — Built by AI, designed for humans",
        "sector": "AI/Technology",
        "colors": {
            "primary": "#06b6d4",
            "secondary": "#8b5cf6",
            "accent": "#f59e0b",
            "background": "#0a0a0f",
            "surface": "#111827",
            "text": "#e2e8f0",
        },
        "fonts": {"heading": "Outfit", "body": "Inter", "mono": "JetBrains Mono"},
        "tone_of_voice": "Professional, innovative, approachable",
        "visual_style": "Modern, clean, dark-mode-first with vibrant accents",
        "tier": "ai-generated",
        "created_at": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat(),
    }

    try:
        # Try to enrich via CMO agent
        cmo_url = "https://humanresource.app.n8n.cloud/webhook/cmo-v2"
        cmo_prompt = (
            f"Generate a brand identity for a project called '{req.project_name}'. "
            f"Return JSON with: company_name, tagline, mission, colors (primary/secondary/accent hex), "
            f"fonts (heading/body), tone_of_voice, visual_style."
        )
        import requests as _req
        resp = _req.post(cmo_url, json={"prompt": cmo_prompt, "sessionId": "brand-studio"}, timeout=15)
        if resp.status_code == 200:
            cmo_data = resp.json()
            cmo_text = cmo_data.get("text") or cmo_data.get("output") or ""
            # Try to extract JSON from CMO response
            if "{" in cmo_text:
                import re
                json_match = re.search(r'\{[^{}]*\}', cmo_text, re.DOTALL)
                if json_match:
                    try:
                        enriched = json.loads(json_match.group())
                        brand_data.update({k: v for k, v in enriched.items() if v})
                    except json.JSONDecodeError:
                        pass
    except Exception as e:
        logger.warning(f"CMO enrichment failed, using template: {e}")

    # Save to project
    brand_path = _brand_registry.create_brand(project_dir, brand_data)
    return {"status": "ok", "brand": brand_data, "path": brand_path}


@app.post("/api/brand/upload")
async def brand_upload(file: UploadFile = File(...), project_name: str = ""):
    """Extract brand identity from an uploaded file (JSON, image, or document)."""
    if not BRAND_READY:
        return {"status": "error", "message": "BrandRegistry not available"}
    if not project_name:
        return {"status": "error", "message": "project_name is required"}

    # Resolve project directory
    project_dir = None
    for search_root in [SCRIPT_DIR, os.path.join(SCRIPT_DIR, "projects")]:
        candidate = os.path.join(search_root, project_name)
        if os.path.isdir(candidate):
            project_dir = candidate
            break
    if not project_dir:
        return {"status": "error", "message": f"Project '{project_name}' not found"}

    content = await file.read()
    filename = file.filename or "upload"

    from datetime import datetime
    # Handle JSON files directly
    if filename.endswith(".json"):
        try:
            brand_data = json.loads(content.decode("utf-8"))
            brand_data["tier"] = "user-provided"
            brand_data["last_updated"] = datetime.now().isoformat()
            brand_path = _brand_registry.create_brand(project_dir, brand_data)
            return {"status": "ok", "brand": brand_data, "path": brand_path}
        except json.JSONDecodeError:
            return {"status": "error", "message": "Invalid JSON in uploaded file"}

    # For images/PDFs: save to soul/ and create placeholder brand
    soul_dir = os.path.join(project_dir, "soul")
    os.makedirs(soul_dir, exist_ok=True)
    asset_path = os.path.join(soul_dir, filename)
    with open(asset_path, "wb") as f:
        f.write(content)

    brand_data = {
        "company_name": project_name,
        "logo_path": asset_path,
        "tier": "user-provided",
        "source_file": filename,
        "colors": {},
        "fonts": {},
        "tone_of_voice": "",
        "visual_style": "",
        "created_at": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat(),
    }
    brand_path = _brand_registry.create_brand(project_dir, brand_data)
    return {"status": "ok", "brand": brand_data, "path": brand_path, "asset_saved": asset_path}


@app.post("/api/brand/describe")
def brand_describe(req: BrandDescribeRequest):
    """Create brand identity from a natural language description."""
    if not BRAND_READY:
        return {"status": "error", "message": "BrandRegistry not available"}

    # Resolve project directory
    project_dir = None
    for search_root in [SCRIPT_DIR, os.path.join(SCRIPT_DIR, "projects")]:
        candidate = os.path.join(search_root, req.project_name)
        if os.path.isdir(candidate):
            project_dir = candidate
            break
    if not project_dir:
        return {"status": "error", "message": f"Project '{req.project_name}' not found"}

    from datetime import datetime
    # Use CMO agent to interpret the description
    brand_data = {
        "company_name": req.project_name,
        "tier": "described",
        "source_description": req.description,
        "colors": {"primary": "#06b6d4", "secondary": "#14b8a6", "accent": "#d4a574", "background": "#0a0a0f", "text": "#e2e8f0"},
        "fonts": {"heading": "Outfit", "body": "Inter"},
        "tone_of_voice": "Professional, innovative",
        "visual_style": req.description,
        "created_at": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat(),
    }

    try:
        cmo_url = "https://humanresource.app.n8n.cloud/webhook/cmo-v2"
        cmo_prompt = (
            f"A user described their brand vision for '{req.project_name}' as: \"{req.description}\"\n\n"
            f"Based on that description, generate a brand identity. Return JSON with: "
            f"company_name, tagline, mission, colors (primary/secondary/accent as hex), "
            f"fonts (heading/body), tone_of_voice, visual_style."
        )
        import requests as _req
        resp = _req.post(cmo_url, json={"prompt": cmo_prompt, "sessionId": "brand-studio"}, timeout=15)
        if resp.status_code == 200:
            cmo_data = resp.json()
            cmo_text = cmo_data.get("text") or cmo_data.get("output") or ""
            if "{" in cmo_text:
                import re
                json_match = re.search(r'\{[^{}]*\}', cmo_text, re.DOTALL)
                if json_match:
                    try:
                        enriched = json.loads(json_match.group())
                        brand_data.update({k: v for k, v in enriched.items() if v})
                    except json.JSONDecodeError:
                        pass
    except Exception as e:
        logger.warning(f"CMO interpretation failed, using defaults: {e}")

    brand_path = _brand_registry.create_brand(project_dir, brand_data)
    return {"status": "ok", "brand": brand_data, "path": brand_path}


# ── Phantom QA Standalone Endpoints ───────────────────────────

class PhantomRequest(BaseModel):
    app_name: str
    url: str = ""
    frontend_url: str = ""
    description: str = ""
    stages: list[str] | None = None

@app.post("/api/phantom/run")
def phantom_run(req: PhantomRequest):
    """Run Phantom QA Gate on demand for any app."""
    if not PHANTOM_AVAILABLE:
        return JSONResponse({"error": "Phantom QA Gate not available"}, status_code=503)
    try:
        app_dir = os.path.join(SCRIPT_DIR, req.app_name)
        context = {
            "app_name": req.app_name,
            "base_url": req.url,
            "frontend_url": req.frontend_url,
            "app_dir": app_dir if os.path.isdir(app_dir) else "",
            "description": req.description,
        }
        if req.stages:
            context["stages"] = req.stages
        verdict = run_phantom_gate(context)
        return {
            "verdict": verdict.get("verdict"),
            "score": verdict.get("score"),
            "report_path": verdict.get("report_path"),
            "duration": verdict.get("duration_seconds"),
            "stages": {k: {"score": v.get("score"), "passed": v.get("passed")}
                       for k, v in verdict.get("stages", {}).items()},
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/phantom/reports")
def phantom_reports():
    """List recent Phantom QA reports."""
    reports_dir = os.path.join(SCRIPT_DIR, "Project_Aether", "C-Suite_Active_Logic",
                               "Phantom_QA", "reports")
    if not os.path.isdir(reports_dir):
        return {"reports": []}
    files = sorted(
        [f for f in os.listdir(reports_dir) if f.endswith(".md")],
        reverse=True
    )[:20]
    return {"reports": files}

@app.get("/api/phantom/report/{filename}")
def phantom_report(filename: str):
    """Serve a specific Phantom QA report."""
    reports_dir = os.path.join(SCRIPT_DIR, "Project_Aether", "C-Suite_Active_Logic",
                               "Phantom_QA", "reports")
    filepath = os.path.join(reports_dir, filename)
    if not os.path.exists(filepath) or not filename.endswith(".md"):
        return JSONResponse({"error": "Report not found"}, status_code=404)
    return FileResponse(filepath, media_type="text/markdown")


# ── Startup: Auto-start incoming watcher ──────────────────
@app.on_event("startup")
async def _startup_watcher():
    global _watcher_thread
    if _watcher_available:
        _watcher_thread = threading.Thread(target=watch_incoming, args=(60,), daemon=True)
        _watcher_thread.start()
        logger.info("Incoming Watcher auto-started (60s poll)")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

# V3 MIGRATION COMPLETE
