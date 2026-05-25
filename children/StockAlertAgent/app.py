import logging
import time
from collections import defaultdict
from fastapi import FastAPI, Request, HTTPException, Security, Depends
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

# Setup Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("StockAlertAgent")

app = FastAPI(
    title="StockAlertAgent",
    description="Monitors stock prices in real-time and triggers alerts based on predefined thresholds. This agent enables users to set up custom notifications for specific stock tickers when their price reaches, exceeds, or falls below a target value.",
    version="1.0.0"
)

# CORS Middleware
origins = ['http://localhost:5173', 'https://your-frontend-domain.com']
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom Rate Limiter
rate_limit_store = defaultdict(list)
RATE_LIMIT_RPM = 120

async def check_rate_limit(request: Request):
    client_ip = request.client.host
    now = time.time()
    rate_limit_store[client_ip] = [t for t in rate_limit_store[client_ip] if now - t < 60]
    if len(rate_limit_store[client_ip]) >= RATE_LIMIT_RPM:
        logger.warning(f"Rate limit exceeded for {client_ip} ({len(rate_limit_store[client_ip])}/{RATE_LIMIT_RPM} RPM)")
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again in a minute.")
    rate_limit_store[client_ip].append(now)

# Authentication Posture

bearer_scheme = HTTPBearer(auto_error=True)
async def verify_auth(credentials: HTTPAuthorizationCredentials = Security(bearer_scheme)):
    import os
    expected = os.getenv("STOCKALERTAGENT_BEARER_TOKEN", "default_bearer_token")
    if credentials.credentials != expected:
        raise HTTPException(status_code=401, detail="Invalid Bearer Token")


# Audit Middleware

@app.middleware("http")
async def audit_logging_middleware(request: Request, call_next):
    client_ip = request.client.host
    logger.info(f"AUDIT LOG: Inbound {request.method} request to {request.url.path} from {client_ip}")
    response = await call_next(request)
    logger.info(f"AUDIT LOG: Outbound response status {response.status_code} for {request.url.path}")
    return response


# Pydantic Schemas from Data Contracts

class CreateStockAlertContractInput(BaseModel):
    
    ticker_symbol: str
    
    alert_price: str
    
    alert_type: str
    
    user_id: str
    
    notification_channel: str
    
    threshold_operator: str
    

class CreateStockAlertContractOutput(BaseModel):
    
    alert_id: str
    
    ticker_symbol: str
    
    alert_price: str
    
    alert_type: str
    
    status: str
    
    created_at: str
    
    user_id: str
    

class GetStockAlertsContractInput(BaseModel):
    
    user_id: str
    

class GetStockAlertsContractOutput(BaseModel):
    
    alerts: str
    
    count: str
    

class DeleteStockAlertContractInput(BaseModel):
    
    alert_id: str
    
    user_id: str
    

class DeleteStockAlertContractOutput(BaseModel):
    
    alert_id: str
    
    status: str
    
    message: str
    


# API Endpoints



  
    
  

  

  

@app.post("/api/v1/alerts", 
    response_model=CreateStockAlertContractOutput, 
    summary="Creates a new stock price alert for a specified ticker and user.",
    dependencies=[Depends(check_rate_limit), Depends(verify_auth)]
)
async def creates_a_new_stock_price_alert_for_a_specified_ticker_and_user(
    
    
    payload: CreateStockAlertContractInput
    
):
    logger.info(f"Executing endpoint: /api/v1/alerts")
    
    # Deterministic Mock Response fulfilling the exact Output Data Contract
    response_data = {}
    
      
        
    response_data["alert_id"] = "gen_createstockalertcontract_" + str(int(time.time()))
        
      
        
          
    response_data["ticker_symbol"] = getattr(payload, "ticker_symbol", "mock_value_for_ticker_symbol")
          
        
      
        
          
    response_data["alert_price"] = getattr(payload, "alert_price", "mock_value_for_alert_price")
          
        
      
        
          
    response_data["alert_type"] = getattr(payload, "alert_type", "mock_value_for_alert_type")
          
        
      
        
    response_data["status"] = "SUCCESS"
        
      
        
          
    response_data["created_at"] = getattr(payload, "created_at", "mock_value_for_created_at")
          
        
      
        
    response_data["user_id"] = "gen_createstockalertcontract_" + str(int(time.time()))
        
      
    
    
    return response_data



  

  
    
  

  

@app.get("/api/v1/alerts/{user_id}", 
    response_model=GetStockAlertsContractOutput, 
    summary="Retrieves all active stock price alerts for a given user ID.",
    dependencies=[Depends(check_rate_limit), Depends(verify_auth)]
)
async def retrieves_all_active_stock_price_alerts_for_a_given_user_id(
    
    user_id: str,
    
    
):
    logger.info(f"Executing endpoint: /api/v1/alerts/{user_id}")
    
    # Deterministic Mock Response fulfilling the exact Output Data Contract
    response_data = {}
    
      
        
          
    response_data["alerts"] = "mock_value_for_alerts"
          
        
      
        
          
    response_data["count"] = "mock_value_for_count"
          
        
      
    
    
    return response_data



  

  

  
    
  

@app.delete("/api/v1/alerts/{alert_id}", 
    response_model=DeleteStockAlertContractOutput, 
    summary="Deletes a specific stock price alert by its ID.",
    dependencies=[Depends(check_rate_limit), Depends(verify_auth)]
)
async def deletes_a_specific_stock_price_alert_by_its_id(
    
    alert_id: str,
    
    
):
    logger.info(f"Executing endpoint: /api/v1/alerts/{alert_id}")
    
    # Deterministic Mock Response fulfilling the exact Output Data Contract
    response_data = {}
    
      
        
    response_data["alert_id"] = "gen_deletestockalertcontract_" + str(int(time.time()))
        
      
        
    response_data["status"] = "SUCCESS"
        
      
        
          
    response_data["message"] = "mock_value_for_message"
          
        
      
    
    
    return response_data
