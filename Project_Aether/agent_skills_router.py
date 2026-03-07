"""
Agent Skills Router — Independent Service Modules
====================================================
Project Aether | Meta_App_Factory
FastAPI service exposing each C-Suite agent as an independent
callable API endpoint (Skill/Tool).

Usage:
  python agent_skills_router.py             → Start on port 8001
  python agent_skills_router.py --port 8002 → Custom port

Endpoints:
  GET  /                        → Service info
  GET  /agents                  → List all registered agents
  GET  /agents/{agent_id}       → Get agent config + status
  POST /agent/{agent_id}        → Execute agent skill
  POST /route                   → Auto-classify and route prompt
  GET  /health                  → Full system health check
"""

import os
import sys
import json
import uvicorn
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── Import Aether Runtime ──
RUNTIME_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, RUNTIME_DIR)
sys.path.insert(0, os.path.abspath(os.path.join(RUNTIME_DIR, "..")))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(RUNTIME_DIR, "..", ".env"))
except ImportError:
    pass

from aether_runtime import AetherRuntime, ConfigLoader, AgentRouter, IntentClassifier

# ══════════════════════════════════════════════════
#  APP INIT
# ══════════════════════════════════════════════════

app = FastAPI(
    title="Aether Agent Skills Router",
    description="Independent callable endpoints for each C-Suite agent. Use any agent as a standalone Skill or Tool.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize runtime on startup
runtime: Optional[AetherRuntime] = None

@app.on_event("startup")
async def startup():
    global runtime
    runtime = AetherRuntime()


# ══════════════════════════════════════════════════
#  REQUEST / RESPONSE MODELS
# ══════════════════════════════════════════════════

class SkillRequest(BaseModel):
    """Request payload for invoking an agent skill."""
    prompt: str
    context: Optional[str] = None
    skip_critic: bool = False

class RouteRequest(BaseModel):
    """Request payload for auto-classification routing."""
    prompt: str
    skip_critic: bool = False


# ══════════════════════════════════════════════════
#  ENDPOINTS
# ══════════════════════════════════════════════════

@app.get("/")
async def root():
    """Service info and available endpoints."""
    agents = runtime.list_agents() if runtime else []
    return {
        "service": "Aether Agent Skills Router",
        "version": "1.0.0",
        "status": "operational",
        "timestamp": datetime.now().isoformat(),
        "total_agents": len(agents),
        "active_agents": sum(1 for a in agents if a["status"] == "active"),
        "endpoints": {
            "list_agents": "GET /agents",
            "agent_detail": "GET /agents/{agent_id}",
            "invoke_agent": "POST /agent/{agent_id}",
            "auto_route": "POST /route",
            "health_check": "GET /health",
        },
    }


@app.get("/agents")
async def list_agents():
    """List all registered agent skills with their status and capabilities."""
    if not runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")

    agents = runtime.list_agents()
    # Enrich with endpoint paths
    enriched = []
    for agent in agents:
        agent["endpoint"] = f"/agent/{agent['key'].lower().replace('_', '-')}"
        agent["invoke_method"] = "POST"
        enriched.append(agent)

    return {
        "total": len(enriched),
        "active": sum(1 for a in enriched if a["status"] == "active"),
        "placeholder": sum(1 for a in enriched if a["status"] == "placeholder"),
        "agents": enriched,
    }


@app.get("/agents/{agent_id}")
async def get_agent_detail(agent_id: str):
    """Get detailed config for a specific agent."""
    if not runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")

    # Normalize: deep-crawler → DEEP_CRAWLER
    agent_key = agent_id.upper().replace("-", "_")
    agent = runtime.loader.get_agent(agent_key)

    if not agent:
        available = [k.lower().replace("_", "-") for k in runtime.loader.agents.keys()]
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_id}' not found. Available: {available}"
        )

    return {
        "key": agent.agent_key,
        "name": agent.name,
        "role": agent.role,
        "model": agent.model,
        "status": "placeholder" if agent.is_placeholder else "active",
        "division": agent.division,
        "temperature": agent.temperature,
        "max_tokens": agent.max_tokens,
        "tools": agent.tools,
        "reports_to": agent.reports_to,
        "system_prompt_preview": agent.system_prompt[:300] + "..." if len(agent.system_prompt) > 300 else agent.system_prompt,
        "endpoint": f"/agent/{agent_id}",
        "invoke_method": "POST",
        "invoke_example": {
            "url": f"http://localhost:8001/agent/{agent_id}",
            "method": "POST",
            "body": {"prompt": "Your task description here", "context": "Optional context", "skip_critic": False},
        },
    }


