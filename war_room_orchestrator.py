import os
import sys
import json
import asyncio
import aiohttp
import httpx
from datetime import datetime
from dotenv import load_dotenv
from ai_utils import generate_with_backoff_sync

# =====================================================================
# PHASE 1: ENFORCE TELEMETRY LOCK & MLOPS TRACING
# =====================================================================
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGCHAIN_PROJECT"] = "Meta_App_Factory_V3"

try:
    from langsmith import traceable
except ImportError:
    # Fallback to a dummy decorator if langsmith is not available
    def traceable(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

# CIO Framework Integration
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "Core_Framework"))
try:
    from base_orchestrator import BaseOrchestrator
except ImportError:
    # Fallback if pathing is complex in runtime
    class BaseOrchestrator: 
        def validate_payload(self, data, agent): return data

# Load environment variables
dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

GHOST_STREAM_URL = "http://localhost:5030/api/qa/ingest"

# Endpoints
CFO_URL = "http://localhost:5070/api/consult"
CMO_URL = "http://localhost:5020/api/warroom/respond"
CIO_URL = "http://localhost:5090/api/cio/process"

async def sse_broadcast(status: str, node: str, result: str):
    """Broadcast telemetry to Phantom QA Ghost Stream."""
    payload = {
        "agent": "CEO_Brain",
        "status": status,
        "message": f"[{node}] {result}",
        "timestamp": datetime.now().isoformat()
    }
    print(f"[Ghost Stream] {status} | {node}")
    try:
        # httpx avoids WinError 233 — aiohttp uses subprocess pipes on Windows
        async with httpx.AsyncClient(timeout=2.0) as client:
            await client.post(GHOST_STREAM_URL, json=payload)
    except Exception as e:
        print(f"  [Ghost Stream Error] {e}")

def validate_report(report: dict, agent: str) -> dict:
    """
    Validation Shield: Uses the Core_Framework's BaseOrchestrator logic.
    """
    framework = BaseOrchestrator()
    validated = framework.validate_payload(report, agent)
    
    # Custom boardroom extensions (not yet in core)
    # If the node was organically bypassed, skip rigid schema enforcement
    if validated.get("status") == "BYPASSED":
        return validated

    if agent == "CMO" and "error" not in validated:
        if not all(k in validated for k in ["perspective", "data_points"]):
            return {"error": "Validation Shield: CMO missing narrative", "raw": report}
            
    if agent == "CFO" and "report" in validated:
        inner = validated["report"]
        if not all(k in inner for k in ["fragility_index", "composite_score"]):
            return {"error": "Validation Shield: CFO missing financial indices", "raw": report}

    return validated

# ── Trace Division Heads Calls natively ──

@traceable(run_type="llm", name="CFO_Agent_Call")
async def call_cfo(intent: str, intel_brief: str = "") -> dict:
    """Call CFO via the Dialogue Box native form."""
    try:
        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field('instruction', f"CEO DIRECTIVE: {intent}\n\n=== CIO INTELLIGENCE BRIEF ===\n{intel_brief}")
            async with session.post(CFO_URL, data=data, timeout=60) as resp:
                text = await resp.text()
                try:
                    return validate_report(json.loads(text), "CFO")
                except:
                    return {"error": "CFO response is not JSON", "raw": text}
    except Exception as e:
        return {"error": str(e)}

@traceable(run_type="llm", name="CMO_Agent_Call")
async def call_cmo(intent: str, intel_brief: str = "") -> dict:
    """Call CMO via the War Room endpoint."""
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "topic": f"{intent}\n\n=== CIO INTELLIGENCE BRIEF ===\n{intel_brief}",
                "context": "CEO War Room Directive",
                "agents_present": ["CEO", "CFO", "CIO", "CMO"]
            }
            async with session.post(CMO_URL, json=payload, timeout=60) as resp:
                text = await resp.text()
                try:
                    return validate_report(json.loads(text), "CMO")
                except:
                    return {"error": "CMO response is not JSON", "raw": text}
    except Exception as e:
        return {"error": str(e)}

