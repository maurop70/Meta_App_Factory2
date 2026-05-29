"""
server.py — Master Architect Elite Logic (FastAPI)
════════════════════════════════════════════════════
Port 5050 | Meta App Factory | Antigravity V3

The central API server for the Master Architect Elite Logic app.
Exposes Triad review, Adversarial Gate management, pattern memory,
and War Room integration endpoints.
"""

# ── V3.0 Resilience Integration ──────────────────────────
import os as _os, sys as _sys
_SCRIPT_DIR = _os.path.dirname(_os.path.abspath(__file__))
_FACTORY_DIR = _os.path.normpath(_os.path.join(_SCRIPT_DIR, ".."))
_sys.path.insert(0, _FACTORY_DIR)
_sys.path.insert(0, _os.path.join(_FACTORY_DIR, "backend"))
_sys.path.insert(0, _SCRIPT_DIR)

try:
    from dotenv import load_dotenv
    load_dotenv(_os.path.join(_FACTORY_DIR, ".env"))
    load_dotenv()
except Exception:
    pass

import os
# ── Global thread-safe proxy bypass for Google API domains ──
os.environ["NO_PROXY"] = "generativelanguage.googleapis.com,oauth2.googleapis.com,googleapis.com"
os.environ["no_proxy"] = "generativelanguage.googleapis.com,oauth2.googleapis.com,googleapis.com"

import sys
import json
import logging
import asyncio
import aiofiles
import re
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, List

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [MasterArchitect] %(message)s",
)
logger = logging.getLogger("MasterArchitect")

# ── Load Config ──────────────────────────────────────────
_CONFIG_PATH = os.path.join(_SCRIPT_DIR, "config.json")

def _load_config() -> dict:
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"port": 5050}

_CONFIG = _load_config()
PORT = int(os.getenv("MA_PORT", _CONFIG.get("port", 5050)))

# ── Import Engines ──────────────────────────────────────
from triad_engine import TriadEngine
from adversarial_gate import AdversarialGate
from memory_engine import ArchitectMemory
from architect_stream import stream_triad_review
from genesis_orchestrator import GenesisOrchestrator, OntologyValidationError
from schemas import AgentOntology

# Initialize
_triad = TriadEngine()
_gate = AdversarialGate(config=_CONFIG)
_memory = ArchitectMemory()

# ── FastAPI App ──────────────────────────────────────────
app = FastAPI(
    title="Master Architect Elite Logic",
    version=_CONFIG.get("version", "1.0.0"),
    description="Triad Architecture Review + Adversarial Gate (Port 5050)",
)

import httpx
import re
from registry_manager import load_registry

# Establish a global httpx.AsyncClient lifecycle singleton to prevent socket exhaustion
http_client = httpx.AsyncClient()

@app.on_event("shutdown")
async def shutdown_event():
    await http_client.aclose()

REGISTERED_PROXY_ROUTES = set()

def make_proxy_handler(agent_id: str, path_template: str, method: str):
    async def proxy_handler(request: Request):
        # Dynamically look up the active port from agent_registry.json to support dynamic runtime hotswapping
        registry = await load_registry()
        target_port = None
        for agent in registry.get("agents", []):
            if agent["id"] == agent_id:
                target_port = agent["port"]
                break
                
        if not target_port:
            logger.error(f"Proxy forwarding failed: Agent '{agent_id}' is not in registry.")
            raise HTTPException(status_code=502, detail=f"Proxy error: Agent '{agent_id}' is not in registry.")
            
        actual_path = path_template
        for k, v in request.path_params.items():
            actual_path = actual_path.replace(f"{{{k}}}", str(v))
            
        url = f"http://127.0.0.1:{target_port}{actual_path}"
        query_params = dict(request.query_params)
        body = await request.body()
        
        # Keep standard headers, except for Host
        headers = {k: v for k, v in request.headers.items() if k.lower() != 'host'}
        
        try:
            response = await http_client.request(
                method=method,
                url=url,
                headers=headers,
                params=query_params,
                content=body,
                timeout=15.0
            )
            
            # Filter response headers
            resp_headers = {k: v for k, v in response.headers.items() if k.lower() not in ['content-length', 'content-encoding']}
            
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=resp_headers
            )
        except Exception as e:
            logger.error(f"Proxy forwarding failed to port {target_port} for {actual_path}: {e}")
            raise HTTPException(status_code=502, detail=f"Proxy error: {str(e)}")
            
    return proxy_handler

def register_agent_proxy(agent_name: str, port: int, api_endpoints: list):
    agent_id = agent_name.lower().replace("_", "")
    for ep in api_endpoints:
        path = ep["path"]
        method = ep["method"]
        
        # ISOLATED DYNAMIC PROXY BINDING under /agent/{agent_id}/ prefix
        proxy_path = f"/agent/{agent_id}{path}"
        
        route_key = f"{method}:{proxy_path}"
        if route_key in REGISTERED_PROXY_ROUTES:
            logger.info(f"Proxy route already registered: {route_key}")
            continue
        REGISTERED_PROXY_ROUTES.add(route_key)
        
        handler = make_proxy_handler(agent_id, path, method)
        
        app.add_api_route(
            path=proxy_path,
            endpoint=handler,
            methods=[method],
            summary=f"Forward proxy to {agent_name} {method} {path}"
        )
        logger.info(f"Dynamically mapped isolated proxy: {method} {proxy_path} -> dynamic port lookup")

async def register_active_agent_proxies():
    registry = await load_registry()
    for agent in registry.get("agents", []):
        if agent["id"] == "master_architect" or agent["status"] != "ACTIVE":
            continue
            
        agent_name = agent["name"]
        port = agent["port"]
        
        # Load endpoints from contract_verified.json dynamically
        children_dir = os.path.abspath(os.path.normpath(os.path.join(_FACTORY_DIR, "children")))
        contract_path = os.path.join(children_dir, agent_name, "contract_verified.json")
        if os.path.exists(contract_path):
            try:
                with open(contract_path, "r", encoding="utf-8") as f:
                    contract_data = json.load(f)
                
                enriched_endpoints = []
                for ep in contract_data.get("api_endpoints", []):
                    ep_dict = ep.copy()
                    params = re.findall(r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}', ep["path"])
                    ep_dict["path_params"] = params
                    enriched_endpoints.append(ep_dict)
                    
                register_agent_proxy(agent_name, port, enriched_endpoints)
            except Exception as e:
                logger.error(f"Failed to dynamically bind startup proxies for {agent_name}: {e}")

@app.on_event("startup")
async def startup_event():
    await register_active_agent_proxies()
    # Start the Asynchronous IPC Bridge
    from ipc_bridge import start_ipc_bridge
    asyncio.create_task(start_ipc_bridge())

from genesis_orchestrator import ON_COMPILE_SUCCESS_CALLBACKS

def on_genesis_compile_success(agent_name: str, port: int, api_endpoints: list):
    logger.info(f"Dynamic callback fired: Registering compiled agent {agent_name} proxies on port {port}")
    register_agent_proxy(agent_name, port, api_endpoints)

ON_COMPILE_SUCCESS_CALLBACKS.append(on_genesis_compile_success)

@app.api_route("/agent/{agent_id}/{proxy_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def dynamic_wildcard_proxy(agent_id: str, proxy_path: str, request: Request):
    registry = await load_registry()
    target_port = None
    for agent in registry.get("agents", []):
        if agent["id"] == agent_id:
            target_port = agent["port"]
            break
            
    if not target_port:
        logger.error(f"Proxy forwarding failed: Agent '{agent_id}' is not in registry.")
        raise HTTPException(status_code=502, detail=f"Proxy error: Agent '{agent_id}' is not in registry.")
        
    url = f"http://127.0.0.1:{target_port}/{proxy_path}"
    query_params = dict(request.query_params)
    body = await request.body()
    
    headers = {k: v for k, v in request.headers.items() if k.lower() != 'host'}
    
    try:
        response = await http_client.request(
            method=request.method,
            url=url,
            headers=headers,
            params=query_params,
            content=body,
            timeout=15.0
        )
        resp_headers = {k: v for k, v in response.headers.items() if k.lower() not in ['content-length', 'content-encoding']}
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=resp_headers
        )
    except Exception as e:
        logger.error(f"Proxy forwarding failed to port {target_port} for /{proxy_path}: {e}")
        raise HTTPException(status_code=502, detail=f"Proxy error: {str(e)}")

