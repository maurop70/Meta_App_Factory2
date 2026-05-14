import asyncio
import httpx

async def test_mutate():
    async with httpx.AsyncClient() as client:
        payload = {
            "relative_path": "CFO_Agent/test_mutation.py",
            "content": "import flask\n\napp = flask.Flask(__name__)"
        }
        url = "http://localhost:8000/api/v1/atomizer/mutate"
        response = await client.post(url, json=payload)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")

if __name__ == "__main__":
    asyncio.run(test_mutate())