@traceable(run_type="llm", name="CIO_Agent_Call")
async def call_cio(intent: str, intel_brief: str = "") -> dict:
    """Call CIO via the Intelligence Sweep endpoint."""
    try:
        async with aiohttp.ClientSession() as session:
            payload = {"focus_areas": [f"{intent}\n\n{intel_brief}"]}
            # Some endpoint implementations might block if a sweep is already in progress
            async with session.post(CIO_URL, json=payload, timeout=60) as resp:
                text = await resp.text()
                try:
                    return validate_report(json.loads(text), "CIO")
                except:
                    return {"error": "CIO response is not JSON", "raw": text}
    except Exception as e:
        return {"error": str(e)}

@traceable(run_type="llm", name="CIO_Deep_Research_Preflight")
async def call_cio_preflight(intent: str) -> dict:
    """Pre-flight CIO sweep to gather live internet intelligence."""
    try:
        async with aiohttp.ClientSession() as session:
            payload = {"query": intent}
            async with session.post("http://localhost:5090/api/cio/deep_research", json=payload, timeout=120) as resp:
                if resp.status == 200:
                    return await resp.json()
                return {"error": f"HTTP {resp.status}"}
    except Exception as e:
        return {"error": str(e)}

# ── PHASE 1: CORE AGENT EXECUTION LOOP ──

@traceable(run_type="chain", name="Core_Agent_Execution_Loop")
async def execute_agent_node(agent_id: str, payload: dict):
    """
    Core LLM loop. Natively exports intermediate states (tool inputs, 
    confidence scores) to the tracing server before returning payload.
    """
    prompt = payload.get("prompt")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY is missing from environment. Cannot synthesize.")
        return {"error": "GEMINI_API_KEY is missing from environment."}

    GEMINI_MODELS = ["gemini-2.5-pro", "gemini-2.5-flash"]
    GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

    ceo_strategy = None
    last_error = ""

    async with httpx.AsyncClient(timeout=120.0) as http:
        for model in GEMINI_MODELS:
            url = f"{GEMINI_BASE}/{model}:generateContent?key={api_key}"
            body = {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.7, "maxOutputTokens": 8192}
            }
            try:
                resp = await http.post(url, json=body)
                if resp.status_code == 200:
                    data = resp.json()
                    ceo_strategy = (
                        data.get("candidates", [{}])[0]
                        .get("content", {})
                        .get("parts", [{}])[0]
                        .get("text", "")
                    )
                    if ceo_strategy:
                        print(f"[CEO Synthesis] Success with {model}")
                        break
                elif resp.status_code == 429:
                    last_error = f"{model}: Rate limited (429)"
                    await asyncio.sleep(3)
                else:
                    last_error = f"{model}: HTTP {resp.status_code} — {resp.text[:200]}"
            except Exception as req_err:
                last_error = f"{model}: {req_err}"

    if not ceo_strategy:
        raise Exception(f"All Gemini models failed. Last error: {last_error}")

    return {"strategy": ceo_strategy}

# ── CEO DISPATCH MATRIX ──

