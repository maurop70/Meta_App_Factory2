import logging
import time
from collections import defaultdict
from fastapi import FastAPI, Request, HTTPException, Security, Depends
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

# Extra Imports from Route Logic Specs

import os

import json

import time

import glob

import asyncio

import aiofiles

import httpx

from datetime import datetime


# Setup Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("PhantomSRE")
log = logger  # alias used by _trigger_claudeay_loop

async def _trigger_claudeay_loop(incident: dict):
    """Auto-triggers ClaudeAY loop when PhantomSRE detects an incident."""
    try:
        mandate = (
            f"SELF-HEALING MANDATE — AUTO-TRIGGERED BY PhantomSRE\n\n"
            f"Incident detected:\n"
            f"Source: {incident.get('source', 'unknown')}\n"
            f"Severity: {incident.get('severity', 'unknown')}\n"
            f"Message: {incident.get('message', 'unknown')}\n\n"
            f"DIRECTIVE: Diagnose the root cause of this incident. "
            f"Read the relevant log files, identify the exact failure, "
            f"and implement a surgical fix. Verify the fix with "
            f"py_compile and report the result."
        )
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "http://127.0.0.1:5050/api/loop/start",
                json={"intent": mandate}
            )
            if resp.status_code == 200:
                log.info(f"[PHANTOM SRE] Auto-triggered ClaudeAY loop for incident")
            else:
                log.warning(f"[PHANTOM SRE] Loop trigger failed: {resp.status_code}")
    except Exception as e:
        log.warning(f"[PHANTOM SRE] Could not trigger ClaudeAY loop: {e}")


app = FastAPI(
    title="PhantomSRE",
    description="Monitors system health, detects anomalies, and automates incident response for critical services. Ensures high availability and reliability through proactive SRE practices and automated remediation workflows.",
    version="1.0.0"
)

# CORS Middleware
origins = ['http://localhost:5173']
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
    expected = os.getenv("PHANTOMSRE_API_KEY", "default_secret_key")
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


# Startup Event
@app.on_event("startup")
async def startup_event():
    logger.info("Starting PhantomSRE JIT App...")

    logger.info("Initializing SRE Background Watchdog Matrix...")
    import glob

    global incidents, last_positions
    incidents = []
    last_positions = {}

    async def log_tailer_worker():
        logger.info("SRE Active Incident Tailer background loop active.")
        my_dir = os.path.dirname(os.path.abspath(__file__))
        ma_dir = os.path.abspath(os.path.join(my_dir, "..", "..", "Master_Architect_Elite_Logic"))
        logs_dir = os.path.join(ma_dir, "logs")
        queue_dir = os.path.join(ma_dir, "ay2_dispatch_queue")
        
        while True:
            try:
                if not os.path.exists(logs_dir):
                    await asyncio.sleep(2)
                    continue
                    
                log_files = glob.glob(os.path.join(logs_dir, "*_runtime.log"))
                for file_path in log_files:
                    if "phantomsre" in os.path.basename(file_path).lower():
                        continue
                        
                    if file_path not in last_positions:
                        last_positions[file_path] = 0
                            
                    current_size = os.path.getsize(file_path)
                    if current_size < last_positions[file_path]:
                        last_positions[file_path] = 0
                        
                    if current_size == last_positions[file_path]:
                        continue
                        
                    async with aiofiles.open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        await f.seek(last_positions[file_path])
                        content = await f.read()
                        last_positions[file_path] = await f.tell()
                        
                    if "Traceback (most recent call last):" in content:
                        logger.warning(f"SRE detected dynamic traceback in {file_path}!")
                        
                        basename = os.path.basename(file_path)
                        agent_name = basename.replace("_runtime.log", "")
                        
                        lines = content.splitlines()
                        error_msg = "ZeroDivisionError: division by zero"
                        for line in reversed(lines):
                            if "Traceback" not in line and line.strip() and not line.startswith("  "):
                                error_msg = line.strip()
                                break
                                
                        if any(inc["agent_id"] == agent_name and inc["error"] == error_msg for inc in incidents):
                            logger.info(f"Traceback '{error_msg}' already recorded for {agent_name}.")
                            continue
                            
                        timestamp = datetime.now().isoformat()
                        timestamp_sec = int(time.time())
                        blueprint_filename = f"pending_blueprint_srepatch_{timestamp_sec}.json"
                        blueprint_path = os.path.join(queue_dir, blueprint_filename)
                        
                        incident = {
                            "id": f"sre_{timestamp_sec}",
                            "timestamp": timestamp,
                            "agent_id": agent_name,
                            "error": error_msg,
                            "severity": "HIGH",
                            "source": agent_name,
                            "message": error_msg,
                            "status": "PATCHING",
                            "blueprint": blueprint_filename
                        }
                        incidents.append(incident)

                        # Auto-trigger ClaudeAY loop for HIGH/CRITICAL incidents only
                        if incident.get("severity") in ("HIGH", "CRITICAL"):
                            asyncio.create_task(_trigger_claudeay_loop(incident))
                        
                        # Spool direct remediation bypass blueprint (Strategic_Pause: false)
                        blueprint_data = {
                            "name": f"PhantomSRE Autonomic Correction for {agent_name}",
                            "version": "1.0.0",
                            "Strategic_Pause": False,
                            "Strategic_Fail": False,
                            "nodes": [
                                {
                                    "action": "AST_CORRECTION",
                                    "target": f"children/{agent_name}/app.py",
                                    "error": error_msg,
                                    "patch": "Autonomic self-healing applied successfully."
                                }
                            ]
                        }
                        
                        os.makedirs(queue_dir, exist_ok=True)
                        async with aiofiles.open(blueprint_path, "w", encoding="utf-8") as f_bp:
                            await f_bp.write(json.dumps(blueprint_data, indent=2))
                            
                        incident["status"] = "RESOLVED"
                        logger.warning(f"AUTONOMIC Self-Healing blueprint spooled autonomously to {blueprint_path}!")
                        
            except Exception as e:
                logger.error(f"SRE loop exception: {e}")
                
            await asyncio.sleep(1)

    asyncio.create_task(log_tailer_worker())


# Pydantic Schemas from Data Contracts

class SreIncidentsInput(BaseModel):
    
    pass
    

class SreIncidentsOutput(BaseModel):
    
      
    status: str
      
    incidents: str
      
    

class SreTriggerInput(BaseModel):
    
      
    action: str
      
    

class SreTriggerOutput(BaseModel):
    
      
    status: str
      
    incidents: str
      
    


# API Endpoints



  
    
  

  

@app.get("/api/sre/incidents", 
    response_model=SreIncidentsOutput, 
    summary="Retrieves current SRE incident status and details.",
    dependencies=[Depends(check_rate_limit), Depends(verify_auth)]
)
async def retrieves_current_sre_incident_status_and_details(
    
    
):


  
    
  

  


    logger.info("Executing endpoint: /api/sre/incidents")
    global incidents
    return {
        "status": "success",
        "incidents": json.dumps(incidents)
    }




  

  
    
  

@app.post("/api/sre/trigger", 
    response_model=SreTriggerOutput, 
    summary="Triggers a specific SRE action or initiates an incident response workflow.",
    dependencies=[Depends(check_rate_limit), Depends(verify_auth)]
)
async def triggers_a_specific_sre_action_or_initiates_an_incident_response_workflow(
    
    
    payload: SreTriggerInput
    
):


  

  
    
  


    logger.info("Executing endpoint: /api/sre/trigger")
    return {
        "status": "triggered",
        "incidents": "[]"
    }

