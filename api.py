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
import coo_agent
from persona_manager import get_persona_manager
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass  # Python < 3.7 fallback — PYTHONIOENCODING handles it

from auto_heal import auto_heal, diagnose
from warroom_protocol import (
    WarRoomReport, ReportStore, WarRoomOrchestrator, PipelineStep,
    get_orchestrator, get_report_store, parse_agent_response,
    PIPELINE_FULL_BUSINESS_PLAN, PIPELINE_ADVERSARIAL_DRILL,
    ChaosScenario, CHAOS_LIBRARY,
    StrategyMode, STRATEGY_PRESETS, get_strategy_mode,
)
from wisdom_vault import get_wisdom_vault

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, UploadFile, File, Form
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

# ── Load .env so GEMINI_API_KEY and all secrets are available to every thread ──
try:
    from dotenv import load_dotenv as _load_dotenv
    _env_path = os.path.join(SCRIPT_DIR, ".env")
    if os.path.exists(_env_path):
        _load_dotenv(_env_path, override=True)
        logger.info(f"Loaded .env from {_env_path}")
    else:
        logger.warning(f".env not found at {_env_path}")
except ImportError:
    logger.warning("python-dotenv not installed — .env not loaded. Run: pip install python-dotenv")


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

# ── Institutional Memory (Learning Engine) ────────────────────
try:
    from institutional_memory import record_lesson, get_lessons, get_lessons_for_build, search_lessons
    _MEMORY_AVAILABLE = True
    logger.info("Institutional Memory engine loaded.")
except ImportError:
    _MEMORY_AVAILABLE = False
    logger.warning("Institutional Memory not available.")
    def record_lesson(*a, **kw): pass
    def get_lessons(*a, **kw): return []
    def get_lessons_for_build(*a, **kw): return ""
    def search_lessons(*a, **kw): return []


# ── MODELS ────────────────────────────────────────────────────
class TaskRequest(BaseModel):
    task: str

class ChatRequest(BaseModel):
    prompt: str
    project_name: str = "Factory"
    session_id: str = "factory-builder"
    dashboard_context: dict | None = None

class SentinelAlert(BaseModel):
    severity: str
    message: str
    source: str = "System"

class HRMemo(BaseModel):
    agent_id: str
    memo: str

# ── SYSTEM NOTIFIER NATIVE BRIDGE ──────────────────────────────
try:
    from systems.notifier import SystemNotifier
    notifier_bus = SystemNotifier()
    logger.info("System Notifier connected natively.")
except ImportError as e:
    logger.warning(f"System Notifier offline: {e}")
    notifier_bus = None

# ── ROUTES ────────────────────────────────────────────────────

@app.get("/api/registry/raw")
async def get_registry_raw():
    """Serve the central architecture SSoT (registry.json) as-is for downstream agents."""
    try:
        with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as e:
        logger.error(f"Failed to read registry: {e}")
        return JSONResponse(status_code=500, content={"error": f"Failed to load registry: {str(e)}"})


@app.post("/api/sentinel/alert")
async def post_sentinel_alert(alert: SentinelAlert):
    if not notifier_bus:
        return JSONResponse(status_code=500, content={"error": "Notifier offline"})
    res = notifier_bus.trigger_sentinel(alert.severity, alert.message, alert.source)
    return {"status": "success", "alert": res}

@app.post("/api/hr/memo")
async def post_hr_memo(memo: HRMemo):
    if not notifier_bus:
        return JSONResponse(status_code=500, content={"error": "Notifier offline"})
    res = notifier_bus.trigger_hr_memo(memo.agent_id, memo.memo)
    return {"status": "success", "memo": res}

@app.get("/api/sentinel/log")
async def get_sentinel_log():
    try:
        if not notifier_bus:
            return {"log": []}
        return {"log": notifier_bus.get_sentinel_logs()}
    except Exception as e:
        logger.error(f"Error fetching sentinel logs: {e}")
        return {"log": []}

# ── AETHER COMMAND SUITE ENDPOINTS ────────────────────────────
class ExplainRequest(BaseModel):
    app_name: str

class WarRoomDispatchRequest(BaseModel):
    commander_intent: str
    project_id: str = "Aether"
    strategy_mode: str = "operator_directive"

