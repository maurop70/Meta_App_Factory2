"""
operator_agent.py — Phase 10: The Operator Agent Infrastructure
═════════════════════════════════════════════════════════════════════
Autonomous proxy executing the "API-First Shadow Protocol".
Executes physical actions exclusively by constructing native JSON 
payloads mapped to internal endpoints. Runs as persistent FastAPI service.
"""

import os
import json
import logging
import requests
from typing import Optional, List
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pydantic import BaseModel, Field
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '.env'), override=True)
except ImportError:
    pass

import google.generativeai as genai

logger = logging.getLogger("OperatorAgent")
logging.basicConfig(level=logging.INFO)

BASE_URL = "http://localhost:5000"

# ── Zero-Trust Authentication Headers ──
AUTH_HEADERS = {
    "X-Antigravity-Agent": "Operator_Agent",
    "X-Sentinel-Relay": "secure-signature-verified"
}

# ── Python Tool Schemas (Gemini Inferred) ──


def trigger_dispatch(message: str, strategy_mode: str, stress_test: bool) -> str:
    """Fires POST /api/war-room/dispatch for standard Aether protocols."""
    payload = {
        "message": message,
        "strategy_mode": strategy_mode,
        "stress_test": stress_test
    }
    url = f"{BASE_URL}/api/war-room/dispatch"
    try:
        r = requests.post(url, json=payload, headers=AUTH_HEADERS, timeout=15)
        return f"Successfully dispatched command to /api/war-room/dispatch. Status: {r.status_code}. Response: {r.text[:200]}"
    except Exception as e:
        logger.error(f"[Operator] Error firing dispatch: {e}")
        return f"Failed to dispatch: {e}"

def trigger_seed(topic: str) -> str:
    """Fires POST /api/warroom/seed to bypass legacy keyword gates."""
    payload = {"topic": topic}
    url = f"{BASE_URL}/api/warroom/seed"
    try:
        r = requests.post(url, json=payload, headers=AUTH_HEADERS, timeout=15)
        return f"Successfully passed seed to /api/warroom/seed. Status: {r.status_code}. Response: {r.text[:200]}"
    except Exception as e:
        logger.error(f"[Operator] Error firing seed: {e}")
        return f"Failed to trigger seed: {e}"

def trigger_chaos_drill(scenario_id: str, project_id: str) -> str:
    """Fires POST /api/warroom/drill for targeted stress testing."""
    payload = {
        "scenario_id": scenario_id,
        "project_id": project_id
    }
    url = f"{BASE_URL}/api/warroom/drill"
    try:
        r = requests.post(url, json=payload, headers=AUTH_HEADERS, timeout=15)
        return f"chaos drill '{scenario_id}' deployed. Status: {r.status_code}."
    except Exception as e:
        logger.error(f"[Operator] Error firing chaos drill: {e}")
        return f"Failed to trigger chaos drill: {e}"

def trigger_system_flush(project_id: str) -> str:
    """Clears the active pipeline memory to unlock the board via DELETE /api/warroom/history/clear."""
    url = f"{BASE_URL}/api/warroom/history/clear"
    try:
        r = requests.delete(url, params={"project": project_id}, headers=AUTH_HEADERS, timeout=10)
        return f"System flushed successfully. Status: {r.status_code}."
    except Exception as e:
        logger.error(f"[Operator] Error flushing system: {e}")
        return f"Failed to flush system: {e}"

def get_system_status(check_type: str) -> str:
    """Pings the internal health-check endpoints of the C-Suite (Ports 5030, 5050, 5070)."""
    ports = [5030, 5050, 5070]
    results = []
    for port in ports:
        try:
            r = requests.get(f"http://localhost:{port}/health", timeout=2)
            results.append(f"Port {port}: ONLINE ({r.status_code})")
        except:
            results.append(f"Port {port}: OFFLINE")
            
    # Also check the orchestrator
    try:
        r = requests.get(f"{BASE_URL}/api/health", timeout=2)
        results.append(f"Orchestrator 5000: ONLINE ({r.status_code})")
    except:
        results.append(f"Orchestrator 5000: OFFLINE")
        
    return " | ".join(results)

