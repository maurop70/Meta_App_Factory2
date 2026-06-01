import logging
import time
from collections import defaultdict
from fastapi import FastAPI, Request, HTTPException, Security, Depends
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

# Extra Imports from Route Logic Specs

import psutil

import httpx

import os

import json

import asyncio

from datetime import datetime


# Setup Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("WarRoomMonitor")

app = FastAPI(
    title="WarRoomMonitor",
    description="Monitors system health, CPU/RAM usage, and the operational status of all registered child agents by asynchronously pinging their health endpoints, providing a comprehensive system status.",
    version="1.0.0"
)

# CORS Middleware
origins = ['http://localhost:5173', 'https://warroom.genesis.ai']
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom Rate Limiter
rate_limit_store = defaultdict(list)
RATE_LIMIT_RPM = 30

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

class SystemHealthContractInput(BaseModel):
    
    pass
    

class SystemHealthContractOutput(BaseModel):
    
      
    cpu_percent: str
      
    memory_percent: str
      
    child_agents_status: str
      
    timestamp: str
      
    

class MonitorStartContractInput(BaseModel):
    
      
    interval_seconds: str
      
    report_destination_url: str
      
    monitor_duration_minutes: str
      
    

class MonitorStartContractOutput(BaseModel):
    
      
    status: str
      
    message: str
      
    monitor_id: str
      
    


# API Endpoints



  
    
  

  

@app.get("/api/health", 
    response_model=SystemHealthContractOutput, 
    summary="Provides a comprehensive system health report including CPU, RAM, and child agent statuses.",
    dependencies=[Depends(check_rate_limit), Depends(verify_auth)]
)
async def provides_a_comprehensive_system_health_report_including_cpu_ram_and_child_agent_statuses(
    
    
):


  
    
  


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
        "overall_status": overall,
        "status": overall
    }




  

  
    
  

@app.post("/api/monitor/start", 
    response_model=MonitorStartContractOutput, 
    summary="Initiates continuous monitoring of system and child agent health, optionally sending reports to a specified destination.",
    dependencies=[Depends(check_rate_limit), Depends(verify_auth)]
)
async def initiates_continuous_monitoring_of_system_and_child_agent_health_optionally_sending_reports_to_a_specified_destination(
    
    
    payload: MonitorStartContractInput
    
):


  


    logger.info(f"Executing endpoint: /api/monitor/start")
    
    # Deterministic Mock Response fulfilling the exact Output Data Contract
    response_data = {}
    
      
        
    response_data["status"] = "SUCCESS"
        
      
        
          
    response_data["message"] = getattr(payload, "message", "mock_value_for_message")
          
        
      
        
    response_data["monitor_id"] = "gen_monitorstartcontract_" + str(int(time.time()))
        
      
    
    
    return response_data

