from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pydantic import BaseModel
import sqlite3

from core.database import get_db_connection
from security.minting_engine import minting_engine
from routes.taxonomy_router import router as taxonomy_router

app = FastAPI(title="Module 0: Gateway Core")

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5175", "http://127.0.0.1:5175"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the Taxonomy Router
app.include_router(taxonomy_router, prefix="/api/v1/taxonomy", tags=["Taxonomy"])

class LoginRequest(BaseModel):
    emp_id: str
    pin: str

@app.post("/api/v1/auth/login")
def login(request: LoginRequest, response: Response):
    """
    Centralized Identity Minting Endpoint.
    Validates credentials against the Taxonomy Core and mints an RS256 JWT.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM erp_employees WHERE emp_id = ?", (request.emp_id,))
        user = cursor.fetchone()
        
        import bcrypt
        
        pin_verified = False
        if user:
            if user["pin_hash"]:
                try:
                    pin_verified = bcrypt.checkpw(request.pin.encode("utf-8"), user["pin_hash"].encode("utf-8"))
                except Exception:
                    pass
            if not pin_verified and user["pin"]:
                pin_verified = (user["pin"] == request.pin)
                
        if not user or not pin_verified:
            raise HTTPException(status_code=401, detail="Invalid Employee ID or PIN")
            
        if user["status"] != "ACTIVE":
            raise HTTPException(status_code=403, detail="Account is disabled")

        # Construct the JWT Payload
        token_payload = {
            "sub": user["emp_id"],
            "role": user["role"],
            "department": user["department"],
            "name": f"{user['first_name']} {user['last_name']}"
        }
        
        # Mint Dual Tokens
        access_token = minting_engine.mint_access_token(token_payload)
        refresh_token = minting_engine.mint_refresh_token(token_payload)
        
        # Actuate the HttpOnly Cookie
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=False, # Set to True when migrating behind an HTTPS load balancer
            samesite="lax", # 'lax' required for localhost cross-port bridging, 'strict' in production
            max_age=7 * 24 * 60 * 60 # 7 Days
        )
        
        # Only expose the short-lived access token to the DOM
        return {
            "status": "success",
            "access_token": access_token,
            "user": token_payload
        }
    finally:
        conn.close()

@app.post("/api/v1/auth/refresh")
def refresh(request: Request):
    """
    Autonomous Refresh Actuation.
    Extracts the HttpOnly refresh cookie, verifies database state, and remints the access token.
    """
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="Refresh Token Missing.")
        
    payload = minting_engine.verify_token(token)
    if not payload:
        raise HTTPException(status_code=403, detail="Cryptographic Verification Failed.")
        
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=403, detail="Invalid Token Type.")
        
    # State Verification: Query gateway_core.db to ensure user is still ACTIVE
    emp_id = payload.get("sub")
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT status, role, department, first_name, last_name FROM erp_employees WHERE emp_id = ?", (emp_id,))
        user = cursor.fetchone()
        
        if not user or user["status"] != "ACTIVE":
            raise HTTPException(status_code=403, detail="Account is disabled or terminated.")
            
        # Re-Mint Access Token
        token_payload = {
            "sub": emp_id,
            "role": user["role"],
            "department": user["department"],
            "name": f"{user['first_name']} {user['last_name']}"
        }
        
        access_token = minting_engine.mint_access_token(token_payload)
        
        return {
            "status": "success",
            "access_token": access_token
        }
    finally:
        conn.close()

@app.get("/api/v1/auth/public-key")
def get_public_key():
    """Autonomous Key Distribution Endpoint for downstream microservices."""
    from security.minting_engine import PUBLIC_KEY_PATH
    with open(PUBLIC_KEY_PATH, "r") as key_file:
        pub_key = key_file.read()
    return {"public_key": pub_key}

if __name__ == "__main__":
    # Module 0 strictly binds to Port 9000 to prevent collisions
    uvicorn.run(app, host="0.0.0.0", port=9000)
