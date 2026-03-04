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

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
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
    """SSE endpoint: streams factory build progress in real-time."""
    import io
    import contextlib
    import threading
    import queue

    progress_queue = queue.Queue()

    def run_build():
        # Capture stdout from factory.create_app
        old_stdout = sys.stdout
        sys.stdout = buffer = io.StringIO()
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
            progress_queue.put({"step": "COMPLETE", "text": f"✅ App '{req.app_name}' built successfully!"})
        except Exception as e:
            progress_queue.put({"step": "ERROR", "text": f"❌ Build failed: {str(e)}"})
        finally:
            sys.stdout = old_stdout
            # Push all captured output
            output = buffer.getvalue()
            for line in output.strip().split("\n"):
                if line.strip():
                    progress_queue.put({"step": "LOG", "text": line.strip()})
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
    """Non-streaming build: directly calls factory.create_app and returns result."""
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
        return {"status": "success", "app_name": req.app_name, "log": output}
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


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "streaming": STREAMING_AVAILABLE,
        "memory": STREAMING_AVAILABLE and MEMORY_AVAILABLE,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