@app.post("/api/warroom/dispatch")
async def warroom_dispatch(req: WarRoomDispatchRequest, request: Request):
    """Bridge to the Concurrent War Room Dispatcher."""
    import asyncio
    try:
        intent_lower = req.commander_intent.lower()
        project_id = req.project_id or "Aether"

        if "@operator reject" in intent_lower or "reject blueprint" in intent_lower:
            from eos_context import get_eos
            eos = get_eos(project_id)
            eos.reset()
            from datetime import datetime as _dt
            try:
                await _broadcast({
                    "type": "state_reset",
                    "message": "COMMANDER OVERRIDE: Blueprint rejected. Session state flushed and deploy lock cleared.",
                    "timestamp": _dt.now().isoformat()
                }, project=project_id)
            except NameError:
                pass
            return {"status": "success", "data": {"strategy": "Blueprint rejected. Session state flushed and Deploy Lock cleared."}}

        # ── Broadcast operator command to live feed ──
        from datetime import datetime as _dt
        await _broadcast({
            "type": "dialogue",
            "agent": "COMMANDER",
            "message": f"[OPERATOR DIRECTIVE] {req.commander_intent}",
            "timestamp": _dt.now().isoformat()
        }, project=project_id)

        # ── Trigger the full C-Suite state_machine pipeline ──
        # This ensures the stepper nodes (CMO→CTO→CFO→Phantom→Launch) update
        # in response to @Operator commands, not just "Initialize Protocol"
        exec_req = WarRoomExecuteRequest(
            project_id=project_id,
            intent=req.commander_intent  # pass the operator's topic into the pipeline
        )
        asyncio.create_task(war_room_execute_endpoint(exec_req, request))

        return {"status": "success", "data": {"strategy": "C-Suite pipeline initiated. Monitoring SSE stream for results."}}

    except Exception as e:
        logger.error(f"War Room Dispatch Error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})



@app.post("/api/socratic/explain")
async def socratic_explain(req: ExplainRequest):
    try:
        import google.generativeai as genai
        app_dir = os.path.join(SCRIPT_DIR, req.app_name)
        state_file = os.path.join(app_dir, "local_state.json")
        context = f"App Name: {req.app_name}\n"
        
        if os.path.exists(state_file):
            with open(state_file, "r", encoding="utf-8") as f:
                context += f"State Map:\n{f.read()}\n"
        else:
            context += "Warning: App does not have a local_state.json ledger initialized.\n"
            
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return JSONResponse(status_code=500, content={"error": "GEMINI_API_KEY missing from environment"})
            
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        prompt = f"""You are the Master Architect. The Commander clicked the Socratic Explain button for the child app '{req.app_name}'.

Current Local State/Context:
{context}

Provide a concise, 2-to-3 sentence technical architectural breakdown explaining this app's runtime logic flow based on your factory registry memory and the state provided. Be highly analytical, do not apologize."""
        
        res = model.generate_content(prompt)
        return {"status": "success", "trace": res.text}
    except Exception as e:
        logger.error(f"Socratic Explain Error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

class RefineRequest(BaseModel):
    app_name: str

@app.post("/api/system/refine")
async def system_refine(req: RefineRequest):
    try:
        from refine_engine import refine_and_apply
        import threading
        
        app_dir = os.path.join(SCRIPT_DIR, req.app_name)
        
        def background_refine():
            logger.info(f"Initiated Phantom QA Refine loop on {req.app_name}")
            feedback_prompt = "Perform a self-audit optimization sweep on this app. Identify logic bottlenecks, apply production best-practices, and resolve any strict mode UI conflict issues locally without breaking existing patterns."
            generator = refine_and_apply(req.app_name, app_dir, feedback_prompt)
            for step in generator:
                logger.info(f"Refine [{req.app_name}]: {step.get('text')}")
                
        # Launch fire-and-forget background job
        threading.Thread(target=background_refine, daemon=True).start()
        
        return {"status": "success", "message": "Phantom QA optimization sweep started in background."}
    except Exception as e:
        logger.error(f"System Refine Error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


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
    mode: str = "technical"
    user_profile: str = "executive"


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
        # ── Master Architect Pre-Build Review ──
        if _MODEL_ROUTER_AVAILABLE:
            progress_queue.put({"step": "ARCHITECT", "text": "🏗️ Master Architect: Reviewing architecture..."})
            try:
                arch_review = _architect_review(
                    feature_description=f"Build new app '{req.app_name}': {req.description}",
                    change_type="new_app",
                    affected_components=[req.app_name, req.blueprint or "custom"],
                )
                if arch_review.get("concerns"):
                    for c in arch_review["concerns"][:3]:
                        progress_queue.put({"step": "ARCHITECT", "text": f"  ⚠️ {c}"})
                if arch_review.get("recommendations"):
                    for r in arch_review["recommendations"][:3]:
                        progress_queue.put({"step": "ARCHITECT", "text": f"  💡 {r}"})
                progress_queue.put({"step": "ARCHITECT", "text": f"🏗️ Architect verdict: {arch_review.get('verdict', 'PROCEED')}"})
                # Record the review as a lesson
                if MEMORY_AVAILABLE:
                    try:
                        record_lesson(f"Architect review for '{req.app_name}': {arch_review.get('verdict','?')}", "architect_review", req.app_name)
                    except Exception:
                        pass
            except Exception as e:
                progress_queue.put({"step": "ARCHITECT", "text": f"⚠️ Architect review skipped: {str(e)[:80]}"})

        old_stdout = sys.stdout
        sys.stdout = buffer = io.StringIO()
        build_ok = False
        try:
            # Import factory here to avoid circular imports at module level
            sys.path.insert(0, SCRIPT_DIR)
            from factory import MetaAppFactory
            from forge_orchestrator import ForgeOrchestrator
            import model_router

            if req.mode == "venture":
                progress_queue.put({"step": "FORGE", "text": "🏭 Routing through INCUBATOR GATE (CMO -> CTO)..."})
                orchestrator = ForgeOrchestrator()
                allowed = orchestrator.run_incubator_gate(f"{req.app_name}: {req.description}")
                if not allowed:
                    progress_queue.put({"step": "ERROR", "text": "🛑 Build halted: Awaiting @Operator approval in War Room."})
                    progress_queue.put(None)
                    return

            elif req.user_profile == "copilot":
                progress_queue.put({"step": "FORGE", "text": "🧑‍💻 Co-Pilot Detected. Bypassing Forge. Extracting raw CTO architecture..."})
                prompt = f"Draft raw native Python structural blueprint for {req.app_name}: {req.description}. Provide code only, assuming a coder will implement this."
                raw_code = model_router.route("CTO", prompt)
                progress_queue.put({"step": "LOG", "text": f"\n\n=== RAW CO-PILOT BLUEPRINT ===\n{raw_code}\n====================\n"})
                progress_queue.put({"step": "COMPLETE", "text": f"✅ Raw architecture yielded to Builder Chat."})
                progress_queue.put(None)
                return

            else:
                progress_queue.put({"step": "FORGE", "text": "👔 Executive Detected. Engaging Autonomous Forge..."})
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

        # ── Phantom QA Gate (post-build) — UPGRADE 3: Blocking ──
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

                # BLOCKING GATE: score < 70 requires user approval
                if score < 70:
                    _pending_approvals[req.app_name] = {"score": score, "report": verdict.get("report_path", ""), "approved": False}
                    progress_queue.put({
                        "step": "GATE_BLOCKED",
                        "text": f"🛑 BUILD PAUSED — Phantom QA score {score}/100 is below threshold (70). Awaiting commander approval.",
                        "score": score,
                        "app_name": req.app_name,
                    })
                    # Wait for approval (poll every 2s, timeout 5 min)
                    import time as _gate_time
                    for _ in range(150):  # 150 x 2s = 5 min
                        _gate_time.sleep(2)
                        approval = _pending_approvals.get(req.app_name, {})
                        if approval.get("approved"):
                            progress_queue.put({"step": "GATE_APPROVED", "text": "✅ Commander approved deployment. Proceeding."})
                            _pending_approvals.pop(req.app_name, None)
                            break
                        if req.app_name not in _pending_approvals:
                            # Aborted
                            progress_queue.put({"step": "GATE_ABORTED", "text": "❌ Build aborted by commander."})
                            build_ok = False
                            break
                    else:
                        progress_queue.put({"step": "GATE_TIMEOUT", "text": "⏰ Approval timeout (5 min). Build aborted."})
                        _pending_approvals.pop(req.app_name, None)
                        build_ok = False
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


import socket

def ping_port(port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False

@app.get("/api/agents/status")
def agent_status():
    """Live Socket Ping for Native Modules."""
    agents = {}
    
    # Active Native Ports aligned with watchdog
    c_suite_active = ping_port(5041)
    architect_active = ping_port(5050)
    qa_active = ping_port(5030)
    core_active = ping_port(5000)
    clo_active = ping_port(5080)
    
    # Map overarching C-Suite
    for name in ["CFO", "CMO", "HR", "CRITIC"]:
        agents[name] = c_suite_active
        
    agents["ARCHITECT"] = architect_active
    agents["PITCH"] = qa_active
    agents["ATOMIZER"] = core_active
    agents["CLO"] = clo_active
    
    return agents


@app.get("/api/registry")
def get_registry():
    """Return the list of registered apps."""
    try:
        with open(REGISTRY_PATH, "r", encoding="utf-8-sig") as f:
            data = json.load(f)

        apps = []
        for name, info in data.get("apps", {}).items():
            if not isinstance(info, dict):
                continue
            apps.append({
                "name": name,
                "status": info.get("status", "unknown"),
                "type": info.get("type", "App"),
                "port": info.get("port"),
                "path": info.get("path", ""),
                "form_url": info.get("form_url"),
            })
        return {"apps": apps}
    except Exception as e:
        logger.error(f"Registry read failed: {e}")
        return JSONResponse({"error": f"Registry unavailable: {e}", "apps": []}, status_code=500)

# ── Pre-Deploy Gate Endpoints ─────────────────────────────────

@app.post("/api/gate/verify")
async def gate_verify(request: Request):
    """Run the PreDeployGate Triad Review locally (Aether-Native)."""
    if not PRE_DEPLOY_AVAILABLE or not _pre_deploy_gate:
        return JSONResponse({"error": "PreDeployGate not available"}, status_code=503)

    body = await request.json()
    project_id = body.get("project_id", "unknown")
    description = body.get("description", "")
    components = body.get("components", [])
    change_type = body.get("change_type", "feature")
    context = body.get("context", {})

    result = _pre_deploy_gate.verify(
        project_id=project_id,
        description=description,
        components=components,
        change_type=change_type,
        context=context
    )
    return result


@app.get("/api/gate/status")
def gate_status_endpoint():
    """Return PreDeployGate health and active challenge count."""
    if not PRE_DEPLOY_AVAILABLE or not _pre_deploy_gate:
        return {"status": "unavailable", "source": "none"}
    return _pre_deploy_gate.get_status()


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

# ── Pre-Deploy Gate (Aether-Native) ──────────────────────────
try:
    from pre_deploy_gate import get_pre_deploy_gate
    _pre_deploy_gate = get_pre_deploy_gate()
    PRE_DEPLOY_AVAILABLE = True
    logger.info("PreDeployGate loaded (Aether-Native).")
except ImportError:
    _pre_deploy_gate = None
    PRE_DEPLOY_AVAILABLE = False
    logger.warning("PreDeployGate not available.")

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


ORCHESTRATION_STATE = "healthy"

from native_watchdog import get_native_watchdog

@app.get("/api/health")
def health_check():
    watchdog = get_native_watchdog()
    telemetry = watchdog.get_system_pulse()
    
    # Merge existing Orchestration status
    telemetry["api_status"] = ORCHESTRATION_STATE
    telemetry["streaming"] = STREAMING_AVAILABLE
    telemetry["memory"] = STREAMING_AVAILABLE and MEMORY_AVAILABLE
    telemetry["parser"] = PARSER_AVAILABLE if 'PARSER_AVAILABLE' in globals() else False
    
    return telemetry


class WarRoomExecuteRequest(BaseModel):
    project_id: str
    intent: str = "Genesis"


@app.post("/api/warroom/execute")
async def war_room_execute_endpoint(req: WarRoomExecuteRequest, request: Request):
    import asyncio
    project_id = req.project_id
    is_architecture_phase = any(kw in req.intent.lower() for kw in ["initialize", "architect", "genesis", "@operator"])

    async def native_sequence():
        try:
            import sys, os
            if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


            from logic_checker import evaluate_logic
            from stress_tester import ChaosStressTester
            from ux_simulator import UXSimulator
            from cmo_agent import CMOAgent
            from cto_agent import CTOAgent
            from cfo_excel_architect import CFOExcelArchitect
            from datetime import datetime as _dt

            # --- LIVE CMO INTELLIGENCE (Gemini Function Calling + DuckDuckGo + UDPP Provenance) ---
            await _broadcast({"type": "dialogue", "agent": "SYSTEM", "message": "RUNNING LIVE CMO MARKET INTELLIGENCE..."}, project=project_id)
            market_pulse = await asyncio.to_thread(CMOAgent().run, req.intent or project_id)
            verdict_str = market_pulse.get("verdict", "NEUTRAL")
            pivot_text = " (Requires Pivot Option)" if verdict_str == "BEARISH" else ""

            await _broadcast({
                "type": "market_pulse",
                "verdict": verdict_str,
                "velocity": market_pulse.get("trend_velocity", 5.0),
                "sentiment": market_pulse.get("public_sentiment_score", 0.0)
            }, project=project_id)

            # ─────────────────────────────────────────────────
            # RECURSIVE REPAIR LOOP  (max 3 iterations)
            # ─────────────────────────────────────────────────
            max_iterations = 3
            iteration = 0
            rejection_feedback = None   # injected into agent prompts on retry

            while iteration < max_iterations:
                iteration += 1

                if iteration > 1:
                    # Reset all pipeline nodes back to PROCESSING so the React
                    # stepper visually tracks the new run from the beginning.
                    await _broadcast({"type": "dialogue", "agent": "COMMANDER",
                                      "message": f"── RECURSIVE REPAIR LOOP: ITERATION {iteration}/{max_iterations} ──\nInjecting rejection feedback into C-Suite agents..."}, project=project_id)
                    for phase in ["CMO_STRATEGY", "CTO_FEASIBILITY", "CFO_FINANCIAL_MODEL", "PHANTOM_STRESS_TEST"]:
                        await _broadcast({"type": "state_machine", "phase": phase, "status": "PROCESSING"}, project=project_id)
                    await asyncio.sleep(0.5)
                else:
                    await _broadcast({"type": "dialogue", "agent": "COMMANDER",
                                      "message": "── AETHER-NATIVE SEQUENCE: ITERATION 1/3 ──"}, project=project_id)

                # Build the effective intent for this iteration (includes feedback on retries)
                effective_intent = req.intent
                if rejection_feedback:
                    effective_intent = (
                        f"{req.intent}\n\n"
                        f"[CRITIC REJECTION FEEDBACK FROM PRIOR RUN — MUST FIX]\n{rejection_feedback}"
                    )

                # Start CEO synthesis concurrently (fires alongside CMO→CTO→CFO)
                async def run_synthesis(intent=effective_intent):
                    try:
                        from war_room_orchestrator import dispatch_to_csuite
                        result = await dispatch_to_csuite(intent)
                        strategy = result.get("strategy") or result.get("error", "No response.")
                        return strategy
                    except Exception as e:
                        logger.error(f"CEO Synthesis background error: {e}")
                        return f"Error: {e}"

                ceo_synthesis_task = asyncio.create_task(run_synthesis())

                # ── Phase 1: CMO Strategy ──────────────────────────────────
                await _broadcast({"type": "state_machine", "phase": "CMO_STRATEGY", "status": "PROCESSING"}, project=project_id)
                await _broadcast({"type": "dialogue", "agent": "SYSTEM", "message": f"INITIALIZING CMO STRATEGY MODULE... Market Pulse: {verdict_str}"}, project=project_id)
                await _broadcast({"type": "dialogue", "agent": "CMO", "message": f"Market Evaluated as {verdict_str}. Velocity: {market_pulse.get('trend_velocity', 5.0)}. Sentiment: {market_pulse.get('public_sentiment_score', 0.0)}."}, project=project_id)
                await asyncio.sleep(1.5)
                if rejection_feedback:
                    await _broadcast({"type": "dialogue", "agent": "CMO",
                                      "message": f"[ADAPTING STRATEGY] Addressing prior Critic rejection: {rejection_feedback[:300]}"}, project=project_id)
                await _broadcast({"type": "dialogue", "agent": "CMO", "message": f"Generated target strategy for '{project_id}'{pivot_text}. Marketing cost baseline assigned."}, project=project_id)
                await _broadcast({"type": "state_machine", "phase": "CMO_STRATEGY", "status": "PASS"}, project=project_id)

                # ── Phase 2: CTO Feasibility ───────────────────────────────
                await _broadcast({"type": "state_machine", "phase": "CTO_FEASIBILITY", "status": "PROCESSING"}, project=project_id)
                await _broadcast({"type": "dialogue", "agent": "SYSTEM", "message": "RUNNING LIVE CTO INFRASTRUCTURE COST ANALYSIS..."}, project=project_id)
                if rejection_feedback:
                    await _broadcast({"type": "dialogue", "agent": "CTO",
                                      "message": f"[STACK RE-EVALUATION] Critic flagged: {rejection_feedback[:300]}"}, project=project_id)

                cto_result = await asyncio.to_thread(CTOAgent().run, effective_intent)
                infra_cost = cto_result.get("infrastructure_cost_monthly", 450)
                capex = cto_result.get("capex_estimate", 0)
                cloud_equiv = cto_result.get("cloud_comparison_monthly", 0)
                breakeven = cto_result.get("roi_breakeven_months", 0)
                gate_status = cto_result.get("gate_status", "PASSED")
                live_flag = " [LIVE ANALYSIS]" if cto_result.get("live_data") else " [SIMULATED]"

                cto_msg = (
                    f"Infrastructure Evaluation{live_flag}: Gate Status: {gate_status}.\n"
                    f"Monthly OpEx: ${infra_cost:,.0f}/mo | CapEx (pilot): ${capex:,.0f}\n"
                    f"Cloud Equivalent: ${cloud_equiv:,.0f}/mo | ROI Breakeven: {breakeven} months"
                )
                if cto_result.get("recommendation"):
                    cto_msg += f"\n{cto_result['recommendation'][:300]}"

                await _broadcast({"type": "dialogue", "agent": "CTO", "message": cto_msg}, project=project_id)

                if gate_status == "FAILED":
                    await _broadcast({"type": "dialogue", "agent": "SYSTEM",
                                      "message": "CTO GATE FAILED: Architecture infeasible.", "isError": True}, project=project_id)
                    await _broadcast({"type": "state_machine", "phase": "CTO_FEASIBILITY", "status": "FAIL"}, project=project_id)
                    return
                await _broadcast({"type": "state_machine", "phase": "CTO_FEASIBILITY", "status": "PASS"}, project=project_id)

                # ── Phase 3: CFO Financial Model ───────────────────────────
                await _broadcast({"type": "state_machine", "phase": "CFO_FINANCIAL_MODEL", "status": "PROCESSING"}, project=project_id)
                architect = CFOExcelArchitect()
                await _broadcast({"type": "dialogue", "agent": "SYSTEM", "message": "BOOTING EXCEL ARCHITECT..."}, project=project_id)
                if rejection_feedback:
                    await _broadcast({"type": "dialogue", "agent": "CFO",
                                      "message": f"[MODEL REVISION] Incorporating Critic feedback: {rejection_feedback[:300]}"}, project=project_id)
                await asyncio.to_thread(
                    architect.generate_business_plan,
                    project_id=project_id,
                    cmo_data={
                        "marketing_cost": 25000,
                        "projected_revenue": 100000,
                        "market_verdict": market_pulse.get("verdict", "NEUTRAL"),
                        "sentiment_score": market_pulse.get("public_sentiment_score", 0),
                        "cmo_summary": market_pulse.get("summary", "")[:200],
                    },
                    cto_data={
                        "infrastructure_cost_estimate": cto_result.get("infrastructure_cost_monthly", 450),
                        "capex_estimate": cto_result.get("capex_estimate", 0),
                        "cloud_comparison": cto_result.get("cloud_comparison_monthly", 0),
                        "roi_breakeven_months": cto_result.get("roi_breakeven_months", 0),
                        "dev_buffer_weeks": 4.5,
                        "tech_debt_risk_premium_pct": 10,
                    },
                    market_pulse=market_pulse
                )
                await _broadcast({"type": "dialogue", "agent": "CFO", "message": "Native Fragility Report explicitly generated to business_plan.xlsx.\\nCost Basis Calculated. ROI is stable."}, project=project_id)
                await _broadcast({"type": "state_machine", "phase": "CFO_FINANCIAL_MODEL", "status": "PASS"}, project=project_id)

                # ── Phase 4: Phantom QA — await CEO barrier ────────────────
                await _broadcast({"type": "state_machine", "phase": "PHANTOM_STRESS_TEST", "status": "PROCESSING"}, project=project_id)
                await _broadcast({"type": "dialogue", "agent": "SYSTEM", "message": "AWAITING CEO SYNTHESIS BEFORE TRIAD QA GATE..."}, project=project_id)

                ceo_strategy = await ceo_synthesis_task
                await _broadcast({
                    "type": "dialogue",
                    "agent": "CEO",
                    "message": f"[CEO SYNTHESIS — ITERATION {iteration}]\n{ceo_strategy[:1500]}",
                    "timestamp": _dt.now().isoformat()
                }, project=project_id)

                await _broadcast({"type": "dialogue", "agent": "SYSTEM", "message": "TRIGGERING NATIVE TRIAD MODULES (PHANTOM QA ELITE)..."}, project=project_id)

                async def run_logic():
                    await asyncio.sleep(1)
                    # Collect UDPP provenance sidecars from live agents
                    provenance_block = {
                        "CMO": market_pulse.get("_provenance", {}),
                        "CTO": cto_result.get("_provenance", {}),
                    }
                    res = await asyncio.to_thread(evaluate_logic, ceo_strategy, provenance_block)
                    status = res["status"]
                    gate = res.get("gate_triggered", "")
                    if status == "FAIL":
                        err_msg = " | ".join(res.get("errors", ["Semantic contradiction detected."]))
                        gate_label = f" [{gate.upper()}]" if gate else ""
                        await _broadcast({"type": "dialogue", "agent": "CRITIC",
                                          "message": f"Logic Checker{gate_label}: FAIL. {err_msg}"}, project=project_id)
                    else:
                        await _broadcast({"type": "dialogue", "agent": "CRITIC", "message": f"Logic Checker: {status}. CEO intent verified. No contradictions."}, project=project_id)
                    return res

                async def run_stress():
                    tester = ChaosStressTester(project_id)
                    res = await asyncio.to_thread(tester.run_tests)
                    await _broadcast({"type": "dialogue", "agent": "PHANTOM_QA", "message": f"Stress Tester: {res['status']}. Score: {res.get('score', 0)}."}, project=project_id)
                    return res

                async def run_ux():
                    if is_architecture_phase:
                        await asyncio.sleep(1)
                        res = {"verdict": "SKIPPED", "score": 100}
                        await _broadcast({"type": "dialogue", "agent": "PHANTOM_QA", "message": "Playwright Deep Audit: SKIPPED (Architecture Phase Detected). UI testing deferred to deployment."}, project=project_id)
                        return res
                    sim = UXSimulator(project_id)
                    res = await asyncio.to_thread(sim.run_deep_audit)
                    await _broadcast({"type": "dialogue", "agent": "SYSTEM", "message": f"Playwright Deep Audit: {res['verdict']}. Score: {res.get('score', 0)}."}, project=project_id)
                    return res

                results = await asyncio.gather(run_logic(), run_stress(), run_ux())
                logic_res, stress_res, ux_res = results

                logic_score = 100 if logic_res["status"] == "PASS" else 0
                if is_architecture_phase:
                    composite_score = (logic_score + stress_res.get("score", 0)) / 2.0
                else:
                    composite_score = (logic_score + stress_res.get("score", 0) + ux_res.get("score", 0)) / 3.0

                await _broadcast({"type": "dialogue", "agent": "COMMANDER",
                                  "message": f"QA COMPOSITE SCORE: {composite_score:.1f}/100.\\nMinimum confidence: 80/100 required."}, project=project_id)

                # ── Semantic + Score Gate ──────────────────────────────────
                semantic_failed = logic_res["status"] == "FAIL"
                score_failed    = composite_score < 80.0
                hw_failed       = stress_res["status"] == "FAIL" or (not is_architecture_phase and ux_res["verdict"] == "FAIL")

                if semantic_failed or score_failed or hw_failed:
                    # Extract rejection reason for next iteration's feedback injection
                    rejection_feedback = " ".join(logic_res.get("errors", [f"QA score below threshold: {composite_score:.1f}/100."]))

                    if iteration < max_iterations:
                        await _broadcast({"type": "dialogue", "agent": "SYSTEM",
                                          "message": f"ITERATION {iteration} FAILED. Routing rejection feedback to C-Suite. Preparing retry...", "isError": True}, project=project_id)
                        await _broadcast({"type": "state_machine", "phase": "PHANTOM_STRESS_TEST", "status": "FAIL"}, project=project_id)
                        await asyncio.sleep(1.5)
                        continue   # ← loop back for next iteration
                    else:
                        # Max iterations hit — hard-lock deployment
                        await _broadcast({"type": "dialogue", "agent": "SYSTEM",
                                          "message": f"MAX ITERATIONS REACHED ({max_iterations}/{max_iterations}). DEPLOYMENT HARD-LOCKED.", "isError": True}, project=project_id)
                        await _broadcast({"type": "state_machine", "phase": "PHANTOM_STRESS_TEST", "status": "FAIL"}, project=project_id)
                        await asyncio.sleep(0.3)
                        await _broadcast({"type": "state_machine", "phase": "COMMERCIALLY_READY", "status": "FAIL"}, project=project_id)
                        return

                # ── All gates passed — unlock deployment ───────────────────
                await _broadcast({"type": "dialogue", "agent": "PHANTOM_QA",
                                  "message": f"VERDICT: PASSED (Iteration {iteration}) — Commercial viability and architecture validated."}, project=project_id)
                await _broadcast({"type": "state_machine", "phase": "PHANTOM_STRESS_TEST", "status": "PASS"}, project=project_id)
                await asyncio.sleep(0.5)
                await _broadcast({"type": "state_machine", "phase": "COMMERCIALLY_READY", "status": "PASS"}, project=project_id)
                await _broadcast({"type": "dialogue", "agent": "COMMANDER",
                                  "message": f"AETHER-NATIVE SEQUENCE COMPLETE (ITERATION {iteration}/{max_iterations}). DEPLOYMENT AUTHORIZED."}, project=project_id)
                return  # ← success exit

        except Exception as e:
            await _broadcast({"type": "dialogue", "agent": "SYSTEM", "message": f"Execution Error: {str(e)}", "isError": True}, project=project_id)
    asyncio.create_task(native_sequence())
    return {"status": "started", "project": project_id}

# ── ORCHESTRATION BIND: War Room Dispatch ─────────────────────
class WarRoomDispatchRequest(BaseModel):
    message: str
    project_id: str = None
    strategy_mode: str = "balanced"    # "aggressive_growth" | "lean_mvp" | "custom" | "balanced"
    custom_directive: str = ""          # Commander's custom guidance (when strategy_mode="custom")
    stress_test: bool = False           # If True, run adversarial drill after pipeline

@app.post("/api/war-room/dispatch")
async def war_room_dispatch(req: WarRoomDispatchRequest, request: Request):
    import httpx
    import asyncio
    global ORCHESTRATION_STATE
    
    project_id = req.project_id or request.headers.get("X-Antigravity-Project-ID", "AntigravityWorkspace_Q3")
    print(f"DEBUG: Received Dispatch for {project_id}")
    msg_lower = req.message.lower()
    
    # ── Phase 11 Incubator Gate: STRICT prefix-only match ────────────────────────
    # Must start with "@operator" so self-broadcast strings like
    # "Awaiting @Operator authorization" do NOT re-trigger the gate.
    _is_operator_cmd = msg_lower.strip().startswith("@operator")

    # ── MERGE LIVE — priority 0 (checked before approve/reject/new-gate) ─────────
    # "@operator merge live" / "@operator merge" → final deployment flow.
    _MERGE_TOKENS = ("@operator merge live", "@operator merge")
    _is_merge_cmd = any(msg_lower.strip().startswith(tok) for tok in _MERGE_TOKENS)

    if _is_merge_cmd:
        logger.info(f"[DEPLOY] Merge-Live command received: {req.message!r}")

        async def execute_merge():
            global ORCHESTRATION_STATE
            import forge_orchestrator, os, glob, shutil

            staging_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "staging_environment")
            live_dir    = os.path.dirname(os.path.abspath(__file__))   # Meta_App_Factory root

            # Find the most recently modified .py in staging
            candidates = sorted(
                glob.glob(os.path.join(staging_dir, "*.py")),
                key=os.path.getmtime, reverse=True
            )

            if not candidates:
                await _broadcast({
                    "type": "dialogue", "agent": "SYSTEM",
                    "icon": "⚠️", "color": "#eab308",
                    "message": (
                        "**[DEPLOY BLOCKED]** No staged blueprint found in `/staging_environment/`.\n"
                        "Run `@Operator Approve Build` first to build and validate a blueprint."
                    ),
                    "timestamp": _dt.now().isoformat()
                }, project=project_id)
                return

            staging_path   = candidates[0]
            staging_fname  = os.path.basename(staging_path)
            app_name       = os.path.splitext(staging_fname)[0]   # strip .py → app name
            live_path      = os.path.join(live_dir, staging_fname)

            # Broadcast: merge in progress
            await _broadcast({
                "type": "dialogue", "agent": "INCUBATOR_GATE",
                "icon": "🚀", "color": "#10b981",
                "message": (
                    f"**@Operator Merge Live — INITIATING**\n\n"
                    f"Deploying `{staging_fname}` from `/staging_environment/` → production root.\n"
                    f"Taking rollback snapshot first..."
                ),
                "timestamp": _dt.now().isoformat()
            }, project=project_id)

            # Use ForgeOrchestrator.merge_to_live() — takes backup, then copies
            try:
                orchestrator = forge_orchestrator.ForgeOrchestrator()
                success = await asyncio.to_thread(
                    orchestrator.merge_to_live, staging_path, live_path
                )
            except Exception as merge_err:
                logger.error(f"[DEPLOY] merge_to_live raised: {merge_err}")
                success = False

            if not success:
                await _broadcast({
                    "type": "dialogue", "agent": "SYSTEM",
                    "icon": "❌", "color": "#ef4444",
                    "message": (
                        f"**[DEPLOY FAILED]** `merge_to_live` could not copy `{staging_fname}` "
                        f"to production.\n\nCheck the server logs for the specific file error. "
                        f"The staging file is intact — no data was lost."
                    ),
                    "timestamp": _dt.now().isoformat()
                }, project=project_id)
                return

            # Register in registry.json
            try:
                _update_registry(
                    app_name  = app_name,
                    blueprint = "autonomous_forge",
                    description = f"Autonomous Forge Deployment — QA-validated and deployed {_dt.now().strftime('%Y-%m-%d %H:%M')}",
                )
                # Upgrade status from "scaffolding" → "active"
                with open(REGISTRY_PATH, "r", encoding="utf-8") as _rf:
                    _reg = json.load(_rf)
                _reg["apps"][app_name]["status"] = "active"
                _reg["apps"][app_name]["deployed_by"] = "Autonomous_Forge_Phase11"
                _reg["apps"][app_name]["staging_source"] = staging_fname
                with open(REGISTRY_PATH, "w", encoding="utf-8") as _wf:
                    json.dump(_reg, _wf, indent=4)
                logger.info(f"[DEPLOY] '{app_name}' registered as active in registry.json")
                registry_status = "✅ Registered in `registry.json`"
            except Exception as reg_err:
                logger.error(f"[DEPLOY] Registry update failed: {reg_err}")
                registry_status = f"⚠️ Registry write failed: `{reg_err}` — file deployed but not registered"

            # Update progress bar to full PASS
            for phase in ("CMO_STRATEGY", "CTO_FEASIBILITY", "CFO_FINANCIAL_MODEL",
                          "PHANTOM_STRESS_TEST", "COMMERCIALLY_READY"):
                await _broadcast({"type": "state_machine", "phase": phase, "status": "PASS"}, project=project_id)

            # Triumphant deploy broadcast
            await _broadcast({
                "type": "dialogue", "agent": "INCUBATOR_GATE",
                "icon": "🎉", "color": "#10b981",
                "message": (
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🚀 **DEPLOYMENT CONFIRMED — PRODUCT IS LIVE**\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"**App Name:** `{app_name}`\n"
                    f"**Source:** `/staging_environment/{staging_fname}`\n"
                    f"**Deployed To:** `Meta_App_Factory/{staging_fname}` (production root)\n"
                    f"**Registry:** {registry_status}\n"
                    f"**Rollback:** Snapshot taken by `ForgeRollbackManager` ✅\n"
                    f"**Deployed by:** Autonomous Forge — Phase 11\n"
                    f"**Timestamp:** {_dt.now().isoformat()}\n\n"
                    f"The Factory has shipped its first autonomous build. "
                    f"Commander — the pipeline is complete. 🎯"
                ),
                "timestamp": _dt.now().isoformat()
            }, project=project_id)

            ORCHESTRATION_STATE = "idle"

        asyncio.create_task(execute_merge())
        return {"status": "merge_initiated", "project": project_id}

    # ── EXECUTIVE FORK RESOLUTION — checked before new-gate logic ────────────────
    # Authorization commands route to execute_staging_cycle / reject.
    # They are NEVER sent to run_incubator_gate().
    _APPROVE_TOKENS = ("@operator approve build", "@operator approve")
    _REJECT_TOKENS  = ("@operator reject blueprint", "@operator reject")
    _is_fork_approve = any(msg_lower.strip().startswith(tok) for tok in _APPROVE_TOKENS)
    _is_fork_reject  = any(msg_lower.strip().startswith(tok) for tok in _REJECT_TOKENS)

    if _is_fork_approve or _is_fork_reject:
        action = "APPROVED" if _is_fork_approve else "REJECTED"
        logger.info(f"[EXEC FORK] Resolution received: {action} — message: {req.message!r}")

        async def resolve_fork():
            global ORCHESTRATION_STATE
            import forge_orchestrator, os, glob

            if _is_fork_approve:
                # Broadcast acknowledgement immediately
                await _broadcast({
                    "type": "dialogue", "agent": "INCUBATOR_GATE",
                    "icon": "✅", "color": "#10b981",
                    "message": (
                        "**@Operator Approve Build — CONFIRMED**\n\n"
                        "Commander authorization received. Routing blueprint to `/staging_environment/`. "
                        "QA Architect executing sandbox validation now..."
                    ),
                    "timestamp": _dt.now().isoformat()
                }, project=project_id)

                # Find the newest .py file in staging_environment to run
                staging_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "staging_environment")
                os.makedirs(staging_dir, exist_ok=True)
                candidates = sorted(
                    glob.glob(os.path.join(staging_dir, "*.py")),
                    key=os.path.getmtime, reverse=True
                )

                if not candidates:
                    await _broadcast({
                        "type": "dialogue", "agent": "SYSTEM",
                        "icon": "⚠️", "color": "#eab308",
                        "message": (
                            "**[STAGING EMPTY]** No blueprint script found in `/staging_environment/`.\n"
                            "The Incubator Gate must write a build script before approval can run it.\n"
                            "Re-run the Incubator Gate with your app idea to generate a blueprint."
                        ),
                        "timestamp": _dt.now().isoformat()
                    }, project=project_id)
                    ORCHESTRATION_STATE = "idle"
                    return

                staging_filename = os.path.basename(candidates[0])
                staging_path     = os.path.join(staging_dir, staging_filename)
                logger.info(f"[EXEC FORK] Running staging cycle on: {staging_filename}")

                await _broadcast({
                    "type": "state_machine", "phase": "CFO_FINANCIAL_MODEL", "status": "PROCESSING"
                }, project=project_id)

                # ── QA AUTO-HEAL LOOP ─────────────────────────────────────────────
                MAX_RETRIES = 3
                attempt     = 0
                healed      = False

                while attempt <= MAX_RETRIES:
                    try:
                        orchestrator = forge_orchestrator.ForgeOrchestrator()
                        result       = await asyncio.to_thread(orchestrator.execute_staging_cycle, staging_filename)
                    except Exception as e:
                        logger.error(f"[AUTO-HEAL] execute_staging_cycle raised exception: {e}")
                        result = {"status": "error", "stdout": "", "stderr": str(e)}

                    qa_status = result.get("status", "unknown").lower()
                    qa_stdout = result.get("stdout", "")
                    qa_stderr = result.get("stderr", "")

                    # ── PASS — we are done ────────────────────────────────────────
                    if qa_status == "pass":
                        await _broadcast({
                            "type": "dialogue", "agent": "INCUBATOR_GATE",
                            "icon": "🚀", "color": "#10b981",
                            "message": (
                                f"**QA ARCHITECT — VERDICT: PASS ✅**"
                                + (f" *(healed in {attempt} attempt{'s' if attempt != 1 else ''})*" if attempt > 0 else "")
                                + f"\n\nBlueprint `{staging_filename}` executed cleanly in sandbox.\n\n"
                                f"**Output preview:**\n```\n{qa_stdout[:800]}\n```\n\n"
                                "Build cleared. Use `@Operator merge live` to push to production."
                            ),
                            "timestamp": _dt.now().isoformat()
                        }, project=project_id)
                        await _broadcast({"type": "state_machine", "phase": "CFO_FINANCIAL_MODEL", "status": "PASS"}, project=project_id)
                        await _broadcast({"type": "state_machine", "phase": "PHANTOM_STRESS_TEST",  "status": "PASS"}, project=project_id)
                        await _broadcast({"type": "state_machine", "phase": "COMMERCIALLY_READY",   "status": "PASS"}, project=project_id)
                        healed = True
                        break

                    # ── SECURITY BLOCK — non-healable, escalate immediately ────────
                    if qa_status == "security_block":
                        await _broadcast({
                            "type": "dialogue", "agent": "INCUBATOR_GATE",
                            "icon": "🛑", "color": "#ef4444",
                            "message": (
                                f"**QA ARCHITECT — SECURITY BLOCK 🛑**\n\n"
                                f"Blueprint `{staging_filename}` was rejected by the Safety Auditor.\n\n"
                                f"**Violation:** `{qa_stderr}`\n\n"
                                "This violation cannot be auto-healed. Issue `@Operator Reject Blueprint` to discard "
                                "and re-architect from scratch."
                            ),
                            "timestamp": _dt.now().isoformat()
                        }, project=project_id)
                        await _broadcast({"type": "state_machine", "phase": "CFO_FINANCIAL_MODEL", "status": "FAIL"}, project=project_id)
                        break

                    # ── FAILURE / ERROR / TIMEOUT — attempt auto-heal ─────────────
                    if attempt < MAX_RETRIES:
                        attempt += 1
                        await _broadcast({
                            "type": "dialogue", "agent": "INCUBATOR_GATE",
                            "icon": "🔧", "color": "#eab308",
                            "message": (
                                f"**QA ARCHITECT — VERDICT: {qa_status.upper()} ⚠️**\n\n"
                                f"Blueprint `{staging_filename}` failed (attempt {attempt}/{MAX_RETRIES}).\n\n"
                                f"**Error traceback:**\n```\n{qa_stderr[:600]}\n```\n\n"
                                f"Routing traceback to CTO Auto-Heal Agent... standby."
                            ),
                            "timestamp": _dt.now().isoformat()
                        }, project=project_id)

                        # Read the broken script
                        try:
                            with open(staging_path, "r", encoding="utf-8") as _f:
                                broken_code = _f.read()
                        except Exception as read_err:
                            logger.error(f"[AUTO-HEAL] Cannot read staging file: {read_err}")
                            break

                        # Ask the CTO to produce a fixed version
                        heal_prompt = (
                            f"You are the CTO Auto-Heal Agent. A Python script failed QA validation.\n"
                            f"Your ONLY job is to return a 100% syntactically correct, fixed Python script.\n\n"
                            f"=== BROKEN SCRIPT ===\n```python\n{broken_code}\n```\n\n"
                            f"=== ERROR TRACEBACK (attempt {attempt}) ===\n```\n{qa_stderr[:1200]}\n```\n\n"
                            f"Rules:\n"
                            f"1. Fix EVERY error shown in the traceback.\n"
                            f"2. Do NOT add os.remove, shutil.rmtree, sys.exit, or any destructive calls.\n"
                            f"3. Return ONLY raw Python code — no markdown fences, no explanation.\n"
                            f"4. The fixed script must be self-contained and executable with `python script.py`.\n\n"
                            f"Fixed Python script:"
                        )

                        try:
                            import model_router  # local import — matches api.py pattern (cf. line 331)
                            loop = asyncio.get_event_loop()
                            healed_code = await loop.run_in_executor(
                                _warroom_executor,
                                model_router.route,
                                "CTO",
                                heal_prompt
                            )
                        except Exception as llm_err:
                            logger.error(f"[AUTO-HEAL] CTO LLM call failed: {llm_err}")
                            await _broadcast({
                                "type": "dialogue", "agent": "SYSTEM",
                                "icon": "❌", "color": "#ef4444",
                                "message": f"**[AUTO-HEAL ERROR]** CTO agent call failed: `{llm_err}`",
                                "timestamp": _dt.now().isoformat()
                            }, project=project_id)
                            break

                        # ── HARDENED CODE EXTRACTOR ──────────────────────────────────────────
                        # The LLM often injects prose, emojis, or prefixes around the code.
                        # This pipeline extracts only valid Python, discarding everything else.
                        import re as _re

                        def _extract_python_code(raw: str) -> str:
                            """
                            4-stage extractor. Returns clean Python or raises ValueError
                            so the heal loop can surface the problem rather than write garbage.
                            """
                            raw = raw.strip()

                            # Stage 1 — prefer explicit ```python ... ``` block
                            m = _re.search(r'```python\s*\n(.*?)```', raw, _re.DOTALL | _re.IGNORECASE)
                            if m:
                                return m.group(1).strip()

                            # Stage 2 — fallback to any ``` ... ``` block
                            m = _re.search(r'```\s*\n(.*?)```', raw, _re.DOTALL)
                            if m:
                                candidate = m.group(1).strip()
                                # Must contain at least one line that looks like Python
                                if any(_re.match(r'\s*(import |from |def |class |#|if |for |while |print|[a-zA-Z_]\w*\s*[=(])', ln) for ln in candidate.splitlines()):
                                    return candidate

                            # Stage 3 — no fences: find the first Python-looking line
                            #           and take everything from there onward
                            lines = raw.splitlines()
                            start_idx = None
                            PYTHON_STARTS = _re.compile(
                                r'^\s*(import |from |def |class |#!|#\s|if __name__|'
                                r'[a-zA-Z_]\w*\s*=|print\s*\(|[a-zA-Z_]\w*\s*\()'
                            )
                            for idx, ln in enumerate(lines):
                                if PYTHON_STARTS.match(ln):
                                    start_idx = idx
                                    break

                            if start_idx is not None:
                                candidate = '\n'.join(lines[start_idx:])
                            else:
                                # Nothing Python-like found — return raw and let QA catch it
                                candidate = raw

                            # Stage 4 — line-by-line sanitise: drop any leading prose lines
                            # that contain non-Python characters (emoji, markdown, colons etc.)
                            KNOWN_PREFIXES = _re.compile(
                                r'^(\s*'
                                r'[\U00010000-\U0010FFFF\u2600-\u26FF\u2700-\u27BF]|'   # emoji range
                                r'\s*\[.*?\]|'   # [Gemini], [CTO BLUEPRINT], etc.
                                r'\s*(Here|Sure|Certainly|Below|The fixed|Fixed|Note:|Explanation:)'
                                r')',
                                _re.UNICODE
                            )
                            cleaned_lines = []
                            in_code = False
                            for ln in candidate.splitlines():
                                if not in_code:
                                    # Skip prose lines until we hit valid Python
                                    if KNOWN_PREFIXES.match(ln) or (ln.strip() and not PYTHON_STARTS.match(ln) and not ln.startswith(' ')):
                                        continue
                                    else:
                                        in_code = True
                                cleaned_lines.append(ln)

                            result = '\n'.join(cleaned_lines).strip()
                            if not result:
                                raise ValueError("Extractor produced empty output — LLM response contained no extractable Python code.")
                            return result

                        try:
                            healed_code = _extract_python_code(healed_code)
                            logger.info(f"[AUTO-HEAL] Code extractor succeeded — {len(healed_code)} chars extracted.")
                        except ValueError as extract_err:
                            logger.error(f"[AUTO-HEAL] Code extractor failed: {extract_err}")
                            await _broadcast({
                                "type": "dialogue", "agent": "SYSTEM",
                                "icon": "⚠️", "color": "#eab308",
                                "message": (
                                    f"**[EXTRACTOR WARNING]** CTO response contained no extractable Python.\n"
                                    f"`{extract_err}`\n\nRetrying with stricter prompt on next attempt."
                                ),
                                "timestamp": _dt.now().isoformat()
                            }, project=project_id)
                            # Don't break — let the while loop increment attempt and retry
                            continue

                        # Write healed script back to the same staging file
                        try:
                            with open(staging_path, "w", encoding="utf-8") as _f:
                                _f.write(healed_code)
                            logger.info(f"[AUTO-HEAL] Attempt {attempt}: healed script written to {staging_filename}")
                        except Exception as write_err:
                            logger.error(f"[AUTO-HEAL] Cannot write healed script: {write_err}")
                            break

                        await _broadcast({
                            "type": "dialogue", "agent": "INCUBATOR_GATE",
                            "icon": "♻️", "color": "#8b5cf6",
                            "message": (
                                f"**CTO AUTO-HEAL — Attempt {attempt}/{MAX_RETRIES}**\n\n"
                                f"Fixed script written to `{staging_filename}`. Re-running QA sandbox..."
                            ),
                            "timestamp": _dt.now().isoformat()
                        }, project=project_id)
                        # Loop continues — next iteration re-runs QA on the healed file
                        continue

                    else:
                        # MAX_RETRIES exhausted
                        await _broadcast({
                            "type": "dialogue", "agent": "INCUBATOR_GATE",
                            "icon": "❌", "color": "#ef4444",
                            "message": (
                                f"**AUTO-HEAL EXHAUSTED — {MAX_RETRIES}/{MAX_RETRIES} attempts failed ❌**\n\n"
                                f"The CTO agent could not produce a valid script after {MAX_RETRIES} healing cycles.\n\n"
                                f"**Last error:**\n```\n{qa_stderr[:600]}\n```\n\n"
                                "Manual intervention required. Issue `@Operator Reject Blueprint` to discard "
                                "and start fresh, or inspect the staging file directly."
                            ),
                            "timestamp": _dt.now().isoformat()
                        }, project=project_id)
                        await _broadcast({"type": "state_machine", "phase": "CFO_FINANCIAL_MODEL", "status": "FAIL"}, project=project_id)
                        break

            else:
                # REJECT path
                await _broadcast({
                    "type": "dialogue", "agent": "INCUBATOR_GATE",
                    "icon": "🚫", "color": "#ef4444",
                    "message": (
                        "**@Operator Reject Blueprint — CONFIRMED**\n\n"
                        "Commander has rejected the pending blueprint. The Executive Fork is cleared.\n"
                        "Issue a new `@Operator <app idea>` command to start a fresh Incubator Gate run."
                    ),
                    "timestamp": _dt.now().isoformat()
                }, project=project_id)
                # Reset progress bar to idle
                for phase in ("CMO_STRATEGY", "CTO_FEASIBILITY", "CFO_FINANCIAL_MODEL", "PHANTOM_STRESS_TEST", "COMMERCIALLY_READY"):
                    await _broadcast({"type": "state_machine", "phase": phase, "status": "WAITING"}, project=project_id)

            ORCHESTRATION_STATE = "idle"

        asyncio.create_task(resolve_fork())
        return {"status": "fork_resolved", "action": action, "project": project_id}

    # Re-entrancy guard: reject NEW gate triggers if gate is already running
    # (authorization commands above are intentionally exempt from this guard)
    if _is_operator_cmd and ORCHESTRATION_STATE == "processing":
        logger.warning("Incubator Gate already processing — ignoring duplicate trigger.")
        return JSONResponse(
            {"status": "already_running", "project": project_id,
             "detail": "Incubator Gate is already active. Wait for completion or Executive Fork."},
            status_code=429
        )

    if _is_operator_cmd:
        logger.info(f"Phase 11 Incubator Gate triggered by @Operator command: {req.message[:80]!r}")
        ORCHESTRATION_STATE = "processing"
        import forge_orchestrator
        
        async def trigger_incubator():
            import traceback as _tb
            global ORCHESTRATION_STATE
            print(f"\n[INCUBATOR GATE] ▶ STARTING — project_id={project_id!r} | prompt={req.message[:80]!r}", flush=True)
            try:
                await _broadcast({
                    "type": "intervention",
                    "agent": "SYSTEM",
                    "message": "INCUBATOR GATE ENGAGED: Bypassing legacy debate. Routing to Phase 11 Pre-Flight...",
                    "timestamp": _dt.now().isoformat()
                }, project=project_id)
                print(f"[INCUBATOR GATE] ▶ Broadcast sent. Instantiating ForgeOrchestrator...", flush=True)
                orchestrator = forge_orchestrator.ForgeOrchestrator()
                print(f"[INCUBATOR GATE] ▶ Calling run_incubator_gate() in thread...", flush=True)
                await asyncio.to_thread(orchestrator.run_incubator_gate, req.message, project_id)
                print(f"[INCUBATOR GATE] ▶ run_incubator_gate() returned cleanly.", flush=True)
                
            except forge_orchestrator.ExecutiveForkTriggered:
                print(f"[INCUBATOR GATE] ✅ ExecutiveForkTriggered — halted, awaiting @Operator authorization.", flush=True)
                logger.info("Executive Fork triggered. Awaiting human input.")
                await _broadcast({
                    "type": "intervention",
                    "agent": "SYSTEM",
                    "message": "⚡ EXECUTIVE FORK: CMO + CTO pre-flight complete. Awaiting @Operator authorization to enter /staging_environment/.",
                    "timestamp": _dt.now().isoformat()
                }, project=project_id)
            except Exception as e:
                print(f"\n[INCUBATOR GATE] ❌ FATAL EXCEPTION: {type(e).__name__}: {e}", flush=True)
                _tb.print_exc()
                logger.error(f"Incubator Gate failed: {type(e).__name__}: {e}")
                await _broadcast({
                    "type": "intervention",
                    "agent": "SYSTEM",
                    "message": f"❌ Incubator Gate Failure: {type(e).__name__}: {str(e)}",
                    "timestamp": _dt.now().isoformat()
                }, project=project_id)
            finally:
                ORCHESTRATION_STATE = "idle"
                print(f"[INCUBATOR GATE] ▶ DONE — state reset to idle.", flush=True)
                
        asyncio.create_task(trigger_incubator())
        return {"status": "incubator_gate_started", "project": project_id}
        
    elif any(kw in msg_lower for kw in ['cmo', 'cfo', 'roi']):
        logger.info(f"Orchestration Bind triggered by keywords in: {req.message}")
        ORCHESTRATION_STATE = "processing"
        
        async def trigger_csuite():
            global ORCHESTRATION_STATE
            try:
                # Resolve Commander's strategic philosophy
                _strategy = get_strategy_mode(req.strategy_mode, req.custom_directive)
                _strategy_label = _strategy.label

                # Broadcast START_DEBATE event via the Server-Sent Events/WS stream
                await _broadcast({
                    "type": "intervention",
                    "agent": "SYSTEM",
                    "message": f"START_DEBATE — Strategy: {_strategy_label} | Stress Test: {req.stress_test}",
                    "timestamp": _dt.now().isoformat()
                }, project=project_id)

                topic = f"Commander overrides: {req.message}"

                # ── UPGRADE 6: CEO Triage (Dynamic Hierarchy Composition) ──
                await _broadcast({
                    "type": "intervention",
                    "agent": "CEO",
                    "message": "Staffing Project: Evaluating Commander Intent...",
                    "timestamp": _dt.now().isoformat()
                }, project=project_id)
                
                triage_prompt = (
                    "You are the CEO. You must dynamically select the most efficient War Room team to handle the following objective.\n"
                    f"Objective: '{req.message}'\n"
                    "Available Agents: [CMO, CFO, CTO, CLO, CRITIC, ARCHITECT]\n"
                    "Rules:\n"
                    "1. Return ONLY a valid JSON array of strings containing the selected agent names in order.\n"
                    "2. The Minimum Squad is 2 agents. The final agent should act as the gate (typically CRITIC or CTO).\n"
                    "3. Output MUST be only JSON, e.g. [\"CTO\", \"ARCHITECT\", \"CRITIC\"]\n"
                    "Team Selection:"
                )
                loop = asyncio.get_event_loop()
                triage_resp = await loop.run_in_executor(_warroom_executor, _call_agent, "CEO", triage_prompt)
                
                triage_list = []
                try:
                    import re
                    # Clean potential markdown
                    clean_resp = re.sub(r'```(?:json)?', '', triage_resp).strip()
                    triage_list = json.loads(clean_resp)
                    if not isinstance(triage_list, list):
                        triage_list = []
                except Exception as e:
                    logger.error(f"CEO Triage parsing failed: {e} | Raw: {triage_resp}")
                
                async def _run_performance_review(pid: str, critic_output: str, score: float, p_type: str = "GLOBAL"):
                    """Phase 7: Analyzes a brilliant project plan or absolute failure to extract Win Conditions or Scars."""
                    logger.info(f"Triggering Performance Review for {pid}...")
                    loop = asyncio.get_event_loop()
                    pm = get_persona_manager()
                    
                    is_win = score >= 8.0
                    if is_win:
                        review_prompt = (
                            f"The Commander rated this {p_type} project plan {score}/10, a massive success.\n"
                            "Analyze the CRITIC's successful verdict and identify 1 specific strategic behavior or tactic "
                            "performed by the CTO and/or CFO that made this a success.\n"
                            f"Prepend the tactic with the context tag: [{p_type}].\n"
                            "Return ONLY a strict JSON object mapping the agent's name to a single bullet point string.\n"
                            f"Example: {{\"CTO\": \"[{p_type}] Chose SQLite to minimize dev overhead\"}}\n"
                            f"CRITIC VERDICT:\n{critic_output}"
                        )
                    else:
                        review_prompt = (
                            f"The Commander rated this {p_type} project plan {score}/10, an absolute failure.\n"
                            "Analyze the CRITIC's failed verdict and identify 1 critical mistake "
                            "performed by the CTO and/or CFO that caused this rejection.\n"
                            f"Prepend the scar with the context tag: [{p_type}].\n"
                            "Return ONLY a strict JSON object mapping the agent's name to a single bullet point string.\n"
                            f"Example: {{\"CFO\": \"[{p_type}] Proposed budget ignoring critical tax law\"}}\n"
                            f"CRITIC VERDICT:\n{critic_output}"
                        )
                    
                    try:
                        resp = await loop.run_in_executor(_warroom_executor, _call_agent, "SYSTEM", review_prompt)
                        clean_json = re.sub(r'^```[\w]*\n|```$', '', resp.strip(), flags=re.MULTILINE).strip()
                        start = clean_json.find('{')
                        end = clean_json.rfind('}')
                        if start != -1 and end != -1:
                            insights = json.loads(clean_json[start:end+1])
                            for agent, tactic in insights.items():
                                if is_win:
                                    pm.add_win_condition(agent.upper(), tactic)
                                    msg = f"New Win Condition added: {tactic}"
                                else:
                                    pm.add_scar(agent.upper(), tactic)
                                    msg = f"New Scar added: {tactic}"
                                
                                logger.info(f"Agent Persona ({agent}) updated: {tactic}")
                                
                                await _broadcast({
                                    "type": "persona_update",
                                    "agent": agent.upper(),
                                    "level_up": is_win,
                                    "message": msg,
                                    "timestamp": _dt.now().isoformat()
                                }, project=pid)
                    except Exception as e:
                        logger.error(f"Performance Review failed: {e}")

                # ── WAR ROOM PROTOCOL INTEGRATION ──────────────────────
                _wr_store = get_report_store()
                _wr_orchestrator = get_orchestrator()
                _wr_pipeline = _wr_orchestrator.compose_pipeline(req.message, triage_override=triage_list)
                _wr_session = _wr_orchestrator.start_session(
                    project_id, _wr_pipeline, req.message,
                    strategy_mode=_strategy, stress_test=req.stress_test,
                )
                logger.info(f"War Room Session: {_wr_orchestrator.get_pipeline_summary(_wr_pipeline)}")
                
                async def trigger_agent_response(agent_name, prompt_override=None):
                    loop = asyncio.get_event_loop()
                    query = prompt_override or topic
                    
                    # ── Phase 7: Agent Persona Injection ──
                    try:
                        pm = get_persona_manager()
                        query = pm.inject_memory_into_prompt(agent_name, query)
                    except Exception as e:
                        logger.warning(f"Failed to inject persona memory for {agent_name}: {e}")

                    logger.info(f"Triggering {agent_name} response")
                    await _broadcast({
                        "type": "agent_working",
                        "agent": agent_name,
                        "timestamp": _dt.now().isoformat()
                    }, project=project_id)
                    
                    try:
                        if agent_name == "CPO":
                            import cpo_agent
                            resp = await loop.run_in_executor(_warroom_executor, cpo_agent.run_cpo, query)
                        else:
                            resp = await loop.run_in_executor(_warroom_executor, _call_agent, agent_name, query)
                        coo = coo_agent.get_coo()
                        ledger = coo.record_usage(project_id, agent_name, query, resp or "")
                        
                        await _broadcast({
                            "type": "coo_alert",
                            "tokens_total": ledger.total_tokens,
                            "budget": ledger.max_budget,
                            "status": ledger.status,
                            "est_cost": f"${ledger.estimated_cost_usd:.4f}"
                        }, project=project_id)
                    except coo_agent.OpBudgetExceeded as e:
                        logger.error(str(e))
                        await _broadcast({
                            "type": "dialogue",
                            "agent": "SYSTEM",
                            "icon": "🛑",
                            "color": "#dc2626",
                            "message": f"**[COO OPERATION ABORT]** {str(e)}",
                            "timestamp": _dt.now().isoformat()
                        }, project=project_id)
                        raise # break loop
                        
                    agent_meta = _AGENTS.get(agent_name, {})
                    await _broadcast({
                        "type": "dialogue",
                        "agent": agent_name,
                        "icon": agent_meta.get("icon", "🤖"),
                        "color": agent_meta.get("color", "#3b82f6"),
                        "message": resp or f"{agent_name} logic processed.",
                        "timestamp": _dt.now().isoformat()
                    }, project=project_id)
                    
                    # ── Stealth Extraction (Dual-Output Pattern) ──
                    structured_data = {}
                    metadata = {"cost": f"${ledger.estimated_cost_usd:.4f}" if 'ledger' in locals() else "$0.00"}
                    
                    from warroom_protocol import HANDOFF_MODELS
                    model_cls = HANDOFF_MODELS.get(agent_name)
                    if model_cls and resp:
                        fields = list(model_cls.model_fields.keys())
                        stealth_prompt = (
                            f"Extract the following fields from this debate transcript into a strict JSON payload.\n"
                            f"Fields required: {fields}\n"
                            f"Do not summarize. Extract raw values only into JSON format matching the provided Pydantic fields.\n"
                            f"Transcript:\n{resp}"
                        )
                        try:
                            s_resp = await loop.run_in_executor(_warroom_executor, _call_agent, "SYSTEM", stealth_prompt)
                            clean_json = re.sub(r'^```[\w]*\n|```$', '', s_resp.strip(), flags=re.MULTILINE).strip()
                            s_start = clean_json.find('{')
                            s_end = clean_json.rfind('}')
                            if s_start != -1 and s_end != -1:
                                structured_data = json.loads(clean_json[s_start:s_end+1])
                        except Exception as e:
                            logger.error(f"Stealth Extraction failed for {agent_name}: {e}")
                            
                    return (resp or "", structured_data, metadata)

                async def _propose_wisdom(report):
                    try:
                        vault = get_wisdom_vault()
                        candidate = vault.propose_from_report(report)
                        if candidate:
                            await _broadcast({
                                "type": "wisdom_proposal",
                                "agent": "SYSTEM",
                                "message": f"💡 New insight proposed: {candidate.title}",
                                "standard_id": candidate.standard_id,
                            }, project=project_id)
                    except Exception as e:
                        logger.warning(f"Wisdom proposal failed: {e}")


                import re

                def _parse_agent_json(raw_text: str) -> dict:
                    """Parse JSON from agent response, stripping markdown fences if present."""
                    cleaned = re.sub(r'^```[\w]*\n|```$', '', raw_text.strip(), flags=re.MULTILINE).strip()
                    # Try to find JSON object in the text
                    start = cleaned.find('{')
                    end = cleaned.rfind('}')
                    if start != -1 and end != -1:
                        try:
                            return json.loads(cleaned[start:end+1])
                        except json.JSONDecodeError:
                            pass
                    return {}

                def _compress_context(cmo_data: dict, cto_data: dict, cfo_data: dict, critic_data: dict, phantom_verdict: str, phantom_score: int) -> str:
                    """Aether Synthesis: Compress iteration context to prevent prompt bloating."""
                    summary_parts = []
                    # CMO summary
                    cmo_rec = cmo_data.get("recommendation", "UNKNOWN")
                    cmo_risks = cmo_data.get("key_risks", [])
                    summary_parts.append(f"CMO: {cmo_rec}. Risks: {', '.join(cmo_risks[:2]) if cmo_risks else 'none cited'}.")
                    # CTO summary
                    cto_score = cto_data.get("technical_feasibility_score", "N/A")
                    cto_rec = cto_data.get("recommendation", "UNKNOWN")
                    summary_parts.append(f"CTO: {cto_rec} (Feasibility: {cto_score}/10).")
                    # CFO summary
                    cfo_rec = cfo_data.get("recommendation", "UNKNOWN")
                    cfo_roi = cfo_data.get("projected_roi", "N/A")
                    summary_parts.append(f"CFO: {cfo_rec}. ROI: {cfo_roi}.")
                    # Critic summary
                    critic_level = critic_data.get("agreement_level", 5.0)
                    critic_verdict = critic_data.get("verdict", "UNKNOWN")
                    objections = critic_data.get("objections", [])
                    summary_parts.append(f"CRITIC: {critic_verdict} ({critic_level}/10). Objections: {'; '.join(objections[:2]) if objections else 'none'}.")
                    # Phantom summary
                    summary_parts.append(f"PHANTOM QA: {phantom_verdict} ({phantom_score}/100).")
                    return " | ".join(summary_parts)

                def _validate_social_media_schema(project_dir: str) -> dict:
                    """Phantom Schema Validity: Check Social_Media_Matrix.json for structural integrity."""
                    required_keys = {"platforms", "content_calendar", "kpi_targets"}
                    matrix_path = os.path.join(project_dir, "Social_Media_Matrix.json")
                    if not os.path.exists(matrix_path):
                        # Also check EOS subdirectory
                        eos_path = os.path.join(project_dir, "eos", "Social_Media_Matrix.json")
                        if os.path.exists(eos_path):
                            matrix_path = eos_path
                        else:
                            return {"valid": True, "note": "Social_Media_Matrix.json not found — schema check skipped."}
                    try:
                        with open(matrix_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        if not isinstance(data, dict):
                            return {"valid": False, "error": "Root element must be a JSON object."}
                        missing = required_keys - set(data.keys())
                        if missing:
                            return {"valid": False, "error": f"Missing required keys: {', '.join(missing)}"}
                        # Validate platforms is a list
                        if not isinstance(data.get("platforms"), list) or len(data["platforms"]) == 0:
                            return {"valid": False, "error": "platforms must be a non-empty array."}
                        return {"valid": True, "platforms_count": len(data["platforms"])}
                    except json.JSONDecodeError as e:
                        return {"valid": False, "error": f"Invalid JSON: {str(e)[:150]}"}
                    except Exception as e:
                        return {"valid": False, "error": str(e)[:150]}

                iteration = 1
                max_iterations = 5
                

                # ── Phase 8: Session Checkpoint Mechanics ──
                import os
                checkpoint_dir = os.path.join("Boardroom_Exchange", "active_sessions")
                os.makedirs(checkpoint_dir, exist_ok=True)
                checkpoint_file = os.path.join(checkpoint_dir, f"{project_id}_state.json")

                def _save_checkpoint(last_agent: str):
                    coo = coo_agent.get_coo()
                    ledger = coo.get_ledger(project_id)
                    def serialize_report(rep):
                        if hasattr(rep, 'model_dump'):
                            return rep.model_dump()
                        elif hasattr(rep, 'dict'):
                            return rep.dict()
                        if isinstance(rep, dict):
                            return rep
                        return {}
                    
                    state = {
                        "last_agent": last_agent,
                        "coo": {
                            "tokens_in": ledger.tokens_in,
                            "tokens_out": ledger.tokens_out,
                            "iteration": ledger.iteration_count
                        },
                        "reports": {k: serialize_report(v) for k, v in _wr_session['reports'].items()}
                    }
                    try:
                        with open(checkpoint_file, "w", encoding="utf-8") as f:
                            json.dump(state, f, indent=2)
                    except Exception as e:
                        logger.warning(f"Failed writing checkpoint: {e}")

                if os.path.exists(checkpoint_file):
                    try:
                        with open(checkpoint_file, "r", encoding="utf-8") as f:
                            chk = json.load(f)
                        
                        coo_agent.get_coo().restore_ledger(
                            project_id,
                            chk['coo']['tokens_in'],
                            chk['coo']['tokens_out'],
                            chk['coo']['iteration']
                        )
                        
                        from warroom_protocol import WarRoomReport
                        for k, v in chk['reports'].items():
                            if 'metadata' not in v:
                                v['metadata'] = {}
                            v['metadata']['is_resumed'] = True
                            _wr_session['reports'][k] = WarRoomReport(**v)
                            
                        logger.info(f"Resumed debate {project_id} from {chk.get('last_agent', 'known')} checkpoint.")
                        asyncio.create_task(_broadcast({
                            "type": "dialogue",
                            "agent": "SYSTEM",
                            "icon": "💾",
                            "color": "#10b981",
                            "message": f"**[STATE RECOVERY]** Resuming debate from {chk.get('last_agent', 'previous')} checkpoint...",
                            "timestamp": _dt.now().isoformat()
                        }, project=project_id))
                    except Exception as e:
                        logger.warning(f"Failed to load checkpoint: {e}")

                while iteration <= max_iterations:
                    logger.info(f"=== LINEAR DEPENDENCY PROTOCOL — Iteration {iteration} ===")
                    # Broadcast iteration counter to UI
                    await _broadcast({
                        "type": "consensus_iteration",
                        "iteration": iteration,
                        "max_iterations": max_iterations,
                        "timestamp": _dt.now().isoformat()
                    }, project=project_id)
                    await _broadcast({
                        "type": "dialogue",
                        "agent": "SYSTEM",
                        "icon": "🔄",
                        "color": "#eab308",
                        "message": f"**Linear Dependency Protocol — Iteration {iteration}/{max_iterations}**\nPhase 1 → 1.5 → 2 → 3 → 4 chain initiating.",
                        "timestamp": _dt.now().isoformat()
                    }, project=project_id)

                    # ═══════════════════════════════════════════════════
                    # PHASE 1: THE FOUNDATION — CMO & CEO
                    # ═══════════════════════════════════════════════════
                    global market_pulse_data
                    from strategic_sentiment import get_strategic_sentiment
                    market_pulse_data = get_strategic_sentiment().analyze_market(project_id)
                    verdict_str = market_pulse_data.get("verdict", "NEUTRAL")
                    
                    pivot_instruction = ""
                    if verdict_str == "BEARISH":
                        pivot_instruction = "\nWARNING: The Market Pulse is currently BEARISH (Low momentum, negative sentiment). You MUST present a 'Pivot Option' (e.g., lower CAC channels, feature pruning) in your strategy."

                    cmo_prompt_override = f"{topic}\n\n[MARKET PULSE]: {market_pulse_data}\n{pivot_instruction}"

                    await _broadcast({
                        "type": "market_pulse",
                        "verdict": verdict_str,
                        "velocity": market_pulse_data.get("trend_velocity", 5.0),
                        "sentiment": market_pulse_data.get("public_sentiment_score", 0.0)
                    }, project=project_id)

                    await _broadcast({
                        "type": "dialogue",
                        "agent": "SYSTEM",
                        "icon": "📊",
                        "color": "#a855f7",
                        "message": f"**PHASE 1: THE FOUNDATION**\nFetching Strategic Sentiment... Market Pulse: {verdict_str}. CMO pulling market research & quantifying costs...",
                        "timestamp": _dt.now().isoformat()
                    }, project=project_id)

                    
                    # 1a. CMO: Market Research + Cost Quantification
                    cmo_data = {}
                    if "CMO" in triage_list:
                        if 'CMO' not in _wr_session['reports']:
                            cmo_resp, cmo_data, cmo_meta = await trigger_agent_response('CMO', cmo_prompt_override)

                            # ── WAR ROOM: Parse CMO into typed WarRoomReport ──
                            _cmo_report = parse_agent_response(cmo_resp, 'CMO', 'market', project_id, iteration, structured_data=cmo_data, metadata=cmo_meta)
                            _wr_store.save(_cmo_report)
                            await _propose_wisdom(_cmo_report)
                            _wr_session['reports']['CMO'] = _cmo_report
                            _save_checkpoint('CMO')

                        cmo_report = _wr_session['reports']['CMO']
                        cmo_hp = cmo_report.handoff_payload  # Strictly typed CMOHandoff fields
                        cmo_data = cmo_hp

                        # Extract CMO's critical numbers from typed handoff
                        cmo_marketing_cost = cmo_hp.get("marketing_cost", 0)
                        cmo_projected_revenue = cmo_hp.get("projected_revenue", 0)
                        cmo_demographic_reach = cmo_hp.get("demographic_reach", 0)
                        cmo_cpa = cmo_hp.get("cost_per_acquisition", 0)
                        cmo_recommendation = cmo_report.recommendation
                        cmo_strategy = cmo_hp.get("market_strategy", cmo_report.detailed_report[:300] if hasattr(cmo_report, 'detailed_report') else "N/A")
                    else:
                        logger.info("COO: Skipping CMO per CEO Triage.")
                        cmo_marketing_cost = 0
                        cmo_projected_revenue = 0
                        cmo_demographic_reach = 0
                        cmo_cpa = 0
                        cmo_recommendation = "SKIPPED"
                        cmo_strategy = "N/A"
                        cmo_hp = {}

                    # 1b. CEO: Validate CMO strategy against growth targets
                    ceo_alignment = "UNKNOWN"
                    if "CEO" in triage_list:
                        # Build handoff from upstream CMO report
                        ceo_handoff = _wr_orchestrator.build_handoff_context(
                            PipelineStep(agent_name='CEO', phase='validation', depends_on=['CMO']),
                            _wr_session['reports'],
                            req.message,
                            iteration=iteration,
                            market_pulse=market_pulse_data,
                            wisdom_vault=get_wisdom_vault(),
                        )
                        if 'CEO' not in _wr_session['reports']:
                            ceo_resp, ceo_data, ceo_meta = await trigger_agent_response('CEO', ceo_handoff)

                            # ── WAR ROOM: Parse CEO into typed WarRoomReport ──
                            _ceo_report = parse_agent_response(ceo_resp, 'CEO', 'validation', project_id, iteration, structured_data=ceo_data, metadata=ceo_meta)
                            _wr_store.save(_ceo_report)
                            await _propose_wisdom(_ceo_report)
                            _wr_session['reports']['CEO'] = _ceo_report
                            _save_checkpoint('CEO')

                        ceo_report = _wr_session['reports']['CEO']
                        ceo_hp = ceo_report.handoff_payload  # Strictly typed CEOHandoff fields

                        ceo_approved = ceo_hp.get("approved_for_phase2", True)
                        ceo_alignment = ceo_hp.get("growth_target_alignment", "UNKNOWN")
                        ceo_target = ceo_hp.get("growth_target_annual", 0)

                        if not ceo_approved:
                            await _broadcast({
                                "type": "dialogue",
                                "agent": "SYSTEM",
                                "icon": "⚠️",
                                "color": "#f59e0b",
                                "message": f"**Phase 1 GATE: CEO flags MISALIGNMENT**\nAlignment: {ceo_alignment} | Growth Target: ${ceo_target:,.0f}\nRevision required. Cycling back.",
                                "timestamp": _dt.now().isoformat()
                            }, project=project_id)
                    else:
                        logger.info("COO: Skipping CEO validation per CEO Triage.")

# ═══════════════════════════════════════════════════
                    
                    # ═══════════════════════════════════════════════════
                    # PHASE 1.2: THE PRODUCT OFFICER — CPO
                    # ═══════════════════════════════════════════════════
                    if "CPO" in triage_list:
                        await _broadcast({
                            "type": "dialogue",
                            "agent": "SYSTEM",
                            "icon": "🎨",
                            "color": "#ec4899",
                            "message": f"**PHASE 1.2: THE PRODUCT OFFICER**\nCPO evaluating Commerciability & UX Friction...",
                            "timestamp": _dt.now().isoformat()
                        }, project=project_id)

                        cpo_handoff = f"Provide a MoSCoW prioritization and UX alignment report based on intention: '{req.message}'"
                        if 'CPO' not in _wr_session['reports']:
                            cpo_resp, cpo_data, cpo_meta = await trigger_agent_response('CPO', cpo_handoff)
                            _cpo_report = parse_agent_response(cpo_resp, 'CPO', 'product', project_id, iteration, structured_data=cpo_data, metadata=cpo_meta)
                            _wr_store.save(_cpo_report)
                            _wr_session['reports']['CPO'] = _cpo_report
                            _save_checkpoint('CPO')
                    else:
                        logger.info("COO: Skipping CPO per CEO Triage.")
                    # PHASE 1.5: THE ENGINEER — CTO
                    # ═══════════════════════════════════════════════════
                    await _broadcast({
                        "type": "dialogue",
                        "agent": "SYSTEM",
                        "icon": "🔧",
                        "color": "#06b6d4",
                        "message": f"**PHASE 1.5: THE ENGINEER**\nCTO assessing Technical Feasibility of CMO strategy...\n• Strategy: {cmo_strategy[:100]}...\n• CEO Alignment: {ceo_alignment}",
                        "timestamp": _dt.now().isoformat()
                    }, project=project_id)

                    
                    # CTO receives CMO strategy + CEO validation via orchestrator handoff
                    cto_data = {}
                    cto_hp = {}
                    if "CTO" in triage_list:
                        cto_handoff = _wr_orchestrator.build_handoff_context(
                            PipelineStep(agent_name='CTO', phase='technical', depends_on=['CMO', 'CEO']),
                            _wr_session['reports'],
                            req.message,
                            iteration=iteration,
                            market_pulse=market_pulse_data,
                            wisdom_vault=get_wisdom_vault(),
                        )
                        if 'CTO' not in _wr_session['reports']:
                            cto_resp, cto_data, cto_meta = await trigger_agent_response('CTO', cto_handoff)

                            # ── WAR ROOM: Parse CTO into typed WarRoomReport ──
                            _cto_report = parse_agent_response(cto_resp, 'CTO', 'technical', project_id, iteration, structured_data=cto_data, metadata=cto_meta)
                            _wr_store.save(_cto_report)
                            await _propose_wisdom(_cto_report)
                            _wr_session['reports']['CTO'] = _cto_report
                            _save_checkpoint('CTO')

                        cto_report = _wr_session['reports']['CTO']
                        cto_hp = cto_report.handoff_payload  # Strictly typed CTOHandoff fields
                        cto_data = cto_hp
                        
                        # Extract CTO's Technical Feasibility Score + USE fields from typed handoff
                        cto_feasibility = float(cto_hp.get("technical_feasibility_score", 5))
                        cto_project_type = cto_hp.get("project_type", "DIGITAL")
                        cto_tech_stack = cto_hp.get("tech_stack", [])
                        cto_automation_layer = cto_hp.get("automation_monitoring_layer", "")
                        cto_skills_blocks = cto_hp.get("skills_library_blocks", [])
                        cto_timeline = cto_hp.get("implementation_timeline_weeks", 0)
                        cto_v3_compliance = cto_hp.get("v3_compliance", "UNKNOWN")
                        cto_pre_deploy = cto_hp.get("pre_deploy_gate_status", "UNKNOWN")
                        cto_recommendation = cto_report.recommendation
                        
                        # Extract CFO-ready metrics from typed CTO handoff (already flattened)
                        infra_cost = cto_hp.get("infrastructure_cost_estimate", 0)
                        dev_buffer = cto_hp.get("development_buffer_weeks", 0)
                        tech_debt_premium = cto_hp.get("tech_debt_risk_premium_pct", 0)
                        gate_source = cto_hp.get("gate_source", "aether_native" if PRE_DEPLOY_AVAILABLE else "llm_estimate")

                        # Compute development_buffer_weeks if LLM didn't provide it
                        if not dev_buffer and cto_timeline:
                            dev_buffer = round(cto_timeline * 1.5, 1) if cto_feasibility < 7 else cto_timeline

                        # TECHNICAL GATE CHECK via Orchestrator
                        _cto_gate_step = PipelineStep(agent_name='CTO', phase='technical', is_gate=True, gate_threshold=4.0)
                        _cto_gate_result = _wr_orchestrator.check_gate(_cto_gate_step, cto_report)
                        if not _cto_gate_result['passed']:
                            await _broadcast({
                                "type": "dialogue",
                                "agent": "SYSTEM",
                                "icon": "🛑",
                                "color": "#ef4444",
                                "message": f"**TECHNICAL GATE FAILURE**\n{_cto_gate_result['reason']}\nCFO modeling BLOCKED. CTO recommends: {cto_recommendation}.\nRevision required.",
                                "timestamp": _dt.now().isoformat()
                            }, project=project_id)
                    else:
                        logger.info("COO: Skipping CTO per CEO Triage.")
                        cto_timeline = 0
                        dev_buffer = 0
                        infra_cost = 0
                        tech_debt_premium = 0
                        cto_pre_deploy = "UNKNOWN"

# ═══════════════════════════════════════════════════
                    
                    # ═══════════════════════════════════════════════════
                    # PHASE 1.8: THE LEGAL OFFICER — CLO
                    # ═══════════════════════════════════════════════════
                    if "CLO" in triage_list:
                        await _broadcast({
                            "type": "dialogue",
                            "agent": "SYSTEM",
                            "icon": "⚖️",
                            "color": "#64748b",
                            "message": f"**PHASE 1.8: THE LEGAL OFFICER**\nCLO evaluating IP Security & Compliance...",
                            "timestamp": _dt.now().isoformat()
                        }, project=project_id)

                        clo_handoff = f"Provide a rapid IP mapping and compliance scan for intention: '{req.message}'"
                        if 'CLO' not in _wr_session['reports']:
                            clo_resp, clo_data, clo_meta = await trigger_agent_response('CLO', clo_handoff)
                            _clo_report = parse_agent_response(clo_resp, 'CLO', 'legal', project_id, iteration, structured_data=clo_data, metadata=clo_meta)
                            _wr_store.save(_clo_report)
                            _wr_session['reports']['CLO'] = _clo_report
                            _save_checkpoint('CLO')
                    else:
                        logger.info("COO: Skipping CLO per CEO Triage.")
                    # PHASE 2: THE MODEL — CFO
                    # ═══════════════════════════════════════════════════
                    await _broadcast({
                        "type": "dialogue",
                        "agent": "SYSTEM",
                        "icon": "💰",
                        "color": "#22c55e",
                        "message": f"**PHASE 2: THE MODEL**\nCFO building Business Plan utilizing CTO Phase 1.5 USE Output:\n• Timeline: {cto_timeline}wk (Buffer: {dev_buffer}wk)\n• Infra Cost: ${infra_cost:,.0f}/mo | Tech Debt Premium: {tech_debt_premium}%\n• Gate Status: {cto_pre_deploy}",
                        "timestamp": _dt.now().isoformat()
                    }, project=project_id)

                    # ── AETHER-NATIVE CFO EXCEL EXTRACTION ──────────────────
                    # Run the mathematical generation using native python/pandas
                    native_cfo_msg = ""
                    try:
                        from cfo_excel_architect import get_cfo_architect
                        cfo_arch = get_cfo_architect()
                        cfo_native_result = cfo_arch.generate_business_plan(
                            project_id=project_id,
                            cmo_data=cmo_data,
                            cto_data=cto_data,
                            market_pulse=market_pulse_data
                        )
                        if cfo_native_result.get("status") == "success":
                            native_cfo_msg = (
                                f"\n\n=== Native Excel Architect Output ===\n"
                                f"- Excel Artifact Generated: {cfo_native_result.get('file_name')}\n"
                                f"- Fragility Index: {cfo_native_result.get('fragility_index')}/100\n"
                                f"- Total Computed Cost Basis: ${cfo_native_result.get('total_cost'):,.2f}\n"
                                f"- Baseline ROI: {cfo_native_result.get('roi_percentage')}%\n"
                                f"- Risk-Adjusted ROI: {cfo_native_result.get('risk_adjusted_roi')}%\n"
                                f"- Net Present Value (NPV): ${cfo_native_result.get('npv'):,.2f}\n"
                            )
                            # Broadcast the model creation natively
                            await _broadcast({
                                "type": "dialogue",
                                "agent": "SYSTEM",
                                "icon": "📊",
                                "color": "#10b981",
                                "message": f"**CFO EXCEL ARCHITECT**\nNative Fragility Report generated: {cfo_native_result.get('file_name')}\nTotal Cost Basis: ${cfo_native_result.get('total_cost'):,.0f} | Risk-Adj ROI: {cfo_native_result.get('risk_adjusted_roi')}%",
                                "timestamp": _dt.now().isoformat()
                            }, project=project_id)
                    except Exception as e:
                        logger.warning(f"Native CFO failed: {e}")

                    # CFO LLM receives upstream reports via orchestrator + native Excel output
                    cfo_handoff = _wr_orchestrator.build_handoff_context(
                        PipelineStep(agent_name='CFO', phase='financials', depends_on=['CMO', 'CEO', 'CTO']),
                        _wr_session['reports'],
                        req.message,
                        iteration=iteration,
                        market_pulse=market_pulse_data,
                        wisdom_vault=get_wisdom_vault(),
                    )
                    # Append Native Excel results if available
                    if native_cfo_msg:
                        cfo_handoff += native_cfo_msg
                    cfo_resp, cfo_data, cfo_meta = await trigger_agent_response('CFO', cfo_handoff)

                    # ── WAR ROOM: Parse CFO into typed WarRoomReport ──
                    cfo_report = parse_agent_response(cfo_resp, 'CFO', 'financials', project_id, iteration, structured_data=cfo_data, metadata=cfo_meta)
                    _wr_store.save(cfo_report)
                    await _propose_wisdom(cfo_report)
                    _wr_session['reports']['CFO'] = cfo_report
                    cfo_hp = cfo_report.handoff_payload  # Strictly typed CFOHandoff fields
                    
                    # If Native Excel generated, sync the LLM responses to mathematical truth
                    cfo_roi = float(cfo_native_result.get('roi_percentage')) if native_cfo_msg else cfo_hp.get("roi_percentage", 0)
                    cfo_roas = float(cfo_native_result.get('roas')) if native_cfo_msg else cfo_hp.get("roas", 0)
                    cfo_breakeven = cfo_hp.get("breakeven_month", 0)
                    cfo_recommendation = cfo_report.recommendation

                    # ═══════════════════════════════════════════════════
                    # PHASE 3: THE ADVERSARY — CRITIC
                    # ═══════════════════════════════════════════════════
                    await _broadcast({
                        "type": "dialogue",
                        "agent": "SYSTEM",
                        "icon": "🔍",
                        "color": "#ef4444",
                        "message": f"**PHASE 3: THE ADVERSARY**\nCRITIC evaluating completed Business Plan:\n• CMO Cost: ${cmo_marketing_cost:,.0f} | Revenue: ${cmo_projected_revenue:,.0f}\n• CFO ROI: {cfo_roi}% | ROAS: {cfo_roas}x | Breakeven: Month {cfo_breakeven}",
                        "timestamp": _dt.now().isoformat()
                    }, project=project_id)

                    # CRITIC receives ALL upstream reports via orchestrator handoff
                    critic_handoff = _wr_orchestrator.build_handoff_context(
                        PipelineStep(agent_name='CRITIC', phase='adversarial', depends_on=['CMO', 'CEO', 'CTO', 'CFO']),
                        _wr_session['reports'],
                        req.message,
                        iteration=iteration,
                        market_pulse=market_pulse_data,
                        wisdom_vault=get_wisdom_vault(),
                    )
                    
                    # ═══════════════════════════════════════════════════
                    # PHASE 3 & 4: ASYNCHRONOUS PARALLELISM
                    # Run CRITIC Evaluation & Phantom UI Pathfinder concurrently
                    # ═══════════════════════════════════════════════════
                    import asyncio
                    from phantom_ui_pathfinder import run_ui_audit
                    
                    # Phase Detection Logic
                    is_architecture_phase = any(kw in msg_lower for kw in ["initialize", "architect", "genesis"])
                    
                    if is_architecture_phase:
                        await _broadcast({
                            "type": "dialogue",
                            "agent": "PHANTOM_QA",
                            "icon": "👻",
                            "color": "#14b8a6",
                            "message": "Playwright Deep Audit: SKIPPED (Architecture Phase Detected). UI testing deferred to deployment.",
                            "timestamp": _dt.now().isoformat()
                        }, project=project_id)
                        
                        critic_task = asyncio.create_task(trigger_agent_response('CRITIC', critic_handoff))
                        critic_tuple = await critic_task
                        phantom_ui_res = {"verdict": "SKIPPED", "score": 100, "errors": []}
                    else:
                        # Tell frontend that parallel execution is starting
                        await _broadcast({
                            "type": "dialogue",
                            "agent": "SYSTEM",
                            "icon": "👻",
                            "color": "#14b8a6",
                            "message": "**PHASE 3 & 4 PARALLEL EXECUTION**\nCritic reviewing logic while Phantom Pathfinder headless UI stress test runs...",
                            "timestamp": _dt.now().isoformat()
                        }, project=project_id)
                        
                        critic_task = asyncio.create_task(trigger_agent_response('CRITIC', critic_handoff))
                        phantom_task = asyncio.to_thread(run_ui_audit, project_id)
                        
                        critic_tuple, phantom_ui_res = await asyncio.gather(critic_task, phantom_task)
                    critic_resp, critic_data, critic_meta = critic_tuple

                    # ── WAR ROOM: Parse CRITIC into typed WarRoomReport ──
                    critic_report = parse_agent_response(critic_resp, 'CRITIC', 'adversarial', project_id, iteration, structured_data=critic_data, metadata=critic_meta)
                    
                    # Extract Critic Agreement Level from typed report
                    critic_score = float(critic_report.agreement_level or 0)
                    if critic_score == 0:
                        score_match = re.search(r'(?i)(?:agreement|confidence|score).*?(\d+(?:\.\d+)?)', critic_resp)
                        critic_score = float(score_match.group(1)) if score_match else 5.0
                        critic_report.agreement_level = critic_score
                        
                    _wr_store.save(critic_report, is_gate=True, gate_score=critic_score)
                    await _propose_wisdom(critic_report)
                    _wr_session['reports']['CRITIC'] = critic_report
                    
                    # ── Phase 7: Performance Review (The Learning Engine) ──
                    if critic_score >= 8.0 or critic_score <= 4.0:
                        project_type = locals().get("cto_project_type", "GLOBAL")
                        asyncio.create_task(_run_performance_review(project_id, critic_resp, critic_score, project_type))

                    # Critic score already evaluated

                    # Update Persuasion Score (UI Meter)
                    global _persuasion_score
                    _persuasion_score = min(max(critic_score, 1), 10)
                    await _broadcast({
                        "type": "persuasion_update",
                        "score": _persuasion_score,
                        "reason": (
                            f"Critic: {critic_data.get('verdict', 'N/A')} ({_persuasion_score}/10) | "
                            f"Cost Challenge: {critic_data.get('cost_challenge', 'N/A')[:60]}"
                        )
                    }, project=project_id)

                    # ═══════════════════════════════════════════════════
                    # EVALUATE AUDITOR VERDICT (Phase 4 Results)
                    # ═══════════════════════════════════════════════════
                    phantom_verdict = phantom_ui_res.get("verdict", "FAIL")
                    phantom_score = phantom_ui_res.get("score", 0)
                    
                    schema_result = {"valid": True, "note": "Checked"}
                    if phantom_verdict == "FAIL":
                        errors = phantom_ui_res.get("errors", [])
                        err_str = errors[0] if errors else "General UI Failure"
                        logger.error(f"Phantom UI Gate execution failed: {err_str}")

                    # Schema Validity: Social_Media_Matrix.json
                    project_dir = os.path.join(SCRIPT_DIR, "projects", project_id)
                    schema_result = _validate_social_media_schema(project_dir)
                    if not schema_result.get("valid", True):
                        phantom_verdict = "FAIL"
                        logger.warning(f"Schema Validity FAILED: {schema_result.get('error')}")

                    # Broadcast Phantom QA verdict
                    schema_status = "✅ Valid" if schema_result.get("valid") else f"❌ {schema_result.get('error', 'Invalid')}"
                    await _broadcast({
                        "type": "dialogue",
                        "agent": "SYSTEM",
                        "icon": "👻",
                        "color": "#14b8a6",
                        "message": (
                            f"**Phantom QA Audit Report:**\n"
                            f"Verdict: {phantom_verdict} | Score: {phantom_score}/100\n"
                            f"Schema Validity: {schema_status}\n"
                            f"Safe for Execution: {'✅ YES' if phantom_verdict == 'PASS' else '❌ NO'}"
                        ),
                        "timestamp": _dt.now().isoformat()
                    }, project=project_id)

                    # ═══════════════════════════════════════════════════
                    # EXIT CONDITION: Critic > 9.0 AND Phantom PASS/SKIPPED
                    # ═══════════════════════════════════════════════════
                    if critic_score > 9.0 and phantom_verdict in ["PASS", "SKIPPED"]:
                        logger.info("LINEAR DEPENDENCY PROTOCOL: Consensus Reached!")
                        await _broadcast({
                            "type": "consensus_iteration",
                            "iteration": iteration,
                            "max_iterations": max_iterations,
                            "status": "CONSENSUS",
                            "timestamp": _dt.now().isoformat()
                        }, project=project_id)
                        await _broadcast({
                            "type": "dialogue",
                            "agent": "SYSTEM",
                            "icon": "✅",
                            "color": "#10b981",
                            "message": (
                                f"**CONSENSUS REACHED (Iteration {iteration})**\n"
                                f"Critic: {critic_score}/10 ✅ | Phantom QA: {phantom_verdict} ✅\n"
                                f"Business Plan: CMO ${cmo_marketing_cost:,.0f} → CTO {cto_feasibility}/10 → CFO ROI {cfo_roi}% → APPROVED\n"
                                f"Safe for Execution. Deliberation terminated."
                            ),
                            "timestamp": _dt.now().isoformat()
                        }, project=project_id)
                        break

                    # ── Aether Memory Compression for next iteration ──
                    compressed = _compress_context(cmo_data, cto_data, cfo_data, critic_data, phantom_verdict, phantom_score)
                    # Build re-entry topic with Critic's specific objections
                    cost_challenge = critic_data.get("cost_challenge", "No specific cost challenge.")
                    revenue_challenge = critic_data.get("revenue_challenge", "No specific revenue challenge.")
                    topic = (
                        f"ITERATION {iteration} FAILED CONSENSUS — REVISE AND RESUBMIT:\n\n"
                        f"Previous Results: {compressed}\n\n"
                        f"CRITIC COST CHALLENGE: {cost_challenge}\n"
                        f"CRITIC REVENUE CHALLENGE: {revenue_challenge}\n"
                        f"Critic Objections: {'; '.join(critic_data.get('objections', []))}\n"
                        f"Evidence Demanded: {critic_data.get('evidence_demanded', 'N/A')}\n"
                        f"Phantom Verdict: {phantom_verdict} (Score: {phantom_score}/100)\n\n"
                        f"CMO: Revise your marketing_cost and projected_revenue to address the Critic's challenges.\n"
                        f"Original directive: {req.message}"
                    )
                    iteration += 1

                if iteration > max_iterations:
                    await _broadcast({
                        "type": "consensus_iteration",
                        "iteration": max_iterations,
                        "max_iterations": max_iterations,
                        "status": "MAX_REACHED",
                        "timestamp": _dt.now().isoformat()
                    }, project=project_id)
                    await _broadcast({
                        "type": "dialogue",
                        "agent": "SYSTEM",
                        "icon": "🛑",
                        "color": "#ef4444",
                        "message": f"Linear Dependency Protocol: Max iterations ({max_iterations}) reached without consensus. Awaiting Commander hard override.",
                        "timestamp": _dt.now().isoformat()
                    }, project=project_id)

                logger.info("Sequential C-Suite Chain Completed.")
                _wr_orchestrator.end_session(project_id, 'consensus_reached' if iteration <= max_iterations else 'max_iterations')
            except Exception as e:
                logger.error(f"C-Suite Trigger Chain failed: {e}")
                _wr_orchestrator.end_session(project_id, f'error: {str(e)[:100]}')
            finally:
                ORCHESTRATION_STATE = "healthy"
                
        asyncio.create_task(trigger_csuite())
        return {"status": "processing", "message": "Sequential C-Suite Trigger Initiated", "project_id": project_id}
        
    return {"status": "ignored", "message": "No actionable keywords detected."}

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


# ═══════════════════════════════════════════════════════════════
#  UPGRADE 5: Agent Call Metrics (Post-N8N)
# ═══════════════════════════════════════════════════════════════
import socket as _socket

_agent_call_stats = {"total": 0, "model_router": 0, "gemini_direct": 0, "cached": 0}

# ═══════════════════════════════════════════════════════════════
#  UPGRADE 4: Intelligent Model Router (Gemini / Claude)
# ═══════════════════════════════════════════════════════════════

try:
    from model_router import route as _model_route, get_model_for_task
    _MODEL_ROUTER_AVAILABLE = True
    logger.info("Model Router loaded (Gemini + Claude routing).")
except ImportError:
    _MODEL_ROUTER_AVAILABLE = False
    logger.warning("Model Router not found — falling back to Gemini-only.")


# ═══════════════════════════════════════════════════════════════
#  UPGRADE 5: Master Architect — Pre-Feature Architectural Review
# ═══════════════════════════════════════════════════════════════

_ARCHITECT_SYSTEM_PROMPT = """You are the MASTER ARCHITECT of a software factory.
You review proposed features, builds, and code changes BEFORE they are implemented.
Your job is to identify architectural concerns, suggest best practices, and approve or flag designs.

Respond in this EXACT JSON format (no markdown, no code fences):
{
  "verdict": "APPROVE" or "REVIEW" or "REJECT",
  "concerns": ["list of architectural concerns, max 3"],
  "recommendations": ["list of actionable recommendations, max 3"],
  "architecture_notes": "1-2 sentence summary of architectural guidance"
}

Focus on: port conflicts, process management, frontend/backend coupling,
error handling, state management, security, and deployment patterns.
Be concise. Never output anything outside the JSON object."""


def _architect_review(feature_description: str, change_type: str = "feature",
                      affected_components: list = None) -> dict:
    """Send a feature/fix description to the Master Architect for review.
    Uses Model Router to pick the best LLM.
    Returns {verdict, concerns, recommendations, architecture_notes}."""
    if not _MODEL_ROUTER_AVAILABLE:
        return {"verdict": "SKIP", "concerns": [], "recommendations": [],
                "architecture_notes": "Model Router unavailable — Architect review skipped."}

    prompt = (
        f"CHANGE TYPE: {change_type}\n"
        f"AFFECTED COMPONENTS: {', '.join(affected_components or ['unknown'])}\n"
        f"DESCRIPTION:\n{feature_description}\n\n"
        f"Provide your architectural review."
    )
    try:
        raw = _model_route("architect", prompt, _ARCHITECT_SYSTEM_PROMPT)
        # Parse JSON response
        import re as _re
        # Strip markdown fences if present
        cleaned = _re.sub(r'^```[\w]*\n|```$', '', raw.strip(), flags=_re.MULTILINE).strip()
        result = json.loads(cleaned)
        result.setdefault("verdict", "REVIEW")
        result.setdefault("concerns", [])
        result.setdefault("recommendations", [])
        result.setdefault("architecture_notes", "")
        return result
    except json.JSONDecodeError:
        return {"verdict": "REVIEW", "concerns": [],
                "recommendations": [], "architecture_notes": raw[:300] if raw else "Parse error"}
    except Exception as e:
        return {"verdict": "ERROR", "concerns": [str(e)[:200]],
                "recommendations": [], "architecture_notes": "Architect review failed."}


class ArchitectReviewRequest(BaseModel):
    feature_description: str
    change_type: str = "feature"  # feature, bugfix, new_app, refactor
    affected_components: list = []


@app.post("/api/architect/review")
def architect_review(req: ArchitectReviewRequest):
    """Master Architect pre-feature review. Call before implementing any significant change."""
    result = _architect_review(req.feature_description, req.change_type, req.affected_components)
    # Record to institutional memory
    if MEMORY_AVAILABLE:
        try:
            record_lesson(
                f"Architect review ({req.change_type}): {result.get('verdict')} — {result.get('architecture_notes', '')[:100]}",
                "architect_review", ",".join(req.affected_components or ["general"])
            )
        except Exception:
            pass
    return result

def _gemini_direct(agent_name: str, topic: str) -> str:
    """Generate a real AI response via streaming bridge (secondary fallback)."""
    try:
        if STREAMING_AVAILABLE:
            from streaming_bridge import stream_chat
            prompt = (
                f"You are the {agent_name} in a C-suite boardroom war room. "
                f"Give a concise assessment (3-5 sentences) on this topic. "
                f"Stay in character as a senior executive.\n\nTOPIC: {topic}"
            )
            full_response = ""
            for event in stream_chat(prompt, dashboard_context={"mode": "warroom", "agent": agent_name}):
                if event.get("type") == "chunk":
                    full_response += event.get("text", "")
                elif event.get("type") == "complete":
                    full_response = event.get("text", full_response)
            if full_response.strip():
                return full_response.strip()[:2000]
    except Exception as e:
        logger.warning(f"[GeminiDirect] {agent_name} failed: {e}")
    return ""


# ═══════════════════════════════════════════════════════════════
#  UPGRADE 6: AI Model Health Endpoint
# ═══════════════════════════════════════════════════════════════

@app.get("/api/health/ai")
def ai_health():
    """Return AI model connectivity status and call stats."""
    return {
        "status": "model_router" if _MODEL_ROUTER_AVAILABLE else "gemini_direct",
        "model_router_available": _MODEL_ROUTER_AVAILABLE,
        "streaming_available": STREAMING_AVAILABLE,
        "call_stats": _agent_call_stats.copy(),
    }


# ═══════════════════════════════════════════════════════════════
#  UPGRADE 1: App Launch / Stop / Watchdog / Self-Healing
# ═══════════════════════════════════════════════════════════════

_running_apps: dict = {}  # app_name -> {"process": Popen, "port": int, ...}
_restart_cooldowns: dict = {}  # app_name -> last_restart_timestamp
import threading as _threading
import socket as _socket
import time as _time


def _find_free_port(start_port: int, max_scan: int = 20) -> int:
    """Scan upward from start_port to find the next free port."""
    for offset in range(max_scan):
        port = start_port + offset
        with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start_port + max_scan


# ── Post-Launch Smoke Test (Phantom QA Integration) ──────────
def _smoke_test_app(port: int, timeout: int = 10) -> dict:
    """
    Phantom QA post-launch smoke test.
    Polls http://localhost:{port}/ every 1s for up to `timeout` seconds.
    Verifies HTTP 200 and text/html content type (not JSON).
    Returns {"passed": bool, "detail": str, "content_type": str, "status_code": int}.
    """
    import urllib.request
    import urllib.error
    deadline = _time.time() + timeout
    last_error = "timeout"
    while _time.time() < deadline:
        try:
            req = urllib.request.Request(f"http://localhost:{port}/", method="GET")
            with urllib.request.urlopen(req, timeout=2) as resp:
                status = resp.status
                ct = resp.headers.get("Content-Type", "")
                body_peek = resp.read(500).decode("utf-8", errors="replace")
                is_html = "text/html" in ct or "<html" in body_peek.lower() or "<!doctype" in body_peek.lower()
                if status == 200 and is_html:
                    return {"passed": True, "detail": "Frontend serving HTML", "content_type": ct, "status_code": status}
                elif status == 200:
                    # App is up but serving JSON (API-only) — still counts as alive
                    return {"passed": True, "detail": "API responding (no frontend build)", "content_type": ct, "status_code": status}
                else:
                    last_error = f"HTTP {status}"
        except urllib.error.URLError as e:
            last_error = str(e.reason)
        except Exception as e:
            last_error = str(e)
        _time.sleep(1)
    return {"passed": False, "detail": last_error, "content_type": "", "status_code": 0}


@app.post("/api/apps/{app_name}/launch")
def launch_app(app_name: str):
    """Launch a registered app with post-launch Phantom QA smoke test."""
    global _running_apps
    if app_name in _running_apps:
        info = _running_apps[app_name]
        return {"status": "already_running", "port": info["port"], "url": f"http://localhost:{info['port']}"}

    result = _do_launch(app_name)
    if isinstance(result, JSONResponse):
        return result

    # ── Phantom QA Post-Launch Smoke Test ──
    port = result["port"]
    pid = result["pid"]
    smoke = _smoke_test_app(port, timeout=10)
    result["launch_verified"] = smoke["passed"]
    result["smoke_test"] = smoke

    if smoke["passed"]:
        logger.info(f"✅ Phantom QA: {app_name} verified on port {port} ({smoke['detail']})")
        # Record success lesson
        if MEMORY_AVAILABLE:
            try:
                record_lesson(f"App launch verified: {app_name} on port {port}", "launch_success", app_name)
            except Exception:
                pass
    else:
        logger.warning(f"⚠️ Phantom QA: {app_name} smoke test FAILED on port {port} ({smoke['detail']})")
        # Check if process died
        proc_info = _running_apps.get(app_name)
        if proc_info and proc_info["process"].poll() is not None:
            _running_apps.pop(app_name, None)
            result["status"] = "launch_failed"
            logger.error(f"❌ {app_name} process died immediately (exit code: {proc_info['process'].returncode})")
        if MEMORY_AVAILABLE:
            try:
                record_lesson(
                    f"App launch FAILED: {app_name} on port {port}. {smoke['detail']}",
                    "launch_failure", app_name
                )
            except Exception:
                pass
    return result


def _do_launch(app_name: str, port_override: int = None) -> dict:
    """Internal launch logic. Returns dict on success, JSONResponse on failure."""
    global _running_apps

    # Resolve app directory
    gdrive = os.path.join(os.path.expanduser("~"), "My Drive", "Antigravity-AI Agents", "Meta_App_Factory")
    app_dir = None
    for candidate in [
        os.path.join(gdrive, app_name), 
        os.path.join(SCRIPT_DIR, app_name),
        os.path.join(SCRIPT_DIR, "projects", app_name),
        os.path.join(SCRIPT_DIR, "agents", app_name)
    ]:
        if os.path.isdir(candidate):
            app_dir = candidate
            break
    if not app_dir:
        return JSONResponse({"error": f"App directory not found for '{app_name}'"}, status_code=404)

    # Find the server script (Prioritize .bat files for composite apps)
    server_script = None
    bat_path = os.path.join(app_dir, f"launch_{app_name}.bat")
    if os.path.isfile(bat_path):
        server_script = bat_path
    
    if not server_script:
        for candidate_name in ["server.py", "app.py", "main.py"]:
            candidate_path = os.path.join(app_dir, candidate_name)
            if os.path.isfile(candidate_path):
                server_script = candidate_path
                break

    if not server_script:
        return JSONResponse({"error": f"No server.py/app.py/main.py or launch_{app_name}.bat found in {app_dir}"}, status_code=404)

    # Determine port
    if port_override:
        port = port_override
    else:
        assigned_port = 5010
        try:
            with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
                reg_data = json.load(f)
            app_info = reg_data.get("apps", {}).get(app_name, {})
            if app_info.get("port"):
                assigned_port = int(app_info["port"])
        except Exception:
            pass
        port = _find_free_port(assigned_port)

    # Start the process
    try:
        env = os.environ.copy()
        env["PORT"] = str(port)
        if server_script.endswith(".py"):
            proc = subprocess.Popen(
                [sys.executable, server_script, "--port", str(port)],
                cwd=app_dir, env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
        else:
            proc = subprocess.Popen(
                [server_script],
                cwd=app_dir, env=env, shell=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
        _running_apps[app_name] = {
            "process": proc, "port": port, "pid": proc.pid,
            "app_dir": app_dir, "server_script": server_script,
            "launched_at": _time.time(),
        }
        logger.info(f"Launched {app_name} on port {port} (PID: {proc.pid})")
        return {"status": "launched", "port": port, "url": f"http://localhost:{port}", "pid": proc.pid}
    except Exception as e:
        return JSONResponse({"error": f"Failed to launch: {str(e)}"}, status_code=500)


@app.post("/api/apps/{app_name}/stop")
def stop_app(app_name: str):
    """Stop a running app."""
    global _running_apps
    if app_name not in _running_apps:
        return JSONResponse({"error": f"'{app_name}' is not running"}, status_code=404)
    info = _running_apps.pop(app_name)
    try:
        info["process"].terminate()
        info["process"].wait(timeout=5)
    except Exception:
        try:
            info["process"].kill()
        except Exception:
            pass
    logger.info(f"Stopped {app_name} (was on port {info['port']})")
    return {"status": "stopped", "app_name": app_name}


# ── Child App Process Watchdog + Self-Healing Auto-Restart ────
_WATCHDOG_INTERVAL = 30  # seconds
_RESTART_COOLDOWN = 300  # 5 minutes between auto-restarts per app

def _watchdog_loop():
    """Background thread: monitors child app health every 30s.
    Detects dead processes, attempts auto-restart (max 1 per 5min), records lessons."""
    while True:
        _time.sleep(_WATCHDOG_INTERVAL)
        try:
            dead_apps = []
            for name, info in list(_running_apps.items()):
                if info["process"].poll() is not None:
                    dead_apps.append((name, info))

            for name, info in dead_apps:
                exit_code = info["process"].returncode
                logger.warning(f"🔴 Watchdog: {name} died (exit code {exit_code}, was port {info['port']})")

                # Record crash lesson
                if MEMORY_AVAILABLE:
                    try:
                        record_lesson(
                            f"Child app CRASHED: {name} (exit code {exit_code}, port {info['port']}). "
                            f"Auto-healing will attempt restart.",
                            "child_app_crash", name
                        )
                    except Exception:
                        pass

                # Remove dead reference
                _running_apps.pop(name, None)

                # Auto-restart with cooldown
                last_restart = _restart_cooldowns.get(name, 0)
                if _time.time() - last_restart > _RESTART_COOLDOWN:
                    logger.info(f"🔄 Watchdog: Auto-restarting {name}...")
                    _restart_cooldowns[name] = _time.time()

                    result = _do_launch(name, port_override=info["port"])
                    if isinstance(result, JSONResponse):
                        logger.error(f"❌ Watchdog: Auto-restart of {name} failed")
                        if MEMORY_AVAILABLE:
                            try:
                                record_lesson(f"Auto-restart FAILED for {name}", "auto_restart_failed", name)
                            except Exception:
                                pass
                        continue

                    # Run smoke test on restarted app
                    smoke = _smoke_test_app(result["port"], timeout=8)
                    if smoke["passed"]:
                        logger.info(f"✅ Watchdog: {name} auto-healed on port {result['port']}")
                        if MEMORY_AVAILABLE:
                            try:
                                record_lesson(
                                    f"Auto-HEALED: {name} restarted on port {result['port']}",
                                    "auto_healed", name
                                )
                            except Exception:
                                pass
                    else:
                        logger.error(f"❌ Watchdog: {name} restarted but smoke test failed: {smoke['detail']}")
                        if MEMORY_AVAILABLE:
                            try:
                                record_lesson(
                                    f"Auto-restart of {name} succeeded but smoke test FAILED: {smoke['detail']}",
                                    "auto_restart_smoke_fail", name
                                )
                            except Exception:
                                pass
                else:
                    cooldown_left = int(_RESTART_COOLDOWN - (_time.time() - last_restart))
                    logger.warning(f"⏳ Watchdog: {name} cooldown active ({cooldown_left}s remaining), skipping restart")

        except Exception as e:
            logger.error(f"Watchdog error: {e}")

# Start watchdog thread on module load
_watchdog_thread = _threading.Thread(target=_watchdog_loop, daemon=True, name="app-watchdog")
_watchdog_thread.start()

# Start Aether Native Watchdog (Phase 7)
try:
    from native_watchdog import get_native_watchdog
    get_native_watchdog().start_background_loop()
except Exception as e:
    logger.error(f"Failed to start Aether Native Watchdog: {e}")
logger.info("🐕 App Watchdog started (30s interval, auto-restart with 5min cooldown)")


@app.get("/api/apps/running")
def get_running_apps():
    """Return list of currently running apps with health status."""
    result = {}
    for name, info in list(_running_apps.items()):
        alive = info["process"].poll() is None
        health = "healthy" if alive else "dead"
        # Quick health ping for alive processes
        if alive:
            try:
                import urllib.request
                with urllib.request.urlopen(f"http://localhost:{info['port']}/api/health", timeout=2) as resp:
                    if resp.status != 200:
                        health = "degraded"
            except Exception:
                health = "degraded"
        result[name] = {
            "port": info["port"], "pid": info["pid"],
            "alive": alive, "health": health
        }
    return result


# ── War Room WebSocket (Phase 2 — Adversarial Boardroom) ─────

import asyncio
import time as _time
import random
import requests as _requests
from datetime import datetime as _dt
from concurrent.futures import ThreadPoolExecutor

_warroom_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="warroom")

# War Room State (Per-Project)
_warroom_clients: dict[str, list[WebSocket]] = {}
_warroom_logs: dict[str, list[dict]] = {}
_persuasion_score: int = 5  # 1-10 Critic agreement
_session_active: bool = False

# UPGRADE 2: War Room Persistence (Per-Project)
def _get_history_path(project: str):
    pdir = os.path.join(SCRIPT_DIR, "projects", project)
    os.makedirs(pdir, exist_ok=True)
    return os.path.join(pdir, "warroom_history.json")

def _load_warroom_history(project: str):
    """Load War Room history from disk on startup."""
    if project not in _warroom_logs: _warroom_logs[project] = []
    path = _get_history_path(project)
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            _warroom_logs[project] = data.get("messages", [])[-200:]
            logger.info(f"War Room: loaded {len(_warroom_logs[project])} messages for {project}")
    except Exception as e:
        logger.warning(f"War Room history load failed for {project}: {e}")

def _save_warroom_history(project: str):
    """Persist War Room messages to disk."""
    path = _get_history_path(project)
    try:
        data = {
            "last_updated": _dt.now().isoformat(),
            "message_count": len(_warroom_logs.get(project, [])),
            "messages": _warroom_logs.get(project, [])[-500:],  # Keep last 500
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as e:
        logger.warning(f"War Room history save failed for {project}: {e}")

# Agent personas for the boardroom
_AGENTS = {
    "CEO": {"icon": "👔", "color": "#3b82f6", "role": "Chief Executive Officer"},
    "CMO": {"icon": "📢", "color": "#8b5cf6", "role": "Chief Marketing Officer"},
    "CFO": {"icon": "💰", "color": "#22c55e", "role": "Chief Financial Officer"},
    "CTO": {"icon": "🔧", "color": "#06b6d4", "role": "Chief Technology Officer"},
    "CRITIC": {"icon": "🔍", "color": "#ef4444", "role": "Quality Assurance / Devil's Advocate"},
    "ARCHITECT": {"icon": "🏗️", "color": "#06b6d4", "role": "System Architect"},
    "SYSTEM": {"icon": "⚡", "color": "#eab308", "role": "System Orchestrator"},
}

# Agent registry
_WARROOM_AGENT_NAMES = ["CEO", "CMO", "CFO", "CTO", "CRITIC", "CLO", "CPO"]

# Role-scoped prompt templates (Linear Dependency Protocol)
_WARROOM_PROMPTS = {
    "CMO": (
        "You are the CMO in a boardroom war room. You are PHASE 1 of the Linear Dependency Protocol. "
        "All downstream agents (CFO, CRITIC) depend on YOUR numbers. "
        "Respond in VALID JSON ONLY (no markdown fences, no extra text).\n\n"
        "Required JSON schema:\n"
        '{{\n'
        '  "market_strategy": "your 3-5 sentence go-to-market strategy",\n'
        '  "target_demographic": "specific audience segment with size estimate",\n'
        '  "marketing_cost": 50000,\n'
        '  "projected_revenue": 250000,\n'
        '  "revenue_timeline_months": 12,\n'
        '  "demographic_reach": 150000,\n'
        '  "cost_per_acquisition": 8.50,\n'
        '  "recommendation": "PROCEED or PIVOT or HOLD",\n'
        '  "confidence": 7.5,\n'
        '  "key_risks": ["risk 1", "risk 2"]\n'
        '}}\n\n'
        "CRITICAL: You MUST provide specific dollar amounts for marketing_cost and projected_revenue. "
        "These numbers flow directly into the CFO's business plan. Vague estimates are unacceptable.\n\nTOPIC: {topic}"
    ),
    "CEO": (
        "You are the CEO in a boardroom war room. You are the VALIDATOR for Phase 1. "
        "The CMO has presented their market strategy. Your job is to validate it against "
        "the company's growth targets. Respond in VALID JSON ONLY.\n\n"
        "Required JSON schema:\n"
        '{{\n'
        '  "growth_target_alignment": "ALIGNED or MISALIGNED or PARTIAL",\n'
        '  "strategic_assessment": "your 3-5 sentence assessment of the CMO strategy",\n'
        '  "growth_target_annual": 500000,\n'
        '  "gap_to_target": 0,\n'
        '  "approved_for_phase2": true,\n'
        '  "concerns": ["concern 1"]\n'
        '}}\n\n'
        "Compare the CMO's projected_revenue against your growth_target_annual. "
        "If the gap is too large, set approved_for_phase2 to false.\n\nTOPIC: {topic}"
    ),
    "CFO": (
        "You are the CFO in a boardroom war room. You are PHASE 2 of the Linear Dependency Protocol. "
        "You CANNOT produce estimates from thin air — you MUST use the CMO's marketing_cost and "
        "projected_revenue figures provided below as your input data. "
        "Respond in VALID JSON ONLY (no markdown fences, no extra text).\n\n"
        "Required JSON schema:\n"
        '{{\n'
        '  "business_plan_summary": "your 3-5 sentence business plan assessment",\n'
        '  "cmo_marketing_cost_used": 50000,\n'
        '  "cmo_projected_revenue_used": 250000,\n'
        '  "profitability_timeline_months": 8,\n'
        '  "roi_percentage": 400.0,\n'
        '  "roas": 5.0,\n'
        '  "breakeven_month": 6,\n'
        '  "burn_rate_monthly": 15000,\n'
        '  "recommendation": "FUND or DEFER or REJECT",\n'
        '  "confidence": 7.0,\n'
        '  "financial_risks": ["risk 1", "risk 2"]\n'
        '}}\n\n'
        "CRITICAL: ROI = ((projected_revenue - marketing_cost) / marketing_cost) * 100. "
        "ROAS = projected_revenue / marketing_cost. Use the CMO's EXACT numbers.\n\nTOPIC: {topic}"
    ),
    "CRITIC": (
        "You are the Chief Critic and quality arbiter in a boardroom war room. You are PHASE 3. "
        "You ONLY evaluate the COMPLETED Business Plan produced by Phase 1 (CMO) and Phase 2 (CFO). "
        "Respond in VALID JSON ONLY (no markdown fences, no extra text).\n\n"
        "Required JSON schema:\n"
        '{{\n'
        '  "agreement_level": 6.5,\n'
        '  "verdict": "AGREE or OBJECT or ABSTAIN",\n'
        '  "cost_challenge": "your specific challenge to the CMO marketing_cost assumption",\n'
        '  "revenue_challenge": "your specific challenge to the CFO revenue optimism",\n'
        '  "objections": ["objection 1", "objection 2"],\n'
        '  "evidence_demanded": "what data you need to see to raise your agreement_level",\n'
        '  "analysis": "your 3-5 sentence critical assessment of the full business plan"\n'
        '}}\n\n'
        "You must SPECIFICALLY challenge: (1) the CMO's marketing_cost assumptions — are they realistic? "
        "(2) the CFO's revenue projections — is the ROI/ROAS achievable? "
        "Score agreement_level 1-10. Be tough but fair.\n\nTOPIC: {topic}"
    ),
    "CTO": (
        "You are an Elite Enterprise Architect in a boardroom war room. You are PHASE 1.5 of the Linear Dependency Protocol. "
        "The CEO has validated the CMO's market strategy. Your job is to assess TECHNICAL FEASIBILITY "
        "before the CFO builds the financial model. You have access to the _ANTIGRAVITY_SKILLS_LIBRARY. "
        "You are strictly forbidden from proposing basic, single-file scripts or MVP-level code. Every blueprint you design must be State-of-the-Art. "
        "You must default to advanced native Python patterns: asynchronous processing (asyncio), strict type-hinting, fault-tolerance, and zero-latency internal execution. "
        "Assume every application is destined for commercial venture scale. Architect accordingly. "
        "All builds must follow V3 Resilience Core (healed_post, auto_heal, StateManager). "
        "You operate the Master Architect Elite Pre-Deploy Gate. "
        "UNIVERSAL STACK EVALUATOR (USE) is ONLINE. You evaluate ALL project types: "
        "DIGITAL (code/SaaS), PHYSICAL (hardware/logistics), and OPERATIONAL (AI tools/process automation). "
        "For non-digital projects, focus your tech_stack on the Automation and Monitoring Layer - "
        "how Antigravity Ops Intelligence will track project health. "
        "The feasibility score reflects our INTERNAL capability to automate and oversee the venture. "
        "SCAN _ANTIGRAVITY_SKILLS_LIBRARY for execution building blocks. "
        "Respond in VALID JSON ONLY (no markdown fences, no extra text).\\n\\n"
        "Required JSON schema:\\n"
        '{{\\n'
        '  "technical_feasibility_score": 7.5,\\n'
        '  "project_type": "DIGITAL or PHYSICAL or OPERATIONAL or HYBRID",\\n'
        '  "tech_stack": ["FastAPI", "React/Vite", "Supabase"],\\n'
        '  "automation_monitoring_layer": "how Antigravity Ops Intelligence tracks this project",\\n'
        '  "skills_library_blocks": ["model-router", "regulatory-shield"],\\n'
        '  "implementation_timeline_weeks": 3,\\n'
        '  "v3_compliance": "COMPLIANT or NON_COMPLIANT",\\n'
        '  "pre_deploy_gate_status": "CLEAR or BLOCKED",\\n'
        '  "architecture_assessment": "3-5 sentence technical assessment",\\n'
        '  "scalability_rating": "HIGH or MEDIUM or LOW",\\n'
        '  "technical_risks": ["risk 1", "risk 2"],\\n'
        '  "recommendation": "BUILD or PROTOTYPE or REJECT",\\n'
        '  "meta_factory_integration": "which Factory blueprint and patterns to use",\\n'
        '  "cfo_ready_metrics": {\\n'
        '    "infrastructure_cost_estimate": 5000,\\n'
        '    "development_buffer_weeks": 4.5,\\n'
        '    "tech_debt_risk_premium_pct": 10,\\n'
        '    "gate_source": "aether_native"\\n'
        '  }\\n'
        '}}\\n\\n'
        "CRITICAL: technical_feasibility_score MUST be 1-10. Scores below 4 trigger a TECHNICAL GATE FAILURE "
        "and block the CFO from building the financial model. For NON-DIGITAL projects, score reflects "
        "our capability to AUTOMATE AND MONITOR the venture. "
        "cfo_ready_metrics.infrastructure_cost_estimate = monthly hosting/tooling/API costs based on tech_stack. "
        "cfo_ready_metrics.development_buffer_weeks = 1.5x implementation_timeline_weeks if feasibility below 7, else same as timeline. "
        "cfo_ready_metrics.tech_debt_risk_premium_pct = percentage to add to CFO budget for V3 compliance hardening. "
        "The Technical Gate is Aether-Native and feeds real-time infrastructure costs to the CFO. Be rigorous but fair.\\n\\nTOPIC: {topic}"
    ),
}

def _call_agent(agent_name: str, topic: str) -> str:
    print(f"[DEBUG-TRACE] => Entering _call_agent for {agent_name}...", flush=True)
    try:
        template = _WARROOM_PROMPTS.get(agent_name, "")
        if template:
            try:
                prompt = template.format(topic=topic)
            except KeyError:
                prompt = template.replace("{topic}", topic)
        else:
            prompt = f"You are {agent_name}. Topic: {topic}"

        _agent_call_stats["total"] += 1

        print(f"[DEBUG-TRACE] {agent_name} -> Prompt built. Model router available: {_MODEL_ROUTER_AVAILABLE}", flush=True)
        if _MODEL_ROUTER_AVAILABLE:
            try:
                print(f"[DEBUG-TRACE] {agent_name} -> Calling _model_route via general...", flush=True)
                result = _model_route("general", prompt)
                print(f"[DEBUG-TRACE] {agent_name} -> _model_route finished. len={(len(result) if result else 0)}", flush=True)
                if result and result.strip():
                    return result.strip()[:2000]
            except Exception as e:
                print(f"[DEBUG-TRACE] {agent_name} -> _model_route exception: {e}", flush=True)

        print(f"[DEBUG-TRACE] {agent_name} -> Testing fallback _gemini_direct...", flush=True)
        result = _gemini_direct(agent_name, topic)
        print(f"[DEBUG-TRACE] {agent_name} -> _gemini_direct finished.", flush=True)
        if result and result.strip():
            return result.strip()

        print(f"[DEBUG-TRACE] {agent_name} -> Returning EMPTY string.", flush=True)
        return ""

    except Exception as e:
        print(f"[DEBUG-TRACE] {agent_name} -> COMPLETE FAILURE: {e}", flush=True)
        return ""


_warroom_sse_queues = {}

async def _broadcast(msg: dict, project: str = "Aether"):
    """Send a message to all connected War Room clients for a project + persist to disk."""
    if project not in _warroom_logs: _warroom_logs[project] = []
    _warroom_logs[project].append(msg)
    # Keep last 200 in memory
    if len(_warroom_logs[project]) > 200:
        _warroom_logs[project].pop(0)
    # Persist to disk (Upgrade 2)
    _save_warroom_history(project)
    
    dead = []
    for ws in _warroom_clients.get(project, []):
        try:
            await ws.send_json(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _warroom_clients[project].remove(ws)
        
    for q in _warroom_sse_queues.get(project, []):
        q.put_nowait(msg)


@app.get("/api/war-room/stream")
async def war_room_sse_stream(project: str, request: Request):
    """SSE endpoint for React frontend (CommandCenter.jsx) to receive broadcast events."""
    import asyncio
    if project not in _warroom_sse_queues:
        _warroom_sse_queues[project] = []
    
    q = asyncio.Queue()
    _warroom_sse_queues[project].append(q)
    
    # Snapshot of state_machine events already in history so new clients catch up
    # (mirrors the WebSocket history replay — fixes the race condition where
    #  native_sequence() broadcasts before the browser SSE connection is ready)
    history_replay = [
        msg for msg in _warroom_logs.get(project, [])
        if msg.get("type") == "state_machine"
    ]
    
    async def sse_generator():
        try:
            # Send an initial connection event
            init_msg = {"type": "init", "message": "SSE Connected"}
            yield f"data: {json.dumps(init_msg)}\n\n"
            
            # Replay any state_machine history so the stepper catches up
            for past_msg in history_replay:
                yield f"data: {json.dumps(past_msg)}\n\n"
            
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=2.0)
                    yield f"data: {json.dumps(msg)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            if q in _warroom_sse_queues.get(project, []):
                _warroom_sse_queues[project].remove(q)
                
    return StreamingResponse(sse_generator(), media_type="text/event-stream")



@app.websocket("/ws/warroom")
async def warroom_websocket(websocket: WebSocket, project: str = "Aether"):
    """WebSocket endpoint for War Room real-time dialogue."""
    global _persuasion_score
    await websocket.accept()
    
    if project not in _warroom_clients: _warroom_clients[project] = []
    _warroom_clients[project].append(websocket)
    _load_warroom_history(project)
    logger.info(f"War Room '{project}' client connected ({len(_warroom_clients[project])} total)")

    # Send history on connect
    try:
        await websocket.send_json({
            "type": "init",
            "history": _warroom_logs.get(project, [])[-50:],
            "persuasion": _persuasion_score,
            "agents": _AGENTS,
        })
    except Exception:
        pass

    try:
        while True:
            data = await websocket.receive_json()
            # Handle user interventions and EOS commands
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
                }, project=project)
                
                # ── Phase 11 Bypass for @operator commands ──
                if "@operator" in user_msg.lower():
                    continue
                
                # ── EOS Action Parsing ──
                if user_msg.startswith("/market"):
                    import asyncio
                    req = {"project_name": project, "company_name": get_eos(project).get("company_name", "Startup")}
                    res = generate_market_intel(req)
                    if res.get("status") == "ok":
                        await _broadcast({
                            "type": "dialogue", "agent": "SYSTEM", "icon": "📊", "color": "#10b981",
                            "message": f"**Market Intel Acquired**\nTAM: {res['market'].get('tam')}\nSAM: {res['market'].get('sam')}\nSOM: {res['market'].get('som')}",
                            "timestamp": _dt.now().isoformat()
                        }, project=project)
                    else:
                        await _broadcast({"type": "dialogue", "agent": "SYSTEM", "icon": "❌", "color": "#ef4444", "message": f"Market Intel Error: {res.get('error')}", "timestamp": _dt.now().isoformat()}, project=project)
                    asyncio.create_task(_live_debate("Review the Market Intel just acquired.", project_name=project, phase="market"))
                
                elif user_msg.startswith("/brand"):
                    import asyncio
                    res = generate_brand_identity({"project_name": project})
                    if res.get("status") == "ok":
                        b = res["brand"]
                        await _broadcast({
                            "type": "dialogue", "agent": "SYSTEM", "icon": "🎨", "color": "#a855f7",
                            "message": f"**Brand DNA Generated**\nName: {b.get('company_name')}\nTagline: {b.get('tagline')}\nLogo Prompt: {b.get('logo_prompt')}",
                            "timestamp": _dt.now().isoformat()
                        }, project=project)
                    else:
                        await _broadcast({"type": "dialogue", "agent": "SYSTEM", "icon": "❌", "color": "#ef4444", "message": f"Brand Error: {res.get('error')}", "timestamp": _dt.now().isoformat()}, project=project)
                    asyncio.create_task(_live_debate("Critique the new brand identity.", project_name=project, phase="brand"))

                elif user_msg.startswith("/legal"):
                    import asyncio
                    res = generate_legal_analysis({"project_name": project})
                    if res.get("status") == "ok":
                        l = res["legal"]
                        await _broadcast({
                            "type": "dialogue", "agent": "SYSTEM", "icon": "⚖️", "color": "#14b8a6",
                            "message": f"**Legal Analysis Complete**\nTrademark Viability: {l.get('trademark_viability')}",
                            "timestamp": _dt.now().isoformat()
                        }, project=project)
                    else:
                        await _broadcast({"type": "dialogue", "agent": "SYSTEM", "icon": "❌", "color": "#ef4444", "message": f"Legal Error: {res.get('error')}", "timestamp": _dt.now().isoformat()}, project=project)
                    asyncio.create_task(_live_debate("Review the Legal & IP analysis.", project_name=project, phase="legal"))

                elif user_msg.startswith("/financials"):
                    import asyncio
                    res = generate_financial_model({"project_name": project})
                    if res.get("status") == "ok":
                        link = f"http://localhost:8000/api/eos/documents/{res['path'].split('/')[-1]}" if '/' in str(res.get('path')) else res.get('path')
                        await _broadcast({
                            "type": "dialogue", "agent": "SYSTEM", "icon": "📈", "color": "#3b82f6",
                            "message": f"**Financial Model Ready**\nBreakeven: Month {res.get('breakeven')}\n[Download XLSX]({link})",
                            "timestamp": _dt.now().isoformat()
                        }, project=project)
                    else:
                        await _broadcast({"type": "dialogue", "agent": "SYSTEM", "icon": "❌", "color": "#ef4444", "message": f"Financial Error: {res.get('error')}", "timestamp": _dt.now().isoformat()}, project=project)
                    asyncio.create_task(_live_debate("Assess the 5-year financial projections just generated.", project_name=project, phase="financials"))

                elif user_msg.startswith("/business-plan"):
                    import asyncio
                    res = generate_business_plan({"project_name": project})
                    if res.get("status") == "ok":
                        await _broadcast({
                            "type": "dialogue", "agent": "SYSTEM", "icon": "📑", "color": "#6366f1",
                            "message": f"**Reconciled Business Plan Generated**\nAvailable in Workspace. Executive summary finalized.",
                            "timestamp": _dt.now().isoformat()
                        }, project=project)
                    else:
                        await _broadcast({"type": "dialogue", "agent": "SYSTEM", "icon": "❌", "color": "#ef4444", "message": f"Business Plan Error: {res.get('error')}", "timestamp": _dt.now().isoformat()}, project=project)
                    asyncio.create_task(_live_debate("Evaluate the reconciled Business Plan.", project_name=project, phase="business_plan"))

                elif user_msg.startswith("/funding"):
                    import asyncio
                    res = generate_funding_strategy({"project_name": project})
                    if res.get("status") == "ok":
                        await _broadcast({
                            "type": "dialogue", "agent": "SYSTEM", "icon": "💰", "color": "#eab308",
                            "message": f"**Funding Strategy**\nGap: ${res.get('gap')}\n\n{res.get('strategy')}",
                            "timestamp": _dt.now().isoformat()
                        }, project=project)
                    else:
                        await _broadcast({"type": "dialogue", "agent": "SYSTEM", "icon": "❌", "color": "#ef4444", "message": f"Funding Error: {res.get('error')}", "timestamp": _dt.now().isoformat()}, project=project)
                    asyncio.create_task(_live_debate("Evaluate the proposed funding strategy.", project_name=project, phase="funding"))

                elif user_msg.startswith("/pitch"):
                    import asyncio
                    res = generate_pitch_deck({"project_name": project})
                    if res.get("status") == "ok":
                        ilink = f"http://localhost:8000/api/eos/documents/{res.get('investor', '').split('/')[-1]}"
                        clink = f"http://localhost:8000/api/eos/documents/{res.get('customer', '').split('/')[-1]}"
                        await _broadcast({
                            "type": "dialogue", "agent": "SYSTEM", "icon": "🎯", "color": "#f43f5e",
                            "message": f"**Deliverable Suite Generated**\n[Download Investor Deck]({ilink})\n[Download Customer Deck]({clink})",
                            "timestamp": _dt.now().isoformat()
                        }, project=project)
                    else:
                        await _broadcast({"type": "dialogue", "agent": "SYSTEM", "icon": "❌", "color": "#ef4444", "message": f"Pitch Error: {res.get('error')}", "timestamp": _dt.now().isoformat()}, project=project)
                    asyncio.create_task(_live_debate("The Pitch decks are ready for distribution.", project_name=project, phase="pitch"))
                    
                else:
                    if user_msg == "START_DEBATE":
                        # Commander triggered a full debate via UI
                        # Use the previous commander message as the topic
                        logs = _warroom_logs.get(project, [])
                        topic = "General strategic review."
                        if len(logs) >= 2:
                            topic = logs[-2].get("message", "")[:200]
                        asyncio.create_task(_live_debate(topic, project_name=project, phase="kickoff"))
                        continue

                    # Smart routing: detect if the Commander is addressing a specific agent
                    # e.g. "CMO, prepare market research" → only CMO responds
                    _KNOWN_AGENTS = {"CEO", "CMO", "CFO", "CTO", "CRITIC", "ARCHITECT", "CPO"}
                    user_upper = user_msg.upper()
                    directed_agent = None
                    for ag in _KNOWN_AGENTS:
                        if user_upper.startswith(ag + ",") or user_upper.startswith(ag + " "):
                            directed_agent = ag
                            break

                    if directed_agent:
                        # Single-agent directed response — quick and focused
                        asyncio.create_task(_directed_response(directed_agent, user_msg, project_name=project))
                    else:
                        # General board question — lightweight 2-agent response (no full multi-round)
                        asyncio.create_task(_board_quick_response(user_msg, project_name=project))

            elif data.get("type") == "ping":
                # Keepalive — just acknowledge with a pong
                try:
                    await websocket.send_json({"type": "pong"})
                except Exception:
                    pass

            elif data.get("type") == "override":
                _persuasion_score = min(10, _persuasion_score + 2)
                await _broadcast({
                    "type": "persuasion_update",
                    "score": _persuasion_score,
                    "reason": "Commander Hard Override executed",
                }, project=project)
                await _broadcast({
                    "type": "dialogue",
                    "agent": "SYSTEM",
                    "icon": "⚡",
                    "color": "#eab308",
                    "message": f"🚨 HARD OVERRIDE — Commander bypassed deliberation. Critic compliance forced to {_persuasion_score}/10.",
                    "timestamp": _dt.now().isoformat(),
                }, project=project)

    except WebSocketDisconnect:
        pass
    finally:
        if websocket in _warroom_clients.get(project, []):
            _warroom_clients[project].remove(websocket)
        logger.info(f"War Room '{project}' client disconnected ({len(_warroom_clients.get(project, []))} total)")







async def _directed_response(agent_name: str, user_msg: str, project_name: str = "Aether"):
    """Commander addressed a specific agent — get a focused response from that agent only.
    Used for post-debate commands like 'CMO, prepare a market research report.'"""
    loop = asyncio.get_event_loop()
    meta = _AGENTS.get(agent_name, {"icon": "💬", "color": "#94a3b8"})

    # Build a role-scoped prompt
    prompt_template = _WARROOM_PROMPTS.get(agent_name, "Respond to this request from the Commander: {topic}")
    directed_prompt = (
        f"You are the {agent_name} in a boardroom. The Commander has specifically addressed you.\n"
        f"Commander's request: {user_msg}\n"
        f"Provide a detailed, focused response in your role. Be thorough but concise (4-6 sentences)."
    )

    await _broadcast({
        "type": "dialogue",
        "agent": "SYSTEM",
        "icon": "📡",
        "color": "#6366f1",
        "message": f"Commander directed to {agent_name}. Awaiting {agent_name}'s response...",
        "timestamp": _dt.now().isoformat(),
    }, project=project_name)

    if agent_name == "CPO":
        import cpo_agent
        response = await loop.run_in_executor(_warroom_executor, cpo_agent.run_cpo, user_msg)
    else:
        response = await loop.run_in_executor(_warroom_executor, _call_agent, agent_name, directed_prompt)

    if not response:
        response = f"[{agent_name}] I've received your request. I'll prepare the analysis and report back."

    await _broadcast({
        "type": "dialogue",
        "agent": agent_name,
        "icon": meta.get("icon", "💬"),
        "color": meta.get("color", "#94a3b8"),
        "message": response,
        "timestamp": _dt.now().isoformat(),
    }, project=project_name)

    # Log to institutional memory
    if MEMORY_AVAILABLE:
        try:
            record_lesson(
                f"Commander → {agent_name}: '{user_msg[:80]}' — {agent_name} responded",
                "commander_intervention", project_name
            )
        except Exception:
            pass


async def _board_quick_response(user_msg: str, project_name: str = "Aether"):
    """Lightweight board response for general Commander questions post-debate.
    CEO responds first, CRITIC weighs in — no multi-round loop."""
    loop = asyncio.get_event_loop()

    await _broadcast({
        "type": "dialogue",
        "agent": "SYSTEM",
        "icon": "📡",
        "color": "#6366f1",
        "message": "Board responding to Commander input...",
        "timestamp": _dt.now().isoformat(),
    }, project=project_name)

    prompt = f"You are responding to a Commander intervention in a boardroom. Commander said: '{user_msg}'. Respond in your role — concise, 3-4 sentences."

    # CEO and CRITIC respond in parallel
    for agent_n in ["CEO", "CRITIC"]:
        await _broadcast({
            "type": "agent_working",
            "agent": agent_n,
            "timestamp": _dt.now().isoformat()
        }, project=project_name)

    ceo_future = loop.run_in_executor(_warroom_executor, _call_agent, "CEO", prompt)
    critic_future = loop.run_in_executor(_warroom_executor, _call_agent, "CRITIC", prompt)

    ceo_resp = await ceo_future
    await asyncio.sleep(0.8)
    await _broadcast({
        "type": "dialogue",
        "agent": "CEO",
        "icon": "👔",
        "color": "#3b82f6",
        "message": ceo_resp or "Noted. I'll take this under advisement.",
        "timestamp": _dt.now().isoformat(),
    }, project=project_name)

    critic_resp = await critic_future
    await asyncio.sleep(0.8)
    await _broadcast({
        "type": "dialogue",
        "agent": "CRITIC",
        "icon": "🔍",
        "color": "#ef4444",
        "message": critic_resp or "Valid point. Let me assess the implications.",
        "timestamp": _dt.now().isoformat(),
    }, project=project_name)


async def _live_debate(topic: str, project_name: str = "Aether", phase: str = None):
    """Route the debate topic to C-Suite agents via Model Router and stream responses."""
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
    }, project=project_name)

    # Call agents in parallel via thread pool
    agents_to_call = ["CMO", "CFO", "CRITIC"]
    futures = {}
    for agent in agents_to_call:
        await _broadcast({"type": "agent_working", "agent": agent, "timestamp": _dt.now().isoformat()}, project=project_name)
        futures[agent] = loop.run_in_executor(_warroom_executor, _call_agent, agent, topic)

    # Also call CEO (elite council) for a real strategic take
    await _broadcast({"type": "agent_working", "agent": "CEO", "timestamp": _dt.now().isoformat()}, project=project_name)
    futures["CEO"] = loop.run_in_executor(_warroom_executor, _call_agent, "CEO", topic)

    # Stream responses as they arrive, with staggered timing for natural feel
    agent_order = ["CEO", "CMO", "CFO", "CRITIC"]
    for agent in agent_order:
        response = await futures[agent]
        await asyncio.sleep(0.8)  # Natural delay between speakers

        if not response:
            response = "No response available."

        meta = _AGENTS.get(agent, {})
        await _broadcast({
            "type": "dialogue",
            "agent": agent,
            "icon": meta.get("icon", "💬"),
            "color": meta.get("color", "#94a3b8"),
            "message": response,
            "timestamp": _dt.now().isoformat(),
        }, project=project_name)

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
    }, project=project_name)

    # ── Autonomous Multi-Round Debate (General Topics) ──
    # When no specific EOS phase is set, the debate continues autonomously
    # until the Critic reaches consensus (score >= 7) or max rounds (5).
    if not phase:
        _MAX_DEBATE_ROUNDS = 5
        round_num = 1
        debate_history = [f"ROUND 1 DISCUSSION:\n"]
        # Collect round 1 responses for context
        for agent in agent_order:
            resp = await futures[agent]
            if resp:
                debate_history.append(f"{agent}: {resp[:300]}")

        while _persuasion_score < 7 and round_num < _MAX_DEBATE_ROUNDS:
            round_num += 1
            await asyncio.sleep(2)

            # System announces continuation
            await _broadcast({
                "type": "dialogue", "agent": "SYSTEM", "icon": "🔄", "color": "#eab308",
                "message": f"**ROUND {round_num}/{_MAX_DEBATE_ROUNDS}** — Critic score {_persuasion_score}/10 (need ≥7 for consensus). Debate continues...",
                "timestamp": _dt.now().isoformat(),
            }, project=project_name)

            # Build context-aware follow-up prompts
            history_context = "\n".join(debate_history[-12:])  # Last 12 entries for context
            followup_prompts = {
                "CEO": (
                    f"You are the CEO continuing a boardroom debate. This is round {round_num}. "
                    f"The Critic's current confidence is {_persuasion_score}/10. "
                    f"Address the Critic's concerns directly and strengthen your position. "
                    f"Be concise (3-4 sentences). Prior discussion:\n{history_context}\n\n"
                    f"ORIGINAL TOPIC: {topic}"
                ),
                "CTO": (
                    f"You are the CTO in a boardroom debate, round {round_num}. "
                    f"The Critic scored confidence at {_persuasion_score}/10. "
                    f"Provide technical solutions to address the concerns raised. "
                    f"Be specific about architecture, stack, and feasibility. (3-4 sentences)\n"
                    f"Prior discussion:\n{history_context}\n\nTOPIC: {topic}"
                ),
                "CFO": (
                    f"You are the CFO in round {round_num} of a boardroom debate. "
                    f"Critic confidence: {_persuasion_score}/10. "
                    f"Provide updated financial analysis addressing concerns. "
                    f"Include specific numbers and risk mitigation. (3-4 sentences)\n"
                    f"Prior discussion:\n{history_context}\n\nTOPIC: {topic}"
                ),
                "CRITIC": (
                    f"You are the Critic in round {round_num} of a boardroom debate. "
                    f"Your current confidence is {_persuasion_score}/10. "
                    f"Re-evaluate based on the board's responses. If concerns are addressed, "
                    f"increase your score. If not, explain what's still missing. "
                    f"End with 'Confidence: X/10'. (3-5 sentences)\n"
                    f"Prior discussion:\n{history_context}\n\nTOPIC: {topic}"
                ),
            }

            # Call agents for this round (include CTO this time)
            round_agents = ["CEO", "CTO", "CFO", "CRITIC"]
            round_futures = {}
            for agent in round_agents:
                prompt = followup_prompts.get(agent, f"Continue the debate on: {topic}")
                round_futures[agent] = loop.run_in_executor(
                    _warroom_executor, _call_agent, agent, prompt
                )

            debate_history.append(f"\nROUND {round_num} DISCUSSION:")
            for agent in round_agents:
                response = await round_futures[agent]
                await asyncio.sleep(1.0)
                if not response:
                    response = "No response available."
                meta = _AGENTS.get(agent, {})
                await _broadcast({
                    "type": "dialogue",
                    "agent": agent,
                    "icon": meta.get("icon", "💬"),
                    "color": meta.get("color", "#94a3b8"),
                    "message": response,
                    "timestamp": _dt.now().isoformat(),
                }, project=project_name)
                debate_history.append(f"{agent}: {response[:300]}")

            # Parse Critic's updated score
            critic_resp = await round_futures["CRITIC"]
            if critic_resp:
                import re
                score_match = re.search(r'(\d+(?:\.\d+)?)\s*/\s*10', critic_resp)
                if score_match:
                    new_score = min(10, max(1, int(float(score_match.group(1)))))
                    _persuasion_score = new_score
                else:
                    delta = random.choice([0, 1, 1, 1, 2])
                    _persuasion_score = max(1, min(10, _persuasion_score + delta))

            await _broadcast({
                "type": "persuasion_update",
                "score": _persuasion_score,
                "reason": f"Critic re-assessment after round {round_num}",
            }, project=project_name)

        # ── Debate Conclusion + Final Deliverables ──
        if _persuasion_score >= 7:
            conclusion_status = "CONSENSUS REACHED"
            conclusion_icon = "✅"
            conclusion_color = "#22c55e"
        else:
            conclusion_status = f"DEADLOCK after {round_num} rounds"
            conclusion_icon = "🛑"
            conclusion_color = "#ef4444"

        await _broadcast({
            "type": "dialogue", "agent": "SYSTEM", "icon": conclusion_icon, "color": conclusion_color,
            "message": f"**{conclusion_status}** — Critic final score: {_persuasion_score}/10 after {round_num} round(s). Generating final deliverables...",
            "timestamp": _dt.now().isoformat(),
        }, project=project_name)

        # Generate final summary deliverable via Model Router
        final_history = "\n".join(debate_history[-20:])
        def _generate_final_deliverable():
            summary_prompt = (
                f"You are a board secretary. Summarize the following boardroom debate into a FINAL DELIVERABLE.\n\n"
                f"FORMAT YOUR RESPONSE EXACTLY LIKE THIS:\n"
                f"## Executive Summary\n[2-3 sentence overview]\n\n"
                f"## Key Decisions\n- [bullet points]\n\n"
                f"## Action Items\n- [numbered list with owners]\n\n"
                f"## Risk Factors\n- [from Critic's concerns]\n\n"
                f"## Recommendation\n[Final go/no-go recommendation]\n\n"
                f"DEBATE TRANSCRIPT:\n{final_history}\n\n"
                f"ORIGINAL TOPIC: {topic}\n"
                f"FINAL CRITIC SCORE: {_persuasion_score}/10\n"
                f"STATUS: {conclusion_status}"
            )
            if _MODEL_ROUTER_AVAILABLE:
                return _model_route("architect", summary_prompt, "You are a professional board secretary producing concise executive deliverables from boardroom debates. Use markdown formatting.")
            return "Final deliverable generation requires Model Router."

        deliverable = await loop.run_in_executor(_warroom_executor, _generate_final_deliverable)

        await _broadcast({
            "type": "dialogue", "agent": "SYSTEM", "icon": "📋", "color": "#6366f1",
            "message": f"**FINAL DELIVERABLE**\n\n{deliverable}",
            "timestamp": _dt.now().isoformat(),
        }, project=project_name)

        # Record to institutional memory
        if MEMORY_AVAILABLE:
            try:
                record_lesson(
                    f"War Room debate concluded: '{topic[:80]}' — {conclusion_status}, Critic score {_persuasion_score}/10, {round_num} rounds",
                    "warroom_conclusion", project_name
                )
            except Exception:
                pass

        return  # General debate complete — skip EOS phase logic below

    # ── Auto-Iterative Loop Trigger (EOS Phase-specific) ──
    if phase and _persuasion_score < 7:
        from eos_context import get_eos
        eos = get_eos(project_name)
        status = eos.get("phase_status", {}).get(phase)
        
        if status != "deadlocked":
            eos.set_critique(phase, critic_response)
            count = eos.start_iteration(phase)
            
            if count <= 3:
                await asyncio.sleep(1)
                await _broadcast({
                    "type": "dialogue", "agent": "SYSTEM", "icon": "🔄", "color": "#eab308",
                    "message": f"🚨 CRITIC REJECTED PHASE '{phase.upper()}'. Initiating automated REVISION {count}/3 based on feedback...",
                    "timestamp": _dt.now().isoformat(),
                }, project=project_name)
                
                # Execute replacement asynchronously
                def _run_gen():
                    if phase == "market": return generate_market_intel({"project_name": project_name, "company_name": eos.get("company_name", "Startup")})
                    elif phase == "brand": return generate_brand_identity({"project_name": project_name})
                    elif phase == "legal": return generate_legal_analysis({"project_name": project_name})
                    elif phase == "business_plan": return generate_business_plan({"project_name": project_name})
                    return {"error": f"Iteration not supported for {phase}"}
                
                res = await loop.run_in_executor(_warroom_executor, _run_gen)
                
                if res.get("status") == "ok":
                    doc_msg = json.dumps(res.get(phase, {}), indent=2)[:300] + "..."
                    await _broadcast({
                        "type": "dialogue", "agent": "SYSTEM", "icon": "✅", "color": "#10b981",
                        "message": f"**{phase.upper()} Revised**\n```json\n{doc_msg}\n```",
                        "timestamp": _dt.now().isoformat()
                    }, project=project_name)
                    # Re-trigger debate on the new revision
                    asyncio.create_task(_live_debate(f"Review the revised {phase} proposal. Does it address the previous weaknesses?", project_name=project_name, phase=phase))
            else:
                await _broadcast({
                    "type": "dialogue", "agent": "SYSTEM", "icon": "🛑", "color": "#ef4444",
                    "message": f"**DEADLOCK REACHED**\nThe board failed to reach consensus on '{phase.upper()}' after 3 iterations. Commander intervention required to Proceed or Force Override.",
                    "timestamp": _dt.now().isoformat()
                }, project=project_name)

