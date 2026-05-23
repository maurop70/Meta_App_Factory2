import asyncio
from fastapi import FastAPI, HTTPException
import uvicorn
from pydantic import BaseModel
from typing import Any, Dict

app = FastAPI(title="Sentinel Queue Broker", version="1.0.0")

task_queue = asyncio.Queue()

class TaskPayload(BaseModel):
    source_node: str
    task_type: str
    payload: Dict[str, Any]

@app.post("/v1/queue/enqueue")
async def enqueue_task(task: TaskPayload):
    await task_queue.put(task.model_dump())
    print(f"[SENTINEL QUEUE] Task ingested from {task.source_node}. Queue depth: {task_queue.qsize()}")
    return {"status": "queued", "queue_depth": task_queue.qsize()}

@app.get("/v1/queue/dequeue")
async def dequeue_task():
    if task_queue.empty():
        raise HTTPException(status_code=404, detail="Queue empty")
    task = await task_queue.get()
    task_queue.task_done()
    print(f"[SENTINEL QUEUE] Task dispatched to Master Architect.")
    return {"status": "success", "task": task}

if __name__ == '__main__':
    print("[SENTINEL QUEUE] ONLINE. Saturation Governors active on port 5052...")
    uvicorn.run(app, host="127.0.0.1", port=5052)