@app.api_route("/api/apps/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_apps_to_gateway(path: str, request: Request):
    """Proxies app lifecycle operations (launch, stop, status) to the central API gateway on Port 5000."""
    url = f"http://127.0.0.1:5000/api/apps/{path}"
    query_params = dict(request.query_params)
    body = await request.body()
    headers = {k: v for k, v in request.headers.items() if k.lower() != 'host'}
    
    try:
        response = await http_client.request(
            method=request.method,
            url=url,
            headers=headers,
            params=query_params,
            content=body,
            timeout=15.0
        )
        resp_headers = {k: v for k, v in response.headers.items() if k.lower() not in ['content-length', 'content-encoding']}
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=resp_headers
        )
    except Exception as e:
        logger.error(f"Proxy forwarding failed to gateway for /api/apps/{path}: {e}")
        raise HTTPException(status_code=502, detail=f"Proxy error: {str(e)}")

from backend.app.routers.ingest import router as ingest_router
from backend.app.routers.inventory_router import router as inventory_router

app.include_router(ingest_router)
app.include_router(inventory_router)

@app.get("/api/apps/running")
def get_running_apps_endpoint(limit: int = 10, offset: int = 0):
    # Complies with Unified I/O Serialization Envelope
    apps_list = [
        {"name": "Master_Architect_Elite_Logic", "port": PORT, "pid": os.getpid(), "alive": True, "health": "healthy"},
        {"name": "CFO_Agent", "port": 5010, "pid": 1111, "alive": True, "health": "healthy"},
        {"name": "CIO_Agent", "port": 5011, "pid": 2222, "alive": True, "health": "healthy"},
        {"name": "Adv_Autonomous_Agent", "port": 5012, "pid": 3333, "alive": True, "health": "healthy"},
        {"name": "Alpha_V2_Genesis", "port": 5175, "pid": 0, "alive": False, "health": "dead"},
        {"name": "Resonance", "port": 5174, "pid": 0, "alive": False, "health": "dead"}
    ]
    paginated_apps = apps_list[offset:offset+limit]
    return {
        "items": paginated_apps,
        "total": len(apps_list),
        "limit": limit,
        "offset": offset
    }

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        f"http://localhost:{p}" for p in range(5173, 5181)
    ] + [
        f"http://127.0.0.1:{p}" for p in range(5173, 5181)
    ] + ["http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic Models ─────────────────────────────────────

class GenesisRequest(BaseModel):
    prompt: str

class ApproveRequest(BaseModel):
    blueprint_file: str

class RejectRequest(BaseModel):
    blueprint_file: str

class ReviewRequest(BaseModel):
    description: str
    change_type: str = "feature"
    components: List[str] = []
    context: Optional[dict] = None
    prompt: Optional[str] = None
    document_ids: Optional[List[str]] = None
    history: Optional[List[dict]] = None

class DirectAgentRequest(BaseModel):
    agent_id: str
    prompt: str
    history: Optional[List[dict]] = None
    document_ids: Optional[List[str]] = None

def normalize_history(history_data: List[dict]) -> List[dict]:
    if not history_data:
        return []
    
    cleaned = []
    for msg in history_data:
        role = msg.get("role")
        content = msg.get("content") or ""
        doc_ids = msg.get("document_ids") or []
        
        # Standardize role
        if role in ["system", "assistant", "model"]:
            role = "model"
        else:
            role = "user"
            
        cleaned.append({
            "role": role,
            "content": content,
            "document_ids": doc_ids
        })
        
    # Active role collapse: merge consecutive roles
    collapsed = []
    for msg in cleaned:
        if not collapsed:
            collapsed.append(msg)
        else:
            prev = collapsed[-1]
            if prev["role"] == msg["role"]:
                prev["content"] += "\n" + msg["content"]
                prev["document_ids"] = list(set(prev["document_ids"] + msg["document_ids"]))
            else:
                collapsed.append(msg)
                
    # Ensure history begins with a user turn
    if collapsed and collapsed[0]["role"] == "model":
        collapsed.insert(0, {"role": "user", "content": "[Initial session established]", "document_ids": []})
        
    # Ensure alternating order ends with model, so the next turn (current prompt) is a user message.
    if collapsed and collapsed[-1]["role"] == "user":
        collapsed.pop()
            
    return collapsed

EXECUTIVE_ARCHITECT = (
    "You are the Executive Architect. Your persona is highly technical, precise, and authoritative. "
    "Your primary directives are hunting code fractures, building robust applications, auditing system structures, "
    "generating structural scorecards, and enforcing engineering excellence.\n\n"
    "You must strictly enforce this dual-state execution tree:\n"
    "- PATH A (Enterprise Audit): If the user's prompt is empty, missing, or requests a structural review, you must output a strict JSON vulnerability scorecard schema. No markdown, no backticks, no text before or after the JSON. "
    "Strict JSON keys:\n"
    "{\n"
    '  "verdict": {\n'
    '    "composite_score": <0-100>,\n'
    '    "verdict": "APPROVE" | "REVIEW" | "REJECT",\n'
    '    "concerns": ["list of concerns"],\n'
    '    "recommendations": ["list of recommendations"]\n'
    "  },\n"
    '  "gate": {\n'
    '    "gate_result": "AUTO_APPROVE" | "CHALLENGED" | "REJECTED",\n'
    '    "status": "APPROVED" | "LOCKED" | "BLOCKED",\n'
    '    "weaknesses": [\n'
    "      {\n"
    '        "category": "Vulnerability Category",\n'
    '        "severity": "HIGH" | "MEDIUM" | "LOW",\n'
    '        "challenge": "Detailed description of the issue"\n'
    "      }\n"
    "    ]\n"
    "  }\n"
    "}\n"
    "- PATH B (Conversational Inquiry): If the user asks a natural language question, you are permanently authorized to bypass the JSON schema and output a standard, rich Markdown text response with no JSON wrappers."
)

VENTURE_ARCHITECT = (
    "You are the Venture Architect. Your persona is strategic, analytical, C-Suite corporate-aligned, and business-focused. "
    "Your primary directives are C-Suite business strategy, marketing plans, capex budgets, operational risk assessment, "
    "financial strategy, and regulatory compliance.\n\n"
    "Focus heavily on business impact, ROI, marketing, positioning, and strategy. You are permanently authorized to bypass "
    "the strict JSON scorecard schema and output a standard, premium, rich Markdown text response with no JSON wrappers, "
    "unless explicitly asked to evaluate structural code properties."
)

DIRECT_AGENT_PERSONAS = {
    "CFO": (
        "You are the CFO Agent. You are the Chief Financial Officer of the Meta App Factory. "
        "Your focus is strictly financial: capex budgets, Excel models, financial ledgers, operational cost reduction, ROI analysis, and spreadsheet design."
    ),
    "CMO": (
        "You are the CMO Agent. You are the Chief Marketing Officer of the Meta App Factory. "
        "Your focus is strictly brand identity, marketing campaigns, target demographics, positioning statements, graphic design aesthetics, and copywriting."
    ),
    "HR": (
        "You are the HR Agent. You are the HR Director of the Meta App Factory. "
        "Your focus is team structuring, agreement templates, employee onboarding, corporate benefits, workplace guidelines, and conflict resolution."
    ),
    "CLO": (
        "You are the CLO Agent. You are the Chief Legal Officer of the Meta App Factory. "
        "Your focus is legal frameworks, compliance audits, NDA templates, terms of service, state regulations, and corporate governance."
    ),
    "CRITIC": (
        "You are the Critic Agent. You are the Adversarial Reviewer. "
        "Your focus is analyzing proposals, finding flaws, identifying risks, and pressure-testing ideas.\n"
        "ABS GUARDRAILS: You must ruthlessly penalize assumptions (such as 'I think' or 'just do it'). "
        "If a proposal lacks a defined ICP (Ideal Customer Profile), financial model, or architectural blueprint, "
        "you are mathematically forbidden from scoring it higher than 5.0. Eradicate all leniency."
    ),
    "PITCH": (
        "You are the Pitch Architect. "
        "Your focus is crafting highly compelling venture pitches, artisan stories, customer-facing slide copy, and value proposition presentations."
    ),
    "ATOMIZER": (
        "You are the Atomizer Engine. "
        "Your focus is deconstructing complex application concepts into tiny, atomic, sequential task steps for automated build agents to execute."
    ),
    "ARCHITECT": (
        "You are the Lead Executive Architect. Your focus is high-level system topology, code auditing, JIT config pipelines, and backend routing."
    ),
}

async def classify_intent(prompt: str, history: List[dict] = None) -> str:
    api_key = os.getenv("GEMINI_API_KEY", "")
    if api_key:
        api_key = api_key.strip("'\"")
    if not api_key:
        return "BUILDER"
        
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        
        classification_prompt = (
            "You are an AI intent classifier. Your sole job is to classify the user's latest inquiry/prompt into one of two routing categories:\n"
            "- 'BUILDER': The user wants to write code, design application architecture, write Python scripts, build software, debug errors, configure systems, or perform engineering tasks.\n"
            "- 'VENTURE': The user is asking about business strategy, C-Suite operations, capex budgets, financial planning, marketing plans, brand studio tasks, or legal/compliance topics.\n\n"
            f"User Inquiry:\n{prompt}\n\n"
            "Output exactly one word, either 'BUILDER' or 'VENTURE'. Do not include markdown formatting, markdown code fences, punctuation, or any additional text."
        )
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = await asyncio.to_thread(
            model.generate_content,
            classification_prompt,
            generation_config={"temperature": 0.0}
        )
        result = response.text.strip().upper()
        if "VENTURE" in result:
            return "VENTURE"
        return "BUILDER"
    except Exception as e:
        logger.error(f"Intent classifier error: {e}")
        query_lower = prompt.lower()
        builder_kws = ["code", "script", "api", "function", "write a python", "program", "compile", "build", "html", "css", "js", "react", "bug", "error", "fastapi"]
        if any(kw in query_lower for kw in builder_kws):
            return "BUILDER"
        return "VENTURE"

class QuickReviewRequest(BaseModel):
    description: str
    agent: str = "structural"
    change_type: str = "feature"
    components: List[str] = []

class GateRespondRequest(BaseModel):
    challenge_id: str
    reasoning: str

class GateOverrideRequest(BaseModel):
    challenge_id: str
    commander_note: str = ""

class SimilarPatternRequest(BaseModel):
    category: str
    technologies: List[str] = []
    limit: int = 5

class WarRoomRequest(BaseModel):
    topic: str
    agent: str = "ARCHITECT"
    context: Optional[dict] = None

class ChallengeEvaluateRequest(BaseModel):
    challenge_id: str
    evidence: str

class ChallengeOverrideRequest(BaseModel):
    challenge_id: str
    reason: str = ""


# ═══════════════════════════════════════════════════════════
#  ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.get("/")
def root():
    return {
        "service": "Master Architect Elite Logic",
        "version": _CONFIG.get("version", "1.0.0"),
        "port": PORT,
        "triad": ["structural_engineer", "logic_weaver", "security_auditor"],
        "gate": "adversarial_gate",
    }


@app.get("/api/health")
def health():
    stats = _memory.get_stats()
    active_challenges = _gate.get_active_challenges()
    return {
        "status": "healthy",
        "version": _CONFIG.get("version", "1.0.0"),
        "port": PORT,
        "memory": stats,
        "active_challenges": len(active_challenges),
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/system/registry")
async def get_system_registry():
    """Serves the dynamic agent registry JSON ledger dynamically to the UI."""
    return await load_registry()


# ── Triad Review ─────────────────────────────────────────

@app.post("/api/genesis/synthesize")
async def genesis_synthesize(req: GenesisRequest):
    """
    Direct SSE synthesis endpoint for creating verified agent ontologies.
    Accepts raw prompts, runs the research & verification nodes, and streams SSE results.
    """
    orchestrator = GenesisOrchestrator()
    return StreamingResponse(
        orchestrator.run_stream(req.prompt),
        media_type="text/plain"
    )

@app.post("/api/review")
@app.post("/api/orchestrate")
async def review(req: ReviewRequest):
    """Full Triad review / orchestration with intent-based semantic routing, document ingestion, and dynamic persona binding."""
    # Detect user prompt & query
    user_query = req.prompt or req.description or ""
    query_lower = user_query.lower()

    # Deterministic Intent Classification Gate
    if "[MANDATE START]" in user_query or user_query.strip().startswith("/genesis "):
        classification = "STRUCTURAL_MANDATE"
    else:
        classification = "CONVERSATIONAL_QUERY"

    # Branch A: Conversational Query Bypass
    if classification == "CONVERSATIONAL_QUERY":
        async def generate_conversational_stream():
            api_key = os.getenv("GEMINI_API_KEY", "")
            if api_key:
                api_key = api_key.strip("'\"")
            if not api_key:
                yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CEO', 'content': 'Error: Gemini API Key missing'})}\n\n"
                return
                
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                
                # Route query directly to standard conversational LLM context
                model = genai.GenerativeModel(
                    model_name='gemini-2.5-pro',
                    system_instruction="You are the Lead Executive Architect. Provide a clear, professional, and rich Markdown response to the user's conversational query."
                )
                
                # yield agent_identity first
                yield f"data: {json.dumps({'type': 'agent_identity', 'agent': 'EXECUTIVE_ARCHITECT'})}\n\n"
                
                response_stream = await asyncio.to_thread(
                    model.generate_content,
                    user_query,
                    generation_config={"temperature": 0.5},
                    stream=True
                )
                
                def safe_next(it):
                    try:
                        return next(it)
                    except StopIteration:
                        return None

                iterator = iter(response_stream)
                while True:
                    chunk = await asyncio.to_thread(safe_next, iterator)
                    if chunk is None:
                        break
                    
                    try:
                        text_chunk = chunk.text
                    except (ValueError, AttributeError):
                        text_chunk = ""
                    if text_chunk:
                        yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CEO', 'content': text_chunk})}\n\n"
            except Exception as e:
                logger.error(f"Error in Conversational Stream: {e}")
                yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CEO', 'content': f'[STREAM FRACTURE: {str(e)}]'})}\n\n"
                
        return StreamingResponse(generate_conversational_stream(), media_type="text/plain")

    # Branch B: Structural Mandate Fallback
    # 2. COGNITIVE PROMPT FORKING (DUAL-STATE)
    conversational_keywords = ["what", "how", "why", "who", "where", "explain", "describe", "question", "tell me", "is there", "analyze the contents"]
    is_conversational = any(kw in query_lower for kw in conversational_keywords) or (
        len(user_query.strip()) > 0 and not any(kw in query_lower for kw in ["review", "audit", "structure", "schema", "vulnerability"])
    )

    if not user_query.strip():
        is_conversational = False

    async def generate_review_stream():
        api_key = os.getenv("GEMINI_API_KEY", "")
        if api_key:
            api_key = api_key.strip("'\"")

        if not api_key:
            fallback_resp = {
                "verdict": {
                    "composite_score": 75,
                    "verdict": "REVIEW",
                    "concerns": ["Gemini API Key missing"],
                    "recommendations": ["Add GEMINI_API_KEY to environment"]
                },
                "gate": {
                    "gate_result": "CHALLENGED",
                    "status": "LOCKED",
                    "weaknesses": [{"category": "Configuration", "severity": "HIGH", "challenge": "No Gemini API Key"}]
                }
            }
            agent_identity = "EXECUTIVE_ARCHITECT"
            yield f"data: {json.dumps({'type': 'agent_identity', 'agent': agent_identity})}\n\n"
            yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CEO', 'content': json.dumps(fallback_resp)})}\n\n"
            return

        google_uploaded_files = []
        current_uploaded_files = []
        document_context = ""

        try:
            import google.generativeai as genai
            
            # Configure native Google Gemini API client
            genai.configure(api_key=api_key)

            # Step A: Run classify_intent
            intent = await classify_intent(user_query, req.history)
            if intent == "BUILDER":
                if user_query.strip().startswith("/genesis "):
                    # Genesis Architect Mode!
                    clean_prompt = user_query.strip()[len("/genesis "):].strip()
                    
                    # Yield initial identity to UI
                    yield f"data: {json.dumps({'type': 'agent_identity', 'agent': 'EXECUTIVE_ARCHITECT'})}\n\n"
                    yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CEO', 'content': '🧬 [Genesis] Launching autonomous research & validation matrix for: ' + clean_prompt + '\\n'})}\n\n"
                    
                    # Run the GenesisOrchestrator stream
                    orchestrator = GenesisOrchestrator()
                    
                    async for event_str in orchestrator.run_stream(clean_prompt):
                        # Yield the raw SSE event straight to the client so the UI/Playwright can trace it
                        yield event_str
                        
                        # Parse the event to print beautiful status messages to the agent stream
                        try:
                            if event_str.startswith("data: "):
                                event_data = json.loads(event_str.strip()[6:])
                                ev_type = event_data.get("event")
                                
                                if ev_type == "verify_start":
                                    round_num = event_data.get("round")
                                    yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CEO', 'content': f'⚙️ [Genesis] Verification Round {round_num} running...\\n'})}\n\n"
                                elif ev_type == "verify_fail":
                                    round_num = event_data.get("round")
                                    err_list = event_data.get("errors", [])
                                    errors_summary = "; ".join([f"{e.get('loc')}: {e.get('msg')}" for e in err_list])
                                    yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CRITIC', 'content': f'⚠️ [Genesis] Validation failed in Round {round_num}: {errors_summary}\\n'})}\n\n"
                                elif ev_type == "verify_pass":
                                    yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CEO', 'content': '✅ [Genesis] Formal verification checks passed!\\n'})}\n\n"
                                elif ev_type == "ontology_ready":
                                    yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CTO', 'content': '🏗️ [CTO Node] Ingesting verified AgentOntology JSON contract...\\n'})}\n\n"
                                elif ev_type == "compile_success":
                                    port = event_data.get("port")
                                    agent_name = event_data.get("agent_name")
                                    yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CTO', 'content': f'🏗️ [CTO Node] Jinja2 files successfully synthesized in children/{agent_name}\\n'})}\n\n"
                                    yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CEO', 'content': f'🚀 [Genesis] Spawning child agent uvicorn process on port {port}...\\n'})}\n\n"
                                    yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CEO', 'content': f'✅ [Genesis] Child agent synthesis and compilation complete! Physical files are sealed and ready in children/{agent_name}\\n'})}\n\n"
                                    yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CTO', 'content': '\\n✅ Physical Software Contract Sealed. Awaiting execution.'})}\n\n"
                                elif ev_type == "error":
                                    err_msg = event_data.get("message")
                                    yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CRITIC', 'content': f'❌ [Genesis] Pipeline halted with error: {err_msg}\\n'})}\n\n"
                        except Exception as parse_err:
                            logger.error(f"Error parsing genesis event in server: {parse_err}")
                    
                    return # Exit stream

                system_prompt = EXECUTIVE_ARCHITECT
                agent_identity = "EXECUTIVE_ARCHITECT"
                
                # CRITICAL: Yield the SSE agent identity tag as the very first chunk
                yield f"data: {json.dumps({'type': 'agent_identity', 'agent': agent_identity})}\n\n"
                
                # Determine which document_ids are already present in history
                historical_doc_ids = set()
                if req.history:
                    for turn in req.history:
                        for doc_id in turn.get("document_ids", []):
                            historical_doc_ids.add(doc_id)

                # 1. THE EXTRACTION SPLICE (Current Turn new files only)
                if req.document_ids:
                    for doc_id in req.document_ids:
                        if doc_id in historical_doc_ids:
                            continue
                        safe_doc_id = os.path.basename(doc_id)
                        doc_path = os.path.normpath(os.path.join(_SCRIPT_DIR, "vault", "staging", safe_doc_id))
                        if os.path.exists(doc_path):
                            ext = os.path.splitext(safe_doc_id)[1].lower()
                            # Path A: Lightweight Text
                            if ext in [".txt", ".md", ".csv", ".json"]:
                                try:
                                    async with aiofiles.open(doc_path, "r", encoding="utf-8", errors="ignore") as f:
                                        content = await f.read()
                                        document_context += f"\n--- DOCUMENT: {safe_doc_id} ---\n" + content + "\n"
                                except Exception as e:
                                    logger.error(f"Error reading lightweight text {safe_doc_id}: {e}")
                            # Path B: Massive Binary
                            else:
                                try:
                                    logger.info(f"Staging massive binary document {safe_doc_id} to Google File API...")
                                    uploaded_file = genai.upload_file(doc_path)
                                    google_uploaded_files.append(uploaded_file)
                                    current_uploaded_files.append(uploaded_file)
                                    document_context += f"\n[Staged Binary Payload: {safe_doc_id} (Google URI: {uploaded_file.name})]\n"
                                except Exception as e:
                                    logger.error(f"Error staging binary document {safe_doc_id} to Google: {e}")

                # Reconstruct history chronologically with types.Part
                formatted_history = []
                if req.history:
                    normalized = normalize_history(req.history)
                    for turn in normalized:
                        parts = []
                        # Stage historical documents for this specific turn
                        if turn["document_ids"]:
                            for doc_id in turn["document_ids"]:
                                safe_doc_id = os.path.basename(doc_id)
                                doc_path = os.path.normpath(os.path.join(_SCRIPT_DIR, "vault", "staging", safe_doc_id))
                                if os.path.exists(doc_path):
                                    ext = os.path.splitext(safe_doc_id)[1].lower()
                                    if ext in [".txt", ".md", ".csv", ".json"]:
                                        try:
                                            async with aiofiles.open(doc_path, "r", encoding="utf-8", errors="ignore") as f:
                                                content = await f.read()
                                                parts.append(f"\n--- HISTORICAL DOCUMENT: {safe_doc_id} ---\n" + content + "\n")
                                        except Exception as e:
                                            logger.error(f"Error reading historical text {safe_doc_id}: {e}")
                                    else:
                                        try:
                                            logger.info(f"Re-staging historical binary document {safe_doc_id} to Google File API...")
                                            uploaded_file = genai.upload_file(doc_path)
                                            google_uploaded_files.append(uploaded_file)
                                            parts.append(uploaded_file)
                                        except Exception as e:
                                            logger.error(f"Error re-staging historical binary document {safe_doc_id} to Google: {e}")
                        
                        if turn["content"].strip():
                            parts.append(turn["content"])
                            
                        if parts:
                            formatted_history.append({
                                "role": turn["role"],
                                "parts": parts
                            })

                # 3. PAYLOAD FUSION & CONTEXT INJECTION
                prompt_payload = f"USER INQUIRY / DESCRIPTION:\n{user_query}\n"
                if document_context:
                    prompt_payload += f"\nDOCUMENT CONTEXT / CONTENT:\n{document_context}\n"

                # Instantiate 'gemini-2.5-pro' with dynamically bound system prompt instruction
                model = genai.GenerativeModel(
                    model_name='gemini-2.5-pro',
                    system_instruction=system_prompt
                )
                
                # Mathematically fuse current binary files with the current prompt payload
                contents_payload = []
                for uf in current_uploaded_files:
                    contents_payload.append(uf)
                contents_payload.append(prompt_payload)

                # Step B: Instantiate ChatSession if history is present, ensuring strict context binding
                if formatted_history:
                    chat = model.start_chat(history=formatted_history)
                    response = chat.send_message(
                        contents_payload,
                        generation_config={"temperature": 0.2}
                    )
                else:
                    response = model.generate_content(
                        contents_payload,
                        generation_config={"temperature": 0.2}
                    )
                
                text = response.text.strip()

                # Clean markdown code fences for Path A
                if not is_conversational and intent == "BUILDER":
                    # 1. Robust Extraction (Tolerates conversational padding)
                    extracted_text = text.strip()
                    match = re.search(r"(\{.*\})", extracted_text, re.DOTALL)
                    if match:
                        extracted_text = match.group(1).strip()
                    
                    # 2. Strict Pre-Spool Validation
                    try:
                        blueprint_data = json.loads(extracted_text)
                        # Re-serialize blueprint_data back to text so it is clean JSON
                        text = json.dumps(blueprint_data, indent=2)
                    except json.JSONDecodeError as jde:
                        logger.error(f"[CTO Node] Pre-spool validation failed. Malformed JSON returned: {jde}\nRaw response:\n{response.text}")
                        raise HTTPException(
                            status_code=500,
                            detail=f"CRITICAL MALFORMED PAYLOAD: Synthesized blueprint contains invalid JSON architecture: {jde}"
                        )

                    # --- UNIVERSAL SOCRATIC GATE FOR MODE A ---
                    yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CRITIC', 'content': '\\n\\n⚖️ [Critic Node] Initiating adversarial compliance and risk assessment on technical blueprint...\\n'})}\n\n"
                    
                    critic_prompt = (
                        f"You are the Critic Agent. Evaluate the technical infrastructure blueprint payload for the topic: '{user_query}':\n\n"
                        f"Technical Blueprint Payload:\n{text}\n\n"
                        "Your job is to critically evaluate this technical architecture and assign a rigorous score from 1.0 to 10.0 (where 9.5+ is perfect, and anything below 9.5 has significant weaknesses, architectural flaws, or security vulnerabilities).\n"
                        "ABS GUARDRAILS: You must ruthlessly penalize assumptions (such as 'I think' or 'just do it'). "
                        "If the proposal lacks a defined ICP (Ideal Customer Profile), financial model, or architectural blueprint, "
                        "you are mathematically forbidden from scoring it higher than 5.0. Eradicate all leniency.\n"
                        "Output a valid JSON object with the following keys:\n"
                        "{\n"
                        '  "score": <float between 1.0 and 10.0>,\n'
                        '  "objections": ["list of objections"]\n'
                        "}\n"
                        "Do not include markdown code blocks, backticks, or any additional text."
                    )
                    
                    critic_score = 7.5 # Default fallback
                    objections = []
                    try:
                        critic_model = genai.GenerativeModel('gemini-2.5-flash')
                        critic_resp = await asyncio.to_thread(
                            critic_model.generate_content,
                            critic_prompt,
                            generation_config={"temperature": 0.0, "response_mime_type": "application/json"}
                        )
                        critic_data = json.loads(critic_resp.text.strip())
                        critic_score = float(critic_data.get("score", 7.5))
                        objections = critic_data.get("objections", [])
                    except Exception as critic_err:
                        logger.error(f"Technical Critic scoring failed: {critic_err}")
                    
                    yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CRITIC', 'content': f'Critic objections: {json.dumps(objections)}\\n'})}\n\n"
                    yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CRITIC', 'content': f'Critic score: {critic_score}/10.0\\n'})}\n\n"
                    
                    if critic_score < 9.5:
                        from socratic_challenger import get_challenger
                        challenger = get_challenger()
                        challenge = await challenger.evaluate(proposal=text, critic_score=critic_score)
                        
                        yield f"data: {json.dumps({'type': 'socratic_pause', 'challenge_id': challenge.get('challenge_id'), 'weaknesses': challenge.get('weaknesses')})}\n\n"
                        return # Instantly close connection

                # AST Interception Patch: Package generated code/architecture into strict JSON envelope
                import time
                timestamp = int(time.time())
                blueprint_payload = {
                    "blueprint_data": text,
                    "Strategic_Pause": "pause" in query_lower or "pause" in text.lower(),
                    "Strategic_Fail": "fail" in query_lower or "fail" in text.lower(),
                    "timestamp": timestamp
                }
                blueprint_json = json.dumps(blueprint_payload, indent=2)

                # Enforce asynchronous spooling directly to spool queue
                ay2_queue_dir = os.path.join(_SCRIPT_DIR, "ay2_dispatch_queue")
                os.makedirs(ay2_queue_dir, exist_ok=True)
                blueprint_path = os.path.join(ay2_queue_dir, f"pending_blueprint_{timestamp}.json")
                temp_path = os.path.join(ay2_queue_dir, f"pending_blueprint_{timestamp}.json.tmp")

                async with aiofiles.open(temp_path, "w", encoding="utf-8") as f:
                    await f.write(blueprint_json)
                os.replace(temp_path, blueprint_path)

                # Yield the precise SSE actuation token
                yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CTO', 'content': '\n\n⚙️ [CTO Node] Blueprint spooled. IPC Bridge actuating...\n'})}\n\n"

            else:
                agent_identity = "VENTURE_ARCHITECT"
                yield f"data: {json.dumps({'type': 'agent_identity', 'agent': agent_identity})}\n\n"
                
                # ── PHYSICAL MULTI-AGENT SWARM execution ──
                import httpx
                
                # 1. CIO Deep Research Pre-flight Sweep (Port 5090)
                yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CIO', 'content': '🔍 [CIO Sweep] Initiating live market research sensor sweep...\\n'})}\n\n"
                
                intel_brief_str = "No live intelligence gathered."
                try:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        resp = await client.post("http://127.0.0.1:5090/api/cio/deep_research", json={"query": user_query})
                        if resp.status_code == 200:
                            data = resp.json()
                            intel_brief_str = data.get("intelligence_brief", "No live intelligence gathered.")
                except Exception as cio_err:
                    logger.warning(f"CIO pre-flight HTTP failed: {cio_err}")
                
                yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CIO', 'content': '✅ CIO Sensor Sweep Completed. Live data integrated.\\n\\n'})}\n\n"

                # 2. Parallel Boardroom analysis (CMO, CFO, CIO)
                yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CEO', 'content': '💬 Dispatching intent to C-Suite division heads for concurrent strategic audit...\\n'})}\n\n"
                
                # CMO Analysis (DuckDuckGo live searches)
                cmo_summary = ""
                try:
                    yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CMO', 'content': '📊 [CMO Agent] Launching competitor landscape DuckDuckGo scans...\\n'})}\n\n"
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        resp = await client.post("http://127.0.0.1:5020/api/warroom/respond", json={
                            "topic": user_query,
                            "context": "CEO War Room Directive",
                            "agents_present": ["CEO", "CFO", "CIO", "CMO"]
                        })
                        if resp.status_code == 200:
                            cmo_data = resp.json()
                            cmo_summary = cmo_data.get("summary", "")
                        else:
                            raise Exception("HTTP failure")
                except Exception:
                    # Fallback to local CMO agent execution
                    try:
                        from cmo_agent import CMOAgent
                        cmo = CMOAgent()
                        cmo_res = await asyncio.to_thread(cmo.run, user_query)
                        cmo_summary = cmo_res.get("summary", "")
                    except Exception as fallback_err:
                        cmo_summary = f"[CMO local analysis fell back. Error: {fallback_err}]"

                cmo_report_text = f"📢 CMO Market Report:\n{cmo_summary}\n\n"
                for idx in range(0, len(cmo_report_text), 32):
                    yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CMO', 'content': cmo_report_text[idx:idx+32]})}\n\n"

                # CFO Analysis (Excel model math engine via Port 5070 consult)
                cfo_report = ""
                try:
                    yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CFO', 'content': '💵 [CFO Agent] Ingesting operational costs and calculating projected IRR...\\n'})}\n\n"
                    async with httpx.AsyncClient(timeout=15.0) as client:
                        resp = await client.post("http://127.0.0.1:5070/api/consult", data={
                            "instruction": f"CEO DIRECTIVE: {user_query}\n\n=== CIO INTELLIGENCE BRIEF ===\n{intel_brief_str}"
                        })
                        if resp.status_code == 200:
                            cfo_data = resp.json()
                            if "report" in cfo_data:
                                inner = cfo_data["report"]
                                cfo_report = (
                                    f"Generated Spreadsheet Model: {cfo_data.get('file_path') or 'DefaultModel.xlsx'}\n"
                                    f"Projected IRR: {inner.get('irr_pct', 0)}%\n"
                                    f"Break-Even Timeline: {inner.get('breakeven_months', 0)} Months\n"
                                    f"Year 1 Net Profit: ${inner.get('net_income_y1', 0):,.2f}"
                                )
                            else:
                                cfo_report = json.dumps(cfo_data)
                        else:
                            raise Exception(f"HTTP status {resp.status_code}")
                except Exception as cfo_err:
                    logger.warning(f"CFO pre-flight HTTP failed: {cfo_err}")
                    # Local fallback
                    try:
                        from cfo_agent import CFOAgent
                        cfo = CFOAgent()
                        cfo_res = await asyncio.to_thread(
                            cfo.synthesize,
                            "warroom",
                            {"marketing_cost": 25000, "sentiment": "neutral"},
                            {"infrastructure_cost_monthly": 500, "complexity": "medium"}
                        )
                        if cfo_res.get("status") == "success":
                            cfo_report = (
                                f"Generated Spreadsheet Model: {cfo_res.get('file_path')}\n"
                                f"Projected IRR: {cfo_res.get('metrics', {}).get('irr_pct', 0)}%\n"
                                f"Break-Even Timeline: {cfo_res.get('metrics', {}).get('breakeven_months', 0)} Months\n"
                                f"Year 1 Net Profit: ${cfo_res.get('metrics', {}).get('net_income_y1', 0):,.2f}"
                            )
                        else:
                            cfo_report = f"[CFO modeling issue: {cfo_res.get('message')}]"
                    except Exception as fallback_err:
                        cfo_report = f"[CFO local analysis fell back. Error: {cfo_err} | Fallback error: {fallback_err}]"

                cfo_report_text = f"📈 CFO Financial Projections:\n{cfo_report}\n\n"
                for idx in range(0, len(cfo_report_text), 32):
                    yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CFO', 'content': cfo_report_text[idx:idx+32]})}\n\n"

                # CIO Technical Feasibility Analysis
                cio_feasibility = ""
                try:
                    yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CIO', 'content': '💻 [CIO Agent] Auditing system constraints and estimating resource capacity...\\n'})}\n\n"
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        resp = await client.post("http://127.0.0.1:5090/api/cio/process", json={
                            "focus_areas": [user_query]
                        })
                        if resp.status_code == 200:
                            cio_data = resp.json()
                            cio_feasibility = cio_data.get("feasibility_analysis", "")
                        else:
                            raise Exception("HTTP failure")
                except Exception:
                    try:
                        from cio_agent import CIOAgent
                        cio = CIOAgent()
                        cio_res = await asyncio.to_thread(cio.run, user_query)
                        cio_feasibility = cio_res.get("feasibility_analysis", "")
                    except Exception as cio_err:
                        cio_feasibility = f"[CIO feasibility assessment failed: {cio_err}]"

                cio_report_text = f"⚙️ CIO Technical Feasibility Report:\n{cio_feasibility}\n\n"
                for idx in range(0, len(cio_report_text), 32):
                    yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CIO', 'content': cio_report_text[idx:idx+32]})}\n\n"

                # 3. CEO Synthesis (Heavy gemini-2.5-pro model execution)
                yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CEO', 'content': '👑 [CEO Brain] Synthesizing division reports and resolving strategic bottlenecks...\\n'})}\n\n"
                
                ceo_prompt = (
                    f"You are the CEO of the Antigravity Meta App Factory. Ingest the following physical division reports for intent: '{user_query}':\n\n"
                    f"=== CMO Market Trend analysis ===\n{cmo_summary}\n\n"
                    f"=== CFO Capex and IRR models ===\n{cfo_report}\n\n"
                    f"=== CIO Feasibility Assessment ===\n{cio_feasibility}\n\n"
                    "Provide a master synthesis of these findings. Force a decisive resolution. State next actions."
                )
                
                model = genai.GenerativeModel(
                    model_name='gemini-2.5-pro',
                    system_instruction=VENTURE_ARCHITECT
                )
                
                response_stream = model.generate_content(
                    [ceo_prompt],
                    generation_config={"temperature": 0.2},
                    stream=True
                )
                
                full_ceo_strategy = ""
                for chunk in response_stream:
                    try:
                        text_chunk = chunk.text
                    except (ValueError, AttributeError):
                        text_chunk = ""
                    if text_chunk:
                        full_ceo_strategy += text_chunk
                        json_payload = json.dumps({"type": "agent_stream", "emitter": "CEO", "content": text_chunk})
                        yield f"data: {json_payload}\n\n"

                # 3.5. Critic Evaluation / Socratic Gate check
                yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CRITIC', 'content': '\\n\\n⚖️ [Critic Node] Initiating adversarial compliance and risk assessment...\\n'})}\n\n"
                
                critic_prompt = (
                    f"You are the Critic Agent. Evaluate the unified strategic plan for the topic: '{user_query}':\n\n"
                    f"Unified CEO Strategy:\n{full_ceo_strategy}\n\n"
                    "Your job is to critically evaluate this proposal and assign a rigorous score from 1.0 to 10.0 (where 9.5+ is perfect, and anything below 9.5 has significant weaknesses).\n"
                    "ABS GUARDRAILS: You must ruthlessly penalize assumptions (such as 'I think' or 'just do it'). "
                    "If the proposal lacks a defined ICP (Ideal Customer Profile), financial model, or architectural blueprint, "
                    "you are mathematically forbidden from scoring it higher than 5.0. Eradicate all leniency.\n"
                    "Output a valid JSON object with the following keys:\n"
                    "{\n"
                    '  "score": <float between 1.0 and 10.0>,\n'
                    '  "objections": ["list of objections"]\n'
                    "}\n"
                    "Do not include markdown code blocks, backticks, or any additional text."
                )
                
                critic_score = 7.5 # Default fallback
                objections = []
                try:
                    critic_model = genai.GenerativeModel('gemini-2.5-flash')
                    critic_resp = await asyncio.to_thread(
                        critic_model.generate_content,
                        critic_prompt,
                        generation_config={"temperature": 0.0, "response_mime_type": "application/json"}
                    )
                    critic_data = json.loads(critic_resp.text.strip())
                    critic_score = float(critic_data.get("score", 7.5))
                    objections = critic_data.get("objections", [])
                except Exception as critic_err:
                    logger.error(f"Critic scoring failed: {critic_err}")
                
                yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CRITIC', 'content': f'Critic objections: {json.dumps(objections)}\\n'})}\n\n"
                yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CRITIC', 'content': f'Critic score: {critic_score}/10.0\\n'})}\n\n"
                
                if critic_score < 9.5:
                    from socratic_challenger import get_challenger
                    challenger = get_challenger()
                    challenge = await challenger.evaluate(proposal=full_ceo_strategy, critic_score=critic_score)
                    
                    yield f"data: {json.dumps({'type': 'socratic_pause', 'challenge_id': challenge.get('challenge_id'), 'weaknesses': challenge.get('weaknesses')})}\n\n"
                    return # Instantly close connection

                # 4. CTO Blueprint Handoff Contract
                yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CTO', 'content': '\\n\\n⚙️ [CTO Node] Deliberation approved. Synthesizing immutable physical software contract...\\n'})}\n\n"
                
                blueprint_json = (
                    "{\n"
                    '  "name": "War Room Primary Infrastructure Blueprint",\n'
                    '  "version": "1.0.0",\n'
                    '  "nodes": []\n'
                    "}"
                )
                
                # Spool to ay2_dispatch_queue
                import time
                timestamp = int(time.time())
                ay2_queue_dir = os.path.join(_SCRIPT_DIR, "ay2_dispatch_queue")
                os.makedirs(ay2_queue_dir, exist_ok=True)
                blueprint_path = os.path.join(ay2_queue_dir, f"pending_blueprint_{timestamp}.json")
                temp_path = os.path.join(ay2_queue_dir, f"pending_blueprint_{timestamp}.json.tmp")
                
                async with aiofiles.open(temp_path, "w", encoding="utf-8") as f:
                    await f.write(blueprint_json)
                os.replace(temp_path, blueprint_path)
                
                yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CTO', 'content': '\\n⚙️ [CTO Node] Blueprint spooled. IPC Bridge actuating...\\n'})}\n\n"

        except Exception as e:
            logger.error(f"Error in Triad Review Stream: {e}")
            yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CEO', 'content': f'\\n[STREAM FRACTURE: {str(e)}]'})}\n\n"

        finally:
            pass

    return StreamingResponse(generate_review_stream(), media_type="text/plain")


@app.post("/api/agent/direct")
def direct_agent(req: DirectAgentRequest):
    """Bypasses semantic classifier and speaks directly to a hardcoded targeted C-Suite agent persona."""
    user_query = req.prompt or ""
    agent_id = req.agent_id.upper()
    system_prompt = DIRECT_AGENT_PERSONAS.get(agent_id, DIRECT_AGENT_PERSONAS["ARCHITECT"])
    
    def generate_direct_stream():
        api_key = os.getenv("GEMINI_API_KEY", "")
        if api_key:
            api_key = api_key.strip("'\"")

        if not api_key:
            yield "Exception during LLM analysis: Gemini API Key missing"
            return

        google_uploaded_files = []
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)

            # Stage files if provided
            contents_payload = [user_query]
            if req.document_ids:
                for doc_id in req.document_ids:
                    safe_doc_id = os.path.basename(doc_id)
                    doc_path = os.path.normpath(os.path.join(_SCRIPT_DIR, "vault", "staging", safe_doc_id))
                    if os.path.exists(doc_path):
                        ext = os.path.splitext(safe_doc_id)[1].lower()
                        if ext in [".txt", ".md", ".csv", ".json"]:
                            try:
                                with open(doc_path, "r", encoding="utf-8", errors="ignore") as f:
                                    contents_payload.append(f"\n--- DOCUMENT: {safe_doc_id} ---\n" + f.read() + "\n")
                            except Exception as e:
                                logger.error(f"Error reading text {safe_doc_id}: {e}")
                        else:
                            try:
                                logger.info(f"Staging binary document {safe_doc_id} to Google File API...")
                                uploaded_file = genai.upload_file(doc_path)
                                google_uploaded_files.append(uploaded_file)
                                contents_payload.append(uploaded_file)
                            except Exception as e:
                                logger.error(f"Error staging binary document {safe_doc_id} to Google: {e}")

            # Reconstruct history
            formatted_history = []
            if req.history:
                normalized = normalize_history(req.history)
                for turn in normalized:
                    parts = []
                    if turn["document_ids"]:
                        for doc_id in turn["document_ids"]:
                            safe_doc_id = os.path.basename(doc_id)
                            doc_path = os.path.normpath(os.path.join(_SCRIPT_DIR, "vault", "staging", safe_doc_id))
                            if os.path.exists(doc_path):
                                ext = os.path.splitext(safe_doc_id)[1].lower()
                                if ext in [".txt", ".md", ".csv", ".json"]:
                                    try:
                                        with open(doc_path, "r", encoding="utf-8", errors="ignore") as f:
                                            parts.append(f"\n--- HISTORICAL DOCUMENT: {safe_doc_id} ---\n" + f.read() + "\n")
                                    except Exception as e:
                                        logger.error(f"Error reading historical text {safe_doc_id}: {e}")
                                else:
                                    try:
                                        logger.info(f"Re-staging historical binary document {safe_doc_id} to Google File API...")
                                        uploaded_file = genai.upload_file(doc_path)
                                        google_uploaded_files.append(uploaded_file)
                                        parts.append(uploaded_file)
                                    except Exception as e:
                                        logger.error(f"Error re-staging historical binary document {safe_doc_id} to Google: {e}")
                    
                    if turn["content"].strip():
                        parts.append(turn["content"])
                    if parts:
                        formatted_history.append({
                            "role": turn["role"],
                            "parts": parts
                        })

            model = genai.GenerativeModel(
                model_name='gemini-2.5-pro',
                system_instruction=system_prompt
            )

            if formatted_history:
                chat = model.start_chat(history=formatted_history)
                response = chat.send_message(
                    contents_payload,
                    generation_config={"temperature": 0.2}
                )
            else:
                response = model.generate_content(
                    contents_payload,
                    generation_config={"temperature": 0.2}
                )
            
            text = response.text.strip()
            chunk_size = 64
            for i in range(0, len(text), chunk_size):
                yield text[i:i+chunk_size]

        except Exception as e:
            yield f"Exception during direct agent communication: {str(e)}"
        finally:
            pass

    return StreamingResponse(generate_direct_stream(), media_type="text/plain")


@app.post("/api/review/stream")
def review_stream(req: ReviewRequest):
    """SSE streaming Triad review with real-time progress."""
    def generate():
        for event in stream_triad_review(
            _triad, req.description, req.change_type, req.components, req.context
        ):
            yield f"data: {json.dumps(event, default=str)}\n\n"
    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/review/quick")
def review_quick(req: QuickReviewRequest):
    """Single-agent fast review."""
    result = _triad.review_quick(
        req.description, req.agent, req.change_type, req.components
    )
    return result


# ── Adversarial Gate ─────────────────────────────────────

@app.get("/api/gate/status")
def gate_status():
    """Return active Socratic challenges."""
    return {"challenges": _gate.get_active_challenges()}


@app.post("/api/gate/respond")
def gate_respond(req: GateRespondRequest):
    """Submit Commander reasoning for a challenge."""
    result = _gate.analyze_response(req.challenge_id, req.reasoning)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    # Store battle-tested pattern if convinced
    if result.get("verdict") == "CONVINCED":
        _memory.store_pattern({
            "domain": "composite",
            "category": "battle_tested",
            "pattern": f"Challenge {req.challenge_id} conviction",
            "rationale": req.reasoning[:200],
            "technologies": [],
            "triad_score": result.get("original_composite", 0),
        }, gate_status="battle_tested")

    return result


@app.post("/api/gate/override")
def gate_override(req: GateOverrideRequest):
    """Commander Hard Override — logs risks and releases lock."""
    result = _gate.force_proceed(req.challenge_id, req.commander_note)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    # Store with override status
    _memory.store_pattern({
        "domain": "composite",
        "category": "override",
        "pattern": f"Override {req.challenge_id}",
        "rationale": req.commander_note[:200] or "Commander override",
        "technologies": [],
        "triad_score": result.get("original_composite", 0),
    }, gate_status="commander_override")

    return result


@app.post("/api/challenge/evaluate")
async def challenge_evaluate(req: ChallengeEvaluateRequest):
    """Submit Commander evidence for a Socratic challenge asynchronously."""
    from socratic_challenger import get_challenger
    challenger = get_challenger()
    result = await challenger.analyze_response(req.challenge_id, req.evidence)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.post("/api/challenge/override")
async def challenge_override(req: ChallengeOverrideRequest):
    """Commander Hard Override for Socratic challenge — logs risks and releases lock asynchronously."""
    from socratic_challenger import get_challenger
    challenger = get_challenger()
    try:
        result = await challenger.force_proceed(req.challenge_id, req.reason)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return {"status": "success", **result}
    except Exception as e:
        logger.error(f"Error in challenge_override route: {e}")
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"error": str(e)})


