import re
import json
import os
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

load_dotenv()

app = FastAPI(title="Data-Sanitization Proxy", version="1.0.2")

EXTERNAL_GATEWAY_URL = os.getenv("EXTERNAL_LLM_GATEWAY", "https://api.openai.com/v1/chat/completions")
EXTERNAL_API_KEY = os.getenv("EXTERNAL_LLM_API_KEY", "")

REDACTION_MATRIX = [
    (r"ey[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", "[REDACTED_JWT]"),
    (r"(?i)(password|secret|key)[\s:=]+[\"'][^\"']+[\"']", r"\1: [REDACTED_SECRET]"),
    (r"(?:/[a-zA-Z0-9_.-]+)+/vault/[a-zA-Z0-9_.-]+", "[REDACTED_VAULT_PATH]")
]

def sanitize_payload(text: str) -> str:
    sanitized = text
    for pattern, replacement in REDACTION_MATRIX:
        sanitized = re.sub(pattern, replacement, sanitized)
    return sanitized

@app.post("/v1/chat/completions")
async def proxy_inference(request: Request):
    if not EXTERNAL_API_KEY:
        print("[FATAL] EXTERNAL_LLM_API_KEY is null. Ensure .env is populated.")
        raise HTTPException(status_code=500, detail="Proxy Configuration Fracture: Missing API Key.")

    try:
        payload = await request.json()
        raw_string = json.dumps(payload)
        safe_string = sanitize_payload(raw_string)
        safe_payload = json.loads(safe_string)
        print(f"[SANITIZATION PROXY] safe_payload keys: {list(safe_payload.keys())}")
        # Determine whether to route natively or via compatibility layer
        url = EXTERNAL_GATEWAY_URL
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {EXTERNAL_API_KEY}"}
        if "contents" in safe_payload:
            url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
            headers = {"Content-Type": "application/json", "x-goog-api-key": EXTERNAL_API_KEY}

        print(f"[SANITIZATION PROXY] Routing to URL: {url} with headers keys: {list(headers.keys())}")
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=safe_payload, headers=headers)
        print(f"[SANITIZATION PROXY] Received response code: {response.status_code}")
        return JSONResponse(status_code=response.status_code, content=response.json())
    except httpx.RequestError as exc:
        print(f"[SANITIZATION PROXY] Network routing fracture: {exc}")
        raise HTTPException(status_code=502, detail="Bad Gateway: External LLM unreachable.")
    except Exception as e:
        print(f"[SANITIZATION PROXY] Proxy Fracture: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Proxy Fracture: {str(e)}")

if __name__ == '__main__':
    print("[SANITIZATION PROXY] TRANSPARENT FORWARDER ONLINE. Intercepting port 5051...")
    uvicorn.run(app, host="127.0.0.1", port=5051)
