import httpx
import asyncio
from fastapi import APIRouter, Request

router = APIRouter()

@router.post("/api/warroom/threat")
async def ingest_adversarial_threat(request: Request):
    payload = await request.json()
    print("[WAR ROOM NODE] Threat model ingested. Dispatching to Sentinel Queue (Port 5052)...")

    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "http://127.0.0.1:5052/v1/queue/enqueue",
                json={
                    "source_node": "WarRoom_Agent",
                    "task_type": "adversarial_review",
                    "payload": payload
                },
                timeout=5.0
            )
            return {"status": "asynchronous_handoff_complete", "queue_telemetry": response.json()}
        except Exception as e:
            print(f"[WAR ROOM FATAL] Broker Unreachable: {e}")
            return {"status": "fracture", "detail": str(e)}
