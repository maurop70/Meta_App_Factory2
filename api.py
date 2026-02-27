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
