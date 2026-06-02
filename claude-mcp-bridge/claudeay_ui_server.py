"""
ClaudeAY Web UI Server
----------------------
Lightweight FastAPI server serving the ClaudeAY standalone
web interface on port 9002. Bridges the browser UI to the
MCP bridge, loop engine, and Antigravity API.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import json
import asyncio
import logging
from pathlib import Path
from datetime import datetime

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

# Add bridge root to path
BRIDGE_ROOT = Path(__file__).parent
sys.path.insert(0, str(BRIDGE_ROOT))
sys.path.insert(0, str(BRIDGE_ROOT.parent))

from shared_modules.dispatch_queue import dispatch_mandate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ClaudeAY-UI")

app = FastAPI(title="ClaudeAY Web UI", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

TELEMETRY_LOG  = BRIDGE_ROOT / "logs" / "telemetry.jsonl"
LOOP_LOG       = BRIDGE_ROOT / "logs" / "loop_history.jsonl"
RULES_PATH     = BRIDGE_ROOT / "rules" / "CLAUDE_RULES.md"

# SSE clients for streaming loop output to browser
sse_clients: list = []


@app.on_event("startup")
async def startup_event():
    """Clear stale telemetry log on startup."""
    import os
    telemetry_log = TELEMETRY_LOG
    if telemetry_log.exists():
        telemetry_log.write_text("")  # clear stale events on startup


def _read_jsonl(path: Path, n: int) -> list:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        return [json.loads(l) for l in lines[-n:] if l.strip()]
    except Exception:
        return []


@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """Serve the ClaudeAY web interface."""
    html_path = BRIDGE_ROOT / "claudeay_ui.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>claudeay_ui.html not found</h1>", status_code=404)


@app.get("/api/status")
async def get_status():
    """System status for the UI."""
    import socket
    mcp_online = False
    try:
        s = socket.create_connection(("localhost", 9001), timeout=1)
        s.close()
        mcp_online = True
    except Exception:
        pass

    telemetry = _read_jsonl(TELEMETRY_LOG, 20)
    loop_events = _read_jsonl(LOOP_LOG, 10)

    def _is_maf_critical(e):
        if e.get("type") not in ("console_error", "page_error", "request_failed"):
            return False
        url = (
            e.get("url") or
            e.get("data", {}).get("url", "") or
            e.get("params", {}).get("response", {}).get("url", "") or
            ""
        )
        if any(domain in str(url) for domain in 
               ("claude.ai", "anthropic.com", "assets-proxy.anthropic.com")):
            return False
        if not url and e.get("type") in ("console_error", "page_error"):
            return False
        return True

    critical = [e for e in telemetry if _is_maf_critical(e)]

    return JSONResponse({
        "mcp_online": mcp_online,
        "rules_loaded": RULES_PATH.exists(),
        "rules_lines": RULES_PATH.read_text(encoding="utf-8").count("\n")
                       if RULES_PATH.exists() else 0,
        "critical_errors": len(critical),
        "total_events": len(telemetry),
        "recent_errors": critical[-3:],
        "recent_loop": loop_events[-5:],
    })


@app.post("/api/execute")
async def execute_intent(request: Request):
    """Execute a user intent through the ClaudeAY loop."""
    body = await request.json()
    intent = body.get("intent", "").strip()
    if not intent:
        return JSONResponse({"error": "No intent provided"}, status_code=400)

    async def stream():
        try:
            from dispatcher import AntigravityDispatcher
            from ay_client import send_mandate
            from loop_engine import load_recent_telemetry
            from intent_router import classify_intent

            yield f"data: {json.dumps({'type': 'status', 'content': 'Classifying intent...'})}\n\n"

            engine = await classify_intent(intent)
            yield f"data: {json.dumps({'type': 'engine', 'engine': engine})}\n\n"
            yield f"data: {json.dumps({'type': 'status', 'content': f'Routing to {engine}...'})}\n\n"

            dispatcher = AntigravityDispatcher()
            telemetry = load_recent_telemetry()

            mandate = dispatcher.build_prompt(
                instruction=intent,
                telemetry=telemetry if telemetry.get("total_events", 0) > 0 else None,
            )

            yield f"data: {json.dumps({'type': 'status', 'content': 'Sending mandate to Antigravity...'})}\n\n"

            ledger = await asyncio.to_thread(send_mandate, mandate)

            for line in ledger.split("\n"):
                if line.strip():
                    yield f"data: {json.dumps({'type': 'output', 'content': line})}\n\n"
                    await asyncio.sleep(0.02)

            yield f"data: {json.dumps({'type': 'complete', 'content': 'Mandate complete.'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


@app.get("/api/telemetry")
async def get_telemetry():
    """Return recent telemetry for the UI."""
    events = _read_jsonl(TELEMETRY_LOG, 50)
    return JSONResponse({"events": events})


@app.post("/api/loop/start")
async def loop_start_proxy(request: Request):
    import httpx
    try:
        body = await request.json()
    except Exception:
        body = {}
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post("http://localhost:5050/api/loop/start", json=body, timeout=30.0)
            return JSONResponse(status_code=resp.status_code, content=resp.json())
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": f"Failed to reach loop server: {e}"})


@app.get("/api/loop/status")
async def loop_status_proxy():
    import httpx
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get("http://localhost:5050/api/loop/status", timeout=10.0)
            return JSONResponse(status_code=resp.status_code, content=resp.json())
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": f"Failed to reach loop server: {e}"})


@app.post("/api/loop/approve")
async def loop_approve_proxy(request: Request):
    import httpx
    try:
        body = await request.json()
    except Exception:
        body = {}
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post("http://localhost:5050/api/loop/approve", json=body, timeout=10.0)
            return JSONResponse(status_code=resp.status_code, content=resp.json())
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": f"Failed to reach loop server: {e}"})


@app.post("/api/dispatch")
async def dispatch_to_queue(request: Request):
    """
    Allows ClaudeAY to dispatch mandates directly to ay2_dispatch_queue
    without human transport between UI instances.
    """
    try:
        body = await request.json()
        mandate_text = body.get("mandate", "").strip()

        if not mandate_text:
            return JSONResponse(
                status_code=400,
                content={"error": "mandate is required"}
            )

        filename = dispatch_mandate(mandate_text, source="ClaudeAY")

        return JSONResponse(content={
            "status": "queued",
            "blueprint": filename
        })
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


if __name__ == "__main__":
    print("ClaudeAY Web UI starting on http://localhost:9002")
    uvicorn.run(app, host="0.0.0.0", port=9002, log_level="warning")