def trigger_executive_directive(options: List[str], context: str) -> str:
    """Surfaces an architectural conflict as a UI-level prompt in the War Room for human adjudication."""
    payload = {
        "message": f"[EXECUTIVE FORK AWAITING DIRECTIVE]\nContext: {context}\nOptions: {', '.join(options)}",
        "strategy_mode": "architectural_fork",
        "stress_test": False
    }
    url = f"{BASE_URL}/api/war-room/dispatch"
    try:
        r = requests.post(url, json=payload, headers=AUTH_HEADERS, timeout=15)
        return f"Successfully escalated fork to War Room UI. Status: {r.status_code}."
    except Exception as e:
        logger.error(f"[Operator] Error escalating fork: {e}")
        return f"Failed to escalate fork: {e}"

OPERATOR_TOOLS = [trigger_dispatch, trigger_seed, trigger_chaos_drill, trigger_system_flush, get_system_status, trigger_executive_directive]

def invoke_operator(directive: str) -> str:
    """
    Invokes the Operator Agent using Gemini Function Calling.
    Executes the matched tool directly against the local REST API.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "Error: GEMINI_API_KEY is not set. Execution blocked."

    genai.configure(api_key=api_key)
    
    system_instruction = (
        "You are the Operator Agent, a permanent autonomous proxy executing the API-First Shadow Protocol. "
        "Your responses will be securely broadcast back to the War Room UI. "
        "When given a directive, select the optimal tool, execute it natively, and report the success or failure "
        "clearly back to the Commander."
    )

    # Hardcoded gemini-2.5-flash series for strict schema compliance
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=system_instruction,
        tools=OPERATOR_TOOLS
    )

    logger.info(f"[Operator] Parsing directive: {directive}")
    try:
        chat = model.start_chat()
        response = chat.send_message(directive)
        
        # Give a robust, direct summary
        res_text = response.text
        if not res_text.strip() and chat.history:
            res_text = chat.history[-1].parts[0].text
            
        logger.info(f"[Operator] Execution Result: {res_text}")
        return res_text
    except Exception as e:
        logger.error(f"[Operator] Execution Fault: {e}")
        return f"Operator Error: {e}"

def push_feedback_to_warroom(message: str):
    """Closes the feedback loop by streaming confirmation directly back to the UI."""
    try:
        url = f"{BASE_URL}/api/warroom/intervene"
        # We simulate a systemic SSE event by passing it locally or through the intervene trigger
        payload = {
            "message": "Operator Confirmation Protocol",
            "project_name": "Aether",
            "operator_override_message": message # Special flag for api.py to digest as Operator
        }
        # In api.py, it will interpret 'operator_override_message' as a system broadcast
        requests.post(url, json=payload, headers=AUTH_HEADERS, timeout=5)
    except Exception as e:
        logger.warning(f"[Operator] Failed to push SSE feedback: {e}")

# ── API Background Service ──
app = FastAPI(title="Operator Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class DirectiveRequest(BaseModel):
    directive: str
    
def background_execution(directive: str):
    """Executes the directive and pushes the physical result back to the UI."""
    logger.info(f"[Operator] Starting background execution for directive: {directive}")
    result = invoke_operator(directive)
    push_feedback_to_warroom(result)

@app.post("/api/operator/command")
async def run_command(req: DirectiveRequest, bg_tasks: BackgroundTasks):
    """Persistent endpoint called by the main orchestrator."""
    bg_tasks.add_task(background_execution, req.directive)
    return {"status": "ok", "message": "Directive received. Operator executing."}

class ExecutiveForkPayload(BaseModel):
    options: List[str]
    context: str

@app.post("/api/operator/executive-fork")
async def handle_executive_fork(req: ExecutiveForkPayload, bg_tasks: BackgroundTasks):
    """Called by forge_orchestrator to halt autonomous loop and ping UI."""
    bg_tasks.add_task(trigger_executive_directive, req.options, req.context)
    return {"status": "Escalated", "message": "Executive fork sent to War Room UI."}

class WriteFilePayload(BaseModel):
    file_path: str
    content: str

@app.post("/api/builder/write-file")
async def builder_write_file(payload: WriteFilePayload):
    """Writes a file to the active project context directly from the Builder Chat."""
    factory_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.abspath(os.path.dirname(factory_dir))
    
    # Safely resolve absolute path
    clean_path = payload.file_path.lstrip("/\\")
    target_path = os.path.abspath(os.path.join(root_dir, clean_path))
    
    # Enforce strict path traversal security
    if not target_path.startswith(root_dir):
        raise HTTPException(status_code=403, detail="Forbidden: Path traversal attack blocked.")
    
    try:
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(payload.content)
        logger.info(f"[Operator] Wrote physical file to {target_path}")
        return {"status": "ok", "message": f"Successfully wrote to {payload.file_path}"}
    except Exception as e:
        logger.error(f"[Operator] Failed to write file {target_path}: {e}")
        return {"error": str(e)}

class ReadFilePayload(BaseModel):
    file_path: str

@app.post("/api/builder/read-file")
async def builder_read_file(payload: ReadFilePayload):
    """Reads physical filesystem source code into the Builder Chat context."""
    factory_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.abspath(os.path.dirname(factory_dir))
    
    clean_path = payload.file_path.lstrip("/\\")
    target_path = os.path.abspath(os.path.join(root_dir, clean_path))
    
    if not target_path.startswith(root_dir):
        raise HTTPException(status_code=403, detail="Forbidden: Path traversal attack blocked.")
        
    try:
        if not os.path.exists(target_path):
            raise HTTPException(status_code=404, detail="File not found on target path.")
            
        with open(target_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        logger.info(f"[Operator] Read physical file from {target_path}")
        return {"status": "ok", "content": content}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Operator] Failed to read file {target_path}: {e}")
        return {"error": str(e)}
    
@app.get("/api/health")
def health():
    """Watchdog compatibility ping."""
    return {"status": "up", "agent": "Operator_Agent"}

class ErrorTelemetryPayload(BaseModel):
    service_name: str
    error_message: str
    traceback: str

@app.post("/api/telemetry/error")
def log_telemetry_error(payload: ErrorTelemetryPayload):
    """Centralized error aggregation for failing C-Suite apps."""
    logger.error(f"[TELEMETRY ERROR] {payload.service_name} crashed: {payload.error_message}")
    logger.error(f"Traceback:\n{payload.traceback}")
    
    factory_dir = os.path.dirname(os.path.abspath(__file__))
    error_log = os.path.join(factory_dir, "central_error.log")
    try:
        with open(error_log, "a", encoding="utf-8") as f:
            f.write(f"\n[{datetime.now().isoformat()}] {payload.service_name}: {payload.error_message}\n{payload.traceback}\n")
    except Exception:
        pass
    
    # Broadcast to War Room UI
    push_feedback_to_warroom(f"⚠️ App Crash: {payload.service_name} crashed with {payload.error_message}. See central error log.")
    return {"status": "Logged"}

class QuarantinePayload(BaseModel):
    service_name: str

@app.post("/api/operator/quarantine")
def quarantine_service(payload: QuarantinePayload):
    """Force changes an app's manifest status to QUARANTINED."""
    import os, json
    factory_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(factory_dir)
    manifest_path = os.path.join(root_dir, "sync_manifest.json")
    
    try:
        if os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            if isinstance(data, list):
                for app in data:
                    if app.get("name") == payload.service_name:
                        app["status"] = "QUARANTINED"
                
                with open(manifest_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                    
        return {"status": "QUARANTINED", "message": f"{payload.service_name} has been isolated."}
    except Exception as e:
        logger.error(f"[Operator] Failed to quarantine {payload.service_name}: {e}")
        return {"error": str(e)}

@app.get("/api/operator/manifest")
def get_manifest():
    """Parses sync_manifest.json dynamically and serves it as the active C-Suite array."""
    import json
    
    factory_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(factory_dir)
    manifest_path = os.path.join(root_dir, "sync_manifest.json")
    
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
            # If it's already a standardized array, just return it
            if isinstance(data, list):
                return data
                
            apps_array = []
            
            # Map top-level items into array objects for the frontend
            for key, val in data.items():
                if isinstance(val, dict) and key not in ["projects", "drive_structure"]:
                    apps_array.append({"name": key, "status": val.get("status", "active"), **val})
                    
            for proj_name, proj_data in data.get("projects", {}).items():
                apps_array.append({"name": proj_name, "status": proj_data.get("status", "active"), **proj_data})
                
            return apps_array
    except Exception as e:
        logger.error(f"[Operator] Failed to read sync_manifest.json: {e}")
        return []

@app.get("/api/operator/scout")
def scout_agents():
    """Scans the root for unregistered agents (folders ending in Agent with a server.py)"""
    import os, json
    factory_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(factory_dir)
    manifest_path = os.path.join(root_dir, "sync_manifest.json")
    
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest_json = json.load(f)
            
        if isinstance(manifest_json, list):
            registered_names = [a.get("name") for a in manifest_json if a.get("name")]
        else:
            registered_names = list(manifest_json.keys())
            registered_names.extend(list(manifest_json.get("projects", {}).keys()))
    except Exception:
        registered_names = []
        
    anomalies = []
    
    # Check Meta_App_Factory directory
    for item in os.listdir(factory_dir):
        if item.endswith("_Agent") or item.endswith("_Agents"):
            item_path = os.path.join(factory_dir, item)
            if os.path.isdir(item_path):
                if os.path.exists(os.path.join(item_path, "server.py")) or os.path.exists(os.path.join(item_path, "main.py")) or os.path.exists(os.path.join(item_path, "api.py")):
                    if item not in registered_names:
                        anomalies.append({"name": item, "path": item_path})
                        
    # Check Root directory
    for item in os.listdir(root_dir):
        if item.endswith("_Agent") or item.endswith("_Agents"):
            item_path = os.path.join(root_dir, item)
            if os.path.isdir(item_path) and item not in [a["name"] for a in anomalies]:
                if os.path.exists(os.path.join(item_path, "server.py")) or os.path.exists(os.path.join(item_path, "main.py")) or os.path.exists(os.path.join(item_path, "api.py")):
                    if item not in registered_names:
                        anomalies.append({"name": item, "path": item_path})
                        
    return anomalies

class PromotePayload(BaseModel):
    name: str
    port: str
    cwd: str
    command: str

@app.post("/api/operator/promote")
def promote_agent(payload: PromotePayload):
    """Appends the newly discovered agent directly to sync_manifest.json."""
    import os, json
    factory_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(factory_dir)
    manifest_path = os.path.join(root_dir, "sync_manifest.json")
    
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        # Standardize strictly to an array container
        if isinstance(data, dict):
            apps_array = []
            for key, val in data.items():
                if isinstance(val, dict) and key not in ["projects", "drive_structure"]:
                    apps_array.append({"name": key, "status": val.get("status", "active"), **val})
            for proj_name, proj_data in data.get("projects", {}).items():
                apps_array.append({"name": proj_name, "status": proj_data.get("status", "active"), **proj_data})
            data = apps_array
            
        new_app = {
            "name": payload.name,
            "port": int(payload.port) if payload.port.isdigit() else payload.port,
            "cwd": payload.cwd,
            "command": payload.command,
            "status": "promoted"
        }
        
        data.append(new_app)
        
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            
        return {"status": "success", "message": f"{payload.name} promoted to Active C-Suite map."}
    except Exception as e:
        logger.error(f"[Operator] Promotion failed: {e}")
        return {"error": str(e)}

class RestartRequest(BaseModel):
    service_name: str

@app.post("/api/operator/restart-service")
def restart_service(req: RestartRequest, bg_tasks: BackgroundTasks):
    """Executes a native OS-level restart of a registered Meta_App_Factory service."""
    import subprocess
    
    restart_commands = {
        "phantom_qa": 'start /min "" cmd /c "cd Phantom_QA_Elite\\backend && python server.py"',
        "master_architect": 'start /min "" cmd /c "cd Master_Architect_Elite_Logic && python server.py"',
        "c_suite": 'start /min "" cmd /c "cd CFO_Agent && python server.py"',
        "clo_legal": 'start /min "" cmd /c "cd apps\\CLO_Agent && python legal_engine.py"',
        "ghost_operator": 'start /min "" cmd /c "python operator_agent.py"',
    }
    
    service = req.service_name.lower()
    if service in restart_commands:
        cmd = restart_commands[service]
        factory_dir = os.path.dirname(os.path.abspath(__file__))
        
        def spawn_process():
            try:
                subprocess.Popen(cmd, shell=True, cwd=factory_dir)
                logger.info(f"[Operator] Restarts dispatched for {service}")
            except Exception as e:
                logger.error(f"[Operator] Restart failed for {service}: {e}")
                
        bg_tasks.add_task(spawn_process)
        return {"status": "ok", "message": f"Restart initiated for {service}"}
    else:
        return {"status": "error", "message": f"Unknown service: {service}"}

if __name__ == "__main__":
    uvicorn.run("operator_agent:app", host="0.0.0.0", port=5100, reload=True)
