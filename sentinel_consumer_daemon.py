import asyncio
import httpx

QUEUE_URL = "http://127.0.0.1:5052/v1/queue/dequeue"
MASTER_ARCHITECT_URL = "http://127.0.0.1:5050/api/review"

async def consume_queue():
    print("[SENTINEL CONSUMER] ONLINE. Bridging Port 5052 (Queue) -> Port 5050 (Architect)...")
    async with httpx.AsyncClient(timeout=300.0) as client:  # 5-min timeout for complex architectures
        while True:
            try:
                response = await client.get(QUEUE_URL)
                if response.status_code == 200:
                    task_data = response.json().get("task", {})
                    print(f"[SENTINEL CONSUMER] Dequeued task from {task_data.get('source_node')}. Forwarding to Master Architect...")
                    
                    # Force synchronous await on Master Architect processing
                    ma_response = await client.post(MASTER_ARCHITECT_URL, json=task_data.get("payload", {}))
                    print(f"[SENTINEL CONSUMER] Master Architect processing complete. Status: {ma_response.status_code}")
                    
                elif response.status_code == 404:
                    # Queue empty, fall into CPU-idle hibernation
                    await asyncio.sleep(2.0)
                else:
                    print(f"[SENTINEL CONSUMER] Anomalous queue response: {response.status_code}")
                    await asyncio.sleep(5.0)
            except httpx.RequestError as e:
                print(f"[SENTINEL CONSUMER] Network fracture detected: {e}. Retrying in 5s...")
                await asyncio.sleep(5.0)
            except Exception as e:
                print(f"[SENTINEL CONSUMER] Fatal Execution Error: {e}")
                await asyncio.sleep(5.0)

if __name__ == "__main__":
    asyncio.run(consume_queue())
