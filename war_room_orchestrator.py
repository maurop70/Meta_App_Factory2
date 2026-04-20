import os
import sys
import json
import asyncio
import httpx
from datetime import datetime
from dotenv import load_dotenv
from ai_utils import generate_with_backoff_sync

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
    if agent == "CMO" and "error" not in validated:
        if not all(k in validated for k in ["perspective", "data_points"]):
            return {"error": "Validation Shield: CMO missing narrative", "raw": report}
            
    if agent == "CFO" and "report" in validated:
        inner = validated["report"]
        if not all(k in inner for k in ["fragility_index", "composite_score"]):
            return {"error": "Validation Shield: CFO missing financial indices", "raw": report}

    return validated

async def call_cfo(intent: str) -> dict:
    """Call CFO via the Dialogue Box native form."""
    try:
        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field('instruction', f"CEO DIRECTIVE: {intent}")
            async with session.post(CFO_URL, data=data, timeout=60) as resp:
                text = await resp.text()
                try:
                    return validate_report(json.loads(text), "CFO")
                except:
                    return {"error": "CFO response is not JSON", "raw": text}
    except Exception as e:
        return {"error": str(e)}

async def call_cmo(intent: str) -> dict:
    """Call CMO via the War Room endpoint."""
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "topic": intent,
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

async def call_cio(intent: str) -> dict:
    """Call CIO via the Intelligence Sweep endpoint."""
    try:
        async with aiohttp.ClientSession() as session:
            payload = {"focus_areas": [intent]}
            # Some endpoint implementations might block if a sweep is already in progress
            async with session.post(CIO_URL, json=payload, timeout=60) as resp:
                text = await resp.text()
                try:
                    return validate_report(json.loads(text), "CIO")
                except:
                    return {"error": "CIO response is not JSON", "raw": text}
    except Exception as e:
        return {"error": str(e)}

async def dispatch_to_csuite(intent: str, pre_collected_reports: dict = None):
    await sse_broadcast("RUNNING", "Routing Commander's Intent to C-Suite...", "INFO")
    
    print("\n--- CEO War Room Dispatch Started ---")
    print(f"Commander's Intent: '{intent}'")
    
    if pre_collected_reports:
        await sse_broadcast("RUNNING", "Using pre-collected agent reports for synthesis.", "INFO")
        cfo_res = validate_report(pre_collected_reports.get("CFO", {}), "CFO")
        cmo_res = validate_report(pre_collected_reports.get("CMO", {}), "CMO")
        cio_res = validate_report(pre_collected_reports.get("CIO", {}), "CIO")
    else:
        await sse_broadcast("RUNNING", "C-Suite Deliberating (CFO, CMO, CIO) concurrently...", "INFO")
        
        # Run all three HTTP requests concurrently
        cfo_task = asyncio.create_task(call_cfo(intent))
        cmo_task = asyncio.create_task(call_cmo(intent))
        cio_task = asyncio.create_task(call_cio(intent))
        
        cfo_res, cmo_res, cio_res = await asyncio.gather(cfo_task, cmo_task, cio_task)
    
    await sse_broadcast("RUNNING", "Reports received. Synthesizing CEO Strategy.", "INFO")
    
    # Bundle payloads for the CEO
    bundled_payload = {
        "CFO_Report": cfo_res,
        "CMO_Report": cmo_res,
        "CIO_Report": cio_res
    }
    
    # ── CEO Synthesis via Gemini 2.5 Cloud ──
    print("\n--- Engaging CEO Synthesis (Gemini 2.5 Cloud) ---")
    
    prompt = f"""
You are the CEO of the Antigravity Meta App Factory workspace. 
You just dispatched a Commander's Intent to your C-Suite.
Intent: "{intent}"

Here are the raw JSON reports you received back from the division heads:
CFO Report: 
{json.dumps(cfo_res, indent=2)}

CMO Report:
{json.dumps(cmo_res, indent=2)}

CIO Report:
{json.dumps(cio_res, indent=2)}

YOUR DIRECTIVE:
1. Do not repeat the reports. Synthesize them.
2. Identify cross-departmental CONTRADICTIONS (e.g. CMO wants a huge budget, CFO warns of fragility; CIO wants risky AI scaling, CFO warns of compute costs).
3. Force a decisive resolution as the CEO.
4. Output a single final unified strategy and next actions.
"""

    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print("Error: GEMINI_API_KEY is missing from environment. Cannot synthesize.")
            await sse_broadcast("FAIL", "CEO Synthesis failed: Missing API Key", "TEST_FAIL")
            return {"error": "GEMINI_API_KEY is missing from environment."}

        # ── Direct REST call via httpx (async, no subprocess, no Windows pipe) ──
        # genai.Client on Windows uses gRPC over a named pipe → WinError 233.
        # httpx uses pure TCP sockets → zero subprocess involvement.
        GEMINI_MODELS = ["gemini-2.5-pro", "gemini-2.0-flash", "gemini-1.5-flash"]
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

        print("\n================ CEO FINAL STRATEGY ================\n")
        print(ceo_strategy)
        print("\n====================================================\n")

        await sse_broadcast("PASS", "War Room deliberation complete. Strategy unified.", "TEST_PASS")
        return {"strategy": ceo_strategy}

    except Exception as e:
        print(f"CEO Synthesis failed: {e}")
        await sse_broadcast("FAIL", f"CEO Synthesis failed: {str(e)}", "TEST_FAIL")
        return {"error": str(e)}


if __name__ == "__main__":
    if len(sys.argv) > 1:
        commander_intent = " ".join(sys.argv[1:])
    else:
        commander_intent = "Stress test the entire project roadmap for 2026. Focus on minimizing AI compute burn while maximizing aggressive SaaS market capture."
        
    asyncio.run(dispatch_to_csuite(commander_intent))
