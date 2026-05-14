import asyncio
import json
import logging
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)
qa_router = APIRouter(prefix="/api/qa", tags=["QA Telemetry Watchdog"])

async def telemetry_heartbeat_stream(request: Request):
    """
    Global Event Bus Watchdog.
    Maintains the SSE connection for the React TelemetryBar and AgentStatusPanel.
    """
    try:
        while True:
            # 1. Zero-Trust Connection Verification
            if await request.is_disconnected():
                logger.info("[WATCHDOG] Global telemetry connection severed by client. Terminating loop.")
                break
            
            # 2. Synthesize the Heartbeat Payload
            payload = {
                "type": "heartbeat", 
                "status": "ONLINE",
                "agents": {
                    "CFO": "active",
                    "CMO": "active",
                    "HR": "active",
                    "CRITIC": "active",
                    "PITCH": "active",
                    "ATOMIZER": "active",
                    "ARCHITECT": "active",
                    "CLO": "active"
                }
            }
            
            yield f"data: {json.dumps(payload)}\n\n"
            
            # 3. Yield the thread back to the ASGI worker (5-second pulse)
            await asyncio.sleep(5.0) 
            
    except asyncio.CancelledError:
        logger.warning("[WATCHDOG] SSE Stream violently terminated by environment.")
        raise

@qa_router.get("/stream")
async def global_telemetry_stream(request: Request):
    """
    Natively binds to the /api/qa/stream frontend request.
    """
    return StreamingResponse(telemetry_heartbeat_stream(request), media_type="text/event-stream")
