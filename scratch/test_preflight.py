import httpx
import asyncio

async def test_preflight():
    url = "http://localhost:8000/api/v1/qa/engine/pre-flight"
    payload = {
        "target_path": "CFO_Agent/server.py",
        "content": "import flask\n\napp = flask.Flask(__name__)"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload)
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.json()}")
        except Exception as e:
            print(f"Request failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_preflight())
