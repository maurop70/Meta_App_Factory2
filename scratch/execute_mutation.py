import httpx
import json
import asyncio

async def get_logs():
    print("Triggering execution...")
    async with httpx.AsyncClient() as client:
        resp = await client.post('http://localhost:5000/api/warroom/execute', json={
            'project_id': 'AntigravityWorkspace_Q3', 
            'intent': '@Operator Directive: Implement the idea from VentureScout. Problem: Small contractors are overwhelmed. Solution: A unified contractor CRM.'
        }, timeout=60.0)
        print(f"Trigger response: {resp.status_code}")
        
        print("Listening to SSE logs...")
        async with client.stream('GET', 'http://localhost:5000/api/war-room/stream?project=AntigravityWorkspace_Q3', timeout=60.0) as response:
            async for line in response.aiter_lines():
                if line.startswith('data: '):
                    try:
                        data = json.loads(line[6:])
                        if data.get('type') == 'dialogue':
                            print(f"[{data.get('agent')}] {data.get('message')}")
                        elif data.get('type') == 'state_machine':
                            print(f"[STATE] {data.get('phase')} -> {data.get('status')}")
                        
                        msg_str = str(data)
                        if 'MAX ITERATIONS REACHED' in msg_str or 'DEPLOYMENT HARD-LOCKED' in msg_str or 'DEPLOYMENT INITIATED' in msg_str:
                            break
                    except Exception:
                        pass

asyncio.run(get_logs())