@traceable(run_type="chain", name="CEO_War_Room_Dispatch")
async def dispatch_to_csuite(intent: str, pre_collected_reports: dict = None):
    await sse_broadcast("RUNNING", "Routing Commander's Intent to C-Suite...", "INFO")
    
    print("\n--- CEO War Room Dispatch Started ---")
    print(f"Commander's Intent: '{intent}'")

    # =====================================================================
    # PHASE 2: NATIVE VECTOR MEMORY MATRIX LOOKUP
    # =====================================================================
    historical_memories = []
    try:
        from agent_memory_matrix import VectorMemoryMatrix
        memory = VectorMemoryMatrix()
        context = memory.retrieve_context(intent, n_results=3)
        if context and context.get("documents"):
            for doc_list in context["documents"]:
                for doc in doc_list:
                    historical_memories.append(doc)
            print(f"[Memory Matrix] Retrieved {len(historical_memories)} matching historical contexts.")
    except Exception as mem_err:
        print(f"[Memory Matrix Error] Failed to retrieve context: {mem_err}")

    # INJECT CIO PRE-FLIGHT
    await sse_broadcast("RUNNING", "CIO Agent initiating Live Internet Sensor Matrix...", "INFO")
    intel_brief_str = "No live intelligence gathered."
    
    preflight_result = await call_cio_preflight(intent)
    if "error" not in preflight_result and "intelligence_brief" in preflight_result:
        sources = preflight_result.get("source_count", 0)
        intel_brief_str = preflight_result.get("intelligence_brief", "")
        await sse_broadcast("PASS", f"[CIO] Deep Research Complete: {sources} Sources Scraped", "TEST_PASS")
    else:
        err = preflight_result.get("error", "Unknown error")
        await sse_broadcast("FAIL", f"[CIO] Deep Research Failed: {err}", "TEST_FAIL")
    
    if pre_collected_reports:
        await sse_broadcast("RUNNING", "Using pre-collected agent reports for synthesis.", "INFO")
        cfo_res = validate_report(pre_collected_reports.get("CFO", {}), "CFO")
        cmo_res = validate_report(pre_collected_reports.get("CMO", {}), "CMO")
        cio_res = validate_report(pre_collected_reports.get("CIO", {}), "CIO")
    else:
        await sse_broadcast("RUNNING", "C-Suite Deliberating (CFO, CMO, CIO) concurrently...", "INFO")
        
        # =====================================================================
        # PHASE 3: ASYNCHRONOUS HIERARCHIES (TASKGROUP ROUTING)
        # =====================================================================
        try:
            async with asyncio.TaskGroup() as tg:
                cfo_task = tg.create_task(call_cfo(intent, intel_brief_str))
                cmo_task = tg.create_task(call_cmo(intent, intel_brief_str))
                cio_task = tg.create_task(call_cio(intent, intel_brief_str))
            
            cfo_res = cfo_task.result()
            cmo_res = cmo_task.result()
            cio_res = cio_task.result()
        except Exception as e:
            # Fatal execution halt escalated for architectural review
            raise RuntimeError(f"PARALLEL EXECUTION FRACTURE: {str(e)}")
    
    await sse_broadcast("RUNNING", "Reports received. Synthesizing CEO Strategy.", "INFO")
    
    # Bundle payloads for the CEO
    bundled_payload = {
        "CFO_Report": cfo_res,
        "CMO_Report": cmo_res,
        "CIO_Report": cio_res
    }
    
    # ── CEO Synthesis via Gemini 2.5 Cloud ──
    print("\n--- Engaging CEO Synthesis (Gemini 2.5 Cloud) ---")
    
    history_section = ""
    if historical_memories:
        history_section = "\n### [HISTORICAL BOARDROOM MEMORY (Vector Search)]\n" + "\n---\n".join(historical_memories) + "\n"

    prompt = f"""
You are the CEO of the Antigravity Meta App Factory workspace. 
You just dispatched a Commander's Intent to your C-Suite.
Intent: "{intent}"
{history_section}
### [CIO INTELLIGENCE & TECHNICAL FEASIBILITY REPORT]
{intel_brief_str}

Here are the raw JSON reports you received back from the division heads:
CFO Report: 
{json.dumps(cfo_res, indent=2)}

CMO Report:
{json.dumps(cmo_res, indent=2)}

CIO Report:
{json.dumps(cio_res, indent=2)}

YOUR DIRECTIVE:
1. Do not repeat the reports. Synthesize them.
2. Mathematically recognize that the CIO is online and active. Analyze the CIO's technical feasibility metrics and resources.
3. Identify cross-departmental CONTRADICTIONS (e.g. CMO wants a huge budget, CFO warns of fragility; CIO wants risky AI scaling, CFO warns of compute costs).
4. Force a decisive resolution as the CEO.
5. Output a single final unified strategy and next actions.
"""

    try:
        # Run via the decorated execute_agent_node function (Phase 1)
        node_result = await execute_agent_node(agent_id="CEO", payload={"prompt": prompt})
        
        if "error" in node_result:
            raise Exception(node_result["error"])
            
        ceo_strategy = node_result["strategy"]

        print("\n================ CEO FINAL STRATEGY ================\n")
        print(ceo_strategy)
        print("\n====================================================\n")
        
        # =====================================================================
        # PHASE 2: NATIVE VECTOR MEMORY MATRIX RECORDING
        # =====================================================================
        try:
            from agent_memory_matrix import VectorMemoryMatrix
            memory = VectorMemoryMatrix()
            memory.lock_memory(
                session_id="warroom",
                payload=f"Intent: {intent}\nStrategy: {ceo_strategy}",
                metadata={"timestamp": datetime.now().isoformat(), "intent": intent[:100]}
            )
            print("[Memory Matrix] Successfully locked strategy into vector store.")
        except Exception as mem_err:
            print(f"[Memory Matrix Error] Failed to lock memory: {mem_err}")

        await sse_broadcast("PASS", "War Room deliberation complete. Strategy unified.", "TEST_PASS")
        return {"strategy": ceo_strategy}

    except Exception as e:
        print(f"CEO Synthesis failed: {e}")
        await sse_broadcast("FAIL", f"CEO Synthesis failed: {str(e)}", "TEST_FAIL")
        return {"error": str(e)}


