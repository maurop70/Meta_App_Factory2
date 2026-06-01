import httpx
import logging
from datetime import datetime

logger = logging.getLogger("phantom_core.telemetry")

class SSEDispatcher:
    """Telemetry dispatcher routing SSE events to QA stream consumers."""
    def __init__(self, channel: str):
        self.channel = channel
        self.ingest_url = "http://127.0.0.1:5030/api/qa/ingest"

    async def push(self, data: dict) -> None:
        logger.info(f"[SSEDispatcher] Broadcasting SSE Telemetry event: {data}")
        # Format payload to match standard event ingestion schema
        payload = {
            "agent": data.get("agent", "AdversarialTestAgent"),
            "message": data.get("message", f"Status update: {data.get('status')}" + (f" on {data.get('target')}" if 'target' in data else "")),
            "status": data.get("status", "INFO"),
        }
        
        # Format custom detailed messages for status updates
        if data.get("status") == "booting":
            payload["message"] = f"Igniting Ephemeral QA Sandbox for target: {data.get('target')}"
        elif data.get("status") == "executing_api_fuzzing":
            payload["message"] = f"Executing Adversarial API Fuzzing Suite (SkepticRunner)"
        elif data.get("status") == "executing_ui_fuzzing":
            payload["message"] = f"Executing Headless Playwright UI Fuzzing Suite (GhostUserRunner)"
        elif data.get("status") == "completed":
            conclusion = data.get("ledger", {}).get("conclusion", "UNKNOWN")
            payload["message"] = f"Campaign complete. Conclusion: {conclusion}"
        elif data.get("status") == "fatal_fracture":
            payload["message"] = f"Campaign halted due to a fatal fracture: {data.get('error')}"
            
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                await client.post(self.ingest_url, json=payload)
        except Exception as e:
            # Fallback to direct process memory queue if available
            try:
                from server import qa_event_broadcast
                event = {
                    "timestamp": datetime.now().isoformat(),
                    "agent": payload["agent"],
                    "message": payload["message"],
                    "status": payload["status"]
                }
                qa_event_broadcast(event)
            except Exception:
                logger.error(f"SSE Telemetry post failed: {e}")
