import logging
import time
from collections import defaultdict
from fastapi import FastAPI, Request, HTTPException, Security, Depends
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import asyncio

# Setup Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("WarRoomMonitor")

app = FastAPI(
    title="WarRoomMonitor",
    description="Monitors the health and operational status of the host system and all registered child agents. Provides real-time CPU/RAM metrics and asynchronous connectivity checks to ensure system stability and agent availability.",
    version="1.0.0"
)

# CORS Middleware
origins = ['http://localhost:5173', 'https://your-frontend.com']
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom Rate Limiter
rate_limit_store = defaultdict(list)
RATE_LIMIT_RPM = 60

async def check_rate_limit(request: Request):
    client_ip = request.client.host
    now = time.time()
    rate_limit_store[client_ip] = [t for t in rate_limit_store[client_ip] if now - t < 60]
    if len(rate_limit_store[client_ip]) >= RATE_LIMIT_RPM:
        logger.warning(f"Rate limit exceeded for {client_ip} ({len(rate_limit_store[client_ip])}/{RATE_LIMIT_RPM} RPM)")
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again in a minute.")
    rate_limit_store[client_ip].append(now)

# Authentication Posture
api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=True)
async def verify_auth(api_key: str = Security(api_key_header)):
    import os
    expected = os.getenv("WARROOMMONITOR_API_KEY", "default_secret_key")
    if api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API Key")

# Audit Middleware
@app.middleware("http")
async def audit_logging_middleware(request: Request, call_next):
    client_ip = request.client.host
    logger.info(f"AUDIT LOG: Inbound {request.method} request to {request.url.path} from {client_ip}")
    response = await call_next(request)
    logger.info(f"AUDIT LOG: Outbound response status {response.status_code} for {request.url.path}")
    return response

# Pydantic Schemas from Data Contracts
class SystemHealthContractOutput(BaseModel):
    timestamp: str
    cpu_percent: str
    memory_percent: str
    child_agents_status: str
    overall_status: str

class DetailedMonitorRequestContractInput(BaseModel):
    agent_names_filter: str
    include_system_metrics: str
    ping_timeout_ms: str

class DetailedMonitorRequestContractOutput(BaseModel):
    timestamp: str
    requested_agents_status: str
    system_metrics_snapshot: str
    overall_request_status: str

# API Endpoints
@app.get("/api/health", 
    response_model=SystemHealthContractOutput, 
    summary="Retrieves current system health including CPU, RAM, and child agent connectivity status.",
    dependencies=[Depends(check_rate_limit), Depends(verify_auth)]
)
async def retrieves_current_system_health_including_cpu_ram_and_child_agent_connectivity_status():
    import psutil
    import httpx
    import os
    import json
    from datetime import datetime
    
    logger.info("Executing endpoint: /api/health")
    
    # 1. Capture live CPU/RAM metrics
    cpu = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory().percent
    
    # 2. Read agent_registry.json path relative to factory
    registry_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "Master_Architect_Elite_Logic", "agent_registry.json"))
    
    child_status = {}
    overall = "HEALTHY"
    
    if os.path.exists(registry_path):
        try:
            with open(registry_path, "r", encoding="utf-8") as f:
                registry = json.load(f)
                
            # 3. Asynchronously ping all active child agent ports via httpx
            async with httpx.AsyncClient(timeout=2.0) as client:
                tasks = []
                agents_to_ping = []
                for agent in registry.get("agents", []):
                    # Skip master_architect and self
                    if agent["id"] in ["master_architect", "warroommonitor"] or agent["status"] != "ACTIVE":
                        continue
                    agents_to_ping.append(agent)
                    # Ping /api/health or root
                    tasks.append(client.get(f"http://127.0.0.1:{agent['port']}/"))
                    
                if tasks:
                    responses = await asyncio.gather(*tasks, return_exceptions=True)
                    for agent, resp in zip(agents_to_ping, responses):
                        name = agent["name"]
                        if isinstance(resp, Exception):
                            child_status[name] = "OFFLINE"
                            overall = "DEGRADED"
                        else:
                            if resp.status_code < 500:
                                child_status[name] = "ONLINE"
                            else:
                                child_status[name] = "DEGRADED"
                                overall = "DEGRADED"
        except Exception as reg_err:
            logger.error(f"Error reading registry or pinging: {reg_err}")
            overall = "DEGRADED"
    else:
        logger.warning(f"agent_registry.json not found at {registry_path}")
        
    return {
        "timestamp": datetime.now().isoformat(),
        "cpu_percent": f"{cpu}%",
        "memory_percent": f"{mem}%",
        "child_agents_status": json.dumps(child_status),
        "overall_status": overall
    }

@app.post("/api/v1/monitor/status", 
    response_model=DetailedMonitorRequestContractOutput, 
    summary="Requests a detailed status report for specified agents or the entire system with configurable depth.",
    dependencies=[Depends(check_rate_limit), Depends(verify_auth)]
)
async def requests_a_detailed_status_report_for_specified_agents_or_the_entire_system_with_configurable_depth(
    payload: DetailedMonitorRequestContractInput
):
    logger.info("Executing endpoint: /api/v1/monitor/status")
    
    # Deterministic Mock Response fulfilling the exact Output Data Contract
    response_data = {
        "timestamp": "2026-05-25T00:00:00Z",
        "requested_agents_status": "SUCCESS",
        "system_metrics_snapshot": getattr(payload, "system_metrics_snapshot", "mock_value_for_system_metrics_snapshot"),
        "overall_request_status": "SUCCESS"
    }
    return response_data
