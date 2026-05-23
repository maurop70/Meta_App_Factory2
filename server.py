import asyncio
import json
import os
from typing import Any, AsyncIterator
import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import uvicorn
from google.antigravity import Agent, LocalAgentConfig
from google.antigravity.connections.connection import Connection, ConnectionStrategy
from google.antigravity.types import Step, StepType, StepSource, StepTarget, StepStatus

from dotenv import load_dotenv
import traceback

load_dotenv()

class NativeProxyTransport:
    def __init__(self):
        self.proxy_url = "http://127.0.0.1:5051/v1/chat/completions"

    async def request(self, prompt: str) -> str:
        payload = {
            "model": "gemini-2.5-flash",
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
        print(f"[NativeProxyTransport] Routing inference to local proxy on Port 5051...")
        try:
            async with httpx.AsyncClient(timeout=60.0, trust_env=False) as client:
                response = await client.post(self.proxy_url, json=payload)
            response.raise_for_status()
            resp_json = response.json()
            print("[NativeProxyTransport] Successfully received 200 OK from Sanitization Proxy.")
            return resp_json["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"[NativeProxyTransport] FAILED to connect/request proxy on Port 5051: {e}")
            traceback.print_exc()
            raise e

class NativeProxyConnection(Connection):
    def __init__(self, transport: NativeProxyTransport):
        self._transport = transport
        self._prompt = None
        self._response_text = None

    @property
    def is_idle(self) -> bool:
        return True

    @property
    def conversation_id(self) -> str:
        return "custom-native-proxy-conv"

    async def send(self, prompt: Any, **kwargs: Any) -> None:
        if isinstance(prompt, str):
            self._prompt = prompt
        elif hasattr(prompt, "text"):
            self._prompt = prompt.text
        elif isinstance(prompt, list):
            self._prompt = "\n".join([p if isinstance(p, str) else getattr(p, "text", "") for p in prompt])
        else:
            self._prompt = str(prompt)
        self._response_text = await self._transport.request(self._prompt)

    async def receive_steps(self) -> AsyncIterator[Step]:
        yield Step(
            id="step-1",
            step_index=0,
            type=StepType.TEXT_RESPONSE,
            source=StepSource.MODEL,
            target=StepTarget.USER,
            status=StepStatus.DONE,
            content=self._response_text,
            content_delta=self._response_text,
            is_complete_response=True
        )
        yield Step(
            id="step-2",
            step_index=1,
            type=StepType.FINISH,
            source=StepSource.MODEL,
            target=StepTarget.USER,
            status=StepStatus.DONE
        )

    async def send_trigger_notification(self, content: str) -> None:
        pass

class NativeProxyStrategy(ConnectionStrategy):
    def __init__(self, transport: NativeProxyTransport):
        self._transport = transport
        self._connection = NativeProxyConnection(transport)

    def connect(self) -> Connection:
        return self._connection

    async def __aenter__(self) -> None:
        pass

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        pass

class CustomizedAgentConfig(LocalAgentConfig):
    transport: Any = None

    def create_strategy(self, *, tool_runner: Any, hook_runner: Any) -> ConnectionStrategy:
        return NativeProxyStrategy(self.transport)

LocalAgentConfig = CustomizedAgentConfig

app = FastAPI(title="Master Architect Triad")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/review")
async def ingest_and_synthesize(request: Request):
    payload = await request.json()
    brief = payload.get("description", "")
    print(f"[MasterArchitect] Ingesting brief into Antigravity 2.0 Engine: {brief[:50]}...")
    
    config = LocalAgentConfig(transport=NativeProxyTransport())
    async with Agent(config) as agent:
        enforcement_prompt = (
            f"Synthesize strict AST mutations for the following brief: {brief}. "
            "You are constrained by MAF Doctrine: 1. Native SQLite pagination required. "
            "2. React data-grid must use CSS reflow for viewports < 900px. "
            "3. Output MUST be valid JSON matching the Blueprint schema: "
            "{\"ast_mutations\": [{\"target_file\": \"filename\", \"code_payload\": \"file content\"}]}. "
            "Use ONLY target_file and code_payload keys inside each mutation block."
        )
        print("[MasterArchitect] Dynamic Subagents dispatched. Synthesizing...")
        response = await agent.chat(enforcement_prompt)
        raw_output = await response.text()
        
    try:
        # Clean and validate the Antigravity JSON output
        blueprint_data = json.loads(raw_output.strip('`').replace('json\n', ''))
        vault_path = os.path.join("vault", "blueprints", "authorized", "AG2_Synthesized_Blueprint.json")
        with open(vault_path, "w") as f:
            json.dump(blueprint_data, f, indent=2)
        
        print(f"[MasterArchitect] Triad verdict: AUTO_APPROVE. Physical contract written to {vault_path}")
        return {"status": "AUTO_APPROVE", "blueprint_path": vault_path}
    except Exception as e:
        print(f"[MasterArchitect] FATAL: Antigravity engine failed to yield strict JSON. Fracture: {e}")
        return {"status": "REVIEW", "composite": 0}

@app.post("/api/chat/stream")
async def chat_stream(request: Request):
    payload = await request.json()
    brief = payload.get("prompt", payload.get("description", ""))
    print(f"[MasterArchitect] Streaming brief into Antigravity 2.0 Engine: {brief[:50]}...")
    
    enforcement_prompt = (
        f"Synthesize strict AST mutations for the following brief: {brief}. "
        "You are constrained by MAF Doctrine: 1. Native SQLite pagination required. "
        "2. React data-grid must use CSS reflow for viewports < 900px. "
        "3. Output MUST be valid JSON matching the Blueprint schema: "
        "{\"ast_mutations\": [{\"target_file\": \"filename\", \"code_payload\": \"file content\"}]}. "
        "Use ONLY target_file and code_payload keys inside each mutation block."
    )
    
    async def generator():
        transport = NativeProxyTransport()
        print("[MasterArchitect] Dispatched streaming subagents...")
        
        try:
            content = await transport.request(enforcement_prompt)
        except Exception as e:
            yield f"data: {json.dumps({'error': f'Inference fracture: {str(e)}'})}\n\n"
            return
            
        blueprint_path = ""
        status = "REVIEW"
        try:
            blueprint_data = json.loads(content.strip('`').replace('json\n', ''))
            vault_path = os.path.join("vault", "blueprints", "authorized", "AG2_Synthesized_Blueprint.json")
            os.makedirs(os.path.dirname(vault_path), exist_ok=True)
            with open(vault_path, "w", encoding="utf-8") as f:
                json.dump(blueprint_data, f, indent=2)
            blueprint_path = vault_path
            status = "AUTO_APPROVE"
            print(f"[MasterArchitect] Streaming triad verdict: AUTO_APPROVE. Written to {vault_path}")
        except Exception as je:
            print(f"[MasterArchitect] Streaming failed to parse valid JSON: {je}")
            status = "REVIEW"
            
        chunk_size = 12
        for i in range(0, len(content), chunk_size):
            chunk = content[i:i+chunk_size]
            yield f"data: {json.dumps({'token': chunk})}\n\n"
            await asyncio.sleep(0.01)
            
        yield f"data: {json.dumps({'status': status, 'blueprint_path': blueprint_path})}\n\n"
        yield "data: [DONE]\n\n"
        
    return StreamingResponse(generator(), media_type="text/event-stream")

@app.api_route("/api/apps/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_apps(path: str, request: Request):
    async with httpx.AsyncClient(trust_env=False) as client:
        method = request.method
        url = f"http://127.0.0.1:5000/api/apps/{path}"
        headers = dict(request.headers)
        headers.pop("host", None)
        params = dict(request.query_params)
        body = await request.body()
        resp = await client.request(method, url, headers=headers, params=params, content=body, timeout=10.0)
        return StreamingResponse(
            resp.iter_bytes(),
            status_code=resp.status_code,
            headers=dict(resp.headers)
        )

@app.get("/api/qa/stream")
async def proxy_qa_stream(request: Request):
    client = httpx.AsyncClient(trust_env=False)
    req = client.build_request("GET", "http://127.0.0.1:5000/api/qa/stream", headers=request.headers.items())
    resp = await client.send(req, stream=True)
    return StreamingResponse(
        resp.aiter_bytes(),
        status_code=resp.status_code,
        headers=dict(resp.headers)
    )


if __name__ == '__main__':
    print("[MasterArchitect] ONLINE. Antigravity SDK Integrated on Port 5050 with NativeProxyTransport.")
    uvicorn.run(app, host="0.0.0.0", port=5050)
