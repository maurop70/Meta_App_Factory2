from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
from dotenv import load_dotenv

# Load secure environment variables
load_dotenv()

app = FastAPI(title="Aether Agent Skills Router", version="1.0.0")

class AgentRequest(BaseModel):
    task: str
    context: dict = {}

# Mock registry for the 13 agents
AGENTS = [
    "ceo", "cfo", "cto", "cmo", "deep-crawler", "the-critic", 
    "the-librarian", "compliance-officer", "data-architect", 
    "researcher", "graphic-designer", "presentation-expert", "cx-strategist"
]

@app.get("/health")
async def health_check():
    return {"status": "✅ Active", "runtime": "Aether v1.0.0"}

@app.get("/agents")
async def list_agents():
    return {"available_agents": AGENTS}

@app.post("/agent/{agent_id}")
async def call_agent(agent_id: str, request: AgentRequest):
    if agent_id not in AGENTS:
        raise HTTPException(status_code=404, detail="Agent not found in registry")
    
    # Logic to route the task to the specific agent persona
    return {
        "status": "success",
        "agent": agent_id,
        "message": f"Task received by {agent_id.upper()}",
        "execution_context": "Skills Router v1.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
