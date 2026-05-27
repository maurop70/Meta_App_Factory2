import asyncio
import json
import logging
from datetime import datetime
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)
qa_router = APIRouter(prefix="/api/qa", tags=["QA Telemetry Watchdog"])

# Global event queue for dynamic real-time streaming
QA_EVENT_QUEUE = []

def push_qa_event(agent: str, message: str, status: str, filename: str = None, score: int = None):
    """
    Pushes a high-priority event to the global SSE stream event queue.
    """
    event = {
        "agent": agent,
        "message": message,
        "status": status,
        "timestamp": datetime.now().isoformat()
    }
    if filename:
        event["filename"] = filename
    if score is not None:
        event["score"] = score
    QA_EVENT_QUEUE.append(event)
    logger.info(f"[QA TELEMETRY QUEUE] Event pushed: {event}")

async def telemetry_heartbeat_stream(request: Request):
    """
    Global Event Bus Watchdog.
    Maintains the SSE connection and yields heartbeat + real-time QA events.
    """
    heartbeat_timer = 0
    try:
        while True:
            # 1. Zero-Trust Connection Verification
            if await request.is_disconnected():
                logger.info("[WATCHDOG] Global telemetry connection severed by client. Terminating loop.")
                break
            
            # 2. Yield any queued events immediately
            while QA_EVENT_QUEUE:
                event = QA_EVENT_QUEUE.pop(0)
                yield f"data: {json.dumps(event)}\n\n"
            
            # 3. Yield heartbeat payload every 5 seconds
            if heartbeat_timer >= 5.0:
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
                heartbeat_timer = 0
                
            await asyncio.sleep(0.5)
            heartbeat_timer += 0.5
            
    except asyncio.CancelledError:
        logger.warning("[WATCHDOG] SSE Stream violently terminated by environment.")
        raise

@qa_router.get("/stream")
async def global_telemetry_stream(request: Request):
    """
    Natively binds to the /api/qa/stream frontend request.
    """
    return StreamingResponse(telemetry_heartbeat_stream(request), media_type="text/event-stream")