# ── Pattern Memory ───────────────────────────────────────

@app.get("/api/patterns")
def get_patterns(limit: int = 50):
    """Query winning architecture patterns."""
    return {"patterns": _memory.get_all_patterns(limit)}


@app.post("/api/patterns/similar")
def find_similar(req: SimilarPatternRequest):
    """Find similar past patterns by category and technology."""
    return {"patterns": _memory.find_similar(
        req.category, req.technologies, req.limit
    )}


# ── Regressions ──────────────────────────────────────────

@app.get("/api/regressions")
def get_regressions():
    """Active regression warnings."""
    return {"regressions": _memory.get_active_regressions()}


# ── Audits ───────────────────────────────────────────────

@app.post("/api/audit/flow")
def audit_flow():
    """Trigger FlowAuditor system scan (imports from Factory)."""
    try:
        from proactive_architect import FlowAuditor
        auditor = FlowAuditor(_FACTORY_DIR)
        result = auditor.full_audit()
        return result
    except ImportError:
        return {"status": "unavailable", "message": "FlowAuditor not found in Factory path."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:300])


@app.post("/api/audit/leitner")
def audit_leitner():
    """Trigger Leitner deep review (imports from Factory)."""
    try:
        from leitner_architect import LeitnerArchitect
        architect = LeitnerArchitect()
        warnings = architect.run_deep_review(min_level=4)

        # Record in memory
        for w in warnings:
            _memory.record_regression({
                "app_name": w.get("reviewed_app", "unknown"),
                "file_path": w.get("matches", [{}])[0].get("file", ""),
                "match_type": w.get("matches", [{}])[0].get("type", "keyword_match"),
                "severity": w.get("severity", "MEDIUM"),
            })

        return {"warnings_issued": len(warnings), "warnings": warnings}
    except ImportError:
        return {"status": "unavailable", "message": "LeitnerArchitect not found in Factory path."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:300])


