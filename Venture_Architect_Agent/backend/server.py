import os
import sys
import logging

# Ensure telemetry directory exists
log_dir = "/var/log/aether_net"
os.makedirs(log_dir, exist_ok=True)

# Configure Telemetry with both Stream and File handlers
logger = logging.getLogger("venture_architect")
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s [%(name)s] %(levelname)s: %(message)s', datefmt="%H:%M:%S")

# Console Handler
ch = logging.StreamHandler(sys.stdout)
ch.setFormatter(formatter)
logger.addHandler(ch)

# Telemetry File Handler
fh = logging.FileHandler(os.path.join(log_dir, "venture_architect.log"))
fh.setFormatter(formatter)
logger.addHandler(fh)
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Import engines
from engines.financial_modeler import generate_financials
from engines.unit_economics import calculate_unit_economics
from engines.pitch_deck import generate_pitch_deck
from engines.business_model import generate_business_model
from engines.cap_table import generate_cap_table
from engines.valuation import calculate_valuation
from engines.gtm_allocator import generate_gtm_budget
from engines.scenario_builder import build_scenarios

# Import memory store
import memory_store

app = FastAPI(title="Venture Architect Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static frontend files
frontend_dir = Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = frontend_dir / "index.html"
    if index_file.exists():
        with open(index_file, "r", encoding="utf-8") as f:
            return f.read()
    return "Venture Architect Agent Frontend not found."

@app.get("/api/projects")
async def list_projects():
    return {"projects": memory_store.list_projects()}

@app.get("/api/state/{project_name}")
async def get_state(project_name: str):
    return memory_store.get_project_state(project_name)

@app.post("/api/generate/business-model")
async def api_business_model(request: Request):
    data = await request.json()
    project_name = data.get("project_name", "default_project")
    user_input = data.get("user_input", "")
    
    # Fetch CMO Context to inform business model
    cmo_context = memory_store.get_cmo_context(project_name)
    context_str = f"CMO Context: {cmo_context}" if cmo_context else "No CMO context found."
    
    result = await generate_business_model(user_input, context_str)
    
    # Save State
    state = memory_store.get_project_state(project_name)
    state["business_model"] = result
    memory_store.save_project_state(project_name, state)
    
    return result

@app.post("/api/generate/unit-economics")
async def api_unit_economics(request: Request):
    data = await request.json()
    project_name = data.get("project_name", "default_project")
    user_input = data.get("user_input", "")
    
    state = memory_store.get_project_state(project_name)
    context_str = f"Business Model: {state.get('business_model', {})}"
    
    result = await calculate_unit_economics(user_input, context_str)
    
    state["unit_economics"] = result
    memory_store.save_project_state(project_name, state)
    
    return result

@app.post("/api/generate/financials")
async def api_financials(request: Request):
    data = await request.json()
    project_name = data.get("project_name", "default_project")
    user_input = data.get("user_input", "")
    
    state = memory_store.get_project_state(project_name)
    context_str = f"Business Model: {state.get('business_model', {})}, Unit Economics: {state.get('unit_economics', {})}"
    
    result = await generate_financials(user_input, context_str)
    
    state["financials"] = result
    memory_store.save_project_state(project_name, state)
    
    return result

@app.post("/api/generate/pitch-deck")
async def api_pitch_deck(request: Request):
    data = await request.json()
    project_name = data.get("project_name", "default_project")
    user_input = data.get("user_input", "")
    
    state = memory_store.get_project_state(project_name)
    context_str = f"Financials: {state.get('financials', {})}, Business Model: {state.get('business_model', {})}"
    
    result = await generate_pitch_deck(user_input, context_str)
    
    state["pitch_deck"] = result
    memory_store.save_project_state(project_name, state)
    
    return result

@app.post("/api/generate/cap-table")
async def api_cap_table(request: Request):
    data = await request.json()
    project_name = data.get("project_name", "default_project")
    user_input = data.get("user_input", "")
    state = memory_store.get_project_state(project_name)
    context_str = f"Financials: {state.get('financials', {})}"
    
    result = await generate_cap_table(user_input, context_str)
    state["cap_table"] = result
    memory_store.save_project_state(project_name, state)
    return result

@app.post("/api/generate/valuation")
async def api_valuation(request: Request):
    data = await request.json()
    project_name = data.get("project_name", "default_project")
    user_input = data.get("user_input", "")
    state = memory_store.get_project_state(project_name)
    context_str = f"Financials: {state.get('financials', {})}, Cap Table: {state.get('cap_table', {})}"
    
    result = await calculate_valuation(user_input, context_str)
    state["valuation"] = result
    memory_store.save_project_state(project_name, state)
    return result

@app.post("/api/generate/gtm-budget")
async def api_gtm_budget(request: Request):
    data = await request.json()
    project_name = data.get("project_name", "default_project")
    user_input = data.get("user_input", "")
    state = memory_store.get_project_state(project_name)
    cmo_context = memory_store.get_cmo_context(project_name)
    context_str = f"Financials: {state.get('financials', {})}, CMO GTM Strategy: {cmo_context.get('gtm_plan', {})}"
    
    result = await generate_gtm_budget(user_input, context_str)
    state["gtm_budget"] = result
    memory_store.save_project_state(project_name, state)
    return result

@app.post("/api/generate/scenarios")
async def api_scenarios(request: Request):
    data = await request.json()
    project_name = data.get("project_name", "default_project")
    user_input = data.get("user_input", "")
    state = memory_store.get_project_state(project_name)
    context_str = f"Financials: {state.get('financials', {})}, Unit Economics: {state.get('unit_economics', {})}"
    
    result = await build_scenarios(user_input, context_str)
    state["scenarios"] = result
    memory_store.save_project_state(project_name, state)
    return result

if __name__ == "__main__":
    import uvicorn
    # Run on port 5110 to avoid conflicts with other agents
    uvicorn.run(app, host="127.0.0.1", port=5110)