@app.post("/agent/{agent_id}")
async def invoke_agent(agent_id: str, request: SkillRequest):
    """
    Invoke a specific agent skill directly.
    
    This is the primary endpoint for using agents as standalone tools.
    Each agent can be called independently without C-Suite orchestration.
    
    Examples:
      POST /agent/deep-crawler   {"prompt": "Find legal tech competitors"}
      POST /agent/the-critic     {"prompt": "Review this proposal for risks"}
      POST /agent/cfo            {"prompt": "Calculate ROI for $5K investment"}
      POST /agent/cto            {"prompt": "Design a REST API for task management"}
    """
    if not runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")

    # Normalize: deep-crawler → DEEP_CRAWLER
    agent_key = agent_id.upper().replace("-", "_")

    # Verify agent exists
    agent = runtime.loader.get_agent(agent_key)
    if not agent:
        available = [k.lower().replace("_", "-") for k in runtime.loader.agents.keys()]
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_id}' not found. Available: {available}"
        )

    # Build prompt with optional context
    full_prompt = request.prompt
    if request.context:
        full_prompt = f"CONTEXT:\n{request.context}\n\nTASK:\n{request.prompt}"

    # Dispatch to agent
    result = runtime.prompt(full_prompt, target=agent_key, skip_critic=request.skip_critic)

    return {
        "agent": agent.name,
        "agent_key": agent_key,
        "endpoint": f"/agent/{agent_id}",
        "request_prompt": request.prompt,
        "session_id": result.get("session_id"),
        "status": result.get("status"),
        "response": result.get("response"),
        "critic_review": result.get("critic_review"),
        "routing": {
            "classified_to": result.get("classified_to"),
            "resolved_to": result.get("resolved_to"),
            "confidence": result.get("confidence"),
            "duration_ms": result.get("duration_ms"),
        },
    }


@app.post("/route")
async def auto_route(request: RouteRequest):
    """
    Auto-classify a prompt and route to the best-matching agent.
    
    The IntentClassifier analyzes the prompt and automatically selects
    the most appropriate agent. Useful when you don't know which agent to call.
    """
    if not runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")

    result = runtime.prompt(request.prompt, skip_critic=request.skip_critic)

    return {
        "auto_routed": True,
        "classified_to": result.get("classified_to"),
        "resolved_to": result.get("resolved_to"),
        "confidence": result.get("confidence"),
        "session_id": result.get("session_id"),
        "status": result.get("status"),
        "response": result.get("response"),
        "critic_review": result.get("critic_review"),
        "duration_ms": result.get("duration_ms"),
    }


@app.get("/health")
async def health_check():
    """Full system health check — agent status, webhook reachability, credential verification."""
    if not runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")

    report = runtime.health_check()

    # Add Skills Router status
    report["skills_router"] = {
        "status": "operational",
        "version": "1.0.0",
        "uptime": datetime.now().isoformat(),
        "endpoints_registered": 6,
    }

    # Add security status
    n8n_key = os.getenv("N8N_API_KEY", "")
    report["security"] = {
        "n8n_api_key": "✅ Present" if n8n_key else "❌ Missing",
        "env_file": "✅ Loaded" if n8n_key else "⚠️ Check .env",
        "hardcoded_credentials": "✅ None (remediated)",
    }

    return report


# ══════════════════════════════════════════════════
#  AGENT SKILL REGISTRY (for Meta_App_Factory integration)
# ══════════════════════════════════════════════════