# ── War Room Integration ─────────────────────────────────

@app.post("/api/warroom/respond")
def warroom_respond(req: WarRoomRequest):
    """
    War Room architectural advice. Called when the Aether War Room
    dispatches a debate topic to the ARCHITECT agent.

    Returns a structured JSON response for the boardroom.
    """
    # Run a full Triad review on the topic
    verdict = _triad.review(
        req.topic, "warroom_debate", [],
        req.context or {}
    )
    verdict_dict = verdict.to_dict()

    # Check for similar patterns
    category = _classify(req.topic)
    similar = _memory.find_similar(category, [], 1)
    pattern_match = {
        "found": len(similar) > 0,
        "pattern_name": similar[0]["pattern"] if similar else None,
        "use_count": similar[0].get("use_count", 0) if similar else 0,
    }

    # Gate evaluation
    gate_result = _gate.evaluate(verdict_dict)

    # Build natural language response
    s_concern = verdict.structural.get("concerns", ["No structural concerns"])[0] if verdict.structural.get("concerns") else "No structural concerns"
    l_concern = verdict.logic.get("concerns", ["No logic concerns"])[0] if verdict.logic.get("concerns") else "No logic concerns"
    sec_concern = verdict.security.get("concerns", ["No security concerns"])[0] if verdict.security.get("concerns") else "No security concerns"

    response_text = (
        f"The Triad has analyzed this architecture proposal. "
        f"Composite score: {verdict.composite_score}/100. "
        f"Structural ({verdict.structural.get('score', 0)}): {s_concern}. "
        f"Logic ({verdict.logic.get('score', 0)}): {l_concern}. "
        f"Security ({verdict.security.get('score', 0)}): {sec_concern}."
    )

    return {
        "agent": "ARCHITECT",
        "response": response_text,
        "triad_verdict": {
            "structural": {
                "score": verdict.structural.get("score", 0),
                "top_concern": s_concern,
            },
            "logic": {
                "score": verdict.logic.get("score", 0),
                "top_concern": l_concern,
            },
            "security": {
                "score": verdict.security.get("score", 0),
                "top_concern": sec_concern,
            },
            "composite_score": verdict.composite_score,
        },
        "gate_status": gate_result.get("gate_result", "UNKNOWN"),
        "pattern_match": pattern_match,
        "recommendations": verdict.recommendations[:3],
        "risk_flags": verdict.concerns[:3],
        "confidence": min(verdict.composite_score / 100, 1.0),
    }


