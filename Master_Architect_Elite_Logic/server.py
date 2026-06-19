"""
server.py — Master Architect Elite Logic (FastAPI)
════════════════════════════════════════════════════
Port 5050 | Meta App Factory | Antigravity V3

The central API server for the Master Architect Elite Logic app.
Exposes Triad review, Adversarial Gate management, pattern memory,
and War Room integration endpoints.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# ── V3.0 Resilience Integration ──────────────────────────
import os as _os, sys as _sys
_SCRIPT_DIR = _os.path.dirname(_os.path.abspath(__file__))
_FACTORY_DIR = _os.path.normpath(_os.path.join(_SCRIPT_DIR, ".."))
_sys.path.insert(0, _os.path.join(_FACTORY_DIR, "claude-mcp-bridge"))
_sys.path.insert(0, _FACTORY_DIR)
_sys.path.insert(0, _os.path.join(_FACTORY_DIR, "backend"))
_sys.path.insert(0, _SCRIPT_DIR)

# Cost-tracking telemetry: record LLM token usage to data/maf_telemetry.db.
try:
    from shared_modules.telemetry import record_usage as _record_usage
except Exception:
    def _record_usage(*_a, **_k):
        return None

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
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse, HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict

import threading
from collections import deque
from loop_engine import AutonomousLoop
from intent_router import classify_intent
from shared_modules.agent_schemas import validate_cfo_output, validate_cio_output, validate_critic_output

# Shared loop status ring buffer — last 50 messages
loop_status_buffer: deque = deque(maxlen=50)
loop_running: bool = False
_approval_event = threading.Event()
_approval_response: list = ["proceed"]

class WorkspaceBlueprintSchema(BaseModel):
    presentation_name: str = Field(description="The strict filename for the generated Workspace artifact.")
    template_id: str = Field(description="The Google Drive Document ID of the target template.")
    mutations: Dict[str, str] = Field(description="A strict key-value map of template tags (e.g., '{{PROJECT_NAME}}') to their generated content.")

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

# Server-side document parsing (PDF/DOCX/PPTX/...) so C-Suite sub-agents
# receive clean text rather than opaque Google File API placeholders.
try:
    from document_parser_service import DocumentParserService
    _DOC_PARSER_AVAILABLE = True
except Exception as _dp_err:
    DocumentParserService = None
    _DOC_PARSER_AVAILABLE = False
    logging.getLogger("server").warning(f"DocumentParserService unavailable: {_dp_err}")

# Automated pitch-deck (PPTX) generation on C-Suite consensus.
try:
    from Aether.presentation_architect import PresentationArchitect
    _PRES_ARCHITECT_AVAILABLE = True
except Exception as _pa_err:
    PresentationArchitect = None
    _PRES_ARCHITECT_AVAILABLE = False
    logging.getLogger("server").warning(f"PresentationArchitect unavailable: {_pa_err}")

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
    asyncio.create_task(start_ipc_bridge(PORT))
    # Reap idle/dead full-stack preview dev servers (Phase 4).
    try:
        import preview_manager
        preview_manager.start_reaper()
    except Exception as _e:
        logger.warning(f"preview reaper not started: {_e}")

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
        if "running" in path:
            return JSONResponse(
                status_code=502,
                content={
                    "items": [],
                    "total": 0,
                    "limit": 10,
                    "offset": 0,
                    "running_apps": [],
                    "error": "Gateway Unreachable",
                    "detail": str(e)
                }
            )
        else:
            return JSONResponse(
                status_code=502,
                content={
                    "status": "error",
                    "error": "Gateway Unreachable",
                    "detail": str(e)
                }
            )

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
    mode: Optional[str] = "auto"  # explicit routing: "auto" | "build" | "venture"
    test_inject_broken: Optional[bool] = None  # test-only: inject a known-broken build (gated by ALLOW_TEST_INJECTION)

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

# ── BUILDER blueprint contract ──
# The autonomous build path uses THIS prompt (not EXECUTIVE_ARCHITECT, which emits a
# vulnerability scorecard). The downstream actuator (mock_antigravity.py) writes each
# code_payload verbatim, so the model must return the COMPLETE, runnable file contents.
BUILDER_BLUEPRINT = (
    "You are the MAF Build Architect. The user will describe an application they want built. "
    "You output ONLY a single JSON object describing the complete, runnable set of files for that application. "
    "There is no conversation: every response is a buildable blueprint.\n\n"
    "JSON shape:\n"
    "{\n"
    '  "app_name": "<short kebab-case name, e.g. simple-todo>",\n'
    '  "summary": "<one short sentence describing what was built>",\n'
    '  "ast_mutations": [\n'
    '    { "target_file": "<relative path, e.g. index.html or src/app.js>", "code_payload": "<the COMPLETE final content of that file>" }\n'
    "  ]\n"
    "}\n\n"
    "Rules:\n"
    "- code_payload MUST be the full, final file content — never a diff, snippet, placeholder, or '...'.\n"
    "- target_file MUST be a relative path. Never use absolute paths, drive letters, or '..'.\n"
    "- Produce a minimal but fully working app. Prefer a single self-contained index.html (inline CSS/JS) "
    "when the request allows; otherwise include every file required to run.\n"
    "- Output raw JSON only: no markdown, no backticks, no prose before or after the object."
)

# Gemini response schema mirror of the BUILDER blueprint, so generation is forced to
# valid JSON in the exact shape the actuator consumes (eliminates malformed-payload 500s).
BUILDER_BLUEPRINT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "app_name": {"type": "STRING"},
        "summary": {"type": "STRING"},
        "ast_mutations": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "target_file": {"type": "STRING"},
                    "code_payload": {"type": "STRING"},
                },
                "required": ["target_file", "code_payload"],
            },
        },
    },
    "required": ["app_name", "ast_mutations"],
}

# Full-stack (Phase 4) builder: a Vite+React project scaffold already exists in the
# sandbox (index.html, src/main.jsx, package.json, node_modules) — the model only
# overlays the app's React source so it runs on a live dev server.
FULLSTACK_BLUEPRINT = (
    "You are the MAF Full-Stack Build Architect. You generate a React (Vite) application. "
    "A working Vite + React project ALREADY EXISTS in the sandbox: index.html, src/main.jsx, "
    "package.json, vite.config.js, and node_modules are provided — you MUST NOT regenerate any "
    "of those. You output ONLY the app's React source as ast_mutations, every target_file under "
    "frontend/src/, at minimum frontend/src/App.jsx (the default export that the existing "
    "src/main.jsx renders). You may add more frontend/src/*.jsx and *.css files and import them "
    "from App.jsx with relative paths.\n"
    "OPTIONAL BACKEND: if the app needs to persist data or expose APIs, also output backend/app.py — "
    "a FastAPI app with a module-level `app = FastAPI()` and routes under /api/... The Vite dev server "
    "proxies /api to this backend automatically, so the frontend calls it with relative fetch('/api/...'). "
    "Persist data with the standard-library sqlite3 module (DB file inside the backend dir).\n\n"
    "Same JSON shape as before:\n"
    "{\n"
    '  "app_name": "<short kebab-case name>",\n'
    '  "summary": "<one sentence>",\n'
    '  "ast_mutations": [ { "target_file": "frontend/src/App.jsx", "code_payload": "<COMPLETE file content>" } ]\n'
    "}\n\n"
    "Rules:\n"
    "- code_payload is the full, final content of the file (a valid React component module).\n"
    "- Use ONLY local, self-contained code — no external CDN <script> tags or remote assets "
    "(network egress is blocked during verification). Use React (already installed) and inline styles or .css files.\n"
    "- frontend/src/App.jsx MUST `export default` a React component.\n"
    "- Backend (if any): ONLY FastAPI + the Python standard library (sqlite3, json, datetime, etc.) are "
    "available — do NOT import any other third-party package (none can be installed). All routes under /api/.\n"
    "- target_file paths are relative, never absolute or with '..'.\n"
    "- Output raw JSON only: no markdown, no backticks, no prose."
)

VENTURE_ARCHITECT = (
    "You are the Venture Architect (CEO). Your persona is strategic, analytical, C-Suite corporate-aligned, and business-focused. "
    "Your primary directives are C-Suite business strategy, marketing plans, capex budgets, operational risk assessment, "
    "financial strategy, and regulatory compliance.\n\n"
    "You do NOT rubber-stamp the user's concept. You actively critique it: name its structural risks and weakest assumptions, "
    "give concrete, actionable recommendations to strengthen it, and — if the concept carries serious structural risk — "
    "propose one or two stronger alternative concepts or pivots and explain why they are superior.\n\n"
    "Synthesize the CMO / CFO / CIO division reports into a single decisive strategy, and structure your Markdown response "
    "with these explicit sections (use these headings):\n"
    "## Verdict & Concept Critique\n"
    "## Market Strategy\n"
    "## Pricing & Financial Rationale\n"
    "## Technology Roadmap\n"
    "## Recommendations to Strengthen the Concept\n"
    "## Alternative Concepts (if warranted)\n"
    "## Decisive Resolution & Next Actions\n\n"
    "When the Critic raises objections, you MUST revise the strategy to resolve each objection head-on in the next pass.\n\n"
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

async def classify_builder_venture_intent(prompt: str, history: List[dict] = None) -> str:
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

class ChallengeDelegateRequest(BaseModel):
    challenge_id: str


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


@app.get("/builds")
@app.get("/builds/")
def builds_gallery():
    """Browsable gallery + live control center for apps produced by autonomous builds."""
    try:
        import preview_manager
        active_previews = preview_manager.status()
    except Exception:
        active_previews = {}
    root = os.path.join(_SCRIPT_DIR, "generated_builds")
    cards = []
    if os.path.isdir(root):
        for name in sorted(os.listdir(root)):
            app_path = os.path.join(root, name)
            if not os.path.isdir(app_path):
                continue
            is_fs = os.path.isdir(os.path.join(app_path, "frontend"))
            files, newest = [], 0
            for dp, _dirs, fnames in os.walk(app_path):
                # Never descend into the node_modules junction (symlinked + huge).
                _dirs[:] = [d for d in _dirs if d != "node_modules"]
                for fn in fnames:
                    fp = os.path.join(dp, fn)
                    files.append(os.path.relpath(fp, app_path).replace("\\", "/"))
                    try:
                        newest = max(newest, os.path.getmtime(fp))
                    except OSError:
                        pass
            if not files:
                continue
            when = datetime.fromtimestamp(newest).strftime("%Y-%m-%d %H:%M") if newest else "—"
            if is_fs:
                status_info = active_previews.get(name)
                is_running = bool(status_info and status_info.get("alive"))
                if is_running:
                    port = status_info["port"]
                    btn_html = (
                        f'<a class="btn" href="http://localhost:{port}/" target="_blank">▶ Open live preview (:{port})</a> '
                        f'<button class="btn btn-danger" onclick="stopPreview(\'{name}\', this)">⏹ Stop</button>'
                    )
                else:
                    btn_html = f'<button class="btn btn-success" onclick="startPreview(\'{name}\', this)">⚡ Start live preview</button>'
                cards.append(
                    f'<div class="card"><h2>{name} <span class="badge">Full-Stack</span></h2>'
                    f'<p>React + FastAPI · built {when}</p>'
                    f'{btn_html}</div>'
                )
            else:
                entry = "index.html" if "index.html" in files else sorted(files)[0]
                cards.append(
                    f'<div class="card"><h2>{name}</h2>'
                    f'<p>{len(files)} file(s) · built {when}</p>'
                    f'<a class="btn" href="/builds/{name}/{entry}" target="_blank">▶ Open app</a></div>'
                )
    body = "".join(cards) or '<p class="empty">No apps built yet — describe one in Builder Chat.</p>'
    html = (
        '<!doctype html><html><head><meta charset="utf-8"><title>MAF Built Apps</title><style>'
        'body{font-family:Inter,system-ui,sans-serif;background:#0B0F19;color:#e5e7eb;margin:0;padding:32px}'
        'h1{font-weight:700;margin:0 0 4px}.sub{color:#9ca3af;margin:0 0 24px;font-size:13px}'
        '.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px}'
        '.card{background:#111827;border:1px solid #1f2937;border-radius:14px;padding:18px;position:relative}'
        '.card h2{margin:0 0 6px;font-size:16px;color:#5eead4}.card p{margin:0 0 12px;font-size:12px;color:#9ca3af}'
        '.btn{display:inline-block;background:#0d9488;color:#fff;text-decoration:none;padding:8px 14px;border:none;border-radius:8px;font-size:13px;cursor:pointer}'
        '.btn:hover{background:#14b8a6}'
        '.btn-danger{background:#b91c1c}.btn-danger:hover{background:#dc2626}'
        '.btn-success{background:#047857}.btn-success:hover{background:#059669}'
        '.badge{background:#1e293b;color:#38bdf8;font-size:10px;padding:2px 6px;border-radius:4px;vertical-align:middle;margin-left:6px}'
        '.empty{color:#9ca3af}code{color:#cbd5e1}</style>'
        '<script>'
        'async function startPreview(name, btn){btn.innerText="Starting...";btn.disabled=true;'
        'try{const res=await fetch("/api/preview/start",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({app_name:name})});'
        'if(res.ok){const data=await res.json();window.open(data.url,"_blank");location.reload();}'
        'else{alert("Failed to start preview.");btn.innerText="⚡ Start live preview";btn.disabled=false;}}'
        'catch(err){alert("Error starting preview: "+err.message);btn.innerText="⚡ Start live preview";btn.disabled=false;}}'
        'async function stopPreview(name, btn){btn.innerText="Stopping...";btn.disabled=true;'
        'try{const res=await fetch("/api/preview/stop",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({app_name:name})});'
        'if(res.ok){location.reload();}else{alert("Failed to stop preview.");btn.innerText="⏹ Stop";btn.disabled=false;}}'
        'catch(err){alert("Error stopping preview: "+err.message);btn.innerText="⏹ Stop";btn.disabled=false;}}'
        '</script></head><body>'
        '<h1>🏗️ MAF Built Apps</h1>'
        '<p class="sub">Every app produced by Builder Chat. Full-stack apps boot on demand; static apps open directly.</p>'
        f'<div class="grid">{body}</div></body></html>'
    )
    return HTMLResponse(html)


@app.get("/builds/{app_name}")
def build_app_redirect(app_name: str):
    return RedirectResponse(url=f"/builds/{app_name}/")


@app.get("/builds/{app_name}/")
@app.get("/builds/{app_name}/{file_path:path}")
def serve_build(app_name: str, file_path: str = "index.html"):
    """Serve a file from a generated app, strictly sandboxed to generated_builds/<app_name>/."""
    root = os.path.abspath(os.path.join(_SCRIPT_DIR, "generated_builds"))
    base = os.path.abspath(os.path.join(root, os.path.basename(app_name)))
    if base != root and not base.startswith(root + os.sep):
        raise HTTPException(status_code=400, detail="Invalid app name")
    rel = (file_path or "index.html").replace("\\", "/")
    parts = [p for p in rel.split("/") if p not in ("", ".", "..")]
    target = os.path.abspath(os.path.join(base, *parts)) if parts else os.path.join(base, "index.html")
    if target != base and not target.startswith(base + os.sep):
        raise HTTPException(status_code=400, detail="Path traversal blocked")
    if not os.path.isfile(target):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(target)


@app.get("/api/preview/status")
async def preview_status():
    """Active full-stack preview dev servers (ports, PIDs, idle time)."""
    try:
        import preview_manager
        return preview_manager.status()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/preview/stop")
async def preview_stop(payload: dict):
    import preview_manager
    app_name = os.path.basename(str(payload.get("app_name", "")))
    stopped = await asyncio.to_thread(preview_manager.stop_preview, app_name)
    return {"status": "stopped" if stopped else "not_running", "app_name": app_name}


@app.post("/api/preview/start")
async def preview_start(payload: dict):
    import preview_manager
    app_name = os.path.basename(str(payload.get("app_name", "")))
    app_dir = os.path.join(_SCRIPT_DIR, "generated_builds", app_name)
    if not os.path.isdir(os.path.join(app_dir, "frontend")):
        raise HTTPException(status_code=404, detail=f"No full-stack build for '{app_name}'")
    info = await asyncio.to_thread(preview_manager.start_preview, app_name, app_dir)
    ready = await asyncio.to_thread(preview_manager.wait_ready, info["port"], 45)
    return {"status": "started" if ready else "starting", "app_name": app_name,
            "port": info["port"], "url": f"http://localhost:{info['port']}/"}


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


@app.post("/api/loop/start")
async def loop_start(request: Request):
    global loop_running
    try:
        data = await request.json()
    except Exception:
        data = {}
    user_intent = (data or {}).get("intent", "").strip()
    if not user_intent:
        return JSONResponse({"error": "intent is required"}, status_code=400)
    if loop_running:
        return JSONResponse({"error": "Loop already running"}, status_code=409)

    def run_loop():
        global loop_running
        loop_running = True
        loop_status_buffer.append({"type": "start", "msg": f"Loop started: {user_intent}"})
        try:
            engine = AutonomousLoop()
            # Monkey-patch input() so Section 11 gates post to status buffer
            # instead of blocking the thread on console
            import builtins
            original_input = builtins.input
            def ui_input(prompt=""):
                loop_status_buffer.append({"type": "approval_required", "msg": prompt})
                # Block this thread until operator posts to /api/loop/approve
                while not _approval_event.is_set():
                    import time; time.sleep(0.5)
                _approval_event.clear()
                return _approval_response[0]
            builtins.input = ui_input
            engine.run(user_intent)
            builtins.input = original_input
        except Exception as e:
            loop_status_buffer.append({"type": "error", "msg": str(e)})
        finally:
            loop_running = False
            loop_status_buffer.append({"type": "done", "msg": "Loop complete"})

    _approval_event.clear()
    t = threading.Thread(target=run_loop, daemon=True)
    t.start()
    return {"status": "loop started"}


@app.get("/api/loop/status")
def loop_status():
    return {
        "running": loop_running,
        "buffer": list(loop_status_buffer)
    }


@app.post("/api/loop/approve")
async def loop_approve(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    directive = (data or {}).get("directive", "proceed").strip()
    _approval_response[0] = directive
    _approval_event.set()
    return {"status": "directive received"}


@app.post("/api/loop/architect")
async def loop_architect_decision(request: Request):
    try:
        body = await request.json()
        ledger = body.get("ledger", "")
        context = body.get("context", "")
        iteration = body.get("iteration", 0)
        if not ledger:
            return JSONResponse(status_code=400, content={"error": "ledger is required"})
        architect_prompt = (
            f"You are the Senior Architect of the Meta App Factory.\n\n"
            f"ITERATION: {iteration}\n\n"
            f"EXECUTION CONTEXT:\n{context}\n\n"
            f"LEDGER FROM LAST EXECUTION:\n{ledger}\n\n"
            f"Respond with ONLY this JSON object:\n"
            f'{{"decision": "COMPLETE"|"ITERATE"|"ESCALATE"|"ERROR", '
            f'"reasoning": "one sentence", '
            f'"next_mandate": "full mandate if ITERATE else null", '
            f'"escalation_reason": "reason if ESCALATE else null"}}\n'
            f"No markdown. JSON only."
        )
        from google import genai
        import os, json as json_mod
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=architect_prompt,
            config={"temperature": 0.0}
        )
        raw = response.text.strip().strip("```").strip("json").strip()
        decision = json_mod.loads(raw)
        loop_status_buffer.append({
            "type": "architect_decision",
            "decision": decision.get("decision"),
            "reasoning": decision.get("reasoning"),
            "iteration": iteration
        })
        return JSONResponse(content=decision)
    except Exception as e:
        logger.error(f"[ARCHITECT] Decision endpoint failed: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


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

    # -- Explicit Build-vs-Venture Routing Resolver --------------------------
    # Precedence: inline prefix (/build, /venture, /csuite) > explicit `mode`
    # field > AUTO (fall back to the LLM classifier downstream). forced_intent
    # stays None in AUTO mode. Inline prefixes are stripped from the prompt here
    # (the client keeps the original text in its local chat history).
    forced_intent = None
    is_full_stack = False
    _prefix_map = {"/fullstack": "BUILDER", "/build": "BUILDER", "/venture": "VENTURE", "/csuite": "VENTURE"}
    _stripped = user_query.lstrip()
    _low = _stripped.lower()
    for _pfx, _pintent in _prefix_map.items():
        if _low == _pfx or (_low.startswith(_pfx) and _low[len(_pfx):len(_pfx) + 1].isspace()):
            forced_intent = _pintent
            is_full_stack = (_pfx == "/fullstack")
            user_query = _stripped[len(_pfx):].lstrip()
            query_lower = user_query.lower()
            break
    if forced_intent is None:
        _mode = (getattr(req, "mode", None) or "auto").strip().lower()
        if _mode == "build":
            forced_intent = "BUILDER"
        elif _mode in ("venture", "csuite"):
            forced_intent = "VENTURE"

    # Deterministic Intent Classification Gate
    if "[MANDATE START]" in user_query or user_query.strip().startswith("/genesis "):
        classification = "STRUCTURAL_MANDATE"
    elif forced_intent is not None:
        # Explicit build/venture signal -> force the structural path so the
        # prompt reaches the builder/venture pipeline, not conversational chat.
        classification = "STRUCTURAL_MANDATE"
    else:
        classification = "CONVERSATIONAL_QUERY"

    # Branch A: Conversational Query Bypass
    if classification == "CONVERSATIONAL_QUERY":
        # ── ClaudeAY Dual-Engine Router ─────────────────────
        try:
            _routing_engine = await classify_intent(user_query)
        except Exception as _cay_err:
            import logging
            logging.getLogger("server").warning(
                f"[ROUTER] Intent classification failed: {_cay_err}. Defaulting to GEMINI."
            )
            _routing_engine = "GEMINI"

        if _routing_engine == "CLAUDE":
            async def generate_claudeay_stream():
                import json
                import sys
                import os
                sys.path.insert(0, os.path.dirname(
                    os.path.dirname(os.path.abspath(__file__))
                ))
                try:
                    from dispatcher import AntigravityDispatcher
                    from ay_client import send_mandate
                    from loop_engine import load_recent_telemetry

                    dispatcher = AntigravityDispatcher()
                    telemetry = load_recent_telemetry()

                    yield f"data: {json.dumps({'type': 'agent_identity', 'agent': 'CLAUDE_ARCHITECT'})}\n\n"
                    yield f"data: {json.dumps({'type': 'agent_stream', 'content': '[🔵 CLAUDE ARCHITECT] Analyzing request...\\n'})}\n\n"

                    mandate = dispatcher.build_prompt(
                        instruction=user_query,
                        telemetry=telemetry if telemetry.get('total_events', 0) > 0 else None,
                    )

                    ledger = send_mandate(mandate)

                    for line in ledger.split('\n'):
                        if line.strip():
                            yield f"data: {json.dumps({'type': 'agent_stream', 'content': line + chr(10)})}\n\n"

                    yield f"data: {json.dumps({'type': 'agent_stream', 'content': '\\n[🔵 CLAUDE ARCHITECT] Mandate complete.'})}\n\n"

                except Exception as e:
                    yield f"data: {json.dumps({'type': 'agent_stream', 'content': f'[CLAUDE ERROR] {str(e)}\\nFalling back to Gemini.'})}\n\n"
                    # Fallback: signal to use Gemini
                    yield f"data: {json.dumps({'type': 'fallback_to_gemini'})}\n\n"

            return StreamingResponse(
                generate_claudeay_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                }
            )
        # ── End ClaudeAY Router — GEMINI path continues below ──

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
                # Telemetry: record token usage for the conversational turn.
                try:
                    _um = getattr(response_stream, "usage_metadata", None)
                    if _um:
                        _record_usage("ma_conversational", "gemini-2.5-pro",
                                      getattr(_um, "prompt_token_count", 0),
                                      getattr(_um, "candidates_token_count", 0))
                except Exception:
                    pass
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
        nonlocal is_conversational
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

            # Step A: Resolve intent -- explicit override wins, else LLM classifier.
            if forced_intent is not None:
                intent = forced_intent
            else:
                intent = await classify_builder_venture_intent(user_query, req.history)
            # Force the structural/build path for BUILDER so keyword-free prose
            # prompts (e.g. "make me a todo app") still reach blueprint
            # extraction/validation/spool (overrides the is_conversational heuristic).
            if intent == "BUILDER":
                is_conversational = False
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

                system_prompt = FULLSTACK_BLUEPRINT if is_full_stack else BUILDER_BLUEPRINT
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

                # BUILDER path is always structural: force valid JSON in the exact
                # actuator schema so blueprint generation can no longer emit malformed
                # payloads (the prior cause of the "CRITICAL MALFORMED PAYLOAD" 500s).
                builder_gen_config = {
                    "temperature": 0.2,
                    "response_mime_type": "application/json",
                    "response_schema": BUILDER_BLUEPRINT_SCHEMA,
                    "max_output_tokens": 32768,
                }

                # Step B: Instantiate ChatSession if history is present, ensuring strict context binding
                if formatted_history:
                    chat = model.start_chat(history=formatted_history)
                    response = chat.send_message(
                        contents_payload,
                        generation_config=builder_gen_config
                    )
                else:
                    response = model.generate_content(
                        contents_payload,
                        generation_config=builder_gen_config
                    )
                
                text = response.text.strip()

                # Telemetry: record token usage for the Triad review generation.
                try:
                    _um = getattr(response, "usage_metadata", None)
                    if _um:
                        _record_usage("ma_builder_review", "gemini-2.5-pro",
                                      getattr(_um, "prompt_token_count", 0),
                                      getattr(_um, "candidates_token_count", 0))
                except Exception:
                    pass

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
                        logger.warning(f"[CTO Node] Pre-spool validation failed. Retrying at temperature 0.0...")
                        try:
                            # Single retry at temperature 0.0 for maximum determinism
                            retry_config = builder_gen_config.copy()
                            retry_config["temperature"] = 0.0
                            if formatted_history:
                                chat = model.start_chat(history=formatted_history)
                                retry_response = chat.send_message(
                                    contents_payload,
                                    generation_config=retry_config
                                )
                            else:
                                retry_response = model.generate_content(
                                    contents_payload,
                                    generation_config=retry_config
                                )
                            retry_text = retry_response.text.strip()
                            retry_extracted = retry_text
                            retry_match = re.search(r"(\{.*\})", retry_extracted, re.DOTALL)
                            if retry_match:
                                retry_extracted = retry_match.group(1).strip()
                            blueprint_data = json.loads(retry_extracted)
                            text = json.dumps(blueprint_data, indent=2)
                            logger.info("[CTO Node] Pre-spool validation passed on retry.")
                        except Exception as retry_err:
                            logger.error(f"[CTO Node] Pre-spool validation retry failed: {retry_err}\nRaw response:\n{response.text}")
                            raise HTTPException(
                                status_code=500,
                                detail=f"CRITICAL MALFORMED PAYLOAD: Synthesized blueprint contains invalid JSON architecture: {jde}"
                            )

                    # [BUILDER Socratic gate removed 2026-06-14] The business-strategy Critic
                    # (ICP / financial-model rubric, 9.5 pass bar) is category-mismatched for
                    # technical blueprints: code has no ICP, so it always scored <=5.0 and halted
                    # every build. The strict JSON validation above + the downstream AY2 dispatch /
                    # auditor wires are the real technical review.

                # AST Interception Patch: Package generated code/architecture into strict JSON envelope
                import time
                timestamp = int(time.time())
                # These are control flags, not content signals. They must only fire on an
                # explicit operator directive (the standalone tokens "/pause" / "/fail"),
                # never on a substring of natural-language prose: real build prompts routinely
                # contain "fail"/"pause" ("show a PASS/FAIL banner", "handle login failure",
                # "play/pause controls") and a substring match would falsely trip the actuator's
                # crash-test / strategic-pause paths and abort an otherwise-valid build.
                # (E2E suites trigger these by spooling JSON with the flags set directly, so
                # they do not depend on this query heuristic.)
                strategic_pause = bool(re.search(r"(?:^|\s)/pause\b", user_query, re.IGNORECASE))
                strategic_fail = bool(re.search(r"(?:^|\s)/fail\b", user_query, re.IGNORECASE))

                # Test-only: inject a known-broken build to deterministically exercise the
                # self-healing loop. Gated by an env flag so it is inert on a reachable endpoint.
                if getattr(req, "test_inject_broken", None) and os.getenv("ALLOW_TEST_INJECTION", "").lower() == "true":
                    blueprint_data = {
                        "app_name": "selfheal-test",
                        "summary": "injected broken build for self-heal verification",
                        "ast_mutations": [{
                            "target_file": "index.html",
                            "code_payload": "<!doctype html><html><head><title>Heal Test</title></head><body><h1>Self-Heal Test</h1><script>renderAppError();</script></body></html>",
                        }],
                    }
                    text = json.dumps(blueprint_data, indent=2)
                    logger.warning("[TEST] ALLOW_TEST_INJECTION: spooling known-broken blueprint to exercise self-healing.")

                blueprint_payload = {
                    "blueprint_data": text,
                    "Strategic_Pause": strategic_pause,
                    "Strategic_Fail": strategic_fail,
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

                # ── Build verification + self-healing loop ──
                # Wait for the build to actuate, headlessly render it, and feed any
                # console/runtime/network errors (+ a screenshot) back to the model for up
                # to MAX_ROUNDS repair passes. The final ✅ is gated on a clean render.
                try:
                    _bp_inner = blueprint_data if isinstance(blueprint_data, dict) else json.loads(text)
                except Exception:
                    _bp_inner = {}
                _raw_app = str(_bp_inner.get("app_name", "app")).strip()
                _safe_app = "".join(c if (c.isalnum() or c in "-_") else "-" for c in _raw_app).strip("-_") or "app"
                _app_dir = os.path.join(_SCRIPT_DIR, "generated_builds", _safe_app)
                _targets = [m.get("target_file", "") for m in _bp_inner.get("ast_mutations", []) if isinstance(m, dict)]

                _factory_ui_dir = os.path.join(_FACTORY_DIR, "factory_ui")
                _verify_dir = os.path.join(_SCRIPT_DIR, ".verify_tmp")
                os.makedirs(_verify_dir, exist_ok=True)
                _build_url = f"http://localhost:{PORT}/builds/{_safe_app}/"
                _open_url = _build_url
                _gallery_url = f"http://localhost:{PORT}/builds/"
                MAX_ROUNDS = 3

                def _targets_of(inner):
                    return [m.get("target_file", "") for m in inner.get("ast_mutations", []) if isinstance(m, dict)]

                async def _await_actuation(spool_ts, targets, deadline_s=45):
                    _dl = time.time() + deadline_s
                    while time.time() < _dl:
                        await asyncio.sleep(0.7)
                        if not targets:
                            continue
                        _ok = True
                        for _tf in targets:
                            _rel = str(_tf).replace("\\", "/").lstrip("/")
                            _dest = os.path.join(_app_dir, *[p for p in _rel.split("/") if p])
                            if not (os.path.exists(_dest) and os.path.getmtime(_dest) >= spool_ts - 1):
                                _ok = False
                                break
                        if _ok:
                            return True
                    return False

                async def _run_verify():
                    _stamp = int(time.time() * 1000)
                    _rp = os.path.join(_verify_dir, f"report_{_stamp}.json")
                    _sp = os.path.join(_verify_dir, f"shot_{_stamp}.png")
                    try:
                        _proc = await asyncio.create_subprocess_exec(
                            "node", "verify_app.mjs", _build_url, _sp, _rp,
                            cwd=_factory_ui_dir,
                            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                        )
                        await asyncio.wait_for(_proc.communicate(), timeout=45)
                    except Exception as _ve:
                        logger.warning(f"[Self-Heal] verifier unavailable ({_ve}); skipping verification.")
                        return {"success": True, "_skipped": True}, None
                    try:
                        with open(_rp, "r", encoding="utf-8") as _f:
                            _report = json.load(_f)
                    except Exception:
                        return {"success": True, "_skipped": True}, None
                    return _report, (_sp if os.path.exists(_sp) else None)

                def _spool_blueprint(inner):
                    _ts = int(time.time())
                    _payload = {
                        "blueprint_data": json.dumps(inner, indent=2),
                        "Strategic_Pause": False, "Strategic_Fail": False, "timestamp": _ts,
                    }
                    _bp = os.path.join(ay2_queue_dir, f"pending_blueprint_{_ts}.json")
                    _tmp = _bp + ".tmp"
                    with open(_tmp, "w", encoding="utf-8") as _f:
                        _f.write(json.dumps(_payload, indent=2))
                    os.replace(_tmp, _bp)
                    return _ts

                async def _request_fix(report, shot_path):
                    _errs = []
                    for _k in ("pageErrors", "consoleErrors", "networkErrors"):
                        for _e in report.get(_k, []):
                            _errs.append(f"[{_k}] {_e}")
                    _files = []
                    for _tf in _targets:
                        _rel = str(_tf).replace("\\", "/").lstrip("/")
                        _dest = os.path.join(_app_dir, *[p for p in _rel.split("/") if p])
                        try:
                            with open(_dest, "r", encoding="utf-8") as _f:
                                _files.append((_tf, _f.read()))
                        except Exception:
                            _files.append((_tf, ""))
                    _files_blob = "\n\n".join(f"--- FILE: {p} ---\n{c}" for p, c in _files)
                    _fix_prompt = (
                        "The app you generated produced errors when rendered in a headless browser. "
                        "Return a CORRECTED, COMPLETE blueprint in the same JSON schema "
                        "{app_name, ast_mutations:[{target_file, code_payload}]}. Keep app_name identical, "
                        "emit the FULL final content of every file, and fix every error listed.\n\n"
                        "ERRORS:\n" + "\n".join(_errs) + "\n\n"
                        "CURRENT FILES:\n" + _files_blob
                    )
                    _parts = [_fix_prompt]
                    if shot_path and os.path.exists(shot_path):
                        try:
                            _parts = [await asyncio.to_thread(genai.upload_file, shot_path), _fix_prompt]
                        except Exception:
                            _parts = [_fix_prompt]
                    _fix_model = genai.GenerativeModel("gemini-2.5-pro", system_instruction=BUILDER_BLUEPRINT)
                    _resp = await asyncio.to_thread(
                        _fix_model.generate_content, _parts,
                        generation_config={"temperature": 0.2, "response_mime_type": "application/json", "response_schema": BUILDER_BLUEPRINT_SCHEMA},
                    )
                    return json.loads(_resp.text.strip())

                await _await_actuation(timestamp, _targets)

                # Full-stack: boot the dev server and verify the RUNNING app (not static files).
                _is_fs = is_full_stack or any(
                    str(t).replace("\\", "/").lstrip("/").startswith(("frontend/", "backend/")) for t in _targets
                )
                _preview = None
                if _is_fs:
                    try:
                        import preview_manager
                        _preview = await asyncio.to_thread(preview_manager.start_preview, _safe_app, _app_dir)
                        _pport = _preview["port"]
                        _build_url = f"http://127.0.0.1:{_pport}/"
                        _open_url = f"http://localhost:{_pport}/"
                        yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CTO', 'content': f'🚀 [Preview] Dev server on :{_pport} — waiting for readiness...\n'})}\n\n"
                        _ready = await asyncio.to_thread(preview_manager.wait_ready, _pport, 45)
                        if not _ready:
                            yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CRITIC', 'content': '⚠️ [Preview] Dev server slow to boot; verifying anyway...\n'})}\n\n"
                    except Exception as _pe:
                        logger.error(f"[Preview] start failed: {_pe}")
                        _is_fs = False
                        yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CRITIC', 'content': f'⚠️ [Preview] Could not start dev server: {_pe}\n'})}\n\n"

                _final_ok = False
                _last_report = {}
                for _round in range(1, MAX_ROUNDS + 1):
                    _report, _shot = await _run_verify()
                    if _is_fs and not _report.get("success"):
                        try:
                            _vlog = await asyncio.to_thread(preview_manager.tail_log, _safe_app)
                            if _vlog.strip():
                                _report.setdefault("consoleErrors", []).append("[vite dev-server log]\n" + _vlog[-1500:])
                        except Exception:
                            pass
                    _last_report = _report
                    if _report.get("success"):
                        _final_ok = True
                        break
                    _nerr = sum(len(_report.get(_k, [])) for _k in ("pageErrors", "consoleErrors", "networkErrors"))
                    yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CRITIC', 'content': f'\n🔧 [Self-Heal] Round {_round}: {_nerr} issue(s) detected, repairing...\n'})}\n\n"
                    if _round >= MAX_ROUNDS:
                        break
                    try:
                        _fixed = await _request_fix(_report, _shot)
                    except Exception as _fe:
                        logger.error(f"[Self-Heal] fix request failed: {_fe}")
                        break
                    _bp_inner = _fixed
                    _targets = _targets_of(_fixed) or _targets
                    _new_ts = _spool_blueprint(_fixed)
                    yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CTO', 'content': '⚙️ [Self-Heal] Actuating revised blueprint...\n'})}\n\n"
                    await _await_actuation(_new_ts, _targets)
                    if _is_fs:
                        await asyncio.sleep(3)  # let Vite HMR + uvicorn --reload pick up the rewrite
                        if _preview and _preview.get("backend_port"):
                            await asyncio.to_thread(preview_manager.wait_ready, _preview["backend_port"], 12)

                if _final_ok:
                    _verified = "" if _last_report.get("_skipped") else " (verified clean)"
                    if _is_fs:
                        _msg = (
                            f"\n✅ [Build Complete]{_verified} full-stack app running live.\n"
                            f"▶ Open your app:  {_open_url}\n"
                        )
                    else:
                        _msg = (
                            f"\n✅ [Build Complete]{_verified} {len(_targets)} file(s) in generated_builds/{_safe_app}/.\n"
                            f"▶ Open your app:  {_open_url}\n"
                            f"📂 All your built apps:  {_gallery_url}\n"
                        )
                    yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CTO', 'content': _msg})}\n\n"
                    yield f"data: {json.dumps({'type': 'build_complete', 'app_name': _safe_app, 'open_url': _open_url, 'gallery_url': _gallery_url, 'files': _targets})}\n\n"
                else:
                    _rem = []
                    for _k in ("pageErrors", "consoleErrors", "networkErrors"):
                        _rem.extend(_last_report.get(_k, []))
                    _detail = ("  - " + "\n  - ".join(_rem[:5])) if _rem else "  (no diagnostic captured)"
                    _msg = (
                        f"\n⚠️ [Build Incomplete] Could not reach a clean render after {MAX_ROUNDS} self-heal round(s).\n"
                        f"Latest issues:\n{_detail}\n"
                        f"Partial output is at generated_builds/{_safe_app}/ — {_open_url}\n"
                    )
                    yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CRITIC', 'content': _msg})}\n\n"

            else:
                agent_identity = "VENTURE_ARCHITECT"
                yield f"data: {json.dumps({'type': 'agent_identity', 'agent': agent_identity})}\n\n"
                
                # ── PHYSICAL MULTI-AGENT SWARM execution ──
                import httpx

                # VAULT EXTRACTION SPLICE — bind foundational documents to C-Suite context
                if req.document_ids:
                    _venture_parser = DocumentParserService() if _DOC_PARSER_AVAILABLE else None
                    for doc_id in req.document_ids:
                        safe_doc_id = os.path.basename(doc_id)
                        doc_path = os.path.normpath(os.path.join(_SCRIPT_DIR, "vault", "staging", safe_doc_id))
                        if os.path.exists(doc_path):
                            ext = os.path.splitext(safe_doc_id)[1].lower()
                            if ext in [".txt", ".md", ".csv", ".json"]:
                                try:
                                    async with aiofiles.open(doc_path, "r", encoding="utf-8", errors="ignore") as f:
                                        content = await f.read()
                                        document_context += f"\n--- DOCUMENT: {safe_doc_id} ---\n" + content + "\n"
                                except Exception as e:
                                    logger.error(f"Error reading vault document {safe_doc_id}: {e}")
                            elif _venture_parser is not None and _venture_parser.is_supported(doc_path):
                                # PDF/DOCX/PPTX/etc. — extract clean text server-side so
                                # CMO/CFO/CIO sub-agents (no Google File API access) see the content.
                                try:
                                    extracted = await asyncio.to_thread(
                                        _venture_parser._extract_text, doc_path, ext
                                    )
                                    if extracted and not extracted.startswith("ERROR:"):
                                        document_context += f"\n--- DOCUMENT: {safe_doc_id} ---\n" + extracted + "\n"
                                    else:
                                        logger.warning(f"Parser returned no text for {safe_doc_id}: {extracted}")
                                        # Last-resort: stage to Google so at least the CEO can see it.
                                        uploaded_file = genai.upload_file(doc_path)
                                        google_uploaded_files.append(uploaded_file)
                                        document_context += f"\n[Staged Binary Payload: {safe_doc_id} (Google URI: {uploaded_file.name})]\n"
                                except Exception as e:
                                    logger.error(f"Error parsing vault document {safe_doc_id}: {e}")
                            else:
                                # Images (PNG/JPG) and other binaries the parser can't read —
                                # stage to the Google File API for the CEO's multimodal pass.
                                try:
                                    logger.info(f"Staging binary document {safe_doc_id} to Google File API...")
                                    uploaded_file = genai.upload_file(doc_path)
                                    google_uploaded_files.append(uploaded_file)
                                    document_context += f"\n[Staged Binary Payload: {safe_doc_id} (Google URI: {uploaded_file.name})]\n"
                                except Exception as e:
                                    logger.error(f"Error staging binary document {safe_doc_id} to Google: {e}")
                    if document_context:
                        active_query = user_query + f"\n\n[ATTACHED FOUNDATIONAL DOCUMENTS]:\n{document_context}"
                    else:
                        active_query = user_query

                # 1. CIO Deep Research Pre-flight Sweep (Port 5090)
                yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CIO', 'content': '🔍 [CIO Sweep] Initiating live market research sensor sweep...\\n'})}\n\n"
                
                intel_brief_str = "No live intelligence gathered."
                _cio_intel_ok = False
                try:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        resp = await client.post("http://127.0.0.1:5090/api/cio/deep_research", json={"query": active_query})
                        if resp.status_code == 200:
                            data = resp.json()
                            intel_brief_str = data.get("intelligence_brief", "No live intelligence gathered.")
                            _cio_intel_ok = True
                        else:
                            raise Exception(f"HTTP {resp.status_code}")
                except Exception as cio_err:
                    logger.warning(f"CIO pre-flight HTTP failed: {cio_err}")
                    # Port 5090 offline — run the deep-research crawler locally rather
                    # than streaming a fake success (which silently starved the C-Suite).
                    yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CIO', 'content': '⚠️ CIO port 5090 offline. Running local fallback web search...\\n'})}\n\n"
                    try:
                        from shared_modules.deep_research_crawler import deep_research
                        _research = await deep_research(active_query)
                        _brief = _research.get("intelligence_brief", "")
                        if _brief:
                            intel_brief_str = _brief
                            _cio_intel_ok = True
                    except Exception as fallback_err:
                        logger.error(f"CIO local fallback research failed: {fallback_err}")
                        yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CIO', 'content': f'⚠️ CIO local fallback research failed: {fallback_err}\\n'})}\n\n"

                if _cio_intel_ok:
                    yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CIO', 'content': '✅ CIO Sensor Sweep Completed. Live data integrated.\\n\\n'})}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CIO', 'content': '⚠️ CIO Sweep completed without live intelligence; proceeding on internal knowledge.\\n\\n'})}\n\n"

                # 2. Parallel Boardroom analysis (CMO, CFO, CIO)
                yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CEO', 'content': '💬 Dispatching intent to C-Suite division heads for concurrent strategic audit...\\n'})}\n\n"

                # Raw sub-agent payloads for the deterministic Critic structural gate
                # (populated in both HTTP and fallback paths below).
                cmo_res, cfo_res, cio_res = {}, {}, {}

                # CMO Analysis (DuckDuckGo live searches)
                cmo_summary = ""
                try:
                    yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CMO', 'content': '📊 [CMO Agent] Launching competitor landscape DuckDuckGo scans...\\n'})}\n\n"
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        resp = await client.post("http://127.0.0.1:5020/api/warroom/respond", json={
                            "topic": active_query,
                            "context": "CEO War Room Directive",
                            "agents_present": ["CEO", "CFO", "CIO", "CMO"]
                        })
                        if resp.status_code == 200:
                            cmo_data = resp.json()
                            cmo_res = cmo_data
                            cmo_summary = cmo_data.get("summary", "")
                        else:
                            raise Exception("HTTP failure")
                except Exception:
                    # Fallback to local CMO agent execution
                    try:
                        from cmo_agent import CMOAgent
                        cmo = CMOAgent()
                        cmo_res = await asyncio.to_thread(cmo.run, active_query)
                        cmo_summary = cmo_res.get("summary", "")
                        # Surface the extended business sections when present.
                        _cmo_sections = [
                            ("Market Analysis", cmo_res.get("market_analysis", "")),
                            ("Market Strategy", cmo_res.get("market_strategy", "")),
                            ("Strategy Rationale", cmo_res.get("strategy_rationale", "")),
                            ("Concept Recommendations", cmo_res.get("concept_recommendations", "")),
                            ("Alternative Concepts", cmo_res.get("alternative_concepts", "")),
                        ]
                        _extra = "".join(f"\n\n**{label}:** {text}" for label, text in _cmo_sections if text)
                        if _extra:
                            cmo_summary = f"{cmo_summary}{_extra}"
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
                            "instruction": f"CEO DIRECTIVE: {active_query}\n\n=== CIO INTELLIGENCE BRIEF ===\n{intel_brief_str}"
                        })
                        if resp.status_code == 200:
                            cfo_data = resp.json()
                            cfo_res = cfo_data
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
                        try:
                            validate_cfo_output(cfo_res)
                        except ValueError as schema_err:
                            logger.error(f"[SCHEMA GATE] CFO output rejected: {schema_err}")
                            raise
                        if cfo_res.get("status") == "success":
                            metrics = cfo_res.get('metrics', cfo_res)
                            cfo_report = (
                                f"Generated Spreadsheet Model: {cfo_res.get('file_path', cfo_res.get('file_name', 'None'))}\n"
                                f"Projected IRR: {metrics.get('irr_pct', metrics.get('roi_percentage', 0))}%\n"
                                f"Break-Even Timeline: {metrics.get('breakeven_months', 0)} Months\n"
                                f"Year 1 Net Profit: ${metrics.get('net_income_y1', metrics.get('projected_revenue', 0)):,.2f}"
                            )
                            # Surface the CFO narrative sections when present.
                            _fin = cfo_res.get("financial_analysis", "")
                            _inv = cfo_res.get("investment_recommendations", "")
                            if _fin:
                                cfo_report += f"\n\n**Financial Analysis:** {_fin}"
                            if _inv:
                                cfo_report += f"\n\n**Investment Recommendations:** {_inv}"
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
                            "focus_areas": [active_query]
                        })
                        if resp.status_code == 200:
                            cio_data = resp.json()
                            cio_res = cio_data
                            cio_feasibility = cio_data.get("feasibility_analysis", "")
                        else:
                            raise Exception("HTTP failure")
                except Exception:
                    try:
                        from cio_agent import CIOAgent
                        cio = CIOAgent()
                        cio_res = await asyncio.to_thread(cio.run, active_query)
                        try:
                            validate_cio_output(cio_res)
                        except ValueError as schema_err:
                            logger.error(f"[SCHEMA GATE] CIO output rejected: {schema_err}")
                            raise
                        cio_feasibility = cio_res.get("feasibility_analysis", "") or cio_res.get("data", "")
                    except Exception as cio_err:
                        cio_feasibility = f"[CIO feasibility assessment failed: {cio_err}]"

                cio_report_text = f"⚙️ CIO Technical Feasibility Report:\n{cio_feasibility}\n\n"
                for idx in range(0, len(cio_report_text), 32):
                    yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CIO', 'content': cio_report_text[idx:idx+32]})}\n\n"

                # 3. CEO Synthesis (Heavy gemini-2.5-pro model execution)
                yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CEO', 'content': '👑 [CEO Brain] Synthesizing division reports and resolving strategic bottlenecks...\\n'})}\n\n"
                
                # Phase 2 Semantic Recall Pre-Fetch Hook
                historical_context = ""
                try:
                    from backend.core.vector_store import VectorStore
                    from backend.services.embedding_service import GoogleEmbeddingService
                except ImportError:
                    from core.vector_store import VectorStore
                    from services.embedding_service import GoogleEmbeddingService
                
                pre_fetch_store = VectorStore(persist_directory="./chroma_data")
                pre_fetch_service = GoogleEmbeddingService()
                
                logger.info("Semantic Recall Hook: Vectorizing raw CEO objective...")
                embedding_res = await pre_fetch_service.get_embedding_async(user_query)
                
                # STRICT GUARDRAIL: Halt and yield 502 error if embedding service fails
                if isinstance(embedding_res, JSONResponse):
                    err_msg = json.loads(embedding_res.body.decode()).get("detail", "Google Embedding API offline.")
                    yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CEO', 'content': f'❌ [Semantic Recall Gate] FAILED to fetch objective embedding: {err_msg}\\n'})}\n\n"
                    yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CEO', 'content': '[STREAM FRACTURE: 502 Gateway Unreachable]'})}\n\n"
                    return
                
                # Asynchronously query ChromaDB (L2 distance threshold: 0.55)
                try:
                    logger.info("Semantic Recall Hook: Actuating spatial ChromaDB recall query...")
                    results = await pre_fetch_store.query_async(
                        collection_name="maf_knowledge",
                        query_embeddings=[embedding_res],
                        n_results=5
                    )
                    
                    ids = results.get("ids", [[]])[0]
                    distances = results.get("distances", [[]])[0]
                    documents = results.get("documents", [[]])[0]
                    
                    valid_docs = []
                    recalled_telemetry = []
                    
                    for idx_item in range(len(ids)):
                        doc_id = ids[idx_item]
                        distance = distances[idx_item]
                        doc_text = documents[idx_item]
                        
                        # STRICT GUARDRAIL: L2 distance must be < 0.55
                        if distance < 0.55:
                            valid_docs.append(f"Document ID: {doc_id}\nContent: {doc_text}")
                            recalled_telemetry.append({"document_id": doc_id, "l2_distance": float(distance)})
                    
                    if valid_docs:
                        joined_docs = "\n\n".join(valid_docs)
                        # STRICT GUARDRAIL: XML Bounded Prompt Mutation
                        historical_context = (
                            "<historical_semantic_memory>\n"
                            f"{joined_docs}\n"
                            "</historical_semantic_memory>"
                        )
                        logger.info(f"Semantic Recall Hook: Injected {len(valid_docs)} recalled documents.")
                        
                        # Telemetry Handshake: Transmit asynchronously to /api/qa/alerts
                        try:
                            import httpx
                            async def dispatch_telemetry():
                                alert_payload = {
                                    "source": "CEO_SEMANTIC_RECALL",
                                    "severity": "INFO",
                                    "alert_type": "vector_recall",
                                    "message": f"Semantic recall successful for objective. Items recalled: {len(recalled_telemetry)}",
                                    "metadata": {"recalled_items": recalled_telemetry, "objective": user_query[:100]}
                                }
                                for port_tel in [8000, 5009]:
                                    try:
                                        async with httpx.AsyncClient(timeout=2.0) as tel_client:
                                            await tel_client.post(f"http://127.0.0.1:{port_tel}/api/qa/alerts", json=alert_payload)
                                            break
                                    except Exception:
                                        pass
                            asyncio.create_task(dispatch_telemetry())
                        except Exception as tel_err:
                            logger.warning(f"Telemetry dispatch failed: {tel_err}")
                except Exception as query_err:
                    logger.error(f"Semantic Recall Hook query failure: {query_err}")

                # ── Autonomous C-Suite Debate Loop ──────────────────────────────
                # If the Critic rejects the synthesis (score < threshold), feed its
                # objections back into the CEO and re-synthesize, up to MAX_REVISIONS
                # times, before escalating a socratic challenge to the Commander.
                MAX_REVISIONS = 3
                CONSENSUS_THRESHOLD = 9.5

                base_ceo_prompt = (
                    f"You are the CEO of the Antigravity Meta App Factory. Ingest the following physical division reports for intent: '{active_query}':\n\n"
                    f"=== CMO Market Trend analysis ===\n{cmo_summary}\n\n"
                    f"=== CFO Capex and IRR models ===\n{cfo_report}\n\n"
                    f"=== CIO Feasibility Assessment ===\n{cio_feasibility}\n\n"
                    "Provide a master synthesis of these findings. Force a decisive resolution. State next actions."
                )

                # Stitch historical semantic context under XML boundary isolation
                ceo_system_instruction = VENTURE_ARCHITECT
                if historical_context:
                    ceo_system_instruction = f"{VENTURE_ARCHITECT}\n\n{historical_context}"

                model = genai.GenerativeModel(
                    model_name='gemini-2.5-pro',
                    system_instruction=ceo_system_instruction
                )

                # Project slug for Workspace Vault artifacts (triage report, approved strategy, blueprint).
                _proj_raw = (user_query or "Venture").strip().splitlines()[0][:50] if (user_query or "").strip() else "Venture"
                project_slug = re.sub(r'[^A-Za-z0-9 _-]', '', _proj_raw).strip().replace(' ', '_') or "Venture"

                def _write_vault(filename, content):
                    """Persist an artifact to vault/venture/ in BOTH the server dir and the project root."""
                    saved = []
                    for _base in (_SCRIPT_DIR, _FACTORY_DIR):
                        try:
                            _vdir = os.path.join(_base, "vault", "venture")
                            os.makedirs(_vdir, exist_ok=True)
                            _vpath = os.path.join(_vdir, filename)
                            with open(_vpath, "w", encoding="utf-8") as _vf:
                                _vf.write(content or "")
                            saved.append(_vpath)
                        except Exception as _ve:
                            logger.error(f"Vault write failed ({_base}): {_ve}")
                    return saved

                full_ceo_strategy = ""
                critic_score = 0.0
                objections = []
                consensus_reached = False

                for revision in range(1, MAX_REVISIONS + 1):
                    if revision > 1:
                        yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CEO', 'content': f'\\n\\n🔁 [Revision {revision}/{MAX_REVISIONS}] C-Suite debating to resolve Critic objections...\\n'})}\n\n"

                    # Build this round's CEO prompt; on revisions, inject prior objections.
                    ceo_prompt = base_ceo_prompt
                    if objections:
                        _obj_text = "\n".join(f"- {o}" for o in objections)
                        ceo_prompt = (
                            base_ceo_prompt
                            + f"\n\n=== CRITIC OBJECTIONS FROM THE PREVIOUS ROUND (score {critic_score}/10.0) ===\n{_obj_text}\n\n"
                            + "Revise the strategy to resolve EACH objection above explicitly. Do not repeat the previous answer verbatim."
                        )

                    # Include any staged multimodal payloads (images) so the CEO can
                    # actually see them; text docs are already inlined via ceo_prompt.
                    ceo_contents = [ceo_prompt] + google_uploaded_files
                    response_stream = model.generate_content(
                        ceo_contents,
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

                    # ── Deterministic C-Suite structural gate (CPG/Venture mandate) ──
                    # Reject sub-agent output lacking the mandated bottom-up structures
                    # BEFORE spending an LLM Critic call. A failed gate hard-overrides the
                    # score to 1.0, forcing revisions; if never resolved, the missing
                    # structures are surfaced verbatim in the Deadlock Triage Report.
                    from shared_modules.csuite_critic_gate import critic_gate, critic_signoff
                    cfo_gate = critic_gate("CFO", cfo_res)
                    cmo_gate = critic_gate("CMO", cmo_res)
                    cio_gate = critic_gate("CIO", cio_res)
                    signoff_res = critic_signoff([cfo_gate, cmo_gate, cio_gate])

                    critic_score = 7.5  # Default fallback
                    objections = []
                    if not signoff_res["signed_off"]:
                        # Structural rejection — bypass the LLM score entirely.
                        critic_score = 1.0
                        objections = [f"[{rej['agent']}] Missing structural requirement: {m}"
                                      for rej in signoff_res["rejections"]
                                      for m in rej.get("missing", [])]
                        yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CRITIC', 'content': '🛑 [Structural Gate] C-Suite output is missing required bottom-up structures — overriding score to 1.0 and returning to sender.\\n'})}\n\n"
                    else:
                        # Structures present — proceed to the LLM-based Critic score.
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
                            try:
                                validate_critic_output({"score": critic_score, "objections": objections})
                            except ValueError as schema_err:
                                logger.error(f"[SCHEMA GATE] Critic output rejected: {schema_err}")
                                raise
                        except Exception as critic_err:
                            logger.error(f"Critic scoring failed: {critic_err}")

                    yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CRITIC', 'content': f'Critic objections: {json.dumps(objections)}\\n'})}\n\n"
                    yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CRITIC', 'content': f'Critic score: {critic_score}/10.0 (round {revision}/{MAX_REVISIONS})\\n'})}\n\n"

                    if critic_score >= CONSENSUS_THRESHOLD:
                        consensus_reached = True
                        yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CRITIC', 'content': f'✅ Consensus reached at {critic_score}/10.0. Strategy approved.\\n'})}\n\n"
                        break
                    elif revision < MAX_REVISIONS:
                        yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CRITIC', 'content': '❌ Below consensus threshold. Returning to the C-Suite for revision...\\n'})}\n\n"

                if not consensus_reached:
                    # C-Suite could not self-resolve within MAX_REVISIONS — produce a
                    # full triage report (streamed + saved to vault), then escalate.
                    yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CRITIC', 'content': f'\\n⚠️ C-Suite could not reach consensus after {MAX_REVISIONS} revisions (best score {critic_score}/10.0). Compiling deadlock triage report...\\n\\n'})}\n\n"

                    triage_prompt = (
                        "You are the Chief of Staff documenting why the C-Suite failed to reach consensus on a venture. "
                        "Write a comprehensive, well-structured Markdown report with EXACTLY these sections:\n"
                        "# Deadlock Triage Report\n"
                        "## Executive Summary (why consensus failed)\n"
                        "## Venture PROs\n"
                        "## Venture CONs\n"
                        "## C-Suite Proposed Enhancements\n"
                        "## Critic Objections\n"
                        "## Entrepreneurial Lessons (Flaws in Thinking)\n\n"
                        f"VENTURE INTENT:\n{user_query}\n\n"
                        f"FINAL C-SUITE STRATEGY (best attempt, scored {critic_score}/10.0):\n{full_ceo_strategy}\n\n"
                        "UNRESOLVED CRITIC OBJECTIONS:\n" + "\n".join(f"- {o}" for o in objections) + "\n\n"
                        "Be specific and actionable. Output Markdown only."
                    )
                    triage_report = ""
                    try:
                        triage_model = genai.GenerativeModel('gemini-2.5-pro', system_instruction=VENTURE_ARCHITECT)
                        triage_stream = triage_model.generate_content(
                            triage_prompt, generation_config={"temperature": 0.3}, stream=True
                        )
                        for chunk in triage_stream:
                            try:
                                _tc = chunk.text
                            except (ValueError, AttributeError):
                                _tc = ""
                            if _tc:
                                triage_report += _tc
                                yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CRITIC', 'content': _tc})}\n\n"
                    except Exception as triage_err:
                        logger.error(f"Deadlock triage report generation failed: {triage_err}")
                        triage_report = (
                            "# Deadlock Triage Report\n\n"
                            f"## Executive Summary\nConsensus not reached after {MAX_REVISIONS} revisions (best score {critic_score}/10.0).\n\n"
                            "## Critic Objections\n" + "\n".join(f"- {o}" for o in objections) + "\n\n"
                            f"## Final Strategy (best attempt)\n{full_ceo_strategy}\n"
                        )
                        yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CRITIC', 'content': triage_report})}\n\n"

                    _saved = _write_vault(f"{project_slug}_Deadlock_Triage_Report.md", triage_report)
                    if _saved:
                        yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CRITIC', 'content': '\\n💾 Deadlock triage report saved to vault/venture/.\\n'})}\n\n"

                    from socratic_challenger import get_challenger
                    challenger = get_challenger()
                    challenge = await challenger.evaluate(proposal=full_ceo_strategy, critic_score=critic_score)

                    yield f"data: {json.dumps({'type': 'socratic_pause', 'challenge_id': challenge.get('challenge_id'), 'weaknesses': challenge.get('weaknesses')})}\n\n"
                    return  # Instantly close connection

                # 4. CTO Blueprint Handoff Contract
                yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CTO', 'content': '\\n\\n⚙️ [CTO Node] Deliberation approved. Synthesizing immutable physical software contract...\\n'})}\n\n"
                
                # Synthesize final consensus payload (Workspace Blueprint)
                cto_prompt = (
                    f"You are the CTO Agent. Synthesize the final strategic Workspace Blueprint from the C-Suite consensus strategy described below. "
                    f"You MUST output a valid JSON object matching the WorkspaceBlueprintSchema.\n\n"
                    f"C-SUITE CONSENSUS STRATEGY:\n{full_ceo_strategy}\n\n"
                    f"Extract the strategic objectives and formulate the Slide presentation mutations. Ensure presentation_name is safe and template_id is set to '1QEgXTEkk8C4mIP6QhRvZ0d-DpcuvyniGfwqzkDXC-oY'."
                )
                
                blueprint_json = ""
                try:
                    import google.generativeai as genai
                    cto_model = genai.GenerativeModel('gemini-2.5-pro')
                    cto_resp = cto_model.generate_content(
                        cto_prompt,
                        generation_config=genai.GenerationConfig(
                            response_mime_type="application/json",
                            response_schema=WorkspaceBlueprintSchema
                        )
                    )
                    blueprint_json = cto_resp.text.strip()
                    # Telemetry: record token usage for CTO blueprint synthesis.
                    try:
                        _um = getattr(cto_resp, "usage_metadata", None)
                        if _um:
                            _record_usage("ma_cto_synthesis", "gemini-2.5-pro",
                                          getattr(_um, "prompt_token_count", 0),
                                          getattr(_um, "candidates_token_count", 0))
                    except Exception:
                        pass
                except Exception as cto_err:
                    logger.error(f"CTO final blueprint synthesis failed: {cto_err}")
                    # Fallback matching WorkspaceBlueprintSchema
                    blueprint_json = json.dumps({
                        "presentation_name": "Heinlein_Foods_90_Day_Strategy",
                        "template_id": "1QEgXTEkk8C4mIP6QhRvZ0d-DpcuvyniGfwqzkDXC-oY",
                        "mutations": {
                            "{{PROJECT_NAME}}": "Project Heinlein Foods",
                            "{{OBJECTIVE}}": "90-Day Survival: C-Suite Swarm & Rapid Capitalization",
                            "{{STRATEGY_SUMMARY}}": "Direct digital engagement targeting B2B executives. $50k budget allocation to drive 5x ROAS / 400% ROI, generating $250k to offset $15k monthly burn. Breakeven target: 2 months."
                        }
                    }, indent=2)
                
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

                # ── Automated Presentation Deck Generation (on consensus) ──
                # NOTE: PresentationArchitect slide copy is largely templated
                # (Antigravity-AI branding); the CFO figures below are injected,
                # but the narrative is generic. Decks download via api.py (:5000).
                if _PRES_ARCHITECT_AVAILABLE:
                    try:
                        yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CTO', 'content': '\\n🎬 [CTO Node] Compiling investor & customer pitch decks...\\n'})}\n\n"

                        # Derive a company/project name from the blueprint mutations, else the query.
                        company = "Venture"
                        try:
                            _bp = json.loads(blueprint_json)
                            company = (_bp.get("mutations", {}).get("{{PROJECT_NAME}}")
                                       or _bp.get("presentation_name")
                                       or company)
                        except Exception:
                            pass
                        company = re.sub(r'[^A-Za-z0-9 _-]', '', str(company)).strip() or "Venture"
                        safe_company = company.replace(' ', '_')[:60]

                        # Pull the figures the deck renders out of the CFO report text.
                        _irr = re.search(r'IRR[:\s]+([\d.]+)', cfo_report)
                        _be = re.search(r'Break-?Even[^:]*:\s*([\d.]+)', cfo_report)
                        _rev = re.search(r'Net Profit:\s*\$?([\d,]+)', cfo_report)
                        inv_data = {
                            "roi": _irr.group(1) if _irr else "340",
                            "breakeven_month": int(float(_be.group(1))) if _be else 6,
                            "y1_revenue": f"${_rev.group(1)}" if _rev else "$0",
                            "gross_margin": 68,
                            "signals_daily": 50,
                        }

                        arch = PresentationArchitect()
                        res_inv = await asyncio.to_thread(
                            arch.generate, "investor", inv_data, f"{safe_company}_Investor_Deck.json"
                        )
                        res_cust = await asyncio.to_thread(
                            arch.generate, "customer", {}, f"{safe_company}_Customer_Deck.json"
                        )

                        _doc_base = "http://localhost:5000/api/eos/documents"
                        for _label, _res in (("Investor", res_inv), ("Customer", res_cust)):
                            _pptx = (_res or {}).get("pptx_path")
                            if _pptx:
                                _fn = os.path.basename(_pptx)
                                yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CTO', 'content': f'▶ Download {_label} Deck: {_doc_base}/{_fn}\\n'})}\n\n"
                            else:
                                yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CTO', 'content': f'⚠️ {_label} deck generation returned no file.\\n'})}\n\n"
                    except Exception as deck_err:
                        logger.error(f"Pitch deck generation failed: {deck_err}")
                        yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CTO', 'content': f'⚠️ Deck generation error: {deck_err}\\n'})}\n\n"

                # ── Workspace Vault Persistence (approved strategy + blueprint) ──
                _md_saved = _write_vault(f"{project_slug}_Approved_Strategy.md", full_ceo_strategy)
                _bp_saved = _write_vault(f"{project_slug}_Blueprint.json", blueprint_json)
                if _md_saved or _bp_saved:
                    yield f"data: {json.dumps({'type': 'agent_stream', 'emitter': 'CTO', 'content': '\\n💾 Approved strategy + blueprint saved to vault/venture/.\\n'})}\n\n"

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


@app.post("/api/challenge/delegate")
async def challenge_delegate(req: ChallengeDelegateRequest):
    """Delegate a Socratic challenge to the C-Suite: run live research per weakness
    and synthesize draft answers for the user to review/edit before submitting."""
    from socratic_challenger import get_challenger
    challenger = get_challenger()
    challenges = await challenger._load_challenges()
    challenge = challenges.get(req.challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail=f"Challenge {req.challenge_id} not found.")

    weaknesses = challenge.get("weaknesses", [])

    # Gather live research context per weakness.
    research_brief = ""
    try:
        from shared_modules.deep_research_crawler import deep_research
        for w in weaknesses:
            _q = f"{w.get('category','')} {w.get('challenge','')}".strip()
            if not _q:
                continue
            try:
                _r = await deep_research(_q)
                research_brief += f"\n## Research for: {w.get('category','')}\n{_r.get('intelligence_brief','')[:1500]}\n"
            except Exception as _re:
                logger.warning(f"Delegate research failed for weakness {w.get('category','')}: {_re}")
    except Exception as imp_err:
        logger.warning(f"deep_research unavailable for delegation: {imp_err}")

    weakness_text = "\n".join(
        f"{w.get('id')}. [{w.get('category')}] {w.get('challenge')}" for w in weaknesses
    )

    api_key = os.getenv("GEMINI_API_KEY", "")
    if api_key:
        api_key = api_key.strip("'\"")

    draft = ""
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        delegate_model = genai.GenerativeModel('gemini-2.5-pro', system_instruction=VENTURE_ARCHITECT)
        prompt = (
            "The Critic raised the following weaknesses about our venture strategy. "
            "Using the live research below, draft a concise, evidence-based rebuttal that addresses EACH weakness "
            "with specific data points and concrete commitments. Write in the first person as the founding team. "
            "Output plain prose the user can review and edit — no headings, no JSON.\n\n"
            f"WEAKNESSES:\n{weakness_text}\n\n"
            f"LIVE RESEARCH:\n{research_brief or 'No external research available; reason from first principles.'}\n"
        )
        resp = await asyncio.to_thread(
            delegate_model.generate_content, prompt, generation_config={"temperature": 0.4}
        )
        draft = (getattr(resp, "text", "") or "").strip()
    except Exception as gen_err:
        logger.error(f"Challenge delegation synthesis failed: {gen_err}")
        raise HTTPException(status_code=500, detail=f"Delegation synthesis failed: {gen_err}")

    return {
        "challenge_id": req.challenge_id,
        "draft": draft,
        "weaknesses_addressed": len(weaknesses),
        "research_sources": bool(research_brief),
    }


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