# =====================================================================
# PHASE 3: ASYNCHRONOUS HIERARCHIES (ORCHESTRATE PARALLEL MATRIX)
# =====================================================================

async def orchestrate_c_suite_parallel(blueprint: dict):
    """
    Natively spawns subagent tasks without sequential blocking.
    The CTO node dynamically orchestrates the matrix.
    """
    try:
        # Utilize native Python 3.11+ TaskGroups for strict parallel execution
        async with asyncio.TaskGroup() as tg:
            # We import and trigger our local CFO, CMO, and CTO integrations in parallel
            from cto_agent import CTOAgent
            from cmo_agent import CMOAgent
            from cfo_agent import CFOAgent
            
            cto = CTOAgent()
            cmo = CMOAgent()
            cfo = CFOAgent()
            
            intent_str = json.dumps(blueprint)
            
            cto_task = tg.create_task(asyncio.to_thread(cto.run, intent_str))
            # Mock or call CMO response
            cmo_task = tg.create_task(asyncio.to_thread(cmo.run, intent_str))
            # Synthesize basic financials
            cfo_task = tg.create_task(asyncio.to_thread(
                cfo.synthesize,
                project_id=blueprint.get("project_id", "DefaultProject"),
                cmo_data={"marketing_cost": 25000},
                cto_data={"infrastructure_cost_monthly": 500}
            ))
            
        # Matrix reconciliation
        return {
            "status": "success",
            "cto_report": cto_task.result(),
            "cfo_report": cfo_task.result(),
            "cmo_report": cmo_task.result()
        }
        
    except Exception as e:
        # Fatal execution halt escalated for architectural review
        raise RuntimeError(f"PARALLEL EXECUTION FRACTURE: {str(e)}")


import subprocess
from pathlib import Path

BLUEPRINT_PATH = Path("Infrastructure_Blueprint.json")

async def blueprint_worker(queue: asyncio.Queue):
    """
    Background worker natively isolated from the primary application thread.
    Ingests the blueprint JSON and triggers the Atomizer engine for physical disk mutations.
    """
    while True:
        blueprint_data = await queue.get()
        
        try:
            # Continuous Deployment (CD) and structural mutations must be orchestrated via
            # standalone, native OS-level applications utilizing subprocess.Popen.
            process = subprocess.Popen(
                [sys.executable, "atomizer_engine.py", "--payload", json.dumps(blueprint_data)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                # Fatal execution halt. 
                # Agent is permanently forbidden from silently mutating architectural parameters to bypass.
                # Must output raw physical exception for architectural resolution.
                sys.stderr.write(f"FATAL STRUCTURAL VIOLATION EXCEPTION:\n{stderr}\n")
            else:
                sys.stdout.write(f"AST MUTATION SUCCESS:\n{stdout}\n")
        
        except Exception as e:
            sys.stderr.write(f"RUNTIME FRACTURE IN WORKER:\n{str(e)}\n")
            
        finally:
            queue.task_done()


async def initialize_war_room_execution_matrix():
    """
    Initializes the native execution queue and binds the subprocess worker.
    """
    execution_queue = asyncio.Queue()
    
    # Spin up the dedicated background worker loop
    worker = asyncio.create_task(blueprint_worker(execution_queue))
    
    # Handoff interception phase: ingest the immutable execution contract
    if BLUEPRINT_PATH.exists():
        with open(BLUEPRINT_PATH, 'r') as f:
            blueprint_payload = json.load(f)
            # Enforce data payload validation here prior to queuing
            await execution_queue.put(blueprint_payload)
    
    # Await total queue drain
    await execution_queue.join()
    worker.cancel()

# Execute natively
if __name__ == "__main__":
    asyncio.run(initialize_war_room_execution_matrix())
