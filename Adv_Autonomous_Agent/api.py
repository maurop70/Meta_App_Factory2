# ── V3.0 Resilience Integration ──────────────────────────
import os as _os, sys as _sys
_FACTORY_DIR = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
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


from fastapi import FastAPI
from pydantic import BaseModel
import subprocess
import sys
import os

app = FastAPI(title="Antigravity Meta App Factory API")

class TaskRequest(BaseModel):
    task: str

@app.post("/execute")
def execute_task(request: TaskRequest):
    # This bridge triggers the MetaSupervisor via the CLI
    # We use subprocess to run the supervisor script with the user's prompt
    try:
        # Determine the path to supervisor.py relative to this file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        supervisor_path = os.path.join(current_dir, "supervisor.py")
        
        # In a real production scenario, you might want to run this as a background task
        # or use a task queue if the supervisor loop takes a long time.
        # For now, we trigger it and return a confirmation message.
        
        # Note: supervisor.py enters an interactive loop. 
        # For n8n integration, you might later want a non-interactive mode.
        command = [sys.executable, supervisor_path, request.task]
        
        # We start the process in the background to avoid blocking the API response
        subprocess.Popen(command)
        
        return {
            "status": "success", 
            "message": f"Task '{request.task}' sent to Antigravity factory.",
            "details": "Supervisor process started in background."
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", 8000)))
    args, unknown = parser.parse_known_args()
    uvicorn.run(app, host="0.0.0.0", port=args.port)
# V3 AUTO-HEAL ACTIVE