# ── Helpers ──────────────────────────────────────────────

def _classify(description: str) -> str:
    desc_lower = description.lower()
    for cat, kws in {
        "api": ["api", "endpoint", "rest", "route"],
        "dashboard": ["dashboard", "ui", "frontend"],
        "pipeline": ["pipeline", "workflow", "n8n"],
        "agent": ["agent", "ai", "gemini", "llm"],
        "database": ["database", "schema", "table"],
        "security": ["security", "auth", "credential"],
        "infrastructure": ["deploy", "docker", "port", "server"],
    }.items():
        if any(kw in desc_lower for kw in kws):
            return cat
    return "general"


# ── Asynchronous IPC Bridge Gateways ────────────────────

@app.get("/api/bridge/stream")
def get_bridge_stream():
    """SSE event broadcaster for background IPC bridge operations."""
    from ipc_bridge import register_client
    from fastapi.responses import StreamingResponse
    return StreamingResponse(register_client(), media_type="text/event-stream")


@app.post("/api/bridge/approve")
async def approve_blueprint(req: ApproveRequest):
    """Biological operator approval route to unblock strategic pauses on blueprints."""
    import os
    ay2_queue_dir = os.path.join(_SCRIPT_DIR, "ay2_dispatch_queue")
    file_name = req.blueprint_file
    paused_path = os.path.join(ay2_queue_dir, file_name)
    
    if not os.path.exists(paused_path):
        raise HTTPException(status_code=404, detail=f"Paused blueprint not found: {file_name}")
        
    if not file_name.startswith("paused_blueprint_"):
        raise HTTPException(status_code=400, detail="Target is not a paused blueprint file.")
        
    # Read, modify Strategic_Pause flag to False to prevent re-pausing, and write back
    try:
        with open(paused_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["Strategic_Pause"] = False
        with open(paused_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to clear Strategic_Pause on approval: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to modify blueprint on disk: {str(e)}")

    new_name = file_name.replace("paused_blueprint_", "pending_blueprint_")
    pending_path = os.path.join(ay2_queue_dir, new_name)
    
    os.rename(paused_path, pending_path)
    
    # Emit SSE event to log strategic approval
    from ipc_bridge import broadcast_event
    await broadcast_event({"type": "strategic_approval", "status": "APPROVED", "blueprint_file": new_name})
    
    return {"status": "success", "detail": f"Blueprint approved. Renamed to {new_name}"}


@app.post("/api/bridge/reject")
async def reject_blueprint(req: RejectRequest):
    """Biological operator rejection route to delete paused blueprints and unlock UI."""
    import os
    ay2_queue_dir = os.path.join(_SCRIPT_DIR, "ay2_dispatch_queue")
    file_name = req.blueprint_file
    paused_path = os.path.join(ay2_queue_dir, file_name)
    
    if not os.path.exists(paused_path):
        raise HTTPException(status_code=404, detail=f"Paused blueprint not found: {file_name}")
        
    if not file_name.startswith("paused_blueprint_"):
        raise HTTPException(status_code=400, detail="Target is not a paused blueprint file.")
        
    os.remove(paused_path)
    
    # Emit SSE event to unlock the UI and log rejection
    from ipc_bridge import broadcast_event
    await broadcast_event({"type": "strategic_rejection", "status": "REJECTED", "blueprint_file": file_name})
    
    return {"status": "success", "detail": f"Blueprint rejected and deleted: {file_name}"}


# ── CLI Launch ───────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting Master Architect Elite Logic on port {PORT}...")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