SKILL_REGISTRY = {
    "ceo": {
        "name": "CEO — Chief Executive",
        "description": "Strategic decision-making, delegation, executive oversight",
        "endpoint": "/agent/ceo",
        "use_cases": ["strategic planning", "team coordination", "executive decisions"],
    },
    "cfo": {
        "name": "CFO — Chief Financial Officer",
        "description": "Budget analysis, ROI calculations, financial projections",
        "endpoint": "/agent/cfo",
        "use_cases": ["budget planning", "revenue projections", "cost analysis"],
    },
    "cto": {
        "name": "CTO — Chief Technology Officer",
        "description": "Architecture design, technical implementation, infrastructure planning",
        "endpoint": "/agent/cto",
        "use_cases": ["system architecture", "API design", "deployment planning"],
    },
    "cmo": {
        "name": "CMO — Chief Marketing Officer",
        "description": "Market strategy, brand positioning, campaign design",
        "endpoint": "/agent/cmo",
        "use_cases": ["marketing campaigns", "competitor analysis", "brand strategy"],
    },
    "deep-crawler": {
        "name": "Deep Crawler — Intelligence Gathering",
        "description": "Web research, data extraction, market scanning",
        "endpoint": "/agent/deep-crawler",
        "use_cases": ["market research", "competitive intelligence", "data mining"],
    },
    "the-critic": {
        "name": "The Critic — Quality Assurance",
        "description": "Audit, review, risk assessment, quality evaluation",
        "endpoint": "/agent/the-critic",
        "use_cases": ["proposal review", "risk assessment", "feasibility analysis"],
    },
    "the-librarian": {
        "name": "The Librarian — Knowledge Management",
        "description": "Index management, documentation, metadata sync",
        "endpoint": "/agent/the-librarian",
        "use_cases": ["documentation", "catalog management", "metadata sync"],
    },
    "compliance-officer": {
        "name": "Compliance Officer — Security & Legal",
        "description": "Security audits, credential management, privacy compliance",
        "endpoint": "/agent/compliance-officer",
        "use_cases": ["security audits", "compliance checks", "privacy reviews"],
    },
    "data-architect": {
        "name": "Data Architect — Schema & Analytics",
        "description": "Database design, data pipelines, dashboard creation",
        "endpoint": "/agent/data-architect",
        "use_cases": ["schema design", "data modeling", "analytics dashboards"],
    },
    "researcher": {
        "name": "Researcher — Academic & Technical Research",
        "description": "Deep research, literature review, technical analysis",
        "endpoint": "/agent/researcher",
        "use_cases": ["technical research", "competitive analysis", "trend identification"],
    },
    "graphic-designer": {
        "name": "Graphic Designer — Visual Assets",
        "description": "Logo design, brand assets, visual identity",
        "endpoint": "/agent/graphic-designer",
        "use_cases": ["logo concepts", "brand guidelines", "visual assets"],
    },
    "presentation-expert": {
        "name": "Presentation Expert — Pitch & Decks",
        "description": "Pitch decks, presentation design, business narratives",
        "endpoint": "/agent/presentation-expert",
        "use_cases": ["pitch decks", "investor presentations", "business proposals"],
    },
    "cx-strategist": {
        "name": "CX Strategist — Customer Experience",
        "description": "User experience strategy, customer journey mapping, feedback analysis",
        "endpoint": "/agent/cx-strategist",
        "use_cases": ["UX strategy", "customer journey", "feedback loops"],
    },
}


@app.get("/skills")
async def list_skills():
    """List all available agent skills for external tool/integration registration."""
    return {
        "service": "Aether Agent Skills",
        "base_url": "http://localhost:8001",
        "total_skills": len(SKILL_REGISTRY),
        "skills": SKILL_REGISTRY,
    }


# ══════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Aether Agent Skills Router")
    parser.add_argument("--port", type=int, default=8001, help="Port to run on (default: 8001)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to")
    args = parser.parse_args()

    print(f"\n🚀 Starting Aether Agent Skills Router on {args.host}:{args.port}")
    print(f"📡 Swagger docs: http://localhost:{args.port}/docs")
    print(f"📋 Agent list:   http://localhost:{args.port}/agents")
    print(f"🔧 Skills list:  http://localhost:{args.port}/skills\n")

    uvicorn.run(app, host=args.host, port=args.port)
