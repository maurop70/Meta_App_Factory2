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
from fastapi import FastAPI, BackgroundTasks
import uvicorn
from pydantic import BaseModel, Field

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
    
@app.get("/api/health")
def health():
    """Watchdog compatibility ping."""
    return {"status": "up", "agent": "Operator_Agent"}

if __name__ == "__main__":
    uvicorn.run("operator_agent:app", host="0.0.0.0", port=5100, reload=True)