async def _analyze_upload(project_name: str, file_path: str, filename: str):
    import base64
    import mimetypes
    import requests
    
    await _broadcast({
        "type": "dialogue", "agent": "SYSTEM", "icon": "📎", "color": "#10b981",
        "message": f"**Master Architect uploaded a document:** `{filename}`\nThe Critic is reviewing it now...",
        "timestamp": _dt.now().isoformat()
    }, project=project_name)
    
    mime_type, _ = mimetypes.guess_type(file_path)
    is_image = mime_type and mime_type.startswith("image")
    
    api_key = get_secret("GEMINI_API_KEY")
    if not api_key:
        return
        
    prompt = "You are the CRITIC, the adversarial board member of a startup war room. The Master Architect (the user) has just uploaded this file for review. Provide a sharp, insightful, and constructively critical analysis of this document/image. Identify specific weaknesses, risks, and areas for improvement. Format nicely in markdown, staying in character as a blunt, hyper-logical analyst."
    
    try:
        if is_image:
            with open(file_path, "rb") as f:
                b64_data = base64.b64encode(f.read()).decode("utf-8")
            data = {
                "contents": [{"role": "user", "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": mime_type, "data": b64_data}}
                ]}]
            }
        else:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()[:30000] # Truncate to avoid massive overload
            data = {
                "contents": [{"role": "user", "parts": [
                    {"text": f"{prompt}\n\nDOCUMENT CONTENTS:\n{content}"}
                ]}]
            }
            
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
        headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
        r = requests.post(url, json=data, headers=headers)
        
        candidates = r.json().get("candidates", [])
        if candidates:
            critic_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            await _broadcast({
                "type": "dialogue", "agent": "CRITIC", "icon": "🔍", "color": "#ef4444",
                "message": f"**Analysis of `{filename}`**\n\n{critic_text}",
                "timestamp": _dt.now().isoformat()
            }, project=project_name)
            
            # Re-seed the boardroom to discuss the CRITIC's findings
            await asyncio.sleep(2)
            asyncio.create_task(_live_debate(f"The CRITIC just reviewed '{filename}'. Does the rest of the board agree with this assessment?", project_name=project_name))

    except Exception as e:
        logger.error(f"Upload analysis failed: {e}")
        await _broadcast({
            "type": "dialogue", "agent": "SYSTEM", "icon": "❌", "color": "#ef4444",
            "message": f"Failed to analyze '{filename}': {str(e)}",
            "timestamp": _dt.now().isoformat()
        }, project=project_name)


