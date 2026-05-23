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
import sys
import json
import logging
from datetime import datetime

from fastapi import FastAPI, HTTPException
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

from backend.app.routers.ingest import router as ingest_router
from backend.app.routers.inventory_router import router as inventory_router

app.include_router(ingest_router)
app.include_router(inventory_router)

@app.get("/api/apps/running")
def get_running_apps_endpoint(limit: int = 10, offset: int = 0):
    # Complies with Unified I/O Serialization Envelope
    apps_list = [
        {"name": "Master_Architect_Elite_Logic", "port": PORT, "pid": os.getpid(), "alive": True, "health": "healthy"},
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

class ReviewRequest(BaseModel):
    description: str
    change_type: str = "feature"
    components: List[str] = []
    context: Optional[dict] = None
    prompt: Optional[str] = None
    document_ids: Optional[List[str]] = None

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


# ── Triad Review ─────────────────────────────────────────

@app.post("/api/review")
def review(req: ReviewRequest):
    """Full Triad review with document ingestion, dual-state prompt forking, and context-injected streaming."""
    # Detect user prompt & query
    user_query = req.prompt or req.description or ""
    query_lower = user_query.lower()

    # 2. COGNITIVE PROMPT FORKING (DUAL-STATE)
    conversational_keywords = ["what", "how", "why", "who", "where", "explain", "describe", "question", "tell me", "is there", "analyze the contents"]
    is_conversational = any(kw in query_lower for kw in conversational_keywords) or (
        len(user_query.strip()) > 0 and not any(kw in query_lower for kw in ["review", "audit", "structure", "schema", "vulnerability"])
    )

    if not user_query.strip():
        is_conversational = False

    system_prompt = (
        "You are the Master Architect. You are analyzing proposed software changes or audited enterprise documents.\n\n"
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
        "- PATH B (Conversational Inquiry): If the user asks a natural language question (e.g., 'what is in this file?', 'explain this', or asks questions about the documents), you are permanently authorized to bypass the JSON schema and output a standard, rich Markdown text response with no JSON wrappers."
    )

    # Streaming review generator
    def generate_review_stream():
        api_key = os.getenv("GEMINI_API_KEY", "")

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
            yield json.dumps(fallback_resp)
            return

        google_uploaded_files = []
        document_context = ""

        try:
            import google.generativeai as genai
            
            # Configure native Google Gemini API client
            genai.configure(api_key=api_key)

            # 1. THE EXTRACTION SPLICE
            if req.document_ids:
                for doc_id in req.document_ids:
                    safe_doc_id = os.path.basename(doc_id)
                    doc_path = os.path.normpath(os.path.join(_SCRIPT_DIR, "vault", "staging", safe_doc_id))
                    if os.path.exists(doc_path):
                        ext = os.path.splitext(safe_doc_id)[1].lower()
                        # Path A: Lightweight Text
                        if ext in [".txt", ".md", ".csv", ".json"]:
                            try:
                                with open(doc_path, "r", encoding="utf-8", errors="ignore") as f:
                                    document_context += f"\n--- DOCUMENT: {safe_doc_id} ---\n" + f.read() + "\n"
                            except Exception as e:
                                logger.error(f"Error reading lightweight text {safe_doc_id}: {e}")
                        # Path B: Massive Binary
                        else:
                            try:
                                logger.info(f"Staging massive binary document {safe_doc_id} to Google File API...")
                                uploaded_file = genai.upload_file(doc_path)
                                google_uploaded_files.append(uploaded_file)
                                document_context += f"\n[Staged Binary Payload: {safe_doc_id} (Google URI: {uploaded_file.name})]\n"
                            except Exception as e:
                                logger.error(f"Error staging binary document {safe_doc_id} to Google: {e}")

            # 3. PAYLOAD FUSION & CONTEXT INJECTION
            prompt_payload = f"USER INQUIRY / DESCRIPTION:\n{user_query}\n"
            if document_context:
                prompt_payload += f"\nDOCUMENT CONTEXT / CONTENT:\n{document_context}\n"

            # Instantiate 'gemini-2.5-pro' with system prompt instruction
            model = genai.GenerativeModel(
                model_name='gemini-2.5-pro',
                system_instruction=system_prompt
            )
            
            # Mathematically fuse binary files with the prompt payload
            contents_payload = []
            for uf in google_uploaded_files:
                contents_payload.append(uf)
            contents_payload.append(prompt_payload)

            response = model.generate_content(
                contents_payload,
                generation_config={"temperature": 0.2}
            )
            
            text = response.text.strip()

            # Clean markdown code fences for Path A
            if not is_conversational:
                import re
                if "```" in text:
                    match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
                    if match:
                        text = match.group(1).strip()
                start = text.find("{")
                end = text.rfind("}")
                if start != -1 and end > start:
                    text = text[start:end + 1]

            # Simulate streaming chunks
            chunk_size = 64
            for i in range(0, len(text), chunk_size):
                yield text[i:i+chunk_size]

        except Exception as e:
            yield f"Exception during LLM analysis: {str(e)}"

        finally:
            # 4. MEMORY SANITIZATION
            if google_uploaded_files:
                try:
                    import google.generativeai as genai
                    genai.configure(api_key=api_key)
                    for uf in google_uploaded_files:
                        logger.info(f"Sanitizing memory: Forcefully deleting {uf.name} from Google servers...")
                        genai.delete_file(uf.name)
                except Exception as e:
                    logger.error(f"Error during Google File API memory sanitization: {e}")

    return StreamingResponse(generate_review_stream(), media_type="text/plain")


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


# ── CLI Launch ───────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting Master Architect Elite Logic on port {PORT}...")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
