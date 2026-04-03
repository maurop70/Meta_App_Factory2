import asyncio
import websockets
import json

async def main():
    try:
        async with websockets.connect('ws://localhost:8000/ws/warroom?project=AntigravityWorkspace_Q3') as ws:
            print("Connected!")
            await ws.send(json.dumps({"type": "ping"}))
            print("Sent ping")
            res = await ws.recv()
            print("Received:", res)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    asyncio.run(main())