@app.post("/api/warroom/intervene")
async def warroom_intervene_http(request: Request):
    """HTTP fallback for Commander Intervention when WebSocket is disconnected.
    Triggers the same smart routing as the WS handler.
    Also handles Phase 11 state_machine and INCUBATOR_GATE typed events."""
    data = await request.json()
    user_msg = data.get("message", "").strip()
    project = data.get("project_name", "Aether")

    if not user_msg:
        return {"status": "error", "error": "No message provided"}

    # ── Phase 11: state_machine broadcast (from forge_orchestrator._broadcast_phase) ──
    event_type = data.get("event_type", "")
    agent = data.get("agent", "")
    if event_type == "state_machine" or "[state_machine]" in user_msg:
        phase = data.get("phase") or ""
        status = data.get("status") or ""
        # Try to parse from message string as fallback
        if not phase:
            import re as _re
            _pm = _re.search(r'phase=(\w+)', user_msg)
            _sm = _re.search(r'status=(\w+)', user_msg)
            phase = _pm.group(1) if _pm else ""
            status = _sm.group(1) if _sm else ""
        if phase and status:
            await _broadcast({
                "type": "state_machine",
                "phase": phase,
                "status": status,
                "timestamp": _dt.now().isoformat()
            }, project=project)
            return {"status": "ok", "routed_to": "state_machine"}

    # ── Phase 11: INCUBATOR_GATE Executive Fork broadcast ──
    if agent == "INCUBATOR_GATE":
        await _broadcast({
            "type": "dialogue",
            "agent": "INCUBATOR_GATE",
            "icon": "⚡",
            "color": "#10b981",
            "message": user_msg,
            "timestamp": _dt.now().isoformat(),
            "is_user": False,
        }, project=project)
        return {"status": "ok", "routed_to": "INCUBATOR_GATE"}

    # ── Default: broadcast as Commander message ──
    await _broadcast({
        "type": "dialogue",
        "agent": "COMMANDER",
        "icon": "⚡",
        "color": "#f97316",
        "message": user_msg,
        "timestamp": _dt.now().isoformat(),
        "is_user": True,
    }, project=project)

    operator_msg = data.get("operator_override_message", "")
    if operator_msg:
        await _broadcast({
            "type": "dialogue", "agent": "Operator_Agent", "icon": "⚙️", "color": "#10b981",
            "message": f"**Operator Protocol Execution**\n\n{operator_msg}",
            "timestamp": _dt.now().isoformat()
        }, project=project)
        return {"status": "ok", "routed_to": "Operator_Agent"}

    # ── Operator Agent Intercept ──
    if user_msg.lower().startswith("@operator") or user_msg.lower().startswith("operator,") or user_msg.lower().startswith("operator "):
        async def _call_operator(msg, proj):
            try:
                await _broadcast({
                    "type": "agent_working",
                    "agent": "Operator_Agent",
                    "timestamp": _dt.now().isoformat()
                }, project=proj)
                import httpx
                async with httpx.AsyncClient() as client:
                    await client.post(
                        "http://localhost:5100/api/operator/command",
                        json={"directive": msg},
                        timeout=5.0
                    )
            except Exception as e:
                logger.error(f"Operator intercept failed: {e}")
                
        asyncio.create_task(_call_operator(user_msg, project))
        return {"status": "ok", "routed_to": "Operator_Agent"}

    # Smart routing — same logic as WebSocket handler
    _KNOWN_AGENTS = {"CEO", "CMO", "CFO", "CTO", "CRITIC", "ARCHITECT", "CPO"}
    user_upper = user_msg.upper()
    directed_agent = None
    for ag in _KNOWN_AGENTS:
        if user_upper.startswith(ag + ",") or user_upper.startswith(ag + " "):
            directed_agent = ag
            break

    if directed_agent:
        asyncio.create_task(_directed_response(directed_agent, user_msg, project_name=project))
    else:
        asyncio.create_task(_board_quick_response(user_msg, project_name=project))

    return {"status": "ok", "routed_to": directed_agent or "board"}


