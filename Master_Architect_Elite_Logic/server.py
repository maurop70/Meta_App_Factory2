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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        f"http://localhost:{p}" for p in range(5173, 5181)
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
    """Full Triad review (blocking). Returns composite verdict + gate result."""
    verdict = _triad.review(
        req.description, req.change_type, req.components, req.context
    )
    verdict_dict = verdict.to_dict()

    # Pass through Adversarial Gate
    gate_result = _gate.evaluate(verdict_dict)
    gate_status = gate_result.get("gate_result", "UNKNOWN")

    # Store approved patterns
    if gate_status == "AUTO_APPROVE":
        _memory.store_pattern({
            "domain": "composite",
            "category": _classify(req.description),
            "pattern": req.description[:100],
            "rationale": f"Auto-approved (score {verdict.composite_score})",
            "technologies": req.components,
            "triad_score": verdict.composite_score,
        }, gate_status="approved")

    return {
        "verdict": verdict_dict,
        "gate": gate_result,
    }


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
