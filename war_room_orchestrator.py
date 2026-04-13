import os
import sys
import json
import asyncio
import aiohttp
from datetime import datetime
from dotenv import load_dotenv
from google import genai

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
        "node": node,
        "result": result,
        "timestamp": datetime.now().isoformat()
    }
    print(f"[Ghost Stream] {status} | {node}")
    try:
        async with aiohttp.ClientSession() as session:
            await session.post(GHOST_STREAM_URL, json=payload, timeout=2)
    except Exception as e:
        print(f"  [Ghost Stream Error] {e}")

async def call_cfo(intent: str) -> dict:
    """Call CFO via the Dialogue Box native form."""
    try:
        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field('instruction', f"CEO DIRECTIVE: {intent}")
            async with session.post(CFO_URL, data=data, timeout=60) as resp:
                text = await resp.text()
                try:
                    return json.loads(text)
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
                    return json.loads(text)
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
                    return json.loads(text)
                except:
                    return {"error": "CIO response is not JSON", "raw": text}
    except Exception as e:
        return {"error": str(e)}

async def dispatch_to_csuite(intent: str):
    await sse_broadcast("RUNNING", "Routing Commander's Intent to C-Suite...", "INFO")
    
    print("\n--- CEO War Room Dispatch Started ---")
    print(f"Commander's Intent: '{intent}'")
    
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

Here are the raw JSON reports you received back concurrently from the division heads:
CFO Report (Financial/Fragility Risk): 
{json.dumps(cfo_res, indent=2)}

CMO Report (Go-to-Market/Brand Strategy):
{json.dumps(cmo_res, indent=2)}

CIO Report (Tech Frontier/Competitor Analysis):
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

        # New GenAI SDK instantiation
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-2.5-pro',
            contents=prompt
        )
        ceo_strategy = response.text
        
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