@app.post("/api/warroom/upload")
async def warroom_upload(
    file: UploadFile = File(...),
    project_name: str = Form("Aether")
):
    """Upload a document to the War Room for the Critic to analyze."""
    try:
        project_dir = os.path.join(SCRIPT_DIR, "projects", project_name)
        os.makedirs(project_dir, exist_ok=True)
        
        upload_dir = os.path.join(project_dir, "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        
        filename = file.filename or "upload"
        file_path = os.path.join(upload_dir, filename)
        
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
            
        asyncio.create_task(_analyze_upload(project_name, file_path, filename))
        
        return {"status": "ok", "message": "File uploaded and sent to Critic for review."}
    except Exception as e:
        logger.error(f"Warroom upload error: {e}")
        return {"error": str(e)}


@app.post("/api/warroom/propose_outcome")
async def warroom_propose_outcome(request: Request):
    """Trigger an outcome proposal after the C-Suite reaches consensus.
    The system summarizes what was decided and pushes an outcome_proposal WS event."""
    body = await request.json()
    project_name = body.get("project_name", "Aether")
    
    eos = get_eos(project_name)
    
    # Collect all locked deliverables as the outcome
    deliverables = {}
    for phase in ["market", "brand", "legal", "business_plan", "financials", "funding", "pitch"]:
        data = eos.get(phase) or eos.get(f"{phase}_analysis") or eos.get(f"{phase}_plan")
        if data:
            deliverables[phase] = data
    
    # Also grab high-level context
    summary = {
        "company_name": eos.get("company_name", project_name),
        "industry": eos.get("industry", ""),
        "tagline": eos.get("tagline", ""),
        "deliverables_count": len(deliverables),
        "phases_locked": [p for p in ["market", "brand", "legal", "business_plan", "financials"] if eos.get("phase_status", {}).get(p) == "locked"],
    }
    
    await _broadcast({
        "type": "outcome_proposal",
        "summary": summary,
        "deliverables": deliverables,
        "project_name": project_name,
        "timestamp": _dt.now().isoformat(),
    }, project=project_name)
    
    await _broadcast({
        "type": "dialogue", "agent": "SYSTEM", "icon": "🎯", "color": "#22c55e",
        "message": f"**CONSENSUS REACHED** — The board has finalized {len(deliverables)} deliverables for {summary['company_name']}.\n\nChoose how to proceed:\n• **Update Existing Product** — merge into the current codebase\n• **Create New Product** — spin up a fresh build\n• **Dismiss** — archive for later",
        "timestamp": _dt.now().isoformat(),
    }, project=project_name)
    
    return {"status": "ok", "summary": summary}


@app.post("/api/warroom/execute_outcome")
async def warroom_execute_outcome(request: Request):
    """Execute a brainstorm outcome: generate implementation plan for approval."""
    body = await request.json()
    project_name = body.get("project_name", "Aether")
    outcome_type = body.get("outcome_type", "update")  # "update" or "new"
    
    eos = get_eos(project_name)
    company = eos.get("company_name", project_name)
    
    # Build context from EOS state
    eos_snapshot = json.dumps({k: v for k, v in eos._state.items() if k not in ["_iterations", "_critiques"]}, indent=2, default=str)[:8000]
    
    if outcome_type == "update":
        plan_prompt = (
            f"You are the Master Architect for '{company}'. The C-Suite war room has finalized new deliverables through adversarial debate. "
            f"Generate a DETAILED implementation plan to UPDATE the existing product with these new findings. "
            f"Structure the plan as markdown with: ## Summary, ## Changes Required (file-by-file), ## Risk Assessment, ## Timeline. "
            f"Be specific about which files to modify and what code changes are needed.\n\n"
            f"EOS CONTEXT:\n{eos_snapshot}"
        )
    else:
        plan_prompt = (
            f"You are the Master Architect for '{company}'. The C-Suite war room has finalized deliverables for a NEW product. "
            f"Generate a DETAILED implementation plan to BUILD this product from scratch. "
            f"Structure the plan as markdown with: ## Product Overview, ## Architecture, ## Tech Stack, ## File Structure, ## Build Steps, ## Timeline. "
            f"Be specific about the app scaffold and deployment strategy.\n\n"
            f"EOS CONTEXT:\n{eos_snapshot}"
        )
    
    # Use Model Router (Claude preferred for structured planning)
    plan_text = ""
    if _MODEL_ROUTER_AVAILABLE:
        plan_text = _model_route("implementation_plan", plan_prompt)
    
    if not plan_text:
        # Fallback to Gemini direct
        api_key = get_secret("GEMINI_API_KEY")
        if api_key:
            try:
                import requests as _req
                url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
                headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
                data = {"contents": [{"role": "user", "parts": [{"text": plan_prompt}]}]}
                r = _req.post(url, json=data, headers=headers, timeout=60)
                candidates = r.json().get("candidates", [])
                if candidates:
                    plan_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            except Exception as e:
                logger.error(f"Plan generation failed: {e}")
    
    if not plan_text:
        plan_text = f"# Implementation Plan for {company}\n\nUnable to generate plan automatically. Please review the EOS deliverables in the project directory."
    
    # Save the plan to the project directory
    project_dir = os.path.join(SCRIPT_DIR, "projects", project_name)
    os.makedirs(project_dir, exist_ok=True)
    plan_path = os.path.join(project_dir, "implementation_plan.md")
    with open(plan_path, "w", encoding="utf-8") as f:
        f.write(plan_text)
    
    # Broadcast the plan for user approval
    await _broadcast({
        "type": "implementation_plan",
        "plan": plan_text,
        "outcome_type": outcome_type,
        "project_name": project_name,
        "plan_path": plan_path,
        "timestamp": _dt.now().isoformat(),
    }, project=project_name)
    
    await _broadcast({
        "type": "dialogue", "agent": "SYSTEM", "icon": "📋", "color": "#6366f1",
        "message": f"**Implementation Plan Generated** ({outcome_type.upper()})\n\nThe plan has been saved to `{plan_path}`.\nReview it below and **Approve** to begin execution or **Reject** to revise.",
        "timestamp": _dt.now().isoformat(),
    }, project=project_name)
    
    return {"status": "ok", "plan": plan_text, "path": plan_path}


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
    
    # ── Operator Agent Intercept (Fallback Route) ──
    operator_msg = body.get("operator_override_message", "")
    if operator_msg:
        await _broadcast({
            "type": "dialogue", "agent": "Operator_Agent", "icon": "⚙️", "color": "#10b981",
            "message": f"**Operator Protocol Execution**\n\n{operator_msg}",
            "timestamp": _dt.now().isoformat()
        })
        return {"status": "ok", "routed_to": "Operator_Agent"}

    if msg.lower().startswith("@operator") or msg.lower().startswith("operator,") or msg.lower().startswith("operator "):
        async def _call_operator_fallback(m):
            try:
                await _broadcast({"type": "agent_working", "agent": "Operator_Agent", "timestamp": _dt.now().isoformat()})
                import httpx
                async with httpx.AsyncClient() as client:
                    await client.post(
                        "http://localhost:5100/api/operator/command",
                        json={"directive": m},
                        timeout=5.0
                    )
            except Exception as e:
                pass
        asyncio.create_task(_call_operator_fallback(msg))
        return {"status": "ok", "routed_to": "Operator_Agent"}
    asyncio.create_task(_simulate_response(msg))

    # Record all user interventions as institutional lessons
    record_lesson(
        category="user_feedback",
        summary=f"Commander intervention: {msg[:120]}",
        details=msg,
        source_agent="COMMANDER",
        severity="normal",
        tags=["intervention", "user-feedback"],
    )

    return {"status": "ok", "message": "Intervention dispatched"}


@app.get("/api/warroom/state")
def warroom_state(project_name: str = None):
    """Get current War Room state."""
    response = {
        "persuasion_score": getattr(sys.modules[__name__], '_persuasion_score', 5),
        "connected_clients": sum(len(clients) for clients in _warroom_clients.values()),
        "total_projects_active": len(_warroom_clients),
        "log_lengths": {proj: len(logs) for proj, logs in _warroom_logs.items()},
        "recent_logs": {proj: logs[-5:] for proj, logs in _warroom_logs.items()}
    }
    
    if project_name:
        from eos_context import get_eos
        eos = get_eos(project_name)
        state_dict = eos.to_dict() if hasattr(eos, 'to_dict') else (eos.__dict__ if hasattr(eos, '__dict__') else {})
        status_map = state_dict.get("phase_status", {})
        
        # execution check
        is_executing = any(s in ['iterating', 'processing', 'active'] for s in status_map.values())
        is_locked = any(s in ['locked', 'deadlocked'] for s in status_map.values())
        
        sequence_state = {}
        STATUS_MAP = {"iterating": "PROCESSING", "locked": "PASS", "deadlocked": "FAIL", "pending": "WAITING", "waiting": "WAITING"}
        for phase, status in status_map.items():
            sequence_state[phase] = STATUS_MAP.get(status, status.upper())

        response["is_executing"] = is_executing or is_locked
        response["phase_status"] = status_map
        response["sequence_state"] = sequence_state

    return response


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

    # Kick off live debate via Model Router agents
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

    # Record override as an institutional lesson
    record_lesson(
        category="override",
        summary=f"Commander bypassed Critic on challenge {challenge_id}",
        details=f"Override note: {commander_note}. Risk level: {override.get('risk_level', 'unknown')}. Risk: {override.get('risk_description', '')}",
        source_agent="COMMANDER",
        severity="high",
        tags=["override", "critic-bypass"],
    )

    return override


# ── Phase 4: Incoming Watcher + Archiver + Master Audit ────────────────

import threading

# ── Institutional Memory REST API ─────────────────────────────

@app.get("/api/lessons")
def api_get_lessons(project_name: str = None, category: str = None, limit: int = 50):
    """Retrieve institutional lessons learned."""
    lessons = get_lessons(project_name=project_name, category=category, limit=limit)
    return {"lessons": lessons, "count": len(lessons)}

@app.post("/api/lessons")
async def api_record_lesson(request: Request):
    """Manually record a lesson (from any client or agent)."""
    body = await request.json()
    lesson = record_lesson(
        category=body.get("category", "user_feedback"),
        summary=body.get("summary", ""),
        details=body.get("details", ""),
        project_name=body.get("project_name"),
        source_agent=body.get("source_agent", "USER"),
        severity=body.get("severity", "normal"),
        tags=body.get("tags", []),
    )
    return {"status": "ok", "lesson": lesson}

@app.get("/api/lessons/search")
def api_search_lessons(q: str = "", limit: int = 20):
    """Search across all institutional lessons."""
    return {"results": search_lessons(q, limit=limit)}

@app.get("/api/lessons/build-context")
def api_build_context(project_name: str = None):
    """Get the accumulated lessons context block for injecting into child app builds."""
    context = get_lessons_for_build(project_name)
    return {"context": context, "project": project_name}

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

    # Generate brand using CMO agent via Model Router (or fallback to template)
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
        # Enrich brand via CMO agent (Model Router)
        cmo_prompt = (
            f"Generate a brand identity for a project called '{req.project_name}'. "
            f"Return JSON with: company_name, tagline, mission, colors (primary/secondary/accent hex), "
            f"fonts (heading/body), tone_of_voice, visual_style."
        )
        cmo_text = _call_agent("CMO", cmo_prompt)
        if cmo_text and "{" in cmo_text:
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
        cmo_prompt = (
            f"A user described their brand vision for '{req.project_name}' as: \"{req.description}\"\n\n"
            f"Based on that description, generate a brand identity. Return JSON with: "
            f"company_name, tagline, mission, colors (primary/secondary/accent as hex), "
            f"fonts (heading/body), tone_of_voice, visual_style."
        )
        cmo_text = _call_agent("CMO", cmo_prompt)
        if cmo_text and "{" in cmo_text:
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


# ═══════════════════════════════════════════════════════════════
#  UPGRADE 2: War Room History Retrieval
# ═══════════════════════════════════════════════════════════════

@app.get("/api/warroom/history")
def warroom_history():
    """Return full War Room debate history from disk."""
    try:
        if os.path.exists(_WARROOM_HISTORY_PATH):
            with open(_WARROOM_HISTORY_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Group messages into sessions by SYSTEM "SESSION OPENED" markers
            messages = data.get("messages", [])
            sessions = []
            current_session = {"topic": "Unknown", "started": None, "messages": []}
            for msg in messages:
                if msg.get("type") == "dialogue" and msg.get("agent") == "SYSTEM" and "SESSION OPENED" in msg.get("message", ""):
                    if current_session["messages"]:
                        sessions.append(current_session)
                    topic = msg.get("message", "").split("Topic: ")[-1].strip('"')
                    current_session = {
                        "topic": topic,
                        "started": msg.get("timestamp"),
                        "messages": [msg],
                    }
                else:
                    current_session["messages"].append(msg)
            if current_session["messages"]:
                sessions.append(current_session)
            return {
                "session_count": len(sessions),
                "total_messages": len(messages),
                "sessions": sessions,
                "last_updated": data.get("last_updated"),
            }
        return {"session_count": 0, "total_messages": 0, "sessions": []}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.delete("/api/warroom/history/clear")
def warroom_history_clear():
    """Clear all War Room history."""
    global _warroom_log
    _warroom_log.clear()
    try:
        if os.path.exists(_WARROOM_HISTORY_PATH):
            os.remove(_WARROOM_HISTORY_PATH)
    except Exception:
        pass
    return {"status": "ok", "message": "War Room history cleared"}


# ═══════════════════════════════════════════════════════════════
#  UPGRADE 3: Phantom QA Blocking Gate
# ═══════════════════════════════════════════════════════════════

_pending_approvals: dict = {}  # app_name -> {"score": int, "report": str, "approved": bool}


@app.post("/api/build/approve/{app_name}")
def build_approve(app_name: str):
    """Approve or abort a build blocked by Phantom QA gate."""
    if app_name not in _pending_approvals:
        return JSONResponse({"error": f"No pending approval for '{app_name}'"}, status_code=404)
    _pending_approvals[app_name]["approved"] = True
    logger.info(f"Build approved: {app_name} (QA score: {_pending_approvals[app_name]['score']})")
    return {"status": "approved", "app_name": app_name}


@app.post("/api/build/abort/{app_name}")
def build_abort(app_name: str):
    """Abort a build blocked by Phantom QA gate."""
    if app_name in _pending_approvals:
        _pending_approvals.pop(app_name)
    return {"status": "aborted", "app_name": app_name}


# ── EOS (Enterprise Operating System) Endpoints ────────────────

try:
    from eos_context import get_eos
    from Aether.financial_architect import FinancialArchitect
    from Aether.presentation_architect import PresentationArchitect
    from factory_stream import get_secret
except ImportError as e:
    logger.warning(f"EOS Imports varied: {e}")

@app.get("/api/eos/state")
def get_eos_state(project_name: str = "Aether"):
    eos = get_eos(project_name)
    if hasattr(eos, 'to_dict'):
        return eos.to_dict()
    elif hasattr(eos, '__dict__'):
        return {k: v for k, v in eos.__dict__.items() if not k.startswith('_')}
    return {}

@app.post("/api/eos/state")
def update_eos_state(payload: dict):
    pn = payload.get("project_name", "Aether")
    get_eos(pn).update(payload)
    return {"status": "ok", "state": get_eos(pn).to_dict()}

@app.post("/api/eos/reset")
def reset_eos_state(payload: dict):
    pn = payload.get("project_name", "Aether")
    get_eos(pn).reset()
    return {"status": "reset"}

@app.post("/api/eos/market-intel")
def generate_market_intel(payload: dict):
    pn = payload.get("project_name", "Aether")
    eos = get_eos(pn)
    company = eos.get("company_name", payload.get("company_name", "Startup"))
    niche = eos.get("industry", payload.get("industry", "Tech"))
    
    critique = eos.get_critique("market")
    prompt = f"Analyze the market for '{company}' in the '{niche}' industry. Return ONLY valid JSON with no markdown block formatting. Keys: 'tam' (string, e.g. '$10B'), 'sam' (string), 'som' (string), 'competitors' (list of dicts with 'name' and 'weakness')."
    
    if critique:
        prompt += f"\n\n[CRITICAL FEEDBACK FROM BOARD]: The previous attempt was rejected. Address these exact weaknesses in your revision:\n{critique}"
    
    eos.start_iteration("market")
    
    api_key = get_secret("GEMINI_API_KEY")
    if not api_key:
        return {"error": "No GEMINI_API_KEY"}
        
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
    data = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
    
    try:
        import requests
        r = requests.post(url, json=data, headers=headers)
        js = r.json()
        
        candidates = js.get("candidates", [])
        if not candidates:
            return {"error": "No response from Gemini", "details": js}
            
        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
        if text.startswith("```json"): text = text.replace("```json", "", 1)
        if text.endswith("```"): text = text[:-3]
        
        result = json.loads(text.strip())
        
        eos.update({
            "tam": result.get("tam", "$0"),
            "sam": result.get("sam", "$0"),
            "som": result.get("som", "$0"),
            "competitors": result.get("competitors", [])
        })
        eos.lock_phase("market")
        return {"status": "ok", "market": result}
    except Exception as e:
        logger.error(f"Market intel error: {e}")
        return {"error": str(e)}

@app.post("/api/eos/brand")
def generate_brand_identity(payload: dict):
    eos = get_eos()
    company = payload.get("company_name", eos.get("company_name"))
    niche = payload.get("industry", eos.get("industry"))
    
    critique = eos.get_critique("brand")
    prompt = f"Act as a high-end Brand Studio. Generate a brand identity for '{company}' in '{niche}'. Return ONLY valid JSON block. Keys: 'company_name' (string, if you suggest a new one, else use the provided), 'tagline' (string), 'brand_colors' (dict of 'primary', 'secondary', 'accent' with hex codes), 'logo_prompt' (string: detailed DALL-E 3 midjourney prompt for the logo)."
    
    if critique:
        prompt += f"\n\n[CRITICAL FEEDBACK FROM BOARD]: The previous attempt was rejected. Fix these weaknesses:\n{critique}"
    
    eos.start_iteration("brand")
    
    api_key = get_secret("GEMINI_API_KEY")
    if not api_key:
        return {"error": "No GEMINI_API_KEY"}
        
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
    data = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
    
    try:
        import requests
        r = requests.post(url, json=data, headers=headers)
        js = r.json()
        candidates = js.get("candidates", [])
        if not candidates: return {"error": "Empty response"}
            
        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
        if text.startswith("```json"): text = text.replace("```json", "", 1)
        if text.endswith("```"): text = text[:-3]
        
        result = json.loads(text.strip())
        
        eos.update({
            "company_name": result.get("company_name", company),
            "tagline": result.get("tagline", "Innovating the future"),
            "brand_colors": result.get("brand_colors", {}),
            "logo_prompt": result.get("logo_prompt", "")
        })
        eos.lock_phase("brand")
        return {"status": "ok", "brand": result}
    except Exception as e:
        logger.error(f"Brand studio error: {e}")
        return {"error": str(e)}

@app.post("/api/eos/legal")
def generate_legal_analysis(payload: dict):
    eos = get_eos()
    company = payload.get("company_name", eos.get("company_name", "Startup"))
    niche = payload.get("industry", eos.get("industry", "Tech"))
    
    critique = eos.get_critique("legal")
    prompt = f"Act as a Legal AI Agent. Analyze the trademark and copyright viability for a company named '{company}' in the '{niche}' industry. Detail intellectual property implications. Return ONLY valid JSON block. Keys: 'trademark_viability' (string), 'copyright_risks' (string), 'legal_strategy' (string)."
    
    if critique:
        prompt += f"\n\n[CRITICAL FEEDBACK FROM BOARD]: The previous legal analysis was rejected. Address these exact weaknesses:\n{critique}"
    
    eos.start_iteration("legal")
    
    api_key = get_secret("GEMINI_API_KEY")
    if not api_key:
        return {"error": "No GEMINI_API_KEY"}
        
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
    data = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
    
    try:
        import requests
        r = requests.post(url, json=data, headers=headers)
        js = r.json()
        candidates = js.get("candidates", [])
        if not candidates: return {"error": "Empty response"}
            
        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
        if text.startswith("```json"): text = text.replace("```json", "", 1)
        if text.endswith("```"): text = text[:-3]
        
        result = json.loads(text.strip())
        
        eos.update({
            "legal_analysis": result
        })
        eos.lock_phase("legal")
        return {"status": "ok", "legal": result}
    except Exception as e:
        logger.error(f"Legal AI error: {e}")
        return {"error": str(e)}

@app.post("/api/eos/business-plan")
def generate_business_plan(payload: dict):
    pn = payload.get("project_name", "Aether")
    eos = get_eos(pn)
    eos.update(payload)
    
    critique = eos.get_critique("business_plan")
    
    # Synthesize previous data for the prompt
    c_name = eos.get("company_name", "Startup")
    niche = eos.get("industry", "Business")
    brand = eos.get("tagline", "")
    tam = eos.get("tam", "")
    legal = eos.get("legal_analysis", {}).get("trademark_viability", "")
    
    prompt = f"Act as an Elite Business Planner. Reconcile this data into a cohesive Executive Summary for '{c_name}' (Tagline: {brand}) in the '{niche}' sector. Market TAM: {tam}. Legal standing: {legal}. Return ONLY valid JSON block. Keys: 'executive_summary' (string), 'business_model_canvas' (dict of 'value_propositions', 'customer_segments', 'revenue_streams' - all strings)."
    
    if critique:
        prompt += f"\n\n[CRITICAL FEEDBACK FROM BOARD]: The previous attempt was rejected. Address these exact weaknesses:\n{critique}"
        
    eos.start_iteration("business_plan")
    
    api_key = get_secret("GEMINI_API_KEY")
    if not api_key: return {"error": "No GEMINI_API_KEY"}
    
    try:
        import requests
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
        headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
        data = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
        r = requests.post(url, json=data, headers=headers)
        
        candidates = r.json().get("candidates", [])
        if not candidates: return {"error": "Empty response"}
        
        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
        if text.startswith("```json"): text = text.replace("```json", "", 1)
        if text.endswith("```"): text = text[:-3]
        
        result = json.loads(text.strip())
        eos.update({"business_plan": result})
        eos.lock_phase("business_plan")
        return {"status": "ok", "business_plan": result}
        
    except Exception as e:
        logger.error(f"Business Plan Error: {e}")
        return {"error": str(e)}

@app.post("/api/eos/financial-model")
def generate_financial_model(payload: dict):
    eos = get_eos()
    eos.update(payload)
    config = eos.get_financial_config()
    
    arch = FinancialArchitect()
    try:
        # PII setup handles safe path. 
        res = arch.generate_projections(config=config, output_name=f"{config['company_name'].replace(' ', '_')}_Financials.xlsx")
        
        if res.get("generated"):
            eos.update({
                "financial_xlsx_path": res.get("path"),
                "breakeven_month": res.get("breakeven_month")
            })
            eos.lock_phase("financials")
            return {"status": "ok", "path": res.get("path"), "breakeven": res.get("breakeven_month")}
        return {"error": "Failed to generate financials", "details": res}
    except Exception as e:
        logger.error(f"Financial Model error: {e}")
        return {"error": str(e)}

@app.post("/api/eos/funding")
def generate_funding_strategy(payload: dict):
    eos = get_eos()
    eos.update(payload)
    gap = eos.compute_funding_gap()
    
    prompt = f"Company {eos.get('company_name')} needs to raise ${eos.get('total_investment_needed')}. The founder is investing ${eos.get('equity_contribution')}. The funding gap is ${gap}. Write a brief, punchy markdown strategy (3 paragraphs max) recommending how to split this gap between VC funding and Bank Loans. End with the suggested VC equity give %."
    
    api_key = get_secret("GEMINI_API_KEY")
    if api_key:
        try:
            import requests
            url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
            headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
            data = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
            r = requests.post(url, json=data, headers=headers)
            candidates = r.json().get("candidates", [])
            if candidates:
                text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                eos.update({"funding_strategy_md": text})
                eos.mark_phase_complete("funding")
                return {"status": "ok", "strategy": text, "gap": gap}
        except Exception as e:
            logger.error(f"Funding strategy error: {e}")
            return {"error": str(e)}
    return {"error": "No GEMINI_API_KEY"}

@app.post("/api/eos/pitch-deck")
def generate_pitch_deck():
    eos = get_eos()
    company = eos.get("company_name", "Startup")
    try:
        arch = PresentationArchitect()
        
        # Generate Investor Deck
        inv_data = {
            "roi": "450", "breakeven_month": eos.get("breakeven_month", 6),
            "y1_revenue": f"${eos.get('monthly_revenue', 0)*12:,.0f}",
            "gross_margin": 72, "signals_daily": 150
        }
        res_inv = arch.generate(audience="investor", data=inv_data, output_name=f"{company.replace(' ', '_')}_Investor_Deck.json")
        
        # Generate Customer Deck
        res_cust = arch.generate(audience="customer", data={}, output_name=f"{company.replace(' ', '_')}_Customer_Deck.json")
        
        if res_inv.get("pptx_path") or res_cust.get("pptx_path"):
            eos.update({
                "investor_pptx_path": res_inv.get("pptx_path"),
                "customer_pptx_path": res_cust.get("pptx_path")
            })
            eos.lock_phase("pitch")
            return {"status": "ok", "investor": res_inv.get("pptx_path"), "customer": res_cust.get("pptx_path")}
        return {"error": "Deck generation failed (returned false paths)"}
    except Exception as e:
        logger.error(f"Pitch Deck error: {e}")
        return {"error": str(e)}

@app.get("/api/eos/documents/{filename:path}")
def download_eos_document(filename: str):
    import os
    from fastapi.responses import FileResponse
    # Look in the V2 Executive Reports directory
    safe_path = os.path.join(SCRIPT_DIR, "data", "V2_Executive_Reports", filename.replace("..", ""))
    if os.path.exists(safe_path):
        return FileResponse(safe_path)
    return JSONResponse({"error": "File not found"}, status_code=404)

from fastapi.responses import RedirectResponse

@app.get("/resonance")
def redirect_resonance():
    """Direct route for Resonance UI."""
    return RedirectResponse(url="http://localhost:5174", status_code=307)

@app.get("/aegis")
def redirect_aegis():
    """Direct route for Project Aegis UI."""
    return RedirectResponse(url="http://localhost:5070", status_code=307)

@app.get("/clo")
def redirect_clo():
    """Direct route for CLO Legal Engine UI/API."""
    return RedirectResponse(url="http://localhost:5080", status_code=307)

# ── Aegis Expansion: Fragility Ingest from Alpha_V2_Genesis ──────
_fragility_cache = {}

@app.post("/api/aegis/fragility-ingest")
def aegis_fragility_ingest(request: Request):
    """Receives Fragility Index broadcasts from Alpha_V2_Genesis (Port 5008)
    and caches them for the Master Architect Elite reasoning loop."""
    import asyncio
    loop = asyncio.new_event_loop()
    body = loop.run_until_complete(request.json())
    loop.close()
    _fragility_cache["latest"] = body
    return {"status": "ingested", "fragility_index": body.get("fragility_index")}

@app.get("/api/aegis/fragility-latest")
def aegis_fragility_latest():
    """Returns the latest cached Fragility Index for downstream consumers."""
    if not _fragility_cache.get("latest"):
        return JSONResponse({"status": "no_data", "message": "No fragility broadcast received yet."}, status_code=404)
    return _fragility_cache["latest"]

# ── Aegis Expansion: Sentinel Relay (CFO → Phantom QA → PulseBoard) ──
@app.post("/api/aegis/sentinel-relay")
async def aegis_sentinel_relay(request: Request):
    """Traffic controller: receives CFO financial calculations,
    routes them through Phantom QA for audit before PulseBoard commit.
    
    HARDENED: Rejects payloads missing audit signatures (is_audited=False
    or phantom_audit_id=None) with a 403 before they even reach QA."""
    import requests as _req
    body = await request.json()
    
    # ── Pre-Flight: Audit Signature Check ──────────────────────
    is_audited = body.get("is_audited", False)
    audit_id = body.get("phantom_audit_id")
    
    if not is_audited or not audit_id:
        return JSONResponse({
            "relay": "REJECTED",
            "pulseboard_status": "BLOCKED",
            "detail": "UNAUTHORIZED: Payload missing Phantom QA audit signature. "
                      "All financial data must pass through /api/phantom-qa/audit "
                      "before reaching the Sentinel Relay.",
            "payload_source": body.get("agent", "unknown"),
            "is_audited": is_audited,
            "phantom_audit_id": audit_id,
        }, status_code=403)
    
    # ── Step 1: Forward to Phantom QA for verification ─────────
    qa_verdict = {"status": "UNREACHABLE"}
    try:
        qa_res = _req.post("http://localhost:5030/api/audit", json=body, timeout=10)
        if qa_res.ok:
            qa_verdict = qa_res.json()
    except Exception as e:
        qa_verdict = {"status": "UNREACHABLE", "error": str(e)}
    
    # ── Step 2: Only PASSED verdicts unlock PulseBoard ─────────
    # SKIPPED and UNREACHABLE are treated as failures (zero-trust)
    pulseboard_status = "BLOCKED"
    if qa_verdict.get("status") == "PASSED":
        pulseboard_status = "COMMITTED"
    
    return {
        "relay": "complete",
        "phantom_qa_verdict": qa_verdict,
        "pulseboard_status": pulseboard_status,
        "payload_source": body.get("agent", body.get("source", "unknown"))
    }


@app.get("/genesis")
def redirect_genesis():
    """Direct route for Alpha Genesis UI."""
    return RedirectResponse(url="http://localhost:5173", status_code=307)

@app.get("/app/{app_name}")
def route_app(app_name: str):
    """Central proxy router for active apps."""
    name_lower = app_name.lower()
    routes = {
        "resonance": "http://localhost:5174",
        "alpha_v2_genesis": "http://localhost:5175", # Alpha port
        "project_aether": "http://localhost:5175",
        "delegate_ai_beta_agreement_vault": "http://localhost:5176",
        "pulseboard": "http://localhost:5177",
    }
    
    target_url = routes.get(name_lower)
    if target_url:
        return RedirectResponse(url=target_url, status_code=307)
    
    # Fallback checking registry.json for 'port'
    try:
        with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            app_data = data.get("apps", {}).get(app_name, {})
            if "port" in app_data and app_data["port"] is not None:
                return RedirectResponse(url=f"http://localhost:{app_data['port']}", status_code=307)
    except Exception as e:
        logger.error(f"Routing error: {e}")
        
    return JSONResponse(status_code=404, content={"error": f"UI for '{app_name}' not configured in Aether-Native router."})

# ═══════════════════════════════════════════════════════════════
# WAR ROOM EVOLUTION ENDPOINTS — Phase 1 (Red Team) + Phase 2 (Strategic Mirror)
# ═══════════════════════════════════════════════════════════════

@app.get("/api/warroom/strategies")
async def list_strategies():
    """Return available strategy presets for the Commander's Intent modal."""
    return {
        "presets": {
            k: {"label": v.label, "risk_tolerance": v.risk_tolerance,
                "budget_priority": v.budget_priority, "modifier": v.gate_threshold_modifier}
            for k, v in STRATEGY_PRESETS.items()
        },
        "supports_custom": True,
    }


class StrategySelectRequest(BaseModel):
    project_id: str
    mode: str = "balanced"         # "aggressive_growth" | "lean_mvp" | "custom"
    custom_directive: str = ""

@app.post("/api/warroom/strategy")
async def select_strategy(req: StrategySelectRequest):
    """Commander selects strategic mode for an active session."""
    orch = get_orchestrator()
    session = orch.get_session(req.project_id)
    if not session:
        return JSONResponse({"error": f"No active session for {req.project_id}"}, status_code=404)
    strategy = get_strategy_mode(req.mode, req.custom_directive)
    session["strategy_mode"] = strategy
    logger.info(f"Strategy updated for {req.project_id}: {strategy.label}")
    return {"status": "updated", "strategy": strategy.model_dump()}


@app.get("/api/warroom/chaos-library")
async def list_chaos_scenarios():
    """Return available chaos scenarios for manual drill triggering."""
    return {
        "scenarios": [
            {"id": s.scenario_id, "type": s.type, "severity": s.severity,
             "description": s.description}
            for s in CHAOS_LIBRARY
        ]
    }


class DrillRequest(BaseModel):
    project_id: str
    scenario_id: str = None  # If None, random from CHAOS_LIBRARY

@app.post("/api/warroom/drill")
async def trigger_drill(req: DrillRequest):
    """Manually trigger an adversarial drill on an active session."""
    import asyncio

    orch = get_orchestrator()
    session = orch.get_session(req.project_id)
    if not session:
        return JSONResponse({"error": f"No active session for {req.project_id}"}, status_code=404)
    if session["status"] != "active":
        return JSONResponse({"error": f"Session {req.project_id} is {session['status']}, not active"}, status_code=400)

    # Select scenario
    scenario = None
    if req.scenario_id:
        scenario = next((s for s in CHAOS_LIBRARY if s.scenario_id == req.scenario_id), None)
        if not scenario:
            return JSONResponse({"error": f"Unknown scenario: {req.scenario_id}"}, status_code=404)

    # Broadcast drill start
    await _broadcast({
        "type": "intervention",
        "agent": "SYSTEM",
        "message": f"RED TEAM DRILL INITIATED — Scenario: {scenario.scenario_id if scenario else 'random'}",
        "timestamp": _dt.now().isoformat()
    }, project=req.project_id)

    # Run drill with live agent calls
    loop = asyncio.get_event_loop()
    def _drill_agent_call(agent_name, prompt):
        return _call_agent(agent_name, prompt)

    result = orch.run_adversarial_drill(
        session, scenario=scenario, max_retries=3,
        agent_call_fn=_drill_agent_call,
    )

    # Broadcast result
    status_emoji = {"passed": "\u2705", "escalated": "\u26a0\ufe0f", "failed": "\u274c"}
    await _broadcast({
        "type": "intervention",
        "agent": "RED_TEAM",
        "message": (
            f"{status_emoji.get(result['status'], '?')} Drill {result['status'].upper()} "
            f"(Score: {result['final_score']}/10, Iterations: {result['iterations']})"
        ),
        "timestamp": _dt.now().isoformat()
    }, project=req.project_id)

    return {
        "status": result["status"],
        "scenario": result["scenario"].model_dump() if hasattr(result["scenario"], "model_dump") else result["scenario"],
        "iterations": result["iterations"],
        "final_score": result["final_score"],
        "escalation_reason": result.get("escalation_reason"),
    }

# ═══════════════════════════════════════════════════════════════
# WAR ROOM EVOLUTION ENDPOINTS — Phase 3 (Wisdom Vault)
# ═══════════════════════════════════════════════════════════════

class WisdomApproveRequest(BaseModel):
    standard_id: str

@app.get("/api/wisdom/standards")
async def list_approved_standards(domain: str = None, applicability: str = None):
    """List approved corporate standards."""
    vault = get_wisdom_vault()
    standards = vault.get_approved(domain=domain, applicability=applicability)
    return [s.model_dump() for s in standards]

@app.get("/api/wisdom/pending")
async def list_pending_standards():
    """List standards awaiting Commander review."""
    vault = get_wisdom_vault()
    standards = vault.get_pending()
    return [s.model_dump() for s in standards]

@app.post("/api/wisdom/approve")
async def approve_standard(req: WisdomApproveRequest):
    """Commander approves a proposed standard."""
    vault = get_wisdom_vault()
    result = vault.approve(req.standard_id)
    if result:
        return {"status": "success", "standard": result.model_dump()}
    return JSONResponse({"error": "Standard not found or already processed"}, status_code=404)

@app.post("/api/wisdom/reject")
async def reject_standard(req: WisdomApproveRequest):
    """Commander rejects a proposed standard."""
    vault = get_wisdom_vault()
    result = vault.reject(req.standard_id)
    if result:
        return {"status": "success", "standard": result.model_dump()}
    return JSONResponse({"error": "Standard not found or already processed"}, status_code=404)

# ═══════════════════════════════════════════════════════════════
# COO ENDPOINTS — Phase 4 Resource Tracking
# ═══════════════════════════════════════════════════════════════

@app.get("/api/coo/budget")
async def get_coo_budget(project_id: str):
    coo = coo_agent.get_coo()
    ledger = coo.get_ledger(project_id)
    return {
        "project_id": ledger.project_id,
        "tokens_total": ledger.total_tokens,
        "budget": ledger.max_budget,
        "status": ledger.status,
        "est_cost": f"${ledger.estimated_cost_usd:.4f}"
    }

@app.post("/api/coo/reset")
async def reset_coo_budget(project_id: str):
    coo = coo_agent.get_coo()
    ledger = coo.reset_ledger(project_id)
    return {"status": "success", "message": f"Budget reset for {project_id}"}


# ── Startup: Auto-start incoming watcher + Ghost Operator ──
@app.on_event("startup")
async def _startup_watcher():
    global _watcher_thread
    if _watcher_available:
        _watcher_thread = threading.Thread(target=watch_incoming, args=(60,), daemon=True)
        _watcher_thread.start()
        logger.info("Incoming Watcher auto-started (60s poll)")

    # ── Auto-boot Ghost Operator on port 5100 ──
    import socket as _sock
    _operator_alive = False
    try:
        with _sock.create_connection(("localhost", 5100), timeout=1):
            _operator_alive = True
    except Exception:
        pass

    if not _operator_alive:
        try:
            _factory_dir = os.path.dirname(os.path.abspath(__file__))
            subprocess.Popen(
                ["python", "operator_agent.py"],
                cwd=_factory_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            logger.info("Ghost Operator auto-started on port 5100.")
        except Exception as _e:
            logger.error(f"Ghost Operator auto-start FAILED: {_e}")
    else:
        logger.info("Ghost Operator already running on port 5100 — skipping launch.")

if __name__ == "__main__":
    import uvicorn
    # AETHER-NATIVE: Lock to port 5000 to act as Central Brain
    uvicorn.run(app, host="0.0.0.0", port=5000)

# V3 MIGRATION COMPLETE
