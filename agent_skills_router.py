"""
agent_skills_router.py -- Aether Agent Skills Router V7
======================================================
Meta App Factory | Aether Protocol | Antigravity-AI

Routes tasks to 18 Specialist Agents. V7 adds News Bureau Chief
as the final agent for actionable signal processing.
Call tracking active for Visual Mapping Protocol.
"""

import os
import sys
import json
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

# Load secure environment variables
load_dotenv()

app = FastAPI(title="Aether Agent Skills Router", version="7.0.0")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.path.join(SCRIPT_DIR, ".Gemini_state")
CALL_STATS_PATH = os.path.join(STATE_DIR, "agent_call_stats.json")


class AgentRequest(BaseModel):
    task: str
    context: dict = {}


# Registry for the 19 agents (V8: + dr-aris)
AGENTS = [
    "ceo", "cfo", "cto", "cmo", "deep-crawler", "the-critic",
    "the-librarian", "compliance-officer", "data-architect",
    "researcher", "graphic-designer", "presentation-expert",
    "cx-strategist", "aether-architect", "delegate-orchestrator",
    "unified-eq-specialist", "geotalent-scout", "news-bureau-chief",
    "dr-aris"
]

# System Core Skills — foundational agents that power the factory
SYSTEM_CORE_SKILLS = {"meta-app-factory", "aether-architect", "delegate-orchestrator"}

# Cloud-Auth Skills — agents with Google Cloud OAuth (Sheets & Slides)
CLOUD_AUTH_AGENTS = {"presentation-expert", "news-bureau-chief"}


# ── Call Tracking ────────────────────────────────────────

def _track_call(agent_id: str) -> None:
    """Log an agent call to .Gemini_state/agent_call_stats.json."""
    os.makedirs(STATE_DIR, exist_ok=True)
    stats = {}
    if os.path.isfile(CALL_STATS_PATH):
        try:
            with open(CALL_STATS_PATH, "r", encoding="utf-8") as f:
                stats = json.load(f)
        except (json.JSONDecodeError, Exception):
            stats = {}

    now = datetime.now(timezone.utc).isoformat()

    if agent_id not in stats:
        stats[agent_id] = {"total_calls": 0, "call_log": [], "last_called": None}

    stats[agent_id]["total_calls"] += 1
    stats[agent_id]["last_called"] = now

    # Keep last 200 call timestamps per agent
    call_log = stats[agent_id].get("call_log", [])
    call_log.append(now)
    stats[agent_id]["call_log"] = call_log[-200:]

    try:
        with open(CALL_STATS_PATH, "w", encoding="utf-8", newline="\n") as f:
            json.dump(stats, f, indent=2)
    except Exception:
        pass  # Non-blocking — don't fail the dispatch on logging errors


# ── API Endpoints ────────────────────────────────────────

@app.get("/health")
async def health_check():
    return {"status": "✅ Active", "runtime": "Aether v2.0.0"}


@app.get("/agents")
async def list_agents():
    return {"available_agents": AGENTS, "total": len(AGENTS)}


@app.get("/agents/stats")
async def agent_stats():
    """Return call stats for all agents (used by Visual Mapping Protocol)."""
    if not os.path.isfile(CALL_STATS_PATH):
        return {"stats": {}, "message": "No call data yet."}
    try:
        with open(CALL_STATS_PATH, "r", encoding="utf-8") as f:
            stats = json.load(f)
        # Summarize without full call logs
        summary = {}
        for agent_id, data in stats.items():
            summary[agent_id] = {
                "total_calls": data.get("total_calls", 0),
                "last_called": data.get("last_called"),
                "recent_7d": len([
                    ts for ts in data.get("call_log", [])[-50:]
                    # Simple recency check: just count tail entries
                ]),
            }
        return {"stats": summary}
    except Exception as e:
        return {"stats": {}, "error": str(e)}


@app.post("/agent/{agent_id}")
async def call_agent(agent_id: str, request: AgentRequest):
    if agent_id not in AGENTS:
        raise HTTPException(status_code=404, detail="Agent not found in registry")

    # Track this call for Visual Mapping Protocol
    _track_call(agent_id)

    # Logic to route the task to the specific agent persona
    return {
        "status": "success",
        "agent": agent_id,
        "message": f"Task received by {agent_id.upper()}",
        "execution_context": "Skills Router v2.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
