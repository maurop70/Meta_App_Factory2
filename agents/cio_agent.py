import httpx
import asyncio
from fastapi import APIRouter, Request

router = APIRouter()

@router.post("/api/cio/seed")
async def ingest_cio_brief(request: Request):
    payload = await request.json()
    print("[CIO NODE] Brief compiled. Dispatching to Sentinel Queue (Port 5052)...")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "http://127.0.0.1:5052/v1/queue/enqueue",
                json={
                    "source_node": "CIO_Agent",
                    "task_type": "synthesis",
                    "payload": payload
                },
                timeout=5.0
            )
            return {"status": "asynchronous_handoff_complete", "queue_telemetry": response.json()}
        except Exception as e:
            print(f"[CIO FATAL] Broker Unreachable: {e}")
            return {"status": "fracture", "detail": str(e)}
